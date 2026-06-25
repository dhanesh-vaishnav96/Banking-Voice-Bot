"""
Speech-to-Text Service for Hindi Voice Collection Bot.

Primary: Browser Web Speech API (handled on frontend, no backend needed)
Optional: Faster-Whisper (local model, Hindi transcription)

This module provides the backend Faster-Whisper endpoint for future use.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy-loaded Whisper model
_whisper_model = None


def _get_whisper_model():
    """Lazy-load Faster-Whisper model on first use."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    try:
        from faster_whisper import WhisperModel  # type: ignore
        from backend.config import WHISPER_MODEL_SIZE

        logger.info(f"Loading Faster-Whisper model: {WHISPER_MODEL_SIZE}")
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",
        )
        logger.info("Faster-Whisper model loaded successfully.")
        return _whisper_model

    except ImportError:
        logger.warning(
            "faster-whisper is not installed. "
            "Install it with: pip install faster-whisper"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        return None


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "webm",
    language: str = "hi",
) -> Tuple[str, float]:
    """
    Transcribe audio bytes to text using Faster-Whisper.

    Args:
        audio_bytes: Raw audio data
        audio_format: Format hint (webm, wav, mp3, ogg)
        language: Language code ("hi" for Hindi)

    Returns:
        (transcript_text, confidence_score)
    """
    import tempfile
    import os

    model = _get_whisper_model()
    if model is None:
        raise RuntimeError(
            "Faster-Whisper model is not available. "
            "Install it or use the browser Web Speech API instead."
        )

    # Write audio bytes to a temp file for Whisper
    with tempfile.NamedTemporaryFile(
        suffix=f".{audio_format}", delete=False
    ) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            vad_filter=True,
        )

        text_parts = []
        total_confidence = 0.0
        segment_count = 0

        for seg in segments:
            text_parts.append(seg.text.strip())
            if hasattr(seg, "avg_logprob"):
                # Convert log-prob to approximate confidence [0,1]
                import math
                confidence = min(1.0, max(0.0, math.exp(seg.avg_logprob)))
                total_confidence += confidence
                segment_count += 1

        transcript = " ".join(text_parts).strip()
        avg_confidence = (
            total_confidence / segment_count if segment_count > 0 else 0.8
        )

        logger.info(f"Transcribed: '{transcript}' (confidence: {avg_confidence:.2f})")
        return transcript, avg_confidence

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def is_whisper_available() -> bool:
    """Check if Faster-Whisper is installed and loadable."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
