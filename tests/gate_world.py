"""A test world's market past B.5's gate (operator ruling B, 2026-10-05; built
2026-10-07).

"5. Kalshi game markets (spreads, moneylines, totals) stay on the board with
their numbers, but none carries a pick badge, and none feeds a combo
proposal, until its market passes its gate." The brief's reading: the gate
is "a market's at-the-line record's 100 settled comparisons, per
forecaster, on the distinct-bet key, after A.2's exclusion".

A world built to test what a PICK looks like -- its outline, its size, its
headline, a combo of two -- needs its market past that gate, as MLB
moneyline is on the record (107 and 108 on 6 October). This writes the
hundred: one finished game in a past season each, a forecast of it written
before it, a near-start read of the venue's contract at the line the
forecast was asked, and one claim off that one contract, settled -- one
distinct bet each, on one contract, none voided, every row through the
schema's own rules. Nothing else in the world moves: the forecasts are not
resolved, so no blind count, gate or curve counts them, and they sit in a
season no slate the tests build reads.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: The market's proposition, as the claim and the quote store it.
_SHAPES = {
    "spread": ("home_margin", -1.5, "home", "cover"),
    "moneyline": ("home_win", None, "home", "win"),
    "total": ("total", 8.5, "over", "over"),
}


def pass_the_gate(conn, *, sport: str, market: str, predictor: str = "statistical",
                  n: int = 100, season: int = 2024, tag: str = "gate") -> list[int]:
    """Write `n` settled at-the-line comparisons for `sport`'s `market` and
    `predictor` -- B.5's gate is 100 -- and return the claims' ids."""
    quantity, line, side, model_side = _SHAPES[market]
    start = datetime(season, 3, 1, 17, 0, tzinfo=timezone.utc)
    stamp = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    claims = []
    for i in range(n):
        gid = f"{tag}_{sport}_{market}_{predictor}_{i}"
        kickoff = start + timedelta(days=i)
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, ?, ?, 1, 'R', 'GHA', 'GHB', ?, 'final', ?, ?, ?)",
            (gid, sport, season, stamp(kickoff), kickoff.strftime("%Y-%m-%d"),
             3 + i % 2, 2))
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
            " line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES (?, ?, ?, ?, 'GHA', ?, 0.6, ?, ?, 'early', 'fs2', '{}', 'gate')",
            (stamp(kickoff - timedelta(hours=6)), sport, gid, market, line,
             model_side, predictor))
        pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
            " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
            " VALUES ('kalshi', ?, ?, ?, ?, ?, ?, ?, ?, 0.49, 0.51, ?)",
            (f"{gid}-t", f"{gid}-e", sport, gid, market, quantity, line, side,
             stamp(kickoff - timedelta(hours=1))))
        quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
            " game_id, market, quantity, line, side, shape, model_prob, venue_price,"
            " venue_implied, price_basis, created_utc, resolved_utc, outcome)"
            " VALUES (?, ?, 'kalshi', ?, ?, ?, ?, ?, ?, 'rung_matched', 0.6, 0.5, 0.5,"
            " 'mid', ?, ?, ?)",
            (pid, quote, sport, gid, market, quantity, line, side,
             stamp(kickoff - timedelta(minutes=50)), stamp(kickoff + timedelta(hours=4)),
             i % 2))
        claims.append(conn.execute("SELECT MAX(id) FROM at_the_line_claims").fetchone()[0])
    conn.commit()
    return claims
