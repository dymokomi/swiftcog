import Foundation
import ArgumentParser

// MARK: - App Mode
public enum AppMode: String, CaseIterable, ExpressibleByArgument {
    case backend = "backend"
    case frontend = "frontend"
    
    public var description: String {
        switch self {
        case .backend:
            return "Backend server with core kernels"
        case .frontend:
            return "Frontend client connecting to backend"
        }
    }
    
    public var defaultValueDescription: String {
        return description
    }
}

/// Protocol that all SwiftCog applications must conform to
public protocol SwiftCogApp: AnyObject {
    /// Initialize the app for backend mode with core cognitive kernels
    /// - Parameter system: The KernelSystem configured for backend mode
    static func initBackend(system: KernelSystem) async throws -> Self
    
    /// Initialize the app for frontend mode with interface kernels
    /// - Parameter system: The KernelSystem configured for frontend mode  
    static func initFrontend(system: KernelSystem) async throws -> Self
    
    /// Optional method to get app metadata
    static var appName: String { get }
    static var appDescription: String { get }
}

/// Default implementations
public extension SwiftCogApp {
    static var appName: String { 
        return String(describing: Self.self) 
    }
    
    static var appDescription: String { 
        return "A SwiftCog application" 
    }
} 