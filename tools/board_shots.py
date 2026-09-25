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
WIDTHS = ((1300, 1100), (390, 844))


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


def _standing(conn, game: str, market: str | None = None) -> "sqlite3.Row | None":
    """The standing statistical forecast on one game: in one market, or the
    first of spread and total the fixture holds (the fixture week asks
    mostly totals, spreads being held)."""
    markets = (market,) if market else ("spread", "total")
    for m in markets:
        row = conn.execute(
            "SELECT p.id, p.game_id, p.model_prob, p.line_asked, p.market_type FROM predictions p"
            " WHERE p.game_id = ? AND p.market_type = ? AND p.predictor = 'statistical'"
            "   AND NOT EXISTS (SELECT 1 FROM predictions later"
            "                   WHERE later.game_id = p.game_id AND later.market_type = p.market_type"
            "                     AND later.subject = p.subject AND later.predictor = p.predictor"
            "                     AND later.created_utc > p.created_utc)"
            " ORDER BY p.id LIMIT 1", (game, m)).fetchone()
        if row:
            return row
    return None


def _price(conn, pred, *, implied: float) -> None:
    """A venue quote and the frozen claim read against it, so the Today block
    prices the question and the row wears the outline the arithmetic gives
    it. The shape is the one the fixture's markets take; the numbers are
    chosen, not measured, and the copy is thrown away after the capture."""
    market = pred["market_type"]
    quantity = {"spread": "home_margin", "total": "total"}.get(market, "count")
    side = "over" if market == "total" else "home"
    # STAMPED AFTER THE PREDICTION, as the blind-first triggers require.
    now = db.just_after(pred["created_utc"]) if pred.get("created_utc") else db.utcnow()
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id, market,"
        " quantity, line, yes_side, yes_bid, yes_ask, last_price, volume, fetched_utc)"
        " VALUES ('fixture venue', 'T', 'E', 'nfl', ?, ?, ?, ?, ?, ?, ?, ?, 500, ?)",
        (pred["game_id"], market, quantity, pred["line_asked"], side,
         implied - 0.01, implied + 0.01, implied, now))
    quote_id = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (created_utc, prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, model_prob, venue_price,"
        " venue_implied, price_basis)"
        " VALUES (?, ?, ?, 'fixture venue', 'nfl', ?, ?, ?, ?, ?, 'rung_matched', ?, ?, ?,"
        " 'the midpoint of the venue book')",
        (now, pred["id"], quote_id, pred["game_id"], market, quantity, pred["line_asked"],
         side, pred["model_prob"], implied, implied))


def _cover(conn, markets=("spread", "total")) -> None:
    """Enough narrow, thin quotes across three games that the coverage list
    calls each market measured -- the numbers are invented for the capture
    and the copy is thrown away."""
    games = [r[0] for r in conn.execute("SELECT DISTINCT game_id FROM predictions ORDER BY game_id LIMIT 3").fetchall()]
    for market in markets:
        quantity = "home_margin" if market == "spread" else "total"
        for i in range(60):
            conn.execute(
                "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id, market,"
                " quantity, line, yes_side, yes_bid, yes_ask, last_price, volume, fetched_utc)"
                " VALUES ('fixture venue', 'T', 'E', 'nfl', ?, ?, ?, ?, ?, 0.49, 0.51, 0.50, 40, ?)",
                (games[i % 3], market, quantity, -3.5 + i * 0.5,
                 "over" if market == "total" else "home", db.utcnow()))


def _take(conn, pred_id: int) -> None:
    conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                 (pred_id, db.utcnow()))


def _mockup_copy(source: Path, target: Path) -> None:
    """The world in the mockup's shape: a live game, a game whose pick clears
    the bar with a question that costs after fees beside it, a won final and
    a lost final. Four games is what the fixture week holds, so the costs
    row of the mockup is a tile inside the expanded row here."""
    from gridiron import resolve

    shutil.copy(source, target)
    conn = db.open_db(target)
    games = [r[0] for r in conn.execute(
        "SELECT DISTINCT g.id FROM games g JOIN predictions p ON p.game_id = g.id"
        " WHERE g.status = 'scheduled' ORDER BY g.kickoff_utc, g.id").fetchall()]
    live, priced, final_a, final_b = games[:4]
    conn.execute(
        "UPDATE games SET status = 'in', home_score = 17, away_score = 14,"
        " live_period = '3rd Quarter', live_clock = '8:41', live_updated_utc = ?"
        " WHERE id = ?", (db.utcnow(), live))
    _cover(conn, ("total",))
    # A FIFTH GAME, so the costs-after-fees row exists beside the one that
    # clears: the fixture week holds four games and the mockup shows five.
    # Its total forecast is a copy of the priced game's, written now, with
    # its own number; the row's face carries the club colours like any other.
    home, away = conn.execute("SELECT home, away FROM games WHERE id = ?", (priced,)).fetchone()
    fifth = f"2025_18_{home}_{away}"
    conn.execute(
        "INSERT INTO games (id, season, week, game_type, kickoff_utc, home, away, status, sport)"
        " SELECT ?, season, week, game_type, kickoff_utc, ?, ?, 'scheduled', sport FROM games WHERE id = ?",
        (fifth, away, home, priced))

    def _fresh_total(game: str, prob: float) -> int:
        seed = conn.execute(
            "SELECT * FROM predictions WHERE market_type = 'total' AND predictor = 'statistical'"
            " AND game_id = ? ORDER BY id DESC LIMIT 1", (priced,)).fetchone()
        cols = [c for c in seed.keys() if c not in ("id",)]
        row = dict(seed)
        # THE LATE PASS, so the key admits it beside the early forecast and
        # the standing-row clause reads the later one.
        made = db.utcnow()
        row.update(game_id=game, model_prob=prob, created_utc=made,
                   pass_kind='final' if game == priced else row['pass_kind'])
        conn.execute(
            f"INSERT INTO predictions ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [row[c] for c in cols])
        new_id = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
        rank = conn.execute("SELECT * FROM prediction_ranks WHERE prediction_id = ? ORDER BY id DESC LIMIT 1",
                            (seed["id"],)).fetchone()
        if rank:
            rcols = [c for c in rank.keys() if c != "id"]
            rrow = dict(rank); rrow.update(prediction_id=new_id, on_shortlist=1, created_utc=db.just_after(made))
            conn.execute(
                f"INSERT INTO prediction_ranks ({', '.join(rcols)}) VALUES ({', '.join('?' for _ in rcols)})",
                [rrow[c] for c in rcols])
        return new_id

    clears_id = _fresh_total(priced, 0.64)
    costs_id = _fresh_total(fifth, 0.52)
    # COSTS AFTER FEES means neither side is cheap: the model within the fee
    # of the price, not far below it (far below makes the other side cheap).
    for pid, model, implied in ((clears_id, 0.64, 0.54), (costs_id, 0.59, 0.60)):
        pred = conn.execute("SELECT id, game_id, line_asked, market_type, created_utc FROM predictions WHERE id = ?",
                            (pid,)).fetchone()
        _price(conn, {**dict(pred), "model_prob": model}, implied=implied)
    _take(conn, clears_id)
    conn.commit()
    conn.close()
    # TWO FINALS, one every pick won and one every pick lost, so the row's
    # lead pick reads won on one and lost on the other whichever question
    # leads. The scores are tried on a copy nobody keeps.
    def _all_outcomes(c, game):
        return [r[0] for r in c.execute(
            "SELECT outcome FROM predictions WHERE game_id = ? AND predictor = 'statistical'"
            "   AND market_type IN ('spread', 'total')", (game,)).fetchall()]

    scores = ((34, 31), (31, 34), (10, 7), (7, 10), (45, 3), (3, 45))
    done = False
    for score_a in scores:
        for score_b in scores:
            if done:
                break
            trial = target.with_suffix(".trial.db")
            shutil.copy(target, trial)
            c2 = db.open_db(trial)
            for game, (home, away) in ((final_a, score_a), (final_b, score_b)):
                c2.execute("UPDATE games SET status = 'final', home_score = ?, away_score = ? WHERE id = ?",
                           (home, away, game))
            c2.commit()
            resolve.resolve_all(c2)
            a, b = _all_outcomes(c2, final_a), _all_outcomes(c2, final_b)
            c2.close()
            if a and b and ((all(x == 1 for x in a) and all(x == 0 for x in b))
                            or (all(x == 0 for x in a) and all(x == 1 for x in b))):
                shutil.move(trial, target)
                done = True
            else:
                trial.unlink()
    conn = db.open_db(target)
    for g in (final_a, final_b):
        pred = _standing(conn, g)
        if pred and conn.execute("SELECT outcome FROM predictions WHERE id = ?",
                                 (pred["id"],)).fetchone()[0] == 1:
            _take(conn, pred["id"])
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
                # FROM THE TOP: a sticky header paints where the page was
                # scrolled, and a full-page capture taken mid-scroll shows it
                # mid-page.
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(150)
                page.screenshot(path=str(out / f"{tag}-{route}-{width}.jpg"), full_page=True, type="jpeg", quality=82)
            ctx.close()
        browser.close()
    return errors


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else REPO / "docs" / "closeouts" / "shots" / "2026-09-25-visual"
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
        errors += capture(base, out, "app")
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
    # THE MOCKUP'S SHAPE (visual pass, 2026-09-25): the side-by-side pair.
    shaped = scratch / "world-mockup.db"
    _mockup_copy(world, shaped)
    base, server = _serve(shaped)
    try:
        errors += capture(base, out, "shaped", routes=("games", "props"), expand=True)
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
