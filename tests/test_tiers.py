"""T3: confidence tiers, and the two things they must never do.

A tier chip sits directly beside a specific forecast, which makes it the most
persuasive element on the page. Two failures matter:

  * showing a hit rate before the tier has earned one — a "64%" on nine settled
    picks reads as a track record for the pick next to it;
  * drifting from the record page, so the card says one number and the chart
    says another about the same bucket.

Both are prevented structurally: the tier is DERIVED from `bucket_record`, the
same function the chart uses, and it refuses to state an earned figure below the
threshold.
"""

from __future__ import annotations

import pytest

from gridiron import audit, calibration, config, db, language, views


def _seed_bucket(conn, sport, n, hits, prob=0.75):
    """n resolved predictions in one bucket, `hits` of them correct."""
    games = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM games WHERE sport = ? AND status='final' LIMIT ?",
            (sport, n),
        )
    ]
    assert len(games) >= n, f"fixture has only {len(games)} finished games"
    for i, game in enumerate(games[:n]):
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, model_prob, model_side, predictor, factor_set_version,"
            " factors_json, reasoning, resolved_utc, outcome)"
            " VALUES (?,?,?,'moneyline',?,?,'win','statistical',?,'{}','x',?,?)",
            (db.utcnow(), sport, game, f"S{i}", prob, config.FACTOR_SET_VERSION,
             db.utcnow(), 1 if i < hits else 0),
        )
    conn.commit()


# --- the gate ---------------------------------------------------------------

def test_a_tier_below_the_gate_states_the_shortfall_not_a_hit_rate(mlb_league):
    _seed_bucket(mlb_league, "mlb", 19, 12)
    bucket = calibration.bucket_record(
        mlb_league, 0.75, sport="mlb", market_type="moneyline"
    )
    tier = calibration.tier_from_bucket(bucket)
    assert tier["n"] == 19
    assert tier["proven"] is False
    assert tier["earned"] is None, "a tier stated a hit rate below its gate"
    assert tier["message"] == "tier unproven - 19 settled of 20 needed"
    assert "%" not in tier["message"]


def test_exactly_twenty_flips_the_tier_to_its_earned_figure(mlb_league):
    """19 does not and 20 does. The boundary is the whole point of a gate."""
    _seed_bucket(mlb_league, "mlb", 20, 13)
    bucket = calibration.bucket_record(
        mlb_league, 0.75, sport="mlb", market_type="moneyline"
    )
    tier = calibration.tier_from_bucket(bucket)
    assert tier["n"] == 20
    assert tier["proven"] is True
    assert tier["earned"] == round(13 / 20, 4)
    assert tier["message"] == "this tier hits 65% over 20 settled"


def test_the_tier_figure_is_the_record_pages_own_bucket_maths(mlb_league):
    """One implementation. The chip and the chart cannot disagree because they
    are the same function called twice."""
    _seed_bucket(mlb_league, "mlb", 24, 15)
    bucket = calibration.bucket_record(
        mlb_league, 0.75, sport="mlb", market_type="moneyline"
    )
    tier = calibration.tier_from_bucket(bucket)

    curve = calibration.curve(mlb_league, sport="mlb", market_type="moneyline")
    point = next(b for b in curve["buckets"] if b["label"] == bucket["label"])
    assert tier["earned"] == point["actual"], (
        f"the card says {tier['earned']} and the chart says {point['actual']}"
    )
    assert tier["n"] == point["n"]


# --- the mapping ------------------------------------------------------------

@pytest.mark.parametrize(
    "probability, expected",
    [(0.52, "LEAN"), (0.59, "LEAN"), (0.60, "SOLID"), (0.69, "SOLID"),
     (0.70, "STRONG"), (0.85, "STRONG")],
)
def test_the_tier_follows_the_claimed_confidence(probability, expected):
    label = calibration.bucket_label(probability)
    assert calibration.TIERS[label] == expected


def test_strong_spans_two_buckets_and_each_keeps_its_own_number():
    """Pooling 70-80% with 80%+ into one STRONG hit rate would be the merge LAW
    4 forbids, and it would flatter: the easier bucket lifts the harder one."""
    assert calibration.TIERS["70-80%"] == "STRONG"
    assert calibration.TIERS["80%+"] == "STRONG"
    a = calibration.tier_from_bucket({"label": "70-80%", "n": 40, "actual": 0.60})
    b = calibration.tier_from_bucket({"label": "80%+", "n": 40, "actual": 0.90})
    assert a["earned"] != b["earned"], "two buckets were pooled into one figure"
    assert a["bucket"] != b["bucket"]


def test_the_threshold_is_the_charts_threshold_not_a_second_one():
    assert calibration.TIER_MIN_SETTLED == config.MIN_SAMPLE_FOR_BUCKET_POINT


# --- LAW 5 ------------------------------------------------------------------

def test_no_stake_or_unit_surface_anywhere_in_the_tier_code(mlb_league):
    """Tiers are the closest this project comes to the thing LAW 5 forbids, so
    the ban is asserted where the temptation is."""
    from gridiron import audit

    audit.check_not_a_betting_tool()

    card_tier = calibration.tier_from_bucket(
        {"label": "70-80%", "n": 41, "actual": 0.64}
    )
    for banned in ("unit", "stake", "bankroll", "wager", "payout", "$"):
        assert banned not in repr(card_tier).lower(), (
            f"the tier payload carries {banned!r}"
        )


def test_the_card_payload_carries_a_tier_and_no_stake(mlb_league):
    week = mlb_league.execute(
        "SELECT MIN(week) AS w FROM games WHERE sport='mlb' AND status='scheduled'"
    ).fetchone()["w"]
    payload = views.week(mlb_league, "mlb", 2025, week)
    for card in payload["cards"]:
        assert "tier" in card
        for banned in ("stake", "units", "bankroll", "payout"):
            assert banned not in repr(card).lower()


# ---------------------------------------------------------------------------
# STRONG BY DEFAULT (ruling R2, 2026-09-02)
#
# Picks opens on the most confident band rather than on the whole slate. That
# is a convenience with a cost: the band a reader lands on is also the one
# with the fewest settled rows behind it, and a filter nobody chose is the
# kind that misreads as a thin night. Both halves are tested here -- the count
# line that names what it narrowed, and the caveat that says the band is
# young until it stops being true.
# ---------------------------------------------------------------------------


def test_picks_opens_on_the_strongest_band(mlb_league):
    assert config.PICKS_DEFAULT_TIER == "STRONG"
    payload = views.week(mlb_league, "mlb")
    assert payload["default_tier"] == "STRONG"


def test_the_default_never_hides_what_it_filtered(mlb_league):
    """The count line names the whole slate, not only the band."""
    assert audit.tier_count_faults(views.week(mlb_league, "mlb")) == []

    # And the composer itself, on a slate that HAS bands to filter: four
    # STRONG picks out of forty-six is the example ruling R2 gives.
    cards = ([{"market": "moneyline", "tier": {"tier": "STRONG"}}] * 4
             + [{"market": "moneyline", "tier": {"tier": "LEAN"}}] * 42)
    lines = views._count_lines(cards)
    assert lines["|STRONG"] == "STRONG · 4 of 46 picks"
    assert lines["|"] == "46 picks"
    assert audit.tier_count_faults(
        {"default_tier": "STRONG", "glance": {"count_lines": lines}}) == []


def test_a_count_line_with_no_denominator_is_caught_by_name():
    payload = {"default_tier": "STRONG",
               "glance": {"count_lines": {"|STRONG": "4 picks"}}}
    faults = audit.tier_count_faults(payload)
    assert len(faults) == 1
    assert "names no denominator" in faults[0]
    assert "'|STRONG'" in faults[0]


def test_a_part_larger_than_its_whole_is_caught():
    payload = {"default_tier": "STRONG",
               "glance": {"count_lines": {"|STRONG": "STRONG - 9 of 4 picks"}}}
    faults = audit.tier_count_faults(payload)
    assert len(faults) == 1
    assert "cannot exceed its whole" in faults[0]


def test_an_unfiltered_count_needs_no_denominator():
    """"45 picks" hides nothing -- there is no whole behind it to name."""
    payload = {"default_tier": "STRONG",
               "glance": {"count_lines": {"|": "45 picks"}}}
    assert audit.tier_count_faults(payload) == []


def test_the_caveat_names_the_band_and_the_shortfall():
    said = language.least_tested_tier_line("STRONG", 3, 20)
    assert said is not None
    assert "STRONG" in said and "3" in said and "20" in said
    assert "%" not in said, "a caveat about sample size stated a rate"


def test_the_caveat_disappears_once_the_band_earns_its_verdict():
    """A caveat that outlives its reason is furniture."""
    assert language.least_tested_tier_line("STRONG", 20, 20) is None
    assert language.least_tested_tier_line("STRONG", 41, 20) is None


def test_the_caveat_goes_when_the_band_clears_its_gate(mlb_league):
    """Seeded through the record, not asserted about the composer."""
    assert views.week(mlb_league, "mlb")["tier_caveat"] is not None
    _seed_bucket(mlb_league, "mlb", calibration.TIER_MIN_SETTLED, 15, prob=0.78)
    assert views.week(mlb_league, "mlb")["tier_caveat"] is None
