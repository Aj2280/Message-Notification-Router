import csv
import sys
import os

sys.path.insert(0, os.path.abspath("code"))
from src.context_builder import ContextBuilder
from src.decision_logic import DecisionRouter
from src.evidence_selector import EvidenceSelector

class Validator:
    def __init__(self, dataset_dir="dataset"):
        self.dataset_dir = dataset_dir
        self.cb = ContextBuilder(dataset_dir)
        self.router = DecisionRouter()
        self.evidence_selector = EvidenceSelector()

    def validate_sample_messages(self, sample_filename="sample_messages.csv"):
        sample_path = os.path.join(self.dataset_dir, sample_filename)
        if not os.path.exists(sample_path):
            print(f"Sample file {sample_path} not found.")
            return

        with open(sample_path, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        total = len(reader)
        action_matches = 0
        type_matches = 0

        print(f"--- Evaluating {total} sample messages ---")
        for row in reader:
            msg_id = row["message_id"]
            true_action = row["action"]
            true_type = row["message_type"]

            case = self.cb.build_case(row)
            pred = self.router.route(case)
            evidence = self.evidence_selector.select_evidence(case)

            pred_action = pred["action"]
            pred_type = pred["message_type"]

            a_match = (pred_action == true_action)
            t_match = (pred_type == true_type)

            if a_match:
                action_matches += 1
            if t_match:
                type_matches += 1

            status = "OK" if (a_match and t_match) else "MISMATCH"
            print(f"[{status:8s}] {msg_id}: Action (True={true_action:6s}, Pred={pred_action:6s}) | Type (True={true_type:15s}, Pred={pred_type:15s})")

        print(f"\n--- Accuracy Results ---")
        print(f"Action Accuracy: {action_matches}/{total} ({action_matches/total*100:.1f}%)")
        print(f"Message Type Accuracy: {type_matches}/{total} ({type_matches/total*100:.1f}%)")

if __name__ == "__main__":
    validator = Validator()
    validator.validate_sample_messages()
