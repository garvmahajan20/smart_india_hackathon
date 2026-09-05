# -*- coding: utf-8 -*-
import hashlib
import json
import os
from typing import Any, Dict, Optional

from .models import LLMProviderResponse

class LLMCache:
    """
    Deterministic disk cache for LLM extraction requests.
    Prevents repeated expensive API invocations during demos and regression runs.
    """

    def __init__(self, cache_dir: str = "data/cache/llm"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def generate_cache_key(
        self,
        provider_name: str,
        model_name: str,
        prompt_version: str,
        prompt_content: str,
        schema_version: str = "v1"
    ) -> str:
        """
        Creates a deterministic SHA-256 cache key based on invocation parameters and text content.
        """
        hasher = hashlib.sha256()
        hasher.update(provider_name.encode("utf-8"))
        hasher.update(b":")
        hasher.update(model_name.encode("utf-8"))
        hasher.update(b":")
        hasher.update(prompt_version.encode("utf-8"))
        hasher.update(b":")
        hasher.update(schema_version.encode("utf-8"))
        hasher.update(b":")
        hasher.update(prompt_content.encode("utf-8"))
        return hasher.hexdigest()

    def get(self, key: str) -> Optional[LLMProviderResponse]:
        """
        Retrieves a cached response if available.
        """
        file_path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            resp = LLMProviderResponse.from_dict(data)
            resp.is_cached = True
            return resp
        except Exception:
            return None

    def set(self, key: str, response: LLMProviderResponse) -> None:
        """
        Persists a response into disk cache.
        """
        file_path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(response.to_dict(), f, indent=2)
        except Exception:
            pass

    def has(self, key: str) -> bool:
        return os.path.exists(os.path.join(self.cache_dir, f"{key}.json"))
