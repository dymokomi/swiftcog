# SwiftCog App Loading System

SwiftCog now supports dynamic app loading, allowing you to create and run multiple cognitive architecture applications.

## Usage

### Running Apps

```bash
# Run without specifying an app (lists available apps and loads ExampleApp as default)
swift run SwiftCog run --api-key YOUR_API_KEY

# Run a specific app by name
swift run SwiftCog run ExampleApp --api-key YOUR_API_KEY
swift run SwiftCog run SimpleApp --api-key YOUR_API_KEY

# Run an app from a directory path (future enhancement)
swift run SwiftCog run /path/to/app/directory --api-key YOUR_API_KEY
```

### Available Apps

Currently available example apps:
- **ExampleApp**: A comprehensive cognitive architecture with all kernel types (Sensing, Executive, Motor, Expression)
- **SimpleApp**: A minimal implementation with just Executive and Expression kernels

## Creating New Apps

### 1. Create App Directory Structure

```bash
mkdir -p Sources/Examples/YourApp
```

### 2. Create Your App Class

Create `Sources/Examples/YourApp/YourApp.swift`:

```swift
import Foundation
import SwiftCogCore
import Distributed

public class YourApp: SwiftCogApp {
    public static let appName = "YourApp"
    public static let appDescription = "Description of your app"
    
    let system: KernelSystem
    // Add your kernels here
    
    public required init(system: KernelSystem) async throws {
        self.system = system
        
        // Initialize your kernels and connect them
        // See ExampleApp or SimpleApp for examples
    }
}

// Register the app
extension YourApp {
    public static func register() {
        AppRegistry.register(name: appName, type: YourApp.self)
    }
}
```

### 3. Register Your App

Add your app to `Sources/Examples/Examples.swift`:

```swift
public static func initialize() {
    ExampleApp.register()
    SimpleApp.register()
    YourApp.register()  // Add this line
}

public static var availableApps: [String] {
    return ["ExampleApp", "SimpleApp", "YourApp"]  // Add your app name
}
```

### 4. Build and Run

```bash
swift build
swift run SwiftCog run YourApp --api-key YOUR_API_KEY
```

## App Structure

All apps must:
1. Conform to the `SwiftCogApp` protocol
2. Implement the required initializer: `init(system: KernelSystem) async throws`
3. Provide `appName` and `appDescription` static properties
4. Register themselves with the `AppRegistry`

## Directory Organization

```
Sources/
├── SwiftCogCore/          # Core framework
├── SwiftCog/              # Main executable
└── Examples/              # Example applications
    ├── Examples.swift     # App registry initialization
    ├── ExampleApp/        # Full-featured example
    │   └── ExampleApp.swift
    └── SimpleApp/         # Minimal example
        └── SimpleApp.swift
```

## Benefits

- **Modular**: Each app is self-contained
- **Discoverable**: Apps are automatically listed when running without arguments
- **Type-safe**: Apps are registered at compile time
- **Extensible**: Easy to add new apps without modifying core code
- **Testable**: Each app can be tested independently 