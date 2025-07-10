import Foundation

public class KernelSystem: AsyncMessageHandler, MessageSystem {
    private var kernels: [KernelID: any Kernel] = [:]
    private var sensingKernels: [SensingKernel] = []
    private var connections: [KernelID: KernelID] = [:]
    private let apiKey: String
    
    // TCP communication
    private var tcpServer: TCPServer?
    private let host: String
    private let port: Int

    public init(apiKey: String, host: String = "127.0.0.1", port: Int = 8080) {
        self.apiKey = apiKey
        self.host = host
        self.port = port
        
        do {
            tcpServer = try TCPServer(host: host, port: port)
            tcpServer?.messageHandler = self
        } catch {
            print("Failed to create TCP server: \(error)")
        }
    }

    // MARK: - Backend Kernels
    
    public func createExpressionKernel(customHandler: ((KernelMessage, ExpressionKernel) async throws -> Void)? = nil) async throws -> ExpressionKernel {
        let kernel = ExpressionKernel(system: self, customHandler: customHandler)
        let kernelId = kernel.getKernelId()
        kernels[kernelId] = kernel
        return kernel
    }

    public func createMotorKernel(customHandler: ((KernelMessage, MotorKernel) async throws -> Void)? = nil) async throws -> MotorKernel {
        let kernel = MotorKernel(system: self, customHandler: customHandler)
        let kernelId = kernel.getKernelId()
        kernels[kernelId] = kernel
        return kernel
    }

    public func createExecutiveKernel(customHandler: ((KernelMessage, ExecutiveKernel) async throws -> Void)? = nil) async throws -> ExecutiveKernel {
        let kernel = ExecutiveKernel(system: self, customHandler: customHandler)
        let kernelId = kernel.getKernelId()
        kernels[kernelId] = kernel
        return kernel
    }

    public func createSensingKernel(customHandler: ((KernelMessage, SensingKernel) async throws -> Void)? = nil) async throws -> SensingKernel {
        let kernel = SensingKernel(system: self, apiKey: apiKey, customHandler: customHandler)
        let kernelId = kernel.getKernelId()
        kernels[kernelId] = kernel
        sensingKernels.append(kernel)
        return kernel
    }
    

    
    // MARK: - TCP Communication
    
    public func startTCPServer() async throws {
        guard let server = tcpServer else { return }
        try await server.start()
    }
    
    public func sendToFrontend(_ message: KernelMessage) {
        tcpServer?.sendToClients(message)
    }
    
    // MARK: - AsyncMessageHandler
    
    public func handleMessage(_ message: KernelMessage) async throws {
        print("🔄 KernelSystem.handleMessage() - Message: \(message.sourceKernelId) -> '\(message.payload)'")
        
        // Backend received message from frontend - route to appropriate kernel
        print("📥 Backend routing message to SensingKernel")
        if let sensingKernel = sensingKernels.first {
            try await sensingKernel.receive(message: message)
        } else {
            print("❌ No sensing kernel available on backend!")
        }
    }
    
    // MARK: - Local Message Routing
    
    public func connect(from source: any Kernel, to destination: any Kernel) async throws {
        let sourceId = source.getKernelId()
        let destinationId = destination.getKernelId()
        connections[sourceId] = destinationId
        print("🔗 Connected \(sourceId) -> \(destinationId)")
    }

    public func emit(message: KernelMessage, from emitter: any Kernel) async throws {
        let emitterId = emitter.getKernelId()
        print("🚀 KernelSystem.emit() - From: \(emitterId), Message: '\(message.payload)'")
        
        // Backend: Local routing then send to frontend asynchronously
        if let destinationId = connections[emitterId],
           let destinationKernel = kernels[destinationId] {
            // Forward to next kernel in pipeline
            print("🔀 Backend routing \(emitterId) -> \(destinationId)")
            try await destinationKernel.receive(message: message)
        } else {
            print("⚠️ No connection found for \(emitterId)")
        }
        
        // If this is the final kernel (like ExpressionKernel), send to frontend asynchronously
        if emitter is ExpressionKernel {
            print("📤 Backend sending to frontend via TCP (ExpressionKernel)")
            sendToFrontend(message)
        }
    }

    @discardableResult
    public func run() -> [Task<Void, Error>] {
        var tasks: [Task<Void, Error>] = []
        
        // Backend mode: Start TCP server
        let serverTask = Task {
            try await startTCPServer()
        }
        tasks.append(serverTask)
        
        return tasks
    }
    
    public func shutdown() async throws {
        if let server = tcpServer {
            try await server.stop()
        }
    }
} 