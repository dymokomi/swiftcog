import Foundation

public class KernelSystem: AsyncMessageHandler {
    public let mode: AppMode
    private var kernels: [KernelID: any Kernel] = [:]
    private var sensingKernels: [SensingKernel] = []
    private var sensingInterfaceKernels: [SensingInterfaceKernel] = []
    private var connections: [KernelID: KernelID] = [:]
    private let apiKey: String
    
    // TCP communication
    private var tcpServer: TCPServer?
    private var tcpClient: TCPClient?
    private let host: String
    private let port: Int

    public init(apiKey: String, mode: AppMode = .backend, host: String = "127.0.0.1", port: Int = 8080) {
        self.apiKey = apiKey
        self.mode = mode
        self.host = host
        self.port = port
        
        if mode == .backend {
            do {
                tcpServer = try TCPServer(host: host, port: port)
                tcpServer?.messageHandler = self
            } catch {
                print("Failed to create TCP server: \(error)")
            }
        } else {
            tcpClient = TCPClient(host: host, port: port)
            tcpClient?.messageHandler = self
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
    
    // MARK: - Frontend Interface Kernels
    
    public func createSensingInterfaceKernel(customHandler: ((KernelMessage, SensingInterfaceKernel) async throws -> Void)? = nil, speechInputCallback: ((String) -> Void)? = nil) async throws -> SensingInterfaceKernel {
        let kernel = SensingInterfaceKernel(system: self, apiKey: apiKey, customHandler: customHandler, speechInputCallback: speechInputCallback)
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
    
    // MARK: - TCP Communication
    
    public func startTCPServer() async throws {
        guard mode == .backend, let server = tcpServer else { return }
        try await server.start()
    }
    
    public func connectTCPClient() async throws {
        guard mode == .frontend, let client = tcpClient else { return }
        try await client.connect()
    }
    
    public func sendToBackend(_ message: KernelMessage) async throws {
        try await tcpClient?.send(message)
    }
    
    public func sendToFrontend(_ message: KernelMessage) {
        tcpServer?.sendToClients(message)
    }
    
    // MARK: - AsyncMessageHandler
    
    public func handleMessage(_ message: KernelMessage) async throws {
        print("🔄 KernelSystem.handleMessage() - Mode: \(mode), Message: \(message.sourceKernelId) -> '\(message.payload)'")
        
        if mode == .backend {
            // Backend received message from frontend - route to appropriate kernel
            print("📥 Backend routing message to SensingKernel")
            if let sensingKernel = sensingKernels.first {
                try await sensingKernel.receive(message: message)
            } else {
                print("❌ No sensing kernel available on backend!")
            }
        } else {
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
        print("🚀 KernelSystem.emit() - From: \(emitterId), Mode: \(mode), Message: '\(message.payload)'")
        
        if mode == .frontend {
            // Frontend: Send to backend via TCP
            print("📤 Frontend sending to backend via TCP")
            try await sendToBackend(message)
        } else {
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
    }

    @discardableResult
    public func run() -> [Task<Void, Error>] {
        var tasks: [Task<Void, Error>] = []
        
        if mode == .backend {
            // Backend mode: Start TCP server
            let serverTask = Task {
                try await startTCPServer()
            }
            tasks.append(serverTask)
        } else {
            // Frontend mode: Connect to backend and start speech recognition
            let clientTask = Task {
                try await connectTCPClient()
            }
            tasks.append(clientTask)
            
            // Start speech recognition tasks
            for sensingInterfaceKernel in sensingInterfaceKernels {
                let task = Task.detached {
                    // Give TCP time to connect
                    try await Task.sleep(for: .seconds(2))
                    
                    do {
                        try await sensingInterfaceKernel.startSensing()
                    } catch {
                        print("SensingInterfaceKernel failed with error: \(error)")
                        throw error
                    }
                }
                tasks.append(task)
            }
        }
        
        return tasks
    }
    
    public func shutdown() async throws {
        if let server = tcpServer {
            try await server.stop()
        }
        if let client = tcpClient {
            try await client.disconnect()
        }
    }
} 