"""The factor registry, and the per-sport declarations that populate it.

Importing this package registers every sport's factors. The declarations live
in one module per sport — `registry.py` holds the machinery and NFL's set,
`mlb.py` and `nba.py` hold theirs — so a reader looking for what a sport
believes about itself has one file to open.

The import order matters and is not incidental: `registry` defines the
decorator, then each sport's module runs its declarations against it. A sport
module imports only `.registry`, never the other way round, so there is no
cycle.
"""

from __future__ import annotations

from . import registry  # noqa: F401  (defines the decorator and NFL's factors)


def _register_sport_factors() -> None:
    """Import each sport's declarations for their side effect on the registry."""
    from . import cfb, mlb, nba  # noqa: F401


_register_sport_factors()
