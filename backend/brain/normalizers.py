"""Multilingual Hindi/English/Indic normalization helpers for numbers, IDs, BP, and dates across 10 Gnani languages."""

from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from brain.multilingual_numbers import (
    MULTILINGUAL_MONTH_MAP,
    MULTILINGUAL_NUMBER_WORDS,
    resolve_single_indic_compound_word,
)
from models.visit_schema import BloodPressure

# All 10 supported Indian script digit blocks -> ASCII 0-9
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
INDIC_DIGITS = str.maketrans(
    "०१२३४५६७८९"
    "০১২৩৪৫৬৭৮৯"
    "૦૧૨૩૪૫૬૭૮૯"
    "੦੧੨੩੪੫੬੭੮੯"
    "௦௧௨௩௪௫௬௭௮௯"
    "౦౧౨౩౪౫౬౭౮౯"
    "೦೧೨೩೪೫೬೭೮೯"
    "൦൧൨൩൪൫൬൭൮൯",
    "0123456789" * 8,
)

DECIMAL_MARKER_WORDS = {
    "point",
    "dot",
    "dashamlav",
    "पॉइंट",
    "पॉइन्ट",
    "दशमलव",
    "दशांश",
    "पॉईंट",
    "புள்ளி",
    "பாயிண்ட்",
    "పాయింట్",
    "দশমিক",
    "পয়েন্ট",
    "পয়েন্ট",
    "પોઇન્ટ",
    "પોઈન્ટ",
    "ಪಾಯಿಂಟ್",
    "ದಶಾಂಶ",
    "പോയിന്റ്",
    "പോയിൻറ്",
    "ਦਸ਼ਮਲਵ",
    "ਪੁਆਇੰਟ",
}

CONJUNCTION_WORDS = {
    "and",
    "aur",
    "और",
    "மற்றும்",
    "మరియు",
    "এবং",
    "आणि",
    "અને",
    "ಮತ್ತು",
    "ഉം",
    "ਅਤੇ",
}

NUMBER_WORDS: Dict[str, int] = dict(MULTILINGUAL_NUMBER_WORDS)

HALF_WORDS = {"aadha", "adha", "half", "आधा", "अर्धा", "அரை", "అర", "আধা", "અડધો", "ಅರ್ಧ", "അര", "ਅੱਧਾ"}
ONE_AND_HALF_WORDS = {"dedh", "derh", "डेढ़", "दीड", "ஒன்றரை", "ఒకటిన్నర", "দেড়", "દોઢ", "ಒಂದೂವರೆ", "ഒന്നര", "ਡੇਢ"}
TWO_AND_HALF_WORDS = {"dhai", "dhayi", "ढाई", "अडीच", "இரண்டரை", "రెండున్నర", "আড়াই", "અઢી", "ಎರಡೂವರೆ", "രണ്ടര", "ਢਾਈ"}
SAADE_PREFIXES = {"saade", "sadhe", "sade", "साढ़े", "साडे", "ಸಾಡೆ"}

SINGLE_DIGIT_WORDS: Dict[str, str] = {
    "0": "0", "zero": "0", "shunya": "0", "sunya": "0", "oh": "0",
    "शून्य": "0", "பூஜ்ஜியம்": "0", "సున్నా": "0", "শূন্য": "0", "શૂન્ય": "0", "ಸೊನ್ನೆ": "0", "പൂജ്യം": "0", "ਸਿਫ਼ਰ": "0",
    "1": "1", "one": "1", "ek": "1", "ik": "1", "onnu": "1", "ondru": "1", "okati": "1", "ondu": "1", "ikk": "1",
    "एक": "1", "ஒன்று": "1", "ఒకటి": "1", "এক": "1", "એક": "1", "ಒಂದು": "1", "ഒന്ന്": "1", "ਇੱਕ": "1", "ਇਕ": "1",
    "2": "2", "two": "2", "do": "2", "rendu": "2", "irandu": "2", "dui": "2", "don": "2", "be": "2", "eradu": "2", "randu": "2",
    "दो": "2", "இரண்டு": "2", "రెండు": "2", "দুই": "2", "दोन": "2", "બે": "2", "ಎರಡು": "2", "രണ്ട്": "2", "ਦੋ": "2",
    "3": "3", "three": "3", "teen": "3", "tin": "3", "moonu": "3", "moondru": "3", "moodu": "3", "tran": "3", "mooru": "3", "moonnu": "3", "tinn": "3",
    "तीन": "3", "மூன்று": "3", "మూడు": "3", "তিন": "3", "ત્રણ": "3", "ಮೂರು": "3", "മൂന്ന്": "3", "ਤਿੰਨ": "3",
    "4": "4", "four": "4", "char": "4", "chaar": "4", "naalu": "4", "naangu": "4", "naalugu": "4", "naalku": "4",
    "चार": "4", "நான்கு": "4", "నాలుగు": "4", "চার": "4", "ચાર": "4", "ನಾಲ್ಕು": "4", "നാല്": "4", "ਚਾਰ": "4",
    "5": "5", "five": "5", "paanch": "5", "panch": "5", "anju": "5", "aindhu": "5", "aidu": "5", "paach": "5", "panj": "5",
    "पांच": "5", "पाँच": "5", "ஐந்து": "5", "ఐదు": "5", "পাঁচ": "5", "पाच": "5", "પાંચ": "5", "ಐದು": "5", "അഞ്ച്": "5", "ਪੰਜ": "5",
    "6": "6", "six": "6", "chhah": "6", "chhe": "6", "che": "6", "aaru": "6", "chhoy": "6", "saha": "6", "chha": "6",
    "छह": "6", "छः": "6", "ஆறு": "6", "ఆరు": "6", "ছয়": "6", "सहा": "6", "છ": "6", "ಆರು": "6", "ആറ്": "6", "ਛੇ": "6",
    "7": "7", "seven": "7", "saat": "7", "sat": "7", "ezhu": "7", "edu": "7", "elu": "7", "satt": "7",
    "सात": "7", "ஏழு": "7", "ఏడు": "7", "সাত": "7", "સાત": "7", "ಏಳು": "7", "ഏഴ്": "7", "ਸੱਤ": "7",
    "8": "8", "eight": "8", "aath": "8", "ath": "8", "ettu": "8", "enimidi": "8", "aat": "8", "entu": "8", "atth": "8",
    "आठ": "8", "எட்டு": "8", "ఎనిమిది": "8", "আট": "8", "આઠ": "8", "ಎಂಟು": "8", "എട്ട്": "8", "ਅੱਠ": "8",
    "9": "9", "nine": "9", "nau": "9", "ombadhu": "9", "tommidi": "9", "noy": "9", "nav": "9", "ombattu": "9", "ombathu": "9",
    "नौ": "9", "ஒன்பது": "9", "తొమ్మిది": "9", "নয়": "9", "नऊ": "9", "નવ": "9", "ಒಂಬತ್ತು": "9", "ഒൻപത്": "9", "ਨੌਂ": "9",
}

KG_UNIT_WORDS = [
    "kilograms", "kilogram", "kilos", "kilo", "kgs", "kg",
    "किलोग्राम", "किलो", "किग्रा",
    "கிலோகிராம்", "கிலோ",
    "కిలోగ్రాములు", "కిలోగ్రామ్", "కిలోలు", "కిలో",
    "কিলোগ্রাম", "কিলো", "কেজি",
    "किलोग्रॅम",
    "કિલોગ્રામ", "કિલો",
    "ಕಿಲೋಗ್ರಾಂ", "ಕಿಲೋ", "ಕೆಜಿ",
    "കിലോഗ്രാം", "കിലോ",
    "ਕਿਲੋਗ੍ਰਾਮ", "ਕਿੱਲੋ", "ਕਿਲੋ",
]

GRAM_UNIT_WORDS = [
    "grams", "gram", "gms", "gm",
    "ग्राम", "ग्रॅम", "கிராம்", "గ్రాములు", "గ్రాము", "গ্রাম", "ગ્રામ", "ಗ್ರಾಂ", "ഗ്രാം", "ਗ੍ਰਾਮ",
]

WEEKDAY_MAP: Dict[str, int] = {
    # English & Hindi/Marathi (base + inflected forms)
    "monday": 0, "mon": 0, "somvar": 0, "somvaar": 0, "सोमवार": 0, "सोमवारी": 0,
    "tuesday": 1, "tue": 1, "tues": 1, "mangalvar": 1, "mangalwaar": 1, "मंगलवार": 1, "मंगळवार": 1, "मंगळवारी": 1,
    "wednesday": 2, "wed": 2, "budhvar": 2, "budhwaar": 2, "बुधवार": 2, "बुधवारी": 2,
    "thursday": 3, "thu": 3, "thurs": 3, "guruvar": 3, "guruvaar": 3, "brihaspativar": 3, "veervar": 3, "गुरुवार": 3, "गुरूवार": 3, "गुरुवारी": 3, "बृहस्पतिवार": 3,
    "friday": 4, "fri": 4, "shukravar": 4, "shukravaar": 4, "शुक्रवार": 4, "शुक्रवारी": 4,
    "saturday": 5, "sat": 5, "shanivar": 5, "shanivaar": 5, "शनिवार": 5, "शनिवारी": 5,
    "sunday": 6, "sun": 6, "ravivar": 6, "ravivaar": 6, "itvar": 6, "itvaar": 6, "रविवार": 6, "रविवारी": 6,
    # Tamil
    "திங்கள்": 0, "திங்கட்கிழமை": 0, "செவ்வாய்": 1, "செவ்வாய்க்கிழமை": 1, "செவ்வாயன்று": 1,
    "புதன்": 2, "புதன்கிழமை": 2, "வியாழன்": 3, "வியாழக்கிழமை": 3,
    "வெள்ளி": 4, "வெள்ளிக்கிழமை": 4, "சனி": 5, "சனிக்கிழமை": 5, "ஞாயிறு": 6, "ஞாயிற்றுக்கிழமை": 6,
    # Telugu
    "సోమవారం": 0, "మంగళవారం": 1, "బుధవారం": 2, "గురువారం": 3, "శుక్రవారం": 4, "శనివారం": 5, "ఆదివారం": 6,
    # Bengali
    "সোমবার": 0, "সোমবাৰে": 0, "মঙ্গলবার": 1, "মঙ্গলবারে": 1, "বুধবার": 2, "বৃহস্পতিবার": 3, "শুক্রবার": 4, "শনিবার": 5, "রবিবার": 6,
    # Gujarati
    "સોમવાર": 0, "સોમવારે": 0, "મંગળવાર": 1, "મંગળવારે": 1, "બુધવાર": 2, "ગુરુવાર": 3, "શુક્રવાર": 4, "શનિવાર": 5, "રવિવાર": 6,
    # Kannada
    "ಸೋಮವಾರ": 0, "ಮಂಗಳವಾರ": 1, "ಬುಧವಾರ": 2, "ಗುರುವಾರ": 3, "ಶುಕ್ರವಾರ": 4, "ಶನಿವಾರ": 5, "ಭಾನುವಾರ": 6,
    # Malayalam
    "തിങ്കൾ": 0, "തിങ്കളാഴ്ച": 0, "ചൊവ്വ": 1, "ചൊവ്വാഴ്ച": 1, "ബുധൻ": 2, "ബുധനാഴ്ച": 2,
    "വ്യാഴം": 3, "വ്യാഴാഴ്ച": 3, "വെള്ളി": 4, "വെള്ളിയാഴ്ച": 4, "ശനി": 5, "ശനിയാഴ്ച": 5, "ഞായർ": 6, "ഞായറാഴ്ച": 6,
    # Punjabi
    "ਸੋਮਵਾਰ": 0, "ਮੰਗਲਵਾਰ": 1, "ਬੁੱਧਵਾਰ": 2, "ਵੀਰਵਾਰ": 3, "ਸ਼ੁੱਕਰਵਾਰ": 4, "ਸ਼ਨੀਵਾਰ": 5, "ਐਤਵਾਰ": 6,
}

MONTH_MAP: Dict[str, int] = dict(MULTILINGUAL_MONTH_MAP)


def normalize_text(text: str) -> str:
    """Normalize all 10 Indic script digits, Unicode NFKC, and whitespace."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", text).translate(INDIC_DIGITS)
    return " ".join(norm.strip().split())


def tokenize_unicode_words(text: str) -> List[str]:
    """Split text into clean word tokens preserving Indic vowel signs/matras."""
    raw_tokens = text.split()
    cleaned: List[str] = []
    for tok in raw_tokens:
        stripped = tok.strip(".,;:!?()[]{}'\"|।॥")
        if stripped:
            cleaned.append(stripped)
    return cleaned


def today_in_timezone(tz_name: str = "Asia/Kolkata") -> date:
    """Return current date in configured timezone."""
    return datetime.now(ZoneInfo(tz_name)).date()


def parse_number_tokens(tokens: List[str]) -> Optional[float]:
    """Parse spoken English/Hindi/Indic numeric tokens into float."""
    if not tokens:
        return None

    lowered = [t.lower() for t in tokens]
    joined = " ".join(lowered).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", joined):
        return float(joined)

    # Decimal marker split across all 10 languages
    for marker_idx, tok in enumerate(lowered):
        if tok in DECIMAL_MARKER_WORDS and 0 < marker_idx < len(lowered) - 1:
            lhs = parse_number_tokens(lowered[:marker_idx])
            rhs_tokens = lowered[marker_idx + 1 :]
            if lhs is None or not rhs_tokens:
                return None
            if len(rhs_tokens) == 1 and re.fullmatch(r"\d+", rhs_tokens[0]):
                return float(f"{int(lhs)}.{rhs_tokens[0]}")
            digits: List[str] = []
            for rtok in rhs_tokens:
                if rtok in SINGLE_DIGIT_WORDS:
                    digits.append(SINGLE_DIGIT_WORDS[rtok])
                elif rtok in NUMBER_WORDS and len(rhs_tokens) == 1:
                    digits.append(str(NUMBER_WORDS[rtok]))
                else:
                    return None
            if digits:
                return float(f"{int(lhs)}.{''.join(digits)}")

    if joined in HALF_WORDS:
        return 0.5
    if joined in ONE_AND_HALF_WORDS:
        return 1.5
    if joined in TWO_AND_HALF_WORDS:
        return 2.5
    if joined in {"sawa", "sava"}:
        return 1.25

    if lowered[0] in SAADE_PREFIXES and len(lowered) >= 2:
        base = parse_number_tokens(lowered[1:])
        return (base + 0.5) if base is not None else None
    if lowered[0] in {"sawa", "sava"} and len(lowered) >= 2:
        base = parse_number_tokens(lowered[1:])
        return (base + 0.25) if base is not None else None
    if lowered[0] in {"paune", "pone"} and len(lowered) >= 2:
        base = parse_number_tokens(lowered[1:])
        return (base - 0.25) if base is not None else None

    total = 0
    current = 0
    matched_any = False
    for tok in lowered:
        if tok in CONJUNCTION_WORDS:
            continue
        if re.fullmatch(r"\d+", tok):
            num_v = int(tok)
            if current > 0 and current < 10 and num_v < 10:
                return None  # Ambiguous consecutive digits (e.g. "ek 2"), do not guess
            current += num_v
            matched_any = True
            continue

        resolved_v = resolve_single_indic_compound_word(tok)
        if resolved_v is not None:
            matched_any = True
            if resolved_v == 100:
                # Multiplier + hundred word ("do sau", "two hundred", "రెండు వందల", "ਦੋ ਸੌ")
                if current >= 100:
                    return None
                total += (current or 1) * 100
                current = 0
            elif resolved_v in {200, 300, 400, 500, 600, 700, 800, 900}:
                if current > 0:
                    return None
                total += resolved_v
                current = 0
            elif 1 <= resolved_v <= 9 and 0 < current < 10:
                # Never merge two consecutive single digits ("do teen", "five two")
                return None
            elif 10 <= resolved_v <= 99 and 0 < current < 100:
                # Never merge two unrelated tens/teens ("bees tees")
                return None
            else:
                current += resolved_v
        else:
            return None
    total += current
    return float(total) if matched_any else None


def _is_numeric_token(tok: str) -> bool:
    low = tok.lower()
    return bool(
        re.fullmatch(r"\d+(?:\.\d+)?", low)
        or resolve_single_indic_compound_word(low) is not None
        or low in DECIMAL_MARKER_WORDS
        or low in HALF_WORDS
        or low in ONE_AND_HALF_WORDS
        or low in TWO_AND_HALF_WORDS
        or low in SAADE_PREFIXES
        or low in {"sawa", "sava", "paune", "pone"}
        or low in CONJUNCTION_WORDS
    )


def _tail_number_tokens(segment: str) -> List[str]:
    tokens = tokenize_unicode_words(segment)
    kept: List[str] = []
    for tok in reversed(tokens):
        if _is_numeric_token(tok):
            kept.append(tok)
        else:
            break
    kept.reverse()
    while kept and kept[0].lower() in CONJUNCTION_WORDS:
        kept.pop(0)
    return kept


def _head_number_tokens(segment: str) -> List[str]:
    tokens = tokenize_unicode_words(segment)
    kept: List[str] = []
    for tok in tokens:
        if _is_numeric_token(tok):
            kept.append(tok)
        else:
            break
    while kept and kept[-1].lower() in CONJUNCTION_WORDS:
        kept.pop()
    return kept


def _unit_regex(units: List[str]) -> str:
    sorted_u = sorted(units, key=len, reverse=True)
    # Use whitespace/punctuation boundaries so Indic combining marks match accurately
    return r"(?:(?<=^)|(?<=[\s\d.,;:()\-]))(" + "|".join(re.escape(u) for u in sorted_u) + r")(?=$|[\s.,;!?()\-।॥])"


KG_REGEX = re.compile(_unit_regex(KG_UNIT_WORDS), re.IGNORECASE)
GRAM_REGEX = re.compile(_unit_regex(GRAM_UNIT_WORDS), re.IGNORECASE)


def parse_spoken_weight_kg(text: str) -> Optional[float]:
    """Extract weight in kilograms from any of the 10 supported Indian languages or English."""
    cleaned = normalize_text(text)
    if not cleaned:
        return None

    # 1. Check kg + gram combination (e.g. "do kilo aath sau gram", "2 kg 500 gm", "3 கிலோ 200 கிராம்")
    kg_matches = list(KG_REGEX.finditer(cleaned))
    gram_matches = list(GRAM_REGEX.finditer(cleaned))

    if kg_matches and gram_matches:
        kg_m = kg_matches[0]
        gm_m = next((g for g in gram_matches if g.start() > kg_m.end()), None)
        if gm_m:
            kg_tokens = _tail_number_tokens(cleaned[: kg_m.start()])
            gm_tokens = _tail_number_tokens(cleaned[kg_m.end() : gm_m.start()])
            kg_val = parse_number_tokens(kg_tokens)
            gm_val = parse_number_tokens(gm_tokens)
            if kg_val is not None and gm_val is not None and 0 <= gm_val < 1000:
                total_kg = round(kg_val + gm_val / 1000.0, 2)
                if 0.2 < total_kg <= 200.0:
                    return total_kg

    # 2. Standalone kg match ("do point aath kilo", "இரண்டு புள்ளி எட்டு கிலோ", "55 kg")
    for kg_m in kg_matches:
        tokens = _tail_number_tokens(cleaned[: kg_m.start()])
        val = parse_number_tokens(tokens)
        if val is not None and 0.2 < val <= 200.0:
            return round(val, 2)

    # 3. Standalone gram match ("aath sau gram", "800 gram")
    for gm_m in gram_matches:
        tokens = _tail_number_tokens(cleaned[: gm_m.start()])
        val = parse_number_tokens(tokens)
        if val is not None and 200 <= val <= 20000:
            return round(val / 1000.0, 2)

    # 4. Weight keyword without unit across all 10 languages
    wt_keywords = (
        r"(?:weight|vajan|wajan|वजन|எடை|బరువు|ওজন|वजन|વજન|ತೂಕ|ഭാരം|ਵਜ਼ਨ)"
        r"\s*(?:is|hai|आहे|ఉంది|আছে|છે|ಇದೆ|ആണ്|ਹੈ|:|=|ab)?\s*([^\n.;,!?।॥]+)"
    )
    m = re.search(wt_keywords, cleaned, re.IGNORECASE)
    if m:
        head_tokens = _head_number_tokens(m.group(1))
        val = parse_number_tokens(head_tokens)
        if val is not None and 0.2 < val <= 200.0:
            return round(val, 2)

    return None


def parse_blood_pressure(text: str) -> Optional[BloodPressure]:
    """Parse blood pressure readings across all 10 languages."""
    cleaned = normalize_text(text)
    if not cleaned:
        return None

    bp_label = (
        r"(?:bp|blood\s*pressure|raktchap|रक्तचाप|रक्तदाब|"
        r"இரத்த\s+அழுத்தம்|రక్తపోటు|রক্তচাপ|બ્લડ\s+પ્રેશર|ರಕ್ತದೊತ್ತಡ|രക്തസമ്മർദ്ദം|ਬਲੱਡ\s+ਪ੍ਰੈਸ਼ਰ)"
    )

    slash_match = re.search(
        rf"(?:{bp_label})?\s*(?:is|hai|आहे|ఉంది|আছে|છે|ಇದೆ|ആണ്|ਹੈ|:|=)?\s*"
        r"(\d{2,3})\s*(?:/|by|over|aur|और)\s*(\d{2,3})",
        cleaned,
        re.IGNORECASE,
    )
    if slash_match:
        sys_val = int(slash_match.group(1))
        dia_val = int(slash_match.group(2))
        if 50 <= sys_val <= 260 and 30 <= dia_val <= 160 and sys_val > dia_val:
            return BloodPressure(
                systolic=sys_val,
                diastolic=dia_val,
                raw_text=slash_match.group(0).strip(),
            )

    if re.search(bp_label, cleaned, re.IGNORECASE):
        spoken = re.search(
            rf"{bp_label}\s*(?:is|hai|:|=)?\s*([^\n.;,!?]+?)\s+(?:by|over|/)\s+([^\n.;,!?]+)",
            cleaned,
            re.IGNORECASE,
        )
        if spoken:
            sys_num = parse_number_tokens(_tail_number_tokens(spoken.group(1)))
            dia_num = parse_number_tokens(_head_number_tokens(spoken.group(2)))
            if (
                sys_num is not None
                and dia_num is not None
                and 50 <= sys_num <= 260
                and 30 <= dia_num <= 160
                and sys_num > dia_num
            ):
                return BloodPressure(
                    systolic=int(sys_num),
                    diastolic=int(dia_num),
                    raw_text=spoken.group(0).strip(),
                )
    return None


def parse_beneficiary_id(text: str, expect_id: bool = False) -> Optional[str]:
    """Parse alphanumeric or digit-by-digit beneficiary IDs spoken in any supported language."""
    cleaned = normalize_text(text)
    if not cleaned:
        return None

    id_labels = (
        r"(?:beneficiary\s*id|patient\s*id|id|"
        r"आईडी|लाभार्थी\s*आईडी|பயனாளி\s*ஐடி|ஐடி|లబ్ధిదారు\s*ఐడి|ఐడి|"
        r"আইডি|आयडी|આઈડી|ಐಡಿ|ഐഡി|ਆਈਡੀ)"
    )
    id_clause_pattern = re.compile(
        rf"{id_labels}\s*(?:number|no\.?|क्रमांक|எண்|సంఖ్య|নম্বর|નંબર|ಸಂಖ್ಯೆ|നമ്പർ|ਨੰਬਰ)?\s*"
        r"(?:is|hai|आहे|ఉంది|আছে|છે|ಇದೆ|ആണ്|ਹੈ|:|=|galat\s*hai[,\s]*)?\s*"
        r"([^\n.,;?!।॥]{1,60})",
        re.IGNORECASE,
    )
    match = id_clause_pattern.search(cleaned)
    candidate_phrase: Optional[str] = None
    if match:
        candidate_phrase = match.group(1).strip()
    elif expect_id:
        candidate_phrase = cleaned.strip()
    else:
        compact = re.search(r"\b([A-Za-z]{1,4}-?\d{2,6})\b", cleaned)
        if compact:
            return _format_id_token(compact.group(1))

    if not candidate_phrase:
        return None

    candidate_phrase = re.split(
        r"[.,;?!।॥]|\b(?:hai|hain|h|kar\s+do|please|aur|weight|next|visit)\b|"
        r"(?:आहे|हैं|है|உள்ளது|ఉంది|আছে|છે|ಇದೆ|ആണ്|ਹੈ)",
        candidate_phrase,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    direct = re.fullmatch(r"([A-Za-z]{1,4})\s*[-–—]?\s*(\d{2,8})", candidate_phrase)
    if direct:
        return f"{direct.group(1).upper()}-{direct.group(2)}"

    pure_digits = re.fullmatch(r"\d{3,10}", candidate_phrase.replace(" ", ""))
    if pure_digits:
        return pure_digits.group(0)

    tokens = tokenize_unicode_words(candidate_phrase)
    if not tokens:
        return None

    prefix_letters: List[str] = []
    digits: List[str] = []
    seen_digit = False
    for tok in tokens:
        low = tok.lower()
        if low in {"dash", "hyphen"}:
            continue
        if low in SINGLE_DIGIT_WORDS:
            digits.append(SINGLE_DIGIT_WORDS[low])
            seen_digit = True
        elif re.fullmatch(r"\d+", low):
            digits.append(low)
            seen_digit = True
        elif not seen_digit and re.fullmatch(r"[a-z]{1,4}", low) and low not in {
            "is", "the", "number", "no", "nahi",
        }:
            prefix_letters.append(tok.upper())
        else:
            break

    digit_str = "".join(digits)
    if prefix_letters and len(digit_str) >= 2:
        return f"{''.join(prefix_letters)}-{digit_str}"
    if len(digit_str) >= 3:
        return digit_str
    return None


def _format_id_token(token: str) -> str:
    m = re.fullmatch(r"([A-Za-z]{1,4})-?(\d{2,8})", token.strip())
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return token.strip().upper()


def _add_months(base_date: date, months: int) -> date:
    month_idx = base_date.month - 1 + months
    year = base_date.year + month_idx // 12
    month = month_idx % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def resolve_relative_date(
    text: str,
    anchor_date: Optional[date] = None,
    tz_name: str = "Asia/Kolkata",
) -> Tuple[Optional[date], Optional[str], Optional[str]]:
    """
    Resolve explicit or relative follow-up dates across all 10 languages in Asia/Kolkata.

    Never invents a date when the reference is ambiguous.
    """
    anchor = anchor_date or today_in_timezone(tz_name)
    cleaned = normalize_text(text)
    lower = cleaned.lower()

    # 1. Explicit ISO date
    iso_m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", lower)
    if iso_m:
        try:
            d = date(int(iso_m.group(1)), int(iso_m.group(2)), int(iso_m.group(3)))
            return d, iso_m.group(0), None
        except ValueError:
            return None, iso_m.group(0), iso_m.group(0)

    # 2. DD/MM/YYYY
    dmy_m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", lower)
    if dmy_m:
        day_i, mon_i, yr_i = int(dmy_m.group(1)), int(dmy_m.group(2)), int(dmy_m.group(3))
        if yr_i < 100:
            yr_i += 2000
        try:
            return date(yr_i, mon_i, day_i), dmy_m.group(0), None
        except ValueError:
            return None, dmy_m.group(0), dmy_m.group(0)

    # 3. Multilingual Month-Day patterns (supports numeric and spoken day + all 10 language month names)
    sorted_months = sorted(MONTH_MAP.keys(), key=len, reverse=True)
    month_names = "|".join(re.escape(k) for k in sorted_months)
    boundary_l = r"(?:^|(?<=[\s,(]))"
    boundary_r = r"(?=$|[\s.,;!?()।॥])"

    md_pat1 = re.search(
        rf"{boundary_l}([^\s.,;!?]+)\s+({month_names})(?:\s+(\d{{4}}))?{boundary_r}",
        lower,
    )
    if md_pat1:
        day_parsed = parse_number_tokens([md_pat1.group(1)])
        if day_parsed is not None and 1 <= day_parsed <= 31 and float(day_parsed).is_integer():
            day_i = int(day_parsed)
            mon_i = MONTH_MAP[md_pat1.group(2)]
            yr_i = int(md_pat1.group(3)) if md_pat1.group(3) else anchor.year
            try:
                candidate = date(yr_i, mon_i, day_i)
                if not md_pat1.group(3) and candidate < anchor:
                    candidate = date(yr_i + 1, mon_i, day_i)
                return candidate, md_pat1.group(0).strip(), None
            except ValueError:
                return None, md_pat1.group(0).strip(), md_pat1.group(0).strip()

    md_pat2 = re.search(
        rf"{boundary_l}({month_names})\s+(\d{{1,2}})(?:\s+(\d{{4}}))?{boundary_r}",
        lower,
    )
    if md_pat2:
        mon_i = MONTH_MAP[md_pat2.group(1)]
        day_i = int(md_pat2.group(2))
        yr_i = int(md_pat2.group(3)) if md_pat2.group(3) else anchor.year
        try:
            candidate = date(yr_i, mon_i, day_i)
            if not md_pat2.group(3) and candidate < anchor:
                candidate = date(yr_i + 1, mon_i, day_i)
            return candidate, md_pat2.group(0).strip(), None
        except ValueError:
            return None, md_pat2.group(0).strip(), md_pat2.group(0).strip()

    # 4. Multilingual weekday lookup (safe for Indic combining marks via token matching + ASCII boundary)
    tokens = tokenize_unicode_words(lower)
    for idx, tok in enumerate(tokens):
        if tok in WEEKDAY_MAP:
            target_wd = WEEKDAY_MAP[tok]
            days_ahead = (target_wd - anchor.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            raw_ref = " ".join(tokens[max(0, idx - 1) : idx + 1])
            return anchor + timedelta(days=days_ahead), raw_ref, None
    for wd_key, target_wd in sorted(WEEKDAY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if not wd_key.isascii() and wd_key in lower:
            days_ahead = (target_wd - anchor.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return anchor + timedelta(days=days_ahead), wd_key, None

    # 5. Relative offsets across all 10 languages: days / weeks / months
    day_units = (
        r"(?:din|days|day|दिनों|दिन|நாட்கள்|நாள்|రోజులు|రోజుల|రోజు|দিন|दिवसांनी|दिवस|"
        r"દિવસ|ದಿನಗಳ|ದಿನ|ദിവസത്തിന്|ദിവസം|ਦਿਨਾਂ|ਦਿਨ)"
    )
    days_pat = re.search(
        rf"(?:^|\s)([^\s]+)\s*{day_units}(?:\s*(?:baad|bad|later|बाद|பிறகு|கழித்து|తర్వాత|পরে|नंतर|પછી|ನಂತರ|ശേഷം|ਬਾਅਦ))?|"
        rf"\b(?:after|in)\s+([^\s]+)\s*{day_units}",
        lower,
    )
    if days_pat:
        raw_num = days_pat.group(1) or days_pat.group(2)
        val = parse_number_tokens([raw_num])
        if val is not None and 1 <= val <= 365:
            return anchor + timedelta(days=int(val)), days_pat.group(0).strip(), None

    week_units = (
        r"(?:hafte|hafta|weeks|week|हफ्ते|सप्ताह|வாரங்கள்|வாரம்|వారాలు|వారం|সপ্তাহ|आठवडे|आठवड्यांनी|आठवडा|અઠવાડિયા|ವಾರಗಳ|ವಾರ|ആഴ്ച|ਹਫ਼ਤੇ|ਹਫ਼ਤਾ)"
    )
    weeks_pat = re.search(
        rf"(?:^|\s)([^\s]+)\s*{week_units}(?:\s*(?:baad|bad|later|बाद|பிறகு|கழித்து|తర్వాత|পরে|नंतर|પછી|ನಂತರ|ശേഷം|ਬਾਅਦ))?|"
        rf"\b(?:after|in)\s+([^\s]+)\s*{week_units}",
        lower,
    )
    if weeks_pat:
        raw_num = weeks_pat.group(1) or weeks_pat.group(2)
        val = parse_number_tokens([raw_num])
        if val is not None and 1 <= val <= 52:
            return anchor + timedelta(weeks=int(val)), weeks_pat.group(0).strip(), None

    month_units = (
        r"(?:mahine|mahina|months|month|महीने|माह|மாதங்கள்|மாதம்|నెలలు|నెల|মাস|महिना|महिने|મહિના|ತಿಂಗಳು|മാസം|ਮਹੀਨੇ)"
    )
    months_pat = re.search(
        rf"(?:^|\s)([^\s]+)\s*{month_units}(?:\s*(?:baad|bad|later|बाद|பிறகு|கழித்து|తర్వాత|পরে|नंतर|પછી|ನಂತರ|ശേഷം|ਬਾਅਦ))?|"
        rf"\b(?:after|in)\s+([^\s]+)\s*{month_units}",
        lower,
    )
    if months_pat:
        raw_num = months_pat.group(1) or months_pat.group(2)
        val = parse_number_tokens([raw_num])
        if val is not None and 1 <= val <= 12:
            return _add_months(anchor, int(val)), months_pat.group(0).strip(), None

    # 6. Tomorrow across all 10 languages in follow-up context
    tomorrow_words = r"(?:tomorrow|நாளை|రేపు|আগামীকাল|उद्या|આવતીકાલે|ನಾಳೆ|നാളെ|ਕੱਲ੍ਹ)"
    if re.search(tomorrow_words, lower) or (
        re.search(r"\bkal\b|कल", lower)
        and re.search(r"\b(?:next\s*visit|agla\s*visit|follow\s*up|visit|bulaya|aana)\b|अगली\s*विजिट", lower)
    ):
        return anchor + timedelta(days=1), "tomorrow", None

    if re.search(r"\b(?:day\s+after\s+tomorrow|parson|parso)\b", lower) and re.search(
        r"\b(?:next\s*visit|agla\s*visit|follow\s*up|visit|bulaya|aana)\b", lower
    ):
        return anchor + timedelta(days=2), "parson", None

    # 7. Ambiguous references across all 10 languages — DO NOT invent a date!
    ambig_pat = re.search(
        r"(?:\b(?:agle\s+hafte|agla\s+hafta|next\s+week|agle\s+mahine|agla\s+mahina|"
        r"next\s+month|kuch\s+din\s+baad|thoda\s+baad|soon|later|sometime|few\s+days\s+later)\b|"
        r"अगले\s+हफ्ते|अगले\s+सप्ताह|अगले\s+महीने|कुछ\s+दिन\s+बाद|"
        r"அடுத்த\s+வாரம்|சில\s+நாட்கள்\s+கழித்து|వచ్చే\s+వారం|కొన్ని\s+రోజుల\s+తర్వాత|"
        r"আগামী\s+সপ্তাহ|কিছুদিন\s+পর|पुढच्या\s+आठवड्यात|काही\s+दिवसांनी|"
        r"આવતા\s+અઠવાડિયે|થોડા\s+દિવસ\s+પછી|ಮುಂದಿನ\s+ವಾರ|ಕೆಲವು\s+ದಿನಗಳ\s+ನಂತರ|"
        r"അടുത്ത\s+ആഴ്ച|കുറച്ച്\s+ദിവസങ്ങൾക്ക്\s+ശേഷം|ਅਗਲੇ\s+ਹਫ਼ਤੇ|ਕੁਝ\s+ਦਿਨਾਂ\s+ਬਾਅਦ)",
        lower,
    )
    if ambig_pat:
        ref = ambig_pat.group(0)
        return None, ref, ref

    return None, None, None
