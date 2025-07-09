import Foundation
import OpenAIKit

public class SensingInterfaceKernel: Kernel {
    private let system: KernelSystem
    private let speechEngine: SpeechToTextEngine
    private let customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)?
    private let speechInputCallback: ((String) -> Void)?
    private let kernelId = KernelID.sensingInterface

    public init(system: KernelSystem, apiKey: String, customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)? = nil, speechInputCallback: ((String) -> Void)? = nil) {
        self.system = system
        self.speechEngine = SpeechToTextEngine(apiKey: apiKey)
        self.customHandler = customHandler
        self.speechInputCallback = speechInputCallback
    }

    public func getKernelId() -> KernelID {
        return kernelId
    }

    public func receive(message: KernelMessage) async throws {
        if let customHandler = customHandler {
            try await customHandler(message, self)
        } else {
            // Default: Display the response from backend
            print("Response from backend: \(message.payload)")
        }
    }
    
    public func startSensing() async throws {
        print("SensingInterfaceKernel: Starting speech recognition")
        
        for try await speechText in speechEngine.start() {
            await processSpeechInput(speechText)
        }
    }
    
    private func processSpeechInput(_ speechText: String) async {
        print("Frontend captured speech: '\(speechText)'")
        
        // Notify the UI about the speech input first
        speechInputCallback?(speechText)
        
        // Message sending is handled by the UI callback
        // The speechInputCallback will trigger the UI to send the message to backend
    }
} 