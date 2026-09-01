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

from . import subjects as _subjects

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


#: WHICH FORM OF A CLUB'S NAME EACH PLACE USES, and the rule lives here so
#: there is one place it lives.
#:
#:   FULL  ("St. Louis Cardinals") for a heading or a row -- a label, where the
#:         whole name identifies the club at a glance.
#:   CITY  ("St. Louis") inside a sentence -- "the market has St. Louis at 48%"
#:         reads the way a person says it; the full name reads like a form
#:         being filled in.
#:
#: Both come from the feed (`displayName` and `location`); neither is composed
#: here, and a club with no row keeps its tricode in both forms.
NAME_FORMS = ("full", "city")


def team_name(code: str | None, names: dict | None, form: str = "full") -> str:
    """A club's name in the requested form, or its tricode when none was fetched.

    The fallback is the point. `names` comes from the `teams` table, which is
    populated from the feed and carries the URL and date it came from; a club
    with no row -- a historical code like OAK or SD that no current team list
    contains -- keeps rendering as a tricode rather than being guessed at. A
    tricode is terse; an invented name is wrong.
    """
    if not code:
        return ""
    entry = (names or {}).get(code)
    if not entry:
        return code
    # Tolerates the older flat {code: "Full Name"} shape as well as the two-form
    # dict, so a caller holding either does not have to know which.
    if isinstance(entry, str):
        return entry
    return entry.get(form) or entry.get("full") or code


#: Re-exported, not redefined. It moved to `subjects.py` so a prediction-path
#: module can use it without importing this one, which names a market column in
#: the clause below and would fail LAW 1's closure scan. See that module.
strip_market_suffix = _subjects.strip_market_suffix


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


#: The side each market's question was FORMED as. A stored probability and a
#: stored contribution are both signed toward this side; the model frequently
#: takes the other one.
YES_SIDE = {"spread": "cover", "moneyline": "win", "prop": "over",
            "total": "over"}


def side_named(item: dict, form: str = "full") -> tuple[str, float | None]:
    """WHO the pick is on, and the probability OF THAT SIDE. The one door.

    `form` chooses how a club is named: "full" for a heading or a row, "city"
    inside a sentence. That rule lives HERE rather than at each call site, for
    the same reason the flip does -- a rule with four copies is a rule with
    four chances to be applied inconsistently.

    THIS EXISTS BECAUSE THE SAME DEFECT HAPPENED THREE TIMES, in three places
    that each reached for `subject` on their own:

      1. the chance label read "97% chance WAS covers" beside a decomposition
         summing against WAS -- 34 cards, because the renderer hardcoded a verb
         per market type (K1);
      2. the Why heading read "Why Atlanta Braves" over a pick for Colorado,
         with every reason "working against it" (K3);
      3. the market clause read "the market has Atlanta Braves at 34%" under
         that same pick -- the number right, the name wrong (R2).

    Each was fixed where it was found. Three instances of one defect is not
    three bugs, it is a missing function: `subject` is the side the QUESTION
    was asked about, and prose wants the side the ANSWER took. They differ
    whenever the model takes the NO side, which on a moneyline is close to half
    the time.

    So every piece of prose naming a team, an answer or a side-probability goes
    through here, and `audit.check_side_named` fails by name on any composer in
    this module that reaches `subject` directly instead.

    Returns the display name and the model's probability for the same side.
    `model_prob` is already confidence in the side taken (`stated_side`
    guarantees it), so the pair is always about one thing.
    """
    market_type = item.get("market_type")
    side = item.get("model_side")
    name = strip_market_suffix(item.get("subject"), item.get("prop_type"))

    if market_type == "total":
        # A TOTALS QUESTION NAMES NO TEAM. Its stored subject is the matchup
        # ("AKR @ WAKE"), which is a pair of tricodes, and putting that through
        # the team-naming path produced "Why AKR @ WAKE" as a heading and "the
        # market has AKR @ WAKE at 71%" in the prose -- raw identifiers in a
        # sentence, and the wrong framing besides: nobody is backing Akron.
        #
        # The side IS the answer here, so that is what gets named.
        return ("the over" if side != "under" else "the under"), item.get("model_prob")

    if market_type in ("moneyline", "spread"):
        # THE FLIP. A moneyline's subject is the home club; taking the NO side
        # is a pick for the visitors, and naming the home club would name the
        # team being forecast AGAINST.
        if market_type == "moneyline" and side == "lose" and item.get("opponent"):
            name = item["opponent"]
        name = team_name(name, item.get("team_names"), form)

    return name, item.get("model_prob")


def is_no_side(item: dict) -> bool:
    """Did the model take the NO side of the question as asked?"""
    yes = YES_SIDE.get(item.get("market_type"))
    side = item.get("model_side")
    return bool(yes and side and side != yes)


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
    # THE ONE DOOR. `side_named` resolves the club-or-player the pick is on,
    # including the flip when the model took the NO side of the question. For a
    # prop it already strips the stored stat suffix -- `market` and `prop_type`
    # are the same string there -- so there is nothing left for this function
    # to do to the name.
    subject, _prob = side_named(item)
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

    if market_type == "total":
        # NOT A TEAM AND NOT A PLAYER. A totals question is about the GAME, so
        # the sentence names neither side: "over 52.5 total points". Routing it
        # through the subject would produce "Ohio State over 52.5", which reads
        # as a claim about one team's scoring and is not the question asked.
        over = "over" if side != "under" else "under"
        return f"{over} {_number(line)} total points"

    if market_type == "moneyline":
        # "ATL to lose" is arithmetic; "COL to win" is what a person says. The
        # subject of an MLB moneyline is always the home club, so the model
        # taking the NO side is a pick for the visitors -- and naming the club
        # we are actually backing is the whole point of the plain-words law.
        # Falls back to the literal form only when the opponent is unknown,
        # because inventing one would be worse than reading oddly.
        # `subject` is already the club being backed, flip included.
        if side == "lose":
            return f"{subject} to win"
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
    market_type = item.get("market_type")
    side = item.get("model_side")
    # THE ONE DOOR, for the game markets. A prop's subject is a person's name
    # and needs only its stored stat suffix removed.
    subject, _prob = side_named(item)
    if market_type == "prop":
        subject = strip_market_suffix(item.get("subject"), item.get("prop_type"))
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

    if market_type == "total":
        # A TOTAL IS NOT A "COVERS" QUESTION, and it read as one: the label
        # under a totals card said "IDST @ USU COVERS", which is the verb from
        # the spread branch applied to a question about the combined score.
        # The same shape as the two defects this function was written to end,
        # arriving through a market type that did not exist when it was.
        #
        # It names no team on purpose -- the question is about the game.
        return f"the game goes {'under' if side == 'under' else 'over'}"

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
        # The TRICODE is deliberate here and not a miss -- see the note above.
        # It still comes from the side taken, not from the question's subject.
        #
        # The fallback matters: with no opponent recorded there is no other
        # club to name, and "TB wins" under a pick AGAINST Tampa would be the
        # very inversion this function exists to prevent. Say "TB loses"
        # instead -- clumsier, and true.
        raw = strip_market_suffix(item.get("subject"), item.get("prop_type"))
        if side == "lose":
            if item.get("opponent"):
                return f"{item['opponent']} wins"
            return f"{raw} loses"
        return f"{raw} wins"

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

#: AT MOST THREE SENTENCES (ruling, 2026-08-31). One reason, one counterweight
#: or second reason, and the market. Four was a paragraph; three is a thought.
WHY_MAX_SENTENCES = 3

#: How a contribution's share of the total movement becomes words. Bands, not a
#: number: "0.42 of the log-odds" is the thing this replaced.
#: THE SIZE IS FOLDED INTO THE LEAD-IN, not appended as a tag. Appending gave
#: "Mostly it comes down to X, and it is the main thing." -- two clauses saying
#: the same thing, the second of which is the sort of phrase only a machine
#: writes. The opening words carry the weight instead.
WHY_LEAD_BANDS = (
    (0.45, "Mostly it comes down to"),
    (0.25, "The biggest single reason is"),
    (0.00, "No one thing decides it; the largest is"),
)

#: How much the second factor matters, as a qualifier on its lead-in.
WHY_SECOND_BANDS = (
    (0.25, ", and not by a little"),
    (0.10, ""),
    (0.00, ", a little"),
)


def _band(bands, share: float) -> str:
    for floor, words in bands:
        if share >= floor:
            return words
    return bands[-1][1]


def _lead(phrase: str, share: float) -> str:
    """The first sentence: what drove it, with its size in the opening words.

    LEAD-IN GRAMMAR RATHER THAN A PREDICATE. The composer used to write
    "{Phrase} helps the pick — the biggest reason", which read as a spreadsheet
    talking: the phrases are long noun clauses, and bolting a verb onto the
    front of one produces "How good the two teams have been, adjusted for who
    they played helps the pick".
    """
    return f"{_band(WHY_LEAD_BANDS, share)} {phrase}."


#: Past this many words, a supporting phrase goes AFTER the verb instead of
#: before it. Read aloud, "how good the two teams have been, adjusted for who
#: they played points the same way" is a garden path: by the time "points"
#: arrives the reader has been inside a subordinate clause for eight words and
#: takes it for a noun. The opposer sentence never had this problem because it
#: already leads with the direction, so the long phrase lands at the end.
WHY_LONG_SUBJECT_WORDS = 6


def _second(phrase: str, helps: bool, share: float) -> str:
    """The second sentence: another reason, or the thing pulling against it."""
    size = _band(WHY_SECOND_BANDS, share)
    if not helps:
        return f"Pulling the other way{size}: {phrase}."
    if len(phrase.split()) > WHY_LONG_SUBJECT_WORDS:
        return f"Pointing the same way{size}: {phrase}."
    return f"{phrase[:1].upper()}{phrase[1:]} points the same way{size}."


#: The side each market's question was FORMED as. A contribution is signed
#: toward this side, which is not always the side the model took.
WHY_YES_SIDE = {"spread": "cover", "moneyline": "win", "prop": "over"}


def why_is_flipped(item: dict) -> bool:
    """Did the model take the NO side of the question as asked?

    THIS IS THE K1 BUG'S SHAPE, in prose rather than in a verb table. A
    contribution is signed toward the YES side -- "does the home club win" --
    and the model frequently takes the other one. Without this, a pick for
    Colorado renders as "Why Atlanta Braves" with every reason working against
    it: each sentence individually true about the yes side, and the paragraph
    as a whole describing the opposite of the forecast above it.
    """
    return is_no_side(item)


def why_sentences(item: dict, factors: dict | None = None) -> list[str]:
    """The plain-English reasons for one pick, at most three sentences.

    ONE: the biggest reason. TWO: the second reason, OR the strongest thing
    pulling the other way when that is larger than the second supporter --
    because a reader who is only told what agrees with the pick is being sold
    to. THREE: the market, and only where a line exists.

    `item` carries `contributions` (the same list the decomposition uses);
    `factors` maps a factor name to its declared WHY phrase, passed in so this
    module never imports the registry.
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

    magnitude, value, phrase = scored[0]
    out = [_lead(phrase, magnitude / total)]

    rest = scored[1:]
    if rest:
        supporters = [t for t in rest if t[1] > 0]
        opposers = [t for t in rest if t[1] < 0]
        # The strongest OPPOSER wins the slot when it is larger than the next
        # supporter: a reader told only what agrees with the pick is being sold
        # to rather than informed.
        pick = rest[0]
        if opposers and (not supporters or opposers[0][0] > supporters[0][0]):
            pick = opposers[0]
        elif supporters:
            pick = supporters[0]
        out.append(_second(pick[2], pick[1] > 0, pick[0] / total))

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
    # A CLAUSE, not a sentence (ruling). It attaches to the reasons rather than
    # competing with them: what the model could not see is context for the
    # three sentences above, not a fourth reason.
    return f"({subject}{tail} couldn't be measured for this game.)"


def why_market(item: dict) -> str | None:
    """The closing clause, where a line exists. None where none does.

    Never invents a comparison: a market with no published price gets no
    sentence at all rather than a hedged one.
    """
    implied = item.get("market_implied_prob")
    model = item.get("model_prob")
    if implied is None or model is None:
        return None
    # NAME THE SIDE THE MODEL TOOK. `implied` is already the market's
    # probability for THAT side, so naming the subject instead produced "the
    # market has Atlanta Braves at 34%" under a pick for Colorado -- the K1
    # defect once more, in the one sentence that quotes a number back to the
    # reader. Same flip the heading uses, so the two cannot name different
    # clubs.
    # PROSE takes the city form: "the market has St. Louis at 48%" is what a
    # person says. The heading above it uses the full name, and both come from
    # the same door.
    subject, _prob = side_named(item, form="city")
    lean = ("leans harder on its own reading" if model > implied
            else "is the more cautious of the two")
    return f"The market has {subject} at {round(implied * 100)}%; the model {lean}."


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
    picked, _prob = side_named(item)
    sentences = why_sentences(item, factors)
    # THE MARKET IS SENTENCE THREE, where a line exists. Where none does it is
    # omitted rather than replaced by a hedge: the budget is a ceiling, not a
    # quota to fill.
    market = why_market(item)
    if market and len(sentences) < WHY_MAX_SENTENCES:
        sentences = sentences + [market]
    return {
        "heading": f"Why {picked}" if picked else "Why this pick",
        "sentences": sentences,
        "absent": why_absent(item, factors),
        "market": why_market(item),
        "more_label": "How the model works",
        "more_href": "#/factors",
        "n_factors": len(item.get("contributions") or []),
    }

#: WHAT EACH SCHEDULED TASK IS CALLED, in words. "predict:mlb" is an internal
#: identifier that happens to be readable, which is the most dangerous kind: it
#: LOOKS like English and is a colon-joined key. A reader should not have to
#: know the code to read the panel that says whether the machine is alive.
TASK_WORDS = {
    "predict:cfb": "Predict college football",
    "recalibrate": "Re-check the claims",
    "refresh": "Fetch results",
    "resolve": "Settle picks",
    "predict:nfl": "Predict football",
    "predict:mlb": "Predict baseball",
    "predict:nba": "Predict basketball",
    "catch-up": "Catch up after a sleep",
}


#: How many reasons a change line names before it counts the rest. TWO, by
#: ruling on 2026-08-31: the line is a summary and the full list lives on the
#: page under it, so naming three or four made it an inventory that a reader
#: skips without gaining anything the list below does not already give.
CHANGE_NAMES_SHOWN = 2


def _names_then_count(phrases: list[str], *, rest_word: str = "more") -> str:
    """"a and b" -- or "a, b and 18 smaller changes" once the list runs on.

    A list of twenty-three noun phrases is not a sentence, it is an inventory,
    and a reader skips it. The count is not a truncation of the fact: the full
    list is rendered directly beneath this line.

    `rest_word` is how the remainder is described, and it is NOT cosmetic.
    "smaller changes" is a claim about size and may only be used when the two
    named ones were actually ranked by a measured effect; otherwise the
    remainder is "more", which claims nothing.
    """
    shown = [p for p in phrases[:CHANGE_NAMES_SHOWN] if p]
    rest = len(phrases) - len(shown)
    if not shown:
        return ""
    if rest > 0:
        return ", ".join(shown) + f" and {rest} {rest_word}"
    if len(shown) == 1:
        return shown[0]
    return ", ".join(shown[:-1]) + " and " + shown[-1]


def set_change_line(changes: dict, *, first: bool = False,
                    sport_label: str | None = None,
                    ranked_by: str = "declaration") -> str:
    """One line on WHAT changed in a factor set, in words.

    The page names each set by the date it began, which answers "when" and
    leaves "what" to whoever remembers. This is the answer, composed from what
    `registry.set_changes` read out of the registry -- so the sentence cannot
    say a factor joined that the registry does not carry.

    `ranked_by` IS A HONESTY SWITCH, not a formatting option. The ruling asks
    for "the two most consequential" changes, and consequence is a measured
    quantity: this project has one, the factor's effect on the record. Where
    the sample behind that effect is too thin to order by -- which is every
    sport today, at 2 to 25 settled -- the two named are simply the first two
    DECLARED, and the sentence must not imply otherwise. So "the two that moved
    the answer most" and "and 18 smaller changes" are said only under
    `ranked_by="effect"`; otherwise it is a plain list and a plain count.

    THREE SENTENCES THIS GOT WRONG on the first reading, all of them by
    treating a real distinction as a missing one:

      * "Added playing at home; retired playing at home" -- a factor declared
        and retired the same day, listed twice, reading as a contradiction. It
        now has its own clause, because being measured and dropped inside a day
        is the most informative thing that can happen to a factor.
      * "The opening set, with nothing recorded about what it declared" for
        baseball, which was not being forecast under that set AT ALL. That is
        an absence, and the explicit-absent rule applies to prose as much as to
        a feature vector: it must not read as a records gap.
      * "Began with 7 more reasons" about a sport's FIRST seven.
    """
    def phrases(key):
        return [c.get("phrase") for c in (changes.get(key) or []) if c.get("phrase")]

    joined = phrases("joined")
    left = phrases("left")
    both = phrases("tried_and_dropped")
    later = phrases("joined_after_it_began")

    if not changes.get("in_force"):
        who = sport_label or "This sport"
        return f"{who} was not being forecast under this set."

    by_effect = ranked_by == "effect"
    rest = "smaller changes" if by_effect else "more"

    def named(items):
        return _names_then_count(items, rest_word=rest)

    # THE SPORT'S OWN FIRST SET, which is not always the first set overall:
    # baseball and basketball both begin at the second one. Nothing "changed"
    # when a sport declared its opening position.
    first = first or not changes.get("in_force_before")

    parts = []
    if first:
        n = len(joined) + len(both)
        opening = joined or both
        lead = ("Where the model started: "
                f"{n} {_reasons(n)} declared at once, ")
        lead += (f"the two that moved the answer most being {named(opening)}"
                 if by_effect else named(opening))
        parts.append(lead)
        if later:
            # Not padding. A factor added after the set opened is scored from
            # ITS date, not the set's (LAW 2), so it has a shorter record than
            # the set's age implies, and the page should not let that pass.
            parts.append(f"{len(later)} of them joined after the set opened, so "
                         f"their record is shorter than its date suggests")
    elif joined:
        began = len(joined) - len(later)
        if later and began > 0:
            parts.append(f"Began with {began} more -- {named(joined[:began])} "
                         f"-- then {len(later)} {_reasons(len(later))} joined "
                         f"later, {named(later)}")
        elif later:
            parts.append(f"{len(later)} {_reasons(len(later))} joined after it "
                         f"began: {named(later)}")
        else:
            parts.append(f"Added {named(joined)}")

    if both:
        parts.append(f"{named(both)} {_was(len(both))} declared and "
                     f"withdrawn the same day, once measured")
    if left:
        parts.append(f"retired {named(left)}")
    elif joined and not both:
        # Said out loud because the absence is the informative half: a set that
        # only ever adds is a set nobody has pruned.
        parts.append("nothing retired")

    if not parts:
        return "Nothing was added or retired while this set was in force."
    return "; ".join(parts) + "."


def _was(n: int) -> str:
    return "was" if n == 1 else "were"


def _reasons(n: int) -> str:
    return "reason" if n == 1 else "reasons"


#: Why the second forecaster was not asked, in words. The stored reason is a
#: code -- `llm_unavailable:api_error` -- and it reached the Schedule page
#: verbatim, inside a sentence that was otherwise plain English.
#:
#: Each of these is a DIFFERENT situation with a different response, which is
#: the argument for saying them rather than printing one code for all of them:
#: a missing key is a setup step, a budget stop is working as designed, and an
#: API error is the only one that might be worth retrying.
DEGRADED_WORDS = {
    "no_api_key": "no key is configured for the second forecaster",
    "sdk_missing": "the second forecaster's library is not installed",
    "daily_budget": "the day's spending cap was reached",
    "api_error": "the second forecaster could not be reached",
    "unparseable": "the second forecaster answered in a form we could not read",
    "out_of_range": "the second forecaster returned something that was not a probability",
    "no_reasoning": "the second forecaster gave a number with no reasoning",
}


def degraded_words(reason: str | None) -> str:
    """"llm_unavailable:api_error" -> "the second forecaster could not be reached".

    An unknown code is passed through rather than swallowed: a reason nobody
    has written words for is still more useful on the page than silence, and
    seeing it there is what prompts writing them.
    """
    code = (reason or "").strip()
    if code.startswith("llm_unavailable:"):
        code = code.split(":", 1)[1]
    return DEGRADED_WORDS.get(code, code)


#: What a non-live database is called on the banner. `backtest` is the only
#: other kind today, and "BACKTEST DATABASE" is what it must say -- not the
#: stored key uppercased in the browser, which is how it was said before.
DATABASE_LABELS = {
    "backtest": "BACKTEST DATABASE",
    "sample": "SAMPLE DATABASE",
}


def database_label(kind: str | None) -> str | None:
    """The banner's label, or None for a live database, which needs no banner.

    An unrecognised kind still gets a banner -- it is a warning, and a warning
    suppressed because nobody wrote words for it is the worst of both.
    """
    if not kind or kind == "live":
        return None
    return DATABASE_LABELS.get(kind) or f"{kind.upper()} DATABASE"


def colophon(meta: dict) -> str:
    """The footer line: what this record actually contains, in one sentence.

    Composed HERE because it is five sentences of prose about data, and it was
    built in the renderer -- "Current factor set since " + a sliced timestamp,
    a count glued to " predictions on record", a spend formatted with
    `toFixed`. Every one of those is a decision about how a number reads, made
    in the one place the plain-words tests cannot see and the humaniser's rules
    do not apply.
    """
    bits = []
    started = meta.get("factor_set_started")
    bits.append(f"Current factor set since {started[:10]}" if started
                else "Current factor set")
    bits.append(f"{meta.get('predictions', 0):,} predictions on record")

    seasons = meta.get("seasons_loaded") or []
    span = f" ({seasons[0]}-{seasons[-1]})" if len(seasons) >= 2 else ""
    bits.append(f"{meta.get('games_final', 0):,} completed games loaded{span}")

    cover = meta.get("market_coverage") or {}
    bits.append(f"market comparison for {cover.get('with_market_line', 0):,}"
                f" of {cover.get('n', 0):,}")

    ledger = meta.get("llm_ledger") or {}
    bits.append(f"LLM spend today ${float(ledger.get('usd_spent') or 0):.4f}"
                f" of ${float(ledger.get('usd_cap') or 0):.2f}")
    return " · ".join(bits)


def earned_number_line(raw: float | None, shown: float | None,
                       settled: int | None, version: int | None) -> str | None:
    """What the model claimed, what it is shown as, and why they differ.

    None when nothing was corrected -- which is every card today. A card in a
    raw category must look exactly as it did before corrections existed, or
    the reader is being told something changed when nothing did.

    THE RAW CLAIM IS NEVER HIDDEN. It is the model's actual output and the
    thing the record is keeping score of; the corrected figure is what the
    claims like it have been worth. Showing one without the other would make
    the correction unfalsifiable to a reader.
    """
    if raw is None or shown is None or version is None:
        return None
    if abs(raw - shown) < 0.005:
        return None
    n = f"{settled:,}" if settled else "its"
    return (f"The model's raw claim was {raw:.0%}; it is shown as {shown:.0%}, "
            f"which is what claims like this have been worth over {n} settled "
            f"predictions.")


def corrections_note(active: bool, min_train: int, version: int | None = None,
                     fitted: str | None = None,
                     settled: int | None = None) -> str:
    """The one line the Record tab shows about corrections.

    Two states, and they must not read alike: numbers shown exactly as the
    model made them, or numbers adjusted by the record with the version and
    the sample that did the adjusting.
    """
    if not active:
        # TWO STAGES, SAID AS TWO. A correction is fitted and inspectable at
        # `min_train`; it is APPLIED only once it beats the rows it was not
        # fitted on, which needs a forty-row holdout and so about two hundred
        # settled. Saying "corrections begin at 50" was true of the fit and
        # false of the number on the card, and the measurement behind the
        # holdout floor is in `correction.HOLDOUT_MIN`.
        return (f"Claims are shown exactly as the model made them. A "
                f"correction is fitted at {min_train} settled predictions and "
                f"applied only once it beats the rows it was not fitted on.")
    when = f", fitted {fitted[:10]}" if fitted else ""
    n = f", {settled:,} settled" if settled else ""
    return (f"Shown numbers are earned: claims are adjusted by the record "
            f"(version {version}{when}{n}).")


#: The two-word label under a tile's percentage. It answers "per cent of
#: WHAT", which a bare number does not.
TILE_LABELS = {
    "spread": ("covers", "misses"),
    "moneyline": ("wins", "loses"),
    "total": ("over", "under"),
    "prop": ("over", "under"),
}


def tile_label(item: dict) -> str:
    """What the tile's percentage is a percentage OF, in one or two words.

    Composed here rather than in the renderer, per the 2026-08-31 ruling. It is
    the same question `chance_clause` answers at length, said short enough to
    sit under a number in a 124px tile -- and derived from the same side, so
    the two cannot disagree.
    """
    yes, no = TILE_LABELS.get(item.get("market_type") or "", ("over", "under"))
    return no if is_no_side(item) else yes


def tile_line(item: dict) -> str:
    """The pick in its shortest honest form, for a tile.

    "Alabama -30.5", "Under 55.5 total", "Tulsa to win". The full sentence
    lives on the card and in the rail; this is the version that fits three
    across without truncating, which the frame forbids.

    THE SIDE IS RESOLVED BY `side_named` LIKE EVERYTHING ELSE. A short form is
    exactly where the wrong-side defect would reappear -- there is less room
    for the reader to notice it.
    """
    market_type = item.get("market_type")
    line = item.get("line_asked")
    subject, _prob = side_named(item, form="city")

    if market_type == "total":
        word = "Under" if is_no_side(item) else "Over"
        return f"{word} {_number(line)} total"

    if market_type == "moneyline":
        return f"{subject} to win"

    if market_type == "spread":
        if line is None:
            return subject
        # THE NUMBER IS NOT FLIPPED, and the first version of this flipped it.
        # `side_named` does not swap the club on a spread the way it does on a
        # moneyline, so negating the line produced "Alabama +30.5" for a pick
        # AGAINST Alabama -- which reads as Alabama receiving the points, the
        # inversion in miniature and in the one place a reader has least room
        # to notice it.
        #
        # The rung is the question, so it is printed as asked; the LABEL
        # underneath carries the side ("covers" / "misses"), and the two are
        # derived from the same `is_no_side`.
        return f"{subject} {float(line):+.1f}"

    # A prop: the person, the side, the number, the stat.
    market = item.get("prop_type") or item.get("market")
    if line is not None and float(line) == 0.5:
        said = half_unit_phrase(subject, market, item.get("model_side"))
        if said:
            return said
    word = SIDE_WORDS.get(item.get("model_side"), "over")
    return f"{subject} {word} {_number(line)} {humanise(market)}".strip()


def task_name(task: str | None) -> str:
    """"predict:mlb" -> "Predict baseball". Falls back to opened-out words."""
    if not task:
        return ""
    if task in TASK_WORDS:
        return TASK_WORDS[task]
    # A task added later and forgotten still must not render as a key.
    head, _, tail = str(task).partition(":")
    words = head.replace("_", " ").replace("-", " ").strip().capitalize()
    return f"{words} {tail}".strip() if tail else words
