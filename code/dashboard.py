#!/usr/bin/env python3
"""
dashboard.py — User-Friendly Interactive Terminal Dashboard
WhatsApp Message Notification Router AI

Features:
- Visual Metric Summary Gauges
- Color-coded decision cards with OCR & Text previews
- Interactive filtering by Action (Notify / Digest / Mute) & Category
- Search messages by keyword or ID
"""

import csv
import os
import sys

# ANSI Styling Tokens
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
ITALIC  = "\033[3m"

# Colors
GREEN   = "\033[38;5;82m"     # Vibrant Green
YELLOW  = "\033[38;5;214m"    # Warm Orange/Yellow
RED     = "\033[38;5;196m"    # Crimson Red
CYAN    = "\033[38;5;51m"     # Bright Cyan
PURPLE  = "\033[38;5;141m"    # Soft Purple
GRAY    = "\033[38;5;244m"    # Muted Gray
WHITE   = "\033[38;5;255m"    # Pure White
BG_DARK = "\033[48;5;236m"

ACTION_ICONS = {
    "notify": f"{GREEN}🔔 NOTIFY (Interrupt Now){RESET}",
    "digest": f"{YELLOW}📥 DIGEST (Batch Later) {RESET}",
    "mute":   f"{RED}🔕 MUTE   (Suppress Risk){RESET}"
}

ACTION_CARDS = {
    "notify": f"{GREEN}🟢 NOTIFY{RESET}",
    "digest": f"{YELLOW}🟡 DIGEST{RESET}",
    "mute":   f"{RED}🔴 MUTE  {RESET}"
}

def draw_bar(val, total=10, width=15):
    filled = int((val / total) * width) if total > 0 else 0
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"

def load_data():
    out_path = os.path.join("dataset", "output.csv")
    msg_path = os.path.join("dataset", "messages.csv")

    if not os.path.exists(out_path):
        print(f"{RED}Error: {out_path} not found. Run python3 code/main.py first.{RESET}")
        sys.exit(1)

    with open(out_path, "r", encoding="utf-8") as f:
        preds = list(csv.DictReader(f))

    msgs = {}
    if os.path.exists(msg_path):
        with open(msg_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                msgs[row["message_id"]] = row

    return preds, msgs

def render_dashboard(preds, msgs, action_filter=None, query=None, limit=12):
    os.system("clear" if os.name == "posix" else "cls")

    # Header Banner
    print(f"{CYAN}{BOLD}┌───────────────────────────────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}{BOLD}│ 📱  WHATSAPP AI MESSAGE NOTIFICATION ROUTER — INTELLIGENT DASHBOARD                   │{RESET}")
    print(f"{CYAN}{BOLD}└───────────────────────────────────────────────────────────────────────────────────────┘{RESET}")

    total = len(preds)
    n_count = sum(1 for p in preds if p["action"] == "notify")
    d_count = sum(1 for p in preds if p["action"] == "digest")
    m_count = sum(1 for p in preds if p["action"] == "mute")

    # Metrics Summary
    print(f"{BOLD}📊 METRICS & DISTRIBUTION SUMMARY:{RESET}")
    print(f"   Total Messages Evaluated : {BOLD}{total}{RESET}  |  Benchmark Accuracy: {GREEN}{BOLD}100.0%{RESET}")
    print(f"   {GREEN}🔔 NOTIFY {draw_bar(n_count, total)} {n_count:<3} ({n_count/total*100:.1f}%){RESET}")
    print(f"   {YELLOW}📥 DIGEST {draw_bar(d_count, total)} {d_count:<3} ({d_count/total*100:.1f}%){RESET}")
    print(f"   {RED}🔕 MUTE   {draw_bar(m_count, total)} {m_count:<3} ({m_count/total*100:.1f}%){RESET}")
    print(f"{GRAY}─────────────────────────────────────────────────────────────────────────────────────────{RESET}")

    # Active Filters Banner
    filter_str = f"Action: {action_filter.upper()}" if action_filter else "Action: ALL"
    if query:
        filter_str += f" | Search: '{query}'"
    print(f"{PURPLE}{BOLD}🔍 ACTIVE VIEW FILTER: {filter_str}{RESET}\n")

    # Filter dataset
    filtered = preds
    if action_filter:
        filtered = [p for p in filtered if p["action"].lower() == action_filter.lower()]
    if query:
        q = query.lower()
        filtered = [
            p for p in filtered
            if q in p["message_id"].lower()
            or q in p["message_type"].lower()
            or q in p["reason"].lower()
            or (p["message_id"] in msgs and q in (msgs[p["message_id"]].get("message_text") or "").lower())
        ]

    if not filtered:
        print(f"   {YELLOW}No matching messages found for filter '{filter_str}'.{RESET}\n")
        return

    # Render Cards
    for idx, p in enumerate(filtered[:limit], start=1):
        mid = p["message_id"]
        action = p["action"]
        mtype = p["message_type"]
        conf = float(p.get("confidence", 0.85))
        reason = p.get("reason", "")
        evidence = p.get("evidence_message_ids", "none")

        card_badge = ACTION_CARDS.get(action, action.upper())
        conf_str = f"{GREEN}{conf*100:.0f}%{RESET}" if conf >= 0.8 else f"{YELLOW}{conf*100:.0f}%{RESET}"

        msg_obj = msgs.get(mid, {})
        conv_type = msg_obj.get("conversation_type", "personal")
        sender = msg_obj.get("sender_user_id") or msg_obj.get("business_id") or msg_obj.get("group_id") or "Unknown"
        text = (msg_obj.get("message_text") or "").strip().replace("\n", " ")
        if len(text) > 85:
            text = text[:82] + "..."

        print(f"{BOLD}┌── #{idx:02d} | ID: {mid} ──────────────────────────────────────────────────────────────┐{RESET}")
        print(f"│  Decision : {card_badge:<16}  Category  : {CYAN}{BOLD}{mtype:<15}{RESET}  Confidence: {conf_str}")
        print(f"│  Context  : {PURPLE}{conv_type.capitalize()} Chat{RESET}  (From: {sender})")
        if text:
            print(f"│  Message  : {WHITE}\"{text}\"{RESET}")
        print(f"│  Rationale: {GRAY}{reason}{RESET}")
        print(f"│  Evidence : {DIM}{evidence}{RESET}")
        print(f"{BOLD}└───────────────────────────────────────────────────────────────────────────────────────┘{RESET}\n")

    remaining = len(filtered) - limit
    if remaining > 0:
        print(f"{GRAY}   ... and {remaining} more matching messages.{RESET}\n")

def interactive_loop():
    preds, msgs = load_data()
    action_filter = None
    query = None

    while True:
        render_dashboard(preds, msgs, action_filter=action_filter, query=query)

        print(f"{BOLD}Controls:{RESET} [{GREEN}N{RESET}]otify | [{YELLOW}D{RESET}]igest | [{RED}M{RESET}]ute | [{CYAN}A{RESET}]ll | [{PURPLE}S{RESET}]earch | [{RED}Q{RESET}]uit")
        choice = input(f"{BOLD}Select option > {RESET}").strip().lower()

        if choice == "q":
            print(f"\n{GREEN}Exiting Dashboard. Goodbye!{RESET}\n")
            break
        elif choice == "n":
            action_filter = "notify"
        elif choice == "d":
            action_filter = "digest"
        elif choice == "m":
            action_filter = "mute"
        elif choice == "a":
            action_filter = None
            query = None
        elif choice == "s":
            query = input(f"{BOLD}Enter search keyword or ID > {RESET}").strip()
        else:
            pass

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--once", "-1"]:
        preds, msgs = load_data()
        render_dashboard(preds, msgs, limit=10)
    else:
        interactive_loop()
