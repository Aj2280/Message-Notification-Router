import Foundation
import Speech
import AVFoundation

let args = CommandLine.arguments
guard args.count > 1 else {
    print("Usage: asr <audio_path>")
    exit(1)
}

let audioPath = args[1]
let url = URL(fileURLWithPath: audioPath)

guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")), recognizer.isAvailable else {
    print("")
    exit(0)
}

let request = SFSpeechURLRecognitionRequest(url: url)
request.shouldReportPartialResults = false
if #available(macOS 10.15, *) {
    request.requiresOnDeviceRecognition = true
}

let semaphore = DispatchSemaphore(value: 0)
var resultText = ""

recognizer.recognitionTask(with: request) { result, error in
    if let result = result {
        if result.isFinal {
            resultText = result.bestTranscription.formattedString
            semaphore.signal()
        }
    } else if error != nil {
        semaphore.signal()
    }
}

let _ = semaphore.wait(timeout: .now() + 10.0)
print(resultText)
