"""
Rule-Based Conversation Engine — Version 2
Hindi Voice Collection Bot

V2 Improvements:
  - Stage-independent (cross-cutting) intent handling
  - User can interrupt at any point to ask bank, amount, identity, or request link
  - Richer, more natural Hindi conversational responses
  - Confidence scoring per intent match
  - Detailed conversation logging (timestamp, intent, confidence, stage)
  - Support for delay/busy/tomorrow responses
  - No LLM — pure keyword matching with priority dispatch

Intent Priority (highest first):
  1. Cross-cutting: who_are_you, bank_query, amount_query, link_request, busy, delay, payment_decline
  2. Stage-specific: confirm, deny, proceed, payment_accept
"""

import re
import time
import datetime
from typing import Tuple, Optional, Dict, Any
from backend.utils import number_to_hindi_words
from backend.models.session import (
    ConversationSession,
    STAGE_AWAITING_NAME_CONFIRMATION,
    STAGE_AMOUNT_DUE_INFORMATION,
    STAGE_BANK_INFORMATION,
    STAGE_PAYMENT_OFFER,
    STAGE_CONVERSATION_COMPLETED,
    STAGE_WRONG_PERSON,
)


# ─────────────────────────────────────────────────────────────────────────────
# Intent Registry — keyword sets with confidence weights
# ─────────────────────────────────────────────────────────────────────────────

# Each entry: (keywords_list, base_confidence)
# Longer / more specific keywords → higher confidence
INTENT_REGISTRY: Dict[str, Tuple[list, float]] = {

    # ── Cross-Cutting Intents (handled at any stage) ──────────────────────────

    "who_are_you": ([
        "aap kaun bol rahe ho", "aap kaun hain", "aap kaun ho",
        "kaun bol raha hai", "kaun hai", "kaun baat kar raha hai",
        "kiska phone hai", "kahan se call", "kahan se bol rahe",
        "who are you", "identify yourself",
    ], 0.93),

    "bank_query": ([
        "kaunse bank se", "kaunsa bank", "kaun sa bank", "konsa bank",
        "konse bank", "kis bank se", "kis bank se", "which bank",
        "kaunsi company", "kaun si company", "konsi company", "kis company",
        "kahan se baat kar", "kis taraf se", "kahan se call aa raha",
    ], 0.90),

    "amount_query": ([
        "kitna amount", "kitne rupaye", "kitna due", "kitni rakam",
        "kitna paisa", "kitna baaki", "due amount kya hai",
        "amount kya hai", "kitne paise due hain", "how much",
        "kitna banta hai", "total kitna",
    ], 0.90),

    "link_request": ([
        "link bhej do", "link bhejo", "link bhej dena", "link bhej de",
        "payment link bhej", "payment link do", "link send karo",
        "link send kar do", "send link", "mujhe link do",
        "link chahiye", "payment link chahiye", "abhi link bhej",
    ], 0.95),

    "busy_interrupt": ([
        "abhi busy hoon", "main busy hoon", "busy hoon abhi",
        "baad mein baat karein", "baad mein call karo",
        "abhi time nahi hai", "time nahi hai abhi",
        "phir call karna", "baad mein karna",
        "i am busy", "busy right now",
    ], 0.88),

    "delay_promise": ([
        "kal payment karunga", "kal kar dunga", "kal karta hoon",
        "kal tak kar deta hoon", "kal karunga",
        "parso karunga", "agle hafte karunga",
        "2 din mein karunga", "do din mein karta hoon",
        "thodi der mein karunga", "evening mein karunga",
        "i will pay tomorrow", "will pay later",
    ], 0.87),

    "payment_already_done": ([
        "main kar chuka hoon", "already done", "payment kar diya",
        "maine bhar diya", "already paid", "pehle hi de diya",
        "de chuka hoon", "paisa de diya", "i have paid",
        "subah kar diya", "kal kar diya tha",
    ], 0.92),

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

    # ── Affirmative / Name Confirmation ───────────────────────────────────────

    "confirm": ([
        "ji haan", "ji han", "haan ji", "han ji",
        "haan bilkul", "bilkul haan",
        "bol raha hoon", "bol raha hun", "main hi bol raha hoon",
        "main hi hoon", "haan main hi hoon",
        "ji main", "main hi", "main hoon",
        "haan", "han", "haa", "haan haan",
        "haan kar sakte ho", "haan baat kar sakte ho",
        "haan tum mere se baat kar sakte ho",
        "हां", "जी हां", "हाँ", "जी हाँ", "बिल्कुल", "ठीक है",
        "yes", "yeah", "yep", "yes speaking",
        "bilkul", "zaroor", "sure",
        "theek hai", "thik hai",
        "ok", "okay",
    ], 0.90),

    # ── Negative / Wrong Person ────────────────────────────────────────────────

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

    # ── Payment Acceptance ────────────────────────────────────────────────────

    "payment_accept": ([
        "bhej do", "bhejdo", "bhej dena", "bhej de", "bhejo",
        "send karo", "send kar do", "send karein", "send kijiye",
        "kar do", "kardo", "kar dena",
        "haan bhej", "link bhej", "payment karna chahta hoon",
        "abhi payment karta hoon",
    ], 0.92),

    # ── Payment Decline ───────────────────────────────────────────────────────

    "payment_decline": ([
        "nahi chahiye link", "link nahi chahiye",
        "payment nahi karunga", "nahi karunga",
        "abhi nahi", "nahi abhi",
    ], 0.90),
}

# Intents that can override stage flow at any point (except name confirmation)
CROSS_CUTTING_INTENTS = {
    "who_are_you", "bank_query", "amount_query",
    "link_request", "busy_interrupt", "delay_promise",
    "payment_already_done", "partial_payment", "angry_customer",
    "supervisor_request",
}

# Intents that terminate the conversation
TERMINAL_INTENTS = {"deny"}
# Human-readable intent labels (used by demo script and frontend)
INTENT_LABELS = {
    'confirm':         'Confirmed',
    'deny':            'Wrong Person',
    'bank_query':      'Bank Query',
    'amount_query':    'Amount Query',
    'link_request':    'Link Request',
    'busy_interrupt':  'User Busy',
    'delay_promise':   'Promise to Pay',
    'payment_accept':  'Accepted Payment',
    'payment_decline': 'Declined Payment',
    'payment_already_done': 'Payment Already Done',
    'who_are_you':     'Identity Query',
    'proceed':         'Acknowledged',
    'unclear':         'Unclear',
    'partial_payment': 'Partial Payment',
    'angry_customer':  'Angry Customer',
    'supervisor_request': 'Supervisor Request',
}




# ─────────────────────────────────────────────────────────────────────────────
# Text Normalisation
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _match_score(text: str, keywords: list) -> float:
    """
    Return match quality [0.0, 1.0]:
      - 0.0 → no match
      - Score increases with keyword specificity (length as proxy)
    """
    norm = _normalise(text)
    best = 0.0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in norm:
            # Longer keyword = more specific match = higher raw score
            specificity = min(1.0, len(kw_lower.split()) / 6.0)
            score = 0.5 + (0.5 * specificity)
            best = max(best, score)
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Intent Detection — returns (intent_name, confidence)
# ─────────────────────────────────────────────────────────────────────────────

def detect_intent(text: str, stage: str) -> Tuple[str, float]:
    """
    Detect user intent from text at the given stage.

    V2 Priority Strategy:
      1. Score all intents.
      2. Cross-cutting intents ALWAYS win if they have ANY match score,
         regardless of stage-specific score (except at name-confirmation).
      3. Stage-specific matching only applies if no cross-cutting matched.

    Returns:
        (intent_name, confidence_0_to_1)
    """
    best_intent = "unclear"
    best_score = 0.0

    # Step 1: Score all intents
    scored = {}
    for intent_name, (keywords, base_conf) in INTENT_REGISTRY.items():
        raw = _match_score(text, keywords)
        if raw > 0.0:
            scored[intent_name] = raw * base_conf

    # Step 2: Cross-cutting STRICT priority
    # Cross-cutting intents win absolutely at any stage.
    cross_cutting_matched = False
    for intent_name in CROSS_CUTTING_INTENTS:
            s = scored.get(intent_name, 0)
            if s > best_score:
                best_score = s
                best_intent = intent_name
                cross_cutting_matched = True

    # Step 3: Stage-specific (only if NO cross-cutting matched)
    if not cross_cutting_matched:
        stage_intent, stage_conf = _stage_specific_intent(text, stage, scored)
        if stage_conf > best_score:
            best_score = stage_conf
            best_intent = stage_intent

    # Step 4: Confidence floor and cap
    confidence = round(min(0.99, max(0.50, best_score)), 2)
    if best_intent == "unclear":
        confidence = 0.50

    return best_intent, confidence


def _stage_specific_intent(
    text: str, stage: str, scored: Dict[str, float]
) -> Tuple[str, float]:
    """Return the best stage-specific intent and its score."""

    if stage == STAGE_AWAITING_NAME_CONFIRMATION:
        deny_score    = scored.get("deny", 0)
        confirm_score = scored.get("confirm", 0)
        if deny_score > confirm_score and deny_score > 0:
            return "deny", deny_score
        if confirm_score > 0:
            return "confirm", confirm_score
        return "unclear", 0.0

    elif stage == STAGE_AMOUNT_DUE_INFORMATION:
        # After amount info — any non-cross-cutting response advances stage
        for intent_name in ("bank_query", "confirm", "payment_accept", "payment_decline"):
            if scored.get(intent_name, 0) > 0:
                return "proceed", scored[intent_name]
        return "proceed", 0.70  # default advance

    elif stage in (STAGE_BANK_INFORMATION, STAGE_PAYMENT_OFFER):
        decline_score = scored.get("payment_decline", 0)
        accept_score  = max(
            scored.get("payment_accept", 0),
            scored.get("confirm", 0),
        )
        if decline_score > accept_score and decline_score > 0:
            return "payment_decline", decline_score
        if accept_score > 0:
            return "payment_accept", accept_score
        return "payment_accept", 0.65  # optimistic default

    return "unclear", 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Amount Formatter
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_amount(amount: float) -> str:
    if amount == int(amount):
        return str(int(amount))
    return f"{amount:.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# V2 Response Templates — Natural, Conversational Hindi
# ─────────────────────────────────────────────────────────────────────────────

def get_opening_message(session: ConversationSession) -> str:
    return (
        f"Namaste! Kya main {session.customer_name} ji se baat kar sakta hoon?"
    )


def get_wrong_person_message(session: ConversationSession) -> str:
    return (
        f"Maaf kijiye. Mujhe {session.customer_name} ji se baat karni thi. Dhanyavaad. Namaste."
    )


def get_amount_due_information(session: ConversationSession) -> str:
    amount_hindi = number_to_hindi_words(session.amount_due)
    return (
        f"{session.customer_name} ji, aapke account mein {amount_hindi} rupaye ki "
        "due payment pending hai. Kripaya isse jald se jald clear kar dein."
    )


def get_who_are_you_message(session: ConversationSession) -> str:
    amount_hindi = number_to_hindi_words(session.amount_due)
    return (
        f"Ji, main {session.bank_name} ke collections department se bol raha hoon. "
        f"Aapke account mein {amount_hindi} rupaye due hain, "
        "aur main aapki madad karna chahta hoon isse resolve karne mein."
    )


def get_bank_only_message(session: ConversationSession) -> str:
    """Answer bank query without immediately jumping to payment offer."""
    return (
        f"Ji, main {session.bank_name} ki taraf se bol raha hoon. "
        "Kya aap abhi payment ke baare mein baat karna chahenge?"
    )


def get_amount_only_message(session: ConversationSession) -> str:
    """Answer amount query in isolation."""
    amount_hindi = number_to_hindi_words(session.amount_due)
    return (
        f"{session.customer_name} ji, aapke account mein abhi "
        f"{amount_hindi} rupaye ki pending payment hai. "
        "Kya main payment link share karun?"
    )


def get_bank_information(session: ConversationSession) -> str:
    amount_hindi = number_to_hindi_words(session.amount_due)
    return (
        f"Ji, main {session.bank_name} se bol raha hoon. "
        f"Aapke account mein {amount_hindi} rupaye pending hain. "
        "Kya main abhi payment link share karun? Aap ek click mein payment kar sakte hain."
    )


def get_payment_link_message(session: ConversationSession) -> str:
    return (
        "Bilkul sir. Main payment link share kar raha hoon. "
        "Aap is link ka use karke apni payment complete kar sakte hain."
    )


def get_busy_message(session: ConversationSession) -> str:
    return (
        f"Ji bilkul, {session.customer_name} ji. Koi baat nahi! "
        "Main samajhta hoon aap busy hain. "
        "Main abhi payment link share kar raha hoon. "
        "Aap jab free hon tab is link ka use karke payment kar sakte hain."
    )


def get_delay_message(session: ConversationSession) -> str:
    return (
        f"Theek hai, {session.customer_name} ji. "
        "Main aapki baat samajh raha hoon. "
        "Kripaya jald se jald payment kar dein taaki koi extra charges na lagein. "
        "Main abhi payment link share kar raha hoon. "
        "Aap is link ka use karke apni payment complete kar sakte hain. Dhanyavaad!"
    )


def get_payment_decline_message(session: ConversationSession) -> str:
    return (
        f"Theek hai, {session.customer_name} ji. "
        "Koi baat nahi. Lekin please dhyan rakhein ki due amount par "
        "late charges lag sakte hain. "
        "Jab bhi payment karna ho, hamare helpline par call karein. Namaste!"
    )


def get_payment_already_done_message(session: ConversationSession) -> str:
    return (
        f"Acha, {session.customer_name} ji. Agar aapne payment kar diya hai, "
        "to kripaya use update hone mein 24 ghante ka samay dein. "
        "Hum apna system check kar lenge. Aapka bohot shukriya. Namaste!"
    )


def get_payment_offer_followup(session: ConversationSession) -> str:
    """Offer payment link after bank info was given."""
    return (
        f"Toh {session.customer_name} ji, kya main abhi payment link share karun? "
        "Bahut aasaan hai — ek click mein ho jayega."
    )


def get_unclear_message(session: ConversationSession, stage: str) -> str:
    """Stage-aware fallback when intent is unclear."""
    if stage == STAGE_AWAITING_NAME_CONFIRMATION:
        return (
            f"Maaf kijiye, kya aap {session.customer_name} ji bol rahe hain? "
            "Kripaya haan ya nahi mein batayein."
        )
    elif stage == STAGE_AMOUNT_DUE_INFORMATION:
        return (
            f"{session.customer_name} ji, kya aapka koi sawaal hai "
            "payment ke baare mein?"
        )
    elif stage in (STAGE_BANK_INFORMATION, STAGE_PAYMENT_OFFER):
        return (
            f"{session.customer_name} ji, kya main aapko payment link bhejun? "
            "Haan ya nahi batayein."
        )
    return "Maaf kijiye, kya aap phir se bol sakte hain?"


# ─────────────────────────────────────────────────────────────────────────────
# Conversation Logger
# ─────────────────────────────────────────────────────────────────────────────

def _log_turn(
    session: ConversationSession,
    user_text: str,
    bot_response: str,
    intent: str,
    confidence: float,
    stage_before: str,
    stage_after: str,
):
    """Append a structured log entry to the session's conversation_log."""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "stage_before": stage_before,
        "stage_after": stage_after,
        "user_message": user_text,
        "bot_response": bot_response,
        "intent": intent,
        "confidence": confidence,
    }
    session.conversation_log.append(entry)
    session.add_to_history("user", user_text)
    session.add_to_history("bot", bot_response)


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine — process_user_input (V2)
# ─────────────────────────────────────────────────────────────────────────────

def process_user_input(
    session: ConversationSession,
    user_text: str,
) -> Tuple[str, Optional[str], str, float]:
    """
    Process user input and advance the conversation.

    V2 Strategy:
      - Cross-cutting intents override stage flow
      - Stage-specific intents handle structured progression
      - All responses are personalized with customer name

    Returns:
        (bot_response, payment_link_or_None, intent_name, confidence)
    """
    stage_before = session.stage
    intent, confidence = detect_intent(user_text, stage_before)

    bot_response: str = ""
    payment_link: Optional[str] = None

    # ── Already Completed ──────────────────────────────────────────────────────
    if stage_before in (STAGE_CONVERSATION_COMPLETED, STAGE_WRONG_PERSON):
        bot_response = (
            "Yeh conversation samaapt ho chuki hai. Dhanyavaad aur namaste!"
        )
        _log_turn(session, user_text, bot_response, intent, confidence,
                  stage_before, stage_before)
        return bot_response, None, intent, confidence

    # ════════════════════════════════════════════════════════════════════════
    # CROSS-CUTTING INTENT HANDLERS
    # (fire at any stage except final confirmation when in name stage)
    # ════════════════════════════════════════════════════════════════════════

    if intent == "partial_payment":
        bot_response = "Aap aadha payment abhi kar sakte hain taaki account active rahe. Main link bhej raha hoon."
        session.advance_to(STAGE_CONVERSATION_COMPLETED)
        return bot_response, session.payment_link, intent, confidence

    if intent == "angry_customer":
        bot_response = "Jitesh ji, main samajhta hoon aapko takleef hui — main aapko pareshan nahi karoonga. Theek hai."
        session.advance_to(STAGE_CONVERSATION_COMPLETED)
        return bot_response, None, intent, confidence

    if intent == "supervisor_request":
        bot_response = "Zaroor, main apne senior ko bata deta hoon. Woh aapko jald callback karenge. Dhanyavaad."
        session.advance_to(STAGE_CONVERSATION_COMPLETED)
        return bot_response, None, intent, confidence

    if intent == "who_are_you":
        bot_response = get_who_are_you_message(session)
        # Don't advance stage — continue where we were

    elif intent == "bank_query":
        if stage_before in (STAGE_BANK_INFORMATION, STAGE_PAYMENT_OFFER):
            # Already in bank/offer stage — answer fully and send link
            bot_response = get_bank_then_offer_message(session)
        elif stage_before == STAGE_AMOUNT_DUE_INFORMATION:
            # Bank query at amount stage → answer bank + offer, advance to bank_information
            bot_response = get_bank_then_offer_message(session)
            session.advance_to(STAGE_BANK_INFORMATION)
        elif stage_before == STAGE_AWAITING_NAME_CONFIRMATION:
            # Bank query at name stage → answer and ask name again
            bot_response = f"Ji, main {session.bank_name} se bol raha hoon. Kya meri baat {session.customer_name} ji se ho rahi hai?"
        else:
            # Other stages — just identify ourselves
            bot_response = get_who_are_you_message(session)

    elif intent == "amount_query":
        bot_response = get_amount_only_message(session)
        # Advance to amount stage if we're still at name confirmation and confirmed
        if stage_before == STAGE_AMOUNT_DUE_INFORMATION:
            session.advance_to(STAGE_BANK_INFORMATION)

    elif intent == "link_request":
        # User directly asks for payment link — skip ahead
        bot_response = get_payment_link_message(session)
        payment_link = session.payment_link
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif intent == "busy_interrupt":
        # Send link proactively, end conversation
        bot_response = get_busy_message(session)
        payment_link = session.payment_link
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif intent == "delay_promise":
        # Acknowledge, send link, end
        bot_response = get_delay_message(session)
        payment_link = session.payment_link
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif intent == "payment_already_done":
        bot_response = get_payment_already_done_message(session)
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif intent == "payment_decline" and stage_before != STAGE_AWAITING_NAME_CONFIRMATION:
        bot_response = get_payment_decline_message(session)
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    # ════════════════════════════════════════════════════════════════════════
    # STAGE-SPECIFIC HANDLERS
    # ════════════════════════════════════════════════════════════════════════

    elif stage_before == STAGE_AWAITING_NAME_CONFIRMATION:
        if intent == "confirm":
            bot_response = get_amount_due_information(session)
            session.advance_to(STAGE_AMOUNT_DUE_INFORMATION)
        elif intent == "deny":
            bot_response = get_wrong_person_message(session)
            session.advance_to(STAGE_WRONG_PERSON)
        else:
            bot_response = get_unclear_message(session, stage_before)

    elif stage_before == STAGE_AMOUNT_DUE_INFORMATION:
        # Any response after amount info → reveal bank + offer link
        bot_response = get_bank_information(session)
        session.advance_to(STAGE_BANK_INFORMATION)

    elif stage_before == STAGE_BANK_INFORMATION:
        if intent == "payment_accept":
            bot_response = get_payment_link_message(session)
            payment_link = session.payment_link
            session.advance_to(STAGE_CONVERSATION_COMPLETED)
        elif intent == "payment_decline":
            bot_response = get_payment_decline_message(session)
            session.advance_to(STAGE_CONVERSATION_COMPLETED)
        else:
            # Default: offer the link
            bot_response = get_payment_link_message(session)
            payment_link = session.payment_link
            session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif stage_before == STAGE_PAYMENT_OFFER:
        if intent == "payment_decline":
            bot_response = get_payment_decline_message(session)
            session.advance_to(STAGE_CONVERSATION_COMPLETED)
        else:
            bot_response = get_payment_link_message(session)
            payment_link = session.payment_link
            session.advance_to(STAGE_CONVERSATION_COMPLETED)

    else:
        bot_response = get_unclear_message(session, stage_before)

    stage_after = session.stage

    # Track payment_link_sent on session directly
    if payment_link:
        session.payment_link_sent = True

    _log_turn(session, user_text, bot_response, intent, confidence,
              stage_before, stage_after)

    return bot_response, payment_link, intent, confidence
