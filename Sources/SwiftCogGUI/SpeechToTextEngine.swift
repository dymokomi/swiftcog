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
    
    // Hybrid VAD-based silence detection
    private var silenceTimer: Timer?
    private let silenceThreshold: TimeInterval = 1.2 // 1200ms as requested
    private var lastTranscriptionUpdateTime = Date()
    private var lastTranscriptionContent = ""
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
        lastTranscriptionUpdateTime = Date()
        lastTranscriptionContent = ""
        hasSpeechBeenDetected = false
        startSilenceTimer()
        
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss.SSS"
        let timestamp = formatter.string(from: Date())
        print("[\(timestamp)] SpeechToTextEngine: Started listening with hybrid VAD")
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
        
        // Stop silence timer (ensure on main thread)
        DispatchQueue.main.async { [weak self] in
            self?.silenceTimer?.invalidate()
            self?.silenceTimer = nil
        }
        
        isListening = false
        
        print("SpeechToTextEngine: Stopped listening")
    }
    
    private func startSilenceTimer() {
        // Ensure timer is created on main thread
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            
            self.silenceTimer?.invalidate()
            self.silenceTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
                guard let self = self else { 
                    print("Timer fired but self is nil")
                    return 
                }
                
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss.SSS"
                let timestamp = formatter.string(from: Date())
                
                // Check if transcription has stopped updating for the threshold period
                let timeSinceLastUpdate = Date().timeIntervalSince(self.lastTranscriptionUpdateTime)
                
                // Debug current state - ALWAYS show when we have any content AND every 1 second to show timer is alive
                let transcription = self.currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines)
                let shouldLog = !transcription.isEmpty || self.hasSpeechBeenDetected || Int(timeSinceLastUpdate * 5) % 5 == 0
                
                if shouldLog {
                    print("[\(timestamp)] Timer check: speechDetected=\(self.hasSpeechBeenDetected), hasContent=\(!transcription.isEmpty), timeSinceUpdate=\(String(format: "%.1f", timeSinceLastUpdate))s, threshold=\(self.silenceThreshold)s, listening=\(self.isListening)")
                }
                
                // Only proceed if we have speech detected and content and haven't had updates recently
                if self.hasSpeechBeenDetected && 
                   !self.currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
                   timeSinceLastUpdate >= self.silenceThreshold &&
                   self.isListening {
                    
                    print("[\(timestamp)] SpeechToTextEngine: Transcription silence timeout (\(String(format: "%.1f", timeSinceLastUpdate))s), finalizing: '\(self.currentTranscription)'")
                    self.handleSilenceDetected()
                }
            }
            
            print("Timer created on main thread: \(Thread.isMainThread)")
        }
    }
    
    private func updateTranscription(_ text: String) {
        let trimmedText = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss.SSS"
        let timestamp = formatter.string(from: Date())
        
        // Only update timer if transcription content actually changed
        if trimmedText != lastTranscriptionContent && !trimmedText.isEmpty {
            lastTranscriptionUpdateTime = Date()
            lastTranscriptionContent = trimmedText
            print("[\(timestamp)] SpeechToTextEngine: Transcription updated: '\(trimmedText)'")
        } else if !trimmedText.isEmpty {
            print("[\(timestamp)] SpeechToTextEngine: Transcription refinement (no content change): '\(trimmedText)'")
        }
        
        currentTranscription = text
        onTranscriptionUpdate?(text)
    }
    
    private func handleSilenceDetected() {
        let finalText = currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !finalText.isEmpty else { return }
        
        // Stop listening and timer (ensure on main thread)
        DispatchQueue.main.async { [weak self] in
            self?.silenceTimer?.invalidate()
        }
        stopListening()
        
        // Clear current transcription and reset state
        currentTranscription = ""
        isSpeechDetected = false
        hasSpeechBeenDetected = false
        lastTranscriptionContent = ""
        
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
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss.SSS"
                let timestamp = formatter.string(from: Date())
                print("[\(timestamp)] SpeechToTextEngine: VAD - Speech started")
                self.isSpeechDetected = true
                self.hasSpeechBeenDetected = true
            }
            
            self.updateTranscription(text)
        }
    }
    
    public func speechRecognitionTaskFinishedReadingAudio(_ task: SFSpeechRecognitionTask) {
        DispatchQueue.main.async {
            print("SpeechToTextEngine: VAD - Native speech stopped detected")
            self.isSpeechDetected = false
            
            // This delegate method isn't reliable on macOS, so we mainly rely on transcription timing
            // but we can use it to update UI state when available
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