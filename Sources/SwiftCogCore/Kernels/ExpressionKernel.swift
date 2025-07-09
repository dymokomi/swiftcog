import Foundation
import Distributed
import DistributedCluster

public distributed actor ExpressionKernel: Kernel {
    let kernelId: KernelID
    unowned let system: KernelSystem
    private let customHandler: ((KernelMessage, ExpressionKernel) async throws -> Void)?
    
    public init(actorSystem: DefaultDistributedActorSystem, system: KernelSystem, customHandler: ((KernelMessage, ExpressionKernel) async throws -> Void)? = nil) {
        self.actorSystem = actorSystem
        self.kernelId = KernelID()
        self.system = system
        self.customHandler = customHandler
    }

    public distributed func getKernelId() -> KernelID {
        return self.kernelId
    }

    public distributed func receive(message: KernelMessage) {
        if let customHandler = customHandler {
            Task {
                // Use the custom handler if provided
                try await customHandler(message, self)
            }
        } else {
            // Default behavior: print the message
            print("ExpressionKernel received: \(message.payload)")
        }
    }
} 