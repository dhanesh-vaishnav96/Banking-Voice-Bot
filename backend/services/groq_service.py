"""
groq_service.py — Groq LLM integration for response generation.

Architecture:
  - Sends customer context + conversation history + user message to Groq.
  - Enforces structured JSON output: {response, intent, end_call, send_payment_link,
    promised_date, promised_amount, callback_requested}.
  - Validates the response (Hindi text, length, no markdown/JSON/AI words).
  - Retries once if validation fails.
  - Raises GroqUnavailableError on API failure so the caller can cascade to Gemini.

Logging per request:
  - user_text, classifier_intent, groq_intent, stage, llm_provider, response_time_ms
"""

import json
import re
import time
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional

from backend.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
    GROQ_MAX_RESPONSE_CHARS,
)
from backend.prompts.collection_agent import build_system_prompt, build_gemini_history

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SDK Initialisation (lazy, so import failure is non-fatal)
# ─────────────────────────────────────────────────────────────────────────────

_client = None
_sdk_available = False

try:
    from groq import Groq
    _sdk_available = True
except ImportError:
    logger.warning("groq SDK not installed. Run: pip install groq")


def _get_client():
    global _client
    if _client is None:
        if not _sdk_available:
            raise GroqUnavailableError("groq SDK not installed")
        if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
            raise GroqUnavailableError("GROQ_API_KEY is not set in .env")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class GroqUnavailableError(Exception):
    """Raised when Groq is unreachable or misconfigured. Triggers cascade to Gemini."""


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass  (mirrors GeminiResult for drop-in compatibility)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GroqResult:
    response: str
    intent: str
    end_call: bool
    send_payment_link: bool
    response_time_ms: int
    llm_provider: str = "groq"

    # Phase 2 Entity Extraction
    promised_date: Optional[str] = None
    promised_amount: Optional[float] = None
    callback_requested: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Response Validator  (identical rules to gemini_service.py)
# ─────────────────────────────────────────────────────────────────────────────

_BANNED_PATTERNS = [
    r"```",
    r"#{1,6} ",
    r"\*{1,2}",
    r"\[.*?\]\(.*?\)",
    r'"response"\s*:',     # only ban if response text itself contains JSON keys
    r"\bai\b", r"\bllm\b",
    r"\bchatbot\b",
    r"\bassistant\b",
    r"\bprompt\b",
]
_BANNED_RE = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)

_HINDI_WORDS = {
    "haan", "nahi", "aap", "main", "ji", "kya", "hai", "ka",
    "ki", "ko", "se", "aur", "namaste", "dhanyavaad", "bilkul",
    "kripaya", "rupaye", "payment", "bank", "link",
}


def _is_valid_response(text: str) -> bool:
    if not text or not text.strip():
        return False
    if len(text) > GROQ_MAX_RESPONSE_CHARS:
        return False
    if _BANNED_RE.search(text):
        return False
    lower = text.lower()
    has_devanagari = bool(re.search(r"[\u0900-\u097f]", text))
    has_hinglish = any(w in lower for w in _HINDI_WORDS)
    if not (has_devanagari or has_hinglish):
        return False
    return True


def _clean_response(text: str) -> str:
    text = re.sub(r"```[a-z]*", "", text)
    text = re.sub(r"`", "", text)
    text = re.sub(r"#{1,6} ", "", text)
    text = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# JSON Parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    if not raw or not raw.strip():
        raise ValueError("Empty response")

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*?\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{[\s\S]+\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in Groq output: {raw[:300]}")


def _extract_plain_response(raw: str) -> dict:
    """
    Groq sometimes returns plain Hindi text instead of JSON.
    Wrap in expected structure so the call doesn't fail.
    """
    cleaned = re.sub(r"```[a-z]*", "", raw).strip().rstrip("`").strip()
    return {
        "response": cleaned,
        "intent": "unclear",
        "end_call": False,
        "send_payment_link": False,
        "promised_date": None,
        "promised_amount": None,
        "callback_requested": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Groq System Prompt Builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_groq_messages(system_prompt: str, history: list, user_text: str) -> list:
    """
    Convert conversation history (Gemini-format) to Groq/OpenAI chat format.
    Groq uses role=system, role=user, role=assistant.
    """
    messages = [{"role": "system", "content": system_prompt}]

    for turn in history:
        role = turn.get("role", "user")
        text = turn.get("parts", [{}])[0].get("text", "")
        if not text:
            continue
        # Gemini uses "model" for bot turns; OpenAI/Groq uses "assistant"
        groq_role = "assistant" if role == "model" else "user"
        messages.append({"role": groq_role, "content": text})

    messages.append({"role": "user", "content": user_text})
    return messages


# ─────────────────────────────────────────────────────────────────────────────
# Core API Call
# ─────────────────────────────────────────────────────────────────────────────

async def _call_groq(system_prompt: str, history: list, user_text: str) -> dict:
    """
    Make one async call to Groq. Returns parsed JSON dict.
    Raises GroqUnavailableError on failure.
    """
    client = _get_client()
    messages = _build_groq_messages(system_prompt, history, user_text)

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=256,
                )
            ),
            timeout=GROQ_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise GroqUnavailableError(f"Groq API timed out after {GROQ_TIMEOUT_SECONDS}s")
    except Exception as e:
        raise GroqUnavailableError(f"Groq API error: {e}")

    raw_text = response.choices[0].message.content or ""
    if not raw_text.strip():
        raise GroqUnavailableError("Groq returned empty response")

    try:
        return _parse_json(raw_text)
    except ValueError:
        logger.warning(f"Groq returned plain text (no JSON). Wrapping. Raw: {raw_text[:80]}")
        return _extract_plain_response(raw_text)


# ─────────────────────────────────────────────────────────────────────────────
# Public Interface
# ─────────────────────────────────────────────────────────────────────────────

async def get_groq_response(
    session,
    user_text: str,
    intent_hint: str,
) -> GroqResult:
    """
    Get a structured response from Groq Llama 3.3 70B.

    Args:
        session: ConversationSession (provides customer data + conversation history)
        user_text: The user's transcribed speech
        intent_hint: Pre-classified intent from intent_classifier

    Returns:
        GroqResult with validated Hindi response + metadata

    Raises:
        GroqUnavailableError: If Groq fails after retries — caller cascades to Gemini
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
    history = build_gemini_history(session)  # reuse existing history builder

    parsed: Optional[dict] = None
    validated_response: Optional[str] = None

    # Try up to 2 times
    for attempt in range(2):
        try:
            parsed = await _call_groq(system_prompt, history, user_text)
        except GroqUnavailableError:
            raise  # Let caller cascade to Gemini

        raw_response = parsed.get("response", "").strip()
        cleaned = _clean_response(raw_response)

        if _is_valid_response(cleaned):
            validated_response = cleaned
            break
        else:
            logger.warning(
                f"Groq response failed validation (attempt {attempt + 1}): "
                f"'{raw_response[:80]}'"
            )

    if validated_response is None or parsed is None:
        if parsed:
            raw_response = parsed.get("response", "").strip()
            if raw_response:
                validated_response = _clean_response(raw_response)
                logger.warning(
                    f"Using unvalidated Groq response after 2 attempts: '{raw_response[:60]}'"
                )
            else:
                raise GroqUnavailableError("Groq response failed validation after 2 attempts")
        else:
            raise GroqUnavailableError("Groq response failed validation after 2 attempts")

    elapsed_ms = int((time.time() - t_start) * 1000)

    result = GroqResult(
        response=validated_response,
        intent=parsed.get("intent", "unclear"),
        end_call=bool(parsed.get("end_call", False)),
        send_payment_link=bool(parsed.get("send_payment_link", False)),
        response_time_ms=elapsed_ms,
        llm_provider="groq",
        promised_date=parsed.get("promised_date"),
        promised_amount=parsed.get("promised_amount"),
        callback_requested=bool(parsed.get("callback_requested", False)),
    )

    logger.info(
        f"Groq | user='{user_text[:40]}' | hint={intent_hint} | "
        f"intent={result.intent} | end_call={result.end_call} | "
        f"send_link={result.send_payment_link} | {elapsed_ms}ms"
    )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Post-Call Summary Generation
# ─────────────────────────────────────────────────────────────────────────────

async def generate_call_summary(session) -> dict:
    """
    Generate a structured JSON call summary using Groq.
    Returns dictionary matching the CallSummary schema.
    Falls back gracefully on failure.
    """
    client = _get_client()

    history_text = "\n".join([
        f"{msg['role'].upper()}: {msg['parts'][0]['text']}"
        for msg in build_gemini_history(session)
    ])

    summary_prompt = f"""Analyze the following Hindi collection call transcript between an Executive and Customer.
The customer is {session.customer_name}. Amount due: {session.amount_due} for {session.bank_name}.

TRANSCRIPT:
{history_text}

Provide a structured JSON output exactly matching this schema (no markdown, no code fences):
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
}}"""

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a JSON-only output assistant. Return only valid JSON."},
                        {"role": "user", "content": summary_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=512,
                )
            ),
            timeout=15.0,
        )
        return _parse_json(response.choices[0].message.content or "")
    except Exception as e:
        logger.error(f"Groq: Failed to generate summary: {e}")
        return {
            "call_summary": "Failed to generate summary.",
            "customer_intent": "UNKNOWN",
            "payment_commitment": {"amount": None, "promised_date": None},
            "follow_up_required": True,
            "follow_up_reason": str(e),
            "call_outcome": "FAILED",
        }
