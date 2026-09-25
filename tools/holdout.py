"""Measure a candidate fit against a market's incumbent on a holdout season,
and -- only if it wins under the tie rule -- activate it.

    python tools/holdout.py --sport nfl --market spread --candidate 91 \\
        --through 2024 --score 2025
    python tools/holdout.py ... --activate --reason "why, in words"

THE ACTIVATION GATE (operator rulings of 2026-09-24). A fit is written
inactive, and it becomes a market's model only by a dated activation carrying
its holdout against the incumbent. Ties go to the incumbent: the candidate is
activated only if the paired bootstrap 95% interval of (candidate - incumbent)
log loss lies wholly below zero.

THE MEASUREMENT MIRRORS THE ONE MADE ON 24 SEPTEMBER (fs5 against the sets it
replaced, on a scratch copy, no network): both factor sets are REFIT on the
same games through season N-1 and scored on season N, so neither fit is
scored on rows it was trained on. Each set is the one its stored fit was
trained with -- its coefficients, plus any factor it reported constant or
dropped -- and the registry is flipped to that set IN THIS PROCESS ONLY. If
the registry cannot reproduce a stored set, the tool refuses rather than
measuring something else under its name.

WHAT IT WRITES. Nothing, unless `--activate` is given and the candidate won.
The measurement reads a scratch copy of the record, backed up through
`db.read_the_live_record` into the temp directory (or `--scratch`, a copy
made earlier). Refits are made with `logistic.fit` directly, never with
`baseline.train`, which would insert into `model_fits`. The one write this
tool can make to the live record is the activation row, through the door
(`activation.activate_measured`), and the schema's triggers decide it.

`--record FILE` (2026-09-24, the fs5 revert) also writes the measurement,
whole, into a JSON file under the market's key -- a file, never the record.
It is how a measurement reaches code without anybody typing its numbers:
the revert's incumbent activations carry exactly what this measured
(`gridiron/model/fs5_revert_holdout.json`).

GAME MARKETS ONLY, for now: a prop market has many rows per game and a count
market is a rate rather than a logistic, and pairing either needs a key this
tool does not build. It says so rather than measuring them badly.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import math
import random
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import config, db  # noqa: E402

#: The 24 September measurement's bootstrap, kept so a rerun reproduces it.
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 20260923


class HoldoutRefused(RuntimeError):
    """The measurement could not be made honestly, so it was not made."""


def paired_bootstrap(diffs: list[float], draws: int = BOOTSTRAP_DRAWS,
                     seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    """The 95% percentile interval of the mean of per-row differences,
    resampling ROWS so each draw keeps a game's two scores together."""
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(draws))
    return means[int(0.025 * draws)], means[int(0.975 * draws) - 1]


def beats_the_incumbent(interval: tuple[float, float]) -> bool:
    """THE TIE RULE, as the schema's trigger states it: the upper bound of
    (candidate - incumbent) log loss is below zero. Printed here so the
    verdict is read before anything is asked of the record."""
    return interval[1] < 0


def _row_log_loss(p: float, y: int, eps: float = 1e-12) -> float:
    p = min(max(p, eps), 1 - eps)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def _stored_set(conn, fit_id: int) -> tuple[dict, set[str]]:
    import json

    row = conn.execute(
        "SELECT id, sport, market_type, factor_set_version, fitted_utc,"
        " train_through, coefficients_json FROM model_fits WHERE id = ?",
        (fit_id,)).fetchone()
    if row is None:
        raise HoldoutRefused(f"there is no fit {fit_id} on the record")
    blob = json.loads(row["coefficients_json"])
    names = (set(blob.get("coefficients") or {}) | set(blob.get("constant") or {})
             | set(blob.get("dropped") or {}))
    return dict(row), names


def _rows(conn, sport: str, market: str, seasons: tuple[int, ...], names: set[str]):
    """One factor set's rows for `seasons`, keyed by game, with the registry
    flipped to exactly `names` for the duration."""
    from gridiron import sports
    from gridiron.factors import compute, registry

    original = dict(registry.REGISTRY)
    seen: list[str] = []
    real_fv = compute.feature_vector

    def logged(ctx, market_type, market_name=None):
        seen.append(ctx.game_id)
        return real_fv(ctx, market_type, market_name)

    try:
        for name, factor in original.items():
            if factor.sport == sport and market in factor.applies_to:
                registry.REGISTRY[name] = dataclasses.replace(
                    factor, active=name in names)
        compute.feature_vector = logged
        rows, labels, built = sports.get(sport).training_set(conn, seasons, market)
    finally:
        compute.feature_vector = real_fv
        registry.REGISTRY.clear()
        registry.REGISTRY.update(original)
    if set(built) != names:
        raise HoldoutRefused(
            f"the registry cannot rebuild this factor set: the stored fit has "
            f"{sorted(names)} and the registry gives {sorted(built)}. Measuring "
            f"it would measure something else under its name.")
    if len(seen) != len(rows) or len(set(seen)) != len(seen):
        raise HoldoutRefused(
            f"{sport} {market} rows are not one per game ({len(rows)} rows, "
            f"{len(set(seen))} games), so the two sets cannot be paired")
    return dict(zip(seen, zip(rows, labels))), built


def measure(scratch, sport: str, market: str, candidate: int, incumbent: int,
            through: int, score: int) -> dict:
    """Refit both sets on identical games through `through`, score `score`."""
    from gridiron.model import baseline, counts, logistic

    if market in config.SPORT_PROP_MARKETS.get(sport, ()) or counts.is_count_market(market):
        raise HoldoutRefused(
            f"{sport} {market} is a prop or count market; this tool pairs one "
            f"row per game and measures game markets only")
    first = min(config.SPORT_LOAD_SEASONS[sport])
    train_seasons = tuple(range(first, through + 1))
    l2 = inspect.signature(baseline.train).parameters["l2"].default
    out = {"sport": sport, "market": market, "through": through,
           "score": score, "l2": l2, "sets": {}}
    data = {}
    for role, fit_id in (("candidate", candidate), ("incumbent", incumbent)):
        stored, names = _stored_set(scratch, fit_id)
        if (stored["sport"], stored["market_type"]) != (sport, market):
            raise HoldoutRefused(
                f"fit {fit_id} is {stored['sport']} {stored['market_type']}, "
                f"not {sport} {market}")
        train, built = _rows(scratch, sport, market, train_seasons, names)
        held, _ = _rows(scratch, sport, market, (score,), names)
        data[role] = (train, held, built)
        out["sets"][role] = {"fit_id": fit_id, "set": stored["factor_set_version"],
                             "fitted_utc": stored["fitted_utc"],
                             "factors": sorted(built)}

    def paired(part: int):
        a, b = data["candidate"][part], data["incumbent"][part]
        common = [g for g in a if g in b]
        if any(a[g][1] != b[g][1] for g in common):
            raise HoldoutRefused("the two sets disagree about an outcome")
        return common, a, b

    train_ids, a_tr, b_tr = paired(0)
    held_ids, a_ho, b_ho = paired(1)
    if not held_ids:
        raise HoldoutRefused(f"no {sport} {market} rows in {score} to score")
    labels = [a_ho[g][1] for g in held_ids]
    probs = {}
    for role, tr, ho in (("candidate", a_tr, a_ho), ("incumbent", b_tr, b_ho)):
        fit = logistic.fit([tr[g][0] for g in train_ids],
                           [tr[g][1] for g in train_ids],
                           data[role][2], l2=l2)
        p = [fit.predict(ho[g][0]) for g in held_ids]
        probs[role] = p
        out["sets"][role].update(
            n_train=len(train_ids), log_loss=logistic.log_loss(p, labels),
            brier=logistic.brier(p, labels))
    diffs = [_row_log_loss(c, y) - _row_log_loss(i, y) for c, i, y in
             zip(probs["candidate"], probs["incumbent"], labels)]
    out["n"] = len(held_ids)
    out["difference"] = sum(diffs) / len(diffs)
    out["interval"] = paired_bootstrap(diffs)
    out["beats"] = beats_the_incumbent(out["interval"])
    out["holdout"] = f"fit through {through}, scored on {score}"
    return out


def _scratch_copy(folder: Path) -> Path:
    # THROUGH THE BACKUP DOOR (schema ruling 6, 2026-09-24; 2026-09-25): the
    # same copy the gate makes, with no raw `sqlite3.connect` of its own.
    return db.back_up_the_live_record(
        folder / "record.db",
        "backing the record up into a scratch copy for a holdout measurement, "
        "which reads the copy and never the record")


def record_measurement(path: Path, result: dict, command: str) -> None:
    """Write one measurement into a JSON file, keyed 'sport:market'.

    MERGED, so four runs build one file; a market measured again replaces
    its own entry and no other. The file carries the command that made each
    entry and when, so a reader can run it again and compare.
    """
    import json

    from gridiron.db import utcnow

    path = Path(path)
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        existing = {}
    entry = dict(result)
    entry["interval"] = list(result["interval"])
    entry["measured_utc"] = utcnow()
    entry["command"] = command
    existing[f"{result['sport']}:{result['market']}"] = entry
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + chr(10),
                    encoding="utf-8")


def _refuse_the_network() -> None:
    """A holdout is measured on stored facts. A fetch would change them."""
    from gridiron.data import sources

    def refused(url, *args, **kwargs):
        raise RuntimeError(f"the holdout tool does not fetch: {url}")

    sources._http_get = refused


def main(argv=None) -> int:
    from gridiron.model import activation

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sport", required=True, choices=config.SPORTS)
    parser.add_argument("--market", required=True)
    parser.add_argument("--candidate", type=int, required=True,
                        help="the fit to measure, as stored on the record")
    parser.add_argument("--incumbent", type=int,
                        help="measure against this fit instead of the market's "
                             "active one; refused with --activate")
    parser.add_argument("--through", type=int, required=True,
                        help="refit both sets on seasons up to this one")
    parser.add_argument("--score", type=int, required=True,
                        help="the season held out and scored")
    parser.add_argument("--scratch", help="an existing scratch copy of the record")
    parser.add_argument("--record", help="also write the measurement into this "
                                         "JSON file, under the market's key")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--reason", default="")
    args = parser.parse_args(argv)
    if args.score <= args.through:
        raise SystemExit("the scored season must come after every season fitted")

    reader = db.read_the_live_record(
        "the market's active fit, which a candidate is measured against")
    try:
        active = activation.active_fit(reader, args.sport, args.market)
    finally:
        reader.close()
    incumbent = args.incumbent or (active["fit_id"] if active else None)
    if incumbent is None:
        print(f"{args.sport} {args.market} has no active fit, so there is no "
              f"incumbent to beat. Ties go to the incumbent and there is none: "
              f"activating a fit here waits for the operator's ruling.")
        return 2
    if args.activate and (active is None or incumbent != active["fit_id"]):
        raise SystemExit("--activate measures against the market's active fit "
                         "only; the schema refuses any other incumbent")

    _refuse_the_network()
    folder = None
    if args.scratch:
        path = Path(args.scratch)
        if db._is_the_live_record(path):
            raise SystemExit("--scratch is the live record; give it a copy")
    else:
        folder = Path(tempfile.mkdtemp(prefix="gridiron-holdout-"))
        path = _scratch_copy(folder)
    scratch = db.connect(path)
    try:
        result = measure(scratch, args.sport, args.market, args.candidate,
                         incumbent, args.through, args.score)
    finally:
        scratch.close()
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)

    if args.record:
        record_measurement(
            Path(args.record), result,
            "python tools/holdout.py " + " ".join(
                a for a in (argv if argv is not None else sys.argv[1:])
                if not a.startswith(("--scratch", "--record"))
                and a not in (args.scratch, args.record)))
    c, i = result["sets"]["candidate"], result["sets"]["incumbent"]
    low, high = result["interval"]
    print(f"{args.sport} {args.market}: {result['holdout']}, n={result['n']} "
          f"(both refit on the same {c['n_train']} games, l2={result['l2']})")
    for role, s in (("candidate", c), ("incumbent", i)):
        print(f"  {role:9s} fit {s['fit_id']:>4} {s['set']:9s} log loss "
              f"{s['log_loss']:.5f}  Brier {s['brier']:.5f}")
    print(f"  candidate - incumbent log loss {result['difference']:+.5f}, "
          f"95% interval [{low:+.5f}, {high:+.5f}]")
    if not result["beats"]:
        print("  TIE: the interval does not exclude zero, so the incumbent stays.")
        return 1 if args.activate else 0
    print("  The candidate beats the incumbent under the tie rule.")
    if not args.activate:
        return 0

    # THE ONE WRITE, through the door. Writable only here, only for this row.
    conn = db.connect(config.DB_PATH)
    try:
        written = activation.activate_measured(
            conn, args.candidate, incumbent_fit_id=incumbent,
            holdout=result["holdout"], holdout_n=result["n"],
            log_loss=c["log_loss"], brier=c["brier"],
            incumbent_log_loss=i["log_loss"], incumbent_brier=i["brier"],
            interval=result["interval"],
            reason=args.reason or "measured with tools/holdout.py")
    finally:
        conn.close()
    print(f"  activated: fit_activations row {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
