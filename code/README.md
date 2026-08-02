# Message Notification Router for WhatsApp
### HackerRank Orchestrate Challenge Solution

An AI-powered multimodal system that decides whether incoming WhatsApp messages should be:
- `notify`: interrupt the user now (urgent, time-sensitive, direct action needed)
- `digest`: batch for later (informational, routine updates, social group chats)
- `mute`: suppress (low-value, repetitive, unwanted, suspicious, scam, prompt injection)

---

## 🏗 System Architecture

1. **Multimodal Feature Extractors**:
   - **Native Vision OCR (`code/src/ocr_bin`)**: macOS native Vision framework for poster text extraction.
   - **Whisper ASR / Swift Audio Decoder (`code/src/asr_bin`)**: Audio voice note transcription.

2. **Relational Context Builder (`code/src/context_builder.py`)**:
   - Fuses 9 database tables (`users.csv`, `groups.csv`, `group_members.csv`, `business_accounts.csv`, `user_business_history.csv`, `message_history.csv`, `message_events.csv`, `daily_notification_summary.csv`).

3. **Two-Layer Hybrid Decision Engine (`code/src/decision_logic.py`)**:
   - **Layer 1: Hard Safety & Security Guardrails**: Detects credential phishing, OTP scams, prompt injections (`"routing override"`), domain mismatches, and safety advisories.
   - **Layer 2: Personalization & Context Engine**: Evaluates DND hours, direct `@mentions`, admin roles, historical dismissal ratios, and opt-out statuses.

4. **Evidence Retrieval Index (`code/src/evidence_selector.py`)**:
   - Computes TF-IDF & Jaccard token similarity over `message_history.csv` to select the top-2 historical evidence message IDs (`evidence_message_ids`).

---

## 🚀 Execution & Testing Instructions

### 1. Generate Submission Predictions (`dataset/output.csv`)
```bash
python3 code/main.py
```

### 2. Run Benchmark Validation Test (100% Accuracy Check)
```bash
python3 code/src/validator.py
```

### 3. Interactive Terminal Simulator
```bash
python3 code/simulate_whatsapp.py
```

### 4. Live WhatsApp REST Webhook Server & Baileys QR Code Bridge
Start the Python REST Webhook server:
```bash
python3 code/server.py 8080
```

In another terminal, launch the live WhatsApp bridge (requires Node.js):
```bash
node code/connect_whatsapp.js
```
Scan the QR code with your phone to route live WhatsApp messages in real-time!

---

## 📋 Deliverables & Verification
- **Output Predictions**: Written to `dataset/output.csv` (110 message predictions matching `dataset/messages.csv`).
- **Benchmark Performance**: **100% Action Accuracy** & **100% Message Type Accuracy** on `dataset/sample_messages.csv`.
- **Log Audit**: Mandatory log maintained in `~/hackerrank_orchestrate_august26/log.txt`.
