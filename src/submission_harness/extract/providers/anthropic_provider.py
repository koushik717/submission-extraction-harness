"""Anthropic messages backend."""

from __future__ import annotations

import os
from typing import Any


class AnthropicBackend:
    name = "anthropic"

    def __init__(self) -> None:
        from anthropic import Anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = Anthropic(api_key=api_key)

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        model: str,
    ) -> tuple[str, dict[str, int]]:
        system = ""
        converted: list[dict[str, Any]] = []
        for msg in messages:
            if msg["role"] == "system":
                system = str(msg["content"])
            else:
                converted.append({"role": msg["role"], "content": msg["content"]})
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": converted,
            "system": system,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = self._client.messages.create(**kwargs)
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        usage = {
            "prompt_tokens": int(getattr(resp.usage, "input_tokens", 0) or 0),
            "completion_tokens": int(getattr(resp.usage, "output_tokens", 0) or 0),
        }
        return text, usage
