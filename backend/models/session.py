"""In-memory session store for conversation state management — V3 (Gemini Hybrid)."""

import uuid
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field


STAGE_IDENTITY_CONFIRMATION = "identity_confirmation"
STAGE_INTRODUCTION           = "introduction"
STAGE_BANK_INFORMATION       = "bank_information"
STAGE_AMOUNT_INFORMATION     = "amount_information"
STAGE_PAYMENT_OFFER          = "payment_offer"
STAGE_PAYMENT_LINK           = "payment_link"
STAGE_CONVERSATION_COMPLETED = "conversation_completed"
STAGE_WRONG_PERSON           = "wrong_person"

ALL_STAGES = [
    STAGE_IDENTITY_CONFIRMATION,
    STAGE_INTRODUCTION,
    STAGE_BANK_INFORMATION,
    STAGE_AMOUNT_INFORMATION,
    STAGE_PAYMENT_OFFER,
    STAGE_PAYMENT_LINK,
    STAGE_CONVERSATION_COMPLETED,
    STAGE_WRONG_PERSON,
]


@dataclass
class ConversationSession:
    session_id: str
    customer_name: str
    amount_due: float
    bank_name: str
    payment_link: str
    stage: str = STAGE_IDENTITY_CONFIRMATION
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turn_count: int = 0

    # V1 history (role + text) — used for summary endpoint
    history: list = field(default_factory=list)

    # V2 structured conversation log (timestamp, intent, confidence, etc.)
    conversation_log: List[Dict[str, Any]] = field(default_factory=list)

    # V2 tracking: which intents were detected across the session
    intents_detected: List[str] = field(default_factory=list)

    # V2 tracking: was payment link sent?
    payment_link_sent: bool = False

    # V3: Gemini multi-turn history (in-memory, not persisted)
    gemini_history: List[Dict] = field(default_factory=list)

    # V3.1: Phase 2 Entity Extraction & Memory
    promised_date: Optional[str] = None
    promised_amount: Optional[float] = None
    callback_requested: bool = False
    payment_completed: bool = False
    
    # V3.1: Post-call summary JSON
    post_call_summary: Optional[Dict[str, Any]] = None

    @property
    def is_complete(self) -> bool:
        return self.stage in (STAGE_CONVERSATION_COMPLETED, STAGE_WRONG_PERSON)

    @property
    def duration_seconds(self) -> float:
        return round(self.updated_at - self.created_at, 1)

    def advance_to(self, stage: str):
        self.stage = stage
        self.updated_at = time.time()
        self.turn_count += 1

    def add_to_history(self, role: str, text: str):
        self.history.append({
            "role": role,
            "text": text,
            "timestamp": time.time(),
        })

    def add_gemini_turn(self, role: str, text: str):
        """
        Append a turn in Gemini's multi-turn format.
        role: 'user' | 'bot'
        """
        gemini_role = "model" if role == "bot" else "user"
        self.gemini_history.append({
            "role": gemini_role,
            "parts": [{"text": text}],
        })

    def get_recent_history(self, n: int = 10) -> List[Dict]:
        """Return last n Gemini-format turns for the context window."""
        return self.gemini_history[-n:]

    def record_intent(self, intent: str):
        """Track unique intents detected during the session."""
        if intent not in self.intents_detected:
            self.intents_detected.append(intent)


# ─── Session Store ─────────────────────────────────────────────────────────────
_sessions: Dict[str, ConversationSession] = {}


def create_session(
    customer_name: str,
    amount_due: float,
    bank_name: str,
    payment_link: str,
) -> ConversationSession:
    session_id = str(uuid.uuid4())[:8].upper()
    session = ConversationSession(
        session_id=session_id,
        customer_name=customer_name,
        amount_due=amount_due,
        bank_name=bank_name,
        payment_link=payment_link,
    )
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Optional[ConversationSession]:
    return _sessions.get(session_id)


def delete_session(session_id: str):
    _sessions.pop(session_id, None)


def list_sessions() -> Dict[str, ConversationSession]:
    return dict(_sessions)
