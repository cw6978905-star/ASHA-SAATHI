"""End-to-end integration tests for Person B AI Brain <-> Person A voice pipeline."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
VOICE_DIR = REPO_ROOT / "voice"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from brain.llm_client import MockLLMClient  # noqa: E402
from config import Settings  # noqa: E402
from voice import brain as voice_brain  # noqa: E402
from voice import server as voice_server  # noqa: E402


@pytest.fixture
def isolated_voice_brain(danger_signs_path: Path):
    """Configure a fresh isolated brain app with MockLLMClient per test."""
    settings = Settings(
        llm_provider="mock",
        danger_signs_path=danger_signs_path,
        app_timezone="Asia/Kolkata",
    )
    voice_brain.configure_brain_app(settings=settings, llm_client=MockLLMClient())
    return voice_brain


def test_voice_brain_never_echoes_and_completes_multiturn_anc_flow(
    isolated_voice_brain, anchor_date: date
) -> None:
    session: Dict[str, Any] = {"visit_date": anchor_date}

    # Turn 1: ANC visit + name
    r1 = isolated_voice_brain.on_transcript(
        "Aaj maine Priya Devi ka ANC checkup kiya.", session
    )
    assert "मैंने सुना:" not in r1["reply_text"]
    assert r1["text_to_speak"] == r1["reply_text"]
    assert r1["form_state"]["beneficiary_name"] == "Priya Devi"
    assert r1["form_state"]["visit_type"] == "anc"
    assert "weight_kg" in r1["missing_fields"]
    assert r1["danger_flag"] is False
    assert r1["confirmation_state"] == "collecting"

    # Turn 2: Bare numeric weight reply
    r2 = isolated_voice_brain.on_transcript("Weight 54 kilo hai.", session)
    assert r2["form_state"]["weight_kg"] == 54.0
    assert "weight_kg" not in r2["missing_fields"]
    assert "beneficiary_id" in r2["missing_fields"]

    # Turn 3: Remaining required ANC fields -> triggers readback & awaiting_confirmation
    r3 = isolated_voice_brain.on_transcript(
        "ID P-102, BP 120/80 hai, IFA goli di hai, next visit agle Mangalvar ko hai.",
        session,
    )
    assert r3["missing_fields"] == []
    assert r3["follow_up_date"] == "2026-11-17"
    assert r3["confirmation_required"] is True
    assert r3["confirmation_state"] == "awaiting_confirmation"
    assert r3["confirmed"] is False
    assert "Priya Devi" in r3["reply_text"]

    # Turn 4: Reject save
    r4 = isolated_voice_brain.on_transcript("Nahi, ruko.", session)
    assert r4["confirmed"] is False
    assert r4["confirmed_record"] is None

    # Turn 5: Voice correction updates weight without losing existing fields
    r5 = isolated_voice_brain.on_transcript(
        "Weight 54 nahi 56 kilo karo.", session
    )
    assert r5["form_state"]["weight_kg"] == 56.0
    assert r5["form_state"]["beneficiary_name"] == "Priya Devi"
    assert r5["confirmation_state"] == "awaiting_confirmation"

    # Turn 6: Explicit confirmation produces Person C confirmed record payload
    r6 = isolated_voice_brain.on_transcript("Haan save kar do.", session)
    assert r6["confirmed"] is True
    assert r6["confirmation_state"] == "confirmed"
    assert r6["confirmed_record"] is not None
    assert r6["confirmed_record"]["confirmed"] is True
    assert r6["confirmed_record"]["visit_record"]["beneficiary_name"] == "Priya Devi"
    assert r6["confirmed_record"]["visit_record"]["weight_kg"] == 56.0


def test_voice_brain_danger_sign_persists_across_subsequent_turns(
    isolated_voice_brain, anchor_date: date
) -> None:
    session: Dict[str, Any] = {"visit_date": anchor_date}

    # Turn 1: Danger symptom reported
    r1 = isolated_voice_brain.on_transcript(
        "Sunita ko tez heavy bleeding ho rahi hai.", session
    )
    assert r1["danger_flag"] is True
    assert r1["danger_detected"] is True
    assert len(r1["danger_flags"]) >= 1
    assert r1["action"] == "refer_danger"
    assert r1["danger_flags"][0]["source_reference"] == "PENDING_PERSON_C_VERIFICATION"

    # Turn 2: Routine follow-up data must NOT clear existing danger state
    r2 = isolated_voice_brain.on_transcript(
        "Weight 50 kilo hai, ID S-204.", session
    )
    assert r2["danger_flag"] is True
    assert r2["danger_detected"] is True
    assert len(r2["danger_flags"]) >= 1
    assert session["danger_flag"] is True


def test_voice_brain_medical_guardrail_and_session_isolation(
    isolated_voice_brain, anchor_date: date
) -> None:
    sess_a: Dict[str, Any] = {"visit_date": anchor_date}
    sess_b: Dict[str, Any] = {"visit_date": anchor_date}

    ra = isolated_voice_brain.on_transcript(
        "Maine Priya Devi ka ANC checkup kiya, weight 55 kilo hai.", sess_a
    )
    rb_guardrail = isolated_voice_brain.on_transcript(
        "Kaunsi medicine deni chahiye aur kitni dose mg batao?", sess_b
    )

    assert rb_guardrail["guardrail_triggered"] is True
    assert rb_guardrail["action"] == "refuse_medical_advice"
    assert rb_guardrail["form_state"]["beneficiary_name"] is None
    assert ra["form_state"]["beneficiary_name"] == "Priya Devi"
    assert sess_a["session_id"] != sess_b["session_id"]


def test_voice_brain_multilingual_detection_and_mid_conversation_switch(
    isolated_voice_brain, anchor_date: date
) -> None:
    session: Dict[str, Any] = {"visit_date": anchor_date}

    # Turn 1: Auto language from Gnani STT detected_language="hi-IN" (ignoring "indic-auto" earlier)
    r1 = isolated_voice_brain.on_transcript(
        "Priya Devi का ANC चेकअप किया, वजन 55 किलो है।",
        session,
        detected_language="hi-IN",
    )
    assert r1["language"] == "hi-IN"
    assert r1["language_code"] == "hi-IN"
    assert r1["form_state"]["weight_kg"] == 55.0

    # Turn 2: Switch language mid-conversation while preserving captured form data
    r2 = isolated_voice_brain.on_transcript(
        "Tamil mein baat karo", session, detected_language="hi-en"
    )
    assert r2["language"] == "ta-IN"
    assert r2["language_code"] == "ta-IN"
    assert r2["language_switched"] is True
    assert r2["form_state"]["weight_kg"] == 55.0
    assert r2["form_state"]["beneficiary_name"] == "Priya Devi"

    # Verify Gnani's placeholder "indic-auto" never crashes sanitization
    r3 = isolated_voice_brain.on_transcript(
        "ID P-205", session, detected_language="indic-auto"
    )
    assert r3["language"] == "ta-IN"
    assert r3["form_state"]["beneficiary_id"] == "P-205"


def test_direct_brain_import_from_voice_directory_works_without_package_shadowing() -> None:
    script = (
        "from brain import on_transcript; "
        "s = {}; "
        "r = on_transcript('Maine Priya Devi ka ANC checkup kiya, weight 55 kilo hai', s); "
        "assert 'मैंने सुना:' not in r['reply_text']; "
        "assert r['form_state']['weight_kg'] == 55.0; "
        "assert r['form_state']['beneficiary_name'] == 'Priya Devi'; "
        "print('OK')"
    )
    env = {**os.environ, "LLM_PROVIDER": "mock"}
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(VOICE_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "OK" in proc.stdout


def test_voice_server_http_endpoints_and_index_html_clean(
    danger_signs_path: Path,
) -> None:
    settings = Settings(
        llm_provider="mock",
        danger_signs_path=danger_signs_path,
        app_timezone="Asia/Kolkata",
    )
    app = voice_server.create_voice_app(settings=settings, llm_client=MockLLMClient())
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    html = home.text
    assert html.count('id="banner"') == 1
    assert html.count('m.type === "brain"') == 1
    assert "m.reply_text" in html

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert len(health.json()["supported_languages"]) == 10

    langs = client.get("/api/brain/languages")
    assert langs.status_code == 200
    assert set(langs.json()["languages"].keys()) == {
        "hi-IN", "en-IN", "ta-IN", "te-IN", "bn-IN",
        "mr-IN", "gu-IN", "kn-IN", "ml-IN", "pa-IN",
    }


def test_voice_server_websocket_end_to_end_with_mocked_gnani(
    danger_signs_path: Path,
) -> None:
    settings = Settings(
        llm_provider="mock",
        danger_signs_path=danger_signs_path,
        app_timezone="Asia/Kolkata",
    )
    app = voice_server.create_voice_app(settings=settings, llm_client=MockLLMClient())
    client = TestClient(app)

    stt_state: Dict[str, Any] = {"queue": None, "loop": None, "ready": asyncio.Event}
    tts_requests: List[Dict[str, Any]] = []
    sent_commits: List[str] = []

    class FakeSTTConnection:
        def __init__(self) -> None:
            self.queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        async def __aenter__(self) -> "FakeSTTConnection":
            stt_state["queue"] = self.queue
            stt_state["loop"] = asyncio.get_running_loop()
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def send(self, data: Any) -> None:
            if isinstance(data, str):
                sent_commits.append(data)

        def __aiter__(self):
            return self

        async def __anext__(self) -> str:
            item = await self.queue.get()
            if item is None:
                raise StopAsyncIteration
            return item

    class FakeTTSConnection:
        def __init__(self) -> None:
            self._responses = iter([
                json.dumps({
                    "type": "audio",
                    "data": {"audio": base64.b64encode(b"\x01\x02\x03\x04").decode("ascii")},
                }),
                json.dumps({"type": "complete"}),
            ])

        async def __aenter__(self) -> "FakeTTSConnection":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def send(self, payload: str) -> None:
            tts_requests.append(json.loads(payload))

        def __aiter__(self):
            return self

        async def __anext__(self) -> str:
            try:
                return next(self._responses)
            except StopIteration:
                raise StopAsyncIteration

    def fake_connect(url: str, **kwargs):
        if url == voice_server.STT_URL:
            return FakeSTTConnection()
        if url == voice_server.TTS_URL:
            return FakeTTSConnection()
        raise AssertionError(f"Unexpected websocket URL: {url}")

    def push_stt(payload: Optional[Dict[str, Any]]) -> None:
        raw = None if payload is None else json.dumps(payload)
        stt_state["loop"].call_soon_threadsafe(stt_state["queue"].put_nowait, raw)

    with patch.object(voice_server.websockets, "connect", side_effect=fake_connect):
        with client.websocket_connect("/ws") as ws:
            # 1. Browser sends initial hello -> AI safety disclosure via TTS
            ws.send_text('{"type":"hello"}')
            assert json.loads(ws.receive_text()) == {"type": "tts_start"}
            assert ws.receive_bytes() == b"\x01\x02\x03\x04"
            assert json.loads(ws.receive_text()) == {"type": "tts_end"}
            assert "doctor nahi hoon" in tts_requests[-1]["text"]

            # 2. Browser commits -> forwarded to Gnani STT
            ws.send_text('{"type":"commit"}')

            # 3. Gnani STT delivers multilingual transcript -> Brain responds -> TTS speaks in bn-IN
            push_stt({
                "type": "transcript",
                "text": "মীরা দেবী এর নবজাতক পরীক্ষা। ওজন ৫২ কেজি।",
                "detected_language": "bn-IN",
            })
            raw_echo = json.loads(ws.receive_text())
            assert raw_echo["type"] == "transcript"

            brain_msg = json.loads(ws.receive_text())
            assert brain_msg["type"] == "brain"
            assert brain_msg["language"] == "bn-IN"
            assert brain_msg["language_code"] == "bn-IN"
            assert brain_msg["form_state"]["visit_type"] == "newborn"
            assert brain_msg["form_state"]["weight_kg"] == 52.0
            assert "beneficiary_id" in brain_msg["missing_fields"]
            assert brain_msg["danger_flag"] is False
            assert brain_msg["confirmation_state"] == "collecting"
            session_id = brain_msg["session_id"]

            assert json.loads(ws.receive_text()) == {"type": "tts_start"}
            assert ws.receive_bytes() == b"\x01\x02\x03\x04"
            assert json.loads(ws.receive_text()) == {"type": "tts_end"}
            assert tts_requests[-1]["language"] == "bn-IN"

            # 4. REST API shares the exact live session state created over WebSocket
            rest_state = client.get(f"/api/brain/session/{session_id}")
            assert rest_state.status_code == 200
            assert rest_state.json()["form_state"]["weight_kg"] == 52.0
            assert rest_state.json()["language"] == "bn-IN"

            # 5. Danger sign transcript triggers persistent banner & referral action
            push_stt({
                "type": "transcript",
                "text": "তীব্র রক্তপাত হচ্ছে।",
                "detected_language": "bn-IN",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            danger_msg = json.loads(ws.receive_text())
            assert danger_msg["danger_flag"] is True
            assert danger_msg["danger_detected"] is True
            assert danger_msg["action"] == "refer_danger"
            assert len(danger_msg["danger_flags"]) >= 1
            assert json.loads(ws.receive_text()) == {"type": "tts_start"}
            assert ws.receive_bytes() == b"\x01\x02\x03\x04"
            assert json.loads(ws.receive_text()) == {"type": "tts_end"}

            # 6. Subsequent non-danger turn preserves danger flag while completing remaining fields
            push_stt({
                "type": "transcript",
                "text": "ID B-404",
                "detected_language": "bn-IN",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            follow_msg = json.loads(ws.receive_text())
            assert follow_msg["danger_flag"] is True
            assert follow_msg["form_state"]["beneficiary_id"] == "B-404"
            assert json.loads(ws.receive_text()) == {"type": "tts_start"}
            assert ws.receive_bytes() == b"\x01\x02\x03\x04"
            assert json.loads(ws.receive_text()) == {"type": "tts_end"}

            push_stt(None)

    assert '{"type":"commit"}' in sent_commits
