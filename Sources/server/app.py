"""
FastAPI ASGI application for SwiftCog Python server.
This file creates the ASGI app that can be run with uvicorn.
"""
import os
import sys
import asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import ray

# Add the server directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kernel_system import KernelSystem
from swiftcog_types import WebSocketMessage, KernelMessage
import json

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(title="SwiftCog Python Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global kernel system instance
kernel_system: Optional[KernelSystem] = None

@app.on_event("startup")
async def startup_event():
    """Initialize the server on startup."""
    global kernel_system
    
    print("Starting SwiftCog Python Server...")
    
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        raise RuntimeError("OPENAI_API_KEY environment variable not set")
    
    # Connect to existing Ray cluster
    try:
        if not ray.is_initialized():
            print("Connecting to Ray cluster...")
            ray.init(address="auto")  # Connect to existing cluster
        print("Ray connected successfully!")
    except Exception as e:
        print(f"Failed to connect to Ray cluster: {e}")
        print("Make sure Ray cluster is running: ray start --head")
        raise
    
    # Initialize kernel system with default kernels
    kernel_system = KernelSystem(host="127.0.0.1", port=8765)
    await kernel_system.initialize()
    
    print("Server initialized successfully!")
    print("Connect SwiftCog GUI to ws://127.0.0.1:8000/ws")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global kernel_system
    
    print("Shutting down SwiftCog Server...")
    
    if kernel_system:
        await kernel_system.shutdown()
    
    if ray.is_initialized():
        ray.shutdown()
    
    print("Server shutdown complete")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "SwiftCog Python Server",
        "status": "running",
        "version": "1.0.0",
        "websocket_url": "ws://127.0.0.1:8000/ws"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "ray_initialized": ray.is_initialized() if ray else False,
        "kernel_system_ready": kernel_system is not None
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for GUI communication with real-time message polling."""
    global kernel_system
    
    await websocket.accept()
    print("GUI connected via WebSocket")
    
    # Create new session context and deactivate all person percepts when GUI connects
    if kernel_system and kernel_system.kernel_system_actor:
        try:
            # Get the memory kernel and create a new session context
            memory_kernel = ray.get_actor("MemoryKernel")
            
            # Check if there were any active people before starting new session
            person_percepts = await memory_kernel.get_concepts_by_type.remote("percept")
            active_percepts = [p for p in person_percepts if p.get("activation", 0) > 0]
            
            new_session_id = await memory_kernel.create_new_session_context.remote("GUI connected - new session")
            
            # Record session start in conversation history
            from swiftcog_types import ConversationMessage, KernelID
            session_message = ConversationMessage(
                source_kernel_id=KernelID.MEMORY,
                speaker="system", 
                content="[Session] New session started - GUI connected",
                store_in_memory=True
            )
            await memory_kernel.receive.remote(session_message)
            
            # Deactivate all person percepts from previous session
            deactivated_count = await memory_kernel.deactivate_all_person_percepts.remote()
            print(f"GUI: Created new session context {new_session_id}, deactivated {deactivated_count} person percepts")
            
            # If there were active people, record that the session reset
            if active_percepts:
                session_reset_message = ConversationMessage(
                    source_kernel_id=KernelID.MEMORY,
                    speaker="system",
                    content="[Session] Previous session ended - all participants disconnected",
                    store_in_memory=True
                )
                await memory_kernel.receive.remote(session_reset_message)
            
        except Exception as e:
            print(f"GUI: Error creating new session context: {e}")
    
    # Flag to control message polling
    processing_active = False
    
    async def poll_and_send_gui_messages():
        """Continuously poll for GUI messages and send them immediately."""
        while processing_active:
            try:
                if kernel_system and kernel_system.kernel_system_actor:
                    # Check for GUI messages
                    gui_messages = await kernel_system.kernel_system_actor.get_gui_messages.remote()
                    
                    if gui_messages:
                        for gui_message in gui_messages:
                            import datetime
                            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            
                            response = WebSocketMessage(
                                type="kernelMessage",
                                kernel_message=gui_message.to_dict()
                            )
                            await websocket.send_text(response.model_dump_json())
                            print(f"[{timestamp}] GUI: Sent {gui_message.get_message_type()} to WebSocket (real-time)")
                
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.005)  # 5ms polling interval for real-time response
                
            except Exception as e:
                print(f"GUI: Error in message polling: {e}")
                break
    
    try:
        while True:
            # Receive message from GUI
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message = WebSocketMessage(**message_data)
                
                if message.type == "kernelMessage":
                    # Process kernel message
                    kernel_message = message.get_kernel_message()
                    if not kernel_message:
                        error_response = WebSocketMessage(
                            type="error",
                            success=False,
                            message="Invalid kernel message format."
                        )
                        await websocket.send_text(error_response.model_dump_json())
                        continue
                    
                    # Start real-time message processing
                    if kernel_system and kernel_system.kernel_system_actor:
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] GUI: Starting real-time message processing")
                        
                        # Start polling for messages if not already active
                        if not processing_active:
                            processing_active = True
                            polling_task = asyncio.create_task(poll_and_send_gui_messages())
                        
                        # Handle message asynchronously - results will be polled and sent in real-time
                        await kernel_system.kernel_system_actor.handle_message.remote(kernel_message)
                        
                        print(f"[{timestamp}] GUI: Message processing initiated (real-time polling active)")
                    else:
                        print("Error: Kernel system not initialized")
                        error_response = WebSocketMessage(
                            type="error",
                            success=False,
                            message="Kernel system not initialized"
                        )
                        await websocket.send_text(error_response.model_dump_json())
                
                else:
                    print(f"Unknown message type: {message.type}")
                    
            except json.JSONDecodeError as e:
                print(f"Invalid JSON received: {e}")
                error_response = WebSocketMessage(
                    type="error",
                    success=False,
                    message=f"Invalid JSON: {str(e)}"
                )
                await websocket.send_text(error_response.model_dump_json())
                 
            except Exception as e:
                print(f"Error processing message: {e}")
                error_response = WebSocketMessage(
                    type="error",
                    success=False,
                    message=f"Error processing message: {str(e)}"
                )
                await websocket.send_text(error_response.model_dump_json())
     
    except WebSocketDisconnect:
        print("GUI disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Stop message polling
        processing_active = False
        print("WebSocket connection closed")

if __name__ == "__main__":
    import uvicorn
    
    # This is for development - in production, use uvicorn command
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info") 