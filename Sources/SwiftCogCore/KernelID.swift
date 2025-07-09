import Foundation

public struct KernelID: Hashable, Codable, Sendable {
    public let rawValue: UUID

    public init() {
        self.rawValue = UUID()
    }
} 