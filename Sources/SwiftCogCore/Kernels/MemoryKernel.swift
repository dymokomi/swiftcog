import Foundation
import Distributed
import DistributedCluster

public distributed actor MemoryKernel: Kernel {
    let kernelId: KernelID

    public init(actorSystem: DefaultDistributedActorSystem) {
        self.actorSystem = actorSystem
        self.kernelId = KernelID()
    }

    public distributed func getKernelId() -> KernelID {
        return self.kernelId
    }

    public distributed func receive(message: KernelMessage) {
        // Not implemented yet
    }
} 