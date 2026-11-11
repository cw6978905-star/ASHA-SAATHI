"""Module 2: Multilingual Form State Manager and Conversation Orchestrator (All 10 Gnani Languages)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from config import DEFAULT_REQUIRED_FIELDS_BY_VISIT_TYPE
from brain.correction import CorrectionEngine
from brain.danger_detector import DangerDetector
from brain.extraction import ExtractionEngine
from brain.guardrails import MedicalGuardrails
from brain.languages import (
    FOLLOWUP_QUESTIONS as ALL_FOLLOWUP_QUESTIONS,
    build_tts_metadata,
    get_followup_question,
    get_ui_phrase,
    normalize_language_code,
    resolve_session_language,
)
from brain.normalizers import today_in_timezone
from brain.readback import (
    build_confirmed_payload,
    classify_confirmation_intent,
    generate_readback,
)
from models.visit_schema import (
    BrainProcessResponse,
    ConfirmResponse,
    CorrectionResponse,
    DangerFlag,
    ExtractionPayload,
    LanguageCode,
    ReadbackResponse,
    SessionStateResponse,
    VisitRecord,
)

logger = logging.getLogger("asha_saathi.state")

# Preserve backwards-compatible export
FOLLOWUP_QUESTIONS: Dict[str, Dict[str, str]] = ALL_FOLLOWUP_QUESTIONS


@dataclass
class SessionContext:
    """Isolated per-session conversation, language preference, and visit form state."""

    session_id: str
    record: VisitRecord = field(default_factory=VisitRecord)
    danger_flags: List[DangerFlag] = field(default_factory=list)
    awaiting_confirmation: bool = False
    confirmed: bool = False
    confirmed_payload: Optional[Dict[str, Any]] = None
    last_asked_field: Optional[str] = None
    asked_unknown_fields: set[str] = field(default_factory=set)
    language: Optional[str] = None
    detected_language: Optional[str] = None
    manual_language_locked: bool = False
    turn_count: int = 0


class SessionNotFoundError(KeyError):
    """Raised when attempting to access or mutate a nonexistent session."""


class FormStateManager:
    """
    Maintains isolated multi-turn visit form state and language preferences across
    10 Gnani languages while coordinating extraction, corrections, danger detection,
    guardrails, and read-back.
    """

    def __init__(
        self,
        extraction_engine: ExtractionEngine,
        correction_engine: CorrectionEngine,
        danger_detector: DangerDetector,
        guardrails: MedicalGuardrails,
        required_fields_map: Optional[Dict[str, List[str]]] = None,
        timezone_name: str = "Asia/Kolkata",
    ) -> None:
        self._extractor = extraction_engine
        self._corrector = correction_engine
        self._danger = danger_detector
        self._guardrails = guardrails
        self._required_fields_map = required_fields_map or dict(
            DEFAULT_REQUIRED_FIELDS_BY_VISIT_TYPE
        )
        self._timezone = timezone_name
        self._sessions: Dict[str, SessionContext] = {}
        self._lock = threading.RLock()

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: str) -> SessionContext:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(session_id=session_id)
            return self._sessions[session_id]

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def set_session_language(self, session_id: str, language: str) -> SessionStateResponse:
        """Manually update session language preference without altering existing form state."""
        norm = normalize_language_code(language)
        if norm == "auto":
            raise ValueError("Manual session preference cannot be 'auto'.")
        with self._lock:
            session = self.get_or_create_session(session_id)
            session.language = norm
            session.manual_language_locked = True
            return self.get_session_state_response(session_id)

    def compute_missing_fields(self, record: VisitRecord) -> List[str]:
        """Determine required missing fields based on visit_type."""
        if record.visit_type is None:
            required = ["visit_type", "beneficiary_name", "beneficiary_id"]
        else:
            required = self._required_fields_map.get(
                record.visit_type, self._required_fields_map.get("other", [])
            )

        missing: List[str] = []
        for field_name in required:
            if field_name == "vaccinations":
                if not record.vaccinations:
                    missing.append(field_name)
            elif getattr(record, field_name, None) is None:
                missing.append(field_name)
        return missing

    def build_next_actions(self, session: SessionContext) -> List[str]:
        """Generate structured action hints for Person A and Person C."""
        actions: List[str] = []
        if session.danger_flags:
            actions.append("urgent_phc_referral")
        if session.confirmed:
            actions.append("ready_for_person_c_storage")
        elif session.awaiting_confirmation:
            actions.append("await_worker_confirmation")
        elif session.record.missing_fields:
            actions.extend(f"collect_missing:{f}" for f in session.record.missing_fields)
        return actions

    def get_session_state_response(self, session_id: str) -> SessionStateResponse:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFoundError(f"Session '{session_id}' not found.")
            session.record.missing_fields = self.compute_missing_fields(session.record)
            active_lang = session.language or "hi-en"
            return SessionStateResponse(
                session_id=session.session_id,
                language=active_lang,
                detected_language=session.detected_language,
                tts_metadata=build_tts_metadata(active_lang, session.detected_language),
                form_state=session.record.to_compact_dict(),
                missing_fields=list(session.record.missing_fields),
                visit_type=session.record.visit_type,
                beneficiary_info={
                    "name": session.record.beneficiary_name,
                    "id": session.record.beneficiary_id,
                },
                danger_detected=len(session.danger_flags) > 0,
                danger_flags=list(session.danger_flags),
                confirmation_required=session.awaiting_confirmation,
                confirmed=session.confirmed,
                follow_up_date=(
                    session.record.next_visit_date.isoformat()
                    if session.record.next_visit_date
                    else None
                ),
                vaccinations=dict(session.record.vaccinations),
                next_actions=self.build_next_actions(session),
                turn_count=session.turn_count,
            )

    def process_transcript(
        self,
        session_id: str,
        transcript: str,
        language: Optional[LanguageCode] = None,
        visit_date: Optional[date] = None,
        context: Optional[Dict[str, Any]] = None,
        detected_language: Optional[str] = None,
        preferred_language: Optional[str] = None,
        language_explicit: Optional[bool] = None,
    ) -> BrainProcessResponse:
        """Process a single final transcript turn in an isolated multilingual visit session."""
        with self._lock:
            session = self.get_or_create_session(session_id)
            ctx = context or {}
            det_lang_in = detected_language or ctx.get("detected_language")
            pref_lang_in = preferred_language or ctx.get("preferred_language")

            explicit_flag = (
                language_explicit
                if language_explicit is not None
                else (language is not None)
            )
            lang_res = resolve_session_language(
                transcript=transcript,
                requested_language=language or "hi-en",
                current_session_language=session.language,
                detected_language=det_lang_in,
                preferred_language=pref_lang_in,
                requested_explicit=explicit_flag,
                manual_language_locked=session.manual_language_locked,
            )
            active_lang = lang_res.active_language
            session.language = active_lang
            session.detected_language = lang_res.detected_language
            session.manual_language_locked = lang_res.manual_locked
            session.turn_count += 1

            anchor_date = visit_date or session.record.visit_date or today_in_timezone(
                self._timezone
            )
            if session.record.visit_date is None:
                session.record.visit_date = anchor_date

            # 1. Highest priority: Two-layer Danger-Sign Detection on every turn
            danger_detected_turn, new_flags = self._danger.detect(
                transcript, language=active_lang
            )
            if danger_detected_turn:
                self._merge_danger_flags(session, new_flags)

            # 2. Medical Safety Guardrails
            guardrail_decision = self._guardrails.evaluate_input(
                transcript, language=active_lang
            )
            if guardrail_decision.blocked:
                reply = guardrail_decision.refusal_text or self._guardrails.get_refusal_message(
                    active_lang
                )
                if danger_detected_turn:
                    reply = f"{self._danger.get_referral_message(active_lang)} {reply}"
                reply = self._guardrails.validate_output(reply, language=active_lang)
                session.record.missing_fields = self.compute_missing_fields(session.record)
                logger.info(
                    "Session %s guardrail triggered (%s) | lang=%s",
                    session_id,
                    guardrail_decision.reason,
                    active_lang,
                )
                return self._build_process_response(
                    session=session,
                    reply_text=reply,
                    action="refer_danger" if danger_detected_turn else "refuse_medical_advice",
                    guardrail_triggered=True,
                    guardrail_reason=guardrail_decision.reason,
                    language_switched=lang_res.switched,
                )

            # 3. If awaiting explicit confirmation
            if session.awaiting_confirmation and not lang_res.explicit_switch_command:
                corr = self._corrector.detect_corrections(
                    transcript=transcript,
                    existing_record=session.record,
                    visit_date=anchor_date,
                    language=active_lang,
                )
                if corr.is_correction:
                    return self._handle_correction_in_turn(
                        session=session,
                        detection=corr,
                        language=active_lang,
                        danger_detected_turn=danger_detected_turn,
                        language_switched=lang_res.switched,
                    )

                intent = classify_confirmation_intent(transcript)
                if intent == "confirm":
                    session.confirmed = True
                    session.awaiting_confirmation = False
                    session.confirmed_payload = build_confirmed_payload(
                        session_id=session.session_id,
                        record=session.record,
                        danger_flags=session.danger_flags,
                        timezone_name=self._timezone,
                    )
                    reply = self._confirmation_saved_message(session, active_lang)
                    if session.danger_flags:
                        reply = f"{self._danger.get_referral_message(active_lang)} {reply}"
                    reply = self._guardrails.validate_output(reply, language=active_lang)
                    return self._build_process_response(
                        session=session,
                        reply_text=reply,
                        action="refer_danger" if session.danger_flags else "completed",
                        language_switched=lang_res.switched,
                    )

                if intent == "reject":
                    session.confirmed = False
                    session.awaiting_confirmation = False
                    reply = get_ui_phrase("rejected_ack", active_lang)
                    reply = self._guardrails.validate_output(reply, language=active_lang)
                    return self._build_process_response(
                        session=session,
                        reply_text=reply,
                        action="clarify",
                        language_switched=lang_res.switched,
                    )

            # 4. Check for Voice Correction against existing record
            if self._has_existing_data(session.record) and not lang_res.explicit_switch_command:
                corr = self._corrector.detect_corrections(
                    transcript=transcript,
                    existing_record=session.record,
                    visit_date=anchor_date,
                    language=active_lang,
                )
                if corr.is_correction:
                    return self._handle_correction_in_turn(
                        session=session,
                        detection=corr,
                        language=active_lang,
                        danger_detected_turn=danger_detected_turn,
                        language_switched=lang_res.switched,
                    )

            # 5. Extract structured healthcare information
            existing_ctx = session.record.to_compact_dict()
            existing_ctx["_expecting_field"] = session.last_asked_field
            extracted = self._extractor.extract(
                transcript=transcript,
                visit_date=anchor_date,
                existing_form=existing_ctx,
                language=active_lang,
                detected_language=lang_res.detected_language,
            )

            # Handle pure mid-conversation language switch command without mutating form state
            if lang_res.explicit_switch_command and not self._payload_has_clinical_fields(extracted):
                session.record.missing_fields = self.compute_missing_fields(session.record)
                switch_ack = get_ui_phrase("language_switched", active_lang)
                if session.awaiting_confirmation:
                    rb = generate_readback(session.record, language=active_lang)
                    reply = f"{switch_ack}\n{rb}"
                    action = "confirm_record"
                else:
                    next_q = self._next_question_for_session(session, active_lang)
                    reply = f"{switch_ack} {next_q}".strip()
                    action = "collect_info" if next_q else "clarify"
                reply = self._guardrails.validate_output(reply, language=active_lang)
                return self._build_process_response(
                    session=session,
                    reply_text=reply,
                    action=action,  # type: ignore[arg-type]
                    language_switched=True,
                )

            # Prevent cross-beneficiary contamination inside the same session
            conflict_msg = self._check_beneficiary_isolation(
                session=session, extracted=extracted, language=active_lang
            )
            if conflict_msg:
                reply = self._guardrails.validate_output(conflict_msg, language=active_lang)
                return self._build_process_response(
                    session=session,
                    reply_text=reply,
                    action="clarify",
                    language_switched=lang_res.switched,
                )

            newly_filled = self._merge_extraction(session, extracted)
            session.record.missing_fields = self.compute_missing_fields(session.record)

            # 6. Build priority-ordered voice response in active_lang
            return self._compose_next_step_response(
                session=session,
                newly_filled=newly_filled,
                language=active_lang,
                danger_detected_turn=danger_detected_turn,
                language_switched=lang_res.switched,
            )

    def _resolve_action_language(
        self,
        session: SessionContext,
        transcript: str,
        language: Optional[str],
        detected_language: Optional[str],
        preferred_language: Optional[str],
        language_explicit: Optional[bool],
    ) -> str:
        explicit_flag = (
            language_explicit
            if language_explicit is not None
            else (language is not None and language != "hi-en")
        )
        lang_res = resolve_session_language(
            transcript=transcript,
            requested_language=language or "hi-en",
            current_session_language=session.language,
            detected_language=detected_language,
            preferred_language=preferred_language,
            requested_explicit=explicit_flag,
            manual_language_locked=session.manual_language_locked,
        )
        session.language = lang_res.active_language
        session.detected_language = lang_res.detected_language
        session.manual_language_locked = lang_res.manual_locked
        return lang_res.active_language

    def confirm_session(
        self,
        session_id: str,
        transcript: Optional[str] = None,
        explicit_confirm: Optional[bool] = None,
        language: Optional[LanguageCode] = None,
        visit_date: Optional[date] = None,
        language_explicit: Optional[bool] = None,
        detected_language: Optional[str] = None,
        preferred_language: Optional[str] = None,
    ) -> ConfirmResponse:
        """Handle explicit confirmation, rejection, or pre-save correction."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFoundError(f"Session '{session_id}' not found.")

            active_lang = self._resolve_action_language(
                session=session,
                transcript=transcript or "",
                language=language,
                detected_language=detected_language,
                preferred_language=preferred_language,
                language_explicit=language_explicit,
            )
            tts_meta = build_tts_metadata(active_lang, session.detected_language)

            anchor_date = visit_date or session.record.visit_date or today_in_timezone(
                self._timezone
            )
            session.record.missing_fields = self.compute_missing_fields(session.record)

            if transcript:
                d_hit, flags = self._danger.detect(transcript, language=active_lang)
                if d_hit:
                    self._merge_danger_flags(session, flags)

                corr = self._corrector.detect_corrections(
                    transcript=transcript,
                    existing_record=session.record,
                    visit_date=anchor_date,
                    language=active_lang,
                )
                if corr.is_correction:
                    if corr.corrections:
                        updated, _, errors = self._corrector.apply_corrections(
                            session.record, corr
                        )
                        if not errors:
                            session.record = updated
                            session.confirmed = False
                            session.awaiting_confirmation = True
                    session.record.missing_fields = self.compute_missing_fields(
                        session.record
                    )
                    rb_text = generate_readback(session.record, language=active_lang)
                    reply = self._guardrails.validate_output(rb_text, language=active_lang)
                    return ConfirmResponse(
                        session_id=session.session_id,
                        confirmed=False,
                        ready_for_storage=False,
                        confirmation_required=True,
                        reply_text=reply,
                        readback_text=rb_text,
                        language=active_lang,
                        tts_metadata=tts_meta,
                        form_state=session.record.to_compact_dict(),
                        confirmed_record=None,
                        missing_fields=list(session.record.missing_fields),
                        danger_detected=len(session.danger_flags) > 0,
                        danger_flags=list(session.danger_flags),
                        next_actions=self.build_next_actions(session),
                    )

            decision = explicit_confirm
            if decision is None and transcript:
                intent = classify_confirmation_intent(transcript)
                if intent == "confirm":
                    decision = True
                elif intent == "reject":
                    decision = False

            rb_text = generate_readback(session.record, language=active_lang)

            if decision is True:
                session.confirmed = True
                session.awaiting_confirmation = False
                payload = build_confirmed_payload(
                    session_id=session.session_id,
                    record=session.record,
                    danger_flags=session.danger_flags,
                    timezone_name=self._timezone,
                )
                session.confirmed_payload = payload
                reply = self._confirmation_saved_message(session, active_lang)
                if session.danger_flags:
                    reply = f"{self._danger.get_referral_message(active_lang)} {reply}"
                reply = self._guardrails.validate_output(reply, language=active_lang)
                return ConfirmResponse(
                    session_id=session.session_id,
                    confirmed=True,
                    ready_for_storage=True,
                    confirmation_required=False,
                    reply_text=reply,
                    readback_text=rb_text,
                    language=active_lang,
                    tts_metadata=tts_meta,
                    form_state=session.record.to_compact_dict(),
                    confirmed_record=payload,
                    missing_fields=list(session.record.missing_fields),
                    danger_detected=len(session.danger_flags) > 0,
                    danger_flags=list(session.danger_flags),
                    next_actions=self.build_next_actions(session),
                )

            if decision is False:
                session.confirmed = False
                session.awaiting_confirmation = False
                reply = get_ui_phrase("rejected_ack", active_lang)
                reply = self._guardrails.validate_output(reply, language=active_lang)
                return ConfirmResponse(
                    session_id=session.session_id,
                    confirmed=False,
                    ready_for_storage=False,
                    confirmation_required=False,
                    reply_text=reply,
                    readback_text=rb_text,
                    language=active_lang,
                    tts_metadata=tts_meta,
                    form_state=session.record.to_compact_dict(),
                    confirmed_record=None,
                    missing_fields=list(session.record.missing_fields),
                    danger_detected=len(session.danger_flags) > 0,
                    danger_flags=list(session.danger_flags),
                    next_actions=self.build_next_actions(session),
                )

            session.awaiting_confirmation = True
            session.confirmed = False
            reply = self._guardrails.validate_output(rb_text, language=active_lang)
            return ConfirmResponse(
                session_id=session.session_id,
                confirmed=False,
                ready_for_storage=False,
                confirmation_required=True,
                reply_text=reply,
                readback_text=rb_text,
                language=active_lang,
                tts_metadata=tts_meta,
                form_state=session.record.to_compact_dict(),
                confirmed_record=None,
                missing_fields=list(session.record.missing_fields),
                danger_detected=len(session.danger_flags) > 0,
                danger_flags=list(session.danger_flags),
                next_actions=self.build_next_actions(session),
            )

    def correct_session(
        self,
        session_id: str,
        transcript: str,
        language: Optional[LanguageCode] = None,
        visit_date: Optional[date] = None,
        language_explicit: Optional[bool] = None,
        detected_language: Optional[str] = None,
        preferred_language: Optional[str] = None,
    ) -> CorrectionResponse:
        """Apply explicit voice correction against an existing session form."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFoundError(f"Session '{session_id}' not found.")

            active_lang = self._resolve_action_language(
                session=session,
                transcript=transcript,
                language=language,
                detected_language=detected_language,
                preferred_language=preferred_language,
                language_explicit=language_explicit,
            )
            tts_meta = build_tts_metadata(active_lang, session.detected_language)

            anchor_date = visit_date or session.record.visit_date or today_in_timezone(
                self._timezone
            )
            d_hit, flags = self._danger.detect(transcript, language=active_lang)
            if d_hit:
                self._merge_danger_flags(session, flags)

            detection = self._corrector.detect_corrections(
                transcript=transcript,
                existing_record=session.record,
                visit_date=anchor_date,
                language=active_lang,
                force_correction_mode=True,
            )

            if detection.ambiguous_field:
                reply = detection.clarification_prompt or get_ui_phrase("rejected_ack", active_lang)
                reply = self._guardrails.validate_output(reply, language=active_lang)
                session.record.missing_fields = self.compute_missing_fields(session.record)
                return CorrectionResponse(
                    session_id=session.session_id,
                    correction_applied=False,
                    updated_fields=[],
                    clarification_needed=True,
                    reply_text=reply,
                    language=active_lang,
                    tts_metadata=tts_meta,
                    form_state=session.record.to_compact_dict(),
                    missing_fields=list(session.record.missing_fields),
                    danger_detected=len(session.danger_flags) > 0,
                    danger_flags=list(session.danger_flags),
                    confirmation_required=session.awaiting_confirmation,
                    confirmed=session.confirmed,
                )

            updated_record, updated_fields, errors = self._corrector.apply_corrections(
                session.record, detection
            )
            if errors and not updated_fields:
                reply = self._guardrails.validate_output(" ".join(errors), language=active_lang)
                session.record.missing_fields = self.compute_missing_fields(session.record)
                return CorrectionResponse(
                    session_id=session.session_id,
                    correction_applied=False,
                    updated_fields=[],
                    clarification_needed=True,
                    reply_text=reply,
                    language=active_lang,
                    tts_metadata=tts_meta,
                    form_state=session.record.to_compact_dict(),
                    missing_fields=list(session.record.missing_fields),
                    danger_detected=len(session.danger_flags) > 0,
                    danger_flags=list(session.danger_flags),
                    confirmation_required=session.awaiting_confirmation,
                    confirmed=session.confirmed,
                )

            session.record = updated_record
            session.confirmed = False
            session.confirmed_payload = None
            session.record.missing_fields = self.compute_missing_fields(session.record)

            if session.awaiting_confirmation or not session.record.missing_fields:
                session.awaiting_confirmation = True
                reply = generate_readback(session.record, language=active_lang)
            else:
                ack = self._format_update_ack(updated_fields, active_lang)
                next_q = self._next_question_for_session(session, active_lang)
                reply = f"{ack} {next_q}".strip()

            if d_hit:
                reply = f"{self._danger.get_referral_message(active_lang)} {reply}"
            reply = self._guardrails.validate_output(reply, language=active_lang)

            return CorrectionResponse(
                session_id=session.session_id,
                correction_applied=len(updated_fields) > 0,
                updated_fields=updated_fields,
                clarification_needed=False,
                reply_text=reply,
                language=active_lang,
                tts_metadata=tts_meta,
                form_state=session.record.to_compact_dict(),
                missing_fields=list(session.record.missing_fields),
                danger_detected=len(session.danger_flags) > 0,
                danger_flags=list(session.danger_flags),
                confirmation_required=session.awaiting_confirmation,
                confirmed=session.confirmed,
            )

    def generate_session_readback(
        self, session_id: str, language: Optional[LanguageCode] = None
    ) -> ReadbackResponse:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFoundError(f"Session '{session_id}' not found.")
            active_lang = (
                normalize_language_code(language)
                if (language and language.lower() != "auto")
                else (session.language or "hi-en")
            )
            session.record.missing_fields = self.compute_missing_fields(session.record)
            session.awaiting_confirmation = True
            rb_text = generate_readback(session.record, language=active_lang)
            rb_text = self._guardrails.validate_output(rb_text, language=active_lang)
            return ReadbackResponse(
                session_id=session.session_id,
                readback_text=rb_text,
                language=active_lang,
                tts_metadata=build_tts_metadata(active_lang, session.detected_language),
                missing_fields=list(session.record.missing_fields),
                confirmation_required=True,
                confirmed=session.confirmed,
            )

    def _handle_correction_in_turn(
        self,
        session: SessionContext,
        detection: Any,
        language: str,
        danger_detected_turn: bool,
        language_switched: bool = False,
    ) -> BrainProcessResponse:
        if detection.ambiguous_field:
            reply = detection.clarification_prompt or get_ui_phrase("rejected_ack", language)
            if danger_detected_turn:
                reply = f"{self._danger.get_referral_message(language)} {reply}"
            reply = self._guardrails.validate_output(reply, language=language)
            return self._build_process_response(
                session=session,
                reply_text=reply,
                action="refer_danger" if danger_detected_turn else "clarify",
                language_switched=language_switched,
            )

        updated_record, updated_fields, errors = self._corrector.apply_corrections(
            session.record, detection
        )
        if errors and not updated_fields:
            reply = " ".join(errors)
            if danger_detected_turn:
                reply = f"{self._danger.get_referral_message(language)} {reply}"
            reply = self._guardrails.validate_output(reply, language=language)
            return self._build_process_response(
                session=session,
                reply_text=reply,
                action="refer_danger" if danger_detected_turn else "clarify",
                language_switched=language_switched,
            )

        was_awaiting = session.awaiting_confirmation
        session.record = updated_record
        session.confirmed = False
        session.confirmed_payload = None
        session.record.missing_fields = self.compute_missing_fields(session.record)

        if was_awaiting or not session.record.missing_fields:
            session.awaiting_confirmation = True
            reply = generate_readback(session.record, language=language)
            action = "refer_danger" if danger_detected_turn else "confirm_record"
        else:
            ack = self._format_update_ack(updated_fields, language)
            next_q = self._next_question_for_session(session, language)
            reply = f"{ack} {next_q}".strip()
            action = "refer_danger" if danger_detected_turn else "collect_info"

        if danger_detected_turn:
            reply = f"{self._danger.get_referral_message(language)} {reply}"
        reply = self._guardrails.validate_output(reply, language=language)
        return self._build_process_response(
            session=session,
            reply_text=reply,
            action=action,  # type: ignore[arg-type]
            language_switched=language_switched,
        )

    def _compose_next_step_response(
        self,
        session: SessionContext,
        newly_filled: List[str],
        language: str,
        danger_detected_turn: bool,
        language_switched: bool = False,
    ) -> BrainProcessResponse:
        if (
            session.record.ambiguous_next_visit_reference
            and session.record.next_visit_date is None
        ):
            session.last_asked_field = "next_visit_date"
            msg = get_ui_phrase(
                "ambiguous_date",
                language,
                ref=session.record.ambiguous_next_visit_reference,
            )
            if danger_detected_turn:
                msg = f"{self._danger.get_referral_message(language)} {msg}"
            msg = self._guardrails.validate_output(msg, language=language)
            return self._build_process_response(
                session=session,
                reply_text=msg,
                action="refer_danger" if danger_detected_turn else "clarify",
                language_switched=language_switched,
            )

        actionable_missing = [
            f
            for f in session.record.missing_fields
            if f not in session.asked_unknown_fields
        ]

        if danger_detected_turn:
            referral = self._danger.get_referral_message(language)
            reply = self._guardrails.validate_output(referral, language=language)
            return self._build_process_response(
                session=session,
                reply_text=reply,
                action="refer_danger",
                language_switched=language_switched,
            )

        if actionable_missing:
            next_field = actionable_missing[0]
            session.last_asked_field = next_field
            session.awaiting_confirmation = False
            ack = self._acknowledge_turn(session.record, newly_filled, language)
            question = get_followup_question(next_field, language)
            reply = f"{ack} {question}".strip()
            reply = self._guardrails.validate_output(reply, language=language)
            return self._build_process_response(
                session=session,
                reply_text=reply,
                action="collect_info",
                language_switched=language_switched,
            )

        session.last_asked_field = None
        session.awaiting_confirmation = True
        rb_text = generate_readback(session.record, language=language)
        rb_text = self._guardrails.validate_output(rb_text, language=language)
        return self._build_process_response(
            session=session,
            reply_text=rb_text,
            action="confirm_record",
            language_switched=language_switched,
        )

    def _merge_danger_flags(
        self, session: SessionContext, new_flags: List[DangerFlag]
    ) -> None:
        existing_by_id = {f.danger_sign_id: f for f in session.danger_flags}
        for flag in new_flags:
            if flag.danger_sign_id in existing_by_id:
                curr = existing_by_id[flag.danger_sign_id]
                for layer in flag.matched_layers:
                    if layer not in curr.matched_layers:
                        curr.matched_layers.append(layer)
                for ev in flag.matched_evidence:
                    if ev not in curr.matched_evidence:
                        curr.matched_evidence.append(ev)
                curr.ambiguous = curr.ambiguous or flag.ambiguous
            else:
                session.danger_flags.append(flag)
                existing_by_id[flag.danger_sign_id] = flag

            if flag.danger_sign_id not in session.record.danger_signs:
                session.record.danger_signs.append(flag.danger_sign_id)

    def _check_beneficiary_isolation(
        self,
        session: SessionContext,
        extracted: ExtractionPayload,
        language: str,
    ) -> Optional[str]:
        """Prevent mixing data from two different beneficiaries inside the same session."""
        curr_name = session.record.beneficiary_name
        curr_id = session.record.beneficiary_id
        new_name = extracted.beneficiary_name
        new_id = extracted.beneficiary_id

        name_conflict = (
            curr_name
            and new_name
            and curr_name.strip().lower() != new_name.strip().lower()
        )
        id_conflict = (
            curr_id and new_id and curr_id.strip().upper() != new_id.strip().upper()
        )

        if name_conflict or id_conflict:
            target = new_name or new_id or ""
            active = curr_name or curr_id or ""
            return get_ui_phrase(
                "beneficiary_conflict", language, active=active, target=target
            )
        return None

    def _merge_extraction(
        self, session: SessionContext, extracted: ExtractionPayload
    ) -> List[str]:
        rec = session.record
        newly_filled: List[str] = []

        scalar_fields = [
            "beneficiary_name",
            "beneficiary_id",
            "visit_type",
            "weight_kg",
            "blood_pressure",
            "pregnancy_info",
            "newborn_info",
            "ifa_status",
            "next_visit_date",
        ]
        for fname in scalar_fields:
            val = getattr(extracted, fname)
            if val is not None:
                if getattr(rec, fname) != val:
                    setattr(rec, fname, val)
                    newly_filled.append(fname)
                if fname in rec.unknown_fields:
                    rec.unknown_fields.remove(fname)
                session.asked_unknown_fields.discard(fname)

        if extracted.ambiguous_next_visit_reference and rec.next_visit_date is None:
            rec.ambiguous_next_visit_reference = extracted.ambiguous_next_visit_reference
        elif rec.next_visit_date is not None:
            rec.ambiguous_next_visit_reference = None

        if extracted.vaccinations:
            rec.vaccinations.update(extracted.vaccinations)
            newly_filled.append("vaccinations")

        for obs in extracted.observations:
            if obs and obs not in rec.observations:
                rec.observations.append(obs)

        for k, v in extracted.negative_findings.items():
            rec.negative_findings[k] = v

        for u in extracted.unknown_fields:
            if u not in rec.unknown_fields:
                rec.unknown_fields.append(u)
            session.asked_unknown_fields.add(u)

        if newly_filled:
            session.confirmed = False
            session.confirmed_payload = None

        return newly_filled

    def _payload_has_clinical_fields(self, extracted: ExtractionPayload) -> bool:
        return any(
            [
                extracted.beneficiary_name is not None,
                extracted.beneficiary_id is not None,
                extracted.visit_type is not None,
                extracted.weight_kg is not None,
                extracted.blood_pressure is not None,
                extracted.pregnancy_info is not None,
                extracted.newborn_info is not None,
                bool(extracted.vaccinations),
                extracted.ifa_status is not None,
                extracted.next_visit_date is not None,
                bool(extracted.negative_findings),
                bool(extracted.unknown_fields),
            ]
        )

    def _has_existing_data(self, record: VisitRecord) -> bool:
        return any(
            [
                record.beneficiary_name is not None,
                record.beneficiary_id is not None,
                record.visit_type is not None,
                record.weight_kg is not None,
                record.blood_pressure is not None,
                bool(record.vaccinations),
                record.ifa_status is not None,
                record.next_visit_date is not None,
            ]
        )

    def _next_question_for_session(
        self, session: SessionContext, language: str
    ) -> str:
        actionable = [
            f
            for f in session.record.missing_fields
            if f not in session.asked_unknown_fields
        ]
        if not actionable:
            return ""
        session.last_asked_field = actionable[0]
        return get_followup_question(actionable[0], language)

    def _acknowledge_turn(
        self, record: VisitRecord, newly_filled: List[str], language: str
    ) -> str:
        if not newly_filled:
            return ""
        if "beneficiary_name" in newly_filled and record.beneficiary_name:
            return get_ui_phrase("ack_name", language, name=record.beneficiary_name)
        if "weight_kg" in newly_filled and record.weight_kg is not None:
            wt_str = (
                str(int(record.weight_kg))
                if float(record.weight_kg).is_integer()
                else f"{record.weight_kg:g}"
            )
            return get_ui_phrase("ack_weight", language, wt=wt_str)
        if "beneficiary_id" in newly_filled and record.beneficiary_id:
            return get_ui_phrase("ack_id", language, bid=record.beneficiary_id)
        if "blood_pressure" in newly_filled and record.blood_pressure:
            return get_ui_phrase("ack_bp", language, bp=record.blood_pressure.formatted())
        return ""

    def _format_update_ack(self, updated_fields: List[str], language: str) -> str:
        if not updated_fields:
            return ""
        return get_ui_phrase("updated_ack", language, fields=", ".join(updated_fields))

    def _confirmation_saved_message(self, session: SessionContext, language: str) -> str:
        name = session.record.beneficiary_name or "Beneficiary"
        return get_ui_phrase("saved_ack", language, name=name)

    def _build_process_response(
        self,
        session: SessionContext,
        reply_text: str,
        action: Any,
        guardrail_triggered: bool = False,
        guardrail_reason: Optional[str] = None,
        language_switched: bool = False,
    ) -> BrainProcessResponse:
        active_lang = session.language or "hi-en"
        return BrainProcessResponse(
            session_id=session.session_id,
            reply_text=reply_text,
            action=action,
            language=active_lang,
            detected_language=session.detected_language,
            language_switched=language_switched,
            tts_metadata=build_tts_metadata(active_lang, session.detected_language),
            form_state=session.record.to_compact_dict(),
            missing_fields=list(session.record.missing_fields),
            visit_type=session.record.visit_type,
            beneficiary_info={
                "name": session.record.beneficiary_name,
                "id": session.record.beneficiary_id,
            },
            danger_detected=len(session.danger_flags) > 0,
            danger_flags=list(session.danger_flags),
            confirmation_required=session.awaiting_confirmation,
            confirmed=session.confirmed,
            follow_up_date=(
                session.record.next_visit_date.isoformat()
                if session.record.next_visit_date
                else None
            ),
            vaccinations=dict(session.record.vaccinations),
            next_actions=self.build_next_actions(session),
            guardrail_triggered=guardrail_triggered,
            guardrail_reason=guardrail_reason,
        )
