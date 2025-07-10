import Foundation
import AVFoundation
import OpenAIKit

public class SpeechToTextEngine {
    private let apiKey: String
    private var webSocketTask: URLSessionWebSocketTask?
    private var audioEngine: AVAudioEngine?
    private var inputNode: AVAudioInputNode?
    private var isRecording = false
    private let sampleRate: Double = 24000
    private let chunkDuration: Double = 0.1 // 100ms chunks
    
    public enum EngineError: Error {
        case transcriptionFailed
        case webSocketError(Error)
        case audioEngineError(Error)
        case invalidAPIKey
    }
    
    public init(apiKey: String) {
        self.apiKey = apiKey
    }
    
    public func start() -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    try await self.startRealtimeSession(continuation: continuation)
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }
    
    private func startRealtimeSession(continuation: AsyncThrowingStream<String, Error>.Continuation) async throws {
        // Create WebSocket connection to OpenAI Realtime API
        let model = "gpt-4o-mini-realtime-preview-2024-12-17"
        let wsURL = URL(string: "wss://api.openai.com/v1/realtime?model=\(model)")!
        
        var request = URLRequest(url: wsURL)
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("realtime=v1", forHTTPHeaderField: "OpenAI-Beta")
        
        let webSocketTask = URLSession.shared.webSocketTask(with: request)
        self.webSocketTask = webSocketTask
        
        webSocketTask.resume()
        
        print("SpeechToTextEngine: Connecting to OpenAI Realtime API...")
        
        // Start receiving messages
        await receiveMessages(continuation: continuation)
    }
    
    private func receiveMessages(continuation: AsyncThrowingStream<String, Error>.Continuation) async {
        guard let webSocketTask = webSocketTask else { return }
        
        Task {
            do {
                while true {
                    let message = try await webSocketTask.receive()
                    
                    switch message {
                    case .string(let text):
                        await handleWebSocketMessage(text, continuation: continuation)
                    case .data(let data):
                        if let text = String(data: data, encoding: .utf8) {
                            await handleWebSocketMessage(text, continuation: continuation)
                        }
                    @unknown default:
                        break
                    }
                }
            } catch {
                continuation.finish(throwing: EngineError.webSocketError(error))
            }
        }
    }
    
    private func handleWebSocketMessage(_ text: String, continuation: AsyncThrowingStream<String, Error>.Continuation) async {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let eventType = json["type"] as? String else {
            return
        }

        switch eventType {
        case "session.created":
            print("SpeechToTextEngine: Session created, sending configuration...")
            
            // Send session configuration
            let sessionConfig: [String: Any] = [
                "type": "session.update",
                "session": [
                    "input_audio_format": "pcm16",
                    "input_audio_transcription": ["model": "whisper-1"],
                    "turn_detection": [
                        "type": "server_vad",
                        "silence_duration_ms": 800
                    ],
                    "instructions": "You are a speech-to-text service. Only transcribe speech, do not respond or generate audio.",
                    "modalities": ["text"]
                ]
            ]
            
            do {
                try await sendMessage(sessionConfig)
            } catch {
                continuation.finish(throwing: EngineError.webSocketError(error))
            }
            
        case "session.updated":
            print("SpeechToTextEngine: Session configured, starting audio streaming...")
            
            // Start audio streaming
            do {
                try await startAudioStreaming()
            } catch {
                continuation.finish(throwing: error)
            }
            
        case "conversation.item.input_audio_transcription.completed":
            if let transcript = json["transcript"] as? String {
                print("SpeechToTextEngine: Transcript: \(transcript)")
                continuation.yield(transcript)
            }
            
        case "input_audio_buffer.speech_started":
            print("SpeechToTextEngine: Speech started")
            
        case "input_audio_buffer.speech_stopped":
            print("SpeechToTextEngine: Speech stopped")
            
        case "error":
            print("SpeechToTextEngine: OpenAI API error: \(json)")
            continuation.finish(throwing: EngineError.transcriptionFailed)
            
        default:
            // Ignore other event types (like response generation events)
            break
        }
    }
    
    private func sendMessage(_ message: [String: Any]) async throws {
        guard let webSocketTask = webSocketTask else { return }
        
        let jsonData = try JSONSerialization.data(withJSONObject: message)
        let jsonString = String(data: jsonData, encoding: .utf8)!
        
        try await webSocketTask.send(.string(jsonString))
    }
    
    private func startAudioStreaming() async throws {
        audioEngine = AVAudioEngine()
        
        guard let audioEngine = audioEngine else {
            throw EngineError.audioEngineError(NSError(domain: "AudioEngine", code: 1, userInfo: [NSLocalizedDescriptionKey: "Failed to create audio engine"]))
        }
        
        inputNode = audioEngine.inputNode
        
        guard let inputNode = inputNode else {
            throw EngineError.audioEngineError(NSError(domain: "AudioEngine", code: 2, userInfo: [NSLocalizedDescriptionKey: "Failed to get input node"]))
        }
        
        // Use the input node's hardware format for the tap
        let inputFormat = inputNode.inputFormat(forBus: 0)
        
        // Calculate buffer size based on the input format's sample rate
        let bufferSize = UInt32(inputFormat.sampleRate * chunkDuration) // 100ms chunks
        
        inputNode.installTap(onBus: 0, bufferSize: bufferSize, format: inputFormat) { [weak self] (buffer, time) in
            Task {
                await self?.sendAudioChunk(buffer: buffer)
            }
        }
        
        do {
            try audioEngine.start()
            isRecording = true
            print("SpeechToTextEngine: Audio streaming started")
        } catch {
            throw EngineError.audioEngineError(error)
        }
    }
    
    private func sendAudioChunk(buffer: AVAudioPCMBuffer) async {
        guard webSocketTask != nil else { return }
        
        // Convert the buffer to PCM16 format at 24kHz if needed
        guard let convertedBuffer = convertToRequiredFormat(buffer: buffer) else {
            print("SpeechToTextEngine: Failed to convert audio buffer")
            return
        }
        
        guard let channelData = convertedBuffer.int16ChannelData else {
            print("SpeechToTextEngine: No channel data available")
            return
        }
        
        let frameLength = Int(convertedBuffer.frameLength)
        let data = Data(bytes: channelData[0], count: frameLength * 2) // 2 bytes per sample for int16
        
        let base64Audio = data.base64EncodedString()
        
        let audioMessage: [String: Any] = [
            "type": "input_audio_buffer.append",
            "audio": base64Audio
        ]
        
        do {
            try await sendMessage(audioMessage)
        } catch {
            print("SpeechToTextEngine: Error sending audio chunk: \(error)")
        }
    }
    
    private func convertToRequiredFormat(buffer: AVAudioPCMBuffer) -> AVAudioPCMBuffer? {
        // Target format: PCM16, 24kHz, mono
        guard let targetFormat = AVAudioFormat(
            commonFormat: .pcmFormatInt16,
            sampleRate: sampleRate,
            channels: 1,
            interleaved: false
        ) else {
            return nil
        }
        
        // If the buffer is already in the correct format, return it
        if buffer.format.isEqual(targetFormat) {
            return buffer
        }
        
        // Create converter
        guard let converter = AVAudioConverter(from: buffer.format, to: targetFormat) else {
            return nil
        }
        
        // Calculate the capacity needed for the converted buffer
        let capacity = UInt32(Double(buffer.frameLength) * targetFormat.sampleRate / buffer.format.sampleRate)
        
        guard let convertedBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: capacity) else {
            return nil
        }
        
        var error: NSError?
        converter.convert(to: convertedBuffer, error: &error) { inNumPackets, outStatus in
            outStatus.pointee = .haveData
            return buffer
        }
        
        if let error = error {
            print("SpeechToTextEngine: Audio conversion error: \(error)")
            return nil
        }
        
        return convertedBuffer
    }
    
    public func stop() {
        isRecording = false
        
        if let inputNode = inputNode {
            inputNode.removeTap(onBus: 0)
        }
        
        audioEngine?.stop()
        
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        
        print("SpeechToTextEngine: Stopped")
    }
} 