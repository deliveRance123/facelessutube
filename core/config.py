import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env
load_dotenv(BASE_DIR / ".env")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")

# Server Settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# YouTube Client Secret
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
TOKEN_PICKLE_FILE = BASE_DIR / "storage" / "youtube_token.pickle"

# Personal Avatar & Voice Assets
FACE_IMAGE_PATH = BASE_DIR / "face_clean.png" if (BASE_DIR / "face_clean.png").exists() else (BASE_DIR / "face.png")
VOICE_SAMPLE_PATH = BASE_DIR / "voice.wav"

# Directories
STORAGE_DIR = BASE_DIR / "storage"
VIDEOS_DIR = STORAGE_DIR / "videos"
TEMP_DIR = STORAGE_DIR / "temp"
MUSIC_DIR = STORAGE_DIR / "music"
STATIC_DIR = BASE_DIR / "web" / "static"
TEMPLATES_DIR = BASE_DIR / "web" / "templates"

for d in [STORAGE_DIR, VIDEOS_DIR, TEMP_DIR, MUSIC_DIR, STATIC_DIR, TEMPLATES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = STORAGE_DIR / "settings.json"

def get_channel_settings() -> dict:
    """Reads persistent user channel settings from storage/settings.json or returns defaults."""
    default_settings = {
        "default_voice": os.getenv("DEFAULT_VOICE", "en-US-ChristopherNeural"),
        "recording_max_seconds": 60,
    }
    if SETTINGS_FILE.exists():
        try:
            import json
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    default_settings.update(data)
        except Exception:
            pass
    return default_settings

def save_channel_settings(settings: dict) -> None:
    """Saves persistent settings to storage/settings.json."""
    import json
    current = get_channel_settings()
    current.update(settings)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

def get_default_voice() -> str:
    """Returns the dynamically configured default voice."""
    return get_channel_settings().get("default_voice", "en-US-ChristopherNeural")

def set_default_voice(voice_id: str) -> str:
    """Persists the default voice selection to settings."""
    save_channel_settings({"default_voice": voice_id})
    return voice_id

# Dynamic alias
DEFAULT_VOICE = get_default_voice()

# Niche Theme
NICHE = "Dark Psychology & Stoic Life Laws"
