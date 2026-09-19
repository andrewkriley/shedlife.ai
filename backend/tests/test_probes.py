from theshed.probes.runner import (
    MIN_DISK_GB,
    MIN_RAM_GB,
    MIN_VCPU,
    ProbeResult,
    run_probe,
)


class FakeHost:
    def llm_key(self) -> ProbeResult:
        return ProbeResult("pass")

    def outbound_https(self) -> ProbeResult:
        return ProbeResult("pass")

    def proxmox_api(self) -> ProbeResult:
        return ProbeResult("pass")

    def proxmox_capacity(self) -> ProbeResult:
        return ProbeResult(
            "warn",
            detail=f"below minimums ({MIN_VCPU} vCPU / {MIN_RAM_GB} GiB / {MIN_DISK_GB} GiB)",
        )

    def bridge_exists(self) -> ProbeResult:
        return ProbeResult("pass")

    def storage_pool_exists(self) -> ProbeResult:
        return ProbeResult("pass")

    def ntp_ok(self) -> ProbeResult:
        return ProbeResult("pass")

    def ssh_key_installed(self) -> ProbeResult:
        return ProbeResult("pass")

    def adopted_endpoint(self) -> ProbeResult:
        return ProbeResult("skip")

    def domain_resolves(self) -> ProbeResult:
        return ProbeResult("warn", detail="name does not resolve yet")


def test_known_probe_runs_against_host() -> None:
    result = run_probe("llm_key", FakeHost())
    assert result.status == "pass"


def test_capacity_warns_instead_of_failing() -> None:
    result = run_probe("proxmox_capacity", FakeHost())
    assert result.status == "warn"


def test_unknown_probe_is_an_error() -> None:
    result = run_probe("invented", FakeHost())
    assert result.status == "error"


def test_host_exception_is_error_not_a_field_typo() -> None:
    class Boom:
        def llm_key(self) -> ProbeResult:
            raise RuntimeError("socket closed")

    result = run_probe("llm_key", Boom())
    assert result.status == "error"
    assert "socket closed" in (result.detail or "")
