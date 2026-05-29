import os
from dataclasses import dataclass
from typing import Any

import anthropic


DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DEFAULT_MAX_TOKENS = 4096


@dataclass
class LLMClient:
    """Thin wrapper around anthropic.Anthropic. Reads ANTHROPIC_API_KEY from env."""

    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic()

    def complete_text(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(resp)

    def complete_vision(self, system: str, content_blocks: list[dict[str, Any]]) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": content_blocks}],
        )
        return _extract_text(resp)


def _extract_text(response: Any) -> str:
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts)
