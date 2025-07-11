"""
Sensing kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, GazeMessage, VoiceMessage, TextMessage


@ray.remote
class SensingKernel:
    """Sensing kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        self.custom_handler = custom_handler
        self.kernel_id = KernelID.SENSING
    
    def get_kernel_id(self) -> KernelID:
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        print(f"SensingKernel: Processing {message.get_message_type()} message from {message.source_kernel_id.value}")
        
        # Handle different message types
        if isinstance(message, GazeMessage):
            await self.handle_gaze_data(message)
            return
        elif isinstance(message, VoiceMessage):
            await self.handle_voice_data(message)
            return
        elif isinstance(message, TextMessage):
            await self.handle_text_data(message)
            return
        else:
            print(f"SensingKernel: Unknown message type: {type(message)}")
            # Forward unknown messages as text
            await self.handle_text_data(message)
    
    async def handle_gaze_data(self, message: GazeMessage) -> None:
        """Handle gaze data messages - for now just log them."""
        try:
            # Send gaze data to memory kernel
            memory_kernel = ray.get_actor("MemoryKernel")
            await memory_kernel.receive.remote(message)
            print("SensingKernel -> MemoryKernel (gaze data)")
            
            print(f"SensingKernel: Received gaze data - looking at screen: {message.looking_at_screen}")
            # For now, just log the gaze data as requested
            # Future implementations could store this data, trigger behaviors, etc.
            
        except Exception as e:
            print(f"SensingKernel: Error processing gaze data: {e}")
    
    async def handle_voice_data(self, message: VoiceMessage) -> None:
        """Handle voice/speech data messages."""
        try:
            # Send voice data to memory kernel
            memory_kernel = ray.get_actor("MemoryKernel")
            await memory_kernel.receive.remote(message)
            print("SensingKernel -> MemoryKernel (voice data)")
            
            # Forward voice data to executive for processing
            executive_kernel = ray.get_actor("ExecutiveKernel")
            await executive_kernel.receive.remote(message)
            print("SensingKernel -> ExecutiveKernel (voice data)")
            
            print(f"SensingKernel: Received voice data - transcription: '{message.transcription}'")
            
        except Exception as e:
            print(f"SensingKernel: Error processing voice data: {e}")
    
    async def handle_text_data(self, message: KernelMessage) -> None:
        """Handle text data messages."""
        try:
            # Send text data to memory kernel
            memory_kernel = ray.get_actor("MemoryKernel")
            await memory_kernel.receive.remote(message)
            print("SensingKernel -> MemoryKernel (text data)")
            
            # Forward text data to executive for processing
            executive_kernel = ray.get_actor("ExecutiveKernel")
            await executive_kernel.receive.remote(message)
            print("SensingKernel -> ExecutiveKernel (text data)")
            
            if isinstance(message, TextMessage):
                print(f"SensingKernel: Received text data: '{message.content}'")
            else:
                print(f"SensingKernel: Received unknown message type: {type(message)}")
            
        except Exception as e:
            print(f"SensingKernel: Error processing text data: {e}") 