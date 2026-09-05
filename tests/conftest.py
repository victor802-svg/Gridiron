"""Shared fixtures.

Tests run against a temporary database seeded with a small synthetic league, so
the suite is deterministic and needs no network. Tests that want the real
nflverse data are marked `slow` and say so.
"""

from __future__ import annotations

import os
import socket
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from gridiron import api, auth, db, resolve, run
from gridiron.factors import store
from gridiron.model import baseline

try:                                   # the browser suite is optional
    from playwright import sync_api as playwright_api
except ImportError:                    # pragma: no cover
    playwright_api = None

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


def seed_league(conn) -> sqlite3.Connection:
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
def league(conn) -> sqlite3.Connection:
    """The synthetic league, built per test."""
    return seed_league(conn)


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

# ---------------------------------------------------------------------------
# THE BROWSER FIXTURES
# ---------------------------------------------------------------------------
#
# They lived in `test_smoke.py` until the desk suite needed them. A fixture
# defined in a test module is visible only inside that module, so a second file
# asking for `page` errors with "fixture not found" -- which reads like a
# missing dependency and is really a scoping rule.
#
# `served` builds a synthetic league, trains it, runs two weeks and resolves
# them, then serves the real app against it. It is the most expensive fixture
# in the suite and function-scoped on purpose: a browser test that mutated
# shared state would otherwise decide what the next one sees.

SMOKE_TOKEN = "smoke-token-for-the-browser-suite"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

# ---------------------------------------------------------------------------
# THE BROWSER SUITE'S SHARED WORLD
# ---------------------------------------------------------------------------
#
# MEASURED 2026-09-01: seventy-seven tests take a browser fixture, and every
# one of them rebuilt the entire world first -- a sixteen-week synthetic
# league, six fitted models, three slates of predictions, a resolution pass, a
# uvicorn server, a fresh Chromium and a login. The assertions were never the
# cost. The setup was, seventy-seven times over.
#
# So the expensive half is built ONCE per session and the cheap half stays per
# test. What each test still gets entirely to itself:
#
#   * a fresh browser CONTEXT -- its own cookies, its own storage, its own
#     session id. That is what actually isolates one browser test from the
#     next, and it costs milliseconds rather than seconds.
#   * the API's database pointer, re-asserted before every test. This is the
#     shared state the audit was for: `api.set_database` is a MODULE-LEVEL
#     GLOBAL, and `test_api` and `test_auth` legitimately point it at their
#     own databases and then at None. Without re-asserting, a browser test
#     that happened to run after one of those would talk to a server pointing
#     at nothing, and fail a long way from the cause.
#
# A test that needs to CHANGE the world asks for `served_fresh`, which is the
# old fixture unchanged -- so needing isolation is said out loud.


def _build_world(conn) -> None:
    """The seeding every browser test used to do for itself."""
    store.sync_registry(conn)
    # Six markets: the spread plus each prop type, fitted separately.
    baseline.train_all(conn, (2025,), l2=1.0, note="smoke", min_rows=20)
    run.run_week(conn, 2025, 7, include_props=True, use_llm=False)
    run.run_week(conn, 2025, 8, include_props=True, use_llm=False)
    resolve.resolve_all(conn)
    # A slate that has NOT been played, so the picks tab has live cards. The
    # rail, the pick sentence and the tier chip only exist before a result:
    # a settled card shows its verdict instead, per the approved mockup.
    run.run_week(conn, 2025, 18, include_props=True, use_llm=False)
    _seed_llm_row_with_a_code_name(conn)
    conn.commit()


def _seed_llm_row_with_a_code_name(conn) -> None:
    """One LLM forecast whose reasoning quotes a factor by its CODE NAME.

    THE DEFECT, PUT INTO THE FIXTURE ON PURPOSE (2026-09-05). The prompt used
    to name factors by their code names and the model quoted them back: 27 of
    65 stored rows carried `ufc_scheduled_rounds`, `mlb_bullpen_recent_load`
    or `mean_vs_line` onto a card. LAW 3 forbids editing what a forecaster
    said, so the repair is at RENDER time -- and a render-time repair can only
    be tested against a row that needs it.

    WITHOUT THIS THE BROWSER SUITE HAS NOTHING TO LOOK AT. Its league is seeded
    with `use_llm=False`, so the second forecaster's view was empty in every
    test -- which is the other half of why this went unnoticed for weeks: the
    scan could not have caught it even if somebody had pointed it at the view.
    """
    row = conn.execute(
        "SELECT game_id, market_type, subject, line_asked, factor_set_version"
        "  FROM predictions WHERE predictor = 'statistical'"
        "   AND market_type = 'spread' ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return
    conn.execute(
        "INSERT INTO predictions (created_utc, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (db.utcnow(), row["game_id"], row["market_type"], row["subject"],
         # STRONG on purpose: Picks opens filtered to STRONG, so a SOLID row
         # would be hidden by the default and the view the render test exists
         # to look at would be empty again.
         row["line_asked"], 0.78, "cover", "llm", row["factor_set_version"],
         '{"prob_yes": 0.61}',
         "The home side is the stronger team here: srs_diff is well positive "
         "and recent_form_diff agrees with it, while travel_kmiles is small "
         "enough not to matter."))


def _serve(db_file):
    """A uvicorn server on its own port, and the thread running it."""
    import uvicorn

    api.set_database(db_file)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(api.app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while time.time() < deadline and not server.started:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the server did not start within 20s")
    return f"http://127.0.0.1:{port}", server, thread


@pytest.fixture(scope="session")
def _shared_world(tmp_path_factory):
    """One league, one database, one server, for the whole browser suite."""
    db_file = tmp_path_factory.mktemp("browser") / "test.db"
    previous = os.environ.get(auth.TOKEN_VAR)
    os.environ[auth.TOKEN_VAR] = SMOKE_TOKEN
    conn = db.open_db(db_file)
    seed_league(conn)
    _build_world(conn)
    base, server, thread = _serve(db_file)
    yield {"base": base, "db": db_file}
    server.should_exit = True
    thread.join(timeout=10)
    conn.close()
    api.set_database(None)
    if previous is None:
        os.environ.pop(auth.TOKEN_VAR, None)
    else:
        os.environ[auth.TOKEN_VAR] = previous


@pytest.fixture
def served(_shared_world):
    """The shared server's URL, with the database pointer re-asserted."""
    api.set_database(_shared_world["db"])
    os.environ[auth.TOKEN_VAR] = SMOKE_TOKEN
    return _shared_world["base"]


@pytest.fixture(scope="function")
def served_fresh(league, db_path, monkeypatch):
    """A world of its own, for a test that needs to change it.

    This is the fixture every browser test used to get, kept unchanged for the
    ones that genuinely need an untouched database.
    """
    import uvicorn

    monkeypatch.setenv(auth.TOKEN_VAR, SMOKE_TOKEN)

    store.sync_registry(league)
    # Six markets: the spread plus each prop type, fitted separately.
    baseline.train_all(league, (2025,), l2=1.0, note="smoke", min_rows=20)
    run.run_week(league, 2025, 7, include_props=True, use_llm=False)
    run.run_week(league, 2025, 8, include_props=True, use_llm=False)
    resolve.resolve_all(league)
    # A slate that has NOT been played, so the picks tab has live cards. The
    # rail, the pick sentence and the tier chip only exist before a result:
    # a settled card shows its verdict instead, per the approved mockup.
    run.run_week(league, 2025, 18, include_props=True, use_llm=False)
    league.commit()

    api.set_database(db_path)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(api.app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 20
    while time.time() < deadline and not server.started:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the server did not start within 20s")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
    api.set_database(None)


@pytest.fixture(scope="session")
def _browser():
    """ONE CHROMIUM for the whole suite.

    Launching a browser costs about a second and seventy-seven of them cost a
    minute and a half of pure process startup. A CONTEXT is what isolates two
    tests from each other -- separate cookies, storage and session id -- and a
    context costs milliseconds. So the browser is shared and the context is
    not.
    """
    if playwright_api is None:
        pytest.skip("playwright is not installed")
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {exc}; run `playwright install chromium`")
        yield browser
        browser.close()


@pytest.fixture
def page(served, _browser):
    browser = _browser
    # 1120, NOT 1280, and the number matters. 1280 is exactly the desk
    # breakpoint, so this fixture sat on the boundary: the moment the
    # desk shipped, eight tests written about the COMPACT ROWS were
    # handed a grid of tiles and failed on markup they were never
    # about. The row suite runs at a row width; `test_desk.py` sets
    # its own viewport for the desk, and D4 renders both.
    context = browser.new_context(viewport={"width": 1120, "height": 900})
    page = context.new_page()
    page.console_errors = []
    page.page_errors = []
    page.on("console", lambda m: page.console_errors.append(m.text)
            if m.type == "error" else None)
    page.on("pageerror", lambda e: page.page_errors.append(str(e)))
    # Sign in the way a person does, through the real login page. Every
    # route is behind the gate (P3), so without this the browser lands on
    # /login and every assertion below fails for the wrong reason. It also
    # means the login flow is exercised by every browser test rather than
    # only by the one that names it.
    page.goto(served + "/login", wait_until="networkidle")
    page.fill("#token", SMOKE_TOKEN)
    page.click("#submit")
    page.wait_for_url(served + "/", timeout=15000)
    page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
    yield page
    # THE CONTEXT CLOSES, NOT THE BROWSER. Closing the context is what
    # discards this test's cookies, storage and signed-in session; the
    # browser process is the expensive part and is reused.
    context.close()

# ---------------------------------------------------------------------------
# THE NETWORK IS SHUT UNLESS A TEST SAYS OTHERWISE
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS, and it is not a hypothetical. Two tests in `test_refresh.py`
# stubbed three sports' loaders and not the fourth, so every run fetched an
# entire college football season from ESPN. They took 416 and 353 seconds --
# between them, three quarters of the whole suite. Nothing failed. Nothing was
# marked slow. They simply took six and a half minutes each, for weeks.
#
# The test directly above them stubs all four loaders and carries a comment
# explaining exactly this trap, written when it was found the first time. The
# lesson was recorded in prose and applied by hand to one of the three places
# it belonged. So this is the mechanism version: a test cannot reach the
# network at all unless it says it needs to, and the ones that say so are
# NAMED in the run's output rather than blending in.
#
# Loopback stays open. The browser suite drives a real uvicorn server over
# 127.0.0.1, and that is not "the network" in any sense this guard cares
# about -- it is the app under test.

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

#: Tests that declared `@pytest.mark.network` and therefore ran with the
#: outside world reachable. Reported at the end of the session.
_WENT_OUTSIDE: list[str] = []


class NetworkBlocked(RuntimeError):
    """A test reached for the network without saying it would."""


def _is_loopback(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("utf-8", "replace")
    return str(host) in _LOOPBACK


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    """Shut the network for every test that has not declared it needs it."""
    if request.node.get_closest_marker("network"):
        _WENT_OUTSIDE.append(request.node.nodeid)
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create = socket.create_connection

    def _refuse(where, address):
        raise NetworkBlocked(
            f"{request.node.nodeid} tried to reach {address} through {where}. "
            f"Tests run with the network shut: stub the source, or mark the "
            f"test `@pytest.mark.network` if it genuinely needs the outside "
            f"world. Two tests that quietly fetched a whole football season "
            f"cost this suite thirteen minutes a run."
        )

    def guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if not _is_loopback(host):
            _refuse("socket.connect", address)
        return real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if not _is_loopback(host):
            _refuse("socket.connect_ex", address)
        return real_connect_ex(self, address, *args, **kwargs)

    def guarded_create(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if not _is_loopback(host):
            _refuse("socket.create_connection", address)
        return real_create(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: this test genuinely reaches the outside world. It will be "
        "named in the run's summary.",
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """NAME the tests that went outside. A count would not be enough.

    The gate's own rule is that a tier which was not run has to be named
    rather than merely counted; the same applies to tests that left the
    building. If this list grows, it should grow visibly.
    """
    if not _WENT_OUTSIDE:
        return
    terminalreporter.write_sep("-", "tests that reached the network")
    for node in sorted(set(_WENT_OUTSIDE)):
        terminalreporter.write_line(f"  {node}")
