import pytest

from theshed.bootstrap.install_state import (
    DEFAULT_CT_HOSTNAME,
    PINNED_UBUNTU_VERSION,
    InstallState,
    classify_install,
    completion_summary,
    delete_target_ctid,
    install_plan_warning,
    ostemplate_volume,
    parse_state,
    parse_storage_cfg,
    proxmox_notes,
    render_url,
    select_os_template,
    select_rootfs_storage,
    should_reuse,
)


def test_no_state_means_create() -> None:
    assert should_reuse(None, live_health_ok=True) is False


def test_healthy_recorded_and_live_ct_is_reused() -> None:
    state = InstallState(ctid=200, ct_ip="192.0.2.50", image_ref="v0.3.0", health_ok=True)
    assert should_reuse(state, live_health_ok=True) is True


def test_delete_flag_skips_reuse() -> None:
    state = InstallState(ctid=200, ct_ip="192.0.2.50", image_ref="v0.3.0", health_ok=True)
    assert should_reuse(state, live_health_ok=True, delete_requested=True) is False


def test_delete_target_prefers_recorded_ctid() -> None:
    state = InstallState(ctid=200, ct_ip="192.0.2.50", image_ref="v0.3.0", health_ok=True)
    assert delete_target_ctid(state, default_ctid=9100) == 200
    assert delete_target_ctid(None, default_ctid=9100) == 9100


def test_classify_install_fresh_update_or_delete() -> None:
    assert classify_install(delete_requested=False, ct_present=False) == "fresh"
    assert classify_install(delete_requested=False, ct_present=True) == "update"
    assert classify_install(delete_requested=True, ct_present=True) == "delete"
    assert classify_install(delete_requested=True, ct_present=False) == "delete"


def test_install_plan_warning_fresh() -> None:
    text = install_plan_warning("fresh", ctid=9100, ct_status="missing")
    assert "Action:  fresh" in text
    assert "not present" in text or "missing" in text
    assert "fresh install" in text
    assert "Type yes to continue." in text


def test_install_plan_warning_update_shows_status() -> None:
    text = install_plan_warning(
        "update",
        ctid=9100,
        ct_status="running",
        app_ready=True,
        ct_ip="192.0.2.50",
        image_ref="theshed-v0.4.7",
    )
    assert "Action:  update" in text
    assert "running" in text
    assert "App:     ready" in text
    assert "UPDATE" in text
    assert "http://192.0.2.50:8080" in text


def test_install_plan_warning_delete_destroys_ct() -> None:
    text = install_plan_warning("delete", ctid=9100, hostname="theshed-deploy", ct_status="running")
    assert "DESTROY" in text
    assert "9100" in text
    assert "theshed-deploy" in text


def test_stale_state_without_live_health_creates_again() -> None:
    state = InstallState(ctid=200, ct_ip="192.0.2.50", image_ref="v0.3.0", health_ok=True)
    assert should_reuse(state, live_health_ok=False) is False


def test_parse_state_reads_the_spec_shape() -> None:
    parsed = parse_state(
        {
            "ctid": 200,
            "ct_ip": "192.0.2.50",
            "image_ref": "v0.3.0",
            "health": {"last_ok": "2026-09-20T00:00:00Z"},
        }
    )
    assert parsed is not None
    assert parsed.ctid == 200
    assert render_url(parsed.ct_ip) == "http://192.0.2.50:8080"


def test_completion_summary_includes_ready_and_url() -> None:
    text = completion_summary(
        ct_ip="192.0.2.50",
        ctid=9100,
        hostname="theshed-deploy",
        image_ref="theshed-v0.4.4",
    )
    assert "The Shed is ready." in text
    assert "URL:  http://192.0.2.50:8080" in text
    assert "CT:   9100 (theshed-deploy)" in text
    assert "Ref:  theshed-v0.4.4" in text


def test_completion_summary_includes_login_and_debug() -> None:
    text = completion_summary(
        ct_ip="192.0.2.50",
        ctid=9100,
        hostname="theshed-deploy",
        image_ref="theshed-v0.4.6",
        username="admin",
        password="once-only",
        ct_password="ct-root-once",
        debug=True,
    )
    assert "Username: admin" in text
    assert "Password: once-only" in text
    assert "CT user: root" in text
    assert "CT pass: ct-root-once" in text
    assert "Debug: on" in text
    assert "/api/debug/logs" in text


def test_proxmox_notes_are_the_completion_details() -> None:
    text = proxmox_notes(
        ct_ip="192.0.2.50",
        ctid=9100,
        hostname="theshed-deploy",
        image_ref="theshed-v0.4.9",
        username="admin",
        password="once-only",
        ct_password="ct-root-once",
        debug=True,
    )
    assert "The Shed is ready." in text
    assert "URL:" in text
    assert "http://192.0.2.50:8080" in text
    assert "Username: admin" in text
    assert "Password: once-only" in text
    assert "CT user: root" in text
    assert "CT pass: ct-root-once" in text
    assert "9100 (theshed-deploy)" in text
    assert "theshed-v0.4.9" in text
    assert text == completion_summary(
        ct_ip="192.0.2.50",
        ctid=9100,
        hostname="theshed-deploy",
        image_ref="theshed-v0.4.9",
        username="admin",
        password="once-only",
        ct_password="ct-root-once",
        debug=True,
    )


PVEAM_AVAILABLE = """
system          alpine-3.21-default_20241217_amd64.tar.xz
system          debian-13-standard_13.6-1_amd64.tar.zst
system          ubuntu-24.04-standard_24.04-2_amd64.tar.zst
system          ubuntu-25.04-standard_25.04-1.1_amd64.tar.zst
system          ubuntu-26.04-standard_26.04-1_amd64.tar.zst
"""


def test_pinned_ubuntu_version_is_the_current_latest_lts() -> None:
    assert PINNED_UBUNTU_VERSION == "26.04"


def test_default_ct_hostname_distinguishes_the_bootstrap_ct() -> None:
    assert DEFAULT_CT_HOSTNAME == "theshed-deploy"


def test_select_os_template_locks_to_pinned_ubuntu_version() -> None:
    assert (
        select_os_template(PVEAM_AVAILABLE)
        == "ubuntu-26.04-standard_26.04-1_amd64.tar.zst"
    )


def test_select_os_template_ignores_newer_unpinned_ubuntu() -> None:
    available = (
        PVEAM_AVAILABLE + "system          ubuntu-26.10-standard_26.10-1_amd64.tar.zst\n"
    )
    assert (
        select_os_template(available) == "ubuntu-26.04-standard_26.04-1_amd64.tar.zst"
    )


def test_select_os_template_prefers_newer_build_of_pinned_series() -> None:
    available = """
system          ubuntu-26.04-standard_26.04-1_amd64.tar.zst
system          ubuntu-26.04-standard_26.04-2_amd64.tar.zst
"""
    assert (
        select_os_template(available) == "ubuntu-26.04-standard_26.04-2_amd64.tar.zst"
    )


def test_select_os_template_returns_none_without_pinned_ubuntu() -> None:
    assert select_os_template("system          ubuntu-24.04-standard_24.04-2_amd64.tar.zst") is None


def test_ostemplate_volume_is_a_short_pve_volume_id() -> None:
    volume = ostemplate_volume("ubuntu-26.04-standard_26.04-1_amd64.tar.zst")
    assert volume == "local:vztmpl/ubuntu-26.04-standard_26.04-1_amd64.tar.zst"
    assert len(volume) <= 255


def test_ostemplate_volume_rejects_pve_download_noise() -> None:
    noise = (
        "downloading http://download.proxmox.com/images/system/"
        "ubuntu-25.04-standard_25.04-1_amd64.tar.zst to "
        "/var/lib/vz/template/cache/ubuntu-25.04-standard_25.04-1_amd64.tar.zst "
        "(12345678/12345678 bytes)\n"
        "local:vztmpl/ubuntu-25.04-standard_25.04-1_amd64.tar.zst"
    )
    assert len(f"local:vztmpl/{noise}") > 255
    with pytest.raises(ValueError, match="255"):
        ostemplate_volume(noise)


PVESM_STATUS = """
Name             Type     Status           Total            Used       Available        %
local             dir     active        98402356         8234123        90168233    8.37%
local-lvm     lvmthin     active       157286400        12345678       144940722    7.85%
"""


def test_select_rootfs_storage_prefers_local_lvm() -> None:
    assert select_rootfs_storage(PVESM_STATUS) == "local-lvm"


def test_select_rootfs_storage_falls_back_to_local_zfs() -> None:
    status = """
Name             Type     Status           Total            Used       Available        %
local             dir     active        98402356         8234123        90168233    8.37%
local-zfs     zfspool     active      1900012344        12345678      1887666666    0.65%
"""
    assert select_rootfs_storage(status) == "local-zfs"


def test_select_rootfs_storage_uses_first_custom_name() -> None:
    status = """
Name             Type     Status           Total            Used       Available        %
nvme-tank     lvmthin     active       500000000        10000000       490000000    2.00%
"""
    assert select_rootfs_storage(status) == "nvme-tank"


def test_select_rootfs_storage_honors_requested_name() -> None:
    assert select_rootfs_storage(PVESM_STATUS, requested="local") == "local"


def test_select_rootfs_storage_rejects_missing_requested() -> None:
    with pytest.raises(ValueError, match="local-lvm"):
        select_rootfs_storage(
            """
Name             Type     Status           Total            Used       Available        %
nvme-tank     lvmthin     active       500000000        10000000       490000000    2.00%
""",
            requested="local-lvm",
        )


def test_select_rootfs_storage_skips_inactive() -> None:
    status = """
Name             Type     Status           Total            Used       Available        %
local-lvm     lvmthin  inactive       157286400               0       157286400    0.00%
nvme-tank     lvmthin     active       500000000        10000000       490000000    2.00%
"""
    assert select_rootfs_storage(status) == "nvme-tank"


def test_select_rootfs_storage_requires_an_active_rootdir() -> None:
    with pytest.raises(ValueError, match="rootdir"):
        select_rootfs_storage("Name             Type     Status\n")


STORAGE_CFG = """
dir: local
	path /var/lib/vz
	content iso,vztmpl,backup,snippets

lvmthin: local-lvm
	thinpool data
	vgname pve
	content rootdir,images

zfspool: tank
	pool tank
	content images,rootdir

dir: stale
	path /mnt/stale
	content rootdir
	disable 1
"""


def test_parse_storage_cfg_lists_enabled_rootdir_only() -> None:
    assert parse_storage_cfg(STORAGE_CFG) == ["local-lvm", "tank"]


def test_select_rootfs_storage_skips_unusable_local_lvm() -> None:
    assert select_rootfs_storage(PVESM_STATUS, usable=["tank", "local"]) == "local"
