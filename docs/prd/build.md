# Build (phase) — PRD

Status: **awaiting grill**. Not MVP. This is the **Build phase** (lab
expansion), not the Build *job*. See [`../mvp.md`](../mvp.md) and
"Lifecycle phases are not jobs" in [`../architecture.md`](../architecture.md).

## Intent (not yet designed)

After Deploy, use the living harness — the Build job, and Run where
operations are the work — to add the tools and toys the tenant wants.
Same rules as every phase: TDD, web UI + assistant, predetermined
playbooks, reviewable / rerunnable / idempotent, errors become issues.

## Candidate list (brief, not approved)

- Proxmox cluster of 3 or 5 hosts (quorum-safe). Phase 1 assumed one host.
- Local AI cluster: single GPU, multi GPU, Ollama or vLLM, multi-host Ray.
  Prior art: [vllm_manager](https://github.com/andrewkriley/vllm_manager).
  A drafted GPU pipeline already exists and should be input to this grill:
  [`gpu-compute-management.md`](./gpu-compute-management.md).
- Splunk Enterprise.

No SPEC until that grill lands.
