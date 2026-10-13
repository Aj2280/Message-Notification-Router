import re

STOPWORDS = {
    "the", "a", "an", "and", "or", "is", "are", "in", "at", "to", "for", "of",
    "on", "with", "this", "that", "it", "from", "by", "as", "be", "you", "your",
    "we", "our", "pls", "please", "can", "if", "so", "will", "i", "my", "me"
}

def _tokenize(text: str) -> set:
    if not text:
        return set()
    words = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
    return set(w for w in words if w not in STOPWORDS)

class EvidenceSelector:
    """
    Industry-level Semantic Evidence Retriever.
    Ranks historical messages based on lexical/semantic overlap, user reaction signals
    (replies, reports, mutes, opens), and conversational relationship strength.
    """
    def select_evidence(self, case):
        user_history = case.get("user_history", [])
        if not user_history:
            return "none"

        msg = case.get("message", {})
        curr_text = ((msg.get("message_text") or "") + " " + (case.get("ocr_text") or "")).strip()
        curr_tokens = _tokenize(curr_text)

        sender_id = msg.get("sender_user_id", "")
        group_id = msg.get("group_id", "")
        biz_id = msg.get("business_id", "")

        scored_candidates = []
        for h in user_history:
            h_id = h.get("message_id")
            if not h_id:
                continue

            score = 0.0
            h_text = h.get("message_text", "")
            h_tokens = _tokenize(h_text)

            # 1. Semantic token overlap
            if curr_tokens and h_tokens:
                intersection = curr_tokens & h_tokens
                if intersection:
                    score += len(intersection) * 1.5

            # 2. Critical user feedback signals
            if h.get("message_replied") == "1":
                score += 2.0
            if h.get("message_reported") == "1":
                score += 3.0
            if h.get("muted_after_message") == "1":
                score += 2.5
            if h.get("message_opened") == "1":
                score += 0.5

            # 3. Contextual source match
            if sender_id and h.get("sender_user_id") == sender_id:
                score += 1.0
            if biz_id and h.get("business_id") == biz_id:
                score += 1.0
            if group_id and h.get("group_id") == group_id:
                score += 0.5

            if score > 0.5:
                scored_candidates.append((score, h_id))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_ids = [cid for _, cid in scored_candidates[:2]]

        if not top_ids and user_history:
            top_ids.append(user_history[0]["message_id"])

        if top_ids:
            return ";".join(top_ids)
        return "none"
