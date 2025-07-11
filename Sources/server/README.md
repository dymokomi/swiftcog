# SwiftCog Python Server

A Python implementation of the SwiftCog cognitive architecture server using Ray for distributed computing and WebSocket for GUI communication.

## Features

- **Ray-based Distributed Computing**: Each kernel runs as a Ray actor for scalability
- **WebSocket Communication**: Real-time communication with Swift GUI
- **Cognitive Architecture**: Sensing, Executive, Motor, and Expression kernels
- **OpenAI Integration**: Built-in LLM service for intelligent responses
- **Dynamic App Loading**: Load custom apps from Python code
- **Graceful Shutdown**: Proper cleanup of resources

## Installation

1. Install Python dependencies:
```bash
cd Sources/server
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

## Usage

### Quick Start with Ray and Uvicorn

The recommended way to start the server is using the startup script:

```bash
cd Sources/server
export OPENAI_API_KEY="your-openai-api-key"
./start_server.sh
```

This script will:
1. Install dependencies
2. Start Ray cluster (`ray start --head`)
3. Start uvicorn server (`uvicorn app:app --port 8000`)
4. Clean up Ray cluster on shutdown

### Manual Start (Advanced)

If you prefer to start components manually:

```bash
# Terminal 1: Start Ray cluster
ray start --head --port=6379 --dashboard-port=8265 --include-dashboard

# Terminal 2: Start uvicorn server
cd Sources/server
export OPENAI_API_KEY="your-openai-api-key"
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# When done, stop Ray cluster
ray stop
```

### Environment Variables

- `OPENAI_API_KEY`: Required - Your OpenAI API key
- Ray cluster runs on port 6379
- Ray dashboard available at http://127.0.0.1:8265
- Server runs on `ws://127.0.0.1:8000/ws`

## Architecture

### Kernel System

The Python server implements the same kernel architecture as the Swift version:

1. **SensingKernel**: Processes incoming messages from the GUI
2. **ExecutiveKernel**: Makes decisions using LLM integration
3. **MotorKernel**: Handles action processing
4. **ExpressionKernel**: Formats responses for the GUI

### Message Flow

```
GUI (Swift) → WebSocket → SensingKernel → ExecutiveKernel → MotorKernel → ExpressionKernel → WebSocket → GUI (Swift)
```

### Ray Integration

Each kernel runs as a Ray actor, allowing for:
- Distributed processing across multiple cores/machines
- Fault tolerance and recovery
- Scalable parallel processing

## Creating Custom Apps

Create a Python file with your custom app class:

```python
import os
from kernel_system import KernelSystem
from llm_service import LLMService, OpenAIProvider
from kernels import (
    create_sensing_handler,
    create_executive_handler,
    create_motor_handler,
    create_expression_handler
)

class MyCustomApp:
    APP_NAME = "MyCustomApp"
    APP_DESCRIPTION = "My custom cognitive architecture app"
    
    def __init__(self, system: KernelSystem, llm_service: LLMService):
        self.system = system
        self.llm_service = llm_service
        self.sensing_kernel = None
        self.executive_kernel = None
        self.motor_kernel = None
        self.expression_kernel = None
    
    @classmethod
    async def init_backend(cls, system: KernelSystem):
        """Initialize the app with custom kernel setup."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        openai_provider = OpenAIProvider(api_key)
        llm_service = LLMService(openai_provider)
        app = cls(system, llm_service)
        
        # Create custom handlers
        sensing_handler = await create_sensing_handler(system)
        executive_handler = await create_executive_handler(system, llm_service)
        motor_handler = await create_motor_handler(system)
        expression_handler = await create_expression_handler(system)
        
        # Create kernels
        app.sensing_kernel = await system.create_sensing_kernel(sensing_handler)
        app.executive_kernel = await system.create_executive_kernel(executive_handler)
        app.motor_kernel = await system.create_motor_kernel(motor_handler)
        app.expression_kernel = await system.create_expression_kernel(expression_handler)
        
        # Connect kernels
        await system.connect(app.sensing_kernel, app.executive_kernel)
        await system.connect(app.executive_kernel, app.motor_kernel)
        await system.connect(app.motor_kernel, app.expression_kernel)
        
        return app
```

## Integration with Swift GUI

### Command Line Usage

The recommended way to run the GUI with a specific Python app:

```bash
# Start the server first
cd Sources/server
export OPENAI_API_KEY="your-openai-api-key"
./start_server.sh

# In another terminal, run the GUI with an app
cd Sources/SwiftCogGUI
swift run SwiftCogGUI --app Sources/Examples/Python/ExampleApp.py
```

Available example apps:
- `Sources/Examples/Python/ExampleApp.py` - General cognitive assistant
- `Sources/Examples/Python/MathTutorApp.py` - Math tutoring specialist  
- `Sources/Examples/Python/WeatherAssistantApp.py` - Weather information assistant

### WebSocket Communication

The Python server communicates with the Swift GUI using WebSocket messages over the `/ws` endpoint. The message format is JSON-based:

```json
{
  "type": "kernelMessage",
  "kernelMessage": {
    "id": "uuid",
    "sourceKernelId": "sensing",
    "payload": "message content",
    "timestamp": "2023-12-01T12:00:00Z"
  }
}
```

## Testing

### Command Line Testing

You can test app loading without the GUI using the test script:

```bash
cd Sources/server
python test_cli.py ../Examples/Python/ExampleApp.py
```

This will:
1. Connect to the WebSocket server
2. Send the app code for loading
3. Test a sample message exchange
4. Display the server responses

### Manual Testing

You can also test individual components:

```bash
# Test WebSocket connection
curl -X GET http://127.0.0.1:8000/health

# View API documentation
open http://127.0.0.1:8000/docs

# Monitor Ray dashboard
open http://127.0.0.1:8265
```

## Development

### Project Structure

```
Sources/server/
├── __init__.py              # Package initialization
├── main.py                  # Server entry point
├── types.py                 # Core data types
├── kernel_system.py         # Kernel system implementation
├── kernels.py               # Kernel implementations
├── llm_service.py          # LLM service providers
├── example_app.py          # Example application
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

### Key Components

- **KernelSystem**: Manages kernels and WebSocket communication
- **Kernels**: Ray actors implementing cognitive functions
- **LLMService**: OpenAI integration for intelligent responses
- **ExampleApp**: Default application implementation

### Debugging

The server includes extensive logging. Monitor the console output for:
- 🚀 Server initialization
- 🌐 WebSocket connections
- 🔄 Message processing
- 🔗 Kernel connections
- ❌ Error messages

## Performance

- Ray provides distributed computing capabilities
- WebSocket enables real-time communication
- uvloop (on Unix) improves async performance
- Graceful shutdown ensures proper resource cleanup

## Error Handling

The server handles various error conditions:
- Missing OpenAI API key
- WebSocket connection failures
- Kernel processing errors
- Graceful shutdown on signals

## Future Enhancements

- Support for additional LLM providers
- Plugin system for custom kernels
- Metrics and monitoring
- Distributed deployment across multiple machines
- Persistent state management 