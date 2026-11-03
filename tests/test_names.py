"""Name reconciliation contracts (METHODOLOGY.md §12)."""

from hierarchy.names import canonical


def test_display_names_and_slugs_canonicalize_identically():
    assert canonical("Claude Opus 5.5 (High)") == "claude opus 5.5 (high)"
    assert canonical("anthropic/claude-opus-5.5") == "claude opus 5.5"
    assert canonical("Google/Gemini-3-Pro") == "gemini 3 pro"
    assert canonical("Gemini 3.1 Pro Preview (02/26)") == "gemini 3.1 pro preview"
    assert canonical("Gemini 3 Pro (11/25)") == "gemini 3 pro"
    assert canonical("  GPT-5.1 ") == "gpt 5.1"


def test_variants_are_not_silently_merged():
    # "(high)" is a real model variant on Arena: it must NOT collapse into the
    # base model — no fuzzy matching on purpose (§12).
    assert canonical("Claude Opus 5.5 (High)") != canonical("Claude Opus 5.5")


def test_separators_and_case_are_normalized():
    assert canonical("deepseek_v3.2-FLASH") == "deepseek v3.2 flash"
    assert canonical("Qwen3-Max") == canonical("qwen3 max")
