import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import OpenAI
from redis.asyncio import Redis
from starlette.types import ASGIApp, Receive, Scope, Send

from theshed.agents.mcp_tools import call_mcp_tool
from theshed.agents.models import BOOTSTRAP_DEFAULT_MODEL, VENDOR_DEFAULT_MODELS
from theshed.agents.providers.anthropic import AnthropicClient
from theshed.agents.providers.openai import OpenAIClient
from theshed.agents.tool_loop import ToolCall
from theshed.auth.routes import router as auth_router
from theshed.bootstrap.operator import seed_operator_from_env
from theshed.bootstrap.tools import make_bootstrap_tool_executor
from theshed.db.session import async_session_factory
from theshed.debug import log as debug_log
from theshed.debug.middleware import DebugHttpMiddleware
from theshed.debug.routes import router as debug_router
from theshed.foundations.routes import router as foundations_router
from theshed.issues.routes import router as issues_router
from theshed.observability.galileo import TurnTracer
from theshed.probes.host import DefaultProbeHost
from theshed.profile import is_bootstrap_profile
from theshed.secrets.client import EnvVarSecretsClient, LocalSecretsClient, SecretNotFoundError
from theshed.settings.galileo import apply_galileo_runtime
from theshed.settings.routes import router as settings_router
from theshed.setup.routes import router as setup_router
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
CLASSIFIER_MODEL = os.environ.get("CLASSIFIER_MODEL", BOOTSTRAP_DEFAULT_MODEL)
# GALILEO_PROJECT_NAME, not GALILEO_PROJECT — matches this tenant's .env,
# not the Galileo SDK's own env var name (which is bridged separately
# below, same reasoning as the API key bridge).
GALILEO_PROJECT = os.environ.get("GALILEO_PROJECT_NAME", "the-shed")
GALILEO_LOG_STREAM = os.environ.get("GALILEO_LOG_STREAM", "default")


def _configure_llm(app: FastAPI, provider: str, api_key: str) -> None:
    app.state.llm_client = None
    if provider == "anthropic":
        app.state.llm_client = AnthropicClient(api_key=api_key)
        app.state.classifier_model = VENDOR_DEFAULT_MODELS["anthropic"]
        debug_log.record("llm", "configure", "Configured anthropic client")
        return
    if provider == "openai":
        client = OpenAIClient(api_key=api_key)
        app.state.llm_client = client
        app.state.openai_client = client
        app.state.classifier_model = VENDOR_DEFAULT_MODELS["openai"]
        debug_log.record("llm", "configure", "Configured openai client")
        return
    # Gemini is listed in Settings; chat still needs a native client.
    debug_log.record(
        "llm",
        "configure",
        f"No chat client for {provider}",
        level="error",
        detail={"provider": provider},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = Redis.from_url(REDIS_URL)
    app.state.classifier_model = CLASSIFIER_MODEL
    app.state.configure_llm = lambda provider, key: _configure_llm(app, provider, key)

    if is_bootstrap_profile():
        secrets_path = os.environ.get("THESHED_LOCAL_SECRETS_PATH")
        secrets: EnvVarSecretsClient | LocalSecretsClient = LocalSecretsClient(path=secrets_path)
        app.state.secrets = secrets
        app.state.llm_client = None
        app.state.openai_client = None
        try:
            vendor = secrets.get("local://providers/llm/vendor")
            key = secrets.get("local://providers/llm/api_key")
            _configure_llm(app, vendor, key)
        except SecretNotFoundError:
            pass
        apply_galileo_runtime(app.state, secrets)
        app.state.probe_host = DefaultProbeHost(secrets=secrets)
        app.state.tool_executor = None
        app.state.tool_executor_factory = lambda db: make_bootstrap_tool_executor(
            db, app.state.probe_host
        )
        debug_log.bind_secrets(secrets)
        if (
            isinstance(secrets, LocalSecretsClient)
            and os.environ.get("THESHED_DEBUG", "").strip().lower() in {"1", "true", "yes"}
        ):
            try:
                secrets.get("local://debug/enabled")
            except SecretNotFoundError:
                secrets.set("local://debug/enabled", "1")
        async with async_session_factory() as db:
            await seed_operator_from_env(db)
        yield
        await app.state.redis.aclose()
        return

    secrets = EnvVarSecretsClient()
    app.state.secrets = secrets
    anthropic_key = secrets.get("infisical://the-shed/providers/anthropic/api_key")
    app.state.llm_client = AnthropicClient(api_key=anthropic_key)

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


class StripApiPrefix:
    """SPA and Vite talk to /api/*; the backend's own routes are unprefixed.
    Same rewrite a LAN reverse proxy would do. See frontend/vite.config.ts."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if isinstance(path, str) and (path == "/api" or path.startswith("/api/")):
                scope = dict(scope)
                scope["path"] = path[4:] or "/"
        await self.app(scope, receive, send)


app = FastAPI(title="The Shed", lifespan=lifespan)
app.add_middleware(DebugHttpMiddleware)
app.add_middleware(StripApiPrefix)
app.include_router(auth_router)
app.include_router(setup_router)
app.include_router(debug_router)
app.include_router(turns_router)
app.include_router(settings_router)
app.include_router(foundations_router)
app.include_router(issues_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "ref": os.environ.get("THESHED_REF") or "unknown"}


_frontend_dist = os.environ.get("THESHED_FRONTEND_DIST")
if _frontend_dist:
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="ui")
