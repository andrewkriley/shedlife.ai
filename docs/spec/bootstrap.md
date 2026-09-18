# Bootstrap & Fleet Provisioning — SPEC

Status: draft, technical design for [`../prd/bootstrap.md`](../prd/bootstrap.md).
References [`../architecture.md`](../architecture.md) (portable pattern) and
[`../stack.md`](../stack.md) (reference technologies).

## Actors / components

- **Operator** — the human running the bootstrap.
- **Proxmox host(s)** — one, or three/five for cluster mode; Proxmox VE already
  installed (human pre-task, out of scope).
- **Bootstrap orchestrator (LXC)** — ephemeral; fetched and started by the bootstrap
  command; does the actual provisioning work; destroyed after handoff.
- **Cloud-image VM template** — built once by the orchestrator; source for every
  subsequently-provisioned VM.
- **Fleet-repo host (GitLab CE)** — hosts the tenant's Fleet repo; adopted (existing
  instance) or provisioned (new instance, as its own VM, before the k3s/Flux step).
- **k3s cluster** — three control-plane + two worker nodes (cluster mode) or a smaller
  equivalent for the single-host default; provisioned from the VM template.
- **Flux** — installed into k3s once it's up; the living, ongoing orchestrator from
  that point forward.
- **Fleet repo** (`theshed-<tenant>`) — private, self-hosted on the tenant's GitLab CE;
  source of truth Flux reconciles against.
- **The Shed application** — deployed as a Flux-managed workload once the Fleet repo
  declares it.

## Sequence (happy path, cluster mode)

1. Operator runs the bootstrap command on host 1 (pinned release tag by default).
2. The command provisions the bootstrap LXC on host 1.
3. The LXC starts the menu-driven wizard (or loads an imported YAML file): collects
   hostnames/IPs for all hosts, a root password per host (used once), the Fleet-repo
   host choice (adopt: URL + token; or provision: stand up a new GitLab CE instance),
   and the still-open field list (network bridge, storage pool, NTP, etc. — see PRD
   Open Questions).
4. The LXC generates a dedicated SSH keypair and, using the supplied root passwords,
   installs that key on every host (including host 1). Root passwords are discarded
   from memory/state after this step — never persisted or logged.
5. The LXC forms the Proxmox cluster across all supplied hosts (corosync/quorum),
   using the dedicated key from this point forward.
6. The LXC builds the VM template from a cloud image.
7. If the Fleet-repo host is being provisioned (not adopted): the LXC provisions a VM
   for it now, outside the eventual k3s cluster, and waits for it to become reachable.
8. The LXC provisions the k3s VMs from the template — five for cluster mode (three
   control-plane, two worker), one for the single-host default.
9. The LXC installs k3s across the provisioned VMs, forming the cluster.
10. The LXC installs Flux into the k3s cluster, pointing it at the tenant's Fleet repo
    (existing, or newly created on the GitLab CE instance from step 7).
11. Flux reconciles: deploys the database, cache/queue, and The Shed itself as declared
    in the Fleet repo.
12. The LXC confirms Flux has successfully reconciled the core workloads, then is
    destroyed. Handoff complete — all further provisioning goes through the running
    Shed's own RUN capabilities, not the LXC.

## Data

### Bootstrap-time input (importable by the wizard)

Illustrative shape — not final, pending the open wizard-field-list question:

```yaml
version: 1
topology: cluster        # single | cluster
hosts:
  - hostname: <host-1>
    ip: <ip>
  - hostname: <host-2>
    ip: <ip>
  - hostname: <host-3>
    ip: <ip>
  - hostname: <host-4>
    ip: <ip>
  - hostname: <host-5>
    ip: <ip>
fleet_repo_host:
  mode: adopt             # adopt | provision
  url: <existing GitLab CE url>          # if adopt
  token_ref: <how the token is supplied> # if adopt
fleet_repo: theshed-<tenant>
# network, storage, NTP fields: TBD
```

### Fleet repo (`theshed-<tenant>`) contents

- Declarative registry config (sub-agents, hosts, services) — the `instance.yaml`-style
  content described in `architecture.md`.
- Kubernetes/Flux manifests (Kustomizations, HelmReleases) for the database,
  cache/queue, and The Shed itself.
- Both live in one repo, organized by directory, per the tenant-Fleet model in the PRD.

### Bootstrap state file

Written by the orchestrator as each step completes; read on every invocation to
determine where to resume. Illustrative shape:

```yaml
version: 1
started_at: <timestamp>
steps:
  ssh_key_generated: { done: true, fingerprint: <...> }
  cluster_formed: { done: true, hosts: [<host-1>, <host-2>, ...] }
  vm_template_built: { done: true, template_id: <proxmox vmid> }
  fleet_repo_host_ready: { done: false }   # e.g. provisioning still in progress
  k3s_vms_provisioned: { done: false, vmids: [] }
  k3s_installed: { done: false }
  flux_installed: { done: false }
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

Mirrors the PRD's Open Questions:

- DNS scope (is DNS record creation part of this bootstrap, or a later RUN capability)
  — not yet decided.
- Full wizard field list — not yet enumerated.
- Fleet-repo host provisioning target (sizing, single node vs. HA) — not yet decided.
