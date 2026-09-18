import pytest
from redis.asyncio import Redis

from theshed.auth.service import SessionStore, hash_password, verify_password


class TestPasswordHashing:
    def test_verify_succeeds_for_correct_password(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed) is True

    def test_verify_fails_for_wrong_password(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert verify_password("wrong password", hashed) is False

    def test_hash_is_not_the_plaintext(self) -> None:
        hashed = hash_password("hunter2")
        assert hashed != "hunter2"

    def test_hash_uses_argon2id(self) -> None:
        hashed = hash_password("hunter2")
        assert hashed.startswith("$argon2id$")


@pytest.mark.asyncio
class TestSessionStore:
    async def test_create_then_get_returns_the_user_id(self, redis_client: Redis) -> None:
        store = SessionStore(redis_client)
        session_id = await store.create(user_id="user-123")

        assert await store.get_user_id(session_id) == "user-123"

    async def test_unknown_session_id_returns_none(self, redis_client: Redis) -> None:
        store = SessionStore(redis_client)
        assert await store.get_user_id("nonexistent") is None

    async def test_invalidate_removes_the_session(self, redis_client: Redis) -> None:
        store = SessionStore(redis_client)
        session_id = await store.create(user_id="user-123")

        await store.invalidate(session_id)

        assert await store.get_user_id(session_id) is None

    async def test_two_sessions_get_distinct_ids(self, redis_client: Redis) -> None:
        store = SessionStore(redis_client)
        first = await store.create(user_id="user-123")
        second = await store.create(user_id="user-123")

        assert first != second
