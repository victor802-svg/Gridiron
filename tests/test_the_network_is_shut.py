"""Tests cannot reach the outside world unless they say they will.

THE CLASS FIX for what the durations list found. Two tests in `test_refresh.py`
stubbed three sports' loaders and not the fourth, so every run fetched an
entire college football season. 416 and 353 seconds -- three quarters of the
whole suite. Nothing failed, nothing was marked slow; they were simply slow,
for weeks.

The test directly above them stubbed all four AND carried a comment explaining
the trap, written the first time it was found. A lesson recorded in prose gets
applied to some of the places it belongs.

What the guard then found, in order, none of it by reading:
  1. the college loader, unstubbed in two tests   (the known one)
  2. `_near_start_snapshots`, a market fetch       (a second way out)
  3. `teams.load_teams`, per sport                 (a third, another module)
"""

from __future__ import annotations

import socket
import urllib.request

import pytest


def test_an_unmarked_test_cannot_reach_the_network():
    """THE PLANTED VIOLATION, run inline: this is what the guard does.

    A test that fetches without declaring it must fail loudly rather than
    quietly taking six minutes.
    """
    # Caught by BEHAVIOUR rather than by importing the class: `conftest` is
    # not importable by name, and the message is the part a person actually
    # meets when this fires.
    with pytest.raises(RuntimeError) as caught:
        socket.create_connection(("sports.core.api.espn.com", 443), timeout=5)
    assert "stub the source" in str(caught.value)
    assert "mark the test" in str(caught.value)


def test_the_block_covers_the_ways_out_that_were_actually_used():
    """Each of these is a real call path something in this project took."""
    for call in (
        lambda: socket.socket().connect(("example.invalid", 80)),
        lambda: socket.socket().connect_ex(("example.invalid", 80)),
        lambda: urllib.request.urlopen("https://example.invalid/x", timeout=5),
    ):
        with pytest.raises(Exception) as caught:
            call()
        assert "stub the source" in str(caught.value), (
            f"this call path is not covered by the guard: {caught.value}")


def test_loopback_stays_open():
    """The browser suite drives a real server on 127.0.0.1.

    That is not "the network" in any sense this guard cares about -- it is the
    application under test, and blocking it would make the guard useless
    rather than strict.
    """
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=5)
        client.close()
    finally:
        listener.close()


@pytest.mark.network
def test_a_marked_test_is_allowed_out_and_is_named(request):
    """The escape hatch, and it is not silent.

    A test carrying this marker appears by name in the run's summary under
    "tests that reached the network". The gate's own rule is that a tier which
    did not run has to be NAMED rather than counted; a test that left the
    building is the same kind of fact.

    It does not reach anything real: it asks for a hostname that cannot
    resolve. Unmarked, that raises the guard's own error; marked, it raises the
    resolver's -- which proves the guard stepped aside without needing the
    outside world to be up. A test that fails when the wifi does is a test
    nobody trusts.
    """
    assert request.node.get_closest_marker("network") is not None
    with pytest.raises(Exception) as caught:
        socket.create_connection(("no-such-host.invalid", 80), timeout=5)
    assert "stub the source" not in str(caught.value), (
        "the guard is still installed on a test marked `network`")
