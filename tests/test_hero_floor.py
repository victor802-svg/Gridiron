"""The hero's floor (R3, 2026-09-05): a claim under HERO_MIN_CLAIM never leads."""
from __future__ import annotations

import pytest

from gridiron import audit, config, language, views

WIDE = {"width": 1440, "height": 900}


def test_the_floor_is_declared_and_dated():
    assert config.HERO_MIN_CLAIM == 0.55
    assert config.HERO_MIN_CLAIM_DECLARED == "2026-09-05"


def test_the_no_lead_sentence_is_composed_in_words():
    said = language.no_lead_line(config.HERO_MIN_CLAIM)
    assert "55%" in said and "lead" in said
    assert audit.plain_words_violations(said) == []


def test_the_payload_carries_the_floor_and_the_sentence(league):
    payload = views.week(league, "nfl", 2025, 7)
    assert payload["hero_min_claim"] == config.HERO_MIN_CLAIM
    assert payload["no_lead"] == language.no_lead_line(config.HERO_MIN_CLAIM)


def _open_week(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/record'")
    with page.expect_response(lambda r: "/api/week" in r.url):
        page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-market-tabs .market-tab", timeout=10000)


CARDS = """[
  {prediction_id: 1, shown_prob: 0.5499, model_prob: 0.5499, abs_gap: 0.3, phrase: 'A', row_title: 'a'},
  {prediction_id: 2, shown_prob: 0.55, model_prob: 0.55, abs_gap: 0.2, phrase: 'B', row_title: 'b'},
  {prediction_id: 3, shown_prob: 0.80, model_prob: 0.80, abs_gap: 0.1, phrase: 'C', row_title: 'c'},
  {prediction_id: 4, shown_prob: 0.90, model_prob: 0.90, abs_gap: 0.05, phrase: 'D', row_title: 'd',
   method_note: 'a coin flip by construction'}
]"""


def test_the_selection_filters_at_the_boundary_and_follows_the_sort(page):
    """AT the boundary: 0.55 leads, 0.5499 does not (MENTOR 3)."""
    _open_week(page)
    lead = page.evaluate(f"(window.Gridiron.selectHero({CARDS}, 'disagreement', 0.55) || {{}}).prediction_id")
    assert lead == 2, "the sharpest disagreement at or above the floor leads"
    lead = page.evaluate(f"(window.Gridiron.selectHero({CARDS}, 'confidence', 0.55) || {{}}).prediction_id")
    assert lead == 3, "by confidence the largest claim above the floor leads; the flagged one never does"
    none = page.evaluate(f"window.Gridiron.selectHero({CARDS}, 'disagreement', 0.95)")
    assert none is None
    pool = page.evaluate(f"window.Gridiron.heroCandidates({CARDS}, 'disagreement', 0.55).map(c => c.prediction_id)")
    assert pool == [2, 3], "the carousel steps through the candidates above the floor, in sort order"


def test_a_tab_with_no_pick_at_the_floor_shows_the_sentence_not_a_hero(page):
    _open_week(page)
    page.evaluate(f"""() => window.Gridiron.renderHero({CARDS}, 'disagreement',
        {{disagreement: 'Sharpest disagreement'}}, 0.95, 'Nothing leads this tab: no pick reaches 95%.')""")
    host = page.query_selector("#week-hero")
    assert host.is_visible()
    assert page.text_content("#week-hero .hero-none").strip() == "Nothing leads this tab: no pick reaches 95%."
    assert page.query_selector("#week-hero .hero-pick") is None
    assert page.evaluate("document.getElementById('week-hero').dataset.id") is None


def test_the_shipped_slate_never_leads_with_a_claim_under_the_floor(page):
    _open_week(page)
    tabs = page.evaluate("[...document.querySelectorAll('.market-tab')].map(b => b.dataset.market)")
    for market in tabs:
        page.click(f".market-tab[data-market='{market}']")
        page.wait_for_timeout(250)
        state = page.evaluate("""() => {
            const host = document.getElementById('week-hero');
            if (host.hidden) return {hidden: true};
            const none = host.querySelector('.hero-none');
            const chance = host.querySelector('.chance-hero');
            return {hidden: false, none: none ? none.textContent : null,
                    chance: chance ? chance.textContent : null, id: host.dataset.id || null};
        }""")
        if state.get("hidden") or state.get("none"):
            continue
        import re
        m = re.search(r"(\d+)%", state["chance"] or "")
        assert m, f"{market}: the hero shows no chance"
        assert int(m.group(1)) >= 55, f"{market}: the hero leads with {state['chance']}"


def test_the_guard_sees_a_hero_showing_a_claim_under_the_floor():
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert audit.hero_flag_faults(js) == []
    broken = js.replace("(shownProb(c) || 0) >= minClaim", "true", 1)
    assert broken != js
    faults = audit.hero_flag_faults(broken)
    assert faults and any("floor" in f for f in faults), faults
