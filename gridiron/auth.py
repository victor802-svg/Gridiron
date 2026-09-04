"""Access control for a personal appliance.

The threat model is small and worth stating, because security written without
one is decoration. Gridiron binds 127.0.0.1 and, in P4, is published to a
private tailnet. It holds no money and no personal data. What it holds is a
RECORD — an append-only forecasting history whose value is entirely in nobody
having been able to touch it. So the job here is: keep the record private on a
network where other devices exist, and make sure a device that has not proved it
holds the token sees nothing at all.

Four decisions worth reading:

**The token never reaches the browser.** It is compared server-side and
exchanged for a session id. A token in a cookie is a token in every request log,
every screenshot, and every `document.cookie` read.

**The cookie is HttpOnly and SameSite=Strict, set by the SERVER.** JavaScript
cannot set an HttpOnly cookie — `document.cookie` silently ignores the flag and
you end up with a readable cookie that looks right. The handoff is therefore a
real POST that the server answers with a `Set-Cookie`.

**Failures are stored, not counted in memory.** A restart must not be the way
around the backoff, and a failed sign-in nobody records is one nobody notices.

**`/api/health` is liveness only.** It answers before authentication so a
monitor can see the process is up, which means it must carry no data at all —
not counts, not staleness, not the database path. Everything it used to carry
moved behind the gate.
"""

from __future__ import annotations

import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

#: Where the token lives. Read at request time rather than import time so
#: `make_token.py` does not require a restart to take effect.
#: Beside the installation, NOT beside the package. A frozen build's
#: REPO_ROOT is the extraction directory, so this used to look inside the
#: bundle and find nothing.
ENV_FILE = config.HOME / ".env"
TOKEN_VAR = "GRIDIRON_ACCESS_TOKEN"

COOKIE_NAME = "gridiron_session"
SESSION_HOURS = 24 * 30

#: Paths that answer WITHOUT a session. Deliberately tiny, and each one earns
#: its place:
#:   /api/health   liveness for a monitor; carries no data
#:   /login        the page you must be able to see in order to sign in
#:   /auth/login   the POST that signs you in
#:   /auth/handoff the desktop launcher's single-use nonce exchange
#:   /static/login.css, /static/app.css  so the login page is not unstyled
OPEN_PATHS = frozenset({
    "/api/health",
    # THE SIGN-IN SCREEN'S OWN NUMBERS (GRIDIRON_13 P6). Counts and records
    # only -- `audit.check_the_login_page_shows_no_pick` refuses a side, a
    # probability, a team with a line and a rate, and it runs inside the view
    # rather than at the route, so there is no way to serve one.
    "/api/login-glance",
    "/login",
    "/auth/login",
    "/auth/handoff",
    "/favicon.ico",
    # The service worker is the app SHELL. It must be fetchable before a session
    # exists or it can never install, and it carries no data: a guard in
    # `audit.check_no_offline_data_caching` is what keeps that true.
    "/sw.js",
    "/static/manifest.webmanifest",
})

#: Backoff after this many failures from one address, doubling each time.
FAILURES_BEFORE_BACKOFF = 3
BACKOFF_BASE_SECONDS = 2
BACKOFF_MAX_SECONDS = 300
#: Failures older than this stop counting, so one bad evening is not permanent.
FAILURE_WINDOW_MINUTES = 30


class NotConfigured(RuntimeError):
    """No access token has been created yet."""


# ---------------------------------------------------------------------------
# the token
# ---------------------------------------------------------------------------

def read_token() -> str | None:
    """The configured token, from the environment or `.env`.

    Never logged and never returned to a client. The only thing done with it is
    a constant-time comparison.
    """
    # ONE PARSER. This function used to carry its own, which is how `.env`
    # came to be a file that held exactly one recognised name: anything else
    # written in it was read by nothing. `config.setting` reads the whole file
    # and keeps the same precedence -- process environment first.
    #
    # Re-read rather than using the value cached at import, because the token
    # can be rotated while the server is running and the next request should
    # see the new one.
    from_env = os.environ.get(TOKEN_VAR)
    if from_env:
        return from_env.strip() or None
    return config.read_env_file(ENV_FILE).get(TOKEN_VAR) or None


# ---------------------------------------------------------------------------
# CSRF, per form (GRIDIRON_13 P3)
# ---------------------------------------------------------------------------
#
# The session cookie is SameSite=Strict, which already refuses a cross-site
# POST in every browser that honours it. This is the second lock, and it is
# here because the first one is a promise made by somebody else's software:
# a settings write changes when the appliance runs, and "the browser will not
# send the cookie" is not a sentence this project wants to be the whole of its
# defence.
#
# DERIVED FROM THE SESSION, not stored. A token table would be a third thing
# to expire and clean up; an HMAC of the session id under the access token is
# stateless, unforgeable without the token, and dies with the session.

CSRF_HEADER = "X-Gridiron-Form"


def csrf_token(session_id: str | None) -> str | None:
    """The form token for this session. None when there is no session."""
    secret = read_token()
    if not session_id or not secret:
        return None
    return hmac.new(secret.encode("utf-8"), session_id.encode("utf-8"),
                    "sha256").hexdigest()[:32]


def csrf_is_valid(session_id: str | None, candidate: str | None) -> bool:
    expected = csrf_token(session_id)
    if not expected or not candidate:
        return False
    return hmac.compare_digest(expected, candidate)


def token_matches(candidate: str) -> bool:
    """Constant-time comparison. `==` on a secret leaks its prefix through
    timing, which is a small leak on a fast local network and a free one to
    avoid."""
    token = read_token()
    if not token or not candidate:
        return False
    return hmac.compare_digest(token, candidate)


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)


def create_session(conn: sqlite3.Connection, *, user_agent: str | None = None) -> str:
    session_id = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (id, created_utc, expires_utc, user_agent)"
        " VALUES (?,?,?,?)",
        (
            session_id,
            _iso(_now()),
            _iso(_now() + timedelta(hours=SESSION_HOURS)),
            (user_agent or "")[:200],
        ),
    )
    conn.commit()
    return session_id


#: How much of the window has to have elapsed before a session is extended.
#: Writing on every request would be a write per page view for no benefit; a
#: tenth of the window means at most ten extensions across thirty days.
SLIDE_AFTER = 0.1


def session_is_valid(conn: sqlite3.Connection, session_id: str | None) -> bool:
    """Is this session live -- and if so, SLIDE it (GRIDIRON_13 P6).

    THIRTY DAYS FROM LAST USE, not from sign-in. A fixed expiry logs the
    operator out on a schedule that has nothing to do with whether they were
    using the app: open it every day for a month and it still throws you out
    on day thirty, at which point the token has to come out of wherever it is
    kept. Sliding means it expires only after a real absence.
    """
    if not session_id:
        return False
    row = conn.execute(
        "SELECT expires_utc FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    now = _now()
    if not row or row["expires_utc"] <= _iso(now):
        return False
    full = timedelta(hours=SESSION_HOURS)
    remaining = _parse(row["expires_utc"]) - now
    if remaining < full * (1 - SLIDE_AFTER):
        conn.execute(
            "UPDATE sessions SET expires_utc = ? WHERE id = ?",
            (_iso(now + full), session_id))
        conn.commit()
    return True


def drop_session(conn: sqlite3.Connection, session_id: str | None) -> None:
    if session_id:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()


def drop_all_sessions(conn: sqlite3.Connection) -> int:
    """Sign out everywhere. Returns how many devices were signed out.

    THE ANSWER TO "I LEFT IT OPEN SOMEWHERE". A thirty-day sliding session is
    convenient exactly because it does not expire while it is in use, which
    means a device left signed in stays signed in -- so the app has to offer
    the other half of that bargain. Rotating the token does the same thing,
    but this does not require the operator to have the token to hand.
    """
    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conn.execute("DELETE FROM sessions")
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------

def record_failure(conn: sqlite3.Connection, ip: str, reason: str) -> None:
    conn.execute(
        "INSERT INTO auth_failures (at_utc, ip, reason) VALUES (?,?,?)",
        (_iso(_now()), ip, reason),
    )
    conn.commit()


def backoff_seconds(conn: sqlite3.Connection, ip: str) -> int:
    """How long this address must wait before its next attempt is considered.

    Doubles per failure past the threshold and caps, so a wrong paste costs
    nothing and a script costs progressively more. Computed from stored rows so
    restarting the server does not reset it.
    """
    since = _iso(_now() - timedelta(minutes=FAILURE_WINDOW_MINUTES))
    row = conn.execute(
        "SELECT COUNT(*) AS n, MAX(at_utc) AS last FROM auth_failures"
        " WHERE ip = ? AND at_utc >= ?",
        (ip, since),
    ).fetchone()
    n = row["n"] or 0
    if n < FAILURES_BEFORE_BACKOFF or not row["last"]:
        return 0
    penalty = min(
        BACKOFF_BASE_SECONDS * (2 ** (n - FAILURES_BEFORE_BACKOFF)),
        BACKOFF_MAX_SECONDS,
    )
    elapsed = (_now() - datetime.strptime(row["last"], "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=timezone.utc)).total_seconds()
    return max(0, int(penalty - elapsed))


# ---------------------------------------------------------------------------
# the desktop handoff
# ---------------------------------------------------------------------------

def mint_handoff(conn: sqlite3.Connection, *, seconds: int = 60) -> str:
    """A single-use nonce so the launcher can open an authenticated browser.

    The TOKEN is never in a URL. This is not the token: it is a random value
    that is valid once, for a minute, and is useless the instant it is
    exchanged. That distinction is the whole reason it exists — without it the
    only way to open a signed-in browser is to put the secret in the address
    bar, where it lands in history.
    """
    nonce = secrets.token_urlsafe(24)
    conn.execute(
        "INSERT INTO handoff_nonces (nonce, created_utc, expires_utc)"
        " VALUES (?,?,?)",
        (nonce, _iso(_now()), _iso(_now() + timedelta(seconds=seconds))),
    )
    conn.commit()
    return nonce


def redeem_handoff(conn: sqlite3.Connection, nonce: str | None) -> bool:
    if not nonce:
        return False
    row = conn.execute(
        "SELECT expires_utc, used_utc FROM handoff_nonces WHERE nonce = ?", (nonce,)
    ).fetchone()
    if row is None or row["used_utc"] or row["expires_utc"] <= _iso(_now()):
        return False
    conn.execute(
        "UPDATE handoff_nonces SET used_utc = ? WHERE nonce = ?", (_iso(_now()), nonce)
    )
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def path_is_open(path: str) -> bool:
    """Whether a path answers without a session.

    Static assets are open because the login page needs its stylesheet, and a
    stylesheet reveals nothing. Every other path — including /docs, /redoc and
    /openapi.json, which describe the whole surface — is closed.

    `.woff2` JOINED 2026-09-04, with the fonts (operator ruling 4). It is the
    same argument one step further: the login page loads the stylesheet, the
    stylesheet asks for a font, and a font refused with a 401 leaves the sign-in
    screen drawn in a different face from the app behind it — while logging a
    console error on every visit, which is how the browser smoke test found
    this within an hour of the fonts landing.

    IT REVEALS LESS THAN THE STYLESHEET DOES. `manrope-latin.woff2` is a
    licensed open font, byte-identical to the file Google serves to anyone who
    asks, and its SHA-256 is written down in this repository. A stylesheet at
    least describes the shape of the interface; a font describes the shape of
    the letter "a".

    THE LIST STAYS AN EXTENSION ALLOWLIST, not a directory one. `/static/` also
    holds `app.js` and `index.html`, and neither is open — which is the whole
    reason this is written as "these extensions" rather than "this folder".
    """
    if path in OPEN_PATHS:
        return True
    return (path.startswith("/static/")
            and path.endswith((".css", ".ico", ".svg", ".woff2")))
