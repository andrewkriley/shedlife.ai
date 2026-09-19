# Auth — PRD

Status: draft, updated for the bootstrap profile. See [`../spec/auth.md`](../spec/auth.md) for the technical design this
PRD drives, and [`../architecture.md`](../architecture.md) ("Identity/auth as
pluggable providers", "Multi-tenancy from day one") for the cross-cutting pattern this
document turns into a concrete build. First-user seeding is the Bootstrap
setup gate, not a Fleet apply — Fleet does not exist in Phase 1.

## Problem

The data model has been multi-user-ready since the very first design decision of this
whole project, but nothing has actually specified how a person authenticates, stays
authenticated across a session, or how the very first account on a new deployment
comes to exist.

## Goals

- Local password authentication, modeled as one identity-provider type among several
  from the start — adding Google/GitHub OAuth later is additive, not a restructuring.
- An auth mechanism that works cleanly with the transport already chosen for turn
  streaming (SSE via the browser's native `EventSource`), not one that fights it.
- The first user account on a new tenant deployment exists without a public
  signup: the bootstrap **setup gate** creates it (email + password + LLM
  provider key). A later declarative apply (Fleet) may reconcile the same
  identity once Deploy exists; it is not how the account first comes to be.

## Non-goals (this phase)

- OAuth providers (Google, GitHub) — the identity-provider model supports adding them
  later; not built this phase.
- Role-based access control **enforcement** — the `users`/roles data model exists per
  the original scope decision, but differentiated permissions by role is future work;
  single real user this phase makes it unobservable anyway.
- Multi-factor authentication, password reset flows, account recovery — not addressed
  this phase.

## Users

- The operator (single real user this phase); the data model supports more.

## Success criteria

- A user logs in with a password and stays authenticated across both REST calls and
  an open SSE turn-stream connection, without a custom-header workaround.
- A new tenant deployment has a working admin account at the end of the
  bootstrap setup gate — the first screen, not a later settings page.
- Adding an OAuth provider later requires no schema change to how a user's identity is
  modeled — confirmed by the schema itself (see SPEC), not just asserted.

## Requirements

### Session mechanism

**Cookie-based sessions, not bearer tokens in a header.** The original reasoning here
was wrong in its detail and is corrected now rather than left standing: the premise
was that the browser's native `EventSource` API can't set custom headers, so cookies
were "forced." But `POST /turns` carries a request body (the message), and
`EventSource` can only issue `GET` — it was never actually usable for this endpoint,
regardless of auth scheme. The real transport is `fetch()` with a manually-parsed
`text/event-stream` response body (see the Core Agentic Loop SPEC's Interfaces
section), and `fetch()` can set arbitrary headers just fine — so the header-limitation
argument doesn't hold once the transport is stated correctly.

Cookies remain the right choice anyway, on independent merits: they're attached
automatically by the browser (no frontend code has to manage storing and re-attaching
a token on every request), and they pair naturally with server-side session state that
can be revoked immediately (see below) rather than a self-contained token that's only
as revocable as its own expiry. The decision stands; the stated reason for it doesn't
depend on an EventSource constraint that turned out not to apply.

### Identity model

Local password auth is one identity-provider type among several, per
`architecture.md` — a user's credentials live in an `identities` relation keyed to
the user, not fields on the user record itself, so OAuth providers are additive later.

### First user

Created by `POST /setup` on the bootstrap LXC (see Bootstrap SPEC): email,
password, LLM provider key. Refused once any identity exists; subsequent
visits are login. This replaces the earlier "seed via Fleet declarative
config" requirement, which assumed a repo that Phase 1 does not have.

### Cookie flags (bootstrap exception)

Cookie-based sessions stand. In the bootstrap profile (HTTP on the LAN),
`Secure` is **off**; `HttpOnly` and `SameSite=Lax` stay. `Secure` turns on
when TLS exists (Deploy grill). CSRF on writes is unchanged.

### Password handling

Hashed with a modern, deliberately-slow algorithm (Argon2id — the current
best-practice default), never logged, never returned in any API response.

### CSRF

Cookie-based sessions need CSRF protection on state-changing requests — a standard
mitigation (e.g. double-submit cookie), not an afterthought.

## Open questions

None remaining from this design pass.
