#!/usr/bin/env bash
# Thin Phase 1 installer. Run as root on a Proxmox host.
# Does not collect an LLM API key, the Proxmox host root password, or tenant facts.
# Those belong to the web app after this script prints a LAN URL.
# Generates (does not prompt for) the operator login and the CT root password.
#
#   curl -fsSL https://github.com/andrewkriley/shedlife.ai/releases/latest/download/install.sh | bash
# Override the cloned ref with --ref or THESHED_REF (a branch or another release).
# `THESHED_REF=branch curl ... | bash` does NOT work: the variable applies to
# curl only. Use `curl ... | bash -s -- --ref branch` or `export THESHED_REF=`.
#
# Overrides (all optional):
#   THESHED_REF          git ref to fetch (default: latest GitHub release, else main)
#   THESHED_CTID         CT id (default: first free VMID at or above 9100,
#                        confirmed free on this Proxmox cluster)
#   THESHED_HOSTNAME     CT name in Proxmox (default: theshed)
#   THESHED_BRIDGE       LAN bridge (default: vmbr0)
#   THESHED_CT_IP        static CT address (CIDR). DHCP when unset.
#   THESHED_GATEWAY      used only with THESHED_CT_IP
#   THESHED_MEMORY       CT RAM MiB (default: 4096)
#   THESHED_CORES        CT vCPU (default: 2)
#   THESHED_DISK         rootfs size (default: 16)
#   THESHED_STORAGE      Proxmox storage for the rootfs (default: first
#                        active rootdir storage, preferring local-lvm)
#   THESHED_TEMPLATE     pveam volume id (default: ubuntu-26.04-standard)
#   THESHED_IMAGE        prebuilt image (skips compose build when set)
#   THESHED_STATE_FILE   host-side state (default: /var/lib/theshed/install-state.yaml)
#   THESHED_PORT         published app port (default: 8080)
#   THESHED_DELETE=1     same as --delete: destroy the bootstrap CT, then install
#   THESHED_DEBUG=1      same as --debug: live debug console, CT stdout, tty1, GET /debug/logs
#   THESHED_YES=1        same as --yes: skip the confirmation prompt
#   THESHED_PARALLEL=1   same as --parallel: create a new CT on the next free VMID
#
#   curl -fsSL .../install.sh | bash -s -- --delete
#   curl -fsSL .../install.sh | bash -s -- --debug
#   curl -fsSL .../install.sh | bash -s -- --yes
#   curl -fsSL .../install.sh | bash -s -- --parallel
#   curl -fsSL .../install.sh | bash -s -- --ref cursor/improvements-bb2b
set -euo pipefail

REPO="https://github.com/andrewkriley/shedlife.ai.git"
RAW_API="https://api.github.com/repos/andrewkriley/shedlife.ai/releases/latest"
STATE_FILE="${THESHED_STATE_FILE:-/var/lib/theshed/install-state.yaml}"
CTID_EXPLICIT=0
HOSTNAME_EXPLICIT=0
if [[ -n "${THESHED_CTID:-}" ]]; then
  CTID_EXPLICIT=1
fi
if [[ -n "${THESHED_HOSTNAME:-}" ]]; then
  HOSTNAME_EXPLICIT=1
fi
PREFERRED_CTID=9100
CTID="${THESHED_CTID:-${PREFERRED_CTID}}"
CT_HOSTNAME="${THESHED_HOSTNAME:-theshed}"
PVE_ETC="${THESHED_PVE_ETC:-/etc/pve}"
BRIDGE="${THESHED_BRIDGE:-vmbr0}"
MEMORY="${THESHED_MEMORY:-4096}"
CORES="${THESHED_CORES:-2}"
DISK="${THESHED_DISK:-16}"
PORT="${THESHED_PORT:-8080}"
OPERATOR_USERNAME="${THESHED_OPERATOR_USERNAME:-${THESHED_OPERATOR_EMAIL:-admin}}"
OPERATOR_PASSWORD=""
CT_ROOT_PASSWORD=""
APP_DIR="/opt/theshed"
REF_FROM_ENV=0
CT_EXISTS=0
CT_STATUS="missing"
APP_READY=0
EXISTING_IP=""
EXISTING_REF=""
INSTALL_ACTION=""

print_banner() {
  cat <<'EOF'
 ___  _  _  ___  ___     _     ___  ___  ___     _    ___ 
/ __|| || || __||   \   | |   |_ _|| __|| __|   /_\  |_ _|
\__ \| __ || _| | |) |  | |__  | | | _| | _|   / _ \  | | 
|___/|_||_||___||___/   |____||___||_|  |___| /_/ \_\|___|

                 ______________________
                /                     /|
               /_____________________/ |
               |  _______    _____   | |
               | |       |  |     |  | |
               | |   o   |  |_____|  | |
               | |_______|           | /
               |_____________________|/
             ,,,"",,,"",,,,"",,,"",,,"",,,

           ____________________________________
          | Your digital shed -- the place you |
          | go to spend lots of time building, |
          | tinkering, and fixing things.      |
          |____________________________________|
              ||                          ||
      ,,,"",,,||,,"",,,,"",,,"",,,"",,,,,||,,"",,,
EOF
}

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "install.sh must run as root on the Proxmox host" >&2
    exit 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --delete) THESHED_DELETE=1 ;;
      --debug) THESHED_DEBUG=1 ;;
      --yes) THESHED_YES=1 ;;
      --parallel) THESHED_PARALLEL=1 ;;
      --ref)
        shift
        if [[ $# -lt 1 || -z "${1}" ]]; then
          echo "--ref needs a branch or tag" >&2
          exit 1
        fi
        THESHED_REF="$1"
        ;;
      --ref=*)
        THESHED_REF="${1#--ref=}"
        if [[ -z "${THESHED_REF}" ]]; then
          echo "--ref needs a branch or tag" >&2
          exit 1
        fi
        ;;
      --help|-h)
        echo "Usage: install.sh [--delete] [--debug] [--yes] [--parallel] [--ref <git-ref>]"
        echo "  --delete     destroy the chosen bootstrap CT, then install"
        echo "  --debug      enable the live debug console, container stdout, CT tty1, and GET /debug/logs"
        echo "  --yes        skip confirmation; upgrades the recorded CT (never creates a parallel one)"
        echo "  --parallel   install a new CT on the next free VMID, leaving existing CTs alone"
        echo "  --ref        git branch or tag to clone (or set THESHED_REF). Do not prefix curl."
        exit 0
        ;;
      *)
        echo "Unknown option: $1" >&2
        echo "Usage: install.sh [--delete] [--debug] [--yes] [--parallel] [--ref <git-ref>]" >&2
        exit 1
        ;;
    esac
    shift
  done
}

wants_delete() {
  [[ "${THESHED_DELETE:-}" == "1" || "${THESHED_DELETE:-}" == "true" ]]
}

wants_debug() {
  [[ "${THESHED_DEBUG:-}" == "1" || "${THESHED_DEBUG:-}" == "true" ]]
}

wants_yes() {
  [[ "${THESHED_YES:-}" == "1" || "${THESHED_YES:-}" == "true" ]]
}

wants_parallel() {
  [[ "${THESHED_PARALLEL:-}" == "1" || "${THESHED_PARALLEL:-}" == "true" ]]
}

is_shed_hostname() {
  local name="${1:-}"
  [[ "${name}" == "theshed" || "${name}" == theshed-* ]]
}

# Guests on every cluster node: pmxcfs conf files plus .vmlist.
cluster_listed_vmids() {
  local f
  for f in "${PVE_ETC}"/nodes/*/lxc/*.conf "${PVE_ETC}"/nodes/*/qemu-server/*.conf; do
    [[ -f "${f}" ]] || continue
    basename "${f}" .conf
  done
  if [[ -r "${PVE_ETC}/.vmlist" ]]; then
    grep -oE '"[0-9]+":' "${PVE_ETC}/.vmlist" | tr -d '":' || true
  fi
  return 0
}

# Ask the live cluster whether this VMID is free (CTs and VMs, every node).
# pvesh nextid --vmid returns the id only when it is unused cluster-wide.
cluster_nextid_says_taken() {
  local id="$1" out
  command -v pvesh >/dev/null 2>&1 || return 1
  if out="$(pvesh get /cluster/nextid --vmid "${id}" 2>&1)"; then
    out="${out//[$'\t\r\n \"']/}"
    if [[ "${out}" == "${id}" ]]; then
      return 1
    fi
    return 0
  fi
  printf '%s' "${out}" | grep -qi 'already exists'
}

vmid_in_use() {
  local id="$1" used
  if pct status "${id}" >/dev/null 2>&1 || qm status "${id}" >/dev/null 2>&1; then
    return 0
  fi
  # Do not `grep -q` a pipe: grep exits on the first match and SIGPIPE +
  # pipefail would treat a listed VMID as free.
  while read -r used; do
    if [[ "${used}" == "${id}" ]]; then
      return 0
    fi
  done < <(cluster_listed_vmids)
  if cluster_nextid_says_taken "${id}"; then
    return 0
  fi
  return 1
}

next_free_vmid() {
  local id quiet="${1:-}"
  if [[ "${CTID_EXPLICIT}" == "1" ]]; then
    if vmid_in_use "${CTID}"; then
      echo "THESHED_CTID=${CTID} is already in use on this Proxmox cluster." >&2
      exit 1
    fi
    echo "${CTID}"
    return
  fi
  id="${PREFERRED_CTID}"
  while vmid_in_use "${id}"; do
    if [[ "${quiet}" != "quiet" ]]; then
      echo "VMID ${id} is already in use on this cluster; trying the next id." >&2
    fi
    id=$((id + 1))
    if [[ "${id}" -gt 999999999 ]]; then
      echo "Could not find a free VMID on this Proxmox cluster." >&2
      exit 1
    fi
  done
  echo "${id}"
}

hostname_for_new_ct() {
  if [[ "${HOSTNAME_EXPLICIT}" == "1" ]]; then
    echo "${CT_HOSTNAME}"
    return
  fi
  echo "theshed"
}

list_shed_cts() {
  local vmid status name
  command -v pct >/dev/null 2>&1 || return 0
  while read -r vmid status name; do
    [[ -z "${vmid}" || "${vmid}" == "VMID" ]] && continue
    if [[ -z "${name}" || "${name}" == "-" ]]; then
      name="$(pct config "${vmid}" 2>/dev/null | awk '/^hostname:/{print $2}')"
    fi
    if is_shed_hostname "${name}"; then
      printf '%s %s %s\n' "${vmid}" "${status}" "${name}"
    fi
  done < <(pct list 2>/dev/null | awk 'NR>1 {print $1, $2, $NF}')
}

first_listed_shed_vmid() {
  list_shed_cts | awk '{print $1; exit}'
}

print_existing_installs() {
  local vmid status name ip found=0
  echo
  echo "Existing The Shed installations"
  while read -r vmid status name; do
    found=1
    ip=""
    if [[ "${status}" == "running" ]]; then
      ip="$(pct exec "${vmid}" -- hostname -I 2>/dev/null | awk '{print $1}' || true)"
    fi
    printf '  VMID %s  %s  %s' "${vmid}" "${name}" "${status}"
    if [[ -n "${ip}" ]]; then
      printf '  http://%s:%s' "${ip}" "${PORT}"
    fi
    echo
  done < <(list_shed_cts)
  if [[ "${found}" == "0" ]]; then
    echo "  (none)"
  fi
  echo
}

select_ct() {
  local vmid="$1"
  CTID="${vmid}"
  CT_EXISTS=0
  CT_STATUS="missing"
  APP_READY=0
  EXISTING_IP=""
  if ! pct status "${CTID}" >/dev/null 2>&1; then
    return
  fi
  CT_EXISTS=1
  CT_STATUS="$(pct status "${CTID}" 2>/dev/null | awk '/^status:/{print $2}')"
  CT_HOSTNAME="$(pct config "${CTID}" 2>/dev/null | awk '/^hostname:/{print $2}')"
  if [[ "${CT_STATUS}" == "running" ]]; then
    EXISTING_IP="$(ct_ip 2>/dev/null || true)"
    if [[ -n "${EXISTING_IP}" ]] && ct_ready_ok "${EXISTING_IP}"; then
      APP_READY=1
    fi
  fi
}

prepare_new_ct() {
  CTID="$(next_free_vmid)"
  CT_HOSTNAME="$(hostname_for_new_ct)"
  CT_EXISTS=0
  CT_STATUS="missing"
  APP_READY=0
  EXISTING_IP=""
  EXISTING_REF=""
}

read_tty_line() {
  local reply
  if [[ ! -r /dev/tty ]]; then
    echo "No TTY. Re-run with --yes, --parallel, or THESHED_YES=1 / THESHED_PARALLEL=1." >&2
    exit 1
  fi
  if ! read -r reply < /dev/tty; then
    echo "Input failed." >&2
    exit 1
  fi
  printf '%s\n' "${reply}"
}

inspect_existing() {
  local recorded name ip listed
  recorded="$(read_state_ctid || true)"
  listed="$(first_listed_shed_vmid || true)"
  if [[ -n "${recorded}" ]]; then
    CTID="${recorded}"
  elif [[ -n "${listed}" ]]; then
    CTID="${listed}"
  fi
  CT_EXISTS=0
  CT_STATUS="missing"
  APP_READY=0
  EXISTING_IP="$(read_state_ip || true)"
  EXISTING_REF=""
  if [[ -f "${STATE_FILE}" ]]; then
    EXISTING_REF="$(awk '/^image_ref:/{print $2}' "${STATE_FILE}" | tr -d '"')"
  fi
  if pct status "${CTID}" >/dev/null 2>&1; then
    CT_EXISTS=1
    CT_STATUS="$(pct status "${CTID}" 2>/dev/null | awk '/^status:/{print $2}')"
    name="$(pct config "${CTID}" 2>/dev/null | awk '/^hostname:/{print $2}')"
    if [[ -n "${name}" ]]; then
      if ! is_shed_hostname "${name}"; then
        if [[ "${CTID_EXPLICIT}" == "1" || -n "${recorded}" ]]; then
          echo "CT ${CTID} is hostname '${name}', not a Shed CT." >&2
          exit 1
        fi
        # Default 9100 belongs to someone else; allocate the next free VMID.
        CT_EXISTS=0
        CT_STATUS="missing"
        return
      fi
      CT_HOSTNAME="${name}"
    fi
    if [[ "${CT_STATUS}" == "running" ]]; then
      ip="$(ct_ip 2>/dev/null || true)"
      if [[ -n "${ip}" ]]; then
        EXISTING_IP="${ip}"
      fi
      if [[ -n "${EXISTING_IP}" ]] && ct_ready_ok "${EXISTING_IP}"; then
        APP_READY=1
      fi
    fi
    return
  fi
  # State file VMID is gone (a previous parallel attempt, or the CT was
  # destroyed). Upgrade the Shed CT that is actually on this host.
  if [[ -n "${listed}" ]]; then
    select_ct "${listed}"
  fi
}

select_upgrade_ct() {
  local count vmid
  count="$(list_shed_cts | wc -l | tr -d ' ')"
  if [[ "${count}" == "0" ]]; then
    echo "No Shed CT to upgrade." >&2
    exit 1
  fi
  if [[ "${count}" -gt 1 ]]; then
    echo "Enter the VMID to upgrade [${CTID}]:" >&2
    vmid="$(read_tty_line)"
    if [[ -n "${vmid}" ]]; then
      select_ct "${vmid}"
    fi
  else
    vmid="$(first_listed_shed_vmid)"
    select_ct "${vmid}"
  fi
  if [[ "${CT_EXISTS}" != "1" ]]; then
    echo "CT ${CTID} is not present; cannot upgrade." >&2
    exit 1
  fi
}

plan_action() {
  if wants_delete; then
    echo delete
  elif [[ "${CT_EXISTS}" == "1" ]]; then
    echo update
  else
    echo fresh
  fi
}

choose_install_action() {
  local count choice nextid listed
  count="$(list_shed_cts | wc -l | tr -d ' ')"
  if wants_delete; then
    INSTALL_ACTION=delete
    return
  fi
  if wants_parallel; then
    prepare_new_ct
    INSTALL_ACTION=fresh
    return
  fi
  if [[ "${count}" == "0" && "${CT_EXISTS}" != "1" ]]; then
    prepare_new_ct
    INSTALL_ACTION=fresh
    return
  fi
  if wants_yes; then
    if [[ "${CT_EXISTS}" != "1" ]]; then
      listed="$(first_listed_shed_vmid || true)"
      if [[ -n "${listed}" ]]; then
        select_ct "${listed}"
      fi
    fi
    if [[ "${CT_EXISTS}" != "1" ]]; then
      echo "No Shed CT to upgrade. Re-run without --yes, or use --parallel." >&2
      exit 1
    fi
    INSTALL_ACTION=update
    return
  fi
  nextid="$(
    CTID_EXPLICIT=0
    next_free_vmid quiet
  )"
  echo "An existing Shed CT was found." >&2
  echo "  1) Upgrade an existing installation in place" >&2
  echo "  2) Install a parallel instance for testing (next VMID ${nextid})" >&2
  echo "Enter 1 or 2:" >&2
  choice="$(read_tty_line)"
  case "${choice}" in
    1)
      select_upgrade_ct
      INSTALL_ACTION=update
      ;;
    2)
      prepare_new_ct
      INSTALL_ACTION=fresh
      ;;
    *)
      echo "Aborted." >&2
      exit 1
      ;;
  esac
}

print_plan() {
  local action="$1"
  echo
  echo "Installation status"
  echo "  Action:  ${action}"
  echo "  CT:      ${CTID} (${CT_HOSTNAME}) — ${CT_STATUS}"
  echo "  Ref:     ${THESHED_REF}"
  if [[ "${REF_FROM_ENV:-0}" != "1" ]]; then
    echo "  Note:    no --ref given — defaulting to the latest release, not a branch."
  fi
  if [[ "${APP_READY}" == "1" ]]; then
    echo "  App:     ready"
  else
    echo "  App:     not ready"
  fi
  if [[ -n "${EXISTING_IP}" ]]; then
    echo "  URL:     http://${EXISTING_IP}:${PORT}"
  fi
  echo
  case "${action}" in
    delete)
      if [[ "${CT_STATUS}" == "missing" ]]; then
        echo "WARNING: --delete was set but CT ${CTID} is not present. A new installation will be created."
      else
        echo "WARNING: --delete will DESTROY CT ${CTID} (${CT_HOSTNAME}) and all data on it, then create a new installation."
      fi
      ;;
    update)
      echo "WARNING: an existing installation is present. This will UPDATE CT ${CTID} (${CT_HOSTNAME}) in place. Operator login and data volumes are kept; the app clone and image are refreshed."
      ;;
    *)
      if list_shed_cts | grep -q .; then
        echo "WARNING: this is a parallel install. It will create CT ${CTID} (${CT_HOSTNAME}) next to the existing Shed CT(s). Existing CTs are left running."
      else
        echo "WARNING: this is a fresh install. It will create CT ${CTID} (${CT_HOSTNAME}) and start The Shed."
      fi
      ;;
  esac
  echo "Type yes to continue."
}

confirm_install() {
  local reply
  if wants_yes; then
    echo "THESHED_YES=1: continuing without a prompt."
    return 0
  fi
  if [[ ! -r /dev/tty ]]; then
    echo "No TTY for confirmation. Re-run with --yes or THESHED_YES=1." >&2
    exit 1
  fi
  if ! read -r reply < /dev/tty; then
    echo "Confirmation failed." >&2
    exit 1
  fi
  if [[ "${reply}" != "yes" ]]; then
    echo "Aborted."
    exit 1
  fi
}

ensure_operator_password() {
  if [[ -z "${OPERATOR_PASSWORD}" ]]; then
    OPERATOR_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)"
  fi
}

ensure_ct_root_password() {
  if [[ -z "${CT_ROOT_PASSWORD}" ]]; then
    CT_ROOT_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)"
  fi
}

apply_ct_root_password() {
  ensure_ct_root_password
  pct exec "${CTID}" -- bash -c "echo 'root:${CT_ROOT_PASSWORD}' | chpasswd"
}

persist_ct_root_password() {
  ensure_ct_root_password
  pct exec "${CTID}" -- bash -c "
    set -euo pipefail
    if [[ -f ${APP_DIR}/.env ]]; then
      if grep -q '^THESHED_CT_ROOT_PASSWORD=' ${APP_DIR}/.env; then
        sed -i 's/^THESHED_CT_ROOT_PASSWORD=.*/THESHED_CT_ROOT_PASSWORD=${CT_ROOT_PASSWORD}/' ${APP_DIR}/.env
      else
        echo 'THESHED_CT_ROOT_PASSWORD=${CT_ROOT_PASSWORD}' >> ${APP_DIR}/.env
      fi
    fi
  "
}

load_operator_from_ct() {
  local line
  line="$(pct exec "${CTID}" -- bash -c "grep -E '^THESHED_OPERATOR_USERNAME=|^THESHED_OPERATOR_EMAIL=|^THESHED_OPERATOR_PASSWORD=|^THESHED_CT_ROOT_PASSWORD=|^THESHED_DEBUG=' ${APP_DIR}/.env" 2>/dev/null || true)"
  if [[ -n "${line}" ]]; then
    OPERATOR_USERNAME="$(printf '%s\n' "${line}" | awk -F= '/^THESHED_OPERATOR_USERNAME=/{print $2}')"
    if [[ -z "${OPERATOR_USERNAME}" ]]; then
      OPERATOR_USERNAME="$(printf '%s\n' "${line}" | awk -F= '/^THESHED_OPERATOR_EMAIL=/{print $2}')"
    fi
    OPERATOR_PASSWORD="$(printf '%s\n' "${line}" | awk -F= '/^THESHED_OPERATOR_PASSWORD=/{print $2}')"
    CT_ROOT_PASSWORD="$(printf '%s\n' "${line}" | awk -F= '/^THESHED_CT_ROOT_PASSWORD=/{print $2}')"
    if printf '%s\n' "${line}" | grep -q '^THESHED_DEBUG=1'; then
      THESHED_DEBUG=1
    fi
  fi
}

delete_existing_ct() {
  local recorded name
  recorded="$(read_state_ctid || true)"
  if [[ -n "${recorded}" ]]; then
    CTID="${recorded}"
  fi
  if ! pct status "${CTID}" >/dev/null 2>&1; then
    echo "No CT ${CTID} to delete."
    rm -f "${STATE_FILE}"
    return
  fi
  name="$(pct config "${CTID}" 2>/dev/null | awk '/^hostname:/{print $2}')"
  if [[ -n "${name}" ]] && ! is_shed_hostname "${name}"; then
    echo "CT ${CTID} is hostname '${name}', not a Shed CT. Refusing --delete." >&2
    exit 1
  fi
  echo "Deleting CT ${CTID} (${name:-unknown})"
  pct stop "${CTID}" >/dev/null 2>&1 || true
  pct destroy "${CTID}"
  rm -f "${STATE_FILE}"
}

resolve_ref() {
  if [[ -n "${THESHED_REF:-}" ]]; then
    REF_FROM_ENV=1
    return
  fi
  REF_FROM_ENV=0
  local tag
  tag="$(curl -fsSL "${RAW_API}" 2>/dev/null | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1 || true)"
  if [[ -n "${tag}" ]]; then
    echo "THESHED_REF is unset; using latest GitHub release ${tag}." >&2
    echo "A branch test needs: curl ... | bash -s -- --ref <branch-or-tag>" >&2
    THESHED_REF="${tag}"
  else
    echo "THESHED_REF is unset; no GitHub release found, using main." >&2
    THESHED_REF="main"
  fi
}

READY_PATH="/api/setup/status"

ct_ready_ok() {
  local ip="$1"
  # The first-run API. GET /health is registered after the static UI mount
  # on older images and 404s from the Proxmox host.
  if curl -fsS --max-time 3 "http://${ip}:${PORT}${READY_PATH}" >/dev/null 2>&1; then
    return 0
  fi
  pct exec "${CTID}" -- curl -fsS --max-time 3 "http://127.0.0.1:${PORT}${READY_PATH}" >/dev/null 2>&1
}

assert_running_ref() {
  local ip="$1" body
  body="$(curl -fsS --max-time 5 "http://${ip}:${PORT}/api/health" 2>/dev/null || true)"
  if [[ -z "${body}" ]]; then
    body="$(pct exec "${CTID}" -- curl -fsS --max-time 5 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null || true)"
  fi
  if printf '%s' "${body}" | grep -Eq "\"ref\"[[:space:]]*:[[:space:]]*\"${THESHED_REF}\""; then
    echo "Running app ref ${THESHED_REF}"
    return 0
  fi
  echo "Upgrade did not replace the running image." >&2
  echo "Expected /api/health ref=${THESHED_REF}; got: ${body:-empty}" >&2
  echo "The UI will keep the old Proxmox token field until this container is rebuilt." >&2
  exit 1
}

cloned_reports_ref() {
  pct exec "${CTID}" -- grep -q 'os.environ.get("THESHED_REF")' "${APP_DIR}/backend/src/theshed/main.py"
}

verify_running_image() {
  local ip="$1"
  if cloned_reports_ref; then
    assert_running_ref "${ip}"
    return
  fi
  echo "Ref ${THESHED_REF} does not publish /health ref; skipped image check."
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
  echo "The Shed is starting at: http://${1}:${PORT}"
  echo "Waiting for GET ${READY_PATH} ..."
}

write_ct_notes() {
  local ip="$1"
  local notes
  notes="$(
    printf '%s\n' \
      "The Shed is ready." \
      "" \
      "  URL:      http://${ip}:${PORT}" \
      "  Username: ${OPERATOR_USERNAME}" \
      "  Password: ${OPERATOR_PASSWORD}" \
      "  CT user:  root" \
      "  CT pass:  ${CT_ROOT_PASSWORD}" \
      "  CT:       ${CTID} (${CT_HOSTNAME})" \
      "  Ref:      ${THESHED_REF}"
  )"
  if wants_debug; then
    notes="${notes}"$'\n'"  Debug:    on  (http://${ip}:${PORT}/api/debug/logs, CT tty1)"
  fi
  if ! pct set "${CTID}" --description "${notes}"; then
    echo "Could not write the URL and passwords to the CT notes field." >&2
  fi
}

print_summary() {
  local ip="$1"
  echo
  echo "========================================"
  echo "The Shed is ready."
  echo
  echo "  URL:      http://${ip}:${PORT}"
  echo "  Username: ${OPERATOR_USERNAME}"
  echo "  Password: ${OPERATOR_PASSWORD}"
  echo "  CT user:  root"
  echo "  CT pass:  ${CT_ROOT_PASSWORD}"
  echo "  CT:       ${CTID} (${CT_HOSTNAME})"
  echo "  Ref:      ${THESHED_REF}"
  if wants_debug; then
    echo "  Debug:    on  (http://${ip}:${PORT}/api/debug/logs, CT tty1)"
  fi
  echo
  echo "Open that URL from a browser on this LAN."
  echo "Log in with username and password above, then finish the onboarding wizard."
  echo "Proxmox console / pct console: root and the CT pass."
  echo "These details are also on the CT notes in the Proxmox UI."
  echo "========================================"
  write_ct_notes "${ip}"
}

prepare_ct_packages() {
  pct exec "${CTID}" -- bash -s <<'INNER'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git openssl
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
INNER
}

follow_debug_to_tty() {
  if ! wants_debug; then
    return 0
  fi
  echo "Tailing app logs onto CT tty1"
  pct exec "${CTID}" -- bash -c "
    set +e
    if [[ -f /var/run/theshed-debug-tty.pid ]]; then
      kill \"\$(cat /var/run/theshed-debug-tty.pid)\" 2>/dev/null
    fi
    cd ${APP_DIR} || exit 0
    nohup docker compose --env-file .env -f bootstrap/docker-compose.yml logs -f --no-color app >/dev/tty1 2>&1 &
    echo \$! > /var/run/theshed-debug-tty.pid
  " || true
}

compose_up() {
  local cache_flag="${1:-}"
  if [[ -n "${THESHED_IMAGE:-}" ]]; then
    pct exec "${CTID}" -- bash -c "cd ${APP_DIR} && docker compose --env-file .env -f bootstrap/docker-compose.yml up -d --force-recreate --no-build"
  else
    # A leftover THESHED_IMAGE= in .env would otherwise keep the previous
    # image tag and skip a real rebuild of the UI. Upgrades pass
    # --no-cache so a branch change cannot reuse theshed:bootstrap.
    pct exec "${CTID}" -- bash -c "
      set -euo pipefail
      cd ${APP_DIR}
      sed -i '/^THESHED_IMAGE=$/d' .env
      docker compose --env-file .env -f bootstrap/docker-compose.yml build ${cache_flag} --build-arg THESHED_REF=${THESHED_REF} app
      docker compose --env-file .env -f bootstrap/docker-compose.yml up -d --force-recreate --build
    "
  fi
  follow_debug_to_tty
}

write_fresh_env() {
  local db_pass debug_flag
  db_pass="$(openssl rand -hex 24)"
  ensure_operator_password
  ensure_ct_root_password
  debug_flag="0"
  if wants_debug; then
    debug_flag="1"
  fi
  pct exec "${CTID}" -- bash -c "cat > ${APP_DIR}/.env <<EOF
POSTGRES_PASSWORD=${db_pass}
THESHED_IMAGE=${THESHED_IMAGE:-}
THESHED_DEBUG=${debug_flag}
THESHED_REF=${THESHED_REF}
THESHED_OPERATOR_USERNAME=${OPERATOR_USERNAME}
THESHED_OPERATOR_EMAIL=${OPERATOR_USERNAME}
THESHED_OPERATOR_PASSWORD=${OPERATOR_PASSWORD}
THESHED_CT_ROOT_PASSWORD=${CT_ROOT_PASSWORD}
EOF"
}

upsert_ct_env() {
  local key="$1"
  local value="$2"
  pct exec "${CTID}" -- bash -c "
    set -euo pipefail
    [[ -f ${APP_DIR}/.env ]] || exit 0
    if grep -q '^${key}=' ${APP_DIR}/.env; then
      sed -i 's#^${key}=.*#${key}=${value}#' ${APP_DIR}/.env
    else
      echo '${key}=${value}' >> ${APP_DIR}/.env
    fi
  "
}

update_existing_ct() {
  local ref="$1"
  if [[ "${HOSTNAME_EXPLICIT}" != "1" ]]; then
    CT_HOSTNAME="theshed"
  fi
  pct set "${CTID}" --hostname "${CT_HOSTNAME}"
  if [[ "${CT_STATUS}" == "stopped" ]]; then
    echo "Starting CT ${CTID}"
    pct start "${CTID}"
    CT_STATUS="running"
  fi
  echo "Updating CT ${CTID} (${CT_HOSTNAME}) to ${ref}"
  load_operator_from_ct
  prepare_ct_packages
  pct exec "${CTID}" -- bash -c "
    set -euo pipefail
    if [[ -f ${APP_DIR}/.env ]]; then
      cp ${APP_DIR}/.env /tmp/theshed.env
    fi
    rm -rf ${APP_DIR}
    git clone --depth 1 --branch ${ref} ${REPO} ${APP_DIR}
    if [[ -f /tmp/theshed.env ]]; then
      cp /tmp/theshed.env ${APP_DIR}/.env
    fi
  "
  if ! pct exec "${CTID}" -- test -f "${APP_DIR}/.env"; then
    write_fresh_env
  elif wants_debug; then
    pct exec "${CTID}" -- bash -c "
      if grep -q '^THESHED_DEBUG=' ${APP_DIR}/.env; then
        sed -i 's/^THESHED_DEBUG=.*/THESHED_DEBUG=1/' ${APP_DIR}/.env
      else
        echo 'THESHED_DEBUG=1' >> ${APP_DIR}/.env
      fi
    "
  fi
  upsert_ct_env THESHED_REF "${ref}"
  echo "Rebuilding the app image for ${ref} (no cache)"
  compose_up --no-cache
}

ensure_template() {
  if [[ -n "${THESHED_TEMPLATE:-}" ]]; then
    echo "${THESHED_TEMPLATE}"
    return
  fi
  pveam update >/dev/null
  local name
  # Column 2 only — never capture `pveam download` progress; pct create
  # rejects an ostemplate longer than 255 characters.
  name="$(pveam available --section system | awk '$2 ~ /^ubuntu-26.04-standard/ {print $2}' | sort -V | tail -1)"
  if [[ -z "${name}" ]]; then
    echo "Could not find ubuntu-26.04-standard. Set THESHED_TEMPLATE." >&2
    exit 1
  fi
  if ! pveam list local | grep -q "${name}"; then
    pveam download local "${name}" >&2
  fi
  local volume="local:vztmpl/${name}"
  if [[ ${#volume} -gt 255 ]]; then
    echo "ostemplate is ${#volume} characters; pct create allows 255. Set THESHED_TEMPLATE." >&2
    exit 1
  fi
  echo "${volume}"
}

rootdir_from_cfg() {
  # storage.cfg — do not call `pvesm status` here. A stale local-lvm
  # entry makes that command exit non-zero and abort the installer.
  awk '
    BEGIN { name=""; content=""; disabled=0 }
    /^[A-Za-z0-9._-]+:/ {
      if (name != "" && disabled == 0 && content ~ /(^|,)rootdir(,|$)/) print name
      name=$2
      content=""
      disabled=0
      next
    }
    $1 == "content" { content=$2 }
    $1 == "disable" { disabled=1 }
    END {
      if (name != "" && disabled == 0 && content ~ /(^|,)rootdir(,|$)/) print name
    }
  ' /etc/pve/storage.cfg 2>/dev/null || true
}

usable_storages() {
  local name
  while read -r name; do
    [[ -z "${name}" ]] && continue
    if pvesm status --storage "${name}" >/dev/null 2>&1; then
      printf '%s\n' "${name}"
    fi
  done
}

resolve_storage() {
  local names first candidate
  names="$(rootdir_from_cfg | usable_storages)"
  if [[ -n "${THESHED_STORAGE:-}" ]]; then
    if printf '%s\n' "${names}" | grep -qx "${THESHED_STORAGE}"; then
      echo "${THESHED_STORAGE}"
      return
    fi
    echo "THESHED_STORAGE='${THESHED_STORAGE}' is not a usable rootdir storage; ignoring it." >&2
  fi
  for candidate in local-lvm local-zfs local; do
    if printf '%s\n' "${names}" | grep -qx "${candidate}"; then
      echo "${candidate}"
      return
    fi
  done
  first="$(printf '%s\n' "${names}" | head -1)"
  if [[ -n "${first}" ]]; then
    echo "${first}"
    return
  fi
  echo "No usable Proxmox storage with content type rootdir." >&2
  echo "Enable rootdir on a working pool, or set THESHED_STORAGE." >&2
  exit 1
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
  if vmid_in_use "${CTID}"; then
    echo "VMID ${CTID} is already in use on this Proxmox cluster. Re-run to pick the next free id, or set THESHED_CTID." >&2
    exit 1
  fi
  local net="name=eth0,bridge=${BRIDGE},ip=dhcp"
  if [[ -n "${THESHED_CT_IP:-}" ]]; then
    net="name=eth0,bridge=${BRIDGE},ip=${THESHED_CT_IP}"
    if [[ -n "${THESHED_GATEWAY:-}" ]]; then
      net="${net},gw=${THESHED_GATEWAY}"
    fi
  fi
  echo "Creating CT ${CTID} (${CT_HOSTNAME})"
  ensure_ct_root_password
  pct create "${CTID}" "${template}" \
    --hostname "${CT_HOSTNAME}" \
    --memory "${MEMORY}" \
    --cores "${CORES}" \
    --rootfs "${STORAGE}:${DISK}" \
    --net0 "${net}" \
    --password "${CT_ROOT_PASSWORD}" \
    --unprivileged 1 \
    --features nesting=1 \
    --onboot 1
  pct start "${CTID}"
}

bootstrap_ct() {
  local ref="$1"
  prepare_ct_packages
  pct exec "${CTID}" -- bash -c "rm -rf ${APP_DIR} && git clone --depth 1 --branch ${ref} ${REPO} ${APP_DIR}"
  write_fresh_env
  compose_up
}

wait_ready() {
  local ip="$1" i
  for i in $(seq 1 60); do
    if ct_ready_ok "${ip}"; then
      return 0
    fi
    sleep 5
  done
  echo "Timed out waiting for GET ${READY_PATH} on http://${ip}:${PORT}${READY_PATH}" >&2
  exit 1
}

main() {
  parse_args "$@"
  print_banner
  need_root
  resolve_ref
  echo "The Shed installer — ref ${THESHED_REF}"
  inspect_existing
  print_existing_installs
  # Must not run in $(...): prepare_new_ct sets CTID for the new VMID.
  choose_install_action
  print_plan "${INSTALL_ACTION}"
  confirm_install
  if [[ "${INSTALL_ACTION}" == "delete" ]]; then
    delete_existing_ct
    prepare_new_ct
    INSTALL_ACTION=fresh
  fi
  local ip
  if [[ "${INSTALL_ACTION}" == "update" ]]; then
    update_existing_ct "${THESHED_REF}"
    load_operator_from_ct
    if [[ -z "${CT_ROOT_PASSWORD}" ]]; then
      apply_ct_root_password
      persist_ct_root_password
    fi
    ip="$(ct_ip)"
    if [[ -z "${ip}" ]]; then
      echo "Could not determine the CT address. Set THESHED_CT_IP." >&2
      exit 1
    fi
    print_url "${ip}"
    wait_ready "${ip}"
    verify_running_image "${ip}"
    write_state "${ip}" "${THESHED_REF}"
    print_summary "${ip}"
    return 0
  fi
  STORAGE="$(resolve_storage)"
  echo "Using storage ${STORAGE} for the CT rootfs"
  local template
  template="$(ensure_template)"
  ensure_operator_password
  ensure_ct_root_password
  create_ct "${template}"
  bootstrap_ct "${THESHED_REF}"
  ip="$(ct_ip)"
  if [[ -z "${ip}" ]]; then
    echo "Could not determine the CT address. Set THESHED_CT_IP." >&2
    exit 1
  fi
  print_url "${ip}"
  wait_ready "${ip}"
  verify_running_image "${ip}"
  write_state "${ip}" "${THESHED_REF}"
  print_summary "${ip}"
}

main "$@"
