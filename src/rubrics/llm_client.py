"""OpenAI-compatible client for gpt-5.4-mini (aiberm.com / dubrify.com)."""
from __future__ import annotations
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.3
    max_retries: int = 3
    timeout_s: float = 120.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL", "https://aiberm.com/v1"),
            model=os.environ.get("LLM_MODEL", "openai/gpt-5.4-mini"),
        )


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _extract_json_block(text: str) -> str:
    m = _JSON_FENCE.search(text)
    if m:
        return m.group(1)
    return text.strip()


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self._client = httpx.Client(timeout=cfg.timeout_s)

    def complete_json(
        self, system: str, user: str, schema_hint: str,
        temperature: float | None = None, model: str | None = None,
    ) -> Any:
        """POST /chat/completions and parse JSON. Retries on 5xx/connection errors."""
        @retry(
            stop=stop_after_attempt(self.cfg.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
            reraise=True,
        )
        def _call() -> dict:
            r = self._client.post(
                f"{self.cfg.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.cfg.api_key}"},
                json={
                    "model": model or self.cfg.model,
                    "temperature": temperature if temperature is not None else self.cfg.temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()

        data = _call()
        content = data["choices"][0]["message"]["content"]
        block = _extract_json_block(content)
        try:
            return json.loads(block)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON. Raw content (first 500 chars): %s", content[:500])
            raise ValueError(f"LLM did not return valid JSON: {e}") from e

    async def complete_json_async(
        self, system: str, user: str, schema_hint: str,
        temperature: float | None = None, model: str | None = None,
    ) -> Any:
        """Async variant of complete_json. Uses a fresh httpx.AsyncClient per call.

        Retries on 5xx / connection errors via tenacity AsyncRetrying.
        """
        from tenacity import AsyncRetrying

        async def _do_call() -> dict:
            async with httpx.AsyncClient(timeout=self.cfg.timeout_s) as ac:
                r = await ac.post(
                    f"{self.cfg.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.cfg.api_key}"},
                    json={
                        "model": model or self.cfg.model,
                        "temperature": temperature if temperature is not None else self.cfg.temperature,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                r.raise_for_status()
                return r.json()

        data: dict | None = None
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.cfg.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
            reraise=True,
        ):
            with attempt:
                data = await _do_call()
        assert data is not None
        content = data["choices"][0]["message"]["content"]
        block = _extract_json_block(content)
        try:
            return json.loads(block)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON. Raw content (first 500): %s", content[:500])
            raise ValueError(f"LLM did not return valid JSON: {e}") from e
