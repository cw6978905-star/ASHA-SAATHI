"""Configurable LLM provider interface with Mock, OpenAI-compatible, Gemini, and Anthropic backends."""

from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

import httpx

from config import Settings, scrub_secrets

logger = logging.getLogger("asha_saathi.llm")


class LLMProviderError(RuntimeError):
    """Raised when an external LLM provider call fails or is misconfigured."""


class LLMConfigurationError(LLMProviderError):
    """Raised when production or explicit real LLM configuration is incomplete or invalid."""


class LLMTimeoutError(LLMProviderError):
    """Raised when an external LLM request exceeds the configured timeout."""


class LLMRateLimitError(LLMProviderError):
    """Raised when an external LLM provider responds with HTTP 429 rate limiting."""


def _post_json_with_retries(
    url: str,
    headers: Dict[str, str],
    body: Dict[str, Any],
    timeout_seconds: float,
    api_key: str,
    provider_label: str,
    max_transient_retries: int = 1,
) -> Dict[str, Any]:
    """Send JSON POST to an LLM endpoint with safe retry and secret-redacted error mapping."""
    transient_statuses = {429, 502, 503, 504}
    last_exc: Optional[LLMProviderError] = None

    for attempt in range(max_transient_retries + 1):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(url, headers=headers, json=body)

            if response.status_code == 429:
                last_exc = LLMRateLimitError(
                    f"{provider_label} rate limit exceeded (HTTP 429)."
                )
                if attempt < max_transient_retries:
                    retry_after_raw = response.headers.get("Retry-After", "0.2")
                    try:
                        delay = min(max(float(retry_after_raw), 0.05), 1.0)
                    except ValueError:
                        delay = 0.2
                    time.sleep(delay)
                    continue
                raise last_exc

            if response.status_code in transient_statuses:
                last_exc = LLMProviderError(
                    f"{provider_label} temporary server error (HTTP {response.status_code})."
                )
                if attempt < max_transient_retries:
                    time.sleep(0.15)
                    continue
                raise last_exc

            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise LLMProviderError(
                    f"{provider_label} returned non-object JSON payload."
                )
            return data

        except httpx.TimeoutException as exc:
            last_exc = LLMTimeoutError(
                f"{provider_label} request timed out after {timeout_seconds}s."
            )
            if attempt < max_transient_retries:
                continue
            raise last_exc from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            safe_msg = scrub_secrets(
                f"{provider_label} returned HTTP {status_code}.",
                [api_key],
            )
            raise LLMProviderError(safe_msg) from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            safe_msg = scrub_secrets(
                f"{provider_label} request failed: {exc}",
                [api_key],
            )
            raise LLMProviderError(safe_msg) from exc

    raise last_exc or LLMProviderError(f"{provider_label} request failed.")


class BaseLLMClient(ABC):
    """Abstract provider interface for structured JSON completions."""

    provider_name: str = "base"

    @abstractmethod
    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "generic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return raw text/JSON string from the LLM for the given prompts."""


class CallableMockLLMClient(BaseLLMClient):
    """Test helper LLM client delegating responses to a custom callable or fixed sequence."""

    provider_name = "mock_callable"

    def __init__(
        self,
        responder: Callable[[str, str, str, Optional[Dict[str, Any]]], str],
    ) -> None:
        self._responder = responder

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "generic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._responder(system_prompt, user_prompt, task, metadata)


class MockLLMClient(BaseLLMClient):
    """
    Deterministic local mock provider used when API credentials are unavailable.

    Produces structured JSON responses so offline development, live demos without
    external keys, and automated tests run reliably.
    """

    provider_name = "mock"

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "generic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        meta = metadata or {}
        if task == "extraction":
            from brain.extraction import deterministic_extract_dict

            transcript = str(meta.get("transcript", ""))
            visit_date = meta.get("visit_date")
            tz_name = str(meta.get("timezone", "Asia/Kolkata"))
            existing_form = meta.get("existing_form") or {}
            payload = deterministic_extract_dict(
                transcript=transcript,
                anchor_date=visit_date,
                tz_name=tz_name,
                existing_form=existing_form,
            )
            return json.dumps(payload, ensure_ascii=False)

        if task == "danger_detection":
            from brain.danger_detector import deterministic_contextual_danger_dict

            transcript = str(meta.get("transcript", ""))
            catalog = meta.get("catalog") or []
            return json.dumps(
                deterministic_contextual_danger_dict(transcript, catalog),
                ensure_ascii=False,
            )

        if task == "correction":
            from brain.correction import deterministic_detect_corrections_dict

            transcript = str(meta.get("transcript", ""))
            existing_form = meta.get("existing_form") or {}
            visit_date = meta.get("visit_date")
            tz_name = str(meta.get("timezone", "Asia/Kolkata"))
            return json.dumps(
                deterministic_detect_corrections_dict(
                    transcript=transcript,
                    existing_form=existing_form,
                    anchor_date=visit_date,
                    tz_name=tz_name,
                ),
                ensure_ascii=False,
            )

        return "{}"


class OpenAICompatibleLLMClient(BaseLLMClient):
    """Provider for OpenAI and OpenAI-compatible REST endpoints (Groq, OpenRouter, Ollama, vLLM)."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError("LLM_API_KEY is required for OpenAI-compatible provider.")
        if not model:
            raise LLMConfigurationError("LLM_MODEL is required for OpenAI-compatible provider.")
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout = timeout_seconds

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "generic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "model": self._model,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        data = _post_json_with_retries(
            url=url,
            headers=headers,
            body=body,
            timeout_seconds=self._timeout,
            api_key=self._api_key,
            provider_label="OpenAI-compatible",
        )
        try:
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise LLMProviderError("OpenAI-compatible response contained empty content.")
            return content
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                "OpenAI-compatible response missing choices[0].message.content."
            ) from exc


class GeminiLLMClient(BaseLLMClient):
    """Provider for Google Gemini REST generateContent API."""

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError("LLM_API_KEY is required for Gemini provider.")
        if not model:
            raise LLMConfigurationError("LLM_MODEL is required for Gemini provider.")
        self._api_key = api_key
        self._model = model.removeprefix("models/")
        self._base_url = (
            base_url or "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")
        self._timeout = timeout_seconds

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "generic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        model_id = self._model.removeprefix("models/")
        url = f"{self._base_url}/models/{model_id}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }
        data = _post_json_with_retries(
            url=url,
            headers=headers,
            body=body,
            timeout_seconds=self._timeout,
            api_key=self._api_key,
            provider_label="Gemini",
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(
                str(p.get("text", ""))
                for p in parts
                if isinstance(p, dict) and not p.get("thought")
            )
            if not text.strip():
                raise LLMProviderError("Gemini response contained empty text parts.")
            return text
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                "Gemini response missing candidates[0].content.parts."
            ) from exc


class AnthropicLLMClient(BaseLLMClient):
    """Provider for Anthropic Messages REST API."""

    provider_name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError("LLM_API_KEY is required for Anthropic provider.")
        if not model:
            raise LLMConfigurationError("LLM_MODEL is required for Anthropic provider.")
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")
        self._timeout = timeout_seconds

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "generic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = f"{self._base_url}/messages"
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": 1024,
            "temperature": 0.0,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        data = _post_json_with_retries(
            url=url,
            headers=headers,
            body=body,
            timeout_seconds=self._timeout,
            api_key=self._api_key,
            provider_label="Anthropic",
        )
        blocks = data.get("content", [])
        if not isinstance(blocks, list):
            raise LLMProviderError("Anthropic response missing content list.")
        text = "".join(
            str(b.get("text", ""))
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if not text.strip():
            raise LLMProviderError("Anthropic response contained empty content text.")
        return text


def _infer_auto_provider() -> str:
    if os.getenv("LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip():
        return "openai_compatible"
    if os.getenv("GEMINI_API_KEY", "").strip():
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    return "openai_compatible"


def create_llm_client(settings: Settings) -> BaseLLMClient:
    """Instantiate configured LLM provider; never silently downgrade explicit real providers to mock."""
    provider = settings.llm_provider.strip().lower() or "mock"

    if provider == "mock":
        if settings.require_real_llm:
            raise LLMConfigurationError(
                "REQUIRE_REAL_LLM / production mode is active; mock LLM_PROVIDER cannot be used."
            )
        logger.info("LLM provider initialized in mock mode")
        return MockLLMClient()

    if provider == "auto":
        if settings.llm_api_key and settings.llm_model:
            provider = _infer_auto_provider()
        elif settings.require_real_llm:
            raise LLMConfigurationError(
                "Production mode requires real LLM credentials (LLM_API_KEY and LLM_MODEL); refusing silent mock fallback."
            )
        else:
            logger.info("LLM credentials/model not configured in dev 'auto' mode; using mock provider")
            return MockLLMClient()

    if provider not in {"openai", "openai_compatible", "gemini", "anthropic"}:
        raise LLMConfigurationError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

    if not settings.llm_api_key or not settings.llm_model:
        missing = []
        if not settings.llm_api_key:
            missing.append("LLM_API_KEY (or provider API key)")
        if not settings.llm_model:
            missing.append("LLM_MODEL")
        raise LLMConfigurationError(
            f"Real LLM provider '{provider}' requested without {', '.join(missing)}. "
            "Refusing silent fallback to mock mode."
        )

    if provider in {"openai", "openai_compatible"}:
        return OpenAICompatibleLLMClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if provider == "gemini":
        return GeminiLLMClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return AnthropicLLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )
