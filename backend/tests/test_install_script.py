import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bootstrap" / "install.sh"
README = ROOT / "README.md"


def _write_exec(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)


def _install_lib(tmp_path: Path) -> Path:
    text = SCRIPT.read_text()
    if not text.rstrip().endswith('main "$@"'):
        raise AssertionError('install.sh must end with main "$@" so tests can source helpers')
    lib = tmp_path / "install-lib.sh"
    lib.write_text(text.rsplit('main "$@"', 1)[0])
    return lib


def _run_vmid_helpers(
    tmp_path: Path,
    body: str,
    *,
    taken_pct: tuple[str, ...] = (),
    taken_qm: tuple[str, ...] = (),
    nextid_taken: tuple[str, ...] = (),
    vmlist_ids: tuple[str, ...] = (),
    conf_ids: tuple[tuple[str, str], ...] = (),
    shed_cts: tuple[tuple[str, str, str], ...] = (),
    state_ctid: str | None = None,
    state_ip: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    work = tmp_path / "vmid"
    bindir = work / "bin"
    pve = work / "pve"
    bindir.mkdir(parents=True)
    pve.mkdir(parents=True)

    taken = list(taken_pct)
    for vmid, _status, _name in shed_cts:
        if vmid not in taken:
            taken.append(vmid)
    pct_ids = " ".join(taken)
    qm_ids = " ".join(taken_qm)
    nextid_ids = " ".join(nextid_taken)
    list_rows = "\n".join(f"{vmid} {status} - {name}" for vmid, status, name in shed_cts)
    config_cases = "\n".join(
        f'    {vmid}) echo "hostname: {name}" ;;' for vmid, _status, name in shed_cts
    )
    _write_exec(
        bindir / "pct",
        f"""#!/usr/bin/env bash
cmd="${{1:-}}"
id="${{2:-}}"
taken="{pct_ids}"
case "${{cmd}}" in
  status)
    for t in $taken; do
      [[ "${{id}}" == "${{t}}" ]] && echo "status: running" && exit 0
    done
    exit 1
    ;;
  list)
    echo "VMID Status Lock Name"
    printf '%s\\n' "{list_rows}"
    ;;
  config)
    case "${{id}}" in
{config_cases}
      *) exit 1 ;;
    esac
    ;;
  exec)
    echo "10.54.10.172"
    ;;
  *) exit 0 ;;
esac
""",
    )
    _write_exec(
        bindir / "curl",
        """#!/usr/bin/env bash
exit 1
""",
    )
    _write_exec(
        bindir / "qm",
        f"""#!/usr/bin/env bash
cmd="${{1:-}}"
id="${{2:-}}"
taken="{qm_ids}"
case "${{cmd}}" in
  status)
    for t in $taken; do
      [[ "${{id}}" == "${{t}}" ]] && exit 0
    done
    exit 1
    ;;
  *) exit 0 ;;
esac
""",
    )
    _write_exec(
        bindir / "pvesh",
        f"""#!/usr/bin/env bash
vmid=""
taken="{nextid_ids}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vmid)
      vmid="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
for t in $taken; do
  if [[ "${{vmid}}" == "${{t}}" ]]; then
    echo "VM ${{vmid}} already exists" >&2
    exit 1
  fi
done
if [[ -n "${{vmid}}" ]]; then
  echo "${{vmid}}"
  exit 0
fi
exit 1
""",
    )
    if vmlist_ids:
        entries = ",".join(
            f'"{vid}":{{"node":"other","type":"qemu","version":1}}' for vid in vmlist_ids
        )
        (pve / ".vmlist").write_text(f'{{"version":1,"ids":{{{entries}}}}}\n')
    for kind, vid in conf_ids:
        folder = "lxc" if kind == "lxc" else "qemu-server"
        conf_dir = pve / "nodes" / "other" / folder
        conf_dir.mkdir(parents=True, exist_ok=True)
        (conf_dir / f"{vid}.conf").write_text("name: overlap\n")

    lib = _install_lib(tmp_path)
    script = work / "run.sh"
    script.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
export PATH="{bindir}:$PATH"
export THESHED_PVE_ETC="{pve}"
source "{lib}"
{body}
"""
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("THESHED_")}
    if extra_env:
        env.update(extra_env)
    if state_ctid is not None:
        state_path = work / "install-state.yaml"
        state_path.write_text(
            "version: 1\n"
            f"ctid: {state_ctid}\n"
            f"ct_ip: {state_ip or '10.54.10.189'}\n"
            "image_ref: theshed-v0.4.15\n"
        )
        env["THESHED_STATE_FILE"] = str(state_path)
    env.setdefault("PATH", os.environ.get("PATH", "/usr/bin:/bin"))
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_install_script_writes_theshed_ref_into_ct_env() -> None:
    text = SCRIPT.read_text()
    assert "THESHED_REF=${THESHED_REF}" in text
    assert "upsert_ct_env" in text
    update = text.split("update_existing_ct() {", 1)[1].split("\n}\n", 1)[0]
    assert "upsert_ct_env THESHED_REF" in update
    assert 'pct set "${CTID}" --hostname "${CT_HOSTNAME}"' in update
    assert 'CT_HOSTNAME="theshed"' in update
    compose = (ROOT / "bootstrap" / "docker-compose.yml").read_text()
    assert "THESHED_REF: ${THESHED_REF:-}" in compose


def test_install_script_exists_and_is_thin() -> None:
    text = SCRIPT.read_text()
    assert SCRIPT.is_file()
    assert text.startswith("#!/usr/bin/env bash")
    assert "THESHED_REF" in text
    assert "/api/setup/status" in text
    assert "install-state.yaml" in text
    assert "pct create" in text


def test_install_script_does_not_collect_operator_secrets() -> None:
    text = SCRIPT.read_text()
    assert "Does not collect an LLM API key" in text
    assert "read -p" not in text
    assert "ANTHROPIC_API_KEY" not in text
    assert "sk-ant" not in text


def test_install_script_confirms_fresh_update_or_delete() -> None:
    text = SCRIPT.read_text()
    assert "inspect_existing" in text
    assert "print_existing_installs" in text
    assert "choose_install_action" in text
    assert "print_plan" in text
    assert "confirm_install" in text
    assert "update_existing_ct" in text
    assert "/dev/tty" in text
    assert "read -r" in text
    assert "THESHED_YES" in text
    assert "--yes" in text
    assert "fresh install" in text
    assert "UPDATE" in text
    assert "DESTROY" in text
    assert "parallel" in text
    assert "next_free_vmid" in text
    assert "list_shed_cts" in text
    main = text.split("main() {", 1)[1]
    assert main.index("inspect_existing") < main.index("print_existing_installs")
    assert main.index("print_existing_installs") < main.index("choose_install_action")
    assert main.index("choose_install_action") < main.index("print_plan")
    assert main.index("print_plan") < main.index("confirm_install")
    assert main.index("confirm_install") < main.index("create_ct")
    assert 'action="$(choose_install_action)"' not in text
    assert "INSTALL_ACTION" in main
    assert "prepare_new_ct" in text
    assert "select_upgrade_ct" in text
    assert "first_listed_shed_vmid" in text
    assert "next_free_vmid quiet" in text
    fresh = text.split("choose_install_action() {", 1)[1].split("\n}\n", 1)[0]
    assert fresh.index("count") < fresh.index("prepare_new_ct")
    assert "pvesh get /cluster/nextid" in text
    assert "vmid_in_use" in text
    create = text.split("create_ct() {", 1)[1].split("bootstrap_ct() {", 1)[0]
    assert "vmid_in_use" in create


def test_readme_install_is_a_one_line_latest_release() -> None:
    text = README.read_text()
    assert (
        "curl -fsSL https://github.com/andrewkriley/shedlife.ai/releases/latest/download/install.sh | bash"
        in text
    )
    assert "tag=$(" not in text


def test_readme_shows_phase_progress_and_ends_at_the_loop() -> None:
    text = README.read_text()
    assert "1. Bootstrap" in text
    assert "In progress" in text
    assert "Not started" in text
    assert "## How a message becomes an answer" in text
    assert "## Status" not in text
    assert "## Documentation" not in text
    assert "## Contributing" not in text
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings[-1] == "## How a message becomes an answer"


def test_install_script_pins_ubuntu_26_04() -> None:
    text = SCRIPT.read_text()
    assert "debian-12-standard" not in text
    assert "ubuntu-26.04-standard" in text
    assert "ubuntu-[0-9]" not in text
    assert "sort -V" in text
    assert "pveam download local \"${name}\" >&2" in text
    assert 'volume="local:vztmpl/${name}"' in text
    assert "-gt 255" in text


def test_install_script_detects_rootfs_storage() -> None:
    text = SCRIPT.read_text()
    assert 'STORAGE="${THESHED_STORAGE:-local-lvm}"' not in text
    assert "/etc/pve/storage.cfg" in text
    assert "pvesm status --storage" in text
    assert "THESHED_STORAGE" in text
    assert "--rootfs" in text


def test_install_script_names_the_ct_theshed() -> None:
    text = SCRIPT.read_text()
    assert "--hostname theshed \\" not in text
    assert 'CT_HOSTNAME="${THESHED_HOSTNAME:-theshed}"' in text
    assert '--hostname "${CT_HOSTNAME}"' in text
    host_fn = text.split("hostname_for_new_ct() {", 1)[1].split("\n}\n", 1)[0]
    assert 'echo "theshed"' in host_fn
    assert "theshed-${CTID}" not in host_fn
    assert "theshed-deploy" not in text


def test_install_script_accepts_delete_flag() -> None:
    text = SCRIPT.read_text()
    assert "--delete" in text
    assert "THESHED_DELETE" in text
    assert "pct destroy" in text
    assert "pct stop" in text
    assert "bash -s -- --delete" in README.read_text()


def test_install_script_prints_connect_url_before_health_wait() -> None:
    text = SCRIPT.read_text()
    assert 'The Shed is starting at: http://${1}:${PORT}' in text
    main = text.split("main() {", 1)[1]
    assert main.index("print_url") < main.index("wait_ready")
    print_url = text.split("print_url() {", 1)[1].split("write_ct_notes() {", 1)[0]
    assert "Waiting for GET ${READY_PATH}" in print_url
    assert "Username:" not in print_url
    assert "Password:" not in print_url
    assert "CT user:" not in print_url
    assert "CT pass:" not in print_url
    assert main.count("print_url") == 2
    assert main.count("print_summary") == 2
    assert main.count('echo "Waiting for GET') == 0


def test_install_script_prints_completion_summary() -> None:
    text = SCRIPT.read_text()
    assert "print_summary" in text
    assert "The Shed is ready." in text
    assert "URL:" in text
    assert "Username:" in text
    assert "Password:" in text
    assert "CT user:" in text
    assert "CT pass:" in text
    assert "THESHED_OPERATOR_USERNAME" in text
    assert "THESHED_OPERATOR_PASSWORD" in text
    assert "THESHED_CT_ROOT_PASSWORD" in text
    main = text.split("main() {", 1)[1]
    assert main.index("wait_ready") < main.index("print_summary")


def test_install_script_writes_completion_details_to_ct_notes() -> None:
    text = SCRIPT.read_text()
    assert "write_ct_notes" in text
    assert 'pct set "${CTID}" --description' in text
    notes = text.split("write_ct_notes() {", 1)[1].split("\n}\n", 1)[0]
    assert "URL:" in notes
    assert "Username:" in notes
    assert "Password:" in notes
    assert "CT user:" in notes
    assert "CT pass:" in notes
    assert "OPERATOR_PASSWORD" in notes
    assert "CT_ROOT_PASSWORD" in notes
    summary = text.split("print_summary() {", 1)[1].split("\n}\n", 1)[0]
    assert "write_ct_notes" in summary
    main = text.split("main() {", 1)[1]
    assert main.index("wait_ready") < main.index("print_summary")


def test_install_script_sets_generated_ct_root_password() -> None:
    text = SCRIPT.read_text()
    assert "--password" in text
    assert "ensure_ct_root_password" in text
    assert "CT_ROOT_PASSWORD" in text
    assert "chpasswd" in text
    assert "persist_ct_root_password" in text
    create = text.split("create_ct() {", 1)[1].split("bootstrap_ct() {", 1)[0]
    assert '--password "${CT_ROOT_PASSWORD}"' in create
    main = text.split("main() {", 1)[1]
    assert main.index("ensure_ct_root_password") < main.index("create_ct")


def test_install_script_waits_on_setup_status_not_health() -> None:
    text = SCRIPT.read_text()
    assert "/api/setup/status" in text
    assert "wait_ready" in text
    assert "ct_ready_ok" in text
    wait = text.split("wait_ready() {", 1)[1].split("main() {", 1)[0]
    assert "/health" not in wait
    assert "pct exec" in text.split("ct_ready_ok() {", 1)[1].split("read_state_ip() {", 1)[0]


def test_install_script_defaults_web_user_to_admin() -> None:
    text = SCRIPT.read_text()
    assert 'OPERATOR_USERNAME="${THESHED_OPERATOR_USERNAME:-${THESHED_OPERATOR_EMAIL:-admin}}"' in text
    assert "operator@theshed.local" not in text


def test_install_script_offers_upgrade_or_parallel() -> None:
    text = SCRIPT.read_text()
    assert "--parallel" in text
    assert "THESHED_PARALLEL" in text
    assert "list_shed_cts" in text
    assert 'echo "theshed"' in text
    assert "Upgrade an existing installation" in text
    assert "parallel instance" in text
    assert "bash -s -- --parallel" in text
    readme = README.read_text()
    assert "parallel" in readme.lower()
    text = SCRIPT.read_text()
    assert "--debug" in text
    assert "THESHED_DEBUG" in text
    assert "/debug/logs" in text
    assert "bash -s -- --debug" in text


def test_install_script_follows_debug_logs_to_tty1() -> None:
    text = SCRIPT.read_text()
    assert "follow_debug_to_tty" in text
    assert "/dev/tty1" in text
    assert "logs -f" in text
    assert "theshed-debug-tty.pid" in text
    compose = text.split("compose_up() {", 1)[1].split("write_fresh_env() {", 1)[0]
    assert "follow_debug_to_tty" in compose


def test_next_free_vmid_keeps_9100_when_cluster_is_clear(tmp_path: Path) -> None:
    result = _run_vmid_helpers(tmp_path, "next_free_vmid")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "9100"


def test_next_free_vmid_skips_local_ct_and_vm(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        "next_free_vmid",
        taken_pct=("9100",),
        taken_qm=("9101",),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "9102"
    assert "VMID 9100 is already in use" in result.stderr
    assert "VMID 9101 is already in use" in result.stderr


def test_next_free_vmid_skips_ids_listed_on_another_node(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        "next_free_vmid",
        vmlist_ids=("9100", "9101"),
        conf_ids=(("qemu", "9102"), ("lxc", "9103")),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "9104"


def test_next_free_vmid_trusts_cluster_nextid(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        "next_free_vmid",
        nextid_taken=("9100", "9101"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "9102"


def test_fresh_prepare_uses_cluster_free_vmid(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        'prepare_new_ct\nprintf "CTID=%s HOST=%s\\n" "${CTID}" "${CT_HOSTNAME}"\n',
        vmlist_ids=("9100",),
    )
    assert result.returncode == 0, result.stderr
    assert "CTID=9101 HOST=theshed" in result.stdout


def test_fresh_prepare_names_the_ct_theshed_when_9100_is_free(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        'prepare_new_ct\nprintf "CTID=%s HOST=%s\\n" "${CTID}" "${CT_HOSTNAME}"\n',
    )
    assert result.returncode == 0, result.stderr
    assert "CTID=9100 HOST=theshed" in result.stdout


def test_explicit_ctid_refuses_cluster_overlap(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        "next_free_vmid",
        taken_qm=("9200",),
        extra_env={"THESHED_CTID": "9200"},
    )
    assert result.returncode != 0
    assert "THESHED_CTID=9200 is already in use on this Proxmox cluster." in result.stderr


def test_create_ct_rechecks_vmid_against_the_cluster(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        'CTID=9100\nif vmid_in_use "${CTID}"; then echo TAKEN; else echo FREE; fi\n',
        nextid_taken=("9100",),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "TAKEN"


def test_inspect_existing_ignores_a_stale_state_vmid(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        'inspect_existing\nprintf "CTID=%s EXISTS=%s HOST=%s IP=%s\\n" "${CTID}" "${CT_EXISTS}" "${CT_HOSTNAME}" "${EXISTING_IP}"\n',
        shed_cts=(("9100", "running", "theshed-deploy"),),
        state_ctid="9101",
        state_ip="10.54.10.189",
    )
    assert result.returncode == 0, result.stderr
    assert "CTID=9100 EXISTS=1 HOST=theshed-deploy IP=10.54.10.172" in result.stdout


def test_upgrade_option_targets_the_listed_ct_not_nextid(tmp_path: Path) -> None:
    result = _run_vmid_helpers(
        tmp_path,
        "inspect_existing\nselect_upgrade_ct\n"
        'printf "CTID=%s EXISTS=%s HOST=%s\\n" "${CTID}" "${CT_EXISTS}" "${CT_HOSTNAME}"\n',
        shed_cts=(("9100", "running", "theshed-deploy"),),
        state_ctid="9101",
        state_ip="10.54.10.189",
    )
    assert result.returncode == 0, result.stderr
    assert "CTID=9100 EXISTS=1 HOST=theshed-deploy" in result.stdout


def test_next_free_vmid_quiet_hides_skip_messages(tmp_path: Path) -> None:
    result = _run_vmid_helpers(tmp_path, "next_free_vmid quiet", taken_pct=("9100",))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "9101"
    assert "trying the next id" not in result.stderr


def test_install_script_prints_banner_first() -> None:
    text = SCRIPT.read_text()
    assert "Your digital shed -- the place you" in text
    assert "print_banner" in text
    banner_at = text.index("print_banner")
    ref_at = text.index('echo "The Shed installer')
    assert banner_at < ref_at
