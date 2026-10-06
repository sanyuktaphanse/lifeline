import json
import logging
import os
from collections.abc import Callable, Mapping, Sequence
from http import HTTPStatus
from typing import Any

import anthropic
import dashscope
import requests
from dashscope.common.error import RequestFailure
from dotenv import load_dotenv

from contracts.interfaces import ModelAdapter
from contracts.schemas import Message, Role, ToolCall

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "anthropic"
DEFAULT_FALLBACK_PROVIDER = "dashscope"
# Source: Anthropic current models table, claude-api skill cached 2026-06-24.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
# Source: dashscope 1.27.3, dashscope.Generation.Models.qwen_plus.
DEFAULT_DASHSCOPE_MODEL = "qwen-plus"
# Source: Anthropic Python SDK guidance, 16000 keeps a non streaming request under the HTTP timeout.
ANTHROPIC_MAX_TOKENS = 16000
# Source: project decision on 14 September 2026 to cap DashScope replies at 2048 tokens.
DASHSCOPE_MAX_TOKENS = 2048
AUTH_STATUSES = {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}
REDACTED = "[redacted]"
# The council may run on a different model from the loop's. Each name below replaces the
# ordinary one when it is set, so the council needs no provider code of its own.
COUNCIL_MODEL_VARIABLES = {
    "ANTHROPIC_MODEL": "ANTHROPIC_COUNCIL_MODEL",
    "DASHSCOPE_MODEL": "DASHSCOPE_COUNCIL_MODEL",
}


class ModelAdapterError(RuntimeError):
    """A provider failure, naming the provider and the status it answered with when there was one."""

    def __init__(
        self, message: str, provider: str | None = None, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ProviderUnavailable(ModelAdapterError):
    pass


class MissingApiKey(ProviderUnavailable):
    pass


def _setting(env: Mapping[str, str], name: str, default: str) -> str:
    return env.get(name) or default


def environment(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    """The settings a component reads: the ones given, or the process environment with .env loaded.

    Passing an environment is how a test, or a component that wants different models, keeps out of
    the process environment altogether.
    """
    if env is None:
        load_dotenv()
        return os.environ
    return env


def _status_failure(
    error_class: type[ModelAdapterError],
    provider: str,
    status_code: int,
    detail: str,
    api_key: str,
) -> ModelAdapterError:
    """An error carrying the provider, the status and the provider's own words, never the key."""
    message = f"{provider}: {status_code} {detail}".replace(api_key, REDACTED)
    return error_class(message, provider=provider, status_code=status_code)


def _anthropic_assistant_content(message: Message) -> str | list[dict[str, Any]]:
    # Source: claude-api skill model migration guide, an Anthropic assistant turn goes
    # back exactly as received so its thinking blocks stay valid for the next turn.
    if message.provider == "anthropic" and message.provider_content is not None:
        return list(message.provider_content)
    if not message.tool_calls:
        return message.text
    blocks: list[dict[str, Any]] = []
    if message.text:
        blocks.append({"type": "text", "text": message.text})
    blocks.extend(
        {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
        for call in message.tool_calls
    )
    return blocks


def _anthropic_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for message in messages:
        if message.role is Role.SYSTEM:
            continue
        if message.role is Role.ASSISTANT:
            turns.append(
                {"role": "assistant", "content": _anthropic_assistant_content(message)}
            )
            continue
        if message.role is Role.TOOL:
            block = {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id,
                "content": message.text,
            }
            previous = turns[-1] if turns else None
            # Source: claude-api skill, every tool result for one assistant turn goes
            # back in a single user message.
            if (
                previous is not None
                and previous["role"] == "user"
                and isinstance(previous["content"], list)
                and previous["content"][-1]["type"] == "tool_result"
            ):
                previous["content"].append(block)
            else:
                turns.append({"role": "user", "content": [block]})
            continue
        turns.append({"role": "user", "content": message.text})
    return turns


def _call_anthropic(
    model: str,
    api_key: str,
    messages: Sequence[Message],
    tools: Sequence[dict[str, Any]],
) -> Message:
    system = "\n\n".join(m.text for m in messages if m.role is Role.SYSTEM)
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "messages": _anthropic_messages(messages),
    }
    if system:
        request["system"] = system
    if tools:
        request["tools"] = list(tools)

    try:
        response = anthropic.Anthropic(api_key=api_key).messages.create(**request)
    except anthropic.APIConnectionError as exc:
        raise ProviderUnavailable(f"anthropic: {exc}", provider="anthropic") from exc
    except anthropic.APIStatusError as exc:
        # Every status the SDK raises becomes the adapter's own error, so nothing else reaches a
        # caller. Only 401 and 403 mean the provider is unavailable and switch to the fallback.
        # The SDK error is not chained, because its request still holds the key in its headers.
        error_class = ProviderUnavailable if exc.status_code in AUTH_STATUSES else ModelAdapterError
        raise _status_failure(
            error_class, "anthropic", exc.status_code, exc.message, api_key
        ) from None

    if response.stop_reason == "refusal":
        raise ModelAdapterError("anthropic declined the request.")
    return Message(
        role=Role.ASSISTANT,
        text="".join(block.text for block in response.content if block.type == "text"),
        tool_calls=[
            ToolCall(id=block.id, name=block.name, arguments=block.input)
            for block in response.content
            if block.type == "tool_use"
        ],
        provider="anthropic",
        model=model,
        provider_content=[block.to_dict() for block in response.content],
    )


def _dashscope_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {}),
        },
    }


def _dashscope_message(message: Message) -> dict[str, Any]:
    # Source: dashscope 1.27.3 acli/providers/adapter.py, tool results are tool messages
    # correlated by tool_call_id and assistant turns keep their tool_calls.
    if message.role is Role.TOOL:
        return {"role": "tool", "content": message.text, "tool_call_id": message.tool_call_id}
    if message.role is Role.ASSISTANT and message.tool_calls:
        return {
            "role": "assistant",
            "content": message.text or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ],
        }
    return {"role": message.role.value, "content": message.text}


def _dashscope_tool_call(call: Mapping[str, Any]) -> ToolCall:
    function = call["function"]
    try:
        arguments = json.loads(function["arguments"] or "{}")
    except json.JSONDecodeError as exc:
        raise ModelAdapterError(
            f"dashscope tool call {call['id']} has arguments that are not valid JSON."
        ) from exc
    if not isinstance(arguments, dict):
        raise ModelAdapterError(
            f"dashscope tool call {call['id']} has arguments that are not a JSON object."
        )
    return ToolCall(id=call["id"], name=function["name"], arguments=arguments)


def _call_dashscope(
    model: str,
    api_key: str,
    messages: Sequence[Message],
    tools: Sequence[dict[str, Any]],
    base_url: str | None = None,
) -> Message:
    request: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "messages": [_dashscope_message(m) for m in messages],
        "result_format": "message",
        "max_tokens": DASHSCOPE_MAX_TOKENS,
    }
    if tools:
        request["tools"] = [_dashscope_tool(tool) for tool in tools]
    if base_url:
        # Source: dashscope 1.27.3 client/base_api.py, base_address replaces
        # dashscope.base_http_api_url for this one call, so no process wide setting changes.
        request["base_address"] = base_url

    try:
        response = dashscope.Generation.call(**request)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        raise ProviderUnavailable(f"dashscope: {exc}", provider="dashscope") from exc
    except RequestFailure as exc:
        error_class = ProviderUnavailable if exc.http_code in AUTH_STATUSES else ModelAdapterError
        raise _status_failure(
            error_class, "dashscope", exc.http_code, f"{exc.name} {exc.message}", api_key
        ) from None

    if response.status_code != HTTPStatus.OK:
        error_class = (
            ProviderUnavailable if response.status_code in AUTH_STATUSES else ModelAdapterError
        )
        raise _status_failure(
            error_class,
            "dashscope",
            response.status_code,
            f"{response.code} {response.message}",
            api_key,
        )

    message = response.output.choices[0].message
    return Message(
        role=Role.ASSISTANT,
        text=message.get("content") or "",
        tool_calls=[_dashscope_tool_call(call) for call in message.get("tool_calls") or []],
        provider="dashscope",
        model=model,
    )


_PROVIDERS: dict[str, Callable[..., Message]] = {
    "anthropic": _call_anthropic,
    "dashscope": _call_dashscope,
}
_PROVIDER_SETTINGS = {
    "anthropic": ("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL, "ANTHROPIC_API_KEY"),
    "dashscope": ("DASHSCOPE_MODEL", DEFAULT_DASHSCOPE_MODEL, "DASHSCOPE_API_KEY"),
}
# A Model Studio key works only against the endpoint of the region it was created in. The URL is
# never written here; docs/technical-reference.md cites the page that lists each region's endpoint.
_PROVIDER_BASE_URLS = {"dashscope": "DASHSCOPE_BASE_URL"}


class ProviderModelAdapter(ModelAdapter):
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        env = environment(env)
        self._env = env
        self.provider = _setting(env, "MODEL_PROVIDER", DEFAULT_PROVIDER)
        self.fallback_provider = _setting(
            env, "FALLBACK_MODEL_PROVIDER", DEFAULT_FALLBACK_PROVIDER
        )
        for name in (self.provider, self.fallback_provider):
            if name not in _PROVIDERS:
                raise ValueError(
                    f"Unknown model provider {name!r}. Expected one of {sorted(_PROVIDERS)}."
                )
        self._models = {
            name: _setting(env, model_variable, default)
            for name, (model_variable, default, _) in _PROVIDER_SETTINGS.items()
        }

    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]
    ) -> Message:
        try:
            return self._ask(self.provider, messages, tools)
        except ProviderUnavailable as exc:
            logger.warning(
                "Model provider %s unavailable, retrying once on %s: %s",
                self.provider,
                self.fallback_provider,
                exc,
            )
            return self._ask(self.fallback_provider, messages, tools)

    def _ask(
        self,
        provider: str,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
    ) -> Message:
        key_variable = _PROVIDER_SETTINGS[provider][2]
        api_key = self._env.get(key_variable)
        if not api_key:
            raise MissingApiKey(
                f"{key_variable} is not set. Add it to .env to use {provider}."
            )
        extra: dict[str, str] = {}
        base_url_variable = _PROVIDER_BASE_URLS.get(provider)
        if base_url_variable and self._env.get(base_url_variable):
            extra["base_url"] = self._env[base_url_variable]
        return _PROVIDERS[provider](self._models[provider], api_key, messages, tools, **extra)


def council_env(env: Mapping[str, str]) -> dict[str, str]:
    """The environment a council adapter reads: the given one with the council models in place.

    A council model variable that is unset or empty changes nothing, so a council with no
    variables of its own runs on the same models as the loop.
    """
    overlaid = dict(env)
    for ordinary, council in COUNCIL_MODEL_VARIABLES.items():
        if env.get(council):
            overlaid[ordinary] = env[council]
    return overlaid


def council_adapter(env: Mapping[str, str] | None = None) -> ProviderModelAdapter:
    """An adapter for the council, separate from the loop's, so its calls are its own."""
    return ProviderModelAdapter(council_env(environment(env)))
