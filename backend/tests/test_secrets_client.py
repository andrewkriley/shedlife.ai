import pytest

from theshed.secrets.client import EnvVarSecretsClient, SecretNotFoundError

REF = "infisical://the-shed/providers/anthropic/api_key"


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_resolves_mapped_reference_from_env() -> None:
    client = EnvVarSecretsClient(env={"ANTHROPIC_API_KEY": "sk-ant-test"})
    assert client.get(REF) == "sk-ant-test"


def test_unmapped_reference_raises() -> None:
    client = EnvVarSecretsClient(mapping={}, env={"ANTHROPIC_API_KEY": "sk-ant-test"})
    with pytest.raises(SecretNotFoundError):
        client.get(REF)


def test_mapped_but_unset_env_var_raises() -> None:
    client = EnvVarSecretsClient(env={})
    with pytest.raises(SecretNotFoundError):
        client.get(REF)


def test_caches_within_ttl_without_rereading_env() -> None:
    clock = FakeClock()
    env = {"ANTHROPIC_API_KEY": "sk-ant-first"}
    client = EnvVarSecretsClient(env=env, ttl_seconds=60.0, clock=clock)

    assert client.get(REF) == "sk-ant-first"
    env["ANTHROPIC_API_KEY"] = "sk-ant-second"
    clock.now += 30.0  # still within TTL
    assert client.get(REF) == "sk-ant-first"  # cached, not re-read


def test_refetches_after_ttl_expires_picking_up_rotation() -> None:
    clock = FakeClock()
    env = {"ANTHROPIC_API_KEY": "sk-ant-first"}
    client = EnvVarSecretsClient(env=env, ttl_seconds=60.0, clock=clock)

    assert client.get(REF) == "sk-ant-first"
    env["ANTHROPIC_API_KEY"] = "sk-ant-rotated"
    clock.now += 61.0  # past TTL
    assert client.get(REF) == "sk-ant-rotated"


def test_default_mapping_includes_galileo_key() -> None:
    galileo_ref = "infisical://the-shed/observability/galileo_api_key"
    client = EnvVarSecretsClient(env={"GALILEO_API_KEY": "galileo-test-key"})
    assert client.get(galileo_ref) == "galileo-test-key"
