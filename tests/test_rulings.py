"""The five rulings on the M1-M4 close-out, held in place by tests.

Each test names the ruling it enforces. A ruling that lives only in a commit
message is a ruling the next session can undo without noticing.
"""

from __future__ import annotations

import pytest

from gridiron import audit, config, horizon
from gridiron.data import mlb_repo
from gridiron.factors import registry
import gridiron.factors.mlb as mlb_factors


# --- RULING 1: keep both rulings, break the dependency instead -------------

def test_the_ladder_was_not_padded_to_manufacture_confidence():
    """Rungs exist because the market quotes them. Adding one to give the model
    somewhere to be confident would be choosing the questions to flatter the
    answer, which is the opposite of what the ladder is for."""
    assert config.MLB_PROP_LADDER == {
        "batter_hits": (0.5, 1.5),
        "batter_total_bases": (1.5,),
        "batter_home_runs": (0.5,),
        "pitcher_strikeouts": (3.5, 4.5, 5.5, 6.5),
    }


def test_the_confidence_floor_was_not_lowered():
    assert config.PROPS_MIN_CLAIM == 0.70


def test_the_rate_factor_uses_a_window_far_longer_than_the_mean():
    """The repair. Measured over the SAME window, rate x plate-appearances
    reconstructed the rolling mean exactly (corr +1.000), so three declared
    factors were two instruments and an identity."""
    assert mlb_repo.BATTER_BASELINE_WINDOW > mlb_repo.BATTER_WINDOW * 2
    assert mlb_repo.BATTER_BASELINE_WINDOW == 60
    assert mlb_repo.BATTER_WINDOW == 15


def test_the_rate_factor_records_why_it_was_redeclared():
    f = registry.REGISTRY["mlb_batter_rate"]
    assert f.active
    assert f.note and "REDECLARED" in f.note
    # A repair is not a discovery, and the note has to say which it is.
    assert "corr(rate x pa, mean) = +1.000" in f.note
    assert "REPAIR OF A BROKEN INSTRUMENT" in f.note


def test_the_baseline_rate_is_a_different_number_from_the_window_mean(tmp_path):
    """Not just a longer window in the docstring -- a different query."""
    from gridiron import db

    conn = db.open_db(tmp_path / "r1.db")
    for i in range(40):
        # First twenty games hitless, last twenty with a hit each: the 15-game
        # mean sees only the recent form, the 60-game baseline sees both.
        conn.execute(
            "INSERT INTO mlb_batter_games (player_id, season, game_date, game_pk,"
            " player_name, hits, plate_appearances) VALUES (7, 2026, ?, ?, 'X', ?, 4)",
            (f"2026-05-{i + 1:02d}", 800000 + i, 0 if i < 20 else 1),
        )
    conn.commit()
    mean, _sd, _n = mlb_repo.batter_rolling(conn, 7, "batter_hits", "2026-06-30")
    baseline, n = mlb_repo.batter_baseline_rate(conn, 7, "batter_hits", "2026-06-30")
    assert mean == pytest.approx(1.0)          # every one of the last 15 had a hit
    assert baseline == pytest.approx(0.5 / 4)  # 20 hits over 40 games x 4 PA
    assert n == 40
    conn.close()


def test_mean_vs_line_is_labelled_inert_where_the_ladder_has_one_rung():
    assert set(mlb_factors.SINGLE_RUNG_MARKETS) == {
        "batter_total_bases", "batter_home_runs",
    }
    note = registry.REGISTRY["mlb_prop_mean_vs_line"].note or ""
    assert "INERT IN SINGLE-RUNG MARKETS" in note
    assert "-0.0534" in note, "the measurement that showed it, not just the claim"


def test_mean_vs_line_stays_declared_in_every_market():
    """Checklist item 1 requires it from the first fit, inert or not. A market
    that gains a rung gains the instrument back with no code change."""
    for market in config.SPORT_PROP_MARKETS["mlb"]:
        names = {f.name for f in registry.active_factors("mlb", "prop", market)}
        assert "mlb_prop_mean_vs_line" in names, market


def test_a_market_that_asked_nothing_says_so_in_words():
    line = horizon.zero_write_line("batter_total_bases", 0, 0.70)
    assert line == (
        "total bases: 0 asked — model never reached 70% at the market's line"
    )
    assert "batter_total_bases" not in line       # plain words
    assert horizon.zero_write_line("batter_hits", 3, 0.70) == ""


# --- RULING 3: the orphan scan ---------------------------------------------

def test_the_ladder_cross_check_has_a_production_caller():
    """It shipped with zero callers anywhere -- not even a test."""
    from pathlib import Path

    cli = Path(audit.__file__).resolve().parent / "cli.py"
    assert "rung_probabilities" in cli.read_text(encoding="utf-8")
    assert "assert_monotone_across_rungs" in cli.read_text(encoding="utf-8")


def test_the_package_has_no_orphan_functions():
    audit.check_no_orphan_functions()


def test_a_decorated_function_is_not_reported_as_an_orphan():
    """The decorator is the call site. A scan that flagged every factor would
    need a 35-line allowlist, and an allowlist that long is a mute button."""
    hits = {h.split(" ")[0] for h in audit.orphan_functions()}
    assert not (hits & set(registry.REGISTRY))


def test_every_orphan_allowlist_entry_is_dated_and_reasoned():
    for name, reason in audit.ORPHAN_ALLOWLIST.items():
        assert reason.startswith("2026-"), f"{name} has no date"
        assert len(reason) > 30, f"{name} has a token reason"


def test_tests_do_not_count_as_callers():
    """A function reached only by its own unit test is exactly the case the
    scan is for, so `tests/` must not silence it."""
    from pathlib import Path

    root = Path(audit.__file__).resolve().parent
    sources = audit._caller_sources(root)
    assert not any("tests" in str(p).split("\\") or "tests" in str(p).split("/")
                   for p in sources)


# --- RULING 4: gates that cannot clear -------------------------------------

def test_an_unreachable_gate_says_so_with_its_arithmetic(tmp_path):
    from gridiron import db

    conn = db.open_db(tmp_path / "r4.db")
    # One slate played, one prediction written, thirty slates left: nowhere
    # near a hundred, and the message has to say so rather than read as progress.
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, home_score, away_score, league_date)"
        " VALUES ('mlb_1','mlb',2026,1,'REG','2026-04-01T23:00:00Z','PHI','NYM',"
        " 'final',4,2,'2026-04-01')"
    )
    for i in range(2, 5):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
            " home, away, status, league_date) VALUES (?,'mlb',2026,?,'REG',?,"
            " 'PHI','NYM','scheduled',?)",
            (f"mlb_{i}", i, f"2026-04-0{i}T23:00:00Z", f"2026-04-0{i}"),
        )
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES ('2026-04-01T00:00:00Z','mlb','mlb_1','prop','batter_hits',"
        " 'X batter_hits',0.5,0.8,'over','statistical','fs2','{}','because',"
        " '2026-04-02T00:00:00Z',1)"
    )
    conn.commit()

    out = horizon.market_outlook(conn, "mlb", "batter_hits", season=2026)
    assert out["reachable"] is False
    assert out["gate"] == 100
    assert "CANNOT CLEAR" in out["message"]
    assert str(out["expected"]) in out["message"], "the arithmetic is shown"
    assert "04-04" in out["message"], "and when the season ends"
    conn.close()


def test_a_market_with_no_rate_yet_does_not_claim_it_cannot_clear(tmp_path):
    """Absent, degraded and declined are three states. 'Nothing written yet' is
    not 'will never get there'."""
    from gridiron import db

    conn = db.open_db(tmp_path / "r4b.db")
    out = horizon.market_outlook(conn, "mlb", "pitcher_strikeouts", season=2026)
    assert out["reachable"] is None
    assert "no rate to project from" in out["message"]
    assert "CANNOT" not in out["message"]
    conn.close()


def test_the_outlook_is_marked_as_an_extrapolation():
    """LAW 4's spirit: a projected number must not read like a measured one."""
    from gridiron import db

    conn = db.open_db(":memory:")
    out = horizon.market_outlook(conn, "mlb", "batter_hits", season=2026)
    assert out["expected_is_an_extrapolation"] is True
    conn.close()


# --- RULING 5: the version convention --------------------------------------

def test_the_factor_set_version_did_not_bump_for_a_zero_record_repair():
    assert config.FACTOR_SET_VERSION == "fs2"
    assert config.FACTOR_SET_HISTORY == ("fs1", "fs2")


def test_the_version_convention_records_the_granularity_mismatch():
    from pathlib import Path

    text = (Path(config.__file__)).read_text(encoding="utf-8")
    assert "ENDORSED BY THE OPERATOR 2026-08-31" in text
    assert "per sport per market" in text


def test_every_compiled_scanner_has_a_known_positive_fixture():
    """A scanner with no fixture is a scanner nobody has proved can see.

    Ruling, 2026-08-31: the fourth instance of a `\b` arriving as a literal
    backspace. It found a FIFTH within a minute -- `SNAKE_CASE`, which enforces
    the plain-words law, had a backspace at both ends and had therefore been
    matching nothing at all. The explicit INTERNAL_TERMS half kept working,
    which is why the pages still looked scanned.

    Adding a compiled pattern to `audit` without a fixture fails here.
    """
    import re
    from pathlib import Path

    from gridiron import audit, config

    source = (Path(config.PACKAGE_ROOT) / "audit.py").read_text(encoding="utf-8")
    declared = set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=\s*__import__\(\"re\"\)\.compile",
                              source, re.M))
    missing = sorted(declared - set(audit.SCANNER_FIXTURES))
    assert not missing, (
        "these scanners have no known-positive fixture, so nothing proves they "
        f"match anything: {missing}"
    )
    assert not audit.scanner_self_check()
