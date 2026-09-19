import pytest

from theshed.setup.providers import ProviderRejected, looks_like_subscription, validate_api_key


def test_subscription_word_is_rejected() -> None:
    assert looks_like_subscription("claude subscription")
    with pytest.raises(ProviderRejected, match="subscription will not work"):
        validate_api_key("anthropic", "claude subscription")


def test_anthropic_key_must_look_like_an_api_key() -> None:
    with pytest.raises(ProviderRejected, match="does not look like"):
        validate_api_key("anthropic", "not-a-key")


def test_valid_looking_key_passes_without_live_check() -> None:
    validate_api_key("anthropic", "sk-ant-api03-test")


def test_live_check_failure_stays_on_the_gate() -> None:
    def boom(_key: str) -> None:
        raise ProviderRejected("provider rejected the key")

    with pytest.raises(ProviderRejected, match="provider rejected"):
        validate_api_key("anthropic", "sk-ant-api03-test", live_check=boom)


def test_unknown_vendor_rejected() -> None:
    with pytest.raises(ProviderRejected, match="Unsupported"):
        validate_api_key("cohere", "abc")
