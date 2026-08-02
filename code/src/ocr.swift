import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count > 1 else {
    print("Usage: ocr <image_path>")
    exit(1)
}

let imagePath = args[1]
guard let nsImage = NSImage(contentsOfFile: imagePath),
      let cgImage = nsImage.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("")
    exit(0)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
    if let results = request.results {
        let text = results.compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
        print(text)
    }
} catch {
    print("")
}
