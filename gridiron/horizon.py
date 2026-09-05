"""What a market's gate can still reach before its season ends.

RULING R3, made concrete. `GAME_TYPES` stays `("R",)`, so the MLB record ends on
the last day of the regular season and October is a different question. That has
a consequence the interface has to say out loud rather than imply: **some gates
cannot clear.**

A gate that will not be reached is not the same as a gate that has not been
reached yet, and showing them the same way is the quiet kind of dishonesty this
project exists to avoid. "6 of 100" reads as progress. "6 of 100 · ~60 expected
· season ends 09-27" reads as what it is.

The arithmetic is deliberately crude and deliberately stated: slates remaining,
times the rate this market has actually been writing at, plus what already
exists. It is an extrapolation from a small sample and it says so. The point is
not to predict the final number precisely; it is to make the difference between
"slow" and "impossible" visible without the reader doing arithmetic in their
head.
"""

from __future__ import annotations

import sqlite3

from . import config


def slates_remaining(conn: sqlite3.Connection, sport: str, season: int) -> int:
    """Distinct future slates still on the calendar for this sport's season.

    A SLATE IS WHAT THE SPORT WRITES BY: `games.week`, which is a week for
    football and basketball, a day for baseball and college football, a card
    for the fights. It is the same column `_written_so_far` divides by, and
    it has to be, because the outlook multiplies one by the other.

    Until 2026-09-05 this counted calendar days -- and UTC days at that, so a
    Sunday night football game was its own slate. The NFL record showed 73
    slates remaining against a rate measured per week, and the Record page
    projected ~3,504 resolutions from 48 written in week one. Eighteen weeks
    of 48 is 864.
    """
    row = conn.execute(
        "SELECT COUNT(DISTINCT week)"
        " FROM games WHERE sport = ? AND season = ? AND status = 'scheduled'",
        (sport, season),
    ).fetchone()
    return int(row[0] or 0)


def season_ends(conn: sqlite3.Connection, sport: str, season: int) -> str | None:
    row = conn.execute(
        "SELECT MAX(COALESCE(league_date, substr(kickoff_utc, 1, 10)))"
        " FROM games WHERE sport = ? AND season = ?",
        (sport, season),
    ).fetchone()
    return row[0] if row and row[0] else None


def market_outlook(
    conn: sqlite3.Connection, sport: str, market: str, season: int | None = None
) -> dict:
    """Whether this market's 100-resolution gate can clear before the season ends.

    Every figure carries the sample it came from (LAW 4). `expected` is an
    extrapolation and is labelled one; `reachable` is the judgement the
    interface renders, and it is only ever False when the arithmetic says so
    with the rate measured over at least one slate.
    """
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON) \
        if season is None else season
    is_prop = market in config.SPORT_PROP_MARKETS.get(sport, ())
    market_type = "prop" if is_prop else market
    prop_type = market if is_prop else None

    written, slates_used, resolved = _written_so_far(
        conn, sport, market_type, prop_type, season
    )
    remaining = slates_remaining(conn, sport, season)
    ends = season_ends(conn, sport, season)
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM

    per_slate = (written / slates_used) if slates_used else None
    expected = None
    if per_slate is not None:
        expected = int(round(resolved + per_slate * remaining))

    out = {
        "sport": sport,
        "market": market,
        "gate": gate,
        "resolved": resolved,
        "written": written,
        "n": resolved,
        "slates_used": slates_used,
        "slates_remaining": remaining,
        "season_ends": ends,
        "per_slate": round(per_slate, 2) if per_slate is not None else None,
        "expected": expected,
        "expected_is_an_extrapolation": True,
    }

    if per_slate is None:
        out["reachable"] = None
        out["message"] = (
            f"{resolved} of {gate} · nothing written in this market yet, so "
            "there is no rate to project from"
        )
        return out

    out["reachable"] = expected >= gate
    ends_short = ends[5:] if ends else "the season's end"
    if out["reachable"]:
        out["message"] = (
            f"{resolved} of {gate} · ~{expected} expected · season ends {ends_short}"
        )
    else:
        out["message"] = (
            f"{resolved} of {gate} · ~{expected} expected · season ends "
            f"{ends_short} · THIS GATE CANNOT CLEAR THIS SEASON"
        )
    return out


def _written_so_far(conn, sport, market_type, prop_type, season):
    """(written, slates that wrote any, resolved) for one market this season."""
    sql = (
        "SELECT COUNT(*) AS written,"
        " COUNT(DISTINCT g.week) AS slates,"
        " SUM(CASE WHEN p.resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND p.market_type = ?"
        " AND p.predictor = 'statistical'"
        " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                 WHERE v.prediction_id = p.id)"
    )
    params = [sport, season, market_type]
    if prop_type is not None:
        sql += " AND p.prop_type = ?"
        params.append(prop_type)
    row = conn.execute(sql, params).fetchone()
    return int(row["written"] or 0), int(row["slates"] or 0), int(row["resolved"] or 0)


def zero_write_line(market: str, asked: int, floor: float) -> str:
    """What a slate says about a market it wrote nothing in (ruling 1).

    A market where the model never reached the floor at the line the market
    actually quotes is the floor telling the truth, not a defect, and the card
    says so in words rather than leaving a silent gap that reads as a failure to
    find questions.
    """
    from . import language

    if asked:
        return ""
    return (
        f"{language.humanise(market)}: 0 asked — model never reached "
        f"{round(floor * 100)}% at the market's line"
    )
