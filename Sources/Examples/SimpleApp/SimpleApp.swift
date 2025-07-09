import Foundation
import SwiftCogCore
import Distributed

public class SimpleApp: SwiftCogApp {
    public static let appName = "SimpleApp"
    public static let appDescription = "A minimal cognitive architecture application for testing"
    
    let system: KernelSystem
    let executiveKernel: ExecutiveKernel
    let expressionKernel: ExpressionKernel

    public required init(system: KernelSystem) async throws {
        self.system = system
        
        // Create a simple architecture with just Executive and Expression kernels
        self.executiveKernel = try await system.createExecutiveKernel { message, kernel in
            print("🧠 SimpleApp Executive: Received \(message.payload)")
            
            // Simple decision: echo the message back
            let response = KernelMessage(
                source: message.source,
                destination: message.destination,
                payload: "SimpleApp processed: \(message.payload)"
            )
            try await system.emit(message: response, from: kernel)
        }
        
        self.expressionKernel = try await system.createExpressionKernel { message, kernel in
            print("💬 SimpleApp Expression: \(message.payload)")
        }
        
        // Connect executive to expression
        try await system.connect(from: self.executiveKernel, to: self.expressionKernel)
        
        // Send an initial test message
        let testMessage = KernelMessage(
            source: nil,
            destination: nil,
            payload: "Hello from SimpleApp!"
        )
        try await system.emit(message: testMessage, from: self.executiveKernel)
    }
}

// Register the app with the registry
extension SimpleApp {
    public static func register() {
        AppRegistry.register(name: appName, type: SimpleApp.self)
    }
} 