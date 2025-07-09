import Foundation

public class ExpressionInterfaceKernel: Kernel {
    private let system: KernelSystem
    private let customHandler: ((KernelMessage, ExpressionInterfaceKernel) async throws -> Void)?
    private let kernelId = KernelID.expressionInterface

    public init(system: KernelSystem, customHandler: ((KernelMessage, ExpressionInterfaceKernel) async throws -> Void)? = nil) {
        self.system = system
        self.customHandler = customHandler
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        print("📺 ExpressionInterfaceKernel (Frontend) received message: '\(message.payload)'")
        
        if let customHandler = customHandler {
            try await customHandler(message, self)
        } else {
            try await defaultHandler(message: message)
        }
    }
    
    private func defaultHandler(message: KernelMessage) async throws {
        // Frontend expression interface: Display the message from backend
        print("💬 Displaying to user: \(message.payload)")
        
        // Could also trigger UI updates, text-to-speech, etc.
        // For now, just print the response
    }
} 