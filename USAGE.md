# SwiftCog Usage Guide

Complete guide for running SwiftCog with Ray, uvicorn, and the Swift GUI.

## Prerequisites

1. **Python Environment**: Python 3.8+
2. **Swift**: Swift 5.0+ (for macOS)
3. **OpenAI API Key**: Required for LLM functionality

## Quick Start

### 1. Set Up Environment

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-openai-api-key-here"

# Navigate to the project directory
cd /path/to/swiftcog
```

### 2. Start the Python Server

```bash
# Navigate to server directory
cd Sources/server

# Install dependencies and start server (recommended)
./start_server.sh
```

You should see output like:
```
🚀 Starting SwiftCog Python Server...
======================================
📦 Installing dependencies...
⚡ Starting Ray cluster...
🌐 Starting uvicorn server...
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
🚀 Starting SwiftCog Python Server...
⚡ Ray connected successfully!
🚀 Server initialized successfully!
💡 Connect SwiftCog GUI to ws://127.0.0.1:8000/ws
```

### 3. Launch GUI with Python App

In a new terminal:

```bash
# Navigate to GUI directory
cd Sources/SwiftCogGUI

# Run GUI with a specific Python app
swift run SwiftCogGUI --app Sources/Examples/Python/ExampleApp.py
```

## Available Python Apps

### 1. ExampleApp.py
Basic cognitive assistant with standard pipeline functionality.

```bash
swift run SwiftCogGUI --app Sources/Examples/Python/ExampleApp.py
```

**Features:**
- General conversation
- Standard cognitive pipeline
- Basic LLM integration

### 2. MathTutorApp.py
Specialized math tutoring assistant with step-by-step explanations.

```bash
swift run SwiftCogGUI --app Sources/Examples/Python/MathTutorApp.py
```

**Features:**
- Math keyword detection
- Step-by-step explanations
- Lower temperature for consistency
- Educational prompts

### 3. WeatherAssistantApp.py
Weather information and planning specialist.

```bash
swift run SwiftCogGUI --app Sources/Examples/Python/WeatherAssistantApp.py
```

**Features:**
- Weather forecasting focus
- Clothing recommendations
- Activity planning advice
- Meteorology explanations

## Testing and Debugging

### 1. Test App Loading (Without GUI)

```bash
cd Sources/server
python test_cli.py ../Examples/Python/ExampleApp.py
```

Expected output:
```
🧪 Testing app loading: ExampleApp.py
📁 App file: ../Examples/Python/ExampleApp.py
📝 App code length: 4832 characters
🔗 Connecting to ws://127.0.0.1:8000/ws
✅ Connected to WebSocket
📤 App loading message sent
📥 Response received: {"type":"appLoaded","app_name":"ExampleApp.py","success":true,"message":"App 'ExampleApp.py' loaded successfully"}
✅ App loaded successfully!
```

### 2. Monitor Components

**Ray Dashboard:**
```bash
open http://127.0.0.1:8265
```

**Server Health:**
```bash
curl http://127.0.0.1:8000/health
```

**API Documentation:**
```bash
open http://127.0.0.1:8000/docs
```

## Advanced Usage

### Manual Server Startup

If you prefer to start components separately:

```bash
# Terminal 1: Start Ray cluster
ray start --head --port=6379 --dashboard-port=8265 --include-dashboard

# Terminal 2: Start uvicorn server
cd Sources/server
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Terminal 3: Run GUI
cd Sources/SwiftCogGUI
swift run SwiftCogGUI --app Sources/Examples/Python/ExampleApp.py

# When done, stop Ray cluster
ray stop
```

### Custom App Development

Create your own Python app:

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
    APP_DESCRIPTION = "My custom cognitive app"
    
    def __init__(self, system: KernelSystem, llm_service: LLMService):
        self.system = system
        self.llm_service = llm_service
        self.sensing_kernel = None
        self.executive_kernel = None
        self.motor_kernel = None
        self.expression_kernel = None
    
    @classmethod
    async def init_backend(cls, system: KernelSystem):
        # Initialize your custom app
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        openai_provider = OpenAIProvider(api_key)
        llm_service = LLMService(openai_provider)
        app = cls(system, llm_service)
        
        # Create and connect kernels
        # ... your custom kernel setup
        
        return app
```

Then run it:
```bash
swift run SwiftCogGUI --app path/to/MyCustomApp.py
```

## Message Flow

1. **GUI Launch**: Swift GUI reads Python app file
2. **App Loading**: GUI sends app code to server via WebSocket
3. **Server Processing**: Server executes `init_backend()` and creates Ray actors
4. **Kernel Pipeline**: Ray actors process messages: Sensing → Executive → Motor → Expression
5. **Response**: Server sends responses back to GUI via WebSocket

## Architecture Overview

```
┌─────────────────┐     WebSocket     ┌─────────────────┐
│  Swift GUI      │◄─────────────────►│  FastAPI Server │
│  (Port 8000)    │   /ws endpoint    │  (uvicorn)      │
└─────────────────┘                   └─────────────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │  Ray Cluster    │
                                      │  (Port 6379)    │
                                      │                 │
                                      │  ┌─────────────┐│
                                      │  │ Kernels     ││
                                      │  │ (Ray Actors)││
                                      │  └─────────────┘│
                                      └─────────────────┘
```

## Troubleshooting

### Common Issues

1. **"Ray cluster not found"**
   - Make sure Ray is started: `ray start --head`
   - Check Ray status: `ray status`

2. **"OPENAI_API_KEY not set"**
   - Set environment variable: `export OPENAI_API_KEY="your-key"`

3. **"WebSocket connection failed"**
   - Ensure server is running on port 8000
   - Check server logs for errors

4. **"App file not found"**
   - Use absolute path or path relative to current directory
   - Check file exists: `ls -la Sources/Examples/Python/ExampleApp.py`

5. **"exec() arg 1 must be a string, bytes or code object"**
   - This was fixed in recent updates - make sure Swift GUI uses snake_case JSON keys
   - Update to latest version of both GUI and server

6. **"App loading failed: No app code provided"**
   - Check that the Python app file exists and is readable
   - Verify the command line argument: `--app Sources/Examples/Python/ExampleApp.py`

7. **Ray serialization errors ("cannot pickle '_thread.RLock' object")**
   - This was fixed by moving LLM service creation inside Ray actors
   - Update to latest version where handlers create their own LLM services

### Testing Without GUI

You can test the server communication without the GUI:

```bash
cd Sources/server
python test_swift_format.py
```

This will test the complete app loading and message exchange workflow.

### Server Logs

Monitor server output for detailed debugging:
```
🌐 GUI connected via WebSocket
📝 Loading app: ExampleApp.py
✅ App 'ExampleApp.py' loaded successfully
🔄 KernelSystem.handle_message() - Message: sensing-interface -> 'Hello'
📥 Backend routing message to SensingKernel
```

## Performance Tips

1. **Ray Dashboard**: Monitor actor performance at `http://127.0.0.1:8265`
2. **Uvicorn Reload**: Use `--reload` flag for development
3. **LLM Temperature**: Adjust temperature in custom apps for different response styles
4. **Token Limits**: Set appropriate max_tokens for your use case

## Next Steps

1. Create custom Python apps for specialized use cases
2. Experiment with different kernel configurations
3. Monitor Ray cluster performance and scaling
4. Integrate additional LLM providers
5. Add custom display commands for enhanced UI 