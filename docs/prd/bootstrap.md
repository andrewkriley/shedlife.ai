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
- Running Proxmox host package / PVE updates on the first host —
  operator pre-task or Deploy. Bootstrap does not `apt`/`pveupgrade`
  the node. Subscription and repo settings are not collected, and
  host upgrades are not one of the four playbooks.
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
  anywhere: they run the pinned install command, open the printed URL, log in,
  and finish a short onboarding wizard that ends in a visible summary of
  collected / valid / failing fields plus probe results. Chat, debug, the
  assistant status, Settings, and Foundations remain available.
- Re-running the install command lists every Shed CT it finds and asks
  whether to upgrade one in place or create a parallel CT on the next
  cluster-free VMID. `--yes` upgrades the recorded CT and does not invent
  a parallel instance.
- Re-running the wizard or a probe, or changing one field, does not require
  starting over.
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
  the LAN URL as soon as the CT has an address, then print the login
  details once in the completion summary after `/api/setup/status`
  returns. Write the same completion details (URL,
  Username / Password, CT user / CT pass) to the CT Proxmox notes field,
  set the CT password so the Proxmox console can log in, and seed the
  operator identity so the web UI accepts `admin`.
- Before changing anything, the installer scans for Shed CTs (state file
  plus hostname `theshed` / `theshed-*`) and prints a table: VMID,
  hostname, status, IP, ref, app ready. Fresh and parallel creates ask the
  live Proxmox cluster (`pvesh get /cluster/nextid` plus the cluster guest
  list) so the VMID cannot overlap a CT or VM on any node. If none exist
  and `9100` is free: create `9100` / `theshed`; if `9100` is taken,
  take the next free id. New CTs use hostname `theshed` (the name shown
  in Proxmox). If any Shed CTs exist, the TTY
  asks (1) upgrade an existing CT in place (keep login and volumes;
  rebuilds the app image with `--no-cache`) or (2)
  install a parallel instance on the next free cluster VMID
  (also hostname `theshed`). `--yes` / `THESHED_YES=1` skips prompts and upgrades
  the recorded CT. `THESHED_PARALLEL=1` forces a parallel CT. `--delete`:
  destroy the chosen CT, then a fresh install on a cluster-free VMID.
  `THESHED_CTID` still pins a specific id and is refused if that id is in
  use.
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
  chat, same turn loop, same auth cookies. Bootstrap does not collect or
  configure Galileo; the turn tracer stays a no-op in this phase.
- Registry contains one sub-agent: `bootstrap.intake` (Assist job).
  Classification short-circuits.
- Persistence (database, session store) runs inside the LXC. Data does not
  leave the CT.
- Secrets use the same client interface as the rest of the product, backed by
  a local store. See Secrets Management.

### Setup gate (identity only)

- Operator username + password: username is `admin`. The installer
  generates the password and prints Username / Password plus CT user
  `root` / CT pass in the completion summary. If the CT has no identity yet (dev / no
  installer seed), this gate collects username + password typed twice.
  This *is* the first user — not a later Fleet apply.
- Gate is skippable on later visits once an operator identity exists
  (login). It does not collect an LLM key, Proxmox facts, or Galileo.
  Changing the provider key later is a Settings action or a wizard re-run.

### Onboarding wizard

After login, a step-through wizard collects the minimum the operator must
type, validates each step, discovers the rest from the Proxmox API, and
ends on a pass / warn / fail summary. First login opens it when those
facts are missing. **Onboarding** in the header re-runs it any time
(existing values pre-fill, including the Proxmox Token ID; the Token
Secret stays a blank field with a visible “saved” status — GET never
returns the secret value). Chat, debug,
the assistant status, Settings, and Foundations stay in the chrome.

Steps, in order:

1. Proxmox IP or API URL.
2. Proxmox Token ID (`USER@REALM!tokenid`).
3. Proxmox Token Secret — joined as `id=secret` into local secrets, then
   `proxmox_api` plus host discovery (nodes, bridges, pools, version).
   Empty node / bridge / pool are filled from what was found when the
   operator has not already set them.
4. AI provider (Anthropic | OpenAI | Gemini) and API key. A Claude
   subscription is rejected with an explanation. Validated with a live,
   cheap provider call. On a re-run, a blank key keeps the saved one.
5. Tenant name and slug.
6. Fresh install (all-build / greenfield) **or** fresh install with
   adoption. Adopt then collects a URL per service the operator wants to
   keep (GitLab, Infisical, DNS, k3s) and runs a shallow reachability
   probe. The schema still stores per-dependency `intent.*` rows.

Not in the wizard: network CIDR, gateway, domains, SSH key install,
operator email, Galileo. Those stay on Foundations, chat, or later
phases. The four playbooks remain; the wizard is a UI over collect /
validate / probe, not a fifth playbook.

### Foundations interview

The wizard is the first-run path. Chat can still fill remaining schema
fields through `foundations.write`. The UI shows schema state next to the
conversation, grouped the same way as the field list below.
The working chrome fits one browser window: the transcript scrolls inside
the chat pane, Foundations / Issues share a tabbed review column about
**30% of the browser width**, and
the debug log (when on) sits under those panes instead of covering them,
newest events first, each line stamped in system local time with an
explicit timezone (`UTC` or `UTC±offset`).
Buttons depress and show a busy label while work is in flight. The header
shows **AI Assistant is Connected · provider · model · ref**
once `/health` is ok and a sub-agent is registered, naming the live
provider and model chat will call and the git ref this CT was
installed from (`THESHED_REF`) — so the operator can tell the
assistant is live, and which branch or tag is running, before sending
a message. Sending a message on the
printed LAN HTTP URL must show a reply or an error in the transcript;
a click that does nothing is a product bug (the page is not a secure
context). A Settings model override is what chat, the header, and verify call
when it matches the live vendor; it persists across upgrades. Applying
another vendor's model is refused until that key is saved — otherwise
the header and chat keep the live vendor and verify can 404
(`claude-*` on OpenAI). The assistant fills records; it does not
invent keys.

Field groups:

- **Tenant**: display name and slug.
- **Proxmox**: API/URL or host address, node name if more than one node is
  already there (intent only), and an API token stored in local secrets
  (`api_token_ref` on the schema). The panel shows the saved **Proxmox
  Token ID** (`USER@REALM!tokenid`) in the field and collects **Proxmox
  Token Secret** separately; the app joins them as `id=secret`. The
  assistant may still send a combined `api_token`.
  Root password is collected once, used to install a dedicated SSH key,
  then discarded — never persisted, never logged, never written into the
  YAML bundle.
- **Network**: bridge name, operator-facing address as CIDR + gateway, NTP
  (`inherit` from the Proxmox host by default).
- **Storage**: a storage pool name for later VM disks. Single-host only.
- **Domains**: intended hostname(s) for later ingress. May not resolve yet.
  `shedlife.ai` is not a default. When proposing names, use devices you
  would find in a workshop shed — tools, electronics, test gear — as the
  left-most label (`scope`, `bench`, `solder`, …), never generic
  `server01` / `web` / `app` names.
- **Build-vs-Adopt intent**: the wizard asks once — all-build, or adopt
  some services. All-build writes `build` / `greenfield` on every
  dependency. Adopt collects a URL per chosen service (GitLab, Infisical,
  DNS, k3s) and writes `adopt` / `brownfield` only for those; the rest
  stay build. Nothing is created or contacted except as a *probe*
  (reachability), and only when the operator has chosen adopt. The
  Foundations panel can still edit each dependency.

Explicitly not collected: Proxmox subscription/repo settings; cluster
node lists to form. The Proxmox API token *is* collected — intake jobs
(`proxmox_api`, host discovery) authenticate with it.

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
| `proxmox_api` | API reachable; the saved API token authenticates (`/version`). |
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

- Re-run the install script: after confirmation, upgrade a listed CT in
  place (the guest shown in the table, not a missing VMID left in the
  state file), or create a parallel CT on the next cluster-free VMID.
  `--delete` destroys the chosen CT first, after confirmation.
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
