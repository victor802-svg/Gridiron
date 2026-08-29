"""Turn a context into the feature vector the model sees.

The only interesting decision here is what to do with a factor that returns
`None`. We substitute the factor's declared `default` and record the name in
`missing`, which is stored on the prediction. So a forecast made without a
weather forecast says so on its own record, forever, instead of looking
identical to one made in a dome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import registry


@dataclass
class FeatureVector:
    market_type: str
    values: dict[str, float] = field(default_factory=dict)
    raw: dict[str, float | None] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return list(self.values)

    def to_json_dict(self) -> dict:
        return {
            "market_type": self.market_type,
            "values": {k: round(v, 6) for k, v in self.values.items()},
            "missing": self.missing,
            "failed": self.failed,
            "notes": self.notes,
        }


def feature_vector(ctx, market_type: str) -> FeatureVector:
    fv = FeatureVector(market_type=market_type, notes=list(getattr(ctx, "notes", [])))
    for f in registry.active_factors(market_type):
        try:
            value = f.fn(ctx)
        except Exception as exc:  # noqa: BLE001 - a broken factor must not kill the slate
            fv.failed[f.name] = f"{type(exc).__name__}: {exc}"
            value = None
        fv.raw[f.name] = value
        if value is None:
            fv.values[f.name] = f.default
            fv.missing.append(f.name)
        else:
            fv.values[f.name] = float(value)
    return fv


def describe(fv: FeatureVector, coefficients: dict[str, float] | None = None) -> list[dict]:
    """Per-factor contributions, largest absolute effect first.

    With coefficients this is the actual decomposition of the log-odds, which is
    what makes the statistical model explainable: every prediction can be read
    back as a list of "this pushed it this far, in this direction".
    """
    out = []
    for name, value in fv.values.items():
        entry = {
            "factor": name,
            "value": round(value, 4),
            "missing": name in fv.missing,
            "rationale": registry.REGISTRY[name].rationale,
        }
        if coefficients is not None and name in coefficients:
            entry["coefficient"] = round(coefficients[name], 4)
            entry["contribution"] = round(coefficients[name] * value, 4)
        out.append(entry)
    if coefficients is not None:
        out.sort(key=lambda e: abs(e.get("contribution", 0.0)), reverse=True)
    return out
