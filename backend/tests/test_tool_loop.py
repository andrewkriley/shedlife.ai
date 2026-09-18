import pytest

from theshed.agents.tool_loop import (
    ApprovalRequired,
    LoopGuard,
    MaxRoundsExceeded,
    RepeatedCallDetected,
    ToolCall,
    UnproductiveLoopDetected,
    canonicalize_arguments,
)


class TestCanonicalizeArguments:
    def test_trims_whitespace(self) -> None:
        assert canonicalize_arguments({"q": "network status"}) == canonicalize_arguments(
            {"q": "  network status  "}
        )

    def test_key_order_does_not_matter(self) -> None:
        assert canonicalize_arguments({"a": 1, "b": 2}) == canonicalize_arguments({"b": 2, "a": 1})

    def test_different_values_are_not_equal(self) -> None:
        assert canonicalize_arguments({"q": "network"}) != canonicalize_arguments({"q": "dns"})


class TestMaxRounds:
    def test_raises_after_max_rounds(self) -> None:
        guard = LoopGuard(max_rounds=2)
        guard.before_call(ToolCall("search", {"q": "a"}))
        guard.before_call(ToolCall("search", {"q": "b"}))
        with pytest.raises(MaxRoundsExceeded):
            guard.before_call(ToolCall("search", {"q": "c"}))


class TestRepeatedCallGuard:
    def test_raises_on_exact_repeat(self) -> None:
        guard = LoopGuard()
        guard.before_call(ToolCall("search", {"q": "network"}))
        with pytest.raises(RepeatedCallDetected):
            guard.before_call(ToolCall("search", {"q": "network"}))

    def test_raises_on_cosmetically_different_repeat(self) -> None:
        guard = LoopGuard()
        guard.before_call(ToolCall("search", {"q": "network"}))
        with pytest.raises(RepeatedCallDetected):
            guard.before_call(ToolCall("search", {"q": "  network  "}))

    def test_allows_genuinely_different_calls(self) -> None:
        guard = LoopGuard()
        guard.before_call(ToolCall("search", {"q": "network"}))
        guard.before_call(ToolCall("search", {"q": "dns"}))  # no raise


class TestUnproductiveLoopDetection:
    def test_raises_when_last_k_results_identical_despite_varying_calls(self) -> None:
        guard = LoopGuard(unproductive_window=3)
        guard.before_call(ToolCall("search", {"q": "a"}))
        guard.after_result("no results found")
        guard.before_call(ToolCall("search", {"q": "b"}))
        guard.after_result("no results found")
        guard.before_call(ToolCall("search", {"q": "c"}))
        with pytest.raises(UnproductiveLoopDetected):
            guard.after_result("no results found")

    def test_does_not_raise_when_results_vary(self) -> None:
        guard = LoopGuard(unproductive_window=3)
        guard.before_call(ToolCall("search", {"q": "a"}))
        guard.after_result("result A")
        guard.before_call(ToolCall("search", {"q": "b"}))
        guard.after_result("result B")
        guard.before_call(ToolCall("search", {"q": "c"}))
        guard.after_result("result C")  # no raise


class TestApprovalGate:
    def test_side_effect_call_raises_approval_required_instead_of_proceeding(self) -> None:
        guard = LoopGuard()
        call = ToolCall("confirm_create_firewall_policy", {"name": "x"}, has_side_effects=True)
        with pytest.raises(ApprovalRequired) as exc_info:
            guard.before_call(call)
        assert exc_info.value.call is call

    def test_non_side_effect_call_does_not_raise(self) -> None:
        guard = LoopGuard()
        guard.before_call(ToolCall("web_search", {"q": "x"}, has_side_effects=False))  # no raise
