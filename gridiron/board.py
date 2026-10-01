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

THE CUSHION ON A PROP TILE IS ARITHMETIC, NOT AN EDGE. No pick'em venue is
read (docs/PRIZEPICKS_FEASIBILITY.md), so the break-even is the declared
`config.PICKEM_TWO_PICK_MULTIPLE` and every tile says "not read yet" for its
venue line. A tile wears no outline for it: LAW 5 permits an edge against a
RECORDED price, and a declared constant is not one. Both readings of that are
in the close-out; this is the conservative one.
"""

from __future__ import annotations

import sqlite3

from . import bet, calibration, config, language
from .data import teams


#: The two forecasters, in the order the board lists them on an expanded row.
FORECASTERS = tuple(config.FORECASTER_LABELS)


def breakeven() -> float:
    """A leg's break-even in a standard two-pick entry: both must hit."""
    return config.PICKEM_TWO_PICK_MULTIPLE ** (-1.0 / config.PICKEM_LEGS)


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
                    unit_dollars: float | None) -> dict:
    """One question as the board shows it: on the row's face or as a tile.

    THE NUMBERS ARE THE TODAY CARD'S where one exists -- the same price, the
    same payout, the same edge the groups showed -- and the model's own where
    the question was never priced.
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
        "named_club": language.club_named(card),
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
            "prob": language.prob_tip(
                shown, label,
                asked_words=(entry or {}).get("asked_words") if corrected else None),
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
            # are operator question 37's, not ruled.)
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


def _pick_for(blocks: list[dict]) -> dict | None:
    """Which question is THE pick on a row: the one that clears the bar by
    the most, else the shortlist's first, else the surest. Never the other
    forecaster's -- the page is one forecaster's view."""
    if not blocks:
        return None

    def order(b):
        clears = b["signal"] == "clears"
        place = b.get("_place")
        return (not clears, -(b.get("_edge") or 0.0) if clears else 0.0,
                place if place is not None else 10 ** 6, -(b.get("prob") or 0.0))

    return sorted(blocks, key=order)[0]


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
        "tips": {"badge": (block.get("tips") or {}).get("badge"),
                 "line": block.get("question") or ""},
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

    def block_for(card: dict, forecaster: str) -> dict:
        entry = index.get(card["prediction_id"])
        state = _state_of(card)
        n = _settled_n(conn, settled_cache, sport=sport,
                       market_type=card["market_type"],
                       prop_type=card.get("prop_type"), predictor=forecaster)
        block = _question_block(
            card, entry, state=state, taken=card["prediction_id"] in already,
            forecaster=forecaster, n_settled=n, hours=hours,
            unit_dollars=unit_dollars)
        block["_place"] = card.get("shortlist_place")
        block["_edge"] = (entry or {}).get("edge_cents")
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
        own = [block_for(c, chosen) for c in group]
        theirs = [block_for(c, c["predictor"]) for c in others.get(game_id, [])]
        pick = _pick_for(own)
        bets = own + theirs
        for b in bets:
            b.pop("_place", None)
            b.pop("_edge", None)
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
            "pick_label_words": language.pick_label_words(
                state, pick["signal"] if pick else "none"),
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
    families = config.SPORT_PROP_MARKETS.get(sport, ())
    be = breakeven()
    tiles = []
    for card in cards:
        family = card.get("prop_type")
        if card.get("market_type") != "prop" and family not in families:
            continue
        family = family or card.get("market")
        block = block_for(card, chosen)
        block.pop("_place", None)
        block.pop("_edge", None)
        state = block["state"]
        # A PROP WEARS NO OUTLINE (see the module docstring): the cushion is
        # arithmetic against a declared multiple, not an edge against a read
        # price. A settled tile keeps its fill.
        if state != "final":
            block["signal"] = "none"
            block["tips"].pop("signal", None)
        player = language.strip_market_suffix(card.get("subject"), family)
        game = conn.execute("SELECT home, away FROM games WHERE id = ?",
                            (card["game_id"],)).fetchone()
        home, away = (game["home"], game["away"]) if game else (None, None)
        club_code = _player_club(conn, sport, player, home, away)
        colours = team_colours(sport, club_code)
        # A live tile carries no chance (LIVE TAB, above), so none is read.
        shown = block.get("prob")
        cushion = None if shown is None else shown - be
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
            "breakeven": be,
            "breakeven_words": language.breakeven_words(be),
            # WHERE THE MULTIPLE CAME FROM (ruling c, 2026-09-25): declared
            # until a venue is read, and `audit.board_signal_faults` refuses
            # an outline on a tile whose multiple was not read.
            "multiple_source": "declared",
            "cushion": cushion,
            "cushion_words": language.cushion_words(cushion),
            "venue_words": language.board_labels()["not_read"],
            # NO ALT LINES UNTIL A VENUE IS READ. An alt tile carries the
            # second badge and its tooltip; the composers exist and the scan
            # demands them, and nothing sets `alt` tonight.
            "alt": False,
            "high_end_badge_words": None,
            "game_id": card["game_id"],
            "matchup": card.get("matchup") or "",
        })
        block["tips"]["cushion"] = language.cushion_tip(
            shown, be, config.PICKEM_TWO_PICK_MULTIPLE, config.PICKEM_LEGS,
            config.PICKEM_TWO_PICK_DECLARED)
        block["tips"]["venue"] = language.venue_line_tip()
        block["tips"]["number"] = language.number_tip(block["number"])
        if block["alt"]:
            high = _settled_n(conn, settled_cache, sport=sport,
                              market_type=card["market_type"],
                              prop_type=card.get("prop_type"), predictor=chosen)
            block["high_end_badge_words"] = language.high_end_badge_words(
                high, config.MIN_SAMPLE_FOR_EDGE_CLAIM)
            block["tips"]["high_end"] = language.high_end_badge_tip(
                high, config.MIN_SAMPLE_FOR_EDGE_CLAIM)
        if state == "live":
            # NOTHING ON A LIVE TILE CAN BE ACTED ON, the cushion and the
            # venue line included: `audit.live_card_faults` names the venue
            # line by its field, and a cushion beside a game being played is
            # the same adverse selection with a different label.
            for field in ("venue_words", "cushion_words", "breakeven_words"):
                block.pop(field, None)
            block["cushion"] = None
            block["tips"].pop("cushion", None)
            block["tips"].pop("venue", None)
        tiles.append(block)
    tiles.sort(key=lambda t: (-(t["cushion"] if t["cushion"] is not None else -9),
                              t["prediction_id"]))
    chips = [{"key": "", "label": language.board_labels()["all"], "n": len(tiles)},
             {"key": "alt", "label": language.board_labels()["alt"],
              "n": sum(1 for t in tiles if t["alt"])}]
    for family in families:
        chips.append({"key": family, "label": language.market_words(sport, family),
                      "n": sum(1 for t in tiles if t["family"] == family)})

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
        # NOTHING CLEARS THE BAR, said once, and only on a slate that has a
        # price to clear it against: on an unpriced slate the day strip
        # already says the first read is still to come.
        "nothing_clears_words": (
            language.nothing_clears_words()
            if games and not any((g["pick"] or {}).get("signal") == "clears" for g in games)
            and any(q.get("priced") for g in games for q in g["questions"]) else None),
        "props": {
            "n": len(tiles),
            "tiles": tiles,
            "chips": chips,
            "breakeven": be,
            "multiple": config.PICKEM_TWO_PICK_MULTIPLE,
            "legs": config.PICKEM_LEGS,
            "declared": config.PICKEM_TWO_PICK_DECLARED,
            "note": language.props_not_read_words(),
            "empty_words": language.props_empty_words(sport_label) if not tiles else None,
            "alt_empty_words": language.alt_lines_empty_words(),
            "entry": language.entry_words(),
        },
    }
