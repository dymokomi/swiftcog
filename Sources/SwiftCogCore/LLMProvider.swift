import Foundation

// MARK: - LLM Provider Protocol

public protocol LLMProvider {
    func generateCompletion(
        systemPrompt: String,
        userMessage: String,
        temperature: Double,
        maxTokens: Int
    ) async throws -> String
}

// MARK: - LLM Message Models

public struct LLMMessage: Codable {
    let role: String
    let content: String
    
    public init(role: String, content: String) {
        self.role = role
        self.content = content
    }
}

public struct LLMRequest: Codable {
    let model: String
    let messages: [LLMMessage]
    let temperature: Double
    let max_tokens: Int
    
    public init(model: String, messages: [LLMMessage], temperature: Double, maxTokens: Int) {
        self.model = model
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = maxTokens
    }
}

public struct LLMChoice: Codable {
    let message: LLMMessage
}

public struct LLMResponse: Codable {
    let choices: [LLMChoice]
}

// MARK: - OpenAI Provider Implementation

public class OpenAIProvider: LLMProvider {
    private let apiKey: String
    private let baseURL: String
    private let session: URLSession
    
    public init(apiKey: String, baseURL: String = "https://api.openai.com/v1") {
        self.apiKey = apiKey
        self.baseURL = baseURL
        self.session = URLSession.shared
    }
    
    public func generateCompletion(
        systemPrompt: String,
        userMessage: String,
        temperature: Double = 0.7,
        maxTokens: Int = 500
    ) async throws -> String {
        
        let url = URL(string: "\(baseURL)/chat/completions")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let messages = [
            LLMMessage(role: "system", content: systemPrompt),
            LLMMessage(role: "user", content: userMessage)
        ]
        
        let llmRequest = LLMRequest(
            model: "gpt-4o-mini",
            messages: messages,
            temperature: temperature,
            maxTokens: maxTokens
        )
        
        let jsonData = try JSONEncoder().encode(llmRequest)
        request.httpBody = jsonData
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw LLMError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw LLMError.apiError(statusCode: httpResponse.statusCode, message: errorMessage)
        }
        
        let llmResponse = try JSONDecoder().decode(LLMResponse.self, from: data)
        
        guard let firstChoice = llmResponse.choices.first else {
            throw LLMError.noResponse
        }
        
        return firstChoice.message.content
    }
}

// MARK: - Local LLM Provider (Placeholder for future implementation)

public class LocalLLMProvider: LLMProvider {
    private let endpoint: String
    
    public init(endpoint: String) {
        self.endpoint = endpoint
    }
    
    public func generateCompletion(
        systemPrompt: String,
        userMessage: String,
        temperature: Double = 0.7,
        maxTokens: Int = 500
    ) async throws -> String {
        // TODO: Implement local LLM integration (e.g., Ollama, LocalAI, etc.)
        // This could follow a similar pattern to OpenAI but with different endpoints/formats
        throw LLMError.notImplemented
    }
}

// MARK: - LLM Service

public class LLMService {
    private let provider: LLMProvider
    
    public init(provider: LLMProvider) {
        self.provider = provider
    }
    
    public func processMessage(
        _ message: String,
        systemPrompt: String,
        temperature: Double = 0.7,
        maxTokens: Int = 500
    ) async throws -> String {
        return try await provider.generateCompletion(
            systemPrompt: systemPrompt,
            userMessage: message,
            temperature: temperature,
            maxTokens: maxTokens
        )
    }
}

// MARK: - Error Types

public enum LLMError: Error, LocalizedError {
    case invalidResponse
    case apiError(statusCode: Int, message: String)
    case noResponse
    case notImplemented
    
    public var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from LLM provider"
        case .apiError(let statusCode, let message):
            return "API error (\(statusCode)): \(message)"
        case .noResponse:
            return "No response from LLM provider"
        case .notImplemented:
            return "LLM provider not implemented"
        }
    }
} 