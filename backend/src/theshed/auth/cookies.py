"""Session cookie flags, per docs/spec/auth.md (bootstrap Secure-off)."""

from __future__ import annotations

import secrets

from fastapi import Response

from theshed.auth.dependencies import CSRF_COOKIE, SESSION_COOKIE
from theshed.profile import cookie_secure


def set_session_cookies(response: Response, session_id: str) -> str:
    secure = cookie_secure()
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, secure=secure, samesite="lax")
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, secure=secure, samesite="lax")
    return csrf_token
