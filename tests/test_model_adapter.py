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
from contracts.schemas import Message, ToolCall
from core.fake_adapter import FakeModelAdapter
from core.model_adapter import (
    MissingApiKey,
    ModelAdapterError,
    ProviderModelAdapter,
    ProviderUnavailable,
)

MESSAGES = [Message(role="user", text="Quote 1,200 SGD to my landlord in Brazil")]
KEYS = {"ANTHROPIC_API_KEY": "test-anthropic-key", "DASHSCOPE_API_KEY": "test-dashscope-key"}
QUOTE_TOOL_CALL = ToolCall(
    id="toolu_01", name="quote_route", arguments={"corridor": "SG>BR", "amount": "1200"}
)


def _anthropic_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _anthropic_text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _fake_anthropic(calls: list, *, content=None, stop_reason="end_turn", error=None):
    blocks = [_anthropic_text("Here is the quote.")] if content is None else content

    class FakeAnthropic:
        def __init__(self, *, api_key=None, **kwargs):
            self.api_key = api_key
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            calls.append(dict(kwargs, _api_key=self.api_key))
            if error is not None:
                raise error
            return SimpleNamespace(stop_reason=stop_reason, content=blocks)

    return FakeAnthropic


def _fake_dashscope(calls: list, *, message=None, status_code=200):
    reply = message or {"role": "assistant", "content": "Aqui está a cotação."}

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
                output={"choices": [{"finish_reason": "stop", "message": reply}]},
            )
        )

    return call


def _dashscope_tool_call_message(arguments: str) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "toolu_01",
                "type": "function",
                "function": {"name": "quote_route", "arguments": arguments},
            }
        ],
    }


@pytest.fixture(autouse=True)
def no_real_provider_calls(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("A test reached a real provider SDK.")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    monkeypatch.setattr(dashscope.Generation, "call", refuse)


def test_fake_adapter_returns_scripted_responses_in_order():
    fake = FakeModelAdapter(["first", "second"])

    assert isinstance(fake, ModelAdapter)
    first = fake.complete(MESSAGES, [])
    assert first.text == "first"
    assert (first.provider, first.model) == ("fake", "fake")
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
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
    dashscope_calls: list = []
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope(dashscope_calls))

    adapter = ProviderModelAdapter()
    reply = adapter.complete(MESSAGES, [])

    assert adapter.provider == "dashscope"
    assert reply.text == "Aqui está a cotação."
    assert (reply.provider, reply.model) == ("dashscope", "qwen-plus")
    assert len(dashscope_calls) == 1
    assert dashscope_calls[0]["api_key"] == "test-dashscope-key"
    assert dashscope_calls[0]["max_tokens"] == 2048
    assert dashscope_calls[0]["messages"] == [
        {"role": "user", "content": "Quote 1,200 SGD to my landlord in Brazil"}
    ]


def test_anthropic_answers_by_default_without_an_internal_fallback(monkeypatch):
    anthropic_calls: list = []
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls))

    adapter = ProviderModelAdapter(env=KEYS)
    reply = adapter.complete(MESSAGES, [])

    assert reply.text == "Here is the quote."
    assert (reply.provider, reply.model) == ("anthropic", "claude-opus-5")
    call = anthropic_calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["_api_key"] == "test-anthropic-key"
    assert "fallbacks" not in call
    assert "betas" not in call
    assert call["messages"] == [
        {"role": "user", "content": "Quote 1,200 SGD to my landlord in Brazil"}
    ]


def test_anthropic_tool_call_is_returned_in_the_message(monkeypatch):
    content = [
        _anthropic_text("Let me quote that."),
        SimpleNamespace(
            type="tool_use",
            id="toolu_01",
            name="quote_route",
            input={"corridor": "SG>BR", "amount": "1200"},
        ),
    ]
    monkeypatch.setattr(
        anthropic, "Anthropic", _fake_anthropic([], content=content, stop_reason="tool_use")
    )

    reply = ProviderModelAdapter(env=KEYS).complete(MESSAGES, [])

    assert reply.text == "Let me quote that."
    assert reply.tool_calls == [QUOTE_TOOL_CALL]
    assert reply.provider == "anthropic"


def test_dashscope_tool_call_is_returned_in_the_message(monkeypatch):
    message = _dashscope_tool_call_message('{"corridor": "SG>BR", "amount": "1200"}')
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope([], message=message))

    reply = ProviderModelAdapter(env=dict(KEYS, MODEL_PROVIDER="dashscope")).complete(
        MESSAGES, []
    )

    assert reply.tool_calls == [QUOTE_TOOL_CALL]
    assert reply.provider == "dashscope"


def test_dashscope_tool_call_with_malformed_arguments_is_an_error(monkeypatch):
    message = _dashscope_tool_call_message('{"corridor": "SG>BR"')
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope([], message=message))

    adapter = ProviderModelAdapter(env=dict(KEYS, MODEL_PROVIDER="dashscope"))
    with pytest.raises(ModelAdapterError):
        adapter.complete(MESSAGES, [])


def test_refusal_is_an_error_and_does_not_switch_provider(monkeypatch):
    monkeypatch.setattr(
        anthropic, "Anthropic", _fake_anthropic([], content=[], stop_reason="refusal")
    )

    adapter = ProviderModelAdapter(env=KEYS)
    with pytest.raises(ModelAdapterError) as excinfo:
        adapter.complete(MESSAGES, [])

    assert not isinstance(excinfo.value, ProviderUnavailable)


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APIConnectionError(request=_anthropic_request()),
        anthropic.AuthenticationError(
            "invalid x-api-key",
            response=httpx2.Response(401, request=_anthropic_request()),
            body=None,
        ),
    ],
    ids=["connection", "auth"],
)
def test_primary_failure_falls_back_and_reports_the_provider(monkeypatch, error):
    anthropic_calls: list = []
    dashscope_calls: list = []
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls, error=error))
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope(dashscope_calls))

    reply = ProviderModelAdapter(env=KEYS).complete(MESSAGES, [])

    assert reply.text == "Aqui está a cotação."
    assert (reply.provider, reply.model) == ("dashscope", "qwen-plus")
    assert len(anthropic_calls) == 1
    assert len(dashscope_calls) == 1


def test_missing_primary_key_falls_back_before_any_sdk_call(monkeypatch):
    dashscope_calls: list = []
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope(dashscope_calls))

    reply = ProviderModelAdapter(
        env={"DASHSCOPE_API_KEY": "test-dashscope-key"}
    ).complete(MESSAGES, [])

    assert reply.provider == "dashscope"
    assert len(dashscope_calls) == 1


def test_missing_keys_on_both_providers_raise_a_clear_error():
    adapter = ProviderModelAdapter(env={})

    with pytest.raises(MissingApiKey, match="DASHSCOPE_API_KEY is not set"):
        adapter.complete(MESSAGES, [])


def test_dashscope_auth_status_falls_back_to_anthropic(monkeypatch):
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope([], status_code=401))
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic([]))

    reply = ProviderModelAdapter(
        env=dict(KEYS, MODEL_PROVIDER="dashscope", FALLBACK_MODEL_PROVIDER="anthropic")
    ).complete(MESSAGES, [])

    assert reply.text == "Here is the quote."
    assert reply.provider == "anthropic"


def test_fallback_is_tried_only_once(monkeypatch):
    anthropic_calls: list = []
    dashscope_calls: list = []
    error = anthropic.APIConnectionError(request=_anthropic_request())
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls, error=error))
    monkeypatch.setattr(
        dashscope.Generation, "call", _fake_dashscope(dashscope_calls, status_code=401)
    )

    adapter = ProviderModelAdapter(env=KEYS)
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

    adapter = ProviderModelAdapter(env=KEYS)
    with pytest.raises(anthropic.BadRequestError):
        adapter.complete(MESSAGES, [])
