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