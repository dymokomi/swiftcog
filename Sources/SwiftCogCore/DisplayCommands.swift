import Foundation

// MARK: - Display Command Protocol
public protocol DisplayCommand: Codable, Sendable {
    var type: DisplayCommandType { get }
}

public enum DisplayCommandType: String, Codable, Sendable {
    case textBubble
    case clearScreen
    case highlightText
    case displayList
    case updateStatus
    case showThinking
    case hideThinking
    // Keep old showMessage for backward compatibility
    case showMessage
}

// MARK: - Text Bubble Command
public struct TextBubbleCommand: DisplayCommand {
    public var type: DisplayCommandType { .textBubble }
    public let text: String
    public let isUser: Bool
    public let timestamp: Date
    
    public init(text: String, isUser: Bool) {
        self.text = text
        self.isUser = isUser
        self.timestamp = Date()
    }
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
        try container.encode(text, forKey: .text)
        try container.encode(isUser, forKey: .isUser)
        try container.encode(timestamp, forKey: .timestamp)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        text = try container.decode(String.self, forKey: .text)
        isUser = try container.decode(Bool.self, forKey: .isUser)
        timestamp = try container.decode(Date.self, forKey: .timestamp)
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, text, isUser, timestamp
    }
}

// MARK: - Clear Screen Command
public struct ClearScreenCommand: DisplayCommand {
    public var type: DisplayCommandType { .clearScreen }
    
    public init() {}
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        // No additional fields to decode
    }
    
    private enum CodingKeys: String, CodingKey {
        case type
    }
}

// MARK: - Highlight Text Command
public struct HighlightTextCommand: DisplayCommand {
    public var type: DisplayCommandType { .highlightText }
    public let text: String
    public let highlightColor: String
    
    public init(text: String, highlightColor: String = "#ffff00") {
        self.text = text
        self.highlightColor = highlightColor
    }
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
        try container.encode(text, forKey: .text)
        try container.encode(highlightColor, forKey: .highlightColor)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        text = try container.decode(String.self, forKey: .text)
        highlightColor = try container.decode(String.self, forKey: .highlightColor)
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, text, highlightColor
    }
}

// MARK: - Display List Command
public struct DisplayListCommand: DisplayCommand {
    public var type: DisplayCommandType { .displayList }
    public let items: [ListItem]
    public let allowSelection: Bool
    
    public init(items: [ListItem], allowSelection: Bool = false) {
        self.items = items
        self.allowSelection = allowSelection
    }
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
        try container.encode(items, forKey: .items)
        try container.encode(allowSelection, forKey: .allowSelection)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        items = try container.decode([ListItem].self, forKey: .items)
        allowSelection = try container.decode(Bool.self, forKey: .allowSelection)
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, items, allowSelection
    }
}

public struct ListItem: Codable, Sendable {
    public let id: String
    public let text: String
    public let isSelected: Bool
    
    public init(id: String, text: String, isSelected: Bool = false) {
        self.id = id
        self.text = text
        self.isSelected = isSelected
    }
}

// MARK: - Legacy Commands (for backward compatibility)
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
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
        try container.encode(message, forKey: .message)
        try container.encode(isUser, forKey: .isUser)
        try container.encode(timestamp, forKey: .timestamp)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        message = try container.decode(String.self, forKey: .message)
        isUser = try container.decode(Bool.self, forKey: .isUser)
        timestamp = try container.decode(Date.self, forKey: .timestamp)
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, message, isUser, timestamp
    }
}

public struct UpdateStatusCommand: DisplayCommand {
    public var type: DisplayCommandType { .updateStatus }
    public let status: String
    
    public init(status: String) {
        self.status = status
    }
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
        try container.encode(status, forKey: .status)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        status = try container.decode(String.self, forKey: .status)
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, status
    }
}

public struct ShowThinkingCommand: DisplayCommand {
    public var type: DisplayCommandType { .showThinking }
    
    public init() {}
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        // No additional fields to decode
    }
    
    private enum CodingKeys: String, CodingKey {
        case type
    }
}

public struct HideThinkingCommand: DisplayCommand {
    public var type: DisplayCommandType { .hideThinking }
    
    public init() {}
    
    // Custom encoding to include type field
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
    }
    
    // Custom decoding
    public init(from decoder: Decoder) throws {
        // No additional fields to decode
    }
    
    private enum CodingKeys: String, CodingKey {
        case type
    }
}

// MARK: - Display Command Factory
public struct DisplayCommandFactory {
    public static func createDisplayCommand(from payload: String) -> DisplayCommand? {
        // Try to decode as JSON first
        guard let data = payload.data(using: .utf8) else {
            // Fallback: treat as plain text message
            return TextBubbleCommand(text: payload, isUser: false)
        }
        
        let decoder = JSONDecoder()
        
        do {
            // First, try to decode just the type field
            let typeContainer = try decoder.decode(TypeContainer.self, from: data)
            
            // Now decode the specific command based on type
            switch typeContainer.type {
            case .textBubble:
                return try decoder.decode(TextBubbleCommand.self, from: data)
            case .clearScreen:
                return try decoder.decode(ClearScreenCommand.self, from: data)
            case .highlightText:
                return try decoder.decode(HighlightTextCommand.self, from: data)
            case .displayList:
                return try decoder.decode(DisplayListCommand.self, from: data)
            case .updateStatus:
                return try decoder.decode(UpdateStatusCommand.self, from: data)
            case .showThinking:
                return try decoder.decode(ShowThinkingCommand.self, from: data)
            case .hideThinking:
                return try decoder.decode(HideThinkingCommand.self, from: data)
            case .showMessage:
                return try decoder.decode(ShowMessageCommand.self, from: data)
            }
        } catch {
            print("Failed to decode display command: \(error)")
            // Fallback: treat as plain text message
            return TextBubbleCommand(text: payload, isUser: false)
        }
    }
    
    private struct TypeContainer: Codable {
        let type: DisplayCommandType
    }
} 