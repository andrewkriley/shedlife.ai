from theshed.agents.providers.openai import (
    _to_openai_messages,
    _to_openai_tools,
    completion_kwargs,
)


def test_to_openai_messages_keeps_plain_turns() -> None:
    out = _to_openai_messages(
        "You are helpful.",
        [{"role": "user", "content": "hi"}],
    )
    assert out[0] == {"role": "system", "content": "You are helpful."}
    assert out[1] == {"role": "user", "content": "hi"}


def test_to_openai_messages_rewrites_anthropic_tool_blocks() -> None:
    out = _to_openai_messages(
        "sys",
        [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "calling"},
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "foundations_read",
                        "input": {},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_1", "content": "{}"},
                ],
            },
        ],
    )
    assert out[1]["role"] == "assistant"
    assert out[1]["tool_calls"][0]["id"] == "call_1"
    assert out[2] == {"role": "tool", "tool_call_id": "call_1", "content": "{}"}


def test_gpt_5_4_uses_reasoning_chat_completion_params() -> None:
    kwargs = completion_kwargs(
        model="gpt-5.4",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"name": "foundations_read", "input_schema": {"type": "object"}}],
    )
    assert kwargs["model"] == "gpt-5.4"
    assert kwargs["max_completion_tokens"] == 4096
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["tools"][0]["function"]["name"] == "foundations_read"


def test_to_openai_tools_maps_input_schema() -> None:
    tools = _to_openai_tools(
        [{"name": "foundations_read", "description": "Read", "input_schema": {"type": "object"}}]
    )
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "foundations_read"
    assert tools[0]["function"]["parameters"] == {"type": "object"}
