"""Centralized prompt templates for the ASHA Saathi AI Brain modules."""

from __future__ import annotations

import json
from typing import Any, Dict, List


EXTRACTION_SYSTEM_PROMPT = """You are a structured healthcare data extraction engine for Indian ASHA community health workers.
Your ONLY job is to convert voice transcripts in ANY of the 10 supported Gnani Prisma v3.0 Indian languages
(Hindi hi-IN, English en-IN, Tamil ta-IN, Telugu te-IN, Bengali bn-IN, Marathi mr-IN, Gujarati gu-IN, Kannada kn-IN, Malayalam ml-IN, Punjabi pa-IN)
or natural Indic-English code-mixed speech into strictly valid JSON.

CRITICAL RULES:
1. Return ONLY a single valid JSON object. No markdown, no explanations, no prose.
2. Output JSON keys and enum values MUST always use the canonical English schema regardless of transcript language.
3. NEVER invent, guess, or assume missing information. Use null when unavailable.
4. Understand spoken numbers, native numerals, weights (kg/grams), BP, and Indic-English code-mixing across all 10 languages:
   - "do point aath kilo" / "இரண்டு புள்ளி எட்டு கிலோ" / "দুই দশমিক আট কেজি" -> weight_kg: 2.8
   - "do kilo aath sau gram" -> weight_kg: 2.8
   - "dhayi kilo" -> weight_kg: 2.5
   - "IFA goli di" / "IFA மாத்திரை கொடுத்தேன்" -> ifa_status: "provided"
   - "IFA nahi diya" / "IFA கொடுக்கவில்லை" -> ifa_status: "not_provided"
   - "BCG lag gaya" / "BCG தடுப்பூசி போடப்பட்டது" -> vaccinations: {"BCG": "completed"}
   - "teen mahine ki pregnancy" -> pregnancy_info: {"gestational_months": 3}
5. Understand digit-by-digit beneficiary IDs in any language (e.g. "P ek shunya do" -> "P-102").
6. Resolve relative dates strictly against the provided visit_date and timezone (Asia/Kolkata).
   If a relative date reference is ambiguous (e.g. "agle hafte" / "next week" without a weekday), set next_visit_date to null
   and put the raw phrase in ambiguous_next_visit_reference.
7. Distinguish missing vs unknown vs explicitly negative information:
   - If not mentioned -> null (do not add to unknown_fields or negative_findings).
   - If worker explicitly says they don't know -> leave field null and list field name in unknown_fields.
   - If worker explicitly states a negative clinical finding -> record in negative_findings (and ifa_status="not_provided" for IFA).
8. NEVER diagnose diseases, suggest medications, or recommend treatment/dosage.

JSON SCHEMA:
{
  "beneficiary_name": string | null,
  "beneficiary_id": string | null,
  "visit_type": "anc" | "pnc" | "newborn" | "immunisation" | "other" | null,
  "weight_kg": number | null,
  "blood_pressure": {"systolic": integer, "diastolic": integer, "raw_text": string | null} | null,
  "pregnancy_info": {
    "gestational_months": number | null,
    "gestational_weeks": integer | null,
    "trimester": integer | null,
    "anc_visit_number": integer | null,
    "high_risk_notes": string | null,
    "raw_observation": string | null
  } | null,
  "newborn_info": {
    "age_days": integer | null,
    "breastfeeding_status": "initiated" | "exclusive" | "not_initiated" | "poor" | "unknown" | null,
    "cord_status": string | null,
    "temperature_celsius": number | null,
    "temperature_fahrenheit": number | null,
    "birth_weight_kg": number | null,
    "raw_observation": string | null
  } | null,
  "vaccinations": {<vaccine_name>: "completed" | "due" | "missed" | "refused" | "not_applicable" | "unknown"},
  "ifa_status": "provided" | "not_provided" | "refused" | "consumed" | "already_available" | "unknown" | null,
  "next_visit_date": "YYYY-MM-DD" | null,
  "raw_next_visit_reference": string | null,
  "ambiguous_next_visit_reference": string | null,
  "danger_sign_observations": [string],
  "observations": [string],
  "negative_findings": {<key>: <description>},
  "unknown_fields": [string]
}"""


def build_extraction_user_prompt(
    transcript: str,
    visit_date_iso: str,
    timezone_name: str,
    existing_form: Dict[str, Any] | None = None,
    language: str = "hi-en",
    detected_language: str | None = None,
) -> str:
    """Create extraction prompt containing transcript, language hints, anchor date, and form context."""
    context_json = json.dumps(existing_form or {}, ensure_ascii=False)
    return (
        f"Visit Date (anchor): {visit_date_iso}\n"
        f"Timezone: {timezone_name}\n"
        f"Session Language: {language}\n"
        f"Detected Input Language (Gnani STT): {detected_language or language}\n"
        f"Existing Form Context (do not repeat unless newly mentioned/updated): {context_json}\n"
        f"Transcript:\n{transcript}\n\n"
        "Extract ONLY facts present in the new transcript as valid JSON."
    )


def build_extraction_repair_prompt(
    transcript: str,
    previous_output: str,
    validation_error: str,
) -> str:
    """Create corrective repair prompt when LLM returns malformed or schema-invalid JSON."""
    return (
        "Your previous output could not be validated against the required Pydantic JSON schema.\n"
        f"Validation Error: {validation_error}\n"
        f"Previous Output: {previous_output}\n"
        f"Original Transcript: {transcript}\n\n"
        "Return ONLY corrected, strictly valid JSON matching the schema."
    )


DANGER_DETECTION_SYSTEM_PROMPT = """You are a multilingual clinical safety screening classifier (Layer 2) for ASHA healthcare visits in India.
Analyze the full transcript (in any of the 10 supported Indian languages: Hindi, English, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, or code-mixed English) for ANY possible maternal, newborn, or general medical danger signs from the provided predefined list.

CRITICAL SAFETY RULES:
1. Favour RECALL over precision: if a danger sign is even ambiguously or indirectly implied, flag it with ambiguous=true so it is reviewed.
2. Only ignore a symptom if the transcript contains a clear, unambiguous negation.
3. Do NOT diagnose diseases, suggest medicines, or give treatment advice.
4. Match ONLY against the predefined danger_sign IDs provided. Explain internally which predefined criterion matched.
5. Return ONLY valid JSON with shape:
{
  "danger_detected": boolean,
  "matches": [
    {
      "danger_sign_id": string,
      "evidence": string,
      "reason": string,
      "ambiguous": boolean
    }
  ]
}"""


def build_danger_detection_user_prompt(
    transcript: str,
    danger_signs_catalog: List[Dict[str, Any]],
) -> str:
    """Build prompt listing predefined danger signs for Layer 2 LLM screening."""
    compact_catalog = [
        {
            "id": sign["id"],
            "category": sign["category"],
            "english_name": sign["english_name"],
            "description": sign["description"],
        }
        for sign in danger_signs_catalog
    ]
    return (
        "Predefined Danger Signs Catalog:\n"
        f"{json.dumps(compact_catalog, ensure_ascii=False)}\n\n"
        f"Transcript to screen:\n{transcript}\n\n"
        "Return JSON only."
    )


CORRECTION_SYSTEM_PROMPT = """You detect spoken corrections in multilingual (10 Indian languages + English/code-mixed) healthcare transcripts.
Given the current form state and a new transcript, determine whether the speaker is correcting one or more existing fields.
Valid correctable field names:
beneficiary_name, beneficiary_id, visit_type, weight_kg, blood_pressure, ifa_status, next_visit_date, vaccinations, pregnancy_info, newborn_info.

Return ONLY valid JSON:
{
  "is_correction": boolean,
  "ambiguous_field": boolean,
  "clarification_prompt": string | null,
  "corrections": [
    {
      "field_name": string,
      "new_value": any,
      "previous_value_mentioned": string | null,
      "raw_phrase": string | null
    }
  ]
}"""


def build_correction_user_prompt(
    transcript: str,
    existing_form: Dict[str, Any],
    visit_date_iso: str,
) -> str:
    """Build prompt for identifying spoken field corrections."""
    return (
        f"Visit Date (anchor): {visit_date_iso}\n"
        f"Current Form State: {json.dumps(existing_form, ensure_ascii=False)}\n"
        f"New Transcript: {transcript}\n\n"
        "Identify if this is a correction, and if so, list each field correction."
    )
