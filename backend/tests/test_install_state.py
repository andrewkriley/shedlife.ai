from theshed.bootstrap.install_state import (
    InstallState,
    parse_state,
    render_url,
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
