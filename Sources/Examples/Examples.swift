import Foundation
import SwiftCogCore

/// Module that exports all example applications
public enum Examples {
    /// Initialize all example applications (register them with the app registry)
    public static func initialize() {
        ExampleApp.register()
    }
    
    /// Get a list of all available example apps
    public static var availableApps: [String] {
        return ["ExampleApp"]
    }
} 