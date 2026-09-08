"""GRIDIRON_NIGHT_AUDIT (2026-09-08): what the audit built and what it removed.

Item 1 is the one construction the brief permits: a dead job on the first
screen. The rest of this file proves removals -- code that served pages
THREE_STATES took away -- by asserting the names are gone and the scans that
would have to notice a regression still run clean.
"""
from pathlib import Path

import pytest

from gridiron import audit, config, db, language, views

WEB = Path(views.__file__).resolve().parent / "web"


def test_the_thresholds_are_declared_and_dated():
    assert set(config.FRESHNESS_HOURS) == {"daily_run", "venue_read", "reasoning"}
    assert config.FRESHNESS_DECLARED.startswith("2026-09-08")
    assert all(h > 0 for h in config.FRESHNESS_HOURS.values())


def test_a_fresh_record_reads_fresh_and_a_silent_one_reads_dead(tmp_path):
    conn = db.open_db(tmp_path / "pulse.db")
    block = views.freshness(conn)
    assert [e["job"] for e in block["entries"]] == ["daily_run", "venue_read", "reasoning"]
    # NEVER RUN IS STALE, in words: an age of nothing is not an age of zero.
    assert block["any_stale"]
    assert all("never run" in e["words"] for e in block["entries"])

    conn.execute("INSERT INTO task_runs (task, started_utc, finished_utc, result, detail)"
                 " VALUES ('predict:mlb', ?, ?, 'ok', 'wrote 5')",
                 (db.utcnow(), db.utcnow()))
    conn.commit()
    block = views.freshness(conn)
    run = next(e for e in block["entries"] if e["job"] == "daily_run")
    assert run["stale"] is False and "ago" in run["words"]


def test_the_words_carry_the_threshold_when_it_is_crossed():
    assert language.freshness_words("venue read", 31.0, 30.0) == "venue read 31h ago, past 30h"
    assert language.freshness_words("venue read", 3.0, 30.0) == "venue read 3h ago"
    assert language.freshness_words("daily run", 60.0, 36.0) == "daily run 2 days ago, past 36h"
    assert language.freshness_words("reasoning pass", None, 36.0) == "reasoning pass has never run"


def test_the_strip_carries_the_pulse_and_a_stale_job_is_marked_without_red():
    """THE BRIEF SAID "TURNS RED"; the colour law's guard reserves red for a
    loss. The stale state is bold in the warning ink and its words carry the
    threshold; red is a ruling for the morning, and this test holds the line
    until it is made."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert 'id="day-jobs"' in html
    assert "day-job-stale" in js
    assert ".day-job-stale { color: var(--warn-ink)" in css
    assert audit.colour_law_faults(css) == []


def test_a_dead_job_shown_as_fresh_is_refused_by_name():
    planted = {"freshness": {"entries": [
        {"job": "daily_run", "age_hours": 2.0, "limit_hours": 36.0,
         "stale": False, "words": "daily run 2h ago"},
        {"job": "venue_read", "age_hours": 1.0, "limit_hours": 30.0,
         "stale": False, "words": "venue read 1h ago"},
        {"job": "reasoning", "age_hours": 66.0, "limit_hours": 36.0,
         "stale": False, "words": "reasoning pass 66h ago"},
    ]}}
    with pytest.raises(audit.LawViolation, match="FIRST SCREEN"):
        audit.check_the_strip_shows_a_dead_job(planted)
    assert audit.freshness_faults({"today": {}}), "no block at all is a fault"


# ---------------------------------------------------------------------------
# Item 6: the dead weight is gone, and the scans that would notice a
# regression still run clean.
# ---------------------------------------------------------------------------

def test_the_hero_pool_and_the_notice_shortener_are_gone():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    # THE DEFINITION FORMS, not the bare names: the dated note that marks
    # where each stood names them, and a comment must be able to say what
    # was removed without a scan reading that as the thing coming back.
    for name in ("function heroPool", "const HERO_STEPS", "function shortNotice"):
        assert name not in js, name


def test_no_rule_styles_a_class_nothing_builds():
    css = (WEB / "style.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for cls in ("notices-summary", "notices-count", "view-menu"):
        assert f".{cls} " not in css and f".{cls}{{" not in css and f".{cls}:" not in css, cls
        assert f"'{cls}'" not in js and f'"{cls}"' not in js and f" {cls} " not in html, cls
    assert audit.dead_selector_faults(js, html, css) == []
    assert audit.duplicate_js_definitions() == []


def test_the_retired_hero_test_file_stays_as_the_marker():
    """Zero tests, on purpose, with the reason in its docstring."""
    source = (Path(__file__).parent / "test_hero_floor.py").read_text(encoding="utf-8")
    assert "RETIRED WITH THE HERO" in source
    assert "def test_" not in source


def test_no_chip_on_a_card_repeats_the_label_above_it():
    """THE SIBLINGS OF "Payspays". Every value that sits under a label on a
    card is checked against that label's words."""
    labels = language.price_row_labels()
    assert "pays" not in language.payout_chip_words(2.5).lower()
    assert "after fees" not in language.edge_line_words(4.0)
    assert "other side" not in language.edge_line_words(4.0, other_side=True)
    # and the label is where "on the other side" lives, said once
    assert language.edge_label_words(labels["edge"], "no").endswith("on the other side")


# ---------------------------------------------------------------------------
# Item 4: the strings that would have passed, and no longer do.
# ---------------------------------------------------------------------------

def test_a_combo_identifier_on_a_label_is_internal_vocabulary():
    for term in ("combo_2", "same_game", "unforecast_leg", "why_not", "settles_into"):
        assert audit.plain_words_violations(f"Priced as {term} today"), term


def test_a_urllib_post_in_the_market_module_is_an_order_path(tmp_path):
    market = tmp_path / "market"
    market.mkdir()
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    (market / "__init__.py").write_text("", encoding="utf-8")
    (market / "venue.py").write_text(
        "import urllib.request\n"
        "def send(url, body):\n"
        "    return urllib.request.urlopen(urllib.request.Request(url, data=body))\n",
        encoding="utf-8")
    faults = audit.order_path_faults(tmp_path)
    assert any("data=" in f for f in faults), faults
    # and a plain read is not a write
    (market / "venue.py").write_text(
        "import urllib.request\n"
        "def read(url):\n"
        "    return urllib.request.urlopen(urllib.request.Request(url))\n",
        encoding="utf-8")
    assert not any("data=" in f or "method=" in f for f in audit.order_path_faults(tmp_path))


def test_the_shipped_tree_still_passes_every_widened_scan():
    """The additions were grepped first; this is the proof they renamed nothing."""
    assert audit.venue_credential_faults() == []
    assert audit.order_path_faults() == []
    assert audit.wagering_ledger_faults() == []
