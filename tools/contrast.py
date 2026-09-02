"""Measure contrast on the dark theme, and fail anything under WCAG AA.

This exists because of a specific failure. The approved palette uses `--ink`
for the page GROUND; the CSS it replaced used `--ink` for the TEXT. Aliasing one
to the other painted every heading the colour of the page — the matchup and the
probability rendered black on black — and the entire test suite stayed green. It
was caught by looking at a screenshot.

A screenshot is not a check. This is: every foreground token is measured against
every ground it is actually used on, INCLUDING the heading-on-ground pairs that
went invisible, and the worst ratio is reported whether or not it passes.

    python tools/contrast.py

WCAG AA: 4.5:1 for body text, 3.0:1 for large text (>=24px, or >=19px bold).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSS = REPO / "gridiron" / "web" / "style.css"

AA_BODY = 4.5
AA_LARGE = 3.0


def tokens() -> dict[str, str]:
    """Every `--name: #hex` in the token block, resolved one alias deep."""
    text = CSS.read_text(encoding="utf-8")
    block = text[text.index(":root {"): text.index("* { box-sizing")]
    found: dict[str, str] = {}
    for name, value in re.findall(r"--([a-z0-9-]+):\s*([^;]+);", block):
        found[name] = value.strip()
    resolved: dict[str, str] = {}
    for name, value in found.items():
        seen = 0
        while value.startswith("var(--") and seen < 4:
            value = found.get(value[6:-1], value).strip()
            seen += 1
        if value.startswith("#"):
            resolved[name] = value
    return resolved


def rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(value: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


#: What is actually drawn on what, named the way the CSS uses it. The
#: heading-on-ground pairs are FIRST because those are the ones that failed.
PAIRS = [
    # (foreground, background, what it is, large text?)
    ("chrome", "ink", "the matchup heading on the page", True),
    ("chrome", "card", "the matchup heading on a card", True),
    ("chrome", "ink", "the probability on the page", True),
    ("chrome", "card", "the probability on a card", True),
    ("chrome", "resolved", "a heading on a settled card", True),
    ("chrome", "card-2", "a chip value", False),
    ("muted", "ink", "secondary text on the page", False),
    ("muted", "card", "secondary text on a card", False),
    ("muted", "resolved", "a settled card's matchup", False),
    ("muted", "card-2", "a chip label", False),
    ("faint", "ink", "captions and sample sizes on the page", False),
    ("faint", "card", "captions and sample sizes on a card", False),
    ("faint", "resolved", "captions on a settled card", False),
    # RENAMED WITH THE TOKENS (GRIDIRON_16 R2). These were "the accent on the
    # page" and "the selected segment" -- both now chrome, because green is no
    # longer the interactive accent. What is left is the two value colours,
    # measured on every ground a verdict chip actually sits on.
    ("win", "ink", "a pick that won, on the page", False),
    ("win", "card", "a pick that won, on a card", False),
    ("win", "card-2", "a pick that won, on a raised well", False),
    ("loss", "ink", "a pick that lost, on the page", False),
    ("loss", "card", "a pick that lost, on a card", False),
    ("loss", "card-2", "a pick that lost, on a raised well", False),
    ("chrome", "card-2", "the pressed segment and every focus ring", False),
    ("ink", "chrome", "the STRONG tier chip: dark on white", False),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    palette = tokens()
    missing = [n for pair in PAIRS for n in pair[:2] if n not in palette]
    if missing:
        print("tokens not found:", sorted(set(missing)))
        return 2

    print(f"{'pair':<44} {'ratio':>7}  {'needs':>6}  verdict")
    print("-" * 78)
    failures = []
    worst = (999.0, "")
    for fg, bg, what, large in PAIRS:
        r = ratio(palette[fg], palette[bg])
        need = AA_LARGE if large else AA_BODY
        ok = r >= need
        if r < worst[0]:
            worst = (r, f"{fg} on {bg} ({what})")
        if not ok:
            failures.append(f"{fg} on {bg} — {what}: {r:.2f} < {need}")
        print(f"{what:<44} {r:>6.2f}:1  {need:>5.1f}  {'ok' if ok else 'FAILS AA'}")

    print()
    print(f"worst pair: {worst[1]} at {worst[0]:.2f}:1")
    if failures:
        print()
        print("BELOW WCAG AA:")
        for f in failures:
            print("  " + f)
        return 1
    print("every pair meets WCAG AA for its size.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
