import Foundation
import Network
import SwiftCogCore

// MARK: - WebSocket Client for Python Server Communication
public class WebSocketClient {
    private let host: String
    private let port: Int
    private var webSocketTask: URLSessionWebSocketTask?
    private let session: URLSession
    
    public weak var messageHandler: AsyncMessageHandler?
    
    public init(host: String = "127.0.0.1", port: Int = 8765) {
        self.host = host
        self.port = port
        self.session = URLSession.shared
    }
    
    public func connect() async throws {
        let url = URL(string: "ws://\(host):\(port)/ws")!
        webSocketTask = session.webSocketTask(with: url)
        
        print("🌐 WebSocket Client: Connecting to \(url)")
        webSocketTask?.resume()
        
        // Start receiving messages
        await startReceiving()
    }
    
    private func startReceiving() async {
        guard let webSocketTask = webSocketTask else { return }
        
        do {
            while true {
                let message = try await webSocketTask.receive()
                
                switch message {
                case .string(let text):
                    await handleMessage(text)
                case .data(let data):
                    if let text = String(data: data, encoding: .utf8) {
                        await handleMessage(text)
                    }
                @unknown default:
                    break
                }
            }
        } catch {
            print("❌ WebSocket Client: Receive error: \(error)")
        }
    }
    
    private func handleMessage(_ text: String) async {
        do {
            let data = text.data(using: .utf8)!
            let pythonMessage = try JSONDecoder().decode(PythonAsyncMessage.self, from: data)
            
            // Convert to kernel message for the message handler
            switch MessageType(rawValue: pythonMessage.type) {
            case .kernelMessage:
                if let kernelMessage = pythonMessage.kernelMessage {
                    print("🌐 WebSocket Client: Received kernel message: '\(kernelMessage.payload)'")
                    try await messageHandler?.handleMessage(kernelMessage)
                }
            default:
                print("❌ WebSocket Client: Unknown message type: \(pythonMessage.type)")
            }
        } catch {
            print("❌ WebSocket Client: Failed to decode message: \(error)")
        }
    }
    
    public func send(_ message: PythonAsyncMessage) async throws {
        guard let webSocketTask = webSocketTask else {
            throw NSError(domain: "WebSocketClient", code: 1, userInfo: [NSLocalizedDescriptionKey: "Not connected"])
        }
        
        let encoder = JSONEncoder()
        let data = try encoder.encode(message)
        let text = String(data: data, encoding: .utf8)!
        
        print("🌐 WebSocket Client: Sending message: \(message.type)")
        try await webSocketTask.send(.string(text))
        print("✅ WebSocket Client: Message sent successfully")
    }
    
    public func disconnect() async throws {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        print("🌐 WebSocket Client: Disconnected")
    }
} 