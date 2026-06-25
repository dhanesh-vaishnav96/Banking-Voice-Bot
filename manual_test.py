"""
Fast manual test — no TTS waiting, uses timeout, shows stage transitions clearly.
"""
import requests
import json

BASE = "http://localhost:8000/api"
TIMEOUT = 30  # seconds per request

def start(name="Jitesh Soni", amount=15000, bank="SBI Bank", link="https://pay.sbi/abc123"):
    r = requests.post(f"{BASE}/start", json={
        "customer_name": name, "amount_due": amount,
        "bank_name": bank, "payment_link": link
    }, timeout=TIMEOUT)
    d = r.json()
    resp = d.get("bot_response", "")
    print(f"  [BOT] {resp[:100]}")
    print(f"        stage={d.get('stage')} complete={d.get('is_complete', False)}")
    return d["session_id"]

def respond(sid, text):
    r = requests.post(f"{BASE}/respond", json={"session_id": sid, "user_text": text}, timeout=TIMEOUT)
    d = r.json()
    resp = d.get("bot_response", "")
    print(f"  [YOU] {text}")
    print(f"  [BOT] {resp[:100]}")
    print(f"        intent={d.get('intent')} stage={d.get('stage')} complete={d.get('is_complete')} link={bool(d.get('payment_link'))}")
    return d

# ─────────────────────────────────────────
print("\n" + "="*70)
print("SCENARIO 1: HAPPY PATH")
print("="*70)
try:
    sid = start()
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
except Exception as e:
    print(f"  ERROR: {e}")

# ─────────────────────────────────────────
print("\n" + "="*70)
print("SCENARIO 2: WRONG PERSON")
print("="*70)
try:
    sid = start()
    respond(sid, "Nahi main Jitesh nahi hoon")
except Exception as e:
    print(f"  ERROR: {e}")

# ─────────────────────────────────────────
print("\n" + "="*70)
print("SCENARIO 3: ALREADY PAID")
print("="*70)
try:
    sid = start()
    respond(sid, "Maine payment kar diya")
except Exception as e:
    print(f"  ERROR: {e}")

# ─────────────────────────────────────────
print("\n" + "="*70)
print("SCENARIO 4: IMMEDIATE PAYMENT (YES at offer)")
print("="*70)
try:
    sid = start()
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan bhej do")
except Exception as e:
    print(f"  ERROR: {e}")

# ─────────────────────────────────────────
print("\n" + "="*70)
print("SCENARIO 5: PAYMENT TOMORROW")
print("="*70)
try:
    sid = start()
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "kal karunga")
except Exception as e:
    print(f"  ERROR: {e}")

# ─────────────────────────────────────────
print("\n" + "="*70)
print("SCENARIO 6: PARTIAL PAYMENT")
print("="*70)
try:
    sid = start()
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "Haan")
    respond(sid, "aadha payment de sakta hoon")
except Exception as e:
    print(f"  ERROR: {e}")

print("\nDone.")
