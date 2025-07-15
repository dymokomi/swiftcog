"""
Executive kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
import datetime
import asyncio
from swiftcog_types import KernelID, KernelMessage, TextMessage, TextBubbleCommand, ShowThinkingCommand, HideThinkingCommand, create_display_command_json, ConversationMessage, GoalCreationRequest, ConceptCreationRequest
from .base_kernel import BaseKernel
from llm_template import llm_template
from llm_service import ToolDefinition, LLMService, OpenAIProvider


@ray.remote
class ExecutiveKernel(BaseKernel):
    """Executive kernel implementation with non-blocking message routing and proactive goal checking."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.EXECUTIVE, custom_handler)
        self.last_interaction_time = datetime.datetime.now()
        self.proactive_task: Optional[asyncio.Task] = None
        self.is_processing_proactive = False
        self.proactive_check_interval = 5.0  # seconds
        self._thinking_shown = False
        
        # Initialize LLM service
        try:
            openai_provider = OpenAIProvider()
            self.llm_service = LLMService(openai_provider)
        except Exception as e:
            print(f"ExecutiveKernel: Failed to initialize LLM service: {e}")
            self.llm_service = None
        
        # Initialize tools for goal and knowledge management
        self._initialize_tools()
    
    def _initialize_tools(self) -> None:
        """Initialize the available tools for executive decision making."""
        # Complete goal tool
        complete_goal_tool = ToolDefinition(
            name="complete_goal",
            description="Mark a learning goal as completed when you have achieved the learning objective",
            parameters={
                "type": "object",
                "properties": {
                    "goal_id": {
                        "type": "string", 
                        "description": "ID of the goal to mark as completed"
                    },
                    "completion_summary": {
                        "type": "string",
                        "description": "Brief summary of what was learned or achieved"
                    }
                },
                "required": ["goal_id", "completion_summary"]
            },
            function=self._complete_goal_tool
        )
        
        # Add knowledge tool
        add_knowledge_tool = ToolDefinition(
            name="add_knowledge",
            description="Add new factual knowledge or concepts to memory for future reference",
            parameters={
                "type": "object",
                "properties": {
                    "knowledge_type": {
                        "type": "string",
                        "description": "Type of knowledge (personal_info, concept, fact, preference, etc.)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the knowledge to store"
                    },
                    "details": {
                        "type": "object",
                        "description": "Additional structured details about this knowledge"
                    }
                },
                "required": ["knowledge_type", "description"]
            },
            function=self._add_knowledge_tool
        )
        
        # Create goal tool
        create_goal_tool = ToolDefinition(
            name="create_goal",
            description="Create a new learning goal when you identify something important to learn",
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural language description of the learning goal"
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority level: high, medium, low",
                        "enum": ["high", "medium", "low"]
                    }
                },
                "required": ["description"]
            },
            function=self._create_goal_tool
        )
        
        # Respond only tool (no-op, just respond)
        respond_only_tool = ToolDefinition(
            name="respond_only",
            description="Just respond to the user without taking any goal or memory actions",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for not taking any actions"
                    }
                },
                "required": ["reason"]
            },
            function=self._respond_only_tool
        )
        
        # Memory query tools
        get_memory_stats_tool = ToolDefinition(
            name="get_memory_stats",
            description="Get overview of memory state including concept counts, active concepts, and memory statistics",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for checking memory stats"
                    }
                },
                "required": ["reason"]
            },
            function=self._get_memory_stats_tool
        )
        
        get_user_knowledge_tool = ToolDefinition(
            name="get_user_knowledge",
            description="Search for what the AI knows about the user, including personal information and preferences",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional search query to filter user knowledge (empty for all)"
                    }
                },
                "required": []
            },
            function=self._get_user_knowledge_tool
        )
        
        get_active_goals_tool = ToolDefinition(
            name="get_active_goals",
            description="List current active learning goals and their status",
            parameters={
                "type": "object",
                "properties": {
                    "include_completed": {
                        "type": "boolean",
                        "description": "Whether to include completed goals (default: false)"
                    }
                },
                "required": []
            },
            function=self._get_active_goals_tool
        )
        
        search_memory_tool = ToolDefinition(
            name="search_memory",
            description="Search memory for specific information using text matching",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant memories"
                    },
                    "concept_type": {
                        "type": "string",
                        "description": "Optional concept type to filter by (knowledge, goal, conversation, percept, etc.)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)"
                    }
                },
                "required": ["query"]
            },
            function=self._search_memory_tool
        )
        
        self.available_tools = [complete_goal_tool, add_knowledge_tool, create_goal_tool, respond_only_tool, 
                               get_memory_stats_tool, get_user_knowledge_tool, get_active_goals_tool, search_memory_tool]
    
    async def _complete_goal_tool(self, goal_id: str, completion_summary: str) -> str:
        """Tool function to mark a goal as completed."""
        try:
            # Update goal status to completed
            memory_kernel = ray.get_actor("MemoryKernel")
            success = await memory_kernel.update_concept.remote(
                goal_id,
                {"data": {"status": "completed", "completion_summary": completion_summary}}
            )
            
            if success:
                print(f"ExecutiveKernel: Completed goal {goal_id}: {completion_summary}")
                return f"Goal completed: {completion_summary}"
            else:
                return f"Error: Could not find goal {goal_id} to complete"
                
        except Exception as e:
            print(f"ExecutiveKernel: Error completing goal {goal_id}: {e}")
            return f"Error completing goal: {str(e)}"
    
    async def _add_knowledge_tool(self, knowledge_type: str, description: str, details: dict = None) -> str:
        """Tool function to add knowledge to memory via Learning kernel."""
        try:
            # Get memory kernel to find active person percepts
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Create a concept creation request for the knowledge
            concept_data = {
                "knowledge_type": knowledge_type,
                "description": description,
                "details": details or {},
                "source": "executive_conversation"
            }
            
            # If this is personal information, try to link it to active person percepts
            person_percept_id = None
            if knowledge_type in ["personal_info", "preference", "fact", "interest", "skill", "goal", "relationship"]:
                # Get active person percepts
                person_percepts = await memory_kernel.get_concepts_by_type.remote("percept")
                active_percepts = [p for p in person_percepts if p.get("activation", 0) > 0]
                
                if active_percepts:
                    # Use the most recently activated percept
                    most_recent = max(active_percepts, key=lambda p: p.get("activation", 0))
                    person_percept_id = most_recent.get("id")
                    concept_data["linked_person_percept"] = person_percept_id
                    print(f"ExecutiveKernel: Linking {knowledge_type} knowledge to person percept {person_percept_id}")
            
            concept_request = ConceptCreationRequest(
                source_kernel_id=KernelID.EXECUTIVE,
                concept_type="knowledge",
                concept_data=concept_data
            )
            
            # Send to Learning kernel for storage
            await self.send_to_kernel(KernelID.LEARNING, concept_request)
            
            print(f"ExecutiveKernel: Added knowledge - {knowledge_type}: {description}")
            return f"Added knowledge: {description}"
            
        except Exception as e:
            print(f"ExecutiveKernel: Error adding knowledge: {e}")
            return f"Error adding knowledge: {str(e)}"
    
    async def _create_goal_tool(self, description: str, priority: str = "medium") -> str:
        """Tool function to create a new learning goal via Learning kernel."""
        try:
            # Create a goal creation request
            goal_request = GoalCreationRequest(
                source_kernel_id=KernelID.EXECUTIVE,
                description=description,
                status="open"
            )
            
            # Send to Learning kernel for creation
            await self.send_to_kernel(KernelID.LEARNING, goal_request)
            
            print(f"ExecutiveKernel: Created new goal: {description}")
            return f"Created learning goal: {description}"
            
        except Exception as e:
            print(f"ExecutiveKernel: Error creating goal: {e}")
            return f"Error creating goal: {str(e)}"
    
    async def _respond_only_tool(self, reason: str) -> str:
        """Tool function for when no actions are needed, just responding."""
        print(f"ExecutiveKernel: Responding only - {reason}")
        return f"No actions taken: {reason}"
    
    async def _get_memory_stats_tool(self, reason: str) -> str:
        """Tool function to get memory statistics and overview."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            stats = await memory_kernel.get_concept_graph_stats.remote()
            
            # Format the stats nicely
            total_concepts = stats.get("total_concepts", 0)
            total_relations = stats.get("total_relations", 0)
            active_concepts = stats.get("active_concepts", 0)
            concepts_by_type = stats.get("concepts_by_type", {})
            
            result = f"Memory Statistics:\n"
            result += f"- Total concepts: {total_concepts}\n"
            result += f"- Active concepts: {active_concepts}\n"
            result += f"- Total relations: {total_relations}\n"
            result += f"- Concepts by type:\n"
            
            for ctype, count in concepts_by_type.items():
                result += f"  • {ctype}: {count}\n"
            
            print(f"ExecutiveKernel: Retrieved memory stats - {total_concepts} concepts, {active_concepts} active")
            return result
            
        except Exception as e:
            print(f"ExecutiveKernel: Error getting memory stats: {e}")
            return f"Error retrieving memory stats: {str(e)}"
    
    async def _get_user_knowledge_tool(self, query: str = "") -> str:
        """Tool function to search for what the AI knows about the currently active user."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Get active person percepts first
            person_percepts = await memory_kernel.get_concepts_by_type.remote("percept")
            active_percepts = [p for p in person_percepts if p.get("activation", 0) > 0]
            
            if not active_percepts:
                return "No person is currently present, so I don't have context for any user knowledge."
            
            # Get all knowledge concepts
            all_knowledge = await memory_kernel.get_concepts_by_type.remote("knowledge")
            
            # Filter for knowledge linked to currently active person percepts and that is active
            user_knowledge = []
            active_percept_ids = {p.get("id") for p in active_percepts}
            
            for knowledge in all_knowledge:
                knowledge_data = knowledge.get("data", {})
                knowledge_type = knowledge_data.get("knowledge_type", "")
                description = knowledge_data.get("description", "")
                activation = knowledge.get("activation", 0)
                linked_percept = knowledge_data.get("linked_person_percept")
                
                # Only include knowledge that is:
                # 1. Currently active (activation > 0)
                # 2. Linked to a currently active person percept OR is general knowledge
                # 3. Matches the query if provided
                is_person_specific = linked_percept and linked_percept in active_percept_ids
                is_general_knowledge = not linked_percept and knowledge_type in ["personal_info", "preference", "fact", "interest", "skill", "goal", "relationship"]
                is_active = activation > 0
                matches_query = not query or query.lower() in description.lower()
                
                if is_active and (is_person_specific or is_general_knowledge) and matches_query:
                    user_knowledge.append(knowledge)
            
            if not user_knowledge:
                current_person_ids = [p.get("data", {}).get("person_id", "unknown") for p in active_percepts]
                return f"No knowledge found for currently present person(s): {', '.join(current_person_ids)}"
            
            # Sort by creation time (newest first)
            user_knowledge.sort(key=lambda k: k.get("meta", {}).get("created", 0), reverse=True)
            
            # Show which person(s) we're displaying knowledge for
            current_person_ids = [p.get("data", {}).get("person_id", "unknown") for p in active_percepts]
            result = f"What I know about the currently present person ({', '.join(current_person_ids)}):\n"
            
            for knowledge in user_knowledge[:10]:  # Show top 10
                knowledge_data = knowledge.get("data", {})
                knowledge_type = knowledge_data.get("knowledge_type", "unknown")
                description = knowledge_data.get("description", "")
                
                result += f"- [{knowledge_type}] {description}\n"
            
            if len(user_knowledge) > 10:
                result += f"... and {len(user_knowledge) - 10} more items"
            
            print(f"ExecutiveKernel: Retrieved {len(user_knowledge)} knowledge items for currently active person(s)")
            return result
            
        except Exception as e:
            print(f"ExecutiveKernel: Error getting user knowledge: {e}")
            return f"Error retrieving user knowledge: {str(e)}"
    
    async def _get_active_goals_tool(self, include_completed: bool = False) -> str:
        """Tool function to get active learning goals."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            all_goals = await memory_kernel.get_concepts_by_type.remote("goal")
            
            if not all_goals:
                return "No learning goals found."
            
            # Filter goals based on status
            filtered_goals = []
            for goal in all_goals:
                goal_data = goal.get("data", {})
                status = goal_data.get("status", "unknown")
                
                if include_completed:
                    filtered_goals.append(goal)
                elif status != "completed":
                    filtered_goals.append(goal)
            
            if not filtered_goals:
                return "No active learning goals found."
            
            # Sort by activation (most active first), then by creation time
            filtered_goals.sort(key=lambda g: (g.get("activation", 0), g.get("meta", {}).get("created", 0)), reverse=True)
            
            result = f"Learning Goals:\n"
            for goal in filtered_goals:
                goal_data = goal.get("data", {})
                description = goal_data.get("description", "No description")
                status = goal_data.get("status", "unknown")
                activation = goal.get("activation", 0)
                
                status_icon = {
                    "open": "○",
                    "in_progress": "●",
                    "completed": "✓"
                }.get(status, "?")
                
                activation_info = f" (activation: {activation:.2f})" if activation > 0 else ""
                result += f"{status_icon} {description} [{status}]{activation_info}\n"
            
            print(f"ExecutiveKernel: Retrieved {len(filtered_goals)} goals")
            return result
            
        except Exception as e:
            print(f"ExecutiveKernel: Error getting active goals: {e}")
            return f"Error retrieving active goals: {str(e)}"
    
    async def _search_memory_tool(self, query: str, concept_type: str = None, limit: int = 5) -> str:
        """Tool function to search memory for specific information."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Use the memory kernel's search functionality
            if concept_type:
                results = await memory_kernel.search_concepts.remote(query, limit, concept_type)
            else:
                results = await memory_kernel.search_concepts.remote(query, limit)
            
            if not results:
                return f"No memories found matching '{query}'"
            
            result = f"Search results for '{query}':\n"
            for i, item in enumerate(results, 1):
                concept_type = item.get("type", "unknown")
                label = item.get("label", "No label")
                score = item.get("score", 0)
                activation = item.get("activation", 0)
                
                # Show additional details for different concept types
                data = item.get("data", {})
                details = ""
                if concept_type == "knowledge":
                    knowledge_type = data.get("knowledge_type", "")
                    if knowledge_type:
                        details = f" ({knowledge_type})"
                elif concept_type == "goal":
                    status = data.get("status", "")
                    if status:
                        details = f" ({status})"
                elif concept_type == "conversation":
                    speaker = data.get("speaker", "")
                    if speaker:
                        details = f" by {speaker}"
                
                activation_info = f" [active: {activation:.2f}]" if activation > 0 else ""
                result += f"{i}. [{concept_type}] {label}{details}{activation_info}\n"
            
            print(f"ExecutiveKernel: Found {len(results)} memory results for '{query}'")
            return result
            
        except Exception as e:
            print(f"ExecutiveKernel: Error searching memory: {e}")
            return f"Error searching memory: {str(e)}"
        
    async def start_proactive_monitoring(self) -> None:
        """Start the proactive goal checking background task."""
        if self.proactive_task is None or self.proactive_task.done():
            self.proactive_task = asyncio.create_task(self._proactive_monitoring_loop())
            print("ExecutiveKernel: Started proactive goal monitoring")
    
    async def stop_proactive_monitoring(self) -> None:
        """Stop the proactive goal checking background task."""
        if self.proactive_task and not self.proactive_task.done():
            self.proactive_task.cancel()
            try:
                await self.proactive_task
            except asyncio.CancelledError:
                pass
            print("ExecutiveKernel: Stopped proactive goal monitoring")
    
    async def _proactive_monitoring_loop(self) -> None:
        """Background task that monitors for inactivity and triggers proactive goal checking."""
        while True:
            try:
                await asyncio.sleep(self.proactive_check_interval)
                
                # Check if we should trigger proactive goal checking
                if self._should_trigger_proactive_check():
                    await self._perform_proactive_goal_check()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"ExecutiveKernel: Error in proactive monitoring loop: {e}")
                await asyncio.sleep(self.proactive_check_interval)
    
    def _should_trigger_proactive_check(self) -> bool:
        """Check if we should trigger a proactive goal check based on inactivity."""
        if self.is_processing_proactive:
            return False
            
        current_time = datetime.datetime.now()
        time_since_last_interaction = (current_time - self.last_interaction_time).total_seconds()
        
        # Trigger if it's been more than 5 seconds since last interaction
        return time_since_last_interaction > 5.0
    
    async def _perform_proactive_goal_check(self) -> None:
        """Perform the proactive goal check using LLM."""
        if self.is_processing_proactive:
            return
            
        self.is_processing_proactive = True
        
        try:
            start_time = self._get_current_time()
            print(f"[{start_time}] ExecutiveKernel: Starting proactive goal check")
            
            # Check if local LLM service is available
            if not self.llm_service:
                print("ExecutiveKernel: Local LLM service not available for proactive check")
                return
                
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Get goals and context first
            goals_data = await self._get_goals_for_proactive_check(memory_kernel)
            
            # Only proceed if there are actionable goals
            if goals_data["actionable_goals"] == 0:
                print("ExecutiveKernel: No actionable goals available, skipping proactive check")
                # Update last interaction time to prevent immediate re-triggering
                self.last_interaction_time = datetime.datetime.now()
                return
            
            # Show thinking indicator only when we have goals to process
            await self._show_thinking_indicator(start_time)
            
            conversation_context = await self._get_conversation_context(memory_kernel)
            
            # Process with LLM to get proactive question
            proactive_question = await self._process_proactive_check_with_llm(
                goals_data, conversation_context
            )
            
            # Hide thinking indicator
            await self._hide_thinking_indicator()
            
            # Send proactive question to user
            if proactive_question:
                await self._send_proactive_question(proactive_question)
                
            # Update last interaction time to prevent immediate re-triggering
            self.last_interaction_time = datetime.datetime.now()
            
        except Exception as e:
            print(f"ExecutiveKernel: Error in proactive goal check: {e}")
            # Only try to hide thinking indicator if we showed it
            if self._thinking_shown:
                await self._hide_thinking_indicator()
        finally:
            self.is_processing_proactive = False
    
    async def _get_goals_for_proactive_check(self, memory_kernel) -> dict:
        """Retrieve goals from memory for proactive checking."""
        try:
            # Get all goals from memory
            all_goals = await memory_kernel.get_concepts_by_type.remote("goal")
            
            # Filter for active goals (those with some activation) and not already in progress
            active_goals = [goal for goal in all_goals if goal.get("activation", 0) > 0]
            actionable_goals = [goal for goal in active_goals if goal.get("data", {}).get("status", "unknown") not in ["in_progress", "completed"]]
            
            # Get person percepts for context
            person_percepts = await memory_kernel.get_concepts_by_type.remote("percept")
            current_percepts = [p for p in person_percepts if p.get("activation", 0) > 0]
            
            # Format goals for template
            goals_list = []
            for goal in actionable_goals:  # Only include actionable goals
                goal_info = {
                    "id": goal.get("id", ""),
                    "description": goal.get("data", {}).get("description", "No description"),
                    "status": goal.get("data", {}).get("status", "unknown"),
                    "activation": goal.get("activation", 0),
                    "created": goal.get("meta", {}).get("created", 0)
                }
                goals_list.append(goal_info)
            
            # Format person percepts info
            person_percepts_info = f"{len(current_percepts)} active person percepts detected"
            if current_percepts:
                percept_details = []
                for percept in current_percepts:
                    person_id = percept.get("data", {}).get("person_id", "unknown")
                    percept_details.append(f"person_{person_id}")
                person_percepts_info += f" ({', '.join(percept_details)})"
            
            return {
                "total_goals": len(all_goals),
                "active_goals": len(active_goals),
                "actionable_goals": len(actionable_goals),
                "goals_list": goals_list,
                "person_percepts_info": person_percepts_info
            }
            
        except Exception as e:
            print(f"ExecutiveKernel: Error retrieving goals: {e}")
            return {
                "total_goals": 0,
                "active_goals": 0,
                "actionable_goals": 0,
                "goals_list": [],
                "person_percepts_info": "No person percepts available"
            }
    
    async def _process_proactive_check_with_llm(self, goals_data: dict, conversation_context: str) -> Optional[str]:
        """Use LLM to process goals and generate proactive question."""
        try:
            # Check if local LLM service is available
            if not self.llm_service:
                print("ExecutiveKernel: Local LLM service not available for proactive check")
                return None
                
            # Format goals for template
            goals_list_str = ""
            for i, goal in enumerate(goals_data["goals_list"], 1):
                goals_list_str += f"{i}. {goal['description']} (Status: {goal['status']}, Activation: {goal['activation']:.2f})\n"
            
            if not goals_list_str:
                goals_list_str = "No actionable goals currently exist in the system."
            
            # Use template system to generate prompts
            template_result = llm_template.call(
                "proactive_goal_check",
                total_goals=goals_data["total_goals"],
                active_goals=goals_data["active_goals"],
                conversation_count=len(conversation_context.split('\n')) if conversation_context and conversation_context != "No previous conversation." else 0,
                person_percepts_info=goals_data["person_percepts_info"],
                goals_list=goals_list_str.strip(),
                conversation_context=conversation_context
            )
            
            system_prompt = template_result['system_prompt']
            user_message = template_result['user_message']
            
            llm_start = self._get_current_time()
            print(f"[{llm_start}] ExecutiveKernel: Starting proactive LLM processing")
            
            # Use the local LLM service to process the proactive check
            proactive_question = await self.llm_service.process_message(
                message=user_message,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=200,
                template_name="proactive_goal_check"
            )
            
            # Handle None response safely
            if proactive_question is None:
                proactive_question = ""
            
            llm_end = self._get_current_time()
            print(f"[{llm_start} -> {llm_end}] LLM: Generated proactive question: {proactive_question}")
            
            # Mark the most relevant goal as in_progress to prevent repetition
            await self._mark_goal_as_launched(goals_data["goals_list"])
            
            return proactive_question
            
        except Exception as e:
            print(f"ExecutiveKernel: Error in proactive LLM processing: {e}")
            return None
    
    async def _mark_goal_as_launched(self, goals_list: list) -> None:
        """Mark the most relevant goal as in_progress to prevent repetition."""
        if not goals_list:
            return
            
        try:
            # Find the most activated goal that isn't already in progress
            best_goal = None
            best_activation = 0
            
            for goal in goals_list:
                if goal.get("status") == "open" and goal.get("activation", 0) > best_activation:
                    best_goal = goal
                    best_activation = goal.get("activation", 0)
            
            if best_goal:
                # Update the goal status to in_progress
                memory_kernel = ray.get_actor("MemoryKernel")
                goal_id = best_goal.get("id")
                
                if goal_id:
                    # Update the goal concept's data to mark as in_progress
                    current_data = best_goal.get("data", {})
                    updated_data = {**current_data, "status": "in_progress"}
                    
                    await memory_kernel.update_concept.remote(
                        goal_id, 
                        {"data": updated_data}
                    )
                    
                    print(f"ExecutiveKernel: Marked goal '{best_goal['description']}' as in_progress")
                else:
                    print("ExecutiveKernel: Could not mark goal as launched - no goal ID available")
                    
        except Exception as e:
            print(f"ExecutiveKernel: Error marking goal as launched: {e}")
    
    async def _send_proactive_question(self, question: str) -> None:
        """Send proactive question to user as AI text bubble."""
        try:
            ai_bubble_command = TextBubbleCommand(text=question, is_user=False)
            ai_bubble_json = create_display_command_json(ai_bubble_command)
            
            ai_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=ai_bubble_json
            )
            
            await self.send_to_kernel(KernelID.MOTOR, ai_message)
            
            # Store the proactive question as an AI response in memory
            ai_conversation_message = ConversationMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                speaker="ai",
                content=question,
                store_in_memory=True
            )
            
            await self.send_to_kernel(KernelID.LEARNING, ai_conversation_message)
            
            response_time = self._get_current_time()
            print(f"[{response_time}] ExecutiveKernel: Sent proactive question to user")
            
        except Exception as e:
            print(f"ExecutiveKernel: Error sending proactive question: {e}")
    
    async def start(self) -> None:
        """Start the kernel's background message processing and proactive monitoring."""
        # Start the base kernel processing
        await super().start()
        
        # Start proactive monitoring
        await self.start_proactive_monitoring()
    
    async def stop(self) -> None:
        """Stop the kernel's background message processing and proactive monitoring."""
        # Stop proactive monitoring
        await self.stop_proactive_monitoring()
        
        # Stop the base kernel processing
        await super().stop()
    
    async def receive(self, message: KernelMessage) -> None:
        """Process executive decisions using LLM (non-blocking, real-time)."""
        try:
            # Update last interaction time
            self.last_interaction_time = datetime.datetime.now()
            
            # Executive kernel only processes TextMessage types
            if not isinstance(message, TextMessage):
                print(f"ExecutiveKernel: Unsupported message type: {type(message)}")
                return
            
            content = message.content
            start_time = self._get_current_time()
            print(f"[{start_time}] ExecutiveKernel: Processing '{content}'")
            
            # Get necessary actors  
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Process the user input through the pipeline
            await self._store_user_message(content, start_time)
            await self._show_user_text_bubble(content, start_time)
            await self._show_thinking_indicator(start_time)
            
            conversation_context = await self._get_conversation_context(memory_kernel)
            ai_response = await self._process_with_llm(content, conversation_context)
            
            await self._hide_thinking_indicator()
            
            # Only send response if we have content
            if ai_response:
                await self._store_ai_response(ai_response)
                await self._show_ai_response_bubble(ai_response)
            else:
                print("ExecutiveKernel: No response to send, skipping AI response bubble")
            
        except ValueError as e:
            print(f"ExecutiveKernel: Error - Required kernel not found: {str(e)}")
            
        except Exception as e:
            print(f"ExecutiveKernel: Error: {str(e)}")
            await self._handle_error(e)
    
    def _get_current_time(self) -> str:
        """Get current time formatted as HH:MM:SS.mmm"""
        return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    async def _store_user_message(self, content: str, start_time: str) -> None:
        """Store user input in conversation memory (non-blocking)."""
        user_conversation_message = ConversationMessage(
            source_kernel_id=KernelID.EXECUTIVE,
            speaker="user",
            content=content,
            store_in_memory=True
        )
        
        await self.send_to_kernel(KernelID.LEARNING, user_conversation_message)
        print(f"[{start_time}] ExecutiveKernel -> LearningKernel (user conversation, non-blocking)")
    
    async def _show_user_text_bubble(self, content: str, start_time: str) -> None:
        """Send command to show user text bubble (non-blocking, immediate)."""
        user_bubble_command = TextBubbleCommand(text=content, is_user=True)
        user_bubble_json = create_display_command_json(user_bubble_command)
        
        user_bubble_message = TextMessage(
            source_kernel_id=KernelID.EXECUTIVE,
            content=user_bubble_json
        )
        
        await self.send_to_kernel(KernelID.MOTOR, user_bubble_message)
        bubble_time = self._get_current_time()
        print(f"[{start_time} -> {bubble_time}] ExecutiveKernel -> MotorKernel (user bubble, non-blocking)")
    
    async def _show_thinking_indicator(self, start_time: str) -> None:
        """Show thinking indicator (non-blocking, immediate)."""
        thinking_command = ShowThinkingCommand()
        thinking_json = create_display_command_json(thinking_command)
        
        thinking_message = TextMessage(
            source_kernel_id=KernelID.EXECUTIVE,
            content=thinking_json
        )
        
        await self.send_to_kernel(KernelID.MOTOR, thinking_message)
        self._thinking_shown = True
        thinking_time = self._get_current_time()
        print(f"[{start_time} -> {thinking_time}] ExecutiveKernel -> MotorKernel (thinking, non-blocking)")
    
    async def _get_conversation_context(self, memory_kernel) -> str:
        """Get conversation history from memory and build context."""
        conversation_history = await memory_kernel.get_conversation_history.remote(limit=10)
        print(f"ExecutiveKernel: Retrieved {len(conversation_history)} conversation messages")
        
        context_messages = []
        for msg in conversation_history[:-1]:  # Exclude the current message we just stored
            speaker = msg["speaker"]
            msg_content = msg["content"]
            context_messages.append(f"{speaker}: {msg_content}")
        
        return "\n".join(context_messages) if context_messages else "No previous conversation."
    
    async def _process_with_llm(self, content: str, conversation_context: str) -> str:
        """Use LLM to process with conversation context, goals, and tools."""
        try:
            # Check if local LLM service is available
            if not self.llm_service:
                print("ExecutiveKernel: Local LLM service not available, falling back to basic response")
                return "I'm sorry, but I can't process your message right now due to a configuration issue."
            
            # Get current goals and person context
            memory_kernel = ray.get_actor("MemoryKernel")
            goals_data = await self._get_goals_for_conversation_context(memory_kernel)
            person_context = await self._get_person_context(memory_kernel)
            
            # Use template system to generate prompts with full context
            template_result = llm_template.call(
                "executive_decision",
                conversation_context=conversation_context,
                current_input=content,
                current_goals=goals_data,
                person_context=person_context
            )
            
            system_prompt = template_result['system_prompt']
            user_message = template_result['user_message']
            
            llm_start = self._get_current_time()
            print(f"[{llm_start}] ExecutiveKernel: Starting LLM processing with tools")
            
            # Use the local LLM service with tools
            response = await self.llm_service.process_message_with_tools(
                message=user_message,
                system_prompt=system_prompt,
                tools=self.available_tools,
                temperature=0.7,
                max_tokens=500,
                max_tool_calls=3,
                template_name="executive_decision"
            )
            
            llm_end = self._get_current_time()
            # Handle None response content safely
            ai_response = (response.get('content') or '').strip()
            print(f"[{llm_start} -> {llm_end}] LLM: Generated response with {len(response.get('tool_calls', []))} tool calls")
            
            # Execute any tool calls
            tool_executed = False
            if response.get('tool_calls'):
                print(f"ExecutiveKernel: Executing {len(response['tool_calls'])} tool calls")
                tool_results = await self.llm_service.execute_tools(response['tool_calls'], self.available_tools)
                
                # Log tool execution results and check for successful non-respond_only tools
                for result in tool_results:
                    if result['success']:
                        print(f"ExecutiveKernel: Tool {result['function']} executed successfully: {result['result']}")
                        if result['function'] != 'respond_only':
                            tool_executed = True
                    else:
                        print(f"ExecutiveKernel: Tool {result['function']} failed: {result['result']}")
            
            # Handle empty responses
            if not ai_response or ai_response.lower() in ['none', 'null', '']:
                if tool_executed:
                    # If tools were executed but no response, provide a friendly default
                    ai_response = "Got it! I've updated my understanding accordingly."
                    print("ExecutiveKernel: Provided default response for tool execution without text")
                else:
                    # If no tools and no response, return None to skip sending message
                    print("ExecutiveKernel: Empty response with no tools executed, skipping message")
                    return None
            
            return ai_response
            
        except Exception as e:
            print(f"ExecutiveKernel: Error in LLM processing: {e}")
            # Always return a response for errors
            return f"I encountered an error processing your message: {str(e)}"
    
    async def _get_goals_for_conversation_context(self, memory_kernel) -> str:
        """Get current goals formatted for conversation context."""
        try:
            all_goals = await memory_kernel.get_concepts_by_type.remote("goal")
            
            if not all_goals:
                return "No current learning goals."
            
            # Filter for open and in_progress goals (not completed)
            active_goals = [goal for goal in all_goals if goal.get("data", {}).get("status") in ["open", "in_progress"]]
            
            if not active_goals:
                return "No active learning goals."
            
            # Format goals for context in natural language
            goals_list = []
            for goal in active_goals:
                goal_info = goal.get("data", {})
                description = goal_info.get("description", "No description")
                status = goal_info.get("status", "unknown")
                goal_id = goal.get("id", "unknown")
                
                # Format goal description naturally
                if status == "open":
                    goals_list.append(f"- {description} (ready to work on)")
                elif status == "in_progress":
                    goals_list.append(f"- {description} (currently working on this)")
                else:
                    goals_list.append(f"- {description} ({status})")
            
            return "Current learning goals:\n" + "\n".join(goals_list)
            
        except Exception as e:
            print(f"ExecutiveKernel: Error getting goals for context: {e}")
            return "Error retrieving learning goals."
    
    async def _get_person_context(self, memory_kernel) -> str:
        """Get person context information for currently active people only."""
        try:
            # Get active person percepts
            person_percepts = await memory_kernel.get_concepts_by_type.remote("percept")
            active_percepts = [p for p in person_percepts if p.get("activation", 0) > 0]
            
            context_parts = []
            
            if active_percepts:
                # Format person presence naturally
                if len(active_percepts) == 1:
                    person_id = active_percepts[0].get("data", {}).get("person_id", "unknown")
                    context_parts.append(f"Currently interacting with person {person_id}")
                else:
                    person_ids = [p.get("data", {}).get("person_id", "unknown") for p in active_percepts]
                    context_parts.append(f"Currently perceiving {len(active_percepts)} people: {', '.join(person_ids)}")
                
                # Get knowledge concepts linked to currently active person percepts
                knowledge_concepts = await memory_kernel.get_concepts_by_type.remote("knowledge")
                active_percept_ids = {p.get("id") for p in active_percepts}
                
                # Filter for knowledge linked to currently active people and that is active
                relevant_knowledge = []
                for knowledge in knowledge_concepts:
                    knowledge_data = knowledge.get("data", {})
                    activation = knowledge.get("activation", 0)
                    linked_percept = knowledge_data.get("linked_person_percept")
                    
                    # Include knowledge that is active and linked to current person(s)
                    if activation > 0 and linked_percept in active_percept_ids:
                        relevant_knowledge.append(knowledge)
                
                if relevant_knowledge:
                    # Sort by creation time (newest first) and take top 5
                    relevant_knowledge.sort(key=lambda k: k.get("meta", {}).get("created", 0), reverse=True)
                    recent_knowledge = relevant_knowledge[:5]
                    
                    # Format knowledge naturally
                    knowledge_items = []
                    for knowledge in recent_knowledge:
                        knowledge_type = knowledge.get("data", {}).get("knowledge_type", "unknown")
                        description = knowledge.get("data", {}).get("description", "")
                        
                        if knowledge_type == "personal_info":
                            knowledge_items.append(f"Personal: {description}")
                        elif knowledge_type == "preference":
                            knowledge_items.append(f"Preference: {description}")
                        elif knowledge_type == "fact":
                            knowledge_items.append(f"Fact: {description}")
                        else:
                            knowledge_items.append(f"{knowledge_type}: {description}")
                    
                    context_parts.append("What I know:\n" + "\n".join(knowledge_items))
            
            return "\n\n".join(context_parts) if context_parts else "No person context available."
            
        except Exception as e:
            print(f"ExecutiveKernel: Error getting person context: {e}")
            return "Error retrieving person context."
    
    async def _store_ai_response(self, ai_response: str) -> None:
        """Store AI response in conversation memory (non-blocking)."""
        ai_conversation_message = ConversationMessage(
            source_kernel_id=KernelID.EXECUTIVE,
            speaker="ai",
            content=ai_response,
            store_in_memory=True
        )
        
        await self.send_to_kernel(KernelID.LEARNING, ai_conversation_message)
        print(f"ExecutiveKernel -> LearningKernel (AI conversation, non-blocking)")
    
    async def _hide_thinking_indicator(self) -> None:
        """Hide thinking indicator (non-blocking, immediate)."""
        hide_thinking_command = HideThinkingCommand()
        hide_thinking_json = create_display_command_json(hide_thinking_command)
        
        hide_thinking_message = TextMessage(
            source_kernel_id=KernelID.EXECUTIVE,
            content=hide_thinking_json
        )
        
        await self.send_to_kernel(KernelID.MOTOR, hide_thinking_message)
        self._thinking_shown = False
        hide_time = self._get_current_time()
        print(f"ExecutiveKernel -> MotorKernel (hide thinking, non-blocking)")
    
    async def _show_ai_response_bubble(self, ai_response: str) -> None:
        """Send command to show AI response bubble (non-blocking, immediate)."""
        ai_bubble_command = TextBubbleCommand(text=ai_response, is_user=False)
        ai_bubble_json = create_display_command_json(ai_bubble_command)
        
        ai_message = TextMessage(
            source_kernel_id=KernelID.EXECUTIVE,
            content=ai_bubble_json
        )
        
        await self.send_to_kernel(KernelID.MOTOR, ai_message)
        response_time = self._get_current_time()
        print(f"ExecutiveKernel -> MotorKernel (AI response, non-blocking)")
    
    async def _handle_error(self, error: Exception) -> None:
        """Handle errors by sending error message as text bubble (non-blocking)."""
        try:
            error_bubble_command = TextBubbleCommand(text=f"Error: {str(error)}", is_user=False)
            error_bubble_json = create_display_command_json(error_bubble_command)
            
            error_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=error_bubble_json
            )
            
            await self.send_to_kernel(KernelID.MOTOR, error_message)
            print("ExecutiveKernel -> MotorKernel (error, non-blocking)")
        except Exception as inner_e:
            print(f"ExecutiveKernel: Failed to send error message: {inner_e}") 