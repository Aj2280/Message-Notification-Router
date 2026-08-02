import sys
import os

sys.path.insert(0, os.path.abspath("code"))
from src.context_builder import ContextBuilder
from src.decision_logic import DecisionRouter
from src.evidence_selector import EvidenceSelector

def run_interactive_simulation():
    print("=" * 65)
    print("      WhatsApp Message Notification Router - Live Simulator     ")
    print("=" * 65)
    print("Loading context builder and decision router...")
    
    cb = ContextBuilder("dataset")
    router = DecisionRouter()
    evidence_selector = EvidenceSelector()

    print("\nSystem ready! You can simulate incoming WhatsApp messages.\n")

    test_cases = [
        {
            "label": "Scenario A: Urgent Group Water Supply Alert",
            "message_id": "sim_001",
            "user_id": "u_011",
            "conversation_type": "group",
            "group_id": "group_002",
            "sender_user_id": "u_043",
            "created_at": "2026-07-31 11:09",
            "message_text": "Tower B folks, quick heads-up. Water tanker is here, please store drinking water now!",
            "media_type": "",
            "media_id": ""
        },
        {
            "label": "Scenario B: Phishing / Scam OTP Trap (Adversarial)",
            "message_id": "sim_002",
            "user_id": "u_049",
            "conversation_type": "personal",
            "group_id": "",
            "sender_user_id": "u_050",
            "created_at": "2026-07-31 14:00",
            "message_text": "Security alert: OTP may have leaked. Verify now at account-login.in or profile blocked in 2 hrs.",
            "media_type": "",
            "media_id": ""
        },
        {
            "label": "Scenario C: Verified Order Delivery Update",
            "message_id": "sim_003",
            "user_id": "u_001",
            "conversation_type": "business",
            "group_id": "",
            "business_id": "business_001",
            "created_at": "2026-07-31 08:28",
            "message_text": "Your order ending 4821 has been packed and is expected to reach local hub today.",
            "media_type": "",
            "media_id": ""
        }
    ]

    for tc in test_cases:
        print(f"--- {tc['label']} ---")
        print(f"User: {tc['user_id']} | Conv Type: {tc['conversation_type']}")
        print(f"Message: \"{tc['message_text']}\"")
        
        case = cb.build_case(tc)
        pred = router.route(case)
        evidence = evidence_selector.select_evidence(case)

        print(f"➜ ROUTING ACTION  : {pred['action'].upper()}")
        print(f"  Message Category: {pred['message_type']}")
        print(f"  Confidence Score: {pred['confidence']}")
        print(f"  Evidence IDs    : {evidence}")
        print(f"  Reason          : {pred['reason']}\n")

if __name__ == "__main__":
    run_interactive_simulation()
