"""
Base kernel class for the SwiftCog Python server.
"""
import asyncio
import ray
from abc import ABC, abstractmethod
from typing import Callable, Optional, List
from swiftcog_types import KernelID, KernelMessage


class BaseKernel:
    """Base class for all kernel implementations with async message queue."""
    
    def __init__(self, kernel_id: KernelID, custom_handler: Optional[Callable] = None):
        self.kernel_id = kernel_id
        self.custom_handler = custom_handler
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.processing_task: Optional[asyncio.Task] = None
        self.running = False
    
    def get_kernel_id(self) -> KernelID:
        """Return the kernel ID."""
        return self.kernel_id
    
    async def send_to_kernel(self, target_kernel_id: KernelID, message: KernelMessage) -> None:
        """Send a message to another kernel via KernelSystemActor (non-blocking)."""
        try:
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            await kernel_system_actor.send_message_to_kernel.remote(target_kernel_id, message)
            
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] {self.kernel_id.value} -> {target_kernel_id.value} ({message.get_message_type()}, non-blocking)")
        except ValueError:
            print(f"{self.kernel_id.value}: Error - KernelSystemActor not found")
    
    async def send_to_gui(self, message: KernelMessage) -> None:
        """Send a message directly to the GUI via KernelSystemActor (non-blocking)."""
        try:
            kernel_system_actor = ray.get_actor("KernelSystemActor")
            await kernel_system_actor.send_to_gui.remote(message)
            
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] {self.kernel_id.value} -> GUI ({message.get_message_type()}, non-blocking)")
        except ValueError:
            print(f"{self.kernel_id.value}: Error - KernelSystemActor not found")
    
    async def start(self) -> None:
        """Start the kernel's background message processing."""
        if not self.running:
            self.running = True
            self.processing_task = asyncio.create_task(self._process_messages())
            print(f"{self.kernel_id.value}: Started background message processing")
    
    async def stop(self) -> None:
        """Stop the kernel's background message processing."""
        self.running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        print(f"{self.kernel_id.value}: Stopped background message processing")
    
    async def send_message(self, message: KernelMessage) -> None:
        """Send a message to this kernel's queue (non-blocking)."""
        await self.message_queue.put(message)
    
    async def _process_messages(self) -> None:
        """Background task that continuously processes messages from the queue."""
        while self.running:
            try:
                # Wait for a message with a timeout to allow graceful shutdown
                message = await asyncio.wait_for(self.message_queue.get(), timeout=0.1)
                
                # Process the message
                await self.receive(message)
                
                # Mark task as done
                self.message_queue.task_done()
                
            except asyncio.TimeoutError:
                # Continue loop to check if still running
                continue
            except Exception as e:
                print(f"{self.kernel_id.value}: Error processing message: {e}")
    
    @abstractmethod
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message. Should be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement the receive method") 