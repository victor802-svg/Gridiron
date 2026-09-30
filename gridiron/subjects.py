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
#:
#: READ OFF `SIDES` FROM 2026-09-30, below: the yes spelling of each market is
#: the one `SIDES` places on the yes side, so this map and the one place
#: cannot come to disagree. It was a literal of its own until then.


# ---------------------------------------------------------------------------
# THE ONE PLACE A STORED SIDE IS PLACED (the operator's ruling of 2026-09-30)
# ---------------------------------------------------------------------------
#
# "Read 'fail to cover' as the no side in the one place the side is worked
# out; the page and the check refuse any side they can't place instead of
# passing it." (docs/briefs/2026-09-30-rulings.md)
#
# WHAT HAPPENED. College football stores the no side of a spread as
# "fail to cover"; every other sport stores "not_cover". The words knew both
# (`language.SIDE_WORDS`, since the nine cards of 2026-09-01) and placed any
# spelling that was not the yes one on the no side. The numbers did not:
# `priced.shape.blind_probability` listed "cover" and "not_cover" and had no
# rule for "fail to cover", so it could not say which side the question takes
# (`question_takes_the_proposition` None), and every page builder turned the
# claim's numbers round only on `is False`. So recommendation 111 read "North
# Texas -6.5 · 24% · 48¢" -- the other side's chance and price, under the
# words of the side the record holds -- where its own numbers are about 76%
# and about 51.5¢. Two places were deciding the side, each by its own rule,
# and they disagreed on one spelling.
#
# SO THE SIDE IS PLACED HERE AND NOWHERE ELSE. Every spelling the record holds
# (measured 2026-09-30 on the live record: spread cover / not_cover /
# "fail to cover", moneyline win / lose, total, prop and rounds over / under,
# distance yes / no) and every one a sport declares on its questions, each on
# its side. The numbers (`priced.shape.blind_probability`), the words
# (`language.is_no_side`) and the resolvers all ask `side_taken`. A spelling
# that is not here is REFUSED BY NAME (`UnplaceableSide`), never defaulted:
# the two defaults this replaces pointed opposite ways -- the words and the
# game resolvers read an unknown spelling as the no side, the fight resolver
# read it as the yes side -- and a default is how "fail to cover" came to be
# read as no side at all. A new spelling is added here, with a dated line,
# or it fails at the first card and in the gate
# (`audit.check_every_side_is_placed`) rather than shipping a number.
#
# In this module, which imports nothing, because the resolvers and the sport
# modules are on the prediction path and `gridiron.priced` may not be (LAW 1:
# `audit.check_prediction_closure` refuses it in a blind closure).

#: EVERY STORED SPELLING OF EVERY SIDE, per market, and which side of that
#: market's question it is. The record is append-only (LAW 3): 93 college
#: spreads say "fail to cover" and will say it for ever, so the table meets
#: them where they are.
SIDES: dict[str, dict[str, str]] = {
    "spread": {"cover": "yes", "not_cover": "no",
               # college football's spelling of the no side (2026-09-30)
               "fail to cover": "no"},
    "moneyline": {"win": "yes", "lose": "no"},
    "total": {"over": "yes", "under": "no"},
    "prop": {"over": "yes", "under": "no"},
    "rounds": {"over": "yes", "under": "no"},
    "distance": {"yes": "yes", "no": "no"},
}


class UnplaceableSide(ValueError):
    """A stored side the one place cannot place (the ruling of 2026-09-30).

    Raised by name and never guessed: a page builder that meets one refuses
    to paint a number rather than paint the other side's, and the gate's
    check fails on one."""


def side_taken(market_type: str | None, side: str | None) -> str:
    """"yes" or "no": which side of its market's question a stored side is.

    THE ONE PLACE (2026-09-30). Raises `UnplaceableSide`, naming the market
    and the spelling, for a market with no declared sides or a spelling the
    market does not declare.
    """
    sides = SIDES.get(market_type)
    if sides is None:
        raise UnplaceableSide(
            f"THE SIDE CANNOT BE PLACED: {market_type!r} is not a market whose "
            f"sides are declared in subjects.SIDES, so which side of its "
            f"question {side!r} is cannot be said, and nothing is shown for it "
            f"(the ruling of 2026-09-30)")
    taken = sides.get(side)
    if taken is None:
        raise UnplaceableSide(
            f"THE SIDE CANNOT BE PLACED: the stored side {side!r} is not a "
            f"spelling subjects.SIDES declares for a {market_type} question "
            f"({sorted(sides)}), so which side it is cannot be said, and no "
            f"number is shown for it rather than the other side's (the ruling "
            f"of 2026-09-30). Add the spelling to subjects.SIDES with a dated "
            f"line; never a default.")
    return taken


def takes_the_yes_side(market_type: str | None, side: str | None) -> bool:
    """Is this stored side the yes side of its market's question? Through
    `side_taken`, so a side it cannot place raises rather than answers."""
    return side_taken(market_type, side) == "yes"


YES_SIDE = {market: next(spelling for spelling, which in sides.items()
                         if which == "yes")
            for market, sides in SIDES.items()}
