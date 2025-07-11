"""
Executive kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage, VoiceMessage, TextBubbleCommand, ShowThinkingCommand, HideThinkingCommand, create_display_command_json
from .base_kernel import BaseKernel


@ray.remote
class ExecutiveKernel(BaseKernel):
    """Executive kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.EXECUTIVE, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Default handler that makes executive decisions using LLM."""
        try:
            # Extract content from different message types
            if isinstance(message, TextMessage):
                content = message.content
            elif isinstance(message, VoiceMessage):
                content = message.transcription
            else:
                print(f"ExecutiveKernel: Unsupported message type: {type(message)}")
                return
            
            # Get the kernel system actor for LLM service
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            llm_service = await kernel_system_actor.get_shared_llm_service.remote()
            if not llm_service:
                raise RuntimeError("Shared LLM service not initialized")
            
            # Get motor kernel for display output
            motor_kernel = ray.get_actor("MotorKernel")
            
            # Step 1: Send command to show user text bubble
            user_bubble_command = TextBubbleCommand(text=content, is_user=True)
            user_bubble_json = create_display_command_json(user_bubble_command)
            
            user_bubble_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=user_bubble_json
            )
            
            # Hardcoded connection: Executive -> Motor (for display)
            await motor_kernel.receive.remote(user_bubble_message)
            print("ExecutiveKernel -> MotorKernel (user bubble)")
            
            # Step 2: Show thinking indicator
            thinking_command = ShowThinkingCommand()
            thinking_json = create_display_command_json(thinking_command)
            
            thinking_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=thinking_json
            )
            
            await motor_kernel.receive.remote(thinking_message)
            print("ExecutiveKernel -> MotorKernel (thinking)")
            
            # Step 3: Use LLM to process the message
            system_prompt = """You are an executive decision-making system in a cognitive architecture. 
Your role is to analyze input from sensing and memory, then provide intelligent decisions or responses.
Be very concise and provide direct answers to questions."""
            
            print(f"ExecutiveKernel: Processing with LLM: {content}")
            
            # Use the shared LLM service to process the message
            ai_response = await llm_service.process_message.remote(
                content,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            print(f"LLM: Generated response: {ai_response}")
            
            # Step 4: Hide thinking indicator
            hide_thinking_command = HideThinkingCommand()
            hide_thinking_json = create_display_command_json(hide_thinking_command)
            
            hide_thinking_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=hide_thinking_json
            )
            
            await motor_kernel.receive.remote(hide_thinking_message)
            print("ExecutiveKernel -> MotorKernel (hide thinking)")
            
            # Step 5: Send command to show AI response bubble
            ai_bubble_command = TextBubbleCommand(text=ai_response, is_user=False)
            ai_bubble_json = create_display_command_json(ai_bubble_command)
            
            ai_message = TextMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                content=ai_bubble_json
            )
            
            await motor_kernel.receive.remote(ai_message)
            print("ExecutiveKernel -> MotorKernel (AI response)")
            
            # Step 6: Send to Learning kernel for learning
            # Hardcoded connection: Executive -> Learning
            try:
                learning_kernel = ray.get_actor("LearningKernel")
                learning_message = TextMessage(
                    source_kernel_id=KernelID.EXECUTIVE,
                    content=f"Learn from: {content} -> {ai_response}"
                )
                await learning_kernel.receive.remote(learning_message)
                print("ExecutiveKernel -> LearningKernel")
            except ValueError:
                print("Error: LearningKernel not found")
            
        except Exception as e:
            print(f"Error in ExecutiveKernel: {str(e)}")
            
            # If anything fails, send error as text bubble
            try:
                error_bubble_command = TextBubbleCommand(text=f"Error: {str(e)}", is_user=False)
                error_bubble_json = create_display_command_json(error_bubble_command)
                
                error_message = TextMessage(
                    source_kernel_id=KernelID.EXECUTIVE,
                    content=error_bubble_json
                )
                
                motor_kernel = ray.get_actor("MotorKernel")
                await motor_kernel.receive.remote(error_message)
                print("ExecutiveKernel -> MotorKernel (error)")
            except Exception as inner_e:
                print(f"Error: Failed to send error message: {inner_e}") 