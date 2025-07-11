"""
Kernel system implementation for the SwiftCog Python server.
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
import websockets
from websockets.server import WebSocketServerProtocol
import ray
from swiftcog_types import KernelID, KernelMessage, AsyncMessage, MessageType, TextMessage, GazeMessage, VoiceMessage
from kernels import (
    SensingKernel,
    ExecutiveKernel,
    MotorKernel,
    ExpressionKernel,
    MemoryKernel,
    LearningKernel
)
from shared_components import SharedLLMService
import os


@ray.remote
class KernelSystemActor:
    """Ray actor for the kernel system - ensures single shared instance."""
    
    def __init__(self):
        self.kernels: Dict[KernelID, Any] = {}
        self.sensing_kernels: List[Any] = []
        self.shared_llm_service: Optional[Any] = None
        self.outgoing_messages: List[KernelMessage] = []  # Queue for messages to send to frontend
    
    async def initialize_shared_llm_service(self, api_key: str) -> None:
        """Initialize the shared LLM service."""
        if not self.shared_llm_service:
            print("Initializing shared LLM service...")
            self.shared_llm_service = SharedLLMService.remote(api_key)
            print("Shared LLM service initialized")
    
    def get_shared_llm_service(self) -> Any:
        """Get the shared LLM service."""
        return self.shared_llm_service
    
    async def create_sensing_kernel(self, custom_handler=None) -> Any:
        """Create a sensing kernel with optional custom handler."""
        kernel = SensingKernel.options(name="SensingKernel").remote(custom_handler)
        self.kernels[KernelID.SENSING] = kernel
        self.sensing_kernels.append(kernel)
        return kernel
    
    async def create_executive_kernel(self, custom_handler=None) -> Any:
        """Create an executive kernel with optional custom handler."""
        kernel = ExecutiveKernel.options(name="ExecutiveKernel").remote(custom_handler)
        self.kernels[KernelID.EXECUTIVE] = kernel
        return kernel
    
    async def create_motor_kernel(self, custom_handler=None) -> Any:
        """Create a motor kernel with optional custom handler."""
        kernel = MotorKernel.options(name="MotorKernel").remote(custom_handler)
        self.kernels[KernelID.MOTOR] = kernel
        return kernel
    
    async def create_expression_kernel(self, custom_handler=None) -> Any:
        """Create an expression kernel with optional custom handler."""
        kernel = ExpressionKernel.options(name="ExpressionKernel").remote(custom_handler)
        self.kernels[KernelID.EXPRESSION] = kernel
        return kernel
    
    async def create_memory_kernel(self, custom_handler=None) -> Any:
        """Create a memory kernel with optional custom handler."""
        kernel = MemoryKernel.options(name="MemoryKernel").remote(custom_handler)
        self.kernels[KernelID.MEMORY] = kernel
        return kernel
    
    async def create_learning_kernel(self, custom_handler=None) -> Any:
        """Create a learning kernel with optional custom handler."""
        kernel = LearningKernel.options(name="LearningKernel").remote(custom_handler)
        self.kernels[KernelID.LEARNING] = kernel
        return kernel
    
    async def queue_frontend_message(self, message: KernelMessage) -> None:
        """Queue a message for delivery to the frontend."""
        print("Backend queuing message for frontend")
        self.outgoing_messages.append(message)
    
    def get_message_summary(self, message: KernelMessage) -> str:
        """Get a readable summary of the message content."""
        if isinstance(message, TextMessage):
            return f"text: '{message.content}'"
        elif isinstance(message, GazeMessage):
            return f"gaze: looking={message.looking_at_screen}"
        elif isinstance(message, VoiceMessage):
            return f"voice: '{message.transcription}'"
        else:
            return f"{message.get_message_type()}: {type(message).__name__}"

    async def handle_message(self, message: KernelMessage) -> None:
        """Handle incoming message from frontend."""
        message_summary = self.get_message_summary(message)
        print(f"KernelSystemActor.handle_message() - Message: {message.source_kernel_id.value} -> {message_summary}")
        
        # Route message to sensing kernel (hardcoded connection from GUI)
        print("Backend routing message to SensingKernel")
        if self.sensing_kernels:
            sensing_kernel = self.sensing_kernels[0]
            await sensing_kernel.receive.remote(message)
        else:
            print("No sensing kernel available on backend!")
    
    def get_outgoing_messages(self) -> List[KernelMessage]:
        """Get and clear outgoing messages for the frontend."""
        messages = self.outgoing_messages.copy()
        self.outgoing_messages.clear()
        return messages
    
    async def create_default_kernels(self) -> None:
        """Create the default kernel system with hardcoded connections."""
        print("Creating default kernels...")

        sensing_kernel = await self.create_sensing_kernel()
        executive_kernel = await self.create_executive_kernel()
        motor_kernel = await self.create_motor_kernel()
        expression_kernel = await self.create_expression_kernel()
        memory_kernel = await self.create_memory_kernel()
        learning_kernel = await self.create_learning_kernel()


class KernelSystem:
    """Main kernel system with WebSocket communication."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.websocket_clients: List[WebSocketServerProtocol] = []
        self.kernel_system_actor: Optional[Any] = None
        
        # Don't initialize Ray here - let the caller handle it
        # This allows connecting to existing Ray clusters
    
    async def initialize(self) -> None:
        """Initialize the kernel system and create default kernels."""
        print("Initializing kernel system...")
        
        # Create the kernel system actor with a specific name
        try:
            # Try to get existing actor first
            self.kernel_system_actor = ray.get_actor("KernelSystemActor")
            print("Found existing KernelSystemActor")
        except ValueError:
            # Actor doesn't exist, create a new one
            self.kernel_system_actor = KernelSystemActor.options(name="KernelSystemActor").remote()
            print("Created new KernelSystemActor")
        
        # Initialize shared LLM service if API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            await self.kernel_system_actor.initialize_shared_llm_service.remote(api_key)
        else:
            print("OPENAI_API_KEY not set - LLM functionality will be limited")
        
        # Create default kernels
        await self.kernel_system_actor.create_default_kernels.remote()
        
        print("Kernel system initialized")
    
    async def process_message(self, message: KernelMessage) -> None:
        """Process a message from the frontend (ASGI version)."""
        if self.kernel_system_actor:
            await self.kernel_system_actor.handle_message.remote(message)
            
            # Check for outgoing messages and send them to frontend
            outgoing_messages = await self.kernel_system_actor.get_outgoing_messages.remote()
            for outgoing_message in outgoing_messages:
                await self.send_to_frontend(outgoing_message)
    
    async def send_to_frontend(self, message: KernelMessage) -> None:
        """Send message to all connected WebSocket clients."""
        async_message = AsyncMessage(type=MessageType.KERNEL_MESSAGE.value, kernel_message=message)
        await self.send_to_frontend_raw(async_message)
    
    async def send_to_frontend_raw(self, async_message: AsyncMessage) -> None:
        """Send an AsyncMessage directly to the frontend."""
        if not self.websocket_clients:
            print("No WebSocket clients connected")
            return
        
        message_json = json.dumps(async_message.to_dict())
        
        print(f"WebSocket Server: Sending message to {len(self.websocket_clients)} client(s)")
        
        # Send to all connected clients
        disconnected_clients = []
        for client in self.websocket_clients:
            try:
                await client.send(message_json)
                print("WebSocket Server: Message sent successfully")
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket client disconnected")
                disconnected_clients.append(client)
            except Exception as e:
                print(f"WebSocket Server: Failed to send to client: {e}")
                disconnected_clients.append(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            self.websocket_clients.remove(client)
    
    async def handle_websocket_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle a new WebSocket connection."""
        print(f"New WebSocket connection from {websocket.remote_address}")
        self.websocket_clients.append(websocket)
        
        try:
            async for message in websocket:
                try:
                    # Parse the incoming message
                    data = json.loads(message)
                    async_message = AsyncMessage.from_dict(data)
                    
                    # Handle kernel messages only
                    if async_message.type == MessageType.KERNEL_MESSAGE.value:
                        await self.process_message(async_message.kernel_message)
                    else:
                        print(f"Unknown message type: {async_message.type}")
                    
                except json.JSONDecodeError as e:
                    print(f"Failed to decode WebSocket message: {e}")
                except Exception as e:
                    print(f"Error handling WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"WebSocket connection error: {e}")
        finally:
            if websocket in self.websocket_clients:
                self.websocket_clients.remove(websocket)
    
    async def start_websocket_server(self) -> None:
        """Start the WebSocket server."""
        print(f"Starting WebSocket server on {self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_websocket_connection,
            self.host,
            self.port
        ):
            print(f"WebSocket server started on ws://{self.host}:{self.port}")
            # Keep the server running
            await asyncio.Future()  # Run forever
    
    async def run(self) -> None:
        """Run the kernel system."""
        await self.start_websocket_server()
    
    async def shutdown(self) -> None:
        """Shutdown the kernel system."""
        print("Shutting down kernel system...")
        
        # Close all WebSocket connections
        for client in self.websocket_clients:
            try:
                await client.close()
            except Exception as e:
                print(f"Error closing WebSocket client: {e}")
        
        # Shutdown Ray
        if ray.is_initialized():
            ray.shutdown()
        
        print("Kernel system shut down") 