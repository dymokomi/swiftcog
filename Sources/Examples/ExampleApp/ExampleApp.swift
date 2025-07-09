import Foundation
import SwiftCogCore
import Distributed

public class ExampleApp: SwiftCogApp {
    public static let appName = "ExampleApp"
    public static let appDescription = "A simple example cognitive architecture application"
    
    let system: KernelSystem
    let sensingKernel: SensingKernel
    let executiveKernel: ExecutiveKernel
    let motorKernel: MotorKernel
    let expressionKernel: ExpressionKernel

    public required init(system: KernelSystem) async throws {
        self.system = system
        
        // Create ExpressionKernel with custom handler
        self.expressionKernel = try await system.createExpressionKernel { message, kernel in
            print("🎯 Custom ExpressionKernel handler: \(message.payload)")
            // Add your custom expression logic here
            // For example, you could format the output differently or send to external systems
        }
        
        // Create MotorKernel with custom handler
        self.motorKernel = try await system.createMotorKernel { message, kernel in
            print("🚀 Custom MotorKernel handler: Processing \(message.payload)")
            // Add your custom motor logic here
            // For example, you could control physical actuators or send commands
            
            // Still emit the message to the next kernel in the pipeline
            try await system.emit(message: message, from: kernel)
        }
        
        // Create ExecutiveKernel with custom handler
        self.executiveKernel = try await system.createExecutiveKernel { message, kernel in
            print("🧠 Custom ExecutiveKernel handler: Deciding on \(message.payload)")
            // Add your custom executive logic here
            // For example, you could implement decision-making algorithms
            
            // Process the message and potentially modify it before passing on
            let processedMessage = KernelMessage(
                source: message.source,
                destination: message.destination,
                payload: "Processed: \(message.payload)"
            )
            try await system.emit(message: processedMessage, from: kernel)
        }
        
        // Create SensingKernel (no custom handler needed for now)
        self.sensingKernel = try await system.createSensingKernel()
        
        // Explicitly connect the kernels to form the pipeline
        try await system.connect(from: self.sensingKernel, to: self.executiveKernel)
        try await system.connect(from: self.executiveKernel, to: self.motorKernel)
        try await system.connect(from: self.motorKernel, to: self.expressionKernel)
    }
}

// Register the app with the registry
extension ExampleApp {
    public static func register() {
        AppRegistry.register(name: appName, type: ExampleApp.self)
    }
}