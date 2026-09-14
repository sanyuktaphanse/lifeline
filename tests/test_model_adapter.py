import json
from types import SimpleNamespace

import anthropic
import dashscope
import httpx2
import pytest
from anthropic.types import TextBlock, ThinkingBlock, ToolUseBlock
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

USER_TEXT = "Quote 1,200 SGD to my landlord in Brazil"
MESSAGES = [Message(role="user", text=USER_TEXT)]
KEYS = {"ANTHROPIC_API_KEY": "test-anthropic-key", "DASHSCOPE_API_KEY": "test-dashscope-key"}
QUOTE_ARGUMENTS = {"corridor": "SG>BR", "amount": "1200"}
QUOTE_TOOL_CALL = ToolCall(id="toolu_01", name="quote_route", arguments=QUOTE_ARGUMENTS)
QUOTE_TOOL = {
    "name": "quote_route",
    "description": "Quote the routes for one corridor and amount.",
    "input_schema": {
        "type": "object",
        "properties": {"corridor": {"type": "string"}, "amount": {"type": "string"}},
        "required": ["corridor", "amount"],
    },
}
QUOTE_RESULT = json.dumps({"rail": "wise", "fee": "8.40"})


def _tool_result(call_id: str = "toolu_01", text: str = QUOTE_RESULT) -> Message:
    return Message(role="tool", source="tool_result", tool_call_id=call_id, text=text)


def _anthropic_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _text(text: str) -> TextBlock:
    return TextBlock(type="text", text=text)


def _quote_tool_use() -> ToolUseBlock:
    return ToolUseBlock(type="tool_use", id="toolu_01", name="quote_route", input=QUOTE_ARGUMENTS)


def _fake_anthropic(
    calls: list, *, content=None, stop_reason="end_turn", error=None, replies=None
):
    if replies is None:
        blocks = [_text("Here is the quote.")] if content is None else content
        replies = [(blocks, stop_reason)]
    queue = list(replies)

    class FakeAnthropic:
        def __init__(self, *, api_key=None, **kwargs):
            self.api_key = api_key
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            calls.append(dict(kwargs, _api_key=self.api_key))
            if error is not None:
                raise error
            blocks, reason = queue.pop(0) if len(queue) > 1 else queue[0]
            return SimpleNamespace(stop_reason=reason, content=blocks)

    return FakeAnthropic


def _fake_dashscope(calls: list, *, message=None, replies=None, status_code=200):
    if replies is None:
        replies = [message or {"role": "assistant", "content": "Aqui está a cotação."}]
    queue = list(replies)

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
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
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


def test_scripted_two_step_tool_loop_with_the_fake_adapter():
    fake = FakeModelAdapter(
        [
            Message(role="assistant", text="", tool_calls=[QUOTE_TOOL_CALL]),
            "Wise is cheapest at 8.40 SGD.",
        ]
    )
    tools = {"quote_route": lambda arguments: {"rail": "wise", "fee": "8.40"}}

    conversation = list(MESSAGES)
    reply = fake.complete(conversation, [QUOTE_TOOL])
    while reply.tool_calls:
        conversation.append(reply)
        for call in reply.tool_calls:
            result = tools[call.name](call.arguments)
            conversation.append(_tool_result(call.id, json.dumps(result)))
        reply = fake.complete(conversation, [QUOTE_TOOL])

    assert reply.text == "Wise is cheapest at 8.40 SGD."
    assert len(fake.calls) == 2
    second_turn = fake.calls[1][0]
    assert [message.role.value for message in second_turn] == ["user", "assistant", "tool"]
    assert second_turn[1].tool_calls == [QUOTE_TOOL_CALL]
    assert second_turn[2].tool_call_id == "toolu_01"
    assert second_turn[2].text == QUOTE_RESULT


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
    assert dashscope_calls[0]["messages"] == [{"role": "user", "content": USER_TEXT}]


def test_anthropic_answers_by_default_without_an_internal_fallback(monkeypatch):
    anthropic_calls: list = []
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls))

    adapter = ProviderModelAdapter(env=KEYS)
    reply = adapter.complete(MESSAGES, [])

    assert reply.text == "Here is the quote."
    assert (reply.provider, reply.model) == ("anthropic", "claude-opus-5")
    assert reply.provider_content == [{"type": "text", "text": "Here is the quote."}]
    call = anthropic_calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["_api_key"] == "test-anthropic-key"
    assert "fallbacks" not in call
    assert "betas" not in call
    assert call["messages"] == [{"role": "user", "content": USER_TEXT}]


def test_anthropic_tool_call_is_returned_in_the_message(monkeypatch):
    content = [_text("Let me quote that."), _quote_tool_use()]
    monkeypatch.setattr(
        anthropic, "Anthropic", _fake_anthropic([], content=content, stop_reason="tool_use")
    )

    reply = ProviderModelAdapter(env=KEYS).complete(MESSAGES, [])

    assert reply.text == "Let me quote that."
    assert reply.tool_calls == [QUOTE_TOOL_CALL]
    assert reply.provider == "anthropic"


def test_anthropic_round_trip_replays_the_assistant_turn_unchanged(monkeypatch):
    anthropic_calls: list = []
    step_one = [
        ThinkingBlock(type="thinking", thinking="", signature="sig-step-one"),
        _text("Let me quote that."),
        _quote_tool_use(),
    ]
    step_two = [_text("Wise is cheapest at 8.40 SGD.")]
    monkeypatch.setattr(
        anthropic,
        "Anthropic",
        _fake_anthropic(anthropic_calls, replies=[(step_one, "tool_use"), (step_two, "end_turn")]),
    )
    adapter = ProviderModelAdapter(env=KEYS)

    first = adapter.complete(MESSAGES, [QUOTE_TOOL])
    final = adapter.complete([*MESSAGES, first, _tool_result()], [QUOTE_TOOL])

    assert first.tool_calls == [QUOTE_TOOL_CALL]
    assert final.text == "Wise is cheapest at 8.40 SGD."
    assert anthropic_calls[1]["tools"] == [QUOTE_TOOL]
    assert anthropic_calls[1]["messages"] == [
        {"role": "user", "content": USER_TEXT},
        {"role": "assistant", "content": [block.to_dict() for block in step_one]},
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_01", "content": QUOTE_RESULT}
            ],
        },
    ]


def test_anthropic_rebuilds_a_turn_from_another_provider_and_groups_results(monkeypatch):
    anthropic_calls: list = []
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(anthropic_calls))
    second_call = ToolCall(id="toolu_02", name="quote_route", arguments={"corridor": "IN>SG"})
    conversation = [
        *MESSAGES,
        Message(
            role="assistant",
            text="",
            tool_calls=[QUOTE_TOOL_CALL, second_call],
            provider="dashscope",
            model="qwen-plus",
        ),
        _tool_result("toolu_01"),
        _tool_result("toolu_02", '{"rail": "upi_paynow"}'),
    ]

    ProviderModelAdapter(env=KEYS).complete(conversation, [QUOTE_TOOL])

    assert anthropic_calls[0]["messages"] == [
        {"role": "user", "content": USER_TEXT},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_01", "name": "quote_route", "input": QUOTE_ARGUMENTS},
                {"type": "tool_use", "id": "toolu_02", "name": "quote_route", "input": {"corridor": "IN>SG"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_01", "content": QUOTE_RESULT},
                {"type": "tool_result", "tool_use_id": "toolu_02", "content": '{"rail": "upi_paynow"}'},
            ],
        },
    ]


def test_dashscope_tool_call_is_returned_in_the_message(monkeypatch):
    message = _dashscope_tool_call_message(json.dumps(QUOTE_ARGUMENTS))
    monkeypatch.setattr(dashscope.Generation, "call", _fake_dashscope([], message=message))

    reply = ProviderModelAdapter(env=dict(KEYS, MODEL_PROVIDER="dashscope")).complete(
        MESSAGES, []
    )

    assert reply.tool_calls == [QUOTE_TOOL_CALL]
    assert reply.provider == "dashscope"


def test_dashscope_round_trip_sends_tool_calls_and_tool_results(monkeypatch):
    dashscope_calls: list = []
    replies = [
        _dashscope_tool_call_message(json.dumps(QUOTE_ARGUMENTS)),
        {"role": "assistant", "content": "A Wise é a mais barata, 8,40 SGD."},
    ]
    monkeypatch.setattr(
        dashscope.Generation, "call", _fake_dashscope(dashscope_calls, replies=replies)
    )
    adapter = ProviderModelAdapter(env=dict(KEYS, MODEL_PROVIDER="dashscope"))

    first = adapter.complete(MESSAGES, [QUOTE_TOOL])
    final = adapter.complete([*MESSAGES, first, _tool_result()], [QUOTE_TOOL])

    assert first.tool_calls == [QUOTE_TOOL_CALL]
    assert final.text == "A Wise é a mais barata, 8,40 SGD."
    assert dashscope_calls[1]["tools"][0]["function"]["name"] == "quote_route"
    assert dashscope_calls[1]["messages"] == [
        {"role": "user", "content": USER_TEXT},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "toolu_01",
                    "type": "function",
                    "function": {
                        "name": "quote_route",
                        "arguments": json.dumps(QUOTE_ARGUMENTS, ensure_ascii=False),
                    },
                }
            ],
        },
        {"role": "tool", "content": QUOTE_RESULT, "tool_call_id": "toolu_01"},
    ]


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
