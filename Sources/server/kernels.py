"""
Shared kernel components and handler implementations for the SwiftCog Python server.
"""
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional, TYPE_CHECKING, Any
import ray
from swiftcog_types import KernelID, KernelMessage, TextBubbleCommand, ShowThinkingCommand, HideThinkingCommand, create_display_command_json
from llm_service import LLMService, OpenAIProvider

if TYPE_CHECKING:
    from kernel_system import KernelSystem


@ray.remote
class SharedLLMService:
    """Shared LLM service as a Ray actor for use across all kernels."""
    
    def __init__(self, api_key: str):
        openai_provider = OpenAIProvider(api_key)
        self.llm_service = LLMService(openai_provider)
    
    async def process_message(self, message: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 500):
        """Process a message using the LLM service."""
        return await self.llm_service.process_message(
            message=message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )


class Kernel(ABC):
    """Abstract base class for all kernels."""
    
    @abstractmethod
    def get_kernel_id(self) -> KernelID:
        """Get the kernel ID."""
        pass
    
    @abstractmethod
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        pass


# Custom handler implementations for kernel customization
async def create_sensing_handler(system: 'KernelSystem'):
    """Create a sensing kernel handler that passes through messages."""
    async def handler(message: KernelMessage, kernel):
        # Just pass through the original message without modification
        await system.emit_from_actor(message, KernelID.SENSING)
    return handler


async def create_expression_handler(system: 'KernelSystem'):
    """Create an expression kernel handler that sends back to frontend."""
    async def handler(message: KernelMessage, kernel):
        print(f"Backend ExpressionKernel: {message.payload}")
        # Send the display command to frontend
        await system.emit_from_actor(message, KernelID.EXPRESSION)
    return handler


async def create_motor_handler(system: 'KernelSystem'):
    """Create a motor kernel handler."""
    async def handler(message: KernelMessage, kernel):
        print(f"Backend MotorKernel: Processing {message.payload}")
        await system.emit_from_actor(message, KernelID.MOTOR)
    return handler


async def create_executive_handler(system: 'KernelSystem', source_code: str = None, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 500):
    """Create an executive kernel handler with optional source code evaluation."""
    async def handler(message: KernelMessage, kernel):
        try:
            # Get shared LLM service
            llm_service = system.get_shared_llm_service()
            if not llm_service:
                raise RuntimeError("Shared LLM service not initialized")
            
            # Step 1: Send command to show user text bubble
            user_bubble_command = TextBubbleCommand(text=message.payload, is_user=True)
            user_bubble_json = create_display_command_json(user_bubble_command)
            
            user_bubble_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=user_bubble_json
            )
            await system.emit_from_actor(user_bubble_message, KernelID.EXECUTIVE)
            
            # Step 2: Show thinking indicator
            thinking_command = ShowThinkingCommand()
            thinking_json = create_display_command_json(thinking_command)
            
            thinking_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=thinking_json
            )
            await system.emit_from_actor(thinking_message, KernelID.EXECUTIVE)
            
            # Step 3: Execute custom source code if provided
            custom_response = None
            if source_code:
                try:
                    # Create a safe execution environment
                    exec_globals = {
                        'message': message,
                        'system': system,
                        'kernel': kernel,
                        'llm_service': llm_service,
                        'KernelMessage': KernelMessage,
                        'KernelID': KernelID,
                        'TextBubbleCommand': TextBubbleCommand,
                        'ShowThinkingCommand': ShowThinkingCommand,
                        'HideThinkingCommand': HideThinkingCommand,
                        'create_display_command_json': create_display_command_json,
                        'print': print,
                        '__builtins__': __builtins__
                    }
                    exec_locals = {}
                    
                    # Execute the custom code
                    exec(source_code, exec_globals, exec_locals)
                    
                    # Check if custom code provided a response
                    if 'custom_response' in exec_locals:
                        custom_response = exec_locals['custom_response']
                    
                except Exception as e:
                    print(f"Error executing custom source code: {e}")
                    # Continue with default behavior if custom code fails
            
            # Step 4: Use LLM if no custom response or as fallback
            if custom_response is None:
                # Use provided system prompt or default
                default_prompt = """You are an executive decision-making system in a cognitive architecture. 
Your role is to analyze input and provide intelligent decisions or responses.
Be very concise. Just provide direct answer to the question."""
                
                prompt = system_prompt or default_prompt
                
                # Use the shared LLM service to process the message
                ai_response = await llm_service.process_message.remote(
                    message.payload,
                    system_prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                ai_response = custom_response
            
            # Step 5: Hide thinking indicator
            hide_thinking_command = HideThinkingCommand()
            hide_thinking_json = create_display_command_json(hide_thinking_command)
            
            hide_thinking_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=hide_thinking_json
            )
            await system.emit_from_actor(hide_thinking_message, KernelID.EXECUTIVE)
            
            # Step 6: Send command to show AI response bubble
            ai_bubble_command = TextBubbleCommand(text=ai_response, is_user=False)
            ai_bubble_json = create_display_command_json(ai_bubble_command)
            
            ai_message = KernelMessage(
                source_kernel_id=KernelID.EXECUTIVE,
                payload=ai_bubble_json
            )
            await system.emit_from_actor(ai_message, KernelID.EXECUTIVE)
            
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
                await system.emit_from_actor(error_message, KernelID.EXECUTIVE)
            except Exception as inner_e:
                print(f"Failed to send error message: {inner_e}")
    
    return handler 