import os
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

logger = logging.getLogger("FridayMemory")

BASE_DIR = Path(__file__).resolve().parent
MEMORY_FILE = BASE_DIR / "memory_store.json"

# Common city/region to IANA timezone mapping
TIMEZONE_ALIASES = {
    "delhi": "Asia/Kolkata",
    "india": "Asia/Kolkata",
    "ist": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "kolkata": "Asia/Kolkata",
    "bangalore": "Asia/Kolkata",
    "dubai": "Asia/Dubai",
    "uae": "Asia/Dubai",
    "london": "Europe/London",
    "uk": "Europe/London",
    "gmt": "GMT",
    "utc": "UTC",
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "est": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "california": "America/Los_Angeles",
    "pst": "America/Los_Angeles",
    "tokyo": "Asia/Tokyo",
    "japan": "Asia/Tokyo",
    "singapore": "Asia/Singapore",
    "sydney": "Australia/Sydney",
    "toronto": "America/Toronto",
    "canada": "America/Toronto",
    "berlin": "Europe/Berlin",
    "germany": "Europe/Berlin",
    "paris": "Europe/Paris",
    "france": "Europe/Paris",
}

class FridayMemoryEngine:
    """
    Cognitive Memory & Self-Learning Engine inspired by OpenJarvis.
    Maintains persistent memory, user preferences, dynamic timezones, and self-learned facts.
    """
    def __init__(self):
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load memory store: {e}")
        return {
            "users": {},
            "chats": {},
            "global_learned_facts": {},
        }

    def _save(self):
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save memory store: {e}")

    def get_chat_prefs(self, chat_id: int) -> Dict[str, Any]:
        cid = str(chat_id)
        if cid not in self.data["chats"]:
            self.data["chats"][cid] = {
                "timezone": "Asia/Kolkata",
                "language": "auto",
                "custom_name": None,
                "learned_facts": {},
            }
        return self.data["chats"][cid]

    def set_timezone(self, chat_id: int, tz_input: str) -> Optional[str]:
        """Resolves and sets timezone for a chat."""
        cleaned = tz_input.strip().lower()
        target_tz = TIMEZONE_ALIASES.get(cleaned, tz_input.strip())
        try:
            # Validate timezone
            ZoneInfo(target_tz)
            prefs = self.get_chat_prefs(chat_id)
            prefs["timezone"] = target_tz
            self._save()
            return target_tz
        except Exception:
            return None

    def get_timezone(self, chat_id: int) -> str:
        return self.get_chat_prefs(chat_id).get("timezone", "Asia/Kolkata")

    def set_language(self, chat_id: int, language: str):
        prefs = self.get_chat_prefs(chat_id)
        prefs["language"] = language.strip()
        self._save()

    def get_language(self, chat_id: int) -> str:
        return self.get_chat_prefs(chat_id).get("language", "auto")

    def set_voice(self, chat_id: int, voice_id: str):
        """Persistently saves voice model selection per chat."""
        prefs = self.get_chat_prefs(chat_id)
        prefs["voice"] = voice_id
        self._save()

    def get_voice(self, chat_id: int, default_voice: str) -> str:
        """Retrieves persistent voice model selection."""
        return self.get_chat_prefs(chat_id).get("voice", default_voice)

    def learn_fact(self, chat_id: int, key: str, value: str):
        """Stores a learned fact for this chat / user."""
        prefs = self.get_chat_prefs(chat_id)
        prefs.setdefault("learned_facts", {})[key.strip()] = value.strip()
        self._save()

    def get_current_time_str(self, chat_id: int) -> str:
        """Returns the real-time accurate clock formatted in user's chosen timezone."""
        tz_name = self.get_timezone(chat_id)
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Asia/Kolkata")
            tz_name = "Asia/Kolkata"

        now = datetime.now(tz)
        return now.strftime("%A, %d %B %Y, %I:%M:%S %p") + f" ({tz_name})"

    def build_cognitive_context(self, chat_id: int) -> str:
        """
        Builds the live cognitive context (real-time clock, user timezone, language, learned memory)
        to inject into Friday's reasoning engine.
        """
        prefs = self.get_chat_prefs(chat_id)
        current_time = self.get_current_time_str(chat_id)
        tz = prefs.get("timezone", "Asia/Kolkata")
        lang = prefs.get("language", "auto")
        learned = prefs.get("learned_facts", {})

        context_lines = [
            f"[LIVE SYSTEM CLOCK & USER CONTEXT]",
            f"- Current Real-Time Clock: {current_time}",
            f"- Configured User Timezone: {tz}",
            f"- Preferred Language: {lang}",
        ]

        if learned:
            context_lines.append("- Persistent Learned Facts About This User/Chat:")
            for k, v in learned.items():
                context_lines.append(f"  * {k}: {v}")

        global_facts = self.data.get("global_learned_facts", {})
        if global_facts:
            context_lines.append("- Global Knowledge Updates:")
            for k, v in global_facts.items():
                context_lines.append(f"  * {k}: {v}")

        return "\n".join(context_lines)

# Singleton instance
memory_engine = FridayMemoryEngine()
