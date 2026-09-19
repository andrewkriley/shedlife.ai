# MVP deliverables

Status: current after the [2026-09-19 reframe grill](./grill/2026-09-19-reframe.md).
Phases 2–4 are named so the product shape is visible; they are **not** in
scope until their own grill lands.

The Shed is stood up and then used in four phases. Only Phase 1 is MVP.

## Prerequisites (human, before any script)

- An Anthropic, OpenAI, or Gemini **API key**. A Claude subscription (or any
  browser-login / Claude Code credential) will not work.
- One Proxmox host, installed, on the internet.
- A strong root password for that host, in a password manager.

`shedlife.ai` is the product domain. It is not required to resolve for Phase 1.

## Phase 1 — Bootstrap (MVP)

An operator runs a script from the public product repo on the Proxmox host
(pinned release tag by default). The script creates one LXC, starts The Shed
in the **bootstrap profile**, and prints a LAN URL.

The operator opens that URL. A setup gate takes the LLM provider + API key
and the first operator account. After that, the UI is the chat: a bootstrap
assistant, backed by a foundations schema, that:

- asks for the facts Deploy will need in order to *start*
- validates them
- runs predetermined pre-deploy probes
- stores the result locally on the LXC
- records unexpected errors as local issues

Success: the operator can leave the machine, come back, see the same
foundations state, re-run probes, and export a YAML bundle. No GitLab, k3s,
Flux, Infisical, or Proxmox cluster has been created.

PRD/SPEC: [`prd/bootstrap.md`](./prd/bootstrap.md), [`spec/bootstrap.md`](./spec/bootstrap.md).

## Phase 2 — Deploy (not MVP)

Deploy the foundational platforms. Separate grill required. Candidate list
(not approved): GitLab CE (non-HA), Infisical (secrets + CA), PowerDNS, k3s
(3 control-plane + 2 workers), Flux, Let's Encrypt, Traefik (?), Cloudflared,
Postgres, Grafana, Prometheus.

Stub: [`prd/deploy.md`](./prd/deploy.md). Parked former design:
[`parked/bootstrap-fleet-prd-v1.md`](./parked/bootstrap-fleet-prd-v1.md).

## Phase 3 — Build (not MVP)

Build the tools and toys for the lab. Separate grill required. Candidate
list (not approved): Proxmox cluster of 3 or 5 hosts; local AI cluster
(single/multi GPU, Ollama or vLLM, multi-host Ray — inspired by
[vllm_manager](https://github.com/andrewkriley/vllm_manager)); Splunk
Enterprise.

Stub: [`prd/build.md`](./prd/build.md). GPU design already drafted:
[`prd/gpu-compute-management.md`](./prd/gpu-compute-management.md).

## Phase 4 — Run (not MVP)

AI Ops and patrols. Separate grill required. Stub: [`prd/run.md`](./prd/run.md).

## Principles that apply to every phase

- Test-first for deterministic code; Galileo for LLM-facing behavior.
- Each phase is driven through the web UI with an AI assistant.
- Assistants execute predetermined playbooks. They do not invent deployment
  patterns.
- Phases are reviewable, rerunnable, idempotent, and state-aware.
- Unexpected errors open an issue with the maintainer (local in Phase 1;
  tenant tracker once Deploy exists). Operator-flagged errors do the same.
- Visual UI uses the `therileys-team` token set, dark only. See
  [`stack.md`](./stack.md).
