import Foundation

public struct KernelMessage: Codable, Sendable {
    public let id: UUID
    public let source: KernelID?
    public let destination: KernelID?
    public let payload: String // For now, a simple string payload

    public init(source: KernelID?, destination: KernelID?, payload: String) {
        self.id = UUID()
        self.source = source
        self.destination = destination
        self.payload = payload
    }
} 