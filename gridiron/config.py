"""Configuration. Everything tunable lives here or in an environment variable."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
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

#: The installation's settings file. It has always existed and has always held
#: the access token; until 2026-09-01 it was read ONLY for that one name, by a
#: parser inside `auth` that looked for `GRIDIRON_ACCESS_TOKEN` and ignored
#: every other line.
#:
#: That is a trap rather than a limitation. An `ANTHROPIC_API_KEY=` line added
#: here would have sat in the file looking entirely correct and been read by
#: nobody -- a worse failure than the one it was meant to fix, because it
#: looks fixed. So the file is now read whole.
ENV_FILE = HOME / ".env"


def read_env_file(path: Path) -> dict[str, str]:
    """Every `KEY=value` in a settings file. Missing or unreadable is empty.

    Deliberately small: no interpolation, no multi-line values, no `export`
    prefix. A settings file for one appliance does not need a language, and
    every feature here would be a way for the file to mean something other
    than what it appears to say.

    NEVER LOGGED. The values are secrets; this returns them and says nothing.
    """
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_FILE_SETTINGS = read_env_file(ENV_FILE)


def setting(name: str, default: str = "") -> str:
    """A setting from the process environment, then `.env`, then the default.

    THE PROCESS ENVIRONMENT WINS, and that order is the useful one: a variable
    set for one run -- a different key, a different database -- overrides the
    file without editing it, and the file is what persists. The reverse would
    make a stale file silently beat an explicit instruction.
    """
    return os.environ.get(name) or _FILE_SETTINGS.get(name, default)


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
SPORTS: tuple[str, ...] = ("nfl", "mlb", "nba", "cfb", "ufc")

#: "NCAAF" rather than "CFB" because it is what the tab says everywhere
#: else in the sport and what a reader will recognise beside NFL.
SPORT_LABELS = {"nfl": "NFL", "mlb": "MLB", "nba": "NBA", "cfb": "NCAAF",
                "ufc": "UFC"}


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
#: "card" for UFC, because that is what a night of fights is called and
#: nothing else in the sport's vocabulary would be recognised.
SPORT_SLATE_WORD = {"nfl": "week", "mlb": "day", "nba": "week", "ufc": "card",
                    "cfb": "day"}

#: HOW MLB SCORES ARE DISTRIBUTED, measured 2026-09-02 on every stored final.
#:
#: These are RAW distributions -- no line subtracted, no model expectation
#: removed -- and they are what a run-line or totals build starts from before
#: it has a fit of its own. They are NOT interchangeable with
#: `market.lines.MARGIN_SD_BY_SPORT`, which holds RESIDUALS for the market
#: comparison. Confusing the two is how the feasibility probe came to report a
#: discrepancy between 4.71 and 4.534 that does not exist.
#:
#: Dated and carrying their N, because the undated-SD guard refuses a
#: plausible-looking number that nobody measured.
MLB_SCORE_DISTRIBUTION = {
    "measured_utc": "2026-09-02T00:00:00Z",
    "n": 9373,
    "source": "every stored MLB final, seasons 2023-2026",
    # SD of (home runs + away runs). Stable across four seasons: 4.31 to 4.59.
    "total_sd": 4.511,
    "total_mean": 8.97,
    # SD of (home runs - away runs), and a mean of +0.021: home advantage in
    # MLB is essentially nothing, which is not true of the other three sports.
    "margin_sd": 4.534,
    "margin_mean": 0.021,
    # What the run line actually asks. 28% of games are decided by one run, so
    # the +/-1.5 question is "does this land outside the one-run band".
    "home_by_2_or_more": 0.358,
    "away_by_2_or_more": 0.362,
    "one_run_games": 0.280,
}

#: MEASUREMENTS THAT MUST NOT BE READ EARLY, with the date they open.
#:
#: `docs/MLB_PROPS.md` records one day of rung claims and draws no conclusion
#: from it: "one day is not two weeks, the ruling says four days is not
#: evidence, and the `rungs` command refuses to read a verdict out of a window
#: that has not closed." The date lived only in that prose and in FOLLOWUPS,
#: which meant the interface could not show a reader how long the wait was.
#: Declared here, dated, so the Record page can count it down like every other
#: gate (GRIDIRON_13 P1).
READ_WINDOWS: dict[str, dict] = {
    "mlb_prop_rungs": {
        "label": "the rung distribution",
        "declared": "2026-08-31",
        "opens": "2026-09-14",
        "sport": "mlb",
        "why": ("Two weeks of offered rungs. Below-floor claims clustering at "
                "60-69 near the mean rung would mean the floor is working as "
                "designed rather than the ladder being mis-set."),
    },
}

#: WHAT EACH FORECASTER IS CALLED, in one place because two places disagree.
#:
#: The Record tab has named these since GRIDIRON_12 and the Picks list needed
#: the same names in GRIDIRON_14; a second literal would have been a second
#: chance for the two pages to call the same forecaster different things.
#: Two forecasters, both blind. A third -- the operator's own informed calls
#: -- stood beside them from GRIDIRON_12 until it was withdrawn on 2026-09-02.
FORECASTER_LABELS = {"statistical": "statistical", "llm": "LLM"}

# ---------------------------------------------------------------------------
# THE FINAL PASS (2026-09-03) -- forecasting close to start, not days before it
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS. The model's confident disagreements lose (55.6% on n=207,
# docs/DIAGNOSIS.md), and D1 could not test whether that is because the market
# knows late news -- no free source publishes an opening line for those
# seasons. What the record CAN show is that the model guarantees itself the
# disadvantage by asking early. Measured lead times, live rows only:
#
#     MLB    median   7.7h      NFL    median  371h  (15.5 days)
#     CFB    median 108.5h      NBA    median 1325h  (55 DAYS)
#
# A forecast written 55 days out is written before rosters settle, before any
# injury is known, and before most factors have a current value.
#
# SO EVERY SPORT GETS A SECOND, LATE PASS. It writes NEW rows (LAW 3 --
# append-only, the early rows stand), and the LATEST ROW BEFORE START is the
# standing forecast for grading, calibration, Picks and Results. The early row
# is kept and labelled, never graded. Whether the late pass is actually better
# is not assumed here: `calibration.early_vs_final` measures it, and the
# number decides on its date.
#
# THE TIMES, AND THE HONEST PROVENANCE OF EACH. Only one of these is measured.
# docs/TIMING_FEASIBILITY.md records why the other three could not be:
#
#   MLB  MEASURED. 39 live lineup captures (2026-09-01/02) land at a median
#        1h45m before first pitch. T-2h30m would have caught 18 of 39 (46%);
#        T-1h30m catches 33 of 39 (85%). n=39 over two days is thin and is
#        not seasonal -- it is the only evidence that exists.
#   NFL  NOT MEASURED. The `injuries` table carries no timestamp at all, so
#        report timing cannot be recovered from what we hold.
#   CFB  NOT MEASURED. No college injury or depth-chart table exists.
#   NBA  NOT MEASURED. Rests on the league's published 5:30 ET report window;
#        we hold no dated record of receiving it.
#
# A time that was not measured is labelled `measured=False` and says so
# wherever it is shown. That is the same rule the ladders follow: a declared
# constant may be a judgement, but it may not look like a measurement.


@dataclass(frozen=True)
class FinalPass:
    """When a sport's late pass runs, and what stands behind the time."""

    #: Minutes before the slate's FIRST start. None for a wall-clock time.
    minutes_before_first: int | None
    #: Local wall-clock times (HH:MM) the pass runs at, when not T-minus.
    at_local: tuple[str, ...]
    #: Was this time chosen from a measurement, or declared?
    measured: bool
    #: What the time rests on, in plain words, for Settings and the close-out.
    basis: str


#: When the final-pass times were declared. Shown beside each on the settings
#: page, so a reader can see how old the judgement is.
FINAL_PASS_DECLARED = "2026-09-03"

#: Dated 2026-09-03. See docs/TIMING_FEASIBILITY.md for every figure.
FINAL_PASS: dict[str, FinalPass] = {
    "mlb": FinalPass(
        minutes_before_first=90,
        at_local=(),
        measured=True,
        basis=("1h30m before the first pitch. Measured on 39 lineups that "
               "posted before their game: 85% were up by then, and only 46% "
               "were up 2h30m out."),
    ),
    "nfl": FinalPass(
        minutes_before_first=None,
        at_local=("08:00", "14:00"),
        measured=False,
        basis=("08:00 for the Sunday card and 14:00 for a standalone night "
               "game. Not measured: the injury table carries no timestamp, so "
               "we cannot say when a report arrives."),
    ),
    "cfb": FinalPass(
        minutes_before_first=None,
        at_local=("08:00", "14:00"),
        measured=False,
        basis=("08:00 on a Saturday and 14:00 for a weeknight game. Not "
               "measured: no college injury or depth-chart data is stored."),
    ),
    # UFC: a card is one evening and the prelims start hours before the main
    # event, so the late pass sits before the first bout rather than before
    # any particular one. NOT MEASURED -- no dated record of when a UFC card's
    # information settles exists, and inventing one would be the failure
    # docs/TIMING_FEASIBILITY.md exists to refuse.
    "ufc": FinalPass(
        minutes_before_first=180,
        at_local=(),
        measured=False,
        basis=("3 hours before the first bout. Not measured: nothing in the "
               "record dates when a card's line-up settles, and weigh-ins are "
               "the day before."),
    ),
    "nba": FinalPass(
        minutes_before_first=None,
        at_local=("15:00",),
        measured=False,
        basis=("15:00, after the league's 5:30 ET injury report window. Not "
               "measured: we hold no dated record of receiving that report."),
    ),
}


#: WHICH TIER PICKS OPENS ON (ruling R2, 2026-09-02).
#:
#: STRONG, for every sport. The reader's first question is what the model is
#: most sure of, and a slate sorted by disagreement puts fifty LEAN picks in
#: front of that. The toggle to SOLID, LEAN or all tiers is one tap away and
#: is remembered for the session.
#:
#: THE FILTER NEVER HIDES WHAT IT HID: the count line reads "STRONG - 13 of 45
#: picks", so a reader can always see the denominator the default is narrowing.
#: A filter that quietly shrinks a slate is a filter that makes a thin night
#: look like a selective one.
PICKS_DEFAULT_TIER = "STRONG"

#: Which forecaster the Picks list opens on. The statistical model answers
#: every question on every slate; the LLM runs on one sport and skips rows
#: when it is degraded, so it is a choice a reader makes rather than the one
#: they are given.
PICKS_DEFAULT_FORECASTER = "statistical"

#: The markets each sport asks about. MLB is moneyline only: there is no run
#: line question worth asking that the moneyline does not already ask better.
SPORT_MARKETS: dict[str, tuple[str, ...]] = {
    # THE MONEYLINE JOINED 2026-09-04 (MARKET_ROSTER #18). Like the NBA's, it
    # needs no player identity match and resolves from a final score present
    # for every stored game. The spread stays first: it is the market this
    # sport was built on.
    "nfl": ("spread", "moneyline", "total", "passing_yards",
            "receiving_yards", "rushing_yards", "receptions", "passing_tds"),
    # THE RUN LINE AND THE TOTAL joined 2026-09-02 (GRIDIRON_16 STEP 3), on
    # the evidence in docs/MLB_RUNLINE_FEASIBILITY.md: ESPN carries both on
    # every priced game, at a rung fixed at +/-1.5, with explicit side labels.
    "mlb": ("moneyline", "spread", "total",
            "batter_hits", "batter_total_bases",
            "batter_home_runs", "batter_strikeouts", "pitcher_strikeouts"),
    # THE MONEYLINE IS FIRST (MARKET_ROSTER #1, declared 2026-09-04). It ranks
    # 20th of 21 on volume and is the most reliable entry on the list: it needs
    # no player identity match, no lineup and no crosswalk, and it resolves
    # from a final score that is present for 100% of 21,527 stored games. Every
    # prop above it depends on a name matching a name.
    "nba": ("moneyline", "spread", "total", "points", "rebounds", "assists",
            "threes"),
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
    # THE OPERATOR'S THREE, IN THEIR ORDER (2026-09-03). No method-of-victory:
    # it was excluded by the brief and is not smuggled in as a fourth.
    #
    # `rounds` and `distance` are the sport's own question shapes and share no
    # calibration family with a moneyline -- a fight ending inside a round is
    # right or wrong for entirely different reasons than who won it.
    "ufc": ("moneyline", "rounds", "distance"),
}

#: Which of a sport's markets are player props (the rest are game markets).
SPORT_PROP_MARKETS: dict[str, tuple[str, ...]] = {
    "nfl": ("passing_yards", "receiving_yards", "rushing_yards",
            "receptions", "passing_tds"),
    # `batter_strikeouts` JOINED 2026-09-04 (MARKET_ROSTER #3), and its
    # POSITION IN THIS TUPLE MATTERS: `select_day_props` fills the day by
    # round-robin in this order, so a market added at the end is served last
    # when the cap bites. It sits after the batting markets and before
    # pitcher strikeouts, which is where its liquidity puts it.
    "mlb": ("batter_hits", "batter_total_bases", "batter_home_runs",
            "batter_strikeouts", "pitcher_strikeouts"),
    "nba": ("points", "rebounds", "assists", "threes"),
    "cfb": (),          # measured, not assumed: no prop lines exist
    # NO PLAYER PROPS IN UFC. A bout has two competitors and the questions are
    # about the bout, not about a person's counting stat.
    "ufc": (),
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
    # UFC seasons are plain calendar years -- the sport has no season shape at
    # all, only a rolling calendar of cards.
    "ufc": int(os.environ.get("GRIDIRON_UFC_SEASON", "2026")),
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
    # THE ROUNDS MARKET IS A TOTAL: over or under a posted length. It is named
    # `rounds` rather than `total` because a reader asked "the total" about a
    # fight would reasonably think of points, and there are none.
    "ufc": ("rounds",),
}


# (A helper that reads this table arrives in B6, with the guard that needs it.
#  Writing it now would ship a function nothing calls, which is what the orphan
#  scan exists to catch -- and did, within a minute of it being added.)

#: WHICH MARKETS CARRY A FINDING ABOUT THEIR OWN METHOD (operator ruling 2,
#: 2026-09-04).
#:
#: A market can be fitted, calibrated, honest about its sample and still be
#: asking a question with almost nothing in it. The two totals measured
#: walk-forward came back at +0.0010 (NBA) and +0.0016 (NFL) against
#: always-the-base-rate, and the close-out established WHY: the rung is chosen
#: as the ladder point nearest the model's own expectation, so P(over) is one
#: half by construction and the only thing left for a coefficient to find is
#: the rounding residual.
#:
#: THE FINDING IS ABOUT THE METHOD, NOT THE MODEL, which is why it is declared
#: per (sport, market) rather than derived from a Brier score. A totals model
#: that measured +0.05 next season would still be asked at its own rung, and
#: the flag would still be true.
#:
#: DERIVED FROM THE DECLARED LIST, never a hardcoded row. Every `total` this
#: project declares is asked at a rung chosen from its own expectation --
#: `nfl_total_asked`, `nba_total_asked`, `mlb_total_asked` and
#: `cfb_total_asked` all take the model's expectation and return a rung, and a
#: planting asserts that none of them escapes this map. A sixth sport
#: declaring a total is flagged the day it is declared, which is the same rule
#: the market tabs follow and the fix for the failure STEP 4 found four times
#: in one session.
#:
#: UFC's `rounds` IS A TOTAL AND IS NOT FLAGGED. Its rung is fixed by the
#: bout's scheduled length -- 2.5 for a three-rounder, 4.5 for a five -- so it
#: is not chosen from the model's expectation and the construction argument
#: does not reach it. That is a difference in method, and this table is about
#: method.
#:
#: SESSION E WAS THE FIX, AND IT DID NOT WORK (2026-09-04). The plan was to
#: stop asking at our own rung: write the model's forecast DISTRIBUTION blind,
#: then read P(over) off it at the MARKET's line. The walk-forward tested that
#: against the rung method on 3,947 out-of-sample games and refused it in all
#: four arms -- worse calibrated by 6 to 13 percentage points, with a NEGATIVE
#: edge everywhere. `DISTRIBUTIONAL_VERDICTS` above carries the figures.
#:
#: SO THIS FLAG IS NOT WAITING FOR ANYTHING. It stood for one version pending
#: a fix; the fix was built, measured and refused, and the finding it reports
#: is now better evidenced than when it was written. It stands until some
#: other change makes it false, and the note's own wording -- "so far" -- is
#: the part doing that work.
#: WHAT THE WALK-FORWARD SAID, per sport and market (Session E Part 2,
#: 2026-09-04). `tools/walkforward_distributional.py` produced every figure.
#:
#: THE CLAUSE IT ANSWERS, from `docs/DISTRIBUTIONAL.md` §7: *"The change ships
#: only if the distributional read-out is better calibrated than the current
#: rung method, measured on identical games, walk-forward."* And the operator's
#: ruling of the same day: **PER SPORT** -- LAW 6 makes each sport its own
#: decision, and sports are never averaged to reach a verdict.
#:
#: IT SAID NO, IN ALL FOUR ARMS, on 3,947 out-of-sample games. The read-out is
#: worse calibrated by 6 to 13 percentage points everywhere, and its edge over
#: always-the-base-rate is NEGATIVE in every arm -- worse than guessing.
#:
#: THE DISTRIBUTIONS THEMSELVES ARE HONEST. Every PIT came back flat, well
#: inside the declared tolerance, so the spread is right for the mean. What
#: fails is the step after: reading a probability off an honest distribution
#: AT SOMEBODY ELSE'S NUMBER assumes our mean is unbiased relative to theirs,
#: and it is not. The market's number lands closer to the result on 55-59% of
#: games, so most of what looks like disagreement is our error, and the more
#: confidently the read-out disagrees the more wrong it is -- monotonically,
#: in all four arms, to a claimed 86% that came in at 43%.
#:
#: SO NOTHING SHIPS, and these markets stay on rungs. The design document
#: stands as the record of a hypothesis that failed its test, which is what it
#: said it would be.
DISTRIBUTIONAL_VERDICTS: dict[tuple[str, str], dict] = {
    ("nfl", "total"): {
        "verdict": "DO NOT SHIP",
        "measured_utc": "2026-09-04T00:00:00Z",
        "n": 768,
        "splits": "trained through 2022, 2023, 2024; tested on the season after each",
        "rung_gap_pts": 0.35,
        "readout_gap_pts": 13.24,
        "rung_edge": 0.0011,
        "readout_edge": -0.0281,
        "readout_reach_70_pct": 12.37,
        "pit_flat": True,
        "market_closer_share_pct": 57.42,
        "why": ("the read-out is 13.2 points worse calibrated and its edge is "
                "negative; the market's total lands closer on 57% of games"),
    },
    ("nfl", "spread"): {
        "verdict": "DO NOT SHIP",
        "measured_utc": "2026-09-04T00:00:00Z",
        "n": 813,
        "splits": "trained through 2022, 2023, 2024; tested on the season after each",
        "rung_gap_pts": 1.93,
        "readout_gap_pts": 11.91,
        "rung_edge": 0.0036,
        "readout_edge": -0.0164,
        "readout_reach_70_pct": 7.75,
        "pit_flat": True,
        "market_closer_share_pct": 58.92,
        "why": ("the read-out is 10.0 points worse calibrated and its edge is "
                "negative; the market's spread lands closer on 59% of games"),
    },
    ("nba", "total"): {
        "verdict": "DO NOT SHIP",
        "measured_utc": "2026-09-04T00:00:00Z",
        "n": 1223,
        "splits": "trained through 2024, tested on 2025",
        "rung_gap_pts": 3.98,
        "readout_gap_pts": 9.60,
        "rung_edge": -0.0030,
        "readout_edge": -0.0147,
        "readout_reach_70_pct": 6.05,
        "pit_flat": True,
        "market_closer_share_pct": 54.78,
        "why": ("the read-out is 5.6 points worse calibrated and its edge is "
                "negative; the market's total lands closer on 55% of games"),
    },
    ("nba", "spread"): {
        "verdict": "DO NOT SHIP",
        "measured_utc": "2026-09-04T00:00:00Z",
        "n": 1143,
        "splits": "trained through 2024, tested on 2025",
        "rung_gap_pts": 2.57,
        "readout_gap_pts": 12.39,
        "rung_edge": 0.0085,
        "readout_edge": -0.0197,
        "readout_reach_70_pct": 11.20,
        "pit_flat": True,
        "market_closer_share_pct": 57.22,
        "why": ("the read-out is 9.8 points worse calibrated and its edge is "
                "negative; the market's spread lands closer on 57% of games"),
    },
    # CFB'S TOTAL WAS NOT TESTED, and the reason is not line coverage. Its
    # EXPECTATION does not work: regressing the actual total on it gives slope
    # 0.109 and R-squared 0.0093 over 1,639 games, so the sum of two
    # points-per-game figures explains under one per cent of a college total.
    # There is nothing to build a distribution on, and the brief's "fit it
    # first, then include CFB" was answered by the fit itself.
    ("cfb", "total"): {
        "verdict": "NOT RUN",
        "measured_utc": "2026-09-04T00:00:00Z",
        "n": 1639,
        "splits": "no walk-forward; the expectation was measured and refused",
        "rung_gap_pts": None,
        "readout_gap_pts": None,
        "rung_edge": None,
        "readout_edge": None,
        "readout_reach_70_pct": None,
        "pit_flat": None,
        "market_closer_share_pct": None,
        "why": ("the expectation explains 0.93% of the variance in a college "
                "total (slope 0.109), so there is no forecast to distribute"),
    },
}
DISTRIBUTIONAL_VERDICTS_DECLARED = "2026-09-04T00:00:00Z"

#: The markets that actually run distributionally. DERIVED from the verdicts,
#: so a market cannot start reading out without a recorded SHIP -- which is
#: the failure `plant_a_market_shipped_without_a_verdict` breaks on purpose.
#:
#: EMPTY, on 2026-09-04, and that is the whole result of Session E Part 2.
DISTRIBUTIONAL_MARKETS: frozenset[tuple[str, str]] = frozenset(
    key for key, entry in DISTRIBUTIONAL_VERDICTS.items()
    if entry.get("verdict") == "SHIP")


def distributional_verdict(sport: str, market: str) -> dict | None:
    """What the walk-forward said about this market, or None if never asked."""
    return DISTRIBUTIONAL_VERDICTS.get((sport, market))


def is_distributional(sport: str, market: str) -> bool:
    """Does this market ask at the market's line rather than at a rung?"""
    return (sport, market) in DISTRIBUTIONAL_MARKETS


FLAGGED_METHODS: dict[tuple[str, str], str] = {
    (sport, "total"): "total_at_own_rung"
    for sport, markets in SPORT_MARKETS.items() if "total" in markets
}
FLAGGED_METHODS_DECLARED = "2026-09-04T00:00:00Z"


def flagged_method(sport: str | None, market_type: str | None) -> str | None:
    """The finding key this market's METHOD carries, or None.

    The words live in `language.METHOD_NOTES`; this says only WHICH finding
    applies. Split for the same reason every other plain-words split exists:
    no sentence a reader sees is composed outside `language.py`.
    """
    if not sport or not market_type:
        return None
    return FLAGGED_METHODS.get((sport, market_type))



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
    # UFC: the years already loaded by ufc_loader (2022-2026). A card is 12
    # bouts and each bout costs a status fetch, so a season is roughly 1,800
    # requests -- five gives the Elo enough history to be worth having and
    # keeps the loader courteous.
    "ufc": tuple(range(2022, 2027)),
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

#: PER MARKET, FROM 2026-09-03 -- the fix FOLLOWUPS asked for, made at the
#: moment it stopped being free.
#:
#: The note above says it plainly: "the string is global, factor sets are per
#: sport per market, so a change to one NBA prop factor would bump the version
#: for every MLB market too and split records nothing touched... it is much
#: cheaper before a single-sport bump is ever needed than after." This is that
#: bump. The asked-line redeclaration touches the SPREAD factor sets of three
#: sports and nothing else.
#:
#: MEASURED BEFORE DECIDING. Settled rows at the time of the bump:
#:
#:      spread, all sports          8   (MLB run line only)
#:      NOT spread                126   (MLB moneyline 80, props 38, total 8)
#:
#: A global bump to fs3 would have split that 126 -- including the project's
#: largest single record -- for a change that touched none of it.
#:
#: MLB's spread is DELIBERATELY ABSENT. Its run line is asked at a fixed
#: plus-or-minus 1.5 and has no asked-line factor at all, so nothing about it
#: changed and its eight settled rows stay on fs2.
FACTOR_SET_VERSIONS: dict[tuple[str, str], str] = {
    # THE COUNT MARKETS CHANGED MODEL FORM on 2026-09-03 (Session C): a
    # logistic became a Poisson or negative-binomial rate. That is a bigger
    # change than a factor moving -- the same inputs now reach the answer
    # through a different link -- so the rows before and after are not one
    # record and must not share a curve.
    #
    # THE MARKET KEY CARRIES THE STAT because the version is per market and a
    # count market's key is 'prop:passing_tds', not 'prop'. Versioning 'prop'
    # would split every NFL prop, including the yardage markets this ruling
    # did not touch.
    ("nfl", "prop:passing_tds"): "fs3-rate",
    ("nfl", "prop:receptions"): "fs3-rate",
    ("mlb", "prop:batter_home_runs"): "fs3-rate",
    ("mlb", "prop:batter_hits"): "fs3-rate",
    ("mlb", "prop:pitcher_strikeouts"): "fs3-rate",
    ("nfl", "spread"): "fs3",
    # NBA SPREAD GAINED A FACTOR on 2026-09-03 (Session D): `nba_srs_diff`, an
    # opponent-adjusted rating declared beside the rolling net rating. A model
    # with a factor the previous one did not have is a different model, and its
    # rows belong to a different curve.
    #
    # THE NFL SPREAD IS DELIBERATELY NOT BUMPED. Session D's brief expected to
    # add the adjusted factor to both sports; the NFL already had it --
    # `srs_diff`, declared 2026-08-28 -- so no NFL factor moved. What changed
    # for the NFL is the PROSE, which is not a factor set. Versioning it would
    # split a curve for a change that cannot affect a probability, and a
    # version bump that means nothing is worse than none: it teaches a reader
    # that the marker is decorative.
    ("nba", "spread"): "fs4",
    ("cfb", "spread"): "fs3",
}


def factor_set_version(sport: str | None = None,
                       market_type: str | None = None) -> str:
    """Which factor set a question belongs to.

    Falls back to the global default, so a market with no entry keeps the
    version it has always had and its record is not split by somebody else's
    change. Called with neither argument it IS the default, which is what the
    display surfaces want.
    """
    if sport is None or market_type is None:
        return FACTOR_SET_VERSION
    return FACTOR_SET_VERSIONS.get((sport, market_type), FACTOR_SET_VERSION)

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
#: Read from the process environment OR from `.env`, so the key can live with
#: the installation the way the access token does rather than with a Windows
#: account -- it survives a machine move, and a rebuild cannot delete it
#: because `.env` deliberately sits outside the bundle.
ANTHROPIC_API_KEY = setting("ANTHROPIC_API_KEY")
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
    # MARKET_ROSTER #3, declared 2026-09-04. Measured over 125,298 stored
    # batter-games: mean 0.889 strikeouts, and the two rungs land at 61.7% and
    # 22.2% over. TWO RUNGS RATHER THAN ONE, exactly as `batter_hits` has: at
    # 0.5 alone the question inherits its base rate as the answer, which is
    # the failure that disqualified triples at 1.3% and makes doubles thin at
    # 13.7%. A second rung gives the model somewhere to disagree.
    #
    # 2.5 IS NOT DECLARED. It is over 4.6% of the time, which is the
    # one-sidedness the roster's own section 4(a) rules out -- 270 of those a
    # night would be a category a model saying "no" unconditionally would look
    # calibrated on, having measured nothing.
    "batter_strikeouts": (0.5, 1.5),
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


#: FACTORS WHOSE COEFFICIENTS CANNOT BE READ ONE AT A TIME (D1, 2026-09-03).
#:
#: When two correlated factors are fitted together and the model uses their
#: DIFFERENCE, each coefficient stops describing its own factor. Measured over
#: the stored record on 2026-09-03, standardised (coefficient x factor SD):
#:
#:   nfl spread    srs_diff        alone -0.083   together -0.211
#:                 recent_form_diff alone +0.048  together +0.194   r = 0.698
#:
#:   nba spread    nba_srs_diff    alone +0.200   together +0.536
#:                 nba_net_rating_rolling alone -0.040  together -0.440  r = 0.791
#:
#: Both members inflate -- by 2.5x and 4x in the NFL, by 2.7x and 11x in the
#: NBA -- and take OPPOSITE SIGNS. That is mutual suppression: the pair is
#: measuring "season-long quality against the schedule faced, set against how
#: the club has played lately", and neither half of that is a claim on its own.
#:
#: WHY THIS IS NOT JUST A NOTE IN A DOCUMENT. The card's "why" reads each
#: contribution and names its declared phrase, so a reader was going to be told
#: that "how the two clubs have been playing lately" was pulling AGAINST the
#: pick. It was not. It was carrying the half of a difference. A sentence that
#: is arithmetically derived and still false is the worst kind this project can
#: print, because it looks checked.
#:
#: SO THE PAIR IS DESCRIBED AS ONE REASON, summing the two contributions --
#: which is what the model actually did with them -- under one declared phrase.
#: The decomposition on the Factors page still shows both separately, because
#: somebody auditing the model needs the parts; the card shows the reason.
#:
#: THIS IS NOT A RETIREMENT. The brief asks both to stay declared for one
#: version so they can be scored against each other, and the pair predicts
#: better than either alone (nba Brier .2403 both, .2448 adjusted only, .2467
#: raw only). Retiring the raw member would cost real accuracy. What it cannot
#: be allowed to cost is a true sentence.
JOINTLY_READ_FACTORS: dict[tuple[str, str], tuple[tuple[str, ...], str]] = {
    ("nfl", "spread"): (
        ("srs_diff", "recent_form_diff"),
        "how good the two teams have been, against who they played and how "
        "lately",
    ),
    ("nba", "spread"): (
        ("nba_srs_diff", "nba_net_rating_rolling"),
        "how good the two clubs have been, against who they played and how "
        "lately",
    ),
}
JOINTLY_READ_DECLARED = "2026-09-03T00:00:00Z"


#: SPORTS WHOSE RECORD SPLITS BELOW THE MARKET (R2, 2026-09-03).
#:
#: LAW 6 forbids one curve across two sports because the easy one dilutes the
#: hard one. The same argument applies one level down wherever a sport contains
#: populations that differ enough to matter, and UFC does:
#:
#:     tier          settled   goes the distance
#:     fight_night     1,619        55.3%
#:     numbered          753        58.0%
#:     contender         218        43.6%
#:
#: Twelve to fourteen points. A single UFC distance curve would average a 43.6%
#: population with a 58.0% one and describe nobody, and it would FLATTER, in
#: the same direction and for the same reason the law was written about.
#:
#: EACH TIER CARRIES ITS OWN GATE. `MIN_SAMPLE_FOR_EDGE_CLAIM` applies per
#: category, so splitting the record three ways means three separate hundreds
#: rather than one shared one. That is slower and it is the point: a Contender
#: Series claim earned on numbered-card evidence is not earned.
#:
#: A CARD WITH NO TIER JOINS NO CATEGORY. The source carries no tier field, so
#: an unrecognised card name is stamped NULL, and NULL is not a tier -- those
#: bouts feed the rating pool and are never scored, because there is no honest
#: category for them.
SPORT_EVENT_TIERS: dict[str, tuple[str, ...]] = {
    "ufc": ("numbered", "fight_night", "contender"),
}
EVENT_TIERS_DECLARED = "2026-09-03T00:00:00Z"


def event_tiers(sport: str) -> tuple[str, ...]:
    """The tiers a sport's record splits into, or () when it does not split."""
    return SPORT_EVENT_TIERS.get(sport, ())


def jointly_read(sport: str, market: str):
    """The jointly-read groups for one market, as (names, phrase) pairs."""
    entry = JOINTLY_READ_FACTORS.get((sport, market))
    return [entry] if entry else []

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
