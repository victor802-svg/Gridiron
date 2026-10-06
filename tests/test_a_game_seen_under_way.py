"""A GAME'S START IS THE EARLIER OF ITS LISTED START AND THE FIRST POLL THAT
SAW IT TRULY UNDER WAY; NOTHING IS PRICED ON A GAME THAT IS NOT STILL
UPCOMING (operator question 38 (A) and its two rulings, 2026-10-06, second
set, docs/briefs/2026-10-06-rulings-second.md; built 2026-10-07).

The ruling, whole: "Q38 (A), plus: 1. A game's start is the earlier of its
listed start and the first poll that sees it truly under way (a score or
period recorded; MLB's warm-up "Live" before the listed start does not
count). No read at or after that instant is a close or a claim. 2.
recommend.for_predictions refuses any game that is not still upcoming: in
progress, final, postponed, or past its start as defined in 1. Planting: a
finished game's pick priced; an in-play read used as a close."

Every test here fails on c0fa561, the release: it kept no instant at which a
game was first seen under way, read every close and claim against the listed
start alone, and priced a finished game's question.
"""
from __future__ import annotations

import ast
import importlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gridiron import audit, db, language, live, recount, shortlist, tasks, views
from gridiron.market import at_the_line, recommend
from gridiron.priced import coverage

ROOT = Path(__file__).resolve().parents[1]
GAME, PK = "mlb_990380", 990380
LISTED = "2026-09-27T19:10:00Z"
SEEN = "2026-09-27T19:02:00Z"


@pytest.fixture(autouse=True)
def _covered(monkeypatch):
    """Every market priceable: coverage is not what these test."""
    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})


def _at(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _mlb(pk, *, abstract="Live", detailed="In Progress", coded="I",
         innings=({"num": 1, "home": {"runs": 0, "hits": 0},
                   "away": {"runs": 1, "hits": 2}},),
         half="Bottom", runs=(0, 1)):
    """A statsapi schedule payload hydrated with the linescore, shaped as the
    record's cached ones are (measured 2026-10-07)."""
    line = {"teams": {"home": {"runs": runs[0]}, "away": {"runs": runs[1]}},
            "innings": list(innings)}
    if half:
        line.update(currentInning=1, currentInningOrdinal="1st",
                    inningHalf=half, inningState=half, outs=0)
    return {"dates": [{"games": [{
        "gamePk": pk, "gameDate": LISTED,
        "status": {"abstractGameState": abstract, "detailedState": detailed,
                   "codedGameState": coded, "statusCode": coded},
        "linescore": line}]}]}


#: statsapi's Pre-Game payload as the record's cache holds it, three hours
#: before a listed start: "Top 1st", 0-0, one inning carrying no run count.
PRE_GAME = dict(abstract="Preview", detailed="Pre-Game", coded="P",
                innings=({"num": 1, "home": {"hits": 0}, "away": {"hits": 0}},),
                half="Top", runs=(0, 0))
#: the warm-up: the league's 'Live' with the pre-game coded state.
WARM_UP = dict(PRE_GAME, abstract="Live", detailed="Warmup")


def _espn(event_id, *, name="STATUS_IN_PROGRESS", state="in", period=1,
          scores=("3", "0"), periods=1):
    return {"id": event_id, "date": LISTED, "competitions": [{
        "status": {"period": period, "displayClock": "8:41",
                   "type": {"name": name, "state": state}},
        "competitors": [
            {"homeAway": "home", "id": "1", "score": scores[0],
             "linescores": [{"value": 3}] * periods},
            {"homeAway": "away", "id": "2", "score": scores[1],
             "linescores": [{"value": 0}] * periods}]}]}


def _game(conn, gid, *, start=LISTED, status="scheduled", sport="mlb", n=0):
    scores = {"scheduled": (None, None), "in": (0, 0), "final": (3, 2)}[status]
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES (?, ?, 2026, 1, 'R', ?, ?, ?, ?, '2026-09-27', ?, ?)",
        (gid, sport, f"H{n}", f"A{n}", start, status, *scores))


def _forecast(conn, gid, *, n=0, claimed="2026-09-27T12:31:00Z",
              read="2026-09-27T12:30:00Z", price=0.46, recommended=False,
              claim=True):
    """A shortlisted moneyline on the home side at 60%, read and claimed at
    46c that morning (a pick that clears the bar) -- or, `claim=False`, not
    read at the venue at all."""
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-27T09:00:00Z', 'mlb', ?, 'moneyline', ?, NULL, 0.6, 'win',"
        " 'statistical', 'final', 'fs2', '{\"coverage\": 1.0}', 'test')",
        (gid, f"H{n}"))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    if claim:
        quote = _read(conn, gid, read, price)
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape, dist_mean,"
            " dist_sd, model_prob, venue_price, venue_implied, price_basis,"
            " created_utc) VALUES (?, ?, 'kalshi', 'mlb', ?, 'moneyline',"
            " 'home_win', NULL, 'home', 'line_less', NULL, NULL, 0.6, ?, ?,"
            " 'mid', ?)", (pid, quote, gid, price, price, claimed))
    rec = None
    if recommended:
        conn.execute(
            "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
            " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
            " created_utc) VALUES (?, 'mlb', ?, 'moneyline', 'yes', 0.6, ?,"
            " 10.0, 'flat', 1.0, 0, '2026-09-27T13:00:00Z')", (pid, gid, price))
        rec = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return pid, rec


def _read(conn, gid, at, price, *, ticker=None):
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
        " volume, fetched_utc, read_kind) VALUES ('kalshi', ?, 'E', 'mlb', ?,"
        " 'moneyline', 'home_win', NULL, 'home', ?, ?, NULL, 900, ?,"
        " 'near_start')", (ticker or f"T-{gid}", gid, price - 0.01, price + 0.01, at))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]


def _poll(conn, monkeypatch, at, *, mlb=None, espn=None):
    """The shipped live poll at the held instant `at`, its own stamp held."""
    monkeypatch.setattr(live, "utcnow", lambda: at)
    if mlb is not None:
        fetch = lambda c, sport, day: live._read_mlb(mlb)  # noqa: E731
    else:
        fetch = lambda c, sport, day: [  # noqa: E731
            dict(live.read_event(e), game_id=str(e["id"])) for e in espn]
    return live.poll(conn, now=_at(at), fetcher=fetch)


def _rows(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM live_first_under_way ORDER BY game_id")]


def _world(tmp_path, *, recommended=True):
    conn = db.open_db(tmp_path / "q38.db")
    at_the_line.ensure_read_kind(conn)
    _game(conn, GAME)
    pid, rec = _forecast(conn, GAME, recommended=recommended)
    return conn, pid, rec


# --- the first poll that sees a game truly under way ---------------------------

def test_a_pregame_payload_writes_no_instant(tmp_path, monkeypatch):
    """The placeholders a pregame payload carries are no score or period
    recorded: statsapi's Pre-Game "Top 1st", 0-0 with no inning's runs, and
    ESPN's scheduled event at period 0 with scores of "0"."""
    conn, _pid, _rec = _world(tmp_path)
    _poll(conn, monkeypatch, "2026-09-27T19:01:00Z", mlb=_mlb(PK, **PRE_GAME))
    _game(conn, "401990001", sport="cfb", n=1)
    conn.commit()
    _poll(conn, monkeypatch, "2026-09-27T19:01:30Z", espn=[_espn(
        "401990001", name="STATUS_SCHEDULED", state="pre", period=0,
        scores=("0", "0"), periods=0)])
    assert _rows(conn) == []


def test_the_warm_up_live_before_the_listed_start_writes_no_instant(tmp_path, monkeypatch):
    """MLB's warm-up "Live" before the listed start does not count (the
    ruling's words): the poll stores it as 'in', as it always has, and writes
    no instant -- and the game is still read until its listed start."""
    conn, pid, _rec = _world(tmp_path)
    _poll(conn, monkeypatch, "2026-09-27T19:01:00Z", mlb=_mlb(PK, **WARM_UP))
    assert conn.execute("SELECT status FROM games WHERE id = ?",
                        (GAME,)).fetchone()[0] == "in"
    assert _rows(conn) == []
    picked = tasks._near_start_selection(conn, "2026-09-27T19:05:01Z")
    assert picked["recs"] == [pid]
    assert [m["status"] for m in picked["marked_under_way"]] == ["in"]
    # ...and a warm-up 'Live' that somehow carried an inning's runs before
    # the listed start is refused all the same
    assert live.under_way_evidence(
        dict(status="in", warm_up=True, innings_recorded=1), LISTED,
        _at("2026-09-27T19:05:00Z")) is None


def test_the_first_poll_that_sees_a_score_or_period_writes_the_instant_once(
        tmp_path, monkeypatch):
    """An inning's runs (statsapi) or a period numbered one or more and a
    period's score (ESPN), under a status the feed calls under way: one row,
    stamped with the poll's own instant, the evidence in words beside it;
    the next poll writes nothing."""
    conn, _pid, _rec = _world(tmp_path)
    report = _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    assert report["first_under_way"] == [GAME]
    (row,) = _rows(conn)
    assert (row["game_id"], row["under_way_utc"], row["sport"],
            row["feed_status"]) == (GAME, SEEN, "mlb", "In Progress")
    assert "runs recorded in 1 inning" in row["evidence"]
    assert "the score 0-1 (home first)" in row["evidence"]
    assert LISTED in row["evidence"]
    again = _poll(conn, monkeypatch, "2026-09-27T19:03:30Z", mlb=_mlb(
        PK, innings=({"num": 1, "home": {"runs": 2}, "away": {"runs": 1}},),
        runs=(2, 1)))
    assert again["first_under_way"] == [] and _rows(conn) == [row]
    _game(conn, "401990002", sport="cfb", n=2)
    conn.commit()
    _poll(conn, monkeypatch, "2026-09-27T19:04:00Z", espn=[_espn("401990002")])
    espn = next(r for r in _rows(conn) if r["game_id"] == "401990002")
    assert espn["under_way_utc"] == "2026-09-27T19:04:00Z"
    assert "period 1 recorded" in espn["evidence"]
    assert "a score recorded for 1 period" in espn["evidence"]


def _day(*payloads):
    """One day's statsapi schedule holding every game of the payloads given,
    as the poll's one request for a day returns them."""
    return {"dates": [{"games": [g for p in payloads for g in p["dates"][0]["games"]]}]}


def test_the_poll_writes_the_instant_of_a_game_its_days_payload_shows_under_way_before_its_window(
        tmp_path, monkeypatch):
    """Q38's prover (2026-10-07): the poll's request is the whole day's
    scoreboard, and its window holds only the games listed within ten minutes.
    A game listed for 19:10 that the payload shows in progress at 18:30 -- a
    stale listing, the case question 38 (A) was ruled for -- while another
    game's window is open was looked past until its own window opened: its
    in-play reads were read, claimed and priced (its status still
    'scheduled') until 19:00. The poll now writes its instant, by the same
    evidence, while its listed start is still ahead; it writes nothing else
    about it, and nothing for a game of the payload that is only listed,
    warming up, or already past its listed start."""
    conn, pid, _rec = _world(tmp_path)
    _game(conn, "mlb_990390", start="2026-09-27T18:35:00Z", n=10)   # its window open
    _game(conn, "mlb_990391", start="2026-09-27T19:20:00Z", n=11)   # pregame, later
    _game(conn, "mlb_990392", start="2026-09-27T19:25:00Z", n=12)   # warming up, later
    _game(conn, "mlb_990393", start="2026-09-27T16:05:00Z", status="final", n=13)
    conn.commit()
    report = _poll(conn, monkeypatch, "2026-09-27T18:30:00Z", mlb=_day(
        _mlb(990390), _mlb(PK), _mlb(990391, **PRE_GAME), _mlb(990392, **WARM_UP),
        _mlb(990393, abstract="Final", detailed="Final", coded="F")))
    rows = {r["game_id"]: r for r in _rows(conn)}
    assert set(rows) == {"mlb_990390", GAME}
    assert rows[GAME]["under_way_utc"] == "2026-09-27T18:30:00Z"
    assert "runs recorded in 1 inning" in rows[GAME]["evidence"]
    assert sorted(report["first_under_way"]) == sorted(rows)
    # nothing else about it is written: its status waits for its window
    assert conn.execute("SELECT status FROM games WHERE id = ?",
                        (GAME,)).fetchone()[0] == "scheduled"
    # and every reader reads the start it gives
    assert live.start_of(LISTED, rows[GAME]["under_way_utc"]) == _at("2026-09-27T18:30:00Z")
    assert tasks._near_start_selection(conn, "2026-09-27T18:35:01Z")["recs"] == []
    assert recommend.not_still_upcoming(
        "scheduled", LISTED, rows[GAME]["under_way_utc"], "2026-09-27T18:35:01Z") \
        == recommend.FIRST_SEEN_UNDER_WAY_WHY
    assert recommend.for_predictions(conn, [pid], now="2026-09-27T18:35:01Z") == []
    # a game the record files under another sport is never written from this
    # sport's scoreboard
    _game(conn, "401990005", sport="cfb", start="2026-09-27T21:00:00Z", n=14)
    conn.commit()
    assert live.record_first_under_way(
        conn, "401990005", dict(status="in", innings_recorded=1, status_raw="In Progress"),
        only_before_its_listed_start=True, sport="mlb") is False


def test_a_postponed_game_writes_no_instant(tmp_path, monkeypatch):
    """statsapi calls a postponed game 'Final' (its abstract state) with no
    linescore: no inning's runs, so no instant -- whatever the poll stores."""
    conn, _pid, _rec = _world(tmp_path)
    _poll(conn, monkeypatch, "2026-09-27T19:05:00Z", mlb=_mlb(
        PK, abstract="Final", detailed="Postponed", coded="D", innings=(),
        half=None, runs=(None, None)))
    assert _rows(conn) == []


def test_the_instant_is_never_updated_deleted_or_replaced(tmp_path, monkeypatch):
    """One row per game, permanent, as its precedents are: an update, a
    delete, a replacing insert and a second insert are each refused."""
    conn, _pid, _rec = _world(tmp_path)
    _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    (row,) = _rows(conn)
    for statement in (
            "UPDATE live_first_under_way SET under_way_utc = '2026-09-27T19:20:00Z'",
            "DELETE FROM live_first_under_way",
            "INSERT OR REPLACE INTO live_first_under_way (game_id, under_way_utc,"
            " sport, feed_status, evidence) VALUES ('mlb_990380',"
            " '2026-09-27T19:20:00Z', 'mlb', 'In Progress', 'a second sighting')",
            "REPLACE INTO live_first_under_way (game_id, under_way_utc, sport,"
            " feed_status, evidence) VALUES ('mlb_990380',"
            " '2026-09-27T18:00:00Z', 'mlb', 'In Progress', 'dated back by hand')",
            "INSERT INTO live_first_under_way (game_id, under_way_utc, sport,"
            " feed_status, evidence) VALUES ('mlb_990380',"
            " '2026-09-27T19:20:00Z', 'mlb', 'In Progress', 'a second sighting')"):
        with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
            conn.execute(statement)
        conn.rollback()
    assert _rows(conn) == [row]
    # an instant that is not one is refused by the table itself
    _game(conn, "mlb_990399", n=9)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("INSERT INTO live_first_under_way (game_id, under_way_utc,"
                     " sport, feed_status, evidence) VALUES ('mlb_990399',"
                     " '2026-09-27T19:20Z', 'mlb', 'In Progress', 'to the minute')")


# --- the one door -------------------------------------------------------------

def test_a_games_start_is_the_earlier_of_its_listed_start_and_the_first_poll():
    assert live.start_of(LISTED, None) == _at(LISTED)
    assert live.start_of(LISTED, SEEN) == _at(SEEN)
    assert live.start_of(LISTED, "2026-09-27T19:30:00Z") == _at(LISTED)
    assert live.start_of(None, SEEN) == _at(SEEN)
    assert live.start_of(None, None) is None
    # a listed start to the minute is the same instant
    assert live.start_of("2026-09-27T19:10Z", SEEN) == _at(SEEN)
    with pytest.raises(ValueError):
        live.start_of("2026-09-27T19:10:00", SEEN)     # names no zone


def test_the_sql_spelling_agrees_with_the_door(tmp_path, monkeypatch):
    """`live.before_the_start` is `live.start_of` in SQL, stamp for stamp,
    on a game seen under way before its listed start, one seen after it, one
    never seen, and one with no listed start."""
    conn = db.open_db(tmp_path / "spelling.db")
    for n, (gid, listed, seen) in enumerate((
            ("mlb_990401", LISTED, SEEN), ("mlb_990402", LISTED, "2026-09-27T19:30:00Z"),
            ("mlb_990403", LISTED, None), ("mlb_990404", None, SEEN))):
        _game(conn, gid, start=listed, n=n)
        if seen:
            conn.execute("INSERT INTO live_first_under_way (game_id, under_way_utc,"
                         " sport, feed_status, evidence) VALUES (?, ?, 'mlb',"
                         " 'In Progress', 'written in this test')", (gid, seen))
    conn.commit()
    stamps = ("2026-09-27T19:01:59Z", SEEN, "2026-09-27T19:05:00Z", LISTED,
              "2026-09-27T19:10:01Z", "2026-09-27T19:31:00Z")
    for g in conn.execute("SELECT g.id, g.kickoff_utc,"
                          f" {live.under_way_sql('g', conn)} AS seen FROM games g"):
        start = live.start_of(g["kickoff_utc"], g["seen"])
        for stamp in stamps:
            got = conn.execute(
                "SELECT 1 FROM games g WHERE g.id = :g AND "
                + live.before_the_start("x.stamp", "g", conn).replace(
                    "x.stamp", ":s"), {"g": g["id"], "s": stamp}).fetchone()
            assert bool(got) == (start is None or _at(stamp) < start), (g["id"], stamp)


def test_a_record_without_the_table_starts_every_game_at_its_listed_start(tmp_path):
    """A record no release carrying the table has opened -- read through a
    read-only door, it cannot be migrated -- never saw a game under way:
    every spelling reads the listed start there, and nothing raises."""
    conn = db.open_db(tmp_path / "older.db")
    _game(conn, GAME)
    conn.execute("DROP TABLE live_first_under_way")
    conn.commit()
    assert live.keeps_first_under_way(conn) is False
    assert live.under_way_sql("g", conn) == "NULL"
    assert "live_first_under_way" not in live.before_the_start("c.created_utc", "g", conn)
    assert live.record_first_under_way(conn, GAME, dict(status="in", innings_recorded=1)) is False


# --- every reader of a close or a claim reads it ----------------------------------

def test_the_near_start_run_keeps_a_game_until_its_start_as_defined(tmp_path, monkeypatch):
    """Item 1 keeps a game until its start; the start is now the earlier of
    the listed start and the first poll that saw it under way, so a game seen
    at 19:02 is not read at 19:05 -- nor counted in the noop's words."""
    conn, pid, _rec = _world(tmp_path)
    assert tasks._near_start_selection(conn, "2026-09-27T19:05:01Z")["recs"] == [pid]
    assert tasks._games_starting_within(conn, "2026-09-27T19:05:01Z") == 1
    _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    assert tasks._near_start_selection(conn, "2026-09-27T19:01:59Z")["recs"] == [pid]
    assert tasks._near_start_selection(conn, "2026-09-27T19:05:01Z")["recs"] == []
    assert tasks._games_starting_within(conn, "2026-09-27T19:05:01Z") == 0
    # a loader's refresh setting the status back to 'scheduled' moves nothing
    conn.execute("UPDATE games SET status = 'scheduled', home_score = NULL,"
                 " away_score = NULL WHERE id = ?", (GAME,))
    conn.commit()
    assert tasks._near_start_selection(conn, "2026-09-27T19:05:01Z")["recs"] == []


def test_no_read_at_or_after_the_start_as_defined_is_claimed(tmp_path, monkeypatch):
    conn, pid, _rec = _world(tmp_path)
    before = _read(conn, GAME, "2026-09-27T18:35:01Z", 0.50)
    during = _read(conn, GAME, "2026-09-27T19:05:01Z", 0.88)
    _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    monkeypatch.setattr(at_the_line, "utcnow", lambda: "2026-09-27T19:05:02Z")
    counts = at_the_line.evaluate(conn, [pid])
    assert counts["quote_after_first_pitch"] >= 1
    claimed = {r[0] for r in conn.execute(
        "SELECT quote_id FROM at_the_line_claims WHERE prediction_id = ?", (pid,))}
    assert before in claimed and during not in claimed


def test_the_close_is_the_last_read_before_the_start_as_defined(tmp_path, monkeypatch):
    """The close: its own contract's last near-start read before the start
    -- 19:02, when the poll saw the game under way -- and its minutes counted
    to that instant; the 88c read at 19:05:01 is no close."""
    conn, pid, rec = _world(tmp_path)
    _read(conn, GAME, "2026-09-27T18:35:01Z", 0.50, ticker=f"T-{GAME}")
    _read(conn, GAME, "2026-09-27T19:05:01Z", 0.88, ticker=f"T-{GAME}")
    _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    monkeypatch.setattr(recommend, "utcnow", lambda: "2026-09-27T19:05:30Z")
    assert recommend.record_closing_prices(conn)["closed"] == 1
    got = conn.execute(
        "SELECT r.close_price, k.minutes_before_start, q.fetched_utc"
        "  FROM recommendations r JOIN recommendation_closes k"
        "    ON k.recommendation_id = r.id"
        "  JOIN venue_quotes q ON q.id = k.close_quote_id WHERE r.id = ?",
        (rec,)).fetchone()
    assert (got["fetched_utc"], got["close_price"]) == ("2026-09-27T18:35:01Z", 0.5)
    assert got["minutes_before_start"] == pytest.approx(27.0)
    assert audit.reads_at_or_after_the_start_faults(conn) == []


def test_the_at_the_line_record_and_its_recount_read_the_start_as_defined(
        tmp_path, monkeypatch):
    """A claim written after the poll saw the game under way never stands,
    and the recount, which restates the start from the two stored instants,
    agrees -- where a window that forgot the second disagrees with it."""
    conn, pid, _rec = _world(tmp_path)
    _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    late = _read(conn, GAME, "2026-09-27T19:05:01Z", 0.88)
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', ?, 'moneyline', 'home_win', NULL,"
        " 'home', 'line_less', NULL, NULL, 0.6, 0.88, 0.88, 'mid',"
        " '2026-09-27T19:05:30Z')", (pid, late, GAME))
    conn.commit()
    standing = at_the_line.standing_claims(conn, sport="mlb", market="moneyline",
                                           predictor="statistical")
    again = recount.standing_claims_of(recount.claims(
        conn, sport="mlb", market="moneyline", predictor="statistical",
        event_tier=None))
    assert [c["created_utc"] for c in standing] == ["2026-09-27T12:31:00Z"]
    assert [c["created_utc"] for c in again.values()] == ["2026-09-27T12:31:00Z"]
    # the window put back to the listed start takes the in-play claim; the
    # recount does not
    monkeypatch.setattr(live, "before_the_start", lambda stamp, game, c: (
        f"({game}.kickoff_utc IS NULL OR julianday({stamp}) < julianday({game}.kickoff_utc))"))
    forgot = at_the_line.standing_claims(conn, sport="mlb", market="moneyline",
                                         predictor="statistical")
    assert [c["created_utc"] for c in forgot] == ["2026-09-27T19:05:30Z"]


def test_the_page_states_no_claim_written_after_the_start(tmp_path, monkeypatch):
    """The at-the-line sentence and a live card's pregame figure read the
    latest claim written before the start -- the shape of the 17 baseball
    claims of 7 September, written from in-play reads two hours after their
    games' listed starts, which the sentence stated as "the venue's price
    implies 4%"."""
    conn, pid, _rec = _world(tmp_path, recommended=False)
    late = _read(conn, GAME, "2026-09-27T19:37:14Z", 0.04)
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', ?, 'moneyline', 'home_win', NULL,"
        " 'home', 'line_less', NULL, NULL, 0.6, 0.04, 0.04, 'mid',"
        " '2026-09-27T19:41:46Z')", (pid, late, GAME))
    conn.commit()
    said = views._at_the_line(conn, "mlb", [pid], {})[pid]
    assert "implies 46%" in said["words"] and "4%" not in said["words"].replace("46%", "")
    pregame = views._pregame_claim(conn, {"prediction_id": pid}, {})
    first = conn.execute("SELECT MIN(id) FROM at_the_line_claims").fetchone()[0]
    assert pregame["claim_id"] == first
    # and a game seen under way before its listed start: a claim written
    # between the two instants is no claim either
    _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    between = _read(conn, GAME, "2026-09-27T19:04:00Z", 0.70)
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', ?, 'moneyline', 'home_win', NULL,"
        " 'home', 'line_less', NULL, NULL, 0.6, 0.70, 0.70, 'mid',"
        " '2026-09-27T19:04:01Z')", (pid, between, GAME))
    conn.commit()
    assert views._pregame_claim(conn, {"prediction_id": pid}, {})["claim_id"] == first
    assert "implies 46%" in views._at_the_line(conn, "mlb", [pid], {})[pid]["words"]


# --- ruling 2: nothing priced on a game that is not still upcoming ----------------

def _four(tmp_path, monkeypatch, *, unread=()):
    """A finished game, one still 'scheduled' past its listed start, one the
    poll saw under way before its listed start (then set 'scheduled' again
    by a loader's refresh), and one still to come -- each shortlisted and
    claimed before its start, unless named `unread`."""
    conn = db.open_db(tmp_path / "four.db")
    at_the_line.ensure_read_kind(conn)
    games = (("mlb_990381", "2026-09-27T17:10:00Z", "final"),
             ("mlb_990382", "2026-09-27T18:10:00Z", "scheduled"),
             ("mlb_990383", "2026-09-27T20:10:00Z", "scheduled"),
             ("mlb_990384", "2026-09-28T01:10:00Z", "scheduled"))
    ids = {}
    for n, (gid, start, status) in enumerate(games):
        _game(conn, gid, start=start, status=status, n=n)
        ids[gid] = _forecast(conn, gid, n=n, read="2026-09-27T10:00:00Z",
                             claimed="2026-09-27T10:01:00Z",
                             claim=gid not in unread)[0]
    monkeypatch.setattr(live, "utcnow", lambda: "2026-09-27T20:01:00Z")
    live.poll(conn, now=_at("2026-09-27T20:01:00Z"),
              fetcher=lambda c, s, d: live._read_mlb(_mlb(990383)))
    conn.execute("UPDATE games SET status = 'scheduled', home_score = NULL,"
                 " away_score = NULL WHERE id = 'mlb_990383'")
    conn.commit()
    return conn, ids


ASKED = "2026-09-27T20:05:00Z"


def test_no_entry_for_a_game_that_is_not_still_upcoming(tmp_path, monkeypatch):
    """No price, side, edge or size -- no entry at all -- for a game final,
    in play, past its start still 'scheduled', or seen under way before its
    listed start; and never a raise."""
    conn, ids = _four(tmp_path, monkeypatch)
    got = {e["prediction_id"]: e for e in recommend.for_predictions(
        conn, list(ids.values()), now=ASKED)}
    assert set(got) == {ids["mlb_990384"]}
    assert got[ids["mlb_990384"]]["side"] == "yes"
    # asked before every start, all four were to come but the finished one
    early = recommend.for_predictions(conn, list(ids.values()),
                                      now="2026-09-27T16:00:00Z")
    assert {e["prediction_id"] for e in early} == set(ids.values()) - {ids["mlb_990381"]}
    # 'in' is refused whatever its cause -- baseball's warm-up included
    conn.execute("UPDATE games SET status = 'in', home_score = 0, away_score = 0"
                 " WHERE id = 'mlb_990384'")
    conn.commit()
    assert recommend.for_predictions(conn, list(ids.values()), now=ASKED) == []
    words = {recommend.not_still_upcoming(*args) for args in (
        ("final", LISTED, None, ASKED), ("in", LISTED, None, ASKED),
        ("scheduled", "2026-09-27T18:10:00Z", None, ASKED),
        ("scheduled", "2026-09-27T20:10:00Z", "2026-09-27T20:01:00Z", ASKED),
        ("scheduled", "2026-09-27T20:10", None, ASKED))}
    assert words == {recommend.OVER_WHY, recommend.BEING_PLAYED_WHY,
                     recommend.PAST_ITS_START_WHY,
                     recommend.FIRST_SEEN_UNDER_WAY_WHY,
                     recommend.START_UNREADABLE_WHY}
    assert audit.plain_words_violations(" ".join(words)) == []
    assert recommend.not_still_upcoming("scheduled", None, None, ASKED) is None


def test_the_writer_names_each_game_it_refused(tmp_path, monkeypatch):
    conn, ids = _four(tmp_path, monkeypatch)
    counts = recommend.record_for(conn, list(ids.values()), now=ASKED)
    assert counts["recommended"] == 1 and counts["not_still_upcoming"] == 3
    named = {r["game_id"]: r["why"] for r in counts["not_still_upcoming_named"]}
    assert named == {"mlb_990381": recommend.OVER_WHY,
                     "mlb_990382": recommend.PAST_ITS_START_WHY,
                     "mlb_990383": recommend.FIRST_SEEN_UNDER_WAY_WHY}
    assert [r[0] for r in conn.execute("SELECT game_id FROM recommendations")] \
        == ["mlb_990384"]


def _released(status, kickoff_utc, under_way_utc, now):
    """The door as released: only a game marked in play refused."""
    return (recommend.BEING_PLAYED_WHY
            if (status or "").lower() in recommend.IN_PLAY_STATUSES else None)


def _page_set(monkeypatch, name, value):
    """Set `name` on the market module the PAGE imports -- the one in
    `sys.modules` now, which a blind window earlier in the session may have
    replaced (test_two_contract_claims.py's `_now`) -- and on this file's."""
    for module in {recommend, importlib.import_module("gridiron.market.recommend")}:
        monkeypatch.setattr(module, name, value)


def test_the_slate_check_names_an_entry_on_a_game_not_still_upcoming(tmp_path, monkeypatch):
    conn, ids = _four(tmp_path, monkeypatch)
    _page_set(monkeypatch, "utcnow", lambda: ASKED)
    honest = views.week(conn, "mlb", 2026, 1)
    audit.check_no_entry_for_a_game_not_still_upcoming(conn, honest, ASKED)
    _page_set(monkeypatch, "not_still_upcoming", _released)
    planted = views.week(conn, "mlb", 2026, 1)
    faults = audit.not_still_upcoming_entry_faults(conn, planted, ASKED)
    for gid in ("mlb_990381", "mlb_990382", "mlb_990383"):
        assert any(f" on {gid}:" in f for f in faults), (gid, faults)
    assert not any(" on mlb_990384:" in f for f in faults)
    with pytest.raises(audit.LawViolation, match="NOT STILL UPCOMING"):
        audit.check_no_entry_for_a_game_not_still_upcoming(conn, planted, ASKED)


def test_a_row_drawn_as_to_come_past_its_start_says_why_it_has_no_price(
        tmp_path, monkeypatch):
    """Q38's prover (2026-10-07): a game still listed 'scheduled' is drawn as
    to come -- every NFL, NBA and UFC game being played (no live poll follows
    them), one postponed, one seen under way before its listed start and set
    back by a loader. Ruling 2 leaves it unpriced, and as first built its
    price slot said "venue has not listed this yet" (and its tooltip that
    the first read comes two hours before the start) of a game the venue
    listed and that was priced that morning. It says why now; a game still
    to come keeps its price, and a prop keeps its own words."""
    conn, ids = _four(tmp_path, monkeypatch)
    _page_set(monkeypatch, "utcnow", lambda: ASKED)
    rows = {g["game_id"]: g for g in views.week(conn, "mlb", 2026, 1)["board"]["games"]}
    for gid in ("mlb_990382", "mlb_990383"):
        pick = rows[gid]["pick"]
        assert rows[gid]["state"] == "upcoming" and pick["price"] is None, gid
        assert pick["price_words"] == language.past_its_start_price_words(), gid
        assert pick["tips"]["price"] == language.past_its_start_price_tip(), gid
    to_come = rows["mlb_990384"]["pick"]
    assert to_come["price"] is not None and "¢" in to_come["price_words"]
    for words in (language.past_its_start_price_words(),
                  language.past_its_start_price_tip()):
        assert audit.plain_words_violations(words) == []
        assert audit.advice_word_faults(words) == []
    assert "venue has not listed" not in json.dumps(rows["mlb_990382"])


def test_the_day_strip_says_why_a_started_slate_has_no_price(tmp_path, monkeypatch):
    """"No venue price on this slate yet" was false of games priced before
    they began: on a slate whose every game has started the strip says why
    nothing is priced, with no fee line; with some still to come, its note is
    about those."""
    conn, ids = _four(tmp_path, monkeypatch, unread=("mlb_990384",))
    _page_set(monkeypatch, "utcnow", lambda: ASKED)
    some = views.week(conn, "mlb", 2026, 1)["today"]
    assert some["no_price_words"] == language.first_price_words(
        tasks.NEAR_START_HOURS, some_started=True)
    assert "still to come" in some["no_price_words"]
    _page_set(monkeypatch, "utcnow", lambda: "2026-09-28T02:00:00Z")
    over = views.week(conn, "mlb", 2026, 1)["today"]
    assert over["no_price_words"] == language.slate_started_words()
    assert over["fee_line"] is None
    # TRUE OF THIS SLATE (Q38's prover, 2026-10-07): two of its games are
    # still listed as to come past their listed starts -- postponed, or a
    # stale listing -- and may never have started, so the words claim no
    # start; they said "Every game on this slate has started" as first built
    assert "started" not in over["no_price_words"]
    assert "past its listed start" in over["no_price_words"]
    for words in (some["no_price_words"], over["no_price_words"]):
        assert audit.plain_words_violations(words) == []
        assert audit.advice_word_faults(words) == []


# --- the gate ----------------------------------------------------------------------

def test_the_record_check_names_an_in_play_close_or_claim_and_holds_the_seventeen(
        tmp_path, monkeypatch):
    conn, pid, _rec = _world(tmp_path)
    _read(conn, GAME, "2026-09-27T18:35:01Z", 0.50, ticker=f"T-{GAME}")
    _read(conn, GAME, "2026-09-27T19:05:01Z", 0.88, ticker=f"T-{GAME}")
    _poll(conn, monkeypatch, SEEN, mlb=_mlb(PK))
    # the closer with its door put back to the listed start closes on 88c
    monkeypatch.setattr(live, "start_of", lambda listed, under_way: db.instant(listed))
    monkeypatch.setattr(recommend, "utcnow", lambda: "2026-09-27T19:35:01Z")
    recommend.record_closing_prices(conn)
    faults = audit.reads_at_or_after_the_start_faults(conn)
    assert any("'s close" in f and "19:05:01Z" in f for f in faults), faults
    with pytest.raises(audit.LawViolation, match="CLOSE OR A CLAIM"):
        audit.check_no_close_or_claim_read_at_or_after_the_start(conn)
    # a claim numbered as one of the seventeen held, on another game, is named
    claimed = conn.execute("SELECT MAX(id) FROM at_the_line_claims").fetchone()[0]
    assert claimed <= 17
    in_play = _read(conn, GAME, "2026-09-27T19:20:00Z", 0.90)
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', ?, 'moneyline', 'home_win', NULL,"
        " 'home', 'line_less', NULL, NULL, 0.6, 0.90, 0.90, 'mid',"
        " '2026-09-27T19:20:01Z')", (pid, in_play, GAME))
    conn.commit()
    faults = audit.reads_at_or_after_the_start_faults(conn)
    assert any(f.startswith("claim ") and "19:20:00Z" in f for f in faults), faults


def test_the_seventeen_are_held_by_number_game_and_write():
    assert len(audit.IN_PLAY_CLAIMS_HELD_2026_09_07) == 17
    assert {n for n, _g, _w in audit.IN_PLAY_CLAIMS_HELD_2026_09_07} == set(range(1, 18))
    assert {w[:16] for _n, _g, w in audit.IN_PLAY_CLAIMS_HELD_2026_09_07} == {
        "2026-09-07T19:41"}


def test_no_test_leaves_a_held_clock_on_the_market_modules():
    """Q38's prover (2026-10-07): a market module built afresh while a test
    held `db.utcnow` binds the held clock, and kept it for every test after
    (`test_starts_are_instants.py`'s final-pass tests left 2026-09-05T18:59:59Z,
    on which `test_three_states.py`'s page tests passed). The suite puts the
    real clock back after every test and names what it put back."""
    import sys

    from tests import conftest

    module = importlib.import_module("gridiron.market.recommend")
    real = db.utcnow
    assert module.utcnow is real
    module.utcnow = lambda: "2026-09-05T18:59:59Z"     # as a fresh import binds it
    try:
        put_back = conftest._market_clocks_put_back()
    finally:
        held = module.utcnow
        module.utcnow = real
    assert held is real and "gridiron.market.recommend" in put_back
    assert all(getattr(m, "utcnow", real) is real for n, m in list(sys.modules.items())
               if n.startswith("gridiron.market"))
    assert conftest._market_clocks_put_back() == []


def test_the_gate_makes_both_calls():
    gate = ROOT / "tools" / "verify.py"
    step = next(node for node in ast.parse(gate.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    called = {node.attr for node in ast.walk(step)
              if isinstance(node, ast.Attribute)
              and isinstance(node.value, ast.Name) and node.value.id == "audit"}
    assert {"check_no_close_or_claim_read_at_or_after_the_start",
            "check_no_entry_for_a_game_not_still_upcoming"} <= called
