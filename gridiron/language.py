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

# ---------------------------------------------------------------------------
# THE PLAIN WHY
# ---------------------------------------------------------------------------
#
# What replaced the engineering output on a pick card. It used to read:
#
#     srs_diff = 1.3322 pushes toward the yes side by 1.38 in log-odds;
#     asked_line = -0.5 pushes against the yes side by 0.56 in log-odds; ...
#
# Every term in that sentence is an internal identifier or a unit nobody thinks
# in. The decomposition is not wrong and it has not been deleted -- it moved to
# the Factors page, where somebody auditing the model goes looking for it. What
# a reader wants on a pick is which few things drove it and how hard.
#
# THE WORDS ARE DERIVED FROM THE SAME CONTRIBUTIONS THE ARITHMETIC USES. Order
# is by absolute contribution; direction is the contribution's sign; size is the
# contribution's share of the total movement. Nothing here consults the factor's
# rationale for a direction, and no template asserts one -- a coefficient's sign
# is a measured fact that changes on a refit, and prose that hardcoded it would
# go quietly wrong the way `mlb_batter_rate` went backwards for a day.

#: At most this many factor sentences. Four is what fits in a paragraph a
#: person will actually read; the rest are on the Factors page.
WHY_MAX_SENTENCES = 4

#: How a contribution's share of the total movement becomes words. Bands, not a
#: number: "0.42 of the log-odds" is the thing this replaced.
WHY_SIZE_BANDS = (
    (0.45, "the biggest reason"),
    (0.25, "a good deal"),
    (0.10, "some"),
    (0.00, "a little"),
)


def _size_words(share: float) -> str:
    for floor, words in WHY_SIZE_BANDS:
        if share >= floor:
            return words
    return "a little"


#: The side each market's question was FORMED as. A contribution is signed
#: toward this side, which is not always the side the model took.
WHY_YES_SIDE = {"spread": "cover", "moneyline": "win", "prop": "over"}


def why_is_flipped(item: dict) -> bool:
    """Did the model take the NO side of the question as asked?

    THIS IS THE K1 BUG'S SHAPE, in prose rather than in a verb table. A
    contribution is signed toward the YES side -- "does the home club win" --
    and the model frequently takes the other one. Without this, a pick for
    Colorado renders as "Why Atlanta Braves" with every reason "working against
    it": each sentence individually true about the yes side, and the paragraph
    as a whole describing the opposite of the forecast above it.
    """
    yes = WHY_YES_SIDE.get(item.get("market_type"))
    side = item.get("model_side")
    return bool(yes and side and side != yes)


def why_sentences(item: dict, factors: dict | None = None) -> list[str]:
    """The plain-English reasons for one pick, strongest first.

    `item` is a rendered prediction carrying `contributions` (the same list the
    decomposition uses) and optionally `absent_factors`. `factors` maps a factor
    name to its declared WHY phrase; passed in so this module never imports the
    registry, which would put the factor code inside the humaniser's blast
    radius for no reason.
    """
    contributions = item.get("contributions") or []
    known = factors or {}
    # Directions are relative to THE PICK, not to the question's yes side.
    flip = -1.0 if why_is_flipped(item) else 1.0

    scored = []
    for c in contributions:
        name = c.get("factor")
        value = c.get("contribution")
        if not name or value is None or c.get("missing"):
            continue
        phrase = known.get(name)
        if not phrase:
            # A factor with no declared phrase is SKIPPED rather than rendered
            # as its identifier. A test fails on any such factor, so this is a
            # belt to the test's braces and never the normal path.
            continue
        scored.append((abs(float(value)), float(value) * flip, phrase))

    if not scored:
        return []

    scored.sort(key=lambda t: -t[0])
    total = sum(t[0] for t in scored) or 1.0

    out = []
    for magnitude, value, phrase in scored[:WHY_MAX_SENTENCES]:
        direction = "helps the pick" if value > 0 else "works against it"
        size = _size_words(magnitude / total)
        # "The starting pitching matchup helps the pick — the biggest reason."
        joiner = " — " if size == "the biggest reason" else " "
        out.append(f"{phrase[:1].upper()}{phrase[1:]} {direction}{joiner}{size}.")
    return out


def why_absent(item: dict, factors: dict | None = None) -> str | None:
    """One clause for what could not be measured, or None.

    Absence is a fact about the world and is stated as one. It is deliberately
    ONE sentence however many factors are missing: a reader needs to know the
    model was working partly blind, not to read a list.
    """
    known = factors or {}
    # Accepts either bare names or the card's richer {"factor": ...} rows, so
    # a caller does not have to reshape what it already has.
    raw = item.get("absent_factors") or []
    names = [
        (a.get("factor") if isinstance(a, dict) else a) for a in raw
    ]
    names = [n for n in names if known.get(n)]
    if not names:
        return None
    phrases = [known[n] for n in names[:3]]
    if len(phrases) == 1:
        subject = phrases[0]
    elif len(phrases) == 2:
        subject = f"{phrases[0]} and {phrases[1]}"
    else:
        subject = f"{phrases[0]}, {phrases[1]} and {phrases[2]}"
    more = len(names) - len(phrases)
    tail = f", and {more} other thing{'s' if more > 1 else ''}" if more else ""
    return f"{subject[:1].upper()}{subject[1:]}{tail} could not be measured for this game."


def why_market(item: dict) -> str | None:
    """The closing clause, where a line exists. None where none does.

    Never invents a comparison: a market with no published price gets no
    sentence at all rather than a hedged one.
    """
    implied = item.get("market_implied_prob")
    model = item.get("model_prob")
    if implied is None or model is None:
        return None
    subject = strip_market_suffix(item.get("subject"), item.get("prop_type"))
    if item.get("market_type") in ("moneyline", "spread"):
        subject = team_name(subject, item.get("team_names"))
    lean = "heavier" if model > implied else "lighter"
    return (
        f"The market has {subject} at {round(implied * 100)}%; "
        f"the model weighs the same evidence {lean}."
    )


def why_block(item: dict, factors: dict | None = None) -> dict:
    """Everything the expanded row needs to explain a pick, in words.

    One structure so the card, and anything else that ever shows a reason, read
    from the same place. `heading` names the pick rather than repeating the
    market: "Why Tampa Bay Rays", not "Why moneyline".
    """
    # The heading names WHO the pick is on, not the whole claim: "Why SF", not
    # "Why SF covers -3.5" -- the claim is already on the row above, and
    # repeating it inside its own explanation reads as a stutter.
    #
    # Derived the same way `phrase` derives its subject, including the flip
    # that names the opponent when the model takes the NO side of a moneyline,
    # so the heading and the pick sentence cannot name different teams.
    picked = strip_market_suffix(item.get("subject"), item.get("prop_type"))
    if item.get("market_type") in ("moneyline", "spread"):
        if item.get("market_type") == "moneyline" and item.get("model_side") == "lose"                 and item.get("opponent"):
            picked = item["opponent"]
        picked = team_name(picked, item.get("team_names"))
    sentences = why_sentences(item, factors)
    return {
        "heading": f"Why {picked}" if picked else "Why this pick",
        "sentences": sentences,
        "absent": why_absent(item, factors),
        "market": why_market(item),
        "more_label": "How the model works",
        "more_href": "#/factors",
        "n_factors": len(item.get("contributions") or []),
    }
