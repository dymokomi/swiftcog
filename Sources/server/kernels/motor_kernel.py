"""
Motor kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage
from .base_kernel import BaseKernel


@ray.remote
class MotorKernel(BaseKernel):
    """Motor kernel implementation with non-blocking message routing."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.MOTOR, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Process motor commands and forward to Expression (non-blocking)."""
        if isinstance(message, TextMessage):
            content = message.content
        else:
            print(f"MotorKernel: Unsupported message type: {type(message)}")
            return
            
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] MotorKernel: Processing {message.get_message_type()}")
        
        # Send to Expression kernel (non-blocking)
        await self.send_to_kernel(KernelID.EXPRESSION, message) 