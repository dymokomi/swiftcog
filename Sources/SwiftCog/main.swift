import Foundation
import SwiftCogCore
import Examples
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

        @Argument(help: "The path to the application directory to run, or app name if using built-in apps.")
        var appPath: String?
        
        @Option(name: .long, help: "The OpenAI API key. If not provided, it will be read from the OPENAI_API_KEY environment variable.")
        var apiKey: String?

        func run() async throws {
            try DotEnv.load(path: ".env")
            
            guard let finalApiKey = apiKey ?? ProcessInfo.processInfo.environment["OPENAI_API_KEY"] else {
                fatalError("Missing OpenAI API Key. Please provide it using the --api-key option or the OPENAI_API_KEY environment variable.")
            }

            // Initialize example apps registry
            Examples.initialize()
            
            let system = try await KernelSystem(apiKey: finalApiKey)
            
            // Determine which app to load
            let app: SwiftCogApp
            if let appPath = appPath {
                // Check if it's a directory path or an app name
                if FileManager.default.fileExists(atPath: appPath) {
                    // It's a directory path, try to load from path
                    print("Loading app from directory: \(appPath)")
                    app = try await AppLoader.loadApp(from: appPath, system: system)
                } else {
                    // It's an app name, try to load from registry
                    print("Loading app by name: \(appPath)")
                    app = try await AppLoader.loadApp(named: appPath, system: system)
                }
            } else {
                // No app specified, list available apps and load ExampleApp as default
                print("No app specified. Available apps: \(AppRegistry.availableApps.joined(separator: ", "))")
                print("Loading default app: ExampleApp")
                app = try await AppLoader.loadApp(named: "ExampleApp", system: system)
            }
            
            print("SwiftCog system starting with app: \(type(of: app))...")

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
