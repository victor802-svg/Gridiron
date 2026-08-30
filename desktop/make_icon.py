"""Draw the Gridiron icon in code, at 16, 32, 48 and 256.

No downloaded artwork and no imaging library. PNG is zlib plus four chunks and
ICO is a header plus those PNGs, both of which the standard library can do — and
the alternative was adding Pillow to a project whose logistic regression is
hand-written specifically to avoid depending on a numeric stack. A repository
should hold the source of everything it ships; a binary nobody can diff is a
thing nobody can check.

THE MARK: a dark card with a probability dumbbell across it — two dots joined by
a rail, which is exactly the shape the app uses on every card to show the model
and the market disagreeing. At 256 the two dots are clearly different colours;
at 16 it reads as a small dark tile with a bright bar, which is enough to find
in a taskbar.

    python desktop/make_icon.py
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent / "gridiron.ico"
SIZES = (16, 32, 48, 256)

# The app's own palette, so the icon and the interface are the same object.
# Kept in step with the approved palette in gridiron/web/style.css. An icon
# that is the app's old colours is a small daily lie about what will open.
CARD = (0x0A, 0x0F, 0x0C, 255)      # --ink: the page ground
RAIL = (0x1F, 0x2B, 0x1E, 255)      # --line: the hairline
MODEL = (0x00, 0xDC, 0x82, 255)     # --green: the model's dot
MARKET = (0x8A, 0xA0, 0x8C, 255)    # --muted: the market's dot
CLEAR = (0, 0, 0, 0)


def _blend(under: tuple, over: tuple, alpha: float) -> tuple:
    """Coverage blending, so edges are not staircases at 16px."""
    a = max(0.0, min(1.0, alpha))
    return tuple(round(under[i] * (1 - a) + over[i] * a) for i in range(4))


def draw(size: int) -> list[list[tuple]]:
    """One frame, supersampled 3x for antialiasing.

    Everything is drawn in fractions of `size` rather than pixel constants, so
    the same code produces a 16 and a 256 that are recognisably the same mark.
    """
    ss = 3
    big = size * ss
    px = [[CLEAR for _ in range(big)] for _ in range(big)]

    radius = big * 0.22
    for y in range(big):
        for x in range(big):
            # Rounded card. Distance to the rounded-rect edge, in pixels.
            dx = max(radius - x, 0, x - (big - 1 - radius))
            dy = max(radius - y, 0, y - (big - 1 - radius))
            outside = (dx * dx + dy * dy) ** 0.5 - radius
            if outside < 0.5:
                px[y][x] = CARD

    cy = big // 2
    left, right = big * 0.26, big * 0.74
    rail_h = max(big * 0.045, 1.0)

    # The rail.
    for y in range(big):
        for x in range(big):
            if left <= x <= right and abs(y - cy) <= rail_h / 2:
                px[y][x] = RAIL

    # The two dots. The market sits left, the model right and larger: the model
    # is the thing this app produces, and the icon should say so.
    dot = big * 0.115
    for cx, colour, scale in ((left, MARKET, 0.85), (right, MODEL, 1.0)):
        r = dot * scale
        for y in range(int(cy - r - 2), int(cy + r + 3)):
            for x in range(int(cx - r - 2), int(cx + r + 3)):
                if 0 <= x < big and 0 <= y < big:
                    d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                    if d <= r + 0.5:
                        px[y][x] = _blend(px[y][x], colour, min(1.0, r + 0.5 - d))

    # Downsample the supersampled frame.
    out = [[CLEAR for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(ss):
                for sx in range(ss):
                    p = px[y * ss + sy][x * ss + sx]
                    for i in range(4):
                        acc[i] += p[i]
            out[y][x] = tuple(round(v / (ss * ss)) for v in acc)
    return out


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def to_png(frame: list[list[tuple]]) -> bytes:
    """A minimal RGBA PNG: signature, IHDR, IDAT, IEND.

    Filter byte 0 on every scanline. Filtering would shrink the file; the
    largest icon here is a few kilobytes and unfiltered data is data a person
    can follow.
    """
    size = len(frame)
    raw = bytearray()
    for row in frame:
        raw.append(0)
        for pixel in row:
            raw.extend(bytes(pixel))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def to_ico(frames: dict[int, bytes]) -> bytes:
    """Wrap the PNGs in an ICO container.

    Every entry is a PNG rather than a BMP. Windows has accepted PNG-in-ICO
    since Vista, it is required for 256 anyway, and one encoder is one thing to
    get right instead of two.
    """
    order = sorted(frames)
    header = struct.pack("<HHH", 0, 1, len(order))
    offset = len(header) + 16 * len(order)
    entries, blobs = b"", b""
    for size in order:
        data = frames[size]
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,   # 0 means 256 in this format
            0 if size >= 256 else size,
            0, 0, 1, 32, len(data), offset,
        )
        blobs += data
        offset += len(data)
    return header + entries + blobs


def main() -> int:
    frames = {}
    for size in SIZES:
        frames[size] = to_png(draw(size))
        print(f"  drew {size}x{size}  ({len(frames[size]):,} bytes)")
    OUT.write_bytes(to_ico(frames))
    print(f"\nwrote {OUT}  ({OUT.stat().st_size:,} bytes, {len(SIZES)} sizes)")

    # Also emit the largest as a PNG, so the icon can be looked at without an
    # ICO viewer and so a test can inspect pixels without parsing the container.
    png = OUT.with_suffix(".png")
    png.write_bytes(frames[max(SIZES)])
    print(f"wrote {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
