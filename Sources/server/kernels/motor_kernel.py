"""
Motor kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage


@ray.remote
class MotorKernel:
    """Motor kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        self.custom_handler = custom_handler
        self.kernel_id = KernelID.MOTOR
    
    def get_kernel_id(self) -> KernelID:
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        if self.custom_handler:
            await self.custom_handler(message, self)
        else:
            await self.default_handler(message)
    
    async def default_handler(self, message: KernelMessage) -> None:
        """Default handler that processes motor commands and forwards directly to Expression."""
        print(f"MotorKernel: Processing {message.payload}")
        
        # Hardcoded connection: Motor -> Expression
        try:
            expression_kernel = ray.get_actor("ExpressionKernel")
            await expression_kernel.receive.remote(message)
            print("MotorKernel -> ExpressionKernel")
        except ValueError:
            print("Error: ExpressionKernel not found") 