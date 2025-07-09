import SwiftUI
import WebKit
import Foundation

// MARK: - Chat Message Model
struct ChatMessage: Codable {
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
class WebChatController: ObservableObject {
    @Published var messages: [ChatMessage] = []
    private var webView: WKWebView?
    private var onMessageSent: ((String) -> Void)?
    
    // Create the view that references this controller
    lazy var view: WebChatView = {
        return WebChatView(controller: self)
    }()
    
    init(onMessageSent: @escaping (String) -> Void) {
        self.onMessageSent = onMessageSent
    }
    
    func setup(webView: WKWebView) {
        self.webView = webView
    }
    
    func handleUserMessage(_ message: String) {
        print("🎯 WebChatController: User sent message: '\(message)'")
        
        // Add user message to WebView first
        addMessage(message, isUser: true)
        
        // Then send to backend
        onMessageSent?(message)
    }
    
    func addMessage(_ content: String, isUser: Bool = false) {
        DispatchQueue.main.async {
            if isUser {
                print("🎯 WebChatController: Adding USER message to WebView: '\(content)'")
                // Add user message via JavaScript
                let escapedContent = content.replacingOccurrences(of: "\"", with: "\\\"")
                    .replacingOccurrences(of: "\n", with: "\\n")
                
                let script = "addMessage(\"\(escapedContent)\", true);"
                self.webView?.evaluateJavaScript(script) { _, error in
                    if let error = error {
                        print("❌ JavaScript error adding user message: \(error)")
                    } else {
                        print("✅ Successfully added user message to WebView")
                    }
                }
            } else {
                print("🎯 WebChatController: Adding AI message to WebView: '\(content)'")
                // Add AI response via JavaScript
                let escapedContent = content.replacingOccurrences(of: "\"", with: "\\\"")
                    .replacingOccurrences(of: "\n", with: "\\n")
                
                let script = "addAIResponse(\"\(escapedContent)\");"
                self.webView?.evaluateJavaScript(script) { _, error in
                    if let error = error {
                        print("❌ JavaScript error adding AI message: \(error)")
                    } else {
                        print("✅ Successfully added AI response to WebView")
                    }
                }
            }
        }
    }
}

// MARK: - WebKit Coordinator
class WebViewCoordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    let controller: WebChatController
    
    init(controller: WebChatController) {
        self.controller = controller
    }
    
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        print("WebView loaded successfully")
    }
    
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "messageHandler", let messageText = message.body as? String {
            controller.handleUserMessage(messageText)
        }
    }
}

// MARK: - WebView Wrapper
struct WebViewWrapper: NSViewRepresentable {
    let controller: WebChatController
    let onMessageSent: (String) -> Void
    
    func makeNSView(context: Context) -> WKWebView {
        let coordinator = WebViewCoordinator(controller: controller)
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(coordinator, name: "messageHandler")
        
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = coordinator
        
        // Setup controller with webView
        controller.setup(webView: webView)
        
        // Load the HTML content
        let htmlContent = createChatHTML()
        webView.loadHTMLString(htmlContent, baseURL: nil)
        
        return webView
    }
    
    func updateNSView(_ nsView: WKWebView, context: Context) {
        // Updates handled via JavaScript calls
    }
    
    private func createChatHTML() -> String {
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SwiftCog Chat</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    height: 100vh;
                    display: flex;
                    flex-direction: column;
                }
                
                .header {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    padding: 20px;
                    text-align: center;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                }
                
                .header h1 {
                    color: white;
                    font-size: 24px;
                    font-weight: 600;
                }
                
                .status {
                    color: #4ade80;
                    font-size: 14px;
                    margin-top: 5px;
                }
                
                .chat-container {
                    flex: 1;
                    padding: 20px;
                    overflow-y: auto;
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }
                
                .message {
                    display: flex;
                    margin-bottom: 15px;
                }
                
                .message.user {
                    justify-content: flex-end;
                }
                
                .message.assistant {
                    justify-content: flex-start;
                }
                
                .message-bubble {
                    max-width: 70%;
                    padding: 12px 16px;
                    border-radius: 18px;
                    position: relative;
                    animation: slideIn 0.3s ease-out;
                }
                
                .message.user .message-bubble {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-bottom-right-radius: 6px;
                }
                
                .message.assistant .message-bubble {
                    background: white;
                    color: #1f2937;
                    border-bottom-left-radius: 6px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                }
                
                .message-content {
                    line-height: 1.4;
                }
                
                .message-time {
                    font-size: 11px;
                    opacity: 0.7;
                    margin-top: 6px;
                }
                
                .message.user .message-time {
                    text-align: right;
                }
                
                .input-container {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    padding: 20px;
                    border-top: 1px solid rgba(255, 255, 255, 0.2);
                }
                
                .input-row {
                    display: flex;
                    gap: 10px;
                    align-items: center;
                }
                
                .message-input {
                    flex: 1;
                    padding: 12px 16px;
                    border: none;
                    border-radius: 25px;
                    background: white;
                    font-size: 16px;
                    outline: none;
                }
                
                .send-button {
                    padding: 12px 24px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 25px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: transform 0.2s;
                }
                
                .send-button:hover {
                    transform: scale(1.05);
                }
                
                .send-button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                    transform: none;
                }
                
                .thinking {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    color: rgba(255, 255, 255, 0.8);
                    font-style: italic;
                    margin-bottom: 10px;
                }
                
                .thinking-dots {
                    display: flex;
                    gap: 4px;
                }
                
                .thinking-dot {
                    width: 6px;
                    height: 6px;
                    background: rgba(255, 255, 255, 0.6);
                    border-radius: 50%;
                    animation: pulse 1.4s infinite ease-in-out;
                }
                
                .thinking-dot:nth-child(1) { animation-delay: 0s; }
                .thinking-dot:nth-child(2) { animation-delay: 0.16s; }
                .thinking-dot:nth-child(3) { animation-delay: 0.32s; }
                
                @keyframes slideIn {
                    from {
                        opacity: 0;
                        transform: translateY(20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                @keyframes pulse {
                    0%, 80%, 100% {
                        transform: scale(0);
                        opacity: 0.5;
                    }
                    40% {
                        transform: scale(1);
                        opacity: 1;
                    }
                }
                
                .welcome-message {
                    text-align: center;
                    color: rgba(255, 255, 255, 0.8);
                    margin: 40px 0;
                }
                
                .welcome-message h2 {
                    font-size: 28px;
                    margin-bottom: 10px;
                }
                
                .welcome-message p {
                    font-size: 16px;
                    opacity: 0.8;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧠 SwiftCog Chat</h1>
                <div class="status">● Connected</div>
            </div>
            
            <div class="chat-container" id="chatContainer">
                <div class="welcome-message">
                    <h2>Welcome to SwiftCog!</h2>
                    <p>Your AI-powered cognitive assistant is ready to help.</p>
                </div>
            </div>
            
            <div class="input-container">
                <div class="input-row">
                    <input type="text" class="message-input" id="messageInput" placeholder="Type your message..." />
                    <button class="send-button" id="sendButton">Send</button>
                </div>
            </div>
            
            <script>
                const chatContainer = document.getElementById('chatContainer');
                const messageInput = document.getElementById('messageInput');
                const sendButton = document.getElementById('sendButton');
                let isWaiting = false;
                
                function addMessage(content, isUser) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
                    
                    const now = new Date();
                    const timeString = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    
                    messageDiv.innerHTML = `
                        <div class="message-bubble">
                            <div class="message-content">${content}</div>
                            <div class="message-time">${timeString}</div>
                        </div>
                    `;
                    
                    chatContainer.appendChild(messageDiv);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    
                    // Remove welcome message on first real message
                    const welcomeMsg = chatContainer.querySelector('.welcome-message');
                    if (welcomeMsg) {
                        welcomeMsg.remove();
                    }
                }
                
                function showThinking() {
                    const thinkingDiv = document.createElement('div');
                    thinkingDiv.className = 'thinking';
                    thinkingDiv.id = 'thinking';
                    thinkingDiv.innerHTML = `
                        🤔 SwiftCog is thinking
                        <div class="thinking-dots">
                            <div class="thinking-dot"></div>
                            <div class="thinking-dot"></div>
                            <div class="thinking-dot"></div>
                        </div>
                    `;
                    chatContainer.appendChild(thinkingDiv);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
                
                function hideThinking() {
                    const thinking = document.getElementById('thinking');
                    if (thinking) {
                        thinking.remove();
                    }
                }
                
                function sendMessage() {
                    const message = messageInput.value.trim();
                    if (!message || isWaiting) return;
                    
                    addMessage(message, true);
                    messageInput.value = '';
                    isWaiting = true;
                    sendButton.disabled = true;
                    showThinking();
                    
                    // Send to Swift
                    window.webkit.messageHandlers.messageHandler.postMessage(message);
                }
                
                messageInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        sendMessage();
                    }
                });
                
                sendButton.addEventListener('click', sendMessage);
                
                // Function to be called from Swift
                function addAIResponse(response) {
                    hideThinking();
                    addMessage(response, false);
                    isWaiting = false;
                    sendButton.disabled = false;
                    messageInput.focus();
                }
                
                // Focus input on load
                window.addEventListener('load', function() {
                    messageInput.focus();
                });
            </script>
        </body>
        </html>
        """
    }
}

// MARK: - Main SwiftUI Chat View
struct WebChatView: View {
    @ObservedObject var controller: WebChatController
    let onMessageSent: (String) -> Void
    
    init(controller: WebChatController) {
        self.controller = controller
        self.onMessageSent = { message in
            controller.handleUserMessage(message)
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            WebViewWrapper(controller: controller, onMessageSent: onMessageSent)
        }
        .navigationTitle("SwiftCog Chat")
        .frame(minWidth: 800, minHeight: 600)
    }
    
    func addMessage(_ content: String, isUser: Bool) {
        if !isUser {
            controller.addMessage(content)
        }
    }
} 