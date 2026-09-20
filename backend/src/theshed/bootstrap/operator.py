"""Seed the installer-generated operator identity on first boot."""

from __future__ import annotations

import os
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.service import hash_password
from theshed.bootstrap.install_state import DEFAULT_OPERATOR_USERNAME
from theshed.db.models import Identity, User
from theshed.debug import log as debug_log

USERNAME_ENV = "THESHED_OPERATOR_USERNAME"
EMAIL_ENV = "THESHED_OPERATOR_EMAIL"
PASSWORD_ENV = "THESHED_OPERATOR_PASSWORD"
DEFAULT_OPERATOR_EMAIL = DEFAULT_OPERATOR_USERNAME


def operator_username(environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    return (env.get(USERNAME_ENV) or env.get(EMAIL_ENV) or DEFAULT_OPERATOR_USERNAME).strip()


async def seed_operator_from_env(
    db: AsyncSession,
    environ: Mapping[str, str] | None = None,
) -> bool:
    env = environ if environ is not None else os.environ
    username = operator_username(env)
    password = (env.get(PASSWORD_ENV) or "").strip()
    if not password:
        return False

    count = int((await db.execute(select(func.count()).select_from(Identity))).scalar_one())
    if count > 0:
        return False

    user = User(display_name=username)
    db.add(user)
    await db.flush()
    db.add(
        Identity(
            user_id=user.id,
            provider="local",
            provider_user_id=username,
            password_hash=hash_password(password),
        )
    )
    await db.commit()
    debug_log.record("auth", "seed", f"Seeded operator {username}")
    return True
