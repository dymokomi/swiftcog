import AppKit
import SwiftUI
import SwiftCogCore
import AVFoundation
import Vision
// Import our local views

class SwiftCogGUIApp: NSObject, NSApplicationDelegate, @unchecked Sendable {
    private var window: NSWindow?
    private var chatController: ChatController?
    private var system: FrontendKernelSystem?
    private var speechEngine: SpeechToTextEngine?
    private var gazeTracker: GazeTracker?
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
            speechEngine = SpeechToTextEngine()
            
            // Create GazeTracker for gaze-based VAD blocking
            gazeTracker = GazeTracker()
            
            // Wire up gaze tracker with speech engine and kernel system
            if let speechEngine = speechEngine, let gazeTracker = gazeTracker {
                speechEngine.setGazeTracker(gazeTracker)
                gazeTracker.setKernelSystem(system)
            }
            
            // Start the kernel system background tasks
            let _ = system.run()
            
            // Launch the chat window on the main thread
            await MainActor.run {
                self.createWindow()
            }
            
            print("SwiftCog GUI app started successfully!")
            
            // Start gaze tracking
            gazeTracker?.start()
            
            // Give gaze tracker time to initialize
            try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
            
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
        let chatView = ChatView(controller: chatController!, speechEngine: speechEngine!, gazeTracker: gazeTracker!)
        
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
            try speechEngine.startListening(
                onTranscriptionUpdate: { transcription in
                    // Real-time transcription updates are handled by the overlay view
                    // No need to do anything here as the UI is bound to speechEngine.currentTranscription
                },
                onFinalTranscription: { finalText in
                    print("GUI: Final speech input: '\(finalText)'")
                    
                    // Handle final speech input
                    Task { @MainActor in
                        self.chatController?.handleUserMessage(finalText)
                    }
                }
            )
        } catch {
            print("Speech recognition error: \(error)")
        }
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