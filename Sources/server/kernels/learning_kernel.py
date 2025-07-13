"""
Learning kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional, Dict, Any
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage, PersonPresenceMessage, ConceptCreationRequest, ConversationMessage, GoalCreationRequest
from .base_kernel import BaseKernel
from llm_service import LLMService, OpenAIProvider, ToolDefinition


@ray.remote
class LearningKernel(BaseKernel):
    """Learning kernel implementation with non-blocking message routing."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.LEARNING, custom_handler)
        
        # Initialize LLM service
        try:
            openai_provider = OpenAIProvider()
            self.llm_service = LLMService(openai_provider)
        except Exception as e:
            print(f"LearningKernel: Failed to initialize LLM service: {e}")
            self.llm_service = None
        
        # Initialize tools
        self._initialize_tools()
    
    def _initialize_tools(self) -> None:
        """Initialize the available tools for the learning kernel."""
        # Create goal tool
        create_goal_tool = ToolDefinition(
            name="create_goal",
            description="Create a new goal in memory when you need to learn more about a person who is not yet known",
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural language description of the goal"
                    }
                },
                "required": ["description"]
            },
            function=self._create_goal_tool
        )
        
        # Do nothing tool
        do_nothing_tool = ToolDefinition(
            name="do_nothing",
            description="Take no action - use this when no goal needs to be created or when a goal already exists",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for not creating a goal"
                    }
                },
                "required": ["reason"]
            },
            function=self._do_nothing_tool
        )
        
        self.available_tools = [create_goal_tool, do_nothing_tool]
    
    async def _create_goal_tool(self, description: str) -> str:
        """Tool function to create a goal."""
        try:
            # Create goal request
            goal_request = GoalCreationRequest(
                source_kernel_id=KernelID.LEARNING,
                description=description,
                status="open"
            )
            
            # Send to memory kernel
            await self.send_to_kernel(KernelID.MEMORY, goal_request)
            
            return f"Goal created: {description}"
        except Exception as e:
            return f"Error creating goal: {str(e)}"
    
    async def _do_nothing_tool(self, reason: str) -> str:
        """Tool function to do nothing - used when no goal needs to be created."""
        return f"No action taken: {reason}"
    
    async def _analyze_person_with_llm(self, person_id: str) -> None:
        """Analyze a person using LLM to determine if a goal should be created."""
        if not self.llm_service:
            print("LearningKernel: LLM service not available, skipping person analysis")
            return
        
        try:
            # Get person information from memory
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Search for person-related concepts
            person_concepts = await memory_kernel.search_concepts.remote(f"person {person_id}", limit=10, concept_type="person")
            person_percepts = await memory_kernel.search_concepts.remote(f"person percept {person_id}", limit=10, concept_type="percept")
            
            # Search for existing goals related to this person
            existing_goals = await memory_kernel.search_concepts.remote(f"learn person {person_id}", limit=10, concept_type="goal")
            
            # Build context for LLM
            context_info = {
                "person_id": person_id,
                "person_concepts": person_concepts,
                "person_percepts": person_percepts,
                "existing_goals": existing_goals
            }
            
            # Create system prompt
            system_prompt = """You are a learning system analyzing a person who has been detected. 
Your task is to determine if you need to create a goal to learn more about this person.

You should create a goal if:
- The person has no name or identity information
- The person is not well-known to the system
- You need to learn more about who this person is
- AND there are no existing goals already created for learning about this person

You should use the do_nothing tool if:
- The person is already well-known (has name/identity information)
- There are already existing goals for learning about this person
- No additional learning goals are needed

If you determine that a goal should be created, use the create_goal tool to create an appropriate goal.
The goal should be in natural language, for example: "Learn the name and identity of the person with ID person_123"

Be concise and focused on the specific need to identify or learn about this person."""
            
            # Create user message with context
            user_message = f"""
Person detected: {person_id}

Context information:
- Person concepts found: {len(person_concepts)}
- Person percepts found: {len(person_percepts)}
- Existing goals found: {len(existing_goals)}

Person concepts: {person_concepts}
Person percepts: {person_percepts}
Existing goals: {existing_goals}

Based on this information, determine if I need to create a goal to learn more about this person.
If the person is not well-known or lacks identity information AND there are no existing goals for learning about them, create an appropriate goal.
If there are already existing goals or the person is well-known, use the do_nothing tool.
"""
            
            # Call LLM with tools
            response = await self.llm_service.process_message_with_tools(
                message=user_message,
                system_prompt=system_prompt,
                tools=self.available_tools,
                temperature=0.3,
                max_tokens=200
            )
            
            print(f"LearningKernel: LLM response for person {person_id}: {response.get('content', 'No content')}")
            
            # Execute any tool calls
            if response.get('tool_calls'):
                print(f"LearningKernel: Executing {len(response['tool_calls'])} tool calls")
                tool_results = await self.llm_service.execute_tools(response['tool_calls'], self.available_tools)
                
                for result in tool_results:
                    if result['success']:
                        if result['function'] == 'do_nothing':
                            print(f"LearningKernel: No action taken for person {person_id}: {result['result']}")
                        else:
                            print(f"LearningKernel: Tool {result['function']} executed successfully: {result['result']}")
                    else:
                        print(f"LearningKernel: Tool {result['function']} failed: {result['result']}")
            
        except Exception as e:
            print(f"LearningKernel: Error analyzing person {person_id}: {e}")
    
    async def _person_percept_exists(self, person_id: str) -> bool:
        """Check if a person percept already exists by querying MemoryKernel."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            exists = await memory_kernel.check_percept_exists.remote(person_id)
            return exists
        except ValueError:
            print("LearningKernel: Error - MemoryKernel not found")
            return False
    
    async def _request_person_percept_creation(self, person_id: str) -> None:
        """Request creation of a new person percept concept (non-blocking)."""
        concept_data = {
            "person_id": person_id,
            "percept_type": "person_presence",
            "description": f"Person {person_id} detected"
        }
        
        request = ConceptCreationRequest(
            source_kernel_id=KernelID.LEARNING,
            concept_type="percept",
            concept_data=concept_data
        )
        
        # Send request to MemoryKernel (non-blocking)
        await self.send_to_kernel(KernelID.MEMORY, request)
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] LearningKernel -> MemoryKernel: Requested creation of person percept for {person_id} (non-blocking)")
    
    async def _update_person_percept_context(self, person_id: str) -> None:
        """Update an existing person percept to link to current context."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            updated = await memory_kernel.update_person_percept_context.remote(person_id)
            if updated:
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{timestamp}] LearningKernel: Updated context for existing person percept {person_id}")
            else:
                print(f"LearningKernel: Failed to update context for person percept {person_id}")
        except ValueError:
            print("LearningKernel: Error - MemoryKernel not found")
    
    async def receive(self, message: KernelMessage) -> None:
        """Process learning messages and forward to Memory (non-blocking)."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if isinstance(message, TextMessage):
            content = message.content
            print(f"[{timestamp}] LearningKernel: Ignoring TextMessage (no longer storing as facts): {content}")
                
        elif isinstance(message, PersonPresenceMessage):
            print(f"[{timestamp}] LearningKernel: Processing person presence - present: {message.is_present}, person_id: {message.person_id}")
            
            # Only process if person is present and we have a person_id
            if message.is_present and message.person_id:
                # Check if person percept already exists via MemoryKernel
                if not await self._person_percept_exists(message.person_id):
                    print(f"LearningKernel: Person percept for {message.person_id} not found, requesting creation")
                    await self._request_person_percept_creation(message.person_id)
                else:
                    print(f"LearningKernel: Person percept for {message.person_id} already exists, updating context")
                    await self._update_person_percept_context(message.person_id)
                
                # After adding person percept to context, analyze with LLM to determine if goal should be created
                print(f"LearningKernel: Analyzing person {message.person_id} with LLM")
                await self._analyze_person_with_llm(message.person_id)
            else:
                print("LearningKernel: Person not present or no person_id provided")
                
        elif isinstance(message, ConversationMessage):
            print(f"[{timestamp}] LearningKernel: Processing conversation message from {message.speaker}: {message.content[:100]}...")
            
            # Forward to MemoryKernel for storage (non-blocking)
            await self.send_to_kernel(KernelID.MEMORY, message)
            
            send_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp} -> {send_time}] LearningKernel -> MemoryKernel (conversation, non-blocking)")
                
        else:
            print(f"[{timestamp}] LearningKernel: Unsupported message type: {type(message)}")
            return 