"""G1: the schema itself carries the laws."""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import db
from gridiron.data import reference


# --- LAW 1: the games table has no line on it ------------------------------

def test_games_table_has_no_market_columns(conn):
    cols = set(db.table_columns(conn, "games")) | set(
        db.table_columns(conn, "game_conditions")
    )
    forbidden = [c for c in cols if any(w in c for w in ("spread", "total", "moneyline", "odds"))]
    assert forbidden == [], (
        f"LAW 1 violation: market columns {forbidden} are reachable from the tables "
        "the prediction path reads"
    )


def test_market_columns_live_only_in_quarantine(conn):
    assert "spread_line" in db.table_columns(conn, "market_lines_raw")
    assert "line" in db.table_columns(conn, "market_snapshots")


# --- schema ruling 3 (2026-09-24): a fresh build needs no ensure step -------

def _every_column_an_ensure_step_adds() -> list[tuple[str, str]]:
    """(table, column) for every ADD COLUMN the code can run on an old record:
    `db.MIGRATIONS` inside `db.init`, and the market module's own steps
    outside it, which are the ones a fresh build never runs."""
    from gridiron.market import lines

    return ([(table, column) for table, column, _ in db.MIGRATIONS]
            + [("market_snapshots", c) for c, _ in lines.SNAPSHOT_MIGRATIONS]
            + [("market_lines_raw", c) for c, _ in lines.RAW_MIGRATIONS]
            + [("venue_quotes", "read_kind")])


def test_a_fresh_build_holds_every_column_an_ensure_step_adds(tmp_path):
    """"A fresh database built at the released commit must match the live
    record without relying on ensure code" (schema ruling 3, 2026-09-24).

    Until 2026-09-25 `market_lines_raw.spread_sign_source` existed only
    through `lines.ensure_raw_columns`, which runs after an MLB line fetch
    and never in `db.init`. A fresh build lacked it, and the gate's run-line
    check raised "no such column" on one -- it passed only because the gate
    reads a copy of the live record, which had met the ensure step.
    """
    from gridiron import audit
    from gridiron.market import lines

    conn = db.open_db(tmp_path / "fresh.db")
    try:
        missing = [f"{table}.{column}"
                   for table, column in _every_column_an_ensure_step_adds()
                   if column not in db.table_columns(conn, table)]
        assert missing == [], (
            f"a fresh build lacks {missing}: schema.sql does not declare a "
            f"column the code adds to an older record, so a database built at "
            f"the release differs from the live record")
        assert lines.ensure_raw_columns(conn) == [], "the step still adds a column"
        assert lines.ensure_snapshot_columns(conn) == []
        audit.check_run_line_signs(conn, "mlb")        # asks the column; must not raise
    finally:
        conn.close()


def test_the_declared_sign_column_is_the_one_the_ensure_step_adds(tmp_path):
    """The same type, default and constraints, not merely the same name: an
    old table given the column by the ensure step reads back exactly as the
    fresh one declares it (schema ruling 3, 2026-09-24)."""
    from gridiron.market import lines

    fresh = db.open_db(tmp_path / "fresh.db")
    old = db.connect(tmp_path / "old.db")
    try:
        # The table as every record held it before 2026-09-02.
        old.execute(
            "CREATE TABLE market_lines_raw (game_id TEXT PRIMARY KEY,"
            " fetched_utc TEXT NOT NULL, source TEXT NOT NULL,"
            " spread_line REAL, total_line REAL, home_moneyline INTEGER,"
            " away_moneyline INTEGER)")
        assert lines.ensure_raw_columns(old) == ["spread_sign_source"]

        def shape(conn):
            return [tuple(r) for r in conn.execute(
                "PRAGMA table_xinfo(market_lines_raw)")]

        assert shape(fresh) == shape(old)
        sql = fresh.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'market_lines_raw'"
        ).fetchone()[0].lower()
        assert "check" not in sql.split("spread_sign_source", 1)[1], (
            "the declaration carries a CHECK the ensure step never added")
    finally:
        fresh.close()
        old.close()


#: `recommendations` exactly as every record held it until 2026-09-26: the
#: released text, comments aside.
_RECOMMENDATIONS_BEFORE_ITEM_3 = """
CREATE TABLE recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id   INTEGER NOT NULL REFERENCES predictions (id),
    sport           TEXT    NOT NULL,
    game_id         TEXT    NOT NULL REFERENCES games (id),
    market          TEXT    NOT NULL,
    side            TEXT    NOT NULL CHECK (side IN ('yes', 'no')),
    fair_value      REAL    NOT NULL CHECK (fair_value > 0 AND fair_value < 1),
    price           REAL    NOT NULL CHECK (price > 0 AND price < 1),
    edge_cents      REAL    NOT NULL,
    size_kind       TEXT    NOT NULL CHECK (size_kind IN ('flat', 'fraction')),
    size_units      REAL    NOT NULL,
    gate_n          INTEGER NOT NULL,
    created_utc     TEXT    NOT NULL,
    close_price     REAL,
    clv_cents       REAL,
    closed_utc      TEXT,
    UNIQUE (prediction_id, created_utc)
)"""


def test_an_older_record_gains_the_correction_columns_exactly_as_declared(tmp_path):
    """GRIDIRON_REPAIR item 3 (2026-09-26): `db.init` alone brings an older
    `recommendations` to the declared table -- the same columns, types and
    clauses in the same place, the new rule freezing them, and every stored
    row as it was with both new columns NULL. The gate compares a copy the
    same `db.init` migrated with a fresh build, with an empty register."""
    from gridiron import schema_diff

    fresh = db.open_db(tmp_path / "fresh.db")
    old = db.connect(tmp_path / "old.db")
    try:
        old.execute("PRAGMA foreign_keys = OFF")
        old.execute(_RECOMMENDATIONS_BEFORE_ITEM_3)
        old.execute(
            "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
            " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
            " created_utc) VALUES (7, 'mlb', 'g1', 'total', 'no', 0.41, 0.46,"
            " 3.2, 'flat', 1.0, 0, '2026-09-07T20:52:31Z')")
        old.commit()
        db.init(old)

        def shape(conn):
            return [tuple(r) for r in conn.execute(
                "PRAGMA table_xinfo(recommendations)")]

        assert shape(old) == shape(fresh)

        def sql(conn):
            return conn.execute("SELECT sql FROM sqlite_master"
                                " WHERE name = 'recommendations'").fetchone()[0]

        assert schema_diff.table_differences(sql(old), sql(fresh)) == []
        frozen = "recommendation_correction_is_frozen"
        for conn in (old, fresh):
            assert conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'trigger'"
                                " AND name = ?", (frozen,)).fetchone(), frozen
        row = old.execute("SELECT * FROM recommendations").fetchone()
        assert (row["side"], row["fair_value"], row["created_utc"]) == (
            "no", 0.41, "2026-09-07T20:52:31Z")
        assert row["correction_version"] is None
        assert row["calibrated_fair_value"] is None
        # AND IT IS FROZEN FROM THE FIRST OPEN, on the old row too
        with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
            old.execute("UPDATE recommendations SET correction_version = 1,"
                        " calibrated_fair_value = 0.5")
        db.init(old)                     # a second open adds nothing
        assert shape(old) == shape(fresh)
    finally:
        fresh.close()
        old.close()


# --- LAW 3: append-only ----------------------------------------------------

def test_prediction_cannot_be_deleted(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute("DELETE FROM predictions WHERE id = ?", (a_prediction,))


def test_prediction_probability_is_immutable(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute(
            "UPDATE predictions SET model_prob = 0.99 WHERE id = ?", (a_prediction,)
        )


def test_prediction_reasoning_is_immutable(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute(
            "UPDATE predictions SET reasoning = 'rewritten' WHERE id = ?", (a_prediction,)
        )


def test_resolution_is_the_one_permitted_write(a_prediction, league):
    league.execute(
        "UPDATE predictions SET resolved_utc = ?, outcome = 1 WHERE id = ?",
        (db.utcnow(), a_prediction),
    )
    league.commit()
    row = league.execute(
        "SELECT outcome, model_prob FROM predictions WHERE id = ?", (a_prediction,)
    ).fetchone()
    assert row["outcome"] == 1
    assert row["model_prob"] == 0.58, "resolution must not touch the probability"


def test_a_prediction_resolves_only_once(a_prediction, league):
    league.execute(
        "UPDATE predictions SET resolved_utc = ?, outcome = 1 WHERE id = ?",
        (db.utcnow(), a_prediction),
    )
    league.commit()
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute(
            "UPDATE predictions SET resolved_utc = ?, outcome = 0 WHERE id = ?",
            (db.utcnow(), a_prediction),
        )


# --- LAW 1: ordering -------------------------------------------------------

def test_snapshot_without_a_prediction_is_rejected(league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (?,?,?,?)",
            (9999, db.utcnow(), "test", -3.5),
        )


def test_snapshot_timestamped_before_its_prediction_is_rejected(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (?,?,?,?)",
            (a_prediction, "1999-01-01T00:00:00Z", "test", -3.5),
        )


# --- LAW 2: a factor needs a reason ----------------------------------------

def test_factor_without_rationale_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
            ("mystery", "2026-08-28T00:00:00Z", None),
        )


def test_factor_with_a_token_rationale_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
            ("mystery", "2026-08-28T00:00:00Z", "because"),
        )


def test_factor_without_a_date_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
            ("mystery", "whenever", "Rest matters because tired bodies play worse."),
        )


def test_factor_cannot_be_deleted(conn):
    conn.execute(
        "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
        ("rest_days", "2026-08-28T00:00:00Z", "Short weeks compress recovery and preparation."),
    )
    with pytest.raises(sqlite3.IntegrityError, match="LAW 2"):
        conn.execute("DELETE FROM factors WHERE name = 'rest_days'")


# --- probabilities are probabilities ---------------------------------------

@pytest.mark.parametrize("bad", [0.0, 1.0, -0.2, 1.5])
def test_impossible_probabilities_are_rejected(league, bad):
    game_id = league.execute("SELECT id FROM games LIMIT 1").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        league.execute(
            "INSERT INTO predictions (created_utc, game_id, market_type, subject, line_asked,"
            " model_prob, model_side, predictor, factor_set_version, factors_json, reasoning)"
            " VALUES (?,?,'spread','KC',-3.5,?,'cover','statistical','fs1','{}','x')",
            (db.utcnow(), game_id, bad),
        )


# --- reference data --------------------------------------------------------

def test_kickoff_converts_eastern_to_utc():
    # 13:00 ET on a September Sunday is EDT, UTC-4.
    assert reference.kickoff_to_utc("2026-09-13", "13:00") == "2026-09-13T17:00:00Z"
    # February is EST, UTC-5.
    assert reference.kickoff_to_utc("2026-02-08", "18:30") == "2026-02-08T23:30:00Z"


def test_kickoff_without_a_time_is_none_not_a_guess():
    assert reference.kickoff_to_utc("2026-09-13", "") is None
    assert reference.kickoff_to_utc("2026-09-13", None) is None


def test_travel_distance_is_sane():
    sea = reference.site_for("SEA")
    mia = reference.site_for("MIA")
    d = reference.haversine_miles(sea[0], sea[1], mia[0], mia[1])
    assert 2600 < d < 2800, d
    assert reference.haversine_miles(*sea[:2], *sea[:2]) == 0.0


def test_every_current_club_has_a_site():
    for team in ("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV "
                 "MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS").split():
        assert reference.site_for(team) is not None, team
