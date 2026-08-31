"""The ladder measurement, and the line it must never cross.

Ruling, 2026-08-31: the ladder question gets MEASURED before it gets retuned.
Six MLB prop questions fell below the 70% floor in one night, and a count
cannot tell "the floor working as designed" from "a ladder set where the model
has nothing to say" -- only the distribution of the claims that failed can.

The danger in recording claims that never became predictions is that they look
like more data. They are not: they have no outcome, they were never committed
to in advance, and scoring them would let the model be judged on the questions
it liked. These tests hold that line.
"""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import config, db
from gridiron.model import rungs


def test_the_log_is_never_read_by_anything_that_scores(league):
    """No scoring path may so much as name the table.

    A curve, a Brier score or an N built from claims the model was never held
    to is backfitting with extra steps -- and it would arrive looking like a
    larger sample, which is the most persuasive form the mistake can take.
    """
    import ast
    from pathlib import Path

    root = Path(db.__file__).resolve().parent
    scorers = ["calibration.py", "resolve.py", "views.py"]
    offenders = []
    for name in scorers:
        text = (root / name).read_text(encoding="utf-8")
        # The docstring exemption the other law scans use: prose may explain
        # the rule, code may not reach the table.
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "prop_rung_claims" in node.value:
                    offenders.append(f"{name}: {node.value[:60]}")
    assert not offenders, (
        "a scoring module reaches the rung log; these are claims with no "
        f"outcome and must never enter the record: {offenders}"
    )


def test_a_recorded_claim_cannot_be_rewritten(league):
    """LAW 3 applies here too: what the model said is what it said."""
    league.execute(
        "INSERT INTO prop_rung_claims (sport, season, week, game_id, subject,"
        " market, rung, chosen_rung, rolling_mean, prob_yes, claimed, side,"
        " asked, written, floor_applied, factor_set_version, created_utc)"
        " VALUES ('mlb',2026,157,'g1','Someone batter_hits','batter_hits',"
        " 0.5,0.5,1.2,0.8,0.8,'over',1,0,0.7,'fs2','2026-08-31T00:00:00Z')"
    )
    league.commit()
    with pytest.raises(sqlite3.IntegrityError):
        league.execute("UPDATE prop_rung_claims SET claimed = 0.99")


def test_a_claim_outside_a_probability_is_refused(league):
    """The boundary, tested AT the boundary (MENTOR 3).

    `claimed` is confidence in the side STATED, so it can never be below 0.5 --
    `stated_side` guarantees it. 0.5 exactly is legal and 0.499 is not.
    """
    def insert(claimed):
        league.execute(
            "INSERT INTO prop_rung_claims (sport, season, week, game_id,"
            " subject, market, rung, chosen_rung, rolling_mean, prob_yes,"
            " claimed, side, asked, written, floor_applied,"
            " factor_set_version, created_utc)"
            " VALUES ('mlb',2026,157,'g2','Someone batter_hits','batter_hits',"
            f" 0.5,0.5,1.2,0.5,{claimed},'over',1,0,0.7,'fs2',"
            f" '2026-08-31T00:00:{int(claimed * 100) % 60:02d}Z')"
        )

    insert(0.5)
    league.commit()
    with pytest.raises(sqlite3.IntegrityError):
        insert(0.499)


def test_only_a_declared_ladder_is_logged():
    """No ladder, no rungs -- rather than a ladder invented to have one."""
    assert rungs.declared_rungs("mlb", "batter_hits") == config.MLB_PROP_LADDER["batter_hits"]
    assert rungs.declared_rungs("nfl", "passing_yards") == ()
    assert rungs.declared_rungs("nba", "nba_points") == ()


def test_the_distribution_refuses_to_conclude_early(league):
    """Two weeks, by ruling. One day of data must not read as an answer."""
    league.execute(
        "INSERT INTO prop_rung_claims (sport, season, week, game_id, subject,"
        " market, rung, chosen_rung, rolling_mean, prob_yes, claimed, side,"
        " asked, written, floor_applied, factor_set_version, created_utc)"
        " VALUES ('mlb',2026,157,'g3','Someone batter_hits','batter_hits',"
        " 0.5,0.5,1.2,0.62,0.62,'over',1,0,0.7,'fs2','2026-08-31T00:00:00Z')"
    )
    league.commit()
    d = rungs.distribution(league, sport="mlb")
    assert d["days"] < rungs.DECIDE_AFTER_DAYS
    assert "not enough to decide" in d["verdict"]
    assert d["below_floor"] == 1
    assert d["below_floor_nearly"] == 1
