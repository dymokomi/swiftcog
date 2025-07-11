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
2. Current person who is speaking 
3. Goals

Long term memory:
1. Facts that are rememembered arranged hierarchically
2. Visual memory of people (facial data)
3. Long term goals
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
            # Check the source kernel and log accordingly
            if message.source_kernel_id == KernelID.LEARNING:
                print(f"MemoryKernel: Storing text memory from learning kernel: {message.content}")
            elif message.source_kernel_id == KernelID.SENSING:
                print(f"MemoryKernel: Storing text memory from sensing kernel: {message.content}")
            elif message.source_kernel_id == KernelID.EXECUTIVE:
                print(f"MemoryKernel: Storing text memory from executive kernel: {message.content}")
            elif message.source_kernel_id == KernelID.SENSING_INTERFACE:
                print(f"MemoryKernel: Storing text memory from sensing interface: {message.content}")
            else:
                print(f"MemoryKernel: Storing text memory from {message.source_kernel_id.value} kernel: {message.content}")
            
            content = message.content
            print(f"MemoryKernel: Storing text memory: {content}")
        elif isinstance(message, GazeMessage):
            # Check the source kernel for gaze messages too
            if message.source_kernel_id == KernelID.SENSING:
                print(f"MemoryKernel: Storing gaze memory from sensing kernel: looking at screen = {message.looking_at_screen}")
            elif message.source_kernel_id == KernelID.SENSING_INTERFACE:
                print(f"MemoryKernel: Storing gaze memory from sensing interface: looking at screen = {message.looking_at_screen}")
            else:
                print(f"MemoryKernel: Storing gaze memory from {message.source_kernel_id.value}: looking at screen = {message.looking_at_screen}")
        else:
            print(f"MemoryKernel: Storing memory for message type {type(message)} from {message.source_kernel_id.value}")
        
        # Store the information in memory (for now just log it)
        # In a real implementation, this would store to a database or memory system
        # For now, we just acknowledge receipt and don't forward anywhere 