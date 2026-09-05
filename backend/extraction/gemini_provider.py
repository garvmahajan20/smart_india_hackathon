# -*- coding: utf-8 -*-
import json
import os
import time
from typing import Any, Dict, Optional

import requests

from .models import LLMProviderResponse
from .provider import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    """
    Production Gemini API provider utilizing structured JSON output mode.
    Reads GEMINI_API_KEY from environment without hard-coding secrets.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback_model: Optional[str] = None,
        max_retries: int = 2,
        timeout_seconds: int = 30
    ):
        if api_key is None:
            if "GEMINI_API_KEY" not in os.environ:
                try:
                    from backend.config import load_dotenv
                    load_dotenv()
                except ImportError:
                    pass
            self._api_key = os.environ.get("GEMINI_API_KEY", "")
        else:
            self._api_key = api_key

        self._model_name = (model_name or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")).strip()
        self._fallback_model = (fallback_model or os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.7-flash")).strip()
        self._max_retries = max_retries
        self._timeout = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "Gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def fallback_model(self) -> str:
        return self._fallback_model

    def is_available(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _execute_request(
        self,
        model: str,
        payload: Dict[str, Any]
    ) -> LLMProviderResponse:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self._api_key}"
        last_error = ""
        for attempt in range(self._max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = requests.post(url, json=payload, timeout=self._timeout)
                latency = (time.perf_counter() - t0) * 1000.0

                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return LLMProviderResponse(
                            content="",
                            model_name=model,
                            latency_ms=latency,
                            error="No candidate returned by Gemini API.",
                        )

                    text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    usage = data.get("usageMetadata", {})
                    p_tok = usage.get("promptTokenCount")
                    c_tok = usage.get("candidatesTokenCount")

                    return LLMProviderResponse(
                        content=text_content,
                        model_name=model,
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        latency_ms=latency,
                        is_mock=False,
                        is_cached=False,
                    )
                else:
                    last_error = f"Gemini API error ({resp.status_code}): {resp.text}"
                    # Return immediately on 404 (model not found) to allow fallback without burning retries
                    if resp.status_code == 404:
                        return LLMProviderResponse(
                            content="",
                            model_name=model,
                            error=last_error,
                            is_mock=False,
                            is_cached=False,
                        )
                    if resp.status_code in [429, 500, 503] and attempt < self._max_retries:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    break

            except Exception as e:
                last_error = f"Network or execution error: {str(e)}"
                if attempt < self._max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue

        return LLMProviderResponse(
            content="",
            model_name=model,
            error=last_error,
            is_mock=False,
            is_cached=False,
        )

    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> LLMProviderResponse:
        if not self.is_available():
            return LLMProviderResponse(
                content="",
                model_name=self.model_name,
                error="GEMINI_API_KEY is not configured in environment.",
                is_mock=False,
                is_cached=False,
            )

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            }
        }

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        if json_schema:
            payload["generationConfig"]["responseSchema"] = json_schema

        # 1. Primary Model Attempt
        res = self._execute_request(self._model_name, payload)
        if not res.error:
            return res

        # 2. Bounded Single Fallback (only on model availability errors: 404 or 503)
        if self._fallback_model and self._fallback_model != self._model_name:
            err_str = res.error or ""
            if "404" in err_str or "503" in err_str or "NOT_FOUND" in err_str or "UNAVAILABLE" in err_str:
                fallback_res = self._execute_request(self._fallback_model, payload)
                if not fallback_res.error:
                    return fallback_res

        return res
