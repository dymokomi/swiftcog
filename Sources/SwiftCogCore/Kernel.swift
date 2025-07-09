import Foundation

public protocol Kernel: AnyObject {
    func getKernelId() -> KernelID
    func receive(message: KernelMessage) async throws
} 