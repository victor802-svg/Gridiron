"""Turn a context into the feature vector the model sees.

**Missing is an explicit state (v2).** A factor that cannot be measured for a
game is *excluded from that game's vector*. It does not become a default, and
it is never silently indistinguishable from a real measurement that happened to
be zero. The prediction row records which factors were actually PRESENT and
which were ABSENT, and both lists are permanent.

Before v2 an unmeasurable factor was substituted with its declared default —
usually 0.0 — and merely noted. That is how `precipitation`, unmeasurable in
66% of games, came to be fitted as if two thirds of the league's history were
played in confirmed dry weather.

One thing this does not do, stated here because the temptation to overclaim is
strong: for a linear model, excluding a term and imputing zero produce the same
coefficients. The gain is in the record, in what gets scored, and in what an
explanation is allowed to say — not in the arithmetic of the fit. See
`logistic.fit` and `tests/test_missingness.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import registry


class MissingDataDefaulted(AssertionError):
    """An unmeasurable factor was given a value instead of being excluded.

    This lives here rather than in `gridiron.audit` for a structural reason:
    `feature_vector` is on the prediction path, and importing the audit module
    would drag its list of forbidden market identifiers into the closure that
    the LAW 1 scan walks. The guard would then flag itself.
    """


def assert_missing_is_explicit(fv: "FeatureVector") -> None:
    """A factor is measured or absent. Never both, never absent with a value.

    Runs on every feature vector, so a fallback reintroduced anywhere between a
    factor function and the model is caught at the moment it produces its first
    silent zero, not a season later when a coefficient looks strange.
    """
    overlap = set(fv.values) & set(fv.absent)
    if overlap:
        raise MissingDataDefaulted(
            f"GRIDIRON v2: {sorted(overlap)} are recorded as absent AND carry a "
            "value. An unmeasurable factor is excluded from the vector; it does "
            "not get a stand-in value and a note saying it was defaulted. That "
            "is how precipitation came to be fitted as confirmed dry weather in "
            "two thirds of the league's history."
        )
    for name in fv.absent:
        if fv.raw.get(name) is not None:
            raise MissingDataDefaulted(
                f"GRIDIRON v2: {name!r} is listed absent but its raw value is "
                f"{fv.raw[name]!r}."
            )


@dataclass
class FeatureVector:
    sport: str
    market_type: str
    #: Only the factors that could actually be measured for this game.
    values: dict[str, float] = field(default_factory=dict)
    raw: dict[str, float | None] = field(default_factory=dict)
    #: Declared, active, applicable — and not measurable here.
    absent: list[str] = field(default_factory=list)
    #: Absent because the factor function raised. Kept apart from ordinary
    #: unavailability: one is the world being quiet, the other is a bug.
    failed: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    #: Where each measured value came from, when that is not obvious
    #: (e.g. weather: forecast / observed / indoors).
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def names(self) -> list[str]:
        return list(self.values)

    @property
    def present(self) -> list[str]:
        return list(self.values)

    @property
    def coverage(self) -> float:
        total = len(self.values) + len(self.absent)
        return len(self.values) / total if total else 0.0

    def to_json_dict(self) -> dict:
        return {
            "sport": self.sport,
            "market_type": self.market_type,
            "values": {k: round(v, 6) for k, v in self.values.items()},
            "present": self.present,
            "absent": self.absent,
            "failed": self.failed,
            "notes": self.notes,
            "sources": self.sources,
            "coverage": round(self.coverage, 4),
        }


def absent_factors(payload: dict) -> list[str]:
    """Read the absent list off a stored prediction of either factor set.

    v1 rows wrote `missing`; v2 rows write `absent`. Both are permanent records
    and both must stay readable, so the reader knows about both rather than the
    writer pretending v1 never happened.
    """
    return list(payload.get("absent") or payload.get("missing") or [])


class SportNotOnContext(AssertionError):
    """A context reached the factor loop without saying which sport it is."""


def feature_vector(ctx, market_type: str, market: str | None = None) -> FeatureVector:
    sport = getattr(ctx, "sport", None)
    if not sport:
        raise SportNotOnContext(
            "LAW 6: this context carries no sport, so there is no way to know "
            "whose factors apply. A context without a sport cannot produce a "
            "feature vector — that is how one sport's factors would end up in "
            "another sport's model."
        )
    fv = FeatureVector(
        sport=sport, market_type=market_type, notes=list(getattr(ctx, "notes", []))
    )
    for f in registry.active_factors(sport, market_type, market):
        try:
            value = f.fn(ctx)
        except Exception as exc:  # noqa: BLE001 - a broken factor must not kill the slate
            fv.failed[f.name] = f"{type(exc).__name__}: {exc}"
            fv.raw[f.name] = None
            fv.absent.append(f.name)
            continue
        fv.raw[f.name] = value
        if value is None:
            fv.absent.append(f.name)
        else:
            fv.values[f.name] = float(value)

    assert_missing_is_explicit(fv)

    basis = getattr(ctx, "weather_basis", None)
    if basis:
        for name in ("wind", "cold", "precipitation"):
            if name in fv.values:
                fv.sources[name] = basis
    return fv


def describe(fv: FeatureVector, coefficients: dict[str, float] | None = None) -> list[dict]:
    """Per-factor rows for display, largest absolute effect first.

    Absent factors are listed too, with a null value — the reader is told what
    the model could not see, which is part of reading a forecast honestly.
    """
    out = []
    for name, value in fv.values.items():
        entry = {
            "factor": name,
            "value": round(value, 4),
            "present": True,
            "rationale": registry.REGISTRY[name].rationale,
        }
        if name in fv.sources:
            entry["source"] = fv.sources[name]
        if coefficients is not None and name in coefficients:
            entry["coefficient"] = round(coefficients[name], 4)
            entry["contribution"] = round(coefficients[name] * value, 4)
        out.append(entry)

    if coefficients is not None:
        out.sort(key=lambda e: abs(e.get("contribution", 0.0)), reverse=True)

    for name in fv.absent:
        out.append({
            "factor": name,
            "value": None,
            "present": False,
            "contribution": None,
            "rationale": registry.REGISTRY[name].rationale
            if name in registry.REGISTRY else "",
            "why_absent": fv.failed.get(name, "not measurable for this game"),
        })
    return out
