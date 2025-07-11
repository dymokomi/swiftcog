"""
Expression kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage
from .base_kernel import BaseKernel


@ray.remote
class ExpressionKernel(BaseKernel):
    """Expression kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.EXPRESSION, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Default handler that sends messages directly to GUI."""
        if isinstance(message, TextMessage):
            content = message.content
        else:
            print(f"ExpressionKernel: Unsupported message type: {type(message)}")
            return
            
        print(f"ExpressionKernel: {content}")
        
        # Hardcoded connection: Expression -> GUI (via system)
        try:
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            # Queue message for frontend delivery
            await kernel_system_actor.queue_frontend_message.remote(message)
            print("ExpressionKernel -> GUI")
        except ValueError:
            print("Error: KernelSystemActor not found") 