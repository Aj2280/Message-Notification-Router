class EvidenceSelector:
    def select_evidence(self, case):
        user_history = case.get("user_history", [])
        if not user_history:
            return "none"

        msg = case.get("message", {})
        sender_id = msg.get("sender_user_id", "")
        group_id = msg.get("group_id", "")
        biz_id = msg.get("business_id", "")

        matched_ids = []
        for h in user_history:
            h_id = h.get("message_id")
            if not h_id:
                continue

            # Prioritize historical messages with direct reactions (replied, reported, muted)
            if h.get("message_replied") == "1" or h.get("message_reported") == "1" or h.get("muted_after_message") == "1":
                matched_ids.append(h_id)
            elif sender_id and h.get("sender_user_id") == sender_id:
                matched_ids.append(h_id)
            elif biz_id and h.get("business_id") == biz_id:
                matched_ids.append(h_id)

            if len(matched_ids) >= 2:
                break

        if not matched_ids and user_history:
            # Fallback to most recent historical message if relevant
            matched_ids.append(user_history[0]["message_id"])

        if matched_ids:
            return ";".join(matched_ids[:3])
        return "none"
