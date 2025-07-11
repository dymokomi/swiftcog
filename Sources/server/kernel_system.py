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
from swiftcog_types import KernelID, KernelMessage, AsyncMessage, MessageType
from sensing_kernel import SensingKernel
from executive_kernel import ExecutiveKernel
from motor_kernel import MotorKernel
from expression_kernel import ExpressionKernel
from memory_kernel import MemoryKernel
from learning_kernel import LearningKernel
from kernels import SharedLLMService
import os


class KernelSystem:
    """Main kernel system with WebSocket communication."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.kernels: Dict[KernelID, Any] = {}
        self.sensing_kernels: List[Any] = []
        self.connections: Dict[KernelID, KernelID] = {}
        self.websocket_clients: List[WebSocketServerProtocol] = []
        self.message_handler: Optional[Any] = None
        self.shared_llm_service: Optional[Any] = None
        
        # Don't initialize Ray here - let the caller handle it
        # This allows connecting to existing Ray clusters
    
    async def create_sensing_kernel(self, custom_handler=None) -> Any:
        """Create a sensing kernel with optional custom handler."""
        kernel = SensingKernel.remote(custom_handler)
        self.kernels[KernelID.SENSING] = kernel
        self.sensing_kernels.append(kernel)
        return kernel
    
    async def create_executive_kernel(self, custom_handler=None) -> Any:
        """Create an executive kernel with optional custom handler."""
        kernel = ExecutiveKernel.remote(custom_handler)
        self.kernels[KernelID.EXECUTIVE] = kernel
        return kernel
    
    async def create_motor_kernel(self, custom_handler=None) -> Any:
        """Create a motor kernel with optional custom handler."""
        kernel = MotorKernel.remote(custom_handler)
        self.kernels[KernelID.MOTOR] = kernel
        return kernel
    
    async def create_expression_kernel(self, custom_handler=None) -> Any:
        """Create an expression kernel with optional custom handler."""
        kernel = ExpressionKernel.remote(custom_handler)
        self.kernels[KernelID.EXPRESSION] = kernel
        return kernel
    
    async def create_memory_kernel(self, custom_handler=None) -> Any:
        """Create a memory kernel with optional custom handler."""
        kernel = MemoryKernel.remote(custom_handler)
        self.kernels[KernelID.MEMORY] = kernel
        return kernel
    
    async def create_learning_kernel(self, custom_handler=None) -> Any:
        """Create a learning kernel with optional custom handler."""
        kernel = LearningKernel.remote(custom_handler)
        self.kernels[KernelID.LEARNING] = kernel
        return kernel
    
    async def connect(self, from_kernel: Any, to_kernel: Any) -> None:
        """Connect two kernels in the pipeline."""
        # Get kernel IDs from the Ray actors
        from_id = await from_kernel.get_kernel_id.remote()
        to_id = await to_kernel.get_kernel_id.remote()
        
        self.connections[from_id] = to_id
        print(f"🔗 Connected {from_id.value} -> {to_id.value}")
    
    async def emit(self, message: KernelMessage, from_kernel: Any) -> None:
        """Emit a message from a kernel to the next in the pipeline."""
        # Get emitter kernel ID
        emitter_id = await from_kernel.get_kernel_id.remote()
        print(f"🚀 KernelSystem.emit() - From: {emitter_id.value}, Message: '{message.payload}'")
        
        # Local routing to next kernel in pipeline
        if emitter_id in self.connections:
            destination_id = self.connections[emitter_id]
            if destination_id in self.kernels:
                destination_kernel = self.kernels[destination_id]
                print(f"🔀 Backend routing {emitter_id.value} -> {destination_id.value}")
                await destination_kernel.receive.remote(message)
            else:
                print(f"⚠️ No kernel found for {destination_id.value}")
        else:
            print(f"⚠️ No connection found for {emitter_id.value}")
        
        # If this is the final kernel (ExpressionKernel), send to frontend
        if emitter_id == KernelID.EXPRESSION:
            print("📤 Backend sending to frontend via WebSocket (ExpressionKernel)")
            await self.send_to_frontend(message)
    
    async def handle_message(self, message: KernelMessage) -> None:
        """Handle incoming message from frontend."""
        print(f"🔄 KernelSystem.handle_message() - Message: {message.source_kernel_id.value} -> '{message.payload}'")
        
        # Route message to sensing kernel
        print("📥 Backend routing message to SensingKernel")
        if self.sensing_kernels:
            sensing_kernel = self.sensing_kernels[0]
            await sensing_kernel.receive.remote(message)
        else:
            print("❌ No sensing kernel available on backend!")
    
    async def send_to_frontend(self, message: KernelMessage) -> None:
        """Send message to all connected WebSocket clients."""
        if self.message_handler:
            # Use the custom message handler for ASGI
            await self.message_handler(message)
        else:
            # Use the legacy WebSocket method
            async_message = AsyncMessage(type=MessageType.KERNEL_MESSAGE.value, kernel_message=message)
            await self.send_to_frontend_raw(async_message)
    
    async def send_to_frontend_raw(self, async_message: AsyncMessage) -> None:
        """Send an AsyncMessage directly to the frontend."""
        if not self.websocket_clients:
            print("⚠️ No WebSocket clients connected")
            return
        
        message_json = json.dumps(async_message.to_dict())
        
        print(f"🌐 WebSocket Server: Sending message to {len(self.websocket_clients)} client(s)")
        
        # Send to all connected clients
        disconnected_clients = []
        for client in self.websocket_clients:
            try:
                await client.send(message_json)
                print("✅ WebSocket Server: Message sent successfully")
            except websockets.exceptions.ConnectionClosed:
                print("❌ WebSocket client disconnected")
                disconnected_clients.append(client)
            except Exception as e:
                print(f"❌ WebSocket Server: Failed to send to client: {e}")
                disconnected_clients.append(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            self.websocket_clients.remove(client)
    
    async def initialize(self) -> None:
        """Initialize the kernel system and create default kernels."""
        print("🔧 Initializing kernel system...")
        
        # Initialize shared LLM service if API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            await self.initialize_shared_llm_service(api_key)
        else:
            print("⚠️ OPENAI_API_KEY not set - LLM functionality will be limited")
        
        # Create default kernels
        await self.create_default_kernels()
        
        print("✅ Kernel system initialized")
    
    async def initialize_shared_llm_service(self, api_key: str) -> None:
        """Initialize the shared LLM service."""
        if not self.shared_llm_service:
            print("🧠 Initializing shared LLM service...")
            self.shared_llm_service = SharedLLMService.remote(api_key)
            print("✅ Shared LLM service initialized")
    
    def get_shared_llm_service(self) -> Any:
        """Get the shared LLM service."""
        return self.shared_llm_service
    
    def set_message_handler(self, handler) -> None:
        """Set custom message handler for ASGI integration."""
        self.message_handler = handler
    
    async def process_message(self, message: KernelMessage) -> None:
        """Process a message from the frontend (ASGI version)."""
        await self.handle_message(message)
    
    async def emit_from_actor(self, message: KernelMessage, emitter_id: KernelID) -> None:
        """Emit a message from within a Ray actor (simplified version)."""
        print(f"🚀 KernelSystem.emit_from_actor() - From: {emitter_id.value}, Message: '{message.payload}'")
        
        # Local routing to next kernel in pipeline
        if emitter_id in self.connections:
            destination_id = self.connections[emitter_id]
            if destination_id in self.kernels:
                destination_kernel = self.kernels[destination_id]
                print(f"🔀 Backend routing {emitter_id.value} -> {destination_id.value}")
                await destination_kernel.receive.remote(message)
            else:
                print(f"⚠️ No kernel found for {destination_id.value}")
        else:
            print(f"⚠️ No connection found for {emitter_id.value}")
        
        # If this is the final kernel (ExpressionKernel), send to frontend
        if emitter_id == KernelID.EXPRESSION:
            print("📤 Backend sending to frontend via WebSocket (ExpressionKernel)")
            await self.send_to_frontend(message)

    async def create_default_kernels(self) -> None:
        """Create the default kernel system with hardcoded connections."""
        print("🔧 Creating default kernels...")
        
        # Import kernel handlers
        from kernels import create_sensing_handler, create_executive_handler, create_motor_handler, create_expression_handler
        
        # Create a reference to this kernel system for use in handlers
        kernel_system_ref = self
        
        # Create default handlers for all kernels
        sensing_handler = await create_sensing_handler(kernel_system_ref)
        executive_handler = await create_executive_handler(
            kernel_system_ref,
            system_prompt="""You are an executive decision-making system in a cognitive architecture. 
Your role is to analyze input from sensing and memory, then provide intelligent decisions or responses.
Be very concise and provide direct answers to questions.""",
            temperature=0.7,
            max_tokens=500
        )
        motor_handler = await create_motor_handler(kernel_system_ref)
        expression_handler = await create_expression_handler(kernel_system_ref)
        
        # Simple pass-through handlers for Memory and Learning kernels
        async def memory_handler(message: KernelMessage, kernel):
            print(f"Backend MemoryKernel: Processing memory for {message.payload}")
            await kernel_system_ref.emit_from_actor(message, KernelID.MEMORY)
            
        async def learning_handler(message: KernelMessage, kernel):
            print(f"Backend LearningKernel: Learning from {message.payload}")
            await kernel_system_ref.emit_from_actor(message, KernelID.LEARNING)
        
        # Create all kernels with their handlers
        sensing_kernel = await self.create_sensing_kernel(sensing_handler)
        executive_kernel = await self.create_executive_kernel(executive_handler)
        motor_kernel = await self.create_motor_kernel(motor_handler)
        expression_kernel = await self.create_expression_kernel(expression_handler)
        memory_kernel = await self.create_memory_kernel(memory_handler)
        learning_kernel = await self.create_learning_kernel(learning_handler)
        
        # Set up connections according to the specified architecture:
        # Sensing -> Executive
        await self.connect(sensing_kernel, executive_kernel)
        
        # Memory -> Executive
        await self.connect(memory_kernel, executive_kernel)
        
        # Executive -> Motor
        await self.connect(executive_kernel, motor_kernel)
        
        # Motor -> Expression  
        await self.connect(motor_kernel, expression_kernel)
        
        # Expression -> GUI (handled automatically in emit() method)
        
        # Executive -> Learning
        await self.connect(executive_kernel, learning_kernel)
        
        # Learning -> Memory
        await self.connect(learning_kernel, memory_kernel)
        
        print("✅ Default kernels created with hardcoded connections:")
        print("   📥 Sensing -> Executive")
        print("   🧠 Memory -> Executive")
        print("   🎯 Executive -> Motor")
        print("   🚀 Motor -> Expression")
        print("   💬 Expression -> GUI")
        print("   📚 Executive -> Learning")
        print("   🔄 Learning -> Memory")
    
    async def handle_websocket_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle a new WebSocket connection."""
        print(f"🌐 New WebSocket connection from {websocket.remote_address}")
        self.websocket_clients.append(websocket)
        
        try:
            async for message in websocket:
                try:
                    # Parse the incoming message
                    data = json.loads(message)
                    async_message = AsyncMessage.from_dict(data)
                    
                    # Handle kernel messages only
                    if async_message.type == MessageType.KERNEL_MESSAGE.value:
                        await self.handle_message(async_message.kernel_message)
                    else:
                        print(f"❌ Unknown message type: {async_message.type}")
                    
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to decode WebSocket message: {e}")
                except Exception as e:
                    print(f"❌ Error handling WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("🌐 WebSocket connection closed")
        except Exception as e:
            print(f"❌ WebSocket connection error: {e}")
        finally:
            if websocket in self.websocket_clients:
                self.websocket_clients.remove(websocket)
    
    async def start_websocket_server(self) -> None:
        """Start the WebSocket server."""
        print(f"🌐 Starting WebSocket server on {self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_websocket_connection,
            self.host,
            self.port
        ):
            print(f"🌐 WebSocket server started on ws://{self.host}:{self.port}")
            # Keep the server running
            await asyncio.Future()  # Run forever
    
    async def run(self) -> None:
        """Run the kernel system."""
        await self.start_websocket_server()
    
    async def shutdown(self) -> None:
        """Shutdown the kernel system."""
        print("🛑 Shutting down kernel system...")
        
        # Close all WebSocket connections
        for client in self.websocket_clients:
            try:
                await client.close()
            except Exception as e:
                print(f"Error closing WebSocket client: {e}")
        
        # Shutdown Ray
        if ray.is_initialized():
            ray.shutdown()
        
        print("🛑 Kernel system shut down") 