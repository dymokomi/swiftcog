import Foundation

public struct KernelMessage: Codable, Sendable {
    public let id: UUID
    public let sourceKernelId: KernelID
    public let payload: String
    public let timestamp: Date
    
    public init(id: UUID = UUID(), sourceKernelId: KernelID, payload: String) {
        self.id = id
        self.sourceKernelId = sourceKernelId
        self.payload = payload
        self.timestamp = Date()
    }
    
    // Custom coding keys to match Python server format
    enum CodingKeys: String, CodingKey {
        case id
        case sourceKernelId
        case payload
        case timestamp
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(sourceKernelId, forKey: .sourceKernelId)
        try container.encode(payload, forKey: .payload)
        
        // Encode timestamp as ISO string to match Python server
        let formatter = ISO8601DateFormatter()
        try container.encode(formatter.string(from: timestamp), forKey: .timestamp)
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        sourceKernelId = try container.decode(KernelID.self, forKey: .sourceKernelId)
        payload = try container.decode(String.self, forKey: .payload)
        
        // Try to decode timestamp as ISO string first, fallback to Double
        if let timestampString = try? container.decode(String.self, forKey: .timestamp) {
            let formatter = ISO8601DateFormatter()
            timestamp = formatter.date(from: timestampString) ?? Date()
        } else if let timestampDouble = try? container.decode(Double.self, forKey: .timestamp) {
            timestamp = Date(timeIntervalSince1970: timestampDouble)
        } else {
            timestamp = Date()
        }
    }
} 