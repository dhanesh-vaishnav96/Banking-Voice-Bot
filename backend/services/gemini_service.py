"""
gemini_service.py — Gemini 2.5 Flash integration for response generation.

Architecture:
  - Sends customer context + conversation history + user message to Gemini.
  - Enforces structured JSON output: {response, intent, end_call, send_payment_link}.
  - Validates the response (Hindi text, length, no markdown/JSON/AI words).
  - Retries once if validation fails.
  - Raises GeminiUnavailableError on API failure so the caller can fallback.

Logging per request:
  - user_text, classifier_intent, gemini_intent, stage, llm_provider, response_time_ms
"""

import json
import re
import time
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional

from backend.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_SECONDS,
    GEMINI_MAX_RESPONSE_CHARS,
)
from backend.prompts.collection_agent import build_system_prompt, build_gemini_history

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SDK Initialisation (lazy, so import failure is non-fatal)
# ─────────────────────────────────────────────────────────────────────────────

_client = None
_sdk_available = False

try:
    from google import genai
    from google.genai import types as genai_types
    _sdk_available = True
except ImportError:
    logger.warning("google-genai SDK not installed. Run: pip install google-genai")


def _get_client():
    global _client
    if _client is None:
        if not _sdk_available:
            raise GeminiUnavailableError("google-genai SDK not installed")
        if not GEMINI_API_KEY:
            raise GeminiUnavailableError("GEMINI_API_KEY is not set in .env")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class GeminiUnavailableError(Exception):
    """Raised when Gemini is unreachable or misconfigured. Triggers fallback."""


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GeminiResult:
    response: str
    intent: str
    end_call: bool
    send_payment_link: bool
    response_time_ms: int
    llm_provider: str = "gemini"
    
    # Phase 2 Entity Extraction
    promised_date: Optional[str] = None
    promised_amount: Optional[float] = None
    callback_requested: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Response Validator
# ─────────────────────────────────────────────────────────────────────────────

# Words that should never appear in a TTS response
_BANNED_PATTERNS = [
    r"```",                     # code blocks
    r"#{1,6} ",                 # markdown headings
    r"\*{1,2}",                 # bold/italic
    r"\[.*?\]\(.*?\)",          # markdown links
    r'"response"\s*:',          # leaked JSON key
    r'"intent"\s*:',            # leaked JSON key
    r"end_call",                # leaked JSON key
    r"\bai\b", r"\bllm\b",      # AI mentions
    r"\bchatbot\b",
    r"\bassistant\b",
    r"\bprompt\b",
    r"\bsystem\b",
    r"\bmodel\b",
]
_BANNED_RE = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)

# Minimal Hindi character check — at least some Devanagari or common Hinglish words
_HINDI_WORDS = {"haan", "nahi", "aap", "main", "ji", "kya", "hai", "ka",
                "ki", "ko", "se", "aur", "namaste", "dhanyavaad", "bilkul",
                "kripaya", "rupaye", "payment", "bank", "link"}


def _is_valid_response(text: str) -> bool:
    """Return True if the response passes all validation checks."""
    if not text or not text.strip():
        return False
    if len(text) > GEMINI_MAX_RESPONSE_CHARS:
        return False
    if _BANNED_RE.search(text):
        return False
    # Check for at least one Hindi/Hinglish word or Devanagari character
    lower = text.lower()
    has_devanagari = bool(re.search(r"[\u0900-\u097f]", text))
    has_hinglish = any(w in lower for w in _HINDI_WORDS)
    if not (has_devanagari or has_hinglish):
        return False
    return True


def _clean_response(text: str) -> str:
    """Strip markdown artifacts and trim whitespace."""
    text = re.sub(r"```[a-z]*", "", text)
    text = re.sub(r"`", "", text)
    text = re.sub(r"#{1,6} ", "", text)
    text = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# JSON Parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_gemini_json(raw: str) -> dict:
    """
    Extract and parse the JSON object from Gemini's raw output.
    Handles cases where Gemini wraps JSON in code fences or outputs prose.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty Gemini response")

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Try full parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find the first { ... } block with greedy match
    match = re.search(r"\{[\s\S]*?\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Wider search — find largest JSON block
    match = re.search(r"\{[\s\S]+\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in Gemini output: {raw[:300]}")


def _extract_plain_response(raw: str) -> dict:
    """
    Gemini sometimes ignores the JSON format instruction and returns plain Hindi.
    In that case, wrap the text in the expected structure so the call doesn't fail.
    The intent and flags will be inferred by the route handler from the classifier hint.
    """
    cleaned = re.sub(r"```[a-z]*", "", raw).strip().rstrip("`").strip()
    return {
        "response": cleaned,
        "intent": "unclear",          # caller overrides with classifier hint
        "end_call": False,
        "send_payment_link": False,
        "promised_date": None,
        "promised_amount": None,
        "callback_requested": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core API Call
# ─────────────────────────────────────────────────────────────────────────────

async def _call_gemini(system_prompt: str, history: list, user_text: str) -> dict:
    """
    Make one async call to Gemini. Returns parsed JSON dict.
    Raises GeminiUnavailableError on failure.
    """
    client = _get_client()

    # Build contents: conversation history + current user turn
    contents = list(history)
    contents.append({
        "role": "user",
        "parts": [{"text": user_text}],
    })

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.4,
                        max_output_tokens=256,
                    ),
                )
            ),
            timeout=GEMINI_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise GeminiUnavailableError(f"Gemini API timed out after {GEMINI_TIMEOUT_SECONDS}s")
    except Exception as e:
        raise GeminiUnavailableError(f"Gemini API error: {e}")

    raw_text = response.text or ""
    if not raw_text.strip():
        raise GeminiUnavailableError("Gemini returned empty response")

    # Try structured JSON first; fall back to treating raw text as plain Hindi response
    try:
        return _parse_gemini_json(raw_text)
    except ValueError:
        logger.warning(f"Gemini returned plain text (no JSON). Wrapping as response. Raw: {raw_text[:80]}")
        return _extract_plain_response(raw_text)


# ─────────────────────────────────────────────────────────────────────────────
# Public Interface
# ─────────────────────────────────────────────────────────────────────────────

async def get_gemini_response(
    session,
    user_text: str,
    intent_hint: str,
) -> GeminiResult:
    """
    Get a structured response from Gemini 2.5 Flash.

    Args:
        session: ConversationSession (provides customer data + gemini_history)
        user_text: The user's transcribed speech
        intent_hint: Pre-classified intent from intent_classifier

    Returns:
        GeminiResult with validated Hindi response + metadata

    Raises:
        GeminiUnavailableError: If Gemini fails after retries
    """
    t_start = time.time()

    system_prompt = build_system_prompt(
        customer_name=session.customer_name,
        amount_due=session.amount_due,
        bank_name=session.bank_name,
        payment_link=session.payment_link,
        stage=session.stage,
        intent_hint=intent_hint,
    )
    history = build_gemini_history(session)

    parsed: Optional[dict] = None
    validated_response: Optional[str] = None

    # Try up to 2 times (first attempt + one regeneration if validation fails)
    for attempt in range(2):
        try:
            parsed = await _call_gemini(system_prompt, history, user_text)
        except GeminiUnavailableError:
            raise  # Let caller handle fallback

        raw_response = parsed.get("response", "").strip()
        cleaned = _clean_response(raw_response)

        if _is_valid_response(cleaned):
            validated_response = cleaned
            break
        else:
            logger.warning(
                f"Gemini response failed validation (attempt {attempt + 1}): "
                f"'{raw_response[:80]}'"
            )

    if validated_response is None or parsed is None:
        # If validation failed both attempts but we have a parsed dict, use it with a warning
        if parsed:
            raw_response = parsed.get("response", "").strip()
            if raw_response:
                validated_response = _clean_response(raw_response)
                logger.warning(f"Using unvalidated Gemini response after 2 attempts: '{raw_response[:60]}'")
            else:
                raise GeminiUnavailableError("Gemini response failed validation after 2 attempts")
        else:
            raise GeminiUnavailableError("Gemini response failed validation after 2 attempts")

    elapsed_ms = int((time.time() - t_start) * 1000)

    result = GeminiResult(
        response=validated_response,
        intent=parsed.get("intent", "unclear"),
        end_call=bool(parsed.get("end_call", False)),
        send_payment_link=bool(parsed.get("send_payment_link", False)),
        response_time_ms=elapsed_ms,
        llm_provider="gemini",
        promised_date=parsed.get("promised_date"),
        promised_amount=parsed.get("promised_amount"),
        callback_requested=bool(parsed.get("callback_requested", False))
    )

    logger.info(
        f"Gemini | user='{user_text[:40]}' | hint={intent_hint} | "
        f"intent={result.intent} | end_call={result.end_call} | "
        f"send_link={result.send_payment_link} | {elapsed_ms}ms"
    )

    return result

# ─────────────────────────────────────────────────────────────────────────────
# Post-Call Summary Generation
# ─────────────────────────────────────────────────────────────────────────────

async def generate_call_summary(session) -> dict:
    """
    Generate a structured JSON call summary using Gemini.
    Returns dictionary matching the CallSummary schema.
    """
    client = _get_client()
    
    # Format history into a single text block
    history_text = "\n".join([
        f"{msg['role'].upper()}: {msg['parts'][0]['text']}"
        for msg in build_gemini_history(session)
    ])
    
    summary_prompt = f"""
Analyze the following Hindi collection call transcript between an Executive and Customer.
The customer is {session.customer_name}. Amount due: {session.amount_due} for {session.bank_name}.

TRANSCRIPT:
{history_text}

Provide a structured JSON output exactly matching this schema, without any markdown formatting:
{{
  "call_summary": "<Short 2-3 sentence English summary of what happened>",
  "customer_intent": "<PAID|WILL_PAY|REFUSED|DISPUTE|WRONG_PERSON|CALLBACK_REQUESTED|BUSY>",
  "payment_commitment": {{
    "amount": <number or null>,
    "promised_date": "<ISO8601 date or simple text like 'tomorrow' or null>"
  }},
  "follow_up_required": <true or false>,
  "follow_up_reason": "<Short reason or null>",
  "call_outcome": "<SUCCESS|PENDING|FAILED>"
}}
"""
    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[{"role": "user", "parts": [{"text": summary_prompt}]}],
                    config=genai_types.GenerateContentConfig(temperature=0.2),
                )
            ),
            timeout=15.0,
        )
        return _parse_gemini_json(response.text or "")
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return {
            "call_summary": "Failed to generate summary.",
            "customer_intent": "UNKNOWN",
            "payment_commitment": {"amount": None, "promised_date": None},
            "follow_up_required": True,
            "follow_up_reason": str(e),
            "call_outcome": "PENDING"
        }
