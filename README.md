# The Shed

*Your digital shed — the place you go to spend lots of time building, tinkering,
and fixing things.*

The Shed is an agentic-first AI harness with three jobs: **Assist** (the everyday
personal-assistant work of running a life), **Build** (new projects, new features,
fixes — for The Shed itself or anything else), and **Run** (operating the
infrastructure underneath all of it — hosting, network, cloud, home tech stack).
One conversational interface, a growable registry of domain-specific sub-agents,
fanning out to whichever of them a message actually needs and fanning back in to
one answer — the pattern is laid out in
[`docs/architecture.md`](docs/architecture.md).

The Shed is a **product**, not a single deployment: this repo holds the pattern
and the code, with no environment-specific content in it at all. Each deployment
is a **tenant**, running its own instance with its own private configuration —
see "Product vs. tenant" in the architecture doc.

A tenant is stood up in four **phases** (Bootstrap → Deploy → Build → Run).
Those phases are not the same thing as the three jobs. Only **Phase 1,
Bootstrap**, is current MVP: a curl-installed LXC that hosts the chat UI, collects
foundations, validates them, and runs pre-deploy probes. See
[`docs/mvp.md`](docs/mvp.md).

[shedlife.ai](https://shedlife.ai) is the product domain (secured, not yet
active). It is not a required tenant hostname.

## Prerequisites

- An Anthropic, OpenAI, or Gemini **API key**. A Claude subscription will not
  work.
- One Proxmox host, installed and on the internet.
- A strong root password for that host, stored in a password manager.

## Install (Phase 1)

On the Proxmox host, as root. This always follows GitHub's latest release:

```bash
curl -fsSL https://github.com/andrewkriley/shedlife.ai/releases/latest/download/install.sh | bash
```

`THESHED_REF` overrides the ref the script clones (a branch or another
release). The script does not ask for an API key. It prints a LAN URL; the
setup gate in the browser is the first place that key is typed.

## How a message becomes an answer

```mermaid
flowchart TD
    U([User]) -->|message| API[API backend]
    API -->|message + recent context| C{Classifier}
    C -->|single-agent profile: short-circuit| BOOT["bootstrap.intake<br/>foundations · probes"]
    BOOT --> ANSWER([Answer, streamed to chat])

    C -.->|living harness, post-Deploy| ASSIST["assist"]
    C -.->|living harness, post-Deploy| BUILD["build"]
    C -.->|living harness, post-Deploy| NET["run.network"]
    ASSIST -.->|2+ matches| SYN{{Synthesis}}
    BUILD -.->|2+ matches| SYN
    NET -.->|2+ matches| SYN
    SYN -.-> ANSWER
    ANSWER -->|optional: Verify| VERIFY[[Independent verifier]]
```

Solid lines are the Phase 1 target. Dashed lines are the living harness already
designed (and partly built) — they are not the MVP bar.

## Status

The Core Agentic Loop is built and running in development (chat, SSE turns,
classifier, `assist`, `run.network`, verifier, settings, Galileo). Bootstrap
reuses that machinery as a profile: `bootstrap/install.sh` starts one LXC,
the setup gate takes the first operator + API key, and the intake assistant
collects / validates / probes foundations. Deploy / Build / Run phases await
their own grills.

Current release: see tags / `CHANGELOG.md`.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — portable pattern.
- [`docs/mvp.md`](docs/mvp.md) — phase-gated deliverables.
- [`docs/stack.md`](docs/stack.md) — technologies, including `therileys-team`
  tokens.
- [`docs/grill/2026-09-19-reframe.md`](docs/grill/2026-09-19-reframe.md) — the
  interrogation that produced this shape.

| Subsystem | PRD | SPEC |
|---|---|---|
| Bootstrap (Phase 1 / MVP) | [PRD](docs/prd/bootstrap.md) | [SPEC](docs/spec/bootstrap.md) |
| Deploy (Phase 2, awaiting grill) | [PRD stub](docs/prd/deploy.md) | — |
| Build phase (Phase 3, awaiting grill) | [PRD stub](docs/prd/build.md) | — |
| Run phase (Phase 4, awaiting grill) | [PRD stub](docs/prd/run.md) | — |
| Core Agentic Loop | [PRD](docs/prd/core-agentic-loop.md) | [SPEC](docs/spec/core-agentic-loop.md) |
| GPU / Compute Management | [PRD](docs/prd/gpu-compute-management.md) | [SPEC](docs/spec/gpu-compute-management.md) |
| Secrets Management | [PRD](docs/prd/secrets-management.md) | [SPEC](docs/spec/secrets-management.md) |
| Auth | [PRD](docs/prd/auth.md) | [SPEC](docs/spec/auth.md) |
| Release Pipeline | [PRD](docs/prd/release-pipeline.md) | [SPEC](docs/spec/release-pipeline.md) |

Parked former Fleet-provisioning design (not source of truth):
[`docs/parked/`](docs/parked/).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, the testing expectation, and
how a change lands. See [`AGENTS.md`](AGENTS.md) if you're an AI agent working
in this repo. See [`RELEASING.md`](RELEASING.md) for how versions get cut.
