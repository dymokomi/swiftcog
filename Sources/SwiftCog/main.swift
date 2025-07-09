import Foundation
import SwiftCogCore
import ExampleApp
import Distributed
import ArgumentParser
import DistributedCluster
import DotEnv

@main
struct SwiftCog: AsyncParsableCommand {
    static var configuration = CommandConfiguration(
        abstract: "A Swift-based real-time cognitive architecture.",
        subcommands: [Run.self],
        defaultSubcommand: Run.self
    )
}

extension SwiftCog {
    struct Run: AsyncParsableCommand {
        static var configuration = CommandConfiguration(commandName: "run", abstract: "Run an application.")

        @Argument(help: "The path to the application to run (currently ignored).")
        var appPath: String?
        
        @Option(name: .long, help: "The OpenAI API key. If not provided, it will be read from the OPENAI_API_KEY environment variable.")
        var apiKey: String?

        func run() async throws {
            try DotEnv.load(path: ".env")
            
            guard let finalApiKey = apiKey ?? ProcessInfo.processInfo.environment["OPENAI_API_KEY"] else {
                fatalError("Missing OpenAI API Key. Please provide it using the --api-key option or the OPENAI_API_KEY environment variable.")
            }

            let system = try await KernelSystem(apiKey: finalApiKey)
            // The app's initializer is responsible for setting up the architecture.
            _ = try await ExampleApp(system: system)
            
            print("SwiftCog system starting...")

            // The KernelSystem is responsible for running the application.
            let tasks = system.run()

            // Wait for all sensing tasks to complete
            for task in tasks {
                try await task.value
            }
            
            print("All work complete, shutting down.")
            try await system.actorSystem.shutdown()
        }
    }
}
