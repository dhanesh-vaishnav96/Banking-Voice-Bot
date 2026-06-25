import asyncio
from backend.services.conversation_engine import process_user_input, detect_intent
from backend.models.session import ConversationSession, STAGE_AWAITING_NAME_CONFIRMATION

def test_intent():
    texts = ["haan", "haan haan", "haan kar sakte ho", "haan tum mere se baat kar sakte ho"]
    
    for t in texts:
        intent, conf = detect_intent(t, STAGE_AWAITING_NAME_CONFIRMATION)
        print(f"'{t}' -> intent={intent}, conf={conf}")

if __name__ == "__main__":
    test_intent()
