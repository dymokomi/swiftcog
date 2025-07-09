import Foundation

public class ExecutiveKernel: Kernel {
    private let system: KernelSystem
    private let customHandler: ((KernelMessage, ExecutiveKernel) async throws -> Void)?
    private let kernelId = KernelID.executive

    public init(system: KernelSystem, customHandler: ((KernelMessage, ExecutiveKernel) async throws -> Void)? = nil) {
        self.system = system
        self.customHandler = customHandler
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        print("🧠 ExecutiveKernel (Backend) received message: '\(message.payload)'")
        
        if let customHandler = customHandler {
            try await customHandler(message, self)
        } else {
            try await defaultHandler(message: message)
        }
    }
    
    private func defaultHandler(message: KernelMessage) async throws {
        // Backend executive: Process with decision making and forward
        let response = KernelMessage(
            id: UUID(),
            sourceKernelId: .executive,
            payload: "Executive decision made for: '\(message.payload)'"
        )
        
        try await system.emit(message: response, from: self)
    }
} 