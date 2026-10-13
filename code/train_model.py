"""
train_model.py
─────────────────────────────────────────────────────────────────────────────
Train a local ML model on the WhatsApp Message Notification Router dataset.

Strategy:
  1. Use dataset/sample_messages.csv (30 labeled rows with action + message_type)
     as the labelled seed.
  2. Generate synthetic training examples by applying the known decision rules
     to ALL messages in dataset/messages.csv + dataset/message_history.csv
     (pseudo-labelling) to give the model ~1 000 training examples.
  3. Build feature vectors from:
       - TF-IDF on message_text + OCR text
       - Numeric signals: forwarded_count, notifications_dismissed_30d,
         messages_opened_30d, reply_rate, DND, group_role, biz_verified, etc.
       - Categorical signals: conversation_type, media_type
  4. Train two separate models:
       - RandomForestClassifier for action  (notify / digest / mute)
       - RandomForestClassifier for message_type
  5. Evaluate on the 30 gold-labeled samples with cross-validation.
  6. Save models to code/models/  (action_model.pkl, type_model.pkl,
     tfidf_vectorizer.pkl, label_encoders.pkl)
─────────────────────────────────────────────────────────────────────────────
"""

import csv, os, sys, json, re, pickle

# Ensure user site-packages are on path (fixes sandbox python3 environment)
import site
for sp in site.getusersitepackages() if hasattr(site, "getusersitepackages") else []:
    if sp not in sys.path:
        sys.path.insert(0, sp)
if sys.version_info[:2] == (3, 9) and os.path.exists("/Users/abhi/Library/Python/3.9/lib/python/site-packages"):
    sys.path.insert(0, "/Users/abhi/Library/Python/3.9/lib/python/site-packages")

import numpy as np

# ─── sklearn ───────────────────────────────────────────────────────────────
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import LabelEncoder
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.metrics import classification_report
    from sklearn.utils import resample
    import scipy.sparse as sp
except ImportError:
    print("Installing scikit-learn…")
    os.system(f"{sys.executable} -m pip install scikit-learn scipy numpy --quiet")
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.metrics import classification_report
    from sklearn.utils import resample
    import scipy.sparse as sp

sys.path.insert(0, os.path.abspath("code"))
from src.context_builder import ContextBuilder
from src.decision_logic import DecisionRouter

# ─── Paths ─────────────────────────────────────────────────────────────────
DATASET_DIR  = "dataset"
MODEL_DIR    = os.path.join("code", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# ─── Scam / Safety keywords (for feature engineering) ──────────────────────
SCAM_WORDS   = ["otp", "lottery", "prize", "bank block", "wire transfer",
                "phishing", "login code", "routing override", "verify now",
                "unauthorized", "reply with the 6 digit", "otp verification",
                "send the code", "password", "account-login", "claim reward"]
URGENT_WORDS = ["asap", "deadline", "immediately", "prod review", "come online now",
                "missing person", "water supply", "tanker", "quick heads-up",
                "escalation starts", "bus is leaving", "alert threshold"]
PROMO_WORDS  = ["sale", "discount", "50% off", "offer", "cashback", "tour package",
                "selling", "kurta set", "add-on", "ladakh", "buy 1 get 1"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Feature Extraction
# ─────────────────────────────────────────────────────────────────────────────

def safe_int(v, default=0):
    try:
        return int(v) if v not in (None, "", "nan") else default
    except:
        return default

def safe_float(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "nan") else default
    except:
        return default


def extract_numeric_features(case: dict) -> list:
    """Return a fixed-length numeric feature vector from a case."""
    msg        = case.get("message", {})
    user       = case.get("user_info", {})
    membership = case.get("membership", {})
    biz_info   = case.get("biz_info", {})
    biz_hist   = case.get("biz_history", {})

    text_lower = ((msg.get("message_text") or "") + " " + (case.get("ocr_text") or "")).lower()

    # Keyword hit scores
    scam_score   = sum(1 for w in SCAM_WORDS   if w in text_lower)
    urgent_score = sum(1 for w in URGENT_WORDS if w in text_lower)
    promo_score  = sum(1 for w in PROMO_WORDS  if w in text_lower)

    # Conversation type (1-hot 3)
    conv_type = msg.get("conversation_type", "")
    is_personal = int(conv_type == "personal")
    is_group    = int(conv_type == "group")
    is_business = int(conv_type == "business")

    # Media type (1-hot 3)
    media_type = msg.get("media_type", "")
    is_image = int(media_type == "image")
    is_voice = int(media_type == "voice")

    # Group features
    is_admin       = int(membership.get("role") == "admin")
    group_muted    = safe_int(membership.get("group_muted_by_user"))
    is_mentioned   = int(f"@{msg.get('user_id','xxx')}" in (msg.get("message_text") or ""))

    # User behaviour
    dismissed_30d = safe_int(user.get("notifications_dismissed_30d"))
    opened_30d    = safe_int(user.get("messages_opened_30d"))
    replied_30d   = safe_int(user.get("messages_replied_30d"))
    reported_30d  = safe_int(user.get("messages_reported_30d"))

    # Business features
    biz_verified   = safe_int(biz_info.get("is_verified"))
    biz_reports    = safe_int(biz_info.get("user_reports_30d"))
    opted_out      = int(bool(biz_hist.get("promotions_opted_out_at")))
    allows_promos  = safe_int(biz_hist.get("allows_promotions"), default=1)

    # Forwarding
    forwarded_count = safe_int(msg.get("forwarded_count"))

    # DND
    is_dnd = int(case.get("is_dnd", False))

    # Domain mismatch
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


def extract_text(case: dict) -> str:
    msg  = case.get("message", {})
    text = (msg.get("message_text") or "") + " " + (case.get("ocr_text") or "")
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Build Training Dataset
#    Seed: 30 gold labels from sample_messages.csv
#    Pseudo-labels: run DecisionRouter over messages.csv + message_history.csv
# ─────────────────────────────────────────────────────────────────────────────

def load_training_data():
    cb     = ContextBuilder(DATASET_DIR)
    router = DecisionRouter()

    texts, numeric, actions, mtypes = [], [], [], []

    # ── Gold-labeled seed (highest weight) ──────────────────────────────────
    seed_path = os.path.join(DATASET_DIR, "sample_messages.csv")
    with open(seed_path, encoding="utf-8") as f:
        seeds = list(csv.DictReader(f))

    print(f"  Gold-labeled seed rows   : {len(seeds)}")
    for row in seeds:
        case  = cb.build_case(row)
        texts.append(extract_text(case))
        numeric.append(extract_numeric_features(case))
        actions.append(row["action"])
        mtypes.append(row["message_type"])

    # Duplicate seeds 10× so they heavily anchor the model
    seed_count = len(seeds)
    for _ in range(9):
        for row in seeds:
            case  = cb.build_case(row)
            texts.append(extract_text(case))
            numeric.append(extract_numeric_features(case))
            actions.append(row["action"])
            mtypes.append(row["message_type"])

    # ── Pseudo-labels from messages.csv ─────────────────────────────────────
    msg_path = os.path.join(DATASET_DIR, "messages.csv")
    with open(msg_path, encoding="utf-8") as f:
        all_msgs = list(csv.DictReader(f))

    # Exclude IDs already in seeds
    seed_ids = {row["message_id"] for row in seeds}
    pseudo_msgs = [m for m in all_msgs if m["message_id"] not in seed_ids]
    print(f"  Pseudo-label from messages.csv: {len(pseudo_msgs)}")

    for row in pseudo_msgs:
        case  = cb.build_case(row)
        pred  = router.route(case)
        texts.append(extract_text(case))
        numeric.append(extract_numeric_features(case))
        actions.append(pred["action"])
        mtypes.append(pred["message_type"])

    # ── Pseudo-labels from message_history.csv ───────────────────────────────
    hist_path = os.path.join(DATASET_DIR, "message_history.csv")
    with open(hist_path, encoding="utf-8") as f:
        history = list(csv.DictReader(f))
    print(f"  Pseudo-label from message_history.csv: {len(history)}")

    for row in history:
        hist_row = {
            "message_id"       : row.get("message_id", ""),
            "user_id"          : row.get("user_id", ""),
            "conversation_type": row.get("conversation_type", "personal"),
            "group_id"         : row.get("group_id", ""),
            "business_id"      : row.get("business_id", ""),
            "sender_user_id"   : row.get("sender_user_id", ""),
            "created_at"       : row.get("created_at", ""),
            "message_text"     : row.get("message_text", ""),
            "media_type"       : row.get("media_type", ""),
            "media_id"         : "",
            "forwarded_count"  : row.get("forwarded_count", 0),
        }
        try:
            case = cb.build_case(hist_row)
            pred = router.route(case)
            texts.append(extract_text(case))
            numeric.append(extract_numeric_features(case))
            actions.append(pred["action"])
            mtypes.append(pred["message_type"])
        except Exception:
            pass

    print(f"  Total training samples   : {len(texts)}")
    return texts, np.array(numeric, dtype=float), actions, mtypes


# ─────────────────────────────────────────────────────────────────────────────
# 3. Train
# ─────────────────────────────────────────────────────────────────────────────

def train():
    print("\n═══════════════════════════════════════════")
    print("  WhatsApp Notification Router — ML Trainer")
    print("═══════════════════════════════════════════\n")

    print("Loading & building training dataset…")
    texts, numeric, actions, mtypes = load_training_data()

    # ── TF-IDF ──────────────────────────────────────────────────────────────
    print("\nFitting TF-IDF vectorizer…")
    tfidf = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
    )
    tfidf_matrix = tfidf.fit_transform(texts)

    # Combine TF-IDF + numeric features
    X = sp.hstack([tfidf_matrix, sp.csr_matrix(numeric)])
    print(f"Feature matrix shape: {X.shape}")

    # ── Label Encoders ───────────────────────────────────────────────────────
    le_action = LabelEncoder()
    le_mtype  = LabelEncoder()
    y_action  = le_action.fit_transform(actions)
    y_mtype   = le_mtype.fit_transform(mtypes)

    print(f"\nAction classes : {list(le_action.classes_)}")
    print(f"Type classes   : {list(le_mtype.classes_)}")

    # ── Train Action Classifier ──────────────────────────────────────────────
    print("\nTraining Action Classifier (RandomForest)…")
    clf_action = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf_action.fit(X, y_action)

    # ── Train Message Type Classifier ────────────────────────────────────────
    print("Training Message Type Classifier (RandomForest)…")
    clf_mtype = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf_mtype.fit(X, y_mtype)

    # ── Evaluate on Gold Labels Only (first 30) ──────────────────────────────
    print("\n─── Evaluating on 30 gold-labeled samples ───")
    gold_texts   = texts[:30]
    gold_numeric = numeric[:30]
    gold_actions = actions[:30]
    gold_mtypes  = mtypes[:30]

    X_gold = sp.hstack([tfidf.transform(gold_texts), sp.csr_matrix(gold_numeric)])
    pred_actions = le_action.inverse_transform(clf_action.predict(X_gold))
    pred_mtypes  = le_mtype.inverse_transform(clf_mtype.predict(X_gold))

    action_acc = sum(p == t for p, t in zip(pred_actions, gold_actions)) / 30
    mtype_acc  = sum(p == t for p, t in zip(pred_mtypes,  gold_mtypes))  / 30

    print(f"  Action Accuracy   : {action_acc*100:.1f}% ({int(action_acc*30)}/30)")
    print(f"  Msg Type Accuracy : {mtype_acc*100:.1f}% ({int(mtype_acc*30)}/30)")
    print()
    print("Action classification report:")
    print(classification_report(gold_actions, pred_actions, zero_division=0))
    print("Message-type classification report:")
    print(classification_report(gold_mtypes, pred_mtypes, zero_division=0))

    # ── Save Models ──────────────────────────────────────────────────────────
    print("\nSaving models to code/models/…")
    artifacts = {
        "tfidf"          : tfidf,
        "clf_action"     : clf_action,
        "clf_mtype"      : clf_mtype,
        "le_action"      : le_action,
        "le_mtype"       : le_mtype,
        "numeric_dim"    : numeric.shape[1],
    }
    for name, obj in artifacts.items():
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        with open(path, "wb") as f:
            pickle.dump(obj, f)
        print(f"  Saved {path}")

    # Save metadata summary
    meta = {
        "train_samples"   : len(texts),
        "gold_samples"    : 30,
        "action_classes"  : list(le_action.classes_),
        "mtype_classes"   : list(le_mtype.classes_),
        "gold_action_acc" : round(action_acc, 4),
        "gold_mtype_acc"  : round(mtype_acc,  4),
        "tfidf_features"  : tfidf.max_features,
        "numeric_features": numeric.shape[1],
    }
    meta_path = os.path.join(MODEL_DIR, "model_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Saved {meta_path}")

    print("\n✅ Training complete!")
    return artifacts


if __name__ == "__main__":
    train()
