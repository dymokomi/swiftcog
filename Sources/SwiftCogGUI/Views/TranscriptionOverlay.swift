import SwiftUI

struct TranscriptionOverlay: View {
    let transcription: String
    let isListening: Bool
    let isSpeechDetected: Bool
    
    var body: some View {
        VStack {
            Spacer()
            
            if isListening && !transcription.isEmpty {
                VStack(spacing: 16) {
                    // Microphone icon with pulse animation - only show when VAD detects speech
                    if isSpeechDetected {
                        Image(systemName: "mic.fill")
                            .font(.system(size: 24))
                            .foregroundColor(.blue)
                            .scaleEffect(1.2)
                            .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: isSpeechDetected)
                    }
                    
                    // Transcription text
                    Text(transcription)
                        .font(.system(size: 18, weight: .medium))
                        .multilineTextAlignment(.center)
                        .foregroundColor(.primary)
                        .padding(.horizontal, 24)
                        .padding(.vertical, 16)
                        .background(
                            RoundedRectangle(cornerRadius: 16)
                                .fill(.regularMaterial)
                                .shadow(color: .black.opacity(0.1), radius: 10, x: 0, y: 4)
                        )
                        .transition(.scale.combined(with: .opacity))
                }
                .padding(.horizontal, 40)
                .animation(.spring(response: 0.6, dampingFraction: 0.8), value: transcription)
            } else if isListening && isSpeechDetected {
                // Active listening indicator when VAD detects speech but no transcription yet
                VStack(spacing: 12) {
                    Image(systemName: "mic.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.blue)
                        .scaleEffect(1.2)
                        .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: isSpeechDetected)
                    
                    Text("Listening...")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 16)
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(.regularMaterial)
                        .shadow(color: .black.opacity(0.1), radius: 10, x: 0, y: 4)
                )
                .transition(.scale.combined(with: .opacity))
                .animation(.spring(response: 0.6, dampingFraction: 0.8), value: isSpeechDetected)
            }
            
            Spacer()
        }
        .allowsHitTesting(false) // Allow touches to pass through
    }
}

struct TranscriptionOverlay_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.opacity(0.1)
                .ignoresSafeArea()
            
            TranscriptionOverlay(
                transcription: "This is a sample transcription that shows how the speech-to-text appears in real time.",
                isListening: true,
                isSpeechDetected: true
            )
        }
    }
} 