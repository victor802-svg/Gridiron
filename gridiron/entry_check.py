"""CHECK AN ENTRY: the form, the legs' games, the payouts typed, and the words
(GRIDIRON_ENTRY_CHECK, step 1; the brief of 2026-09-30,
docs/briefs/2026-09-30-entry-check.md, with ruling D of 2026-10-05; built
2026-10-07).

THE OPERATOR TYPES EVERY ENTRY (LAW 5's forbidden half, the brief's words:
"Gridiron never logs in to, reads, scrapes or calls any pick'em app, holds no
credential for one, never places or edits an entry"). This module reads the
form the operator filled in on the Props page -- the app, the entry type, the
legs (player, club, stat, line as typed, over or under, standard, goblin or
demon, the line before a discount), the payout the app shows for THIS entry
(a power multiplier or a flex table), whether he confirmed it, and a promo --
and answers with arithmetic (`gridiron.entry_math`, no model) and words
(`gridiron.language`). It imports nothing that can reach another machine, and
`audit.check_the_entry_check_reaches_no_app` holds it to that.

ONE CALCULATOR (reading (f), 2026-10-07). The Props page's entry rail is this
check, grown into the brief's form: its legs are the entry's (typed, or a prop
the operator marked put in with its player, club and stat, the line still
his to type), its payout field is the payout typed for the entry, and its
verdict is reading (h)'s at coin flips. The rail's three readings at the
model's chance on each leg's MAIN line are gone: that is the venue's line,
never the line the operator types, so beside a typed leg they would be numbers
under another contract's words (step A's rule), and the model at the typed
line is step 2's. None of them ever drew a number on the record: no leg has a
main line while the venue's prop series are unread (question 39).

WHAT IS WRITTEN: the payout the operator confirmed, once per change, to
`pickem_payouts_typed` (`remember`) -- his own typed default, reading (e). No
leg, no entry and no result is written anywhere.

WHICH GAME A LEG IS IN (reading (d)): from the record's own schedule and the
record's own game stats, never guessed. A leg is placed only where its typed
club has a game still to come (the earliest by its listed start, read as an
instant -- the live poll follows no NFL game, so a listed start is an NFL
game's start, question 38) and exactly one player of its typed name played
his latest game this season for that club. A leg that cannot be placed says
why, and the one-game check says it could not check it.
"""

from __future__ import annotations

import json
import math
import sqlite3
import unicodedata
from datetime import datetime

from . import config, db, entry_math, language, picks

#: THE APPS THE BRIEF NAMES (scope v1, 2026-09-30), each as the form sends it
#: and as a reader reads it. No address, no account and nothing about any of
#: them beyond its name: the operator types what each one shows.
APPS = (("prizepicks", "PrizePicks"), ("underdog", "Underdog"),
        ("chalkboard", "Chalkboard"))

ENTRY_TYPES = ("power", "flex")

#: RULING D (2026-10-05): "Legs are standard, goblin or demon". A leg's kind is
#: shown with it and moves no number: "break-even comes from that payout only".
LEG_KINDS = ("standard", "goblin", "demon")

SIDES = ("over", "under")

#: THE PROMOS STEP 1 READS: none, a payout the app raised, or a share of the
#: winnings added (with or without a cap). A deposit match is step 4's.
PROMOS = ("none", "raised", "profit")

#: NFL PLAYER PROPS ONLY (scope v1).
SPORT = "nfl"

#: The table the payouts typed are kept in (schema.sql), named in full in each
#: statement below, so the gate reads what each one writes
#: (`audit.entry_check_reach_faults`).
TABLE = "pickem_payouts_typed"

#: BOUNDS ON THE FORM, NOT FACTS ABOUT ANY APP (2026-10-07): each says what a
#: typed number can mean, and a number past one reads as a mistyped key.
PAYOUT_CEILING = 1000.0
LINE_CEILING = 10000.0
PERCENT_CEILING = 1000.0
UNITS_CEILING = 100000.0
WORDS_LIMIT = 80


class EntryRefused(ValueError):
    """A form the check cannot read, and why, in words a reader reads."""


# ---------------------------------------------------------------------------
# reading the form
# ---------------------------------------------------------------------------

def _number(raw, *, strip: str = "") -> float | None:
    """A typed number, or None where nothing was typed. Raises ValueError on
    anything that is not a finite number ("nan" included: a float to Python,
    and no number a reader typed)."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise ValueError("not a number")
    if isinstance(raw, (int, float)):
        got = float(raw)
    else:
        text = str(raw).strip().lower()
        for ch in strip:
            text = text.rstrip(ch).strip()
        if text == "":
            return None
        got = float(text)
    if math.isnan(got) or math.isinf(got):
        raise ValueError("not a finite number")
    return got


def _words(raw) -> str:
    return " ".join(str(raw or "").split())[:WORDS_LIMIT]


def _refuse(code: str, **detail) -> EntryRefused:
    return EntryRefused(language.entry_check_refused_words(code, **detail))


def _payout(raw, legs: int, entry_type: str, *, what: str) -> dict | None:
    """A payout as typed: a power entry's multiplier, or a flex entry's table
    of what k of the legs right pays (k from 1 to the legs; a row left empty
    pays nothing). None where nothing at all was typed."""
    raw = raw if isinstance(raw, dict) else {}
    if entry_type == "power":
        try:
            got = _number(raw.get("multiplier"), strip="x")
        except ValueError:
            raise _refuse("payout_number", what=what,
                          raw=str(raw.get("multiplier"))) from None
        if got is None:
            return None
        if got <= 1.0:
            raise _refuse("payout_low", what=what, got=got)
        if got > PAYOUT_CEILING:
            raise _refuse("payout_high", what=what, got=got, most=PAYOUT_CEILING)
        return {"multiplier": got}
    table_raw = raw.get("table") if isinstance(raw.get("table"), dict) else {}
    table: dict[int, float] = {}
    for k in range(1, legs + 1):
        cell = table_raw.get(str(k), table_raw.get(k))
        try:
            got = _number(cell, strip="x")
        except ValueError:
            raise _refuse("flex_number", what=what, right=k, legs=legs,
                          raw=str(cell)) from None
        if got is None:
            continue
        if got < 0.0 or got > PAYOUT_CEILING:
            raise _refuse("flex_bounds", what=what, right=k, legs=legs, got=got,
                          most=PAYOUT_CEILING)
        if got > 0.0:
            table[k] = got
    if not table:
        return None
    faults = entry_math.flex_table_faults(table, legs)
    if "pays_less_for_more" in faults:
        raise _refuse("flex_less_for_more", what=what, legs=legs)
    if "never_returns_the_unit" in faults:
        raise _refuse("flex_top", what=what, legs=legs)
    return {"table": table}


def read_form(body) -> dict:
    """The entry as the operator typed it, every field read and bounded, or
    `EntryRefused` with the words saying which field and why."""
    if not isinstance(body, dict):
        raise _refuse("not_a_form")
    app = str(body.get("app") or "")
    if app not in dict(APPS):
        raise _refuse("app")
    entry_type = str(body.get("entry_type") or "")
    if entry_type not in ENTRY_TYPES:
        raise _refuse("entry_type")
    legs_raw = body.get("legs")
    if not isinstance(legs_raw, list):
        raise _refuse("legs_count", n=0)
    if not entry_math.MIN_LEGS <= len(legs_raw) <= entry_math.MAX_LEGS:
        raise _refuse("legs_count", n=len(legs_raw))
    legs = []
    for n, raw in enumerate(legs_raw, 1):
        raw = raw if isinstance(raw, dict) else {}
        player = _words(raw.get("player"))
        if not player:
            raise _refuse("leg_player", leg=n)
        stat = _words(raw.get("stat"))
        if not stat:
            raise _refuse("leg_stat", leg=n)
        try:
            line = _number(raw.get("line"))
        except ValueError:
            raise _refuse("leg_line", leg=n, raw=str(raw.get("line"))) from None
        if line is None:
            raise _refuse("leg_line_missing", leg=n)
        if line < 0.0 or line > LINE_CEILING:
            raise _refuse("leg_line_bounds", leg=n, got=line)
        side = str(raw.get("side") or "")
        if side not in SIDES:
            raise _refuse("leg_side", leg=n)
        kind = str(raw.get("kind") or "")
        if kind not in LEG_KINDS:
            raise _refuse("leg_kind", leg=n)
        try:
            original = _number(raw.get("original_line"))
        except ValueError:
            raise _refuse("leg_original", leg=n,
                          raw=str(raw.get("original_line"))) from None
        if original is not None:
            if original < 0.0 or original > LINE_CEILING:
                raise _refuse("leg_original_bounds", leg=n, got=original)
            if abs(original - line) < entry_math.FLOAT_NOISE:
                raise _refuse("leg_original_same", leg=n, got=original)
        club = str(raw.get("club") or "").strip().upper()[:4]
        legs.append({"player": player, "club": club, "stat": stat, "line": line,
                     "side": side, "kind": kind, "original_line": original})
    size = len(legs)
    payout = _payout(body.get("payout"), size, entry_type, what="payout")
    if payout is None:
        raise _refuse("payout_missing")
    promo_raw = body.get("promo") if isinstance(body.get("promo"), dict) else {}
    promo_kind = str(promo_raw.get("kind") or "none")
    if promo_kind not in PROMOS:
        raise _refuse("promo_kind")
    promo: dict = {"kind": promo_kind}
    if promo_kind == "raised":
        raised = _payout(promo_raw.get("payout"), size, entry_type, what="raised")
        if raised is None:
            raise _refuse("raised_missing")
        if entry_type == "power":
            if raised["multiplier"] <= payout["multiplier"] + entry_math.FLOAT_NOISE:
                raise _refuse("raised_not_higher", got=raised["multiplier"],
                              base=payout["multiplier"])
        else:
            lower = [k for k in range(1, size + 1)
                     if raised["table"].get(k, 0.0)
                     < payout["table"].get(k, 0.0) - entry_math.FLOAT_NOISE]
            higher = [k for k in range(1, size + 1)
                      if raised["table"].get(k, 0.0)
                      > payout["table"].get(k, 0.0) + entry_math.FLOAT_NOISE]
            if lower:
                raise _refuse("raised_flex_lower", right=lower[0], legs=size)
            if not higher:
                raise _refuse("raised_not_higher_flex")
        promo["payout"] = raised
    elif promo_kind == "profit":
        try:
            percent = _number(promo_raw.get("percent"), strip="%")
        except ValueError:
            raise _refuse("percent") from None
        if percent is None or percent <= 0.0 or percent > PERCENT_CEILING:
            raise _refuse("percent")
        try:
            cap = _number(promo_raw.get("cap_units"))
        except ValueError:
            raise _refuse("cap") from None
        if cap is not None and (cap <= 0.0 or cap > UNITS_CEILING):
            raise _refuse("cap")
        # THE ENTRY IN UNITS IS ASKED ONLY WHERE THE CAP NEEDS IT (reading
        # (c)): without a cap it is not read at all -- not even refused, so a
        # word left in the field of a promo with no cap stops nothing
        # (2026-10-07, resumed build).
        entry_units = None
        if cap is not None:
            try:
                entry_units = _number(promo_raw.get("entry_units"))
            except ValueError:
                raise _refuse("entry_units") from None
            if entry_units is not None and (entry_units <= 0.0
                                            or entry_units > UNITS_CEILING):
                raise _refuse("entry_units")
        promo.update(percent=percent, cap_units=cap, entry_units=entry_units)
    return {"app": app, "entry_type": entry_type, "legs": legs, "payout": payout,
            "confirmed": body.get("payout_confirmed") is True, "promo": promo}


# ---------------------------------------------------------------------------
# which game each leg is in (reading (d))
# ---------------------------------------------------------------------------

def normalise(name: str | None) -> str:
    """A player's name folded for matching: accents, punctuation and case only
    -- the rule `market.crosswalk.normalise` measured for the MLB bridge,
    written again here because the entry check may import nothing that reads
    another machine (`audit.check_the_entry_check_reaches_no_app`). NOT
    nicknames, initials, suffixes or a fuzzy distance: each turns a failed
    match into a wrong one, and a leg left unplaced says so."""
    if not name:
        return ""
    stripped = unicodedata.normalize("NFKD", str(name))
    ascii_only = stripped.encode("ascii", "ignore").decode("ascii")
    for ch in (".", "'", "’", ","):
        ascii_only = ascii_only.replace(ch, "")
    ascii_only = ascii_only.replace("-", " ")
    return " ".join(ascii_only.lower().split())


def club_names(conn: sqlite3.Connection) -> dict[str, str]:
    """Each NFL club's full name from the record's `teams` rows (read from the
    feed, `data.teams`); a club with none keeps its code, never a guessed
    name."""
    return {r["tricode"]: r["display_name"] for r in conn.execute(
        "SELECT tricode, display_name FROM teams WHERE sport = ?", (SPORT,))}


def _games_to_come(conn: sqlite3.Connection, now: datetime) -> list[dict]:
    """Every NFL game the record lists as scheduled whose listed start, read
    as an instant, is after `now`, earliest first. A start nobody can read is
    left out: no leg is placed in a game the record cannot date."""
    out = []
    for r in conn.execute(
            "SELECT id, season, home, away, kickoff_utc, league_date FROM games"
            " WHERE sport = ? AND status = 'scheduled'", (SPORT,)):
        try:
            start = db.instant(r["kickoff_utc"])
        except ValueError:
            continue
        if start is None or start <= now:
            continue
        out.append(dict(r, start=start))
    out.sort(key=lambda g: (g["start"], g["id"]))
    return out


def _game_day(game: dict):
    """A game's league day as a date (its `league_date`, else its listed
    start's day), or None where the record has neither."""
    text = game.get("league_date") or (game.get("kickoff_utc") or "")[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date() if text else None
    except ValueError:
        return None


def _games_begun_or_undated(conn: sqlite3.Connection, now: datetime) -> tuple[dict, dict]:
    """THE GAMES THAT MAKE A CLUB'S NEXT GAME UNCERTAIN (the prover, 2026-10-07;
    reading (d), "never guessed"). Two maps by club: its LATEST game whose
    listed start, read as an instant, is at or before `now`, whatever its
    status; and its games not recorded as over whose start the record cannot
    read (`kickoff_utc` is NULL while nflverse lists a game's time as not yet
    set, `reference.kickoff_to_utc`).

    WHY: no poll follows an NFL game (question 38), so the record keeps one
    'scheduled' from its listed start until a refresh writes its result, and
    `_games_to_come` leaves it out from its start -- so a leg typed while its
    club's game was being played was put in the club's NEXT game, and two
    legs of that one game in two games of the next week, unflagged: the
    brief's planting, "an unflagged same-game pair". A game with no start
    time is left out of `_games_to_come` too, so a leg was put in the game
    after it. The latest begun game, not every one: a game the record never
    marked over years ago (a cancelled one) says nothing once the club has
    played since."""
    latest: dict[str, dict] = {}
    undated: dict[str, list] = {}
    for r in conn.execute(
            "SELECT id, season, home, away, kickoff_utc, league_date, status FROM games"
            " WHERE sport = ?", (SPORT,)):
        try:
            start = db.instant(r["kickoff_utc"])
        except ValueError:
            start = None
        if start is None:
            if r["status"] != "final":
                for club in (r["home"], r["away"]):
                    undated.setdefault(club, []).append(dict(r))
            continue
        if start > now:
            continue
        for club in (r["home"], r["away"]):
            held = latest.get(club)
            if held is None or (start, r["id"]) > (held["start"], held["id"]):
                latest[club] = dict(r, start=start)
    return latest, undated


def clubs_with_a_game_to_come(conn: sqlite3.Connection, now: datetime,
                              names: dict[str, str]) -> list[dict]:
    """The clubs the form offers: each with a game still to come on the
    record, by name."""
    codes = set()
    for g in _games_to_come(conn, now):
        codes.update((g["home"], g["away"]))
    return sorted(({"key": c, "label": language.entry_check_club_words(c, names)}
                   for c in codes), key=lambda o: (o["label"], o["key"]))


def _players_of_season(conn: sqlite3.Connection, season: int, cache: dict) -> dict:
    """Each player's club as of his latest game this season, by his folded
    name: {folded name: {player id: club}}, from the record's own game stats
    (`player_week_stats`, the rows the factors and the board's jersey read)."""
    if season in cache:
        return cache[season]
    latest: dict[str, tuple] = {}
    for r in conn.execute(
            "SELECT player_id, player_name, team, week FROM player_week_stats"
            " WHERE season = ?", (season,)):
        held = latest.get(r["player_id"])
        if held is None or r["week"] > held[0]:
            latest[r["player_id"]] = (r["week"], r["player_name"], r["team"])
    by_name: dict[str, dict] = {}
    for pid, (_week, name, club) in latest.items():
        by_name.setdefault(normalise(name), {})[pid] = club
    cache[season] = by_name
    return by_name


def game_of_leg(conn: sqlite3.Connection, leg: dict, *, now: datetime,
                games: list[dict], names: dict[str, str], cache: dict,
                begun: tuple[dict, dict] | None = None) -> dict:
    """The game a typed leg is in, where the record can say -- its club's
    next game still to come, and the typed player that club's, this season,
    by his latest game -- or why it cannot. Never guessed.

    AND ONLY WHERE THAT NEXT GAME IS CERTAIN (the prover, 2026-10-07): not
    while the club's latest game past its listed start is not recorded as
    over -- the leg may be in that game or the next -- nor while a game of
    the club not recorded as over has no start time and could come first
    (`_games_begun_or_undated`, which `check` hands in as `begun`)."""
    club = leg.get("club") or ""
    if not club:
        return {"game": None, "why": language.entry_check_unplaced_words("no_club")}
    game = next((g for g in games if club in (g["home"], g["away"])), None)
    club_words = language.entry_check_club_words(club, names)
    if game is None:
        return {"game": None, "why": language.entry_check_unplaced_words(
            "no_game", club=club_words)}
    latest, undated = begun if begun is not None else _games_begun_or_undated(conn, now)
    last = latest.get(club)

    def _named(g):
        return {"away": language.entry_check_club_words(g["away"], names),
                "home": language.entry_check_club_words(g["home"], names),
                "day": g.get("league_date") or (g.get("kickoff_utc") or "")[:10] or None}

    if last is not None and last["status"] != "final":
        return {"game": None, "why": language.entry_check_unplaced_words(
            "under_way", **_named(last))}
    floor, ceiling = (_game_day(last) if last else None), _game_day(game)
    for u in undated.get(club, ()):
        day = _game_day(u)
        if day is not None and floor is not None and day < floor:
            continue  # the club has played since: it says nothing now
        if day is None or ceiling is None or day <= ceiling:
            return {"game": None, "why": language.entry_check_unplaced_words(
                "undated", **_named(u))}
    players = _players_of_season(conn, int(game["season"]), cache)
    found = players.get(normalise(leg.get("player")), {})
    on_club = [pid for pid, c in found.items() if c == club]
    if len(on_club) == 1:
        return {"game": game, "why": None}
    if len(on_club) > 1:
        return {"game": None, "why": language.entry_check_unplaced_words(
            "two_players", player=leg.get("player"), club=club_words)}
    if found:
        elsewhere = sorted({language.entry_check_club_words(c, names)
                            for c in found.values()})
        return {"game": None, "why": language.entry_check_unplaced_words(
            "other_club", player=leg.get("player"), club=club_words,
            others=elsewhere)}
    return {"game": None, "why": language.entry_check_unplaced_words(
        "no_player", player=leg.get("player"), season=int(game["season"]))}


# ---------------------------------------------------------------------------
# the payouts typed (reading (e))
# ---------------------------------------------------------------------------

def _has_the_table(conn: sqlite3.Connection) -> bool:
    """A record no release carrying the table has opened yet, read through a
    read-only door (the gate's step 4), holds none: then nothing was typed
    (`board._player_number`'s precedent, 2026-09-29)."""
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                        " AND name = ?", (TABLE,)).fetchone() is not None


def _payout_of_row(row) -> dict:
    if row["entry_type"] == "power":
        return {"multiplier": float(row["multiplier"])}
    table = json.loads(row["flex_table"] or "{}") or {}
    return {"table": {int(k): float(v) for k, v in table.items()}}


def _same_payout(a: dict, b: dict) -> bool:
    if (a.get("table") is None) != (b.get("table") is None):
        return False
    if a.get("table") is None:
        return abs(float(a["multiplier"]) - float(b["multiplier"])) < entry_math.FLOAT_NOISE
    keys = set(a["table"]) | set(b["table"])
    return all(abs(float(a["table"].get(k, 0.0)) - float(b["table"].get(k, 0.0)))
               < entry_math.FLOAT_NOISE for k in keys)


def _field_values(payout: dict) -> dict:
    """The payout as the form's fields hold it: "3", or {"5": "10", ...}. TO
    FIFTEEN FIGURES (the prover, 2026-10-07): as handed, six, so a payout
    typed 123.4567 was offered back as 123.457 -- not the one typed (reading
    (e)) -- and, confirmed, kept again as another."""
    if payout.get("table") is not None:
        return {"table": {str(k): f"{v:.15g}" for k, v in sorted(payout["table"].items())}}
    return {"multiplier": f"{payout['multiplier']:.15g}"}


def remembered(conn: sqlite3.Connection) -> list[dict]:
    """THE LAST PAYOUT TYPED FOR EACH APP, ENTRY TYPE AND SIZE, offered filled
    in and never confirmed (reading (e)): the latest row of each key, with the
    form's field values and words saying what and when."""
    if not _has_the_table(conn):
        return []
    apps = dict(APPS)
    out = []
    for r in conn.execute(
            "SELECT t.* FROM pickem_payouts_typed t WHERE t.id = (SELECT MAX(u.id)"
            "  FROM pickem_payouts_typed u"
            "  WHERE u.app = t.app AND u.entry_type = t.entry_type"
            "    AND u.legs = t.legs)"):
        payout = _payout_of_row(r)
        size = language.entry_check_size_words(apps.get(r["app"], r["app"]),
                                               r["entry_type"], r["legs"])
        out.append({
            "app": r["app"], "entry_type": r["entry_type"], "legs": r["legs"],
            "fields": _field_values(payout),
            "typed_utc": r["typed_utc"],
            "words": language.entry_check_remembered_words(
                size, language.entry_check_payout_words(payout, r["legs"]),
                r["typed_utc"]),
        })
    out.sort(key=lambda e: (e["app"], e["entry_type"], e["legs"]))
    return out


def remember(conn: sqlite3.Connection, form: dict) -> bool:
    """Keep the payout the operator confirmed for this app, entry type and
    size, as typed -- a plain insert (the frozen register: no upsert), and
    only where it differs from the last one kept for the key. True where a
    row was written. The one write the entry check makes."""
    if not form.get("confirmed") or not _has_the_table(conn):
        return False
    app, entry_type, legs = form["app"], form["entry_type"], len(form["legs"])
    last = conn.execute(
        "SELECT * FROM pickem_payouts_typed WHERE app = ? AND entry_type = ? AND legs = ?"
        " ORDER BY id DESC LIMIT 1", (app, entry_type, legs)).fetchone()
    if last is not None and _same_payout(_payout_of_row(last), form["payout"]):
        return False
    payout = form["payout"]
    conn.execute(
        "INSERT INTO pickem_payouts_typed (typed_utc, app, entry_type, legs, multiplier,"
        " flex_table) VALUES (?, ?, ?, ?, ?, ?)",
        (db.utcnow(), app, entry_type, legs,
         None if payout.get("table") is not None else float(payout["multiplier"]),
         (json.dumps({str(k): float(v) for k, v in sorted(payout["table"].items())})
          if payout.get("table") is not None else None)))
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# the check
# ---------------------------------------------------------------------------

def _now(now) -> datetime:
    return db.instant(now or db.utcnow())


def _drawn_points(points: float) -> float:
    """THE GAP TO AN EVEN CHANCE AS DRAWN, to a hundredth of a point -- never
    at the bar when it is under it (ruling B.2's rule, `picks.drawn_edge`, at
    this page's hundredths): 2.996 points is drawn 2.99, not 3.00."""
    bar = config.PICK_MIN_EDGE * 100.0
    if points < bar - entry_math.FLOAT_NOISE * 100.0 and round(points, 2) >= bar:
        return math.floor(points * 100.0) / 100.0
    # NEVER "-0.00" (2026-10-07, resumed build): 8x on three legs breaks even
    # at 8 ** (-1/3), a hair over one half in floating point, and the gap
    # rounds to a signed zero the words would print.
    drawn = round(points, 2)
    return 0.0 if drawn == 0 else drawn


def check(conn: sqlite3.Connection, body, *, now=None, remember_it: bool = True) -> dict:
    """THE ENTRY CHECK: the form read, each leg placed in its game where the
    record can say, and -- once the payout is confirmed -- the break-even per
    leg, the expected return per unit at coin flips, a promo's payout and
    what it adds, the legs in one game, and reading (h)'s outline. Every
    sentence is `language`'s. Writes the payout confirmed (`remember`) and
    nothing else, and only when `remember_it`."""
    words = language.entry_check_panel_words()
    out = {"open": True, "refused_words": None, "ask_words": None,
           "computed": False, "signal": "none", "verdict_words": None,
           "verdict_tip": None, "lines": [], "promo_words": None,
           "one_game_words": [], "legs": [], "note": words["note"],
           "remembered": [], "remembered_now_words": None, "numbers": None}
    try:
        form = read_form(body)
    except EntryRefused as exc:
        out["refused_words"] = str(exc)
        out["remembered"] = remembered(conn)
        return out
    at = _now(now)
    names = club_names(conn)
    games = _games_to_come(conn, at)
    begun = _games_begun_or_undated(conn, at)
    cache: dict = {}
    placed = [game_of_leg(conn, leg, now=at, games=games, names=names, cache=cache,
                          begun=begun)
              for leg in form["legs"]]
    for leg, where in zip(form["legs"], placed):
        game = where["game"]
        out["legs"].append({
            "words": language.entry_check_leg_words(
                leg["player"], leg["side"], leg["line"], leg["stat"]),
            "detail_words": language.entry_check_leg_detail_words(
                leg["kind"], leg["original_line"]),
            "game_words": (language.entry_check_game_words(
                language.entry_check_club_words(game["away"], names),
                language.entry_check_club_words(game["home"], names),
                game["league_date"] or (game["kickoff_utc"] or "")[:10])
                if game else None),
            "unplaced_words": where["why"],
        })
    groups = entry_math.one_game_groups([w["game"]["id"] if w["game"] else None
                                         for w in placed])
    unchecked = [i for i, w in enumerate(placed) if w["game"] is None]
    out["one_game_words"] = language.entry_check_one_game_words(
        [(g, out["legs"][g[0]]["game_words"]) for g in groups], unchecked,
        len(placed))
    if not form["confirmed"]:
        # NOTHING IS WORKED OUT FROM A PAYOUT NOT CONFIRMED (reading (e)):
        # one the page filled in is the last one typed, offered, and the
        # operator says whether it is what the app shows for this entry.
        out["ask_words"] = words["confirm_first"]
        out["remembered"] = remembered(conn)
        return out
    promo = form["promo"]
    if (promo["kind"] == "profit" and promo["cap_units"] is not None
            and promo["entry_units"] is None):
        # THE ENTRY IN UNITS, ONLY BECAUSE THE CAP NEEDS IT (reading (c)).
        out["ask_words"] = words["entry_units_first"]
        out["remembered"] = remembered(conn)
        return out
    legs = len(form["legs"])
    typed = form["payout"]
    # EVERY NUMBER FROM THE PAYOUT TYPED FOR THIS ENTRY, AND ITS PROMO ONCE
    # (ruling D: "break-even comes from that payout only"; the brief's
    # planting, "a boost applied twice"): a leg's kind, line and discount
    # reach none of it.
    be = entry_math.breakeven(typed, legs)
    ev = entry_math.expected_return(typed, legs)
    offered, offered_be, offered_ev, adds = typed, be, ev, None
    if promo["kind"] == "raised":
        offered = promo["payout"]
    elif promo["kind"] == "profit":
        offered = entry_math.with_a_profit_promo(
            typed, percent=promo["percent"], cap_units=promo["cap_units"],
            entry_units=promo["entry_units"])
    if promo["kind"] != "none":
        offered_be = entry_math.breakeven(offered, legs)
        offered_ev = entry_math.expected_return(offered, legs)
        adds = offered_ev - ev
    # READING (h), ON THE ENTRY AS OFFERED (its promo in): green where every
    # leg's break-even is three points or more under an even chance -- B.2's
    # bar, the one door (`picks.clears_the_pick_bar`) -- red where the entry
    # returns less than it costs at coin flips, and no outline between.
    edge = entry_math.edge_at_a_coin_flip(offered_be)
    if picks.clears_the_pick_bar(edge):
        signal = "clears"
    elif entry_math.costs(offered_ev):
        signal = "costs"
    else:
        signal = "none"
    points = _drawn_points(edge * 100.0)
    out.update(computed=True, signal=signal,
               verdict_words=language.entry_check_verdict_words(
                   signal, points, promo=promo["kind"] != "none", raw=edge * 100.0),
               verdict_tip=language.entry_check_verdict_tip(config.PICK_MIN_EDGE))
    lines = [
        {"label": words["line_breakeven"],
         "value_words": language.entry_check_breakeven_words(be),
         "tip": language.entry_check_breakeven_tip(typed, legs)},
        {"label": words["line_return"],
         "value_words": language.entry_check_return_words(ev),
         "tip": words["return_tip"]},
    ]
    if promo["kind"] != "none":
        out["promo_words"] = language.entry_check_promo_words(
            promo["kind"], typed, offered, legs, percent=promo.get("percent"),
            cap_units=promo.get("cap_units"), entry_units=promo.get("entry_units"))
        lines += [
            {"label": words["line_promo_breakeven"],
             "value_words": language.entry_check_breakeven_words(offered_be),
             "tip": language.entry_check_breakeven_tip(offered, legs)},
            {"label": words["line_promo_return"],
             "value_words": language.entry_check_return_words(offered_ev),
             "tip": words["return_tip"]},
            {"label": words["line_promo_adds"],
             "value_words": language.entry_check_return_words(adds),
             "tip": words["adds_tip"]},
        ]
    lines.append({"label": words["line_promo_gap" if promo["kind"] != "none" else "line_gap"],
                  "value_words": language.entry_check_gap_words(points, raw=edge * 100.0),
                  "tip": words["gap_tip"]})
    out["lines"] = lines
    out["numbers"] = {
        "breakeven": round(be, 6), "expected": round(ev, 6),
        "offered_breakeven": round(offered_be, 6), "offered_expected": round(offered_ev, 6),
        "promo_adds": None if adds is None else round(adds, 6),
        "edge_points": round(edge * 100.0, 6),
        "payout": _field_values(typed), "offered": _field_values(offered),
        "groups": groups, "unchecked": unchecked,
    }
    if remember_it and remember(conn, form):
        apps = dict(APPS)
        out["remembered_now_words"] = language.entry_check_remembered_now_words(
            language.entry_check_size_words(apps[form["app"]], form["entry_type"], legs),
            language.entry_check_payout_words(typed, legs))
    out["remembered"] = remembered(conn)
    return out


def panel(conn: sqlite3.Connection, *, sport: str, tiles: list[dict],
          now=None) -> dict:
    """WHAT THE PROPS PAGE DRAWS THE FORM FROM: its words, the apps, entry
    types, kinds, sides and promos, the clubs with a game still to come, the
    record's stat words, the props the operator marked (each put in with its
    player, club and stat and no line -- the line is the app's, and his to
    type), and the payouts last typed. NFL only (scope v1): another sport's
    page says so. Reads only."""
    words = language.entry_check_panel_words()
    if sport != SPORT:
        return {"open": False, "heading": words["heading"],
                "closed_words": words["closed"]}
    at = _now(now)
    names = club_names(conn)
    marked = []
    for t in tiles:
        if not t.get("taken") or t.get("state") != "upcoming":
            continue
        stat = t.get("family_words") or ""
        marked.append({"player": t.get("player") or "",
                       "club": ((t.get("club") or {}).get("tricode") or ""),
                       "stat": stat,
                       "words": language.prop_leg_words(t.get("player"), stat)})
    return {
        "open": True,
        "heading": words["heading"],
        "labels": words,
        "apps": [{"key": k, "label": label} for k, label in APPS],
        "types": [{"key": k, "label": words[f"type_{k}"]} for k in ENTRY_TYPES],
        "kinds": [{"key": k, "label": words[f"kind_{k}"]} for k in LEG_KINDS],
        "sides": [{"key": k, "label": words[f"side_{k}"]} for k in SIDES],
        "promos": [{"key": k, "label": words[f"promo_{k}"]} for k in PROMOS],
        "clubs": clubs_with_a_game_to_come(conn, at, names),
        "stats": [language.market_words(SPORT, f)
                  for f in config.SPORT_PROP_MARKETS.get(SPORT, ())],
        "marked": marked,
        "remembered": remembered(conn),
        "min_legs": entry_math.MIN_LEGS,
        "max_legs": entry_math.MAX_LEGS,
        "leg_labels": [language.entry_check_leg_label(n)
                       for n in range(1, entry_math.MAX_LEGS + 1)],
        "flex_rows": {str(n): [{"right": k, "label": language.entry_check_flex_row_words(k, n)}
                               for k in range(n, 0, -1)]
                      for n in range(entry_math.MIN_LEGS, entry_math.MAX_LEGS + 1)},
        "note": words["note"],
    }
