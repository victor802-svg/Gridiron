"""A flagged method says so, and never leads (operator ruling 2, 2026-09-04).

And the binaries that arrived with ruling 4 stay checkable.

WHY THIS FILE EXISTS. A market can be fitted, calibrated, honest about its
sample size and still be asking a question with almost nothing in it: two
totals measured +0.0010 and +0.0016 walk-forward against always-the-base-rate,
and the close-out established why -- the rung is chosen as the ladder point
nearest the model's OWN expectation, so P(over) is one half by construction.
Nothing in the record was wrong. The card was.
"""

from __future__ import annotations

import re

import pytest

from gridiron import audit, config, language


# --- the declaration --------------------------------------------------------

def test_every_total_asked_at_its_own_rung_is_flagged():
    """The four sports that declare a total all choose their own rung."""
    assert audit.flagged_method_faults() == []
    for sport, markets in config.SPORT_MARKETS.items():
        if "total" in markets:
            assert config.flagged_method(sport, "total") == "total_at_own_rung", (
                f"{sport} declares a total and it is not flagged")


def test_the_flag_is_derived_and_not_a_written_row():
    """A sixth sport declaring a total is flagged the day it is declared.

    The failure this rules out was found FOUR TIMES in one session on
    2026-09-04, each time silent: a declaration and a hardcoded copy of it
    drifting apart. A written row here would be the fifth.
    """
    declared = {(s, "total") for s, m in config.SPORT_MARKETS.items()
                if "total" in m}
    assert set(config.FLAGGED_METHODS) == declared


def test_a_rung_fixed_by_the_bout_is_not_flagged():
    """UFC's `rounds` IS a total and is asked at the market's own rung.

    2.5 for a three-rounder, 4.5 for a five: fixed by the bout's scheduled
    length, not chosen from the model's expectation. The construction argument
    does not reach it, and a caveat that reached it would be false.
    """
    assert "rounds" in config.SPORT_TOTAL_MARKETS.get("ufc", ())
    assert config.flagged_method("ufc", "rounds") is None


@pytest.mark.parametrize("sport,market", [
    ("nfl", "spread"), ("nfl", "moneyline"), ("nba", "moneyline"),
    ("mlb", "batter_hits"), ("ufc", "moneyline"), ("ufc", "distance"),
])
def test_nothing_else_carries_a_caveat(sport, market):
    """A flag on a market that earns no flag is a caveat that means nothing."""
    assert config.flagged_method(sport, market) is None


# --- the words --------------------------------------------------------------

def test_the_note_is_the_sentence_the_ruling_asked_for():
    note = language.method_note("total_at_own_rung")
    assert note == (
        "totals asked this way have been a coin flip so far "
        "(NBA +0.001, NFL +0.002 in walk-forward) — shown for the record.")


def test_the_note_carries_its_numbers():
    """LAW 4's habit: a caveat without its measurements is an opinion."""
    note = language.method_note("total_at_own_rung")
    assert "+0.001" in note and "+0.002" in note
    assert "walk-forward" in note


def test_an_unflagged_market_says_nothing():
    assert language.method_note(None) is None


def test_a_flag_with_no_words_raises_rather_than_printing_its_key():
    """The third answer -- printing the identifier -- is the unacceptable one."""
    with pytest.raises(language.NoWordsForThisMarket):
        language.method_note("a_finding_nobody_wrote_words_for")


def test_no_identifier_reaches_the_note():
    """The plain-words law, applied to the newest sentence on the card."""
    for key, note in language.METHOD_NOTES.items():
        assert "_" not in note, f"{key}'s note carries an identifier: {note!r}"
        assert note.endswith(".")


# --- the card ---------------------------------------------------------------

def test_a_totals_card_carries_the_note_and_a_spread_card_does_not():
    """Composed where every other sentence on a card is composed."""
    assert language.method_note(config.flagged_method("nba", "total"))
    assert language.method_note(config.flagged_method("nba", "spread")) is None


def test_the_payload_carries_the_note_on_every_flagged_card():
    """Read off the live record rather than a fixture: whatever the slate
    holds, a flagged card carries the note and an unflagged one does not."""
    from gridiron import db as _db, views as _views

    conn = _db.connect()
    for sport in config.SPORTS:
        payload = _views.week(conn, sport)
        for card in payload.get("cards") or []:
            expected = language.method_note(
                config.flagged_method(sport, card.get("market_type")))
            assert card.get("method_note") == expected, (
                f"{sport}:{card.get('market_type')} card carries "
                f"{card.get('method_note')!r} and should carry {expected!r}")


def test_the_hero_refusal_is_still_in_the_shipped_page():
    """Asserted against `app.js`, because that is where the refusal lives."""
    audit.check_the_hero_refuses_flagged_methods()


def test_the_guard_sees_an_unflagged_total():
    """A scanner that cannot see the thing it scans for is the failure this
    project has shipped three times, each time green."""
    original = dict(config.FLAGGED_METHODS)
    try:
        config.FLAGGED_METHODS.pop(("nfl", "total"))
        assert audit.flagged_method_faults(), (
            "flagged_method_faults misses a declared total asked at its own "
            "rung with no flag on it")
    finally:
        config.FLAGGED_METHODS.clear()
        config.FLAGGED_METHODS.update(original)
    assert audit.flagged_method_faults() == []


def test_the_guard_sees_a_hero_that_stopped_refusing():
    broken = """
      function heroPool(cards) { return cards.slice(); }
      const top = heroPool(cards).slice(0, HERO_STEPS);
      const rest = open.slice(1);
    """
    faults = audit.hero_flag_faults(broken)
    assert len(faults) >= 2, faults


# --- the vendored binaries (operator ruling 4) ------------------------------

def test_the_vendored_fonts_match_their_recorded_provenance():
    audit.check_vendored_fonts()


def test_the_licence_travels_with_the_files():
    """The OFL requires it, and it is also what makes the files checkable
    without leaving the repository."""
    licence = config.PACKAGE_ROOT / "web" / "fonts" / "OFL.txt"
    assert licence.is_file()
    text = licence.read_text(encoding="utf-8")
    assert "SIL Open Font License" in text
    assert "Manrope" in text


def test_the_stylesheet_asks_only_for_files_that_are_here():
    """A `src:` naming a file nobody shipped renders in the fallback face and
    says nothing about it."""
    web = config.PACKAGE_ROOT / "web"
    css = (web / "style.css").read_text(encoding="utf-8")
    asked = re.findall(r"url\('(fonts/[^']+)'\)", css)
    assert asked, "the stylesheet declares no @font-face src at all"
    for rel in asked:
        assert (web / rel).is_file(), f"style.css asks for {rel}, which is not here"


def test_no_font_is_fetched_from_off_this_machine():
    """The whole reason the font was not vendored before was that a CDN link
    would put a network dependency in a local-first app."""
    css = (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")
    for face in re.findall(r"@font-face\s*\{[^}]*\}", css):
        assert "http" not in face, f"a @font-face reaches the network: {face}"


def test_the_variable_axis_covers_every_weight_the_page_asks_for():
    """640 is asked for in two places and no static instance can answer it."""
    css = (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")
    faces = re.findall(r"@font-face\s*\{[^}]*\}", css)
    assert faces, "no @font-face rules at all"
    for face in faces:
        assert "font-weight: 200 800" in face, (
            "a face declares a single weight; the stylesheet asks for 640, "
            "which a static instance rounds to 600 or 700 in silence")
    weights = {int(w) for w in re.findall(r"font-weight:\s*(\d{3})\s*;", css)}
    weights |= {int(w) for w in re.findall(r"font:\s*(\d{3})\s", css)}
    assert weights, "no weights found to check"
    assert all(200 <= w <= 800 for w in weights), (
        f"a weight outside the vendored axis: {sorted(weights)}")


def test_the_offline_shell_names_the_fonts():
    """A worker that caches the stylesheet asking for a font and not the font
    renders the offline app in a fallback face."""
    sw = (config.PACKAGE_ROOT / "web" / "sw.js").read_text(encoding="utf-8")
    for name in ("manrope-latin.woff2", "manrope-latin-ext.woff2"):
        assert name in sw, f"the offline shell does not cache {name}"


def test_the_licence_is_byte_stable_across_a_checkout():
    """REGRESSION, 2026-09-04, found minutes after the guard was written.

    `git stash` round-tripped `OFL.txt` through `core.autocrlf`, added 93 bytes
    of carriage returns, and `check_vendored_fonts` failed exactly as built.
    `.gitattributes` had been drawn one file too narrow -- `*.woff2 binary`
    and nothing about the licence, which is also in the hash table.

    A LICENCE'S BYTES ARE THE LICENCE: a document received under terms,
    recorded by hash and shipped unchanged. Line-ending normalisation is a
    modification, small and silent, and it is the kind that makes a provenance
    table look like it is lying.
    """
    licence = config.PACKAGE_ROOT / "web" / "fonts" / "OFL.txt"
    assert b"\r\n" not in licence.read_bytes(), (
        "OFL.txt has CRLF line endings, so its bytes no longer match the "
        "SHA-256 in SOURCE.md and the gate will fail on the next checkout")

    attrs = (config.PACKAGE_ROOT.parent / ".gitattributes")
    assert attrs.is_file(), "no .gitattributes, so nothing stops the next one"
    text = attrs.read_text(encoding="utf-8")
    assert "*.woff2 binary" in text
    assert "OFL.txt -text" in text, (
        "the licence is hashed by the gate and not declared byte-stable")


def test_a_woff2_is_served_as_a_font():
    """`mimetypes` does not know `.woff2` on a stock CPython install.

    Browsers sniff the `wOF2` magic and render it anyway, which is exactly why
    an octet-stream would never have been noticed. `font/woff2` is the
    registered type (RFC 8081) and a correct Content-Type is not something to
    leave to a sniffer's good manners.
    """
    import mimetypes

    from gridiron import api  # noqa: F401  (registering the type is an import side effect)

    assert mimetypes.guess_type("manrope-latin.woff2")[0] == "font/woff2"


def test_the_login_page_can_fetch_its_font_and_nothing_else_opened():
    """REGRESSION, 2026-09-04. `path_is_open` allowed `.css`, `.ico` and
    `.svg` under `/static/` and not `.woff2`, so every visit to the sign-in
    screen 401'd on the font: the page drew in a fallback face and logged a
    console error, which is how the browser smoke test found it.

    BOTH DIRECTIONS. Widening an auth allowlist is the kind of change that is
    only safe if what it did NOT widen is asserted in the same breath --
    `/static/` also holds `app.js` and `index.html`.
    """
    from gridiron import auth

    assert auth.path_is_open("/static/fonts/manrope-latin.woff2")
    assert auth.path_is_open("/static/fonts/manrope-latin-ext.woff2")
    assert auth.path_is_open("/static/style.css")

    for closed in ("/static/app.js", "/static/index.html",
                   "/static/fonts/OFL.txt", "/static/fonts/SOURCE.md",
                   "/api/week", "/openapi.json"):
        assert not auth.path_is_open(closed), f"{closed} answers without a session"


def test_the_gate_refuses_a_run_with_no_browser_tier():
    """REGRESSION, 2026-09-04, and the trap was mine.

    The browser tests skip themselves when playwright cannot be imported --
    correct for a contributor with no browsers, wrong for the gate. A full run
    made under the system Python rather than the project's `.venv` produced 31
    silent skips, pytest exited 0, and four newly written browser tests had
    never once executed while being reported as passing.

    `summarise` already refuses a run with a skipped tier. This asserts the
    browser tier reaches it, so an ABSENT tier is treated exactly like a
    DECLINED one.
    """
    import importlib.util
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(config.PACKAGE_ROOT).parent / "tools"))
    try:
        import verify
    finally:
        sys.path.pop(0)

    code, lines = verify.summarise({"a": True, "b": True}, skipped=("browser",))
    assert code != 0, "the gate passed a run whose browser tier never ran"
    assert any("INCOMPLETE" in ln for ln in lines), lines

    # And the source of the absence is read, not assumed.
    src = (Path(config.PACKAGE_ROOT).parent / "tools" / "verify.py").read_text(
        encoding="utf-8")
    assert 'find_spec("playwright")' in src, (
        "nothing checks whether the browser tier can run at all, so an "
        "interpreter without playwright passes the gate over half a suite")
    assert importlib.util is not None
