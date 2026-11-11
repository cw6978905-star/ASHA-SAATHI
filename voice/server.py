import asyncio
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

VOICE_DIR = Path(__file__).resolve().parent
REPO_ROOT = VOICE_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
for _path in (str(REPO_ROOT), str(BACKEND_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from brain.extraction import ExtractionValidationError  # noqa: E402
from brain.llm_client import BaseLLMClient, LLMProviderError  # noqa: E402
from config import Settings, scrub_secrets  # noqa: E402
from main import register_exception_handlers  # noqa: E402
from voice.brain import (  # noqa: E402
    configure_brain_app,
    get_brain_app,
    get_intro_message,
    get_state_manager,
    on_transcript,
)

load_dotenv(dotenv_path=VOICE_DIR / ".env", override=False)
load_dotenv(dotenv_path=BACKEND_DIR / ".env", override=False)
load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
load_dotenv(override=False)
KEY = os.getenv("GNANI_API_KEY")
logger = logging.getLogger("asha_saathi.voice_server")

STT_URL = "wss://api.vachana.ai/stt/v3/stream"
STT_HEADERS = {
    "x-api-key-id": KEY,
    "model": "prisma-v3.0",
    "language_code": "indic-auto",
    "format": "transcribe",
    "keyterms": json.dumps([
        "TT injection", "TT", "ANC checkup", "ANC", "IFA goli", "IFA",
        "PHC", "ASHA", "Anganwadi", "immunisation", "newborn",
        "bleeding", "high fever", "fever", "convulsions", "fits",
        "swelling", "refer",
    ]),
    "topic": "ASHA worker home visit notes: antenatal care, newborn, immunisation",
    "x-min-silence-ms": "900",
    "x-idle-timeout-sec": "300",
}

TTS_URL = "wss://api.vachana.ai/api/v1/tts"
TTS_HEADERS = {"X-API-Key-ID": KEY}
TTS_VOICE = "Shivani"
SAMPLE_RATE = 16000

DISCLOSURE = get_intro_message("hi-en")


def _get_stt_headers() -> Dict[str, Optional[str]]:
    headers = dict(STT_HEADERS)
    headers["x-api-key-id"] = os.getenv("GNANI_API_KEY") or KEY
    return headers


def _get_tts_headers() -> Dict[str, Optional[str]]:
    headers = dict(TTS_HEADERS)
    headers["X-API-Key-ID"] = os.getenv("GNANI_API_KEY") or KEY
    return headers


def _scrub_voice_error(exc: Exception) -> str:
    return scrub_secrets(
        str(exc),
        [os.getenv("GNANI_API_KEY"), KEY, os.getenv("LLM_API_KEY")],
    )


async def speak(browser: WebSocket, text: str, language: str = "auto"):
    await browser.send_text(json.dumps({"type": "tts_start"}))
    try:
        async with websockets.connect(
            TTS_URL, additional_headers=_get_tts_headers()
        ) as tts:
            await tts.send(json.dumps({
                "text": text,
                "voice": TTS_VOICE,
                "model": "timbre-v3.0",
                "language": language or "auto",
                "speed": 1.0,
                "audio_config": {
                    "sample_rate": SAMPLE_RATE,
                    "num_channels": 1,
                    "sample_width": 2,
                    "encoding": "linear_pcm",
                    "container": "raw",
                },
            }))
            async for raw in tts:
                msg = json.loads(raw)
                kind = msg.get("type")
                if kind == "audio":
                    audio = base64.b64decode(msg["data"]["audio"])
                    if audio:
                        await browser.send_bytes(audio)
                elif kind == "error":
                    safe_tts_err = scrub_secrets(
                        str(msg.get("message") or "TTS error"),
                        [os.getenv("GNANI_API_KEY"), KEY],
                    )
                    logger.warning("TTS error: %s", safe_tts_err)
                    break
                elif kind == "complete":
                    break
    except Exception as e:
        logger.warning("speak error: %s", _scrub_voice_error(e))
    finally:
        try:
            await browser.send_text(json.dumps({"type": "tts_end"}))
        except Exception:
            pass


def create_voice_app(
    settings: Optional[Settings] = None,
    llm_client: Optional[BaseLLMClient] = None,
) -> FastAPI:
    """Create the integrated ASHA-SAATHI voice + AI Brain FastAPI server."""
    if settings is not None or llm_client is not None:
        brain_app = configure_brain_app(settings=settings, llm_client=llm_client)
    else:
        brain_app = get_brain_app()

    voice_app = FastAPI(
        title="ASHA Saathi – Integrated Voice & AI Brain Server",
        version="2.0.0",
    )
    voice_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    voice_app.include_router(brain_app.router)
    register_exception_handlers(voice_app, brain_app.state.settings)
    voice_app.state.brain_app = brain_app
    voice_app.state.state_manager = brain_app.state.state_manager
    voice_app.state.settings = brain_app.state.settings

    @voice_app.get("/")
    async def index():
        return FileResponse(VOICE_DIR / "index.html")

    @voice_app.websocket("/ws")
    async def ws_endpoint(browser: WebSocket):
        await browser.accept()
        state = {"task": None}
        session = {}

        def stop_speaking():
            t = state["task"]
            if t and not t.done():
                t.cancel()

        def start_speaking(text: str, language: str = "auto"):
            stop_speaking()
            state["task"] = asyncio.create_task(
                speak(browser, text, language=language)
            )

        try:
            async with websockets.connect(
                STT_URL, additional_headers=_get_stt_headers()
            ) as gnani:

                async def up():  # browser -> server
                    while True:
                        msg = await browser.receive()
                        if msg["type"] == "websocket.disconnect":
                            return
                        if msg.get("bytes") is not None:
                            await gnani.send(msg["bytes"])
                        else:
                            text = msg.get("text") or ""
                            if '"commit"' in text:
                                await gnani.send(text)
                            elif '"hello"' in text:
                                try:
                                    payload = json.loads(text)
                                except Exception:
                                    payload = {}
                                intro_lang = (
                                    payload.get("language")
                                    or session.get("language")
                                    or "hi-en"
                                )
                                intro_tts_lang = payload.get("language_code") or "auto"
                                start_speaking(
                                    get_intro_message(intro_lang),
                                    language=intro_tts_lang,
                                )
                            elif '"interrupt"' in text:
                                stop_speaking()
                            elif '"language"' in text or '"preferred_language"' in text:
                                try:
                                    payload = json.loads(text)
                                except Exception:
                                    payload = {}
                                pref = (
                                    payload.get("preferred_language")
                                    or payload.get("language")
                                )
                                if isinstance(pref, str) and pref.strip():
                                    cleaned_pref = pref.strip()
                                    session["preferred_language"] = cleaned_pref
                                    sid = session.get("session_id")
                                    if sid and get_state_manager().get_session(sid):
                                        try:
                                            get_state_manager().set_session_language(
                                                sid, cleaned_pref
                                            )
                                            session["language"] = cleaned_pref
                                        except ValueError:
                                            pass

                async def down():  # Gnani STT -> browser (+ AI Brain reply)
                    async for raw in gnani:
                        await browser.send_text(raw)
                        try:
                            m = json.loads(raw)
                        except Exception:
                            continue
                        transcript_text = m.get("text", "")
                        if m.get("type") == "transcript" and transcript_text.strip():
                            det_lang = (
                                m.get("detected_language")
                                or m.get("language")
                                or m.get("language_code")
                            )
                            t0 = time.perf_counter()
                            try:
                                result = await asyncio.to_thread(
                                    on_transcript,
                                    transcript_text,
                                    session,
                                    detected_language=det_lang,
                                )
                            except (LLMProviderError, ExtractionValidationError, Exception) as exc:
                                safe_err = _scrub_voice_error(exc)
                                logger.warning("Brain turn failed over /ws: %s", safe_err)
                                await browser.send_text(json.dumps({
                                    "type": "error",
                                    "message": safe_err,
                                }))
                                continue
                            brain_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                            await browser.send_text(json.dumps({
                                "type": "brain",
                                "session_id": result.get("session_id"),
                                "reply_text": result.get("reply_text"),
                                "text_to_speak": result.get("text_to_speak"),
                                "action": result.get("action"),
                                "language": result.get("language"),
                                "detected_language": result.get("detected_language"),
                                "language_code": result.get("language_code"),
                                "language_switched": result.get(
                                    "language_switched", False
                                ),
                                "latency_ms": brain_latency_ms,
                                "form_state": result.get("form_state"),
                                "missing_fields": result.get("missing_fields", []),
                                "danger_flag": result.get("danger_flag", False),
                                "danger_detected": result.get("danger_detected", False),
                                "danger_flags": result.get("danger_flags", []),
                                "confirmation_state": result.get("confirmation_state"),
                                "confirmation_required": result.get(
                                    "confirmation_required", False
                                ),
                                "confirmed": result.get("confirmed", False),
                                "confirmed_record": result.get("confirmed_record"),
                                "follow_up_date": result.get("follow_up_date"),
                                "vaccinations": result.get("vaccinations", {}),
                                "next_actions": result.get("next_actions", []),
                                "tts_metadata": result.get("tts_metadata", {}),
                                "guardrail_triggered": result.get(
                                    "guardrail_triggered", False
                                ),
                            }))
                            start_speaking(
                                result["text_to_speak"],
                                language=result.get("language_code") or "auto",
                            )

                tasks = [asyncio.create_task(up()), asyncio.create_task(down())]
                _, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
        except Exception as e:
            safe_err = _scrub_voice_error(e)
            logger.warning("Voice WebSocket session error: %s", safe_err)
            try:
                await browser.send_text(json.dumps({
                    "type": "error",
                    "message": safe_err,
                }))
            except Exception:
                pass
        finally:
            stop_speaking()

    return voice_app


app = create_voice_app()
