"""Desktop launcher for Gridiron.

Four properties, in the order they matter:

**Attach first.** If a healthy Gridiron is already serving on the port, this
opens a window onto it and starts nothing. Two servers on one SQLite file is a
lock fight nobody asked for, and the second one silently failing is worse.

**Health gated.** The window is not opened until `/api/health` answers ok. A
browser pointed at a port that is not listening yet shows a connection error the
user then has to reload past, which teaches them to distrust the app.

**Loud failure.** If the server does not come up, this prints the captured
traceback and reason, shows a native dialog on Windows, and exits non-zero. It
never opens a window onto nothing and never exits 0 on a failure.

**Geometry remembered.** The app window runs in its own browser profile under
the state directory, so Chromium remembers its size and position across
launches. The last known placement is mirrored into `launcher.json` so the
fallback path and `--status` can report and reuse it.

Usage:
    python desktop/launcher.py
    python desktop/launcher.py --status
    python desktop/launcher.py --attach-only
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gridiron import config  # noqa: E402

# The launcher keeps its window profile beside whatever state directory the
# package chose, so a frozen build and a source checkout do not disagree about
# where "here" is.
STATE_DIR = Path(os.environ.get("GRIDIRON_STATE") or (Path.home() / ".gridiron"))
PROFILE_DIR = STATE_DIR / "window-profile"
LAUNCHER_STATE = STATE_DIR / "launcher.json"

DEFAULT_GEOMETRY = {"width": 1180, "height": 900, "x": 60, "y": 40}
HEALTH_TIMEOUT_SECONDS = 25.0

CHROMIUM_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)


class LaunchFailure(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

def load_state() -> dict:
    try:
        return json.loads(LAUNCHER_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(**fields) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    state.update(fields)
    LAUNCHER_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def remembered_geometry() -> dict:
    """Chromium's own record of where the window was, with our file as fallback.

    The browser profile is the authority — it is what actually restores the
    window — and this reads it back so the value can be shown and reused.
    """
    preferences = PROFILE_DIR / "Default" / "Preferences"
    try:
        placement = (
            json.loads(preferences.read_text(encoding="utf-8"))
            .get("browser", {})
            .get("window_placement", {})
        )
        if placement:
            geometry = {
                "x": placement.get("left", DEFAULT_GEOMETRY["x"]),
                "y": placement.get("top", DEFAULT_GEOMETRY["y"]),
                "width": placement.get("right", 0) - placement.get("left", 0)
                or DEFAULT_GEOMETRY["width"],
                "height": placement.get("bottom", 0) - placement.get("top", 0)
                or DEFAULT_GEOMETRY["height"],
                "maximized": placement.get("maximized", False),
                "source": "browser profile",
            }
            return geometry
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    saved = load_state().get("geometry")
    if saved:
        return {**saved, "source": "launcher.json"}
    return {**DEFAULT_GEOMETRY, "source": "default"}


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

def probe(port: int, timeout: float = 1.5) -> dict | None:
    """Ask a possible server whether it is a healthy Gridiron."""
    try:
        with urllib.request.urlopen(
            f"http://{config.HOST}:{port}/api/health", timeout=timeout
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload if payload.get("ok") else None
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def wait_for_health(port: int, deadline: float, server_error: list) -> dict:
    while time.time() < deadline:
        if server_error:
            raise LaunchFailure(
                "the server thread died before it became healthy:\n\n"
                + "".join(server_error)
            )
        payload = probe(port, timeout=1.0)
        if payload:
            return payload
        time.sleep(0.25)
    raise LaunchFailure(
        f"/api/health did not answer within {HEALTH_TIMEOUT_SECONDS:.0f}s on port {port}. "
        "The window was not opened, because a window onto a dead server is worse "
        "than no window."
    )


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------

def start_server(port: int, database: str | None) -> list:
    """Run uvicorn on a daemon thread. Returns a list that receives the
    traceback if it dies, which is what makes the failure loud rather than a
    hang."""
    errors: list = []

    def run() -> None:
        try:
            import uvicorn

            from gridiron import api

            api.set_database(database or config.DB_PATH)
            uvicorn.run(api.app, host=config.HOST, port=port, log_level="warning")
        except BaseException:  # noqa: BLE001 - the traceback is the product here
            errors.append(traceback.format_exc())

    threading.Thread(target=run, name="gridiron-server", daemon=True).start()
    return errors


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def find_browser() -> str | None:
    for candidate in CHROMIUM_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ("msedge", "chrome", "chromium", "brave", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def open_window(url: str, geometry: dict) -> str:
    """Open the app window. Returns a description of how it was opened."""
    browser = find_browser()
    if browser is None:
        import webbrowser

        webbrowser.open(url)
        return "default browser (no Chromium found; geometry not applied)"

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        browser,
        f"--app={url}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    # Only impose geometry when the profile has nothing of its own to restore;
    # after that the browser's memory is the better answer.
    if geometry.get("source") == "default":
        args += [
            f"--window-size={geometry['width']},{geometry['height']}",
            f"--window-position={geometry['x']},{geometry['y']}",
        ]
    subprocess.Popen(args, close_fds=True)
    return f"{Path(browser).name} app window (profile at {PROFILE_DIR})"


def shout(title: str, message: str, *, allow_dialog: bool = True) -> None:
    """Fail where the user can actually see it.

    From a terminal the banner on stderr is the loud failure, and a modal dialog
    would only block a script waiting for a click nobody is there to give. With
    no console attached - a desktop shortcut, a frozen build - stderr goes
    nowhere, so the dialog is the only way the failure is visible at all.
    """
    banner = "=" * 68
    print(os.linesep.join(["", banner, title, banner, message, banner]),
          file=sys.stderr, flush=True)

    has_console = bool(getattr(sys.stderr, "isatty", lambda: False)())
    if not allow_dialog or has_console or os.environ.get("GRIDIRON_NO_DIALOG"):
        return
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(
                None, message[:1500], f"Gridiron - {title}", 0x10
            )
        except Exception:  # noqa: BLE001 - a missing dialog must not mask the error
            pass


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch Gridiron")
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--database", default=None)
    parser.add_argument("--attach-only", action="store_true",
                        help="attach to a running server; never start one")
    parser.add_argument("--no-window", action="store_true",
                        help="serve and health-gate, but open no window")
    parser.add_argument("--status", action="store_true",
                        help="report what is running and what geometry is remembered")
    parser.add_argument("--no-dialog", action="store_true",
                        help="never show a modal error dialog (for automation)")
    args = parser.parse_args(argv)

    geometry = remembered_geometry()

    if args.status:
        running = probe(args.port)
        print(json.dumps({
            "port": args.port,
            "running": running is not None,
            "health": running,
            "state_dir": str(STATE_DIR),
            "remembered_geometry": geometry,
            "last_launch": load_state().get("last_launch_utc"),
        }, indent=2))
        return 0

    url = f"http://{config.HOST}:{args.port}/"

    # --- attach first ------------------------------------------------------
    existing = probe(args.port)
    if existing:
        print(f"Gridiron already healthy on port {args.port}; attaching.")
        if not args.no_window:
            print("  window:", open_window(url, geometry))
        save_state(
            last_launch_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            mode="attached",
            port=args.port,
            geometry={k: geometry[k] for k in ("x", "y", "width", "height")},
        )
        return 0

    if args.attach_only:
        shout(
            "nothing to attach to",
            f"No healthy Gridiron is serving on port {args.port}, and --attach-only "
            "was given, so no server was started.",
            allow_dialog=not args.no_dialog,
        )
        return 3

    # --- start, then gate on health ---------------------------------------
    print(f"Starting Gridiron on {url}")
    errors = start_server(args.port, args.database)
    try:
        health = wait_for_health(
            args.port, time.time() + HEALTH_TIMEOUT_SECONDS, errors
        )
    except LaunchFailure as exc:
        shout("failed to start", str(exc), allow_dialog=not args.no_dialog)
        return 2

    print(f"  healthy: {health}")
    if not args.no_window:
        print("  window:", open_window(url, geometry))
    save_state(
        last_launch_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        mode="started",
        port=args.port,
        database=health.get("database"),
        geometry={k: geometry[k] for k in ("x", "y", "width", "height")},
    )

    if args.no_window:
        return 0

    print("\nGridiron is running. Close this window or press Ctrl+C to stop the server.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
