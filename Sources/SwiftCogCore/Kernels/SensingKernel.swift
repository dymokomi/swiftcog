import Foundation
import Distributed
import DistributedCluster

public distributed actor SensingKernel: Kernel {
    let kernelId: KernelID
    unowned let system: KernelSystem
    private let speechEngine: SpeechToTextEngine

    public init(actorSystem: DefaultDistributedActorSystem, system: KernelSystem, apiKey: String) {
        self.actorSystem = actorSystem
        self.kernelId = KernelID()
        self.system = system
        self.speechEngine = SpeechToTextEngine(apiKey: apiKey)
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
        // A sensing kernel might not need to receive messages in this simple scenario
    }
} 