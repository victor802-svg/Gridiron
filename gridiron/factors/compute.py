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


class WeatherNotRead(MissingDataDefaulted):
    """A weather factor carried a value on a row whose weather was not read
    outdoors -- an indoor game, or no reading at all (operator ruling 4,
    2026-09-24)."""


#: WHAT A FIT TRAINED UNDER THIS RULE SAYS ABOUT ITS WEATHER ROWS
#: (2026-09-24). `baseline.train` stores it in the fit's blob as
#: `indoor_weather`; a fit without it was trained while indoor games were
#: filled, and its weather counts include those domes.
INDOOR_WEATHER = "absent"

#: The bases on which a context's weather counts as READ: a forecast fetched
#: before kickoff, or the observation the source published after it. Anything
#: else -- 'indoors', 'none', an unknown roof -- is a reason there is no value.
WEATHER_READ = ("forecast", "observed")


def assert_weather_was_read(ctx, fv: "FeatureVector") -> None:
    """A weather factor carries a value only if the weather was read, outdoors.

    THE ONE DOOR (operator ruling 4, 2026-09-24: "precipitation, wind and cold
    all follow the same rule. An indoor game carries no value"; and the fs5
    brief: "a training row with no weather can't carry a precipitation
    value"). Runs inside `feature_vector`, which every training row and every
    forecast of every sport goes through, so a fill reintroduced anywhere --
    in a factor, in the context, in a loader -- fails here, by name, on the
    first row it touches.

    WHY IT EXISTS. Until that day a dome read wind 0, cold 0 and rain 0: 760
    of the NFL spread's 2,632 training rows said the weather was measured for
    games it never reached, and precipitation's only values in the whole
    training set were those domes. `assert_missing_is_explicit` could not see
    it -- the values were not listed absent, they were simply made up.

    Which factors are weather is declared on the factor (`Factor.weather`,
    the context reading it is computed from), not listed here.
    """
    for name, value in fv.values.items():
        declared = registry.REGISTRY.get(name)
        reading = declared.weather if declared is not None else None
        if reading is None:
            continue
        where = f"{fv.sport} {fv.market_type} {getattr(ctx, 'game_id', '?')}"
        if getattr(ctx, "indoors", None):
            raise WeatherNotRead(
                f"WEATHER ON AN INDOOR GAME: {name!r} = {value!r} for {where}, "
                f"which is played indoors. An indoor game carries no value for "
                f"the wind, the cold or the rain (operator ruling 4, "
                f"2026-09-24): no weather reaches it, and a 0.0 there reads "
                f"as a calm, mild, dry afternoon nobody measured.")
        basis = getattr(ctx, "weather_basis", None)
        if basis not in WEATHER_READ or getattr(ctx, reading, None) is None:
            raise WeatherNotRead(
                f"WEATHER THAT WAS NEVER READ: {name!r} = {value!r} for "
                f"{where}, whose {reading} reading is "
                f"{getattr(ctx, reading, None)!r} on a {basis!r} basis. A row "
                f"with no weather reading carries no weather value -- absent, "
                f"never filled (the fs5 brief, 2026-09-24).")


def weather_absent_reason(ctx) -> str | None:
    """Why a weather factor is absent, in words, or None to say nothing extra."""
    if getattr(ctx, "indoors", None):
        return "played indoors: no weather reaches the game"
    basis = getattr(ctx, "weather_basis", None)
    if basis == "unknown roof":
        return "the roof is not known to be open, so no weather is read"
    if basis not in WEATHER_READ:
        return "no weather reading for this game"
    return None


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
    #: (e.g. weather: forecast / observed).
    sources: dict[str, str] = field(default_factory=dict)
    #: WHY AN ABSENT FACTOR IS ABSENT, where the vector knows (2026-09-24):
    #: an indoor game's weather is absent because no weather reaches it, which
    #: is a different fact from a forecast nobody fetched.
    absent_reasons: dict[str, str] = field(default_factory=dict)

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
    assert_weather_was_read(ctx, fv)

    # WHICH FACTORS ARE WEATHER IS READ OFF THE REGISTRY (2026-09-24), where
    # it is declared, rather than a list of three NFL names kept here.
    basis = getattr(ctx, "weather_basis", None)
    why_absent = weather_absent_reason(ctx)
    for name in list(fv.values) + fv.absent:
        if registry.REGISTRY[name].weather is None:
            continue
        if name in fv.values and basis:
            fv.sources[name] = basis
        elif name not in fv.values and why_absent and name not in fv.failed:
            fv.absent_reasons[name] = why_absent
    return fv


def factor_value_words(why: str | None, value, reads=None, unit=None,
                       unit_scale: float = 1.0,
                       unit_offset: float = 0.0) -> str:
    """One factor, as a line a model and a person both read the same way.

    THE PROMPT USED TO HAND OVER BARE ENCODED NUMBERS. Twenty-seven of 103
    factors are an indicator, a scaled quantity or a difference, so the model
    was told `= 0` and wrote "(a three-round bout, = 0)" -- correct, and it
    reads to a person as zero rounds.

    THREE SHAPES, IN ORDER OF HOW MUCH IS DECLARED:

    * AN INDICATOR BECOMES ITS PHRASE AND NOTHING ELSE. "a three-round bout"
      carries the whole fact, and appending "= 0" to it would put back exactly
      what this is for.
    * A QUANTITY BECOMES ITS REAL UNITS. `ufc_age_gap` at 0.78 is "the age
      difference between the two fighters = 7.8 years", not "= 0.78".
    * ANYTHING ELSE KEEPS ITS NUMBER, which is the honest fallback for a
      factor whose author has not said how it reads. A guessed unit is worse
      than a bare number: one is uninformative and the other is wrong.

    THE SAME DOOR AS THE CARD. `why` is the declared WHY phrase that
    `why_sentences` composes with, so the model is told what a reader is told.
    """
    label = (why or "").strip()
    if value is None:
        return label
    if reads:
        for level, phrase in reads.items():
            if abs(float(value) - float(level)) < 1e-9:
                return (phrase or "").strip() or label
    if unit:
        shown = float(value) * float(unit_scale) + float(unit_offset)
        return f"{label} = {shown:.4g} {unit}".strip()
    return f"{label} = {float(value):g}".strip()


def describe(fv: FeatureVector, coefficients: dict[str, float] | None = None) -> list[dict]:
    """Per-factor rows for display, largest absolute effect first.

    Absent factors are listed too, with a null value — the reader is told what
    the model could not see, which is part of reading a forecast honestly.
    """
    out = []
    for name, value in fv.values.items():
        entry = {
            "factor": name,
            # THE PLAIN NAME TRAVELS WITH THE CODE NAME (2026-09-05). Every
            # declared factor has a `why` phrase -- measured, 103 of 103 -- so
            # anything rendering a factor to a person can use one. The code
            # name stays for the things that key on it.
            "why": registry.REGISTRY[name].why,
            # HOW THE VALUE READS, carried so the prompt can say "a
            # three-round bout" rather than "= 0" (2026-09-05).
            "reads": registry.REGISTRY[name].reads,
            "unit": registry.REGISTRY[name].unit,
            "unit_scale": registry.REGISTRY[name].unit_scale,
            "unit_offset": registry.REGISTRY[name].unit_offset,
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
            "why": registry.REGISTRY[name].why,
            "value": None,
            "present": False,
            "contribution": None,
            "rationale": registry.REGISTRY[name].rationale
            if name in registry.REGISTRY else "",
            "why_absent": absent_reason(fv, name),
        })
    return out


def absent_reason(fv: FeatureVector, name: str) -> str:
    """Why one absent factor is absent: the error if it failed, the reason the
    vector recorded if it has one, else the plain default. ONE DOOR, read by
    `describe` and by the statistical forecast's stored `absent_detail`."""
    return (fv.failed.get(name) or fv.absent_reasons.get(name)
            or "not measurable for this game")
