import Foundation
import SwiftCogCore
import Distributed

public class ExampleApp {
    let system: KernelSystem
    let sensingKernel: SensingKernel
    let executiveKernel: ExecutiveKernel
    let motorKernel: MotorKernel
    let expressionKernel: ExpressionKernel

    public required init(system: KernelSystem) async throws {
        self.system = system
        self.expressionKernel = try await system.createExpressionKernel()
        self.motorKernel = try await system.createMotorKernel()
        self.executiveKernel = try await system.createExecutiveKernel()
        self.sensingKernel = try await system.createSensingKernel()
        
        // Explicitly connect the kernels to form the pipeline
        try await system.connect(from: self.sensingKernel, to: self.executiveKernel)
        try await system.connect(from: self.executiveKernel, to: self.motorKernel)
        try await system.connect(from: self.motorKernel, to: self.expressionKernel)
    }
} 