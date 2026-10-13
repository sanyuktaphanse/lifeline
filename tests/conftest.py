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


@pytest.fixture(autouse=True)
def no_wise_sandbox_from_env(monkeypatch):
    """Keep every test off the Wise sandbox, whatever .env holds; a test that wants it passes a fake one.

    An empty value is set rather than the variable removed, because load_dotenv fills in a removed variable
    from .env but never overrides one that is set.
    """
    monkeypatch.setenv("WISE_SANDBOX_TOKEN", "")


@pytest.fixture(autouse=True)
def no_app_passphrase_from_env(monkeypatch):
    """Keep every test off the API passphrase, whatever .env holds; a test that wants one sets it.

    An empty value is set rather than the variable removed, for the same reason as above.
    """
    monkeypatch.setenv("LIFELINE_APP_PASSPHRASE", "")
