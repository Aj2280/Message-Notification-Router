import csv
import json
import os
from datetime import datetime

class ContextBuilder:
    def __init__(self, dataset_dir="dataset"):
        self.dataset_dir = dataset_dir
        self.users = self._load_csv("users.csv", key_col="user_id")
        self.groups = self._load_csv("groups.csv", key_col="group_id")
        self.group_members = self._load_group_members()
        self.business_accounts = self._load_csv("business_accounts.csv", key_col="business_id")
        self.user_business_history = self._load_user_business_history()
        self.message_history = self._load_csv_list("message_history.csv")
        self.message_events = self._load_message_events()
        self.images = self._load_csv("images.csv", key_col="image_id")
        self.voice_notes = self._load_csv("voice_notes.csv", key_col="voice_note_id")
        self.image_ocr_cache = self._load_ocr_cache()

    def _load_csv(self, filename, key_col):
        path = os.path.join(self.dataset_dir, filename)
        result = {}
        if os.path.exists(path):
            with open(path, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    result[row[key_col]] = row
        return result

    def _load_csv_list(self, filename):
        path = os.path.join(self.dataset_dir, filename)
        result = []
        if os.path.exists(path):
            with open(path, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    result.append(row)
        return result

    def _load_group_members(self):
        path = os.path.join(self.dataset_dir, "group_members.csv")
        result = {}
        if os.path.exists(path):
            with open(path, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    key = (row["group_id"], row["user_id"])
                    result[key] = row
        return result

    def _load_user_business_history(self):
        path = os.path.join(self.dataset_dir, "user_business_history.csv")
        result = {}
        if os.path.exists(path):
            with open(path, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    key = (row["user_id"], row["business_id"])
                    result[key] = row
        return result

    def _load_message_events(self):
        path = os.path.join(self.dataset_dir, "message_events.csv")
        result = {}
        if os.path.exists(path):
            with open(path, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    key = (row["user_id"], row["message_id"])
                    result[key] = row
        return result

    def _load_ocr_cache(self):
        ocr_path = "scratch/image_ocr_cache.json"
        if os.path.exists(ocr_path):
            with open(ocr_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def is_in_dnd(self, dnd_window_str, created_at_str):
        if not dnd_window_str or "-" not in dnd_window_str or not created_at_str:
            return False
        try:
            time_part = created_at_str.split()[-1]
            msg_dt = datetime.strptime(time_part, "%H:%M")
            start_str, end_str = dnd_window_str.split("-")
            start_dt = datetime.strptime(start_str.strip(), "%H:%M")
            end_dt = datetime.strptime(end_str.strip(), "%H:%M")

            if start_dt <= end_dt:
                return start_dt <= msg_dt <= end_dt
            else:
                return msg_dt >= start_dt or msg_dt <= end_dt
        except Exception:
            return False

    def build_case(self, message_row):
        msg_id = message_row["message_id"]
        user_id = message_row["user_id"]
        conv_type = message_row["conversation_type"]
        group_id = message_row.get("group_id", "")
        business_id = message_row.get("business_id", "")
        sender_user_id = message_row.get("sender_user_id", "")
        created_at = message_row.get("created_at", "")
        media_type = message_row.get("media_type", "")
        media_id = message_row.get("media_id", "")

        user_info = self.users.get(user_id, {})
        dnd_window = user_info.get("do_not_disturb_window", "")
        is_dnd = self.is_in_dnd(dnd_window, created_at)

        group_info = {}
        membership = {}
        if conv_type == "group" and group_id:
            group_info = self.groups.get(group_id, {})
            membership = self.group_members.get((group_id, user_id), {})

        biz_info = {}
        biz_history = {}
        domain_mismatch = False
        if conv_type == "business" and business_id:
            biz_info = self.business_accounts.get(business_id, {})
            biz_history = self.user_business_history.get((user_id, business_id), {})
            off_dom = biz_info.get("official_domain", "").strip().lower()
            snd_dom = biz_info.get("domain_used_by_sender", "").strip().lower()
            is_verified = biz_info.get("verified") == "1"
            if off_dom and snd_dom and not is_verified:
                if off_dom not in snd_dom and snd_dom not in off_dom:
                    domain_mismatch = True

        ocr_text = ""
        if media_type == "image" and media_id:
            ocr_text = self.image_ocr_cache.get(media_id, "")

        user_history = []
        for h_msg in self.message_history:
            if h_msg["user_id"] == user_id:
                same_sender = sender_user_id and h_msg.get("sender_user_id") == sender_user_id
                same_group = group_id and h_msg.get("group_id") == group_id
                same_biz = business_id and h_msg.get("business_id") == business_id
                if same_sender or same_group or same_biz:
                    h_id = h_msg["message_id"]
                    event = self.message_events.get((user_id, h_id), {})
                    combined = dict(h_msg)
                    combined.update(event)
                    user_history.append(combined)

        return {
            "message": message_row,
            "user_info": user_info,
            "is_dnd": is_dnd,
            "group_info": group_info,
            "membership": membership,
            "biz_info": biz_info,
            "biz_history": biz_history,
            "domain_mismatch": domain_mismatch,
            "ocr_text": ocr_text,
            "user_history": user_history
        }
