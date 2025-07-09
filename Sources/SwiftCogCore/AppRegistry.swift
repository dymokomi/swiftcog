import Foundation

/// Registry for SwiftCog applications
public class AppRegistry {
    public typealias BackendAppFactory = (KernelSystem) async throws -> SwiftCogApp
    public typealias FrontendAppFactory = (KernelSystem) async throws -> SwiftCogApp
    
    private static var registeredBackendApps: [String: BackendAppFactory] = [:]
    private static var registeredFrontendApps: [String: FrontendAppFactory] = [:]
    
    /// Register an app with the registry
    /// - Parameters:
    ///   - name: The name of the app (should match directory name)
    ///   - type: The app type that conforms to SwiftCogApp
    public static func register<T: SwiftCogApp>(
        name: String,
        type: T.Type
    ) {
        registeredBackendApps[name] = { system in
            return try await T.initBackend(system: system)
        }
        registeredFrontendApps[name] = { system in
            return try await T.initFrontend(system: system)
        }
    }
    
    /// Get all registered app names
    public static var availableApps: [String] {
        return Array(registeredBackendApps.keys).sorted()
    }
    
    /// Create a backend instance of a registered app
    /// - Parameters:
    ///   - name: The name of the app to create
    ///   - system: The KernelSystem configured for backend mode
    /// - Returns: An instance of the requested app configured for backend
    /// - Throws: AppLoaderError if the app is not found
    public static func createBackendApp(named name: String, system: KernelSystem) async throws -> SwiftCogApp {
        guard let factory = registeredBackendApps[name] else {
            throw AppLoaderError.appLoadingFailed("Backend app '\(name)' not found in registry. Available apps: \(availableApps.joined(separator: ", "))")
        }
        
        return try await factory(system)
    }
    
    /// Create a frontend instance of a registered app
    /// - Parameters:
    ///   - name: The name of the app to create
    ///   - system: The KernelSystem configured for frontend mode
    /// - Returns: An instance of the requested app configured for frontend
    /// - Throws: AppLoaderError if the app is not found
    public static func createFrontendApp(named name: String, system: KernelSystem) async throws -> SwiftCogApp {
        guard let factory = registeredFrontendApps[name] else {
            throw AppLoaderError.appLoadingFailed("Frontend app '\(name)' not found in registry. Available apps: \(availableApps.joined(separator: ", "))")
        }
        
        return try await factory(system)
    }
    
    /// Check if an app is registered
    /// - Parameter name: The name of the app to check
    /// - Returns: True if the app is registered, false otherwise
    public static func isRegistered(name: String) -> Bool {
        return registeredBackendApps[name] != nil
    }
} 