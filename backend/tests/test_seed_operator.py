import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.service import verify_password
from theshed.bootstrap.operator import DEFAULT_OPERATOR_EMAIL, seed_operator_from_env
from theshed.db.models import Identity


@pytest.mark.asyncio
async def test_seed_operator_creates_local_identity(db_session: AsyncSession) -> None:
    created = await seed_operator_from_env(
        db_session,
        environ={
            "THESHED_OPERATOR_EMAIL": DEFAULT_OPERATOR_EMAIL,
            "THESHED_OPERATOR_PASSWORD": "printed-once",
        },
    )
    assert created is True
    identity = (await db_session.execute(select(Identity))).scalar_one()
    assert identity.provider_user_id == DEFAULT_OPERATOR_EMAIL
    assert verify_password("printed-once", identity.password_hash)


@pytest.mark.asyncio
async def test_seed_operator_is_idempotent(db_session: AsyncSession) -> None:
    env = {
        "THESHED_OPERATOR_EMAIL": DEFAULT_OPERATOR_EMAIL,
        "THESHED_OPERATOR_PASSWORD": "printed-once",
    }
    assert await seed_operator_from_env(db_session, environ=env) is True
    assert await seed_operator_from_env(db_session, environ=env) is False
    count = int((await db_session.execute(select(func.count()).select_from(Identity))).scalar_one())
    assert count == 1
