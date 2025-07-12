"""
Learning kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage, PersonPresenceMessage
from .base_kernel import BaseKernel


@ray.remote
class LearningKernel(BaseKernel):
    """Learning kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.LEARNING, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Default handler that processes learning and forwards directly to Memory."""
        if isinstance(message, TextMessage):
            content = message.content
        elif isinstance(message, PersonPresenceMessage):
            return
        else:
            print(f"LearningKernel: Unsupported message type: {type(message)}")
            return
            
        print(f"LearningKernel: Learning from {content}")
        
        # Hardcoded connection: Learning -> Memory
        try:
            # Create a new TextMessage with LearningKernel as the source
            forwarded_message = TextMessage(
                source_kernel_id=KernelID.LEARNING,
                content=content
            )
            
            memory_kernel = ray.get_actor("MemoryKernel")
            await memory_kernel.receive.remote(forwarded_message)
            print("LearningKernel -> MemoryKernel")
        except ValueError:
            print("Error: MemoryKernel not found") 