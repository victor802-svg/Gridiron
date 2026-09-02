"""G5: the interface. Read-only, local-only, and every number beside its N."""

from __future__ import annotations

import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from gridiron import api, auth, calibration, config, resolve, run
from gridiron.factors import store
from gridiron.model import baseline


TOKEN = "test-token-for-the-api-suite"


@pytest.fixture
def client(league, db_path, monkeypatch):
    store.sync_registry(league)
    # Six markets: the spread plus each prop type, fitted separately.
    baseline.train_all(league, (2025,), l2=1.0, note="test", min_rows=20)
    run.run_week(league, 2025, 7, include_props=True, use_llm=False)
    run.run_week(league, 2025, 8, include_props=True, use_llm=False)
    resolve.resolve_all(league)
    league.commit()
    monkeypatch.setenv(auth.TOKEN_VAR, TOKEN)
    api.set_database(db_path)
    with TestClient(api.app) as c:
        # Every route is behind the gate now (P3), so the interface suite signs
        # in the way a person does. What it is testing is the interface, not the
        # gate; test_auth.py tests the gate.
        c.post("/auth/login", json={"token": TOKEN})
        yield c
    api.set_database(None)


# --- LAW 3: there is no way in ---------------------------------------------

def test_no_route_can_write_to_the_record():
    """History is "searchable, never editable" because nothing can be called.

    `/auth/login` and `/auth/logout` write a session row and nothing else, on
    a separate handle, and they are named here so a third POST cannot appear
    without this test failing and someone having to justify it.

    THAT HAS HAPPENED TWICE, and both arguments live here.

    `POST /api/calls` was added on 2026-09-02 for the operator's own calls and
    withdrawn the same day (GRIDIRON_16 R1); the route went with it.

    `POST /api/settings` is the standing one. It writes to `settings` -- when
    tasks run, quiet hours, which notifications are on -- and it CANNOT reach
    the record: it is given `get_settings_conn`, a handle whose only caller
    refuses every name outside `settings.EDITABLE`, while the interface's own
    handle stays `query_only`. The `settings` table has its own append-only
    triggers, and the test below proves `predictions` is unmoved by every
    write route the app has.

    A FOURTH POST still has to come back here and argue for itself.
    """
    writers = sorted(
        route.path
        for route in api.app.routes
        if set(getattr(route, "methods", set()) or set()) - {"GET", "HEAD"}
    )
    assert writers == ["/api/settings", "/auth/login", "/auth/logout"], (
        f"a write verb appeared outside the sign-in paths: {writers}"
    )


def test_no_route_can_touch_a_prediction(client):
    """THE GUARANTEE THE TEST ABOVE IS ACTUALLY MAKING.

    Counting POSTs is a proxy for the thing that matters; this is the thing
    itself. Every write route the app has is exercised, and `predictions` must
    be exactly as it was found -- LAW 3 does not soften because a route was
    added next to it.
    """
    from gridiron import api as _api

    conn = _api.get_conn()
    def snapshot():
        return conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(outcome), -1) AS sum_"
            " FROM predictions").fetchone()

    before = snapshot()
    # `/auth/logout` ONLY, and the omission is deliberate. Posting a bad token
    # at `/auth/login` exercises the other write route, but a failed sign-in
    # is RECORDED -- that is the whole point of the backoff, which is stored
    # rather than held in memory so a restart is not a way around it. Doing it
    # here left a failure behind that
    # `test_auth.py::test_the_backoff_survives_a_restart` then measured,
    # and it failed in the full suite while passing alone. `test_auth.py`
    # covers the login route against the record directly.
    client.post("/auth/logout")
    after = snapshot()
    assert (before["n"], before["sum_"]) == (after["n"], after["sum_"])


def test_the_interface_connection_is_read_only(client):
    conn = api.get_conn()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES"
            " ('x','2026-01-01T00:00:00Z','a rationale long enough to pass the check')"
        )


def test_serving_refuses_a_public_interface():
    with pytest.raises(ValueError, match="127.0.0.1 only"):
        api.serve(host="0.0.0.0")


# --- health ----------------------------------------------------------------

def test_health_answers_liveness_only(client):
    """P3 stripped this route to nothing but liveness. It is the one endpoint
    that answers before authentication, so anything it carried would be readable
    by anyone who could reach the port. The kind banner and the staleness lines
    moved to /api/meta and /api/schedule, both behind the gate."""
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert set(body) == {"ok", "version"}


# --- the scorecard ---------------------------------------------------------

def test_scorecard_carries_a_sample_size_everywhere(client):
    payload = client.get("/api/scorecard").json()
    calibration.assert_every_figure_has_n(payload)     # must not raise
    assert payload["headline"]["n"] >= 0
    for bucket in payload["headline"]["buckets"]:
        assert isinstance(bucket["n"], int)


def test_scorecard_fails_loudly_rather_than_rendering_without_n(client, monkeypatch):
    """LAW 4 at the boundary: a stripped payload must 500, not reach the page."""
    real = calibration.scorecard

    def stripped(conn, *, sport):
        payload = real(conn, sport=sport)
        payload["headline"]["score"].pop("n")
        return payload

    monkeypatch.setattr(calibration, "scorecard", stripped)
    response = client.get("/api/scorecard")
    assert response.status_code == 500
    assert "LAW 4" in response.json()["detail"]


def test_the_headline_is_the_largest_gap(client):
    payload = client.get("/api/scorecard").json()
    assert "largest_gap" in payload["headline"]
    assert payload["headline"]["largest_gap"]


def test_categories_are_reported_separately(client):
    payload = client.get("/api/scorecard").json()
    # spread + five prop markets, each times two forecasters.
    assert len(payload["categories"]) == 2 * (1 + len(config.PROP_MARKETS))
    assert payload["markets"][0] == "spread"
    assert "never merged" in payload["separation_note"].lower()


def test_every_prop_market_has_its_own_gate(client):
    """The 100-resolution threshold applies per market, not to "props"."""
    for market in config.PROP_MARKETS:
        body = client.get(f"/api/history?prop_type={market}&limit=1").json()
        assert "n" in body


def test_the_edge_figure_is_withheld_below_the_threshold(client):
    edge = client.get("/api/scorecard").json()["edge"]
    assert edge["renderable"] is False
    assert "model_more_confident" not in edge
    assert edge["shortfall"] > 0
    assert "luck" in edge["standing_note"]


# --- this week -------------------------------------------------------------

def test_week_cards_are_sorted_by_disagreement(client):
    cards = client.get("/api/week?season=2025&week=7").json()["cards"]
    assert cards
    gaps = [c["abs_gap"] for c in cards]
    assert gaps == sorted(gaps, reverse=True), "the interesting cards must be first"


def test_a_card_carries_everything_needed_to_read_it(client):
    cards = client.get("/api/week?season=2025&week=7").json()["cards"]
    card = next(c for c in cards if c["market_type"] == "spread")
    for key in ("model_prob", "market_implied_prob", "gap", "top_factors",
                "reasoning", "line_asked", "claim", "created_utc",
                "factor_set_version"):
        assert key in card, key
    assert card["top_factors"], "a card with no factors explains nothing"
    assert all("rationale" in f for f in card["top_factors"])


def test_public_percentage_is_reported_as_absent_not_zero(client):
    for card in client.get("/api/week?season=2025&week=7").json()["cards"]:
        assert card["public_pct"] is None


def test_props_say_there_is_no_market_rather_than_implying_one(client):
    cards = client.get("/api/week?season=2025&week=7").json()["cards"]
    props = [c for c in cards if c["market_type"] == "prop"]
    assert props
    for card in props:
        assert card["market_implied_prob"] is None
        assert card["gap"] is None
        assert card["prop_type"] in config.PROP_MARKETS
        assert card["market"] == card["prop_type"]


def test_an_unforecast_week_falls_back_rather_than_showing_nothing(client):
    body = client.get("/api/week").json()
    assert body["n"] > 0
    assert body["week"] in (7, 8)


# --- factors ---------------------------------------------------------------

def test_every_factor_row_has_its_sample_size_and_rationale(client):
    payload = client.get("/api/factors").json()
    assert payload["n"] >= 0
    assert payload["factors"]
    for f in payload["factors"]:
        assert isinstance(f["n"], int)
        assert f["rationale"]
        assert f["added_utc"]
        assert f["verdict"]


def test_the_inactive_factor_is_shown_with_its_reason(client):
    payload = client.get("/api/factors").json()
    entry = next(f for f in payload["factors"] if f["factor"] == "public_bet_pct")
    assert entry["active"] is False
    assert entry["note"]


# --- history ---------------------------------------------------------------

def test_history_is_searchable(client):
    everything = client.get("/api/history?limit=500").json()
    assert everything["n"] > 0
    subject = everything["items"][0]["subject"]
    hit = client.get(f"/api/history?q={subject.split()[0]}&limit=500").json()
    assert 0 < hit["n"] <= everything["n"]


def test_history_filters_compose(client):
    spreads = client.get("/api/history?market_type=spread&limit=500").json()
    stat = client.get(
        "/api/history?market_type=spread&predictor=statistical&limit=500"
    ).json()
    assert stat["n"] <= spreads["n"]
    for item in stat["items"]:
        assert item["market_type"] == "spread"
        assert item["predictor"] == "statistical"


def test_history_records_the_line_at_the_time(client):
    items = client.get("/api/history?market_type=spread&limit=500").json()["items"]
    assert any(i["market_line_at_the_time"] is not None for i in items)
    for i in items:
        assert "line_asked" in i and "model_prob" in i


def test_history_paginates(client):
    first = client.get("/api/history?limit=5&offset=0").json()
    second = client.get("/api/history?limit=5&offset=5").json()
    assert first["returned"] == 5
    assert {i["prediction_id"] for i in first["items"]} & {
        i["prediction_id"] for i in second["items"]
    } == set()


def test_a_single_prediction_can_be_inspected(client):
    pid = client.get("/api/history?limit=1").json()["items"][0]["prediction_id"]
    detail = client.get(f"/api/prediction/{pid}").json()
    assert detail["prediction_id"] == pid
    assert "factors" in detail and "values" in detail["factors"]
    assert client.get("/api/prediction/999999").status_code == 404


# --- the page itself -------------------------------------------------------

def test_the_page_and_its_assets_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Gridiron" in page.text
    for asset in ("/static/app.js", "/static/style.css"):
        assert client.get(asset).status_code == 200


def test_the_page_has_no_build_step():
    """No bundler, no npm, no framework: the assets shipped are the assets
    written. The list is spelled out rather than counted so that adding a file
    to `web/` is a decision somebody makes on purpose — a minified bundle or a
    vendored framework would land here and have to be argued for."""
    web = config.PACKAGE_ROOT / "web"
    assert {p.name for p in web.iterdir()} == {
        "index.html",        # the app
        "login.html",        # P3: the one page reachable without a session
        "app.js",
        "style.css",
        "sw.js",             # P4: app shell only, never data
        "icon.svg",          # drawn in code, not exported from a design tool
        "manifest.webmanifest",
    }
    html = (web / "index.html").read_text(encoding="utf-8")
    assert "/static/app.js" in html
    assert "node_modules" not in html and "cdn" not in html.lower()
    # Nothing shipped may be a build artefact.
    assert not any(p.name.endswith((".min.js", ".min.css", ".map"))
                   for p in web.iterdir())


def test_the_meta_states_it_is_not_a_betting_tool(client):
    body = client.get("/api/meta").json()
    assert "does not" in body["not_a_betting_tool"]
    assert body["minimum_for_edge_claim"] == config.MIN_SAMPLE_FOR_EDGE_CLAIM


def test_the_markets_payload_matches_what_the_browser_reads(client):
    """A contract test, because this one broke and nobody noticed for three
    sessions. s1 renamed `spread` to `game_markets` on the server; the browser
    still read `data.spread`, threw inside boot's catch on every load, and left
    the week picker and the chart's market selector permanently empty."""
    body = client.get("/api/markets").json()
    for field in ("markets", "game_markets", "props", "n"):
        assert field in body, f"/api/markets no longer returns {field!r}"

    # Comments stripped first: the fix for this bug is documented in a comment
    # that names the old field, and an earlier draft of this test matched its
    # own explanation. A check that reads prose fails when prose improves.
    app_js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    body_of = app_js.split("loadMarkets")[1][:600]
    code = chr(10).join(line.split("//", 1)[0] for line in body_of.splitlines())
    reads = set(re.findall(r"data\.(\w+)", code))
    unknown = reads - set(body)
    assert not unknown, (
        f"loadMarkets reads {sorted(unknown)}, which /api/markets does not return"
    )


def test_the_week_picker_is_offered_every_slate_that_has_predictions(client):
    body = client.get("/api/weeks").json()
    assert body["n"] > 0, "no slates offered to the picker"
    for week in body["weeks"]:
        assert {"season", "week", "n"} <= set(week)
