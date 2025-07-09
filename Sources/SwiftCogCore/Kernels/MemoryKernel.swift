import Foundation

public class MemoryKernel: Kernel {
    private let kernelId = KernelID.memory

    public init() {
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        // Not implemented yet
        print("MemoryKernel received message: '\(message.payload)'")
    }
} 