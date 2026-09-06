"""Past the gate, the countdown says calibration speaks (UI audit finding 10,
2026-09-05). "158 of 100 · 0 more before calibration speaks" kept the shape
of a countdown after the count had passed the gate. Tested AT the gate."""
from __future__ import annotations

from gridiron import audit, language


def test_the_countdown_at_and_past_the_gate():
    below = language.bucket_countdown_line("50-60%", 99, 100)
    at = language.bucket_countdown_line("50-60%", 100, 100)
    past = language.bucket_countdown_line("50-60%", 158, 100)
    assert below == "50-60% bucket: 99 of 100 · 1 more before calibration speaks"
    assert "calibration speaks here" in at and "more before" not in at
    assert "calibration speaks here" in past and "158" in past and "0 more" not in past
    for line in (below, at, past):
        assert audit.plain_words_violations(line) == []


def test_the_glance_countdown_comes_through_the_one_function(world_copy):
    from gridiron import views
    sport = world_copy.execute(
        "SELECT sport FROM predictions WHERE resolved_utc IS NOT NULL LIMIT 1").fetchone()[0]
    payload = views.settled_since(world_copy, sport) if hasattr(views, "settled_since") else None
    if payload is None:
        import inspect
        source = inspect.getsource(views)
        assert "bucket_countdown_line" in source
        assert "before calibration speaks" not in source.replace("bucket_countdown_line", "")
        return
    for bucket in payload["buckets"]:
        assert bucket["countdown"] == language.bucket_countdown_line(
            bucket["label"], bucket["n"], payload["gate"])
