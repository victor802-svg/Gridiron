"""The desktop launcher.

ATTACH FIRST. If a healthy Gridiron is already listening, this opens a window
onto it and starts nothing. Two servers on one database is how a personal
appliance ends up with a locked SQLite file and a record that stops growing, and
the second copy is invisible — it looks like the app simply opened.

STARTED-BY-US BOOKKEEPING decides what happens on close. If this process started
the server, closing the window stops it. If it attached to one that was already
running — from a terminal, or from another window — closing leaves it alone.
Killing a server somebody else started is the kind of surprise that makes a tool
untrustworthy.

THE SCHEDULED TASKS DO NOT NEED THIS. `Gridiron-Resolve` and the three predict
tasks invoke `python -m gridiron.cli task ...` directly against the database.
They do not talk to the server, they do not need a window, and closing this one
never stops the record from being kept. The launcher deliberately does not read,
write, start, stop or inspect any scheduled task: the appliance and the viewer
are separate things, and the viewer is the disposable one.

127.0.0.1 ALWAYS. `api.serve` refuses any other host, and this passes none.
Reaching Gridiron from a phone is `tailscale serve` (see tools/phone_setup.ps1),
which puts a TLS listener in front of the loopback socket rather than opening
one to the network.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _pin_installation() -> Path:
    """Point this process at the installation, BEFORE gridiron.config is imported.

    A frozen build resolves its package root inside the bundle, so without this
    it looks for `.env` in the extraction directory (found: nothing, answered
    503) and falls back to `~/.gridiron` for the database — a different, empty
    record, while the scheduled tasks go on filling the real one. The window
    would have shown an empty project and nothing would have said why.
    """
    home = Path(
        os.environ.get("GRIDIRON_HOME")
        or (Path(sys.executable).resolve().parent
            if getattr(sys, "frozen", False) else REPO)
    )
    # A frozen exe sits in dist/Gridiron/, so the installation is two up.
    if getattr(sys, "frozen", False) and (home.parent.parent / "gridiron").is_dir():
        home = home.parent.parent
    os.environ["GRIDIRON_HOME"] = str(home)
    return home


HOME = _pin_installation()

HOST = "127.0.0.1"
DEFAULT_PORT = 8848
HEALTH_TIMEOUT = 30.0
LOG_TAIL_LINES = 15

#: Window geometry lives beside the user's other application state, NOT in the
#: bundle. A rebuild replaces dist/ wholesale, and a window that forgets where
#: it was every time the app is rebuilt is a small daily annoyance that reads as
#: the app being broken.
STATE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Gridiron"
GEOMETRY_FILE = STATE_DIR / "window.json"
LOG_FILE = STATE_DIR / "launcher.log"

DEFAULT_GEOMETRY = {"width": 1280, "height": 900, "x": None, "y": None}


# ---------------------------------------------------------------------------
# where things live
# ---------------------------------------------------------------------------

def bundle_root() -> Path | None:
    """The PyInstaller extraction directory, or None when running from source."""
    return Path(sys._MEIPASS) if getattr(sys, "frozen", False) else None


def repo_root() -> Path:
    """The working directory the server runs in.

    When frozen, this is the directory the executable was launched from — set by
    the shortcut — NOT the bundle. That distinction is the whole reason the
    record survives a rebuild.
    """
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("GRIDIRON_HOME", Path(sys.executable).resolve().parent))
    return REPO


def database_path() -> Path:
    """Where the record lives. MUST resolve outside any bundle directory.

    A database inside dist/ is a database that a rebuild deletes, and the record
    is the only thing in this project that cannot be regenerated. A test asserts
    this path is not under dist/ or under the PyInstaller extraction directory.
    """
    from gridiron import config

    return Path(config.DB_PATH).resolve()


def env_path() -> Path:
    """Where the access token lives. Outside the bundle for the same reason: a
    rebuild must not silently sign every device out."""
    from gridiron import auth

    return Path(auth.ENV_FILE).resolve()


def paths_are_outside_the_bundle() -> list[str]:
    """Every path that must survive a rebuild, checked. Returns what is wrong.

    "Outside the bundle" is NECESSARY BUT NOT SUFFICIENT, and the insufficiency
    was found the hard way. A frozen build fell back to `~/.gridiron` for its
    database — outside the bundle, so this check passed — while the scheduled
    tasks went on writing `var/gridiron.db`. The window would have opened onto
    an empty record with nothing anywhere saying why. So it also checks the
    paths are the ones the INSTALLATION uses.
    """
    problems: list[str] = []
    bundle = bundle_root()
    for name, path in (("database", database_path()), ("token file", env_path())):
        if "dist" in path.parts:
            problems.append(f"the {name} resolves inside dist/: {path}")
        if bundle is not None:
            try:
                path.relative_to(bundle)
            except ValueError:
                pass
            else:
                problems.append(f"the {name} resolves inside the bundle: {path}")

    # The same record the CLI and the scheduler use, not merely a safe one.
    expected_db = (HOME / "var" / "gridiron.db").resolve()
    if database_path() != expected_db:
        problems.append(
            f"the database is {database_path()}, but this installation keeps its "
            f"record at {expected_db}. A window onto a different database shows "
            "an empty project while the scheduled tasks fill the real one."
        )
    expected_env = (HOME / ".env").resolve()
    if env_path() != expected_env:
        problems.append(
            f"the token file is {env_path()}, but this installation keeps it at "
            f"{expected_env}"
        )
    return problems


# ---------------------------------------------------------------------------
# attach first
# ---------------------------------------------------------------------------

def build_notice() -> str | None:
    """A line to print when this bundle has fallen behind the repository.

    Said HERE as well as in the footer, and both from `buildinfo.freshness()`
    so they cannot disagree. The launcher is where somebody looks when the app
    is behaving oddly, and "the app you are running was built from a commit
    four behind this checkout" is the answer often enough to be worth saying
    before the window opens rather than after they have hunted for it.
    """
    from gridiron import buildinfo, language

    fresh = buildinfo.freshness()
    if fresh.get("from_source") or not fresh.get("stale"):
        return None
    return language.build_line(fresh)


def running_build(port: int, timeout: float = 2.0) -> str | None:
    """Which build is answering on that port, or None if nothing is.

    `/api/health` carries the build for exactly this reason (GRIDIRON_13 P6):
    a caller has to know which code is answering before it can decide to trust
    it.
    """
    try:
        with urllib.request.urlopen(
            f"http://{HOST}:{port}/api/health", timeout=timeout
        ) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None
    build = body.get("build")
    return str(build) if build else None


#: Newlines for the dialogs. Written as names because an escape inside an
#: f-string in this file has twice been collapsed into a real line break by a
#: careless edit, which is a syntax error at import and stops the app opening.
NL = chr(10)
NL2 = NL + NL

#: What the launcher may do when it finds a server already listening.
ATTACH = "attach"
ASK = "ask"
RESTART = "restart"


def attach_decision(mine: str | None, theirs: str | None,
                    *, confirmed: bool = False) -> str:
    """Attach, ask, or restart -- decided here so it can be tested and planted.

    THE FAILURE THIS EXISTS TO END. The launcher attached to whatever was
    healthy on the port. When that was a server from an older build, the app
    opened, worked, and showed a PHOTOGRAPH: every screen rendered, nothing
    errored, and the code answering was not the code that had just been built.
    A stale bundle is the failure that does not look like one.

    SILENCE IS NOT AN OPTION ON MISMATCH. It returns ASK, and only a caller
    that has actually asked -- `confirmed=True` -- gets RESTART. There is no
    path from "the builds differ" to "attach anyway", which is what
    `audit.stale_attach_faults` checks by running this function rather than by
    reading the launcher's source.

    UNKNOWN IS NOT MISMATCH. A server too old to report a build at all, or a
    launcher that cannot read its own, attaches: refusing on missing
    information would make the app unopenable for a reason nobody could act
    on.
    """
    if not mine or not theirs:
        return ATTACH
    if mine == theirs:
        return ATTACH
    return RESTART if confirmed else ASK


def port_is_open(port: int, timeout: float = 0.4) -> bool:
    with socket.socket() as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((HOST, port)) == 0


def gridiron_is_healthy(port: int, timeout: float = 2.0) -> bool:
    """Whether what is on that port is OUR app and answering.

    An open port is not enough: something else may hold 8848. `/api/health` is
    the one route that answers without a session, which is exactly what makes it
    usable here, and it returns a known shape.
    """
    try:
        with urllib.request.urlopen(
            f"http://{HOST}:{port}/api/health", timeout=timeout
        ) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return bool(body.get("ok")) and "version" in body


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------

def load_geometry() -> dict:
    try:
        saved = json.loads(GEOMETRY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_GEOMETRY)
    geometry = dict(DEFAULT_GEOMETRY)
    for key in geometry:
        if isinstance(saved.get(key), int):
            geometry[key] = saved[key]
    # A window remembered off-screen is a window the user cannot find.
    geometry["width"] = max(480, min(geometry["width"], 6000))
    geometry["height"] = max(400, min(geometry["height"], 4000))
    return geometry


def save_geometry(geometry: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        GEOMETRY_FILE.write_text(json.dumps(geometry, indent=1), encoding="utf-8")
    except OSError:
        pass


def browser_command(url: str, geometry: dict) -> list[str] | None:
    """A Chromium app window if one is installed, else None for the default browser.

    `--app=` gives a window with no tabs, no address bar and its own taskbar
    entry, which is as close to a native window as this gets without adding a
    GUI toolkit and a webview runtime to a project that has neither. The URL
    carries a single-use handoff nonce, never the token.
    """
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
        / "Microsoft/Edge/Application/msedge.exe",
    ]
    for exe in candidates:
        if exe.exists():
            args = [
                str(exe),
                f"--app={url}",
                f"--window-size={geometry['width']},{geometry['height']}",
                f"--user-data-dir={STATE_DIR / 'browser'}",
            ]
            if geometry["x"] is not None and geometry["y"] is not None:
                args.append(f"--window-position={geometry['x']},{geometry['y']}")
            return args
    return None


def open_window(url: str, geometry: dict) -> subprocess.Popen | None:
    command = browser_command(url, geometry)
    if command is None:
        import webbrowser

        webbrowser.open(url)
        return None
    return subprocess.Popen(command)


# ---------------------------------------------------------------------------
# failure, said out loud
# ---------------------------------------------------------------------------

def log_tail(lines: int = LOG_TAIL_LINES) -> str:
    try:
        return "\n".join(
            LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        )
    except OSError:
        return "(no launcher log)"


def error_dialog(title: str, message: str) -> None:
    """A native dialog, because a frozen app has no console to print to.

    Without this, a server that fails to start produces an executable that
    flashes and vanishes, which tells the user nothing at all.
    """
    body = f"{message}\n\nLast {LOG_TAIL_LINES} log lines:\n\n{log_tail()}"
    try:
        import tkinter as tk
        from tkinter import scrolledtext

        root = tk.Tk()
        root.title(title)
        root.geometry("760x420")
        text = scrolledtext.ScrolledText(root, wrap="word", font=("Consolas", 9))
        text.insert("1.0", body)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Button(root, text="Close", command=root.destroy, width=12).pack(pady=(0, 10))
        root.mainloop()
    except Exception:  # noqa: BLE001 - a dialog that cannot open must still report
        print(title + chr(10) + body, file=sys.stderr)


def ask_yes_no(title: str, message: str) -> bool:
    """A yes/no dialog. NO when it cannot ask.

    A frozen app has no console, so a question nobody can see must not be
    treated as agreement: refusing to restart leaves the operator with a
    working app and a printed line, which is recoverable. Silently stopping a
    server on the strength of a dialog that never opened is not.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(title, message)
        root.destroy()
        return bool(answer)
    except Exception:  # noqa: BLE001 - no display, no console, no assumption
        print(title + chr(10) + message + chr(10)
              + "(could not ask; leaving it running)", file=sys.stderr)
        return False


def _my_build() -> str | None:
    try:
        from gridiron import buildinfo

        return buildinfo.build_id()
    except Exception:  # noqa: BLE001 - an unknown build attaches, see the rule
        return None


def stop_server(port: int, timeout: float = 10.0) -> bool:
    """Stop whatever Gridiron is on that port, and wait until it is gone.

    ONLY AFTER THE OPERATOR SAID YES. `attach_decision` never returns RESTART
    without confirmation, so this is unreachable from an unattended path.
    """
    import subprocess as sp

    if sys.platform != "win32":
        return False
    found = sp.run(["netstat", "-ano"], capture_output=True, text=True,
                   timeout=timeout, stdin=sp.DEVNULL)
    pids = {
        line.split()[-1]
        for line in (found.stdout or "").splitlines()
        if f"{HOST}:{port}" in line and "LISTENING" in line
    }
    if not pids:
        return False
    for pid in pids:
        sp.run(["taskkill", "/PID", pid, "/F"], capture_output=True,
               text=True, timeout=timeout, stdin=sp.DEVNULL)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_is_open(port):
            return True
        time.sleep(0.3)
    return not port_is_open(port)


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

def start_server(port: int) -> subprocess.Popen:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    handle = LOG_FILE.open("a", encoding="utf-8")
    handle.write(f"\n--- launcher start {time.strftime('%Y-%m-%dT%H:%M:%SZ')} ---\n")
    handle.flush()

    if getattr(sys, "frozen", False):
        command = [sys.executable, "--serve-only", "--port", str(port)]
    else:
        command = [
            sys.executable, "-m", "gridiron.cli", "serve", "--port", str(port)
        ]
    # STDIO IS ALWAYS REDIRECTED, and it is not optional. A console=False
    # frozen build has no stdout handle at all; the first log line it writes
    # then kills the process, and what you see is an executable that starts,
    # binds nothing, and exits 1 with no message. Handing it a real file is
    # what makes the frozen server work.
    return subprocess.Popen(
        command, cwd=str(repo_root()), stdout=handle, stderr=handle,
        env={**os.environ, "GRIDIRON_HOME": str(HOME)},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def wait_for_health(port: int, deadline: float) -> bool:
    while time.time() < deadline:
        if gridiron_is_healthy(port):
            return True
        time.sleep(0.25)
    return False


def signed_in_url(port: int) -> str:
    """The URL to open: a one-time handoff when a token is configured.

    THE TOKEN IS NEVER IN THE URL AND NEVER LOGGED. The nonce is random, valid
    once, and expires in sixty seconds; redeeming it is what mints the session.
    With no token configured the plain root is opened, and the middleware sends
    the window to a page that explains what to run.
    """
    from gridiron import api, auth, config

    api.set_database(config.DB_PATH)
    if auth.read_token() is None:
        return f"http://{HOST}:{port}/"
    url = api.desktop_handoff_url(HOST, port)
    return url or f"http://{HOST}:{port}/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open Gridiron in a window.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--keep-running", action="store_true",
        help="leave the server running after the window closes, even if this "
             "launcher started it",
    )
    parser.add_argument(
        "--serve-only", action="store_true",
        help="run the server in the foreground; used by the frozen build to "
             "re-enter itself as a child process",
    )
    args = parser.parse_args(argv)

    if args.serve_only:
        from gridiron import api, config

        api.set_database(config.DB_PATH)
        api.serve(port=args.port, log_level="info")
        return 0

    # SAID BEFORE THE WINDOW OPENS. A stale bundle is the failure that does
    # not look like one -- everything works and the screen is a photograph --
    # so the launcher says it where somebody looks when the app seems odd.
    stale = build_notice()
    if stale:
        print(f"Gridiron: {stale}")

    problems = paths_are_outside_the_bundle()
    if problems:
        error_dialog(
            "Gridiron — refusing to start",
            "The record or the token would live inside the application bundle, "
            "where a rebuild would delete it:\n  " + "\n  ".join(problems),
        )
        return 2

    # --- attach first ------------------------------------------------------
    started_by_us = False
    server: subprocess.Popen | None = None

    if gridiron_is_healthy(args.port):
        # WHOSE BUILD IS THAT? (GRIDIRON_13 P6.) Attaching to a server from an
        # older build opens an app that works perfectly and is not the code
        # that was just built -- and nothing on screen says so.
        mine = _my_build()
        theirs = running_build(args.port)
        decision = attach_decision(mine, theirs)
        if decision == ASK:
            confirmed = ask_yes_no(
                "Gridiron - an older build is running",
                "A Gridiron from a different build is already listening on "
                f"{HOST}:{args.port}." + NL2
                + f"  running: {theirs}" + NL
                + f"  this one: {mine}" + NL2
                + "Attaching to it would open an app that works and is not "
                  "the code you just built. Stop it and start this one?")
            decision = attach_decision(mine, theirs, confirmed=confirmed)
        if decision == RESTART:
            if not stop_server(args.port):
                error_dialog(
                    "Gridiron - could not stop the older server",
                    f"The server on {HOST}:{args.port} did not stop. Close it "
                    f"yourself, or start this build on another port with "
                    f"--port.")
                return 2
            server = start_server(args.port)
            started_by_us = True
            if not wait_for_health(args.port, time.time() + HEALTH_TIMEOUT):
                server.terminate()
                error_dialog(
                    "Gridiron - the server did not start",
                    f"No healthy response from "
                    f"http://{HOST}:{args.port}/api/health within "
                    f"{HEALTH_TIMEOUT:.0f} seconds.")
                return 1
        else:
            print(f"attaching to the Gridiron already on {HOST}:{args.port}")
    elif port_is_open(args.port):
        error_dialog(
            "Gridiron — port in use",
            f"Something is listening on {HOST}:{args.port} but it is not "
            "Gridiron: /api/health did not answer as expected. Close whatever "
            "holds the port, or start Gridiron on another one with --port.",
        )
        return 2
    else:
        server = start_server(args.port)
        started_by_us = True
        if not wait_for_health(args.port, time.time() + HEALTH_TIMEOUT):
            server.terminate()
            error_dialog(
                "Gridiron — the server did not start",
                f"No healthy response from http://{HOST}:{args.port}/api/health "
                f"within {HEALTH_TIMEOUT:.0f} seconds.",
            )
            return 1

    geometry = load_geometry()
    window = open_window(signed_in_url(args.port), geometry)
    save_geometry(geometry)

    # A server we ATTACHED to belongs to somebody else, and somebody else can
    # stop it. When that happened the window was already open and simply went
    # blank: no error, no title, nothing to act on. Re-checking here converts a
    # silent blank page into a sentence that names the cause.
    if window is not None and not started_by_us:
        time.sleep(1.5)
        if not gridiron_is_healthy(args.port):
            error_dialog(
                "Gridiron — the server it attached to has gone",
                f"This launcher found a Gridiron already running on {HOST}:"
                f"{args.port} and opened a window onto it, but that server has "
                "since stopped. The window will be blank. "
                "Close the window and open Gridiron again: with nothing on the "
                "port, this launcher will start its own server.",
            )

    if window is None:
        # The default browser was used, so there is no window to wait on. Leave
        # the server up: there is no reliable way to know when the user is done.
        print("opened in the default browser; leaving the server running")
        return 0

    try:
        window.wait()
    except KeyboardInterrupt:
        pass

    if server is not None and started_by_us and not args.keep_running:
        # Ours to stop, so stop it. A server nobody asked for outliving its
        # window is a background process the user cannot see or account for.
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        print("stopped the server this launcher started")
    elif started_by_us:
        print("leaving the server running (--keep-running)")
    else:
        print("leaving the server running: this launcher did not start it")

    # THE SCHEDULED TASKS ARE UNTOUCHED. They call the CLI directly against the
    # database and never needed the server; the record keeps itself whether this
    # window is open or not.
    return 0


if __name__ == "__main__":
    sys.exit(main())
