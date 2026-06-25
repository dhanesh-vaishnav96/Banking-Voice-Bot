"""API routes for the Hindi Voice Collection Bot — V4 (Multi-Provider: Groq → Gemini → Rules)."""

import logging
import time
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse

from backend.schemas.models import (
    StartConversationRequest,
    StartConversationResponse,
    ProcessResponseRequest,
    ProcessResponseResponse,
    SessionStateResponse,
    TranscribeResponse,
    TTSRequest,
    ConversationSummaryResponse,
)
from backend.models.session import (
    create_session,
    get_session,
    STAGE_AWAITING_NAME_CONFIRMATION,
    STAGE_AMOUNT_DUE_INFORMATION,
    STAGE_BANK_INFORMATION,
    STAGE_PAYMENT_OFFER,
    STAGE_CONVERSATION_COMPLETED,
    STAGE_WRONG_PERSON,
)
from backend.services.conversation_engine import (
    get_opening_message,
    process_user_input,
)
from backend.services.intent_classifier import classify_intent
from backend.services.groq_service import (
    get_groq_response,
    GroqUnavailableError,
)
from backend.services.gemini_service import (
    get_gemini_response,
    GeminiUnavailableError,
    generate_call_summary as gemini_generate_summary,
)
from backend.services.tts import synthesize, get_available_voices
from backend.services.stt import transcribe_audio, is_whisper_available
from backend.config import (
    AUDIO_DIR,
    GEMINI_ENABLED,
    GROQ_ENABLED,
    LLM_PROVIDER,
    GEMINI_FALLBACK_TO_RULES,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["conversation"])


# ─────────────────────────────────────────────────────────────────────────────
# Stage Advancement Logic (backend owns state, NOT Gemini)
# ─────────────────────────────────────────────────────────────────────────────

def _advance_stage_from_intent(session, intent: str, end_call: bool, send_link: bool):
    """
    Given the detected intent and Gemini metadata flags, advance
    the session stage. The backend is always the authority on state.
    """
    stage = session.stage

    if intent in ("deny", "wrong_person") or (stage == STAGE_AWAITING_NAME_CONFIRMATION and intent == "deny"):
        session.advance_to(STAGE_WRONG_PERSON)

    elif intent == "already_paid":
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif intent == "busy_interrupt":
        session.payment_link_sent = True
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif intent in ("link_request", "payment_accept", "partial_payment", "delay_promise") or (
        send_link and stage != STAGE_AWAITING_NAME_CONFIRMATION
    ):
        session.payment_link_sent = True
        session.advance_to(STAGE_CONVERSATION_COMPLETED)

    elif intent in ("payment_decline", "refusal_to_pay", "supervisor_request"):
        session.advance_to(STAGE_CONVERSATION_COMPLETED)
        
    elif intent == "angry_customer":
        pass # Let the prompt de-escalate without ending the call immediately

    elif intent == "confirm" and stage == STAGE_AWAITING_NAME_CONFIRMATION:
        session.advance_to(STAGE_AMOUNT_DUE_INFORMATION)

    elif stage == STAGE_AMOUNT_DUE_INFORMATION and intent not in ("who_are_you", "bank_query", "amount_query"):
        # Any substantive reply after amount info → move to bank stage
        session.advance_to(STAGE_BANK_INFORMATION)

    elif stage == STAGE_BANK_INFORMATION and intent not in ("who_are_you", "bank_query", "amount_query"):
        session.advance_to(STAGE_PAYMENT_OFFER)

    elif end_call:
        session.advance_to(STAGE_CONVERSATION_COMPLETED)


def _log_turn(session, user_text: str, bot_response: str, intent: str,
              confidence: float, stage_before: str, llm_provider: str):
    """Append a structured entry to session.conversation_log."""
    import datetime
    session.conversation_log.append({
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "stage_before": stage_before,
        "stage_after": session.stage,
        "user_message": user_text,
        "bot_response": bot_response,
        "intent": intent,
        "confidence": round(confidence, 3),
        "llm_provider": llm_provider,
    })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/start — Begin a new conversation session
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=StartConversationResponse)
async def start_conversation(request: StartConversationRequest):
    """
    Start a new conversation session.
    Opening greeting is hardcoded (no LLM call) for fast first response.
    """
    if not request.customer_name.strip():
        raise HTTPException(status_code=400, detail="customer_name cannot be empty")
    if request.amount_due <= 0:
        raise HTTPException(status_code=400, detail="amount_due must be positive")
    if not request.bank_name.strip():
        raise HTTPException(status_code=400, detail="bank_name cannot be empty")

    payment_link = request.payment_link or "https://pay.example.com"

    session = create_session(
        customer_name=request.customer_name.strip(),
        amount_due=request.amount_due,
        bank_name=request.bank_name.strip(),
        payment_link=payment_link,
    )

    opening_message = get_opening_message(session)
    session.add_to_history("bot", opening_message)
    session.add_gemini_turn("bot", opening_message)

    # TTS
    audio_url = ""
    try:
        audio_path = await synthesize(opening_message, audio_dir=AUDIO_DIR)
        audio_url = f"/audio/{audio_path.name}"
    except Exception as e:
        logger.error(f"TTS failed: {e}")

    active_provider = LLM_PROVIDER if (GROQ_ENABLED or GEMINI_ENABLED) else "rule_based"
    logger.info(
        f"Session {session.session_id} started for {session.customer_name} "
        f"| primary_provider={active_provider}"
    )

    return StartConversationResponse(
        session_id=session.session_id,
        bot_response=opening_message,
        audio_url=audio_url,
        stage=session.stage,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/respond — Multi-Provider Cascade: Groq → Gemini → Rule Engine
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/respond", response_model=ProcessResponseResponse)
async def process_response(request: ProcessResponseRequest):
    """
    Process a user response using a 3-stage LLM cascade:
      1. Groq (llama-3.3-70b-versatile) — Primary
      2. Gemini (gemini-2.0-flash)       — Secondary fallback
      3. Rule-Based Engine               — Final safety net

    Detailed logging per turn:
      user_text, classifier_intent, llm_intent, stage, llm_provider, response_time_ms
    """
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found or expired."
        )

    if session.is_complete:
        raise HTTPException(
            status_code=400,
            detail="This conversation has already been completed."
        )

    user_text = request.user_text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="user_text cannot be empty")

    stage_before = session.stage
    t_start = time.time()

    # ── Step 1: Lightweight intent classification (always runs) ────────────────
    classifier_intent, classifier_confidence = classify_intent(user_text, stage_before)
    logger.info(
        f"Session {session.session_id} | Stage: {stage_before} | "
        f"User: '{user_text[:50]}' | ClassifierIntent: {classifier_intent} ({classifier_confidence:.2f})"
    )

    # ── Step 2: Multi-provider LLM cascade ────────────────────────────────────────
    bot_response: str = ""
    payment_link_to_send: str | None = None
    intent: str = classifier_intent
    confidence: float = classifier_confidence
    llm_provider: str = "rule_based"
    llm_result = None

    # ── 2a. Try Groq (Primary) ─────────────────────────────────────────────────────
    if GROQ_ENABLED and LLM_PROVIDER in ("groq",):
        try:
            llm_result = await get_groq_response(
                session=session,
                user_text=user_text,
                intent_hint=classifier_intent,
            )
            llm_provider = "groq"
        except GroqUnavailableError as e:
            logger.warning(
                f"Session {session.session_id} | Groq unavailable ({e}). "
                f"Cascading to Gemini..."
            )

    # ── 2b. Try Gemini (Secondary Fallback) ──────────────────────────────────
    if llm_result is None and GEMINI_ENABLED:
        try:
            llm_result = await get_gemini_response(
                session=session,
                user_text=user_text,
                intent_hint=classifier_intent,
            )
            llm_provider = "gemini_fallback"
        except GeminiUnavailableError as e:
            logger.warning(
                f"Session {session.session_id} | Gemini unavailable ({e}). "
                f"Cascading to rule-based engine."
            )

    # ── 2c. Apply LLM result (if either provider succeeded) ────────────────────
    if llm_result is not None:
        bot_response = llm_result.response
        llm_intent = llm_result.intent
        intent = llm_intent if llm_intent != "unclear" else classifier_intent
        confidence = 1.0

        _advance_stage_from_intent(
            session,
            intent=intent,
            end_call=llm_result.end_call,
            send_link=llm_result.send_payment_link,
        )

        # Save extracted entities to session memory
        if llm_result.promised_date:
            session.promised_date = llm_result.promised_date
        if llm_result.promised_amount:
            session.promised_amount = float(llm_result.promised_amount)
        if llm_result.callback_requested:
            session.callback_requested = True
        if intent == "already_paid":
            session.payment_completed = True

        if llm_result.send_payment_link:
            payment_link_to_send = session.payment_link

        elapsed_ms = llm_result.response_time_ms
        logger.info(
            f"Session {session.session_id} | {llm_provider.upper()} | "
            f"ClassifierHint={classifier_intent} | Intent={intent} | "
            f"Stage→{session.stage} | {elapsed_ms}ms"
        )

    # ── Step 3: Rule-based final fallback ───────────────────────────────────────
    if not bot_response:
        rb_response, rb_link, rb_intent, rb_conf = process_user_input(session, user_text)
        bot_response = rb_response
        intent = rb_intent
        confidence = rb_conf
        llm_provider = "rule_based_fallback"
        if rb_link:
            payment_link_to_send = rb_link

    # ── Step 4: Update session history ────────────────────────────────────────
    session.add_to_history("user", user_text)
    session.add_to_history("bot", bot_response)
    session.add_gemini_turn("user", user_text)
    session.add_gemini_turn("bot", bot_response)
    session.record_intent(intent)

    if payment_link_to_send:
        session.payment_link_sent = True

    _log_turn(session, user_text, bot_response, intent, confidence, stage_before, llm_provider)

    elapsed_total_ms = int((time.time() - t_start) * 1000)
    logger.info(
        f"Session {session.session_id} | DONE | "
        f"intent={intent} | stage={session.stage} | "
        f"provider={llm_provider} | total={elapsed_total_ms}ms"
    )

    # ── Step 4.5: Post-call summary (async, fire-and-forget) ──────────────────
    if session.is_complete and not session.post_call_summary:
        import asyncio
        from backend.services.groq_service import generate_call_summary as groq_summary

        async def background_summary():
            # Prefer Groq for summary; fall back to Gemini
            try:
                summary = await groq_summary(session)
                session.post_call_summary = summary
                logger.info(f"Session {session.session_id} | Post-Call Summary generated (groq).")
            except Exception as e1:
                logger.warning(f"Groq summary failed ({e1}), trying Gemini...")
                try:
                    summary = await gemini_generate_summary(session)
                    session.post_call_summary = summary
                    logger.info(f"Session {session.session_id} | Post-Call Summary generated (gemini_fallback).")
                except Exception as e2:
                    logger.error(f"Both summary providers failed for {session.session_id}: {e2}")

        # Fire and forget
        asyncio.create_task(background_summary())


    # ── Step 5: TTS ──────────────────────────────────────────────────────────
    audio_url = ""
    try:
        audio_path = await synthesize(bot_response, audio_dir=AUDIO_DIR)
        audio_url = f"/audio/{audio_path.name}"
    except Exception as e:
        logger.error(f"TTS failed: {e}")

    return ProcessResponseResponse(
        bot_response=bot_response,
        audio_url=audio_url,
        stage=session.stage,
        is_complete=session.is_complete,
        payment_link=payment_link_to_send,
        intent=intent,
        confidence=confidence,
        llm_provider=llm_provider,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/session/{session_id}/summary — Conversation summary
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/session/{session_id}/summary", response_model=ConversationSummaryResponse)
async def get_conversation_summary(session_id: str):
    """Get a structured summary of the entire conversation session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return ConversationSummaryResponse(
        session_id=session.session_id,
        customer_name=session.customer_name,
        amount_due=session.amount_due,
        bank_name=session.bank_name,
        current_stage=session.stage,
        is_complete=session.is_complete,
        payment_link_sent=session.payment_link_sent,
        turn_count=session.turn_count,
        duration_seconds=session.duration_seconds,
        intents_detected=session.intents_detected,
        conversation_log=session.conversation_log,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/session/{session_id} — Get session state
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str):
    """Get current state of a conversation session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStateResponse(
        session_id=session.session_id,
        stage=session.stage,
        customer_name=session.customer_name,
        amount_due=session.amount_due,
        bank_name=session.bank_name,
        payment_link=session.payment_link,
        is_complete=session.is_complete,
        turn_count=session.turn_count,
        payment_link_sent=session.payment_link_sent,
        intents_detected=session.intents_detected,
        promised_date=session.promised_date,
        promised_amount=session.promised_amount,
        callback_requested=session.callback_requested,
        payment_completed=session.payment_completed,
        post_call_summary=session.post_call_summary,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/transcribe — Optional Faster-Whisper STT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Query("hi", description="Language code"),
):
    """Transcribe uploaded audio using Faster-Whisper (optional backend STT)."""
    if not is_whisper_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Faster-Whisper is not installed. "
                "Use browser Web Speech API for STT."
            ),
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    content_type = audio.content_type or "audio/webm"
    fmt_map = {
        "audio/webm": "webm", "audio/wav": "wav",
        "audio/mpeg": "mp3",  "audio/ogg": "ogg", "audio/mp4": "mp4",
    }
    audio_format = fmt_map.get(content_type, "webm")

    try:
        transcript, confidence = await transcribe_audio(
            audio_bytes, audio_format=audio_format, language=language
        )
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

    return TranscribeResponse(
        transcript=transcript, language=language, confidence=confidence
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/tts — Standalone TTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert any text to Hindi speech and return audio URL."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")
    try:
        audio_path = await synthesize(
            request.text, audio_dir=AUDIO_DIR, voice=request.voice
        )
        return {"audio_url": f"/audio/{audio_path.name}"}
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/voices — List voices
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/voices")
async def list_voices():
    return {"voices": get_available_voices()}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/health — Health check
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    from backend.config import GEMINI_API_KEY, GEMINI_MODEL
    return {
        "status": "ok",
        "version": "3.0.0",
        "tts_provider": "edge_tts",
        "stt_primary": "browser_web_speech_api",
        "llm_provider": "gemini" if GEMINI_ENABLED else "rule_based",
        "gemini_model": GEMINI_MODEL if GEMINI_ENABLED else None,
        "gemini_key_set": bool(GEMINI_API_KEY),
        "fallback_enabled": GEMINI_FALLBACK_TO_RULES,
        "features": [
            "gemini_hybrid_engine",
            "rule_based_fallback",
            "intent_classification",
            "response_validation",
            "conversation_history",
            "summary_endpoint",
        ],
    }
