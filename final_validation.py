import asyncio
from backend.utils import number_to_hindi_words
from backend.services.conversation_engine import process_user_input
from backend.models.session import ConversationSession

def test_numbers():
    print("Testing Numbers:")
    amounts = [5000, 15000, 2500, 100000]
    for a in amounts:
        print(f"{a} -> {number_to_hindi_words(a)}")
    print("-" * 30)

def test_scenario(name, user_messages):
    print(f"Scenario: {name}")
    session = ConversationSession(
        session_id="test1",
        customer_name="Jitesh Soni",
        amount_due=5000,
        bank_name="ICICI Bank",
        payment_link="http://pay.me/123"
    )
    # Start
    msg, link, intent, conf = process_user_input(session, "")
    print(f"Bot (Start): {msg}")
    
    for user_msg in user_messages:
        print(f"User: {user_msg}")
        msg, link, intent, conf = process_user_input(session, user_msg)
        print(f"Bot: {msg}")
    print("-" * 30)

def main():
    test_numbers()
    
    scenarios = {
        "Happy Path": ["Haan", "Haan bhej do"],
        "Bank Query": ["Aap kis bank se bol rahe ho?", "Theek hai payment link bhej do"],
        "Amount Query": ["Mera kitna amount baaki hai?", "Theek hai main de dunga"],
        "Busy User": ["Main abhi busy hoon", "Call me tomorrow"],
        "Payment Done": ["Mera payment ho gaya hai"]
    }
    
    for name, msgs in scenarios.items():
        test_scenario(name, msgs)

if __name__ == "__main__":
    main()
