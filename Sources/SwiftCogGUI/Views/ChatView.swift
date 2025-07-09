import SwiftUI
import WebKit
import Foundation

// MARK: - Chat Message Model
struct ChatMessage: Codable, Identifiable {
    let id: String
    let content: String
    let isUser: Bool
    let timestamp: Date
    
    init(content: String, isUser: Bool) {
        self.id = UUID().uuidString
        self.content = content
        self.isUser = isUser
        self.timestamp = Date()
    }
}

// MARK: - Chat Controller
class ChatController: ObservableObject {
    @Published var messages: [ChatMessage] = []
    private var webView: WKWebView?
    private var onUserMessage: ((String) -> Void)?
    
    init(onUserMessage: @escaping (String) -> Void) {
        self.onUserMessage = onUserMessage
    }
    
    func setup(webView: WKWebView) {
        self.webView = webView
    }
    
    // Handle display commands from backend
    func handleDisplayCommand(_ command: DisplayCommand) {
        DispatchQueue.main.async {
            switch command.type {
            case .showMessage:
                if let cmd = command as? ShowMessageCommand {
                    self.addMessage(cmd.message, isUser: cmd.isUser)
                }
            case .clearScreen:
                self.clearMessages()
            case .showThinking:
                self.showThinking()
            case .hideThinking:
                self.hideThinking()
            case .updateStatus:
                if let cmd = command as? UpdateStatusCommand {
                    self.updateStatus(cmd.status)
                }
            }
        }
    }
    
    private func addMessage(_ content: String, isUser: Bool) {
        let message = ChatMessage(content: content, isUser: isUser)
        messages.append(message)
        
        // Update WebView
        let escapedContent = content.replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
        
        let script = "addMessage(\"\(escapedContent)\", \(isUser));"
        webView?.evaluateJavaScript(script) { _, error in
            if let error = error {
                print("❌ ChatController: JavaScript error: \(error)")
            }
        }
    }
    
    private func clearMessages() {
        messages.removeAll()
        webView?.evaluateJavaScript("clearMessages();")
    }
    
    private func showThinking() {
        webView?.evaluateJavaScript("showThinking();")
    }
    
    private func hideThinking() {
        webView?.evaluateJavaScript("hideThinking();")
    }
    
    private func updateStatus(_ status: String) {
        let escapedStatus = status.replacingOccurrences(of: "\"", with: "\\\"")
        webView?.evaluateJavaScript("updateStatus(\"\(escapedStatus)\");")
    }
    
    func handleUserMessage(_ message: String) {
        // Add user message immediately to UI
        addMessage(message, isUser: true)
        
        // Send to backend
        onUserMessage?(message)
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
        controller.setup(webView: webView)
        
        // Load the HTML content
        loadHTMLFromBundle(webView: webView)
        
        return webView
    }
    
    private func loadHTMLFromBundle(webView: WKWebView) {
        // For executable targets, try Bundle.main first, then check relative path as fallback
        var htmlURL: URL?
        
        // Try Bundle.main first (for built executable)
        print("🔍 Searching for chat.html in Bundle.main...")
        htmlURL = Bundle.main.url(forResource: "chat", withExtension: "html")
        if htmlURL != nil {
            print("✅ Found in Bundle.main: \(htmlURL!)")
        } else {
            print("❌ Not found in Bundle.main")
        }
        
        // Fallback: try direct file path for development
        if htmlURL == nil {
            print("🔍 Trying direct file path...")
            let resourcePath = "Sources/SwiftCogGUI/Resources/chat.html"
            if FileManager.default.fileExists(atPath: resourcePath) {
                htmlURL = URL(fileURLWithPath: resourcePath)
                print("✅ Found at direct path: \(resourcePath)")
            } else {
                print("❌ Not found at direct path: \(resourcePath)")
            }
        }
        
        guard let finalURL = htmlURL else {
            print("❌ Could not find chat.html file in bundle")
            return
        }
        
        do {
            let htmlContent = try String(contentsOf: finalURL)
            webView.loadHTMLString(htmlContent, baseURL: finalURL.deletingLastPathComponent())
            print("✅ Loaded chat interface from bundle")
        } catch {
            print("❌ Error loading HTML file: \(error)")
        }
    }
    
    func updateNSView(_ nsView: WKWebView, context: Context) {
        // Updates handled via JavaScript calls
    }
}

// MARK: - Main Chat View
struct ChatView: View {
    @ObservedObject var controller: ChatController
    
    init(controller: ChatController) {
        self.controller = controller
    }
    
    var body: some View {
        ChatWebViewWrapper(controller: controller)
    }
} 