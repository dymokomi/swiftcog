import AppKit
import SwiftUI
import SwiftCogCore
import Examples

class SwiftCogGUIApp: NSObject, NSApplicationDelegate {
    private var window: NSWindow?
    private var exampleApp: ExampleApp?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Configure the application
        NSApp.setActivationPolicy(.regular)
        
        // Initialize the frontend app
        Task {
            do {
                // Create kernel system for frontend mode
                let system = KernelSystem(apiKey: getAPIKey(), mode: .frontend, host: "127.0.0.1", port: 8080)
                
                // Initialize the frontend app
                let app = try await ExampleApp.initFrontend(system: system)
                self.exampleApp = app
                
                // Start the kernel system background tasks
                let _ = system.run()
                
                // Launch the chat window on the main thread
                await MainActor.run {
                    self.createWindow(with: app)
                }
                
                print("SwiftCog GUI app started successfully!")
            } catch {
                print("Error initializing SwiftCog GUI: \(error)")
                await MainActor.run {
                    self.showErrorAlert(error: error)
                }
            }
        }
    }
    
    @MainActor
    private func createWindow(with app: ExampleApp) {
        let chatController = WebChatController { userMessage in
            Task {
                // Send user message through the sensing interface kernel
                let message = KernelMessage(sourceKernelId: .sensingInterface, payload: userMessage)
                try? await app.system.emit(message: message, from: app.sensingInterfaceKernel!)
            }
        }
        
        // Store reference for AI responses
        app.chatController = chatController
        
        // Create the SwiftUI content view
        let contentView = chatController.view
        
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