"""Structured Pydantic schemas for ASHA household healthcare visit records and API I/O."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from brain.languages import normalize_language_code

LanguageCode = str
VisitType = Literal["anc", "pnc", "newborn", "immunisation", "other"]
VaccinationStatus = Literal[
    "completed", "due", "missed", "refused", "not_applicable", "unknown"
]
IFAStatus = Literal[
    "provided", "not_provided", "refused", "consumed", "already_available", "unknown"
]


class BloodPressure(BaseModel):
    """Systolic and diastolic blood pressure reading in mmHg."""

    systolic: int = Field(..., ge=50, le=260)
    diastolic: int = Field(..., ge=30, le=160)
    raw_text: Optional[str] = None

    @model_validator(mode="after")
    def validate_systolic_gt_diastolic(self) -> "BloodPressure":
        if self.systolic <= self.diastolic:
            raise ValueError("Systolic BP must be greater than diastolic BP.")
        return self

    def formatted(self) -> str:
        return f"{self.systolic}/{self.diastolic}"


class PregnancyInfo(BaseModel):
    """Structured antenatal / pregnancy observations."""

    gestational_months: Optional[float] = Field(default=None, ge=0.5, le=10.5)
    gestational_weeks: Optional[int] = Field(default=None, ge=1, le=45)
    trimester: Optional[int] = Field(default=None, ge=1, le=3)
    anc_visit_number: Optional[int] = Field(default=None, ge=1, le=12)
    high_risk_notes: Optional[str] = None
    raw_observation: Optional[str] = None


class NewbornInfo(BaseModel):
    """Structured newborn baby observations."""

    age_days: Optional[int] = Field(default=None, ge=0, le=365)
    breastfeeding_status: Optional[
        Literal["initiated", "exclusive", "not_initiated", "poor", "unknown"]
    ] = None
    cord_status: Optional[str] = None
    temperature_celsius: Optional[float] = Field(default=None, ge=30.0, le=44.0)
    temperature_fahrenheit: Optional[float] = Field(default=None, ge=85.0, le=112.0)
    birth_weight_kg: Optional[float] = Field(default=None, gt=0.2, le=8.0)
    raw_observation: Optional[str] = None


class DangerFlag(BaseModel):
    """Structured danger-sign detection alert combining Layer 1 and Layer 2 evidence."""

    danger_sign_id: str
    category: str
    english_name: str
    matched_layers: List[Literal["rule_based", "llm"]] = Field(default_factory=list)
    matched_evidence: List[str] = Field(default_factory=list)
    llm_reason: Optional[str] = None
    ambiguous: bool = False
    referral_message: str
    source_reference: str


class VisitRecord(BaseModel):
    """Complete structured ASHA household visit record."""

    beneficiary_name: Optional[str] = None
    beneficiary_id: Optional[str] = None
    visit_type: Optional[VisitType] = None
    visit_date: Optional[date] = None
    weight_kg: Optional[float] = Field(default=None, gt=0.2, le=200.0)
    blood_pressure: Optional[BloodPressure] = None
    pregnancy_info: Optional[PregnancyInfo] = None
    newborn_info: Optional[NewbornInfo] = None
    vaccinations: Dict[str, VaccinationStatus] = Field(default_factory=dict)
    ifa_status: Optional[IFAStatus] = None
    next_visit_date: Optional[date] = None
    ambiguous_next_visit_reference: Optional[str] = None
    danger_signs: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    negative_findings: Dict[str, str] = Field(default_factory=dict)
    unknown_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)

    @field_validator("beneficiary_name")
    @classmethod
    def clean_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None

    @field_validator("beneficiary_id")
    @classmethod
    def clean_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned.upper() if cleaned else None

    @field_validator("weight_kg")
    @classmethod
    def normalize_weight(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return round(float(value), 2)

    @field_validator("visit_type", mode="before")
    @classmethod
    def normalize_visit_type(cls, value: Any) -> Any:
        if isinstance(value, str):
            norm = value.strip().lower()
            aliases = {
                "immunization": "immunisation",
                "vaccination": "immunisation",
                "tika": "immunisation",
                "tikakaran": "immunisation",
                "antenatal": "anc",
                "postnatal": "pnc",
                "newborn_visit": "newborn",
                "general": "other",
            }
            return aliases.get(norm, norm)
        return value

    def to_compact_dict(self) -> Dict[str, Any]:
        """Serialize record using JSON-friendly ISO dates while preserving nullability."""
        return self.model_dump(mode="json")


class ExtractionPayload(BaseModel):
    """Strict schema validated against LLM JSON extraction outputs."""

    beneficiary_name: Optional[str] = None
    beneficiary_id: Optional[str] = None
    visit_type: Optional[VisitType] = None
    weight_kg: Optional[float] = Field(default=None, gt=0.2, le=200.0)
    blood_pressure: Optional[BloodPressure] = None
    pregnancy_info: Optional[PregnancyInfo] = None
    newborn_info: Optional[NewbornInfo] = None
    vaccinations: Dict[str, VaccinationStatus] = Field(default_factory=dict)
    ifa_status: Optional[IFAStatus] = None
    next_visit_date: Optional[date] = None
    raw_next_visit_reference: Optional[str] = None
    ambiguous_next_visit_reference: Optional[str] = None
    danger_sign_observations: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    negative_findings: Dict[str, str] = Field(default_factory=dict)
    unknown_fields: List[str] = Field(default_factory=list)

    @field_validator("visit_type", mode="before")
    @classmethod
    def normalize_visit_type(cls, value: Any) -> Any:
        return VisitRecord.normalize_visit_type(value)

    @field_validator("weight_kg")
    @classmethod
    def round_weight(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return round(float(value), 2)


class CorrectionCandidate(BaseModel):
    """Single field-level voice correction candidate."""

    field_name: str
    new_value: Any
    previous_value_mentioned: Optional[str] = None
    raw_phrase: Optional[str] = None


class CorrectionDetectionResult(BaseModel):
    """Output from voice correction analysis."""

    is_correction: bool = False
    ambiguous_field: bool = False
    clarification_prompt: Optional[str] = None
    corrections: List[CorrectionCandidate] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)


class ProcessTranscriptRequest(BaseModel):
    """Request payload from Person A's voice pipeline to the AI Brain."""

    session_id: str = Field(..., min_length=1, max_length=128)
    transcript: str = Field(..., min_length=1, max_length=4000)
    language: LanguageCode = "hi-en"
    detected_language: Optional[str] = None
    preferred_language: Optional[str] = None
    visit_date: Optional[date] = None
    context: Optional[Dict[str, Any]] = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language_code(value, default="hi-en")


class BrainProcessResponse(BaseModel):
    """Unified response returned to Person A (reply text + TTS metadata) and Person C (form + flags)."""

    session_id: str
    reply_text: str
    action: Literal[
        "collect_info",
        "clarify",
        "confirm_record",
        "refer_danger",
        "refuse_medical_advice",
        "completed",
    ]
    language: str = "hi-en"
    detected_language: Optional[str] = None
    language_switched: bool = False
    tts_metadata: Dict[str, Any] = Field(default_factory=dict)
    form_state: Dict[str, Any]
    missing_fields: List[str] = Field(default_factory=list)
    visit_type: Optional[VisitType] = None
    beneficiary_info: Dict[str, Optional[str]] = Field(default_factory=dict)
    danger_detected: bool = False
    danger_flags: List[DangerFlag] = Field(default_factory=list)
    confirmation_required: bool = False
    confirmed: bool = False
    follow_up_date: Optional[str] = None
    vaccinations: Dict[str, str] = Field(default_factory=dict)
    next_actions: List[str] = Field(default_factory=list)
    guardrail_triggered: bool = False
    guardrail_reason: Optional[str] = None


class ConfirmRequest(BaseModel):
    """Request to handle explicit confirmation, rejection, or inline pre-save correction."""

    session_id: str = Field(..., min_length=1, max_length=128)
    transcript: Optional[str] = Field(default=None, max_length=4000)
    explicit_confirm: Optional[bool] = None
    language: LanguageCode = "hi-en"
    detected_language: Optional[str] = None
    preferred_language: Optional[str] = None
    visit_date: Optional[date] = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language_code(value, default="hi-en")


class ConfirmResponse(BaseModel):
    """Confirmation outcome and storage-ready confirmed payload for Person C."""

    session_id: str
    confirmed: bool
    ready_for_storage: bool
    confirmation_required: bool
    reply_text: str
    readback_text: str
    language: str = "hi-en"
    tts_metadata: Dict[str, Any] = Field(default_factory=dict)
    form_state: Dict[str, Any]
    confirmed_record: Optional[Dict[str, Any]] = None
    missing_fields: List[str] = Field(default_factory=list)
    danger_detected: bool = False
    danger_flags: List[DangerFlag] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)


class CorrectionRequest(BaseModel):
    """Explicit voice correction endpoint request."""

    session_id: str = Field(..., min_length=1, max_length=128)
    transcript: str = Field(..., min_length=1, max_length=4000)
    language: LanguageCode = "hi-en"
    detected_language: Optional[str] = None
    preferred_language: Optional[str] = None
    visit_date: Optional[date] = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language_code(value, default="hi-en")


class CorrectionResponse(BaseModel):
    """Result after processing a voice correction against existing session state."""

    session_id: str
    correction_applied: bool
    updated_fields: List[str] = Field(default_factory=list)
    clarification_needed: bool = False
    reply_text: str
    language: str = "hi-en"
    tts_metadata: Dict[str, Any] = Field(default_factory=dict)
    form_state: Dict[str, Any]
    missing_fields: List[str] = Field(default_factory=list)
    danger_detected: bool = False
    danger_flags: List[DangerFlag] = Field(default_factory=list)
    confirmation_required: bool = False
    confirmed: bool = False


class ReadbackRequest(BaseModel):
    """Request to generate read-back summary for an active session."""

    session_id: str = Field(..., min_length=1, max_length=128)
    language: LanguageCode = "hi-en"

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language_code(value, default="hi-en")


class ReadbackResponse(BaseModel):
    """Read-back text and current completeness metadata."""

    session_id: str
    readback_text: str
    language: str = "hi-en"
    tts_metadata: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    confirmation_required: bool = False
    confirmed: bool = False


class LanguagePreferenceRequest(BaseModel):
    """Explicit mid-conversation session language update without losing form state."""

    language: str = Field(..., min_length=2, max_length=20)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        resolved = normalize_language_code(value)
        if resolved == "auto":
            raise ValueError("Explicit language preference cannot be 'auto'.")
        return resolved


class SessionStateResponse(BaseModel):
    """Inspection response for GET /api/brain/session/{session_id}."""

    session_id: str
    language: str = "hi-en"
    detected_language: Optional[str] = None
    tts_metadata: Dict[str, Any] = Field(default_factory=dict)
    form_state: Dict[str, Any]
    missing_fields: List[str] = Field(default_factory=list)
    visit_type: Optional[VisitType] = None
    beneficiary_info: Dict[str, Optional[str]] = Field(default_factory=dict)
    danger_detected: bool = False
    danger_flags: List[DangerFlag] = Field(default_factory=list)
    confirmation_required: bool = False
    confirmed: bool = False
    follow_up_date: Optional[str] = None
    vaccinations: Dict[str, str] = Field(default_factory=dict)
    next_actions: List[str] = Field(default_factory=list)
    turn_count: int = 0
