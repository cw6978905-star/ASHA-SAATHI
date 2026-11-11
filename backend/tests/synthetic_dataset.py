"""Comprehensive 40-case synthetic ASHA healthcare dataset for evaluation and testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SyntheticExtractionCase:
    case_id: int
    label: str
    transcript: str
    expected_visit_type: Optional[str] = None
    expected_name: Optional[str] = None
    expected_id: Optional[str] = None
    expected_weight_kg: Optional[float] = None
    expected_bp: Optional[tuple[int, int]] = None
    expected_ifa: Optional[str] = None
    expected_vaccinations: Dict[str, str] = field(default_factory=dict)
    expected_next_visit_date: Optional[str] = None
    expect_ambiguous_date: bool = False
    expected_danger: bool = False


# Anchor date across dataset: 2026-11-11 (Wednesday)
SYNTHETIC_EXTRACTION_CASES: List[SyntheticExtractionCase] = [
    SyntheticExtractionCase(
        case_id=1,
        label="Hindi ANC visit",
        transcript="Aaj maine Sunita Devi ka ANC checkup kiya. Weight pachpan kilo hai. BP 120/80 hai. IFA goli di. Next visit agle Mangalvar ko hai.",
        expected_visit_type="anc",
        expected_name="Sunita Devi",
        expected_weight_kg=55.0,
        expected_bp=(120, 80),
        expected_ifa="provided",
        expected_next_visit_date="2026-11-17",
    ),
    SyntheticExtractionCase(
        case_id=2,
        label="English ANC visit",
        transcript="Today I conducted an ANC checkup for Kavita Sharma. Beneficiary ID is A-204. Weight is 58.5 kg. Blood pressure is 118/76. IFA tablets provided. Next visit after 7 days.",
        expected_visit_type="anc",
        expected_name="Kavita Sharma",
        expected_id="A-204",
        expected_weight_kg=58.5,
        expected_bp=(118, 76),
        expected_ifa="provided",
        expected_next_visit_date="2026-11-18",
    ),
    SyntheticExtractionCase(
        case_id=3,
        label="Mixed newborn visit (spec example)",
        transcript="Aaj maine Priya Devi ka newborn checkup kiya. Baby ka weight do point aath kilo hai. BCG vaccination ho gaya hai. Next visit agle Mangalvar ko hai.",
        expected_visit_type="newborn",
        expected_name="Priya Devi",
        expected_id=None,
        expected_weight_kg=2.8,
        expected_vaccinations={"BCG": "completed"},
        expected_next_visit_date="2026-11-17",
    ),
    SyntheticExtractionCase(
        case_id=4,
        label="Spoken weight do point aath",
        transcript="Baby ka weight do point aath kilo hai.",
        expected_weight_kg=2.8,
    ),
    SyntheticExtractionCase(
        case_id=5,
        label="Spoken weight two point eight",
        transcript="Newborn weight is two point eight kg.",
        expected_visit_type="newborn",
        expected_weight_kg=2.8,
    ),
    SyntheticExtractionCase(
        case_id=6,
        label="Spoken weight kg and grams",
        transcript="Baby ka weight do kilo aath sau gram hai.",
        expected_weight_kg=2.8,
    ),
    SyntheticExtractionCase(
        case_id=7,
        label="Spoken weight dhayi kilo",
        transcript="Newborn ka vajan dhayi kilo hai.",
        expected_visit_type="newborn",
        expected_weight_kg=2.5,
    ),
    SyntheticExtractionCase(
        case_id=8,
        label="IFA tablets provided",
        transcript="ANC visit mein IFA goli di hai aur BP 110/70 hai.",
        expected_visit_type="anc",
        expected_bp=(110, 70),
        expected_ifa="provided",
    ),
    SyntheticExtractionCase(
        case_id=9,
        label="BCG vaccination completed",
        transcript="Baby ko BCG lag gaya hai aur OPV-0 bhi diya gaya hai.",
        expected_vaccinations={"BCG": "completed", "OPV-0": "completed"},
    ),
    SyntheticExtractionCase(
        case_id=10,
        label="Digit-by-digit beneficiary ID",
        transcript="Beneficiary ID hai P ek shunya do.",
        expected_id="P-102",
    ),
    SyntheticExtractionCase(
        case_id=11,
        label="Pure numeric digit-by-digit ID",
        transcript="Patient ID number one two three four hai.",
        expected_id="1234",
    ),
    SyntheticExtractionCase(
        case_id=12,
        label="Relative date after X weeks",
        transcript="Next visit ek hafte baad hai.",
        expected_next_visit_date="2026-11-18",
    ),
    SyntheticExtractionCase(
        case_id=13,
        label="Ambiguous relative date",
        transcript="Next visit agle hafte hogi.",
        expected_next_visit_date=None,
        expect_ambiguous_date=True,
    ),
    SyntheticExtractionCase(
        case_id=14,
        label="Pregnancy duration teen mahine",
        transcript="Rekha Devi ka ANC visit, teen mahine ki pregnancy hai, weight 49 kilo.",
        expected_visit_type="anc",
        expected_name="Rekha Devi",
        expected_weight_kg=49.0,
    ),
    SyntheticExtractionCase(
        case_id=15,
        label="Explicit negative IFA",
        transcript="Meena Devi ka PNC visit, weight 50 kilo, IFA nahi diya.",
        expected_visit_type="pnc",
        expected_name="Meena Devi",
        expected_weight_kg=50.0,
        expected_ifa="not_provided",
    ),
    SyntheticExtractionCase(
        case_id=16,
        label="Immunisation visit without weight",
        transcript="Aarav ka immunisation visit hai, beneficiary ID R-305, Pentavalent lag gaya, next visit 14 din baad.",
        expected_visit_type="immunisation",
        expected_name="Aarav",
        expected_id="R-305",
        expected_vaccinations={"Pentavalent": "completed"},
        expected_next_visit_date="2026-11-25",
    ),
    SyntheticExtractionCase(
        case_id=17,
        label="Noisy code-mixed transcript with filler",
        transcript="Haanji aaj maine Geeta Rani ka PNC checkup kiya, weight 52.5 kilo hai aur ID G-410 hai.",
        expected_visit_type="pnc",
        expected_name="Geeta Rani",
        expected_id="G-410",
        expected_weight_kg=52.5,
    ),
    SyntheticExtractionCase(
        case_id=18,
        label="Spoken BP in Hindi",
        transcript="ANC checkup mein BP ek sau bees by assi hai.",
        expected_visit_type="anc",
        expected_bp=(120, 80),
    ),
    SyntheticExtractionCase(
        case_id=19,
        label="Grams only weight",
        transcript="Baby ka weight aath sau gram hai.",
        expected_weight_kg=0.8,
    ),
    SyntheticExtractionCase(
        case_id=20,
        label="Explicit unknown ID",
        transcript="Beneficiary ID abhi pata nahi hai.",
        expected_id=None,
    ),
]


@dataclass(frozen=True)
class SyntheticDangerCase:
    case_id: int
    label: str
    transcript: str
    expected_danger: bool
    expected_sign_ids: List[str] = field(default_factory=list)
    expect_ambiguous: bool = False


SYNTHETIC_DANGER_CASES: List[SyntheticDangerCase] = [
    SyntheticDangerCase(
        case_id=21,
        label="Pregnancy vaginal bleeding (Hinglish)",
        transcript="Priya Devi ko pregnancy mein heavy bleeding ho rahi hai.",
        expected_danger=True,
        expected_sign_ids=["severe_bleeding"],
    ),
    SyntheticDangerCase(
        case_id=22,
        label="Newborn high fever (Hinglish)",
        transcript="Baby ko tez bukhar hai aur sharir bahut garam hai.",
        expected_danger=True,
        expected_sign_ids=["high_fever"],
    ),
    SyntheticDangerCase(
        case_id=23,
        label="Hindi Devanagari convulsions and fever",
        transcript="मरीज को तेज बुखार है और दौरे पड़ रहे हैं।",
        expected_danger=True,
        expected_sign_ids=["high_fever", "convulsions"],
    ),
    SyntheticDangerCase(
        case_id=24,
        label="English breathing difficulty",
        transcript="The newborn has fast breathing and chest indrawing since morning.",
        expected_danger=True,
        expected_sign_ids=["breathing_difficulty"],
    ),
    SyntheticDangerCase(
        case_id=25,
        label="Code-mixed poor feeding and fever",
        transcript="Baby ko high fever hai aur doodh nahi pi raha hai.",
        expected_danger=True,
        expected_sign_ids=["high_fever", "poor_feeding_newborn"],
    ),
    SyntheticDangerCase(
        case_id=26,
        label="Maternal severe headache and blurred vision",
        transcript="Patient ko bahut tez sar dard aur aankhon ke aage dhundhla dikh raha hai.",
        expected_danger=True,
        expected_sign_ids=["severe_headache_blurred_vision"],
    ),
    SyntheticDangerCase(
        case_id=27,
        label="Reduced fetal movement",
        transcript="Garbhavati mahila ne bataya pet mein baccha hil nahi raha hai.",
        expected_danger=True,
        expected_sign_ids=["reduced_fetal_movement"],
    ),
    SyntheticDangerCase(
        case_id=28,
        label="Umbilical cord infection",
        transcript="Newborn ke nabhi se mawad aa raha hai aur nabhi laal ho gayi hai.",
        expected_danger=True,
        expected_sign_ids=["umbilical_cord_infection"],
    ),
    SyntheticDangerCase(
        case_id=29,
        label="Explicit negative statement (no bleeding, no fever)",
        transcript="Patient ko bleeding nahi hai aur baby ko bukhar nahi hai. Sab normal hai.",
        expected_danger=False,
    ),
    SyntheticDangerCase(
        case_id=30,
        label="Explicit negative English statement",
        transcript="No fever, no convulsions, and no breathing difficulty observed.",
        expected_danger=False,
    ),
    SyntheticDangerCase(
        case_id=31,
        label="Ambiguous danger sign statement (recall-first)",
        transcript="Baby thoda garam lag raha hai, shayad bukhar ho.",
        expected_danger=True,
        expected_sign_ids=["high_fever"],
        expect_ambiguous=True,
    ),
    SyntheticDangerCase(
        case_id=32,
        label="Ambiguous spotting statement",
        transcript="Lag raha hai halka sa khoon ka daag dikha tha.",
        expected_danger=True,
        expected_sign_ids=["severe_bleeding"],
        expect_ambiguous=True,
    ),
    SyntheticDangerCase(
        case_id=33,
        label="Indirect contextual expression (Layer 2)",
        transcript="Baccha respond nahi kar raha aur bilkul dheela pad gaya hai.",
        expected_danger=True,
        expected_sign_ids=["unconsciousness_lethargy"],
    ),
    SyntheticDangerCase(
        case_id=34,
        label="Routine healthy newborn checkup (no danger)",
        transcript="Baby ka weight 3.1 kilo hai, BCG vaccination ho gaya, breastfeeding normal hai.",
        expected_danger=False,
    ),
]


@dataclass(frozen=True)
class SyntheticCorrectionCase:
    case_id: int
    label: str
    initial_state: Dict[str, Any]
    transcript: str
    expected_applied: bool
    expected_fields: Dict[str, Any] = field(default_factory=dict)
    expect_clarification: bool = False


SYNTHETIC_CORRECTION_CASES: List[SyntheticCorrectionCase] = [
    SyntheticCorrectionCase(
        case_id=35,
        label="Incorrect weight correction",
        initial_state={"beneficiary_name": "Priya Devi", "weight_kg": 3.2, "visit_type": "newborn"},
        transcript="No, weight is 2.8 kilo.",
        expected_applied=True,
        expected_fields={"weight_kg": 2.8},
    ),
    SyntheticCorrectionCase(
        case_id=36,
        label="Incorrect name correction",
        initial_state={"beneficiary_name": "Priya", "weight_kg": 2.8, "visit_type": "newborn"},
        transcript="Naam Priya nahi, Priti hai.",
        expected_applied=True,
        expected_fields={"beneficiary_name": "Priti"},
    ),
    SyntheticCorrectionCase(
        case_id=37,
        label="Incorrect date correction",
        initial_state={"beneficiary_name": "Priya Devi", "next_visit_date": "2026-11-16"},
        transcript="Next visit Monday nahi Tuesday hai.",
        expected_applied=True,
        expected_fields={"next_visit_date": "2026-11-17"},
    ),
    SyntheticCorrectionCase(
        case_id=38,
        label="Beneficiary ID correction",
        initial_state={"beneficiary_name": "Priya Devi", "beneficiary_id": "P-102"},
        transcript="Beneficiary ID galat hai, P-103 hai.",
        expected_applied=True,
        expected_fields={"beneficiary_id": "P-103"},
    ),
    SyntheticCorrectionCase(
        case_id=39,
        label="Multiple corrections in one utterance",
        initial_state={"beneficiary_name": "Priya", "weight_kg": 2.8, "visit_type": "newborn"},
        transcript="Naam Priya nahi Priti hai aur weight 2.8 nahi 3.1 kilo hai.",
        expected_applied=True,
        expected_fields={"beneficiary_name": "Priti", "weight_kg": 3.1},
    ),
    SyntheticCorrectionCase(
        case_id=40,
        label="IFA negative correction",
        initial_state={"beneficiary_name": "Sunita Devi", "ifa_status": "provided", "visit_type": "anc"},
        transcript="IFA nahi diya.",
        expected_applied=True,
        expected_fields={"ifa_status": "not_provided"},
    ),
]
