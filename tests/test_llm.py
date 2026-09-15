"""Tests for the LLM layer's robustness rules (no network calls)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src import llm


def test_chain_is_ordered_and_non_empty():
    names = [p["name"] for p in llm.PROVIDERS]
    assert names, "chain must not be empty"
    assert names[0].startswith("or-"), names
    assert names[-1] == "deepseek-chat", names  # paid anchor stays last


def test_every_provider_has_key_and_url():
    for p in llm.PROVIDERS:
        assert p["key_var"] and p["url"] and p["models"], p


def test_extract_rejects_null_content():
    """A reasoning model returning content=null must count as a failure, not crash."""
    resp = {"choices": [{"message": {"content": None, "reasoning": None}}]}
    try:
        llm._extract_text(resp)
        assert False, "should have raised"
    except RuntimeError as e:
        assert "empty" in str(e)


def test_extract_rejects_thinking_leak():
    resp = {"choices": [{"message": {"content": "We need to produce concise review. 1.  **Check rates**"}}]}
    try:
        llm._extract_text(resp)
        assert False, "should have raised"
    except RuntimeError as e:
        assert "chain-of-thought" in str(e)


def test_extract_accepts_clean_prose():
    resp = {"choices": [{"message": {"content": "The estimate of HK$12,294,998 looks plausible; fix the tiling rate first."}}]}
    assert llm._extract_text(resp).startswith("The estimate")


def test_extract_falls_back_to_reasoning_field():
    resp = {"choices": [{"message": {"content": None, "reasoning": "Tidy summary of the screening."}}]}
    assert llm._extract_text(resp) == "Tidy summary of the screening."


def test_extract_handles_no_choices():
    try:
        llm._extract_text({"error": "nope"})
        assert False, "should have raised"
    except RuntimeError as e:
        assert "no choices" in str(e)


def test_fallback_review_never_returns_none():
    """The rule-based fallback is the last line of defence: it must always produce text."""
    txt = llm.fallback_review([{"severity": "critical", "description": "Odd rate", "detail": "HK$2,850 vs HK$780"}], 12345.0)
    assert isinstance(txt, str) and "HK$12,345" in txt
    txt2 = llm.fallback_review([], 999.0)
    assert isinstance(txt2, str) and "HK$999" in txt2
