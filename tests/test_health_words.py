"""The Health panel speaks in words (UI audit finding 11, 2026-09-05).

A failed task recorded "SlateAlreadyAnswered: ufc 2026 slate 20260905 already
has 84 forecasts ... written 2026-09-04T02:04 under factor set 'fs2'" and the
Settings page placed it as it was. The rendered-page scan covers the route and
never saw it: no fixture run had failed. The browser world now carries one.
"""
from __future__ import annotations

from gridiron import audit, language, tasks

RAW = ("SlateAlreadyAnswered: ufc 2026 slate 20260905 already has 84 forecasts in "
       "every market it asks (distance, moneyline, rounds), written 2026-09-04T02:04 "
       "under factor set 'fs2'. A slate is answered once. Nothing was written.")


def test_the_recorded_detail_is_said_in_words():
    words = language.task_detail_words(RAW)
    assert audit.plain_words_violations(words) == [], words
    assert not words.startswith("SlateAlreadyAnswered")
    assert "the slate of 5 September 2026" in words
    assert "4 September 2026 at 02:04 UTC" in words
    assert "factor set 2" in words and "fs2" not in words
    assert "84 forecasts in every market it asks (distance, moneyline, rounds)" in words
    assert language.task_detail_words(None) is None
    assert language.task_detail_words("") == ""
    # a bare version token, as the recalibration task writes it
    bare = language.task_detail_words("fitted 12 categories under fs2; 3 unchanged")
    assert bare == "fitted 12 categories under factor set 2; 3 unchanged"
    assert audit.plain_words_violations(bare) == []


def test_the_health_payload_carries_the_failed_run_in_words(world_copy):
    health = tasks.status(world_copy)
    entry = next(t for t in health["tasks"] if t["task"] == "catch-up")
    assert entry["last_result"] == "failed"
    assert "SlateAlreadyAnswered" not in entry["last_detail"]
    assert "20260905" not in entry["last_detail"]
    assert audit.health_detail_faults(health) == []


def test_the_guard_sees_a_raw_detail():
    faults = audit.health_detail_faults({"tasks": [{"task": "catch-up", "last_detail": RAW, "missed": []}]})
    assert faults and "catch-up" in faults[0]
    faults = audit.health_detail_faults({"tasks": [{"task": "resolve", "last_detail": None,
                                                   "missed": [{"detail": RAW}]}]})
    assert faults, "a missed run's raw detail escaped"


def test_the_settings_page_shows_the_failed_run_in_words(page):
    page.evaluate("location.hash = '#/settings'")
    page.wait_for_selector("#settings-health .set", timeout=15000)
    text = page.text_content("#settings-health")
    assert "SlateAlreadyAnswered" not in text
    assert "20260905" not in text
    assert "the slate of 5 September" in text


#: Each Health row's label column against the row, as the page lays it out.
_LABEL_SHARE = (
    "() => [...document.querySelectorAll('#settings-health .set')].map(r => ["
    " r.querySelector('.set-k b').textContent,"
    " r.querySelector('.set-k').getBoundingClientRect().width"
    " / r.getBoundingClientRect().width])")


def test_a_long_detail_leaves_the_label_room_to_be_read(page):
    """THE PROVER OF GRIDIRON_REPAIR item 7 (2026-09-26). The value column
    is `auto`, so a long detail -- this world's failed catch-up, and from
    item 7 every abandoned run's -- took the row and left the label column,
    where the warning sits, a few words a line: 4% of the row at 1120px and
    12% at 390, measured on the unfixed stylesheet. A detail now wraps
    inside 62ch, and a Health row stacks at phone width."""
    page.evaluate("location.hash = '#/settings'")
    page.wait_for_selector("#settings-health .set", timeout=15000)
    wide = page.evaluate(_LABEL_SHARE)
    assert wide and min(share for _label, share in wide) > 0.3, wide
    page.set_viewport_size({"width": 390, "height": 844})
    narrow = page.evaluate(_LABEL_SHARE)
    assert narrow and min(share for _label, share in narrow) > 0.9, narrow
