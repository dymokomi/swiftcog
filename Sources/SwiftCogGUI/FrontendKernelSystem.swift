import Foundation
import SwiftCogCore

public class FrontendKernelSystem: AsyncMessageHandler {
    private var tcpClient: TCPClient?
    private let host: String
    private let port: Int
    private var displayCommandHandler: ((DisplayCommand) -> Void)?
    
    public init(host: String = "127.0.0.1", port: Int = 8080) {
        self.host = host
        self.port = port
        
        tcpClient = TCPClient(host: host, port: port)
        tcpClient?.messageHandler = self
    }
    
    // MARK: - Display Command Handling
    
    public func setDisplayCommandHandler(_ handler: @escaping (DisplayCommand) -> Void) {
        self.displayCommandHandler = handler
    }
    
    private func parseDisplayCommand(_ payload: String) -> DisplayCommand? {
        return DisplayCommandFactory.createDisplayCommand(from: payload)
    }
    
    // MARK: - TCP Client Communication
    
    public func connectTCPClient() async throws {
        guard let client = tcpClient else { return }
        try await client.connect()
    }
    
    public func sendToBackend(_ message: String) async throws {
        let kernelMessage = KernelMessage(sourceKernelId: .sensingInterface, payload: message)
        try await tcpClient?.send(kernelMessage)
    }
    
    // MARK: - AsyncMessageHandler
    
    public func handleMessage(_ message: KernelMessage) async throws {
        print("🔄 FrontendKernelSystem.handleMessage() - Message: \(message.sourceKernelId) -> '\(message.payload)'")
        
        // Parse display command from backend and send to UI
        if let displayCommand = parseDisplayCommand(message.payload) {
            await MainActor.run {
                displayCommandHandler?(displayCommand)
            }
        } else {
            print("❌ Failed to parse display command from: \(message.payload)")
        }
    }
    
    // MARK: - System Management
    
    @discardableResult
    public func run() -> [Task<Void, Error>] {
        var tasks: [Task<Void, Error>] = []
        
        // Frontend mode: Connect to backend
        let clientTask = Task {
            try await connectTCPClient()
        }
        tasks.append(clientTask)
        
        return tasks
    }
    
    public func shutdown() async throws {
        if let client = tcpClient {
            try await client.disconnect()
        }
    }
} 