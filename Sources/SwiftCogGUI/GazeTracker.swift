import Foundation
import AVFoundation
import Vision

public class GazeTracker: NSObject, ObservableObject {
    // Published state drives UI and VAD blocking
    @Published public var lookingAtScreen: Bool = false
    
    // Reference to kernel system for sending gaze data
    private weak var kernelSystem: FrontendKernelSystem?
    
    private let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "gaze.tracker.queue")
    private lazy var faceLandmarksRequest: VNDetectFaceLandmarksRequest = {
        VNDetectFaceLandmarksRequest(completionHandler: handleFaces)
    }()
    
    private lazy var featurePrintRequest: VNGenerateImageFeaturePrintRequest = {
        VNGenerateImageFeaturePrintRequest(completionHandler: handleFeaturePrint)
    }()
    
    private var isStarted = false
    private var currentFeatureVector: [Float]?
    
    // Camera warmup properties
    private var isWarmingUp = true
    private var validFrameCount = 0
    private var validFaceDetectionCount = 0
    private let requiredWarmupFrames = 30  // Skip first 30 frames (~1 second at 30fps)
    private let requiredFaceDetections = 3  // Need 3 stable face detections before sending
    
    // Person detection stabilization properties
    private var personDetectionStable = false
    private var personDetectionStartTime: Date?
    private var stableDetectionCount = 0
    private let stabilizationDuration: TimeInterval = 2.0  // 2 seconds
    private let requiredStableDetections = 6  // Need 6 stable detections over 2 seconds
    
    // Frame processing coordination
    private var pendingGazeState: Bool?
    private var frameProcessingComplete = false
    
    public override init() {
        super.init()
        requestCameraPermission()
    }
    
    public func setKernelSystem(_ kernelSystem: FrontendKernelSystem) {
        self.kernelSystem = kernelSystem
        print("GazeTracker: Kernel system configured for gaze data transmission")
    }
    
    private func requestCameraPermission() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            print("GazeTracker: Camera access already authorized")
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                DispatchQueue.main.async {
                    if granted {
                        print("GazeTracker: Camera access granted")
                    } else {
                        print("GazeTracker: Camera access denied")
                    }
                }
            }
        case .denied, .restricted:
            print("GazeTracker: Camera access denied or restricted")
        @unknown default:
            print("GazeTracker: Unknown camera authorization status")
        }
    }
    
    public func start() {
        guard !isStarted else { 
            print("GazeTracker: Already started")
            return 
        }
        
        guard AVCaptureDevice.authorizationStatus(for: .video) == .authorized else {
            print("GazeTracker: Camera access not authorized")
            return
        }
        
        guard session.inputs.isEmpty else { 
            print("GazeTracker: Session already has inputs")
            return 
        }
        
        // Reset warmup state
        isWarmingUp = true
        validFrameCount = 0
        validFaceDetectionCount = 0
        
        session.sessionPreset = .vga640x480 // Small resolution is fine for landmarks
        
        guard
            let camera = AVCaptureDevice.default(.builtInWideAngleCamera,
                                               for: .video,
                                               position: .front),
            let input = try? AVCaptureDeviceInput(device: camera)
        else { 
            print("GazeTracker: Failed to create camera input")
            return 
        }
        
        session.addInput(input)
        
        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: queue)
        session.addOutput(output)
        
        session.startRunning()
        isStarted = true
        print("GazeTracker: Started gaze tracking - entering warmup period")
    }
    
    public func stop() {
        guard isStarted else { return }
        
        session.stopRunning()
        session.inputs.forEach { session.removeInput($0) }
        session.outputs.forEach { session.removeOutput($0) }
        
        isStarted = false
        print("GazeTracker: Stopped gaze tracking")
    }
    
    // MARK: Vision callbacks
    private func handleFaces(request: VNRequest, error: Error?) {
        guard error == nil else {
            print("GazeTracker: Vision error: \(error!)")
            if !isWarmingUp {
                pendingGazeState = false
                checkFrameProcessingComplete()
            }
            return
        }
        
        guard
            let face = (request.results as? [VNFaceObservation])?.first,
            let yaw = face.yaw?.doubleValue
        else {
            if !isWarmingUp {
                pendingGazeState = false
                checkFrameProcessingComplete()
            }
            return
        }
        
        // Heuristic: ±14° = 0.25 rad (same as example)
        let isLooking = abs(yaw) < 0.25
        
        // Handle warmup period - count valid face detections
        if isWarmingUp {
            if isLooking {
                validFaceDetectionCount += 1
                print("GazeTracker: Warmup face detection \(validFaceDetectionCount)/\(requiredFaceDetections)")
                
                if validFaceDetectionCount >= requiredFaceDetections {
                    isWarmingUp = false
                    print("GazeTracker: Camera warmup complete! Ready to send gaze messages.")
                }
            }
            return // Don't send gaze messages during warmup
        }
        
        // Normal operation - store pending gaze state
        pendingGazeState = isLooking
        checkFrameProcessingComplete()
    }
    
    private func handleFeaturePrint(request: VNRequest, error: Error?) {
        guard error == nil else {
            print("GazeTracker: Feature print error: \(error!)")
            currentFeatureVector = nil
            frameProcessingComplete = true
            checkFrameProcessingComplete()
            return
        }
        
        guard let observation = request.results?.first as? VNFeaturePrintObservation else {
            currentFeatureVector = nil
            frameProcessingComplete = true
            checkFrameProcessingComplete()
            return
        }
        
        // Extract the feature vector data
        let featureData = observation.data
        let featureVector = featureData.withUnsafeBytes { buffer in
            return Array(buffer.bindMemory(to: Float.self))
        }
        
        currentFeatureVector = featureVector
        frameProcessingComplete = true
        checkFrameProcessingComplete()
    }
    
    private func checkFrameProcessingComplete() {
        // Only process gaze state when both face detection and feature vector processing are complete
        guard let gazeState = pendingGazeState, frameProcessingComplete else {
            return
        }
        
        // Reset for next frame
        pendingGazeState = nil
        frameProcessingComplete = false
        
        // Now update the looking state with both face detection and feature vector available
        updateLookingState(gazeState)
    }
    
    private func updateLookingState(_ newValue: Bool) {
        DispatchQueue.main.async {
            let previousValue = self.lookingAtScreen
            self.lookingAtScreen = newValue
            
            var shouldSendMessage = false
            var stabilizationJustCompleted = false
            
            // Handle person detection stabilization
            if newValue && !previousValue {
                // Person just started looking at screen - start stabilization period
                self.personDetectionStartTime = Date()
                self.personDetectionStable = false
                self.stableDetectionCount = 0
                print("GazeTracker: Person detection started - beginning stabilization period")
                shouldSendMessage = true
            } else if !newValue && previousValue {
                // Person stopped looking at screen - reset stabilization
                self.personDetectionStartTime = nil
                self.personDetectionStable = false
                self.stableDetectionCount = 0
                print("GazeTracker: Person left - resetting stabilization")
                shouldSendMessage = true
            } else if newValue && previousValue {
                // Person continues looking - check if we should stabilize
                if let startTime = self.personDetectionStartTime, !self.personDetectionStable {
                    let timeElapsed = Date().timeIntervalSince(startTime)
                    self.stableDetectionCount += 1
                    
                    if timeElapsed >= self.stabilizationDuration && self.stableDetectionCount >= self.requiredStableDetections {
                        self.personDetectionStable = true
                        stabilizationJustCompleted = true
                        print("GazeTracker: Person detection stabilized after \(String(format: "%.1f", timeElapsed))s - enabling feature vector transmission")
                        shouldSendMessage = true
                    }
                }
            }
            
            // Send messages on state changes or when stabilization completes
            if shouldSendMessage {
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss.SSS"
                let timestamp = formatter.string(from: Date())
                
                if previousValue != newValue {
                    print("[\(timestamp)] GazeTracker: Looking at screen changed: \(previousValue) -> \(newValue)")
                } else if stabilizationJustCompleted {
                    print("[\(timestamp)] GazeTracker: Stabilization completed - sending gaze data with feature vector")
                }
                
                // Send gaze data to sensing kernel
                self.sendGazeDataMessage(lookingAtScreen: newValue, timestamp: timestamp)
            }
        }
    }
    
    private func sendGazeDataMessage(lookingAtScreen: Bool, timestamp: String) {
        guard let kernelSystem = kernelSystem else {
            // Silent - not all deployments need gaze data messaging
            return
        }
        
        // Create structured gaze data payload in new format
        var gazeData: [String: Any] = [
            "messageType": "gazeData",
            "lookingAtScreen": lookingAtScreen,
            "timestamp": timestamp
        ]
        
        // Add feature vector only if available AND person detection is stable
        if let featureVector = currentFeatureVector, personDetectionStable && lookingAtScreen {
            gazeData["featureVector"] = featureVector
            gazeData["featureVectorDimensions"] = featureVector.count
        }
        
        // Convert to JSON string
        do {
            let jsonData = try JSONSerialization.data(withJSONObject: gazeData, options: [])
            let jsonString = String(data: jsonData, encoding: .utf8) ?? "{}"
            
            // Send asynchronously to avoid blocking the gaze tracking thread
            Task {
                do {
                    try await kernelSystem.sendToBackend(jsonString)
                    let hasFeatureVector = currentFeatureVector != nil && personDetectionStable && lookingAtScreen
                    let featureInfo = hasFeatureVector ? " with \(currentFeatureVector!.count)D feature vector" : ""
                    let stabilizationInfo = lookingAtScreen && !personDetectionStable ? " (stabilizing - no feature vector)" : ""
                    print("[\(timestamp)] GazeTracker: Sent gaze data - looking: \(lookingAtScreen)\(featureInfo)\(stabilizationInfo)")
                } catch {
                    print("[\(timestamp)] GazeTracker: Failed to send gaze data: \(error)")
                }
            }
        } catch {
            print("[\(timestamp)] GazeTracker: Failed to serialize gaze data: \(error)")
        }
    }
}

// MARK: - AVCapture delegate
extension GazeTracker: AVCaptureVideoDataOutputSampleBufferDelegate {
    public func captureOutput(_ output: AVCaptureOutput,
                             didOutput sampleBuffer: CMSampleBuffer,
                             from connection: AVCaptureConnection) {
        
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        
        // Check if frame is valid (not black/empty) before processing
        guard isValidFrame(pixelBuffer) else {
            // Skip processing black/empty frames that occur during camera startup
            return
        }
        
        // Handle camera warmup period
        if isWarmingUp {
            validFrameCount += 1
            if validFrameCount < requiredWarmupFrames {
                print("GazeTracker: Warming up... (\(validFrameCount)/\(requiredWarmupFrames) frames)")
                return
            }
            // Continue processing during warmup to detect faces, but don't send gaze messages yet
        }
        
        // Reset frame processing state for new frame
        pendingGazeState = nil
        frameProcessingComplete = false
        
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .up)
        try? handler.perform([faceLandmarksRequest, featurePrintRequest])
    }
}

// MARK: - Frame validation
extension GazeTracker {
    private func isValidFrame(_ pixelBuffer: CVPixelBuffer) -> Bool {
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }
        
        guard let baseAddress = CVPixelBufferGetBaseAddress(pixelBuffer) else {
            print("GazeTracker: No base address for pixel buffer")
            return false
        }
        
        let width = CVPixelBufferGetWidth(pixelBuffer)
        let height = CVPixelBufferGetHeight(pixelBuffer)
        let bytesPerRow = CVPixelBufferGetBytesPerRow(pixelBuffer)
        let pixelFormat = CVPixelBufferGetPixelFormatType(pixelBuffer)
        
        // Sample just the center pixel for simplicity
        let centerX = width / 2
        let centerY = height / 2
        
        var brightness: Int = 0
        
        // Handle different pixel formats
        if pixelFormat == kCVPixelFormatType_32BGRA {
            let pixelOffset = centerY * bytesPerRow + centerX * 4
            let pixel = baseAddress.advanced(by: pixelOffset).assumingMemoryBound(to: UInt8.self)
            let blue = Int(pixel[0])
            let green = Int(pixel[1])
            let red = Int(pixel[2])
            brightness = (red * 299 + green * 587 + blue * 114) / 1000
        } else if pixelFormat == kCVPixelFormatType_420YpCbCr8BiPlanarFullRange || pixelFormat == kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange {
            // YUV format - just use the Y (luminance) component
            let pixelOffset = centerY * bytesPerRow + centerX
            let pixel = baseAddress.advanced(by: pixelOffset).assumingMemoryBound(to: UInt8.self)
            brightness = Int(pixel[0])
        } else {
            // For unknown formats, let's be conservative and allow processing
            return true
        }
        
        // Use a lower threshold since we're only checking one pixel
        let isValid = brightness > 5
        
        if !isValid {
            print("GazeTracker: Skipping black/empty frame (brightness: \(brightness))")
        }
        
        return isValid
    }
}

 