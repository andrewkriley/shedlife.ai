from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bootstrap" / "install.sh"
README = ROOT / "README.md"


def test_install_script_writes_theshed_ref_into_ct_env() -> None:
    text = SCRIPT.read_text()
    assert "THESHED_REF=${THESHED_REF}" in text
    assert "upsert_ct_env" in text
    update = text.split("update_existing_ct() {", 1)[1].split("\n}\n", 1)[0]
    assert "upsert_ct_env THESHED_REF" in update
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


def test_install_script_names_the_ct_theshed_deploy() -> None:
    text = SCRIPT.read_text()
    assert "--hostname theshed \\" not in text
    assert "theshed-deploy" in text
    assert '--hostname "${CT_HOSTNAME}"' in text


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
    assert "theshed-${CTID}" in text
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


def test_install_script_prints_banner_first() -> None:
    text = SCRIPT.read_text()
    assert "Your digital shed -- the place you" in text
    assert "print_banner" in text
    banner_at = text.index("print_banner")
    ref_at = text.index('echo "The Shed installer')
    assert banner_at < ref_at
