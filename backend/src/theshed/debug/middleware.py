from __future__ import annotations

import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from theshed.debug import log as debug_log

_SKIP = {"/health", "/debug/logs", "/debug/status", "/api/health", "/api/debug/logs", "/api/debug/status"}


class DebugHttpMiddleware:
    """Record request/response pairs (and unhandled errors) when debug is on."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")
        if path in _SKIP:
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            debug_log.record(
                "http",
                "error",
                f"{method} {path} crashed: {exc}",
                level="error",
                detail={"type": type(exc).__name__},
            )
            raise

        level = "error" if status_code >= 400 else "info"
        elapsed_ms = int((time.monotonic() - started) * 1000)
        debug_log.record(
            "http",
            "request",
            f"{method} {path} → {status_code} ({elapsed_ms}ms)",
            level=level,
            detail={"method": method, "path": path, "status": status_code, "ms": elapsed_ms},
        )
