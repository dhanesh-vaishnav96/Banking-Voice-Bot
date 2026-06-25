"""
Configuration management for Hindi Voice Collection Bot.
Reads from .env file or environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ─── TTS Configuration ─────────────────────────────────────────────────────────
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge_tts")  # edge_tts | elevenlabs

# edge-tts voices for Hindi
EDGE_TTS_VOICE_MALE = os.getenv("EDGE_TTS_VOICE_MALE", "hi-IN-MadhurNeural")
EDGE_TTS_VOICE_FEMALE = os.getenv("EDGE_TTS_VOICE_FEMALE", "hi-IN-SwaraNeural")
EDGE_TTS_DEFAULT_VOICE = os.getenv("EDGE_TTS_DEFAULT_VOICE", "hi-IN-MadhurNeural")

# ElevenLabs (optional)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

# ─── STT Configuration ─────────────────────────────────────────────────────────
STT_PROVIDER = os.getenv("STT_PROVIDER", "browser")  # browser | faster_whisper
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")  # tiny | small | medium

# ─── Audio Storage ─────────────────────────────────────────────────────────────
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

# ─── Server ────────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ─── Session ───────────────────────────────────────────────────────────────────
SESSION_TIMEOUT_SECONDS = int(os.getenv("SESSION_TIMEOUT_SECONDS", "3600"))

# ─── Gemini LLM Configuration ──────────────────────────────────────────────────
GEMINI_API_KEY            = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL              = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_ENABLED            = os.getenv("GEMINI_ENABLED", "true").lower() == "true"
GEMINI_FALLBACK_TO_RULES  = os.getenv("GEMINI_FALLBACK_TO_RULES", "true").lower() == "true"
GEMINI_TIMEOUT_SECONDS    = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "8.0"))
GEMINI_MAX_RESPONSE_CHARS = int(os.getenv("GEMINI_MAX_RESPONSE_CHARS", "300"))

# ─── Groq LLM Configuration ────────────────────────────────────────────────────
GROQ_API_KEY              = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL                = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_ENABLED              = os.getenv("GROQ_ENABLED", "true").lower() == "true"
GROQ_TIMEOUT_SECONDS      = float(os.getenv("GROQ_TIMEOUT_SECONDS", "8.0"))
GROQ_MAX_RESPONSE_CHARS   = int(os.getenv("GROQ_MAX_RESPONSE_CHARS", "300"))

# ─── Primary LLM Provider ──────────────────────────────────────────────────────
# Options: groq | gemini | rule_based
# Cascade: groq -> gemini -> rule_based  (automatic fallback)
LLM_PROVIDER              = os.getenv("LLM_PROVIDER", "groq")
