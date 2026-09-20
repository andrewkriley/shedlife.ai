# Bootstrap — SPEC

Status: current, technical design for [`../prd/bootstrap.md`](../prd/bootstrap.md).
References [`../architecture.md`](../architecture.md), [`../stack.md`](../stack.md),
and the existing Core Agentic Loop / Auth interfaces this profile reuses.

## Actors / components

- **Operator** — on the LAN, browser to the CT URL.
- **Proxmox host** — one; VE already installed (human pre-task).
- **`bootstrap/install.sh`** — thin; creates the CT, starts the image, prints
  the URL. Not an orchestrator.
- **Bootstrap LXC** — durable for this phase. Runs The Shed (bootstrap
  profile) plus its local database and session store.
- **Setup gate** — first-run screen; creates secret-zero (LLM key) and the
  first local-password identity.
- **`bootstrap.intake`** — the only registered sub-agent. Assist job.
  Playbooks below are its only tools besides ordinary conversation.
- **Foundations store** — schema rows + probe results + exportable YAML.
- **Local secrets store** — implements the secrets-client interface.
- **Local issues store** — unexpected errors and operator-filed issues.

## Sequence (happy path)

1. Operator, as root on the Proxmox host, runs the install command pinned to
   a release tag (overrideable). Example shape:
   `curl -fsSL https://github.com/andrewkriley/shedlife.ai/releases/latest/download/install.sh | bash`
2. The script inspects the recorded CT (if any): present / running /
   stopped, and whether `GET /api/setup/status` answers. It prints that
   status and a warning, then requires `yes` on the TTY unless
   `--yes` / `THESHED_YES=1`. Fresh → create. Existing → update in
   place (keep `.env` and compose volumes, refresh the clone and
   image). `--delete` → destroy the CT, then fresh. New CTs get a
   generated `admin` password and CT `root` password
   (`pct create --password`). Prints the URL plus Username / Password /
   CT user / CT pass immediately, then waits until
   `GET /api/setup/status` succeeds (from the host, or `pct exec` to
   localhost). Do not wait on `GET /health`. `--debug` writes
   `THESHED_DEBUG=1`.
3. Operator opens the URL. Seeded identity exists → login with username
   `admin` and the printed password, then setup if no LLM key yet. No
   identity → setup gate.
4. Setup gate: provider + API key (live validate). Username + password
   (typed twice) only when no operator identity exists yet.
   Writes `local://providers/llm/api_key` (and optional Galileo refs).
   Creates `users` / `identities` rows. Sets the session cookie
   (`Secure` off).
5. Chat UI loads in a single-window shell (header + chat + tabbed review).
   The header polls `GET /health` and `GET /settings/sub-agents` and shows
   **AI Assistant is Connected** when both succeed and at least one agent
   is registered. Registry has one row (`bootstrap.intake`); the turn
   path short-circuits classification and opens that agent.
6. `collect-foundations`: the agent asks for schema fields, writes them
   through a `foundations.write` tool (no side effects beyond the store).
   The review panel reflects the schema after each write.
7. `validate-foundations`: runs without the model inventing rules; failures
   attach to fields.
8. `predeploy-probe`: each probe is its own tool. `ssh_key_installed`
   pauses for approval, generates the dedicated key in the CT, installs it
   via the still-held root password, discards the password, stores only the
   fingerprint. Other probes are read-only.
9. `export-state`: produces the YAML bundle (references, not values). The
   operator can download it. It is also kept on the CT.
10. The LXC stays up. Handoff to Deploy is "foundations valid + probes
    in an accepted state," not a process exit.

## Data

### Installer state file (on the Proxmox host)

```yaml
version: 1
ctid: <vmid>
ct_ip: <addr>
image_ref: <tag or digest>
health: { last_ok: <timestamp> }
```

Used only to decide "create vs. reprint URL." Not the foundations store.

### Foundations schema (illustrative)

```yaml
version: 1
tenant:
  name: <string>
  slug: <[a-z0-9-]+>
operator:
  email: <email>          # identity; password is not in this file
proxmox:
  host: <ip or hostname>
  node: <node name>
  ssh_key_fingerprint: <fingerprint or null>
network:
  bridge: vmbr0
  address: <cidr>
  gateway: <ip>
  ntp: inherit            # inherit | [<server>, ...]
storage:
  pool: local-lvm
domains:
  intended: [<hostname>, ...]
intent:
  gitlab:    { mode: build }                    # or adopt + url + token_ref
  infisical: { mode: build }
  dns:       { mode: greenfield }               # or brownfield + url + token_ref
  k3s:       { mode: build }                    # or adopt + kubeconfig_ref
probes:
  llm_key:              { status: pass, at: <ts> }
  outbound_https:       { status: pass, at: <ts> }
  proxmox_api:          { status: pass, at: <ts> }
  proxmox_capacity:     { status: warn, at: <ts>, detail: <redacted> }
  bridge_exists:        { status: pass, at: <ts> }
  storage_pool_exists:  { status: pass, at: <ts> }
  ntp_ok:               { status: pass, at: <ts> }
  ssh_key_installed:    { status: pass, at: <ts> }
  adopted_endpoint:     { status: skip, at: <ts> }   # skip when all-build
  domain_resolves:      { status: warn, at: <ts> }
```

Secret *values* are only in the local secrets store, referenced as
`local://<path>` (see Secrets Management). The exportable bundle is this
document plus those references.

### Sub-agent registry (bootstrap profile seed)

| Field | Value |
|---|---|
| `id` | `bootstrap.intake` |
| `macro_category` | `assist` |
| `description` | Collect, validate, and probe tenant foundations so Deploy can start |
| `tools` | playbook tools + `foundations.write` / `foundations.read` + probes |
| `default_provider` / `default_model` | whatever the setup gate configured |

`assist`, `run.network`, and `build` are **not** registered in this profile.
They remain in the product; they are not seeded here.

### Local issues

| Field | Notes |
|---|---|
| `id` | opaque |
| `classification` | `operator-input` \| `environment` \| `product-bug` |
| `summary` | short, no secrets |
| `detail` | redacted |
| `source` | `automatic` \| `operator` |
| `filed_externally` | null, or a product-GitHub issue URL after opt-in |
| `created_at` | |

## Interfaces

Reused from the living harness:

- `POST /auth/login`, `POST /auth/logout` — Auth SPEC, with `Secure` off.
- `POST /turns`, `POST /turns/{id}/approvals`, `POST /turns/{id}/verify` —
  Core Agentic Loop SPEC.
- `GET /health` — UI connected indicator. Registered before the static
  mount so it is not swallowed.
- `GET /api/setup/status` — installer wait loop and reuse check.

New:

- `GET` / `PUT /foundations` — read/replace the schema (PUT is what the
  review panel and `foundations.write` use; the agent does not write the
  table itself).
- `POST /foundations/validate` — playbook 2, deterministic.
- `POST /probes/{id}` — run one probe; `ssh_key_installed` goes through the
  existing approval event if invoked from a turn.
- `GET /foundations/export` — YAML bundle.
- `GET` / `POST /issues` — list / operator-file. Automatic writes happen
  in-process on unexpected errors, not via this POST.
- `POST /issues/{id}/file-upstream` — opt-in product-GitHub for
  `product-bug` only.
- Setup-gate endpoints: `POST /setup` (first user + provider key) —
  refused once an identity exists.

Settings (`GET /settings/models`, `POST /settings/provider`, model
overrides) stay; they are how the operator changes provider after the
gate. The page always lists Anthropic / OpenAI / Gemini, can save a new
API key, groups connection status, the assistant list (a lone agent is
pre-selected), and a "Change the model" assignment block. Bootstrap
wires an Anthropic or OpenAI client from `local://providers/llm/*` so
chat and the live models list use the same key.

### Debug log

In-memory ring (last 500 events). Enabled by `THESHED_DEBUG=1` or
`local://debug/enabled`. Toggle wins over the env var. Events: HTTP
(except `/health` and `/debug/logs`), UI clicks, provider connect
attempts, unhandled errors. Secrets are redacted. Each recorded event
is also printed to the app process stdout as one `[debug]` line
and written to the CT `tty1` / `/dev/console` when writable (Proxmox
console). `--debug` also tails compose logs onto `tty1`. Interfaces:

- `GET /debug/status` — `{enabled}`
- `POST /debug/enabled` — `{enabled}` persists the toggle
- `GET /debug/logs` — `{enabled, events[]}`
- `POST /debug/events` — UI clicks / client errors

The UI toggle is green when debug is on and muted when off. The log
panel is shown only while debug is enabled, in the page flow under the
chat — not as a fixed overlay.

## Security model

- Install script: root on Proxmox, creates one unprivileged LXC. Product
  image from GHCR (or the pinned script's documented equivalent). The
  CT `root` password is generated (never prompted), printed next to the
  URL, and stored on the CT for reprint; it is not the Proxmox host
  root password.
- Setup gate and login: Argon2id, session cookie `HttpOnly` + `SameSite=Lax`,
  `Secure` off, CSRF on writes — Auth SPEC, bootstrap exception on `Secure`.
- Root password: memory-only, dropped after `ssh_key_installed` succeeds
  or the operator cancels.
- Dedicated SSH private key: on the CT's local secrets store, never in
  YAML, never in issues, never in Galileo payloads.
- LLM API key: local secrets store, same rules.
- LAN HTTP only. No Cloudflared, no public DNS requirement.

## Playbook engine

A playbook is data: `id`, `steps[]` (`tool`, `required`, `has_side_effects`),
`success_when`. The agent selects a playbook and supplies arguments. The
engine runs the steps, records per-step status, and refuses unknown
playbook ids. Tests cover the engine with a mocked tool layer — no model.

## Open items

None for this phase. Probe minimums (exact CPU/RAM/disk numbers) are an
implementation constant, documented next to the probe, not a design
blocker.
