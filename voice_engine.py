import re
import os
import uuid
import asyncio
import requests
import io
from pathlib import Path
from config import VOICE_NAME, TEMP_AUDIO_DIR, CARTESIA_API_KEY, CARTESIA_VOICE_ID

# Persistent HTTP Session with keep-alive connection pooling for lowest possible latency (< 0.4s)
_cartesia_session = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
_cartesia_session.mount("https://", _adapter)

def prewarm_cartesia():
    """Silently pre-establishes TLS handshake so the very first voice note responds in milliseconds."""
    try:
        _cartesia_session.head("https://api.cartesia.ai", timeout=3)
    except Exception:
        pass

import threading
threading.Thread(target=prewarm_cartesia, daemon=True).start()

def clean_text_for_speech(text: str) -> str:
    """
    Filters and refines text into natural, human-friendly conversational speech.
    Removes robotic markers, formatting, markdown, and emojis so Cartesia sounds 100% human.
    """
    # Remove code snippets and blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`.*?`", "", text)
    # Remove markdown links [title](url) -> title
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove asterisks, hashtags, underscores, tildes, backticks, carets, angles
    text = re.sub(r"[\*_~#>`^\\/\[\]{}|]", " ", text)
    # Remove emojis and strange symbols so TTS doesn't stumble or read emoji descriptions (preserves all Indic scripts \u0900-\u0D7F)
    text = re.sub(r"[^\w\s\u0900-\u0D7F.,!?'-]", " ", text)
    # Clean up repetitive exclamation or question marks into natural pauses
    text = re.sub(r"!+", "!", text)
    text = re.sub(r"\?+", "?", text)
    text = re.sub(r"\.+", ".", text)
    # Ensure natural comma pauses for human breathing cadence
    text = re.sub(r",+", ",", text)
    # Normalize multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def text_to_speech_bytes(text: str, voice: str = None) -> bytes:
    """
    Direct in-memory speech synthesis via Cartesia AI.
    Bypasses disk I/O entirely for sub-second delivery.
    """
    spoken_text = clean_text_for_speech(text)
    if not spoken_text:
        spoken_text = "जी, मैंने सुन लिया।"

    loop = asyncio.get_event_loop()

    # Determine language
    is_hindi = any("\u0900" <= c <= "\u0D7F" for c in spoken_text) or any(
        w in spoken_text.lower() for w in ["hai", "kya", "aap", "main", "hum", "kaise", "thik", "batao", "namaste", "nahi", "accha", "ki", "da", "ni"]
    )
    lang_code = "hi" if is_hindi else "en"

    if CARTESIA_API_KEY:
        target_voice_id = voice if (voice and "-" in voice and len(voice) > 20) else (CARTESIA_VOICE_ID or "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc")

        def _call_cartesia():
            headers = {
                "X-API-Key": CARTESIA_API_KEY,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json"
            }
            # 24kHz sample rate reduces generation time and payload size by ~45% while preserving pristine voice quality
            payload = {
                "model_id": "sonic-latest",
                "transcript": spoken_text,
                "voice": {
                    "mode": "id",
                    "id": target_voice_id
                },
                "language": lang_code,
                "output_format": {
                    "container": "mp3",
                    "encoding": "mp3",
                    "sample_rate": 24000
                }
            }
            try:
                resp = _cartesia_session.post(
                    "https://api.cartesia.ai/tts/bytes",
                    headers=headers,
                    json=payload,
                    timeout=8
                )
                if resp.status_code == 200 and resp.content:
                    return resp.content
                else:
                    print(f"[VoiceEngine] Cartesia error: {resp.status_code} {resp.text}")
                    return None
            except Exception as e:
                print(f"[VoiceEngine] Cartesia session error: {e}")
                return None

        audio_bytes = await loop.run_in_executor(None, _call_cartesia)
        if audio_bytes:
            return audio_bytes

    # Fallback: synthesize to temp file and read bytes
    filename = f"fallback_{uuid.uuid4().hex[:8]}.mp3"
    fallback_path = str(TEMP_AUDIO_DIR / filename)
    try:
        await text_to_speech(text, output_path=fallback_path, voice=voice)
        if os.path.exists(fallback_path):
            with open(fallback_path, "rb") as f:
                content = f.read()
            try:
                os.remove(fallback_path)
            except Exception:
                pass
            return content
    except Exception as e:
        print(f"[VoiceEngine] Fallback synthesis failed: {e}")

    return None

async def text_to_speech(text: str, output_path: str = None, voice: str = None) -> str:
    """
    Converts text to natural human speech with native Hindi accent.
    Priority 1: Cartesia AI (Native Hindi voices: Siya / Sagar / Neha with "language": "hi")
    Priority 2: Microsoft edge-tts
    Priority 3: Google gTTS fallback
    """
    if not output_path:
        filename = f"reply_{uuid.uuid4().hex[:8]}.mp3"
        output_path = str(TEMP_AUDIO_DIR / filename)

    spoken_text = clean_text_for_speech(text)
    if not spoken_text:
        spoken_text = "I received your message."

    loop = asyncio.get_event_loop()

    # Determine if text is predominantly Hindi or English
    is_hindi = any("\u0900" <= c <= "\u0D7F" for c in spoken_text) or any(
        w in spoken_text.lower() for w in ["hai", "kya", "aap", "main", "hum", "kaise", "thik", "batao", "namaste", "nahi", "accha"]
    )
    lang_code = "hi" if is_hindi else "en"

    # 1. Cartesia AI (Jacqueline / Native voices)
    if CARTESIA_API_KEY:
        target_voice_id = voice if (voice and "-" in voice and len(voice) > 20) else (CARTESIA_VOICE_ID or "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc")

        def _call_cartesia():
            headers = {
                "X-API-Key": CARTESIA_API_KEY,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json"
            }
            # Cartesia sonic-latest handles multilingual & English natively at ultra-low latency
            payload = {
                "model_id": "sonic-latest",
                "transcript": spoken_text,
                "voice": {
                    "mode": "id",
                    "id": target_voice_id
                },
                "language": lang_code,
                "output_format": {
                    "container": "mp3",
                    "encoding": "mp3",
                    "sample_rate": 24000
                }
            }
            resp = _cartesia_session.post(
                "https://api.cartesia.ai/tts/bytes",
                headers=headers,
                json=payload,
                timeout=8
            )

            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return True
            else:
                print(f"[VoiceEngine] Cartesia error: {resp.status_code} {resp.text}")
                return False

        try:
            success = await loop.run_in_executor(None, _call_cartesia)
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"[VoiceEngine] Synthesized with Cartesia AI ({target_voice_id}, lang={lang_code}): {output_path}")
                return output_path
        except Exception as e:
            print(f"[VoiceEngine] Cartesia request exception: {e}. Falling back to edge-tts...")

    # 2. edge-tts fallback
    selected_voice = voice or VOICE_NAME
    try:
        import edge_tts
        communicate = edge_tts.Communicate(spoken_text, voice=selected_voice)
        await communicate.save(output_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"[VoiceEngine] Synthesized with edge-tts ({selected_voice})")
            return output_path
    except Exception as e:
        print(f"[VoiceEngine] edge-tts error: {e}. Trying fallback gTTS...")

    # 3. Fallback to gTTS
    try:
        from gtts import gTTS
        def _generate_gtts():
            tts = gTTS(text=spoken_text, lang="hi" if is_hindi else "en")
            tts.save(output_path)
        await loop.run_in_executor(None, _generate_gtts)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except Exception as fallback_error:
        print(f"[VoiceEngine] gTTS fallback failed: {fallback_error}")
        raise RuntimeError(f"Text-to-Speech generation failed: {fallback_error}")

    return output_path
