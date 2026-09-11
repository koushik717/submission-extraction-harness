"""OpenAI chat backend."""

from __future__ import annotations

import os
from typing import Any


class OpenAIBackend:
    name = "openai"

    def __init__(self) -> None:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self._client = OpenAI(api_key=api_key)

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        model: str,
    ) -> tuple[str, dict[str, int]]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = self._client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        usage = {
            "prompt_tokens": int(getattr(resp.usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(resp.usage, "completion_tokens", 0) or 0),
        }
        return text, usage
