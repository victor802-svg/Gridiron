"""The venue's packages, graded (GRIDIRON_COMBOS, 2026-09-08).

WHAT THESE TESTS ARE ACTUALLY DEFENDING. LAW 5 was amended on 2026-09-08 to
let the engine price a multi-leg package the VENUE published, and the whole
safety of that amendment is in the word "published": the app grades what it is
offered and never assembles anything. Every test below is about one of the two
halves of that -- the four shapes a package may not be priced in, and the fact
that nothing here builds one.

AND THE GROUP SHIPS EMPTY. Measured against the venue on the day this was
written: the only readable package markets were college-basketball same-game
parlays, which C1 refuses by name, and no baseball package existed at all. So
several of these tests build their packages by hand -- there was nothing else
to build them from, and a test that waited for the venue to offer something
would be a test that never ran.
"""
import pytest

from gridiron import audit, calibration, config, db, language, views
from gridiron.market import combos


# ---------------------------------------------------------------------------
# C1 -- the four shapes, and the one that passes
# ---------------------------------------------------------------------------

GAMES = {"Kansas City": "g1", "Buffalo": "g1", "Miami": "g2", "Denver": "g3"}


def test_a_same_game_package_is_refused_and_counted():
    """THE ONE THE VENUE ACTUALLY SELLS, and the one with no fair value here.

    Multiplying two probabilities from one game prices a correlation nobody
    declared, which LAW 2 forbids, and this record holds no joint model to
    declare one with.
    """
    verdict = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Buffalo over 44"]}, GAMES)
    assert verdict["priceable"] is False
    assert verdict["why"] == "same_game"
    assert combos.UNPRICEABLE[verdict["why"]].startswith("same-game")


def test_a_four_leg_package_is_refused():
    verdict = combos.classify(
        {"sport": "nfl", "legs": ["a", "b", "c", "d"]}, GAMES)
    assert verdict["why"] == "leg_count"


def test_a_leg_this_record_does_not_forecast_is_refused():
    """Never guessed at. A leg with no probability behind it would leave one of
    the factors in the product invented."""
    verdict = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Sunderland to win"]}, GAMES)
    assert verdict["why"] == "unforecast_leg"


def test_a_sport_this_record_does_not_forecast_is_refused():
    """College BASKETBALL is not college football and is not in this record."""
    verdict = combos.classify(
        {"sport": "cbb", "legs": ["Michigan -7.5", "UConn -2"]}, GAMES)
    assert verdict["why"] == "unforecast_sport"


def test_a_cross_game_package_in_one_sport_is_priceable():
    verdict = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Miami moneyline"]}, GAMES)
    assert verdict["priceable"] is True
    assert verdict["games"] == ["g1", "g2"]


def test_a_leg_naming_two_games_is_unreadable_rather_than_guessed():
    """TWO LOS ANGELES CLUBS ON ONE SLATE is the case this rule exists for.

    The first version of this test asserted the wrong thing and the code was
    right: it fed a map `club_index` would never build, and read the pass as
    a defect. What actually happens is here -- a leg whose text matches names
    belonging to two different games is refused, and one that matches a single
    game's name is placed.
    """
    ambiguous = {"Los Angeles": "g1", "Los Angeles Rams": "g2"}
    assert combos._game_of("Los Angeles Rams moneyline", ambiguous) is None
    assert combos._game_of("Los Angeles moneyline", ambiguous) == "g1"


def test_a_name_shared_by_two_games_is_dropped_from_the_map():
    rows = [{"id": "g1", "home": "LAR", "home_location": "Los Angeles",
             "away": "SF", "away_location": "San Francisco"},
            {"id": "g2", "home": "LAC", "home_location": "Los Angeles",
             "away": "DEN", "away_location": "Denver"}]
    tokens = combos.club_index(rows)
    assert "Los Angeles" not in tokens
    assert tokens["Denver"] == "g2"


def test_the_venue_writes_clubs_in_full_and_the_matcher_reads_them():
    """FOUND BY RUNNING IT. The first matcher compared our tricodes -- DEN --
    against the venue's own text, "Denver -7.5", and matched nothing, so every
    package came back with the wrong reason for the right refusal."""
    rows = [{"id": "g9", "home": "DEN", "home_location": "Denver",
             "home_name": "Denver Broncos", "away": "KC",
             "away_location": "Kansas City"}]
    tokens = combos.club_index(rows)
    assert combos._game_of("Denver -7.5", tokens) == "g9"
    assert combos._game_of("Denver Broncos moneyline", tokens) == "g9"


def test_the_side_a_leg_names_is_read_and_never_assumed():
    """A LEG NAMES A SIDE, not just a game. The wrong-side defect has shipped
    here four times in other forms; this is the fifth place it could."""
    rows = [{"id": "g9", "home": "DEN", "home_location": "Denver",
             "away": "KC", "away_location": "Kansas City"}]
    sides = combos.sides_for(rows)
    assert combos.leg_side("Denver moneyline", sides["g9"]) == "home"
    assert combos.leg_side("Kansas City moneyline", sides["g9"]) == "away"
    assert combos.leg_side("over 44.5 points", sides["g9"]) is None


# ---------------------------------------------------------------------------
# C1 -- the guard, and what it refuses
# ---------------------------------------------------------------------------

def _priced(**fields):
    package = {"ticker": "T", "sport": "nfl", "priceable": True,
               "legs": ["a", "b"], "games": ["g1", "g2"]}
    package.update(fields)
    return package


@pytest.mark.parametrize("package, expected", [
    (_priced(games=["g1", "g1"]), "correlation"),
    (_priced(leg_sports=["nfl", "mlb"]), "LAW 6"),
    (_priced(legs=["a", "b", "c", "d"], games=["g1", "g2", "g3", "g4"]),
     "declared shape"),
    (_priced(unforecast_leg=True), "does not forecast"),
])
def test_the_guard_fails_by_name_on_each_forbidden_shape(package, expected):
    with pytest.raises(audit.LawViolation, match="GRADED, NEVER BUILT"):
        audit.check_combo_package([package])
    assert any(expected in fault
               for fault in audit.combo_package_faults([package]))


def test_the_guard_passes_the_shape_the_law_permits():
    assert audit.combo_package_faults([_priced()]) == []


def test_the_blanket_refusal_is_gone_and_the_four_replaced_it():
    """RETIRED BY NAME on 2026-09-08, with the note that says what took over."""
    from gridiron.market import recommend

    assert not hasattr(recommend, "price_parlay")
    assert not hasattr(recommend, "SinglesOnly")


# ---------------------------------------------------------------------------
# C2 -- the arithmetic, and the cost printed beside it
# ---------------------------------------------------------------------------

def test_fair_value_is_the_product_of_the_legs():
    assert combos.fair_value([0.6, 0.6]) == 0.36
    assert combos.fair_value([0.6, None]) is None


def test_the_edge_is_the_same_subtraction_a_single_gets():
    edge = combos.package_edge(0.40, 0.30)
    assert edge["edge_cents"] == pytest.approx(8.0, abs=0.01)
    assert edge["return_on_stake"] == pytest.approx(0.2667, abs=0.001)


def test_the_singles_alternative_is_on_the_arithmetic_not_in_the_prose():
    """THE COST IS THE POINT, and it is a measurement rather than a warning."""
    two = combos.singles_alternative([0.6, 0.6], [0.65, 0.65])
    three = combos.singles_alternative([0.6, 0.6, 0.6], [0.65, 0.65, 0.65])
    assert two["ratio"] == pytest.approx(1.67, abs=0.01)
    assert three["ratio"] == pytest.approx(2.78, abs=0.01)
    assert three["ratio"] > two["ratio"], "a third leg costs more, not less"


def test_the_margin_line_prints_both_numbers():
    words = language.combo_margin_words(0.30, 0.36)
    assert "30" in words and "36.0" in words


# ---------------------------------------------------------------------------
# C3 -- the size
# ---------------------------------------------------------------------------

def test_below_the_gate_a_package_is_a_fraction_of_a_flat_unit():
    two = combos.size_for(2, settled=0, gate=100)
    three = combos.size_for(3, settled=0, gate=100)
    assert two["kind"] == "flat" and two["units"] == config.FLAT_UNIT * 0.5
    assert three["units"] == config.FLAT_UNIT * 0.25
    assert "no measured edge" in two["why"]


def test_a_flat_size_says_which_flat_size_it_is():
    """FOUND BY RENDERING THE FIRST PACKAGE CARD. The sentence said "One flat
    unit" for a half-unit package while the money beside it said $7.50 --- two
    numbers disagreeing, with nothing to tell a reader which one to believe."""
    assert language.size_words(units=0.5, flat=True, why=None,
                               unit_dollars=None).startswith("Half a flat unit")
    assert "half a flat unit" in language.size_words(
        units=0.5, flat=True, why=None, unit_dollars=15)
    assert "$7.50" in language.size_words(units=0.5, flat=True, why=None,
                                          unit_dollars=15)
    assert language.size_words(units=0.25, flat=True, why=None,
                               unit_dollars=None).startswith("A quarter")
    assert language.size_words(units=1.0, flat=True, why=None,
                               unit_dollars=None).startswith("One flat unit")


def test_above_the_gate_a_package_is_never_staked_above_the_flat_fraction():
    """CAPPED AT WHAT AN UNPROVEN ONE WOULD HAVE BEEN. A measured edge may
    shrink a package's size and may never grow it past the flat fraction."""
    sized = combos.size_for(2, settled=400, gate=100, fair=0.60, price=0.30,
                            measured_edge=True)
    assert sized["units"] <= config.FLAT_UNIT * 0.5


# ---------------------------------------------------------------------------
# C4 -- WITHDRAWN 2026-09-09, and what is left of it
# ---------------------------------------------------------------------------
#
# Five tests stood here: the two combo markets, the hundred-package CLV gate,
# the kill's declared threshold, the condition it fires on, and its refusal to
# edit the registry. Every one of them was true, and every one described a
# product this app cannot have.
#
# The venue quotes a combo to an account holder on request. The app has no
# account and LAW 5 does not permit one, so it never sees the price paid --
# and a product with no price paid has no closing line, no CLV, no verdict and
# nothing for a kill to fire on. The criterion counted SETTLED packages and
# nothing could ever settle.
#
# What replaces them is one test: that the withdrawal is complete, and that
# the app says why on the card rather than leaving a reader to look for a
# sample size that is never coming.


def test_the_combo_record_is_withdrawn_and_says_so():
    """C4 WITHDRAWN (operator ruling, 2026-09-09).

    The machinery is GONE, not left unused -- the treatment `Factor.default`
    got, and for the same reason: a constant nobody reads is one the next
    reader assumes is doing something.
    """
    assert not hasattr(config, "COMBO_MARKETS")
    assert not hasattr(config, "combo_market")
    assert not hasattr(config, "is_combo_market")
    assert not hasattr(config, "COMBO_KILL_AFTER")
    assert not hasattr(calibration, "combo_kill_verdict")
    assert not hasattr(calibration, "MIN_PACKAGES_FOR_CLV")
    # The dates the withdrawal happened on, so a reader finds the ruling.
    assert config.COMBO_RECORD_WITHDRAWN == "2026-09-09"
    assert calibration.COMBO_CLV_WITHDRAWN == "2026-09-09"
    # ONE ANSWER FOR EVERY MARKET now that no combo reaches it.
    assert calibration.clv_minimum("moneyline") == 50
    assert calibration.clv_minimum("combo_2") == 50


def test_the_card_says_the_product_cannot_be_scored():
    """EVERY OTHER NUMBER ON THIS PAGE CARRIES ITS N (LAW 4), so a reader
    trained by that will look for one on a combo card. It is not coming, and
    the card says so instead of leaving a hole."""
    words = language.combo_unmeasurable_words()
    assert "never sees the price" in words
    assert "cannot be scored" in words
    assert "No record is kept" in words


def test_a_package_tap_is_one_row_in_the_same_table(tmp_path):
    conn = db.connect(tmp_path / "taken.db")
    db.init(conn)
    conn.execute(
        "INSERT INTO venue_packages (venue, ticker, event_ticker, series,"
        " sport, legs_text, leg_count, game_ids, priceable, why_not, fetched_utc)"
        " VALUES ('kalshi', 'K1', 'E1', 'KXNFLCOMBO', 'nfl', 'A & B', 2,"
        "         'g1,g2', 1, NULL, '2026-09-08T00:00:00Z')")
    conn.execute("INSERT INTO games (id, sport, season, week, game_type,"
                 " kickoff_utc, home, away, status) VALUES ('g1', 'nfl', 2026,"
                 " 1, 'REG', '2026-09-08T17:00:00Z', 'KC', 'BUF', 'scheduled')")
    conn.commit()
    package_id = conn.execute(
        "SELECT id FROM venue_packages").fetchone()["id"]

    assert views.take_package(conn, package_id)["taken"] is True
    assert views.take_package(conn, package_id)["already"] is True
    assert conn.execute("SELECT COUNT(*) FROM picks_taken").fetchone()[0] == 1
    row = conn.execute("SELECT * FROM picks_taken").fetchone()
    assert row["package_id"] == package_id and row["prediction_id"] is None


def test_the_taken_table_admits_one_kind_of_tap_per_row(tmp_path):
    """A ROW NAMING BOTH IS TWO TAPS RECORDED AS ONE, and a row naming
    neither is a tap on nothing."""
    import sqlite3

    conn = db.connect(tmp_path / "both.db")
    db.init(conn)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("INSERT INTO picks_taken (prediction_id, package_id,"
                     " taken_utc) VALUES (1, 1, '2026-09-08T00:00:00Z')")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("INSERT INTO picks_taken (taken_utc)"
                     " VALUES ('2026-09-08T00:00:00Z')")


def test_a_package_tap_never_enters_a_single_legs_curve(tmp_path):
    """LAW 6 ONE LEVEL DOWN. A package and its legs are different products."""
    conn = db.connect(tmp_path / "curve.db")
    db.init(conn)
    comparison = calibration.taken_comparison(
        conn, sport="nfl", market_type="moneyline")
    assert comparison["taken"]["n"] == 0
    packages = calibration.taken_packages(conn, sport="nfl")
    assert packages["market"] == "packages"
    assert "nothing taken or passed over" in packages["words"]


# ---------------------------------------------------------------------------
# C5 -- the words
# ---------------------------------------------------------------------------

def test_the_products_own_name_is_permitted_and_the_sportsbooks_is_not():
    assert audit.pressure_word_faults("Combos — 2 packages") == []
    assert audit.pressure_word_faults("a combo card") == []
    for banned in ("parlay", "same game", "boost", "builder", "add leg", "slip"):
        assert audit.pressure_word_faults(f"the {banned} here"), banned


def test_a_package_cards_own_words_are_scanned():
    """THE LEGS ARRIVE AS THE VENUE WROTE THEM, which is the one place on this
    page where the text is somebody else's."""
    planted = {"today": {"combos": {"cards": [
        {"legs_words": "Denver moneyline · Kansas City same game"}]}}}
    assert audit.day_pressure_faults(planted)
    with pytest.raises(audit.LawViolation):
        audit.check_the_day_applies_no_pressure(planted)


def test_nothing_on_a_package_card_animates_or_counts_down():
    faults = audit.price_chip_animation_faults()
    assert faults == [], faults
    assert audit.countdown_faults() == []


# ---------------------------------------------------------------------------
# C6 -- the group, and what it says when it is empty
# ---------------------------------------------------------------------------

def test_the_heading_counts_what_was_offered_and_why_each_was_refused():
    words = language.combo_heading_words(
        1, {"same_game": 2}, ["mlb"])
    assert words.startswith("1 priced")
    assert "2 same-game, not priceable" in words
    assert "none for MLB" in words


def test_the_heading_reads_as_a_sentence_after_a_count():
    """A PHRASE THAT ONLY WORKS ALONE would print as "4 a sport this record
    does not forecast", which is how a heading meant to be an answer becomes a
    thing a reader skips."""
    words = language.combo_heading_words(0, {"unforecast_sport": 4}, [])
    assert "4 in a sport this record does not forecast" in words


def test_the_empty_state_never_reports_the_venue_as_having_nothing():
    """REPLACED 2026-09-09. This asserted the two shapes of "the venue offered
    nothing" -- and the ruling of that date forbids the app saying that at
    all: the venue's combo builder is an account-holder feature that exists
    whether or not anything sits on its public shelf, and the true statement
    is that this app cannot ask.

    The empty state now describes OUR side, per sport, in the operator's own
    words, so a reader can see that a combo is two picks from one sport.
    """
    assert not hasattr(language, "combo_empty_words")
    words = language.combo_none_clear_words("MLB")
    assert words == "no two MLB picks clear the bar today"
    assert "package" not in words and "venue" not in words
    # AND THE GROUP SAYS WHAT IT CANNOT DO, above the cards.
    assert "cannot ask" in language.COMBO_RFQ_SENTENCE
    assert "on request" in language.COMBO_RFQ_SENTENCE


def test_the_group_ships_empty_and_truthful_on_the_live_record(tmp_path):
    """An empty group is a finding, and the sentence is how a reader tells it
    from a broken one.

    REWRITTEN 2026-09-09. It asserted the heading was "Combos" and the empty
    sentence said "no package open today". Both were corrected by ruling: the
    group is PER SPORT ("MLB combos", LAW 6), and it never reports the venue
    as having nothing, because the venue's builder exists whether or not its
    public shelf does -- the app simply cannot ask. The empty state describes
    OUR side of it.
    """
    conn = db.connect(tmp_path / "group.db")
    db.init(conn)
    block = views._combo_block(conn, [], [], "mlb")
    assert block["n"] == 0
    assert block["cards"] == []
    assert block["heading"] == "MLB combos"
    assert block["empty_words"] == "no two MLB picks clear the bar today"
    # AND NEVER THE OLD SENTENCE, in any form.
    assert "package open" not in block["empty_words"]
    # The group says what it cannot do, above the cards.
    assert "cannot ask" in block["rfq_words"]


# ---------------------------------------------------------------------------
# The two rulings of 2026-09-08, after the brief: a tap is retracted rather
# than deleted, and verification never touches the live record.
# ---------------------------------------------------------------------------

def test_a_tap_is_never_deleted(tmp_path):
    """LAW 3, ENFORCED RATHER THAN COMMENTED. `picks_taken` carried the word
    "append-only" in its own comment and had no no-delete trigger, which is how
    a synthetic tap came to be removed with an ordinary DELETE on 2026-09-08.
    """
    import sqlite3

    conn = db.connect(tmp_path / "taps.db")
    db.init(conn)
    conn.execute(
        "INSERT INTO venue_packages (venue, ticker, event_ticker, series,"
        " sport, legs_text, leg_count, game_ids, priceable, why_not,"
        " fetched_utc) VALUES ('t', 'K', 'E', 'S', 'nfl', 'A & B', 2, 'g1,g2',"
        " 1, NULL, '2026-09-08T00:00:00Z')")
    conn.execute("INSERT INTO picks_taken (package_id, taken_utc)"
                 " VALUES (1, '2026-09-08T01:00:00Z')")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM picks_taken WHERE id = 1")


def test_a_tap_is_taken_back_by_a_second_row_carrying_its_reason(tmp_path):
    """CARD_FACE F3, built. The tap stays because it happened; what changes is
    that a second append-only row says it no longer stands, and why."""
    conn = db.connect(tmp_path / "retract.db")
    db.init(conn)
    conn.execute(
        "INSERT INTO venue_packages (venue, ticker, event_ticker, series,"
        " sport, legs_text, leg_count, game_ids, priceable, why_not,"
        " fetched_utc) VALUES ('t', 'K', 'E', 'S', 'nfl', 'A & B', 2, 'g1,g2',"
        " 1, NULL, '2026-09-08T00:00:00Z')")
    conn.execute("INSERT INTO picks_taken (package_id, taken_utc)"
                 " VALUES (1, '2026-09-08T01:00:00Z')")
    conn.commit()

    # a reason that says nothing is not a reason
    assert views.retract_tap(conn, 1, "oops")["retracted"] is False
    assert views.retract_tap(conn, 999, "a package nobody took")["retracted"] is False

    got = views.retract_tap(conn, 1, "written by a verification run, not by "
                                     "the operator")
    assert got["retracted"] is True and got["already"] is False
    assert views.retract_tap(conn, 1, "the same reason again")["already"] is True

    # BOTH ROWS STAND, and the tap no longer counts as a choice
    assert conn.execute("SELECT COUNT(*) FROM picks_taken").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM picks_retracted").fetchone()[0] == 1
    assert views.taken_package_ids(conn, [1]) == set()
    assert calibration.taken_packages(conn, sport="nfl")["n"] == 0


def test_a_retraction_is_itself_append_only(tmp_path):
    import sqlite3

    conn = db.connect(tmp_path / "retract2.db")
    db.init(conn)
    conn.execute(
        "INSERT INTO venue_packages (venue, ticker, event_ticker, series,"
        " sport, legs_text, leg_count, game_ids, priceable, why_not,"
        " fetched_utc) VALUES ('t', 'K', 'E', 'S', 'nfl', 'A & B', 2, 'g1,g2',"
        " 1, NULL, '2026-09-08T00:00:00Z')")
    conn.execute("INSERT INTO picks_taken (package_id, taken_utc)"
                 " VALUES (1, '2026-09-08T01:00:00Z')")
    conn.commit()
    views.retract_tap(conn, 1, "written by a verification run")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE picks_retracted SET reason = 'something else'")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM picks_retracted")


def test_verification_may_not_open_the_live_record():
    """THE RULE THIS SESSION EARNED. A verification run of mine opened the
    operator's own database and wrote two rows into it; nothing refused."""
    with pytest.raises(db.LiveRecordTouched, match="MAY NOT OPEN THE LIVE"):
        db.connect()
    with pytest.raises(db.LiveRecordTouched):
        db.open_db(config.DB_PATH)
    # and the same file, spelled differently, is still the same file
    with pytest.raises(db.LiveRecordTouched):
        db.connect(config.DB_PATH.parent / ".." / "var" / config.DB_PATH.name)


def test_a_scratch_database_is_never_refused(tmp_path):
    conn = db.open_db(tmp_path / "scratch.db")
    conn.execute("SELECT COUNT(*) FROM picks_taken")
    conn.close()
    memory = db.connect(":memory:")
    memory.close()


def test_the_one_door_into_the_live_record_cannot_be_written_through():
    """Narrow, named, and unable to write. The reason is not decoration."""
    import sqlite3

    with pytest.raises(db.LiveRecordTouched, match="NEEDS A REASON"):
        db.read_the_live_record("why")
    if not config.DB_PATH.exists():
        pytest.skip("no live record on this machine to read")
    conn = db.read_the_live_record(
        "proving the handle refuses a write, which is the whole of its point")
    try:
        conn.execute("SELECT COUNT(*) FROM picks_taken").fetchone()
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO picks_taken (package_id, taken_utc)"
                         " VALUES (999999, '2026-09-08T00:00:00Z')")
    finally:
        conn.close()


def test_the_shipped_way_to_retract_is_the_command_line(tmp_path, capsys):
    """No button and no route: a retraction is rare, deliberate, and needs a
    reason typed in words. The CLI is the shipped caller."""
    from gridiron import cli

    path = tmp_path / "cli.db"
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO venue_packages (venue, ticker, event_ticker, series,"
        " sport, legs_text, leg_count, game_ids, priceable, why_not,"
        " fetched_utc) VALUES ('t', 'K', 'E', 'S', 'nfl', 'A & B', 2, 'g1,g2',"
        " 1, NULL, '2026-09-08T00:00:00Z')")
    conn.execute("INSERT INTO picks_taken (package_id, taken_utc)"
                 " VALUES (1, '2026-09-08T01:00:00Z')")
    conn.commit()
    conn.close()

    assert cli.main(["--database", str(path), "retract-tap", "1", "short"]) == 1
    assert "not retracted" in capsys.readouterr().out
    assert cli.main(["--database", str(path), "retract-tap", "1",
                     "marked by mistake, the game had already started"]) == 0
    assert "both rows stand" in capsys.readouterr().out
    assert cli.main(["--database", str(path), "retract-tap", "1",
                     "marked by mistake, the game had already started"]) == 0
    assert "already retracted" in capsys.readouterr().out
