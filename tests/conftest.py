import anthropic
import dashscope
import pytest


@pytest.fixture(autouse=True)
def no_real_provider_calls(monkeypatch):
    """Fail any test that reaches a real provider SDK, in every file, whatever .env holds.

    A test that needs an SDK replaces the entry point with its own fake, which overrides this one.
    """

    def refuse(*args, **kwargs):
        raise AssertionError("A test reached a real provider SDK.")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    monkeypatch.setattr(dashscope.Generation, "call", refuse)
