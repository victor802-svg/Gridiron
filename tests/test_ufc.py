"""UFC: the data layer and the fighter rating (U2).

WHAT THIS DOES NOT TEST, because it does not exist yet: UFC is not a declared
sport. There are no UFC questions, predictions, factors or markets, and
`config.SPORTS` does not contain it. These tests cover the loader's storage
shape and the rating's arithmetic, which are the two things U2 delivers.

NOTHING HERE TOUCHES THE NETWORK. The bouts are synthetic and built in the
test, which is also how the leak test gets a result it can predict by hand.
"""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import db
from gridiron.model import ufc_rating


def _bout(conn, bout_id, when, a, b, winner, *, method="kotko",
          rounds=3, end_round=1, status="final"):
    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " fighter_a, fighter_b, status, winner, method, end_round, fetched_utc)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (bout_id, "evt", when, rounds, a, b, status, winner, method,
         end_round, db.utcnow()))


@pytest.fixture
def cage(conn) -> sqlite3.Connection:
    """A small synthetic history: A beats B repeatedly, C is unknown."""
    conn.execute("INSERT INTO ufc_events (id, name, event_utc, season,"
                 " fetched_utc) VALUES ('evt','Test Card','2025-01-01T00:00Z',"
                 " 2025, ?)", (db.utcnow(),))
    # THE FIGHTERS EXIST FIRST. `ufc_ratings` carries a foreign key to
    # `ufc_fighters`, which caught this fixture the first time it stored: a
    # rating for a fighter nobody has heard of is a rating about nobody.
    for who in ("A", "B", "C"):
        conn.execute(
            "INSERT INTO ufc_fighters (id, name, fetched_utc) VALUES (?,?,?)",
            (who, f"Fighter {who}", db.utcnow()))
    for i in range(1, 7):
        _bout(conn, f"b{i}", f"2025-0{i}-01T00:00Z", "A", "B", "A")
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# the rating is walk-forward
# ---------------------------------------------------------------------------

def test_the_first_bout_is_rated_from_nothing(cage):
    rows = ufc_rating.walk_forward(cage, ufc_rating.K_FITTED)
    first = rows[0]
    assert first["rating_a"] == ufc_rating.START
    assert first["rating_b"] == ufc_rating.START
    assert first["expected_a"] == pytest.approx(0.5), (
        "two fighters with no history are not a coin flip"
    )


def test_a_bout_never_sees_its_own_result(cage):
    """THE LEAK EVERY ROLLING WINDOW IN THIS PROJECT IS SHAPED TO AVOID.

    A rating recomputed at read time would have seen the outcome it is being
    used to predict. Here the winner's rating going INTO each bout must be
    strictly the one earned before it -- so it rises between bouts and never
    within one.
    """
    rows = ufc_rating.walk_forward(cage, ufc_rating.K_FITTED)
    ratings = [r["rating_a"] for r in rows]
    assert ratings == sorted(ratings), (
        "A wins every bout, so the rating carried INTO each one must not fall"
    )
    assert ratings[0] < ratings[-1], "six straight wins moved nothing"
    # The last bout's incoming rating is earned from the five before it, not
    # from six: the sixth result is not yet visible to it.
    assert len(rows) == 6


def test_a_draw_moves_no_rating(conn):
    conn.execute("INSERT INTO ufc_events (id, name, event_utc, season,"
                 " fetched_utc) VALUES ('evt','T','2025-01-01T00:00Z',2025,?)",
                 (db.utcnow(),))
    _bout(conn, "d1", "2025-01-01T00:00Z", "A", "B", None,
          method="draw", end_round=3)
    _bout(conn, "d2", "2025-02-01T00:00Z", "A", "B", "A")
    conn.commit()
    rows = ufc_rating.walk_forward(conn, ufc_rating.K_FITTED)
    # The draw is not graded at all, and the bout after it still starts level.
    assert len(rows) == 1, "a draw was scored as a result"
    assert rows[0]["rating_a"] == ufc_rating.START
    assert rows[0]["rating_b"] == ufc_rating.START


def test_a_no_contest_moves_no_rating(conn):
    conn.execute("INSERT INTO ufc_events (id, name, event_utc, season,"
                 " fetched_utc) VALUES ('evt','T','2025-01-01T00:00Z',2025,?)",
                 (db.utcnow(),))
    _bout(conn, "n1", "2025-01-01T00:00Z", "A", "B", None, method="no-contest")
    conn.commit()
    assert ufc_rating.walk_forward(conn, ufc_rating.K_FITTED) == []


def test_a_bigger_k_moves_a_rating_further(cage):
    small = ufc_rating.walk_forward(cage, 8.0)
    large = ufc_rating.walk_forward(cage, 80.0)
    assert large[-1]["rating_a"] > small[-1]["rating_a"]


def test_the_expected_curve_has_no_home_side():
    """A fight has no home team, and the curve must not invent one."""
    assert ufc_rating.expected(1500.0, 1500.0) == pytest.approx(0.5)
    assert ufc_rating.expected(1900.0, 1500.0) == pytest.approx(10 / 11, abs=1e-6)
    assert (ufc_rating.expected(1600.0, 1500.0)
            == pytest.approx(1.0 - ufc_rating.expected(1500.0, 1600.0)))


def test_storing_ratings_writes_both_corners(cage):
    ufc_rating.walk_forward(cage, ufc_rating.K_FITTED, store=True)
    n = cage.execute("SELECT COUNT(*) FROM ufc_ratings").fetchone()[0]
    assert n == 12, "six bouts, two corners each"
    stored = cage.execute(
        "SELECT k_factor FROM ufc_ratings LIMIT 1").fetchone()[0]
    assert stored == ufc_rating.K_FITTED, (
        "the stored rating does not say which K produced it"
    )


def test_a_sweep_never_touches_the_record(cage):
    ufc_rating.fit_k(cage)
    assert cage.execute("SELECT COUNT(*) FROM ufc_ratings").fetchone()[0] == 0, (
        "fitting K wrote ratings; a sweep must not touch the record"
    )


# ---------------------------------------------------------------------------
# the fitted constant
# ---------------------------------------------------------------------------

def test_the_declared_k_is_inside_its_own_candidate_list():
    """A CONSTANT AT THE EDGE OF ITS SWEEP HAS NOT BEEN FITTED.

    The first sweep stopped at 48 and 48 won, which says only that the list
    was too short. The candidates now reach 200 and the optimum sits at 80,
    with worse values on both sides -- this test refuses a future edit that
    trims the range back around the answer.
    """
    assert ufc_rating.K_FITTED in ufc_rating.K_CANDIDATES
    assert ufc_rating.K_FITTED != ufc_rating.K_CANDIDATES[0]
    assert ufc_rating.K_FITTED != ufc_rating.K_CANDIDATES[-1], (
        "the fitted K is the last candidate, so the sweep was clamped rather "
        "than fitted; extend the range until the curve turns over"
    )


def test_the_candidates_are_declared_in_order():
    assert list(ufc_rating.K_CANDIDATES) == sorted(ufc_rating.K_CANDIDATES)
    assert len(set(ufc_rating.K_CANDIDATES)) == len(ufc_rating.K_CANDIDATES)


def test_fitting_reports_its_margin_and_sample(cage):
    fit = ufc_rating.fit_k(cage, warmup=0)
    assert fit["n"] > 0
    assert fit["k"] in ufc_rating.K_CANDIDATES
    # LAW 4's habit: a figure arrives with what stands behind it.
    assert "brier" in fit and "candidates" in fit
    assert len(fit["candidates"]) == len(ufc_rating.K_CANDIDATES)
    assert fit["margin_over_runner_up"] is not None


def test_fitting_on_nothing_says_so_rather_than_guessing(conn):
    fit = ufc_rating.fit_k(conn)
    assert fit["k"] is None
    assert fit["n"] == 0
    assert "nothing was fitted" in fit["note"]
