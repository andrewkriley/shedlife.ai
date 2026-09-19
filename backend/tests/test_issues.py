from theshed.issues.redact import classify_and_redact, looks_like_secret


def test_api_key_shaped_strings_are_secrets() -> None:
    assert looks_like_secret("sk-ant-api03-abcdefghijklmnopqrstuvwxyz")
    assert looks_like_secret("local://providers/llm/api_key=sk-ant-x")


def test_redaction_strips_secrets_from_detail() -> None:
    raw = "failed talking to host with key sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    classification, detail = classify_and_redact("socket timeout: " + raw)
    assert "sk-ant" not in detail
    assert "[redacted]" in detail
    assert classification == "environment"


def test_validation_style_messages_are_operator_input() -> None:
    classification, _ = classify_and_redact("tenant.slug must match [a-z0-9-]+")
    assert classification == "operator-input"
