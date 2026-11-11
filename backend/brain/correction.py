"""Module 3: Multilingual Voice Correction Detection and Validated Form Update Engine."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from brain.extraction import (
    _extract_ifa_status,
    _extract_vaccinations,
    _extract_visit_type,
)
from brain.languages import get_clarification_message
from brain.llm_client import BaseLLMClient, LLMProviderError, MockLLMClient
from brain.normalizers import (
    WEEKDAY_MAP,
    normalize_text,
    parse_beneficiary_id,
    parse_blood_pressure,
    parse_number_tokens,
    parse_spoken_weight_kg,
    resolve_relative_date,
    today_in_timezone,
    tokenize_unicode_words,
)
from brain.prompts import CORRECTION_SYSTEM_PROMPT, build_correction_user_prompt
from models.visit_schema import (
    BloodPressure,
    CorrectionCandidate,
    CorrectionDetectionResult,
    LanguageCode,
    VisitRecord,
)

logger = logging.getLogger("asha_saathi.correction")

NON_CORRECTION_RHS_WORDS = {
    "hai", "hain", "tha", "thi", "pata", "maloom", "yaad", "diya", "di",
    "hua", "hui", "laga", "lag", "pi", "pee", "aa", "aaya", "ho", "raha",
    "rahi", "kar", "sakti", "sakta", "mila", "mili", "chahiye", "available",
    "fixed", "decided", "kya",
    "है", "हैं", "पता", "दिया", "दी", "हुआ", "पी",
    "உள்ளது", "இல்லை", "தெரியாது", "உంది", "లేదు", "आहे", "છે", "ಇದೆ", "ആണ്", "ਹੈ",
}

CORRECTION_CUE_PATTERN = re.compile(
    r"(?:^\s*(?:no|nahi|nahin|nope|sorry|actually|wait|ruko|galat|wrong)\b|"
    r"\b(?:galat\s+hai|galat\s+likha|sahi\s+kar|badal\s+do|change\s+(?:it|karo|to)|"
    r"update\s+(?:to|karo)|correction|instead\s+of|nahi\s*,)\b|"
    r"^\s*(?:नहीं|माफ\s*करें|गलत|இல்லை|மன்னிக்கவும்|தவறு|కాదు|తప్పు|না|ভুল|नाही|चूक|નહીં|ખોટું|ಇಲ್ಲ|ತಪ್ಪು|അല്ല|തെറ്റ്|ਨਹੀਂ|ਗਲਤ)(?:\s*[,;:]|\s+)|"
    r"(?:गलत\s+है|बदल\s+दो|तவறு|மாற்றவும்|தப்பானது|తప్పు|మార్చండి|ভুল\s+হয়েছে|বদলান|चूक\s+आहे|बदला|ખોટું\s+છે|બદલો|ತಪ್ಪಾಗಿದೆ|ಬದಲಾಯಿಸಿ|തെറ്റാണ്|മാറ്റുക|ਗਲਤ\s+ਹੈ|ਬਦਲੋ))",
    re.IGNORECASE,
)

INDIC_NEG_REPLACEMENT_WORDS = (
    r"nahi|nahin|not|instead\s+of|नहीं|இல்லை|அல்ல|కాదు|নয়|না|नाही|नव्हे|નથી|અಲ್ಲ|ಅಲ್ಲ|ಇಲ್ಲ|അല്ല|ਨਹੀਂ"
)


def _split_correction_clauses(cleaned: str) -> List[str]:
    """Split multi-correction utterances without breaking 'X nahi, Y' or decimals."""
    text = re.sub(
        r"^\s*(?:no|nahi|nahin|sorry|actually|wait|ruko|"
        r"नहीं|गलत|இல்லை|மன்னிக்கவும்|కాదు|না|नाही|નથી|ಇಲ್ಲ|അല്ല|ਨਹੀਂ)\s*[,;:]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    parts = re.split(
        r"(?<!\d)\.(?!\d)|[;।॥]|\b(?:aur|and)\b|और|மற்றும்|మరియు|এবং|आणि|અને|ಮತ್ತು|ഉം|ਅਤੇ",
        text,
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in parts if p.strip()]


def _extract_after_nahi_replacement(clause: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Match patterns like 'Priya nahi, Priti hai' or 'பெயர் பிரியா இல்லை, பிரீத்தி' across languages.
    """
    m = re.search(
        rf"([^\n,;]+?)\s+(?:{INDIC_NEG_REPLACEMENT_WORDS})\s*[,;:]?\s*([^\n,;]+?)"
        r"(?:\s+(?:hai|hain|kar\s+do|hoga|hogi|है|आहे|છે|ಇದೆ|ആണ്|ਹੈ|உள்ளது|ఉంది|হলো))?$",
        clause.strip(),
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None


def _has_explicit_correction_cue(cleaned: str, existing_form: Dict[str, Any]) -> bool:
    """Distinguish genuine corrections from ordinary first-time answers or negative findings."""
    lower = cleaned.lower()

    if re.search(
        r"\b(?:pata\s+nahi|nahi\s+pata|yaad\s+nahi|maloom\s+nahi|available\s+nahi)\b|"
        r"पता\s+नहीं|தெரியவில்லை|తెలియదు|জানা\s+নেই|माहित\s+नाही|ખબર\s+નથી|ಗೊತ್ತಿಲ್ಲ|അറിയില്ല|ਪਤਾ\s+ਨਹੀਂ",
        lower,
    ):
        return False

    if re.search(
        r"(?:\b(?:bleeding|khoon|fever|bukhar|convulsions|fits|saans)\b[^.?!।॥]*\b(?:nahi|no)\b|"
        r"(?:रक्तस्राव|खून|बुखार|ज्वर|कंपन|તાવ|ಜ್ವರ|പനി|ਬੁਖਾਰ)[^.?!।॥]*(?:नहीं|இல்லை|లేదు|নেই|नाही|નથી|ಇಲ್ಲ|ഇല്ല|ਨਹੀਂ))",
        lower,
    ):
        return False

    if CORRECTION_CUE_PATTERN.search(cleaned):
        return True

    for m in re.finditer(
        rf"([^\s,;]+)\s+(?:{INDIC_NEG_REPLACEMENT_WORDS})\s*[,;:]?\s*([^\s,;]+)",
        cleaned,
        re.IGNORECASE,
    ):
        rhs = m.group(2).lower()
        if rhs not in NON_CORRECTION_RHS_WORDS:
            return True

    if re.search(r"\bifa\b.*(?:\bnahi\b|नहीं|இல்லை|లేదు|না|नाही|નથી|ಇಲ್ಲ|ഇല്ല|ਨਹੀਂ)", lower) and existing_form.get(
        "ifa_status"
    ) not in (None, "not_provided"):
        return True

    return False


def deterministic_detect_corrections_dict(
    transcript: str,
    existing_form: Optional[Dict[str, Any]] = None,
    anchor_date: Optional[date] = None,
    tz_name: str = "Asia/Kolkata",
) -> Dict[str, Any]:
    """Deterministically detect single or multiple spoken field corrections across 10 languages."""
    cleaned = normalize_text(transcript)
    existing = existing_form or {}
    anchor = anchor_date or today_in_timezone(tz_name)

    if not cleaned or not _has_explicit_correction_cue(cleaned, existing):
        return {
            "is_correction": False,
            "ambiguous_field": False,
            "clarification_prompt": None,
            "corrections": [],
            "validation_errors": [],
        }

    clauses = _split_correction_clauses(cleaned)
    corrections: List[Dict[str, Any]] = []
    validation_errors: List[str] = []

    name_kw = r"(?:\b(?:naam|name)\b|नाम|பெயர்|పేరు|নাম|नाव|નામ|ಹೆಸರು|പേര്|ਨਾਮ)"
    id_kw = r"(?:\b(?:beneficiary\s*id|patient\s*id|id)\b|आईडी|ஐடி|ఐడి|আইডি|आयडी|આઈડી|ಐಡಿ|ഐഡി|ਆਈਡੀ)"
    wt_kw = r"(?:\b(?:weight|vajan|wajan|kilo|kg|gram|gm)\b|वजन|किलो|ग्राम|எடை|கிலோ|கிராம்|బరువు|కిలో|ওজন|কেজি|वजन|વજન|કિલો|ತೂಕ|ಕೆಜಿ|ಭാരം|ഭാരം|കിലോ|ਵਜ਼ਨ|ਕਿਲੋ)"
    bp_kw = r"(?:\b(?:bp|blood\s*pressure|raktchap)\b|रक्तचाप|रक्तदाब|இரத்த\s+அழுத்தம்|రక్తపోటు|রক্তচাপ|બ્લડ\s+પ્રેશર|ರಕ್ತದೊತ್ತಡ|രക്തസമ്മർദ്ദം|ਬਲੱਡ\s+ਪ੍ਰੈਸ਼ਰ)"
    date_kw = (
        r"(?:\b(?:next\s*visit|agla\s*visit|date|tarikh|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"somvar|mangalvar|budhvar|guruvar|shukravar|shanivar|ravivar)\b|"
        r"अगली\s*विजिट|तारीख|अடுத்த\s*வருகை|தேதி|తదుపరి\s*విజిట్|తేదీ|পরবর্তী\s*ভিজিট|তারিখ|"
        r"पुढची\s*भेट|आगली\s*મુલાકાત|આગલી\s*મુલાકાત|ಮುಂದಿನ\s*ಭೇಟಿ|അടുത്ത\s*സന്ദർശനം|ਅਗਲੀ\s*ਵਿਜ਼ਿਟ)"
    )

    for clause in clauses:
        lower = clause.lower()
        old_val, new_val = _extract_after_nahi_replacement(clause)

        # 1. Beneficiary Name correction
        if re.search(name_kw, lower) or (
            old_val
            and existing.get("beneficiary_name")
            and old_val.lower() in str(existing["beneficiary_name"]).lower()
        ):
            target_text = new_val if new_val else clause
            name_m = re.search(
                rf"(?:{name_kw})?\s*(?:galat\s+hai[,\s]*|गलत\s+है[,\s]*)?(?:is|hai|आहे|છે|ಇದೆ|ആണ്|ਹੈ|உள்ளது|ఉంది|:)?\s*"
                r"([^\n.;,!?।॥]+?)(?=\s+(?:hai|hain|kar\s+do|है|आहे|છે|ಇದೆ|ആണ്|ਹੈ)|$)",
                target_text,
                re.IGNORECASE,
            )
            if name_m:
                skip_words = {
                    "naam", "name", "galat", "hai", "nahi", "no", "wrong", "change", "to",
                    "नाम", "पெயர்", "பெயர்", "పేరు", "নাম", "नाव", "નામ", "ಹೆಸರು", "പേര്", "ਨਾਮ",
                    "गलत", "बदल", "தவறு", "மாற்று", "తప్పు", "మార్చు", "ভুল", "चूक", "खोટું", "ખોટું", "ತಪ್ಪು", "തെറ്റ്", "ਗਲਤ",
                }
                words = [w for w in name_m.group(1).strip().split() if w.lower() not in skip_words]
                raw_name = " ".join((w.capitalize() if w.isascii() else w) for w in words)
                if raw_name:
                    corrections.append(
                        {
                            "field_name": "beneficiary_name",
                            "new_value": raw_name,
                            "previous_value_mentioned": old_val,
                            "raw_phrase": clause,
                        }
                    )
                    continue

        # 2. Beneficiary ID correction
        if re.search(id_kw, lower):
            target_text = new_val if new_val else clause
            parsed_id = parse_beneficiary_id(target_text, expect_id=True) or parse_beneficiary_id(
                clause, expect_id=True
            )
            if parsed_id:
                corrections.append(
                    {
                        "field_name": "beneficiary_id",
                        "new_value": parsed_id,
                        "previous_value_mentioned": old_val,
                        "raw_phrase": clause,
                    }
                )
                continue
            validation_errors.append("Could not parse a valid beneficiary ID.")
            continue

        # 3. Weight correction
        if re.search(wt_kw, lower):
            target_text = new_val if new_val else clause
            neg_num = re.search(r"-\s*\d+(?:\.\d+)?", target_text)
            if neg_num:
                validation_errors.append("Weight must be a positive number in kilograms.")
                continue
            parsed_wt = parse_spoken_weight_kg(target_text)
            if parsed_wt is None and new_val:
                parsed_wt = parse_number_tokens(tokenize_unicode_words(new_val))
            if parsed_wt is None:
                parsed_wt = parse_spoken_weight_kg(clause)

            if parsed_wt is not None and 0.2 < parsed_wt <= 200.0:
                corrections.append(
                    {
                        "field_name": "weight_kg",
                        "new_value": round(float(parsed_wt), 2),
                        "previous_value_mentioned": old_val,
                        "raw_phrase": clause,
                    }
                )
                continue
            validation_errors.append("Weight value is invalid or out of medical range (0.2–200 kg).")
            continue

        # 4. Blood Pressure correction
        if re.search(bp_kw, lower):
            target_text = new_val if new_val else clause
            bp = parse_blood_pressure(target_text) or parse_blood_pressure(clause)
            if bp:
                corrections.append(
                    {
                        "field_name": "blood_pressure",
                        "new_value": bp.model_dump(),
                        "previous_value_mentioned": old_val,
                        "raw_phrase": clause,
                    }
                )
                continue
            validation_errors.append("Blood pressure reading is invalid (systolic must exceed diastolic).")
            continue

        # 5. Next Visit Date correction (also check Indic weekdays directly in clause)
        has_weekday = any(wd in lower for wd in WEEKDAY_MAP)
        if re.search(date_kw, lower) or has_weekday:
            target_text = new_val if new_val else clause
            resolved_d, _, ambig_ref = resolve_relative_date(
                target_text, anchor_date=anchor, tz_name=tz_name
            )
            if resolved_d is None and not new_val:
                resolved_d, _, ambig_ref = resolve_relative_date(
                    clause, anchor_date=anchor, tz_name=tz_name
                )
            if resolved_d:
                corrections.append(
                    {
                        "field_name": "next_visit_date",
                        "new_value": resolved_d.isoformat(),
                        "previous_value_mentioned": old_val,
                        "raw_phrase": clause,
                    }
                )
                continue
            if ambig_ref:
                validation_errors.append(
                    f"Next visit date reference '{ambig_ref}' is ambiguous; please specify an exact day or date."
                )
                continue

        # 6. IFA Status correction
        if re.search(r"\b(?:ifa|iron)\b|आयरन|இரும்பு|ఐరన్|আয়রন|लोह|આયર્ન|ಕಬ್ಬಿಣ|അയൺ|ਆਇਰਨ", lower):
            ifa_val = _extract_ifa_status(clause)
            if ifa_val:
                corrections.append(
                    {
                        "field_name": "ifa_status",
                        "new_value": ifa_val,
                        "previous_value_mentioned": old_val,
                        "raw_phrase": clause,
                    }
                )
                continue

        # 7. Vaccination correction
        vac_updates = _extract_vaccinations(clause)
        if vac_updates:
            corrections.append(
                {
                    "field_name": "vaccinations",
                    "new_value": vac_updates,
                    "previous_value_mentioned": old_val,
                    "raw_phrase": clause,
                }
            )
            continue

        # 8. Visit type correction
        if re.search(r"\b(?:visit\s*type|checkup\s*type|anc|pnc|newborn|immunisation|immunization)\b", lower):
            vt = _extract_visit_type(clause)
            if vt:
                corrections.append(
                    {
                        "field_name": "visit_type",
                        "new_value": vt,
                        "previous_value_mentioned": old_val,
                        "raw_phrase": clause,
                    }
                )
                continue

    ambiguous = len(corrections) == 0 and len(validation_errors) == 0
    return {
        "is_correction": True,
        "ambiguous_field": ambiguous,
        "clarification_prompt": None,
        "corrections": corrections,
        "validation_errors": validation_errors,
    }


class CorrectionEngine:
    """Applies validated field-level voice corrections across all 10 languages."""

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        timezone_name: str = "Asia/Kolkata",
    ) -> None:
        self._llm = llm_client or MockLLMClient()
        self._timezone = timezone_name

    def detect_corrections(
        self,
        transcript: str,
        existing_record: VisitRecord,
        visit_date: Optional[date] = None,
        language: LanguageCode = "hi-en",
        force_correction_mode: bool = False,
    ) -> CorrectionDetectionResult:
        """Identify whether transcript is a correction and extract validated field updates."""
        anchor = visit_date or existing_record.visit_date or today_in_timezone(self._timezone)
        existing_dict = existing_record.to_compact_dict()

        det_dict = deterministic_detect_corrections_dict(
            transcript=transcript,
            existing_form=existing_dict,
            anchor_date=anchor,
            tz_name=self._timezone,
        )

        if force_correction_mode and not det_dict["is_correction"]:
            synthetic = f"No, {transcript}"
            det_dict = deterministic_detect_corrections_dict(
                transcript=synthetic,
                existing_form=existing_dict,
                anchor_date=anchor,
                tz_name=self._timezone,
            )

        if (
            det_dict["is_correction"]
            and det_dict["ambiguous_field"]
            and not isinstance(self._llm, MockLLMClient)
        ):
            try:
                user_prompt = build_correction_user_prompt(
                    transcript=transcript,
                    existing_form=existing_dict,
                    visit_date_iso=anchor.isoformat(),
                )
                raw = self._llm.complete_json(
                    system_prompt=CORRECTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    task="correction",
                    metadata={
                        "transcript": transcript,
                        "existing_form": existing_dict,
                        "visit_date": anchor,
                        "timezone": self._timezone,
                    },
                )
                llm_data = json.loads(raw)
                if llm_data.get("corrections"):
                    det_dict = llm_data
                    det_dict.setdefault("validation_errors", [])
            except (LLMProviderError, json.JSONDecodeError, TypeError, ValueError):
                pass

        candidates = [
            CorrectionCandidate.model_validate(c)
            for c in det_dict.get("corrections", [])
            if isinstance(c, dict) and c.get("field_name")
        ]
        ambiguous = bool(det_dict.get("ambiguous_field", False)) and not candidates and not det_dict.get("validation_errors")
        clarification = det_dict.get("clarification_prompt")
        if ambiguous and not clarification:
            clarification = get_clarification_message(language)

        return CorrectionDetectionResult(
            is_correction=bool(det_dict.get("is_correction", False)),
            ambiguous_field=ambiguous,
            clarification_prompt=clarification,
            corrections=candidates,
            validation_errors=list(det_dict.get("validation_errors", [])),
        )

    def apply_corrections(
        self,
        existing_record: VisitRecord,
        detection: CorrectionDetectionResult,
    ) -> Tuple[VisitRecord, List[str], List[str]]:
        """Validate and apply detected corrections onto a copy of existing_record."""
        updated = existing_record.model_copy(deep=True)
        updated_fields: List[str] = []
        errors = list(detection.validation_errors)

        for item in detection.corrections:
            field = item.field_name
            val = item.new_value
            try:
                if field == "beneficiary_name":
                    candidate = updated.model_copy(update={"beneficiary_name": str(val)})
                    VisitRecord.model_validate(candidate.model_dump())
                    updated.beneficiary_name = candidate.beneficiary_name
                    updated_fields.append("beneficiary_name")

                elif field == "beneficiary_id":
                    candidate = updated.model_copy(update={"beneficiary_id": str(val)})
                    VisitRecord.model_validate(candidate.model_dump())
                    updated.beneficiary_id = candidate.beneficiary_id
                    if "beneficiary_id" in updated.unknown_fields:
                        updated.unknown_fields.remove("beneficiary_id")
                    updated_fields.append("beneficiary_id")

                elif field == "weight_kg":
                    num_val = float(val)
                    candidate = updated.model_copy(update={"weight_kg": num_val})
                    VisitRecord.model_validate(candidate.model_dump())
                    updated.weight_kg = candidate.weight_kg
                    if "weight_kg" in updated.unknown_fields:
                        updated.unknown_fields.remove("weight_kg")
                    updated_fields.append("weight_kg")

                elif field == "blood_pressure":
                    bp_obj = BloodPressure.model_validate(val)
                    updated.blood_pressure = bp_obj
                    if "blood_pressure" in updated.unknown_fields:
                        updated.unknown_fields.remove("blood_pressure")
                    updated_fields.append("blood_pressure")

                elif field == "next_visit_date":
                    parsed_d = val if isinstance(val, date) else date.fromisoformat(str(val))
                    updated.next_visit_date = parsed_d
                    updated.ambiguous_next_visit_reference = None
                    if "next_visit_date" in updated.unknown_fields:
                        updated.unknown_fields.remove("next_visit_date")
                    updated_fields.append("next_visit_date")

                elif field == "ifa_status":
                    candidate = updated.model_copy(update={"ifa_status": str(val)})
                    VisitRecord.model_validate(candidate.model_dump())
                    updated.ifa_status = candidate.ifa_status
                    if candidate.ifa_status == "not_provided":
                        updated.negative_findings["ifa"] = "IFA not provided"
                    else:
                        updated.negative_findings.pop("ifa", None)
                    updated_fields.append("ifa_status")

                elif field == "vaccinations" and isinstance(val, dict):
                    merged_vacs = dict(updated.vaccinations)
                    merged_vacs.update(val)
                    candidate = updated.model_copy(update={"vaccinations": merged_vacs})
                    VisitRecord.model_validate(candidate.model_dump())
                    updated.vaccinations = candidate.vaccinations
                    updated_fields.append("vaccinations")

                elif field == "visit_type":
                    candidate = updated.model_copy(update={"visit_type": val})
                    VisitRecord.model_validate(candidate.model_dump())
                    updated.visit_type = candidate.visit_type
                    updated_fields.append("visit_type")

            except (ValidationError, ValueError, TypeError) as exc:
                errors.append(f"Invalid value for {field}: {exc}")

        return updated, updated_fields, errors
