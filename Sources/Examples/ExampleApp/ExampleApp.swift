import Foundation
import SwiftCogCore
import Distributed

public class ExampleApp: SwiftCogApp {
    public static let appName = "ExampleApp"
    public static let appDescription = "A simple example cognitive architecture application"
    
    let system: KernelSystem
    let sensingKernel: SensingKernel
    let executiveKernel: ExecutiveKernel
    let motorKernel: MotorKernel
    let expressionKernel: ExpressionKernel
    let llmService: LLMService

    public required init(system: KernelSystem) async throws {
        self.system = system
        
        // Initialize LLM Service with OpenAI Provider
        // You should set your API key as an environment variable: OPENAI_API_KEY
        guard let apiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] else {
            throw NSError(domain: "ExampleApp", code: 1, userInfo: [NSLocalizedDescriptionKey: "OPENAI_API_KEY environment variable not set"])
        }
        let openAIProvider = OpenAIProvider(apiKey: apiKey)
        self.llmService = LLMService(provider: openAIProvider)
        
        // Create SensingKernel (no custom handler needed for now)
        self.sensingKernel = try await system.createSensingKernel()
        
        // Create ExpressionKernel with custom handler
        self.expressionKernel = try await system.createExpressionKernel { message, kernel in
            print("Custom ExpressionKernel handler: \(message.payload)")
        }
        
        // Create MotorKernel with custom handler
        self.motorKernel = try await system.createMotorKernel { message, kernel in
            print("Custom MotorKernel handler: Processing \(message.payload)")
            try await system.emit(message: message, from: kernel)
        }
        
        // Create ExecutiveKernel with custom handler that calls LLM
        self.executiveKernel = try await system.createExecutiveKernel { [llmService = self.llmService] message, kernel in
            do {
                // Define custom system prompt for the executive decision-making
                let systemPrompt = """
                You are an executive decision-making system in a cognitive architecture. 
                Your role is to analyze input and provide intelligent decisions or responses.
                Be concise, practical, and actionable in your responses.
                Focus on the key insights and next steps.
                """
                // Use the LLM service to process the message
                let aiResponse = try await llmService.processMessage(
                    message.payload,
                    systemPrompt: systemPrompt,
                    temperature: 0.7,
                    maxTokens: 500
                )
                // Create a new message with the AI-processed content
                let processedMessage = KernelMessage(
                    source: message.source,
                    destination: message.destination,
                    payload: aiResponse
                )
                
                // Emit the AI-processed message to the next kernel
                try await system.emit(message: processedMessage, from: kernel)
                
            } catch {
                print("Error calling LLM: \(error.localizedDescription)")
                // If LLM fails, pass through the original message
                try await system.emit(message: message, from: kernel)
            }
        }
        
        // Explicitly connect the kernels to form the pipeline
        try await system.connect(from: self.sensingKernel, to: self.executiveKernel)
        try await system.connect(from: self.executiveKernel, to: self.motorKernel)
        try await system.connect(from: self.motorKernel, to: self.expressionKernel)
    }
}

// Register the app with the registry
extension ExampleApp {
    public static func register() {
        AppRegistry.register(name: appName, type: ExampleApp.self)
    }
}