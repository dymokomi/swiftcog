import Foundation

/// Error types for app loading
public enum AppLoaderError: Error, LocalizedError {
    case appDirectoryNotFound(String)
    case noAppFileFound(String)
    case multipleAppFilesFound([String])
    case appLoadingFailed(String)
    case appNotConformingToProtocol(String)
    
    public var errorDescription: String? {
        switch self {
        case .appDirectoryNotFound(let path):
            return "App directory not found: \(path)"
        case .noAppFileFound(let path):
            return "No app file found in: \(path)"
        case .multipleAppFilesFound(let files):
            return "Multiple app files found: \(files.joined(separator: ", ")). Please ensure only one main app file exists."
        case .appLoadingFailed(let reason):
            return "Failed to load app: \(reason)"
        case .appNotConformingToProtocol(let className):
            return "App class \(className) does not conform to SwiftCogApp protocol"
        }
    }
}

/// Information about a discovered app
public struct AppInfo {
    public let name: String
    public let path: String
    public let mainFile: String
    
    public init(name: String, path: String, mainFile: String) {
        self.name = name
        self.path = path
        self.mainFile = mainFile
    }
}

/// Loads SwiftCog applications dynamically
public class AppLoader {
    
    /// Discover apps in a given directory
    /// - Parameter appsDirectory: Path to the directory containing apps
    /// - Returns: Array of discovered app information
    public static func discoverApps(in appsDirectory: String) throws -> [AppInfo] {
        let fileManager = FileManager.default
        
        guard fileManager.fileExists(atPath: appsDirectory) else {
            throw AppLoaderError.appDirectoryNotFound(appsDirectory)
        }
        
        var discoveredApps: [AppInfo] = []
        
        let contents = try fileManager.contentsOfDirectory(atPath: appsDirectory)
        
        for item in contents {
            let itemPath = "\(appsDirectory)/\(item)"
            var isDirectory: ObjCBool = false
            
            if fileManager.fileExists(atPath: itemPath, isDirectory: &isDirectory) && isDirectory.boolValue {
                // This is a directory, check if it contains an app
                if let appInfo = try discoverAppInDirectory(itemPath) {
                    discoveredApps.append(appInfo)
                }
            }
        }
        
        return discoveredApps
    }
    
    /// Discover an app in a specific directory
    /// - Parameter appDirectory: Path to the app directory
    /// - Returns: AppInfo if a valid app is found, nil otherwise
    private static func discoverAppInDirectory(_ appDirectory: String) throws -> AppInfo? {
        let fileManager = FileManager.default
        let contents = try fileManager.contentsOfDirectory(atPath: appDirectory)
        
        // Look for Swift files that might be the main app file
        let swiftFiles = contents.filter { $0.hasSuffix(".swift") }
        
        if swiftFiles.isEmpty {
            return nil // No Swift files found, skip this directory
        }
        
        // Look for a file that might be the main app file
        // Priority: AppName.swift, main.swift, or the only .swift file
        let appName = URL(fileURLWithPath: appDirectory).lastPathComponent
        let mainFile: String
        
        if swiftFiles.contains("\(appName).swift") {
            mainFile = "\(appName).swift"
        } else if swiftFiles.contains("main.swift") {
            mainFile = "main.swift"
        } else if swiftFiles.count == 1 {
            mainFile = swiftFiles[0]
        } else {
            // Multiple Swift files and no clear main file
            throw AppLoaderError.multipleAppFilesFound(swiftFiles)
        }
        
        return AppInfo(name: appName, path: appDirectory, mainFile: mainFile)
    }
    
    /// Load an app from a directory path using the registry
    /// - Parameters:
    ///   - appPath: Path to the app directory
    ///   - system: KernelSystem to initialize the app with
    /// - Returns: The loaded app instance
    public static func loadApp(from appPath: String, system: KernelSystem) async throws -> SwiftCogApp {
        let fileManager = FileManager.default
        
        guard fileManager.fileExists(atPath: appPath) else {
            throw AppLoaderError.appDirectoryNotFound(appPath)
        }
        
        let appInfo = try discoverAppInDirectory(appPath)
        guard let appInfo = appInfo else {
            throw AppLoaderError.noAppFileFound(appPath)
        }
        
        // Use the app name to look up in the registry
        let appName = appInfo.name
        return try await AppRegistry.createApp(named: appName, system: system)
    }
    
    /// Load an app by name (without requiring a directory path)
    /// - Parameters:
    ///   - appName: Name of the app to load
    ///   - system: KernelSystem to initialize the app with
    /// - Returns: The loaded app instance
    public static func loadApp(named appName: String, system: KernelSystem) async throws -> SwiftCogApp {
        return try await AppRegistry.createApp(named: appName, system: system)
    }
} 