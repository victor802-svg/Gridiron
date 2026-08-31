"""R1: the tier table IS the record.

The Record tab used to open with a calibration chart — the right shape for
auditing the model, the wrong shape for the question a reader has, which is
"when it says STRONG, is it?". This is that question as a table, in the same
vocabulary the chips on every pick already use.

ONE ROW PER BAND, NOT PER TIER. The brief that asked for this called the
buckets and the tiers "the same partition (LEAN 50-60, SOLID 60-70, STRONG
70%+)". They are not: STRONG spans 70-80% AND 80%+. Pooling them into one row
is the merge LAW 4 forbids and it flatters in a predictable direction, so
STRONG appears twice, labelled with its band.
"""

from __future__ import annotations

import pytest

from gridiron import calibration as C, config, db


@pytest.fixture()
def conn(tmp_path):
    connection = db.open_db(tmp_path / "tiers.db")
    yield connection
    connection.close()


# --- the partition ---------------------------------------------------------

def test_strong_spans_two_bands_and_they_are_reported_separately(conn):
    t = C.tier_table(conn, sport="nfl", market_type="spread")
    bands = [(r["tier"], r["band"]) for r in t["rows"]]
    assert bands == [
        ("LEAN", "50-60%"), ("SOLID", "60-70%"),
        ("STRONG", "70-80%"), ("STRONG", "80%+"),
    ]
    strong = [r for r in t["rows"] if r["tier"] == "STRONG"]
    assert len(strong) == 2, (
        "STRONG pooled into one row: the easier band would lift the harder one"
    )


def test_the_table_has_a_row_for_every_declared_bucket(conn):
    t = C.tier_table(conn, sport="nfl", market_type="spread")
    assert [r["band"] for r in t["rows"]] == [b[2] for b in C.BUCKETS]


# --- LAW 4: below the gate, no numbers -------------------------------------

@pytest.mark.parametrize("n", [0, 1, 9, 19])
def test_a_band_below_the_gate_shows_no_percentages(n):
    verdict = C.tier_verdict(0.75, 0.90, n)
    assert verdict == f"unproven — {n} of {C.TIER_MIN_SETTLED}"
    assert "%" not in verdict


def test_a_band_below_the_gate_carries_no_claimed_or_actual(conn):
    """Not merely hidden by the renderer: ABSENT from the payload, so there is
    no number for a future template to reach for."""
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, home_score, away_score, league_date)"
        " VALUES ('nfl_1','nfl',2025,1,'REG','2025-09-07T17:00:00Z','KC','BUF',"
        " 'final',24,20,'2025-09-07')"
    )
    # Distinct subjects: the schema refuses two predictions on the same
    # question by the same forecaster, which is LAW 3 doing its job.
    for i in range(3):
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor,"
            " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
            " VALUES ('2025-09-01T00:00:00Z','nfl','nfl_1','spread',?,-3.5,"
            " 0.75,'cover','statistical','fs2','{}','because',"
            " '2025-09-08T00:00:00Z',1)",
            (f"KC{i}",),
        )
    conn.commit()
    t = C.tier_table(conn, sport="nfl", market_type="spread")
    row = next(r for r in t["rows"] if r["band"] == "70-80%")
    assert row["n"] == 3
    assert row["proven"] is False
    assert row["claimed"] is None and row["actual"] is None and row["right"] is None


# --- the verdict rule ------------------------------------------------------

@pytest.mark.parametrize("claimed,actual,expected", [
    (0.55, 0.55, "about as good as it claims"),
    (0.53, 0.50, "about as good as it claims"),      # exactly 3 points
    (0.60, 0.70, "better than it claims"),
    (0.70, 0.60, "much more confident than it should be"),
])
def test_the_verdict_words_follow_the_declared_rule(claimed, actual, expected):
    assert C.tier_verdict(claimed, actual, 40) == expected


def test_an_overconfident_band_states_the_size_of_the_miss():
    said = C.tier_verdict(0.55, 0.515, 40)
    assert said.startswith("overconfident by")
    assert "3.5 points" in said


def test_the_boundary_is_decided_by_the_threshold_not_by_float_error():
    """0.53 - 0.50 is 3.0000000000000027 in binary floating point, which put a
    gap the rule calls close enough on the wrong side of its own band."""
    assert C.tier_verdict(0.53, 0.50, 40) == "about as good as it claims"


def test_the_thresholds_are_dated_constants():
    assert C.VERDICT_BANDS_DECLARED.startswith("2026-08-31")
    assert C.VERDICT_CLOSE_ENOUGH == 3.0
    assert C.VERDICT_BADLY_OFF == 8.0


def test_no_verdict_leaks_an_internal_identifier():
    from gridiron import audit

    for claimed, actual, n in ((0.55, 0.55, 40), (0.70, 0.60, 40),
                               (0.55, 0.515, 40), (0.5, 0.5, 3)):
        hits = audit.plain_words_violations(C.tier_verdict(claimed, actual, n))
        assert not hits, hits


# --- the headline ----------------------------------------------------------

def test_the_headline_names_the_largest_gap_not_the_flattering_band():
    rows = [
        {"tier": "LEAN", "band": "50-60%", "n": 40, "proven": True,
         "claimed": 0.55, "actual": 0.54, "verdict": "about as good as it claims"},
        {"tier": "STRONG", "band": "70-80%", "n": 40, "proven": True,
         "claimed": 0.75, "actual": 0.55, "verdict": "much more confident than it should be"},
    ]
    said = C._tier_headline(rows)
    assert "STRONG" in said and "70-80%" in said
    assert "much more confident" in said


def test_with_nothing_proven_the_headline_says_so_rather_than_grading():
    rows = [{"tier": "LEAN", "band": "50-60%", "n": 4, "proven": False,
             "claimed": None, "actual": None, "verdict": "unproven — 4 of 20"}]
    said = C._tier_headline(rows)
    assert "No band" in said and "4" in said
    assert "%" not in said


def test_an_empty_record_says_nothing_has_resolved():
    said = C._tier_headline(
        [{"tier": "LEAN", "band": "50-60%", "n": 0, "proven": False,
          "claimed": None, "actual": None, "verdict": "unproven — 0 of 20"}]
    )
    assert said == "Nothing has resolved yet, so there is nothing to grade."


# --- ONE IMPLEMENTATION: the table and the chips cannot drift --------------

def test_the_table_numbers_equal_the_chip_numbers_to_the_decimal():
    """Both call `bucket_record`. This asserts it, over the real record, so a
    future reimplementation that 'happens to agree' is caught."""
    conn = db.open_db(config.DB_PATH)
    try:
        for sport in config.SPORTS:
            for market in config.SPORT_MARKETS.get(sport, ()):
                mt = C.market_type_of(sport, market)
                pt = C.prop_type_of(sport, market)
                table = C.tier_table(conn, sport=sport, market_type=mt, prop_type=pt)
                for row in table["rows"]:
                    lo, hi = next((lo, hi) for lo, hi, name in C.BUCKETS
                                  if name == row["band"])
                    chip = C.bucket_record(
                        conn, (lo + min(hi, 1.0)) / 2.0, sport=sport,
                        market_type=mt, prop_type=pt, predictor="statistical",
                    )
                    assert row["n"] == chip["n"], f"{sport}/{market}/{row['band']}"
                    if row["proven"]:
                        assert row["actual"] == chip["actual"]
                        assert row["claimed"] == chip["claimed"]
                    # ...and the tier label agrees with the chip's own mapping
                    tier = C.tier_from_bucket(chip)
                    assert row["tier"] == tier["tier"], (
                        f"{sport}/{market}/{row['band']}: table says "
                        f"{row['tier']}, chip says {tier['tier']}"
                    )
    finally:
        conn.close()


def test_the_scorecard_carries_the_table_and_passes_its_validators():
    conn = db.open_db(config.DB_PATH)
    try:
        payload = C.scorecard(conn, sport="mlb")
        assert payload["tier_table"]["rows"]
        C.assert_every_figure_has_n(payload)
        C.assert_single_sport(payload, "mlb")
    finally:
        conn.close()


def test_the_table_is_per_sport_and_refuses_to_be_asked_without_one(conn):
    with pytest.raises(Exception):
        C.tier_table(conn, sport=None, market_type="spread")
