import Foundation
import Network

// MARK: - Message Types

public struct AsyncMessage: Codable {
    public let type: String
    public let kernelMessage: KernelMessage
    
    public init(type: String, kernelMessage: KernelMessage) {
        self.type = type
        self.kernelMessage = kernelMessage
    }
}

// MARK: - TCP Server (Backend)

public class TCPServer {
    private let listener: NWListener
    private var connections: [NWConnection] = []
    
    public weak var messageHandler: AsyncMessageHandler?
    
    public init(host: String = "127.0.0.1", port: Int = 8080) throws {
        let params = NWParameters.tcp
        params.allowLocalEndpointReuse = true
        
        listener = try NWListener(using: params, on: NWEndpoint.Port(integerLiteral: UInt16(port)))
    }
    
    public func start() async throws {
        listener.stateUpdateHandler = { state in
            switch state {
            case .ready:
                print("TCP server started on port \(self.listener.port!)")
            case .failed(let error):
                print("TCP server failed: \(error)")
            default:
                break
            }
        }
        
        listener.newConnectionHandler = { [weak self] connection in
            self?.handleNewConnection(connection)
        }
        
        listener.start(queue: .main)
        
        // Keep running
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            // This will run indefinitely until server stops
        }
    }
    
    private func handleNewConnection(_ connection: NWConnection) {
        connections.append(connection)
        
        connection.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                self?.startReceiving(connection)
            case .cancelled, .failed:
                self?.connections.removeAll { $0 === connection }
            default:
                break
            }
        }
        
        connection.start(queue: .main)
    }
    
    private func startReceiving(_ connection: NWConnection) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            if let data = data, !data.isEmpty {
                self?.handleMessage(data)
            }
            
            if !isComplete {
                self?.startReceiving(connection)
            }
        }
    }
    
    private func handleMessage(_ data: Data) {
        do {
            // Messages are newline-delimited JSON
            let lines = String(data: data, encoding: .utf8)?.components(separatedBy: "\n") ?? []
            for line in lines {
                guard !line.isEmpty else { continue }
                
                let lineData = line.data(using: .utf8)!
                let message = try JSONDecoder().decode(AsyncMessage.self, from: lineData)
                
                Task {
                    try await messageHandler?.handleMessage(message.kernelMessage)
                }
            }
        } catch {
            print("Failed to decode message: \(error)")
        }
    }
    
    public func sendToClients(_ message: KernelMessage) {
        print("🌐 TCP Server: Sending message to \(connections.count) client(s): '\(message.payload)'")
        let asyncMessage = AsyncMessage(type: "kernelMessage", kernelMessage: message)
        
        do {
            let data = try JSONEncoder().encode(asyncMessage)
            let jsonString = String(data: data, encoding: .utf8)! + "\n"
            let messageData = jsonString.data(using: .utf8)!
            
            for connection in connections {
                connection.send(content: messageData, completion: .contentProcessed { error in
                    if let error = error {
                        print("❌ TCP Server: Failed to send to client: \(error)")
                    } else {
                        print("✅ TCP Server: Message sent successfully")
                    }
                })
            }
        } catch {
            print("❌ TCP Server: Failed to encode message: \(error)")
        }
    }
    
    public func stop() async throws {
        listener.cancel()
        for connection in connections {
            connection.cancel()
        }
        connections.removeAll()
    }
}

// MARK: - TCP Client (Frontend)

public class TCPClient {
    private let host: String
    private let port: Int
    private var connection: NWConnection?
    
    public weak var messageHandler: AsyncMessageHandler?
    
    public init(host: String = "127.0.0.1", port: Int = 8080) {
        self.host = host
        self.port = port
    }
    
    public func connect() async throws {
        let endpoint = NWEndpoint.hostPort(host: NWEndpoint.Host(host), port: NWEndpoint.Port(integerLiteral: UInt16(port)))
        connection = NWConnection(to: endpoint, using: .tcp)
        
        // Wait for connection to be ready
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            var resumed = false
            connection?.stateUpdateHandler = { state in
                if !resumed {
                    switch state {
                    case .ready:
                        resumed = true
                        self.startReceiving()
                        continuation.resume()
                    case .failed(let error):
                        resumed = true
                        continuation.resume(throwing: error)
                    default:
                        break
                    }
                }
            }
            
            connection?.start(queue: .main)
        }
    }
    
    private func startReceiving() {
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            if let data = data, !data.isEmpty {
                Task {
                    await self?.handleMessage(data)
                }
            }
            
            if !isComplete {
                self?.startReceiving()
            }
        }
    }
    
    private func handleMessage(_ data: Data) async {
        do {
            // Messages are newline-delimited JSON
            let lines = String(data: data, encoding: .utf8)?.components(separatedBy: "\n") ?? []
            
            for line in lines {
                guard !line.isEmpty else { continue }
                
                let lineData = line.data(using: .utf8)!
                let message = try JSONDecoder().decode(AsyncMessage.self, from: lineData)
                
                print("🌐 TCP Client: Received message: '\(message.kernelMessage.payload)'")
                try await messageHandler?.handleMessage(message.kernelMessage)
            }
        } catch {
            print("❌ TCP Client: Failed to decode message: \(error)")
        }
    }
    
    public func send(_ message: KernelMessage) async throws {
        print("🌐 TCP Client: Sending message: '\(message.payload)'")
        let asyncMessage = AsyncMessage(type: "kernelMessage", kernelMessage: message)
        let data = try JSONEncoder().encode(asyncMessage)
        let jsonString = String(data: data, encoding: .utf8)! + "\n"
        let messageData = jsonString.data(using: .utf8)!
        
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            connection?.send(content: messageData, completion: .contentProcessed { error in
                if let error = error {
                    print("❌ TCP Client: Failed to send: \(error)")
                    continuation.resume(throwing: error)
                } else {
                    print("✅ TCP Client: Message sent successfully")
                    continuation.resume()
                }
            })
        }
    }
    
    public func disconnect() async throws {
        connection?.cancel()
        connection = nil
    }
}

// MARK: - Message Handler Protocol

public protocol AsyncMessageHandler: AnyObject {
    func handleMessage(_ message: KernelMessage) async throws
} 