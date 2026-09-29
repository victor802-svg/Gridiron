"""What ONE DISTINCT BET is: the one function every count of a bet reads
(operator question 17, ruled 2026-09-27; question 21, ruled 2026-09-28;
built 2026-09-28).

THE RULINGS. Question 17: "one function defines a distinct bet: forecaster +
the venue's question (game, market, line). Morning and final pass of one
question count once; which pass counts stays each record's standing rule;
alt lines are separate questions. Q12's, Q14's and Q16's counts all use it."
Question 21: "the line the forecaster was asked (the rung). Two rungs on one
game are two questions."

THE KEY: the forecaster (`predictions.predictor`), the game, the market
(`market_type`), the subject (the team, the pairing or the player -- and for
a prop the player AND the prop, 'Drake London receiving_yards': a prop's
player and its stat are both the venue's question), and the rung asked
(`predictions.line_asked`; NULL for a moneyline or a UFC distance, and NULL
is one value). It is the blind record's own unit, the key
`calibration.standing_row_clause` has kept one standing row per since
2026-09-03.

THE PROP TYPE IS NOT A COLUMN OF THE KEY (2026-09-29). A prop's question is
named by its subject, and `prop_type` is a column the earliest rows lack: 32
NFL week-one props written on 29 August at 05:55Z (fs1) carry none, and ten
of those questions -- the same player, prop and rung -- were asked again at
07:34Z (fs2) with it set. Keyed by the prop type as well (`IS`: NULL is not
'receiving_yards'), each of the ten was two questions, and the eight settled
ones stood twice in every reader that counts a sport's markets together: 14
NFL figures moved that no ruling names (the factor table's N and effects,
"scored over 154" to 162, the pick card's worst-band footnote, a tier
table's pace), against the ruling's "morning and final pass of one question
count once". The brief of 2026-09-28 had named the prop type as well as the
subject; this reverses that reading, back to the question
`calibration.resolved` has kept the prop type out of since ruling R4
(2026-09-02), for this same pair of runs ("keying on it split ten questions
that are plainly the same one"). Read on the live record on 2026-09-29,
read-only: all 252 typed prop rows' subjects end with their type, each of
the 32 untyped ones names one, and no game holds one subject under two prop
types -- so the subject tells every prop question apart, and leaving the
type out joins exactly those ten, each with itself. A door that NAMES a
prop's market selects `prop_type` beside the key, never in it; a count of
one prop type filters by it (`WHERE p.prop_type = ?`), never keys by it.

WHY ONE MODULE (2026-09-28). Until this date six keys counted a bet: the
standing clause and the priced and outlook doors (the question, the rung
included), `drift.bet_of` (the game and market, the player for a prop; no
rung), the at-the-line door (game, market and side; no rung and no player)
and its coverage line (the game alone), and question 12's recommendation
pairs (game and market across forecasters). The live NCAAF point spread
record holds twelve games asked at two rungs: two bets to the priced record
and the outlook, one to the drift and at-the-line records.

ONE TEXT, THREE FORMS. `KEY` is written once. `of` reads it off a row for
Python; `columns` writes it as a SQL column list, for a SELECT (so a door's
rows carry what `of` reads, off the forecast itself) and for a window's
PARTITION BY; `same` writes it as the SQL condition that two rows are one
bet. (A fourth from 2026-09-28, `given`: the condition that a row is the bet
whose key is handed in as parameters -- operator question 27's early pass
asking whether its question's final pass is written.) NULL IS ONE VALUE in
all of them: SQL's `IS` treats two NULLs as equal
(the standing clause read `IFNULL(line_asked, -1e9)` for the same reason), a
window groups NULLs together, and Python's None equals None -- so a
moneyline's absent rung is one rung.

ON THE PREDICTION PATH'S SIDE OF LAW 1. Question 16's correction gates read
this function (from 2026-09-29: `correction.settled_rows` selects
`bet.columns`, and every count of it is `bet.count`), and `gridiron.correction`
is inside the blind import closure: so this module imports nothing of the
package and names no market data, and `audit.check_all_prediction_closures`
refuses it if it ever does.
The recount that proves each door keys by it reads the venue's claims and
the line's snapshots, and lives outside the closure (`gridiron.recount`).
"""
from __future__ import annotations

#: THE KEY, WRITTEN ONCE (operator question 17, 2026-09-28). The columns of a
#: forecast that say whose answer it is and which question it answered. Every
#: form below is made from this tuple and from nothing else, and
#: `audit.check_every_count_keys_one_bet` refuses a count keyed any other way.
#:
#: NO `prop_type` (2026-09-29): the question is named by its subject, and a
#: column the early rows lack split one question in two -- a week-one prop
#: asked at 05:55Z with no prop type and again at 07:34Z with one stood
#: twice (the module's text above says what that moved).
KEY = ("predictor", "game_id", "market_type", "subject", "line_asked")


class NotABet(ValueError):
    """A row counted as a bet does not carry the key's columns."""


def of(row) -> tuple:
    """Which distinct bet a row is on: its forecaster and its question.

    Reads a database row, a dict or an object carrying the key's names. A row
    that lacks one is refused by name rather than counted as some other bet:
    a door whose SELECT dropped the rung would otherwise count every rung as
    one.
    """
    try:
        if hasattr(row, "keys"):
            return tuple(row[column] for column in KEY)
        return tuple(getattr(row, column) for column in KEY)
    except (KeyError, IndexError, AttributeError) as exc:
        raise NotABet(
            f"a row counted as a distinct bet does not carry the key's "
            f"columns {list(KEY)} ({exc}): every door selects "
            f"`bet.columns(...)` off the forecast itself, so the key is read "
            f"where it was written (operator question 17, 2026-09-28)") from exc


def count(rows) -> int:
    """How many distinct bets a list of rows is on: ONE count for every
    record's `distinct_bets`."""
    return len({of(r) for r in rows})


def columns(alias: str) -> str:
    """The key as SQL columns of one table alias, named as the forecast names
    them -- for a SELECT list and for a window's PARTITION BY."""
    return ", ".join(f"{alias}.{column}" for column in KEY)


def same(a: str, b: str) -> str:
    """The key as SQL: the rows of two aliases are one distinct bet.

    `IS`, never `=`: NULL is one value, as it is to `of`. Measured on a copy
    of the record on 2026-09-28, SQLite searches the question index with it
    as it did with `=`.
    """
    return " AND ".join(f"{a}.{column} IS {b}.{column}" for column in KEY)


def given(alias: str) -> str:
    """The key as SQL against values handed in: a row of `alias` is the
    distinct bet whose key is passed as the parameters, in `KEY`'s order --
    `bet.of(...)` of the question being asked (operator question 27, ruled
    2026-09-28: the early pass asks whether ITS question's final pass is
    written, before it writes; `predict.final_pass_written`).

    A FOURTH FORM, made from the same tuple. `IS`, never `=`: a moneyline's
    absent rung is one rung here too.
    """
    return " AND ".join(f"{alias}.{column} IS ?" for column in KEY)
