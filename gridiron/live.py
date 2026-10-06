"""The live poll: what is happening right now, and nothing else.

WHAT THIS IS ALLOWED TO TOUCH. `games` — the score, the period, the clock and
the status. That is data about the world, not a claim about it, and updating
it is permitted (LAW 3 governs `predictions`, which nothing here writes).
And from 2026-10-07 (operator question 38 (A), ruled 2026-10-06) one row of
`live_first_under_way` per game: the instant the poll first saw it truly
under way, written once and never rewritten, because it decides which
reads were closes and claims (`start_of`, below, is the one door that reads
it).

WHAT IT MUST NOT DO, and the reason each is structural rather than a promise:

  * IT MUST NOT REACH THE PREDICTION PATH. A live score is the outcome, and a
    forecast that could see it would be scoring itself. So this module is
    outside the prediction import closure, its columns are prefixed `live_` so
    the closure scan can name them exactly, and a planting imports this module
    from a sport's prediction path to prove the scan fires.

  * IT MUST NOT SETTLE ANYTHING. Marking a game final is a fact about the
    game; settling a prediction is a claim about a forecast, and only the
    resolve task writes one. The poller may CALL that resolver when a game
    ends -- so a result lands within a minute rather than within four hours --
    but calling the one idempotent resolver is not a second path to an
    outcome. A test asserts that a game the poller marked final leaves its
    predictions open until resolve actually runs.

  * IT MUST NOT RUN WHEN NOTHING IS ON. Polling a scoreboard every 90 seconds
    around the clock would be thousands of requests a day to a public endpoint
    that owes us nothing, almost all of them about games that finished hours
    ago. Outside a window the poll makes ZERO requests, and a test proves the
    count is zero rather than small.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from . import config
from .data import sources as http
from . import db
from .db import utcnow

#: How often the poll runs while a window is open. Declared 2026-09-01.
#:
#: Ninety seconds is a judgement about what a score is FOR here. This is not a
#: scoreboard app: the number exists so a tile can say the game is 21-7 in the
#: third, and a minute and a half of staleness does not change what a reader
#: does with that. Faster costs requests linearly and buys nothing.
POLL_SECONDS = 90

#: How long a game of each sport is expected to take, kickoff to final.
#: Measured against the record on 2026-09-01: the 95th percentile of
#: (last update - kickoff) is comfortably inside each of these, and the window
#: is deliberately generous because closing it early stops the poll while a
#: game is still being played, which is the one failure that matters.
GAME_HOURS = {
    "nfl": 4.0,
    "cfb": 4.5,     # the longest: reviews, overtime, and a running clock that stops
    "nba": 3.0,
    "mlb": 4.0,     # extra innings have no clock at all
}

#: HOW LONG AFTER ITS START A GAME MAY STILL BE POLLED (ruled 2026-09-09).
#:
#: THE WINDOW USED TO CLOSE ON `GAME_HOURS`, and a game that ran past it was
#: dropped while it was still being played. Measured against a live game that
#: day: polled at one, three and four hours after first pitch; not polled at
#: five. Extra innings, a rain delay, a long review -- the poll stopped and
#: the score froze on screen with nothing saying so.
#:
#: A GAME IS NOW ON UNTIL THE POLLER HAS SEEN IT FINAL. This is only the
#: backstop for a row whose status never arrives: without one, a single stale
#: game would keep the poller requesting all night, which is the zero-request
#: contract undone from the other end. Twelve hours is far beyond any real
#: game in any sport here -- baseball's expected four, college football's
#: four and a half -- so it can only catch a row nothing is updating.
STALE_AFTER = timedelta(hours=12)

#: A poll starts this long before the first kickoff, so a game that starts
#: early -- or a clock that is a few minutes out -- is not missed.
WINDOW_LEAD = timedelta(minutes=10)

#: One request per sport per poll, and each of these was measured rather than
#: assumed on 2026-09-01:
#:
#:   * `site.api.espn.com` answers 403, as the market module already recorded.
#:   * `sports.core.api.espn.com/.../events` answers, but returns a list of
#:     `$ref` stubs -- one further request per game. On a 60-game college
#:     Saturday that is 9,600 requests across a ten-hour window, to a public
#:     endpoint that owes this project nothing.
#:   * `cdn.espn.com/core/<league>/scoreboard` answers with every event in
#:     full, in ONE request. 25 events for the college date tested.
#:   * MLB's own `statsapi` answers with the whole day hydrated with the
#:     linescore -- score, inning and status -- also in one request. It is
#:     already this project's MLB source, so it is not a new dependency.
ESPN_SCOREBOARD = "https://cdn.espn.com/core/{league}/scoreboard?xhr=1&dates={day}"
MLB_SCHEDULE = ("https://statsapi.mlb.com/api/v1/schedule?sportId=1"
                "&startDate={date}&endDate={date}&hydrate=linescore")

ESPN_LEAGUE = {
    "cfb": "college-football",
    "nba": "nba",
    "nfl": "nfl",
}

#: WHICH SPORTS CAN BE FOLLOWED LIVE AT ALL, and why the other two cannot yet.
#:
#: The blocker is identity, not the feed. A game id has to match what the
#: record already stores:
#:
#:   cfb  401635525          the ESPN event id itself      -> matches exactly
#:   mlb  mlb_718780         statsapi's gamePk, prefixed   -> matches exactly
#:   nba  nba_0022200001     an NBA-stats id, not ESPN's   -> NO match
#:   nfl  2016_01_CAR_DEN    an nflverse key               -> NO match
#:
#: Following the last two would mean bridging ESPN's events to our ids by team
#: and date. This project has done exactly one identity bridge before (the
#: ESPN-to-MLB player crosswalk) and the rule it established was that a bridge
#: is MEASURED, stored with its match rate, and refuses ambiguous pairs --
#: because a wrong match attaches a live score to the wrong game and nobody
#: notices. That is its own piece of work, not a line in this one.
LIVE_SPORTS = ("cfb", "mlb")

#: What ESPN's status names mean in this table's vocabulary. Anything not
#: listed is treated as SCHEDULED and logged, rather than guessed at: a status
#: nobody has mapped writing itself into the record as "in progress" would put
#: a live mark on a postponed game.
STATUS_MAP = {
    "STATUS_SCHEDULED": "scheduled",
    "STATUS_IN_PROGRESS": "in",
    "STATUS_HALFTIME": "in",
    "STATUS_END_PERIOD": "in",
    "STATUS_DELAYED": "in",
    "STATUS_RAIN_DELAY": "in",
    "STATUS_FINAL": "final",
    "STATUS_FULL_TIME": "final",
}


#: The columns the live poll owns. Named HERE and not in `gridiron.db`, and
#: that placement is the law rather than tidiness: `db` is inside the
#: prediction import closure, so a module on the forecasting path naming
#: `live_period` in code makes the LAW 1 scan flag the package -- which is
#: exactly what happened when this migration was first written there. The
#: market snapshot migration moved out of `db` for the same reason and left a
#: note saying so; this is that note being taken.
LIVE_COLUMNS = ("live_period", "live_clock", "live_updated_utc")


def _games_create_sql(name: str) -> str:
    """The `games` CREATE from schema.sql, under another name.

    Read from the schema file rather than retyped, so the rebuilt table cannot
    drift from the declared one -- a migration that builds a slightly
    different table than the schema describes is a difference nobody sees
    until the next migration.
    """
    text = db.SCHEMA_PATH.read_text(encoding="utf-8")
    head = text.index("CREATE TABLE IF NOT EXISTS games (")
    # Built with chr(10): a backslash-n written here has been mangled into a
    # literal newline on the way into this project three times now, and a
    # broken escape inside a migration is a broken migration.
    marker = chr(10) + ");"
    tail = text.index(marker, head) + len(marker)
    return text[head:tail].replace(
        "CREATE TABLE IF NOT EXISTS games (", f"CREATE TABLE {name} (", 1)


def ensure_live_columns(conn) -> bool:
    """Let `games.status` hold 'in', and let a started game carry a score.

    THE OLD CONSTRAINTS COULD NOT DESCRIBE A GAME IN FLIGHT. `status` allowed
    only 'scheduled' and 'final', and a second CHECK said a score exists if and
    only if the game is FINAL -- so a running game was inexpressible twice
    over, and the slate clock could only ever say "upcoming" or "complete".

    SQLite applies a CHECK at CREATE and never revisits it, so this is a table
    rebuild, and `games` has ten foreign-key children. TWO TRAPS, both hit on
    the first attempt, both of which briefly emptied a live 21,527-row table:

      1. `ALTER TABLE ... RENAME` REWRITES CHILDREN. Modern SQLite follows a
         renamed table into every foreign key that references it, so renaming
         `games` out of the way silently repointed all ten children at the
         renamed table, and dropping it left 310,480 dangling references.
         `db.widen_sport_checks` sets `legacy_alter_table` for exactly this
         reason and the first draft here did not copy it. THIS VERSION NEVER
         RENAMES THE LIVE TABLE: it builds the new one alongside, copies,
         checks the count, drops the old, and renames the NEW one into place
         -- at which point the children's references, which still say `games`,
         are correct again.

      2. `executescript()` COMMITS. It ends any open transaction before it
         runs, so wrapping this in BEGIN/ROLLBACK bought nothing: the rename
         was already committed when the failure arrived. There is no
         transaction here to give false comfort. The steps are ordered so each
         is safe alone, the row count is compared before anything is dropped,
         and `foreign_key_check` runs at the end as proof rather than as
         decoration.

    Returns True when it rebuilt, False when there was nothing to do.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='games'"
    ).fetchone()
    if not row:
        return False
    stored = row[0] or ""
    if "'in'" in stored and LIVE_COLUMNS[0] in stored:
        return False

    columns = [r[1] for r in conn.execute("PRAGMA table_info(games)")]
    keep = [c for c in columns if c not in LIVE_COLUMNS]
    joined = ", ".join(keep)
    before = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS games_rebuilt")
        conn.execute(_games_create_sql("games_rebuilt"))
        conn.execute(
            f"INSERT INTO games_rebuilt ({joined}) SELECT {joined} FROM games")
        moved = conn.execute("SELECT COUNT(*) FROM games_rebuilt").fetchone()[0]
        if moved != before:
            conn.execute("DROP TABLE games_rebuilt")
            conn.commit()
            raise RuntimeError(
                f"the rebuild copied {moved} of {before} games; nothing was "
                f"replaced and the original table is untouched")
        conn.execute("DROP TABLE games")
        # LEGACY MODE for this one statement: the children already reference
        # `games` by name and must be left exactly as they are.
        conn.execute("PRAGMA legacy_alter_table = ON")
        conn.execute("ALTER TABLE games_rebuilt RENAME TO games")
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.commit()
        # The indexes went with the dropped table; the schema file rebuilds
        # them and no-ops everything else.
        conn.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
        broken = conn.execute("PRAGMA foreign_key_check").fetchall()
        if broken:
            raise RuntimeError(
                f"widening games.status left {len(broken)} dangling references "
                f"-- restore from backup before continuing")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
    return True


class LiveWindow:
    """One sport's live window, and why it is open."""

    __slots__ = ("sport", "first_kickoff", "last_expected_end", "games")

    def __init__(self, sport, first_kickoff, last_expected_end, games):
        self.sport = sport
        self.first_kickoff = first_kickoff
        self.last_expected_end = last_expected_end
        self.games = games

    def __repr__(self) -> str:
        return (f"LiveWindow({self.sport!r}, {len(self.games)} games, "
                f"{self.first_kickoff}..{self.last_expected_end})")


def _parse(moment: str | None) -> datetime | None:
    if not moment:
        return None
    try:
        return datetime.strptime(moment[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def open_windows(conn: sqlite3.Connection, now: datetime | None = None) -> list[LiveWindow]:
    """Every sport with a game that SHOULD be under way at `now`.

    Reads the schedule, not the scoreboard: the question "is anything on?" has
    to be answerable without making a request, or the poll would have to call
    the endpoint to find out whether it should call the endpoint.
    """
    now = now or datetime.now(timezone.utc)
    windows = []
    for sport in LIVE_SPORTS:
        hours = GAME_HOURS.get(sport, 4.0)
        # THE WINDOW'S BOUNDS ARE INSTANTS (operator question 35,
        # 2026-10-01): `julianday()` on both sides, never the stored text.
        rows = conn.execute(
            "SELECT id, kickoff_utc, status FROM games"
            " WHERE sport = ? AND kickoff_utc IS NOT NULL AND status != 'final'"
            "   AND julianday(kickoff_utc) >= julianday(?)"
            "   AND julianday(kickoff_utc) <= julianday(?)",
            (sport,
             (now - STALE_AFTER).strftime("%Y-%m-%dT%H:%M:%SZ"),
             (now + WINDOW_LEAD).strftime("%Y-%m-%dT%H:%M:%SZ")),
        ).fetchall()
        live = []
        for row in rows:
            kickoff = _parse(row["kickoff_utc"])
            if kickoff is None:
                continue
            # ON FROM ITS START UNTIL IT IS SEEN FINAL (ruled 2026-09-09).
            # `status != 'final'` in the query above is the closing condition;
            # this is the opening one, plus the stale backstop. The expected
            # length of a game decides nothing any more: a game that runs long
            # is still a game being played, and dropping it was how a score
            # came to freeze on screen mid-innings.
            if kickoff - WINDOW_LEAD <= now <= kickoff + STALE_AFTER:
                live.append(row["id"])
        if live:
            kickoffs = [_parse(r["kickoff_utc"]) for r in rows
                        if r["id"] in set(live)]
            kickoffs = [k for k in kickoffs if k]
            # THE REPORTED END IS STILL THE EXPECTED ONE. `GAME_HOURS` says
            # when a game is expected to finish, which is what a window's
            # description is for; it no longer decides whether the poll runs.
            windows.append(LiveWindow(
                sport, min(kickoffs), max(kickoffs) + timedelta(hours=hours), live))
    return windows


def scoreboard(conn: sqlite3.Connection, sport: str, day: str) -> list[dict]:
    """One request. Returns a list of games in this module's own shape.

    The two feeds are shaped nothing alike, so each is read into the same
    small dictionary here rather than leaving the caller to branch on sport --
    which is how one of them would end up with a field the other silently
    lacks.
    """
    if sport == "mlb":
        url = MLB_SCHEDULE.format(date=f"{day[:4]}-{day[4:6]}-{day[6:8]}")
        body = http.fetch(conn, url, ttl=timedelta(seconds=POLL_SECONDS))
        return _read_mlb(json.loads(body))
    league = ESPN_LEAGUE.get(sport)
    if not league:
        raise ValueError(f"no live source for {sport!r}")
    url = ESPN_SCOREBOARD.format(league=league, day=day)
    body = http.fetch(conn, url, ttl=timedelta(seconds=POLL_SECONDS))
    payload = json.loads(body)
    events = ((payload.get("content") or {}).get("sbData") or {}).get("events") or []
    out = []
    for event in events:
        state = read_event(event)
        if state:
            state["game_id"] = str(state["event_id"])
            out.append(state)
    return out


#: What MLB calls a game that is under way, finished, or not yet started.
MLB_STATES = {"Live": "in", "Final": "final", "Preview": "scheduled"}

#: statsapi's words for a game in its warm-up (2026-10-07, operator question
#: 38 (A)): the league calls it 'Live' (abstract state) while its coded state
#: is still the pre-game 'P' and its detailed state 'Warmup'. The poll maps
#: 'Live' to 'in' (above); the ruling says that warm-up, before the listed
#: start, is not a game "truly under way". No warm-up payload is cached on the
#: record (measured 2026-10-07), so these are the feed's documented words.
MLB_WARM_UP_DETAILED = "Warmup"
MLB_PRE_GAME_CODED = "P"


def _innings_recorded(line: dict) -> int:
    """How many innings of a statsapi linescore carry a run count for either
    side -- the feed's own record of play (2026-10-07, operator question 38).
    MEASURED on the record's cached schedules that day: a Pre-Game payload
    up to three hours before its listed start already carries a linescore
    reading "Top 1st", 0-0 and one inning, with NO run count in that inning;
    every game in progress carries one in each inning played. So the team
    totals and the current inning are placeholders before play, and an
    inning's runs are the score or period the ruling asks to be recorded."""
    return sum(
        1 for inning in (line.get("innings") or [])
        if isinstance(inning, dict)
        and any("runs" in (inning.get(side) or {}) for side in ("home", "away")))


def _read_mlb(payload: dict) -> list[dict]:
    """statsapi's schedule, hydrated with the linescore, in this shape."""
    out = []
    for date in payload.get("dates") or []:
        for game in date.get("games") or []:
            line = game.get("linescore") or {}
            teams = line.get("teams") or {}
            status = game.get("status") or {}
            state = MLB_STATES.get(status.get("abstractGameState"))
            if state is None:
                continue
            # "Top 6th" is what a person following baseball says, and it is
            # two fields here: the half and the ordinal.
            half = (line.get("inningHalf") or "").strip()
            ordinal = line.get("currentInningOrdinal")
            period = f"{half} {ordinal}".strip() if ordinal else None
            out.append({
                "game_id": f"mlb_{game.get('gamePk')}",
                "event_id": game.get("gamePk"),
                "status": state,
                "status_raw": status.get("detailedState"),
                "home_score": (teams.get("home") or {}).get("runs"),
                "away_score": (teams.get("away") or {}).get("runs"),
                # BASEBALL HAS NO CLOCK. Absent rather than an empty string:
                # the tile shows the inning alone, which is the whole of what
                # the sport has to say about how far along it is.
                "period": period,
                "clock": None,
                # WHAT THE FEED RECORDED, for the first-under-way record
                # (2026-10-07, operator question 38 (A)): the innings that
                # carry runs, and whether this is the warm-up 'Live'.
                "innings_recorded": _innings_recorded(line),
                "warm_up": (status.get("detailedState") == MLB_WARM_UP_DETAILED
                            or (status.get("abstractGameState") == "Live"
                                and status.get("codedGameState")
                                == MLB_PRE_GAME_CODED)),
            })
    return out


def read_event(payload: dict) -> dict | None:
    """The score, period, clock and status from one event document.

    Returns None when the document carries no competition -- a listing that
    exists but has not been filled in yet is not a game in progress.
    """
    competitions = payload.get("competitions") or []
    if not competitions:
        return None
    competition = competitions[0]
    status = (((competition.get("status") or {}).get("type") or {})
              .get("name"))
    mapped = STATUS_MAP.get(status)
    competitors = competition.get("competitors") or []
    scores, home, away = {}, None, None
    for side in competitors:
        value = side.get("score")
        if isinstance(value, dict):
            value = value.get("value")
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = None
        if side.get("homeAway") == "home":
            home, scores["home"] = side.get("id"), value
        else:
            away, scores["away"] = side.get("id"), value
    period = (competition.get("status") or {}).get("period")
    clock = (competition.get("status") or {}).get("displayClock")
    try:
        number = int(period) if period is not None else None
    except (TypeError, ValueError):
        number = None
    return {
        "event_id": payload.get("id"),
        "status_raw": status,
        "status": mapped,
        "home_score": scores.get("home"),
        "away_score": scores.get("away"),
        "period": str(period) if period is not None else None,
        "clock": clock,
        "home_id": home,
        "away_id": away,
        # WHAT THE FEED RECORDED, for the first-under-way record (2026-10-07,
        # operator question 38 (A)). MEASURED on the record's cached
        # scoreboards that day: a scheduled event carries scores of "0" and
        # period 0 and no period's score; a finished one its period number
        # and one score per period for each side. So a period numbered one
        # or more, or a period's score, is a period or score recorded, and
        # the pregame "0" is a placeholder.
        "period_number": number,
        "periods_scored": max(
            (len(side.get("linescores") or []) for side in competitors
             if isinstance(side, dict)), default=0),
    }


def apply_event(conn: sqlite3.Connection, game_id: str, seen: dict) -> bool:
    """Write one game's live state. True when something actually changed.

    A GAME THAT HAS NOT STARTED IS LEFT ALONE. The status map returns None for
    anything unrecognised, and an unmapped status writes nothing at all rather
    than defaulting to a state -- the same rule the humaniser now follows for
    a side it has no words for, and for the same reason: a confident wrong
    value is worse than an absent one.

    The score is written only when the game has started, because a scheduled
    game carrying a score is refused by the schema, on purpose.
    """
    status = seen.get("status")
    if status is None:
        return False

    row = conn.execute(
        "SELECT status, home_score, away_score, live_period, live_clock"
        " FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return False

    home = seen.get("home_score")
    away = seen.get("away_score")
    if status == "scheduled":
        home = away = None
    elif home is None or away is None:
        # STARTED, BUT THE FEED HAS NO SCORE YET. 0-0 is the honest reading of
        # a game that has kicked off, and the schema requires a score for a
        # started game -- but only say it when the feed says the game is under
        # way, never to satisfy a constraint.
        home = 0 if home is None else home
        away = 0 if away is None else away

    unchanged = (row["status"] == status
                 and row["home_score"] == home
                 and row["away_score"] == away
                 and row["live_period"] == seen.get("period")
                 and row["live_clock"] == seen.get("clock"))
    if unchanged:
        return False

    conn.execute(
        "UPDATE games SET status = ?, home_score = ?, away_score = ?,"
        " live_period = ?, live_clock = ?, live_updated_utc = ?"
        " WHERE id = ?",
        (status, home, away, seen.get("period"), seen.get("clock"),
         utcnow(), game_id),
    )
    return True


# ---------------------------------------------------------------------------
# A GAME'S START: THE EARLIER OF ITS LISTED START AND THE FIRST POLL THAT SAW
# IT TRULY UNDER WAY (operator question 38 (A), ruled 2026-10-06, second set,
# docs/briefs/2026-10-06-rulings-second.md; built 2026-10-07)
# ---------------------------------------------------------------------------
#
# "A game's start is the earlier of its listed start and the first poll that
# sees it truly under way (a score or period recorded; MLB's warm-up "Live"
# before the listed start does not count). No read at or after that instant
# is a close or a claim."
#
# Item 1 (ruled 2026-09-30) keeps a game and claims its reads until its
# LISTED start whatever its status says, which is what stopped baseball's
# warm-up 'Live' cutting its closes to 35 minutes out. It also meant that a
# game truly begun before its listed start -- a stale listing -- had its
# in-play reads claimed, closed on and priced until the listed time (item
# 1's prover, 2026-10-01: question 38). The record kept no instant at which
# a game was first seen under way; `live_first_under_way` is that instant,
# and these are the ONE DOOR every reader of a close or a claim reads it by:
# `start_of` in Python, `before_the_start` its one SQL spelling beside it,
# `julianday()` on both sides as operator question 35 compares every start.

#: The record of the first poll that saw each game truly under way.
UNDER_WAY_TABLE = "live_first_under_way"


def start_of(listed: str | None, under_way: str | None) -> datetime | None:
    """THE ONE DOOR FOR A GAME'S START (operator question 38 (A), 2026-10-07):
    the earlier of its listed start and the instant the first poll saw it
    truly under way, each read as an instant (`db.instant`). None when the
    record knows neither. A listed start nobody can read raises ValueError,
    as `db.instant` does, so every reader keeps item 1's rule for it (the
    game is not read, named, and never guessed); a game first seen under way
    with no listed start starts at that instant."""
    listed_at = db.instant(listed)
    seen_at = db.instant(under_way) if under_way else None
    if listed_at is None:
        return seen_at
    if seen_at is None:
        return listed_at
    return min(listed_at, seen_at)


def _named(part: str) -> str:
    """A table alias or an aliased column, never anything else: the SQL
    spellings below are put into statements as text."""
    if not all(piece.isidentifier() for piece in part.split(".")):
        raise ValueError(f"{part!r} is not a column or a table alias")
    return part


def keeps_first_under_way(conn: sqlite3.Connection) -> bool:
    """Does this database hold the first-under-way record at all? A record
    no release carrying it has opened yet does not (2026-10-07): read
    through a read-only door -- the gate's tests read the operator's record
    so -- it cannot be migrated, and a reader must not write to the database
    it is reading (the opening read's precedent, `drift._venue_claims`).
    Such a record never saw a game under way, so every game on it starts at
    its listed start, which is what the spellings below say there."""
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (UNDER_WAY_TABLE,)).fetchone() is not None


def under_way_sql(game: str, conn: sqlite3.Connection) -> str:
    """The instant `game` (a `games` alias) was first seen truly under way,
    as a scalar subquery for a SELECT list -- NULL where it never was, or on
    a record without the table -- so a reader that already reads the listed
    start hands both to `start_of`."""
    game = _named(game)
    if not keeps_first_under_way(conn):
        return "NULL"
    return (f"(SELECT u.under_way_utc FROM {UNDER_WAY_TABLE} u"
            f" WHERE u.game_id = {game}.id)")


def before_the_start(stamp: str, game: str, conn: sqlite3.Connection) -> str:
    """THE ONE SQL SPELLING of "strictly before the game's start" (operator
    question 38 (A), 2026-10-07): `stamp` before the listed start of `game`
    (a `games` alias), or no listed start, AND before the instant it was
    first seen truly under way, if it was -- `julianday()` on both sides of
    each, as operator question 35 compares every start. `start_of` in SQL.
    On a record without the table, the listed start alone (every game on it
    starts there)."""
    stamp, game = _named(stamp), _named(game)
    listed = (f"({game}.kickoff_utc IS NULL"
              f" OR julianday({stamp}) < julianday({game}.kickoff_utc))")
    if not keeps_first_under_way(conn):
        return f"({listed})"
    return (f"({listed}"
            f" AND NOT EXISTS (SELECT 1 FROM {UNDER_WAY_TABLE} u"
            f"  WHERE u.game_id = {game}.id"
            f"    AND julianday({stamp}) >= julianday(u.under_way_utc)))")


def under_way_evidence(state: dict, listed: str | None,
                       at: datetime) -> str | None:
    """What the feed recorded that says the game is truly under way, in
    words -- or None, and then the poll writes no row.

    BY THE FEED'S OWN FIELDS, AS MEASURED on the record's cached payloads
    (2026-10-07): an inning's runs (statsapi, `innings_recorded`), or a
    period numbered one or more or a period's own score (ESPN,
    `period_number`, `periods_scored`) -- never the placeholders a pregame
    payload carries (statsapi's "Top 1st" and 0-0 with no inning's runs;
    ESPN's scores of "0" at period 0) -- and only under a status the feed
    calls under way or over. MLB'S WARM-UP 'LIVE' BEFORE THE LISTED START
    DOES NOT COUNT, whatever it carries (the ruling's own words)."""
    if state.get("status") not in ("in", "final"):
        return None
    try:
        listed_at = db.instant(listed)
    except ValueError:
        listed_at = None
    if state.get("warm_up") and (listed_at is None or at < listed_at):
        return None
    innings = int(state.get("innings_recorded") or 0)
    period = state.get("period_number")
    scored = int(state.get("periods_scored") or 0)
    recorded = []
    if innings > 0:
        recorded.append(f"runs recorded in {innings} inning"
                        + ("" if innings == 1 else "s"))
    if period is not None and period >= 1:
        recorded.append(f"period {period} recorded")
    if scored > 0:
        recorded.append(f"a score recorded for {scored} period"
                        + ("" if scored == 1 else "s"))
    if not recorded:
        return None
    score = ("" if state.get("home_score") is None or state.get("away_score") is None
             else f", the score {state.get('home_score')}-{state.get('away_score')}"
                  f" (home first)")
    return (f"The feed reported {state.get('status_raw') or state.get('status')} "
            f"with {' and '.join(recorded)}{score}, at the first poll that saw "
            f"it; its listed start was {listed or 'not recorded'}.")


def record_first_under_way(conn: sqlite3.Connection, game_id: str,
                           state: dict, *,
                           only_before_its_listed_start: bool = False,
                           sport: str | None = None) -> bool:
    """Write the instant this poll first saw `game_id` truly under way, once
    (operator question 38 (A), 2026-10-07). True when a row was written.

    ONCE PER GAME: a game already in the record is left as it is, and the
    schema refuses a second row whatever the statement says. Stamped with
    the poll's own instant as it writes, as `games.live_updated_utc` is, and
    committed at once, so a reader of the start sees it as soon as it is
    stamped. A plain insert, never an upsert (the frozen register). A
    database without the table (one no release carrying it has opened) is
    left as it is: `db.init` brings the table, never this.

    `only_before_its_listed_start` (Q38's prover, 2026-10-07): for a game
    outside the poll's window (`poll`, below), a row is written only while
    its listed start is still ahead of the stamp, or not recorded -- the
    only case in which the instant moves its start. A listed start nobody
    can read writes none: every reader keeps item 1's rule for it. `sport`,
    when given, is the sport whose scoreboard the state came from, and a
    game the record files under another sport writes none."""
    if not keeps_first_under_way(conn):
        return False
    if conn.execute(f"SELECT 1 FROM {UNDER_WAY_TABLE} WHERE game_id = ?",
                    (game_id,)).fetchone():
        return False
    game = conn.execute("SELECT sport, kickoff_utc FROM games WHERE id = ?",
                        (game_id,)).fetchone()
    if game is None or (sport is not None and game["sport"] != sport):
        return False
    stamp = utcnow()
    if only_before_its_listed_start:
        try:
            listed_at = db.instant(game["kickoff_utc"])
        except ValueError:
            return False
        if listed_at is not None and not db.instant(stamp) < listed_at:
            return False
    evidence = under_way_evidence(state, game["kickoff_utc"], db.instant(stamp))
    if evidence is None:
        return False
    try:
        conn.execute(
            f"INSERT INTO {UNDER_WAY_TABLE} (game_id, under_way_utc, sport,"
            " feed_status, evidence) VALUES (?, ?, ?, ?, ?)",
            (game_id, stamp, game["sport"],
             str(state.get("status_raw") or state.get("status")), evidence))
    except sqlite3.IntegrityError as exc:
        # ANOTHER POLL GOT THERE FIRST, between the look and the insert: its
        # row stands, as the rule says.
        if "first seen under way once" in str(exc):
            return False
        raise
    conn.commit()
    return True


def record_poll(conn: sqlite3.Connection, sport: str, requests: int,
                seen: int, changed: int) -> None:
    """RATE HONESTY. What this poll asked for, written down every time.

    A poller that cannot say how many requests it made is a poller nobody can
    hold to a rate, and "it only runs during games" is a claim about code
    rather than a measurement until there is a row per run to count.
    """
    conn.execute(
        "INSERT INTO live_polls (polled_utc, sport, requests, games_seen,"
        " games_changed) VALUES (?,?,?,?,?)",
        (utcnow(), sport, requests, seen, changed),
    )


def poll(conn: sqlite3.Connection, now: datetime | None = None,
         fetcher=None, resolver=None) -> dict:
    """One pass. Makes NO requests when no window is open.

    `fetcher` and `resolver` are injectable so the tests can prove the request
    count exactly rather than by inspection -- the claim "zero requests on a
    quiet day" is worth nothing if the only evidence is reading the code.
    """
    now = now or datetime.now(timezone.utc)
    fetcher = fetcher or scoreboard
    windows = open_windows(conn, now)
    report = {"windows": len(windows), "requests": 0, "seen": 0,
              "changed": 0, "finals": 0, "sports": [], "resolved": None,
              "first_under_way": []}
    if not windows:
        # THE QUIET-DAY PATH, and it returns before touching the network. Not
        # "fetches and discards", not "fetches with a long cache": makes no
        # request at all.
        return report

    finished: list[str] = []
    for window in windows:
        day = window.first_kickoff.strftime("%Y%m%d")
        requests = seen = changed = 0
        try:
            payload = fetcher(conn, window.sport, day)
            requests = 1
        except Exception as exc:  # noqa: BLE001 - a poll that fails is a poll
            record_poll(conn, window.sport, 1, 0, 0)
            report["sports"].append(
                {"sport": window.sport, "error": f"{type(exc).__name__}: {exc}"})
            report["requests"] += 1
            continue

        wanted = set(window.games)
        for state in payload:
            game_id = state.get("game_id")
            if game_id not in wanted:
                # THE PAYLOAD'S OTHER GAMES ARE SEEN TOO (Q38's prover,
                # 2026-10-07). The window holds the games listed within ten
                # minutes of now (`open_windows`), but the request is the
                # whole day's scoreboard, so this poll also holds what the
                # feed says of a game listed later -- and a game truly under
                # way before its listed start, a stale listing, is the case
                # operator question 38 (A) was ruled for. As first built the
                # poll looked past such a game until its window opened, so
                # its in-play reads were claimed, closed on and priced (its
                # status still 'scheduled') until ten minutes before its
                # listed start. Its first-under-way instant is written here,
                # by the same evidence, while its listed start is still
                # ahead and only for a game the record files under this
                # scoreboard's sport; nothing else about it is written (its
                # status, score and clock wait for its window, as before),
                # and no request is added.
                if record_first_under_way(conn, game_id, state,
                                          only_before_its_listed_start=True,
                                          sport=window.sport):
                    report["first_under_way"].append(game_id)
                continue
            seen += 1
            if apply_event(conn, game_id, state):
                changed += 1
            # THE FIRST POLL THAT SEES IT TRULY UNDER WAY (operator question
            # 38 (A), 2026-10-07), once per game, by the feed's own fields.
            if record_first_under_way(conn, game_id, state):
                report["first_under_way"].append(game_id)
            if state.get("status") == "final":
                finished.append(game_id)
        conn.commit()
        record_poll(conn, window.sport, requests, seen, changed)
        report["requests"] += requests
        report["seen"] += seen
        report["changed"] += changed
        report["sports"].append({"sport": window.sport, "requests": requests,
                                 "seen": seen, "changed": changed})
    conn.commit()

    report["finals"] = len(finished)
    if finished and resolver is not None:
        # THE POLLER DOES NOT SETTLE ANYTHING. It calls the one resolver, which
        # is idempotent and is the only thing that writes an outcome. Without
        # this a result waits up to four hours for the scheduled resolve; with
        # it, the record still has exactly one path to an outcome.
        report["resolved"] = resolver(conn)
    return report


def rate(conn: sqlite3.Connection, hours: int = 24) -> dict:
    """Requests per hour over a window, for the schedule panel."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    row = conn.execute(
        "SELECT COUNT(*) AS polls, COALESCE(SUM(requests), 0) AS requests,"
        " MAX(polled_utc) AS last"
        " FROM live_polls WHERE polled_utc >= ?", (cutoff,)).fetchone()
    requests = row["requests"] or 0
    return {
        "hours": hours,
        "polls": row["polls"] or 0,
        "requests": requests,
        "per_hour": round(requests / hours, 2) if hours else 0.0,
        "last_utc": row["last"],
    }
