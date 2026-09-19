# Deploy — PRD

Status: **awaiting grill**. Not MVP. Do not implement from this file or from
the parked former-bootstrap design. See [`../mvp.md`](../mvp.md).

## Intent (not yet designed)

Deploy stands up the foundational platforms from the Bootstrap foundations
bundle, through the web UI, with a Deploy assistant that **executes
predetermined playbooks** and never invents topology. Phases stay
reviewable, rerunnable, idempotent, and state-aware. Errors open issues.

## Candidate platform list (brief, not approved)

GitLab CE (non-HA), Infisical (secrets management and CA — root +
intermediate, relationship to Let's Encrypt, short-lived operator certs,
trust for passwordless SSH), PowerDNS, k3s (3 control-plane + 2 workers),
Flux, Let's Encrypt, Traefik (?), Cloudflared, Postgres, Grafana,
Prometheus.

A large amount of prior work on k3s / Flux / Fleet / Infisical sequencing
and Build-vs-Adopt lives in
[`../parked/bootstrap-fleet-prd-v1.md`](../parked/bootstrap-fleet-prd-v1.md)
and [`../parked/bootstrap-fleet-spec-v1.md`](../parked/bootstrap-fleet-spec-v1.md).
Treat that as raw material for the Deploy grill, not as decided SPEC.

## Open questions the Deploy grill must answer

1. Let's Encrypt: HTTP-01 or DNS-01? How does renewal work with k3s and
   with non-k3s VMs? What can be automated?
2. Is Traefik needed, or does something else terminate TLS / ingress?
3. How does Cloudflared sit next to PowerDNS and public names?
4. Infisical as CA vs. Let's Encrypt: what trusts what, and where do 2-hour
   operator certs live?
5. After success: does the bootstrap LXC retire, stay as break-glass, or
   join the platform?
6. Which of the candidate list is actually in Deploy vs. later Build
   (Grafana/Prometheus vs. Galileo, Postgres-in-LXC vs. platform Postgres)?
7. Brownfield DNS record migration (already identified, still undesigned).

No SPEC until that grill lands.
