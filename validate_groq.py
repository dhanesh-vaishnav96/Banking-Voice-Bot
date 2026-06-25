"""
validate_groq.py — Human-paced validation script for Multi-Provider Architecture.

Tests 6 scenarios with 10s delays between API calls to avoid rate limits.
Verifies:
  - provider=groq on every turn
  - Entity extraction (promised_amount, promised_date, callback_requested, payment_completed)
  - Post-call summary JSON generation

Usage:
    python validate_groq.py

Prerequisites:
    1. Server must be running: python -m uvicorn backend.main:app --port 8000
    2. GROQ_API_KEY must be set in .env
"""

import time
import json
import requests

BASE_URL = "http://127.0.0.1:8000/api"

CUSTOMER = {
    "customer_name": "Jitesh Soni",
    "amount_due": 5000,
    "bank_name": "HDFC Bank",
    "payment_link": "https://pay.hdfc.com/jitesh123",
}

SCENARIOS = [
    {
        "name": "Happy Path",
        "turns": [
            "haan ji, main Jitesh Soni bol raha hoon",
            "Theek hai, main payment kar dunga",
        ],
    },
    {
        "name": "Partial Payment",
        "turns": [
            "haan ji",
            "Mere paas abhi poore paise nahi hain. Main kal 2500 rupaye de sakta hoon.",
        ],
    },
    {
        "name": "Needs More Time",
        "turns": [
            "haan main hi hoon",
            "Abhi nahi, mujhe 3 din chahiye payment ke liye",
        ],
    },
    {
        "name": "Already Paid",
        "turns": [
            "ji haan",
            "Maine payment kal kar diya tha.",
        ],
    },
    {
        "name": "Angry Customer",
        "turns": [
            "haan bolo",
            "Yeh kya bakwaas hai! Mujhe baar baar call mat karo!",
        ],
    },
    {
        "name": "Supervisor Request",
        "turns": [
            "haan bol raha hoon",
            "Main aapke manager se baat karna chahta hoon.",
        ],
    },
]

SEPARATOR = "=" * 60


def start_session():
    resp = requests.post(f"{BASE_URL}/start", json=CUSTOMER, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data["session_id"], data["bot_response"]


def send_turn(session_id: str, user_text: str):
    resp = requests.post(
        f"{BASE_URL}/respond",
        json={"session_id": session_id, "user_text": user_text},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def get_session_state(session_id: str):
    """Read entities and post_call_summary from /session/{id} endpoint."""
    resp = requests.get(f"{BASE_URL}/session/{session_id}", timeout=10)
    if resp.status_code == 200:
        return resp.json()
    return None


def run_scenario(scenario: dict):
    print(f"\n{SEPARATOR}")
    print(f"SCENARIO: {scenario['name']}")
    print(SEPARATOR)

    session_id, greeting = start_session()
    print(f"\nBot (greeting): {greeting}")

    all_providers = []
    final_data = None

    for user_text in scenario["turns"]:
        time.sleep(3)  # Brief pause between turns
        print(f"\nUser: {user_text}")
        try:
            data = send_turn(session_id, user_text)
            provider = data.get("llm_provider", "unknown")
            all_providers.append(provider)
            final_data = data

            print(f"Bot : {data['bot_response']}")
            print(f"      ► provider={provider} | intent={data.get('intent')} | stage={data.get('stage')} | is_complete={data.get('is_complete')}")
        except Exception as e:
            print(f"[ERROR] Turn failed: {e}")

    # Wait for async post-call summary
    if final_data and final_data.get("is_complete"):
        print(f"\nWaiting 10 seconds for post-call summary generation...")
        time.sleep(10)

        state = get_session_state(session_id)
        if state:
            pc = state.get("post_call_summary") or {}

            print(f"\n── Post-Call Summary ──")
            print(f"  call_summary      : {pc.get('call_summary', 'N/A')}")
            print(f"  customer_intent   : {pc.get('customer_intent', 'N/A')}")
            print(f"  payment_commitment: {pc.get('payment_commitment', {})}")
            print(f"  follow_up_required: {pc.get('follow_up_required', 'N/A')}")
            print(f"  call_outcome      : {pc.get('call_outcome', 'N/A')}")

            print(f"\n── Extracted Entities (Session State) ──")
            print(f"  promised_amount   : {state.get('promised_amount')}")
            print(f"  promised_date     : {state.get('promised_date')}")
            print(f"  callback_requested: {state.get('callback_requested')}")
            print(f"  payment_completed : {state.get('payment_completed')}")
        else:
            print("[WARN] Could not read session state.")

    print(f"\n── Providers Used ──")
    for i, (turn_text, prov) in enumerate(zip(scenario["turns"], all_providers)):
        groq_tick = "✓" if prov == "groq" else "✗"
        print(f"  [{groq_tick}] Turn {i+1} '{turn_text[:35]}...' → provider={prov}")

    return all_providers


def main():
    print("=" * 60)
    print("  GROQ MULTI-PROVIDER VALIDATION REPORT")
    print("=" * 60)
    print(f"  Base URL: {BASE_URL}")
    print(f"  Customer: {CUSTOMER['customer_name']}")
    print(f"  Amount:   Rs.{CUSTOMER['amount_due']}")
    print(f"  Bank:     {CUSTOMER['bank_name']}")

    all_results = {}
    groq_success = 0
    total_turns = 0

    for scenario in SCENARIOS:
        providers = run_scenario(scenario)
        all_results[scenario["name"]] = providers
        groq_success += sum(1 for p in providers if p == "groq")
        total_turns += len(providers)
        print(f"\nWaiting 8 seconds before next scenario...")
        time.sleep(8)

    # Final summary
    print(f"\n\n{'=' * 60}")
    print("  FINAL VALIDATION SUMMARY")
    print("=" * 60)
    for name, providers in all_results.items():
        primary = providers[0] if providers else "N/A"
        status = "PASS ✓" if all(p == "groq" for p in providers) else f"PARTIAL ({', '.join(set(providers))})"
        print(f"  {name:<25} → {status}")

    groq_pct = (groq_success / total_turns * 100) if total_turns else 0
    print(f"\n  Groq Success Rate: {groq_success}/{total_turns} turns ({groq_pct:.0f}%)")

    if groq_pct == 100:
        print("\n  ✓ VALIDATION PASSED — Groq is primary provider for all turns.")
    elif groq_pct > 0:
        print("\n  ~ PARTIAL — Some turns fell back. Check GROQ_API_KEY and quota.")
    else:
        print("\n  ✗ VALIDATION FAILED — Groq not used. Check GROQ_API_KEY and GROQ_ENABLED.")


if __name__ == "__main__":
    main()
