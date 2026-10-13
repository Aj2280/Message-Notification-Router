import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.abspath("code"))
from src.context_builder import ContextBuilder
from src.decision_logic import DecisionRouter
from src.trained_router import TrainedRouter
from src.llm_router import LLMRouter
from src.evidence_selector import EvidenceSelector

# ANSI Color formatting for terminal
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
WHITE   = "\033[97m"

ACTION_BADGES = {
    "notify": f"{GREEN}{BOLD}🔔 NOTIFY (Interrupt Now){RESET}",
    "digest": f"{YELLOW}{BOLD}📥 DIGEST (Batch Later) {RESET}",
    "mute":   f"{RED}{BOLD}🔕 MUTE   (Suppress Risk){RESET}"
}

print(f"{BOLD}{CYAN}Initializing ContextBuilder, Trained ML Model, and Decision Router...{RESET}")
cb = ContextBuilder("dataset")
trained_ml_router = TrainedRouter()
fallback = trained_ml_router if trained_ml_router._ready else DecisionRouter()
router = LLMRouter(fallback_router=fallback)
evidence_selector = EvidenceSelector()

request_counter = 0

class WhatsAppWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default noisy HTTP server log to keep terminal clean
        return

    def do_GET(self):
        # Health check endpoint
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "status": "online",
            "service": "WhatsApp Notification Router AI",
            "model_ready": trained_ml_router._ready
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_POST(self):
        global request_counter
        request_counter += 1

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode("utf-8"))
            
            msg_id = payload.get("message_id", payload.get("id", f"msg_{request_counter:03d}"))
            user_id = payload.get("user_id", payload.get("recipient_id", "u_001"))
            conv_type = payload.get("conversation_type", payload.get("chat_type", "personal"))
            message_text = payload.get("message_text", payload.get("text", payload.get("body", "")))
            sender = payload.get("sender_user_id", payload.get("from", "Unknown"))
            
            msg_row = {
                "message_id": msg_id,
                "user_id": user_id,
                "conversation_type": conv_type,
                "group_id": payload.get("group_id", ""),
                "business_id": payload.get("business_id", ""),
                "sender_user_id": sender,
                "created_at": payload.get("created_at", "2026-08-01 12:00"),
                "message_text": message_text,
                "media_type": payload.get("media_type", ""),
                "media_id": payload.get("media_id", ""),
                "forwarded_count": payload.get("forwarded_count", 0)
            }

            case = cb.build_case(msg_row)
            pred = router.route(case)
            evidence = evidence_selector.select_evidence(case)

            action = pred["action"]
            mtype = pred["message_type"]
            reason = pred["reason"]
            conf = float(pred.get("confidence", 0.8))

            badge = ACTION_BADGES.get(action, action.upper())
            conf_percent = f"{conf * 100:.1f}%"
            conf_bar = f"[{'█' * int(conf * 10)}{'░' * (10 - int(conf * 10))}] {conf_percent}"

            # Print detailed terminal inspection card
            print(f"\n{BOLD}╔═══════════════════════════════════════════════════════════════════════════════╗{RESET}")
            print(f"{BOLD}║ 📩 INCOMING WHATSAPP MESSAGE #{request_counter:03d}                                            ║{RESET}")
            print(f"{BOLD}╠═══════════════════════════════════════════════════════════════════════════════╣{RESET}")
            print(f"║ {BOLD}Message ID{RESET}  : {CYAN}{msg_id}{RESET}")
            print(f"║ {BOLD}Conversation{RESET}: {MAGENTA}{conv_type.upper()}{RESET} (Sender: {sender})")
            display_text = message_text.replace('\n', ' ')
            if len(display_text) > 65:
                display_text = display_text[:62] + "..."
            print(f"║ {BOLD}Text Content{RESET}: {WHITE}\"{display_text}\"{RESET}")
            if case.get("ocr_text"):
                ocr_preview = case['ocr_text'][:60] + "..." if len(case['ocr_text']) > 60 else case['ocr_text']
                print(f"║ {BOLD}Flyer OCR{RESET}   : {YELLOW}{ocr_preview}{RESET}")
            if case.get("voice_text"):
                print(f"║ {BOLD}Voice ASR{RESET}   : {GREEN}\"{case['voice_text']}\"{RESET}")
            print(f"{BOLD}╠───────────────────────────────────────────────────────────────────────────────╢{RESET}")
            print(f"║ {BOLD}AI DECISION{RESET} : {badge}")
            print(f"║ {BOLD}Category{RESET}    : {CYAN}{BOLD}{mtype.upper()}{RESET}")
            print(f"║ {BOLD}Confidence{RESET}  : {conf_bar}")
            print(f"║ {BOLD}Reason{RESET}      : {reason}")
            print(f"║ {BOLD}Evidence IDs{RESET}: {DIM}{evidence}{RESET}")
            print(f"{BOLD}╚═══════════════════════════════════════════════════════════════════════════════╝{RESET}\n")

            response_data = {
                "message_id": msg_id,
                "action": action,
                "message_type": mtype,
                "reason": reason,
                "confidence": conf,
                "evidence_message_ids": evidence
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data, indent=2).encode("utf-8"))

        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            err_res = {"error": "Invalid payload", "details": str(e)}
            self.wfile.write(json.dumps(err_res).encode("utf-8"))

def run_server(port=8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, WhatsAppWebhookHandler)
    print(f"\n{BOLD}{GREEN}========================================================================{RESET}")
    print(f"{BOLD}{GREEN} 🚀 WhatsApp Notification Router AI Engine Live on Port {port} {RESET}")
    print(f"{BOLD}{GREEN}========================================================================{RESET}")
    print(f"{BOLD}Webhook Endpoint{RESET}: http://localhost:{port}/webhook/whatsapp")
    print(f"{DIM}Listening for incoming WhatsApp messages and outputting detailed terminal cards...{RESET}\n")
    httpd.serve_forever()

if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
