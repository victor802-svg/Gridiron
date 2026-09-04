"""Counts modelled as rates (Session C, 2026-09-03).

THE CAUSAL CLAIM THIS TESTS, stated before it is tested: a small-count event
forecast by a logistic built for continuous yardage will be overconfident,
because the logistic is asked to express "will he throw more than 1.5 touchdown
passes" as a single squashed number with no notion that the underlying quantity
is 0, 1, 2 or 3. A count is honestly modelled as a RATE: predict the expected
count, and the probability of clearing a rung follows from the distribution.

MEASURED BEFORE CHOOSING A FORM, over the stored record:

    market                    n       mean      var   var/mean
    nfl passing_tds        5,714      1.450    1.330      0.918   Poisson-like
    mlb batter_home_runs 138,987      0.114    0.116      1.017   Poisson-like
    mlb batter_hits      138,987      0.823    0.747      0.907   Poisson-like
    nfl receptions        26,488      3.911    4.869      1.245   OVER-dispersed
    mlb pitcher_strikeouts 13,917     4.783    6.130      1.282   OVER-dispersed

A Poisson has variance equal to its mean. Two of these markets do not, by a
quarter or more, and a Poisson there would understate the spread -- which is
itself a way of being overconfident, and would have swapped one such error for
another. Those two get a negative binomial with the MEASURED dispersion.

NOTHING HERE IS SHIPPED ON THE STRENGTH OF THE ARGUMENT ABOVE. The brief is
explicit: if the rate form is not better calibrated in the walk-forward, it does
not ship. `compare_forms` is what decides, and the number decides on its date.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: WHICH MARKETS ARE COUNTS, declared rather than guessed from a name.
#:
#: A market is here when the quantity being asked about is a small non-negative
#: integer. Yardage is not: 95.5 rushing yards is a continuous quantity that
#: happens to be written with a decimal, and modelling it as a rate would be
#: the mirror of the error this module exists to fix.
COUNT_MARKETS: dict[str, str] = {
    "passing_tds": "poisson",
    "batter_home_runs": "poisson",
    "batter_hits": "poisson",
    # MARKET_ROSTER #3, measured 2026-09-04 over 125,298 stored batter-games:
    # mean 0.889, variance 0.754, ratio 0.848. UNDER-dispersed rather than
    # over, so a Poisson is the honest form and the negative binomial would be
    # claiming a spread the data does not have.
    "batter_strikeouts": "poisson",
    "receptions": "negative_binomial",
    "pitcher_strikeouts": "negative_binomial",
}

#: Measured variance-to-mean ratios, dated. Used as the negative binomial's
#: dispersion; a Poisson market keeps 1.0 by definition rather than by fiat.
DISPERSION: dict[str, float] = {
    "passing_tds": 0.918,
    "batter_home_runs": 1.017,
    "batter_hits": 0.907,
    "batter_strikeouts": 0.848,
    "receptions": 1.245,
    "pitcher_strikeouts": 1.282,
}
DISPERSION_DECLARED = "2026-09-03T00:00:00Z"

#: How far from 1.0 a variance-to-mean ratio must sit before a Poisson is the
#: wrong form. Declared, because "materially exceeds" needs a number: 15% is
#: the point at which the implied standard deviation is off by about 7%, which
#: moves a rung probability by enough to see.
OVERDISPERSION_THRESHOLD = 1.15


class NotFitted(RuntimeError):
    """A rate model that could not be fitted, said out loud."""


@dataclass
class RateFit:
    """A fitted rate model. Mirrors `logistic.Fit` so callers read one shape."""

    names: list[str]
    coefficients: list[float]
    intercept: float
    n: int
    iterations: int
    converged: bool
    l2: float
    form: str = "poisson"
    dispersion: float = 1.0
    presence: dict = field(default_factory=dict)
    dropped: dict = field(default_factory=dict)
    constant: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        """The same envelope a logistic fit uses, plus what makes it a rate.

        `form` is the flag `load_fit` reads to decide which object to rebuild.
        A stored fit that did not say which form produced it would be read as a
        logistic and its coefficients interpreted through the wrong link --
        silently, because both are just numbers.
        """
        return {
            "form": self.form,
            "dispersion": self.dispersion,
            "intercept": self.intercept,
            "coefficients": {n: c for n, c in zip(self.names, self.coefficients)},
            "n": self.n,
            "l2": self.l2,
            "converged": self.converged,
            "iterations": self.iterations,
            "presence": self.presence,
            "dropped": self.dropped,
            "constant": self.constant,
        }

    @classmethod
    def from_json(cls, blob: dict) -> "RateFit":
        coefficients = blob.get("coefficients") or {}
        return cls(
            names=list(coefficients),
            coefficients=list(coefficients.values()),
            intercept=blob["intercept"],
            n=blob.get("n", 0),
            iterations=blob.get("iterations", 0),
            converged=blob.get("converged", False),
            l2=blob.get("l2", 0.0),
            form=blob.get("form", "poisson"),
            dispersion=blob.get("dispersion", 1.0),
            presence=blob.get("presence") or {},
            dropped=blob.get("dropped") or {},
            constant=blob.get("constant") or {},
        )

    def contributions(self, values: dict):
        """Each factor's push on the LOG RATE, which is where it acts.

        A rate model's contribution is additive in log space exactly as a
        logistic's is in log-odds, so the decomposition reads the same way and
        the "why" sentences need no special case.
        """
        return [(n, values.get(n, 0.0), c * values.get(n, 0.0))
                for n, c in zip(self.names, self.coefficients) if n in values]

    def expected(self, values: dict) -> float:
        """The expected count for one feature vector. Always positive."""
        z = self.intercept
        for name, coef in zip(self.names, self.coefficients):
            z += coef * values.get(name, 0.0)
        # CLAMPED, because exp overflows long before a rate becomes plausible.
        # A passing game has never produced e^30 touchdowns.
        return math.exp(max(-20.0, min(20.0, z)))


def fit_rate(rows: list[dict], counts: list[float], names: list[str],
             *, l2: float = 2.0, form: str = "poisson",
             dispersion: float = 1.0, max_iter: int = 40) -> RateFit:
    """Poisson (or negative-binomial) regression with a log link, by IRLS.

    THE SAME SHAPE AS `logistic.fit`, deliberately: Newton-Raphson with a ridge
    penalty, pure Python, no numpy. A reader who can follow one can follow the
    other, and the coefficients are meant to be read by a human.

    The only real difference is the link. A logistic maps a linear score onto
    (0, 1); this maps it onto (0, inf) through exp, which is what a count needs
    -- the model can say "about 1.4 touchdowns" and the rung probability comes
    from the distribution rather than from a second squashing.

    A NEGATIVE BINOMIAL IS FITTED AS A POISSON with the same mean and a wider
    variance. With the dispersion FIXED at its measured value rather than
    estimated jointly, the mean equation is identical and only the probability
    calculation differs -- which is why one fitter serves both and the form is
    recorded on the result rather than branching here.
    """
    if not rows:
        raise NotFitted("no rows to fit a rate on")

    usable, dropped, constant = [], {}, {}
    for name in names:
        seen = [r[name] for r in rows if name in r]
        if len(seen) < 2:
            dropped[name] = len(seen)
            continue
        if len(set(seen)) == 1:
            constant[name] = len(seen)
            continue
        usable.append(name)

    k = len(usable)
    beta = [0.0] * (k + 1)          # index 0 is the intercept
    design = [[1.0] + [r.get(n, 0.0) for n in usable] for r in rows]
    converged, iterations = False, 0

    for iterations in range(1, max_iter + 1):
        # mu = exp(X beta); for a Poisson the IRLS weight IS mu.
        mu = []
        for row in design:
            z = sum(b * x for b, x in zip(beta, row))
            mu.append(math.exp(max(-20.0, min(20.0, z))))

        grad = [0.0] * (k + 1)
        hess = [[0.0] * (k + 1) for _ in range(k + 1)]
        for row, m, y in zip(design, mu, counts):
            resid = y - m
            for i in range(k + 1):
                grad[i] += resid * row[i]
                for j in range(k + 1):
                    hess[i][j] += m * row[i] * row[j]
        # RIDGE ON EVERYTHING BUT THE INTERCEPT. Penalising the intercept would
        # pull the whole rate toward one per unit, which is a claim about the
        # sport rather than about the factors.
        for i in range(1, k + 1):
            grad[i] -= l2 * beta[i]
            hess[i][i] += l2

        step = _solve(hess, grad)
        if step is None:
            raise NotFitted("the rate model's Hessian was singular")
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-8:
            converged = True
            break

    return RateFit(
        names=usable, coefficients=beta[1:], intercept=beta[0], n=len(rows),
        iterations=iterations, converged=converged, l2=l2, form=form,
        dispersion=dispersion,
        presence={n: sum(1 for r in rows if n in r) for n in usable},
        dropped=dropped, constant=constant)


def _solve(matrix, vector):
    """Gaussian elimination with partial pivoting. None when singular."""
    n = len(vector)
    aug = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col] / aug[col][col]
            for c in range(col, n + 1):
                aug[r][c] -= factor * aug[col][c]
    return [aug[i][n] / aug[i][i] for i in range(n)]


# ---------------------------------------------------------------------------
# from a rate to a probability
# ---------------------------------------------------------------------------

def p_over(rate: float, rung: float, *, form: str = "poisson",
           dispersion: float = 1.0) -> float:
    """P(count > rung), from the distribution rather than from a second fit.

    A rung is always a half-integer in this project, so "more than 1.5" means
    "2 or more" and there is no tie to rule on -- which is exactly why the
    ladders end in .5 and is stated here because the arithmetic below depends
    on it.

    MONOTONE BY CONSTRUCTION: raising the rung can only remove outcomes from
    the over side, so the probability can only fall. A planting checks it.
    """
    if rate is None or rate <= 0:
        return 0.0
    need = math.floor(rung) + 1          # 1.5 -> 2 or more
    if need <= 0:
        return 1.0
    if form == "negative_binomial" and dispersion > 1.0:
        return 1.0 - _nb_cdf(need - 1, rate, dispersion)
    return 1.0 - _poisson_cdf(need - 1, rate)


def _poisson_cdf(k: int, rate: float) -> float:
    """P(X <= k). Summed term by term, which is exact for the k values here."""
    total, term = 0.0, math.exp(-rate)
    for i in range(0, k + 1):
        if i:
            term *= rate / i
        total += term
    return min(1.0, total)


def _nb_cdf(k: int, mean: float, dispersion: float) -> float:
    """P(X <= k) for a negative binomial with this mean and variance ratio.

    Parameterised by the MEASURED variance-to-mean ratio rather than by the
    textbook (r, p), because the ratio is the thing the data reports and the
    conversion belongs here rather than in a comment somewhere:

        var = dispersion * mean,  so  r = mean / (dispersion - 1)
        and p = 1 / dispersion.
    """
    r = mean / (dispersion - 1.0)
    p = 1.0 / dispersion
    total = 0.0
    term = p ** r                        # P(X = 0)
    for i in range(0, k + 1):
        if i:
            term *= (r + i - 1) / i * (1.0 - p)
        total += term
    return min(1.0, total)


def form_for(prop_type: str) -> tuple[str, float]:
    """Which form a market uses, and its dispersion. Declared, not sniffed."""
    form = COUNT_MARKETS.get(prop_type)
    if form is None:
        return "", 1.0
    return form, DISPERSION.get(prop_type, 1.0)


def is_count_market(prop_type: str | None) -> bool:
    return bool(prop_type) and prop_type in COUNT_MARKETS
