"""The stored form of a subject, and how to say it out loud.

ONE FUNCTION, IN ITS OWN MODULE, for a reason worth writing down.

`strip_market_suffix` lived in `language.py`, which is the right place for it
by subject matter -- it turns a stored identifier into something a person
reads. But `language.py` also composes the market clause, so it NAMES
`market_implied_prob` in code, and LAW 1's import-closure scan rejects any
module on the prediction path that names a market column.

`sports/nba.py` is on the prediction path and needed exactly this one function,
to keep a void reason from reading "FERNANDO TATIS JR. BATTER_HITS". Importing
the humaniser to get it pulled the market-naming module into the NBA prediction
closure, and LAW 1's guard failed the build -- correctly, and within seconds of
the change.

The two obvious ways out were both bad: a second copy of the function in the
sports module, or an allowlist entry excusing the import. A display helper that
names no market data has no reason to live behind a module that does, so it
moved here instead. `language` re-exports it, and every existing caller keeps
working unchanged.

This module imports nothing, and must keep importing nothing.
"""

from __future__ import annotations


def strip_market_suffix(subject: str | None, market: str | None) -> str:
    """"Saquon Barkley rushing_yards" -> "Saquon Barkley".

    Prop subjects are stored with the stat appended, because the subject has to
    be unique per question. That is a storage decision and it has no business
    being read by a person.
    """
    text = (subject or "").strip()
    if market and text.endswith(market):
        text = text[: -len(market)].strip()
    return text


def stat_suffix(subject: str | None, known) -> str | None:
    """Recover a prop's stat from its stored subject, when the column is empty.

    THIRTY-TWO NFL PROP ROWS carry `prop_type = NULL`. They were written at
    05:55 on 2026-08-29, under factor set fs1; the change that started
    recording the column landed at 07:34 the same morning, and every row since
    has it. So this is not a bug in the writing path -- it is history, and LAW 3
    makes it permanent: a prediction is never edited after the fact, and
    backfilling a column would be exactly that.

    The consequence was visible on the Picks page: "Sam Darnold passing_yards
    over 165.5", because `strip_market_suffix` needs to be TOLD what to strip
    and the record no longer knows. The stat is still there -- it is the end of
    the subject -- and the declared market names for the sport say what it can
    legitimately be. Matching against those recovers it for reading without
    touching the row.

    Longest first, so `batter_home_runs` is never mistaken for a shorter name
    that happens to be its tail.
    """
    text = (subject or "").strip()
    for name in sorted((k for k in (known or ()) if k), key=len, reverse=True):
        if text.endswith(name):
            return name
    return None


#: WHICH SIDE OF EACH QUESTION IS THE "YES". Moved here from `language` on
#: 2026-09-02 for the reason this module exists: `gridiron.calls` needs it to
#: know what sides a question has, the resolver imports `calls`, and importing
#: the humaniser to reach one dict would drag a market-naming module into that
#: closure. The scan caught it within seconds of the change, twice in a row --
#: first through `calibration`, then through `language`.
#:
#: `language` re-exports it, so every existing caller is unchanged.
#: THE YES SIDE OF EVERY MARKET'S QUESTION.
#:
#: A market missing from this map has NO yes side, so `is_no_side` returns
#: False for every pick in it and the flip never happens -- which means the
#: card shows the probability of one side and decomposes the other. That is
#: exactly what UFC's two new markets did on the day they were added: 14 cards
#: showed 0.5743 while their own contributions said 0.4257, the exact
#: complement, and the side-arithmetic guard caught all of them by name.
#:
#: So a new market is added HERE at the same time it is added anywhere else.
YES_SIDE = {"spread": "cover", "moneyline": "win", "prop": "over",
            "total": "over", "rounds": "over", "distance": "yes"}
