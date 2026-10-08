"""Every UFC count is per card tier: the tier table, the ranker, the taken
record, the edge figure and the board badge (operator question 34, ruled
2026-09-30: "every UFC count is per card tier: tier table, ranker, taken
record, edge figure, board badge. Planting each."; built 2026-10-08).

R2 of 2026-09-03 splits the UFC record by card because one curve over the
three "would average those and describe neither". The re-read of 29
September (finding G2) found these five counting the three cards as one:
the tier bands read 28/15/4/2 where Fight Night held 22/14/2/1 and the
Contender Series 6/1/2/1; the ranker "49 settled on the shortlist and 0 off
it" (39/0, 10/0, 0/0); the taken record's "every forecast 49"; the edge
figure's one count over three; and the board's badge, "49/100".

Each test here fails on c4014a9 (the release, `git archive`), whose doors
take no card and count every card's rows, and which has no guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from gridiron import audit, board, calibration, config, db, shortlist, views

SEASON = config.SPORT_CURRENT_SEASON["ufc"]
TIERS = config.event_tiers("ufc")

#: (card, bout, the model's number, outcome, the venue's implied number,
#: led its slate, taken) -- every count has another number on each card.
QUESTIONS = (
    ("fight_night", "fn_a", 0.55, 1, 0.45, True, True),
    ("fight_night", "fn_b", 0.65, 0, 0.64, False, False),
    ("fight_night", "fn_c", 0.75, 1, None, True, False),
    ("contender", "cs_a", 0.55, 1, 0.40, True, False),
    ("contender", "cs_b", 0.85, 1, None, True, False),
    ("numbered", "nc_a", 0.55, 0, 0.52, False, False),
)
CARDS = {"fight_night": ("ev_fn", 1, "2026-09-05T19:00:00Z"),
         "contender": ("ev_cs", 2, "2026-09-08T23:00:00Z"),
         "numbered": ("ev_nc", 3, "2026-09-19T21:00:00Z")}
BANDS = {"fight_night": [1, 1, 1, 0], "contender": [1, 0, 0, 1],
         "numbered": [1, 0, 0, 0]}
RANKER = {"fight_night": (2, 1), "contender": (2, 0), "numbered": (0, 1)}
TAKEN = {"fight_night": (1, 2, 3), "contender": (0, 2, 2), "numbered": (0, 1, 1)}
EDGE = {"fight_night": (2, 1), "contender": (1, 1), "numbered": (1, 0)}


def _world(tmp_path):
    conn = db.open_db(tmp_path / "cards.db")
    for tier, (event, week, kickoff) in CARDS.items():
        conn.execute(
            "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
            " event_tier) VALUES (?, ?, ?, ?, '2026-09-01T00:00:00Z', ?)",
            (event, f"UFC {event}", kickoff, SEASON, tier))
    for tier, bout, prob, outcome, implied, led, taken in QUESTIONS:
        event, week, kickoff = CARDS[tier]
        conn.execute(
            "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
            " fighter_a, fighter_b, status, fetched_utc)"
            " VALUES (?, ?, ?, 3, 'A', 'B', 'final', '2026-09-01T00:00:00Z')",
            (bout, event, kickoff))
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, 'ufc', ?, ?, 'R', 'A', 'B', ?, 'final', ?, 1, 0)",
            (bout, SEASON, week, kickoff, kickoff[:10]))
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
            " VALUES (?, 'ufc', ?, 'moneyline', 'A', NULL, ?, 'win',"
            " 'statistical', 'final', 'fs2', '{\"coverage\": 1.0}', 'test', ?, ?)",
            (kickoff[:10] + "T10:00:00Z", bout, prob,
             kickoff[:10] + "T23:59:00Z", outcome))
        pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
        if implied is not None:
            conn.execute(
                "INSERT INTO market_snapshots (prediction_id, fetched_utc,"
                " source, implied_prob, kind) VALUES (?, ?, 'test', ?,"
                " 'open_at_predict')", (pid, kickoff[:10] + "T10:00:05Z", implied))
        conn.execute(
            "INSERT INTO prediction_ranks (prediction_id, ranker_version, sport,"
            " market_type, rank_score, confidence, completeness, edge,"
            " edge_counted, edge_gate_n, factor_set_version, on_shortlist,"
            " shortlist_place, backfilled, created_utc) VALUES (?, ?, 'ufc',"
            " 'moneyline', 0.5, 0.2, 1.0, NULL, 0, 0, 'fs2', ?, ?, 0, ?)",
            (pid, config.RANKER_VERSION, 1 if led else 0, 0 if led else None,
             kickoff[:10] + "T10:00:06Z"))
        if taken:
            conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc)"
                         " VALUES (?, ?)", (pid, kickoff[:10] + "T11:00:00Z"))
    conn.commit()
    return conn


def _without_the_card(monkeypatch):
    """THE DOOR AS IT STOOD: every count asked the curve's rows with no card."""
    real = calibration.resolved
    monkeypatch.setattr(calibration, "resolved",
                        lambda conn, **kw: real(conn, **dict(kw, event_tier=None)))


def _named_as_asked(monkeypatch):
    """Every card's rows handed back under the card asked for: a door only a
    recount made without it can see."""
    real = calibration.resolved

    def door(conn, **kw):
        rows = real(conn, **dict(kw, event_tier=None))
        for r in rows:
            r.event_tier = kw.get("event_tier")
        return rows

    monkeypatch.setattr(calibration, "resolved", door)


# --- the tier table ----------------------------------------------------------

def test_the_tier_table_is_one_cards_and_names_it(tmp_path):
    conn = _world(tmp_path)
    for tier in TIERS:
        table = calibration.tier_table(conn, sport="ufc", market_type="moneyline",
                                       predictor="statistical", event_tier=tier)
        assert [r["n"] for r in table["rows"]] == BANDS[tier] == table["recounted"]
        assert table["event_tier"] == tier
        assert table["tiers_counted"] == [tier]
        assert table["card_label"] == {"numbered": "Numbered card",
                                       "fight_night": "Fight Night",
                                       "contender": "Contender Series"}[tier]
    with pytest.raises(calibration.PooledCount, match="not one of ufc's declared"):
        calibration.tier_table(conn, sport="ufc", market_type="moneyline")
    with pytest.raises(calibration.PooledCount):
        calibration.bucket_record(conn, 0.55, sport="ufc", market_type="moneyline")
    # The page's card choice asks for any card; the scorecard's is the first.
    page = calibration.scorecard(conn, sport="ufc")
    assert page["tier_table"]["event_tier"] == TIERS[0]
    assert [c["tier"] for c in page["cards"]] == list(TIERS)
    chosen = views.tier_table_for(conn, "ufc", market="moneyline",
                                  forecaster="statistical", card="contender")
    assert [r["n"] for r in chosen["rows"]] == BANDS["contender"]
    with pytest.raises(KeyError):
        views.tier_table_for(conn, "ufc", market="moneyline",
                             forecaster="statistical", card="every card")


def test_the_tier_chip_counts_its_own_cards_band(tmp_path):
    """The chip on a UFC card reads the tier table's door for its own card:
    a 55% Contender Series fight's band holds the Contender Series' one, not
    the three cards' three."""
    conn = _world(tmp_path)
    page = views.week(conn, "ufc", SEASON, 2, forecaster="statistical")
    chips = {c["prediction_id"]: c["bucket"] for c in page["cards"]}
    assert chips and all(b["event_tier"] == "contender" for b in chips.values())
    assert sorted(b["n"] for b in chips.values()) == [1, 1]
    rows = views.history(conn, sport="ufc")
    by_tier = {r["tier"]["bucket"]: r["tier"]["n"] for r in rows["items"]
               if r["prediction_id"] in chips}
    assert by_tier == {"50-60%": 1, "80%+": 1}


# --- the ranker --------------------------------------------------------------

def test_the_ranker_is_one_cards_and_names_it(tmp_path):
    conn = _world(tmp_path)
    panel = calibration.ranker_scorecard(conn, sport="ufc")
    got = {c["event_tier"]: (c["shortlisted"]["n"], c["not_shortlisted"]["n"])
           for c in panel["comparisons"] if c["market"] == "moneyline"}
    assert got == RANKER
    labels = {c["category_label"] for c in panel["comparisons"]}
    assert "moneyline, Fight Night" in labels and "moneyline, Numbered card" in labels
    assert panel["n"] == len(panel["comparisons"]) == 9   # comparisons, never a sum


def test_the_edge_gate_count_and_the_rank_written_are_one_cards(tmp_path):
    """`settled_for_gate`, the ranker's edge gate and the badge's count,
    requires the card for UFC; and a UFC rank is written with its own card's
    count."""
    conn = _world(tmp_path)
    assert {t: shortlist.settled_for_gate(conn, "ufc", "moneyline", None,
                                          "statistical", t) for t in TIERS} == \
        {"fight_night": 3, "contender": 2, "numbered": 1}
    with pytest.raises(calibration.PooledCount, match="the edge gate's settled count"):
        shortlist.settled_for_gate(conn, "ufc", "moneyline", None, "statistical")
    # A new Fight Night fight still to come, ranked: its edge gate's count is
    # Fight Night's 3, never the cards' 6.
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES ('ev_fn2', 'UFC ev_fn2', '2099-10-10T21:00:00Z', ?,"
        " '2026-09-01T00:00:00Z', 'fight_night')", (SEASON,))
    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " fighter_a, fighter_b, status, fetched_utc) VALUES ('fn2_a', 'ev_fn2',"
        " '2099-10-10T21:00:00Z', 3, 'A', 'B', 'scheduled', '2026-09-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('fn2_a', 'ufc', ?, 9, 'R',"
        " 'A', 'B', '2099-10-10T21:00:00Z', 'scheduled', '2099-10-10')", (SEASON,))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-10-07T18:00:00Z', 'ufc', 'fn2_a', 'moneyline', 'A', NULL, 0.6,"
        " 'win', 'statistical', 'early', 'fs2', '{\"coverage\": 1.0}', 'test')")
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    written = conn.execute("SELECT edge_gate_n FROM prediction_ranks"
                           " WHERE prediction_id = ?", (pid,)).fetchone()[0]
    assert written == 3


# --- the taken record --------------------------------------------------------

def test_the_taken_record_is_one_cards_and_names_it(tmp_path):
    conn = _world(tmp_path)
    page = views.scorecard(conn, "ufc")
    got = {m["event_tier"]: (m["taken"]["n"], m["not_taken"]["n"], m["all"]["n"])
           for m in page["taken_record"]["markets"] if m["market"] == "moneyline"}
    assert got == TAKEN
    labels = [m["market_label"] for m in page["taken_record"]["markets"]
              if m["market"] == "moneyline"]
    assert "moneyline, Fight Night, statistical" in labels
    # The markets with nothing settled are said with their cards.
    assert "rounds, Fight Night" in (page["taken_record"]["silent_words"] or "")


# --- the edge figure ---------------------------------------------------------

def test_the_edge_question_is_asked_once_per_card_and_no_headline_curve(tmp_path):
    conn = _world(tmp_path)
    page = calibration.scorecard(conn, sport="ufc")
    assert page["edge"] is None and page["headline"] is None
    got = {e["event_tier"]: (e["n"], e["n_disagreements"]) for e in page["edges"]}
    assert got == EDGE
    assert [e["card_label"] for e in page["edges"]] == [
        "moneyline, Numbered card", "moneyline, Fight Night",
        "moneyline, Contender Series"]
    assert "separately per market and card" in page["ranker"]["note"]
    with pytest.raises(calibration.PooledCount):
        calibration.edge(conn, sport="ufc", market_type="moneyline",
                         predictor="statistical")


def test_a_sport_that_does_not_split_by_card_counts_as_before(league):
    """NFL: no card asked or named, the tier table and the edge as they were,
    with the recount beside each; a card named is refused."""
    page = calibration.scorecard(league, sport="nfl")
    assert page["headline"] is not None and page["edge"] is not None
    assert "edges" not in page and "cards" not in page
    assert "event_tier" not in page["tier_table"]
    assert page["tier_table"]["recounted"] == [r["n"] for r in page["tier_table"]["rows"]]
    with pytest.raises(calibration.PooledCount, match="declares no cards"):
        calibration.tier_table(league, sport="nfl", market_type="spread",
                               event_tier="fight_night")


# --- the board badge ---------------------------------------------------------

def test_the_board_badge_is_its_cards_count_and_names_it(tmp_path):
    conn = _world(tmp_path)
    for tier, (event, week, kickoff) in CARDS.items():
        page = views.week(conn, "ufc", SEASON, week, forecaster="statistical")
        blocks = [b for g in page["board"]["games"] for b in g["questions"]]
        assert blocks
        want = sum(1 for q in QUESTIONS if q[0] == tier)
        assert {(b["badge_card"], b["badge_n"]) for b in blocks} == {(tier, want)}
        label = {"numbered": "Numbered card", "fight_night": "Fight Night",
                 "contender": "Contender Series"}[tier]
        assert all(f", {label}." in b["tips"]["badge"] for b in blocks)


# --- each pooled count refused by its builder, the API and the gate ----------

@pytest.mark.parametrize("pooled", [_without_the_card, _named_as_asked])
def test_each_pooled_count_is_refused_by_its_builder(tmp_path, monkeypatch, pooled):
    conn = _world(tmp_path)
    pooled(monkeypatch)
    for build in (
            lambda: calibration.tier_table(conn, sport="ufc", market_type="moneyline",
                                           predictor="statistical",
                                           event_tier="fight_night"),
            lambda: calibration.ranker_scorecard(conn, sport="ufc"),
            lambda: calibration.taken_comparison(conn, sport="ufc",
                                                 market_type="moneyline",
                                                 event_tier="fight_night"),
            lambda: calibration.edge(conn, sport="ufc", market_type="moneyline",
                                     predictor="statistical",
                                     event_tier="fight_night")):
        with pytest.raises(calibration.PooledCardCount,
                           match="EVERY UFC COUNT IS PER CARD TIER"):
            build()


def test_a_pooled_badge_is_refused_by_the_board_and_the_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn = _world(tmp_path)
    real = shortlist.settled_for_gate
    monkeypatch.setattr(
        shortlist, "settled_for_gate",
        lambda conn, sport, mt, pt, predictor, event_tier=None:
        real(conn, sport, mt, pt, predictor, "fight_night") + 3)
    with pytest.raises(calibration.PooledCardCount, match="THE BOARD'S BADGE"):
        views.week(conn, "ufc", SEASON, 1, forecaster="statistical")
    monkeypatch.setattr(board, "_card_of", lambda conn, cache, sport, game_id: None)
    monkeypatch.setattr(shortlist, "settled_for_gate", real)
    with pytest.raises(calibration.PooledCardCount, match="names card None"):
        views.week(conn, "ufc", SEASON, 1, forecaster="statistical")
    token = "test-token-for-the-badges-per-card"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "cards.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            response = client.get("/api/week", params={"sport": "ufc",
                                                       "season": SEASON, "week": 1})
    finally:
        api.set_database(None)
    assert response.status_code == 500


def test_a_pooled_count_is_refused_by_the_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    _world(tmp_path)
    _without_the_card(monkeypatch)
    token = "test-token-for-the-counts-per-card"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "cards.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            page = client.get("/api/scorecard", params={"sport": "ufc"})
            table = client.get("/api/tier-table", params={
                "sport": "ufc", "market": "moneyline", "card": "fight_night"})
    finally:
        api.set_database(None)
    assert page.status_code == 500 and table.status_code == 500
    assert "PER CARD" in table.json()["detail"]


def test_the_headline_and_one_edge_over_every_card_are_refused(tmp_path):
    conn = _world(tmp_path)
    page = calibration.scorecard(conn, sport="ufc")
    pooled = calibration.curve(conn, sport="ufc", market_type="moneyline",
                               predictor="statistical")
    for change in ({"headline": pooled},
                   {"edge": dict(page["edges"][0], event_tier=None), "edges": None},
                   {"edges": page["edges"][:2]}):
        with pytest.raises(calibration.PooledCardCount):
            calibration.assert_no_pooled_headline(dict(page, **change))


@pytest.mark.parametrize("check", [
    "check_a_ufc_tier_table_is_its_cards", "check_a_ufc_ranker_count_is_its_cards",
    "check_a_ufc_taken_record_is_its_cards", "check_a_ufc_edge_figure_is_its_cards",
    "check_a_ufc_board_badge_is_its_cards"])
def test_the_gate_names_a_pooled_count(tmp_path, monkeypatch, check):
    conn = _world(tmp_path)
    getattr(audit, check)(conn)                                # lawful: passes
    if check == "check_a_ufc_board_badge_is_its_cards":
        real = shortlist.settled_for_gate
        monkeypatch.setattr(
            shortlist, "settled_for_gate",
            lambda conn, sport, mt, pt, predictor, event_tier=None:
            len(calibration.resolved(conn, sport=sport, market_type=mt,
                                     prop_type=pt, predictor=predictor)))
        # The gate builds the current slate: a fight still to come on it.
        conn.execute(
            "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
            " event_tier) VALUES ('ev_next', 'UFC ev_next', '2099-10-10T21:00:00Z',"
            " ?, '2026-09-01T00:00:00Z', 'fight_night')", (SEASON,))
        conn.execute(
            "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
            " fighter_a, fighter_b, status, fetched_utc) VALUES ('next_a',"
            " 'ev_next', '2099-10-10T21:00:00Z', 3, 'A', 'B', 'scheduled',"
            " '2026-09-01T00:00:00Z')")
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES ('next_a', 'ufc', ?, 9,"
            " 'R', 'A', 'B', '2099-10-10T21:00:00Z', 'scheduled', '2099-10-10')",
            (SEASON,))
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES"
            " ('2026-10-07T18:00:00Z', 'ufc', 'next_a', 'moneyline', 'A', NULL,"
            " 0.6, 'win', 'statistical', 'early', 'fs2', '{\"coverage\": 1.0}',"
            " 'test')")
        conn.commit()
        assert real(conn, "ufc", "moneyline", None, "statistical", "fight_night") == 3
    else:
        _without_the_card(monkeypatch)
    with pytest.raises(audit.LawViolation, match="IS NOT ITS CARD'S"):
        getattr(audit, check)(conn)


def test_the_gate_makes_each_call():
    """Step 2 of `tools/verify.py` calls each of the five checks."""
    source = (Path(config.PACKAGE_ROOT).parent / "tools" / "verify.py").read_text(
        encoding="utf-8")
    called = {n.attr for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.Attribute) and n.attr.startswith("check_a_ufc_")}
    assert {"check_a_ufc_tier_table_is_its_cards",
            "check_a_ufc_ranker_count_is_its_cards",
            "check_a_ufc_taken_record_is_its_cards",
            "check_a_ufc_edge_figure_is_its_cards",
            "check_a_ufc_board_badge_is_its_cards"} <= called


# --- the tier chip on a card and a Results row (the prover, 2026-10-08) -----
#
# The chip reads the tier table's door, which refuses a UFC band asked for no
# card. A bout on a card the source names with no tier ("UFC Freedom 250", 14
# June 2026, is on the record) has none, and the predict path writes its
# questions whatever its card (`sports.ufc.slate_questions` reads no tier),
# so on the change as handed ONE such forecast took UFC's slate and the whole
# of UFC's Results down (500). It is in no card's count, as its badge is: its
# chip counts 0. Both tests fail on c4014a9 (every chip pooled, no guard) and
# the first on the change as handed (the door's refusal).

def _a_card_of_no_declared_kind(conn) -> int:
    kickoff = "2026-06-15T00:00:00Z"
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES ('ev_nd', 'UFC Freedom 250', ?, ?,"
        " '2026-06-01T00:00:00Z', NULL)", (kickoff, SEASON))
    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " fighter_a, fighter_b, status, fetched_utc) VALUES ('nd_a', 'ev_nd',"
        " ?, 3, 'A', 'B', 'final', '2026-06-01T00:00:00Z')", (kickoff,))
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score) VALUES"
        " ('nd_a', 'ufc', ?, 4, 'R', 'A', 'B', ?, 'final', ?, 1, 0)",
        (SEASON, kickoff, kickoff[:10]))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES ('2026-06-14T10:00:00Z', 'ufc', 'nd_a', 'moneyline', 'A',"
        " NULL, 0.55, 'win', 'statistical', 'final', 'fs2',"
        " '{\"coverage\": 1.0}', 'test', '2026-06-15T03:00:00Z', 1)")
    conn.commit()
    return 4


def test_a_bout_on_a_card_of_no_declared_kind_is_in_no_cards_band_and_takes_no_page_down(
        tmp_path):
    conn = _world(tmp_path)
    week = _a_card_of_no_declared_kind(conn)
    page = views.week(conn, "ufc", SEASON, week, forecaster="statistical")
    (card,) = page["cards"]
    assert (card["bucket"]["n"], card["bucket"]["event_tier"]) == (0, None)
    assert "no declared kind" in card["tier"]["message"]
    fight_night = views.week(conn, "ufc", SEASON, 1, forecaster="statistical")
    fn_a = next(c for c in fight_night["cards"] if c["game_id"] == "fn_a")
    assert (fn_a["bucket"]["n"], fn_a["bucket"]["event_tier"]) == (1, "fight_night")
    chips = {i["game_id"]: i["tier"]["n"]
             for i in views.history(conn, sport="ufc", limit=50)["items"]}
    assert chips["nd_a"] == 0 and chips["fn_a"] == 1 and chips["cs_a"] == 1
    audit.check_a_ufc_tier_table_is_its_cards(conn)              # lawful: passes


def test_a_chip_counting_another_cards_band_is_refused_by_the_slate_results_the_api_and_the_gate(
        tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn = _world(tmp_path)
    week = _a_card_of_no_declared_kind(conn)
    real = calibration.bucket_record
    # THE NO-CARD BOUT'S BAND COUNTED IN FIGHT NIGHT'S.
    monkeypatch.setattr(
        calibration, "bucket_on_no_card",
        lambda probability, *, sport: dict(real(
            conn, probability, sport=sport, market_type="moneyline",
            event_tier="fight_night"), event_tier=None))
    with pytest.raises(calibration.PooledCardCount, match="THE TIER CHIP"):
        views.week(conn, "ufc", SEASON, week, forecaster="statistical")
    with pytest.raises(calibration.PooledCardCount, match="THE TIER CHIP"):
        views.history(conn, sport="ufc", limit=50)
    with pytest.raises(audit.LawViolation, match="IS NOT ITS CARD'S"):
        audit.check_a_ufc_tier_table_is_its_cards(conn)
    monkeypatch.undo()
    # EVERY CARD'S ROWS NAMED AS THE ASKED CARD'S, behind the chip's door.
    _named_as_asked(monkeypatch)
    with pytest.raises(calibration.PooledCardCount, match="THE TIER CHIP"):
        views.history(conn, sport="ufc", limit=50)
    token = "test-token-for-the-chips-per-card"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "cards.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            response = client.get("/api/history", params={"sport": "ufc"})
    finally:
        api.set_database(None)
    assert response.status_code == 500
    assert "TIER CHIP" in response.json()["detail"]
