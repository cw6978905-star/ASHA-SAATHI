import asyncio
import base64
import json
import os

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse

load_dotenv()
KEY = os.getenv("GNANI_API_KEY")

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

DISCLOSURE = "नमस्ते, मैं एक एआई असिस्टेंट हूँ। अपना विज़िट नोट बोलिए।"


from brain import on_transcript


app = FastAPI()


@app.get("/")
async def index():
    return FileResponse("index.html")


async def speak(browser, text):
    await browser.send_text(json.dumps({"type": "tts_start"}))
    try:
        async with websockets.connect(
            TTS_URL, additional_headers=TTS_HEADERS
        ) as tts:
            await tts.send(json.dumps({
                "text": text,
                "voice": TTS_VOICE,
                "model": "timbre-v3.0",
                "language": "auto",
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
                    print("TTS error:", msg.get("message"))
                    break
                elif kind == "complete":
                    break
    except Exception as e:
        print("speak error:", e)
    finally:
        try:
            await browser.send_text(json.dumps({"type": "tts_end"}))
        except Exception:
            pass


@app.websocket("/ws")
async def ws_endpoint(browser: WebSocket):
    await browser.accept()
    state = {"task": None}
    session = {}

    def stop_speaking():
        t = state["task"]
        if t and not t.done():
            t.cancel()

    def start_speaking(text):
        stop_speaking()
        state["task"] = asyncio.create_task(speak(browser, text))

    try:
        async with websockets.connect(
            STT_URL, additional_headers=STT_HEADERS
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
                            start_speaking(DISCLOSURE)
                        elif '"interrupt"' in text:
                            stop_speaking()

            async def down():  # Gnani STT -> browser (+ reply)
                async for raw in gnani:
                    await browser.send_text(raw)
                    try:
                        m = json.loads(raw)
                    except Exception:
                        continue
                    if m.get("type") == "transcript" and m.get("text", "").strip():
                                                result = await asyncio.to_thread(on_transcript, m["text"], session)
                                                await browser.send_text(json.dumps({
                                                 "type": "brain",
                                                 "form_state": result.get("form_state"),
                                                 "danger_flag": result.get("danger_flag", False),
                                                }))
                                                start_speaking(result["text_to_speak"])

            tasks = [asyncio.create_task(up()), asyncio.create_task(down())]
            _, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
    except Exception as e:
        print("session error:", e)