"""Never put secret values or raw probe payloads in an issue body."""

from __future__ import annotations

import re

SECRET_RE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{10,}"
    r"|local://[A-Za-z0-9_./-]+(?:=[^\s]+)?)"
)


def looks_like_secret(text: str) -> bool:
    return SECRET_RE.search(text) is not None


def redact(text: str) -> str:
    return SECRET_RE.sub("[redacted]", text)


def classify_and_redact(message: str) -> tuple[str, str]:
    lowered = message.lower()
    if "must match" in lowered or "required" in lowered or "invalid" in lowered:
        classification = "operator-input"
    elif "socket" in lowered or "timeout" in lowered or "refused" in lowered:
        classification = "environment"
    else:
        classification = "product-bug"
    return classification, redact(message)
