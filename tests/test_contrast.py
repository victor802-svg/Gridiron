"""The LEAN chip reads at 4.5:1 (UI audit finding 21, 2026-09-05): --faint on
a card measured 4.36:1, under the floor a small label needs."""
from __future__ import annotations

import re

from gridiron import config


def _token(css, name):
    m = re.search(r"--%s:\s*(#[0-9A-Fa-f]{6})" % re.escape(name), css)
    assert m, name
    return m.group(1)


def _lum(hex_):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_the_lean_chip_reads_at_four_and_a_half_to_one():
    """The browser measured the LEAN chip at 4.36:1 -- the token itself is
    5.5:1 on a card; the shortfall was an ancestor's opacity on the chip's
    text. --muted is the lighter token, so the chip clears the floor with
    that opacity applied (the phone drive re-measures it in U4)."""
    css = (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")
    card = _token(css, "card")
    faint, muted = _token(css, "faint"), _token(css, "muted")
    assert _lum(muted) > _lum(faint), "--muted is no longer the lighter token; re-check the chip"
    assert _ratio(muted, card) >= 4.5 / 0.85, "with an 85% opacity the chip would fall under 4.5:1"
    rule = re.search(r"\.tier\.lean\s*\{([^}]*)\}", css).group(1)
    assert "var(--muted)" in rule, rule
