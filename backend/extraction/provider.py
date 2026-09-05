# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .models import LLMProviderResponse

class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM Providers.
    Decouples prompt generation and extraction pipelines from specific LLM vendors (Gemini, Claude, OpenAI, or Mock).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if provider credentials and network endpoints are configured."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> LLMProviderResponse:
        """
        Invokes the provider and requests structured JSON output adhering to json_schema if supported.
        """
        pass
