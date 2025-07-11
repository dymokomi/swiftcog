"""
Motor kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage
from .base_kernel import BaseKernel


@ray.remote
class MotorKernel(BaseKernel):
    """Motor kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.MOTOR, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Default handler that processes motor commands and forwards directly to Expression."""
        if isinstance(message, TextMessage):
            content = message.content
        else:
            print(f"MotorKernel: Unsupported message type: {type(message)}")
            return
            
        print(f"MotorKernel: Processing {content}")
        
        # Hardcoded connection: Motor -> Expression
        try:
            expression_kernel = ray.get_actor("ExpressionKernel")
            await expression_kernel.receive.remote(message)
            print("MotorKernel -> ExpressionKernel")
        except ValueError:
            print("Error: ExpressionKernel not found") 