"""A venue contract is read at the line it sells (operator question 36 (i),
ruled 2026-09-30: "the writer -- read an away contract at +s (the stored
number as it is) from the release, with a planting").

The venue sells "<team> wins by over <s>". A home contract is the home side
covering -s; an away contract is the complement of the home side covering
+s, and `kalshi.parse_markets` stores it at +s -- already that line. From the
first claim writer (2026-09-07) `at_the_line.home_view_line` negated an away
row, so every claim priced off one stored -s beside a price about +s (269
claims, 54 recommendations on the record; nothing stored changes -- question
36 (ii) is not ruled). The contracts here are the venue's own, cut from the
record's cached payloads, and the questions the record's own forecasts on
those games (`audit.VENUE_SPREAD_CONTRACTS_AS_SOLD`).
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from gridiron import audit, db, drift, views
from gridiron.market import at_the_line as atl
from gridiron.market import kalshi

REPO = Path(__file__).resolve().parents[1]

#: The clubs as the venue's words name them, and our codes for them.
CLUBS = {"Tulsa": "TLSA", "North Texas": "UNT", "Baltimore": "BAL",
         "Toronto": "TOR", "WAS Commanders": "WAS", "SEA Seahawks": "SEA"}

WORDS = re.compile(r"^(?P<club>.+) wins by over (?P<s>[0-9.]+) (points|runs)$")


def _game(sport):
    return next(g for g in audit.VENUE_SPREAD_CONTRACTS_AS_SOLD if g["sport"] == sport)


def _question(sport, pass_kind="final"):
    return next(q for q in _game(sport)["questions"] if q["pass"] == pass_kind)


def _sold_by_the_words(game, words):
    """The line a contract sells, worked out here from the venue's words
    alone: the home club winning by over s is the home side covering -s; the
    away club winning by over s is the complement of the home side covering
    +s."""
    hit = WORDS.match(words)
    assert hit, words
    club, strike = CLUBS[hit.group("club")], float(hit.group("s"))
    assert club in (game["home"], game["away"]), (club, game)
    return -strike if club == game["home"] else strike


def _world(tmp_path, sport, *, questions=None, only=None):
    """One fixture game, its questions (the fixture's, or those given) as
    statistical spread forecasts on the home side, and its cached contracts
    (or `only` those) as an opening and a near-start look. Returns the
    connection, the forecast ids by pass, and the game."""
    game = _game(sport)
    conn = db.open_db(tmp_path / f"{sport}.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, ?, 2099, 1, 'REG', ?, ?,"
        " '2099-01-01T00:00:00Z', 'scheduled', '2098-12-31')",
        (game["game"], sport, game["home"], game["away"]))
    ids = {}
    for q in questions or game["questions"]:
        factors = {"coverage": 1.0}
        if q["distribution"] is not None:
            factors["margin_distribution"] = {
                "quantity": "home_margin", "family": "normal",
                "mean": q["distribution"][0], "sd": q["distribution"][1],
                "declared": "2026-08-31T00:00:00Z", "written_blind": True}
        cur = conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES"
            " ('2098-12-30T00:00:00Z', ?, ?, 'spread', ?, ?, ?, ?, 'statistical',"
            " ?, 'fsQ36', ?, 'test')",
            (sport, game["game"], game["home"], q["asked"], q["prob"], q["side"],
             q["pass"], json.dumps(factors)))
        ids[q["pass"]] = cur.lastrowid
    quotes, unread = kalshi.parse_markets(
        sport, "spread", {"home": game["home"], "away": game["away"]},
        audit.venue_contract_payload(game))
    assert unread == []
    for kind, stamp in (("open", "2098-12-30T06:00:00Z"),
                        ("near_start", "2098-12-31T22:00:00Z")):
        for q in quotes:
            if only and not q["ticker"].endswith(tuple("-" + o for o in only)):
                continue
            conn.execute(
                "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
                " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
                " last_price, volume, fetched_utc, read_kind)"
                " VALUES ('kalshi', ?, ?, ?, ?, 'spread', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (q["ticker"], q["event_ticker"], sport, game["game"],
                 q["quantity"], q["line"], q["yes_side"], q["yes_bid"],
                 q["yes_ask"], q["last_price"], q["volume"], stamp, kind))
    conn.commit()
    return conn, ids, game


def _claims(conn, pid):
    return conn.execute(
        "SELECT c.*, q.ticker FROM at_the_line_claims c"
        " JOIN venue_quotes q ON q.id = c.quote_id WHERE c.prediction_id = ?",
        (pid,)).fetchall()


# --- the venue's own contracts, read at the lines they sell -------------------

def test_the_three_cached_payloads_contracts_are_read_at_the_lines_they_sell():
    """"North Texas wins by over 1.5 points" (UNT at TLSA) sells Tulsa +1.5;
    "Toronto wins by over 1.5 runs" (TOR at BAL) sells Baltimore +1.5; "SEA
    Seahawks wins by over 7.5 points" (SEA at WAS) sells Washington +7.5.
    Each home contract sells its own -s. The released reading read every
    away contract at -s."""
    assert {g["sport"] for g in audit.VENUE_SPREAD_CONTRACTS_AS_SOLD} == {"cfb", "mlb", "nfl"}
    seen = {}
    for game in audit.VENUE_SPREAD_CONTRACTS_AS_SOLD:
        quotes, unread = kalshi.parse_markets(
            game["sport"], "spread", {"home": game["home"], "away": game["away"]},
            audit.venue_contract_payload(game))
        assert unread == [] and len(quotes) == len(game["contracts"])
        words = {f"{game['event']}-{c[0]}": c[1] for c in game["contracts"]}
        for q in quotes:
            by_the_words = _sold_by_the_words(game, words[q["ticker"]])
            fixture = next(c[5] for c in game["contracts"]
                           if q["ticker"].endswith("-" + c[0]))
            assert fixture == by_the_words, (words[q["ticker"]], fixture)
            assert atl.home_view_line(q) == by_the_words, (
                f"{words[q['ticker']]!r} is read at {atl.home_view_line(q)}; "
                f"it sells the home side at {by_the_words:+g}")
            seen[words[q["ticker"]]] = atl.home_view_line(q)
    assert seen["North Texas wins by over 1.5 points"] == 1.5
    assert seen["Tulsa wins by over 1.5 points"] == -1.5
    assert seen["Toronto wins by over 1.5 runs"] == 1.5
    assert seen["Baltimore wins by over 1.5 runs"] == -1.5
    assert seen["SEA Seahawks wins by over 7.5 points"] == 7.5
    assert seen["WAS Commanders wins by over 7.5 points"] == -7.5


def test_a_same_strike_pair_agrees():
    """A home and an away contract at one strike are two lines -- the home
    side covering -s and covering +s -- and the prices agree with that
    within the spread: the chance of covering -s is no more than the chance
    of covering +s. Read the released way, both were "covers -s", and at TOR
    at BAL's 1.5 the two prices stood 31 points apart, no overlap -- the
    record's 8,286 such pairs 41 points apart on average."""
    pairs = 0
    for game in audit.VENUE_SPREAD_CONTRACTS_AS_SOLD:
        quotes, _ = kalshi.parse_markets(
            game["sport"], "spread", {"home": game["home"], "away": game["away"]},
            audit.venue_contract_payload(game))
        home = {abs(q["line"]): q for q in quotes if q["yes_side"] == "home"}
        away = {abs(q["line"]): q for q in quotes if q["yes_side"] == "away"}
        for strike in sorted(set(home) & set(away)):
            h, a = home[strike], away[strike]
            pairs += 1
            assert atl.home_view_line(h) == -strike
            assert atl.home_view_line(a) == strike
            assert atl.quotes_selling([h, a], -strike) == [h]
            assert atl.quotes_selling([h, a], strike) == [a]
            # one rising curve, within the spread: covering -s's bid is at or
            # below covering +s's ask (the away contract's complemented bid)
            assert h["yes_bid"] <= 1 - a["yes_bid"] + 1e-9, (game["event"], strike)
            assert atl.implied_of(h)[0] <= atl.implied_of(a)[0]
        # the whole look, read in the one place, rises with the line
        points = sorted((atl.home_view_line(q), atl.implied_of(q)[0]) for q in quotes)
        assert [p for _l, p in points] == sorted(p for _l, p in points), points
    assert pairs == 6
    bal, tor = (next(q for q in kalshi.parse_markets(
        "mlb", "spread", {"home": "BAL", "away": "TOR"},
        audit.venue_contract_payload(_game("mlb")))[0] if q["ticker"].endswith(t))
        for t in ("-BAL2", "-TOR2"))
    # read the released way, both "Baltimore covers -1.5": 32.5% and 63.5%
    assert atl.implied_of(tor)[0] - atl.implied_of(bal)[0] > 0.3


def test_the_one_place_reads_the_stored_number_and_refuses_an_unknown_side():
    """The ruling's words: "read an away contract at +s (the stored number as
    it is)". Every side the schema admits reads its stored number; any other
    is refused by name, never read as either side."""
    for side, line in (("home", -3.5), ("away", 3.5), ("over", 44.5), ("under", 44.5)):
        assert atl.home_view_line({"line": line, "yes_side": side}) == line
    assert atl.home_view_line({"line": None, "yes_side": "away"}) is None
    assert set(atl.CONTRACT_SIDES) == {"home", "away", "over", "under"}
    with pytest.raises(atl.UnreadContract, match="'neither'"):
        atl.home_view_line({"line": 3.5, "yes_side": "neither"})


# --- the writer ---------------------------------------------------------------

def test_a_claim_written_from_an_away_contract_carries_plus_s_and_its_price(tmp_path):
    """SEA at WAS: the contract priced nearest an even chance is "SEA
    Seahawks wins by over 7.5 points" at 52-53c -- Washington +7.5, the line
    the record's own question (forecast 2319) was asked at. The claim is
    Washington covering +7.5: the line +7.5, the price 52.5c complemented to
    47.5%, the question's own number beside it (54.8%), and it settles at
    +7.5. The released writer stored it at -7.5 with the distribution read at
    -7.5 (14.6%, the record's claim 1662) beside that same 47.5%.

    And a question asked at -1.5 on the same game gets a claim at +7.5 too,
    the frozen distribution read at +7.5 (52.1%), where the released writer
    read it at -7.5."""
    final, early = _question("nfl", "final"), _question("nfl", "early")
    conn, ids, game = _world(tmp_path, "nfl")
    got = atl.evaluate(conn, [ids["final"], ids["early"]])
    assert got["claims"] == 2
    assert got["rung_matched"] == 1 and got["rung_differs_margin"] == 1

    own = _claims(conn, ids["final"])
    assert len(own) == 1 and own[0]["ticker"].endswith("-SEA8")
    assert own[0]["line"] == pytest.approx(7.5) and own[0]["shape"] == "rung_matched"
    assert own[0]["venue_price"] == pytest.approx(0.525)
    assert own[0]["venue_implied"] == pytest.approx(0.475)
    assert own[0]["model_prob"] == pytest.approx(final["home_covers"])

    other = _claims(conn, ids["early"])
    mean, sd = early["distribution"]
    assert len(other) == 1 and other[0]["ticker"].endswith("-SEA8")
    assert other[0]["line"] == pytest.approx(7.5)
    assert other[0]["shape"] == "rung_differs_margin"
    assert other[0]["venue_implied"] == pytest.approx(0.475)
    assert other[0]["model_prob"] == pytest.approx(
        atl.model_probability("home_margin", mean, sd, 7.5), abs=1e-6)
    assert other[0]["model_prob"] == pytest.approx(0.5212, abs=1e-4), \
        "Washington +7.5, never Washington -7.5 (0.1458)"

    # WAS loses by five: covers +7.5 (and would not have covered -7.5)
    conn.execute("UPDATE games SET status = 'final', home_score = 17,"
                 " away_score = 22 WHERE id = ?", (game["game"],))
    conn.commit()
    atl.resolve_claims(conn)
    assert [r[0] for r in conn.execute("SELECT outcome FROM at_the_line_claims")] == [1, 1]


def test_the_near_start_reader_writes_its_claim_through_the_one_place(tmp_path):
    """`lines.refresh_venue_ladder`, the near-start reader, asks the venue
    (switched off under test) and writes its claims through the claim
    writer: the claim off "SEA Seahawks wins by over 7.5 points" is at
    +7.5."""
    from gridiron.market import lines

    conn, ids, _game_ = _world(tmp_path, "nfl", questions=[_question("nfl")])
    got = lines.refresh_venue_ladder(conn, [ids["final"]])
    assert got["claims"] == 1
    claim = _claims(conn, ids["final"])[0]
    assert claim["ticker"].endswith("-SEA8") and claim["line"] == pytest.approx(7.5)
    assert claim["venue_implied"] == pytest.approx(0.475)


def test_a_home_contract_is_still_read_at_minus_s(tmp_path):
    """UNT at TLSA, asked at +6.5 (the record's forecast 3147): the rung is
    "Tulsa wins by over 1.5 points", 48-49c, the home side covering -1.5, as
    before -- the distribution read at -1.5, the record's claim 1714."""
    conn, ids, _game_ = _world(tmp_path, "cfb")
    assert atl.evaluate(conn, [ids["final"]])["claims"] == 1
    claim = _claims(conn, ids["final"])[0]
    assert claim["ticker"].endswith("-TLSA2")
    assert claim["line"] == pytest.approx(-1.5)
    assert claim["venue_implied"] == pytest.approx(0.485)
    assert claim["model_prob"] == pytest.approx(0.239752, abs=1e-6)


def test_a_baseball_run_line_off_an_away_contract_is_refused(tmp_path):
    """A baseball forecast carries no margin distribution and every run line
    is asked at -1.5. TOR at BAL's rung is "Toronto wins by over 1.5 runs"
    (36-37c: Baltimore +1.5 at 63.5%), another rung than the question's, so
    the writer refuses it -- its ordinary `no_distribution` refusal -- where
    the released writer read it at -1.5 and wrote the model's -1.5 (33.7%)
    beside a price for +1.5 (the record's claims 612 and 613; 139 MLB claims,
    41 run-line recommendations). The home contract at the question's own
    -1.5 is still a rung-matched claim."""
    conn, ids, _game_ = _world(tmp_path, "mlb")
    got = atl.evaluate(conn, [ids["final"]])
    assert got["claims"] == 0 and got["no_distribution"] == 1
    assert conn.execute("SELECT COUNT(*) FROM at_the_line_claims").fetchone()[0] == 0

    (tmp_path / "home").mkdir()
    conn2, ids2, _g = _world(tmp_path / "home", "mlb", only=("BAL2",))
    got = atl.evaluate(conn2, [ids2["final"]])
    assert got["claims"] == 1 and got["rung_matched"] == 1
    claim = _claims(conn2, ids2["final"])[0]
    assert claim["line"] == pytest.approx(-1.5)
    assert claim["model_prob"] == pytest.approx(_question("mlb")["home_covers"])
    assert claim["venue_implied"] == pytest.approx(0.325)


# --- the opening read and drift -----------------------------------------------

@pytest.mark.parametrize("sport, line, price", [
    ("nfl", 7.5, 0.475), ("mlb", 1.5, 0.635), ("cfb", -1.5, 0.485)])
def test_the_opening_read_names_the_line_its_rung_sells(tmp_path, sport, line, price):
    conn, _ids, game = _world(tmp_path, sport)
    opened = views._opening_price(conn, game["game"], "spread", flip=False)
    assert opened["line"] == pytest.approx(line)
    assert opened["price"] == pytest.approx(price)


def test_drift_pairs_a_claim_with_its_own_contracts_opening_read(tmp_path):
    """Every claim is set beside the opening read of the contract that sells
    its own line -- never the other sign's contract at the same strike. The
    released matching took "WAS Commanders wins by over 1.5" and "SEA
    Seahawks wins by over 1.5" as one rung at -1.5 and opened the claim at
    the Seahawks' 24.5% where its own contract opened at 19.5%, and found no
    opening read at all for a claim at +1.5."""
    conn, ids, game = _world(tmp_path, "nfl", questions=[_question("nfl")])
    atl.evaluate(conn, [ids["final"]])
    written = conn.execute("SELECT c.*, p.predictor, p.market_type, p.subject,"
                           " p.line_asked FROM at_the_line_claims c"
                           " JOIN predictions p ON p.id = c.prediction_id").fetchone()
    pairs = drift._pairs_of(conn, [written])
    assert len(pairs) == 1 and pairs[0]["opened"] == pytest.approx(0.475)
    assert pairs[0]["line"] == pytest.approx(7.5)

    def claim_at(line, n):
        return {"id": n, "prediction_id": ids["final"], "predictor": "statistical",
                "game_id": game["game"], "market": "spread", "market_type": "spread",
                "subject": game["home"], "line_asked": line, "line": line,
                "model_prob": 0.99, "venue_implied": 0.5}
    pairs = {p["line"]: p for p in drift._pairs_of(
        conn, [claim_at(-1.5, 1), claim_at(1.5, 2), claim_at(-7.5, 3), claim_at(7.5, 4)])}
    assert pairs[-1.5]["opened"] == pytest.approx(0.195)
    assert pairs[1.5]["opened"] == pytest.approx(0.245)
    assert pairs[-7.5]["opened"] == pytest.approx(0.075)
    assert pairs[7.5]["opened"] == pytest.approx(0.475)


# --- the gate -------------------------------------------------------------------

def test_the_gate_check_passes_the_shipped_readers_and_step_2_calls_it():
    audit.check_every_venue_contract_is_read_at_the_line_it_sells()
    assert audit.contract_line_faults() == []
    gate = (REPO / "tools" / "verify.py").read_text(encoding="utf-8")
    step = next(node for node in ast.parse(gate).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert any(isinstance(node, ast.Attribute)
               and node.attr == "check_every_venue_contract_is_read_at_the_line_it_sells"
               for node in ast.walk(step))


def test_the_fixture_is_the_venues_words_and_the_records_questions():
    """The line each fixture contract sells is the one its words sell, and
    each question's expected claim is worked out from the fixture alone --
    the rung by its own prices, the model's number at the line it sells."""
    for game in audit.VENUE_SPREAD_CONTRACTS_AS_SOLD:
        for _suffix, words, strike, bid, ask, sold in game["contracts"]:
            assert sold == _sold_by_the_words(game, words)
            assert abs(sold) == strike and 0 < bid < ask < 1
    nfl = _game("nfl")
    assert audit._q36_rung(nfl).endswith("-SEA8")
    own = audit._q36_expected(nfl, _question("nfl", "final"))
    assert own["line"] == 7.5 and own["shape"] == "rung_matched"
    assert audit._q36_expected(_game("mlb"), _question("mlb")) is None


def test_an_away_contract_read_at_minus_s_is_named_at_every_reader(monkeypatch):
    """The released one place, put back: the check names the one place, the
    rung, the claim writer, the opening read and drift -- and the record's
    own claim 1662 comes back, "stored at -7.5 with the model's 0.1458".

    PATCHED BY ITS DOTTED NAME, the module as the check will import it: the
    blind window drops `gridiron.market` from `sys.modules`, so after any
    earlier test that forecast, this file's `atl` can be an older module
    object than the one the readers import.
    """
    def negated(quote):
        if quote["line"] is None:
            return None
        return (float(quote["line"]) if quote["yes_side"] in ("home", "over")
                else -float(quote["line"]))
    monkeypatch.setattr("gridiron.market.at_the_line.home_view_line", negated)
    with pytest.raises(audit.LawViolation) as caught:
        audit.check_every_venue_contract_is_read_at_the_line_it_sells()
    text = str(caught.value)
    for door in ("at_the_line.home_view_line", "at_the_line.rung_for",
                 "at_the_line.evaluate", "views._opening_price", "drift._pairs_of"):
        assert door in text, door
    assert "'SEA Seahawks wins by over 7.5 points'" in text
    assert "stored at -7.5 with the model's 0.1458 beside 0.4750" in text
    assert "got a claim at -1.5 with the model's 0.3366 beside 0.6350" in text


@pytest.mark.parametrize("stored", ["at -s", "as a home contract at -s"])
def test_an_away_contract_stored_at_minus_s_is_named_at_the_storage(monkeypatch, stored):
    """THE PROVER (2026-09-30). The ruling reads "the stored number as it
    is", so the reading is only as right as the storage. An away contract
    STORED at -s -- or placed on the home side at -s -- is `parse_markets`'
    fault: the check names it there, for each of the fixture's six away
    contracts, and names every reader it reaches, but not the one place,
    which read it as stored. As first built the check named only the one
    place ("... stored at -1.5 on the away side is read at -1.5") and never
    the storage. (Patched by its dotted name, as below.)"""
    import importlib

    real = importlib.import_module("gridiron.market.kalshi").parse_markets

    def misstored(*args, **kwargs):
        quotes, unread = real(*args, **kwargs)
        out = []
        for q in quotes:
            if q["yes_side"] == "away":
                q = dict(q, line=-q["line"])
                if stored != "at -s":
                    q["yes_side"] = "home"
            out.append(q)
        return out, unread
    monkeypatch.setattr("gridiron.market.kalshi.parse_markets", misstored)
    faults = audit.contract_line_faults()
    storage = [f for f in faults if f.startswith("kalshi.parse_markets")]
    assert len(storage) == 6, storage
    assert any("'SEA Seahawks wins by over 7.5 points'" in f and "stored at -7.5" in f
               and "at +7.5, from the away side" in f for f in storage), storage
    assert not any(f.startswith("at_the_line.home_view_line") for f in faults), faults
    for door in ("at_the_line.rung_for", "at_the_line.evaluate",
                 "views._opening_price", "drift._pairs_of"):
        assert any(f.startswith(door) for f in faults), door


def test_a_ladder_matched_across_the_two_signs_in_drift_is_named(monkeypatch):
    """Drift's matching put back to the strike alone: a home contract at -s
    and an away one at +s taken as one rung. The check names drift, and only
    drift. (Patched by its dotted name, as above.)"""
    import importlib

    now = importlib.import_module("gridiron.market.at_the_line")

    def by_the_strike(ladder, claim):
        return now.rung_for([q for q in ladder
                             if abs(now.home_view_line(q)) == abs(claim["line"])])
    monkeypatch.setattr("gridiron.drift._opening_at_the_claims_line", by_the_strike)
    faults = audit.contract_line_faults()
    assert faults and all(f.startswith("drift._pairs_of") for f in faults), faults
    assert any("'WAS Commanders wins by over 1.5 points'" in f for f in faults)


def test_a_second_claim_writer_is_named_as_the_near_start_readers_fault(monkeypatch):
    """The near-start reader is held by its source: it calls the claim
    writer, and nothing else in the package inserts a claim. A second writer
    is named."""
    monkeypatch.setattr(audit, "_q36_claim_writers",
                        lambda: ["market/at_the_line.py:evaluate",
                                 "market/lines.py:refresh_venue_ladder"])
    faults = audit.contract_line_faults()
    assert faults and all(f.startswith("lines.refresh_venue_ladder") for f in faults)
    assert "market/lines.py:refresh_venue_ladder" in faults[0]


def test_the_shipped_package_has_one_claim_writer():
    assert audit._q36_claim_writers() == ["market/at_the_line.py:evaluate"]
