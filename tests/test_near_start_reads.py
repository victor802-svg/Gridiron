"""The near-start pass reads every open recommendation, every firing
(GRIDIRON_REPAIR item 1, 2026-09-23).

Until that date the pass read each prediction once and then excluded it, and
it never read a recommended prediction at all: every one of them had no media
line, and the pass only took predictions that did. The close was therefore
always the price the recommendation was made at -- 49 of 49 rows at 0.00c.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from gridiron import db, tasks
from gridiron.market import lines


def _stamp(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


def _world(tmp_path, *, closed=False):
    conn = db.open_db(tmp_path / "near.db")
    kickoff = _stamp(timedelta(hours=1))
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g0', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', ?, 'scheduled', '2026-09-23')", (kickoff,))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'mlb', 'g0',"
        " 'total', 'BBB at AAA', 8.5, 0.6, 'over', 'statistical', 'final',"
        " 'fs2', '{}', 'x')", (_stamp(timedelta(hours=-5)),))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    # NO MEDIA LINE: the open snapshot carries no implied probability, which
    # is the shape of all 55 recommended predictions on 2026-09-23.
    conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
        " implied_prob, kind) VALUES (?, ?, 'test', NULL, 'open_at_predict')",
        (pid, _stamp(timedelta(hours=-5))))
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc, closed_utc) VALUES (?, 'mlb', 'g0', 'total', 'yes', 0.6,"
        " 0.46, 10.0, 'flat', 1.0, 0, ?, ?)",
        (pid, _stamp(timedelta(hours=-4)),
         _stamp(timedelta(hours=-3)) if closed else None))
    conn.commit()
    return conn, pid


def _watch(monkeypatch):
    """Record what the pass hands the venue read, instead of reading it.

    THE MODULE IS LOOKED UP NOW, not at import. A blind window drops the market
    package from `sys.modules` (`blind.forget_market_module`), so a test that
    ran one earlier in the session leaves this file holding a stale `lines`
    while the pass imports a fresh one -- and a patch on the stale one is a
    patch on nothing. It passed alone and failed in the suite the first time.
    """
    import importlib

    current = importlib.import_module(lines.__name__)
    seen: list[list[int]] = []

    def read(conn, ids):
        seen.append(list(ids))
        return {"quotes": 0, "claims": 0}

    monkeypatch.setattr(current, "refresh_venue_ladder", read)
    return seen


def test_an_open_recommendation_is_read_on_every_firing(tmp_path, monkeypatch):
    conn, pid = _world(tmp_path)
    seen = _watch(monkeypatch)
    first = tasks._near_start_snapshots(conn)
    second = tasks._near_start_snapshots(conn)
    # read both times: the close is the LAST read before the start, so a pass
    # that reads once and stops can never find it
    assert seen == [[pid], [pid]]
    assert first["near_start_recommendations"] == 1
    assert second["near_start_due"] == 1


def test_a_closed_recommendation_is_not_read(tmp_path, monkeypatch):
    conn, _ = _world(tmp_path, closed=True)
    seen = _watch(monkeypatch)
    tasks._near_start_snapshots(conn)
    assert seen == []


def test_the_once_then_exclude_is_retired_by_name():
    """It may not come back quietly, and the note saying why it went stays."""
    source = Path(tasks.__file__).read_text(encoding="utf-8")
    assert "RETIRED 2026-09-23 (GRIDIRON_REPAIR item 1): THE ONCE-THEN-EXCLUDE" in source
    body = source[source.index("def _near_start_snapshots"):
                  source.index("def _plus_hours")]
    code = "\n".join(line for line in body.splitlines()
                     if not line.strip().startswith("#"))
    assert "n.kind = 'near_start'" not in code, \
        "the once-then-exclude is back in the near-start selection"


# ---------------------------------------------------------------------------
# THE CLOSE WINDOW (the operator's ruling of 2026-09-30, GRIDIRON_REPAIR
# item 1): "The near-start run keeps every game until its start, so the close
# is the last read before the start." Measured first, on one verified copy of
# the record (30 September; FOLLOWUPS, "The close window"): 14 of the 19
# measured baseball closes since item 1 were the read 35 minutes out, because
# the firing five minutes before each game's listed start left it out -- the
# pass kept a recommendation only while its game's status said 'scheduled' or
# 'pre', and baseball's feed calls a game in its warm-up 'Live', which the
# poller stores as 'in'. NFL 12 of 12 and NCAAF 7 of 8 closed on the last
# firing before the start.
#
# THE CLOCK IS HELD in every test below (`_hold`): each firing is an instant
# written out, never a reading of the machine's clock, and nothing waits.
# ---------------------------------------------------------------------------

import importlib  # noqa: E402

import pytest  # noqa: E402

START = "2026-09-27T19:10:00Z"
SCORES = {"scheduled": (None, None), "in": (0, 0), "final": (3, 2)}


def _hold(monkeypatch, now: str) -> None:
    """Hold every clock the pass, the claim writer and the closer read at
    `now`: `db.utcnow`, and the name each market module imported from it --
    looked up now, as `_watch` looks up `lines`, because a blind window drops
    the market package from `sys.modules`."""
    monkeypatch.setattr(db, "utcnow", lambda: now)
    for name in ("gridiron.market.recommend", "gridiron.market.at_the_line"):
        monkeypatch.setattr(importlib.import_module(name), "utcnow",
                            lambda: now)


def _game(conn, gid, *, start=START, status="scheduled", sport="mlb"):
    home, away = SCORES[status]
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES (?, ?, 2026, 1, 'R', 'AAA', 'BBB', ?, ?, '2026-09-27', ?, ?)",
        (gid, sport, start, status, home, away))


def _forecast(conn, gid, *, media=None, market="total", sport="mlb"):
    subject, line, side = (("BBB at AAA", 8.5, "over") if market == "total"
                           else ("AAA", None, "win"))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-27T12:00:00Z', ?, ?, ?, ?, ?, 0.6, ?, 'statistical',"
        " 'final', 'fs2', '{\"coverage\": 1.0}', 'x')",
        (sport, gid, market, subject, line, side))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
        " implied_prob, kind) VALUES (?, '2026-09-27T12:00:05Z', 'test', ?,"
        " 'open_at_predict')", (pid, media))
    return pid


def _recommend(conn, gid, pid, *, market="total", sport="mlb",
               stamp="2026-09-27T13:00:00Z"):
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc) VALUES (?, ?, ?, ?, 'yes', 0.6, 0.46, 10.0,"
        " 'flat', 1.0, 0, ?)", (pid, sport, gid, market, stamp))
    return conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]


@pytest.mark.parametrize("status", ["scheduled", "in", "final"])
def test_a_game_is_read_until_its_listed_start_whatever_its_status_says(
        tmp_path, monkeypatch, status):
    """Five minutes before the listed start a recommendation is read whether
    the record says its game is scheduled, under way (baseball's warm-up) or
    over; until 2026-09-30 'in' and 'final' were left out. A forecast read
    while its game is marked under way or over is named in the payload with
    that status, since the record keeps no history of a game's status."""
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", status=status)
    pid = _forecast(conn, "g1")
    _recommend(conn, "g1", pid)
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:05:01Z")
    seen = _watch(monkeypatch)
    got = tasks._near_start_snapshots(conn)
    assert seen == [[pid]]
    assert got["near_start_recommendations"] == 1
    named = got["near_start_marked_under_way"]
    if status == "scheduled":
        assert named == []
    else:
        assert named == [{"prediction_id": pid, "game_id": "g1",
                          "status": status, "listed_start": START}]


def test_a_game_past_its_listed_start_is_never_read_whatever_its_status_says(
        tmp_path, monkeypatch):
    """At the listed start and after it, never -- a game the record still
    calls 'scheduled' included -- so every read that could be the close is a
    read before the start."""
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", status="scheduled")
    pid = _forecast(conn, "g1", media=0.52)
    _recommend(conn, "g1", pid)
    conn.commit()
    for now in ("2026-09-27T19:10:00Z", "2026-09-27T19:10:01Z"):
        got = tasks._near_start_selection(conn, now)
        assert got["recs"] == [] and got["drift"] == [], now
        assert tasks._games_starting_within(conn, now) == 0, now
    got = tasks._near_start_selection(conn, "2026-09-27T19:09:59Z")
    assert got["recs"] == [pid] and got["drift"] == [pid]
    # and no further out than the window: two hours before the start, in;
    # a second more, out
    assert tasks._near_start_selection(conn, "2026-09-27T17:10:00Z")["recs"] == [pid]
    assert tasks._near_start_selection(conn, "2026-09-27T17:09:59Z")["recs"] == []


def test_a_start_stored_to_the_minute_is_read_as_an_instant(tmp_path):
    """UFC stores its starts to the minute. Compared as text, "...T19:10Z" is
    AFTER "...T19:10:30Z" (':' is below 'Z'), so a firing thirty seconds
    after the start took the game for one still ahead of it."""
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", start="2026-10-04T19:10Z")
    pid = _forecast(conn, "g1", media=0.52)
    _recommend(conn, "g1", pid)
    conn.commit()
    after = "2026-10-04T19:10:30Z"
    assert "2026-10-04T19:10Z" > after, "the text comparison it replaces"
    got = tasks._near_start_selection(conn, after)
    assert got["recs"] == [] and got["drift"] == []
    assert tasks._games_starting_within(conn, after) == 0
    before = tasks._near_start_selection(conn, "2026-10-04T19:09:30Z")
    assert before["recs"] == [pid] and before["drift"] == [pid]
    assert tasks._games_starting_within(conn, "2026-10-04T19:09:30Z") == 1


def test_a_withdrawn_recommendation_is_still_not_read(tmp_path):
    """The window moved; the door did not (ruling 1, 2026-09-24)."""
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", status="in")
    pid = _forecast(conn, "g1")
    rec = _recommend(conn, "g1", pid)
    conn.execute(
        "INSERT INTO recommendation_voids (recommendation_id, voided_utc,"
        " reason) VALUES (?, '2026-09-27T14:00:00Z',"
        " 'withdrawn in a test world, by hand')", (rec,))
    conn.commit()
    assert tasks._near_start_selection(conn, "2026-09-27T19:05:01Z")["recs"] == []


def test_a_drift_row_of_a_game_marked_under_way_gets_its_look_before_the_start(
        tmp_path, monkeypatch):
    """The drift row's one media look is taken until the listed start too:
    until 2026-09-30 a drift row was selected only while its game said
    'scheduled'."""
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", status="in")
    pid = _forecast(conn, "g1", media=0.52)
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:05:01Z")
    seen = _watch(monkeypatch)
    current = importlib.import_module(lines.__name__)
    looked: list[int] = []
    monkeypatch.setattr(current, "refresh_quotes", lambda c, ids, ttl=None: 0)
    monkeypatch.setattr(current, "snapshot_prediction",
                        lambda c, p, kind: looked.append(p))
    got = tasks._near_start_snapshots(conn)
    assert seen == [[pid]] and looked == [pid]
    assert got["near_start_taken"] == 1
    assert got["near_start_marked_under_way"][0]["status"] == "in"


def test_the_noop_line_counts_a_game_marked_under_way_before_its_start(
        tmp_path, monkeypatch):
    """The words of a firing that read nothing count the window the
    selection reads: until 2026-09-30 they counted games still 'scheduled'."""
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", status="in")
    _forecast(conn, "g1")                      # no media line, no recommendation
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:05:01Z")
    _watch(monkeypatch)
    result, detail, counts = tasks._run_near_start(conn)
    assert result == "noop" and counts["near_start_games_in_window"] == 1
    assert detail.startswith("1 game starts within the next 2 hours")


def test_the_firing_writes_its_claim_on_a_game_in_its_warm_up(
        tmp_path, monkeypatch):
    """EVERY CLAIM IT READS: the firing five minutes out on a game marked
    'in' reads the venue AND the claim writer claims the read (a moneyline,
    whose claim is the blind number itself). Until 2026-09-30 the pass left
    the game out, and the claim writer refused a game whose status said 'in'
    whole. Only the venue's answer is a stub: the near-start reader and the
    claim writer are the shipped ones."""
    from gridiron.market import at_the_line

    conn = db.open_db(tmp_path / "near.db")
    at_the_line.ensure_read_kind(conn)
    _game(conn, "g1", status="in")
    pid = _forecast(conn, "g1", market="moneyline")
    _recommend(conn, "g1", pid, market="moneyline")
    conn.commit()
    now = "2026-09-27T19:05:01Z"
    _hold(monkeypatch, now)
    kalshi = importlib.import_module("gridiron.market.kalshi")

    def answer(c, ids, **kwargs):
        c.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " last_price, volume, fetched_utc, read_kind) VALUES (?, 'TM',"
            " 'E', 'mlb', 'g1', 'moneyline', 'home_win', NULL, 'home', 0.54,"
            " 0.56, NULL, 900, ?, 'near_start')", (at_the_line.VENUE, now))
        c.commit()
        return {"quotes": 1}

    monkeypatch.setattr(kalshi, "capture_for_predictions", answer)
    got = tasks._near_start_snapshots(conn)
    assert got["venue_near_start"] == 1 and got["at_the_line_claims"] == 1
    claim = conn.execute("SELECT created_utc, venue_implied FROM"
                         " at_the_line_claims WHERE prediction_id = ?",
                         (pid,)).fetchone()
    assert claim["created_utc"] == now
    assert claim["venue_implied"] == pytest.approx(0.55)


def _venue(monkeypatch, prices: dict[str, float]):
    """A venue that answers each firing with the price `prices` holds for
    its instant, as a near-start read of the recommendation's own contract
    ('T8'). What the pass asks for is recorded; nothing leaves the machine."""
    current = importlib.import_module(lines.__name__)
    asked: list[tuple[str, list[int]]] = []

    def read(c, ids):
        now = db.utcnow()
        asked.append((now, list(ids)))
        price = prices.get(now)
        for pid in ids if price is not None else ():
            c.execute(
                "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
                " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
                " last_price, volume, fetched_utc, read_kind)"
                " SELECT 'kalshi', 'T8', 'E', 'mlb', game_id, 'total', 'total',"
                " 8.5, 'over', ?, ?, NULL, 900, ?, 'near_start'"
                "  FROM predictions WHERE id = ?",
                (price - 0.01, price + 0.01, now, pid))
        c.commit()
        return {"quotes": len(ids) if price is not None else 0, "claims": 0}

    monkeypatch.setattr(current, "refresh_venue_ladder", read)
    return asked


def _priced(conn, *, start=START, status="scheduled"):
    """One recommendation priced off contract 'T8' at 46c, that morning."""
    _game(conn, "g1", start=start, status=status)
    pid = _forecast(conn, "g1")
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
        " volume, fetched_utc, read_kind) VALUES ('kalshi', 'T8', 'E', 'mlb',"
        " 'g1', 'total', 'total', 8.5, 'over', 0.45, 0.47, NULL, 900,"
        " '2026-09-27T12:30:00Z', 'near_start')")
    quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
        " sport, game_id, market, quantity, line, side, shape, dist_mean,"
        " dist_sd, model_prob, venue_price, venue_implied, price_basis,"
        " created_utc) VALUES (?, ?, 'kalshi', 'mlb', 'g1', 'total', 'total',"
        " 8.5, 'over', 'rung_matched', NULL, NULL, 0.6, 0.46, 0.46, 'mid',"
        " '2026-09-27T12:31:00Z')", (pid, quote))
    rec = _recommend(conn, "g1", pid)
    conn.commit()
    return pid, rec


def _close(conn, rec):
    return conn.execute(
        "SELECT r.close_price, r.clv_cents, c.minutes_before_start,"
        "       q.fetched_utc"
        "  FROM recommendations r"
        "  JOIN recommendation_closes c ON c.recommendation_id = r.id"
        "  LEFT JOIN venue_quotes q ON q.id = c.close_quote_id"
        " WHERE r.id = ?", (rec,)).fetchone()


def test_the_close_is_the_read_five_minutes_out_on_a_game_in_its_warm_up(
        tmp_path, monkeypatch):
    """END TO END, the fourteen's shape: a baseball recommendation priced that
    morning, read at the firing 35 minutes out, then marked 'in' (its
    warm-up) before the firing five minutes out. The close is the read five
    minutes out -- the last read before the start. Until 2026-09-30 the
    second firing left the game out and the close was the read 35 minutes
    out."""
    conn = db.open_db(tmp_path / "near.db")
    pid, rec = _priced(conn)
    asked = _venue(monkeypatch, {"2026-09-27T18:35:01Z": 0.50,
                                 "2026-09-27T19:05:01Z": 0.55})
    _hold(monkeypatch, "2026-09-27T18:35:01Z")
    tasks._near_start_snapshots(conn)
    conn.execute("UPDATE games SET status = 'in', home_score = 0,"
                 " away_score = 0 WHERE id = 'g1'")   # the warm-up, 'Live'
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:05:01Z")
    fired = tasks._near_start_snapshots(conn)
    _hold(monkeypatch, "2026-09-27T19:35:01Z")
    closed = tasks._near_start_snapshots(conn)
    assert asked == [("2026-09-27T18:35:01Z", [pid]),
                     ("2026-09-27T19:05:01Z", [pid])]
    assert fired["near_start_marked_under_way"] == [
        {"prediction_id": pid, "game_id": "g1", "status": "in",
         "listed_start": START}]
    assert closed["closing_prices"] == 1
    row = _close(conn, rec)
    assert row["fetched_utc"] == "2026-09-27T19:05:01Z"
    assert row["close_price"] == pytest.approx(0.55)
    assert row["clv_cents"] == pytest.approx(9.0)
    assert row["minutes_before_start"] == pytest.approx(5.0)


def test_the_close_is_the_last_read_before_the_start_when_later_ones_exist(
        tmp_path, monkeypatch):
    """The rule itself, on reads the record already holds: of the reads 35
    and 5 minutes out and one a second after the start, the close is the
    read five minutes out -- never an earlier one while a later one before
    the start exists, and never one at or after the start."""
    from gridiron.market import recommend

    conn = db.open_db(tmp_path / "near.db")
    pid, rec = _priced(conn)
    for stamp, bid in (("2026-09-27T18:35:01Z", 0.49),
                       ("2026-09-27T19:05:01Z", 0.54),
                       ("2026-09-27T19:10:00Z", 0.88),
                       ("2026-09-27T19:10:01Z", 0.89)):
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " last_price, volume, fetched_utc, read_kind) VALUES ('kalshi',"
            " 'T8', 'E', 'mlb', 'g1', 'total', 'total', 8.5, 'over', ?, ?,"
            " NULL, 900, ?, 'near_start')", (bid, bid + 0.02, stamp))
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:35:01Z")
    current = importlib.import_module(recommend.__name__)
    assert current.record_closing_prices(conn)["closed"] == 1
    row = _close(conn, rec)
    assert row["fetched_utc"] == "2026-09-27T19:05:01Z"
    assert row["close_price"] == pytest.approx(0.55)
    assert row["minutes_before_start"] == pytest.approx(5.0)


def _minute_world(conn):
    """A start stored to the minute, and three reads of the recommendation's
    own contract: a minute before it, and thirty seconds after it."""
    pid, rec = _priced(conn, start="2026-10-04T02:00Z")
    stamps = {}
    for name, stamp, bid in (("before", "2026-10-04T01:59:00Z", 0.49),
                             ("after", "2026-10-04T02:00:30Z", 0.89)):
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " last_price, volume, fetched_utc, read_kind) VALUES ('kalshi',"
            " 'T8', 'E', 'mlb', 'g1', 'total', 'total', 8.5, 'over', ?, ?,"
            " NULL, 900, ?, 'near_start')", (bid, bid + 0.02, stamp))
        stamps[name] = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.commit()
    return rec, stamps


def test_a_read_in_the_starts_own_minute_after_it_is_never_the_close(
        tmp_path, monkeypatch):
    """A start stored to the minute is an instant: the read thirty seconds
    after it -- which sorted before it as text -- is not the close; the last
    read before it is, one minute out, and the minutes are worked out from
    the instant (a start without seconds raised in `_minutes_between`, which
    would have stopped the closer and every near-start firing with it)."""
    from gridiron.market import recommend

    conn = db.open_db(tmp_path / "near.db")
    rec, stamps = _minute_world(conn)
    _hold(monkeypatch, "2026-10-04T02:00:30Z")
    current = importlib.import_module(recommend.__name__)
    got = current.record_closing_prices(conn)
    assert got == {"closed": 1, "unmeasured": 0, "still_open": 0}, \
        "thirty seconds after a start stored to the minute, it has started"
    row = conn.execute(
        "SELECT close_quote_id, close_price, minutes_before_start"
        "  FROM recommendation_closes WHERE recommendation_id = ?",
        (rec,)).fetchone()
    assert row["close_quote_id"] == stamps["before"]
    assert row["close_price"] == pytest.approx(0.50)
    assert row["minutes_before_start"] == pytest.approx(1.0)


def test_the_closer_waits_for_a_start_stored_to_the_minute(tmp_path, monkeypatch):
    from gridiron.market import recommend

    conn = db.open_db(tmp_path / "near.db")
    _minute_world(conn)
    _hold(monkeypatch, "2026-10-04T01:59:59Z")
    current = importlib.import_module(recommend.__name__)
    assert current.record_closing_prices(conn)["still_open"] == 1


def test_an_instant_is_read_to_the_second_or_to_the_minute_and_never_guessed():
    first = db.instant("2026-09-27T19:10:00Z")
    assert first == db.instant("2026-09-27T19:10Z")
    assert first.tzinfo is not None and first.utcoffset().total_seconds() == 0
    assert db.instant("2026-09-27T19:10:30Z") > db.instant("2026-09-27T19:10Z")
    assert db.instant(None) is None and db.instant("") is None
    for bad in ("tomorrow", "2026-09-27 19:10", "2026-09-27T19:10:00"):
        with pytest.raises(ValueError, match="instant"):
            db.instant(bad)


# ---------------------------------------------------------------------------
# A START NOBODY CAN READ STOPS NOTHING BUT ITSELF (2026-09-30, item 1's
# prover). As first built, one listed start `db.instant` refuses -- a feed
# that drops its zone, a date with no time -- on any game a drift row or an
# open recommendation sits on raised in the selection, before the closer, and
# stopped every firing for every game: the left-out the ruling removes, made
# total. The games table has no rule on the column's form, and the college
# loader can store an empty start. Such a forecast is not read and is named;
# every other game is read; the closer holds it open; no claim is written.
# ---------------------------------------------------------------------------

UNREADABLE = ("2026-09-27T19:40:00",     # a feed that dropped its zone
              "2026-09-27")              # a date with no time


def test_a_start_nobody_can_read_stops_no_other_game(tmp_path, monkeypatch):
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", status="in")             # its warm-up, five minutes out
    warm = _forecast(conn, "g1")
    _recommend(conn, "g1", warm)
    named = {}
    for n, start in enumerate(UNREADABLE, 2):
        _game(conn, f"g{n}", start=start)
        pid = _forecast(conn, f"g{n}", media=0.52)
        _recommend(conn, f"g{n}", pid)
        named[pid] = start
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:05:01Z")
    seen = _watch(monkeypatch)
    result, detail, counts = tasks._run_near_start(conn)
    assert seen == [[warm]], "every other game is read, the warm-up included"
    assert {row["prediction_id"]: row["listed_start"]
            for row in counts["near_start_unreadable_start"]} == named
    assert "2 forecasts not read: the listed start of 2 games cannot be " \
           "read as an instant" in detail, detail
    assert result == "ok"


def test_a_start_nobody_can_read_is_named_on_a_firing_that_reads_nothing(
        tmp_path, monkeypatch):
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1", start=UNREADABLE[0])
    pid = _forecast(conn, "g1")
    _recommend(conn, "g1", pid)
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:05:01Z")
    seen = _watch(monkeypatch)
    result, detail, counts = tasks._run_near_start(conn)
    assert seen == [] and result == "noop"
    assert counts["near_start_unreadable_start"] == [
        {"prediction_id": pid, "game_id": "g1",
         "listed_start": UNREADABLE[0]}]
    assert detail.endswith("; 1 forecast not read: the listed start of 1 "
                           "game cannot be read as an instant"), detail


def test_the_closer_holds_open_a_start_nobody_can_read(tmp_path, monkeypatch):
    """Whether such a start has passed cannot be told: it is held open with
    the starts still ahead, never closed on a guess, and stops no other
    close."""
    from gridiron.market import recommend

    conn = db.open_db(tmp_path / "near.db")
    pid, rec = _priced(conn)                    # g1, listed 19:10:00Z
    _game(conn, "g2", start=UNREADABLE[0])
    held = _recommend(conn, "g2", _forecast(conn, "g2"))
    conn.commit()
    _hold(monkeypatch, "2026-09-27T19:35:01Z")
    current = importlib.import_module(recommend.__name__)
    got = current.record_closing_prices(conn)
    assert got == {"closed": 0, "unmeasured": 1, "still_open": 1}
    shut = {r["id"]: r["closed_utc"] for r in conn.execute(
        "SELECT id, closed_utc FROM recommendations")}
    assert shut[rec] == "2026-09-27T19:35:01Z" and shut[held] is None


def test_the_noop_count_skips_a_start_it_cannot_read_or_an_empty_one(tmp_path):
    """The college loader stores an empty start for an event with no date;
    as first built the count raised on it (`None` against an instant) and on
    an unreadable one."""
    conn = db.open_db(tmp_path / "near.db")
    _game(conn, "g1")
    for n, start in enumerate(UNREADABLE + ("",), 2):
        _game(conn, f"g{n}", start=start)
    conn.commit()
    assert tasks._games_starting_within(conn, "2026-09-27T19:05:01Z") == 1
