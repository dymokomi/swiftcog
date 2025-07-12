import Foundation
import AVFoundation
import Vision
import CoreImage
import AppKit

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
    private var currentPixelBuffer: CVPixelBuffer?
    private var snapshotCounter = 0
    
    // Camera warmup properties
    private var isWarmingUp = true
    private var validFrameCount = 0
    private var validFaceDetectionCount = 0
    private let requiredWarmupFrames = 30  // Skip first 30 frames (~1 second at 30fps)
    private let requiredFaceDetections = 3  // Need 3 stable face detections before sending
    
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
                updateLookingState(false)
            }
            return
        }
        
        guard
            let face = (request.results as? [VNFaceObservation])?.first,
            let yaw = face.yaw?.doubleValue
        else {
            if !isWarmingUp {
                updateLookingState(false) // No face => not looking
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
        
        // Normal operation - send gaze messages
        updateLookingState(isLooking)
    }
    
    private func handleFeaturePrint(request: VNRequest, error: Error?) {
        guard error == nil else {
            print("GazeTracker: Feature print error: \(error!)")
            currentFeatureVector = nil
            return
        }
        
        guard let observation = request.results?.first as? VNFeaturePrintObservation else {
            currentFeatureVector = nil
            return
        }
        
        // Extract the feature vector data
        let featureData = observation.data
        let featureVector = featureData.withUnsafeBytes { buffer in
            return Array(buffer.bindMemory(to: Float.self))
        }
        
        currentFeatureVector = featureVector
    }
    
    private func updateLookingState(_ newValue: Bool) {
        DispatchQueue.main.async {
            let previousValue = self.lookingAtScreen
            self.lookingAtScreen = newValue
            
            // Only log and send messages on state changes
            if previousValue != newValue {
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss.SSS"
                let timestamp = formatter.string(from: Date())
                print("[\(timestamp)] GazeTracker: Looking at screen changed: \(previousValue) -> \(newValue)")
                
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
        
        // Add feature vector if available
        let hasFeatureVector = currentFeatureVector != nil
        if let featureVector = currentFeatureVector {
            gazeData["featureVector"] = featureVector
            gazeData["featureVectorDimensions"] = featureVector.count
        }
        
        // Save snapshot whenever we're sending gaze data with feature vectors
        // This helps diagnose the double vector issue
        if hasFeatureVector {
            print("[\(timestamp)] GazeTracker: Saving snapshot for face vector analysis")
            saveSnapshot(timestamp: timestamp, hasFeatureVector: hasFeatureVector)
        }
        
        // Convert to JSON string
        do {
            let jsonData = try JSONSerialization.data(withJSONObject: gazeData, options: [])
            let jsonString = String(data: jsonData, encoding: .utf8) ?? "{}"
            
            // Send asynchronously to avoid blocking the gaze tracking thread
            Task {
                do {
                    try await kernelSystem.sendToBackend(jsonString)
                    let featureInfo = currentFeatureVector != nil ? " with \(currentFeatureVector!.count)D feature vector" : ""
                    print("[\(timestamp)] GazeTracker: Sent gaze data - looking: \(lookingAtScreen)\(featureInfo)")
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
        
        // Store current pixel buffer for potential snapshot
        currentPixelBuffer = pixelBuffer
        
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
        
        // Debug: Log pixel format info only once during warmup
        if isWarmingUp && validFrameCount == 0 {
            print("GazeTracker: Frame info - Format: \(pixelFormat), Size: \(width)x\(height), BytesPerRow: \(bytesPerRow)")
        }
        
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
            if !isWarmingUp {
                print("GazeTracker: BGRA pixel at center - R:\(red) G:\(green) B:\(blue) Brightness:\(brightness)")
            }
        } else if pixelFormat == kCVPixelFormatType_420YpCbCr8BiPlanarFullRange || pixelFormat == kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange {
            // YUV format - just use the Y (luminance) component
            let pixelOffset = centerY * bytesPerRow + centerX
            let pixel = baseAddress.advanced(by: pixelOffset).assumingMemoryBound(to: UInt8.self)
            brightness = Int(pixel[0])
            if !isWarmingUp {
                print("GazeTracker: YUV pixel at center - Y:\(brightness)")
            }
        } else {
            if isWarmingUp && validFrameCount == 0 {
                print("GazeTracker: Unsupported pixel format: \(pixelFormat)")
            }
            // For unknown formats, let's be conservative and allow processing
            return true
        }
        
        // Use a lower threshold since we're only checking one pixel
        let isValid = brightness > 5
        
        if !isValid && !isWarmingUp {
            print("GazeTracker: Skipping black/empty frame (brightness: \(brightness))")
        } else if isValid && !isWarmingUp {
            print("GazeTracker: Valid frame (brightness: \(brightness))")
        }
        
        return isValid
    }
}

// MARK: - Snapshot functionality
extension GazeTracker {
    private func saveSnapshot(timestamp: String, hasFeatureVector: Bool) {
        guard let pixelBuffer = currentPixelBuffer else {
            print("GazeTracker: No pixel buffer available for snapshot")
            return
        }
        
        // Create filename with timestamp and vector info
        let vectorInfo = hasFeatureVector ? "with_vector" : "no_vector"
        snapshotCounter += 1
        let filename = "gaze_snapshot_\(timestamp.replacingOccurrences(of: ":", with: "-").replacingOccurrences(of: ".", with: "_"))_\(vectorInfo)_\(snapshotCounter).jpg"
        
        // Get desktop directory for saving
        let desktopURL = FileManager.default.urls(for: .desktopDirectory, in: .userDomainMask).first!
        let snapshotURL = desktopURL.appendingPathComponent(filename)
        
        // Convert pixel buffer to CGImage
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let context = CIContext()
        
        guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else {
            print("GazeTracker: Failed to create CGImage from pixel buffer")
            return
        }
        
        // Create NSBitmapImageRep and save as JPEG
        let bitmapRep = NSBitmapImageRep(cgImage: cgImage)
        guard let jpegData = bitmapRep.representation(using: .jpeg, properties: [.compressionFactor: 0.8]) else {
            print("GazeTracker: Failed to create JPEG data")
            return
        }
        
        do {
            try jpegData.write(to: snapshotURL)
            print("GazeTracker: Saved snapshot to \(snapshotURL.path)")
        } catch {
            print("GazeTracker: Failed to save snapshot: \(error)")
        }
    }
} 