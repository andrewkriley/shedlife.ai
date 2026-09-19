---
Parked: former Bootstrap & Fleet Provisioning SPEC. Superseded by docs/spec/bootstrap.md (Phase 1 intake) and awaiting a Deploy grill. Do not implement from this file.
---
# Bootstrap & Fleet Provisioning — SPEC

Status: parked. Pair: [`bootstrap-fleet-prd-v1.md`](./bootstrap-fleet-prd-v1.md).
This is historical design, not current intent.

## Actors / components

- **Operator** — the human running the bootstrap.
- **Proxmox host(s)** — one, or three/five for cluster mode; Proxmox VE already
  installed (human pre-task, out of scope).
- **Bootstrap orchestrator (LXC)** — ephemeral; fetched and started by the bootstrap
  command; does the actual provisioning work; destroyed after handoff.
- **Cloud-image VM template** — built once by the orchestrator; source for every
  subsequently-provisioned VM.
- **Fleet-repo host (GitLab CE)** — hosts the tenant's Fleet repo; adopted (existing
  instance) or provisioned (new instance, as its own VM, before the k3s/Flux step;
  single node, no HA, when provisioned).
- **k3s cluster** — three control-plane + two worker nodes (cluster mode) or a smaller
  equivalent for the single-host default; **either** provisioned from the VM template
  (`infra` stage runs) **or** adopted (an existing cluster from anywhere; `infra` stage
  is skipped entirely).
- **Flux** — installed into k3s once it's up (or confirmed already present, in the
  adopted-cluster case); the living, ongoing orchestrator from that point forward.
- **Secrets backend (Infisical)** — adopted (existing instance) or provisioned (new
  instance); unlike the Fleet-repo host, has no circular dependency on the bootstrap
  sequence, so it deploys as an ordinary `platform/`-layer Flux-managed workload
  (single node, no HA, when provisioned) rather than a special pre-cluster resource.
- **Fleet repo** (`theshed-<tenant>`) — private, self-hosted on the tenant's GitLab CE;
  source of truth Flux reconciles against. Internally split into a `platform/` layer
  (DNS, database, cache, secrets backend, LiteLLM) and an `apps/` layer (The Shed itself).
- **The Shed application** — deployed as a Flux-managed workload in the Fleet repo's
  `apps/` layer, once the `app` stage runs.

## Stages

Every run declares a **target stage** (`infra`, `platform`, or `app` — default `app`,
a full run) and, independently, whether the k3s cluster is being **built** or
**adopted**. Adoption always starts execution at the `platform` stage, regardless of
the target stage requested (there is no `infra` work to do against a cluster that
already exists).

| Cluster mode | Target stage | Behavior |
|---|---|---|
| build | `infra` | Steps 1–7 below only. Ends with a formed k3s cluster, no Flux. |
| build | `platform` | Steps 1–10. Adds Flux + the Fleet repo's `platform/` layer. |
| build | `app` (default) | Full run, steps 1–12. |
| adopt | `platform` | Starts at step 8, using the supplied cluster credential in place of steps 1–7's output. |
| adopt | `app` (default) | Starts at step 8, continues through step 12. |

## Sequence (happy path, cluster mode, build + full run)

1. Operator runs the bootstrap command on host 1 (pinned release tag by default).
2. The command provisions the bootstrap LXC on host 1.
3. The LXC starts the menu-driven wizard (or loads an imported YAML file): collects
   hostnames/IPs for all hosts, a root password per host (used once), the target stage
   and cluster mode, the Fleet-repo host choice (adopt: URL + token; or provision:
   stand up a new GitLab CE instance), and the rest of the field list (network,
   storage, VM sizing, DNS, ingress domain — see SPEC Data section).
4. The LXC generates a dedicated SSH keypair and, using the supplied root passwords,
   installs that key on every host (including host 1). Root passwords are discarded
   from memory/state after this step — never persisted or logged.
5. **DNS resolution for the rest of the sequence** is established now: brownfield
   (existing DNS adopted in step 3) — the LXC confirms it's reachable, hard
   requirement. Greenfield (nothing to adopt) — the LXC writes static host-entry files
   to every host it controls (itself included), covering just the hosts this bootstrap
   creates; no DNS server involved yet.
6. The LXC forms the Proxmox cluster across all supplied hosts (corosync/quorum),
   using the dedicated key and the name resolution from step 5.
7. The LXC builds the VM template, provisions the k3s VMs from it (five for cluster
   mode, one for single-host), and installs k3s across them, forming the cluster.
   **`infra`-stage runs stop here.**
8. *(Adopted-cluster runs start here, using the supplied cluster credential in place
   of a cluster this bootstrap just formed.)* If the Fleet-repo host is being
   provisioned (not adopted): the LXC provisions a VM for it now, outside the k3s
   cluster, and waits for it to become reachable.
9. The LXC installs Flux into the k3s cluster (or confirms it's already present and
   healthy, in the adopted case), pointing it at the tenant's Fleet repo.
10. Flux reconciles the Fleet repo's **`platform/` layer**: the database, cache/queue,
    a new tenant-dedicated DNS instance (no serving responsibility yet — see DNS,
    above), and — if provisioning rather than adopting — a new secrets backend
    instance.
11. Once the secrets backend is reachable (adopted or newly reconciled), the LXC seeds
    into it the other credentials collected during the wizard (the Fleet-repo host
    token, the DNS token) — without this they'd only ever exist as one-time wizard
    inputs, with nowhere for the running Shed's RUN capabilities to fetch them again
    later. **`platform`-stage runs stop here.**
12. The LXC (or, for an adopted cluster with no LXC, the operator's own bootstrap CLI
    invocation) adds The Shed's manifests to the Fleet repo's **`apps/` layer**.
13. Flux reconciles the `apps/` layer: The Shed itself comes up as a running workload.
    The LXC confirms this succeeded, then is destroyed (an adopted-cluster run that
    never provisioned an LXC has nothing to destroy). Handoff complete — all further
    provisioning, including any DNS migration/cutover, goes through the running Shed's
    own RUN capabilities.

## Data

### Bootstrap-time input (importable by the wizard)

Illustrative shape:

```yaml
version: 1

stage:
  target: app               # infra | platform | app (default)

k3s_cluster:
  mode: build                # build | adopt
  kubeconfig_ref: <ref>       # if adopt — how the cluster credential is supplied

topology: cluster        # single | cluster; ignored if k3s_cluster.mode == adopt

network:
  bridge: vmbr0
  gateway: <gateway ip>
  ntp: inherit            # inherit (from Proxmox host) | [<ntp server>, ...]

storage:
  pool: local-lvm          # single-host only; shared storage out of scope this phase

hosts:
  - hostname: <host-1>
    address: <ip>/<prefix>
  - hostname: <host-2>
    address: <ip>/<prefix>
  - hostname: <host-3>
    address: <ip>/<prefix>
  - hostname: <host-4>
    address: <ip>/<prefix>
  - hostname: <host-5>
    address: <ip>/<prefix>

vm_template:
  image: <cloud image reference, e.g. a specific Ubuntu/Debian cloud image>
  sizing:
    control_plane: { vcpu: 2, ram_gb: 4, disk_gb: 20 }
    worker:        { vcpu: 4, ram_gb: 8, disk_gb: 40 }

fleet_repo_host:
  mode: adopt              # adopt | provision
  url: <existing GitLab CE url>            # if adopt
  token_ref: <how the token is supplied>   # if adopt
  sizing: { vcpu: 2, ram_gb: 4, disk_gb: 40 }  # if provision; single node, no HA

fleet_repo: theshed-<tenant>

dns:
  mode: brownfield          # brownfield | greenfield
  existing_url: <existing PowerDNS API URL>  # if brownfield
  token_ref: <how the token is supplied>     # if brownfield

secrets_backend:
  mode: adopt               # adopt | provision
  url: <existing Infisical url>            # if adopt
  machine_identity_ref: <how the credential is supplied>  # if adopt
  sizing: { vcpu: 2, ram_gb: 4, disk_gb: 20 }  # if provision; single node, no HA

ingress:
  shed_domain: <e.g. shed.tenant.example>
```

### Fleet repo (`theshed-<tenant>`) contents

- Declarative registry config (sub-agents, hosts, services) — the `instance.yaml`-style
  content described in `architecture.md`.
- Kubernetes/Flux manifests, split into two directories matching the stage boundary:
  - `platform/` — Kustomizations/HelmReleases for the database, cache/queue, and DNS.
  - `apps/` — Kustomizations/HelmReleases for The Shed itself.
- Both the registry config and the manifests live in one repo, organized by directory,
  per the tenant-Fleet model in the PRD — the `platform`/`apps` split is *within* that
  one repo, not a reason to split the repo itself.

### Fleet repo GitLab configuration

Set up once, as part of the Fleet-repo-host step (adopt or provision):

- **`main` protected**: MR required (no direct push), signed commits required, "prevent
  approval by author" turned **off** (self-approval allowed — see PRD reasoning).
- **CI** (`.gitlab-ci.yml`, this repo's own, separate from the product repo's GitHub
  Actions): YAML lint, `kubeconform` against the manifest set, `kustomize build`
  (both `platform/` and `apps/` overlays) as a dry-run, `gitleaks`.

### Bootstrap state file

Written by the orchestrator as each step completes; read on every invocation to
determine where to resume. Illustrative shape:

```yaml
version: 1
started_at: <timestamp>
target_stage: app          # infra | platform | app
cluster_mode: build        # build | adopt
steps:
  ssh_key_generated: { done: true, fingerprint: <...> }        # build only
  dns_resolution_ready: { done: true }
  cluster_formed: { done: true, hosts: [<host-1>, <host-2>, ...] }  # build only
  vm_template_built: { done: true, template_id: <proxmox vmid> }    # build only
  k3s_vms_provisioned: { done: true, vmids: [] }                    # build only
  k3s_installed: { done: true }                                     # build only
  # --- adopt-mode runs start resuming from here ---
  fleet_repo_host_ready: { done: false }   # e.g. provisioning still in progress
  flux_installed: { done: false }
  platform_layer_reconciled: { done: false }   # database, cache, DNS, secrets backend
  secrets_seeded: { done: false }   # fleet-repo-host/DNS tokens written in; platform-stage runs stop here
  apps_layer_added: { done: false }
  apps_layer_reconciled: { done: false }       # app-stage runs stop here
  handoff_confirmed: { done: false }
```

**Resume logic**: for each step, if the state file marks it `done`, verify against
live infrastructure (e.g. does `template_id` still exist in Proxmox) before trusting
it — if verification fails, the step re-runs and the state file is corrected. If a
step is not marked `done`, it runs. This is the hybrid model from the PRD: the state
file is the fast path, live verification is the safety net against drift (manual
deletion, a half-finished prior attempt, etc.).

**Teardown**: not built this phase (see PRD). When it exists, it should be able to read
this same file and reverse each `done` step in roughly reverse order — no new
discovery mechanism needed beyond what resumption already requires.

## Interfaces

- Script entry point: `bootstrap/install.sh` in the public product repo, fetched and
  executed directly, pinned to a release tag by default, overridable to a different
  ref.
- Wizard: interactive menu by default; supports a config-import mode for known values
  or a restore/replay.

## Security model

- Root password: transient, operator-supplied, used once per host during initial trust
  establishment, never persisted or logged.
- Dedicated SSH keypair: generated by the bootstrap process, not reused from any
  existing identity; installed on every host; becomes the durable credential for all
  subsequent host access (cluster formation, and later RUN host management).
- Fleet-repo host token (adopt case): supplied by the operator during the wizard;
  scope should be as narrow as the GitOps controller actually needs (read/write to one
  repo), not a full admin credential.
- No secret values are ever committed to the Fleet repo — only references, consistent
  with the secrets pattern in `architecture.md`.

## Open items

Mirrors the PRD's Open Questions — one remaining, by design:

- DNS record migration mechanism (brownfield existing-to-new cutover) — identified as a
  separate later concern, out of this bootstrap's critical path, not yet designed.
