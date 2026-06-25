"""
intent_classifier.py — Lightweight, stateless intent classifier.

Extracted from conversation_engine.py keyword registry.
Used as a "hint" context passed to Gemini, and as the authoritative
classifier when Gemini is unavailable (fallback mode).

This module has zero I/O — it is pure Python string matching.
"""

import re
from typing import Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Normalizer
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\u0900-\u097f]", " ", text)  # keep Devanagari
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Keyword Registry
# Format: intent -> ([keywords], base_confidence)
# ─────────────────────────────────────────────────────────────────────────────

_REGISTRY: dict = {

    "confirm": ([
        "ji haan", "ji han", "haan ji", "han ji",
        "haan bilkul", "bilkul haan",
        "bol raha hoon", "bol raha hun", "main hi bol raha hoon",
        "main hi hoon", "haan main hi hoon",
        "ji main", "main hi", "main hoon",
        "haan haan", "haan kar sakte ho", "haan baat kar sakte ho",
        "haan tum mere se baat kar sakte ho",
        "haan", "han", "haa",
        "हां", "जी हां", "हाँ", "जी हाँ", "बिल्कुल", "ठीक है",
        "yes", "yeah", "yep", "yes speaking", "speaking",
        "bilkul", "zaroor", "sure",
        "theek hai", "thik hai",
        "ok", "okay",
    ], 0.90),

    "deny": ([
        "nahi main nahi hoon", "main nahi hoon",
        "galat number hai", "wrong number",
        "nahi bol raha", "nahi ji nahi",
        "nahi hoon main", "main nahin hoon",
        "nahi", "nahin", "no",
        "नहीं", "ना", "गलत",
        "wrong person", "aapne galat number lagaya hai",
        "not speaking", "nahi hoon",
    ], 0.88),

    "who_are_you": ([
        "aap kaun bol rahe ho", "aap kaun hain", "aap kaun ho",
        "kaun bol raha hai", "kaun hai", "kaun baat kar raha hai",
        "kiska phone hai", "kahan se call", "kahan se bol rahe",
        "who are you", "identify yourself",
    ], 0.93),

    "bank_query": ([
        "kis bank se", "kaunsa bank", "kon sa bank",
        "bank ka naam", "bank name",
        "aap kaun ho", "kaun sa institution",
        "which bank", "bank bolo",
    ], 0.88),

    "amount_query": ([
        "kitna paisa", "kitne rupaye", "amount kitna",
        "kitni payment", "how much", "amount kya hai",
        "total kitna", "due amount",
    ], 0.88),

    "link_request": ([
        "link bhej do", "link send karo", "payment link",
        "link chahiye", "payment karna hai",
        "send the link", "link do", "bhej do",
        "haan bhejo", "link share karo",
    ], 0.92),

    "already_paid": ([
        "maine payment kar diya", "payment ho gaya",
        "already paid", "kar diya maine",
        "pay kar diya", "paise de diye",
        "payment complete", "payment done",
    ], 0.92),

    "busy_interrupt": ([
        "busy hoon", "baad mein call karo", "main meeting mein hoon",
        "abhi nahi", "baad mein baat karte hain",
        "thodi der baad", "busy hai",
        "call back karo", "later call",
    ], 0.90),

    "delay_promise": ([
        "kal karunga", "kal kar dunga", "kal payment karunga",
        "do din mein", "week mein karunga",
        "promise karunga", "zaroor karunga",
        "jald karunga", "karta hoon",
    ], 0.88),

    "payment_accept": ([
        "haan karunga", "bilkul karunga", "payment karunga",
        "abhi karta hoon", "karta hoon",
        "yes will pay", "pay kar deta hoon",
        "okay karunga", "thik hai karunga",
    ], 0.88),

    "payment_decline": ([
        "nahi karunga", "payment nahi karunga",
        "nahi dunga", "refuse",
        "mat karo", "nahi karna",
        "no payment", "main nahi dunga", "nahi bharunga",
        "refusal to pay", "paise nahi hain"
    ], 0.88),

    "partial_payment": ([
        "aadha de sakta hoon", "aadha payment", "thoda payment",
        "half payment", "kuch de sakta hoon", "part payment",
        "aadhe paise", "50 percent"
    ], 0.90),

    "angry_customer": ([
        "pareshan mat karo", "bar bar phone kyu karte ho",
        "dimag kharab", "harassment", "police complaint",
        "gussa", "pagal ho kya", "stop calling", "don't call"
    ], 0.92),

    "supervisor_request": ([
        "manager se baat", "manager se baat karao",
        "apne senior se", "supervisor se baat",
        "senior", "manager", "escalate"
    ], 0.92),
}


# ─────────────────────────────────────────────────────────────────────────────
# Scoring helper
# ─────────────────────────────────────────────────────────────────────────────

def _match_score(user_norm: str, keyword: str, base_conf: float) -> float:
    """Score how well a keyword matches the normalized user text."""
    kw = _normalise(keyword)
    if not kw:
        return 0.0
    # Exact containment
    if kw in user_norm:
        specificity = min(len(kw) / max(len(user_norm), 1), 1.0)
        return base_conf * (0.7 + 0.3 * specificity)
    # Word-boundary partial
    user_words = set(user_norm.split())
    kw_words = set(kw.split())
    common = user_words & kw_words
    if not common:
        return 0.0
    ratio = len(common) / len(kw_words)
    if ratio >= 0.5:
        return base_conf * 0.55 * ratio
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def classify_intent(user_text: str, stage: str = "") -> Tuple[str, float]:
    """
    Classify user_text into the best matching intent.

    Returns:
        (intent_name, confidence) where confidence is in [0, 1].
        Falls back to ("unclear", 0.5) when no good match is found.
    """
    user_norm = _normalise(user_text)
    if not user_norm:
        return "unclear", 0.0

    best_intent = "unclear"
    best_score = 0.0

    for intent, (keywords, base_conf) in _REGISTRY.items():
        for kw in keywords:
            score = _match_score(user_norm, kw, base_conf)
            if score > best_score:
                best_score = score
                best_intent = intent

    if best_score < 0.45:
        return "unclear", 0.5

    return best_intent, round(best_score, 3)
