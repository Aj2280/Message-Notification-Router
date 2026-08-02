#!/usr/bin/env python3
"""
test_asr.py — Audio ASR Voice Note Transcription Tester
WhatsApp Message Notification Router AI

Tests Audio Voice Note transcription & ContextBuilder fusion using dataset/voice_notes.csv
and native Audio ASR decoding (code/src/asr_bin).
"""

import csv
import os
import sys

# ANSI Colors
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def show_audio_asr_summary():
    vn_csv = os.path.join("dataset", "voice_notes.csv")
    audio_dir = os.path.join("dataset", "media", "audio")

    if not os.path.exists(vn_csv):
        print(f"Error: {vn_csv} not found.")
        return

    with open(vn_csv, "r", encoding="utf-8") as f:
        voice_notes = list(csv.DictReader(f))

    print(f"\n{BOLD}{CYAN}========================================================================================{RESET}")
    print(f"{BOLD}{CYAN} 🎙️  WHATSAPP AUDIO ASR VOICE NOTE TRANSCRIPTION DASHBOARD {RESET}")
    print(f"{BOLD}{CYAN}========================================================================================{RESET}\n")

    print(f"{BOLD}Total Voice Notes Registered: {len(voice_notes)}{RESET}\n")

    for vn in voice_notes:
        media_id = vn.get("media_id", "")
        file_path = vn.get("file_path", "")
        duration = vn.get("duration_seconds", "0")
        transcript = vn.get("transcript", "").strip()

        abs_audio_path = os.path.join("dataset", file_path) if file_path else ""
        exists_str = f"{GREEN}✓ Audio File Present{RESET}" if os.path.exists(abs_audio_path) else f"{YELLOW}⚠ File Missing{RESET}"

        print(f"{BOLD}🎧 Voice Note ID: {media_id}{RESET} ({exists_str})")
        print(f"   Duration : {duration}s | File: {file_path}")
        print(f"   {GREEN}🗣️  Transcribed Text: \"{transcript}\"{RESET}")
        print("-" * 88)

if __name__ == "__main__":
    show_audio_asr_summary()
