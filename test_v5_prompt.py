import requests, time

BASE = 'http://127.0.0.1:8000/api'
CUSTOMER = {'customer_name': 'Jitesh Soni', 'amount_due': 5000, 'bank_name': 'ICICI Bank', 'payment_link': 'https://pay.icici.com/jitesh'}

scenarios = [
    {"name": "1. Direct Confirm & Pay", "turns": ["Haan", "Haan boliye", "Thik hai, bhej do"]},
    {"name": "2. Question Handling (Bank)", "turns": ["Ji haan", "Aap kaun bol rahe ho?", "Haan boliye", "Thik hai link bhej do"]},
    {"name": "3. Question Handling (Amount)", "turns": ["Haan main hi hoon", "Haan boliye", "Kitna amount hai?", "Kal kar dunga"]},
    {"name": "4. No Money Pushback", "turns": ["Ji bol raha hoon", "Haan 2 minute hain", "Mere paas paise nahi hain", "Agle hafte arrange honge", "Thik hai"]},
    {"name": "5. Angry Customer Calm Down", "turns": ["Kya hai bhai?", "Mere paas time nahi hai abhi", "Baad me call karna"]},
    {"name": "6. Unrelated Question", "turns": ["Haan Jitesh bol raha hoon", "Haan boliye", "Kya bank aaj open hai?", "Thik hai link dedo"]},
    {"name": "7. Already Paid", "turns": ["Haan", "Haan bolo", "Maine kal hi payment kar diya tha"]},
    {"name": "8. Delay Promise", "turns": ["Haan ji", "Boliye", "Abhi thoda busy hoon, shaam ko karunga"]},
    {"name": "9. Supervisor Request", "turns": ["Haan", "Kya hai?", "Mujhe manager se baat karni hai"]},
    {"name": "10. Alternate Greeting Flow", "turns": ["Hello", "Ji boliye", "Paise nahi hain abhi", "Do din baad"]},
]

print("=== V5 Prompt Quality Test (10 Conversations) ===")

for i, scenario in enumerate(scenarios):
    print(f"\\n--- Scenario {scenario['name']} ---")
    r = requests.post(f'{BASE}/start', json=CUSTOMER, timeout=10)
    if r.status_code != 200:
        print("Failed to start session:", r.text)
        continue
    
    sid = r.json()['session_id']
    bot_intro = r.json()['bot_response']
    print(f"Bot : {bot_intro}")
    
    for turn in scenario['turns']:
        print(f"User: {turn}")
        t = time.time()
        r = requests.post(f'{BASE}/respond', json={'session_id': sid, 'user_text': turn}, timeout=20)
        resp = r.json()
        print(f"Bot : {resp['bot_response']} [intent: {resp['intent']}, stage: {resp['stage']}]")
        if resp['is_complete']:
            break
    time.sleep(1) # Breathe
