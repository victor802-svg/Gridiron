"""Screenshots of the board, every page and every empty state, at 1100 and 390.

    python tools/board_shots.py [out_dir]

Builds the browser suite's own world (the same league, weeks and forecasts
`tests/conftest.py` seeds), serves it on a loopback port, signs in the way a
person does, and captures each page. A second copy of the world carries one
game in progress and one taken pick, so the live row and YOURS are on the
page. Nothing here touches the operator's record: the worlds are scratch files
under the output directory.

The captures are the close-out's evidence (GRIDIRON_BOARD, 2026-09-24); the
gate does not run this.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gridiron import api, auth, db  # noqa: E402

TOKEN = "board-shots-token"
WIDTHS = ((1100, 900), (390, 844))


def _world(path: Path) -> None:
    from tests import conftest as ct

    conn = db.open_db(path)
    ct.seed_league(conn)
    ct._build_world(conn)
    conn.close()


def _live_copy(source: Path, target: Path) -> None:
    """The same world with one game in progress and one standing pick taken."""
    shutil.copy(source, target)
    conn = db.open_db(target)
    game = conn.execute(
        "SELECT g.id FROM games g JOIN predictions p ON p.game_id = g.id"
        " WHERE g.status = 'scheduled' ORDER BY g.kickoff_utc, g.id LIMIT 1").fetchone()[0]
    conn.execute(
        "UPDATE games SET status = 'in', home_score = 17, away_score = 14,"
        " live_period = '3rd Quarter', live_clock = '8:41', live_updated_utc = ?"
        " WHERE id = ?", (db.utcnow(), game))
    other = conn.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE g.status = 'scheduled' AND g.id != ? AND p.predictor = 'statistical'"
        "   AND NOT EXISTS (SELECT 1 FROM predictions later"
        "                   WHERE later.game_id = p.game_id AND later.market_type = p.market_type"
        "                     AND later.subject = p.subject AND later.predictor = p.predictor"
        "                     AND later.created_utc > p.created_utc)"
        " ORDER BY p.id LIMIT 1", (game,)).fetchone()[0]
    conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                 (other, db.utcnow()))
    # AND ONE PROP, so the entry rail has a leg and its lines to show.
    prop = conn.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE g.status = 'scheduled' AND g.id != ? AND p.predictor = 'statistical'"
        "   AND p.market_type = 'prop' AND p.id != ?"
        "   AND NOT EXISTS (SELECT 1 FROM predictions later"
        "                   WHERE later.game_id = p.game_id AND later.market_type = p.market_type"
        "                     AND later.subject = p.subject AND later.predictor = p.predictor"
        "                     AND later.created_utc > p.created_utc)"
        " ORDER BY p.id LIMIT 1", (game, other)).fetchone()
    if prop:
        conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                     (prop[0], db.utcnow()))
    conn.commit()
    conn.close()


def _serve(db_file: Path):
    import socket

    import uvicorn

    api.set_database(db_file)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while time.time() < deadline and not server.started:
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}", server


def _sign_in(page, base: str) -> None:
    page.goto(base + "/login", wait_until="networkidle")
    page.fill("#token", TOKEN)
    page.click("#submit")
    page.wait_for_url(base + "/", timeout=15000)
    page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)


def _route(page, route: str) -> None:
    page.evaluate(f"location.hash = '#/{route}'")
    page.wait_for_function(
        "(id) => { const el = document.getElementById(id); return !!el && !el.hidden; }",
        arg=f"view-{route}", timeout=15000)
    page.wait_for_timeout(600)


def capture(base: str, out: Path, tag: str, *, sport: str | None = None,
            routes=("games", "props", "record", "results", "settings"),
            expand: bool = False, last_week: bool = False) -> list[str]:
    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, height in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": height})
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            _sign_in(page, base)
            if sport:
                page.click(f"#sport-tabs button[data-sport='{sport}']")
                page.wait_for_timeout(600)
            for route in routes:
                _route(page, route)
                if route == "games" and last_week:
                    page.evaluate("document.querySelector('.week-more').open = true")
                    options = page.evaluate(
                        "[...document.querySelectorAll('#week-picker option')].map(o => o.value)")
                    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
                        page.select_option("#week-picker", options[-1])
                    page.wait_for_timeout(600)
                if route == "games" and expand:
                    head = page.query_selector("#games-rows .game-head")
                    if head:
                        head.click()
                        page.wait_for_timeout(300)
                page.screenshot(path=str(out / f"{tag}-{route}-{width}.jpg"), full_page=True, type="jpeg", quality=82)
            ctx.close()
        browser.close()
    return errors


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else REPO / "docs" / "closeouts" / "shots" / "2026-09-25-board"
    out.mkdir(parents=True, exist_ok=True)
    os.environ[auth.TOKEN_VAR] = TOKEN
    scratch = Path(tempfile.mkdtemp(prefix="board-shots-"))
    world = scratch / "world.db"
    live = scratch / "world-live.db"
    print("building the world ...")
    _world(world)
    _live_copy(world, live)
    errors: list[str] = []
    base, server = _serve(world)
    try:
        errors += capture(base, out, "board")
        errors += capture(base, out, "expanded", routes=("games",), expand=True)
        errors += capture(base, out, "settled", routes=("games",), expand=True, last_week=True)
        # THE EMPTY STATES: a sport with no forecasts (no games today, props
        # not read yet) -- NBA in the fixture world.
        errors += capture(base, out, "empty", sport="nba", routes=("games", "props"))
    finally:
        server.should_exit = True
    base, server = _serve(live)
    try:
        errors += capture(base, out, "live", routes=("games", "props"))
    finally:
        server.should_exit = True
        api.set_database(None)
    shutil.rmtree(scratch, ignore_errors=True)
    print(f"wrote {len(list(out.glob('*.jpg')))} captures to {out}")
    if errors:
        print("PAGE ERRORS:", errors)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
