"""Provider + API key checks for the setup gate."""

from __future__ import annotations

from collections.abc import Callable

SUPPORTED = ("anthropic", "openai", "gemini")

Validator = Callable[[str], None]


class ProviderRejected(ValueError):
    pass


def looks_like_subscription(key: str) -> bool:
    stripped = key.strip().lower()
    if not stripped:
        return False
    return (
        "subscription" in stripped
        or stripped.startswith("claude.ai")
        or "console.anthropic.com/login" in stripped
    )


def reject_if_not_api_key(vendor: str, key: str) -> None:
    if vendor not in SUPPORTED:
        raise ProviderRejected(f"Unsupported provider: {vendor}")
    if looks_like_subscription(key):
        raise ProviderRejected(
            "A Claude subscription will not work. Use an Anthropic, OpenAI, or Gemini API key."
        )
    if vendor == "anthropic" and not key.strip().startswith("sk-ant-"):
        raise ProviderRejected(
            "That does not look like an Anthropic API key. A Claude subscription will not work."
        )
    if vendor == "openai" and not key.strip().startswith("sk-"):
        raise ProviderRejected("That does not look like an OpenAI API key.")


def validate_api_key(
    vendor: str,
    key: str,
    live_check: Validator | None = None,
) -> None:
    reject_if_not_api_key(vendor, key)
    if live_check is not None:
        live_check(key)
