"""One card, three states (GRIDIRON_THREE_STATES, 2026-09-08).

A pick is born on Upcoming, moves to Live when its game starts, and ends on
Results when the game is final. THE STATE IS DERIVED, never clicked: a state a
person can set is a state that can disagree with the game being played.

The tests that earn their place are the movement one -- a card leaves Upcoming
and appears on Live within one poll, and reaches settled within one resolve --
and the four that keep anything actionable off a live card.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gridiron import audit, db, language, shortlist, views
from gridiron.data.team_colours import TEAM_COLOURS

DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})

WEB = Path(views.__file__).resolve().parent / "web"


def _world(tmp_path, *, status="scheduled", home_score=None, away_score=None):
    conn = db.open_db(tmp_path / "states.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g0', 'mlb', 2026, 1, 'R', 'CHC', 'MIL',"
        " '2026-09-09T00:00:00Z', ?, '2026-09-08', ?, ?)",
        (status, home_score, away_score))
    conn.commit()
    return conn


def _pick(conn, *, subject="CHC", prob=0.62):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-08T00:00:00Z', 'mlb', 'g0', 'moneyline', ?, NULL,"
        " ?, 'win', 'statistical', 'final', 'fs2', ?, 'test')",
        (subject, prob, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return pid


def _go_live(conn, *, period="Top 6th", home=3, away=2):
    conn.execute(
        "UPDATE games SET status = 'in', home_score = ?, away_score = ?,"
        " live_period = ?, live_updated_utc = ? WHERE id = 'g0'",
        (home, away, period, db.utcnow()))
    conn.commit()


# --- the movement, which is the whole idea -----------------------------------

def test_a_card_moves_to_live_on_its_own_and_then_to_settled(tmp_path):
    """THE POLLER MOVES IT, NOT A CLICK. `games.status` is what the live poll
    writes; the tab a card sits on is read off that, so a card cannot be in a
    state its game is not in."""
    conn = _world(tmp_path)
    _pick(conn)

    before = views.week(conn, "mlb", 2026, 1)["today"]
    assert before["live_n"] == 0
    assert before["watching_n"] + before["n"] == 1, "it starts on Upcoming"

    _go_live(conn)
    during = views.week(conn, "mlb", 2026, 1)["today"]
    assert during["live_n"] == 1, "one poll moved it"
    assert during["watching_n"] + during["n"] == 0, "and it left Upcoming"
    assert "In progress" in during["live_heading"]

    conn.execute("UPDATE games SET status = 'final' WHERE id = 'g0'")
    conn.commit()
    after = views.week(conn, "mlb", 2026, 1)["today"]
    assert after["live_n"] == 0, "and it left Live when the game ended"
    assert after["settled_n"] == 1


def test_the_state_is_read_off_the_game_and_nothing_else():
    assert views.card_state("scheduled") == "upcoming"
    assert views.card_state("in") == "live"
    assert views.card_state("final") == "final"
    # A STATUS THIS PROJECT DOES NOT KNOW IS NOT LIVE. Showing an unknown
    # state as live would be a claim about a game.
    assert views.card_state(None) == "upcoming"
    assert views.card_state("postponed") == "upcoming"


# --- what a live card may not carry ------------------------------------------

def test_a_live_card_carries_nothing_that_can_be_acted_on(tmp_path):
    """THE IN-GAME RULE, ON THE SCREEN. A score this app reads up to ninety
    seconds late, against a market priced off the feed, is adversely selected
    by construction -- so the sizing path refuses it, the claim writer refuses
    a quote taken after first pitch, and the card carries no number at all."""
    conn = _world(tmp_path)
    _pick(conn)
    _go_live(conn)
    today = views.week(conn, "mlb", 2026, 1)["today"]
    card = today["live"][0]
    for forbidden in audit.LIVE_FORBIDDEN:
        assert card.get(forbidden) is None, forbidden
    assert card["score_words"] == "MIL 2 – CHC 3"
    assert card["period_words"] == "Top 6th"
    assert "read" in card["polled_words"]
    audit.check_the_live_card_offers_nothing({"today": today})


def test_the_guard_names_each_thing_a_live_card_may_not_carry():
    for field, value in (("size_words", "$15"), ("edge_line_words", "+2.0¢"),
                         ("payout_words", "2.00x"), ("price_words", "50¢")):
        planted = {"today": {"live": [
            {"state": "live", "n": 1, "question": "x", field: value}]}}
        assert audit.live_card_faults(planted), field
        with pytest.raises(audit.LawViolation):
            audit.check_the_live_card_offers_nothing(planted)
    # and an upcoming card carrying the same fields is fine
    fine = {"today": {"clears": [
        {"state": "upcoming", "n": 1, "question": "x", "size_words": "$15"}]}}
    assert audit.live_card_faults(fine) == []


def test_a_stale_score_is_visible_as_stale():
    """A SCORE WITH NO TIME ON IT IS A SCORE A READER TRUSTS TOO MUCH. The
    poller runs every ninety seconds while a window is open and not at all
    otherwise, so a card can hold a number that stopped being true."""
    assert "just now" in language.polled_words(
        "2026-09-08T03:00:00Z", "2026-09-08T03:01:00Z")
    assert "20 minutes ago" in language.polled_words(
        "2026-09-08T03:00:00Z", "2026-09-08T03:20:00Z")
    assert "3 hours ago" in language.polled_words(
        "2026-09-08T00:00:00Z", "2026-09-08T03:00:00Z")
    assert "no score" in language.polled_words(None)


def test_the_taken_pick_leads_the_live_tab_and_says_only_that(tmp_path):
    """The game he has money on is the one he is looking for. WHICH WAY IT IS
    GOING IS THE GAME'S TO SAY: he declined a running verdict on 2026-09-08,
    and the reasoning stands -- it is the feature that makes a person watch
    the app instead of the game."""
    conn = _world(tmp_path)
    first = _pick(conn, subject="CHC")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-08T00:00:00Z', 'mlb', 'g0', 'total',"
        " 'MIL at CHC', 8.5, 0.58, 'under', 'statistical', 'final', 'fs2',"
        " ?, 'test')", (WHOLE,))
    second = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [second])
    views.take_pick(conn, second)
    _go_live(conn)

    live = views.week(conn, "mlb", 2026, 1)["today"]["live"]
    assert len(live) == 2
    assert live[0]["prediction_id"] == second, "the marked one leads"
    assert live[0]["taken_badge"] == "Yours"
    assert live[1].get("taken_badge") is None
    # and nothing on it says whether it is winning
    blob = json.dumps(live[0]).lower()
    for forbidden in ("winning", "ahead", "losing", "on track"):
        assert forbidden not in blob, forbidden


# --- the richer card ---------------------------------------------------------

def test_the_card_shows_what_the_record_already_knew(tmp_path):
    """NOTHING NEW IS FETCHED. Every line is a read of a table some factor
    already filled."""
    conn = _world(tmp_path)
    conn.execute("INSERT INTO mlb_probables (game_id, side, pitcher_id,"
                 " pitcher_name, recorded_utc) VALUES ('g0', 'home', 1,"
                 " 'A Pitcher', '2026-09-08T00:00:00Z')")
    conn.commit()
    _pick(conn)
    card = views.week(conn, "mlb", 2026, 1)["today"]["watching"][0]
    assert card["home_starter"] == "A Pitcher"
    # ABSENT IS NOT ZERO AND NOT AN EM DASH: a slate this early has no away
    # starter, and the card says which fact that is.
    assert card["away_starter"] == "starter not named"
    assert "first_sentence" in card


def test_a_club_wears_its_own_colour_and_white_can_be_read_on_it():
    """MEASURED PER CLUB, because white on a club's primary is a different
    pair for every club and some of them fail."""
    cubs = views.team_colours("mlb", "CHC")
    assert cubs["known"] and cubs["primary"] == "0e3386"
    assert cubs["how"] in ("primary", "alternate", "darkened")

    def ratio(one, two):
        def lin(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        def lum(value):
            r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
            return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
        a, b = lum(one), lum(two)
        hi, lo = max(a, b), min(a, b)
        return (hi + 0.05) / (lo + 0.05)

    for sport, clubs in TEAM_COLOURS.items():
        for tricode, (primary, on_white, how) in clubs.items():
            assert ratio("ffffff", on_white) >= 4.5, (sport, tricode, how)
    # an unknown club is neutral rather than invented
    assert views.team_colours("mlb", "ZZZ")["known"] is False


def test_no_club_mark_is_stored_anywhere():
    """The payload the colours come from carries `logos`. None is taken."""
    audit.check_no_marks()
    assert audit.mark_faults()  == []


def test_the_payout_is_the_biggest_number_and_the_edge_is_a_line():
    """THE OPERATOR'S RULING OF 2026-09-08. A payout is what a reader of a
    sportsbook reads first; the edge is what ranks a card, on its own line."""
    css = (WEB / "style.css").read_text(encoding="utf-8")
    root = css[css.index(":root {"):css.index("* { box-sizing")]
    tokens = {name: value for name, value in
              re.findall(r"--([a-z0-9-]+):\s*([0-9.]+)px;", root)}

    def size(selector):
        """THE SCALE IS IN TOKENS NOW, so this resolves one before measuring:
        a test that only reads literal pixels would pass a card whose sizes
        all came from the same token."""
        block = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
        assert block, selector
        found = re.search(r"font-size:\s*(?:var\(--([a-z0-9-]+)\)|([0-9.]+)px)",
                          block.group(1))
        assert found, selector
        return float(tokens[found.group(1)] if found.group(1) else found.group(2))

    assert size(".box-payout .box-value") > size(".box-value")
    assert size(".box-payout .box-value") > size(".face-q")
    # THE CHIP DOES NOT REPEAT ITS OWN LABEL (fixed 2026-09-08). The box is
    # headed "Pays"; the chip said "pays 1.65x" beneath it, which rendered as
    # "Payspays 1.65x" the first time a card carried a real payout.
    assert language.payout_chip_words(1.65) == "1.65x"
    assert language.price_under_payout_words(0.61) == "61¢ a contract"
    # THE VALUE DOES NOT REPEAT ITS LABEL (NIGHT_AUDIT item 6, 2026-09-08):
    # the line is headed "Edge after fees" and the value used to say it again.
    assert language.edge_line_words(3.2) == "+3.2¢"
    assert language.edge_line_words(3.2, other_side=True) == "+3.2¢"


def test_one_type_scale_and_four_sizes():
    """A FIFTH SIZE IS HOW A CARD GROWS A HIERARCHY NOBODY CHOSE."""
    css = (WEB / "style.css").read_text(encoding="utf-8")
    root = css[css.index(":root {"):css.index("* { box-sizing")]
    for token in ("--face-band", "--face-q", "--face-chip", "--face-meta",
                  "--face-rhythm"):
        assert token in root, token


# --- what the old page took with it ------------------------------------------

def test_the_old_picks_page_is_gone_by_name():
    """Each removal, checked where it would come back."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    for gone in ('id="week-hero"', 'id="week-sort-seg"', 'id="week-tier-seg"',
                 'id="week-view"', 'id="notices-summary"'):
        assert gone not in html, gone
    for gone in ("renderHero", "renderViewMenu", "renderTierFilter",
                 "renderNotices", "heroIndex"):
        assert gone not in app, gone
    assert ".hero" not in css
    # and the two tabs took their place
    assert 'id="state-tabs"' in html
    assert 'data-state="live"' in html


def test_the_nav_is_still_four_pages_and_the_controls_still_two_rows():
    """A LAYOUT DOES NOT GET TO BREAK A LAW. Live is a tab, not a fifth page,
    and the state tabs replaced three segmented controls rather than joining
    them."""
    audit.check_the_nav_is_four_pages()
    assert audit.picks_control_row_faults() == []
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert audit.picks_control_rows(html) == ["week-market-tabs", "state-tabs"]


# --- the forecaster control, and the unit (operator ruling, 2026-09-08) -----

def test_picks_carries_no_control_to_switch_forecaster():
    """A SWITCH ON THE CARD FACE LETS A READER PICK WHICHEVER FORECASTER
    FLATTERS EACH PICK, and `picks_taken` would then record that choosing
    rather than one forecaster's work. The choice is a Settings default, which
    attributes every taken row to one forecaster for a stretch of days -- and
    the settings table is append-only, so the stretch is dated at both ends.
    """
    html = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    for gone in ("week-forecaster-seg", "week-view-button", "data-forecaster"):
        assert gone not in html, gone
        assert gone not in app, gone


def test_the_default_forecaster_is_a_dated_setting(tmp_path):
    from gridiron import settings

    conn = _world(tmp_path)
    assert settings.value(conn, "default_forecaster") == "statistical"
    changed = settings.set_value(conn, "default_forecaster", "llm")
    assert changed["changed"] and changed["was"] == "statistical"
    row = conn.execute(
        "SELECT changed_utc, previous, value FROM settings"
        " WHERE name = 'default_forecaster' ORDER BY id DESC LIMIT 1").fetchone()
    assert row["changed_utc"] and row["previous"] == "statistical"
    assert row["value"] == "llm"
    # and only the two forecasters this record holds
    for bad in ("both", "", "ensemble"):
        with pytest.raises(settings.SettingRefused):
            settings._a_forecaster(bad)


def test_the_default_forecaster_decides_whose_questions_picks_shows(tmp_path):
    from gridiron import settings

    conn = _world(tmp_path)
    _pick(conn, subject="CHC")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-08T00:00:00Z', 'mlb', 'g0', 'total', 'MIL at CHC',"
        " 8.5, 0.61, 'under', 'llm', 'final', 'fs2', ?, 'test')", (WHOLE,))
    other = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [other])

    assert "the model has" in views.week(conn, "mlb", 2026, 1)["today"]["count_words"]
    settings.set_value(conn, "default_forecaster", "llm")
    assert "the reasoning pass has" in \
        views.week(conn, "mlb", 2026, 1)["today"]["count_words"]


def test_the_unit_and_the_denominator_agree():
    """THE CAP WAS BEING EXCEEDED BY HALF AGAIN. A unit of $15 against a
    bankroll of $1,000 is 1.5% of the money; at the old denominator of 100
    units the 2% ceiling resolved to 2.00 units, and two units at $15 is $30 --
    3% of the money, in the one constant that exists to stop that.
    """
    from gridiron import config
    from gridiron.market import recommend

    assert config.BANKROLL_UNITS == pytest.approx(1000.0 / 15.0)
    assert config.BANKROLL_UNITS_DECLARED.startswith("2026-09-08")
    assert config.FLAT_UNIT == 1.0

    # one unit is one and a half per cent of the ring-fenced money
    assert 100.0 / config.BANKROLL_UNITS == pytest.approx(1.5)
    # and the declared ceiling resolves to exactly that ceiling
    capped = recommend.size_for(model_prob=0.92, price=0.50, settled=200,
                                measured_edge=True)
    # NEVER OVER, and within one rounding step of the ceiling. `size_for`
    # rounds units to three decimals for display, so 1.333 units is 1.99950%
    # rather than 2.00000% -- the direction that matters is that rounding can
    # only take it under.
    share = capped["units"] / config.BANKROLL_UNITS
    assert share <= config.MAX_FRACTION
    assert share == pytest.approx(config.MAX_FRACTION, abs=1e-4)
    assert language.size_words(units=capped["units"], flat=False, why=None,
                               unit_dollars=15.0).startswith("$20")
    assert language.size_words(units=config.FLAT_UNIT, flat=True,
                               why="no measured edge yet",
                               unit_dollars=15.0).startswith("$15")


def test_both_forecasters_still_write_with_the_control_removed():
    """MEASURED ON A COPY OF THE RECORD, not asserted: the daily task wrote 50
    statistical rows and 30 from the reasoning pass for slate 166 on
    2026-09-08, with the View menu already removed.

    The structural half is checked here, because it is the half that could
    silently change: `use_llm` is the scheduler's argument and nothing in the
    read path references it.
    """
    from pathlib import Path as _Path

    from gridiron import api, tasks, views as _views

    assert "use_llm" in _Path(tasks.__file__).read_text(encoding="utf-8")
    for module in (_views, api):
        assert "use_llm" not in _Path(module.__file__).read_text(encoding="utf-8"), (
            f"{module.__name__} can reach the reasoning pass's switch")
