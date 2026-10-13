import os
import csv
import json
import subprocess
from faster_whisper import WhisperModel

def extract_all():
    os.makedirs("scratch", exist_ok=True)
    ocr_cache_path = "scratch/image_ocr_cache.json"
    asr_cache_path = "scratch/voice_transcription_cache.json"

    # 1. OCR Extraction using Apple Vision binary
    ocr_bin = "code/src/ocr_bin"
    ocr_results = {}
    if os.path.exists("dataset/images.csv"):
        print("Extracting OCR from dataset/images.csv...")
        with open("dataset/images.csv", "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                img_id = row["image_id"]
                img_path = os.path.join("dataset", row["file_path"])
                if os.path.exists(img_path) and os.path.exists(ocr_bin):
                    try:
                        res = subprocess.run([ocr_bin, img_path], capture_output=True, text=True, check=True)
                        extracted = res.stdout.strip()
                        if extracted:
                            ocr_results[img_id] = extracted
                            print(f"  [OCR] {img_id}: {extracted[:60]}...")
                    except Exception as e:
                        print(f"  [OCR Error] {img_id}: {e}")

    with open(ocr_cache_path, "w", encoding="utf-8") as f:
        json.dump(ocr_results, f, indent=2)
    print(f"Saved {len(ocr_results)} OCR transcripts to {ocr_cache_path}")

    # 2. Whisper ASR Transcription
    asr_results = {}
    if os.path.exists("dataset/voice_notes.csv"):
        print("Transcribing voice notes from dataset/voice_notes.csv with Whisper...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        with open("dataset/voice_notes.csv", "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                vn_id = row["voice_note_id"]
                audio_path = os.path.join("dataset", row["file_path"])
                if os.path.exists(audio_path):
                    try:
                        segments, info = model.transcribe(audio_path)
                        text = " ".join([s.text for s in segments]).strip()
                        if text:
                            asr_results[vn_id] = text
                            print(f"  [ASR] {vn_id}: \"{text}\"")
                    except Exception as e:
                        print(f"  [ASR Error] {vn_id}: {e}")

    with open(asr_cache_path, "w", encoding="utf-8") as f:
        json.dump(asr_results, f, indent=2)
    print(f"Saved {len(asr_results)} ASR transcripts to {asr_cache_path}")

if __name__ == "__main__":
    extract_all()
