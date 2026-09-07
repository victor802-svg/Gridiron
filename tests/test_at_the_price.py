"""Four shapes of claim (GRIDIRON_AT_THE_PRICE, 2026-09-07).

A claim pairs the model's number for a proposition with the venue's price for
the same one. Until today the writer knew one way to get the model's number --
read a frozen margin distribution at the venue's line -- and refused every
question that could not supply one. The record held no claim at all.

WHAT THIS FILE IS ABOUT, in order of how much damage each would do:

  * the SIDE mapping, because a claim about the opposite side of a question is
    a wrong number that looks exactly like a right one;
  * the KICKOFF guard, because a pre-game probability against an in-play price
    is not a disagreement;
  * the four shapes and their refusals;
  * the sign of the venue's line, which was wrong in a function nobody had
    ever called.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gridiron import db
from gridiron.market import at_the_line as atl
from gridiron.market import kalshi
from gridiron.model import counts
from gridiron.priced import shape as shapes

DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}


def _row(mapping):
    """A stand-in for a sqlite3.Row: subscriptable, with keys()."""
    class Row(dict):
        def keys(self):  # noqa: D102 - dict's own keys, named for the protocol
            return super().keys()
    return Row(mapping)


def _world(tmp_path, *, kickoff="2026-09-09T00:00:00Z", status="scheduled"):
    conn = db.open_db(tmp_path / "price.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g1', 'mlb', 2026, 1, 'R', 'MIA', 'NYM', ?, ?, '2026-09-08',"
        " ?, ?)",
        (kickoff, status, None if status == "scheduled" else 2,
         None if status == "scheduled" else 1))
    conn.commit()
    return conn


def _predict(conn, *, market="moneyline", subject="MIA", side="win", prob=0.6,
             line=None, prop_type=None, extra=None):
    payload = {"coverage": 1.0}
    payload.update(extra or {})
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " pass_kind, factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', 'g1', ?, ?, ?, ?, ?, ?,"
        " 'statistical', 'final', 'fs2', ?, 'test')",
        (market, prop_type, subject, line, prob, side, json.dumps(payload)))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]


def _quote(conn, *, market="moneyline", quantity="home_win", line=None,
           yes_side="home", price=0.5, fetched="2026-09-07T02:00:00Z"):
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
        " volume, fetched_utc) VALUES (?, 'T', 'E', 'mlb', 'g1', ?, ?, ?, ?,"
        " ?, ?, ?, 900, ?)",
        (atl.VENUE, market, quantity, line, yes_side, price - 0.01,
         price + 0.01, price, fetched))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]


# --- the side, which is the one that would hurt most -------------------------

def test_a_winner_question_maps_to_the_home_side_in_all_four_directions():
    """TWO INDEPENDENT FLIPS, and the first version of this read only one.

    Six of the twenty-two baseball moneylines written on 2026-09-07 said
    'lose'. Reading the subject and ignoring the side turned "the home side
    loses, 62%" into "the home side wins, 62%" -- the defect this project has
    had more often than any other, arriving through the door built to stop it.
    """
    game = {"home": "MIA", "away": "NYM"}
    cases = {("MIA", "win"): 0.60, ("MIA", "lose"): 0.40,
             ("NYM", "win"): 0.40, ("NYM", "lose"): 0.60}
    for (subject, side), expected in cases.items():
        got = shapes.blind_probability(
            _row({"model_prob": 0.60, "model_side": side, "subject": subject}),
            game, quantity="home_win")
        assert got["prob"] == pytest.approx(expected), (subject, side)
        assert side in got["why"]


def test_a_side_the_mapping_does_not_know_is_refused_not_assumed():
    game = {"home": "MIA", "away": "NYM"}
    for quantity, side in (("home_win", "cover"), ("home_margin", "win"),
                           ("total", "win")):
        got = shapes.blind_probability(
            _row({"model_prob": 0.6, "model_side": side, "subject": "MIA"}),
            game, quantity=quantity)
        assert got["prob"] is None, (quantity, side)
    # a subject that is neither side of the game
    got = shapes.blind_probability(
        _row({"model_prob": 0.6, "model_side": "win", "subject": "BOS"}),
        game, quantity="home_win")
    assert got["prob"] is None and "neither side" in got["why"]


def test_a_spread_claim_is_about_the_home_side_covering():
    game = {"home": "MIA", "away": "NYM"}
    covered = shapes.blind_probability(
        _row({"model_prob": 0.62, "model_side": "cover", "subject": "MIA"}),
        game, quantity="home_margin")
    assert covered["prob"] == pytest.approx(0.62)
    not_covered = shapes.blind_probability(
        _row({"model_prob": 0.62, "model_side": "not_cover", "subject": "MIA"}),
        game, quantity="home_margin")
    assert not_covered["prob"] == pytest.approx(0.38)
    # asked about the away side covering: a different proposition, refused
    away = shapes.blind_probability(
        _row({"model_prob": 0.62, "model_side": "cover", "subject": "NYM"}),
        game, quantity="home_margin")
    assert away["prob"] is None


def test_a_total_claim_is_always_about_the_over():
    game = {"home": "MIA", "away": "NYM"}
    under = shapes.blind_probability(
        _row({"model_prob": 0.54, "model_side": "under", "subject": "NYM at MIA"}),
        game, quantity="total")
    assert under["prob"] == pytest.approx(0.46)


# --- the four shapes ---------------------------------------------------------

def test_the_four_shapes_and_what_each_one_needs():
    line_less = shapes.claim_shape(
        _row({"line_asked": None, "market_type": "moneyline", "prop_type": None}),
        None, quantity="home_win")
    assert line_less["shape"] == shapes.LINE_LESS
    assert not shapes.needs_margin_distribution(line_less["shape"])

    matched = shapes.claim_shape(
        _row({"line_asked": 8.5, "market_type": "total", "prop_type": None}),
        8.5, quantity="total")
    assert matched["shape"] == shapes.RUNG_MATCHED
    assert not shapes.needs_margin_distribution(matched["shape"])

    count = shapes.claim_shape(
        _row({"line_asked": 1.5, "market_type": "prop",
              "prop_type": "batter_strikeouts"}), 0.5, quantity="count")
    assert count["shape"] == shapes.RUNG_DIFFERS_COUNT
    assert shapes.needs_count_rate(count["shape"])

    margin = shapes.claim_shape(
        _row({"line_asked": 8.5, "market_type": "total", "prop_type": None}),
        9.5, quantity="total")
    assert margin["shape"] == shapes.RUNG_DIFFERS_MARGIN
    assert shapes.needs_margin_distribution(margin["shape"])


def test_an_unclassifiable_question_is_refused_by_name():
    """A yardage prop at a strike off the model's rung: continuous, so the
    count model has nothing to say about it and no distribution was frozen."""
    got = shapes.claim_shape(
        _row({"line_asked": 235.5, "market_type": "prop",
              "prop_type": "passing_yards"}), 245.5, quantity="count")
    assert got["shape"] is None
    assert got["refused"] == "no_distribution_for_this_market"
    assert "not a counting stat" in got["why"]

    mismatched = shapes.claim_shape(
        _row({"line_asked": 8.5, "market_type": "total", "prop_type": None}),
        None, quantity="total")
    assert mismatched["refused"] == "line_presence_differs"


# --- the venue's number, from the claim's side -------------------------------

def test_the_venue_line_is_read_from_the_home_side():
    """A LATENT SIGN ERROR, found before the first claim was written.

    `kalshi.parse_markets` stores the home strike on a home row and the AWAY
    strike on an away row -- opposite numbers. `rung_for` complemented the
    price for an away row and left the line alone, so a claim from one would
    have integrated the distribution at +3.5 while pricing -3.5.
    """
    home = _row({"line": -3.5, "yes_side": "home"})
    away = _row({"line": 3.5, "yes_side": "away"})
    assert atl.home_view_line(home) == -3.5
    assert atl.home_view_line(away) == -3.5
    assert atl.home_view_line(_row({"line": None, "yes_side": "home"})) is None


# --- the writer --------------------------------------------------------------

def test_a_winner_contract_writes_a_claim_with_no_distribution(tmp_path):
    """THE FINDING BEHIND THE WHOLE BRIEF. A moneyline needs nothing frozen:
    the blind probability answers the venue's question exactly."""
    conn = _world(tmp_path)
    pid = _predict(conn, market="moneyline", subject="MIA", side="win", prob=0.6)
    _quote(conn, market="moneyline", quantity="home_win", price=0.55)
    got = atl.evaluate(conn, [pid])
    assert got["claims"] == 1 and got["line_less"] == 1
    row = conn.execute("SELECT * FROM at_the_line_claims").fetchone()
    assert row["shape"] == "line_less"
    assert row["dist_mean"] is None and row["dist_sd"] is None
    assert row["model_prob"] == pytest.approx(0.6)
    assert row["side"] == "home"


def test_a_rung_matched_total_writes_a_claim_with_no_distribution(tmp_path):
    conn = _world(tmp_path)
    pid = _predict(conn, market="total", subject="NYM at MIA", side="under",
                   prob=0.54, line=8.5)
    _quote(conn, market="total", quantity="total", line=8.5, yes_side="over",
           price=0.5)
    got = atl.evaluate(conn, [pid])
    assert got["claims"] == 1 and got["rung_matched"] == 1
    row = conn.execute("SELECT * FROM at_the_line_claims").fetchone()
    assert row["model_prob"] == pytest.approx(0.46), "the over, not the under"


def test_a_count_prop_at_a_differing_rung_reads_the_blind_rate(tmp_path):
    """Q3. The venue's declared series carry no prop today, so this is the
    only place the count path runs -- which is the point of testing it."""
    conn = _world(tmp_path)
    pid = _predict(conn, market="prop", prop_type="batter_strikeouts",
                   subject="A Batter", side="under", prob=0.77, line=1.5,
                   extra={"expected_count": 0.8972, "model_form": "poisson"})
    _quote(conn, market="prop", quantity="count", line=0.5, yes_side="over",
           price=0.5)
    got = atl.evaluate(conn, [pid])
    assert got["claims"] == 1 and got["rung_differs_count"] == 1
    row = conn.execute("SELECT * FROM at_the_line_claims").fetchone()
    expected = counts.p_over(0.8972, 0.5, form="poisson", dispersion=1.0)
    assert row["model_prob"] == pytest.approx(expected, abs=1e-6)
    assert row["dist_mean"] is None, "a count claim carries no margin parameters"


def test_a_count_claim_without_a_blind_rate_is_refused(tmp_path):
    """A rate fitted after the venue's strike was visible is LAW 1 with extra
    steps, so a prediction that did not carry one gets no claim."""
    conn = _world(tmp_path)
    pid = _predict(conn, market="prop", prop_type="batter_strikeouts",
                   subject="A Batter", side="under", prob=0.77, line=1.5)
    _quote(conn, market="prop", quantity="count", line=0.5, yes_side="over")
    got = atl.evaluate(conn, [pid])
    assert got["claims"] == 0 and got["no_blind_rate"] == 1


def test_a_margin_claim_still_needs_its_frozen_distribution(tmp_path):
    conn = _world(tmp_path)
    pid = _predict(conn, market="total", subject="NYM at MIA", side="under",
                   prob=0.54, line=8.5)
    _quote(conn, market="total", quantity="total", line=9.5, yes_side="over")
    got = atl.evaluate(conn, [pid])
    assert got["claims"] == 0 and got["no_distribution"] == 1

    with_dist = _predict(conn, market="total", subject="NYM at MIA (second look)",
                         side="over", prob=0.54, line=8.5,
                         extra={"margin_distribution": dict(DIST, quantity="total",
                                                            mean=9.0, sd=4.0)})
    got2 = atl.evaluate(conn, [with_dist])
    assert got2["claims"] == 1 and got2["rung_differs_margin"] == 1
    row = conn.execute(
        "SELECT * FROM at_the_line_claims WHERE prediction_id = ?",
        (with_dist,)).fetchone()
    assert row["dist_sd"] == pytest.approx(4.0)


# --- the game must not have started ------------------------------------------

def test_no_claim_is_written_against_a_live_price(tmp_path):
    """A PRE-GAME PROBABILITY AGAINST AN IN-PLAY PRICE IS NOT A DISAGREEMENT.

    On the first live run, seventeen of twenty-nine claims did exactly that --
    one of them a home side the model made 59.6% against a venue price of
    3.5%, which was the fourth inning.
    """
    conn = _world(tmp_path, kickoff="2026-09-07T01:00:00Z")
    pid = _predict(conn)
    _quote(conn, price=0.55, fetched="2026-09-07T02:00:00Z")   # after first pitch
    got = atl.evaluate(conn, [pid])
    assert got["claims"] == 0 and got["quote_after_first_pitch"] == 1


def test_no_claim_is_written_on_a_game_already_under_way(tmp_path):
    conn = _world(tmp_path, status="in")
    pid = _predict(conn)
    _quote(conn, price=0.55)
    got = atl.evaluate(conn, [pid])
    assert got["claims"] == 0 and got["game_under_way"] == 1


# --- the table itself --------------------------------------------------------

def test_a_shape_may_not_claim_inputs_it_does_not_carry(tmp_path):
    conn = _world(tmp_path)
    pid = _predict(conn)
    qid = _quote(conn)
    with pytest.raises(sqlite3.IntegrityError, match="exactly the inputs"):
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape, dist_mean,"
            " dist_sd, model_prob, venue_price, venue_implied, price_basis,"
            " created_utc) VALUES (?,?,?,'mlb','g1','moneyline','home_win',"
            " NULL,'home','line_less', 2.0, 13.0, 0.6, 0.5, 0.5, 'mid',"
            " '2026-09-08T00:00:00Z')", (pid, qid, atl.VENUE))


def test_the_claim_row_records_which_shape_it_is(tmp_path):
    """FOUR SHAPES NEVER MERGE. A line-less claim carries no distribution
    error, so a curve mixing it with a rung-differing one would report the
    distribution as better than it is -- LAW 6's argument, one level down."""
    conn = _world(tmp_path)
    pid = _predict(conn)
    _quote(conn, price=0.55)
    atl.evaluate(conn, [pid])
    shape = conn.execute("SELECT shape FROM at_the_line_claims").fetchone()[0]
    assert shape in shapes.SHAPES
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE at_the_line_claims SET shape = 'rung_matched'")


def test_the_widening_rebuilds_a_narrow_table_and_keeps_its_guards(tmp_path):
    """A database built before shapes existed refuses three of the four."""
    conn = _world(tmp_path)
    conn.executescript("""
        DROP TABLE at_the_line_claims;
        CREATE TABLE at_the_line_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER NOT NULL REFERENCES predictions (id),
            quote_id INTEGER NOT NULL REFERENCES venue_quotes (id),
            venue TEXT NOT NULL, sport TEXT NOT NULL,
            game_id TEXT NOT NULL REFERENCES games (id),
            market TEXT NOT NULL CHECK (market IN ('spread','total','moneyline')),
            quantity TEXT NOT NULL CHECK (quantity IN ('home_margin','total','home_win')),
            line REAL, side TEXT NOT NULL CHECK (side IN ('home','over')),
            dist_mean REAL NOT NULL, dist_sd REAL NOT NULL,
            model_prob REAL NOT NULL, venue_price REAL NOT NULL,
            venue_implied REAL NOT NULL, price_basis TEXT NOT NULL,
            created_utc TEXT NOT NULL, resolved_utc TEXT, outcome INTEGER,
            UNIQUE (prediction_id, quote_id));
    """)
    conn.commit()
    assert atl.ensure_claim_shape(conn) is True
    columns = [r[1] for r in conn.execute("PRAGMA table_info(at_the_line_claims)")]
    assert "shape" in columns
    triggers = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'"
        " AND tbl_name='at_the_line_claims'")}
    assert "at_the_line_no_delete" in triggers, "the guards came back"
    assert "at_the_line_requires_a_blind_rate" in triggers
    assert atl.ensure_claim_shape(conn) is False, "and it is idempotent"


def test_the_schema_splitter_reads_a_trigger_to_its_end():
    """Splitting the schema on ';' cuts a trigger into fragments, and the
    first version of the migration did exactly that -- dropping the old table
    and then failing to restore its guards."""
    schema = (Path(db.__file__).resolve().parent / "schema.sql").read_text(
        encoding="utf-8")
    statements = atl._schema_statements(schema, "at_the_line_claims")
    triggers = [s for s in statements if s.startswith("CREATE TRIGGER")]
    assert triggers, "the claim table has triggers"
    for statement in triggers:
        assert statement.rstrip().endswith("END;"), statement[:60]


# --- the ticker that found all of this ---------------------------------------

def test_the_baseball_ticker_carries_the_first_pitch():
    """BASEBALL PLAYS DOUBLEHEADERS, so date and teams do not identify a game
    and the venue puts the start time in the ticker. Ours did not, which is
    why the record held 1,172 venue quotes and none of them baseball."""
    game = _row({"league_date": "2026-09-07", "kickoff_utc": "2026-09-07T17:10:00Z",
                 "home": "MIA", "away": "NYM"})
    assert kalshi.event_ticker("mlb", "moneyline", game) == \
        "KXMLBGAME-26SEP071310NYMMIA"
    # and football, which plays one game per matchup per day, is unchanged
    nfl = _row({"league_date": "2026-09-09", "kickoff_utc": "2026-09-09T20:15:00Z",
                "home": "SEA", "away": "NE"})
    assert kalshi.event_ticker("nfl", "spread", nfl) == "KXNFLSPREAD-26SEP09NESEA"
    assert "mlb" in kalshi.CROSSWALK_MEASURED, "measured, never guessed"
