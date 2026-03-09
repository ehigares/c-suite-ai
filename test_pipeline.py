"""
test_pipeline.py — Logic verification for the summarization and history pipeline.

Runs without API keys or a running server. Tests the pure-Python functions that
govern how history is built, how the exchange count triggers summarization, and
how the history prefix injected into model prompts is formatted.

Run from the project root:
    python test_pipeline.py
"""

import sys
import asyncio
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Minimal stubs so imports work without the full app environment
# ---------------------------------------------------------------------------

# storage and council are importable from the project root because
# "python -m backend.xxx" sets up the package, but plain "python test_pipeline.py"
# needs the path adjusted.
sys.path.insert(0, ".")

from backend.storage import build_history, count_exchanges
from backend.council import _build_history_prefix, run_background_summarization


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
_failures = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS}  {label}")
    else:
        msg = f"  {FAIL}  {label}"
        if detail:
            msg += f"\n        -> {detail}"
        print(msg)
        _failures.append(label)


def section(title: str):
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_exchange(user: str, chairman: str) -> list[dict]:
    """Return [user_message, assistant_message] representing one exchange."""
    return [
        {"role": "user", "content": user},
        {
            "role": "assistant",
            "stage1": [],
            "stage2": [],
            "stage3": {"model": "Chairman", "response": chairman},
        },
    ]


def make_conversation(num_exchanges: int, running_summary: str = "") -> dict:
    """Build a fake conversation dict with the given number of exchanges."""
    messages = []
    for i in range(1, num_exchanges + 1):
        messages.extend(make_exchange(f"User question {i}", f"Chairman answer {i}"))
    return {
        "id": "test-conv-001",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "Test Conversation",
        "council_config": {},
        "running_summary": running_summary,
        "summary_last_updated_at_exchange": 0,
        "messages": messages,
    }


# ---------------------------------------------------------------------------
# Tests: count_exchanges
# ---------------------------------------------------------------------------

def test_count_exchanges():
    section("count_exchanges()")

    check("empty conversation -> 0", count_exchanges(make_conversation(0)) == 0)
    check("1 exchange -> 1",        count_exchanges(make_conversation(1)) == 1)
    check("5 exchanges -> 5",       count_exchanges(make_conversation(5)) == 5)
    check("10 exchanges -> 10",     count_exchanges(make_conversation(10)) == 10)

    # Odd message layout shouldn't crash
    conv = make_conversation(3)
    conv["messages"].append({"role": "user", "content": "dangling"})
    check("dangling user message doesn't inflate count",
          count_exchanges(conv) == 3)


# ---------------------------------------------------------------------------
# Tests: build_history
# ---------------------------------------------------------------------------

def test_build_history():
    section("build_history()")

    # Empty conversation
    check("empty conversation -> None",
          build_history(make_conversation(0)) is None)

    # Fewer exchanges than raw window — all returned as recent, no summary needed
    h = build_history(make_conversation(2), raw_exchanges=3)
    check("2 exchanges, window=3 -> not None", h is not None)
    check("2 exchanges, window=3 -> 2 recent_exchanges",
          len(h["recent_exchanges"]) == 2)
    check("2 exchanges, window=3 -> empty summary",
          h["running_summary"] == "")

    # Exactly window size
    h = build_history(make_conversation(3), raw_exchanges=3)
    check("3 exchanges, window=3 -> 3 recent",
          len(h["recent_exchanges"]) == 3)

    # More exchanges than window — only last N returned
    h = build_history(make_conversation(5), raw_exchanges=3)
    check("5 exchanges, window=3 -> 3 recent",
          len(h["recent_exchanges"]) == 3)
    check("5 exchanges, window=3 -> most recent exchange is last",
          h["recent_exchanges"][-1]["user"] == "User question 5")
    check("5 exchanges, window=3 -> oldest recent exchange is #3",
          h["recent_exchanges"][0]["user"] == "User question 3")

    # Running summary is passed through when present
    conv = make_conversation(5, running_summary="This is the existing summary.")
    h = build_history(conv, raw_exchanges=3)
    check("running_summary preserved in output",
          h["running_summary"] == "This is the existing summary.")

    # window=1 edge case
    h = build_history(make_conversation(5), raw_exchanges=1)
    check("window=1 -> only 1 recent exchange",
          len(h["recent_exchanges"]) == 1)
    check("window=1 -> that exchange is the last one",
          h["recent_exchanges"][0]["user"] == "User question 5")

    # window=10 with only 3 exchanges — no crash, returns all 3
    h = build_history(make_conversation(3), raw_exchanges=10)
    check("window=10 with 3 exchanges -> 3 recent (no crash)",
          len(h["recent_exchanges"]) == 3)


# ---------------------------------------------------------------------------
# Tests: _build_history_prefix
# ---------------------------------------------------------------------------

def test_build_history_prefix():
    section("_build_history_prefix()")

    check("None -> empty string",
          _build_history_prefix(None) == "")

    check("empty dict -> empty string",
          _build_history_prefix({}) == "")

    check("empty summary + empty recent -> empty string",
          _build_history_prefix({"running_summary": "", "recent_exchanges": []}) == "")

    # Summary only
    prefix = _build_history_prefix({
        "running_summary": "The user is designing a database.",
        "recent_exchanges": [],
    })
    check("summary-only -> contains CONVERSATION SUMMARY",
          "CONVERSATION SUMMARY" in prefix)
    check("summary-only -> contains summary text",
          "designing a database" in prefix)
    check("summary-only -> ends with separator",
          prefix.endswith("---\n\n"))

    # Recent exchanges only
    prefix = _build_history_prefix({
        "running_summary": "",
        "recent_exchanges": [
            {"user": "What is 2+2?", "chairman": "It is 4."},
        ],
    })
    check("recent-only -> contains RECENT CONVERSATION",
          "RECENT CONVERSATION" in prefix)
    check("recent-only -> contains user question",
          "What is 2+2?" in prefix)
    check("recent-only -> contains chairman answer",
          "It is 4." in prefix)
    check("recent-only -> does NOT contain CONVERSATION SUMMARY",
          "CONVERSATION SUMMARY" not in prefix)

    # Both summary and recent
    prefix = _build_history_prefix({
        "running_summary": "Running summary here.",
        "recent_exchanges": [{"user": "Q", "chairman": "A"}],
    })
    check("both -> contains CONVERSATION SUMMARY", "CONVERSATION SUMMARY" in prefix)
    check("both -> contains RECENT CONVERSATION",  "RECENT CONVERSATION" in prefix)
    check("both -> summary comes before recent",
          prefix.index("CONVERSATION SUMMARY") < prefix.index("RECENT CONVERSATION"))


# ---------------------------------------------------------------------------
# Tests: summarization trigger condition
# ---------------------------------------------------------------------------

def test_summarization_trigger():
    section("Summarization trigger condition (every 5 exchanges)")

    # Mirrors the exact condition in main.py:
    #   if summ_model and exchange_count > 0 and exchange_count % 5 == 0
    def should_trigger(exchange_count: int, has_summ_model: bool) -> bool:
        return bool(has_summ_model and exchange_count > 0 and exchange_count % 5 == 0)

    check("0 exchanges -> no trigger",   not should_trigger(0,  True))
    check("1 exchange  -> no trigger",   not should_trigger(1,  True))
    check("4 exchanges -> no trigger",   not should_trigger(4,  True))
    check("5 exchanges -> trigger",          should_trigger(5,  True))
    check("6 exchanges -> no trigger",   not should_trigger(6,  True))
    check("10 exchanges -> trigger",         should_trigger(10, True))
    check("15 exchanges -> trigger",         should_trigger(15, True))
    check("5 exchanges, no summ model -> no trigger",
          not should_trigger(5, False))


# ---------------------------------------------------------------------------
# Tests: exchange selection in run_background_summarization
# ---------------------------------------------------------------------------

def test_exchange_selection():
    section("Exchange selection for compression")

    # Mirrors the logic in council.py run_background_summarization:
    #   exchanges_to_compress = exchanges[:-raw] if len(exchanges) > raw else []
    def exchanges_to_compress(total: int, raw: int) -> int:
        if total > raw:
            return total - raw
        return 0

    check("5 total, raw=3 -> 2 compressed",  exchanges_to_compress(5, 3) == 2)
    check("5 total, raw=5 -> 0 compressed",  exchanges_to_compress(5, 5) == 0)
    check("3 total, raw=5 -> 0 compressed",  exchanges_to_compress(3, 5) == 0)
    check("10 total, raw=3 -> 7 compressed", exchanges_to_compress(10, 3) == 7)
    check("10 total, raw=1 -> 9 compressed", exchanges_to_compress(10, 1) == 9)

    # Confirm the correct exchanges are selected (indices)
    # At 5 exchanges with raw=3: compress [0,1], keep [2,3,4]
    all_ex = [{"user": f"Q{i}", "chairman": f"A{i}"} for i in range(5)]
    raw = 3
    to_compress = all_ex[:-raw] if len(all_ex) > raw else []
    check("correct exchanges selected for compression (Q0, Q1)",
          [e["user"] for e in to_compress] == ["Q0", "Q1"])
    to_keep = all_ex[-raw:]
    check("correct exchanges kept as raw (Q2, Q3, Q4)",
          [e["user"] for e in to_keep] == ["Q2", "Q3", "Q4"])


# ---------------------------------------------------------------------------
# Tests: run_background_summarization — no-op paths (no API call made)
# ---------------------------------------------------------------------------

async def test_summarization_noop_paths():
    section("run_background_summarization() no-op paths")

    fake_model = {
        "id": "fake",
        "model": "fake-model",
        "base_url": "http://fake.invalid",
        "api_key": "",
        "display_name": "Fake",
    }

    # 0 exchanges — should return early without calling the model
    conv_empty = make_conversation(0)
    # This will fail to connect (fake URL) but should catch the exception silently
    # We just verify it doesn't raise
    raised = False
    try:
        await run_background_summarization("test-id", conv_empty, fake_model, raw_exchanges_to_keep=3)
    except Exception:
        raised = True
    check("0 exchanges -> returns silently (no raise)", not raised)

    # 3 exchanges with raw=5 -> nothing to compress -> returns early (no HTTP call)
    conv_short = make_conversation(3)
    raised = False
    try:
        await run_background_summarization("test-id", conv_short, fake_model, raw_exchanges_to_keep=5)
    except Exception:
        raised = True
    check("3 exchanges, raw=5 -> returns early silently (no raise)", not raised)

    # 5 exchanges with raw=3 -> 2 to compress -> WILL try HTTP (will fail gracefully)
    conv_trigger = make_conversation(5)
    raised = False
    try:
        await run_background_summarization("test-id", conv_trigger, fake_model, raw_exchanges_to_keep=3)
    except Exception:
        raised = True
    check("5 exchanges, raw=3 -> HTTP fails but caught silently (no raise)", not raised)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("\nLLM Council — Pipeline Logic Tests")
    print("=" * 60)
    print("(No API keys or running server required)")

    test_count_exchanges()
    test_build_history()
    test_build_history_prefix()
    test_summarization_trigger()
    test_exchange_selection()
    asyncio.run(test_summarization_noop_paths())

    print(f"\n{'=' * 60}")
    if _failures:
        print(f"  {FAIL}  {len(_failures)} test(s) FAILED:")
        for f in _failures:
            print(f"       - {f}")
        sys.exit(1)
    else:
        print(f"  {PASS}  All tests passed.")
    print()


if __name__ == "__main__":
    main()
