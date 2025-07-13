"""
Executive kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage, VoiceMessage, TextBubbleCommand, ShowThinkingCommand, HideThinkingCommand, create_display_command_json, ConversationMessage
from .base_kernel import BaseKernel


@ray.remote
class ExecutiveKernel(BaseKernel):
    """Executive kernel implementation with non-blocking message routing."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.EXECUTIVE, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Process executive decisions using LLM (non-blocking, real-time)."""
        try:
            # Extract content from different message types
            if isinstance(message, TextMessage):
                content = message.content
            elif isinstance(message, VoiceMessage):
                content = message.transcription
            else:
                print(f"ExecutiveKernel: Unsupported message type: {type(message)}")
                return
            
            import datetime
            start_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{start_time}] ExecutiveKernel: Processing '{content}'")
            
            # Get necessary actors
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            llm_service = await kernel_system_actor.get_shared_llm_service.remote()
            if not llm_service:
                raise RuntimeError("Shared LLM service not initialized")
            
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Step 1: Store user input in conversation memory (non-blocking)
            user_conversation_message = ConversationMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                speaker="user",
                content=content,
                store_in_memory=True
            )
            
            await self.send_to_kernel(KernelID.LEARNING, user_conversation_message)
            print(f"[{start_time}] ExecutiveKernel -> LearningKernel (user conversation, non-blocking)")
            
            # Step 2: Send command to show user text bubble (non-blocking, immediate)
            user_bubble_command = TextBubbleCommand(text=content, is_user=True)
            user_bubble_json = create_display_command_json(user_bubble_command)
            
            user_bubble_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=user_bubble_json
            )
            
            await self.send_to_kernel(KernelID.MOTOR, user_bubble_message)
            bubble_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{start_time} -> {bubble_time}] ExecutiveKernel -> MotorKernel (user bubble, non-blocking)")
            
            # Step 3: Show thinking indicator (non-blocking, immediate)
            thinking_command = ShowThinkingCommand()
            thinking_json = create_display_command_json(thinking_command)
            
            thinking_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=thinking_json
            )
            
            await self.send_to_kernel(KernelID.MOTOR, thinking_message)
            thinking_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{start_time} -> {thinking_time}] ExecutiveKernel -> MotorKernel (thinking, non-blocking)")
            
            # Step 4: Get conversation history from memory
            conversation_history = await memory_kernel.get_conversation_history.remote(limit=10)
            print(f"ExecutiveKernel: Retrieved {len(conversation_history)} conversation messages")
            
            # Step 5: Build context for LLM
            context_messages = []
            for msg in conversation_history[:-1]:  # Exclude the current message we just stored
                speaker = msg["speaker"]
                msg_content = msg["content"]
                context_messages.append(f"{speaker}: {msg_content}")
            
            conversation_context = "\n".join(context_messages) if context_messages else "No previous conversation."
            
            # Step 6: Use LLM to process with conversation context
            system_prompt = f"""You are an executive decision-making system in a cognitive architecture. 
Your role is to analyze input from sensing and memory, then provide intelligent decisions or responses.
Be very concise and provide direct answers to questions.

Previous conversation context:
{conversation_context}

Current user input: {content}

Respond naturally as if continuing the conversation."""
            
            llm_start = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{llm_start}] ExecutiveKernel: Starting LLM processing")
            
            # Use the shared LLM service to process the message
            ai_response = await llm_service.process_message.remote(
                content,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            llm_end = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{llm_start} -> {llm_end}] LLM: Generated response: {ai_response}")
            
            # Step 7: Store AI response in conversation memory (non-blocking)
            ai_conversation_message = ConversationMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                speaker="ai",
                content=ai_response,
                store_in_memory=True
            )
            
            await self.send_to_kernel(KernelID.LEARNING, ai_conversation_message)
            print(f"[{llm_end}] ExecutiveKernel -> LearningKernel (AI conversation, non-blocking)")
            
            # Step 8: Hide thinking indicator (non-blocking, immediate)
            hide_thinking_command = HideThinkingCommand()
            hide_thinking_json = create_display_command_json(hide_thinking_command)
            
            hide_thinking_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=hide_thinking_json
            )
            
            await self.send_to_kernel(KernelID.MOTOR, hide_thinking_message)
            hide_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{llm_end} -> {hide_time}] ExecutiveKernel -> MotorKernel (hide thinking, non-blocking)")
            
            # Step 9: Send command to show AI response bubble (non-blocking, immediate)
            ai_bubble_command = TextBubbleCommand(text=ai_response, is_user=False)
            ai_bubble_json = create_display_command_json(ai_bubble_command)
            
            ai_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=ai_bubble_json
            )
            
            await self.send_to_kernel(KernelID.MOTOR, ai_message)
            response_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{llm_end} -> {response_time}] ExecutiveKernel -> MotorKernel (AI response, non-blocking)")
            
        except ValueError as e:
            print(f"ExecutiveKernel: Error - Required kernel not found: {str(e)}")
            
        except Exception as e:
            print(f"ExecutiveKernel: Error: {str(e)}")
            
            # If anything fails, send error as text bubble (non-blocking)
            try:
                error_bubble_command = TextBubbleCommand(text=f"Error: {str(e)}", is_user=False)
                error_bubble_json = create_display_command_json(error_bubble_command)
                
                error_message = TextMessage(
                    source_kernel_id=KernelID.EXECUTIVE,
                    content=error_bubble_json
                )
                
                await self.send_to_kernel(KernelID.MOTOR, error_message)
                print("ExecutiveKernel -> MotorKernel (error, non-blocking)")
            except Exception as inner_e:
                print(f"ExecutiveKernel: Failed to send error message: {inner_e}") 