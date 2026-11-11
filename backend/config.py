"""Configuration and safe logging utilities for the ASHA Saathi AI Brain backend."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BACKEND_DIR / ".env", override=False)


DEFAULT_REQUIRED_FIELDS_BY_VISIT_TYPE: Dict[str, List[str]] = {
    "anc": [
        "beneficiary_name",
        "weight_kg",
        "beneficiary_id",
        "blood_pressure",
        "ifa_status",
        "next_visit_date",
    ],
    "pnc": [
        "beneficiary_name",
        "beneficiary_id",
        "weight_kg",
        "ifa_status",
        "next_visit_date",
    ],
    "newborn": [
        "beneficiary_name",
        "beneficiary_id",
        "weight_kg",
        "vaccinations",
        "next_visit_date",
    ],
    "immunisation": [
        "beneficiary_name",
        "beneficiary_id",
        "vaccinations",
        "next_visit_date",
    ],
    "other": [
        "beneficiary_name",
        "beneficiary_id",
        "next_visit_date",
    ],
}


DEFAULT_AI_INTRO_MESSAGES: Dict[str, str] = {
    "hi-en": (
        "Namaste, main ASHA Saathi AI assistant hoon. Main visit record bharne mein "
        "madad karoongi, lekin main doctor nahi hoon aur dawai ya ilaj ki salah nahi de sakti."
    ),
    "en": (
        "Hello, I am the ASHA Saathi AI assistant. I help record visit details, "
        "but I am not a doctor and cannot give medical or treatment advice."
    ),
    "hi": (
        "नमस्ते, मैं आशा साथी AI असिस्टेंट हूँ। मैं विजिट रिकॉर्ड भरने में मदद करूँगी, "
        "लेकिन मैं डॉक्टर नहीं हूँ और दवा या इलाज की सलाह नहीं दे सकती।"
    ),
}


class SecretRedactingFilter(logging.Filter):
    """Logging filter that masks API keys and Bearer tokens if accidentally formatted."""

    _BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
    _KEY_PATTERN = re.compile(r"(sk-|AIza|key=)[A-Za-z0-9\-_]{8,}")

    def __init__(self, secret_values: Optional[List[str]] = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secret_values or []) if s and len(s) >= 6]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = self._redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True

    def _redact(self, text: str) -> str:
        masked = text
        for secret in self._secrets:
            if secret in masked:
                masked = masked.replace(secret, "[REDACTED]")
        masked = self._BEARER_PATTERN.sub(r"\1[REDACTED]", masked)
        masked = self._KEY_PATTERN.sub("[REDACTED_KEY]", masked)
        return masked


@dataclass(frozen=True)
class Settings:
    """Application configuration loaded from environment variables."""

    llm_provider: str = "mock"
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_timeout_seconds: float = 20.0
    max_extraction_retries: int = 2
    app_timezone: str = "Asia/Kolkata"
    danger_signs_path: Path = field(
        default_factory=lambda: BACKEND_DIR / "data" / "danger_signs.json"
    )
    log_level: str = "INFO"
    ai_intro_messages: Dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_AI_INTRO_MESSAGES)
    )
    required_fields_by_visit_type: Dict[str, List[str]] = field(
        default_factory=lambda: {
            k: list(v) for k, v in DEFAULT_REQUIRED_FIELDS_BY_VISIT_TYPE.items()
        }
    )


def _resolve_danger_signs_path(raw_path: Optional[str]) -> Path:
    if not raw_path:
        return BACKEND_DIR / "data" / "danger_signs.json"
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (BACKEND_DIR / candidate).resolve()


def _resolve_api_key(provider: str) -> Optional[str]:
    direct = os.getenv("LLM_API_KEY", "").strip()
    if direct:
        return direct
    provider_env_map = {
        "openai": "OPENAI_API_KEY",
        "openai_compatible": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    fallback_var = provider_env_map.get(provider)
    if fallback_var:
        val = os.getenv(fallback_var, "").strip()
        if val:
            return val
    return None


def load_settings() -> Settings:
    """Build Settings instance from environment variables."""
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"
    api_key = _resolve_api_key(provider)
    model = os.getenv("LLM_MODEL", "").strip() or None
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None

    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    except ValueError:
        timeout = 20.0

    try:
        retries = max(0, int(os.getenv("MAX_EXTRACTION_RETRIES", "2")))
    except ValueError:
        retries = 2

    intro_messages = {
        "hi-en": os.getenv(
            "AI_INTRO_MESSAGE_HI_EN", DEFAULT_AI_INTRO_MESSAGES["hi-en"]
        ),
        "en": os.getenv("AI_INTRO_MESSAGE_EN", DEFAULT_AI_INTRO_MESSAGES["en"]),
        "hi": os.getenv("AI_INTRO_MESSAGE_HI", DEFAULT_AI_INTRO_MESSAGES["hi"]),
    }

    return Settings(
        llm_provider=provider,
        llm_api_key=api_key,
        llm_model=model,
        llm_base_url=base_url,
        llm_timeout_seconds=timeout,
        max_extraction_retries=retries,
        app_timezone=os.getenv("APP_TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata",
        danger_signs_path=_resolve_danger_signs_path(os.getenv("DANGER_SIGNS_PATH")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        ai_intro_messages=intro_messages,
    )


def configure_logging(settings: Optional[Settings] = None) -> logging.Logger:
    """Configure root/app logger safely without exposing secrets or PII."""
    cfg = settings or load_settings()
    logger = logging.getLogger("asha_saathi")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    secrets = [cfg.llm_api_key] if cfg.llm_api_key else []
    redactor = SecretRedactingFilter(secrets)
    for handler in logger.handlers:
        handler.filters = [
            f for f in handler.filters if not isinstance(f, SecretRedactingFilter)
        ]
        handler.addFilter(redactor)

    level = getattr(logging, cfg.log_level, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False
    return logger
