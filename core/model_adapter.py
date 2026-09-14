import logging
import os
from collections.abc import Callable, Mapping, Sequence
from http import HTTPStatus
from typing import Any

import anthropic
import dashscope
import requests
from dashscope.common.error import AuthenticationError as DashScopeAuthenticationError
from dotenv import load_dotenv

from contracts.interfaces import ModelAdapter
from contracts.schemas import Message

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "anthropic"
DEFAULT_FALLBACK_PROVIDER = "dashscope"
# Source: Anthropic current models table, claude-api skill cached 2026-06-24.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
# Source: dashscope 1.27.3, dashscope.Generation.Models.qwen_plus.
DEFAULT_DASHSCOPE_MODEL = "qwen-plus"
# Source: Anthropic Python SDK guidance, 16000 keeps a non streaming request under the HTTP timeout.
ANTHROPIC_MAX_TOKENS = 16000
# Source: anthropic 1.3.0 BetaFallbacksParam, refusal fallback routed by category.
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Source: anthropic 1.3.0 _client.py raises a plain TypeError with this text when no credential is set.
ANTHROPIC_MISSING_CREDENTIALS = "Could not resolve authentication method"
AUTH_STATUSES = {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}


class ModelAdapterError(RuntimeError):
    pass


class ProviderUnavailable(ModelAdapterError):
    pass


def _setting(env: Mapping[str, str], name: str, default: str) -> str:
    return env.get(name) or default


def _call_anthropic(
    model: str, messages: Sequence[Message], tools: Sequence[dict[str, Any]]
) -> Message:
    system = "\n\n".join(m.text for m in messages if m.role == "system")
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "messages": [
            {"role": m.role, "content": m.text} for m in messages if m.role != "system"
        ],
        "betas": [ANTHROPIC_FALLBACK_BETA],
        "fallbacks": "default",
    }
    if system:
        request["system"] = system
    if tools:
        request["tools"] = list(tools)

    try:
        response = anthropic.Anthropic().beta.messages.create(**request)
    except (
        anthropic.APIConnectionError,
        anthropic.AuthenticationError,
        anthropic.PermissionDeniedError,
    ) as exc:
        raise ProviderUnavailable(f"anthropic: {exc}") from exc
    except TypeError as exc:
        if ANTHROPIC_MISSING_CREDENTIALS not in str(exc):
            raise
        raise ProviderUnavailable(f"anthropic: {exc}") from exc

    if response.stop_reason == "refusal":
        raise ModelAdapterError("anthropic declined the request on every fallback model.")
    if any(block.type == "tool_use" for block in response.content):
        raise ModelAdapterError(
            "anthropic answered with a tool call, which Message cannot carry yet."
        )
    return Message(
        role="assistant",
        text="".join(block.text for block in response.content if block.type == "text"),
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


def _call_dashscope(
    model: str, messages: Sequence[Message], tools: Sequence[dict[str, Any]]
) -> Message:
    request: dict[str, Any] = {
        "model": model,
        "messages": [{"role": m.role, "content": m.text} for m in messages],
        "result_format": "message",
    }
    if tools:
        request["tools"] = [_dashscope_tool(tool) for tool in tools]

    try:
        response = dashscope.Generation.call(**request)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        DashScopeAuthenticationError,
    ) as exc:
        raise ProviderUnavailable(f"dashscope: {exc}") from exc

    failure = f"dashscope: {response.status_code} {response.code} {response.message}"
    if response.status_code in AUTH_STATUSES:
        raise ProviderUnavailable(failure)
    if response.status_code != HTTPStatus.OK:
        raise ModelAdapterError(failure)

    message = response.output.choices[0].message
    if message.get("tool_calls"):
        raise ModelAdapterError(
            "dashscope answered with a tool call, which Message cannot carry yet."
        )
    return Message(role="assistant", text=message.get("content") or "")


_PROVIDERS: dict[
    str, Callable[[str, Sequence[Message], Sequence[dict[str, Any]]], Message]
] = {
    "anthropic": _call_anthropic,
    "dashscope": _call_dashscope,
}
_MODEL_SETTINGS = {
    "anthropic": ("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
    "dashscope": ("DASHSCOPE_MODEL", DEFAULT_DASHSCOPE_MODEL),
}


class ProviderModelAdapter(ModelAdapter):
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        if env is None:
            load_dotenv()
            env = os.environ
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
            name: _setting(env, variable, default)
            for name, (variable, default) in _MODEL_SETTINGS.items()
        }
        self.last_provider: str | None = None

    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]
    ) -> Message:
        self.last_provider = None
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
        reply = _PROVIDERS[provider](self._models[provider], messages, tools)
        self.last_provider = provider
        return reply
