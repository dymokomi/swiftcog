import Foundation
import SwiftCogCore
import SwiftUI
import AppKit

public class ExampleApp: SwiftCogApp {
    public static let appName = "ExampleApp"
    public static let appDescription = "A simple example cognitive architecture application"
    
    let system: KernelSystem
    let llmService: LLMService
    
    // Backend kernels
    private var sensingKernel: SensingKernel?
    private var executiveKernel: ExecutiveKernel?
    private var motorKernel: MotorKernel?
    private var expressionKernel: ExpressionKernel?
    
    // Frontend interface kernels
    private var sensingInterfaceKernel: SensingInterfaceKernel?
    private var expressionInterfaceKernel: ExpressionInterfaceKernel?
    
    // Frontend chat controller
    private var chatController: WebChatController?

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
    
    /// Initialize ExampleApp for frontend mode with interface kernels
    public static func initFrontend(system: KernelSystem) async throws -> Self {
        guard let apiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] else {
            throw NSError(domain: "ExampleApp", code: 1, userInfo: [NSLocalizedDescriptionKey: "OPENAI_API_KEY environment variable not set"])
        }
        
        let openAIProvider = OpenAIProvider(apiKey: apiKey)
        let llmService = LLMService(provider: openAIProvider)
        let app = ExampleApp(system: system, llmService: llmService)
        
        print("ExampleApp: Initializing frontend interface kernels...")
        
        // Create SensingInterfaceKernel for user input
        app.sensingInterfaceKernel = try await system.createSensingInterfaceKernel(
            customHandler: { message, kernel in
                print("Frontend SensingInterfaceKernel: Got user input: \(message.payload)")
            },
            speechInputCallback: { [weak app] speechText in
                print("🎯 ExampleApp: Speech input callback: '\(speechText)'")
                // Add the user's speech to the chat interface
                app?.chatController?.addMessage(speechText, isUser: true)
            }
        )
        
        // Create ExpressionInterfaceKernel for AI responses
        app.expressionInterfaceKernel = try await system.createExpressionInterfaceKernel { [weak app] message, kernel in
            print("🎯 ExampleApp: ExpressionInterfaceKernel received message: '\(message.payload)'")
            // Extract the AI response from the formatted message
            let response = message.payload.replacingOccurrences(of: "SwiftCog Response: ", with: "")
            print("🎯 ExampleApp: Extracted response: '\(response)'")
            Task { @MainActor in
                print("🎯 ExampleApp: Updating chat view with response")
                app?.chatController?.addMessage(response, isUser: false)
            }
        }
        
        print("ExampleApp: Frontend interface kernels created")
        
        return app as! Self
    }
    
    /// Launch the SwiftUI chat window for frontend mode
    public func launchChatWindow() {
        let chatController = WebChatController { userMessage in
            Task {
                // Send user message through the sensing interface kernel
                let message = KernelMessage(sourceKernelId: .sensingInterface, payload: userMessage)
                try? await self.system.emit(message: message, from: self.sensingInterfaceKernel!)
            }
        }
        
        // Store reference to chat view for AI responses
        self.chatController = chatController
        print("🎯 ExampleApp: Stored chatView reference: \(chatController)")
        
        // Create and launch the SwiftUI window
        let contentView = chatController.view
        
        DispatchQueue.main.async {
            let hostingController = NSHostingController(rootView: contentView)
            let window = NSWindow(contentViewController: hostingController)
            
            window.title = "SwiftCog Chat"
            window.setContentSize(NSSize(width: 1000, height: 700))
            window.styleMask = [.titled, .closable, .miniaturizable, .resizable]
            window.minSize = NSSize(width: 400, height: 300)
            window.center()
            window.makeKeyAndOrderFront(nil)
            
            // Keep the window alive
            NSApp.setActivationPolicy(.regular)
            NSApp.activate(ignoringOtherApps: true)
            
            print("ExampleApp: SwiftUI chat window launched!")
        }
    }
}

// Register the app with the registry
extension ExampleApp {
    public static func register() {
        AppRegistry.register(name: appName, type: ExampleApp.self)
    }
}