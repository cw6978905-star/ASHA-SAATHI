"""Module 4: Multilingual Read-Back Generation and Confirmation Handler (All 10 Gnani Languages)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal
from zoneinfo import ZoneInfo

from brain.languages import (
    FIELD_LABELS as ALL_FIELD_LABELS,
    TEMPLATE_KEY_MAP,
    get_field_label,
    get_ui_phrase,
    normalize_language_code,
)
from models.visit_schema import DangerFlag, LanguageCode, VisitRecord

ConfirmationIntent = Literal["confirm", "reject", "unclear"]

# Preserve backwards-compatible export
FIELD_LABELS: Dict[str, Dict[str, str]] = ALL_FIELD_LABELS

AFFIRMATIVE_PATTERN = re.compile(
    r"(?:^\s*(?:haan|han|ha|ji\s*haan|ji|yes|yeah|yep|ok|okay|bilkul|sahi|correct|confirm)\b|"
    r"\b(?:save\s+kar\s+do|save\s+kardo|save\s+karo|save\s+kar\s+dijiye|save\s+it|"
    r"record\s+save\s+kar|theek\s+hai|thik\s+hai|sahi\s+hai|confirm\s+kar|"
    r"aam|aama|avunu|haan|ho|hoy|ha|houdu|athe|haanji)\b|"
    r"हाँ|जी\s*हाँ|सेव\s*कर\s*दो|सही\s*है|ठीक\s*है|"
    r"ஆம்|ஆமா|ஆமாம்|சேமிக்கவும்|சரி|"
    r"అవును|సేవ్\s*చేయండి|సరే|"
    r"হ্যাঁ|সেভ\s*করুন|ঠিক\s*আছে|"
    r"होय|हो|सेव्ह\s*करा|बरोबर\s*आहे|"
    r"હા|સેવ\s*કરો|બરાબર\s*છે|"
    r"ಹೌದು|ಸೇವ್\s*ಮಾಡಿ|ಸರಿ|"
    r"അതെ|സേവ്\s*ചെയ്യൂ|ശരി|"
    r"ਹਾਂ|ਹਾਂਜੀ|ਸੇਵ\s*ਕਰ\s*ਦੋ|ਠੀਕ\s*ਹੈ)",
    re.IGNORECASE,
)

NEGATIVE_PATTERN = re.compile(
    r"(?:^\s*(?:nahi|nahin|na|no|nope|ruko|wait|cancel)\b|"
    r"\b(?:mat\s+save|save\s+mat|don't\s+save|do\s+not\s+save|galat\s+hai|wrong|change\s+karo|"
    r"illa|illai|vendam|kaadu|vaddu|naahi|nako|nathi|beda|alla|venda)\b|"
    r"नहीं|मत\s*सेव|गलत\s*है|रुको|"
    r"இல்லை|வேண்டாம்|சேமிக்க\s*வேண்டாம்|"
    r"కాదు|వద్దు|సేవ్\s*చేయవద్దు|"
    r"না|সেভ\s*করবেন\s*না|"
    r"नाही|नको|सेव्ह\s*करू\s*नका|"
    r"ના|નહીં|સેવ\s*ન\s*કરો|"
    r"ಇಲ್ಲ|ಬೇಡ|ಸೇವ್\s*ಮಾಡಬೇಡಿ|"
    r"അല്ല|വേണ്ട|സേവ്\s*ചെയ്യരുത്|"
    r"ਨਹੀਂ|ਨਾ|ਸੇਵ\s*ਨਾ\s*ਕਰੋ)",
    re.IGNORECASE,
)

# Per-language structured read-back templates
READBACK_TEMPLATES: Dict[str, Dict[str, str]] = {
    "ta-IN": {
        "header_name_type": "{name} அவர்களின் {vtype} வருகை பதிவு:",
        "header_name": "{name} அவர்களின் வருகை பதிவு:",
        "header_type": "{vtype} வருகை பதிவு:",
        "header_plain": "வருகை பதிவு சுருக்கம்:",
        "id": "பயனாளி ID {val}.",
        "weight": "எடை {val} கிலோ.",
        "bp": "இரத்த அழுத்தம் {val}.",
        "preg": "கர்ப்ப காலம் {val} மாதங்கள்.",
        "age": "குழந்தையின் வயது {val} நாட்கள்.",
        "vac": "{vac} தடுப்பூசி நிலை: {status}.",
        "ifa": "IFA நிலை: {status}.",
        "next_visit": "அடுத்த வருகை தேதி {val}.",
        "danger": "அபாய அறிகுறிகள்: {val}.",
        "missing": "விடுபட்ட விவரங்கள்: {val}.",
    },
    "te-IN": {
        "header_name_type": "{name} యొక్క {vtype} విజిట్ రికార్డు:",
        "header_name": "{name} యొక్క విజిట్ రికార్డు:",
        "header_type": "{vtype} విజిట్ రికార్డు:",
        "header_plain": "విజిట్ రికార్డు సారాంశం:",
        "id": "లబ్ధిదారు ID {val}.",
        "weight": "బరువు {val} కిలోలు.",
        "bp": "రక్తపోటు {val}.",
        "preg": "గర్భధారణ సమయం {val} నెలలు.",
        "age": "శిశువు వయస్సు {val} రోజులు.",
        "vac": "{vac} టీకా స్థితి: {status}.",
        "ifa": "IFA స్థితి: {status}.",
        "next_visit": "తదుపరి విజిట్ తేదీ {val}.",
        "danger": "ప్రమాద సంకేతాలు: {val}.",
        "missing": "లేని వివరాలు: {val}.",
    },
    "bn-IN": {
        "header_name_type": "{name}-এর {vtype} ভিজিট রেকর্ড:",
        "header_name": "{name}-এর ভিজিট রেকর্ড:",
        "header_type": "{vtype} ভিজিট রেকর্ড:",
        "header_plain": "ভিজিট রেকর্ডের সারাংশ:",
        "id": "উপভোক্তার ID {val}।",
        "weight": "ওজন {val} কেজি।",
        "bp": "রক্তচাপ {val}।",
        "preg": "গর্ভাবস্থার সময়কাল {val} মাস।",
        "age": "নবজাতকের বয়স {val} দিন।",
        "vac": "{vac} টিকা অবস্থা: {status}।",
        "ifa": "IFA অবস্থা: {status}।",
        "next_visit": "পরবর্তী ভিজিট তারিখ {val}।",
        "danger": "বিপদ সংকেত: {val}।",
        "missing": "অসম্পূর্ণ তথ্য: {val}।",
    },
    "mr-IN": {
        "header_name_type": "{name} यांची {vtype} भेट नोंद:",
        "header_name": "{name} यांची भेट नोंद:",
        "header_type": "{vtype} भेट नोंद:",
        "header_plain": "भेट नोंद सारांश:",
        "id": "लाभार्थी ID {val} आहे.",
        "weight": "वजन {val} किलो आहे.",
        "bp": "रक्तदाब {val} आहे.",
        "preg": "गर्भधारणा {val} महिने आहे.",
        "age": "बाळाचे वय {val} दिवस आहे.",
        "vac": "{vac} लसीकरण स्थिती: {status}.",
        "ifa": "IFA स्थिती: {status}.",
        "next_visit": "पुढची भेट {val} रोजी आहे.",
        "danger": "धोक्याची लक्षणे: {val}.",
        "missing": "अपूर्ण माहिती: {val}.",
    },
    "gu-IN": {
        "header_name_type": "{name} નો {vtype} મુલાકાત રેકોર્ડ:",
        "header_name": "{name} નો મુલાકાત રેકોર્ડ:",
        "header_type": "{vtype} મુલાકાત રેકોર્ડ:",
        "header_plain": "મુલાકાત રેકોર્ડ સારાંશ:",
        "id": "લાભાર્થી ID {val} છે.",
        "weight": "વજન {val} કિલો છે.",
        "bp": "બ્લડ પ્રેશર {val} છે.",
        "preg": "ગર્ભાવસ્થા {val} મહિનાની છે.",
        "age": "બાળકની ઉંમર {val} દિવસ છે.",
        "vac": "{vac} રસીકરણ સ્થિતિ: {status}.",
        "ifa": "IFA સ્થિતિ: {status}.",
        "next_visit": "આગલી મુલાકાત {val} ના રોজ છે.",
        "danger": "જોખમી સંકેતો: {val}.",
        "missing": "બાકી વિગતો: {val}.",
    },
    "kn-IN": {
        "header_name_type": "{name} ಅವರ {vtype} ಭೇಟಿ ದಾಖಲೆ:",
        "header_name": "{name} ಅವರ ಭೇಟಿ ದಾಖಲೆ:",
        "header_type": "{vtype} ಭೇಟಿ ದಾಖಲೆ:",
        "header_plain": "ಭೇಟಿ ದಾಖಲೆ ಸಾರಾಂಶ:",
        "id": "ಫಲಾನುಭವಿ ID {val}.",
        "weight": "ತೂಕ {val} ಕಿಲೋ ಇದೆ.",
        "bp": "ರಕ್ತದೊತ್ತಡ {val} ಇದೆ.",
        "preg": "ಗರ್ಭಾವಸ್ಥೆ {val} ತಿಂಗಳು.",
        "age": "ಮಗುವಿನ ವಯಸ್ಸು {val} ದಿನಗಳು.",
        "vac": "{vac} ಲಸಿಕೆ ಸ್ಥಿತಿ: {status}.",
        "ifa": "IFA ಸ್ಥಿತಿ: {status}.",
        "next_visit": "ಮುಂದಿನ ಭೇಟಿ {val} ರಂದು.",
        "danger": "ಅಪಾಯದ ಲಕ್ಷಣಗಳು: {val}.",
        "missing": "ಬಾಕಿ ಇರುವ ಮಾಹಿತಿ: {val}.",
    },
    "ml-IN": {
        "header_name_type": "{name}-ന്റെ {vtype} സന്ദർശന രേഖ:",
        "header_name": "{name}-ന്റെ സന്ദർശന രേഖ:",
        "header_type": "{vtype} സന്ദർശന രേഖ:",
        "header_plain": "സന്ദർശന രേഖയുടെ സംഗ്രഹം:",
        "id": "ഗുണഭോക്താവിന്റെ ID {val}.",
        "weight": "ഭാരം {val} കിലോ ആണ്.",
        "bp": "രക്തസമ്മർദ്ദം {val} ആണ്.",
        "preg": "ഗർഭകാലം {val} മാസം.",
        "age": "കുഞ്ഞിന്റെ പ്രായം {val} ദിവസം.",
        "vac": "{vac} വാക്സിനേഷൻ നില: {status}.",
        "ifa": "IFA നില: {status}.",
        "next_visit": "അടുത്ത സന്ദർശനം {val}.",
        "danger": "അപകട ലക്ഷണങ്ങൾ: {val}.",
        "missing": "വിട്ടുപോയ വിവരങ്ങൾ: {val}.",
    },
    "pa-IN": {
        "header_name_type": "{name} ਦਾ {vtype} ਵਿਜ਼ਿਟ ਰਿਕਾਰਡ:",
        "header_name": "{name} ਦਾ ਵਿਜ਼ਿਟ ਰਿਕਾਰਡ:",
        "header_type": "{vtype} ਵਿਜ਼ਿਟ ਰਿਕਾਰਡ:",
        "header_plain": "ਵਿਜ਼ਿਟ ਰਿਕਾਰਡ ਸਾਰਾਂਸ਼:",
        "id": "ਲਾਭਪਾਤਰੀ ID {val} ਹੈ।",
        "weight": "ਵਜ਼ਨ {val} ਕਿਲੋ ਹੈ।",
        "bp": "ਬਲੱਡ ਪ੍ਰੈਸ਼ਰ {val} ਹੈ।",
        "preg": "ਗਰਭ ਅਵਸਥਾ {val} ਮਹੀਨੇ ਹੈ।",
        "age": "ਬੱਚੇ ਦੀ ਉਮਰ {val} ਦਿਨ ਹੈ।",
        "vac": "{vac} ਟੀਕਾਕਰਨ ਸਥਿਤੀ: {status}।",
        "ifa": "IFA ਸਥਿਤੀ: {status}।",
        "next_visit": "ਅਗਲੀ ਵਿਜ਼ਿਟ {val} ਨੂੰ ਹੈ।",
        "danger": "ਖ਼ਤਰੇ ਦੇ ਸੰਕੇਤ: {val}।",
        "missing": "ਬਾਕੀ ਜਾਣਕਾਰੀ: {val}।",
    },
}


def _format_weight(weight: float) -> str:
    if float(weight).is_integer():
        return str(int(weight))
    return f"{weight:g}"


def _format_human_date(d_val: Any, tkey: str) -> str:
    if d_val is None:
        return ""
    if tkey == "en":
        return d_val.strftime("%d %B %Y")
    return d_val.strftime("%-d %B")


def classify_confirmation_intent(transcript: Optional[str]) -> ConfirmationIntent:
    """Classify worker response across all 10 languages as confirm, reject, or unclear."""
    if not transcript or not transcript.strip():
        return "unclear"
    text = " ".join(transcript.strip().split())

    if NEGATIVE_PATTERN.search(text):
        return "reject"
    if AFFIRMATIVE_PATTERN.search(text):
        return "confirm"
    return "unclear"


def generate_readback(
    record: VisitRecord,
    language: LanguageCode = "hi-en",
    include_missing_notice: bool = True,
    ask_confirmation: bool = True,
) -> str:
    """Generate a natural-language spoken read-back of the complete extracted record in all 10 languages."""
    norm_lang = normalize_language_code(language, default="hi-en")
    tkey = TEMPLATE_KEY_MAP.get(norm_lang, "hi-en")
    lines: List[str] = []
    name = record.beneficiary_name
    vtype = record.visit_type

    if tkey == "en":
        if name and vtype:
            lines.append(f"{vtype.upper()} visit record for {name}:")
        elif name:
            lines.append(f"Visit record for {name}:")
        elif vtype:
            lines.append(f"{vtype.upper()} visit record:")
        else:
            lines.append("Visit record summary:")

        if record.beneficiary_id:
            lines.append(f"Beneficiary ID is {record.beneficiary_id}.")
        if record.weight_kg is not None:
            lines.append(f"Weight is {_format_weight(record.weight_kg)} kg.")
        if record.blood_pressure:
            lines.append(f"Blood pressure is {record.blood_pressure.formatted()}.")
        if record.pregnancy_info and record.pregnancy_info.gestational_months is not None:
            lines.append(
                f"Pregnancy duration is {_format_weight(record.pregnancy_info.gestational_months)} months."
            )
        if record.newborn_info and record.newborn_info.age_days is not None:
            lines.append(f"Newborn age is {record.newborn_info.age_days} days.")
        for vaccine, status in record.vaccinations.items():
            lines.append(f"{vaccine} vaccination is {status}.")
        if record.ifa_status:
            lines.append(f"IFA status is {record.ifa_status.replace('_', ' ')}.")
        if record.next_visit_date:
            lines.append(f"Next visit is on {_format_human_date(record.next_visit_date, 'en')}.")
        if record.danger_signs:
            lines.append(f"Danger signs flagged: {', '.join(record.danger_signs)}.")

        if include_missing_notice and record.missing_fields:
            labels = [get_field_label(f, norm_lang) for f in record.missing_fields]
            lines.append(f"Missing fields: {', '.join(labels)}.")
        if ask_confirmation:
            lines.append(get_ui_phrase("confirm_question", norm_lang))
        return "\n".join(lines)

    if tkey == "hi":
        if name and vtype:
            lines.append(f"{name} का {vtype.upper()} विजिट रिकॉर्ड:")
        elif name:
            lines.append(f"{name} का विजिट रिकॉर्ड:")
        else:
            lines.append("विजिट रिकॉर्ड सारांश:")

        if record.beneficiary_id:
            lines.append(f"लाभार्थी ID {record.beneficiary_id} है।")
        if record.weight_kg is not None:
            lines.append(f"वजन {_format_weight(record.weight_kg)} किलो है।")
        if record.blood_pressure:
            lines.append(f"ब्लड प्रेशर {record.blood_pressure.formatted()} है।")
        if record.pregnancy_info and record.pregnancy_info.gestational_months is not None:
            lines.append(
                f"गर्भावस्था {_format_weight(record.pregnancy_info.gestational_months)} महीने की है।"
            )
        for vaccine, status in record.vaccinations.items():
            lines.append(f"{vaccine} टीकाकरण {status} है।")
        if record.ifa_status:
            ifa_hi = {
                "provided": "IFA गोली दी गई है।",
                "not_provided": "IFA गोली नहीं दी गई है।",
                "refused": "IFA गोली लेने से मना किया गया है।",
                "consumed": "IFA गोली ली जा रही है।",
                "already_available": "IFA गोली पहले से उपलब्ध है।",
                "unknown": "IFA स्थिति अज्ञात है।",
            }.get(record.ifa_status, f"IFA स्थिति {record.ifa_status} है।")
            lines.append(ifa_hi)
        if record.next_visit_date:
            lines.append(f"अगली विजिट {_format_human_date(record.next_visit_date, 'hi')} को है।")
        if record.danger_signs:
            lines.append(f"खतरे के संकेत दर्ज हैं: {', '.join(record.danger_signs)}।")

        if include_missing_notice and record.missing_fields:
            labels = [get_field_label(f, norm_lang) for f in record.missing_fields]
            lines.append(f"अधूरी जानकारी: {', '.join(labels)}।")
        if ask_confirmation:
            lines.append(get_ui_phrase("confirm_question", norm_lang))
        return "\n".join(lines)

    if tkey in READBACK_TEMPLATES:
        tpl = READBACK_TEMPLATES[tkey]
        if name and vtype:
            lines.append(tpl["header_name_type"].format(name=name, vtype=vtype.upper()))
        elif name:
            lines.append(tpl["header_name"].format(name=name))
        elif vtype:
            lines.append(tpl["header_type"].format(vtype=vtype.upper()))
        else:
            lines.append(tpl["header_plain"])

        if record.beneficiary_id:
            lines.append(tpl["id"].format(val=record.beneficiary_id))
        if record.weight_kg is not None:
            lines.append(tpl["weight"].format(val=_format_weight(record.weight_kg)))
        if record.blood_pressure:
            lines.append(tpl["bp"].format(val=record.blood_pressure.formatted()))
        if record.pregnancy_info and record.pregnancy_info.gestational_months is not None:
            lines.append(
                tpl["preg"].format(val=_format_weight(record.pregnancy_info.gestational_months))
            )
        if record.newborn_info and record.newborn_info.age_days is not None:
            lines.append(tpl["age"].format(val=record.newborn_info.age_days))
        for vaccine, status in record.vaccinations.items():
            lines.append(tpl["vac"].format(vac=vaccine, status=status))
        if record.ifa_status:
            lines.append(tpl["ifa"].format(status=record.ifa_status.replace("_", " ")))
        if record.next_visit_date:
            lines.append(tpl["next_visit"].format(val=_format_human_date(record.next_visit_date, tkey)))
        if record.danger_signs:
            lines.append(tpl["danger"].format(val=", ".join(record.danger_signs)))

        if include_missing_notice and record.missing_fields:
            labels = [get_field_label(f, norm_lang) for f in record.missing_fields]
            lines.append(tpl["missing"].format(val=", ".join(labels)))
        if ask_confirmation:
            lines.append(get_ui_phrase("confirm_question", norm_lang))
        return "\n".join(lines)

    # Default: hi-en (code-mixed Hindi-English)
    if name and vtype:
        lines.append(f"{name} ka {vtype} visit record:")
    elif name:
        lines.append(f"{name} ka visit record:")
    elif vtype:
        lines.append(f"{vtype} visit record:")
    else:
        lines.append("Visit record:")

    if record.beneficiary_id:
        lines.append(f"Beneficiary ID {record.beneficiary_id} hai.")
    if record.weight_kg is not None:
        lines.append(f"Weight {_format_weight(record.weight_kg)} kilo hai.")
    if record.blood_pressure:
        lines.append(f"Blood pressure {record.blood_pressure.formatted()} hai.")
    if record.pregnancy_info and record.pregnancy_info.gestational_months is not None:
        lines.append(
            f"Pregnancy {_format_weight(record.pregnancy_info.gestational_months)} mahine hai."
        )
    if record.newborn_info and record.newborn_info.age_days is not None:
        lines.append(f"Baby ki umar {record.newborn_info.age_days} din hai.")
    for vaccine, status in record.vaccinations.items():
        status_hi = "complete" if status == "completed" else status
        lines.append(f"{vaccine} vaccination {status_hi} hai.")
    if record.ifa_status:
        ifa_msg = {
            "provided": "IFA goli di gayi hai.",
            "not_provided": "IFA goli nahi di gayi hai.",
            "refused": "IFA goli lene se mana kiya hai.",
            "consumed": "IFA goli le rahi hain.",
            "already_available": "IFA goli pehle se available hai.",
            "unknown": "IFA status pata nahi hai.",
        }.get(record.ifa_status, f"IFA status {record.ifa_status} hai.")
        lines.append(ifa_msg)
    if record.next_visit_date:
        lines.append(f"Next visit {_format_human_date(record.next_visit_date, 'hi-en')} hai.")
    if record.danger_signs:
        lines.append(f"Danger signs flagged hain: {', '.join(record.danger_signs)}.")

    if include_missing_notice and record.missing_fields:
        labels = [get_field_label(f, norm_lang) for f in record.missing_fields]
        lines.append(f"Missing fields: {', '.join(labels)}.")
    if ask_confirmation:
        lines.append(get_ui_phrase("confirm_question", norm_lang))
    return "\n".join(lines)


def build_confirmed_payload(
    session_id: str,
    record: VisitRecord,
    danger_flags: List[DangerFlag],
    timezone_name: str = "Asia/Kolkata",
) -> Dict[str, Any]:
    """Build a storage-ready confirmed payload for Person C's encrypted database layer."""
    confirmed_at = datetime.now(ZoneInfo(timezone_name)).isoformat()
    return {
        "session_id": session_id,
        "confirmed": True,
        "confirmed_at": confirmed_at,
        "visit_record": record.to_compact_dict(),
        "danger_detected": len(danger_flags) > 0,
        "danger_flags": [flag.model_dump() for flag in danger_flags],
        "storage_handoff_note": "Confirmed by ASHA worker. Persist and encrypt via Person C storage module.",
    }
