"""A RECOMMENDATION HEADLINES THE CONTRACT IT BUYS, THE MODEL'S OWN SIDE NAMED
BESIDE IT (operator question 37, ruled 2026-10-05).

The ruling, whole (docs/briefs/2026-10-05-rulings.md): "Q37: headline the
contract the recommendation buys; the model's own side named beside it."

A question's words name the side the model took; a recommendation buys the
side the price makes worth buying, and that can be the OTHER one. Until this
date the board's row and tile, the Today card and My day's chip drew the
model's side's words, chance, price and payout beside the size, the edge and
the green outline of the contract bought, and the taken rail named the
model's side beside the other's edge: rec 117 (ATL at NO, 6 October) read
"Atlanta +2.5 · 32% · 48c · 2.06x · $15", outlined, and bought New Orleans
-2.5 at 68% and 51.5c. Each now headlines the contract bought and names the
model's own side and number beside it.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from gridiron import audit, db, language, views
from gridiron.market import recommend
from gridiron.priced import coverage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def covered(monkeypatch):
    """The coverage list is not what these test: every market is priceable."""
    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})


def _rec117(path, **kwargs):
    """Rec 117's shape (step A's test world): "NO covers -9.5" answered
    "not_cover" -- Atlanta +9.5 -- priced off the home contract "New Orleans
    wins by over 2.5" at a 51.5c mid, the model's 68.48% for New Orleans
    -2.5; the recommendation buys New Orleans -2.5."""
    from tests import test_every_number_names_its_line as step_a
    from tests.gate_world import pass_the_gate

    # AS A PICK, ITS MARKET PAST B.5'S GATE (operator ruling B, 2026-10-05;
    # built 2026-10-07): these tests hold the headline of a recommendation
    # the page calls a pick -- sized, outlined, "Model's pick" -- so the NFL
    # spread here has its hundred settled comparisons at the venue's price.
    # Rec 117 itself is a number under B (`test_ranked_by_edge.py`).
    got = step_a._world(path, "rec117", **kwargs)
    pass_the_gate(got[0], sport="nfl", market="spread")
    return got


def _moneyline(path, *, price=0.30, confidence=0.57):
    """Step C's world: BBB (away) to win at `confidence`, a claim of one minus
    it on the home side AAA against a home price of `price`. At 30c the
    recommendation buys AAA, the other side of the model's words -- recs 47
    and 82's shape, read at the question's own line."""
    from tests import test_recommend as rec

    conn = rec._world(path, kickoff="2099-01-01T00:00:00Z")
    pid = rec._away_pick(conn, price=price, confidence=confidence)
    # ITS MARKET PAST B.5'S GATE (operator ruling B, 2026-10-05; 2026-10-07),
    # as `_rec117`'s: the moneyline is held here as a pick.
    from tests.gate_world import pass_the_gate

    pass_the_gate(conn, sport="mlb", market="moneyline")
    return conn, pid


def _card(payload, pid, groups=("clears", "below_floor", "watching")):
    return next(c for g in groups for c in payload["today"][g] if c["prediction_id"] == pid)


def _blocks(payload, pid):
    out = []
    for g in payload["board"]["games"]:
        if g.get("pick") and g["pick"]["prediction_id"] == pid:
            out.append(("pick", g["pick"], g))
        out += [("tile", q, g) for q in g["questions"] if q["prediction_id"] == pid]
    return out


def _line(payload, pid):
    return next(x for x in payload["recommendations"]["lines"] if x["prediction_id"] == pid)


def _every_check(conn, payload):
    return (audit.headline_faults(payload) + audit.pick_side_faults(payload)
            + audit.combo_side_faults(payload) + audit.board_price_side_faults(payload)
            + audit.number_line_faults(payload, audit.pick_contracts(conn, payload)))


def test_rec_117_headlines_the_contract_it_buys(tmp_path):
    """The card, the row and the tile name New Orleans -2.5 with its 68%,
    52c and 1.94x, its size, its edge (bare: it is that contract's own) and
    the green outline, and say beside it "The model's own side: Atlanta +2.5,
    32%"; the row's label says the pick is the other side; the line names the
    model's side at its end. Fails on b39754c, which drew "Atlanta +2.5 · 32%
    · 48c · 2.06x" beside New Orleans -2.5's "$15"."""
    conn, pid, sport, week = _rec117(tmp_path / "rec117.db")
    payload = views.week(conn, sport, 2026, week)
    card = _card(payload, pid)
    assert card["question"] == "New Orleans covers -2.5"
    assert card["line_words"] == "New Orleans -2.5"
    assert card["question_takes_the_proposition"] is True
    assert card["model_words"] == "68¢"
    assert card["venue_words"] == "52¢ · pays 1.94x"
    assert card["payout"] == recommend.payout_multiple(0.515)
    assert card["edge_label"] == "Edge after fees"
    assert card["buys_the_other_side"] is True
    assert card["own_side_words"] == "The model's own side: Atlanta +2.5, 32%"
    assert card["named_club"] == "NO"
    assert card["size_words"].startswith("One flat unit")
    blocks = _blocks(payload, pid)
    assert {kind for kind, _, _ in blocks} == {"pick", "tile"}
    for kind, block, game in blocks:
        assert block["line_words"] == "New Orleans -2.5", kind
        assert block["prob_words"] == "68%" and block["prob"] == pytest.approx(0.6848)
        assert block["price"] == pytest.approx(0.515) and block["pays"] == card["payout"]
        assert block["edge_words"] == "+15.0¢"
        assert block["signal"] == "clears" and block["size_words"] == card["size_words"]
        assert block["own_side_words"] == "The model's own side: Atlanta +2.5, 32%"
        assert block["named_club"] == "NO"
        # the reasons are the model's, for its own side, and say so -- after
        # the question as the model was asked it, at its own line
        assert block["tips"]["line"].startswith(
            "The model was asked about Atlanta +9.5 and gives it 58%. This buys "
            "the other side of the model's own.")
        assert "Atlanta +2.5, 32%" in block["tips"]["prob"]
        if kind == "pick":
            assert game["pick_label_words"] == "Model's pick · the other side"
    line = _line(payload, pid)
    assert line["side_words"] == "New Orleans covers -2.5"
    assert line["words"].endswith(" The model's own side: Atlanta covers +2.5, 32%.")
    assert _every_check(conn, payload) == []
    conn.close()


def test_a_moneyline_bought_on_the_other_side_headlines_it(tmp_path):
    """Recs 47 and 82's shape, read at the question's own line: the model's
    "BBB to win" at 57%, the recommendation AAA at 43% and 30c. The card and
    the row headline AAA -- 43%, 30c, 3.33x -- with "The model's own side:
    BBB to win, 57%" beside it, and the card's numbers line names the
    question it is about. Fails on b39754c ("BBB to win · 57% · 70c ·
    1.43x" beside AAA's size)."""
    conn, pid = _moneyline(tmp_path)
    payload = views.week(conn, "mlb", 2026, 1)
    card = _card(payload, pid)
    assert (card["question"], card["model_words"]) == ("AAA to win", "43¢")
    assert card["venue_words"] == "30¢ · pays 3.33x"
    assert card["own_side_words"] == "The model's own side: BBB to win, 57%"
    assert card["rail_line"].startswith("For BBB to win, as the model was asked: ")
    for kind, block, game in _blocks(payload, pid):
        assert (block["line_words"], block["prob_words"]) == ("AAA to win", "43%"), kind
        assert block["price_words"].startswith("30") and block["pays_words"] == "3.33x"
        assert block["edge_words"] == "+11.0¢"
        assert block["own_side_words"] == "The model's own side: BBB to win, 57%"
    assert _every_check(conn, payload) == []
    conn.close()


def test_my_day_and_the_rail_name_the_contract_bought(tmp_path):
    """A taken recommendation's My day chip wears AAA's club beside "AAA to
    win", and the taken rail names AAA with its edge when marked and the
    model's own side beside it. Fails on b39754c (the chip "BBB · BBB to win",
    the rail "BBB to win · +11.0¢ when marked")."""
    conn, pid = _moneyline(tmp_path)
    assert recommend.record_for(conn, [pid])["recommended"] == 1
    conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                 (pid, db.utcnow()))
    conn.commit()
    payload = views.week(conn, "mlb", 2026, 1)
    [chip] = payload["board"]["my_day"]["entries"]
    assert (chip["club"]["tricode"], chip["line_words"]) == ("AAA", "AAA to win")
    [rail] = payload["today"]["taken_today"]["entries"]
    assert rail["words"] == ("AAA to win · +11.0¢ when marked — the model's own side: "
                             "BBB to win, 57%")
    assert rail["side"] == "yes" and rail["fair_value"] == pytest.approx(0.43)
    assert _every_check(conn, payload) == []
    # AS RELEASED: the chip and the rail on the model's side
    chip.update({"line_words": "BBB to win", "club": dict(chip["club"], tricode="BBB")})
    rail["words"] = "BBB to win · +11.0¢ when marked"
    faults = audit.headline_faults(payload)
    assert any("my_day" in f and "operator question 37" in f for f in faults), faults
    assert any("taken_today" in f and "operator question 37" in f for f in faults), faults
    conn.close()


def test_a_recommendation_on_the_models_own_side_is_unchanged(tmp_path):
    """BBB at 57% against 51.5c: the recommendation buys BBB, the side the
    model took -- headlined as before, nothing beside it, the label as it
    was. Holds what was right; passes on b39754c too."""
    conn, pid = _moneyline(tmp_path, price=0.485)
    payload = views.week(conn, "mlb", 2026, 1)
    card = _card(payload, pid)
    assert (card["question"], card["model_words"]) == ("BBB to win", "57¢")
    assert "own_side_words" not in card
    for kind, block, game in _blocks(payload, pid):
        assert block["line_words"] == "BBB to win" and "own_side_words" not in block
        if kind == "pick":
            assert game["pick_label_words"] == "Model's pick"
    assert not _line(payload, pid)["words"].endswith("%.")
    assert _every_check(conn, payload) == []
    conn.close()


def test_a_watched_card_buys_nothing_and_keeps_its_question(tmp_path):
    """BBB at 57% against 58c: neither side clears the fee, so nothing is
    bought and the card keeps the model's words, its figure labelled "on the
    other side" as step C's prover left it. Holds what was right."""
    conn, pid = _moneyline(tmp_path, price=0.42)
    payload = views.week(conn, "mlb", 2026, 1)
    card = _card(payload, pid)
    assert card["question"] == "BBB to win" and "own_side_words" not in card
    assert card["edge_label"] == "Edge after fees, on the other side"
    assert audit.headline_faults(payload) == []
    conn.close()


def _released_still_upcoming(status, kickoff_utc, under_way_utc, now):
    """`recommend.not_still_upcoming` as released before operator question
    38's ruling 2 (2026-10-06): only a game said to be in play was refused,
    so a finished game's question was priced."""
    return (recommend.BEING_PLAYED_WHY
            if (status or "").lower() in recommend.IN_PLAY_STATUSES else None)


def test_a_finished_cards_figure_and_verdict_are_the_contract_bought(tmp_path,
                                                                     monkeypatch):
    """A FINISHED GAME HAS NO PRICED CARD (operator question 38, ruling 2,
    2026-10-06; 2026-10-07: "recommend.for_predictions refuses any game that
    is not still upcoming"): rec 117's shape, finished NO 27 ATL 20, is in no
    priced group of Today, its settled card is the question's own, and the
    board's finished row is the forecast's own verdict with no own side.

    AS RELEASED BEFORE THAT RULING a finished game's card was still priced
    (step A's prover), and Q37 made its card in CLEARS headline the contract
    bought too -- New Orleans -2.5's 68% and its claim's verdict (New
    Orleans covered -2.5); with the released door put back, that shape is
    still what the checks hold."""
    conn, pid, sport, week = _rec117(tmp_path / "final.db", final=(27, 20))
    payload = views.week(conn, sport, 2026, week)
    assert not [c for g in ("clears", "below_floor", "watching")
                for c in payload["today"][g] if c["prediction_id"] == pid]
    assert not [x for x in payload["recommendations"]["lines"]
                if x["prediction_id"] == pid]
    settled = _card(payload, pid, groups=("settled",))
    assert "own_side_words" not in settled and not settled.get("buys_the_other_side")
    for kind, block, game in _blocks(payload, pid):
        assert block["state"] == "final" and "own_side_words" not in block
        assert block["line_words"] == "Atlanta +9.5"
    assert _every_check(conn, payload) == []
    # AS RELEASED: the finished game priced, and its card headlining the
    # contract bought -- the door put back on the market module as it is
    # now (a blind window earlier in the session drops the package, and the
    # page imports it afresh: test_two_contract_claims.py's `_now`)
    import importlib

    monkeypatch.setattr(importlib.import_module("gridiron.market.recommend"),
                        "not_still_upcoming", _released_still_upcoming)
    released = views.week(conn, sport, 2026, week)
    card = _card(released, pid, groups=("clears", "below_floor"))
    assert card["state"] == "final" and card["question"] == "New Orleans covers -2.5"
    assert card["settled_words"] == language.settled_outcome_words(
        0.6848, 1, "New Orleans covers -2.5")
    assert _every_check(conn, released) == []
    conn.close()


def test_a_live_card_is_never_a_purchase(tmp_path):
    """A game being played carries nothing that can be acted on (LAW 5's
    in-game rule): its card buys nothing and is headlined by its latest
    claim's words for the question's side, with its pregame figure."""
    conn, pid, sport, week = _rec117(tmp_path / "live.db", live=True)
    payload = views.week(conn, sport, 2026, week)
    card = _card(payload, pid, groups=("live",))
    assert card["question"] == "Atlanta covers +2.5"
    assert card["pregame_words"] == "pregame 32%"
    assert "own_side_words" not in card and card["buys_the_other_side"] is False
    assert audit.headline_faults(payload) == []
    conn.close()


def test_the_released_page_is_named_by_the_check(tmp_path, monkeypatch):
    """The page as released -- every card headlining its question's side --
    is named by the check on the card, the row, the tile and the line."""
    conn, pid, sport, week = _rec117(tmp_path / "released.db")
    real = views._buys_the_other_side
    monkeypatch.setattr(views, "_buys_the_other_side", lambda *a, **k: False)
    payload = views.week(conn, sport, 2026, week)
    assert _card(payload, pid)["question"] == "Atlanta covers +2.5"
    faults = audit.headline_faults(payload)
    for where in ("today.clears", "board.games[0].pick", "board.games[0].questions"):
        assert any(f.startswith(where) and "operator question 37" in f
                   for f in faults), (where, faults)
    with pytest.raises(audit.LawViolation, match="HEADLINE IS NOT THE CONTRACT IT BUYS"):
        audit.check_every_recommendation_headlines_what_it_buys(payload)
    # AND THE LINE, which named the side bought from step C, without the
    # model's own side beside it
    monkeypatch.setattr(views, "_buys_the_other_side", real)
    shipped = views.week(conn, sport, 2026, week)
    line = _line(shipped, pid)
    line["words"] = line["words"].rsplit(" The model's own side", 1)[0]
    assert any(f.startswith("recommendations.lines") and "operator question 37" in f
               for f in audit.headline_faults(shipped))
    conn.close()


def test_the_check_names_each_released_shape():
    assert audit.headline_faults(audit.HEADLINE_FIXTURE_GOOD) == []
    assert audit.number_line_faults(audit.HEADLINE_FIXTURE_GOOD,
                                    audit.HEADLINE_CONTRACTS) == []
    for name, change in audit.HEADLINE_FIXTURES_AS_RELEASED.items():
        faults = audit.headline_faults(audit._headline_fixture(**change))
        assert any("operator question 37" in f for f in faults), name


def test_the_words_are_plain():
    said = [language.own_side_words("Atlanta +2.5", 0.3152),
            language.own_side_words("Atlanta covers +2.5", 0.3152, clause=True),
            language.own_side_reasons_words("The model's own side: Atlanta +2.5, 32%"),
            language.pick_label_words("upcoming", "clears", other_side=True),
            language.prob_tip(0.6848, "statistical",
                              own_side="The model's own side: Atlanta +2.5, 32%"),
            # My day's chip's tooltip (Q37's prover, 2026-10-05)
            language.my_day_line_tip("New Orleans covers -2.5",
                                     "The model's own side: Atlanta +2.5, 32%")]
    assert said[0] == "The model's own side: Atlanta +2.5, 32%"
    assert said[1] == "the model's own side: Atlanta covers +2.5, 32%"
    for words in said:
        assert audit.plain_words_violations(words) == [], words
        assert audit.advice_word_faults(words) == [], words
    # the label says so only of a pick still to start -- and from ruling B
    # (2026-10-05; built 2026-10-07) a finished row is never labelled a
    # pick at all: "Model's pick" heads only a pick still to come
    assert language.pick_label_words("final", "won", other_side=True) == \
        "The model's number · won"
    assert language.pick_label_words("upcoming", "clears", pick=True, other_side=True) == \
        "Model's pick · the other side"


def test_the_gate_makes_the_call():
    """Gate step 2 calls the check on every sport's slate, both forecasters,
    read from its syntax tree (a row left as a comment would not count)."""
    tree = ast.parse((ROOT / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "step_2_guards")
    assert any(isinstance(n, ast.Attribute)
               and n.attr == "check_every_recommendation_headlines_what_it_buys"
               for n in ast.walk(step))


# --- Q37's prover (2026-10-05): three paths the change as first built missed --

def test_my_days_chip_names_the_models_own_side_beside_the_contract_bought(tmp_path):
    """A tapped recommendation buying the other side: My day's chip headlines
    AAA, and its tooltip names the model's own side beside it, as the row it
    scrolls to, the taken rail and the line do. As first built the chip said
    "AAA to win" alone, and the check passed it; a recommendation on the
    model's own side keeps its words alone."""
    conn, pid = _moneyline(tmp_path)
    assert recommend.record_for(conn, [pid])["recommended"] == 1
    conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                 (pid, db.utcnow()))
    conn.commit()
    payload = views.week(conn, "mlb", 2026, 1)
    [chip] = payload["board"]["my_day"]["entries"]
    assert chip["tips"]["line"] == "AAA to win. The model's own side: BBB to win, 57%."
    assert audit.headline_faults(payload) == []
    # AS FIRST BUILT: the contract bought, and the model's side said nowhere
    chip["tips"]["line"] = "AAA to win"
    assert any("my_day" in f and "operator question 37" in f
               for f in audit.headline_faults(payload))
    conn.close()
    # ON THE MODEL'S OWN SIDE: the words alone, and an own side there is named
    (tmp_path / "own").mkdir()
    conn, pid = _moneyline(tmp_path / "own", price=0.485)
    assert recommend.record_for(conn, [pid])["recommended"] == 1
    conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                 (pid, db.utcnow()))
    conn.commit()
    payload = views.week(conn, "mlb", 2026, 1)
    [chip] = payload["board"]["my_day"]["entries"]
    assert chip["tips"]["line"] == "BBB to win"
    assert audit.headline_faults(payload) == []
    chip["tips"]["line"] = "BBB to win. The model's own side: AAA to win, 43%."
    assert any("my_day" in f for f in audit.headline_faults(payload))
    conn.close()


def test_the_check_holds_the_words_the_page_draws_not_only_the_numbers(tmp_path):
    """The row and the tile draw `prob_words`, `price_words` and `pays_words`,
    and the card its chips' words; `prob`, `price` and `pays` only place the
    bar. As first built the check read the numbers alone, so the model's
    side's "32%", "48c" and "2.06x" beside numbers of the contract bought
    passed."""
    conn, pid, sport, week = _rec117(tmp_path / "words.db")
    payload = views.week(conn, sport, 2026, week)
    for kind, block, _ in _blocks(payload, pid):
        assert (block["prob_words"], block["price_words"], block["pays_words"]) == (
            "68%", "52¢", "1.94x"), kind
    card = _card(payload, pid)
    assert (card["venue_words"], card["payout_words"], card["price_words"]) == (
        "52¢ · pays 1.94x", "1.94x", "52¢ a contract")
    assert audit.headline_faults(payload) == []
    for kind, block, _ in _blocks(payload, pid):
        planted = json.loads(json.dumps(payload))
        target = next(b for k, b, _ in _blocks(planted, pid) if k == kind)
        target.update({"prob_words": "32%", "price_words": "48¢", "pays_words": "2.06x"})
        named = [f for f in audit.headline_faults(planted) if "operator question 37" in f]
        for words in ("'32%'", "'48¢'", "'2.06x'"):
            assert any(words in f for f in named), (kind, words, named)
    planted = json.loads(json.dumps(payload))
    _card(planted, pid).update({"venue_words": "48¢ · pays 2.06x", "payout_words": "2.06x",
                                "price_words": "48¢ a contract"})
    named = [f for f in audit.headline_faults(planted) if f.startswith("today.clears")]
    for words in ("'48¢ · pays 2.06x'", "'2.06x'", "'48¢ a contract'"):
        assert any(words in f for f in named), (words, named)
    conn.close()


def test_a_live_row_carrying_the_models_own_side_is_named(tmp_path):
    """The model's own side carries a chance, and a game being played shows
    its pregame figure and nothing else (LAW 5; LIVE TAB). The page draws it
    on a row still to start only; a live row or card carrying it is named by
    the live check, which as first built had no word for the field."""
    conn, pid, sport, week = _rec117(tmp_path / "live.db", live=True)
    payload = views.week(conn, sport, 2026, week)
    assert audit.live_tab_faults(payload) == []
    game = next(g for g in payload["board"]["games"]
                if any(b["prediction_id"] == pid for _, b, _ in _blocks(payload, pid)))
    assert game["state"] == "live"
    # (the row's pick is its tile's own block, one object drawn twice)
    assert not any("own_side_words" in b for _, b, _ in _blocks(payload, pid))
    for _, block, _ in _blocks(payload, pid):
        block["own_side_words"] = "The model's own side: Atlanta +2.5, 32%"
    _card(payload, pid, groups=("live",))["own_side_words"] = (
        "The model's own side: Atlanta +2.5, 32%")
    named = [f for f in audit.live_tab_faults(payload) if "own_side_words" in f]
    assert any(f.startswith("today.live") for f in named), named
    assert any(f.startswith("board.games") for f in named), named
    with pytest.raises(audit.LawViolation, match="THE LIVE TAB SHOWS THE GAME"):
        audit.check_the_live_tab_shows_only_the_game(payload)
    conn.close()


def test_the_fixtures_are_rec_117_as_measured():
    """The fixture's numbers are rec 117's as the record holds them (measured
    2026-10-05 on a verified copy): claim 1789 at -2.5, 0.6848 at 0.515."""
    good = json.loads(json.dumps(audit.HEADLINE_FIXTURE_GOOD))
    card = good["today"]["clears"][0]
    assert (card["fair_value"], card["price"]) == (0.6848, 0.515)
    assert audit.HEADLINE_CONTRACTS[3583]["priced"]["claim"] == 1789
