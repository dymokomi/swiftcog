import Foundation

// MARK: - Display Command Protocol
public protocol DisplayCommand: Codable, Sendable {
    var type: DisplayCommandType { get }
}

public enum DisplayCommandType: String, Codable, Sendable {
    case showMessage
    case clearScreen
    case updateStatus
    case showThinking
    case hideThinking
}

// MARK: - Specific Display Commands
public struct ShowMessageCommand: DisplayCommand {
    public var type: DisplayCommandType { .showMessage }
    public let message: String
    public let isUser: Bool
    public let timestamp: Date
    
    public init(message: String, isUser: Bool) {
        self.message = message
        self.isUser = isUser
        self.timestamp = Date()
    }
}

public struct ClearScreenCommand: DisplayCommand {
    public var type: DisplayCommandType { .clearScreen }
    
    public init() {}
}

public struct UpdateStatusCommand: DisplayCommand {
    public var type: DisplayCommandType { .updateStatus }
    public let status: String
    
    public init(status: String) {
        self.status = status
    }
}

public struct ShowThinkingCommand: DisplayCommand {
    public var type: DisplayCommandType { .showThinking }
    
    public init() {}
}

public struct HideThinkingCommand: DisplayCommand {
    public var type: DisplayCommandType { .hideThinking }
    
    public init() {}
} 