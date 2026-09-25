"""P3: the gate.

The test that matters most is `test_every_route_is_closed`, and it matters
because it is ENUMERATED FROM THE APP rather than written by hand. A hand-kept
list of protected routes is a list that goes stale the first time someone adds
an endpoint, and it goes stale silently — the suite stays green while the new
route serves the record to anyone who asks. Walking `app.routes` means a route
added tomorrow is tested tomorrow, with no one remembering to do anything.

The second is `test_the_session_cookie_is_httponly`. `document.cookie` accepts
the HttpOnly flag and silently drops it, so a cookie set from JavaScript looks
correct in any test that only checks the name is present. The flag is asserted
directly on the Set-Cookie header.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from gridiron import api, auth

TOKEN = "test-token-not-the-real-one"


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv(auth.TOKEN_VAR, TOKEN)
    api.set_database(db_path)
    with TestClient(api.app) as c:
        yield c
    api.set_database(None)


class ManualClock:
    """A clock that moves only when a test moves it (schema ruling 5 of
    2026-09-24: "The auth backoff test takes an injectable clock instead of
    wall time. No test in the gate may depend on elapsed real time").

    IT STARTS MONTHS IN THE PAST, on a whole second. A reading of the real
    clock that leaks into the code under test therefore does not flake -- it
    fails every time, because the real now is months past every stamp this
    clock wrote and no penalty survives that long.
    """

    def __init__(self, start: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock(monkeypatch):
    """Auth's clock, replaced by one the test moves by hand."""
    manual = ManualClock()
    monkeypatch.setattr(auth, "clock", manual)
    return manual


def _wrong(client):
    return client.post("/auth/login", json={"token": "wrong"})


def _routes():
    """Every path the app actually serves, taken from the app itself."""
    paths = []
    for route in api.app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set()) or set()
        if not path or "{" in path:
            continue
        if "GET" in methods:
            paths.append(path)
    return sorted(set(paths))


# --- everything is closed ---------------------------------------------------

def test_every_route_is_closed_to_an_unauthenticated_caller(client):
    """Enumerated from the app, not hardcoded. A route added tomorrow is
    covered tomorrow without anyone remembering to add it here."""
    leaked = []
    for path in _routes():
        if auth.path_is_open(path):
            continue
        response = client.get(path, headers={"accept": "application/json"})
        if response.status_code not in (401, 403):
            leaked.append(f"{path} -> {response.status_code}")
    assert not leaked, "these answered without a session: " + ", ".join(leaked)


def test_the_api_documentation_is_closed(client):
    """/api/docs and /openapi.json describe the whole surface, which is exactly
    what an unauthenticated caller should not be handed."""
    for path in ("/api/docs", "/openapi.json"):
        response = client.get(path, headers={"accept": "application/json"})
        assert response.status_code == 401, f"{path} answered {response.status_code}"


def test_a_browser_asking_for_a_page_is_sent_to_the_login_page(client):
    response = client.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_the_login_page_itself_is_reachable(client):
    assert client.get("/login").status_code == 200


# --- health is liveness only ------------------------------------------------

def test_health_answers_without_a_session(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_leaks_nothing(client):
    """The one open route must carry NO data: not the database path, not the
    record's kind, not counts, not staleness. An open endpoint that reports
    what is in the database is a data leak with a reassuring name."""
    body = client.get("/api/health").json()
    # `build` JOINED THE SHAPE ON 2026-09-02 (GRIDIRON_13 P6) and had to argue
    # for itself here, which is what this test is for. The launcher compares
    # the running server's build against its own before attaching, because
    # attaching to an older one opens an app that works perfectly and is not
    # the code that was built -- a photograph, with nothing on screen saying
    # so. A build identifier is the same class of thing as the version string
    # already here: it says which code is answering. It is not data ABOUT THE
    # RECORD, which is what the leak rule below is actually about.
    assert set(body) == {"ok", "version", "build"}
    blob = repr(body).lower()
    for leak in ("database", "path", ".db", "kind", "sport", "stale", "n="):
        assert leak not in blob, f"/api/health leaked {leak!r}: {body}"


def test_health_does_not_return_an_exception_message(client, monkeypatch):
    """A sqlite error carries the full database path."""
    def boom():
        raise RuntimeError("unable to open database file: C:/secret/path.db")

    monkeypatch.setattr(api, "get_conn", boom)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert response.json() == {"ok": False}


# --- signing in -------------------------------------------------------------

def test_the_right_token_opens_the_app(client):
    assert client.post("/auth/login", json={"token": TOKEN}).status_code == 200
    assert client.get("/api/sports").status_code == 200


def test_the_wrong_token_does_not(client):
    response = client.post("/auth/login", json={"token": "nope"})
    assert response.status_code == 401
    assert client.get("/api/sports",
                      headers={"accept": "application/json"}).status_code == 401


def test_the_session_cookie_is_httponly_strict_and_not_the_token(client):
    """HttpOnly is the flag JavaScript cannot set. SameSite=Strict is what stops
    another site's page from riding the session."""
    response = client.post("/auth/login", json={"token": TOKEN})
    header = response.headers["set-cookie"]
    assert "httponly" in header.lower()
    assert "samesite=strict" in header.lower().replace(" ", "")
    assert TOKEN not in header, "the token itself was handed to the browser"


def test_logging_out_ends_the_session(client):
    client.post("/auth/login", json={"token": TOKEN})
    assert client.get("/api/sports").status_code == 200
    client.post("/auth/logout")
    assert client.get("/api/sports",
                      headers={"accept": "application/json"}).status_code == 401


def test_an_unconfigured_appliance_refuses_rather_than_falls_open(db_path, monkeypatch):
    """No token configured is not 'unprotected by choice'. Serving the record to
    anyone who asks would be the worst possible default."""
    monkeypatch.delenv(auth.TOKEN_VAR, raising=False)
    monkeypatch.setattr(auth, "ENV_FILE", db_path.parent / "nonexistent.env")
    api.set_database(db_path)
    with TestClient(api.app) as c:
        response = c.get("/api/sports", headers={"accept": "application/json"})
        assert response.status_code == 503
        assert "make_token" in response.text
    api.set_database(None)


# --- rate limiting ----------------------------------------------------------

def test_repeated_failures_engage_a_backoff(client, clock):
    """ON THE TEST'S CLOCK, not the machine's (schema ruling 5, 2026-09-24).
    Before 2026-09-25 this asserted only a Retry-After above zero, and held
    while the stamp's fraction of a second plus one round trip stayed under
    a second. Now the penalty is exact, and it ends when the clock is moved
    past it, not when the machine happens to be slow."""
    for _ in range(auth.FAILURES_BEFORE_BACKOFF):
        assert _wrong(client).status_code == 401
    response = _wrong(client)
    assert response.status_code == 429
    assert response.headers["retry-after"] == str(auth.BACKOFF_BASE_SECONDS)
    clock.advance(auth.BACKOFF_BASE_SECONDS - 1)
    assert _wrong(client).headers["retry-after"] == "1", "one second is left"
    clock.advance(1)
    assert _wrong(client).status_code == 401, "the penalty outlived its clock"


def test_the_backoff_survives_a_restart(client, db_path, clock):
    """Held in the database, not in memory. A backoff you get past by
    restarting the process is not a backoff.

    THE TEST THAT FLAKED (2026-09-24, under the gate's load). With three
    failures the penalty is two seconds; the stamps are cut to whole seconds
    and the wait is rounded down, so the restart had at most one second of
    real time before the penalty ran out -- and a restart opens a fresh
    connection that runs the whole of `db.init`. Measured 2026-09-25: 0 of
    60 red idle, 3 of 3 red with a 1.1 s pause at the restart. On the manual
    clock the restart takes no time at all, however long the machine takes.
    """
    for _ in range(auth.FAILURES_BEFORE_BACKOFF + 1):
        _wrong(client)
    api.set_database(None)
    api.set_database(db_path)
    with TestClient(api.app) as fresh:
        refused = _wrong(fresh)
        assert refused.status_code == 429
        assert refused.headers["retry-after"] == str(auth.BACKOFF_BASE_SECONDS)
        clock.advance(auth.BACKOFF_BASE_SECONDS)
        assert _wrong(fresh).status_code == 401


def test_failures_older_than_the_window_stop_counting(client, clock):
    """"So one bad evening is not permanent": the window is measured on the
    same clock as the penalty."""
    for _ in range(auth.FAILURES_BEFORE_BACKOFF):
        _wrong(client)
    assert _wrong(client).status_code == 429
    clock.advance(auth.FAILURE_WINDOW_MINUTES * 60 + 1)
    assert _wrong(client).status_code == 401


def test_production_reads_the_real_clock():
    """The seam is for tests. Nothing in the package reassigns it, and the
    scan refuses a second reading of the real clock anywhere in auth."""
    from gridiron import audit

    assert auth.clock is auth._the_real_clock
    audit.check_auth_reads_one_clock()


def test_every_failure_is_logged(client):
    client.post("/auth/login", json={"token": "wrong"})
    conn = api.get_auth_conn()
    rows = conn.execute("SELECT * FROM auth_failures").fetchall()
    assert rows, "a failed sign-in was not recorded"
    assert rows[0]["reason"] == "bad token"
    assert TOKEN not in repr([dict(r) for r in rows])


# --- the desktop handoff ----------------------------------------------------

def test_the_handoff_signs_a_browser_in_without_the_token_in_the_url(
        client, db_path, clock):
    from gridiron import db

    # ON THE TEST'S CLOCK (ruling 5): the nonce's minute is not spent by a
    # slow machine between minting it and redeeming it.
    nonce = auth.mint_handoff(db.open_db(db_path))
    assert TOKEN not in nonce
    response = client.get(f"/auth/handoff?n={nonce}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/sports").status_code == 200


def test_a_handoff_nonce_works_exactly_once(client, db_path, clock):
    from gridiron import db

    nonce = auth.mint_handoff(db.open_db(db_path))
    first = client.get(f"/auth/handoff?n={nonce}", follow_redirects=False)
    assert first.headers["location"] == "/", "the first use was refused"
    client.post("/auth/logout")
    second = client.get(f"/auth/handoff?n={nonce}", follow_redirects=False)
    assert second.headers["location"] == "/login"


def test_a_handoff_nonce_lasts_its_minute_and_no_longer(client, db_path, clock):
    """Sixty seconds on the clock, not on the machine: redeemed at 59 it signs
    in, and at 60 it is refused."""
    from gridiron import db

    conn = db.open_db(db_path)
    early, late = auth.mint_handoff(conn), auth.mint_handoff(conn)
    clock.advance(59)
    assert client.get(f"/auth/handoff?n={early}",
                      follow_redirects=False).headers["location"] == "/"
    clock.advance(1)
    assert client.get(f"/auth/handoff?n={late}",
                      follow_redirects=False).headers["location"] == "/login"


def test_an_expired_handoff_nonce_is_refused(client, db_path):
    from gridiron import db

    nonce = auth.mint_handoff(db.open_db(db_path), seconds=-1)
    response = client.get(f"/auth/handoff?n={nonce}", follow_redirects=False)
    assert response.headers["location"] == "/login"


def test_the_handoff_url_never_contains_the_token(db_path, monkeypatch):
    """Asserted against the CONFIGURED token, not the fixture's constant.

    The first version of this test checked that a token it had never installed
    was absent from the URL, which is true of any string and proves nothing. A
    test that cannot fail is worse than no test: it occupies the place where a
    real one would go.
    """
    monkeypatch.setenv(auth.TOKEN_VAR, TOKEN)
    api.set_database(db_path)
    url = api.desktop_handoff_url()
    assert url is not None
    configured = auth.read_token()
    assert configured == TOKEN, "the test is not checking the live token"
    assert configured not in url
    assert "token" not in url.lower()
    api.set_database(None)


def test_no_token_means_no_handoff_url(db_path, monkeypatch):
    monkeypatch.delenv(auth.TOKEN_VAR, raising=False)
    monkeypatch.setattr(auth, "ENV_FILE", db_path.parent / "nonexistent.env")
    api.set_database(db_path)
    assert api.desktop_handoff_url() is None
    api.set_database(None)
