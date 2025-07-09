# Frontend/Backend Architecture Demo

This document demonstrates the new frontend/backend separation architecture in SwiftCog with clean functional separation.

## Architecture Overview

The SwiftCog system now supports running as two separate processes with distinct initialization:

1. **Backend**: Runs the core cognitive kernels (SensingKernel, ExecutiveKernel, MotorKernel, ExpressionKernel)
2. **Frontend**: Runs interface kernels (SensingInterfaceKernel, ExpressionInterfaceKernel) that connect to the backend

## How to Use

### 1. Start the Backend Server

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your_openai_api_key_here"

# Start the backend server (runs continuously)
swift run SwiftCog run ExampleApp --mode backend
```

**Expected Output:**
```
Loading app by name: ExampleApp
ExampleApp: Initializing backend kernels...
ExampleApp: Backend kernel pipeline established
SwiftCog system starting with app: ExampleApp in backend mode...
KernelSystem running in backend mode...
Backend mode: 1 SensingKernel(s) ready to receive messages from frontend
Backend server running... Press Ctrl+C to stop.
```

The backend will:
- Initialize all core kernels (Sensing, Executive, Motor, Expression) 
- Set up the cognitive processing pipeline
- **Run continuously as a server** (no immediate shutdown)
- Listen for connections from frontend clients
- Process messages received from frontend and generate AI responses
- Shut down gracefully with Ctrl+C

### 2. Start the Frontend Client (In Another Terminal)

```bash
# Set your OpenAI API key (needed for speech recognition)
export OPENAI_API_KEY="your_openai_api_key_here"

# Start the frontend client
swift run SwiftCog run ExampleApp --mode frontend
```

**Expected Output:**
```
Loading app by name: ExampleApp
ExampleApp: Initializing frontend interface kernels...
ExampleApp: Frontend interface kernels created
SwiftCog system starting with app: ExampleApp in frontend mode...
KernelSystem running in frontend mode...
Frontend mode: Starting speech recognition in 1 SensingInterfaceKernel(s)
Frontend client running...
SensingInterfaceKernel: Starting speech recognition...
SpeechToTextEngine: Connecting to OpenAI Realtime API...
```

The frontend will:
- Initialize interface kernels for speech input and expression output
- Connect to the backend server via distributed actors
- **Handle ALL speech recognition** and send transcriptions to backend
- Display AI responses received from the backend

## Key Architectural Changes

### 1. Clean Functional Separation
- **No Mode Checking**: Applications no longer check modes internally
- **Distinct Initialization**: Separate `initBackend()` and `initFrontend()` static methods
- **Clear Responsibilities**: Backend handles cognition, frontend handles interface
- **Speech Recognition Separation**: Only frontend does speech recognition, backend only receives messages

### 2. SwiftCogApp Protocol
```swift
public protocol SwiftCogApp: AnyObject {
    /// Initialize for backend mode with core cognitive kernels
    static func initBackend(system: KernelSystem) async throws -> Self
    
    /// Initialize for frontend mode with interface kernels  
    static func initFrontend(system: KernelSystem) async throws -> Self
}
```

### 3. Kernel Responsibilities

**Backend Kernels:**
- `SensingKernel`: Pure message receiver (NO speech recognition)
- `ExecutiveKernel`: LLM processing and decision making
- `MotorKernel`: Action processing and routing
- `ExpressionKernel`: Output generation

**Frontend Interface Kernels:**
- `SensingInterfaceKernel`: Speech recognition and input to backend
- `ExpressionInterfaceKernel`: Output display and UI interaction

### 4. Separate App Factories
- `AppRegistry.createBackendApp()`: Creates backend instances
- `AppRegistry.createFrontendApp()`: Creates frontend instances
- `AppLoader.loadBackendApp()` / `AppLoader.loadFrontendApp()`: Mode-specific loading

### 5. KernelSystem Design
- Knows its mode but doesn't check it in operations
- Provides all kernel creation methods
- Applications only call relevant methods for their mode
- Clean separation without internal mode branching

### 6. Example Implementation

**Backend Mode (ExampleApp.initBackend):**
```swift
// Creates: SensingKernel → ExecutiveKernel → MotorKernel → ExpressionKernel
// SensingKernel: Only receives messages from frontend (no speech recognition)
// ExecutiveKernel: LLM processing pipeline
// MotorKernel & ExpressionKernel: Processing and output generation
```

**Frontend Mode (ExampleApp.initFrontend):**
```swift
// Creates: SensingInterfaceKernel, ExpressionInterfaceKernel
// SensingInterfaceKernel: Does ALL speech recognition
// ExpressionInterfaceKernel: Handles UI output display
// Connects to backend for cognitive processing
```

## Distributed Actor System

The system uses Swift 6's distributed actors with different configurations:

- **Backend**: Listens on port 7354 for incoming connections
- **Frontend**: Connects to backend on port 7355

This allows for true distributed processing where the UI runs separately from the core cognitive processing.

## Benefits of Clean Separation

1. **No Internal Mode Checks**: Functions don't need to determine their environment
2. **Clear API Surface**: Backend and frontend have distinct initialization paths
3. **Better Testing**: Each mode can be tested independently
4. **Easier Development**: No ambiguity about which kernels are available
5. **Type Safety**: Compile-time guarantees about kernel availability
6. **Scalability**: Easy to extend with new modes or kernel types

## Future Enhancements

1. **Service Discovery**: Automatic discovery of backend services
2. **Multiple Frontends**: Support for multiple UI clients connecting to one backend
3. **Load Balancing**: Distribute processing across multiple backend instances
4. **Real-time Updates**: Live streaming of cognitive state to frontend
5. **Web Interface**: Browser-based frontend using WebSocket connections

## Testing the Architecture

You can test both modes independently:

```bash
# Test backend mode only
swift run SwiftCog run ExampleApp --mode backend

# Test frontend mode only  
swift run SwiftCog run ExampleApp --mode frontend

# Test with different apps
swift run SwiftCog run YourCustomApp --mode frontend
```

## Implementation Pattern for New Apps

When creating a new SwiftCog app, implement both static methods:

```swift
public class MyApp: SwiftCogApp {
    static func initBackend(system: KernelSystem) async throws -> Self {
        // Create cognitive kernels and processing pipeline
        // Focus on AI/LLM processing and decision making
    }
    
    static func initFrontend(system: KernelSystem) async throws -> Self {
        // Create interface kernels for user interaction
        // Focus on speech recognition, UI display, user input
    }
}
```

This separation enables more flexible deployment scenarios, better scalability, and cleaner separation of concerns between UI and cognitive processing with no internal mode checking required.

## Troubleshooting

### Backend Shuts Down Immediately

**Problem:** Backend mode exits with "All work complete, shutting down" right after starting.

**Cause:** Backend SensingKernels are now passive message receivers (no active tasks), so the main loop thinks work is complete.

**Solution:** ✅ **Fixed** - Backend now runs as a persistent server with proper signal handling:
- Uses `withCheckedThrowingContinuation` to keep server running indefinitely
- Responds to Ctrl+C (SIGINT) for graceful shutdown
- No longer depends on active sensing tasks

### Frontend vs Backend Speech Recognition

**Expected Behavior:**
- ✅ **Frontend Mode**: Shows "Starting speech recognition", connects to OpenAI Realtime API
- ✅ **Backend Mode**: Shows "SensingKernel(s) ready to receive messages" (no speech recognition)

**Verification:**
```bash
# Backend should NOT show speech recognition
swift run SwiftCog --mode backend
# Should show: "Backend server running... Press Ctrl+C to stop."

# Frontend should show speech recognition  
swift run SwiftCog --mode frontend
# Should show: "SensingInterfaceKernel: Starting speech recognition..."
``` 