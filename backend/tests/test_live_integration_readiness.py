"""Live LLM HTTP transport, fail-closed config, clinical review, and 10-step E2E readiness tests."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from brain.llm_client import (
    AnthropicLLMClient,
    GeminiLLMClient,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    OpenAICompatibleLLMClient,
    create_llm_client,
)
from config import Settings, load_settings
from main import create_app
from voice import server as voice_server


def _patch_httpx_transport(handler):
    real_client_cls = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    return patch("brain.llm_client.httpx.Client", side_effect=client_factory)


def test_real_providers_refuse_silent_fallback_without_credentials() -> None:
    for provider in ("openai", "openai_compatible", "gemini", "anthropic"):
        with pytest.raises(LLMConfigurationError):
            create_llm_client(Settings(llm_provider=provider, llm_api_key=None, llm_model="gpt-4o-mini"))
        with pytest.raises(LLMConfigurationError):
            create_llm_client(Settings(llm_provider=provider, llm_api_key="test-key-123456", llm_model=None))

    # Strict production enforcement disables mock/auto silent fallback too
    with pytest.raises(LLMConfigurationError):
        create_llm_client(Settings(llm_provider="mock", require_real_llm=True))
    with pytest.raises(LLMConfigurationError):
        create_llm_client(Settings(llm_provider="auto", require_real_llm=True))


def test_provider_switching_from_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestSecretKeyForUnitTest999")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("REQUIRE_REAL_LLM", raising=False)

    cfg = load_settings()
    client = create_llm_client(cfg)
    assert isinstance(client, GeminiLLMClient)
    assert client.provider_name == "gemini"

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret-123456789")
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-sonnet-latest")
    cfg2 = load_settings()
    client2 = create_llm_client(cfg2)
    assert isinstance(client2, AnthropicLLMClient)


def test_real_http_providers_extraction_repair_danger_and_no_secret_leak(
    danger_signs_path: Path, caplog
) -> None:
    openai_secret = "sk-live-super-secret-token-99999"
    gemini_secret = "AIzaSySecretGeminiToken99999"
    anthropic_secret = "sk-ant-secret-token-99999"

    captured_requests: List[httpx.Request] = []
    attempt_counter = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        url_str = str(request.url)
        assert openai_secret not in url_str
        assert gemini_secret not in url_str
        assert anthropic_secret not in url_str

        attempt_counter["count"] += 1
        # Simulate Gemini returning malformed JSON first, then valid schema on retry repair
        if "generativelanguage.googleapis.com" in url_str:
            assert request.headers.get("x-goog-api-key") == gemini_secret
            body_text = request.content.decode("utf-8")
            if "Predefined Danger Signs Catalog" in body_text:
                return httpx.Response(200, json={
                    "candidates": [{"content": {"parts": [{"text": json.dumps({
                        "danger_detected": True,
                        "matches": [{
                            "danger_sign_id": "unconsciousness_lethargy",
                            "evidence": "baccha respond nahi kar raha",
                            "reason": "Lethargy/unresponsiveness",
                            "ambiguous": False,
                        }],
                    })}]}}]
                })
            if attempt_counter["count"] == 1:
                return httpx.Response(200, json={
                    "candidates": [{"content": {"parts": [{"text": "{bad-json"}]}}]
                })
            return httpx.Response(200, json={
                "candidates": [{"content": {"parts": [
                    {"thought": True, "text": "thinking..."},
                    {"text": json.dumps({
                        "beneficiary_name": "Kavita Devi",
                        "beneficiary_id": "K-108",
                        "visit_type": "anc",
                        "weight_kg": 56.5,
                        "blood_pressure": {"systolic": 118, "diastolic": 78, "raw_text": "118/78"},
                        "ifa_status": "provided",
                        "next_visit_date": "2026-11-18",
                    })},
                ]}}]
            })

        if "api.anthropic.com" in url_str:
            assert request.headers.get("x-api-key") == anthropic_secret
            return httpx.Response(200, json={
                "content": [{"type": "text", "text": json.dumps({
                    "danger_detected": False, "matches": []
                })}]
            })

        # OpenAI-compatible default
        assert request.headers.get("authorization") == f"Bearer {openai_secret}"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({
                "beneficiary_name": "மீனா",
                "visit_type": "newborn",
                "weight_kg": 3.1,
            })}}]
        })

    with _patch_httpx_transport(handler):
        # 1. Gemini end-to-end through create_app (repair + extraction + danger OR-logic)
        gem_app = create_app(Settings(
            llm_provider="gemini",
            llm_api_key=gemini_secret,
            llm_model="models/gemini-2.5-flash",
            danger_signs_path=danger_signs_path,
            allow_deterministic_fallback=False,
        ))
        from config import scrub_secrets
        assert "FakeTestDummyToken" not in scrub_secrets("Header AQ.FakeTestDummyToken99999 failed")
        gem_client = TestClient(gem_app)
        assert gem_client.get("/health").json()["llm_mode"] == "live"

        with caplog.at_level(logging.DEBUG, logger="asha_saathi"):
            res = gem_client.post("/api/brain/process", json={
                "session_id": "gem_live_1",
                "transcript": "Kavita Devi ANC checkup ID K-108 weight 56.5 kilo, baccha respond nahi kar raha",
                "language": "hi-en",
                "visit_date": "2026-11-11",
            })
        assert res.status_code == 200
        body = res.json()
        assert body["form_state"]["beneficiary_name"] == "Kavita Devi"
        assert body["form_state"]["weight_kg"] == 56.5
        assert body["danger_detected"] is True
        assert any(f["danger_sign_id"] == "unconsciousness_lethargy" for f in body["danger_flags"])

        # 2. Direct OpenAI-compatible client (Tamil response JSON) & Anthropic client
        oai = OpenAICompatibleLLMClient(api_key=openai_secret, model="gpt-4o-mini")
        out_oai = json.loads(oai.complete_json("sys", "usr"))
        assert out_oai["beneficiary_name"] == "மீனா"

        ant = AnthropicLLMClient(api_key=anthropic_secret, model="claude-3-5-sonnet-latest")
        out_ant = json.loads(ant.complete_json("sys", "usr"))
        assert out_ant["danger_detected"] is False

    logs_combined = " ".join(r.getMessage() for r in caplog.records)
    assert openai_secret not in logs_combined
    assert gemini_secret not in logs_combined
    assert anthropic_secret not in logs_combined


def test_real_llm_error_handling_timeouts_rate_limits_and_no_silent_mock_fallback(
    danger_signs_path: Path,
) -> None:
    secret_key = "sk-live-never-expose-77777"

    # Case A: Persistent HTTP 429 -> raises LLMRateLimitError & maps to HTTP 429 without secret leak
    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0.05"}, json={"error": "rate limit"})

    with _patch_httpx_transport(rate_limit_handler):
        app_429 = create_app(Settings(
            llm_provider="openai_compatible",
            llm_api_key=secret_key,
            llm_model="gpt-4o-mini",
            danger_signs_path=danger_signs_path,
        ))
        client_429 = TestClient(app_429)
        r429 = client_429.post("/api/brain/process", json={
            "session_id": "err_429",
            "transcript": "Priya Devi weight 54 kilo",
        })
        assert r429.status_code == 429
        assert secret_key not in r429.text

    # Case B: Timeout -> raises LLMTimeoutError & maps to HTTP 504 cleanly
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out reading from upstream")

    with _patch_httpx_transport(timeout_handler):
        app_to = create_app(Settings(
            llm_provider="openai_compatible",
            llm_api_key=secret_key,
            llm_model="gpt-4o-mini",
            danger_signs_path=danger_signs_path,
        ))
        client_to = TestClient(app_to)
        r_to = client_to.post("/api/brain/process", json={
            "session_id": "err_timeout",
            "transcript": "Priya Devi weight 54 kilo",
        })
        assert r_to.status_code == 504
        assert secret_key not in r_to.text

    # Case C: Auth 401 -> maps to HTTP 502 with secret scrubbed
    def auth_fail_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": f"invalid key {secret_key}"})

    with _patch_httpx_transport(auth_fail_handler):
        app_auth = create_app(Settings(
            llm_provider="openai_compatible",
            llm_api_key=secret_key,
            llm_model="gpt-4o-mini",
            danger_signs_path=danger_signs_path,
        ))
        client_auth = TestClient(app_auth)
        r_auth = client_auth.post("/api/brain/process", json={
            "session_id": "err_auth",
            "transcript": "Priya Devi weight 54 kilo",
        })
        assert r_auth.status_code == 502
        assert secret_key not in r_auth.text


def test_complete_10_step_e2e_voice_session_isolation_switch_error_and_delete(
    danger_signs_path: Path,
) -> None:
    from brain.llm_client import MockLLMClient

    settings = Settings(
        llm_provider="mock",
        danger_signs_path=danger_signs_path,
        app_timezone="Asia/Kolkata",
    )
    app = voice_server.create_voice_app(settings=settings, llm_client=MockLLMClient())
    client = TestClient(app)

    # Verify concurrent REST session remains isolated
    s_other = client.post("/api/brain/process", json={
        "session_id": "isolated_rest_session",
        "transcript": "Sita Devi ka PNC checkup kiya, weight 49 kilo.",
        "language": "hi-en",
        "visit_date": "2026-11-11",
    })
    assert s_other.status_code == 200
    assert s_other.json()["form_state"]["beneficiary_name"] == "Sita Devi"

    stt_state: Dict[str, Any] = {"queue": None, "loop": None}
    tts_requests: List[Dict[str, Any]] = []

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
            return None

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
                    "data": {"audio": base64.b64encode(b"PCM").decode("ascii")},
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

    def drain_tts() -> None:
        assert json.loads(ws.receive_text()) == {"type": "tts_start"}
        assert ws.receive_bytes() == b"PCM"
        assert json.loads(ws.receive_text()) == {"type": "tts_end"}

    with patch.object(voice_server.websockets, "connect", side_effect=fake_connect):
        with client.websocket_connect("/ws") as ws:
            # Step 1: Start voice session
            ws.send_text('{"type":"hello"}')
            drain_tts()

            # Step 2-4: STT delivers ANC note -> Brain extracts & asks for missing field
            push_stt({
                "type": "transcript",
                "text": "Aaj maine Radha Devi ka ANC checkup kiya, weight 53 kilo hai.",
                "detected_language": "hi-en",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            b1 = json.loads(ws.receive_text())
            assert b1["form_state"]["beneficiary_name"] == "Radha Devi"
            assert b1["form_state"]["visit_type"] == "anc"
            assert b1["form_state"]["weight_kg"] == 53.0
            assert "beneficiary_id" in b1["missing_fields"]
            assert isinstance(b1["latency_ms"], float)
            sid = b1["session_id"]
            drain_tts()

            # Test barge-in interrupt command safely accepted
            ws.send_text('{"type":"interrupt"}')

            # Step 5: Provide remaining fields
            push_stt({
                "type": "transcript",
                "text": "ID R-505, BP 120/80 hai, IFA goli di hai, next visit agle Mangalvar ko hai.",
                "detected_language": "hi-en",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            b2 = json.loads(ws.receive_text())
            assert b2["missing_fields"] == []
            assert b2["confirmation_state"] == "awaiting_confirmation"
            assert b2["confirmed"] is False
            drain_tts()

            # Step 6: Spoken correction updates weight without clearing existing fields
            push_stt({
                "type": "transcript",
                "text": "Weight 53 nahi 55 kilo karo.",
                "detected_language": "hi-en",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            b3 = json.loads(ws.receive_text())
            assert b3["form_state"]["weight_kg"] == 55.0
            assert b3["form_state"]["beneficiary_id"] == "R-505"
            assert b3["confirmed"] is False
            drain_tts()

            # Step 7: Danger sign turn flagged via OR-logic and persisted
            push_stt({
                "type": "transcript",
                "text": "Unko heavy bleeding ho rahi hai.",
                "detected_language": "hi-en",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            b4 = json.loads(ws.receive_text())
            assert b4["danger_flag"] is True
            assert b4["action"] == "refer_danger"
            drain_tts()

            # Language switch over WebSocket preserves all fields & danger flags
            ws.send_text('{"type":"language","language":"en-IN"}')
            push_stt({
                "type": "transcript",
                "text": "Readback",
                "detected_language": "en-IN",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            b5 = json.loads(ws.receive_text())
            assert b5["language"] == "en-IN"
            assert b5["form_state"]["weight_kg"] == 55.0
            assert b5["danger_flag"] is True
            drain_tts()

            # Step 8-10: Explicit readback request + explicit yes confirmation -> Person C payload
            rb_resp = client.post("/api/brain/readback", json={"session_id": sid, "language": "en-IN"})
            assert rb_resp.status_code == 200
            assert rb_resp.json()["confirmation_required"] is True

            push_stt({
                "type": "transcript",
                "text": "Yes, save it.",
                "detected_language": "en-IN",
            })
            assert json.loads(ws.receive_text())["type"] == "transcript"
            b6 = json.loads(ws.receive_text())
            assert b6["confirmed"] is True
            assert b6["confirmation_state"] == "confirmed"
            assert b6["confirmed_record"]["confirmed"] is True
            assert b6["confirmed_record"]["danger_detected"] is True
            assert b6["confirmed_record"]["visit_record"]["beneficiary_name"] == "Radha Devi"
            assert b6["confirmed_record"]["visit_record"]["weight_kg"] == 55.0
            drain_tts()

            # Verify runtime error inside on_transcript sends WS error without closing socket
            with patch.object(voice_server, "on_transcript", side_effect=LLMTimeoutError("Upstream timed out")):
                push_stt({"type": "transcript", "text": "test timeout", "detected_language": "en-IN"})
                assert json.loads(ws.receive_text())["type"] == "transcript"
                err_msg = json.loads(ws.receive_text())
                assert err_msg["type"] == "error"
                assert "timed out" in err_msg["message"].lower()

            push_stt(None)

    # Verify session isolation & deletion
    other_state = client.get("/api/brain/session/isolated_rest_session")
    assert other_state.status_code == 200
    assert other_state.json()["form_state"]["beneficiary_name"] == "Sita Devi"

    deleted = client.delete(f"/api/brain/session/{sid}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/brain/session/{sid}").status_code == 404


def test_clinical_review_register_and_all_12_entries_pending_approval(
    danger_signs_path: Path,
) -> None:
    review_doc = (danger_signs_path.parent.parent / "CLINICAL_DANGER_SIGNS_REVIEW.md").read_text(encoding="utf-8")
    raw_catalog = json.loads(danger_signs_path.read_text(encoding="utf-8"))
    entries = raw_catalog["danger_signs"]

    assert len(entries) == 12
    assert raw_catalog["metadata"]["pending_person_c_verification"] is True
    assert raw_catalog["metadata"]["verification_status"] == "preliminary_pending_person_c_verification"

    for entry in entries:
        assert entry["source_reference"] == "PENDING_PERSON_C_VERIFICATION"
        assert entry["id"] in review_doc
        assert entry["english_name"] in review_doc
