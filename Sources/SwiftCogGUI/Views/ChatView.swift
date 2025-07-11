import SwiftUI
import WebKit
import SwiftCogCore

// MARK: - Chat Message Model
struct ChatMessage {
    let id = UUID()
    let text: String
    let isUser: Bool
    let timestamp: Date
    
    init(text: String, isUser: Bool) {
        self.text = text
        self.isUser = isUser
        self.timestamp = Date()
    }
}

// MARK: - Chat Controller
class ChatController: ObservableObject {
    private var webView: WKWebView?
    private let onUserMessage: (String) -> Void
    
    init(onUserMessage: @escaping (String) -> Void) {
        self.onUserMessage = onUserMessage
    }
    
    func setWebView(_ webView: WKWebView) {
        self.webView = webView
        self.loadChatInterface()
    }
    
    func handleUserMessage(_ message: String) {
        // Don't add message locally - let the server handle all display commands
        onUserMessage(message)
    }
    
    func addMessage(_ text: String, isUser: Bool) {
        guard let webView = webView else { return }
        
        // Properly escape all special characters for JavaScript
        let escapedText = text
            .replacingOccurrences(of: "\\", with: "\\\\")  // Escape backslashes first
            .replacingOccurrences(of: "'", with: "\\'")     // Escape single quotes
            .replacingOccurrences(of: "\"", with: "\\\"")   // Escape double quotes
            .replacingOccurrences(of: "\n", with: "\\n")    // Escape newlines
            .replacingOccurrences(of: "\r", with: "\\r")    // Escape carriage returns
            .replacingOccurrences(of: "\t", with: "\\t")    // Escape tabs
        
        let script = "addMessage('\(escapedText)', \(isUser));"
        
        webView.evaluateJavaScript(script) { result, error in
            if let error = error {
                print("ChatController: JavaScript error: \(error)")
            }
        }
    }
    
    func clearChat() {
        guard let webView = webView else { return }
        
        let script = "clearChat();"
        
        webView.evaluateJavaScript(script) { result, error in
            if let error = error {
                print("ChatController: JavaScript error: \(error)")
            }
        }
    }
    
    func displayList(_ items: [ListItem]) {
        guard let webView = webView else { return }
        
        do {
            // Convert ListItem objects to a format suitable for JavaScript
            let itemsForJS = items.map { ["id": $0.id, "text": $0.text, "isSelected": $0.isSelected] }
            let jsonData = try JSONSerialization.data(withJSONObject: itemsForJS)
            let jsonString = String(data: jsonData, encoding: .utf8) ?? "[]"
            
            let script = "displayList(\(jsonString));"
            
            webView.evaluateJavaScript(script) { result, error in
                if let error = error {
                    print("ChatController: JavaScript error: \(error)")
                }
            }
        } catch {
            print("ChatController: Failed to encode list items: \(error)")
        }
    }
    
    func updateStatus(_ status: String) {
        guard let webView = webView else { return }
        
        // Properly escape all special characters for JavaScript
        let escapedStatus = status
            .replacingOccurrences(of: "\\", with: "\\\\")  // Escape backslashes first
            .replacingOccurrences(of: "'", with: "\\'")     // Escape single quotes
            .replacingOccurrences(of: "\"", with: "\\\"")   // Escape double quotes
            .replacingOccurrences(of: "\n", with: "\\n")    // Escape newlines
            .replacingOccurrences(of: "\r", with: "\\r")    // Escape carriage returns
            .replacingOccurrences(of: "\t", with: "\\t")    // Escape tabs
        
        let script = "updateStatus('\(escapedStatus)');"
        
        webView.evaluateJavaScript(script) { result, error in
            if let error = error {
                print("ChatController: JavaScript error: \(error)")
            }
        }
    }
    
    func showThinking() {
        guard let webView = webView else { return }
        
        let script = "showThinking();"
        
        webView.evaluateJavaScript(script) { result, error in
            if let error = error {
                print("ChatController: JavaScript error: \(error)")
            }
        }
    }
    
    func hideThinking() {
        guard let webView = webView else { return }
        
        let script = "hideThinking();"
        
        webView.evaluateJavaScript(script) { result, error in
            if let error = error {
                print("ChatController: JavaScript error: \(error)")
            }
        }
    }
    
    func handleDisplayCommand(_ command: DisplayCommand) {
        switch command.type {
        case .textBubble:
            if let textCommand = command as? TextBubbleCommand {
                addMessage(textCommand.text, isUser: textCommand.isUser)
            }
        case .clearScreen:
            clearChat()
        case .displayList:
            if let listCommand = command as? DisplayListCommand {
                displayList(listCommand.items)
            }
        case .updateStatus:
            if let statusCommand = command as? UpdateStatusCommand {
                updateStatus(statusCommand.status)
            }
        case .showThinking:
            showThinking()
        case .hideThinking:
            hideThinking()
        default:
            break
        }
    }
    
    private func loadChatInterface() {
        guard let webView = webView else { return }
        
        // Try to find the HTML file in the bundle
        var htmlURL: URL?
        
        print("Searching for chat.html in Bundle.main...")
        
        if let bundleURL = Bundle.main.url(forResource: "chat", withExtension: "html") {
            print("Found in Bundle.main: \(bundleURL)")
            htmlURL = bundleURL
        } else {
            print("Not found in Bundle.main")
            
            // Try alternative path
            let resourcePath = "Sources/SwiftCogGUI/Resources/chat.html"
            print("Trying direct file path...")
            
            if FileManager.default.fileExists(atPath: resourcePath) {
                htmlURL = URL(fileURLWithPath: resourcePath)
                print("Found at direct path: \(resourcePath)")
            } else {
                print("Not found at direct path: \(resourcePath)")
            }
        }
        
        guard let htmlURL = htmlURL else {
            print("Could not find chat.html file in bundle")
            return
        }
        
        do {
            let htmlContent = try String(contentsOf: htmlURL)
            webView.loadHTMLString(htmlContent, baseURL: htmlURL.deletingLastPathComponent())
            print("Loaded chat interface from bundle")
        } catch {
            print("Error loading HTML file: \(error)")
        }
    }
}

// MARK: - WebKit Coordinator
class ChatWebViewCoordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    let controller: ChatController
    
    init(controller: ChatController) {
        self.controller = controller
    }
    
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        print("Chat WebView loaded successfully")
    }
    
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "messageHandler", let messageText = message.body as? String {
            controller.handleUserMessage(messageText)
        }
    }
}

// MARK: - WebView Wrapper
struct ChatWebViewWrapper: NSViewRepresentable {
    let controller: ChatController
    
    func makeNSView(context: Context) -> WKWebView {
        let coordinator = ChatWebViewCoordinator(controller: controller)
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(coordinator, name: "messageHandler")
        
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = coordinator
        
        // Setup controller with webView
        controller.setWebView(webView)
        
        // Load the HTML content
        loadHTMLFromBundle(webView: webView)
        
        return webView
    }
    
    private func loadHTMLFromBundle(webView: WKWebView) {
        // For executable targets, try Bundle.main first, then check relative path as fallback
        var htmlURL: URL?
        
        // Try Bundle.main first (for built executable)
        print("Searching for chat.html in Bundle.main...")
        htmlURL = Bundle.main.url(forResource: "chat", withExtension: "html")
        if htmlURL != nil {
            print("Found in Bundle.main: \(htmlURL!)")
        } else {
            print("Not found in Bundle.main")
        }
        
        // Fallback: try direct file path for development
        if htmlURL == nil {
            print("Trying direct file path...")
            let resourcePath = "Sources/SwiftCogGUI/Resources/chat.html"
            if FileManager.default.fileExists(atPath: resourcePath) {
                htmlURL = URL(fileURLWithPath: resourcePath)
                print("Found at direct path: \(resourcePath)")
            } else {
                print("Not found at direct path: \(resourcePath)")
            }
        }
        
        guard let finalURL = htmlURL else {
            print("Could not find chat.html file in bundle")
            return
        }
        
        do {
            let htmlContent = try String(contentsOf: finalURL)
            webView.loadHTMLString(htmlContent, baseURL: finalURL.deletingLastPathComponent())
            print("Loaded chat interface from bundle")
        } catch {
            print("Error loading HTML file: \(error)")
        }
    }
    
    func updateNSView(_ nsView: WKWebView, context: Context) {
        // Updates handled via JavaScript calls
    }
}

// MARK: - Main Chat View
struct ChatView: View {
    @ObservedObject var controller: ChatController
    @ObservedObject var speechEngine: SpeechToTextEngine
    
    init(controller: ChatController, speechEngine: SpeechToTextEngine) {
        self.controller = controller
        self.speechEngine = speechEngine
    }
    
    var body: some View {
        ZStack {
            ChatWebViewWrapper(controller: controller)
            
            // Transcription overlay on top
            TranscriptionOverlay(
                transcription: speechEngine.currentTranscription,
                isListening: speechEngine.isListening
            )
        }
    }
} 