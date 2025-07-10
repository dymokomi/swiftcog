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
        
        // Create SensingKernel with custom handler that passes through the original message
        app.sensingKernel = try await system.createSensingKernel { message, kernel in
            // Just pass through the original message without modification
            try await app.system.emit(message: message, from: kernel)
        }
        
        // Create ExpressionKernel with custom handler that sends back to frontend
        app.expressionKernel = try await system.createExpressionKernel { message, kernel in
            print("Backend ExpressionKernel: \(message.payload)")
            
            // Send the display command to frontend
            try await app.system.emit(message: message, from: kernel)
        }
        
        // Create MotorKernel with custom handler
        app.motorKernel = try await system.createMotorKernel { message, kernel in
            print("Backend MotorKernel: Processing \(message.payload)")
            try await app.system.emit(message: message, from: kernel)
        }
        
        // Create ExecutiveKernel with custom handler that calls LLM
        app.executiveKernel = try await system.createExecutiveKernel { [llmService = app.llmService] message, kernel in
            do {
                let encoder = JSONEncoder()
                
                // Step 1: Send command to show user text bubble
                let userTextBubbleCommand = TextBubbleCommand(text: message.payload, isUser: true)
                let commandData = try encoder.encode(userTextBubbleCommand)
                let commandJson = String(data: commandData, encoding: .utf8) ?? ""
                
                let userBubbleMessage = KernelMessage(
                    sourceKernelId: .executive,
                    payload: commandJson
                )
                
                try await app.system.emit(message: userBubbleMessage, from: kernel)
                
                // Step 2: Show thinking indicator
                let showThinkingCommand = ShowThinkingCommand()
                let thinkingCommandData = try encoder.encode(showThinkingCommand)
                let thinkingCommandJson = String(data: thinkingCommandData, encoding: .utf8) ?? ""
                
                let thinkingMessage = KernelMessage(
                    sourceKernelId: .executive,
                    payload: thinkingCommandJson
                )
                
                try await app.system.emit(message: thinkingMessage, from: kernel)
                
                // Step 3: Define custom system prompt for the executive decision-making
                let systemPrompt = """
                You are an executive decision-making system in a cognitive architecture. 
                Your role is to analyze input and provide intelligent decisions or responses.
                Be very concise. Just provide direct answer to the question.
                """
                
                // Step 4: Use the LLM service to process the message
                let aiResponse = try await llmService.processMessage(
                    message.payload,
                    systemPrompt: systemPrompt,
                    temperature: 0.7,
                    maxTokens: 500
                )
                
                // Step 5: Hide thinking indicator
                let hideThinkingCommand = HideThinkingCommand()
                let hideThinkingCommandData = try encoder.encode(hideThinkingCommand)
                let hideThinkingCommandJson = String(data: hideThinkingCommandData, encoding: .utf8) ?? ""
                
                let hideThinkingMessage = KernelMessage(
                    sourceKernelId: .executive,
                    payload: hideThinkingCommandJson
                )
                
                try await app.system.emit(message: hideThinkingMessage, from: kernel)
                
                // Step 6: Send command to show AI response bubble (grey color for assistant)
                let aiTextBubbleCommand = TextBubbleCommand(text: aiResponse, isUser: false)
                let aiCommandData = try encoder.encode(aiTextBubbleCommand)
                let aiCommandJson = String(data: aiCommandData, encoding: .utf8) ?? ""
                
                let aiProcessedMessage = KernelMessage(
                    sourceKernelId: .executive,
                    payload: aiCommandJson
                )
                
                // Emit the AI display command to the next kernel
                try await app.system.emit(message: aiProcessedMessage, from: kernel)
                
            } catch {
                print("Error in ExecutiveKernel: \(error.localizedDescription)")
                
                // If anything fails, send error as text bubble
                do {
                    let encoder = JSONEncoder()
                    let errorBubbleCommand = TextBubbleCommand(text: "Error: \(error.localizedDescription)", isUser: false)
                    let errorCommandData = try encoder.encode(errorBubbleCommand)
                    let errorCommandJson = String(data: errorCommandData, encoding: .utf8) ?? ""
                    
                    let errorMessage = KernelMessage(
                        sourceKernelId: .executive,
                        payload: errorCommandJson
                    )
                    
                    try await app.system.emit(message: errorMessage, from: kernel)
                } catch {
                    print("Failed to send error message: \(error)")
                }
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