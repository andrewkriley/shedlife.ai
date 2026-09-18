"""Creates the one dev-admin account for local use.

Dev-only stand-in for the real mechanism: per docs/spec/auth.md, the first
user on a real tenant deployment is seeded through the same
declarative-config apply step as the rest of that tenant's Fleet state —
that depends on Bootstrap/Fleet, which doesn't exist yet. This script is a
placeholder until it does, not the production path.
"""

import asyncio
import sys

from sqlalchemy import select

from theshed.auth.service import hash_password
from theshed.db.models import Identity, User
from theshed.db.session import async_session_factory

DEV_EMAIL = "dev@example.com"
DEV_PASSWORD = "dev-password-change-me"


async def seed() -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Identity).where(Identity.provider == "local", Identity.provider_user_id == DEV_EMAIL)
        )
        if result.scalar_one_or_none() is not None:
            print(f"Dev user {DEV_EMAIL!r} already exists — nothing to do.")
            return

        user = User(display_name="Dev Admin")
        db.add(user)
        await db.flush()
        db.add(
            Identity(
                user_id=user.id,
                provider="local",
                provider_user_id=DEV_EMAIL,
                password_hash=hash_password(DEV_PASSWORD),
            )
        )
        await db.commit()
        print(f"Created dev user: {DEV_EMAIL} / {DEV_PASSWORD}")


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as exc:  # noqa: BLE001 — a CLI script, not library code
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
