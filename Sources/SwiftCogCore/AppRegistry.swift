import Foundation

/// Registry for SwiftCog applications
public class AppRegistry {
    public typealias AppFactory = (KernelSystem) async throws -> SwiftCogApp
    
    private static var registeredApps: [String: AppFactory] = [:]
    
    /// Register an app with the registry
    /// - Parameters:
    ///   - name: The name of the app (should match directory name)
    ///   - factory: A closure that creates an instance of the app
    public static func register<T: SwiftCogApp>(
        name: String,
        type: T.Type
    ) {
        registeredApps[name] = { system in
            return try await T(system: system)
        }
    }
    
    /// Get all registered app names
    public static var availableApps: [String] {
        return Array(registeredApps.keys).sorted()
    }
    
    /// Create an instance of a registered app
    /// - Parameters:
    ///   - name: The name of the app to create
    ///   - system: The KernelSystem to pass to the app
    /// - Returns: An instance of the requested app
    /// - Throws: AppLoaderError if the app is not found
    public static func createApp(named name: String, system: KernelSystem) async throws -> SwiftCogApp {
        guard let factory = registeredApps[name] else {
            throw AppLoaderError.appLoadingFailed("App '\(name)' not found in registry. Available apps: \(availableApps.joined(separator: ", "))")
        }
        
        return try await factory(system)
    }
    
    /// Check if an app is registered
    /// - Parameter name: The name of the app to check
    /// - Returns: True if the app is registered, false otherwise
    public static func isRegistered(name: String) -> Bool {
        return registeredApps[name] != nil
    }
} 