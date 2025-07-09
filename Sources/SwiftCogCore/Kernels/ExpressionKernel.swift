import Foundation
import Distributed
import DistributedCluster

public distributed actor ExpressionKernel: Kernel {
    let kernelId: KernelID
    unowned let system: KernelSystem
    
    public init(actorSystem: DefaultDistributedActorSystem, system: KernelSystem) {
        self.actorSystem = actorSystem
        self.kernelId = KernelID()
        self.system = system
    }

    public distributed func getKernelId() -> KernelID {
        return self.kernelId
    }

    public distributed func receive(message: KernelMessage) {
        print("ExpressionKernel received: \(message.payload)")
    }
} 