"""The gate is visible while it runs, and cannot flatter a partial run.

TWO FAILURES THIS CLOSES, both observed rather than imagined:

  * On 2026-09-01 `verify.py` ran the suite with `capture_output=True`, so for
    twenty-eight minutes there was nothing on screen. A slow suite and a hung
    one look identical through a blank terminal, and that cost a wrong call:
    the run was killed as "stuck" on the evidence of a CPU reading, and it was
    healthy, and had in fact just passed.

  * Earlier the same week the suite was split in two to fit a timeout. Both
    halves passed. The whole suite failed. The split was never declared, so
    nothing in the output said which half had not been run.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _verify():
    spec = importlib.util.spec_from_file_location(
        "gridiron_verify", REPO / "tools" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_skipped_tier_is_never_a_pass():
    """THE POINT OF THE WHOLE PHASE.

    Every step that ran passed. A tier did not run. That is not a pass, and
    the exit code has to say so -- a green summary is carried into a commit
    message that outlives the memory of which tier produced it.
    """
    verify = _verify()
    code, lines = verify.summarise(
        {"1. test suite": True, "2. planted violations": True}, ["browser"])
    assert code != 0, "a skipped tier was reported as a pass"
    assert any("INCOMPLETE" in line for line in lines)


def test_the_skipped_tier_is_named_not_merely_counted():
    """"a tier was skipped" tells you to worry; naming it tells you what."""
    verify = _verify()
    _, lines = verify.summarise({"2. planted violations": True}, ["browser"])
    joined = "\n".join(lines)
    assert "browser" in joined
    assert verify.TIERS["browser"] in joined


def test_every_way_of_skipping_has_a_name():
    """A tier the summary cannot name would print as an empty accusation."""
    verify = _verify()
    for tier in ("browser", "slow", "tests", "end to end"):
        assert tier in verify.TIERS, f"{tier} can be skipped but has no description"
        assert verify.TIERS[tier].strip()


def test_a_full_run_that_passes_is_a_pass():
    """The guard must not be so eager that it fails a clean run."""
    verify = _verify()
    code, lines = verify.summarise(
        {"1. test suite": True, "2. planted violations": True}, [])
    assert code == 0
    assert not any("INCOMPLETE" in line for line in lines)


def test_a_full_run_that_fails_is_still_a_failure():
    verify = _verify()
    code, _ = verify.summarise(
        {"1. test suite": False, "2. planted violations": True}, [])
    assert code != 0


def test_the_suite_is_not_run_with_its_output_captured():
    """Progress you cannot see is progress you end up guessing about.

    Asserted against the CALL, not the text. The first version of this test
    searched the source for "capture_output" and failed immediately -- on the
    docstring above `step_1_tests`, which explains why capturing was removed.
    A scan that cannot tell code from prose about code is the defect this
    project has met four times in other guards; here it took one run to
    reappear.
    """
    import ast

    tree = ast.parse((REPO / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "step_1_tests")
    for node in ast.walk(step):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            assert keyword.arg != "capture_output", (
                "the test suite's output is captured again, so a slow run and "
                "a hung one will look identical from outside"
            )
