# ASHA-SAATHI — Live LLM & Gnani Integration Runbook

This guide documents the exact steps required to move from verified offline mock/stub testing to live external API verification.

---

## 1. Environment Variables Required

Copy `.env.example` to `.env` (at repo root, `backend/.env`, or `voice/.env`):

| Variable | Owner | Required For | Notes |
|---|---|---|---|
| `GNANI_API_KEY` | Person A | Live Prisma v3.0 STT + Timbre v3.0 TTS | Sent via `x-api-key-id` (STT) / `X-API-Key-ID` (TTS) |
| `LLM_PROVIDER` | Person B | AI Brain LLM mode | `mock`, `auto`, `openai`, `openai_compatible`, `gemini`, or `anthropic` |
| `LLM_API_KEY` | Person B | Real LLM mode | Or provider-specific `OPENAI_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` |
| `LLM_MODEL` | Person B | Real LLM mode | Target model ID (e.g. `gpt-4o-mini`, `gemini-2.5-flash`, `claude-3-5-sonnet-latest`) |
| `LLM_BASE_URL` | Person B | Optional | Custom endpoint for Groq, OpenRouter, vLLM, or Ollama |
| `APP_ENV` | Person B | Optional | Set `production` to forbid silent fallback to mock mode |
| `REQUIRE_REAL_LLM` | Person B | Optional | `true` enforces real LLM credentials at startup |
| `LLM_TIMEOUT_SECONDS` | Person B | Optional | Default `20` |
| `MAX_EXTRACTION_RETRIES` | Person B | Optional | Default `2` JSON schema repair retries |
| `APP_TIMEZONE` | Person B | Optional | Default `Asia/Kolkata` |
| `DANGER_SIGNS_PATH` | Person B | Optional | Default `data/danger_signs.json` |
| `LOG_LEVEL` | Person B | Optional | Default `INFO` |

> **Fail-Closed Policy:** Setting `LLM_PROVIDER` to `openai`, `openai_compatible`, `gemini`, or `anthropic` without `LLM_API_KEY` and `LLM_MODEL` (or setting `APP_ENV=production` / `REQUIRE_REAL_LLM=true` without credentials) raises `LLMConfigurationError` at startup and **never silently falls back to `MockLLMClient`**.

---

## 2. Live LLM Verification Steps (Person B)

1. Export real credentials in `.env` (without committing `.env`):
   ```bash
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=<real-key>
   LLM_MODEL=gemini-2.5-flash
   REQUIRE_REAL_LLM=true
   ```
2. Start backend or integrated voice server and check `/health`:
   ```bash
   cd voice
   ../backend/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000
   curl http://localhost:8000/health
   ```
   Confirm `llm_mode == "live"`, `llm_provider == "gemini"`, and `llm_model_configured == true`.
3. Send a test transcript via `POST /api/brain/process` across Hindi/English/Tamil/Bengali and inspect validated `form_state`, `danger_flags`, and absence of API keys in server logs.

---

## 3. Live Gnani Prisma v3.0 & Timbre v3.0 Verification Steps (Person A)

Since `GNANI_API_KEY` is not present in this environment, live audio tests could not be executed. Perform these steps with an active Gnani key:

1. Set `GNANI_API_KEY` in `voice/.env` (or root `.env`).
2. Start `uvicorn server:app` inside `voice/` and open `http://localhost:8000/` in a Chromium/Safari mobile browser over localhost or HTTPS (required for `getUserMedia` mic access).
3. Tap the microphone button once to verify:
   - `"hello"` trigger invokes Timbre v3.0 TTS (`tts_start` -> raw linear PCM 16 kHz audio -> `tts_end`) speaking Person B's safety disclosure.
4. Hold to talk across **all 10 supported languages** (`hi-IN`, `en-IN`, `ta-IN`, `te-IN`, `bn-IN`, `mr-IN`, `gu-IN`, `kn-IN`, `ml-IN`, `pa-IN`) plus Hinglish code-mixing (`hi-en`):
   - Confirm Prisma v3.0 (`indic-auto`) returns `type: "transcript"` frames with detected language metadata (`detected_language` / `language` / `language_code`).
   - Confirm `"brain"` JSON frames update `#form`, append `"Assistant: ..."` to `#log`, trigger persistent red `#banner` on danger phrases, and stream Timbre v3.0 audio in the matching `language_code`.
5. Test barge-in by pressing the talk button while TTS is actively playing (`{"type":"interrupt"}` cancels active `speak` task and browser audio buffers).
6. Record measured browser end-of-speech -> first TTS audio byte latency shown in `#latency` plus server-side `latency_ms` in `"brain"` frames across languages, and log any Gnani STT language-tag quirks or recognition errors.

---

## 4. Clinical Review Sign-Off (Person C)

See [`backend/CLINICAL_DANGER_SIGNS_REVIEW.md`](backend/CLINICAL_DANGER_SIGNS_REVIEW.md) for all 12 danger-sign entries awaiting qualified public-health verification against NHM HBNC / IMNCI / MCP Card / PMSMA / WHO PCPNC guidelines before removing `PENDING_PERSON_C_VERIFICATION`.
