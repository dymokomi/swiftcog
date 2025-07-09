import SwiftCogCore
import Examples
import ArgumentParser
import DotEnv
import Foundation
import AppKit

@main
struct SwiftCogCLI: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "swiftcog",
        abstract: "SwiftCog - Cognitive AI System with separated frontend/backend processes"
    )
    
    @Option(name: .shortAndLong, help: "Specify backend or frontend mode")
    var mode: AppMode = .backend
    
    @Option(name: .long, help: "TCP host")
    var host: String = "127.0.0.1"
    
    @Option(name: .long, help: "TCP port")
    var port: Int = 8080
    
    func run() async throws {
        // Load environment variables
        try DotEnv.load(path: ".env")
        
        // Check for OpenAI API key
        guard let apiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"],
              !apiKey.isEmpty else {
            print("Error: OPENAI_API_KEY environment variable is not set")
            print("Please set your OpenAI API key in the .env file or environment")
            throw ExitCode.failure
        }
        
        print("Starting SwiftCog in \(mode.rawValue) mode")
        print("TCP: \(host):\(port)")
        
        // Create kernel system with TCP configuration
        let system = KernelSystem(apiKey: apiKey, mode: mode, host: host, port: port)
        
        do {
            // Create and run the app based on mode
            if mode == .backend {
                let _ = try await ExampleApp.initBackend(system: system)
                let tasks = system.run()
                print("Backend running - listening for TCP connections")
                
                // Wait for any task to complete or fail
                try await withThrowingTaskGroup(of: Void.self) { group in
                    for task in tasks {
                        group.addTask {
                            try await task.value
                        }
                    }
                    
                    // For backend, just wait indefinitely (until manually stopped)
                    let infiniteTask = Task {
                        while true {
                            try await Task.sleep(for: .seconds(1))
                        }
                    }
                    
                    group.addTask {
                        try await infiniteTask.value
                    }
                    
                    // Wait for the first task to complete (which should never happen for backend)
                    try await group.next()
                }
            } else {
                let app = try await ExampleApp.initFrontend(system: system)
                let tasks = system.run()
                print("Frontend starting - connecting to backend and launching chat window")
                
                // Launch the SwiftUI chat window
                app.launchChatWindow()
                
                // Wait for all frontend tasks to complete
                try await withThrowingTaskGroup(of: Void.self) { group in
                    for task in tasks {
                        group.addTask {
                            try await task.value
                        }
                    }
                    
                    // Wait for all tasks to complete
                    for try await _ in group {
                        // Tasks completed
                    }
                }
                
                print("Frontend session completed")
            }
        } catch {
            print("Error: \(error)")
            try await system.shutdown()
            throw ExitCode.failure
        }
    }
}
