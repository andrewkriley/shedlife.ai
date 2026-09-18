import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import OpenAI
from redis.asyncio import Redis

from theshed.agents.providers.anthropic import AnthropicClient
from theshed.auth.routes import router as auth_router
from theshed.observability.galileo import TurnTracer
from theshed.secrets.client import EnvVarSecretsClient, SecretNotFoundError
from theshed.settings.routes import router as settings_router
from theshed.turns.routes import router as turns_router

# Dev-only: loads a .env file into the process environment, so
# EnvVarSecretsClient can resolve secrets from it. Deliberately NOT a path
# hardcoded into this repo — theshed is the product, and where any given
# operator's real secrets live is tenant-specific (e.g. this project's own
# Fleet repo, not theshed itself; see "Product vs. tenant" in
# docs/architecture.md). THESHED_ENV_FILE points at it explicitly; with
# nothing set, falls back to python-dotenv's normal search from the current
# working directory. A real deployment has no .env to load at all — see
# docs/spec/secrets-management.md, "Secret zero's runtime home" (a
# Kubernetes Secret, injected directly).
load_dotenv(os.environ.get("THESHED_ENV_FILE"))

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

    # OpenAI isn't wired into any sub-agent yet (only Anthropic is), but the
    # settings surface's live models-list (docs/spec/core-agentic-loop.md)
    # calls it directly — so a missing/invalid key must not take down
    # startup, only make that one provider's list come back empty.
    try:
        openai_key = secrets.get("infisical://the-shed/providers/openai/api_key")
        app.state.openai_client = OpenAI(api_key=openai_key)
    except SecretNotFoundError:
        app.state.openai_client = None

    # The Galileo SDK reads GALILEO_API_KEY from the process environment
    # directly, under a name that doesn't match our own dev-mode env var
    # (GALILEO_THESHED_API) — bridge the two here rather than renaming the
    # existing credential.
    os.environ.setdefault(
        "GALILEO_API_KEY", secrets.get("infisical://the-shed/observability/galileo_api_key")
    )
    app.state.tracer_factory = lambda: TurnTracer.create(
        project=GALILEO_PROJECT, log_stream=GALILEO_LOG_STREAM
    )

    yield
    await app.state.redis.aclose()


app = FastAPI(title="The Shed", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(turns_router)
app.include_router(settings_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
