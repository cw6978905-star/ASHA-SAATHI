"""Module 5: Two-layer Multilingual Danger-Sign Detection Engine (All 10 Gnani Languages)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from brain.languages import get_referral_message
from brain.llm_client import BaseLLMClient, LLMProviderError
from brain.normalizers import normalize_text
from brain.prompts import (
    DANGER_DETECTION_SYSTEM_PROMPT,
    build_danger_detection_user_prompt,
)
from models.visit_schema import DangerFlag, LanguageCode

logger = logging.getLogger("asha_saathi.danger")

# Re-export default referral dict for backwards compatibility with existing imports
FIXED_REFERRAL_MESSAGES: Dict[str, str] = {
    "hi-en": get_referral_message("hi-en"),
    "en": get_referral_message("en"),
    "hi": get_referral_message("hi"),
}

UNCERTAINTY_PATTERN = re.compile(
    r"(?:\b(?:shayad|shaayad|lag\s+raha|lag\s+rahi|lagta\s+hai|thoda|thodi|halka|halki|"
    r"maybe|might|possibly|seems|appears|slight|slightly|mild|pata\s+nahi\s+kya|doubt|unsure)\b|"
    r"शायद|लग\s+रहा|लग\s+रही|लगता\s+है|थोड़ा|हल्का|"
    r"ஒருவேளை|சிறிது|போல\s+தோன்றுகிறது|போல\s+இருக்கு|தெரியவில்லை|"
    r"బహుశా|కొంచెం|అనిపిస్తోంది|కావచ్చు|"
    r"সম্ভবত|মনে\s+হচ্ছে|হয়তো|হালকা|"
    r"कदाचित|वाटते|असू\s+शकतो|थोडंसं|"
    r"કદાચ|લાગે\s+છે|હોઈ\s+શકે|થોડું|"
    r"ಬಹುಶಃ|ಸ್ವಲ್ಪ|ಅನಿಸುತ್ತದೆ|ಇರಬಹುದು|"
    r"ഒരുപക്ഷേ|ചെറിയ|തോന്നുന്നു|ആയിരിക്കാം|"
    r"ਸ਼ਾਇਦ|ਲੱਗ\s+ਰਿਹਾ|ਲੱਗਦਾ\s+ਹੈ|ਹੋ\s+ਸਕਦਾ|ਥੋੜ੍ਹਾ)",
    re.IGNORECASE,
)

NEGATION_POST_PATTERN = re.compile(
    r"(?:\b(?:nahi\s+hai|nahi\s+ho\s+raha|nahi\s+ho\s+rahi|nahi\s+aaya|nahi\s+aa\s+raha|"
    r"nahi\s+aa\s+rahi|nahi\s+hua|nahi\s+hui|bilkul\s+nahi|absent|normal\s+hai|theek\s+hai|"
    r"illai|illa|ledu|kaadu|nai|naahi|nathi)\b|"
    r"नहीं\s+है|नहीं\s+हो\s+रहा|नहीं\s+हो\s+रही|नहीं\s+आया|"
    r"இல்லை|கிடையாது|లేదు|కాదు|নেই|নয়|না|नाही|नसते|નથી|ಇಲ್ಲ|അല്ല|ഇല്ല|ਨਹੀਂ)",
    re.IGNORECASE,
)

NEGATION_PRE_PATTERN = re.compile(
    r"\b(?:no|not|without|denied|denies|negative\s+for|koi)\s+$",
    re.IGNORECASE,
)


def _phonetic_normalize(text: str) -> str:
    """Normalize common transliteration spelling variations while keeping Indic scripts intact."""
    norm = normalize_text(text).lower()
    replacements = [
        (r"\bbukha+r\b", "bukhar"),
        (r"\bbhukhar\b", "bukhar"),
        (r"\btej\b", "tez"),
        (r"\bkhun\b", "khoon"),
        (r"\bsans\b", "saans"),
        (r"\bdudh\b", "doodh"),
        (r"\bsoojan\b", "sujan"),
        (r"\bpeeliya\b", "piliya"),
        (r"\bbeho+sh\b", "behosh"),
        (r"\bmavad\b", "mawad"),
        (r"\bme\b", "mein"),
        (r"\bpee\b", "pi"),
        (r"\bjada\b", "jyada"),
        (r"\bzyada\b", "jyada"),
    ]
    for pattern, repl in replacements:
        norm = re.sub(pattern, repl, norm)
    return norm


def _is_inherent_negative_phrase(phrase_lower: str) -> bool:
    """Phrases that denote danger specifically because of absence (e.g. 'not feeding', 'unconscious')."""
    inherent_markers = (
        "nahi", "not ", "no ", "unable", "refusing", "नहीं",
        "குடிக்கவில்லை", "இல்லை", "அசையவில்லை",
        "లేదు", "తాగడం లేదు", "లేకపోతోంది",
        "নেই", "খাচ্ছে না", "নড়ছে না",
        "नाही", "पीत नाही", "हलत नाही",
        "નથી", "પીતું નથી", "હલતું નથી",
        "ಇಲ್ಲ", "ಕುಡಿಯುತ್ತಿಲ್ಲ", "ಚಲಿಸುತ್ತಿಲ್ಲ",
        "ഇല്ല", "കുടിക്കുന്നില്ല", "അനങ്ങുന്നില്ല",
        "ਨਹੀਂ", "ਪੀ ਰਿਹਾ", "ਹਿੱਲ ਨਹੀਂ",
    )
    return any(tok in phrase_lower for tok in inherent_markers)


def _is_negated_in_clause(
    clause: str, match_start: int, match_end: int, matched_phrase: str
) -> Tuple[bool, bool]:
    """
    Determine whether a matched keyword in a clause is explicitly negated or ambiguous.

    Returns:
        (is_unambiguously_negated, is_ambiguous)
    """
    is_ambiguous = bool(UNCERTAINTY_PATTERN.search(clause))
    if is_ambiguous:
        return False, True

    if _is_inherent_negative_phrase(matched_phrase.lower()):
        return False, False

    pre_context = clause[max(0, match_start - 25) : match_start]
    post_context = clause[match_end : min(len(clause), match_end + 40)]

    if NEGATION_PRE_PATTERN.search(pre_context):
        return True, False
    if NEGATION_POST_PATTERN.search(post_context):
        return True, False

    return False, False


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def deterministic_contextual_danger_dict(
    transcript: str, catalog: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Deterministic contextual Layer-2 simulation for Mock mode."""
    norm = _phonetic_normalize(transcript)
    valid_ids = {item["id"] for item in catalog}
    matches: List[Dict[str, Any]] = []

    contextual_rules = [
        (
            "unconsciousness_lethargy",
            r"(?:respond\s+nahi\s+kar|aankh\s+nahi\s+khol|bilkul\s+dheela|activity\s+nahi|bejaan|not\s+responding|lethargic|"
            r"बच्चा\s+बिल्कुल\s+ढीला|प्रतिक्रिया\s+नहीं|कुझ\s+बोल\s+नहीं|"
            r"சுறுசுறுப்பாக\s+இல்லை|பதில்\s+கொடுக்கவில்லை|"
            r"బిడ్డ\s+కదలడం\s+లేదు|స్పందించడం\s+లేదు|"
            r"সাড়া\s+দিচ্ছে\s+না|একদম\s+নিস্তেজ|"
            r"प्रतिसाद\s+देत\s+नाही|अजिबात\s+हालचाल\s+नाही|"
            r"પ્રતિસાદ\s+આપતું\s+નથી|બિલકુલ\s+ઢીલું|"
            r"ಪ್ರತಿಕ್ರಿಯಿಸುತ್ತಿಲ್ಲ|ಚಲನೆಯೇ\s+ಇಲ್ಲ|"
            r"പ്രതികരിക്കുന്നില്ല|ഒട്ടും\s+അനങ്ങുന്നില്ല|"
            r"ਕੋਈ\s+ਜਵਾਬ\s+ਨਹੀਂ\s+ਦੇ\s+ਰਿਹਾ|ਬਿਲਕੁਲ\s+ਢਿੱਲਾ)",
            "Contextual expression indicates severe lethargy or unresponsiveness.",
        ),
        (
            "severe_headache_blurred_vision",
            r"(?:aankhon\s+ke\s+aage\s+(?:kaala|kala|andhera|chakkar)|dhundhla\s+nazar|haath\s+pair\s+(?:aur\s+)?chehra\s+sooj|"
            r"eyes\s+blurry|dark\s+spots\s+before\s+eyes|आंखों\s+के\s+आगे\s+अंधेरा|"
            r"கண்\s+முன்\s+இருட்டாக|பார்வை\s+மங்கலாக|కళ్ళ\s+ముందు\s+చీకటి|চোখে\s+অন্ধকার|"
            r"डोळ्यांसमोर\s+अंधारी|આંખો\s+સામે\s+અંધારું|ಕಣ್ಣುಗಳ\s+ಮುಂದೆ\s+ಕತ್ತಲೆ|കണ്ണിന്\s+മുന്നിൽ\s+ഇരുട്ട്|ਅੱਖਾਂ\s+ਅੱਗੇ\s+ਹਨੇਰਾ)",
            "Contextual expression suggests preeclampsia-like visual/headache/swelling symptoms.",
        ),
        (
            "reduced_fetal_movement",
            r"(?:pet\s+ke\s+andar\s+(?:harkat|movement)\s+(?:band|kam)|baby\s+(?:has\s+)?stopped\s+kicking|kicks\s+nahi|"
            r"not\s+kicking\s+much|कमी\s+हालचाल|அசைவு\s+குறைந்து|కదలికలు\s+తగ్గినట్లు|নড়াচড়া\s+কম\s+মনে|"
            r"हालचाल\s+कमी\s+वाटते|હલનચલન\s+ઓછું\s+લાગે|ಚಲನೆ\s+ಕಡಿಮೆಯಾಗಿದೆ|അനക്കം\s+കുറഞ്ഞതായി|ਹਲਚਲ\s+ਘੱਟ\s+ਲੱਗ)",
            "Contextual expression indicates reduced or absent fetal movement.",
        ),
        (
            "severe_bleeding",
            r"(?:kapda\s+khoon\s+se\s+bheeg|pad\s+bhar\s+khoon|laal\s+daag\s+aur\s+khoon|blood\s+soaking|"
            r"blood\s+stained\s+cloth|लाल\s+धब्बा|रक्त\s+थांबत\s+नाही)",
            "Contextual expression indicates vaginal or heavy bleeding.",
        ),
        (
            "high_fever",
            r"(?:bhatti\s+jaisa\s+tap|chhoone\s+par\s+bahut\s+garam|feel(?:s|ing)?\s+(?:very\s+|unusually\s+)?(?:hot|warm)|"
            r"10[1-6]\s*(?:°?\s*f|degree)|3[89]\.\d\s*°?\s*c|4[0-3](?:\.\d)?\s*°?\s*c|"
            r"शरीर\s+बहुत\s+तप|உடல்\s+சூடாக|శరీరం\s+వేడిగా|শরীর\s+গরম|शरीर\s+गरम|"
            r"શરીર\s+ગરમ|ದೇಹ\s+ಬಿಸಿಯಾಗಿದೆ|ശരീരം\s+ചൂടാണ്|ਸਰੀਰ\s+ਗਰਮ)",
            "Contextual or numeric temperature indicator points to high fever.",
        ),
        (
            "breathing_difficulty",
            r"(?:chhati\s+andar\s+dhas|ribs\s+pulling\s+in|pet\s+aur\s+chhati\s+tez\s+hil|struggling\s+for\s+air|"
            r"பக்கவாட்டு\s+எலும்பு|ఛాతీ\s+లోపలికి|বুক\s+ভেতরে\s+ঢুকে|छाती\s+आत\s+जाते|"
            r"છાતી\s+અંદર\s+ખેંચાય|ಎದೆ\s+ಒಳಕ್ಕೆ\s+ಹೋಗುತ್ತಿದೆ|നെഞ്ച്\s+ഉള്ളിലേക്ക്\s+വലിയുന്നു|ਛਾਤੀ\s+ਅੰਦਰ\s+ਧਸ)",
            "Contextual expression indicates respiratory distress or chest indrawing.",
        ),
        (
            "convulsions",
            r"(?:aankhein\s+palat\s+rahi|sharir\s+akad\s+gaya|daant\s+bheench|shaking\s+uncontrollably)",
            "Contextual expression describes convulsive episode.",
        ),
        (
            "poor_feeding_newborn",
            r"(?:maa\s+ka\s+doodh\s+(?:chhod|nahi\s+le)|muh\s+nahi\s+laga\s+raha|refusing\s+breast|sucking\s+weakly)",
            "Contextual expression indicates poor feeding in newborn.",
        ),
    ]

    clauses = re.split(r"[.;!?\n।॥]+", norm)
    for clause in clauses:
        if not clause.strip():
            continue
        is_ambig = bool(UNCERTAINTY_PATTERN.search(clause))
        for sign_id, pat, reason in contextual_rules:
            if sign_id not in valid_ids:
                continue
            m = re.search(pat, clause)
            if m:
                negated, ambig_flag = _is_negated_in_clause(
                    clause, m.start(), m.end(), m.group(0)
                )
                if not negated:
                    matches.append(
                        {
                            "danger_sign_id": sign_id,
                            "evidence": m.group(0),
                            "reason": reason,
                            "ambiguous": bool(is_ambig or ambig_flag),
                        }
                    )

    return {"danger_detected": len(matches) > 0, "matches": matches}


def _collect_entry_phrases(entry: Dict[str, Any]) -> List[str]:
    """Gather all configured phrases from legacy lists and multilingual phrase dictionary."""
    phrases: List[str] = []
    phrases.extend(entry.get("english_keywords", []))
    phrases.extend(entry.get("hindi_phrases", []))
    phrases.extend(entry.get("regional_phrases", []))

    ml_dict = entry.get("multilingual_phrases") or {}
    if isinstance(ml_dict, dict):
        native_map = ml_dict.get("native_script") or {}
        if isinstance(native_map, dict):
            for lang_phrases in native_map.values():
                if isinstance(lang_phrases, list):
                    phrases.extend(lang_phrases)
        for list_key in ("transliterations", "code_mixed", "spelling_variations"):
            vals = ml_dict.get(list_key) or []
            if isinstance(vals, list):
                phrases.extend(vals)
    # Deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for p in phrases:
        if isinstance(p, str) and p.strip() and p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


class DangerDetector:
    """
    Two-layer multilingual danger-sign detector using OR logic:
    danger_detected = rule_based_detected OR llm_detected.
    """

    def __init__(
        self,
        danger_signs_path: Path,
        llm_client: BaseLLMClient,
    ) -> None:
        self._path = Path(danger_signs_path)
        self._llm = llm_client
        self._metadata: Dict[str, Any] = {}
        self._catalog: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        """Load configurable multilingual danger-sign definitions from JSON."""
        with self._path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        self._metadata = raw.get("metadata", {})
        self._catalog = raw.get("danger_signs", [])
        self._by_id = {entry["id"]: entry for entry in self._catalog if "id" in entry}
        logger.info(
            "Loaded %d danger signs (verification_status=%s)",
            len(self._catalog),
            self._metadata.get("verification_status", "unknown"),
        )

    @property
    def metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)

    @property
    def catalog(self) -> List[Dict[str, Any]]:
        return list(self._catalog)

    def get_referral_message(self, language: LanguageCode = "hi-en") -> str:
        """Return the fixed PHC referral template in the worker's selected language."""
        default_map = self._metadata.get("default_referral_messages", {})
        if language in default_map:
            return str(default_map[language])
        return get_referral_message(language)

    def detect_rule_based(
        self,
        transcript: str,
        language: LanguageCode = "hi-en",
    ) -> Dict[str, DangerFlag]:
        """Layer 1: Deterministic rule-based matching across all 10 languages."""
        norm_transcript = _phonetic_normalize(transcript)
        if not norm_transcript:
            return {}

        clauses = [
            c.strip()
            for c in re.split(
                r"(?<!\d)[.,;!\?\n।॥]+|[.,;!\?\n।॥]+(?!\d)|"
                r"\b(?:lekin|but|par|aur|and)\b|लेकिन|और|மற்றும்|ஆனால்|మరియు|కానీ|এবং|কিন্তু|आणि|पण|અને|પરંતુ|ಮತ್ತು|ಆದರೆ|ഉം|പക്ഷേ|ਅਤੇ|ਪਰ",
                norm_transcript,
            )
            if c.strip()
        ]
        flags: Dict[str, DangerFlag] = {}

        for entry in self._catalog:
            sign_id = entry["id"]
            phrases = _collect_entry_phrases(entry)
            phrases.sort(key=len, reverse=True)

            matched_evidence: List[str] = []
            any_ambiguous = False

            for clause in clauses:
                for raw_phrase in phrases:
                    norm_phrase = _phonetic_normalize(raw_phrase)
                    if not norm_phrase:
                        continue
                    is_ascii = all(ord(ch) < 128 for ch in norm_phrase)
                    if is_ascii:
                        pat = re.compile(rf"\b{re.escape(norm_phrase)}\b")
                    else:
                        pat = re.compile(re.escape(norm_phrase))

                    m = pat.search(clause)
                    if not m:
                        continue

                    negated, ambiguous = _is_negated_in_clause(
                        clause, m.start(), m.end(), norm_phrase
                    )
                    if negated:
                        continue

                    if ambiguous:
                        any_ambiguous = True
                    if raw_phrase not in matched_evidence:
                        matched_evidence.append(raw_phrase)
                    break

            if sign_id == "high_fever" and not matched_evidence:
                f_match = re.search(
                    r"\b(100\.[4-9]|10[1-6](?:\.\d)?)\s*(?:°?\s*f|fahrenheit|fever)\b",
                    norm_transcript,
                )
                c_match = re.search(
                    r"\b(3[89](?:\.\d)?|4[0-3](?:\.\d)?)\s*(?:°?\s*c|celsius)\b",
                    norm_transcript,
                )
                if f_match or c_match:
                    matched_evidence.append((f_match or c_match).group(0))  # type: ignore[union-attr]

            if matched_evidence:
                referral = self.get_referral_message(language)
                if language == "hi-en" and entry.get("referral_message"):
                    referral = entry["referral_message"]
                flags[sign_id] = DangerFlag(
                    danger_sign_id=sign_id,
                    category=entry.get("category", "general"),
                    english_name=entry.get("english_name", sign_id),
                    matched_layers=["rule_based"],
                    matched_evidence=matched_evidence,
                    ambiguous=any_ambiguous,
                    referral_message=referral,
                    source_reference=entry.get(
                        "source_reference", "PENDING_PERSON_C_VERIFICATION"
                    ),
                )

        return flags

    def detect_llm_based(
        self,
        transcript: str,
        language: LanguageCode = "hi-en",
    ) -> Dict[str, DangerFlag]:
        """Layer 2: Contextual LLM screening against predefined danger signs."""
        if not transcript.strip():
            return {}

        user_prompt = build_danger_detection_user_prompt(transcript, self._catalog)
        try:
            raw = self._llm.complete_json(
                system_prompt=DANGER_DETECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                task="danger_detection",
                metadata={"transcript": transcript, "catalog": self._catalog},
            )
            parsed = json.loads(_extract_json_object(raw))
        except (LLMProviderError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Layer 2 LLM danger detection failed safely: %s", exc)
            return {}

        flags: Dict[str, DangerFlag] = {}
        matches = parsed.get("matches") if isinstance(parsed, dict) else None
        if not isinstance(matches, list):
            return {}

        for item in matches:
            if not isinstance(item, dict):
                continue
            sign_id = item.get("danger_sign_id")
            if not isinstance(sign_id, str) or sign_id not in self._by_id:
                continue
            entry = self._by_id[sign_id]
            evidence_val = str(item.get("evidence") or "").strip()
            reason_val = str(item.get("reason") or "").strip() or None
            ambig = bool(item.get("ambiguous", False))
            referral = self.get_referral_message(language)
            if language == "hi-en" and entry.get("referral_message"):
                referral = entry["referral_message"]

            flags[sign_id] = DangerFlag(
                danger_sign_id=sign_id,
                category=entry.get("category", "general"),
                english_name=entry.get("english_name", sign_id),
                matched_layers=["llm"],
                matched_evidence=[evidence_val] if evidence_val else [],
                llm_reason=reason_val,
                ambiguous=ambig,
                referral_message=referral,
                source_reference=entry.get(
                    "source_reference", "PENDING_PERSON_C_VERIFICATION"
                ),
            )
        return flags

    def detect(
        self,
        transcript: str,
        language: LanguageCode = "hi-en",
    ) -> Tuple[bool, List[DangerFlag]]:
        """
        Combine Layer 1 (rule-based) and Layer 2 (LLM-based) using OR logic.

        Layer 2 can NEVER cancel or override a positive Layer 1 detection.
        """
        rule_flags = self.detect_rule_based(transcript, language=language)
        llm_flags = self.detect_llm_based(transcript, language=language)

        merged: Dict[str, DangerFlag] = {}
        for sign_id, flag in rule_flags.items():
            merged[sign_id] = flag.model_copy(deep=True)

        for sign_id, lflag in llm_flags.items():
            if sign_id in merged:
                existing = merged[sign_id]
                if "llm" not in existing.matched_layers:
                    existing.matched_layers.append("llm")
                for ev in lflag.matched_evidence:
                    if ev and ev not in existing.matched_evidence:
                        existing.matched_evidence.append(ev)
                if lflag.llm_reason:
                    existing.llm_reason = lflag.llm_reason
                existing.ambiguous = existing.ambiguous or lflag.ambiguous
            else:
                merged[sign_id] = lflag

        flag_list = list(merged.values())
        return (len(flag_list) > 0), flag_list
