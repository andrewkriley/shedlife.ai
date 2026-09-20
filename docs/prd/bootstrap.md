# Bootstrap — PRD

Status: current (Phase 1 / MVP). See [`../spec/bootstrap.md`](../spec/bootstrap.md)
for the technical design, [`../architecture.md`](../architecture.md) for the
portable pattern, and [`../mvp.md`](../mvp.md) for how this phase sits next to
Deploy / Build / Run. Produced by the
[2026-09-19 reframe grill](../grill/2026-09-19-reframe.md).

The former "Bootstrap & Fleet Provisioning" design (k3s, Flux, Fleet repo, LXC
teardown) is parked in [`../parked/`](../parked/). It is not this document.

## Problem

The Shed cannot Deploy a platform until something is alive that can talk to the
operator, remember facts, and check that those facts are real. A human
copy-pasting values into a shell script is not repeatable, not reviewable, and
not something an assistant can re-run after a mistake. The first control plane
has to exist before Git, Kubernetes, or a secrets backend do.

## Goals

- One command, run on a fresh Proxmox host, produces a LAN URL.
- That URL is The Shed: a chat UI with a bootstrap assistant, styled with the
  product token set.
- The assistant collects the foundations Deploy needs in order to *start*,
  validates them, and runs predetermined pre-deploy probes.
- Facts live on the LXC, are visible beside the chat, and can be edited and
  re-probed. The same inputs replay to the same state.
- A YAML bundle can be exported for the next phase. Nothing in this phase
  provisions the next phase's platforms.
- Unexpected errors become local issues. The assistant never invents a
  playbook.

## Non-goals (this phase)

- Installing Proxmox VE on bare metal — a human pre-task.
- Forming a Proxmox cluster (3/5 hosts) — Build-phase grill.
- Provisioning or adopting GitLab, Infisical, PowerDNS, k3s, Flux, Let's
  Encrypt, Traefik, Cloudflared, Grafana, Prometheus — Deploy-phase grill.
- Retiring or migrating the LXC after a later Deploy — Deploy-phase grill.
- Shared storage, hardware failure handling, multi-site topologies.
- Exposing the control plane to the public internet.

## Users

- Primary: the operator standing up a new tenant, on the same LAN as the
  Proxmox host.
- The data model is multi-user-ready; only one real user exists.

## Success criteria

- From one Proxmox host with an API key the operator has not yet typed
  anywhere: they run the pinned install command, open the printed URL, complete
  the setup gate, and finish a foundations interview that ends in a visible
  schema of collected / valid / failing fields plus probe results.
- Re-running the install command against the same host does not create a
  second CT if the first one is healthy; it reprints the URL.
- Re-running a probe or changing one field does not require starting over.
- No platform service listed in Non-goals has been created.
- An unexpected probe crash produces a local issue the operator can see; a
  typo in a CIDR does not.

## Requirements

### Thin installer

- Lives in the public product repo as `bootstrap/install.sh`, fetched and
  executed directly, pinned to a release tag by default, overridable to
  another ref.
- Runs on the Proxmox host as root. Creates one LXC, starts The Shed image
  (bootstrap profile) inside it, attaches the CT to the host's LAN bridge,
  prints `http://<ct-ip>:<port>`.
- Does not collect the LLM API key, the Proxmox *host* root password, or
  tenant facts. Those belong to the web app. It *does* generate the first
  operator username (`admin`) + password and a CT `root` password, print
  them next to   the URL (including the early "The Shed is at" line, before
  `/api/setup/status` returns), write the same completion details (URL,
  Username / Password, CT user / CT pass) to the CT Proxmox notes field,
  set the CT password so the Proxmox console can log in, and seed the
  operator identity so the web UI accepts `admin`.
- Before changing anything, the installer inspects whether a bootstrap CT
  is already present and whether the app answers. It prints that status,
  a warning for the planned action, and waits for `yes` on the TTY
  (`THESHED_YES=1` / `--yes` skips the prompt). Fresh: create a new CT.
  Existing: update that CT in place (keep login and volumes). `--delete`:
  destroy the CT, then a fresh install.
- `--debug` (or `THESHED_DEBUG=1`) starts the CT with the live debug
  console on: HTTP requests (including start of a long SSE turn), UI
  clicks, chat submit/SSE, provider connection attempts, model
  assignments, turn and LLM `complete()` calls (vendor, model, duration),
  and errors. The same log is on `GET /debug/logs`, on the app process
  stdout (Proxmox / container console, `docker compose logs`), on CT
  tty1, and can be toggled from the UI after the platform is up.
- Optional static CT IP via an environment variable; otherwise DHCP. Either
  way the printed URL is the address the operator's browser will use — not
  localhost on the CT.

### Bootstrap profile

- The process in the LXC *is* The Shed, not a second app. Same API, same
  chat, same turn loop, same auth cookies, same Galileo hook.
- Registry contains one sub-agent: `bootstrap.intake` (Assist job).
  Classification short-circuits.
- Persistence (database, session store) runs inside the LXC. Data does not
  leave the CT.
- Secrets use the same client interface as the rest of the product, backed by
  a local store. See Secrets Management.

### Setup gate (before chat)

- Provider: Anthropic | OpenAI | Gemini. A Claude subscription is rejected
  with an explanation, not retried as a key.
- API key, validated with a live, cheap provider call. Failure stays on this
  screen.
- Operator username + password: username is `admin`. The installer
  generates the password and prints Username / Password plus CT user
  `root` / CT pass with the URL. If the CT has no identity yet (dev / no
  installer seed), the gate still collects username + password typed
  twice. This *is* the first user — not a later Fleet apply.
- Optional Galileo key / console URL; omitted means the existing no-op
  tracer.
- Gate is skippable on later visits once an operator identity exists
  (login). Changing the provider key later is a settings action, not a
  re-install.

### Foundations interview

Driven by chat, stored as a schema (see SPEC). The UI shows schema state
next to the conversation, grouped the same way as the field list below.
The working chrome fits one browser window: the transcript scrolls inside
the chat pane, Foundations / Issues share a tabbed review column, and
the debug log (when on) sits under those panes instead of covering them.
Buttons depress and show a busy label while work is in flight. The header
shows **AI Assistant is Connected · provider · model**
once `/health` is ok and a sub-agent is registered, naming the live
provider and model chat will call — so the operator can tell the
assistant is live before sending a message. Sending a message on the
printed LAN HTTP URL must show a reply or an error in the transcript;
a click that does nothing is a product bug (the page is not a secure
context). A Settings model override is what chat calls and it persists
across upgrades. The assistant fills records; it does not invent keys.

Field groups:

- **Tenant**: display name and slug.
- **Proxmox**: API/URL or host address, node name if more than one node is
  already there (intent only). Root password is collected once, used to
  install a dedicated SSH key, then discarded — never persisted, never
  logged, never written into the YAML bundle.
- **Network**: bridge name, operator-facing address as CIDR + gateway, NTP
  (`inherit` from the Proxmox host by default).
- **Storage**: a storage pool name for later VM disks. Single-host only.
- **Domains**: intended hostname(s) for later ingress. May not resolve yet.
  `shedlife.ai` is not a default. When proposing names, use devices you
  would find in a workshop shed — tools, electronics, test gear — as the
  left-most label (`scope`, `bench`, `solder`, …), never generic
  `server01` / `web` / `app` names.
- **Build-vs-Adopt intent** (uniform question per dependency, no aggregate
  shortcut): GitLab, Infisical, DNS, k3s. Adopt collects URL + how the
  token will be supplied; Build records "create later." Nothing is created
  or contacted except as a *probe* (reachability), and only when the
  operator has chosen adopt.

Explicitly not collected: Proxmox subscription/repo settings; a separate
Proxmox API token (first contact is root + the dedicated key, same as
before); cluster node lists to form.

### Playbooks

Only these four, all predetermined:

1. `collect-foundations` — interview against the schema.
2. `validate-foundations` — types, requiredness, semantic checks (CIDR,
   hostname, slug).
3. `predeploy-probe` — the probe set below.
4. `export-state` — write/download the YAML bundle (secret *references*,
   never values).

The model may not add a fifth.

### Discovery (not a playbook)

Read-only tools the assistant may call during `collect-foundations` to
enumerate what is already on the host or at an adopted URL. They fill
the conversation, not the schema — the assistant writes known keys
afterwards with `foundations_write`, after the operator confirms.
Provenance on each result is `discovered`.

Host inventory (skip when Proxmox facts are unavailable):
`list_proxmox_nodes`, `list_bridges`, `list_storage_pools`,
`proxmox_version`.

Adopted-platform discovery (skip unless that intent is adopt /
brownfield; k3s skips when only `kubeconfig_ref` is set):
`discover_gitlab`, `discover_infisical`, `discover_dns`, `discover_k3s`.

These are not generic exec / SSH / web-search, and they do not
provision GitLab, Infisical, DNS, or k3s. HTTP bodies are never
returned.

`propose_hostnames` is the same kind of helper: read-only, not a
playbook step, provenance `proposed`. It returns workshop-device
labels (optionally under an operator-supplied zone) and skips names
already in `domains.intended`.

### Pre-deploy probes

Each probe is a tool. Read-only probes are `has_side_effects: false`.
Installing the dedicated SSH key is `true` and needs approval.

| Probe | Pass means |
|---|---|
| `llm_key` | The configured provider accepts the key. |
| `outbound_https` | The CT can reach the public internet (needed later for images and APIs). |
| `proxmox_api` | API reachable; root (or the dedicated key once installed) authenticates. |
| `proxmox_capacity` | CPU / RAM / disk against documented minimums — warn, don't hard-fail, if below. |
| `bridge_exists` | Named bridge exists on the host. |
| `storage_pool_exists` | Named pool exists. |
| `ntp_ok` | Clock is sane (offset within a documented bound). |
| `ssh_key_installed` | Dedicated key works; root password no longer required. |
| `adopted_endpoint` | Each *adopted* URL responds at a shallow health check. |
| `domain_resolves` | Intended name resolves — **warn only**; greenfield names will fail. |

Probes are rerunnable. Results hang off the schema, not the chat transcript.

### Credential bootstrapping

- Root password: transient, operator-known, used once per host, never
  persisted.
- Dedicated SSH keypair: generated in the LXC, installed on first successful
  `proxmox_api` + approval of `ssh_key_installed`. This is the durable host
  credential for later phases.

### Issues

- Unexpected errors (probe exception, unhandled 5xx, playbook step crash)
  write a local issue: classification `operator-input` | `environment` |
  `product-bug`, redacted body, UI-visible.
- The operator can also file manually from an error the UI showed.
- Opt-in file-to-product-GitHub for `product-bug` only, never with secrets
  or raw probe payloads.
- Schema validation failures are not issues.

### Idempotency / failure recovery

- Re-run the install script: after confirmation, an existing CT is
  updated in place. `--delete` destroys it first, after confirmation.
- Re-run a playbook or probe: completed work is skipped after live
  verification, same hybrid model as before (local state + live check).
- Abandoned-CT cleanup is still manual this phase. The installer's state
  file lists what it created.

### LAN posture

- HTTP on the LAN. Cookies: `HttpOnly`, `SameSite=Lax`, `Secure` off.
- Not published via a tunnel. TLS is Deploy.

## Open questions

None for this phase. Let's Encrypt, Traefik, Cloudflared, LXC retirement,
and cluster formation are explicitly later grills — see [`../mvp.md`](../mvp.md).
