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

import re as _re

from . import config as _config
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
    # COLLEGE FOOTBALL STORES THIS SIDE AS "fail to cover", not "not_cover",
    # and for three days that one missing key put the opposite of the forecast
    # on nine live cards. `SIDE_WORDS.get(side, "covers")` fell through to its
    # default, so a prediction that Nebraska would FAIL to cover rendered as
    # "Nebraska Cornhuskers covers -24.5" -- the fourth appearance of the
    # wrong-side defect, and the first to get past `side_named`, because the
    # name was right and the VERB was wrong.
    #
    # Both strings are kept. The record is append-only (LAW 3): nine rows say
    # "fail to cover" and will say it forever, so the words have to meet them
    # where they are rather than the record being tidied to suit the table.
    "fail to cover": "does not cover",
    "over": "over",
    "under": "under",
    "win": "to win",
    "lose": "to lose",
}


def side_word_or_side(side: str | None) -> str:
    """The verb, falling back to the SIDE'S OWN NAME rather than another's.

    The distinction that matters: an unrecognised side printed as itself reads
    oddly and is TRUE. An unrecognised side printed as another side's verb
    reads perfectly and is FALSE. Where a sentence must be produced no matter
    what, this is the honest degradation; where it need not, `side_word`
    raises instead.
    """
    try:
        return side_word(side)
    except UnknownSide:
        return side or ""


class UnknownSide(KeyError):
    """A stored side this module has no words for. Raised, never defaulted."""


def side_word(side: str | None) -> str:
    """The verb for a stored side, or a loud failure.

    THE DEFAULT WAS THE BUG. `SIDE_WORDS.get(side, "covers")` turns a side
    nobody has written words for into a confident claim about the opposite
    one, and it does it silently, on the card, at high confidence. A sport
    added later with a new label string inherits the defect automatically --
    which is exactly how college football got it.

    Raising means a new sport fails at the first card rather than shipping a
    lie, and the failure names the string it did not recognise.
    """
    word = SIDE_WORDS.get(side)
    if word is None:
        raise UnknownSide(
            f"no words for the stored side {side!r}. Add it to SIDE_WORDS -- "
            f"do NOT let it fall through to another side's verb, which is how "
            f"nine college spreads came to state the opposite of themselves."
        )
    return word

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


def surname(name: str | None) -> str:
    """"Salahdine Parnasse" -> "Parnasse". How a fight is billed.

    A suffix travels with the surname: "Fernando Tatis Jr." is "Tatis Jr.",
    not "Jr.". Returns the whole string when there is nothing to trim, so a
    single-word name is left alone rather than emptied.
    """
    parts = (name or "").split()
    if not parts:
        return ""
    if len(parts) > 2 and parts[-1].rstrip(".").lower() in (
            "jr", "sr", "ii", "iii", "iv"):
        return " ".join(parts[-2:])
    return parts[-1]


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
#: Re-exported, not redefined -- it moved to `subjects.py` so the prediction
#: path can reach it without importing this module, which names market columns.
YES_SIDE = _subjects.YES_SIDE


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
        # The side IS the answer here, so that is what gets named -- placed by
        # the one place (2026-09-30), never by "anything but under".
        return ("the under" if is_no_side(item) else "the over"), item.get("model_prob")

    if market_type in ("moneyline", "spread"):
        # THE FLIP, ON BOTH MARKETS NOW (ruling E1). A game market's subject is
        # the home club; taking the NO side is a pick for the visitors, and
        # naming the home club would name the team being forecast AGAINST.
        #
        # The spread used to be excluded, and the reasoning was that the RUNG
        # is the question so it should print as asked. That is true of the
        # record and false of the reader: a tile reading "Alabama -24.5 ...
        # 76% MISSES" makes a person work out that the pick is East Carolina
        # receiving the points, every time, on every tile. The pick is
        # "ECU +24.5", so that is what it says -- the same claim, at the same
        # probability, in the words somebody would use.
        #
        # THE NUMBER MUST FLIP WITH THE NAME. Flipping one without the other
        # is how an earlier attempt produced "Alabama +30.5" for a pick
        # AGAINST Alabama. `tile_line` and `phrase` negate the line exactly
        # when this function swapped the club, and both ask `is_no_side` to
        # decide, so they cannot disagree about which happened.
        if side_flips(item):
            name = item["opponent"]
        name = team_name(name, item.get("team_names"), form)

    return name, item.get("model_prob")


def is_no_side(item: dict) -> bool:
    """Did the model take the NO side of the question as asked?

    THROUGH THE ONE PLACE (the operator's ruling of 2026-09-30). This read
    "any spelling but the yes one is the no side" while the numbers
    (`priced.shape.blind_probability`) listed spellings of their own: two
    rules for one fact, and on college football's "fail to cover" the words
    named North Texas while the numbers were Tulsa's. Both ask
    `subjects.side_taken` now. A spelling it does not know raises
    `subjects.UnplaceableSide` by name, so the card is refused rather than
    worded on a guessed side. A question with no stored side, or of a market
    with no declared sides, is said as it was asked, as before.

    AN EMPTY SPELLING IS A STORED SIDE, NOT A MISSING ONE (the prover,
    2026-09-30). This read `not side`, so a forecast stored with the side ''
    was said as asked -- the yes side's words -- and an unpriced card drew
    the model's own number under them: "over 44.5 total points · 62%" for a
    side nobody can place, on a spread, a total and a prop alike (measured on
    a scratch world; a priced one was refused by the numbers). `model_side`
    is NOT NULL on the record, so only a question with no side at all (None)
    is said as asked; '' goes to the one place, which refuses it by name.
    """
    market_type = item.get("market_type")
    side = item.get("model_side")
    if side is None or market_type not in _subjects.SIDES:
        return False
    return _subjects.side_taken(market_type, side) == "no"


def side_flips(item: dict) -> bool:
    """Is this pick RESTATED as the other side, or said as it was asked?

    THE ONE DOOR FOR THE FLIP ITSELF, which is a different question from
    `is_no_side` and had been answered in three places with two different
    answers.

    Taking the NO side is not enough. Restating "Las Vegas does not cover -7.5"
    as "Miami covers +7.5" needs SOMEBODY TO NAME, and a card whose opponent
    was never recorded has nobody. `side_named` knew that and gated its flip on
    the opponent; `flipped_line` did not, and negated the number anyway. On a
    card with no opponent that produced "WAS covers +3.5" -- the original
    subject, the flipped line, and a verb belonging to neither.

    Every card in the live record carries an opponent, so the two never
    disagreed in production. They disagreed on exactly the inputs a test writes
    by hand, which is the worst place for a rule to differ: the fixtures that
    are supposed to pin the behaviour were pinning a case the code never meets.
    """
    return is_no_side(item) and bool(item.get("opponent"))


def club_named(item: dict) -> str | None:
    """The code of the club a game pick's WORDS name, or None when they name
    no club (a total, a fight's rounds or distance, a prop -- whose club is
    its player's, which the stats tables say).

    THE SAME FLIP AS THE WORDS (pick-number finding 6, 2026-09-30). My day
    chose a taken pick's club by the question's subject, which is the home
    club on a game question, so a taken "not_cover" on PHI -3.5 was the chip
    "PHI · DAL +3.5" and a taken "lose" moneyline "PHI · DAL to win": the
    club the model forecast AGAINST beside the words of the side it took.
    The club named is the one `side_named` names, decided by `side_flips`,
    so the chip's club and its words cannot come apart.
    """
    if item.get("market_type") not in ("moneyline", "spread"):
        return None
    return item.get("opponent") if side_flips(item) else item.get("subject")


def spread_verb(item: dict) -> str:
    """"covers" or "does not cover", decided ONCE.

    Written out as a function rather than as an expression in two places
    because the two places are `phrase` and `chance_clause`, they sit four
    screens apart, and a card on which they disagree is the defect this module
    has now produced twice. The second time, one of them had the condition
    right and the other had it half right, and the half was invisible until a
    layout put the two sentences beside each other.

    The verb is positive when the sentence is about the side being BACKED --
    either the model took the YES side, or it took the NO side and there was an
    opponent to restate the pick as. It is negative only when the question
    stands as asked and the answer is no.
    """
    return "covers" if (not is_no_side(item) or side_flips(item))         else "does not cover"


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
    # THE SCHOOL FORM IN PROSE (ruling E1). "Temple Owls covers -14.5" puts a
    # mascot in the middle of a sentence; "Temple covers +14.5" is what a
    # person says. Headings may still carry the full name -- that is where a
    # club's whole name belongs.
    subject, _prob = side_named(item, form="city")
    side = item.get("model_side")
    line = item.get("line_asked")

    if market_type == "prop" or (market and market in MARKET_WORDS
                                 and market not in ("spread", "moneyline")):
        # THE SIDE IS PLACED BY THE ONE PLACE BEFORE IT IS WORDED (the
        # prover, 2026-09-30). This branch never asked `is_no_side`: it
        # printed a spelling it had no word for as itself, so the OTHER
        # forecaster's prop on an open row -- the one card built from
        # `phrase` alone -- stored as "Over" or "" was drawn "Some Player
        # Over 55.5 receiving yards · 62%", a number on a side nobody can
        # place (measured on a scratch world, live and finished; the page's
        # own forecaster's card was refused by its other composers). Asked
        # here, an unknown spelling is refused by name, as on every other
        # market; the words below are unchanged for every declared one.
        is_no_side(item)
        # A half-unit question is a yes/no question, and gets said that way.
        if line is not None and float(line) == 0.5:
            said = half_unit_phrase(subject, market, side)
            if said:
                return said
        # STRICT. A prop side with no word is a defect, not a formatting
        # choice, and defaulting to "over" is what shipped the opposite of
        # nine forecasts on the spread.
        word = side_word_or_side(side)
        line_text = _number(line)
        return f"{subject} {word} {line_text} {humanise(market)}".strip()

    # A FIGHT IS NOT A GAME, and neither of its markets is a spread.
    #
    # "Dan Hooker vs Salahdine Parnasse covers +4.5" is what the shared spread
    # path produced, and it is wrong twice: nobody covers anything in a fight,
    # and the number is a count of rounds rather than points.
    # EACH SIDE BELOW IS PLACED BY THE ONE PLACE (`is_no_side`, through
    # `subjects.side_taken`; the ruling of 2026-09-30), never by "anything
    # but under" or a list of no-side spellings of its own.
    if market_type == "rounds":
        over = "Under" if is_no_side(item) else "Over"
        rung = _number(line)
        unit = "round" if str(rung) in ("0.5", "1", "1.5") else "rounds"
        return f"{over} {rung} {unit}"

    if market_type == "distance":
        # THE QUESTION IS ABOUT THE BOUT, not about a fighter, so the sentence
        # names neither -- the same reasoning the totals branch below follows.
        return ("Does not go the distance" if is_no_side(item)
                else "Goes the distance")

    if market_type == "total":
        # NOT A TEAM AND NOT A PLAYER. A totals question is about the GAME, so
        # the sentence names neither side: "over 52.5 total points". Routing it
        # through the subject would produce "Ohio State over 52.5", which reads
        # as a claim about one team's scoring and is not the question asked.
        over = "under" if is_no_side(item) else "over"
        # WHAT THIS SPORT COUNTS. Hardcoded to "total points" until 2026-09-08,
        # when the operator read "under 12.5 total points" on a baseball card.
        # `SPORT_MARKET_WORDS` has held ("mlb", "total") -> "total runs" since
        # the filter chips were written; the sentence never asked it.
        unit = SPORT_MARKET_WORDS.get((item.get("sport"), "total"), "total points")
        return f"{over} {_number(line)} {unit}"

    if market_type == "moneyline":
        # "ATL to lose" is arithmetic; "COL to win" is what a person says. The
        # subject of an MLB moneyline is always the home club, so the model
        # taking the NO side is a pick for the visitors -- and naming the club
        # we are actually backing is the whole point of the plain-words law.
        # Falls back to the literal form only when the opponent is unknown,
        # because inventing one would be worse than reading oddly.
        # `subject` is already the club being backed, flip included.
        # THE FALLBACK THE NOTE ABOVE PROMISED (the sweep of pick-number step
        # C, 2026-09-30). This asked `is_no_side`, so a "lose" with no
        # opponent recorded -- no club to move the pick to, `subject` still
        # the question's own -- read "PHI to win" for a pick AGAINST PHI, the
        # words and `chance_clause` ("PHI loses") naming opposite sides. It
        # asks `side_flips`, the one door for the flip, and a no side that did
        # not flip is said as asked: "PHI to lose". Every card on the record
        # carries an opponent, so nothing drawn moves.
        if side_flips(item):
            return f"{subject} to win"
        return f"{subject} {side_word(side)}".strip()

    # SPREADS. The subject and the number flip together, decided once by
    # `side_flips`, so the verb is the positive one whenever the sentence is
    # about the side being backed -- and the negative one when there was no
    # opponent to move the pick to and the question stands as asked.
    return f"{subject} {spread_verb(item)} "           f"{_signed(flipped_line(item))}".strip()


def phrase_of_the_other_side(item: dict) -> str:
    """The question's OTHER side, in the words `phrase` would give it:
    "Detroit covers -1.5" for a pick stated "Washington covers +1.5",
    "Dallas to win" for "Philadelphia to win", "over 8.5 total runs" for
    "under 8.5 total runs".

    FOR A RECOMMENDATION THAT BUYS THE SIDE THE MODEL DID NOT TAKE
    (pick-number finding 4, 2026-09-30). The price can make the other side
    of a question the one worth buying -- recommendations 47 and 82 bought
    Detroit -1.5 and New York -1.5 on questions the model answered
    "Washington covers +1.5" and "Tampa Bay covers +1.5" -- and the line that
    states a recommendation said "the other side" after the question's words
    rather than naming it. The side is swapped through the one place
    (`subjects.other_side_spelling`), and the words come from `phrase`, so a
    side it cannot place is refused by name as it is everywhere else.
    """
    return phrase(the_other_side(item))


def the_other_side(item: dict) -> dict:
    """The question on `item` on its OTHER side -- the same game, market,
    subject and line, the side swapped through the one place
    (`subjects.other_side_spelling`) -- so every composer here (`phrase`,
    `tile_line`, `pick_line_words`, `club_named`) words the contract a
    recommendation buys when it is not the side the model took.

    OPERATOR QUESTION 37, RULED 2026-10-05 ("headline the contract the
    recommendation buys; the model's own side named beside it"). The page
    headlined the model's side -- "Atlanta +2.5 · 32% · 48c · $15" -- beside
    the size, the edge and the outline of the contract the recommendation
    buys, New Orleans -2.5. A side it cannot place is refused by name, as
    everywhere else."""
    other = _subjects.other_side_spelling(item.get("market_type"), item.get("model_side"))
    out = dict(item, model_side=other)
    # THE STORED SENTENCE IS THE MODEL'S SIDE'S, never the other side's: a
    # composer that read it would word the side the model took.
    out.pop("phrase", None)
    out.pop("row_title", None)
    return out


def own_side_words(words: str, probability: float | None, *,
                   clause: bool = False) -> str:
    """The model's own side and its number, said beside a pick that headlines
    the OTHER side -- the contract the recommendation buys (operator question
    37, ruled 2026-10-05: "headline the contract the recommendation buys; the
    model's own side named beside it").

    "The model's own side: Washington +1.5, 58%" on the row and the tile;
    `clause` gives the lower-case form for the end of a sentence ("... the
    model's own side: Washington covers +1.5, 58%"). The number is the
    model's for that side at the same contract's line, so the two sides of
    one contract read as one hundred."""
    start = "the model's own side" if clause else "The model's own side"
    if probability is None:
        return f"{start}: {words}"
    return f"{start}: {words}, {round(float(probability) * 100)}%"


def own_side_reasons_words(own_side: str) -> str:
    """The words' tooltip, beside a pick headlining the contract bought on
    the other side of the model's (operator question 37, 2026-10-05): the
    reasons after it are the model's for its own side, and it says so."""
    return (f"This buys the other side of the model's own. {own_side}. "
            f"The reasons that follow are the model's, for its own side.")


class LineNotNamed(ValueError):
    """A number on a pick whose line its words cannot name -- refused, never
    drawn under the words of another line (pick-number step A, 2026-09-30)."""


def at_the_contract(item: dict, line, *, home: str | None) -> dict:
    """The question on `item` asked again at `line` -- the line of the venue
    contract its numbers belong to, from the claim's fixed proposition's
    view (the home side's line on a spread, the over's on a total) -- on the
    same side, so every composer here (`phrase`, `tile_line`,
    `phrase_of_the_other_side`, `club_named`) words that contract.

    PICK-NUMBER STEP A (2026-09-30; findings 2 and 5). A claim is read at the
    venue's line, which is often not the question's: rec 111 asked "North
    Texas -6.5" and was priced off "Tulsa by more than 1.5", so its 76% and
    51.5c are North Texas +1.5's -- and the row read "North Texas -6.5 ·
    76% · 51.5c". A number is shown under the words of the exact contract it
    belongs to, its line and its side (the reading recorded in
    docs/REPAIR_STATE.md): this moves the words to the numbers, never the
    numbers to the words. `views._the_contract` is the one door that decides
    which line; this only says it.

    A spread's line is the SUBJECT's: the home side's line where the subject
    is the home club, its negation where the subject is the visitor (the
    visitor covering -L is the home side not covering L). A subject that is
    neither club cannot be placed at the line and is refused by name
    (`LineNotNamed`). A market with no line -- a moneyline, a fight's
    distance -- or no line to move to is said as asked."""
    market_type = item.get("market_type")
    if line is None or market_type not in ("spread", "total", "prop"):
        return item
    if market_type == "spread":
        if home and item.get("subject") == home:
            own = float(line)
        elif home and item.get("opponent") == home:
            own = -float(line)
        else:
            raise LineNotNamed(
                f"THE PAGE REFUSES A NUMBER WHOSE LINE IT CANNOT NAME: question "
                f"{item.get('prediction_id')} ({item.get('phrase') or item.get('subject')!r}) "
                f"carries numbers read at the home side's {float(line):+g}, and "
                f"its subject {item.get('subject')!r} is not placed against the "
                f"home club {home!r}, so no words can name that line "
                f"(pick-number step A, 2026-09-30)")
    else:
        own = float(line)
    asked = item.get("line_asked")
    if asked is not None and abs(float(asked) - own) < 1e-9:
        return item
    return dict(item, line_asked=own)


#: WHY A ROW PRICED ACROSS TWO CONTRACTS SHOWS NO PRICE (pick-number step A,
#: 2026-09-30; operator question 36 (ii) and (iii) not ruled, the
#: conservative default in docs/REPAIR_STATE.md): its stored model number is
#: about one venue contract and its price about another, so no price, payout,
#: edge or size is drawn for it -- only the model's own number for the
#: question as asked, and this sentence.
ACROSS_TWO_CONTRACTS_WORDS = ("Priced across two contracts before 30 September; "
                              "no single contract carries these numbers.")


def across_two_contracts_words() -> str:
    """The one plain sentence a row priced across two contracts carries."""
    return ACROSS_TWO_CONTRACTS_WORDS


def across_two_contracts_price_words() -> str:
    """What such a row says where its price would be: short, and true."""
    return "no single contract"


def across_two_contracts_pays_words() -> str:
    """What such a row's payout chip says: that no payout is shown -- never
    left empty, which a tile draws as "not recorded", false of a price the
    venue listed and the record kept (step A's prover, 2026-09-30). The
    sentence beneath it and the chip's tooltip say why."""
    return "not shown"


def across_two_contracts_tip() -> str:
    """The longer reason, for the tooltip on that short slot."""
    return ("Before 30 September the venue's contracts naming the visiting side "
            "were read at the wrong sign, so this row's stored chance is about "
            "one contract and its price about another. Neither is shown and "
            "nothing is sized on them; the chance here is the model's own for "
            "the question as asked.")


def asked_elsewhere_words(question_words: str, probability: float | None) -> str:
    """What the model was asked, beside a pick named at the venue's line.

    "The model was asked about North Texas -6.5 and gives it 63%." The pick
    beside it names the venue's contract at another line -- the one its
    numbers, its price and its size belong to (pick-number step A,
    2026-09-30) -- and this says, in plain words, what the forecast itself
    was about, so the two are never read as one line."""
    if probability is None:
        return f"The model was asked about {question_words}."
    return (f"The model was asked about {question_words} and gives it "
            f"{round(float(probability) * 100)}%.")


def as_the_model_was_asked(question_words: str, sentence: str) -> str:
    """One of the forecast's own sentences, said beside a pick named at the
    venue's line: it names the question it is about first.

    "For North Texas -6.5, as the model was asked: The model says 63%. The
    market implies 36% -- 27 points apart." FOUND BY STEP A'S PROVER
    (2026-09-30): where a card's words moved to the contract its numbers
    belong to (`views._the_contract`), the card still carried the forecast's
    own numbers line bare -- "The model says 63%" beside "North Texas covers
    +1.5", whose chance is 76% -- North Texas -6.5's numbers under North Texas
    +1.5's words. The sentence is the forecast's, unchanged; this says which
    question it is about."""
    return f"For {question_words}, as the model was asked: {sentence}"


def why_heading_as_asked(question_words: str) -> str:
    """The why block's heading beside a pick named at the venue's line: the
    reasons, and the market's number among them ("The market has North Texas
    at 36%"), are the forecast's question's, so the heading names it at its
    own line -- "Why North Texas -6.5, as the model was asked" -- where it
    said "Why North Texas" over a card reading "North Texas covers +1.5"
    (step A's prover, 2026-09-30)."""
    return f"Why {question_words}, as the model was asked"


class NoWordsForThisMarket(ValueError):
    """A market reached the prose layer without declaring how to say it."""


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
    # THE SCHOOL FORM, which settles the argument the note below was having
    # with itself. That note defends the tricode on two grounds: a full name
    # wraps in a narrow column, and a club name is PLURAL, so "Colorado
    # Rockies wins" is wrong while "TB wins" is right.
    #
    # The school form answers both without the tricode. "Ohio covers", "East
    # Carolina covers", "Toledo wins" -- singular, short, and a name rather
    # than a code. The spread branch was using the FULL form and producing
    # "OHIO BOBCATS COVERS", which is the exact plural disagreement the note
    # warns about, while the moneyline branch beside it said "TOL WINS": one
    # team, two notations, on adjacent rows of the same slate (seen in the
    # 390px render, E3).
    subject, _prob = side_named(item, form="city")
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
        # placed by the one place (2026-09-30), never "anything but under"
        return f"the game goes {'under' if is_no_side(item) else 'over'}"

    if market_type == "prop":
        market = item.get("prop_type") or item.get("market")
        line = item.get("line_asked")
        # A half-unit prop is a yes/no question and reads as one.
        if line is not None and float(line) == 0.5:
            said = half_unit_phrase(subject, market, side)
            if said:
                return said
        return f"{subject} goes {'under' if is_no_side(item) else 'over'}"

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
        raw = team_name(strip_market_suffix(item.get("subject"),
                                            item.get("prop_type")),
                        item.get("team_names"), "city")
        if is_no_side(item):
            if item.get("opponent"):
                # THROUGH THE NAME LOOKUP, like every other club here. Left
                # raw, this printed "TOL wins" beside "Tulsa wins" on the same
                # slate -- one notation for the side that was flipped and
                # another for the side that was not, which is the reader doing
                # the work of noticing they are the same kind of thing.
                return (f"{team_name(item['opponent'], item.get('team_names'), 'city')}"
                        f" wins")
            return f"{raw} loses"
        return f"{raw} wins"

    # THE FIGHT MARKETS (2026-09-03). Found by rendering a UFC card at 390px:
    # an "Over 2.5 rounds" question read "Nathaniel Wood vs Pavel Andrusca
    # covers". A bout does not cover, and the subject of a rounds question is
    # the whole matchup, so the spread fallthrough produced both errors at
    # once.
    #
    # THIS IS THE FOURTH TIME THIS FUNCTION HAS BEEN WRONG IN THE SAME SHAPE,
    # and the docstring above predicted it: props read "goes over" whichever
    # side was taken, then spreads read "covers" whichever side was taken, and
    # now two new markets fell through to the spread verb because nothing
    # forces a new market to claim its own words. The subject is never named
    # here -- "the fight" is what a reader would say, and it sidesteps the
    # plural problem the spread branch spent a session on.
    if market_type == "rounds":
        return f"the fight goes {'under' if is_no_side(item) else 'over'}"
    if market_type == "distance":
        return ("the fight goes the distance" if not is_no_side(item)
                else "the fight ends early")

    if market_type == "spread":
        # THE SUBJECT IS ALREADY THE SIDE BEING BACKED, so the verb is always
        # the positive one -- exactly as `phrase` does it, four screens up.
        #
        # THIS WAS A DOUBLE FLIP AND IT WAS LIVE ON 68 OF 321 CARDS. `side_named`
        # flips the name when the model takes the NO side: a card stored on LV
        # at -7.5 whose model_side is `not_cover` resolves to "Miami", because
        # backing Las Vegas not to cover -7.5 IS backing Miami +7.5. This
        # function then negated the VERB as well, so the card read "Miami does
        # not cover" beside a pick line reading "Miami covers +7.5" -- two
        # sentences, one card, opposite claims.
        #
        # HOW IT SURVIVED THE GUARDS. Both fixes were right on their own and
        # neither knew about the other: the subject flip arrived when the
        # moneyline started naming the club actually being backed, and the verb
        # negation arrived when the renderer's hardcoded verb table put "WAS
        # covers" on 34 cards that said the opposite. The docstring above
        # records the second and could not know it had made the first
        # redundant. ONE DOOR FOR THE SIDE means one place decides it, and the
        # name is that place.
        #
        # Found by rendering the new hero, which puts the pick sentence and the
        # chance clause four lines apart in large type. The old tile put them at
        # opposite corners.
        #
        # AND ONLY WHERE THE NAME ACTUALLY MOVED. With no opponent recorded
        # there is nobody to restate the pick as, so the sentence says what was
        # asked and answers it in the negative -- which is `side_flips`, the
        # same door `side_named` and `flipped_line` now use.
        return f"{subject} {spread_verb(item)}"

    # A MARKET THAT HAS NOT CLAIMED ITS WORDS GETS NONE (2026-09-03).
    #
    # For most of this function's life the last line WAS the spread branch, so
    # every market nobody had thought about inherited "covers" -- which is how
    # a UFC rounds question came to read "Nathaniel Wood vs Pavel Andrusca
    # covers", and how props read "goes over" whichever side was taken before
    # that, and spreads read "covers" whichever side was taken before that.
    # Three of the same mistake, each fixed by adding a branch, none of them
    # fixed by removing the reason a fourth was possible.
    #
    # It is a fifth market's turn to be added at some point. It will fail
    # LOUDLY here rather than quietly wearing a verb from a market it has
    # nothing to do with, and `audit.check_every_side_has_words` in the gate is
    # where that failure will land.
    raise NoWordsForThisMarket(
        f"{market_type!r} has no declared words in language.chance_clause, so "
        f"there is no true sentence to put on the card. A new market claims "
        f"its own words here; it does not inherit the spread's.")


#: WHAT A VOIDED FORECAST IS CALLED ON THE PAGE (operator ruling 1,
#: 2026-09-24): "the page shows them as withdrawn in those words, never
#: deleted." One word for every void, whatever voided it -- a forecast
#: published from a fit that then failed its holdout, or a question that was
#: never answered -- because a reader who meets two words for one state
#: assumes two states. It said VOID until this date.
WITHDRAWN_WORD = "WITHDRAWN"


def result_word(item: dict) -> str:
    """PENDING / WIN / LOSS / WITHDRAWN. "open" is not a word anybody says."""
    if item.get("voided"):
        return WITHDRAWN_WORD
    return RESULT_WORDS.get(item.get("outcome"), "PENDING")


def withdrawn_words(reason: str | None) -> str | None:
    """The reason beside the word, so a withdrawn row says why on its face.

    A hover is not an answer on a phone, and "withdrawn" alone invites the
    worst guess about what happened. None for a row that is not withdrawn.
    """
    if not reason:
        return None
    return f"withdrawn: {plain_reason(reason)}"


#: A game's key as the resolver wrote it into a reason: `mlb_824785`, or the
#: football form `2025_08_DAL_SEA`. The row it sits beside already names the
#: game in words.
_GAME_KEY = _re.compile(
    r"\b(?:(?:nfl|mlb|nba|cfb|ufc)_\d+|\d{4}_\d{2}_[A-Z]{2,4}_[A-Z]{2,4})\b")
_CODE_WORD = _re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def plain_reason(reason: str) -> str:
    """A stored void reason in plain words, AT RENDER TIME, NEVER BY REWRITING.

    MEASURED 2026-09-24, the day the reason moved out of a hover and onto the
    page: 6 of the 38 distinct reasons in the live record carry an identifier
    -- a game key (`mlb_824785 finished level`) or a market's code name
    (`Tua Tagovailoa passing_yards has no box score`). A void is append-only,
    so the row keeps what the resolver wrote and the reader is shown "the game
    finished level" and "passing yards", the same door `humanise_reasoning`
    is for a forecaster's prose.
    """
    text = _GAME_KEY.sub("the game", reason.strip())
    return _CODE_WORD.sub(lambda m: humanise(m.group(0)), text)


#: WHAT A SPORT CALLS ITS OWN MARKETS. A handicap is a "point spread" in
#: football and a "run line" in baseball, and a reader who follows one sport
#: does not translate. The generic humaniser called MLB's run line a "point
#: spread", which is a sentence about the wrong sport.
SPORT_MARKET_WORDS = {
    ("mlb", "spread"): "run line",
    ("mlb", "total"): "total runs",
    ("nfl", "total"): "total points",
    ("nba", "total"): "total points",
    ("cfb", "total"): "total points",
}


def market_label(item: dict) -> str:
    """What to call this market in a filter or a heading."""
    kind = item.get("prop_type") or item.get("market") or item.get("market_type")
    sport = item.get("sport")
    named = SPORT_MARKET_WORDS.get((sport, kind))
    if named:
        return named
    return humanise(kind)


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
#: toward this side, which is not always the side the model took. READ OFF
#: THE ONE PLACE (2026-09-30), not a second literal of the yes spellings.
WHY_YES_SIDE = {market: YES_SIDE[market] for market in ("spread", "moneyline", "prop")}


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


#: The factors whose value is a signed distance in points, per sport. Named
#: rather than pattern-matched: a name that merely ENDS in "asked_distance"
#: could be anything, and this list is short enough to say out loud.
ASKED_DISTANCE_FACTORS = ("asked_distance", "nba_asked_distance",
                          "cfb_asked_distance")


def asked_distance_phrase(name: str, value) -> str | None:
    """"the question sits 6 points above what the model expects".

    None for any other factor, so the caller falls back to the declared WHY
    phrase. ROUNDED TO WHOLE POINTS because half a point of rounding residual
    is not a thing a reader needs four decimals of, and "sits 0.4 points
    above" reads as precision nobody claimed.

    AT ZERO IT SAYS SO PLAINLY rather than "0 points above", which reads as a
    measurement that failed.
    """
    if name not in ASKED_DISTANCE_FACTORS or value is None:
        return None
    points = round(float(value))
    if points == 0:
        return "the question sits about where the model expects"
    word = "above" if points > 0 else "below"
    unit = "point" if abs(points) == 1 else "points"
    return (f"the question sits {abs(points)} {unit} {word} what the model "
            f"expects")


def merge_jointly_read(contributions: list, joint) -> list:
    """Collapse each jointly-read group into ONE contribution (D1, 2026-09-03).

    Two correlated factors fitted together can end up carrying the halves of a
    difference: each coefficient inflates and they take opposite signs, so the
    model is using "A minus B" and neither A nor B is a claim by itself. The
    measurement that found this, and the numbers, are on
    `config.JOINTLY_READ_FACTORS`.

    Describing such a pair as two reasons tells a reader they disagree. They do
    not -- they are one reason with two terms, and SUMMING the contributions is
    exactly what the model did with them. So the group becomes one entry,
    carrying the sum, under one declared phrase.

    NOTHING IS HIDDEN BY THIS. The decomposition on the Factors page still
    lists every factor separately, because somebody auditing the model needs
    the parts. This is about the sentence on the card, which is a claim about
    WHY, and a claim about why must be true.

    `joint` is a list of (names, phrase) pairs, passed in rather than imported,
    for the same reason `factors` is: this module reads no configuration.
    """
    if not joint:
        return contributions
    grouped = {n: (names, phrase) for names, phrase in joint for n in names}
    if not grouped:
        return contributions

    # ONLY WHERE THE PAIR ACTUALLY BOTH CONTRIBUTED TO THIS ROW.
    #
    # A prediction written before the adjusted factor existed carries only the
    # raw one, and so does a game where the adjusted factor was absent. There
    # is no suppression in such a row -- one factor cannot suppress a factor
    # that is not there -- and describing it with the joint phrase would tell a
    # reader the model weighed "who they played" when it had no such input.
    # Rewriting what an old row knew is the reading equivalent of editing it.
    present = {}
    for c in contributions:
        name = c.get("factor")
        if name in grouped and not c.get("missing"):
            present[grouped[name][0]] = present.get(grouped[name][0], 0) + 1
    live = {names for names, n in present.items() if n > 1}

    out, sums = [], {}
    for c in contributions:
        name = c.get("factor")
        if name not in grouped or c.get("missing") or grouped[name][0] not in live:
            out.append(c)
            continue
        names, phrase = grouped[name]
        if names not in sums:
            sums[names] = {"factor": "+".join(names), "value": None,
                           "contribution": 0.0, "joint_phrase": phrase}
            out.append(sums[names])
        sums[names]["contribution"] += float(c.get("contribution") or 0.0)
    return out


def why_sentences(item: dict, factors: dict | None = None,
                  joint=None) -> list[str]:
    """The plain-English reasons for one pick, at most three sentences.

    ONE: the biggest reason. TWO: the second reason, OR the strongest thing
    pulling the other way when that is larger than the second supporter --
    because a reader who is only told what agrees with the pick is being sold
    to. THREE: the market, and only where a line exists.

    `item` carries `contributions` (the same list the decomposition uses);
    `factors` maps a factor name to its declared WHY phrase, passed in so this
    module never imports the registry.
    """
    # A JOINTLY-FITTED PAIR IS ONE REASON, NOT TWO THAT DISAGREE (D1).
    contributions = merge_jointly_read(item.get("contributions") or [], joint)
    known = factors or {}
    # Directions are relative to THE PICK, not to the question's yes side.
    flip = -1.0 if why_is_flipped(item) else 1.0

    scored = []
    for c in contributions:
        name = c.get("factor")
        value = c.get("contribution")
        if not name or value is None or c.get("missing"):
            continue
        # A VALUE-AWARE PHRASE WHERE THE VALUE IS THE POINT (B3, 2026-09-03).
        # "How far the question sits from what the model expects" is a label;
        # "the question sits 6 points above what the model expects" is the
        # thing itself, and the distance factors are the only ones whose
        # value is already in the reader's own units -- points.
        phrase = (c.get("joint_phrase")
                  or asked_distance_phrase(name, c.get("value"))
                  or known.get(name))
        if not phrase:
            # A factor with no declared phrase is SKIPPED rather than rendered
            # as its identifier. A test fails on any such factor, so this is a
            # belt to the test's braces and never the normal path.
            continue
        # A CONTRIBUTION OF EXACTLY ZERO IS NOT A REASON, and describing one is
        # how a card came to say "pulling the other way: the reach difference"
        # about two fighters with identical reach. It pulled neither way. The
        # supporters/opposers split below classifies on a strict sign, so a
        # zero belongs to neither list and would be picked up by the fallback
        # and labelled as opposition it never offered.
        #
        # Found in UFC, where identical reach is common, and fixed here because
        # nothing about it is UFC's: any factor can land on zero.
        if not float(value):
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


def why_block(item: dict, factors: dict | None = None,
              joint=None) -> dict:
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
    # THE SCHOOL FORM, matching the tile and the pick sentence (ruling E1).
    # The heading is grammatically the subject of the sentence that follows it
    # -- "Why Ohio: The biggest single reason is..." -- so it is prose, not a
    # label, and E1 asks that one pick read identically in all four places it
    # appears. "Ohio" on the tile and "Ohio Bobcats" in the rail is the same
    # inconsistency in a smaller font.
    picked, _prob = side_named(item, form="city")
    sentences = why_sentences(item, factors, joint)
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
    "predict:ufc": "Predict the fights",
    "catch-up": "Catch up after a sleep",
    # "Note what is known" rather than "capture": a reader is being told
    # what the machine does, and nothing on this panel is named after a
    # table.
    "capture": "Note what is known right now",
    # The live poll was a task with no words (audit 2026-09-05); `task_name`
    # opened the key out, which is the fallback and not the door.
    "live": "Follow the games being played",
    # The second look, named for what a reader would call it rather than for
    # the window it uses.
    "near-start": "Look at the line again before the start",
    # THE FINAL PASS (2026-09-03). "Take one more look" rather than "final
    # pass", because a reader of the Health panel is being told what the
    # machine does, not what the code calls it. The early pass keeps its own
    # name: from a reader's side there is one forecast a day and then a
    # second, closer look at it.
    "final:cfb": "Take one more look at college football",
    "final:nfl": "Take one more look at football",
    "final:mlb": "Take one more look at baseball",
    "final:nba": "Take one more look at basketball",
    "final:ufc": "Take one more look at the fights",
}


#: WHAT AN EARLY ROW IS CALLED WHEREVER IT APPEARS (2026-09-03).
#:
#: The word is "early view" and it is never "superseded", "stale" or
#: "obsolete". The early row was a real forecast, made honestly on what was
#: known days before the game; calling it stale would imply it was wrong, and
#: whether the later one is actually better is the open question
#: `calibration.early_vs_final` exists to answer. Until that number arrives,
#: the interface says WHEN it was made and nothing about its quality.
EARLY_VIEW = "early view"
STANDING_VIEW = "final"


def early_vs_final_line(record: dict) -> str:
    """"The later look changed the pick on 9 of 62 games and scored better on 41."

    BELOW THE GATE, THE COUNT AND NOTHING ELSE. A Brier comparison on eleven
    pairs is not a finding, and printing one would invite the reader to
    conclude something the sample cannot support -- LAW 4's rule, applied to
    a smaller question than an edge claim.
    """
    n = record.get("n") or 0
    gate = record.get("gate") or 0
    if not n:
        return ("No game yet has both an early and a later forecast, so there "
                "is nothing to compare.")
    games = "game" if n == 1 else "games"
    if not record.get("proven"):
        return (f"{n} {games} so far have both an early and a later forecast. "
                f"{gate} are needed before this can say whether forecasting "
                f"later helped.")
    changed = record.get("changed_side") or 0
    better = record.get("final_better") or 0
    return (f"The later look changed the pick on {changed} of {n} {games} and "
            f"scored better on {better}.")


#: What each forecaster is called in front of a reader. "The reasoning pass"
#: rather than "the LLM", which is an acronym for a thing a reader did not ask
#: about; "the model" rather than "statistical", which is a column value.
FORECASTER_WORDS = {
    "statistical": "the model",
    "llm": "the reasoning pass",
}

#: Why a forecaster stopped, in words. The stored reasons are internal tokens
#: and none of them may reach a page.
SILENCE_REASONS = {
    "bad_api_key": "its key was refused",
    "no_api_key": "it has no key",
    "api_error": "the service returned an error",
    "budget": "it had spent its daily budget",
}


def forecaster_silent_line(predictor: str, hours: float, wrote: int,
                           reason: str | None) -> str:
    """"The reasoning pass has written nothing for 31 hours..."

    A FORECASTER THAT STOPS IS A DEFECT, NOT A FOOTNOTE. It wrote 23 rows on
    one morning and none since; every run recorded why, in a column nobody
    reads, while every screen looked healthy because the other forecaster kept
    working.
    """
    who = FORECASTER_WORDS.get(predictor, predictor)
    days = hours / 24.0
    when = (f"{round(hours)} hours" if hours < 48
            else f"{round(days)} days")
    said = SILENCE_REASONS.get(reason or "")
    because = f" -- {said}." if said else "."
    return (f"{who.capitalize()} has written nothing for {when}{because} "
            f"It has {wrote} forecasts on the record and is not adding to "
            f"them, so nothing it would have said is being scored.")


#: What a reader is called the three UFC card kinds. THE PLAIN-WORDS LAW: no
#: internal identifier reaches the interface, so 'fight_night' -- which is what
#: the column holds and what every query filters on -- is never what a card
#: says. Held here rather than beside the tier logic because this module is the
#: one door prose comes through.
TIER_LABELS = {
    "numbered": "Numbered card",
    "fight_night": "Fight Night",
    "contender": "Contender Series",
}


MONTH_NAMES = ("January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December")


def settled_day_label(day: str | None) -> str:
    """"Yesterday" when it was, otherwise the day in words (cards UI).

    THE RENDERER MUST NOT DECIDE THIS. Whether the latest settled day counts as
    "yesterday" is a claim about a calendar, and the browser's calendar is the
    reader's while the record's is UTC -- so a card could say "Yesterday" about
    a day that, where the reader is sitting, was two days ago.

    Composed here, from the record's own dates, and it says the DATE whenever
    it is not certain the word is true.
    """
    if not day:
        return ""
    from datetime import date, timedelta

    try:
        when = date.fromisoformat(day[:10])
    except ValueError:
        return ""
    today = date.today()
    if when == today - timedelta(days=1):
        return "Yesterday:"
    if when == today:
        return "Today:"
    # BUILT FROM THE PARTS, not from a strftime directive. "%-d" strips the
    # leading zero on Linux and is a ValueError on Windows, and this project
    # runs on Windows -- a format string that raises on the operator's own
    # machine is worse than no formatting.
    return f"{when.day} {MONTH_NAMES[when.month - 1]}:"


def sentence_case(text: str | None) -> str:
    """"run line" -> "Run line". The FIRST letter only.

    `str.title()` would give "Run Line" and, worse, "Total Bases" -- title case
    on a label a person would write in sentence case. `capitalize()` would
    lowercase everything after the first letter, which destroys a proper noun.
    """
    if not text:
        return ""
    return text[0].upper() + text[1:]


def slate_headline(slate_title: str | None, state: str | None,
                   first_start_utc: str | None, now: str | None = None) -> str:
    """"Tonight", "Today", or the slate's day in words (cards UI, 2026-09-04).

    THE BRIEF ASKS FOR A WORD, NOT A KEY, and the reason is the defect this
    project has already fixed twice: "Day 159, 2026" and "Week 1, 2026" are
    slate keys, and a key in a heading is the database talking to itself.

    "Tonight" ONLY WHEN IT IS TONIGHT. A slate five days away is not tonight,
    and a heading that says so is wrong in the largest type on the page --
    which is worse than being dull. The word is used when the first start is
    today, and the day's own name otherwise.
    """
    if not slate_title:
        return ""
    if not first_start_utc:
        return slate_title
    from datetime import date, datetime, timedelta, timezone

    try:
        start = datetime.fromisoformat(
            first_start_utc.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return slate_title
    today = (datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone().date()
             if now else date.today())
    if start.date() == today:
        # EVENING, in the reader's own clock. A 1pm start is not "tonight".
        return "Tonight" if start.hour >= 17 else "Today"
    if start.date() == today + timedelta(days=1):
        return "Tomorrow"
    return slate_title


def no_lead_line(min_claim: float) -> str:
    """What the hero's place says when no pick on the tab reaches the floor."""
    return (f"Nothing leads this tab: no pick reaches {round(min_claim * 100)}%. "
            "The picks below are ranked as usual.")


def hero_tags(headline: str | None) -> dict:
    """What the hero card is answering, for each sort. Both, pre-composed.

    "SHARPEST DISAGREEMENT TONIGHT" IS FALSE ON A SLATE TEN DAYS OUT, and the
    brief's own wording assumes tonight because the brief was written about
    tonight. A tag naming a time that is not this one is the same defect as a
    heading naming a slate key: small, confident, and wrong.

    So the word is used only when the heading has already established it. The
    heading is the one place that decides what today is, and everything else
    on the page agrees with it rather than working it out again.

    BOTH VARIANTS ARE RETURNED because the sort toggle lives in the browser and
    the browser composes no prose. It picks between two sentences written here,
    exactly as it picks between the pre-composed count lines.
    """
    when = f" {headline.lower()}" if headline in (
        "Tonight", "Today", "Tomorrow") else ""
    return {
        "disagreement": f"Sharpest disagreement{when}",
        "confidence": f"Most confident{when}",
        # A CARD WITH NO LINE HAS NO DISAGREEMENT TO BE THE SHARPEST OF (audit
        # 2026-09-05): on a slate the market had not priced, the hero wore the
        # disagreement tag over "no line to compare it with".
        "no_line": f"Most confident{when}, with no line to compare against",
    }


RETIRED_WORD = "retired"


def market_words(sport: str, market: str) -> str:
    """"home runs", or "home runs · retired" once the operator has retired it."""
    words = MARKET_WORDS.get(market) or humanise(market)
    if _config.retired_market(sport, market):
        return f"{words} · {RETIRED_WORD}"
    return words


def fit_rows_words(sport: str, entries: list[dict]) -> str | None:
    """How many training rows carried one factor in each market's active fit.

    "point spread 1,703 of 2,632 · total 1,650 of 2,478" -- every count with
    the fit's own row count beside it (LAW 4), one clause per market, because
    a factor shared by three markets was fitted three times on three
    different sets of rows (operator ruling 4, 2026-09-24: "the fit reports
    each factor's rows used"). A factor the fit carried but could not fit
    says so; a count taken while indoor games were filled says that too,
    because those domes are among its rows without being readings.
    """
    parts = []
    for e in entries:
        words = market_words(sport, e["market"])
        if e.get("rows") is None:
            clause = f"{words}: rows not recorded by this fit"
        else:
            clause = f"{words} {int(e['rows']):,} of {int(e.get('n') or 0):,}"
        if e.get("excluded"):
            clause += ", not fitted"
        if e.get("indoor_filled"):
            clause += ", indoor games among them"
        parts.append(clause)
    return " · ".join(parts) if parts else None


def retired_outlook_line(n: int, gate: int, day: str) -> str:
    """What a retired market's gate line says instead of a projection."""
    when = date_words_from_iso(day) or day
    return (f"{n} of {gate} · retired {when}; nothing more will be written, "
            f"so {n} settled is the final count")


def market_outlook_line(n: int, gate: int, expected: int | None,
                        ends: str | None, *, written_before: bool = False) -> str:
    """The line beside a blind curve: its count, what the pace projects, and
    whether the gate can clear this season (ruling R3, 2026-09-05).

    COMPOSED HERE FROM 2026-09-27 (operator question 14, 3 of 3), where it
    was written inside `horizon.market_outlook`: the guard reads the line
    again from the outlook's own numbers, so there is one composition. `n` is
    the curve's own count -- one forecaster's standing questions, one card's
    for UFC -- and the words are the ones the page has always printed.

    NOTHING THIS SEASON IS NOT NOTHING EVER: `n` counts every season's
    questions and the pace only this season's, so with a count from an
    earlier season and no rate the line says "this season", not "yet" (item
    6's prover found the at-the-line line denying the claims it counted).
    """
    if expected is None:
        when = "this season" if written_before else "yet"
        return (f"{n} of {gate} · nothing written in this market {when}, so "
                f"there is no rate to project from")
    ends_short = ends[5:] if ends else "the season's end"
    line = f"{n} of {gate} · ~{expected} expected · season ends {ends_short}"
    if expected >= gate:
        return line
    return f"{line} · THIS GATE CANNOT CLEAR THIS SEASON"


def category_label(market: str, tier: str | None, predictor: str,
                   retired: dict | None = None) -> str:
    """"moneyline, Fight Night, statistical" -- never `fight_night`.

    The browser split "moneyline / fight_night / statistical" on its slashes
    and printed the middle part raw, which on the UFC record was the tier key
    on every row (audit 2026-09-05). Composed here, where the tier's words
    already live, and the forecaster keeps the plain word it is filtered by.
    """
    words = MARKET_WORDS.get(market) or humanise(market)
    # A RETIRED MARKET SAYS SO BESIDE ITS NAME (R1, 2026-09-05): "home runs ·
    # retired, statistical". The count beside it is final and the row is
    # greyed by the renderer.
    parts = [f"{words} · {RETIRED_WORD}" if retired else words]
    if tier:
        parts.append(tier_label(tier) or "")
    parts.append(FORECASTER_FILTER_WORDS.get(predictor, predictor))
    return ", ".join(p for p in parts if p)


#: The forecaster as the Record page's filter names it. Distinct from
#: FORECASTER_WORDS ("the model"), which is for sentences.
FORECASTER_FILTER_WORDS = {"statistical": "statistical", "llm": "reasoning pass"}


def tier_label(tier: str | None) -> str:
    """"Contender Series", never 'contender'.

    An unknown tier returns the empty string rather than the identifier: a card
    whose tier the source did not carry says nothing about its tier, which is
    the truth, and printing the raw value would be the exact failure the
    plain-words scan exists to catch.
    """
    return TIER_LABELS.get(tier or "", "")


#: WHAT A FLAGGED METHOD SAYS, in the operator's words (ruling 2, 2026-09-04).
#:
#: Keyed by the finding, not by the market: four sports share one finding
#: because they share one construction, and four copies of a sentence is how
#: three of them come to say something slightly different.
#:
#: THE NUMBERS ARE IN THE SENTENCE because a caveat without them is an opinion.
#: +0.001 and +0.002 are the walk-forward edges over always-the-base-rate,
#: rounded to the three decimals that separate them from zero, and they are the
#: measurements the close-outs carry.
#:
#: "SO FAR" IS DOING WORK. It dates the claim without a date: two sports have
#: been measured this way and the finding is about those two.
#: LAW 6 REACHES THE CARD (found by the operator, 2026-09-08). One note was
#: shared by every sport's total and it cited NBA and NFL walk-forward edges,
#: so a Cubs card argued from basketball and football. A number that mixes two
#: sports describes neither, and on a card it describes the wrong game.
#:
#: THE NOTE IS NOW BUILT FROM THAT SPORT'S OWN VERDICT, and a sport whose
#: total was never walked forward gets NO sentence: "we have not tested this"
#: and "we tested it and it was a coin flip" are different facts, and the
#: second may not be borrowed from a sport that is not on the card.
METHOD_NOTES: dict[str, str] = {
    # KEPT AS THE FALLBACK WORDING ONLY, with every other sport's figures
    # taken out of it. `method_note_for` is what a card reads.
    "total_at_own_rung": (
        "asked at the rung nearest the model's own expectation, so the "
        "question is close to a coin flip by construction — shown for the "
        "record."
    ),
}


def method_note_for(sport: str | None, market: str | None) -> str | None:
    """The flagged-method sentence for ONE sport, in that sport's own terms.

    THE STRUCTURAL CLAIM IS TRUE EVERYWHERE AND NEEDS NO FIGURES: the rung is
    the ladder point nearest the model's own expectation, so P(over) is near
    one half by construction. That sentence is the same for every sport
    because the METHOD is the same, and it cites nothing.

    WHAT IS ADDED IS ONLY THAT SPORT'S OWN RECORDED VERDICT -- the word and
    the sample size in `config.DISTRIBUTIONAL_VERDICTS[(sport, market)]`, read
    from that key and no other. A sport with no verdict says so; it does not
    borrow one.

    THE FIGURES IN THE OLD SENTENCE ARE NOT REPRODUCED. It read "(NBA +0.001,
    NFL +0.002 in walk-forward)", and those come from the measurement written
    up beside `config.FLAGGED_METHODS` rather than from the verdict registry's
    `rung_edge`, which holds different numbers. Rather than re-cite figures
    whose provenance I cannot pin from the registry alone, the note carries
    the verdict word and the sample, both of which are in the row it reads.
    """
    from . import config

    key = config.flagged_method(sport or "", market or "")
    if key is None:
        return None
    base = METHOD_NOTES.get(key)
    if base is None:
        return None
    label = SPORT_LABELS.get(sport, (sport or "").upper())
    verdict = config.distributional_verdict(sport or "", market or "")
    if verdict is None:
        return (f"{label}: {base} Reading it at the market's line instead has "
                f"not been measured for {label}.")
    n = verdict.get("n")
    where = f" over {n:,} games" if n else ""
    if verdict.get("verdict") == "NOT RUN":
        return (f"{label}: {base} Reading it at the market's line was measured"
                f"{where} and refused.")
    return (f"{label}: {base} Reading it at the market's line was walked "
            f"forward{where} and came back {verdict['verdict'].lower()}.")


def method_note(key: str | None) -> str | None:
    """The one line a flagged market carries, or None.

    THE CARD DOES NOT DECIDE WHETHER TO SAY THIS. `config.flagged_method` says
    which finding applies and this says what it reads as, so a market is
    flagged in exactly one place and worded in exactly one other.

    AN UNKNOWN KEY IS A FAULT, not a silent absence. A market flagged with a
    finding nobody wrote words for would render as an ordinary card, which is
    the failure mode the flag exists to prevent -- so it raises instead.
    """
    if key is None:
        return None
    try:
        return METHOD_NOTES[key]
    except KeyError:
        raise NoWordsForThisMarket(
            f"{key!r} is declared in config.FLAGGED_METHODS and has no words "
            f"in language.METHOD_NOTES. A flagged market with no note renders "
            f"as an unflagged one, which is the whole thing the flag is for."
        ) from None


def rate_line(expected: float | None, rung: float | None,
              probability: float | None, market: str | None = None) -> str:
    """"The model expects about 0.9 home runs; clearing 0.5 is about 60%."

    C3, 2026-09-03. A count market answers in two steps and a reader is
    entitled to both: the RATE the model actually predicts, and the
    probability of clearing the rung that follows from it. The logistic form
    it replaced had only the second, which is why an overconfident claim had
    nothing a reader could check it against -- "72%" says nothing about
    whether the model thinks he throws one touchdown or three.

    ROUNDED TO ONE DECIMAL, because a rate carried to four is precision the
    fit does not have and a reader would read as certainty.
    """
    if expected is None or probability is None:
        return ""
    thing = humanise(market) if market else "of them"
    said = f"The model expects about {expected:.1f} {thing}"
    if rung is None:
        return said + "."
    return (f"{said}; clearing {rung:g} is about "
            f"{round(probability * 100)}%.")


def what_it_knew(present: int, absent_phrases: list, data_age_hours=None) -> str:
    """"Rested on 7 of 9 factors; the starter wasn't announced yet."

    WHY A CARD SAYS THIS AT ALL. Every prediction row already records which
    factors it could measure and which it could not -- it has since the
    missing-data rule replaced silent zeroes -- and none of it reached a
    reader. A forecast made without the starter and one made with him look
    identical on the page, and the reader has no way to tell which kind of
    claim they are being shown.

    THE ABSENCES ARE NAMED, not counted. "Rested on 7 of 9" tells a reader
    something is missing; saying WHICH is the difference between a caveat and
    an explanation, and the declared WHY phrase is already the plain-words
    version of every factor.

    AT MOST TWO ARE NAMED. A card that lists nine absences is an inventory a
    reader skips, which is the same ruling the change line follows.
    """
    total = present + len(absent_phrases)
    if not total:
        return ""
    noun = "factor" if total == 1 else "factors"
    said = f"Rested on {present} of {total} {noun}"
    if absent_phrases:
        named = list(absent_phrases[:2])
        rest = len(absent_phrases) - len(named)
        joined = " and ".join(named) if len(named) == 2 else named[0]
        if rest:
            joined += f", and {rest} other{'s' if rest > 1 else ''}"
        said += f"; {joined} couldn't be measured"
    said += "."
    if data_age_hours is not None:
        said += " " + data_age_line(data_age_hours)
    return said


def data_age_line(hours: float) -> str:
    """"Data as of 2 hours before first pitch."

    THE AGE OF THE NEWEST THING BEHIND THE FORECAST. A pick made ninety
    minutes out and one made fifteen days out are different claims, and the
    only place that difference currently appears is a timestamp nobody reads.
    """
    if hours is None:
        return ""
    if hours < 0:
        return "Data from after the game had started."
    if hours < 2:
        return f"Data as of {max(1, round(hours * 60))} minutes before it starts."
    if hours < 48:
        return f"Data as of {round(hours)} hours before it starts."
    return f"Data as of {round(hours / 24)} days before it starts."


def pass_mark(pass_kind: str | None) -> str:
    """"final" or "early only", for a settled row (A3).

    "EARLY ONLY" RATHER THAN "EARLY", because on the Results page the row IS
    the record -- it was the forecast that got graded. Marking it merely
    "early" would read as though a better one existed and this was the wrong
    one shown. What actually happened is that no later pass ran, usually
    because the slate had already started, and the early forecast stood.
    """
    return STANDING_VIEW if (pass_kind or "early") == "final" else "early only"


def early_view_note(created_utc: str, kickoff_utc: str | None,
                    *, superseded: bool) -> str:
    """"Early view - written 15 days before kickoff." Says when, not whether.

    `superseded` IS NOT OPTIONAL AND IS NOT INFERRED. An early row is only an
    "early view" if a later forecast actually exists to stand in its place.
    Where the final pass has not run -- or ran after the game had started and
    correctly wrote nothing -- the early row IS the standing forecast, and
    telling a reader it had been replaced would be false.

    That was a real bug for about a minute: the first version said "a later
    forecast stands in its place" on every row in a record that contained no
    final rows at all."""
    tail = (" A later forecast stands in its place." if superseded else
            " No later forecast was made, so this one stands.")
    if not kickoff_utc:
        return (f"{EARLY_VIEW.capitalize()} - an earlier forecast of this "
                f"game.{tail}")
    from datetime import datetime

    def _dt(text):
        return datetime.fromisoformat(text.replace("Z", "+00:00"))

    try:
        hours = (_dt(kickoff_utc) - _dt(created_utc)).total_seconds() / 3600.0
    except (ValueError, AttributeError):
        return (f"{EARLY_VIEW.capitalize()} - an earlier forecast of this "
                f"game.{tail}")
    if hours >= 48:
        when = f"{round(hours / 24)} days"
    elif hours >= 2:
        when = f"{round(hours)} hours"
    else:
        when = f"{max(1, round(hours * 60))} minutes"
    return f"{EARLY_VIEW.capitalize()} - written {when} before the game.{tail}"


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
    # SET AND REJECTED, which is a different problem from not set at all and
    # from a network failure: the key exists, the service answered, and the
    # answer was no. Says what to do about it, because "could not be reached"
    # sent the reader to look at their connection for three days.
    "bad_api_key": "the second forecaster's key was refused -- it needs replacing",
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


#: Short month names for the build stamp. The footer says "built 1 Sep from
#: 0e23769" rather than an ISO timestamp: a person reads a date, and the
#: commit is the part that has to be exact.
SHORT_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def sport_record_line(label: str, wins: int, losses: int, settled: int) -> str:
    """"MLB 33-18", or "NCAAF 0 settled" for a sport with nothing graded.

    ALWAYS ONE SPORT (LAW 6). There is no combined figure anywhere and there
    must not be: a number mixing NFL spreads with MLB moneylines describes
    neither, and it flatters reliably because the easy sport dilutes the hard
    one. Each tab carries its own record and they sit side by side.

    A sport with nothing settled says so rather than showing "0-0", which
    reads as a record of no wins rather than an absence of games (LAW 4).
    """
    if not settled:
        return f"{label} 0 settled"
    return f"{label} {wins}-{losses}"


def sport_record_parts(wins: int, losses: int, settled: int) -> tuple[str, str]:
    """The record split into the part that always shows and the part that may not.

    ("33-18", "") for a graded sport, ("0", "settled") for one with nothing
    yet. Below the desk width the header has four tabs, four page links and a
    brand to fit, and the trailing word is what gives way -- LAW 4 wants the
    COUNT present, not a particular notation, and the hover carries the full
    sentence at every width. The number never goes.
    """
    if not settled:
        return "0", "settled"
    return f"{wins}-{losses}", ""


def sport_record_detail(label: str, wins: int, losses: int, settled: int,
                        written: int, voided: int) -> str:
    """The hover: what the tab's number is made of, including the voids.

    Voids are named because they are the difference between "written" and
    "settled" that nothing else on the tab explains, and an unexplained gap
    invites the reader to assume the worse of the two possible causes.
    """
    parts = [f"{label}: {settled} settled of {written} written"]
    if settled:
        parts.append(f"{wins} right, {losses} wrong")
    if voided:
        # "withdrawn" from 2026-09-24, the word every void now carries.
        parts.append(f"{voided} withdrawn")
    return " · ".join(parts)


#: The three states a slate can be in, and what each one leads with. The
#: countdown's own digits are formatted in the browser -- it ticks, and the
#: browser is the thing that knows what time it is now -- but every WORD
#: around them is written here.
SLATE_STATES = {
    "upcoming": "first kickoff",
    "live": "in progress",
    "complete": "complete",
}

#: WHAT EACH SPORT CALLS THE MOMENT IT STARTS (ruled 2026-09-09). "first
#: kickoff" was printed above a baseball slate, a basketball slate and a fight
#: card, because the state line composed one phrase for five sports out of
#: football's noun. A reader who is told "kickoff" about a game with a first
#: pitch is being told the page was written for a different sport.
FIRST_START_WORDS = {
    "nfl": "first kickoff",
    "cfb": "first kickoff",
    "mlb": "first pitch",
    "nba": "first tip-off",
    "ufc": "first bell",
}


def slate_state_word(state: str, sport: str | None = None) -> str:
    """The word beside the slate's clock, in the sport's own language.

    Falls back to football's noun only when the sport is unknown, which is
    the case a payload with no cards produces -- and even then it is a word
    rather than a blank, because a missing label reads as a broken line.
    """
    if state == "upcoming":
        return FIRST_START_WORDS.get(sport or "", SLATE_STATES["upcoming"])
    return SLATE_STATES.get(state, state)


def slate_state_line(state: str, final: int, games: int) -> str | None:
    """"in progress - 12 of 60 final". None while the slate is still ahead.

    None rather than an empty string for the upcoming case, because that line
    is a countdown the browser has to keep re-rendering and this one is a
    fact that does not change until a game ends.
    """
    if state == "upcoming":
        return None
    return f"{SLATE_STATES.get(state, state)} · {final} of {games} final"


def tier_filter_line(tier: str | None, shown: int, total: int) -> str:
    """"STRONG - 4 of 177 picks". Says the whole as well as the part.

    A filtered count with no denominator is the most quietly misleading
    number an interface can show: four picks looks like a thin slate rather
    than a narrow filter, and the reader has no way to tell which.
    """
    noun = "pick" if total == 1 else "picks"
    if not tier:
        return f"{total} {noun}"
    return f"{tier} · {shown} of {total} {noun}"


# ---------------------------------------------------------------------------
# A GAME IN FLIGHT (L2). Every string a live or finished tile shows.
# ---------------------------------------------------------------------------


def score_line(home: str, home_score, away: str, away_score) -> str | None:
    """"ALA 21 · ECU 7". None until there is a score to show.

    HOME FIRST, which is the opposite order to the matchup heading above it
    ("ECU @ ALA") and is deliberate: the heading is a fixture and reads as
    "visitor at host", while a score is read aloud host-first. Both orders are
    conventional in their own place, and the tile shows each in its own.
    """
    if home_score is None or away_score is None:
        return None
    return f"{home} {int(home_score)} \u00b7 {away} {int(away_score)}"


def clock_line(period: str | None, clock: str | None,
               state: str | None = None) -> str | None:
    """"3rd · 8:41", or "Top 6th" for a sport with no clock at all.

    Absent stays absent: a game with no period recorded shows nothing here
    rather than a dash, and baseball shows the inning alone because that is
    the whole of what the sport has to say about how far along it is.
    """
    if state == "final":
        # A FINISHED GAME HAS NO CLOCK. "Bottom 9th" beside a final score
        # reads as a game still being played, and the tile already carries a
        # verdict chip saying it is over.
        return None
    if not period and not clock:
        return None
    if not clock:
        return period
    if not period:
        return clock
    return f"{period} \u00b7 {clock}"


def running_total_line(home_score, away_score, line, side: str | None) -> str | None:
    """"31 · under 58.5" -- where the combined score stands against the ask.

    A TOTALS TILE HAS NO TEAM TO SHOW A SCORE FOR, so it shows the number the
    question is actually about. Naming the side as well means the reader can
    see at a glance whether 31 with a quarter left is comfortable or not,
    which is the only reason to put a running number on a card at all.
    """
    if home_score is None or away_score is None or line is None:
        return None
    return (f"{int(home_score) + int(away_score)} \u00b7 "
            f"{side or 'over'} {_number(line)}")


#: What a settled tile says about how the forecast did. WITHDRAWN (VOID until
#: 2026-09-24) is not a verdict about the model -- the forecast was taken back
#: or the question never answered -- so it is named separately rather than
#: folded into a loss.
VERDICT_WORDS = {1: "WIN", 0: "LOSS", None: ""}


def verdict_word(outcome, voided: bool = False) -> str:
    return WITHDRAWN_WORD if voided else VERDICT_WORDS.get(outcome, "")


#: The three states a tile can be in. Declared so the renderer branches on a
#: word the server chose rather than inferring one from a status string.
TILE_STATES = ("upcoming", "live", "final")


def tile_state(status: str | None, resolved: bool = False,
               voided: bool = False) -> str:
    """Which of the three a card is in. Unknown statuses read as upcoming.

    A status nobody mapped must not light a live mark on a tile: the same
    rule the poller follows when it declines to write an unmapped state, seen
    from the other end.
    """
    if voided or resolved or status == "final":
        return "final"
    if status == "in":
        return "live"
    return "upcoming"


# ---------------------------------------------------------------------------
# THE OPERATOR'S CALL, IN WORDS (GRIDIRON_12)
# ---------------------------------------------------------------------------


def live_rate_line(requests: int, polls: int, hours: int) -> str:
    """"41 requests over 41 polls in the last 24 hours".

    THE COUNT, NOT A RATE PER SE. "0.4 requests an hour" averages a Saturday
    of college football against six quiet days and describes neither -- the
    same objection LAW 6 makes about mixing sports, in miniature. The raw
    counts and the window let a reader do the division they actually want.
    """
    if not polls:
        return f"no live poll in the last {hours} hours"
    return (f"{requests} {'request' if requests == 1 else 'requests'} over "
            f"{polls} {'poll' if polls == 1 else 'polls'} in the last "
            f"{hours} hours")


def live_not_followed_line(sports: list[str]) -> str | None:
    """Which sports the live poll cannot follow, and that it is identity.

    Named rather than silently absent: a panel showing live figures for two
    sports and nothing for the other two invites the reader to conclude the
    poll is broken, when what is missing is a measured way to match one feed's
    game to another's.
    """
    if not sports:
        return None
    named = ", ".join(SPORT_LABELS.get(s, s.upper()) for s in sports)
    return (f"{named} are not followed live: their game ids come from other "
            f"feeds, and matching them needs a measured bridge rather than a "
            f"guess")


#: Printed labels per sport, for the few phrases here that name one. Kept as a
#: literal rather than imported from config, because this module deliberately
#: has one import and an internal key must never reach prose.
#: ONE DOOR (audit 2026-09-05). A second copy lived here with four sports in
#: it, and the fifth rendered as "UFC" only because the fallback upper-cases
#: an unknown key -- the right label for the wrong reason.
SPORT_LABELS = _config.SPORT_LABELS


def build_line(freshness: dict) -> str:
    """What this build is, in words a person can act on.

    THREE STATES, AND THE THIRD IS THE ONE THAT MATTERS. Running from source
    is the developer's ordinary case. A current build says so quietly. A build
    that has fallen behind says HOW FAR and what to do, because the failure it
    is warning about does not look like a failure: the record keeps filling,
    the window keeps opening, and the screen is simply a photograph of an
    older app. A three-day-old bundle showed a live record through an
    interface that predated college football, the desk and the rail, and
    nothing on the page said so.
    """
    if freshness.get("from_source"):
        return "running from source"

    commit = (freshness.get("commit") or "")[:7]
    built = freshness.get("built_utc") or ""
    when = ""
    if len(built) >= 10:
        try:
            month, day = int(built[5:7]), int(built[8:10])
            when = f"{day} {SHORT_MONTHS[month - 1]}"
        except (ValueError, IndexError):
            when = built[:10]
    stamp = f"built {when} from {commit}" if when else f"built from {commit}"

    behind = freshness.get("behind")
    if behind:
        return (f"{stamp} - this build is {behind} "
                f"{'commit' if behind == 1 else 'commits'} behind; rebuild")
    if behind is None:
        # COULD NOT CHECK is not the same as UP TO DATE, and saying nothing
        # would let the second be assumed from the first.
        return f"{stamp} - could not check against the repository"
    return stamp


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
    bits.append(f"LLM spend today ${float(ledger.get('usd_spent') or 0):.2f}"
                f" of ${float(ledger.get('usd_cap') or 0):.2f}")
    # WHAT YOU ARE LOOKING AT, last, where a footer's provenance belongs.
    build = meta.get("build")
    if build:
        bits.append(build_line(build))
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
                     settled: int | None = None, *,
                     since: str | None = None,
                     held_out: int | None = None,
                     questions: int | None = None) -> str:
    """The one line the Record tab shows about corrections.

    Two states, and they must not read alike: numbers shown exactly as the
    model made them, or numbers adjusted by the record with the version and
    the sample that did the adjusting.

    FROM QUESTION 32 (ruled 2026-09-29) a correction is in force by its own
    dated row, once it is measured on the questions it was not fitted on and
    the improvement is clear of zero: the line says since when (`since`, the
    row's instant) and on how many (`held_out` of `questions`), where it said
    the instant the correction was fitted -- which was the instant it came
    into force only because the weekly refit put it there.
    """
    if not active:
        # TWO STAGES, SAID AS TWO. A correction is fitted and inspectable at
        # `min_train`; it is APPLIED only once it is measured on the questions
        # it was not fitted on, which needs forty held out and so about two
        # hundred settled (`correction.HOLDOUT_MIN`). From question 32
        # (2026-09-29) "beats" means clear of zero: the bootstrap interval of
        # its improvement lies wholly above it.
        # QUESTIONS, FROM QUESTION 16'S RELEASE (2026-09-29): the gate counts
        # each settled question once, where this said "predictions".
        return (f"Claims are shown exactly as the model made them. A "
                f"correction is fitted at {min_train} {CORRECTION_GATE_NOUN} "
                f"and put in force only once one fitted on the earliest four "
                f"fifths of them improves the latest fifth, with a 95% "
                f"interval clear of zero.")
    when = date_words_from_iso((fitted or "")[:10])
    # WHAT IT WAS FITTED ON, as written: the forecasts, which this said
    # "settled" beside a gate that now counts questions (2026-09-29).
    n = f" on {settled:,} settled forecasts" if settled else ""
    fitted_words = f", fitted on {when}{n}" if when else n
    in_force = date_words_from_iso((since or "")[:10])
    measured = (f", measured on the latest {held_out} of the {questions} "
                f"{CORRECTION_GATE_NOUN} before it was fitted"
                if held_out and questions else "")
    since_words = f", in force since {in_force}{measured}" if in_force else ""
    # THE CORRECTION BY ITS DAY, ITS VERSION IN THE NOTE'S TOOLTIP (operator
    # question 19; the board merge, 2026-09-29): this said "(version 8, ...)".
    return (f"Shown numbers are earned: claims are adjusted by the record "
            f"(the correction{fitted_words}{since_words}).")


#: The two-word label under a tile's percentage. It answers "per cent of
#: WHAT", which a bare number does not.
#: What the tile's percentage is a percentage OF.
#:
#: THE GAME MARKETS HAVE ONE WORD EACH, and that is the point of E1 rather
#: than an oversight. `side_named` names the side the model actually took, so
#: a spread pick always covers and a moneyline pick always wins -- there is no
#: such thing as a tile whose headline names one team and whose label bets
#: against them. "MISSES" under "Alabama -24.5" was that tile, and a reader had
#: to do the inversion themselves to find out who the pick was on.
#:
#: Totals keep two words because a totals question names no team: over and
#: under are the two sides, and neither is a flip of the other's subject.
TILE_LABELS = {
    "spread": ("covers", "covers"),
    "moneyline": ("wins", "wins"),
    "total": ("over", "under"),
    "prop": ("over", "under"),
}


#: How a slate says which slate it is. A day-keyed sport stores YYYYMMDD --
#: an integer that orders the record perfectly and means nothing to a reader.
#: "Season 2026, week 20260905" was on the page above every college slate.
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday")


def _is_day_key(week: int | None) -> bool:
    """A slate key that is really a date: 20260905, not 5."""
    return week is not None and 19000101 <= int(week) <= 29991231


def date_words(week: int | None) -> str | None:
    """20260905 -> "Saturday 5 September". None when it is not a date.

    The weekday is included because it is the thing a reader actually holds a
    slate by -- "Saturday" is what a college football card IS -- and the year
    is not, because the season is already named beside it.
    """
    if not _is_day_key(week):
        return None
    import datetime as _dt
    text = str(int(week))
    try:
        day = _dt.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"


def slate_title(season: int | None, week: int | None, slate_word: str,
                league_date: str | None = None) -> str:
    """What to call this slate at the top of the page, in words.

    NEVER THE KEY, and the key comes in two disguises. College football stores
    a slate as 20260905 -- a date wearing an integer's clothes -- which
    produced "Season 2026, week 20260905". Baseball stores an ORDINAL, and
    the first fix missed it: the page then read "Day 158, 2026", which is not
    eight digits but is just as much an internal number a reader cannot use.

    So a key that IS a date is read as one, and a key that is not defers to
    the slate's actual calendar date. Only when neither is available does the
    number appear at all, and then with its own word beside it.
    """
    if week is None:
        return "This slate"
    # A WEEK NUMBER IS A NAME; A DAY NUMBER IS NOT. "Week 2" is how football
    # organises itself and how a reader refers to a slate, so it stays. The
    # day-keyed sports store an ordinal that means nothing outside this
    # database -- baseball's "Day 158" -- and those defer to the calendar.
    # The first version of this fix replaced BOTH, which quietly renamed
    # "Week 2, 2026" to a date nobody asked for.
    words = date_words(week)
    if not words and slate_word == "day":
        words = date_words_from_iso(league_date)
    if words:
        return f"{words}, {season}" if season else words
    return f"{slate_word.title()} {week}, {season}" if season else f"{slate_word.title()} {week}"


# ---------------------------------------------------------------------------
# HOW CLOSE A GATE IS (GRIDIRON_13 P1)
# ---------------------------------------------------------------------------
#
# Every gate in this app used to state only that it had not been cleared:
# "unproven -- 14 of 20 settled" and nothing about the shape of the wait. A
# reader could not tell 19-of-20 from 1-of-20 without doing the arithmetic,
# and the two are completely different situations -- one is next week, the
# other is next season.
#
# ONE COMPONENT, used by every counter on the page: the tier gates, the
# correction gate, the drift pairs, the rung window. A second implementation
# would be a second opinion about what "close" means.
#
# COUNTS, NEVER A PERCENTAGE. "70%" of the way to a verdict is a number that
# invites being read as a probability on a page whose whole subject is
# probabilities, and it hides the N that LAW 4 requires. The bar is drawn from
# the counts; the words are the counts.

def progress(done: int, needed: int, *, noun: str = "settled",
             cleared_note: str | None = None) -> dict:
    """How far along a gate is, in counts and in words.

    `n` is present because LAW 4's walker requires it beside any claim, and
    because the count IS the sample size here -- there is no other number this
    could be.
    """
    done = max(0, int(done))
    needed = max(0, int(needed))
    cleared = needed and done >= needed
    remaining = max(0, needed - done)
    if not needed:
        line = f"{done} {noun}"
        note = ""
    elif cleared:
        # NOT "140 of 100". Once a gate is behind you the denominator has
        # stopped being the point, and a count that exceeds its own target
        # reads as an error.
        line = f"{done} {noun}"
        note = cleared_note or "cleared"
    else:
        line = f"{done} of {needed} {noun}"
        note = f"{remaining} more {noun}"
    return {
        "done": done,
        "needed": needed,
        "remaining": remaining,
        "cleared": bool(cleared),
        "n": done,
        "line": line,
        "note": note,
    }


def gate_progress(done: int, first_gate: int, second_gate: int) -> dict:
    """A gate with a gate behind it: the verdict at 20, the edge at 100.

    TWO STAGES, ONE LINE AT A TIME. Showing "36 of 20" once a gate is cleared
    is arithmetic nobody needs; what a reader wants at that point is the NEXT
    thing standing between this tier and a claim about an edge. So the line
    re-points at the second gate the moment the first is behind it, and says
    which one it is talking about.
    """
    if done < first_gate:
        out = progress(done, first_gate)
        out["stage"] = "verdict"
        out["toward"] = "a verdict"
        return out
    out = progress(done, second_gate, cleared_note="past the edge figure")
    out["stage"] = "edge"
    out["toward"] = "the edge figure"
    if not out["cleared"]:
        out["note"] = (f"verdict earned - {done} of {second_gate} toward the "
                       f"edge figure")
    return out


def date_gate(declared: str, opens: str, today: str | None = None) -> dict:
    """A window that opens on a date, counted in days.

    THE SAME SHAPE AS EVERY OTHER GATE, deliberately: `done`, `needed`, `n`, a
    line and a note. A reader should not have to learn two ways of reading
    "how much longer" on one page, and a scan that checks progress lines for
    percentages should cover this one too.
    """
    from datetime import date

    def _d(text):
        return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))

    start, end = _d(declared), _d(opens)
    now = _d(today) if today else date.today()
    total = max(1, (end - start).days)
    elapsed = max(0, min(total, (now - start).days))
    remaining = max(0, (end - now).days)
    day_word = "day" if remaining == 1 else "days"
    return {
        "done": elapsed,
        "needed": total,
        "remaining": remaining,
        "cleared": remaining == 0,
        "n": elapsed,
        "opens": opens,
        "line": (f"{elapsed} of {total} days"),
        "note": ("the window is open - read it"
                 if remaining == 0
                 else f"read on {date_words_from_iso(opens)} - {remaining} "
                      f"{day_word}"),
    }


#: How many days of history a pace estimate needs before it is worth stating.
#: Below this the honest answer is that the pace is unknown -- an estimate
#: from three days of one sport is a number with a confidence interval wider
#: than the thing it estimates.
PACE_MIN_DAYS = 7
PACE_WINDOW_DAYS = 14


def pace_clause(remaining: int, per_slate: float | None,
                days_of_history: int) -> str:
    """"about 2 slates at the current pace", or that the pace is unknown."""
    if days_of_history < PACE_MIN_DAYS or not per_slate:
        return "pace unknown -- too little history to estimate one"
    slates = remaining / per_slate
    if slates < 1:
        return "about a slate at the current pace"
    rounded = int(round(slates))
    word = "slate" if rounded == 1 else "slates"
    return f"about {rounded} {word} at the current pace"


def closest_verdict_line(name: str | None, remaining: int,
                         pace: str) -> str:
    """The line at the top of Record: which gate is nearest, and how near.

    NAMED, NOT RANKED. It says which one is closest and how far, and stops --
    it does not order the others into a league table, because the second
    closest gate is not information anybody acts on.
    """
    if name is None:
        return "Every tier has settled enough for a verdict."
    return (f"Closest to a verdict: {name} -- {remaining} more settled, "
            f"{pace}.")


def rail_numbers_line(model_prob: float, market_prob: float | None,
                      gap: float | None, *, venue_line: bool = False) -> str:
    """"The model says 53%. The market implies 41% -- a 12 point disagreement."

    IN WORDS, NOT A PICTURE (GRIDIRON_16 R3). A dot-and-span graphic stood
    here until 2026-09-02. It showed the same three numbers and made the
    reader estimate two of them off a 100-pixel track, which is a worse way to
    read a percentage than reading the percentage.

    "no line" stays in words when the market has none, never an em-dash: a
    dash reads as an error rather than an absence.
    """
    model = f"The model says {round(model_prob * 100)}%."
    if market_prob is None:
        # "NO LINE" MUST NOT CONTRADICT THE LINE UNDERNEATH IT (E4,
        # 2026-09-06). The published-line sources price few of these markets,
        # and this sentence said so in absolute terms -- which, on a card that
        # now carries the venue's own number two lines below, read as the page
        # disagreeing with itself. It was visible in the first render.
        if venue_line:
            return (f"{model} No published line prices this market, so the "
                    f"venue's own number is the comparison below.")
        return f"{model} There is no line to compare it with."
    market = f"The market implies {round(market_prob * 100)}%"
    if gap is None:
        return f"{model} {market}."
    points = abs(round(gap * 100))
    if points == 0:
        return f"{model} {market} -- the same call."
    # "a 12 points disagreement" was the first phrasing and is not English.
    # Apart reads naturally at every count and needs no article.
    word = "point" if points == 1 else "points"
    return f"{model} {market} -- {points} {word} apart."


def schedule_disagreement(label: str, recorded: str, os_state: dict) -> str | None:
    """When the app and the scheduler disagree about a task, say which is which.

    None when they agree, so a settled row carries no noise. The wording names
    BOTH values and which one will actually happen, because "out of sync" is
    a status, not something a person can act on.
    """
    if not os_state or not os_state.get("available"):
        return None
    if not os_state.get("found"):
        return (f"{label} is not installed on this machine, so nothing will "
                f"run at {recorded}. Install the scheduled tasks to use this "
                f"setting.")
    held = os_state.get("at")
    if held and recorded and held != recorded:
        return (f"{label} is recorded as {recorded} here, but the scheduler "
                f"holds {held} -- and the scheduler is what actually wakes up. "
                f"Set the time again to move it.")
    return None


def gate_name(kind: str, subject: str) -> str:
    """What a gate on the Record page is called, in words.

    COMPOSED HERE, NOT IN THE BROWSER. The renderer built these by gluing a
    label onto a data field -- "Where the line went after " + a market name --
    and `audit.check_js_composes_no_prose` caught it on the first gate run.
    That guard exists because `'picked ' + String(s.subject).toUpperCase()`
    once shipped a raw identifier to a reader; a sentence assembled in the
    browser is outside the plain-words scan, outside the side resolver and
    outside the tests.
    """
    if kind == "correction":
        return f"A correction for {subject}"
    if kind == "drift":
        return f"Where the line went after {subject}"
    if kind == "read_window":
        return f"Reading {subject}"
    return subject


def results_caption(n: int, day: str | None) -> str:
    """"22 predictions, resolved on Monday 31 August" -- or the whole season.

    THE DAY IN WORDS, not the stored key. The renderer glued " on " onto
    "2026-08-31" until 2026-09-02, which put a date key in front of a reader
    and composed a sentence in the browser -- two rules at once.
    """
    thing = "prediction" if n == 1 else "predictions"
    if not day:
        return f"{n} {thing}"
    words = date_words_from_iso(day) or day
    return f"{n} {thing}, played on {words}"


def login_glance_line(label: str, won: int, lost: int, open_now: int,
                      slate_word: str) -> str:
    """"MLB 45-25 - 46 questions tonight". COUNTS ONLY, and never a total.

    The sign-in screen is the one place the record faces somebody who has not
    signed in, so this is written to be worth nothing to them: a win-loss
    record and how many questions are open. No side, no team, no price, no
    probability -- a count is not a tip.

    QUESTIONS, NOT "PICKS" (the prover of operator ruling B, 2026-10-07: "A
    leg is called a pick only if its edge after fees is 3 percentage points
    or more. Below that it is shown as a number, never as a pick"). The count
    is of every open question the record holds, and it said "46 picks
    tonight" of them -- on 6 October none of them a pick under B.
    """
    parts = []
    if won or lost:
        parts.append(f"{won}-{lost}")
    if open_now:
        when = "tonight" if slate_word == "day" else "this week"
        thing = "question" if open_now == 1 else "questions"
        parts.append(f"{open_now} {thing} {when}")
    if not parts:
        return f"{label} nothing settled yet"
    return f"{label} " + " · ".join(parts)


def signed_out_line(devices: int | None) -> str:
    """"Signed out on 3 devices." The count, because it is the reassurance."""
    if not devices:
        return "Signed out. No other device was signed in."
    thing = "device" if devices == 1 else "devices"
    return f"Signed out on {devices} {thing}."


def factor_what(rationale: str | None,
                plain_names: dict | None = None) -> str:
    """One line saying what a factor measures, from its declared rationale.

    THE FIRST SENTENCE, and no more. A factor card answers "what is this" at a
    glance; the full declaration is a LAW 2 dated record and stays in the
    table underneath, where somebody auditing goes looking for it. Composed
    here rather than in the browser, like every other visible string.

    A DECLARATION MAY NAME ANOTHER FACTOR BY ITS CODE, the way a code comment
    does -- and one does: a rationale mentioning `short_week_diff` put that
    identifier straight onto a card, where the plain-words scan found it. The
    audit table is allowed to be dense and is exempt by position; a CARD is a
    reading surface and is not. So the codes are swapped for the names those
    factors already have, rather than editing a dated declaration to suit the
    page showing it.
    """
    if not rationale:
        return ""
    text = str(rationale).strip()
    for code, plain in sorted((plain_names or {}).items(),
                              key=lambda kv: -len(kv[0])):
        if plain and code in text:
            text = text.replace(code, plain)
    for stop in (". ", " -- ", "; "):
        cut = text.find(stop)
        if 0 < cut < 160:
            return text[:cut + 1].strip().rstrip(".") + "."
    return (text[:150].rstrip() + "...") if len(text) > 160 else text


#: THE FACTOR-VALUE COMPOSER LIVES IN `factors.compute`, and this re-exports
#: it. Not a preference: `gridiron.model.llm` is inside the prediction closure
#: and this module names market columns (`market_implied_prob`,
#: `running_total_line`), so importing `language` from there is a LAW 1
#: violation -- and the closure scan said so within a minute of it being
#: written.
#:
#: THE PRECEDENT IS THE ONE `audit` ALREADY FOLLOWS: "the runtime missing-data
#: check therefore lives in `factors.compute`, and `audit` re-exports it."
#: Same shape, same reason.
from .factors.compute import factor_value_words  # noqa: E402,F401

def with_prefix_aliases(phrases: dict[str, str],
                        prefixes: tuple[str, ...] = ()) -> dict[str, str]:
    """Add the shortened forms of each factor name that a model actually writes.

    THE MODEL SHORTENS NAMES. Asked about `ufc_scheduled_rounds` it wrote
    "(scheduled_rounds = 0)"; asked about `mlb_prop_mean_vs_line` it wrote
    "mean_vs_line". An exact-match substitution sees neither, and both reach a
    card as snake_case.

    DERIVED FROM THE DECLARED NAMES, never guessed. Every suffix at an
    underscore boundary is a candidate, and a candidate becomes an alias only
    when all three hold:

    * IT IS NOT ITSELF A DECLARED FACTOR. `nba_asked_line` yields `asked_line`,
      which is a declared factor of its own, so no alias is made -- a reader
      must never be shown basketball's phrase over football's factor.
    * IT STILL LOOKS LIKE A CODE NAME. `mean_vs_line` does; `line` does not,
      and mapping a bare English word would rewrite ordinary prose.
    * EVERY DECLARED NAME THAT PRODUCES IT AGREES ON THE PHRASE. Three sports
      declare a `prop_mean_vs_line` variant and all three read "where the line
      sits against his recent average", so substituting is safe whichever was
      meant. Where they disagreed, no alias would be made and the code name
      would survive -- which is the honest outcome, because guessing which
      sport's factor a shortened name meant is exactly the sort of quiet
      wrongness this project spends its time preventing.

    `prefixes` is accepted and unused beyond documentation of intent: the
    suffix walk covers sport prefixes and every other leading segment without
    needing to be told what they are.
    """
    owners: dict[str, set[str]] = {}
    for name, phrase in phrases.items():
        parts = name.split("_")
        for i in range(1, len(parts) - 1):
            alias = "_".join(parts[i:])
            owners.setdefault(alias, set()).add((phrase or "").strip())

    out = dict(phrases)
    for alias, seen in owners.items():
        if alias in phrases:
            continue
        if len(seen) != 1:
            continue
        phrase = next(iter(seen))
        if phrase:
            out[alias] = phrase
    return out


def humanise_reasoning(text: str | None, phrases: dict[str, str]) -> str | None:
    """Swap any code name in stored reasoning for its plain phrase.

    AT RENDER TIME, NEVER BY REWRITING. LAW 3 is append-only: a prediction's
    reasoning is what the forecaster said and is not edited afterwards. So the
    row keeps `mlb_bullpen_recent_load` for ever and the READER is shown "how
    hard the bullpens have been worked lately".

    WHY THERE ARE ROWS TO REPAIR AT ALL. The prompt used to name factors by
    their code names, and the model quoted them back: measured 2026-09-05 at
    19 of 42 new UFC rows and 8 of 23 older MLB ones -- about 45% either way,
    every one of them a snake_case identifier on a card. The prompt now uses
    plain names, so no NEW row can carry one; this is for the old ones.

    LONGEST NAME FIRST, and it matters: `mlb_prop_mean_vs_line` contains
    `prop_mean_vs_line`, and replacing the short one first would leave `mlb_`
    stranded in front of a phrase.

    THE ONE DOOR. Every surface that shows stored reasoning calls this, so a
    new surface cannot quietly render raw. `audit.check_no_code_names_in_llm_prose`
    is what makes that true rather than hoped for.
    """
    if not text:
        return text
    out = text
    for name in sorted(phrases, key=len, reverse=True):
        phrase = (phrases.get(name) or "").strip()
        if not phrase or name not in out:
            continue
        out = out.replace(name, phrase)
    # AND A NAME NO FACTOR HAS (2026-09-25). Row 2471, an NFL forecast the
    # reasoning pass wrote at 19:26Z on 25 September, says "(neither_neutral
    # =1)": an identifier the model made up, which no registry phrase can
    # replace because nothing declares it. The same render-time rule as a
    # void's reason (`plain_reason`, 2026-09-24): a code-shaped word left over
    # is read out in words, and the row keeps what was written.
    return _CODE_WORD.sub(lambda m: humanise(m.group(0)), out)


def tier_chip_label(tier: str | None, proven: bool) -> str:
    """"STRONG" once it is proven, "STRONG · unproven" until then.

    MEASURED, 2026-09-04, and this is why it exists. Across four live slates,
    **17 of 379 cards** carried a tier chip with any settled record behind it.
    The other 362 named a band -- often STRONG -- with nothing standing behind
    it, and the sentence saying so (`tier_record_line`) reached the reader only
    as a HOVER TOOLTIP on a grid card: absent on every touch device and on
    every glance.

    THE PRECEDENT IS THIS PROJECT'S OWN, three rulings old. The coin-flip note
    was put on the collapsed card face rather than one tap in, because "a
    caveat behind a tap is a caveat most readers never reach, and the reader
    taking the percentage at face value is exactly the one it is written for."
    A tooltip is worse than a tap.

    ONE WORD, NOT THE SENTENCE. The full line still travels and the hero still
    prints it; a chip is small and the reader only needs to know that the band
    is a claim rather than a record. The sentence is a tap away in the body,
    where the reader who wants the numbers goes.

    NO NUMBER, so the cards brief's R2 is untouched -- "unproven" is a word,
    not a second figure competing with the probability.
    """
    if not tier:
        return ""
    return tier if proven else f"{tier} · unproven"


def tier_record_line(tier: str, settled: int, needed: int,
                     earned: float | None) -> str:
    """"STRONG - 8 settled, not yet proven." The band names itself.

    BELOW THE GATE IT SAYS THE HONEST THING AND NAMES THE BAND. The old
    sentence read "tier unproven - 8 settled of 20 needed", which is true and
    made a reader carry the band in their head from the chip beside it. Saying
    STRONG here costs nothing and means the line survives being read on its
    own -- in a digest, in a notification, anywhere the chip is not.

    ABOVE THE GATE IT REPORTS THE EARNED RATE, with its N beside it, because
    LAW 4 permits a figure exactly when the sample is there and not before.
    """
    if earned is not None and settled >= needed:
        return f"{tier} hits {round(earned * 100)}% over {settled} settled"
    noun = "settled" if settled != 1 else "settled pick"
    return (f"{tier} - {settled} {noun}, not yet proven; "
            f"{needed} needed before it earns a verdict")


def least_tested_tier_line(tier: str, settled: int, gate: int) -> str | None:
    """"STRONG is the least-tested tier so far - 3 settled."

    None once the band has cleared its gate, because the sentence is a caveat
    and a caveat that outlives its reason is furniture. Picks opens on STRONG
    (ruling R2, 2026-09-02), which puts the app's most confident claims in
    front of a reader first -- and the tier with the fewest settled rows
    behind it. Saying so is the whole point: the default is a convenience, not
    a verdict.
    """
    if settled >= gate:
        return None
    return (f"{tier} is the least-tested tier so far - {settled} settled of "
            f"{gate} needed before it earns a verdict.")


def calendar_day_line(day: str, won: int, lost: int, void: int) -> str:
    """"Wednesday 2 September - 5 right, 2 wrong, 1 withdrawn".

    THE WHOLE DAY IN ONE SENTENCE, because the square shows "5-2" and a
    reader hovering it deserves the rest -- particularly the withdrawn
    forecasts (the voids), which the square deliberately does not fold into
    either number. "withdrawn" from 2026-09-24, the word every void carries.
    """
    when = date_words_from_iso(day) or day
    if not (won or lost or void):
        return f"{when} - nothing settled"
    parts = []
    if won or lost:
        parts.append(f"{won} right, {lost} wrong")
    if void:
        parts.append(f"{void} withdrawn")
    return f"{when} - " + ", ".join(parts)


def calendar_note() -> str:
    """What the colours mean, said once under the calendar."""
    return ("Green when more went right than wrong that day, red when fewer, "
            "grey when even. Withdrawn forecasts are counted separately and "
            "are neither: a forecast taken back is not a result, and a "
            "question that was never answered is not a loss.")


def no_picks_from(label: str, others: list[tuple[str, int]]) -> str:
    """Why the slate is empty for the forecaster the reader chose.

    An empty list with no explanation reads as a broken page. It is not: the
    LLM runs on one sport and stands down when it is degraded, and a slate
    with no LLM picks on it is the system working. So the sentence says who
    made none AND who made some, with the counts, rather than leaving a reader
    to guess which of the two happened.
    """
    # FORECASTS, NOT "PICKS" (operator ruling B, 2026-10-05; built
    # 2026-10-07): B calls a leg a pick only at three points after fees, and
    # what a forecaster made none of here is a forecast.
    head = f"{label} made no forecasts on this slate."
    if not others:
        return head
    rest = "; ".join(f"{lab} made {n}" for lab, n in others)
    return f"{head} {rest}."


def date_words_from_iso(day: str | None) -> str | None:
    """"2026-09-27" -> "Sunday 27 September". None when there is no date."""
    if not day or len(day) < 10:
        return None
    try:
        return date_words(int(day[:4] + day[5:7] + day[8:10]))
    except (ValueError, TypeError):
        return None


def slate_option(season: int | None, week: int | None, n: int,
                 slate_word: str, league_date: str | None = None) -> str:
    """One line in the slate chooser: the same words, plus how many picks."""
    return f"{slate_title(season, week, slate_word, league_date)} ({n})"


def flipped_line(item: dict) -> float | None:
    """The spread as the PICK holds it, not as the question asked it.

    A question asked at -24.5 that the model answers "no" is a pick on the
    other side at +24.5. Same claim, same probability, and it is the form a
    person says out loud. Kept in one function because the tile, the sentence
    and the history row all need the same number, and three copies of a sign
    flip is three chances to get a sign wrong.
    """
    line = item.get("line_asked")
    if line is None:
        return None
    # THE NUMBER FLIPS EXACTLY WHEN THE NAME DID, and `side_flips` is the one
    # place that decides. This used to ask `is_no_side`, which flips the line
    # even when there is no opponent to move the pick to.
    return -float(line) if side_flips(item) else float(line)


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

    # A FIGHT'S TWO OTHER MARKETS SAY THEMSELVES. Falling through to the prop
    # branch produced "Dan Hooker vs Salahdine Parnasse over 4.5" and
    # "... yes dist" -- the subject repeated from the heading above it, and a
    # truncated stat name standing in for a question.
    if market_type == "rounds":
        word = "Under" if is_no_side(item) else "Over"
        rung = _number(line)
        unit = "round" if str(rung) in ("0.5", "1", "1.5") else "rounds"
        return f"{word} {rung} {unit}"

    if market_type == "distance":
        return "Not the distance" if is_no_side(item) else "Goes the distance"

    if market_type == "moneyline":
        # A NO SIDE THAT DID NOT FLIP IS SAID AS ASKED (the sweep of
        # pick-number step C, 2026-09-30): with no opponent recorded `subject`
        # is the question's own club, and "PHI to win" over a pick against
        # PHI was the wrong side on the row, on My day's chip and on the tile.
        # `phrase` says the same now; every card on the record carries an
        # opponent, so nothing drawn moves.
        if is_no_side(item) and not side_flips(item):
            return f"{subject} {side_word(item.get('model_side'))}"
        return f"{subject} to win"

    if market_type == "spread":
        if line is None:
            return subject
        # BOTH HALVES FLIP TOGETHER (ruling E1). `side_named` has already
        # swapped the club when the model took the NO side, so the number has
        # to swap with it or the tile reads "Alabama +30.5" for a pick against
        # Alabama. One `is_no_side` decides both, here and in `phrase`.
        return f"{subject} {flipped_line(item):+.1f}"

    # A prop: the person, the side, the number, the stat.
    market = item.get("prop_type") or item.get("market")
    if line is not None and float(line) == 0.5:
        said = half_unit_phrase(subject, market, item.get("model_side"))
        if said:
            return said
    return (f"{subject} {side_word_or_side(item.get('model_side'))} "
            f"{_number(line)} {humanise(market)}").strip()


def unfinished_run_line(age_hours: float) -> str:
    """A run that started and never said how it ended, in words."""
    return (f"started {age_hours:.0f}h ago and never recorded an ending. The "
            "process was killed, or the machine slept, before it could say "
            "what happened; whatever it was doing may be half done.")


def abandoned_run_line(started_iso: str, marked_iso: str,
                       silent_after_hours: float) -> str:
    """The detail an abandoned run is stored with (GRIDIRON_REPAIR item 7,
    2026-09-26): when it started, when a later run marked it, and the
    silence it was past.

    STORED, so it keeps its stamps as the record writes them and the Health
    panel says them as dates on the way out (`task_detail_words`). It starts
    in lower case on purpose: a leading "Word:" is read there as an
    exception's class name and cut off.
    """
    return (f"never recorded an ending: it started {started_iso} and was "
            f"marked abandoned {marked_iso}, past the {silent_after_hours:g} "
            "hours after which this task counts as silent. The process was "
            "killed, or the machine slept or lost power, before it could say "
            "how it ended; whatever it was doing may be half done.")


def counted(n: int, noun: str, plural: str | None = None) -> str:
    """"1 prediction", "41 predictions". Never "prediction(s)".

    A bracketed plural is a code plural: it asks the reader to do the
    grammar. The Health panel showed "wrote 41 prediction(s) for slate
    20260905" until the audit of 2026-09-05, and both halves of that line
    were the same defect -- something written for the log and shown to a
    person.
    """
    word = noun if n == 1 else (plural or noun + "s")
    return f"{n} {word}"


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

# ---------------------------------------------------------------------------
# THE RAIL (D3). Every string in the three desk panels is composed here.
# ---------------------------------------------------------------------------

#: The windows a slate's kickoffs fall into, on the league's clock: (first
#: hour, last hour inclusive, what to call it). Declared rather than derived,
#: because a window is a broadcast slot -- "the noon games" is a thing a
#: reader already knows the shape of, and clustering the actual times would
#: rename it every week.
KICKOFF_WINDOWS = (
    (0, 14, "early"),
    (15, 18, "afternoon"),
    (19, 23, "night"),
)


def kickoff_window(hour: int | None) -> str | None:
    """Which declared window an hour belongs to. None stays None."""
    if hour is None:
        return None
    for first, last, name in KICKOFF_WINDOWS:
        if first <= hour <= last:
            return name
    return None


def window_line(name: str, count: int) -> str:
    """"afternoon · 22 games". The count is the claim, so it carries itself."""
    return f"{name} · {count} {'game' if count == 1 else 'games'}"


def coverage_line(market: str, priced: int, asked: int) -> str:
    """"spread · 60 of 60 priced".

    COVERAGE IS REPORTED, NEVER USED TO CHOOSE (ruling R-A, LAW 1). Questions
    are formed blind for every game on the slate; how many of them the market
    happened to price is a fact about the market, and it is stated here so a
    reader can see when a comparison is thin rather than wonder why a gap
    column is half empty.
    """
    return f"{market} · {priced} of {asked} priced"


def sharpest_line(gap: float | None, phrase: str | None) -> str:
    """"+19 percentage points apart · Temple covers -14.5" -- the widest gap.

    Named "apart" rather than "edge": the number is the distance between two
    opinions, and which of them is right is exactly what the record has not
    established yet.

    SAYS *PERCENTAGE* POINTS, and the long word is the point. The first draft
    read "+54 points apart" next to a pick reading "covers -14.5", on a page
    about a sport whose margins are measured in points -- two different units
    one word apart, and the shorter word was the wrong one.
    """
    if gap is None or not phrase:
        return "no market comparison on this slate"
    points = round(gap * 100)
    return f"{points:+d} percentage points apart · {phrase}"


#: The left-hand labels on the glance panel's fact rows. Here rather than in
#: the renderer because the ruling of 2026-08-31 puts every visible phrase in
#: this module -- and because the first draft had them as JavaScript literals,
#: which is exactly how a second vocabulary starts.
#:
#: "SHARPEST ON THIS SLATE" NAMES ITS SCOPE, and it has to. The greeting panel
#: sits directly beneath this one and reports the sharpest disagreement among
#: the predictions that arrived since the reader last looked -- a different
#: set, a different number. Both said "sharpest disagreement" in the render,
#: eight inches apart, disagreeing.
GLANCE_LABELS = {
    "sharpest": "sharpest on this slate",
    "tiers": "graded so far",
}


def glance_label(key: str) -> str:
    return GLANCE_LABELS.get(key, key)


def tier_status_line(label: str, proven: int, tiers: int, fullest: int,
                     needed: int) -> str:
    """LAW 4 in one line: how much of this sport's record is gradeable yet.

    Takes the sport's PRINTED label rather than its key, because this
    module has one import and does not get a second one to look a name up
    with -- an internal key reaching prose is the defect it exists to stop.

    A COUNT, NEVER A POOLED RATE. Adding up settled predictions across markets
    is arithmetic; adding up their hit rates would be the merge LAW 4 forbids,
    and it would flatter, because the easy market dilutes the hard one.
    """
    if proven:
        return f"{proven} of {tiers} {label} tiers proven"
    return (f"no {label} tier proven yet · fullest has {fullest} "
            f"of {needed} settled")


def unreachable_line() -> str:
    """What the page says when a request never reached the appliance.

    THE BROWSER'S OWN WORDS ARE NOT WORDS (UI audit finding 8, 2026-09-05).
    A tab tapped while offline put "Failed to fetch" in the error box -- a
    string from the network layer, meaning nothing to a reader -- and it
    stayed there after the connection returned and the next tap succeeded.
    This sentence is handed to the page at boot, so it is there when the
    network is not.
    """
    return ("The appliance could not be reached, so nothing here has been "
            "refreshed. Check the connection and try again.")


def settled_count_line(n: int) -> str:
    """"13 settled" -- the picks a finished slate no longer shows (UI audit
    finding 9, 2026-09-05). The counts line said "53 picks" over a page of 40,
    because settled picks leave the grid once a slate is not live and nothing
    said where the other 13 had gone."""
    return f"{n:,} settled"


def bucket_countdown_line(label: str, n: int, gate: int) -> str:
    """"50-60% bucket: 30 of 100 · 70 more before calibration speaks", and past
    the gate "50-60% bucket: 158 settled · past the 100 needed, so calibration
    speaks here". The first shape used to keep going -- "158 of 100 · 0 more
    before calibration speaks" -- which says the gate is still ahead when it is
    behind (UI audit finding 10, 2026-09-05). Tested AT the gate."""
    if n >= gate:
        return (f"{label} bucket: {n:,} settled · past the {gate:,} needed, "
                "so calibration speaks here")
    return f"{label} bucket: {n:,} of {gate:,} · {gate - n:,} more before calibration speaks"


_DETAIL_CLASS = _re.compile(r"^[A-Z][A-Za-z0-9]*(?:Error|Exception|Answered|Refused|Missing|Failure)?:\s+")
_DETAIL_SLATE_KEY = _re.compile(r"\bslate (\d{4})(\d{2})(\d{2})\b")
_DETAIL_STAMP = _re.compile(r"\b(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2})?Z?\b")
_DETAIL_FACTOR_SET = _re.compile(r"factor set '?fs(\d+)'?")
_DETAIL_BARE_FS = _re.compile(r"(?<![A-Za-z0-9_])'?fs(\d+)'?(?![A-Za-z0-9_])")


def task_detail_words(detail: str | None) -> str | None:
    """A task's recorded detail, as a reader would say it.

    THE HEALTH PANEL PRINTED A PYTHON EXCEPTION (UI audit finding 11,
    2026-09-05): "SlateAlreadyAnswered: ufc 2026 slate 20260905 already has 84
    forecasts ... written 2026-09-04T02:04 under factor set 'fs2'". The class
    name, the slate key and the ISO stamp are the record's vocabulary, and
    `run_task` stores them as the exception wrote them; this is the door they
    pass through on the way to a page, and it leaves the sentence's meaning
    alone.
    """
    if not detail:
        return detail
    # THE ABSOLUTE DAY, never "Today": a task record is read back days later.
    def day_words(y, mo, d):
        return f"{int(d)} {MONTH_NAMES[int(mo) - 1]} {y}"

    text = _DETAIL_CLASS.sub("", detail, count=1)
    text = _DETAIL_SLATE_KEY.sub(
        lambda m: "the slate of " + day_words(m.group(1), m.group(2), m.group(3)), text)
    text = _DETAIL_STAMP.sub(
        lambda m: day_words(m.group(1), m.group(2), m.group(3)) + f" at {m.group(4)}:{m.group(5)} UTC",
        text)
    text = _DETAIL_FACTOR_SET.sub(lambda m: f"factor set {m.group(1)}", text)
    # A bare version token ("fitted 12 categories under fs2") is the same
    # identifier without the words around it (U4 re-drive, 2026-09-06).
    text = _DETAIL_BARE_FS.sub(lambda m: f"factor set {m.group(1)}", text)
    return text


def llm_routed_off_line(n: int, gate: int, since: str) -> str:
    """What an LLM prop category's gate line says once the reasoning pass no
    longer asks that market (ruling E1, 2026-09-06). The count is final and
    the sentence says so, rather than counting down to a gate that will never
    be reached and reading as a stall."""
    when = date_words_from_iso(since) or since
    return (f"{n} of {gate} · the reasoning pass stopped asking this market "
            f"{when}; nothing more will be written, so {n} settled is the "
            f"final count")


# ---------------------------------------------------------------------------
# AT THE VENUE'S LINE (E4, 2026-09-06) -- a forecast, never advice
# ---------------------------------------------------------------------------
#
# Every sentence here states two probabilities for ONE fixed question and
# stops. It never says which side to take, never calls a gap an opportunity,
# and never uses a word from `audit.ADVICE_WORDS`, which is scanned rather
# than trusted. What a reader does with the pair is outside this codebase.

def at_the_line_side_words(market: str, line: float | None,
                           home: str | None = None) -> str:
    """The proposition a claim is about, said out loud."""
    who = home or "the home side"
    if market == "moneyline" or line is None:
        return f"{who} winning"
    if market == "total":
        return f"more than {_number(line)} points scored"
    return f"{who} covering {_signed(line)}"


def at_the_line_line(market: str, line: float | None, model_prob: float,
                     venue_implied: float, n: int, *, home: str | None = None) -> str:
    """One claim as a sentence: what the model's margin forecast says about the
    venue's number, what the price says about it, and how many have settled.

    THE SENTENCE NAMES WHICH FORECAST IT IS, and that is not a flourish. A pick
    card already carries a percentage -- the fitted model's answer to the
    question the model chose -- and this is a DIFFERENT calculation: the frozen
    distribution of the margin, read at a number the venue chose. On a card
    where the two numbers sit inches apart and disagree, an unlabelled second
    percentage reads as a contradiction rather than as a second reading, which
    was visible the first time this line was rendered.
    """
    what = at_the_line_side_words(market, line, home)
    forecast = "total" if market == "total" else "margin"
    # A CLAIM PRICED ACROSS TWO CONTRACTS (pick-number step A, 2026-09-30):
    # its price is about another line than `line`, so the sentence states the
    # model's number at its own line and no price beside it, and says why.
    if venue_implied is None:
        return (f"from the model's {forecast} forecast, {what} is a "
                f"{round(model_prob * 100)}% chance; "
                f"{ACROSS_TWO_CONTRACTS_WORDS[0].lower()}"
                f"{ACROSS_TWO_CONTRACTS_WORDS[1:-1]}; {n} settled so far")
    return (f"from the model's {forecast} forecast, {what} is a "
            f"{round(model_prob * 100)}% chance; the venue's price implies "
            f"{round(venue_implied * 100)}%; {n} settled so far")


def at_the_line_gate_line(n: int, gate: int) -> str:
    """The gate, in the shape LAW 4 asks for: the count, then what is missing."""
    if n >= gate:
        return f"{n} settled comparisons, past the {gate} this record needs"
    return (f"{n} of {gate} settled comparisons · {gate - n} more before any "
            f"figure here is shown at all")


def at_the_line_pace_line(n: int, gate: int, expected: int | None,
                          ends: str | None, *,
                          written_before: bool = False) -> str:
    """When the at-the-line gate opens at the rate claims are being written.

    ONE FORECASTER'S PACE (item 6, 2026-09-26): each line sits in a row that
    names its forecaster, and "no claim ... in this market" under the
    reasoning pass's row would contradict the statistical row above it,
    which has claims. It says whose claims it means.

    AND WHEN (the prover of item 6, 2026-09-26). `n` counts every settled
    bet, whatever its season, and the pace only this season's, so a
    forecaster whose claims were all written in an earlier season read
    "2 of 100 · no claim from this forecaster has been written in this
    market yet" -- a count and its denial in one sentence (the browser
    world, whose games are last season's). `written_before` says a claim
    exists from an earlier season, and the line then says "this season".
    """
    if expected is None:
        when = "this season" if written_before else "yet"
        return (f"{n} of {gate} · no claim from this forecaster has been "
                f"written in this market {when}, so there is no rate to "
                f"project from")
    ends_words = date_words_from_iso(ends) if ends else None
    tail = f" · season ends {ends_words}" if ends_words else ""
    if expected >= gate:
        return f"{n} of {gate} · ~{expected} expected{tail}"
    return (f"{n} of {gate} · ~{expected} expected{tail} · THIS GATE CANNOT "
            f"CLEAR THIS SEASON")


def at_the_line_category_label(market: str, predictor: str,
                               tier: str | None = None) -> str:
    """"point spread at the venue's line, reasoning pass" -- whose curve it is.

    ONE CURVE PER FORECASTER (GRIDIRON_REPAIR item 6, 2026-09-26). The label
    named the market alone because the curve pooled both forecasters; each
    row now says whose claims it counts, in the Record page's own filter
    words, and a tier in its words for a sport that splits below the market.
    """
    parts = [f"{humanise(market)} at the venue's line"]
    if tier:
        parts.append(tier_label(tier) or "")
    parts.append(FORECASTER_FILTER_WORDS.get(predictor, predictor))
    return ", ".join(p for p in parts if p)


def _whose(predictor: str | None, tier: str | None) -> str:
    """", Fight Night, statistical" -- the tier and forecaster a line is about."""
    parts = [tier_label(tier) if tier else "",
             FORECASTER_FILTER_WORDS.get(predictor, predictor) if predictor else ""]
    return "".join(f", {p}" for p in parts if p)


def at_the_line_coverage_line(market: str, with_claim: int, n: int, *,
                              predictor: str | None = None,
                              event_tier: str | None = None,
                              across: int = 0) -> str:
    """How much of one forecaster's market could be read at the venue's line.

    WHOSE FORECASTS (item 6, 2026-09-26): one line per forecaster, and it
    names which, so two lines about one market never read as one count.

    COUNTED IN GAMES, NOT FORECASTS (the prover of item 6, 2026-09-26):
    `at_the_line.coverage` counted one bet per game, so the line said games.
    It said "forecasts" over a count of questions, and a game asked at two
    rungs read "2 of 2 forecasts" beside a curve of one comparison.

    COUNTED IN QUESTIONS (operator question 17, 2026-09-28): a bet is one
    forecaster's question, the rung included -- "Two rungs on one game are
    two questions" -- and the curve beside the line counts them so, so the
    line says questions: "games" would be false for a game asked twice.

    AND THE QUESTIONS READ ONLY ACROSS TWO CONTRACTS (operator ruling A.2,
    2026-10-05): the venue was read for them, but every claim on them was
    priced across two contracts before the fix of 30 September, and the rule
    leaves those out of every comparison with a price -- said, so the share
    does not read as the venue having quoted nothing: "...; 38 more were
    read only across two contracts before the fix of 30 September, and no
    comparison with a price counts them". WHEN is one phrase,
    `ACROSS_TWO_CONTRACTS_WHEN` (the prover, 2026-10-05: "before 30
    September" was false of the six claims written at 18:00-18:05Z that day).
    """
    what = f"{humanise(market)}{_whose(predictor, event_tier)}"
    if not n:
        return f"{what}: nothing written yet"
    share = round(with_claim / n * 100)
    line = (f"{what}: the venue's line could be read for {with_claim} of "
            f"{counted(n, 'question')} it answered ({share}%)")
    if across:
        line += (f"; {across} more {'was' if across == 1 else 'were'} read only "
                 f"across two contracts {ACROSS_TWO_CONTRACTS_WHEN}, and no "
                 f"comparison with a price counts {'it' if across == 1 else 'them'}")
    return line


# ---------------------------------------------------------------------------
# THE HYPOTHETICAL UNIT LEDGER (operator ruling D1, 2026-09-06)
# ---------------------------------------------------------------------------
#
# THE WORD "HYPOTHETICAL" IS NOT DECORATION AND IT LEADS. The ruling permits
# this figure on the condition that it is labelled one wherever it appears, so
# the label is the first word of the sentence rather than a footnote under it:
# a reader who stops after four words has still read the true part.

def paper_ledger_line(ledger: dict) -> str:
    """One market's hypothetical one-unit record, said in words.

    THE LABEL LEADS AND THE MARKET FOLLOWS IT. The ruling requires the word
    "hypothetical" wherever the figure appears, so it is the first word; the
    market comes next because three of these sentences sit under one another on
    the Record page and the first render of them said "one unit carried on each
    of 130 settled comparisons" three times over with nothing to tell a reader
    which market each one was about.
    """
    gate = ledger.get("minimum_for_a_claim")
    # AND WHOSE (item 6, 2026-09-26): one ledger per forecaster, so two
    # sentences about each market sit under one another, and the forecaster
    # follows the market in each or the pair reads as one figure said twice.
    market = humanise(ledger.get("market")) + _whose(
        ledger.get("predictor"), ledger.get("event_tier"))
    n = ledger.get("n", 0)
    if not ledger.get("renderable"):
        return (f"hypothetical, {market}, and not shown yet: {n} of {gate} "
                f"settled comparisons where the model and the price disagreed "
                f"· {ledger.get('shortfall', gate)} more before any figure here "
                f"is shown at all")
    units = ledger.get("units")
    after = ledger.get("units_after_fees")
    return (f"hypothetical, {market}: one unit carried on each of {n} settled "
            f"comparisons where the model and the price disagreed comes to "
            f"{units:+.2f} units, or {after:+.2f} after the venue's fee")


def paper_fee_line(ledger: dict) -> str:
    """Where the fee in that sentence came from, and what it is not."""
    if ledger.get("fee_verified"):
        return "the fee is the venue's published formula."
    return ("the fee is the venue's formula as this project recorded it on "
            "6 September 2026, and it has not been checked against the "
            "venue's own schedule; the page would not load that day.")


# ---------------------------------------------------------------------------
# THE SHORTLIST (THE_SHORTLIST S2, 2026-09-07)
# ---------------------------------------------------------------------------
#
# WHAT THESE SENTENCES MAY NOT SAY. A shortlist is the shape a tip sheet
# takes, and the words are the difference. There are no best bets here, no top
# plays, no locks and no value: `audit.ADVICE_WORDS` scans every one of these
# strings on the gate and a planted "top plays" proves the scan fires. The
# list says what put a question on it -- the model's own confidence, how
# complete the evidence was -- and stops.
#
# AND THE COUNT OF WHAT IS NOT ON IT IS ON THE CONTROL ITSELF. A page that
# quietly showed twenty of seventy would be lying about the record by
# omission, which is the failure this project keeps finding in its own past.

def shortlist_line(shown: int, total: int, slate_word: str, *,
                   ranked: bool = True) -> str:
    """What the reader is looking at, and what put it there.

    AN UNRANKED SLATE SAYS SO. Every row written before 7 September 2026 has no
    rank until the backfill reaches it, and those slates are shown whole, in
    the order this page has always used. Describing them as ordered by
    confidence would be a sentence about a thing that did not happen.
    """
    if not ranked:
        return (f"every question on this {slate_word}, in the order this page "
                f"has always used: these were written before the ordering was")
    if shown >= total:
        return (f"every question on this {slate_word}, ordered by how sure the "
                f"model is and how complete the evidence was")
    return (f"the {shown} clearest questions on this {slate_word}, ordered by "
            f"how sure the model is and how complete the evidence was")


def shortlist_rest_line(rest: int) -> str | None:
    """The control that reveals everything else, with its count on its face.

    None where there is nothing behind the control, so the page shows no
    control at all rather than one offering "the other 0".
    """
    if not rest:
        return None
    if rest == 1:
        return "the other one"
    return f"the other {rest}"


def shortlist_rank_line(rank: dict | None) -> str | None:
    """One pick's place in the ordering, in the reader's own terms.

    THE EDGE IS NAMED WHETHER OR NOT IT COUNTED, and the sentence says which,
    because a number shown beside a pick that a reader assumes moved the order
    is worse than no number at all.
    """
    if not rank:
        return None
    parts = [f"{round(rank['confidence'] * 100)}% of the way from a coin flip",
             f"evidence {round(rank['completeness'] * 100)}% complete"]
    if rank.get("edge") is None:
        parts.append("no line to disagree with")
    elif rank.get("edge_counted"):
        parts.append("and its market has enough settled questions for the "
                     "disagreement to count toward the order")
    else:
        parts.append(f"disagreement with the line recorded but not counted "
                     f"yet: {rank.get('edge_gate_n', 0)} of "
                     f"{rank.get('gate', 100)} settled in this market")
    return "; ".join(parts)


def ranker_gate_line(led: int, rest: int, gate: int) -> str:
    """How far the ranker's own comparison is from being able to say anything."""
    short = max(gate - led, 0) + max(gate - rest, 0)
    if not short:
        return (f"{led} settled on the shortlist against {rest} settled off it")
    return (f"{led} settled on the shortlist and {rest} off it; both sides need "
            f"{gate} before this comparison says anything")


def ranker_verdict_line(led_brier: float | None, rest_brier: float | None,
                        led_n: int, rest_n: int) -> str:
    """Whether the ordering earned its place, in the record's own vocabulary.

    A RANKER THAT DOES NOT RANK IS A FINDING, not a bug to be quietly tuned
    away. The sentence for that case is written here, in full, so that nobody
    has to decide in the moment how to describe a disappointing result.
    """
    if led_brier is None or rest_brier is None:
        return "nothing has settled on one of the two sides yet"
    if led_brier < rest_brier:
        return (f"the shortlist scored better than what it outranked "
                f"({led_brier} against {rest_brier}, lower is better), on "
                f"{led_n} and {rest_n} settled questions")
    if led_brier > rest_brier:
        return (f"THE SHORTLIST DID NOT SEPARATE: it scored {led_brier} against "
                f"{rest_brier} for the questions it outranked, lower being "
                f"better, on {led_n} and {rest_n} settled questions. The "
                f"ordering is not earning its place and the finding stands "
                f"rather than the formula being retuned to hide it")
    return (f"the two sides scored identically ({led_brier}) on {led_n} and "
            f"{rest_n} settled questions, so the ordering separated nothing")


# ---------------------------------------------------------------------------
# THE RECOMMENDATION (THE_RECOMMENDATION R2-R4, 2026-09-07)
# ---------------------------------------------------------------------------
#
# LAW 5 permits a recommendation now and the plain-words law still governs how
# it reads. No "lock", no "best bet", no confidence theatre: the line says the
# question, what the model makes it worth, what the venue is charging, what is
# left after the fee, how much, and whether anything has settled behind it.
# `audit.ADVICE_WORDS` scans these strings on every gate run.

def recommendation_line(*, words: str, fair_value: float, price: float,
                        edge_cents: float, units: float,
                        flat: bool, size_why: str | None = None,
                        own_side: str | None = None,
                        not_a_pick: str | None = None,
                        pays: float | None = None) -> str:
    """One recommendation, in the order a reader needs it.

    THE SIZE CARRIES ITS OWN REASON, and there are two different ones behind a
    flat unit: a market with nothing settled yet, and a market with plenty
    settled where the model is behind the price. Collapsing them into "no
    measured edge yet" would tell a reader the second case is waiting for data
    it already has.

    THE SIDE IT BUYS, IN ITS OWN WORDS, WITH ITS OWN NUMBERS (pick-number
    finding 4, 2026-09-30). `words` names the side the recommendation buys,
    `fair_value` is the model's number for that side and `price` what that
    side costs. Until this date the line put the claim's fixed proposition's
    number and price (the home side's, the over's) after the QUESTION's
    words and called the side bought "the yes side" or "the other side" --
    of a proposition the reader never sees: "Washington covers +1.5 -- the
    model makes it 42¢, the venue is at 38¢, and the yes side is worth
    +2.1¢", where 42% and 38¢ are Detroit -1.5's and Detroit -1.5 is what it
    bought. The caller works out the side (`views._recommendations_block`).

    `own_side` (operator question 37, ruled 2026-10-05: "headline the
    contract the recommendation buys; the model's own side named beside
    it"): where the side bought is not the one the model took, the line ends
    by naming the model's own side and its number (`own_side_words`).

    `not_a_pick` (operator ruling B, 2026-10-05; reading (d), built
    2026-10-07): a recommendation that is not a pick -- its market short of
    B.5's gate, or its edge under three points -- is stated with its numbers
    and no size, and these words say why in the size's place.
    `edge_cents` is the edge as it may be drawn (`picks.drawn_edge`).

    `pays` (the prover of ruling B, 2026-10-07: B.3, "Every pick and every
    browse row shows its payout as a multiplier beside its chance and edge",
    with reading (a)'s "the Today payload's ... recommendation lines"): what
    the side bought pays, said beside its price -- "the venue is at 52¢
    (pays 1.94x)". As built the line stated the chance, the price and the
    edge and no multiplier.
    """
    tail = not_a_pick if not_a_pick else _units_words(units, flat, size_why)
    paid = f" (pays {payout_chip_words(pays)})" if pays is not None else ""
    line = (f"{words} — the model makes it {round(fair_value * 100)}¢, the "
            f"venue is at {round(price * 100)}¢{paid}, and it is worth "
            f"{edge_cents:+.1f}¢ a contract after the fee. {tail}")
    return f"{line} {own_side}." if own_side else line


#: A FLAT SIZE IS NOT ALWAYS ONE UNIT (GRIDIRON_COMBOS C3, 2026-09-08). A
#: package below its gate is half a unit on two legs and a quarter on three,
#: and the sentence said "One flat unit" for all three sizes until the first
#: package card was rendered. The money beside it was right, which is worse:
#: the reader would have had two numbers disagreeing and no way to tell which
#: one to believe.
_FLAT_PHRASES = {1.0: "One flat unit", 0.5: "Half a flat unit",
                 0.25: "A quarter of a flat unit"}


def flat_size_phrase(units: float) -> str:
    """"One flat unit", "Half a flat unit", "A quarter of a flat unit"."""
    return _FLAT_PHRASES.get(round(float(units), 4)) or f"{units:g} of a flat unit"


def _units_words(units: float, flat: bool, size_why: str | None = None) -> str:
    if flat:
        reason = size_why or "no measured edge in this market yet"
        return f"{flat_size_phrase(units)} — {reason}."
    return f"{units:.2f} units, a quarter of Kelly and capped."


def clv_line(n: int, mean_cents: float | None, beat_share: float | None,
             minimum: int, *, unmeasured: int = 0, restated: int = 0,
             unaccounted: int = 0, before_window: int = 0, repeats: int = 0,
             since: str | None = None, first_read: str | None = None) -> str:
    """The closing-line verdict, or how far it is from arriving.

    THE FASTEST HONEST READ. A win rate needs several hundred settled questions;
    this says something at around fifty, because it compares the app's price
    against the market's own final estimate rather than against one outcome.

    AND WHAT IT DID NOT COUNT, said beside it (2026-09-23). A close with no
    later read of its own price is not a close at 0.00c, and an old close
    worked out again afterwards is not a close made at the time.

    AND FROM WHEN, AND NOT BEFORE WHEN (the operator's ruling 8 of 2026-09-23,
    2026-09-27). `since` is the day the count started again; `first_read`,
    given only while it is still to come, is the first clean read, and until
    then the line says the date and claims nothing, whatever the count.

    AND WHAT IT COUNTED ONCE (operator question 12, 2026-09-27): `repeats`
    is the later rows of this market's same-side pairs, each in no figure
    of the line because its question and side are counted once, as the
    earlier row. Said last, beside the counts they are left out of.

    ONE FORECASTER'S LINE (operator question 22, 2026-09-28): each line is
    one forecaster's, named by its label, and a repeat is that forecaster's
    own -- one distinct bet (the question, at one rung) and one side; so it
    says "this forecaster's earlier recommendation on the same question",
    where it said "an earlier recommendation on the same game", which two
    forecasters, or two rungs of one game, would also have been.
    """
    counted_from = (f" since {date_words_from_iso(since) or since}"
                    if since else "")
    if first_read is not None:
        when = date_words_from_iso(first_read) or first_read
        head = (f"{n} of {minimum}" if n < minimum else f"{n}")
        line = (f"{head} priced against a close{counted_from} · the first "
                f"clean read is {when}, and nothing is claimed before it")
    elif n < minimum:
        line = (f"{n} of {minimum} priced against a close{counted_from} · "
                f"nothing is claimed from a sample this size")
    elif mean_cents is None:
        line = (f"{n} priced against a close{counted_from}, and none of them "
                f"has a closing price")
    else:
        direction = "cheaper" if mean_cents > 0 else "richer"
        line = (f"{n} priced against a close{counted_from} · {mean_cents:+.1f}¢ "
                f"a contract on average, which is buying {direction} than the "
                f"market's own final estimate · "
                f"{round((beat_share or 0) * 100)}% beat the close")
    if before_window:
        day = date_words_from_iso(since) or since or "the repair"
        line += (f" · 1 more was written before {day}, when the count started "
                 f"again, and is not counted" if before_window == 1 else
                 f" · {before_window} more were written before {day}, when the "
                 f"count started again, and are not counted")
    if unmeasured == 1:
        line += (" · 1 more closed with no later read of its own price and is "
                 "not counted")
    elif unmeasured:
        line += (f" · {unmeasured} more closed with no later read of their own "
                 f"price and are not counted")
    if restated == 1:
        line += (" · 1 older close was worked out again afterwards and is not "
                 "counted")
    elif restated:
        line += (f" · {restated} older closes were worked out again afterwards "
                 f"and are not counted")
    if unaccounted == 1:
        line += (" · 1 more closed before 23 September on its own price and "
                 "has not been worked out again")
    elif unaccounted:
        line += (f" · {unaccounted} more closed before 23 September on their "
                 f"own price and have not been worked out again")
    if repeats == 1:
        line += (" · 1 more repeats this forecaster's earlier recommendation "
                 "on the same question and side and is counted once, as the "
                 "earlier one")
    elif repeats:
        line += (f" · {repeats} more repeat this forecaster's earlier "
                 f"recommendations on the same question and side and are "
                 f"counted once, as the earlier one")
    return line


def closing_line_label(what: str, predictor: str) -> str:
    """"total, reasoning pass", "Since the repair, statistical" -- one row of
    the closing line's panel and whose it is.

    ONE LINE PER FORECASTER (operator question 22, ruled 2026-09-28:
    "Recommendation counts split per forecaster, like every other count").
    Every row of the panel -- the window line, each market's line, the
    withdrawn and re-grade lines -- named its market or its kind alone,
    because each count held both forecasters' recommendations; each now
    says whose it counts, in the Record page's own filter words, as the
    priced and drift rows beside it do.
    """
    return f"{what}, {FORECASTER_FILTER_WORDS.get(predictor, predictor)}"


def closing_line_window_line(since: str, first_read: str, n: int, *,
                             verdict_open: bool, predictor: str) -> str:
    """The closing line's own first sentence, for one forecaster: from when
    it counts, how many of this forecaster's, and when it may first be read.

    THE OPERATOR'S RULING 8 OF 2026-09-23 (GRIDIRON_REPAIR item 8, built
    2026-09-27): "the observation window restarts on the date item 1 ships;
    the first clean CLV read is 21 days after that, not before." Said on
    every sport's Record page, including one with nothing closed yet -- the
    date is the same everywhere, and a panel that said nothing until a close
    arrived would leave the reader to guess why the older ones went.

    ONE PER FORECASTER (operator question 22, 2026-09-28): the count is one
    forecaster's, and the sentence says whose ("12 recommendations from the
    model"), where it summed both.
    """
    from datetime import date

    start = date_words_from_iso(since) or since
    when = date_words_from_iso(first_read) or first_read
    # THE GAP FROM THE DATES THEMSELVES, so the sentence cannot say 21 while
    # the dates say otherwise.
    gap = (date.fromisoformat(first_read[:10])
           - date.fromisoformat(since[:10])).days
    who = FORECASTER_WORDS.get(predictor, predictor)
    head = (f"The closing line was repaired on {start}, and its count started "
            f"again that day: {counted(n, 'recommendation')} from {who} "
            f"priced against a close since.")
    if verdict_open:
        return (f"{head} Its first clean read came on {when}, {gap} days after "
                f"the repair.")
    return (f"{head} The first clean read is {when}, {gap} days after the "
            f"repair, and nothing is claimed from it before then.")


def withdrawn_recommendations_line(n: int, reasons: list[str | None]) -> str:
    """The recommendations the closing line does not count, and why.

    OPERATOR RULING 1, 2026-09-24: withdrawn recommendations are shown "as
    withdrawn in those words, never deleted", and never counted. Said beside
    the closing line rather than inside it, with every distinct reason once,
    so a reader can see what was taken back without the record pretending it
    was never said.
    """
    said = []
    for reason in reasons:
        text = recommendation_void_reason_words(reason) if reason else ""
        if text and text not in said:
            said.append(text)
    head = ("1 recommendation withdrawn and never counted" if n == 1 else
            f"{n} recommendations withdrawn and never counted")
    return head + (": " + "; and ".join(said) if said else "")


#: WHEN THE CLAIMS PRICED ACROSS TWO CONTRACTS WERE WRITTEN, in every sentence
#: of the rule of 2026-10-05 (operator ruling A.2): until Q36.1 was released,
#: at 18:44Z on 30 September (`at_the_line.ONE_CONTRACT_FROM`). These
#: sentences first said "before 30 September" (the prover, 2026-10-05), which
#: is false of the six claims run 8464 wrote at 18:00-18:05Z that day and of
#: recs 114 and 115, priced from two of them -- the very two the closing
#: line's own row names once the 54 are voided. `audit.two_contract_words_faults`
#: holds each sentence's date to the record.
ACROSS_TWO_CONTRACTS_WHEN = "before the fix of 30 September"

#: WHY A RECOMMENDATION PRICED ACROSS TWO CONTRACTS IS LEFT OUT, in words a
#: first-time reader can follow (operator ruling A.2, 2026-10-05). The ruled
#: void reason, "priced across two contracts, Q36", carries a question's
#: number from the repair's own papers, so the page says it this way -- the
#: precedent of fit 71's withdrawal (`RULED_WITHDRAWAL_WORDS`). No colon
#: inside it (the prover, 2026-10-05): the withdrawn line puts it after one
#: of its own ("41 recommendations withdrawn and never counted: ...").
ACROSS_TWO_CONTRACTS_REASON_WORDS = (
    f"priced across two contracts {ACROSS_TWO_CONTRACTS_WHEN}, because the "
    "venue's contract naming the visiting side was read at the wrong sign, so "
    "the model's number was about one contract and the price about another")

#: The row's own label beside the closing line, with whose it is after it.
ACROSS_TWO_CONTRACTS_LABEL = "Priced across two contracts"


def recommendation_void_reason_words(reason: str | None) -> str:
    """A recommendation's withdrawal reason as the page says it: the one
    ruled on 2026-10-05 (`recommend.TWO_CONTRACTS_VOID_REASON`) in plain
    words, any other through `plain_reason`, as before."""
    from .market import recommend as _recommend

    if reason == _recommend.TWO_CONTRACTS_VOID_REASON:
        return ACROSS_TWO_CONTRACTS_REASON_WORDS
    return plain_reason(reason) if reason else ""


def across_two_contracts_recommendations_line(n: int) -> str:
    """The recommendations the closing line leaves out because each was
    priced from a claim across two contracts, and why (operator ruling A.2,
    2026-10-05: the claims are excluded "from every price comparison").
    Beside the line and never inside it, as a withdrawal is -- these are
    left out by a rule, not withdrawn: the operator voids by his own word."""
    head = ("1 recommendation was" if n == 1 else f"{n} recommendations were")
    return (f"{head} {ACROSS_TWO_CONTRACTS_REASON_WORDS}, and "
            f"{'it is' if n == 1 else 'they are'} never counted")


# "BOTH SIDES, NO POSITION" IS GONE (operator question 22, ruled 2026-09-28:
# "This reverses Q12 for 45/46: each counts once in its own forecaster's
# line, and the 'Both sides, no position' row goes"). Its sentence,
# `both_sides_recommendations_line`, stood here from 2026-09-27; recs 45 and
# 46 are two forecasters' two distinct bets, each counted in its own line,
# and nothing paints a row for them.


def regraded_recommendations_line(graded: list[tuple[float, float]]) -> str:
    """The recommendations the corrected bar would have refused, and by how
    much -- each as (return on what its side cost, the bar it was under).

    GRIDIRON_REPAIR item 4, the operator's ruling of 2026-09-23: "Re-grade
    the three recommendations it let through as 'would not have cleared'."
    In those words, beside the closing line. A LABEL, NOT A WITHDRAWAL: they
    were made, so they stay on the record and are counted where they were,
    and this says what the bar makes of them now that it divides by what the
    side taken cost rather than by the yes price.
    """
    n = len(graded)
    # TO THE HUNDREDTH: 4.97% to one place is "5.0%, under the 5%".
    figures = _joined([f"{got * 100:.2f}%" for got, _ in graded])
    bars = sorted({minimum for _, minimum in graded})
    bar = _joined([f"{minimum * 100:.0f}%" for minimum in bars])
    if n == 1:
        return (f"1 recommendation would not have cleared the bar: its edge "
                f"was measured against the yes price rather than against what "
                f"the side taken cost, and on that cost it came to {figures}, "
                f"under the {bar} asked for. It was made, so it stays on the "
                f"record and is counted where it was")
    return (f"{n} recommendations would not have cleared the bar: each edge "
            f"was measured against the yes price rather than against what the "
            f"side taken cost, and on that cost they came to {figures}, under "
            f"the {bar} asked for. They were made, so they stay on the record "
            f"and are counted where they were")


def clv_finding_line(mean_cents: float, n: int) -> str:
    """The sentence for a negative closing line, written before it is needed."""
    return (f"THE MODEL IS BUYING RICH: {mean_cents:+.1f}¢ a contract against "
            f"the close over {n} recommendations. The honest reading is that "
            f"the prices it likes are the ones the market is about to move "
            f"away from, and the finding stands rather than the engine being "
            f"quietly retuned.")


def priced_line(blind_prob: float, priced_prob: float, price: float,
                move_cents: float | None) -> str:
    """The second forecaster's number beside the first, never instead of it.

    TWO FORECASTERS, SAID OUT LOUD. The blind one answered before it could see
    a price; this one answered afterwards and read it. A page that showed only
    the second would be reporting the market's skill as the model's.
    """
    moved = ""
    if move_cents is not None and abs(move_cents) >= 1:
        way = "toward" if (move_cents > 0) == (blind_prob > price) else "away from"
        moved = (f" The price has moved {abs(move_cents):.0f}¢ {way} the blind "
                 f"forecast since.")
    return (f"Reading the price as well: {round(priced_prob * 100)}%, against "
            f"{round(blind_prob * 100)}% from the blind forecast and "
            f"{round(price * 100)}¢ at the venue.{moved}")


def priced_category_label(sport: str, market: str, predictor: str,
                          tier: str | None = None) -> str:
    """"moneyline blended with the price, reasoning pass" -- whose forecasts
    the priced rows blended, and on which card.

    ONE ROW PER FORECASTER (operator question 14, ruled 2026-09-27). The row
    named the market alone because its count pooled both forecasters' rows;
    each row now says whose forecasts it counts, in the Record page's own
    filter words, and a UFC row names its card, as the at-the-line rows do.
    The market in the words every other row of the page uses for it.
    """
    parts = [f"{market_words(sport, market)} blended with the price"]
    if tier:
        parts.append(tier_label(tier) or "")
    parts.append(FORECASTER_FILTER_WORDS.get(predictor, predictor))
    return ", ".join(p for p in parts if p)


def drift_category_label(sport: str, market: str, predictor: str,
                         tier: str | None = None) -> str:
    """"moneyline, statistical" -- whose disagreements a drift count holds, in
    which market and, for UFC, on which card.

    ONE FORECASTER'S BETS (operator question 14, ruled 2026-09-27, 2 of 3).
    The gate list named the market type alone -- "prop" for every prop type
    at once -- and nobody's forecasts; each row now names its market in the
    words the rest of the page uses, its card, and its forecaster, as the
    correction gates beside it do.
    """
    parts = [market_words(sport, market)]
    if tier:
        parts.append(tier_label(tier) or "")
    parts.append(FORECASTER_FILTER_WORDS.get(predictor, predictor))
    return ", ".join(p for p in parts if p)


def drift_line(sport: str, market: str, n: int, moved_toward: int | None,
               gate: int, disagreement: float, tier: str | None = None) -> str:
    """Where the published line went after one forecaster's disagreements in
    one market: the count below the gate, the direction past it.

    ONE PER BET (operator question 14, ruled 2026-09-27, 2 of 3). "Over 79
    games" counted a question's morning and final pass, and two rungs of one
    game, as more games; the count was then one per game (one player's line
    in one game, for a prop). A UFC line names its card, because a market's
    row on the learning panel carries one line per card and three alike
    would not say which is which.

    QUESTIONS, NOT GAMES (operator question 17, 2026-09-28): a bet is one
    forecaster's question, the rung included, so a game asked at two rungs
    is two of the count and "games" would be false; a prop's question is a
    player's line, as it was.
    """
    lead = f"{tier_label(tier)}: " if tier and tier_label(tier) else ""
    if n < gate or moved_toward is None:
        return (f"{lead}{n} of {gate} disagreements have a second look at the "
                f"line. Nothing is reported about direction until there are "
                f"enough.")
    noun = ("player lines" if market in _config.SPORT_PROP_MARKETS.get(sport, ())
            else "questions")
    return (f"{lead}When the model disagreed by {disagreement:.0%} or more, "
            f"the market moved toward it {moved_toward / n:.0%} of the time "
            f"over {n} {noun}.")


def nothing_priced_line(considered: int, uncovered: int, no_edge: int,
                        across: int = 0) -> str:
    """Why the list is empty, which is not the same question every day.

    THREE DIFFERENT REASONS AND THEY MATTER DIFFERENTLY. A slate where nothing
    is covered is a slate the engine was never allowed to price; a slate where
    prices existed and none cleared the fee is the engine working; and a slate
    with no prices at all is a data gap. A single sentence for all three would
    hide the one that needs fixing.

    AND A FOURTH (pick-number step A, 2026-09-30): a question whose stored
    claim was priced across two venue contracts before 30 September is not
    priced on this page at all, and is counted by that reason rather than
    as one that "carried a venue price and none cleared its fee".
    """
    if not considered:
        return ("Nothing priced wrong enough today. No question on this slate "
                "reached the point of being priced at all.")
    two = (f"{across} {'was' if across == 1 else 'were'} priced across two "
           f"contracts before 30 September; no single contract carries "
           f"{'its' if across == 1 else 'their'} numbers.") if across else ""
    if across and not (uncovered or no_edge):
        return f"Nothing priced wrong enough today. {two}"
    if uncovered and not no_edge:
        head = (f"Nothing priced wrong enough today. All {uncovered} of the "
                f"other questions leading this slate were in markets this engine "
                f"does not cover." if across else
                f"Nothing priced wrong enough today. All {uncovered} of the "
                f"questions leading this slate were in markets this engine "
                f"does not cover.")
        return f"{head} {two}".strip()
    parts = []
    if no_edge:
        parts.append(f"{no_edge} carried a venue price and none cleared its fee")
    if uncovered:
        parts.append(f"{uncovered} were in markets the engine does not cover")
    return (f"Nothing priced wrong enough today. " + ", and ".join(parts)
            + f". {two}").strip()


def priced_coverage_line(sport_label: str, covered: list, entries: int) -> str:
    """What the engine is allowed to price at all, and how few that is.

    NOT `coverage_line`, which already exists and means something else: how
    many of a slate's questions carried a market line. Two functions with one
    name is a shadowed definition, and this file has a scan for exactly that --
    which fired the moment these two met.
    """
    if not covered:
        return (f"{sport_label}: no market is covered yet. The venue's ladders "
                f"have not been measured enough to choose one, and an "
                f"unmeasured market is not priced.")
    named = ", ".join(humanise(m) for m in covered)
    return (f"{sport_label}: {named} — {len(covered)} of {entries} measured "
            f"markets, chosen for a narrow quote and thin trade rather than "
            f"for anything that has won.")


def taken_comparison_line(taken: int, passed: int, gate: int,
                          taken_brier: float | None,
                          passed_brier: float | None) -> str:
    """Whether the operator's own selections beat the ones he skipped.

    A QUESTION ABOUT A PERSON, NOT ABOUT THE MODEL, and the sentence keeps that
    straight: it says what his picks did, never what he should do next.
    """
    if taken_brier is None or passed_brier is None:
        return (f"{taken} taken and {passed} passed over; both sides need "
                f"{gate} settled before this comparison says anything")
    if taken_brier < passed_brier:
        return (f"the picks taken scored {taken_brier} against {passed_brier} "
                f"for the ones passed over, lower being better, on {taken} and "
                f"{passed} settled questions")
    if taken_brier > passed_brier:
        return (f"the picks taken scored {taken_brier} against {passed_brier} "
                f"for the ones passed over, lower being better, on {taken} and "
                f"{passed} settled questions: the selection did not improve on "
                f"the list it was made from")
    return (f"the two sides scored identically ({taken_brier}) on {taken} and "
            f"{passed} settled questions")


# ---------------------------------------------------------------------------
# TODAY (GRIDIRON_TODAY T1, 2026-09-07)
# ---------------------------------------------------------------------------
#
# TWO GROUPS AND THE WORDS THAT KEEP THEM APART. One clears the venue's fee;
# the other does not and says so on every row, in cents, including when the
# number is negative. The operator ruled that the list is never empty, and this
# is how that ruling is answered without the app asserting something it has not
# measured: it SHOWS a row and prints the row's true edge beside it.
#
# No sentence here may say a watched row is worth backing.
# `audit.ADVICE_WORDS` scans them all on the gate and a planting puts one in a
# watched label to prove the scan fires.

def watching_heading(n: int) -> str:
    """The line above the group that does not clear the bar."""
    if not n:
        return "Nothing else on today's slate."
    # NONE OF THEM A PICK (operator ruling B, 2026-10-05; built 2026-10-07):
    # a recommendation in a market that has not passed its gate, or under
    # three points, is watched with its numbers and says why beside it, so
    # "none of which clears the venue's fee" is no longer true of all of them.
    return (f"Watching — {n} more, none of them a pick. The number beside "
            f"each is what it is actually worth after the venue's fee.")


def clears_the_bar_heading(n: int, folded: int = 0) -> str:
    """The line above the group that does.

    `folded` is the picks the operator's payout floor keeps out of the cards.
    They CLEARED THE BAR, so a heading that says "nothing" above a fold saying
    "1 more clear the bar" is a page disagreeing with itself -- which it did,
    on the first priced slate this design was rendered against.
    """
    # THE GROUP IS THE SLATE'S PICKS (operator ruling B, 2026-10-05; built
    # 2026-10-07): three points or more after fees in a market past its
    # gate, beside the writer's own bar -- and B.4's words where there is none.
    if not n and not folded:
        return nothing_worth_taking_words()
    if not n:
        return (f"Picks — {folded} on today's slate, all of them under your "
                f"payout floor.")
    return f"Picks — {n} on today's slate."


def fee_arithmetic_line(median_price: float | None, cents: float | None) -> str:
    """What a bet at today's median price costs before anything is right.

    ON THE SAME SCREEN AS THE TEMPTATION, every day. The fee is largest at a
    coin flip, which is exactly where a disagreement looks most attractive.

    "A CONTRACT", NOT "A PICK" (the prover of operator ruling B, 2026-10-07):
    under B a pick has three points of edge after fees or more, so "a pick
    with no edge" is a thing the page says cannot exist; the sentence is
    about any contract bought at that price.
    """
    if median_price is None or cents is None:
        return ("No venue price on this slate yet, so there is no fee to "
                "quote against it.")
    return (f"At today's median venue price of {round(median_price * 100)}¢, "
            f"the fee is {cents:.1f}¢ a contract. A contract with no edge "
            f"costs that much before anything is right or wrong.")


def taken_line(n: int) -> str:
    """How many of today's rows the operator has marked as taken."""
    if not n:
        return "None marked as taken today."
    if n == 1:
        return "One marked as taken today."
    return f"{n} marked as taken today."


# ---------------------------------------------------------------------------
# WHAT THE RECORD HAS TAUGHT IT (GRIDIRON_TODAY T3, 2026-09-07)
# ---------------------------------------------------------------------------
#
# The correction and the drift measurement have been running since they were
# built and have never been on a page. The operator concluded the app did not
# learn. It does; it was simply silent about it, which is the same failure as
# a number without its N -- a reader cannot check what they cannot see.

#: WHAT A CORRECTION'S GATE COUNTS, IN WORDS (operator questions 16 and 23,
#: built 2026-09-29): each question once -- a question's morning and final
#: pass are one, two rungs of a game are two -- where it counted settled rows.
CORRECTION_GATE_NOUN = "settled questions"

#: A correction is fitted for its category whole: every prop type is one
#: category under 'prop', and UFC's cards are one. Said wherever its count
#: stands beside something narrower (a prop type's row, a card's line), so
#: nobody reads the category's count as that row's (question 31's note,
#: 2026-09-28: splitting the category would be a model change no ruling
#: names).
EVERY_PROP_TYPE = "every prop type together"
EVERY_CARD = "every card together"

#: The label's verdict as a reader says it (question 23, 2026-09-28).
FITTED_BELOW_ITS_GATE_WORDS = "fitted below its gate"


def correction_gate_progress(settled: int, minimum: int) -> dict:
    """"41 of 50 settled questions" -- one correction category's gate line,
    from its count on the key: one composition the builder writes and the
    guard reads again (operator question 16, 2026-09-29). One question
    short is "1 more settled question", never "questions" (the render of
    2026-09-29: UFC's three statistical categories stand at 49)."""
    # FROM QUESTION 32 (2026-09-29): in force only by its own dated row, once
    # measured clear of zero -- where this said "applied only where it beat
    # the rows it was not fitted on", which the weekly refit decided itself.
    out = progress(settled, minimum, noun=CORRECTION_GATE_NOUN,
                   cleared_note="fitted - in force only once its measurement "
                                "is clear of zero")
    if not out["cleared"] and out["remaining"] == 1:
        out["note"] = "1 more settled question"
    return out


def correction_scope_words(sport: str, market_type: str) -> str | None:
    """"every prop type together" for the prop category, "every card
    together" for a sport whose cards are its tiers, or None."""
    if market_type == "prop":
        return EVERY_PROP_TYPE
    if _config.event_tiers(sport):
        return EVERY_CARD
    return None


def correction_category_label(sport: str, market_type: str,
                              forecaster: str) -> str:
    """"point spread, statistical", "player props, every prop type together,
    reasoning pass", "moneyline, every card together, statistical" -- the
    category one correction is fitted for, whose it is, and what it holds.

    THE CATEGORY WHOLE, SAID (operator question 16, 2026-09-29): the gate
    named "prop, statistical" for every prop type at once, and nothing said
    UFC's cards were counted together. The forecaster is named as the
    Record page's other gate rows name it.
    """
    what = "player props" if market_type == "prop" else market_words(
        sport, market_type)
    scope = correction_scope_words(sport, market_type)
    return ", ".join(p for p in (
        what, scope, FORECASTER_FILTER_WORDS.get(forecaster, "")) if p)


def correction_below_its_gate_line(version: int, fitted_utc: str | None,
                                   count_used: int, corrected: int,
                                   gate: int) -> str:
    """"The correction fitted on Monday 21 September was fitted below its
    gate: its 56 settled forecasts are 32 questions, under the 50 it needs,
    so it can never be in force." -- a labelled fit, in words, with both its
    counts (question 23, ruled 2026-09-28). NAMED BY ITS DAY (operator
    question 19; the board merge, 2026-09-29): it said "Version 3, fitted on
    ...", and the version is the row's tooltip now; `version` is kept in the
    signature for the callers that pass it."""
    the = the_correction_words(fitted_utc)
    return (f"{the[0].upper()}{the[1:]} was {FITTED_BELOW_ITS_GATE_WORDS}: its "
            f"{count_used} settled forecasts are {corrected} questions, under "
            f"the {gate} it needs, so it can never be in force.")


#: WHAT A WITHDRAWAL'S REASON SAYS ON THE PAGE (operator question 32,
#: 2026-09-29). The reason is stored exactly as the operator ruled it; the
#: page says it in words a first-time reader can follow, since "the pre-Q32
#: rule" is a question's number in the repair's own papers and "pooled rows"
#: a term of its record. Any other reason is shown as written.
RULED_WITHDRAWAL_WORDS = (
    "it was put in force by the weekly refit under the rule before 29 "
    "September, on one comparison with no interval that counted each pass of "
    "a question separately")

#: What a correction not in force waits for, said once (question 32). THE
#: RENDER OF 2026-09-29 read "measured on the questions it was not fitted
#: on", which is false of the version itself -- it is fitted on every
#: settled forecast -- and true only of the gate's refit, which is what these
#: words now name.
NOT_IN_FORCE_WORDS = (
    "a correction is put in force only by a dated row of its own, once one "
    "fitted on the earliest four fifths of its settled questions improves the "
    "latest fifth, with a 95% interval clear of zero")


def withdrawal_reason_words(reason: str | None) -> str:
    """A withdrawal's reason as the page says it: the ruled one in plain
    words, any other as written."""
    from . import correction as _correction

    if reason == _correction.FIT_71_WITHDRAWAL_REASON:
        return RULED_WITHDRAWAL_WORDS
    return (reason or "").strip()


def correction_state_clause(state: dict | None,
                            latest: dict | None = None) -> str | None:
    """Where a category's correction stands, BY ITS OWN ROWS (operator
    question 32, ruled 2026-09-29) -- a clause the status line and the gate
    row both say:

      in force   "version 8 is in force since Tuesday 29 September: on the 260
                 settled questions before it was fitted, one fitted on the
                 earliest 208 lowered the Brier score on the latest 52 by
                 0.0052 (95% interval 0.0011 to 0.0093, clear of zero)"
      withdrawn  "version 8 has been withdrawn since Tuesday 29 September: <its
                 reason>; nothing is in force"
      fitted     "version 9, fitted on Monday 5 October on 380 settled
                 forecasts, is not in force: <what it waits for>"

    `state` is the category's latest activation row as the door returns it
    (`correction.latest_activation`), or None; `latest` its newest version
    row, named too where it is newer than the one the row is about. None
    when there is nothing fitted to speak of.

    NAMED BY THE DAY IT WAS FITTED, NOT BY ITS VERSION (operator question 19,
    ruled 2026-09-27: "internal version names only in a tooltip"; the board
    merge, 2026-09-29). Each clause said "version 8 ..." -- a number that
    tells a reader nothing and matches a stored row; it is the row's tooltip
    now (`correction_versions_tip`), and the clause names the correction by
    the day it was fitted: "the correction fitted on Monday 28 September is
    in force since ...".
    """
    from . import correction as _correction

    gate = _correction.MIN_TRAIN

    def fitted_clause(row: dict) -> str:
        when = date_words_from_iso((row.get("fitted_utc") or "")[:10])
        on = f" fitted on {when} on {row['n_train']} settled forecasts" \
            if when else f" fitted on {row['n_train']} settled forecasts"
        return f"the correction{on} is not in force: {NOT_IN_FORCE_WORDS}"

    newer = ""
    if state is not None and latest is not None \
            and latest.get("version", 0) > state["version"] \
            and latest.get("n_train", 0) >= gate:
        newer = "; " + fitted_clause(latest)
    if state is not None:
        since = date_words_from_iso((state["activated_utc"] or "")[:10])
        kind = state["activation_kind"]
        the = the_correction_words(state.get("fitted_utc"))
        if kind == "measured":
            # WHAT WAS MEASURED, TRULY (the render of 2026-09-29): the gate's
            # refit, on the questions settled before the version was fitted
            # -- the version itself was fitted on all of them.
            bets, held = state["measured_bets"], state["measured_holdout_n"]
            return (
                f"{the} is in force since {since}: on the "
                f"{bets} {CORRECTION_GATE_NOUN} before it was fitted, one "
                f"fitted on the earliest {bets - held} lowered the Brier score "
                f"on the latest {held} by {state['measured_improvement']:.4f} "
                f"(95% interval {state['diff_low']:.4f} to "
                f"{state['diff_high']:.4f}, clear of zero){newer}")
        if kind == "scratch":
            return (f"{the} is in force since {since}, "
                    f"in a test world, without a measurement{newer}")
        return (f"{the} has been withdrawn since "
                f"{since}: {withdrawal_reason_words(state['activation_reason'])}"
                f"; nothing is in force{newer}")
    if latest is not None and latest.get("n_train", 0) >= gate:
        return fitted_clause(latest)
    return None


def the_correction_words(fitted_utc: str | None) -> str:
    """"the correction fitted on Monday 28 September": a correction named in
    words, by the day it was fitted (operator question 19; the board merge,
    2026-09-29) -- its version number is the tooltip's."""
    when = date_words_from_iso((fitted_utc or "")[:10]) if fitted_utc else None
    return f"the correction fitted on {when}" if when else "the correction"


def correction_versions_tip(versions) -> str | None:
    """The tooltip carrying the correction versions a row speaks of --
    "Version 8: the correction's number within its category; ..." -- or None
    when it names none (operator question 19; the board merge, 2026-09-29)."""
    named = sorted({int(v) for v in versions if v is not None})
    if not named:
        return None
    if len(named) == 1:
        return version_tip("correction", named[0])
    listed = ", ".join(str(v) for v in named[:-1]) + f" and {named[-1]}"
    return f"Versions {listed}: {VERSION_KIND_WORDS['correction']}."


def correction_state_line(state: dict | None,
                          latest: dict | None = None) -> str | None:
    """The state clause as a sentence of its own, for the Record page's gate
    row (question 32, 2026-09-29)."""
    clause = correction_state_clause(state, latest)
    if not clause:
        return None
    return clause[0].upper() + clause[1:] + "."


def correction_status_line(fitted: bool, n: int, minimum: int,
                           fitted_utc: str | None, active: bool,
                           last_refit: str | None = None,
                           n_train: int = 0, *,
                           below_its_gate: dict | None = None,
                           scope: str | None = None,
                           state: dict | None = None,
                           latest: dict | None = None) -> str:
    """Where one category's correction stands.

    FOUR STATES AND THEY ARE DIFFERENT FACTS. Below the threshold; past it but
    never fitted because the refit has not run since; fitted and deliberately
    inert; and in force. The first version of this sentence collapsed the
    second into the first and printed "not yet fitted: 52 of 50 settled rows,
    0 more before a correction is calculated" -- which reads as a
    contradiction, because it is one.

    ON QUESTION 17'S KEY (operator questions 16 and 23, built 2026-09-29):
    `n` is the category's settled QUESTIONS, the count its gate reads, and a
    fit is described by the settled forecasts it was fitted on (its own
    `n_train`, as written). A fit exists whatever the count now says, so a
    fitted one is never "not yet fitted" (it was, on 28 September, for UFC's
    fits of 85 forecasts beside 49 questions). A FIFTH STATE: a fit labelled
    "fitted below its gate" (`below_its_gate`, the label as written), which
    can never be in force. `scope` names a category wider than its row
    ("every prop type together").

    AND FROM QUESTION 32 (ruled 2026-09-29), IN FORCE OR WITHDRAWN BY ITS OWN
    ROW: `state` is the category's latest activation row, as the door returns
    it (`correction.latest_activation`), and `latest` its newest version. In
    force, the line says since when and on what measurement, with its
    interval; withdrawn, since when and why; fitted and never activated, that
    it is not in force and what it waits for. "In force since" the day it was
    FITTED, as this said until then, was true only because the weekly refit
    put a fit in force itself.
    """
    when = date_words_from_iso((fitted_utc or "")[:10]) if fitted_utc else None
    wide = f", {scope}" if scope else ""
    count = (f"{n} {CORRECTION_GATE_NOUN}{wide}" if n >= minimum else
             f"{n} of {minimum} {CORRECTION_GATE_NOUN}{wide}")
    if below_its_gate:
        # NAMED BY ITS DAY, its version in the row's tooltip (operator
        # question 19; the board merge, 2026-09-29).
        labelled = the_correction_words(
            below_its_gate.get("fitted_utc") or fitted_utc)
        return (f"{count}; {labelled} was "
                f"{FITTED_BELOW_ITS_GATE_WORDS}: its "
                f"{below_its_gate['count_used']} settled forecasts are "
                f"{below_its_gate['corrected_count']} questions, under the "
                f"{below_its_gate['gate']} it needs, so it can never be in "
                f"force")
    if state is not None:
        return f"{count}; {correction_state_clause(state, latest)}"
    if not fitted or n_train < minimum:
        if n < minimum:
            short = minimum - n
            return (f"not yet fitted: {count}, {short} more before a "
                    f"correction is calculated at all")
        ran = date_words_from_iso((last_refit or "")[:10]) if last_refit else None
        return (f"eligible and not yet fitted: {count}, past the {minimum} a "
                f"fit needs" + (f", and the refit last ran on {ran}" if ran else ""))
    if not active:
        # THE SAME CLAUSE THE GATE ROW SAYS, where the newest version is given
        # (question 32, 2026-09-29): one wording of one state.
        clause = correction_state_clause(None, latest) if latest else None
        if clause:
            return f"{count}; {clause}"
        return (f"{count}; fitted{' on ' + when if when else ''} on {n_train} "
                f"settled forecasts, and not in force: {NOT_IN_FORCE_WORDS}")
    # IN FORCE WITH NO ROW TO SAY SINCE WHEN: a caller that did not pass the
    # door's row. The day it was fitted is not the day it came into force
    # (question 32), so no day is said.
    return (f"{count}; in force, fitted{' on ' + when if when else ''} on "
            f"{n_train} settled forecasts")


def correction_meaning_line(claim: float, corrected: float) -> str:
    """The number first, then the words, for one worked example.

    A slope and an intercept mean nothing to a reader; what they do to a
    seventy-per-cent claim means everything.
    """
    if abs(corrected - claim) < 0.005:
        return (f"a {round(claim * 100)}% claim is published unchanged at "
                f"{round(corrected * 100)}%")
    direction = "lower" if corrected < claim else "higher"
    return (f"claims near {round(claim * 100)}% have been worth about "
            f"{round(corrected * 100)}% on this record, so they are now "
            f"published {direction}")


def correction_never_rewrites_line() -> str:
    """The property a reader must not have to infer."""
    return ("A correction changes what gets written next and never what was "
            "written before: every prediction keeps the number it was made "
            "with, which is why the record can still be checked.")


# A ROW WITH `n_train` BELOW THE THRESHOLD IS A PLACEHOLDER, not a fit: it
# records that the category had nothing to fit when the refit last ran. Calling
# it a fit would tell a reader the model has learned something it has not, and
# the difference is visible only in that column.


# ---------------------------------------------------------------------------
# THE DAY'S FACE (GRIDIRON_CARD_FACE, 2026-09-07)
# ---------------------------------------------------------------------------
#
# A sportsbook page is two things wearing one skin. Its GRAMMAR -- an event
# header, the market underneath, prices side by side, a running list of what
# you took -- is good information design for this content and is why the
# operator can already read one. Its PRESSURE -- a countdown, a price that
# flashes when it moves, a "hot" badge, a parlay builder -- exists to make
# wagering feel urgent.
#
# This screen takes the grammar. The pressure is banned by name in
# `audit.PRESSURE_WORDS`, a planting proves the scan fires, and no element on
# the page is allowed to animate when a price changes.


def day_strip_words(*, day_words: str | None, slate_words: str | None,
                    clears: int, watching: int, below_floor: int,
                    floor: float | None, forecaster: str | None = None,
                    live: int = 0, settled: int = 0) -> dict:
    """The whole day in one strip, so nothing below it has to be read first.

    THE PAGE DID NOT SAY WHAT KIND OF DAY IT WAS. Today sat 916 pixels down a
    desktop screen and 1,533 down a phone, under the filters and the hero, and
    a reader had to get there and read thirty rows to learn the answer was
    "nothing yet". Measured on 2026-09-07, before this existed.
    """
    where = " · ".join(part for part in (day_words, slate_words) if part)
    # THE COUNT IS OF PICKS THAT CLEAR THE BAR, folded ones included. A pick
    # under the operator's payout floor cleared both conditions and is on the
    # record; the floor decided only that it is a line rather than a card.
    # Counting it as "nothing" would make a display preference look like a
    # rule about bets, which is the distinction F2b exists to keep.
    # WHOSE QUESTIONS ARE BEING COUNTED. The page shows one forecaster at a
    # time, because two forecasters answering one question are two claims and
    # not two picks; the record holds both. On the first slate that produced
    # recommendations the table held six and this line said four, and a reader
    # had no way to tell that the difference was a filter rather than an
    # error.
    who = FORECASTER_WORDS.get(forecaster or "", "")
    total = clears + below_floor
    # A PICK IS B'S (operator ruling B, 2026-10-05; built 2026-10-07): the
    # count is of picks -- three points after fees, in a market past its gate
    # -- and it said "picks that clear the bar" of the writer's bar alone,
    # which an ungated market's recommendation cleared.
    if not total:
        count = f"{who} has no pick" if who else "no pick"
    elif total == 1:
        count = f"{who} has 1 pick" if who else "1 pick"
    else:
        count = f"{who} has {total} picks" if who else f"{total} picks"
    parts = [count]
    if below_floor:
        floor_words = f"{floor:g}x" if floor else "your floor"
        parts.append(f"{below_floor} of them below your {floor_words} floor")
    parts.append(f"{counted(watching, 'question')} watched")
    # THE STRIP COUNTS ALL THREE STATES (THREE_STATES S4, 2026-09-08), and
    # each one only when there is something in it: "0 live" on a morning is a
    # zero a reader has to parse, and the absence says it faster.
    if live:
        parts.append(f"{live} live")
    if settled:
        parts.append(f"{settled} settled")
    return {"where": where, "counts": " · ".join(parts)}


def first_price_words(hours: float, *, some_started: bool = False) -> str:
    """When a venue price is expected, on a slate that has none yet.

    A reader who is told "no price yet" five times learns that the app is
    stuck. A reader told when the price arrives learns how the app works.

    AND ONLY OF THE GAMES STILL TO COME (operator question 38, ruling 2,
    2026-10-07): nothing on a game that has started is priced any more, so
    on a slate where some games have started the sentence is about the rest
    -- "no venue price on this slate yet" was false of games that were
    priced before they started.
    """
    if some_started:
        return (f"No venue price yet for the games on this slate still to "
                f"come. The first is taken about {hours:g} hours before each "
                f"game starts.")
    return (f"No venue price on this slate yet. The first is taken about "
            f"{hours:g} hours before each game starts.")


def slate_started_words() -> str:
    """The day strip's note on a slate none of whose games is still to come
    (operator question 38, ruling 2, 2026-10-07): nothing on a game that is
    not still to come is priced, so the strip says why it shows no price,
    never "no venue price yet" -- which would be false of games that were
    priced before they began.

    NOT "EVERY GAME HAS STARTED" (Q38's prover, 2026-10-07), which it said
    as first built: a game still listed as to come past its listed start --
    postponed, cancelled or a stale listing, which the record cannot tell
    apart; four UFC bouts on the record that day -- is not still to come and
    may never have started, and the board draws it as listed, to come at a
    time already gone. So the words name the ruling's three ways a game is
    not still to come, each true of such a slate."""
    return ("Every game on this slate is under way, over, or past its listed "
            "start, so nothing on it is priced any more.")


def past_its_start_price_words() -> str:
    """The board's price slot on a row drawn as still to come -- its game
    still listed 'scheduled' -- whose game is past its start (Q38's prover,
    2026-10-07; operator question 38, ruling 2: nothing on a game that is not
    still upcoming is priced, and anything that reports what was refused
    names it). The slot said "venue has not listed this yet" there, which is
    false of a game the venue listed and that was priced before its start:
    every NFL, NBA and UFC game being played, which no live poll follows and
    whose status stays 'scheduled' until a loader writes the result. Not "no
    longer priced": four UFC bouts still listed past their starts on the
    record that day were never priced at all."""
    return "past its start, so not priced"


def past_its_start_price_tip() -> str:
    """The tooltip beside `past_its_start_price_words`."""
    return ("This game is past its start: under way, over, or past its "
            "listed start. Nothing on a game that is not still to come is "
            "priced, and no venue read taken at or after its start is a "
            "price for it.")


#: The markets the venue is actually asked about. Everything else in
#: `config.SPORT_MARKETS` is forecast and never priced here, and the chip says
#: which of those two silences it is looking at.
MARKETS_READ_AT_THE_VENUE = frozenset({"spread", "total", "moneyline"})


def no_price_words(market: str | None = None) -> str:
    """What the venue chip says when there is nothing to put in it.

    THREE DIFFERENT SILENCES, and until 2026-09-09 all three said "no price
    yet", which is why the operator read it as a broken app:

      * THE VENUE WAS ASKED AND HAS NOTHING. Now that the slate is read
        daily, this is a real answer and it is said in the operator's own
        words: "venue has not listed this yet".
      * NOBODY ASKED. Every prop market: `capture_for_predictions` excludes
        `market_type = 'prop'`, because matching our player and our rung to
        the venue's ticker is a crosswalk that does not exist. Saying "the
        venue has not listed this" there would be a falsehood on the card --
        `KXNFLREC-26SEP09NESEA` was open with seventy-one contracts on it on
        the morning this was written.
      * The near-start read has not happened yet, which the day strip says at
        the top of the page rather than forty times down it.
    """
    if market is not None and market not in MARKETS_READ_AT_THE_VENUE:
        return "not read at the venue yet"
    return "venue has not listed this yet"


#: The words around the opening read's time. The INSTANT is sent as an
#: instant and the renderer turns it into the reader's clock; these are the
#: two halves that sit either side of it, so no label is invented in the
#: browser.
def opening_read_words() -> dict:
    """The line under the payout chip when the price is an opening read.

    Two facts, and neither of them is the payout: the chip above already says
    what it pays, and saying it twice is the "Payspays" defect of 2026-09-08
    wearing a different label. What a reader cannot get from the chip is WHEN
    this was read and that a closer read is coming -- without the second, an
    opening price gets compared with an edge measured at kickoff.
    """
    return {"before": "read", "after": "re-read near kickoff"}


def opening_read_elsewhere_words(contract_words: str, price: float,
                                 payout: float | None) -> str:
    """An opening read taken at ANOTHER line than the question's, naming the
    contract it is -- "North Texas +1.5 opened at 52¢ · pays 1.94x" -- where
    the venue's opening ladder lists no priced contract at the question's own
    line (pick-number step A, 2026-09-30; finding 5). The price was drawn
    bare under the question's words until then, whichever rung it was."""
    tail = f" · pays {payout:.2f}x" if payout is not None else ""
    return f"{contract_words} opened at {round(price * 100)}¢{tail}"


def opening_read_elsewhere_payout_words(contract_words: str,
                                        payout: float | None) -> str:
    """The payout chip of an opening read at another line: what it pays, and
    on which contract, since the chip alone would sit under the question."""
    if payout is None:
        return no_price_words()
    return f"{payout:.2f}x on {contract_words}"


def price_chip_words(cents: float | None) -> str:
    """The model's fair value, as a price.

    AN EM DASH, NOT "no price yet", when it is absent. The model always has a
    probability; what it lacks until a claim exists is a price for the VENUE's
    question, and those are different propositions. Printing the venue's
    sentence in the model's box said the model had no opinion, which is not
    what is true.
    """
    if cents is None:
        return "—"
    return f"{round(cents)}¢"


def venue_chip_words(price: float | None, payout: float | None,
                     market: str | None = None) -> str:
    """The price and what it returns, which are the same fact twice.

    A reader who has used a sportsbook reads a payout faster than a price, and
    a reader who has used an exchange reads the price. Both, once.

    `market` decides which SILENCE is printed when there is no price -- see
    `no_price_words`. A card that says the venue has nothing must be about a
    market the venue was asked.
    """
    if price is None:
        return no_price_words(market)
    if payout is None:
        return f"{round(price * 100)}¢"
    return f"{round(price * 100)}¢ · pays {payout:.2f}x"


def edge_chip_words(edge_cents: float | None) -> str:
    """THE NUMBER THE EYE LANDS ON, signed, or an em dash when unpriced.

    The dash is not a zero and not a failure. It is "this has not been priced
    yet", and the strip at the top of the page has already said why.
    """
    if edge_cents is None:
        return "—"
    return f"{edge_cents:+.1f}¢"


def edge_label_words(base: str, side: str | None) -> str:
    """The edge chip's label, saying which side of the question it is on.

    A QUESTION, A PLUS SIGN AND A GREEN NUMBER ALL READ AS "BACK THIS", and on
    a card whose edge sits on the other side that is three things agreeing
    with each other and being wrong. Measured on a scratch render: "Carolina
    covers -2.5", model 52¢, venue 60¢, edge +6.0¢ -- where the model's
    disagreement is with the price of Carolina covering, not with Carolina.
    """
    if side == "no":
        return f"{base}, on the other side"
    return base


def edge_state(edge_cents: float | None) -> str:
    """Which of three states the edge chip is in. COLOUR IS DECIDED HERE.

    The renderer applies a class and never picks a colour, so the one place
    that decides what green means is this function.
    """
    if edge_cents is None:
        return "none"
    return "up" if edge_cents > 0 else ("down" if edge_cents < 0 else "flat")


def size_words(*, units: float, flat: bool, why: str | None,
               unit_dollars: float | None) -> str:
    """The size, in the operator's money when he has told the app what a unit
    is worth, and in units when he has not.

    NOTHING HERE IS A BALANCE. The figure is the declared unit multiplied by a
    number he typed on the settings page; no venue account is read, and the
    app has no idea what he actually has.
    """
    if unit_dollars:
        amount = units * unit_dollars
        money = f"${amount:,.0f}" if abs(amount - round(amount)) < 0.005 else f"${amount:,.2f}"
        if flat:
            return (f"{money} · {flat_size_phrase(units).lower()}, "
                    f"{why or 'no measured edge in this market yet'}")
        return f"{money} · {units:.2f} units, a quarter of Kelly and capped"
    return _units_words(units, flat, why)


def gate_status_words(n: int, minimum: int) -> str:
    """Where this market stands against LAW 4's hundred, in words.

    "52 settled" alone tells a reader nothing about whether that is a lot.
    """
    if n >= minimum:
        return f"{n} settled · past the {minimum} this app asks for"
    return f"{n} settled · {minimum - n} more before a verdict"


def below_floor_words(n: int, floor: float) -> str:
    """The fold. Says what is behind it and whose rule put it there."""
    return (f"{n} more clear the bar and pay under your {floor:g}x floor")


def taken_today_heading(n: int) -> str:
    """The running list's own heading. Never the word "slip"."""
    if not n:
        return "Taken today · nothing marked yet"
    # MARKED, NOT "PICKS" (operator ruling B, 2026-10-05; built 2026-10-07):
    # what the operator took is a question he marked, and B calls a leg a
    # pick only at three points after fees -- the heading counted every tap
    # as one.
    return f"Taken today · {n} marked"


def taken_entry_words(question: str, edge_cents: float | None, *,
                      across: bool = False, own_side: str | None = None) -> str:
    """One line in the running list: what it was, and what it was worth then.

    THE EDGE IS FROZEN AT THE TAP. A number that moved afterwards would make
    the list a scoreboard, and this is a record of what was chosen.

    `question` names the contract the edge belongs to (pick-number step A,
    2026-09-30), and an edge worked out across two contracts is not stated
    (`across`): no single contract carries it.

    `own_side` (operator question 37, ruled 2026-10-05): `question` names the
    contract the recommendation bought, and where that is the other side of
    the one the model took, the model's own side and number follow it.
    """
    if across:
        return f"{question} · {across_two_contracts_price_words()} carries its edge"
    if edge_cents is None:
        said = f"{question} · no price recorded at the time"
    else:
        said = f"{question} · {edge_cents:+.1f}¢ when marked"
    return f"{said} — {own_side}" if own_side else said


def worked_example_caption(phrase: str | None, shown_prob: float | None) -> str:
    """"— Miami to win, 60%": which pick the worked example is working.

    COMPOSED HERE FROM 2026-09-07, because it was composed in the renderer
    before that -- a dash, a space, a subject, a comma and a percentage, glued
    together in JavaScript, which is the shape the prose ruling exists to
    prevent.
    """
    what = phrase or "this pick"
    if shown_prob is None:
        return f"— {what}"
    return f"— {what}, {round(shown_prob * 100)}%"


def price_row_labels() -> dict:
    """What sits above each of the three prices.

    "Edge after fees" and not "Edge": the fee is the difference between a
    number that looks like an edge and a number that is one, and a reader who
    has to remember which of the two this is will eventually remember wrong.
    """
    return {
        "model": "Model",
        # THE VENUE BOX IS THE PAYOUT NOW (2026-09-08), with the price beneath
        # it, so its label says what the number is rather than whose it is.
        "venue": "Pays",
        "edge": "Edge after fees",
        "why": "Why",
        "took": "I took this",
        "taken": "taken",
        # The two tabs on Picks. A card is born on the first and moves to the
        # second when its game starts.
        "tab_upcoming": "Upcoming",
        "tab_live": "Live",
    }


def kickoff_label_words() -> str:
    """The word beside a start time. NOT A COUNTDOWN.

    The page used to tick "first kickoff in 2d 6h" once a minute. A countdown
    is the sportsbook's pressure rather than its grammar: it makes a time feel
    like a deadline, and the operator ruled it out by name. The instant is
    still rendered in the reader's own clock, because that is a fact about
    when the game is.
    """
    return "starts"


# ---------------------------------------------------------------------------
# THREE STATES (GRIDIRON_THREE_STATES, 2026-09-08)
# ---------------------------------------------------------------------------
#
# One card, three states, and the state is a fact about the game rather than a
# tab somebody chose. Everything below is the words each state needs; the
# arithmetic and the colour are elsewhere.


def score_line_words(away: str, away_score, home: str, home_score) -> str:
    """"DET 3 - MIN 2". The score, in the order the matchup is written."""
    if away_score is None or home_score is None:
        return f"{away} at {home}"
    return f"{away} {int(away_score)} – {home} {int(home_score)}"


def period_words(sport: str, period: str | None, clock: str | None) -> str:
    """Where the game is, in the sport's own vocabulary.

    THE SOURCE ALREADY SPEAKS IT. Baseball's feed says "Top 6th" and
    football's says "2nd Quarter" with a clock; neither is improved by this
    project inventing a house style for it, and inventing one is how a page
    starts saying "period 6" about a baseball game.
    """
    parts = [part for part in (period, clock) if part]
    return " · ".join(parts) if parts else "under way"


def polled_words(seen_utc: str | None, now_utc: str | None = None) -> str:
    """When the score was last read, so a stale one is visible as stale.

    A SCORE WITH NO TIME ON IT IS A SCORE A READER TRUSTS TOO MUCH. The poller
    runs every ninety seconds while a window is open and not at all otherwise,
    so a card can sit with a number that stopped being true an hour ago.
    """
    if not seen_utc:
        return "no score has been read yet"
    if not now_utc:
        return "read at " + seen_utc[11:16] + " UTC"
    try:
        from datetime import datetime

        fmt = "%Y-%m-%dT%H:%M:%SZ"
        gap = (datetime.strptime(now_utc, fmt)
               - datetime.strptime(seen_utc, fmt)).total_seconds() / 60.0
    except (TypeError, ValueError):
        return "read at " + seen_utc[11:16] + " UTC"
    if gap < 2:
        return "read just now"
    if gap < 60:
        return f"read {round(gap)} minutes ago"
    hours = gap / 60.0
    return f"read {round(hours)} hours ago"


def live_empty_words(first_kickoff_utc: str | None) -> str:
    """The Live tab on a day with nothing on it yet.

    A TAB THAT SAYS NOTHING IS A TAB THAT LOOKS BROKEN. It says what it is
    waiting for; the time itself is rendered in the reader's own clock beside
    it, because the browser is the only party that knows the timezone.
    """
    if not first_kickoff_utc:
        return "Nothing is being played, and nothing on this slate has a start time yet."
    return "Nothing is being played. The first game starts"


def taken_badge_words() -> str:
    """What marks a game the operator has money on. NOT whether it is winning.

    He declined that on 2026-09-08 and the reasoning stands: a running verdict
    on his own pick is the feature that makes a person watch the app instead
    of the game.
    """
    return "Yours"


def state_heading_words(state: str, n: int) -> str:
    """The heading over a group of cards in one state."""
    if state == "live":
        if not n:
            return "Nothing is being played"
        # QUESTIONS, NOT GAMES. One game carries several of them -- a winner,
        # a run line, a total, a strikeout prop -- and calling four cards
        # "four games" is a count of the wrong thing, on the tab whose whole
        # job is saying what is on.
        return f"In progress — {counted(n, 'question')}"
    if state == "final":
        return f"Settled — {counted(n, 'question')}"
    if state == "combos":
        # THE VENUE'S WORD, AND ONLY HERE. "combo" left the pressure list on
        # 2026-09-08 because it is the product's name; "parlay" did not.
        if not n:
            return "Combos"
        return f"Combos — {counted(n, 'package')}"
    return f"Upcoming — {counted(n, 'question')}"


def payout_chip_words(payout: float | None,
                      market: str | None = None) -> str:
    """THE BIGGEST NUMBER ON THE CARD from 2026-09-08, by operator ruling.

    A payout is what a reader of a sportsbook reads first, and it is the one
    number on the card that says what the bet is FOR rather than what it is
    worth. The edge moved to a quiet line beneath; the group heading is what
    says whether a card clears the bar.
    """
    if payout is None:
        return no_price_words(market)
    # THE LABEL ABOVE IT ALREADY SAYS "Pays" (`price_row_labels`), and this
    # said it again: the first card ever rendered with a real payout read
    # "Payspays 3.33x". Found on 2026-09-08 by rendering a package card,
    # and it was true of the single card too -- no pick on the live slate had
    # a price on the day the chip was built, so nobody had seen either.
    return f"{payout:.2f}x"


def price_under_payout_words(price: float | None) -> str:
    """The price, small, beneath the payout it produces."""
    if price is None:
        return ""
    return f"{round(price * 100)}¢ a contract"


def edge_line_words(edge_cents: float | None, other_side: bool = False) -> str:
    """The edge, on its own quiet line under the price row.

    STILL SIGNED AND STILL COLOURED, because it is the number that ranks a
    card; it is simply no longer the number that shouts. Green and red stay
    on it and nowhere else, so the club colours the card gained on 2026-09-08
    cannot be mistaken for a verdict.
    """
    if edge_cents is None:
        return "no price to compare against yet"
    # THE LABEL ABOVE IT ALREADY SAYS "Edge after fees" and, when it applies,
    # "on the other side" (`edge_label_words`). This said both again: the first
    # package card rendered read "EDGE AFTER FEES +9.0¢ after fees", and the
    # single card had read the same since the label was added. Found by
    # NIGHT_AUDIT item 6, 2026-09-08, as a sibling of the payout chip's
    # "Payspays". `other_side` is kept in the signature so the one caller
    # that passes it keeps compiling; the label is where the words live.
    del other_side
    return f"{edge_cents:+.1f}¢"


def board_edge_words(edge_words: str, *, other_side: bool) -> str:
    """The edge as a board tile draws it, where the price would be: the
    Today card's quiet line, and, when the figure is the OTHER side's, the
    words its label says ("-1.5¢ on the other side").

    THE TILE HAS NO LABEL ABOVE IT (the prover of pick-number step C,
    2026-09-30). The Today card puts "on the other side" in the label over
    the figure (`edge_label_words`) and keeps the figure bare; the board
    merge drew the bare figure alone, beside the question's words and the
    question side's chance, so the other side's worth read as the question's.
    The label's own words, after the figure, since there is no label.
    """
    if other_side:
        return f"{edge_words} on the other side"
    return edge_words


def starter_words(name: str | None) -> str:
    """Who is starting, or that nobody has said.

    ABSENT IS NOT ZERO, and it is not an em dash either: "starter not named"
    is a fact about the day, and a reader who sees it knows the slate is early
    rather than that the app is broken.
    """
    return name if name else "starter not named"


def form_words(results: list[str]) -> str:
    """The last five, most recent first: "W W L W L".

    FROM THE RECORD'S OWN FINISHED GAMES, not from a factor. `recent_form_diff`
    is a margin difference over four games and is a different thing; this is
    what a reader means by form, and the card says which it is.
    """
    if not results:
        return "no finished games yet"
    return " ".join(results[:5])


def weather_words(temp_f, wind_mph, precip_pct) -> str | None:
    """The forecast a factor already read, in a reader's units.

    None where nothing was fetched, which is most games: the weather pass runs
    for outdoor football and nothing else, and a card that invented a mild day
    for a domed stadium would be inventing a factor input.
    """
    parts = []
    if temp_f is not None:
        parts.append(f"{round(float(temp_f))}°F")
    if wind_mph is not None:
        parts.append(f"wind {round(float(wind_mph))} mph")
    if precip_pct is not None:
        parts.append(f"{round(float(precip_pct))}% rain")
    return " · ".join(parts) if parts else None


def settled_outcome_words(shown_prob: float | None, outcome: int | None,
                          question: str) -> str:
    """The loop closed on the same card that opened it.

    "The model had this at 66% and it happened." A verdict a reader can check
    against the number they were shown, which is the whole argument for
    keeping one card through three states.
    """
    if outcome is None:
        return "not settled yet"
    if shown_prob is None:
        return "it happened" if outcome else "it did not happen"
    said = f"the model had this at {round(shown_prob * 100)}%"
    return f"{said} and it happened" if outcome else f"{said} and it did not"


# ---------------------------------------------------------------------------
# THE VENUE'S PACKAGES (GRIDIRON_COMBOS, 2026-09-08)
# ---------------------------------------------------------------------------
#
# The heading is the feature on most days. It says what the venue offered and
# what this project could do with it, and on the day this shipped it said that
# nothing the venue had open was priceable here.


#: WHY THE CARD SHOWS NO PRICE, and it is not a gap (ruled 2026-09-09). The
#: venue builds a combo to an account holder's order and quotes it back to
#: that account on request. The public interface carries only prepackaged
#: series, so there is no combo price this app can ever read: asking would
#: require an account, which LAW 5 forbids and marks not amendable.
#:
#: So the app does the half it can do honestly -- what the combo is worth --
#: and the operator does the half only he can do, which is reading the quote
#: on his own screen.
COMBO_RFQ_SENTENCE = (
    "The venue quotes combos to your account on request. This app cannot ask, "
    "so it shows what a combo is worth and you compare.")


def pregame_words(probability: float | None) -> str | None:
    """What the model thought BEFORE the game started (ruled 2026-09-09).

    THE WORD IS THE POINT. A percentage beside a live score reads as the
    model's opinion of the game in front of you, and there is no such
    opinion: no live model exists here -- THREE_STATES S5 is unbuilt -- and
    this figure is the corrected probability the claim was written with,
    hours ago, against a game that had not started.

    LAW 5 permits exactly this and no more: "Live win probability may be
    displayed and is never sized." The card carries no price, no edge, no
    size and no tier chip beside it, and `audit.live_card_faults` fails by
    name on any of them.
    """
    if probability is None:
        return None
    return f"pregame {round(float(probability) * 100)}%"


def combo_group_heading(sport_label: str) -> str:
    """"MLB combos", per sport, because a combo never crosses one (LAW 6).

    The heading names the sport for the same reason every other figure in this
    record does: two sports in one product would describe neither, and a
    reader glancing at a list called "Combos" cannot tell whether the two legs
    came from the same game of the same sport or from two different ones.
    """
    return f"{sport_label} combos"


def combo_none_clear_words(sport_label: str) -> str:
    """No two picks cleared the bar in this sport today.

    IN THESE WORDS, ruled 2026-09-09, because they say what a combo IS: two
    picks, one sport, each good enough on its own. "No package open" described
    the venue's shelf and was wrong twice over -- the shelf is not where these
    come from, and the builder exists whether or not anything is on it.
    """
    return f"no two {sport_label} picks clear the bar today"


def combo_ceiling_words(ceiling_cents: int | None) -> str:
    """The highest price worth paying, in the operator's own words.

    THE ONLY NUMBER ON THE CARD THAT IS A DECISION. There is no venue price to
    compare against and no edge to print, so the card carries what the combo
    is worth and the line beneath it that turns that into an answer: pay less
    than this or do not take it.
    """
    if ceiling_cents is None:
        return "not worth taking at any price"
    return f"worth taking only below {ceiling_cents}\u00a2"


def combo_unmeasurable_words() -> str:
    """Why this product has no record and never will (C4 withdrawn, 2026-09-09).

    Said on the card rather than in a document, because a reader who has been
    told every other number carries its sample size will look for one here.
    """
    return ("This app never sees the price you were quoted, so a combo's "
            "result cannot be scored. No record is kept and none is claimed.")


def combo_heading_words(priced: int, refused: dict, sports_without: list) -> str:
    """"1 priced · 2 same-game, not priceable · none for baseball"."""
    from .market import combos

    parts = []
    parts.append(f"{priced} priced" if priced else "none priced")
    for reason, n in sorted((refused or {}).items()):
        if n and reason in combos.UNPRICEABLE:
            parts.append(f"{n} {combos.UNPRICEABLE[reason]}")
    if sports_without:
        named = ", ".join(SPORT_LABELS.get(s, s) for s in sports_without)
        parts.append(f"none for {named}")
    return " · ".join(parts)


def combo_fee_words(ratio: float | None) -> str:
    """The cost, once, in the heading. It is the argument against the product.

    Measured 2026-09-08: 1.67 times the singles' rate per dollar on two 60c
    legs, 2.8 times on three.
    """
    if not ratio:
        return ("A package costs more per dollar than the same legs taken "
                "singly, and every card prints both.")
    return (f"The fee at package prices is about {ratio:.1f} times the "
            f"singles' rate per dollar, and every card prints both.")


# `combo_empty_words` STOOD HERE until 2026-09-09. It composed "the venue
# has no package open today in any sport this record forecasts" -- a
# sentence the ruling of that date forbids, because the venue's combo
# builder exists whether or not its public shelf does, and what is true is
# that this app cannot ask. `combo_none_clear_words` replaced it and
# describes OUR side: no two picks in this sport cleared the bar.


def combo_legs_words(legs: list) -> str:
    """The legs as the venue wrote them, joined for one line."""
    return " · ".join(legs or [])


def combo_leg_words(words: str, card: dict) -> str:
    """One leg of a proposed combo as its card names it: the words of the
    side it is picked on, then the game it is in -- "under 8.5 total runs ·
    Rays at Braves", "Chicago covers +1.5 · White Sox at Royals".

    THE PROVER OF PICK-NUMBER STEP B (2026-09-30). A proposal card draws its
    legs and nothing else -- no row, no game heading above them -- so a leg
    whose words name no club named no contract: the reasoning pass's
    baseball combos read "under 8.5 total runs + under 8.5 total runs" three
    times on the record (two games each, and a worth for both), and a leg
    naming a city two clubs share ("Chicago covers +1.5", "Los Angeles
    covers +1.5", "New York covers +1.5") left the club to be guessed. A
    worth has to stand under the words of the exact contracts it multiplies.

    THE SHAPE A PROP'S PICK LINE ALREADY HAS ("Josh Allen over 245.5 passing
    yards · Packers at Bills", the card's `matchup`). The game is the row
    title the board heads that game with, so the leg can be found on the
    page: "Rays at Braves", or "Hooker vs Parnasse" for a fight, which has no
    home side; a prop's row title is its player, so a prop takes the
    matchup. A card with neither keeps its words alone.
    """
    game = (card.get("matchup") if card.get("market_type") == "prop"
            else card.get("row_title"))
    return f"{words} · {game}" if game else words


def combo_margin_words(package_price: float | None,
                       legs_product: float | None) -> str:
    """The venue's package price beside what its own legs multiply to.

    ONE VISIBLE NUMBER instead of an inference. A package quoted above the
    product of its legs is the venue charging for the convenience; below it,
    the venue is paying for the volume.
    """
    if package_price is None or legs_product is None:
        return "no package price to compare"
    return (f"{round(package_price * 100)}¢ · its legs multiply to "
            f"{legs_product * 100:.1f}¢")


def combo_singles_words(alt: dict) -> str:
    """The same money as singles, printed on every package card."""
    if not alt or alt.get("singles_edge_cents") is None:
        return ""
    return (f"as singles: {alt['singles_edge_cents']:+.1f}¢ a leg, fee "
            f"{alt['singles_fee_share'] * 100:.1f}% · as one package: fee "
            f"{alt['combo_fee_share'] * 100:.1f}%")


# `combo_kill_words` STOOD HERE until 2026-09-09, when C4 was withdrawn.
# It read the kill verdict out in words. The verdict counted SETTLED
# packages and a combo cannot settle -- the app never sees the price the
# operator was quoted -- so the sentence described a judgement that could
# never be reached. `combo_unmeasurable_words` says the true thing.


def taken_package_entry_words(legs: str, price: float | None) -> str:
    """One package in the running list: what it was, and its price then.

    THE PRICE AS THE VENUE SHOWED IT AT THE READING THE TAP POINTS AT. A
    package has no recommendation row to take an edge from, and a number
    recomputed later would make this a scoreboard rather than a record of what
    was chosen.
    """
    if price is None:
        return f"{legs} · no price recorded at the time"
    return f"{legs} · {round(price * 100)}¢ when marked"


def taken_packages_line(took: int, offered: int, gate: int) -> str:
    """The combo line on the taken record, in the words it will be read in."""
    if not offered:
        return ("No package has been priced here yet, so there is nothing "
                "taken or passed over to compare.")
    if took < gate:
        return (f"{took} of {offered} priced packages marked. A comparison "
                f"needs {gate} settled, so this is a count and not a verdict.")
    return (f"{took} of {offered} priced packages marked, scored on their own "
            f"line and never mixed with single legs.")


def held_line_words(sport: str, markets: list[str], reason: str) -> str:
    """The day strip's line for markets held back from forecasting."""
    names = [market_words(sport, m) for m in markets]
    joined = names[0] if len(names) == 1 else (
        ", ".join(names[:-1]) + " and " + names[-1])
    return (f"{SPORT_LABELS.get(sport, sport.upper())} {joined} held, not "
            f"forecast and not shown: {reason}")


#: WHY A MARKET THE RUN ASKS WAS NOT FORECAST, in words (GRIDIRON_REPAIR item
#: 2, 2026-09-26), one per `baseline.UNTRAINED_WHY`, for one market and for
#: several. No factor set is named by its tag: "fs5" is a word nobody says.
UNTRAINED_WHY_WORDS = {
    "none_active": ("no model is in use for it",
                    "no model is in use for them"),
    "another_set": ("its model in use was fitted to another set of factors",
                    "their models in use were fitted to another set of factors"),
    "factor_not_computed": (
        "its model in use reads a factor that is no longer computed",
        "their models in use read a factor that is no longer computed"),
}


def _joined(names: list[str]) -> str:
    return names[0] if len(names) == 1 else (
        ", ".join(names[:-1]) + " and " + names[-1])


def untrained_line_words(sport: str, markets: list[dict]) -> str:
    """The day strip's line for markets a run asks and cannot answer.

    "NFL moneyline and total not forecast: no model is in use for them".
    One clause per reason, in the order the reasons are declared, so every
    market is named with the reason that stops it.
    """
    clauses = []
    for why in UNTRAINED_WHY_WORDS:
        names = [market_words(sport, m["market"]) for m in markets
                 if m.get("why") == why]
        if names:
            one, many = UNTRAINED_WHY_WORDS[why]
            clauses.append(f"{_joined(names)} not forecast: "
                           f"{one if len(names) == 1 else many}")
    return f"{SPORT_LABELS.get(sport, sport.upper())} " + "; ".join(clauses)


def untrained_run_words(sport: str, markets: list[dict], written: int) -> str:
    """Why a predict run failed, as the Health panel shows it."""
    one = len(markets) == 1
    return (f"{untrained_line_words(sport, markets)}. This run wrote "
            f"{counted(written, 'forecast')} for the markets that have a model "
            f"and is recorded as failed so the gap is seen. Every run fails "
            f"the same way until {'it has' if one else 'they have'} a model "
            f"that can answer {'it' if one else 'them'}, or "
            f"{'is' if one else 'are'} retired.")


def final_pass_answered_words(n: int) -> str:
    """Why an early pass wrote nothing for some questions, as the Health
    panel shows it (operator question 27, ruled 2026-09-28, built
    2026-09-29: "a catch-up may not run an early pass for a question whose
    final pass exists").

    "FINAL FORECAST, the one made close to the start", never "final pass":
    the panel names that task "Take one more look", and a reader is told
    what the machine did, not what the code calls it.
    """
    one = n == 1
    return (f"{counted(n, 'question')} already {'has' if one else 'have'} "
            f"{'its' if one else 'their'} final forecast, the one made close "
            f"to the start, so no early forecast was written for "
            f"{'it' if one else 'them'}; an early forecast is never written "
            f"over a final one")


def final_pass_answered_refusal(sport: str, season: int, week: int,
                                n: int) -> str:
    """The refusal an early pass raises when nothing is left for it to write
    but questions whose final pass is written (operator question 27,
    2026-09-29) -- `run.SlateAlreadyAnswered`'s words for a hand run, beside
    ruling R4's. The scheduled task writes its own line, naming the slate in
    words (`tasks._run_predict`)."""
    return (f"{sport} {season} slate {week}: nothing was left for this early "
            f"pass to write. {final_pass_answered_words(n)}, because a final "
            "forecast written before the start stands over an early one, "
            "whichever is written last. No forecast was written.")


def freshness_words(label: str, age_hours: float | None, limit: float) -> str:
    """"daily run 7h ago", or "venue read 31h ago, past 30h", marked stale.

    THE THRESHOLD IS IN THE SENTENCE when it is crossed, so the mark is never
    a style a reader has to decode: it says what it means and what the rule
    was. A job that has never run says so rather than showing an age of
    nothing.
    """
    if age_hours is None:
        return f"{label} has never run"
    if age_hours < 1:
        shown = "under an hour ago"
    elif age_hours < 48:
        shown = f"{age_hours:.0f}h ago"
    else:
        shown = f"{age_hours / 24:.0f} days ago"
    if age_hours > limit:
        return f"{label} {shown}, past {limit:g}h"
    return f"{label} {shown}"


# ---------------------------------------------------------------------------
# THE PROMPT RECORD, IN WORDS (operator rulings of 2026-09-24 and 2026-09-25)
# ---------------------------------------------------------------------------
#
# "The page and the Record page show reconstructed rows' prompts labelled
# 'reconstructed' in those words." Every word the prompt disclosure shows is
# composed here; the renderer only places it. The prompt itself is shown
# verbatim, as the operator's ruling asks for the prompt and a humanised one
# would match no stored hash (FOLLOWUPS, 2026-09-25), and it sits in a
# literal block like the other strings a reader must see exactly.

#: What the disclosure is called, by the record's own kind. A reconstructed
#: prompt carries the word in those letters and never the sent label.
PROMPT_LABELS = {
    "sent": "The prompt it was sent",
    "reconstructed": "The prompt, reconstructed",
}

#: A reasoning forecast with no record at all: written before the record
#: existed and not yet rebuilt. The gate fails on one; the page still says so.
PROMPT_NOT_KEPT = "No prompt kept for this forecast"

#: A reconstruction's commit, said in words; the commit's name is the line's
#: tooltip (operator question 19, "internal version names only in a
#: tooltip"; the board merge, 2026-09-29). It was placed as a literal after
#: "Rebuilt through the prompt code of this commit:" until then.
PROMPT_COMMIT_WORDS = ("Rebuilt through the prompt code of the commit named in "
                       "this line's tooltip.")

#: The parts of a request, as a reader would name them.
PROMPT_PART_LABELS = {
    "system": "What it was told before the question",
    "user": "The question and the factors it was given",
    "repair": "The request that reformatted its answer",
}


def prompt_label(kind: str | None) -> str:
    """The disclosure's label for a prompt record of this kind."""
    return PROMPT_LABELS.get(kind or "", PROMPT_NOT_KEPT)


def _utc_words(stamp: str | None) -> str | None:
    """"2026-09-24T14:22:25Z" -> "Thursday 24 September at 14:22 UTC"."""
    day = date_words_from_iso(stamp)
    if day is None:
        return None
    clock = (stamp or "")[11:16]
    return f"{day} at {clock} UTC" if len(clock) == 5 and clock[2] == ":" else day


def prompt_note(kind: str | None, reconstructed_utc: str | None = None,
                provenance: str | None = None) -> str:
    """What the disclosure says about where its prompt came from."""
    if kind == "sent":
        return ("This is the exact request the reasoning pass sent, kept with "
                "the forecast when it was written.")
    if kind == "reconstructed":
        when = date_words_from_iso(reconstructed_utc) or "a later day"
        lead = (f"Reconstructed on {when} from what this forecast stored, "
                f"through the prompt code as it stood when it ran. The prompt "
                f"actually sent was not kept, so this is not it.")
        return f"{lead} {provenance.strip()}" if provenance else lead
    return ("This forecast was written before the reasoning pass kept its "
            "prompts, and its prompt has not been reconstructed yet.")


def prompt_part_label(part: str, kind: str | None = None) -> str:
    """One part of a request, named -- and of a reconstruction, named as one.

    THE WORD TRAVELS WITH EVERY BLOCK OF TEXT (render check, 2026-09-25). The
    first render put "What it was told before the question" above a
    reconstructed system prompt: a heading asserting the forecast was told
    that, over text the ruling says "is never presented as the prompt sent",
    and on a phone the one "reconstructed" was four thousand pixels above the
    end of the text it described. So each part of a reconstruction carries
    the word beside it, in those letters, and a sent part never does.
    """
    label = PROMPT_PART_LABELS[part]
    return f"{label}, reconstructed" if kind == "reconstructed" else label


def prompt_request_line(kind: str | None, max_tokens) -> str:
    """The request's settings in a sentence; the model's name is placed
    beside it as a literal, never glued in."""
    verb = "Rebuilt as a request to" if kind == "reconstructed" else "Sent to"
    room = (f", with room for an answer of at most {int(max_tokens)} tokens"
            if isinstance(max_tokens, (int, float)) else "")
    return f"{verb} the model named here{room}."


def reconstruction_provenance(*, commit_utc: str | None, before_merged_only: bool,
                              no_task_run: bool,
                              uncertain: list[str] | tuple[str, ...] = ()) -> str:
    """What a reconstruction's commit can vouch for and what it cannot, in
    words. Stored on the record when it is written; shown beside it.

    THE COMMIT IS THE MAIN CHECKOUT'S AT THE FORECAST'S MINUTE, read from its
    own history, and until the evening of 23 September the scheduler ran that
    checkout's working tree, uncommitted edits and all -- so for those the
    commit is the committed code nearest the run, never proof of what ran.
    """
    moved = _utc_words(commit_utc)
    parts = [
        "Built by the code the scheduler's checkout had committed when this "
        "forecast was written"
        + (f", the commit it moved to on {moved} by its own history." if moved
           else ", by its own history.")]
    if before_merged_only:
        parts.append(
            "Until the evening of 23 September the scheduler also ran edits "
            "that were never committed, so this is the committed code nearest "
            "the run, not proof of the code that ran.")
    else:
        parts.append("From the evening of 23 September the scheduler ran only "
                     "merged commits.")
    if no_task_run:
        parts.append("No scheduled task was recorded running when this "
                     "forecast was written.")
    for name in uncertain:
        parts.append(
            f"The number for {name} sits exactly halfway at its fourth decimal "
            f"place as stored, and the prompt showed it rounded from more "
            f"places than the record keeps, so its last digit may differ from "
            f"what was sent.")
    return " ".join(parts)


def prompt_record_line(n: int, sent: int, reconstructed: int) -> str:
    """The Record page's count of reasoning forecasts and their prompts."""
    missing = n - sent - reconstructed
    if not n:
        return "The reasoning pass has no forecasts in this sport yet."
    line = (f"{n} reasoning forecast{'' if n == 1 else 's'}: {sent} with the "
            f"prompt as sent, {reconstructed} with the prompt reconstructed")
    if missing:
        line += f", and {missing} with no prompt kept"
    return line + "."
# THE BOARD (GRIDIRON_BOARD, operator ruling 2026-09-24)
# ---------------------------------------------------------------------------
#
# Every word on a game row, a bet tile, a prop tile, a chip, a badge, a
# tooltip and the entry rail is composed here. The renderer places them and
# decides nothing about wording; the plain-words scan, the pressure scan and
# the advice scan read this payload, tooltips included.

#: The words on the row that never change with the data.
def board_labels() -> dict:
    """Every fixed label the board's renderer places.

    Typed once, here, so the browser never composes one: a label the renderer
    typed for itself is outside the plain-words scan, and "Payspays" is what
    that produced last time.
    """
    return {
        "starts": "starts",
        "live": "LIVE",
        "final": "FINAL",
        "yours": "Yours",
        "no_pick": "no forecast on this game",
        "questions": "questions",
        "forecaster": "forecaster",
        "expand": "every question on this game",
        "collapse": "fewer",
        "took": "I took this",
        "taken": "taken",
        "record": "record",
        # THE PROPS TILE'S THREE ROWS (operator ruling C, 2026-10-05): the
        # projection, the venue's main line and the break-evens; "cushion"
        # went with the declared multiple it was measured against.
        "projection": "projection",
        "main_line": "main line",
        "breakeven": "break-even",
        # AND A FOURTH (the entry check's step 2, 2026-10-07): whether the
        # model can state its chance at the line the operator types for this
        # player and stat, never a chance on the tile itself.
        "at_your_line": "at your line",
        "save": "Save",
        "venue": "venue line",
        "not_read": "not read yet",
        "not_listed": "not listed",
        "alt": "Alt lines",
        "all": "All",
        "high_end": "high-end record",
        "entry": "Entry",
        "pays": "venue pays",
        "legs": "legs",
        "line_model": "model",
        "line_half": "if half as good",
        "line_kalshi": "Kalshi where listed",
        "line_floor": "floor",
        "per_dollar": "per dollar",
        "pregame": "pregame",
        "how": "How the model works",
        # THE MOCKUP'S FIXED WORDS (visual pass, 2026-09-25), placed by the
        # renderer and never composed there.
        "every_bet": "Every bet on this game",
        # THE GREEN OUTLINE IS A PICK (operator ruling B, 2026-10-05; built
        # 2026-10-07): it said "clears the bar", which an ungated market's
        # recommendation did.
        "legend_clears": "a pick",
        "legend_costs": "costs after fees",
        "legend_won": "won",
        "legend_lost": "lost",
        "polled": "polled",
        # SORT AND FILTER (visual pass, 2026-09-25) and the detail panel.
        # NO SORT BY THE MODEL'S CHANCE (operator ruling B.1, 2026-10-05:
        # "Chance of hitting alone never ranks anything"; built 2026-10-07):
        # the Games page's "the model's chance" option went, and its "edge"
        # orders the picks by their edge and everything else by its start.
        "sort": "sort",
        "sort_time": "start time",
        # THE PROPS PAGE SORTS BY EDGE OR BY GAME (operator ruling C,
        # 2026-10-05, with B.1's "chance of hitting alone never ranks
        # anything"): the cushion was the model's chance less one declared
        # number, so ranking by it was ranking by chance.
        "sort_edge": "edge",
        "show": "show",
        "clears_only": "picks only",
        "market": "market",
        "all_markets": "all markets",
        "form": "last five",
        "injuries": "injuries",
        "weather": "weather",
        "factors": "what the model read",
        "my_day": my_day_heading(),
        "updating": "updating",
    }


def number_tip(number: int | None) -> str:
    """What the jersey's number slot means, on hover."""
    if number is None:
        return "No number on record for this player, so the slot stays empty."
    return f"Number {number}, from the roster file read at the last refresh."


def chart_gate_words(n: int, gate: int, *, first_read: str | None = None) -> str:
    """"12 of 50": what a chart area says below its gate, and draws nothing.

    AND BEFORE THE FIRST CLEAN READ, THE DATE (the board merge, 2026-09-29;
    the operator's ruling 8 of 2026-09-23): a closing-line chart draws
    nothing before `config.CLOSING_LINE_FIRST_CLEAN_READ` whatever its count,
    so its area says when it may, in the words the closing line's own
    sentence uses -- a chart saying "50 of 50" and drawing nothing would read
    as a fault."""
    head = f"{n} of {gate}"
    if first_read is None:
        return head
    when = date_words_from_iso(first_read) or first_read
    return f"{head} · nothing is drawn before {when}"


def closing_chart_title(category_label: str, n: int) -> str:
    """"total, statistical · 12 against the close": a closing-line chart's
    title, naming whose line it is and its N (the board merge, 2026-09-29;
    operator question 22: one line per market and forecaster). Composed here,
    where the board's renderer glued a market's label to its count."""
    return f"{category_label} · {n} against the close"


def record_page_words() -> dict:
    """The Record page's fixed words for the two chart panels (2026-09-25)."""
    return {
        "closing_heading": "The closing line, over time",
        "closing_note": ("Each point is one recommendation against the market's own "
                         "final price for the same question, in the order they "
                         "closed. A chart draws only past its floor; below it the "
                         "area says how many of the floor there are."),
        "taken_heading": "Taken, passed over, every forecast",
        "taken_note": ("Three curves on the same questions, never merged: the "
                       "picks the operator marked, the ones he passed over, and "
                       "all of them. Each draws only past the gate. Voided and "
                       "withdrawn forecasts are never counted."),
        "resolved": "resolved",
    }


def taken_record_silent_words(markets: list[str],
                              predictor: str | None = None) -> str | None:
    """"Nothing of the statistical model's settled yet in passing yards, ..."
    -- the markets said once, whose said once (the board merge, 2026-09-29:
    each block names its forecaster, and a list of "passing yards,
    statistical, receiving yards, statistical" read as twice as many
    markets, which the render showed)."""
    if not markets:
        return None
    whose = (f" of the {FORECASTER_FILTER_WORDS.get(predictor, predictor)} "
             f"model's" if predictor == "statistical" else
             f" of the {FORECASTER_FILTER_WORDS.get(predictor, predictor)}'s"
             if predictor else "")
    return f"Nothing{whose} settled yet in " + ", ".join(markets) + "."


def my_day_heading() -> str:
    return "My day"


def my_day_empty_words() -> str:
    return "Nothing taken on this slate yet."


def my_day_counts_words(n: int, live: int, won: int, lost: int) -> str:
    """"3 taken · 1 live · 1 won · 1 lost": counts of picks, never money."""
    parts = [f"{n} taken"]
    if live:
        parts.append(f"{live} live")
    if won:
        parts.append(f"{won} won")
    if lost:
        parts.append(f"{lost} lost")
    return " · ".join(parts)


def my_day_line_tip(question: str, own_side: str | None = None) -> str:
    """A My day chip's tooltip: the contract its words name, and -- where the
    pick is a recommendation buying the OTHER side of the model's words -- the
    model's own side and number beside it ("New Orleans covers -2.5. The
    model's own side: Atlanta +2.5, 32%.").

    Q37'S PROVER (2026-10-05; operator question 37, ruled that day: "headline
    the contract the recommendation buys; the model's own side named beside
    it"). The chip headlined the contract bought and named the model's side
    nowhere, where the row, the tile, the line and the taken rail all do; the
    chip has no room for a sentence, so it is said in the tooltip."""
    if not own_side:
        return question
    return f"{question}. {own_side}." if question else f"{own_side}."


def my_day_status_words(state: str, signal: str, score_words: str | None) -> str:
    """The chip's state in a word: upcoming, live with the score, won, lost."""
    if state == "live":
        return f"live · {score_words}" if score_words else "live"
    if signal == "won":
        return "won"
    if signal == "lost":
        return "lost"
    if signal == "withdrawn":
        return "withdrawn"
    if state == "final":
        return "settled"
    return "upcoming"


def form_marks_tip(team: str, marks: list[str]) -> str:
    if not marks:
        return f"{team}: no finished games in this record yet."
    return f"{team}'s last {len(marks)}, most recent first, from this record's own finished games."


def injuries_words(names: list[str]) -> str:
    """"Two out or doubtful: A. Player (Out), B. Player (Doubtful)", or the
    absence in words. Only what the injury report the model already reads
    lists; nothing is fetched for this."""
    if not names:
        return "No injuries on the report the model read."
    return f"{len(names)} on the injury report: " + ", ".join(names) + "."


def no_weather_words() -> str:
    return "No forecast was read for this game (the weather pass runs for outdoor football only)."


def factors_absent_words() -> str:
    return "No factor reading on this pick: the forecaster shows no decomposition."


def factor_line_words(plain_name: str | None, factor: str) -> str:
    return plain_name or humanise(factor)


def pick_label_words(state: str, signal: str, *, pick: bool = False,
                     other_side: bool = False) -> str:
    """The small label over the row's lead question: what it is, and its state.

    `other_side` (operator question 37, ruled 2026-10-05): the pick headlines
    the contract the recommendation buys, and where that is the other side of
    the one the model took the label says so -- the row beneath it names the
    model's own side and number. (Short: it heads a 290px column, and the
    render of 2026-10-05 wrapped a longer one onto two lines at 1300px.)

    "MODEL'S PICK" ONLY ON A PICK (operator ruling B, 2026-10-05: "A leg is
    called a pick only if its edge after fees is 3 percentage points or more.
    Below that it is shown as a number, never as a pick"; built 2026-10-07,
    reading (b)). Until then every row's lead wore "Model's pick" -- 1,269
    rows on 108 payloads of the record that day, 280 still to start and none
    of them a pick under B -- because the lead was chosen as the surest
    question. `pick` is the one door's answer (`picks.judge`); a question
    still to come that is not a pick is "Not a pick", and a game being played
    or finished says what its number is, never that it was a pick: whether it
    was one at its start is not on the page (FOLLOWUPS)."""
    if state == "upcoming":
        base = "Model's pick" if pick else "Not a pick"
        return base + " · the other side" if other_side else base
    base = "The model's number"
    if state == "live":
        return base + " · pregame"
    if signal == "won":
        return base + " · won"
    if signal == "lost":
        return base + " · lost"
    if signal == "withdrawn":
        return base + " · withdrawn"
    return base


def not_a_pick_words(*, game_market: bool, n: int, gate: int, passes: bool,
                     edge_points: float | None, under_the_bar: bool,
                     category: str | None = None) -> str:
    """Beside a recommendation that is not a pick, why (operator ruling B,
    2026-10-05; reading (d), built 2026-10-07): its market has not passed
    B.5's gate -- with how many settled comparisons at the venue's price of
    the hundred it has -- or its edge after fees is under the three points
    B.2 asks, or both. `edge_points` is the edge as it may be drawn
    (`picks.drawn_edge`: never at the bar when under it).

    `category` (the prover of ruling B, 2026-10-07): WHOSE COUNT IT IS, in
    the Record page's own label for the curve the gate counts
    (`at_the_line_category_label`: "spread at the venue's line,
    statistical"). The gate is one forecaster's and, for UFC, one card's
    (B.5's reading: "per forecaster"; the at-the-line record splits UFC by
    card), and "its market has 0 of the 100" said a card's count as the
    market's -- false wherever two cards' counts part -- and never said whose
    (NFL spread at the venue's price: 24 the model's, 2 the reasoning pass's,
    on 6 October)."""
    reasons = []
    if not game_market:
        reasons.append("this market keeps no record against the venue's price, "
                       "so it has no gate to pass")
    elif not passes:
        whose = f" ({category})" if category else ""
        reasons.append(f"its market has {n} of the {gate} settled comparisons "
                       f"with the venue's price it needs first{whose}")
    if under_the_bar:
        if edge_points is None:
            reasons.append("it has no edge after fees to read")
        else:
            reasons.append(f"its edge after fees is {edge_points:+.1f} points, "
                           f"under the 3 a pick needs")
    if not reasons:
        return "Not a pick."
    return "Not a pick: " + ", and ".join(reasons) + "."


def pick_words(edge_points: float | None) -> str:
    """"Pick · +4.3 after fees": the badge a Kalshi pick wears beside its
    outline (operator ruling B, 2026-10-05), its edge in points of the side
    bought."""
    if edge_points is None:
        return "Pick"
    return f"Pick · {edge_points:+.1f} after fees"


def nothing_worth_taking_words() -> str:
    """B.4's words, exactly (operator ruling B, 2026-10-05: "No filling. When
    nothing clears on a slate: 'Nothing worth taking today'"): on every page
    that draws picks for a slate with rows still to come and none a pick --
    Games, the Today groups, Props -- and nothing drawn to look like one."""
    return "Nothing worth taking today"


def badge_words(n: int, gate: int) -> str:
    """"12/100": settled in this market against the hundred LAW 4 asks for.

    THE BADGE IS THE SAMPLE SIZE, on every row and every tile, which is what
    lets a signal be read beside how much stands behind it. It never renders
    without its two numbers, and a signal never renders without it.
    """
    return f"{int(n)}/{int(gate)}"


def badge_tip(n: int, gate: int, market_words: str) -> str:
    """What the badge means, for its tooltip."""
    if n >= gate:
        return (f"{n} settled in {market_words}, past the {gate} this app asks "
                f"for before it claims an edge.")
    return (f"{n} settled in {market_words}. {gate - n} more before this app "
            f"claims an edge here; until then a size is a flat unit and a "
            f"signal is a price comparison, not a verdict.")


def high_end_badge_words(n: int, gate: int) -> str:
    """The second badge an alt-line tile carries: how the record has done at
    the high end of the probability range, which is where an alt line lives.
    """
    return f"{int(n)}/{int(gate)} at 70% and up"


def high_end_badge_tip(n: int, gate: int) -> str:
    return (f"An alt line is a claim near the top of the range, and the "
            f"record there is its own: {n} settled at 70% and up of the {gate} "
            f"this app asks for before it trusts that end of the curve.")


def signal_tip(signal: str) -> str | None:
    """What an outline or a fill means, in words, for the tooltip on it."""
    # THE GREEN OUTLINE IS A PICK (operator ruling B, 2026-10-05; built
    # 2026-10-07): an edge after fees of three points or more, in a market
    # that has passed its gate at the venue's price, beside the writer's own
    # bar. Until then it said the fee and the five per cent alone, which an
    # ungated market's recommendation cleared.
    return {
        "clears": ("A pick: its edge after fees is 3 points or more, its "
                   "market has passed its gate at the venue's price, and the "
                   "return on the money is at least five per cent."),
        "costs": ("Costs after fees: at this price the venue's fee eats what "
                  "the model sees, so being right still loses money."),
        "won": "Settled: it happened.",
        "lost": "Settled: it did not happen.",
        "withdrawn": "Withdrawn: this forecast was voided and is never counted.",
    }.get(signal)


def prob_tip(shown: float | None, forecaster_label: str, *,
             asked_words: str | None = None, own_side: str | None = None) -> str:
    """The model's chance, and where it came from.

    `asked_words` (pick-number step A, 2026-09-30): where the pick names the
    venue's contract at another line than the model was asked about, the
    chance is the model's own distribution read at that contract's line, and
    the tooltip says what the model was asked (`asked_elsewhere_words`).

    `own_side` (operator question 37, ruled 2026-10-05): the pick headlines
    the contract the recommendation buys, which is the OTHER side of the one
    the model took; the chance is that contract's, and the tooltip names the
    model's own side and its number (`own_side_words`)."""
    if shown is None:
        return "No probability on this row."
    if own_side:
        return (f"The {forecaster_label} forecaster's chance for this contract, "
                f"{round(shown * 100)}%. It is the other side of the one the "
                f"model took, and the recommendation buys it because the price "
                f"makes it worth buying. {own_side}."
                + (f" {asked_words}" if asked_words else ""))
    if asked_words:
        return (f"The {forecaster_label} forecaster's chance for this contract, "
                f"{round(shown * 100)}%, read from the forecast it wrote before "
                f"any price was seen, at the venue's line. {asked_words}")
    return (f"The {forecaster_label} forecaster's chance, {round(shown * 100)}%, "
            f"written before any price was seen and corrected only where the "
            f"record has earned a correction.")


def price_tip(price: float | None, market: str | None, hours: float) -> str:
    if price is None:
        if market is not None and market not in MARKETS_READ_AT_THE_VENUE:
            return ("No venue price: this market is not read at the venue "
                    "yet, so there is nothing to compare the model with.")
        return (f"No venue price yet. The first read is taken about {hours:g} "
                f"hours before the start, and the close is the last read "
                f"before it.")
    return (f"The venue's last read of this contract, {round(price * 100)}¢. "
            f"The fee is charged on top and is largest near a coin flip.")


def pays_tip(multiple: float | None, *, elsewhere: str | None = None) -> str:
    """`elsewhere` (pick-number step A, 2026-09-30): an opening read taken at
    another line than the question's names the contract it pays on."""
    if multiple is None:
        return "Nothing to pay out: there is no venue price on this contract."
    if elsewhere:
        return (f"The venue's opening read lists no contract at this line. At "
                f"{elsewhere} a dollar returns {multiple:.2f} times if it "
                f"happens, before the fee.")
    return (f"What a dollar returns if this happens, {multiple:.2f} times, "
            f"before the fee.")


def pick_line_words(item: dict) -> str:
    """The pick in its loudest honest form, for the row: the same short form
    the old tiles used, so the side is resolved by the one door."""
    return tile_line(item)


def game_questions_words(counts: dict, chosen: str) -> str:
    """"3 questions from the model · 1 from the reasoning pass": a game row's
    questions, EACH FORECASTER'S COUNTED APART (the prover of the board merge,
    2026-09-29). Questions, never bets or plays.

    The board said "4 questions on this game" over three of the model's and
    one of the reasoning pass's: one figure over both forecasters under the
    word "question", which counted a question both answered twice -- the
    pooled count operator questions 14 and 22 took off every other panel
    ("Recommendation counts split per forecaster, like every other count").
    `counts` is each forecaster's standing questions on the game, on question
    17's key (`bet.count`); the page's own forecaster is said first, and a
    forecaster with none on the game is not mentioned."""
    order = [chosen] + sorted(f for f in counts if f != chosen)
    parts = []
    for forecaster in order:
        n = counts.get(forecaster) or 0
        if not n:
            continue
        whose = FORECASTER_WORDS.get(forecaster, forecaster)
        parts.append(f"{counted(n, 'question')} from {whose}" if not parts
                     else f"{n} from {whose}")
    return " · ".join(parts) if parts else f"{counted(0, 'question')} on this game"


def games_empty_words(sport_label: str) -> str:
    """The Games page with nothing on it."""
    return f"No {sport_label} games on this slate."


def nothing_clears_words() -> str:
    """The Games page's line when no row is a pick.

    B.4'S WORDS FROM 2026-10-07 (operator ruling B, 2026-10-05: "No filling.
    When nothing clears on a slate: 'Nothing worth taking today'"). Until then
    it said "Nothing clears the bar today. Every pick below is priced, and
    none of them beats the fee." -- false under B on both counts: no row
    below it is a pick, and an unpriced row is not priced. It is drawn above
    the rows whenever the slate has a row still to come and none is a pick,
    priced or not (reading (f))."""
    return nothing_worth_taking_words()


def props_empty_words(sport_label: str) -> str:
    return f"No {sport_label} player props forecast on this slate."


# ---------------------------------------------------------------------------
# THE PROPS BOARD (operator ruling C, 2026-10-05; built 2026-10-06)
# ---------------------------------------------------------------------------
#
# "Never present a venue ladder rung as a pick'em pick. Per player and stat:
# the model's projection and its chance at the market's main line (the rung
# nearest 50c), labelled 'about the app's line, check the app'. The full
# ladder moves to its own 'Kalshi ladder' view." Until this date every tile
# was a question this record asked at its own line, beside "57.7% to break
# even" and a cushion from a declared 3x nobody typed. Each tile is now one
# player and one stat: the projection, the chance at the venue's main line,
# the break-even of each payout the operator typed, and a pick only where
# the edge clears the bar (B.2). The words are here; `board` chooses which.

#: THE OPERATOR'S OWN WORDS beside every number at the venue's main line
#: (C.1): the main line stands for the pick'em app's line, which this app
#: never reads (LAW 5; ruling D), so it says so wherever it is shown.
APP_LINE_WORDS = "about the app's line, check the app"


def pickem_entry_name(legs: int) -> str:
    """"2-pick power": an entry by its size and kind, as an app names it."""
    return f"{int(legs)}-pick power"


def pickem_payout_label(legs: int) -> str:
    """The label of the field the operator types a power payout into."""
    return f"A {pickem_entry_name(legs)} entry pays"


def pickem_typed_words(typed_utc: str | None) -> str:
    """"typed Monday 5 October": when the operator typed a payout (C.3, read
    (b): shown with when it was typed)."""
    when = date_words_from_iso((typed_utc or "")[:10]) if typed_utc else None
    return f"typed {when}" if when else "typed on a day the record does not hold"


def pickem_payouts_heading() -> str:
    return "What your app pays"


def pickem_payouts_ask_words(missing: list[int]) -> str | None:
    """THE PAGE ASKS (C.3: "until typed, the page asks for it and shows no
    break-even"), naming each payout not yet typed; None when both are."""
    if not missing:
        return None
    entries = [f"a {pickem_entry_name(n)} entry" for n in missing]
    named = " and ".join(entries)
    verb, them = ("pays", "it") if len(entries) == 1 else ("pay", "them")
    return (f"Type what {named} {verb} in your app. Until you do, no "
            f"break-even is shown for {them}, and no leg is called a pick "
            f"against {them}: nothing here assumes a payout.")


def pickem_payouts_note() -> str:
    return ("Typed once and kept, each with the day you typed it; type again "
            "to change it. Nothing here is read from any pick'em app.")


def pickem_breakeven_words(legs: int, breakeven: float | None) -> str:
    """"2-pick power 57.7%", or that its payout is not typed yet."""
    if breakeven is None:
        return f"{pickem_entry_name(legs)}: payout not typed"
    return f"{pickem_entry_name(legs)} {breakeven * 100:.1f}%"


def pickem_breakeven_tip(legs: int, multiple: float | None,
                         breakeven: float | None, typed_utc: str | None) -> str:
    """Where a break-even comes from: the payout typed, and the arithmetic."""
    name = pickem_entry_name(legs)
    if multiple is None or breakeven is None:
        return (f"No payout is typed for a {name} entry, so no break-even is "
                f"shown and no leg is called a pick against it. Type what your "
                f"app pays at the top of this page.")
    # PLAIN WORDS (the prover of ruling C, 2026-10-06): this said "2 legs that
    # likely all hit together one time in 3", which says nothing a reader can
    # follow. At the break-even every leg hits together exactly as often as
    # the payout pays back.
    every = "both legs" if int(legs) == 2 else f"all {int(legs)} legs"
    return (f"A {name} entry paying {multiple:g} times, as you typed it "
            f"({pickem_typed_words(typed_utc)}). Every leg must hit, so a leg "
            f"breaks even at {breakeven * 100:.1f}%: at that chance {every} "
            f"hit together one time in {multiple:g}, and a payout of "
            f"{multiple:g} times only gives back what the entries cost.")


def prop_projection_words(projection: float | None, family_words: str) -> str:
    """"about 4.4 receptions", or none, said plainly."""
    if projection is None:
        return f"none for {family_words}"
    return f"about {projection:.1f} {family_words}"


def prop_projection_tip(projection: float | None, family_words: str) -> str:
    if projection is None:
        return (f"The model answers {family_words} as a yes-or-no question at "
                f"its own line and states no expected number, so there is no "
                f"projection to show. None is guessed.")
    return (f"The model's own expectation for this player and stat in this "
            f"game, written with its forecast before any line was read: about "
            f"{projection:.1f} {family_words}.")


def prop_main_absent_words() -> str:
    """No main line for this player and stat: the venue lists none here."""
    return "not listed by the venue"


def prop_leg_words(player: str | None, family_words: str) -> str:
    """"Jared Goff · passing yards": a leg named by its player and stat where
    the venue lists no main line -- no line is named, because no line is the
    app's (the prover of ruling C, 2026-10-06: the entry rail drew a taken leg
    under its own question's line beside its chance at another)."""
    return f"{player or ''} · {family_words}".strip(" ·")


def prop_main_absent_tip() -> str:
    return ("The venue's player-prop ladders are not read, so there is no main "
            "line — the rung priced nearest an even chance, which stands for "
            "the app's line — and no chance from the model at it. No leg is "
            "called a pick without one.")


def prop_main_line_tip(price: float | None) -> str:
    cents = "" if price is None else f" (the venue's price {price * 100:.0f}¢)"
    return ("The venue's main line for this player and stat: of every rung it "
            f"lists, the one priced nearest an even chance{cents}. It stands "
            "for the pick'em app's line, which this app never reads — about "
            "the app's line, check the app. Every rung is in the Kalshi "
            "ladder view.")


def prop_no_chance_words() -> str:
    """Reading (a): the model states no chance at the main line."""
    return "the model has no chance at this line yet"


def prop_no_chance_tip(family_words: str) -> str:
    return (f"The model answers {family_words} only at the line it asked, and "
            f"nothing it wrote can be read at another, so it has no chance at "
            f"this line yet. None is guessed, and no leg is called a pick "
            f"without one.")


def prop_chance_words(chance: float | None) -> str:
    return "" if chance is None else f"{round(chance * 100)}%"


def prop_chance_tip(contract_words: str, chance: float, how: str) -> str:
    return (f"The model gives \"{contract_words}\" {round(chance * 100)}%: "
            f"{how}. {APP_LINE_WORDS[0].upper() + APP_LINE_WORDS[1:]}.")


def prop_chance_how_words(asked_here: bool, projection: float | None,
                          family_words: str) -> str:
    """How the model's chance at the main line was stated."""
    if asked_here:
        return "its own question, asked at this line"
    if projection is not None:
        return (f"its expected {projection:.1f} {family_words}, read at this "
                f"line as a count")
    return "read at this line from what it wrote"


def prop_edge_words(edge: float | None) -> str | None:
    """"edge +4.3": the chance at the main line minus a break-even, in points."""
    return None if edge is None else f"edge {edge * 100:+.1f}"


def prop_pick_words(legs: list[int]) -> str | None:
    """"Pick · 2-pick power" -- a leg whose edge clears the bar for these
    entries (B.2); None for a leg that clears for none."""
    if not legs:
        return None
    names = [pickem_entry_name(n) for n in sorted(legs)]
    if len(names) == 1:
        return f"Pick · {names[0]}"
    sizes = " and ".join(f"{int(n)}-pick" for n in sorted(legs))
    return f"Pick · {sizes} power"


def prop_pick_tip(bar: float) -> str:
    return (f"Its edge — the model's chance at the main line minus the "
            f"break-even of the payout you typed — is {bar * 100:g} points or "
            f"more for this entry. Below that a leg is shown as a number and "
            f"never as a pick (ruled 5 October). About the app's line, check "
            f"the app.")


def props_nothing_worth_taking_words() -> str:
    """B.4's words, on the Props page from ruling C (2026-10-05): no leg on
    the slate clears the bar, and nothing is filled in to look like one.
    (From ruling B, built 2026-10-07, the one composer every page asks.)"""
    return nothing_worth_taking_words()


def prop_own_question_words(question: str, chance_words: str) -> str:
    """The question the record asked at its own line, and what it said."""
    said = f" · {chance_words}" if chance_words else ""
    return f"The model's own question: {question}{said}"


def prop_own_question_tip() -> str:
    return ("The question this record asked at its own line before any line "
            "was read, and what the model said: the forecast, graded as asked. "
            "It is not the app's line, so it carries no break-even and is "
            "never called a pick.")


def props_board_note() -> str:
    """The Props page's standing note: what each tile is."""
    return ("Each tile is one player and one stat: the model's projection, its "
            "chance at the venue's main line — about the app's line, check the "
            "app — and the break-even of each payout you typed. A leg is "
            "called a pick only where its edge is 3 points or more.")


def props_ladders_not_read_words() -> str:
    """Why no tile has a main line: the venue's prop ladders are not read."""
    return ("The venue's player-prop ladders are not read, so no main line is "
            "listed for any player yet.")


def venue_ladder_view_words() -> dict:
    """The Kalshi ladder view's fixed words (C.1: "The full ladder moves to
    its own 'Kalshi ladder' view"; reading (e): each rung named under its own
    contract, never a pick'em pick, no badge)."""
    return {
        "chip": "Kalshi ladder",
        "heading": "Kalshi ladder",
        "note": ("Every rung the venue lists for a player and stat, each under "
                 "its own contract and price. A rung is a contract at the "
                 "venue, never a pick'em pick: nothing here carries a "
                 "break-even, an edge or a pick."),
        "empty": ("The venue's player-prop ladders are not read: no prop rung "
                  "is on the record, so there is nothing to list."),
        "main": "main line",
        "main_tip": ("The rung priced nearest an even chance — the one the "
                     "Props tiles read as standing for the app's line."),
    }


def ladder_rung_price_words(price: float | None) -> str:
    return "no price" if price is None else f"{price * 100:.0f}¢"


# ---------------------------------------------------------------------------
# CHECK AN ENTRY (GRIDIRON_ENTRY_CHECK, step 1, the arithmetic; the brief of
# 2026-09-30 with ruling D of 2026-10-05; built 2026-10-07)
# ---------------------------------------------------------------------------
#
# Every word the Props page's entry check draws is composed here; the
# renderer places them. Until 2026-10-07 the entry rail read the model's
# chance at each leg's MAIN line -- the venue's, never the app's line the
# operator types -- and `entry_words` held its sentences; the rail is the
# entry check now (`entry_check`, reading (f)).
#
# THE WORDS KEEP TO THE PLAIN-WORDS RULE AND ITS BANNED LIST (2026-09-08:
# "parlay", "same game", "boost", "builder", "add leg" and "slip" stay
# banned; `audit.pressure_word_faults`) AND TO THE ADVICE LIST ("value",
# "play", "bet", "worth it" ...): the brief's boost is said "a promo" -- "the
# app raised the payout", "a share of the winnings added" -- its value "what
# the promo adds", and its same-game flag "legs in one game", with the brief's
# own sentence beside it: "these legs move together; the math assumes they
# don't". Reading (i), recorded in docs/REPAIR_STATE.md.

def entry_check_panel_words() -> dict:
    """The entry check's fixed words: its labels, its notes and its asks."""
    return {
        "heading": "Check an entry",
        "closed": ("Checking an entry is for NFL player props: this first "
                   "version of the check reads no other sport."),
        "intro": ("Type the entry as the app shows it: each leg, and what the "
                  "app pays for the whole entry."),
        "app": "App",
        # NO APP IS CHOSEN FOR HIM (2026-10-07, resumed build): the payout
        # last typed is kept and offered by app, so an app the page chose
        # would file what he confirms under an app he never named.
        "app_none": "Choose the app",
        "entry": "Entry",
        "type_power": "Power",
        "type_flex": "Flex",
        "legs_heading": "Legs",
        "leg": "Leg",
        "player": "Player",
        "club": "Club",
        "club_none": "Choose a club",
        "stat": "Stat, as the app shows it",
        "line": "Line",
        "side": "Over or under",
        "side_over": "Over",
        "side_under": "Under",
        "kind": "Kind",
        "kind_standard": "Standard",
        "kind_goblin": "Goblin",
        "kind_demon": "Demon",
        "original": "Line before a discount",
        "original_tip": ("Only where the app discounted this leg's line: the "
                         "line it had before. Leave it empty otherwise."),
        "remove": "Take this leg off",
        "more": "One more leg",
        "marked_heading": "Props you marked",
        "marked_note": ("Tap one to put its player, club and stat in the "
                        "entry; type its line as the app shows it."),
        "payout_heading": "What the app pays for this entry",
        "payout_power": "Pays, as a multiple of the entry",
        "payout_flex_note": "Leave a row empty where the app pays nothing for it.",
        "confirm": "This is what the app shows for this entry",
        "promo_heading": "A promo on this entry",
        "promo": "Promo",
        "promo_none": "No promo",
        "promo_raised": "The app raised the payout",
        "promo_profit": "A share of the winnings added",
        "raised_power": "With the promo it pays",
        "raised_flex_note": "With the promo, as the app shows it",
        "percent": "Share of the winnings added, per cent",
        "cap": "The most it adds, in units",
        "cap_note": "Leave it empty where the promo has no cap.",
        "entry_units": "The entry, in units",
        "entry_units_note": "Needed only where the promo has a cap.",
        "check": "Check this entry",
        "changed": "Changed since the last check. Check it again.",
        "line_breakeven": "Break-even per leg",
        "line_return": "At coin flips, per unit",
        "line_promo_breakeven": "Break-even per leg with the promo",
        "line_promo_return": "At coin flips with the promo",
        "line_promo_adds": "What the promo adds, per unit",
        "line_gap": "An even chance on each leg is",
        "line_promo_gap": "With the promo, an even chance on each leg is",
        "return_tip": ("What the entry returns per unit it costs, less that "
                       "unit, with every leg an even chance: below zero it "
                       "costs, above zero it returns more than it costs."),
        "adds_tip": ("The return per unit at coin flips with the promo, less "
                     "the return without it."),
        "gap_tip": ("How far an even chance sits from the chance each leg "
                    "needs: 3 points or more over it clears the bar."),
        "one_game_heading": "Legs in one game",
        "confirm_first": ("Confirm what the app pays for this entry: nothing is "
                          "worked out from a payout until you do."),
        "entry_units_first": ("Type the entry in units: the promo's cap is in "
                              "units, so nothing is worked out until it is "
                              "there."),
        # STEP 2 (2026-10-07): the verdict stays the arithmetic at coin flips;
        # the model's chance at each line stands beside it, marked not yet
        # proven, and may flag a leg, never the verdict.
        "note": ("The verdict is arithmetic only: every leg is put at an even "
                 "chance, and no model and no record is behind it. Beside it, "
                 "where the model forecast a leg's player and stat, its chance "
                 "at your line, not yet proven, may flag a leg and never "
                 "changes the verdict. Nothing is read from any app. Every "
                 "number but the model's comes from the payout you typed "
                 "for this entry — a goblin or demon leg changes what the app "
                 "pays, and a discounted line counts like any other in it. Units "
                 "only, never dollars. Nothing is placed, and nothing about the "
                 "entry is kept but the payout you confirm, offered next time "
                 "for its app and size, to confirm again."),
    }


#: What a field is called in a refusal.
_ENTRY_PAYOUT_WHAT = {"payout": "The payout", "raised": "The raised payout"}


def entry_check_refused_words(code: str, **d) -> str:
    """Why the entry check cannot read the form, in words: the field and what
    it needs."""
    what = _ENTRY_PAYOUT_WHAT.get(d.get("what") or "payout", "The payout")
    leg = f"Leg {d.get('leg')}: " if d.get("leg") is not None else ""
    got = d.get("got")
    words = {
        "not_a_form": ("The page sent something that is not an entry. Reload "
                       "it and try again."),
        "app": "Choose the app: PrizePicks, Underdog or Chalkboard.",
        "entry_type": "Choose power or flex.",
        "legs_count": (f"An entry here has 2 to 8 legs; this one has "
                       f"{d.get('n', 0)}."),
        "leg_player": f"{leg}type the player.",
        "leg_stat": f"{leg}type the stat, as the app shows it.",
        "leg_line": (f"{leg}the line {d.get('raw')!r} is not a number. Type it "
                     f"as the app shows it, like 250.5."),
        "leg_line_missing": f"{leg}type the line, as the app shows it.",
        "leg_line_bounds": (f"{leg}a line of {got:g} is not one a stat has."
                            if got is not None else f"{leg}that line is not one a stat has."),
        "leg_side": f"{leg}choose over or under.",
        "leg_kind": f"{leg}choose standard, goblin or demon.",
        "leg_original": (f"{leg}the line before a discount, {d.get('raw')!r}, "
                         f"is not a number. Leave it empty where the line was "
                         f"not discounted."),
        "leg_original_bounds": (f"{leg}a line of {got:g} before a discount is "
                                f"not one a stat has." if got is not None else
                                f"{leg}that line before a discount is not one a stat has."),
        "leg_original_same": (f"{leg}the line before a discount is the line "
                              f"itself. Leave it empty where the line was not "
                              f"discounted."),
        "payout_missing": "Type what the app pays for this entry.",
        "payout_number": (f"{what} {d.get('raw')!r} is not a payout. Type it as "
                          f"a multiple of the entry, like 3."),
        "payout_low": (f"{what} of {got:g}x returns no more than the entry "
                       f"costs, so no leg could break even on it."
                       if got is not None else f"{what} is too low."),
        "payout_high": (f"{what} of {got:g}x is more than this page reads (at "
                        f"most {d.get('most', 0):g}x). Check what the app shows."
                        if got is not None else f"{what} is too high."),
        "flex_number": (f"{what}: {d.get('right')} of {d.get('legs')} right, "
                        f"{d.get('raw')!r} is not a payout. Type it as a "
                        f"multiple of the entry, or leave it empty where the "
                        f"app pays nothing."),
        "flex_bounds": (f"{what}: {d.get('right')} of {d.get('legs')} right "
                        f"cannot pay {got:g}x (from 0 to {d.get('most', 0):g}x)."
                        if got is not None else f"{what}: a row is out of bounds."),
        "flex_less_for_more": (f"{what} pays less for more legs right somewhere "
                               f"in its table, so it has no single break-even. "
                               f"Check what you typed against the app."),
        "flex_top": (f"{what}: with all {d.get('legs')} legs right it returns "
                     f"no more than the entry costs, so no leg could break even "
                     f"on it."),
        "promo_kind": "Choose a promo, or no promo.",
        "raised_missing": "Type what the app pays with the promo.",
        "raised_not_higher": (f"The raised payout, {got:g}x, is not higher than "
                              f"the payout, {d.get('base', 0):g}x. A promo here "
                              f"raises the payout; check what the app shows."
                              if got is not None else "The raised payout is not higher."),
        "raised_flex_lower": (f"With the promo, {d.get('right')} of "
                              f"{d.get('legs')} right pays less than without "
                              f"it. A promo here raises the payout; check what "
                              f"the app shows."),
        "raised_not_higher_flex": ("With the promo the table pays no more "
                                   "anywhere. Type the raised table as the app "
                                   "shows it, or choose no promo."),
        "percent": ("Type the share of the winnings the promo adds, as a per "
                    "cent above 0 and at most 1000, like 20."),
        "cap": ("Type the most the promo adds as a number of units above 0, or "
                "leave it empty where there is no cap."),
        "entry_units": "Type the entry as a number of units above 0.",
    }
    return words.get(code) or "The entry cannot be read as typed."


def entry_check_club_words(code: str | None, names: dict | None) -> str:
    """A club by its full name from the record's `teams` rows, or its code
    where the record holds none -- never a guessed name."""
    if not code:
        return ""
    return (names or {}).get(code) or code


def entry_check_game_words(away: str, home: str, day: str | None) -> str:
    """"Green Bay Packers at Detroit Lions, Sunday 12 October": the game a leg
    was placed in, by the record's schedule."""
    when = date_words_from_iso(day) if day else None
    return f"{away} at {home}" + (f", {when}" if when else "")


def entry_check_unplaced_words(code: str, **d) -> str:
    """Why a leg was not placed in a game (reading (d): never guessed)."""
    tail = ", so this leg was not placed in a game."
    player, club = d.get("player") or "", d.get("club") or ""
    if code == "no_club":
        return "No club was chosen" + tail
    if code == "no_game":
        return f"The record has no {club} game still to come" + tail
    if code == "two_players":
        return f"The record has more than one {club} player called {player}" + tail
    if code == "other_club":
        others = " and ".join(d.get("others") or [])
        return (f"The record has {player} playing for {others} by his latest "
                f"game this season, not {club}" + tail)
    # WHERE THE CLUB'S NEXT GAME IS NOT CERTAIN (the prover, 2026-10-07): a
    # game past its listed start that the record does not yet have as over,
    # or one with no start time that could come first -- the leg may be in
    # it or the next, and the check never guesses which (reading (d)).
    if code in ("under_way", "undated"):
        when = date_words_from_iso(d["day"]) if d.get("day") else None
        game = (f"the {d.get('away')} at {d.get('home')} game"
                + (f" of {when}" if when else ""))
        unsure = (", so it cannot tell whether this leg is in that game or the "
                  "next one; this leg was not placed in a game.")
        if code == "under_way":
            return (f"The record does not yet have {game} as over, though it is "
                    f"past its listed start" + unsure)
        return f"The record has no start time yet for {game}" + unsure
    return (f"No player called {player} is in the record's game stats this "
            f"season ({d.get('season')})" + tail)


def entry_check_leg_words(player: str, side: str, line: float, stat: str) -> str:
    """"Josh Allen over 250.5 passing yards": a leg as typed."""
    return f"{player} {side} {line:g} {stat}"


def entry_check_leg_detail_words(kind: str, original_line: float | None) -> str:
    """"goblin · discounted from 260.5": the leg's kind, and its discount."""
    out = kind
    if original_line is not None:
        out += f" · discounted from {original_line:g}"
    return out


def entry_check_size_words(app_words: str, entry_type: str, legs: int) -> str:
    """"PrizePicks 3-pick power": the key a payout is remembered under."""
    return f"{app_words} {int(legs)}-pick {entry_type}"


def entry_check_leg_label(n: int) -> str:
    """"Leg 2": a leg's place in the entry, over its fields."""
    return f"Leg {int(n)}"


def entry_check_flex_row_words(right: int, legs: int) -> str:
    """"4 of 5 right pays": one row of a flex table."""
    return f"{int(right)} of {int(legs)} right pays"


def entry_check_payout_words(payout: dict, legs: int) -> str:
    """"3x", or "5 of 5 right pays 10x, 4 of 5 right pays 2x, 3 of 5 right pays
    0.4x, fewer pays nothing"."""
    if payout.get("table") is None:
        return f"{float(payout['multiplier']):g}x"
    rows = [f"{entry_check_flex_row_words(k, legs)} {float(v):g}x"
            for k, v in sorted(payout["table"].items(), reverse=True) if float(v) > 0]
    lowest = min((k for k, v in payout["table"].items() if float(v) > 0), default=None)
    if lowest is not None and lowest > 1:
        rows.append("fewer pays nothing")
    return ", ".join(rows)


def entry_check_remembered_words(size: str, payout_words: str,
                                 typed_utc: str | None) -> str:
    """The last payout typed for an app, entry type and size, offered and not
    confirmed (reading (e))."""
    when = date_words_from_iso((typed_utc or "")[:10]) if typed_utc else None
    return (f"Last typed for {size}" + (f", {when}" if when else "")
            + f": {payout_words}. Confirm it is what the app shows for this "
              f"entry, or type what it shows.")


def entry_check_remembered_now_words(size: str, payout_words: str) -> str:
    return (f"Remembered for {size}: {payout_words}. It is offered next time, "
            f"to confirm again.")


def entry_check_breakeven_words(breakeven: float) -> str:
    """"57.74%": the chance each leg needs, to a hundredth of a point."""
    return f"{breakeven * 100:.2f}%"


def entry_check_breakeven_tip(payout: dict, legs: int) -> str:
    """How the break-even per leg was worked out, from the payout typed."""
    if payout.get("table") is None:
        return (f"The chance each leg needs for the entry to return what it "
                f"costs: {float(payout['multiplier']):g}x to the power of minus "
                f"1/{int(legs)}. From the payout alone, whatever each leg's "
                f"kind.")
    return ("The chance each leg needs, the legs independent, for the table "
            "typed to return what the entry costs: solved step by step to well "
            "under a hundredth of a point. From the table alone, whatever each "
            "leg's kind.")


def _entry_number(x: float) -> str:
    """A return per unit to five places, trailing zeros dropped past two:
    "-0.25", "+0.125", "+0.03125"."""
    text = f"{x:+.5f}"
    while text.endswith("0") and len(text.split(".")[1]) > 2:
        text = text[:-1]
    return "+0.00" if text in ("-0.00", "+0.00") else text


def entry_check_return_words(expected: float) -> str:
    """"-0.25 per unit": what the entry returns per unit, less the unit."""
    return f"{_entry_number(expected)} per unit"


#: AN EVEN CHANCE EXACTLY AT THE BREAK-EVEN, in points (the prover,
#: 2026-10-07): float noise only -- 4x on two legs is exactly one half, and
#: 8x on three a hair past it in floating point.
_ENTRY_EXACT_POINTS = 1e-7


def entry_check_gap_words(points: float, *, raw: float | None = None) -> str:
    """"2.86 points over its break-even": an even chance against the chance
    each leg needs. "Exactly" ONLY WHERE IT IS (the prover, 2026-10-07): as
    handed, 3.9999x on two legs -- red, "-0.00003 per unit" -- was "exactly at
    its break-even" because its gap rounds to 0.00; `raw`, the gap unrounded,
    says which side of the break-even a gap under a hundredth sits."""
    if abs(points) < 0.005:
        if raw is None or abs(raw) < _ENTRY_EXACT_POINTS:
            return "exactly at its break-even"
        side = "over" if raw > 0 else "under"
        return f"less than a hundredth of a point {side} its break-even"
    side = "over" if points > 0 else "under"
    return f"{abs(points):.2f} points {side} its break-even"


def entry_check_promo_words(kind: str, typed: dict, offered: dict, legs: int, *,
                            percent: float | None = None,
                            cap_units: float | None = None,
                            entry_units: float | None = None) -> str:
    """THE PROMO, CONVERTED AND SHOWN (the brief: "converted and shown"): the
    payout the entry has with it, beside the payout typed."""
    was = entry_check_payout_words(typed, legs)
    now = entry_check_payout_words(offered, legs)
    table = typed.get("table") is not None
    if kind == "raised":
        if table:
            return f"With the promo: {now}. Without it: {was}."
        return f"With the promo the app pays {now}, from {was}."
    share = f"A {percent:g}% share of the winnings added"
    if cap_units is not None:
        # "1 unit", never "1 units" (the prover, 2026-10-07).
        units = "unit" if cap_units == 1 else "units"
        share += f", at most {cap_units:g} {units} on a {entry_units:g}-unit entry,"
    if table:
        out = f"{share} makes the table {now}. Without it: {was}."
    else:
        out = f"{share} makes the entry pay {now}, from {was}."
    if cap_units is not None:
        from . import entry_math as _entry_math
        uncapped = _entry_math.with_a_profit_promo(typed, percent=percent)
        if entry_check_payout_words(uncapped, legs) != now:
            out += (f" The cap holds it there: without the cap it would pay "
                    f"{entry_check_payout_words(uncapped, legs)}.")
    return out


def entry_check_verdict_words(signal: str, points: float, *, promo: bool = False,
                              raw: float | None = None) -> str:
    """Reading (h)'s verdict in words, beside its outline (or none). ON THE
    ENTRY AS OFFERED: with a promo, the verdict and its gap are the promo's,
    and the words say so (the render of 2026-10-07: "5.28 points over each
    leg's break-even" stood under a break-even line of 57.74%, the one
    without the promo)."""
    bar = f"{_config.PICK_MIN_EDGE * 100:g}"
    with_it = " with the promo" if promo else ""
    if signal == "clears":
        return (f"Clears the bar at coin flips{with_it}: an even chance is "
                f"{points:.2f} points over each leg's break-even{with_it}, {bar} "
                f"or more.")
    if signal == "costs":
        return (f"Costs at coin flips{with_it}: with every leg an even chance, "
                f"the entry returns less than it costs.")
    if points == 0 and raw is not None and abs(raw) >= _ENTRY_EXACT_POINTS:
        # WITHIN A HUNDREDTH, NOT EXACTLY (the prover, 2026-10-07): as handed,
        # 4.0001x on two legs, "+0.00002 per unit", was said to return
        # "exactly what it costs".
        side = "over" if raw > 0 else "under"
        return (f"No outline: at coin flips{with_it} an even chance is less than "
                f"a hundredth of a point {side} each leg's break-even, and the bar "
                f"needs it {bar} points or more over.")
    if points == 0:
        # AN ENTRY THAT RETURNS EXACTLY ITS COST (2026-10-07, resumed build):
        # "0.00 points over" said of a break-even of exactly one half.
        return (f"No outline: at coin flips{with_it} the entry returns exactly "
                f"what it costs. Each leg's break-even is an even chance, and the "
                f"bar needs it {bar} points or more under one.")
    return (f"No outline: at coin flips{with_it} the entry returns at least what "
            f"it costs, but an even chance is {points:.2f} points over each leg's "
            f"break-even, under the {bar} the bar needs.")


def entry_check_verdict_tip(bar: float) -> str:
    return (f"The colour law read at coin flips, with no model: a green outline "
            f"where every leg's break-even is {bar * 100:g} points or more under "
            f"an even chance, a red one where the entry returns less than it "
            f"costs with every leg an even chance, and none between.")


def _entry_leg_list(indices: list[int]) -> str:
    names = [str(i + 1) for i in indices]
    if len(names) == 1:
        return f"Leg {names[0]}"
    return "Legs " + ", ".join(names[:-1]) + " and " + names[-1]


def entry_check_one_game_words(groups: list[tuple[list[int], str | None]],
                               unchecked: list[int], n_legs: int) -> list[str]:
    """THE ONE-GAME FLAG (the brief: "a same-game flag on legs from one game
    ('these legs move together; the math assumes they don't'), no correlation
    estimate (LAW 2)"): one sentence for each game holding two legs or more,
    and one for the legs that could not be placed and so were not checked
    (reading (d))."""
    out = []
    for legs, game in groups:
        where = f", {game}" if game else ""
        out.append(f"{_entry_leg_list(legs)} are in one game{where}: these legs "
                   f"move together; the math assumes they don't.")
    placed = n_legs - len(unchecked)
    if not groups:
        if not unchecked:
            out.append("No two legs are in one game.")
        elif placed >= 2:
            out.append("No two of the legs placed are in one game.")
    if unchecked and len(unchecked) == n_legs:
        out.append("No leg could be placed in a game, so none was checked "
                   "against the others for a game they share.")
    elif unchecked:
        one = len(unchecked) == 1
        out.append(f"{_entry_leg_list(unchecked)} could not be placed in a game, "
                   f"so {'it was' if one else 'they were'} not checked against "
                   f"the others for a game they share.")
    return out


# ---------------------------------------------------------------------------
# THE MODEL AS A VETO (GRIDIRON_ENTRY_CHECK step 2, the brief of 2026-09-30
# with ruling D of 2026-10-05; built 2026-10-07): "each leg's model
# probability at the typed line if the model forecasts that player and stat;
# at a discounted line only if the model can state a probability at any line,
# otherwise 'can't price this discount'. Show model EV beside coin-flip EV and
# flag legs below their break-even, with the model's record for that stat in
# plain words. The model only flags; it never raises a verdict." Ruling D:
# "Written inactive; shown as 'not yet proven' until its record clears 100
# graded legs." The internal name M4 never reaches a reader (PLAIN WORDS): it
# is "the model's chance at your line", read from its projection.
# ---------------------------------------------------------------------------

def m4_unproven_words(graded: int, gate: int) -> str:
    """"not yet proven · 0 of 100 graded legs": beside every number the model
    states at a line it was never asked (ruling D; reading (c))."""
    legs = "leg" if gate == 1 else "legs"
    return f"not yet proven · {int(graded)} of {int(gate)} graded {legs}"


def m4_unproven_tip(graded: int, gate: int) -> str:
    """Why the model's chance at your line is not yet proven, and why its
    count is what it is."""
    return (f"A first version of the model's chance at any line, written "
            f"inactive: it counts as proven only once {int(gate)} legs it priced "
            f"have been graded, and {int(graded)} have been, because no checked "
            f"entry is kept and graded yet (the check's next step). Until then it "
            f"only flags a leg, and never makes a pick, an outline or a verdict.")


def entry_check_model_words() -> dict:
    """The fixed words of the model's part of the entry check."""
    return {
        "heading": "The model at your lines",
        "line_model_return": "With the model's chances, per unit",
        "line_model_promo_return": "With the model's chances and the promo, per unit",
        "model_return_tip": ("What the entry returns per unit with each leg at the "
                             "model's chance at your line, the legs taken as "
                             "independent, less the unit. Not yet proven."),
        # "THE VERDICT", NEVER "THE OUTLINE" (the render of 2026-10-07): an
        # entry with no outline was told of "the outline above".
        "only_flags": ("It only flags: the verdict above is the arithmetic at "
                       "coin flips, and the model never changes it."),
        "nothing_asked": ("The model states a chance on none of these legs, so it "
                          "flags nothing."),
    }


def entry_check_m4_leg_words(state: str, *, player: str = "", stat_words: str = "",
                             typed_stat: str = "", side: str = "", line: float | None = None,
                             chance: float | None = None,
                             projection: float | None = None, unproven: str = "") -> str:
    """What the model says of one leg, at the line typed: its chance and what
    it is read from, or why it says nothing (the states of `m4.reading`, and
    "unplaced" and "not_a_stat" of the check's own)."""
    if state == "priced":
        out = (f"The model: {chance * 100:.2f}% {side} {line:g}, from its "
               f"projection of {projection:.2f} {stat_words} ({unproven}).")
        if line is not None and float(line) == int(float(line)):
            out += (f" A line of {line:g} can be landed on exactly; that is counted "
                    f"here as not won.")
        return out
    if state == "no_forecast":
        return (f"The model made no forecast of {player}'s {stat_words} for this "
                f"game, so it says nothing of this leg.")
    if state == "no_projection":
        return (f"The model has no projection for {stat_words} yet, so it states "
                f"no chance at your line.")
    if state == "no_fit":
        return (f"Nothing has been fitted yet for how far {stat_words} stray from "
                f"the model's projections, so it states no chance at your line.")
    if state == "not_a_stat":
        return (f"The model forecasts no stat it can match to “{typed_stat}”: "
                f"choose one of the stats offered to ask it.")
    return "This leg was not placed in a game, so the model was not asked."


def entry_check_m4_discount_words(chance_before: float | None, original_line: float,
                                  side: str, unproven: str = "") -> str:
    """A discounted leg: the model's chance at the line before the discount,
    where it can state one at any line -- else the brief's own words."""
    if chance_before is None:
        return "Can't price this discount."
    return (f"Before the discount, at {side} {original_line:g}, the model gives it "
            f"{chance_before * 100:.2f}% ({unproven}).")


def entry_check_m4_gap_words(points: float, *, raw: float, promo: bool,
                             unproven: str = "") -> str:
    """"By the model, this leg is 6.47 points over its break-even": the
    model's chance at the line typed against the chance each leg needs (the
    entry as offered, its promo in) -- an edge, drawn as a number with "not
    yet proven", never a pick, a badge or an outline (reading (d))."""
    with_it = " with the promo" if promo else ""
    return (f"By the model, this leg is {entry_check_gap_words(points, raw=raw)}"
            f"{with_it} ({unproven}).")


def entry_check_m4_lean_words() -> str:
    """THE FLAG (the brief: "flag legs below their break-even"): beside a leg
    whose chance by the model is under its break-even. Words only, never a
    colour or an outline (the model only flags)."""
    return "The model leans against this leg."


def entry_check_m4_record_words(stat_words: str, n: int, right: int, gate: int) -> str:
    """THE MODEL'S RECORD FOR THE STAT IN PLAIN WORDS, WITH ITS N (LAW 4): the
    blind record's own questions of the stat, at the model's own lines."""
    head = f"Its record on its own {stat_words} questions: "
    if n == 0:
        return head + f"none settled yet; {gate} are needed before it says anything."
    said = f"right {right} of {n} settled"
    if n < gate:
        return head + f"{said}; {gate - n} more are needed before that record says anything."
    return head + f"{said}."


def entry_check_m4_tip(projection: float, stat_words: str, fit_n: int,
                       unproven_tip: str) -> str:
    """How the model's chance at your line was read."""
    places = "player-game" if fit_n == 1 else "player-games"
    return (f"Read from the model's projection of {projection:.2f} {stat_words} for "
            f"this player and game, written with its forecast before any line, "
            f"and from how far {stat_words} have strayed from its projections on "
            f"{fit_n} settled {places}. {unproven_tip}")


def entry_check_m4_summary_words(flagged: list[int], priced: list[int], n_legs: int,
                                 unproven: str) -> str:
    """Beside the verdict: which legs the model leans against, in its words,
    and that it only flags."""
    words = entry_check_model_words()
    if not priced:
        return words["nothing_asked"]
    if flagged:
        out = f"The model leans against {_entry_leg_list(flagged).lower()} ({unproven})."
    elif len(priced) == 1:
        # ONE LEG PRICED (the render of 2026-10-07): "none of the leg" was
        # drawn.
        out = f"The model does not lean against the one leg it can price ({unproven})."
    else:
        out = (f"The model leans against none of the {len(priced)} legs it can price "
               f"({unproven}).")
    unpriced = [i for i in range(n_legs) if i not in priced]
    if unpriced:
        one = len(unpriced) == 1
        out += (f" {_entry_leg_list(unpriced)} {'has' if one else 'have'} no chance "
                f"from it.")
    return out + " " + words["only_flags"]


def entry_check_m4_return_missing_words(unpriced: list[int]) -> str:
    """No return at the model's chances unless every leg has one."""
    one = len(unpriced) == 1
    return (f"The return at the model's chances needs its chance on every leg: "
            f"{_entry_leg_list(unpriced).lower()} {'has' if one else 'have'} none.")


def prop_m4_words(state: str, *, stat_words: str, unproven: str = "") -> str:
    """ON A PROPS TILE (2026-10-07): whether the model can state a chance at the
    line the operator types for this player and stat in Check an entry --
    never a chance here, because no line on the tile is one only this reading
    can price (the venue's main line is read by the model's own rules, and
    the tile's own question is the model's own). Short: its tooltip says
    how."""
    if state == "priced":
        return f"type it in Check an entry · {unproven}"
    if state == "no_fit":
        return f"none yet: nothing fitted for {stat_words}"
    return f"none: no projection for {stat_words}"


def prop_m4_tip(state: str, *, stat_words: str, projection: float | None = None,
                fit_n: int | None = None, unproven_tip: str = "") -> str:
    """How the model would read the app's line for this player and stat, or
    why it cannot."""
    if state == "priced":
        places = "player-game" if fit_n == 1 else "player-games"
        return (f"Type the app's line for this player and stat in Check an entry: the "
                f"model states its chance there from its projection of "
                f"{projection:.2f} {stat_words} and how far {stat_words} have "
                f"strayed from its projections on {fit_n} settled {places}. "
                f"{unproven_tip}")
    if state == "no_fit":
        return (f"The model has a projection here, but nothing has been fitted yet "
                f"for how far {stat_words} stray from its projections on settled "
                f"games, so it states no chance at another line.")
    return (f"The model stored no projection of this player's {stat_words} with its "
            f"forecast (it answers a yardage stat as a yes-or-no question at its own "
            f"line), so it states no chance at the app's line. None is implied from "
            f"its own answer.")


# ---------------------------------------------------------------------------
# AN INTERNAL VERSION NAME, ONLY IN A TOOLTIP (operator question 19, ruled
# 2026-09-27, third set: "fixed in the board: headings in plain words;
# internal version names only in a tooltip"; built by the board merge,
# 2026-09-29)
# ---------------------------------------------------------------------------
#
# The Record page painted the blend's version ("b1") beside the heading
# "Priced, and against the close" on every sport, and the ordering's ("r3")
# beside "Did the ordering earn its place". A version name is how a stored row
# is matched to the formula that wrote it; a reader needs it to match, never
# to read. So the heading says what the panel is, in words, and the name sits
# in the heading's tooltip with a sentence saying what it names.

#: What each kind of version names, said once.
VERSION_KIND_WORDS = {
    "blend": ("the formula that mixes the model's number with the market's; "
              "every priced row carries it"),
    "ranker": ("the formula that orders a slate's questions; every rank "
               "carries it"),
    "factor_set": ("the set of declared factors a forecast was made from; "
                   "every forecast carries it"),
    "correction": ("the correction's number within its category; every "
                   "forecast and recommendation made under it carries it"),
    "commit": ("the commit of this project whose prompt code rebuilt this "
               "prompt; the reconstruction carries it"),
}


def version_tip(kind: str, name) -> str:
    """The tooltip that carries an internal version name: "Version b1: the
    formula that mixes ..." -- the one place the name may appear."""
    return f"Version {name}: {VERSION_KIND_WORDS[kind]}."


def factor_set_words(activated: str | None) -> str:
    """A factor set said by the day it came into force -- "since Thursday 24
    September", beside the label "The factor set in force" -- where its name
    is the tooltip's (question 19; the board merge, 2026-09-29)."""
    when = date_words_from_iso((activated or "")[:10]) if activated else None
    return f"since {when}" if when else "no day on record"
