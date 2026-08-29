"""One adapter per sport, and the registry that finds them.

An adapter supplies everything a sport does differently — how a slate is
chosen, how a question is phrased, what a context contains, how an outcome is
read — while the blind loop, the scorecard, the guards and the interface stay
shared. Adding a sport should not mean re-deciding what "blind first" means.

**Each adapter is its own LAW 1 closure.** `gridiron.audit` walks
`gridiron.sports.<sport>` as a separate entrypoint and reports its module count,
so a market import smuggled into baseball is caught by baseball's own scan
rather than hidden in an aggregate that NFL's cleanliness could mask.

Adapters are loaded lazily and by name. Importing this package does not import
every sport, which keeps a sport's dependencies out of the others' closures.
"""

from __future__ import annotations

import importlib
from typing import Protocol

from .. import config


class SportAdapter(Protocol):
    """What every sport must provide. Nothing here may touch market data."""

    SPORT: str

    def slate_questions(self, conn, season, week, *, include_props: bool = True) -> list:
        """The questions for one slate, chosen blind."""

    def build_features(self, conn, question, cache=None):
        """(FeatureVector, context) for one question, from stored data only."""

    def training_set(self, conn, seasons, market, **kwargs):
        """(rows, labels, names) for one market, built by the same rules."""

    def resolve_outcome(self, conn, prediction) -> int:
        """1 if the stated side happened. Raise `Void` when unanswerable."""

    def next_slate(self, conn, season) -> int | None:
        """The next unplayed slate ordinal, or None."""


_LOADED: dict[str, object] = {}


def get(sport: str):
    """The adapter for one sport, imported on first use."""
    if sport not in config.SPORTS:
        raise KeyError(
            f"unknown sport {sport!r}; declared sports are {list(config.SPORTS)}"
        )
    if sport not in _LOADED:
        _LOADED[sport] = importlib.import_module(f"{__name__}.{sport}")
    return _LOADED[sport]


def entrypoints() -> dict[str, str]:
    """Module path per sport, for the per-sport import-closure audit."""
    return {sport: f"{__name__}.{sport}" for sport in config.SPORTS}
