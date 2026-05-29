import os

import pytest

from agents.llm_client import LLMClient


pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


def test_complete_text_returns_non_empty_response():
    client = LLMClient()
    text = client.complete_text(
        system="Răspunzi cu un singur cuvânt: 'ok'.",
        user="Spune 'ok'.",
    )
    assert isinstance(text, str)
    assert len(text.strip()) > 0
