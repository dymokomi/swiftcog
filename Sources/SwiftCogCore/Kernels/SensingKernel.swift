import Foundation
import Distributed
import DistributedCluster

public distributed actor SensingKernel: Kernel {
    let kernelId: KernelID
    unowned let system: KernelSystem
    private let speechEngine: SpeechToTextEngine
    private let customHandler: ((KernelMessage, SensingKernel) async throws -> Void)?

    public init(actorSystem: DefaultDistributedActorSystem, system: KernelSystem, apiKey: String, customHandler: ((KernelMessage, SensingKernel) async throws -> Void)? = nil) {
        self.actorSystem = actorSystem
        self.kernelId = KernelID()
        self.system = system
        self.speechEngine = SpeechToTextEngine(apiKey: apiKey)
        self.customHandler = customHandler
    }

    public distributed func getKernelId() -> KernelID {
        return self.kernelId
    }

    public distributed func startSensing() async throws {
        print("SensingKernel: Starting speech recognition...")
        for try await transcribedText in speechEngine.start() {
            print("SensingKernel: sending '\(transcribedText)'")
            let message = KernelMessage(source: self.kernelId, destination: nil, payload: transcribedText)
            try await self.system.emit(message: message, from: self)
        }
    }

    public distributed func receive(message: KernelMessage) {
        if let customHandler = customHandler {
            Task {
                // Use the custom handler if provided
                try await customHandler(message, self)
            }
        } else {
            // Default behavior: A sensing kernel might not need to receive messages in this simple scenario
        }
    }
} 