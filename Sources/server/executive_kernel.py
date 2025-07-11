"""
Executive kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextBubbleCommand, ShowThinkingCommand, HideThinkingCommand, create_display_command_json


@ray.remote
class ExecutiveKernel:
    """Executive kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        self.custom_handler = custom_handler
        self.kernel_id = KernelID.EXECUTIVE
    
    def get_kernel_id(self) -> KernelID:
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        if self.custom_handler:
            await self.custom_handler(message, self)
        else:
            await self.default_handler(message)
    
    async def default_handler(self, message: KernelMessage) -> None:
        """Default handler that makes executive decisions using LLM."""
        try:
            # Get the kernel system actor for LLM service
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            llm_service = await kernel_system_actor.get_shared_llm_service.remote()
            if not llm_service:
                raise RuntimeError("Shared LLM service not initialized")
            
            # Get motor kernel for display output
            motor_kernel = ray.get_actor("MotorKernel")
            
            # Step 1: Send command to show user text bubble
            user_bubble_command = TextBubbleCommand(text=message.payload, is_user=True)
            user_bubble_json = create_display_command_json(user_bubble_command)
            
            user_bubble_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=user_bubble_json
            )
            
            # Hardcoded connection: Executive -> Motor (for display)
            await motor_kernel.receive.remote(user_bubble_message)
            print("ExecutiveKernel -> MotorKernel (user bubble)")
            
            # Step 2: Show thinking indicator
            thinking_command = ShowThinkingCommand()
            thinking_json = create_display_command_json(thinking_command)
            
            thinking_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=thinking_json
            )
            
            await motor_kernel.receive.remote(thinking_message)
            print("ExecutiveKernel -> MotorKernel (thinking)")
            
            # Step 3: Use LLM to process the message
            system_prompt = """You are an executive decision-making system in a cognitive architecture. 
Your role is to analyze input from sensing and memory, then provide intelligent decisions or responses.
Be very concise and provide direct answers to questions."""
            
            print(f"ExecutiveKernel: Processing with LLM: {message.payload}")
            
            # Use the shared LLM service to process the message
            ai_response = await llm_service.process_message.remote(
                message.payload,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            print(f"LLM: Generated response: {ai_response}")
            
            # Step 4: Hide thinking indicator
            hide_thinking_command = HideThinkingCommand()
            hide_thinking_json = create_display_command_json(hide_thinking_command)
            
            hide_thinking_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=hide_thinking_json
            )
            
            await motor_kernel.receive.remote(hide_thinking_message)
            print("ExecutiveKernel -> MotorKernel (hide thinking)")
            
            # Step 5: Send command to show AI response bubble
            ai_bubble_command = TextBubbleCommand(text=ai_response, is_user=False)
            ai_bubble_json = create_display_command_json(ai_bubble_command)
            
            ai_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=ai_bubble_json
            )
            
            await motor_kernel.receive.remote(ai_message)
            print("ExecutiveKernel -> MotorKernel (AI response)")
            
            # Step 6: Send to Learning kernel for learning
            # Hardcoded connection: Executive -> Learning
            try:
                learning_kernel = ray.get_actor("LearningKernel")
                learning_message = KernelMessage(
                    source_kernel_id=KernelID.EXECUTIVE,
                    payload=f"Learn from: {message.payload} -> {ai_response}"
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
                
                error_message = KernelMessage(
                    source_kernel_id=KernelID.EXECUTIVE,
                    payload=error_bubble_json
                )
                
                motor_kernel = ray.get_actor("MotorKernel")
                await motor_kernel.receive.remote(error_message)
                print("ExecutiveKernel -> MotorKernel (error)")
            except Exception as inner_e:
                print(f"Error: Failed to send error message: {inner_e}") 