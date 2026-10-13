"""
trained_router.py
─────────────────────────────────────────────────────────────────────────────
Inference module for the locally-trained ML models.
Loads saved TF-IDF + RandomForest classifiers from code/models/ and
provides the same .route(case) interface as DecisionRouter so it can
drop-in replace it anywhere in the pipeline.
─────────────────────────────────────────────────────────────────────────────
"""

import os, sys, pickle
import site

# Ensure user site-packages are on path if running Python 3.9
if sys.version_info[:2] == (3, 9) and os.path.exists("/Users/abhi/Library/Python/3.9/lib/python/site-packages"):
    sys.path.insert(0, "/Users/abhi/Library/Python/3.9/lib/python/site-packages")

import numpy as np
import scipy.sparse as sp

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

# ── Keyword lists (same as train_model.py) ──────────────────────────────────
SCAM_WORDS   = ["otp", "lottery", "prize", "bank block", "wire transfer",
                "phishing", "login code", "routing override", "verify now",
                "unauthorized", "reply with the 6 digit", "otp verification",
                "send the code", "password", "account-login", "claim reward"]
URGENT_WORDS = ["asap", "deadline", "immediately", "prod review", "come online now",
                "missing person", "water supply", "tanker", "quick heads-up",
                "escalation starts", "bus is leaving", "alert threshold"]
PROMO_WORDS  = ["sale", "discount", "50% off", "offer", "cashback", "tour package",
                "selling", "kurta set", "add-on", "ladakh", "buy 1 get 1"]


def _safe_int(v, default=0):
    try:
        return int(v) if v not in (None, "", "nan") else default
    except:
        return default


def _safe_float(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "nan") else default
    except:
        return default


def _extract_text(case: dict) -> str:
    msg = case.get("message", {})
    return ((msg.get("message_text") or "") + " " + (case.get("ocr_text") or "")).strip()


def _extract_numeric(case: dict) -> list:
    msg        = case.get("message", {})
    user       = case.get("user_info", {})
    membership = case.get("membership", {})
    biz_info   = case.get("biz_info", {})
    biz_hist   = case.get("biz_history", {})

    text_lower = _extract_text(case).lower()

    scam_score   = sum(1 for w in SCAM_WORDS   if w in text_lower)
    urgent_score = sum(1 for w in URGENT_WORDS if w in text_lower)
    promo_score  = sum(1 for w in PROMO_WORDS  if w in text_lower)

    conv_type   = msg.get("conversation_type", "")
    is_personal = int(conv_type == "personal")
    is_group    = int(conv_type == "group")
    is_business = int(conv_type == "business")

    media_type = msg.get("media_type", "")
    is_image   = int(media_type == "image")
    is_voice   = int(media_type == "voice")

    is_admin     = int(membership.get("role") == "admin")
    group_muted  = _safe_int(membership.get("group_muted_by_user"))
    is_mentioned = int(f"@{msg.get('user_id','xxx')}" in (msg.get("message_text") or ""))

    dismissed_30d = _safe_int(user.get("notifications_dismissed_30d"))
    opened_30d    = _safe_int(user.get("messages_opened_30d"))
    replied_30d   = _safe_int(user.get("messages_replied_30d"))
    reported_30d  = _safe_int(user.get("messages_reported_30d"))

    biz_verified  = _safe_int(biz_info.get("is_verified"))
    biz_reports   = _safe_int(biz_info.get("user_reports_30d"))
    opted_out     = int(bool(biz_hist.get("promotions_opted_out_at")))
    allows_promos = _safe_int(biz_hist.get("allows_promotions"), default=1)

    forwarded_count = _safe_int(msg.get("forwarded_count"))
    is_dnd          = int(case.get("is_dnd", False))
    domain_mismatch = int(case.get("domain_mismatch", False))

    return [
        scam_score, urgent_score, promo_score,
        is_personal, is_group, is_business,
        is_image, is_voice,
        is_admin, group_muted, is_mentioned,
        dismissed_30d, opened_30d, replied_30d, reported_30d,
        biz_verified, biz_reports, opted_out, allows_promos,
        forwarded_count, is_dnd, domain_mismatch,
    ]


def _load(name):
    with open(os.path.join(MODEL_DIR, f"{name}.pkl"), "rb") as f:
        return pickle.load(f)


class TrainedRouter:
    """
    Locally-trained ML classifier (TF-IDF + RandomForest).
    Drop-in replacement for DecisionRouter with .route(case) → dict API.
    """

    def __init__(self):
        try:
            self.tfidf     = _load("tfidf")
            self.clf_action= _load("clf_action")
            self.clf_mtype = _load("clf_mtype")
            self.le_action = _load("le_action")
            self.le_mtype  = _load("le_mtype")
            self._ready    = True
            print("✅ TrainedRouter: ML models loaded from code/models/")
        except Exception as e:
            self._ready = False
            print(f"⚠️  TrainedRouter: Could not load models ({e}). Run python3 code/train_model.py first.")

    def route(self, case: dict) -> dict:
        if not self._ready:
            return {
                "action": "digest",
                "message_type": "unknown",
                "reason": "Trained model not available. Run code/train_model.py first.",
                "confidence": 0.5,
            }

        text    = _extract_text(case)
        numeric = np.array([_extract_numeric(case)], dtype=float)

        tfidf_vec = self.tfidf.transform([text])
        X = sp.hstack([tfidf_vec, sp.csr_matrix(numeric)])

        action_idx = self.clf_action.predict(X)[0]
        mtype_idx  = self.clf_mtype.predict(X)[0]

        action_proba = self.clf_action.predict_proba(X)[0]
        confidence   = float(round(max(action_proba), 3))

        action = self.le_action.inverse_transform([action_idx])[0]
        mtype  = self.le_mtype.inverse_transform([mtype_idx])[0]

        # Build human-readable reason
        text_lower = text.lower()
        if action == "mute" and mtype == "scam":
            reason = "ML model detected scam/phishing indicators in message content."
        elif action == "notify" and mtype == "urgent":
            reason = "ML model identified urgent time-sensitive content requiring immediate attention."
        elif action == "mute" and mtype in ("promotion", "spam"):
            reason = "ML model classified this as unwanted promotional or repetitive content."
        elif action == "notify":
            reason = "ML model determined this message requires prompt user attention."
        elif action == "digest":
            reason = "ML model classified this as informational content suitable for batching."
        else:
            reason = "ML model routing decision based on learned dataset patterns."

        return {
            "action"      : action,
            "message_type": mtype,
            "reason"      : reason,
            "confidence"  : confidence,
        }
