import Foundation
import SwiftCogCore
import Network

// Message types for communicating with Python server
public enum MessageType: String, Codable {
    case kernelMessage = "kernelMessage"
    case error = "error"
}

// Simplified AsyncMessage structure for Python server communication
public struct PythonAsyncMessage: Codable {
    let type: String
    let kernelMessage: KernelMessage?
    let errorMessage: String?
    let success: Bool?
    let message: String?
    
    init(type: MessageType, kernelMessage: KernelMessage? = nil, errorMessage: String? = nil, success: Bool? = nil, message: String? = nil) {
        self.type = type.rawValue
        self.kernelMessage = kernelMessage
        self.errorMessage = errorMessage
        self.success = success
        self.message = message
    }
    
    // Custom coding keys to match Python server expectations
    enum CodingKeys: String, CodingKey {
        case type
        case kernelMessage = "kernel_message"
        case errorMessage = "error_message"
        case success
        case message
    }
}

public class FrontendKernelSystem: AsyncMessageHandler {
    private var webSocketClient: WebSocketClient?
    private let host: String
    private let port: Int
    private var displayCommandHandler: ((DisplayCommand) -> Void)?
    private var errorHandler: ((String) -> Void)?
    
    public init(host: String = "127.0.0.1", port: Int = 8000) {
        self.host = host
        self.port = port
        
        webSocketClient = WebSocketClient(host: host, port: port)
        webSocketClient?.messageHandler = self
    }
    
    // MARK: - Display Command Handling
    
    public func setDisplayCommandHandler(_ handler: @escaping (DisplayCommand) -> Void) {
        self.displayCommandHandler = handler
    }
    
    public func setErrorHandler(_ handler: @escaping (String) -> Void) {
        self.errorHandler = handler
    }
    
    private func parseDisplayCommand(_ payload: String) -> DisplayCommand? {
        return DisplayCommandFactory.createDisplayCommand(from: payload)
    }
    
    // MARK: - WebSocket Client Communication
    
    public func connectWebSocketClient() async throws {
        guard let client = webSocketClient else { return }
        try await client.connect()
    }
    
    public func sendToBackend(_ message: String) async throws {
        let kernelMessage = KernelMessage(sourceKernelId: .sensingInterface, payload: message)
        let asyncMessage = PythonAsyncMessage(type: .kernelMessage, kernelMessage: kernelMessage)
        try await sendAsyncMessage(asyncMessage)
    }
    
    private func sendAsyncMessage(_ message: PythonAsyncMessage) async throws {
        guard let client = webSocketClient else { 
            throw NSError(domain: "FrontendKernelSystem", code: 1, userInfo: [NSLocalizedDescriptionKey: "WebSocket client not available"])
        }
        
        try await client.send(message)
    }
    
    // MARK: - AsyncMessageHandler
    
    public func handleMessage(_ message: KernelMessage) async throws {
        print("FrontendKernelSystem.handleMessage() - Message: \(message.sourceKernelId) -> '\(message.payload)'")
        
        // Try to parse as PythonAsyncMessage first (for Python server)
        if let data = message.payload.data(using: .utf8),
           let pythonMessage = try? JSONDecoder().decode(PythonAsyncMessage.self, from: data) {
            await handlePythonAsyncMessage(pythonMessage)
        } else {
            // Fallback to regular display command parsing (for direct kernel messages)
            if let displayCommand = parseDisplayCommand(message.payload) {
                await MainActor.run {
                    displayCommandHandler?(displayCommand)
                }
            } else {
                print("Failed to parse display command from: \(message.payload)")
            }
        }
    }
    
    private func handlePythonAsyncMessage(_ message: PythonAsyncMessage) async {
        switch MessageType(rawValue: message.type) {
        case .kernelMessage:
            if let kernelMessage = message.kernelMessage {
                if let displayCommand = parseDisplayCommand(kernelMessage.payload) {
                    await MainActor.run {
                        displayCommandHandler?(displayCommand)
                    }
                }
            }
        case .error:
            let errorText = message.errorMessage ?? message.message ?? "Unknown error"
            print("Error: \(errorText)")
            await MainActor.run {
                errorHandler?(errorText)
            }
        default:
            print("Unknown Python message type: \(message.type)")
        }
    }
    
    // MARK: - System Management
    
    @discardableResult
    public func run() -> [Task<Void, Error>] {
        var tasks: [Task<Void, Error>] = []
        
        // Frontend mode: Connect to backend
        let clientTask = Task {
            try await connectWebSocketClient()
        }
        tasks.append(clientTask)
        
        return tasks
    }
    
    public func shutdown() async throws {
        if let client = webSocketClient {
            try await client.disconnect()
        }
    }
} 