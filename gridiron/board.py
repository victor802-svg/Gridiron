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

from . import calibration, config, language
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
    """How many questions in this category have settled: the badge's numerator."""
    key = (sport, market_type, prop_type, predictor)
    if key not in cache:
        cache[key] = len(calibration.resolved(
            conn, sport=sport, market_type=market_type, prop_type=prop_type,
            predictor=predictor))
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
    market = card.get("market") or card.get("market_type")
    signal = _signal(card, entry, state)
    price = entry.get("price") if entry else None
    pays = entry.get("payout") if entry else None
    out = {
        "prediction_id": card["prediction_id"],
        "state": state,
        "forecaster": forecaster,
        "forecaster_label": label,
        "market": market,
        "market_label": language.market_label(card),
        "line_words": language.pick_line_words(card),
        "question": card.get("phrase") or "",
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
        "tips": {
            "prob": language.prob_tip(shown, label),
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
    # THE EXPLANATION LIVES IN THE TOOLTIP, not in a sentence on the tile
    # (the brief's rule). The numbers line the old card kept behind "Why"
    # sits on the probability; the reasons sit on the pick's own words.
    if card.get("rail_line"):
        out["tips"]["prob"] = card["rail_line"]
    sentences = ((card.get("why") or {}).get("sentences") or [])[:2]
    if sentences:
        out["tips"]["line"] = " ".join(sentences)
    elif card.get("reasoning"):
        out["tips"]["line"] = card["reasoning"]
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
        out["tips"]["pays"] = language.pays_tip(pays)
        if entry and entry.get("size_words"):
            out["size_words"] = entry["size_words"]
        if entry and entry.get("edge_line_words"):
            out["edge_words"] = entry["edge_line_words"]
    elif state == "live":
        # THE ONE FIGURE A LIVE ROW MAY CARRY, with its word (ruled 2026-09-09).
        out["pregame_words"] = (entry or {}).get("pregame_words") or \
            language.pregame_words(shown)
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
    rows = conn.execute(
        "SELECT p.id, p.game_id, p.market_type, p.prop_type, p.subject,"
        "       p.line_asked, p.model_prob, p.model_side, p.predictor,"
        "       p.outcome, p.resolved_utc, g.home, g.away, g.status"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
        f"   AND p.game_id IN ({marks})"
        "   AND p.predictor IN (%s)"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)"
        "   AND NOT EXISTS (SELECT 1 FROM predictions later"
        "                   WHERE later.game_id = p.game_id"
        "                     AND later.market_type = p.market_type"
        "                     AND later.subject = p.subject"
        "                     AND later.predictor = p.predictor"
        "                     AND IFNULL(later.line_asked, -1e9)"
        "                         = IFNULL(p.line_asked, -1e9)"
        "                     AND later.created_utc > p.created_utc"
        "                     AND later.created_utc <= g.kickoff_utc)"
        " ORDER BY p.id" % ",".join("?" for _ in others),
        (sport, season, wk, *game_ids, *others)).fetchall()
    from .views import _prose_prop_type, shown_prob

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
        away = _club(sport, game["away"], names)
        home = _club(sport, game["home"], names)
        if state in ("live", "final"):
            away["score"] = game["away_score"]
            home["score"] = game["home_score"]
        row = {
            "game_id": game_id,
            "state": state,
            "n": pick["badge_n"] if pick else 0,
            "away": away,
            "home": home,
            "kickoff_utc": game["kickoff_utc"],
            "sport_key": sport,
            "sport_label": sport_label,
            "pick": pick,
            "questions": bets,
            "questions_words": language.game_questions_words(len(bets)),
            "yours_words": (language.taken_badge_words()
                            if any(b["taken"] for b in bets) else None),
        }
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
    games.sort(key=lambda g: ((g["kickoff_utc"] or ""), g["game_id"]))

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
        shown = block["prob"]
        cushion = None if shown is None else shown - be
        block.update({
            "player": player,
            "surname": language.surname(player),
            # NO NUMBER ON RECORD (close-out, deviation 2): the roster the
            # record loads carries none, so this is None until it does.
            "number": None,
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
        block["tips"]["number"] = "No number on record for this player."
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
    return {
        "labels": labels,
        "games": games,
        "games_n": len(games),
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
