from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.foundations.store import load_foundations, record_probe_result, save_foundations
from theshed.foundations.tokens import IncompleteProxmoxToken
from theshed.onboarding.service import (
    IncompleteAdopt,
    OnboardingError,
    apply_network,
    apply_proxmox_host,
    apply_tenant,
    bind_probe_host,
    check_host_reachable,
    discover_and_fill,
    has_llm_key,
    intent_from_choice,
    llm_vendor,
    present_status,
    run_summary_probes,
    save_provider,
    save_proxmox_token,
    summary_ok,
)
from theshed.probes.host import DefaultProbeHost
from theshed.setup.providers import ProviderRejected

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class ProxmoxStep(BaseModel):
    host: str | None = None
    api_token_id: str | None = None
    api_token_secret: str | None = None
    api_token: str | None = None
    discover: bool = False


class NetworkStep(BaseModel):
    bridge: str = ""
    address: str = ""
    gateway: str = ""
    pool: str = ""


class ProviderStep(BaseModel):
    provider: str = ""
    api_key: str = ""


class TenantStep(BaseModel):
    name: str
    slug: str


class IntentStep(BaseModel):
    mode: str
    gitlab_url: str = ""
    infisical_url: str = ""
    dns_url: str = ""
    k3s_url: str = ""


def _http_get(request: Request) -> Any:
    template = getattr(request.app.state, "probe_host", None)
    if isinstance(template, DefaultProbeHost):
        return template._proxmox_http()
    return getattr(template, "_http_get", None)


_STEP_ERRORS = (
    OnboardingError,
    IncompleteProxmoxToken,
    IncompleteAdopt,
    ProviderRejected,
    PermissionError,
    ValueError,
    RuntimeError,
)


def _raise_step(exc: Exception) -> NoReturn:
    if isinstance(exc, OnboardingError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.errors) from exc
    if isinstance(exc, IncompleteProxmoxToken):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.errors) from exc
    if isinstance(exc, IncompleteAdopt):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"intent.url": str(exc)}) from exc
    if isinstance(exc, ProviderRejected):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"provider.api_key": str(exc)}) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, {"proxmox.api_token": str(exc)}
        ) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, {"error": str(exc)}) from exc


@router.get("/status")
async def get_onboarding_status(
    request: Request,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    doc = await load_foundations(db)
    return present_status(doc, getattr(request.app.state, "secrets", None))


@router.post("/proxmox", dependencies=[Depends(require_csrf)])
async def post_proxmox_step(
    body: ProxmoxStep,
    request: Request,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    secrets = getattr(request.app.state, "secrets", None)
    doc = await load_foundations(db)
    http_get = _http_get(request)
    discovery: dict[str, Any] | None = None
    probe: dict[str, str] | None = None
    try:
        if body.host is not None:
            doc = apply_proxmox_host(doc, body.host)
            check_host_reachable(doc["proxmox"]["host"], http_get=http_get)
        token_sent = bool(
            (body.api_token or "").strip()
            or (body.api_token_id or "").strip()
            or (body.api_token_secret or "").strip()
        )
        if token_sent or body.discover:
            doc = save_proxmox_token(
                doc,
                secrets,
                api_token_id=body.api_token_id,
                api_token_secret=body.api_token_secret,
                api_token=body.api_token,
            )
        elif body.host is None:
            raise OnboardingError({"proxmox.host": "required"})
        doc = await save_foundations(db, doc)
        if token_sent or body.discover:
            host = bind_probe_host(
                getattr(request.app.state, "probe_host", None), doc, secrets, None
            )
            api_result = host.proxmox_api()
            probe = {"status": api_result.status, "detail": api_result.detail}
            await record_probe_result(db, "proxmox_api", api_result.status, api_result.detail)
            doc = await load_foundations(db)
            if api_result.status in {"pass", "warn"}:
                doc, facts = discover_and_fill(doc, secrets, http_get=http_get)
                discovery = {
                    "version": facts.get("version") or "",
                    "nodes": facts.get("nodes") or [],
                    "bridges": facts.get("bridges") or [],
                    "pools": facts.get("pools") or [],
                    "networks": facts.get("networks") or {},
                    "address": facts.get("address") or "",
                    "gateway": facts.get("gateway") or "",
                }
                request.app.state.proxmox_facts = facts
                doc = await save_foundations(db, doc)
    except _STEP_ERRORS as exc:
        _raise_step(exc)
    await db.commit()
    body_out = present_status(doc, secrets)
    body_out["discovery"] = discovery
    body_out["probe"] = probe
    return body_out


@router.post("/network", dependencies=[Depends(require_csrf)])
async def post_network_step(
    body: NetworkStep,
    request: Request,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    secrets = getattr(request.app.state, "secrets", None)
    doc = await load_foundations(db)
    try:
        doc = apply_network(
            doc,
            bridge=body.bridge,
            address=body.address,
            gateway=body.gateway,
            pool=body.pool,
        )
    except _STEP_ERRORS as exc:
        _raise_step(exc)
    saved = await save_foundations(db, doc)
    await db.commit()
    return present_status(saved, secrets)


@router.post("/provider", dependencies=[Depends(require_csrf)])
async def post_provider_step(
    body: ProviderStep,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    secrets = getattr(request.app.state, "secrets", None)
    try:
        vendor = save_provider(
            secrets,
            body.provider,
            body.api_key,
            live_check=getattr(request.app.state, "provider_live_check", None),
            configure=getattr(request.app.state, "configure_llm", None),
        )
    except _STEP_ERRORS as exc:
        _raise_step(exc)
    return {
        "provider": {"vendor": vendor, "api_key_set": has_llm_key(secrets)},
    }


@router.post("/tenant", dependencies=[Depends(require_csrf)])
async def post_tenant_step(
    body: TenantStep,
    request: Request,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    secrets = getattr(request.app.state, "secrets", None)
    doc = await load_foundations(db)
    try:
        doc = apply_tenant(doc, body.name, body.slug)
    except _STEP_ERRORS as exc:
        _raise_step(exc)
    saved = await save_foundations(db, doc)
    await db.commit()
    return present_status(saved, secrets)


@router.post("/intent", dependencies=[Depends(require_csrf)])
async def post_intent_step(
    body: IntentStep,
    request: Request,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    secrets = getattr(request.app.state, "secrets", None)
    doc = await load_foundations(db)
    try:
        doc = dict(doc)
        doc["intent"] = intent_from_choice(
            body.mode,
            {
                "gitlab": body.gitlab_url,
                "infisical": body.infisical_url,
                "dns": body.dns_url,
                "k3s": body.k3s_url,
            },
        )
    except _STEP_ERRORS as exc:
        _raise_step(exc)
    saved = await save_foundations(db, doc)
    await db.commit()
    return present_status(saved, secrets)


@router.post("/complete", dependencies=[Depends(require_csrf)])
async def post_complete(
    request: Request,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    secrets = getattr(request.app.state, "secrets", None)
    doc = await load_foundations(db)
    facts = getattr(request.app.state, "proxmox_facts", None)
    host = bind_probe_host(
        getattr(request.app.state, "probe_host", None), doc, secrets, facts
    )
    checks = run_summary_probes(doc, host)
    for item in checks:
        if item["id"] in {"tenant", "provider"}:
            continue
        await record_probe_result(db, item["id"], item["status"], item["detail"])
    if has_llm_key(secrets):
        checks = [
            {
                "id": "provider",
                "label": "AI provider",
                "status": "pass",
                "detail": llm_vendor(secrets) or "",
            },
            *checks,
        ]
    else:
        checks = [
            {
                "id": "provider",
                "label": "AI provider",
                "status": "fail",
                "detail": "API key is not set",
            },
            *checks,
        ]
    status_body = present_status(doc, secrets)
    token_id = (status_body.get("proxmox") or {}).get("api_token_id") or ""
    token_set = bool((status_body.get("proxmox") or {}).get("api_token_set"))
    checks = [
        {
            "id": "proxmox_token_id",
            "label": "Proxmox Token ID",
            "status": "pass" if token_id else "fail",
            "detail": token_id or "missing",
        },
        {
            "id": "proxmox_token_secret",
            "label": "Proxmox Token Secret",
            "status": "pass" if token_set else "fail",
            "detail": "saved" if token_set else "missing",
        },
        *checks,
    ]
    await db.commit()
    return {
        "ok": summary_ok(checks),
        "needed": present_status(doc, secrets)["needed"],
        "checks": checks,
        "status": present_status(await load_foundations(db), secrets),
    }
