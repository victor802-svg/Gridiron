"""K3: the plain why, and the guard that it cannot contradict the arithmetic.

What a pick card used to say:

    srs_diff = 1.3322 pushes toward the yes side by 1.38 in log-odds;
    asked_line = -0.5 pushes against the yes side by 0.56 in log-odds; ...

Every term there is an internal identifier or a unit nobody thinks in. The
decomposition is not wrong and has not been deleted -- it moved to the Factors
page. What a reader gets instead is which few things drove the pick and how
hard, in words, DERIVED FROM THE SAME CONTRIBUTIONS the decomposition uses.

That derivation is the whole point. Prose that restated a direction of its own
could drift from the arithmetic silently, which is exactly how the chance label
came to say "covers" on 34 cards where the model had said the opposite.
"""

from __future__ import annotations

import pytest

from gridiron import language
from gridiron.factors import registry
import gridiron.factors.mlb  # noqa: F401  (registers MLB's factors)
import gridiron.factors.nba  # noqa: F401


PHRASES = {f.name: f.why for f in registry.all_factors() if f.why}


# --- every factor carries a template ---------------------------------------

def test_every_declared_factor_has_a_why_template():
    """A factor without one cannot be explained, so it would be silently
    dropped from the reasons -- present in the arithmetic and absent from the
    words, which is the drift this whole phase exists to prevent."""
    missing = [f.name for f in registry.all_factors() if not (f.why or "").strip()]
    assert not missing, (
        "these factors have no WHY template and could never be explained: "
        + ", ".join(sorted(missing))
    )


def test_a_why_template_is_a_phrase_not_a_sentence():
    """It names the QUANTITY; the direction is composed at render time from the
    fitted contribution. A template that asserted a direction would go quietly
    wrong the day a refit flipped the sign."""
    for f in registry.all_factors():
        why = f.why or ""
        assert why == why.strip(), f"{f.name}: padded"
        assert not why.endswith("."), f"{f.name}: is a sentence, not a phrase"
        assert why[:1].islower() or why[:1].isdigit(), (
            f"{f.name}: starts capitalised; the composer capitalises it"
        )
        for banned in (" helps", " hurts", " favours", " works against"):
            assert banned not in why, (
                f"{f.name}: template asserts a direction ({banned.strip()!r}); "
                "direction is read from the contribution, never declared"
            )


def test_no_template_leaks_an_internal_identifier():
    from gridiron import audit

    for f in registry.all_factors():
        hits = audit.plain_words_violations(f.why or "")
        assert not hits, f"{f.name}: {hits}"


# --- the words follow the arithmetic ---------------------------------------

def _item(contribs, side="win", market="moneyline", **kw):
    item = {
        "subject": "TB", "market_type": market, "prop_type": None,
        "model_side": side, "model_prob": 0.6,
        "contributions": [
            {"factor": n, "contribution": v, "missing": False} for n, v in contribs
        ],
    }
    item.update(kw)
    return item


def test_the_reasons_are_ordered_by_size_of_contribution():
    said = language.why_sentences(_item([
        ("mlb_park_factor", 0.05),
        ("mlb_starter_rolling_perf", 0.90),
        ("mlb_bullpen_recent_load", 0.30),
    ]), PHRASES)
    assert said[0].startswith("The starting pitching matchup")
    assert said[1].startswith("How hard the bullpens")
    assert said[2].startswith("How much scoring this park")


def test_the_direction_of_each_sentence_is_the_sign_of_its_contribution():
    said = language.why_sentences(_item([
        ("mlb_starter_rolling_perf", 0.90),
        ("mlb_park_factor", -0.40),
    ]), PHRASES)
    assert "helps the pick" in said[0]
    assert "works against it" in said[1]


def test_taking_the_no_side_flips_every_direction():
    """A contribution is signed toward the question's YES side. The model
    frequently takes the other one, and a paragraph of reasons describing the
    side NOT taken is the K1 defect in prose."""
    contribs = [("mlb_starter_rolling_perf", 0.90), ("mlb_park_factor", -0.40)]
    yes = language.why_sentences(_item(contribs, side="win"), PHRASES)
    no = language.why_sentences(_item(contribs, side="lose"), PHRASES)
    assert "helps the pick" in yes[0] and "works against it" in no[0]
    assert "works against it" in yes[1] and "helps the pick" in no[1]


def test_at_most_four_sentences():
    said = language.why_sentences(_item([
        ("mlb_starter_rolling_perf", 0.9), ("mlb_park_factor", 0.8),
        ("mlb_bullpen_recent_load", 0.7), ("mlb_team_rest_travel", 0.6),
        ("mlb_team_offense_rolling", 0.5), ("mlb_starter_rest_days", 0.4),
    ]), PHRASES)
    assert len(said) == language.WHY_MAX_SENTENCES == 4


def test_the_largest_reason_is_named_as_such():
    said = language.why_sentences(_item([
        ("mlb_starter_rolling_perf", 5.0), ("mlb_park_factor", 0.1),
    ]), PHRASES)
    assert "the biggest reason" in said[0]
    assert "the biggest reason" not in said[1]


def test_a_factor_with_no_template_is_skipped_rather_than_printed_raw():
    said = language.why_sentences(
        _item([("some_undeclared_factor", 0.9), ("mlb_park_factor", 0.4)]),
        PHRASES,
    )
    assert len(said) == 1
    assert "some_undeclared_factor" not in said[0]


def test_an_absent_factor_becomes_one_clause():
    clause = language.why_absent(
        {"absent_factors": ["mlb_starter_rolling_perf", "mlb_park_factor"]},
        PHRASES,
    )
    assert clause == (
        "The starting pitching matchup and how much scoring this park allows "
        "could not be measured for this game."
    )


def test_nothing_absent_means_no_clause():
    assert language.why_absent({"absent_factors": []}, PHRASES) is None


# --- the market clause -----------------------------------------------------

def test_the_market_clause_appears_only_where_a_line_exists():
    with_line = language.why_market({
        "subject": "TB", "market_type": "moneyline", "model_prob": 0.57,
        "market_implied_prob": 0.48, "team_names": {"TB": "Tampa Bay Rays"},
    })
    assert "Tampa Bay Rays at 48%" in with_line
    assert "heavier" in with_line
    assert language.why_market({
        "subject": "TB", "market_type": "moneyline", "model_prob": 0.57,
        "market_implied_prob": None,
    }) is None


# --- THE CONSISTENCY GUARD -------------------------------------------------

def _agrees(item, sentences):
    """Does the prose agree with the arithmetic it was built from?

    The invariant: the FIRST sentence names the factor with the largest
    absolute contribution, and its direction matches that contribution's sign
    once the taken side is accounted for.
    """
    contribs = [c for c in item["contributions"] if not c.get("missing")]
    if not contribs or not sentences:
        return False
    top = max(contribs, key=lambda c: abs(c["contribution"]))
    phrase = PHRASES.get(top["factor"])
    if not phrase:
        return False
    first = sentences[0]
    named = first.lower().startswith(phrase.lower())
    signed = top["contribution"] * (-1 if language.why_is_flipped(item) else 1)
    directed = ("helps the pick" in first) == (signed > 0)
    return named and directed


def test_the_words_agree_with_the_contributions_they_came_from():
    item = _item([("mlb_starter_rolling_perf", 0.90), ("mlb_park_factor", -0.40)])
    assert _agrees(item, language.why_sentences(item, PHRASES))


def test_a_planted_mismatch_is_caught():
    """PLANTED. Hand the checker prose that names the wrong factor, and prose
    that names the right one in the wrong direction. Both must fail."""
    item = _item([("mlb_starter_rolling_perf", 0.90), ("mlb_park_factor", -0.40)])
    sound = language.why_sentences(item, PHRASES)
    assert _agrees(item, sound)

    wrong_factor = ["How much scoring this park allows helps the pick — the biggest reason."]
    assert not _agrees(item, wrong_factor), "prose naming the wrong factor passed"

    wrong_direction = [sound[0].replace("helps the pick", "works against it")]
    assert not _agrees(item, wrong_direction), "prose with the sign flipped passed"


def test_the_generated_why_agrees_on_every_prediction_in_the_record():
    """Over the real record, not a fixture. The same sweep shape as K1: if the
    words and the arithmetic can disagree anywhere, they do so here."""
    import json

    from gridiron import config, db

    conn = db.open_db(config.DB_PATH)
    try:
        rows = conn.execute(
            "SELECT market_type, prop_type, subject, model_side, model_prob,"
            " factors_json FROM predictions WHERE predictor = 'statistical'"
        ).fetchall()
        assert rows, "no predictions to check — this would pass vacuously"

        checked = 0
        for r in rows:
            payload = json.loads(r["factors_json"])
            item = {
                "subject": r["subject"], "market_type": r["market_type"],
                "prop_type": r["prop_type"], "model_side": r["model_side"],
                "model_prob": r["model_prob"],
                "contributions": payload.get("contributions") or [],
            }
            sentences = language.why_sentences(item, PHRASES)
            if not sentences:
                continue
            checked += 1
            assert _agrees(item, sentences), (
                f"{r['subject']} {r['market_type']}: the words disagree with "
                f"the contributions they were built from"
            )
        assert checked > 0, "no prediction produced any reasons"
    finally:
        conn.close()


# --- the block the card renders --------------------------------------------

def test_the_heading_names_the_side_actually_taken():
    picked = language.why_block(_item(
        [("mlb_starter_rolling_perf", 0.9)], side="lose",
        opponent="COL", team_names={"TB": "Tampa Bay Rays", "COL": "Colorado Rockies"},
    ), PHRASES)
    assert picked["heading"] == "Why Colorado Rockies"


def test_the_block_carries_the_link_to_the_factors_page():
    block = language.why_block(_item([("mlb_park_factor", 0.4)]), PHRASES)
    assert block["more_label"] == "How the model works"
    assert block["more_href"] == "#/factors"
