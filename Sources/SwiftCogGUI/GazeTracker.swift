import Foundation
import AVFoundation
import Vision

public class GazeTracker: NSObject, ObservableObject {
    // Published state drives UI and VAD blocking
    @Published public var lookingAtScreen: Bool = false
    
    private let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "gaze.tracker.queue")
    private lazy var request: VNDetectFaceLandmarksRequest = {
        VNDetectFaceLandmarksRequest(completionHandler: handleFaces)
    }()
    
    private var isStarted = false
    
    public override init() {
        super.init()
        requestCameraPermission()
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
        print("GazeTracker: Started gaze tracking")
    }
    
    public func stop() {
        guard isStarted else { return }
        
        session.stopRunning()
        session.inputs.forEach { session.removeInput($0) }
        session.outputs.forEach { session.removeOutput($0) }
        
        isStarted = false
        print("GazeTracker: Stopped gaze tracking")
    }
    
    // MARK: Vision callback
    private func handleFaces(request: VNRequest, error: Error?) {
        guard error == nil else {
            print("GazeTracker: Vision error: \(error!)")
            updateLookingState(false)
            return
        }
        
        guard
            let face = (request.results as? [VNFaceObservation])?.first,
            let yaw = face.yaw?.doubleValue
        else {
            updateLookingState(false) // No face => not looking
            return
        }
        
        // Heuristic: ±14° = 0.25 rad (same as example)
        let isLooking = abs(yaw) < 0.25
        updateLookingState(isLooking)
    }
    
    private func updateLookingState(_ newValue: Bool) {
        DispatchQueue.main.async {
            let previousValue = self.lookingAtScreen
            self.lookingAtScreen = newValue
            
            // Only log state changes
            if previousValue != newValue {
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss.SSS"
                let timestamp = formatter.string(from: Date())
                print("[\(timestamp)] GazeTracker: Looking at screen changed: \(previousValue) -> \(newValue)")
            }
        }
    }
}

// MARK: - AVCapture delegate
extension GazeTracker: AVCaptureVideoDataOutputSampleBufferDelegate {
    public func captureOutput(_ output: AVCaptureOutput,
                             didOutput sampleBuffer: CMSampleBuffer,
                             from connection: AVCaptureConnection) {
        
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .up)
        try? handler.perform([request])
    }
} 