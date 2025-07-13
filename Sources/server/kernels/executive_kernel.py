"""
Executive kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
import datetime
from swiftcog_types import KernelID, KernelMessage, TextMessage, TextBubbleCommand, ShowThinkingCommand, HideThinkingCommand, create_display_command_json, ConversationMessage
from .base_kernel import BaseKernel


@ray.remote
class ExecutiveKernel(BaseKernel):
    """Executive kernel implementation with non-blocking message routing."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.EXECUTIVE, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Process executive decisions using LLM (non-blocking, real-time)."""
        try:
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
        system_prompt = f"""You are an executive decision-making system in a cognitive architecture. 
Your role is to analyze input from sensing and memory, then provide intelligent decisions or responses.
Be very concise and provide direct answers to questions.

Previous conversation context:
{conversation_context}

Current user input: {content}

Respond naturally as if continuing the conversation."""
        
        llm_start = self._get_current_time()
        print(f"[{llm_start}] ExecutiveKernel: Starting LLM processing")
        
        # Use the shared LLM service to process the message
        ai_response = await llm_service.process_message.remote(
            content,
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