"""
Memory kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage, GazeMessage

"""
Thinks that the memory should take care of.

Working memory:
1. Current dialog history (for now last 10 messages) and everything later
should be collapsed into a summary 

Long term memory:
2. Facts that are rememembered arranged hierarchically

"""

@ray.remote
class MemoryKernel:
    """Memory kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        self.custom_handler = custom_handler
        self.kernel_id = KernelID.MEMORY
    
    def get_kernel_id(self) -> KernelID:
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Default handler that processes and stores memory-related information."""
        if isinstance(message, TextMessage):
            content = message.content
            print(f"MemoryKernel: Storing text memory: {content}")
        elif isinstance(message, GazeMessage):
            print(f"MemoryKernel: Storing gaze memory: looking at screen = {message.looking_at_screen}")
        else:
            print(f"MemoryKernel: Storing memory for message type: {type(message)}")
        
        # Store the information in memory (for now just log it)
        # In a real implementation, this would store to a database or memory system
        # For now, we just acknowledge receipt and don't forward anywhere 