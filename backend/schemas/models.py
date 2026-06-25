"""Pydantic schemas for API request/response validation — V3 (Gemini Hybrid)."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ─── Request Models ────────────────────────────────────────────────────────────

class StartConversationRequest(BaseModel):
    customer_name: str
    amount_due: float
    bank_name: str
    payment_link: Optional[str] = "https://pay.example.com"


class ProcessResponseRequest(BaseModel):
    session_id: str
    user_text: str


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None


# ─── Response Models ───────────────────────────────────────────────────────────

class StartConversationResponse(BaseModel):
    session_id: str
    bot_response: str
    audio_url: str
    stage: str


class ProcessResponseResponse(BaseModel):
    bot_response: str
    audio_url: str
    stage: str
    is_complete: bool
    payment_link: Optional[str] = None
    # V2 intent tracking
    intent: Optional[str] = None
    confidence: Optional[float] = None
    # V3 Gemini hybrid debug field
    llm_provider: str = "rule_based"  # "gemini" | "rule_based" | "rule_based_fallback"


class SessionStateResponse(BaseModel):
    session_id: str
    stage: str
    customer_name: str
    amount_due: float
    bank_name: str
    payment_link: str
    is_complete: bool
    turn_count: int
    payment_link_sent: bool
    intents_detected: List[str]

    # V3.1 Phase 2 Memory Fields
    promised_date: Optional[str] = None
    promised_amount: Optional[float] = None
    callback_requested: bool = False
    payment_completed: bool = False
    post_call_summary: Optional[Dict[str, Any]] = None


# ─── V3.1 Call Summary Models ──────────────────────────────────────────────────

class PaymentCommitment(BaseModel):
    amount: Optional[float] = None
    promised_date: Optional[str] = None


class CallSummary(BaseModel):
    call_summary: str
    customer_intent: str
    payment_commitment: PaymentCommitment
    follow_up_required: bool
    follow_up_reason: Optional[str] = None
    call_outcome: str


class TranscribeResponse(BaseModel):
    transcript: str
    language: str
    confidence: Optional[float] = None


# ─── V2: Conversation Log Entry ────────────────────────────────────────────────

class ConversationLogEntry(BaseModel):
    timestamp: str
    stage_before: str
    stage_after: str
    user_message: str
    bot_response: str
    intent: str
    confidence: float


# ─── V2: Conversation Summary ──────────────────────────────────────────────────

class ConversationSummaryResponse(BaseModel):
    session_id: str
    customer_name: str
    amount_due: float
    bank_name: str
    current_stage: str
    is_complete: bool
    payment_link_sent: bool
    turn_count: int
    duration_seconds: float
    intents_detected: List[str]
    conversation_log: List[Dict[str, Any]]
