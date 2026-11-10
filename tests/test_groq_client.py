"""Verify Groq request wiring without making external calls."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.llm import GroqCalls


class MemoryCache:
    def __init__(self):
        self.value = None

    def get_or_create(self, _payload, create):
        if self.value is not None:
            return self.value, True
        self.value = create()
        return self.value, False


def test_groq_function_call_is_parsed_and_cached():
    seen = []

    def create(**kwargs):
        seen.append(kwargs)
        result = {"answer": "A", "reasoning": "checked", "ambiguous": False}
        function = SimpleNamespace(name="submit_result", arguments=json.dumps(result))
        tool_call = SimpleNamespace(function=function)
        message = SimpleNamespace(tool_calls=[tool_call])
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    client = GroqCalls.__new__(GroqCalls)
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.cache = MemoryCache()
    client.model = "openai/gpt-oss-120b"

    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    first, first_cached = client._tool_call("blind_solver_run_1", "system text", {"question": "test"}, schema)
    second, second_cached = client._tool_call("blind_solver_run_1", "system text", {"question": "test"}, schema)

    assert first == second == {"answer": "A", "reasoning": "checked", "ambiguous": False}
    assert first_cached is False and second_cached is True
    assert len(seen) == 1
    assert seen[0]["messages"][0] == {"role": "system", "content": "system text"}
    assert seen[0]["tool_choice"] == {"type": "function", "function": {"name": "submit_result"}}
    assert seen[0]["tools"][0]["function"]["parameters"] == schema


def test_groq_client_explains_missing_key(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY is missing"):
        GroqCalls(tmp_path, tmp_path / "cache", "openai/gpt-oss-120b")
