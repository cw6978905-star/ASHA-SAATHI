"""Pytest configuration and shared fixtures for ASHA Saathi AI Brain tests."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from brain.correction import CorrectionEngine
from brain.danger_detector import DangerDetector
from brain.extraction import ExtractionEngine
from brain.guardrails import MedicalGuardrails
from brain.llm_client import MockLLMClient
from brain.state_manager import FormStateManager
from config import Settings
from main import create_app


@pytest.fixture
def anchor_date() -> date:
    """Reference date matching specification examples (Wednesday, 11 November 2026)."""
    return date(2026, 11, 11)


@pytest.fixture
def danger_signs_path() -> Path:
    return BACKEND_DIR / "data" / "danger_signs.json"


@pytest.fixture
def mock_llm() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def extraction_engine(mock_llm: MockLLMClient) -> ExtractionEngine:
    return ExtractionEngine(llm_client=mock_llm, max_retries=2, timezone_name="Asia/Kolkata")


@pytest.fixture
def correction_engine(mock_llm: MockLLMClient) -> CorrectionEngine:
    return CorrectionEngine(llm_client=mock_llm, timezone_name="Asia/Kolkata")


@pytest.fixture
def danger_detector(danger_signs_path: Path, mock_llm: MockLLMClient) -> DangerDetector:
    return DangerDetector(danger_signs_path=danger_signs_path, llm_client=mock_llm)


@pytest.fixture
def guardrails() -> MedicalGuardrails:
    return MedicalGuardrails()


@pytest.fixture
def state_manager(
    extraction_engine: ExtractionEngine,
    correction_engine: CorrectionEngine,
    danger_detector: DangerDetector,
    guardrails: MedicalGuardrails,
) -> FormStateManager:
    return FormStateManager(
        extraction_engine=extraction_engine,
        correction_engine=correction_engine,
        danger_detector=danger_detector,
        guardrails=guardrails,
        timezone_name="Asia/Kolkata",
    )


@pytest.fixture
def test_app(danger_signs_path: Path):
    settings = Settings(
        llm_provider="mock",
        danger_signs_path=danger_signs_path,
        app_timezone="Asia/Kolkata",
    )
    return create_app(settings=settings, llm_client=MockLLMClient())
