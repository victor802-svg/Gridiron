"""A UFC category counts its own card's voids -- the card its curve counts --
through one door (2026-10-01).

The first of operator question 34's counts (ruled 2026-09-30: "every UFC
count is per card tier: tier table, ranker, taken record, edge figure, board
badge. Planting each."), built ahead of it because question 35's own voids
would make it false. Question 35's prover found it: `calibration.curve`
handed the card to `resolved` and not to `void_count`, so once Q35's tool
voids the eighteen final passes 1014-1031 (all Fight Night), each UFC
market's Contender Series category reads "voided 6, void rate 0.3", the
Numbered card category "voided 6, void rate 1.0" on 0 settled, and the line
under the Record page's chart ("0 resolved, 6 withdrawn", the Numbered
card's) with them -- only Fight Night's 6 is true.

`calibration.category_filter` is the one door a curve's rows and its void
count both read; `calibration.assert_each_void_count_is_its_cards`, inside
`calibration.blind_categories`, refuses a category whose void count is not
its card's (the API answers 500); `audit.check_a_ufc_void_count_is_its_cards`
runs it in gate step 2.
"""

from __future__ import annotations

import ast
import re

import pytest

from gridiron import audit, calibration, config, db, recount

REPO = config.PACKAGE_ROOT.parent
MARKETS = ("moneyline", "rounds", "distance")
REASON = ("withdrawn in this test: written at or after its bout's start, "
          "read as an instant")


def _card(conn, event: str, tier: str | None, bouts, *, week: int,
          kickoff: str, played: bool) -> None:
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES (?, ?, ?, 2026, ?, ?)",
        (event, f"UFC {event}", kickoff, db.utcnow(), tier))
    for bout in bouts:
        conn.execute(
            "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
            " fighter_a, fighter_b, status, fetched_utc)"
            " VALUES (?, ?, ?, 3, 'A', 'B', ?, ?)",
            (bout, event, kickoff, "final" if played else "scheduled",
             db.utcnow()))
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, 'ufc', 2026, ?, 'R', 'A', 'B', ?, ?, ?, ?, ?)",
            (bout, week, kickoff, "final" if played else "scheduled",
             kickoff[:10], 1 if played else None, 0 if played else None))


def _forecast(conn, bout: str, market: str, *, pass_kind: str, written: str,
              predictor: str = "statistical", sport: str = "ufc",
              subject: str = "A") -> int:
    line = 2.5 if market == "rounds" else None
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES (?, ?, ?, ?, ?, ?, 0.6, 'win', ?, ?, 'fs2', '{}', 'test',"
        " '2026-09-08T03:00:00Z', 1)",
        (written, sport, bout, market, subject, line, predictor, pass_kind))
    return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]


def _void(conn, prediction_id: int) -> None:
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc,"
                 " reason) VALUES (?, '2026-10-01T05:00:00Z', ?)",
                 (prediction_id, REASON))


def _the_eighteens_world(tmp_path):
    """THE SHAPE QUESTION 35'S VOIDS LEAVE: a Fight Night card of six bouts,
    each forecast in three markets by an early pass the day before and a
    final pass two seconds after its start, the eighteen finals withdrawn
    and their early passes standing; a Contender Series card of two settled
    bouts, none withdrawn; a Numbered card still to come, nothing forecast."""
    conn = db.open_db(tmp_path / "voids.db")
    fight_night = [f"fn{i}" for i in range(1, 7)]
    _card(conn, "fn", "fight_night", fight_night, week=1,
          kickoff="2026-09-05T19:00:00Z", played=True)
    _card(conn, "cs", "contender", ("cs1", "cs2"), week=2,
          kickoff="2026-09-06T23:00:00Z", played=True)
    _card(conn, "nc", "numbered", ("nc1",), week=3,
          kickoff="2026-10-03T23:00:00Z", played=False)
    eighteen = []
    for bout in fight_night:
        for market in MARKETS:
            _forecast(conn, bout, market, pass_kind="early",
                      written="2026-09-04T02:04:00Z")
            eighteen.append(_forecast(conn, bout, market, pass_kind="final",
                                      written="2026-09-05T19:00:02Z"))
    for bout in ("cs1", "cs2"):
        for market in MARKETS:
            _forecast(conn, bout, market, pass_kind="final",
                      written="2026-09-06T20:00:00Z")
    for pid in eighteen:
        _void(conn, pid)
    conn.commit()
    return conn, eighteen


def _statistical(categories, market):
    return {c["event_tier"]: c for c in categories
            if c["market"] == market and c["filters"]["predictor"] == "statistical"}


def _as_released(conn, *, sport, market_type=None, prop_type=None,
                 predictor=None, factor_set_version=None, event_tier=None):
    """THE VOID COUNT AS RELEASED (until 2026-10-01): the market's withdrawn
    forecasts on every card -- the card asked for is not read -- each with
    the card its bout was on."""
    where, params = ["p.sport = ?"], [sport]
    for column, value in (("market_type", market_type), ("prop_type", prop_type),
                          ("predictor", predictor),
                          ("factor_set_version", factor_set_version)):
        if value:
            where.append(f"p.{column} = ?")
            params.append(value)
    return [dict(r) for r in conn.execute(
        "SELECT p.id, (SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
        "   ON e.id = b.event_id WHERE b.id = p.game_id) AS event_tier"
        "  FROM prediction_voids v JOIN predictions p ON p.id = v.prediction_id"
        f" WHERE {' AND '.join(where)} ORDER BY p.id", params)]


def test_each_card_counts_its_own_voids(tmp_path):
    """Fight Night states its six withdrawn beside its six standing early
    passes; the Contender Series and the Numbered card state none -- where
    the released count said 6 beside each (void rate 0.75 and 1.0)."""
    conn, _ = _the_eighteens_world(tmp_path)
    categories = calibration.blind_categories(conn, sport="ufc")
    for market in MARKETS:
        got = _statistical(categories, market)
        assert set(got) == set(config.event_tiers("ufc"))
        said = {tier: (c["n"], c["voided"], c["void_rate"])
                for tier, c in got.items()}
        assert said == {"fight_night": (6, 6, 0.5), "contender": (2, 0, 0.0),
                        "numbered": (0, 0, None)}, (market, said)
        # the cards it counted, read off each withdrawn row's bout, and the
        # recount made without the door, beside each
        assert {tier: (c["void_tiers_counted"], c["voids_recounted"])
                for tier, c in got.items()} == {
            "fight_night": (["fight_night"], 6), "contender": ([], 0),
            "numbered": ([], 0)}
    for c in categories:
        if c["filters"]["predictor"] == "llm":
            assert (c["n"], c["voided"], c["void_rate"]) == (0, 0, None)
    conn.close()


def test_the_record_page_states_each_cards_own(tmp_path):
    """THE SCORECARD AND THE LINE UNDER THE CHART: the Record page's
    "Withdrawn" cells are its categories', and the line under the chart is
    the first category of the chosen market and forecaster
    (`findCurve` in app.js) -- the Numbered card's for UFC, "0 resolved"
    and no withdrawals, where it said "6 withdrawn"."""
    conn, _ = _the_eighteens_world(tmp_path)
    payload = calibration.scorecard(conn, sport="ufc")
    for market in MARKETS:
        drawn = next(c for c in payload["categories"] if c["market"] == market
                     and c["filters"]["predictor"] == "statistical")
        assert drawn["event_tier"] == config.event_tiers("ufc")[0] == "numbered"
        assert (drawn["n"], drawn["voided"]) == (0, 0)
    withdrawn = {(c["market"], c["event_tier"], c["filters"]["predictor"]):
                 c["voided"] for c in payload["categories"] if c["voided"]}
    assert withdrawn == {(m, "fight_night", "statistical"): 6 for m in MARKETS}
    # THE HEADLINE CURVE IS NOT MADE FOR UFC FROM 2026-10-08 (operator
    # question 34, ruled 2026-09-30: "every UFC count is per card tier"): it
    # was every card's moneyline as one population, with every card's 6
    # voids, drawn only where no category matched -- never for UFC, whose
    # every market, card and forecaster is a category. Until that date this
    # test held the pooled curve's 6 here, as the void row of CLAUDE.md
    # named it: question 34's ground.
    assert payload["headline"] is None
    conn.close()


def test_the_curve_and_its_void_count_ask_one_door(tmp_path, monkeypatch):
    """One door for a category's rows: the curve's settled rows and its void
    count are both asked of `category_filter`, with the same card."""
    conn, _ = _the_eighteens_world(tmp_path)
    asked = []
    real = calibration.category_filter

    def spy(**cell):
        asked.append(cell)
        return real(**cell)

    monkeypatch.setattr(calibration, "category_filter", spy)
    c = calibration.curve(conn, sport="ufc", market_type="moneyline",
                          predictor="statistical", event_tier="contender")
    assert len(asked) == 2
    assert asked[0] == asked[1]
    assert asked[0]["event_tier"] == "contender"
    assert (c["n"], c["voided"]) == (2, 0)
    # and the door's card is the curve's: each card's rows, none of another's
    for tier, n in (("fight_night", 6), ("contender", 0), ("numbered", 0)):
        terms, params = real(sport="ufc", market_type="rounds",
                             predictor="statistical", event_tier=tier)
        assert terms[0] == "p.sport = ?" and tier in params
        got = calibration.withdrawn_forecasts(
            conn, sport="ufc", market_type="rounds", predictor="statistical",
            event_tier=tier)
        assert len(got) == n and {r["event_tier"] for r in got} <= {tier}
    conn.close()


@pytest.mark.parametrize("planted,refused", [
    (_as_released, "counts 6 withdrawn forecasts on ['fight_night'] beside "
                   "the 'numbered' curve"),
    # THE FINDING ITSELF: the curve asks the door without the card
    ("without_the_card", "counts 6 withdrawn forecasts on ['fight_night'] "
                         "beside the 'numbered' curve"),
    # every card's withdrawals, each labelled the card asked for: only the
    # recount made without the door sees it
    ("named_as_asked", "counts 6 withdrawn where the recount made without "
                       "its door finds 0"),
], ids=["as_released", "without_the_card", "named_as_asked"])
def test_a_pooled_void_count_is_refused_by_the_builder_the_api_and_the_gate(
        tmp_path, monkeypatch, planted, refused):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn, _ = _the_eighteens_world(tmp_path)
    audit.check_a_ufc_void_count_is_its_cards(conn)              # lawful: passes
    audit.check_the_blind_outlook_is_never_pooled(conn)
    door = calibration.withdrawn_forecasts
    if planted == "without_the_card":
        planted = lambda conn, **kw: door(conn, **dict(kw, event_tier=None))  # noqa: E731
    elif planted == "named_as_asked":
        planted = lambda conn, **kw: [  # noqa: E731
            dict(r, event_tier=kw.get("event_tier"))
            for r in door(conn, **dict(kw, event_tier=None))]
    monkeypatch.setattr(calibration, "withdrawn_forecasts", planted)
    for build in (calibration.blind_categories, calibration.scorecard):
        with pytest.raises(calibration.PooledVoidCount, match=re.escape(refused)):
            build(conn, sport="ufc")
    with pytest.raises(audit.LawViolation,
                       match="A UFC VOID COUNT IS NOT ITS CARD'S") as exc:
        audit.check_a_ufc_void_count_is_its_cards(conn)
    assert "ufc: " in str(exc.value)
    # NOT FILED AS AN OUTLOOK'S POOL: the outlook's guard passed first
    audit.check_the_blind_outlook_is_never_pooled(conn)
    conn.close()
    # THE API ANSWERS 500 rather than serve it
    token = "test-token-for-the-void-count-per-card"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "voids.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            response = client.get("/api/scorecard", params={"sport": "ufc"})
    finally:
        api.set_database(None)
    assert response.status_code == 500
    assert "IN A CATEGORY'S VOID COUNT" in response.json()["detail"]


def test_a_pooled_void_count_is_refused_by_name(tmp_path):
    conn, _ = _the_eighteens_world(tmp_path)
    honest = {"sport": "ufc", "record": "rung",
              "categories": calibration.blind_categories(conn, sport="ufc")}
    conn.close()
    calibration.assert_each_void_count_is_its_cards(honest)       # lawful

    def at(tier):
        return next(i for i, c in enumerate(honest["categories"])
                    if c["market"] == "distance" and c["event_tier"] == tier
                    and c["filters"]["predictor"] == "statistical")

    def refused(tier, change, match):
        rows = [dict(c) for c in honest["categories"]]
        rows[at(tier)].update(change)
        with pytest.raises(calibration.PooledVoidCount, match=match):
            calibration.assert_each_void_count_is_its_cards(
                dict(honest, categories=rows))

    # THE RELEASED PAGE, after the voids: 6 beside the Numbered card's 0
    refused("numbered", dict(voided=6, void_rate=1.0,
                             void_tiers_counted=["fight_night"]),
            r"counts 6 withdrawn forecasts on \['fight_night'\] beside the "
            r"'numbered' curve")
    refused("contender", dict(voided=6, void_rate=0.75,
                              void_tiers_counted=["contender"]),
            "where the recount made without its door finds 0")
    refused("fight_night", dict(void_tiers_counted=["fight_night", None]),
            r"on \['fight_night', None\]")
    refused("fight_night", dict(void_tiers_counted=[]), r"on \[\] beside")
    refused("numbered", dict(void_tiers_counted=["numbered"]),
            r"counts 0 withdrawn forecasts on \['numbered'\]")
    refused("fight_night", dict(void_rate=0.3),
            "states a void rate of 0.3 where its own counts")
    refused("fight_night", dict(voids_recounted=None),
            "the recount made without its door finds None")
    for bad in (None, -1, True, 6.0):
        refused("numbered", dict(voided=bad), "not a count of withdrawn")
    # A SPORT THAT DOES NOT SPLIT BY CARD names none
    mlb = {"sport": "mlb", "record": "rung", "categories": [
        {"category": "moneyline / statistical", "event_tier": None, "n": 5,
         "voided": 1, "void_rate": round(1 / 6, 4),
         "void_tiers_counted": ["fight_night"], "voids_recounted": 1}]}
    with pytest.raises(calibration.PooledVoidCount, match="declares none"):
        calibration.assert_each_void_count_is_its_cards(mlb)
    mlb["categories"][0]["void_tiers_counted"] = []
    calibration.assert_each_void_count_is_its_cards(mlb)


def test_a_sport_that_does_not_split_by_card_counts_as_before(tmp_path):
    """Every other sport's void count is its market's and forecaster's, as
    it was: no card, and the recount agreeing."""
    conn = db.open_db(tmp_path / "mlb.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('m1', 'mlb', 2026, 1, 'R', 'SEA', 'HOU',"
        " '2026-09-07T23:05:00Z', 'final', '2026-09-07', 5, 3)")
    kept = _forecast(conn, "m1", "moneyline", pass_kind="final",
                     written="2026-09-07T21:05:00Z", sport="mlb",
                     subject="SEA")
    gone = _forecast(conn, "m1", "moneyline", pass_kind="final",
                     written="2026-09-07T21:05:00Z", sport="mlb",
                     predictor="llm", subject="SEA")
    _void(conn, gone)
    conn.commit()
    got = {c["filters"]["predictor"]: c
           for c in calibration.blind_categories(conn, sport="mlb")
           if c["market"] == "moneyline"}
    assert (got["llm"]["n"], got["llm"]["voided"], got["llm"]["void_rate"],
            got["llm"]["void_tiers_counted"], got["llm"]["voids_recounted"]) \
        == (0, 1, 1.0, [], 1)
    assert (got["statistical"]["n"], got["statistical"]["voided"]) == (1, 0)
    assert kept != gone
    # the recount's rows carry no card here
    assert [r["event_tier"] for r in recount.voids(conn, sport="mlb")] == [None]
    conn.close()


def test_a_bout_whose_card_the_source_left_unnamed_is_in_no_cards_count(tmp_path):
    """A card the source carries no tier for joins no category (R2): its
    withdrawn forecasts are counted beside no card's curve -- and a count
    that took them in would name them."""
    conn, _ = _the_eighteens_world(tmp_path)
    _card(conn, "xx", None, ("xx1",), week=4, kickoff="2026-09-12T23:00:00Z",
          played=True)
    _void(conn, _forecast(conn, "xx1", "moneyline", pass_kind="final",
                          written="2026-09-12T20:00:00Z"))
    conn.commit()
    got = _statistical(calibration.blind_categories(conn, sport="ufc"),
                       "moneyline")
    assert {t: c["voided"] for t, c in got.items()} == {
        "fight_night": 6, "contender": 0, "numbered": 0}
    door = calibration.withdrawn_forecasts
    pooled = [r for r in door(conn, sport="ufc", market_type="moneyline",
                              predictor="statistical")]
    assert {r["event_tier"] for r in pooled} == {"fight_night", None}
    conn.close()


def test_the_gate_makes_the_call():
    tree = ast.parse((REPO / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "step_2_guards")
    assert any(isinstance(n, ast.Attribute)
               and n.attr == "check_a_ufc_void_count_is_its_cards"
               for n in ast.walk(step))
