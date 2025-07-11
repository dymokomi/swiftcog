import AppKit
import SwiftUI
import SwiftCogCore
// Import our local views

class SwiftCogGUIApp: NSObject, NSApplicationDelegate, @unchecked Sendable {
    private var window: NSWindow?
    private var chatController: ChatController?
    private var system: FrontendKernelSystem?
    private var speechEngine: SpeechToTextEngine?
    private var windowDelegate: WindowDelegate?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Configure the application
        NSApp.setActivationPolicy(.regular)
        
        // Initialize the GUI app
        Task {
            // Create frontend kernel system
            let system = FrontendKernelSystem(host: "127.0.0.1", port: 8000)
            self.system = system
            
            // Set up error handler
            system.setErrorHandler { errorMessage in
                print("Error: \(errorMessage)")
            }
            
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
            await startSpeechRecognition()
        }
        
        NSApp.activate(ignoringOtherApps: true)
    }
    
    private func createWindow() {
        // Create controller that manages chat interaction
        chatController = ChatController { userMessage in
            Task {
                // Send user message directly to backend
                try? await self.system?.sendToBackend(userMessage)
            }
        }
        
        // Set up display command handler
        system?.setDisplayCommandHandler { displayCommand in
            self.chatController?.handleDisplayCommand(displayCommand)
        }
        
        // Create the main chat view
        let chatView = ChatView(controller: chatController!)
        
        // Create the window
        window = NSWindow(
            contentRect: NSRect(x: 100, y: 100, width: 800, height: 600),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        
        window?.title = "SwiftCog Chat"
        window?.contentView = NSHostingView(rootView: chatView)
        window?.center()
        window?.makeKeyAndOrderFront(nil)
        
        // Create and set window delegate
        windowDelegate = WindowDelegate()
        window?.delegate = windowDelegate
    }
    
    private func startSpeechRecognition() async {
        guard let speechEngine = speechEngine else {
            print("Speech engine not initialized")
            return
        }
        
        do {
            print("Starting speech recognition...")
            for try await speechText in speechEngine.start() {
                print("GUI: Speech input: '\(speechText)'")
                
                // Handle speech input directly in GUI
                await MainActor.run {
                    self.chatController?.handleUserMessage(speechText)
                }
            }
        } catch {
            print("Speech recognition error: \(error)")
        }
    }
    
    private func getAPIKey() -> String {
        // Try environment variable first
        if let envKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] {
            return envKey
        }
        
        // Fallback to default (this should be set in your environment)
        return ""
    }
}

// Window delegate to handle window close events
class WindowDelegate: NSObject, NSWindowDelegate {
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        return true
    }
}

// Main entry point
let app = NSApplication.shared
let delegate = SwiftCogGUIApp()
app.delegate = delegate
app.run() 