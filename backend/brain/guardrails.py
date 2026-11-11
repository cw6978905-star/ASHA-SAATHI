"""Module 6: Multilingual Responsible AI Medical Safety Guardrails (All 10 Gnani Languages)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional

from brain.languages import (
    REFUSAL_MESSAGES as ALL_REFUSAL_MESSAGES,
    get_intro_message as lang_get_intro_message,
    get_refusal_message as lang_get_refusal_message,
)
from models.visit_schema import LanguageCode

# Preserve backwards-compatible export
REFUSAL_MESSAGES: Dict[str, str] = dict(ALL_REFUSAL_MESSAGES)

INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|safety|system)\s+(?:instructions|rules|protocols?)\b", re.I),
    re.compile(r"\b(?:override|bypass|disable|turn\s+off|forget)\s+(?:all\s+)?(?:safety|guardrails?|rules?|protocols?)\b", re.I),
    re.compile(r"\b(?:act|pretend|behave)\s+(?:as|like)\s+(?:a\s+)?doctor\b", re.I),
    re.compile(r"\b(?:doctor\s+ban\s+kar|rules?\s+bhool\s+jao|safety\s+band\s+karo|niyam\s+bhool)\b", re.I),
    re.compile(r"\b(?:give|tell)\s+(?:the\s+)?(?:dosage|medicine)\s+anyway\b", re.I),
    # Indic safety-override / jailbreak attempts across all supported scripts
    re.compile(r"(?:नियम\s*भूल|सुरक्षा\s*नियम\s*हटा|डॉक्टर\s*बन\s*कर\s*(?:दवा|इलाज))"),
    re.compile(r"(?:விதிகளை\s*(?:மீறி|மறந்து)|நியமங்களை\s*மறந்து|மருத்துவராக\s*நடித்து)"),
    re.compile(r"(?:నియమాలు\s*(?:పక్కన\s*పెట్టి|మర్చిపోయి)|డాక్టర్‌లా\s*మందు)"),
    re.compile(r"(?:নিয়ম\s*ভুলে|সুরক্ষা\s*নিয়ম\s*বাদ\s*দিয়ে|ডাক্তার\s*সেজে)"),
    re.compile(r"(?:नियम\s*विसरून|सुरक्षा\s*नियम\s*बंद|डॉक्टर\s*म्हणून\s*औषध)"),
    re.compile(r"(?:નિયમો\s*ભૂલીને|સુરક્ષા\s*નિયમ\s*બંધ|ડૉક્ટર\s*બનીને\s*દવા)"),
    re.compile(r"(?:ನಿಯಮಗಳನ್ನು\s*ಮರೆತು|ಸುರಕ್ಷತಾ\s*ನಿಯಮ\s*ಬಿಟ್ಟು|ವೈದ್ಯರಾಗಿ\s*ಔಷಧಿ)"),
    re.compile(r"(?:നിയമങ്ങൾ\s*മറന്ന്|സുരക്ഷാ\s*നിയമങ്ങൾ\s*ഒഴിവാക്കി|ഡോക്ടറായി\s*മരുന്ന്)"),
    re.compile(r"(?:ਨਿਯਮ\s*ਭੁੱਲ\s*ਕੇ|ਸੁਰੱਖਿਆ\s*ਨਿਯਮ\s*ਛੱਡ|ਡਾਕਟਰ\s*ਬਣ\s*ਕੇ\s*ਦਵਾਈ)"),
]

MEDICAL_ADVICE_REQUEST_PATTERNS = [
    # English, Hinglish & Indic-English code-mixed patterns
    re.compile(
        r"\b(?:kaun\s*si|kaunsi|konsi|kya|which|what|enna|endha|ye|yeh|ki|kon|konti|kai|yava|ethu|kehri)\s+"
        r"(?:medicine|medicines|dawai|dawa|tablet|tablets|goli|syrup|antibiotic|injection|treatment|illness|disease)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:medicine|dawai|dawa|tablet|tablets|goli|syrup|dose|dosage)\s+"
        r"(?:deni\s+chahiye|de\s+sakte|du|doon|batao|bataiye|recommend|suggest|prescribe|"
        r"kodukanum|kodukkalam|ivvali|cheppandi|debo|dite\s+hobe|dyavi|dyave|aapvi|kodabeku|kodukkanam|deni\s+chahidi)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:kitni|kitna|how\s+much|how\s+many|what|evvalavu|entha|koto|kiti|ketli|eshtu|ethra|kinni)\s+"
        r"(?:dose|dosage|mg|ml|goli|tablets?|medicine)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:should\s+i\s+give|can\s+i\s+give|can\s+we\s+give|prescribe|recommend\s+medication)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:kaun\s*si|kaunsi|kya|what)\s+(?:bimari|disease|infection|problem)\s+(?:hai|is\s+this|could\s+this\s+be)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:diagnose|diagnosis|kya\s+ilaj|ilaj\s+batao|treatment\s+(?:batao|advice|plan)|how\s+to\s+treat|cure\s+kaise|gharelu\s+upay|home\s+remedy)\b",
        re.I,
    ),
    # Hindi (hi-IN)
    re.compile(r"(?:कौनसी|कौन\s*सी|क्या)\s*(?:दवा|दवाई|गोली|बीमारी)|(?:दवाई\s*(?:बताओ|दें)|दवा\s*(?:दें|बताएं)|इलाज\s*(?:बताओ|बताएं)|कितनी\s*(?:डोज|खुराक|मात्रा))"),
    # Tamil (ta-IN)
    re.compile(r"(?:எந்த\s*(?:மருந்து|மாத்திரை)|மருந்து\s*(?:கொடுக்க|சொல்ல)|எவ்வளவு\s*(?:அளவு|டோஸ்)|சிகிச்சை\s*(?:சொல்லுங்கள்|அளிக்க)|என்ன\s*நோய்)"),
    # Telugu (te-IN)
    re.compile(r"(?:ఏ\s*(?:మందు|మాత్ర)|మందు\s*(?:ఇవ్వాలి|చెప్పండి)|ఎంత\s*మోతాదు|చికిత్స\s*చెప్పండి|ఏ\s*వ్యాధి)"),
    # Bengali (bn-IN)
    re.compile(r"(?:কোন\s*(?:ওষুধ|ট্যাবলেট)|ওষুধ\s*(?:দিতে|বলুন)|কত\s*ডোজ|চিকিৎসা\s*বলুন|কী\s*রোগ)"),
    # Marathi (mr-IN)
    re.compile(r"(?:कोणते\s*(?:औषध|गोळी)|औषध\s*(?:द्यावे|सांगा)|किती\s*डोस|उपचार\s*सांगा|कोणता\s*आजार)"),
    # Gujarati (gu-IN)
    re.compile(r"(?:કઈ\s*(?:દવા|ગોળી)|દવા\s*(?:આપવી|જણાવો)|કેટલો\s*ડોઝ|સારવાર\s*જણાવો|કયો\s*રોગ)"),
    # Kannada (kn-IN)
    re.compile(r"(?:ಯಾವ\s*(?:ಔಷಧಿ|ಮಾತ್ರೆ)|ಔಷಧಿ\s*(?:ಕೊಡಬೇಕು|ಹೇಳಿ)|ಎಷ್ಟು\s*ಡೋಸ್|ಚಿಕಿತ್ಸೆ\s*ಹೇಳಿ|ಯಾವ\s*ರೋಗ)"),
    # Malayalam (ml-IN)
    re.compile(r"(?:ഏത്\s*(?:മരുന്ന്|ഗുളിക)|മരുന്ന്\s*(?:നൽകണം|പറയൂ)|എത്ര\s*ഡോസ്|ചികിത്സ\s*പറയൂ|ഏത്\s*രോഗം)"),
    # Punjabi (pa-IN)
    re.compile(r"(?:ਕਿਹੜੀ\s*(?:ਦਵਾਈ|ਗੋਲੀ)|ਦਵਾਈ\s*(?:ਦੇਣੀ|ਦੱਸੋ)|ਕਿੰਨੀ\s*ਖੁਰਾਕ|ਇਲਾਜ\s*ਦੱਸੋ|ਕਿਹੜੀ\s*ਬਿਮਾਰੀ)"),
]

FORBIDDEN_OUTPUT_PATTERNS = [
    re.compile(
        r"\b(?:paracetamol|acetaminophen|ibuprofen|amoxicillin|azithromycin|cefixime|metronidazole|aspirin|ciprofloxacin)\b",
        re.I,
    ),
    re.compile(
        r"\b\d+\s*(?:mg|ml)\b\s*(?:twice|thrice|daily|every|subah|shaam|din\s+mein|give|take|dena|khilao)",
        re.I,
    ),
    re.compile(
        r"\b(?:take|give|administer)\s+\d+\s*(?:tablet|tablets|drops|ml|mg)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:patient\s+has|diagnosed\s+with|diagnosis\s+is)\s+(?:pneumonia|malaria|sepsis|preeclampsia|typhoid|dengue|anemia)\b",
        re.I,
    ),
]


@dataclass(frozen=True)
class GuardrailDecision:
    """Result of incoming safety guardrail inspection."""

    blocked: bool
    reason: Optional[str] = None
    refusal_text: Optional[str] = None
    is_prompt_injection: bool = False


class MedicalGuardrails:
    """Enforces non-diagnostic, non-prescriptive safety boundaries in all 10 languages."""

    def __init__(self, intro_messages: Optional[Dict[str, str]] = None) -> None:
        self._intro_messages = intro_messages or {}

    def get_intro_message(self, language: LanguageCode = "hi-en") -> str:
        """Return configurable AI assistant safety disclosure message."""
        return lang_get_intro_message(language, overrides=self._intro_messages)

    def get_refusal_message(self, language: LanguageCode = "hi-en") -> str:
        """Return polite medical refusal + doctor/PHC referral in worker's language."""
        return lang_get_refusal_message(language)

    def evaluate_input(
        self, transcript: str, language: LanguageCode = "hi-en"
    ) -> GuardrailDecision:
        """Inspect incoming ASHA transcript for medical advice requests or safety overrides."""
        text = " ".join(transcript.strip().split())
        if not text:
            return GuardrailDecision(blocked=False)

        for pat in INJECTION_PATTERNS:
            if pat.search(text):
                return GuardrailDecision(
                    blocked=True,
                    reason="safety_override_attempt",
                    refusal_text=self.get_refusal_message(language),
                    is_prompt_injection=True,
                )

        for pat in MEDICAL_ADVICE_REQUEST_PATTERNS:
            if pat.search(text):
                return GuardrailDecision(
                    blocked=True,
                    reason="medical_advice_or_treatment_request",
                    refusal_text=self.get_refusal_message(language),
                    is_prompt_injection=False,
                )

        return GuardrailDecision(blocked=False)

    def validate_output(
        self, reply_text: str, language: LanguageCode = "hi-en"
    ) -> str:
        """Ensure no outgoing reply accidentally diagnoses or prescribes medication/dosage."""
        for pat in FORBIDDEN_OUTPUT_PATTERNS:
            if pat.search(reply_text):
                return self.get_refusal_message(language)
        return reply_text
