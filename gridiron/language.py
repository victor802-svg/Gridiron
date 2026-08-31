"""Turning the record into words a person would say out loud.

THE PLAIN-WORDS LAW lives here. No internal identifier reaches the interface:
not `rushing_yards`, not a column named after a database field, not a bare
em-dash standing in for an absence. Every phrase this module returns is one a
reader could say aloud without decoding anything.

It is server-side and single-implementation on purpose. The same sentence has
to appear on a pick card, in the history table and in the digest, and three
copies of the humanising rules would drift into three different vocabularies —
which is how the history page ended up with two columns both called "Market".

The scan in `gridiron.audit` checks rendered pages for snake_case and known
internal terms, and a planting puts `rushing_yards` in a label to prove it
fires. This module is what makes passing that scan possible rather than a
matter of remembering.
"""

from __future__ import annotations

#: What each market is CALLED. Anything absent falls back to the name with its
#: underscores opened out, so nothing can render as snake_case even for a
#: market added later and forgotten.
#:
#: These are NAMES, for a label or a dropdown: "point spread", "moneyline".
#: They are NOT the verb a sentence uses - that is SIDE_WORDS. Conflating the
#: two put the word "covers" in a dropdown labelled Market, which is not a
#: thing a market is called.
MARKET_WORDS = {
    # football
    "spread": "point spread",
    "passing_yards": "passing yards",
    "receiving_yards": "receiving yards",
    "rushing_yards": "rushing yards",
    "receptions": "receptions",
    "passing_tds": "passing touchdowns",
    # baseball
    "moneyline": "moneyline",
    "batter_hits": "hits",
    "batter_total_bases": "total bases",
    "batter_home_runs": "home runs",
    "pitcher_strikeouts": "strikeouts",
    # basketball
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "threes": "three-pointers",
}

#: What the two sides of each question are called in speech.
SIDE_WORDS = {
    "cover": "covers",
    "not_cover": "does not cover",
    "over": "over",
    "under": "under",
    "win": "to win",
    "lose": "to lose",
}

#: A settled prediction's verdict, in the card language.
RESULT_WORDS = {
    None: "PENDING",
    1: "WIN",
    0: "LOSS",
}


def humanise(name: str | None) -> str:
    """`rushing_yards` -> "rushing yards". The floor under everything here."""
    if not name:
        return ""
    return MARKET_WORDS.get(name, str(name).replace("_", " "))


def team_name(code: str | None, names: dict | None) -> str:
    """A club's display name if one was FETCHED, otherwise its tricode.

    The fallback is the point. `names` comes from the `teams` table, which is
    populated from the feed and carries the URL and date it came from; a club
    with no row -- a historical code like OAK or SD that no current team list
    contains -- keeps rendering as a tricode rather than being guessed at. A
    tricode is terse; an invented name is wrong.
    """
    if not code:
        return ""
    return (names or {}).get(code) or code


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


#: A counting-stat prop asked at half a unit is a yes/no question about whether
#: the thing happened at all, and English has words for that. "under 0.5 home
#: runs" is arithmetic; "no home run" is what a person says.
#:
#: This matters most where the market lives below an even chance. An over-0.5
#: home-run prop sits around 15-35%, so the model states the NO side almost
#: every time, and rendering that as "under 0.5 home runs" buries the actual
#: claim inside a comparison the reader has to run themselves.
HALF_UNIT_WORDS = {
    "batter_hits": ("a hit", "hits"),
    "batter_total_bases": ("a total base", "total bases"),
    "batter_home_runs": ("a home run", "home runs"),
    "pitcher_strikeouts": ("a strikeout", "strikeouts"),
    "receptions": ("a reception", "receptions"),
    "passing_tds": ("a passing touchdown", "passing touchdowns"),
    "points": ("a point", "points"),
    "rebounds": ("a rebound", "rebounds"),
    "assists": ("an assist", "assists"),
    "threes": ("a three-pointer", "three-pointers"),
}


def half_unit_phrase(subject: str, market: str, side: str) -> str | None:
    """"Kyle Schwarber - NO home run", or None if this is not that shape."""
    words = HALF_UNIT_WORDS.get(market)
    if not words:
        return None
    singular = words[0]
    if side == "over":
        return f"{subject} records {singular}".strip()
    if side == "under":
        return f"{subject} - NO {singular.split(' ', 1)[-1]}".strip()
    return None


def phrase(item: dict) -> str:
    """One readable sentence for a prediction, whatever kind it is.

        "Saquon Barkley over 95.5 rushing yards"
        "PHI covers -3.5"
        "ATL to win"

    The market never appears twice: if the sentence already names it, the
    caller does not add a column for it. That duplication is exactly what the
    history table used to do.
    """
    market = item.get("prop_type") or item.get("market") or item.get("market_type")
    market_type = item.get("market_type")
    subject = strip_market_suffix(item.get("subject"), market)
    # A game market's subject is a club, so it gets the club's name when one
    # has been fetched. A prop's subject is a person and is already a name.
    if market_type in ("moneyline", "spread"):
        subject = team_name(subject, item.get("team_names"))
    side = item.get("model_side")
    line = item.get("line_asked")

    if market_type == "prop" or (market and market in MARKET_WORDS
                                 and market not in ("spread", "moneyline")):
        # A half-unit question is a yes/no question, and gets said that way.
        if line is not None and float(line) == 0.5:
            said = half_unit_phrase(subject, market, side)
            if said:
                return said
        side_word = SIDE_WORDS.get(side, side or "over")
        line_text = _number(line)
        return f"{subject} {side_word} {line_text} {humanise(market)}".strip()

    if market_type == "moneyline":
        # "ATL to lose" is arithmetic; "COL to win" is what a person says. The
        # subject of an MLB moneyline is always the home club, so the model
        # taking the NO side is a pick for the visitors -- and naming the club
        # we are actually backing is the whole point of the plain-words law.
        # Falls back to the literal form only when the opponent is unknown,
        # because inventing one would be worse than reading oddly.
        opponent = team_name(item.get("opponent"), item.get("team_names"))
        if side == "lose" and opponent:
            return f"{opponent} to win"
        return f"{subject} {SIDE_WORDS.get(side, 'to win')}".strip()

    # spreads
    side_word = SIDE_WORDS.get(side, "covers")
    return f"{subject} {side_word} {_signed(line)}".strip()


def chance_clause(item: dict) -> str:
    """What the confidence figure is a chance OF. "WAS does not cover".

    THIS EXISTS BECAUSE THE RENDERER KEPT GETTING IT WRONG, twice, in the same
    shape. `app.js` built this sentence itself and hardcoded a verb per market
    type: every prop read "goes over" whichever side the model took, and after
    that was fixed in M4, every SPREAD still read "covers" whichever side the
    model took. 34 spread cards in the record -- 20 NBA, 14 NFL -- stated the
    opposite of the forecast beside them, at high confidence, with a correct
    decomposition underneath contradicting the headline.

    Fixing the second branch in the renderer would have left the third. The
    words come from here now, and the renderer has no verb table to be wrong
    with: it prints what the server sends.

    Note what was NOT wrong, because it matters for where to look next time:
    the arithmetic. Across all 190 predictions in the record, in every sport
    and market, `model_prob` equals the logistic of the displayed contributions
    for the displayed side, to within rounding. `stated_side` was right, the
    decomposition's yes-side was right, and only the sentence lied.
    """
    subject = strip_market_suffix(item.get("subject"), item.get("prop_type"))
    market_type = item.get("market_type")
    side = item.get("model_side")
    # THE TRICODE STAYS HERE, deliberately, and the mockup agrees: the pick line
    # reads "Tampa Bay Rays to win" and this small label reads "TB WINS".
    #
    # Two reasons. It sits under a large number in a narrow column, where a
    # full name wraps or truncates. And a club name is plural -- "Colorado
    # Rockies wins" is wrong, "Colorado Rockies win" is right, and "Miami Heat
    # win" is right for a name that looks singular. Getting that agreement
    # right needs a table of which names take which verb, which is a hundred
    # and twenty judgements typed from memory: the exact thing the teams table
    # exists to avoid. The tricode takes the singular verb and always has.

    if market_type == "prop":
        market = item.get("prop_type") or item.get("market")
        line = item.get("line_asked")
        # A half-unit prop is a yes/no question and reads as one.
        if line is not None and float(line) == 0.5:
            said = half_unit_phrase(subject, market, side)
            if said:
                return said
        return f"{subject} goes {'under' if side == 'under' else 'over'}"

    if market_type == "moneyline":
        # Same flip as `phrase`: name the club the model is actually backing.
        # If these two framed the pick differently -- "COL to win" over "ATL
        # loses" -- a reader would have to hold both in their head to see they
        # agree, which is the work the plain-words law exists to remove.
        opponent = item.get("opponent")
        if side == "lose" and opponent:
            return f"{opponent} wins"
        return f"{subject} {'loses' if side == 'lose' else 'wins'}"

    # spreads
    return f"{subject} {'does not cover' if side == 'not_cover' else 'covers'}"


def result_word(item: dict) -> str:
    """PENDING / WIN / LOSS / VOID. "open" is not a word anybody says."""
    if item.get("voided"):
        return "VOID"
    return RESULT_WORDS.get(item.get("outcome"), "PENDING")


def market_label(item: dict) -> str:
    """What to call this market in a filter or a heading."""
    return humanise(item.get("prop_type") or item.get("market")
                    or item.get("market_type"))


#: What to say instead of a dash. A dash means nothing to a reader and looks
#: like an error; each of these says WHY the cell is empty.
ABSENT_WORDS = {
    "market_line": "no line",
    "market_prob": "no line",
    "outcome": "not played",
    "resolved": "not played",
    "generic": "not recorded",
}


def absent(kind: str = "generic") -> str:
    return ABSENT_WORDS.get(kind, ABSENT_WORDS["generic"])


def _number(value) -> str:
    if value is None:
        return ""
    text = f"{float(value):.10g}"
    return text


def _signed(value) -> str:
    if value is None:
        return ""
    return f"{float(value):+.10g}"
