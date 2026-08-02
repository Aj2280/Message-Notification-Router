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

print("Initializing ContextBuilder, Trained ML Model, and LLM Router for WhatsApp Webhook Server...")
cb = ContextBuilder("dataset")
trained_ml_router = TrainedRouter()
fallback = trained_ml_router if trained_ml_router._ready else DecisionRouter()
router = LLMRouter(fallback_router=fallback)
evidence_selector = EvidenceSelector()

class WhatsAppWebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Health check & Webhook Verification
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"status": "online", "service": "WhatsApp Notification Router AI"}
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_POST(self):
        # Receive incoming WhatsApp Webhook JSON payload
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode("utf-8"))
            
            # Map Meta/Twilio or custom WhatsApp webhook payload to routing case
            msg_id = payload.get("message_id", payload.get("id", "web_msg_001"))
            user_id = payload.get("user_id", payload.get("recipient_id", "u_001"))
            conv_type = payload.get("conversation_type", payload.get("chat_type", "personal"))
            message_text = payload.get("message_text", payload.get("text", payload.get("body", "")))
            
            msg_row = {
                "message_id": msg_id,
                "user_id": user_id,
                "conversation_type": conv_type,
                "group_id": payload.get("group_id", ""),
                "business_id": payload.get("business_id", ""),
                "sender_user_id": payload.get("sender_user_id", payload.get("from", "")),
                "created_at": payload.get("created_at", "2026-08-01 12:00"),
                "message_text": message_text,
                "media_type": payload.get("media_type", ""),
                "media_id": payload.get("media_id", ""),
                "forwarded_count": payload.get("forwarded_count", 0)
            }

            case = cb.build_case(msg_row)
            pred = router.route(case)
            evidence = evidence_selector.select_evidence(case)

            response_data = {
                "message_id": msg_id,
                "action": pred["action"],
                "message_type": pred["message_type"],
                "reason": pred["reason"],
                "confidence": pred["confidence"],
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
    print(f"--- WhatsApp Notification Router Server Live on Port {port} ---")
    print(f"Webhook URL: http://localhost:{port}/webhook/whatsapp")
    print("Send POST requests with WhatsApp message JSON payloads to get real-time routing decisions.")
    httpd.serve_forever()

if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
