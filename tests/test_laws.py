"""A law cannot be amended without every page saying so (ruled 2026-09-09).

THE FAILURE THIS EXISTS FOR, and it ran for two days. LAW 5 became "THE APP
RECOMMENDS, IT NEVER TRANSACTS" on 2026-09-07. Three surfaces went on saying
the law it replaced:

  * the page footer -- "Not a betting tool. No stake sizing, no bankroll, no
    recommendations, and no sportsbook or exchange connection.";
  * the Settings list of the laws, which is the page whose whole purpose is
    telling a reader what the rules are;
  * `meta.not_a_betting_tool` -- "It does not size stakes, manage a bankroll,
    or recommend a bet."

Every clause was false. The app sized every pick, led with a group called
"clears the bar", and read a venue for the price on every card. A disclaimer
that understates what an app does is not a safe error: it is the page telling
a reader not to check the thing it is doing.

So the law text is never typed twice. `CLAUDE.md` is the source and these
tests are the mechanism -- not a convention, a comparison.
"""
from __future__ import annotations

from gridiron import laws, views


def _source() -> str:
    return laws.laws_path().read_text(encoding="utf-8")


def test_every_law_rendered_comes_from_the_source_file():
    """The six titles and the six sentences appear in `CLAUDE.md` verbatim.

    Case-insensitively, because the only thing the renderer normalises is
    capitalisation: the law shouts its titles and a footer that shouts back is
    a footer nobody reads. Every other character is the law's own.
    """
    text = _source().replace("**", "").replace("`", "")
    flat = " ".join(text.split()).lower()
    rendered = views._rulings_in_force()
    assert len(rendered) == 6, f"six laws, and {len(rendered)} were rendered"
    for entry in rendered:
        assert entry["name"].lower() in flat, (
            f"the Settings page shows a law titled {entry['name']!r} that is "
            f"not in CLAUDE.md")
        assert entry["what"], f"{entry['name']} renders with no text"
        assert entry["what"].lower() in flat, (
            f"the Settings page states {entry['name']!r} in words that are not "
            f"the law's: {entry['what'][:80]!r}")


def test_the_footer_states_law_five_and_its_four_prohibitions():
    """The footer is the one line every page ends with, so it is the one most
    worth pinning to the source."""
    note = laws.footer_note()
    assert note, "the footer note is empty"
    flat = " ".join(_source().replace("**", "").split()).lower()
    assert "the app recommends, it never transacts." in note.lower()
    for prohibition in laws.prohibitions():
        assert prohibition.lower() in flat
        assert prohibition.rstrip(".").capitalize() + "." in note, (
            f"{prohibition!r} is in the law and not in the footer")
    assert len(laws.prohibitions()) == 4, (
        "LAW 5 marks four things structural and not amendable; the footer "
        "must name all four")


def test_the_withdrawn_sentence_cannot_come_back():
    """THE EXACT WORDS THAT WERE FALSE, refused by name.

    Not a style rule. These sentences were on the page while the opposite was
    true, and the only reason they survived is that nothing compared them
    against anything.
    """
    note = laws.footer_note().lower()
    rendered = " ".join(e["what"].lower() for e in views._rulings_in_force())
    for stale in ("not a betting tool", "no stake sizing", "no bankroll",
                  "no bet recommendations", "no recommendations"):
        assert stale not in note, f"the footer says {stale!r} again"
        assert stale not in rendered, f"the Settings list says {stale!r} again"


def test_a_missing_working_agreement_is_survivable(tmp_path):
    """A file that has moved is a thing to notice on the page, not a reason
    for the API to stop answering."""
    assert laws.read_laws(tmp_path) == []
    assert laws.prohibitions(tmp_path) == []
    assert laws.footer_note(tmp_path) == ""
