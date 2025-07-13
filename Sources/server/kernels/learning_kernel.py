"""
Learning kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional, Dict, Any
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage, PersonPresenceMessage, ConceptCreationRequest, ConversationMessage, GoalCreationRequest
from .base_kernel import BaseKernel
from llm_service import LLMService, OpenAIProvider, ToolDefinition
from llm_template import llm_template


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
            description="Create a new learning goal in memory when you identify a learning opportunity or knowledge gap",
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural language description of the learning goal"
                    }
                },
                "required": ["description"]
            },
            function=self._create_goal_tool
        )
        
        # Do nothing tool
        do_nothing_tool = ToolDefinition(
            name="do_nothing",
            description="Take no action - use this when no learning goals need to be created or when sufficient learning goals already exist",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for not creating a learning goal"
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
    
    async def _get_person_knowledge(self, memory_kernel, person_id: str) -> list:
        """Get knowledge concepts that are linked to this person's percept."""
        try:
            # First find the person's percept
            person_percepts = await memory_kernel.search_concepts.remote(f"person percept {person_id}", limit=10, concept_type="percept")
            
            if not person_percepts:
                return []
            
            # Get the most relevant percept (first one)
            person_percept = person_percepts[0]
            percept_id = person_percept.get("id")
            
            if not percept_id:
                return []
            
            # Get all knowledge concepts
            all_knowledge = await memory_kernel.get_concepts_by_type.remote("knowledge")
            
            # Filter knowledge that's linked to this person's percept
            person_knowledge = []
            for knowledge in all_knowledge:
                knowledge_data = knowledge.get("data", {})
                if knowledge_data.get("linked_person_percept") == percept_id:
                    person_knowledge.append({
                        "id": knowledge.get("id"),
                        "type": knowledge_data.get("knowledge_type", "unknown"),
                        "description": knowledge_data.get("description", ""),
                        "details": knowledge_data.get("details", {}),
                        "activation": knowledge.get("activation", 0)
                    })
            
            print(f"LearningKernel: Found {len(person_knowledge)} knowledge items linked to person {person_id}")
            return person_knowledge
            
        except Exception as e:
            print(f"LearningKernel: Error getting person knowledge for {person_id}: {e}")
            return []
    
    async def _analyze_learning_opportunities(self, person_id: str) -> None:
        """Analyze the current context using LLM to identify learning opportunities and create appropriate goals."""
        if not self.llm_service:
            print("LearningKernel: LLM service not available, skipping learning opportunity analysis")
            return
        
        try:
            # Get current context information from memory
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Search for person-related concepts
            person_concepts = await memory_kernel.search_concepts.remote(f"person {person_id}", limit=10, concept_type="person")
            person_percepts = await memory_kernel.search_concepts.remote(f"person percept {person_id}", limit=10, concept_type="percept")
            
            # Get knowledge connected to this person's percept
            person_knowledge = await self._get_person_knowledge(memory_kernel, person_id)
            
            # Search for existing goals (both specific to this person and general learning goals)
            person_specific_goals = await memory_kernel.search_concepts.remote(f"learn person {person_id}", limit=10, concept_type="goal")
            all_goals = await memory_kernel.search_concepts.remote(f"learn", limit=20, concept_type="goal")
            
            # Get recent conversation history for additional context
            conversation_history = await memory_kernel.get_conversation_history.remote(limit=5)
            
            # Build comprehensive context for LLM
            context_info = {
                "person_id": person_id,
                "person_concepts": person_concepts,
                "person_percepts": person_percepts,
                "person_specific_goals": person_specific_goals,
                "all_learning_goals": all_goals,
                "recent_conversations": conversation_history
            }
            
            # Use template system to generate prompts
            template_result = llm_template.call(
                "learning_opportunities",
                person_id=person_id,
                person_concepts_count=len(person_concepts),
                person_percepts_count=len(person_percepts),
                person_knowledge_count=len(person_knowledge),
                person_specific_goals_count=len(person_specific_goals),
                all_goals_count=len(all_goals),
                conversation_history_count=len(conversation_history),
                person_concepts=person_concepts,
                person_percepts=person_percepts,
                person_knowledge=person_knowledge,
                person_specific_goals=person_specific_goals,
                all_goals=all_goals,
                conversation_history=conversation_history
            )
            
            system_prompt = template_result['system_prompt']
            user_message = template_result['user_message']
            
            # Call LLM with tools (limit to one tool call)
            response = await self.llm_service.process_message_with_tools(
                message=user_message,
                system_prompt=system_prompt,
                tools=self.available_tools,
                temperature=0.3,
                max_tokens=200,
                max_tool_calls=1,
                template_name="learning_opportunities"
            )
            
            print(f"LearningKernel: LLM analysis response for context with person {person_id}: {response.get('content', 'No content')}")
            
            # Execute any tool calls
            if response.get('tool_calls'):
                print(f"LearningKernel: Executing {len(response['tool_calls'])} tool calls for learning opportunities")
                tool_results = await self.llm_service.execute_tools(response['tool_calls'], self.available_tools)
                
                for result in tool_results:
                    if result['success']:
                        if result['function'] == 'do_nothing':
                            print(f"LearningKernel: No learning goals created for person {person_id}: {result['result']}")
                        else:
                            print(f"LearningKernel: Learning goal tool {result['function']} executed successfully: {result['result']}")
                    else:
                        print(f"LearningKernel: Learning goal tool {result['function']} failed: {result['result']}")
            
        except Exception as e:
            print(f"LearningKernel: Error analyzing learning opportunities for person {person_id}: {e}")
    
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
                
                # After adding person percept to context, analyze for learning opportunities
                print(f"LearningKernel: Analyzing learning opportunities for person {message.person_id}")
                await self._analyze_learning_opportunities(message.person_id)
            else:
                print("LearningKernel: Person not present or no person_id provided")
                
        elif isinstance(message, ConversationMessage):
            print(f"[{timestamp}] LearningKernel: Processing conversation message from {message.speaker}: {message.content[:100]}...")
            
            # Forward to MemoryKernel for storage (non-blocking)
            await self.send_to_kernel(KernelID.MEMORY, message)
            
            send_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp} -> {send_time}] LearningKernel -> MemoryKernel (conversation, non-blocking)")
            
        elif isinstance(message, ConceptCreationRequest):
            print(f"[{timestamp}] LearningKernel: Processing ConceptCreationRequest for {message.concept_type}")
            
            # Forward to MemoryKernel for storage (non-blocking)
            await self.send_to_kernel(KernelID.MEMORY, message)
            
            send_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp} -> {send_time}] LearningKernel -> MemoryKernel (concept creation, non-blocking)")
            
        elif isinstance(message, GoalCreationRequest):
            print(f"[{timestamp}] LearningKernel: Processing GoalCreationRequest: {message.description}")
            
            # Forward to MemoryKernel for storage (non-blocking)
            await self.send_to_kernel(KernelID.MEMORY, message)
            
            send_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp} -> {send_time}] LearningKernel -> MemoryKernel (goal creation, non-blocking)")
                
        else:
            print(f"[{timestamp}] LearningKernel: Unsupported message type: {type(message)}")
            return 