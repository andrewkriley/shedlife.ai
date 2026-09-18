# Auth — SPEC

Status: draft, technical design for [`../prd/auth.md`](../prd/auth.md). References
[`../architecture.md`](../architecture.md), the
[Core Agentic Loop SPEC](./core-agentic-loop.md) (the SSE transport constraint this
design resolves for), and the Bootstrap/Fleet declarative-config pattern (first-user
seeding).

## Actors / components

- **User** — via the chat UI.
- **Session store** — Redis-backed (the same Redis already in the stack for jobs, not
  a second store for a second purpose).
- **Auth backend** (FastAPI) — issues/validates the session cookie, hashes/verifies
  passwords.
- **`users` / `identities` tables** (Postgres) — per the identity model.

## Data

### Users / identities (Postgres)

| Table | Key fields |
|---|---|
| `users` | `id`, `display_name`, `created_at` — no credential fields here |
| `identities` | `id`, `user_id`, `provider` (`local` \| `google` \| `github`, only `local` implemented this phase), `provider_user_id` (for `local`: not applicable; for OAuth later: the provider's own user id), `password_hash` (only populated for `provider = local`) |

A user has one `identities` row per way they can authenticate. Adding `google`/`github`
later is a new `provider` value and new rows — no change to `users`, no migration of
existing `local` rows.

## Sequence (login, happy path)

1. User submits email/username + password.
2. Backend looks up the matching `identities` row (`provider = local`), verifies the
   password against `password_hash` (Argon2id).
3. On success: backend creates a session record in Redis (session id → user id, with
   an expiry), and sets an HTTP-only, `Secure`, `SameSite=Lax` cookie carrying the
   session id. Not a JWT in a header — see PRD's reasoning (the SSE/`EventSource`
   constraint).
4. Subsequent requests (REST and the SSE turn-stream connection alike) carry the
   cookie automatically; the backend resolves it against the Redis session store on
   each request.
5. State-changing requests (anything but a plain `GET`) also require a CSRF token
   (double-submit cookie: a non-HTTP-only cookie the frontend reads and echoes back as
   a header on write requests) — the session cookie alone is not sufficient for those.

## First-user seeding

Part of the same declarative-config apply step already designed for a tenant's Fleet
state — an initial admin identity (email/username + an initial password, or a
password-set-on-first-login flow) is declared alongside the sub-agent/host/service
registry entries in the tenant's config, and reconciled into the `users`/`identities`
tables the same way those are. No separate first-run signup screen.

## Interfaces

- `POST /auth/login` — credentials in, session cookie + CSRF cookie out.
- `POST /auth/logout` — invalidates the Redis session record, clears cookies.
- Every other endpoint (REST and the SSE `/turns` connection) requires a valid session
  cookie; write endpoints additionally require the matching CSRF header.

## Security model

- Passwords: Argon2id, never logged, never echoed back in any response.
- Sessions: server-side state in Redis (not a self-contained JWT client can decode),
  so revocation (logout, or an admin forcibly ending a session later) actually
  invalidates it immediately — not just lets a token expire on its own schedule.
- Cookies: `HttpOnly` (unreadable to page JavaScript, mitigating XSS token theft),
  `Secure` (HTTPS only), `SameSite=Lax`.
- CSRF: required on all state-changing requests, per the Sequence above.

## Open items

None remaining from this design pass.
