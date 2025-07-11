"""
Learning kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage


@ray.remote
class LearningKernel:
    """Learning kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        self.custom_handler = custom_handler
        self.kernel_id = KernelID.LEARNING
    
    def get_kernel_id(self) -> KernelID:
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        if self.custom_handler:
            await self.custom_handler(message, self)
        else:
            await self.default_handler(message)
    
    async def default_handler(self, message: KernelMessage) -> None:
        """Default handler that processes learning and adaptation."""
        print(f"Backend LearningKernel: Learning from {message.payload}")
        # Note: Default handlers don't emit - custom handlers handle system communication 