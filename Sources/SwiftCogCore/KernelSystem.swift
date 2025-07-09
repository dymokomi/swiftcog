import Foundation
import Distributed
import DistributedCluster

public class KernelSystem {
    public let actorSystem: DefaultDistributedActorSystem
    private var kernels: [KernelID: any Kernel] = [:]
    private var sensingKernels: [SensingKernel] = []
    private var connections: [KernelID: KernelID] = [:]
    private let apiKey: String

    public init(apiKey: String) async {
        self.apiKey = apiKey
        self.actorSystem = await ClusterSystem("KernelSystem") { settings in
            settings.logging.logLevel = .warning
        }
    }

    public func createExpressionKernel() async throws -> ExpressionKernel {
        let kernel = ExpressionKernel(actorSystem: actorSystem, system: self)
        let kernelId = try await kernel.getKernelId()
        kernels[kernelId] = kernel
        return kernel
    }

    public func createMotorKernel() async throws -> MotorKernel {
        let kernel = MotorKernel(actorSystem: actorSystem, system: self)
        let kernelId = try await kernel.getKernelId()
        kernels[kernelId] = kernel
        return kernel
    }

    public func createExecutiveKernel() async throws -> ExecutiveKernel {
        let kernel = ExecutiveKernel(actorSystem: actorSystem, system: self)
        let kernelId = try await kernel.getKernelId()
        kernels[kernelId] = kernel
        return kernel
    }

    public func createSensingKernel() async throws -> SensingKernel {
        let kernel = SensingKernel(actorSystem: actorSystem, system: self, apiKey: apiKey)
        let kernelId = try await kernel.getKernelId()
        kernels[kernelId] = kernel
        sensingKernels.append(kernel)
        return kernel
    }
    
    public func connect(from source: any Kernel, to destination: any Kernel) async throws {
        let sourceId = try await source.getKernelId()
        let destinationId = try await destination.getKernelId()
        connections[sourceId] = destinationId
    }

    public func emit(message: KernelMessage, from emitter: any Kernel) async throws {
        let emitterId = try await emitter.getKernelId()
        if let destinationId = connections[emitterId],
           let destinationKernel = kernels[destinationId] {
            // Forward the original message
            try await destinationKernel.receive(message: message)
        } else {
            // It's not necessarily an error to have no connection,
            // e.g., for a kernel that is a sink.
        }
    }

    @discardableResult
    public func run() -> [Task<Void, Error>] {
        print("KernelSystem running...")
        var tasks: [Task<Void, Error>] = []
        for sensingKernel in sensingKernels {
            let task = Task.detached {
                do {
                    try await sensingKernel.startSensing()
                } catch {
                    print("SensingKernel failed with error: \(error)")
                    throw error
                }
            }
            tasks.append(task)
        }
        return tasks
    }
} 