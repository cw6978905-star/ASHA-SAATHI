"""Module 1: AI Information Extraction Engine with Pydantic validation and retry repair."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from brain.llm_client import BaseLLMClient, LLMProviderError
from brain.normalizers import (
    MONTH_MAP,
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
from brain.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_repair_prompt,
    build_extraction_user_prompt,
)
from models.visit_schema import ExtractionPayload, PregnancyInfo, NewbornInfo

logger = logging.getLogger("asha_saathi.extraction")

NON_NAME_WORDS = {
    "baby",
    "baccha",
    "bachcha",
    "bacha",
    "infant",
    "newborn",
    "navjat",
    "shishu",
    "patient",
    "mahila",
    "mother",
    "maa",
    "woman",
    "lady",
    "unke",
    "unka",
    "unki",
    "uska",
    "uski",
    "uske",
    "aaj",
    "maine",
    "mene",
    "humne",
    "kal",
    "next",
    "visit",
    "checkup",
    "anc",
    "pnc",
    "beneficiary",
    "id",
    "weight",
    "bcg",
    "opv",
    "ifa",
    "ek",
    "do",
    "is",
    "us",
    "koi",
    "new",
    "born",
    "today",
    "abhi",
    "pata",
    "nahi",
    "nahin",
    "hai",
    "hain",
    "maloom",
    "yaad",
    "unknown",
    "galat",
    "number",
    "ho",
    "gaya",
    "lag",
    "आज", "मैंने", "मरीज", "रोगी", "बच्चा", "नवजात", "शिशु", "महिला", "गर्भवती", "माँ",
    "இன்று", "நான்", "குழந்தை", "பிறந்த", "நோயாளி", "தாய்", "கர்ப்பிணி",
    "ఈరోజు", "నేను", "బిడ్డ", "శిశువు", "రోగి", "తల్లి", "గర్భిణి",
    "আজ", "আমি", "শিশু", "নবজাতক", "রোগী", "মা", "গর্ভবতী",
    "आज", "मी", "बाळ", "रुग्ण", "आई", "गरोदर", "नवजात",
    "આજે", "મેં", "બાળક", "દર્દી", "માતા", "સગર્ભા", "નવજાત",
    "ಇಂದು", "ನಾನು", "ಮಗು", "ರೋಗಿ", "ತಾಯಿ", "ಗರ್ಭಿಣಿ", "ನವಜಾತ",
    "ഇന്ന്", "ഞാൻ", "കുഞ്ഞ്", "രോഗി", "അമ്മ", "ഗർഭിണി", "നവജാത",
    "ਅੱਜ", "ਮੈਂ", "ਬੱਚਾ", "ਮਰੀਜ਼", "ਮਾਂ", "ਗਰਭਵਤੀ", "ਨਵਜੰਮੇ",
    "है", "आहे", "છે", "ಇದೆ", "ആണ്", "ਹੈ", "உள்ளது", "ఉంది", "আছে",
    "का", "की", "के", "चा", "ची", "चे", "यांची", "ਦਾ", "ਦੀ", "ਦੇ",
    "नो", "ની", "નું", "નો", "அவர்களின்", "యొక్క", "এর", "ಅವರ", "യുടെ",
}

VACCINE_CANONICAL: Dict[str, str] = {
    "bcg": "BCG",
    "opv-0": "OPV-0",
    "opv 0": "OPV-0",
    "opv0": "OPV-0",
    "opv-1": "OPV-1",
    "opv 1": "OPV-1",
    "opv-2": "OPV-2",
    "opv 2": "OPV-2",
    "opv-3": "OPV-3",
    "opv 3": "OPV-3",
    "opv": "OPV",
    "polio": "OPV",
    "hepatitis b": "HepB",
    "hep b": "HepB",
    "hepb": "HepB",
    "pentavalent": "Pentavalent",
    "penta-1": "Penta-1",
    "penta 1": "Penta-1",
    "penta-2": "Penta-2",
    "penta 2": "Penta-2",
    "penta-3": "Penta-3",
    "penta 3": "Penta-3",
    "penta": "Pentavalent",
    "rotavirus": "Rotavirus",
    "rota": "Rotavirus",
    "pcv": "PCV",
    "ipv": "IPV",
    "measles": "MR",
    "mr": "MR",
    "dpt": "DPT",
    "tt": "TT",
    "td": "Td",
}


class ExtractionValidationError(RuntimeError):
    """Raised when LLM output fails JSON/Pydantic validation after all retries."""


def _strip_json_fences(raw_text: str) -> str:
    text = raw_text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _extract_beneficiary_name(text: str) -> Optional[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return None

    # 1. Explicit name patterns in English, Romanized Hindi, and native Indic scripts
    patterns = [
        r"(?:naam|name)\s*(?:is|hai|:|=)?\s*([A-Za-z][A-Za-z\s]{1,35}?)(?=\s+(?:hai|hain|ka|ki|ke|nahi|aur|is|visit|weight|beneficiary|id)\b|[.,;?!]|$)",
        r"(?:नाम|பெயர்|పేరు|নাম|नाव|નામ|ಹೆಸರು|പേര്|ਨਾਮ)\s*(?:है|आहे|உள்ளது|ఉంది|হলো|হল|છે|ಇದೆ|ആണ്|ਹੈ|:|=)?\s*([^\s.,;!?।॥]+(?:\s+[^\s.,;!?।॥]+){0,2})",
        r"(?:beneficiary|patient)\s+(?:ka\s+naam|name)\s*(?:is|hai|:|=)?\s*([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
        r"(?:maine|mene|humne|aaj)\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})\s+(?:ka|ki|ke)\s+(?:anc|pnc|newborn|immunisation|immunization|vaccination|checkup|visit)",
        r"(?:^|[.,;]\s*)([A-Za-z]+(?:\s+[A-Za-z]+){0,2})\s+(?:ka|ki|ke)\s+(?:anc|pnc|newborn|immunisation|immunization|vaccination|checkup|visit)",
        r"(?:checkup|visit)\s+(?:of|for)\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
    ]
    for pat in patterns:
        match = re.search(pat, cleaned, re.IGNORECASE)
        if not match:
            continue
        candidate = " ".join(match.group(1).strip().split())
        words = candidate.split()
        filtered = [w for w in words if w.lower() not in NON_NAME_WORDS]
        if not filtered:
            continue
        final_name = " ".join((w.capitalize() if w.isascii() else w) for w in filtered[:3])
        if len(final_name) >= 2:
            return final_name

    # 2. Native Indic possessive pattern: "<Name> <genitive?> <visit_keyword>"
    indic_visit_kw = (
        r"(?:anc|pnc|newborn|immunisation|immunization|vaccination|"
        r"चेकअप|जांच|तपासणी|तपास|பரிசோதனை|தடுப்பூசி|పరీక్ష|తనిఖీ|టీకా|পরীক্ষা|টিকা|"
        r"તપાસ|રસીકરણ|ತಪಾಸಣೆ|ಲಸಿಕೆ|പരിശോധന|വാക്സിനേഷൻ|ਜਾਂਚ|ਟੀਕਾਕਰਨ|"
        r"गर्भवती|नवजात|பிறந்த\s+குழந்தை|నవజాత|নবজাতক|नवजात|નવજાત|ನವಜಾತ|നവജാത|ਨਵਜੰਮੇ)"
    )
    indic_pat = re.search(
        rf"([^\n.,;!?।॥]{{2,50}}?)\s+(?:का|की|के|चा|ची|चे|यांची|அவர்களின்|அவரது|యొక్క|గారి|এর|नो|નો|ની|નું|ಅವರ|യുടെ|ਦਾ|ਦੀ|ਦੇ)\s+{indic_visit_kw}",
        cleaned,
        re.IGNORECASE,
    )
    if indic_pat:
        seg_words = indic_pat.group(1).strip().split()
        filtered = [w for w in seg_words if w.lower() not in NON_NAME_WORDS]
        if filtered:
            # Take up to last 3 non-filler tokens right before genitive particle
            name_words = filtered[-3:]
            return " ".join((w.capitalize() if w.isascii() else w) for w in name_words)

    return None


def _extract_visit_type(text: str) -> Optional[str]:
    lower = normalize_text(text).lower()
    if re.search(
        r"\b(?:newborn|new\s+born|navjat|shishu|baby\s+checkup|birth\s+weight)\b|"
        r"(?:नवजात|शिशु|பிறந்த\s*குழந்தை|నవజాత|নবজাতক|નવજાત|ನವಜಾತ|നവജാത|ਨਵਜੰਮੇ)",
        lower,
    ):
        return "newborn"
    if re.search(
        r"\b(?:anc|antenatal|garbhavati|pregnant|pregnancy|mahine\s+ki\s+pregnancy|trimester)\b|"
        r"(?:गर्भवती|गर्भावस्था|प्रसव\s*पूर्व|கர்ப்பிணி|கர்ப்பம்|గర్భిణి|గర్భం|গর্ভবতী|গর্ভাবস্থা|गरोदर|સગર્ભા|ಗರ್ಭಿಣಿ|ഗർഭിണി|ਗਰਭਵਤੀ)",
        lower,
    ):
        return "anc"
    if re.search(
        r"\b(?:pnc|postnatal|postpartum|prasav\s+ke\s+baad|delivery\s+ke\s+baad)\b|"
        r"(?:प्रसव\s*के\s*बाद|பிரசவத்திற்குப்\s*பின்|ప్రసవానంతర|প্রসবের\s*পর|प्रसूतीनंतर|પ્રસૂતિ\s*પછી|ಪ್ರಸವದ\s*ನಂತರ|പ്രസവശേഷം|ਜਣੇਪੇ\s*ਤੋਂ\s*ਬਾਅਦ)",
        lower,
    ):
        return "pnc"
    if re.search(
        r"\b(?:immunisation|immunization|vaccination|tikakaran|tika\s+lag|vaccine\s+visit)\b|"
        r"(?:टीकाकरण|टीका|लसीकरण|தடுப்பூசி|టీకా|টিকা|টিকাকরণ|રસીકરણ|ಲಸಿಕೆ|കുത്തിവയ്പ്പ്|വാക്സിനേഷൻ|ਟੀਕਾਕਰਨ)",
        lower,
    ):
        return "immunisation"
    if re.search(r"\b(?:general\s+checkup|household\s+visit|routine\s+visit|follow\s*up\s+visit)\b", lower):
        return "other"
    return None


def _extract_vaccinations(text: str) -> Dict[str, str]:
    cleaned = normalize_text(text)
    lower = cleaned.lower()
    results: Dict[str, str] = {}

    clauses = re.split(
        r"[.;\n।॥]|(?:\baur\b|\band\b|और|மற்றும்|మరియు|এবং|आणि|અને|ಮತ್ತು|ഉം|ਅਤੇ)",
        lower,
    )
    sorted_keys = sorted(VACCINE_CANONICAL.keys(), key=len, reverse=True)
    for clause in clauses:
        for key in sorted_keys:
            if re.search(rf"\b{re.escape(key)}\b(?!-\d)", clause):
                canonical = VACCINE_CANONICAL[key]
                status = "completed"
                if re.search(
                    r"\b(?:refused|mana\s+kiya|mana\s+kar|nahi\s+lagwana)\b|"
                    r"(?:मना|மறுத்துவிட்டார்|నిరాకరించారు|অস্বীকার|नाकारले|ના\s*પાડી|ನಿರಾಕರಿಸಿದ್ದಾರೆ|നിരസിച്ചു|ਇਨਕਾਰ)",
                    clause,
                ):
                    status = "refused"
                elif re.search(
                    r"\b(?:nahi\s+laga|nahi\s+diya|nahi\s+hua|not\s+given|not\s+done|missed|chhoot\s+gaya)\b|"
                    r"(?:नहीं\s*लगा|नहीं\s*दिया|போடவில்லை|கொடுக்கவில்லை|వేయలేదు|ఇవ్వలేదు|দেওয়া\s*হয়নি|দিল\s*না|दिले\s*नाही|આપી\s*નથી|ನೀಡಿಲ್ಲ|നൽകിയില്ല|ਨਹੀਂ\s*ਲਗਾਇਆ|ਨਹੀਂ\s*ਦਿੱਤਾ)",
                    clause,
                ):
                    status = "missed"
                elif re.search(
                    r"\b(?:due|baaki|pending|remaining|agla\s+lagna)\b|"
                    r"(?:बाकी|நிலுவையில்|బాకీ|বাকি|बाकी|બાકી|ಬಾಕಿ|ബാക്കി|ਬਾਕੀ)",
                    clause,
                ):
                    status = "due"
                elif re.search(r"\b(?:pata\s+nahi|unknown|card\s+nahi)\b|(?:पता\s*नहीं|தெரியவில்லை|తెలియదు)", clause):
                    status = "unknown"
                elif re.search(
                    r"\b(?:ho\s+gaya|lag\s+gaya|lag\s+gayi|laga\s+diya|laga\s+di|diya\s+gaya|de\s+di|completed|complete|done|given|administered|lagwaya)\b|"
                    r"(?:हो\s*गया|लगा\s*दिया|दिया|போடப்பட்டது|பூர்த்தி|వేయబడింది|వేశారు|দেওয়া\s*হয়েছে|দিয়েছে|दिली|दिली\s*आहे|આપવામાં\s*આવી|ಹಾಕಲಾಗಿದೆ|നൽകി|ਲਗਾਇਆ|ਦਿੱਤਾ)",
                    clause,
                ):
                    status = "completed"
                if canonical == "OPV" and any(k.startswith("OPV-") for k in results):
                    continue
                if canonical == "Pentavalent" and any(k.startswith("Penta-") for k in results):
                    continue
                results[canonical] = status
    return results


def _extract_ifa_status(text: str) -> Optional[str]:
    lower = normalize_text(text).lower()
    ifa_cue = (
        r"\b(?:ifa|iron(?:\s+folic\s+acid)?(?:\s+ki)?\s+(?:goli|tablet|tablets))\b|"
        r"(?:आयरन|IFA|இரும்பு|ఐరన్|আয়রন|लोह|આયર્ન|ಕಬ್ಬಿಣ|അയൺ|ਆਇਰਨ)"
    )
    if not re.search(ifa_cue, lower, re.IGNORECASE):
        return None

    clauses = re.split(r"[.,;\n।॥]", lower)
    for clause in clauses:
        if not re.search(ifa_cue, clause, re.IGNORECASE):
            continue
        if re.search(r"\b(?:pata\s+nahi|yaad\s+nahi|unknown)\b|(?:पता\s*नहीं|தெரியவில்லை|తెలియదు|জানা\s*নেই)", clause):
            return "unknown"
        if re.search(r"\b(?:mana|refused|nahi\s+lena)\b|(?:मना|மறுத்துவிட்டார்|నిరాకరించారు|नाकारले)", clause):
            return "refused"
        if re.search(
            r"\b(?:nahi\s+diya|nahi\s+di|nahi\s+de\s+paayi|not\s+given|not\s+provided|didn't\s+give|did\s+not\s+give|stock\s+nahi)\b|"
            r"(?:नहीं\s*दी|नहीं\s*दिया|கொடுக்கவில்லை|வழங்கவில்லை|ఇవ్వలేదు|দেওয়া\s*হয়নি|দিল\s*না|दिली\s*नाही|દિધી\s*નથી|આપી\s*નથી|ನೀಡಿಲ್ಲ|ಕೊಟ್ಟಿಲ್ಲ|നൽകിയില്ല|കൊടുത്തില്ല|ਨਹੀਂ\s*ਦਿੱਤੀ|ਨਹੀਂ\s*ਦਿੱਤੀਆਂ)",
            clause,
        ):
            return "not_provided"
        if re.search(r"\b(?:kha\s+rahi|le\s+rahi|consumed|taking\s+regularly)\b", clause):
            return "consumed"
        if re.search(r"\b(?:pehle\s+se\s+hai|already\s+has|already\s+available)\b", clause):
            return "already_available"
        if re.search(
            r"\b(?:di|diya|de\s+di|given|provided|distributed|baant|supplied|mila|mili)\b|"
            r"(?:दी|दिया|दी\s*गई|கொடுக்கப்பட்டது|வழங்கப்பட்டது|இచ్చారు|ఇచ్చాము|দেওয়া\s*হয়েছে|দিয়েছি|दिली|दिली\s*आहे|આપી|આપવામાં\s*આવી|ನೀಡಲಾಗಿದೆ|ಕೊಟ್ಟಿದ್ದೇವೆ|നൽകി|കൊടുത്തു|ਦਿੱਤੀ|ਦਿੱਤੀਆਂ)",
            clause,
        ):
            return "provided"
    return None


def _extract_pregnancy_info(text: str) -> Optional[PregnancyInfo]:
    lower = normalize_text(text).lower()
    months: Optional[float] = None
    weeks: Optional[int] = None
    trimester: Optional[int] = None
    anc_visit_no: Optional[int] = None

    m_mon = re.search(
        r"(?:^|\s)([^\s]+)\s*(?:mahine|maah|months|month|महीने|माह|மாதம்|மாத|నెల|నెలల|মাস|महिने|महिना|મહિના|ತಿಂಗಳು|മാസം|ਮਹੀਨੇ)\s*(?:ki\s+pregnancy|pregnant|garbh|गर्भावस्था|கர்ப்பம்|గర్భం|গর্ভাবস্থা|गरोदर|સગર્ભા|ಗರ್ಭಿಣಿ|ഗർഭിണി|ਗਰਭਵਤੀ)?|"
        r"\bpregnant\s*(?:for)?\s*([^\s]+)\s*(?:months|month)\b",
        lower,
    )
    if m_mon and re.search(
        r"\b(?:pregnant|pregnancy|garbh|anc)\b|गर्भावस्था|गर्भवती|கர்ப்பம்|கர்ப்பிணி|గర్భం|গর্ভাবস্থা|गरोदर|સગર્ભા|ಗರ್ಭಿಣಿ|ഗർഭിണി|ਗਰਭਵਤੀ",
        lower,
    ):
        raw_num = m_mon.group(1) or m_mon.group(2)
        val = parse_number_tokens([raw_num])
        if val is not None and 0.5 <= val <= 10.5:
            months = val

    m_wk = re.search(r"\b([a-z0-9]+)\s*(?:weeks|week|hafte)\s*(?:pregnant|pregnancy|gestation)?\b", lower)
    if m_wk and re.search(r"\b(?:pregnant|pregnancy|anc|gestation|garbh)\b", lower):
        val = parse_number_tokens([m_wk.group(1)])
        if val is not None and 1 <= val <= 45:
            weeks = int(val)

    if re.search(r"\b(?:first|1st|pehla)\s+trimester\b", lower):
        trimester = 1
    elif re.search(r"\b(?:second|2nd|dusra)\s+trimester\b", lower):
        trimester = 2
    elif re.search(r"\b(?:third|3rd|teesra)\s+trimester\b", lower):
        trimester = 3
    elif months is not None:
        trimester = 1 if months <= 3 else (2 if months <= 6 else 3)

    m_anc = re.search(r"\banc\s*(?:visit\s*)?[-#:]?\s*(\d)\b", lower)
    if m_anc:
        anc_visit_no = int(m_anc.group(1))

    if any(v is not None for v in (months, weeks, trimester, anc_visit_no)):
        return PregnancyInfo(
            gestational_months=months,
            gestational_weeks=weeks,
            trimester=trimester,
            anc_visit_number=anc_visit_no,
            raw_observation=normalize_text(text),
        )
    return None


def _extract_newborn_info(text: str) -> Optional[NewbornInfo]:
    lower = normalize_text(text).lower()
    age_days: Optional[int] = None
    bf_status: Optional[str] = None
    temp_f: Optional[float] = None
    temp_c: Optional[float] = None

    m_age = re.search(
        r"\b(\d{1,3})\s*(?:din|days|day)\s*(?:ka|ki|old)?\s*(?:baby|baccha|newborn|shishu)?\b",
        lower,
    )
    if m_age and re.search(r"\b(?:baby|baccha|newborn|shishu|old|umar|age)\b", lower):
        days_val = int(m_age.group(1))
        if 0 <= days_val <= 365:
            age_days = days_val

    if re.search(r"\b(?:exclusive\s+breastfeeding|sirf\s+maa\s+ka\s+doodh)\b", lower):
        bf_status = "exclusive"
    elif re.search(r"\b(?:doodh\s+nahi\s+pi|not\s+feeding|unable\s+to\s+feed|stanpaan\s+nahi)\b", lower):
        bf_status = "poor"
    elif re.search(r"\b(?:doodh\s+pi\s+raha|feeding\s+well|breastfeeding\s+(?:started|normal|good)|stanpaan\s+shuru)\b", lower):
        bf_status = "initiated"

    m_tf = re.search(r"\b(9\d(?:\.\d)?|10\d(?:\.\d)?|11\d(?:\.\d)?)\s*(?:°?\s*f|fahrenheit)\b", lower)
    if m_tf:
        temp_f = float(m_tf.group(1))
    m_tc = re.search(r"\b(3\d(?:\.\d)?|4[0-3](?:\.\d)?)\s*(?:°?\s*c|celsius)\b", lower)
    if m_tc:
        temp_c = float(m_tc.group(1))

    if any(v is not None for v in (age_days, bf_status, temp_f, temp_c)):
        return NewbornInfo(
            age_days=age_days,
            breastfeeding_status=bf_status,  # type: ignore[arg-type]
            temperature_fahrenheit=temp_f,
            temperature_celsius=temp_c,
            raw_observation=normalize_text(text),
        )
    return None


def _extract_explicit_negatives_and_unknowns(
    text: str,
    ifa_status: Optional[str],
    vaccinations: Dict[str, str],
) -> Tuple[Dict[str, str], List[str]]:
    lower = normalize_text(text).lower()
    negatives: Dict[str, str] = {}
    unknowns: List[str] = []

    if ifa_status == "not_provided":
        negatives["ifa"] = "IFA not provided"
    for vac, st in vaccinations.items():
        if st in {"missed", "refused"}:
            negatives[f"vaccination_{vac}"] = f"{vac} {st}"

    # Explicit symptom negatives
    neg_checks = [
        ("bleeding", r"\b(?:bleeding|khoon)\b[^.?!;\n]{0,35}\b(?:nahi|no|not|absent)\b|\bno\s+(?:vaginal\s+)?bleeding\b"),
        ("fever", r"\b(?:fever|bukhar|bukhaar)\b[^.?!;\n]{0,35}\b(?:nahi|no|not|absent)\b|\bno\s+fever\b"),
        ("convulsions", r"\b(?:convulsions?|fits|seizures?|daure|jhatke)\b[^.?!;\n]{0,35}\b(?:nahi|no|not|absent)\b|\bno\s+(?:fits|convulsions?|seizures?)\b"),
        ("breathing_difficulty", r"\b(?:saans\s+(?:ki\s+)?(?:takleef|dikkat)|breathing\s+difficulty|fast\s+breathing)\b[^.?!;\n]{0,35}\b(?:nahi|no|not|normal)\b|\bno\s+(?:fast\s+)?breathing\b"),
    ]
    for key, pat in neg_checks:
        if re.search(pat, lower):
            negatives[key] = f"{key} explicitly denied"

    # Explicit unknown fields across supported languages
    unknown_cue = (
        r"(?:\b(?:pata\s+nahi|yaad\s+nahi|nahi\s+pata|maloom\s+nahi|unknown|available\s+nahi)\b|"
        r"पता\s+नहीं|தெரியவில்லை|తెలియదు|জানা\s+নেই|माहित\s+नाही|ખબર\s+નથી|ಗೊತ್ತಿಲ್ಲ|അറിയില്ല|ਪਤਾ\s+ਨਹੀਂ)"
    )
    unknown_checks = [
        ("beneficiary_id", rf"(?:\b(?:beneficiary\s*id|id)\b|आईडी|ஐடி|ఐడి|আইডি|आयडी|આઈડી|ಐಡಿ|ഐഡി|ਆਈਡੀ)[^.?!;\n।॥]{{0,35}}{unknown_cue}"),
        ("weight_kg", rf"(?:\b(?:weight|vajan|wajan)\b|वजन|எடை|బరువు|ওজন|વજન|ತೂಕ|ഭാരം|ਵਜ਼ਨ)[^.?!;\n।॥]{{0,35}}{unknown_cue}"),
        ("blood_pressure", rf"(?:\b(?:bp|blood\s*pressure)\b|रक्तचाप|रक्तदाब|இரத்த\s+அழுத்தம்|రక్తపోటు|রক্তচাপ|બ્લડ\s+પ્રેશર|ರಕ್ತದೊತ್ತಡ|രക്തസമ്മർദ്ദം|ਬਲੱਡ\s+ਪ੍ਰੈਸ਼ਰ)[^.?!;\n।॥]{{0,35}}{unknown_cue}"),
        ("next_visit_date", rf"(?:\b(?:next\s+visit|agla\s+visit)\b|अगली\s*विजिट|அடுத்த\s*வருகை|తదుపరి\s*విజిట్|পরবর্তী\s*ভিজিট|पुढची\s*भेट|આગલી\s*મુલાકાત|ಮುಂದಿನ\s*ಭೇಟಿ|അടുത്ത\s*സന്ദർശനം|ਅਗਲੀ\s*ਵਿਜ਼ਿਟ)[^.?!;\n।॥]{{0,35}}{unknown_cue}"),
    ]
    for field_name, pat in unknown_checks:
        if re.search(pat, lower):
            unknowns.append(field_name)

    return negatives, unknowns


def deterministic_extract_dict(
    transcript: str,
    anchor_date: Optional[date] = None,
    tz_name: str = "Asia/Kolkata",
    existing_form: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic code-mixed healthcare information extractor (used by Mock mode and fallback)."""
    cleaned = normalize_text(transcript)
    anchor = anchor_date or today_in_timezone(tz_name)
    existing = existing_form or {}
    expect_id = bool(
        existing.get("_expecting_field") == "beneficiary_id"
        or re.search(
            r"\b(?:id|beneficiary)\b|आईडी|ஐடி|ఐడి|আইডি|आयडी|આઈડી|ಐಡಿ|ഐഡി|ਆਈਡੀ",
            cleaned,
            re.IGNORECASE,
        )
    )

    beneficiary_name = _extract_beneficiary_name(cleaned)
    beneficiary_id = parse_beneficiary_id(cleaned, expect_id=expect_id)
    visit_type = _extract_visit_type(cleaned)
    weight_kg = parse_spoken_weight_kg(cleaned)
    if weight_kg is None and existing.get("_expecting_field") == "weight_kg":
        bare_num = parse_number_tokens(tokenize_unicode_words(cleaned))
        if bare_num is not None and 0.2 < bare_num <= 200.0:
            weight_kg = round(bare_num, 2)
    blood_pressure = parse_blood_pressure(cleaned)
    pregnancy_info = _extract_pregnancy_info(cleaned)
    newborn_info = _extract_newborn_info(cleaned)
    vaccinations = _extract_vaccinations(cleaned)
    ifa_status = _extract_ifa_status(cleaned)

    # Extract follow-up / next visit date strictly from follow-up clause if present
    date_segment = cleaned
    follow_clause = re.search(
        r"(?:next\s*visit|agla\s*visit|agli\s*visit|follow\s*up|phir\s*visit|"
        r"अगली\s*विजिट|अगला\s*विजिट|அடுத்த\s*வருகை|తదుపరి\s*విజిట్|পরবর্তী\s*ভিজিট|"
        r"पुढची\s*भेट|આગલી\s*મુલાકાત|ಮುಂದಿನ\s*ಭೇಟಿ|അടുത്ത\s*സന്ദർശനം|ਅਗਲੀ\s*ਵਿਜ਼ਿਟ)"
        r"\s*(?:date|tarikh|तारीख|தேதி|తేదీ|তারিখ|तारीख|તારીખ|ದಿನಾಂಕ|തീയതി|ਤਾਰੀਖ਼)?"
        r"\s*(?:is|hai|ko|on|आहे|है|உள்ளது|ఉంది|হবে|છે|ಇದೆ|ആണ്|ਹੈ|:)?\s*([^.;\n।॥]+)",
        cleaned,
        re.IGNORECASE,
    )
    if follow_clause:
        date_segment = follow_clause.group(1)
    elif existing.get("_expecting_field") == "next_visit_date":
        date_segment = cleaned
    else:
        # Avoid interpreting "Aaj maine..." as next_visit_date unless a future/calendar cue exists
        lower_c = cleaned.lower()
        has_calendar_word = any(m in lower_c for m in MONTH_MAP) or any(w in lower_c for w in WEEKDAY_MAP)
        if not has_calendar_word and not re.search(
            r"(?:\b(?:next|agla|agle|after|baad|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b|"
            r"दिनों|दिन|நாட்கள்|நாள்|రోజులు|రోజు|দিন|दिवसांनी|दिवस|દિવસ|ದಿನಗಳ|ದಿನ|ദിവസത്തിന്|ദിവസം|ਦਿਨਾਂ|ਦਿਨ|"
            r"हफ्ते|வாரம்|వారం|সপ্তাহ|आठवडे|आठवडा|અઠવાડિયા|ವಾರ|ആഴ്ച|ਹਫ਼ਤੇ)",
            cleaned,
            re.IGNORECASE,
        ):
            date_segment = ""

    next_date, raw_date_ref, ambig_date_ref = (
        resolve_relative_date(date_segment, anchor_date=anchor, tz_name=tz_name)
        if date_segment
        else (None, None, None)
    )

    negatives, unknowns = _extract_explicit_negatives_and_unknowns(
        cleaned, ifa_status, vaccinations
    )

    # Ensure unknown fields are not filled spuriously
    if "weight_kg" in unknowns:
        weight_kg = None
    if "beneficiary_id" in unknowns:
        beneficiary_id = None
    if "next_visit_date" in unknowns:
        next_date = None

    return {
        "beneficiary_name": beneficiary_name,
        "beneficiary_id": beneficiary_id,
        "visit_type": visit_type,
        "weight_kg": weight_kg,
        "blood_pressure": blood_pressure.model_dump() if blood_pressure else None,
        "pregnancy_info": pregnancy_info.model_dump() if pregnancy_info else None,
        "newborn_info": newborn_info.model_dump() if newborn_info else None,
        "vaccinations": vaccinations,
        "ifa_status": ifa_status,
        "next_visit_date": next_date.isoformat() if next_date else None,
        "raw_next_visit_reference": raw_date_ref,
        "ambiguous_next_visit_reference": ambig_date_ref,
        "danger_sign_observations": [],
        "observations": [cleaned] if cleaned else [],
        "negative_findings": negatives,
        "unknown_fields": unknowns,
    }


class ExtractionEngine:
    """Converts voice transcripts into Pydantic-validated ExtractionPayload objects."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        max_retries: int = 2,
        timezone_name: str = "Asia/Kolkata",
        fallback_on_failure: bool = True,
    ) -> None:
        self._llm = llm_client
        self._max_retries = max(0, max_retries)
        self._timezone = timezone_name
        self._fallback_on_failure = fallback_on_failure

    def extract(
        self,
        transcript: str,
        visit_date: Optional[date] = None,
        existing_form: Optional[Dict[str, Any]] = None,
        language: str = "hi-en",
        detected_language: Optional[str] = None,
    ) -> ExtractionPayload:
        """
        Extract structured healthcare fields from a multilingual voice transcript.

        Retries with corrective repair prompts if the LLM emits malformed JSON
        or schema-invalid fields.
        """
        anchor = visit_date or today_in_timezone(self._timezone)
        user_prompt = build_extraction_user_prompt(
            transcript=transcript,
            visit_date_iso=anchor.isoformat(),
            timezone_name=self._timezone,
            existing_form=existing_form,
            language=language,
            detected_language=detected_language,
        )
        metadata = {
            "transcript": transcript,
            "visit_date": anchor,
            "timezone": self._timezone,
            "existing_form": existing_form or {},
        }

        last_error: Optional[Exception] = None
        last_output: str = ""
        current_prompt = user_prompt

        for attempt in range(self._max_retries + 1):
            try:
                raw_response = self._llm.complete_json(
                    system_prompt=EXTRACTION_SYSTEM_PROMPT,
                    user_prompt=current_prompt,
                    task="extraction",
                    metadata=metadata,
                )
                last_output = raw_response
                cleaned_json = _strip_json_fences(raw_response)
                parsed_dict = json.loads(cleaned_json)
                if not isinstance(parsed_dict, dict):
                    raise ValueError("LLM extraction output must be a JSON object.")
                payload = ExtractionPayload.model_validate(parsed_dict)
                return self._apply_post_validation_guards(
                    payload=payload,
                    transcript=transcript,
                    anchor_date=anchor,
                    existing_form=existing_form,
                )
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Extraction validation failed on attempt %d/%d",
                    attempt + 1,
                    self._max_retries + 1,
                )
                current_prompt = build_extraction_repair_prompt(
                    transcript=transcript,
                    previous_output=last_output,
                    validation_error=str(exc),
                )
            except LLMProviderError as exc:
                last_error = exc
                logger.warning("LLM provider error during extraction: %s", exc)
                break

        if self._fallback_on_failure:
            logger.warning("Falling back to deterministic extraction after retries failed")
            fallback_dict = deterministic_extract_dict(
                transcript=transcript,
                anchor_date=anchor,
                tz_name=self._timezone,
                existing_form=existing_form,
            )
            return ExtractionPayload.model_validate(fallback_dict)

        if isinstance(last_error, LLMProviderError):
            raise last_error

        raise ExtractionValidationError(
            f"Extraction failed after {self._max_retries + 1} attempts: {last_error}"
        )

    def _apply_post_validation_guards(
        self,
        payload: ExtractionPayload,
        transcript: str,
        anchor_date: date,
        existing_form: Optional[Dict[str, Any]],
    ) -> ExtractionPayload:
        """Apply deterministic safeguards for relative dates, negations, and code-mixed numbers."""
        det = deterministic_extract_dict(
            transcript=transcript,
            anchor_date=anchor_date,
            tz_name=self._timezone,
            existing_form=existing_form,
        )

        # Never allow invented date when transcript reference was ambiguous
        if det.get("ambiguous_next_visit_reference") and not det.get("next_visit_date"):
            payload.next_visit_date = None
            payload.ambiguous_next_visit_reference = det["ambiguous_next_visit_reference"]
        elif payload.next_visit_date is None and det.get("next_visit_date"):
            payload.next_visit_date = date.fromisoformat(det["next_visit_date"])

        # Protect explicit IFA negative ("IFA nahi diya") from LLM misclassification
        if det.get("ifa_status") == "not_provided":
            payload.ifa_status = "not_provided"
        elif payload.ifa_status is None and det.get("ifa_status"):
            payload.ifa_status = det["ifa_status"]

        # Backfill deterministic numeric/ID extraction if LLM returned null
        if payload.weight_kg is None and det.get("weight_kg") is not None:
            payload.weight_kg = det["weight_kg"]
        if payload.beneficiary_id is None and det.get("beneficiary_id"):
            payload.beneficiary_id = det["beneficiary_id"]
        if payload.beneficiary_name is None and det.get("beneficiary_name"):
            payload.beneficiary_name = det["beneficiary_name"]
        if payload.visit_type is None and det.get("visit_type"):
            payload.visit_type = det["visit_type"]
        if payload.blood_pressure is None and det.get("blood_pressure"):
            payload.blood_pressure = ExtractionPayload.model_validate(
                {"blood_pressure": det["blood_pressure"]}
            ).blood_pressure
        if not payload.vaccinations and det.get("vaccinations"):
            payload.vaccinations = det["vaccinations"]

        for k, v in det.get("negative_findings", {}).items():
            payload.negative_findings.setdefault(k, v)
        for u in det.get("unknown_fields", []):
            if u not in payload.unknown_fields:
                payload.unknown_fields.append(u)

        return payload
