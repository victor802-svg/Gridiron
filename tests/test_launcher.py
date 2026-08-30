"""F1: the desktop launcher.

The test that earns its place is `test_the_record_never_resolves_inside_a_bundle`.
Everything else here is convenience; that one protects the only thing in this
project that cannot be regenerated. A rebuild replaces `dist/` wholesale, so a
database resolved inside it is a record that a rebuild silently deletes — and it
would be deleted at exactly the moment somebody was pleased about shipping.

The second is the attach-first pair. Two servers on one SQLite file is how a
personal appliance ends up locked, and the failure is invisible: the second copy
looks like the app simply opening.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from desktop import launcher  # noqa: E402


# --- the record must survive a rebuild --------------------------------------

def test_the_record_never_resolves_inside_a_bundle():
    """The database and the token file must both live outside dist/ and outside
    any PyInstaller extraction directory."""
    assert launcher.paths_are_outside_the_bundle() == []
    for path in (launcher.database_path(), launcher.env_path()):
        assert "dist" not in path.parts, f"{path} is inside dist/"


def test_a_database_inside_dist_is_refused_by_name(monkeypatch):
    """Planted: point the database inside dist/ and check the launcher notices.

    It refuses to start rather than running and quietly writing the record
    somewhere a rebuild will erase.
    """
    from gridiron import config

    monkeypatch.setattr(
        config, "DB_PATH", Path(launcher.REPO) / "dist" / "Gridiron" / "gridiron.db"
    )
    problems = launcher.paths_are_outside_the_bundle()
    assert problems, "a database inside dist/ was accepted"
    assert "dist" in problems[0]
    assert "database" in problems[0]


def test_a_token_inside_dist_is_refused_by_name(monkeypatch):
    from gridiron import auth

    monkeypatch.setattr(auth, "ENV_FILE", Path(launcher.REPO) / "dist" / ".env")
    problems = launcher.paths_are_outside_the_bundle()
    assert problems and "token" in problems[0]


def test_a_database_outside_the_bundle_but_not_the_installations_is_refused(monkeypatch):
    """"Outside the bundle" is necessary but NOT sufficient, and this is the
    check that was missing.

    The frozen build fell back to `~/.gridiron/gridiron.db` — outside the
    bundle, so the original check passed it — while the scheduled tasks went on
    writing `var/gridiron.db`. The window would have opened onto an empty record
    and nothing anywhere would have said why. Found by building the exe and
    watching it answer 503, not by reasoning about it.
    """
    from gridiron import config

    monkeypatch.setattr(config, "DB_PATH", Path.home() / ".gridiron" / "gridiron.db")
    problems = launcher.paths_are_outside_the_bundle()
    assert problems, "a database outside the installation was accepted"
    assert "empty project" in problems[0] or "record at" in problems[0]


def test_the_frozen_server_is_always_given_real_stdio():
    """A console=False frozen build has no stdout handle; the first log line
    kills it, and the symptom is an exe that exits 1 having bound nothing."""
    source = Path(launcher.__file__).read_text(encoding="utf-8")
    start = source[source.index("def start_server"):source.index("def wait_for_health")]
    assert "stdout=handle" in start and "stderr=handle" in start


def test_the_child_inherits_the_installation():
    """The server subprocess must be pinned to the same installation, or it
    resolves its own paths and quietly uses a different database."""
    source = Path(launcher.__file__).read_text(encoding="utf-8")
    start = source[source.index("def start_server"):source.index("def wait_for_health")]
    assert "GRIDIRON_HOME" in start


def test_window_state_lives_outside_the_repository():
    """Geometry belongs with the user's application state, not in the bundle: a
    window that forgets where it was on every rebuild reads as a broken app."""
    assert "APPDATA" in str(launcher.STATE_DIR) or str(Path.home()) in str(
        launcher.STATE_DIR
    )
    assert "dist" not in launcher.STATE_DIR.parts


# --- attach first -----------------------------------------------------------

def test_an_unheld_port_reads_as_closed():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    assert launcher.port_is_open(free) is False


def test_a_port_held_by_something_else_is_not_mistaken_for_gridiron():
    """An open port is not enough. Something else may hold 8848, and attaching
    to it would produce a window onto a stranger's process."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        assert launcher.port_is_open(port) is True
        assert launcher.gridiron_is_healthy(port, timeout=1.0) is False
    finally:
        listener.close()


def test_health_is_judged_on_shape_not_just_a_response(monkeypatch):
    """`/api/health` returns a known shape. Anything else is not our app."""
    import urllib.request

    class Fake:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Fake({"ok": True}))
    assert launcher.gridiron_is_healthy(1) is False, "a body with no version passed"

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: Fake({"ok": True, "version": "0.1.0"})
    )
    assert launcher.gridiron_is_healthy(1) is True


# --- the handoff ------------------------------------------------------------

def test_the_opened_url_never_carries_the_token(db_path, monkeypatch):
    from gridiron import api, auth

    monkeypatch.setenv(auth.TOKEN_VAR, "launcher-test-token")
    monkeypatch.setattr(api.config, "DB_PATH", db_path)
    url = launcher.signed_in_url(8848)
    assert "launcher-test-token" not in url
    assert "token" not in url.lower()
    assert "/auth/handoff?n=" in url
    api.set_database(None)


def test_with_no_token_the_launcher_opens_the_plain_root(db_path, monkeypatch):
    """Not a crash and not a blank window: the middleware sends it to a page
    that says what to run."""
    from gridiron import api, auth

    monkeypatch.delenv(auth.TOKEN_VAR, raising=False)
    monkeypatch.setattr(auth, "ENV_FILE", db_path.parent / "absent.env")
    monkeypatch.setattr(api.config, "DB_PATH", db_path)
    assert launcher.signed_in_url(8848) == "http://127.0.0.1:8848/"
    api.set_database(None)


# --- geometry ---------------------------------------------------------------

def test_geometry_falls_back_rather_than_failing(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "GEOMETRY_FILE", tmp_path / "nothing.json")
    assert launcher.load_geometry() == launcher.DEFAULT_GEOMETRY


def test_a_corrupt_geometry_file_does_not_stop_the_app(monkeypatch, tmp_path):
    bad = tmp_path / "window.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(launcher, "GEOMETRY_FILE", bad)
    assert launcher.load_geometry() == launcher.DEFAULT_GEOMETRY


def test_an_absurd_remembered_size_is_clamped(monkeypatch, tmp_path):
    """A window remembered at 40000px is a window the user cannot find."""
    saved = tmp_path / "window.json"
    saved.write_text(json.dumps({"width": 99999, "height": 1}), encoding="utf-8")
    monkeypatch.setattr(launcher, "GEOMETRY_FILE", saved)
    geometry = launcher.load_geometry()
    assert 480 <= geometry["width"] <= 6000
    assert 400 <= geometry["height"] <= 4000


# --- the launcher stays out of the appliance's way --------------------------

def test_the_launcher_never_touches_a_scheduled_task():
    """The appliance and the viewer are separate things, and the viewer is the
    disposable one. Closing the window must never stop the record being kept, so
    the launcher does not read, write, start, stop or inspect any task."""
    source = Path(launcher.__file__).read_text(encoding="utf-8")
    code = "\n".join(
        line.split("#", 1)[0] for line in source.splitlines()
    )
    for forbidden in ("schtasks", "ScheduledTask", "Register-Scheduled",
                      "Unregister-Scheduled", "Start-ScheduledTask"):
        assert forbidden not in code, (
            f"the launcher references {forbidden!r}: closing a window must not "
            "be able to affect whether the record keeps itself"
        )


def test_the_launcher_binds_only_loopback():
    source = Path(launcher.__file__).read_text(encoding="utf-8")
    assert 'HOST = "127.0.0.1"' in source
    assert "0.0.0.0" not in source


def test_the_spec_ships_no_database_and_no_token():
    """The bundle carries the interface and the schema. Not the record."""
    spec = (Path(launcher.REPO) / "desktop" / "gridiron.spec").read_text(encoding="utf-8")
    datas = spec[spec.index("datas=["):spec.index("hiddenimports=")]
    assert "web" in datas and "schema.sql" in datas
    for forbidden in (".env", "gridiron.db", "var"):
        assert forbidden not in datas, f"the bundle would ship {forbidden}"
    # ONEDIR is asserted on the CODE, not the prose. The spec explains at
    # length why onefile is refused, and an earlier version of this test caught
    # its own explanation — a check that reads comments is a check that fails
    # when somebody documents a decision well.
    code = chr(10).join(line.split("#", 1)[0] for line in spec.splitlines())
    assert "COLLECT(" in code, "not a onedir build"
    assert "exclude_binaries=True" in code, "not a onedir build"
    assert "onefile" not in code.lower()
