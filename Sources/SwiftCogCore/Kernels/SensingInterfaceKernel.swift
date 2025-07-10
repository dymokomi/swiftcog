import Foundation
import OpenAIKit

public class SensingInterfaceKernel: Kernel {
    private let system: MessageSystem
    private let customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)?
    private let kernelId = KernelID.sensingInterface

    public init(system: MessageSystem, customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)? = nil) {
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
            // Default: Display the response from backend
            print("Response from backend: \(message.payload)")
        }
    }
} 