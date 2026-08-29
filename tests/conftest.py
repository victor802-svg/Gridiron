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
def conn(tmp_path) -> sqlite3.Connection:
    c = db.open_db(tmp_path / "test.db")
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
    start = datetime(2025, 9, 7, 17, 0, tzinfo=timezone.utc)

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
