import Foundation

/// Protocol that all SwiftCog applications must conform to
public protocol SwiftCogApp: AnyObject {
    /// Initialize the app with a KernelSystem
    /// - Parameter system: The KernelSystem to use for this app
    init(system: KernelSystem) async throws
    
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