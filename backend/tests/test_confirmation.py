"""Tests for Module 4 (Read-Back & Confirmation) and Module 7 (FastAPI Endpoints)."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from brain.readback import generate_readback
from brain.state_manager import FormStateManager
from models.visit_schema import VisitRecord


def test_readback_includes_all_fields_and_missing_notice() -> None:
    rec = VisitRecord(
        beneficiary_name="Priya Devi",
        visit_type="newborn",
        weight_kg=2.8,
        vaccinations={"BCG": "completed"},
        next_visit_date=date(2026, 11, 17),
        missing_fields=["beneficiary_id"],
    )
    rb = generate_readback(rec, language="hi-en")
    assert "Priya Devi ka newborn visit record:" in rb
    assert "Weight 2.8 kilo hai." in rb
    assert "BCG vaccination complete hai." in rb
    assert "Next visit 17 November hai." in rb
    assert "Missing fields: Beneficiary ID." in rb
    assert "Kya main record save kar doon?" in rb


def test_confirmation_reject_and_pre_save_correction_flow(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = "sess_conf_1"
    state_manager.process_transcript(
        sid,
        "Aaj maine Priya Devi ka newborn checkup kiya. Beneficiary ID P-102. Baby ka weight do point aath kilo hai. BCG vaccination ho gaya hai. Next visit agle Mangalvar ko hai.",
        language="hi-en",
        visit_date=anchor_date,
    )

    # Worker rejects saving
    rej = state_manager.confirm_session(sid, transcript="Nahi, mat save karo", language="hi-en")
    assert rej.confirmed is False
    assert rej.ready_for_storage is False
    assert rej.confirmed_record is None

    # Worker corrects weight right before confirmation
    corr_conf = state_manager.confirm_session(
        sid, transcript="Nahi, weight 3.0 kilo hai", language="hi-en", visit_date=anchor_date
    )
    assert corr_conf.confirmed is False
    assert corr_conf.confirmation_required is True
    assert corr_conf.form_state["weight_kg"] == 3.0
    assert "Weight 3 kilo hai." in corr_conf.readback_text

    # Worker explicitly confirms
    ok = state_manager.confirm_session(sid, transcript="Haan, save kar do", language="hi-en")
    assert ok.confirmed is True
    assert ok.ready_for_storage is True
    assert ok.confirmed_record is not None
    assert ok.confirmed_record["visit_record"]["weight_kg"] == 3.0
    assert ok.confirmed_record["visit_record"]["beneficiary_id"] == "P-102"


def test_fastapi_endpoints_end_to_end(test_app) -> None:
    client = TestClient(test_app)

    # Health & intro endpoints
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["pending_person_c_verification"] is True

    intro = client.get("/api/brain/intro", params={"language": "hi-en"})
    assert intro.status_code == 200
    assert "ASHA Saathi" in intro.json()["intro_text"]

    # Process Turn 1
    p1 = client.post(
        "/api/brain/process",
        json={
            "session_id": "api_sess_001",
            "transcript": "Aaj maine Priya Devi ka newborn checkup kiya. Baby ka weight do point aath kilo hai. BCG vaccination ho gaya hai. Next visit agle Mangalvar ko hai.",
            "language": "hi-en",
            "visit_date": "2026-11-11",
        },
    )
    assert p1.status_code == 200
    d1 = p1.json()
    assert d1["form_state"]["weight_kg"] == 2.8
    assert d1["missing_fields"] == ["beneficiary_id"]
    assert d1["danger_detected"] is False
    assert d1["confirmed"] is False

    # Process Turn 2: supply missing ID -> triggers read-back
    p2 = client.post(
        "/api/brain/process",
        json={
            "session_id": "api_sess_001",
            "transcript": "Beneficiary ID P ek shunya do.",
            "language": "hi-en",
            "visit_date": "2026-11-11",
        },
    )
    assert p2.status_code == 200
    d2 = p2.json()
    assert d2["form_state"]["beneficiary_id"] == "P-102"
    assert d2["missing_fields"] == []
    assert d2["confirmation_required"] is True

    # Explicit voice correction endpoint
    corr = client.post(
        "/api/brain/correct",
        json={
            "session_id": "api_sess_001",
            "transcript": "No, weight is 3.1 kilo.",
            "language": "hi-en",
            "visit_date": "2026-11-11",
        },
    )
    assert corr.status_code == 200
    assert corr.json()["correction_applied"] is True
    assert corr.json()["form_state"]["weight_kg"] == 3.1
    assert corr.json()["confirmed"] is False

    # Readback endpoint
    rb = client.post(
        "/api/brain/readback",
        json={"session_id": "api_sess_001", "language": "en"},
    )
    assert rb.status_code == 200
    assert "3.1 kg" in rb.json()["readback_text"]

    # Confirm endpoint
    conf = client.post(
        "/api/brain/confirm",
        json={
            "session_id": "api_sess_001",
            "transcript": "Yes, save it",
            "language": "en",
        },
    )
    assert conf.status_code == 200
    assert conf.json()["confirmed"] is True
    assert conf.json()["ready_for_storage"] is True
    assert conf.json()["confirmed_record"]["visit_record"]["weight_kg"] == 3.1

    # Get session state
    get_res = client.get("/api/brain/session/api_sess_001")
    assert get_res.status_code == 200
    assert get_res.json()["confirmed"] is True

    # Delete session state
    del_res = client.delete("/api/brain/session/api_sess_001")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Confirm 404 after delete
    missing = client.get("/api/brain/session/api_sess_001")
    assert missing.status_code == 404
