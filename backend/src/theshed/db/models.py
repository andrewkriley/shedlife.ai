import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Every _now() default is tz-aware (datetime.now(timezone.utc)); the column
# type must be too, or asyncpg rejects the insert ("can't subtract
# offset-naive and offset-aware datetimes") — Postgres's plain TIMESTAMP
# (SQLAlchemy's bare DateTime default) is timezone-naive.
TZDateTime = DateTime(timezone=True)


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)

    identities: Mapped[list["Identity"]] = relationship(back_populates="user")


class Identity(Base):
    """One row per way a user can authenticate — local password today, OAuth
    providers later. See docs/spec/auth.md.

    Correction from the original SPEC draft: `provider_user_id` is not
    "not applicable" for `local` — it has to hold *something* to look the
    identity up by (the email/username used to log in). For an OAuth
    provider it holds that provider's own user id instead. Unified: it's
    always "however this identity is identified by its provider."
    """

    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(32))  # "local" | "google" | "github"
    provider_user_id: Mapped[str] = mapped_column(String(255))  # email, for "local"
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="identities")


class SubAgent(Base):
    """A registry entry, per docs/spec/core-agentic-loop.md. id is
    "<macro>.<name>" (e.g. "assist"), not a UUID."""

    __tablename__ = "sub_agents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    macro_category: Mapped[str] = mapped_column(String(16))  # "assist" | "build" | "run"
    description: Mapped[str] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text)
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    default_provider: Mapped[str] = mapped_column(String(32))
    default_model: Mapped[str] = mapped_column(String(128))
    provenance: Mapped[str] = mapped_column(String(16), default="manual")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)


class SubAgentModelOverride(Base):
    """An override is its own record, not a mutation of SubAgent's own
    default_provider/default_model — the registry default is never lost,
    and clearing an override just means deleting this row. See
    docs/spec/core-agentic-loop.md, Data section. Absence of a row for a
    given sub_agent_id means "use the registry default"."""

    __tablename__ = "sub_agent_model_overrides"

    sub_agent_id: Mapped[str] = mapped_column(ForeignKey("sub_agents.id"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    set_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    set_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    galileo_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)

    turns: Mapped[list["Turn"]] = relationship(back_populates="conversation")


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    user_message: Mapped[str] = mapped_column(Text)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    galileo_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="turns")
    sub_agent_results: Mapped[list["TurnSubAgentResult"]] = relationship(back_populates="turn")


class TurnSubAgentResult(Base):
    """One row per sub-agent matched in a turn. Never replayed as future
    conversation context — only Turn.final_response is. See
    docs/spec/core-agentic-loop.md, Data section."""

    __tablename__ = "turn_sub_agent_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    turn_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("turns.id"))
    sub_agent_id: Mapped[str] = mapped_column(ForeignKey("sub_agents.id"))
    result: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(default=0)

    turn: Mapped[Turn] = relationship(back_populates="sub_agent_results")


class TurnVerification(Base):
    """One row per manual verifier invocation against a turn. See
    docs/spec/core-agentic-loop.md, Data section."""

    __tablename__ = "turn_verifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    turn_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("turns.id"))
    result: Mapped[str] = mapped_column(Text)
    galileo_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invoked_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    invoked_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
