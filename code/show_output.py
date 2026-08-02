#!/usr/bin/env python3
"""
show_output.py — Terminal Output Viewer for WhatsApp Message Notification Router

Displays output predictions from dataset/output.csv (or messages.csv) in a clean,
formatted terminal interface with ANSI colors, action badges, and metadata cards.
"""

import csv
import sys
import os

# ANSI Color codes
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

ACTION_BADGES = {
    "notify": f"{GREEN}{BOLD}🟢 NOTIFY{RESET}",
    "digest": f"{YELLOW}{BOLD}🟡 DIGEST{RESET}",
    "mute":   f"{RED}{BOLD}🔴 MUTE  {RESET}"
}

def format_confidence_bar(conf_float):
    bars = int(conf_float * 10)
    empty = 10 - bars
    return f"[{'█' * bars}{'░' * empty}] {conf_float:.2f}"

def show_terminal_output(filter_action=None, limit=20):
    output_path = os.path.join("dataset", "output.csv")
    messages_path = os.path.join("dataset", "messages.csv")

    if not os.path.exists(output_path):
        print(f"{RED}Error: {output_path} not found. Run python3 code/main.py first.{RESET}")
        return

    with open(output_path, "r", encoding="utf-8") as f:
        predictions = list(csv.DictReader(f))

    msg_map = {}
    if os.path.exists(messages_path):
        with open(messages_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                msg_map[row["message_id"]] = row

    if filter_action:
        predictions = [p for p in predictions if p["action"].lower() == filter_action.lower()]

    print(f"\n{BOLD}{CYAN}========================================================================================{RESET}")
    print(f"{BOLD}{CYAN} 📱 WHATSAPP MESSAGE NOTIFICATION ROUTER — TERMINAL OUTPUT DASHBOARD {RESET}")
    print(f"{BOLD}{CYAN}========================================================================================{RESET}\n")

    # Summary Statistics
    total = len(predictions)
    notify_cnt = sum(1 for p in predictions if p["action"] == "notify")
    digest_cnt = sum(1 for p in predictions if p["action"] == "digest")
    mute_cnt   = sum(1 for p in predictions if p["action"] == "mute")

    print(f"{BOLD}Summary Stats ({total} Total Messages Shown):{RESET}")
    print(f"  {GREEN}🟢 NOTIFY (Immediate Alert) : {notify_cnt}{RESET}")
    print(f"  {YELLOW}🟡 DIGEST (Batch Later)    : {digest_cnt}{RESET}")
    print(f"  {RED}🔴 MUTE   (Suppress/Scam)  : {mute_cnt}{RESET}\n")

    print(f"{BOLD}{'ID':<10} | {'ACTION':<10} | {'TYPE':<16} | {'CONFIDENCE':<16} | {'EVIDENCE':<20}{RESET}")
    print("-" * 88)

    displayed = 0
    for p in predictions:
        if limit and displayed >= limit:
            break

        mid = p["message_id"]
        action = p["action"]
        mtype = p["message_type"]
        conf = float(p.get("confidence", 0.0))
        evidence = p.get("evidence_message_ids", "none")
        reason = p.get("reason", "")
        
        badge = ACTION_BADGES.get(action, action.upper())
        conf_bar = format_confidence_bar(conf)

        print(f"{BOLD}{mid:<10}{RESET} | {badge:<18} | {CYAN}{mtype:<16}{RESET} | {conf_bar:<16} | {DIM}{evidence:<20}{RESET}")
        
        # If message text is available, print a brief snippet & reason card
        if mid in msg_map:
            orig_text = (msg_map[mid].get("message_text") or "").strip().replace("\n", " ")
            if len(orig_text) > 75:
                orig_text = orig_text[:72] + "..."
            if orig_text:
                print(f"   {DIM}💬 \"{orig_text}\"{RESET}")
        print(f"   {BLUE}💡 Reason: {reason}{RESET}")
        print("-" * 88)

        displayed += 1

    if limit and len(predictions) > limit:
        print(f"{DIM}... and {len(predictions) - limit} more rows. Run with higher limit or filter flags to inspect.{RESET}\n")

if __name__ == "__main__":
    filter_act = None
    limit_val = 15
    if len(sys.argv) > 1:
        if sys.argv[1] in ["notify", "digest", "mute"]:
            filter_act = sys.argv[1]
        elif sys.argv[1].isdigit():
            limit_val = int(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        limit_val = int(sys.argv[2])

    show_terminal_output(filter_action=filter_act, limit=limit_val)
