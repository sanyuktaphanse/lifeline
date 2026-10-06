import anthropic
import dashscope
import pytest

GUARD = "A test reached a real provider SDK."


# This file declares no guard of its own, so these pass only because tests/conftest.py guards
# every test in the suite, whatever .env holds.


def test_constructing_an_anthropic_client_fails_under_the_guard():
    with pytest.raises(AssertionError, match=GUARD):
        anthropic.Anthropic(api_key="test-anthropic-key")


def test_a_dashscope_call_fails_under_the_guard():
    with pytest.raises(AssertionError, match=GUARD):
        dashscope.Generation.call(model="qwen-plus", api_key="test-dashscope-key", messages=[])
