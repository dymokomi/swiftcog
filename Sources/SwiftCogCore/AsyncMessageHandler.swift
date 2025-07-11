import Foundation

// MARK: - Message Handler Protocol

public protocol AsyncMessageHandler: AnyObject {
    func handleMessage(_ message: KernelMessage) async throws
} 