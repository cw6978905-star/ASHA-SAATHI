"""Module 7: FastAPI Integration Layer for Person A (Gnani Voice Pipeline) and Person C (Frontend/Storage)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from brain.correction import CorrectionEngine
from brain.danger_detector import DangerDetector
from brain.extraction import ExtractionEngine
from brain.guardrails import MedicalGuardrails
from brain.languages import (
    SUPPORTED_GNANI_LANGUAGES,
    get_tts_locale,
    normalize_language_code,
)
from brain.llm_client import BaseLLMClient, create_llm_client
from brain.state_manager import FormStateManager, SessionNotFoundError
from config import Settings, configure_logging, load_settings
from models.visit_schema import (
    BrainProcessResponse,
    ConfirmRequest,
    ConfirmResponse,
    CorrectionRequest,
    CorrectionResponse,
    LanguageCode,
    LanguagePreferenceRequest,
    ProcessTranscriptRequest,
    ReadbackRequest,
    ReadbackResponse,
    SessionStateResponse,
)

logger = logging.getLogger("asha_saathi.api")


def create_app(
    settings: Optional[Settings] = None,
    llm_client: Optional[BaseLLMClient] = None,
) -> FastAPI:
    """Construct and wire the FastAPI AI Brain application."""
    cfg = settings or load_settings()
    configure_logging(cfg)

    client = llm_client or create_llm_client(cfg)
    danger_detector = DangerDetector(
        danger_signs_path=cfg.danger_signs_path,
        llm_client=client,
    )
    extraction_engine = ExtractionEngine(
        llm_client=client,
        max_retries=cfg.max_extraction_retries,
        timezone_name=cfg.app_timezone,
    )
    correction_engine = CorrectionEngine(
        llm_client=client,
        timezone_name=cfg.app_timezone,
    )
    guardrails = MedicalGuardrails(intro_messages=cfg.ai_intro_messages)
    state_manager = FormStateManager(
        extraction_engine=extraction_engine,
        correction_engine=correction_engine,
        danger_detector=danger_detector,
        guardrails=guardrails,
        required_fields_map=cfg.required_fields_by_visit_type,
        timezone_name=cfg.app_timezone,
    )

    fastapi_app = FastAPI(
        title="ASHA Saathi – AI Brain Backend (Person B)",
        version="2.0.0",
        description=(
            "Multilingual healthcare conversational intelligence engine supporting all 10 "
            "Gnani Prisma v3.0 / Timbre v3.0 Indian languages. Receives transcripts and "
            "detected languages from Person A and outputs structured visit records, safety "
            "danger flags, TTS metadata, and confirmation states for Person C."
        ),
    )

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    fastapi_app.state.settings = cfg
    fastapi_app.state.state_manager = state_manager
    fastapi_app.state.danger_detector = danger_detector
    fastapi_app.state.guardrails = guardrails

    @fastapi_app.get("/health", tags=["System"])
    def health_check() -> Dict[str, Any]:
        """Return operational status, provider mode, supported languages, and danger-sign metadata."""
        meta = danger_detector.metadata
        return {
            "status": "ok",
            "llm_provider": client.provider_name,
            "timezone": cfg.app_timezone,
            "supported_languages": list(SUPPORTED_GNANI_LANGUAGES.keys()),
            "code_mixing_supported": ["hi-en"],
            "danger_signs_loaded": len(danger_detector.catalog),
            "danger_signs_verification_status": meta.get(
                "verification_status", "unknown"
            ),
            "pending_person_c_verification": meta.get(
                "pending_person_c_verification", True
            ),
        }

    @fastapi_app.get("/api/brain/languages", tags=["AI Brain"])
    def list_supported_languages() -> Dict[str, Any]:
        """Return all 10 Gnani Prisma/Timbre v3.0 supported languages and TTS locale metadata."""
        return {
            "stt_provider": "gnani_prisma_v3",
            "tts_provider": "gnani_timbre_v3",
            "languages": SUPPORTED_GNANI_LANGUAGES,
            "additional_modes": ["hi-en", "auto"],
        }

    @fastapi_app.get("/api/brain/intro", tags=["AI Brain"])
    def get_intro(
        language: LanguageCode = Query(default="hi-en"),
    ) -> Dict[str, Any]:
        """Return configurable AI safety disclosure message and TTS locale metadata."""
        try:
            norm = normalize_language_code(language, default="hi-en")
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        if norm == "auto":
            norm = "hi-en"
        return {
            "language": norm,
            "tts_locale": get_tts_locale(norm),
            "intro_text": guardrails.get_intro_message(norm),
        }

    @fastapi_app.post(
        "/api/brain/process",
        response_model=BrainProcessResponse,
        tags=["AI Brain"],
    )
    def process_transcript(request: ProcessTranscriptRequest) -> BrainProcessResponse:
        """
        Process a spoken voice transcript from Person A.

        Supports Gnani Prisma v3.0 detected_language, manual language selection,
        mid-conversation language switching, two-layer danger detection, guardrails,
        voice corrections, structured extraction, and Gnani Timbre v3.0 TTS metadata.
        """
        response = state_manager.process_transcript(
            session_id=request.session_id,
            transcript=request.transcript,
            language=request.language,
            visit_date=request.visit_date,
            context=request.context,
            detected_language=request.detected_language,
            preferred_language=request.preferred_language,
            language_explicit=("language" in request.model_fields_set),
        )
        logger.info(
            "Processed turn | session=%s lang=%s action=%s danger=%s missing_count=%d confirmed=%s",
            request.session_id,
            response.language,
            response.action,
            response.danger_detected,
            len(response.missing_fields),
            response.confirmed,
        )
        return response

    @fastapi_app.post(
        "/api/brain/confirm",
        response_model=ConfirmResponse,
        tags=["AI Brain"],
    )
    def confirm_visit(request: ConfirmRequest) -> ConfirmResponse:
        """Handle explicit confirmation, rejection, or pre-save correction in active language."""
        try:
            response = state_manager.confirm_session(
                session_id=request.session_id,
                transcript=request.transcript,
                explicit_confirm=request.explicit_confirm,
                language=request.language,
                visit_date=request.visit_date,
                language_explicit=("language" in request.model_fields_set),
                detected_language=request.detected_language,
                preferred_language=request.preferred_language,
            )
            logger.info(
                "Confirmation evaluated | session=%s lang=%s confirmed=%s danger=%s",
                request.session_id,
                response.language,
                response.confirmed,
                response.danger_detected,
            )
            return response
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    @fastapi_app.post(
        "/api/brain/correct",
        response_model=CorrectionResponse,
        tags=["AI Brain"],
    )
    def correct_visit(request: CorrectionRequest) -> CorrectionResponse:
        """Apply spoken field corrections to an existing visit session without creating a new record."""
        try:
            response = state_manager.correct_session(
                session_id=request.session_id,
                transcript=request.transcript,
                language=request.language,
                visit_date=request.visit_date,
                language_explicit=("language" in request.model_fields_set),
                detected_language=request.detected_language,
                preferred_language=request.preferred_language,
            )
            logger.info(
                "Correction evaluated | session=%s lang=%s applied=%s fields=%s",
                request.session_id,
                response.language,
                response.correction_applied,
                response.updated_fields,
            )
            return response
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    @fastapi_app.post(
        "/api/brain/readback",
        response_model=ReadbackResponse,
        tags=["AI Brain"],
    )
    def readback_visit(request: ReadbackRequest) -> ReadbackResponse:
        """Generate natural-language read-back of the current session form state."""
        try:
            lang_arg = (
                request.language
                if "language" in request.model_fields_set
                else None
            )
            return state_manager.generate_session_readback(
                session_id=request.session_id,
                language=lang_arg,
            )
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    @fastapi_app.post(
        "/api/brain/session/{session_id}/language",
        response_model=SessionStateResponse,
        tags=["Session State"],
    )
    def update_session_language(
        session_id: str, request: LanguagePreferenceRequest
    ) -> SessionStateResponse:
        """Manually update a session's preferred language while preserving all form state."""
        return state_manager.set_session_language(session_id, request.language)

    @fastapi_app.get(
        "/api/brain/session/{session_id}",
        response_model=SessionStateResponse,
        tags=["Session State"],
    )
    def get_session_state(session_id: str) -> SessionStateResponse:
        """Return current structured form state, language preference, missing fields, and flags."""
        try:
            return state_manager.get_session_state_response(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    @fastapi_app.delete(
        "/api/brain/session/{session_id}",
        tags=["Session State"],
    )
    def delete_session_state(session_id: str) -> Dict[str, Any]:
        """Clear temporary session state after handoff or cancellation."""
        deleted = state_manager.delete_session(session_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found.",
            )
        logger.info("Cleared temporary session | session=%s", session_id)
        return {"session_id": session_id, "deleted": True}

    return fastapi_app


app = create_app()
