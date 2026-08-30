"""Shared fixtures.

Tests run against a temporary database seeded with a small synthetic league, so
the suite is deterministic and needs no network. Tests that want the real
nflverse data are marked `slow` and say so.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from gridiron import db

TEAMS = ["KC", "BUF", "SF", "PHI", "DAL", "MIA", "SEA", "GB"]


@pytest.fixture
def db_path(tmp_path):
    """The file the test database lives in. The API layer takes a path rather
    than a connection, because it opens one per worker thread."""
    return tmp_path / "test.db"


@pytest.fixture
def conn(db_path) -> sqlite3.Connection:
    c = db.open_db(db_path)
    yield c
    c.close()


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def league(conn) -> sqlite3.Connection:
    """A synthetic 8-team season: weeks 1-16 played, weeks 17-18 scheduled.

    Sixteen played weeks is enough for `baseline.train` to accept the sample,
    which matters: the production guard refuses to fit on fewer than fifty
    games and the fixture should not be exempt from it.

    Scores are generated from a fixed per-team strength so the statistical model
    has a real signal to find, and from a fixed seed so it finds the same one
    every run.
    """
    import random

    rng = random.Random(20260828)
    strength = {t: s for t, s in zip(TEAMS, [7, 5, 4, 2, 0, -2, -4, -6])}
    # Anchored to the clock rather than to a fixed date, so that the fixture is
    # INTERNALLY CONSISTENT: the sixteen played weeks are behind us and the two
    # scheduled weeks are ahead. A fixture that dated an unplayed game in the
    # past described a state a live database cannot be in, and the blind-first
    # check that a forecast precedes its own kickoff had nothing to stand on.
    start = datetime.now(timezone.utc).replace(
        hour=17, minute=0, second=0, microsecond=0
    ) - timedelta(days=7 * 16 - 3)

    with conn:
        for week in range(1, 19):
            order = list(TEAMS)
            rng.shuffle(order)
            kickoff = start + timedelta(days=7 * (week - 1))
            for i in range(0, len(order), 2):
                away, home = order[i], order[i + 1]
                gid = f"2025_{week:02d}_{away}_{home}"
                played = week <= 16
                if played:
                    margin = strength[home] - strength[away] + 2.0 + rng.gauss(0, 9)
                    home_pts = max(0, int(round(21 + margin / 2)))
                    away_pts = max(0, int(round(21 - margin / 2)))
                else:
                    home_pts = away_pts = None
                conn.execute(
                    "INSERT INTO games (id, season, week, game_type, kickoff_utc, home, away,"
                    " status, home_score, away_score) VALUES (?,?,?,'REG',?,?,?,?,?,?)",
                    (
                        gid,
                        2025,
                        week,
                        _iso(kickoff),
                        home,
                        away,
                        "final" if played else "scheduled",
                        home_pts,
                        away_pts,
                    ),
                )
                conn.execute(
                    "INSERT INTO game_conditions (game_id, home_rest, away_rest, roof,"
                    " surface, neutral_site, div_game, stadium) VALUES (?,?,?,?,?,0,0,?)",
                    (gid, 7, 7, "outdoors", "grass", f"{home} Field"),
                )
                # The loader would have split these out of the same upstream
                # row; the fixture does the same so the market half has
                # something to snapshot.
                conn.execute(
                    "INSERT INTO market_lines_raw (game_id, fetched_utc, source,"
                    " spread_line, total_line) VALUES (?,?,'fixture',?,?)",
                    (
                        gid,
                        _iso(kickoff),
                        round((strength[home] - strength[away] + 2.0) * 2) / 2,
                        44.5,
                    ),
                )
                if played:
                    for team, opp, pf, pa in (
                        (home, away, home_pts, away_pts),
                        (away, home, away_pts, home_pts),
                    ):
                        conn.execute(
                            "INSERT INTO team_week_stats (season, week, team, game_id, opponent,"
                            " points_for, points_against, plays) VALUES (?,?,?,?,?,?,?,?)",
                            (2025, week, team, gid, opp, pf, pa, rng.randint(55, 72)),
                        )
                        conn.execute(
                            "INSERT INTO player_week_stats (season, week, player_id, player_name,"
                            " position, team, opponent, attempts, completions, passing_yards,"
                            " passing_tds, carries, rushing_yards, rushing_tds, targets,"
                            " receptions, receiving_yards, receiving_tds)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                2025,
                                week,
                                f"QB-{team}",
                                f"{team} Quarterback",
                                "QB",
                                team,
                                opp,
                                33,
                                21,
                                220 + rng.gauss(0, 45),
                                1,
                                3,
                                12,
                                0,
                                0,
                                0,
                                0,
                                0,
                            ),
                        )
                        conn.execute(
                            "INSERT INTO player_week_stats (season, week, player_id, player_name,"
                            " position, team, opponent, attempts, completions, passing_yards,"
                            " passing_tds, carries, rushing_yards, rushing_tds, targets,"
                            " receptions, receiving_yards, receiving_tds)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                2025,
                                week,
                                f"WR-{team}",
                                f"{team} Receiver",
                                "WR",
                                team,
                                opp,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                8,
                                5,
                                62 + rng.gauss(0, 25),
                                0,
                            ),
                        )

    # This fixture is a BACKTEST database and says so, because that is what it
    # is: every test needing a resolvable prediction forecasts a week already
    # played. Declaring it lets the live rule - a forecast must precede its own
    # kickoff - stay strict in production instead of being loosened to
    # accommodate fixtures. The test that exercises the live rule sets `kind`
    # to live itself.
    db.set_meta(conn, "kind", "backtest")
    db.set_meta(
        conn,
        "kind_note",
        "Synthetic test fixture. Predictions here are written about games "
        "already played and are not a record of anything.",
    )
    conn.commit()
    return conn


@pytest.fixture
def a_prediction(league):
    """One written prediction, for the immutability and snapshot-order tests."""
    cur = league.execute(
        "INSERT INTO predictions (created_utc, game_id, market_type, subject, line_asked,"
        " model_prob, model_side, predictor, factor_set_version, factors_json, reasoning)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            db.utcnow(),
            league.execute(
                "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
            ).fetchone()["id"],
            "spread",
            "KC",
            -3.5,
            0.58,
            "cover",
            "statistical",
            "fs1",
            '{"home_field": 1}',
            "test fixture",
        ),
    )
    league.commit()
    return cur.lastrowid



MLB_CLUBS = ["NYY", "BOS", "LAD", "SFG", "CHC", "STL", "HOU", "SEA"]


@pytest.fixture
def mlb_league(conn) -> sqlite3.Connection:
    """A synthetic 8-club baseball season: 19 days played, day 20 scheduled.

    Built to exercise the two things baseball tests need and football's fixture
    cannot supply — a daily cadence with real rest gaps, and a slate where SOME
    starting pitchers are announced and some are not. Two of the four games on
    day 20 have no probable starter on either side, which is the state a real
    slate is in when the loader runs early.
    """
    import random

    rng = random.Random(1789)
    strength = {club: 0.5 + 0.06 * (4 - i) for i, club in enumerate(MLB_CLUBS)}
    # Anchored to the clock for the same reason the football fixture is: day 20
    # is the slate still to be played, so it has to be in the future.
    start = datetime.now(timezone.utc).replace(
        hour=23, minute=10, second=0, microsecond=0
    ) - timedelta(days=18)

    pitchers = {}
    for i, club in enumerate(MLB_CLUBS):
        for j in range(2):
            pid = 1000 + i * 10 + j
            pitchers.setdefault(club, []).append(pid)

    for day in range(1, 21):
        date = start + timedelta(days=day - 1)
        clubs = MLB_CLUBS[:]
        rng.shuffle(clubs)
        for pair in range(0, len(clubs), 2):
            home, away = clubs[pair], clubs[pair + 1]
            gid = f"mlb_2025_{day:03d}_{home}_{away}"
            played = day < 20
            hs = a_s = None
            if played:
                edge = strength[home] - strength[away] + 0.04
                hs = max(0, int(rng.gauss(4.5 + 4 * edge, 2.5)))
                a_s = max(0, int(rng.gauss(4.5 - 4 * edge, 2.5)))
                if hs == a_s:
                    hs += 1
            conn.execute(
                "INSERT INTO games (id, sport, season, week, game_type, home, away,"
                " kickoff_utc, status, home_score, away_score, league_date) VALUES"
                " (?, 'mlb', 2025, ?, 'REG', ?, ?, ?, ?, ?, ?, ?)",
                (
                    gid, day, home, away, _iso(date),
                    "final" if played else "scheduled", hs, a_s, _iso(date)[:10],
                ),
            )
            if played:
                for team, opp, is_home, rf, ra in (
                    (home, away, 1, hs, a_s), (away, home, 0, a_s, hs)
                ):
                    conn.execute(
                        "INSERT INTO mlb_team_games (game_id, team, opponent, season,"
                        " game_date, is_home, runs_for, runs_against, innings_played)"
                        " VALUES (?,?,?,2025,?,?,?,?,9.0)",
                        (gid, team, opp, _iso(date)[:10], is_home, rf, ra),
                    )
            # Starters are announced for the played days and for HALF of the
            # final slate, so the unannounced case is present in the fixture
            # rather than only in production.
            announced = played or pair < 4
            if announced:
                for side, club in (("home", home), ("away", away)):
                    pid = pitchers[club][day % 2]
                    conn.execute(
                        "INSERT INTO mlb_probables (game_id, side, pitcher_id,"
                        " pitcher_name, recorded_utc) VALUES (?,?,?,?,?)",
                        (gid, side, pid, f"P{pid}", _iso(date)),
                    )
                    if played:
                        conn.execute(
                            "INSERT INTO mlb_pitcher_starts (pitcher_id, season,"
                            " game_date, game_pk, is_start, innings, runs,"
                            " earned_runs, batters_faced) VALUES (?,2025,?,?,1,?,?,?,?)",
                            (
                                pid, _iso(date)[:10], day * 100 + pid,
                                5.0 + rng.random() * 2, rng.randint(0, 5),
                                rng.randint(0, 4), rng.randint(18, 28),
                            ),
                        )
    # This fixture is a BACKTEST database and says so, because that is what it
    # is: every test that needs a resolvable prediction forecasts a week that
    # has already been played. Declaring it lets the live rule — a forecast must
    # precede its own kickoff — stay strict in production instead of being
    # loosened to accommodate the fixtures. The one test that exercises the live
    # rule sets `kind` to live itself.
    db.set_meta(conn, "kind", "backtest")
    db.set_meta(
        conn,
        "kind_note",
        "Synthetic test fixture. Predictions here are written about games "
        "already played and are not a record of anything.",
    )
    conn.commit()
    return conn



NBA_CLUBS = ["BOS", "LAL", "DEN", "MIL", "PHX", "MIA", "GSW", "NYK"]


@pytest.fixture
def nba_league(conn) -> sqlite3.Connection:
    """A synthetic 8-club basketball season plus an unstarted next one.

    Season 2025 is played out over four weeks on a real daily cadence, so
    back-to-backs occur naturally and `days_of_rest` has something to measure.
    Season 2026 is scheduled and untouched, so `first_slate_note` has an
    unstarted season to describe.

    Nine players per club, with a minutes distribution that gives a genuine
    rotation: five starters above the twelve-minute rotation floor, and four
    reserves straddling it.
    """
    import random

    rng = random.Random(58008)
    strength = {club: 6.0 - 1.5 * i for i, club in enumerate(NBA_CLUBS)}
    start = datetime.now(timezone.utc).replace(
        hour=1, minute=0, second=0, microsecond=0
    ) - timedelta(days=30)

    roster = {
        club: [(3000 + i * 20 + j, f"{club} Player {j}", 34.0 - 3.0 * j)
               for j in range(9)]
        for i, club in enumerate(NBA_CLUBS)
    }

    day = 0
    for week in range(1, 5):
        for slot in range(4):          # four game days a week
            day += 2 if slot % 2 else 1   # produces genuine back-to-backs
            when = start + timedelta(days=day)
            clubs = NBA_CLUBS[:]
            rng.shuffle(clubs)
            for pair in range(0, len(clubs), 2):
                home, away = clubs[pair], clubs[pair + 1]
                gid = f"nba_2025_{day:03d}_{home}_{away}"
                edge = strength[home] - strength[away] + 3.0
                hs = max(70, int(rng.gauss(112 + edge / 2, 11)))
                as_ = max(70, int(rng.gauss(112 - edge / 2, 11)))
                if hs == as_:
                    hs += 1
                conn.execute(
                    "INSERT INTO games (id, sport, season, week, game_type, home,"
                    " away, kickoff_utc, status, home_score, away_score)"
                    " VALUES (?, 'nba', 2025, ?, 'REG', ?, ?, ?, 'final', ?, ?)",
                    (gid, week, home, away, _iso(when), hs, as_),
                )
                conn.execute(
                    "INSERT INTO game_conditions (game_id, stadium, neutral_site,"
                    " div_game) VALUES (?, ?, 0, 0)",
                    (gid, f"{home} Arena"),
                )
                for team, opp, is_home, pf, pa in (
                    (home, away, 1, hs, as_), (away, home, 0, as_, hs)
                ):
                    conn.execute(
                        "INSERT INTO nba_team_games (game_id, team, opponent,"
                        " season, game_date, is_home, points_for, points_against,"
                        " minutes, fga, fta, oreb, turnovers)"
                        " VALUES (?,?,?,2025,?,?,?,?,240,?,?,?,?)",
                        (
                            gid, team, opp, _iso(when)[:10], is_home, pf, pa,
                            rng.randint(84, 96), rng.randint(16, 28),
                            rng.randint(8, 14), rng.randint(10, 18),
                        ),
                    )
                    # Eight of the nine play; the ninth is a healthy scratch, so
                    # availability has a real absence to find.
                    for pid, name, mpg in roster[team][:8]:
                        minutes = max(6.0, rng.gauss(mpg, 3.0))
                        conn.execute(
                            "INSERT INTO nba_player_games (game_id, player_id,"
                            " player_name, team, opponent, season, game_date,"
                            " is_home, minutes, points, rebounds, assists,"
                            " threes, fga, fta, threes_att, turnovers)"
                            " VALUES (?,?,?,?,?,2025,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                gid, pid, name, team, opp, _iso(when)[:10],
                                is_home, round(minutes, 1),
                                max(0, int(rng.gauss(minutes * 0.55, 5))),
                                max(0, int(rng.gauss(minutes * 0.17, 2))),
                                max(0, int(rng.gauss(minutes * 0.13, 2))),
                                max(0, int(rng.gauss(minutes * 0.07, 1))),
                                max(1, int(rng.gauss(minutes * 0.45, 3))),
                                max(0, int(rng.gauss(minutes * 0.12, 2))),
                                max(0, int(rng.gauss(minutes * 0.20, 2))),
                                max(0, int(rng.gauss(minutes * 0.05, 1))),
                            ),
                        )

    # An unstarted season, so the preseason note has something to describe.
    future = datetime.now(timezone.utc) + timedelta(days=45)
    for i in range(0, len(NBA_CLUBS), 2):
        home, away = NBA_CLUBS[i], NBA_CLUBS[i + 1]
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'nba', 2026, 1, 'REG',"
            " ?, ?, ?, 'scheduled', ?)",
            (f"nba_2026_001_{home}_{away}", home, away, _iso(future),
             _iso(future)[:10]),
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# a skip that reads green is the vacuous verifier in new clothes
# ---------------------------------------------------------------------------

#: The only reasons a browser test may skip. Anything else is a test that found
#: nothing, called it fine, and reported a green dot.
#:
#: This exists because one did exactly that. `test_model_and_market_are_told_
#: apart_by_form_not_colour` looked for `.rail-dot`, which a redesign had
#: renamed to `.dot`, found nothing, and skipped with "no card on this slate
#: carries a market comparison". It read as a pass for as long as it took
#: somebody to look at the summary line. A skip must name an ABSENT CAPABILITY
#: — no browser, no network — never an absent selector or an empty fixture.
ALLOWED_SKIP_REASONS = (
    "chromium unavailable",
    "playwright is not installed",
    "playwright not installed",
)


def pytest_runtest_makereport(item, call):
    """Turn an unexplained browser skip into a failure.

    Hooked at report time so it catches `pytest.skip()` raised anywhere in the
    test body, not only a decorator.
    """
    import pytest as _pytest

    if call.when != "call" or call.excinfo is None:
        return
    if not call.excinfo.errisinstance(_pytest.skip.Exception):
        return
    if "browser" not in [m.name for m in item.iter_markers()]:
        return
    reason = str(call.excinfo.value).lower()
    if any(allowed in reason for allowed in ALLOWED_SKIP_REASONS):
        return
    raise AssertionError(
        f"{item.name} skipped with an unallowed reason: {call.excinfo.value!r}. "
        "A browser test may skip only when a CAPABILITY is missing (no chromium, "
        "no playwright). Skipping because a selector matched nothing or a fixture "
        "was empty is a test that asserts nothing and reports green — which is "
        "how a renamed selector went unnoticed. Fix the selector or the fixture, "
        "or add the reason to ALLOWED_SKIP_REASONS with a note saying why."
    )
