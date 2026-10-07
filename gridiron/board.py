"""The board: game rows and prop tiles (GRIDIRON_BOARD, operator ruling 2026-09-24).

Built FROM the slate the page already has -- `views.week`'s cards and its
Today block -- and never from a second read of the market. A game row is the
slate's questions grouped by game with the loudest one on the face; a prop
tile is a prop question with the club's measured colours around it. Every
visible string is composed in `gridiron.language`; this module chooses which
words go where and decides nothing about wording.

WHAT A ROW MAY CARRY IN EACH STATE follows the laws already in force. A live
row shows the score, the period, when it was last read, and the pregame
figure with the word "pregame" on it -- no price, no size, no tap
(`audit.live_card_faults`, extended to the board's own field names). A
settled row is filled with its verdict and nothing else changes colour. A
signal never renders without the record badge beside it
(`audit.board_signal_faults`).

A PROP TILE IS ONE PLAYER AND ONE STAT (operator ruling C, 2026-10-05;
built 2026-10-06): "Never present a venue ladder rung as a pick'em pick. Per
player and stat: the model's projection and its chance at the market's main
line (the rung nearest 50c), labelled 'about the app's line, check the app'.
The full ladder moves to its own 'Kalshi ladder' view." Until then the tile
was the question this record asked at its own line, ranked by a CUSHION
against a declared 3x (`config.PICKEM_TWO_PICK_MULTIPLE`, gone): a break-even
from a multiplier nobody typed, on every tile. Now each upcoming tile carries
the projection (`_leg`), the chance at the venue's main line where the model
states one, the break-even of each power payout the operator TYPED (C.3;
none until typed, and the page asks), and a pick only where an edge clears
the bar (B.2). The question the record asked stays on the tile, said as the
model's own question, with no break-even beside it. The venue's ladders are
read through one place (`_venue_prop_ladders`) -- none is read today -- and
the Kalshi ladder view lists them, every rung under its own contract and
never a pick.

PICKS ARE RANKED BY EDGE, NEVER BY CHANCE (operator ruling B, 2026-10-05;
built 2026-10-07). A row's questions are its picks by their edge after fees,
then the sport's declared market order (`_row_order`); its lead is the first
of them -- never the surest, which it was -- and "Model's pick" heads only a
pick, the one door's answer (`picks.judge`, carried on the Today card): three
points or more after fees, the writer's own bar, and for a Kalshi game market
its gate at the venue's price. A row's face draws its chance, its multiplier
and its edge (B.3); a slate with a question to come and no pick says "Nothing
worth taking today" above its rows (B.4); and a recommendation that is not a
pick is drawn with its numbers and the words saying why (reading (d)).
"""

from __future__ import annotations

import json
import sqlite3

from . import bet, calibration, config, language
from .data import teams


#: The two forecasters, in the order the board lists them on an expanded row.
FORECASTERS = tuple(config.FORECASTER_LABELS)


def breakeven(multiple: float, legs: int) -> float:
    """A leg's break-even in a POWER entry of `legs` legs paying `multiple`
    times its stake: every leg must hit, so M * p**N = 1 and p = M**(-1/N)
    (operator ruling C.3, 2026-10-05; the reading of 2026-10-06 recorded in
    docs/REPAIR_STATE.md). 57.7% for 2 legs at 3x, 55.0% for 3 at 6x. Of a
    payout the operator TYPED, never of a declared one."""
    return float(multiple) ** (-1.0 / int(legs))


def typed_payouts(conn: sqlite3.Connection) -> list[dict]:
    """The pick'em power payouts the operator TYPED, each with when (C.3,
    reading (b): stored in the settings store, append-only, shown with when
    they were typed). One entry per `config.PICKEM_POWER_ENTRIES`, its
    `multiple` None where nothing was typed -- and then no break-even, no
    edge and no pick is drawn against it. A stored value that is not a
    payout (written round `settings.set_value`'s check) is read as not
    typed, never repaired into one."""
    from . import settings

    out = []
    for legs, name in config.PICKEM_POWER_ENTRIES:
        got = settings.typed(conn, name)
        multiple = None
        if got is not None:
            try:
                multiple = float(got["value"])
            except (TypeError, ValueError):
                multiple = None
            if multiple is not None and not 1.0 < multiple <= 100.0:
                multiple = None
        out.append({"legs": legs, "name": name, "multiple": multiple,
                    "typed_utc": got["typed_utc"] if multiple is not None else None})
    return out


def _state_of(card: dict) -> str:
    from .views import card_state

    return card_state(card.get("game_status"))


def _signal(card: dict, entry: dict | None, state: str) -> str:
    """Which of the colour law's four signals a question wears, or none.

    From the Today block's own grouping, so the row cannot disagree with the
    groups it replaced: an entry the block put under CLEARS wears the green
    outline; a priced one whose edge is negative wears the red outline; a
    settled question is filled with its verdict.
    """
    if state == "final":
        if card.get("voided"):
            return "withdrawn"
        outcome = card.get("outcome")
        if outcome is None:
            return "none"
        return "won" if outcome else "lost"
    if state == "live" or entry is None:
        return "none"
    if entry.get("group") in ("clears", "below_floor"):
        return "clears"
    cents = entry.get("edge_cents")
    if cents is not None and cents < 0:
        return "costs"
    return "none"


def _settled_n(conn: sqlite3.Connection, cache: dict, *, sport: str,
               market_type: str, prop_type: str | None, predictor: str) -> int:
    """How many questions in this category have settled: the badge's numerator.

    THROUGH THE EDGE GATE'S OWN DOOR (the board merge, 2026-09-29):
    `shortlist.settled_for_gate`, the count a recommendation's gate opens on,
    which is `calibration.resolved` for ONE forecaster -- one standing row per
    distinct bet on question 17's key (`bet.same` inside
    `calibration.standing_row_clause`), its final pass before the start
    standing by question 27's order. The board counted the same rows by
    calling `resolved` itself; it asks the door now, so the badge beside a
    signal and the gate behind the signal are one count by construction."""
    from . import shortlist

    key = (sport, market_type, prop_type, predictor)
    if key not in cache:
        cache[key] = shortlist.settled_for_gate(
            conn, sport, market_type, prop_type, predictor)
    return cache[key]


def _badge(n: int) -> dict:
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    return {"badge_n": n, "badge_gate": gate,
            "badge_words": language.badge_words(n, gate)}


def _club(sport: str, tricode: str | None, names: dict) -> dict:
    """One club's block on a row: tricode, name, and its measured colours."""
    from .views import team_colours

    colours = team_colours(sport, tricode)
    return {
        "tricode": tricode or "",
        "name": language.team_name(tricode, names, "full"),
        "colour": colours["primary"],
        "on_white": colours["on_white"],
        "secondary": _secondary(colours),
        "known": colours["known"],
    }


def _question_block(card: dict, entry: dict | None, *, state: str, taken: bool,
                    forecaster: str, n_settled: int, hours: float,
                    unit_dollars: float | None,
                    past_its_start: bool = False) -> dict:
    """One question as the board shows it: on the row's face or as a tile.

    THE NUMBERS ARE THE TODAY CARD'S where one exists -- the same price, the
    same payout, the same edge the groups showed -- and the model's own where
    the question was never priced.

    `past_its_start` (Q38's prover, 2026-10-07): the question's game is not
    still upcoming (`recommend.not_still_upcoming`), so it has no price, and
    a row still drawn as to come says why in its price slot.
    """
    label = config.FORECASTER_LABELS.get(forecaster, forecaster)
    shown = card.get("shown_prob")
    if shown is None:
        shown = card.get("model_prob")
    # THE PRICED NUMBER IS THE CORRECTED ONE (the board merge, 2026-09-29;
    # GRIDIRON_REPAIR item 3 and operator question 32). Where the Today block
    # priced the question, the old card's model chip read the entry's
    # `fair_value` -- the claim corrected through `correction.shown_proposition`
    # by the correction the category's own activation row puts in force
    # (`recommend.correction_instant`), turned to the side the question names.
    # The board read the card's stored number instead, which agrees only
    # while nothing is in force. It reads the entry's now, as the chip did;
    # an unpriced question keeps the number the slate stored for it.
    # AND IT RUNS ON THE PAGE'S OWN ENTRIES (the prover, 2026-09-29): the
    # index holds `views._today_card`'s cards, which carried the chip's words
    # and not `fair_value` or `question_takes_the_proposition`, so this
    # branch never ran on a real payload and its test handed it a dict made
    # by hand. The card carries both numbers now.
    # A SIDE THAT CANNOT BE PLACED IS REFUSED, NOT PASSED (the operator's
    # ruling of 2026-09-30). This turned on `is False` alone, so a question
    # whose side the one place could not place -- college football's "fail
    # to cover", before the ruling -- was drawn on the claim's own numbers:
    # "North Texas -6.5 · 24% · 48¢" for rec 111, whose numbers are about
    # 76% and 51.5¢. A priced block with no placed side raises by name now,
    # and the API answers 500 rather than paint the other side's numbers.
    takes = entry.get("question_takes_the_proposition") if entry is not None else None
    flip = takes is False
    corrected = entry is not None and entry.get("fair_value") is not None
    if (corrected or (entry is not None and entry.get("price") is not None)) \
            and takes is not True and takes is not False:
        from .subjects import UnplaceableSide

        raise UnplaceableSide(
            f"THE BOARD REFUSES A SIDE IT CANNOT PLACE: question "
            f"{card.get('prediction_id')} ({card.get('market_type')} "
            f"{card.get('model_side')!r}, {card.get('phrase')!r}) "
            f"is priced, and which side its question names against the claim's "
            f"proposition cannot be said ({takes!r}), so no chance, price or "
            f"payout is drawn rather than the other side's (the ruling of "
            f"2026-09-30)")
    if corrected:
        fair = entry["fair_value"]
        shown = 1.0 - fair if flip else fair
    # THE WORDS OF THE CONTRACT THE NUMBERS BELONG TO (pick-number step A,
    # 2026-09-30; findings 2 and 5). The block named its question through
    # `language.pick_line_words(card)` -- the QUESTION's line -- beside the
    # Today card's numbers, which are its claim's, read at the venue's line:
    # rec 111 drew "North Texas -6.5 · 76% · 52c", every number North Texas
    # +1.5's. The Today card names the contract its numbers belong to through
    # the one door (`views._the_contract`), and the block draws those words;
    # where there is no Today card the numbers are the question's own, and so
    # are the words. A card carrying numbers and no words for them is
    # refused by name, never drawn under the question's line.
    carries = entry is not None and (
        corrected or entry.get("price") is not None
        or (state == "live" and entry.get("pregame_words")))
    if carries and "line_words" not in entry:
        raise language.LineNotNamed(
            f"THE BOARD REFUSES A NUMBER WHOSE LINE IT HAS NOT NAMED: question "
            f"{card.get('prediction_id')} ({card.get('phrase')!r}) is drawn with "
            f"its Today card's numbers, and the card names no contract for them "
            f"(`views._the_contract`), so they are not drawn under the "
            f"question's words (pick-number step A, 2026-09-30)")
    if entry is not None and "line_words" in entry:
        line_words = entry["line_words"]
        question_words = entry.get("question") or card.get("phrase") or ""
    else:
        line_words = language.pick_line_words(card)
        question_words = card.get("phrase") or ""
    market = card.get("market") or card.get("market_type")
    signal = _signal(card, entry, state)
    # THE CONTRACT BOUGHT IS THE HEADLINE (operator question 37, ruled
    # 2026-10-05: "headline the contract the recommendation buys; the model's
    # own side named beside it"). Where the Today card's recommendation buys
    # the other side of its question's words, the card's words, its turned
    # numbers (`question_takes_the_proposition` is the side its words name)
    # and its size, edge and outline are all that contract's, and the
    # model's own side and number travel beside them (`own_side_words`) --
    # on an upcoming row only: a live row carries nothing that can be acted
    # on, and a finished row is the forecast's own verdict.
    own_side = (entry or {}).get("own_side_words") if state == "upcoming" else None
    price = entry.get("price") if entry else None
    pays = entry.get("payout") if entry else None
    # THE PRICE AND THE PAYOUT OF THE SIDE THE QUESTION NAMES (the prover of
    # the board merge, 2026-09-29; the wrong-side defect of 2026-09-07). The
    # entry prices the claim's FIXED proposition -- the home side, the over --
    # and the old card turned its price round when the question names the
    # other side (`views._today_card`: "THE PRICE ROW IS ABOUT THE SIDE THE
    # QUESTION NAMES"). The board drew the entry's price and payout as they
    # came, so an away side's question read the home side's 48c and 2.06x
    # under the away side's chance. Turned here, once, as the card turns them.
    # (From 2026-09-30 the card's own `payout` is already the side its
    # question names -- pick-number finding 3 -- and the payout worked out
    # here from the turned price is that same number; the card's `price` and
    # `fair_value` stay the proposition's, the two numbers this turns.)
    if flip and price is not None:
        from .views import _payout_for

        price = 1.0 - price
        pays = _payout_for(price)
    out = {
        "prediction_id": card["prediction_id"],
        "state": state,
        "forecaster": forecaster,
        "forecaster_label": label,
        "market": market,
        "market_label": language.market_label(card),
        "subject": card.get("subject"),
        # THE CLUB THE PICK'S WORDS NAME, by the same flip as the words
        # (pick-number finding 6, 2026-09-30): My day's chip wears it. None
        # for a question about no club.
        # THE TODAY CARD'S WHERE IT DRAWS THE CARD'S WORDS (operator question
        # 37, ruled 2026-10-05): a card headlining the contract its
        # recommendation buys -- the other side of the question's words --
        # names that contract's club.
        "named_club": (entry["named_club"] if entry is not None and "named_club" in entry
                       and "line_words" in entry else language.club_named(card)),
        # THE CONTRACT'S WORDS, never the question's beside its numbers
        # (pick-number step A, 2026-09-30; above).
        "line_words": line_words,
        "question": question_words,
        "prob": shown,
        "prob_words": language.price_chip_words(
            None if shown is None else shown * 100).replace("¢", "%"),
        "signal": signal,
        "taken": taken,
        # WHETHER A VENUE PRICE STANDS BEHIND THE NUMBERS, as a fact rather
        # than as the absence of a sentence: the words say "not listed" in
        # three different ways and a reader of the payload should not have
        # to parse them.
        "priced": price is not None,
        # THE NUMBERS THE BAR AND ITS TICK ARE DRAWN FROM, on an upcoming
        # question only: a live row carries nothing a price could be read
        # off, and a settled one is a verdict.
        "price": price if state == "upcoming" else None,
        "pays": pays if state == "upcoming" else None,
        "tips": {
            # WHAT THE MODEL WAS ASKED, where the words name the venue's
            # contract at another line (step A): the chance is that
            # contract's, and the tooltip says so and names the question.
            # AND THE MODEL'S OWN SIDE, where the words name the contract the
            # recommendation buys on the other side of it (operator question
            # 37, ruled 2026-10-05).
            "prob": language.prob_tip(
                shown, label,
                asked_words=(entry or {}).get("asked_words") if corrected else None,
                own_side=own_side if corrected else None),
            "badge": language.badge_tip(n_settled, config.MIN_SAMPLE_FOR_EDGE_CLAIM,
                                        language.market_label(card)),
        },
        **_badge(n_settled),
    }
    tip = language.signal_tip(signal)
    if tip:
        out["tips"]["signal"] = tip
    # THE FLAGGED-METHOD NOTE STAYS ON THE FACE (operator ruling 2,
    # 2026-09-04): a caveat is not an explanation, and a caveat behind a
    # tooltip is a caveat most readers never reach.
    if card.get("method_note"):
        out["method_note"] = card["method_note"]
    # A CLAIM PRICED ACROSS TWO CONTRACTS (pick-number step A, 2026-09-30;
    # operator question 36 (ii) and (iii) not ruled, the conservative
    # default): the row is drawn without the price, the payout, the edge and
    # the size, with one plain sentence saying why -- on the face, as the
    # method note is, because a missing price explained only in a tooltip
    # reads as "not listed", which would be false.
    across = (entry or {}).get("across_words")
    if across:
        out["across_words"] = across
    # WHAT THE REASONING PASS WAS SENT (the rulings of 2026-09-24 and
    # 2026-09-25, re-homed by the board merge, 2026-09-29). The old card
    # carried the prompt disclosure inside its Why panel, and the Why panel
    # left with the old Picks route; a reasoning-pass question's tile on the
    # expanded row carries it now, collapsed, in the same component, its label
    # and note read off the record's own kind (`views._prompt_block`).
    if card.get("prompt"):
        out["prompt"] = card["prompt"]
    # THE EXPLANATION LIVES IN THE TOOLTIP, not in a sentence on the tile
    # (the brief's rule). The numbers line the old card kept behind "Why"
    # sits on the probability; the reasons sit on the pick's own words.
    # THE CARD'S NUMBERS LINE states the number the slate stored; a priced
    # chance is the corrected one (the prover, 2026-09-29), so its tooltip is
    # its own sentence and never a second, different figure on one number.
    if card.get("rail_line") and not corrected:
        out["tips"]["prob"] = card["rail_line"]
    sentences = ((card.get("why") or {}).get("sentences") or [])[:2]
    if sentences:
        out["tips"]["line"] = " ".join(sentences)
    elif card.get("reasoning"):
        out["tips"]["line"] = card["reasoning"]
    # THE REASONS ARE THE QUESTION'S, AND SAY SO (pick-number step A,
    # 2026-09-30). Where the words name the venue's contract at another line,
    # the forecast's reasons beside them ("the question sits 4 points above
    # what the model expects") are about the question as asked; the tooltip
    # names that question first, found reading rec 111's render.
    # ON A LIVE ROW TOO (step A's prover, 2026-09-30): its words name the
    # latest claim's contract ("New York +6.5 · pregame 30%") and its reasons
    # are the question's ("the question sits 2 points above what the model
    # expects", of New York +15.5); the prefix was asked only of a priced
    # chance, so a live row's tooltip spoke of "the question" under another
    # contract's words -- and, where the forecast gives one reason, carried
    # the market's number for it too ("The market has New York at 76%").
    asked = (entry or {}).get("asked_words")
    if asked:
        out["tips"]["line"] = " ".join(
            x for x in (asked, out["tips"].get("line")) if x)
    # THE MODEL'S OWN SIDE, ON THE FACE AND IN THE WORDS' TOOLTIP (operator
    # question 37, ruled 2026-10-05). The words name the contract bought; the
    # reasons beneath them are the model's for its own side, so the tooltip
    # says whose they are -- after what the model was asked, which names the
    # question at its own line first (step A's prover's order).
    if own_side:
        out["own_side_words"] = own_side
        out["buys_the_other_side"] = True
        reasons = out["tips"].get("line")
        if asked and reasons and reasons.startswith(asked):
            reasons = reasons[len(asked):].strip()
        out["tips"]["line"] = " ".join(x for x in (
            asked, language.own_side_reasons_words(own_side), reasons) if x)
    if state == "upcoming":
        # THE PRICE AND WHAT IT PAYS, beneath the pick, in the words the
        # Today card already used. A live row carries neither: LAW 5's
        # in-game rule, held by `audit.live_card_faults`.
        out["price_words"] = language.venue_chip_words(price, None, market=market)
        # THE ABSENCE IS SAID ONCE. With no price there is no payout either,
        # and printing the same sentence in both places is the "Payspays"
        # defect of 2026-09-08 wearing a different label.
        out["pays_words"] = (language.payout_chip_words(pays, market=market)
                             if price is not None else "")
        out["tips"]["price"] = language.price_tip(price, market, hours)
        # A GAME PAST ITS START IS NOT "NOT LISTED YET" (Q38's prover,
        # 2026-10-07). From operator question 38, ruling 2, nothing on a game
        # that is not still upcoming is priced, and a row whose game is still
        # listed 'scheduled' is drawn as to come -- every NFL, NBA and UFC
        # game being played (no live poll follows them; a loader writes the
        # result), a postponed one, and one seen under way before its
        # listed start. As first built its slot said "venue has not listed
        # this yet" and its tooltip "the first read is taken about 2 hours
        # before the start", false of a game the venue listed and that was
        # priced before it began; it says why there is no price now -- in a
        # market the venue is read for (a prop was never priced, and keeps
        # its own words).
        if price is None and past_its_start and (
                market is None or market in language.MARKETS_READ_AT_THE_VENUE):
            out["price_words"] = language.past_its_start_price_words()
            out["tips"]["price"] = language.past_its_start_price_tip()
        # AN OPENING READ AT ANOTHER LINE NAMES ITS CONTRACT (pick-number
        # step A, 2026-09-30; finding 5): the tooltip said "what a dollar
        # returns if this happens" under the question's words, of a rung the
        # question is not.
        out["tips"]["pays"] = language.pays_tip(
            pays, elsewhere=(entry or {}).get("open_read_line_words")
            if price is None else None)
        if across:
            out["price_words"] = language.across_two_contracts_price_words()
            # THE PAYOUT SLOT SAYS SO TOO (step A's prover, 2026-09-30): it was
            # left empty, and a tile draws an empty payout as "not recorded"
            # ("56% · no single contract | not recorded", rec 114's tile) --
            # false, since the venue's price was recorded. It says the payout
            # is not shown, the sentence beneath it and its tooltip why.
            out["pays_words"] = language.across_two_contracts_pays_words()
            out["tips"]["price"] = language.across_two_contracts_tip()
            out["tips"]["pays"] = language.across_two_contracts_tip()
        if entry and entry.get("size_words"):
            out["size_words"] = entry["size_words"]
        if entry and entry.get("edge_line_words"):
            # THE EDGE SAYS WHOSE IT IS (the prover of pick-number step C,
            # 2026-09-30). The figure is the better side's, and the Today card
            # labelled it "on the other side" where that is not the side the
            # question names; the tile draws the figure where the price was,
            # under the question's words, with no label, so "San Antonio to
            # win · 54% · -1.5¢" drew the other side's -1.5c (San Antonio's own
            # is -2.5c). The tile's words carry the card's answer now.
            # A SPREAD ROW TOO, FROM PICK-NUMBER STEP A (2026-09-30). It kept
            # its bare figure while its words named the question's line and
            # its numbers the venue's (finding 2), where "the other side" of
            # the words would have named another contract again. Its words
            # name the claim's contract now, so the other side of them is the
            # other side of the figure's own contract. (A recommendation's
            # size and outline beside the words of the side it does not buy
            # were operator question 37's; ruled 2026-10-05, the card
            # headlines the contract bought, so its edge is that contract's
            # own and is drawn bare.)
            out["edge_words"] = language.board_edge_words(
                entry["edge_line_words"],
                other_side=bool(entry.get("edge_on_the_other_side")))
    elif state == "live":
        # THE ONE FIGURE A LIVE ROW MAY CARRY, with its word (ruled 2026-09-09).
        out["pregame_words"] = (entry or {}).get("pregame_words") or \
            language.pregame_words(shown)
        # AND NOT THE PROBABILITY BESIDE IT (LIVE TAB, re-homed onto the
        # board's live rows by the merge, 2026-09-29): the Live tab showed
        # the game and nothing else, a card carrying a probability failing by
        # name, and the pregame figure with its word is the one number the
        # 09-09 ruling allows. The board drew no bar and no chance on a live
        # row, but carried both in the payload; neither travels now, and
        # `audit.live_tab_faults` walks the board's live rows for them.
        out.pop("prob", None)
        out.pop("prob_words", None)
        out["tips"].pop("prob", None)
    elif state == "final":
        out["settled_words"] = language.settled_outcome_words(
            shown, card.get("outcome"), out["question"])
        if card.get("voided"):
            out["settled_words"] = language.withdrawn_words(
                card.get("void_reason")) or out["settled_words"]
    # A PICK, OR A NUMBER (operator ruling B, 2026-10-05: "A leg is called a
    # pick only if its edge after fees is 3 percentage points or more. Below
    # that it is shown as a number, never as a pick" and B.5's gate; built
    # 2026-10-07). The Today card carries the one door's answer
    # (`picks.judge`), and a question still to come wears it: `pick`, its
    # badge's words beside its outline, or -- a recommendation that is not a
    # pick -- the words saying why, on its face (reading (d)); and the label
    # it would wear leading its row (`lead_label_words`), which says "Model's
    # pick" only of a pick. A game being played or finished carries none of
    # them: nothing on it is priced.
    is_pick = state == "upcoming" and bool((entry or {}).get("pick"))
    out["pick"] = is_pick
    if state == "upcoming" and entry is not None:
        if entry.get("edge_points") is not None:
            out["edge_points"] = entry["edge_points"]
        if is_pick and entry.get("pick_words"):
            out["pick_words"] = entry["pick_words"]
        if entry.get("not_a_pick_words") and not across:
            out["not_a_pick_words"] = entry["not_a_pick_words"]
    out["lead_label_words"] = language.pick_label_words(
        state, signal, pick=is_pick, other_side=bool(own_side))
    return out


def _today_index(today: dict | None) -> dict:
    """Every Today card by prediction id, tagged with the group it sat in."""
    index: dict = {}
    for group in ("clears", "below_floor", "watching", "live", "settled"):
        for entry in (today or {}).get(group) or []:
            index[entry["prediction_id"]] = dict(entry, group=group)
    return index


def _other_forecaster_rows(conn: sqlite3.Connection, *, sport: str, season: int,
                           wk: int | None, chosen: str, game_ids: list[str],
                           names: dict) -> dict[str, list[dict]]:
    """The OTHER forecaster's standing rows on these games, as light cards.

    The slate is one forecaster's list (GRIDIRON_14); an expanded row shows
    both where both answered, each labelled, never merged and never ranked
    against each other. Read directly rather than through `views.week` again,
    which would rebuild the whole slate for a second name.
    """
    if wk is None or not game_ids:
        return {}
    others = [f for f in FORECASTERS if f != chosen]
    if not others:
        return {}
    marks = ",".join("?" for _ in game_ids)
    # THE STANDING ROW BY THE ONE CLAUSE (the board merge, 2026-09-29). The
    # board chose the other forecaster's row with a rule of its own -- the
    # latest written before the start, keyed by game, market, subject, rung
    # and forecaster -- which is the rule operator question 27 replaced: a
    # final pass written before the start stands whenever one exists, else the
    # latest early pass. `calibration.standing_row_clause` is that rule on
    # question 17's key (`bet.same`), the one every record and the slate's own
    # cards read, a withdrawn row never standing; so the two forecasters on an
    # expanded row stand on their rows by one rule. And the number shown is
    # the one stored for the reader (`calibrated_prob` where a correction was
    # in force when it was written), as the slate's cards show it.
    rows = conn.execute(
        "SELECT p.id, p.game_id, p.market_type, p.prop_type, p.subject,"
        "       p.line_asked, p.model_prob, p.calibrated_prob, p.model_side,"
        "       p.predictor, p.outcome, p.resolved_utc, g.home, g.away, g.status"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
        f"   AND p.game_id IN ({marks})"
        "   AND p.predictor IN (%s)" % ",".join("?" for _ in others)
        + calibration.standing_row_clause(False)
        + " ORDER BY p.id",
        (sport, season, wk, *game_ids, *others)).fetchall()
    from .views import _prompts_for, _prose_prop_type, shown_prob

    # THE PROMPT DISCLOSURE for the other forecaster's reasoning rows too,
    # through the one reader (the board merge, 2026-09-29).
    prompts = _prompts_for(conn, rows)

    out: dict[str, list[dict]] = {}
    for r in rows:
        card = {
            "prediction_id": r["id"], "game_id": r["game_id"], "sport": sport,
            "market_type": r["market_type"],
            "prop_type": _prose_prop_type(r, sport),
            "market": _prose_prop_type(r, sport) or r["market_type"],
            "subject": r["subject"], "line_asked": r["line_asked"],
            "model_prob": r["model_prob"], "model_side": r["model_side"],
            "predictor": r["predictor"], "outcome": r["outcome"],
            "resolved_utc": r["resolved_utc"], "game_status": r["status"],
            "opponent": r["away"] if r["subject"] == r["home"] else r["home"],
            "team_names": names,
        }
        card["shown_prob"] = shown_prob(r)
        card["phrase"] = language.phrase(card)
        if r["id"] in prompts:
            card["prompt"] = prompts[r["id"]]
        out.setdefault(r["game_id"], []).append(card)
    return out


def _row_order(blocks: list[dict], sport: str) -> list[dict]:
    """One forecaster's questions on a row, in ruling B's order (2026-10-05;
    readings (a) and (b), built 2026-10-07): its picks by their edge after
    fees, best first, then everything else in the sport's declared market
    order, then subject, line and number (`picks.browse_key`; one game, one
    start).

    NEVER THE SUREST, AND NEVER THE SHORTLIST'S ORDER. The questions came in
    the slate's order -- the size of the disagreement with the media line,
    then the model's chance (`views._card_order`) -- and the row's lead was
    the one clearing the bar by the most, else the shortlist's first, else
    the surest: 1,269 rows on the record's 108 payloads that day led by a
    question no edge put there, 118 of them a player prop. The shortlist
    ranker orders questions for the shortlist by its own declared inputs and
    rulings, and is not changed; this page orders itself."""
    from . import picks

    def key(b):
        if b.get("pick"):
            return (0, picks.pick_key(b.get("edge_points"), b["prediction_id"]))
        return (1, picks.browse_key(sport, start_order=(0, 0.0), game_id=None,
                                    market=b.get("market"), subject=b.get("subject"),
                                    line=b.get("_line"), prediction_id=b["prediction_id"]))

    return sorted(blocks, key=key)


def _pick_for(blocks: list[dict]) -> dict | None:
    """Which question leads a row: its best pick by edge, or, with none, the
    first in the declared market order (operator ruling B, 2026-10-05,
    reading (b); built 2026-10-07) -- the first of `_row_order`. Never the
    other forecaster's -- the page is one forecaster's view -- and never the
    surest, which it was until this date."""
    return blocks[0] if blocks else None


def _player_club(conn: sqlite3.Connection, sport: str, player: str | None,
                 home: str | None, away: str | None) -> str | None:
    """Which of the game's two clubs a prop's subject plays for, from the
    stats tables the factors already read. None when the record cannot say,
    and a jersey with no club is drawn in the neutral pair rather than in a
    guessed one."""
    if not player:
        return None
    if sport == "nfl":
        row = conn.execute(
            "SELECT team FROM player_week_stats WHERE player_name = ?"
            " ORDER BY season DESC, week DESC LIMIT 1", (player,)).fetchone()
    elif sport == "mlb":
        row = conn.execute(
            "SELECT team FROM mlb_batter_games WHERE player_name = ?"
            " ORDER BY game_date DESC LIMIT 1", (player,)).fetchone()
    elif sport == "nba":
        row = conn.execute(
            "SELECT team FROM nba_player_games WHERE player_name = ?"
            " ORDER BY game_date DESC LIMIT 1", (player,)).fetchone()
    else:
        row = None
    team = row["team"] if row else None
    return team if team in (home, away) else None


def _player_number(conn: sqlite3.Connection, sport: str, player: str | None,
                   club: str | None) -> int | None:
    """The jersey number on record for this player on this club, or None.

    NFL only, through the player id the stats table already carries, so no
    name is matched against the roster. Other sports load no roster numbers
    yet and get None, which the jersey draws as an empty slot.
    """
    if sport != "nfl" or not player or not club:
        return None
    # A RECORD THE MERGE'S SCHEMA HAS NOT REACHED YET HOLDS NO TABLE (the
    # board merge, 2026-09-29): a read-only read of the live record before
    # its first `db.init` under this release -- the gate's recounts, a
    # test's read through `db.read_the_live_record` -- found `player_numbers`
    # missing and the whole slate refused. With no table there is no number
    # on record, and the jersey shows its empty slot, as it does for a player
    # with none (`correction.latest_activation` reads a new table the same
    # way).
    from .db import table_columns

    if not table_columns(conn, "player_numbers"):
        return None
    row = conn.execute(
        "SELECT n.jersey_number FROM player_numbers n"
        " JOIN (SELECT player_id FROM player_week_stats WHERE player_name = ?"
        "        ORDER BY season DESC, week DESC LIMIT 1) s ON s.player_id = n.player_id"
        " WHERE n.team = ? ORDER BY n.season DESC LIMIT 1", (player, club)).fetchone()
    if row is None or row["jersey_number"] is None:
        return None
    return int(row["jersey_number"])


def _detail(conn: sqlite3.Connection, sport: str, game: sqlite3.Row, game_id: str,
            season: int, wk: int, pick: dict | None, first: dict, names: dict) -> dict:
    """The game's detail for the expanded row (3a, 2026-09-25): last five for
    each club, the injury report, the weather and the factors the pick read.
    Only what the record already holds; every absence is said in words."""
    from .views import _recent_form, _weather
    from .data import repo

    out: dict = {}
    for side in ("home", "away"):
        team = game[side]
        marks = _recent_form(conn, sport, team, game["kickoff_utc"])
        out[f"{side}_form_marks"] = marks
        out[f"{side}_form_words"] = language.form_words(marks)
        out[f"{side}_form_tip"] = language.form_marks_tip(
            language.team_name(team, names, "full"), marks)
    listed: list[str] = []
    if sport == "nfl":
        for team in (game["home"], game["away"]):
            for r in repo.injuries_for(conn, season, wk, team):
                status = (r["report_status"] or "").strip()
                if status in ("Out", "Doubtful", "Questionable") and r["player_name"]:
                    listed.append(f"{r['player_name']} ({status})")
    out["injuries_n"] = len(listed)
    out["injuries_words"] = language.injuries_words(listed)
    weather = _weather(conn, game_id)
    out["weather_words"] = weather or language.no_weather_words()
    out["weather_read"] = weather is not None
    factors = []
    for f in (first.get("top_factors") or [])[:5]:
        if f.get("contribution") is None:
            continue
        factors.append({
            # THE FACTOR'S OWN PHRASE, the one the Factors table uses. It is a
            # declared factor's name, not advice, so the words scan reads it
            # for internal vocabulary only.
            "factor_words": language.factor_line_words(f.get("plain_name"), f.get("factor") or ""),
            "contribution": round(float(f["contribution"]), 3),
            "present": bool(f.get("present", True)),
        })
    out["factors"] = factors
    out["factors_words"] = None if factors else language.factors_absent_words()
    return out


def _my_day(games: list[dict], tiles: list[dict]) -> dict:
    """The taken picks on this slate as chips (3b, 2026-09-25): club, pick,
    state, badge. Counts of picks and nothing else -- no stake, no payout,
    no total, which is the law the taken rail already keeps.

    EACH TAKEN QUESTION ONCE (the prover of the board merge, 2026-09-29). A
    prop question is on its game's row AND is a tile, and this read both, so
    one tapped prop was two chips and "2 taken". A prop is one chip now,
    marked as a prop and wearing its player's club as its tile does, and the
    count is of chips. `audit.board_count_faults` holds it."""
    entries = []
    tiles_by_id = {t["prediction_id"]: t for t in tiles}
    seen: set = set()
    for g in games:
        for b in g.get("questions") or []:
            if not b.get("taken") or b["prediction_id"] in seen:
                continue
            seen.add(b["prediction_id"])
            tile = tiles_by_id.get(b["prediction_id"])
            if tile is not None:
                entries.append(_my_day_entry(b, g["game_id"], g["state"],
                                             tile.get("club") or {},
                                             g.get("score_words"), prop=True))
                continue
            # THE CLUB OF THE SIDE THE PICK'S WORDS NAME (pick-number finding
            # 6, 2026-09-30). This chose by the question's SUBJECT, which on a
            # game question is the home club, so a taken "not_cover" on PHI
            # -3.5 was the chip "PHI · DAL +3.5" and a taken "lose" moneyline
            # "PHI · DAL to win": the club the model forecast against beside
            # the side it took. The block carries the club its words name
            # (`language.club_named`, the words' own flip); a question naming
            # no club -- a total -- wears the home club as the game's mark, as
            # it did.
            named = b.get("named_club")
            club = g["home"] if named == g["home"].get("tricode") else (
                g["away"] if named == g["away"].get("tricode") else g["home"])
            entries.append(_my_day_entry(b, g["game_id"], g["state"], club, g.get("score_words")))
    for tile in tiles:
        if tile.get("taken") and tile["prediction_id"] not in seen:
            seen.add(tile["prediction_id"])
            entries.append(_my_day_entry(tile, tile["game_id"], tile["state"],
                                         tile.get("club") or {}, None, prop=True))
    live = sum(1 for e in entries if e["state"] == "live")
    won = sum(1 for e in entries if e["signal"] == "won")
    lost = sum(1 for e in entries if e["signal"] == "lost")
    return {
        "heading": language.my_day_heading(),
        "n": len(entries),
        "entries": entries,
        "counts_words": language.my_day_counts_words(len(entries), live, won, lost),
        "empty_words": language.my_day_empty_words(),
    }


def _my_day_entry(block: dict, game_id: str, state: str, club: dict,
                  score_words: str | None, prop: bool = False) -> dict:
    return {
        "prediction_id": block["prediction_id"],
        "game_id": game_id,
        "prop": prop,
        "state": state,
        "signal": block.get("signal") if state == "final" else "none",
        "line_words": block.get("line_words") or "",
        "status_words": language.my_day_status_words(state, block.get("signal") or "none",
                                                     score_words),
        "badge_words": block.get("badge_words"),
        "badge_n": block.get("badge_n"),
        "club": {"tricode": club.get("tricode") or "", "colour": club.get("colour"),
                 "on_white": club.get("on_white")},
        # THE MODEL'S OWN SIDE BESIDE THE CONTRACT BOUGHT, on the chip too
        # (Q37's prover, 2026-10-05; operator question 37, ruled that day:
        # "headline the contract the recommendation buys; the model's own side
        # named beside it"). The chip headlined New Orleans -2.5 and said
        # nowhere that the model's own side was Atlanta +2.5 at 32%, where the
        # row it scrolls to, the taken rail and the line all say it. The chip
        # is a tap target with no room for a sentence, so the words travel in
        # its tooltip, beside the contract's own words (`own_side_words` is on
        # a block only while its game is still to start).
        "tips": {"badge": (block.get("tips") or {}).get("badge"),
                 "line": language.my_day_line_tip(block.get("question") or "",
                                                  block.get("own_side_words"))},
    }


def _start_order(stamp: str | None) -> tuple:
    """A game's row in start order, its start READ AS AN INSTANT (operator
    question 35, ruled 2026-09-30: "Store and compare starts as instants,
    never as text"; built 2026-10-01): a start stored to the minute sorted
    after one to the second of the same minute as text. A game with no start
    yet comes first, as the empty text did; one whose start cannot be read
    comes last, its time never guessed."""
    from . import db as _db

    try:
        when = _db.instant(stamp)
    except ValueError:
        return (2, 0.0)
    return (0, 0.0) if when is None else (1, when.timestamp())


def _secondary(colours: dict) -> str | None:
    """The club's second colour, where the colour file records one.

    The file holds a primary and the shade white reads on; the second is the
    club's ALTERNATE only where that is what the reading shade is. Nowhere
    else is a second colour known, and nothing here invents one -- the jersey
    then trims in white, which is a colour every club has.
    """
    if colours.get("how") == "alternate":
        return colours.get("on_white")
    return None


# ---------------------------------------------------------------------------
# THE PROPS BOARD (operator ruling C, 2026-10-05; built 2026-10-06)
# ---------------------------------------------------------------------------

def ladder_key(card: dict) -> tuple:
    """One player and one stat on one game: the key a venue ladder is held
    under, and the leg it stands beside."""
    family = card.get("prop_type") or card.get("market")
    return (card.get("game_id"), family,
            language.strip_market_suffix(card.get("subject"), family))


def _venue_prop_ladders(conn: sqlite3.Connection, sport: str,
                        cards: list[dict]) -> tuple[dict, str | None]:
    """The venue's ladder for each player and stat on these cards, keyed by
    `ladder_key`, each a list of rungs -- {"line", "price", "ticker"}: the
    venue's contract "over <line>" at its yes price -- and why there are none.

    THE ONE PLACE THE PROPS BOARD READS A VENUE LADDER, AND NONE IS READ
    (measured 2026-10-06 on a verified copy of the record): the capture
    (`kalshi.capture_for_games`) reads spread, total and moneyline ladders
    only, `venue_quotes` holds no prop quote and has no column naming a
    player, and the cache holds no fetch of the four NFL prop series
    `kalshi.SERIES` declares. So every card is answered with no ladder, and
    the words say why. Reading the venue's player-prop series is a build of
    its own -- the series, the player matched, the rung, on the new-market
    checklist -- that no ruling names; the legs and the Kalshi ladder view are
    built from what this answers, so the day a read lands they change by
    nothing but this function."""
    return {}, language.props_ladders_not_read_words()


def _main_rung(ladder: list[dict]) -> dict | None:
    """The venue's main line out of one ladder: the rung priced nearest an
    even chance (ruling C.1: "the market's main line (the rung nearest 50c)",
    the rule `at_the_line.rung_for` has read since 2026-09-06). A tie goes to
    the lower line, said here rather than left to the order of the list."""
    best = None
    for rung in ladder or []:
        price = rung.get("price")
        if rung.get("line") is None or price is None or not 0.0 < float(price) < 1.0:
            continue
        # TO SIX PLACES: 45c and 55c are one distance from an even chance,
        # which floats would tell apart by their last bit.
        key = (round(abs(float(price) - 0.5), 6), float(rung["line"]))
        if best is None or key < best[0]:
            best = (key, rung)
    return None if best is None else best[1]


def _chance_at(conn: sqlite3.Connection, forecast: dict, game: dict, line: float,
               *, sport: str) -> tuple[float | None, bool, str]:
    """The model's chance that the stat goes OVER `line`, where the record can
    state one: (the chance, whether `line` is the line it was asked at, why).

    THROUGH THE CLAIM WRITER'S OWN RULES, never a rule of the page's own
    (reading (a) of ruling C, 2026-10-06: "shown only where the model states
    a chance at that line (a question asked at that line, or a distribution
    it already carries)"): `priced.shape.claim_shape` and
    `at_the_line.claim_probability` -- the question's own answer where `line`
    is the line it was asked, and a counting stat's blind rate, written with
    its forecast, read at `line` in its declared form (AT_THE_PRICE,
    2026-09-07). A yardage stat at another line has none (None), and no
    chance is guessed. The chance is the number a reader is shown: corrected
    by the correction in force now where one is (`correction.shown_proposition`,
    item 3's door; none is in force for any prop on 2026-10-06)."""
    from . import correction
    from .market import at_the_line
    from .priced import shape as shapes

    got = shapes.claim_shape(forecast, line, quantity="count")
    if got.get("shape") is None:
        return None, False, got.get("why") or ""
    said = at_the_line.claim_probability(
        forecast, game, {"quantity": "count"}, got["shape"], float(line), None)
    prob = said.get("prob")
    if prob is None:
        return None, False, said.get("why") or ""
    shown, _version = correction.shown_proposition(
        conn, sport=sport, market_type="prop", forecaster=forecast["predictor"],
        proposition=float(prob))
    return float(shown), got["shape"] == shapes.RUNG_MATCHED, said.get("why") or ""


def _projection_of(forecast: dict | None) -> float | None:
    """The model's own expected count for the player and stat, written with
    its forecast (`expected_count`, a counting stat's rate); None where it
    stated none -- a yardage stat, answered as a yes-or-no question at its
    own line, or a row written before the rate model."""
    if not forecast:
        return None
    try:
        payload = json.loads(forecast.get("factors_json") or "{}") or {}
    except ValueError:
        return None
    rate = payload.get("expected_count")
    try:
        return None if rate is None else float(rate)
    except (TypeError, ValueError):
        return None


#: FLOAT NOISE, NOT A MARGIN (the prover of ruling C, 2026-10-06). An edge of
#: exactly three points can be worked out as 0.029999999999999985, and that is
#: still three points; nothing a model states is finer than a billionth.
#: (From ruling B, 2026-10-07, the bar is one for both venues and lives in
#: `picks`; this name is kept, the same number.)
PICK_BAR_FLOAT_NOISE = 1e-9


def clears_the_pick_bar(edge: float | None) -> bool:
    """B.2 (2026-10-05): a leg is called a pick only if its edge after fees is
    three points or more -- read on the edge AS WORKED OUT, less float noise
    only. Until 2026-10-06 (the prover of ruling C) the edge was rounded to
    six places first, so a leg at 2.99995 points was called a pick, and the
    gate, reading the page's rounded chance, disagreed with the builder about
    a leg at 2.99994: B.2 says "3 percentage points or more".

    ONE BAR FOR BOTH VENUES (ruling B, built 2026-10-07): a Kalshi pick is
    read against the same bar (`picks.judge`), so the bar is asked of
    `picks.clears_the_pick_bar`; the leg asks it through this name."""
    from . import picks

    return picks.clears_the_pick_bar(edge)


def _leg(conn: sqlite3.Connection, card: dict, block: dict, forecast: dict | None,
         game: dict | None, ladder: list[dict] | None, payouts: list[dict],
         *, sport: str) -> dict:
    """One upcoming player and stat, as the Props board shows it (C.1-C.3):
    the projection, the venue's main line and the model's chance at it, the
    break-even of each typed payout, the edge against each, and a pick only
    where an edge clears the bar. Nothing here reads the question's own line
    as the app's: that line stays the model's own question."""
    family = card.get("prop_type") or card.get("market")
    family_words = language.market_words(sport, family) if family else ""
    projection = _projection_of(forecast)
    out = {
        "projection": projection,
        "projection_words": language.prop_projection_words(projection, family_words),
        "main_line": None, "main_side": None, "main_price": None,
        "main_words": language.prop_main_absent_words(),
        "main_note_words": None,
        "main_chance": None, "main_chance_words": "",
        # THE WORDS THE LEG IS NAMED BY OFF ITS TILE -- the entry rail (the
        # prover of ruling C, 2026-10-06). As built the rail drew a taken
        # leg under its own question's words ("over 200.5 passing yards")
        # beside its chance at the MAIN line, a number under another
        # contract's words. With a main line they are the main line's own
        # contract, on the side the chance is for; without one, the player
        # and the stat and no line at all, because no line is the app's.
        "leg_words": language.prop_leg_words(
            language.strip_market_suffix(card.get("subject"), family), family_words),
        "entries": [], "pick": False, "pick_words": None,
    }
    tips = {"projection": language.prop_projection_tip(projection, family_words),
            "main": language.prop_main_absent_tip()}
    rung = _main_rung(ladder or [])
    chance = None
    if rung is not None and forecast is not None and game is not None:
        line = float(rung["line"])
        over, asked_here, _why = _chance_at(conn, forecast, game, line, sport=sport)
        out["main_line"] = line
        out["main_price"] = float(rung["price"])
        out["main_note_words"] = language.APP_LINE_WORDS
        tips["main"] = language.prop_main_line_tip(out["main_price"])
        if over is None:
            out["main_words"] = language.phrase(dict(card, line_asked=line,
                                                     model_side="over"))
            out["main_chance_words"] = language.prop_no_chance_words()
            tips["chance"] = language.prop_no_chance_tip(family_words)
        else:
            # THE SIDE THE MODEL FAVOURS AT THE MAIN LINE: a pick'em leg can
            # be either side of the app's line, and the model's chance is
            # stated for the side it gives at least half.
            side = "over" if over >= 0.5 else "under"
            chance = over if side == "over" else 1.0 - over
            out["main_side"] = side
            out["main_chance"] = round(chance, 6)
            out["main_words"] = language.phrase(dict(card, line_asked=line, model_side=side))
            out["main_chance_words"] = language.prop_chance_words(chance)
            tips["chance"] = language.prop_chance_tip(
                out["main_words"], chance,
                language.prop_chance_how_words(asked_here, projection, family_words))
        out["leg_words"] = out["main_words"]
    cleared: list[int] = []
    for p in payouts:
        legs, multiple = p["legs"], p["multiple"]
        be = None if multiple is None else breakeven(multiple, legs)
        # THE BAR READS THE EDGE AS WORKED OUT, the page its six places (the
        # prover of ruling C, 2026-10-06; `clears_the_pick_bar`).
        worked = None if (be is None or chance is None) else chance - be
        edge = None if worked is None else round(worked, 6)
        clears = clears_the_pick_bar(worked)
        if clears:
            cleared.append(legs)
        # NEVER "+3.0" UNDER THE BAR (operator ruling B.2, 2026-10-05;
        # reading (c), built 2026-10-07: C's prover found "edge +3.0" on legs
        # at 2.95-2.99999 points): drawn at the tenth below it.
        from . import picks as _picks

        drawn = None if worked is None else _picks.drawn_edge(worked * 100.0, edge * 100.0)
        out["entries"].append({
            "legs": legs, "kind": "power", "multiple": multiple,
            "breakeven": None if be is None else round(be, 6),
            "breakeven_words": language.pickem_breakeven_words(legs, be),
            "edge": edge, "edge_words": language.prop_edge_words(
                None if drawn is None else drawn / 100.0),
            "clears": clears,
            "tip": language.pickem_breakeven_tip(legs, multiple, be, p["typed_utc"]),
        })
    if cleared:
        out["pick"] = True
        out["pick_words"] = language.prop_pick_words(cleared)
        tips["pick"] = language.prop_pick_tip(config.PICK_MIN_EDGE)
    out["tips"] = tips
    return out


def _ladder_rows(tiles: list[dict], cards_by_id: dict, ladders: dict) -> list[dict]:
    """THE KALSHI LADDER VIEW (C.1, reading (e)): the venue's full ladder for
    each player and stat on the slate, every rung under its own contract and
    price -- step A's rule, a number named by the contract it belongs to --
    the main line marked, and nothing a pick'em pick carries: no break-even,
    no edge, no pick and no signal on any rung."""
    rows = []
    for tile in tiles:
        card = cards_by_id.get(tile["prediction_id"])
        if card is None:
            continue
        ladder = ladders.get(ladder_key(card)) or []
        if not ladder:
            continue
        main = _main_rung(ladder)
        rungs = []
        for rung in sorted(ladder, key=lambda r: float(r["line"])):
            rungs.append({
                "line": float(rung["line"]),
                "price": rung.get("price"),
                "contract_words": language.phrase(dict(card, line_asked=float(rung["line"]),
                                                       model_side="over")),
                "price_words": language.ladder_rung_price_words(rung.get("price")),
                "main": rung is main,
            })
        rows.append({"prediction_id": tile["prediction_id"], "player": tile["player"],
                     "family": tile["family"], "family_words": tile["family_words"],
                     "matchup": tile.get("matchup") or "", "club": tile.get("club"),
                     "rungs": rungs})
    return rows


def build(conn: sqlite3.Connection, *, sport: str, season: int, wk: int | None,
          cards: list[dict], today: dict | None, chosen: str,
          unit_dollars: float | None = None) -> dict:
    """The board payload: rows for Games, tiles for Props, words for both."""
    from . import tasks as _tasks
    from .views import taken_ids, team_colours

    names = teams.names(conn, sport)
    index = _today_index(today)
    already = taken_ids(conn, [c["prediction_id"] for c in cards])
    hours = _tasks.NEAR_START_HOURS
    settled_cache: dict = {}
    sport_label = config.SPORT_LABELS.get(sport, sport.upper())

    # --- the rows -----------------------------------------------------------
    by_game: dict[str, list[dict]] = {}
    game_rows: dict[str, dict] = {}
    for card in cards:
        by_game.setdefault(card["game_id"], []).append(card)
    game_ids = list(by_game)
    others = _other_forecaster_rows(conn, sport=sport, season=season, wk=wk,
                                    chosen=chosen, game_ids=game_ids, names=names)
    # WHICH QUESTIONS' GAMES ARE NOT STILL UPCOMING (Q38's prover,
    # 2026-10-07): through the engine's one door, so a row still drawn as to
    # come says why it has no price (`_question_block`).
    from .market import recommend as _recommend

    past_its_start = {r["prediction_id"] for r in _recommend.not_still_upcoming_among(
        conn, [c["prediction_id"] for c in cards]
        + [c["prediction_id"] for rows in others.values() for c in rows])}

    def block_for(card: dict, forecaster: str) -> dict:
        entry = index.get(card["prediction_id"])
        state = _state_of(card)
        n = _settled_n(conn, settled_cache, sport=sport,
                       market_type=card["market_type"],
                       prop_type=card.get("prop_type"), predictor=forecaster)
        block = _question_block(
            card, entry, state=state, taken=card["prediction_id"] in already,
            forecaster=forecaster, n_settled=n, hours=hours,
            unit_dollars=unit_dollars,
            past_its_start=card["prediction_id"] in past_its_start)
        block["_line"] = card.get("line_asked")
        return block

    games = []
    for game_id, group in by_game.items():
        first = group[0]
        game = conn.execute(
            "SELECT home, away, status, home_score, away_score, kickoff_utc,"
            "       live_period, live_clock, live_updated_utc FROM games"
            " WHERE id = ?", (game_id,)).fetchone()
        if game is None:
            continue
        from .views import card_state
        from . import db as _db

        state = card_state(game["status"])
        # EACH FORECASTER'S QUESTIONS IN RULING B'S ORDER, the page's own
        # first (never ranked against the other's): its picks by edge, then
        # the declared market order (`_row_order`).
        own = _row_order([block_for(c, chosen) for c in group], sport)
        theirs = _row_order([block_for(c, c["predictor"])
                             for c in others.get(game_id, [])], sport)
        pick = _pick_for(own)
        bets = own + theirs
        for b in bets:
            b.pop("_line", None)
        # EACH FORECASTER'S QUESTIONS ON THE GAME, COUNTED APART on question
        # 17's key (the prover of the board merge, 2026-09-29): the row's
        # count summed both forecasters' rows under the word "question".
        whose: dict[str, list[dict]] = {}
        for c in group + list(others.get(game_id, [])):
            whose.setdefault(c["predictor"], []).append(c)
        questions_n = {f: bet.count(rows) for f, rows in whose.items()}
        away = _club(sport, game["away"], names)
        home = _club(sport, game["home"], names)
        if state in ("live", "final"):
            away["score"] = game["away_score"]
            home["score"] = game["home_score"]
        row = {
            "game_id": game_id,
            "state": state,
            # THE LABEL SAYS WHEN THE PICK IS THE OTHER SIDE OF THE MODEL'S
            # (operator question 37, ruled 2026-10-05): the row headlines the
            # contract the recommendation buys, and its own-side line names
            # the model's side beneath it.
            # AND "MODEL'S PICK" ONLY OVER A PICK (operator ruling B,
            # 2026-10-05; built 2026-10-07): the lead's own label.
            "pick_label_words": (pick["lead_label_words"] if pick else
                                 language.pick_label_words(state, "none")),
            "n": pick["badge_n"] if pick else 0,
            "away": away,
            "home": home,
            "kickoff_utc": game["kickoff_utc"],
            "sport_key": sport,
            "sport_label": sport_label,
            "pick": pick,
            "questions": bets,
            "questions_n": questions_n,
            "questions_words": language.game_questions_words(questions_n, chosen),
            "yours_words": (language.taken_badge_words()
                            if any(b["taken"] for b in bets) else None),
        }
        row["detail"] = _detail(conn, sport, game, game_id, season, wk, pick,
                                first, names)
        if pick is None:
            row["no_pick_words"] = language.board_labels()["no_pick"]
        if state == "live":
            row["score_words"] = language.score_line_words(
                game["away"], game["away_score"], game["home"], game["home_score"])
            row["period_words"] = language.period_words(
                sport, game["live_period"], game["live_clock"])
            row["polled_words"] = language.polled_words(
                game["live_updated_utc"], _db.utcnow())
        elif state == "final":
            row["score_words"] = language.score_line_words(
                game["away"], game["away_score"], game["home"], game["home_score"])
        games.append(row)
    games.sort(key=lambda g: (_start_order(g["kickoff_utc"]), g["game_id"]))

    # --- the prop tiles -----------------------------------------------------
    # ONE PLAYER AND ONE STAT EACH (operator ruling C, 2026-10-05; built
    # 2026-10-06; the module docstring): an upcoming tile is a LEG -- the
    # projection, the venue's main line and the model's chance at it, the
    # break-even of each payout the operator typed, an edge against each and
    # a pick only where one clears the bar -- and the question the record
    # asked at its own line is said as the model's own, with no break-even
    # beside it. A live tile carries the pregame figure and nothing that can
    # be acted on; a settled one its verdict. The CUSHION against a declared
    # 3x, and the break-even it was drawn from, are gone.
    families = config.SPORT_PROP_MARKETS.get(sport, ())
    payouts = typed_payouts(conn)
    prop_cards = [c for c in cards
                  if c.get("market_type") == "prop" or c.get("prop_type") in families]
    ladders, ladders_why = _venue_prop_ladders(conn, sport, prop_cards)
    # THE FORECAST AND THE GAME BEHIND EACH LEG, read once: the claim
    # writer's rules read the stored row (its line, side, number and rate),
    # never the card's words.
    forecasts: dict[int, dict] = {}
    ids = [c["prediction_id"] for c in prop_cards]
    if ids:
        marks = ",".join("?" for _ in ids)
        for r in conn.execute(
                "SELECT id, game_id, market_type, prop_type, subject, line_asked,"
                "       model_prob, model_side, predictor, factors_json"
                f"  FROM predictions WHERE id IN ({marks})", ids):
            forecasts[r["id"]] = dict(r)
    cards_by_id = {c["prediction_id"]: c for c in prop_cards}
    tiles = []
    for card in prop_cards:
        family = card.get("prop_type") or card.get("market")
        block = block_for(card, chosen)
        block.pop("_line", None)
        state = block["state"]
        # NO SIGNAL BUT A PICK'S OR A VERDICT'S. A settled tile keeps its
        # fill; an upcoming one wears the green outline only where its leg is
        # a pick (B.2), against a payout the operator TYPED -- ruling c of
        # 2026-09-25 ("a prop tile wears no outline until a multiplier is
        # read or typed"), held by `audit.board_signal_faults` -- and with the
        # record badge beside it, as every signal on the board.
        if state != "final":
            block["signal"] = "none"
            block["tips"].pop("signal", None)
        player = language.strip_market_suffix(card.get("subject"), family)
        game = conn.execute("SELECT home, away, kickoff_utc FROM games WHERE id = ?",
                            (card["game_id"],)).fetchone()
        home, away = (game["home"], game["away"]) if game else (None, None)
        club_code = _player_club(conn, sport, player, home, away)
        colours = team_colours(sport, club_code)
        block.update({
            "player": player,
            "surname": language.surname(player),
            # THE NUMBER FROM THE ROSTER (ruling a, 2026-09-25): the record's
            # own `player_numbers` row for this player on this club, else
            # None and an empty slot. Never a guess.
            "number": _player_number(conn, sport, player, club_code),
            "club": {
                "tricode": club_code or "",
                "name": language.team_name(club_code, names, "full") if club_code else "",
                "colour": colours["primary"],
                "on_white": colours["on_white"],
                "secondary": _secondary(colours),
                "known": bool(club_code) and colours["known"],
            },
            "family": family,
            "family_words": language.market_words(sport, family),
            # WHERE A BREAK-EVEN COMES FROM (ruling c, 2026-09-25; ruling
            # C.3, 2026-10-05): "typed" once the operator has typed a payout
            # a leg can be read against, "untyped" before -- never "declared"
            # again. A leg is a pick only against a payout that was typed, and
            # `audit.board_signal_faults` refuses an outline on a tile whose
            # multiple was neither read nor typed.
            "multiple_source": ("typed" if any(p["multiple"] is not None for p in payouts)
                                else "untyped"),
            # NO ALT LINES UNTIL A VENUE IS READ. An alt tile carries the
            # second badge and its tooltip; the composers exist and the scan
            # demands them, and nothing sets `alt` tonight.
            "alt": False,
            "high_end_badge_words": None,
            "game_id": card["game_id"],
            "kickoff_utc": game["kickoff_utc"] if game else None,
            "matchup": card.get("matchup") or "",
            "pick": False,
        })
        # THE MODEL'S OWN QUESTION, said as its own (C.1): the record's
        # forecast at the line it asked, never the app's line, with no
        # break-even beside it.
        if state == "upcoming":
            block["own_question_words"] = language.prop_own_question_words(
                block.get("question") or "", block.get("prob_words") or "")
            block["tips"]["own"] = language.prop_own_question_tip()
            leg = _leg(conn, card, block, forecasts.get(card["prediction_id"]),
                       {"home": home, "away": away} if game else None,
                       ladders.get(ladder_key(card)), payouts, sport=sport)
            leg_tips = leg.pop("tips")
            block.update(leg)
            block["tips"].update({f"leg_{k}": v for k, v in leg_tips.items()})
            if block["pick"]:
                block["signal"] = "clears"
                block["tips"]["signal"] = leg_tips.get("pick")
        block["tips"]["number"] = language.number_tip(block["number"])
        if block["alt"]:
            high = _settled_n(conn, settled_cache, sport=sport,
                              market_type=card["market_type"],
                              prop_type=card.get("prop_type"), predictor=chosen)
            block["high_end_badge_words"] = language.high_end_badge_words(
                high, config.MIN_SAMPLE_FOR_EDGE_CLAIM)
            block["tips"]["high_end"] = language.high_end_badge_tip(
                high, config.MIN_SAMPLE_FOR_EDGE_CLAIM)
        tiles.append(block)
    # BY EDGE, NEVER BY CHANCE (ruling C with B.1, 2026-10-05: "chance of
    # hitting alone never ranks anything"): the picks first, by their best
    # edge; then every other leg still to start, by its start and its player;
    # then the games being played and the finished ones. The cushion this
    # replaced was the chance less one declared number.
    def best_edge(t):
        edges = [e["edge"] for e in t.get("entries") or [] if e.get("edge") is not None]
        return max(edges) if edges else None

    # AND THE REST BY START, THEN THE DECLARED MARKET ORDER (operator ruling
    # B, 2026-10-05, reading (b); built 2026-10-07): C ordered them by start
    # and player; the stat family's declared place comes before the player.
    from . import picks as _picks

    state_rank = {"upcoming": 0, "live": 1, "final": 2}
    tiles.sort(key=lambda t: (state_rank.get(t["state"], 3), not t.get("pick"),
                              -(best_edge(t) or 0.0) if t.get("pick") else 0.0,
                              _start_order(t.get("kickoff_utc")),
                              _picks.market_rank(sport, t.get("family")),
                              t.get("player") or "", t["prediction_id"]))
    ladder_words = language.venue_ladder_view_words()
    ladder_rows = _ladder_rows(tiles, cards_by_id, ladders)
    chips = [{"key": "", "label": language.board_labels()["all"], "n": len(tiles)},
             # THE KALSHI LADDER, IN A VIEW OF ITS OWN (C.1): where the "Alt
             # lines" chip sat, empty since the board was built.
             {"key": "ladder", "label": ladder_words["chip"], "n": len(ladder_rows)}]
    for family in families:
        chips.append({"key": family, "label": language.market_words(sport, family),
                      "n": sum(1 for t in tiles if t["family"] == family)})
    upcoming_legs = [t for t in tiles if t["state"] == "upcoming"]
    missing = [p["legs"] for p in payouts if p["multiple"] is None]

    labels = language.board_labels()
    # THE QUESTIONS RESULTS SHOWS AS SETTLED, BY ID (the prover of the board
    # merge, 2026-09-29). Results heads its settled tiles with the Today
    # block's "Settled -- 15 questions", the page forecaster's shortlisted or
    # taken questions on finished games; the board drew every question on
    # every finished row beneath it, the other forecaster's included, so the
    # heading counted one set and the tiles showed another. The set is the
    # heading's, restyled as board tiles: the same questions as before the
    # merge, never recounted. `audit.board_count_faults` holds every one to a
    # finished block of the page's forecaster.
    settled_ids = [c["prediction_id"] for c in ((today or {}).get("settled") or [])]
    return {
        "labels": labels,
        "games": games,
        "games_n": len(games),
        "settled_ids": settled_ids,
        "sport_key": sport,
        "sport_label": sport_label,
        "my_day": _my_day(games, tiles),
        "games_empty_words": language.games_empty_words(sport_label) if not games else None,
        # NO FILLING (operator ruling B.4, 2026-10-05: "When nothing clears
        # on a slate: 'Nothing worth taking today'"; reading (f), built
        # 2026-10-07): said once, above the rows, wherever the slate has a
        # question of the page's forecaster still to come and none is a pick
        # -- priced or not. Until then it was said only on a priced slate,
        # and in the day strip's note, where "no venue price yet" took its
        # place; and it said "Every pick below is priced", of rows none of
        # which is a pick.
        "nothing_clears_words": (
            language.nothing_clears_words()
            if any(q.get("state") == "upcoming" and q["forecaster"] == chosen
                   and q["prediction_id"] not in past_its_start
                   for g in games for q in g["questions"])
            and not any(q.get("pick") for g in games for q in g["questions"])
            else None),
        # WHOSE ROWS THESE ARE, for the page's market filter: a row's lead is
        # the page's forecaster's question, never the other's.
        "forecaster": chosen,
        "props": {
            "n": len(tiles),
            "tiles": tiles,
            "chips": chips,
            # WHAT THE OPERATOR TYPED, AND WHEN (C.3, reading (b)): each power
            # payout a leg's break-even is read from, the day it was typed,
            # and -- until both are typed -- the page asking for them.
            "payouts": {
                "heading": language.pickem_payouts_heading(),
                "entries": [{
                    # THE SETTING IT IS TYPED INTO, for the page's form to post
                    # to; never drawn.
                    "legs": p["legs"], "setting": p["name"],
                    "label": language.pickem_payout_label(p["legs"]),
                    "multiple": p["multiple"],
                    "value": "" if p["multiple"] is None else f"{p['multiple']:g}",
                    "typed_utc": p["typed_utc"],
                    "typed_words": (language.pickem_typed_words(p["typed_utc"])
                                    if p["multiple"] is not None else None),
                } for p in payouts],
                "typed": not missing,
                "ask_words": language.pickem_payouts_ask_words(missing),
                "note": language.pickem_payouts_note(),
            },
            # NO FILLING (B.4's words, on this page from ruling C): a slate
            # with legs still to start and none of them a pick says so, and
            # nothing is drawn to look like one.
            "nothing_words": (language.props_nothing_worth_taking_words()
                              if upcoming_legs and not any(t["pick"] for t in upcoming_legs)
                              else None),
            "ladders_words": ladders_why if not ladders else None,
            "ladder": {
                "heading": ladder_words["heading"],
                "note": ladder_words["note"],
                "main_words": ladder_words["main"],
                "main_tip": ladder_words["main_tip"],
                "rows": ladder_rows,
                "empty_words": ladder_words["empty"] if not ladder_rows else None,
            },
            "app_line_words": language.APP_LINE_WORDS,
            "pick_bar": config.PICK_MIN_EDGE,
            "note": language.props_board_note(),
            "empty_words": language.props_empty_words(sport_label) if not tiles else None,
            "entry": language.entry_words(),
        },
    }
