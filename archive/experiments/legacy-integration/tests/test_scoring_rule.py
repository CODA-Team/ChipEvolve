"""The scoring rule must not be gameable - every case here is a cold-audit repro.

A qualification scorer that accepts a hedged or coincidental answer inflates every
phase above it: an audit found six ways to pass with a wrong answer, and these tests
are those six, plus the legitimate forms that must keep passing (a tightened rule that
rejects honest answers is just a different way to be wrong).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


scoring = _load("qualification_scoring", "qualification/runners/scoring.py")
comparison = _load("qualification_raw_vs_interface", "qualification/v2/raw_vs_interface.py")


@pytest.mark.parametrize("label, gold, answer", [
    # C1: an answer that mentions the gold while choosing another value
    ("mentions the gold, commits to another", 28, "ANSWER: 27 (the report also shows 28)"),
    ("approximation plus an alternative", 28, "ANSWER: approximately 28 maybe 27"),
    # C2: an identifier's digits must not satisfy a numeric gold
    ("identifier digits", 2638, "ANSWER: place2638"),
    # C3: a stated unit decides, so the wrong unit cannot ride on the digits
    ("wrong unit", 9.2e-11, "ANSWER: 9.2e-11 ps"),
])
def test_a_wrong_answer_does_not_pass(label: str, gold, answer: str) -> None:
    passed, note, _hedge = scoring.verdict(gold, answer, 0.0)
    assert not passed, f"{label} passed: {note}"


@pytest.mark.parametrize("label, gold, answer, unit", [
    ("plain number", 28, "ANSWER: 28", None),
    ("seconds", -4.544e-11, "ANSWER: -4.544e-11 s", None),
    ("picoseconds converted", -4.544e-11, "ANSWER: -45.44 ps", None),
    ("nanoseconds converted", 1.492e-09, "ANSWER: 1.492 ns", None),
    ("a decomposition is not a hedge", 19283, "ANSWER: 19283 nets (19281 signal + 2 special)", None),
    ("a quantity beside a time value", 28, "ANSWER: 28 (slack -1.586e-11 s)", None),
    ("the gold's own unit", -0.04544, "ANSWER: -0.04544 ns", "ns"),
    ("an identifier elsewhere is fine", -4.544e-11, "ANSWER: -4.544e-11 (path:0)", None),
])
def test_a_right_answer_still_passes(label: str, gold, answer: str, unit) -> None:
    passed, note, _hedge = scoring.verdict(gold, answer, 0.0, unit)
    assert passed, f"{label} was rejected: {note}"


def test_the_comparison_arm_uses_the_shared_rule() -> None:
    """The raw-vs-interface arm once graded lists more leniently than phase 5/6."""
    extra = comparison.score_case({"gold": ["metal1", "metal2", "metal3"]},
                                  "ANSWER: metal1 metal2 metal3 metal4", scoring)
    assert extra[0] is False, "a list with an extra element passed"
    hedged = comparison.score_case({"gold": ["metal1", "metal2", "metal3"]},
                                   "ANSWER: metal1 metal2 or metal3", scoring)
    assert hedged[0] is False, "a list offering alternatives passed"
    correct = comparison.score_case({"gold": ["metal1", "metal2", "metal3"]},
                                    "ANSWER: metal1, metal2, metal3", scoring)
    assert correct[0] is True
    # an approximation of one correct set is not a choice
    approximate = comparison.score_case({"gold": [103740, 274400]},
                                        "ANSWER: 103740 and 274400 (approximately)", scoring)
    assert approximate[0] is True


def test_a_file_path_is_not_the_named_object() -> None:
    """`first-name` read "timing/final.rpt" as the answer and failed a correct reply."""
    case = {"mode": "first-name", "gold": "u/Z"}
    passed, note = comparison.score_case(case, "ANSWER: from timing/final.rpt the pin is u/Z",
                                         scoring)
    assert passed, note
    wrong, _ = comparison.score_case(case, "ANSWER: place2796/Z", scoring)
    assert wrong is False


def test_a_case_without_gold_cannot_pass_for_free() -> None:
    case = {"mode": "first-name", "gold": None}
    assert comparison.score_case(case, "ANSWER: unknown", scoring)[0] is False


def test_the_structural_gold_refuses_a_def_it_cannot_account_for(tmp_path: Path) -> None:
    """A sloppy DEF used to yield a two-net gold and the exam scored against it."""
    original = comparison.DEF.read_text(errors="replace")
    for label, text in (("missing END NETS", original.replace("END NETS", "END NETX", 1)),
                        ("header without the space", original.replace("NETS 19281 ;",
                                                                     "NETS 19281;", 1)),
                        ("duplicate header", original.replace("NETS 19281 ;",
                                                              "NETS 19281 ;\nNETS 19281 ;", 1))):
        path = tmp_path / "doctored.def"
        path.write_text(text, encoding="utf-8")
        saved = comparison.DEF
        comparison.DEF = path
        try:
            with pytest.raises(SystemExit):
                comparison.structural_gold()
        finally:
            comparison.DEF = saved
