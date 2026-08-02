import csv
import sys
import os

sys.path.insert(0, os.path.abspath("code"))
from src.context_builder import ContextBuilder
from src.decision_logic import DecisionRouter
from src.llm_router import LLMRouter
from src.evidence_selector import EvidenceSelector

def main():
    dataset_dir = "dataset"
    messages_path = os.path.join(dataset_dir, "messages.csv")
    output_path = os.path.join(dataset_dir, "output.csv")

    if not os.path.exists(messages_path):
        print(f"Error: {messages_path} does not exist.")
        sys.exit(1)

    print("Initializing Message Notification Router pipeline...")
    cb = ContextBuilder(dataset_dir)
    local_router = DecisionRouter()
    router = LLMRouter(fallback_router=local_router)  # Uses Gemini API if GEMINI_API_KEY is set, else local engine
    evidence_selector = EvidenceSelector()

    print(f"Reading incoming messages from {messages_path}...")
    with open(messages_path, mode="r", encoding="utf-8") as f:
        messages = list(csv.DictReader(f))

    print(f"Processing {len(messages)} messages...")
    output_rows = []
    action_counts = {"notify": 0, "digest": 0, "mute": 0}

    for row in messages:
        case = cb.build_case(row)
        pred = router.route(case)
        evidence = evidence_selector.select_evidence(case)

        action = pred["action"]
        mtype = pred["message_type"]
        reason = pred["reason"]
        confidence = pred["confidence"]

        action_counts[action] = action_counts.get(action, 0) + 1

        output_rows.append({
            "message_id": row["message_id"],
            "action": action,
            "message_type": mtype,
            "reason": reason,
            "confidence": confidence,
            "evidence_message_ids": evidence
        })

    print(f"Writing {len(output_rows)} predictions to {output_path}...")
    fieldnames = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]
    with open(output_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print("--- Pipeline Execution Complete ---")
    print(f"Total Predictions: {len(output_rows)}")
    print(f"Action Distribution: {action_counts}")
    print(f"Saved successfully to {output_path}")

if __name__ == "__main__":
    main()
