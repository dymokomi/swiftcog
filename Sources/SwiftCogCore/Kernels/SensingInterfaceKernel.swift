import Foundation
import OpenAIKit

public class SensingInterfaceKernel: Kernel {
    private let system: KernelSystem
    private let speechEngine: SpeechToTextEngine
    private let customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)?
    private let kernelId = KernelID.sensingInterface

    public init(system: KernelSystem, apiKey: String, customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)? = nil) {
        self.system = system
        self.speechEngine = SpeechToTextEngine(apiKey: apiKey)
        self.customHandler = customHandler
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        print("🎙️ SensingInterfaceKernel (Frontend) received message: '\(message.payload)'")
        
        if let customHandler = customHandler {
            try await customHandler(message, self)
        } else {
            // Default: Display the response from backend
            print("🗣️ Response from backend: \(message.payload)")
        }
    }
    
    public func startSensing() async throws {
        print("🎙️ SensingInterfaceKernel (Frontend): Starting speech recognition...")
        
        for try await speechText in speechEngine.start() {
            await processSpeechInput(speechText)
        }
    }
    
    private func processSpeechInput(_ speechText: String) async {
        print("🎤 Frontend captured speech: '\(speechText)'")
        
        let message = KernelMessage(
            id: UUID(),
            sourceKernelId: .sensingInterface,
            payload: speechText
        )
        
        // Send to backend via HTTP
        do {
            try await system.emit(message: message, from: self)
        } catch {
            print("❌ Failed to send speech to backend: \(error)")
        }
    }
} 