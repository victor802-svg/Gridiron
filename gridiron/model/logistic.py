"""Logistic regression, in pure Python, fitted by Newton-Raphson.

No numpy, no sklearn — deliberately. CLAUDE.md: a probability you cannot
interrogate cannot be debugged when it is wrong. The whole method is on this
page: build the weighted normal equations, solve them, repeat until the step
stops moving. When a forecast looks wrong you can read the coefficients, read
the feature values, multiply them together, and see exactly where the number
came from.

Ridge (L2) regularisation is on by default and the intercept is never
penalised. With twenty-odd correlated football factors and a few thousand
games, an unregularised fit will happily hand a large coefficient to a factor
that saw one strange season.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Fit:
    """A fitted model. `names` and `coefficients` line up; `intercept` is apart.

    `presence` records how many training rows actually carried each factor.
    A factor measured on 200 of 2,600 games has a coefficient estimated from
    200 games, and the interface says so rather than presenting it as if it
    were fitted on everything (LAW 4 applied to the model itself).

    `dropped` names factors excluded from the fit for having too few measured
    rows to estimate at all.
    """

    names: list[str]
    coefficients: list[float]
    intercept: float
    n: int
    iterations: int
    converged: bool
    l2: float
    presence: dict[str, int] = None       # factor -> rows where it was measured
    dropped: dict[str, int] = None        # factor -> rows measured (below floor)
    constant: dict[str, int] = None       # factor -> rows measured, all one value

    def __post_init__(self) -> None:
        if self.presence is None:
            self.presence = {name: self.n for name in self.names}
        if self.dropped is None:
            self.dropped = {}
        if self.constant is None:
            self.constant = {}

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.names, self.coefficients))

    def to_json(self) -> dict:
        return {
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
    def from_json(cls, blob: dict) -> "Fit":
        names = list(blob["coefficients"])
        return cls(
            names=names,
            coefficients=[blob["coefficients"][n] for n in names],
            intercept=blob["intercept"],
            n=blob.get("n", 0),
            iterations=blob.get("iterations", 0),
            converged=blob.get("converged", True),
            l2=blob.get("l2", 1.0),
            presence=blob.get("presence"),
            dropped=blob.get("dropped") or {},
            constant=blob.get("constant") or {},
        )

    def log_odds(self, row: dict[str, float]) -> float:
        """Sum over the factors this row actually carries.

        A factor absent from `row` contributes nothing. That is not the same
        claim as "its value was zero": it is "this game says nothing about this
        term, so leave the estimate at its reference level". Because every
        factor is centred on a meaningful baseline (wind on 10mph, cold on 55F,
        the differentials on parity), the reference level reads as "typical",
        which is the honest thing to assume about something unmeasured.
        """
        z = self.intercept
        for name, coef in zip(self.names, self.coefficients):
            value = row.get(name)
            if value is None:
                continue
            z += coef * value
        return z

    def predict(self, row: dict[str, float]) -> float:
        return sigmoid(self.log_odds(row))

    def contributions(self, row: dict[str, float]) -> list[tuple[str, float, float]]:
        """(factor, value, contribution to the log-odds), biggest effect first.

        This is the explanation. Summing the contributions and the intercept
        gives back the log-odds exactly.
        """
        out = [
            (name, row[name], coef * row[name])
            for name, coef in zip(self.names, self.coefficients)
            if row.get(name) is not None
        ]
        out.sort(key=lambda t: abs(t[2]), reverse=True)
        return out


def sigmoid(z: float) -> float:
    # Split by sign to keep exp() from overflowing on a confident prediction.
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting. Small and square by
    construction — one row per factor plus the intercept."""
    n = len(rhs)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ArithmeticError(
                f"singular normal equations at column {col}; two factors are "
                "probably identical or one is constant across the whole sample"
            )
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pivot_value = aug[col][col]
        for row in range(col + 1, n):
            factor = aug[row][col] / pivot_value
            if factor == 0.0:
                continue
            for k in range(col, n + 1):
                aug[row][k] -= factor * aug[col][k]

    solution = [0.0] * n
    for row in range(n - 1, -1, -1):
        total = aug[row][n] - sum(aug[row][k] * solution[k] for k in range(row + 1, n))
        solution[row] = total / aug[row][row]
    return solution


def fit(
    rows: list[dict[str, float]],
    labels: list[int],
    names: list[str],
    *,
    l2: float = 1.0,
    max_iterations: int = 40,
    tol: float = 1e-7,
    min_rows_per_factor: int = 50,
) -> Fit:
    """Fit by iteratively reweighted least squares, with explicit missingness.

    Each step solves (X'WX + lambda*I) delta = X'(y - p) - lambda*beta, the
    Newton step for the penalised log-likelihood. It converges in a handful of
    iterations on data this size and needs no learning rate.

    **A factor absent from a row is excluded from that row entirely** — from the
    linear predictor, from the gradient, and from every Hessian entry it would
    touch.

    An honest caveat, because it would be easy to oversell this. For a LINEAR
    model, excluding a term is arithmetically identical to imputing zero: a row
    with x_i = 0 contributes `residual * 0` to gradient[i] and `w * 0 * x_j` to
    hessian[i][j], which is to say nothing, exactly as an excluded term does.
    `tests/test_missingness.py` pins that equivalence to the fourth decimal so
    nobody later mistakes this for a change in the fitted coefficients.

    What exclusion actually buys is downstream of the fit, and it is not small:

      * A prediction's explanation no longer lists `precipitation = 0.0` for a
        game where the rain was never measured, in the same shape it uses for a
        game that was measured and dry. The two were previously indistinguishable
        on the record, forever.
      * `presence` records how many rows carried each factor, so a coefficient
        estimated from 186 measured games is not presented as one fitted on 544.
      * The factor scorecard now scores a factor only over the predictions where
        it was actually measured, rather than over a majority of games in which
        it was a placeholder.

    The substantive repair for `precipitation` is not here. It is fetching the
    forecast so the factor has a value at all.

    A factor measured on fewer than `min_rows_per_factor` rows is dropped from
    the fit rather than estimated from a sample too thin to estimate from, and
    the count is recorded on the Fit.
    """
    if len(rows) != len(labels):
        raise ValueError("rows and labels differ in length")
    if not rows:
        raise ValueError("cannot fit a model on no data")

    presence = {name: sum(1 for r in rows if r.get(name) is not None) for name in names}
    dropped = {n: c for n, c in presence.items() if c < min_rows_per_factor}

    # A factor measured only where it takes one value carries no information and
    # cannot be fitted, but it WOULD be reported with a coefficient of 0.0 and
    # look like a tested idea. `precipitation` is exactly this: measurable only
    # indoors, where it is always zero. Drop it and name it, so the interface can
    # say "never varied in the training window" instead of "no effect".
    constant: dict[str, int] = {}
    for name in names:
        if name in dropped:
            continue
        values = {r[name] for r in rows if r.get(name) is not None}
        if len(values) <= 1:
            constant[name] = presence[name]

    kept = [n for n in names if n not in dropped and n not in constant]
    if not kept:
        raise ValueError(
            "no factor survived: every one was measured on fewer than "
            f"{min_rows_per_factor} rows, or never varied where it was measured. "
            "There is nothing to fit."
        )

    p = len(kept) + 1  # +1 for the intercept, which sits at index 0 and is always present

    # Per row: the values it carries, and the indices those occupy. Building the
    # index list once keeps the inner loops over present terms only.
    design: list[tuple[list[int], list[float]]] = []
    for r in rows:
        indices = [0]
        values = [1.0]
        for i, name in enumerate(kept, start=1):
            value = r.get(name)
            if value is not None:
                indices.append(i)
                values.append(float(value))
        design.append((indices, values))

    beta = [0.0] * p
    converged = False
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        hessian = [[0.0] * p for _ in range(p)]
        gradient = [0.0] * p

        for (indices, values), y in zip(design, labels):
            z = sum(beta[i] * v for i, v in zip(indices, values))
            pr = sigmoid(z)
            # Floor the weight so a saturated row cannot zero out the Hessian.
            w = max(pr * (1.0 - pr), 1e-6)
            residual = y - pr
            for a, i in enumerate(indices):
                xi = values[a]
                if xi == 0.0:
                    # Pure optimisation, and exact: a measured zero contributes
                    # nothing to its own normal equations. This line is also why
                    # exclusion and zero-imputation coincide here.
                    continue
                gradient[i] += residual * xi
                wxi = w * xi
                for b in range(a, len(indices)):
                    hessian[i][indices[b]] += wxi * values[b]

        for i in range(p):
            for j in range(i):
                hessian[i][j] = hessian[j][i]

        # Penalise every coefficient except the intercept. This also keeps the
        # normal equations non-singular for a factor present on few rows.
        for i in range(1, p):
            hessian[i][i] += l2
            gradient[i] -= l2 * beta[i]

        step = _solve(hessian, gradient)
        beta = [b + s for b, s in zip(beta, step)]

        if max(abs(s) for s in step) < tol:
            converged = True
            break

    return Fit(
        names=list(kept),
        coefficients=beta[1:],
        intercept=beta[0],
        n=len(rows),
        iterations=iteration,
        converged=converged,
        l2=l2,
        presence={n: presence[n] for n in kept},
        dropped=dropped,
        constant=constant,
    )


# --- scoring ---------------------------------------------------------------

def brier(probs: list[float], outcomes: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


def log_loss(probs: list[float], outcomes: list[int], eps: float = 1e-12) -> float:
    total = 0.0
    for p, y in zip(probs, outcomes):
        p = min(max(p, eps), 1.0 - eps)
        total += -(y * math.log(p) + (1 - y) * math.log(1.0 - p))
    return total / len(probs)
