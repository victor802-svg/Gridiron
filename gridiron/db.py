"""SQLite access. One connection factory, one schema loader, no ORM."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config

SCHEMA_PATH = config.PACKAGE_ROOT / "schema.sql"


def utcnow() -> str:
    """The one timestamp format in this project: ISO-8601, UTC, Z-suffixed."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path is not None else config.DB_PATH
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


#: Columns added to existing tables after the first release. Additive only:
#: nothing here drops or rewrites a column, because a migration that could
#: rewrite `predictions` would be a way around LAW 3.
MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    # WHICH PASS WROTE A PREDICTION (2026-09-03). Every existing row is an
    # 'early' one by definition -- they were all written before the late pass
    # existed -- which is exactly what the column default says, so the
    # migration needs no backfill and rewrites no history.
    ("predictions", "pass_kind", "TEXT NOT NULL DEFAULT 'early'"),
    # A BACKFILL MAY NEVER POSE AS A LIVE CAPTURE (S1, 2026-09-03). Every
    # lineup row that exists today came from a historical load, which is
    # exactly what the default says -- so the migration needs no backfill of
    # its own and rewrites nothing.
    ("mlb_lineups", "source", "TEXT NOT NULL DEFAULT 'backfill'"),
    # WHICH KIND OF UFC CARD (E2, 2026-09-03). NULL until backfilled, and NULL
    # stays a legitimate value afterwards for a card whose tier the name does
    # not carry -- so this migration deliberately has no default.
    ("ufc_events", "event_tier", "TEXT"),
    # AND WHETHER IT IS A CARD AT ALL. Defaults to 1 because every stored event
    # was treated as one until today; the backfill demotes the seven that carry
    # a single bout.
    ("ufc_events", "is_card", "INTEGER NOT NULL DEFAULT 1"),
    ("teams", "is_fbs", "INTEGER"),
    # B3: where a college team plays, and the coordinates the weather
    # and travel factors need. `teams` is reference data, not market
    # data, so this migration may live here.
    ("teams", "venue_name", "TEXT"),
    ("teams", "venue_city", "TEXT"),
    ("teams", "venue_state", "TEXT"),
    ("teams", "venue_indoor", "INTEGER"),
    ("teams", "venue_lat", "REAL"),
    ("teams", "venue_lon", "REAL"),
    ("teams", "venue_geocoded_utc", "TEXT"),
    # A MARKET TABLE'S MIGRATION CANNOT LIVE HERE. `db` is on every
    # sport's prediction path, and LAW 1's closure scan rejects a
    # module on that path for NAMING a market table in code -- which it
    # did, within a minute of the column being added. The snapshot
    # table's migration lives in `gridiron.market.lines`, which is
    # already quarantined and is the only writer of those rows.
    # The shown number and the correction that produced it. Added
    # 2026-08-31; every row written before then is NULL, which reads
    # correctly as "no correction was in force", because none was.
    ("predictions", "calibrated_prob", "REAL"),
    ("predictions", "correction_version", "INTEGER"),
    ("predictions", "prop_type", "TEXT"),
    # S1: every record belongs to exactly one sport (LAW 6). Existing rows
    # backfill to 'nfl' via the column default, which is correct: they are all
    # NFL, and there was no other sport when they were written.
    ("games", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("predictions", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("factors", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("factor_scores", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("model_fits", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("nba_injuries", "player_name", "TEXT NOT NULL DEFAULT ''"),
    # The LEAGUE's own calendar date for a game, which is not the UTC date. A
    # game tipping at 02:00 UTC is the previous evening where it is played, and
    # every rolling window cut on the UTC date therefore INCLUDED the game it
    # was predicting: 76.8% of NBA games and 25.1% of MLB ones.
    ("games", "league_date", "TEXT"),
    # When this device last saw the record. Per session, so two devices each
    # get their own "since you last looked" rather than stealing it from
    # one another.
    ("sessions", "last_seen_utc", "TEXT"),
    # Strikeouts are the pitcher prop market; home runs allowed is the input to
    # the batters' home-run market. Both were already in the cached game-log
    # responses and simply were not being read, so this widening costs no
    # fetches at all -- the loader re-parses what is already stored.
    ("mlb_pitcher_starts", "strike_outs", "INTEGER"),
    ("mlb_pitcher_starts", "home_runs_allowed", "INTEGER"),
    # The CITY form of a club's name. Prose reads "the market has St. Louis at
    # 48%"; a heading reads "St. Louis Cardinals". Both come from the feed.
    ("teams", "location", "TEXT"),
)


#: WITHDRAWN FEATURES, dropped forward so a database that already holds a
#: withdrawn table comes into line with the schema instead of keeping a table
#: nothing reads. `operator_calls` went 2026-09-02 by ruling (GRIDIRON_16 R1).
#:
#: DELIBERATELY NOT A GENERAL "RUN THIS SQL" HOOK. It drops NAMED objects and
#: nothing else, and `_schema_defines` refuses anything `schema.sql` still
#: creates, so the record's own tables cannot be named here --
#: because a migration that could drop `predictions` would be the way around
#: LAW 3 that every trigger in this schema exists to prevent. Adding a row
#: here is a deliberate act with a dated note, exactly as adding a factor is.
WITHDRAWN: tuple[tuple[str, str], ...] = (
    ("TABLE", "operator_calls"),
    ("INDEX", "operator_calls_pred"),
    ("INDEX", "operator_calls_open"),
    ("TRIGGER", "operator_calls_no_delete"),
    ("TRIGGER", "operator_calls_no_update"),
    ("TRIGGER", "operator_calls_resolve_once"),
)

class WithdrawalRefused(RuntimeError):
    """A withdrawal that would have touched something still in the schema."""


def _schema_defines(name: str, schema_sql: str) -> bool:
    """Does the schema script still create this object?"""
    lowered = schema_sql.lower()
    for kind in ("table", "index", "trigger", "view"):
        if f"create {kind} if not exists {name.lower()}" in lowered:
            return True
        if f"create {kind} {name.lower()}" in lowered:
            return True
    return False


def _withdraw(conn: sqlite3.Connection) -> list[str]:
    """Drop what has been withdrawn. Idempotent; silent when already gone.

    THE RULE NAMES NOTHING, and that is deliberate twice over.

    A withdrawal may only drop an object THE SCHEMA NO LONGER DEFINES. Deleting
    the CREATE statement is therefore the act that authorises the drop, and the
    two cannot drift: while `predictions` is still created by `schema.sql` --
    which it always will be -- no entry here can touch it. That is the check
    that keeps this from becoming the way around LAW 3.

    The first version listed the record's tables explicitly instead, and LAW
    1's closure scan rejected the module within one run: `db` is on every
    sport's prediction path, so naming a market table here is exactly the
    thing the scan exists to catch. The rule that names nothing is both safer
    and shorter, which is usually how that goes.
    """
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    dropped = []
    for kind, name in WITHDRAWN:
        if kind not in ("TABLE", "INDEX", "TRIGGER", "VIEW"):
            raise WithdrawalRefused(f"unknown object kind {kind!r}")
        if _schema_defines(name, schema_sql):
            raise WithdrawalRefused(
                f"WITHDRAWAL REFUSED: {name!r} is still created by schema.sql, "
                f"so it is part of the live schema and not a withdrawn "
                f"feature. Remove the CREATE statement first -- that deletion "
                f"is what authorises this drop, and requiring it is what keeps "
                f"a withdrawal from becoming a way to drop the record."
            )
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
            (kind.lower(), name)).fetchone()
        if exists:
            conn.execute(f"DROP {kind} IF EXISTS {name}")
            dropped.append(f"{kind.lower()} {name}")
    return dropped


def _migrate(conn: sqlite3.Connection) -> list[str]:
    """Widen existing tables before the schema script runs.

    Order matters: the script creates indexes over columns these migrations
    add, so on an already-populated database the ALTERs must land first. On a
    fresh database the tables do not exist yet, `PRAGMA table_info` returns
    nothing, and each migration is skipped — the CREATE TABLE statements
    already carry the column.
    """
    applied = []
    for table, column, decl in MIGRATIONS:
        info = list(conn.execute(f"PRAGMA table_info({table})"))
        if not info:
            continue            # fresh database; the schema script defines it
        if column not in {r[1] for r in info}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            applied.append(f"{table}.{column}")
    return applied


#: Triggers attached to `predictions`. Named here because a table rename
#: carries its triggers with it, and the schema script would then fail to
#: recreate them under the same names.
PREDICTION_TRIGGERS = (
    "predictions_no_delete",
    "predictions_no_update",
    "predictions_resolve_once",
    "voided_prediction_stays_void",
)


class MigrationRefused(RuntimeError):
    """A widening migration could not be completed safely, so nothing changed."""


#: Tables whose `sport` CHECK must admit every declared sport, and which carry
#: no law that a rebuild could violate. `predictions` is NOT here: it is
#: append-only, its rebuild is verified row-for-row, and it has its own path.
#: Tables whose sport CHECK is rebuilt on sight when a sport is declared.
#:
#: EVERY TABLE THAT CARRIES THE CHECK IS HERE from 2026-09-03, when UFC was
#: declared. It used to name `session_seen` alone, which is how the same
#: defect bit three times in one build: the record accepted college games,
#: then refused the first prediction about one, then served a 500 on the
#: college digest. A list that has to be extended by hand every time a sport
#: is added is a list that will be short again.
#:
#: `predictions` is DELIBERATELY ABSENT and is widened separately, with the
#: row-count-and-hash verification LAW 3 deserves. Everything here holds facts
#: or derived numbers rather than claims, so a plain verified copy is enough --
#: but it is still verified, which the first version of this was not.
WIDEN_ON_SIGHT = ("session_seen", "games", "factors", "factor_scores",
                  "model_fits")


def widen_notification_states(conn: sqlite3.Connection) -> bool:
    """Admit the 'sending' state on a database created before 2026-09-05.

    SQLite applies a CHECK at CREATE and never revisits it, so a database made
    before the state existed refuses every row `notify.send` now writes -- and
    it would refuse it BEFORE the post rather than after, which is a different
    failure from the one being fixed but no better.

    A PLAIN VERIFIED COPY, like `widen_sport_checks`. The table holds delivery
    history, no forecast and no claim, and nothing references it but its own
    index. The row count is checked before the original is dropped, because
    the last rebuild this project did left 311,655 rows in a table called
    `games_narrow` when a foreign key tripped after the copy.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='notifications'"
    ).fetchone()
    if row is None or "'sending'" in (row[0] or ""):
        return False

    before = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN;
        CREATE TABLE notifications_wide (
            id            INTEGER PRIMARY KEY,
            queued_utc    TEXT    NOT NULL,
            sent_utc      TEXT,
            kind          TEXT    NOT NULL CHECK (kind IN ('results', 'failure')),
            title         TEXT    NOT NULL,
            body          TEXT    NOT NULL,
            state         TEXT    NOT NULL
                          CHECK (state IN ('queued','sending','sent','failed')),
            channels_json TEXT
        );
        INSERT INTO notifications_wide
            SELECT id, queued_utc, sent_utc, kind, title, body, state,
                   channels_json
              FROM notifications;
        COMMIT;
    """)
    after = conn.execute("SELECT COUNT(*) FROM notifications_wide").fetchone()[0]
    if after != before:
        conn.execute("DROP TABLE notifications_wide")
        conn.commit()
        raise MigrationRefused(
            f"notifications rebuild copied {after} of {before} rows; the "
            f"original is untouched and nothing was dropped.")
    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN;
        DROP TABLE notifications;
        ALTER TABLE notifications_wide RENAME TO notifications;
        CREATE INDEX IF NOT EXISTS notifications_when ON notifications (id DESC);
        COMMIT;
    """)
    conn.commit()
    return True


def widen_sport_checks(conn: sqlite3.Connection) -> list[str]:
    """Rebuild small tables whose sport CHECK predates a newly declared sport.

    SQLite applies a CHECK when the table is created and never revisits it, so
    adding a sport to `config.SPORTS` and to `schema.sql` leaves every EXISTING
    database refusing it. That has now bitten three times in one build: the
    live record accepted 892 college games, then refused the first prediction
    about one, then served a 500 on the college digest because the
    session-marker table had the old list too.

    These tables hold no forecast and no claim -- `session_seen` records when a
    browser last looked -- so the rebuild is a plain copy rather than the
    verified one `predictions` gets. What matters is that it happens at all.
    """
    from . import config

    done = []
    for table in WIDEN_ON_SIGHT:
        # RECOVER A REBUILD THAT DIED HALF WAY. If `<table>_narrow` is still
        # here, a previous attempt renamed the table aside and never finished.
        # That happened for real on 2026-09-03: `games` is referenced by seven
        # other tables, so DROPping the renamed original tripped a foreign-key
        # constraint after the copy, the transaction rolled back, and the
        # database was left with an empty `games` and 21,527 rows sitting in
        # `games_narrow`. Nothing was lost, and nothing recovered it either.
        stale = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (f"{table}_narrow",)).fetchone()
        if stale:
            done.append(_finish_widening_table(conn, table))
            continue

        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not row or "sport IN" not in (row[0] or ""):
            continue
        stored = row[0]
        if all(f"'{sport}'" in stored for sport in config.SPORTS):
            continue
        expected = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.execute("PRAGMA legacy_alter_table = ON")
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_narrow")
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        done.append(_finish_widening_table(conn, table, expected))
    return done


def _finish_widening_table(conn: sqlite3.Connection, table: str,
                           expected: int | None = None) -> str:
    """Copy `<table>_narrow` back into the rebuilt table, verify, then drop.

    FOREIGN KEYS ARE OFF FOR THE COPY, and that is not laziness. Seven tables
    reference `games(id)`; renaming it aside repoints their constraints at
    `games_narrow`, so the drop fails and takes the whole rebuild with it. The
    verified `predictions` widening has done this since it was written and
    this one did not, which is the whole of the 2026-09-03 failure.

    EVERY ROW IS COUNTED. The copy uses OR IGNORE because the schema script may
    have seeded reference rows, and OR IGNORE is exactly the construct this
    project distrusts -- so it is checked rather than believed. A short copy
    leaves the original in place under `<table>_narrow` and raises.
    """
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    narrow = {r[1] for r in conn.execute(f"PRAGMA table_info({table}_narrow)")}
    shared = [c for c in columns if c in narrow]
    joined = ", ".join(shared)
    if expected is None:
        expected = conn.execute(
            f"SELECT COUNT(*) FROM {table}_narrow").fetchone()[0]

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute(
            f"INSERT OR IGNORE INTO {table} ({joined})"
            f" SELECT {joined} FROM {table}_narrow")
        after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if after < expected:
            conn.rollback()
            raise MigrationRefused(
                f"widening `{table}` would have lost rows: {expected} before, "
                f"{after} after. The original is left in place as "
                f"`{table}_narrow` and nothing was dropped."
            )
        conn.execute(f"DROP TABLE {table}_narrow")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return f"{table} ({after} rows)"


def _needs_market_type_widening(conn: sqlite3.Connection) -> bool:
    """Whether the stored `predictions` table is narrower than the schema.

    TWO CHECKS HAVE NEEDED WIDENING NOW, and the second was found the hard way:
    a sport added to `config.SPORTS` and to `schema.sql` is still refused by an
    EXISTING database, because SQLite applies a CHECK when the table is created
    and never revisits it. The live record accepted 892 college football games
    and then refused the first prediction about one of them.

    So this asks the general question -- does the stored definition admit
    everything the current schema does -- rather than naming one value.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='predictions'"
    ).fetchone()
    if not row:
        return False
    stored = row[0] or ""
    if "moneyline" not in stored:
        return True
    # Every declared sport AND every market type must appear in the stored
    # CHECKs, or rows for the newest one cannot be written. Both were found
    # the same way: by a prediction being refused after everything else about
    # the sport already worked.
    from . import config

    if any(f"'{sport}'" not in stored for sport in config.SPORTS):
        return True
    markets = {"spread", "prop", "moneyline"}
    for sport in config.SPORTS:
        for market in config.SPORT_MARKETS.get(sport, ()):
            markets.add("prop" if market in config.SPORT_PROP_MARKETS.get(sport, ())
                        else market)
    return any(f"'{m}'" not in stored for m in markets)


def _widen_market_type(conn: sqlite3.Connection) -> int | None:
    """Rebuild `predictions` so its market_type CHECK admits 'moneyline'.

    SQLite cannot alter a CHECK in place, so the table is renamed aside, the
    schema script recreates it wide, and every row is copied back verbatim.

    This does not weaken LAW 3. The law forbids editing, deleting or re-scoring
    a prediction; it does not forbid widening the set of questions the table can
    hold. Every row is copied with every column unchanged, and the copy is
    VERIFIED — matching row counts and matching per-row hashes of the fields the
    law protects — before the old table is dropped. If verification fails the
    old table is left in place and the migration raises.
    """
    before = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    fingerprint_sql = (
        "SELECT id, created_utc, game_id, market_type, subject, line_asked,"
        " model_prob, model_side, predictor, factor_set_version, resolved_utc,"
        " outcome FROM {} ORDER BY id"
    )
    before_rows = [
        tuple(r) for r in conn.execute(fingerprint_sql.format("predictions"))
    ]

    conn.execute("PRAGMA foreign_keys = OFF")
    # legacy_alter_table stops SQLite rewriting the foreign keys in
    # `market_snapshots` and `prediction_voids` to follow the rename. Without
    # it those children end up pointing at the renamed-aside table, the drop
    # fails, and the record is left split across two tables. Learned the hard
    # way on the first run of this migration.
    conn.execute("PRAGMA legacy_alter_table = ON")
    for trigger in PREDICTION_TRIGGERS:
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    conn.execute("ALTER TABLE predictions RENAME TO predictions_pre_multisport")
    conn.execute("PRAGMA legacy_alter_table = OFF")
    # The caller runs the schema script next, which recreates `predictions`
    # with the wider CHECK and every index and trigger.
    return before


def _finish_widening(conn: sqlite3.Connection, expected: int) -> None:
    columns = [r[1] for r in conn.execute("PRAGMA table_info(predictions_pre_multisport)")]
    shared = [c for c in columns if c in set(db_columns(conn, "predictions"))]
    joined = ", ".join(shared)
    conn.execute(
        f"INSERT INTO predictions ({joined}) SELECT {joined} FROM predictions_pre_multisport"
    )
    conn.execute("PRAGMA foreign_keys = OFF")
    after = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    if after != expected:
        conn.rollback()
        raise MigrationRefused(
            f"widening `predictions` would have changed the record: {expected} rows "
            f"before, {after} after. The old table is left in place under "
            "`predictions_pre_multisport` and nothing was dropped."
        )
    conn.execute("DROP TABLE predictions_pre_multisport")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def db_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def widen_task_run_results(conn: sqlite3.Connection) -> bool:
    """Admit the 'running' result on a database created before 2026-09-05.

    Same reason and same shape as `widen_notification_states`: SQLite keeps
    the CHECK it was created with, so an older record would refuse the row
    `run_task` now writes first -- and refuse it before the task ran, which
    would stop every scheduled task on the machine at once.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='task_runs'"
    ).fetchone()
    if row is None or "'running'" in (row[0] or ""):
        return False

    before = conn.execute("SELECT COUNT(*) FROM task_runs").fetchone()[0]
    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN;
        CREATE TABLE task_runs_wide (
            id            INTEGER PRIMARY KEY,
            task          TEXT    NOT NULL,
            started_utc   TEXT    NOT NULL,
            finished_utc  TEXT,
            result        TEXT    NOT NULL
                          CHECK (result IN ('running', 'ok', 'noop', 'missed', 'failed')),
            detail        TEXT,
            payload_json  TEXT
        );
        INSERT INTO task_runs_wide
            SELECT id, task, started_utc, finished_utc, result, detail, payload_json
              FROM task_runs;
        COMMIT;
    """)
    after = conn.execute("SELECT COUNT(*) FROM task_runs_wide").fetchone()[0]
    if after != before:
        conn.execute("DROP TABLE task_runs_wide")
        conn.commit()
        raise MigrationRefused(
            f"task_runs: copied {after} of {before} rows; the original is untouched")
    conn.executescript("""
        BEGIN;
        DROP TABLE task_runs;
        ALTER TABLE task_runs_wide RENAME TO task_runs;
        COMMIT;
        PRAGMA foreign_keys=ON;
    """)
    return True


def init(conn: sqlite3.Connection) -> None:
    """Create the schema. Idempotent — every object is IF NOT EXISTS."""
    _migrate(conn)
    # AFTER the widenings and BEFORE the schema script, so a withdrawn object
    # is gone before anything tries to recreate it.
    _withdraw(conn)
    widen_sport_checks(conn)
    # AND THE DELIVERY RECORD'S STATES (2026-09-05). Same reason, different
    # CHECK: a database made before 'sending' existed would refuse every row
    # `notify.send` writes.
    widen_notification_states(conn)
    # AND THE RUN LEDGER'S RESULTS (audit 2026-09-05): a 'running' row is
    # written before a task does anything, and an older CHECK would refuse it.
    widen_task_run_results(conn)
    widening = _widen_market_type(conn) if _needs_market_type_widening(conn) else None
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    if widening is not None:
        _finish_widening(conn, widening)
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('kind', 'live')"
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return default if row is None else row["value"]


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?,?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def database_kind(conn: sqlite3.Connection) -> dict:
    """`live` = predictions made before kickoff. `backtest` = made afterwards
    over completed games, which proves the pipeline works and nothing else."""
    return {
        "kind": get_meta(conn, "kind", "live"),
        "note": get_meta(conn, "kind_note"),
    }


def open_db(path: Path | str | None = None) -> sqlite3.Connection:
    conn = connect(path)
    init(conn)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> object:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]
