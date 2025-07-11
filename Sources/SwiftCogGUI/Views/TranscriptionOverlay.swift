import SwiftUI

struct TranscriptionOverlay: View {
    let transcription: String
    let isListening: Bool
    
    var body: some View {
        VStack {
            Spacer()
            
            if isListening && !transcription.isEmpty {
                VStack(spacing: 16) {
                    // Microphone icon with pulse animation
                    Image(systemName: "mic.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.blue)
                        .scaleEffect(isListening ? 1.2 : 1.0)
                        .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: isListening)
                    
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
            } else if isListening {
                // Listening indicator when no speech detected
                VStack(spacing: 12) {
                    Image(systemName: "mic.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.blue)
                        .scaleEffect(isListening ? 1.2 : 1.0)
                        .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: isListening)
                    
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
                .animation(.spring(response: 0.6, dampingFraction: 0.8), value: isListening)
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
                isListening: true
            )
        }
    }
} 