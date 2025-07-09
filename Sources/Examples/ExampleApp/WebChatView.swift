import SwiftUI
import WebKit
import Foundation
import Darwin

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
    private var fileWatcher: DispatchSourceFileSystemObject?
    private var htmlFileURL: URL?
    private var reloadWorkItem: DispatchWorkItem?
    
    // Create the view that references this controller
    lazy var view: WebChatView = {
        return WebChatView(controller: self)
    }()
    
    init(onMessageSent: @escaping (String) -> Void) {
        self.onMessageSent = onMessageSent
    }
    
    func setup(webView: WKWebView) {
        self.webView = webView
        setupFileWatcher()
    }
    
    private func setupFileWatcher() {
        // For development, watch the source file instead of bundled resource
        let sourceFileURL = URL(fileURLWithPath: "Sources/Examples/ExampleApp/chat.html")
        
        let targetURL: URL
        if FileManager.default.fileExists(atPath: sourceFileURL.path) {
            // Development mode - watch source file
            targetURL = sourceFileURL
            print("🔥 Hot reload: Development mode - watching source file")
        } else {
            // Production mode - watch bundled resource
            guard let htmlURL = Bundle.module.url(forResource: "chat", withExtension: "html") else {
                print("⚠️ Hot reload: Could not find HTML file to watch")
                return
            }
            targetURL = htmlURL
            print("🔥 Hot reload: Production mode - watching bundled resource")
        }
        
        self.htmlFileURL = targetURL
        
        // Create file descriptor for watching
        let fileDescriptor = open(targetURL.path, O_EVTONLY)
        guard fileDescriptor >= 0 else {
            print("⚠️ Hot reload: Could not open file descriptor for \(targetURL.path)")
            return
        }
        
        // Create dispatch source for file system events
        fileWatcher = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: fileDescriptor,
            eventMask: [.write, .extend],
            queue: DispatchQueue.main
        )
        
        fileWatcher?.setEventHandler { [weak self] in
            self?.debounceReload()
        }
        
        fileWatcher?.setCancelHandler {
            close(fileDescriptor)
        }
        
        fileWatcher?.resume()
        print("🔥 Hot reload: File watcher started for \(targetURL.lastPathComponent)")
        print("🔥 Hot reload: Edit \(targetURL.path) to see live changes!")
    }
    
    private func debounceReload() {
        // Cancel any pending reload
        reloadWorkItem?.cancel()
        
        // Create new reload work item with delay
        reloadWorkItem = DispatchWorkItem { [weak self] in
            print("🔥 Hot reload: HTML file changed, reloading WebView...")
            self?.reloadWebView()
        }
        
        // Execute after a short delay to debounce multiple file events
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3, execute: reloadWorkItem!)
    }
    
    private func reloadWebView() {
        guard let webView = self.webView else { return }
        
        // Show visual feedback during reload
        showReloadIndicator()
        
        // Determine which file to load from
        let sourceFileURL = URL(fileURLWithPath: "Sources/Examples/ExampleApp/chat.html")
        let loadURL: URL
        
        if FileManager.default.fileExists(atPath: sourceFileURL.path) {
            // Development mode - load directly from source file
            loadURL = sourceFileURL
        } else {
            // Production mode - load from bundled resource
            guard let bundledURL = Bundle.module.url(forResource: "chat", withExtension: "html") else {
                print("❌ Hot reload: Could not find HTML file to reload")
                return
            }
            loadURL = bundledURL
        }
        
        do {
            let htmlContent = try String(contentsOf: loadURL)
            webView.loadHTMLString(htmlContent, baseURL: loadURL.deletingLastPathComponent())
            print("✅ Hot reload: WebView reloaded with updated HTML from \(loadURL.lastPathComponent)")
        } catch {
            print("❌ Hot reload: Error reloading HTML: \(error)")
        }
    }
    
    private func showReloadIndicator() {
        // Briefly flash the WebView to indicate reload
        guard let webView = self.webView else { return }
        
        let script = """
        (function() {
            const indicator = document.createElement('div');
            indicator.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                background: rgba(0, 200, 0, 0.8);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 10000;
                font-family: monospace;
            `;
            indicator.textContent = '🔥 Hot reloaded';
            document.body.appendChild(indicator);
            
            setTimeout(() => {
                indicator.style.opacity = '0';
                indicator.style.transition = 'opacity 0.5s';
                setTimeout(() => {
                    document.body.removeChild(indicator);
                }, 500);
            }, 1000);
        })();
        """
        
        webView.evaluateJavaScript(script) { _, error in
            if let error = error {
                print("⚠️ Hot reload indicator error: \(error)")
            }
        }
    }
    
    deinit {
        reloadWorkItem?.cancel()
        fileWatcher?.cancel()
        fileWatcher = nil
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
        
        // Load the HTML content from external file
        loadHTMLFromFile(webView: webView)
        
        return webView
    }
    
    private func loadHTMLFromFile(webView: WKWebView) {
        guard let htmlURL = Bundle.module.url(forResource: "chat", withExtension: "html") else {
            print("❌ Could not find chat.html file, falling back to embedded HTML")
            // Fallback to embedded HTML if file not found
            let htmlContent = createFallbackChatHTML()
            webView.loadHTMLString(htmlContent, baseURL: nil)
            return
        }
        
        do {
            let htmlContent = try String(contentsOf: htmlURL)
            webView.loadHTMLString(htmlContent, baseURL: htmlURL.deletingLastPathComponent())
            print("✅ Loaded chat interface from external HTML file")
        } catch {
            print("❌ Error loading HTML file: \(error)")
            // Fallback to embedded HTML if loading fails
            let htmlContent = createFallbackChatHTML()
            webView.loadHTMLString(htmlContent, baseURL: nil)
        }
    }
    
    func updateNSView(_ nsView: WKWebView, context: Context) {
        // Updates handled via JavaScript calls
    }
    
    private func createFallbackChatHTML() -> String {
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>SwiftCog Chat - Fallback</title>
            <style>
                body { 
                    font-family: system-ui; 
                    padding: 20px; 
                    background: #f0f0f0; 
                    text-align: center; 
                }
                .error { color: #e74c3c; margin: 20px 0; }
            </style>
        </head>
        <body>
            <h1>🧠 SwiftCog Chat</h1>
            <div class="error">
                <p>Error: Could not load chat interface from external file.</p>
                <p>Please check that chat.html is properly included in the bundle.</p>
            </div>
            <script>
                // Minimal fallback functions
                function addMessage(content, isUser) {
                    console.log('Message:', content, 'isUser:', isUser);
                }
                function addAIResponse(response) {
                    console.log('AI Response:', response);
                }
                // Minimal message handler
                window.webkit && window.webkit.messageHandlers && 
                window.webkit.messageHandlers.messageHandler && 
                console.log('Message handler available');
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
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationTitle("SwiftCog Chat")
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    func addMessage(_ content: String, isUser: Bool) {
        if !isUser {
            controller.addMessage(content)
        }
    }
} 