"""The closing line counts from the day it was repaired, and is not read before
its first clean read (the operator's ruling 8 of 2026-09-23, GRIDIRON_REPAIR
item 8, built 2026-09-27):

    "READINESS: two BROKEN findings recorded; the observation window restarts
    on the date item 1 ships; the first clean CLV read is 21 days after that,
    not before."
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from gridiron import audit, calibration, config, db, language
from gridiron.priced import coverage

EVE = "2026-10-14T23:59:59Z"
ON_THE_DAY = "2026-10-15T00:00:00Z"


def _closes(conn, *, market: str, count: int, day: str, price: float,
            close: float, tag: str, first: str | None = None) -> None:
    """`count` MLB recommendations on `market`, each on its own game, each
    written on `day`, priced from a near-start read of its own contract and
    closed on a later one before the start, with its account written as the
    closer writes it.

    `first`, when given, is the instant the first recommendation is written
    (the prover, 2026-09-27), the rest two minutes apart: its forecast is 32
    minutes earlier, its close read 88 minutes later and its close 218."""
    base = (datetime.fromisoformat(first.replace("Z", "+00:00"))
            - timedelta(minutes=32) if first else
            datetime.fromisoformat(day + "T01:00:00+00:00"))
    quantity, line, yes = (("home_margin", -1.5, "home") if market == "spread"
                           else ("total", 8.5, "over"))

    def at(t: datetime, minutes: int) -> str:
        return (t + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for i in range(count):
        gid = f"{tag}-{market}-{i}"
        t0 = base + timedelta(minutes=2 * i)
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " 'MIA', 'NYM', ?, 'scheduled', ?)", (gid, at(t0, 240), day))
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES (?, 'mlb', ?,"
            " ?, 'NYM at MIA', ?, 0.6, ?, 'statistical', 'final', 'fs2', '{}',"
            " 'x')", (at(t0, 0), gid, market, line,
                      "cover" if market == "spread" else "over"))
        pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
        quotes = []
        for minutes, mid in ((30, price), (120, close)):
            conn.execute(
                "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
                " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
                " volume, fetched_utc, read_kind) VALUES ('kalshi', ?, 'E',"
                " 'mlb', ?, ?, ?, ?, ?, ?, ?, 900, ?, 'near_start')",
                (f"T-{gid}", gid, market, quantity, line, yes,
                 round(mid - 0.01, 4), round(mid + 0.01, 4), at(t0, minutes)))
            quotes.append(conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0])
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape, dist_mean,"
            " dist_sd, model_prob, venue_price, venue_implied, price_basis,"
            " created_utc) VALUES (?, ?, 'kalshi', 'mlb', ?, ?, ?, ?, ?,"
            " 'rung_matched', NULL, NULL, 0.6, ?, ?, 'mid', ?)",
            (pid, quotes[0], gid, market, quantity, line, yes, price, price,
             at(t0, 31)))
        clv = round((close - price) * 100, 2)
        conn.execute(
            "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
            " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
            " created_utc, close_price, clv_cents, closed_utc) VALUES (?, 'mlb',"
            " ?, ?, 'yes', 0.6, ?, 5.0, 'flat', 1.0, 0, ?, ?, ?, ?)",
            (pid, gid, market, price, at(t0, 32), close, clv, at(t0, 250)))
        rec = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
        conn.execute(
            "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
            " pricing_quote_id, close_quote_id, close_price, clv_cents,"
            " minutes_before_start, restated, reason) VALUES (?, ?, ?, ?, ?, ?,"
            " 120.0, 0, 'the last near-start read of its own contract')",
            (rec, at(t0, 250), quotes[0], quotes[1], close, clv))
    conn.commit()


@pytest.fixture
def world(tmp_path):
    """Fifty closes at +3.0c on the spread and fifty at -4.0c on the total,
    written the day after the repair, and ten at +9.0c on the spread written
    the day before it."""
    conn = db.open_db(tmp_path / "window.db")
    _closes(conn, market="spread", count=50, day="2026-09-25", price=0.46,
            close=0.49, tag="in")
    _closes(conn, market="total", count=50, day="2026-09-25", price=0.50,
            close=0.46, tag="in")
    _closes(conn, market="spread", count=10, day="2026-09-23", price=0.40,
            close=0.49, tag="before")
    yield conn
    conn.close()


def test_the_dates_are_the_ruling_s():
    """Item 1 (commit 23cf89b) reached the released main checkout at
    2026-09-24T06:49:12Z -- that checkout's reflog, the fast-forward to
    4941fa1 -- so the window starts on 24 September, UTC, and the first clean
    read is 21 days after it. No threshold moves with it."""
    assert config.CLOSING_LINE_WINDOW_START == "2026-09-24"
    assert config.CLOSING_LINE_FIRST_READ_AFTER_DAYS == 21
    assert (date.fromisoformat(config.CLOSING_LINE_FIRST_CLEAN_READ)
            - date.fromisoformat(config.CLOSING_LINE_WINDOW_START)
            == timedelta(days=config.CLOSING_LINE_FIRST_READ_AFTER_DAYS))
    assert config.CLOSING_LINE_FIRST_CLEAN_READ == "2026-10-15"
    # A THRESHOLD IS NEVER MOVED TO PRODUCE A PASS (docs/READINESS.md)
    assert calibration.MIN_RECOMMENDATIONS_FOR_CLV == 50
    assert coverage.KILL_AFTER == 50
    # and the first window's start stays in the payload
    assert calibration.CLV_DECLARED == "2026-09-07T00:00:00Z"


def test_the_door_opens_on_the_first_clean_read_and_not_a_second_before():
    assert calibration.closing_line_window(EVE)["open"] is False
    assert calibration.closing_line_window(ON_THE_DAY)["open"] is True
    assert calibration.closing_line_window("2026-09-24T00:00:00Z")["open"] is False
    # the UTC date of the instant, whatever the machine's own clock says
    assert calibration.closing_line_window("2026-10-14T23:30:00Z")["open"] is False
    days = calibration.closing_line_window("2026-09-27T12:00:00Z")["days"]
    assert (days["done"], days["needed"], days["n"]) == (3, 21, 3)
    assert "Thursday 15 October" in days["note"]


def test_the_closing_line_waits_for_its_first_clean_read(world):
    report = calibration.clv_report(world, sport="mlb", now=EVE)
    assert report["window"]["open"] is False
    assert report["window"]["first_clean_read"] == "2026-10-15"
    by = {e["market"]: e for e in report["markets"]}
    for market in ("spread", "total"):
        entry = by[market]
        # THE COUNT, WITH ITS N: how many there are is not a verdict on them
        assert entry["n"] == 50
        assert entry["renderable"] is False
        assert entry["mean_cents"] is None and entry["beat_the_close"] is None
        assert "finding" not in entry
        assert "the first clean read is Thursday 15 October" in entry["words"]
        assert "nothing is claimed before it" in entry["words"]
        assert "¢" not in entry["words"] and "%" not in entry["words"]
    calibration.assert_every_figure_has_n(report)
    assert coverage.stopped(world, "mlb", now=EVE) == {}

    # AND ON THE DAY ITSELF, the verdict of each sign and the kill arrive
    report = calibration.clv_report(world, sport="mlb", now=ON_THE_DAY)
    by = {e["market"]: e for e in report["markets"]}
    assert by["spread"]["renderable"] and by["spread"]["mean_cents"] == 3.0
    assert by["spread"]["beat_the_close"] == 1.0
    assert "+3.0¢" in by["spread"]["words"]
    assert "BUYING RICH" in by["total"]["finding"]
    assert "total" in coverage.stopped(world, "mlb", now=ON_THE_DAY)


def test_a_close_from_before_the_window_is_named_beside_and_never_counted(world):
    for now in (EVE, ON_THE_DAY):
        report = calibration.clv_report(world, sport="mlb", now=now)
        spread = next(e for e in report["markets"] if e["market"] == "spread")
        assert spread["n"] == 50 and spread["before_window"] == 10
        assert report["n"] == 100 and report["before_window"] == 10
        assert ("10 more were written before Thursday 24 September, when the "
                "count started again, and are not counted") in spread["words"]
    # on the day, the mean is the fifty's +3.0c, never the sixty's +3.9c
    assert spread["mean_cents"] == 3.0
    # the withdrawn recount counts every measured close, in the count or
    # before the window, and agrees
    assert audit.withdrawn_counted_faults(world, report) == []
    # a report that dropped the ten altogether would be caught by it
    dropped = dict(report, before_window=0)
    assert audit.withdrawn_counted_faults(world, dropped)


def test_the_window_opens_at_midnight_utc_and_counts_when_each_was_written(
        tmp_path):
    """THE BOUNDARY AND THE READING TAKEN (the prover, 2026-09-27). The window
    opens at 00:00:00Z on 24 September, its first second included, and a close
    counts by when its RECOMMENDATION was written. Ten written in the minutes
    before midnight and closed after it -- measured by a read taken after it
    -- are named beside the count; ten written from midnight are the count.
    Until this test, a window counted by when the close was written, one
    opened at item 1's instant (06:49:12Z) or on the operator's clock the day
    before (07:00Z on the 23rd), and one that left out the first second each
    passed every test and planting: their worlds sat a day either side."""
    conn = db.open_db(tmp_path / "edge.db")
    _closes(conn, market="spread", count=10, day="2026-09-23", price=0.40,
            close=0.49, tag="eve", first="2026-09-23T23:41:00Z")
    _closes(conn, market="spread", count=10, day="2026-09-24", price=0.46,
            close=0.49, tag="day", first="2026-09-24T00:00:00Z")
    start = config.CLOSING_LINE_WINDOW_START + "T00:00:00Z"
    # THE WORLD IS WHAT IT SAYS: every close written, and read, after the
    # window opened; ten recommendations written before it, the first of the
    # other ten at its first second.
    rows = conn.execute(
        "SELECT r.created_utc, c.written_utc, q.fetched_utc"
        "  FROM recommendations r"
        "  JOIN recommendation_closes c ON c.recommendation_id = r.id"
        "  JOIN venue_quotes q ON q.id = c.close_quote_id").fetchall()
    assert len(rows) == 20
    assert all(r["written_utc"] > start and r["fetched_utc"] > start
               for r in rows)
    assert sum(1 for r in rows if r["created_utc"] < start) == 10
    assert min(r["created_utc"] for r in rows if r["created_utc"] >= start) \
        == start

    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    spread = report["markets"][0]
    assert spread["market"] == "spread"
    assert spread["n"] == 10 and spread["before_window"] == 10
    assert spread["mean_cents"] == 3.0 and spread["beat_the_close"] == 1.0
    assert ("10 more were written before Thursday 24 September, when the "
            "count started again, and are not counted") in spread["words"]
    assert audit.withdrawn_counted_faults(conn, report) == []
    conn.close()


def test_the_record_page_says_when_the_closing_line_may_be_read(world):
    payload = calibration.scorecard(world, sport="mlb")
    line = payload["closing_line"]
    since = line["window_line"]
    assert since["label"] == "Since the repair" and since["n"] == line["n"]
    assert "Thursday 24 September" in since["words"]
    # read today (before 15 October) or after it, the sentence names the day
    assert "Thursday 15 October" in since["words"]
    # the kill criterion beside it read the same clock
    stopped = {s["market"] for s in payload["coverage"]["stopped"]}
    assert (("total" in stopped) == line["window"]["open"])
    audit.check_no_withdrawn_recommendation_counted(world, line)


def test_a_sport_with_nothing_closed_still_says_the_date(tmp_path):
    conn = db.open_db(tmp_path / "empty.db")
    report = calibration.clv_report(conn, sport="ufc", now=EVE)
    assert report["markets"] == [] and report["n"] == 0
    assert report["window_line"]["n"] == 0
    assert "Thursday 15 October" in report["window_line"]["words"]
    conn.close()


def test_the_words_are_plain_and_tip_nothing():
    for words in (
            language.clv_line(12, None, None, 50, since="2026-09-24",
                              first_read="2026-10-15", unmeasured=28,
                              restated=23, before_window=1),
            language.clv_line(54, None, None, 50, since="2026-09-24",
                              first_read="2026-10-15"),
            language.clv_line(54, 1.2, 0.6, 50, since="2026-09-24",
                              before_window=3),
            language.closing_line_window_line("2026-09-24", "2026-10-15", 13,
                                              verdict_open=False),
            language.closing_line_window_line("2026-09-24", "2026-10-15", 1,
                                              verdict_open=True)):
        assert audit.plain_words_violations(words) == [], words
        assert audit.advice_word_faults(words) == [], words
    # the gap in the sentence is the dates' own, never a second number
    assert "21 days after the repair" in language.closing_line_window_line(
        "2026-09-24", "2026-10-15", 0, verdict_open=False)
    assert "1 recommendation priced" in language.closing_line_window_line(
        "2026-09-24", "2026-10-15", 1, verdict_open=True)
