"""
Main entry point for the SwiftCog Python server.
"""
import asyncio
import os
import sys
import signal
from typing import Optional
import uvloop
from dotenv import load_dotenv

# Add the server directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kernel_system import KernelSystem

# Load environment variables
load_dotenv()


class SwiftCogServer:
    """Main server class for SwiftCog Python backend."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.kernel_system: Optional[KernelSystem] = None
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize the server with kernel system and default kernels."""
        print("🚀 Initializing SwiftCog Python Server...")
        
        # Create kernel system with default kernels
        self.kernel_system = KernelSystem(host=self.host, port=self.port)
        await self.kernel_system.initialize()
        
        print("🌐 Server initialized successfully!")
    
    async def start(self):
        """Start the server."""
        if not self.kernel_system:
            raise RuntimeError("Server not initialized. Call initialize() first.")
        
        print(f"🌐 Starting SwiftCog Server on ws://{self.host}:{self.port}")
        
        # Set up signal handlers for graceful shutdown
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, self._signal_handler)
        
        # Start the kernel system (WebSocket server)
        try:
            server_task = asyncio.create_task(self.kernel_system.run())
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            
            # Wait for either server completion or shutdown signal
            done, pending = await asyncio.wait(
                [server_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            print(f"❌ Server error: {e}")
            raise
        finally:
            await self.shutdown()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.shutdown_event.set()
    
    async def shutdown(self):
        """Shutdown the server gracefully."""
        print("🛑 Shutting down SwiftCog Server...")
        
        if self.kernel_system:
            await self.kernel_system.shutdown()
        
        print("🛑 Server shutdown complete")


async def main():
    """Main function to run the server."""
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    # Parse command line arguments for host and port
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8765"))
    
    # Create and run server
    server = SwiftCogServer(host=host, port=port)
    
    try:
        await server.initialize()
        await server.start()
    except KeyboardInterrupt:
        print("\nServer interrupted by user")
    except Exception as e:
        print(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Use uvloop for better performance on Unix systems
    if sys.platform != "win32":
        uvloop.install()
    
    print("SwiftCog Python Server")
    print("=" * 50)
    
    # Run the server
    asyncio.run(main()) 