"""The laws, read from the one place they are written.

RULED 2026-09-09, and the reason is three sentences that had gone stale in
three different files. The footer said "Not a betting tool. No stake sizing,
no bankroll, no recommendations"; the Settings list of the laws said the same;
`meta.not_a_betting_tool` said "It does not size stakes, manage a bankroll, or
recommend a bet". LAW 5 stopped saying any of that on 2026-09-07, and the app
sized every pick and led with a group called "clears the bar" for two days
while three surfaces told the reader otherwise.

**THE LAW TEXT IS NEVER TYPED TWICE.** `CLAUDE.md` is the source; every page
that states a law renders it from here, and a test asserts the rendered
strings appear in that file verbatim. A law cannot be amended without every
page saying so, because there is nothing left to forget to update.

OUTSIDE THE PREDICTION CLOSURE, like `buildinfo` and for the same reason: this
reads a file off disk, which has no business anywhere near the path that
writes a probability.
"""

from __future__ import annotations

import re
from pathlib import Path

#: The working agreement, at the repository root. Not inside the package: it
#: is the document a human edits, and it is read rather than imported.
LAWS_FILENAME = "CLAUDE.md"

#: `**5. THE APP RECOMMENDS, IT NEVER TRANSACTS.**` at the start of a line.
_HEADING = re.compile(r"^\*\*(?P<number>[1-6])\.\s+(?P<title>[^*]+?)\.\*\*",
                      re.M)

#: The four prohibitions under LAW 5, each `  * **NO ORDER PATH.** ...`.
_PROHIBITION = re.compile(r"^\s*\*\s+\*\*(?P<title>NO [A-Z ]+?)\.\*\*", re.M)

#: A paragraph that is only an amendment note -- "(Amended 2026-09-07 by
#: operator ruling, ...)" -- and is not what the law SAYS.
_NOTE = re.compile(r"^\(Amended\b", re.I)


def laws_path(root: Path | None = None) -> Path:
    from . import config
    return (root or config.PACKAGE_ROOT.parent) / LAWS_FILENAME


def _clean(text: str) -> str:
    """One paragraph of markdown as one line of plain words.

    The emphasis marks go, the line breaks go, the backticks go. Nothing else
    is touched: this is the law's own wording and a paraphrase would defeat
    the whole point of reading it from source.
    """
    text = text.replace("**", "").replace("`", "")
    return " ".join(text.split())


def read_laws(root: Path | None = None) -> list[dict]:
    """The six laws: number, title, and the first thing each one says.

    `what` is the first PARAGRAPH of the law's own prose, skipping a leading
    amendment note -- which records that the law changed and is not what it
    says. Returns an empty list when the file is missing rather than raising:
    a working agreement that has been moved is a thing to notice on the page,
    not a reason for the API to stop answering.
    """
    path = laws_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    found = list(_HEADING.finditer(text))
    out: list[dict] = []
    for i, match in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        body = text[match.end():end]
        what = ""
        for paragraph in body.split("\n\n"):
            stripped = paragraph.strip()
            if not stripped or _NOTE.match(stripped):
                continue
            # A BLOCKQUOTE IS A REPLACED LAW, kept for audit and never the
            # thing in force. Skipping it is the difference between quoting
            # this law and quoting the one it replaced.
            if stripped.startswith(">") or stripped.startswith("#"):
                continue
            what = _clean(stripped)
            break
        out.append({
            "number": int(match.group("number")),
            "title": _clean(match.group("title")),
            "what": what,
        })
    return out


def prohibitions(root: Path | None = None) -> list[str]:
    """The four things LAW 5 marks structural and not amendable.

    Read from the law rather than listed here, because a list here is the
    fourth copy of a sentence this module exists to stop copying.
    """
    laws = read_laws(root)
    if not laws:
        return []
    path = laws_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    fifth = _HEADING.search(text, 0)
    starts = [m for m in _HEADING.finditer(text) if m.group("number") == "5"]
    if not starts:
        return []
    start = starts[0].end()
    after = [m for m in _HEADING.finditer(text) if m.start() > start]
    end = after[0].start() if after else len(text)
    block = text[start:end]
    # ONLY THE FORBIDDEN BLOCK. The replaced law is kept beneath this one in a
    # blockquote and carries the same words; taking them all would print the
    # old law's prohibitions beside the current one's.
    marker = block.find("FORBIDDEN structurally and permanently")
    if marker != -1:
        block = block[marker:]
    quote = block.find("\n> ")
    if quote != -1:
        block = block[:quote]
    del fifth
    return [_clean(m.group("title")) for m in _PROHIBITION.finditer(block)]


def footer_note(root: Path | None = None) -> str:
    """The one line every page ends with, in the law's own words.

    LAW 5's title, then the four prohibitions. Nothing invented, nothing
    softened, and nothing that can drift from `CLAUDE.md` without a test
    noticing.
    """
    laws = {law["number"]: law for law in read_laws(root)}
    fifth = laws.get(5)
    if fifth is None:
        return ""
    # CAPITALISATION IS THE ONLY THING NORMALISED. The law shouts its titles;
    # a footer that shouts back is a footer nobody reads. The words are the
    # law's own, and the test that proves it compares case-insensitively for
    # exactly this reason.
    parts = [fifth["title"].rstrip(".").capitalize() + "."]
    forbidden = prohibitions(root)
    if forbidden:
        parts.append(" ".join(t.rstrip(".").capitalize() + "." for t in forbidden))
    return " ".join(parts)
