"""Session E: the walk-forward said no, and this keeps that answer binding.

WHAT WAS TESTED. `docs/DISTRIBUTIONAL.md` proposed replacing the rung with a
forecast distribution: write the mean and spread blind, then read P(over the
market's line) off it. The structural argument was strong -- a rung asked at
our own expectation confines P(over) to 45.8%-54.2%, while a read-out spans
3.4%-93.8%.

WHAT THE WALK-FORWARD FOUND. On 3,947 out-of-sample games across four arms,
the read-out was worse calibrated EVERY TIME, by 6 to 13 percentage points,
with a negative edge over always-the-base-rate in all four. The distributions
themselves were honest -- every PIT came back flat -- and that is the finding:
a distribution can be perfectly honest about its own error and still produce
badly calibrated probabilities at somebody else's number, because that number
is not a random point. It is a better forecast.

SO NOTHING SHIPPED, and these tests exist to keep it that way until a
walk-forward says otherwise.
"""

from __future__ import annotations

import pytest

from gridiron import audit, config
from gridiron.model import questions


# --- the verdicts ------------------------------------------------------------

def test_nothing_ships_and_the_record_says_why():
    """The result of Session E Part 2, asserted rather than remembered."""
    assert config.DISTRIBUTIONAL_MARKETS == frozenset(), (
        "a market is running distributionally; the walk-forward refused all "
        "four arms on 2026-09-04")
    for (sport, market), entry in config.DISTRIBUTIONAL_VERDICTS.items():
        assert entry["verdict"] in ("SHIP", "DO NOT SHIP", "NOT RUN")
        assert entry["why"], f"{sport}:{market} has a verdict and no reason"


@pytest.mark.parametrize("sport,market", [
    ("nfl", "total"), ("nfl", "spread"), ("nba", "total"), ("nba", "spread"),
])
def test_every_arm_that_ran_carries_its_evidence(sport, market):
    """LAW 4's habit applied to a decision: no verdict without its numbers."""
    entry = config.distributional_verdict(sport, market)
    assert entry is not None
    assert entry["verdict"] == "DO NOT SHIP"
    assert entry["n"] >= config.MIN_SAMPLE_FOR_EDGE_CLAIM, (
        f"{sport}:{market} decided on {entry['n']} games, below the "
        f"{config.MIN_SAMPLE_FOR_EDGE_CLAIM} this project requires of a claim")
    # The read-out lost, and by how much is on the record.
    assert entry["readout_gap_pts"] > entry["rung_gap_pts"]
    assert entry["readout_edge"] < 0
    # And the distribution itself was honest, which is the interesting half.
    assert entry["pit_flat"] is True


def test_the_distributions_were_honest_and_that_is_the_finding():
    """Every arm's PIT was flat. The forecast spread is right for the mean.

    This is asserted on its own because it is the part a later reader will
    most easily get backwards: the redesign did not fail because the model
    lied about its own uncertainty. It failed at the step after.
    """
    ran = [e for e in config.DISTRIBUTIONAL_VERDICTS.values()
           if e["verdict"] == "DO NOT SHIP"]
    assert len(ran) == 4
    assert all(e["pit_flat"] is True for e in ran)
    assert all(e["market_closer_share_pct"] > 50 for e in ran), (
        "the market's number was closer more often than ours in every arm, "
        "which is why reading a probability off our distribution at their "
        "number produced confident wrong claims")


def test_cfb_was_refused_by_its_own_expectation_not_by_line_coverage():
    """The brief said "fit it first, then include CFB". The fit answered."""
    entry = config.distributional_verdict("cfb", "total")
    assert entry["verdict"] == "NOT RUN"
    assert "0.93%" in entry["why"] or "0.109" in entry["why"]


# --- the guard ---------------------------------------------------------------

def test_the_verdicts_and_the_markets_agree():
    audit.check_distributional_verdicts()


def test_the_guard_sees_a_market_shipped_without_a_verdict():
    original = config.DISTRIBUTIONAL_MARKETS
    try:
        config.DISTRIBUTIONAL_MARKETS = frozenset({("nfl", "total")})
        assert audit.distributional_verdict_faults()
    finally:
        config.DISTRIBUTIONAL_MARKETS = original
    assert audit.distributional_verdict_faults() == []


def test_the_guard_sees_a_ship_verdict_its_numbers_refuse():
    """A decision rule that can be edited after the numbers is not a rule."""
    key = ("nfl", "total")
    original = dict(config.DISTRIBUTIONAL_VERDICTS[key])
    try:
        config.DISTRIBUTIONAL_VERDICTS[key] = {**original, "verdict": "SHIP"}
        faults = audit.distributional_verdict_faults()
        assert any("WORSE calibrated" in f for f in faults), faults
    finally:
        config.DISTRIBUTIONAL_VERDICTS[key] = original


def test_the_guard_sees_a_ladder_deleted_under_a_market_still_on_rungs():
    """The likelier accident: a migration that half-lands."""
    saved = questions.NFL_TOTAL_LADDER
    try:
        questions.NFL_TOTAL_LADDER = None
        faults = audit.distributional_verdict_faults()
        assert any("is gone" in f for f in faults), faults
    finally:
        questions.NFL_TOTAL_LADDER = saved
    assert audit.distributional_verdict_faults() == []


def test_every_market_with_a_verdict_has_a_known_ladder():
    """A market the migration check cannot see is a market it does not check."""
    for key in config.DISTRIBUTIONAL_VERDICTS:
        assert key in audit.LADDERS_BY_MARKET, (
            f"{key} has a verdict and no entry in LADDERS_BY_MARKET")


# --- the measured spreads ----------------------------------------------------

def test_the_forecast_spread_is_declared_dated_and_refuses_a_guess():
    assert questions.FORECAST_SPREAD_DECLARED
    assert questions.forecast_spread("nfl", "total") == 14.28
    with pytest.raises(questions.UnmeasuredForecastSpread):
        questions.forecast_spread("mlb", "total")


def test_the_forecast_spread_is_not_the_market_residual():
    """The mistake this project has already made once, at 4.71 vs 4.534.

    `MARGIN_SD_BY_SPORT` holds SD(actual - THE MARKET'S line); `FORECAST_SPREAD`
    holds SD(actual - OUR expectation). The market forecasts better than we do,
    so ours must be the wider of the two -- and if they were ever equal it
    would mean somebody had copied one into the other.
    """
    from gridiron.market import lines

    for sport in ("nfl", "nba"):
        ours = questions.forecast_spread(sport, "spread")
        theirs = lines.margin_sd(sport)
        assert ours > theirs, (
            f"{sport}: our forecast spread {ours} is not wider than the "
            f"market's residual {theirs}, which would mean we forecast the "
            f"margin at least as well as the market does")


def test_every_measured_spread_carries_its_sample_size():
    assert set(questions.FORECAST_SPREAD) == set(questions.FORECAST_SPREAD_N)
    for key, n in questions.FORECAST_SPREAD_N.items():
        assert n >= config.MIN_SAMPLE_FOR_EDGE_CLAIM, key


def test_neither_mlb_nor_cfb_totals_got_a_gaussian():
    """Both were refused, for different measured reasons.

    MLB's total is right-skewed at +0.64 -- runs are counts and a symmetric
    distribution cannot hold that shape. CFB's expectation explains under 1%
    of the variance, so there is no forecast to put a distribution around.
    """
    assert ("mlb", "total") not in questions.FORECAST_SPREAD
    assert ("cfb", "total") not in questions.FORECAST_SPREAD


# --- the stale comment, and the arithmetic that found it ---------------------

def test_cfb_reads_the_fitted_margin_and_the_comment_now_says_so():
    """The comment claimed the opposite for three days.

    Caught by arithmetic rather than by reading: the CFB margin's measured
    bias is +0.05, and the pre-fit constants (intercept 9.79 against the
    fitted 4.85) would have produced a bias of roughly five points.
    """
    src = (config.PACKAGE_ROOT / "model" / "questions.py").read_text(
        encoding="utf-8")
    assert "CFB'S ENTRY IS RECORDED AND NOT YET USED" not in src
    assert "CFB'S ENTRY IS LIVE" in src

    intercept, slope = questions.EXPECTED_MARGIN_FIT["cfb"]
    assert questions.cfb_expected_margin(10.0, 0.0) == pytest.approx(
        intercept + slope * 10.0)
    assert intercept != questions.CFB_HOME_MARGIN_ASSUMED


# --- the rulings on the result (2026-09-04) ---------------------------------

def test_the_finding_reached_methodology_in_plain_words():
    """RULING 1. A finding that stays in a close-out is a finding nobody
    reads. `METHODOLOGY.md` §6 is where this project says what it believes
    about itself, and it keeps a section for the unflattering ones."""
    text = (config.PACKAGE_ROOT.parent / "docs" / "METHODOLOGY.md").read_text(
        encoding="utf-8")
    assert "the market was closer on" in text
    for share in ("57%", "59%", "55%"):
        assert share in text, f"the market-closer figure {share} is missing"
    assert "Being able to say something is not the same as being right" in text

    # PLAIN WORDS, in a document a reader consults rather than a log.
    for jargon in ("PIT", "calibration gap", "read-out", "Brier score of the"):
        assert jargon not in text.split("## 6.")[1].split("## 7.")[0], jargon


def test_cfbs_slope_is_recorded_and_not_adopted():
    """RULING 2. The brief said fit it first; the fit refused the market."""
    fit = questions.CFB_TOTAL_FIT_MEASURED
    assert fit["adopted"] is False
    assert fit["r2"] == 0.0093
    assert fit["n"] >= config.MIN_SAMPLE_FOR_EDGE_CLAIM
    assert fit["measured_utc"]
    assert fit["why_not_adopted"]

    # AND IT IS NOT SILENTLY IN USE. `cfb_total_asked` still adds two
    # points-per-game figures; a slope of 0.109 would flatten every college
    # total onto the league average.
    plain = questions.cfb_total_asked(30.0, 30.0)
    assert plain is not None and plain > 55, (
        "cfb_total_asked has started applying the fitted slope; two sides "
        "averaging 30 a game would be asked at about 50 rather than 60")


def test_cfb_keeps_asking_totals_at_a_rung_and_says_what_it_is_worth():
    """RULING 2's second half: shown as such, not hidden."""
    assert "total" in config.SPORT_MARKETS["cfb"]
    assert config.flagged_method("cfb", "total") == "total_at_own_rung"
    assert not config.is_distributional("cfb", "total")

    from gridiron import language
    assert language.method_note(config.flagged_method("cfb", "total"))


def test_the_guard_sees_a_weak_market_withdrawn():
    original = config.SPORT_MARKETS["cfb"]
    try:
        config.SPORT_MARKETS["cfb"] = tuple(m for m in original if m != "total")
        faults = audit.hidden_market_faults()
        assert faults and any("cfb:total" in f for f in faults), faults
    finally:
        config.SPORT_MARKETS["cfb"] = original
    assert audit.hidden_market_faults() == []


def test_a_verdict_is_not_a_judgement_on_the_market():
    """The bug the first version of `hidden_market_faults` had.

    `DISTRIBUTIONAL_VERDICTS` records whether the READ-OUT beat the rung, not
    whether the market is any good. The NFL spread is refused there and is the
    market this project was built on, with a walk-forward calibration gap of
    1.93 points against the totals' 0.35-to-3.98 range.
    """
    assert config.distributional_verdict("nfl", "spread")["verdict"] == "DO NOT SHIP"
    assert config.flagged_method("nfl", "spread") is None, (
        "a spread has picked up the coin-flip flag; that finding is about "
        "totals asked at their own rung, and a spread is not one")
    assert audit.hidden_market_faults() == []


# --- no confidence floor on game markets (ruling 3) -------------------------

def test_no_floor_is_declared_for_game_markets():
    assert config.GAME_MARKET_MIN_CLAIM is None
    assert config.GAME_MARKET_MIN_CLAIM_DECLARED
    # And props keep theirs, which is a different situation for a stated reason.
    assert config.PROPS_MIN_CLAIM == 0.70


def test_no_floor_reaches_a_game_market():
    audit.check_no_floor_on_game_markets()


def test_the_guard_sees_a_floor_set_on_game_markets():
    original = config.GAME_MARKET_MIN_CLAIM
    try:
        config.GAME_MARKET_MIN_CLAIM = 0.60
        assert audit.game_market_floor_faults()
    finally:
        config.GAME_MARKET_MIN_CLAIM = original
    assert audit.game_market_floor_faults() == []


def test_the_guard_sees_the_props_floor_escape_its_branch():
    """The regex version could not, and that is why this is an AST walk.

    `predict.py` has TWO `market_type == "prop"` branches. A pattern that
    matched the phrase and the floor separately stayed satisfied by the first
    one while the floor was lifted out of the second -- so the planting
    escaped, and the guard was reporting on a branch that was not the one
    doing the work.
    """
    source = (config.PACKAGE_ROOT / "model" / "predict.py").read_text(
        encoding="utf-8")
    assert audit.game_market_floor_faults(source) == []

    nl = chr(10)
    before = nl.join(['        if q.market_type == "prop":',
                      '            _side, claimed = baseline.stated_side('])
    after = nl.join(['        if True:',
                     '            _side, claimed = baseline.stated_side('])
    broken = source.replace(before, after, 1)
    assert broken != source, "the floor's branch has moved; re-point this test"
    faults = audit.game_market_floor_faults(broken)
    assert faults and "player prop" in faults[0], faults


def test_the_floor_guard_counts_both_constants():
    """A floor by another name is still a floor."""
    assert set(audit.FLOOR_CONSTANTS) == {"PROPS_MIN_CLAIM",
                                          "GAME_MARKET_MIN_CLAIM"}


# --- the tier chip, measured (2026-09-04) -----------------------------------

def test_the_chip_says_whether_it_is_a_record_or_a_claim():
    """MEASURED: 17 of 379 live chips had a settled record behind them.

    Ruling 3 declined a confidence floor on the argument that a reader is told
    what a claim is WORTH instead of having weak claims hidden. The chip is the
    thing doing the telling, so a chip that cannot tell them takes the argument
    with it.
    """
    from gridiron import language

    assert language.tier_chip_label("STRONG", True) == "STRONG"
    assert language.tier_chip_label("STRONG", False) != "STRONG"
    assert "unproven" in language.tier_chip_label("STRONG", False)
    assert language.tier_chip_label(None, False) == ""
    # NO SECOND NUMBER on the chip: the cards brief's R2 is about figures.
    assert not any(ch.isdigit()
                   for ch in language.tier_chip_label("STRONG", False))


def test_the_chip_label_travels_on_the_tier_itself():
    """One door: composed where the tier is built, not per caller."""
    from gridiron import calibration

    unproven = calibration.tier_from_bucket(
        {"label": "70-80%", "n": 3, "actual": 0.5})
    assert unproven["chip_label"] == "STRONG · unproven"
    assert unproven["proven"] is False

    proven = calibration.tier_from_bucket(
        {"label": "70-80%", "n": calibration.TIER_MIN_SETTLED, "actual": 0.74})
    assert proven["chip_label"] == "STRONG"
    assert proven["proven"] is True


def test_the_shipped_chip_still_says_what_it_is():
    audit.check_the_chip_says_what_it_is()


def test_the_guard_sees_a_chip_that_hides_its_emptiness():
    source = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert audit.tier_chip_faults(source) == []

    broken = source.replace("tier.chip_label || tier.tier", "tier.tier", 1)
    broken = broken.replace(
        "if (!tier.proven) chip.classList.add('tier-unproven');", "", 1)
    assert broken != source, "the chip has moved; re-point this test"
    assert len(audit.tier_chip_faults(broken)) >= 2


def test_the_guard_is_not_satisfied_by_its_own_comment():
    """The failure `_caller_sources` documents, met again here.

    `tierChip` carries a paragraph explaining why it renders `chip_label`. The
    first version of this scan read the whole function body, so that paragraph
    satisfied the check and deleting the actual code left the guard green.
    """
    nl = chr(10)
    only_a_comment = nl.join([
        "  function tierChip(tier) {",
        "    // renders chip_label and marks tier-unproven, honest",
        "    const chip = el('span', 'tier', tier.tier);",
        "    chip.title = tier.message || '';",
        "    return chip;",
        "  }",
    ])
    faults = audit.tier_chip_faults(only_a_comment)
    assert len(faults) >= 2, (
        f"a function that only TALKS about chip_label passed the scan: {faults}")


def test_the_measurement_tool_reads_the_live_slate():
    """The tool the operator asked for, run against the record it measures."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "measure_tier_chip",
        Path(config.PACKAGE_ROOT).parent / "tools" / "measure_tier_chip.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    from gridiron import db as _db
    conn = _db.connect()
    try:
        result = module.measure_sport(conn, "nfl")
    finally:
        conn.close()
    assert "cards" in result
    if result.get("cards"):
        # Every card carries a chip; that is the first of the three questions.
        assert sum(m["no_chip"] for m in result["markets"].values()) == 0


# --- fix 1: an absent factor is not a zero (2026-09-05) ---------------------

def test_the_prompt_never_hands_absence_over_as_a_number():
    audit.check_the_prompt_keeps_absence_absent()


def test_the_ufc_zero_was_correct_all_along():
    """The question fix 1 asked, answered in a test so it stays answered.

    A reasoning row read "This is a three-round bout (ufc_scheduled_rounds =
    0)" and the zero was suspected of being a silent default. It was not:
    the factor is a declared INDICATOR, 1.0 for five rounds and 0.0 for three,
    and its own rationale says so. The zero was right and the PRESENTATION was
    what misled -- a code name and an encoded number quoted into prose.
    """
    from gridiron.factors import registry
    import gridiron.factors.ufc  # noqa: F401

    entry = registry.REGISTRY["ufc_scheduled_rounds"]
    assert "scaled so five reads as 1 and three as 0" in entry.rationale

    class _Ctx:
        scheduled_rounds = 3
    assert entry.fn(_Ctx()) == 0.0
    _Ctx.scheduled_rounds = 5
    assert entry.fn(_Ctx()) == 1.0
    # And a length the source does not carry is ABSENT, never guessed.
    _Ctx.scheduled_rounds = 4
    assert entry.fn(_Ctx()) is None


def test_both_directions_of_the_absence_rule_are_seen():
    """A guard that watches one direction teaches the next person to
    over-correct: a measured zero must still reach the model."""
    from gridiron.model import llm

    rows = [
        {"factor": "measured", "value": 0.0, "present": True,
         "rationale": "a measured zero"},
        {"factor": "unmeasurable", "value": None, "present": False,
         "rationale": "no value exists"},
    ]
    text = llm.build_prompt("claim", rows, [])
    assert "measured = 0" in text
    assert "unmeasurable =" not in text
    assert "do not treat these as zero" in text.lower()


# --- fix 2: a push exists in the record before it is sent (2026-09-05) ------

def test_the_record_precedes_the_push():
    audit.check_the_record_precedes_the_push()


def test_a_refused_kind_now_fails_before_anything_is_posted():
    """THE EXACT CASE THAT LOST A PUSH, pinned.

    On 2026-09-05 `send` was called with a kind the table's CHECK refuses.
    Both channels delivered, the phone buzzed, the INSERT raised, and the
    record has no trace of it. The row is now written first, so the CHECK runs
    before anything leaves the machine.
    """
    import sqlite3
    import tempfile
    from pathlib import Path

    from gridiron import db as _db, notify as _notify

    posted = []
    real_push, real_toast = _notify.send_push, _notify.send_toast
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        conn = _db.open_db(Path(tmp) / "n.db")
        try:
            _notify.send_push = lambda body, title="Gridiron": posted.append(1)
            _notify.send_toast = lambda title, body: posted.append(1)
            with pytest.raises(sqlite3.IntegrityError):
                _notify.send(conn, "test", "a kind the table refuses")
        finally:
            _notify.send_push, _notify.send_toast = real_push, real_toast
            conn.close()

    assert posted == [], (
        "a message with a refused kind still reached the channels; the CHECK "
        "must run before the irreversible part, not after it")


def test_sending_is_its_own_state_and_not_queued():
    """A crash mid-post must not hide inside an ordinary state.

    'queued' means held for quiet hours and never sent. 'sending' means handed
    to the network and unaccounted for. One is routine and one wants looking
    at, so they are not the same word.
    """
    import tempfile
    from pathlib import Path

    from gridiron import db as _db

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        conn = _db.open_db(Path(tmp) / "n.db")
        try:
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='notifications'"
            ).fetchone()[0]
            assert "'sending'" in ddl
            assert "'queued'" in ddl
        finally:
            conn.close()


def test_the_migration_widens_an_older_database():
    """A database made before 'sending' existed would refuse every row."""
    import tempfile
    from pathlib import Path

    from gridiron import db as _db

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / "old.db"
        conn = _db.open_db(path)
        try:
            # Recreate the narrow table the way it was before 2026-09-05.
            conn.executescript(
                "DROP TABLE notifications;"
                "CREATE TABLE notifications ("
                " id INTEGER PRIMARY KEY, queued_utc TEXT NOT NULL,"
                " sent_utc TEXT,"
                " kind TEXT NOT NULL CHECK (kind IN ('results','failure')),"
                " title TEXT NOT NULL, body TEXT NOT NULL,"
                " state TEXT NOT NULL CHECK (state IN ('queued','sent','failed')),"
                " channels_json TEXT);")
            conn.execute(
                "INSERT INTO notifications (queued_utc, kind, title, body,"
                " state) VALUES ('2026-01-01T00:00:00Z','failure','t','b','sent')")
            conn.commit()
            assert _db.widen_notification_states(conn) is True
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='notifications'"
            ).fetchone()[0]
            assert "'sending'" in ddl
            # AND THE HISTORY SURVIVED, which is the part a rebuild can lose.
            assert conn.execute(
                "SELECT COUNT(*) FROM notifications").fetchone()[0] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE"
                " name='notifications_wide'").fetchone()[0] == 0
            # Idempotent: a second call is a no-op.
            assert _db.widen_notification_states(conn) is False
        finally:
            conn.close()


# --- fix 3: nothing is reasoned twice (2026-09-05) --------------------------

def test_the_check_is_asked_before_the_model():
    audit.check_nothing_is_reasoned_twice()


def test_a_rerun_over_a_written_slate_makes_no_model_calls():
    """The measured failure, pinned. A resumed UFC pass made 76 reasoning
    calls to write 8 rows: 34 questions answered twice and discarded.

    SPENDS NOTHING -- `llm.reason` is stubbed with a counter, so this measures
    the ORDER of the loop rather than the API.
    """
    from gridiron import db as _db
    from gridiron.model import llm as _llm, predict as _predict

    conn = _db.connect()
    try:
        row = conn.execute(
            "SELECT g.season, g.week, p.sport FROM predictions p"
            "  JOIN games g ON g.id = p.game_id"
            " WHERE p.predictor = 'llm' GROUP BY p.sport, g.season, g.week"
            " ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
        if row is None:
            pytest.skip("no slate in this record has LLM rows")

        calls = []
        original = _llm.reason
        try:
            _llm.reason = lambda *a, **k: calls.append(1)
            run = _predict.predict_slate(
                conn, row["sport"], row["season"], row["week"],
                final=False, include_props=True, use_llm=True)
        finally:
            _llm.reason = original
    finally:
        conn.close()

    assert calls == [], (
        f"a re-run over a written slate made {len(calls)} model calls; every "
        f"one buys an answer `write_prediction` will discard")
    assert run.llm_skipped > 0, (
        "the run reported skipping nothing, so the counter is not counting")


def test_the_skip_is_counted_not_silent():
    """A run reporting `llm_skipped` beside a small `written` is a resume that
    worked. Silence would look identical to a run that had nothing to do."""
    from gridiron.model import predict as _predict

    run = _predict.BlindRun(sport="ufc", season=2026, week=1)
    assert run.llm_skipped == 0
    assert hasattr(run, "llm_skipped")


def test_the_existence_check_is_one_door():
    """`write_prediction` and the LLM path must ask the same question.

    A second predicate that drifted from the unique index is how the final
    pass failed the first time it ran: a check that does not match the
    constraint it stands in for turns a clean no-op into an IntegrityError.
    """
    import inspect

    from gridiron.model import predict as _predict

    src = inspect.getsource(_predict.write_prediction)
    assert "already_written(" in src, (
        "write_prediction no longer asks the shared door, so two predicates "
        "can drift apart")
    assert "SELECT 1 FROM predictions WHERE game_id" not in src, (
        "write_prediction has grown its own copy of the predicate again")


# --- fix 4: no code name reaches a reader (2026-09-05) ---------------------

def test_the_prompt_names_factors_in_plain_words():
    """The source of the 27 dirty rows. A model quotes what it is given."""
    from gridiron.model import llm

    rows = [{"factor": "ufc_scheduled_rounds",
             "why": "how many rounds the bout is scheduled for",
             "value": 0.0, "present": True, "rationale": "scaled"}]
    prompt = llm.build_prompt("does it go the distance", rows, [])
    assert "ufc_scheduled_rounds" not in prompt
    assert "how many rounds the bout is scheduled for" in prompt


def test_every_declared_factor_has_a_phrase_for_the_prompt_to_use():
    """Measured 2026-09-05: 103 of 103. The fallback to a code name exists for
    a caller handing over rows from elsewhere, not for a gap in the registry."""
    from gridiron.factors import registry

    missing = [f.name for f in registry.all_factors() if not (f.why or "").strip()]
    assert not missing, missing


def test_stored_reasoning_is_humanised_at_render_time_not_rewritten():
    """LAW 3: a forecaster's words are never edited. The READER sees plain
    names; the row keeps what was written."""
    from gridiron import db as _db, language, views

    phrases = views._why_phrases()
    conn = _db.connect()
    try:
        rows = conn.execute(
            "SELECT reasoning FROM predictions WHERE predictor = 'llm'"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        pytest.skip("no LLM rows in this record")

    raw = sum(1 for r in rows
              if audit.plain_words_violations(r["reasoning"] or ""))
    shown = sum(1 for r in rows
                if audit.plain_words_violations(
                    language.humanise_reasoning(r["reasoning"], phrases) or ""))
    assert shown == 0, f"{shown} of {len(rows)} rows still render a code name"
    assert raw > 0, (
        "no stored row carries a code name, so this test is no longer "
        "checking the repair it was written for")


def test_the_alias_rule_refuses_to_guess():
    """Shortened names are mapped only where every owner agrees.

    `nba_asked_line` yields `asked_line`, which is a declared factor of its
    own, so no alias is made -- a reader must never be shown basketball's
    phrase over football's factor. And a bare English word is never mapped.
    """
    from gridiron import language

    phrases = {
        "asked_line": "how far the question sits from the line",
        "nba_asked_line": "how far the basketball question sits",
        "mlb_prop_mean_vs_line": "where the line sits against his average",
        "prop_mean_vs_line": "where the line sits against his average",
        "ufc_scheduled_rounds": "how many rounds the bout is scheduled for",
    }
    out = language.with_prefix_aliases(phrases)

    # Declared already: never overwritten by an alias.
    assert out["asked_line"] == phrases["asked_line"]
    # Owners agree, so the shortened form is safe.
    assert out["mean_vs_line"] == "where the line sits against his average"
    assert out["scheduled_rounds"] == phrases["ufc_scheduled_rounds"]
    # Bare words are never mapped.
    assert "line" not in out and "rounds" not in out


def test_the_alias_rule_refuses_when_owners_disagree():
    from gridiron import language

    out = language.with_prefix_aliases({
        "nfl_home_edge": "how much the home crowd is worth in football",
        "nba_home_edge": "how much the home floor is worth in basketball",
    })
    assert "home_edge" not in out, (
        "two sports disagree about what the phrase means and an alias was "
        "made anyway; a reader could be shown the wrong sport's words")


def test_the_llm_view_shows_no_code_name():
    from gridiron import db as _db

    conn = _db.connect()
    try:
        audit.check_no_code_names_in_llm_prose(conn)
    finally:
        conn.close()


# --- encoded factors go to the model in words (2026-09-05) -----------------

def test_an_indicator_reaches_the_model_as_words():
    from gridiron.factors import compute
    from gridiron.model import llm

    rows = [{"factor": "ufc_scheduled_rounds",
             "why": "how many rounds the bout is scheduled for",
             "reads": {1.0: "a five-round bout", 0.0: "a three-round bout"},
             "unit": None, "unit_scale": 1.0, "unit_offset": 0.0,
             "value": 0.0, "present": True, "rationale": "scaled"}]
    prompt = llm.build_prompt("does it go the distance", rows, [])
    assert "- a three-round bout" in prompt
    # AND NOT THE NUMBER. Appending it would put back what the phrase replaced.
    assert "= 0" not in prompt
    assert compute.factor_value_words(
        "how many rounds", 1.0, {1.0: "a five-round bout"}) == "a five-round bout"


def test_a_scaled_quantity_reaches_the_model_in_its_real_units():
    from gridiron.factors import compute

    assert compute.factor_value_words(
        "the age difference between the two fighters", 0.78,
        unit="years", unit_scale=10.0) == (
        "the age difference between the two fighters = 7.8 years")


def test_an_undeclared_value_keeps_its_number():
    """A guessed unit is worse than a bare one: uninformative versus wrong."""
    from gridiron.factors import compute

    assert compute.factor_value_words("the cold", -0.75) == "the cold = -0.75"


def test_cold_carries_no_unit_because_its_zero_is_overloaded():
    """THE COUNTER-EXAMPLE that makes this a decision, not a transcription.

    `cold` returns 0.0 for an INDOOR game as well as for a 55F one, so a unit
    declaration would print "55 F" about a dome -- a temperature nobody
    measured.
    """
    from gridiron.factors import registry

    entry = registry.REGISTRY["cold"]
    assert entry.unit is None and entry.reads is None


def test_every_declared_indicator_is_handed_over_in_words():
    audit.check_indicators_are_words()


def test_the_guard_sees_an_indicator_stripped_of_its_reading():
    from gridiron.factors import registry

    entry = registry.REGISTRY["ufc_scheduled_rounds"]
    original = entry.reads
    try:
        object.__setattr__(entry, "reads", None)
        assert audit.indicator_words_faults()
    finally:
        object.__setattr__(entry, "reads", original)
    assert audit.indicator_words_faults() == []


def test_the_indicator_pattern_does_not_flag_ordinary_english():
    """`mlb_pitcher_k_rate` reads "how often he gets one when he has the
    chance" -- prose about a rate, not a declaration. The first version of the
    pattern flagged it, and "zero otherwise" is what tells the two apart."""
    from gridiron.factors import registry
    import gridiron.factors.mlb  # noqa: F401

    entry = registry.REGISTRY["mlb_pitcher_k_rate"]
    assert "one when" in entry.rationale.lower()
    assert not audit._INDICATOR_WORDS.search(entry.rationale)


def test_the_composer_is_not_importable_into_the_prediction_path_by_accident():
    """LAW 1 caught this within a minute of it being written.

    `language` names market columns, so importing it from `model.llm` -- which
    is inside the prediction closure -- is a violation. The composer lives in
    `factors.compute` and `language` re-exports it, which is the same shape
    `audit` already uses for the missing-data check.
    """
    from gridiron import language
    from gridiron.factors import compute

    assert language.factor_value_words is compute.factor_value_words
    src = (config.PACKAGE_ROOT / "model" / "llm.py").read_text(encoding="utf-8")
    assert "import language" not in src
    audit.check_all_prediction_closures()
