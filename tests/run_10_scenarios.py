import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.session import create_session
from backend.services.conversation_engine import process_user_input, get_opening_message

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

scenarios = [
    {
        "name": "1. Happy path",
        "turns": ["Haan", "Haan bhej do"]
    },
    {
        "name": "2. Wrong person",
        "turns": ["Nahi main nahi hoon"]
    },
    {
        "name": "3. User asks bank name first",
        "turns": ["Aap konse bank se bol rahe ho?", "Haan", "Haan bhej do"]
    },
    {
        "name": "4. User asks amount first",
        "turns": ["Haan", "Kitna due hai?", "Haan bhej do"]
    },
    {
        "name": "5. User directly asks for payment link",
        "turns": ["Link bhej do"]
    },
    {
        "name": "6. User says call later",
        "turns": ["Haan", "Baad mein baat karein"]
    },
    {
        "name": "7. User says busy right now",
        "turns": ["Abhi busy hoon"]
    },
    {
        "name": "8. User says payment already done",
        "turns": ["Haan", "Payment kar diya hai"]
    },
    {
        "name": "9. User mixes Hindi and English",
        "turns": ["Haan", "I am busy right now hoon"]
    },
    {
        "name": "10. User gives unexpected response",
        "turns": ["What is the weather?", "Haan", "Haan bhej do"]
    }
]

for scenario in scenarios:
    print(f"\n{'='*50}")
    print(f"Scenario: {scenario['name']}")
    print(f"{'='*50}")
    s = create_session("Jitesh Soni", 5000, "ICICI Bank", "https://pay.example.com/jitesh")
    print(f"Bot: {get_opening_message(s)}")
    
    for turn in scenario["turns"]:
        print(f"User: {turn}")
        bot_resp, link, intent, conf = process_user_input(s, turn)
        print(f"Bot: {bot_resp}")
        if link:
            print(f"[Payment Link Sent: {link}]")
    print(f"[End Stage: {s.stage}]")
