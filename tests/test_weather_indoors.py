"""AN INDOOR GAME CARRIES NO WEATHER (operator ruling 4, 2026-09-24).

"Weather: precipitation, wind and cold all follow the same rule. An indoor
game carries no value; the fit reports each factor's rows used." And the fs5
brief of the same morning: "a training row with no weather can't carry a
precipitation value."

Until that day a dome read wind 0, cold 0 and rain 0 -- a calm, mild, dry
afternoon nobody measured -- on 760 of the NFL spread's 2,632 training rows,
and precipitation's only values in the whole training set were those domes.
These tests pin the repair, the one guard, the claim that the repair moves no
probability, and the Factors page reading each market's ACTIVE fit.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import random
import textwrap

import pytest

from gridiron import calibration, db, language
from gridiron.data import weather
from gridiron.factors import compute, context, registry, store
from gridiron.model import activation, baseline, logistic


def _scheduled_game(league) -> str:
    return league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' ORDER BY id LIMIT 1"
    ).fetchone()["id"]


def _roof(league, game_id: str, roof: str, *, temp=None, wind=None) -> None:
    league.execute(
        "UPDATE game_conditions SET roof = ?, temp_f = ?, wind_mph = ?"
        " WHERE game_id = ?", (roof, temp, wind, game_id))
    league.commit()


def _forecast(league, game_id: str, temp=41.0, wind=17.0, precip=70.0) -> None:
    league.execute(
        "INSERT INTO weather_forecasts (game_id, fetched_utc, source, temp_f,"
        " wind_mph, precip_pct) VALUES (?,?,?,?,?,?)",
        (game_id, db.utcnow(), "open-meteo", temp, wind, precip))
    league.commit()


WEATHER = ("wind", "cold", "precipitation")


# --- the repair --------------------------------------------------------------

@pytest.mark.parametrize("roof", ["dome", "closed", " Dome "])
def test_an_indoor_game_carries_no_weather_value(league, roof):
    """Even with a stored forecast AND an observed reading on the row: under a
    roof there is no weather to read, and none is invented."""
    game_id = _scheduled_game(league)
    _roof(league, game_id, roof, temp=72.0, wind=0.0)
    _forecast(league, game_id)

    ctx = context.build_game_context(league, game_id)
    assert ctx.indoors is True
    assert ctx.weather_basis == "indoors"
    assert (ctx.wind_mph, ctx.temp_f, ctx.precip_pct) == (None, None, None), (
        "an indoor context must carry no weather reading, not a calm dry day")
    assert context.INDOORS_NOTE in ctx.notes, "the context says why"

    for market in ("spread", "total"):
        fv = compute.feature_vector(ctx, market)
        for name in WEATHER:
            assert name not in fv.values, f"{name} carried a value indoors"
            assert name in fv.absent
            assert "indoors" in compute.absent_reason(fv, name)
            assert name not in fv.sources


def test_an_open_roof_is_outdoors_and_its_forecast_is_read(league):
    game_id = _scheduled_game(league)
    _roof(league, game_id, "open")
    _forecast(league, game_id, temp=35.0, wind=20.0, precip=50.0)

    ctx = context.build_game_context(league, game_id)
    fv = compute.feature_vector(ctx, "spread")
    assert ctx.indoors is False and ctx.weather_basis == "forecast"
    assert fv.values["wind"] == pytest.approx(1.0)
    assert fv.values["cold"] == pytest.approx(-1.0)
    assert fv.values["precipitation"] == pytest.approx(0.5)
    assert {fv.sources[n] for n in WEATHER} == {"forecast"}


def test_an_absent_outdoor_reading_says_so_rather_than_indoors(league):
    game_id = _scheduled_game(league)
    fv = compute.feature_vector(context.build_game_context(league, game_id), "spread")
    for name in WEATHER:
        assert name in fv.absent
        assert compute.absent_reason(fv, name) == "no weather reading for this game"


def test_an_unpublished_roof_is_not_assumed_open(league):
    """A retractable stadium's roof is published only after its game (37 of
    the 2026 season's scheduled games, measured 2026-09-24), and those roofs
    were closed for 354 of 402 home games in 2016-2025. Unknown carries no
    weather value -- not even a stored forecast -- and says why."""
    game_id = _scheduled_game(league)
    _roof(league, game_id, None)
    _forecast(league, game_id)
    ctx = context.build_game_context(league, game_id)
    assert ctx.indoors is None and ctx.weather_basis == "unknown roof"
    assert (ctx.wind_mph, ctx.temp_f, ctx.precip_pct) == (None, None, None)
    assert context.UNKNOWN_ROOF_NOTE in ctx.notes
    fv = compute.feature_vector(ctx, "spread")
    for name in WEATHER:
        assert name in fv.absent
        assert "not known to be open" in compute.absent_reason(fv, name)


def test_the_fetch_and_the_context_share_one_test_of_a_roof(league, monkeypatch):
    """ONE DOOR: the forecast fetch skips every game the context would give no
    weather, because both ask `weather.roof_state`."""
    assert weather.roof_state("dome") == weather.roof_state("Closed") == "indoors"
    assert weather.roof_state("open") == weather.roof_state("outdoors") == "outdoors"
    assert weather.roof_state(None) == weather.roof_state("") == "unknown roof"

    week = [r["id"] for r in league.execute(
        "SELECT id FROM games WHERE week = 17 ORDER BY id")]
    _roof(league, week[0], "dome")
    _roof(league, week[1], None)
    counts = weather.fetch_week(league, 2025, 17)
    assert counts["indoors"] == 1 and counts["unknown_roof"] == 1
    assert league.execute("SELECT COUNT(*) FROM weather_forecasts").fetchone()[0] == 0

    monkeypatch.setattr(weather, "roof_state", lambda roof: "indoors")
    assert context.build_game_context(league, week[2]).indoors is True


def test_the_stored_forecast_absent_detail_names_the_reason(league):
    """The statistical forecast's stored `absent_detail` carries the reason."""
    game_id = _scheduled_game(league)
    _roof(league, game_id, "dome")
    fv = compute.feature_vector(context.build_game_context(league, game_id), "spread")
    fit = logistic.Fit(names=["wind"], coefficients=[0.3], intercept=0.0, n=100,
                       iterations=1, converged=True, l2=1.0)
    stat = baseline.predict(fit, fv)
    assert stat["absent_detail"]["wind"] == "played indoors: no weather reaches the game"


# --- the one guard -----------------------------------------------------------

def test_the_guard_is_a_missing_data_default():
    """Same class of failure as v2's: a value where nothing was measured."""
    assert issubclass(compute.WeatherNotRead, compute.MissingDataDefaulted)


def test_a_weather_value_on_an_indoor_game_is_refused_by_name(league, monkeypatch):
    game_id = _scheduled_game(league)
    _roof(league, game_id, "dome")
    ctx = context.build_game_context(league, game_id)
    monkeypatch.setitem(registry.REGISTRY, "wind", dataclasses.replace(
        registry.REGISTRY["wind"], fn=lambda c: 0.0))
    with pytest.raises(compute.WeatherNotRead, match="WEATHER ON AN INDOOR GAME: 'wind'"):
        compute.feature_vector(ctx, "spread")


def test_a_training_row_with_no_weather_cannot_carry_precipitation(league, monkeypatch):
    """The fs5 brief's words, as a test: the fallback v2 removed, put back."""
    game_id = _scheduled_game(league)
    ctx = context.build_game_context(league, game_id)
    assert ctx.weather_basis == "none"
    monkeypatch.setitem(registry.REGISTRY, "precipitation", dataclasses.replace(
        registry.REGISTRY["precipitation"], fn=lambda c: 0.0))
    with pytest.raises(compute.WeatherNotRead,
                       match="WEATHER THAT WAS NEVER READ: 'precipitation'"):
        compute.feature_vector(ctx, "spread")


def test_a_fill_in_the_context_is_refused_as_well(league):
    """A stand-in reading on the CONTEXT with nothing read behind it -- the
    shape of the released `_weather` -- is caught even though every factor
    function is honest."""
    game_id = _scheduled_game(league)
    ctx = context.build_game_context(league, game_id)
    ctx.precip_pct = 0.0              # a dry day nobody read; basis still 'none'
    with pytest.raises(compute.WeatherNotRead, match="'precipitation'"):
        compute.feature_vector(ctx, "spread")


def test_training_refuses_the_released_fill_by_name(league, monkeypatch):
    """The whole training path, not a hand-built vector: a season with a dome
    under the released fill does not fit."""
    store.sync_registry(league)
    league.execute(
        "UPDATE game_conditions SET roof = 'dome' WHERE game_id IN"
        " (SELECT id FROM games WHERE week = 3)")
    league.commit()
    _released_fill(monkeypatch, guard_off=False)
    with pytest.raises(compute.WeatherNotRead, match="INDOOR"):
        baseline.train(league, "spread", (2025,), l2=1.0, note="released fill")


def test_a_context_fill_alone_reaches_no_row(league, monkeypatch):
    """The released `_weather` without the released factors: each factor
    checks the roof itself, so the stand-in calm day never reaches a value."""
    game_id = _scheduled_game(league)
    _roof(league, game_id, "dome")
    monkeypatch.setattr(context, "_weather",
                        lambda conn, game: (True, 0.0, None, 0.0, "indoors"))
    fv = compute.feature_vector(context.build_game_context(league, game_id), "spread")
    assert not set(WEATHER) & set(fv.values)


def _reads(fn) -> set[str]:
    source = textwrap.dedent(inspect.getsource(fn))
    return {node.attr for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Attribute)
            and node.attr in registry.WEATHER_READINGS}


def test_every_factor_that_reads_the_weather_declares_it():
    """THE GUARD KNOWS A WEATHER FACTOR BY ITS DECLARATION, so a factor that
    reads a weather reading without declaring it would walk past it. Refused
    here, both ways round."""
    undeclared, wrong = [], []
    for f in registry.REGISTRY.values():
        reads = _reads(f.fn)
        if reads and f.weather is None:
            undeclared.append(f"{f.name} reads {sorted(reads)}")
        if f.weather is not None and reads != {f.weather}:
            wrong.append(f"{f.name} declares {f.weather} and reads {sorted(reads)}")
    assert not undeclared, undeclared
    assert not wrong, wrong
    assert {f.name for f in registry.REGISTRY.values() if f.weather} >= {
        "wind", "cold", "precipitation", "cfb_wind_mph"}


def test_a_weather_declaration_must_name_a_reading():
    with pytest.raises(ValueError, match="not a weather reading"):
        registry.factor(added="2026-09-24T00:00:00Z", applies_to=("spread",),
                        rationale="x" * 40, weather="humidity")(lambda ctx: None)


# --- college football --------------------------------------------------------

def _cfb_team(conn, code: str, indoor, lat=40.0, lon=-83.0) -> None:
    conn.execute(
        "INSERT INTO teams (sport, tricode, display_name, source_url, fetched_utc,"
        " venue_indoor, venue_lat, venue_lon) VALUES ('cfb',?,?,?,?,?,?,?)",
        (code, code, "https://example.invalid", db.utcnow(), indoor, lat, lon))
    conn.commit()


def test_a_college_dome_carries_no_wind_and_says_why(conn):
    from gridiron.sports import cfb as cfb_sport

    _cfb_team(conn, "DOM", 1)
    _cfb_team(conn, "UNK", None)
    assert cfb_sport._weather(conn, "DOM", "2020-09-05T18:00:00Z") == (True, None, "indoors")
    assert cfb_sport._weather(conn, "UNK", "2020-09-05T18:00:00Z") == (
        None, None, "unknown roof")


def test_a_college_indoor_context_refuses_a_wind(monkeypatch):
    from gridiron.sports.cfb import CfbContext

    ctx = CfbContext(game_id="cfb_1", season=2025, day=20250906, home="DOM",
                     away="OUT", kickoff_utc="2025-09-06T18:00:00Z",
                     game_date="2025-09-06", market="total", line_asked=52.5,
                     wind_mph=14.0, indoors=True, weather_basis="indoors")
    assert registry.REGISTRY["cfb_wind_mph"].fn(ctx) is None
    fv = compute.feature_vector(ctx, "total", "total")
    assert "cfb_wind_mph" in fv.absent
    monkeypatch.setitem(registry.REGISTRY, "cfb_wind_mph", dataclasses.replace(
        registry.REGISTRY["cfb_wind_mph"], fn=lambda c: c.wind_mph))
    with pytest.raises(compute.WeatherNotRead, match="'cfb_wind_mph'"):
        compute.feature_vector(ctx, "total", "total")


# --- the repair moves no probability -----------------------------------------

def _released_fill(monkeypatch, *, guard_off: bool = True) -> None:
    """ed5c07e's behaviour for an indoor game: the context's calm dry day and
    each weather factor's 0.0 under a roof. With the guard off, unless told."""
    real = context._weather

    def released(conn, game):
        if (game["roof"] or "").lower() in ("dome", "closed"):
            return True, 0.0, None, 0.0, "indoors"
        return real(conn, game)

    monkeypatch.setattr(context, "_weather", released)
    for name in WEATHER:
        f = registry.REGISTRY[name]
        monkeypatch.setitem(registry.REGISTRY, name, dataclasses.replace(
            f, fn=lambda c, _f=f.fn: 0.0 if c.indoors else _f(c)))
    if guard_off:
        monkeypatch.setattr(compute, "assert_weather_was_read", lambda ctx, fv: None)


def test_the_repair_moves_no_coefficient_and_no_probability(league, monkeypatch):
    """MEASURED, NOT ASSUMED: a 0.0 adds nothing to a logistic's gradient or
    Hessian, so the same season fitted with the domes filled and with them
    absent gives the same coefficients -- and the same forecast for a dome.
    What differs is the count of rows the fit says carried the weather."""
    from gridiron import sports

    rng = random.Random(24)
    games = [r["id"] for r in league.execute(
        "SELECT id FROM games WHERE status = 'final' ORDER BY id")]
    for i, game_id in enumerate(games):
        if i % 3 == 0:
            _roof(league, game_id, "dome")
        else:
            _roof(league, game_id, "outdoors", temp=rng.uniform(20, 85),
                  wind=rng.uniform(0, 25))
    dome = _scheduled_game(league)
    _roof(league, dome, "dome")

    def fit_and_forecast():
        rows, labels, names = sports.get("nfl").training_set(league, (2025,), "spread")
        fit = logistic.fit(rows, labels, names, l2=1.0)
        ctx = context.build_game_context(league, dome, line_asked=-3.5)
        return fit, fit.predict(compute.feature_vector(ctx, "spread").values)

    fit_new, p_new = fit_and_forecast()
    with monkeypatch.context() as m:
        _released_fill(m)
        fit_old, p_old = fit_and_forecast()

    assert fit_old.names == fit_new.names
    for name, a, b in zip(fit_new.names, fit_old.coefficients, fit_new.coefficients):
        assert a == pytest.approx(b, abs=1e-9), name
    assert fit_old.intercept == pytest.approx(fit_new.intercept, abs=1e-9)
    assert p_old == pytest.approx(p_new, abs=1e-12)
    domes = sum(1 for i in range(len(games)) if i % 3 == 0)
    assert fit_old.presence["wind"] - fit_new.presence["wind"] > 0
    assert fit_old.presence["wind"] - fit_new.presence["wind"] <= domes


# --- the Factors page reads each market's ACTIVE fit ---------------------------

def _factor_entry(league, name: str) -> dict:
    report = calibration.factor_report(league, sport="nfl")
    return next(f for f in report["factors"] if f["factor"] == name)


def test_the_factors_page_reads_the_active_fit_not_the_newest(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="the active one")
    activation.activate_in_a_scratch_world(league)
    active = activation.active_fit(league, "nfl", "spread")["fit_id"]
    baseline.train(league, "spread", (2025,), l2=1.0, note="newer, never activated")
    newest = league.execute("SELECT MAX(id) FROM model_fits").fetchone()[0]
    assert newest != active

    entry = _factor_entry(league, "rest_diff")
    spread = [e for e in entry["fit_rows"] if e["market"] == "spread"]
    assert [e["fit_id"] for e in spread] == [active]
    assert spread[0]["factor_set_version"] == "fs3", "the declared set, not the default"


def test_a_total_is_read_under_its_own_key(league):
    """The page looked a total up as 'prop:total' and found nothing."""
    store.sync_registry(league)
    baseline.train(league, "total", (2025,), l2=1.0, note="total")
    activation.activate_in_a_scratch_world(league)
    entry = _factor_entry(league, "nfl_total_volatility")
    assert [e["market"] for e in entry["fit_rows"]] == ["total"]
    assert entry["fit_rows_words"].startswith("total ")


def test_a_factor_shared_by_two_markets_reports_both(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="spread")
    baseline.train(league, "total", (2025,), l2=1.0, note="total")
    activation.activate_in_a_scratch_world(league)
    entry = _factor_entry(league, "pace_sum")
    markets = {e["market"] for e in entry["fit_rows"]}
    assert markets == {"spread", "total"}
    words = entry["fit_rows_words"]
    assert "point spread" in words and "total" in words and " of " in words


def test_a_weather_count_taken_with_the_fill_says_so(league):
    """A fit trained before the repair counts domes among its weather rows,
    and its blob does not carry the rule; the page says so beside the count.
    A fit trained now carries the rule and says nothing extra."""
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="now")
    blob = json.loads(league.execute(
        "SELECT coefficients_json FROM model_fits ORDER BY id DESC LIMIT 1"
    ).fetchone()[0])
    assert blob["indoor_weather"] == compute.INDOOR_WEATHER
    blob.pop("indoor_weather")
    blob["coefficients"]["wind"] = 0.05
    blob["presence"]["wind"] = 40
    (blob.get("dropped") or {}).pop("wind", None)
    (blob.get("constant") or {}).pop("wind", None)
    league.execute(
        "INSERT INTO model_fits (sport, fitted_utc, factor_set_version, market_type,"
        " train_through, n_train, coefficients_json, note)"
        " VALUES ('nfl', ?, 'fs3', 'spread', 'seasons:2025-2025', ?, ?, 'before')",
        (db.utcnow(), blob["n"], json.dumps(blob)))
    league.commit()
    activation.activate_in_a_scratch_world(league)

    wind = _factor_entry(league, "wind")
    assert [e["market"] for e in wind["fit_rows"]] == ["spread"]
    assert wind["fit_rows"][0]["indoor_filled"] is True
    assert "indoor games among them" in wind["fit_rows_words"]
    rest = _factor_entry(league, "rest_diff")
    assert "indoor" not in rest["fit_rows_words"]
    # A count of NO rows has no domes among them; the render said otherwise
    # once, about the cold on 0 of 64 (2026-09-24).
    cold = _factor_entry(league, "cold")
    assert cold["fit_rows"] and all(not e["rows"] for e in cold["fit_rows"])
    assert not any(e["indoor_filled"] for e in cold["fit_rows"])
    assert "indoor" not in cold["fit_rows_words"]


def test_fit_rows_words_carry_every_count_with_its_n():
    words = language.fit_rows_words("nfl", [
        {"market": "spread", "rows": 1703, "n": 2632, "excluded": False},
        {"market": "passing_yards", "rows": 0, "n": 1172, "excluded": True},
        {"market": "total", "rows": 2330, "n": 2478, "excluded": False,
         "indoor_filled": True},
        {"market": "receptions", "rows": None, "n": 1343, "excluded": False},
    ])
    assert words == (
        "point spread 1,703 of 2,632 · passing yards 0 of 1,172, not fitted · "
        "total 2,330 of 2,478, indoor games among them · "
        "receptions: rows not recorded by this fit")
    assert language.fit_rows_words("nfl", []) is None
