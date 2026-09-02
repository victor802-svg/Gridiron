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
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba','cfb')),
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    game_type     TEXT    NOT NULL,          -- REG | WC | DIV | CON | SB
    kickoff_utc   TEXT,                      -- ISO-8601 Z; NULL if TBD
    -- The LEAGUE's own calendar date, which is NOT the UTC date. A game tipping
    -- at 02:00 UTC is the previous evening where it is played, and every game
    -- log is keyed on that local date. Every rolling-window cutoff uses this
    -- column: cutting on the UTC date instead let the game being predicted into
    -- its own window, for 76.8% of NBA games and 25.1% of MLB ones.
    league_date   TEXT,
    home          TEXT    NOT NULL,
    away          TEXT    NOT NULL,
    -- scheduled | in | final. 'in' arrived with the live poll (L1): a game
    -- that has started and not finished is a state this table could not
    -- previously express, so the countdown could only ever say "upcoming" or
    -- "complete" and a running game looked unstarted.
    status        TEXT    NOT NULL
                  CHECK (status IN ('scheduled', 'in', 'final')),
    home_score    INTEGER,
    away_score    INTEGER,
    -- --- what the live poll writes, and nothing else -----------------------
    -- Prefixed `live_` so the LAW 1 closure scan can name them precisely. A
    -- column called `period` or `clock` would collide with ordinary words in
    -- the prediction path and the scan would have to guess; these cannot be
    -- read from a forecasting module by accident or on purpose.
    --
    -- They describe a game IN FLIGHT. Nothing here settles anything: only the
    -- resolve task writes an outcome (LAW 3), and a game marked final by the
    -- poller leaves its predictions open until it runs.
    live_period      TEXT,                   -- "3rd", "Top 6th", "OT"
    live_clock       TEXT,                   -- "8:41"; absent for baseball
    live_updated_utc TEXT,                   -- when the poll last saw it

    -- A GAME THAT HAS STARTED HAS A SCORE, including 0-0. The old form of this
    -- said scores exist if and only if the game is FINAL, which a live game
    -- breaks by existing. A table-level CHECK must follow every column, and
    -- the first draft of this sat above the three above -- SQLite reports that
    -- as a syntax error at the first column name, which is a confusing place
    -- to be sent when the fault is the line above it.
    CHECK ((status = 'scheduled') = (home_score IS NULL AND away_score IS NULL))
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
    strike_outs   INTEGER,
    home_runs_allowed INTEGER,
    PRIMARY KEY (pitcher_id, season, game_date, game_pk)
);
CREATE INDEX IF NOT EXISTS mlb_starts_lookup
    ON mlb_pitcher_starts (pitcher_id, game_date);
-- The strikeout market resolves and trains by GAME, not by pitcher, and without
-- this every lookup was a scan of the whole table. It cost the pitcher fit
-- roughly an order of magnitude in time before anyone noticed, because a slow
-- fit looks exactly like a big one.
CREATE INDEX IF NOT EXISTS mlb_starts_by_game
    ON mlb_pitcher_starts (game_pk);

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


-- One row per batter per game. The four batting prop markets resolve from this
-- table and every batter factor reads it.
--
-- Sourced from the per-player GAME LOG (`/people/{id}/stats?stats=gameLog`),
-- one request per player per season, NOT from per-game boxscores. A boxscore is
-- 178 KB and there are 2,430 games in a season, which is a third of a gigabyte
-- of cache per season for the same numbers -- the outage the loader's docstring
-- warns about. The game log carries every stat the markets need.
CREATE TABLE IF NOT EXISTS mlb_batter_games (
    player_id        INTEGER NOT NULL,
    season           INTEGER NOT NULL,
    game_date        TEXT    NOT NULL,
    game_pk          INTEGER NOT NULL,
    player_name      TEXT,
    team             TEXT,
    opponent         TEXT,
    is_home          INTEGER,
    hits             INTEGER,
    total_bases      INTEGER,
    home_runs        INTEGER,
    doubles          INTEGER,
    triples          INTEGER,
    at_bats          INTEGER,
    plate_appearances INTEGER,
    strike_outs      INTEGER,
    walks            INTEGER,
    rbi              INTEGER,
    -- The batting-order slot, 1 to 9, decoded from the boxscore's `battingOrder`
    -- (slot = value // 100). NULL where no lineup was recorded for the game.
    -- IT IS NOT KNOWN BEFORE THE GAME: see `mlb_lineups`.
    lineup_slot      INTEGER,
    is_substitute    INTEGER,
    PRIMARY KEY (player_id, season, game_date, game_pk)
);
CREATE INDEX IF NOT EXISTS mlb_batter_games_lookup
    ON mlb_batter_games (player_id, game_date);
CREATE INDEX IF NOT EXISTS mlb_batter_games_by_game
    ON mlb_batter_games (game_pk);

-- The posted batting order for a game, one row per slot per side.
--
-- MEASURED, NOT ASSUMED: the schedule's `hydrate=lineups` returns
-- `homePlayers`/`awayPlayers` as ORDERED arrays, and that order was checked
-- against the boxscore's own `battingOrder` field on 12 team-games -- 12 agree,
-- 0 disagree. One request per date range covers every game on it.
--
-- A LINEUP IS A FACT ABOUT A GAME THAT HAS STARTED. Measured 2026-08-30: of 41
-- scheduled games across three future dates, ZERO carried lineups; they are all
-- 'Preview' until roughly two hours before first pitch. So this table can never
-- tell a forecast who is batting where TONIGHT, and no factor may read it for
-- the game being predicted. What it supports is the batter's RECENT slot, which
-- is a fact about games already played and is available at prediction time.
CREATE TABLE IF NOT EXISTS mlb_lineups (
    game_id     TEXT    NOT NULL REFERENCES games (id),
    side        TEXT    NOT NULL CHECK (side IN ('home', 'away')),
    slot        INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 9),
    player_id   INTEGER NOT NULL,
    player_name TEXT,
    recorded_utc TEXT   NOT NULL,
    PRIMARY KEY (game_id, side, slot)
);
CREATE INDEX IF NOT EXISTS mlb_lineups_player ON mlb_lineups (player_id);

-- Handedness, which is the input to the platoon-split factor.
--
-- Fetched in BATCHES: `/people?personIds=a,b,c,...` takes 300 ids in one
-- request, so every player in the record costs about five requests rather than
-- fifteen hundred. Handedness does not change, so a row is written once.
CREATE TABLE IF NOT EXISTS mlb_people (
    player_id   INTEGER PRIMARY KEY,
    full_name   TEXT,
    bat_side    TEXT,     -- 'R' | 'L' | 'S' (switch)
    pitch_hand  TEXT,     -- 'R' | 'L'
    primary_position TEXT,
    fetched_utc TEXT NOT NULL
);

-- THE MEASURED PLAYER CROSSWALK (new-market checklist, item 3).
--
-- The stats source and the odds source share no player id: Paul Goldschmidt is
-- 502671 to MLB and 31027 to ESPN, and neither payload carries the other's
-- number. The only bridge is the name, so the bridge is MEASURED and STORED
-- rather than computed on the fly and trusted.
--
-- `method` records HOW a row was matched, so the normaliser's contribution is
-- quantified rather than guessed: 'exact' means the raw names were identical,
-- 'normalised' means it took accent-stripping and punctuation folding. An
-- ambiguous name -- two players normalising to the same string -- is REFUSED,
-- and the refusal is stored with its reason so the prop is skipped visibly.
CREATE TABLE IF NOT EXISTS player_crosswalk (
    sport       TEXT    NOT NULL,
    espn_id     TEXT    NOT NULL,
    source_id   INTEGER,
    espn_name   TEXT    NOT NULL,
    source_name TEXT,
    normalised  TEXT    NOT NULL,
    method      TEXT    NOT NULL CHECK (
                    method IN ('exact', 'normalised', 'refused_ambiguous',
                               'refused_unmatched')),
    reason      TEXT,
    measured_utc TEXT   NOT NULL,
    PRIMARY KEY (sport, espn_id)
);
CREATE INDEX IF NOT EXISTS player_crosswalk_source
    ON player_crosswalk (sport, source_id);

-- Club display names, READ FROM THE FEED. See gridiron/data/teams.py.
--
-- Dated and sourced for the same reason player_crosswalk is: a name typed from
-- memory is the failure mode this project has paid for twice, and a table that
-- records WHERE each row came from and WHEN can be re-checked. A tricode with
-- no row here keeps rendering as a tricode, which is honest.
CREATE TABLE IF NOT EXISTS teams (
    sport        TEXT NOT NULL,
    tricode      TEXT NOT NULL,     -- OUR code, after the measured alias map
    espn_abbrev  TEXT,              -- what the feed called it, kept for audit
    display_name TEXT NOT NULL,
    short_name   TEXT,
    location     TEXT,              -- the CITY form: "St. Louis", "Chicago"
    source_url   TEXT NOT NULL,
    fetched_utc  TEXT NOT NULL,
    -- WHERE THIS TEAM PLAYS. ESPN's college venue documents carry no
    -- coordinates, so the city and state come from the feed and the
    -- lat/lon from Open-Meteo's geocoder WITH A STATE FILTER -- 23 of
    -- 136 FBS venues resolve to the wrong state without one. A venue
    -- that cannot be placed keeps NULLs and its factors go absent.
    -- 1 for a team the FBS group listed, 0 for a lower-division school
    -- seen only as an opponent. Both get rows; only one is FBS.
    is_fbs             INTEGER,
    venue_name         TEXT,
    venue_city         TEXT,
    venue_state        TEXT,
    venue_indoor       INTEGER,
    venue_lat          REAL,
    venue_lon          REAL,
    venue_geocoded_utc TEXT,
    PRIMARY KEY (sport, tricode)
);

-- Prop lines as published, one row per game per market per athlete per rung.
-- Lives outside `market_lines_raw` because that table is one row per GAME.
CREATE TABLE IF NOT EXISTS market_prop_lines_raw (
    game_id     TEXT    NOT NULL REFERENCES games (id),
    market      TEXT    NOT NULL,
    espn_id     TEXT    NOT NULL,
    line        REAL    NOT NULL,
    -- 'over' / 'under', DERIVED from cross-rung monotonicity, never assumed
    -- from the sign of the price. See `market/props.py`.
    side        TEXT    NOT NULL CHECK (side IN ('over', 'under', 'unknown')),
    price       INTEGER,
    implied_prob REAL,
    side_method TEXT,
    source      TEXT    NOT NULL,
    fetched_utc TEXT    NOT NULL,
    PRIMARY KEY (game_id, market, espn_id, line, side)
);


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


-- --- the appliance ----------------------------------------------------------
-- One row per attempt at a scheduled task. APPEND-ONLY, like every other
-- history here: a run that failed is a fact about the record, and a panel that
-- quietly forgets its failures is worse than no panel.
--
-- `result` is deliberately coarse and honest:
--   ok      the task ran and did what it was for
--   noop    it ran and there was correctly nothing to do
--   missed  the slate's games had already started, so it was NOT predicted
--   failed  it raised
CREATE TABLE IF NOT EXISTS task_runs (
    id            INTEGER PRIMARY KEY,
    task          TEXT    NOT NULL,
    started_utc   TEXT    NOT NULL,
    finished_utc  TEXT,
    result        TEXT    NOT NULL
                  CHECK (result IN ('ok', 'noop', 'missed', 'failed')),
    detail        TEXT,
    payload_json  TEXT
);
CREATE INDEX IF NOT EXISTS task_runs_lookup ON task_runs (task, started_utc DESC);

CREATE TRIGGER IF NOT EXISTS task_runs_no_delete
BEFORE DELETE ON task_runs
BEGIN
    SELECT RAISE(ABORT, 'task_runs is append-only: a run that failed is a fact');
END;


-- --- access ----------------------------------------------------------------
-- A browser session. The cookie carries only this id; the token itself is never
-- sent to the browser, never written to a log, and never appears in a URL.
CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    created_utc  TEXT NOT NULL,
    expires_utc  TEXT NOT NULL,
    user_agent   TEXT,
    -- Kept for the migration; the live marker is per SPORT in `session_seen`.
    last_seen_utc TEXT
);

-- When this device last read the digest FOR ONE SPORT.
--
-- Per sport, not per session, and the reason is a bug this replaced: with one
-- marker per device, opening the app on NFL advanced it, and switching to MLB
-- then reported "nothing resolved since you last looked" over six results that
-- had just landed. "Since you last looked" is a question about a record, and
-- every record here belongs to exactly one sport (LAW 6).
CREATE TABLE IF NOT EXISTS session_seen (
    session_id    TEXT NOT NULL,
    sport         TEXT NOT NULL CHECK (sport IN ('nfl','mlb','nba','cfb')),
    last_seen_utc TEXT NOT NULL,
    PRIMARY KEY (session_id, sport)
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions (expires_utc);

-- One row per FAILED sign-in. Kept rather than counted in memory: the backoff
-- must survive a restart, or a restart is the way around it. It is also the
-- only security-relevant log this project keeps, and a failure nobody records
-- is a failure nobody can notice.
CREATE TABLE IF NOT EXISTS auth_failures (
    id        INTEGER PRIMARY KEY,
    at_utc    TEXT NOT NULL,
    ip        TEXT NOT NULL,
    reason    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_failures_ip ON auth_failures (ip, at_utc DESC);

-- A single-use handoff nonce, so the desktop launcher can open an authenticated
-- browser without ever putting the TOKEN in a URL. Sixty seconds, one use.
CREATE TABLE IF NOT EXISTS handoff_nonces (
    nonce       TEXT PRIMARY KEY,
    created_utc TEXT NOT NULL,
    expires_utc TEXT NOT NULL,
    used_utc    TEXT
);


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
    public_pct    REAL,      -- NULL when no free source is available; never a proxy
    -- WHICH LOOK THIS WAS. 'open_at_predict' is the first and only snapshot
    -- taken when the prediction was written, and its meaning is unchanged by
    -- this column existing: it is still what the market said at that moment.
    -- 'near_start' is a second look taken close to kickoff, for the drift
    -- question alone.
    --
    -- BOTH ARE TAKEN AFTER THE PREDICTION ROW EXISTS. The blind structure is
    -- untouched: LAW 1's triggers still reject a snapshot with no prediction
    -- or one timestamped before it, and they apply to this kind exactly as to
    -- the first.
    kind          TEXT    NOT NULL DEFAULT 'open_at_predict'
                  CHECK (kind IN ('open_at_predict', 'near_start'))
);

-- One of each kind per prediction. A second 'open_at_predict' would overwrite
-- the meaning of the first -- the market as it was when the forecast was made
-- -- and a second 'near_start' would make "the drift" ambiguous.
CREATE UNIQUE INDEX IF NOT EXISTS market_snapshots_one_per_kind
    ON market_snapshots (prediction_id, kind);
CREATE INDEX IF NOT EXISTS snap_pred ON market_snapshots (prediction_id);


-- ---------------------------------------------------------------------------
-- Predictions and their scoring.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc   TEXT    NOT NULL,
    sport         TEXT    NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba','cfb')),
    game_id       TEXT    NOT NULL REFERENCES games (id),
    -- 'moneyline' is MLB's only market; NBA and NFL use spread + prop.
    -- 'total' is college football's third question shape: the two teams'
    -- COMBINED score, which is neither a margin nor a player prop and
    -- gets its own calibration family.
    market_type   TEXT    NOT NULL
                  CHECK (market_type IN ('spread', 'prop', 'moneyline', 'total')),
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
    -- THE NUMBER ACTUALLY SHOWN, when a correction was in force at write time.
    -- NULL means the category was raw and `model_prob` was displayed as-is.
    --
    -- Stored BESIDE the raw claim and never instead of it. A record that kept
    -- only the corrected figure could not answer "was the correction right",
    -- which is the entire reason for versioning it: the predictions written
    -- under a version are its forward record.
    calibrated_prob    REAL,
    correction_version INTEGER,
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
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba','cfb')),
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
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba','cfb')),
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
    sport              TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb','nba','cfb')),
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
-- CALIBRATION CORRECTIONS — the model'''s claims, adjusted by its own record.
-- ---------------------------------------------------------------------------
--
-- A forecaster that says 70% and is right 62% of the time is not broken; it is
-- MISCALIBRATED, and that is a measurable, correctable fact. Platt scaling
-- fits two numbers per category -- a slope and an intercept on the claim'''s
-- log-odds -- so a claim can be mapped onto what claims like it have actually
-- been worth.
--
-- ONE CORRECTION PER CATEGORY, and a category is (sport, market_type,
-- forecaster). LAW 6 applies INSIDE the correction exactly as it does outside
-- it: a slope fitted across two sports describes neither, and one fitted
-- across two forecasters would let the better one flatter the worse. The
-- statistical and LLM forecasters each earn their own.
--
-- APPEND-ONLY, AND VERSIONED. A refit never edits a correction; it writes a
-- new version. Corrections apply at WRITE TIME to new predictions only --
-- nothing already written ever changes, because a prediction is what was
-- claimed at the time (LAW 3). That also means every version can be GRADED:
-- the predictions written under it carry its number and have their own curve.
--
-- `train_brier_raw` and `train_brier_corrected` are IN-SAMPLE and are labelled
-- so everywhere they are shown. They say the fit did something; they are not
-- evidence it helps, and the column names are not allowed to imply otherwise.
CREATE TABLE IF NOT EXISTS calibration_corrections (
    id            INTEGER PRIMARY KEY,
    sport         TEXT NOT NULL,
    market_type   TEXT NOT NULL,
    forecaster    TEXT NOT NULL,
    version       INTEGER NOT NULL,
    fitted_utc    TEXT NOT NULL,
    n_train       INTEGER NOT NULL CHECK (n_train >= 0),
    -- Platt'''s two: corrected = sigmoid(slope * logit(claim) + intercept).
    slope         REAL NOT NULL,
    intercept     REAL NOT NULL,
    train_brier_raw       REAL,
    train_brier_corrected REAL,
    -- The holdout check (C2). NULL until a category has enough to run it.
    holdout_n            INTEGER,
    holdout_brier_raw    REAL,
    holdout_brier_corrected REAL,
    -- NULL means fitted but NOT ACTIVE. A correction is inert until this is
    -- set, so a fit can be recorded and inspected without touching a claim.
    active_from   TEXT,
    -- Why it is or is not active, in words, for the interface.
    status        TEXT NOT NULL,
    UNIQUE (sport, market_type, forecaster, version)
);

CREATE INDEX IF NOT EXISTS calibration_corrections_category
    ON calibration_corrections (sport, market_type, forecaster, version DESC);

CREATE TRIGGER IF NOT EXISTS calibration_corrections_no_update
BEFORE UPDATE ON calibration_corrections
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a fitted correction is what it was at the time; '
        || 'refitting writes a new version and never edits one');
END;

CREATE TRIGGER IF NOT EXISTS calibration_corrections_no_delete
BEFORE DELETE ON calibration_corrections
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: corrections are append-only; a version that was '
        || 'once active graded the predictions written under it');
END;


-- ---------------------------------------------------------------------------
-- THE RUNG LOG — a measurement, and deliberately NOT a record of predictions.
-- ---------------------------------------------------------------------------
--
-- Ruling, 2026-08-31: "The ladder question gets MEASURED before it gets
-- retuned. Add to the props slate log the model'''s claim at every OFFERED rung,
-- written or not. After two weeks: if below-floor claims cluster at 60-69 near
-- the mean rung, that is the floor working as designed, not a mis-set ladder."
--
-- Six MLB prop questions in one night were below the 70% floor and not asked.
-- That is either the floor doing its job or a ladder set at the wrong heights,
-- and the two look identical from a count. What separates them is the
-- DISTRIBUTION of the claims that failed -- which needs the claims recorded,
-- including the ones that never became predictions.
--
-- THIS TABLE IS NOT A PREDICTION LOG AND MUST NEVER BE READ AS ONE. A row here
-- is what the model would have said at a rung it was not asked about; it has no
-- outcome, is never resolved, and never enters a curve, a Brier score or an N.
-- Treating these as forecasts would be backfitting with extra steps: the model
-- gets to be judged on the questions it liked, which is the one thing the whole
-- record exists to prevent. `asked` marks the single rung per subject that
-- became a real question, and even that row is a copy for analysis, never the
-- prediction itself.
CREATE TABLE IF NOT EXISTS prop_rung_claims (
    id            INTEGER PRIMARY KEY,
    sport         TEXT NOT NULL,
    season        INTEGER NOT NULL,
    week          INTEGER,
    game_id       TEXT NOT NULL,
    subject       TEXT NOT NULL,
    market        TEXT NOT NULL,
    rung          REAL NOT NULL,
    -- The rung this subject'''s own rolling mean chose, so "near the mean rung"
    -- is answerable without recomputing it later against a changed ladder.
    chosen_rung   REAL,
    rolling_mean  REAL,
    prob_yes      REAL NOT NULL CHECK (prob_yes >= 0.0 AND prob_yes <= 1.0),
    -- Confidence in the side actually stated, which is what the floor tests.
    claimed       REAL NOT NULL CHECK (claimed >= 0.5 AND claimed <= 1.0),
    side          TEXT NOT NULL,
    asked         INTEGER NOT NULL DEFAULT 0,
    written       INTEGER NOT NULL DEFAULT 0,
    floor_applied REAL NOT NULL,
    factor_set_version TEXT NOT NULL,
    created_utc   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS prop_rung_claims_sport_day
    ON prop_rung_claims (sport, created_utc);
CREATE UNIQUE INDEX IF NOT EXISTS prop_rung_claims_once
    ON prop_rung_claims (sport, season, game_id, subject, market, rung, created_utc);

-- Append-only like everything else that records what the model said.
CREATE TRIGGER IF NOT EXISTS prop_rung_claims_no_update
BEFORE UPDATE ON prop_rung_claims
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a recorded claim is what the model said at the time '
        || 'and cannot be rewritten');
END;


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
  OR OLD.calibrated_prob    IS NOT NEW.calibrated_prob
  OR OLD.correction_version IS NOT NEW.correction_version
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

-- WHAT THE LIVE POLL ASKED FOR, every time it ran (L1). Rate honesty: a
-- poller that cannot say how many requests it made is a poller nobody can
-- hold to a rate, and "it only runs during games" is a claim about code until
-- there is a row per run to count. Append-only in practice; nothing reads it
-- but the schedule panel.
CREATE TABLE IF NOT EXISTS live_polls (
    id            INTEGER PRIMARY KEY,
    polled_utc    TEXT    NOT NULL,
    sport         TEXT    NOT NULL,
    requests      INTEGER NOT NULL,
    games_seen    INTEGER NOT NULL,
    games_changed INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS live_polls_when ON live_polls (polled_utc DESC);

-- ---------------------------------------------------------------------------
-- THE OPERATOR'S OWN CALLS (GRIDIRON_12)
-- ---------------------------------------------------------------------------
--
-- A THIRD FORECASTER, and never merged with the other two. The operator sees
-- the model's probability and the market's line before calling, so these are
-- INFORMED forecasts and are labelled that way everywhere they appear. Mixing
-- them into the blind record would destroy the only thing that makes the
-- blind record worth keeping (LAW 1), and pooling them with the model's would
-- be the merge LAW 6 already forbids across sports, applied across
-- forecasters -- which is how `statistical` and `llm` are already kept apart.
--
-- A CALL IS A CONFIDENCE, NOT A STAKE (LAW 5). There is no unit column, no
-- amount, no bankroll, and there never will be: `audit.check_not_a_betting_
-- tool` scans identifiers, and a planting adds one to prove the scan fires.
CREATE TABLE IF NOT EXISTS operator_calls (
    id            INTEGER PRIMARY KEY,
    created_utc   TEXT    NOT NULL,
    prediction_id INTEGER NOT NULL REFERENCES predictions (id),
    side          TEXT    NOT NULL,
    tier          TEXT    NOT NULL CHECK (tier IN ('LEAN', 'SOLID', 'STRONG')),
    -- THE CLAIM IS STORED, NOT LOOKED UP LATER. The tier-to-probability map is
    -- a dated constant; storing what it said at the time means changing the
    -- map later cannot rewrite what the operator was recorded as claiming.
    -- The same reason `predictions` stores `factor_set_version`.
    claimed_prob  REAL    NOT NULL CHECK (claimed_prob > 0 AND claimed_prob < 1),
    resolved_utc  TEXT,
    outcome       INTEGER CHECK (outcome IN (0, 1)),
    CHECK ((resolved_utc IS NULL) = (outcome IS NULL))
);
CREATE INDEX IF NOT EXISTS operator_calls_pred
    ON operator_calls (prediction_id, created_utc DESC);
CREATE INDEX IF NOT EXISTS operator_calls_open
    ON operator_calls (resolved_utc);

-- APPEND-ONLY, on the same terms as `predictions`. A call is a claim with a
-- timestamp; editing one after the fact is the same act as editing a
-- forecast, and LAW 3 does not care which forecaster made it.
CREATE TRIGGER IF NOT EXISTS operator_calls_no_delete
BEFORE DELETE ON operator_calls
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a call is append-only and cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS operator_calls_no_update
BEFORE UPDATE ON operator_calls
FOR EACH ROW
WHEN OLD.created_utc   IS NOT NEW.created_utc
  OR OLD.prediction_id IS NOT NEW.prediction_id
  OR OLD.side          IS NOT NEW.side
  OR OLD.tier          IS NOT NEW.tier
  OR OLD.claimed_prob  IS NOT NEW.claimed_prob
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: a call cannot be edited. Revising a call writes a '
        || 'NEW row before kickoff; the old one stays and the chain is shown');
END;

CREATE TRIGGER IF NOT EXISTS operator_calls_resolve_once
BEFORE UPDATE OF resolved_utc, outcome ON operator_calls
FOR EACH ROW
WHEN OLD.resolved_utc IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
        'GRIDIRON LAW 3: call already resolved; resolution is idempotent');
END;
