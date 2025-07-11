"""
Sensing kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, GazeMessage, VoiceMessage, TextMessage
from .base_kernel import BaseKernel


@ray.remote
class SensingKernel(BaseKernel):
    """Sensing kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.SENSING, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        print(f"SensingKernel: Received {message.get_message_type()} message from {message.source_kernel_id.value}")
        
        # Handle different message types
        if isinstance(message, GazeMessage):
            await self.handle_gaze_data(message)
            return
        elif isinstance(message, TextMessage):
            await self.handle_text_data(message)
            return
        else:
            print(f"SensingKernel: Unknown message type: {type(message)}")
            return

    async def handle_gaze_data(self, message: GazeMessage) -> None:
        """Handle gaze data messages - for now just log them."""
        try:
            # Log feature vector information if available
            if message.feature_vector is not None:
                vector_len = len(message.feature_vector)
                print(f"SensingKernel: Received gaze data - looking: {message.looking_at_screen} with {vector_len}D feature vector")
                
                # Print first 10 values and last 5 values to show actual numbers
                if vector_len > 0:
                    first_10 = message.feature_vector[:10]
                    last_5 = message.feature_vector[-5:] if vector_len > 10 else []
                    
                    print(f"SensingKernel: Feature vector sample:")
                    print(f"  First 10 values: {[f'{x:.6f}' for x in first_10]}")
                    if last_5:
                        print(f"  Last 5 values:   {[f'{x:.6f}' for x in last_5]}")
                    
                    # Show some statistics
                    import numpy as np
                    vector_array = np.array(message.feature_vector)
                    print(f"  Statistics: min={vector_array.min():.6f}, max={vector_array.max():.6f}, mean={vector_array.mean():.6f}, std={vector_array.std():.6f}")
            else:
                print(f"SensingKernel: Received gaze data - looking: {message.looking_at_screen}")
            
            # Create a new GazeMessage with SensingKernel as the source
            forwarded_message = GazeMessage(
                source_kernel_id=KernelID.SENSING,
                looking_at_screen=message.looking_at_screen,
                feature_vector=message.feature_vector,
                feature_vector_dimensions=message.feature_vector_dimensions
            )
            
            # Send gaze data to memory kernel
            learning_kernel = ray.get_actor("LearningKernel")
            await learning_kernel.receive.remote(forwarded_message)

        except Exception as e:
            print(f"SensingKernel: Error processing gaze data: {e}")
    
    async def handle_text_data(self, message: KernelMessage) -> None:
        """Handle text data messages."""
        try:
            # Create a new TextMessage with SensingKernel as the source
            forwarded_message = TextMessage(
                source_kernel_id=KernelID.SENSING,
                content=message.content
            )

            learning_kernel = ray.get_actor("LearningKernel")
            executive_kernel = ray.get_actor("ExecutiveKernel")

            await learning_kernel.receive.remote(forwarded_message)
            await executive_kernel.receive.remote(forwarded_message)
            
        except Exception as e:
            print(f"SensingKernel: Error processing text data: {e}") 