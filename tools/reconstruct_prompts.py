"""Write a reconstructed prompt record for every reasoning forecast that has
none -- the ruling on question 4, 2026-09-25.

    # a scratch database (the gate's copy, a backup): write its records
    python tools/reconstruct_prompts.py --database PATH

    # the live record, AFTER the release that ships the prompt record
    python tools/reconstruct_prompts.py --database var/gridiron.db --live

THE OPERATOR'S WORDS: "Every reasoning row written before the release
(including ids 2358-2441 and any written before item 4 ships) gets a prompt
record rebuilt from its stored inputs through the prompt code as it stood at
that row's run time, stored append-only with kind = "reconstructed", the
code version used, and the reconstruction date. It is never presented as the
prompt sent."

HOW, PER FORECAST:
  * THE CODE AS IT STOOD. The commit is the main checkout's HEAD at the
    forecast's `created_utc`, read from that checkout's own reflog -- the
    latest entry at or before the minute -- because the scheduler runs the
    main checkout. The full commit id is stored on the record, and the time
    the checkout moved to it is in the record's words: a reflog is local and
    expires, the record does not.
  * BUILT BY THAT CODE. The commit's `gridiron` package is taken out of git
    with `git archive` into a scratch directory, and a child process
    (`tools/reconstruct_prompts_child.py`) imports THAT package -- asserting
    it did -- and rebuilds the prompt from the forecast's own stored factors
    through that tree's `describe` and `build_prompt`. The child reads no
    settings file and carries no GRIDIRON_ setting and no model key. The
    request is the model the forecast recorded, that tree's output cap, its
    system prompt and the rebuilt message, stored as canonical JSON with its
    SHA-256 through the one door (`model.prompt_record.keep_reconstructed`).
  * WHAT THE COMMIT CANNOT VOUCH FOR is written in words beside it: until
    about 22:47Z on 23 September the scheduler ran the main checkout's working
    tree, uncommitted edits and all; a forecast no scheduled task run
    encloses says so; and a number stored exactly halfway at its fourth
    decimal place, which the prompt showed rounded from more places than the
    record keeps, is named.

APPEND-ONLY AND IDEMPOTENT. Only a reasoning forecast with no record at all,
written before the release instant, is rebuilt; the schema refuses a
reconstructed record for any other. Run twice, the second run writes
nothing.

WRITES NOTHING ELSE: no migration, no `db.init`, no other table. A database
that has not been opened under the schema that ships the rule has no release
instant and no table to write, and is refused.

REFUSED ON THE LIVE RECORD without `--live`, and the live record is known by
the FILE'S IDENTITY -- the same file, however it is spelled, through a
junction, or by a hard link -- against every place it may be: this
checkout's configured record and its default, the main checkout's, and this
repository's own `var`. Never by comparing one configured path, which a
different setting or spelling walks straight past.

The gate runs `reconstruct` on its own migrated copy of the record WHILE THE
RECORD HAS NO RELEASE INSTANT, so the check that every reasoning forecast has
a record reads the state the live record will have once this tool has run
after the release; from the release on, the gate checks the record's own
records as they stand and names every forecast this tool has not reached
(tools/verify.py, 2026-09-25).

WHAT IT PRINTS (2026-09-25, after the rehearsal): for each commit, the
forecasts rebuilt through it and how many carry each caveat; any forecast it
rebuilt whose fingerprint was taken at or after the release instant, which
was committed after the release whatever its own date says, or that has no
fingerprint at all (above the record's fingerprint baseline); and, last, how
many of the database's reasoning forecasts carry a record after the run, of
each kind, and which carry none.
"""

from __future__ import annotations

import argparse
import bisect
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import config, db, language  # noqa: E402
from gridiron.model import prompt_record  # noqa: E402

CHILD = Path(__file__).resolve().with_name("reconstruct_prompts_child.py")


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED: " + why)
        super().__init__(2)


class ReconstructionFailed(RuntimeError):
    """The code of a commit could not be reached, so nothing was rebuilt."""


# ---------------------------------------------------------------------------
# which file is the live record
# ---------------------------------------------------------------------------

def _git(*args: str, cwd: Path = REPO) -> bytes:
    try:
        done = subprocess.run(["git", "-C", str(cwd), *args],
                              capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReconstructionFailed(f"git {' '.join(args)} did not run: {exc}")
    if done.returncode != 0:
        raise ReconstructionFailed(
            f"git {' '.join(args)} failed: "
            + done.stderr.decode("utf-8", "replace").strip()[:300])
    return done.stdout


def main_checkout() -> Path:
    """The main working tree of this repository -- the checkout the scheduler
    runs -- from git's own list, whichever worktree this runs from."""
    for line in _git("worktree", "list", "--porcelain").decode(
            "utf-8", "replace").splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree "):].strip())
    raise ReconstructionFailed("git lists no main worktree")


def live_record_candidates() -> list[Path]:
    """Every place the operator's record may be reached from here."""
    places = [Path(config.DB_PATH), Path(config.DEFAULT_DB),
              REPO / "var" / "gridiron.db"]
    try:
        places.append(main_checkout() / "var" / "gridiron.db")
    except ReconstructionFailed:
        pass
    return places


def is_the_live_record(path: Path) -> bool:
    """Is `path` the operator's record? BY THE FILE'S IDENTITY: the same file
    on the same volume, whatever the spelling, junction or link."""
    path = Path(path)
    if not path.exists():
        return False
    for candidate in live_record_candidates():
        try:
            if candidate.exists() and os.path.samefile(path, candidate):
                return True
        except OSError:
            continue
    return False


# ---------------------------------------------------------------------------
# the code as it stood
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReflogEntry:
    utc: datetime
    commit: str
    what: str


def reflog(checkout: Path | None = None) -> list[ReflogEntry]:
    """The main checkout's HEAD reflog, oldest first: when HEAD moved, to
    which commit, and why."""
    checkout = checkout or main_checkout()
    out = _git("reflog", "show", "--date=unix", "--format=%H %gd %gs", "HEAD",
               cwd=checkout).decode("utf-8", "replace")
    entries = []
    for line in out.splitlines():
        commit, _, rest = line.partition(" ")
        selector, _, what = rest.partition(" ")
        stamp = selector[selector.find("{") + 1:selector.find("}")]
        if len(commit) != 40 or not stamp.isdigit():
            continue
        entries.append(ReflogEntry(
            datetime.fromtimestamp(int(stamp), tz=timezone.utc), commit, what))
    entries.sort(key=lambda e: e.utc)
    return entries


def _utc(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def commit_at(entries: list[ReflogEntry], created_utc: str) -> ReflogEntry | None:
    """The checkout's HEAD at a forecast's minute: the latest reflog entry at
    or before it. None before the reflog begins."""
    times = [e.utc for e in entries]
    i = bisect.bisect_right(times, _utc(created_utc)) - 1
    return entries[i] if i >= 0 else None


def _archive(commit: str, into: Path) -> Path:
    tree = into / commit[:12]
    if not (tree / "gridiron").exists():
        blob = _git("archive", "--format=tar", commit, "gridiron")
        tree.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:") as tar:
            tar.extractall(tree, filter="data")
    return tree


def _child_env() -> dict:
    """No setting, no key and no path of this process reaches the child."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GRIDIRON_") and k not in (
               "ANTHROPIC_API_KEY", "PYTHONPATH", "PYTHONHOME")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _build(tree: Path, rows: list[dict], scratch: Path) -> dict:
    out = scratch / f"built-{tree.name}.json"
    try:
        done = subprocess.run(
            [sys.executable, "-B", str(CHILD), str(tree), str(out)],
            input=json.dumps(rows), cwd=str(tree), env=_child_env(),
            capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReconstructionFailed(f"the child for {tree.name} did not run: {exc}")
    if done.returncode != 0 or not out.exists():
        tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or [""]
        raise ReconstructionFailed(
            f"the child for {tree.name} failed: {tail[0][:300]}")
    return json.loads(out.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------------

def _without_a_record(conn) -> list:
    """Every reasoning forecast with no prompt record at all, oldest first."""
    rows = conn.execute(
        "SELECT id, created_utc, sport, market_type, game_id, factors_json"
        "  FROM predictions WHERE predictor = 'llm' ORDER BY id").fetchall()
    have = prompt_record.records_for(conn, [r["id"] for r in rows])
    return [r for r in rows if r["id"] not in have]


def _enclosed_by_a_task_run(conn, created_utc: str, sport: str) -> bool:
    """Was a scheduled task that WRITES THIS SPORT'S FORECASTS running at the
    forecast's minute?

    ONLY THOSE TASKS, AND A RUN NEVER FINISHED ONLY UNTIL ITS TASK NEXT
    STARTED (2026-09-25, found by the rehearsal of item 4). Any task used to
    count, and a run never finished counted for ever: `live` polls every few
    minutes and `refresh` writes no forecast, and a `final:cfb` run begun at
    19:41Z on 9 September was still "running" on 25 September, so a forecast
    written by hand beside either would have been told a scheduled task wrote
    it. Measured the same day, no forecast on the record was affected."""
    return conn.execute(
        "SELECT 1 FROM task_runs t"
        " WHERE t.task IN (?, ?, 'catch-up') AND t.started_utc <= ?"
        "   AND (t.finished_utc >= ?"
        "        OR (t.finished_utc IS NULL AND NOT EXISTS ("
        "            SELECT 1 FROM task_runs n WHERE n.task = t.task"
        "               AND n.started_utc > t.started_utc"
        "               AND n.started_utc <= ?)))"
        " LIMIT 1",
        (f"predict:{sport}", f"final:{sport}", created_utc, created_utc,
         created_utc)).fetchone() is not None


def _the_call(conn, row, used: set[int]) -> int | None:
    """The ledger row of the call that answered this forecast: a successful
    reasoning call on the same game, made in the two seconds up to the
    forecast, and cited by no other record. None unless exactly one."""
    earliest = _stamp(_utc(row["created_utc"]) - timedelta(seconds=2))
    found = [c[0] for c in conn.execute(
        "SELECT id FROM llm_calls WHERE game_id = ? AND purpose = 'reasoning'"
        "   AND ok = 1 AND called_utc BETWEEN ? AND ? ORDER BY id",
        (row["game_id"], earliest, row["created_utc"]))
        if c[0] not in used]
    return found[0] if len(found) == 1 else None


def _plain(name: str) -> str:
    return language.humanise(name) if "_" in name else name


#: The caveats a reconstruction's words can carry, counted per commit in the
#: report so the run that writes the live record shows what it wrote.
CAVEAT_WORKING_TREE = "the scheduler also ran uncommitted edits"
CAVEAT_NO_TASK_RUN = "no scheduled task was running"
CAVEAT_UNCERTAIN_DIGIT = "a number exactly halfway at its fourth place"


#: What the report says of a forecast above the baseline with no fingerprint.
NO_FINGERPRINT = "no fingerprint at all"


def _fingerprinted_after(conn, ids, instant: str) -> dict[int, str]:
    """Of these forecasts, those whose fingerprint was taken at or after the
    release instant, or that have none: {forecast id: when, or
    NO_FINGERPRINT}. COMMITTED AFTER THE RELEASE whatever the forecast's own
    date says, or written round `write_prediction` altogether.

    Only above the record's fingerprint baseline, where `fingerprint.write`
    stamps the fingerprint on the forecast's own transaction; the rows at or
    below it were fingerprinted by a backfill, on a later day."""
    baseline = config.RECORD_BASELINE["rows"]
    ids = sorted(i for i in ids if i > baseline)
    out: dict[int, str] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        try:
            taken = {r[0]: r[1] for r in conn.execute(
                f"SELECT prediction_id, taken_utc FROM prediction_fingerprints"
                f" WHERE prediction_id IN ({','.join('?' * len(chunk))})", chunk)}
        except sqlite3.OperationalError:
            return {}
        for pid in chunk:
            if pid not in taken:
                out[pid] = NO_FINGERPRINT
            elif taken[pid] >= instant:
                out[pid] = taken[pid]
    return out


def _coverage(conn) -> tuple[int, Counter, list[int]]:
    """After a run: how many reasoning forecasts the database holds, how many
    carry a prompt record of each kind (read through the one reader), and
    which carry none."""
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM predictions WHERE predictor = 'llm' ORDER BY id")]
    have = prompt_record.records_for(conn, ids)
    return (len(ids), Counter(r["kind"] for r in have.values()),
            [i for i in ids if i not in have])


@dataclass
class Report:
    database: str
    binds_from: str | None = None
    considered: int = 0
    written: int = 0
    by_commit: dict = field(default_factory=lambda: defaultdict(list))
    caveats: dict = field(default_factory=lambda: defaultdict(Counter))
    by_sport: Counter = field(default_factory=Counter)
    after_the_release: list = field(default_factory=list)
    no_commit: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    committed_after: dict = field(default_factory=dict)
    forecasts: int = 0
    kinds: Counter = field(default_factory=Counter)
    without: list = field(default_factory=list)
    seconds: float = 0.0

    def lines(self) -> list[str]:
        out = [f"prompt reconstruction -- {self.database}",
               f"  the release instant: {self.binds_from}",
               f"  reasoning forecasts with no prompt record: {self.considered}",
               f"  reconstructed records written: {self.written}"]
        for commit, ids in self.by_commit.items():
            said = self.caveats.get(commit) or {}
            words = ", ".join(f"{n} {what}" for what, n in said.items() if n)
            out.append(f"    {commit[:12]}  {len(ids):>4} forecasts, ids "
                       f"{min(ids)}-{max(ids)}"
                       + (f"; the record says {words}" if words
                          else "; no caveat beyond the commit"))
        for sport, n in sorted(self.by_sport.items()):
            out.append(f"    {sport:>4}  {n:>4}")
        if self.committed_after:
            out.append(
                f"  REBUILT, BUT COMMITTED AFTER THE RELEASE INSTANT by their "
                f"fingerprints, or with no fingerprint at all, though dated "
                f"before it -- written round the door, or by old code racing "
                f"the release; read each before the record is trusted: "
                f"{sorted(self.committed_after.items())}")
        if self.after_the_release:
            out.append(f"  NOT REBUILT, written at or after the release "
                       f"instant, where a forecast carries the prompt it was "
                       f"sent: {self.after_the_release}")
        if self.no_commit:
            out.append(f"  NOT REBUILT, before the checkout's history begins: "
                       f"{self.no_commit}")
        for pid, why in self.failed:
            out.append(f"  NOT REBUILT, forecast {pid}: {why}")
        out.append(
            f"  after this run: {self.forecasts - len(self.without)} of "
            f"{self.forecasts} reasoning forecasts carry a prompt record "
            f"({self.kinds.get(prompt_record.KIND_SENT, 0)} sent, "
            f"{self.kinds.get(prompt_record.KIND_RECONSTRUCTED, 0)} "
            f"reconstructed)"
            + (f"; WITHOUT ONE: {self.without}" if self.without else ""))
        out.append(f"  {self.seconds:.1f}s")
        return out


def reconstruct(path: Path | str, *, live: bool = False,
                checkout: Path | None = None,
                entries: list[ReflogEntry] | None = None) -> Report:
    """Write the reconstructed records of one database. Refuses the live
    record unless `live`, and a database with no release instant.

    `entries` replaces the main checkout's reflog, for a test that has to
    name the commit itself; the tool never passes it."""
    path = Path(path)
    if not path.exists():
        raise Refused(f"there is no database at {path}")
    if is_the_live_record(path) and not live:
        raise Refused(
            f"{path} is the operator's record (the same file as the live "
            f"record, found by its identity). Its prompts are rebuilt only "
            f"with --live, after the release that ships the prompt record")
    if live and not is_the_live_record(path):
        raise Refused(f"--live names the operator's record, and {path} is not "
                      f"the same file as it")
    started = time.time()
    report = Report(database=str(path))
    # THROUGH `db.connect`, which refuses the live record under any
    # verification -- a test, a planting or the gate -- by name.
    conn = db.connect(path)
    try:
        report.binds_from = prompt_record.binds_from(conn)
        if report.binds_from is None:
            raise Refused(
                f"{path} has no release instant: it has not been opened under "
                f"the schema that ships the prompt record, so there is nothing "
                f"to rebuild against. This tool migrates nothing.")
        todo = _without_a_record(conn)
        report.considered = len(todo)
        if todo:
            _rebuild(conn, todo, report, checkout, entries)
        report.forecasts, report.kinds, report.without = _coverage(conn)
    finally:
        conn.close()
    report.seconds = time.time() - started
    return report


def _rebuild(conn, todo: list, report: Report, checkout: Path | None,
             entries: list[ReflogEntry] | None) -> None:
    """Rebuild every forecast in `todo` written before the release instant,
    through the code of the commit it ran under, into `report`."""
    entries = entries if entries is not None else reflog(checkout)
    groups: dict[str, list] = defaultdict(list)
    moved: dict[int, ReflogEntry] = {}
    for row in todo:
        if row["created_utc"] >= report.binds_from:
            report.after_the_release.append(row["id"])
            continue
        entry = commit_at(entries, row["created_utc"])
        if entry is None:
            report.no_commit.append(row["id"])
            continue
        groups[entry.commit].append(row)
        moved[row["id"]] = entry
    late = _fingerprinted_after(
        conn, [r["id"] for rows in groups.values() for r in rows],
        report.binds_from)
    used = {r[0] for r in conn.execute(
        "SELECT llm_call_id FROM reasoning_prompts"
        " WHERE llm_call_id IS NOT NULL")}
    scratch = Path(tempfile.mkdtemp(prefix="gridiron-reconstruct-"))
    try:
        for commit, rows in groups.items():
            tree = _archive(commit, scratch)
            built = _build(tree, [
                {"id": r["id"], "factors_json": r["factors_json"]}
                for r in rows], scratch)
            by_id = {b["id"]: b for b in built["rows"]}
            when = _stamp(datetime.now(timezone.utc))
            for row in rows:
                got = by_id.get(row["id"]) or {"error": "the child skipped it"}
                if got.get("error"):
                    report.failed.append((row["id"], got["error"]))
                    continue
                stored = json.loads(row["factors_json"])
                request = {
                    "model": stored.get("llm_model") or built["model"],
                    "max_tokens": built["max_tokens"],
                    "system": built["system"],
                    "messages": [{"role": "user", "content": got["prompt"]}],
                }
                entry = moved[row["id"]]
                working_tree = row["created_utc"] < prompt_record.WORKING_TREE_UNTIL
                no_task_run = not _enclosed_by_a_task_run(
                    conn, row["created_utc"], row["sport"])
                uncertain = [_plain(n) for n in got["uncertain"]]
                words = language.reconstruction_provenance(
                    commit_utc=_stamp(entry.utc),
                    before_merged_only=working_tree,
                    no_task_run=no_task_run, uncertain=uncertain)
                call = _the_call(conn, row, used)
                try:
                    prompt_record.keep_reconstructed(
                        conn, prediction_id=row["id"], game_id=row["game_id"],
                        claim=stored["question"]["claim"],
                        request_json=prompt_record.canonical(request),
                        code_version=commit, provenance=words,
                        reconstructed_utc=when, llm_call_id=call)
                except Exception as exc:  # noqa: BLE001 - named per row
                    conn.rollback()
                    report.failed.append((row["id"], f"{type(exc).__name__}: {exc}"))
                    continue
                conn.commit()
                if call is not None:
                    used.add(call)
                report.written += 1
                report.by_commit[commit].append(row["id"])
                report.by_sport[row["sport"]] += 1
                said = report.caveats[commit]
                said[CAVEAT_WORKING_TREE] += working_tree
                said[CAVEAT_NO_TASK_RUN] += no_task_run
                said[CAVEAT_UNCERTAIN_DIGIT] += bool(uncertain)
                if row["id"] in late:
                    report.committed_after[row["id"]] = late[row["id"]]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The ruling on question 4: a reconstructed prompt record "
                    "for every reasoning forecast written before the release")
    parser.add_argument("--database", required=True,
                        help="the database whose forecasts are rebuilt")
    parser.add_argument("--live", action="store_true",
                        help="the database is the operator's record, and this "
                             "is the run that writes to it")
    args = parser.parse_args(argv)
    report = reconstruct(Path(args.database), live=args.live)
    for line in report.lines():
        print(line)
    # NOT A CLEAN RUN while any reasoning forecast is left without a record,
    # or one was rebuilt that its fingerprint says was committed after the
    # release (2026-09-25): the operator reads the lines above either way.
    return 1 if (report.failed or report.no_commit or report.without
                 or report.committed_after) else 0


if __name__ == "__main__":
    raise SystemExit(main())
