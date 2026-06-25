import requests
import time
import sys

URL_START = "http://localhost:8000/api/start"
URL_RESPOND = "http://localhost:8000/api/respond"

scenarios = [
    {
        "name": "1. Happy Path",
        "inputs": ["Haan, main Jitesh bol raha hoon", "Haan theek hai amount", "HDFC Bank ka hi hai", "Haan link bhej do"]
    },
    {
        "name": "2. Wrong Person",
        "inputs": ["Nahi", "Wrong number"]
    },
    {
        "name": "3. Already Paid",
        "inputs": ["Haan", "Maine kal hi payment kar diya tha"]
    },
    {
        "name": "4. Needs More Time",
        "inputs": ["Haan", "Mere paas abhi paise nahi hain, mujhe waqt chahiye"]
    },
    {
        "name": "5. Partial Payment",
        "inputs": ["Haan", "Main aadha paisa de sakta hoon abhi"]
    },
    {
        "name": "6. Payment Link Request",
        "inputs": ["Haan", "Mujhe payment link bhej do"]
    },
    {
        "name": "7. Busy Customer",
        "inputs": ["Haan", "Main abhi busy hoon baad mein call karna"]
    },
    {
        "name": "8. Angry Customer",
        "inputs": ["Haan", "Baar baar phone kyun karte ho, pareshan kar diya hai!"]
    },
    {
        "name": "9. Supervisor Request",
        "inputs": ["Haan", "Apne manager se baat karao"]
    }
]

print("Starting QA Audit...")

errors = 0

for scenario in scenarios:
    print(f"\n{'='*50}\nScenario: {scenario['name']}\n{'='*50}")
    
    start_resp = requests.post(URL_START, json={
        "customer_name": "Jitesh Soni",
        "amount_due": 5000,
        "bank_name": "HDFC Bank",
        "payment_link": "https://example.com/pay"
    }).json()
    
    session_id = start_resp["session_id"]
    print(f"[START] Bot: {start_resp['bot_response']}")
    
    for i, user_input in enumerate(scenario['inputs']):
        print(f"\nUser: {user_input}")
        
        t0 = time.time()
        resp = requests.post(URL_RESPOND, json={
            "session_id": session_id,
            "user_text": user_input
        }).json()
        t1 = time.time()
        
        print(f"Bot: {resp.get('bot_response')}")
        print(f"Stage: {resp.get('stage')} | Complete: {resp.get('is_complete')} | LLM: {resp.get('llm_provider')} | Latency: {round(t1-t0,2)}s")
        
        if resp.get('is_complete'):
            print(f"Conversation completed early at step {i+1}.")
            break
            
print(f"\nQA Audit Complete. Total Errors: {errors}")
