"""The near-start pass reads every open recommendation, every firing
(GRIDIRON_REPAIR item 1, 2026-09-23).

Until that date the pass read each prediction once and then excluded it, and
it never read a recommended prediction at all: every one of them had no media
line, and the pass only took predictions that did. The close was therefore
always the price the recommendation was made at -- 49 of 49 rows at 0.00c.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from gridiron import db, tasks
from gridiron.market import lines


def _stamp(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


def _world(tmp_path, *, closed=False):
    conn = db.open_db(tmp_path / "near.db")
    kickoff = _stamp(timedelta(hours=1))
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g0', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', ?, 'scheduled', '2026-09-23')", (kickoff,))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'mlb', 'g0',"
        " 'total', 'BBB at AAA', 8.5, 0.6, 'over', 'statistical', 'final',"
        " 'fs2', '{}', 'x')", (_stamp(timedelta(hours=-5)),))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    # NO MEDIA LINE: the open snapshot carries no implied probability, which
    # is the shape of all 55 recommended predictions on 2026-09-23.
    conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
        " implied_prob, kind) VALUES (?, ?, 'test', NULL, 'open_at_predict')",
        (pid, _stamp(timedelta(hours=-5))))
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc, closed_utc) VALUES (?, 'mlb', 'g0', 'total', 'yes', 0.6,"
        " 0.46, 10.0, 'flat', 1.0, 0, ?, ?)",
        (pid, _stamp(timedelta(hours=-4)),
         _stamp(timedelta(hours=-3)) if closed else None))
    conn.commit()
    return conn, pid


def _watch(monkeypatch):
    """Record what the pass hands the venue read, instead of reading it.

    THE MODULE IS LOOKED UP NOW, not at import. A blind window drops the market
    package from `sys.modules` (`blind.forget_market_module`), so a test that
    ran one earlier in the session leaves this file holding a stale `lines`
    while the pass imports a fresh one -- and a patch on the stale one is a
    patch on nothing. It passed alone and failed in the suite the first time.
    """
    import importlib

    current = importlib.import_module(lines.__name__)
    seen: list[list[int]] = []

    def read(conn, ids):
        seen.append(list(ids))
        return {"quotes": 0, "claims": 0}

    monkeypatch.setattr(current, "refresh_venue_ladder", read)
    return seen


def test_an_open_recommendation_is_read_on_every_firing(tmp_path, monkeypatch):
    conn, pid = _world(tmp_path)
    seen = _watch(monkeypatch)
    first = tasks._near_start_snapshots(conn)
    second = tasks._near_start_snapshots(conn)
    # read both times: the close is the LAST read before the start, so a pass
    # that reads once and stops can never find it
    assert seen == [[pid], [pid]]
    assert first["near_start_recommendations"] == 1
    assert second["near_start_due"] == 1


def test_a_closed_recommendation_is_not_read(tmp_path, monkeypatch):
    conn, _ = _world(tmp_path, closed=True)
    seen = _watch(monkeypatch)
    tasks._near_start_snapshots(conn)
    assert seen == []


def test_the_once_then_exclude_is_retired_by_name():
    """It may not come back quietly, and the note saying why it went stays."""
    source = Path(tasks.__file__).read_text(encoding="utf-8")
    assert "RETIRED 2026-09-23 (GRIDIRON_REPAIR item 1): THE ONCE-THEN-EXCLUDE" in source
    body = source[source.index("def _near_start_snapshots"):
                  source.index("def _plus_hours")]
    code = "\n".join(line for line in body.splitlines()
                     if not line.strip().startswith("#"))
    assert "n.kind = 'near_start'" not in code, \
        "the once-then-exclude is back in the near-start selection"
