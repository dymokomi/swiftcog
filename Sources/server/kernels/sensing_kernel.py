"""
Sensing kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage


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
        if self.custom_handler:
            await self.custom_handler(message, self)
        else:
            await self.default_handler(message)
    
    async def default_handler(self, message: KernelMessage) -> None:
        """Default handler that processes the message and forwards directly to Executive."""
        print(f"SensingKernel: Processing '{message.payload}'")
        
        # Check if this is gaze data
        if self.is_gaze_data_message(message.payload):
            await self.handle_gaze_data(message.payload)
            return
        
        # Regular user input - forward to Executive
        try:
            executive_kernel = ray.get_actor("ExecutiveKernel")
            await executive_kernel.receive.remote(message)
            print("SensingKernel -> ExecutiveKernel")
        except ValueError:
            print("Error: ExecutiveKernel not found")
    
    def is_gaze_data_message(self, payload: str) -> bool:
        """Check if the message payload contains gaze data."""
        try:
            import json
            data = json.loads(payload)
            return data.get("messageType") == "gazeData"
        except (json.JSONDecodeError, AttributeError):
            return False
    
    async def handle_gaze_data(self, payload: str) -> None:
        """Handle gaze data messages - for now just log them."""
        try:
            import json
            gaze_data = json.loads(payload)
            looking_at_screen = gaze_data.get("lookingAtScreen", False)
            timestamp = gaze_data.get("timestamp", "unknown")
            
            print(f"SensingKernel: Received gaze data - looking at screen: {looking_at_screen} at {timestamp}")
            # For now, just log the gaze data as requested
            # Future implementations could store this data, trigger behaviors, etc.
            
        except Exception as e:
            print(f"SensingKernel: Error processing gaze data: {e}") 