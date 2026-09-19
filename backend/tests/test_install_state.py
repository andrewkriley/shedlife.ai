import pytest

from theshed.bootstrap.install_state import (
    InstallState,
    ostemplate_volume,
    parse_state,
    render_url,
    select_os_template,
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
system          debian-12-standard_12.7-1_amd64.tar.zst
system          debian-13-standard_13.1-1_amd64.tar.zst
system          ubuntu-22.04-standard_22.04-1_amd64.tar.zst
system          ubuntu-24.04-standard_24.04-1_amd64.tar.zst
system          ubuntu-24.04-standard_24.04-2_amd64.tar.zst
system          ubuntu-25.04-standard_25.04-1_amd64.tar.zst
"""


def test_select_os_template_picks_latest_ubuntu_standard() -> None:
    assert (
        select_os_template(PVEAM_AVAILABLE)
        == "ubuntu-25.04-standard_25.04-1_amd64.tar.zst"
    )


def test_select_os_template_prefers_newer_build_of_same_series() -> None:
    available = """
system          ubuntu-24.04-standard_24.04-1_amd64.tar.zst
system          ubuntu-24.04-standard_24.04-2_amd64.tar.zst
"""
    assert (
        select_os_template(available) == "ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
    )


def test_select_os_template_returns_none_without_ubuntu() -> None:
    assert select_os_template("system          debian-12-standard_12.7-1_amd64.tar.zst") is None


def test_ostemplate_volume_is_a_short_pve_volume_id() -> None:
    volume = ostemplate_volume("ubuntu-25.04-standard_25.04-1_amd64.tar.zst")
    assert volume == "local:vztmpl/ubuntu-25.04-standard_25.04-1_amd64.tar.zst"
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
