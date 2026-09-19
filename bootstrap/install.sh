#!/usr/bin/env bash
# Thin Phase 1 installer. Run as root on a Proxmox host.
# Does not collect an LLM API key, the Proxmox root password, or tenant facts.
# Those belong to the web app after this script prints a LAN URL.
#
#   curl -fsSL https://raw.githubusercontent.com/andrewkriley/shedlife.ai/${THESHED_REF:-<tag>}/bootstrap/install.sh | bash
#
# Overrides (all optional):
#   THESHED_REF          git ref to fetch (default: latest GitHub release, else main)
#   THESHED_CTID         CT id (default: 9100)
#   THESHED_BRIDGE       LAN bridge (default: vmbr0)
#   THESHED_CT_IP        static CT address (CIDR). DHCP when unset.
#   THESHED_GATEWAY      used only with THESHED_CT_IP
#   THESHED_MEMORY       CT RAM MiB (default: 4096)
#   THESHED_CORES        CT vCPU (default: 2)
#   THESHED_DISK         rootfs size (default: 16)
#   THESHED_STORAGE      Proxmox storage for the rootfs (default: local-lvm)
#   THESHED_TEMPLATE     pveam template volume id
#   THESHED_IMAGE        prebuilt image (skips compose build when set)
#   THESHED_STATE_FILE   host-side state (default: /var/lib/theshed/install-state.yaml)
#   THESHED_PORT         published app port (default: 8080)
set -euo pipefail

REPO="https://github.com/andrewkriley/shedlife.ai.git"
RAW_API="https://api.github.com/repos/andrewkriley/shedlife.ai/releases/latest"
STATE_FILE="${THESHED_STATE_FILE:-/var/lib/theshed/install-state.yaml}"
CTID="${THESHED_CTID:-9100}"
BRIDGE="${THESHED_BRIDGE:-vmbr0}"
MEMORY="${THESHED_MEMORY:-4096}"
CORES="${THESHED_CORES:-2}"
DISK="${THESHED_DISK:-16}"
STORAGE="${THESHED_STORAGE:-local-lvm}"
PORT="${THESHED_PORT:-8080}"
APP_DIR="/opt/theshed"

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "install.sh must run as root on the Proxmox host" >&2
    exit 1
  fi
}

resolve_ref() {
  if [[ -n "${THESHED_REF:-}" ]]; then
    echo "${THESHED_REF}"
    return
  fi
  local tag
  tag="$(curl -fsSL "${RAW_API}" 2>/dev/null | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1 || true)"
  if [[ -n "${tag}" ]]; then
    echo "${tag}"
  else
    echo "main"
  fi
}

ct_health_ok() {
  local ip="$1"
  curl -fsS --max-time 3 "http://${ip}:${PORT}/health" >/dev/null 2>&1
}

read_state_ip() {
  [[ -f "${STATE_FILE}" ]] || return 1
  awk '/^ct_ip:/{print $2}' "${STATE_FILE}" | tr -d '"'
}

read_state_ctid() {
  [[ -f "${STATE_FILE}" ]] || return 1
  awk '/^ctid:/{print $2}' "${STATE_FILE}"
}

write_state() {
  local ip="$1" ref="$2"
  mkdir -p "$(dirname "${STATE_FILE}")"
  cat >"${STATE_FILE}" <<EOF
version: 1
ctid: ${CTID}
ct_ip: ${ip}
image_ref: ${ref}
health:
  last_ok: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
}

print_url() {
  echo
  echo "The Shed is up: http://${1}:${PORT}"
  echo "Open that URL from a browser on this LAN. Setup happens there."
}

maybe_reuse() {
  local ip ctid_recorded
  ip="$(read_state_ip || true)"
  ctid_recorded="$(read_state_ctid || true)"
  if [[ -z "${ip}" ]]; then
    return 1
  fi
  if [[ -n "${ctid_recorded}" ]]; then
    CTID="${ctid_recorded}"
  fi
  if ct_health_ok "${ip}"; then
    write_state "${ip}" "${THESHED_REF}"
    print_url "${ip}"
    return 0
  fi
  return 1
}

ensure_template() {
  if [[ -n "${THESHED_TEMPLATE:-}" ]]; then
    echo "${THESHED_TEMPLATE}"
    return
  fi
  pveam update >/dev/null
  local name
  name="$(pveam available --section system | awk '/debian-12-standard/{print $2}' | tail -1)"
  if [[ -z "${name}" ]]; then
    echo "Could not find a debian-12-standard template. Set THESHED_TEMPLATE." >&2
    exit 1
  fi
  if ! pveam list local | grep -q "${name}"; then
    pveam download local "${name}"
  fi
  echo "local:vztmpl/${name}"
}

ct_ip() {
  if [[ -n "${THESHED_CT_IP:-}" ]]; then
    echo "${THESHED_CT_IP%%/*}"
    return
  fi
  pct exec "${CTID}" -- hostname -I | awk '{print $1}'
}

create_ct() {
  local template="$1"
  if pct status "${CTID}" >/dev/null 2>&1; then
    echo "CT ${CTID} already exists but is not healthy. Abandoned-CT cleanup is manual this phase." >&2
    exit 1
  fi
  local net="name=eth0,bridge=${BRIDGE},ip=dhcp"
  if [[ -n "${THESHED_CT_IP:-}" ]]; then
    net="name=eth0,bridge=${BRIDGE},ip=${THESHED_CT_IP}"
    if [[ -n "${THESHED_GATEWAY:-}" ]]; then
      net="${net},gw=${THESHED_GATEWAY}"
    fi
  fi
  pct create "${CTID}" "${template}" \
    --hostname theshed \
    --memory "${MEMORY}" \
    --cores "${CORES}" \
    --rootfs "${STORAGE}:${DISK}" \
    --net0 "${net}" \
    --unprivileged 1 \
    --features nesting=1 \
    --onboot 1
  pct start "${CTID}"
}

bootstrap_ct() {
  local ref="$1"
  pct exec "${CTID}" -- bash -s <<'INNER'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git openssl
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
INNER
  pct exec "${CTID}" -- bash -c "rm -rf ${APP_DIR} && git clone --depth 1 --branch ${ref} ${REPO} ${APP_DIR}"
  local db_pass
  db_pass="$(openssl rand -hex 24)"
  pct exec "${CTID}" -- bash -c "cat > ${APP_DIR}/.env <<EOF
POSTGRES_PASSWORD=${db_pass}
THESHED_IMAGE=${THESHED_IMAGE:-}
EOF"
  if [[ -n "${THESHED_IMAGE:-}" ]]; then
    pct exec "${CTID}" -- bash -c "cd ${APP_DIR} && docker compose --env-file .env -f bootstrap/docker-compose.yml up -d"
  else
    pct exec "${CTID}" -- bash -c "cd ${APP_DIR} && docker compose --env-file .env -f bootstrap/docker-compose.yml up -d --build"
  fi
}

wait_health() {
  local ip="$1" i
  for i in $(seq 1 60); do
    if ct_health_ok "${ip}"; then
      return 0
    fi
    sleep 5
  done
  echo "Timed out waiting for GET /health on http://${ip}:${PORT}/health" >&2
  exit 1
}

main() {
  need_root
  THESHED_REF="$(resolve_ref)"
  echo "The Shed installer — ref ${THESHED_REF}"
  if maybe_reuse; then
    exit 0
  fi
  local template
  template="$(ensure_template)"
  create_ct "${template}"
  bootstrap_ct "${THESHED_REF}"
  local ip
  ip="$(ct_ip)"
  if [[ -z "${ip}" ]]; then
    echo "Could not determine the CT address. Set THESHED_CT_IP." >&2
    exit 1
  fi
  wait_health "${ip}"
  write_state "${ip}" "${THESHED_REF}"
  print_url "${ip}"
}

main "$@"
