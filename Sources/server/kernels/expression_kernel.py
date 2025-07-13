"""
Expression kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage
from .base_kernel import BaseKernel


@ray.remote
class ExpressionKernel(BaseKernel):
    """Expression kernel implementation that sends directly to GUI (real-time)."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.EXPRESSION, custom_handler)
    
    async def receive(self, message: KernelMessage) -> None:
        """Process message and send directly to GUI immediately (non-blocking)."""
        if isinstance(message, TextMessage):
            content = message.content
        else:
            print(f"ExpressionKernel: Unsupported message type: {type(message)}")
            return
            
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] ExpressionKernel: Processing and sending to GUI: {message.get_message_type()}")
        
        # Send directly to GUI (non-blocking, real-time)
        await self.send_to_gui(message) 