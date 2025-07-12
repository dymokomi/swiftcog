import Foundation
import AVFoundation
import Speech
import Combine

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
    private let silenceThreshold: TimeInterval = 2.5 // Allow longer pauses during natural speech
    private var lastTranscriptionUpdateTime = Date()
    private var lastTranscriptionContent = ""
    private var hasSpeechBeenDetected = false
    
    // Gaze tracking integration
    private weak var gazeTracker: GazeTracker?
    private var gazeCancellable: AnyCancellable?
    private var shouldListenWhenGazeReturns = false
    private var wasListeningBeforeGazeLoss = false
    
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
    
    deinit {
        gazeCancellable?.cancel()
        stopListening()
    }
    
    public func setGazeTracker(_ gazeTracker: GazeTracker) {
        self.gazeTracker = gazeTracker
        
        // Use Combine to observe the published property
        gazeCancellable = gazeTracker.$lookingAtScreen
            .removeDuplicates()
            .sink { [weak self] isLooking in
                self?.handleGazeStateChange(isLooking: isLooking)
            }
        
        print("SpeechToTextEngine: Gaze tracker configured")
    }
    
    private func handleGazeStateChange(isLooking: Bool) {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss.SSS"
        let timestamp = formatter.string(from: Date())
        
        // Removed verbose logging - only log important state changes below
        
        if isLooking {
            print("[\(timestamp)] SpeechToTextEngine: User looking at screen")
            
            // If we should start listening when gaze returns and we're not currently listening
            if shouldListenWhenGazeReturns && !isListening {
                shouldListenWhenGazeReturns = false
                print("[\(timestamp)] SpeechToTextEngine: Restarting listening due to gaze return")
                
                do {
                    try startListeningWithGazeOverride(
                        onTranscriptionUpdate: onTranscriptionUpdate ?? { _ in },
                        onFinalTranscription: onFinalTranscription ?? { _ in },
                        forceStart: true // Override gaze check since we know user is looking
                    )
                } catch {
                    print("[\(timestamp)] SpeechToTextEngine: Error restarting listening: \(error)")
                }
            } else if shouldListenWhenGazeReturns && isListening {
                shouldListenWhenGazeReturns = false // Reset flag
            } else if !shouldListenWhenGazeReturns && !isListening && onFinalTranscription != nil {
                // Initial gaze detection - try to start listening
                print("[\(timestamp)] SpeechToTextEngine: Initial gaze detection - starting listening")
                do {
                    try startListeningWithGazeOverride(
                        onTranscriptionUpdate: onTranscriptionUpdate ?? { _ in },
                        onFinalTranscription: onFinalTranscription ?? { _ in },
                        forceStart: true // Override gaze check since we know user is looking
                    )
                } catch {
                    print("[\(timestamp)] SpeechToTextEngine: Error starting listening on initial gaze: \(error)")
                }
            }
        } else {
            print("[\(timestamp)] SpeechToTextEngine: User not looking at screen")
            
            // If we're currently listening but user looked away
            if isListening {
                wasListeningBeforeGazeLoss = true
                
                // If user is currently speaking, don't interrupt - let the silence timer handle it
                if hasSpeechBeenDetected && !currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    print("[\(timestamp)] SpeechToTextEngine: User speaking while looking away - will stop after silence")
                    shouldListenWhenGazeReturns = true
                } else {
                    // No active speech, stop listening immediately
                    print("[\(timestamp)] SpeechToTextEngine: No active speech - stopping listening immediately")
                    stopListening()
                    shouldListenWhenGazeReturns = true
                }
            }
        }
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
        try startListeningWithGazeOverride(
            onTranscriptionUpdate: onTranscriptionUpdate,
            onFinalTranscription: onFinalTranscription,
            forceStart: false
        )
    }
    
    private func startListeningWithGazeOverride(
        onTranscriptionUpdate: @escaping (String) -> Void,
        onFinalTranscription: @escaping (String) -> Void,
        forceStart: Bool
    ) throws {
        // Store completion handlers first
        self.onTranscriptionUpdate = onTranscriptionUpdate
        self.onFinalTranscription = onFinalTranscription
        
        // Check if user is looking at screen first (unless forced)
        let isLookingAtScreen = gazeTracker?.lookingAtScreen ?? true
        let hasGazeTracker = gazeTracker != nil
        
        if !forceStart && !isLookingAtScreen && hasGazeTracker {
            print("SpeechToTextEngine: User not looking at screen - deferring listening")
            shouldListenWhenGazeReturns = true
            return
        } else if forceStart {
            print("SpeechToTextEngine: Starting listening (gaze override)")
        }
        
        // Check permissions
        guard SFSpeechRecognizer.authorizationStatus() == .authorized else {
            throw EngineError.permissionDenied
        }
        
        guard let speechRecognizer = speechRecognizer, speechRecognizer.isAvailable else {
            throw EngineError.speechRecognitionNotAvailable
        }
        
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
        
        inputNode.installTap(onBus: 0, bufferSize: 512, format: recordingFormat) { buffer, _ in
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
            self.silenceTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
                guard let self = self else { return }
                
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss.SSS"
                let timestamp = formatter.string(from: Date())
                
                // Check if transcription has stopped updating for the threshold period
                let timeSinceLastUpdate = Date().timeIntervalSince(self.lastTranscriptionUpdateTime)

                // Check if we have speech content and haven't had updates recently
                if self.hasSpeechBeenDetected && 
                   !self.currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
                   timeSinceLastUpdate >= self.silenceThreshold &&
                   self.isListening {
                    
                    let isLookingAtScreen = self.gazeTracker?.lookingAtScreen ?? true
                    
                    if isLookingAtScreen {
                        // User is looking - finalize normally
                        print("[\(timestamp)] SpeechToTextEngine: Transcription silence timeout (\(String(format: "%.1f", timeSinceLastUpdate))s), finalizing: '\(self.currentTranscription)'")
                        self.handleSilenceDetected()
                    } else {
                        // User finished speaking but not looking - stop listening and wait for gaze return
                        print("[\(timestamp)] SpeechToTextEngine: Speech finished but user not looking - stopping until gaze returns")
                        self.handleSilenceDetectedWithoutGaze()
                    }
                }
            }
        }
    }
    
    private func updateTranscription(_ text: String) {
        let trimmedText = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss.SSS"
        // Only update timer if transcription content actually changed
        if trimmedText != lastTranscriptionContent && !trimmedText.isEmpty {
            lastTranscriptionUpdateTime = Date()
            lastTranscriptionContent = trimmedText
            //print("[\(timestamp)] SpeechToTextEngine: Transcription updated: '\(trimmedText)'")
        } else if !trimmedText.isEmpty {
            //print("[\(timestamp)] SpeechToTextEngine: Transcription refinement (no content change): '\(trimmedText)'")
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
        
        // Only restart if user is looking at screen
        if gazeTracker?.lookingAtScreen ?? true {
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
        } else {
            // User not looking - wait for gaze return
            shouldListenWhenGazeReturns = true
        }
    }
    
    private func handleSilenceDetectedWithoutGaze() {
        let finalText = currentTranscription.trimmingCharacters(in: .whitespacesAndNewlines)
        
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
        
        // Don't send to server - user not looking
        print("SpeechToTextEngine: Discarding transcription due to lack of attention: '\(finalText)'")
        
        // Wait for gaze to return before listening again
        shouldListenWhenGazeReturns = true
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