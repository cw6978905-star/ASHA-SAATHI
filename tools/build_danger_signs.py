"""
Builds contracts/danger_signs.json from B's backend/data/danger_signs.json.
Adds: source citations, tiers (refer_now / possible_confirm), weak_terms,
new source-backed signs, numeric rules, negation policy, verification flags.
B's original file is never modified.
"""
import json
from pathlib import Path

SRC = Path("backend/data/danger_signs.json")
OUT = Path("contracts/danger_signs.json")

JOB_AID = {
    "title": "Job Aid for Home Visits by ASHA (Newborn and Young Child)",
    "publisher": "Child Health Division, MoHFW, Govt. of India",
    "year": 2018,
    "url": "https://hbnc-hbyc.mohfw.gov.in/assets/document/English-Job%20Aid%20for%20ASHA%20on%20HBYC.pdf",
    "note": "Page numbers are those printed on the job aid pages. Re-check before submission.",
}

NOT_IN_SOURCE = "NOT_FOUND_IN_JOB_AID: needs RCH/MCP citation or removal from verified list"

# Per-sign changes. Strings are ADDED to B's lists (never replace them).
PATCH = {
    "severe_bleeding": dict(
        applies_to="mother", default_tier="refer_now", source_pages=[7, 8],
        verification="partial: job aid covers excessive postnatal bleeding (more than 5 pads/day). "
                     "Bleeding in pregnancy is NOT in this document.",
        weak_terms=["bleeding", "spotting", "blood loss", "khoon ka daag", "bleading", "khun"],
        add_english=["more than 5 pads", "soaking pads"],
        add_hindi=["paanch pad se zyada", "5 pad se zyada", "pad bhig gaya", "पांच पैड से ज्यादा"],
    ),
    "high_fever": dict(
        applies_to="mother|newborn|child", default_tier="refer_now", source_pages=[7, 27],
        verification="source_verified. Mother threshold is above 102 F; baby: hot to touch.",
        weak_terms=["fever", "bukhar hai", "bukhaar hai", "fever hai", "bukhar ho gaya",
                    "garam lag raha hai", "बुखार है", "बुखार", "bhukhar", "feaver"],
        add_english=["hot to touch", "feels hot"],
        add_hindi=["badan garam hai", "baccha garam hai", "बच्चा गरम है"],
    ),
    "convulsions": dict(
        applies_to="newborn|child", default_tier="refer_now", source_pages=[27],
        verification="partial: confirmed for young child. Newborn convulsions need NSSK/HBNC module.",
        weak_terms=["twitching", "jerking movements", "fitts"],
        add_english=[], add_hindi=[],
    ),
    "breathing_difficulty": dict(
        applies_to="newborn|child", default_tier="refer_now", source_pages=[7, 10, 26, 27],
        verification="source_verified (fast or difficult breathing; chest indrawing under pneumonia, p26).",
        weak_terms=["breathless", "sans", "saans"],
        add_english=["fast and difficult breathing"], add_hindi=["saans tezi se chal rahi hai"],
    ),
    "unconsciousness_lethargy": dict(
        applies_to="mother|newborn|child", default_tier="refer_now", source_pages=[7, 10, 27],
        verification="source_verified (mother losing consciousness; baby weak cry or limp; child lethargic).",
        weak_terms=["not moving", "bahut sust", "sust sa lag raha", "sust", "बहुत सुस्त"],
        add_english=["weak cry", "limp baby", "floppy"],
        add_hindi=["kamzor rona", "rona kamzor hai", "baccha dheela pad gaya",
                   "कमजोर रोना", "ढीला पड़ गया"],
    ),
    "poor_feeding_newborn": dict(
        applies_to="newborn", default_tier="refer_now", source_pages=[7, 10],
        verification="source_verified ('not able to feed' / not feeding well).",
        weak_terms=["doodh kam pi raha"],
        add_english=["not able to feed"], add_hindi=["doodh nahi le raha", "दूध नहीं ले रहा"],
    ),
    "umbilical_cord_infection": dict(
        applies_to="newborn", default_tier="refer_now", source_pages=[9],
        verification="partial: job aid lists oozing umbilicus. Redness/swelling/foul smell not in this document.",
        weak_terms=["naal mein infection", "nabhi mein sujan", "swollen umbilicus"],
        add_english=["oozing umbilicus", "oozing from cord"],
        add_hindi=["nabhi se paani", "नाभि से पानी"],
    ),
    "newborn_jaundice": dict(
        applies_to="newborn", default_tier="refer_now", source_pages=[9, 10],
        verification="source_verified (yellow palms/soles; yellow eyes or skin; timing Day 1 or after Day 14).",
        weak_terms=["jaundice", "newborn jaundice", "piliya ho gaya", "पीलिया", "peeliya", "piliya"],
        add_english=[], add_hindi=["talwe peele", "तलवे पीले"],
    ),
    "hypothermia_cold_baby": dict(
        applies_to="newborn", default_tier="refer_now", source_pages=[7, 10],
        verification="source_verified (feels hot or cold to touch).",
        weak_terms=["thanda", "bahut thanda lag raha"],
        add_english=["feels cold"], add_hindi=[],
    ),
    "severe_headache_blurred_vision": dict(
        applies_to="mother", default_tier="possible_confirm", source_pages=[],
        verification=NOT_IN_SOURCE,
        weak_terms=["sir dard", "sar dard", "soojan"], add_english=[], add_hindi=[],
    ),
    "reduced_fetal_movement": dict(
        applies_to="mother", default_tier="possible_confirm", source_pages=[],
        verification=NOT_IN_SOURCE,
        weak_terms=["halchal kam", "movement nahi"], add_english=[], add_hindi=[],
    ),
    "severe_abdominal_pain": dict(
        applies_to="mother", default_tier="possible_confirm", source_pages=[],
        verification=NOT_IN_SOURCE,
        weak_terms=["pet dard"], add_english=[], add_hindi=[],
    ),
}

# New source-backed signs (English + Hindi only; Hindi is a draft needing native review)
NEW_SIGNS = [
    dict(id="foul_smelling_discharge", category="maternal", applies_to="mother",
         default_tier="refer_now", source_pages=[7, 8],
         verification="source_verified (foul smelling discharge in mother).",
         english_name="Foul-Smelling Vaginal Discharge",
         english_keywords=["foul smelling discharge", "foul smell discharge", "bad smelling discharge"],
         hindi_phrases=["badbudar paani", "badbu wala discharge", "discharge se badbu aa rahi hai",
                        "बदबूदार स्राव", "बदबू वाला डिस्चार्ज"],
         weak_terms=[],
         description="Foul-smelling vaginal discharge in the mother after delivery."),
    dict(id="newborn_eye_discharge_or_pustules", category="newborn", applies_to="newborn",
         default_tier="refer_now", source_pages=[9],
         verification="source_verified (eye discharge; pustules; skin fold redness: refer newborn).",
         english_name="Newborn Eye Discharge, Pustules or Skin Redness",
         english_keywords=["eye discharge", "pus in eye", "pustules", "boils on skin", "redness in skin folds"],
         hindi_phrases=["aankh se pani aa raha hai", "aankh mein mawad", "aankh se gandagi",
                        "phunsi", "chhale pad gaye", "आंख से पानी", "आंख में मवाद", "फुंसी"],
         weak_terms=["aankh se pani aa raha hai"],
         description="Eye discharge, pustules, or redness in skin folds of a newborn."),
    dict(id="child_blood_in_stool", category="child", applies_to="child",
         default_tier="refer_now", source_pages=[25, 27],
         verification="source_verified (young child danger sign). Applies to HBYC visits only.",
         english_name="Blood in Stool (Young Child)",
         english_keywords=["blood in stool", "blood in motion", "bloody stool"],
         hindi_phrases=["potty mein khoon", "stool mein blood", "latrine mein khoon", "पॉटी में खून"],
         weak_terms=[], description="Blood in the stool of a young child."),
    dict(id="child_vomits_everything", category="child", applies_to="child",
         default_tier="refer_now", source_pages=[27],
         verification="source_verified (young child danger sign). Applies to HBYC visits only.",
         english_name="Vomits Everything (Young Child)",
         english_keywords=["vomits everything", "vomiting everything", "vomits all feeds"],
         hindi_phrases=["sab kuch ulti kar deta hai", "kuch bhi nahi ruk raha ulti", "सब कुछ उल्टी कर देता है"],
         weak_terms=["ulti ho rahi hai"], description="Child vomits everything and cannot keep feeds down."),
]

NUMERIC_RULES = [
    dict(id="newborn_low_weight", applies_to="newborn", field="weight_kg", op="<", value=1.8,
         tier="refer_now", source_pages=[7, 9],
         note="Job aid: below 1.8 kg, advise KMC and expressed milk, and refer. Normalise grams to kg "
              "(1800 g = 1.8 kg). Always read weight back digit by digit (1.8 vs 2.8)."),
    dict(id="mother_high_temperature", applies_to="mother", field="temperature_f", op=">", value=102,
         tier="refer_now", source_pages=[7], note="Mother fever above 102 F."),
    dict(id="mother_pads_per_day", applies_to="mother", field="pads_per_day", op=">", value=5,
         tier="refer_now", source_pages=[7], note="More than 5 pads in a day."),
]

POSSIBLE_MESSAGES = {
    "hi-en": "Yeh danger sign ho sakta hai. Kripya confirm karein, aur sahi ho to patient ko abhi nearest PHC refer karein.",
    "en": "This may be a danger sign. Please confirm, and if so, refer the patient to the nearest PHC immediately.",
    "hi": "यह खतरे का संकेत हो सकता है। कृपया पुष्टि करें, और सही हो तो मरीज को तुरंत नजदीकी पीएचसी में रेफर करें।",
}


def union(old, new):
    out = list(old or [])
    for item in new:
        if item not in out:
            out.append(item)
    return out


def main():
    legacy = json.loads(SRC.read_text(encoding="utf-8"))
    meta = legacy["metadata"]

    meta["verification_status"] = "partially_verified_pending_native_language_review"
    meta["pending_person_c_verification"] = False
    meta["primary_source"] = JOB_AID
    meta["guideline_note"] = (
        "Signs follow the MoHFW ASHA job aid listed in primary_source. Signs marked NOT_FOUND_IN_JOB_AID "
        "need another cited source or removal. Only Hindi and English are being claimed as verified-for-demo; "
        "other languages are unverified machine-generated phrases kept for experimentation. "
        "The system flags danger signs from a fixed list and gives no diagnosis or treatment advice."
    )
    meta["language_verification"] = {
        "en-IN": "draft_needs_review", "hi-IN": "draft_needs_native_review",
        "others": "unverified_machine_generated",
    }
    meta["tiers"] = {
        "refer_now": "Clear match to a source-backed sign. Show red banner, speak referral, flag record.",
        "possible_confirm": "Ambiguous or weak mention. Show amber alert 'possible danger sign, please confirm' "
                            "and ask the ASHA once. Never stay silent.",
    }
    meta["possible_referral_messages"] = POSSIBLE_MESSAGES
    meta["matching_rules"] = {
        "longest_match_wins": True,
        "weak_terms_rule": "A match on a weak_terms entry only gives possible_confirm; otherwise default_tier applies.",
        "negation_markers": ["nahi", "nahin", "nahi hai", "koi", "no", "not", "without", "नहीं", "कोई"],
        "negation_window_tokens": 3,
        "negation_policy": "If a negation marker is within the window, do not raise an alert but log the "
                           "mention in the record. Misheard negations are a risk, so also show it on screen.",
        "resolved_markers": ["stopped", "band ho gaya", "ruk gaya", "ठीक हो गया", "बंद हो गया"],
        "resolved_policy": "A resolved marker gives possible_confirm (not silence) so the ASHA decides.",
        "unsure_policy": "When unsure, show possible_confirm. A missed sign costs more than an extra check.",
        "scope": "Matching decides which alert to show. The system gives no diagnosis or treatment advice.",
    }
    meta["numeric_rules"] = NUMERIC_RULES

    by_id = {s["id"]: s for s in legacy["danger_signs"]}
    for sid, p in PATCH.items():
        s = by_id.get(sid)
        if not s:
            print(f"WARNING: {sid} not in B's file, skipped")
            continue
        s["applies_to"] = p["applies_to"]
        s["default_tier"] = p["default_tier"]
        s["source_pages"] = p["source_pages"]
        s["weak_terms"] = p["weak_terms"]
        s["verification"] = p["verification"]
        s["english_keywords"] = union(s.get("english_keywords"), p["add_english"])
        s["hindi_phrases"] = union(s.get("hindi_phrases"), p["add_hindi"])
        s["possible_referral_message"] = POSSIBLE_MESSAGES["hi-en"]
        s["source_reference"] = JOB_AID["title"] + ", MoHFW 2018"
        if p["default_tier"] == "possible_confirm":
            s["source_reference"] = "PENDING: no source found yet"

    signs = list(by_id.values())
    for n in NEW_SIGNS:
        signs.append({
            "id": n["id"], "category": n["category"], "applies_to": n["applies_to"],
            "default_tier": n["default_tier"], "english_name": n["english_name"],
            "english_keywords": n["english_keywords"], "hindi_phrases": n["hindi_phrases"],
            "regional_phrases": [],
            "multilingual_phrases": {
                "native_script": {"hi-IN": [p for p in n["hindi_phrases"] if any("\u0900" <= c <= "\u097f" for c in p)]},
                "transliterations": [], "code_mixed": [], "spelling_variations": [],
            },
            "weak_terms": n["weak_terms"], "description": n["description"],
            "referral_message": "Yeh ek danger sign hai. Kripya patient ko abhi nearest PHC refer karein.",
            "possible_referral_message": POSSIBLE_MESSAGES["hi-en"],
            "source_pages": n["source_pages"], "verification": n["verification"],
            "source_reference": JOB_AID["title"] + ", MoHFW 2018",
        })

    legacy["danger_signs"] = signs
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")

    unverified = [s["id"] for s in signs if "NOT_FOUND" in s.get("verification", "")]
    print(f"Wrote {OUT} with {len(signs)} signs.")
    print("Still need a citation or removal:", unverified)


if __name__ == "__main__":
    main()