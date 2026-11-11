"""Bridge between Person A's Gnani voice server and Person B's multilingual AI Brain."""

from __future__ import annotations

import logging
import sys
import threading
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI

_VOICE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _VOICE_DIR.parent
_BACKEND_DIR = _REPO_ROOT / "backend"

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Allow `from brain import on_transcript` inside `voice/` without shadowing `backend/brain/*`.
if __name__ == "brain":
    __path__ = [str(_BACKEND_DIR / "brain")]
    if __spec__ is not None:
        __spec__.submodule_search_locations = list(__path__)

from brain.languages import get_ui_phrase, normalize_language_code  # noqa: E402
from brain.llm_client import BaseLLMClient  # noqa: E402
from brain.state_manager import FormStateManager  # noqa: E402
import main as _backend_main  # noqa: E402
from config import Settings  # noqa: E402

logger = logging.getLogger("asha_saathi.voice_brain")

_APP_LOCK = threading.RLock()
_BRAIN_APP: Optional[FastAPI] = None


def get_brain_app() -> FastAPI:
    """Return the shared Person B FastAPI app holding FormStateManager and safety engines."""
    global _BRAIN_APP
    with _APP_LOCK:
        if _BRAIN_APP is None:
            _BRAIN_APP = _backend_main.app
        return _BRAIN_APP


def configure_brain_app(
    settings: Optional[Settings] = None,
    llm_client: Optional[BaseLLMClient] = None,
) -> FastAPI:
    """Rebuild the shared brain app (primarily for startup configuration or tests)."""
    global _BRAIN_APP
    with _APP_LOCK:
        _BRAIN_APP = _backend_main.create_app(settings=settings, llm_client=llm_client)
        return _BRAIN_APP


def get_state_manager() -> FormStateManager:
    """Return the shared FormStateManager used across voice WebSocket and REST endpoints."""
    return get_brain_app().state.state_manager


def get_intro_message(language: Optional[str] = None) -> str:
    """Return Person B's localized AI safety disclosure message."""
    app = get_brain_app()
    norm = _sanitize_language_arg(language) or "hi-en"
    return app.state.guardrails.get_intro_message(norm)


def _sanitize_language_arg(raw: Optional[str]) -> Optional[str]:
    """Normalize a language hint, ignoring 'auto'/'indic-auto' or unrecognized values."""
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned or cleaned.lower() in {"auto", "indic-auto", "unknown", "und"}:
        return None
    try:
        norm = normalize_language_code(cleaned)
    except ValueError:
        logger.debug("Ignoring unrecognized language tag from voice pipeline: %s", cleaned)
        return None
    return None if norm == "auto" else norm


def on_transcript(
    text: str,
    session: Optional[Dict[str, Any]] = None,
    detected_language: Optional[str] = None,
    preferred_language: Optional[str] = None,
    visit_date: Optional[date] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a spoken STT transcript through Person B's multilingual AI Brain.

    Maintains isolated per-session form state across turns and returns both legacy
    voice keys (`text_to_speak`, `language`, `form_state`, `danger_flag`) and complete
    structured Section 10 fields for WebSocket/frontend/Person C consumers.
    """
    session_dict: Dict[str, Any] = {} if session is None else session
    session_id = session_dict.setdefault("session_id", f"voice-{uuid4().hex[:12]}")

    manager = get_state_manager()
    transcript = (text or "").strip()

    explicit_lang = _sanitize_language_arg(language or session_dict.get("explicit_language"))
    det_lang = _sanitize_language_arg(
        detected_language or session_dict.get("detected_language")
    )
    pref_lang = _sanitize_language_arg(
        preferred_language or session_dict.get("preferred_language")
    )

    if not transcript:
        active_lang = explicit_lang or pref_lang or _sanitize_language_arg(
            session_dict.get("language")
        ) or "hi-en"
        ctx = manager.get_session(session_id)
        form_state = ctx.record.to_compact_dict() if ctx else {}
        missing_fields = list(ctx.record.missing_fields) if ctx else []
        danger_flags = (
            [f.model_dump(mode="json") for f in ctx.danger_flags] if ctx else []
        )
        reply = get_ui_phrase("clarify_unrecognized", active_lang)
        return {
            "session_id": session_id,
            "text_to_speak": reply,
            "reply_text": reply,
            "action": "clarify",
            "language": active_lang,
            "language_code": "hi-IN" if active_lang in {"hi", "hi-en"} else active_lang,
            "detected_language": det_lang,
            "language_switched": False,
            "tts_metadata": {},
            "form_state": form_state,
            "missing_fields": missing_fields,
            "danger_flag": bool(danger_flags),
            "danger_detected": bool(danger_flags),
            "danger_flags": danger_flags,
            "confirmation_state": "collecting",
            "confirmation_required": bool(ctx.awaiting_confirmation) if ctx else False,
            "confirmed": bool(ctx.confirmed) if ctx else False,
            "confirmed_record": ctx.confirmed_payload if ctx else None,
            "follow_up_date": None,
            "vaccinations": dict(ctx.record.vaccinations) if ctx else {},
            "next_actions": manager.build_next_actions(ctx) if ctx else [],
            "guardrail_triggered": False,
            "guardrail_reason": None,
        }

    response = manager.process_transcript(
        session_id=session_id,
        transcript=transcript,
        language=explicit_lang or "auto",
        visit_date=visit_date or session_dict.get("visit_date"),
        detected_language=det_lang,
        preferred_language=pref_lang,
        language_explicit=bool(explicit_lang),
    )

    ctx = manager.get_session(session_id)
    confirmed_payload = ctx.confirmed_payload if ctx and response.confirmed else None

    if response.confirmed:
        confirmation_state = "confirmed"
    elif response.confirmation_required:
        confirmation_state = "awaiting_confirmation"
    else:
        confirmation_state = "collecting"

    serialized_flags = [flag.model_dump(mode="json") for flag in response.danger_flags]
    language_code = response.tts_metadata.get("language_code") or "hi-IN"

    session_dict["form"] = dict(response.form_state)
    session_dict["danger_flag"] = response.danger_detected
    session_dict["language"] = response.language
    session_dict["detected_language"] = response.detected_language
    session_dict["confirmation_state"] = confirmation_state
    session_dict["confirmed_record"] = confirmed_payload

    return {
        "session_id": response.session_id,
        "text_to_speak": response.reply_text,
        "reply_text": response.reply_text,
        "action": response.action,
        "language": response.language,
        "language_code": language_code,
        "detected_language": response.detected_language,
        "language_switched": response.language_switched,
        "tts_metadata": dict(response.tts_metadata),
        "form_state": dict(response.form_state),
        "missing_fields": list(response.missing_fields),
        "danger_flag": response.danger_detected,
        "danger_detected": response.danger_detected,
        "danger_flags": serialized_flags,
        "confirmation_state": confirmation_state,
        "confirmation_required": response.confirmation_required,
        "confirmed": response.confirmed,
        "confirmed_record": confirmed_payload,
        "follow_up_date": response.follow_up_date,
        "vaccinations": dict(response.vaccinations),
        "next_actions": list(response.next_actions),
        "guardrail_triggered": response.guardrail_triggered,
        "guardrail_reason": response.guardrail_reason,
    }
