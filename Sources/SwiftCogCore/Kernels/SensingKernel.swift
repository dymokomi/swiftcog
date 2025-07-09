import Foundation

public class SensingKernel: Kernel {
    private let system: KernelSystem
    private let apiKey: String
    private let customHandler: ((KernelMessage, SensingKernel) async throws -> Void)?
    private let kernelId = KernelID.sensing

    public init(system: KernelSystem, apiKey: String, customHandler: ((KernelMessage, SensingKernel) async throws -> Void)? = nil) {
        self.system = system
        self.apiKey = apiKey
        self.customHandler = customHandler
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        // Backend sensing: Just processes the message without speech recognition
        if let customHandler = customHandler {
            try await customHandler(message, self)
        } else {
            try await defaultHandler(message: message)
        }
    }
    
    private func defaultHandler(message: KernelMessage) async throws {
        // Create a response based on the input
        let response = KernelMessage(
            id: UUID(),
            sourceKernelId: .sensing,
            payload: "Cognitive processing complete for: '\(message.payload)'"
        )
        
        // Emit to the kernel system for routing
        try await system.emit(message: response, from: self)
    }
} 