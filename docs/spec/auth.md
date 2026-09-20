# Auth — SPEC

Status: draft, technical design for [`../prd/auth.md`](../prd/auth.md). References
[`../architecture.md`](../architecture.md), the
[Core Agentic Loop SPEC](./core-agentic-loop.md) (the SSE transport constraint this
design resolves for), and the Bootstrap setup gate (first-user
seeding). Fleet declarative seeding is a later-phase option, not how the
first account is created.

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
| `identities` | `id`, `user_id`, `provider` (`local` \| `google` \| `github`, only `local` implemented this phase), `provider_user_id` (unique per `provider` — the login-lookup identifier: the username for `local`, the provider's own user id for OAuth later), `password_hash` (only populated for `provider = local`) |

A user has one `identities` row per way they can authenticate. Adding `google`/`github`
later is a new `provider` value and new rows — no change to `users`, no migration of
existing `local` rows.

## Sequence (login, happy path)

1. User submits username + password.
2. Backend looks up the matching `identities` row (`provider = local`), verifies the
   password against `password_hash` (Argon2id).
3. On success: backend creates a session record in Redis (session id → user id, with
   an expiry), and sets an HTTP-only, `SameSite=Lax` cookie carrying the
   session id. `Secure` is on when the control plane is served over HTTPS, and
   **off** in the bootstrap profile (LAN HTTP). Not a JWT in a header — see the
   PRD's reasoning (server-side, immediately-revocable state, independent of any
   transport constraint).
4. Subsequent requests (REST and the `fetch()`-based turn-stream request alike) carry
   the cookie automatically; the backend resolves it against the Redis session store on
   each request.
5. State-changing requests (anything but a plain `GET`) also require a CSRF token
   (double-submit cookie: a non-HTTP-only cookie the frontend reads and echoes back as
   a header on write requests) — the session cookie alone is not sufficient for those.

## First-user seeding

`POST /setup` on a control plane with zero identities (Bootstrap SPEC). Creates
the `users` / `identities` row (local `provider_user_id` is the username) and
stores the LLM API key in the local secrets backend. Refused once any identity
exists. No public signup. A later Fleet apply may declare the same admin; it
must not fight the already-created row.

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
  `SameSite=Lax`, and `Secure` when served over HTTPS (off in the bootstrap
  profile).
- CSRF: required on all state-changing requests, per the Sequence above.

## Open items

None remaining from this design pass.
