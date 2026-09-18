# Auth — PRD

Status: draft. See [`../spec/auth.md`](../spec/auth.md) for the technical design this
PRD drives, and [`../architecture.md`](../architecture.md) ("Identity/auth as
pluggable providers", "Multi-tenancy from day one") for the cross-cutting pattern this
document turns into a concrete build.

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
- The first user account on a new tenant deployment exists without a bespoke
  first-run signup flow, using the same declarative-config pattern already established
  for everything else tenant-specific.

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
- A new tenant deployment has a working admin account immediately after bootstrap,
  with no manual "create the first user" step through the UI.
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

Seeded through the same declarative-config pattern already used for a tenant's Fleet
state (registry entries, sub-agent config) — an initial admin account is part of that
declarative input, reconciled the same way everything else in the Fleet repo is, not
a separate first-run UI flow.

### Password handling

Hashed with a modern, deliberately-slow algorithm (Argon2id — the current
best-practice default), never logged, never returned in any API response.

### CSRF

Cookie-based sessions need CSRF protection on state-changing requests — a standard
mitigation (e.g. double-submit cookie), not an afterthought.

## Open questions

None remaining from this design pass.
