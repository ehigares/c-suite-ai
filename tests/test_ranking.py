"""
test_ranking.py — Tests for ranking parse logic.

Tests parse_ranking_from_text() with well-formed, malformed, and empty inputs.

Run from the project root:
    python -m tests.test_ranking
"""

import sys
sys.path.insert(0, ".")

from backend.council import parse_ranking_from_text


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
# Tests: well-formed input
# ---------------------------------------------------------------------------

def test_well_formed():
    section("parse_ranking_from_text() — well-formed input")

    # Standard format
    text = """Response A is great because...
Response B has issues with...

FINAL RANKING:
1. Response A
2. Response C
3. Response B
"""
    parsed, fallback = parse_ranking_from_text(text)
    check("standard format -> 3 results", len(parsed) == 3)
    check("standard format -> correct order",
          parsed == ["Response A", "Response C", "Response B"])
    check("standard format -> no fallback", fallback is False)

    # Two models only
    text2 = """Analysis here...

FINAL RANKING:
1. Response B
2. Response A
"""
    parsed2, fallback2 = parse_ranking_from_text(text2)
    check("two models -> 2 results", len(parsed2) == 2)
    check("two models -> correct order", parsed2 == ["Response B", "Response A"])
    check("two models -> no fallback", fallback2 is False)

    # Extra whitespace around numbered items
    text3 = """FINAL RANKING:
  1.  Response C
  2.  Response A
  3.  Response B
"""
    parsed3, fallback3 = parse_ranking_from_text(text3)
    check("extra whitespace -> still parses", len(parsed3) == 3)
    check("extra whitespace -> no fallback", fallback3 is False)


# ---------------------------------------------------------------------------
# Tests: malformed input
# ---------------------------------------------------------------------------

def test_malformed():
    section("parse_ranking_from_text() — malformed input")

    # FINAL RANKING section exists but no numbered list — just labels
    text = """My analysis...

FINAL RANKING:
Response C is the best, followed by Response A, then Response B.
"""
    parsed, fallback = parse_ranking_from_text(text)
    check("unnumbered ranking -> extracts labels", len(parsed) >= 2)
    check("unnumbered ranking -> fallback used", fallback is True)

    # No FINAL RANKING section at all — mentions responses throughout
    text2 = """Response A provides a thorough analysis. Response B is decent.
I think Response A is better than Response B overall.
Response C is somewhere in between.
"""
    parsed2, fallback2 = parse_ranking_from_text(text2)
    check("no FINAL RANKING section -> extracts from full text", len(parsed2) >= 2)
    check("no FINAL RANKING section -> fallback used", fallback2 is True)

    # FINAL RANKING with extra text after labels
    text3 = """FINAL RANKING:
1. Response B (best overall quality)
2. Response A (good but verbose)
3. Response C (needs improvement)
"""
    parsed3, fallback3 = parse_ranking_from_text(text3)
    check("labels with extra text -> still extracts", len(parsed3) == 3)
    check("labels with extra text -> correct order",
          parsed3 == ["Response B", "Response A", "Response C"])
    check("labels with extra text -> no fallback", fallback3 is False)


# ---------------------------------------------------------------------------
# Tests: empty / edge cases
# ---------------------------------------------------------------------------

def test_empty():
    section("parse_ranking_from_text() — empty and edge cases")

    # Empty string
    parsed, fallback = parse_ranking_from_text("")
    check("empty string -> empty list", parsed == [])
    check("empty string -> fallback flag", fallback is True)

    # No response labels at all
    parsed2, fallback2 = parse_ranking_from_text("This is just a random thought with no rankings.")
    check("no labels at all -> empty list", parsed2 == [])
    check("no labels -> fallback flag", fallback2 is True)

    # FINAL RANKING section but empty
    parsed3, fallback3 = parse_ranking_from_text("Some analysis.\n\nFINAL RANKING:\n\n")
    check("empty FINAL RANKING -> empty list", parsed3 == [])
    check("empty FINAL RANKING -> fallback", fallback3 is True)

    # Single response only
    parsed4, fallback4 = parse_ranking_from_text("FINAL RANKING:\n1. Response A\n")
    check("single response -> 1 result", len(parsed4) == 1)
    check("single response -> correct label", parsed4[0] == "Response A")
    check("single response -> no fallback", fallback4 is False)

    # Duplicate labels in text (outside FINAL RANKING)
    text = "Response A is mentioned many times. Response A again. Response B too."
    parsed5, fallback5 = parse_ranking_from_text(text)
    check("duplicate labels -> all extracted", len(parsed5) >= 3)
    check("duplicate labels -> fallback used", fallback5 is True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("\nLLM Council — Ranking Parse Tests")
    print("=" * 60)
    print("(No API keys or running server required)")

    test_well_formed()
    test_malformed()
    test_empty()

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
