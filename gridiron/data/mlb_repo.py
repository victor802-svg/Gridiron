"""Read-only MLB accessors for the prediction path.

Same two guarantees as `data.repo`:

1. **No market data.** Nothing here selects a price, and the words do not
   appear. The LAW 1 scan walks this module as part of MLB's own closure.
2. **No future data.** Every historical query takes an explicit date cutoff and
   returns only rows strictly BEFORE it. A factor cannot read the result of the
   game it is predicting because the query does not return it.

The cutoff is a date rather than a week because a baseball season is a
continuous calendar, and two games on the same day must not see each other.
"""

from __future__ import annotations

import sqlite3

#: Rolling windows, declared here so the factor rationales can cite them.
STARTER_WINDOW = 10       # starts
OFFENSE_WINDOW = 15       # games
BULLPEN_WINDOW_DAYS = 3   # days

#: A batter's own recent form. Fifteen games is roughly two and a half weeks of
#: baseball -- long enough that a two-hit night does not dominate it, short
#: enough to still be about the player's current shape rather than his April.
BATTER_WINDOW = 15
#: The opposing club's strikeout rate, over a longer window: a team's plate
#: discipline is a property of its roster and moves slowly.
TEAM_RATE_WINDOW = 30

#: Which column on `mlb_batter_games` each batting market resolves from.
#: One table, so a market cannot be scored against a column it was not asked
#: about.
BATTER_STAT_COLUMN = {
    "batter_hits": "hits",
    "batter_total_bases": "total_bases",
    "batter_home_runs": "home_runs",
}


def game(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT g.*, c.stadium FROM games g"
        " LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.id = ? AND g.sport = 'mlb'",
        (game_id,),
    ).fetchone()


def games_on_day(conn: sqlite3.Connection, season: int, day: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT g.*, c.stadium FROM games g"
        " LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.sport = 'mlb' AND g.season = ? AND g.week = ?"
        " ORDER BY g.kickoff_utc, g.id",
        (season, day),
    ).fetchall()


def game_date(conn: sqlite3.Connection, game_id: str) -> str | None:
    """The LEAGUE's own calendar date for this game, which is the cutoff every
    rolling window must use.

    NOT the UTC date, and the difference is not cosmetic. A game tipping at
    02:00 UTC is the previous evening where it is played, so its own row in the
    game log is dated the day before its `kickoff_utc`. Cutting a window at
    `game_date < utc_date` therefore let the game being predicted into its own
    rolling form, availability and pace — 76.8% of NBA games and 25.1% of MLB
    ones. The model was reading the result it was forecasting.

    Falls back to the UTC date only when no league date was recorded, which is
    the pre-migration case; the loaders now always write one.
    """
    row = conn.execute(
        "SELECT league_date, substr(kickoff_utc, 1, 10) AS utc_date"
        " FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()
    if row is None:
        return None
    return row["league_date"] or row["utc_date"]

def probables(conn: sqlite3.Connection, game_id: str) -> dict[str, sqlite3.Row]:
    """Announced starters by side. An empty dict means not yet announced, which
    is a fact about the world and is recorded as one."""
    return {
        r["side"]: r
        for r in conn.execute(
            "SELECT * FROM mlb_probables WHERE game_id = ?", (game_id,)
        )
    }


def starter_recent(
    conn: sqlite3.Connection, pitcher_id: int, before_date: str, limit: int = STARTER_WINDOW
) -> list[sqlite3.Row]:
    """The pitcher's most recent STARTS before the cutoff, newest first."""
    return conn.execute(
        "SELECT * FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND is_start = 1 AND game_date < ?"
        " ORDER BY game_date DESC LIMIT ?",
        (pitcher_id, before_date, limit),
    ).fetchall()


def starter_last_appearance(
    conn: sqlite3.Connection, pitcher_id: int, before_date: str
) -> str | None:
    row = conn.execute(
        "SELECT MAX(game_date) AS d FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND game_date < ?",
        (pitcher_id, before_date),
    ).fetchone()
    return row["d"] if row and row["d"] else None


def team_recent(
    conn: sqlite3.Connection, team: str, before_date: str, limit: int = OFFENSE_WINDOW
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM mlb_team_games WHERE team = ? AND game_date < ?"
        " ORDER BY game_date DESC LIMIT ?",
        (team, before_date, limit),
    ).fetchall()


def team_games_between(
    conn: sqlite3.Connection, team: str, start_date: str, before_date: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM mlb_team_games"
        " WHERE team = ? AND game_date >= ? AND game_date < ? ORDER BY game_date",
        (team, start_date, before_date),
    ).fetchall()


def starter_innings_in_game(
    conn: sqlite3.Connection, game_id: str, team: str
) -> float | None:
    """Innings thrown by the announced starter in a completed game.

    Used to derive relief innings as (innings played - starter innings). Where
    the starter's own log is missing, this returns None and the bullpen factor
    is ABSENT for that game rather than assuming a full start.
    """
    side = conn.execute(
        "SELECT CASE WHEN home = ? THEN 'home' ELSE 'away' END AS side"
        " FROM games WHERE id = ?",
        (team, game_id),
    ).fetchone()
    if side is None:
        return None
    probable = conn.execute(
        "SELECT pitcher_id FROM mlb_probables WHERE game_id = ? AND side = ?",
        (game_id, side["side"]),
    ).fetchone()
    if probable is None or probable["pitcher_id"] is None:
        return None
    date = game_date(conn, game_id)
    row = conn.execute(
        "SELECT innings FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND game_date = ? AND is_start = 1 LIMIT 1",
        (probable["pitcher_id"], date),
    ).fetchone()
    return row["innings"] if row else None


def park_run_environment(
    conn: sqlite3.Connection, stadium: str | None, season: int
) -> tuple[float | None, int]:
    """Runs per game at this venue in PRIOR seasons, and the games behind it.

    Measured rather than taken from a published table, for two reasons: a
    measurement is reproducible from data already loaded, and restricting it to
    seasons strictly before the one being predicted makes it cutoff-safe by
    construction. Returns (runs_per_game, n_games); `n` is returned, never
    hidden, because a park with forty games behind it and one with four hundred
    are not the same number (LAW 4).
    """
    if not stadium:
        return None, 0
    row = conn.execute(
        "SELECT AVG(t.runs_for + t.runs_against) AS rpg, COUNT(*) AS n"
        " FROM mlb_team_games t"
        " JOIN games g ON g.id = t.game_id"
        " JOIN game_conditions c ON c.game_id = g.id"
        " WHERE c.stadium = ? AND g.season < ? AND t.is_home = 1",
        (stadium, season),
    ).fetchone()
    if row is None or not row["n"]:
        return None, 0
    return float(row["rpg"]), int(row["n"])


def league_run_environment(conn: sqlite3.Connection, season: int) -> float | None:
    row = conn.execute(
        "SELECT AVG(runs_for + runs_against) AS rpg, COUNT(*) AS n"
        " FROM mlb_team_games t JOIN games g ON g.id = t.game_id"
        " WHERE g.season < ? AND g.season >= ? AND t.is_home = 1",
        (season, season - 3),
    ).fetchone()
    if row is None or not row["n"]:
        return None
    return float(row["rpg"])


# ---------------------------------------------------------------------------
# players
#
# Every function here takes `before_date` and returns only rows strictly before
# it, for the same reason the team functions do: the cutoff is what stops a
# factor reading the result of the game it is predicting. That failure is not
# hypothetical here -- cutting on the UTC date rather than the league date let
# 25.1% of MLB games into their own rolling windows.
# ---------------------------------------------------------------------------

def batter_recent(
    conn: sqlite3.Connection,
    player_id: int,
    before_date: str,
    limit: int = BATTER_WINDOW,
) -> list[sqlite3.Row]:
    """The batter's most recent games before the cutoff, newest first."""
    return conn.execute(
        "SELECT * FROM mlb_batter_games WHERE player_id = ? AND game_date < ?"
        " ORDER BY game_date DESC, game_pk DESC LIMIT ?",
        (player_id, before_date, limit),
    ).fetchall()


def batter_rolling(
    conn: sqlite3.Connection,
    player_id: int,
    stat: str,
    before_date: str,
    limit: int = BATTER_WINDOW,
) -> tuple[float | None, float | None, int]:
    """(mean, standard deviation, n) for one batting stat over the window.

    Returns `(None, None, n)` when there is nothing to average. The SD is the
    sample SD and needs two games; with one it is None rather than zero, because
    a zero SD is a claim that the player is perfectly consistent and one game is
    not evidence of that.
    """
    column = BATTER_STAT_COLUMN.get(stat)
    if column is None:
        raise ValueError(f"no batting column for market {stat!r}")
    rows = batter_recent(conn, player_id, before_date, limit)
    values = [r[column] for r in rows if r[column] is not None]
    n = len(values)
    if not n:
        return None, None, 0
    mean = sum(values) / n
    if n < 2:
        return mean, None, n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, var ** 0.5, n


def batter_pa_per_game(
    conn: sqlite3.Connection, player_id: int, before_date: str,
    limit: int = BATTER_WINDOW,
) -> tuple[float | None, int]:
    """Plate appearances per game over the window: the volume instrument.

    THIS IS WHAT STANDS IN FOR TONIGHT'S LINEUP SLOT, and the substitution is
    forced rather than chosen. A scheduled game carries no lineup: measured
    2026-08-30, zero of 41 games across three future dates had one, because
    lineups post about two hours before first pitch and every earlier state is
    'Preview'. So the slot a batter will occupy tonight is not knowable when the
    forecast is written, and a factor reading it would be reading the future.

    Plate appearances per game IS knowable, it is a fact about games already
    played, and it carries the same information the slot carries -- a leadoff
    hitter gets more trips than a nine-hole hitter, and that shows up here
    directly instead of through a proxy.
    """
    rows = batter_recent(conn, player_id, before_date, limit)
    values = [r["plate_appearances"] for r in rows if r["plate_appearances"] is not None]
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def batter_recent_slot(
    conn: sqlite3.Connection, player_id: int, before_date: str, limit: int = 5
) -> tuple[float | None, int]:
    """The batter's average lineup slot in his most recent STARTS.

    Games he did not start are excluded rather than counted as slot zero: he did
    not have a slot, and averaging a nonexistent one towards the top of the
    order would say he bats higher than he does.
    """
    rows = conn.execute(
        "SELECT lineup_slot FROM mlb_batter_games"
        " WHERE player_id = ? AND game_date < ? AND lineup_slot IS NOT NULL"
        " ORDER BY game_date DESC, game_pk DESC LIMIT ?",
        (player_id, before_date, limit),
    ).fetchall()
    if not rows:
        return None, 0
    slots = [r["lineup_slot"] for r in rows]
    return sum(slots) / len(slots), len(slots)


def batter_handedness(conn: sqlite3.Connection, player_id: int) -> str | None:
    row = conn.execute(
        "SELECT bat_side FROM mlb_people WHERE player_id = ?", (player_id,)
    ).fetchone()
    return row["bat_side"] if row else None


def pitcher_handedness(conn: sqlite3.Connection, pitcher_id: int) -> str | None:
    row = conn.execute(
        "SELECT pitch_hand FROM mlb_people WHERE player_id = ?", (pitcher_id,)
    ).fetchone()
    return row["pitch_hand"] if row else None


def starter_suppression(
    conn: sqlite3.Connection, pitcher_id: int, before_date: str,
    limit: int = STARTER_WINDOW,
) -> dict:
    """A starter's recent strikeout and home-run rates, per batter faced.

    Per BATTER FACED rather than per nine innings, because these feed batter
    questions: what a hitter wants to know is what happens in one trip to the
    plate against this arm, not what happens over a notional nine innings the
    starter will not pitch.

    Home runs allowed can be NULL -- the boxscore path returns none for it. When
    it is, the rate is None and the factor is ABSENT, never zero. Zero home runs
    allowed is a real and different claim.
    """
    rows = conn.execute(
        "SELECT strike_outs, home_runs_allowed, batters_faced FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND is_start = 1 AND game_date < ?"
        " ORDER BY game_date DESC LIMIT ?",
        (pitcher_id, before_date, limit),
    ).fetchall()
    faced = sum((r["batters_faced"] or 0) for r in rows)
    if len(rows) < 3 or faced <= 0:
        return {"k_rate": None, "hr_rate": None, "n": len(rows), "faced": faced}

    ks = [r["strike_outs"] for r in rows if r["strike_outs"] is not None]
    hrs = [r["home_runs_allowed"] for r in rows if r["home_runs_allowed"] is not None]
    return {
        "k_rate": (sum(ks) / faced) if ks else None,
        # Only counted when EVERY start in the window reported it. A partial sum
        # over a full denominator would understate the rate and read as a
        # stingier pitcher than he is.
        "hr_rate": (sum(hrs) / faced) if len(hrs) == len(rows) else None,
        "n": len(rows),
        "faced": faced,
    }


def starter_workload(
    conn: sqlite3.Connection, pitcher_id: int, before_date: str,
    limit: int = STARTER_WINDOW,
) -> tuple[float | None, float | None, int]:
    """(mean strikeouts, SD, n) over recent starts -- the strikeout market's own
    form instrument."""
    rows = conn.execute(
        "SELECT strike_outs FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND is_start = 1 AND game_date < ?"
        " AND strike_outs IS NOT NULL ORDER BY game_date DESC LIMIT ?",
        (pitcher_id, before_date, limit),
    ).fetchall()
    values = [r["strike_outs"] for r in rows]
    n = len(values)
    if not n:
        return None, None, 0
    mean = sum(values) / n
    if n < 2:
        return mean, None, n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, var ** 0.5, n


def starter_innings_form(
    conn: sqlite3.Connection, pitcher_id: int, before_date: str,
    limit: int = STARTER_WINDOW,
) -> tuple[float | None, int]:
    """Innings per start over the window: how long he is being left in, which
    bounds how many strikeouts are even available to him."""
    rows = conn.execute(
        "SELECT innings FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND is_start = 1 AND game_date < ?"
        " AND innings IS NOT NULL ORDER BY game_date DESC LIMIT ?",
        (pitcher_id, before_date, limit),
    ).fetchall()
    if not rows:
        return None, 0
    return sum(r["innings"] for r in rows) / len(rows), len(rows)


def team_strikeout_rate(
    conn: sqlite3.Connection, team: str, before_date: str,
    limit: int = TEAM_RATE_WINDOW,
) -> tuple[float | None, int]:
    """The club's strikeouts per plate appearance over its recent games.

    Built from the batter rows rather than a team table, so it counts only
    players whose logs we actually hold; `n` is the number of games behind it
    and is returned rather than hidden.
    """
    rows = conn.execute(
        "SELECT game_date, SUM(strike_outs) AS k, SUM(plate_appearances) AS pa"
        " FROM mlb_batter_games WHERE team = ? AND game_date < ?"
        " GROUP BY game_date, game_pk ORDER BY game_date DESC LIMIT ?",
        (team, before_date, limit),
    ).fetchall()
    ks = sum((r["k"] or 0) for r in rows)
    pas = sum((r["pa"] or 0) for r in rows)
    if not rows or pas <= 0:
        return None, len(rows)
    return ks / pas, len(rows)


def batter_last_played(
    conn: sqlite3.Connection, player_id: int, before_date: str
) -> str | None:
    row = conn.execute(
        "SELECT MAX(game_date) AS d FROM mlb_batter_games"
        " WHERE player_id = ? AND game_date < ?",
        (player_id, before_date),
    ).fetchone()
    return row["d"] if row and row["d"] else None


def batter_stat_in_game(
    conn: sqlite3.Connection, player_id: int, game_pk: int, column: str
) -> tuple[bool, int | None]:
    """(the batter has a line for this game, the stat).

    The two are returned separately on purpose. No line at all means he did not
    play -- scratched, benched, rested -- and that VOIDS the question. A line
    with a zero in it means he played and did not do the thing, which settles
    it. Collapsing the two would score a roster decision as a correct under.
    """
    if column not in set(BATTER_STAT_COLUMN.values()):
        raise ValueError(f"{column!r} is not a resolvable batting column")
    row = conn.execute(
        f"SELECT {column} AS v FROM mlb_batter_games"
        " WHERE player_id = ? AND game_pk = ?",
        (player_id, game_pk),
    ).fetchone()
    if row is None:
        return False, None
    return True, row["v"]


def pitcher_start_in_game(
    conn: sqlite3.Connection, pitcher_id: int, game_pk: int
) -> tuple[bool, int | None]:
    """(he started this game, his strikeouts).

    A pitcher who was announced and then did not start -- scratched, rain, a
    bullpen game -- did not answer the question either way.
    """
    row = conn.execute(
        "SELECT is_start, strike_outs FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND game_pk = ?",
        (pitcher_id, game_pk),
    ).fetchone()
    if row is None or not row["is_start"]:
        return False, None
    return True, row["strike_outs"]


def counts(conn: sqlite3.Connection) -> dict:
    out = {}
    for table in ("mlb_probables", "mlb_pitcher_starts", "mlb_team_games",
                  "mlb_batter_games", "mlb_lineups", "mlb_people"):
        out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    row = conn.execute(
        "SELECT COUNT(*) AS n, SUM(CASE WHEN status='final' THEN 1 ELSE 0 END) AS final,"
        " MIN(season) AS a, MAX(season) AS b FROM games WHERE sport='mlb'"
    ).fetchone()
    out["games"] = row["n"]
    out["games_final"] = row["final"] or 0
    out["seasons"] = [row["a"], row["b"]]
    return out
