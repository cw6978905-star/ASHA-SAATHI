"""Tests for Module 5: Two-layer Danger-Sign Detection and Recall-First Safety."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.danger_detector import DangerDetector, FIXED_REFERRAL_MESSAGES
from brain.llm_client import CallableMockLLMClient
from brain.state_manager import FormStateManager
from tests.synthetic_dataset import SYNTHETIC_DANGER_CASES


@pytest.mark.parametrize(
    "case",
    SYNTHETIC_DANGER_CASES,
    ids=[f"case_{c.case_id}_{c.label}" for c in SYNTHETIC_DANGER_CASES],
)
def test_synthetic_danger_sign_cases(case, danger_detector: DangerDetector) -> None:
    detected, flags = danger_detector.detect(case.transcript, language="hi-en")
    assert detected is case.expected_danger
    found_ids = {f.danger_sign_id for f in flags}
    for expected_id in case.expected_sign_ids:
        assert expected_id in found_ids
    if case.expect_ambiguous:
        assert any(f.ambiguous for f in flags)


def test_llm_cannot_silently_cancel_positive_rule_based_flag(
    danger_signs_path: Path,
) -> None:
    def suppressive_llm(sys_p, usr_p, task, meta):
        # Mocked LLM falsely says there is NO danger sign
        return json.dumps({"danger_detected": False, "matches": []})

    detector = DangerDetector(
        danger_signs_path=danger_signs_path,
        llm_client=CallableMockLLMClient(suppressive_llm),
    )
    detected, flags = detector.detect("Patient ko heavy bleeding ho rahi hai.")
    assert detected is True
    assert len(flags) == 1
    assert flags[0].danger_sign_id == "severe_bleeding"
    assert flags[0].matched_layers == ["rule_based"]


def test_llm_layer2_catches_paraphrase_when_rule_layer_misses(
    danger_signs_path: Path,
) -> None:
    def contextual_llm(sys_p, usr_p, task, meta):
        return json.dumps(
            {
                "danger_detected": True,
                "matches": [
                    {
                        "danger_sign_id": "convulsions",
                        "evidence": "baccha aankhein upar chadha kar kaanp raha hai",
                        "reason": "Indirect description of possible seizure/convulsion.",
                        "ambiguous": True,
                    }
                ],
            }
        )

    detector = DangerDetector(
        danger_signs_path=danger_signs_path,
        llm_client=CallableMockLLMClient(contextual_llm),
    )
    detected, flags = detector.detect(
        "Baccha aankhein upar chadha kar kaanp raha hai."
    )
    assert detected is True
    assert flags[0].danger_sign_id == "convulsions"
    assert "llm" in flags[0].matched_layers
    assert flags[0].ambiguous is True


def test_fixed_referral_template_and_no_diagnosis_in_response(
    state_manager: FormStateManager,
) -> None:
    for lang, expected_msg in FIXED_REFERRAL_MESSAGES.items():
        sid = f"sess_danger_{lang}"
        resp = state_manager.process_transcript(
            sid,
            "Baby ko tez bukhar hai aur doodh nahi pi raha.",
            language=lang,  # type: ignore[arg-type]
        )
        assert resp.danger_detected is True
        assert resp.action == "refer_danger"
        assert resp.reply_text == expected_msg
        lower_reply = resp.reply_text.lower()
        assert "paracetamol" not in lower_reply
        assert "dose" not in lower_reply
        assert "pneumonia" not in lower_reply


def test_configurable_danger_signs_metadata(danger_detector: DangerDetector) -> None:
    meta = danger_detector.metadata
    assert meta.get("pending_person_c_verification") is True
    assert len(danger_detector.catalog) >= 10
    assert all(
        entry.get("source_reference") == "PENDING_PERSON_C_VERIFICATION"
        for entry in danger_detector.catalog
    )
