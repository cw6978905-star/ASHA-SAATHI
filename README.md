# ASHA Saathi (आशा साथी) 🩺🎙️
> **Voice-First Clinical Field Register for ASHA Workers**  
> *Built for the Gnani Voice Hackathon (Healthcare Track)*

## 📌 Overview
ASHA workers spend hours logging pregnancy, newborn, and immunization visits into cumbersome phone apps while walking between houses. **ASHA Saathi** eliminates typing entirely. 

An ASHA worker can speak naturally in any supported Indic language (Hindi, Tamil, regional code-mix, or English)—using local health terminology (*"ANC checkup"*, *"IFA goli"*, *"7 months pregnant"*). The system captures the voice, extracts structured clinical form fields via a Gemini-powered intelligence layer, handles emergency danger-sign escalation instantly, and maintains offline-first visit logs.

---

## 🛠️ Tech Stack & Architecture
- **Speech Capture & Synthesis (STT/TTS):** Gnani AI (`Gnani Prisma v3` STT & `Gnani Timbre v3` TTS) via streaming web audio.
- **AI Brain & Entity Extraction:** FastAPI backend powered by **Gemini 2.5 Flash** for structured JSON extraction and zero-shot code-mixed multilingual understanding.
- **Frontend:** Responsive, mobile-first web interface built with vanilla HTML5, CSS3, and modern JavaScript (Web Speech API + Fetch API).
- **Compliance & Safety:** Deterministic public health danger-sign escalation following standard maternal-child health guidelines (`data/danger_signs.json`).

---

## 🚀 Quickstart Guide (How to Run Locally)

### Prerequisites
- Python 3.10+
- Node.js or a local static file server (optional, or just run via FastAPI's static mount)
- API Keys: Gnani AI credentials & Gemini API Key.

### 1. Clone & Set Up the Backend
```bash
# Navigate to backend
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

## 🏛️ Public Health Compliance, Guardrails & Danger-Sign Citation

### Clinical Guideline Citations
Our danger-sign escalation dataset (`backend/data/danger_signs.json`) is strictly derived from official Government of India and WHO maternal and neonatal community health worker guidelines:
1. **Ministry of Health & Family Welfare (MoHFW), Govt. of India** — *ASHA Training Module 6 & 7: Skills that Saves Lives (Maternal & Newborn Care)* & *Guidelines for Antenatal Care and Skilled Attendance at Birth by ANMs/LHVs/SNs*.
2. **World Health Organization (WHO)** — *Counselling for Maternal and Newborn Health Care: A Handbook for Building Skills* (Danger Signs in Pregnancy, Postpartum, and Newborn).

### Tracked Danger-Sign Escalation List
When any of the following red-flag symptoms are detected in an ASHA worker's spoken notes, the system immediately halts routine logging, triggers an urgent **PHC (Primary Health Centre) Referral** alert in the worker's language, and enforces strict non-diagnostic guardrails (no medication or home-remedy advice):

| Category | Tracked Danger Signs | Immediate Protocol |
| :--- | :--- | :--- |
| **Maternal (ANC / PNC)** | Vaginal bleeding during pregnancy or heavy postpartum bleeding, severe abdominal pain, severe headache with blurred vision, high fever, convulsions / fits, reduced or absent fetal movement, severe swelling of face/hands | Urgent PHC / FRU Referral (`refer_danger`) |
| **Newborn / Infant** | High fever or hypothermia (cold to touch), difficulty breathing / chest indrawing, inability to feed / poor sucking, lethargy or unconsciousness, umbilical cord redness/pus, convulsions | Urgent SNCU / PHC Referral (`refer_danger`) |

### Data Privacy & Synthetic Data Policy
- **Synthetic Beneficiaries Only:** All beneficiary names, IDs, and clinical records used in testing and demos are 100% synthetic. No real patient PII/PHI is stored or transmitted.
- **Zero-Diagnosis Guardrail:** The AI assistant strictly acts as a structured documentation and triage-escalation tool; it refuses to prescribe medication or offer clinical diagnoses.