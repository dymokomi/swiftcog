"""
Base kernel class for the SwiftCog Python server.
"""
from abc import ABC, abstractmethod
from typing import Callable, Optional
from swiftcog_types import KernelID, KernelMessage


class BaseKernel:
    """Base class for all kernel implementations."""
    
    def __init__(self, kernel_id: KernelID, custom_handler: Optional[Callable] = None):
        self.kernel_id = kernel_id
        self.custom_handler = custom_handler
    
    def get_kernel_id(self) -> KernelID:
        """Return the kernel ID."""
        return self.kernel_id
    
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message. Should be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement the receive method") 