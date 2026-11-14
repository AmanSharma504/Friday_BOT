import os
import time
import asyncio
from typing import Dict, List, Any
from config import GEMINI_API_KEY, GEMINI_MODEL

SYSTEM_INSTRUCTION = """You are Friday, a warm, intelligent, and authentic personal AI assistant and companion.
Rules for 100% human-like, ultra-fast conversations:
1. Speak naturally in the same language as the user (fluent everyday Hindi, English, or Hinglish).
2. Sound like a real, lively human friend talking on a call: warm, expressive, and thoughtful. Avoid robotic phrases, artificial formalities, or repetitive filler words.
3. When generating responses for voice: keep replies crisp and spoken-friendly (1 to 2 natural sentences). Use natural comma and period pauses so the voice synthesizer speaks with authentic human breathing cadence. Never include markdown, bullet points, asterisks, or emojis in spoken replies.
4. For text queries: deliver intelligent, clear, direct answers within seconds without unnecessary delay.
5. Remember ongoing context smoothly during the active conversation.
"""

MEMORY_TTL_SECONDS = 1200  # Exactly 20 minutes before conversation history auto-resets (server load protection)
MAX_TURNS_PER_CHAT = 8     # Sliding window to keep RAM footprint minimal and responses blazing fast

FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

class FridayAgent:
    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name or GEMINI_MODEL or "gemini-3.8-flash"
        # Stores text-only conversation history per chat_id
        self.history: Dict[int, List[Dict[str, str]]] = {}
        self.last_activity: Dict[int, float] = {}
        self._init_client()

    def _init_client(self):
        """Initializes the Gemini client with 10-minute timeout."""
        try:
            from google import genai
            from google.genai import types
            http_options = types.HttpOptions(api_version="v1alpha", timeout=15000)
            self.client = genai.Client(api_key=self.api_key, http_options=http_options)
            self.types = types
            print(f"[FridayAgent] Initialized high-speed engine with model: {self.model_name}")
        except Exception as e:
            print(f"[FridayAgent] Client initialization error: {e}")
            raise

    def _generate_with_fallback(self, contents: list) -> str:
        """Attempts generation with configured model, then tries fallback flash models."""
        models_to_try = [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]
        last_error = None

        for model in models_to_try:
            try:
                # Try with 0 thinking budget for ultra-fast generation
                try:
                    config = self.types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.7,
                        thinking_config=self.types.ThinkingConfig(thinking_budget=0),
                    )
                    res = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    )
                except Exception:
                    # Some models don't support thinking_config
                    config = self.types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.7,
                    )
                    res = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    )

                if res and res.text:
                    if model != self.model_name:
                        print(f"[FridayAgent] Successfully used fallback model: {model}")
                        self.model_name = model
                    return res.text.strip()
            except Exception as e:
                last_error = e
                print(f"[FridayAgent] Error with model {model}: {e}. Trying next fallback...")
                continue

        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    def get_history(self, chat_id: int) -> List[Dict[str, str]]:
        now = time.time()
        # Auto-expire conversation if inactive for more than 30 minutes
        if chat_id in self.last_activity:
            if now - self.last_activity[chat_id] > MEMORY_TTL_SECONDS:
                self.history[chat_id] = []
        
        self.last_activity[chat_id] = now
        if chat_id not in self.history:
            self.history[chat_id] = []
        return self.history[chat_id]

    def reset_chat(self, chat_id: int):
        """Clears memory for a specific chat."""
        if chat_id in self.history:
            self.history[chat_id] = []
            self.last_activity.pop(chat_id, None)
            return True
        return False

    def cleanup_expired_memory(self):
        """Removes expired chats to keep RAM footprint minimal on free servers."""
        now = time.time()
        expired = [cid for cid, t in self.last_activity.items() if now - t > MEMORY_TTL_SECONDS]
        for cid in expired:
            self.history.pop(cid, None)
            self.last_activity.pop(cid, None)

    def _build_contents(self, chat_id: int, new_parts: list) -> list:
        """
        Builds contents list with prior text history (sliding window) + current turn.
        Never stores binary audio in persistent memory.
        """
        history = self.get_history(chat_id)[-MAX_TURNS_PER_CHAT:]
        contents = []

        for turn in history:
            role = turn["role"]
            text = turn["text"]
            contents.append(
                self.types.Content(
                    role=role,
                    parts=[self.types.Part.from_text(text=text)]
                )
            )

        # Add current user turn
        user_parts = []
        for p in new_parts:
            if isinstance(p, str):
                user_parts.append(self.types.Part.from_text(text=p))
            else:
                user_parts.append(p)

        contents.append(
            self.types.Content(
                role="user",
                parts=user_parts
            )
        )
        return contents

    async def generate_text_reply(self, chat_id: int, user_message: str) -> str:
        """Processes text message in ~1 second."""
        loop = asyncio.get_event_loop()

        def _call():
            contents = self._build_contents(chat_id, [user_message])
            reply = self._generate_with_fallback(contents)
            reply = reply if reply else "मैं आपकी बात सुन रही हूँ।"
            # Append to history with sliding window
            hist = self.get_history(chat_id)
            hist.append({"role": "user", "text": user_message})
            hist.append({"role": "model", "text": reply})
            if len(hist) > MAX_TURNS_PER_CHAT * 2:
                self.history[chat_id] = hist[-MAX_TURNS_PER_CHAT:]
            return reply

        return await loop.run_in_executor(None, _call)

    async def generate_voice_reply(self, chat_id: int, audio_path: str, mime_type: str = "audio/ogg") -> str:
        """Processes voice note in ~4-5 seconds."""
        loop = asyncio.get_event_loop()

        def _call_audio():
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            audio_part = self.types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            prompt = (
                "The user sent a voice message. Listen closely, understand what they said and their emotion, "
                "and reply directly as Friday like a real human friend having a natural conversation. "
                "Speak in the user's language (Hindi, Hinglish, or English). "
                "Give a warm, natural 1-2 sentence spoken reply that sounds lively and authentic without robotic tone."
            )

            contents = self._build_contents(chat_id, [audio_part, prompt])
            reply = self._generate_with_fallback(contents)
            reply = reply if reply else "जी, मैंने सुन लिया।"
            hist = self.get_history(chat_id)
            hist.append({"role": "user", "text": "[User sent a voice note]"})
            hist.append({"role": "model", "text": reply})
            if len(hist) > MAX_TURNS_PER_CHAT * 2:
                self.history[chat_id] = hist[-MAX_TURNS_PER_CHAT:]
            return reply

        return await loop.run_in_executor(None, _call_audio)
