import AppKit
import SwiftUI
import SwiftCogCore
// Import our local views

class SwiftCogGUIApp: NSObject, NSApplicationDelegate, @unchecked Sendable {
    private var window: NSWindow?
    private var chatController: ChatController?
    private var system: FrontendKernelSystem?
    private var speechEngine: SpeechToTextEngine?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Configure the application
        NSApp.setActivationPolicy(.regular)
        
        // Initialize the GUI app
        Task {
            do {
                // Create frontend kernel system
                let system = FrontendKernelSystem(host: "127.0.0.1", port: 8080)
                self.system = system
                
                // Create SpeechToTextEngine for speech input
                speechEngine = SpeechToTextEngine(apiKey: getAPIKey())
                
                // Start the kernel system background tasks
                let _ = system.run()
                
                // Launch the chat window on the main thread
                await MainActor.run {
                    self.createWindow()
                }
                
                print("SwiftCog GUI app started successfully!")
                
                // Start speech recognition
                Task {
                    await self.startSpeechRecognition()
                }
            } catch {
                print("Error initializing SwiftCog GUI: \(error)")
                await MainActor.run {
                    self.showErrorAlert(error: error)
                }
            }
        }
    }
    
    private func startSpeechRecognition() async {
        guard let speechEngine = speechEngine else {
            print("❌ Speech engine not initialized")
            return
        }
        
        do {
            print("🎙️ Starting speech recognition...")
            for try await speechText in speechEngine.start() {
                print("🎯 GUI: Speech input: '\(speechText)'")
                
                // Handle speech input directly in GUI
                await MainActor.run {
                    self.chatController?.handleUserMessage(speechText)
                }
            }
        } catch {
            print("❌ Speech recognition error: \(error)")
        }
    }
    
    @MainActor
    private func createWindow() {
        let chatController = ChatController { userMessage in
            Task {
                // Send user message directly to backend
                try? await self.system?.sendToBackend(userMessage)
            }
        }
        
        // Store reference for display commands
        self.chatController = chatController
        
        // Set up display command handler
        system?.setDisplayCommandHandler { displayCommand in
            chatController.handleDisplayCommand(displayCommand)
        }
        
        // Create the SwiftUI content view
        let contentView = ChatView(controller: chatController)
        
        // Create the hosting controller and window
        let hostingController = NSHostingController(rootView: contentView)
        let window = NSWindow(contentViewController: hostingController)
        
        // Configure the window properly
        window.title = "SwiftCog Chat"
        window.setContentSize(NSSize(width: 1000, height: 700))
        window.styleMask = [NSWindow.StyleMask.titled, .closable, .miniaturizable, .resizable]
        window.minSize = NSSize(width: 400, height: 300)
        window.center()
        window.makeKeyAndOrderFront(window)
        
        // Store the window reference
        self.window = window
        
        print("SwiftCog chat window created!")
    }
    
    @MainActor
    private func showErrorAlert(error: Error) {
        let alert = NSAlert()
        alert.messageText = "SwiftCog Error"
        alert.informativeText = error.localizedDescription
        alert.addButton(withTitle: "OK")
        alert.runModal()
        NSApp.terminate(nil)
    }
    
    private func getAPIKey() -> String {
        // Try to get API key from environment
        if let apiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"], !apiKey.isEmpty {
            return apiKey
        }
        
        // Try to load from .env file
        let envPath = ".env"
        if let envContent = try? String(contentsOfFile: envPath) {
            for line in envContent.components(separatedBy: .newlines) {
                if line.hasPrefix("OPENAI_API_KEY=") {
                    return String(line.dropFirst("OPENAI_API_KEY=".count))
                }
            }
        }
        
        // If not found, show error
        DispatchQueue.main.async {
            let alert = NSAlert()
            alert.messageText = "Missing API Key"
            alert.informativeText = "Please set your OpenAI API key in the OPENAI_API_KEY environment variable or in a .env file."
            alert.addButton(withTitle: "OK")
            alert.runModal()
            NSApp.terminate(nil)
        }
        
        return ""
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

// Main entry point
let app = NSApplication.shared
let delegate = SwiftCogGUIApp()
app.delegate = delegate
app.run() 