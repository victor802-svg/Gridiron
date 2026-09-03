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


#: WHAT EVERY SPORT ADAPTER MUST PROVIDE, checked when the module is imported.
#:
#: `markets` is on this list because its absence cost the project a guard.
#: `run.already_answered` has called `sports.get(sport).markets()` since ruling
#: R4 was written on 2026-09-02, and NEITHER the NBA nor the college football
#: adapter defined it -- so the duplicate-slate guard raised AttributeError
#: before it could refuse anything, for two sports out of four, for a day.
#:
#: IT FAILED AT FIRST USE, WHICH IS THE WRONG TIME. First use of that path is
#: a scheduled predict run at 09:00, where an AttributeError is a task-runs row
#: nobody reads until they go looking. A missing method is a fact about the
#: module, knowable the moment it is imported, and this is where it is now
#: known.
REQUIRED_ADAPTER_NAMES: tuple[str, ...] = (
    "SPORT",
    "markets",
    "slate_questions",
    "next_slate",
    "resolve_outcome",
    "training_set",
)


class AdapterIncomplete(RuntimeError):
    """A sport adapter is missing part of the interface every sport needs."""


def _check_adapter(sport: str, module) -> None:
    """Refuse an adapter that cannot do what every caller assumes it can."""
    missing = [name for name in REQUIRED_ADAPTER_NAMES
               if not hasattr(module, name)]
    if missing:
        raise AdapterIncomplete(
            f"the {sport!r} adapter ({module.__name__}) is missing "
            f"{', '.join(missing)}. Every sport adapter provides "
            f"{', '.join(REQUIRED_ADAPTER_NAMES)}; a caller that reaches for "
            f"one of them cannot know which sports happen to have it. "
            f"`markets` was absent from two adapters for a day and took the "
            f"duplicate-slate guard down with it, silently, because nothing "
            f"looked until the guard ran."
        )


def get(sport: str):
    """The adapter for one sport, imported on first use and checked then."""
    if sport not in config.SPORTS:
        raise KeyError(
            f"unknown sport {sport!r}; declared sports are {list(config.SPORTS)}"
        )
    if sport not in _LOADED:
        module = importlib.import_module(f"{__name__}.{sport}")
        _check_adapter(sport, module)
        _LOADED[sport] = module
    return _LOADED[sport]


def entrypoints() -> dict[str, str]:
    """Module path per sport, for the per-sport import-closure audit."""
    return {sport: f"{__name__}.{sport}" for sport in config.SPORTS}
