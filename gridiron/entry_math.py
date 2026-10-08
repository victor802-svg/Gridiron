"""THE ARITHMETIC OF A PICK'EM ENTRY, AND NOTHING ELSE (GRIDIRON_ENTRY_CHECK,
step 1; the brief of 2026-09-30, docs/briefs/2026-09-30-entry-check.md, with
the operator's amendments of 2026-10-05, ruling D; built 2026-10-07).

The brief, step 1, whole: "the arithmetic (no model): 'Check an entry' on the
Props page: app, entry type, legs (player, stat, line, over/under, original
line if discounted), payout (power multiplier or flex table), optional boost
(boosted multiplier, or profit-boost percent and cap, converted and shown).
Output: break-even per leg (power M^(-1/N); flex solved from the typed table);
EV per unit at coin-flip legs; the boost's value (EV with minus without); a
same-game flag on legs from one game ('these legs move together; the math
assumes they don't'), no correlation estimate (LAW 2)."

PURE PYTHON, THE STANDARD LIBRARY ONLY, NO RECORD AND NO WORDS. Every number
here is worked from the payout the operator typed for the entry and from an
even chance on every leg -- ruling D: "the operator types the line and the
payout the app shows for the entry; break-even comes from that payout only" --
so a leg's kind (standard, goblin, demon), its line and its discount reach no
function in this module. The words are `gridiron.language`'s, the form and the
record are `gridiron.entry_check`'s, and nothing here imports either.

THE READINGS (recorded in docs/REPAIR_STATE.md, "Rulings taken in your
absence", 2026-10-07):

  * POWER: every leg must be right; the entry returns M per unit. The
    break-even per leg is the chance p at which M * p**N = 1, so
    p = M ** (-1/N); the expected return per unit at an even chance on every
    leg is M * 0.5**N - 1.
  * FLEX: the typed table gives what the entry returns per unit when k of its
    N legs are right (a row left empty pays nothing, and none right pays
    nothing). With the legs independent at p, the expected return per unit is
    the sum over k of C(N, k) p**k (1 - p)**(N - k) times the payout for k,
    less the unit; at an even chance that is the sum of C(N, k) / 2**N times
    the payout for k, less one. The break-even per leg is the p at which that
    is zero, SOLVED BY BISECTION until the interval is a trillionth wide --
    far finer than the hundredth of a point the page shows. A table that pays
    less for more legs right has no single break-even and is refused by the
    caller (`flex_table_faults`), as is one whose every-leg-right payout does
    not return the unit (no break-even short of certainty).
  * A RAISED PAYOUT (the app's own raised multiplier or table) replaces the
    typed payout; A PROFIT PROMO adds a share of the profit -- the payout less
    the unit, where the payout returns more than the unit -- at most the cap
    over the entry (both in units, never dollars) where there is a cap. EITHER
    IS APPLIED ONCE, to the payout typed, never to a payout already raised
    (the brief's planting, "a boost applied twice"); what it adds is the
    expected return with it less the expected return without it.
  * LEGS IN ONE GAME are grouped by the game each was placed in, and that is
    all: no number is put on how they move together (LAW 2: a correlation
    nobody declared is not estimated).
  * A DEPOSIT MATCH (step 4, 2026-10-08): `deposit_match`, per unit of bonus,
    from the same return per unit staked -- one calculator, never a second
    that could disagree with the first.
"""

from __future__ import annotations

import math

#: THE SIZES OF ENTRY THE FORM ACCEPTS (2026-10-07). A bound on the form, not
#: a fact about any app: an entry of one leg is a single, and the three apps
#: the brief names offer none past eight.
MIN_LEGS = 2
MAX_LEGS = 8

#: An even chance on every leg: step 1 has no model.
COIN_FLIP = 0.5

#: FLOAT NOISE, NOT A MARGIN (`picks.FLOAT_NOISE`'s rule, C's prover,
#: 2026-10-06): nothing typed is finer than a billionth, and an entry that
#: returns exactly its cost may be worked out a hair under it.
FLOAT_NOISE = 1e-9

#: The bisection stops when the interval is narrower than this: a trillionth
#: of a probability, against the hundredth of a point the page shows.
BISECTION_WIDTH = 1e-12


def power_breakeven(multiplier: float, legs: int) -> float:
    """The chance each leg must have for a power entry to return its cost:
    M ** (-1/N)."""
    return float(multiplier) ** (-1.0 / int(legs))


def power_return(multiplier: float, legs: int, p: float = COIN_FLIP) -> float:
    """What a power entry returns per unit, less the unit, with every leg at
    the chance `p`: M * p**N - 1."""
    return float(multiplier) * float(p) ** int(legs) - 1.0


def flex_return(table: dict[int, float], legs: int, p: float = COIN_FLIP) -> float:
    """What a flex entry returns per unit, less the unit, with its legs
    independent at the chance `p`: the sum over k of C(N, k) p**k (1-p)**(N-k)
    times the payout for k right, less one. A k the table does not hold pays
    nothing."""
    n = int(legs)
    p = float(p)
    total = 0.0
    for k in range(n + 1):
        pays = float(table.get(k, 0.0) or 0.0)
        if pays:
            total += math.comb(n, k) * p ** k * (1.0 - p) ** (n - k) * pays
    return total - 1.0


def flex_table_faults(table: dict[int, float], legs: int) -> list[str]:
    """Why a flex table has no single break-even, as codes the caller words:
    'pays_less_for_more' where a row pays less than the row below it, and
    'never_returns_the_unit' where every leg right returns no more than the
    unit. Empty where the table can be solved."""
    n = int(legs)
    faults: list[str] = []
    rows = [float(table.get(k, 0.0) or 0.0) for k in range(n + 1)]
    if any(rows[k + 1] < rows[k] for k in range(n)):
        faults.append("pays_less_for_more")
    if rows[n] <= 1.0:
        faults.append("never_returns_the_unit")
    return faults


def flex_breakeven(table: dict[int, float], legs: int) -> float:
    """The chance each leg must have, the legs independent, for a flex entry to
    return its cost: the root of `flex_return` on (0, 1), by bisection.

    THE ROOT IS ONE AND THE BISECTION FINDS IT: with a table that pays no less
    for more legs right, the expected return rises with p (more legs right is
    more likely as p rises), from the unit lost at p = 0 to the every-leg
    payout less the unit at p = 1, which `flex_table_faults` holds above zero.
    """
    faults = flex_table_faults(table, legs)
    if faults:
        raise ValueError(f"a flex table with no single break-even: {faults}")
    lo, hi = 0.0, 1.0
    while hi - lo > BISECTION_WIDTH:
        mid = (lo + hi) / 2.0
        if flex_return(table, legs, mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def breakeven(payout: dict, legs: int) -> float:
    """The break-even per leg of a payout as the form reads it: a power
    entry's {"multiplier": M} or a flex entry's {"table": {k: payout}}."""
    if payout.get("table") is not None:
        return flex_breakeven(payout["table"], legs)
    return power_breakeven(payout["multiplier"], legs)


def expected_return(payout: dict, legs: int, p: float = COIN_FLIP) -> float:
    """The expected return per unit, less the unit, of a payout as the form
    reads it, every leg at `p`."""
    if payout.get("table") is not None:
        return flex_return(payout["table"], legs, p)
    return power_return(payout["multiplier"], legs, p)


def with_a_profit_promo(payout: dict, *, percent: float,
                        cap_units: float | None = None,
                        entry_units: float | None = None) -> dict:
    """THE PAYOUT TYPED, WITH A PROFIT PROMO ADDED ONCE: each payout that
    returns more than the unit gains `percent` per cent of its profit (the
    payout less the unit), at most `cap_units` over `entry_units` per unit
    where there is a cap. A payout that returns the unit or less has no
    profit and gains nothing. Units only, never dollars.

    APPLIED TO THE PAYOUT TYPED, NEVER TO ONE ALREADY RAISED: the caller hands
    this the operator's typed payout, and what it returns is never handed to
    it again (the brief's planting, "a boost applied twice")."""
    share = float(percent) / 100.0
    if cap_units is not None:
        if not entry_units:
            raise ValueError("a capped profit promo needs the entry in units")
        most = float(cap_units) / float(entry_units)
    else:
        most = None

    def raised(pays: float) -> float:
        pays = float(pays)
        if pays <= 1.0:
            return pays
        added = share * (pays - 1.0)
        if most is not None:
            added = min(added, most)
        return pays + added

    if payout.get("table") is not None:
        return {"table": {k: raised(v) for k, v in payout["table"].items()}}
    return {"multiplier": raised(payout["multiplier"])}


def return_at_chances(payout: dict, chances: list[float]) -> float:
    """THE RETURN PER UNIT, LESS THE UNIT, WITH EACH LEG AT ITS OWN CHANCE
    (the entry check's step 2, 2026-10-07: "Show model EV beside coin-flip
    EV"). THE LEGS INDEPENDENT (LAW 2: no correlation nobody declared is
    estimated -- legs in one game are flagged, and the arithmetic is the
    same payout's with its legs in different games).

    POWER: every leg right, M times the product of the chances, less one.
    FLEX: the chance of exactly k legs right, built leg by leg (the
    distribution of a count of independent legs, each its own chance), times
    what k right pays, summed, less one. With every chance an even one these
    are `power_return` and `flex_return` at a coin flip."""
    chances = [float(p) for p in chances]
    if payout.get("table") is None:
        product = 1.0
        for p in chances:
            product *= p
        return float(payout["multiplier"]) * product - 1.0
    right = [1.0]                      # right[k]: the chance of exactly k right
    for p in chances:
        nxt = [0.0] * (len(right) + 1)
        for k, w in enumerate(right):
            nxt[k] += w * (1.0 - p)
            nxt[k + 1] += w * p
        right = nxt
    table = payout["table"]
    return sum(w * float(table.get(k, 0.0) or 0.0) for k, w in enumerate(right)) - 1.0


def deposit_match(payout: dict, legs: int, *, playthrough: float,
                  p: float = COIN_FLIP) -> dict:
    """A DEPOSIT MATCH AFTER ITS PLAYTHROUGH, PER UNIT OF BONUS (the entry
    check's step 4; the brief of 2026-09-30: "deposit match calculator: typed
    bonus, playthrough multiple, entry type and payout used for playthrough;
    output the bonus's expected value after playthrough at coin-flip legs,
    with the playthrough cost shown"; built 2026-10-08, reading (c) recorded
    in docs/REPAIR_STATE.md).

    THE ARITHMETIC, ON ONE UNIT OF BONUS (reading (b): every figure is per
    unit of bonus, so a bonus of B units is B times each): to release it the
    operator stakes `playthrough` units in entries of the typed type and
    payout; each unit staked returns, less the unit, what `expected_return`
    gives that payout with every leg at `p` -- step 1's own arithmetic of that
    entry, so the two cannot disagree. The playthrough's expected cost is the
    stake times minus that return (below zero it is a gain), and the bonus
    after its playthrough is the bonus, ONCE, less that cost, ONCE:
    1 + playthrough x return. Nothing else: no variance, no bankroll, no
    chance of running out before the playthrough is staked (the step asks for
    the expected figure alone, and LAW 5 permits that arithmetic).

    Worked by hand (2026-10-08): 2 legs at 3x, a 5x playthrough -- each unit
    staked -0.25, staked 5, cost 1.25, after -0.25; at 4.5x -- +0.125, a gain
    of 0.625, after +1.625."""
    per_unit_staked = expected_return(payout, legs, p)
    staked = float(playthrough)
    # 0.0 LESS, NOT A NEGATION: an entry returning exactly its cost costs
    # nothing, never "-0.0".
    cost = 0.0 - staked * per_unit_staked
    return {"per_unit_staked": per_unit_staked, "staked": staked, "cost": cost,
            "after": 1.0 - cost}


def edge_at_a_coin_flip(breakeven_per_leg: float) -> float:
    """How far an even chance sits above the break-even per leg, as a share
    of a dollar (0.03 is three points): the edge of a leg at a coin flip,
    which ruling B.2's bar reads (reading (h))."""
    return COIN_FLIP - float(breakeven_per_leg)


def costs(expected: float) -> bool:
    """Reading (h)'s red outline: the expected return per unit at coin flips
    is below zero -- less float noise, so an entry that returns exactly its
    cost is not said to cost."""
    return float(expected) < -FLOAT_NOISE


def one_game_groups(games: list) -> list[list[int]]:
    """The legs (by their place in the entry, from 0) that share a game, two
    or more to a game, in the order their first leg stands. A leg placed in
    no game (None) is in no group; the caller says it could not be checked.
    Nothing is estimated about how a group's legs move together (LAW 2)."""
    seen: dict = {}
    for i, game in enumerate(games):
        if game is None:
            continue
        seen.setdefault(game, []).append(i)
    return [legs for legs in seen.values() if len(legs) >= 2]
