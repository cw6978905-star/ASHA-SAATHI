# ASHA Saathi – AI Brain (Person B) Integration Contract

This document defines the REST API and data contract exposed by Person B's AI Brain (`backend/`) for integration with Person A (Voice Pipeline) and Person C (Frontend, Database & Follow-up Dashboard).

## Running Locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs: `http://localhost:8000/docs`

---

## Integration Boundaries

- **Supported Languages (Gnani Prisma v3.0 / Timbre v3.0):** `hi-IN`, `en-IN`, `ta-IN`, `te-IN`, `bn-IN`, `mr-IN`, `gu-IN`, `kn-IN`, `ml-IN`, `pa-IN`, plus `hi-en` (Hinglish code-mix), `hi`, `en`, and `auto`.
- **Person A (Voice Pipeline):** Sends final STT transcript, `session_id`, `language` (or `"auto"`), optional `detected_language` from Gnani Prisma v3.0, optional `preferred_language`, and optional `visit_date`. Receives `reply_text`, `language`, `detected_language`, `language_switched`, `tts_metadata` (for Gnani Timbre v3.0 synthesis), `action`, `confirmation_required`, and danger referral alerts.
- **Person C (Frontend & Storage):** Reads `form_state`, `missing_fields`, `visit_type`, `beneficiary_info`, `danger_detected`, `danger_flags`, `confirmed`, `follow_up_date`, `vaccinations`, and `next_actions`. Persists and encrypts only when `/api/brain/confirm` returns `confirmed: true` and `ready_for_storage: true`.

### Pending External Inputs
1. **LLM API Credentials:** Configure `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, and optional `LLM_BASE_URL` in `backend/.env`. Defaults safely to `LLM_PROVIDER=mock` when credentials are omitted.
2. **Verified Danger-Sign Guidelines (`data/danger_signs.json`):** Currently populated with preliminary placeholder entries marked `PENDING_PERSON_C_VERIFICATION`. Person C should supply the officially verified public-health danger-sign entries, regional phrases, and authoritative source citations.

---

## Endpoints

### 1. `GET /health`
Returns server readiness, active `llm_provider`, `timezone`, and danger-sign verification metadata.

### 2. `GET /api/brain/intro?language=hi-en`
Returns configurable AI safety disclosure message (`hi-en`, `hi`, or `en`) if needed at session start.

### 3. `POST /api/brain/process`
Primary turn endpoint for Person A.

**Request:**
```json
{
  "session_id": "session_001",
  "transcript": "Aaj maine Priya Devi ka newborn checkup kiya. Baby ka weight do point aath kilo hai. BCG vaccination ho gaya hai. Next visit agle Mangalvar ko hai.",
  "language": "hi-en",
  "visit_date": "2026-11-11"
}
```

**Response:**
```json
{
  "session_id": "session_001",
  "reply_text": "Beneficiary ID bata dijiye.",
  "action": "collect_info",
  "form_state": {
    "beneficiary_name": "Priya Devi",
    "beneficiary_id": null,
    "visit_type": "newborn",
    "visit_date": "2026-11-11",
    "weight_kg": 2.8,
    "blood_pressure": null,
    "pregnancy_info": null,
    "newborn_info": null,
    "vaccinations": {"BCG": "completed"},
    "ifa_status": null,
    "next_visit_date": "2026-11-17",
    "ambiguous_next_visit_reference": null,
    "danger_signs": [],
    "observations": ["Aaj maine Priya Devi ka newborn checkup kiya. Baby ka weight do point aath kilo hai. BCG vaccination ho gaya hai. Next visit agle Mangalvar ko hai."],
    "negative_findings": {},
    "unknown_fields": [],
    "missing_fields": ["beneficiary_id"]
  },
  "missing_fields": ["beneficiary_id"],
  "visit_type": "newborn",
  "beneficiary_info": {"name": "Priya Devi", "id": null},
  "danger_detected": false,
  "danger_flags": [],
  "confirmation_required": false,
  "confirmed": false,
  "follow_up_date": "2026-11-17",
  "vaccinations": {"BCG": "completed"},
  "next_actions": ["collect_missing:beneficiary_id"],
  "guardrail_triggered": false,
  "guardrail_reason": null
}
```

### 4. `POST /api/brain/correct`
Applies single or multiple spoken field corrections to an existing session without mutating unrelated fields.

### 5. `POST /api/brain/readback`
Generates full natural-language read-back in the worker's selected language.

### 6. `POST /api/brain/confirm`
Evaluates explicit worker confirmation (`"Haan, save kar do"` / `explicit_confirm: true`), rejection (`"Nahi, mat save karo"`), or pre-save correction. Returns `confirmed_record` for Person C's encrypted storage layer only after explicit confirmation.

### 7. `GET /api/brain/session/{session_id}` & `DELETE /api/brain/session/{session_id}`
Inspects or clears temporary in-memory session state.

### 8. `GET /api/brain/languages` & `POST /api/brain/session/{session_id}/language`
Lists the 10 Gnani Prisma/Timbre v3.0 supported languages and allows manual mid-conversation language preference switching (`{"language": "ta-IN"}`) while preserving existing form state.
