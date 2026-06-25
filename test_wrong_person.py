import requests
import time

URL_START = "http://localhost:8000/api/start"
URL_RESPOND = "http://localhost:8000/api/respond"

test_inputs = [
    "Nahi",
    "Wrong number",
    "Galat number",
    "Main Jitesh nahi hoon",
    "Wrong person",
    "Aapne galat number lagaya hai",
]

for idx, user_input in enumerate(test_inputs):
    print(f"\n--- Test {idx+1}: {user_input} ---")
    start_resp = requests.post(URL_START, json={
        "customer_name": "Jitesh Soni",
        "amount_due": 5000,
        "bank_name": "HDFC Bank",
        "payment_link": "https://example.com/pay"
    }).json()
    
    session_id = start_resp["session_id"]
    print(f"Bot: {start_resp['bot_response']}")
    print(f"User: {user_input}")
    
    t0 = time.time()
    resp = requests.post(URL_RESPOND, json={
        "session_id": session_id,
        "user_text": user_input
    }).json()
    t1 = time.time()
    
    print(f"Bot: {resp.get('bot_response')}")
    print(f"Stage: {resp.get('stage')}")
    print(f"Is Complete: {resp.get('is_complete')}")
    print(f"LLM Provider: {resp.get('llm_provider')}")
    print(f"Latency: {round(t1-t0, 2)}s")
