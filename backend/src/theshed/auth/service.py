"""Password hashing and session management, per docs/spec/auth.md.

Sessions are server-side state in Redis (not a self-contained JWT), so
revocation (logout) actually invalidates immediately rather than waiting on
a token's own expiry.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from redis.asyncio import Redis

_hasher = PasswordHasher()

SESSION_TTL = timedelta(days=7)
SESSION_KEY_PREFIX = "session:"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


@dataclass
class SessionStore:
    redis_client: Redis

    async def create(self, user_id: str) -> str:
        session_id = secrets.token_urlsafe(32)
        await self.redis_client.set(
            f"{SESSION_KEY_PREFIX}{session_id}",
            user_id,
            ex=int(SESSION_TTL.total_seconds()),
        )
        return session_id

    async def get_user_id(self, session_id: str) -> str | None:
        value = await self.redis_client.get(f"{SESSION_KEY_PREFIX}{session_id}")
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value

    async def invalidate(self, session_id: str) -> None:
        await self.redis_client.delete(f"{SESSION_KEY_PREFIX}{session_id}")
