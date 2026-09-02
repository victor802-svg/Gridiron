"""One pick, one side, in every place it is written (ruling E1).

THE DEFECT THIS CLOSES was live on nine cards on 2026-09-01. College football
stores a failed spread as `"fail to cover"`; `SIDE_WORDS` knew only
`"not_cover"`; and the lookup was `SIDE_WORDS.get(side, "covers")` -- so the
sentence under a prediction that Nebraska would FAIL to cover read "Nebraska
Cornhuskers covers -24.5".

Every standing scan passed while that shipped. They all check that prose goes
THROUGH the humaniser; none checked that the humaniser had words for what it
was handed. The default was the bug.
"""

from __future__ import annotations

import pytest

from gridiron import audit, config, db, language, views


NAMES = {
    "ALA": {"full": "Alabama Crimson Tide", "city": "Alabama"},
    "ECU": {"full": "East Carolina Pirates", "city": "East Carolina"},
}


def _spread(side):
    return {"market_type": "spread", "model_side": side, "line_asked": -24.5,
            "subject": "ALA", "opponent": "ECU", "team_names": NAMES,
            "model_prob": 0.76}


def test_a_no_side_spread_names_the_other_team_with_the_flipped_line():
    """The whole of E1 in one assertion."""
    card = _spread("fail to cover")
    assert language.tile_line(card) == "East Carolina +24.5"
    assert language.tile_label(card) == "covers"
    assert language.phrase(card) == "East Carolina covers +24.5"


def test_a_yes_side_spread_is_untouched():
    card = _spread("cover")
    assert language.tile_line(card) == "Alabama -24.5"
    assert language.tile_label(card) == "covers"
    assert language.phrase(card) == "Alabama covers -24.5"


def test_the_name_and_the_number_flip_together_or_not_at_all():
    """The failure mode of the first attempt, asserted directly.

    Negating the line without swapping the club produced "Alabama +30.5" for a
    pick AGAINST Alabama -- the inversion in miniature, in the one place a
    reader has least room to notice it.
    """
    no_side = language.tile_line(_spread("fail to cover"))
    yes_side = language.tile_line(_spread("cover"))
    assert no_side.startswith("East Carolina") and "+24.5" in no_side
    assert yes_side.startswith("Alabama") and "-24.5" in yes_side
    # Never the two halves crossed.
    assert not no_side.startswith("Alabama")
    assert "+" not in yes_side


def test_an_unknown_side_raises_rather_than_borrowing_another_verb():
    """The class fix. A guess that reads well is worse than one that reads oddly."""
    with pytest.raises(language.UnknownSide):
        language.side_word("fail to score")
    # Where a sentence must exist regardless, it degrades to the side's own
    # name: odd and true, rather than fluent and false.
    assert language.side_word_or_side("fail to score") == "fail to score"


def test_every_side_that_shipped_has_words():
    """Both spellings live in the record and both must render."""
    for side in ("cover", "not_cover", "fail to cover", "win", "lose",
                 "over", "under"):
        assert language.side_word(side)


def test_the_side_in_the_record_has_words(conn):
    audit.check_every_side_has_words(conn)


def test_a_pick_reads_the_same_in_all_four_places(conn):
    """The tile, the sentence, the why heading and the history row.

    Equality across them is the brief's own test, and it is the thing that
    would have caught the nine cards: the tile said "misses" while the
    sentence said "covers", about one prediction, on one card.
    """
    for sport in config.SPORTS:
        data = views.week(conn, sport)
        for card in data["cards"]:
            if card["market_type"] not in ("spread", "moneyline"):
                continue
            tile = card["tile_line"]
            heading = (card["why"] or {}).get("heading", "")
            named = heading.replace("Why ", "")
            if not named or named == "this pick":
                continue
            assert tile.startswith(named), (
                f"{sport}: the tile says {tile!r} and the why says {heading!r} "
                f"-- one pick, two sides")
            assert card["phrase"].startswith(named), (
                f"{sport}: the sentence {card['phrase']!r} does not name "
                f"{named!r}, which the tile does")


def test_the_shipped_cards_agree_with_the_one_door(conn):
    """No card diverges from what the humaniser would produce for it."""
    for sport in config.SPORTS:
        cards = views.week(conn, sport)["cards"]
        assert not audit.pick_disagrees_with_its_label(cards)


def test_the_slate_is_named_in_date_words_not_its_key():
    assert language.date_words(20260905) == "Saturday 5 September"
    assert language.slate_title(2026, 20260905, "day") == "Saturday 5 September, 2026"
    # A week-numbered sport keeps its number, which is already a word people use.
    assert language.slate_title(2026, 1, "week") == "Week 1, 2026"
    assert language.date_words(1) is None


def test_the_boundary_of_what_counts_as_a_date_key():
    """MENTOR section 3, at the edges of the eight-digit range."""
    assert language.date_words(19000101) is not None
    assert language.date_words(29991231) is not None
    assert language.date_words(18991231) is None
    assert language.date_words(30000101) is None
    # And a month or day out of range is not a date, so it is not translated.
    assert language.date_words(20261301) is None


def test_the_plain_words_scan_now_catches_a_slate_key():
    assert audit.plain_words_violations("Season 2026, week 20260905")
    assert not audit.plain_words_violations("Saturday 5 September, 2026")
    # A season is four digits and must not trip it.
    assert not audit.plain_words_violations("Season 2026, Week 1")


def test_the_chance_clause_uses_one_notation_for_every_side():
    """Found in the 390px render: "TOL wins" beside "Tulsa wins".

    The clause defended the tricode on two grounds -- a full name wraps in a
    narrow column, and a club name is plural, so "Colorado Rockies wins" is
    wrong. The school form answers both: singular, short, and a name rather
    than a code. What it must not do is use one notation for the side that got
    flipped and another for the side that did not.
    """
    yes = {"market_type": "moneyline", "model_side": "win", "subject": "TLSA",
           "opponent": "OKST", "team_names": {
               "TLSA": {"full": "Tulsa Golden Hurricane", "city": "Tulsa"},
               "OKST": {"full": "Oklahoma State Cowboys", "city": "Oklahoma State"}},
           "model_prob": 0.7}
    no = dict(yes, model_side="lose")
    assert language.chance_clause(yes) == "Tulsa wins"
    assert language.chance_clause(no) == "Oklahoma State wins"
    # Neither says a tricode.
    assert "TLSA" not in language.chance_clause(no)
    assert "OKST" not in language.chance_clause(no)


def test_the_chance_clause_takes_the_singular_verb():
    """"Ohio covers", never "Ohio Bobcats covers"."""
    card = _spread("fail to cover")
    clause = language.chance_clause(card)
    assert clause == "East Carolina covers"
    assert "Pirates" not in clause, "the plural mascot form is back"
