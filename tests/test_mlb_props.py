"""MLB player props: the ladder, the sides, the identity bridge, the voids.

Every test here corresponds to an item on `docs/NEW_MARKET_CHECKLIST.md`, and
the ones that look paranoid are the ones a real defect paid for.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import config, db, language
from gridiron.data import mlb_repo
from gridiron.factors import registry
from gridiron.market import crosswalk, props
from gridiron.model import baseline, questions


@pytest.fixture()
def conn(tmp_path):
    connection = db.open_db(tmp_path / "props.db")
    yield connection
    connection.close()


# --- item 1: the question instruments --------------------------------------

def test_the_ladder_rung_is_the_one_nearest_our_own_mean():
    assert questions.ladder_rung(0.4, "batter_hits") == 0.5
    assert questions.ladder_rung(1.4, "batter_hits") == 1.5
    assert questions.ladder_rung(7.0, "pitcher_strikeouts") == 6.5
    assert questions.ladder_rung(2.0, "pitcher_strikeouts") == 3.5


def test_a_tie_goes_to_the_lower_rung_and_says_so():
    """Exactly between two rungs. Declared rather than left to `min`."""
    assert questions.ladder_rung(1.0, "batter_hits") == 0.5
    assert questions.ladder_rung(5.0, "pitcher_strikeouts") == 4.5


def test_a_rung_off_the_ladder_is_refused_by_name():
    with pytest.raises(questions.RungOffLadder) as exc:
        questions.assert_on_ladder(2.5, "batter_hits")
    assert "declared ladder" in str(exc.value)


def test_the_ladder_is_reachable_without_any_market_module():
    """The rung is chosen blind. Nothing in `questions` may import the market
    package, and the LAW 1 closure scan covers that -- this asserts the weaker,
    plainer thing: the ladder is a constant, not a fetch."""
    assert isinstance(config.MLB_PROP_LADDER, dict)
    assert config.MLB_PROP_LADDER["batter_hits"] == (0.5, 1.5)


# --- R2: the derived side ---------------------------------------------------

ANCHOR = [{"line": 2.0, "price": 118, "prob": 0.459}]
PAIR = [
    {"line": 1.5, "price": -150, "prob": 0.600},
    {"line": 1.5, "price": 120, "prob": 0.455},
]


def test_the_milestone_anchor_names_the_over():
    quotes = props.derive_sides(
        "batter_total_bases", {"totals": list(PAIR), "milestones": ANCHOR}
    )
    over = next(q for q in quotes if q["side"] == "over")
    under = next(q for q in quotes if q["side"] == "under")
    assert over["price"] == 120
    assert under["price"] == -150
    assert over["method"] == "milestone_anchor"


def test_reversing_the_pair_cannot_change_which_side_is_the_over():
    """The failure this prevents is the ESPN spread sign in a new market."""
    forward = props.derive_sides(
        "batter_total_bases", {"totals": list(PAIR), "milestones": ANCHOR}
    )
    backward = props.derive_sides(
        "batter_total_bases",
        {"totals": list(reversed(PAIR)), "milestones": ANCHOR},
    )
    assert [q["price"] for q in forward if q["side"] == "over"] == \
           [q["price"] for q in backward if q["side"] == "over"]


def test_the_shorter_price_is_not_assumed_to_be_the_over():
    """-150 is the shorter price here and it is the UNDER. A method that read
    the sign would get this exactly backwards."""
    quotes = props.derive_sides(
        "batter_total_bases", {"totals": list(PAIR), "milestones": ANCHOR}
    )
    over = next(q for q in quotes if q["side"] == "over")
    assert over["price"] > 0


def test_a_pair_with_no_anchor_is_refused_rather_than_guessed():
    quotes = props.derive_sides(
        "batter_total_bases", {"totals": list(PAIR), "milestones": []}
    )
    assert all(q["side"] == "unknown" for q in quotes)
    assert quotes[0]["method"] == "refused_no_milestone_anchor"


def test_two_sides_priced_alike_are_refused():
    quotes = props.derive_sides("pitcher_strikeouts", {
        "totals": [
            {"line": 5.5, "price": -105, "prob": 0.512},
            {"line": 5.5, "price": -102, "prob": 0.505},
        ],
        "milestones": [{"line": 6.0, "price": -104, "prob": 0.510}],
    })
    assert all(q["side"] == "unknown" for q in quotes)
    assert "ambiguous" in quotes[0]["method"]


def test_a_one_sided_milestone_market_needs_no_derivation():
    """Home runs are published only as "1+", which is the over at 0.5."""
    quotes = props.derive_sides("batter_home_runs", {
        "totals": [],
        "milestones": [{"line": 1.0, "price": 563, "prob": 0.1508}],
    })
    assert len(quotes) == 1
    assert quotes[0]["side"] == "over"
    assert quotes[0]["line"] == 0.5
    assert quotes[0]["method"] == "one_sided_milestone"


# --- item 3: the measured crosswalk ----------------------------------------

def test_the_normaliser_folds_accents_and_punctuation_only():
    assert crosswalk.normalise("José Ramírez") == "jose ramirez"
    assert crosswalk.normalise("Michael A. Taylor") == "michael a taylor"
    assert crosswalk.normalise("Jazz Chisholm Jr.") == "jazz chisholm jr"
    # ...and does NOT fold two different people onto one another.
    assert crosswalk.normalise("Will Smith") != crosswalk.normalise("Wil Smith")


def _batter(conn, pid, name, pk=900001):
    conn.execute(
        "INSERT INTO mlb_batter_games (player_id, season, game_date, game_pk,"
        " player_name, hits) VALUES (?,?,?,?,?,1)",
        (pid, 2026, "2026-05-01", pk, name),
    )


def test_two_players_sharing_a_normalised_name_are_ambiguous(conn):
    _batter(conn, 1, "Jose Ramirez", 900001)
    _batter(conn, 2, "José Ramírez", 900002)
    conn.commit()
    index = crosswalk.our_players(conn, "mlb")
    assert len(index["jose ramirez"]) == 2


def test_an_unmatched_name_is_recorded_not_dropped(conn):
    _batter(conn, 1, "Paul Goldschmidt")
    conn.commit()
    crosswalk._write(
        conn, "mlb", "999999", "Nobody Atall", None, None, "nobody atall",
        "refused_unmatched", "no player in the record normalises to this name",
        "2026-08-30T00:00:00Z",
    )
    conn.commit()
    assert crosswalk.lookup(conn, "mlb", "999999") is None
    refusals = crosswalk.refusals(conn, "mlb")
    assert len(refusals) == 1
    assert refusals[0]["reason"]


def test_a_refused_crosswalk_yields_no_line_rather_than_a_wrong_one(conn):
    _batter(conn, 1, "Paul Goldschmidt")
    conn.commit()
    assert props.espn_id_for(conn, "mlb", 1) is None


# --- R4: the confidence floor ----------------------------------------------

def test_the_floor_is_a_dated_constant():
    assert config.PROPS_MIN_CLAIM == 0.70
    assert config.PROPS_MIN_CLAIM_DECLARED.startswith("2026-08-30")


def test_a_sub_fifty_probability_becomes_a_confident_claim_about_the_other_side():
    """A 28% chance of a home run is a 72% claim that there will not be one.

    This is why the bucket set starts at 50 and cannot sensibly go lower: the
    model states a SIDE and its confidence in that side, so a bucket below 50
    could never receive a row.
    """
    side, claimed = baseline.stated_side(0.28, "over", "under")
    assert side == "under"
    assert claimed == pytest.approx(0.72)
    assert claimed >= config.PROPS_MIN_CLAIM


def test_a_middling_probability_is_below_the_floor_on_either_side():
    for prob in (0.45, 0.50, 0.55, 0.69):
        _side, claimed = baseline.stated_side(prob, "over", "under")
        assert claimed < config.PROPS_MIN_CLAIM


# --- the plain-words law on the new markets --------------------------------

def test_a_half_unit_prop_reads_as_a_yes_no_question():
    said = language.phrase({
        "market_type": "prop", "prop_type": "batter_home_runs",
        "subject": "Kyle Schwarber batter_home_runs",
        "model_side": "under", "line_asked": 0.5,
    })
    assert said == "Kyle Schwarber - NO home run"
    assert "0.5" not in said
    assert "batter_home_runs" not in said


def test_the_over_side_of_a_half_unit_prop_also_reads_plainly():
    said = language.phrase({
        "market_type": "prop", "prop_type": "batter_hits",
        "subject": "Paul Goldschmidt batter_hits",
        "model_side": "over", "line_asked": 0.5,
    })
    assert said == "Paul Goldschmidt records a hit"


def test_a_whole_rung_prop_keeps_its_number():
    said = language.phrase({
        "market_type": "prop", "prop_type": "pitcher_strikeouts",
        "subject": "Ranger Suarez pitcher_strikeouts",
        "model_side": "over", "line_asked": 5.5,
    })
    assert said == "Ranger Suarez over 5.5 strikeouts"


def test_no_internal_identifier_survives_into_a_market_label():
    for market in config.SPORT_PROP_MARKETS["mlb"]:
        label = language.market_label({"prop_type": market})
        assert "_" not in label, f"{market} renders as an identifier"


# --- item 7: the void rules -------------------------------------------------

def _game(conn, game_id="mlb_900001", status="final", league_date="2026-05-01"):
    # The schema refuses a scheduled game carrying scores, and a final one with
    # none. Honoured here rather than worked around: a fixture that could not
    # exist in the record is not a fixture worth testing against.
    scores = (4, 2) if status == "final" else (None, None)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, home_score, away_score, league_date)"
        " VALUES (?, 'mlb', 2026, 30, 'REG', ?, 'PHI', 'NYM', ?, ?, ?, ?)",
        (game_id, f"{league_date}T23:00:00Z", status, scores[0], scores[1],
         league_date),
    )


def _prediction(conn, market, subject_id, line, side="over",
                game_id="mlb_900001"):
    payload = {
        "sport": "mlb", "market_type": "prop", "values": {}, "present": [],
        "absent": [], "failed": {}, "notes": [], "sources": {},
        "question": {"player_id": str(subject_id), "stat": market,
                     "claim": f"{subject_id} {market}"},
    }
    cur = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-05-01T00:00:00Z','mlb',?,'prop',?,?,?,?,?,"
        "'statistical','fs2',?,'because')",
        (game_id, market, f"subject {subject_id} {market}", line, 0.75, side,
         json.dumps(payload)),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM predictions WHERE id = ?", (cur.lastrowid,)
    ).fetchone()


def test_a_batter_with_no_line_in_the_game_is_void(conn):
    from gridiron.resolve import Void
    from gridiron.sports import mlb

    _game(conn)
    conn.commit()
    pred = _prediction(conn, "batter_hits", 12345, 0.5)
    with pytest.raises(Void) as exc:
        mlb.resolve_outcome(conn, pred)
    assert "no batting line exists" in str(exc.value)


def test_a_batter_who_played_and_went_hitless_settles_as_a_loss(conn):
    """The asymmetry the void rule exists for: no row means he did not play, a
    row of zeros means he played and did not do the thing."""
    from gridiron.sports import mlb

    _game(conn)
    conn.execute(
        "INSERT INTO mlb_batter_games (player_id, season, game_date, game_pk,"
        " player_name, hits, plate_appearances) VALUES (12345, 2026,"
        " '2026-05-01', 900001, 'Someone', 0, 4)"
    )
    conn.commit()
    pred = _prediction(conn, "batter_hits", 12345, 0.5, side="over")
    assert mlb.resolve_outcome(conn, pred) == 0


def test_a_batter_who_cleared_the_rung_settles_as_a_win(conn):
    from gridiron.sports import mlb

    _game(conn)
    conn.execute(
        "INSERT INTO mlb_batter_games (player_id, season, game_date, game_pk,"
        " player_name, hits, plate_appearances) VALUES (12345, 2026,"
        " '2026-05-01', 900001, 'Someone', 2, 4)"
    )
    conn.commit()
    pred = _prediction(conn, "batter_hits", 12345, 0.5, side="over")
    assert mlb.resolve_outcome(conn, pred) == 1


def test_the_under_side_is_scored_as_the_complement(conn):
    from gridiron.sports import mlb

    _game(conn)
    conn.execute(
        "INSERT INTO mlb_batter_games (player_id, season, game_date, game_pk,"
        " player_name, hits, plate_appearances) VALUES (12345, 2026,"
        " '2026-05-01', 900001, 'Someone', 0, 4)"
    )
    conn.commit()
    pred = _prediction(conn, "batter_hits", 12345, 0.5, side="under")
    assert mlb.resolve_outcome(conn, pred) == 1


def test_an_announced_starter_who_did_not_start_is_void(conn):
    from gridiron.resolve import Void
    from gridiron.sports import mlb

    _game(conn)
    conn.execute(
        "INSERT INTO mlb_pitcher_starts (pitcher_id, season, game_date, game_pk,"
        " is_start, strike_outs) VALUES (777, 2026, '2026-05-01', 900001, 0, 1)"
    )
    conn.commit()
    pred = _prediction(conn, "pitcher_strikeouts", 777, 5.5)
    with pytest.raises(Void) as exc:
        mlb.resolve_outcome(conn, pred)
    assert "did not start" in str(exc.value)


def test_a_game_that_never_finished_is_voided_once_it_is_clearly_not_going_to(conn):
    from gridiron.resolve import Void
    from gridiron.sports import mlb

    _game(conn, status="scheduled", league_date="2020-05-01")
    conn.commit()
    pred = _prediction(conn, "batter_hits", 12345, 0.5)
    with pytest.raises(Void) as exc:
        mlb.resolve_outcome(conn, pred)
    assert "not going to settle" in str(exc.value)


def test_a_game_not_yet_played_is_unresolvable_not_void(conn):
    """A void is terminal. A game that has simply not happened yet must stay
    open, or tonight's slate would be destroyed every time resolve ran."""
    from gridiron.db import utcnow
    from gridiron.resolve import Unresolvable
    from gridiron.sports import mlb

    _game(conn, status="scheduled", league_date=utcnow()[:10])
    conn.commit()
    pred = _prediction(conn, "batter_hits", 12345, 0.5)
    with pytest.raises(Unresolvable):
        mlb.resolve_outcome(conn, pred)


# --- item 6: its own category, its own gate --------------------------------

def test_each_prop_market_gets_its_own_fitted_model():
    keys = {baseline.market_key("mlb", m) for m in config.SPORT_PROP_MARKETS["mlb"]}
    assert keys == {
        "mlb:prop:batter_hits", "mlb:prop:batter_total_bases",
        "mlb:prop:batter_home_runs", "mlb:prop:batter_strikeouts",
        "mlb:prop:pitcher_strikeouts",
    }
    assert baseline.market_key("mlb", "moneyline") == "mlb:moneyline"


def test_the_repo_reads_each_market_from_its_own_column():
    assert mlb_repo.BATTER_STAT_COLUMN["batter_hits"] == "hits"
    assert mlb_repo.BATTER_STAT_COLUMN["batter_total_bases"] == "total_bases"
    assert mlb_repo.BATTER_STAT_COLUMN["batter_home_runs"] == "home_runs"
    assert mlb_repo.BATTER_STAT_COLUMN["batter_strikeouts"] == "strike_outs"
    with pytest.raises(ValueError):
        mlb_repo.batter_rolling(None, 1, "pitcher_strikeouts", "2026-05-01")


# --- the cutoff, which is what the rolling-window leak was about ------------

def test_a_batters_rolling_window_excludes_the_game_being_predicted(conn):
    _game(conn)
    for day, hits in (("2026-04-28", 3), ("2026-04-29", 2), ("2026-05-01", 4)):
        conn.execute(
            "INSERT INTO mlb_batter_games (player_id, season, game_date, game_pk,"
            " player_name, hits, plate_appearances) VALUES (5, 2026, ?, ?,"
            " 'Someone', ?, 4)",
            (day, 900000 + int(day[-2:]), hits),
        )
    conn.commit()
    mean, _sd, n = mlb_repo.batter_rolling(conn, 5, "batter_hits", "2026-05-01")
    assert n == 2, "the game being predicted must not be in its own window"
    assert mean == pytest.approx(2.5)


# --- item 4: plausibility cross-checks between related numbers -------------

def test_the_model_cannot_say_a_higher_rung_is_easier():
    """Every game that clears 6.5 strikeouts clears 5.5. A model that orders
    them the other way is contradicting itself, not merely miscalibrated."""
    from gridiron.sports import mlb

    good = [(3.5, 0.81), (4.5, 0.64), (5.5, 0.42), (6.5, 0.25)]
    mlb.assert_monotone_across_rungs(good, "a well-behaved fit")


def test_a_non_monotone_ladder_is_caught_by_name():
    from gridiron.sports import mlb

    bad = [(3.5, 0.60), (4.5, 0.64), (5.5, 0.42), (6.5, 0.25)]
    with pytest.raises(mlb.NonMonotoneLadder) as exc:
        mlb.assert_monotone_across_rungs(bad, "a planted reversal")
    assert "self-contradiction" in str(exc.value)


def test_monotonicity_follows_from_the_sign_of_one_coefficient():
    """The property is structural, not lucky: holding everything else fixed,
    `mean_vs_line` is the only factor that moves with the rung, and it falls as
    the rung rises. So the ladder is monotone exactly when that coefficient is
    positive -- which is what makes a negative one a defect worth naming rather
    than a coefficient worth shrugging at."""
    from gridiron.model import logistic

    fit = logistic.Fit(
        names=["mlb_prop_mean_vs_line"], coefficients=[2.0], intercept=0.0,
        n=1000, iterations=4, converged=True, l2=2.0,
    )
    from gridiron.model import baseline
    from gridiron.factors.compute import FeatureVector

    probs = []
    for rung in config.MLB_PROP_LADDER["pitcher_strikeouts"]:
        fv = FeatureVector(sport="mlb", market_type="prop")
        fv.values["mlb_prop_mean_vs_line"] = (5.0 - rung) / max(rung, 1.0)
        probs.append((rung, baseline.predict(fit, fv)["prob_yes"]))
    from gridiron.sports import mlb

    mlb.assert_monotone_across_rungs(probs, "a positive coefficient")
    assert probs[0][1] > probs[-1][1]
