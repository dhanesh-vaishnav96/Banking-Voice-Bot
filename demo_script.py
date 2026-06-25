"""
Demo Script — Manager Use Case
Hindi Voice Collection Bot V2

Scenario:
  Agent Name : Jitesh Soni
  Amount     : ₹5,000
  Bank       : ICICI Bank

Flow:
  Bot  → Asks for name confirmation
  User → Asks "Aap konse bank se bol rahe ho?" (cross-cutting intent at name stage)
  Bot  → Handles identity query, re-asks name confirmation
  User → Confirms identity
  Bot  → States due amount
  User → "Main kal payment karunga" (delay promise)
  Bot  → Acknowledges, sends payment link proactively
"""

import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.session import create_session
from backend.services.conversation_engine import (
    get_opening_message,
    process_user_input,
    INTENT_LABELS,
)

# ─── ANSI Colors ──────────────────────────────────────────────────────────────
BOT  = "\033[94m"   # Blue
USER = "\033[92m"   # Green
INFO = "\033[93m"   # Yellow
BOLD = "\033[1m"
DIM  = "\033[2m"
RESET = "\033[0m"

def bot_say(text):
    print(f"\n  {BOT}{BOLD}🤖 Bot:{RESET}  {text}")

def user_say(text):
    print(f"\n  {USER}{BOLD}👤 User:{RESET} {text}")

def show_intent(intent, confidence):
    label = INTENT_LABELS.get(intent, intent)
    pct = int(confidence * 100)
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    print(f"  {DIM}  ↳ Intent: [{label}]  Confidence: {bar} {pct}%{RESET}")

def divider():
    print(f"\n  {DIM}{'─' * 58}{RESET}")

def header():
    print(f"\n{BOLD}{'═' * 62}")
    print("  Hindi Voice Collection Bot V2 — Manager Use Case Demo")
    print(f"{'═' * 62}{RESET}")
    print(f"  Customer : Jitesh Soni")
    print(f"  Amount   : ₹5,000")
    print(f"  Bank     : ICICI Bank")
    print(f"  Link     : https://pay.example.com/jitesh")
    print(f"{BOLD}{'─' * 62}{RESET}")


# ─── Demo Runs ────────────────────────────────────────────────────────────────

def run_demo():
    header()

    # Create session
    session = create_session(
        customer_name="Jitesh Soni",
        amount_due=5000,
        bank_name="ICICI Bank",
        payment_link="https://pay.example.com/jitesh",
    )

    # Step 0: Bot opens conversation
    opening = get_opening_message(session)
    session.add_to_history("bot", opening)
    bot_say(opening)
    print(f"  {DIM}  Stage: {session.stage}{RESET}")

    # ── Turn 1: User confirms name ─────────────────────────────────────────────
    divider()
    user_text = "Haan"
    user_say(user_text)
    bot_resp, link, intent, conf = process_user_input(session, user_text)
    bot_say(bot_resp)
    show_intent(intent, conf)
    print(f"  {DIM}  Stage: {session.stage}{RESET}")

    # ── Turn 2: User asks bank query at amount stage ───────────────────────────
    divider()
    user_text = "Aap konse bank se bol rahe ho?"
    user_say(user_text)
    bot_resp, link, intent, conf = process_user_input(session, user_text)
    bot_say(bot_resp)
    show_intent(intent, conf)
    print(f"  {DIM}  Stage: {session.stage}{RESET}")

    # ── Turn 3: User accepts payment link ──────────────────────────────────────
    divider()
    user_text = "Haan bhej do"
    user_say(user_text)
    bot_resp, link, intent, conf = process_user_input(session, user_text)
    bot_say(bot_resp)
    show_intent(intent, conf)
    if link:
        print(f"\n  {BOLD}💳 Payment Link: {link}{RESET}")
    print(f"  {DIM}  Stage: {session.stage} | Complete: {session.is_complete}{RESET}")

    # ── Summary ────────────────────────────────────────────────────────────────
    divider()
    print(f"\n{BOLD}{'─' * 62}")
    print("  Session Summary")
    print(f"{'─' * 62}{RESET}")
    print(f"  Session ID     : {session.session_id}")
    print(f"  Final Stage    : {session.stage}")
    print(f"  Is Complete    : {session.is_complete}")
    print(f"  Payment Sent   : {session.payment_link_sent}")
    print(f"  Total Turns    : {session.turn_count}")
    print(f"  Intents Seen   : {', '.join(session.intents_detected)}")
    print(f"\n  Conversation Log:")
    for entry in session.conversation_log:
        label = INTENT_LABELS.get(entry['intent'], entry['intent'])
        pct   = int(entry['confidence'] * 100)
        print(f"  ├─ [{label} {pct}%]")
        print(f"  │   User: {entry['user_message']}")
        print(f"  │   Bot : {entry['bot_response'][:80]}...")
    print(f"{BOLD}{'═' * 62}{RESET}\n")


# ─── Alternative Demo: Direct Payment Link Request ────────────────────────────

def run_demo_direct_link():
    print(f"\n{BOLD}{'─' * 62}")
    print("  DEMO 2: User Directly Requests Payment Link (Skips Stages)")
    print(f"{'─' * 62}{RESET}")

    session = create_session(
        customer_name="Jitesh Soni",
        amount_due=5000,
        bank_name="ICICI Bank",
        payment_link="https://pay.example.com/jitesh",
    )

    opening = get_opening_message(session)
    session.add_to_history("bot", opening)
    bot_say(opening)

    divider()
    user_text = "Haan main hoon"
    user_say(user_text)
    bot_resp, link, intent, conf = process_user_input(session, user_text)
    bot_say(bot_resp)
    show_intent(intent, conf)

    divider()
    print(f"\n  {INFO}NOTE: User skips bank/amount info and directly requests link{RESET}")
    user_text = "Link bhej do mujhe"
    user_say(user_text)
    bot_resp, link, intent, conf = process_user_input(session, user_text)
    bot_say(bot_resp)
    show_intent(intent, conf)
    if link:
        print(f"\n  {BOLD}💳 Payment Link: {link}{RESET}")
    print(f"  Completed: {session.is_complete} in {session.turn_count} turns\n")


if __name__ == "__main__":
    run_demo()
    run_demo_direct_link()
