"""Capture what was knowable, when (S1, 2026-09-03).

THE PROBLEM THIS SOLVES, measured before it was built. The timing probe of
2026-09-02 set out to answer "when does the information actually land?" for
four sports and could answer it for none of them properly:

    injuries          55,554 rows and NOT ONE carries a timestamp
    mlb_lineups       6,902 of 6,958 came from one backfill on 2026-08-30
    weather           one row per game, overwritten by the next fetch

None of that is missing data. It is data with no capture time, which is a
different and more insidious thing: it looks complete, it answers every
question except the one about time, and averaging it produces a figure like
"lineups post 10,592 hours before first pitch" -- 441 days AFTER the game.

WHAT THIS MODULE DOES. It writes the same information a second time, stamped
and append-only, into tables that exist only to hold history. Nothing here
replaces a current-state row: `injuries`, `mlb_lineups` and
`weather_forecasts` keep their shape and remain what the factors read.

LOUD ON EMPTY. A capture that stores nothing says so and is recorded as a
failure. A silent zero here is the exact failure mode that let a resolver run
for two days against a table nobody refreshed, reporting `noop` truthfully
every time.
"""

from __future__ import annotations

import sqlite3

from . import config
from .db import utcnow


class NothingCaptured(RuntimeError):
    """A capture ran and stored nothing. Loud, never a silent zero."""


def capture_injuries(conn: sqlite3.Connection, sport: str) -> int:
    """Stamp the current injury report into its own history.

    Reads what the loaders have already put in `injuries` and writes a dated
    copy. That is deliberately a COPY rather than a move: the factors read
    current state and must keep working exactly as they do.

    THE STAMP IS WHEN WE SAW IT, not when the league published it. Our
    storage time is an upper bound on publication, and where our own cadence
    is the binding constraint the measurement describes us rather than the
    league -- the distinction the lineup probe had to make and which is the
    whole reason this table exists.
    """
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    rows = conn.execute(
        "SELECT season, week, team, player_id, player_name, position,"
        "       report_status, practice_status"
        "  FROM injuries WHERE season = ?", (season,)).fetchall()
    if not rows:
        return 0

    stamp = utcnow()
    written = 0
    for row in rows:
        if not row["player_name"]:
            continue
        # INSERT OR IGNORE IS RIGHT HERE AND NOWHERE ELSE. The primary key
        # includes the capture time, so the only way this collides is two
        # captures inside the same second -- which is a duplicate of the same
        # observation, not a rejected row. Everywhere else in this project an
        # OR IGNORE would hide a constraint failure, which is why it is
        # explained rather than merely used.
        cur = conn.execute(
            "INSERT OR IGNORE INTO injury_reports (sport, season, week, team,"
            " player_name, player_id, position, report_status,"
            " practice_status, captured_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sport, row["season"], row["week"], row["team"],
             row["player_name"], row["player_id"], row["position"],
             row["report_status"], row["practice_status"], stamp))
        written += cur.rowcount if cur.rowcount > 0 else 0
    conn.commit()
    return written


def capture_lineups(conn: sqlite3.Connection) -> int:
    """Stamp tonight's posted lineups as a LIVE capture.

    Only games that have not started. A lineup read after first pitch is a
    historical fact and is not what this table is for -- storing it as a live
    capture would put the same lie back that the backfill told.
    """
    rows = conn.execute(
        "SELECT l.game_id, l.side, l.slot, l.player_id, l.player_name"
        "  FROM mlb_lineups l JOIN games g ON g.id = l.game_id"
        " WHERE g.kickoff_utc IS NOT NULL AND g.kickoff_utc > ?"
        "   AND g.status = 'scheduled'", (utcnow(),)).fetchall()
    if not rows:
        return 0

    stamp = utcnow()
    written = 0
    for row in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO lineup_captures (game_id, side, slot,"
            " player_id, player_name, captured_utc, source)"
            " VALUES (?,?,?,?,?,?,'live')",
            (row["game_id"], row["side"], row["slot"], row["player_id"],
             row["player_name"], stamp))
        written += cur.rowcount if cur.rowcount > 0 else 0
    conn.commit()
    return written


def capture_weather(conn: sqlite3.Connection) -> int:
    """Copy the forecast for a game that has now finished into the observed
    table, so a later reading and the forecast can be told apart.

    WHAT THIS DOES NOT DO. It does not fetch an observation -- no observed
    weather source is wired into this project. What it does is make the
    SEPARATION real: `weather_forecasts` is what was expected, and
    `weather_observed` is the table an observation goes in when one exists.

    The defect this is aimed at is already recorded: the college wind
    coefficient is fitted on observed weather and applied to forecasts, so a
    model fitted on hindsight is asked to predict from an expectation. That
    cannot be repaired until the two are stored apart, and this is the storing
    apart. **No row is written here from a forecast**, because a forecast
    copied into an observations table is precisely the confusion the two
    tables exist to prevent.
    """
    return 0


def run(conn: sqlite3.Connection) -> dict:
    """One capture pass over everything that carries a time.

    Returns counts per source. Raises `NothingCaptured` when every source
    stored nothing AND at least one had something to store, which is the
    shape of a broken capture rather than a quiet day.
    """
    counts = {"injuries": 0, "lineups": 0, "weather": 0}
    for sport in config.SPORTS:
        counts["injuries"] += capture_injuries(conn, sport)
    counts["lineups"] = capture_lineups(conn)
    counts["weather"] = capture_weather(conn)

    # A QUIET DAY IS NOT A FAILURE, and the first version of this guard did
    # not know the difference. It compared against every injury and lineup row
    # ever stored -- 180,798 of them, almost all historical -- and so fired on
    # its very first run, when there was genuinely nothing to capture.
    #
    # WHAT IT MUST COMPARE AGAINST IS WHAT WAS ELIGIBLE: injury rows for the
    # CURRENT season, and lineups for games that have not started. Out of
    # season, or before a lineup posts, both are legitimately zero and this
    # says so quietly.
    eligible = _eligible(conn)
    if eligible and not any(counts.values()):
        raise NothingCaptured(
            f"a capture pass ran with {eligible} row(s) eligible and wrote "
            f"nothing. Something was there to stamp and none of it was "
            f"stamped, which is a broken capture rather than a quiet day."
        )
    counts["eligible"] = eligible
    return counts


def _eligible(conn: sqlite3.Connection) -> int:
    """How much there was to capture, so a real zero is not read as a fault."""
    seasons = tuple({config.SPORT_CURRENT_SEASON.get(s, config.CURRENT_SEASON)
                     for s in config.SPORTS})
    marks = ",".join("?" for _ in seasons)
    injuries = conn.execute(
        f"SELECT COUNT(*) AS n FROM injuries WHERE season IN ({marks})",
        seasons).fetchone()["n"]
    lineups = conn.execute(
        "SELECT COUNT(*) AS n FROM mlb_lineups l JOIN games g"
        "  ON g.id = l.game_id"
        " WHERE g.kickoff_utc IS NOT NULL AND g.kickoff_utc > ?"
        "   AND g.status = 'scheduled'", (utcnow(),)).fetchone()["n"]
    return injuries + lineups
