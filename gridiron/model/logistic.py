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
    """A fitted model. `names` and `coefficients` line up; `intercept` is apart."""

    names: list[str]
    coefficients: list[float]
    intercept: float
    n: int
    iterations: int
    converged: bool
    l2: float

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
        )

    def log_odds(self, row: dict[str, float]) -> float:
        z = self.intercept
        for name, coef in zip(self.names, self.coefficients):
            z += coef * row.get(name, 0.0)
        return z

    def predict(self, row: dict[str, float]) -> float:
        return sigmoid(self.log_odds(row))

    def contributions(self, row: dict[str, float]) -> list[tuple[str, float, float]]:
        """(factor, value, contribution to the log-odds), biggest effect first.

        This is the explanation. Summing the contributions and the intercept
        gives back the log-odds exactly.
        """
        out = [
            (name, row.get(name, 0.0), coef * row.get(name, 0.0))
            for name, coef in zip(self.names, self.coefficients)
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
) -> Fit:
    """Fit by iteratively reweighted least squares.

    Each step solves (X'WX + lambda*I) delta = X'(y - p) - lambda*beta, which is
    the Newton step for the penalised log-likelihood. It converges in a handful
    of iterations on data this size and does not need a learning rate.
    """
    if len(rows) != len(labels):
        raise ValueError("rows and labels differ in length")
    if not rows:
        raise ValueError("cannot fit a model on no data")

    p = len(names) + 1  # +1 for the intercept, which sits at index 0
    design = [[1.0] + [float(r.get(name, 0.0)) for name in names] for r in rows]
    beta = [0.0] * p
    converged = False
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        hessian = [[0.0] * p for _ in range(p)]
        gradient = [0.0] * p

        for x, y in zip(design, labels):
            z = sum(b * xi for b, xi in zip(beta, x))
            pr = sigmoid(z)
            # Floor the weight so a saturated row cannot zero out the Hessian.
            w = max(pr * (1.0 - pr), 1e-6)
            residual = y - pr
            for i in range(p):
                if x[i] == 0.0:
                    continue
                gradient[i] += residual * x[i]
                wx = w * x[i]
                for j in range(i, p):
                    hessian[i][j] += wx * x[j]

        for i in range(p):
            for j in range(i):
                hessian[i][j] = hessian[j][i]

        # Penalise every coefficient except the intercept.
        for i in range(1, p):
            hessian[i][i] += l2
            gradient[i] -= l2 * beta[i]

        step = _solve(hessian, gradient)
        beta = [b + s for b, s in zip(beta, step)]

        if max(abs(s) for s in step) < tol:
            converged = True
            break

    return Fit(
        names=list(names),
        coefficients=beta[1:],
        intercept=beta[0],
        n=len(rows),
        iterations=iteration,
        converged=converged,
        l2=l2,
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
