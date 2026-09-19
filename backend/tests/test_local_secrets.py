from pathlib import Path

import pytest

from theshed.secrets.client import LocalSecretsClient, SecretNotFoundError

REF = "local://providers/llm/api_key"


def test_set_and_get_round_trip() -> None:
    client = LocalSecretsClient()
    client.set(REF, "sk-ant-test")
    assert client.get(REF) == "sk-ant-test"


def test_missing_reference_raises() -> None:
    client = LocalSecretsClient()
    with pytest.raises(SecretNotFoundError):
        client.get(REF)


def test_rejects_non_local_scheme_on_set() -> None:
    client = LocalSecretsClient()
    with pytest.raises(ValueError, match="local://"):
        client.set("infisical://the-shed/providers/anthropic/api_key", "x")


def test_persists_to_path(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    writer = LocalSecretsClient(path=path)
    writer.set(REF, "sk-ant-persisted")

    reader = LocalSecretsClient(path=path)
    assert reader.get(REF) == "sk-ant-persisted"


def test_file_is_owner_read_write_only(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    client = LocalSecretsClient(path=path)
    client.set(REF, "sk-ant-perm")
    assert oct(path.stat().st_mode)[-3:] == "600"
