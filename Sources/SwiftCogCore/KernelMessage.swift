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
} 