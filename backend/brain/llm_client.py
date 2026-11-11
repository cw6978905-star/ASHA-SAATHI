"""Configurable LLM provider interface with Mock, OpenAI-compatible, Gemini, and Anthropic backends."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

import httpx

from config import Settings

logger = logging.getLogger("asha_saathi.llm")


class LLMProviderError(RuntimeError):
    """Raised when an external LLM provider call fails or is misconfigured."""


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
            raise LLMProviderError("LLM_API_KEY is required for OpenAI-compatible provider.")
        if not model:
            raise LLMProviderError("LLM_MODEL is required for OpenAI-compatible provider.")
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
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"OpenAI-compatible request failed: {exc}") from exc


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
            raise LLMProviderError("LLM_API_KEY is required for Gemini provider.")
        if not model:
            raise LLMProviderError("LLM_MODEL is required for Gemini provider.")
        self._api_key = api_key
        self._model = model
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
        url = f"{self._base_url}/models/{self._model}:generateContent"
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
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(str(p.get("text", "")) for p in parts)
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Gemini request failed: {exc}") from exc


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
            raise LLMProviderError("LLM_API_KEY is required for Anthropic provider.")
        if not model:
            raise LLMProviderError("LLM_MODEL is required for Anthropic provider.")
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
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
            blocks = data.get("content", [])
            return "".join(str(b.get("text", "")) for b in blocks if b.get("type") == "text")
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise LLMProviderError(f"Anthropic request failed: {exc}") from exc


def create_llm_client(settings: Settings) -> BaseLLMClient:
    """Instantiate the configured LLM provider, falling back to Mock if explicitly set or auto without keys."""
    provider = settings.llm_provider.lower()
    if provider == "mock":
        logger.info("LLM provider initialized in mock mode")
        return MockLLMClient()

    if provider == "auto":
        if not settings.llm_api_key or not settings.llm_model:
            logger.info("LLM credentials/model not configured; using mock provider")
            return MockLLMClient()
        provider = "openai_compatible"

    if not settings.llm_api_key or not settings.llm_model:
        logger.warning(
            "Provider '%s' selected without LLM_API_KEY or LLM_MODEL; falling back to mock mode",
            provider,
        )
        return MockLLMClient()

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
    if provider == "anthropic":
        return AnthropicLLMClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    raise LLMProviderError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
