"""Centralized 10-language registry, script/language detection, and TTS metadata for Gnani Prisma/Timbre v3.0."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


SUPPORTED_GNANI_LANGUAGES: Dict[str, Dict[str, str]] = {
    "hi-IN": {"name": "Hindi", "native_name": "हिन्दी", "script": "Devanagari"},
    "en-IN": {"name": "English (India)", "native_name": "English", "script": "Latin"},
    "ta-IN": {"name": "Tamil", "native_name": "தமிழ்", "script": "Tamil"},
    "te-IN": {"name": "Telugu", "native_name": "తెలుగు", "script": "Telugu"},
    "bn-IN": {"name": "Bengali", "native_name": "বাংলা", "script": "Bengali"},
    "mr-IN": {"name": "Marathi", "native_name": "मराठी", "script": "Devanagari"},
    "gu-IN": {"name": "Gujarati", "native_name": "ગુજરાતી", "script": "Gujarati"},
    "kn-IN": {"name": "Kannada", "native_name": "ಕನ್ನಡ", "script": "Kannada"},
    "ml-IN": {"name": "Malayalam", "native_name": "മലയാളം", "script": "Malayalam"},
    "pa-IN": {"name": "Punjabi", "native_name": "ਪੰਜਾਬੀ", "script": "Gurmukhi"},
}

LANGUAGE_ALIASES: Dict[str, str] = {
    "hi": "hi",
    "hi-in": "hi-IN",
    "hindi": "hi-IN",
    "hi-en": "hi-en",
    "hinglish": "hi-en",
    "en": "en",
    "en-in": "en-IN",
    "en-us": "en-IN",
    "en-gb": "en-IN",
    "english": "en-IN",
    "ta": "ta-IN",
    "ta-in": "ta-IN",
    "ta-en": "ta-IN",
    "tamil": "ta-IN",
    "te": "te-IN",
    "te-in": "te-IN",
    "te-en": "te-IN",
    "telugu": "te-IN",
    "bn": "bn-IN",
    "bn-in": "bn-IN",
    "bn-en": "bn-IN",
    "bengali": "bn-IN",
    "bangla": "bn-IN",
    "mr": "mr-IN",
    "mr-in": "mr-IN",
    "mr-en": "mr-IN",
    "marathi": "mr-IN",
    "gu": "gu-IN",
    "gu-in": "gu-IN",
    "gu-en": "gu-IN",
    "gujarati": "gu-IN",
    "kn": "kn-IN",
    "kn-in": "kn-IN",
    "kn-en": "kn-IN",
    "kannada": "kn-IN",
    "ml": "ml-IN",
    "ml-in": "ml-IN",
    "ml-en": "ml-IN",
    "malayalam": "ml-IN",
    "pa": "pa-IN",
    "pa-in": "pa-IN",
    "pa-en": "pa-IN",
    "punjabi": "pa-IN",
    "auto": "auto",
}

# Maps any internal language mode to the canonical Gnani Timbre v3.0 BCP-47 locale
TTS_LOCALE_MAP: Dict[str, str] = {
    "hi-en": "hi-IN",
    "hi": "hi-IN",
    "hi-IN": "hi-IN",
    "en": "en-IN",
    "en-IN": "en-IN",
    "ta-IN": "ta-IN",
    "te-IN": "te-IN",
    "bn-IN": "bn-IN",
    "mr-IN": "mr-IN",
    "gu-IN": "gu-IN",
    "kn-IN": "kn-IN",
    "ml-IN": "ml-IN",
    "pa-IN": "pa-IN",
}

# Template lookup canonicalization (reuses hi for hi-IN and en for en-IN)
TEMPLATE_KEY_MAP: Dict[str, str] = {
    "hi-en": "hi-en",
    "hi": "hi",
    "hi-IN": "hi",
    "en": "en",
    "en-IN": "en",
    "ta-IN": "ta-IN",
    "te-IN": "te-IN",
    "bn-IN": "bn-IN",
    "mr-IN": "mr-IN",
    "gu-IN": "gu-IN",
    "kn-IN": "kn-IN",
    "ml-IN": "ml-IN",
    "pa-IN": "pa-IN",
}

SCRIPT_RANGES: List[Tuple[str, int, int]] = [
    ("bn-IN", 0x0980, 0x09FF),
    ("pa-IN", 0x0A00, 0x0A7F),
    ("gu-IN", 0x0A80, 0x0AFF),
    ("ta-IN", 0x0B80, 0x0BFF),
    ("te-IN", 0x0C00, 0x0C7F),
    ("kn-IN", 0x0C80, 0x0CFF),
    ("ml-IN", 0x0D00, 0x0D7F),
    ("devanagari", 0x0900, 0x097F),
]

MARATHI_SCRIPT_HINTS = re.compile(
    r"(?:आहे|आहेत|नाही|केले|केली|तपासणी|बाळाचे|बाळ|मुलगा|मुलगी|औषध|लस|रक्तदाब|गरोदर|पुढची\s+भेट|भेट|माझ्या|तिचे|त्याचे)"
)

HINGLISH_LATIN_HINTS = re.compile(
    r"\b(?:aaj|maine|humne|unka|unki|iska|kya|hai|hain|nahi|nahin|kilo|goli|diya|di|gaya|gayi|agle|agla|bata|dijiye|karein|kar|raha|rahi|bukhar|khoon|saans|doodh|naam|vajan|wajan)\b",
    re.IGNORECASE,
)

LANGUAGE_SWITCH_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("hi-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\bhindi\b|\bhindi\s+(?:mein|me|please)\b|हिन्दी\s+में|हिंदी\s+में", re.I)),
    ("hi-en", re.compile(r"\b(?:hinglish|hindi[- ]english)\b", re.I)),
    ("en-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\benglish\b|\benglish\s+(?:mein|me|please)\b|अंग्रेजी\s+में", re.I)),
    ("ta-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\btamil\b|\btamil\s+(?:mein|me|la|please)\b|தமிழில்", re.I)),
    ("te-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\btelugu\b|\btelugu\s+(?:mein|me|lo|please)\b|తెలుగులో", re.I)),
    ("bn-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\b(?:bengali|bangla)\b|\b(?:bengali|bangla)\s+(?:mein|te|please)\b|বাংলায়|বাংলায়", re.I)),
    ("mr-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\bmarathi\b|\bmarathi\s+(?:madhe|madhye|mein|please)\b|मराठीत", re.I)),
    ("gu-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\bgujarati\b|\bgujarati\s+(?:ma|mein|please)\b|ગુજરાતીમાં", re.I)),
    ("kn-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\bkannada\b|\bkannada\s+(?:alli|dalli|mein|please)\b|ಕನ್ನಡದಲ್ಲಿ", re.I)),
    ("ml-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\bmalayalam\b|\bmalayalam\s+(?:il|mein|please)\b|മലയാളത്തിൽ|മലയാളത്തില്‍", re.I)),
    ("pa-IN", re.compile(r"\b(?:switch|change|speak|talk|reply|use)\b.*\bpunjabi\b|\bpunjabi\s+(?:vich|mein|please)\b|ਪੰਜਾਬੀ\s+ਵਿੱਚ", re.I)),
]


def normalize_language_code(raw: Optional[str], default: str = "hi-en") -> str:
    """Normalize a language string (e.g. 'ta', 'TA-in', 'tamil', 'hi-en') to canonical tag."""
    if not raw:
        return default
    cleaned = raw.strip()
    key = cleaned.lower().replace("_", "-")
    if key in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[key]
    # Support BCP-47 prefixes like "ta-IN-x-..." or "hi-en"
    for candidate in SUPPORTED_GNANI_LANGUAGES:
        if key == candidate.lower():
            return candidate
    prefix = key.split("-")[0]
    if prefix in LANGUAGE_ALIASES:
        resolved = LANGUAGE_ALIASES[prefix]
        if resolved in {"hi", "en"} and len(key) > 2:
            if key == "hi-en":
                return "hi-en"
            return "hi-IN" if resolved == "hi" else "en-IN"
        return resolved
    raise ValueError(
        f"Unsupported language '{raw}'. Supported: {sorted(SUPPORTED_GNANI_LANGUAGES.keys())} + ['hi-en', 'hi', 'en', 'auto']"
    )


def get_tts_locale(language: str) -> str:
    """Return canonical Gnani Timbre v3.0 BCP-47 TTS locale for any internal language tag."""
    norm = normalize_language_code(language, default="hi-en")
    return TTS_LOCALE_MAP.get(norm, "hi-IN")


def build_tts_metadata(language: str, detected_language: Optional[str] = None) -> Dict[str, Any]:
    """Build standardized metadata consumed by Person A's Gnani Timbre v3.0 TTS layer."""
    tts_locale = get_tts_locale(language)
    lang_info = SUPPORTED_GNANI_LANGUAGES.get(tts_locale, SUPPORTED_GNANI_LANGUAGES["hi-IN"])
    return {
        "tts_provider": "gnani_timbre_v3",
        "stt_provider": "gnani_prisma_v3",
        "language_code": tts_locale,
        "session_language": language,
        "detected_input_language": detected_language,
        "language_name": lang_info["name"],
        "script": lang_info["script"],
        "code_mixed": language == "hi-en",
    }


def detect_script_language(transcript: str) -> str:
    """Heuristic fallback script/language detector when Person A does not supply detected_language."""
    if not transcript or not transcript.strip():
        return "hi-en"

    counts: Dict[str, int] = {}
    for ch in transcript:
        cp = ord(ch)
        for tag, start, end in SCRIPT_RANGES:
            if start <= cp <= end:
                counts[tag] = counts.get(tag, 0) + 1
                break

    if counts:
        dominant = max(counts, key=lambda k: counts[k])
        if dominant == "devanagari":
            if MARATHI_SCRIPT_HINTS.search(transcript):
                return "mr-IN"
            return "hi-IN"
        return dominant

    # Pure Latin script: distinguish Hinglish vs Indian English
    if HINGLISH_LATIN_HINTS.search(transcript):
        return "hi-en"
    return "en-IN"


def detect_language_switch_command(transcript: str) -> Optional[str]:
    """Detect explicit mid-conversation worker request to switch interaction language."""
    for lang_code, pattern in LANGUAGE_SWITCH_PATTERNS:
        if pattern.search(transcript):
            return lang_code
    return None


@dataclass(frozen=True)
class LanguageResolution:
    active_language: str
    detected_language: str
    switched: bool = False
    explicit_switch_command: bool = False
    manual_locked: bool = False


def resolve_session_language(
    transcript: str,
    requested_language: Optional[str],
    current_session_language: Optional[str],
    detected_language: Optional[str] = None,
    preferred_language: Optional[str] = None,
    requested_explicit: bool = True,
    manual_language_locked: bool = False,
) -> LanguageResolution:
    """
    Resolve effective session language across manual preference, Gnani Prisma v3.0
    detected language, and mid-conversation language switches.
    """
    # 1. Explicit spoken switch request inside transcript always updates preference
    spoken_switch = detect_language_switch_command(transcript)
    if spoken_switch:
        return LanguageResolution(
            active_language=spoken_switch,
            detected_language=normalize_language_code(detected_language, default=spoken_switch)
            if detected_language
            else detect_script_language(transcript),
            switched=(current_session_language is not None and current_session_language != spoken_switch),
            explicit_switch_command=True,
            manual_locked=True,
        )

    # 2. Gnani Prisma v3.0 or script-level input language detection
    inferred_input = (
        normalize_language_code(detected_language, default="hi-en")
        if detected_language and detected_language.lower() != "auto"
        else detect_script_language(transcript)
    )

    # 3. Manual UI preference if explicitly supplied
    if preferred_language and preferred_language.lower() != "auto":
        pref = normalize_language_code(preferred_language)
        return LanguageResolution(
            active_language=pref,
            detected_language=inferred_input,
            switched=(current_session_language is not None and current_session_language != pref),
            manual_locked=True,
        )

    # 4. Explicit non-auto language parameter on request
    if requested_explicit and requested_language and requested_language.lower() != "auto":
        req = normalize_language_code(requested_language)
        return LanguageResolution(
            active_language=req,
            detected_language=inferred_input,
            switched=(current_session_language is not None and current_session_language != req),
            manual_locked=True,
        )

    # 5. If session has a manually locked language, keep it even if STT detects another input language
    if current_session_language:
        if (
            not manual_language_locked
            and requested_language
            and requested_language.lower() == "auto"
            and detected_language
        ):
            return LanguageResolution(
                active_language=inferred_input,
                detected_language=inferred_input,
                switched=(current_session_language != inferred_input),
                manual_locked=False,
            )
        return LanguageResolution(
            active_language=current_session_language,
            detected_language=inferred_input,
            switched=False,
            manual_locked=manual_language_locked,
        )

    # 6. First turn with language="auto" (or detected_language supplied)
    if (requested_language and requested_language.lower() == "auto") or detected_language:
        return LanguageResolution(
            active_language=inferred_input,
            detected_language=inferred_input,
            switched=False,
            manual_locked=False,
        )

    return LanguageResolution(
        active_language=normalize_language_code(requested_language, default="hi-en"),
        detected_language=inferred_input,
        switched=False,
        manual_locked=False,
    )


def _tkey(language: str) -> str:
    norm = normalize_language_code(language, default="hi-en")
    return TEMPLATE_KEY_MAP.get(norm, "hi-en")


# ---------------------------------------------------------------------------
# Multilingual Response & Prompt Dictionaries (All 10 Gnani Languages + hi-en)
# ---------------------------------------------------------------------------

FIXED_REFERRAL_MESSAGES: Dict[str, str] = {
    "hi-en": "Yeh ek danger sign hai. Kripya patient ko abhi nearest PHC refer karein.",
    "en": "This is a danger sign. Please refer the patient to the nearest PHC immediately.",
    "hi": "यह एक खतरे का संकेत है। कृपया मरीज को तुरंत नजदीकी पीएचसी (PHC) में रेफर करें।",
    "ta-IN": "இது ஒரு அபாய அறிகுறி. தயவுசெய்து நோயாளியை உடனடியாக அருகிலுள்ள PHC-க்கு பரிந்துரைக்கவும்.",
    "te-IN": "ఇది ప్రమాద సంకేతం. దయచేసి రోగిని వెంటనే సమీపంలోని PHCకి రిఫర్ చేయండి.",
    "bn-IN": "এটি একটি বিপদ সংকেত। অনুগ্রহ করে রোগীকে এখনই নিকটস্থ PHC-তে রেফার করুন।",
    "mr-IN": "हे धोक्याचे लक्षण आहे. कृपया रुग्णाला तात्काळ जवळच्या PHC मध्ये रेफर करा.",
    "gu-IN": "આ એક જોખમી સંકેત છે. કૃપા કરીને દર્દીને તરત જ નજીકના PHC માં રિફર કરો.",
    "kn-IN": "ಇದು ಅಪಾಯದ ಲಕ್ಷಣವಾಗಿದೆ. ದಯವಿಟ್ಟು ರೋಗಿಯನ್ನು ತಕ್ಷಣ ಹತ್ತಿರದ PHC ಗೆ ರೆಫರ್ ಮಾಡಿ.",
    "ml-IN": "ഇതൊരു അപകട ലക്ഷണമാണ്. ദയവായി രോഗിയെ ഉടൻ അടുത്തുള്ള PHC-യിലേക്ക് റഫർ ചെയ്യുക.",
    "pa-IN": "ਇਹ ਇੱਕ ਖ਼ਤਰੇ ਦਾ ਸੰਕੇਤ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਮਰੀਜ਼ ਨੂੰ ਤੁਰੰਤ ਨਜ਼ਦੀਕੀ PHC ਵਿੱਚ ਰੈਫਰ ਕਰੋ।",
}

REFUSAL_MESSAGES: Dict[str, str] = {
    "hi-en": "Main medicine ya treatment advice nahi de sakti. Kripya patient ko PHC ya doctor ke paas refer karein.",
    "en": "I cannot provide medical diagnosis, medicine, or treatment advice. Please refer the patient to a PHC or doctor.",
    "hi": "मैं दवा या इलाज की सलाह नहीं दे सकती। कृपया मरीज को पीएचसी (PHC) या डॉक्टर के पास रेफर करें।",
    "ta-IN": "நான் மருந்து அல்லது சிகிச்சை ஆலோசனை வழங்க முடியாது. தயவுசெய்து நோயாளியை PHC அல்லது மருத்துவரிடம் பரிந்துரைக்கவும்.",
    "te-IN": "నేను మందులు లేదా చికిత్స సలహా ఇవ్వలేను. దయచేసి రోగిని PHC లేదా డాక్టర్ వద్దకు రిఫర్ చేయండి.",
    "bn-IN": "আমি ওষুধ বা চিকিৎসার পরামর্শ দিতে পারি না। অনুগ্রহ করে রোগীকে PHC বা ডাক্তারের কাছে পাঠান।",
    "mr-IN": "मी औषध किंवा उपचाराचा सल्ला देऊ शकत नाही. कृपया रुग्णाला PHC किंवा डॉक्टरांकडे पाठवा.",
    "gu-IN": "હું દવા કે સારવારની સલાહ આપી શકતી નથી. કૃપા કરીને દર્દીને PHC અથવા ડૉક્ટર પાસે રિફર કરો.",
    "kn-IN": "ನಾನು ಔಷಧಿ ಅಥವಾ ಚಿಕಿತ್ಸೆಯ ಸಲಹೆ ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ರೋಗಿಯನ್ನು PHC ಅಥವಾ ವೈದ್ಯರ ಬಳಿಗೆ ಕಳುಹಿಸಿ.",
    "ml-IN": "എനിക്ക് മരുന്നുകളോ ചികിത്സാ ഉപദേശമോ നൽകാൻ കഴിയില്ല. ദയവായി രോഗിയെ PHC-യിലോ ഡോക്ടറുടെ അടുത്തോ റഫർ ചെയ്യുക.",
    "pa-IN": "ਮੈਂ ਦਵਾਈ ਜਾਂ ਇਲਾਜ ਦੀ ਸਲਾਹ ਨਹੀਂ ਦੇ ਸਕਦੀ। ਕਿਰਪਾ ਕਰਕੇ ਮਰੀਜ਼ ਨੂੰ PHC ਜਾਂ ਡਾਕਟਰ ਕੋਲ ਭੇਜੋ।",
}

INTRO_MESSAGES: Dict[str, str] = {
    "hi-en": "Namaste, main ASHA Saathi AI assistant hoon. Main visit record bharne mein madad karoongi, lekin main doctor nahi hoon aur dawai ya ilaj ki salah nahi de sakti.",
    "en": "Hello, I am the ASHA Saathi AI assistant. I help record visit details, but I am not a doctor and cannot give medical or treatment advice.",
    "hi": "नमस्ते, मैं आशा साथी AI असिस्टेंट हूँ। मैं विजिट रिकॉर्ड भरने में मदद करूँगी, लेकिन मैं डॉक्टर नहीं हूँ और दवा या इलाज की सलाह नहीं दे सकती।",
    "ta-IN": "வணக்கம், நான் ஆஷா சாத்தி AI உதவியாளர். வருகை பதிவுகளை நிரப்ப உதவுவேன், ஆனால் நான் மருத்துவர் அல்ல; மருந்து அல்லது சிகிச்சை ஆலோசனை வழங்க மாட்டேன்.",
    "te-IN": "నమస్కారం, నేను ఆశా సాథి AI సహాయకురాలిని. విజిట్ రికార్డు నమోదు చేయడంలో సహాయపడతాను, కానీ నేను డాక్టర్‌ను కాను మరియు మందుల సలహా ఇవ్వలేను.",
    "bn-IN": "নমস্কার, আমি আশা সাথী AI সহকারী। আমি ভিজিট রেকর্ড নথিভুক্ত করতে সাহায্য করব, তবে আমি ডাক্তার নই এবং ওষুধ বা চিকিৎসার পরামর্শ দিতে পারি না।",
    "mr-IN": "नमस्कार, मी आशा साथी AI सहाय्यक आहे. मी भेट नोंद भरण्यास मदत करेन, पण मी डॉक्टर नाही आणि औषध किंवा उपचाराचा सल्ला देऊ शकत नाही.",
    "gu-IN": "નમસ્તે, હું આશા સાથી AI સહાયક છું. હું મુલાકાતનો રેકોર્ડ ભરવામાં મદદ કરીશ, પરંતુ હું ડૉક્ટર નથી અને દવા કે સારવારની સલાહ આપી શકતી નથી.",
    "kn-IN": "ನಮಸ್ಕಾರ, ನಾನು ಆಶಾ ಸಾಥಿ AI ಸಹಾಯಕಿ. ಭೇಟಿ ದಾಖಲೆಗಳನ್ನು ಭರ್ತಿ ಮಾಡಲು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ, ಆದರೆ ನಾನು ವೈದ್ಯರಲ್ಲ ಮತ್ತು ಔಷಧಿ ಅಥವಾ ಚಿಕಿತ್ಸಾ ಸಲಹೆ ನೀಡುವುದಿಲ್ಲ.",
    "ml-IN": "നമസ്കാരം, ഞാൻ ആശാ സാഥി AI അസിസ്റ്റന്റാണ്. സന്ദർശന വിവരങ്ങൾ രേഖപ്പെടുത്താൻ സഹായിക്കാം, പക്ഷേ ഞാൻ ഡോക്ടറല്ല; മരുന്നുകളോ ചികിത്സയോ നിർദ്ദേശിക്കാൻ കഴിയില്ല.",
    "pa-IN": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਮੈਂ ਆਸ਼ਾ ਸਾਥੀ AI ਸਹਾਇਕ ਹਾਂ। ਮੈਂ ਵਿਜ਼ਿਟ ਰਿਕਾਰਡ ਭਰਨ ਵਿੱਚ ਮਦਦ ਕਰਾਂਗੀ, ਪਰ ਮੈਂ ਡਾਕਟਰ ਨਹੀਂ ਹਾਂ ਅਤੇ ਦਵਾਈ ਜਾਂ ਇਲਾਜ ਦੀ ਸਲਾਹ ਨਹੀਂ ਦੇ ਸਕਦੀ।",
}

FOLLOWUP_QUESTIONS: Dict[str, Dict[str, str]] = {
    "visit_type": {
        "hi-en": "Yeh kis tarah ka visit hai — ANC, PNC, newborn, ya vaccination?",
        "en": "What type of visit is this — ANC, PNC, newborn, or immunisation?",
        "hi": "यह किस तरह का विजिट है — ANC, PNC, नवजात, या टीकाकरण?",
        "ta-IN": "இது எந்த வகையான வருகை — ANC, PNC, பிறந்த குழந்தை, அல்லது தடுப்பூசி?",
        "te-IN": "ఇది ఏ రకమైన విజిట్ — ANC, PNC, నవజాత శిశువు, లేదా టీకా?",
        "bn-IN": "এটি কোন ধরনের ভিজিট — ANC, PNC, নবজাতক, নাকি টিকাকরণ?",
        "mr-IN": "ही कोणत्या प्रकारची भेट आहे — ANC, PNC, नवजात, की लसीकरण?",
        "gu-IN": "આ કયા પ્રકારની મુલાકાત છે — ANC, PNC, નવજાત, કે રસીકરણ?",
        "kn-IN": "ಇದು ಯಾವ ರೀತಿಯ ಭೇಟಿ — ANC, PNC, ನವಜಾತ, ಅಥವಾ ಲಸಿಕೆ?",
        "ml-IN": "ഇത് ഏത് തരത്തിലുള്ള സന്ദർശനമാണ് — ANC, PNC, നവജാത ശിശു, അതോ കുത്തിവയ്പ്പ്?",
        "pa-IN": "ਇਹ ਕਿਸ ਤਰ੍ਹਾਂ ਦੀ ਵਿਜ਼ਿਟ ਹੈ — ANC, PNC, ਨਵਜੰਮੇ ਬੱਚੇ, ਜਾਂ ਟੀਕਾਕਰਨ?",
    },
    "beneficiary_name": {
        "hi-en": "Beneficiary ka naam bata dijiye.",
        "en": "Please tell me the beneficiary's name.",
        "hi": "लाभार्थी का नाम बता दीजिए।",
        "ta-IN": "பயனாளியின் பெயரைச் சொல்லுங்கள்.",
        "te-IN": "లబ్ధిదారు పేరు చెప్పండి.",
        "bn-IN": "উপভোক্তার নাম বলুন।",
        "mr-IN": "लाभार्थ्याचे नाव सांगा.",
        "gu-IN": "લાભાર્થીનું નામ જણાવો.",
        "kn-IN": "ಫಲಾನುಭವಿಯ ಹೆಸರನ್ನು ತಿಳಿಸಿ.",
        "ml-IN": "ഗുണഭോക്താവിന്റെ പേര് പറയൂ.",
        "pa-IN": "ਲਾਭਪਾਤਰੀ ਦਾ ਨਾਮ ਦੱਸੋ।",
    },
    "beneficiary_id": {
        "hi-en": "Beneficiary ID bata dijiye.",
        "en": "Please provide the beneficiary ID.",
        "hi": "लाभार्थी ID बता दीजिए।",
        "ta-IN": "பயனாளி ID எண்ணைச் சொல்லுங்கள்.",
        "te-IN": "లబ్ధిదారు ID చెప్పండి.",
        "bn-IN": "উপভোক্তার ID নম্বরটি বলুন।",
        "mr-IN": "लाभार्थी ID क्रमांक सांगा.",
        "gu-IN": "લાભાર્થી ID જણાવો.",
        "kn-IN": "ಫಲಾನುಭವಿ ID ತಿಳಿಸಿ.",
        "ml-IN": "ഗുണഭോക്താവിന്റെ ID പറയൂ.",
        "pa-IN": "ਲਾਭਪਾਤਰੀ ID ਦੱਸੋ।",
    },
    "weight_kg": {
        "hi-en": "Unka weight kitna hai?",
        "en": "What is the weight in kilograms?",
        "hi": "वजन कितना किलो है?",
        "ta-IN": "எடை எத்தனை கிலோ உள்ளது?",
        "te-IN": "బరువు ఎన్ని కిలోలు ఉంది?",
        "bn-IN": "ওজন কত কেজি?",
        "mr-IN": "वजन किती किलो आहे?",
        "gu-IN": "વજન કેટલા કિલો છે?",
        "kn-IN": "ತೂಕ ಎಷ್ಟು ಕಿಲೋ ಇದೆ?",
        "ml-IN": "ഭാരം എത്ര കിലോ ആണ്?",
        "pa-IN": "ਵਜ਼ਨ ਕਿੰਨੇ ਕਿਲੋ ਹੈ?",
    },
    "blood_pressure": {
        "hi-en": "Blood pressure kitna hai?",
        "en": "What is the blood pressure reading?",
        "hi": "ब्लड प्रेशर कितना है?",
        "ta-IN": "இரத்த அழுத்தம் (BP) எவ்வளவு உள்ளது?",
        "te-IN": "రక్తపోటు (BP) ఎంత ఉంది?",
        "bn-IN": "রক্তচাপ (BP) কত?",
        "mr-IN": "रक्तदाब (BP) किती आहे?",
        "gu-IN": "બ્લડ પ્રેશર (BP) કેટલું છે?",
        "kn-IN": "ರಕ್ತದೊತ್ತಡ (BP) ಎಷ್ಟಿದೆ?",
        "ml-IN": "രക്തസമ്മർദ്ദം (BP) എത്രയാണ്?",
        "pa-IN": "ਬਲੱਡ ਪ੍ਰੈਸ਼ਰ (BP) ਕਿੰਨਾ ਹੈ?",
    },
    "ifa_status": {
        "hi-en": "Kya IFA goli di gayi hai?",
        "en": "Were IFA tablets provided?",
        "hi": "क्या IFA गोली दी गई है?",
        "ta-IN": "IFA மாத்திரைகள் வழங்கப்பட்டதா?",
        "te-IN": "IFA మాత్రలు ఇచ్చారా?",
        "bn-IN": "IFA ট্যাবলেট কি দেওয়া হয়েছে?",
        "mr-IN": "IFA गोळ्या दिल्या आहेत का?",
        "gu-IN": "શું IFA ગોળીઓ આપવામાં આવી છે?",
        "kn-IN": "IFA ಮಾತ್ರೆಗಳನ್ನು ನೀಡಲಾಗಿದೆಯೇ?",
        "ml-IN": "IFA ഗുളികകൾ നൽകിയിട്ടുണ്ടോ?",
        "pa-IN": "ਕੀ IFA ਗੋਲੀਆਂ ਦਿੱਤੀਆਂ ਗਈਆਂ ਹਨ?",
    },
    "vaccinations": {
        "hi-en": "Kaunsa vaccination hua hai?",
        "en": "Which vaccination was given?",
        "hi": "कौनसा टीका लगाया गया है?",
        "ta-IN": "எந்த தடுப்பூசி போடப்பட்டுள்ளது?",
        "te-IN": "ఏ టీకా వేశారు?",
        "bn-IN": "কোন টিকা দেওয়া হয়েছে?",
        "mr-IN": "कोणती लस दिली आहे?",
        "gu-IN": "કઈ રસી આપવામાં આવી છે?",
        "kn-IN": "ಯಾವ ಲಸಿಕೆ ಹಾಕಲಾಗಿದೆ?",
        "ml-IN": "ഏത് വാക്സിനാണ് നൽകിയത്?",
        "pa-IN": "ਕਿਹੜਾ ਟੀਕਾ ਲਗਾਇਆ ਗਿਆ ਹੈ?",
    },
    "next_visit_date": {
        "hi-en": "Next visit ki date kya hai?",
        "en": "What is the next visit date?",
        "hi": "अगली विजिट की तारीख क्या है?",
        "ta-IN": "அடுத்த வருகை தேதி என்ன?",
        "te-IN": "తదుపరి విజిట్ తేదీ ఏమిటి?",
        "bn-IN": "পরবর্তী ভিজিটের তারিখ কবে?",
        "mr-IN": "पुढच्या भेटीची तारीख काय आहे?",
        "gu-IN": "આગલી મુલાકાતની તારીખ કઈ છે?",
        "kn-IN": "ಮುಂದಿನ ಭೇಟಿಯ ದಿನಾಂಕ ಯಾವಾಗ?",
        "ml-IN": "അടുത്ത സന്ദർശന തീയതി എന്നാണ്?",
        "pa-IN": "ਅਗਲੀ ਵਿਜ਼ਿਟ ਦੀ ਤਾਰੀਖ਼ ਕੀ ਹੈ?",
    },
}

CLARIFICATION_MESSAGES: Dict[str, str] = {
    "hi-en": "Kaunsi jaankari badalni hai — naam, beneficiary ID, weight, BP, IFA, vaccination ya next visit date?",
    "en": "Which field would you like to correct — name, beneficiary ID, weight, blood pressure, IFA, vaccination, or next visit date?",
    "hi": "कौनसी जानकारी बदलनी है — नाम, लाभार्थी ID, वजन, BP, IFA, टीकाकरण या अगली विजिट की तारीख?",
    "ta-IN": "எந்த தகவலை மாற்ற வேண்டும் — பெயர், ID, எடை, BP, IFA, தடுப்பூசி, அல்லது அடுத்த வருகை தேதி?",
    "te-IN": "ఏ వివరాన్ని మార్చాలి — పేరు, ID, బరువు, BP, IFA, టీకా, లేదా తదుపరి విజిట్ తేదీ?",
    "bn-IN": "কোন তথ্যটি পরিবর্তন করতে চান — নাম, ID, ওজন, BP, IFA, টিকা, নাকি পরবর্তী ভিজিটের তারিখ?",
    "mr-IN": "कोणती माहिती बदलायची आहे — नाव, ID, वजन, BP, IFA, लसीकरण की पुढच्या भेटीची तारीख?",
    "gu-IN": "કઈ વિગત બદલવી છે — નામ, ID, વજન, BP, IFA, રસીકરણ કે આગલી મુલાકાતની તારીખ?",
    "kn-IN": "ಯಾವ ಮಾಹಿತಿಯನ್ನು ಬದಲಾಯಿಸಬೇಕು — ಹೆಸರು, ID, ತೂಕ, BP, IFA, ಲಸಿಕೆ, ಅಥವಾ ಮುಂದಿನ ಭೇಟಿ ದಿನಾಂಕ?",
    "ml-IN": "ഏത് വിവരമാണ് മാറ്റേണ്ടത് — പേര്, ID, ഭാരം, BP, IFA, വാക്സിനേഷൻ, അതോ അടുത്ത സന്ദർശന തീയതി?",
    "pa-IN": "ਕਿਹੜੀ ਜਾਣਕਾਰੀ ਬਦਲਣੀ ਹੈ — ਨਾਮ, ID, ਵਜ਼ਨ, BP, IFA, ਟੀਕਾਕਰਨ, ਜਾਂ ਅਗਲੀ ਵਿਜ਼ਿਟ ਦੀ ਤਾਰੀਖ਼?",
}

FIELD_LABELS: Dict[str, Dict[str, str]] = {
    "beneficiary_name": {
        "hi-en": "Beneficiary naam",
        "en": "beneficiary name",
        "hi": "लाभार्थी का नाम",
        "ta-IN": "பயனாளி பெயர்",
        "te-IN": "లబ్ధిదారు పేరు",
        "bn-IN": "উপভোক্তার নাম",
        "mr-IN": "लाभार्थ्याचे नाव",
        "gu-IN": "લાભાર્થીનું નામ",
        "kn-IN": "ಫಲಾನುಭವಿ ಹೆಸರು",
        "ml-IN": "ഗുണഭോക്താവിന്റെ പേര്",
        "pa-IN": "ਲਾਭਪਾਤਰੀ ਦਾ ਨਾਮ",
    },
    "beneficiary_id": {
        "hi-en": "Beneficiary ID",
        "en": "beneficiary ID",
        "hi": "लाभार्थी ID",
        "ta-IN": "பயனாளி ID",
        "te-IN": "లబ్ధిదారు ID",
        "bn-IN": "উপভোক্তার ID",
        "mr-IN": "लाभार्थी ID",
        "gu-IN": "લાભાર્થી ID",
        "kn-IN": "ಫಲಾನುಭವಿ ID",
        "ml-IN": "ഗുണഭോക്താവിന്റെ ID",
        "pa-IN": "ਲਾਭਪਾਤਰੀ ID",
    },
    "visit_type": {
        "hi-en": "Visit type",
        "en": "visit type",
        "hi": "विजिट का प्रकार",
        "ta-IN": "வருகை வகை",
        "te-IN": "విజిట్ రకం",
        "bn-IN": "ভিজিটের ধরন",
        "mr-IN": "भेटीचा प्रकार",
        "gu-IN": "મુલાકાતનો પ્રકાર",
        "kn-IN": "ಭೇಟಿ ಪ್ರಕಾರ",
        "ml-IN": "സന്ദർശന തരം",
        "pa-IN": "ਵਿਜ਼ਿਟ ਦੀ ਕਿਸਮ",
    },
    "weight_kg": {
        "hi-en": "Weight",
        "en": "weight",
        "hi": "वजन",
        "ta-IN": "எடை",
        "te-IN": "బరువు",
        "bn-IN": "ওজন",
        "mr-IN": "वजन",
        "gu-IN": "વજન",
        "kn-IN": "ತೂಕ",
        "ml-IN": "ഭാരം",
        "pa-IN": "ਵਜ਼ਨ",
    },
    "blood_pressure": {
        "hi-en": "Blood pressure",
        "en": "blood pressure",
        "hi": "ब्लड प्रेशर",
        "ta-IN": "இரத்த அழுத்தம்",
        "te-IN": "రక్తపోటు",
        "bn-IN": "রক্তচাপ",
        "mr-IN": "रक्तदाब",
        "gu-IN": "બ્લડ પ્રેશર",
        "kn-IN": "ರಕ್ತದೊತ್ತಡ",
        "ml-IN": "രക്തസമ്മർദ്ദം",
        "pa-IN": "ਬਲੱਡ ਪ੍ਰੈਸ਼ਰ",
    },
    "ifa_status": {
        "hi-en": "IFA status",
        "en": "IFA status",
        "hi": "IFA स्थिति",
        "ta-IN": "IFA நிலை",
        "te-IN": "IFA స్థితి",
        "bn-IN": "IFA অবস্থা",
        "mr-IN": "IFA स्थिती",
        "gu-IN": "IFA સ્થિતિ",
        "kn-IN": "IFA ಸ್ಥಿತಿ",
        "ml-IN": "IFA നില",
        "pa-IN": "IFA ਸਥਿತಿ",
    },
    "vaccinations": {
        "hi-en": "Vaccination",
        "en": "vaccination status",
        "hi": "टीकाकरण",
        "ta-IN": "தடுப்பூசி",
        "te-IN": "టీకా",
        "bn-IN": "টিকাকরণ",
        "mr-IN": "लसीकरण",
        "gu-IN": "રસીકરણ",
        "kn-IN": "ಲಸಿಕೆ",
        "ml-IN": "വാക്സിനേഷൻ",
        "pa-IN": "ਟੀਕਾਕਰਨ",
    },
    "next_visit_date": {
        "hi-en": "Next visit date",
        "en": "next visit date",
        "hi": "अगली विजिट की तारीख",
        "ta-IN": "அடுத்த வருகை தேதி",
        "te-IN": "తదుపరి విజిట్ తేదీ",
        "bn-IN": "পরবর্তী ভিজিটের তারিখ",
        "mr-IN": "पुढच्या भेटीची तारीख",
        "gu-IN": "આગલી મુલાકાતની તારીખ",
        "kn-IN": "ಮುಂದಿನ ಭೇಟಿ ದಿನಾಂಕ",
        "ml-IN": "അടുത്ത സന്ദർശന തീയതി",
        "pa-IN": "ਅਗਲੀ ਵਿਜ਼ਿਟ ਦੀ ਤਾਰੀਖ਼",
    },
}

UI_PHRASES: Dict[str, Dict[str, str]] = {
    "confirm_question": {
        "hi-en": "Kya main record save kar doon?",
        "en": "Should I save this record?",
        "hi": "क्या मैं यह रिकॉर्ड सेव कर दूँ?",
        "ta-IN": "இந்தப் பதிவை சேமிக்கலாமா?",
        "te-IN": "ఈ రికార్డును సేవ్ చేయమంటారా?",
        "bn-IN": "আমি কি এই রেকর্ডটি সেভ করব?",
        "mr-IN": "मी ही नोंद सेव्ह करू का?",
        "gu-IN": "શું હું આ રેકોર્ડ સેવ કરું?",
        "kn-IN": "ನಾನು ಈ ದಾಖಲೆಯನ್ನು ಸೇವ್ ಮಾಡಲೇ?",
        "ml-IN": "ഈ വിവരങ്ങൾ സേവ് ചെയ്യട്ടെ?",
        "pa-IN": "ਕੀ ਮੈਂ ਇਹ ਰਿਕਾਰਡ ਸੇਵ ਕਰ ਦੇਵਾਂ?",
    },
    "saved_ack": {
        "hi-en": "Dhanyawad. {name} ka visit record confirm ho gaya hai aur save karne ke liye ready hai.",
        "en": "Thank you. Visit record for {name} is confirmed and ready to save.",
        "hi": "धन्यवाद। {name} का विजिट रिकॉर्ड कन्फर्म हो गया है और सेव के लिए तैयार है।",
        "ta-IN": "நன்றி. {name} அவர்களின் வருகை பதிவு உறுதி செய்யப்பட்டு சேமிக்க தயாராக உள்ளது.",
        "te-IN": "ధన్యవాదాలు. {name} యొక్క విజిట్ రికార్డు నిర్ధారించబడింది మరియు సేవ్ చేయడానికి సిద్ధంగా ఉంది.",
        "bn-IN": "ধন্যবাদ। {name}-এর ভিজিট রেকর্ড নিশ্চিত হয়েছে এবং সেভ করার জন্য প্রস্তুত।",
        "mr-IN": "धन्यवाद. {name} यांची भेट नोंद निश्चित झाली असून सेव्ह करण्यासाठी तयार आहे.",
        "gu-IN": "આભાર. {name} નો મુલાકાત રેકોર્ડ કન્ફર્મ થઈ ગયો છે અને સેવ કરવા માટે તૈયાર છે.",
        "kn-IN": "ಧನ್ಯವಾದಗಳು. {name} ಅವರ ಭೇಟಿ ದಾಖಲೆ ದೃಢೀಕರಿಸಲ್ಪಟ್ಟಿದೆ ಮತ್ತು ಸೇವ್ ಮಾಡಲು ಸಿದ್ಧವಾಗಿದೆ.",
        "ml-IN": "നന്ദി. {name}-ന്റെ സന്ദർശന രേഖ സ്ഥിരീകരിച്ചു, സേവ് ചെയ്യാൻ തയ്യാറാണ്.",
        "pa-IN": "ਧੰਨਵਾਦ। {name} ਦਾ ਵਿਜ਼ਿਟ ਰਿਕਾਰਡ ਪੱਕਾ ਹੋ ਗਿਆ ਹੈ ਅਤੇ ਸੇਵ ਕਰਨ ਲਈ ਤਿਆਰ ਹੈ।",
    },
    "rejected_ack": {
        "hi-en": "Theek hai, record save nahi kiya hai. Kripya batayein kya change karna hai.",
        "en": "Okay, I have not saved this record. Please tell me what needs to be changed.",
        "hi": "ठीक है, रिकॉर्ड सेव नहीं किया गया है। कृपया बताएं क्या बदलना है।",
        "ta-IN": "சரி, பதிவு சேமிக்கப்படவில்லை. எதை மாற்ற வேண்டும் என்று சொல்லுங்கள்.",
        "te-IN": "సరే, రికార్డు సేవ్ చేయలేదు. ఏమి మార్చాలో చెప్పండి.",
        "bn-IN": "ঠিক আছে, রেকর্ডটি সেভ করা হয়নি। অনুগ্রহ করে বলুন কী পরিবর্তন করতে হবে।",
        "mr-IN": "ठीक आहे, नोंद सेव्ह केलेली नाही. कृपया काय बदलायचे ते सांगा.",
        "gu-IN": "ઠીક છે, રેકોર્ડ સેવ કર્યો નથી. કૃપા કરીને જણાવો કે શું બદલવું છે.",
        "kn-IN": "ಸರಿ, ದಾಖಲೆಯನ್ನು ಸೇವ್ ಮಾಡಿಲ್ಲ. ದಯವಿಟ್ಟು ಏನು ಬದಲಾಯಿಸಬೇಕು ಎಂದು ತಿಳಿಸಿ.",
        "ml-IN": "ശരി, രേഖ സേവ് ചെയ്തിട്ടില്ല. എന്താണ് മാറ്റേണ്ടതെന്ന് ദയവായി പറയൂ.",
        "pa-IN": "ਠੀਕ ਹੈ, ਰਿਕਾਰਡ ਸੇਵ ਨਹੀਂ ਕੀਤਾ ਗਿਆ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਦੱਸੋ ਕਿ ਕੀ ਬਦਲਣਾ ਹੈ।",
    },
    "updated_ack": {
        "hi-en": "{fields} update kar diya hai.",
        "en": "Updated {fields}.",
        "hi": "{fields} अपडेट कर दिया है।",
        "ta-IN": "{fields} புதுப்பிக்கப்பட்டது.",
        "te-IN": "{fields} అప్‌డేట్ చేయబడింది.",
        "bn-IN": "{fields} আপডেট করা হয়েছে।",
        "mr-IN": "{fields} अपडेट केले आहे.",
        "gu-IN": "{fields} અપડેટ કર્યું છે.",
        "kn-IN": "{fields} ಅಪ್‌ಡೇಟ್ ಮಾಡಲಾಗಿದೆ.",
        "ml-IN": "{fields} അപ്ഡേറ്റ് ചെയ്തു.",
        "pa-IN": "{fields} ਅੱਪਡੇਟ ਕਰ ਦਿੱਤਾ ਗਿਆ ਹੈ।",
    },
    "ambiguous_date": {
        "hi-en": "'{ref}' se exact date clear nahi hai. Kripya next visit ka din ya date bata dijiye.",
        "en": "'{ref}' is not a specific date. Please specify the exact day or date for the next visit.",
        "hi": "'{ref}' से पक्की तारीख साफ नहीं हुई। कृपया अगली विजिट का दिन या तारीख बताएं।",
        "ta-IN": "'{ref}' என்பதில் சரியான தேதி தெளிவாக இல்லை. அடுத்த வருகையின் நாள் அல்லது தேதியைச் சொல்லுங்கள்.",
        "te-IN": "'{ref}' నుండి ఖచ్చితమైన తేదీ స్పష్టంగా లేదు. తదుపరి విజిట్ రోజు లేదా తేదీ చెప్పండి.",
        "bn-IN": "'{ref}' থেকে নির্দিষ্ট তারিখ বোঝা যাচ্ছে না। অনুগ্রহ করে পরবর্তী ভিজিটের দিন বা তারিখ বলুন।",
        "mr-IN": "'{ref}' वरून नक्की तारीख स्पष्ट होत नाही. कृपया पुढच्या भेटीचा दिवस किंवा तारीख सांगा.",
        "gu-IN": "'{ref}' પરથી ચોક્કસ તારીખ સ્પષ્ટ નથી. કૃપા કરીને આગલી મુલાકાતનો દિવસ કે તારીખ જણાવો.",
        "kn-IN": "'{ref}' ನಿಂದ ನಿಖರ ದಿನಾಂಕ ಸ್ಪಷ್ಟವಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು ಮುಂದಿನ ಭೇಟಿಯ ದಿನ ಅಥವಾ ದಿನಾಂಕ ತಿಳಿಸಿ.",
        "ml-IN": "'{ref}' എന്നതിൽ കൃത്യമായ തീയതി വ്യക്തമല്ല. അടുത്ത സന്ദർശനത്തിന്റെ ദിവസമോ തീയതിയോ പറയൂ.",
        "pa-IN": "'{ref}' ਤੋਂ ਪੱਕੀ ਤਾਰੀਖ਼ ਸਪਸ਼ਟ ਨਹੀਂ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਅਗਲੀ ਵਿਜ਼ਿਟ ਦਾ ਦਿਨ ਜਾਂ ਤਾਰੀਖ਼ ਦੱਸੋ।",
    },
    "language_switched": {
        "hi-en": "Language update ho gayi hai. Purana record surakshit hai.",
        "en": "Language updated. Your current visit record is preserved.",
        "hi": "भाषा बदल दी गई है। आपका पिछला रिकॉर्ड सुरक्षित है।",
        "ta-IN": "மொழி மாற்றப்பட்டது. உங்கள் தற்போதைய பதிவு பாதுகாக்கப்பட்டுள்ளது.",
        "te-IN": "భాష మార్చబడింది. మీ ప్రస్తుత విజిట్ రికార్డు భద్రంగా ఉంది.",
        "bn-IN": "ভাষা পরিবর্তন করা হয়েছে। আপনার আগের তথ্য সুরক্ষিত আছে।",
        "mr-IN": "भाषा बदलली आहे. तुमची आधीची नोंद सुरक्षित आहे.",
        "gu-IN": "ભાષા બદલાઈ ગઈ છે. તમારો હાલનો રેકોર્ડ સુરક્ષિત છે.",
        "kn-IN": "ಭಾಷೆಯನ್ನು ಬದಲಾಯಿಸಲಾಗಿದೆ. ನಿಮ್ಮ ಪ್ರಸ್ತುತ ದಾಖಲೆ ಸುರಕ್ಷಿತವಾಗಿದೆ.",
        "ml-IN": "ഭാഷ മാറ്റിയിട്ടുണ്ട്. നിങ്ങളുടെ നിലവിലെ വിവരങ്ങൾ സുരക്ഷിതമാണ്.",
        "pa-IN": "ਭਾਸ਼ਾ ਬਦਲ ਦਿੱਤੀ ਗਈ ਹੈ। ਤੁਹਾਡਾ ਮੌਜੂਦਾ ਰਿਕਾਰਡ ਸੁਰੱਖਿਅਤ ਹੈ।",
    },
    "beneficiary_conflict": {
        "hi-en": "Is session mein abhi {active} ka record chal raha hai. Record mix na ho isliye kripya {target} ke liye naya session shuru karein.",
        "en": "This session currently holds the record for {active}. Please use a separate session for {target} to avoid mixing records.",
        "hi": "इस सेशन में अभी {active} का रिकॉर्ड चल रहा है। रिकॉर्ड मिक्स न हो इसके लिए कृपया {target} के लिए नया सेशन शुरू करें।",
        "ta-IN": "இந்த அமர்வில் தற்போது {active} அவர்களின் பதிவு உள்ளது. பதிவுகள் கலக்காமல் இருக்க {target} க்கு புதிய அமர்வு தொடங்கவும்.",
        "te-IN": "ఈ సెషన్‌లో ప్రస్తుతం {active} రికార్డు ఉంది. రికార్డులు కలవకుండా {target} కోసం కొత్త సెషన్ ప్రారంభించండి.",
        "bn-IN": "এই সেশনে বর্তমানে {active}-এর রেকর্ড চলছে। তথ্য মিশে যাওয়া এড়াতে {target}-এর জন্য নতুন সেশন শুরু করুন।",
        "mr-IN": "या सेशनमध्ये सध्या {active} यांची नोंद सुरू आहे. नोंदी एकत्र होऊ नयेत म्हणून कृपया {target} साठी नवीन सेशन सुरू करा.",
        "gu-IN": "આ સેશનમાં હાલમાં {active} નો રેકોર્ડ ચાલી રહ્યો છે. રેકોર્ડ ભેગા ન થાય તે માટે {target} માટે નવું સેશન શરૂ કરો.",
        "kn-IN": "ಈ ಸೆಷನ್‌ನಲ್ಲಿ ಪ್ರಸ್ತುತ {active} ಅವರ ದಾಖಲೆ ಇದೆ. ದಾಖಲೆಗಳು ಮಿಶ್ರಣವಾಗದಂತೆ {target} ಗಾಗಿ ಹೊಸ ಸೆಷನ್ ಪ್ರಾರಂಭಿಸಿ.",
        "ml-IN": "ഈ സെഷനിൽ നിലവിൽ {active}-ന്റെ വിവരങ്ങളാണ് ഉള്ളത്. വിവരങ്ങൾ കലരാതിരിക്കാൻ {target}-നായി പുതിയ സെഷൻ തുടങ്ങുക.",
        "pa-IN": "ਇਸ ਸੈਸ਼ਨ ਵਿੱਚ ਹੁਣ {active} ਦਾ ਰਿਕਾਰਡ ਚੱਲ ਰਿਹਾ ਹੈ। ਰਿਕਾਰਡ ਮਿਕਸ ਨਾ ਹੋਣ ਲਈ ਕਿਰਪਾ ਕਰਕੇ {target} ਲਈ ਨਵਾਂ ਸੈਸ਼ਨ ਸ਼ੁਰੂ ਕਰੋ।",
    },
    "ack_name": {
        "hi-en": "{name} ka checkup record kar rahi hoon.",
        "en": "Recording visit for {name}.",
        "hi": "{name} का विजिट रिकॉर्ड कर रही हूँ।",
        "ta-IN": "{name} அவர்களின் வருகையை பதிவு செய்கிறேன்.",
        "te-IN": "{name} యొక్క విజిట్ నమోదు చేస్తున్నాను.",
        "bn-IN": "{name}-এর ভিজিট রেকর্ড করছি।",
        "mr-IN": "{name} यांची भेट नोंदवत आहे.",
        "gu-IN": "{name} ની મુલાકાત નોંધી રહી છું.",
        "kn-IN": "{name} ಅವರ ಭೇಟಿಯನ್ನು ದಾಖಲಿಸುತ್ತಿದ್ದೇನೆ.",
        "ml-IN": "{name}-ന്റെ സന്ദർശനം രേഖപ്പെടുത്തുന്നു.",
        "pa-IN": "{name} ਦੀ ਵਿਜ਼ਿਟ ਦਰਜ ਕਰ ਰਹੀ ਹਾਂ।",
    },
    "ack_weight": {
        "hi-en": "Weight {wt} kilo record kiya hai.",
        "en": "Recorded weight {wt} kg.",
        "hi": "वजन {wt} किलो दर्ज किया है।",
        "ta-IN": "எடை {wt} கிலோ பதிவு செய்யப்பட்டது.",
        "te-IN": "బరువు {wt} కిలోలు నమోదు చేయబడింది.",
        "bn-IN": "ওজন {wt} কেজি নথিভুক্ত হয়েছে।",
        "mr-IN": "वजन {wt} किलो नोंदवले आहे.",
        "gu-IN": "વજન {wt} કિલો નોંધાયું છે.",
        "kn-IN": "ತೂಕ {wt} ಕಿಲೋ ದಾಖಲಿಸಲಾಗಿದೆ.",
        "ml-IN": "ഭാരം {wt} കിലോ രേഖപ്പെടുത്തി.",
        "pa-IN": "ਵਜ਼ਨ {wt} ਕਿਲੋ ਦਰਜ ਕੀਤਾ ਗਿਆ ਹੈ।",
    },
    "ack_id": {
        "hi-en": "Beneficiary ID {bid} record kiya hai.",
        "en": "Recorded beneficiary ID {bid}.",
        "hi": "लाभार्थी ID {bid} दर्ज की है।",
        "ta-IN": "பயனாளி ID {bid} பதிவு செய்யப்பட்டது.",
        "te-IN": "లబ్ధిదారు ID {bid} నమోదు చేయబడింది.",
        "bn-IN": "উপভোক্তার ID {bid} নথিভুক্ত হয়েছে।",
        "mr-IN": "लाभार्थी ID {bid} नोंदवला आहे.",
        "gu-IN": "લાભાર્થી ID {bid} નોંધાયું છે.",
        "kn-IN": "ಫಲಾನುಭವಿ ID {bid} ದಾಖಲಿಸಲಾಗಿದೆ.",
        "ml-IN": "ഗുണഭോക്താവിന്റെ ID {bid} രേഖപ്പെടുത്തി.",
        "pa-IN": "ਲਾਭਪਾਤਰੀ ID {bid} ਦਰਜ ਕੀਤੀ ਗਈ ਹੈ।",
    },
    "ack_bp": {
        "hi-en": "Blood pressure {bp} record kiya hai.",
        "en": "Recorded blood pressure {bp}.",
        "hi": "ब्लड प्रेशर {bp} दर्ज किया है।",
        "ta-IN": "இரத்த அழுத்தம் {bp} பதிவு செய்யப்பட்டது.",
        "te-IN": "రక్తపోటు {bp} నమోదు చేయబడింది.",
        "bn-IN": "রক্তচাপ {bp} নথিভুক্ত হয়েছে।",
        "mr-IN": "रक्तदाब {bp} नोंदवला आहे.",
        "gu-IN": "બ્લડ પ્રેશર {bp} નોંધાયું છે.",
        "kn-IN": "ರಕ್ತದೊತ್ತಡ {bp} ದಾಖಲಿಸಲಾಗಿದೆ.",
        "ml-IN": "രക്തസമ്മർദ്ദം {bp} രേഖപ്പെടുത്തി.",
        "pa-IN": "ਬਲੱਡ ਪ੍ਰੈਸ਼ਰ {bp} ਦਰਜ ਕੀਤਾ ਗਿਆ ਹੈ।",
    },
    "clarify_prefix": {
        "hi-en": "Kripya spasht karein:",
        "en": "Please clarify:",
        "hi": "कृपया स्पष्ट करें:",
        "ta-IN": "தயவுசெய்து தெளிவுபடுத்தவும்:",
        "te-IN": "దయచేసి స్పష్టం చేయండి:",
        "bn-IN": "অনুগ্রহ করে স্পষ্ট করুন:",
        "mr-IN": "कृपया स्पष्ट करा:",
        "gu-IN": "કૃપા કરીને સ્પષ્ટ કરો:",
        "kn-IN": "ದಯವಿಟ್ಟು ಸ್ಪಷ್ಟಪಡಿಸಿ:",
        "ml-IN": "ദയവായി വ്യക്തമാക്കുക:",
        "pa-IN": "ਕਿਰਪਾ ਕਰਕੇ ਸਪੱਸ਼ਟ ਕਰੋ:",
    },
}


def get_referral_message(language: str) -> str:
    return FIXED_REFERRAL_MESSAGES.get(_tkey(language), FIXED_REFERRAL_MESSAGES["hi-en"])


def get_refusal_message(language: str) -> str:
    return REFUSAL_MESSAGES.get(_tkey(language), REFUSAL_MESSAGES["hi-en"])


def get_intro_message(language: str, overrides: Optional[Dict[str, str]] = None) -> str:
    key = _tkey(language)
    if overrides:
        if language in overrides:
            return overrides[language]
        if key in overrides:
            return overrides[key]
    return INTRO_MESSAGES.get(key, INTRO_MESSAGES["hi-en"])


def get_followup_question(field_name: str, language: str) -> str:
    key = _tkey(language)
    field_map = FOLLOWUP_QUESTIONS.get(field_name, {})
    return field_map.get(key) or field_map.get("hi-en") or f"Kripya {field_name} bata dijiye."


def get_clarification_message(language: str) -> str:
    return CLARIFICATION_MESSAGES.get(_tkey(language), CLARIFICATION_MESSAGES["hi-en"])


def get_field_label(field_name: str, language: str) -> str:
    key = _tkey(language)
    return FIELD_LABELS.get(field_name, {}).get(key) or FIELD_LABELS.get(field_name, {}).get("en") or field_name


def get_ui_phrase(phrase_key: str, language: str, **kwargs: Any) -> str:
    key = _tkey(language)
    template = UI_PHRASES.get(phrase_key, {}).get(key) or UI_PHRASES.get(phrase_key, {}).get("hi-en", "")
    return template.format(**kwargs) if kwargs else template
