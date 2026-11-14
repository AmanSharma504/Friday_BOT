import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Gemini configuration (Ultra-fast & 100% active: gemini-3.1-flash-lite)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()

# Voice configuration
VOICE_NAME = os.getenv("VOICE_NAME", "en-US-AvaMultilingualNeural").strip()

# Cartesia AI Voice (Ultra-realistic real-time human voice)
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "").strip()
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc").strip()

# Bot Owner Telegram ID (optional, can also be claimed via /setowner)
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID", "").strip()

# Directory for storing temporary audio files
TEMP_AUDIO_DIR = BASE_DIR / "temp_audio"
TEMP_AUDIO_DIR.mkdir(exist_ok=True)

def validate_config() -> bool:
    """Check if all required configuration variables are set."""
    missing = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        missing.append("TELEGRAM_BOT_TOKEN (Missing or default in .env)")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        missing.append("GEMINI_API_KEY (Missing or default in .env)")
    
    if missing:
        print("\n" + "="*50)
        print("⚠️  CONFIGURATION WARNING:")
        for item in missing:
            print(f"  - {item}")
        print("Please edit the .env file with your valid tokens.")
        print("="*50 + "\n")
        return False
    return True
