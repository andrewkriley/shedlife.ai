import pytest

from theshed.profile import cookie_secure, current_profile, is_bootstrap_profile


def test_default_profile_is_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("THESHED_PROFILE", raising=False)
    assert current_profile() == "full"
    assert is_bootstrap_profile() is False
    assert cookie_secure() is True


def test_bootstrap_profile_disables_secure_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THESHED_PROFILE", "bootstrap")
    assert is_bootstrap_profile() is True
    assert cookie_secure() is False


def test_explicit_cookie_secure_overrides_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THESHED_PROFILE", "bootstrap")
    monkeypatch.setenv("THESHED_COOKIE_SECURE", "1")
    assert cookie_secure() is True
