"""
Learning kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage


@ray.remote
class LearningKernel:
    """Learning kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        self.custom_handler = custom_handler
        self.kernel_id = KernelID.LEARNING
    
    def get_kernel_id(self) -> KernelID:
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Default handler that processes learning and forwards directly to Memory."""
        if isinstance(message, TextMessage):
            content = message.content
        else:
            print(f"LearningKernel: Unsupported message type: {type(message)}")
            return
            
        print(f"LearningKernel: Learning from {content}")
        
        # Hardcoded connection: Learning -> Memory
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            await memory_kernel.receive.remote(message)
            print("LearningKernel -> MemoryKernel")
        except ValueError:
            print("Error: MemoryKernel not found") 