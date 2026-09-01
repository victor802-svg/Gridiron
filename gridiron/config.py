"""Configuration. Everything tunable lives here or in an environment variable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent

#: True inside a PyInstaller bundle, where PACKAGE_ROOT is a read-only
#: extraction directory that is replaced wholesale on every rebuild.
FROZEN = bool(getattr(sys, "frozen", False))

#: Where mutable state lives. Kept outside the bundle when frozen, because a
#: track record that a rebuild deletes is not a track record.
#: The installation this process belongs to. A frozen build's PACKAGE_ROOT is
#: inside the bundle, so REPO_ROOT points at the extraction directory and both
#: the record and the token would be looked for THERE. The desktop launcher sets
#: GRIDIRON_HOME to the directory it was started from, which the shortcut sets
#: to the repository, so a frozen window reads the same record the scheduler
#: keeps.
#:
#: This was found by building the exe and watching it answer 503: it looked for
#: .env inside its own bundle, found none, and refused to serve. The subtler
#: half was worse and would not have announced itself — STATE_DIR fell back to
#: ~/.gridiron, a DIFFERENT database, so the window would have opened onto an
#: empty record while the scheduled tasks went on filling the real one.
HOME = Path(os.environ.get("GRIDIRON_HOME") or REPO_ROOT)

STATE_DIR = Path(
    os.environ.get("GRIDIRON_STATE")
    or (HOME / "var" if os.environ.get("GRIDIRON_HOME") else
        (Path.home() / ".gridiron" if FROZEN else REPO_ROOT / "var"))
)

# --- storage ---------------------------------------------------------------
DEFAULT_DB = STATE_DIR / "gridiron.db"
DB_PATH = Path(os.environ.get("GRIDIRON_DB", DEFAULT_DB))

# --- server ----------------------------------------------------------------
# 127.0.0.1 only. Not configurable to a public interface on purpose.
HOST = "127.0.0.1"
PORT = int(os.environ.get("GRIDIRON_PORT", "8848"))

# --- the sports ------------------------------------------------------------
# Order is display order in the interface. NFL first because it is the sport
# the project was built for; MLB second because it is the one resolving daily.
SPORTS: tuple[str, ...] = ("nfl", "mlb", "nba", "cfb")

#: "NCAAF" rather than "CFB" because it is what the tab says everywhere
#: else in the sport and what a reader will recognise beside NFL.
SPORT_LABELS = {"nfl": "NFL", "mlb": "MLB", "nba": "NBA", "cfb": "NCAAF"}


class CrossSportAggregation(RuntimeError):
    """LAW 6: a figure was about to mix two sports into one number."""


def require_sport(sport: str | None, where: str) -> str:
    """The LAW 6 tripwire.

    `sport` is a required argument on every function that reads the record. It
    is validated here rather than defaulted, so the only way to write a query
    spanning two sports is to delete the parameter -- and then this fires by
    name instead of quietly returning a number that describes neither sport.

    IT LIVES HERE, next to `SPORTS`, and not in `calibration` where it was
    written. Calibration names market columns, so LAW 1's closure scan rejects
    any prediction-path module that imports it -- and a module on that path
    needing LAW 6's check is not an odd case, it is the normal one. The rung
    log hit it immediately. A law's own tripwire must not be reachable only by
    modules that are allowed to see the market.

    `calibration` re-exports both names, so every existing caller is unchanged.
    """
    if sport is None or sport == "" or sport == "all":
        raise CrossSportAggregation(
            f"LAW 6: {where} was asked for sport={sport!r}. Every curve, score, "
            "edge figure and sample size belongs to exactly one sport. A number "
            "mixing NFL spreads with MLB moneylines describes neither, and it "
            "flatters reliably because the easy sport dilutes the hard one."
        )
    if sport not in SPORTS:
        raise CrossSportAggregation(
            f"LAW 6: {where} was asked for unknown sport {sport!r}; "
            f"declared sports are {list(SPORTS)}."
        )
    return sport

#: What a sport calls one slate. NFL and NBA number weeks; a baseball slate is
#: a day's card, so MLB's slate ordinal is a day.
#: CFB's slate is a DAY, not a week, and the probe is why: `week` is null
#: on every 2026 event, so slates are derived from dates. Saturday carries
#: 60 games, Friday 8, Sunday 16 -- three different slates a week-shaped
#: ordinal would merge.
SPORT_SLATE_WORD = {"nfl": "week", "mlb": "day", "nba": "week",
                    "cfb": "day"}

#: The markets each sport asks about. MLB is moneyline only: there is no run
#: line question worth asking that the moneyline does not already ask better.
SPORT_MARKETS: dict[str, tuple[str, ...]] = {
    "nfl": ("spread", "passing_yards", "receiving_yards", "rushing_yards",
            "receptions", "passing_tds"),
    "mlb": ("moneyline", "batter_hits", "batter_total_bases",
            "batter_home_runs", "pitcher_strikeouts"),
    "nba": ("spread", "points", "rebounds", "assists", "threes"),
    # THREE TEAM MARKETS AND NO PROPS. The probe found zero prop rows on
    # completed and upcoming games alike, and a CFB event carries exactly one
    # odds provider whose propBets endpoint 404s -- there is no second one to
    # fall back to. Player game stats exist and would resolve props; the gap is
    # the lines. See docs/CFB_FEASIBILITY.md section 6.
    #
    # `total` is a NEW QUESTION SHAPE for this project: over/under on the two
    # teams' combined score, which is not a margin and shares no calibration
    # family with one.
    "cfb": ("spread", "moneyline", "total"),
}

#: Which of a sport's markets are player props (the rest are game markets).
SPORT_PROP_MARKETS: dict[str, tuple[str, ...]] = {
    "nfl": ("passing_yards", "receiving_yards", "rushing_yards",
            "receptions", "passing_tds"),
    "mlb": ("batter_hits", "batter_total_bases", "batter_home_runs",
            "pitcher_strikeouts"),
    "nba": ("points", "rebounds", "assists", "threes"),
    "cfb": (),          # measured, not assumed: no prop lines exist
}

#: MLB's four, in descending order of liquidity -- which is also descending
#: order of how many of them a slate offers. Measured on the 2026-08-30 card:
#: 216 hits quotes, 81 total bases, 108 home runs, 24 strikeouts. When the daily
#: cap bites it bites on strikeouts, which is the thinnest market and the one
#: with roughly one qualifying subject per game.
MLB_PROP_MARKETS: tuple[str, ...] = SPORT_PROP_MARKETS["mlb"]

#: Season the live slate is drawn from, per sport.
SPORT_CURRENT_SEASON = {
    "nfl": int(os.environ.get("GRIDIRON_SEASON", "2026")),
    "mlb": int(os.environ.get("GRIDIRON_MLB_SEASON", "2026")),
    # NBA seasons are named by their starting year: 2026 is 2026-27.
    "nba": int(os.environ.get("GRIDIRON_NBA_SEASON", "2026")),
    "cfb": int(os.environ.get("GRIDIRON_CFB_SEASON", "2026")),
}

#: Which of a sport's markets are TOTALS -- a question about the two teams'
#: combined score rather than about which of them wins or by how much.
#:
#: Its own family, and never pooled with margins. A totals question is right or
#: wrong for different reasons than a spread: weather, pace and both offences
#: move it, and the market prices it separately. LAW 4's reasoning about not
#: merging an easy market with a hard one applies exactly here.
SPORT_TOTAL_MARKETS: dict[str, tuple[str, ...]] = {
    "cfb": ("total",),
}


# (A helper that reads this table arrives in B6, with the guard that needs it.
#  Writing it now would ship a function nothing calls, which is what the orphan
#  scan exists to catch -- and did, within a minute of it being added.)

#: Seasons MLB player-level rows are fetched for: lineups and per-batter game
#: logs. Narrower than SPORT_LOAD_SEASONS because these are the expensive part
#: of the request budget -- one request per batter per season, roughly 700
#: batters a season -- and only the prop markets read them. The moneyline
#: market goes on using every season in SPORT_LOAD_SEASONS.
#:
#: Three seasons is the judgement: enough for a walk-forward fit that trains on
#: two and tests on one, and few enough that a full load is minutes rather than
#: an afternoon.
MLB_PLAYER_SEASONS: tuple[int, ...] = tuple(
    int(x) for x in os.environ.get(
        "GRIDIRON_MLB_PLAYER_SEASONS", "2024,2025,2026"
    ).split(",") if x.strip()
)

#: Seasons pulled by the loader, per sport.
SPORT_LOAD_SEASONS = {
    "nfl": tuple(range(2016, 2027)),
    "mlb": tuple(range(2021, 2027)),
    "nba": tuple(range(2021, 2027)),
    # FOUR SEASONS, and the cost is why. A CFB season is ~890 games and each
    # game's scores sit behind two further fetches, so a season is roughly
    # 2,700 requests before team stats. Four gives a walk-forward fit three
    # seasons to train on and one to test, which is the shape B4 needs, without
    # a first load measured in hours.
    "cfb": tuple(range(2023, 2027)),
}


# --- the factor set --------------------------------------------------------
# Bumped whenever a factor is added, removed or redefined FOR A MARKET THAT
# ALREADY HAS A RECORD. Calibration curves are kept separate per version
# (LAW 4: never merge incomparable samples).
#
# NOT BUMPED FOR MLB'S PROP MARKETS ON 2026-08-30, and the reasoning is written
# here because the convention as first stated says "whenever a factor is added"
# and this is a deliberate reading of it rather than an oversight.
#
# Thirteen factors were added. Every one of them applies ONLY to the four new
# MLB prop markets, which had no record at all: their curves start at N=0
# whatever this string says. No factor belonging to nfl:spread, to any NFL prop,
# to mlb:moneyline or to any NBA market changed by a character.
#
# Bumping would therefore have declared four existing records incomparable with
# their own futures WHEN NOTHING ABOUT THEM CHANGED -- a split that says "these
# two groups of NFL spread predictions were made under different assumptions"
# when they were made under identical ones. That is its own dishonesty, and it
# is permanent: a version split cannot be undone, while leaving the version
# alone can be reversed by bumping later.
#
# The general point, for whoever adds the next sport: this string is global and
# factor sets are per sport per market, so the granularities do not match. It
# tracks changes to an EXISTING market's instruments. Adding a market is not
# that.
#
# ENDORSED BY THE OPERATOR 2026-08-31, as the narrower reading: the version
# tracks changes to an EXISTING market's instruments, and adding a market is a
# new category with its own activation date rather than a change to this string.
#
# NOT BUMPED AGAIN ON 2026-08-31 for the redeclaration of `mlb_batter_rate`
# from a 15-game window to a 60-game one, by the same reading and one further
# fact: all four MLB prop markets stood at ZERO resolutions when it was made.
# There is no record for a split to divide. That window closes at the first
# resolution, which is why the repair was made then rather than later.
#
# THE MISMATCH THIS LEAVES IS RECORDED IN FOLLOWUPS.md: the string is global,
# factor sets are per sport per market, so a change to one NBA prop factor would
# bump the version for every MLB market too and split records nothing touched.
# Nothing has been lost to it yet because every bump so far has been
# project-wide. The fix is to make the version per market, and it is much
# cheaper before a single-sport bump is ever needed than after.
FACTOR_SET_VERSION = "fs2"

#: Every factor set that has ever produced predictions, oldest first. A version
#: is CLOSED, never erased: its record stands as recorded and is reported beside
#: the current one rather than merged into it.
FACTOR_SET_HISTORY = ("fs1", "fs2")

#: When each version began. A version's record starts at N=0 on this date and
#: nothing earlier is backfitted onto it (LAW 2).
FACTOR_SET_ACTIVATED = {
    "fs1": "2026-08-28T00:00:00Z",
    "fs2": "2026-08-29T00:00:00Z",
}

#: How far ahead a live slate may be forecast, in days.
#:
#: BLIND FIRST means before the event, but not arbitrarily long before it. A
#: forecast written two months out is made from the previous season's form, with
#: rotations that no longer exist and no injury report, and — because a question
#: once answered is never re-asked — it would PERMANENTLY occupy that slate's
#: slot, so the model never gets to forecast it with the information it will
#: actually have on the day.
#:
#: The number is a judgement and is recorded as one. What forced it was an NBA
#: run that wrote 47 predictions 52 days before tip. What bounds it from below is
#: a season opener, which is legitimately forecast about two weeks out because
#: that is when rosters settle: the NFL 2026 week 1 slate in this record was
#: written at 12 to 17 days, which was measured rather than assumed, and sits
#: inside 21. Three weeks contains one slate of any of the three sports plus a
#: realistic lead, and excludes the case that prompted the rule by more than
#: double.
MAX_FORECAST_LEAD_DAYS = int(os.environ.get("GRIDIRON_MAX_LEAD_DAYS", "21"))

# --- LAW 4 -----------------------------------------------------------------
# Nothing claims an edge below this many resolved predictions in a category.
MIN_SAMPLE_FOR_EDGE_CLAIM = 100
# A calibration bucket renders its point only with at least this many; below it
# the bucket still renders its N, but is drawn as provisional.
MIN_SAMPLE_FOR_BUCKET_POINT = 20
# "Disagreement" for the edge question: model prob vs market implied prob.
EDGE_DISAGREEMENT_THRESHOLD = 0.05

# --- LLM budget ledger (G3) ------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or ""
LLM_DAILY_USD_CAP = float(os.environ.get("GRIDIRON_LLM_DAILY_USD", "2.00"))
LLM_REASONING_MODEL = os.environ.get("GRIDIRON_LLM_REASONING_MODEL", "claude-sonnet-4-5")
LLM_CHEAP_MODEL = os.environ.get("GRIDIRON_LLM_CHEAP_MODEL", "claude-haiku-4-5-20251001")
LLM_MAX_OUTPUT_TOKENS = 700

# USD per million tokens, (input, output). Used for the ledger only; if a model
# is not listed the call is still made and priced with the fallback.
LLM_PRICES = {
    "claude-opus-4-5": (5.00, 25.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}
LLM_PRICE_FALLBACK = (3.00, 15.00)

# --- data ------------------------------------------------------------------
HTTP_TIMEOUT = 90
USER_AGENT = "gridiron/0.1 (personal forecasting project)"
# Seasons pulled by `python -m gridiron.cli load`. History is needed because
# resolution needs completed games and calibration needs volume.
DEFAULT_LOAD_SEASONS = tuple(range(2016, 2027))
CURRENT_SEASON = int(os.environ.get("GRIDIRON_SEASON", "2026"))

# --- props -----------------------------------------------------------------
# Five markets, in descending order of real-world liquidity. The order is used
# to fill the weekly slate: when the cap bites, it bites on the thinnest market
# first. Each type is its own scoring category and its own 100-resolution gate;
# they are never merged into a single "props" number.
PROP_MARKETS = (
    "passing_yards",
    "receiving_yards",
    "rushing_yards",
    "receptions",
    "passing_tds",
)

# --- MLB props: the declared ladder (ruling R1) ------------------------------
#
# DECLARED 2026-08-30. The rungs are fixed in advance, in this file, and the one
# a question is asked at is the rung NEAREST THE MODEL'S OWN ROLLING MEAN.
#
# This replaces the NFL offset mechanism FOR MLB ONLY. NFL's stands exactly as
# recorded: its props were asked at the player's own average shifted by a
# declared offset, and every NFL prop snapshot says
# `unavailable:no-free-prop-line-source` because nothing published a line to
# compare them against.
#
# WHY A LADDER RATHER THAN AN OFFSET, and why it is still blind:
#
#   * It is blind by construction. Only our own stats choose the rung. The set
#     is declared here, before any slate; nothing is fetched inside the blind
#     window; and the rung a question lands on cannot be moved by what a book
#     is offering, because nothing in the prediction path can see what a book is
#     offering.
#   * It makes the market comparison possible for the first time on a prop.
#     ESPN does publish MLB prop lines -- measured 2026-08-30, 1,084 athlete
#     rows across one 14-game slate -- and they sit on a handful of values:
#     hits 0.5 (96%) and 1.5 (4%), total bases 1.5 (100%), home runs "1+"
#     (100%, i.e. over 0.5), strikeouts 3.5 to 6.5. Asking at a self-generated
#     1.2 hits would produce a question no book answers, so the comparison would
#     stay absent even though lines now exist. Asking where the market answers
#     is what buys the comparison, and it costs nothing that LAW 1 protects.
#
# The rungs below ARE that measured distribution, which is a statement about
# where baseball's prop questions actually live rather than about any one book.
MLB_PROP_LADDER: dict[str, tuple[float, ...]] = {
    "batter_hits": (0.5, 1.5),
    "batter_total_bases": (1.5,),
    # ESPN quotes this as the milestone "1+", which is the same question as
    # over 0.5, and we ask it in the over/under form the rest of the record
    # uses.
    "batter_home_runs": (0.5,),
    "pitcher_strikeouts": (3.5, 4.5, 5.5, 6.5),
}
MLB_PROP_LADDER_DECLARED = "2026-08-30T00:00:00Z"

# --- props: the confidence floor (ruling R4) ---------------------------------
#
# DECLARED 2026-08-30, and it applies to EVERY prop market in EVERY sport from
# that date. Existing prop records stand exactly as written (LAW 3); this
# changes which questions get asked from here on, never any answer already
# given.
#
# A player-prop prediction is written only when the model's claimed confidence
# in the side it states is at least this. Because `stated_side` always reports
# confidence in the side claimed, this reads the same on both halves of a
# market: a 28% chance of a home run is a 72% claim that there will not be one,
# and it qualifies.
#
# It is applied at prediction time from the model's own numbers, so it is
# blind-compatible by construction -- there is nothing to consult but the
# probability the model just produced.
#
# TWO CONSEQUENCES, STATED IN ADVANCE so the record can be read honestly:
#   * a slate may run well under its cap, and that is the floor working;
#   * prop resolutions will concentrate in the 70-80% and 80%+ buckets, which
#     fills the STRONG tier's earned-accuracy line faster than any other part of
#     the record. That is the experiment: boldest claims first, and the record
#     says quickly whether bold means good.
PROPS_MIN_CLAIM = float(os.environ.get("GRIDIRON_PROPS_MIN_CLAIM", "0.70"))
PROPS_MIN_CLAIM_DECLARED = "2026-08-30T00:00:00Z"

#: A reviewable daily card. Baseball's slate is a day, not a week, so this is
#: the daily equivalent of PROPS_PER_WEEK and is deliberately smaller than the
#: number of questions the data could support.
MLB_PROPS_PER_DAY = int(os.environ.get("GRIDIRON_MLB_PROPS_PER_DAY", "25"))

#: Rounding step for each market's line, in the stat's own units.
PROP_LINE_STEP = {
    "passing_yards": 5.0,
    "receiving_yards": 5.0,
    "rushing_yards": 5.0,
    "receptions": 1.0,
    "passing_tds": 1.0,
    # Basketball's four are all counting stats, so all step by one and all sit
    # on a half. Market names do not collide across sports, so one table serves
    # every sport rather than three tables that could drift apart.
    "points": 1.0,
    "rebounds": 1.0,
    "assists": 1.0,
    "threes": 1.0,
    # Baseball's four are counting stats too. They are never rounded by this
    # table in practice -- MLB_PROP_LADDER fixes the rungs outright -- but the
    # entry exists so a market cannot be added to one table and forgotten in
    # the other.
    "batter_hits": 1.0,
    "batter_total_bases": 1.0,
    "batter_home_runs": 1.0,
    "pitcher_strikeouts": 1.0,
}

#: Counting stats sit at 0.5, 1.5, 2.5 ... and never below half, in every sport.
COUNTING_STATS = frozenset(
    {"receptions", "passing_tds", "points", "rebounds", "assists", "threes",
     "batter_hits", "batter_total_bases", "batter_home_runs",
     "pitcher_strikeouts"}
)

#: A reviewable slate beats a large one. Quality of resolution beats quantity of
#: predictions: 40 props a week is what one person can actually read, and a
#: forecast nobody reads is not a forecast anybody can check.
PROPS_PER_WEEK = int(os.environ.get("GRIDIRON_PROPS_PER_WEEK", "40"))
#: Ceiling per game, so one marquee fixture cannot eat the whole slate.
PROPS_PER_GAME = int(os.environ.get("GRIDIRON_PROPS_PER_GAME", "3"))
