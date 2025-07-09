import Foundation

public class LearningKernel: Kernel {
    private let kernelId = KernelID.learning

    public init() {
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        // Not implemented yet
        print("📚 LearningKernel received message: '\(message.payload)'")
    }
} 