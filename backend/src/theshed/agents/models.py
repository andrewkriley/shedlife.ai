"""Which model a live LLM client should call.

The registry default and a Settings override can name a different vendor
than the key that is actually configured. Chat must follow the live client,
not send `claude-*` to OpenAI (or the reverse).
"""

from __future__ import annotations

VENDOR_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-4-5",
    "openai": "o4-mini",
    "gemini": "gemini-2.5-flash",
}

BOOTSTRAP_DEFAULT_PROVIDER = "openai"
BOOTSTRAP_DEFAULT_MODEL = VENDOR_DEFAULT_MODELS["openai"]


def resolve_runtime_model(
    *,
    client_vendor: str | None,
    default_provider: str,
    default_model: str,
    override_provider: str | None = None,
    override_model: str | None = None,
) -> tuple[str, str]:
    """Return `(provider, model)` for the live client.

    Prefer a Settings override when it matches the live vendor. Otherwise
    use the registry default when that vendor matches. If the live client
    is a different vendor, fall back to that vendor's bootstrap default
    rather than sending an impossible model id.
    """
    vendor = (client_vendor or override_provider or default_provider or "").strip() or None
    if vendor is None:
        return default_provider, default_model
    if override_provider == vendor and override_model:
        return vendor, override_model
    if default_provider == vendor and default_model:
        return vendor, default_model
    return vendor, VENDOR_DEFAULT_MODELS.get(vendor, default_model)
