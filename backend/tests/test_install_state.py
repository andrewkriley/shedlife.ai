import pytest

from theshed.bootstrap.install_state import (
    PINNED_UBUNTU_VERSION,
    InstallState,
    ostemplate_volume,
    parse_state,
    parse_storage_cfg,
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


PVEAM_AVAILABLE = """
system          alpine-3.21-default_20241217_amd64.tar.xz
system          debian-13-standard_13.6-1_amd64.tar.zst
system          ubuntu-24.04-standard_24.04-2_amd64.tar.zst
system          ubuntu-25.04-standard_25.04-1.1_amd64.tar.zst
system          ubuntu-26.04-standard_26.04-1_amd64.tar.zst
"""


def test_pinned_ubuntu_version_is_the_current_latest_lts() -> None:
    assert PINNED_UBUNTU_VERSION == "26.04"


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
