from theshed.agents.models import (
    BOOTSTRAP_DEFAULT_MODEL,
    BOOTSTRAP_DEFAULT_PROVIDER,
    resolve_runtime_model,
)


def test_bootstrap_default_is_openai_gpt_4_1_mini() -> None:
    assert BOOTSTRAP_DEFAULT_PROVIDER == "openai"
    assert BOOTSTRAP_DEFAULT_MODEL == "gpt-4.1-mini"


def test_override_wins_when_it_matches_the_live_vendor() -> None:
    provider, model = resolve_runtime_model(
        client_vendor="openai",
        default_provider="openai",
        default_model="gpt-5.4",
        override_provider="openai",
        override_model="gpt-5.4-mini",
    )
    assert (provider, model) == ("openai", "gpt-5.4-mini")


def test_openai_client_does_not_send_a_claude_registry_default() -> None:
    provider, model = resolve_runtime_model(
        client_vendor="openai",
        default_provider="anthropic",
        default_model="claude-haiku-4-5",
    )
    assert (provider, model) == ("openai", "gpt-4.1-mini")


def test_anthropic_client_does_not_send_an_openai_registry_default() -> None:
    provider, model = resolve_runtime_model(
        client_vendor="anthropic",
        default_provider="openai",
        default_model="gpt-5.4",
    )
    assert (provider, model) == ("anthropic", "claude-haiku-4-5")


def test_registry_default_used_when_vendor_matches() -> None:
    provider, model = resolve_runtime_model(
        client_vendor="openai",
        default_provider="openai",
        default_model="gpt-4.1-mini",
    )
    assert (provider, model) == ("openai", "gpt-4.1-mini")
