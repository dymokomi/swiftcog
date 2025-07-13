"""
Executive kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
import datetime
import asyncio
from swiftcog_types import KernelID, KernelMessage, TextMessage, TextBubbleCommand, ShowThinkingCommand, HideThinkingCommand, create_display_command_json, ConversationMessage, GoalCreationRequest
from .base_kernel import BaseKernel
from llm_template import llm_template


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
            
            # Get necessary services
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            llm_service = await kernel_system_actor.get_shared_llm_service.remote()
            if not llm_service:
                print("ExecutiveKernel: Shared LLM service not available for proactive check")
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
                goals_data, conversation_context, llm_service
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
    
    async def _process_proactive_check_with_llm(self, goals_data: dict, conversation_context: str, llm_service) -> Optional[str]:
        """Use LLM to process goals and generate proactive question."""
        try:
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
            
            # Use the shared LLM service to process the proactive check
            proactive_question = await llm_service.process_message.remote(
                user_message,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=200
            )
            
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
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            llm_service = await kernel_system_actor.get_shared_llm_service.remote()
            if not llm_service:
                raise RuntimeError("Shared LLM service not initialized")
            
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Process the user input through the pipeline
            await self._store_user_message(content, start_time)
            await self._show_user_text_bubble(content, start_time)
            await self._show_thinking_indicator(start_time)
            
            conversation_context = await self._get_conversation_context(memory_kernel)
            ai_response = await self._process_with_llm(content, conversation_context, llm_service)
            
            await self._store_ai_response(ai_response)
            await self._hide_thinking_indicator()
            await self._show_ai_response_bubble(ai_response)
            
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
    
    async def _process_with_llm(self, content: str, conversation_context: str, llm_service) -> str:
        """Use LLM to process with conversation context."""
        # Use template system to generate prompts
        template_result = llm_template.call(
            "executive_decision",
            conversation_context=conversation_context,
            current_input=content
        )
        
        system_prompt = template_result['system_prompt']
        user_message = template_result['user_message']
        
        llm_start = self._get_current_time()
        print(f"[{llm_start}] ExecutiveKernel: Starting LLM processing")
        
        # Use the shared LLM service to process the message
        ai_response = await llm_service.process_message.remote(
            user_message,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=500
        )
        
        llm_end = self._get_current_time()
        print(f"[{llm_start} -> {llm_end}] LLM: Generated response: {ai_response}")
        
        return ai_response
    
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