import Foundation

public class MotorKernel: Kernel {
    private let system: KernelSystem
    private let customHandler: ((KernelMessage, MotorKernel) async throws -> Void)?
    private let kernelId = KernelID.motor

    public init(system: KernelSystem, customHandler: ((KernelMessage, MotorKernel) async throws -> Void)? = nil) {
        self.system = system
        self.customHandler = customHandler
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        if let customHandler = customHandler {
            try await customHandler(message, self)
        } else {
            try await defaultHandler(message: message)
        }
    }
    
    private func defaultHandler(message: KernelMessage) async throws {
        // Backend motor: Execute actions and forward response
        let response = KernelMessage(
            id: UUID(),
            sourceKernelId: .motor,
            payload: "Motor action executed for: '\(message.payload)'"
        )
        
        try await system.emit(message: response, from: self)
    }
} 