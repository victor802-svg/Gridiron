"""The blind window — LAW 1, enforced at runtime.

The static guard (`tests/test_guards.py`) proves that the prediction package's
whole import closure never references `gridiron.market`. This is the runtime
companion: while predictions are being computed and written, the market module
is not merely unused, it is *not loaded at all*, and any attempt to load it
raises.

That means the orchestrator must import the market module lazily, after the
window closes. Which is the point: the ordering the law describes becomes
something the interpreter enforces rather than something a future edit can
quietly reorder.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager

MARKET_PACKAGE = "gridiron.market"


class MarketAccessDuringBlindWindow(RuntimeError):
    """Something tried to reach market data while a prediction was being made."""


class _Sentinel:
    """A meta-path finder that refuses one package."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == MARKET_PACKAGE or fullname.startswith(MARKET_PACKAGE + "."):
            raise MarketAccessDuringBlindWindow(
                f"GRIDIRON LAW 1: {fullname!r} was imported inside the blind "
                "window. The model's probability must be computed and written "
                "before any line is fetched. Move the market call after the "
                "window closes."
            )
        return None


@contextmanager
def blind_window():
    if MARKET_PACKAGE in sys.modules:
        raise MarketAccessDuringBlindWindow(
            f"GRIDIRON LAW 1: {MARKET_PACKAGE!r} is already imported as the blind "
            "window opens, so a line is reachable from this process while the "
            "prediction is being formed. Import it lazily, after prediction "
            "rows are written."
        )
    sentinel = _Sentinel()
    sys.meta_path.insert(0, sentinel)
    try:
        yield
    finally:
        try:
            sys.meta_path.remove(sentinel)
        except ValueError:  # pragma: no cover - only if someone else cleared it
            pass


def forget_market_module() -> None:
    """Drop the market package from `sys.modules`.

    Only for a process that has already snapshotted one week and now wants to
    predict another — the second blind window has to open clean. Tests use it
    too, since importing the market module in one test would otherwise poison
    every later blind window in the same session.
    """
    for name in [n for n in sys.modules if n == MARKET_PACKAGE or n.startswith(MARKET_PACKAGE + ".")]:
        del sys.modules[name]
