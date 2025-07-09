import Foundation

public enum KernelID: String, CaseIterable, Codable, Sendable {
    case sensing = "sensing"
    case executive = "executive"
    case memory = "memory"
    case learning = "learning"
    case motor = "motor"
    case expression = "expression"
    
    // Frontend interface kernels
    case sensingInterface = "sensing-interface"
    case expressionInterface = "expression-interface"
} 