"""Tests for Module 2: Multi-turn Form State Manager, missing fields, and beneficiary isolation."""

from __future__ import annotations

from datetime import date

from brain.state_manager import FormStateManager


def test_multi_turn_anc_form_completion_flow(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = "sess_anc_01"

    # Turn 1: Name + visit type
    r1 = state_manager.process_transcript(
        sid, "Maine Priya Devi ka ANC checkup kiya.", language="hi-en", visit_date=anchor_date
    )
    assert r1.form_state["beneficiary_name"] == "Priya Devi"
    assert r1.form_state["visit_type"] == "anc"
    assert "weight_kg" in r1.missing_fields
    assert "weight" in r1.reply_text.lower()
    assert r1.confirmation_required is False

    # Turn 2: Bare numeric weight reply
    r2 = state_manager.process_transcript(
        sid, "55 kilo.", language="hi-en", visit_date=anchor_date
    )
    assert r2.form_state["weight_kg"] == 55.0
    assert "weight_kg" not in r2.missing_fields
    assert "beneficiary_id" in r2.missing_fields
    assert "id" in r2.reply_text.lower()

    # Turn 3: Beneficiary ID
    r3 = state_manager.process_transcript(
        sid, "P-102.", language="hi-en", visit_date=anchor_date
    )
    assert r3.form_state["beneficiary_id"] == "P-102"
    assert "beneficiary_id" not in r3.missing_fields
    assert "blood_pressure" in r3.missing_fields

    # Turn 4: Remaining ANC fields (BP, IFA, Next Visit)
    r4 = state_manager.process_transcript(
        sid,
        "BP 120/80 hai, IFA goli di hai, next visit agle Mangalvar ko hai.",
        language="hi-en",
        visit_date=anchor_date,
    )
    assert r4.missing_fields == []
    assert r4.confirmation_required is True
    assert r4.action == "confirm_record"
    assert "Priya Devi" in r4.reply_text
    assert "55 kilo" in r4.reply_text
    assert "Kya main record save kar doon?" in r4.reply_text


def test_visit_type_specific_required_fields(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    # Immunisation visit does NOT require weight_kg or blood_pressure
    resp = state_manager.process_transcript(
        "sess_imm_01",
        "Aarav ka immunisation visit hai, beneficiary ID R-305, Pentavalent lag gaya, next visit 7 din baad.",
        language="hi-en",
        visit_date=anchor_date,
    )
    assert resp.visit_type == "immunisation"
    assert resp.missing_fields == []
    assert resp.confirmation_required is True


def test_newborn_missing_id_detection(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    resp = state_manager.process_transcript(
        "sess_nb_01",
        "Aaj maine Priya Devi ka newborn checkup kiya. Baby ka weight do point aath kilo hai. BCG vaccination ho gaya hai. Next visit agle Mangalvar ko hai.",
        language="hi-en",
        visit_date=anchor_date,
    )
    assert resp.form_state["weight_kg"] == 2.8
    assert resp.form_state["vaccinations"] == {"BCG": "completed"}
    assert resp.follow_up_date == "2026-11-17"
    assert resp.missing_fields == ["beneficiary_id"]
    assert resp.confirmation_required is False


def test_beneficiary_isolation_across_and_within_sessions(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    # Independent sessions stay strictly isolated
    state_manager.process_transcript(
        "sess_A", "Maine Priya Devi ka ANC checkup kiya. Weight 55 kilo.", visit_date=anchor_date
    )
    state_manager.process_transcript(
        "sess_B", "Maine Sunita Sharma ka newborn checkup kiya. Weight 2.9 kilo.", visit_date=anchor_date
    )
    s_a = state_manager.get_session_state_response("sess_A")
    s_b = state_manager.get_session_state_response("sess_B")
    assert s_a.beneficiary_info["name"] == "Priya Devi"
    assert s_a.form_state["weight_kg"] == 55.0
    assert s_b.beneficiary_info["name"] == "Sunita Sharma"
    assert s_b.form_state["weight_kg"] == 2.9

    # Cross-beneficiary mention inside sess_A must NOT overwrite Priya Devi's record
    conflict_resp = state_manager.process_transcript(
        "sess_A", "Ab Sunita Sharma ka newborn checkup karna hai, weight 3.1 kilo.", visit_date=anchor_date
    )
    assert conflict_resp.action == "clarify"
    assert conflict_resp.form_state["beneficiary_name"] == "Priya Devi"
    assert conflict_resp.form_state["weight_kg"] == 55.0


def test_unknown_field_does_not_loop_infinitely(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = "sess_unknown_id"
    state_manager.process_transcript(
        sid,
        "Aaj maine Priya Devi ka newborn checkup kiya. Baby ka weight 2.8 kilo hai. BCG ho gaya. Next visit agle Mangalvar ko hai.",
        visit_date=anchor_date,
    )
    r2 = state_manager.process_transcript(
        sid, "Beneficiary ID abhi pata nahi hai.", visit_date=anchor_date
    )
    # Missing field is still reported accurately as null/missing, while advancing to readback
    assert r2.form_state["beneficiary_id"] is None
    assert "beneficiary_id" in r2.missing_fields
    assert "beneficiary_id" in r2.form_state["unknown_fields"]
    assert r2.confirmation_required is True
    assert "Missing fields" in r2.reply_text
