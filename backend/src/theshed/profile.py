"""Runtime profile, per docs/architecture.md and docs/spec/bootstrap.md.

`bootstrap` is the Phase 1 control-plane profile: one intake agent, local
secret-zero, LAN cookies without Secure. `full` is the living harness.
"""

from __future__ import annotations

import os

BOOTSTRAP_SUB_AGENT_ID = "bootstrap.intake"
PROFILE_ENV = "THESHED_PROFILE"
COOKIE_SECURE_ENV = "THESHED_COOKIE_SECURE"


def current_profile() -> str:
    value = os.environ.get(PROFILE_ENV, "full").strip().lower()
    return "bootstrap" if value == "bootstrap" else "full"


def is_bootstrap_profile() -> bool:
    return current_profile() == "bootstrap"


def cookie_secure() -> bool:
    """Bootstrap profile is HTTP on the LAN — Secure cookies would never be
    sent. An explicit THESHED_COOKIE_SECURE overrides the profile default."""
    explicit = os.environ.get(COOKIE_SECURE_ENV)
    if explicit is not None:
        return explicit.strip().lower() in {"1", "true", "yes"}
    return not is_bootstrap_profile()
