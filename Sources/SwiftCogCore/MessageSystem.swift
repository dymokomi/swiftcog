import Foundation

public protocol MessageSystem {
    func emit(message: KernelMessage, from emitter: any Kernel) async throws
} 