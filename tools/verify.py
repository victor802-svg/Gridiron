"""The G6 verification run, in one command.

    python tools/verify.py

Four steps, reported honestly:

  1. The full test suite.
  2. The planted-violation harness: every law broken on purpose, every guard
     required to fire.
  3. One complete week end to end — questions chosen, factors computed,
     probabilities written blind, lines snapshotted afterwards, outcomes
     resolved, calibration rendered with its (tiny) N. Run on the most recent
     COMPLETED week, because a week that has not been played cannot be
     resolved, and this step is about proving resolution works.
  4. The status of the live forward week: written before kickoff, lines
     snapshotted after, waiting for the games. Its N is zero until they are
     played, and this says so rather than borrowing step 3's numbers.

Steps 3 and 4 are reported separately and never added together. Step 3 is a
retrospective run and proves the pipeline works. Step 4 is the only thing that
could ever become evidence, and it has not happened yet.

THE GATE READS THE LIVE RECORD, NEVER WRITES IT (operator ruling, 2026-09-24).
On 24 September a gate run from a worktree put an unmerged trigger on the
operator's record: step 2 opened it with `db.open_db`, which runs the tree's
own schema against the file. Now the whole run is verification to `db`, so
any writable open of the record is refused by name; every read goes through
`db.read_the_live_record`, which opens the file read-only; step 2's record
checks and step 3's facts read one scratch copy backed up from that handle and
migrated to this tree's schema; and the record's schema is read when the gate
starts and again when it ends, and a difference fails the gate naming each
object.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
# `tools/` itself, so the shared copy helper imports by name.
sys.path.insert(0, str(Path(__file__).resolve().parent))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import calibration, config, db, resolve, run  # noqa: E402
from gridiron.factors import store  # noqa: E402
from gridiron.model import baseline  # noqa: E402

from dbcopy import FACT_TABLES, copy_facts  # noqa: E402,F401


def summarise(outcomes: dict, skipped=()) -> tuple[int, list[str]]:
    """The verdict, and why. A SKIPPED TIER IS NEVER A PASS.

    Kept as a pure function so a test can hold it to that: hand it a set of
    outcomes that all passed plus one skipped tier, and it must still refuse.
    The failure this guards against is not a bug so much as a habit -- running
    the quick tier, seeing four green rows, and carrying the word "green" into
    a commit message that will outlive the memory of which tier it came from.
    """
    lines = [f"  {'PASS' if ok else 'FAIL'}  {name}"
             for name, ok in outcomes.items()]
    for tier in skipped:
        lines.append(f"  SKIPPED  {tier} -- {TIERS.get(tier, 'an unnamed tier')}")

    if skipped:
        lines += [
            "",
            "INCOMPLETE. " + str(len(skipped)) + " tier(s) above were not run, "
            "so the rows that",
            "passed describe less than the gate does. This is not a pass and is "
            "not",
            "reported as one; run `python tools/verify.py` with no flags for the "
            "gate.",
        ]
        return 1, lines

    lines += [
        "",
        "Step 3 is retrospective and proves the pipeline works. Step 4 is the",
        "only step that could ever become evidence of an edge, and it will not",
        "be evidence of anything until it has a season behind it.",
    ]
    return (0 if all(outcomes.values()) else 1), lines


def rule(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


#: THE TIERS THIS SUITE CAN BE RUN IN, and what each one is worth. Named here
#: so that skipping one is a thing the output has to SAY rather than a silence.
#:
#: `--quick` exists for the middle of a change, when the fast tier answers the
#: question you actually have. It is not a gate, and the summary says so in
#: those words rather than printing a row of PASSes that mean something
#: narrower than they appear to.
TIERS = {
    "browser": "the browser suite -- 77 tests driving a real Chromium",
    "slow": "tests that fetch real data over the network",
    "tests": "the entire test suite (--skip-tests)",
    "end to end": "steps 3 and 4, which need a real database to replay",
}


def step_1_tests(quick: bool, parallel: int = 0) -> tuple[bool, tuple[str, ...]]:
    """Run the suite. Returns (passed, tiers that were NOT run).

    STREAMED, NOT CAPTURED, and that is the point of this phase. The previous
    version passed `capture_output=True` and printed the last three lines when
    it finished -- so for the whole run there was nothing on screen at all, and
    a suite that was merely slow looked exactly like one that had hung. On
    2026-09-01 that cost a wrong diagnosis: the run was killed as "stuck" on
    the evidence of a CPU reading, and it was fine, and had in fact just
    passed. Progress you cannot see is progress you end up guessing about.
    """
    rule("STEP 1 — the full test suite")
    args = [sys.executable, "-m", "pytest", "-q"]
    if parallel:
        # OPT-IN, NOT THE MECHANISM (ruling, 2026-09-02). The suite runs in
        # about three minutes serially, and the fewest moving parts that clear
        # the target is the right answer: parallel workers cost determinism in
        # ordering, make a failure harder to reproduce, and add a dependency
        # for a gate that does not need one. The flag stays because a slower
        # machine may need it.
        args += ["-n", str(parallel)]
        print(f"PARALLEL: {parallel} workers. Ordering is not deterministic;")
        print("Reproduce a failure without this flag." + chr(10))
    skipped: tuple[str, ...] = ()
    if quick:
        args += ["-m", "not browser and not slow"]
        skipped = ("browser", "slow")
        print("QUICK MODE. Not running: "
              + "; ".join(f"{t} ({TIERS[t]})" for t in skipped))
        print("This cannot pass the gate -- see the summary.\n")
    # A TIER THAT IS ABSENT RATHER THAN DECLINED (2026-09-04).
    #
    # The browser tests skip themselves when playwright cannot be imported --
    # `requirements-dev.txt` says so, and that is right for a contributor with
    # no browsers installed. It is WRONG FOR THE GATE. Run under an interpreter
    # without playwright, every browser test skips, pytest exits 0, and this
    # step reports a pass over a suite whose entire rendering half did not run.
    #
    # THAT HAPPENED. On 2026-09-04 a full run was made with the system Python
    # rather than the project's `.venv`: 31 silent skips, and four newly
    # written browser tests among them that had never once executed. The
    # quick-mode machinery below already exists so that "not running a tier is
    # a thing the output has to SAY rather than a silence" -- absence by
    # accident deserves the same treatment as absence by flag.
    if not quick and importlib.util.find_spec("playwright") is None:
        skipped = ("browser",)
        print("PLAYWRIGHT IS NOT IMPORTABLE under " + sys.executable)
        print("The browser tier skipped itself. This cannot pass the gate."
              + chr(10))
    # No capture: pytest writes straight to this terminal, dots and all.
    result = subprocess.run(args, cwd=str(REPO))
    return result.returncode == 0, skipped


class NoRecordToCopy(RuntimeError):
    """There is no live record for the record checks to read a copy of."""


#: THE GATE'S ONE COPY OF THE LIVE RECORD (operator ruling, 2026-09-24).
#:
#: Step 2's record checks and step 3's facts read THIS, never the record. It
#: is backed up once per run through the read-only door, into the temp
#: directory, and migrated there with `open_db` -- so a check that reads a
#: table this tree adds and the record does not hold yet (`recommendation_voids`
#: on the day this was written) reads it from the copy, and the tree's schema
#: never reaches the operator's file before it merges. ONE BACKUP PER RUN, not
#: one per check: the record is about a gigabyte.
#:
#: What the copy checks is the record as it WILL be once this tree merges: its
#: rows, under this tree's schema. That is the question a gate is asked.
_GATE_COPY: dict = {}


def _gate_copy_path() -> Path:
    """The gate's copy of the live record, made on first use."""
    if "path" in _GATE_COPY:
        return _GATE_COPY["path"]
    if not Path(config.DB_PATH).exists():
        raise NoRecordToCopy(
            f"no live record at {config.DB_PATH}, so there is nothing for the "
            f"record checks to read")
    started = time.time()
    folder = Path(tempfile.mkdtemp(prefix="gridiron-gate-"))
    _GATE_COPY.update(folder=folder, conns=[])
    target = folder / "record.db"
    source = db.read_the_live_record(
        "backing the record up into the gate's own scratch copy, which the "
        "record checks read and migrate instead of the record itself")
    try:
        copy = sqlite3.connect(str(target))
        try:
            # ONE INSTANT OF THE RECORD. pages=-1 copies every page in one
            # step, inside one read transaction, so a scheduled task writing
            # meanwhile cannot leave the copy half of one moment and half of
            # the next. The record is in WAL, so the read blocks no writer.
            source.backup(copy, pages=-1)
        finally:
            copy.close()
    finally:
        source.close()
    db.open_db(target).close()
    _GATE_COPY["path"] = target
    print(f"  the record checks read a copy of the live record, not the "
          f"record: {target.stat().st_size / 1e9:.2f} GB, migrated to this "
          f"tree's schema, in {time.time() - started:.0f}s")
    return target


def _record_conn():
    """A handle on the gate's copy of the live record, for the scans that
    check stored rows.

    Until 2026-09-24 this was `db.connect()` on the record itself: a writable
    handle, opened afresh by every check and never closed.
    """
    conn = db.connect(_gate_copy_path())
    _GATE_COPY["conns"].append(conn)
    return conn


def _close_the_record_handles() -> None:
    for conn in _GATE_COPY.get("conns", ()):
        try:
            conn.close()
        except sqlite3.Error:
            pass
    if "conns" in _GATE_COPY:
        _GATE_COPY["conns"] = []


def _drop_the_gate_copy() -> None:
    """Close every handle on the copy and delete it. Says so if it cannot."""
    _close_the_record_handles()
    folder = _GATE_COPY.get("folder")
    _GATE_COPY.clear()
    if folder is None:
        return
    shutil.rmtree(folder, ignore_errors=True)
    if folder.exists():
        print(chr(10) + f"the gate's copy of the record could not be removed: "
              f"{folder} -- delete it by hand; it is about a gigabyte")


def record_schema(conn) -> dict:
    """Every object a record defines, keyed by kind and name, with its SQL.

    An added column shows here too: `ALTER TABLE ... ADD COLUMN` rewrites the
    table's stored CREATE statement.
    """
    return {(row[0], row[1]): row[2] for row in conn.execute(
        "SELECT type, name, sql FROM sqlite_master")}


def schema_changes(before: dict, after: dict) -> list[str]:
    """What changed between two readings of a schema, one line per object."""
    changes = []
    for key in sorted(set(before) | set(after)):
        kind, name = key
        if key not in before:
            changes.append(f"{kind} {name} was created")
        elif key not in after:
            changes.append(f"{kind} {name} was dropped")
        elif before[key] != after[key]:
            changes.append(f"{kind} {name} was redefined")
    return changes


def _the_live_schema() -> dict | None:
    """The live record's schema, read through the read-only door; None when
    there is no record."""
    if not Path(config.DB_PATH).exists():
        return None
    conn = db.read_the_live_record(
        "the live record's schema, read when the gate starts and again when "
        "it ends, so that a gate that changed it fails by name")
    try:
        return record_schema(conn)
    finally:
        conn.close()


def the_record_is_as_found(before: dict | None) -> bool:
    """THE GATE LEAVES THE LIVE RECORD'S SCHEMA AS IT FOUND IT (2026-09-24).

    Compared, not counted. The scheduled tasks write rows into the record for
    the whole of a gate's run, so a row count would fail every gate and prove
    nothing; rows are protected structurally instead -- this process cannot
    hold a writable handle on the record. The schema is different: nothing
    changes it except code that has not been gated, which is exactly what
    happened twice on 23 and 24 September.

    It cannot tell who changed the schema -- a step of this gate, or a
    scheduled task importing code that has not merged -- and does not need to:
    a gate that watched the record change underneath it is not evidence that
    this tree is safe to merge.
    """
    rule("THE LIVE RECORD, AS THE GATE FOUND IT")
    after = _the_live_schema()
    if before is None and after is None:
        print(f"  PASS  no live record at {config.DB_PATH}, before or after")
        return True
    if before is None:
        changes = [f"the record at {config.DB_PATH} was created"]
    elif after is None:
        changes = [f"the record at {config.DB_PATH} disappeared"]
    else:
        changes = schema_changes(before, after)
    if not changes:
        print(f"  PASS  the live record's schema is what it was when the gate "
              f"began: {len(after)} objects")
        return True
    for change in changes:
        print(f"  FAIL  the live record changed during the gate: {change}")
    print("  Find what wrote it -- a gate step, or a scheduled task running "
          "code that has not" + chr(10) + "  merged -- and run the gate "
          "again.")
    return False


def _refused_by_name(step, *args) -> bool:
    """Run a step. A reach for the live record fails it BY NAME, and the gate
    goes on to the next step and to its own summary rather than ending in a
    traceback."""
    try:
        return step(*args)
    except db.LiveRecordTouched as exc:
        print(f"  FAIL  {str(exc).splitlines()[0]}")
        return False


def _env_file():
    """Where the operator's settings live, for the credential scan to read the
    NAMES in. It never reads a value."""
    from gridiron import auth

    return auth.ENV_FILE


def _config():
    from gridiron import config

    return config


def _slate_payload(sport: str):
    """One sport's current slate as the page would render it."""
    from gridiron import views

    return views.week(_record_conn(), sport)


def _at_the_line_payload():
    """Every sport's at-the-line words, in one payload for the advice scan.

    Built from the live record rather than from a fixture: the words that
    matter are the ones a reader would meet today, and a scan that reads a
    fixture proves only that the fixture is polite. Read from the gate's copy
    of it from 2026-09-24, which holds the same rows.
    """
    from gridiron import calibration, config

    conn = _record_conn()
    return {"sports": [calibration.at_the_line_scorecard(conn, sport=sport)
                       for sport in config.SPORTS]}


def step_2_guards() -> bool:
    rule("STEP 2 — planted violations")
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "guards" / "plant.py")],
        cwd=str(REPO), capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("[") or "planted violations were caught" in line:
            print(line)
    ok = result.returncode == 0

    # The standing scans, run against the REAL package rather than a planted
    # copy. A planting proves a scan fires; this proves the package passes it.
    # They were reachable only from tests until 2026-08-31, which the orphan
    # scan is what noticed.
    from gridiron import audit, views

    # EVERY RECORD CHECK BELOW READS THE GATE'S COPY (operator ruling,
    # 2026-09-24). Until then the foreign-key check opened the record itself
    # with `open_db` -- migrating it to this tree's schema, merged or not --
    # and the rest opened it writable with `db.connect()`. The copy is made
    # here, before the first check, so its one line of output is not buried
    # between two of them.
    print()
    try:
        _gate_copy_path()
    except NoRecordToCopy as exc:
        print(f"  {exc}; every check that reads it fails below")
    for name, fn in (
        # FIRST, AND FIRST FOR A REASON (ruling 4, 2026-09-09). A file that
        # does not parse makes every scan after it meaningless: they read it
        # as text and pass, while the browser runs none of it. This is the
        # check that was missing on 2026-09-08.
        ("the browser files parse", audit.check_the_browser_files_parse),
        ("prediction closures (LAW 1)", audit.check_all_prediction_closures),
        ("no orphan functions", audit.check_no_orphan_functions),
        # ADDED 2026-09-03 AFTER IT HAPPENED. Widening a sport CHECK on `games`
        # left twelve tables and 311,655 rows with foreign keys naming a table
        # that no longer existed. Every read worked; the suite was green; the
        # first INSERT in hours is what found it. A schema fault that only
        # breaks on write is the worst kind for a project that mostly reads.
        #
        # ON THE COPY, MIGRATED, FROM 2026-09-24 -- which is what this check
        # was written to ask: whether this tree's migration leaves a foreign
        # key naming a table that is gone, before it reaches the record.
        ("every foreign key points at a real table",
         lambda: audit.check_no_dangling_references(_record_conn())),
        # OPERATOR RULING 2 (2026-09-04). Both halves: the declaration cannot
        # drift from the code that earns it, and the hero cannot quietly start
        # leading with a market whose own note calls it a coin flip.
        # OPERATOR RULING 4 (2026-09-04). A vendored binary is checkable to
        # exactly the extent its provenance is recorded AND enforced.
        # SESSION E PART 2 (2026-09-04). The walk-forward said DO NOT SHIP in
        # all four arms; this is what keeps that answer binding rather than
        # advisory, in both directions.
        ("every market matches its own verdict",
         audit.check_distributional_verdicts),
        # RULINGS 2 AND 3 (2026-09-04). A market the model cannot inform is
        # shown with its caveat rather than withdrawn, and no confidence floor
        # reaches a market that asks about every game on the slate.
        ("no market is hidden", audit.check_no_market_is_hidden),
        # MEASURED 2026-09-04: 17 of 379 live chips had a settled record
        # behind them, and the grid said so only in a hover tooltip.
        ("a chip says what it is", audit.check_the_chip_says_what_it_is),
        # CHECKLIST ITEM 5 ON THE PROMPT (2026-09-05). The feature vector and
        # the factor code were both watched; what the model is TOLD was not.
        ("an absent factor is not a zero",
         audit.check_the_prompt_keeps_absence_absent),
        # A PUSH THAT REACHED THE PHONE EXISTS IN THE RECORD (2026-09-05).
        ("the record precedes the push",
         audit.check_the_record_precedes_the_push),
        # A RESUMED RUN MUST NOT PAY TWICE (2026-09-05).
        ("nothing is reasoned twice", audit.check_nothing_is_reasoned_twice),
        # THE SECOND FORECASTER'S PROSE (2026-09-05). The plain-words scan ran
        # on the page and Picks opens on the statistical forecaster, so this
        # surface had never been read by any guard.
        ("no code name in the LLM view",
         lambda: audit.check_no_code_names_in_llm_prose(_record_conn())),
        # ENCODED FACTORS GO TO THE MODEL IN WORDS (2026-09-05).
        ("an indicator is handed over in words", audit.check_indicators_are_words),
        ("the outlook counts in one unit", audit.check_the_horizon_counts_in_one_unit),
        ("the record precedes the run", audit.check_a_run_is_recorded_before_it_runs),
        ("two control rows above the hero, no more",
         audit.check_picks_has_two_control_rows),
        ("hidden means not painted", audit.check_hidden_is_not_painted),
        ("one answer per question asked", audit.check_a_superseded_answer_is_dropped),
        ("the health panel speaks in words",
         lambda: audit.check_health_speaks_plain(_record_conn())),
        ("the reasoning pass runs on game markets only",
         audit.check_llm_runs_on_game_markets_only),
        ("the shortlist orders questions and does not tip",
         lambda: [audit.check_the_shortlist_speaks_of_questions(
             _slate_payload(sport)) for sport in _config().SPORTS] and None),
        ("the edge moves no ordering its market has not earned",
         lambda: audit.check_the_edge_moves_no_ungated_ordering(_record_conn())),
        ("at the line, a forecast and never advice",
         lambda: audit.check_the_at_the_line_words_are_a_forecast(
             _at_the_line_payload())),
        ("no quoted reasoning recommends a side",
         lambda: audit.check_no_quoted_prose_recommends(_record_conn())),
        ("no retired market was asked after its day",
         lambda: audit.check_no_retired_market_written(_record_conn())),
        ("no retired market is a tab on Picks", audit.check_no_retired_market_in_picks),
        ("the record matches its fingerprint (LAW 3)",
         lambda: audit.check_record_fingerprint(_record_conn())),
        ("no confidence floor on game markets",
         audit.check_no_floor_on_game_markets),
        ("vendored fonts match their provenance", audit.check_vendored_fonts),
        ("every self-chosen rung is flagged", audit.check_flagged_methods),
        ("one door for the side", audit.check_side_named),
        ("no shadowed definitions", audit.check_no_shadowed_definitions),
        ("the side, in prose, anywhere", audit.check_side_named_everywhere),
        ("the renderer composes no prose", audit.check_js_composes_no_prose),
        ("the correction sees claims only", audit.check_correction_is_isolated),
        ("the second look is a second look", audit.check_the_second_look_is_fresh),
        ("no rankings in college football", audit.check_no_rankings),
        ("the rung is chosen against the margin",
         audit.check_the_rung_is_chosen_by_margin),
        ("no tile truncates", audit.check_no_truncation_in_the_frame),
        ("selecting leaves the frame alone",
         audit.check_selection_leaves_the_frame_alone),
        ("every side has words", audit.check_every_side_has_words),
        ("one motion vocabulary", audit.check_motion_vocabulary),
        ("the live mark states no opinion",
         audit.check_the_live_mark_is_not_an_opinion),
        ("a score arriving does not move the slate",
         audit.check_a_live_update_does_not_reorder),
        ("green means a pick won, and nothing else",
         audit.check_the_colour_law),
        # THE GRAMMAR, NOT THE PRESSURE (CARD_FACE, 2026-09-07)
        ("no price moves when it changes", audit.check_no_price_animation),
        ("the day says nothing that tells a reader to hurry",
         lambda: [audit.check_the_day_applies_no_pressure(_slate_payload(sport))
                  for sport in _config().SPORTS] and None),
        ("kickoff is a time, not a timer", audit.check_no_countdown),
        # THREE STATES (2026-09-08)
        ("no club mark is stored", audit.check_no_marks),
        ("nothing on a live card can be acted on",
         lambda: [audit.check_the_live_card_offers_nothing(_slate_payload(sport))
                  for sport in _config().SPORTS] and None),
        ("one definition per function, in the renderer too",
         audit.check_no_duplicate_js_definitions),
        ("picks shows tonight, not last night",
         audit.check_picks_shows_tonight),
        ("every gate counts, and none renders a share",
         lambda: audit.check_progress_is_counted(
             audit.PROGRESS_FIXTURE_GOOD)),
        ("the withdrawn feature left nothing behind",
         audit.check_the_calls_feature_stayed_withdrawn),
        ("two tabs and a menu, and every old address lands",
         audit.check_the_nav_is_four_pages),
        # THE BOARD (GRIDIRON_BOARD, 2026-09-24): a signal never renders
        # without its badge, a club's colour is never typed, and every word
        # on a row, a tile or a tooltip is one a reader may meet.
        ("a signal carries its badge",
         lambda: [audit.check_the_board_signals_carry_their_badges(_slate_payload(sport))
                  for sport in config.SPORTS]),
        ("no club colour is typed", audit.check_no_hand_typed_club_hex),
        ("the board speaks plain, tooltips included",
         lambda: [audit.check_the_board_speaks_plain(_slate_payload(sport))
                  for sport in config.SPORTS]),
        ("a market source stays in the market module",
         audit.check_market_sources_stay_in_the_market_module),
        ("every docstring naming a guard names a real one",
         audit.check_docstrings_name_real_guards),
        ("the launcher refuses to attach to another build",
         audit.check_the_launcher_refuses_a_stale_attach),
        ("no selector asks for a class nothing builds",
         audit.check_no_dead_selectors),
        ("the tier Picks opens on says what it filtered",
         lambda: audit.check_the_default_never_hides_the_count(
             _record_conn())),
        ("every run line agrees with its own price",
         lambda: audit.check_run_line_signs(_record_conn(), "mlb")),
        ("forecasters are never merged",
         lambda: audit.check_forecasters_are_never_merged(
             views.scorecard(_record_conn(), _config().SPORTS[0]))),
        ("no silent defaults (v2)", audit.check_no_silent_defaults),
        # LAW 5 as amended 2026-09-07. The staking scan is retired; these
        # three are what it was really protecting, and they are not amendable.
        ("no venue credential anywhere (LAW 5)",
         lambda: audit.check_no_venue_credentials(
             env_file=_env_file(), conn=_record_conn())),
        ("no order path (LAW 5)", audit.check_no_order_path),
        ("the taken picks are not a ledger (LAW 5)",
         lambda: audit.check_taken_is_not_a_ledger(_record_conn())),
        ("nothing that trains the model reads the taken picks",
         audit.check_taken_not_in_training),
        ("no wagering ledger in the repo (LAW 5)",
         lambda: audit.check_no_wagering_ledger(conn=_record_conn())),
        ("no offline data caching", audit.check_no_offline_data_caching),
        # RULING 1 (2026-09-09). Five NFL prop markets had no venue series at
        # all, so every card in them said "no price yet" from the day they
        # were first forecast, and the gate was green throughout. Nothing
        # here compared what the record FORECASTS against what it can PRICE.
        ("every forecast market can reach the venue",
         audit.check_every_forecast_market_can_reach_the_venue),
        # GRIDIRON_OPENING_READ (2026-09-09). The opening read prices nothing;
        # this is what makes that a fact about the record rather than a
        # promise about the code.
        ("a claim is priced at the line, never at the open",
         lambda: audit.check_claims_price_at_the_line(_record_conn())),
        # THE LIVE RULINGS (2026-09-09). A page that stops asking the first
        # time nothing is on never learns the day started -- which is how the
        # server came to hold six live cards while the screen said nothing was
        # being played.
        ("the live poll keeps asking, and never asks for a price",
         audit.check_the_live_poll_keeps_asking),
        # OPERATOR RULING 1 (2026-09-24). A withdrawn recommendation is never
        # counted: every reader of the table goes through the one door, and
        # the live record's closing line is recounted without it, per sport.
        # The record holds no `recommendation_voids` until this merges, which
        # is why it is recounted on the migrated copy and not the record.
        ("every reader of a recommendation goes through the door",
         audit.check_every_recommendation_reader_uses_the_door),
        ("no withdrawn recommendation is counted",
         lambda: [audit.check_no_withdrawn_recommendation_counted(
             _record_conn(), sport=sport) for sport in _config().SPORTS]),
    ):
        try:
            fn()
            print(f"  PASS  {name}")
        # A CHECK THAT REACHES FOR THE LIVE RECORD FAILS BY NAME (2026-09-24),
        # and so does one with no record to read, rather than ending the gate.
        except (audit.LawViolation, db.LiveRecordTouched,
                NoRecordToCopy) as exc:
            ok = False
            print(f"  FAIL  {name}: {str(exc).splitlines()[0]}")
    _close_the_record_handles()
    return ok


def step_3_one_week_end_to_end(source: Path) -> bool:
    rule("STEP 3 — one complete week, end to end (retrospective; resolution works)")

    # FROM THE GATE'S COPY, NEVER THE RECORD (operator ruling, 2026-09-24).
    # `copy_facts` ATTACHes its source, and an attached file is writable from
    # the attaching connection whatever it is used for; until this date the
    # source was the operator's record, on every run. `copy_facts` now refuses
    # the record under verification by name, so this is not optional.
    if db._is_the_live_record(source):
        source = _gate_copy_path()
        print("facts copied from the gate's copy of the live record, "
              "not from the record")

    sport = "nfl"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        target = Path(tmp) / "one-week.db"
        conn = db.open_db(target)
        copy_facts(conn, source)
        db.set_meta(conn, "kind", "backtest")
        db.set_meta(conn, "kind_note", "single-week end-to-end verification run")
        store.sync_registry(conn)

        # SPORT-SCOPED. This step verifies one NFL week, and without the filter
        # it took MAX(week) across every sport - which is a BASEBALL DAY NUMBER,
        # 155 and climbing. It selected a week no football game has ever been
        # played in, wrote zero predictions, and reported that as a failure of
        # the pipeline rather than of the query. LAW 6 is about reading the
        # record, but the same confusion reaches anything that mixes the sports'
        # week keys.
        last = conn.execute(
            "SELECT season, MAX(week) AS week FROM games"
            " WHERE sport = ? AND status = 'final' AND game_type = 'REG'"
            " AND season = (SELECT MAX(season) FROM games"
            "               WHERE sport = ? AND status = 'final')",
            (sport, sport),
        ).fetchone()
        season, week = last["season"], last["week"]
        print(f"target: {season} week {week} (the most recent completed regular-season week)")

        started = time.time()
        # THIS PIPELINE TRAINS ITS OWN FITS, strictly before the season it
        # predicts, on a scratch copy. A hold (config.HELD_MARKETS) is about
        # the LIVE record's fits and does not bind a scratch pipeline.
        from gridiron import config as _config
        _config.HELD_MARKETS = {}
        fits = baseline.train_all(
            conn, tuple(range(2016, season)),
            note=f"verification fit, strictly before {season}",
        )
        for market_type, fit in sorted(fits.items()):
            print(f"  fit {market_type:22s} n={fit.n:>6,}, trained on "
                  f"2016-{season - 1} only")

        result = run.run_week(conn, season, week, include_props=True, use_llm=False)
        print(f"  predictions written blind: {result['written']}  {result['by_predictor']}")
        print(f"  market snapshots attached AFTER: {result['snapshots']}")

        ordering_violations = conn.execute(
            "SELECT COUNT(*) FROM predictions p JOIN market_snapshots s"
            " ON s.prediction_id = p.id WHERE s.fetched_utc < p.created_utc"
        ).fetchone()[0]
        print(f"  snapshots timestamped before their prediction: {ordering_violations}")

        settled = resolve.resolve_all(conn)
        print(f"  resolved: {settled['settled']}  voided: {settled['voided']}"
              f"  still open: {settled['still_open']}")
        again = resolve.resolve_all(conn)
        print(f"  second resolution pass settled: {again['settled']} (must be 0)")

        print(f"  [{time.time() - started:.0f}s]")
        print()
        ok = True
        # LAW 6: every read of the record names its sport. This step verifies
        # one NFL week, so it asks NFL. It was written before LAW 6 existed and
        # sat broken behind an earlier failure, which is its own small lesson
        # about what an unrun verifier is worth.
        markets = [("spread", None)] + [("prop", m) for m in config.PROP_MARKETS]
        for market_type, prop_type in markets:
            curve = calibration.curve(conn, sport=sport, market_type=market_type,
                                      prop_type=prop_type, predictor="statistical")
            name = prop_type or market_type
            print(f"  {name} / statistical  n={curve['n']}, {curve['voided']} void")
            for bucket in curve["buckets"]:
                if bucket["n"]:
                    print(f"     {bucket['label']:>7s} n={bucket['n']:>3}  "
                          f"claimed {bucket['claimed']:.3f}  actual {bucket['actual']:.3f}"
                          f"  {'(provisional)' if bucket['provisional'] else ''}")
                else:
                    print(f"     {bucket['label']:>7s} n=0")
            print(f"     {curve['largest_gap']}")

        payload = calibration.scorecard(conn, sport=sport)
        calibration.assert_every_figure_has_n(payload)
        print("\n  scorecard passed the LAW 4 validator: every figure carries its N")
        edge = payload["edge"]
        print(f"  edge question: {edge.get('message', 'rendered')}")

        ok = ok and ordering_violations == 0 and settled["settled"] > 0 and again["settled"] == 0
        # Close before the TemporaryDirectory unwinds: Windows will not delete a
        # file that still has an open handle, and the cleanup error would mask
        # the result of the step.
        conn.close()
        return ok


def step_4_live_forward_week() -> bool:
    rule("STEP 4 — the live forward week (the only thing that could be evidence)")
    if not config.DB_PATH.exists():
        print(f"no live database at {config.DB_PATH}")
        return False

    # READ-ONLY, FROM 2026-09-08. This step only asks the record questions --
    # which weeks were written, when, and against which kickoffs -- and
    # `open_db` would have run a migration on the operator's own file to do
    # it. The gate does not need write access to report what the record says.
    conn = db.read_the_live_record(
        "the forward weeks on the live record, which is the only thing in this "
        "project that could ever become evidence of an edge")
    kind = db.database_kind(conn)
    print(f"database: {config.DB_PATH}  (kind={kind['kind']})")

    # GROUPED BY SPORT, and VOIDED ROWS EXCLUDED. Both matter and both were
    # wrong. Without the sport, NFL week 1 and NBA week 1 were added together
    # and reported as one slate of 151 predictions - the same cross-sport week
    # confusion that made step 3 target a baseball day number. And a voided
    # prediction is not part of the record: the six MLB rows written after first
    # pitch were voided FOR that reason, and counting them made the blind-first
    # check fail on predictions that had already been removed for failing it.
    rows = conn.execute(
        "SELECT g.sport, g.season, g.week, COUNT(*) AS n,"
        " MIN(p.created_utc) AS written, MIN(g.kickoff_utc) AS first_kickoff,"
        " SUM(CASE WHEN p.resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved,"
        " SUM(CASE WHEN g.status = 'final' THEN 1 ELSE 0 END) AS played"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)"
        " GROUP BY g.sport, g.season, g.week"
        " ORDER BY g.sport, g.season DESC, g.week DESC"
    ).fetchall()
    if not rows:
        print("no forward predictions on record")
        conn.close()
        return False

    ok = True
    for r in rows:
        snapshots = conn.execute(
            "SELECT COUNT(*) FROM market_snapshots s JOIN predictions p"
            " ON p.id = s.prediction_id JOIN games g ON g.id = p.game_id"
            " WHERE g.sport = ? AND g.season = ? AND g.week = ?",
            (r["sport"], r["season"], r["week"]),
        ).fetchone()[0]
        blind_ok = r["written"] < r["first_kickoff"] if r["first_kickoff"] else None
        print(f"\n  {r['season']} week {r['week']}: {r['n']} predictions")
        print(f"    written        {r['written']}")
        print(f"    first kickoff  {r['first_kickoff']}")
        print(f"    written before kickoff: {blind_ok}")
        print(f"    market snapshots attached: {snapshots}")
        print(f"    games played: {r['played']} of {r['n']}   resolved: {r['resolved']}")
        if blind_ok is False:
            ok = False

    print(
        "\n  Predictions on unplayed games cannot be resolved, so this week's"
        "\n  calibration N is zero and stays zero until the games happen. That is"
        "\n  the honest state of the record, not a gap to be filled with step 3's"
        "\n  numbers. Run `python -m gridiron.cli resolve` after the games."
    )
    conn.close()
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the G6 verification")
    parser.add_argument("--quick", action="store_true",
                        help="skip browser and slow tests in step 1")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument(
        "--parallel", type=int, default=0, metavar="N",
        help="OPT-IN: run the suite across N processes with pytest-xdist. Not "
             "the default -- the suite takes about three minutes serially, and "
             "parallel workers cost deterministic ordering and easy "
             "reproduction. Use it on a slow machine; reproduce failures "
             "without it.")
    parser.add_argument("--source", default=str(config.DEFAULT_DB))
    args = parser.parse_args()

    # THE WHOLE RUN IS VERIFICATION (operator ruling, 2026-09-24). With this
    # set, `db.connect` refuses the live record by name and `copy_facts`
    # refuses to attach it, in this process and in the suite and the planting
    # harness it starts, which inherit the environment. Every read of the
    # record goes through `db.read_the_live_record`, which opens it read-only.
    # Set BEFORE the first step and before the record's schema is read, so
    # nothing below runs without it.
    if not os.environ.get("GRIDIRON_VERIFYING"):
        os.environ["GRIDIRON_VERIFYING"] = "tools/verify.py"
    found = _the_live_schema()

    outcomes: dict[str, bool] = {}
    # EVERY WAY A TIER CAN GO UNRUN IS COLLECTED HERE. Each of these used to be
    # a line of prose in the middle of the output and nothing at all in the
    # verdict, so the summary could print four PASSes after skipping the whole
    # browser suite -- true about far less than it appeared to be.
    skipped: list[str] = []
    try:
        if args.skip_tests:
            skipped.append("tests")
        else:
            passed, tier_skips = step_1_tests(args.quick, args.parallel)
            outcomes["1. test suite"] = passed
            skipped.extend(tier_skips)
        outcomes["2. planted violations"] = _refused_by_name(step_2_guards)

        source = Path(args.source)
        if source.exists():
            outcomes["3. one week end to end"] = _refused_by_name(
                step_3_one_week_end_to_end, source)
        else:
            # chr(10) rather than a backslash-n: this file has now lost that
            # escape in transit twice, and the second time it produced an
            # unterminated f-string three hundred lines from where it was typed.
            print(chr(10) + f"no database at {source}; skipping steps 3 and 4")
            skipped.append("end to end")

        outcomes["4. live forward week"] = _refused_by_name(
            step_4_live_forward_week)
    finally:
        # Even when a step ends in a traceback: the copy is a gigabyte in the
        # temp directory, and whether the record changed is still worth
        # saying on the way out.
        _drop_the_gate_copy()
        outcomes["the live record, as the gate found it"] = (
            the_record_is_as_found(found))

    rule("VERIFICATION SUMMARY")
    code, lines = summarise(outcomes, skipped)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
