"""Automated evaluation report over the 40-case synthetic dataset."""

from __future__ import annotations

from datetime import date

from brain.correction import CorrectionEngine
from brain.danger_detector import DangerDetector
from brain.extraction import ExtractionEngine
from brain.state_manager import FormStateManager
from tests.synthetic_dataset import (
    SYNTHETIC_CORRECTION_CASES,
    SYNTHETIC_DANGER_CASES,
    SYNTHETIC_EXTRACTION_CASES,
)


def compute_evaluation_metrics(
    extraction_engine: ExtractionEngine,
    danger_detector: DangerDetector,
    state_manager: FormStateManager,
    anchor_date: date,
) -> dict[str, float | int]:
    """Run synthetic benchmark across extraction, numeric, correction, danger, and confirmation."""
    ext_passed = 0
    num_total = 0
    num_passed = 0

    for case in SYNTHETIC_EXTRACTION_CASES:
        payload = extraction_engine.extract(case.transcript, visit_date=anchor_date)
        ok = True
        if case.expected_visit_type is not None and payload.visit_type != case.expected_visit_type:
            ok = False
        if case.expected_name is not None and payload.beneficiary_name != case.expected_name:
            ok = False
        if case.expected_id is not None and payload.beneficiary_id != case.expected_id:
            ok = False
        if case.expected_weight_kg is not None:
            num_total += 1
            if payload.weight_kg is not None and abs(payload.weight_kg - case.expected_weight_kg) < 0.01:
                num_passed += 1
            else:
                ok = False
        if case.expected_bp is not None:
            num_total += 1
            if payload.blood_pressure and (
                payload.blood_pressure.systolic,
                payload.blood_pressure.diastolic,
            ) == case.expected_bp:
                num_passed += 1
            else:
                ok = False
        if case.expected_ifa is not None and payload.ifa_status != case.expected_ifa:
            ok = False
        for k, v in case.expected_vaccinations.items():
            if payload.vaccinations.get(k) != v:
                ok = False
        if case.expected_next_visit_date is not None:
            if str(payload.next_visit_date) != case.expected_next_visit_date:
                ok = False
        if case.expect_ambiguous_date and payload.next_visit_date is not None:
            ok = False
        if ok:
            ext_passed += 1

    corr_passed = 0
    for idx, ccase in enumerate(SYNTHETIC_CORRECTION_CASES):
        sid = f"eval_corr_{idx}"
        sess = state_manager.get_or_create_session(sid)
        for k, v in ccase.initial_state.items():
            if k == "next_visit_date" and isinstance(v, str):
                setattr(sess.record, k, date.fromisoformat(v))
            else:
                setattr(sess.record, k, v)
        sess.record.visit_date = anchor_date
        res = state_manager.correct_session(sid, ccase.transcript, visit_date=anchor_date)
        if res.correction_applied == ccase.expected_applied and all(
            res.form_state.get(fk) == fv for fk, fv in ccase.expected_fields.items()
        ):
            corr_passed += 1

    tp = fp = fn = tn = 0
    for dcase in SYNTHETIC_DANGER_CASES:
        detected, _ = danger_detector.detect(dcase.transcript)
        if dcase.expected_danger and detected:
            tp += 1
        elif dcase.expected_danger and not detected:
            fn += 1
        elif not dcase.expected_danger and detected:
            fp += 1
        else:
            tn += 1

    recall = tp / (tp + fn) if (tp + fn) else 1.0
    precision = tp / (tp + fp) if (tp + fp) else 1.0

    # Confirmation trials: affirmative, negative, pre-save correction
    conf_trials = 0
    conf_passed = 0
    sid_c = "eval_conf"
    state_manager.process_transcript(
        sid_c,
        "Priya Devi newborn visit, ID P-102, weight 2.8 kg, BCG done, next visit agle Mangalvar.",
        visit_date=anchor_date,
    )
    conf_trials += 1
    if not state_manager.confirm_session(sid_c, transcript="Nahi mat save karo").confirmed:
        conf_passed += 1
    conf_trials += 1
    corr_c = state_manager.confirm_session(sid_c, transcript="Nahi weight 3.0 kg hai", visit_date=anchor_date)
    if not corr_c.confirmed and corr_c.form_state["weight_kg"] == 3.0:
        conf_passed += 1
    conf_trials += 1
    if state_manager.confirm_session(sid_c, transcript="Haan save kar do").confirmed:
        conf_passed += 1

    return {
        "extraction_accuracy": round(ext_passed / len(SYNTHETIC_EXTRACTION_CASES), 4),
        "numeric_extraction_accuracy": round(num_passed / num_total, 4) if num_total else 1.0,
        "correction_accuracy": round(corr_passed / len(SYNTHETIC_CORRECTION_CASES), 4),
        "danger_sign_recall": round(recall, 4),
        "danger_sign_precision": round(precision, 4),
        "false_positives": fp,
        "false_negatives": fn,
        "confirmation_accuracy": round(conf_passed / conf_trials, 4),
    }


def test_synthetic_benchmark_thresholds_and_report(
    extraction_engine: ExtractionEngine,
    danger_detector: DangerDetector,
    state_manager: FormStateManager,
    anchor_date: date,
) -> None:
    metrics = compute_evaluation_metrics(
        extraction_engine=extraction_engine,
        danger_detector=danger_detector,
        state_manager=state_manager,
        anchor_date=anchor_date,
    )
    print("\n=== ASHA Saathi AI Brain Synthetic Evaluation Report ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    assert metrics["danger_sign_recall"] == 1.0
    assert metrics["false_negatives"] == 0
    assert metrics["extraction_accuracy"] >= 0.90
    assert metrics["numeric_extraction_accuracy"] >= 0.95
    assert metrics["correction_accuracy"] == 1.0
    assert metrics["confirmation_accuracy"] == 1.0
