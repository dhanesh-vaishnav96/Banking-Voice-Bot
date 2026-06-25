"""
Text-to-Speech Service for Hindi Voice Collection Bot — V3 (ElevenLabs + Fallback)

Provider priority:
  1. ElevenLabs (if TTS_PROVIDER=elevenlabs and API key set)
  2. edge-tts (fallback, or if TTS_PROVIDER=edge_tts)

Human Voice Settings (ElevenLabs):
  model:           eleven_multilingual_v2  — best Hindi/Hinglish quality
  stability:       0.45  — slightly lower = more natural variation, less robotic
  similarity_boost: 0.80  — stays close to voice character
  style:           0.35  — adds some expressive style without overdoing it
  use_speaker_boost: True — maximizes voice clarity over TTS artifacts

Usage:
    audio_path = await synthesize(text, audio_dir=AUDIO_DIR)
"""

import asyncio
import uuid
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# ElevenLabs optimized settings for human-like Hindi collection agent voice
# ─────────────────────────────────────────────────────────────────────────────
_ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.50,         # Balanced: prevents robotic tone but maintains clear diction
    "similarity_boost": 0.75,  # Natural blend of Charlie's voice and Hindi phonetics
    "style": 0.20,             # Reduced style: prevents overly emotional/dramatic pauses
    "use_speaker_boost": True, # Required for maximum clarity over telephone/web speakers
}

_ELEVENLABS_MODEL = "eleven_multilingual_v2"  # Best for Hindi/Hinglish


# ─────────────────────────────────────────────────────────────────────────────
# edge-tts (Microsoft Neural — free fallback)
# ─────────────────────────────────────────────────────────────────────────────

async def synthesize_edge_tts(text: str, voice: str, output_path: Path) -> Path:
    """Generate speech using edge-tts (Microsoft Neural TTS). Free, no API key."""
    try:
        import edge_tts  # type: ignore
    except ImportError:
        raise RuntimeError("edge-tts is not installed. Run: pip install edge-tts")

    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(str(output_path))
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# ElevenLabs
# ─────────────────────────────────────────────────────────────────────────────

async def synthesize_elevenlabs(
    text: str,
    voice_id: str,
    api_key: str,
    output_path: Path,
) -> Path:
    """
    Generate speech using ElevenLabs API with optimized Hindi voice settings.

    Model: eleven_multilingual_v2
    Settings tuned for natural Hindi collection agent voice.
    """
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx is not installed. Run: pip install httpx")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": _ELEVENLABS_MODEL,
        "voice_settings": _ELEVENLABS_VOICE_SETTINGS,
    }

    logger.info(
        f"ElevenLabs TTS | voice_id={voice_id[:8]}... | "
        f"model={_ELEVENLABS_MODEL} | chars={len(text)}"
    )
    t_start = time.time()

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs API error {response.status_code}: {response.text[:200]}"
            )
        output_path.write_bytes(response.content)

    elapsed = int((time.time() - t_start) * 1000)
    logger.info(
        f"ElevenLabs TTS complete | {elapsed}ms | saved: {output_path.name}"
    )
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Main synthesize function — provider selection + fallback
# ─────────────────────────────────────────────────────────────────────────────

async def synthesize(
    text: str,
    audio_dir: Path,
    voice: Optional[str] = None,
    provider: Optional[str] = None,
) -> Path:
    """
    High-level TTS: selects ElevenLabs or edge-tts based on config.
    Falls back to edge-tts automatically if ElevenLabs fails.

    Returns: Path to generated .mp3 file
    """
    from backend.config import (
        TTS_PROVIDER,
        EDGE_TTS_DEFAULT_VOICE,
        ELEVENLABS_API_KEY,
        ELEVENLABS_VOICE_ID,
    )

    selected_provider = provider or TTS_PROVIDER
    filename = f"response_{uuid.uuid4().hex[:8]}.mp3"
    output_path = audio_dir / filename

    # ── Try ElevenLabs first ──────────────────────────────────────────────────
    if selected_provider == "elevenlabs" and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
        try:
            voice_id = voice or ELEVENLABS_VOICE_ID
            await synthesize_elevenlabs(text, voice_id, ELEVENLABS_API_KEY, output_path)
            logger.info(f"TTS provider=elevenlabs | file={output_path.name}")
            return output_path
        except Exception as e:
            err_str = str(e)
            # Surface clear diagnostics for common ElevenLabs failures
            if "quota_exceeded" in err_str or "0 credits" in err_str:
                logger.error(
                    "ElevenLabs QUOTA EXHAUSTED — 0 credits remaining. "
                    "Options: (1) Wait for monthly reset, (2) Upgrade plan, "
                    "(3) Use new API key. Falling back to Edge TTS."
                )
            elif "401" in err_str or "invalid_api_key" in err_str:
                logger.error(
                    f"ElevenLabs INVALID API KEY — check ELEVENLABS_API_KEY in .env. "
                    f"Falling back to Edge TTS. Detail: {err_str[:200]}"
                )
            elif "402" in err_str:
                logger.error(
                    f"ElevenLabs PAYMENT REQUIRED (402) — subscription issue. "
                    f"Falling back to Edge TTS. Detail: {err_str[:200]}"
                )
            else:
                logger.warning(
                    f"ElevenLabs TTS failed ({err_str[:200]}). Falling back to Edge TTS."
                )
            # Fall through to edge-tts

    # ── Fallback: edge-tts ────────────────────────────────────────────────────
    selected_voice = voice or EDGE_TTS_DEFAULT_VOICE
    logger.info(f"TTS provider=edge_tts | voice={selected_voice} | chars={len(text)}")
    await synthesize_edge_tts(text, selected_voice, output_path)
    logger.info(f"Audio saved: {output_path.name}")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Voice catalogue
# ─────────────────────────────────────────────────────────────────────────────

def get_available_voices() -> list[dict]:
    """Return list of available voices across providers."""
    from backend.config import ELEVENLABS_VOICE_ID, TTS_PROVIDER
    voices = [
        {
            "provider": "edge_tts",
            "voice_id": "hi-IN-SwaraNeural",
            "name": "Swara (Female, edge-tts)",
            "language": "hi-IN",
            "gender": "Female",
        },
        {
            "provider": "edge_tts",
            "voice_id": "hi-IN-MadhurNeural",
            "name": "Madhur (Male, edge-tts)",
            "language": "hi-IN",
            "gender": "Male",
        },
    ]
    if ELEVENLABS_VOICE_ID:
        voices.insert(0, {
            "provider": "elevenlabs",
            "voice_id": ELEVENLABS_VOICE_ID,
            "name": "ElevenLabs Hindi Voice (active)",
            "language": "hi-IN",
            "gender": "Custom",
            "active": TTS_PROVIDER == "elevenlabs",
        })
    return voices
