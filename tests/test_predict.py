"""G3: the blind loop, the two predictors, and the budget ledger."""

from __future__ import annotations

import json
import math
import random
import types

import pytest

from gridiron import blind, config, db, run
from gridiron.factors import compute, context, store
from gridiron.market import lines
from gridiron.model import baseline, llm, logistic, predict, questions


# --- the logistic model ----------------------------------------------------

def test_fit_recovers_the_coefficients_it_was_given():
    """Generate from a known model, fit it back. If this drifts, every
    explanation the app shows is drifting with it."""
    rng = random.Random(7)
    truth = {"a": 1.5, "b": -0.8, "c": 0.0}
    rows, labels = [], []
    for _ in range(6000):
        row = {k: rng.gauss(0, 1) for k in truth}
        z = 0.3 + sum(truth[k] * row[k] for k in truth)
        rows.append(row)
        labels.append(1 if rng.random() < logistic.sigmoid(z) else 0)

    fit = logistic.fit(rows, labels, ["a", "b", "c"], l2=0.5)
    got = fit.as_dict()
    assert fit.converged
    assert abs(fit.intercept - 0.3) < 0.12
    assert abs(got["a"] - 1.5) < 0.15
    assert abs(got["b"] - -0.8) < 0.15
    assert abs(got["c"] - 0.0) < 0.10


def test_contributions_reconstruct_the_log_odds_exactly():
    fit = logistic.Fit(["x", "y"], [0.4, -1.1], intercept=0.25, n=10,
                       iterations=3, converged=True, l2=1.0)
    row = {"x": 2.0, "y": 0.5}
    total = fit.intercept + sum(c for _, _, c in fit.contributions(row))
    assert abs(total - fit.log_odds(row)) < 1e-12
    assert abs(fit.predict(row) - logistic.sigmoid(fit.log_odds(row))) < 1e-12


def test_sigmoid_does_not_overflow_on_a_confident_prediction():
    assert logistic.sigmoid(-800) == pytest.approx(0.0, abs=1e-12)
    assert logistic.sigmoid(800) == pytest.approx(1.0, abs=1e-12)


def test_fitting_on_nothing_is_an_error_not_a_flat_model():
    with pytest.raises(ValueError):
        logistic.fit([], [], ["a"])


# --- the questions are chosen blind and deterministically ------------------

def test_the_same_game_is_always_asked_the_same_question():
    first = [questions.spread_line_asked(f"2026_01_X{i}_Y") for i in range(50)]
    second = [questions.spread_line_asked(f"2026_01_X{i}_Y") for i in range(50)]
    assert first == second, "the question rule must be reproducible across runs"
    assert set(first) <= set(questions.SPREAD_LADDER)
    assert len(set(first)) == len(questions.SPREAD_LADDER), "all rungs get used"


def test_no_question_can_push():
    for line in questions.SPREAD_LADDER:
        assert abs(line * 2) % 2 == 1, f"{line} allows a push"
    assert questions.prop_line_asked(240.0, "k", "passing_yards") % 1 == 0.5


def test_spread_outcome_uses_the_ordinary_convention():
    # Home favoured by 3.5, wins by 7 -> covers.
    assert questions.spread_outcome(28, 21, -3.5) == 1
    # Home favoured by 3.5, wins by 3 -> does not.
    assert questions.spread_outcome(24, 21, -3.5) == 0
    # Home getting 3.5, loses by 3 -> covers.
    assert questions.spread_outcome(21, 24, 3.5) == 1


def test_a_question_is_not_chosen_from_a_market_line():
    """The rule may depend on the game id and nothing else.

    (`spread_line_asked` is our own name for our own question; what must not
    appear is any reference to the quarantined tables or to a market price.)
    """
    assert questions.spread_line_asked("2026_01_NE_SEA") == questions.spread_line_asked(
        "2026_01_NE_SEA"
    )
    source = (config.PACKAGE_ROOT / "model" / "questions.py").read_text(encoding="utf-8")
    for word in ("market_lines_raw", "market_snapshots", "moneyline", "implied_prob"):
        assert word not in source, word


# --- LAW 1: the blind window -----------------------------------------------

def test_blind_window_refuses_a_market_import():
    blind.forget_market_module()
    with pytest.raises(blind.MarketAccessDuringBlindWindow, match="LAW 1"):
        with blind.blind_window():
            import gridiron.market.lines  # noqa: F401


def test_blind_window_refuses_to_open_if_market_is_already_loaded():
    import gridiron.market.lines  # noqa: F401  - deliberately poison sys.modules

    with pytest.raises(blind.MarketAccessDuringBlindWindow, match="already imported"):
        with blind.blind_window():
            pass


def test_the_window_closes_even_when_the_body_raises():
    import sys

    blind.forget_market_module()
    before = len(sys.meta_path)
    with pytest.raises(ValueError):
        with blind.blind_window():
            raise ValueError("boom")
    assert len(sys.meta_path) == before, "the sentinel must not leak into later work"


# --- the loop --------------------------------------------------------------

@pytest.fixture
def trained(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    return league


def test_a_prediction_row_exists_before_its_snapshot(trained):
    result = run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 4
    assert result["snapshots"]["snapshotted"] + result["snapshots"]["no_line"] == 4

    rows = trained.execute(
        "SELECT p.created_utc, s.fetched_utc FROM predictions p"
        " JOIN market_snapshots s ON s.prediction_id = p.id"
    ).fetchall()
    for r in rows:
        assert r["fetched_utc"] >= r["created_utc"], "LAW 1: the line arrived first"


def test_rerunning_a_week_does_not_write_a_second_opinion(trained):
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    first = trained.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    again = run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    second = trained.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert second == first
    assert again["written"] == 0


def test_stated_confidence_is_never_below_a_coin_flip(trained):
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    for r in trained.execute("SELECT model_prob, model_side FROM predictions"):
        assert 0.5 <= r["model_prob"] < 1.0
        assert r["model_side"] in ("cover", "not_cover")


def test_the_stored_prediction_carries_its_factors_and_explanation(trained):
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    row = trained.execute("SELECT * FROM predictions LIMIT 1").fetchone()
    payload = json.loads(row["factors_json"])
    assert payload["market_type"] == "spread"
    assert payload["values"], "the factor values must be on the record"
    assert "contributions" in payload
    assert row["reasoning"].strip()
    assert row["factor_set_version"] == config.FACTOR_SET_VERSION


def test_predicting_without_a_fitted_model_skips_loudly(league):
    store.sync_registry(league)
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 0
    assert any("no fitted" in s for s in result["skipped"])


# --- the market half -------------------------------------------------------

def test_implied_probability_is_symmetric_about_the_line():
    assert lines.implied_cover_probability(3.5, -3.5) == pytest.approx(0.5)
    assert lines.implied_cover_probability(0.0, 0.0) == pytest.approx(0.5)
    # A home side favoured by 10 is well over half to cover -3.5.
    assert lines.implied_cover_probability(10.0, -3.5) > 0.65
    # ... and well under half to cover -14.5.
    assert lines.implied_cover_probability(10.0, -14.5) < 0.4


def test_public_percentage_is_absent_rather_than_invented(trained):
    assert lines.public_percentage(trained, "any") is None
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    for r in trained.execute("SELECT public_pct FROM market_snapshots"):
        assert r["public_pct"] is None


def test_a_prediction_keeps_its_first_snapshot(trained):
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    pid = trained.execute("SELECT id FROM predictions LIMIT 1").fetchone()["id"]
    first = trained.execute(
        "SELECT COUNT(*) FROM market_snapshots WHERE prediction_id = ?", (pid,)
    ).fetchone()[0]
    lines.snapshot_prediction(trained, pid)
    lines.snapshot_prediction(trained, pid)
    after = trained.execute(
        "SELECT COUNT(*) FROM market_snapshots WHERE prediction_id = ?", (pid,)
    ).fetchone()[0]
    assert after == first == 1


# --- the LLM pass and its ledger -------------------------------------------

class StubClient:
    """Stands in for the Anthropic client. Records what it was asked."""

    def __init__(self, replies, usage=(1200, 180)):
        self._replies = list(replies)
        self.usage = usage
        self.prompts = []
        self.models = []
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, *, model, max_tokens, system, messages):
        self.prompts.append(messages[0]["content"])
        self.models.append(model)
        text = self._replies.pop(0)
        if isinstance(text, Exception):
            raise text
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(text=text)],
            usage=types.SimpleNamespace(
                input_tokens=self.usage[0], output_tokens=self.usage[1]
            ),
        )


def _factor_rows():
    return [
        {"factor": "srs_diff", "value": 0.8, "missing": False, "rationale": "Team quality."},
        {"factor": "wind", "value": 0.0, "missing": True, "rationale": "Wind matters."},
    ]


def test_llm_reasoning_is_recorded_and_priced(conn):
    client = StubClient(['{"probability": 0.62, "reasoning": "Ratings favour the home side."}'])
    result = llm.reason(
        conn,
        question="KC covers -3.5",
        factor_rows=_factor_rows(),
        notes=["week 1: ratings fall back to last season"],
        game_id="G1",
        client=client,
    )
    assert result.probability == pytest.approx(0.62)
    assert result.reasoning
    assert result.usd > 0

    row = conn.execute("SELECT * FROM llm_calls").fetchone()
    assert row["purpose"] == "reasoning"
    assert row["model"] == config.LLM_REASONING_MODEL
    assert row["usd"] == pytest.approx(result.usd)
    assert llm.spent_today(conn) == pytest.approx(result.usd)


def test_the_prompt_carries_factors_and_no_line(conn):
    client = StubClient(['{"probability": 0.55, "reasoning": "Thin factors."}'])
    llm.reason(conn, question="KC covers -3.5", factor_rows=_factor_rows(),
               notes=[], game_id="G1", client=client)
    prompt = client.prompts[0]
    assert "srs_diff" in prompt and "(defaulted)" in prompt
    for word in ("moneyline", "implied", "sportsbook", "vig", "juice"):
        assert word not in prompt.lower()
    assert "market" not in prompt.lower()


def test_malformed_json_is_repaired_by_the_cheap_model(conn):
    client = StubClient(
        [
            "I think about 0.7, honestly.",
            '{"probability": 0.7, "reasoning": "Recovered."}',
        ]
    )
    result = llm.reason(conn, question="q", factor_rows=_factor_rows(), notes=[],
                        game_id="G1", client=client)
    assert result.repaired
    assert client.models == [config.LLM_REASONING_MODEL, config.LLM_CHEAP_MODEL], (
        "formatting must be routed to the cheap model"
    )
    purposes = [r["purpose"] for r in conn.execute("SELECT purpose FROM llm_calls ORDER BY id")]
    assert purposes == ["reasoning", "format"]


def test_the_daily_cap_stops_the_call_before_it_is_made(conn, monkeypatch):
    monkeypatch.setattr(config, "LLM_DAILY_USD_CAP", 0.0001)
    client = StubClient(['{"probability": 0.6, "reasoning": "x"}'])
    with pytest.raises(llm.LLMUnavailable) as exc:
        llm.reason(conn, question="q", factor_rows=_factor_rows(), notes=[], client=client)
    assert exc.value.reason == "daily_budget"
    assert client.prompts == [], "the budget check must precede the spend"


def test_an_api_failure_is_recorded_and_degrades(conn):
    client = StubClient([RuntimeError("503 overloaded")])
    with pytest.raises(llm.LLMUnavailable) as exc:
        llm.reason(conn, question="q", factor_rows=_factor_rows(), notes=[],
                   game_id="G1", client=client)
    assert exc.value.reason == "api_error"
    row = conn.execute("SELECT * FROM llm_calls").fetchone()
    assert row["ok"] == 0
    assert "503" in row["error"]


def test_a_probability_outside_zero_to_one_is_rejected(conn):
    client = StubClient(['{"probability": 1.4, "reasoning": "certain"}'])
    with pytest.raises(llm.LLMUnavailable) as exc:
        llm.reason(conn, question="q", factor_rows=_factor_rows(), notes=[], client=client)
    assert exc.value.reason == "out_of_range"


def test_a_probability_with_no_reasoning_is_rejected(conn):
    client = StubClient(['{"probability": 0.7, "reasoning": ""}'])
    with pytest.raises(llm.LLMUnavailable) as exc:
        llm.reason(conn, question="q", factor_rows=_factor_rows(), notes=[], client=client)
    assert exc.value.reason == "no_reasoning"


def test_both_predictors_are_recorded_as_separate_rows(trained):
    client = StubClient(
        ['{"probability": 0.66, "reasoning": "The home rating is better."}'] * 40
    )
    result = run.run_week(
        trained, 2025, 7, include_props=False, use_llm=True, llm_client=client
    )
    assert result["by_predictor"] == {"statistical": 4, "llm": 4}
    rows = trained.execute(
        "SELECT predictor, COUNT(*) AS n FROM predictions GROUP BY predictor"
    ).fetchall()
    assert {r["predictor"]: r["n"] for r in rows} == {"statistical": 4, "llm": 4}


def test_a_missing_key_degrades_with_a_tag_and_never_fabricates(trained, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    result = run.run_week(trained, 2025, 7, include_props=False, use_llm=True)
    assert result["by_predictor"] == {"statistical": 4}
    assert "llm_unavailable:no_api_key" in result["degradations"]
    assert any("statistical predictions stand alone" in s for s in result["skipped"])
    assert trained.execute(
        "SELECT COUNT(*) FROM predictions WHERE predictor = 'llm'"
    ).fetchone()[0] == 0


def test_the_ledger_summarises_the_day(conn):
    client = StubClient(['{"probability": 0.6, "reasoning": "ok"}'] * 3)
    for _ in range(3):
        llm.reason(conn, question="q", factor_rows=_factor_rows(), notes=[], client=client)
    summary = llm.ledger_summary(conn)
    assert summary["calls"] == 3
    assert summary["usd_spent"] > 0
    assert summary["usd_remaining"] == pytest.approx(
        config.LLM_DAILY_USD_CAP - summary["usd_spent"], abs=1e-4
    )
