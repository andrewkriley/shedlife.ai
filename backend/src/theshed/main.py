import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from theshed.agents.providers.anthropic import AnthropicClient
from theshed.auth.routes import router as auth_router
from theshed.observability.galileo import TurnTracer
from theshed.secrets.client import EnvVarSecretsClient
from theshed.turns.routes import router as turns_router

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CLASSIFIER_MODEL = os.environ.get("CLASSIFIER_MODEL", "claude-haiku-4-5")
GALILEO_PROJECT = os.environ.get("GALILEO_PROJECT", "the-shed")
GALILEO_LOG_STREAM = os.environ.get("GALILEO_LOG_STREAM", "default")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = Redis.from_url(REDIS_URL)

    secrets = EnvVarSecretsClient()
    anthropic_key = secrets.get("infisical://the-shed/providers/anthropic/api_key")
    app.state.llm_client = AnthropicClient(api_key=anthropic_key)
    app.state.classifier_model = CLASSIFIER_MODEL

    # The Galileo SDK reads GALILEO_API_KEY from the process environment
    # directly, under a name that doesn't match our own dev-mode env var
    # (GALILEO_THESHED_API) — bridge the two here rather than renaming the
    # existing credential.
    os.environ.setdefault(
        "GALILEO_API_KEY", secrets.get("infisical://the-shed/observability/galileo_api_key")
    )
    app.state.tracer_factory = lambda: TurnTracer(
        project=GALILEO_PROJECT, log_stream=GALILEO_LOG_STREAM
    )

    yield
    await app.state.redis.aclose()


app = FastAPI(title="The Shed", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(turns_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
