"""
Finite State Machine Validation Layer
Forces strict sequential progression for the Voice Collection Bot.
"""

from typing import Tuple, Optional
from backend.models.session import (
    STAGE_IDENTITY_CONFIRMATION,
    STAGE_INTRODUCTION,
    STAGE_BANK_INFORMATION,
    STAGE_AMOUNT_INFORMATION,
    STAGE_PAYMENT_OFFER,
    STAGE_PAYMENT_LINK,
    STAGE_CONVERSATION_COMPLETED,
    STAGE_WRONG_PERSON,
    ConversationSession
)

def get_next_stage_and_response(current_stage: str, intent: str, session: ConversationSession) -> Tuple[str, Optional[str], bool]:
    """
    Returns (next_stage, hardcoded_response, end_call).
    If hardcoded_response is None, it means the LLM should generate the speech for the next_stage.
    """
    # ── 1. Handle Terminal Cross-Cutting Intents ──
    if intent == "wrong_person":
        msg = f"Maaf kijiye. Mujhe {session.customer_name} ji se baat karni thi. Dhanyavaad. Namaste."
        return STAGE_WRONG_PERSON, msg, True

    if intent == "already_paid":
        msg = "Bahut achhi baat hai. Payment update hone me thoda samay lag sakta hai. Dhanyavaad."
        return STAGE_CONVERSATION_COMPLETED, msg, True

    if intent in ("angry_customer", "supervisor_request"):
        msg = "Theek hai, main aapki baat supervisor se kara deta hoon. Dhanyavaad."
        return STAGE_CONVERSATION_COMPLETED, msg, True

    # ── 2. Handle Strict Forward Sequential Flow ──
    
    if current_stage == STAGE_IDENTITY_CONFIRMATION:
        if intent == "yes":
            return STAGE_INTRODUCTION, None, False
        if intent == "no":
            msg = f"Maaf kijiye. Mujhe {session.customer_name} ji se baat karni thi. Dhanyavaad. Namaste."
            return STAGE_WRONG_PERSON, msg, True
        # If unclear, just repeat
        return STAGE_IDENTITY_CONFIRMATION, None, False

    if current_stage == STAGE_INTRODUCTION:
        # Move immediately to Bank info after introduction regardless of intent
        return STAGE_BANK_INFORMATION, None, False

    if current_stage == STAGE_BANK_INFORMATION:
        if intent == "no":
            msg = "Theek hai, dhanyavaad. Namaste."
            return STAGE_CONVERSATION_COMPLETED, msg, True
        # User agreed to talk or just acknowledged, proceed to amount
        return STAGE_AMOUNT_INFORMATION, None, False

    if current_stage == STAGE_AMOUNT_INFORMATION:
        # After stating amount, proceed to offer
        return STAGE_PAYMENT_OFFER, None, False

    if current_stage == STAGE_PAYMENT_OFFER:
        if intent == "yes":
            # Bug fixes 1, 3, 6: Directly generate payment link and end
            msg = f"Bilkul. Main payment link share kar raha hoon. Aap isi link ka use karke payment complete kar sakte hain. {session.payment_link}"
            return STAGE_PAYMENT_LINK, msg, True
        
        if intent == "delay" or intent == "partial_payment":
            # Only here do we ask for the expected date (or let LLM ask)
            # Actually, the user says "End Conversation" or ask expected date.
            # "If NO → Ask expected payment date → End Conversation"
            msg = "Theek hai. Aap kab tak payment kar paayenge? Please date confirm karein taaki main update kar doon."
            return STAGE_CONVERSATION_COMPLETED, msg, True
            
        if intent == "no":
            msg = "Theek hai, main system mein update kar deta hoon. Dhanyavaad."
            return STAGE_CONVERSATION_COMPLETED, msg, True
            
        # Default for unclear intent at offer
        msg = "Kya aap abhi payment kar sakte hain?"
        return STAGE_PAYMENT_OFFER, msg, False
        
    if current_stage == STAGE_PAYMENT_LINK:
        return STAGE_CONVERSATION_COMPLETED, "Payment link bhej diya gaya hai. Dhanyavaad.", True

    return STAGE_CONVERSATION_COMPLETED, "Dhanyavaad.", True
