"""What ONE DISTINCT BET is: the one function every count of a bet reads
(operator question 17, ruled 2026-09-27; question 21, ruled 2026-09-28;
built 2026-09-28).

THE RULINGS. Question 17: "one function defines a distinct bet: forecaster +
the venue's question (game, market, line). Morning and final pass of one
question count once; which pass counts stays each record's standing rule;
alt lines are separate questions. Q12's, Q14's and Q16's counts all use it."
Question 21: "the line the forecaster was asked (the rung). Two rungs on one
game are two questions."

THE KEY, as the brief of 2026-09-28 reads it: the forecaster
(`predictions.predictor`), the game, the market -- `market_type`, and the
prop type for a prop -- the subject (the team, the pairing or the player: a
prop's player is part of the venue's question), and the rung asked
(`predictions.line_asked`; NULL for a moneyline or a UFC distance, and NULL
is one value). It is the blind record's own unit, the key
`calibration.standing_row_clause` has kept one standing row per since
2026-09-03, with the prop type named as well as carried in the subject.

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
bet. NULL IS ONE VALUE in all three: SQL's `IS` treats two NULLs as equal
(the standing clause read `IFNULL(line_asked, -1e9)` for the same reason), a
window groups NULLs together, and Python's None equals None -- so a
moneyline's absent rung is one rung. A prop type written as NULL is not one
written as '': 32 NFL week-one props of 29 August carry no prop type (their
subject names it); measured on a copy of the record on 2026-09-28, naming
the prop type moves no count, because no count reads a prop with no type.

ON THE PREDICTION PATH'S SIDE OF LAW 1. Question 16's correction gates will
read this function, and `gridiron.correction` is inside the blind import
closure: so this module imports nothing of the package and names no market
data, and `audit.check_all_prediction_closures` refuses it if it ever does.
The recount that proves each door keys by it reads the venue's claims and
the line's snapshots, and lives outside the closure (`gridiron.recount`).
"""
from __future__ import annotations

#: THE KEY, WRITTEN ONCE (operator question 17, 2026-09-28). The columns of a
#: forecast that say whose answer it is and which question it answered. Every
#: form below is made from this tuple and from nothing else, and
#: `audit.check_every_count_keys_one_bet` refuses a count keyed any other way.
KEY = ("predictor", "game_id", "market_type", "prop_type", "subject",
       "line_asked")


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
