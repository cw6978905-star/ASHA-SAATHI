"""Tests for Module 1: AI Information Extraction, normalizers, Pydantic validation, and retries."""

from __future__ import annotations

import json
from datetime import date

import pytest

from brain.extraction import ExtractionEngine, ExtractionValidationError
from brain.llm_client import CallableMockLLMClient
from brain.normalizers import (
    parse_beneficiary_id,
    parse_blood_pressure,
    parse_spoken_weight_kg,
    resolve_relative_date,
)
from tests.synthetic_dataset import SYNTHETIC_EXTRACTION_CASES


def test_spec_newborn_example_exact_fields(
    extraction_engine: ExtractionEngine, anchor_date: date
) -> None:
    transcript = (
        "Aaj maine Priya Devi ka newborn checkup kiya. "
        "Baby ka weight do point aath kilo hai. "
        "BCG vaccination ho gaya hai. "
        "Next visit agle Mangalvar ko hai."
    )
    payload = extraction_engine.extract(transcript, visit_date=anchor_date)
    assert payload.beneficiary_name == "Priya Devi"
    assert payload.beneficiary_id is None
    assert payload.visit_type == "newborn"
    assert payload.weight_kg == 2.8
    assert payload.vaccinations == {"BCG": "completed"}
    assert payload.next_visit_date == date(2026, 11, 17)


@pytest.mark.parametrize(
    "case",
    SYNTHETIC_EXTRACTION_CASES,
    ids=[f"case_{c.case_id}_{c.label}" for c in SYNTHETIC_EXTRACTION_CASES],
)
def test_synthetic_extraction_dataset(
    case, extraction_engine: ExtractionEngine, anchor_date: date
) -> None:
    payload = extraction_engine.extract(case.transcript, visit_date=anchor_date)
    if case.expected_visit_type is not None:
        assert payload.visit_type == case.expected_visit_type
    if case.expected_name is not None:
        assert payload.beneficiary_name == case.expected_name
    if case.expected_id is not None:
        assert payload.beneficiary_id == case.expected_id
    elif case.case_id in {3, 20}:
        assert payload.beneficiary_id is None
    if case.expected_weight_kg is not None:
        assert payload.weight_kg == pytest.approx(case.expected_weight_kg, abs=0.01)
    if case.expected_bp is not None:
        assert payload.blood_pressure is not None
        assert (payload.blood_pressure.systolic, payload.blood_pressure.diastolic) == case.expected_bp
    if case.expected_ifa is not None:
        assert payload.ifa_status == case.expected_ifa
    for vac_k, vac_v in case.expected_vaccinations.items():
        assert payload.vaccinations.get(vac_k) == vac_v
    if case.expected_next_visit_date is not None:
        assert payload.next_visit_date == date.fromisoformat(case.expected_next_visit_date)
    if case.expect_ambiguous_date:
        assert payload.next_visit_date is None
        assert payload.ambiguous_next_visit_reference is not None


def test_spoken_numeric_and_code_mix_normalizers(anchor_date: date) -> None:
    assert parse_spoken_weight_kg("do point aath kilo") == 2.8
    assert parse_spoken_weight_kg("two point eight kg") == 2.8
    assert parse_spoken_weight_kg("do kilo aath sau gram") == 2.8
    assert parse_spoken_weight_kg("dhayi kilo") == 2.5
    assert parse_spoken_weight_kg("saade teen kilo") == 3.5
    assert parse_spoken_weight_kg("aath sau gram") == 0.8

    assert parse_beneficiary_id("Beneficiary ID P ek shunya do") == "P-102"
    assert parse_beneficiary_id("ID number one two three four") == "1234"
    assert parse_beneficiary_id("A zero zero seven", expect_id=True) == "A-007"

    bp = parse_blood_pressure("BP ek sau bees by assi")
    assert bp is not None and bp.systolic == 120 and bp.diastolic == 80

    # Relative date in Asia/Kolkata from Wednesday 2026-11-11
    d1, _, amb1 = resolve_relative_date("agle Mangalvar", anchor_date=anchor_date)
    assert d1 == date(2026, 11, 17) and amb1 is None

    # Ambiguous date reference must NOT invent a date
    d2, _, amb2 = resolve_relative_date("agle hafte", anchor_date=anchor_date)
    assert d2 is None and amb2 is not None


def test_pregnancy_and_unknown_vs_negative_distinction(
    extraction_engine: ExtractionEngine, anchor_date: date
) -> None:
    p1 = extraction_engine.extract(
        "Rekha Devi ka ANC visit, teen mahine ki pregnancy hai, IFA nahi diya, bleeding nahi hai, ID pata nahi.",
        visit_date=anchor_date,
    )
    assert p1.pregnancy_info is not None
    assert p1.pregnancy_info.gestational_months == 3.0
    assert p1.ifa_status == "not_provided"
    assert "bleeding" in p1.negative_findings
    assert "beneficiary_id" in p1.unknown_fields
    assert p1.beneficiary_id is None


def test_llm_invalid_json_retry_succeeds(anchor_date: date) -> None:
    calls = {"count": 0}

    def flaky_llm(sys_p, usr_p, task, meta):
        calls["count"] += 1
        if calls["count"] == 1:
            return "{not valid json!!!"
        return json.dumps(
            {
                "beneficiary_name": "Priya Devi",
                "beneficiary_id": "P-102",
                "visit_type": "newborn",
                "weight_kg": 2.8,
                "vaccinations": {"BCG": "completed"},
                "next_visit_date": "2026-11-17",
            }
        )

    engine = ExtractionEngine(
        llm_client=CallableMockLLMClient(flaky_llm),
        max_retries=2,
        fallback_on_failure=False,
    )
    payload = engine.extract(
        "Priya Devi newborn weight 2.8 kg BCG done",
        visit_date=anchor_date,
    )
    assert calls["count"] == 2
    assert payload.beneficiary_id == "P-102"
    assert payload.weight_kg == 2.8


def test_llm_exhausted_retries_raises_when_fallback_disabled(anchor_date: date) -> None:
    def broken_llm(sys_p, usr_p, task, meta):
        return '{"weight_kg": "invalid_not_a_number"}'

    engine = ExtractionEngine(
        llm_client=CallableMockLLMClient(broken_llm),
        max_retries=1,
        fallback_on_failure=False,
    )
    with pytest.raises(ExtractionValidationError):
        engine.extract("Priya Devi weight 2.8 kg", visit_date=anchor_date)
