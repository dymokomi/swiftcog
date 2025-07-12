"""
Sensing kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, GazeMessage, VoiceMessage, TextMessage, PersonPresenceMessage
from .base_kernel import BaseKernel
from tools.vector_recognition import VectorRecognition


@ray.remote
class SensingKernel(BaseKernel):
    """Sensing kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.SENSING, custom_handler)
        
        # Initialize vector recognition system
        self.vector_recognition = VectorRecognition(
            storage_file="gaze_vectors.json",
            threshold=0.7,
            max_vectors_per_id=10,
            expected_dimensions=768
        )
    
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
        """Handle gaze data messages and send person presence updates."""
        try:
            person_id = None
            is_present = False
            
            # Check if person is present based on looking at screen
            if message.looking_at_screen and message.feature_vector is not None:
                vector_len = len(message.feature_vector)
                print(f"SensingKernel: Received gaze data - looking: {message.looking_at_screen} with {vector_len}D feature vector")
                
                # Recognize the vector and get person ID
                if vector_len == 768:  # Only process if we have the expected dimensions
                    try:
                        person_id = self.vector_recognition.recognize_vector(message.feature_vector)
                        is_present = True
                        print(f"SensingKernel: Person recognized with ID: {person_id}")
                        
                        # Get and log recognition stats
                        stats = self.vector_recognition.get_stats()
                        print(f"SensingKernel: Recognition stats - {stats['total_groups']} groups, {stats['total_vectors']} vectors stored")
                        
                    except Exception as e:
                        print(f"SensingKernel: Error in vector recognition: {e}")
                        # Still consider person present even if recognition fails
                        is_present = True
                        person_id = None
                else:
                    print(f"SensingKernel: Skipping vector recognition - expected 768 dimensions, got {vector_len}")
                    # Still consider person present even if dimensions are wrong
                    is_present = True
                    person_id = None
            else:
                # No person detected
                is_present = False
                person_id = None
                if not message.looking_at_screen:
                    print(f"SensingKernel: No person detected - not looking at screen")
                else:
                    print(f"SensingKernel: No person detected - no feature vector")
            
            # Create and send PersonPresenceMessage
            presence_message = PersonPresenceMessage(
                source_kernel_id=KernelID.SENSING,
                is_present=is_present,
                person_id=person_id
            )
            
            # Send person presence data to learning kernel
            learning_kernel = ray.get_actor("LearningKernel")
            await learning_kernel.receive.remote(presence_message)
            
            print(f"SensingKernel: Sent person presence - present: {is_present}, ID: {person_id}")

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