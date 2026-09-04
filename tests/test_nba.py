"""S3: basketball.

The centre of gravity here is availability, because it is both the factor that
matters most in this sport and the one easiest to get quietly wrong. The wrong
version — reading who actually played from the box score of the game being
predicted — fits beautifully and is unavailable on a Tuesday night in November.
The tests below pin the definition to information that exists BEFORE tip in both
regimes, and pin the asymmetry that remains to the safe direction.

Two other things are tested because both were real bugs caught by the model's own
bookkeeping rather than by a test, and a bug caught once should not need catching
twice:

  * `nba_back_to_back` never fired, because a back-to-back is a game the night
    after a game and "days since" reads 1, not 0.
  * Neutral sites derived from the modal ARENA NAME flagged 26 renames as
    neutral. Comparing cities is what a rename does not change.
"""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import audit, calibration, config, db, resolve
from gridiron.data import nba_loader, nba_repo
from gridiron.factors import compute, registry
from gridiron.market import sources
from gridiron.sports import nba


# --- the shape of the questions ---------------------------------------------

def test_the_spread_ladder_never_pushes():
    """Every rung ends in .5, so a prediction resolves 0 or 1 and never a tie."""
    for rung in nba.SPREAD_LADDER:
        assert abs(rung * 2) % 2 == 1, f"{rung} can push"


def test_the_ladder_is_spaced_for_basketball_not_copied_from_football():
    """A four-point NBA spread is close to a coin flip where a four-point NFL
    spread is not, so the rungs are spaced for the sport rather than copied.

    THE TEST CHANGED ON 2026-09-03 AND THE PROPERTY DID NOT. It used to assert
    that the NBA ladder reached further than football's, which stopped being
    true when football's was extended to -15.5 for the same rule. Reach was
    never the point -- both ladders now reach as far as their own sport's
    expected margins go. What distinguishes them is SPACING, and the NBA's is
    still the wider of the two.
    """
    from gridiron.model import questions as nfl_questions

    def widest_gap(ladder):
        rungs = sorted(ladder)
        return max(b - a for a, b in zip(rungs, rungs[1:]))

    assert widest_gap(nba.SPREAD_LADDER) >= widest_gap(nfl_questions.SPREAD_LADDER)
    assert nba.SPREAD_LADDER != nfl_questions.SPREAD_LADDER, (
        "the NBA ladder is football's, copied"
    )


def test_nba_declares_three_game_markets_and_four_prop_markets():
    """THREE GAME MARKETS from 2026-09-04: the moneyline and the total joined
    the spread, as MARKET_ROSTER entries 1 and 2.

    The moneyline is first in the tuple because it is the question with
    nothing to choose -- no rung, no ladder, no floor -- and because a slate
    whose expected margin falls off the declared ladder still gets one.
    """
    assert set(config.SPORT_MARKETS["nba"]) - set(
        config.SPORT_PROP_MARKETS["nba"]) == {"spread", "moneyline", "total"}
    assert config.SPORT_MARKETS["nba"][0] == "moneyline"
    assert set(config.SPORT_PROP_MARKETS["nba"]) == {
        "points", "rebounds", "assists", "threes"
    }


def test_each_prop_market_is_its_own_category(nba_league):
    """Four markets, four gates, four curves. Merging them would be the exact
    thing LAW 4's no-merged-curves rule forbids."""
    for market in config.SPORT_PROP_MARKETS["nba"]:
        with pytest.raises(calibration.CrossSportAggregation):
            calibration.curve(
                nba_league, sport="all", market_type="prop", prop_type=market
            )
        payload = calibration.curve(
            nba_league, sport="nba", market_type="prop", prop_type=market
        )
        assert payload["filters"]["prop_type"] == market


def test_a_player_is_asked_at_most_one_question_per_game(nba_league):
    """Four questions about the same man on the same night are four correlated
    rows dressed up as four observations."""
    questions = nba.slate_questions(nba_league, 2025, 3)
    props = [q for q in questions if q.market_type == "prop"]
    seen = [(q.game_id, q.player_id) for q in props]
    assert len(seen) == len(set(seen))


def test_the_prop_budget_spreads_across_games_rather_than_stars(nba_league):
    """A global sort by minutes hands every slot to the highest-minutes players
    in the league — on a real NBA week, the same three dozen stars every time.
    The record would then be about those players rather than about the model,
    and their rows would be correlated week to week. Round-robin across games
    spends the same budget on the whole league."""
    from collections import Counter

    questions = nba.slate_questions(nba_league, 2025, 3)
    props = [q for q in questions if q.market_type == "prop"]
    per_game = Counter(q.game_id for q in props)
    assert max(per_game.values()) - min(per_game.values()) <= 1, dict(per_game)


def test_the_prop_stat_rotates_rather_than_sorting(nba_league):
    """A real bug: taking the first stat after sorting asked every player about
    assists forever, and three of the four markets sat permanently empty while
    looking merely unlucky. Alphabetical order is not a sampling strategy."""
    questions = nba.slate_questions(nba_league, 2025, 3)
    stats = {q.stat for q in questions if q.market_type == "prop"}
    assert len(stats) > 1, f"only {stats} were ever asked"


# --- availability, which is the whole sport ---------------------------------

def test_availability_uses_only_information_that_exists_before_tip(nba_league):
    """The measurement must not read the box score of the game being predicted.

    Planted directly: a rotation player is given a huge line in the game itself.
    If availability were reading that game, the number would move. It must not.
    """
    game = nba_league.execute(
        "SELECT * FROM games WHERE sport='nba' AND season=2025 AND week=3 LIMIT 1"
    ).fetchone()
    on_date = nba_repo.game_date(nba_league, game["id"])
    before, _n = nba.availability(nba_league, game["home"], on_date)

    nba_league.execute(
        "UPDATE nba_player_games SET minutes = 48, points = 90 WHERE game_id = ?",
        (game["id"],),
    )
    nba_league.commit()
    after, _n = nba.availability(nba_league, game["home"], on_date)
    assert before == after, (
        "availability changed when the game being predicted changed, so it is "
        "reading the future"
    )


def test_a_rotation_player_missing_from_the_last_game_lowers_availability(nba_league):
    game = nba_league.execute(
        "SELECT * FROM games WHERE sport='nba' AND season=2025 AND week=3 LIMIT 1"
    ).fetchone()
    on_date = nba_repo.game_date(nba_league, game["id"])
    full, _n = nba.availability(nba_league, game["home"], on_date)

    last = nba_repo.team_recent(nba_league, game["home"], on_date, limit=1)[0]
    biggest = nba_league.execute(
        "SELECT player_id FROM nba_player_games WHERE game_id = ? AND team = ?"
        " ORDER BY minutes DESC LIMIT 1",
        (last["game_id"], game["home"]),
    ).fetchone()["player_id"]
    nba_league.execute(
        "DELETE FROM nba_player_games WHERE game_id = ? AND player_id = ?",
        (last["game_id"], biggest),
    )
    nba_league.commit()

    reduced, _n = nba.availability(nba_league, game["home"], on_date)
    assert reduced < full


def test_the_injury_report_can_only_remove_availability_never_add_it(nba_league):
    """The forward path sees the injury report and the backtest does not, so the
    fitted coefficient must come from the WEAKER measurement. That is only safe
    if the report can subtract and never add."""
    game = nba_league.execute(
        "SELECT * FROM games WHERE sport='nba' AND season=2025 AND week=3 LIMIT 1"
    ).fetchone()
    on_date = nba_repo.game_date(nba_league, game["id"])
    without, _n = nba.availability(nba_league, game["home"], on_date)

    player = nba_repo.rotation(nba_league, game["home"], on_date)[0]
    nba_league.execute(
        "INSERT OR REPLACE INTO nba_injuries (player_id, player_name, team,"
        " status, detail, fetched_utc) VALUES (?,?,?,'Out','out',?)",
        (999001, player["player_name"], game["home"], db.utcnow()),
    )
    nba_league.commit()
    with_report, _n = nba.availability(nba_league, game["home"], on_date)
    assert with_report <= without


def test_availability_is_absent_not_one_when_there_is_no_history(nba_league):
    """A club with no window has UNKNOWN availability, and 1.0 would claim a
    full roster. That is the explicit-absent rule (D2) in its most consequential
    place."""
    share, n = nba.availability(nba_league, "ZZZ", "2025-11-01")
    assert share is None and n == 0


# --- the two bugs the bookkeeping caught ------------------------------------

def test_days_of_rest_is_rest_not_days_since_the_last_game(nba_league):
    """A back-to-back is a game the night after a game, so the dates are one day
    apart. `nba_back_to_back` tested for zero and never fired; the fit reported
    it constant across 4,911 rows. Rest is the quantity the factor is named for,
    so rest is what the accessor returns."""
    team = nba_league.execute(
        "SELECT team, game_date FROM nba_team_games ORDER BY game_date DESC LIMIT 1"
    ).fetchone()
    day_after = _plus_days(team["game_date"], 1)
    assert nba_repo.days_of_rest(nba_league, team["team"], day_after) == 0
    assert nba_repo.days_of_rest(nba_league, team["team"], _plus_days(team["game_date"], 3)) == 2


def test_the_back_to_back_factor_actually_fires():
    from gridiron.factors import nba as nba_factors

    class Ctx:
        home_rest_days = 0
        away_rest_days = 2

    assert nba_factors.nba_back_to_back(Ctx()) == -1.0
    Ctx.home_rest_days, Ctx.away_rest_days = 2, 0
    assert nba_factors.nba_back_to_back(Ctx()) == 1.0
    Ctx.home_rest_days, Ctx.away_rest_days = 1, 1
    assert nba_factors.nba_back_to_back(Ctx()) == 0.0


def test_a_renamed_arena_is_not_a_neutral_site(conn):
    """The first derivation took each club's modal ARENA NAME as its home and
    flagged 26 renames in one season as neutral-site games — a factor fitted on
    that would have been measuring sponsorship deals. Cities do not rename."""
    venues = [
        ("g1", "PHX", "Phoenix"),
        ("g2", "PHX", "Phoenix"),   # same city, the building was renamed
        ("g3", "PHX", "Phoenix"),
        ("g4", "PHX", "Mexico City"),
    ]
    for game_id, home, _city in venues:
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " status) VALUES (?, 'nba', 2025, 1, 'REG', ?, 'LAL', 'scheduled')",
            (game_id, home),
        )
        conn.execute(
            "INSERT INTO game_conditions (game_id, stadium, neutral_site,"
            " div_game) VALUES (?, 'x', 0, 0)", (game_id,)
        )
    conn.commit()
    flagged = nba_loader.mark_neutral_sites(conn, 2025, venues)
    assert flagged == 1
    neutral = conn.execute(
        "SELECT game_id FROM game_conditions WHERE neutral_site = 1"
    ).fetchall()
    assert [r["game_id"] for r in neutral] == ["g4"]


# --- the factors ------------------------------------------------------------

def test_every_nba_factor_is_namespaced_and_carries_a_rationale():
    factors = [f for f in registry.all_factors() if f.sport == "nba"]
    # 17 and 10 from 2026-09-03: `nba_asked_distance` was declared and
    # `nba_asked_line` retired in its place, so the spread set gains a factor
    # and the ACTIVE count stays where it was.
    # 21 ON 2026-09-04 (roster #2): the totals market declared three of its
    # own -- an asked-distance, a volatility and an availability SUM. A total
    # is not a directional question, so it takes sums where the spread takes
    # differences, and that is why they are new factors rather than the
    # existing ones widened.
    # 18 LATER THE SAME DAY (Session D): `nba_srs_diff`, the opponent-adjusted
    # rating, declared BESIDE `nba_net_rating_rolling` rather than replacing
    # it, so this one is a genuine addition and the active count moves too.
    assert len(factors) == 21
    assert len([f for f in factors if "spread" in f.applies_to]) == 11
    assert len([f for f in factors if "total" in f.applies_to]) == 5
    assert len([f for f in factors if "prop" in f.applies_to]) == 7
    assert sum(f.active for f in factors) == 19, (
        "nba_back_to_back is deactivated in favour of nba_b2b_either"
    )
    for f in factors:
        assert f.name.startswith("nba_"), f"{f.name} would collide across sports"
        assert len(f.rationale) > 80, f"{f.name} has a token rationale"
        if not f.active:
            assert f.note and f.deactivated_utc, (
                f"{f.name} is inactive with no dated note saying why"
            )


def test_the_home_court_factor_can_actually_vary():
    """MLB's equivalent was deactivated for returning 1.0 to everything. This one
    reads the neutral-site flag, which is the shape NFL's home_field uses and the
    only shape that fits anything."""
    from gridiron.factors import nba as nba_factors

    class Ctx:
        neutral_site = False

    assert nba_factors.nba_home_court(Ctx()) == 1.0
    Ctx.neutral_site = True
    assert nba_factors.nba_home_court(Ctx()) == 0.0


def test_rest_is_clipped_so_the_all_star_break_does_not_swamp_it():
    from gridiron.factors import nba as nba_factors

    class Ctx:
        home_rest_days = 9
        away_rest_days = 0

    assert nba_factors.nba_rest_days_diff(Ctx()) == 4.0


def test_a_prop_factor_that_cannot_be_measured_is_absent_not_zero():
    from gridiron.factors import nba as nba_factors

    class Ctx:
        minutes_mean = None
        usage_rate = None
        stat_per_minute = None
        opponent_allowance = None
        league_allowance = None
        teammate_volume = None
        team_availability = None
        rolling_mean = None
        rolling_sd = None
        line_asked = None

    for fn in (
        nba_factors.nba_prop_minutes,
        nba_factors.nba_prop_usage,
        nba_factors.nba_prop_rate,
        nba_factors.nba_prop_opponent_allowance,
        nba_factors.nba_prop_teammate_competition,
        nba_factors.nba_prop_mean_vs_line,
        nba_factors.nba_prop_volatility,
    ):
        assert fn(Ctx()) is None, fn.__name__


def test_the_prop_model_is_told_which_rung_of_the_line_it_was_asked():
    """The prop equivalent of nba_asked_line, and it was missing from the first
    fit. Lines are set at one of three pre-declared offsets around the player's
    rolling mean, so without knowing WHICH offset was asked the model averages
    three different questions into one answer — and it converges and looks fine
    while doing it."""
    from gridiron.factors import nba as nba_factors

    class Ctx:
        rolling_mean = 20.0
        rolling_sd = 4.0
        line_asked = 14.5

    low = nba_factors.nba_prop_mean_vs_line(Ctx())
    Ctx.line_asked = 25.5
    high = nba_factors.nba_prop_mean_vs_line(Ctx())
    assert low > 0 > high, "the factor must tell a soft line from a hard one"


def test_a_vector_that_defaults_an_absent_nba_factor_is_caught(nba_league):
    q = [
        x
        for x in nba.slate_questions(nba_league, 2025, 3, include_props=False)
    ][0]
    fv, _ctx = nba.build_features(nba_league, q)
    fv.absent.append("nba_availability_index")
    fv.values["nba_availability_index"] = 0.0
    with pytest.raises(compute.MissingDataDefaulted):
        compute.assert_missing_is_explicit(fv)


# --- resolution -------------------------------------------------------------

def test_a_player_who_did_not_appear_voids_rather_than_resolving_under(nba_league):
    """The VOID rule, as in NFL props. A man who did not play did not answer the
    question either way, and scoring it as an under would credit the model for a
    roster decision it never forecast."""
    game = nba_league.execute(
        "SELECT * FROM games WHERE sport='nba' AND status='final' LIMIT 1"
    ).fetchone()
    pred = _fake_prop(nba_league, game["id"], player_id=987654, stat="points")
    with pytest.raises(resolve.Void):
        nba.resolve_outcome(nba_league, pred)


def test_a_spread_resolves_against_the_rung_it_was_asked_at(nba_league):
    game = nba_league.execute(
        "SELECT * FROM games WHERE sport='nba' AND status='final'"
        " AND home_score IS NOT NULL LIMIT 1"
    ).fetchone()
    margin = game["home_score"] - game["away_score"]
    pred = _fake_spread(nba_league, game["id"], line=-4.5, side="cover")
    assert nba.resolve_outcome(nba_league, pred) == (1 if margin - 4.5 > 0 else 0)


def _fake_spread(conn, game_id, line, side):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?, 'nba', ?, 'spread', (SELECT home FROM games WHERE id=?),"
        " ?, 0.55, ?, 'statistical', ?, '{}', 'x')",
        (db.utcnow(), game_id, game_id, line, side, config.FACTOR_SET_VERSION),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM predictions ORDER BY id DESC LIMIT 1"
    ).fetchone()


def _fake_prop(conn, game_id, player_id, stat):
    import json

    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?, 'nba', ?, 'prop', ?, 'Nobody', 20.5, 0.55, 'over',"
        " 'statistical', ?, ?, 'x')",
        (
            db.utcnow(), game_id, stat, config.FACTOR_SET_VERSION,
            json.dumps({"question": {"player_id": str(player_id)}}),
        ),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM predictions ORDER BY id DESC LIMIT 1"
    ).fetchone()


def _plus_days(day: str, n: int) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


# --- the season that has not started ----------------------------------------

def test_an_unstarted_season_says_when_it_starts(nba_league):
    """An empty tab that says nothing reads as broken. One that names the date
    is merely early."""
    note = nba.first_slate_note(nba_league, 2026)
    assert note is not None
    assert note["state"] == "preseason"
    assert note["days_away"] >= 0
    assert str(note["days_away"]) in note["message"]
    assert note["first_game_utc"][:4] == "2026"


def test_a_started_season_has_no_such_note(nba_league):
    assert nba.first_slate_note(nba_league, 2025) is None


# --- laws -------------------------------------------------------------------

def test_the_nba_prediction_closure_cannot_reach_the_market():
    report = audit.check_all_prediction_closures()["nba"]
    reached = [m for m in report.modules if m.startswith("gridiron.market")]
    assert reached == [], report.path_to(reached[0]) if reached else None
    assert len(report.modules) > 1


def test_the_nba_spread_has_a_named_source_and_the_props_have_none():
    spread = sources.for_market("nba", "spread")
    assert spread["available"] is True
    assert spread["licence"]
    for market in config.SPORT_PROP_MARKETS["nba"]:
        assert sources.for_market("nba", market)["available"] is False


@pytest.mark.parametrize(
    "espn_spread, home_moneyline",
    [
        (-6.5, -218),    # CHA hosting as a favourite
        (15.5, 900),     # WSH hosting as a heavy underdog
        (-18.5, -2100),
        (14.5, 700),
        (-1.5, -122),
    ],
)
def test_the_stored_spread_agrees_with_the_moneyline_about_who_is_favoured(
    espn_spread, home_moneyline
):
    """Two conventions collide here and the first version got it half right.

    ESPN writes the spread from the home side the ordinary way — negative means
    the home team gives points. Our column stores the home team's expected
    MARGIN, nflverse's convention, which is the opposite sign. Flipping only
    when ESPN also flagged the home team as favourite produced correct numbers
    for home favourites and sign-reversed ones for home underdogs: a mistake
    that reverses the market comparison on about half of all games and is
    invisible in the data.

    The cross-check is the point. A stored spread and a moneyline must agree
    about which side is favoured; these are real pairs from 2026-04-10.
    """
    from gridiron.market import espn

    stored = espn._home_spread({"spread": espn_spread})
    assert (stored > 0) == (home_moneyline < 0), (
        f"spread {stored:+} and moneyline {home_moneyline:+} disagree about the "
        "favourite"
    )


@pytest.mark.parametrize("sport", ["nba", "mlb"])
def test_every_alias_maps_a_foreign_name_onto_one_of_ours(sport):
    """The invariant that would have caught the bug structurally.

    An alias exists to translate ESPN's spelling into ours, so its KEY must be a
    name we do not use and its VALUE must be one we do. The first NBA map got
    two entries wrong in ways that were silent: `NOP -> NO` was written
    backwards, so New Orleans never matched, and `PHX -> PHO` rewrote a code the
    two feeds already agree on, so Phoenix stopped matching too. Both violate
    this rule; neither raised anything at the time.
    """
    from gridiron.market import espn

    ours = espn.OUR_TRICODES[sport]
    for foreign, mine in espn.ABBREVIATION_ALIASES[sport].items():
        assert mine in ours, f"{sport}: alias points at {mine!r}, which we never use"
        assert foreign not in ours, (
            f"{sport}: alias rewrites {foreign!r}, which is already one of ours"
        )


def test_a_missing_spread_stays_missing():
    from gridiron.market import espn

    assert espn._home_spread({}) is None


def test_a_basketball_figure_never_carries_another_sports_prediction(nba_league):
    calibration.assert_single_sport(
        calibration.scorecard(nba_league, sport="nba"), "nba"
    )
