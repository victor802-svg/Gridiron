"""The cards layout: what must be true at every width.

REPLACES `tests/test_desk.py`, which is deleted. That file pinned two layouts
-- a desk of tiles beside a rail above 1280px, and compact rows below it -- and
half of its 36 tests existed only to prove the two agreed with each other, or
that the breakpoint switched between them at the right moment. There is one
layout now, so those tests are not weakened, they are ANSWERED: a claim about
whether two layouts agree cannot be made about one.

WHAT SURVIVED IS RE-POINTED, NOT DROPPED, which is what ruling R1 asks. No
card truncates; nothing overflows sideways; a tap target is big enough; there
is one greeting; a score arriving does not re-sort the slate; the live mark is
never green; the tier default holds. Each of those was true of the desk, is
true of the cards, and is asserted here against the new markup.
"""

from __future__ import annotations

import re

import pytest

from gridiron import audit

#: THE THREE WIDTHS THE BRIEF NAMES. They are no longer three LAYOUTS -- they
#: are three widths of one layout, which is the whole point of the change, so
#: every test below runs the same assertions at whichever of them it needs.
WIDE = {"width": 1440, "height": 900}
MID = {"width": 900, "height": 900}
PHONE = {"width": 390, "height": 844}


def _open_week(page, size):
    """Open the slate at a width and WAIT FOR IT, not for a duration.

    A fixed sleep is the flakier choice: simultaneously too long on a fast
    machine and too short on a loaded one, and the failure it produces on the
    loaded one looks like a broken assertion rather than a race.

    THE CONDITION IS SIMPLER THAN IT WAS. The old helper had to wait for "the
    layout that BELONGS at this width", because during a resize both could
    exist for a frame and asserting then was what the sleep had been
    accidentally avoiding. One layout has no such moment.
    """
    page.set_viewport_size(size)
    # A FRESH FETCH EVERY TIME, and the helper waits for THAT response.
    #
    # Without this, a test that intercepts `/api/week` can assert against the
    # render from an EARLIER, un-intercepted fetch: the app had already drawn
    # the slate before the route was registered, the wait condition was
    # satisfied by that first render, and the intercepted payload arrived after
    # the assertions had run. The old desk helper hid this by accident --
    # changing the viewport crossed the breakpoint, which forced a re-render,
    # which happened to be the routed one. One layout has no breakpoint to
    # cross, so the accident is gone and the wait has to be honest.
    page.evaluate("location.hash = '#/record'")
    with page.expect_response(lambda r: "/api/week" in r.url):
        page.evaluate("location.hash = '#/games'")
    page.wait_for_function(
        """() => document.body.dataset.ready === 'true'
                 && document.querySelectorAll('#games-rows .game').length > 0""",
        timeout=15000,
    )
    # AND FOR THE ARRIVAL TO END (R4, 2026-09-05). The grid and the hero come
    # in from one per cent below over 200ms; a position measured a frame into
    # that reads the slide as movement. "Waiting for the slate" now includes
    # waiting for it to settle.
    page.wait_for_function(
        """() => ['games-rows', 'games-notes'].every(id => {
            const el = document.getElementById(id);
            if (!el || el.hidden) return true;
            const cs = getComputedStyle(el);
            return cs.opacity === '1' && cs.transform === 'none';
        })""", timeout=5000)


def _cards(page):
    return page.evaluate(
        "document.querySelectorAll('#games-rows .game').length")


def _open_props(page, size):
    """The Props page, waited for the same way."""
    page.set_viewport_size(size)
    page.evaluate("location.hash = '#/record'")
    with page.expect_response(lambda r: "/api/week" in r.url):
        page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-chips .chip-btn", timeout=15000)


# --- what the brief asks the layout to be -----------------------------------

@pytest.mark.parametrize("size", [WIDE, MID, PHONE],
                         ids=["1440", "900", "390"])
def test_one_layout_renders_at_every_width(page, size):
    """The same elements exist at 1440, 900 and 390.

    THIS IS THE RULING, ASSERTED. R1 says one layout for every width; the way
    that fails is for something to appear or disappear as the window changes,
    which is exactly what the desk did and exactly what nobody notices until a
    reader on a laptop sees a different page from a reader on a phone.
    """
    _open_week(page, size)
    shape = page.evaluate("""() => ({
        rows: document.querySelectorAll('#games-rows .game').length,
        picks: document.querySelectorAll('#games-rows .game .pick').length,
        teams: document.querySelectorAll('#games-rows .game .team').length,
        strip: !!document.querySelector('#day-strip') && !document.getElementById('day-strip').hidden,
        pulse: document.querySelectorAll('#day-jobs .day-job').length,
    })""")
    assert shape["rows"] > 0, "no row rendered at all"
    assert shape["picks"] == shape["rows"], "a row is missing its pick block at this width"
    assert shape["teams"] == 2 * shape["rows"], "a row is missing a team line at this width"
    assert shape["strip"], "the day strip is absent at this width"
    assert shape["pulse"] >= 3, "the pulse is absent at this width"


def test_no_card_truncates(page):
    """No ellipsis anywhere in the slate, at the width that used to have one.

    RE-POINTED FROM `test_no_tile_truncates`, and widened: the old test looked
    at the frame at desk width, where nothing truncated, and missed
    "BRISSETT * PASSI..." on the phone for weeks. A truncated card has told the
    reader there is something it is not showing and then not shown it.
    """
    _open_week(page, PHONE)
    bad = page.evaluate("""() => [...document.querySelectorAll('#view-games *')]
        .filter(e => getComputedStyle(e).textOverflow === 'ellipsis')
        .map(e => e.className || e.tagName)""")
    assert not bad, f"these elements truncate: {bad[:6]}"


@pytest.mark.parametrize("size", [WIDE, MID, PHONE],
                         ids=["1440", "900", "390"])
def test_nothing_overflows_sideways(page, size):
    _open_week(page, size)
    over = page.evaluate(
        "document.documentElement.scrollWidth - window.innerWidth")
    assert over <= 0, f"the page overflows sideways by {over}px at {size}"


def test_every_tap_target_on_the_phone_is_big_enough(page):
    """44px, the platform minimum. A control nobody can hit is not a control."""
    _open_week(page, PHONE)
    small = page.evaluate("""() => [...document.querySelectorAll(
        '#view-games button, #view-games a, #view-games select')]
        .filter(e => e.offsetParent !== null)
        .map(e => ({ what: e.className || e.tagName,
                     h: Math.round(e.getBoundingClientRect().height) }))
        .filter(e => e.h > 0 && e.h < 44)""")
    # NO EXEMPTIONS. The hero's dots were exempted here for one commit,
    # because an 8px mark cannot be a 44px target -- and the answer was that
    # the MARK and the TARGET do not have to be the same element. The button is
    # 44px and draws an 8px dot inside it.
    assert not small, f"tap targets under 44px: {small[:6]}"


def test_there_is_exactly_one_greeting(page):
    """The greeting used to be MOVED between two homes depending on width."""
    for size in (WIDE, PHONE):
        _open_week(page, size)
        n = page.evaluate("document.querySelectorAll('#greeting').length")
        assert n == 1, f"{n} greetings at {size['width']}px"


# --- one number per card (R2) -----------------------------------------------

def test_a_collapsed_card_shows_one_number(page):
    """R2. The market's figure is one tap away, not beside the model's.

    A card showing two percentages makes a reader work out which one is the
    claim, and the one they are most likely to read is whichever is larger.
    """
    _open_week(page, WIDE)
    if not _cards(page):
        pytest.skip("no cards on this slate")
    # WHAT A READER SEES WITHOUT HOVERING. The market hint is a hover reveal
    # the brief asks for by name, so it is in the markup and at zero opacity;
    # counting the text alone would count a number nobody is being shown.
    # RE-POINTED 2026-09-08. The old card had a `.card-head` that carried the
    # collapsed face; the CARD_FACE card IS the collapsed face, with its
    # reasons in a `.face-why` that starts hidden. So this reads the card and
    # skips that body, which is the same question asked of the new shape.
    numbers = page.evaluate(r"""() => {
        const card = document.querySelector('#games-rows .game');
        const why = card.querySelector('.game-more');
        const out = [];
        card.querySelectorAll('*').forEach(e => {
            if (e.children.length) return;
            if (why && why.contains(e)) return;
            if (parseFloat(getComputedStyle(e).opacity) === 0) return;
            (e.textContent.match(/\d+(\.\d+)?%/g) || [])
                .forEach(m => out.push(m));
        });
        return out;
    }""")
    assert len(numbers) <= 1, (
        f"a collapsed card shows {len(numbers)} numbers at rest: {numbers}")

def test_a_card_expands_in_place_and_shows_the_why(page):
    """R2's other half: the reasons are one tap away, and they arrive."""
    _open_week(page, WIDE)
    if not _cards(page):
        pytest.skip("no cards on this slate")
    # RE-POINTED 2026-09-08 at the CARD_FACE card: a Why control that reveals
    # a `.face-why` already in the tree by clearing `hidden`, rather than a
    # card head that toggled an `open` class. The promise is R2's and is
    # unchanged -- the reasons are one tap away, they arrive, and the card
    # does not move under the reader while they do.
    result = page.evaluate("""async () => {
        const card = document.querySelector('#games-rows .game');
        const before = card.getBoundingClientRect().top;
        const control = card.querySelector('.game-head');
        if (!control) return {skip: true};
        control.click();
        await new Promise(r => setTimeout(r, 250));
        const body = card.querySelector('.game-more');
        return {
            open: !!(body && !body.hidden),
            expanded: control.getAttribute('aria-expanded'),
            text: body ? body.innerText.trim().length : 0,
            moved: Math.abs(card.getBoundingClientRect().top - before),
        };
    }""")
    assert result["open"], "the card did not open"
    assert result["expanded"] == "true", "aria-expanded did not follow"
    assert result["text"] > 0, "the card opened on nothing"
    assert result["moved"] < 2, (
        f"the card moved {result['moved']}px on opening; it expands IN PLACE "
        f"so the reader keeps their place")


# --- the filter chips (R4, re-homed 2026-09-24) -----------------------------
#
# The market tabs went with the old Picks page (GRIDIRON_BOARD puts no control
# row above the first game). The promises they carried live on the Props
# page's chips now: derived from the declared list, never a written row; a
# zero-count chip stays visible; every chip carries its count.

def test_the_props_chips_come_from_the_declared_list(page):
    """R4. A fifth market must appear without a UI change."""
    from gridiron import config

    _open_props(page, WIDE)
    sport = page.evaluate("window.Gridiron.state.sport")
    keys = page.evaluate(
        """[...document.querySelectorAll('#props-chips .chip-btn')]
             .map(t => t.dataset.key)""")
    assert keys and keys[0] == "", "the first chip is not 'All'"
    assert keys[1] == "alt", "the second chip is not 'Alt lines'"
    assert keys[2:] == list(config.SPORT_PROP_MARKETS.get(sport, ())), (
        f"the chips for {sport} are {keys[2:]}, and the declared prop markets "
        f"are {list(config.SPORT_PROP_MARKETS.get(sport, ()))}. A chip row "
        f"that does not match the declaration is a hardcoded row.")


def test_a_zero_count_chip_stays_visible(page):
    """R4. "No rushing-yards questions tonight" is a fact about the slate."""
    _open_props(page, WIDE)
    counts = page.evaluate(
        """[...document.querySelectorAll('#props-chips .chip-btn')]
             .map(t => ({ n: t.querySelector('.chip-n').textContent,
                          shown: t.offsetParent !== null }))""")
    zeros = [c for c in counts if c["n"] == "0"]
    assert zeros, "the fixture slate has no zero-count family to show"
    assert all(c["shown"] for c in zeros), (
        "a zero-count chip was hidden, which hides the fact that the slate "
        "asked nothing in it")


def test_every_chip_carries_its_count(page):
    """LAW 4's habit, applied to a chip: no number without what it counts."""
    _open_props(page, WIDE)
    missing = page.evaluate(
        """[...document.querySelectorAll('#props-chips .chip-btn')]
             .filter(t => !t.querySelector('.chip-n'))
             .map(t => t.textContent)""")
    assert not missing, f"chips with no count: {missing}"


# --- what the hero's test protected, on the card that replaced it ----------
#
# `test_the_hero_says_which_question_it_is_answering` checked that the hero's
# tag matched the sort it was drawn under -- a hero labelled "sharpest
# disagreement" over a list ordered by confidence is a page contradicting
# itself. THE HERO WAS REMOVED ON 2026-09-08 and so was the sort, so there is
# no tag and no ordering to contradict; every card carries its own question in
# its own words, which `test_three_states.py` and the plain-words scan check.

def test_the_grid_does_not_re_sort_while_a_slate_is_in_progress(page):
    """A score arriving must not move the slate under a reader.

    Re-sorting while games are being played shuffles the screen under somebody
    part way down it, and by confidence the finished games would climb over the
    ones still on.
    """
    seen = {"ids": []}

    def _in_progress(route):
        response = route.fetch()
        payload = response.json()
        glance = payload.get("glance") or {}
        glance["state"] = "in_progress"
        payload["glance"] = glance
        seen["ids"] = [c.get("prediction_id") for c in payload.get("cards", [])
                       if c.get("prediction_id")]
        route.fulfill(response=response, json=payload)

    def _one_final_pick(route):
        route.fulfill(json={
            "picks": [{"prediction_id": seen["ids"][0],
                       "tile_state": "final",
                       "verdict": "WIN",
                       "live_line": "TST 7 - TST 3"}] if seen["ids"] else [],
            "games": [],
            "any_live": False,
        })

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/api/week*", _in_progress)
    page.route("**/api/live*", _one_final_pick)
    try:
        _open_week(page, WIDE)
        if not seen["ids"] or not _cards(page):
            pytest.skip("no cards on this slate to tick")
        order_before = page.evaluate(
            """[...document.querySelectorAll('#games-rows .game')]
                 .map(c => c.dataset.game)""")
        page.wait_for_timeout(1400)
        order_after = page.evaluate(
            """[...document.querySelectorAll('#games-rows .game')]
                 .map(c => c.dataset.game)""")
        assert not errors, (
            f"a live tick threw: {errors}. The throw escapes the loop over "
            f"picks, so every pick after this one stops updating and the "
            f"scores freeze with nothing on the page saying so.")
        assert order_before == order_after, (
            "the slate re-sorted while it was being played")
    finally:
        page.unroute("**/api/week*")
        page.unroute("**/api/live*")


def test_the_live_mark_is_never_green(page):
    """Green means a pick won and means interactive. A live game is neither."""
    _open_week(page, WIDE)
    colour = page.evaluate("""() => {
        const probe = document.createElement('span');
        probe.className = 'live-mark';
        document.body.appendChild(probe);
        const c = getComputedStyle(probe).backgroundColor;
        probe.remove();
        const win = getComputedStyle(document.documentElement)
            .getPropertyValue('--win').trim();
        return { c, win };
    }""")
    assert colour["c"] != colour["win"], (
        f"the live mark is drawn in the win colour ({colour['c']})")


def test_the_form_streak_wears_its_ink_and_nothing_more(page):
    """RULED 2026-09-25 (ruling d): the ruling of 2026-09-08 stands. A W in
    the form row wears the win colour and an L the loss colour, as the
    letter's ink; neither is filled, because a filled W is a pick that won."""
    _open_week(page, WIDE)
    palette = page.evaluate("""() => {
        const r = getComputedStyle(document.documentElement);
        const hex = name => r.getPropertyValue(name).trim().toLowerCase();
        const probe = (cls) => {
            const s = document.createElement('span');
            s.className = cls;
            document.body.appendChild(s);
            const c = getComputedStyle(s);
            const out = { color: c.color, bg: c.backgroundColor, shadow: c.boxShadow };
            s.remove();
            return out;
        };
        const rgb = (h) => 'rgb(' + [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)).join(', ') + ')';
        return { win: rgb(hex('--win')), loss: rgb(hex('--loss')),
                 winMark: probe('fmark win'),
                 lossMark: probe('fmark loss') };
    }""")
    assert palette["winMark"]["color"] == palette["win"], "a W in the form row does not wear the win colour"
    assert palette["lossMark"]["color"] == palette["loss"], "an L in the form row does not wear the loss colour"
    for mark in (palette["winMark"], palette["lossMark"]):
        assert mark["bg"] in ("rgba(0, 0, 0, 0)", "transparent"), "a form mark is filled like a verdict"
        assert mark["shadow"] == "none", "a form mark is ringed like a price comparison"


def test_every_class_the_page_asks_for_is_a_class_it_builds():
    """The scan, run against the shipped files (mechanism, not habit)."""
    audit.check_no_dead_selectors()


def test_the_condensed_face_is_where_the_brief_put_it(page):
    """GRIDIRON_BOARD (operator ruling 2026-09-24): Barlow Condensed for
    team names, scores, picks and big numbers; the clean sans for everything
    else. The cards-UI rule of 2026-09-04 -- no condensed face anywhere --
    is replaced by that ruling, and this holds the new line in both
    directions: the loud things are condensed and the prose is not."""
    _open_week(page, WIDE)
    page.evaluate("() => document.fonts.ready")
    faces = page.evaluate("""() => {
        const face = sel => { const e = document.querySelector(sel); return e ? getComputedStyle(e).fontFamily : null; };
        return { name: face('#games-rows .tname'), score: face('#games-rows .tri'),
                 pick: face('#games-rows .pick-line'), prob: face('#games-rows .pick-prob'),
                 count: face('#games-rows .game-count'), strip: face('#day-counts'),
                 body: getComputedStyle(document.body).fontFamily,
                 loaded: [...document.fonts].filter(f => f.family === 'Barlow Condensed' && f.status === 'loaded').length };
    }""")
    for key in ("name", "score", "pick", "prob"):
        assert faces[key] and "Barlow Condensed" in faces[key], (key, faces[key])
    for key in ("count", "strip", "body"):
        assert faces[key] and "Barlow Condensed" not in faces[key], (key, faces[key])
        assert "Manrope" in faces[key], (key, faces[key])
    assert faces["loaded"] >= 1, "no Barlow Condensed face reached `loaded`"
    assert not any(re.search(r"monospace|mono\b", f or "", re.I) for f in faces.values() if isinstance(f, str))


# --- STRONG BY DEFAULT (R5, and GRIDIRON_17 R2) ------------------------------
#
# RETIRED 2026-09-24. Eight tests here read `#week-tier-seg` and
# `#week-counts`: the tier filter THREE_STATES removed on 2026-09-08 and the
# count line the board removed. Since the 8th every one of them had passed by
# skipping ("no STRONG picks on this slate") or by finding nothing to press,
# which is a test of nothing. The default-band rule they guarded has no
# control on the board to hold it to; the close-out of 2026-09-25 lists them
# and the ruling that would bring a tier filter back would bring them back.

def _shown_ids(page):
    """Every card id in the grid, with "show all" opened AND WAITED FOR.

    `show all` does not reveal hidden markup -- its handler sets a flag and
    calls `renderWeek()`, which RE-FETCHES and rebuilds the grid from scratch.
    Reading the DOM straight after the click catches the page mid-render, with
    `host.innerHTML = ''` already run and nothing appended yet.

    THAT RACE MADE FOUR TESTS SKIP RATHER THAN FAIL, which is worse: each one
    said "no cards on this slate" and passed as a skip while the slate had
    six. A helper that reports an empty page as an empty slate turns every
    test built on it into a test of nothing.
    """
    # THE SHOW-ALL CONTROL WENT WITH THE GRID (2026-09-08). This helper used
    # to press it so the assertions below saw the whole slate rather than the
    # shortlist. There is no "rest" to reveal now: the Today groups show what
    # the bar and the floor put in them, and the control is gone.
    # THE HERO'S CARD COUNTS. It is not in the grid -- the grid drops the card
    # the hero leads with -- so a helper that returned only `#week-cards` would
    # report the largest pick on the page as absent from it.
    return set(page.evaluate(
        """(() => [...document.querySelectorAll('#games-rows .game .q')]
                    .map(c => Number(c.dataset.id)))()"""))


def _flag_ids(page, ids):
    """Route `/api/week` so exactly these prediction ids carry a method note."""
    wanted = set(ids)

    def handler(route):
        response = route.fetch()
        payload = response.json()
        # THE TODAY GROUPS ARE THE CARDS (2026-09-08). This injected only into
        # `cards[]`, which the removed grid read; the cards a reader sees are
        # built from `today.clears` and `today.watching`.
        groups = [payload.get("cards") or []]
        today = payload.get("today") or {}
        for name in ("clears", "below_floor", "watching", "live", "settled"):
            groups.append(today.get(name) or [])
        # AND THE BOARD'S OWN ROWS (2026-09-24): the pick on the face and
        # every question behind it.
        for game in (payload.get("board") or {}).get("games") or []:
            groups.append([game["pick"]] if game.get("pick") else [])
            groups.append(game.get("questions") or [])
        for group in groups:
            for card in group:
                if card.get("prediction_id") in wanted:
                    card["method_note"] = _NOTE
        route.fulfill(response=response, json=payload)

    page.route("**/api/week*", handler)


#: THE FLAGGED NOTE, in the words the server sends. Declared here from
#: 2026-09-08: it lived with the three hero tests that were removed with the
#: hero, and one of them was the only thing declaring it.
_NOTE = "chosen from the model's own distribution, not from a market line"


def test_the_flagged_note_is_readable_without_a_tap(page):
    """A caveat behind a tap is a caveat most readers never reach.

    The reader taking the percentage at face value is precisely the one it is
    written for, so the note is asserted VISIBLE AT REST -- unlike the market
    hint beside it, which is deliberately a hover reveal.
    """
    _open_week(page, WIDE)
    ids = _shown_ids(page)
    if not ids:
        pytest.skip("no cards on this slate to flag")

    _flag_ids(page, ids)
    _open_week(page, WIDE)
    _shown_ids(page)
    # ON THE ROW'S FACE, which is what is visible at rest: the pick's note.
    shown = page.evaluate(
        """[...document.querySelectorAll('#games-rows .game')].map(c => {
             const n = c.querySelector('.pick-method');
             return n ? { text: n.textContent.trim(),
                          seen: n.offsetParent !== null &&
                                getComputedStyle(n).opacity !== '0' }
                      : null;
           })""")
    drawn = [s for s in shown if s]
    assert drawn, "every card was flagged and not one drew a note"
    assert all(s["seen"] for s in drawn), (
        "a method note rendered and is not visible at rest, so the caveat is "
        "absent on every glance and on every touch device")
    assert all(s["text"] == _NOTE for s in drawn), (
        "the note on a card is not the sentence the server wrote")


# `test_the_card_the_hero_refuses_is_still_on_the_page` was removed with the
# hero on 2026-09-08. It checked that the grid dropped the card the hero LED
# WITH by identity rather than by position, because `open.slice(1)` deletes a
# card from the page entirely once the hero can refuse the top one. There is
# no hero, no lead and no slice: the grid shows the slate.

def test_manrope_actually_loads_and_is_the_face_the_page_draws_in(page):
    """A file in the repository is not a font on the page.

    Everything else about ruling 4 is checkable without a browser -- the bytes
    hash, the licence is there, the stylesheet names files that exist. NONE OF
    THAT PROVES THE PAGE USES IT. An `@font-face` whose `src` 401s, or whose
    unicode-range excludes the text, fails SILENTLY: the stack falls through to
    the system face and the page looks fine, slightly wrong, forever.

    IT ALREADY FAILED ONCE THIS WAY. `auth.path_is_open` allowed `.css`, `.ico`
    and `.svg` under `/static/` and not `.woff2`, so the sign-in screen drew in
    a fallback face and said nothing but a console line.
    """
    _open_week(page, WIDE)
    page.evaluate("() => document.fonts.ready")
    loaded = page.evaluate(
        """() => [...document.fonts]
             .filter(f => f.family === 'Manrope' && f.status === 'loaded')
             .map(f => f.unicodeRange ? 'range' : 'all')""")
    assert loaded, (
        "no Manrope face reached `loaded`, so the page is drawing in the "
        "fallback stack and the vendored file is decoration")

    # AND IT IS THE FACE ACTUALLY USED, not merely one that downloaded.
    used = page.evaluate(
        """() => {
             const el = document.querySelector('.hero-game, .card-game, body');
             return getComputedStyle(el).fontFamily;
           }""")
    assert "Manrope" in used, f"the page draws in {used!r}"


def test_no_font_request_is_refused(page):
    """The 401 that started §5.4, asserted rather than remembered."""
    refused = []
    page.on("response", lambda r: refused.append((r.status, r.url))
            if ".woff2" in r.url and r.status >= 400 else None)
    _open_week(page, WIDE)
    page.evaluate("() => document.fonts.ready")
    assert not refused, f"font requests were refused: {refused}"


# --- the tier chip says what it is (2026-09-04) -----------------------------

def test_the_badge_says_how_much_stands_behind_it_where_a_reader_can_see_it(page):
    """MEASURED, and this is the fix. Across four live slates 362 of 379 tier
    chips named a band with no settled record behind it, and the sentence
    saying so reached a GRID card only through `title`. THE TIER CHIP WENT
    WITH THE OLD CARD (GRIDIRON_BOARD, 2026-09-24); the record badge is the
    count on every row and tile, and it is on the face, on a phone."""
    _open_week(page, PHONE)
    if not _cards(page):
        pytest.skip("no rows on this slate")

    badges = page.evaluate(
        """[...document.querySelectorAll('#games-rows .game .pick .badge')]
             .map(t => ({ text: t.textContent.trim(),
                          tip: t.dataset.tip || '',
                          seen: t.offsetParent !== null }))""")
    if not badges:
        pytest.skip("no picks on this slate")
    assert all(c["seen"] for c in badges), "a badge rendered and is hidden"
    for badge in badges:
        assert re.fullmatch(r"\d+/\d+", badge["text"]), (
            f"a badge shows something other than settled over the gate: {badge['text']!r}")
        assert "settled" in badge["tip"], "the badge's words do not say what it counts"


def test_the_chip_is_never_composed_in_the_browser(page):
    """The word comes from the server, like every other word on the page.
    The tier chip lives on Results now (the settled table), so that is
    where it is read."""
    from gridiron import language

    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/results'")
    page.wait_for_selector("#history-table tbody tr", timeout=15000)
    texts = page.evaluate(
        """[...document.querySelectorAll('.tier')]
             .map(t => t.textContent.trim()).filter(Boolean)""")
    if not texts:
        pytest.skip("no tier chips on this slate")

    allowed = set()
    for band in ("LEAN", "SOLID", "STRONG"):
        allowed.add(language.tier_chip_label(band, True))
        allowed.add(language.tier_chip_label(band, False))
    unknown = sorted(set(texts) - allowed)
    assert not unknown, (
        f"these chip labels were not composed by language.tier_chip_label: "
        f"{unknown}")
