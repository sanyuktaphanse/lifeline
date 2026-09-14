from types import SimpleNamespace

import anthropic
import dashscope
import httpx2
import pytest
from dashscope.api_entities.dashscope_response import (
    DashScopeAPIResponse,
    GenerationResponse,
)

from contracts.interfaces import ModelAdapter
from contracts.schemas import Message
from core.fake_adapter import FakeModelAdapter
from core.model_adapter import ProviderModelAdapter, ProviderUnavailable

MESSAGES = [Message(role="user", text="Quote 1,200 SGD to my landlord in Brazil")]


def _anthropic_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _fake_anthropic(calls: list, *, reply: str = "Here is the quote.", error=None):
    class FakeAnthropic:
        def __init__(self, *args, **kwargs):
            self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

        def _create(self, **kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text=reply)],
            )

    return FakeAnthropic


def _fake_dashscope(calls: list, *, reply: str = "Aqui está a cotação.", status_code=200):
    def call(**kwargs):
        calls.append(kwargs)
        if status_code != 200:
            return GenerationResponse.from_api_response(
                DashScopeAPIResponse(
                    status_code=status_code,
                    code="InvalidApiKey",
                    message="Invalid API-key provided.",
                )
            )
        return GenerationResponse.from_api_response(
            DashScopeAPIResponse(
                status_code=200,
                output={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": reply},
                        }
                    ]
                },
            )
        )

    return call


@pytest.fixture(autouse=True)
def no_real_provider_calls(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("A test reached a real provider SDK.")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    monkeypatch.setattr(dashscope.Generation, "call", refuse)


def test_fake_adapter_returns_scripted_responses_in_order():
    fake = FakeModelAdapter(["first", "second"])

    assert isinstance(fake, ModelAdapter)
    assert fake.complete(MESSAGES, []).text == "first"
    assert fake.complete(MESSAGES, []).text == "second"
    with pytest.raises(RuntimeError):
        fake.complete(MESSAGES, [])


def test_provider_defaults_to_anthropic_with_dashscope_fallback():
    adapter = ProviderModelAdapter(env={})

    assert isinstance(adapter, ModelAdapter)
    assert adapter.provider == "anthropic"
    assert adapter.fallback_provider == "dashscope"


def test_empty_values_fall_back_to_the_defaults():
    adapter = ProviderModelAdapter(env={"MODEL_PROVIDER": "", "FALLBACK_MODEL_PROVIDER": ""})

    assert adapter.provider == "anthropic"
    assert adapter.fallback_provider == "dashscope"


def test_provider_is_selected_from_the_environment_variable(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "dashscope")
    monkeypatch.setenv("FALLBACK_MODEL_PROVIDER", "anthropic")
    dashscope_calls: list = []
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope(dashscope_calls))

    adapter = ProviderModelAdapter()
    reply = adapter.complete(MESSAGES, [])

    assert adapter.provider == "dashscope"
    assert reply == Message(role="assistant", text="Aqui está a cotação.")
    assert adapter.last_provider == "dashscope"
    assert len(dashscope_calls) == 1
    assert dashscope_calls[0]["messages"] == [
        {"role": "user", "content": "Quote 1,200 SGD to my landlord in Brazil"}
    ]


def test_anthropic_answers_by_default(monkeypatch):
    anthropic_calls: list = []
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls))

    adapter = ProviderModelAdapter(env={})
    reply = adapter.complete(MESSAGES, [])

    assert reply.text == "Here is the quote."
    assert adapter.last_provider == "anthropic"
    assert anthropic_calls[0]["model"] == "claude-opus-5"
    assert anthropic_calls[0]["messages"] == [
        {"role": "user", "content": "Quote 1,200 SGD to my landlord in Brazil"}
    ]


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APIConnectionError(request=_anthropic_request()),
        anthropic.AuthenticationError(
            "invalid x-api-key",
            response=httpx2.Response(401, request=_anthropic_request()),
            body=None,
        ),
        TypeError(
            '"Could not resolve authentication method. Expected one of api_key, '
            'auth_token, or credentials to be set."'
        ),
    ],
    ids=["connection", "auth", "missing-credentials"],
)
def test_primary_failure_falls_back_and_reports_the_provider(monkeypatch, error):
    anthropic_calls: list = []
    dashscope_calls: list = []
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls, error=error))
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope(dashscope_calls))

    adapter = ProviderModelAdapter(env={})
    reply = adapter.complete(MESSAGES, [])

    assert reply.text == "Aqui está a cotação."
    assert adapter.last_provider == "dashscope"
    assert len(anthropic_calls) == 1
    assert len(dashscope_calls) == 1


def test_dashscope_auth_status_falls_back_to_anthropic(monkeypatch):
    anthropic_calls: list = []
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope([], status_code=401))
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls))

    adapter = ProviderModelAdapter(
        env={"MODEL_PROVIDER": "dashscope", "FALLBACK_MODEL_PROVIDER": "anthropic"}
    )
    reply = adapter.complete(MESSAGES, [])

    assert reply.text == "Here is the quote."
    assert adapter.last_provider == "anthropic"


def test_fallback_is_tried_only_once(monkeypatch):
    anthropic_calls: list = []
    dashscope_calls: list = []
    error = anthropic.APIConnectionError(request=_anthropic_request())
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls, error=error))
    monkeypatch.setattr(
        dashscope.Generation, "call", _fake_dashscope(dashscope_calls, status_code=401)
    )

    adapter = ProviderModelAdapter(env={})
    with pytest.raises(ProviderUnavailable):
        adapter.complete(MESSAGES, [])

    assert len(anthropic_calls) == 1
    assert len(dashscope_calls) == 1


def test_other_errors_do_not_fall_back(monkeypatch):
    error = anthropic.BadRequestError(
        "bad request",
        response=httpx2.Response(400, request=_anthropic_request()),
        body=None,
    )
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic([], error=error))

    adapter = ProviderModelAdapter(env={})
    with pytest.raises(anthropic.BadRequestError):
        adapter.complete(MESSAGES, [])
