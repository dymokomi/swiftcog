import Foundation
import Distributed
import DistributedCluster

public distributed actor MotorKernel: Kernel {
    let kernelId: KernelID
    unowned let system: KernelSystem
    private let customHandler: ((KernelMessage, MotorKernel) async throws -> Void)?

    public init(actorSystem: DefaultDistributedActorSystem, system: KernelSystem, customHandler: ((KernelMessage, MotorKernel) async throws -> Void)? = nil) {
        self.actorSystem = actorSystem
        self.kernelId = KernelID()
        self.system = system
        self.customHandler = customHandler
    }

    public distributed func getKernelId() -> KernelID {
        return self.kernelId
    }

    public distributed func receive(message: KernelMessage) {
        Task {
            if let customHandler = customHandler {
                // Use the custom handler if provided
                try await customHandler(message, self)
            } else {
                // Default behavior: pass the message on
                try await system.emit(message: message, from: self)
            }
        }
    }
} 