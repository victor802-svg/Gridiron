-- Gridiron schema.
--
-- Three of the five laws are enforced here rather than in Python, because a
-- convention in Python is a thing a future session can forget and a CHECK
-- constraint is not.
--
--   LAW 1 (blind first)  : market numbers live in `market_lines_raw` and
--                          `market_snapshots`. The `games` table deliberately
--                          has NO spread/total/moneyline column, so the
--                          prediction path cannot read a line even by accident.
--                          Triggers reject a snapshot that predates its
--                          prediction.
--   LAW 2 (declared)     : `factors.rationale` is NOT NULL and must be a real
--                          sentence; `added_utc` must be a real date.
--   LAW 3 (append-only)  : triggers ABORT on any UPDATE that touches a
--                          prediction's substance, and on any DELETE at all.
--                          The single permitted mutation is the resolution
--                          write, and only from unresolved to resolved.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;


-- What kind of database this is. A backtest database holds predictions made
-- retrospectively over completed games; a live one holds predictions made
-- before kickoff. They must never be read as the same record, so the kind is
-- stored here and the interface says so loudly.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);


-- ---------------------------------------------------------------------------
-- Facts about the world. No market data lives in this section.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS games (
    id            TEXT PRIMARY KEY,          -- source game id, namespaced by sport
    -- LAW 6: every row belongs to exactly one sport, and nothing aggregates
    -- across them. Defaulted to 'nfl' so rows written before there was a second
    -- sport keep the only value they could have had.
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba')),
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    game_type     TEXT    NOT NULL,          -- REG | WC | DIV | CON | SB
    kickoff_utc   TEXT,                      -- ISO-8601 Z; NULL if TBD
    home          TEXT    NOT NULL,
    away          TEXT    NOT NULL,
    status        TEXT    NOT NULL           -- scheduled | final
                  CHECK (status IN ('scheduled', 'final')),
    home_score    INTEGER,
    away_score    INTEGER,
    CHECK ((status = 'final') = (home_score IS NOT NULL AND away_score IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS games_season_week ON games (sport, season, week);
CREATE INDEX IF NOT EXISTS games_sport_status ON games (sport, status);
CREATE INDEX IF NOT EXISTS games_kickoff     ON games (kickoff_utc);

-- Non-market context for a game: rest, venue, observed weather. Separated from
-- `games` only for tidiness; it is equally readable by the prediction path.
CREATE TABLE IF NOT EXISTS game_conditions (
    game_id       TEXT PRIMARY KEY REFERENCES games (id),
    home_rest     INTEGER,
    away_rest     INTEGER,
    roof          TEXT,       -- outdoors | dome | closed | open
    surface       TEXT,
    neutral_site  INTEGER NOT NULL DEFAULT 0,
    div_game      INTEGER,
    stadium       TEXT,
    temp_f        REAL,       -- observed, populated post-game by the source
    wind_mph      REAL
);

-- Forecast weather for an upcoming outdoor game, fetched before kickoff.
-- Kept apart from observed weather so we never confuse a forecast we predicted
-- on with the temperature that actually happened.
CREATE TABLE IF NOT EXISTS weather_forecasts (
    game_id       TEXT PRIMARY KEY REFERENCES games (id),
    fetched_utc   TEXT NOT NULL,
    source        TEXT NOT NULL,
    temp_f        REAL,
    wind_mph      REAL,
    precip_pct    REAL
);

CREATE TABLE IF NOT EXISTS team_week_stats (
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    team          TEXT    NOT NULL,
    game_id       TEXT    REFERENCES games (id),
    opponent      TEXT,
    points_for    INTEGER,
    points_against INTEGER,
    plays         INTEGER,     -- offensive plays, for pace
    PRIMARY KEY (season, week, team)
);

CREATE TABLE IF NOT EXISTS player_week_stats (
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    player_id     TEXT    NOT NULL,
    player_name   TEXT,
    position      TEXT,
    team          TEXT,
    opponent      TEXT,
    -- the stat lines props are written against
    attempts        REAL,
    completions     REAL,
    passing_yards   REAL,
    passing_tds     REAL,
    carries         REAL,
    rushing_yards   REAL,
    rushing_tds     REAL,
    targets         REAL,
    receptions      REAL,
    receiving_yards REAL,
    receiving_tds   REAL,
    PRIMARY KEY (season, week, player_id)
);
CREATE INDEX IF NOT EXISTS pws_player ON player_week_stats (player_id, season, week);
CREATE INDEX IF NOT EXISTS pws_name   ON player_week_stats (player_name);

CREATE TABLE IF NOT EXISTS injuries (
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    team          TEXT    NOT NULL,
    player_id     TEXT,
    player_name   TEXT,
    position      TEXT,
    report_status TEXT,       -- Out | Doubtful | Questionable | '' ; participation only
    practice_status TEXT,
    PRIMARY KEY (season, week, team, player_name)
);
CREATE INDEX IF NOT EXISTS inj_lookup ON injuries (season, week, team);

-- Offensive snap share, joined by name because that is the key the source
-- publishes. A player who cannot be matched is ABSENT, never assumed.
CREATE TABLE IF NOT EXISTS snap_counts (
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    team          TEXT    NOT NULL,
    player_name   TEXT    NOT NULL,
    position      TEXT,
    offense_snaps INTEGER,
    offense_pct   REAL,
    PRIMARY KEY (season, week, team, player_name)
);
CREATE INDEX IF NOT EXISTS snaps_lookup ON snap_counts (season, week, team);


-- ---------------------------------------------------------------------------
-- MLB. Game facts only; no market number appears in this section.
-- ---------------------------------------------------------------------------

-- Who is announced to start. The announcement is the whole point: a prediction
-- made before probables are posted records that absence rather than guessing,
-- and that happens often enough to be shown on the card.
CREATE TABLE IF NOT EXISTS mlb_probables (
    game_id       TEXT NOT NULL REFERENCES games (id),
    side          TEXT NOT NULL CHECK (side IN ('home','away')),
    pitcher_id    INTEGER,
    pitcher_name  TEXT,
    recorded_utc  TEXT NOT NULL,
    PRIMARY KEY (game_id, side)
);

-- One row per pitcher appearance, from the player's own game log.
CREATE TABLE IF NOT EXISTS mlb_pitcher_starts (
    pitcher_id    INTEGER NOT NULL,
    season        INTEGER NOT NULL,
    game_date     TEXT    NOT NULL,
    game_pk       INTEGER,
    is_start      INTEGER NOT NULL DEFAULT 0,
    innings       REAL,
    runs          INTEGER,
    earned_runs   INTEGER,
    batters_faced INTEGER,
    PRIMARY KEY (pitcher_id, season, game_date, game_pk)
);
CREATE INDEX IF NOT EXISTS mlb_starts_lookup
    ON mlb_pitcher_starts (pitcher_id, game_date);

-- One row per team per game: the club's own view of a result.
CREATE TABLE IF NOT EXISTS mlb_team_games (
    game_id        TEXT    NOT NULL REFERENCES games (id),
    team           TEXT    NOT NULL,
    opponent       TEXT    NOT NULL,
    season         INTEGER NOT NULL,
    game_date      TEXT    NOT NULL,
    is_home        INTEGER NOT NULL,
    runs_for       INTEGER,
    runs_against   INTEGER,
    innings_played REAL,
    PRIMARY KEY (game_id, team)
);
CREATE INDEX IF NOT EXISTS mlb_team_games_lookup
    ON mlb_team_games (team, game_date);


-- --- basketball -------------------------------------------------------------
-- One row per team per game, from the league team game log.
CREATE TABLE IF NOT EXISTS nba_team_games (
    game_id      TEXT    NOT NULL REFERENCES games (id),
    team         TEXT    NOT NULL,
    opponent     TEXT    NOT NULL,
    season       INTEGER NOT NULL,
    game_date    TEXT    NOT NULL,
    is_home      INTEGER NOT NULL,
    points_for   INTEGER,
    points_against INTEGER,
    minutes      REAL,      -- team minutes played; 240 in regulation, more in OT
    fga          INTEGER,
    fta          INTEGER,
    oreb         INTEGER,
    turnovers    INTEGER,
    PRIMARY KEY (game_id, team)
);
CREATE INDEX IF NOT EXISTS nba_team_games_lookup
    ON nba_team_games (team, game_date);

-- One row per player per game. This is the prop substrate: minutes and the four
-- counting stats the four prop markets ask about.
CREATE TABLE IF NOT EXISTS nba_player_games (
    game_id      TEXT    NOT NULL REFERENCES games (id),
    player_id    INTEGER NOT NULL,
    player_name  TEXT    NOT NULL,
    team         TEXT    NOT NULL,
    opponent     TEXT    NOT NULL,
    season       INTEGER NOT NULL,
    game_date    TEXT    NOT NULL,
    is_home      INTEGER NOT NULL,
    minutes      REAL,
    points       INTEGER,
    rebounds     INTEGER,
    assists      INTEGER,
    threes       INTEGER,
    fga          INTEGER,
    fta          INTEGER,
    threes_att   INTEGER,
    turnovers    INTEGER,
    PRIMARY KEY (game_id, player_id)
);
CREATE INDEX IF NOT EXISTS nba_player_games_lookup
    ON nba_player_games (player_id, game_date);
CREATE INDEX IF NOT EXISTS nba_player_games_team
    ON nba_player_games (team, game_date);
-- The prop path asks what an OPPONENT has been giving up, which filters on a
-- column the other two indexes do not cover. Without this every such call is a
-- full scan of a hundred thousand rows, and a prop fit that should take minutes
-- takes hours.
CREATE INDEX IF NOT EXISTS nba_player_games_opponent
    ON nba_player_games (opponent, game_date);

-- The current injury report, one row per listed player. This table is a
-- SNAPSHOT, not a history: the source publishes only what is true now, so it is
-- replaced on each fetch rather than appended to. It is therefore usable for a
-- forward prediction and useless for a backtest, which is stated in
-- `nba_availability_index`'s rationale rather than papered over.
CREATE TABLE IF NOT EXISTS nba_injuries (
    player_id    INTEGER NOT NULL,   -- ESPN's athlete id, NOT a stats.nba.com id
    player_name  TEXT    NOT NULL,
    team         TEXT    NOT NULL,
    status       TEXT    NOT NULL,
    detail       TEXT,
    fetched_utc  TEXT    NOT NULL,
    PRIMARY KEY (player_id)
);
CREATE INDEX IF NOT EXISTS nba_injuries_team ON nba_injuries (team);


-- ---------------------------------------------------------------------------
-- LAW 1 QUARANTINE. Everything below this line is market data.
-- Only `gridiron.market` may read these two tables. The prediction path has no
-- import path to that module, and these columns exist on no table it reads.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS market_lines_raw (
    game_id         TEXT PRIMARY KEY REFERENCES games (id),
    fetched_utc     TEXT NOT NULL,
    source          TEXT NOT NULL,
    spread_line     REAL,      -- home-team spread, nflverse convention
    total_line      REAL,
    home_moneyline  INTEGER,
    away_moneyline  INTEGER
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL REFERENCES predictions (id),
    fetched_utc   TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    line          REAL,
    implied_prob  REAL,
    public_pct    REAL       -- NULL when no free source is available; never a proxy
);
CREATE INDEX IF NOT EXISTS snap_pred ON market_snapshots (prediction_id);


-- ---------------------------------------------------------------------------
-- Predictions and their scoring.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc   TEXT    NOT NULL,
    sport         TEXT    NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba')),
    game_id       TEXT    NOT NULL REFERENCES games (id),
    -- 'moneyline' is MLB's only market; NBA and NFL use spread + prop.
    market_type   TEXT    NOT NULL CHECK (market_type IN ('spread', 'prop', 'moneyline')),
    -- For props, the specific market: passing_yards, receptions, ... Each type
    -- is its own category with its own curve and its own gate; they are never
    -- merged into one "props" number.
    prop_type     TEXT,
    subject       TEXT    NOT NULL,   -- 'KC' for a spread side; 'Patrick Mahomes passing_yards' for a prop
    -- The line the QUESTION was about. Chosen by us before any market contact
    -- (a round number, or a stat-derived reference point). It is NOT the
    -- market's price; the market's price arrives later in market_snapshots.
    line_asked    REAL,
    model_prob    REAL    NOT NULL CHECK (model_prob > 0.0 AND model_prob < 1.0),
    model_side    TEXT    NOT NULL,   -- 'cover' | 'not_cover' | 'over' | 'under'
    predictor     TEXT    NOT NULL CHECK (predictor IN ('statistical', 'llm')),
    factor_set_version TEXT NOT NULL,
    factors_json  TEXT    NOT NULL,
    reasoning     TEXT    NOT NULL,
    degraded      TEXT,               -- non-NULL tag when a path was unavailable
    resolved_utc  TEXT,
    outcome       INTEGER CHECK (outcome IN (0, 1)),  -- 1 = model_side happened
    CHECK ((resolved_utc IS NULL) = (outcome IS NULL))
);
CREATE INDEX IF NOT EXISTS pred_game     ON predictions (game_id);
CREATE INDEX IF NOT EXISTS pred_created  ON predictions (created_utc);
CREATE INDEX IF NOT EXISTS pred_open     ON predictions (resolved_utc) WHERE resolved_utc IS NULL;
-- One answer per question, per predictor, per factor set. Re-running a week is
-- a no-op rather than a second opinion, and a predictor cannot quietly change
-- its mind by writing a row for the other side (LAW 3).
DROP INDEX IF EXISTS pred_unique;
CREATE UNIQUE INDEX IF NOT EXISTS pred_one_answer_per_question
    ON predictions (game_id, market_type, subject, predictor, factor_set_version);
CREATE INDEX IF NOT EXISTS pred_sport ON predictions (sport, market_type, prop_type);

-- Factor names are globally unique across sports, not merely unique within
-- one. Non-NFL factors carry their sport as a prefix (`mlb_home_away`), which
-- keeps the primary key intact, makes a name self-describing wherever it is
-- printed, and means no factor from one sport can ever be scored against
-- another's record by a name collision.
CREATE TABLE IF NOT EXISTS factors (
    name          TEXT PRIMARY KEY,
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba')),
    added_utc     TEXT NOT NULL
                  CHECK (added_utc LIKE '____-__-__T%'),
    -- LAW 2: a factor without a stated causal reason is not a factor.
    rationale     TEXT NOT NULL
                  CHECK (length(trim(rationale)) >= 20),
    active        INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    deactivated_utc TEXT,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS factor_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba')),
    computed_utc  TEXT NOT NULL,
    factor        TEXT NOT NULL REFERENCES factors (name),
    window        TEXT NOT NULL,        -- 'since_activation' | 'season:2026' | ...
    n             INTEGER NOT NULL,     -- LAW 4: never nullable
    brier         REAL,
    log_loss      REAL,
    note          TEXT
);
CREATE INDEX IF NOT EXISTS fs_factor ON factor_scores (factor, computed_utc);

-- LLM budget ledger (G3).
CREATE TABLE IF NOT EXISTS llm_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    called_utc    TEXT NOT NULL,
    day_utc       TEXT NOT NULL,        -- YYYY-MM-DD, for the daily cap
    purpose       TEXT NOT NULL,        -- 'reasoning' | 'format'
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    usd           REAL    NOT NULL,
    game_id       TEXT,
    ok            INTEGER NOT NULL DEFAULT 1,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS llm_day ON llm_calls (day_utc);

-- Fitted statistical model coefficients, kept so a prediction can always be
-- re-explained with the exact weights that produced it.
CREATE TABLE IF NOT EXISTS model_fits (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    sport              TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba')),
    fitted_utc         TEXT NOT NULL,
    factor_set_version TEXT NOT NULL,
    market_type        TEXT NOT NULL,
    train_through      TEXT NOT NULL,   -- 'season:2025 week:22' — what it saw
    n_train            INTEGER NOT NULL,
    coefficients_json  TEXT NOT NULL,
    note               TEXT
);

-- LAW 1 / caching: every upstream fetch, by URL.
CREATE TABLE IF NOT EXISTS http_cache (
    url           TEXT PRIMARY KEY,
    fetched_utc   TEXT NOT NULL,
    etag          TEXT,
    immutable     INTEGER NOT NULL DEFAULT 0,  -- completed seasons never change
    body          BLOB NOT NULL
);


-- A prediction that cannot be settled from real data reaches a terminal VOID
-- state with a stated reason. It is recorded here rather than as a nullable
-- outcome, so `predictions` stays append-only and its CHECK constraints stay
-- exactly as strict as they were. A void prediction is never resolved 0 or 1,
-- and is excluded from every curve while its COUNT is reported beside them --
-- a rising void rate is itself a finding, not a rounding error.
CREATE TABLE IF NOT EXISTS prediction_voids (
    prediction_id INTEGER PRIMARY KEY REFERENCES predictions (id),
    voided_utc    TEXT NOT NULL,
    reason        TEXT NOT NULL CHECK (length(trim(reason)) >= 10)
);


-- ---------------------------------------------------------------------------
-- LAW 3 — append-only, enforced.
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS voids_no_update
BEFORE UPDATE ON prediction_voids
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a void is terminal and its reason cannot be rewritten');
END;

CREATE TRIGGER IF NOT EXISTS voided_prediction_stays_void
BEFORE UPDATE OF resolved_utc, outcome ON predictions
FOR EACH ROW
WHEN NEW.resolved_utc IS NOT NULL
 AND (SELECT COUNT(*) FROM prediction_voids WHERE prediction_id = OLD.id) > 0
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: this prediction was voided for want of real data; '
        || 'it cannot later be given an outcome');
END;

CREATE TRIGGER IF NOT EXISTS predictions_no_delete
BEFORE DELETE ON predictions
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: predictions are append-only and cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS predictions_no_update
BEFORE UPDATE ON predictions
FOR EACH ROW
WHEN OLD.created_utc        IS NOT NEW.created_utc
  OR OLD.game_id            IS NOT NEW.game_id
  OR OLD.market_type        IS NOT NEW.market_type
  OR OLD.subject            IS NOT NEW.subject
  OR OLD.line_asked         IS NOT NEW.line_asked
  OR OLD.model_prob         IS NOT NEW.model_prob
  OR OLD.model_side         IS NOT NEW.model_side
  OR OLD.predictor          IS NOT NEW.predictor
  OR OLD.factor_set_version IS NOT NEW.factor_set_version
  OR OLD.factors_json       IS NOT NEW.factors_json
  OR OLD.reasoning          IS NOT NEW.reasoning
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a prediction cannot be edited after creation; '
        || 'resolution writes an outcome, it never rewrites a probability');
END;

-- Resolution happens exactly once and never runs backwards.
CREATE TRIGGER IF NOT EXISTS predictions_resolve_once
BEFORE UPDATE OF resolved_utc, outcome ON predictions
FOR EACH ROW
WHEN OLD.resolved_utc IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: prediction already resolved; resolution is idempotent '
        || 'and never re-scores');
END;


-- ---------------------------------------------------------------------------
-- LAW 1 — the prediction row exists before its market snapshot.
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS snapshot_requires_prediction
BEFORE INSERT ON market_snapshots
FOR EACH ROW
WHEN (SELECT COUNT(*) FROM predictions WHERE id = NEW.prediction_id) = 0
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 1: a market snapshot cannot exist before its prediction row');
END;

CREATE TRIGGER IF NOT EXISTS snapshot_not_before_prediction
BEFORE INSERT ON market_snapshots
FOR EACH ROW
WHEN NEW.fetched_utc < (SELECT created_utc FROM predictions WHERE id = NEW.prediction_id)
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 1: market snapshot is timestamped before the prediction '
        || 'it is attached to; the line was fetched too early');
END;


-- ---------------------------------------------------------------------------
-- LAW 2 — a factor is never deleted, only deactivated.
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS factors_no_delete
BEFORE DELETE ON factors
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 2: a factor may be deactivated but never deleted; '
        || 'its history stays');
END;
