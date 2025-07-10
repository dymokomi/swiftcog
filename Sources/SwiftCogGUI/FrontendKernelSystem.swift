import Foundation
import SwiftCogCore

public class FrontendKernelSystem: AsyncMessageHandler, MessageSystem {
    private var kernels: [KernelID: any Kernel] = [:]
    private var sensingInterfaceKernels: [SensingInterfaceKernel] = []
    private var tcpClient: TCPClient?
    private let host: String
    private let port: Int
    
    public init(host: String = "127.0.0.1", port: Int = 8080) {
        self.host = host
        self.port = port
        
        tcpClient = TCPClient(host: host, port: port)
        tcpClient?.messageHandler = self
    }
    
    // MARK: - Frontend Interface Kernels
    
    public func createSensingInterfaceKernel(customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)? = nil) async throws -> SensingInterfaceKernel {
        let kernel = SensingInterfaceKernel(system: self, customHandler: customHandler)
        let kernelId = kernel.getKernelId()
        kernels[kernelId] = kernel
        sensingInterfaceKernels.append(kernel)
        return kernel
    }
    
    public func createExpressionInterfaceKernel(customHandler: ((KernelMessage, ExpressionInterfaceKernel) async throws -> Void)? = nil) async throws -> ExpressionInterfaceKernel {
        let kernel = ExpressionInterfaceKernel(system: self, customHandler: customHandler)
        let kernelId = kernel.getKernelId()
        kernels[kernelId] = kernel
        return kernel
    }
    
    // MARK: - TCP Client Communication
    
    public func connectTCPClient() async throws {
        guard let client = tcpClient else { return }
        try await client.connect()
    }
    
    public func sendToBackend(_ message: KernelMessage) async throws {
        try await tcpClient?.send(message)
    }
    
    // MARK: - AsyncMessageHandler
    
    public func handleMessage(_ message: KernelMessage) async throws {
        print("🔄 FrontendKernelSystem.handleMessage() - Message: \(message.sourceKernelId) -> '\(message.payload)'")
        
        // Frontend received message from backend - route to interface kernels
        print("📥 Frontend routing message to ExpressionInterfaceKernel")
        var foundKernel = false
        for (_, kernel) in kernels {
            if let expressionInterface = kernel as? ExpressionInterfaceKernel {
                print("✅ Found ExpressionInterfaceKernel, sending message")
                try await expressionInterface.receive(message: message)
                foundKernel = true
            }
        }
        if !foundKernel {
            print("❌ No ExpressionInterfaceKernel found on frontend!")
        }
    }
    
    // MARK: - Message Emission
    
    public func emit(message: KernelMessage, from emitter: any Kernel) async throws {
        let emitterId = emitter.getKernelId()
        print("🚀 FrontendKernelSystem.emit() - From: \(emitterId), Message: '\(message.payload)'")
        
        // Frontend: Send to backend via TCP
        print("📤 Frontend sending to backend via TCP")
        try await sendToBackend(message)
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