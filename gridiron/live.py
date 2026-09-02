"""The live poll: what is happening right now, and nothing else.

WHAT THIS IS ALLOWED TO TOUCH. `games` — the score, the period, the clock and
the status. That is data about the world, not a claim about it, and updating
it is permitted (LAW 3 governs `predictions`, which nothing here writes).

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
        rows = conn.execute(
            "SELECT id, kickoff_utc, status FROM games"
            " WHERE sport = ? AND kickoff_utc IS NOT NULL AND status != 'final'"
            "   AND kickoff_utc >= ? AND kickoff_utc <= ?",
            (sport,
             (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             (now + WINDOW_LEAD).strftime("%Y-%m-%dT%H:%M:%SZ")),
        ).fetchall()
        live = []
        for row in rows:
            kickoff = _parse(row["kickoff_utc"])
            if kickoff is None:
                continue
            if kickoff - WINDOW_LEAD <= now <= kickoff + timedelta(hours=hours):
                live.append(row["id"])
        if live:
            kickoffs = [_parse(r["kickoff_utc"]) for r in rows
                        if r["id"] in set(live)]
            kickoffs = [k for k in kickoffs if k]
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


def _read_mlb(payload: dict) -> list[dict]:
    """statsapi's schedule, hydrated with the linescore, in this shape."""
    out = []
    for date in payload.get("dates") or []:
        for game in date.get("games") or []:
            line = game.get("linescore") or {}
            teams = line.get("teams") or {}
            state = MLB_STATES.get(
                (game.get("status") or {}).get("abstractGameState"))
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
                "status_raw": (game.get("status") or {}).get("detailedState"),
                "home_score": (teams.get("home") or {}).get("runs"),
                "away_score": (teams.get("away") or {}).get("runs"),
                # BASEBALL HAS NO CLOCK. Absent rather than an empty string:
                # the tile shows the inning alone, which is the whole of what
                # the sport has to say about how far along it is.
                "period": period,
                "clock": None,
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
              "changed": 0, "finals": 0, "sports": [], "resolved": None}
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
                continue
            seen += 1
            if apply_event(conn, game_id, state):
                changed += 1
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
