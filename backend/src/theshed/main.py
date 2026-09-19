import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import OpenAI
from redis.asyncio import Redis

from theshed.agents.mcp_tools import call_mcp_tool
from theshed.agents.providers.anthropic import AnthropicClient
from theshed.agents.tool_loop import ToolCall
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
# GALILEO_PROJECT_NAME, not GALILEO_PROJECT — matches this tenant's .env,
# not the Galileo SDK's own env var name (which is bridged separately
# below, same reasoning as the API key bridge).
GALILEO_PROJECT = os.environ.get("GALILEO_PROJECT_NAME", "the-shed")
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

    # The Galileo SDK reads GALILEO_API_KEY and GALILEO_CONSOLE_URL directly
    # from the process environment (pydantic-settings, env_prefix="GALILEO_")
    # rather than accepting them as constructor arguments — bridged via the
    # secrets client here rather than read from os.environ directly, so a
    # real Infisical-backed client later is a constructor swap, not a
    # call-site change. Confirmed live: without GALILEO_CONSOLE_URL set, the
    # SDK silently defaults to the public app.galileo.ai instead of this
    # tenant's actual (self-hosted-equivalent) multitenant instance — every
    # trace 401'd there, never at the real instance the API key is valid for.
    os.environ.setdefault(
        "GALILEO_API_KEY", secrets.get("infisical://the-shed/observability/galileo_api_key")
    )
    os.environ.setdefault(
        "GALILEO_CONSOLE_URL", secrets.get("infisical://the-shed/observability/galileo_console_url")
    )
    # get_or_create_session_id() (see observability/galileo.py) calls the
    # SDK's own top-level start_session() outside any explicit
    # galileo_context(...) block, per cl-ai-builders' own pattern (a
    # conversation's session has to exist before its first turn's trace
    # does) — that resolves project/log_stream from GALILEO_PROJECT/
    # GALILEO_LOG_STREAM env vars, not from a passed-in argument, so those
    # need bridging here same as the API key/console URL above.
    os.environ.setdefault("GALILEO_PROJECT", GALILEO_PROJECT)
    os.environ.setdefault("GALILEO_LOG_STREAM", GALILEO_LOG_STREAM)
    app.state.tracer_factory = lambda: TurnTracer.create(
        project=GALILEO_PROJECT, log_stream=GALILEO_LOG_STREAM
    )

    # run.network's tools are all unifi-mcp's — the only client-executed
    # tool source that exists yet, so this is a universal dispatcher for
    # now (see agents/orchestrator.py's _execute_tool docstring). A
    # missing/invalid credential degrades to no dispatcher at all, same
    # posture as the OpenAI client above — run.network stays registered
    # and its tools still pause for approval correctly, they just can't
    # execute once approved.
    try:
        unifi_url = secrets.get("infisical://the-shed/mcp/unifi_url")
        unifi_token = secrets.get("infisical://the-shed/mcp/unifi_bearer_token")

        async def tool_executor(call: ToolCall) -> str:
            return await call_mcp_tool(unifi_url, unifi_token, call.tool_name, call.arguments)

        app.state.tool_executor = tool_executor
    except SecretNotFoundError:
        app.state.tool_executor = None

    yield
    await app.state.redis.aclose()


app = FastAPI(title="The Shed", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(turns_router)
app.include_router(settings_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
