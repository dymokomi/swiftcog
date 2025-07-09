import Foundation

public class ExpressionKernel: Kernel {
    private let system: KernelSystem
    private let customHandler: ((KernelMessage, ExpressionKernel) async throws -> Void)?
    private let kernelId = KernelID.expression

    public init(system: KernelSystem, customHandler: ((KernelMessage, ExpressionKernel) async throws -> Void)? = nil) {
        self.system = system
        self.customHandler = customHandler
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        print("🗣️ ExpressionKernel (Backend) received message: '\(message.payload)'")
        
        if let customHandler = customHandler {
            try await customHandler(message, self)
        } else {
            try await defaultHandler(message: message)
        }
    }
    
    private func defaultHandler(message: KernelMessage) async throws {
        // Backend expression: Format the message for output
        let formattedMessage = KernelMessage(
            id: UUID(),
            sourceKernelId: .expression,
            payload: "🧠 SwiftCog Response: \(message.payload)"
        )
        
        // This will trigger sending to frontend via WebSocket
        try await system.emit(message: formattedMessage, from: self)
    }
} 