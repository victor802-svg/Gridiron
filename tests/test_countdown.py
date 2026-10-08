"""Past the gate, the countdown says calibration speaks (UI audit finding 10,
2026-09-05). "158 of 100 · 0 more before calibration speaks" kept the shape
of a countdown after the count had passed the gate. Tested AT the gate.

FROM 2026-10-08 (operator question 46) THE LINE NAMES ONE CATEGORY: its
category is a required argument -- "moneyline, statistical, 50-60%: ..." --
where it was "50-60% bucket: ..." of a count over every market, forecaster,
pass and card. The first test asks the words with a category now, and
holds that a line naming none cannot be composed; the band counts
themselves are `test_band_line_per_category.py`'s."""
from __future__ import annotations

import pytest

from gridiron import audit, language

CATEGORY = "moneyline, statistical"


def test_the_countdown_at_and_past_the_gate():
    below = language.bucket_countdown_line(CATEGORY, "50-60%", 99, 100)
    at = language.bucket_countdown_line(CATEGORY, "50-60%", 100, 100)
    past = language.bucket_countdown_line(CATEGORY, "50-60%", 158, 100)
    assert below == ("moneyline, statistical, 50-60%: 99 of 100 · 1 more before "
                     "calibration speaks")
    assert "calibration speaks here" in at and "more before" not in at
    assert "calibration speaks here" in past and "158" in past and "0 more" not in past
    for line in (below, at, past):
        assert audit.plain_words_violations(line) == []
    for nobody in ("", "   ", None):
        with pytest.raises(ValueError, match="QUESTION 46"):
            language.bucket_countdown_line(nobody, "50-60%", 158, 100)


def test_the_glance_countdown_comes_through_the_one_function(world_copy):
    from gridiron import views
    sport = world_copy.execute(
        "SELECT sport FROM predictions WHERE resolved_utc IS NOT NULL LIMIT 1").fetchone()[0]
    payload = views.settled_since(world_copy, sport) if hasattr(views, "settled_since") else None
    if payload is None:
        import inspect
        from gridiron import calibration
        # The words are composed in one place, and the band builder is the
        # one caller (operator question 46, 2026-10-08: `views` reads the
        # bands `calibration.band_lines` composes).
        source = inspect.getsource(calibration)
        assert "bucket_countdown_line" in source
        assert "before calibration speaks" not in inspect.getsource(views)
        assert "before calibration speaks" not in source.replace(
            "bucket_countdown_line", "")
        return
    for bucket in payload["buckets"]:
        assert bucket["countdown"] == language.bucket_countdown_line(
            bucket["category_label"], bucket["label"], bucket["n"], payload["gate"])
