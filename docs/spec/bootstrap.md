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
- **Setup gate** — first-run identity screen when no operator exists yet.
- **Onboarding wizard** — step-through collect / validate / discover /
  summary after login; re-runnable from the header.
- **`bootstrap.intake`** — the only registered sub-agent. Assist job.
  Playbooks below are its only tools besides ordinary conversation.
- **Foundations store** — schema rows + probe results + exportable YAML.
- **Local secrets store** — implements the secrets-client interface.
- **Local issues store** — unexpected errors and operator-filed issues.

## Sequence (happy path)

1. Operator, as root on the Proxmox host, runs the install command pinned to
   a release tag (overrideable). Example shape:
   `curl -fsSL https://github.com/andrewkriley/shedlife.ai/releases/latest/download/install.sh | bash`
2. The script lists Shed CTs it finds (state file and hostname `theshed` /
   `theshed-*`): VMID, hostname, status, IP, ref, whether
   `GET /api/setup/status` answers. It prints that table and a warning,
   then requires a choice on the TTY unless `--yes` / `THESHED_YES=1`.
   Fresh and parallel creates confirm the VMID is free on the live
   cluster (`pvesh get /cluster/nextid --vmid` plus `/etc/pve/.vmlist`
   and guest conf on every node) so it cannot overlap a CT or VM.
   Fresh (no Shed CT, `9100` free) → create `9100` / `theshed`;
   if `9100` is taken, the next free id. New CTs use hostname `theshed`.
   Existing → (1) update that CT in place (keep `.env` and compose
   volumes, refresh the clone and image) or (2) parallel on the next free
   cluster VMID (hostname `theshed`). `--yes` upgrades the recorded CT and never
   invents a parallel instance. `THESHED_PARALLEL=1` forces parallel.
   `--delete` → destroy the chosen CT, then fresh on a cluster-free VMID.
   `THESHED_CTID` pins an id and is refused if that id is in use. New CTs get a
   generated `admin` password and CT `root` password
   (`pct create --password`). Prints the LAN URL as soon as the CT has
   an address, waits until `GET /api/setup/status` succeeds (from the
   host, or `pct exec` to localhost), then prints Username / Password /
   CT user / CT pass once in the completion summary. Do not wait on
   `GET /health`. `--debug` writes
   `THESHED_DEBUG=1`. The same completion details (URL, Username /
   Password, CT user / CT pass, CT id, ref) are written to the CT
   Proxmox notes field (`pct set --description`) so they stay visible
   on the guest in the Proxmox UI after the installer exits.
3. Operator opens the URL. Seeded identity exists → login with username
   `admin` and the printed password. No identity → setup gate (username
   + password typed twice). The gate does not collect an LLM key or
   Galileo.
4. After login, `GET /onboarding/status`. If foundations are incomplete
   or the LLM key is missing, the onboarding wizard opens in the chat
   column (header, debug, Foundations / Issues stay). Steps: Proxmox
   host → Token ID → Token Secret → provider + API key → tenant name
   and slug → all-build or adopt (URLs when adopting). Each step
   validates before the next. Host discovery fills empty node / bridge /
   pool. The last screen is a probe summary. Completing writes
   foundations + secrets. Header **Onboarding** re-runs the wizard
   (pre-filled, including Token ID; the secret stays a blank field with a
   visible “saved” status). Writes
   `local://providers/llm/api_key` and `local://proxmox/api_token`.
   Settings still changes the provider key later.
5. Chat UI loads in a single-window shell (header + chat + tabbed review
   at about 30% of the browser width).
   The header polls `GET /health` and `GET /settings/sub-agents` and shows
   **AI Assistant is Connected · provider · model · ref** when both succeed
   and at least one agent is registered, using `GET /settings/connection`
   for the live vendor and the model chat will actually call, and the
   `ref` from `/health` (`THESHED_REF`, or omitted when `unknown`). Registry
   has one row (`bootstrap.intake`); the turn path short-circuits
   classification and opens that agent. The registry default is OpenAI
   `gpt-4.1-mini`. If the configured key is a different vendor, chat uses
   that vendor's default model rather than sending a Claude id to
   OpenAI (or the reverse). Classify, synthesize, and verify use that
   same resolved model — not a stale `classifier_model` left from a
   previous Apply. A Settings override for `bootstrap.intake` is its
   own row and **survives image upgrades**; changing the registry
   default does not clear it. Apply of a vendor that is not the live
   key is refused (`400`); save that provider's key first. The Settings
   model picker only lists models for the live vendor. Send must produce a visible reply or a
   visible error — a silent no-op is a bug. Confirmed live on a LAN
   HTTP CT URL: `crypto.randomUUID()` throws (not a secure context),
   so chat message ids must not depend on it. Confirmed live with a
   persisted `openai/gpt-5` override: Chat Completions
   `reasoning_effort=none` is a 400 (`minimal` / `low` / `medium` /
   `high` only); `gpt-5.4` still accepts `none`. The OpenAI client
   must pick the effort the named model accepts. The SSE client must
   flush a leftover event when the stream ends without a trailing
   blank line, or an `error` / `done` is dropped and the UI looks
   dead.
6. `collect-foundations`: the wizard is the primary collect path. The
   agent may still ask for remaining schema fields and write them
   through a `foundations.write` tool (no side effects beyond the store).
   It may enumerate the host and adopted URLs with the discovery
   tools below; those calls do not write the schema unless the operator
   confirms. The wizard may write discovered node / bridge / pool when
   those keys are still empty. The review panel
   reflects the schema after each write.
7. `validate-foundations`: runs without the model inventing rules; failures
   attach to fields.
8. `predeploy-probe`: each probe is its own tool. `ssh_key_installed`
   pauses for approval, generates the dedicated key in the CT, installs it
   via the still-held root password, discards the password, stores only the
   fingerprint. Other probes are read-only. Discovery tools are not
   probes and are not a fifth playbook. Host package / PVE updates on the
   first Proxmox node are not a playbook either — operator pre-task or
   Deploy; Bootstrap does not upgrade the host.
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

Used to remember which CT the last install run touched. Listing
existing Shed CTs also scans `pct list` hostnames. Not the foundations store.

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
  api_token_ref: local://proxmox/api_token   # value never in this file
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
document plus those references. The Foundations panel has **Proxmox Token ID** and **Proxmox Token
Secret** fields with hover descriptions on every schema field. Saving
joins them as `USER@REALM!tokenid=secret` into `local://proxmox/api_token`
and leaves only the ref on the schema. `foundations_write` does the
same if the assistant is handed `proxmox.api_token` (combined) or the
two parts. GET returns the Token ID (`USER@REALM!tokenid`) and
`api_token_set`; it never returns the secret or the combined `id=secret`
value.
`proxmox_api` authenticates with `PVEAPIToken=`.

### Sub-agent registry (bootstrap profile seed)

| Field | Value |
|---|---|
| `id` | `bootstrap.intake` |
| `macro_category` | `assist` |
| `description` | Collect, validate, and probe tenant foundations so Deploy can start |
| `tools` | playbook tools + `foundations.write` / `foundations.read` + probes + discovery + `propose_hostnames` |
| `default_provider` / `default_model` | `openai` / `gpt-4.1-mini` |

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
- `GET /health` — `{status, ref}` UI connected indicator plus the
  install ref (`THESHED_REF`, or `unknown`). Registered before the static
  mount so it is not swallowed.
- `GET /api/setup/status` — installer wait loop and reuse check.

New:

- `GET` / `PUT /foundations` — read/replace the schema (PUT is what the
  review panel and `foundations.write` use; the agent does not write the
  table itself).
- `GET /onboarding/status` — whether the wizard should open, plus
  non-secret current values (host, tenant, token-set, vendor, intent).
- `POST /onboarding/proxmox` — save host and/or Token ID + Secret,
  probe `proxmox_api`, discover nodes / bridges / pools, fill empty
  defaults.
- `POST /onboarding/provider` — validate and save the LLM vendor + key
  (blank key on a re-run keeps the saved one).
- `POST /onboarding/tenant` — name + slug.
- `POST /onboarding/intent` — `build` or `adopt` plus optional service
  URLs.
- `POST /onboarding/complete` — run the wizard probe set and return the
  summary. Does not run `ssh_key_installed`.
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

Settings (`GET /settings/models`, `GET /settings/connection`,
`POST /settings/provider`, model overrides)
stay; they are how the operator changes provider after the
wizard. Bootstrap does not collect Galileo. `GET /settings/connection`
is the live vendor and the resolved model chat / verify will actually
call for `bootstrap.intake` (or the first override). Apply / save-key
refreshes the header immediately. The page always lists Anthropic /
OpenAI / Gemini for saving a key; the model assignment block is locked
to the live vendor. `POST /settings/model-assignments` rejects a
provider that is not the live client (`400`: save that key first) so a
Claude id cannot be stored and then sent to OpenAI (the live
`claude-haiku-4-5` / `model_not_found` 404 on `POST /turns/.../verify`).
Classify, synthesize, and verify resolve the same way as chat, so a
stale `app.state.classifier_model` cannot outlive the live key.
Bootstrap wires an Anthropic or OpenAI client from
`local://providers/llm/*` so chat and the live models list use the
same key. Opening Settings keeps the chat transcript mounted (hidden),
so Back to chat does not wipe it. A saved override that matches the
live vendor is what the next turn calls; a product release that only
updates `default_model` will not unstick a tenant that already picked
another id (the v0.4.11–0.4.14 default-model churn did not).

### Debug log

In-memory ring (last 500 events). Enabled by `THESHED_DEBUG=1` or
`local://debug/enabled`. Toggle wins over the env var. Events: HTTP
start and completion (except `/health` and `/debug/logs` — start is
logged immediately so a long SSE `/turns` stream is visible before it
finishes), UI clicks, chat submit/SSE progress/error/done, provider
connect attempts, settings assignments, turn start/model/done/error,
every LLM `complete()` (vendor, model, duration, output size, errors),
and unhandled errors. Secrets are redacted. Each recorded event
is also printed to the app process stdout as one `[debug]` line
and written to the CT `tty1` / `/dev/console` when writable (Proxmox
console). `--debug` also tails compose logs onto `tty1`. Interfaces:

- `GET /debug/status` — `{enabled}`
- `POST /debug/enabled` — `{enabled}` persists the toggle
- `GET /debug/logs` — `{enabled, events[]}`
- `POST /debug/events` — UI clicks / client errors

The UI toggle is an action label: green **Debug On** when debug is off
(press to enable), red **Debug Off** when debug is on (press to disable).
The log panel is shown only while debug is enabled, in the page flow under the
chat — not as a fixed overlay. Each recorded event includes `stamp`
(`YYYY-MM-DD HH:MM:SS UTC` or `UTC±offset` in the process timezone) and
`at` (millisecond ISO). The dock prints `stamp` at the start of the same
line as `source · event` and the message — one text node, matching the
CT console. Newest events first in the panel; `GET /debug/logs` and the
console stay chronological (oldest first).

## Security model

- Install script: root on Proxmox, creates one unprivileged LXC. Product
  image from GHCR (or the pinned script's documented equivalent). The
  CT `root` password is generated (never prompted), printed next to the
  URL, stored on the CT for reprint, and written to the CT Proxmox notes
  field with the URL and operator login; it is not the Proxmox host
  root password. Those notes are on the Proxmox host (same trust as
  root on that node), not in the product repo.
- Setup gate and login: Argon2id, session cookie `HttpOnly` + `SameSite=Lax`,
  `Secure` off, CSRF on writes — Auth SPEC, bootstrap exception on `Secure`.
- Root password: memory-only, dropped after `ssh_key_installed` succeeds
  or the operator cancels.
- Dedicated SSH private key: on the CT's local secrets store, never in
  YAML, never in issues, never in Galileo payloads.
- LLM API key: local secrets store, same rules.
- LAN HTTP only. No Cloudflared, no public DNS requirement. The
  printed URL is not a [secure context](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts):
  do not call `crypto.randomUUID()` (or any other secure-context-only
  Web API) on the chat send path. Cookie `Secure` is already off for
  the same reason.

## Discovery tools

Read-only (`has_side_effects: false`). Invoked from the turn tool loop,
not via `POST /probes/{id}`. Return `{status, values, detail, provenance}`
where `provenance` is always `discovered`. Statuses: `found` | `skip` |
`fail` | `error`. Never include HTTP response bodies. Never write the
foundations store — the assistant proposes known keys and the operator
confirms via `foundations_write`.

Host inventory (`list_proxmox_nodes`, `list_bridges`, `list_storage_pools`,
`proxmox_version`) reads injected Proxmox facts (`nodes`, `bridges`,
`pools`, `version`) — the same injector capacity / bridge / pool probes
use. Missing injector → `skip`. Empty lists are still `found`.

Adopted discovery (`discover_gitlab`, `discover_infisical`, `discover_dns`,
`discover_k3s`) GETs `intent.<name>.url` with the same injected `http_get`
as `adopted_endpoint`. Mode not adopt/brownfield → `skip`. k3s with
`kubeconfig_ref` and no URL → `skip`. HTTP ≥500 or transport error →
`fail`. HTTP <500 → `found` with `{url, http_status, reachable}`. A
crash (`error`) writes a local issue, same as a probe crash.

`propose_hostnames` is the same shape (`has_side_effects: false`, does
not write the store). Arguments: optional `count` (default 3, max 8)
and optional `base` zone. Returns `{status, values.hostnames, detail,
provenance}` with `provenance: proposed`. Labels are a predetermined
list of workshop devices (tools, electronics, test gear) — `bench`,
`vise`, `lathe`, `solder`, `scope`, `meter`, and the rest of the
implementation constant. Already-used first labels in
`domains.intended` are skipped. `shedlife.ai` is never a default
`base`. Invalid `base` → `fail`. The assistant offers the names; the
operator confirms via `foundations_write`.

## Playbook engine

A playbook is data: `id`, `steps[]` (`tool`, `required`, `has_side_effects`),
`success_when`. The agent selects a playbook and supplies arguments. The
engine runs the steps, records per-step status, and refuses unknown
playbook ids. Tests cover the engine with a mocked tool layer — no model.

## Open items

None for this phase. Probe minimums (exact CPU/RAM/disk numbers) are an
implementation constant, documented next to the probe, not a design
blocker.
