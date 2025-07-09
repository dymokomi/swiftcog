import Foundation
import SwiftCogCore

public class ExampleApp {
    public static let appName = "ExampleApp"
    public static let appDescription = "A simple example cognitive architecture application"
    
    public var system: KernelSystem
    public var llmService: LLMService
    
    // Backend kernels only
    private var sensingKernel: SensingKernel?
    private var executiveKernel: ExecutiveKernel?
    private var motorKernel: MotorKernel?
    private var expressionKernel: ExpressionKernel?

    private init(system: KernelSystem, llmService: LLMService) {
        self.system = system
        self.llmService = llmService
    }

    /// Initialize ExampleApp for backend mode with core cognitive kernels
    public static func initBackend(system: KernelSystem) async throws -> Self {
        guard let apiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] else {
            throw NSError(domain: "ExampleApp", code: 1, userInfo: [NSLocalizedDescriptionKey: "OPENAI_API_KEY environment variable not set"])
        }
        
        let openAIProvider = OpenAIProvider(apiKey: apiKey)
        let llmService = LLMService(provider: openAIProvider)
        let app = ExampleApp(system: system, llmService: llmService)
        
        print("ExampleApp: Initializing backend kernels...")
        
        // Create SensingKernel (no custom handler needed - will be connected from frontend)
        app.sensingKernel = try await system.createSensingKernel()
        
        // Create ExpressionKernel with custom handler that sends back to frontend
        app.expressionKernel = try await system.createExpressionKernel { message, kernel in
            print("Backend ExpressionKernel: \(message.payload)")
            
            // Format the message for frontend display
            let formattedMessage = KernelMessage(
                sourceKernelId: .expression,
                payload: "SwiftCog Response: \(message.payload)"
            )
            
            // Send the formatted response back to frontend
            try await app.system.emit(message: formattedMessage, from: kernel)
        }
        
        // Create MotorKernel with custom handler
        app.motorKernel = try await system.createMotorKernel { message, kernel in
            print("Backend MotorKernel: Processing \(message.payload)")
            try await app.system.emit(message: message, from: kernel)
        }
        
        // Create ExecutiveKernel with custom handler that calls LLM
        app.executiveKernel = try await system.createExecutiveKernel { [llmService = app.llmService] message, kernel in
            do {
                // Define custom system prompt for the executive decision-making
                let systemPrompt = """
                You are an executive decision-making system in a cognitive architecture. 
                Your role is to analyze input and provide intelligent decisions or responses.
                Be very concise. Just provide direct answer to the question.
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
                    sourceKernelId: .executive,
                    payload: aiResponse
                )
                
                // Emit the AI-processed message to the next kernel
                try await app.system.emit(message: processedMessage, from: kernel)
                
            } catch {
                print("Error calling LLM: \(error.localizedDescription)")
                // If LLM fails, pass through the original message
                try await app.system.emit(message: message, from: kernel)
            }
        }
        
        // Connect the backend kernels to form the pipeline
        try await system.connect(from: app.sensingKernel!, to: app.executiveKernel!)
        try await system.connect(from: app.executiveKernel!, to: app.motorKernel!)
        try await system.connect(from: app.motorKernel!, to: app.expressionKernel!)
        
        print("ExampleApp: Backend kernel pipeline established")
        
        return app as! Self
    }
    
}