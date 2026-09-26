-- THE EIGHT TABLES OF SCHEMA RULING 2, AS THE LIVE RECORD HOLDS THEM.
--
-- Read through the read-only door (db.read_the_live_record) at
-- 2026-09-25T03:48Z, byte for byte as sqlite_master stores them: the eight
-- tables whose definitions differ in behaviour from the release, and every
-- index and trigger on them. Each table's differing column reached the
-- record by ALTER TABLE ... ADD COLUMN, which is why it sits last and why
-- its CHECK is missing (or, for nba_injuries.player_name, why it carries a
-- DEFAULT the release does not). The two LAW 1 snapshot triggers name
-- "predictions" quoted, as a RENAME wrote them.
--
-- THREE ADDITIONS, market_snapshots_no_delete (schema ruling 4, built
-- 2026-09-25), market_snapshots_never_replaced (the adversarial review of
-- 3603300, the same day) and market_snapshots_never_replaced_by_update (the
-- rehearsal of its fixes, the same day): the release that carries the
-- migration creates each on the record, through the schema script's
-- if-absent form, before the migration runs.
--
-- Used by the tests and the plantings to put a scratch record into the
-- shapes the migration is measured against. Not schema; nothing runs it on
-- a record.

CREATE TABLE factors (
    name          TEXT PRIMARY KEY,
    added_utc     TEXT NOT NULL
                  CHECK (added_utc LIKE '____-__-__T%'),
    -- LAW 2: a factor without a stated causal reason is not a factor.
    rationale     TEXT NOT NULL
                  CHECK (length(trim(rationale)) >= 20),
    active        INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    deactivated_utc TEXT,
    note          TEXT
, sport TEXT NOT NULL DEFAULT 'nfl');

CREATE TABLE factor_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_utc  TEXT NOT NULL,
    factor        TEXT NOT NULL REFERENCES factors (name),
    window        TEXT NOT NULL,        -- 'since_activation' | 'season:2026' | ...
    n             INTEGER NOT NULL,     -- LAW 4: never nullable
    brier         REAL,
    log_loss      REAL,
    note          TEXT
, sport TEXT NOT NULL DEFAULT 'nfl');

CREATE TABLE model_fits (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    fitted_utc         TEXT NOT NULL,
    factor_set_version TEXT NOT NULL,
    market_type        TEXT NOT NULL,
    train_through      TEXT NOT NULL,   -- 'season:2025 week:22' — what it saw
    n_train            INTEGER NOT NULL,
    coefficients_json  TEXT NOT NULL,
    note               TEXT
, sport TEXT NOT NULL DEFAULT 'nfl');

CREATE TABLE market_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL REFERENCES "predictions" (id),
    fetched_utc   TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    line          REAL,
    implied_prob  REAL,
    public_pct    REAL       -- NULL when no free source is available; never a proxy
, kind TEXT NOT NULL DEFAULT 'open_at_predict');

CREATE TABLE mlb_lineups (
    game_id     TEXT    NOT NULL REFERENCES games (id),
    side        TEXT    NOT NULL CHECK (side IN ('home', 'away')),
    slot        INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 9),
    player_id   INTEGER NOT NULL,
    player_name TEXT,
    recorded_utc TEXT   NOT NULL, source TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (game_id, side, slot)
);

CREATE TABLE prediction_ranks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id       INTEGER NOT NULL REFERENCES predictions (id),
    ranker_version      TEXT    NOT NULL,
    sport               TEXT    NOT NULL,
    market_type         TEXT    NOT NULL,
    prop_type           TEXT,
    -- the score and the three inputs that made it, each kept so a rank can be
    -- read back and argued with rather than merely trusted
    rank_score          REAL    NOT NULL CHECK (rank_score >= 0 AND rank_score <= 1),
    confidence          REAL    NOT NULL,
    completeness        REAL    NOT NULL,
    -- NULL where the market never quoted a line: absent stays absent, and an
    -- absent edge is never written as a zero one
    edge                REAL,
    -- whether the edge was allowed to move the ordering (its market has passed
    -- its own gate), and the settled count that decided it
    edge_counted        INTEGER NOT NULL DEFAULT 0 CHECK (edge_counted IN (0, 1)),
    edge_gate_n         INTEGER NOT NULL DEFAULT 0,
    factor_set_version  TEXT,
    -- a rank computed after the games were played, for a row written before
    -- this formula existed. Excluded from any comparison that scores the
    -- ranker, because it is not the same object as a rank made in advance.
    backfilled          INTEGER NOT NULL DEFAULT 0 CHECK (backfilled IN (0, 1)),
    created_utc         TEXT    NOT NULL, on_shortlist INTEGER NOT NULL DEFAULT 0, shortlist_place INTEGER,
    UNIQUE (prediction_id, ranker_version)
);

CREATE TABLE ufc_events (
    id            TEXT PRIMARY KEY,        -- ESPN event id, the card
    name          TEXT NOT NULL,
    event_utc     TEXT,                    -- ISO-8601 Z; NULL if TBD
    season        INTEGER NOT NULL,
    fetched_utc   TEXT NOT NULL
, event_tier TEXT, is_card INTEGER NOT NULL DEFAULT 1, venue_country TEXT, venue_state TEXT, venue_city TEXT);

CREATE TABLE nba_injuries (
    player_id    INTEGER NOT NULL,
    team         TEXT    NOT NULL,
    status       TEXT    NOT NULL,
    detail       TEXT,
    fetched_utc  TEXT    NOT NULL, player_name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (player_id)
);

CREATE INDEX fs_factor ON factor_scores (factor, computed_utc);

CREATE UNIQUE INDEX market_snapshots_one_per_kind
    ON market_snapshots (prediction_id, kind);

CREATE INDEX mlb_lineups_player ON mlb_lineups (player_id);

CREATE INDEX nba_injuries_team ON nba_injuries (team);

CREATE INDEX prediction_ranks_sport
    ON prediction_ranks (sport, ranker_version, rank_score);

CREATE INDEX snap_pred ON market_snapshots (prediction_id);

CREATE TRIGGER factors_no_delete
BEFORE DELETE ON factors
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 2: a factor may be deactivated but never deleted; '
        || 'its history stays');
END;

CREATE TRIGGER rank_comes_after_its_prediction
BEFORE INSERT ON prediction_ranks
FOR EACH ROW
WHEN NEW.created_utc <= (SELECT created_utc FROM predictions WHERE id = NEW.prediction_id)
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 1: a rank is computed after the blind window closes; '
        || 'this one is stamped at or before its own prediction');
END;

CREATE TRIGGER ranks_no_delete
BEFORE DELETE ON prediction_ranks
BEGIN
    SELECT RAISE(ABORT, 'GRIDIRON LAW 3: a rank is never deleted');
END;

CREATE TRIGGER ranks_no_update
BEFORE UPDATE ON prediction_ranks
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a rank is append-only; compute a new one under a new '
        || 'ranker version rather than rewriting this row');
END;

CREATE TRIGGER snapshot_not_before_prediction
BEFORE INSERT ON market_snapshots
FOR EACH ROW
WHEN NEW.fetched_utc < (SELECT created_utc FROM "predictions" WHERE id = NEW.prediction_id)
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 1: market snapshot is timestamped before the prediction '
        || 'it is attached to; the line was fetched too early');
END;

CREATE TRIGGER snapshot_requires_prediction
BEFORE INSERT ON market_snapshots
FOR EACH ROW
WHEN (SELECT COUNT(*) FROM "predictions" WHERE id = NEW.prediction_id) = 0
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 1: a market snapshot cannot exist before its prediction row');
END;

CREATE TRIGGER market_snapshots_no_delete
BEFORE DELETE ON market_snapshots
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a market snapshot is never deleted; what the market '
        || 'said beside a forecast stays in its record');
END;

CREATE TRIGGER market_snapshots_never_replaced
BEFORE INSERT ON market_snapshots
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM market_snapshots s WHERE s.id = NEW.id)
  OR EXISTS (SELECT 1 FROM market_snapshots s
              WHERE s.prediction_id = NEW.prediction_id AND s.kind = NEW.kind)
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a market snapshot is never replaced; one look of '
        || 'each kind per forecast, written once');
END;

CREATE TRIGGER market_snapshots_never_replaced_by_update
BEFORE UPDATE OF id, prediction_id, kind ON market_snapshots
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM market_snapshots s
              WHERE s.id = NEW.id AND s.id IS NOT OLD.id)
  OR EXISTS (SELECT 1 FROM market_snapshots s
              WHERE s.prediction_id = NEW.prediction_id AND s.kind = NEW.kind
                AND s.id IS NOT OLD.id)
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a market snapshot is never replaced; an update may '
        || 'not take the place of another stored snapshot');
END;
