"""Results that find you, and failures that do not wait to be found.

The failure channel exists because of something that already happened: the
appliance sat stalled for two days with every screen green. `resolve` ran every
four hours and truthfully reported "nothing to settle" each time, because
nothing was updating `games.status`. No task failed, no error was logged, and
nothing on any screen was wrong. A push is the only surface that reaches
somebody who is not looking at one.
"""

from __future__ import annotations

import datetime as dt

import pytest

from gridiron import notify


def test_a_message_may_not_carry_a_probability():
    """A push lands on a lock screen and the topic is readable by anyone
    holding it. A percentage there is a tip."""
    faults = notify.message_faults("MLB: 7 settled - model 62% right")
    assert faults and "percentage" in faults[0]


def test_a_message_may_not_carry_a_line():
    """THE ONE THE FIRST REGEX MISSED.

    `\b[-+]` can never match after a space -- a word boundary needs a word
    character on one side, and both ' ' and '-' are non-word. So "Alabama
    -24.5" went straight through the guard whose entire purpose is that no
    line leaves the building. Found by testing the guard against the thing it
    exists to stop, not by reading it.
    """
    for line in ("Alabama -24.5 settled", "ECU +24.5", "total +3.5",
                 "price -110", "odds 2.15"):
        assert notify.message_faults(line), f"{line!r} was allowed out"


def test_the_messages_that_should_pass_do():
    """A guard this crude has to be checked in both directions, or it will
    quietly refuse every message and the channel will look broken."""
    for good in ("MLB: 7 settled - model 4 right, you 2 of 3.",
                 "NCAAF: 60 settled - model 33 right.",
                 "predict:mlb has not run in 40 hours"):
        assert not notify.message_faults(good), f"{good!r} was blocked"


def test_a_blocked_message_raises_rather_than_being_softened():
    with pytest.raises(notify.Blocked):
        notify.check_message("model 62% right")


def test_results_are_never_summed_across_sports():
    """LAW 6. Each sport is its own clause with its own counts, and there is
    no total anywhere in the sentence to be tempted by."""
    said = notify.results_message({
        "mlb": {"settled": 7, "right": 4, "calls_settled": 3, "calls_right": 2},
        "cfb": {"settled": 60, "right": 33},
    })
    assert "MLB: 7 settled" in said and "NCAAF: 60 settled" in said
    assert "67" not in said, "the sports were added together"


def test_nothing_settled_sends_nothing():
    """A message saying "0 settled" teaches its reader to stop reading them,
    and the resolve task runs every four hours regardless."""
    assert notify.results_message({"mlb": {"settled": 0, "right": 0}}) is None
    assert notify.results_message({}) is None


def test_the_operators_calls_appear_only_when_they_made_some():
    with_calls = notify.results_message(
        {"mlb": {"settled": 7, "right": 4, "calls_settled": 3, "calls_right": 2}})
    assert "you 2 of 3" in with_calls
    without = notify.results_message({"mlb": {"settled": 7, "right": 4}})
    assert "you" not in without


def test_quiet_hours_are_the_operators_night():
    for hour in (23, 0, 3, 6):
        assert notify.in_quiet_hours(dt.datetime(2026, 9, 2, hour))
    for hour in (7, 12, 22):
        assert not notify.in_quiet_hours(dt.datetime(2026, 9, 2, hour))


def test_results_queue_overnight_and_failures_do_not(conn):
    """A stalled appliance at 02:00 is still stalled at 07:00.

    The whole point of the failure channel is that it does not wait to be
    noticed, so it is the one thing quiet hours must not silence.
    """
    night = dt.datetime(2026, 9, 2, 2, 0)
    out = notify.send(conn, "results", "MLB: 7 settled - model 4 right.",
                      now=night)
    assert out["queued"] is True
    assert conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE state='queued'"
    ).fetchone()[0] == 1


def test_the_queue_flushes_as_one_message(conn):
    """Three results overnight arrive as one line in the morning, not three
    notifications at 07:00."""
    night = dt.datetime(2026, 9, 2, 2, 0)
    for body in ("MLB: 1 settled - model 1 right.",
                 "NCAAF: 2 settled - model 1 right.",
                 "NBA: 3 settled - model 2 right."):
        notify.send(conn, "results", body, now=night)
    held = notify.flush_queue(conn, now=dt.datetime(2026, 9, 2, 7, 30))
    assert held == 3
    assert conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE state='queued'"
    ).fetchone()[0] == 0


def test_a_failed_channel_is_recorded_honestly(conn, monkeypatch):
    """A push that silently did not arrive is worse than no push channel:
    the operator believes they are covered."""
    monkeypatch.setattr(notify, "send_push", lambda *a, **k: {
        "channel": "push", "ok": False, "detail": "HTTP 500"})
    monkeypatch.setattr(notify, "send_toast", lambda *a, **k: {
        "channel": "toast", "ok": False, "detail": "no notifier"})
    notify.send(conn, "results", "MLB: 1 settled - model 1 right.",
                now=dt.datetime(2026, 9, 2, 14, 0))
    last = notify.last_sent(conn)
    assert last["state"] == "failed"
    assert any(c["detail"] == "HTTP 500" for c in last["channels"])


def test_no_topic_is_said_rather_than_silently_skipped(monkeypatch):
    from gridiron import config

    monkeypatch.setattr(config, "_FILE_SETTINGS", {})
    monkeypatch.delenv("GRIDIRON_NTFY_TOPIC", raising=False)
    result = notify.send_push("MLB: 1 settled.")
    assert result["ok"] is False
    assert "no topic configured" in result["detail"]
