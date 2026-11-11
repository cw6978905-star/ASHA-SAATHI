"""Tests for Module 3: Voice Correction System."""

from __future__ import annotations

from datetime import date

import pytest

from brain.state_manager import FormStateManager
from tests.synthetic_dataset import SYNTHETIC_CORRECTION_CASES


def test_single_field_correction_preserves_other_fields(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = "sess_corr_1"
    state_manager.process_transcript(
        sid,
        "Aaj maine Priya Devi ka newborn checkup kiya. Beneficiary ID P-102 hai. Baby ka weight 3.2 kilo hai. BCG ho gaya. Next visit agle Mangalvar ko hai.",
        visit_date=anchor_date,
    )
    r_corr = state_manager.process_transcript(
        sid, "No, weight is 2.8 kilo.", visit_date=anchor_date
    )
    assert r_corr.form_state["weight_kg"] == 2.8
    assert r_corr.form_state["beneficiary_name"] == "Priya Devi"
    assert r_corr.form_state["beneficiary_id"] == "P-102"
    assert r_corr.form_state["vaccinations"] == {"BCG": "completed"}
    assert r_corr.follow_up_date == "2026-11-17"


@pytest.mark.parametrize(
    "case",
    SYNTHETIC_CORRECTION_CASES,
    ids=[f"case_{c.case_id}_{c.label}" for c in SYNTHETIC_CORRECTION_CASES],
)
def test_synthetic_correction_cases(
    case, state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = f"sess_syn_corr_{case.case_id}"
    session = state_manager.get_or_create_session(sid)
    for k, v in case.initial_state.items():
        if k == "next_visit_date" and isinstance(v, str):
            setattr(session.record, k, date.fromisoformat(v))
        else:
            setattr(session.record, k, v)
    session.record.visit_date = anchor_date

    resp = state_manager.correct_session(
        sid, case.transcript, language="hi-en", visit_date=anchor_date
    )
    assert resp.correction_applied is case.expected_applied
    for field_k, expected_val in case.expected_fields.items():
        assert resp.form_state[field_k] == expected_val


def test_ambiguous_correction_asks_clarification(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = "sess_corr_ambig"
    state_manager.process_transcript(
        sid, "Maine Priya Devi ka newborn checkup kiya. Weight 2.8 kilo.", visit_date=anchor_date
    )
    resp = state_manager.process_transcript(
        sid, "Nahi woh galat hai.", visit_date=anchor_date
    )
    assert resp.action == "clarify"
    assert resp.form_state["beneficiary_name"] == "Priya Devi"
    assert resp.form_state["weight_kg"] == 2.8


def test_invalid_correction_rejected_without_corrupting_state(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = "sess_corr_invalid"
    state_manager.process_transcript(
        sid,
        "Maine Priya Devi ka ANC checkup kiya. Weight 55 kilo. BP 120/80.",
        visit_date=anchor_date,
    )
    resp_wt = state_manager.correct_session(sid, "No, weight is -5 kilo", visit_date=anchor_date)
    assert resp_wt.correction_applied is False
    assert resp_wt.form_state["weight_kg"] == 55.0

    resp_bp = state_manager.correct_session(sid, "No, BP is 80/120", visit_date=anchor_date)
    assert resp_bp.correction_applied is False
    assert resp_bp.form_state["blood_pressure"]["systolic"] == 120
    assert resp_bp.form_state["blood_pressure"]["diastolic"] == 80


def test_unrelated_new_info_not_treated_as_correction(
    state_manager: FormStateManager, anchor_date: date
) -> None:
    sid = "sess_not_corr"
    state_manager.process_transcript(
        sid, "Maine Priya Devi ka ANC checkup kiya.", visit_date=anchor_date
    )
    r2 = state_manager.process_transcript(
        sid, "Unka weight 55 kilo hai aur BP 120/80 hai.", visit_date=anchor_date
    )
    assert r2.form_state["beneficiary_name"] == "Priya Devi"
    assert r2.form_state["weight_kg"] == 55.0
    assert r2.form_state["blood_pressure"]["systolic"] == 120
