import Foundation
import AVFoundation
import Speech

public class SpeechToTextEngine: NSObject, ObservableObject {
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()
    
    // Real-time transcription state
    @Published public var currentTranscription = ""
    @Published public var isListening = false
    @Published public var isSpeechDetected = false // VAD state for UI
    
    // Native VAD-based silence detection
    private var silenceTimer: Timer?
    private let silenceThreshold: TimeInterval = 1.2 // 1200ms as requested
    private var lastSpeechStoppedTime: Date?
    private var hasSpeechBeenDetected = false
    
    // Completion handlers
    private var onFinalTranscription: ((String) -> Void)?
    private var onTranscriptionUpdate: ((String) -> Void)?
    
    public enum EngineError: Error {
        case speechRecognitionNotAvailable
        case audioEngineError(Error)
        case speechRecognitionError(Error)
        case permissionDenied
    }
    
    public override init() {
        super.init()
        setupSpeechRecognizer()
    }
    
    private func setupSpeechRecognizer() {
        speechRecognizer?.delegate = self
        
        // Request speech recognition authorization
        SFSpeechRecognizer.requestAuthorization { authStatus in
            DispatchQueue.main.async {
                switch authStatus {
                case .authorized:
                    print("SpeechToTextEngine: Speech recognition authorized")
                case .denied:
                    print("SpeechToTextEngine: Speech recognition access denied")
                case .restricted:
                    print("SpeechToTextEngine: Speech recognition restricted")
                case .notDetermined:
                    print("SpeechToTextEngine: Speech recognition not determined")
                @unknown default:
                    print("SpeechToTextEngine: Unknown authorization status")
                }
            }
        }
        
        // On macOS, microphone permission is handled automatically by the system
    }
    
    public func startListening(
        onTranscriptionUpdate: @escaping (String) -> Void,
        onFinalTranscription: @escaping (String) -> Void
    ) throws {
        // Check permissions
        guard SFSpeechRecognizer.authorizationStatus() == .authorized else {
            throw EngineError.permissionDenied
        }
        
        guard let speechRecognizer = speechRecognizer, speechRecognizer.isAvailable else {
            throw EngineError.speechRecognitionNotAvailable
        }
        
        // Store completion handlers
        self.onTranscriptionUpdate = onTranscriptionUpdate
        self.onFinalTranscription = onFinalTranscription
        
        // Cancel any previous recognition task
        stopListening()
        
        // On macOS, audio configuration is handled automatically
        
        // Create recognition request with live transcription
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else {
            throw EngineError.speechRecognitionError(NSError(domain: "SpeechEngine", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unable to create recognition request"]))
        }
        
        // Enable live transcription and context-aware recognition
        recognitionRequest.shouldReportPartialResults = true
        if #available(macOS 13.0, *) {
            recognitionRequest.addsPunctuation = true
            recognitionRequest.requiresOnDeviceRecognition = false // Use cloud for better accuracy
        }
        
        // Set up audio engine
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            recognitionRequest.append(buffer)
        }
        
        // Start audio engine
        audioEngine.prepare()
        try audioEngine.start()
        
        // Start recognition task with delegate for VAD
        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest, delegate: self)
        
        isListening = true
        currentTranscription = ""
        isSpeechDetected = false
        lastSpeechStoppedTime = nil
        hasSpeechBeenDetected = false
        startSilenceTimer()
        
        print("SpeechToTextEngine: Started listening with native VAD")
    }
    
    public func stopListening() {
        // Stop audio engine
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        
        // Cancel recognition
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        
        recognitionRequest = nil
        recognitionTask = nil
        
        // Stop silence timer
        silenceTimer?.invalidate()
        silenceTimer = nil
        
        isListening = false
        
        print("SpeechToTextEngine: Stopped listening")
    }
    
    private func startSilenceTimer() {
        silenceTimer?.invalidate()
        silenceTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            
            // Only check for silence if speech was detected and then stopped
            guard let speechStoppedTime = self.lastSpeechStoppedTime,
                  self.hasSpeechBeenDetected,
                  !self.currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  self.isListening else { return }
            
            let timeSinceSpeechStopped = Date().timeIntervalSince(speechStoppedTime)
            
            if timeSinceSpeechStopped >= self.silenceThreshold {
                print("SpeechToTextEngine: VAD silence timeout (\(String(format: "%.1f", timeSinceSpeechStopped))s), finalizing: '\(self.currentTranscription)'")
                self.handleSilenceDetected()
            }
        }
    }
    
    private func updateTranscription(_ text: String) {
        currentTranscription = text
        onTranscriptionUpdate?(text)
        
        let trimmedText = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedText.isEmpty {
            print("SpeechToTextEngine: Transcription updated: '\(trimmedText)'")
        }
    }
    
    private func handleSilenceDetected() {
        let finalText = currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !finalText.isEmpty else { return }
        
        // Stop listening and timer
        silenceTimer?.invalidate()
        stopListening()
        
        // Clear current transcription and reset state
        currentTranscription = ""
        isSpeechDetected = false
        hasSpeechBeenDetected = false
        lastSpeechStoppedTime = nil
        
        // Call the completion handler
        onFinalTranscription?(finalText)
        
        // Restart listening after a brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self = self else { return }
            
            do {
                try self.startListening(
                    onTranscriptionUpdate: self.onTranscriptionUpdate ?? { _ in },
                    onFinalTranscription: self.onFinalTranscription ?? { _ in }
                )
            } catch {
                print("SpeechToTextEngine: Error restarting listening: \(error)")
            }
        }
    }
}

// MARK: - SFSpeechRecognizerDelegate
extension SpeechToTextEngine: SFSpeechRecognizerDelegate {
    public func speechRecognizer(_ speechRecognizer: SFSpeechRecognizer, availabilityDidChange available: Bool) {
        DispatchQueue.main.async {
            if available {
                print("SpeechToTextEngine: Speech recognizer became available")
            } else {
                print("SpeechToTextEngine: Speech recognizer became unavailable")
                self.stopListening()
            }
        }
    }
}

// MARK: - SFSpeechRecognitionTaskDelegate (Native VAD)
extension SpeechToTextEngine: SFSpeechRecognitionTaskDelegate {
    public func speechRecognitionTask(_ task: SFSpeechRecognitionTask, didHypothesizeTranscription transcription: SFTranscription) {
        DispatchQueue.main.async {
            let text = transcription.formattedString
            
            // Mark speech as detected when we get first transcription
            if !self.isSpeechDetected && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                print("SpeechToTextEngine: VAD - Speech started")
                self.isSpeechDetected = true
                self.lastSpeechStoppedTime = nil // Clear any previous stop time
            }
            
            self.updateTranscription(text)
        }
    }
    
    public func speechRecognitionTaskFinishedReadingAudio(_ task: SFSpeechRecognitionTask) {
        DispatchQueue.main.async {
            print("SpeechToTextEngine: VAD - Speech stopped")
            self.isSpeechDetected = false
            self.lastSpeechStoppedTime = Date()
            
            // Mark that we detected speech during this session
            if !self.currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                self.hasSpeechBeenDetected = true
            }
        }
    }
    
    public func speechRecognitionTask(_ task: SFSpeechRecognitionTask, didFinishRecognition recognitionResult: SFSpeechRecognitionResult) {
        DispatchQueue.main.async {
            let text = recognitionResult.bestTranscription.formattedString
            print("SpeechToTextEngine: Final recognition result: '\(text)'")
            self.updateTranscription(text)
            
            if recognitionResult.isFinal {
                // Don't auto-finalize here - let our silence timer handle it
                // This prevents premature finalization during natural speech pauses
            }
        }
    }
    
    public func speechRecognitionTask(_ task: SFSpeechRecognitionTask, didFinishSuccessfully successfully: Bool) {
        DispatchQueue.main.async {
            if successfully {
                print("SpeechToTextEngine: Recognition finished successfully")
            } else {
                print("SpeechToTextEngine: Recognition finished with issues")
            }
        }
    }
    
    public func speechRecognitionTaskWasCancelled(_ task: SFSpeechRecognitionTask) {
        DispatchQueue.main.async {
            print("SpeechToTextEngine: Recognition task was cancelled")
        }
    }
} 