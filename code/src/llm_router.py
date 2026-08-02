"""
llm_router.py
─────────────────────────────────────────────────────────────────────────────
Expert AI Message Notification Router — LLM-Backed Engine

Embeds the full structured system-prompt specification and builds a rich
context payload for every incoming message, then returns a deterministic
structured JSON routing decision.

This module is the "LLM interface layer". When an API key for Gemini /
OpenAI is available it calls the live model. When no key is present it
falls back to the high-accuracy local decision engine so the pipeline
always produces valid output.
─────────────────────────────────────────────────────────────────────────────
"""

import json
import os
import re

# ─── System Prompt (verbatim from challenge specification) ──────────────────

SYSTEM_PROMPT = """You are an expert AI Message Notification Router for WhatsApp.
Your goal is to evaluate incoming messages and make personalized, context-aware notification routing decisions.

### INPUT CONTEXT:
For each incoming message, you will receive:
1. Incoming Message Payload: message_id, user_id, conversation_type (personal/group/business), text content, media (image OCR or voice transcription), and forwarding count.
2. Receiving User Profile: quiet hours, historical open/reply/dismiss rates.
3. Group / Business Metadata: user group role, group mute state, business verification status, user opt-in/opt-out history.
4. Historical Evidence: Related past message logs and user reaction events.

### CRITICAL ROUTING RULES:
1. SAFETY & SCAMS (Highest Priority): Any message containing high-risk scam indicators (lottery wins, OTP requests, urgent bank blocks, suspicious wire transfers, phishing links) or excessive forwarding count (>10) MUST be assigned action="mute" and message_type="scam" or "spam", regardless of user settings.
2. USER OVERRIDES & MUTES:
   - If a group is muted by the user, action MUST be "mute", UNLESS there is a direct @mention of the user (which escalates to "notify" personal/urgent).
   - If a user opted out of a business, set action="mute".
3. NOTIFY (Immediate Interruption): High priority personal messages, direct mentions in groups, time-sensitive payment reminders, urgent family/work emergencies.
4. DIGEST (Show Later): Useful but non-urgent content—opted-in business updates, valid promotional offers, group event notices, routine greetings.
5. EVIDENCE MATCHING: Reference relevant past message IDs from historical context as semicolon-separated string (e.g., "msg_102;msg_405"). If no relevant match exists, output "none".

### ALLOWED VALUES:
- action: notify | digest | mute
- message_type: personal | urgent | event | payment | business_update | promotion | greeting | forward | spam | scam | unknown

### OUTPUT FORMAT:
Respond ONLY with a valid JSON object matching this structure:
{
  "message_id": "<string>",
  "action": "<notify|digest|mute>",
  "message_type": "<type>",
  "reason": "<short concise human-readable explanation>",
  "confidence": <float between 0.0 and 1.0>,
  "evidence_message_ids": "<id1;id2 OR none>"
}"""


def build_user_prompt(case: dict) -> str:
    """Build a rich structured user prompt from a case object."""
    msg = case.get("message", {})
    user_info = case.get("user_info", {})
    group_info = case.get("group_info", {})
    membership = case.get("membership", {})
    biz_info = case.get("biz_info", {})
    biz_history = case.get("biz_history", {})
    user_history = case.get("user_history", [])
    ocr_text = case.get("ocr_text", "")

    evidence_snippet = ""
    if user_history:
        evidence_snippet = "\n".join(
            f"  - [{h.get('message_id', '')}] {h.get('message_text', '')[:80]} "
            f"| event={h.get('event_type', '')} dismissed={h.get('notification_dismissed', '')}"
            for h in user_history[:5]
        )

    prompt = f"""### INCOMING MESSAGE PAYLOAD:
message_id       : {msg.get('message_id', '')}
user_id          : {msg.get('user_id', '')}
conversation_type: {msg.get('conversation_type', '')}
group_id         : {msg.get('group_id', '')}
business_id      : {msg.get('business_id', '')}
sender_user_id   : {msg.get('sender_user_id', '')}
forwarded_count  : {msg.get('forwarded_count', 0)}
media_type       : {msg.get('media_type', '')}

message_text:
\"\"\"{msg.get('message_text', '').strip()}\"\"\"

ocr_image_text (extracted from image poster if any):
\"\"\"{(ocr_text or '').strip()}\"\"\"

### RECEIVING USER PROFILE:
quiet_hours_start      : {user_info.get('quiet_hours_start', '')}
quiet_hours_end        : {user_info.get('quiet_hours_end', '')}
notifications_opened   : {user_info.get('notifications_opened_30d', '')}
notifications_dismissed: {user_info.get('notifications_dismissed_30d', '')}
reply_rate_30d         : {user_info.get('reply_rate_30d', '')}

### GROUP / BUSINESS METADATA:
group_type       : {group_info.get('group_type', '')}
group_size       : {group_info.get('member_count', '')}
user_group_role  : {membership.get('role', '')}
group_muted      : {membership.get('group_muted_by_user', '')}
biz_verified     : {biz_info.get('is_verified', '')}
biz_category     : {biz_info.get('category', '')}
opted_out        : {biz_history.get('promotions_opted_out_at', '')}
why_knows_biz    : {biz_history.get('why_user_knows_account', '')}

### HISTORICAL EVIDENCE (last 5 related messages):
{evidence_snippet or 'none'}

Now produce a routing decision. Respond ONLY with the JSON object specified in the system prompt."""

    return prompt


class LLMRouter:
    """
    LLM-backed router that:
      1. Tries Gemini Flash API (if GEMINI_API_KEY env var is set).
      2. Falls back to local DecisionRouter (always available).
    """

    def __init__(self, fallback_router=None):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.fallback_router = fallback_router
        self._gemini_model = None

        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._gemini_model = genai.GenerativeModel(
                    model_name="gemini-2.0-flash",
                    system_instruction=SYSTEM_PROMPT,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    }
                )
                print("✅ LLMRouter: Gemini 2.0 Flash model loaded with expert system prompt.")
            except Exception as e:
                print(f"⚠️  LLMRouter: Gemini init failed ({e}). Using local fallback engine.")
                self._gemini_model = None
        else:
            print("ℹ️  LLMRouter: No GEMINI_API_KEY set. Using local deterministic engine.")

    def route(self, case: dict) -> dict:
        """Route a message. Returns a prediction dict."""
        msg_id = case.get("message", {}).get("message_id", "unknown")

        # ── Try Gemini API ──────────────────────────────────────────────────
        if self._gemini_model:
            try:
                user_prompt = build_user_prompt(case)
                response = self._gemini_model.generate_content(user_prompt)
                raw = response.text.strip()

                # Strip markdown fences if present
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

                result = json.loads(raw)

                # Validate required fields
                assert result.get("action") in ("notify", "digest", "mute")
                assert result.get("message_type") in (
                    "personal", "urgent", "event", "payment", "business_update",
                    "promotion", "greeting", "forward", "spam", "scam", "unknown"
                )

                return {
                    "action": result["action"],
                    "message_type": result["message_type"],
                    "reason": result.get("reason", "AI routing decision."),
                    "confidence": float(result.get("confidence", 0.85)),
                    "evidence_message_ids": result.get("evidence_message_ids", "none"),
                }

            except Exception as e:
                print(f"⚠️  LLMRouter: Gemini call failed for {msg_id} ({e}). Falling back to local engine.")

        # ── Fallback: local deterministic engine ────────────────────────────
        if self.fallback_router:
            pred = self.fallback_router.route(case)
            return pred

        # ── Last resort default ─────────────────────────────────────────────
        return {
            "action": "digest",
            "message_type": "unknown",
            "reason": "Default fallback: no routing engine available.",
            "confidence": 0.5,
        }
