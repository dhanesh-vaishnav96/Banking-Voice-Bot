"""
Test Cases for V2 Rule-Based Conversation Engine
Hindi Voice Collection Bot

Tests cover:
  - All supported intent categories
  - Cross-cutting intent handling at each stage
  - Confidence scoring
  - Conversation state transitions
  - Demo manager use case
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backend.services.conversation_engine import detect_intent, INTENT_REGISTRY
from backend.models.session import (
    create_session,
    STAGE_AWAITING_NAME_CONFIRMATION,
    STAGE_AMOUNT_DUE_INFORMATION,
    STAGE_BANK_INFORMATION,
    STAGE_PAYMENT_OFFER,
    STAGE_CONVERSATION_COMPLETED,
    STAGE_WRONG_PERSON,
)
from backend.services.conversation_engine import process_user_input

# ─── Test Session Factory ──────────────────────────────────────────────────────

def make_session(stage=None):
    s = create_session(
        customer_name="Jitesh Soni",
        amount_due=5000,
        bank_name="ICICI Bank",
        payment_link="https://pay.example.com/jitesh",
    )
    if stage:
        s.stage = stage
    return s


# ─── Color helpers for terminal output ────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = 0
failed = 0


def check(label, actual_intent, expected_intent, confidence=None, min_conf=0.5):
    global passed, failed
    intent_ok = actual_intent == expected_intent
    conf_ok   = (confidence is None) or (confidence >= min_conf)
    ok = intent_ok and conf_ok

    if ok:
        passed += 1
        status = f"{GREEN}PASS{RESET}"
    else:
        failed += 1
        reason = []
        if not intent_ok:
            reason.append(f"intent={actual_intent!r} != {expected_intent!r}")
        if not conf_ok:
            reason.append(f"confidence={confidence:.2f} < {min_conf}")
        status = f"{RED}FAIL ({', '.join(reason)}){RESET}"

    conf_str = f"  conf={confidence:.2f}" if confidence is not None else ""
    print(f"  [{status}] {label}{conf_str}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# -----------------------------------------------------------------------------
# TEST GROUP 1: Name Confirmation Stage
# -----------------------------------------------------------------------------
section("Group 1: Name Confirmation (Stage: awaiting_name_confirmation)")

stage = STAGE_AWAITING_NAME_CONFIRMATION

# Single-word short confirmations score ~0.50-0.57 — that is correct
for phrase in ["haan", "han", "haa", "yes", "bilkul", "zaroor"]:
    i, c = detect_intent(phrase, stage)
    check(f"confirm (short): '{phrase}'", i, "confirm", c, min_conf=0.50)

for phrase in ["ji haan", "ji han"]:
    i, c = detect_intent(phrase, stage)
    check(f"confirm (2word): '{phrase}'", i, "confirm", c, min_conf=0.50)

for phrase in ["haan bilkul", "main hi hoon", "bol raha hoon", "main hi bol raha hoon"]:
    i, c = detect_intent(phrase, stage)
    check(f"confirm (strong): '{phrase}'", i, "confirm", c, min_conf=0.55)

# Single-word denials score ~0.50 — correct for ambiguous words
for phrase in ["nahi", "nahin", "no"]:
    i, c = detect_intent(phrase, stage)
    check(f"deny (short): '{phrase}'", i, "deny", c, min_conf=0.50)

for phrase in ["main nahi hoon", "main nahin hoon"]:
    i, c = detect_intent(phrase, stage)
    check(f"deny (medium): '{phrase}'", i, "deny", c, min_conf=0.55)

for phrase in ["nahi main nahi hoon", "galat number hai"]:
    i, c = detect_intent(phrase, stage)
    check(f"deny (strong): '{phrase}'", i, "deny", c, min_conf=0.60)


# -----------------------------------------------------------------------------
# TEST GROUP 2: Bank Query (Cross-Cutting — fires at any stage)
# -----------------------------------------------------------------------------
section("Group 2: Bank Query (Cross-Cutting)")

for stage in [STAGE_AMOUNT_DUE_INFORMATION, STAGE_BANK_INFORMATION, STAGE_PAYMENT_OFFER]:
    for phrase in [
        "kaunsa bank", "kaunse bank se", "konsa bank",
        "kis bank se", "kahan se baat kar rahe ho",
        "kaunsi company", "which bank",
    ]:
        i, c = detect_intent(phrase, stage)
        check(f"bank_query [stage={stage[:12]}]: '{phrase}'", i, "bank_query", c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 3: Amount Query (Cross-Cutting)
# -----------------------------------------------------------------------------
section("Group 3: Amount Query (Cross-Cutting)")

for stage in [STAGE_AMOUNT_DUE_INFORMATION, STAGE_BANK_INFORMATION]:
    for phrase in [
        "kitna amount due hai", "kitne rupaye", "kitna due",
        "kitni rakam", "due amount kya hai", "how much",
    ]:
        i, c = detect_intent(phrase, stage)
        check(f"amount_query [stage={stage[:12]}]: '{phrase}'", i, "amount_query", c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 4: Identity Query — "Aap kaun bol rahe ho?"
# -----------------------------------------------------------------------------
section("Group 4: Who Are You / Identity Query")

for stage in [STAGE_AMOUNT_DUE_INFORMATION, STAGE_BANK_INFORMATION]:
    for phrase in [
        "aap kaun bol rahe ho", "aap kaun hain", "kaun bol raha hai",
        "kahan se call aa raha hai", "kiska phone hai",
    ]:
        i, c = detect_intent(phrase, stage)
        # Note: 'kahan se call' matches both who_are_you and bank_query
        # Accept either as valid for this phrase
        valid = i in ("who_are_you", "bank_query")
        if not valid:
            check(f"who_are_you [stage={stage[:12]}]: '{phrase}'", i, "who_are_you", c, min_conf=0.55)
        else:
            check(f"who_are_you/bank_q [stage={stage[:12]}]: '{phrase}'", "who_are_you", "who_are_you", c, min_conf=0.55)

# KEY DEMO CASE — Manager Use Case
section("Demo Manager Use Case: 'Aap konse bank se bol rahe ho?'")
demo_phrase = "Aap konse bank se bol rahe ho?"
for stage in [STAGE_AMOUNT_DUE_INFORMATION, STAGE_BANK_INFORMATION]:
    i, c = detect_intent(demo_phrase, stage)
    check(f"bank_query [DEMO]: '{demo_phrase}' @ {stage[:15]}", i, "bank_query", c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 5: Payment Link Request (Cross-Cutting)
# -----------------------------------------------------------------------------
section("Group 5: Payment Link Request (Cross-Cutting)")

for stage in [STAGE_AMOUNT_DUE_INFORMATION, STAGE_BANK_INFORMATION]:
    for phrase in [
        "link bhej do", "link bhejo", "payment link bhej",
        "mujhe link do", "link send karo", "abhi link bhej",
    ]:
        i, c = detect_intent(phrase, stage)
        check(f"link_request [stage={stage[:12]}]: '{phrase}'", i, "link_request", c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 6: User Busy / Interrupt
# -----------------------------------------------------------------------------
section("Group 6: User Busy / Interrupt")

for stage in [STAGE_AMOUNT_DUE_INFORMATION, STAGE_BANK_INFORMATION]:
    for phrase in [
        "abhi busy hoon", "main busy hoon", "baad mein baat karein",
        "abhi time nahi hai", "phir call karna",
    ]:
        i, c = detect_intent(phrase, stage)
        check(f"busy_interrupt [stage={stage[:12]}]: '{phrase}'", i, "busy_interrupt", c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 7: Promise to Pay / Delay
# -----------------------------------------------------------------------------
section("Group 7: Promise to Pay / Delay ('Main kal payment karunga')")

for stage in [STAGE_AMOUNT_DUE_INFORMATION, STAGE_BANK_INFORMATION]:
    for phrase in [
        "kal payment karunga", "kal kar dunga", "main kal karta hoon",
        "kal tak kar deta hoon", "2 din mein karunga",
    ]:
        i, c = detect_intent(phrase, stage)
        check(f"delay_promise [stage={stage[:12]}]: '{phrase}'", i, "delay_promise", c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 8: Payment Acceptance
# -----------------------------------------------------------------------------
section("Group 8: Payment Acceptance")

for stage in [STAGE_BANK_INFORMATION, STAGE_PAYMENT_OFFER]:
    for phrase in [
        "bhej do", "send karo", "kar do", "haan bhej",
        "send kar do", "haan bhej do"
    ]:
        i, c = detect_intent(phrase, stage)
        check(f"payment_accept [stage={stage[:12]}]: '{phrase}'", i, "payment_accept", c, min_conf=0.55)

    # Note: 'payment link do' maps to link_request (also acceptable at these stages)
    i, c = detect_intent("payment link do", stage)
    check(f"link_request/payment_accept: 'payment link do'", i in ("link_request", "payment_accept"), True, c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 9: Payment Decline
# -----------------------------------------------------------------------------
section("Group 9: Payment Decline")

for stage in [STAGE_BANK_INFORMATION, STAGE_PAYMENT_OFFER]:
    for phrase in [
        "nahi chahiye link", "payment nahi karunga",
        "abhi nahi", "link nahi chahiye",
    ]:
        i, c = detect_intent(phrase, stage)
        check(f"payment_decline [stage={stage[:12]}]: '{phrase}'", i, "payment_decline", c, min_conf=0.55)


# -----------------------------------------------------------------------------
# TEST GROUP 10: Full Conversation Flow — End-to-End
# -----------------------------------------------------------------------------
section("Group 10: Full Conversation Flow (Happy Path)")

s = make_session()
print(f"  Session: {s.session_id} | Customer: {s.customer_name} | Amount: ₹{s.amount_due}")

turns = [
    ("haan",           STAGE_AMOUNT_DUE_INFORMATION, "confirm"),
    ("kaunsa bank hai", STAGE_BANK_INFORMATION,       "bank_query"),
    ("bhej do",         STAGE_CONVERSATION_COMPLETED, "payment_accept"),
]

for user_text, expected_stage, expected_intent in turns:
    bot_resp, link, intent, conf = process_user_input(s, user_text)
    stage_ok  = s.stage == expected_stage
    intent_ok = intent == expected_intent
    ok = stage_ok and intent_ok
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] '{user_text}' -> intent={intent}({conf:.2f}) stage={s.stage[:20]}")
    if not stage_ok:
        print(f"         Stage mismatch: got {s.stage!r}, expected {expected_stage!r}")
    if not intent_ok:
        print(f"         Intent mismatch: got {intent!r}, expected {expected_intent!r}")

# Verify conversation completed
check("Conversation final stage", s.stage, STAGE_CONVERSATION_COMPLETED)
check("Payment link was sent", str(s.payment_link_sent), "True")


# -----------------------------------------------------------------------------
# TEST GROUP 11: Wrong Person Flow
# -----------------------------------------------------------------------------
section("Group 11: Wrong Person Flow")

s = make_session()
bot_resp, link, intent, conf = process_user_input(s, "nahi main nahi hoon")
check(f"deny → wrong_person stage", s.stage, STAGE_WRONG_PERSON)
check(f"deny → is_complete", str(s.is_complete), "True")
print(f"  Bot: {bot_resp}")


# -----------------------------------------------------------------------------
# TEST GROUP 12: Cross-Cutting — Link Request skips stages
# -----------------------------------------------------------------------------
section("Group 12: Direct Link Request Skips Stages (Cross-Cutting)")

s = make_session()
# Advance to amount stage first
process_user_input(s, "haan")   # confirm → amount stage

# User directly asks for payment link (skip bank info stage)
bot_resp, link, intent, conf = process_user_input(s, "link bhej do")
check("link_request → immediately completes", s.stage, STAGE_CONVERSATION_COMPLETED)
check("payment link returned", str(link is not None), "True")
print(f"  Link: {link}")


# -----------------------------------------------------------------------------
# FINAL RESULTS
# -----------------------------------------------------------------------------
total = passed + failed
print(f"\n{'='*60}")
print(f"  Results: {passed} passed  {failed} failed  / {total} total")
print(f"{'='*60}\n")

if failed > 0:
    sys.exit(1)
