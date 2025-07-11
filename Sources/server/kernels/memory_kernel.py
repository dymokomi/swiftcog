"""
Memory kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage


@ray.remote
class MemoryKernel:
    """Memory kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        self.custom_handler = custom_handler
        self.kernel_id = KernelID.MEMORY
    
    def get_kernel_id(self) -> KernelID:
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        if self.custom_handler:
            await self.custom_handler(message, self)
        else:
            await self.default_handler(message)
    
    async def default_handler(self, message: KernelMessage) -> None:
        """Default handler that processes and stores memory-related information."""
        print(f"MemoryKernel: Storing memory: {message.payload}")
        
        # Store the information in memory (for now just log it)
        # In a real implementation, this would store to a database or memory system
        # For now, we just acknowledge receipt and don't forward anywhere
        print(f"Stored in memory: {message.payload}") 