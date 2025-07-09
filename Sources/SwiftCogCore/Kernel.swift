import Distributed
import DistributedCluster

public typealias DefaultDistributedActorSystem = ClusterSystem

public protocol Kernel: DistributedActor where ActorSystem == DefaultDistributedActorSystem {
    distributed func getKernelId() -> KernelID
    distributed func receive(message: KernelMessage)
} 