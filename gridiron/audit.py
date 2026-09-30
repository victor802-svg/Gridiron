"""Static enforcement of LAW 1: what the prediction path is able to reach.

The runtime sentinel in `gridiron.blind` catches a market import while a
prediction is being made. This is the other half, and the stronger one: it walks
the *transitive import closure* of the prediction module and fails if the market
package appears anywhere in it, or if any module in that closure so much as
names a market column.

It reads source, not a running process, so it catches the violation whether or
not the offending line ever executes. A lazily imported line inside a rarely
taken branch is still a line that can fetch a spread, and the guard should not
depend on the test suite happening to walk it.

Docstrings are excluded from the identifier scan. A module is allowed to explain
in prose that it must not touch the market — that is the point of the comment —
but it may not name `spread_line` in a string that could become SQL.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

PACKAGE = "gridiron"

#: The module the whole blind path hangs off.
PREDICTION_ENTRYPOINT = "gridiron.model.predict"


def prediction_entrypoints() -> dict[str, str]:
    """Every entrypoint the LAW 1 scan must walk, keyed by what it covers.

    Each sport is audited SEPARATELY rather than as one aggregate. A market
    import smuggled into baseball would otherwise hide inside a closure that
    football's cleanliness dominated, and the module counts would say nothing
    about where the problem was.
    """
    from . import sports

    return {"shared": PREDICTION_ENTRYPOINT, **sports.entrypoints()}

#: Packages the prediction closure may not contain.
#: Modules the prediction path may not reach, transitively.
#:
#: `gridiron.live` joined `gridiron.market` on 2026-09-01 (L1). The argument is
#: the same one LAW 1 makes about a line, only sharper: a market line is
#: somebody else's opinion about the game, and a live score is THE ANSWER. A
#: forecast that could see either is not a forecast, and the one that can see
#: the score is not even wrong -- it is just reading off the result.
FORBIDDEN_MODULES = ("gridiron.market", "gridiron.live")

#: THE ONE PACKAGE ALLOWED TO READ A PRICE (THE_PRICED P1, 2026-09-07).
#:
#: `gridiron.priced` is a second forecaster that runs after the blind row and
#: the snapshot exist, and reading the price is its entire purpose. It is
#: NAMED HERE rather than the rule being relaxed: every blind entrypoint is
#: still walked by name and still refuses `gridiron.market` and
#: `gridiron.live`, and `plant.py` re-proves that refusal immediately after
#: this exception exists, because a scan loosened one clause too far is the
#: most expensive silent failure this project could have.
#:
#: NOTHING IN THE BLIND CLOSURE MAY IMPORT IT EITHER. The exemption is not a
#: back door: `check_prediction_closure` refuses `gridiron.priced` inside a
#: blind closure exactly as it refuses the market package, because a blind
#: module that imported the priced one would be two steps from a price rather
#: than one.
CLOSURE_EXEMPT_PACKAGE = "gridiron.priced"

#: Identifiers and literal fragments that name market DATA.
#:
#: Two words are deliberately absent, and the distinction is the same one that
#: renamed `spread_line_asked` to `spread_rung` in G6 — our vocabulary must not
#: collide with the market's, and where it does, the more precise name wins:
#:
#:   * `market_type` is a column on `predictions` describing what kind of
#:     question was asked, not a price.
#:   * `moneyline` is the NAME of MLB's market — the question we ask — exactly
#:     as `spread` is the name of NFL's. The market's *price* is stored in the
#:     columns `home_moneyline` / `away_moneyline`, and those are forbidden. A
#:     prediction-path module can say which market it is forecasting; it cannot
#:     name the price of one.
FORBIDDEN_IDENTIFIERS = (
    "market_lines_raw",
    "market_snapshots",
    # THE VENUE'S QUOTES (ruling D3, 2026-09-06): a ladder of prices per
    # game, in the market module and nowhere near the prediction path.
    "venue_quotes",
    "yes_bid",
    "yes_ask",
    "last_price",
    "spread_line",
    "total_line",
    "home_moneyline",
    "away_moneyline",
    "implied_prob",
    "public_pct",
    # THE LIVE COLUMNS (L1). Prefixed `live_` in the schema precisely so they
    # can be named here without catching an ordinary variable: a column called
    # `period` or `clock` would collide with a dozen innocent locals and this
    # list would have to guess.
    "live_period",
    "live_clock",
    "live_updated_utc",
)


class LawViolation(AssertionError):
    """A law is broken in the source. The message names which and where."""


@dataclass
class ClosureReport:
    entrypoint: str
    modules: dict[str, Path] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def path_to(self, target: str) -> list[str]:
        """How the entrypoint reaches `target`, for the error message."""
        parents = {}
        for src, dst in self.edges:
            parents.setdefault(dst, src)
        if target not in parents and target != self.entrypoint:
            return []
        chain = [target]
        while chain[-1] != self.entrypoint:
            nxt = parents.get(chain[-1])
            if nxt is None or nxt in chain:
                break
            chain.append(nxt)
        return list(reversed(chain))


def module_path(module: str, root: Path | None = None) -> Path | None:
    relative = module.split(".")[1:]
    base = (root or config.PACKAGE_ROOT).joinpath(*relative)
    if base.with_suffix(".py").exists():
        return base.with_suffix(".py")
    if (base / "__init__.py").exists():
        return base / "__init__.py"
    return None


def _imports(tree: ast.AST, module: str) -> list[str]:
    """Intra-package modules imported by this one, absolute and relative."""
    package_parts = module.split(".")[:-1]
    found: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PACKAGE):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - node.level + 1]
                prefix = ".".join(base + ([node.module] if node.module else []))
            elif node.module and node.module.startswith(PACKAGE):
                prefix = node.module
            else:
                continue
            if not prefix.startswith(PACKAGE):
                continue
            found.append(prefix)
            # `from .market import lines` names the submodule in `names`.
            for alias in node.names:
                found.append(f"{prefix}.{alias.name}")
    return found


def import_closure(
    entrypoint: str = PREDICTION_ENTRYPOINT, root: Path | None = None
) -> ClosureReport:
    """Walk the closure under `root` (defaults to the installed package).

    The root override exists so a violation can be planted in a throwaway copy
    of the tree and the guard run against it, rather than editing the real
    source to prove the guard works.
    """
    report = ClosureReport(entrypoint=entrypoint)
    queue = [entrypoint]
    seen: set[str] = set()

    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = module_path(module, root)
        if path is None:
            continue
        report.modules[module] = path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imports(tree, module):
            report.edges.append((module, imported))
            if imported not in seen:
                queue.append(imported)
    return report


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """id() of every Constant node that is a docstring, so prose is exempt."""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def market_identifiers_in(path: Path) -> list[tuple[str, int]]:
    """Every forbidden identifier or string literal in one file, with its line."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    exempt = _docstring_nodes(tree)
    hits: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        text = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in exempt:
                continue
            text = node.value
        elif isinstance(node, ast.Name):
            text = node.id
        elif isinstance(node, ast.Attribute):
            text = node.attr
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            text = node.name
        if not text:
            continue
        for word in FORBIDDEN_IDENTIFIERS:
            if word in text:
                hits.append((word, getattr(node, "lineno", 0)))
    return hits


def check_all_prediction_closures(root: Path | None = None) -> dict[str, ClosureReport]:
    """Walk every sport's prediction closure, and the shared core.

    Returns one report per entrypoint so module counts can be reported per
    sport. Raises on the first violation, naming which sport it was in.
    """
    return {
        name: check_prediction_closure(entrypoint, root)
        for name, entrypoint in prediction_entrypoints().items()
    }


def check_prediction_closure(
    entrypoint: str = PREDICTION_ENTRYPOINT, root: Path | None = None
) -> ClosureReport:
    """Raise `LawViolation` if this prediction path can reach market data."""
    report = import_closure(entrypoint, root)

    for module in sorted(report.modules):
        if module == CLOSURE_EXEMPT_PACKAGE or module.startswith(
                CLOSURE_EXEMPT_PACKAGE + "."):
            raise LawViolation(
                f"GRIDIRON LAW 1 VIOLATED: {entrypoint} can reach {module!r}, "
                f"the priced forecaster. That package reads the market by "
                f"design, so a blind path that imports it is two steps from a "
                f"line rather than one. The exemption in CLOSURE_EXEMPT_PACKAGE "
                f"lets the priced package read the market; it does not let the "
                f"blind path read the priced package.")
        for forbidden in FORBIDDEN_MODULES:
            if module == forbidden or module.startswith(forbidden + "."):
                chain = " -> ".join(report.path_to(module)) or module
                raise LawViolation(
                    f"GRIDIRON LAW 1 VIOLATED: {entrypoint} can reach {module!r}.\n"
                    f"  import chain: {chain}\n"
                    "  The model's probability must be computed and written before "
                    "any line is fetched. Nothing on the prediction path may import "
                    "the market package."
                )

    for module, path in sorted(report.modules.items()):
        hits = market_identifiers_in(path)
        if hits:
            listed = ", ".join(f"{word!r} at line {line}" for word, line in hits[:6])
            raise LawViolation(
                f"GRIDIRON LAW 1 VIOLATED: {module} names market data ({listed}).\n"
                f"  file: {path}\n"
                "  A module on the prediction path may explain in prose that it "
                "must not read a line, but it may not name one in code."
            )

    return report


# ---------------------------------------------------------------------------
# LAW 5: not a betting tool
# ---------------------------------------------------------------------------

#: Names a staking tool would need. Identifiers only — a betting surface is
#: made of functions and variables, not sentences. The package says the words
#: "bankroll" and "stake" out loud in its own disclaimer, and a scan that could
#: not tell a disclaimer from a feature would force the project to stop
#: explaining what it refuses to do.
#: RETIRED 2026-09-07, and REPLACED rather than refuted. LAW 5 no longer
#: forbids the staking surface these words describe: the operator wagers either
#: way and ruled that the app should price what he is doing. What the old law
#: was really protecting -- the codebase's distance from his money -- is now
#: three harder scans at the bottom of this file: `check_no_venue_credentials`,
#: `check_no_order_path`, `check_no_wagering_ledger`.
#:
#: The list stays because a reader who greps for `kelly` deserves to find the
#: history rather than an absence. Nothing calls it; `check_no_orphan_functions`
#: does not scan constants.
RETIRED_BETTING_IDENTIFIERS = (
    "kelly",
    "bankroll",
    "stake",
    "wager",
    "bet_size",
    "sizing",
    "unit_size",
    "recommend_bet",
    "sportsbook",
    "exchange_api",
    "expected_value",
    "roi",
    # PRICING A LINE, as distinct from recording one (LAW 5, and the words are
    # the law's own: "no payout or price-to-return arithmetic ... no slip").
    # The list had none of them until 2026-09-02, when a planting put a
    # `prizepicks_payout` in the market module and nothing objected -- the
    # law's TEXT forbade it and the law's MECHANISM did not.
    #
    # This matters more with a projections feed than with a scoreboard API. A
    # feed of lines with no prices is shaped like an invitation to compute a
    # return from them, and the market module is exactly where someone would
    # reasonably put that: the quarantine says WHERE a source may be read, not
    # that anything goes there.
    #
    # `vig` and `odds` are deliberately absent. `devig_pair` removes the
    # market's margin to recover a fair probability, and a stored price is
    # what the market SAID -- both are reading, which the law permits. The
    # forbidden act is turning either into money.
    "payout",
    "payoff",
    "price_to_return",
    "parlay",
    "entry_fee",
    "entry_amount",
    "profit",
    # "bet_slip", not a bare "slip": the law's word is "slip", but a bare
    # substring would fire on any future identifier that merely contains it,
    # and a guard that cries wolf is a guard that gets an allowlist entry.
    "bet_slip",
)


def identifiers_in(path: Path) -> set[str]:
    """Every name bound or referenced in a file. Strings are not names."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


#: THE SCAN CANNOT SCAN ITSELF. This module holds the list of forbidden
#: staking words, so every one of them appears in its own identifiers -- and
#: the moment a guard was written to keep an amount off the operator's calls
#: (`call_stake_faults`, `STAKE_COLUMNS`), LAW 5 flagged the guard.
#:
#: The same shape as two rules already recorded here: `audit` stays outside
#: the prediction closure because it names market columns, and the runtime
#: missing-data check lives in `factors.compute` for the same reason. A module
#: that must NAME what is forbidden cannot be judged by the scan that forbids
#: it.
#:
#: Exactly one file, and narrow on purpose -- a test asserts that nothing else
#: is exempt, because "the scanner is allowed to say the word" is one
#: generalisation away from "the allowlist is where violations go to live".
BETTING_SCAN_EXEMPT = ("audit.py",)


# A MARKET SOURCE LIVES IN THE MARKET MODULE (LAW 5, amended 2026-09-02)
# ---------------------------------------------------------------------------
#
# The operator's amendment permits read-only PrizePicks lines as MARKET DATA,
# "permitted only inside the market module, only after the prediction row
# exists, only unauthenticated". The first clause is the one a scan can hold:
# the identifier may appear inside `gridiron/market/` and nowhere else.
#
# This is the same one-module rule the ESPN odds code already lives under, and
# it is the rule that makes the rest of the amendment enforceable -- a fetcher
# outside the quarantine could be reached from a prediction path, and LAW 1's
# closure scan only sees what the closure imports.

#: Where a market source may be named. Everything under it is already inside
#: the LAW 1 quarantine.
MARKET_MODULE = "market"

#: Names that belong to a market source and to nowhere else.
MARKET_SOURCE_IDENTIFIERS = ("prizepicks", "prize_picks", "kalshi")


def market_source_faults(root: Path | None = None) -> list[str]:
    """A market source named outside the market module."""
    root = root or config.PACKAGE_ROOT
    faults = []
    for path in sorted(root.rglob("*.py")):
        if MARKET_MODULE in path.parts:
            continue
        if path.name in BETTING_SCAN_EXEMPT:
            continue
        for name in sorted(identifiers_in(path)):
            lowered = name.lower()
            for word in MARKET_SOURCE_IDENTIFIERS:
                if word in lowered:
                    faults.append(
                        f"{path.relative_to(root)}:{name} names a market "
                        f"source outside gridiron/{MARKET_MODULE}/. LAW 5 as "
                        f"amended permits read-only lines from PrizePicks and "
                        f"Kalshi ONLY inside the market module -- that quarantine is "
                        f"what keeps a fetcher out of a prediction path, and "
                        f"LAW 1's closure scan can only see what the closure "
                        f"imports.")
    return faults


def check_market_sources_stay_in_the_market_module(root: Path | None = None) -> None:
    faults = market_source_faults(root)
    if faults:
        raise LawViolation(
            "A MARKET SOURCE ESCAPED THE MARKET MODULE:"
            + _NL2 + _NL2.join(faults[:8]))


def betting_surface(root: Path | None = None) -> list[str]:
    """RETIRED 2026-09-07: what the staking scan used to find.

    Kept callable so the tests and close-outs that name it still run and still
    mean something -- it reports what a staking tool would look like, which is
    now a description rather than a violation. The three scans that replaced it
    are `venue_credential_faults`, `order_path_faults` and
    `wagering_ledger_faults`.
    """
    root = root or config.PACKAGE_ROOT
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in BETTING_SCAN_EXEMPT:
            continue
        for name in sorted(identifiers_in(path)):
            lowered = name.lower()
            for word in RETIRED_BETTING_IDENTIFIERS:
                if word in lowered:
                    hits.append(f"{path.name}:{name}")
    return hits


def check_not_a_betting_tool(root: Path | None = None) -> None:
    """RETIRED 2026-09-07 by the amendment to LAW 5. Kept as a no-op with its
    reason attached, because a check that vanished leaves a reader unable to
    tell a relaxed rule from a forgotten one. See `check_no_venue_credentials`,
    `check_no_order_path` and `check_no_wagering_ledger`."""
    return None


def _the_old_staking_refusal(root: Path | None = None) -> None:
    hits = betting_surface(root)
    if hits:
        raise LawViolation(
            "GRIDIRON LAW 5 VIOLATED: the package has grown a staking surface "
            f"({', '.join(hits[:8])}). Gridiron states probabilities and keeps "
            "score of them. It does not size stakes, manage a bankroll, or "
            "recommend a bet."
        )


# ---------------------------------------------------------------------------
# v2: missing stays explicit
# ---------------------------------------------------------------------------

# The runtime half lives in `factors.compute`, because that module IS on the
# prediction path and importing this one would drag the forbidden-identifier
# list below into the closure the LAW 1 scan walks — the guard would flag
# itself. Re-exported here so the planted-violation harness has one door.
from .factors.compute import (  # noqa: E402
    MissingDataDefaulted,
    assert_missing_is_explicit,
)


#: The prediction closure may not read a per-factor fallback value. The
#: `Factor.default` field was removed in v2 rather than left unused, so any
#: reappearance of this name in the factor-computing code is a fallback coming
#: back.
def check_no_silent_defaults(root: Path | None = None) -> None:
    path = (root or config.PACKAGE_ROOT) / "factors" / "compute.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "default":
            raise MissingDataDefaulted(
                f"GRIDIRON v2 VIOLATED: {path.name} line {node.lineno} reads a "
                "`.default` off a factor. A factor that cannot be measured is "
                "excluded from the vector; it is never given a stand-in value."
            )
        if isinstance(node, ast.Name) and node.id == "default":
            raise MissingDataDefaulted(
                f"GRIDIRON v2 VIOLATED: {path.name} line {node.lineno} uses a "
                "`default` value in the factor vector."
            )


# ---------------------------------------------------------------------------
# the service worker may not cache data
# ---------------------------------------------------------------------------

#: A worker that caches a response from these paths is serving a forecast whose
#: age nobody can see. That is the failure this whole project is built against,
#: arriving through the one component that runs after the page has loaded.
_NL2 = chr(10) + "  "

DATA_PATHS = ("/api/", "/auth/")

#: Ways a service worker puts a response into a cache. Any of these appearing in
#: a branch that handles a data path is the violation.
CACHE_WRITES = ("cache.put", "cache.add", "caches.open", "cache.addAll",
                "caches.match", "cache.match")

#: How far past a data-path mention to keep looking for a cache write.
#: Twelve lines covers any chained expression a person would write.
WINDOW_LINES = 12


def offline_data_caching(worker: Path | None = None) -> list[str]:
    """Statements in the service worker that would cache a DATA response.

    The rule this enforces, stated plainly: **once the worker has noticed that a
    request is for a data path, it must RETURN before it touches a cache.**

    The first version of this check looked for a data path and a cache write on
    the SAME LINE, and a planted caching worker walked straight past it — the
    two sat on adjacent lines of one chained expression, which is how anybody
    would actually write it. The planting caught the guard, which is what
    plantings are for; a guard nobody has tried to break is a guard nobody
    should trust.

    So it scans forward from each data-path mention and flags a cache write that
    appears before a `return`. Crude on purpose: a cleverer check that followed
    the control flow would be easier to fool, and the fix for a false positive
    is to write the worker more plainly, which is desirable anyway.
    """
    worker = worker or (config.PACKAGE_ROOT / "web" / "sw.js")
    if not worker.exists():
        return ["no service worker found at " + str(worker)]

    lines = worker.read_text(encoding="utf-8").splitlines()
    code = [line.split("//", 1)[0] for line in lines]
    hits: list[str] = []

    for number, line in enumerate(code):
        if not any(path in line for path in DATA_PATHS):
            continue
        # From here to the end of this branch, the only correct move is to stop.
        for offset in range(number, min(number + WINDOW_LINES, len(code))):
            ahead = code[offset]
            if "return" in ahead and offset > number:
                break
            if any(call in ahead for call in CACHE_WRITES):
                hits.append(
                    f"sw.js:{offset + 1}: caches a response on a path matched at "
                    f"line {number + 1} without returning first — "
                    f"{lines[offset].strip()[:70]}"
                )
                break

    # A worker that never mentions a data path at all has no guard, so every
    # request it caches is potentially data.
    if not any(any(path in line for line in code) for path in DATA_PATHS):
        if any(call in line for line in code for call in CACHE_WRITES):
            hits.append(
                "sw.js: caches responses but never names a data path, so nothing "
                "stops a forecast being served from storage"
            )
    return hits


def check_no_offline_data_caching(worker: Path | None = None) -> None:
    hits = offline_data_caching(worker)
    if hits:
        raise LawViolation(
            "OFFLINE DATA CACHING: the service worker would serve API data from "
            "storage. A forecaster showing yesterday's probabilities as though "
            "they were today's is lying in the exact way this project exists to "
            "prevent: a cached calibration figure has no N you can trust and a "
            "cached slate may describe games that have already finished. The "
            "shell may be cached; data is always fetched, and when the network "
            "is gone the app says so. Offending lines:" + _NL2 + _NL2.join(hits[:8])
        )


# ---------------------------------------------------------------------------
# the plain-words law
# ---------------------------------------------------------------------------

#: Internal vocabulary that must never reach a reader. Market names are here
#: because they are the ones that actually leaked: the history table showed
#: "Saquon Barkley rushing_yards" for months.
INTERNAL_TERMS = (
    "rushing_yards", "receiving_yards", "passing_yards", "passing_tds",
    "batter_hits", "batter_total_bases", "batter_home_runs",
    "pitcher_strikeouts", "market_type", "prop_type", "model_prob",
    "line_asked", "factor_set_version", "created_utc", "resolved_utc",
    "implied_prob", "game_id",
    # GRIDIRON_COMBOS brought these into the payloads (2026-09-08) and the
    # list did not know them until NIGHT_AUDIT item 4 read it against the
    # tree. Any of them on a label is a column name a reader would have to
    # decode.
    "combo_2", "combo_3", "same_game", "unforecast_leg", "unforecast_sport",
    "why_not", "legs_text", "settles_into", "package_id", "taken_id",
    "retracted_utc",
    # FACTOR-SET VERSION STRINGS. "Factor set fs2" rendered in the footer of
    # every page and the scan called the page clean, because a version is not
    # snake_case and was not on this list. It is an internal identifier by any
    # reading: nobody says "fs2" out loud, and a reader cannot tell from it
    # what changed or when. Generated from config so a new version cannot be
    # coined without the scan learning about it.
    *config.FACTOR_SET_HISTORY,
    "factor_set", "fs_version",
)
#: NOT on that list, deliberately: "predictor" and "forecaster". They are
#: ENGLISH WORDS, and the page says "the statistical and LLM predictors are
#: scored separately" as ordinary prose. A scan that cannot tell an identifier
#: from a word starts forcing prose to get worse to satisfy it, which is the
#: opposite of the law.

#: Words that look like snake_case but are legitimate visible text. Kept short
#: and each one justified, because a long allowlist is how a law stops binding.
SNAKE_ALLOWED = (
    "llm_unavailable",   # a degradation TAG, shown verbatim so it can be
                         # grepped in a log; it is a machine fact on purpose
)

#: An identifier shaped like `rushing_yards`. The separators are written as
#: explicit character classes rather than `\b`, because a `\b` in this file
#: has now been mangled into a literal backspace FIVE times -- and this
#: pattern is the one that enforces the plain-words law. It was blind.
SNAKE_CASE = __import__("re").compile(
    r"(?:^|[^A-Za-z0-9_])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?:[^A-Za-z0-9_]|$)")


def version_names() -> tuple[str, ...]:
    """Every internal version name this app coins for its own parts (operator
    question 19; the board merge, 2026-09-29): every factor set ever declared,
    every ordering up to the one in force, and the blend's."""
    sets = set(config.FACTOR_SET_HISTORY) | {config.FACTOR_SET_VERSION} \
        | set(getattr(config, "FACTOR_SET_ACTIVATED", {}) or {})
    rank = int(config.RANKER_VERSION.lstrip("r") or 0)
    ranker = {f"r{i}" for i in range(1, rank + 1)} | {config.RANKER_VERSION}
    return tuple(sorted(sets | ranker | {config.PRICED_VERSION}))


#: A correction's number said in words -- "version 8", "Versions 8 and 9".
_VERSION_IN_WORDS = re.compile(r"(?<![A-Za-z0-9])[Vv]ersions?\s+[0-9]+(?![0-9])")


def version_name_violations(text: str) -> list[str]:
    """An internal version name in text a reader sees (operator question 19,
    ruled 2026-09-27: "internal version names only in a tooltip")."""
    hits = []
    for name in version_names():
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text):
            hits.append(f"the internal version name {name!r} is visible to a "
                        f"reader -- it belongs in a tooltip (operator question "
                        f"19, 2026-09-27)")
    for match in _VERSION_IN_WORDS.findall(text):
        hits.append(f"a version number, {match!r}, is visible to a reader -- "
                    f"name it in words and put the number in a tooltip "
                    f"(operator question 19, 2026-09-27)")
    return hits


def plain_words_violations(text: str, *, in_a_tooltip: bool = False) -> list[str]:
    """Internal vocabulary found in text a person will read.

    Deliberately crude: it looks at rendered visible text, not at markup, and
    flags anything shaped like an identifier. A false positive is fixed by
    writing the label in words, which is the desired outcome anyway.

    AND AN INTERNAL VERSION NAME, UNLESS THE TEXT IS A TOOLTIP (operator
    question 19, ruled 2026-09-27: "headings in plain words; internal version
    names only in a tooltip"; built by the board merge, 2026-09-29): a factor
    set's, the blend's or the ordering's name, or a correction's number said
    as "version 8", is refused in visible text (`version_name_violations`)
    and passes in a tooltip, the one place it may be. Everything else is
    refused in a tooltip as anywhere.
    """
    hits: list[str] = []
    if not in_a_tooltip:
        hits.extend(version_name_violations(text))
    # A FACTOR SET'S NAME IS A VERSION NAME (question 19): in a tooltip it is
    # the name's one place, so the list below does not refuse it there.
    versions = set(version_names()) if in_a_tooltip else set()
    for term in INTERNAL_TERMS:
        if term in text and term not in versions:
            hits.append(f"internal term {term!r} is visible to a reader")
    for match in SNAKE_CASE.findall(text):
        if match in SNAKE_ALLOWED or any(match in h for h in hits):
            continue
        hits.append(f"snake_case {match!r} is visible to a reader")
    # A SLATE KEY IS NOT A DATE A PERSON READS. The day-keyed sports store
    # their slate as YYYYMMDD -- an integer that orders the record perfectly
    # -- and "Season 2026, week 20260905" sat above every college slate until
    # E1. Eight digits a reader has to parse into a date is an identifier
    # wearing a number's clothes, which is the same defect as snake_case in a
    # label and harder to notice.
    for match in DATE_KEY.findall(text):
        hits.append(
            f"the slate key {match!r} is visible to a reader -- say the date "
            f"in words")
    # THE KEY'S OTHER DISGUISE, and the first version of this rule missed it.
    # Catching the eight-digit form left "Day 159, 2026" standing at the top
    # of every baseball slate: not eight digits, just as much an internal
    # ordinal, and read by nobody. A WEEK NUMBER IS DIFFERENT -- "Week 2" is
    # how football organises itself and how a reader refers to a slate, so it
    # stays. No baseball fan has ever called a date "Day 159".
    for match in DAY_KEY.findall(text):
        hits.append(
            f"the slate key 'Day {match}' is visible to a reader -- a day "
            f"ordinal means nothing outside this database; say the date in "
            f"words")
    # THE PRESSURE WORDS ARE NOT HERE, and the reason is measured. Folding
    # them in put the list in front of the second forecaster's own prose,
    # where two stored rows say "boost" -- a boost from playing at home, which
    # is ordinary English about a baseball game. `pressure_word_faults` scans
    # the text THIS PROJECT composes instead, exactly as `ADVICE_WORDS` does
    # and for the same reason: a false positive there is fixed by writing a
    # better sentence, and one here would force the model's prose to get worse
    # to satisfy a scan.
    return sorted(set(hits))


#: An eight-digit run starting with a plausible year: 20260905, not 12345678
#: and not a four-digit season. Bounded so a long ordinary number -- a token, a
#: byte count -- is not mistaken for a date.
DATE_KEY = re.compile(r"(?<![0-9])(?:19|20|21)[0-9]{2}(?:0[1-9]|1[0-2])"
                      r"(?:0[1-9]|[12][0-9]|3[01])(?![0-9])")

#: The ordinal form: "Day 159". One to three digits, so a year is not caught,
#: and the word must stand on its own -- "30-day sliding" and "14 days" are
#: ordinary English and say nothing about a slate.
DAY_KEY = re.compile(r"(?<![A-Za-z0-9])[Dd]ay\s+([0-9]{1,3})(?![0-9])")


def check_plain_words(text: str, where: str = "the page") -> None:
    hits = plain_words_violations(text)
    if hits:
        raise LawViolation(
            f"PLAIN WORDS: {where} shows internal vocabulary. Every visible "
            "label is a phrase a person would say out loud - a record nobody "
            "can read is a record nobody can check. Offending text:"
            + _NL2 + _NL2.join(hits[:8])
        )


# ---------------------------------------------------------------------------
# ORPHANS — a guard nobody calls is a guard on faith
# ---------------------------------------------------------------------------
#
# This scan exists because `rung_probabilities` shipped as checklist item 4's
# cross-check with ZERO callers anywhere -- not in production, not even in a
# test. It could not fail, because nothing ran it. The suite was green and the
# check was decorative.
#
# That is a shape this project keeps meeting from new angles: a green suite
# verifies the code that RUNS. It says nothing about code that does not. A
# planted violation proves a guard fires; this proves a guard is reached.
#
# TWO RULES DECIDE WHAT COUNTS, and both were forced by the first run, which
# flagged 64 functions and would have needed a 35-line allowlist -- the mute
# button this file's own docstring warns about:
#
#   * A DECORATED function is wired. `@factor(...)` registers the function into
#     REGISTRY and the loop invokes it as `f.fn(ctx)`; a route decorator does
#     the same for a handler. The decorator IS the call site, so requiring a
#     bare-name caller would flag every factor in the project.
#   * `tools/` COUNTS AS A CALLER, `tests/` DOES NOT. `tools/verify.py` and
#     `tools/guards/plant.py` are shipped code that runs in earnest. A function
#     reached only by its own unit test is precisely the case this scan is for.

#: Public functions that legitimately have no caller in `gridiron/` or `tools/`.
#: Every entry is DATED and says why, because "it is fine" ages badly and an
#: allowlist nobody can audit is just a mute button.
ORPHAN_ALLOWLIST: dict[str, str] = {
    "main": "2026-08-31: module entry point, invoked by the shell, not by us.",
    # The sport-adapter protocol. `sports.get()` imports the module and the
    # blind loop calls these through it, so no bare name appears at a call site.
    "slate_questions": "2026-08-31: sport-adapter surface, reached through the adapter module.",
    "build_features": "2026-08-31: sport-adapter surface, reached through the adapter module.",
    "training_set": "2026-08-31: sport-adapter surface, reached through the adapter module.",
    "resolve_outcome": "2026-08-31: sport-adapter surface, reached through the adapter module.",
    "next_slate": "2026-08-31: sport-adapter surface, reached through the adapter module.",
    "markets": "2026-08-31: sport-adapter surface, reached through the adapter module.",
    "first_slate_note": "2026-08-31: optional adapter surface, looked up with getattr.",
    "build_context": "2026-08-31: adapter surface, reached through the adapter module.",
    "build_prop_context": "2026-08-31: adapter surface, reached through the adapter module.",
    # Kept deliberately for callers outside this repository's own code.
    "run_week": "2026-08-31: NFL-shaped wrapper kept for existing callers and tests.",
    "select_props": "2026-08-31: single-game prop selection, kept beside select_week_props for callers and tests.",
    "snapshot_for_game": "2026-08-31: per-game snapshot entry point used by the CLI's ad-hoc path and tests.",
    # Read-only accessors and diagnostics, kept because deleting a query is not
    # the same as deleting dead logic: each is exercised by tests, each is one
    # obvious call away, and none can be wrong in a way that reaches the record.
    # MENTOR.md §4: delete is the last resort in a model or data module.
    "batter_last_played": "2026-08-31: batter recency accessor; selection currently inlines the same MAX(game_date). Kept as the named form.",
    "cache_stats": "2026-08-31: http_cache diagnostic, read by hand when a season load looks wrong.",
    "injury_report_names": "2026-08-31: NBA injury accessor, sibling of the one the rotation filter uses.",
    "team_history": "2026-08-31: NFL team history accessor, kept beside the ones the factors use.",
    "prop_market": "2026-08-31: inverse of prop_stat; kept as the named pair so neither is re-derived at a call site.",
    "record_factor_score": "2026-08-31: writes factor_scores; the scoring pass that calls it is not built yet, and the table it writes is declared in the schema.",
    "scalar": "2026-08-31: db convenience, one line, used by tests and ad-hoc queries.",
    "table_columns": "2026-08-31: db introspection used by tests and by the migration path by hand.",
    "check_plain_words": "2026-08-31: raises for callers that render a page; the smoke suite is the only renderer, so it is the only caller.",
}


def _decorated(node) -> bool:
    return bool(getattr(node, "decorator_list", []))


def _public_functions(root: Path) -> dict[str, str]:
    """Public, UNDECORATED, top-level functions in the package: name -> file."""
    import ast as _ast

    out: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = _ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                if not node.name.startswith("_") and not _decorated(node):
                    out.setdefault(node.name, str(path.relative_to(root.parent)))
    return out


def _caller_sources(root: Path) -> dict[str, str]:
    """Every file whose calls count: the package, `tools/`, `desktop/`.

    NEVER TESTS -- a function reached only by its own unit test is precisely
    what this scan is for.

    `desktop/` was added 2026-09-01, when the build stamper was reported as an
    orphan. It is called by the PyInstaller spec, which is how the bundle is
    built: shipped code that runs in earnest, by the same argument that
    admitted `tools/`. Widening the definition of a caller is a mute button
    when it is done to silence a finding; here the finding was wrong, and the
    fix is the rule catching up with where shipped code lives.

    A `.spec` IS PYTHON and is globbed as such. Without that this widening
    would have passed for the wrong reason entirely: the scan counts a bare
    identifier anywhere in a counted file, so the sentence above naming the
    function WAS the call site it found. A guard satisfied by a comment about
    the guard is worse than the finding it silenced.
    """
    out: dict[str, str] = {}
    roots = [root]
    for name in ("tools", "desktop"):
        extra = root.parent / name
        if extra.is_dir():
            roots.append(extra)
    patterns = ("*.py", "*.spec")
    for base in roots:
        for path in sorted(q for pattern in patterns for q in base.rglob(pattern)):
            if "__pycache__" in path.parts:
                continue
            try:
                out[str(path)] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return out


def orphan_functions(root: Path | None = None) -> list[str]:
    """Public functions the shipped code defines and never reaches.

    Callers in `tests/` do not count. A function reached only by its own unit
    test is exactly the case that looked green and did nothing.
    """
    root = Path(__file__).resolve().parent if root is None else Path(root)
    functions = _public_functions(root)
    sources = _caller_sources(root)

    orphans = []
    for name, where in sorted(functions.items()):
        if name in ORPHAN_ALLOWLIST:
            continue
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        uses = 0
        for body in sources.values():
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith((f"def {name}", f"async def {name}")):
                    continue
                uses += len(pattern.findall(line))
        if uses == 0:
            orphans.append(f"{name} ({where}) is defined and never called")
    return orphans


def check_no_orphan_functions(root: Path | None = None) -> None:
    hits = orphan_functions(root)
    if hits:
        raise LawViolation(
            "ORPHANS: these public functions are defined in the shipped code "
            "and reached from nowhere in it. A guard nobody calls is a guard on "
            "faith, and a helper nobody calls is dead weight a reader still has "
            "to get past. Wire it, delete it, or add a DATED line to "
            "audit.ORPHAN_ALLOWLIST saying why it stands alone:"
            + _NL2 + _NL2.join(hits[:10])
        )


# ---------------------------------------------------------------------------
# ONE DOOR FOR THE SIDE — the class fix for a defect that happened three times
# ---------------------------------------------------------------------------
#
# `subject` on a prediction row is the side the QUESTION was asked about: the
# home club on a moneyline, the yes side on a prop. Prose wants the side the
# ANSWER took, and the two differ whenever the model takes the NO side -- close
# to half of all moneylines.
#
# Three composers each reached for `subject` on their own and each got it
# wrong, in three separate sessions:
#
#   K1  the chance label: "97% chance WAS covers" over a decomposition summing
#       against WAS. 34 cards.
#   K3  the Why heading: "Why Atlanta Braves" over a pick for Colorado.
#   R2  the market clause: "the market has Atlanta Braves at 34%" under that
#       same pick -- the number right, the name wrong.
#
# Each was fixed where it was found, which is why it recurred. `language.
# side_named` is now the only place that resolves it, and this scan is what
# keeps it the only place: any OTHER function in the humaniser that reaches
# `subject` or `opponent` directly fails by name.

#: Functions allowed to touch the raw fields, because resolving them IS their
#: job. Everything else must call `side_named`.
SIDE_DOOR = "side_named"
SIDE_RAW_FIELDS = ("subject", "opponent")
#: `strip_market_suffix` takes the subject as an ARGUMENT and never reads the
#: item; `chance_clause` is allowlisted with a dated reason because it renders
#: the tricode rather than the display name, on purpose (a club name is plural:
#: "Colorado Rockies wins" is wrong), and it still derives that tricode from the
#: side taken.
SIDE_ALLOWLIST: dict[str, str] = {
    "side_named": "2026-08-31: this IS the door.",
    "strip_market_suffix": "2026-08-31: takes a subject as an argument; reads no item.",
    "is_no_side": "2026-08-31: reads model_side only, never a name.",
    "side_flips": (
        "2026-09-04: this IS the door for the FLIP, which is a different "
        "question from `side_named`'s. It reads `opponent` to ask whether "
        "there is anybody to restate the pick as -- it never names them. "
        "Added because the answer was previously given in two places with two "
        "different rules: `side_named` gated the flip on an opponent and "
        "`flipped_line` did not, so a card with no opponent got the original "
        "name, the flipped number and a verb belonging to neither."
    ),
    "spread_verb": (
        "2026-09-04: derives the verb from `side_flips` and reads no name at "
        "all. It exists because `phrase` and `chance_clause` each decided the "
        "verb themselves and disagreed on 68 of 321 live cards -- one card "
        "reading 'Miami covers +7.5' beside 'chance Miami does not cover'."
    ),
    "chance_clause": (
        "2026-08-31: renders the TRICODE deliberately -- club names are plural "
        "and 'Colorado Rockies wins' is wrong -- but still derives it from the "
        "side taken, not from the question's subject."
    ),
    "why_market": "2026-08-31: calls side_named; the reach is inside a comment.",
}


def side_field_reachers(path: Path | None = None) -> list[str]:
    """Functions in the humaniser that read a raw side field themselves."""
    import ast as _ast

    path = (Path(__file__).resolve().parent / "language.py") if path is None else Path(path)
    tree = _ast.parse(path.read_text(encoding="utf-8"))

    offenders = []
    for node in tree.body:
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        if node.name in SIDE_ALLOWLIST:
            continue
        for sub in _ast.walk(node):
            # item.get("subject") / item.get("opponent")
            if isinstance(sub, _ast.Call) and isinstance(sub.func, _ast.Attribute):
                if sub.func.attr == "get" and sub.args:
                    arg = sub.args[0]
                    if isinstance(arg, _ast.Constant) and arg.value in SIDE_RAW_FIELDS:
                        offenders.append(f"{node.name} reads item.get({arg.value!r})")
            # item["subject"]
            if isinstance(sub, _ast.Subscript) and isinstance(sub.slice, _ast.Constant):
                if sub.slice.value in SIDE_RAW_FIELDS:
                    offenders.append(f"{node.name} reads item[{sub.slice.value!r}]")
    return sorted(set(offenders))


def check_side_named(path: Path | None = None) -> None:
    hits = side_field_reachers(path)
    if hits:
        raise LawViolation(
            "ONE DOOR FOR THE SIDE: these composers resolve the side themselves "
            "instead of calling language.side_named. That is how the same "
            "inversion shipped three times -- a chance label, a heading and a "
            "market clause each naming the team the model was forecasting "
            "AGAINST. Call side_named, or add a DATED line to "
            "audit.SIDE_ALLOWLIST saying why this one is different:"
            + _NL2 + _NL2.join(hits[:10])
        )


# ---------------------------------------------------------------------------
# NO SHADOWED DEFINITIONS — the gap the orphan scan could not see
# ---------------------------------------------------------------------------
#
# `calibration.py` carried TWO definitions of `scorecard` and two of
# `version_comparison`. Python keeps the last one and silently discards the
# first, so the earlier bodies -- 130 lines -- never ran.
#
# They were not harmless. They were the versions from BEFORE LAW 6: each
# queried `predictions` with no sport filter, which is the merged read that law
# exists to make impossible. When the `*, sport:` versions were written they
# were appended rather than substituted, and the originals stayed.
#
# Every guard in this project missed them, for a reason worth recording:
#
#   * `require_sport` never fired, because the code never executed;
#   * `check_no_orphan_functions` passed, because the NAME is reached -- the
#     live definition's callers make it look used;
#   * every test called the live one and got the right answer.
#
# It surfaced only when an edit to one of them changed nothing on the page.
# A name defined twice at module level is now a failure, and the message says
# which line wins, because "duplicate definition" is not the useful half.

def shadowed_definitions(package: Path | None = None) -> list[str]:
    """Module-level names defined more than once in the same file."""
    import ast as _ast

    root = Path(__file__).resolve().parent if package is None else Path(package)
    out = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = _ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        seen: dict[str, list[int]] = {}
        for node in tree.body:
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                 _ast.ClassDef)):
                seen.setdefault(node.name, []).append(node.lineno)
        for name, lines in seen.items():
            if len(lines) > 1:
                out.append(
                    f"{path.name}: {name} is defined {len(lines)} times "
                    f"(lines {', '.join(str(n) for n in lines)}); only line "
                    f"{lines[-1]} runs"
                )
    return sorted(out)


def check_no_shadowed_definitions(package: Path | None = None) -> None:
    hits = shadowed_definitions(package)
    if hits:
        raise LawViolation(
            "SHADOWED DEFINITION: a name is defined more than once at module "
            "level, so every definition but the last is dead code that still "
            "reads as live. This is how two pre-LAW-6 functions -- both "
            "querying every sport at once -- survived in calibration.py past "
            "the law that forbids them: unreachable code cannot trip a runtime "
            "check, and the orphan scan sees the name as reached. Delete the "
            "dead one, or rename it if both are wanted:"
            + _NL2 + _NL2.join(hits[:10])
        )


# ---------------------------------------------------------------------------
# THE SIDE, IN PROSE, ANYWHERE IN THE PACKAGE
# ---------------------------------------------------------------------------
#
# `check_side_named` above scans `language.py`, because the rule was written
# there and the premise was that all prose lives in the humaniser. The premise
# was wrong by one function: `views._resolved_story` built "picked ATL" out of
# the raw subject, over nine resolved rows whose pick was on Colorado. A FOURTH
# instance of the defect the one-door fix was supposed to end, surviving
# because the guard checked the place the rule was written rather than every
# place it applies.
#
# The distinction that makes a package-wide scan possible without drowning in
# false positives: reading `subject` into a DICT is plumbing -- views does it
# constantly, and must, to hand the item to `language` -- while reading it into
# a STRING is prose. So this looks only for a raw side field interpolated into
# an f-string or concatenated onto one, which is the shape every one of the
# four instances had.

def prose_reaching_the_raw_side(package: Path | None = None) -> list[str]:
    """Raw side fields interpolated straight into a string, anywhere."""
    import ast as _ast

    root = Path(__file__).resolve().parent if package is None else Path(package)
    out = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = _ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.JoinedStr):
                continue
            for piece in _ast.walk(node):
                name = _raw_side_read(piece)
                if not name:
                    continue
                fn = _enclosing_function(tree, piece)
                if fn in SIDE_ALLOWLIST:
                    continue
                out.append(f"{path.name}: {fn or '<module>'} puts the raw "
                           f"{name!r} straight into a sentence")
    return sorted(set(out))


def _raw_side_read(node) -> str | None:
    """`item["subject"]` or `item.get("opponent")`, or None."""
    import ast as _ast

    if isinstance(node, _ast.Subscript) and isinstance(node.slice, _ast.Constant):
        if node.slice.value in SIDE_RAW_FIELDS:
            return node.slice.value
    if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute):
        if node.func.attr == "get" and node.args:
            arg = node.args[0]
            if isinstance(arg, _ast.Constant) and arg.value in SIDE_RAW_FIELDS:
                return arg.value
    return None


def _enclosing_function(tree, target) -> str | None:
    import ast as _ast

    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            for sub in _ast.walk(node):
                if sub is target:
                    return node.name
    return None


def check_side_named_everywhere(package: Path | None = None) -> None:
    hits = prose_reaching_the_raw_side(package)
    if hits:
        raise LawViolation(
            "THE SIDE, IN PROSE: a raw `subject` or `opponent` goes straight "
            "into a sentence instead of through language.side_named. On a "
            "moneyline the subject is the HOME club, so on every pick against "
            "the home side this names the team the model forecast AGAINST. "
            "That shipped four times -- a chance label, a heading, a market "
            "clause, and a resolved row reading 'picked ATL' over a pick on "
            "Colorado. Call side_named, or add a DATED line to "
            "audit.SIDE_ALLOWLIST:"
            + _NL2 + _NL2.join(hits[:10])
        )


# ---------------------------------------------------------------------------
# THE RENDERER COMPOSES NO PROSE — a tripwire, not a proof
# ---------------------------------------------------------------------------
#
# Ruling, 2026-08-31: "PROSE IS COMPOSED SERVER-SIDE ONLY, in language.py,
# period. The frontend renders strings it is handed; it never builds a
# sentence, never concatenates a subject, never uppercases a stat."
#
# Everything the wrong-side defect did on the server, `app.js` could do again
# on its own, out of reach of every Python scan -- and did, in the digest's
# `'picked ' + String(s.subject).toUpperCase()`, which is where the fifth
# instance was found.
#
# THIS IS A REGEX SCAN OF JAVASCRIPT AND IT IS NOT A PARSER. It will miss
# things. That is accepted in the ruling and it is the right trade: the three
# shapes below are the ones that have actually happened here, the scan runs in
# under a millisecond, and the render-based plain-words scan remains the
# backstop that sees RESULTS rather than patterns. A tripwire that catches the
# repeat of a known defect is worth more than a parser nobody finishes.

#: Fields whose value is data about a prediction. Concatenating one of these
#: into a string, or changing its case, is composition.
JS_DATA_FIELDS = (
    "subject", "opponent", "prop_type", "market_type", "model_side",
    "factor", "task", "reason", "category", "database_kind", "tier",
    # ADDED 2026-09-07, after a composition stood in this file for a week
    # unseen: `glance.state_word + ' in ' + span` built the countdown's
    # sentence, and the glue rule never fired because it only fires on a line
    # that also mentions one of these names. THE LIST IS THE WEAKNESS OF THIS
    # SCAN and always was -- it is a tripwire, not a parser -- so a field that
    # has actually been glued to a label goes on it.
    "state_word", "words", "question", "phrase",
)

#: `word + expr` or `expr + word` where the literal contains a space or ends
#: in one -- a label being glued to data. `'a' + 'b'` of two literals is not
#: prose, and neither is `'#/' + route`.
_JS_GLUE = __import__("re").compile(
    r"""['"][A-Za-z][^'"]*\s['"]\s*\+\s*[A-Za-z_$]|"""
    r"""[a-zA-Z_$][\w.\[\]'"$]*\s*\+\s*['"]\s[^'"]*['"]"""
)

#: `.toUpperCase()` / `.toLowerCase()` applied to something that is not a
#: literal. Case is a CSS decision; applying it to data in JS means the string
#: was being shaped for reading.
_JS_CASE = __import__("re").compile(
    r"""(?<!['"])\)?\s*\.\s*to(?:Upper|Lower)Case\s*\(\s*\)"""
)

#: A template literal that mixes prose words with an interpolation.
_JS_TEMPLATE = __import__("re").compile(r"`[^`]*[A-Za-z]{3}[^`]*\$\{[^}]+\}[^`]*`")


def js_prose_composition(path: Path | None = None) -> list[str]:
    """Lines in the renderer that look like a sentence being built."""
    import re as _re

    path = (Path(__file__).resolve().parent / "web" / "app.js") if path is None else Path(path)
    if not path.exists():
        return []

    hits = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").split(chr(10)), 1):
        line = raw.strip()
        # Comments are exempt: this file explains its own history at length,
        # and quoting a deleted defect must not re-trip the scan that killed it.
        if line.startswith("//") or line.startswith("*") or line.startswith("/*"):
            continue
        body = _re.sub(r"//.*$", "", line)
        if _exempt_from_js_prose(body):
            continue

        if _JS_CASE.search(body) and not _re.search(
                r"""['"][^'"]*['"]\s*\.\s*to(?:Upper|Lower)Case""", body):
            hits.append(f"line {n}: changes the case of a value -- {line[:72]}")
        elif any(f".{f}" in body or f"'{f}'" in body or f'"{f}"' in body
                 for f in JS_DATA_FIELDS) and _JS_GLUE.search(body):
            hits.append(f"line {n}: glues a label onto a data field -- {line[:72]}")
        elif _JS_TEMPLATE.search(body):
            hits.append(f"line {n}: builds a sentence in a template -- {line[:72]}")
    return hits


#: A CSS CLASS is not prose. `el('span', 'tier ' + t.tier.toLowerCase(), t.tier)`
#: lowercases a value to make a class token, and the TEXT beside it is the raw
#: server string -- which is the rule being followed, not broken. Matched by
#: position: second argument of `el(`, which is where a class name goes.
_JS_CLASS_ARG = __import__("re").compile(
    r"""el\(\s*['"][^'"]+['"]\s*,\s*['"][^'"]*['"]\s*\+[^,]*to(?:Upper|Lower)Case""")

#: `requireN(obj, where)` builds an EXCEPTION message for a developer, never a
#: line on a page. Its second argument names the payload path that lost its
#: sample size, and it has to be specific to be worth throwing.
_JS_DIAGNOSTIC = __import__("re").compile(r"""requireN\s*\(""")


#: The OTHER place a class token is set. `classList.add('t-' + tier.toLowerCase())`
#: is the same act as passing it to `el()` -- a token for CSS, never a word a
#: reader sees -- and the scan has to know both shapes or it flags correct code
#: for using the wrong one of two equivalent APIs.
_JS_CLASSLIST = __import__("re").compile(
    r"""classList\s*\.\s*(?:add|remove|toggle)\s*\(""")


def _exempt_from_js_prose(body: str) -> bool:
    """Two shapes this scan must not flag, each for a stated reason.

    Narrowed rather than silenced: both exemptions are positional, so a real
    violation on the same line still trips -- a class name is the second
    argument of `el(`, a diagnostic is inside `requireN(`, and prose is
    anywhere else.
    """
    return bool(_JS_CLASS_ARG.search(body) or _JS_DIAGNOSTIC.search(body)
                or _JS_CLASSLIST.search(body))


def check_js_composes_no_prose(path: Path | None = None) -> None:
    hits = js_prose_composition(path)
    if hits:
        raise LawViolation(
            "THE RENDERER COMPOSED PROSE: app.js is building a string a person "
            "reads, instead of placing one the server wrote. Every sentence "
            "comes from gridiron.language -- that is where the side is "
            "resolved, where the plain-words rule is enforced, and where the "
            "tests can see it. A sentence assembled in the browser is outside "
            "all three, which is how `'picked ' + String(s.subject)."
            "toUpperCase()` shipped. Move the wording to language.py and send "
            "the finished string:"
            + _NL2 + _NL2.join(hits[:12])
        )


# ---------------------------------------------------------------------------
# THE CORRECTION SEES THE RECORD'S CLAIMS AND NOTHING ELSE
# ---------------------------------------------------------------------------
#
# A calibration correction is fitted on outcomes. That is legitimate -- it is
# the only way to learn what a claim has been worth -- and it is also one
# reachable step away from a second model fitted on the result, wearing a
# calibration label. Two properties keep it honest, and both are scanned here
# rather than trusted:
#
#   1. IT MAY READ ONLY THE RECORD'S OWN CLAIMS AND OUTCOMES. `predictions`,
#      and `prediction_voids` to exclude the terminal ones. A correction that
#      could reach `games` would be fitting on the score; one that could reach
#      `market_snapshots` would be fitting on the line, which is LAW 1's whole
#      subject arriving through the back door after the fact.
#
#   2. EVERY TRAINING QUERY IS BOUNDED IN TIME. A correction trained on rows
#      that resolved after it was fitted has seen its own future, and C2's
#      holdout -- earliest 80% to fit, latest 20% to test -- would be testing
#      on rows it trained on. The bound is what makes the holdout mean
#      anything.

#: Tables the correction engine may name. Everything else is a different model.
#:
#: AND ITS LABELS (operator question 23, ruled 2026-09-28; built 2026-09-29):
#: `correction_gate_labels` holds "fitted below its gate" beside a fit, written
#: from the fit's own record -- its category, its instant, its n_train and the
#: record's own forecasts -- and carrying no outcome, line or score; the
#: activation door reads it to refuse a labelled fit, as the ruling requires.
#:
#: AND ITS ACTIVATIONS (operator question 32, ruled 2026-09-29): a correction
#: is in force only by its own dated row in `correction_activations` -- the
#: correction it names, the instant, and a measured row's measurement, made
#: from the record's own claims and outcomes by `correction.measure` -- and
#: the door reads it; it carries no line, price or score.
CORRECTION_TABLES = frozenset({
    "predictions", "prediction_voids", "calibration_corrections",
    "correction_gate_labels", "correction_activations",
})

#: WHAT A PART OF AN F-STRING WORKED OUT AT RUN TIME IS READ AS (2026-09-29).
#: The count door of question 16 selects `bet.columns('p')` in an f-string;
#: until this date the scan read only plain strings, so an f-string's query --
#: its tables and its bounds -- was never read at all. Read whole now, each
#: `{...}` standing as this word: in a column list it names no table, and
#: where a table goes it is a table the scan cannot read, refused by name.
FSTRING_PART = "a_part_worked_out_at_run_time"

#: A training query must carry all of these. Not style: each one is a way the
#: fit could otherwise include a row it must not see.
CORRECTION_REQUIRED = (
    ("resolved_utc IS NOT NULL", "an unsettled prediction has no outcome to fit"),
    ("resolved_utc <", "without a time bound the fit can see its own future"),
    ("prediction_voids", "a void is terminal and must be excluded, not scored"),
)

#: The separator before the keyword is load-bearing. Without it, `FROM` matches
#: inside `active_from IS NOT NULL` and the scan reports the engine reading a
#: table called 'IS'. A `\b` would say the same thing; it is written out
#: because two earlier versions of this file had a `\b` turn into a literal
#: backspace in transit, and a scan whose pattern silently matches nothing
#: passes everything.
_SQL_TABLE = __import__("re").compile(
    r"(?:^|[\s,(])(?:FROM|JOIN|INTO|UPDATE)\s+([a-z_][a-z0-9_]*)",
    __import__("re").I)


#: A string is SQL if it STARTS with a SQL verb. Not "contains a table-shaped
#: word": the first version of this scan matched prose, reporting that the
#: engine reads a table called 'the' out of its own docstring. Python joins
#: adjacent string literals at parse time, so a query split across a dozen
#: source lines arrives here as one node beginning with SELECT.
_SQL_START = __import__("re").compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH)\s", __import__("re").I)


def _correction_sql(path: Path) -> list[tuple[int, str]]:
    """Every SQL statement in the module, with its line -- a plain string, and
    from 2026-09-29 an f-string read whole (`FSTRING_PART`)."""
    import ast as _ast

    tree = _ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Constant) and isinstance(node.value, str):
            if _SQL_START.match(node.value):
                out.append((getattr(node, "lineno", 0), node.value))
        elif isinstance(node, _ast.JoinedStr):
            whole = "".join(
                part.value if isinstance(part, _ast.Constant)
                and isinstance(part.value, str) else f" {FSTRING_PART} "
                for part in node.values)
            if _SQL_START.match(whole):
                out.append((getattr(node, "lineno", 0), whole))
    return out


def correction_reaches(path: Path | None = None) -> list[str]:
    """Tables the correction engine names that it has no business naming."""
    path = (Path(__file__).resolve().parent / "correction.py") if path is None else Path(path)
    if not path.exists():
        return []
    bad = []
    for line, sql in _correction_sql(path):
        for table in _SQL_TABLE.findall(sql):
            if table.lower() not in CORRECTION_TABLES:
                bad.append(f"line {line}: reads {table!r}")
    return sorted(set(bad))


def correction_training_is_bounded(path: Path | None = None) -> list[str]:
    """Training queries missing a guard that keeps a forbidden row out."""
    path = (Path(__file__).resolve().parent / "correction.py") if path is None else Path(path)
    if not path.exists():
        return []
    missing = []
    for line, sql in _correction_sql(path):
        # A training query is one that reads outcomes out of predictions.
        if "outcome" not in sql or "predictions" not in sql:
            continue
        for needle, why in CORRECTION_REQUIRED:
            if needle not in sql:
                missing.append(f"line {line}: no {needle!r} -- {why}")
    return sorted(set(missing))


def check_correction_is_isolated(path: Path | None = None) -> None:
    hits = correction_reaches(path) + correction_training_is_bounded(path)
    if hits:
        raise LawViolation(
            "THE CORRECTION REACHED PAST THE RECORD: a calibration correction "
            "is fitted on outcomes, which makes it one step from a second "
            "model fitted on the result. It may read the record's own claims "
            "and outcomes -- `predictions`, and `prediction_voids` to exclude "
            "the terminal ones -- and every training query must be settled, "
            "void-free and BOUNDED IN TIME, or the fit sees its own future and "
            "the holdout tests on rows it trained on:"
            + _NL2 + _NL2.join(hits[:10])
        )


# ---------------------------------------------------------------------------
# A SECOND LOOK AT THE LINE HAS TO BE A SECOND LOOK
# ---------------------------------------------------------------------------
#
# The drift question -- when the model disagrees, does the market later move
# toward it or away? -- rests entirely on two readings of the same line being
# taken at different times. Nothing about the code says they are: both call the
# same fetch, and that fetch serves anything younger than `LIVE_TTL` (six
# hours) straight out of `http_cache`.
#
# So the first live run recorded eight near-start snapshots that were byte-for-
# byte replays of the open ones. Every drift pair read exactly zero movement.
# The rows looked real, the task reported success, and the measurement was of
# nothing. Eight rows were deleted; the mechanism got a shorter TTL.
#
# This asserts the one invariant that makes the second look real. It cannot
# prove the market was re-read -- only a network can -- but the failure it
# catches is the one that actually happened, and it costs nothing.

def second_look_ttl() -> tuple[object, object]:
    """(near-start window, live cache window). Read, not assumed."""
    from .data import sources
    from .market import espn

    return espn.NEAR_START_TTL, sources.LIVE_TTL


def check_the_second_look_is_fresh() -> None:
    near, live = second_look_ttl()
    if near >= live:
        raise LawViolation(
            "THE SECOND LOOK IS NOT A SECOND LOOK: the near-start snapshot "
            f"accepts a cached quote up to {near} old, and the live cache "
            f"window is {live}. Anything at or above that window is served "
            "from `http_cache`, so the second reading of the line is the first "
            "one replayed, every drift pair reads exactly zero movement, and "
            "the whole measurement quietly describes the cache instead of the "
            "market. That shipped once and produced eight such rows."
        )


# ---------------------------------------------------------------------------
# EVERY SCANNER PROVES ITSELF AT IMPORT
# ---------------------------------------------------------------------------
#
# Ruling, 2026-08-31, on the fourth instance of one failure: a `\b` written
# into a generated pattern arrived as a literal backspace (0x08), so the
# compiled regex matched NOTHING and the scan built on it reported every module
# clean. Three guards have now been born blind that way -- the orphan scan's
# name pattern, the JS diagnostic exemption, and the correction's table scan --
# and each was caught by a human noticing a suspiciously tidy result, which is
# not a control.
#
# So each pattern carries a string it MUST match and a string it must NOT, and
# the pair is checked when this module is imported. A blind scanner now fails
# at import rather than passing everything quietly. The cost is a few
# microseconds per process; the alternative has cost three defects.
#
# A pattern with no fixture is itself a failure: the check walks the declared
# list, so adding a scanner without one is caught by the test that asserts
# every compiled pattern in this module appears here.

#: pattern name -> (must match, must not match). Both halves matter: a pattern
#: that matches everything is as broken as one that matches nothing, and only
#: the negative case catches it.
SCANNER_FIXTURES: dict[str, tuple[str, str]] = {
    "SNAKE_CASE": ("rushing_yards", "rushing yards"),
    "_JS_GLUE": ("'picked ' + subject", "a + b"),
    "_JS_CASE": (".toUpperCase()", "toUpperCase"),
    "_JS_TEMPLATE": ("`the model says ${p}`", "`${p}`"),
    "_JS_CLASS_ARG": ("el('span', 'tier ' + t.tier.toLowerCase(), t.tier)",
                      "el('span', 'tier', t.tier)"),
    "_JS_DIAGNOSTIC": ("requireN(c, 'category')", "require(c)"),
    "_JS_CLASSLIST": ("tile.classList.add('t-' + tier)", "list.append(x)"),
    "_SQL_TABLE": ("SELECT x FROM predictions p JOIN games g",
                   "WHERE active_from IS NOT NULL"),
    "_SQL_START": ("SELECT 1 FROM predictions", "a docstring about SELECT"),
    # The key that shipped, and a season that must NOT trip it.
    "DATE_KEY": ("Season 2026, week 20260905", "Season 2026, Week 1"),
}


def scanner_self_check() -> list[str]:
    """Every declared pattern, checked against its known-positive and -negative."""
    problems = []
    here = globals()
    for name, (positive, negative) in SCANNER_FIXTURES.items():
        pattern = here.get(name)
        if pattern is None:
            problems.append(f"{name}: declared a fixture but no such pattern")
            continue
        probe = pattern.match if name == "_SQL_START" else pattern.search
        if not probe(positive):
            problems.append(
                f"{name}: does not match its known-positive {positive!r} -- "
                f"the compiled pattern is {pattern.pattern!r}, which is what a "
                f"corrupted escape looks like"
            )
        if probe(negative):
            problems.append(
                f"{name}: matches its known-negative {negative!r}, so it will "
                f"flag correct code"
            )
    return problems


def check_scanners_can_see() -> None:
    problems = scanner_self_check()
    if problems:
        raise LawViolation(
            "A SCANNER IS BLIND: a guard's pattern does not do what it says, so "
            "everything it scans will pass. This has happened four times, "
            "always from an escape mangled in transit:"
            + _NL2 + _NL2.join(problems)
        )


# Checked HERE, at import, not in a test. A blind scanner that only fails under
# pytest is still blind in every other process -- including the ones that run
# `verify.py` and the ones a person runs by hand to check something.
check_scanners_can_see()


# ---------------------------------------------------------------------------
# NO RANKINGS IN COLLEGE FOOTBALL (ruling R-D)
# ---------------------------------------------------------------------------
#
# The AP and coaches' polls are the obvious thing to reach for in this sport
# and they are excluded on purpose: they are votes. They lag results, they
# carry preseason expectation for weeks after it has been refuted, and they are
# influenced by who plays on television. A model reading them is partly
# modelling sportswriters, and when it beats the market nobody will be able to
# say which part did it.
#
# The exclusion is structural rather than remembered: the context a factor sees
# carries no poll field, so a rankings factor has nothing to read. This scan
# keeps it that way, and it deliberately looks at the CONTEXT and the FACTOR
# BODIES rather than at prose -- the registry's own docstring explains at
# length why rankings are absent, and explaining is not violating.

#: Words that name a poll or a ranking. Matched against context field names and
#: the code of cfb factor functions, never against comments or docstrings.
RANKING_WORDS = ("rank", "ranking", "poll", "ap_top", "coaches_poll",
                 "cfp_rank", "top25", "top_25")


def ranking_reaches(package: Path | None = None) -> list[str]:
    """Context fields or factor code that would let a poll into the model."""
    import ast as _ast

    root = Path(__file__).resolve().parent if package is None else Path(package)
    hits = []
    for name in ("sports/cfb.py", "factors/cfb.py"):
        path = root / name
        if not path.exists():
            continue
        tree = _ast.parse(path.read_text(encoding="utf-8"))
        exempt = _docstring_nodes(tree)
        for node in _ast.walk(tree):
            text = None
            if isinstance(node, _ast.Name):
                text = node.id
            elif isinstance(node, _ast.Attribute):
                text = node.attr
            elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                text = node.name
            elif isinstance(node, _ast.arg):
                text = node.arg
            elif isinstance(node, _ast.Constant) and isinstance(node.value, str):
                if id(node) in exempt:
                    continue
                text = node.value
            if not text:
                continue
            low = text.lower()
            for word in RANKING_WORDS:
                if word in low:
                    hits.append(f"{name}: {text[:48]!r} names {word!r}")
    return sorted(set(hits))


def check_no_rankings(package: Path | None = None) -> None:
    hits = ranking_reaches(package)
    if hits:
        raise LawViolation(
            "RANKINGS ARE NOT A FACTOR (ruling R-D): a poll is a vote, it lags "
            "the results it is meant to summarise, and a model that reads one "
            "is partly modelling sportswriters. Everything a poll knows about "
            "a team's results, the opponent-adjusted margin knows sooner and "
            "without the opinions. The exclusion is structural -- the context "
            "carries no poll field -- and this is what keeps it that way:"
            + _NL2 + _NL2.join(hits[:10])
        )


# ---------------------------------------------------------------------------
# THE RUNG IS CHOSEN AGAINST THE EXPECTED MARGIN (ruling R4, 2026-09-01)
# ---------------------------------------------------------------------------
#
# Measured first, on the college slate of 2026-09-05, which is what produced
# the ruling: 76% of all 177 picks claimed 70% or better, and on the spread the
# confidence sat exactly where the rung was furthest from the answer -- 77% of
# cross-division games claimed 90%+, against 20% of FBS-against-FBS ones. A
# rung picked by rotation asks "does the home side cover -0.5" of a team
# favoured by sixty, and a record full of those measures the schedule.
#
# So the rung is now the declared rung nearest the expected margin. Two ways
# that could quietly come undone, and this catches both by name:
#
#   1. THE ROTATION COMES BACK. A hash of the game id is a perfectly good
#      rung chooser and an easy thing to reach for; it is allowed ONLY on the
#      path where no rating exists, which is a declared absence.
#   2. THE MARKET CHOOSES IT. Asking at the number the book is offering is the
#      purest form of the anchoring LAW 1 exists to prevent -- and it would
#      not look like cheating, it would look like realism.

#: Choosing a rung by hashing the game id. Named, because a reader who finds
#: this in a diff should be told what it costs rather than what it is.
ROTATION_CHOOSERS = ("stable_index",)


def _is_absence_test(test: ast.expr, parameters: set[str]) -> bool:
    """True for `<parameter> is None` -- the one branch a rotation may sit in."""
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and isinstance(test.left, ast.Name)
        and test.left.id in parameters
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    )


def rung_selection_faults(source: str, where: str = "questions.py") -> list[str]:
    """Every way a spread rung could stop being chosen against the margin.

    Reads the source rather than calling the function, because the fault this
    is guarding against is a shape -- a rotation on the live path -- and a
    behavioural check would have to guess which margins to try.
    """
    faults: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.endswith("_spread_rung"):
            continue
        arguments = node.args
        parameters = {a.arg for a in
                      (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)}

        def walk(body: list[ast.stmt], guarded: bool) -> None:
            for statement in body:
                if isinstance(statement, ast.If):
                    inside = guarded or _is_absence_test(statement.test, parameters)
                    walk(statement.body, inside)
                    walk(statement.orelse, guarded)
                    continue
                for inner in ast.walk(statement):
                    if isinstance(inner, ast.If):
                        break
                    if (isinstance(inner, ast.Call)
                            and isinstance(inner.func, ast.Name)
                            and inner.func.id in ROTATION_CHOOSERS
                            and not guarded):
                        faults.append(
                            f"{where}:{node.name}: chooses the rung with "
                            f"{inner.func.id}(), a rotation, on the path where a "
                            f"margin IS available. The rung would be picked by a "
                            f"hash of the game id rather than by what the model "
                            f"expects to happen, which is what made 77% of "
                            f"cross-division spreads claim 90%+."
                        )
                    if isinstance(inner, ast.Name) and inner.id in FORBIDDEN_IDENTIFIERS:
                        faults.append(
                            f"{where}:{node.name}: names {inner.id!r}, a market "
                            f"value. LAW 1: the question may not be formed at the "
                            f"number the market is offering."
                        )
                    if (isinstance(inner, ast.Attribute)
                            and inner.attr in FORBIDDEN_IDENTIFIERS):
                        faults.append(
                            f"{where}:{node.name}: reads .{inner.attr}, a market "
                            f"value. LAW 1: the question may not be formed at the "
                            f"number the market is offering."
                        )
        walk(node.body, guarded=False)
    return faults


#: A rung function that rotates unconditionally -- the shape this replaced --
#: and the shape that is correct. Checked at import like every other scanner
#: (ruling, 2026-08-31): a guard that cannot see its own known-positive passes
#: everything, which has happened here four times.
RUNG_FIXTURE_POSITIVE = (
    "def cfb_spread_rung(game_id, expected_margin=None):\n"
    "    return LADDER[stable_index(game_id, len(LADDER))]\n"
)
RUNG_FIXTURE_NEGATIVE = (
    "def cfb_spread_rung(game_id, expected_margin=None):\n"
    "    if expected_margin is None:\n"
    "        return LADDER[stable_index(game_id, len(LADDER))]\n"
    "    return min(LADDER, key=lambda r: abs(r + expected_margin))\n"
)


def check_the_rung_is_chosen_by_margin(root: Path | None = None) -> None:
    path = (root or config.PACKAGE_ROOT) / "model" / "questions.py"
    faults = rung_selection_faults(path.read_text(encoding="utf-8"),
                                   where="model/questions.py")
    if faults:
        raise LawViolation(
            "A RUNG IS NOT BEING CHOSEN AGAINST THE EXPECTED MARGIN (ruling "
            "R4). The rung is the question; a question nobody could get wrong "
            "is not a measurement of anything:"
            + _NL2 + _NL2.join(faults[:10])
        )


def _check_the_rung_scanner_can_see() -> None:
    if not rung_selection_faults(RUNG_FIXTURE_POSITIVE, where="fixture"):
        raise LawViolation(
            "A SCANNER IS BLIND: rung_selection_faults() does not flag an "
            "unconditional rotation, which is the exact shape ruling R4 "
            "replaced. Everything it scans would pass."
        )
    stray = rung_selection_faults(RUNG_FIXTURE_NEGATIVE, where="fixture")
    if stray:
        raise LawViolation(
            "A SCANNER IS OVER-EAGER: rung_selection_faults() flags the "
            "correct shape, so it will fail on good code: " + "; ".join(stray)
        )


_check_the_rung_scanner_can_see()


# ---------------------------------------------------------------------------
# THE DESK'S TWO PROMISES, SCANNED (D5)
# ---------------------------------------------------------------------------
#
# Both are properties a person cannot check by looking. A tile that truncates
# looks like a tile with a short name in it; a selection that moves the frame
# looks like a page that scrolled for some reason. Each shipped once in this
# project's short history, and each was found by measuring a render rather
# than by reading the code.

#: Selectors that live inside the scrolling frame. A truncation rule reaching
#: any of them is the defect: the tile has told the reader there is something
#: it is not showing, and then not shown it.
FRAME_SELECTORS = (".tile", ".desk-frame", ".tiles")

_CSS_ELLIPSIS = re.compile(r"text-overflow\s*:\s*ellipsis")


# ---------------------------------------------------------------------------
# A SCANNER READS CODE, NOT COMMENTS (audit of 2026-09-05)
# ---------------------------------------------------------------------------
#
# Eight source scanners below read `app.js`, `style.css` and `index.html` as
# raw text, and every one of them fired on a COMMENT that named the thing it
# forbids: `/* text-overflow: ellipsis */` truncated nothing and tripped the
# frame scan; `// never .sort( here` inside `applyLive` read as a re-sort.
# The other direction is worse and had already happened once: `tier_chip_faults`
# was satisfied by a comment explaining `chip_label`, so deleting the code left
# the guard green. A comment recording a removal must be able to outlive it,
# and a comment must never stand in for the code it describes.
#
# So the text is blanked of its comments before any scanner reads it. BLANKED,
# not deleted: every character becomes a space and every newline stays, so a
# line number a scanner reports is still the line in the file.
#
# THE STRIPPER IS PROVED AT IMPORT, the same way the withdrawal scanners are:
# a `//` inside a string literal is not a comment and must survive.

def _without_comments(text: str, kind: str) -> str:
    """`text` with its comments blanked. `kind` is "js", "css" or "html"."""
    if kind == "css":
        return re.sub(r"/\*.*?\*/", lambda m: _blank(m.group(0)), text, flags=re.S)
    if kind == "html":
        return re.sub(r"<!--.*?-->", lambda m: _blank(m.group(0)), text, flags=re.S)
    if kind != "js":
        raise ValueError(f"no comment syntax known for {kind!r}")
    out = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(_blank(text[i:end]))
            i = end
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append(_blank(text[i:end]))
            i = end
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _blank(fragment: str) -> str:
    """Spaces in place of every character, newlines kept."""
    return "".join(c if c == "\n" else " " for c in fragment)


def _check_the_comment_stripper_can_see() -> None:
    problems = []
    js = "const u = 'http://x/y'; // a comment naming .sort(\nlet z = 1; /* .sort( */"
    seen = _without_comments(js, "js")
    if "http://x/y" not in seen:
        problems.append("the stripper eats a // inside a string literal")
    if ".sort(" in seen:
        problems.append("the stripper leaves a // or /* */ comment standing")
    if seen.count("\n") != js.count("\n") or len(seen) != len(js):
        problems.append("the stripper changes line structure")
    if "ellipsis" in _without_comments("a { /* text-overflow: ellipsis */ }", "css"):
        problems.append("the stripper leaves a CSS comment standing")
    if "calls" in _without_comments('<nav><!-- <a data-route="calls"> --></nav>', "html"):
        problems.append("the stripper leaves an HTML comment standing")
    if problems:
        raise LawViolation("THE COMMENT STRIPPER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_comment_stripper_can_see()



def frame_truncation_faults(css: str) -> list[str]:
    """Every rule that would truncate something inside the frame."""
    css = _without_comments(css, "css")
    faults = []
    for block in css.split("}"):
        if "{" not in block:
            continue
        selector, _, body = block.partition("{")
        selector = selector.strip().split("*/")[-1].strip()
        if not _CSS_ELLIPSIS.search(body):
            continue
        if any(part in selector for part in FRAME_SELECTORS):
            faults.append(
                f"{selector!r} truncates with an ellipsis, and it is inside the "
                f"desk frame. A tile grows instead: the whole point of the "
                f"frame is that the slate scrolls, so there is room."
            )
    return faults


#: A rule that truncates a tile, and the rule that relaxes one. Checked at
#: import like every scanner (ruling, 2026-08-31).
CSS_FIXTURE_POSITIVE = ".tile-match { text-overflow: ellipsis; }"
CSS_FIXTURE_NEGATIVE = ".desk-frame * { text-overflow: clip; }"


def check_no_truncation_in_the_frame(path: Path | None = None) -> None:
    path = (path or (config.PACKAGE_ROOT / "web" / "style.css"))
    faults = frame_truncation_faults(Path(path).read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "A TILE TRUNCATES. The frame scrolls precisely so that nothing has "
            "to be cut off, and an ellipsis is the interface admitting it is "
            "hiding something from a reader who cannot ask for the rest:"
            + _NL2 + _NL2.join(faults[:8])
        )


#: THE PROMISE, RE-POINTED FROM THE DESK TO THE CARDS (2026-09-04).
#:
#: It used to be about `selectTile`: selecting a pick filled the rail, and if
#: the frame's scroll position was not saved and restored, a reader half way
#: down a 177-pick slate was thrown back to the top for the crime of looking at
#: something. There is no rail and no frame now.
#:
#: THE SAME PROMISE SURVIVES IN A DIFFERENT MECHANISM. A card expands IN PLACE,
#: and the way that breaks is for the toggle to re-render the slate instead of
#: revealing a body that is already there -- which rebuilds every node, resets
#: the scroll, and moves the card the reader just tapped. So the guard reads
#: the toggle and refuses a re-render inside it.
#: RE-POINTED AGAIN 2026-09-08, at the CARD_FACE card's Why expander.
#: `pickCard` wrote `const toggle = () => {...}` and was removed with the
#: old grid; the new card writes `more.onclick = () => {...}`. BOTH SHAPES
#: ARE ACCEPTED so the fixtures below -- which are what prove this scanner
#: can see at all -- keep working while the shipped card is really read.
_JS_CARD_TOGGLE = re.compile(
    r"(?:const\s+toggle|more\.onclick)\s*=\s*\(\)\s*=>\s*\{"
    r"(?P<body>.*?)\n\s*\};", re.S)

#: What a toggle may not do. Each of these rebuilds the slate from the payload,
#: which is the one thing that cannot happen while a reader is mid-tap.
_REBUILDERS = ("renderGames(", "innerHTML")


def selection_moves_the_frame(js: str) -> list[str]:
    """True-ish when opening a card would cost the reader their place."""
    js = _without_comments(js, "js")
    match = _JS_CARD_TOGGLE.search(js)
    if match is None:
        return ["the card's expand toggle is not in the renderer at all, so "
                "nothing says what happens when a reader opens a pick"]
    body = match.group("body")
    faults = []
    for rebuilder in _REBUILDERS:
        if rebuilder in body:
            faults.append(
                f"the card's toggle calls {rebuilder!r}, which rebuilds the "
                f"slate rather than revealing a body that is already on the "
                f"page. Every node is replaced, the scroll position resets, "
                f"and the card the reader just tapped moves out from under "
                f"them.")
    # HOW A CARD OPENS, in either of the two correct ways (2026-09-08). The
    # old card toggled a class and the stylesheet drew from it; the CARD_FACE
    # card sets `hidden` on a body that is already in the tree, which the
    # stylesheet's own reset draws. Requiring `classList` would fail the
    # shipped card for using the newer of two right answers.
    #
    # NEITHER is still a fault: then nothing in the toggle says how the card
    # opens, and the reveal is happening somewhere this guard cannot see.
    if "classList" not in body and "hidden" not in body:
        faults.append(
            "the card's toggle neither toggles a class nor sets `hidden`, so "
            "whatever it does to open the card is not the in-place reveal the "
            "stylesheet is written for.")
    return faults


SELECT_FIXTURE_POSITIVE = """
    const toggle = () => {
      state.openCard = c.prediction_id;
      renderGames();
    };
"""
SELECT_FIXTURE_NEGATIVE = """
    const toggle = () => {
      if (!built) { buildCardBody(body, c); built = true; }
      const open = !card.classList.contains('open');
      card.classList.toggle('open', open);
      head.setAttribute('aria-expanded', String(open));
    };
"""


def check_selection_leaves_the_frame_alone(path: Path | None = None) -> None:
    path = (path or (config.PACKAGE_ROOT / "web" / "app.js"))
    faults = selection_moves_the_frame(Path(path).read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "SELECTING A PICK WOULD MOVE THE SLATE. Selection is not "
            "navigation; a reader who loses their place has been punished for "
            "looking at something:" + _NL2 + _NL2.join(faults))


def _check_the_desk_scanners_can_see() -> None:
    problems = []
    if not frame_truncation_faults(CSS_FIXTURE_POSITIVE):
        problems.append("frame_truncation_faults misses a truncated tile")
    if frame_truncation_faults(CSS_FIXTURE_NEGATIVE):
        problems.append("frame_truncation_faults flags `text-overflow: clip`, "
                        "which is the rule that FIXES truncation")
    if not selection_moves_the_frame(SELECT_FIXTURE_POSITIVE):
        problems.append("selection_moves_the_frame misses a card toggle that "
                        "re-renders the slate instead of expanding in place")
    if selection_moves_the_frame(SELECT_FIXTURE_NEGATIVE):
        problems.append("selection_moves_the_frame flags a card toggle that "
                        "correctly reveals a body already on the page")
    if problems:
        raise LawViolation(
            "A SCANNER IS BLIND: a desk guard does not do what it says, so "
            "everything it scans will pass:" + _NL2 + _NL2.join(problems))


_check_the_desk_scanners_can_see()


# ---------------------------------------------------------------------------
# THE PICK SAYS THE PICK (ruling E1)
# ---------------------------------------------------------------------------
#
# The fourth appearance of one defect, and the first to get past `side_named`.
# On 2026-09-01 nine live college spread cards read "Nebraska Cornhuskers
# covers -24.5" over a stored prediction that Nebraska would FAIL to cover.
# The name was right. The VERB was wrong: college football stores that side as
# "fail to cover", `SIDE_WORDS` had only "not_cover", and the lookup was
# `SIDE_WORDS.get(side, "covers")` -- so an unrecognised side silently became
# the other side's claim, on the card, at high confidence.
#
# Every standing scan passed while that shipped, because they all check that
# prose goes THROUGH the humaniser. None checked that the humaniser had words
# for what it was handed. These two do.


def summed_records(summary: dict) -> list[str]:
    """A record spanning two sports, anywhere in the tab payload (LAW 6).

    The tabs are where a combined figure would be most tempting and most
    wrong. Each tab's line must name its own sport and no other, and the
    payload must carry no total: a number mixing NFL spreads with MLB
    moneylines describes neither, and it flatters reliably, because the easy
    sport dilutes the hard one.
    """
    faults = []
    for key in summary:
        if key.lower() in ("total", "combined", "overall", "all_sports"):
            faults.append(
                f"the tab payload carries {key!r}, which can only be a figure "
                f"spanning sports -- LAW 6 forbids it and it would be the "
                f"first number a reader saw")
    labels = {s.get("label") for s in summary.get("sports", [])}
    for sport in summary.get("sports", []):
        line = sport.get("record_line") or ""
        for other in labels - {sport.get("label")}:
            if other and other in line:
                faults.append(
                    f"the {sport.get('label')} tab reads {line!r}, which names "
                    f"{other} as well -- one tab, one sport")
    return faults


# ---------------------------------------------------------------------------
# ONE MOTION VOCABULARY (L3)
# ---------------------------------------------------------------------------
#
# Motion on this page has one job: to say that something CHANGED, so a reader
# who looked away knows where to look. Everything else it could do here is a
# way of editorialising -- a bounce on a win, a glow on a big number, a shake
# on a loss -- and this project reports a probability and keeps score of it.
# A loss has to look like a loss, quietly.
#
# The vocabulary is deliberately small enough to hold in your head, which is
# also what makes it scannable: two durations, one curve, four properties, one
# keyframe. Anything else is a fault by definition rather than by judgement.

#: Properties that may be animated. Each of these can be composited without
#: laying the page out again; `height`, `width`, `max-height` and `top` cannot,
#: which is why an expanding box is the classic janky animation and why the
#: one that already existed here was removed rather than retimed.
ANIMATABLE = frozenset({
    "opacity", "transform", "background-color", "border-color", "color",
})

#: The longest anything may take. 150ms is at the edge of registering as
#: instant; 200ms is for a panel replacing its whole contents.
MOTION_MAX_MS = 200

#: The one curve, and the one keyframe.
MOTION_EASE = "ease-out"
ALLOWED_KEYFRAMES = frozenset({"live-pulse"})
#: ONE-SHOT KEYFRAMES (motion, 2026-09-25): a small pop when a pick is marked
#: taken, and nothing else. They run once, under the ceiling, and never loop.
ONE_SHOT_KEYFRAMES = frozenset({"pop"})

#: THE CEILING GOVERNS CHANGES; THE PULSE HAS A FLOOR INSTEAD.
#:
#: This distinction was forced by the scan flagging the live pulse itself on
#: its first run, and it is a real difference rather than an exemption. A
#: transition is a change COMPLETING: past about a fifth of a second it stops
#: reading as instant and becomes something a reader waits for. A pulse is a
#: loop saying "still happening", and a 200ms loop is a 5Hz strobe -- visually
#: horrible, and a genuine hazard for photosensitive readers.
#:
#: So the one repeating animation on the page is required to be SLOW. The
#: fault the guard looks for there is a pulse that is too fast, which is the
#: opposite of the fault it looks for everywhere else.
MOTION_PULSE_MIN_MS = 1000

#: THE MOVEMENT BOUND (R4, 2026-09-05). A panel may arrive from up to two per
#: cent below and may scale by up to two per cent; anything larger is a
#: gesture, and this page makes none. Per cent only, so the bound can be read
#: off the declaration rather than off a pixel measurement at one width.
MOTION_MAX_TRANSLATE_PCT = 2.0
MOTION_MAX_SCALE_DELTA = 0.02
_CSS_TRANSFORM = re.compile(r"(?<![a-z-])transform\s*:\s*([^;}]+)")
_CSS_TRANSLATE = re.compile(r"translate([XY]?)\(\s*([-+]?[0-9.]+)([a-z%]*)")
_CSS_SCALE = re.compile(r"scale\(\s*([0-9.]+)")
_CSS_OTHER_TRANSFORM = re.compile(r"\b(rotate|skew[XY]?|translateX|translate3d|matrix)\(")


def transform_faults(css: str) -> list[str]:
    """Every transform on the page outside the movement bound."""
    faults = []
    for match in _CSS_TRANSFORM.finditer(css):
        value = match.group(1).strip()
        where = f"transform {value[:48]!r}"
        if value in ("none", "initial", "inherit"):
            continue
        for kind, amount, unit in _CSS_TRANSLATE.findall(value):
            if kind == "X":
                faults.append(f"{where}: sideways movement is a gesture; a panel "
                              f"arrives from below or not at all.")
                continue
            if unit != "%":
                faults.append(
                    f"{where}: {amount}{unit or ''} is not a percentage. The bound "
                    f"is {MOTION_MAX_TRANSLATE_PCT:g}% and a pixel figure cannot "
                    f"be held to it at every width.")
            elif abs(float(amount)) > MOTION_MAX_TRANSLATE_PCT:
                faults.append(
                    f"{where}: {amount}% is past the {MOTION_MAX_TRANSLATE_PCT:g}% "
                    f"movement bound. A panel arrives; it does not travel.")
        for amount in _CSS_SCALE.findall(value):
            if abs(float(amount) - 1.0) > MOTION_MAX_SCALE_DELTA + 1e-9:
                faults.append(
                    f"{where}: scale({amount}) is past the "
                    f"{MOTION_MAX_SCALE_DELTA * 100:g}% bound. Nothing on this "
                    f"page grows to be noticed.")
        for name in _CSS_OTHER_TRANSFORM.findall(value):
            faults.append(f"{where}: {name}() is a gesture, and this page makes none.")
    return faults

_CSS_TOKEN = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")
_CSS_TRANSITION = re.compile(r"transition(?:-duration|-property|-timing-function)?"
                             r"\s*:\s*([^;}]+)")
_CSS_ANIMATION = re.compile(r"animation(?:-duration|-timing-function)?\s*:\s*([^;}]+)")
_CSS_KEYFRAMES = re.compile(r"@keyframes\s+([A-Za-z0-9_-]+)")
_CSS_MS = re.compile(r"([0-9.]+)(ms|s)\b")
_CSS_CURVE = re.compile(r"cubic-bezier\([^)]*\)|\bease-in-out\b|\bease-in\b|"
                        r"\bease-out\b|\blinear\b|\bease\b|\bsteps\([^)]*\)")


def _resolve_tokens(css: str) -> dict:
    """The `--name: value` declarations, so `var(--motion-state)` can be read.

    Without this the scan would see `var(--motion-state)` and have no idea
    whether it is 150ms or four seconds -- which is the state a guard is in
    when it checks the shape of a declaration rather than its meaning.
    """
    tokens = {}
    for name, value in _CSS_TOKEN.findall(css):
        tokens[name] = value.strip()
    # One pass of substitution is enough for a vocabulary one level deep, and
    # a deeper one would be a reason to simplify the vocabulary.
    for name, value in list(tokens.items()):
        for other, other_value in tokens.items():
            value = value.replace(f"var(--{other})", other_value)
        tokens[name] = value
    return tokens


def _expand(value: str, tokens: dict) -> str:
    for name, token_value in tokens.items():
        value = value.replace(f"var(--{name})", token_value)
    return value


def motion_faults(css: str) -> list[str]:
    """Every animation on the page that is outside the declared vocabulary."""
    css = _without_comments(css, "css")
    tokens = _resolve_tokens(css)
    faults = []

    def check_duration(where: str, value: str) -> None:
        for amount, unit in _CSS_MS.findall(value):
            ms = float(amount) * (1000 if unit == "s" else 1)
            if ms > MOTION_MAX_MS:
                faults.append(
                    f"{where}: {amount}{unit} is longer than the {MOTION_MAX_MS}ms "
                    f"ceiling. Motion here says that something changed; past "
                    f"about a fifth of a second it becomes something to wait for.")

    def check_curve(where: str, value: str) -> None:
        for curve in _CSS_CURVE.findall(value):
            if curve.strip() != MOTION_EASE:
                faults.append(
                    f"{where}: {curve!r} is a second easing curve. One curve, "
                    f"{MOTION_EASE!r}, so that everything on the page arrives "
                    f"the same way.")

    for match in _CSS_TRANSITION.finditer(css):
        value = _expand(match.group(1).strip(), tokens)
        where = f"transition {match.group(1).strip()[:48]!r}"
        check_duration(where, value)
        check_curve(where, value)
        for part in value.split(","):
            prop = part.strip().split()[0] if part.strip() else ""
            if (prop and not prop[0].isdigit() and prop not in ("all", "none")
                    and not prop.startswith("var(")
                    and not _CSS_MS.match(prop) and prop not in ANIMATABLE
                    and not _CSS_CURVE.fullmatch(prop)):
                faults.append(
                    f"{where}: {prop!r} may not be animated. Animating it "
                    f"forces the page to be laid out again on every frame; "
                    f"the vocabulary is {sorted(ANIMATABLE)}.")

    for match in _CSS_ANIMATION.finditer(css):
        value = _expand(match.group(1).strip(), tokens)
        where = f"animation {match.group(1).strip()[:48]!r}"
        check_curve(where, value)
        pulse = any(name in value for name in ALLOWED_KEYFRAMES)
        if not pulse:
            check_duration(where, value)
            if "infinite" in value:
                faults.append(
                    f"{where}: a one-shot keyframe may not loop. The only thing "
                    f"that repeats is the live mark.")
            continue
        # The one repeating animation, held to its floor rather than the
        # ceiling. See MOTION_PULSE_MIN_MS.
        for amount, unit in _CSS_MS.findall(value):
            ms = float(amount) * (1000 if unit == "s" else 1)
            if ms < MOTION_PULSE_MIN_MS:
                faults.append(
                    f"{where}: a {amount}{unit} pulse is a strobe. The live "
                    f"mark loops at {MOTION_PULSE_MIN_MS}ms or slower -- it "
                    f"says a game is being played, it does not flash for "
                    f"attention.")

    for name in _CSS_KEYFRAMES.findall(css):
        if name not in ALLOWED_KEYFRAMES and name not in ONE_SHOT_KEYFRAMES:
            faults.append(
                f"@keyframes {name!r} is not in the vocabulary. The only thing "
                f"on this page that repeats is the mark saying a game is being "
                f"played right now; anything else that loops is decoration.")
    faults.extend(transform_faults(css))
    return faults


#: A 400ms bounce on a chip, and the same chip done correctly. Checked at
#: import like every scanner (ruling, 2026-08-31).
MOTION_FIXTURE_POSITIVE = """
@keyframes bounce { 50% { transform: scale(1.4); } }
.tile-verdict { animation: bounce 400ms ease-in-out; }
"""
#: And the other direction: the one allowed keyframe, run fast enough to
#: strobe. Both are faults; they are opposite faults.
MOTION_FIXTURE_STROBE = """
.tile-live { animation: live-pulse 200ms ease-out infinite; }
"""
MOTION_FIXTURE_NEGATIVE = """
:root { --motion-state: 150ms; --motion-ease: ease-out; }
.tile-verdict { transition: opacity var(--motion-state) var(--motion-ease); }
"""


def check_motion_vocabulary(path: Path | None = None) -> None:
    path = path or (config.PACKAGE_ROOT / "web" / "style.css")
    faults = motion_faults(Path(path).read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "MOTION OUTSIDE THE VOCABULARY. Movement on this page says that "
            "something changed and nothing else -- it never celebrates a win "
            "or softens a loss, because the record has to read the same "
            "whichever it is:" + _NL2 + _NL2.join(faults[:8]))


def _check_the_motion_scanner_can_see() -> None:
    problems = []
    found = motion_faults(MOTION_FIXTURE_POSITIVE)
    if not found:
        problems.append("motion_faults misses a 400ms bounce on a chip")
    if not motion_faults(MOTION_FIXTURE_STROBE):
        problems.append("motion_faults misses a live mark strobing at 200ms")
    stray = motion_faults(MOTION_FIXTURE_NEGATIVE)
    if stray:
        problems.append(f"motion_faults flags correct motion: {stray}")
    if problems:
        raise LawViolation(
            "A SCANNER IS BLIND: the motion guard does not do what it says:"
            + _NL2 + _NL2.join(problems))


_check_the_motion_scanner_can_see()


#: Tokens that mean something other than "this is happening now". Green is the
#: positive value AND the interactive accent, and it has exactly those two
#: jobs -- a game being played is neither good news nor a control. Red is a
#: negative value. A live mark drawn in either is the interface having an
#: opinion about a game that has not finished.
# THE COLOUR LAW (GRIDIRON_16 R2)
# ---------------------------------------------------------------------------
#
# GREEN MEANS A PICK WON. RED MEANS A PICK LOST. Nothing else may wear either.
#
# The tokens were called `--green` and `--red` until 2026-09-02, and a colour
# named after its hue is a colour anyone can reach for when they want
# something to look important -- which is what happened. Green was ALSO the
# interactive accent: the active tab, every link, every focus ring, the
# pressed segment. Red was ALSO every warning: a failed task, a stale feed, a
# notice border, the error box.
#
# The cost is not aesthetic. When the accent and the positive value share a
# colour, a page full of controls reads as a page full of wins, and the one
# place the colour carries information is the place it is least noticed. The
# rename to `--win` and `--loss` makes the misuse visible in the source, and
# this scan makes it fail.

#: The value tokens and their aliases. `--pos` and `--neg` were the older
#: names; they are gone from the stylesheet and stay on this list so a rule
#: that reaches for them fails rather than resolving to nothing.
_WIN_TOKENS = ("--win", "--win-wash", "--pos")
_LOSS_TOKENS = ("--loss", "--loss-wash", "--neg")

#: THE COLOUR LAW AS AMENDED BY THE OPERATOR ON 2026-09-24 (GRIDIRON_BOARD),
#: recorded in CLAUDE.md with the text it replaced beneath it.
#:
#: Each colour has exactly two jobs and the FORM says which:
#:
#:   a green OUTLINE glow   a pick clears the bar          `.sig-clears`
#:   a red OUTLINE glow     it costs the operator after fees   `.sig-costs`
#:   a SOLID green fill     a pick won                     `.sig-won`
#:   a SOLID red fill       a pick lost                    `.sig-lost`
#:
#: AND THE FORM ROW (ruling d, 2026-09-25, the ruling of 2026-09-08
#: standing): the W and L of a club's last five keep green and red, as the
#: LETTER'S INK ONLY. `.fmark.win` may set `color` to `--win` and
#: `.fmark.loss` `color` to `--loss`; a form mark filled or ringed is refused,
#: because a solid green W is a pick that won, which a club's game is not.
#:
#: Nothing else uses those colours: not a link, not a tally, not a warning,
#: not the edge line. So the scan reads the selector for the state AND the
#: declaration for the form: an outline state painted as a fill is a pick
#: that merely clears the bar dressed as one that won, and a verdict drawn as
#: an outline is a win that looks like a price comparison.
_OUTLINE_WIN = re.compile(r"\.sig-clears\b")
_OUTLINE_LOSS = re.compile(r"\.sig-costs\b")
_FILL_WIN = re.compile(r"\.sig-won\b")
_FILL_LOSS = re.compile(r"\.sig-lost\b")
_FORM_WIN = re.compile(r"\.fmark\.win\b")
_FORM_LOSS = re.compile(r"\.fmark\.loss\b")
#: The one declaration a form mark may make with its colour.
_INK_PROPERTIES = ("color",)

#: Declarations that draw an OUTLINE: a ring, a glow, a border. Anything
#: else -- background, color, fill, stroke -- is a fill or ink.
_OUTLINE_PROPERTIES = ("box-shadow", "outline", "border")
_FILL_PROPERTIES = ("background", "background-color")

#: Anything a person clicks, focuses or navigates by. These may never carry a
#: value colour, whatever their class happens to be called.
_INTERACTIVE_SELECTOR = re.compile(
    r":hover|:focus|:focus-visible|:active|\[aria-pressed|"
    r"(?:^|[\s,>])(?:a|button|nav|summary|select|input)\b|"
    r"\.seg\b|\.tab\b|\.expand\b|\.row-more\b|\.pager\b")

_CSS_RULE = re.compile(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")


_FILTERED_COUNT = re.compile(r"\b(\d+)\s+of\s+(\d+)\b")


_COVERAGE_COUNTS = re.compile(r"Rested on (\d+) of (\d+)")


def coverage_line_faults(cards) -> list[str]:
    """A "what it knew" line that does not match the row it describes.

    The line is a claim ABOUT THE ROW. A card saying it rested on everything
    while its own factor vector records an absence reads as provenance and is
    a decoration, and a reader deciding whether to trust a pick made without
    the starter has only that sentence to go on.
    """
    faults = []
    for card in cards:
        said = (card or {}).get("what_it_knew") or ""
        found = _COVERAGE_COUNTS.search(said)
        if not found:
            continue
        counts = (card or {}).get("factor_counts")
        if isinstance(counts, dict):
            present = int(counts.get("present") or 0)
            total = int(counts.get("total") or 0)
        else:
            # A raw row rather than a card. The planting uses this shape, and
            # so would anything checking the record directly.
            try:
                payload = json.loads((card or {}).get("factors_json") or "{}")
            except ValueError:
                continue
            present = len(payload.get("present") or [])
            total = present + len(payload.get("absent") or [])
        if not total:
            # NOTHING TO COMPARE AGAINST is not a disagreement. A card that
            # carries a sentence and no counts is checked by the plain-words
            # scan, not by this one, and inventing a verdict here would fire
            # on every card in the record -- which it did, on first run.
            continue
        claimed_present, claimed_total = int(found.group(1)), int(found.group(2))
        if (claimed_present, claimed_total) != (present, total):
            faults.append(
                f"a card says {said.split('.')[0]!r} while its row records "
                f"{present} of {total}. The line is a claim about the row, and "
                f"this one is not true of it.")
    return faults


def tier_count_faults(payload: dict) -> list[str]:
    """A filtered count line that does not say what it filtered OUT of.

    PICKS NOW OPENS FILTERED (ruling R2, 2026-09-02): STRONG by default rather
    than the whole slate. That makes this the highest-consequence sentence on
    the page, because the reader did not choose the filter and may not notice
    it. "4 picks" on a 46-pick night reads as a quiet Tuesday; "STRONG - 4 of
    46 picks" reads as a narrow band, which is what it is.

    So the rule is structural rather than a habit of composition: every count
    line keyed to a tier must name TWO numbers, the part and the whole, and the
    whole must not be smaller than the part. An unfiltered line names one
    number and is left alone -- there is nothing hidden behind it.
    """
    faults = []
    default = payload.get("default_tier") or ""
    lines = (payload.get("glance") or {}).get("count_lines") or {}
    for key, line in sorted(lines.items()):
        tier = key.split("|", 1)[-1]
        if not tier:
            continue
        found = _FILTERED_COUNT.search(line or "")
        if not found:
            why = ("Picks opens on this band by default, so a reader who "
                   "never chose a filter sees this number as the size of the "
                   "slate."
                   if tier == default else
                   "A reader who taps a band still needs to know what they "
                   "narrowed it out of.")
            faults.append(
                f"the count line for {key!r} reads {line!r}, which names no "
                f"denominator. {why} Say what it is part of.")
            continue
        shown, total = int(found.group(1)), int(found.group(2))
        if shown > total:
            faults.append(
                f"the count line for {key!r} reads {line!r}: {shown} shown out "
                f"of {total}. A part cannot exceed its whole.")
    return faults


def _declarations(body: str) -> list[tuple[str, str]]:
    """(property, value) pairs of a rule body, lower-cased properties."""
    out = []
    for piece in body.split(";"):
        if ":" not in piece:
            continue
        prop, _, value = piece.partition(":")
        out.append((prop.strip().lower(), value.strip()))
    return out


def colour_law_faults(css: str) -> list[str]:
    """Every rule that paints something a value colour it is not entitled to.

    Four signals, two colours, two forms (amended 2026-09-24). A rule may use
    `--win` only if its selector names `.sig-clears` and the token sits in an
    outline declaration, or names `.sig-won` and the token sits in a fill;
    `--loss` the same way with `.sig-costs` and `.sig-lost`. Everything else
    is a fault by name, interactive selectors first.
    """
    css = _without_comments(css, "css")
    faults = []
    for match in _CSS_RULE.finditer(css):
        selector = match.group("selector")
        selector = selector.split("*/")[-1].strip()
        if not selector or selector.startswith("@"):
            continue
        # `:root` DECLARES the tokens; it does not paint anything with them.
        if selector == ":root" or selector.endswith(":root"):
            continue
        body = match.group("body")
        used_win = [t for t in _WIN_TOKENS if f"var({t})" in body]
        used_loss = [t for t in _LOSS_TOKENS if f"var({t})" in body]
        if not (used_win or used_loss):
            continue
        one_line = " ".join(selector.split())
        if _INTERACTIVE_SELECTOR.search(selector):
            faults.append(
                f"{one_line!r} is interactive and paints itself "
                f"{', '.join(f'var({t})' for t in used_win + used_loss)}. "
                f"A link, a tab, a focus ring and a pressed segment are none "
                f"of the four signals. Interactive is chrome (R2).")
            continue
        for tokens, colour, outline_sel, fill_sel, form_sel, outline_word, fill_word in (
                (used_win, "green", _OUTLINE_WIN, _FILL_WIN, _FORM_WIN,
                 "clears the bar", "won"),
                (used_loss, "red", _OUTLINE_LOSS, _FILL_LOSS, _FORM_LOSS,
                 "costs the operator after fees", "lost")):
            if not tokens:
                continue
            is_outline = bool(outline_sel.search(selector))
            is_fill = bool(fill_sel.search(selector))
            if form_sel.search(selector) and not (is_outline or is_fill):
                # THE FORM ROW'S LETTER (ruling d, 2026-09-25): ink and
                # nothing else. A filled or ringed W is a pick's signal.
                for prop, value in _declarations(body):
                    if not any(f"var({t})" in value for t in tokens):
                        continue
                    if prop not in _INK_PROPERTIES:
                        faults.append(
                            f"{one_line!r} paints `{prop}` {colour} on a form "
                            f"mark. The form row's W and L wear {colour} as "
                            f"the letter's ink only (ruled 2026-09-25); a "
                            f"{colour} fill or ring on a club's game says a "
                            f"pick {fill_word if prop in _FILL_PROPERTIES else outline_word}, "
                            f"and a club's game is not a pick.")
                continue
            if not (is_outline or is_fill):
                faults.append(
                    f"{one_line!r} uses {', '.join(tokens)} and is none of the "
                    f"four signals. A {colour} OUTLINE means a pick "
                    f"{outline_word}; a SOLID {colour} fill means a pick "
                    f"{fill_word}; the form row's letter is the one other "
                    f"place (ruled 2026-09-25); nothing else wears {colour} "
                    f"(amended 2026-09-24).")
                continue
            for prop, value in _declarations(body):
                if not any(f"var({t})" in value for t in tokens):
                    continue
                in_outline = any(prop.startswith(p) for p in _OUTLINE_PROPERTIES)
                in_fill = prop in _FILL_PROPERTIES
                if is_outline and not is_fill and not in_outline:
                    faults.append(
                        f"{one_line!r} paints `{prop}` {colour}, and its state "
                        f"is an OUTLINE: a pick that {outline_word} wears a "
                        f"{colour} ring, never a fill. Filling it says it "
                        f"{fill_word}.")
                if is_fill and not is_outline and not in_fill:
                    faults.append(
                        f"{one_line!r} draws `{prop}` {colour}, and its state "
                        f"is a FILL: a pick that {fill_word} is filled solid "
                        f"{colour}. An outline says it only {outline_word}.")
    return faults


#: THE FIVE MISUSES THE PLANTINGS REPRODUCE: a green link, a red warning
#: border, a fill on a pick that only clears the bar, an outline on a pick
#: that won, and a form mark FILLED green -- the form row keeps the colour
#: for its letter (ruled 2026-09-25) and for nothing else.
COLOUR_LAW_FIXTURE_POSITIVE = """
.row-more { color: var(--win); text-decoration: none; }
.notices-summary { border-left: 2px solid var(--loss); }
.sig-clears { background: var(--win); }
.sig-won { box-shadow: 0 0 0 1px var(--win); }
.fmark.win { background: var(--win); }
"""
COLOUR_LAW_FIXTURE_NEGATIVE = """
.sig-clears { box-shadow: 0 0 0 1.5px var(--win), 0 0 14px 0 var(--win); }
.sig-costs { box-shadow: 0 0 0 1.5px var(--loss), 0 0 14px 0 var(--loss); }
.sig-won { background: var(--win); color: var(--ink); }
.sig-lost { background: var(--loss); color: var(--ink); }
.fmark.win { color: var(--win); }
.fmark.loss { color: var(--loss); }
.row-more { color: var(--chrome); text-decoration: none; }
"""


# ---------------------------------------------------------------------------
# A PANEL THAT HOLDS TAP TARGETS ARRIVES BY ITS FADE ALONE (operator question
# 20, ruled (A) on 2026-09-27; the board merge's step 2 holds every panel to
# it: "arrival motion on any panel holding tap targets is opacity only")
# ---------------------------------------------------------------------------
#
# THE FLAKE THAT ASKED FOR THIS. The slate's tap-target test failed now and
# then on 43.99951171875px -- 44 less 1/2048. Every control it measures is
# laid out at a whole number of pixels, 44 or more; the Today panel arrived
# from one per cent below its place (R4, 2026-09-05), and on the frames it
# moved it sat a fraction of a pixel off whole, so the browser mapped each
# button's box through that offset and rounded its top and bottom apart:
# 44 read 43.9995 or 44.0005. Measured on 2026-09-27 over twelve market
# switches, 9 of 192 frames read a tap target off whole pixels (3 under 44);
# with the movement removed and the fade kept, 193 of 193 were whole. No CSS
# on the control fixes it -- at 45px, 15 readings were still off whole -- so
# the panel stopped moving. The pixels are proved in the browser, every frame
# (`test_smoke.py::test_no_tap_target_leaves_whole_pixels_on_any_frame_of_
# the_slates_arrival`); this scan holds the stylesheet to the rule in the gate,
# where no browser runs, and a planting proves it.
#
# WHAT AN ARRIVAL IS, read from the stylesheet with its comments blanked:
#   1. ITS START STATE: every rule whose selector carries a class the script
#      puts on a panel to arrive it -- `ARRIVAL_CLASS`, and any other class
#      the page's `arrive` adds, read from app.js. It may carry no movement:
#      no `transform`, `translate`, `scale` or `rotate` other than `none`, and
#      a transition in it names opacity alone.
#   2. ITS TRANSITION: every rule setting a transition that applies to an
#      element such a state names (the selector without the class; its tag
#      and classes read from index.html when it names an id), and every
#      transition that runs at the panel duration, which the vocabulary gives
#      only to a panel swapping its whole contents. It names opacity and
#      nothing else -- not a movement, not `all`, and not a shorthand naming
#      no property, which CSS reads as `all`.
#
# WHICH PANELS HOLD TAP TARGETS, decided: EVERY PANEL THAT ARRIVES. What
# arrives in a panel is built by the script, which no scan of the stylesheet
# reads, so the stricter default takes each to hold them. The one that
# arrives today holds them in its own markup (the fold) and in every card the
# script builds into it (the Why control and the took button). A panel that
# arrives holding none is not something this page has; one would be the
# operator's to rule on, not an exemption written here.
#
# NOT SEEN (FOLLOWUPS): a movement the script sets itself (an inline style,
# `animate()`), an arrival through a class the page's `arrive` does not add, a
# transition declared under a selector naming none of the panel's id, tag or
# classes at less than the panel duration, and a movement on a tap target
# itself rather than on a panel arriving. The browser test reads the slate's
# pixels whatever moves them.

#: The class the page's script puts on a panel for the frame it arrives from
#: (`arrive` in app.js). Any other class `arrive` adds is read from the script.
ARRIVAL_CLASS = "arriving"

#: The properties that move a box on screen: an arrival carrying one slides
#: every control inside the panel off whole pixels on the frames it runs.
MOVEMENT_PROPERTIES = frozenset({"transform", "translate", "scale", "rotate"})

_CSS_TIMING_WORD = re.compile(
    r"^(?:ease|ease-in|ease-out|ease-in-out|linear|step-start|step-end|"
    r"normal|allow-discrete|!important)$")
_CSS_COMPOUND_NAME = re.compile(r"([#.]?)(-?[A-Za-z_][\w-]*)")
_JS_ARRIVE = re.compile(r"function\s+arrive\s*\(")
_JS_CLASS_ADDED = re.compile(r"classList\.(?:add|toggle)\(([^)]*)\)")
_JS_CLASS_NAME = re.compile(r"""(['"`])([A-Za-z_][\w-]*)\1""")


def _split_outside_brackets(text: str, sep: str = ",") -> list[str]:
    """`text` split on `sep` wherever it stands outside () and []."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def _last_compound(selector: str) -> str:
    """The compound a selector matches: the part after its last combinator."""
    depth, last = 0, 0
    for i, ch in enumerate(selector):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in " >+~":
            last = i + 1
    return selector[last:].strip()


def _compound_names(compound: str) -> frozenset:
    """The tag, `#id` and `.class` names of one compound selector. An
    attribute or a pseudo-class may apply either way, so neither narrows it."""
    bare = re.sub(r"\[[^\]]*\]|:[\w-]+(?:\([^)]*\))?", " ", compound)
    return frozenset(prefix + name for prefix, name in _CSS_COMPOUND_NAME.findall(bare))


def _arrival_classes(script: str) -> frozenset:
    """`ARRIVAL_CLASS` and every class the page's `arrive` adds."""
    found = {ARRIVAL_CLASS}
    script = _without_comments(script or "", "js")
    at = _JS_ARRIVE.search(script)
    if at:
        opened = script.find("{", at.end())
        depth, end = 0, len(script)
        for i in range(opened, len(script)):
            if script[i] == "{":
                depth += 1
            elif script[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        for call in _JS_CLASS_ADDED.finditer(script[opened:end]):
            found.update(name for _, name in _JS_CLASS_NAME.findall(call.group(1)))
    return frozenset(found)


def _element_names(markup: str, element_id: str) -> frozenset:
    """The tag and classes index.html gives the element with this id."""
    tag = re.search(r"<([A-Za-z][\w-]*)\b[^>]*\bid\s*=\s*['\"]"
                    + re.escape(element_id) + r"['\"][^>]*>", markup or "")
    if not tag:
        return frozenset()
    names = {tag.group(1).lower()}
    classes = re.search(r"\bclass\s*=\s*['\"]([^'\"]*)['\"]", tag.group(0))
    if classes:
        names.update("." + c for c in classes.group(1).split())
    return frozenset(names)


def _transition_properties(prop: str, value: str) -> list[str]:
    """The properties a `transition` or `transition-property` declaration
    names, `all` for a shorthand part naming none; [] for any other."""
    value = value.replace("!important", " ")
    if prop == "transition-property":
        return [p.strip().lower() for p in _split_outside_brackets(value) if p.strip()]
    if prop != "transition":
        return []
    named = []
    for part in _split_outside_brackets(value):
        words = [w for w in _CSS_CURVE.sub(" ", part).split()
                 if not _CSS_MS.fullmatch(w) and not _CSS_TIMING_WORD.match(w)
                 and not w.startswith("var(")]
        if part.strip():
            named.append(words[0].lower() if words else "all")
    return named


def _runs_at(value: str, ms: float) -> bool:
    return any(float(amount) * (1000 if unit == "s" else 1) == ms
               for amount, unit in _CSS_MS.findall(value))


def arrival_movement_faults(css: str, markup: str = "", script: str = "",
                            where: str = "style.css") -> list[str]:
    """Every movement in the arrival of a panel that holds tap targets --
    every panel that arrives (see the block above) -- named by line and rule."""
    css = _without_comments(css, "css")
    markup = _without_comments(markup or "", "html")
    tokens = _resolve_tokens(css)
    panel_ms = next((float(a) * (1000 if u == "s" else 1)
                     for a, u in _CSS_MS.findall(tokens.get("motion-panel", ""))),
                    float(MOTION_MAX_MS))
    arriving = _arrival_classes(script)
    carries = re.compile(r"\.(?:" + "|".join(sorted(map(re.escape, arriving)))
                         + r")(?![\w-])")
    rules = []
    for match in _CSS_RULE.finditer(css):
        head = match.group("selector").rsplit(";", 1)[-1]
        text = " ".join(head.split())
        if not text or text.startswith("@"):
            continue
        line = css.count(chr(10), 0, match.end("selector")) + 1
        declarations = []
        for part in match.group("body").split(";"):
            if ":" in part:
                prop, value = part.split(":", 1)
                declarations.append((prop.strip().lower(),
                                     _expand(value.strip(), tokens)))
        selectors = [s.strip() for s in _split_outside_brackets(text) if s.strip()]
        rules.append((line, selectors, declarations))

    why = ("A panel that holds tap targets arrives by its fade alone (operator "
           "question 20, 2026-09-27; every panel that arrives is taken to hold "
           "them): a movement of any size puts every control inside it a "
           "fraction of a pixel off whole on the frames it runs, and a 44px "
           "control reads 43.9995px.")
    faults: list[str] = []
    panels: dict[str, frozenset] = {}
    for line, selectors, declarations in rules:
        for selector in selectors:
            if not carries.search(selector):
                continue
            for prop, value in declarations:
                if prop in MOVEMENT_PROPERTIES and value.lower() != "none":
                    faults.append(
                        f"{where}:{line} `{selector}`, the state a panel arrives "
                        f"from, carries `{prop}: {value}`. {why}")
            base = " ".join(carries.sub("", selector).split())
            names = _compound_names(_last_compound(base)) if base else frozenset()
            for name in [n for n in names if n.startswith("#")]:
                names = names | _element_names(markup, name[1:])
            panels[base or "every panel the script arrives"] = names

    for line, selectors, declarations in rules:
        named = [p for prop, value in declarations
                 for p in _transition_properties(prop, value)]
        moving = sorted({p for p in named if p not in ("opacity", "none")})
        if not moving:
            continue
        timed = any(_runs_at(value, panel_ms) for prop, value in declarations
                    if prop in ("transition", "transition-duration"))
        for selector in selectors:
            compound = _last_compound(selector)
            if "::" in compound:
                continue
            if carries.search(selector):
                # A transition in the start state itself.
                whose = [" ".join(carries.sub("", selector).split())
                         or "every panel the script arrives"]
            else:
                # A rule applying to a panel that arrives: every name it asks
                # for is one the panel has (none, for `*`, applies to all).
                own = _compound_names(compound)
                whose = sorted(base for base, names in panels.items()
                               if own <= names)
            if not whose and not timed:
                continue
            what = (f"the panel {', '.join(f'`{w}`' for w in whose)}, which arrives"
                    if whose else
                    f"a panel: it runs at the panel duration, {panel_ms:g}ms, which "
                    f"the vocabulary gives only to a panel swapping its whole "
                    f"contents")
            faults.append(
                f"{where}:{line} `{selector}` transitions "
                f"{', '.join(f'`{p}`' for p in moving)} on {what}; its "
                f"transition names opacity alone. {why}")
    return faults


def check_a_panel_holding_tap_targets_arrives_by_its_fade_alone(
        root: Path | None = None) -> None:
    web = (config.PACKAGE_ROOT if root is None else Path(root)) / "web"
    faults = arrival_movement_faults(
        (web / "style.css").read_text(encoding="utf-8"),
        (web / "index.html").read_text(encoding="utf-8"),
        (web / "app.js").read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "A PANEL THAT HOLDS TAP TARGETS MOVES AS IT ARRIVES. The Today "
            "panel arrives by its fade alone (operator question 20, ruled (A) "
            "on 2026-09-27), and every panel that arrives is held to it:"
            + _NL2 + _NL2.join(faults[:8]))


#: THE ARRIVAL AS IT SHIPPED UNTIL 2026-09-27, and as it ships now. Checked at
#: import, like every scanner.
ARRIVAL_FIXTURE_MOVING = """
:root { --motion-panel: 200ms; --motion-ease: ease-out; }
#today {
  transition: opacity var(--motion-panel) var(--motion-ease),
              transform var(--motion-panel) var(--motion-ease);
}
#today.arriving { opacity: 0; transform: translateY(1%); transition: none; }
"""
ARRIVAL_FIXTURE_FADING = """
:root { --motion-panel: 200ms; --motion-ease: ease-out; }
/* #today.arriving { transform: translateY(1%); } -- a comment is not a rule */
#today { transition: opacity var(--motion-panel) var(--motion-ease); }
#today.arriving { opacity: 0; transition: none; }
.tile { transition: background-color 150ms ease-out, opacity 150ms ease-out; }
"""


def _check_the_arrival_scanner_can_see() -> None:
    problems = []
    moving = arrival_movement_faults(ARRIVAL_FIXTURE_MOVING)
    if not any("carries `transform: translateY(1%)`" in f for f in moving):
        problems.append("it misses the start state one per cent below")
    if not any("transitions `transform`" in f for f in moving):
        problems.append("it misses `transform` in the panel's transition")
    stray = arrival_movement_faults(ARRIVAL_FIXTURE_FADING)
    if stray:
        problems.append(f"it refuses the fade alone: {stray}")
    if problems:
        raise LawViolation(
            "A SCANNER IS BLIND: the arrival scan does not do what it says:"
            + _NL2 + _NL2.join(problems))


_check_the_arrival_scanner_can_see()


_JS_CLASS_SELECTOR = re.compile(
    r"""querySelector(?:All)?\(\s*['"]([^'"]+)['"]""")
_CLASS_IN_SELECTOR = re.compile(r"\.([A-Za-z][A-Za-z0-9_-]*)")


def dangling_reference_faults(conn) -> list[str]:
    """Every foreign key must name a table that exists (E4, 2026-09-03).

    THIS FIRED FOR REAL AND SILENTLY, and the way it happened is the reason it
    is now checked rather than assumed.

    Widening the sport CHECK on `games` renames the table aside, copies, and
    renames back. SQLite helpfully REWRITES EVERY REFERENCING TABLE'S FOREIGN
    KEY to follow the rename -- and it does not rewrite them back. Twelve
    tables holding 311,655 rows were left pointing at `games_narrow`, a table
    that no longer existed.

    NOTHING NOTICED FOR HOURS. Every read worked. The suite was green. Four
    sports rendered. `PRAGMA foreign_key_check` was reporting violations the
    whole time and nobody was asking it. It surfaced only when the UFC market
    fetcher became the first thing in a long while to INSERT into one of the
    twelve, and it surfaced as `no such table: main.games_narrow` from a module
    that has nothing to do with games.

    A BROKEN SCHEMA THAT ONLY BREAKS ON WRITE IS THE WORST KIND, because a
    project that mostly reads will believe it is fine right up until the moment
    it needs to record something.
    """
    faults = []
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    for name in sorted(tables):
        for fk in conn.execute(f'PRAGMA foreign_key_list("{name}")'):
            target = fk["table"] if hasattr(fk, "keys") else fk[2]
            if target not in tables:
                faults.append(
                    f"{name} has a foreign key on a table that does not "
                    f"exist: {target!r}. Reads will work and the first INSERT "
                    f"will fail. This is what a half-finished table rebuild "
                    f"leaves behind.")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        faults.append(
            f"PRAGMA foreign_key_check reports {len(violations)} violation(s). "
            f"The first is in table {violations[0][0]!r}.")
    return faults


def check_no_dangling_references(conn) -> None:
    """Raise when any foreign key points at a table that is not there."""
    faults = dangling_reference_faults(conn)
    if faults:
        raise AssertionError(
            "FOREIGN KEYS POINT AT TABLES THAT DO NOT EXIST:\n  "
            + "\n  ".join(faults))


def dead_selector_faults(js: str, html: str, css: str) -> list[str]:
    """A class the browser is asked for that nothing in the app ever builds.

    THIS IS NOT HYPOTHETICAL. The desk tile's corner was renamed `tile-mkt` ->
    `tile-score` in bd7ac2f and one call site kept the old name, so
    `applyLive` fetched null and threw on EVERY live tick. The throw escaped
    the surrounding forEach, which meant one tile stopped the score update for
    every pick after it on the slate. Nothing failed: the suite was green, the
    page rendered, and the scores simply stopped moving.

    A dead selector is invisible in exactly this way -- `querySelector` answers
    null rather than raising, so the mistake surfaces as silence or as a
    TypeError one line later in a function that did nothing wrong. The scan
    reads every class the JS asks for and fails on any the app never creates,
    in the markup, the stylesheet, or a class= / classList / el() call.
    """
    js = _without_comments(js, "js")
    html = _without_comments(html, "html")
    css = _without_comments(css, "css")
    built = set(re.findall(r"class=['\"]([^'\"]+)['\"]", html))
    made = set()
    for group in built:
        made.update(group.split())
    made.update(re.findall(r"\.([A-Za-z][A-Za-z0-9_-]*)", css))
    # Every class the JS itself builds: el('div', 'tile-num tile-num-absent'),
    # classList.add('x'), className = 'y', and class= in a template string.
    made.update(re.findall(r"classList\.(?:add|toggle|remove)\(\s*['\"]([^'\"]+)['\"]", js))
    for literal in re.findall(r"el\(\s*['\"][^'\"]*['\"]\s*,\s*['\"]([^'\"]*)['\"]", js):
        made.update(literal.split())
    for literal in re.findall(r"className\s*=\s*['\"]([^'\"]+)['\"]", js):
        made.update(literal.split())
    for literal in re.findall(r"class=['\"]([^'\"]+)['\"]", js):
        made.update(literal.split())

    faults = []
    for selector in sorted(set(_JS_CLASS_SELECTOR.findall(js))):
        for name in _CLASS_IN_SELECTOR.findall(selector):
            if name not in made:
                faults.append(
                    f"querySelector({selector!r}) asks for a class '{name}' "
                    f"that nothing in the app builds. It will answer null "
                    f"forever, silently or one TypeError later.")
    return faults


def check_no_dead_selectors(root: Path | None = None) -> None:
    web = (root or config.PACKAGE_ROOT) / "web"
    faults = dead_selector_faults(
        (web / "app.js").read_text(encoding="utf-8"),
        (web / "index.html").read_text(encoding="utf-8"),
        (web / "style.css").read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "A SELECTOR NAMES A CLASS NOTHING BUILDS -- querySelector answers "
            "null rather than raising, so this fails as silence:"
            + _NL2 + _NL2.join(faults))


#: THE DECISIONS THE LAUNCHER MAY MAKE ON FINDING A SERVER ALREADY RUNNING,
#: as (launcher build, server build, what it must do). Declared here rather
#: than read off the launcher's source, because the whole point is to run the
#: real function and check its answer.
#:
#: WHY THIS SCAN EXISTS AT ALL. `attach_decision` has said in its own docstring
#: since it was written that "audit.stale_attach_faults checks by running this
#: function rather than by reading the launcher's source" -- and no such
#: function existed. The comment described a guard nobody had written, which is
#: the shape MENTOR 3 names: a docstring asserting a past change is a claim
#: requiring a test. On 2026-09-03 the missing guard cost a real hour: the app
#: attached to a server reporting no build at all, showed seven nav pages and
#: no sport tabs, and looked entirely healthy while being thirty-five commits
#: behind.
STALE_ATTACH_CASES: tuple[tuple[str | None, str | None, str, str], ...] = (
    ("abc123", "abc123", "attach",
     "the same build is answering; there is nothing to warn about"),
    ("abc123", "def456", "ask",
     "the builds differ, which is the case the guard was written for"),
    ("abc123", None, "ask",
     "a server that cannot report a build is OLDER THAN THE BUILD STAMP, "
     "which is a definite answer and the answer is stale -- not an unknown"),
    (None, "def456", "attach",
     "the launcher cannot read its own build, so nothing is known about the "
     "server; refusing here would make the app unopenable for a reason "
     "nobody could act on"),
    (None, None, "attach",
     "neither is known; the same reasoning"),
)


#: A reference to an audit function inside prose: `audit.check_something`,
#: with or without the backticks. Bounded to identifier characters so a
#: sentence ending "see audit.py" or "gridiron.audit." is not read as a name.
_AUDIT_REFERENCE = re.compile(r"\baudit\.([a-z_][a-z0-9_]*)\b")

#: Names on `audit` that are not functions and are legitimately referenced in
#: prose -- the module's own constants and exception types. A docstring may
#: name these without promising a mechanism.
_AUDIT_PROSE_EXEMPT = frozenset({"py", "LawViolation", "MissingDataDefaulted"})


def docstring_reference_faults(root: Path | None = None) -> list[str]:
    """A docstring that names `audit.<name>` where no such name exists.

    A COMMENT MAY NOT PROMISE A MECHANISM THAT IS NOT THERE, and this rule
    exists because one did. `launcher.attach_decision` said in its own
    docstring that "audit.stale_attach_faults checks by running this function
    rather than by reading the launcher's source" -- and there was no
    `stale_attach_faults`. The sentence read like a guarantee, the reviewer
    who wrote it believed it, and the carve-out it was describing went on to
    let the app open on a five-day-old build.

    That is the shape MENTOR 3 names: "a docstring or comment asserts a past
    change -- treat as a claim requiring a test." This is that test, and it is
    mechanical: every `audit.<name>` written in prose anywhere in the package,
    the tools or the desktop launcher must resolve to something that actually
    exists on `gridiron.audit`.

    READ FROM THE AST, not from the raw text, so a name inside a STRING that
    happens to look like a reference is not confused with a docstring -- and,
    more usefully, so this scan does not fire on its own regex above.
    """
    from gridiron import audit as _audit

    root = root or config.PACKAGE_ROOT
    trees = [root]
    for extra in (root.parent / "tools", root.parent / "desktop"):
        if extra.is_dir():
            trees.append(extra)

    faults: list[str] = []
    for tree in trees:
        for path in sorted(tree.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                parsed = ast.parse(path.read_text(encoding="utf-8"),
                                   filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(parsed):
                if not isinstance(node, (ast.Module, ast.ClassDef,
                                         ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                text = ast.get_docstring(node)
                if not text:
                    continue
                # A NAME WRAPPED ACROSS A LINE IS STILL ONE NAME. Prose in
                # this project is hard-wrapped, so `audit.check_correction_is_
                # isolated` arrives split at the underscore and would read as
                # a promise of `check_correction_is_` -- a phantom invented by
                # the scanner rather than by the author. The join is the first
                # thing this scan learned.
                text = re.sub(r"_[ \t]*\n[ \t]*", "_", text)
                for name in sorted(set(_AUDIT_REFERENCE.findall(text))):
                    if name in _AUDIT_PROSE_EXEMPT:
                        continue
                    if hasattr(_audit, name):
                        continue
                    where = getattr(node, "name", "<module>")
                    faults.append(
                        f"{path.name}:{where} promises `audit.{name}`, which "
                        f"does not exist. A comment may not name a mechanism "
                        f"that is not there: the sentence reads as a guarantee "
                        f"and there is nothing behind it."
                    )
    return faults


def check_docstrings_name_real_guards(root: Path | None = None) -> None:
    faults = docstring_reference_faults(root)
    if faults:
        raise LawViolation(
            "A DOCSTRING PROMISES A GUARD THAT DOES NOT EXIST:"
            + _NL2 + _NL2.join(faults))


def stale_attach_faults() -> list[str]:
    """Run the launcher's own decision function against every case.

    BY RUNNING IT, NOT BY READING IT. A scan that grepped the launcher for the
    word ATTACH would pass on a function that returned it for the wrong
    reason, which is exactly what happened: the code was readable, the comment
    was confident, and the decision was wrong for one input out of five.
    """
    faults: list[str] = []
    try:
        from desktop import launcher
    except Exception as exc:  # noqa: BLE001 - a missing launcher is a fault
        return [f"the launcher could not be imported to check it: "
                f"{type(exc).__name__}: {exc}"]

    for mine, theirs, expected, why in STALE_ATTACH_CASES:
        got = launcher.attach_decision(mine, theirs)
        if got != expected:
            faults.append(
                f"launcher build {mine!r} against server build {theirs!r}: "
                f"expected {expected!r}, got {got!r}. {why}.")
        # AND NO PATH FROM "THEY DIFFER" TO "ATTACH ANYWAY". A caller that has
        # asked gets RESTART; it must never get ATTACH, or the confirmation
        # dialog would be a formality in front of the very failure it exists
        # to prevent.
        if expected == "ask":
            confirmed = launcher.attach_decision(mine, theirs, confirmed=True)
            if confirmed == "attach":
                faults.append(
                    f"launcher build {mine!r} against server build {theirs!r}: "
                    f"confirming the mismatch returned 'attach'. There is no "
                    f"path from 'the builds differ' to 'attach anyway'.")
    return faults


def check_the_launcher_refuses_a_stale_attach() -> None:
    faults = stale_attach_faults()
    if faults:
        raise LawViolation(
            "THE LAUNCHER WOULD SHOW A PHOTOGRAPH -- attaching to a server "
            "that is not running this build, silently:"
            + _NL2 + _NL2.join(faults))


def check_the_default_never_hides_the_count(conn=None) -> None:
    """Every sport's slate, as Picks opens it (R2, 2026-09-02)."""
    from gridiron import db as _db
    from gridiron import views as _views

    conn = conn or _db.connect()
    faults = []
    for sport in config.SPORTS:
        for fault in tier_count_faults(_views.week(conn, sport)):
            faults.append(f"{sport}: {fault}")
    if faults:
        raise LawViolation(
            "PICKS OPENS ON A FILTER NOBODY CHOSE, and a count line does not "
            "say what it narrowed:"
            + _NL2 + _NL2.join(faults))


def check_the_colour_law(path: Path | None = None) -> None:
    path = path or (config.PACKAGE_ROOT / "web" / "style.css")
    faults = colour_law_faults(Path(path).read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "THE COLOUR LAW WAS BROKEN -- a green outline clears the bar, a red "
            "outline costs after fees, a solid green fill won, a solid red fill "
            "lost, and nothing else wears either (amended 2026-09-24):"
            + _NL2 + _NL2.join(faults))


def _check_the_colour_scanner_can_see() -> None:
    problems = []
    hits = colour_law_faults(COLOUR_LAW_FIXTURE_POSITIVE)
    if len(hits) < 5:
        problems.append(
            f"colour_law_faults sees {len(hits)} of the five misuses in its "
            f"positive fixture")
    if colour_law_faults(COLOUR_LAW_FIXTURE_NEGATIVE):
        problems.append("colour_law_faults flags a correct signal: "
                        + "; ".join(colour_law_faults(COLOUR_LAW_FIXTURE_NEGATIVE)))
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_colour_scanner_can_see()


# A RUN LINE'S SIGN MUST AGREE WITH ITS MONEYLINE (ruling R2, 2026-09-02)
# ---------------------------------------------------------------------------
#
# `spread_line` is stated as the expected home margin -- positive when the home
# side is favoured. On MLB rows it was not: 21 of 76 carried the opposite sign.
# Nothing consumed it, because Gridiron asks no run-line question yet, so no
# figure was ever wrong. A build inheriting it would have been, and silently:
# a market comparison drawn against a reversed line looks like a model
# disagreeing with the market on exactly the games it agrees with.
#
# THE MONEYLINE IS THE CHECK because it is unambiguous and already stored. A
# team favoured to win is the team giving runs. Where they disagree, one of
# them is wrong and neither may be assumed.

def run_line_sign_faults(rows) -> list[str]:
    """A run line whose sign contradicts its own moneyline favourite."""
    faults = []
    for row in rows or []:
        spread = row.get("spread_line")
        home_ml, away_ml = row.get("home_moneyline"), row.get("away_moneyline")
        if spread is None or home_ml is None or away_ml is None:
            continue
        if spread == 0:
            continue                    # no run line posted yet (ESPN's 0 placeholder)
        if home_ml == away_ml:
            continue                    # a true pick'em says nothing either way
        home_favoured_by_price = home_ml < away_ml
        home_favoured_by_line = spread > 0
        if home_favoured_by_price != home_favoured_by_line:
            faults.append(
                f"{row.get('game_id')}: the run line is {spread:+.1f} -- the "
                f"home side {'favoured' if home_favoured_by_line else 'getting runs'}"
                f" -- while the moneyline has home {home_ml:+} and away "
                f"{away_ml:+}, which says the opposite. One of them is wrong "
                f"and neither may be assumed: read ESPN's own `favorite` flag.")
    return faults


RUN_LINE_FIXTURE_GOOD = [
    {"game_id": "mlb_1", "spread_line": 1.5,
     "home_moneyline": -162, "away_moneyline": 134},
    {"game_id": "mlb_2", "spread_line": -1.5,
     "home_moneyline": 134, "away_moneyline": -162},
]
RUN_LINE_FIXTURE_CONTRADICTED = [
    {"game_id": "mlb_3", "spread_line": 1.5,
     "home_moneyline": 168, "away_moneyline": -180},
]


def check_run_line_signs(conn, sport: str = "mlb") -> None:
    """Every stored run line for a sport, against its own moneyline."""
    # ONLY THE ROWS THAT CLAIM A VERIFIED SIGN. A row marked 'contradicted'
    # is a KNOWN unknown -- ESPN's own flag and its own price disagree -- and
    # it is recorded that way rather than silently passing a check it cannot
    # meet. A build must refuse those rows; it must not read them as correct.
    rows = [dict(r) for r in conn.execute(
        "SELECT r.game_id, r.spread_line, r.home_moneyline, r.away_moneyline"
        "  FROM market_lines_raw r JOIN games g ON g.id = r.game_id"
        " WHERE g.sport = ? AND r.spread_line IS NOT NULL"
        "   AND COALESCE(r.spread_sign_source, 'unverified') = 'espn-flag'",
        (sport,))]
    faults = run_line_sign_faults(rows)
    if faults:
        raise LawViolation(
            "A RUN LINE CONTRADICTS ITS OWN MONEYLINE:"
            + _NL2 + _NL2.join(faults[:8]))


def _check_the_run_line_scanner_can_see() -> None:
    problems = []
    if run_line_sign_faults(RUN_LINE_FIXTURE_GOOD):
        problems.append("run_line_sign_faults flags a consistent run line")
    if not run_line_sign_faults(RUN_LINE_FIXTURE_CONTRADICTED):
        problems.append("run_line_sign_faults misses a reversed sign")
    if run_line_sign_faults([{"game_id": "x", "spread_line": 1.5,
                              "home_moneyline": -105, "away_moneyline": -105}]):
        problems.append("run_line_sign_faults flags a true pick'em")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_run_line_scanner_can_see()


# FOUR PAGES, AND EVERY OLD ADDRESS STILL LANDS (GRIDIRON_13 P5)
# ---------------------------------------------------------------------------
#
# Seven nav entries was one more decision about where a thing lived every time
# a reader wanted something. Four is the ruling, and a fifth would not announce
# itself -- a nav grows one link at a time, each defensible on its own.
#
# AND NO DEAD LINKS. A route that was removed must REDIRECT, not 404: a link
# somebody bookmarked or wrote down still has to land, and the address bar is
# what tells them where the page went.

#: THE NAV, AS RE-RULED BY THE OPERATOR ON 2026-09-24 (GRIDIRON_BOARD).
#:
#: Two PAGE TABS under the sport tabs -- Games, then Props -- and a MENU
#: holding the three pages a reader opens less often. Four pages in one row
#: was the ruling of GRIDIRON_13 R4 and it held for three weeks; the board
#: brief replaces it with this shape, and the scanner is re-ruled rather than
#: deleted, so a third tab or a fourth menu entry still fails by name.
#:
#: `NAV_PAGES` keeps its name because two tests and a planting call it by
#: that name; it is now the whole ruled set, tabs first, then the menu.
PAGE_TABS = ("games", "props")
MENU_PAGES = ("record", "results", "settings")
NAV_PAGES = PAGE_TABS + MENU_PAGES

#: Every route that was removed, and where it went. The old Picks route was
#: `week`; Live and Today were tabs and groups on it, never routes of their
#: own, and every address a reader may have kept for them lands on Games.
REDIRECTED = {
    "history": "results",
    "factors": "record",
    "versions": "record",
    "schedule": "settings",
    "digest": "games",
    "week": "games",
    "picks": "games",
    "live": "games",
    "today": "games",
}


def nav_faults(js: str, html: str) -> list[str]:
    """A nav that is not the ruled shape, or an old route left to 404.

    `html` is the header's markup: the page tabs are the links inside
    `<nav id="nav">` and the menu's are the links inside `<nav id="menu">`.
    Handed a fragment with only one of them, the scan reports the other as
    missing rather than passing on half a header.
    """
    js = _without_comments(js, "js")
    html = _without_comments(html, "html")
    faults = []

    def links_in(nav_id: str) -> tuple[str, ...]:
        block = re.search(rf'<nav id="{nav_id}".*?</nav>', html, re.S)
        return tuple(re.findall(r'data-route="([a-z-]+)"',
                                block.group(0) if block else ""))

    tabs = links_in("nav")
    if tabs != PAGE_TABS:
        faults.append(
            f"the page tabs are {list(tabs)}, not {list(PAGE_TABS)}. Two tabs "
            f"is the ruling (GRIDIRON_BOARD, 2026-09-24): Games and Props, in "
            f"that order; a nav grows one link at a time, each defensible on "
            f"its own, which is how the old one got to seven.")
    menu = links_in("menu")
    if menu != MENU_PAGES:
        faults.append(
            f"the menu holds {list(menu)}, not {list(MENU_PAGES)}. Record, "
            f"Results and Settings live behind the menu and nothing else "
            f"does (GRIDIRON_BOARD, 2026-09-24).")
    for old, new in REDIRECTED.items():
        if not re.search(rf"{old}\s*:\s*'{new}'", js):
            faults.append(
                f"#/{old} does not redirect to #/{new}. A removed route must "
                f"land, not 404: somebody bookmarked it or wrote it down, and "
                f"the address bar is what tells them where the page went.")
    return faults


def _nav_markup(tabs=PAGE_TABS, menu=MENU_PAGES) -> str:
    """A header fragment in the shipped shape, for the fixtures below."""
    return ('<nav id="nav">' + "".join(
        f'<a href="#/{p}" data-route="{p}">x</a>' for p in tabs) + "</nav>"
        '<nav id="menu">' + "".join(
        f'<a href="#/{p}" data-route="{p}">x</a>' for p in menu) + "</nav>")


NAV_REDIRECTS_GOOD = ("const RENAMED = { "
                      + ", ".join(f"{k}: '{v}'" for k, v in REDIRECTED.items())
                      + " };")
#: A third page tab, which is how a nav starts growing again.
NAV_FIXTURE_A_FIFTH_ITEM = _nav_markup(tabs=PAGE_TABS + ("digest",))
#: A menu that quietly lost Settings.
NAV_FIXTURE_A_SHORT_MENU = _nav_markup(menu=("record", "results"))
NAV_FIXTURE_A_DEAD_LINK = "const RENAMED = { history: 'results' };"


def check_the_nav_is_four_pages(js_path=None, html_path=None) -> None:
    """Raise unless the header is the ruled shape. THE NAME IS HISTORY: it
    ruled four pages from GRIDIRON_13 R4 until the board brief re-ruled the
    header on 2026-09-24, and the name stays so the gate's row and the
    close-outs that cite it still point at the check that fires."""
    js_path = js_path or (config.PACKAGE_ROOT / "web" / "app.js")
    html_path = html_path or (config.PACKAGE_ROOT / "web" / "index.html")
    html = Path(html_path).read_text(encoding="utf-8")
    header = re.search(r"<header.*?</header>", html, re.S)
    faults = nav_faults(Path(js_path).read_text(encoding="utf-8"),
                        header.group(0) if header else html)
    if faults:
        raise LawViolation(
            "THE NAV IS NOT WHAT WAS RULED:" + _NL2 + _NL2.join(faults))


def _check_the_nav_scanner_can_see() -> None:
    problems = []
    if nav_faults(NAV_REDIRECTS_GOOD, _nav_markup()):
        problems.append("nav_faults flags the ruled header")
    if not nav_faults(NAV_REDIRECTS_GOOD, NAV_FIXTURE_A_FIFTH_ITEM):
        problems.append("nav_faults misses a third page tab")
    if not nav_faults(NAV_REDIRECTS_GOOD, NAV_FIXTURE_A_SHORT_MENU):
        problems.append("nav_faults misses a menu that lost a page")
    if not nav_faults(NAV_FIXTURE_A_DEAD_LINK, _nav_markup()):
        problems.append("nav_faults misses a removed route left to 404")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_nav_scanner_can_see()


# THE SIGN-IN SCREEN SHOWS COUNTS, NOT PICKS (GRIDIRON_13 P6)
# ---------------------------------------------------------------------------
#
# The login page carries a per-sport record and how many questions are open,
# because that tells the operator the appliance is alive and working before
# they have typed anything -- which is most of what they open it to find out.
#
# It is also THE ONE PLACE THE RECORD FACES SOMEBODY WHO HAS NOT SIGNED IN.
# So it is written to be worth nothing to them: a win-loss count and a slate
# size. Four things would change that, and this refuses all four -- a
# prediction, a side, a team with a line beside it, and a probability. A count
# is not a tip; any of those is.

_A_PROBABILITY_FIELD = ("prob", "probability", "model_prob", "shown_prob",
                        "claimed", "implied", "market_implied_prob")
_A_PICK_FIELD = ("model_side", "side", "pick", "phrase", "tile_line",
                 "row_title", "reasoning", "line_asked", "subject",
                 "prediction_id", "market_line", "spread")


def login_glance_faults(payload, path: str = "$") -> list[str]:
    """Anything on the sign-in screen that is worth reading to a stranger."""
    faults = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in _A_PICK_FIELD:
                faults.append(
                    f"{path}.{key} puts a PICK on the sign-in screen. That "
                    f"page faces somebody who has not signed in; a win-loss "
                    f"count is worth nothing to them and a side is not.")
            elif lowered in _A_PROBABILITY_FIELD:
                faults.append(
                    f"{path}.{key} puts a PROBABILITY on the sign-in screen. "
                    f"Counts and records only (GRIDIRON_13 P6).")
            faults += login_glance_faults(value, f"{path}.{key}")
        for text in (payload.get("line"), payload.get("note")):
            if text and _A_PERCENT_ON_LOGIN.search(str(text)):
                faults.append(
                    f"{path} states a percentage ({text!r}). The sign-in "
                    f"screen carries counts, not rates -- a percentage is the "
                    f"model's claim about something.")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            faults += login_glance_faults(value, f"{path}[{i}]")
    return faults


_A_PERCENT_ON_LOGIN = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*%")

LOGIN_FIXTURE_GOOD = {
    "sports": [{"sport": "mlb", "label": "MLB", "settled": 70, "won": 45,
                "lost": 25, "open": 46, "n": 70,
                "line": "MLB 45-25 - 46 picks tonight"}],
}
LOGIN_FIXTURE_A_PICK = {
    "sports": [{"sport": "mlb", "label": "MLB", "n": 70,
                "model_side": "win", "line": "Cleveland to win"}],
}
LOGIN_FIXTURE_A_PROBABILITY = {
    "sports": [{"sport": "mlb", "label": "MLB", "n": 70,
                "line": "MLB 45-25", "model_prob": 0.53}],
}
LOGIN_FIXTURE_A_RATE = {
    "sports": [{"sport": "mlb", "label": "MLB", "n": 70,
                "line": "MLB has been right 64% of the time"}],
}


def check_the_login_page_shows_no_pick(payload) -> None:
    faults = login_glance_faults(payload)
    if faults:
        raise LawViolation(
            "A PICK IS ON THE SIGN-IN SCREEN:" + _NL2 + _NL2.join(faults))


def _check_the_login_scanner_can_see() -> None:
    problems = []
    if login_glance_faults(LOGIN_FIXTURE_GOOD):
        problems.append("login_glance_faults flags a correct record line")
    if not login_glance_faults(LOGIN_FIXTURE_A_PICK):
        problems.append("login_glance_faults misses a side on the login page")
    if not login_glance_faults(LOGIN_FIXTURE_A_PROBABILITY):
        problems.append("login_glance_faults misses a probability")
    if not login_glance_faults(LOGIN_FIXTURE_A_RATE):
        problems.append("login_glance_faults misses a percentage in a line")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_login_scanner_can_see()


# A SCHEDULE CHANGE IS NOT DONE UNTIL THE OS SAYS SO (GRIDIRON_13 P3)
# ---------------------------------------------------------------------------
#
# Changing a task's time from the app is two acts: ask the OS to change it,
# and then ASK THE OS WHAT IT NOW HAS. Reporting success on an exit code is
# how an appliance ends up with a settings page saying 11:05 and a scheduler
# still firing at 11:00 -- worse than not offering the setting, because the
# operator now believes something false and has a screen agreeing with them.
#
# This project has already lived the general version: two days stalled with
# every screen green, because every screen reported what it had been told
# rather than what was true.

def schedule_claim_faults(payload: dict) -> list[str]:
    """A schedule change reported without reading the scheduler back."""
    faults = []
    if not isinstance(payload, dict):
        return faults
    if "changed" not in payload or "task" not in payload:
        return faults
    read_back = payload.get("read_back")
    if not isinstance(read_back, dict):
        faults.append(
            f"the change to {payload.get('task')!r} is reported without "
            f"reading the scheduler back. An exit code says the command was "
            f"accepted, not that the task moved; the only evidence that "
            f"counts is what the OS holds afterwards.")
        return faults
    if payload.get("changed") and read_back.get("found"):
        asked, held = payload.get("asked"), read_back.get("at")
        if asked and held and asked != held:
            faults.append(
                f"the change to {payload.get('task')!r} is reported as done, "
                f"but the scheduler holds {held} and {asked} was asked for. A "
                f"page that says 11:05 over a scheduler firing at 11:00 is "
                f"worse than no setting at all.")
    return faults


SCHEDULE_FIXTURE_NO_READBACK = {
    "task": "predict:mlb", "asked": "11:05", "changed": True,
    "line": "Gridiron-Predict-MLB now runs at 11:05.",
}
SCHEDULE_FIXTURE_DISAGREES = {
    "task": "predict:mlb", "asked": "11:05", "changed": True,
    "read_back": {"found": True, "at": "11:00"},
}
SCHEDULE_FIXTURE_GOOD = {
    "task": "predict:mlb", "asked": "11:05", "changed": True,
    "read_back": {"found": True, "at": "11:05"},
}


def check_a_schedule_change_was_read_back(payload: dict) -> None:
    faults = schedule_claim_faults(payload)
    if faults:
        raise LawViolation(
            "A SCHEDULE CHANGE WAS CLAIMED, NOT CONFIRMED:"
            + _NL2 + _NL2.join(faults))


def _check_the_schedule_scanner_can_see() -> None:
    problems = []
    if not schedule_claim_faults(SCHEDULE_FIXTURE_NO_READBACK):
        problems.append("schedule_claim_faults misses a change with no read-back")
    if not schedule_claim_faults(SCHEDULE_FIXTURE_DISAGREES):
        problems.append("schedule_claim_faults misses a read-back that "
                        "disagrees with what was asked")
    if schedule_claim_faults(SCHEDULE_FIXTURE_GOOD):
        problems.append("schedule_claim_faults flags a confirmed change")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_schedule_scanner_can_see()


# THE SEASON AS A SHAPE (GRIDIRON_13 P2)
# ---------------------------------------------------------------------------
#
# A results calendar is the densest claim this app makes: one square carries a
# whole day's record, and a reader takes it in without reading a number. Three
# ways it could lie, and this scan refuses all three.
#
#   MERGED SPORTS. A square holding a baseball day and a football day is two
#   records averaged into one colour. LAW 6, in the place it would be least
#   visible -- nobody checks the sport of a green square.
#
#   A VOID COUNTED AS A LOSS. A void is a question that was never answered. A
#   day that voided four and won three is not a 3-4 day, and tinting it red
#   says the model was wrong about games it never got to be wrong about.
#
#   A TINT FROM ANYTHING BUT THE BALANCE. Confidence that day, the size of the
#   disagreements, a streak -- any of them would make a square green for a
#   reason other than "more went right than wrong", which is the one thing a
#   reader will believe it means.

def calendar_faults(payload: dict) -> list[str]:
    """A calendar square that could mislead."""
    faults = []
    sport = payload.get("sport")
    for i, day in enumerate(payload.get("days") or []):
        where = f"day {day.get('day', i)!r}"
        if day.get("sport") and sport and day["sport"] != sport:
            faults.append(
                f"{where} carries sport {day['sport']!r} inside a {sport!r} "
                f"calendar. LAW 6: a square holding two sports is two records "
                f"averaged into one colour, in the place it is least visible.")
        won, lost = day.get("won") or 0, day.get("lost") or 0
        void = day.get("void") or 0
        if day.get("settled") is not None and day["settled"] != won + lost:
            faults.append(
                f"{where} reports {day['settled']} settled against {won} right "
                f"and {lost} wrong. A void is not a loss and must not be "
                f"counted into either.")
        expected = "up" if won > lost else "down" if lost > won else "even"
        if day.get("balance") and day["balance"] != expected:
            faults.append(
                f"{where} is tinted {day['balance']!r} on {won} right and "
                f"{lost} wrong, which is {expected!r}. A square is tinted by "
                f"the day's balance and by nothing else -- not confidence, not "
                f"the size of the disagreements, not a streak.")
        if void and day.get("label") and str(won + void) in str(day["label"]).split("-")[:1]:
            faults.append(
                f"{where} folds {void} void into its win count.")
        if "n" not in day:
            faults.append(f"{where} has no N (LAW 4).")
    return faults


CALENDAR_FIXTURE_GOOD = {
    "sport": "mlb",
    "days": [{"day": "2026-09-01", "won": 5, "lost": 2, "void": 1,
              "settled": 7, "n": 7, "sport": "mlb", "balance": "up",
              "label": "5-2"}],
}
CALENDAR_FIXTURE_MERGED = {
    "sport": "mlb",
    "days": [{"day": "2026-09-01", "won": 5, "lost": 2, "void": 0,
              "settled": 7, "n": 7, "sport": "nfl", "balance": "up",
              "label": "5-2"}],
}
CALENDAR_FIXTURE_VOID_AS_LOSS = {
    "sport": "mlb",
    "days": [{"day": "2026-09-01", "won": 3, "lost": 4, "void": 4,
              "settled": 11, "n": 11, "sport": "mlb", "balance": "down",
              "label": "3-4"}],
}
CALENDAR_FIXTURE_WRONG_TINT = {
    "sport": "mlb",
    "days": [{"day": "2026-09-01", "won": 2, "lost": 5, "void": 0,
              "settled": 7, "n": 7, "sport": "mlb", "balance": "up",
              "label": "2-5"}],
}


def check_the_calendar_says_what_it_shows(payload: dict) -> None:
    faults = calendar_faults(payload)
    if faults:
        raise LawViolation(
            "A CALENDAR SQUARE IS MISLEADING:" + _NL2 + _NL2.join(faults))


def _check_the_calendar_scanner_can_see() -> None:
    problems = []
    if calendar_faults(CALENDAR_FIXTURE_GOOD):
        problems.append("calendar_faults flags a correct day")
    if not calendar_faults(CALENDAR_FIXTURE_MERGED):
        problems.append("calendar_faults misses a square from another sport")
    if not calendar_faults(CALENDAR_FIXTURE_VOID_AS_LOSS):
        problems.append("calendar_faults misses voids counted into settled")
    if not calendar_faults(CALENDAR_FIXTURE_WRONG_TINT):
        problems.append("calendar_faults misses a square tinted against its "
                        "own balance")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_calendar_scanner_can_see()


# HOW CLOSE A GATE IS, IN COUNTS (GRIDIRON_13 P1)
# ---------------------------------------------------------------------------
#
# A progress line says how far a gate has to go. Three ways it could lie, and
# this scan refuses all three:
#
#   A PERCENTAGE INSTEAD OF A COUNT. "70% of the way to a verdict" on a page
#   whose whole subject is probabilities is a number that will be read as one,
#   and it hides the sample size LAW 4 requires be beside every figure.
#
#   NO N. Same law, same reason: 14 of 20 is a claim about a sample.
#
#   GREEN. A filling bar is not a win. Green means a pick won (GRIDIRON_16
#   R2), and a bar that goes green as it fills tells a reader the model is
#   doing well when all it has done is answer more questions. The colour law
#   scan catches this in the stylesheet; this catches it in a payload.

_PERCENT = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*%")


def progress_faults(payload: dict, path: str = "$") -> list[str]:
    """A progress line that states a share instead of a count."""
    faults = []
    if isinstance(payload, dict):
        looks_like_progress = {"done", "needed"} <= payload.keys()
        if looks_like_progress:
            if "n" not in payload:
                faults.append(
                    f"{path} reports progress without an 'n'. A gate line is a "
                    f"claim about a sample, and LAW 4 puts the sample size "
                    f"beside every figure.")
            for key in ("line", "note"):
                text = str(payload.get(key) or "")
                if _PERCENT.search(text):
                    faults.append(
                        f"{path}.{key} states a percentage ({text!r}). A "
                        f"progress line carries COUNTS: a share of the way to "
                        f"a verdict reads as a probability on a page about "
                        f"probabilities, and it hides the N.")
            for key in ("colour", "color", "tone"):
                if str(payload.get(key) or "").lower() in ("win", "green", "good"):
                    faults.append(
                        f"{path}.{key} paints the progress bar the colour that "
                        f"means a pick won. A filling bar is not a win -- it "
                        f"means more questions were answered (R2).")
        for key, value in payload.items():
            faults += progress_faults(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            faults += progress_faults(value, f"{path}[{i}]")
    return faults


PROGRESS_FIXTURE_PERCENT = {"done": 14, "needed": 20, "n": 14,
                            "line": "70% of the way to a verdict"}
PROGRESS_FIXTURE_NO_N = {"done": 14, "needed": 20, "line": "14 of 20 settled"}
PROGRESS_FIXTURE_GREEN = {"done": 14, "needed": 20, "n": 14,
                          "line": "14 of 20 settled", "colour": "win"}
PROGRESS_FIXTURE_GOOD = {"done": 14, "needed": 20, "n": 14,
                         "line": "14 of 20 settled", "note": "6 more settled"}


def check_progress_is_counted(payload: dict) -> None:
    faults = progress_faults(payload)
    if faults:
        raise LawViolation(
            "A PROGRESS LINE IS NOT COUNTING:" + _NL2 + _NL2.join(faults))


def _check_the_progress_scanner_can_see() -> None:
    problems = []
    if not progress_faults(PROGRESS_FIXTURE_PERCENT):
        problems.append("progress_faults misses a percentage in a gate line")
    if not progress_faults(PROGRESS_FIXTURE_NO_N):
        problems.append("progress_faults misses a gate line with no N")
    if not progress_faults(PROGRESS_FIXTURE_GREEN):
        problems.append("progress_faults misses a green progress bar")
    if progress_faults(PROGRESS_FIXTURE_GOOD):
        problems.append("progress_faults flags a correct gate line")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_progress_scanner_can_see()


# PICKS SHOWS TONIGHT (GRIDIRON_16 R4)
# ---------------------------------------------------------------------------
#
# Settled rows live in Results and only there. Picks answers "what does the
# model say about tonight"; a list of what already happened underneath it
# answers a different question, and it grew by a slate a day all season.

#: What a resolved-row section looks like in the renderer.
_RESOLVED_ON_PICKS = ("row-done", "rows-done", "resolvedRow")


def picks_resolved_faults(js: str) -> list[str]:
    """A settled pick rendered on the Picks page."""
    faults = []
    for token in _RESOLVED_ON_PICKS:
        # Prose may name the withdrawn section; code may not build it.
        for line in js.splitlines():
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if token in line.split("//")[0]:
                faults.append(
                    f"the renderer builds {token!r}, a resolved row on the "
                    f"Picks page. Settled picks live in Results and only there "
                    f"(R4): Picks answers what the model says about tonight, "
                    f"and a list of what already happened underneath it "
                    f"answers a different question.")
                break
    return faults


PICKS_RESOLVED_FIXTURE_POSITIVE = """
    if (done.length) {
      const list = el('div', 'rows rows-done');
      done.forEach(c => list.appendChild(resolvedRow(c)));
    }
"""


def check_picks_shows_tonight(path: Path | None = None) -> None:
    path = path or (config.PACKAGE_ROOT / "web" / "app.js")
    faults = picks_resolved_faults(Path(path).read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "A SETTLED PICK IS ON THE PICKS PAGE:" + _NL2 + _NL2.join(faults))


# A WITHDRAWN FEATURE LEAVES NOTHING BEHIND (GRIDIRON_16 R1)
# ---------------------------------------------------------------------------
#
# The operator's calls were withdrawn on 2026-09-02 by SURGERY rather than
# revert, because the notifier shipped in the same brief and had to survive.
# Surgery leaves stumps. This scan is what makes "removed entirely" checkable
# a month from now, when the only memory of the feature is a comment.
#
# It scans CODE, not prose: DECISIONS_MADE.md, the brief, and the comments
# that record what went and why are the account of the removal and must
# outlive it.

#: Identifiers the withdrawn feature owned. None may reappear in code.
WITHDRAWN_CALLS_SYMBOLS = (
    "operator_calls", "operator_tier_table", "call_comparison",
    "paintCall", "callDraft", "submitCall", "call_state_line",
    "call_side_label", "calls_since_line", "call_comparison_line",
    "CallRefused", "TIER_CLAIM", "call_stake_faults", "/api/calls",
)


def withdrawn_calls_faults(text: str, *, comment: str = "#") -> list[str]:
    """Any symbol from the withdrawn operator-calls feature, in code.

    THE DROP LIST IS NOT A STUMP. `db.WITHDRAWN` names `operator_calls`
    because naming it is how the table gets dropped from a database that
    still has one -- it is the instrument of the removal, not a survival of
    it. Those lines are skipped by structure rather than by exempting the
    whole of `db.py`, so anything else that file grew would still be caught.
    """
    faults = []
    in_drop_list = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("WITHDRAWN") and stripped.endswith("("):
            in_drop_list = True
            continue
        if in_drop_list:
            if stripped.startswith(")"):
                in_drop_list = False
            continue
        if stripped.startswith(comment) or stripped.startswith("*"):
            continue
        if stripped[:3] in ('"""', "'" * 3):
            continue
        code = line.split(comment)[0]
        for symbol in WITHDRAWN_CALLS_SYMBOLS:
            if symbol in code:
                faults.append(
                    f"{symbol!r} is back in the code. Operator calls were "
                    f"withdrawn on 2026-09-02 by ruling (GRIDIRON_16 R1) and "
                    f"the removal was surgery, not a revert -- a surviving "
                    f"symbol is a stump, and the next reader cannot tell one "
                    f"from a live feature.")
    return faults


WITHDRAWN_CALLS_FIXTURE_POSITIVE = """
const block = el('div', 'call-block');
paintCall(card, block);
"""


#: THE SCANNER HOLDS THE FORBIDDEN WORDS, so the scanner trips over itself.
#: Exactly the situation `BETTING_SCAN_EXEMPT` was written for a fortnight
#: ago, and the same answer: ONE file, named, with a test pinning the list to
#: that length so the exemption cannot quietly grow into a way to hide a stump.
WITHDRAWN_SCAN_EXEMPT = ("audit.py",)


def check_the_calls_feature_stayed_withdrawn() -> None:
    faults = []
    for path in sorted(config.PACKAGE_ROOT.glob("*.py")):
        if path.name in WITHDRAWN_SCAN_EXEMPT:
            continue
        faults += withdrawn_calls_faults(
            path.read_text(encoding="utf-8"), comment="#")
    web = config.PACKAGE_ROOT / "web"
    for name in ("app.js", "index.html"):
        target = web / name
        if target.exists():
            faults += withdrawn_calls_faults(
                target.read_text(encoding="utf-8"), comment="//")
    if faults:
        raise LawViolation(
            "THE WITHDRAWN FEATURE LEFT SOMETHING BEHIND:"
            + _NL2 + _NL2.join(sorted(set(faults))))


def _check_the_withdrawal_scanners_can_see() -> None:
    problems = []
    if not picks_resolved_faults(PICKS_RESOLVED_FIXTURE_POSITIVE):
        problems.append("picks_resolved_faults misses a resolved row on Picks")
    if picks_resolved_faults("const list = el('div', 'rows');"):
        problems.append("picks_resolved_faults flags an ordinary row list")
    if not withdrawn_calls_faults(WITHDRAWN_CALLS_FIXTURE_POSITIVE, comment="//"):
        problems.append("withdrawn_calls_faults misses a reinstated call block")
    if withdrawn_calls_faults("// operator_calls was withdrawn on 2026-09-02",
                              comment="//"):
        problems.append("withdrawn_calls_faults flags the comment recording "
                        "the removal, which must outlive it")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_withdrawal_scanners_can_see()


RESERVED_COLOURS = ("--win", "--loss")

_CSS_LIVE_MARK = re.compile(
    r"\.tile-live\s*\{(?P<body>[^}]*)\}", re.S)


def live_mark_faults(css: str) -> list[str]:
    """A live mark drawn in a colour that already means something else."""
    faults = []
    for match in _CSS_LIVE_MARK.finditer(css):
        body = match.group("body")
        for token in RESERVED_COLOURS:
            if token in body:
                faults.append(
                    f".tile-live uses var({token}), which is reserved: green "
                    f"means a pick WON and red means a pick LOST (R2). A game "
                    f"in progress is neither -- it has not finished -- and "
                    f"colouring it so tells a reader the model is winning "
                    f"before anything has been settled.")
    return faults


#: A live mark in the win colour, and the chrome one that is correct.
LIVE_MARK_FIXTURE_POSITIVE = ".tile-live { background: var(--win); }"
LIVE_MARK_FIXTURE_NEGATIVE = ".tile-live { background: var(--chrome); }"


def check_the_live_mark_is_not_an_opinion(path: Path | None = None) -> None:
    path = path or (config.PACKAGE_ROOT / "web" / "style.css")
    faults = live_mark_faults(Path(path).read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "THE LIVE MARK HAS AN OPINION:" + _NL2 + _NL2.join(faults))


#: What the live updater must NOT do. Re-rendering the slate would re-sort it,
#: and sorting a slate while it is being played shuffles the screen under
#: somebody reading it -- by confidence, the finished games climb over the ones
#: still on.
RESORT_CALLS = ("renderGames", ".sort(")
#: AND NOTHING MAY MOVE ON THE WAY (motion, 2026-09-25): the class that starts
#: the bar's one first-load fill, and an arrival, are out of a live patch's
#: reach. Declared here, above the scanner that reads them.
BAR_FILL_START = "filling"
LIVE_PATCH_FORBIDDEN = ("pbar", BAR_FILL_START, "arrive(", "arriving")


def live_update_faults(js: str) -> list[str]:
    """A live update that rebuilds or reorders the grid instead of patching."""
    js = _without_comments(js, "js")
    match = re.search(r"function\s+applyLive\s*\([^)]*\)\s*\{(?P<body>.*?)\n  \}",
                      js, re.S)
    if match is None:
        return ["applyLive() is not in the renderer, so nothing patches a tile "
                "in place when a score arrives"]
    body = match.group("body")
    faults = []
    for call in RESORT_CALLS:
        if call in body:
            faults.append(
                f"applyLive() calls {call!r}: a score arriving would rebuild "
                f"or reorder the grid. A tile changing state re-renders IN "
                f"PLACE -- the reader is part way down a slate and the thing "
                f"they were looking at must not move.")
    for word in LIVE_PATCH_FORBIDDEN:
        if word in body:
            faults.append(
                f"applyLive() reaches {word!r}: a score arriving may set the "
                f"new value and nothing may move on its way there -- not the "
                f"bar, not an arrival. The bar fills once, on load (motion, "
                f"2026-09-25).")
    return faults


LIVE_UPDATE_FIXTURE_POSITIVE = """
  function applyLive(live) {
    (live.picks || []).forEach(p => Object.assign(slateCards.get(p.id), p));
    renderGames();
  }
"""
LIVE_UPDATE_FIXTURE_NEGATIVE = """
  function applyLive(live) {
    (live.picks || []).forEach(pick => {
      const tile = document.querySelector('.tile[data-id]');
      if (tile) applyTileState(tile, pick);
    });
  }
"""


def check_a_live_update_does_not_reorder(path: Path | None = None) -> None:
    path = path or (config.PACKAGE_ROOT / "web" / "app.js")
    faults = live_update_faults(Path(path).read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "A SCORE ARRIVING WOULD MOVE THE SLATE:" + _NL2 + _NL2.join(faults))


def _check_the_live_scanners_can_see() -> None:
    problems = []
    if not live_mark_faults(LIVE_MARK_FIXTURE_POSITIVE):
        problems.append("live_mark_faults misses a green live mark")
    if live_mark_faults(LIVE_MARK_FIXTURE_NEGATIVE):
        problems.append("live_mark_faults flags the chrome mark, which is right")
    if not live_update_faults(LIVE_UPDATE_FIXTURE_POSITIVE):
        problems.append("live_update_faults misses an applyLive that re-renders")
    if live_update_faults(LIVE_UPDATE_FIXTURE_NEGATIVE):
        problems.append("live_update_faults flags an applyLive that patches in place")
    if problems:
        raise LawViolation(
            "A SCANNER IS BLIND: a live guard does not do what it says:"
            + _NL2 + _NL2.join(problems))


_check_the_live_scanners_can_see()


def sides_without_words(sides) -> list[str]:
    """Stored sides the humaniser has no verb for. Empty is the only pass."""
    from . import language
    return [
        f"the stored side {side!r} has no entry in SIDE_WORDS, so any sentence "
        f"about it is guessing -- and the guess used to be the opposite side's "
        f"verb"
        for side in sorted(set(sides))
        if side and side not in language.SIDE_WORDS
    ]


def pick_disagrees_with_its_label(cards) -> list[str]:
    """Cards whose pick line and confidence label name different sides.

    A TILE IS TWO CLAIMS ABOUT ONE PICK -- the line across the middle and the
    word under the percentage -- and they are derived separately. "Alabama
    -24.5 ... 76% MISSES" is both of them being individually defensible and
    jointly telling a reader to work out the inversion themselves.
    """
    from . import language
    faults = []
    for card in cards:
        if card.get("market_type") not in ("spread", "moneyline"):
            continue
        # AGAINST THE ONE DOOR, not against a second opinion. Asking whether
        # the label is the "negative" word cannot work now that the flip makes
        # both words positive -- and a guard whose passing depends on the
        # defect still existing is not a guard. So this asks the humaniser
        # what this card should say and compares.
        expected_line = language.tile_line(card)
        expected_label = language.tile_label(card)
        if card.get("tile_line") != expected_line:
            faults.append(
                f"the tile shows {card.get('tile_line')!r} where the pick is "
                f"{expected_line!r} -- the line on the tile is not the side "
                f"the record stored")
        if card.get("tile_label") != expected_label:
            faults.append(
                f"{card.get('tile_line')!r} carries the label "
                f"{card.get('tile_label')!r} where the pick is "
                f"{expected_label!r}: the line names one side and the label "
                f"bets against it")
    return faults


def check_every_side_has_words(conn=None) -> None:
    """Every side in the record, and every side any sport can produce."""
    from . import config
    sides = set()
    if conn is not None:
        sides |= {r[0] for r in conn.execute(
            "SELECT DISTINCT model_side FROM predictions")}
    for market_type, yes in (("spread", "cover"), ("moneyline", "win"),
                             ("total", "over"), ("prop", "over")):
        sides.add(yes)
    faults = sides_without_words(sides)
    if faults:
        raise LawViolation(
            "A SIDE WITH NO WORDS. The humaniser was handed a stored side it "
            "has no verb for, and its old behaviour was to print another "
            "side's verb -- which put the opposite of the forecast on nine "
            "cards for three days:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# A CALL IS A CONFIDENCE, NOT A STAKE -- GUARD WITHDRAWN WITH ITS FEATURE
# ---------------------------------------------------------------------------
#
# `call_stake_faults` scanned `operator_calls` for a column that expressed an
# amount, because the operator's own calls were the closest this project came
# to what LAW 5 forbids: a person recording an opinion with a strength
# attached, one column away from a stake.
#
# The feature was withdrawn on 2026-09-02 (GRIDIRON_16 R1) and the guard went
# with it, because a guard over a table that no longer exists passes for the
# wrong reason -- it would report a clean scan forever while proving nothing.
# LAW 5's general scan is untouched: `check_not_a_betting_tool` still walks
# every identifier in the package, and `STAKE_COLUMNS` lives on below because
# that scan uses the same vocabulary.

#: Names that would turn a measurement into a stake. Read by the LAW 5
#: identifier scan, which is why this outlived the call-specific guard.
STAKE_COLUMNS = (
    "units", "unit", "amount", "stake", "wager", "bankroll", "risk",
    "size", "sizing", "kelly", "payout", "odds", "price",
)


# ---------------------------------------------------------------------------
# THREE FORECASTERS, NEVER ONE (GRIDIRON_12, ruling R2)
# ---------------------------------------------------------------------------
#
# The operator sees the model's probability and the market's line before
# calling, so their calls are INFORMED. Pooling them with the blind record
# would destroy the property that makes the blind record worth keeping, and
# pooling them with the model's would be the merge LAW 4 already forbids --
# applied across forecasters rather than across sports, exactly as
# `statistical` and `llm` are already kept apart.
#
# The tempting version is an "all" or "combined" option in the selector. It
# would look like a convenience and would be the one number on the page that
# describes nothing: the model answers every question on a slate, the operator
# answers the ones they chose.

#: Selector values that could only mean a merge.
MERGED_FORECASTERS = ("all", "combined", "everyone", "total", "overall", "both")


def merged_forecaster_faults(payload: dict) -> list[str]:
    """A forecaster option that could only be a pool of two or more.

    This also carried an "is the informed forecaster labelled as informed"
    rule until 2026-09-02. It went with the operator's calls (GRIDIRON_16 R1)
    and for the reason the call-stake guard went: no forecaster is informed
    any more, so the branch could only ever pass, and a guard that cannot
    fail is a guard on faith.
    """
    faults = []
    for entry in payload.get("forecasters") or []:
        name = str(entry.get("forecaster", "")).lower()
        if name in MERGED_FORECASTERS:
            faults.append(
                f"the forecaster selector offers {name!r}, which can only be a "
                f"pool of two or more. The model answers every question on a "
                f"slate and the operator answers the ones they chose; one "
                f"number over both describes neither."
            )
    return faults


MERGED_FORECASTER_FIXTURE_POSITIVE = {
    "forecasters": [
        {"forecaster": "statistical", "label": "statistical"},
        {"forecaster": "all", "label": "everything together"},
    ]
}
MERGED_FORECASTER_FIXTURE_NEGATIVE = {
    "forecasters": [
        {"forecaster": "statistical", "label": "statistical", "informed": False},
        {"forecaster": "llm", "label": "LLM", "informed": False},
    ]
}


def check_forecasters_are_never_merged(payload: dict) -> None:
    faults = merged_forecaster_faults(payload)
    if faults:
        raise LawViolation(
            "FORECASTERS WERE MERGED:" + _NL2 + _NL2.join(faults))


def _check_the_forecaster_scanner_can_see() -> None:
    problems = []
    if not merged_forecaster_faults(MERGED_FORECASTER_FIXTURE_POSITIVE):
        problems.append("merged_forecaster_faults misses an 'all' option")
    if merged_forecaster_faults(MERGED_FORECASTER_FIXTURE_NEGATIVE):
        problems.append("merged_forecaster_faults flags a correct selector")
    if problems:
        raise LawViolation(
            "A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_forecaster_scanner_can_see()


# ONE FORECASTER IN ONE RANKING (GRIDIRON_14)
# ---------------------------------------------------------------------------
#
# The Record tab has kept the forecasters apart since GRIDIRON_12. THE PICKS
# LIST DID NOT, and the result was on screen: the slate carried the
# statistical row and the LLM row for the same game, unlabelled, adjacent, and
# each sorted on its own disagreement -- so Toronto at Cleveland appeared
# twice, once as "Cleveland to win 53%" and once as "Toronto to win 53%". Two
# contradictory picks, both presented as the pick, with nothing on either
# saying which forecaster said it.
#
# That is the merge LAW 4 forbids in a curve, committed in a LIST instead. A
# ranking is a claim that these are the picks in order; two forecasters in one
# ranking are ranked against each other, and the top of the list is then
# decided by which model happened to disagree with the market harder.

def one_forecaster_faults(payload: dict) -> list[str]:
    """More than one forecaster inside a single picks list."""
    faults = []
    declared = str(payload.get("forecaster") or "")
    cards = payload.get("cards") or []
    seen = {str(c.get("predictor")) for c in cards if c.get("predictor")}
    if len(seen) > 1:
        # NAME A GAME THAT CARRIES BOTH. A fault a reader can look up is one
        # they can believe; "the list is mixed" is a sentence they have to
        # take on trust.
        grouped: dict = {}
        for c in cards:
            grouped.setdefault(
                (c.get("game_id"), c.get("market_type")), set()).add(
                    str(c.get("predictor")))
        example = next((k for k, v in grouped.items() if len(v) > 1), None)
        where = f", and {example[0]} carries both" if example else ""
        faults.append(
            f"the picks list mixes {len(seen)} forecasters "
            f"({', '.join(sorted(seen))}){where}. A ranking says these are the "
            f"picks in order; two forecasters in one ranking rank against each "
            f"other and can state opposite sides of the same game."
        )
    if declared and seen and seen != {declared}:
        faults.append(
            f"the picks list says it is showing {declared!r} but its cards "
            f"carry {', '.join(sorted(seen))}. A label that disagrees with the "
            f"rows beneath it is worse than no label at all."
        )
    if declared.lower() in MERGED_FORECASTERS:
        faults.append(
            f"the picks list is labelled {declared!r}, which can only be a "
            f"pool of two or more forecasters."
        )
    return faults


def check_one_forecaster_per_list(payload: dict) -> None:
    faults = one_forecaster_faults(payload)
    if faults:
        raise LawViolation(
            "TWO FORECASTERS IN ONE RANKING:" + _NL2 + _NL2.join(faults))


def _check_the_picks_scanner_can_see() -> None:
    """The scanner is proven against the defect it was written for."""
    problems = []
    mixed = {
        "forecaster": "statistical",
        "cards": [
            {"game_id": "mlb_1", "market_type": "moneyline",
             "predictor": "statistical", "model_side": "win"},
            {"game_id": "mlb_1", "market_type": "moneyline",
             "predictor": "llm", "model_side": "lose"},
        ],
    }
    if not one_forecaster_faults(mixed):
        problems.append("one_forecaster_faults misses two forecasters naming "
                        "opposite sides of one game")
    clean = {
        "forecaster": "statistical",
        "cards": [
            {"game_id": "mlb_1", "market_type": "moneyline",
             "predictor": "statistical"},
            {"game_id": "mlb_2", "market_type": "moneyline",
             "predictor": "statistical"},
        ],
    }
    if one_forecaster_faults(clean):
        problems.append("one_forecaster_faults flags a single-forecaster list")
    if not one_forecaster_faults({"forecaster": "all", "cards": []}):
        problems.append("one_forecaster_faults misses an 'all' label")
    mislabelled = {
        "forecaster": "llm",
        "cards": [{"game_id": "mlb_1", "market_type": "moneyline",
                   "predictor": "statistical"}],
    }
    if not one_forecaster_faults(mislabelled):
        problems.append("one_forecaster_faults misses a label that disagrees "
                        "with its own rows")
    if problems:
        raise LawViolation(
            "A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_picks_scanner_can_see()


# A FLAGGED METHOD SAYS SO, AND NEVER LEADS (operator ruling 2, 2026-09-04)
# ---------------------------------------------------------------------------
#
# A market can be fitted, calibrated, honest about its sample, and still be
# asking a question with almost nothing in it. Four sports declare a `total`
# and all four choose the rung as the ladder point nearest their OWN
# expectation, which makes P(over) one half by construction -- measured at
# +0.0010 (NBA) and +0.0016 (NFL) walk-forward.
#
# THE FLAG IS DECLARED IN ONE PLACE AND WORDED IN ANOTHER, and this is what
# stops the two drifting apart. STEP 4 found a declaration disagreeing with a
# hardcoded list FOUR TIMES in one session, every one of them silent, so a
# fifth copy of "which markets are totals" is not written here: the fault is
# read off the code that actually chooses the rung.
#
# THE NAMING IS LOAD-BEARING and is asserted rather than assumed.
# `questions.<sport>_<market>_asked` takes the model's own expectation and
# returns a rung. `questions.ufc_rounds_rung` takes the BOUT'S SCHEDULED
# LENGTH, which is not a self-chosen rung at all -- and it is named `_rung`
# for exactly that reason. A future asker named `_asked` for a market nobody
# flagged is the failure this scan exists to catch.

def flagged_method_faults() -> list[str]:
    """Where the method flag and the code that earns it disagree.

    Three ways they can, and all three are silent in production:

    1. A DECLARED MARKET ASKED AT ITS OWN RUNG AND NOT FLAGGED. The card
       renders as any other and a reader takes a coin flip at face value.
    2. A FLAG WITH NO WORDS. `language.method_note` raises on this at render
       time, which is the right behaviour and the wrong moment: it would fire
       on a reader's slate rather than in the gate.
    3. A FLAG ON A MARKET THE SPORT DOES NOT DECLARE. Harmless today and the
       residue of a market that was withdrawn, which is how a stale caveat
       comes to be waiting for the market's return.
    """
    from . import language
    from .model import questions

    faults: list[str] = []

    for sport, markets in config.SPORT_MARKETS.items():
        for market in markets:
            asker = getattr(questions, f"{sport}_{market}_asked", None)
            if asker is None or not callable(asker):
                continue
            if config.flagged_method(sport, market) is None:
                faults.append(
                    f"{sport}:{market} is asked at a rung "
                    f"`questions.{sport}_{market}_asked` chooses from the "
                    f"model's OWN expectation, and it is not in "
                    f"config.FLAGGED_METHODS. P(over) is one half by "
                    f"construction on a question asked that way -- measured "
                    f"at +0.0010 and +0.0016 in two sports -- and an unflagged "
                    f"card says none of that.")

    for (sport, market), key in sorted(config.FLAGGED_METHODS.items()):
        if key not in language.METHOD_NOTES:
            faults.append(
                f"{sport}:{market} is flagged {key!r} and language."
                f"METHOD_NOTES has no words for it. The card would raise on a "
                f"reader's slate instead of failing here.")
        if market not in config.SPORT_MARKETS.get(sport, ()):
            faults.append(
                f"{sport}:{market} is flagged and {sport} does not declare "
                f"that market. A caveat with no card to sit on.")

    return faults


def check_flagged_methods() -> None:
    """Raise unless every self-chosen rung is flagged and every flag has words."""
    faults = flagged_method_faults()
    if faults:
        raise LawViolation(
            "A FLAGGED METHOD SAYS SO:" + _NL2 + _NL2.join(faults))


# THE HERO'S THREE GUARDS WERE RETIRED WITH THE HERO (THREE_STATES,
# 2026-09-08). `hero_flag_faults` and `check_the_hero_refuses_flagged_methods`
# checked that a flagged market could not LEAD the page, that a claim under
# the confidence floor could not lead it, and that the grid dropped the card
# the hero led with by identity rather than by position.
#
# THERE IS NO LEAD. Every card on Upcoming is the same size and which group it
# sits in is decided by the bar, not by a sort. What survives:
#
#   * a flagged method still says so, on the card that carries it --
#     `check_flagged_methods` is a different scan and still runs;
#   * nothing unproven leads, because a card below its market's gate says "no
#     measured edge" on its own face, which binds every card rather than one;
#   * the grid drops nothing, which is the defect the third check existed for.
#
# Recorded here rather than deleted silently: a guard that vanishes is a law
# nobody can audit.


#: One row of the font provenance table: the file, its size and its hash. It
#: sat between the two hero functions and went out with them for a minute on
#: 2026-09-08, which is what a slice taken by function boundaries does to
#: anything declared between two functions.
_FONT_ROW = re.compile(
    r"^\|\s*`(?P<name>[^`]+)`\s*\|\s*(?P<size>[\d,]+)\s*\|\s*`(?P<sha>[0-9a-f]{64})`\s*\|",
    re.M)


def vendored_font_faults(root: Path | None = None) -> list[str]:
    """Where the vendored binaries and their recorded provenance disagree.

    Four ways, and the quiet one is the last:

    1. THE TABLE IS GONE, so nothing is recorded and nothing can be checked.
    2. A FILE NAMED IN THE TABLE IS MISSING.
    3. A FILE'S BYTES DO NOT MATCH what was recorded.
    4. A FILE IS PRESENT AND NOT IN THE TABLE -- a binary that arrived without
       provenance, which is the exact thing the no-committing instinct was
       protecting against and the only one of the four that looks like nothing.
    """
    base = (config.PACKAGE_ROOT / "web" / "fonts") if root is None else Path(root)
    source = base / "SOURCE.md"
    if not source.is_file():
        return [f"{source} is missing, so the vendored binaries beside it have "
                f"no recorded provenance and nothing can check them."]

    import hashlib

    recorded = {
        m.group("name"): (int(m.group("size").replace(",", "")), m.group("sha"))
        for m in _FONT_ROW.finditer(source.read_text(encoding="utf-8"))
    }
    if not recorded:
        return [f"{source} carries no hash table, so the files beside it are "
                f"unchecked binaries with a document about them."]

    faults: list[str] = []
    for name, (size, sha) in sorted(recorded.items()):
        path = base / name
        if not path.is_file():
            faults.append(f"{name} is recorded in SOURCE.md and is not there.")
            continue
        blob = path.read_bytes()
        got = hashlib.sha256(blob).hexdigest()
        if len(blob) != size:
            faults.append(f"{name} is {len(blob)} bytes; SOURCE.md records "
                          f"{size}.")
        if got != sha:
            faults.append(f"{name} hashes to {got[:16]}...; SOURCE.md records "
                          f"{sha[:16]}.... The file in this repository is not "
                          f"the file whose provenance is written down.")

    for path in sorted(base.iterdir()):
        if path.name in ("SOURCE.md",) or path.name in recorded:
            continue
        faults.append(f"{path.name} sits in web/fonts and is not in "
                      f"SOURCE.md's table -- a binary that arrived without "
                      f"provenance is the thing the table exists to prevent.")

    # THE LICENCE TRAVELS WITH THE FILES, which the OFL requires and which is
    # also what makes them checkable without leaving the repository.
    licence = base / "OFL.txt"
    if licence.is_file():
        text = licence.read_text(encoding="utf-8", errors="replace")
        if "SIL Open Font License" not in text:
            faults.append("web/fonts/OFL.txt does not contain the SIL Open "
                          "Font License text it is named for.")

    # AND THE OFFLINE SHELL NAMES THEM. A worker that caches the stylesheet
    # asking for a font and not the font renders the offline app in a fallback
    # face -- the one condition where the difference is most visible.
    sw = (config.PACKAGE_ROOT / "web" / "sw.js")
    if sw.is_file():
        shell = sw.read_text(encoding="utf-8")
        for name in sorted(n for n in recorded if n.endswith(".woff2")):
            if name not in shell:
                faults.append(
                    f"{name} is vendored and the service worker's SHELL does "
                    f"not name it, so the offline app draws in a fallback "
                    f"face while the online one does not.")
    return faults


def check_vendored_fonts(root: Path | None = None) -> None:
    """Raise unless every vendored binary matches its recorded provenance."""
    faults = vendored_font_faults(root)
    if faults:
        raise LawViolation(
            "A VENDORED BINARY IS CHECKABLE:" + _NL2 + _NL2.join(faults))


# A MARKET SHIPS ONLY ON ITS OWN VERDICT (Session E Part 2, 2026-09-04)
# ---------------------------------------------------------------------------
#
# `docs/DISTRIBUTIONAL.md` §7 fixed a decision rule BEFORE the numbers arrived:
# the distributional read-out ships only if it is better calibrated than the
# rung method, and its distribution's PIT is flat. The walk-forward then said
# no in all four arms. `config.DISTRIBUTIONAL_VERDICTS` records that.
#
# A RULE WRITTEN BEFORE THE NUMBERS IS WORTH NOTHING IF IT CAN BE EDITED
# AFTER THEM. This is the guard that makes the verdict binding rather than
# advisory, and it checks the decision against its OWN recorded evidence:
# a market may only be marked SHIP if the figures beside it say it earned it.
#
# AND THE MIGRATION IN BOTH DIRECTIONS. A shipped market must have lost its
# rung ladder -- a ladder left standing is a market that can quietly go back
# to asking at its own rung. A market that did NOT ship must still HAVE its
# ladder, because deleting one for a market that stays on rungs is how a
# migration half-lands.

#: Which declared ladder belongs to which market. Named rather than guessed:
#: a market whose ladder this map does not know is a market the migration
#: check cannot see, so an unknown market is a fault rather than a pass.
LADDERS_BY_MARKET: dict[tuple[str, str], tuple[str, str]] = {
    ("nfl", "total"): ("gridiron.model.questions", "NFL_TOTAL_LADDER"),
    ("nba", "total"): ("gridiron.model.questions", "NBA_TOTAL_LADDER"),
    ("nfl", "spread"): ("gridiron.model.questions", "SPREAD_LADDER"),
    ("cfb", "spread"): ("gridiron.model.questions", "CFB_SPREAD_LADDER"),
    ("nba", "spread"): ("gridiron.sports.nba", "SPREAD_LADDER"),
    # CFB's total is asked at its own expectation rounded to a half, with no
    # ladder at all -- which is why it measured worst of the four.
    ("cfb", "total"): (None, None),
}

#: Every figure a verdict must carry to be a verdict rather than an opinion.
VERDICT_FIELDS = ("verdict", "measured_utc", "n", "splits", "why")


def _ladder_exists(module_name: str | None, attr: str | None) -> bool:
    if module_name is None:
        return False
    import importlib
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return False
    return getattr(module, attr, None) is not None


def distributional_verdict_faults() -> list[str]:
    """Where a market's behaviour and its recorded verdict disagree.

    Five ways, and the first is the one the whole two-session structure exists
    to prevent:

    1. A MARKET SHIPPING WITHOUT A VERDICT. `DISTRIBUTIONAL_MARKETS` is derived
       from the verdicts, so this can only happen if somebody writes the set by
       hand -- which is exactly what the planting does.
    2. A SHIP VERDICT ITS OWN NUMBERS DO NOT SUPPORT. The decision rule was
       fixed before the data; a verdict that ignores the figures beside it is
       the rule being edited after the numbers.
    3. A SHIPPED MARKET THAT STILL HAS ITS RUNG LADDER.
    4. A MARKET LEFT ON RUNGS WHOSE LADDER IS GONE.
    5. A VERDICT MISSING ITS EVIDENCE -- no n, no date, no reason.
    """
    faults: list[str] = []

    derived = frozenset(
        key for key, entry in config.DISTRIBUTIONAL_VERDICTS.items()
        if entry.get("verdict") == "SHIP")
    # READ THROUGH THE ACCESSOR, not around it. `config.is_distributional` is
    # the door every caller will use when a market eventually ships, so the
    # guard has to be looking at the same door -- a check that reads the raw
    # set while production reads the function is a check on the wrong thing.
    for key in sorted(k for k in config.DISTRIBUTIONAL_MARKETS
                      if config.is_distributional(*k) and k not in derived):
        faults.append(
            f"{key[0]}:{key[1]} is running distributionally and no SHIP "
            f"verdict is recorded for it. The walk-forward is the only thing "
            f"that may put a market here.")

    for (sport, market) in sorted(config.DISTRIBUTIONAL_VERDICTS):
        entry = config.distributional_verdict(sport, market)
        where = f"{sport}:{market}"
        if market not in config.SPORT_MARKETS.get(sport, ()):
            faults.append(f"{where} has a verdict and {sport} does not declare "
                          f"that market.")
            continue
        for field in VERDICT_FIELDS:
            if entry.get(field) in (None, ""):
                faults.append(f"{where}'s verdict carries no {field!r}. A "
                              f"verdict without its evidence is an opinion.")

        verdict = entry.get("verdict")
        if verdict == "SHIP":
            gap_b, gap_a = entry.get("readout_gap_pts"), entry.get("rung_gap_pts")
            if gap_a is None or gap_b is None:
                faults.append(f"{where} is marked SHIP with no calibration "
                              f"figures to justify it.")
            elif gap_b > gap_a:
                faults.append(
                    f"{where} is marked SHIP and its own numbers say the "
                    f"read-out is WORSE calibrated ({gap_b} against {gap_a} "
                    f"points). The decision rule was fixed before the data; "
                    f"this is it being edited after.")
            if entry.get("pit_flat") is not True:
                faults.append(
                    f"{where} is marked SHIP and its distribution's PIT is not "
                    f"recorded flat. A read-out cannot be better calibrated "
                    f"than the distribution it is read from.")

        module_name, attr = LADDERS_BY_MARKET.get((sport, market), ("?", "?"))
        if module_name == "?":
            faults.append(f"{where} has a verdict and no entry in "
                          f"LADDERS_BY_MARKET, so nothing can check whether "
                          f"its migration happened.")
            continue
        has_ladder = _ladder_exists(module_name, attr)
        shipped = verdict == "SHIP"
        if shipped and has_ladder:
            faults.append(
                f"{where} shipped distributionally and {module_name}.{attr} is "
                f"still there. A ladder left standing is a market that can go "
                f"back to asking at its own rung without anybody deciding to.")
        if not shipped and module_name is not None and not has_ladder:
            faults.append(
                f"{where} did not ship and {module_name}.{attr} is gone. A "
                f"market left on rungs needs the rungs it is left on.")
    return faults


def check_distributional_verdicts() -> None:
    """Raise unless every market's behaviour matches its recorded verdict."""
    faults = distributional_verdict_faults()
    if faults:
        raise LawViolation(
            "A MARKET SHIPS ONLY ON ITS OWN VERDICT:" + _NL2 + _NL2.join(faults))


# A MARKET THE MODEL CANNOT INFORM IS SHOWN, NOT HIDDEN (rulings 2 and 3,
# 2026-09-04)
# ---------------------------------------------------------------------------
#
# TWO RULINGS, ONE ARGUMENT. CFB's totals expectation explains 0.93% of a
# college total and the market stays on the slate with the coin-flip line on
# it. Game markets get no confidence floor, so a weak claim is labelled rather
# than withheld. Both say the same thing: a reader is told what a claim is
# worth instead of having the weak ones taken away from them.
#
# THE FAILURE THEY GUARD AGAINST IS A KIND ONE. Nobody hides a market out of
# malice; they hide it because it looks bad on the page, or because a floor is
# an easy way to make a slate look sharper. Session E measured what that costs:
# for the one game-market method that could make confident claims, confidence
# ran BACKWARDS -- the questions above 70% were right 38% of the time and the
# ones below it 49%. A floor there would have kept exactly the wrong ones.

def hidden_market_faults() -> list[str]:
    """Where a market that measured badly has been quietly withdrawn.

    TWO WAYS TO DISAPPEAR, and this checks both:

    1. A MARKET WITH A RECORDED VERDICT that is no longer declared. Somebody
       measured it, did not like the answer, and took the question away.
    2. A FLAGGED MARKET that is no longer declared. `FLAGGED_METHODS` names the
       markets whose own method is known to measure almost nothing; those are
       precisely the ones it would be tempting to drop, and the ruling of
       2026-09-04 is that they stay ON the slate WITH the caveat.

    WHAT THIS DOES NOT CHECK is whether a market carries words -- that is
    `flagged_method_faults`, and one door decides it. This guard is about
    presence.

    AND A VERDICT IS NOT A JUDGEMENT ON THE MARKET. `DISTRIBUTIONAL_VERDICTS`
    records whether the READ-OUT beat the rung, not whether the market is any
    good: the NFL spread is refused there and is the market this project was
    built on, with a walk-forward calibration gap of 1.93 points. Reading a DO
    NOT SHIP as "this market is weak" was the first version of this function
    and it was wrong.
    """
    faults: list[str] = []
    for (sport, market) in sorted(config.DISTRIBUTIONAL_VERDICTS):
        entry = config.distributional_verdict(sport, market)
        if entry.get("verdict") == "SHIP":
            continue
        if market not in config.SPORT_MARKETS.get(sport, ()):
            faults.append(
                f"{sport}:{market} was measured and refused and is no longer a "
                f"declared {sport} market. A market the model cannot inform is "
                f"shown as such, not withdrawn: {entry.get('why')}")

    for (sport, market) in sorted(config.FLAGGED_METHODS):
        if market not in config.SPORT_MARKETS.get(sport, ()):
            faults.append(
                f"{sport}:{market} carries a method flag and is no longer a "
                f"declared {sport} market. The flag exists so the question can "
                f"stay on the slate saying what it is worth; withdrawing the "
                f"question instead is the thing the flag was chosen over.")
    return faults


def check_no_market_is_hidden() -> None:
    """Raise unless every refused market is still shown, with its caveat."""
    faults = hidden_market_faults()
    if faults:
        raise LawViolation(
            "A MARKET IS SHOWN, NOT HIDDEN:" + _NL2 + _NL2.join(faults))


#: Names that hold a confidence floor. A comparison against any of them has to
#: sit inside a prop branch or it is reaching a game market.
FLOOR_CONSTANTS = ("PROPS_MIN_CLAIM", "GAME_MARKET_MIN_CLAIM")


def _prop_branch(node: ast.AST) -> bool:
    """Does this `if` test say the question is a player prop?"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Attribute):
            if sub.left.attr != "market_type":
                continue
            for comparator in sub.comparators:
                if isinstance(comparator, ast.Constant) and comparator.value == "prop":
                    return True
    return False


def game_market_floor_faults(source: str | None = None) -> list[str]:
    """Is a confidence floor being applied to a game market?

    OPERATOR RULING, 2026-09-04: no floor on rung game markets. A floor keeps
    the claims the model is most sure of, so it is only as good as the
    relationship between confidence and accuracy -- and Session E measured that
    relationship running BACKWARDS on the one game-market method that could
    make a confident claim at all: of 768 NFL totals questions the 95 that
    cleared 70% were right 38% and 43% of the time, against 49% for the rest.

    READ FROM THE SYNTAX TREE, not from a pattern. The first version of this
    matched `market_type == "prop"` and the floor with a regex, and `predict.py`
    has TWO prop branches -- so lifting the floor out of the second one left
    the first still matching and the planting escaped. An ancestor walk asks
    the question that actually matters: is THIS comparison inside a branch that
    has established the question is a prop?

    THE CONSTANT IS NOT THE FLOOR, which is the other half. A guard that only
    read `GAME_MARKET_MIN_CLAIM` would pass while `PROPS_MIN_CLAIM` was applied
    to every question in the loop -- same effect, different name, and nothing
    in the configuration would look wrong.
    """
    faults: list[str] = []
    if config.GAME_MARKET_MIN_CLAIM is not None:
        faults.append(
            f"config.GAME_MARKET_MIN_CLAIM is "
            f"{config.GAME_MARKET_MIN_CLAIM}, and the ruling of "
            f"{config.GAME_MARKET_MIN_CLAIM_DECLARED[:10]} is that game "
            f"markets carry no floor. Overturn the ruling in "
            f"docs/DECISIONS_MADE.md before setting one.")

    if source is None:
        source = (config.PACKAGE_ROOT / "model" / "predict.py").read_text(
            encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return faults + [f"predict.py does not parse, so no floor can be "
                         f"checked for: {exc}"]

    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        hit = names & set(FLOOR_CONSTANTS)
        if not hit:
            continue
        guarded = False
        walker = parents.get(id(node))
        while walker is not None:
            if isinstance(walker, ast.If) and _prop_branch(walker):
                guarded = True
                break
            walker = parents.get(id(walker))
        if not guarded:
            faults.append(
                f"predict.py compares against {sorted(hit)[0]} at line "
                f"{node.lineno}, and no enclosing branch has established that "
                f"the question is a player prop. Every game on the slate gets "
                f"a question; refusing the ones the model is least sure of "
                f"hides them rather than choosing between them.")
    return faults


def check_no_floor_on_game_markets() -> None:
    """Raise if a confidence floor has reached a game market."""
    faults = game_market_floor_faults()
    if faults:
        raise LawViolation(
            "NO CONFIDENCE FLOOR ON GAME MARKETS:" + _NL2 + _NL2.join(faults))


# A CHIP SAYS WHETHER IT IS A RECORD OR A CLAIM (2026-09-04)
# ---------------------------------------------------------------------------
#
# MEASURED ON FOUR LIVE SLATES: 17 of 379 tier chips had a settled record
# behind them. The other 362 named a band -- 55 of them STRONG -- and the
# sentence saying nothing stood behind it reached a grid card only through the
# `title` attribute, which is a hover tooltip and therefore absent on every
# touch device and every glance.
#
# THE HERO WAS ALWAYS HONEST and the grid was not, which is the worst possible
# split: the one card a reader is shown in full says "not yet proven", and the
# thirty behind it do not.
#
# THE PRECEDENT IS THIS PROJECT'S OWN. The coin-flip note went on the collapsed
# card face rather than one tap in, "because a caveat behind a tap is a caveat
# most readers never reach". A tooltip is worse than a tap.

def tier_chip_faults(source: str | None = None) -> list[str]:
    """Can a chip name a band without saying whether anything stands behind it?

    Read from the shipped `app.js`, because a caveat asserted in a test is a
    caveat that protects the test. Two things have to hold:

    * the chip renders the SERVER'S label, not the bare band name;
    * the label is not the only place the state lives -- an unproven chip also
      carries a class, so the stylesheet can stop it shouting.

    AND THE LABEL IS NOT COMPOSED HERE OR THERE. `language.tier_chip_label` is
    the one door; the browser prints what it is given.
    """
    from . import language

    faults: list[str] = []
    if source is None:
        source = (config.PACKAGE_ROOT / "web" / "app.js").read_text(
            encoding="utf-8")

    match = re.search(r"function tierChip\((?:.|\n)*?\n  \}", source)
    if match is None:
        faults.append("`tierChip` is gone from app.js, so nothing renders the "
                      "band at all.")
        return faults
    # COMMENTS STRIPPED FIRST, and the reason is written in `_caller_sources`
    # a thousand lines above: "a guard satisfied by a comment about the guard
    # is worse than the finding it silenced." The first version of this scan
    # read the whole function body, and the paragraph inside `tierChip`
    # EXPLAINING why it renders `chip_label` satisfied the check for
    # `chip_label` -- so deleting the actual code left the guard green.
    body = re.sub("//" + "[^" + chr(10) + "]*", "", match.group(0))

    if "chip_label" not in body:
        faults.append(
            "`tierChip` no longer renders the server's `chip_label`, so a "
            "chip names a band without saying whether it has earned it. On "
            "the slates of 2026-09-04 that was true of 362 of 379 cards.")
    if "tier-unproven" not in body:
        faults.append(
            "`tierChip` no longer marks an unproven chip, so a STRONG that "
            "has never been right about anything looks exactly like one that "
            "has.")
    if "title" in body and "chip_label" not in body:
        faults.append(
            "the chip's only account of itself is the `title` attribute, "
            "which is a hover tooltip: absent on every touch device.")

    # And the words themselves still come from one place and say something.
    if language.tier_chip_label("STRONG", True) == \
            language.tier_chip_label("STRONG", False):
        faults.append(
            "`language.tier_chip_label` reads the same proven and unproven, "
            "so the chip cannot tell a reader which it is looking at.")
    return faults


def check_the_chip_says_what_it_is() -> None:
    """Raise unless a tier chip states whether it is a record or a claim."""
    faults = tier_chip_faults()
    if faults:
        raise LawViolation(
            "A CHIP SAYS WHETHER IT IS A RECORD OR A CLAIM:"
            + _NL2 + _NL2.join(faults))


# AN ABSENT FACTOR NEVER REACHES THE MODEL AS A NUMBER (2026-09-05)
# ---------------------------------------------------------------------------
#
# CHECKLIST ITEM 5, applied to the prompt rather than to the feature vector.
# `compute.assert_missing_is_explicit` already refuses a vector that defaults an
# absent factor to zero, and `check_no_silent_defaults` scans the factor code
# for a reintroduced fallback. Neither looks at what the LLM is TOLD.
#
# THE PROMPT GETS THIS RIGHT TODAY and this is what keeps it right. Absent
# factors are collected into a block headed "NOT MEASURABLE for this game. No
# value exists. Do not assume one, and do not treat these as zero" -- they are
# never emitted as `name = 0`. A single edit to the loop in `build_prompt`
# would change that, and nothing would look different: the model would simply
# start reasoning from zeroes it was handed as facts.
#
# WHY IT WAS WRITTEN ON 2026-09-05. A UFC reasoning row read "This is a
# three-round bout (ufc_scheduled_rounds = 0)" and the zero was suspected of
# being exactly this failure. It was not -- `ufc_scheduled_rounds` is a
# declared INDICATOR, 1.0 for five rounds and 0.0 for three, so the zero was
# correct and the prompt was honest. The scan exists because the question was
# worth being able to answer structurally rather than by reading the function.

def prompt_absence_faults() -> list[str]:
    """Does an absent factor reach the model as a value?

    BEHAVIOURAL, not a source scan: it builds a prompt from one present factor
    and one absent one and reads what came out. A pattern match on
    `build_prompt` would pass on a rewrite that did the wrong thing in a new
    shape, and this cannot.
    """
    from .model import llm

    faults: list[str] = []
    rows = [
        {"factor": "present_one", "value": 0.0, "present": True,
         "rationale": "a measured zero, which is a measurement"},
        {"factor": "absent_one", "value": None, "present": False,
         "contribution": None, "rationale": "not measurable for this game"},
    ]
    text = llm.build_prompt("does the home side win", rows, [])

    if re.search(r"absent_one\s*=", text):
        faults.append(
            "an absent factor is rendered to the model as `absent_one = ...`. "
            "CHECKLIST ITEM 5: a value that was never measured must not be "
            "handed over as one, and a zero is the most convincing wrong "
            "answer available -- the model would reason from it as a fact.")
    if "absent_one" not in text:
        faults.append(
            "an absent factor is not mentioned to the model at all. Silence "
            "and a zero are different failures with the same result: the "
            "model cannot know what could not be measured, so it cannot say "
            "so in its reasoning.")
    if "do not treat these as zero" not in text.lower():
        faults.append(
            "the prompt no longer tells the model that unmeasurable factors "
            "are not zero. The list alone is a heading; the instruction is "
            "the part that does the work.")
    # And a MEASURED zero must still be handed over as a value -- refusing it
    # would be the opposite error, and just as silent.
    if not re.search(r"present_one\s*=\s*0", text):
        faults.append(
            "a MEASURED zero no longer reaches the model. Zero is a "
            "measurement like any other; dropping it would hide a real "
            "observation to avoid a mistake nobody is making.")
    return faults


def check_the_prompt_keeps_absence_absent() -> None:
    """Raise if an unmeasurable factor reaches the model as a number."""
    faults = prompt_absence_faults()
    if faults:
        raise LawViolation(
            "AN ABSENT FACTOR IS NOT A ZERO:" + _NL2 + _NL2.join(faults))


# A PUSH THAT REACHED THE PHONE EXISTS IN THE RECORD (2026-09-05)
# ---------------------------------------------------------------------------
#
# `notify.send` used to post to both channels and THEN insert its row. On
# 2026-09-05 a message went out with a `kind` the table's CHECK refuses: both
# channels delivered, the phone buzzed, the INSERT raised, and the record has
# no trace of a push a person received.
#
# THE ORDERING WAS THE WHOLE DEFECT. Every validation the table performs was
# happening AFTER the irreversible part, which is the wrong way round for any
# action that leaves the machine.
#
# BEHAVIOURAL, NOT A SOURCE SCAN. This runs `send` against a temporary
# database with the channels stubbed, and asks the stub whether a row existed
# at the moment it was called. A pattern match on the function would pass on a
# rewrite that reintroduced the bug in a new shape.

def notification_ordering_faults() -> list[str]:
    """Is a push posted before the record knows about it?"""
    import tempfile
    from pathlib import Path

    # IMPORTED HERE, not at module scope: `audit` holds the list of forbidden
    # market identifiers, so a prediction-path module that imported it would
    # make the LAW 1 closure scan flag itself. `db` is safe to reach from
    # inside a function and not from the top of this file.
    from . import db, notify

    faults: list[str] = []
    seen: dict = {}

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        conn = db.open_db(Path(tmp) / "notify.db")
        real_push, real_toast = notify.send_push, notify.send_toast

        def watching_push(body, title="Gridiron"):
            seen["rows_at_post"] = conn.execute(
                "SELECT COUNT(*) FROM notifications").fetchone()[0]
            seen["states_at_post"] = [
                r[0] for r in conn.execute("SELECT state FROM notifications")]
            return {"channel": "push", "ok": True, "detail": "HTTP 200"}

        try:
            notify.send_push = watching_push
            notify.send_toast = lambda title, body: {
                "channel": "toast", "ok": True, "detail": "shown"}
            notify.send(conn, "failure", "an ordering probe", title="probe")
        finally:
            notify.send_push, notify.send_toast = real_push, real_toast

        # CLOSED WHATEVER HAPPENED. On Windows SQLite holds the file open, so
        # a connection left behind by an exception makes the temporary
        # directory undeletable -- and the planting that breaks `send` on
        # purpose is exactly the path that raises.
        try:
            final = conn.execute(
                "SELECT state, sent_utc, channels_json FROM notifications"
            ).fetchone()
        finally:
            conn.close()

    if not seen.get("rows_at_post"):
        faults.append(
            "a push was posted with no row in `notifications`. A message that "
            "reaches the phone and leaves no trace is a record that is silent "
            "about something a person received -- which happened on "
            "2026-09-05 and is the whole reason this exists.")
    elif "sending" not in (seen.get("states_at_post") or []):
        faults.append(
            f"a row existed at post time and its state was "
            f"{seen.get('states_at_post')}. It should be 'sending': 'queued' "
            f"means held for quiet hours and never sent, and conflating the "
            f"two hides a crash mid-post inside an ordinary state.")

    if final is None:
        faults.append("the row vanished after the post.")
    else:
        if final["state"] != "sent":
            faults.append(
                f"a delivered push left its row at {final['state']!r} rather "
                f"than 'sent'. The record may be wrong about the outcome only "
                f"by being told a wrong outcome, never by not being told.")
        if not final["sent_utc"] or not final["channels_json"]:
            faults.append(
                "the row was never marked with when it went or what happened "
                "on each channel.")
    return faults


def check_the_record_precedes_the_push() -> None:
    """Raise if a push can reach the phone before the record knows."""
    faults = notification_ordering_faults()
    if faults:
        raise LawViolation(
            "A PUSH EXISTS IN THE RECORD:" + _NL2 + _NL2.join(faults))


# NOTHING IS REASONED TWICE (2026-09-05)
# ---------------------------------------------------------------------------
#
# `predict_slate` called `llm.reason` and only then `write_prediction`, which
# returns None for a row that already exists. So the answer was bought and
# thrown away: resuming an interrupted pass, or backfilling the LLM half of a
# slate whose statistical half is written, re-reasoned every question at full
# price.
#
# MEASURED ON 2026-09-05: a resumed UFC pass made 76 reasoning calls to write 8
# rows. Thirty-four questions were answered a second time and discarded --
# about $0.23 against a $2.00 daily cap, on a slate of forty-two.
#
# THE FIX IS ORDER, and the guard is about order: the existence check must be
# reachable BEFORE the call that costs money.

def reason_before_check_faults(source: str | None = None) -> list[str]:
    """Is the existence check asked before the model is?

    READ FROM THE SYNTAX TREE. `predict_slate` is a long loop and a pattern
    match would be satisfied by the check that lives inside `write_prediction`
    much further down -- which is precisely the check that was too late.
    """
    faults: list[str] = []
    if source is None:
        source = (config.PACKAGE_ROOT / "model" / "predict.py").read_text(
            encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"predict.py does not parse: {exc}"]

    loop = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "predict_slate":
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.For):
                loop = sub
    if loop is None:
        faults.append("`predict_slate` has no loop over questions any more; "
                      "this scan cannot see what it was built to see.")
        return faults

    reason_line = check_line = None
    for node in ast.walk(loop):
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name == "reason" and reason_line is None:
                reason_line = node.lineno
            if name == "already_written" and check_line is None:
                check_line = node.lineno

    if reason_line is None:
        faults.append("`llm.reason` is not called in the slate loop, so there "
                      "is nothing for this scan to protect.")
        return faults
    if check_line is None:
        faults.append(
            "the slate loop calls `llm.reason` and never asks "
            "`already_written` first, so a resumed or backfilling run pays "
            "for every question it has already answered.")
    elif check_line > reason_line:
        faults.append(
            f"`already_written` is asked at line {check_line} and "
            f"`llm.reason` at line {reason_line}. The check must come first: "
            f"asked afterwards it is a refund nobody gets.")
    return faults


def horizon_unit_faults(source: str | None = None) -> list[str]:
    """Do the outlook's rate and its multiplier count the same thing?

    `market_outlook` multiplies a rate per slate by the slates remaining. The
    rate comes from `_written_so_far`, which counts the distinct `week` of the
    door's rows (`standing_questions` reads `g.week`); the multiplier comes
    from `slates_remaining`. If the second counts anything else -- and until
    2026-09-05 it counted UTC calendar days -- the projection is off by the
    ratio of the two units, silently, on every gate line of the Record page.
    Read from the syntax tree, so a comment naming a column is not a query
    naming it.

    THE RATE IS READ OFF THE DOOR'S ROWS FROM 2026-09-27 (operator question
    14, 3 of 3): `_written_so_far` was a query grouping by `g.week`, and is
    now a count over the standing questions `standing_questions` hands the
    outlook -- the curve's own rows -- so the unit is checked in both: the
    door must read `g.week`, and the count must key its slates on `week` and
    on no calendar column.
    """
    if source is None:
        source = (config.PACKAGE_ROOT / "horizon.py").read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"horizon.py does not parse: {exc}"]
    sql: dict[str, str] = {}
    keys: dict[str, set] = {}
    names = ("slates_remaining", "_written_so_far", "standing_questions")
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            found = [c.value for c in ast.walk(node)
                     if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            sql[node.name] = " ".join(found)
            keys[node.name] = set(found)
    faults = []
    for name in names:
        if name not in sql:
            faults.append(f"`horizon.{name}` is gone, so this scan cannot see "
                          "what it was built to see.")
    if faults:
        return faults
    remaining = sql["slates_remaining"]
    if "DISTINCT week" not in remaining:
        faults.append("`slates_remaining` does not count `DISTINCT week`, the "
                      "slate key the rate is measured by.")
    for column in ("league_date", "kickoff_utc"):
        if column in remaining:
            faults.append(
                f"`slates_remaining` reads `{column}`: a calendar day is not "
                f"a slate for a weekly sport, and the rate it multiplies is "
                f"per slate. The outlook would overstate a football gate by "
                f"the days in a week.")
    if "g.week" not in sql["standing_questions"]:
        faults.append("`standing_questions` no longer reads `g.week`, so the "
                      "rate's slates are in a unit the multiplier does not "
                      "share.")
    if "week" not in keys["_written_so_far"]:
        faults.append("`_written_so_far` no longer counts its slates by "
                      "`week`, so the rate is in a unit the multiplier does "
                      "not share.")
    for column in ("league_date", "kickoff_utc"):
        if column in sql["_written_so_far"] or column in sql["standing_questions"]:
            faults.append(
                f"the outlook's rate reads `{column}`: a calendar day is not "
                f"the slate `slates_remaining` counts.")
    return faults


def task_run_order_faults(source: str | None = None) -> list[str]:
    """Is the run recorded before the task runs, and finished after?

    READ FROM THE SYNTAX TREE of `tasks.run_task`: the INSERT into task_runs
    must sit before the first `_run_*` call, and an UPDATE must sit after.
    Written at the end -- the shape until 2026-09-05 -- a run that is killed
    leaves no row, and the Health panel shows the last run that finished as
    though nothing had happened since.
    """
    if source is None:
        source = (config.PACKAGE_ROOT / "tasks.py").read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"tasks.py does not parse: {exc}"]
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "run_task"), None)
    if fn is None:
        return ["`tasks.run_task` is gone, so this scan cannot see what it "
                "was built to see."]
    insert_line = update_line = run_line = None
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name == "execute" and node.args and isinstance(node.args[0], ast.Constant):
            text = str(node.args[0].value).lstrip().upper()
            # An explicit boundary: `task_runs_later` is not `task_runs`.
            if re.match(r"INSERT INTO TASK_RUNS[\s(]", text) and insert_line is None:
                insert_line = node.lineno
            if re.match(r"UPDATE TASK_RUNS[\s(]", text) and update_line is None:
                update_line = node.lineno
        elif isinstance(name, str) and name.startswith("_run_") and run_line is None:
            run_line = node.lineno
    faults = []
    if run_line is None:
        return ["`run_task` dispatches to no `_run_*` function; nothing to order."]
    if insert_line is None:
        faults.append("`run_task` never inserts a task_runs row before the "
                      "task runs, so a run that is killed leaves no trace.")
    elif insert_line > run_line:
        faults.append(
            f"the task_runs row is written at line {insert_line}, after the "
            f"task runs at line {run_line}. A run killed in between is a run "
            f"the Health panel never hears about.")
    if update_line is None or (run_line and update_line < run_line):
        faults.append("`run_task` does not finish its row after the task "
                      "runs, so every run reads as still running.")
    faults += _closing_write_faults(fn)
    return faults


def _closing_write_faults(fn: ast.FunctionDef) -> list[str]:
    """Is every write that ends the run's row inside a `try` that catches?

    THE OPERATOR'S RULING of 2026-09-23 (GRIDIRON_REPAIR item 7, built
    2026-09-26): "the run_task closing UPDATE moves inside the try". It sat
    after the handler, so a write that raised left `run_task` with the row
    still 'running' and the process exiting 1 -- `final:cfb` on 9, 21, 23
    and 25 September. Read here as the gate reads the rest of the order:
    every `UPDATE task_runs` in `run_task`, and every commit after the task
    is dispatched, must lie in the BODY of a `try` that has a handler (an
    exception raised inside a handler is not caught by that handler's own
    `try`, so a retry there needs a `try` of its own).

    AND A HANDLER THAT CATCHES WHAT THE WRITE RAISES (the prover of item 7,
    2026-09-26). Any handler used to do: a close inside `try: ... except
    ValueError:` passed this scan while the locked write it exists for, an
    `OperationalError`, still left `run_task`, and so did one whose handler
    caught everything and raised it again. A `try` guards here only if one of
    its handlers catches `Exception` or wider (bare, `Exception`,
    `BaseException`, alone or in a tuple) and raises nothing itself.
    """
    broad = {"Exception", "BaseException"}

    def catches_the_write(handler: ast.ExceptHandler) -> bool:
        kinds = (handler.type.elts if isinstance(handler.type, ast.Tuple)
                 else [handler.type])
        if not any(kind is None or (isinstance(kind, ast.Name) and kind.id in broad)
                   or (isinstance(kind, ast.Attribute) and kind.attr in broad)
                   for kind in kinds):
            return False
        return not any(isinstance(sub, ast.Raise)
                       for statement in handler.body for sub in ast.walk(statement))

    guarded: set[int] = set()
    tries = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())
    for node in ast.walk(fn):
        if isinstance(node, tries) and any(catches_the_write(h) for h in node.handlers):
            for statement in node.body:
                guarded.update(id(sub) for sub in ast.walk(statement))
    dispatched = min((node.lineno for node in ast.walk(fn)
                      if isinstance(node, ast.Call)
                      and str(getattr(node.func, "attr", None)
                              or getattr(node.func, "id", None) or "").startswith("_run_")),
                     default=None)
    faults = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or id(node) in guarded:
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if (name == "execute" and node.args and isinstance(node.args[0], ast.Constant)
                and re.match(r"UPDATE TASK_RUNS[\s(]",
                             str(node.args[0].value).lstrip().upper())):
            faults.append(
                f"the write that ends the run's row, at line {node.lineno}, "
                f"sits outside any try that catches what it raises: if it "
                f"raises -- a second writer holding the record past the wait, "
                f"a payload that cannot be written -- it leaves run_task, the "
                f"process exits 1 and the row stays running (GRIDIRON_REPAIR "
                f"item 7).")
        elif (name == "commit" and dispatched is not None
                and node.lineno > dispatched):
            faults.append(
                f"the commit at line {node.lineno}, after the task runs, sits "
                f"outside any try that catches what it raises: if it raises, "
                f"the run's ending is lost and the row stays running "
                f"(GRIDIRON_REPAIR item 7).")
    return faults


# ---------------------------------------------------------------------------
# EVERY SCHEDULED TASK WAKES THE MACHINE (GRIDIRON_REPAIR item 7, 2026-09-26)
# ---------------------------------------------------------------------------

#: Where every Gridiron-* task is defined. Registering the tasks is the
#: operator's act; what they are registered WITH is this file's.
INSTALLER = config.REPO_ROOT / "tools" / "schedule_install.ps1"


def _powershell_code(script: str) -> str:
    """The script as PowerShell reads it: comments blanked (a `#` line, a
    `<# ... #>` block) and each backtick line continuation joined, strings
    kept whole -- so a comment can neither satisfy nor trip the scan."""
    out: list[str] = []
    i, n = 0, len(script)
    while i < n:
        if script.startswith("<#", i):
            end = script.find("#>", i + 2)
            end = n if end < 0 else end + 2
            out.append(chr(10) * script.count(chr(10), i, end))
            i = end
        elif script[i] == "#":
            end = script.find(chr(10), i)
            i = n if end < 0 else end
        elif script[i] in "\"'":
            quote, j = script[i], i + 1
            while j < n:
                if quote == '"' and script[j] == "`":
                    j += 2
                    continue
                if script[j] == quote:
                    if j + 1 < n and script[j + 1] == quote:
                        j += 2
                        continue
                    break
                j += 1
            out.append(script[i:j + 1])
            i = j + 1
        else:
            out.append(script[i])
            i += 1
    return re.sub(r"`[ \t]*\r?\n", " ", "".join(out))


def _powershell_extent(code: str, start: int, *, until_newline: bool = True) -> str:
    """From `start` to the end of its statement: the next line break outside
    brackets and strings (or, with `until_newline=False`, the bracket that
    closes the one at `start`)."""
    depth, i, n = 0, start, len(code)
    while i < n:
        c = code[i]
        if c in "\"'":
            j = i + 1
            while j < n and code[j] != c:
                j += 2 if (c == '"' and code[j] == "`") else 1
            i = j + 1
            continue
        if c in "({":
            depth += 1
        elif c in ")}":
            depth -= 1
            if not until_newline and depth == 0:
                return code[start:i + 1]
        elif c == chr(10) and depth <= 0 and until_newline:
            return code[start:i]
        i += 1
    return code[start:]


#: THE SWITCH AS THE SCAN ACCEPTS IT: bare, or bound to `$true`, and nothing
#: else (the prover of item 7, 2026-09-26). The first scan refused only
#: `-WakeToRun:$false`, so `-WakeToRun:0`, `:$null`, `:$off` and
#: `:(1 -eq 2)` -- each a switch PowerShell binds to false -- passed as waking.
#: The value after a colon is read as one token and must be `$true`.
_WAKE_SWITCH = re.compile(r"(?<![\w-])-WakeToRun\b(?:\s*:\s*([^\s`)]*))?", re.I)


def _wakes(settings: str) -> bool:
    """Does this settings expression carry the switch in a form read as true?"""
    return any(m.group(1) is None or m.group(1).lower() == "$true"
               for m in _WAKE_SWITCH.finditer(settings))


def _settings_wake(statement: str, scope: str) -> str | None:
    """Why a registration's settings do not wake the machine, or None if
    they do. `scope` is the code a `$variable` given as the settings is
    looked up in.

    A VARIABLE IS READ ONLY IF IT IS MADE ONCE AND ONLY PASSED ON (the prover
    of item 7, 2026-09-26). The first scan read the last assignment that
    called `New-ScheduledTaskSettingsSet` and nothing else, so a set made with
    the switch and then changed (`$settings.WakeToRun = $false`, a property
    set through `PSObject`) or made again (`$settings = (New-...)`, `$settings
    = $plain`) passed while the task registered without the wake. Now the
    variable must be assigned exactly once, straight from
    `New-ScheduledTaskSettingsSet`, and mentioned nowhere else in its scope
    than that assignment and `-Settings $it`; anything more is named.
    """
    # THE PARAMETER, never the end of a command's name (`Update-Settings`).
    found = re.search(r"(?<![\w-])-Settings\s+", statement, re.I)
    if found is None:
        return "it is registered with no settings at all"
    rest = statement[found.end():]
    if rest.startswith("("):
        settings = _powershell_extent(rest, 0, until_newline=False)
    elif (var := re.match(r"\$\{?(?:(?:script|global|local|private):)?(\w+)\}?", rest, re.I)):
        name = var.group(1)
        mention = (r"\$\{?(?:(?:script|global|local|private):)?"
                   + re.escape(name) + r"\b\}?")
        assigned = list(re.finditer(mention + r"\s*[-+*/%]?=", scope, re.I))
        assigned += list(re.finditer(
            r"(?<![\w-])(?:Set|New)-Variable\b[^" + chr(10) + r"]*?(?<![\w$])"
            + re.escape(name) + r"\b", scope, re.I))
        if not assigned:
            return f"its settings, ${name}, are made nowhere the scan can read"
        if len(assigned) > 1:
            return (f"its settings, ${name}, are assigned {len(assigned)} times; "
                    f"the scan reads only a settings set made once")
        mentions = len(re.findall(mention, scope, re.I))
        passed = len(re.findall(r"(?<![\w-])-Settings\s+" + mention, scope, re.I))
        if mentions != 1 + passed:
            return (f"its settings, ${name}, are used or changed after they are "
                    f"made, which the scan cannot read")
        made = scope[assigned[0].end():]
        if not re.match(r"\s*\(?\s*New-ScheduledTaskSettingsSet\b", made, re.I):
            return (f"its settings, ${name}, are not made by "
                    f"New-ScheduledTaskSettingsSet")
        settings = _powershell_extent(scope, assigned[0].end())
    else:
        return "its settings are an expression the scan cannot read"
    if not re.search(r"New-ScheduledTaskSettingsSet\b", settings, re.I):
        return "its settings are not made by New-ScheduledTaskSettingsSet"
    return (None if _wakes(settings) else
            "its settings do not carry -WakeToRun in a form read as true")


def installer_wake_faults(script: str | None = None) -> list[str]:
    """Every Gridiron-* task the installer defines without -WakeToRun, by name.

    THE OPERATOR'S RULING of 2026-09-23 (GRIDIRON_REPAIR item 7, built
    2026-09-26): "every Gridiron-* task gains WakeToRun". EVERY: Live and
    Serve too. Read from the installer's code, never its comments: each
    task registered through `New-GridironTask` carries that helper's
    settings, each registered directly its own, and a name in `$TaskNames`
    the file registers nowhere the scan can read is named too, as is any
    other way of defining a task (`schtasks`, `Set-ScheduledTask`,
    `New-ScheduledTask`), whose settings it cannot see. The registered tasks
    on the machine are the operator's; this reads what they are made from.
    """
    if script is None:
        script = INSTALLER.read_text(encoding="utf-8")
    code = _powershell_code(script)
    faults: list[str] = []

    def named(text: str) -> str:
        return text.replace("$($Prefix)", "Gridiron-")

    block = re.search(r"\$TaskNames\s*=\s*@\(", code)
    listed = ([named(m) for m in re.findall(
        r'"([^"]+)"', _powershell_extent(code, block.end() - 1, until_newline=False))]
        if block else [])
    if not listed:
        faults.append("the installer lists no $TaskNames, so the scan cannot "
                      "say which tasks it must find.")

    helper = re.search(r"function\s+New-GridironTask\s*\{", code, re.I)
    body = (_powershell_extent(code, helper.end() - 1, until_newline=False)
            if helper else "")
    outside = (code[:helper.start()] + code[helper.end() - 1 + len(body):]
               if helper else code)
    through_helper = None
    if helper:
        inner = re.search(r"Register-ScheduledTask\b", body, re.I)
        through_helper = ("it registers nothing" if inner is None else
                          _settings_wake(_powershell_extent(body, inner.start()), body))

    registered: dict[str, str | None] = {}
    for call in re.finditer(r"(?<![\w-])New-GridironTask\b", outside, re.I):
        statement = _powershell_extent(outside, call.start())
        name = re.search(r'-Name\s+"([^"]+)"', statement, re.I)
        if name is None:
            faults.append("a task is registered through New-GridironTask with "
                          "no name the scan can read.")
            continue
        if helper is None:
            registered[named(name.group(1))] = "New-GridironTask is defined nowhere"
        else:
            registered[named(name.group(1))] = (
                None if through_helper is None
                else f"it is registered through New-GridironTask, and {through_helper}")
    for call in re.finditer(r"(?<![\w-])Register-ScheduledTask\b", outside, re.I):
        statement = _powershell_extent(outside, call.start())
        name = re.search(r'-TaskName\s+"([^"]+)"', statement, re.I)
        if name is None:
            faults.append("a task is registered directly with no name the scan "
                          "can read.")
            continue
        registered[named(name.group(1))] = _settings_wake(statement, outside)
    for other in re.finditer(r"(?<![\w-])(schtasks|Set-ScheduledTask|New-ScheduledTask)"
                             r"(?![\w-])", code, re.I):
        faults.append(f"a task is defined or changed by {other.group(1)}, whose "
                      f"settings the scan cannot read; define every task "
                      f"through New-GridironTask or Register-ScheduledTask.")
    for name, why in sorted(registered.items()):
        if why is not None:
            faults.append(
                f"{name}: {why}, so a sleeping machine sleeps through it. The "
                f"operator's ruling of 2026-09-23 (GRIDIRON_REPAIR item 7): "
                f"every Gridiron-* task gains WakeToRun.")
    for name in listed:
        if name not in registered:
            faults.append(f"{name} is in $TaskNames and the installer registers "
                          f"it nowhere the scan can read, so nothing says it "
                          f"wakes the machine.")
    return faults


def check_every_task_wakes_to_run() -> None:
    """Raise, naming each task, unless every Gridiron-* task the installer
    defines wakes the machine to run (GRIDIRON_REPAIR item 7)."""
    faults = installer_wake_faults()
    if faults:
        raise LawViolation(
            "EVERY SCHEDULED TASK WAKES THE MACHINE TO RUN:" + _NL2 + _NL2.join(faults))


#: THE ROWS OF CONTROLS ABOVE THE HERO ON PICKS (R2, 2026-09-05), declared.
#: A control row is a direct child of `#view-week`, above the FIRST CARD,
#: that holds a button, a select or an input where a reader can see it -- a
#: collapsed `<details>` is not a row until it is opened. Two rows, and a
#: third is how a page grows a fourth segmented control, then a fifth, each
#: defensible alone.
#:
#: THE LANDMARK MOVED ON 2026-09-08 and the number did not. The rule was
#: anchored on `#week-hero`, which THREE_STATES removed along with the sort
#: segment, the tier buttons and the View menu; the first card is `#today`
#: now. The two rows that remain are the market chips and the state tabs, so
#: the page carries fewer controls above its first card than when this rule
#: was written, not more.
#: RE-POINTED AT THE GAMES PAGE (GRIDIRON_BOARD, 2026-09-24). The Picks route
#: is gone; the first thing on Games is the rows themselves, and the brief
#: puts NO control row above them: the sport and page tabs are in the header,
#: the pulse is words, and the week picker sits beneath the rows behind a
#: <details>. So the declared list is empty, and any control row that
#: appears above the first game row is a fault by name.
#: ONE ROW DECLARED, 2026-09-25: the sort-and-filter bar the visual brief
#: asks for ("Sort and filter bar on Games and Props"). The 2026-09-24 brief
#: put none above the rows; the later brief asks for this one by name, so it
#: is declared here with its date rather than slipped past the scan. A second
#: one is still a fault, and the planting still plants an undeclared row.
#: RULED BY THE OPERATOR the same day (the merge brief, ruling 2): "the sort
#: and filter bar stays above the rows, as built."
PICKS_FIRST_CARD = "id=\"games-rows\""
PICKS_CONTROL_ROWS: tuple[str, ...] = ("games-controls",)

_VOID_TAGS = frozenset({"input", "br", "img", "hr", "meta", "link", "source", "wbr"})


def picks_control_rows(html: str) -> list[str]:
    """The names (id, else class) of every control row above the hero."""
    from html.parser import HTMLParser

    html = _without_comments(html, "html")
    start = html.find('id="view-games"')
    end = html.find(PICKS_FIRST_CARD)
    if start < 0 or end < 0:
        return ["<view-games or the first game row missing>"]
    section = html[html.rfind("<", 0, start): html.rfind("<", 0, end)]

    class Walker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.rows: list[str] = []
            self.current: dict | None = None
            self.details = 0

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if self.depth == 1 and tag not in _VOID_TAGS:
                # A <nav> is a row of controls by nature: the market tabs are
                # filled at render, so their markup holds no button to find.
                self.current = {"name": attrs.get("id") or attrs.get("class") or tag,
                                "interactive": tag == "nav"}
            if tag == "details":
                self.details += 1
            if (tag in ("button", "select", "input", "textarea") and self.current
                    and not self.details):
                self.current["interactive"] = True
            if tag not in _VOID_TAGS:
                self.depth += 1

        def handle_endtag(self, tag):
            if tag in _VOID_TAGS:
                return
            self.depth -= 1
            if tag == "details":
                self.details -= 1
            if self.depth == 1 and self.current is not None:
                if self.current["interactive"]:
                    self.rows.append(self.current["name"])
                self.current = None

    walker = Walker()
    walker.feed(section)
    return walker.rows


def picks_control_row_faults(html: str | None = None) -> list[str]:
    """A control row above the hero that was not declared."""
    if html is None:
        html = (config.PACKAGE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    rows = picks_control_rows(html)
    faults = []
    for name in rows:
        if name not in PICKS_CONTROL_ROWS:
            faults.append(
                f"a row of controls named {name!r} sits above the first game "
                f"row on Games, and the declared rows are "
                f"{list(PICKS_CONTROL_ROWS)}. The board brief puts the tabs in "
                f"the header and nothing above the rows; a control row here is "
                f"how a page grows a fifth segmented control.")
    if len(rows) > len(PICKS_CONTROL_ROWS):
        faults.append(f"{len(rows)} control rows above the first card; "
                      f"{len(PICKS_CONTROL_ROWS)} are declared: {rows}")
    return faults


def check_picks_has_two_control_rows() -> None:
    """Raise if Picks carries a control row above the hero beyond the two."""
    faults = picks_control_row_faults()
    if faults:
        raise LawViolation(
            "A CONTROL ROW ABOVE THE FIRST GAME ROW:" + _NL2 + _NL2.join(faults))


def retired_market_faults(conn) -> list[str]:
    """Every prediction written in a retired market at or after the moment
    its door closed (`from`), by id. The retirement binds from that moment
    forward and never before: rows written earlier, even on the same day, are
    the market's record and stay."""
    faults: list[str] = []
    for (sport, market), entry in config.RETIRED_MARKETS.items():
        is_prop = market in config.SPORT_PROP_MARKETS.get(sport, ())
        rows = conn.execute(
            "SELECT id, created_utc FROM predictions WHERE sport = ?"
            "   AND " + ("prop_type = ?" if is_prop else "market_type = ?")
            + "   AND created_utc >= ? ORDER BY id",
            (sport, market, entry.get("from") or entry["retired"] + "T00:00:00Z")
        ).fetchall()
        for r in rows:
            faults.append(
                f"prediction {r['id']} asks {sport} {market} at {r['created_utc']}, "
                f"and that market was retired on {entry['retired']} "
                f"({entry['reason']}; the door closed at "
                f"{entry.get('from') or entry['retired']})")
    return faults


def check_no_retired_market_written(conn) -> None:
    """Raise, by prediction id, if a retired market was asked after its day."""
    faults = retired_market_faults(conn)
    if faults:
        raise LawViolation(
            "A RETIRED MARKET WAS ASKED:" + _NL2 + _NL2.join(faults[:12]))


def retired_in_picks_faults() -> list[str]:
    """A retired market offered as a tab on Picks."""
    from . import views

    faults: list[str] = []
    for (sport, market), entry in config.RETIRED_MARKETS.items():
        offered = [t["market"] for t in views._market_tabs(sport, [])]
        if market in offered:
            faults.append(
                f"Picks offers a {sport} {market} tab, and that market was "
                f"retired on {entry['retired']}. A retired market keeps its "
                f"row on Record and has no tab on Picks.")
    return faults


def check_no_retired_market_in_picks() -> None:
    """Raise if a retired market is still a tab on Picks."""
    faults = retired_in_picks_faults()
    if faults:
        raise LawViolation(
            "A RETIRED MARKET IS ON PICKS:" + _NL2 + _NL2.join(faults))


def check_record_fingerprint(conn) -> None:
    """Raise, by prediction id, if any protected field has drifted from the
    fingerprint taken when the row was written, if any row has no fingerprint,
    or if the declared baseline no longer reproduces (ruling 4, 2026-09-05)."""
    from . import fingerprint

    faults = fingerprint.drift(conn, config.RECORD_BASELINE)
    if faults:
        raise LawViolation(
            "THE RECORD DOES NOT MATCH ITS FINGERPRINT (LAW 3):" + _NL2
            + _NL2.join(faults[:12])
            + (_NL2 + f"... and {len(faults) - 12} more" if len(faults) > 12 else ""))


def check_a_run_is_recorded_before_it_runs() -> None:
    """Raise if a task could die without leaving a row."""
    faults = task_run_order_faults()
    if faults:
        raise LawViolation(
            "THE RECORD PRECEDES THE RUN:" + _NL2 + _NL2.join(faults))


def check_the_horizon_counts_in_one_unit() -> None:
    """Raise if the outlook's rate and multiplier count different things."""
    faults = horizon_unit_faults()
    if faults:
        raise LawViolation(
            "THE OUTLOOK MULTIPLIES TWO UNITS:" + _NL2 + _NL2.join(faults))


def check_nothing_is_reasoned_twice() -> None:
    """Raise if the model is asked before the record is."""
    faults = reason_before_check_faults()
    if faults:
        raise LawViolation(
            "NOTHING IS REASONED TWICE:" + _NL2 + _NL2.join(faults))


# NO CODE NAME REACHES A READER THROUGH THE SECOND FORECASTER (2026-09-05)
# ---------------------------------------------------------------------------
#
# THE PLAIN-WORDS LAW HAD A HOLE AND THE LLM WALKED THROUGH IT. The prompt used
# to name factors by their code names, and the model quoted them back into
# prose that appears on a card: measured 2026-09-05 at 19 of 42 new UFC rows
# and 8 of 23 older MLB ones -- 27 of 65 stored rows, about 45%.
#
# IT WAS NEVER LOOKED AT. The rendered-page scan exists and runs, but Picks
# opens on `PICKS_DEFAULT_FORECASTER = "statistical"` and no test ever moved
# the selector, so the LLM's prose had not been read by any guard since the
# forecaster was built.
#
# TWO REPAIRS, and this watches both. The prompt now uses plain names, so no
# NEW row can carry one. Old rows are humanised AT RENDER TIME -- LAW 3 forbids
# editing what a forecaster said -- through `language.humanise_reasoning`.

def llm_prose_faults(conn) -> list[str]:
    """Does any rendered LLM card carry an internal identifier?

    Rendered through `views.week(..., forecaster='llm')`, which is the call the
    page makes, so this reads what a reader would read.
    """
    from . import config, views

    faults: list[str] = []
    looked_at = 0
    for sport in config.SPORTS:
        try:
            payload = views.week(conn, sport, forecaster="llm")
        except Exception as exc:                                  # noqa: BLE001
            faults.append(f"{sport}: the LLM view could not be rendered at "
                          f"all ({type(exc).__name__}: {exc})")
            continue
        for card in payload.get("cards") or []:
            if card.get("predictor") != "llm":
                continue
            looked_at += 1
            for field in ("reasoning", "phrase", "chance_clause"):
                hits = plain_words_violations(card.get(field) or "")
                if hits:
                    # IDENTIFIED BY ROW, NOT BY TEAM. Naming the subject here
                    # would put a raw side into a sentence, which
                    # `check_side_named_everywhere` refuses for good reason --
                    # on a moneyline the subject is the HOME club, so a
                    # message built from it names the side the model forecast
                    # AGAINST on every pick against the home team. A
                    # prediction id is unambiguous and points at one row.
                    faults.append(
                        f"{sport} prediction {card.get('prediction_id')}: the "
                        f"second forecaster's {field} shows {hits[0]}")
    if looked_at == 0 and not faults:
        # NOT A PASS. A scan that saw nothing proves nothing, and this one
        # went unwritten for weeks precisely because nobody looked.
        faults.append(
            "no LLM card was rendered on any slate, so this scan checked "
            "nothing. It is reported rather than passed: the hole it exists "
            "for was invisible for weeks because the view was never opened.")
    return faults


def check_no_code_names_in_llm_prose(conn) -> None:
    """Raise if the second forecaster shows a reader an internal identifier."""
    faults = llm_prose_faults(conn)
    if faults:
        raise LawViolation(
            "NO CODE NAME REACHES A READER:" + _NL2 + _NL2.join(faults))


# AN INDICATOR IS HANDED OVER IN WORDS (2026-09-05)
# ---------------------------------------------------------------------------
#
# TWENTY-SEVEN OF 103 FACTORS ARE ENCODED and the prompt used to hand the model
# the bare number. It reasoned correctly and wrote "(a three-round bout,
# ufc_scheduled_rounds = 0)" -- right, and it reads to a person as zero rounds.
# A model reasons better from "three rounds" than from "= 0", and so does
# anyone reading the prose afterwards.
#
# A DECLARED READING IS THE ONLY ONE. `reads` maps an exact value to a phrase
# and `unit` gives a quantity its real units; anything undeclared keeps its
# number, because a guessed unit is worse than a bare one -- uninformative
# versus wrong.

#: Rationale wording that says a factor is an indicator. The author writes it,
#: so it is a declaration rather than an inference -- and a new indicator whose
#: rationale says so and which declares no `reads` is exactly what this
#: catches.
_INDICATOR_WORDS = re.compile(
    "|".join([
        r"indicator",
        r"dummy coding",
        "reads as 1",
        # The DECLARATIVE form: "One when X, zero otherwise".
        r"(?:1|One) when[^.]*zero otherwise",
    ]), re.I)


def indicator_words_faults() -> list[str]:
    """Is any indicator still handed to the model as a bare number?

    BEHAVIOURAL for the declared ones: each is rendered at each of its levels
    and the output is read. DECLARATIVE for the rest: a factor whose own
    rationale calls it an indicator and declares no reading is named.
    """
    from .factors import registry
    from .model import llm

    faults: list[str] = []
    for entry in registry.all_factors():
        declared = bool(entry.reads)
        if declared:
            for level, phrase in entry.reads.items():
                rows = [{"factor": entry.name, "why": entry.why,
                         "reads": entry.reads, "unit": entry.unit,
                         "unit_scale": entry.unit_scale,
                         "unit_offset": entry.unit_offset,
                         "value": level, "present": True,
                         "rationale": entry.rationale}]
                text = llm.build_prompt("a claim", rows, [])
                if f"- {phrase}" not in text:
                    faults.append(
                        f"{entry.name} declares that {level:g} reads "
                        f"{phrase!r} and the prompt does not say it.")
                if re.search(rf"- .*{re.escape(entry.name)}.*=", text):
                    faults.append(
                        f"{entry.name} is handed to the model as a bare "
                        f"number under its code name.")
                if re.search(rf"- {re.escape(phrase)} = ", text):
                    faults.append(
                        f"{entry.name} says {phrase!r} and then appends a "
                        f"number to it, which puts back exactly what the "
                        f"phrase replaced.")
        elif _INDICATOR_WORDS.search(entry.rationale or ""):
            faults.append(
                f"{entry.name}'s own rationale calls it an indicator and it "
                f"declares no `reads`, so the model is told a bare 0 or 1 and "
                f"a reader sees whatever it quotes back.")
    return faults


def check_indicators_are_words(_conn=None) -> None:
    """Raise if an indicator reaches the model as a number."""
    faults = indicator_words_faults()
    if faults:
        raise LawViolation(
            "AN INDICATOR IS HANDED OVER IN WORDS:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# HIDDEN MEANS NOT PAINTED (UI audit, 2026-09-05)
# ---------------------------------------------------------------------------
#
# `hidden` is the attribute the app toggles to show and hide things, and the
# user-agent stylesheet gives it `display: none` at the lowest priority there
# is. Any class rule that sets `display` beats it: `.show-all { display: block }`
# left the show-all button painted and clickable after it had shown all;
# `.yesterday { display: flex }` painted an empty strip with a rule across the
# page; `.view-panel { display: grid }` painted the closed view menu. Each was
# hidden to every test that read the attribute. The class ends with one rule --
# `[hidden] { display: none !important; }` -- and this check refuses a
# stylesheet that lacks it, so it cannot be tidied away.

_HIDDEN_RULE = re.compile(r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important[^}]*\}")


def hidden_rule_faults(css: str) -> list[str]:
    """Does the stylesheet still declare that hidden wins?"""
    css = _without_comments(css, "css")
    if _HIDDEN_RULE.search(css):
        return []
    return ["style.css no longer declares `[hidden] { display: none !important }`, "
            "so any class rule that sets `display` paints an element the app has "
            "hidden -- the show-all button stays clickable after it has shown all, "
            "the empty yesterday strip draws a rule across the page, and every "
            "test that reads the attribute passes."]


def check_hidden_is_not_painted(root: Path | None = None) -> None:
    """Raise unless the one rule that makes `hidden` win is in the stylesheet."""
    base = (config.PACKAGE_ROOT / "web") if root is None else Path(root)
    faults = hidden_rule_faults((base / "style.css").read_text(encoding="utf-8"))
    if faults:
        raise LawViolation("HIDDEN MEANS NOT PAINTED:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# ONE ANSWER PER QUESTION ASKED (UI audit finding 1, 2026-09-05)
# ---------------------------------------------------------------------------
#
# Every request app.js makes carries the sport, and for a month every answer
# painted the moment it arrived, in whatever order the network chose. College
# football's slate answers slowest, so NCAAF then UFC within a second put UFC's
# tabs over football's cards, and the empty NBA tab showed 243 football picks.
# The mechanism is two sequence numbers -- `sportSeq` on every sport switch,
# `weekSeq` on every slate render -- taken before the fetch and checked after
# it. This tripwire reads every sport-scoped fetch in app.js and refuses one
# that paints without the check. A regex, not a parser (see the renderer-prose
# note above); it catches the shape that shipped.

_JS_SPORT_FETCH = "await fetchJSON(withSport("


def render_guard_faults(source: str) -> list[str]:
    """Which sport-scoped fetches paint without checking they are still wanted?"""
    source = _without_comments(source, "js")
    faults: list[str] = []
    week = re.search(r"async function renderGames\(\)\s*\{(?P<body>[\s\S]*?)\n  \}", source)
    if week is None:
        faults.append("`renderGames` is gone from app.js; nothing renders the slate.")
    else:
        body = week.group("body")
        at = body.find(_JS_SPORT_FETCH + "'/api/week'")
        if at < 0 or "++weekSeq" not in body[:at]:
            faults.append("`renderGames` takes no sequence number before it asks for the "
                          "slate, so two renders in flight paint in arrival order.")
        elif "!== weekSeq" not in body[at:at + 240]:
            faults.append("`renderGames` does not drop an answer a later render has "
                          "superseded; the slower slate takes the page.")
    if not re.search(r"async function selectSport\([^)]*\)\s*\{[\s\S]*?\+\+sportSeq", source):
        faults.append("`selectSport` no longer moves `sportSeq` on, so nothing asked "
                      "for the previous sport knows it is stale.")
    lines = source.split("\n")
    for i, line in enumerate(lines):
        if _JS_SPORT_FETCH not in line or "'/api/week' + qs" in line:
            continue
        # THE CHECK SITS AFTER THE ANSWER, and an answer can span a
        # continuation line and a catch block before anything is painted (the
        # live tick); fourteen lines covers the longest shape that ships.
        window = "\n".join(lines[i:i + 14])
        if "stale(seq)" not in window and "!== weekSeq" not in window:
            faults.append(f"app.js line {i + 1}: `{line.strip()[:70]}` paints its answer "
                          "without checking whether the sport has changed since it asked.")
    return faults


def check_a_superseded_answer_is_dropped(root: Path | None = None) -> None:
    """Raise unless every sport-scoped fetch in app.js checks its sequence."""
    base = (config.PACKAGE_ROOT / "web") if root is None else Path(root)
    faults = render_guard_faults((base / "app.js").read_text(encoding="utf-8"))
    if faults:
        raise LawViolation("ONE ANSWER PER QUESTION ASKED:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE HEALTH PANEL SPEAKS IN WORDS (UI audit finding 11, 2026-09-05)
# ---------------------------------------------------------------------------
#
# A task that fails records `f"{type(exc).__name__}: {exc}"`, and the Settings
# page placed that as it was: a Python class name, a slate key and an ISO
# stamp in visible text. The rendered-page scan covers the route and never saw
# it, because the fixture world had no failed run. `language.task_detail_words`
# is the door; this check walks the health payload the page is handed and runs
# every detail through the plain-words scan.


def health_detail_faults(health: dict) -> list[str]:
    """Which task details on the Health panel are not plain words?"""
    faults: list[str] = []
    for entry in (health or {}).get("tasks", []):
        details = [entry.get("last_detail")] + [m.get("detail") for m in entry.get("missed", [])]
        for detail in details:
            if not detail:
                continue
            for hit in plain_words_violations(str(detail)):
                faults.append(f"{entry.get('task')}: {hit}")
    return faults


def check_health_speaks_plain(conn) -> None:
    """Raise unless every task detail the Settings page shows is plain words."""
    from . import tasks
    faults = health_detail_faults(tasks.status(conn))
    if faults:
        raise LawViolation("THE HEALTH PANEL SPEAKS IN WORDS:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE REASONING PASS RUNS ON GAME MARKETS ONLY (ruling E1, 2026-09-06)
# ---------------------------------------------------------------------------


def llm_routing_faults() -> list[str]:
    """Where the LLM roster disagrees with the ruling: a prop market on it, a
    market the sport does not declare, a sport with no entry, no date."""
    faults: list[str] = []
    if not getattr(config, "LLM_ROUTING_DECLARED", None):
        faults.append("LLM_MARKETS_BY_SPORT carries no declaration date.")
    for sport in config.SPORTS:
        if sport not in config.LLM_MARKETS_BY_SPORT:
            faults.append(f"{sport} has no LLM roster; the pass would be asked "
                          f"nothing or everything by accident.")
            continue
        for market in config.LLM_MARKETS_BY_SPORT[sport]:
            if market in config.SPORT_PROP_MARKETS.get(sport, ()):
                faults.append(f"{sport}:{market} is a prop market on the LLM "
                              f"roster; the reasoning pass runs on game markets "
                              f"only, by ruling of 2026-09-06.")
            elif market not in config.SPORT_MARKETS.get(sport, ()):
                faults.append(f"{sport}:{market} is on the LLM roster and {sport} "
                              f"does not declare that market.")
    return faults


def check_llm_runs_on_game_markets_only() -> None:
    faults = llm_routing_faults()
    if faults:
        raise LawViolation("THE REASONING PASS RUNS ON GAME MARKETS ONLY:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# A FORECAST, NEVER ADVICE (AT_THE_LINE E4, 2026-09-06)
# ---------------------------------------------------------------------------
#
# The at-the-line record puts the model's probability next to a venue's price.
# That pair is the most decision-relevant thing this project produces, and it
# is exactly where a forecaster starts sounding like a tipster: one adjective
# is the difference between "the model says 58%, the price says 52%" and a
# recommendation, which LAW 5 forbids.
#
# So the vocabulary is scanned rather than trusted, in two places with two
# different lists, because the two kinds of text are not ours in the same way:
#
#   * TEXT THIS PROJECT COMPOSES -- every label, line and note in the
#     at-the-line payload -- may not use any of `ADVICE_WORDS`. We write those
#     sentences, so a false positive is fixed by writing a better sentence.
#   * THE MODEL'S OWN PROSE, quoted on a card, is scanned for the shorter list
#     in `TIPSTER_WORDS`: words no sentence about a football game needs and
#     that only ever arrive as a recommendation. "Value" is on the first list
#     and not the second, because a reasoning line may legitimately discuss the
#     value of a running game, and two stored rows already do.
ADVICE_WORDS: tuple[str, ...] = (
    "value", "play", "plays", "bet", "bets", "lock", "hammer", "fade", "smash",
    "best bet", "best bets", "top play", "top plays", "free money",
    "sure thing", "no-brainer",
    # THE SHORTLIST'S OWN TEMPTATIONS (THE_SHORTLIST S2, 2026-09-07). A page
    # that puts twenty questions in front of a reader every morning is one
    # adjective away from being a tip sheet, and the two read almost the same
    # until you notice that one of them is telling you what to do.
    "card of the day", "pick of the day", "worth it", "worth backing",
    # "leans" is NOT here, and the render is why. The hero already says "the
    # model leans harder on its own reading", which is a sentence about a
    # probability and not a recommendation; adding the word would have made the
    # project's own honest prose a violation and taught the next reader that
    # the list is arbitrary.
)

#: The subset that is advice wherever it appears, including in prose the model
#: wrote and we only quote.
TIPSTER_WORDS: tuple[str, ...] = (
    "lock", "hammer", "smash", "best bet", "free money", "sure thing",
    "no-brainer",
)


def _word_scan(words: tuple[str, ...]) -> "re.Pattern[str]":
    # GROUPED (2026-09-24). Without the group the two boundaries bound only the
    # first word and the last: "lock" matched inside "body-clock", and the gate
    # refused two reasoning lines about a west-coast team's 1pm start as tips.
    joined = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z])(?:{joined})(?![A-Za-z])", re.IGNORECASE)


_ADVICE_SCAN = _word_scan(ADVICE_WORDS)
_TIPSTER_SCAN = _word_scan(TIPSTER_WORDS)


def advice_word_faults(text: str, where: str = "the page") -> list[str]:
    """Words that turn a forecast into a recommendation."""
    return [f"{where} says {hit.lower()!r}, which reads as advice rather than a "
            f"forecast (LAW 5)"
            for hit in sorted(set(_ADVICE_SCAN.findall(text or "")))]


def at_the_line_advice_faults(payload) -> list[str]:
    """Every string in an at-the-line payload, scanned. The payload is what the
    interface renders, so this is the text a reader actually meets."""
    faults: list[str] = []

    def walk(node, path):
        if isinstance(node, str):
            faults.extend(advice_word_faults(node, path))
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, (list, tuple)):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(payload, "$")
    return sorted(set(faults))


def check_the_at_the_line_words_are_a_forecast(payload) -> None:
    faults = at_the_line_advice_faults(payload)
    if faults:
        raise LawViolation(
            "LAW 5: the at-the-line record is a forecast beside a price, and "
            "its words have started recommending something:"
            + _NL2 + _NL2.join(faults[:8]))


def tipster_faults_in_quoted_prose(conn) -> list[str]:
    """Stored reasoning that recommends rather than explains."""
    faults = []
    for row in conn.execute(
            "SELECT id, reasoning FROM predictions WHERE reasoning IS NOT NULL"):
        for hit in sorted(set(_TIPSTER_SCAN.findall(row["reasoning"]))):
            faults.append(
                f"prediction {row['id']} quotes {hit.lower()!r} in its reasoning, "
                f"which is a recommendation and not an explanation (LAW 5)")
    return sorted(set(faults))


def check_no_quoted_prose_recommends(conn) -> None:
    faults = tipster_faults_in_quoted_prose(conn)
    if faults:
        raise LawViolation(
            "LAW 5: a stored reasoning line reads as a tip, and the card shows "
            "it verbatim:" + _NL2 + _NL2.join(faults[:8]))


# ---------------------------------------------------------------------------
# THE EDGE MOVES NO ORDERING UNTIL ITS MARKET HAS EARNED ONE
# (THE_SHORTLIST S1, 2026-09-07)
# ---------------------------------------------------------------------------
#
# The shortlist ranks questions by three declared inputs, and the third --
# how far the model sits from the market's price -- is the one that would do
# the most damage first. With almost nothing resolved, the questions where
# this model most disagrees with a market that prices thousands of games are
# mostly the questions where THIS MODEL IS WRONG. A shortlist built on them
# would surface its own worst errors and call them the clearest of the day.
#
# So the edge is stored and shown, and carries no weight until its own market
# has passed the same hundred-resolution gate every other edge figure needs.
# This scan does not take the ranker's word for it: it recomputes each stored
# score from the components stored beside it and refuses a row whose number
# cannot be reproduced from its own declared inputs. A rank that weighted an
# ungated edge cannot survive that, whatever flag it wrote next to itself.

RANK_TOLERANCE = 1e-6


def edge_weight_faults(conn) -> list[str]:
    """Stored ranks that do not follow from their own declared inputs."""
    from . import config, shortlist

    faults: list[str] = []
    rows = conn.execute(
        "SELECT id, prediction_id, ranker_version, sport, market_type, prop_type,"
        " rank_score, confidence, completeness, edge, edge_counted, edge_gate_n"
        " FROM prediction_ranks").fetchall()
    for row in rows:
        counted = bool(row["edge_counted"])
        if counted and row["edge"] is None:
            faults.append(
                f"rank {row['id']} (prediction {row['prediction_id']}) counted an "
                f"edge it does not have: an unquoted market is an absence, not a "
                f"zero disagreement")
            continue
        if counted and (row["edge_gate_n"] or 0) < config.RANK_EDGE_GATE:
            faults.append(
                f"rank {row['id']} (prediction {row['prediction_id']}) weighted the "
                f"edge for {row['sport']} {row['market_type']} at "
                f"{row['edge_gate_n']} settled, below the {config.RANK_EDGE_GATE} "
                f"that market must reach before disagreement may move an ordering")
            continue
        try:
            expected = shortlist.combine(
                row["confidence"], row["completeness"], row["edge"],
                edge_counted=counted)
        except shortlist.RankIsNotAClaim as exc:
            faults.append(f"rank {row['id']}: {exc}")
            continue
        if abs(expected - row["rank_score"]) > RANK_TOLERANCE:
            faults.append(
                f"rank {row['id']} (prediction {row['prediction_id']}) stores "
                f"{row['rank_score']} where its own inputs give {expected}. A score "
                f"that does not follow from its declared components is a formula "
                f"nobody can check, and the likeliest cause is an ungated edge "
                f"moving the ordering.")
    return sorted(set(faults))[:20]


def check_the_edge_moves_no_ungated_ordering(conn) -> None:
    faults = edge_weight_faults(conn)
    if faults:
        raise LawViolation(
            "THE SHORTLIST WEIGHTED AN EDGE ITS MARKET HAS NOT EARNED:"
            + _NL2 + _NL2.join(faults[:8]))


def slate_advice_faults(payload) -> list[str]:
    """The shortlist's own words, and every sentence it puts on a card.

    A SHORTLIST IS THE SHAPE A TIP SHEET TAKES. What separates this page from
    one is the vocabulary: it says how sure the model is and how complete the
    evidence was, and it never says what to do about it. That distinction is
    one careless label away from gone, so it is scanned rather than trusted --
    here, and by a planted "top plays" in `tools/guards/plant.py`.
    """
    faults = at_the_line_advice_faults(payload.get("shortlist") or {})
    for card in payload.get("cards") or []:
        faults.extend(advice_word_faults(card.get("rank_line") or "",
                                         f"the ordering line on prediction "
                                         f"{card.get('prediction_id')}"))
    return sorted(set(faults))


def check_the_shortlist_speaks_of_questions(payload) -> None:
    faults = slate_advice_faults(payload)
    if faults:
        raise LawViolation(
            "LAW 5: the shortlist has started recommending rather than "
            "ordering:" + _NL2 + _NL2.join(faults[:8]))


# ---------------------------------------------------------------------------
# THE APP RECOMMENDS, IT NEVER TRANSACTS (LAW 5 as amended 2026-09-07)
# ---------------------------------------------------------------------------
#
# The old law forbade the arithmetic. This one permits the arithmetic and
# forbids the machinery, which is a harder line to hold and a much easier one
# to check: a stake size is a number and could always be argued about, but a
# credential is a string, an order is an HTTP verb, and a ledger is a table.
#
# `BETTING_IDENTIFIERS` and `check_not_a_betting_tool` are RETIRED, not
# deleted -- see the note beside them. What replaces them is three scans, each
# with its own planting:
#
#   * NO CREDENTIALS, in the package, the environment or the record.
#   * NO ORDER PATH: no write verb aimed at a venue, no account read.
#   * NO LEDGER: the operator's own wagering record lives outside this repo.
#
# None of the three is amendable by a later session. A brief asking for one is
# refused and pointed at LAW 5, which is exactly what the old law's own refusal
# clause did for staking -- the mechanism is unchanged, only its subject.

#: WHAT MAKES A CREDENTIAL A *VENUE* CREDENTIAL. Two lists, and a fault needs
#: one word from each in the same name -- except inside the market module,
#: which is the only code that talks to a venue at all, where a credential word
#: is a fault on its own.
#:
#: THE FIRST RUN OF THIS SCAN PROVED THE POINT. A single list flagged the app's
#: own sign-in cookie and the Anthropic key the reasoning pass runs on: three
#: findings, none of them a violation, on a scan meant to catch something that
#: would be unmistakable. A guard that cries wolf gets an allowlist, and an
#: allowlist is the mute button this file's own docstring warns about.
VENUE_WORDS = (
    "kalshi", "polymarket", "draftkings", "fanduel", "betfair", "pinnacle",
    "bookmaker", "sportsbook", "prizepicks", "exchange", "venue", "book",
)
CREDENTIAL_WORDS = (
    "api_key", "apikey", "secret", "token", "password", "cookie", "session",
    "credential", "bearer", "private_key", "signing_key", "access_key",
    "auth_header",
    # THE SPELLINGS A CLIENT LIBRARY USES (NIGHT_AUDIT item 4, 2026-09-08).
    # Grepped against the tree before adding: zero matches each.
    "client_secret", "refresh_token", "auth_token", "passwd",
)
#: Names that are a venue credential whatever module they sit in.
VENUE_CREDENTIAL_IDENTIFIERS = tuple(
    f"{venue}_{word}" for venue in VENUE_WORDS for word in
    ("key", "api_key", "secret", "token", "password", "cookie", "session")
)

#: PLACING, CANCELLING, OR LOOKING AT MONEY. The gap between a recommendation
#: and a wager is a human being, and these are the names that would close it.
ORDER_PATH_IDENTIFIERS = (
    "place_order", "submit_order", "send_order", "create_order", "cancel_order",
    "modify_order", "amend_order", "order_ticket", "order_payload", "place_bet",
    "submit_bet", "place_wager", "buy_contract", "sell_contract",
    "account_balance", "available_balance", "account_positions",
    "open_positions", "portfolio_value", "withdraw_funds", "deposit_funds",
    "transfer_funds", "fund_account",
    # NOT a bare "withdraw": this project already withdrew a feature and calls
    # it that -- WITHDRAWN, WithdrawalRefused, _withdraw -- so the bare word
    # would report three findings that are nothing to do with money. Caught on
    # the first run of this scan.
)

#: THE OPERATOR'S OWN RESULTS. Not the model's record -- that is the whole
#: point of the project -- but what he actually staked and what it returned.
WAGERING_LEDGER_IDENTIFIERS = (
    "my_bets", "my_wagers", "bet_log", "wager_log", "bet_ledger",
    "wager_ledger", "betting_ledger", "bets_placed", "wagers_placed",
    "realised_pnl", "realized_pnl", "profit_and_loss", "account_history",
)

#: Tables that would hold that ledger, checked against the schema itself.
WAGERING_LEDGER_TABLES = (
    "bets", "wagers", "my_bets", "bet_ledger", "wager_ledger", "pnl",
    "account_history", "positions",
)

#: Environment names that would hold a venue credential. The VALUE is never
#: read, printed or logged by any of this -- the name is the whole finding.
VENUE_ENV_PREFIXES = ("KALSHI", "POLYMARKET", "DRAFTKINGS", "FANDUEL",
                      "BETFAIR", "PINNACLE", "PRIZEPICKS", "BOOKMAKER",
                      "EXCHANGE")
VENUE_ENV_SUFFIXES = ("KEY", "SECRET", "TOKEN", "PASSWORD", "COOKIE",
                      "SESSION", "CREDENTIAL", "AUTH")


def venue_credential_faults(root: Path | None = None, env_file: Path | None = None,
                            conn=None) -> list[str]:
    """A venue credential in the code, the environment, or the record.

    THREE PLACES, BECAUSE THERE ARE THREE WAYS IN. A key can be typed into a
    module, exported into `.env`, or written to a settings table by a future
    convenience. The value is never read here; the name is the finding, and
    printing a secret to prove it exists would be its own violation.
    """
    root = root or config.PACKAGE_ROOT
    faults: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in BETTING_SCAN_EXEMPT:
            continue
        in_market = MARKET_MODULE in path.parts
        for name in sorted(identifiers_in(path)):
            lowered = name.lower()
            credential = any(word in lowered for word in CREDENTIAL_WORDS)
            if not credential:
                continue
            # Inside the market module a credential word is enough: that
            # package exists to read venues and nothing else.
            if in_market or any(v in lowered for v in VENUE_WORDS):
                faults.append(
                    f"{path.relative_to(root)}:{name} is a venue credential by "
                    f"name. LAW 5: no key, token, password, cookie or session "
                    f"for any venue lives in this codebase, its environment or "
                    f"its database.")
    env_file = env_file or config.ENV_FILE if hasattr(config, "ENV_FILE") else env_file
    if env_file is not None and Path(env_file).exists():
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            name = line.split("=", 1)[0].strip().upper()
            if not name or name.startswith("#"):
                continue
            if (any(p in name for p in VENUE_ENV_PREFIXES)
                    and any(s in name for s in VENUE_ENV_SUFFIXES)):
                # THE NAME, NEVER THE VALUE. Printing the secret to prove the
                # secret exists would be its own violation.
                faults.append(
                    f"the environment defines {name}, which names a venue "
                    f"credential. LAW 5: the app authenticates to nothing.")
    if conn is not None:
        for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'table'"):
            sql = (row["sql"] or "").lower()
            for word in VENUE_CREDENTIAL_IDENTIFIERS:
                if word in sql:  # e.g. a column called kalshi_token
                    faults.append(
                        f"the record's table {row['name']} has a column named "
                        f"for a venue credential ({word}). LAW 5: not in the "
                        f"code, not in the environment, not in the database.")
    return sorted(set(faults))


def check_no_venue_credentials(root: Path | None = None, env_file=None,
                               conn=None) -> None:
    faults = venue_credential_faults(root, env_file, conn)
    if faults:
        raise LawViolation(
            "LAW 5: A VENUE CREDENTIAL EXISTS IN THIS PROJECT."
            + _NL2 + _NL2.join(faults[:8]))


#: HTTP verbs that change something at the other end. The project's own fetch
#: helper is a GET, and every venue read goes through it.
WRITE_VERBS = ('"POST"', "'POST'", '"PUT"', "'PUT'", '"DELETE"', "'DELETE'",
               '"PATCH"', "'PATCH'", "requests.post", "requests.put",
               "requests.delete", "requests.patch", "session.post")


def _python_without_comments(text: str) -> str:
    """Python source with its comments blanked, by the tokeniser.

    THE SAME RULE THE OTHER SCANNERS FOLLOW: a comment may neither trip a scan
    nor satisfy one, so a module explaining in prose that it must never POST
    does not thereby appear to POST. `_without_comments` knows JavaScript, CSS
    and HTML; Python needs the tokeniser, because a `#` inside a string is not
    a comment.
    """
    import io
    import tokenize

    try:
        out = []
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            out.append("" if tok.type == tokenize.COMMENT else tok.string)
        return " ".join(out)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # An unparseable file is not a silent pass: scan it raw rather than
        # skipping it, and accept the false positive a comment might cause.
        return text


def order_path_faults(root: Path | None = None) -> list[str]:
    """Anything that could place, cancel or price an order at a venue, or read
    an account.

    The identifier scan is the blunt half. The other half reads the market
    module -- the only place a venue is named at all -- for a write verb: a
    module that may fetch a price has no business sending one.
    """
    root = root or config.PACKAGE_ROOT
    faults: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in BETTING_SCAN_EXEMPT:
            continue
        for name in sorted(identifiers_in(path)):
            lowered = name.lower()
            for word in ORDER_PATH_IDENTIFIERS:
                if word in lowered:
                    faults.append(
                        f"{path.relative_to(root)}:{name} is an order path by "
                        f"name. LAW 5: nothing here places, cancels, modifies "
                        f"or prepares an order, and nothing reads an account.")
        if MARKET_MODULE in path.parts:
            source = _python_without_comments(path.read_text(encoding="utf-8"))
            for verb in WRITE_VERBS:
                if verb in source:
                    faults.append(
                        f"{path.relative_to(root)} sends {verb.strip(chr(34))} "
                        f"from the market module. LAW 5: every venue request is "
                        f"unauthenticated and READ-ONLY.")
            # A `urllib` POST HAS NO VERB IN IT (NIGHT_AUDIT item 4, 2026-09-08).
            # `Request(url, data=body)` posts because `data` is present; the
            # verb list above never sees it. Read off the syntax tree, where a
            # keyword argument cannot hide in a string.
            for name, keyword in _request_write_keywords(path):
                faults.append(
                    f"{path.relative_to(root)} builds {name}(..., {keyword}=...) "
                    f"in the market module, which is a write however it is "
                    f"spelled. LAW 5: every venue request is unauthenticated "
                    f"and READ-ONLY.")
    return sorted(set(faults))


def _request_write_keywords(path: Path) -> list[tuple[str, str]]:
    """Every `Request(...)` call in a file that carries `data=` or `method=`."""
    import ast as _ast

    tree = _ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[str, str]] = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, _ast.Attribute) else getattr(func, "id", "")
        if not name or not name.endswith("Request"):
            continue
        for kw in node.keywords:
            if kw.arg in ("data", "method"):
                hits.append((name, kw.arg))
    return hits


def check_no_order_path(root: Path | None = None) -> None:
    faults = order_path_faults(root)
    if faults:
        raise LawViolation(
            "LAW 5: AN ORDER PATH EXISTS. The gap between a recommendation and "
            "a wager is a human being, on purpose." + _NL2 + _NL2.join(faults[:8]))


def wagering_ledger_faults(root: Path | None = None, conn=None) -> list[str]:
    """The operator's own stakes and returns, inside the repo.

    NOT THE MODEL'S RECORD, which is the entire project: this is the other
    ledger, the one with real money in it. A model that can see its own profit
    and loss is one step from fitting to it, and the step leaves no trace in
    the code afterwards.
    """
    root = root or config.PACKAGE_ROOT
    faults: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in BETTING_SCAN_EXEMPT:
            continue
        for name in sorted(identifiers_in(path)):
            lowered = name.lower()
            for word in WAGERING_LEDGER_IDENTIFIERS:
                if word in lowered:
                    faults.append(
                        f"{path.relative_to(root)}:{name} names the operator's "
                        f"own wagering record. LAW 5: that ledger lives outside "
                        f"this codebase.")
    if conn is not None:
        for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"):
            if row["name"].lower() in WAGERING_LEDGER_TABLES:
                faults.append(
                    f"the record holds a table called {row['name']}, which is "
                    f"the operator's own wagering ledger by name. LAW 5: it "
                    f"lives outside this codebase.")
    return sorted(set(faults))


def check_no_wagering_ledger(root: Path | None = None, conn=None) -> None:
    faults = wagering_ledger_faults(root, conn)
    if faults:
        raise LawViolation(
            "LAW 5: THE OPERATOR'S OWN WAGERING LEDGER IS IN THE REPOSITORY."
            + _NL2 + _NL2.join(faults[:8]))


# ---------------------------------------------------------------------------
# WHICH PICKS WERE TAKEN, AND WHAT THAT RECORD MAY NEVER BECOME
# (GRIDIRON_TODAY T2, 2026-09-07)
# ---------------------------------------------------------------------------
#
# `picks_taken` holds a prediction id and a time. Two scans stand over it, and
# they guard two different failures:
#
#   * IT MUST NOT GROW A LEDGER. A stake, a price paid, a payout or a result in
#     money would make it the thing LAW 5 keeps outside this repository, and it
#     would arrive one convenient column at a time.
#   * IT MUST NOT REACH THE MODEL. The operator takes a fraction of the list
#     and takes it for his own reasons; a model fitted to those picks would be
#     learning his habits rather than the sport, and the damage would be
#     invisible afterwards because the fit would look ordinary.

TAKEN_TABLE = "picks_taken"

#: Column names that would turn a record of choices into a record of money.
LEDGER_SHAPED_COLUMNS = (
    "stake", "price", "paid", "payout", "payoff", "profit", "loss", "amount",
    "units", "size", "returned", "return", "odds", "cost", "won", "balance",
    "pnl", "money", "usd", "dollars", "wager", "risk",
    # NIGHT_AUDIT item 4, 2026-09-08: two more shapes a ledger column takes.
    "winnings", "net_profit",
)

#: The modules that teach the model anything. None of them may name the table.
TRAINING_MODULES = (
    "model/baseline.py", "model/logistic.py", "model/predict.py",
    "model/questions.py", "correction.py", "drift.py", "shortlist.py",
    "factors/compute.py", "factors/registry.py", "factors/context.py",
    "factors/store.py",
)


def taken_ledger_faults(conn) -> list[str]:
    """A money-shaped column on the record of which picks were taken."""
    faults: list[str] = []
    for row in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            "   AND name = ?", (TAKEN_TABLE,)):
        for column in conn.execute(f"PRAGMA table_info({TAKEN_TABLE})"):
            lowered = column["name"].lower()
            for word in LEDGER_SHAPED_COLUMNS:
                if word in lowered:
                    faults.append(
                        f"{TAKEN_TABLE}.{column['name']} is money-shaped. LAW 5: "
                        f"this table records WHICH pick and WHEN. A stake, a "
                        f"price, a payout or a result in money makes it the "
                        f"operator's wagering ledger, which lives outside this "
                        f"repository.")
    return sorted(set(faults))


def check_taken_is_not_a_ledger(conn) -> None:
    faults = taken_ledger_faults(conn)
    if faults:
        raise LawViolation(
            "LAW 5: THE RECORD OF TAKEN PICKS HAS GROWN A LEDGER:"
            + _NL2 + _NL2.join(faults[:8]))


def taken_in_training_faults(root: Path | None = None) -> list[str]:
    """The taken table named by anything that teaches the model.

    Reads the SQL as text rather than trusting the call graph: a training query
    that mentions the table is a fault whether or not today's code path reaches
    it, because the next edit will.
    """
    root = root or config.PACKAGE_ROOT
    faults: list[str] = []
    for relative in TRAINING_MODULES:
        path = root / relative
        if not path.exists():
            continue
        source = _python_without_comments(path.read_text(encoding="utf-8"))
        if TAKEN_TABLE in source:
            faults.append(
                f"{relative} names {TAKEN_TABLE}. The picks the operator took "
                f"are a biased sample of the model's own work: a model fitted "
                f"to them learns his habits rather than the sport, and the "
                f"damage is invisible afterwards because the fit looks "
                f"ordinary.")
    return faults


def check_taken_not_in_training(root: Path | None = None) -> None:
    faults = taken_in_training_faults(root)
    if faults:
        raise LawViolation(
            "THE MODEL CAN SEE WHICH PICKS WERE TAKEN:"
            + _NL2 + _NL2.join(faults[:8]))


# ---------------------------------------------------------------------------
# THE GRAMMAR, NOT THE PRESSURE (GRIDIRON_CARD_FACE, 2026-09-07)
# ---------------------------------------------------------------------------
#
# The operator asked for a page that reads like a sportsbook, because he can
# already read one. A sportsbook page is two things wearing one skin:
#
#   THE GRAMMAR -- an event header, the market under it, prices side by side,
#   a running list of what you took. That is good information design for this
#   content, and it is what was taken.
#
#   THE PRESSURE -- a countdown, a price that flashes when it moves, a "hot"
#   badge, a streak counter, a parlay builder. That exists to make wagering
#   feel urgent, and it is what makes a book money.
#
# The difference between the two is invisible in a diff and obvious on a
# screen, which is exactly the kind of thing that needs a scan rather than an
# intention.

#: Words with no job on this page except to make a reader move faster. Matched
#: on word boundaries written as character classes, because a substring match
#: on "hot" flags "shot" and a scan that cries wolf gets switched off.
#: "combo" LEFT THIS LIST ON 2026-09-08, when LAW 5 was amended to let the
#: engine price a package the venue publishes. It is the product's name and
#: the group's name, and a scan that banned it would force the page to call
#: the thing something a reader would not recognise.
#:
#: EVERYTHING ELSE STAYS BANNED, including "parlay" and "same game": the first
#: is the sportsbook's word for the product and carries its urgency, and the
#: second names a package this app refuses to price -- printing it as a label
#: would advertise the one shape that has no fair value here.
PRESSURE_WORDS: tuple[str, ...] = (
    "boost", "boosted", "hot", "trending", "popular", "streak", "streaks",
    "parlay", "parlays", "same game", "sgp", "builder", "add leg", "slip",
)

_PRESSURE = re.compile(
    "(?:^|[^A-Za-z])(" + "|".join(w.replace(" ", r"\s+") for w in PRESSURE_WORDS)
    + ")(?:[^A-Za-z]|$)", re.IGNORECASE)


def pressure_word_faults(text: str) -> list[str]:
    """A sportsbook's urgency vocabulary in text this project composes.

    NOT a judgement about the words in English. "Hot" is a fine word about
    weather and a terrible one on a pick card, where its only function is to
    suggest that a reader who waits will miss something.
    """
    if not text:
        return []
    return sorted({
        f"the word {m.group(1).lower()!r} belongs to a sportsbook's pressure, "
        f"not to a forecast: it tells a reader to hurry rather than telling "
        f"them anything"
        for m in _PRESSURE.finditer(str(text))
    })


#: The selectors that carry a price. A transition or an animation on one of
#: these is a number that MOVES when it changes, which is the single most
#: effective piece of pressure a book has.
#: EXTENDED FOR THE BOARD (motion, 2026-09-25): every class a price, a
#: probability, a payout or a score is drawn in. A transition on any of them
#: would make a number move on its way to a new value.
PRICE_SELECTORS = (".box", ".box-value", ".edge", ".face-prices",
                   ".pick-price", ".pick-pays", ".pick-prob", ".q-price", ".q-prob",
                   ".pay", ".prop-prob", ".cush", ".entry-value", ".tscore", ".game-score",
                   ".my-chip-state", ".v-mult")
#: THE BAR FILL may arrive once, on first load, and never on an update: the
#: stylesheet may transition `.pbar-fill` on `opacity` alone, and the JS
#: that patches a live score may not reach the bar or the class that starts
#: the fill. Both are scanned; both are planted.
#: BY ITS FADE, NOT A TRANSFORM (the board merge, 2026-09-29). The board
#: grew the fill from nothing by `scaleX`, at the panel duration, inside a
#: row or a tile that holds tap targets; operator question 20 and the merge
#: checklist's step 2 ("arrival motion on any panel holding tap targets is
#: opacity only") leave an arrival its fade and nothing else, and
#: `audit.arrival_movement_faults` refuses a movement at that duration. So
#: the fill fades in, once, in place -- the same "once, on load, never on an
#: update" the board ruled, in the one property an arrival may use.
BAR_FILL_CLASS = ".pbar-fill"


def bar_fill_faults(css: str | None = None) -> list[str]:
    """A bar fill that would move on anything but its one first-load fade."""
    if css is None:
        path = Path(__file__).resolve().parent / "web" / "style.css"
        css = path.read_text(encoding="utf-8") if path.exists() else ""
    css = _without_comments(css, "css")
    faults = []
    for match in _CSS_RULE.finditer(css):
        selector = " ".join(match.group("selector").split()).split("*/")[-1].strip()
        if BAR_FILL_CLASS not in selector:
            continue
        for animated in _CSS_ANIMATED.finditer(match.group("body")):
            value = animated.group(0)
            if "none" in value.split(":", 1)[-1].split(";")[0]:
                continue   # the start state snaps into place; nothing moves
            named = _transition_properties(
                animated.group(1), value.split(":", 1)[-1]) \
                if animated.group(1) == "transition" else ["animation"]
            if animated.group(1) == "animation" or any(p != "opacity" for p in named):
                faults.append(
                    f"{selector!r} sets {value.strip()[:50]!r}: the bar fills once on "
                    f"first load, by its fade and nothing else, and never on an "
                    f"update (motion, 2026-09-25; by its fade alone from the "
                    f"board merge, 2026-09-29).")
    return faults


def check_the_bar_fills_once(css: str | None = None) -> None:
    faults = bar_fill_faults(css)
    if faults:
        raise LawViolation("THE BAR FILLS ONCE, ON LOAD:" + _NL2 + _NL2.join(faults))


_CSS_ANIMATED = re.compile(r"(?:^|[;\s])(transition|animation)\b[^;]*")


def price_chip_animation_faults(css: str | None = None) -> list[str]:
    """Every rule that would make a price move on its way to a new value."""
    if css is None:
        path = Path(__file__).resolve().parent / "web" / "style.css"
        css = path.read_text(encoding="utf-8") if path.exists() else ""
    css = _without_comments(css, "css")
    faults = []
    for match in _CSS_RULE.finditer(css):
        selector = " ".join(match.group("selector").split()).split("*/")[-1].strip()
        if not selector or selector.startswith("@"):
            continue
        if not any(part in selector for part in PRICE_SELECTORS):
            continue
        for animated in _CSS_ANIMATED.finditer(match.group("body")):
            faults.append(
                f"{selector!r} sets {animated.group(1)}, so a price would move "
                f"on its way to a new value. A number that flashes when it "
                f"changes is a sportsbook's pressure and this page refuses it: "
                f"{animated.group(0).strip()[:60]}")
    return faults


def check_no_price_animation(css: str | None = None) -> None:
    faults = price_chip_animation_faults(css)
    if faults:
        raise LawViolation(
            "A PRICE MAY NOT MOVE WHEN IT CHANGES. The whole point of an "
            "animated odds chip is that the eye is caught by the movement "
            "rather than by the number, and a reader who is watching prices "
            "flicker is not reading them:" + _NL2 + _NL2.join(faults[:6]))


_JS_COUNTDOWN = re.compile(
    r"setInterval|setTimeout")
_JS_TIME_LEFT = re.compile(
    r"(?:new\s+Date\s*\(\s*\)|Date\.now\s*\(\s*\))")


def countdown_faults(path=None) -> list[str]:
    """A ticking time-to-kickoff anywhere in the renderer.

    KICKOFF IS A TIME, NOT A TIMER. The page ticked "first kickoff in 2d 6h"
    once a minute until this brief; the instant is still rendered in the
    reader's own clock, which is a fact about when the game is rather than a
    deadline counting down at them.

    Shape-based on purpose: a repeating timer, a subtraction against the
    current instant, and a write into the page, in one function. Renaming the
    variables does not get past it.
    """
    path = ((Path(__file__).resolve().parent / "web" / "app.js")
            if path is None else Path(path))
    if not path.exists():
        return []
    source = path.read_text(encoding="utf-8")
    faults = []
    for block in re.split(r"(?m)^  function ", source)[1:]:
        name = block.split("(", 1)[0].strip()
        body = chr(10).join(line for line in block.split(chr(10))
                        if not line.strip().startswith("//"))
        if not _JS_COUNTDOWN.search(body):
            continue
        if not _JS_TIME_LEFT.search(body):
            continue
        if "textContent" not in body and "innerText" not in body:
            continue
        faults.append(
            f"{name!r} repeats a timer, subtracts against the current instant "
            f"and writes the result into the page. That is a countdown, and a "
            f"countdown makes a start time read as a deadline")
    return faults


def check_no_countdown(path=None) -> None:
    faults = countdown_faults(path)
    if faults:
        raise LawViolation(
            "NO COUNTDOWN TO KICKOFF. A start time is a fact about when a game "
            "is; a countdown is a sportsbook telling a reader they are running "
            "out of time to act, and the two look identical in a payload:"
            + _NL2 + _NL2.join(faults[:6]))


_JS_DEF = re.compile(r"(?m)^(\s*)function\s+([A-Za-z_$][\w$]*)\s*\(")


def duplicate_js_definitions(path=None) -> list[str]:
    """A function name defined twice at the same indentation in the renderer.

    THE SECOND ONE WINS AND THE FIRST IS DEAD, silently. This file held two:
    `renderToday`, byte-identical, one directly after the other; and
    `localTime`, 571 lines apart and NOT identical -- one returned an empty
    string for a date that would not parse and the other returned the raw
    instant, which would have printed a machine timestamp on a card.

    A fix applied to the dead copy changes nothing on the screen, which is the
    worst kind of bug to chase. `check_no_shadowed_definitions` has caught this
    in Python since the day a name collision reached the record; the renderer
    had no equivalent until 2026-09-07.
    """
    path = ((Path(__file__).resolve().parent / "web" / "app.js")
            if path is None else Path(path))
    if not path.exists():
        return []
    return duplicate_js_definitions_in(path.read_text(encoding="utf-8"))


def duplicate_js_definitions_in(source: str) -> list[str]:
    """The same scan over text, which is the form the comment-blindness test
    drives it in and the form the file scan delegates to."""
    seen: dict[tuple[str, int], int] = {}
    faults = []
    for n, line in enumerate(source.split(chr(10)), 1):
        if line.strip().startswith("//"):
            continue
        match = _JS_DEF.match(line)
        if not match:
            continue
        key = (match.group(2), len(match.group(1)))
        if key in seen:
            faults.append(
                f"{match.group(2)!r} is defined twice in the renderer, at "
                f"lines {seen[key]} and {n}. The second replaces the first at "
                f"load, so the first is dead code that still looks live -- and "
                f"a fix applied to it changes nothing on the screen")
        else:
            seen[key] = n
    return faults


#: Where a card's own words live in the slate payload. Walked rather than
#: named one by one, because a card that grows a new line of prose should be
#: scanned the day it grows it, not the day somebody remembers to add it here.
DAY_TEXT_KEYS = (
    "where_words", "count_words", "no_price_words", "clears_heading",
    "watching_heading", "below_floor_words", "fee_line", "taken_line",
    "question", "matchup", "sport_label", "kickoff_label", "model_words",
    "venue_words", "edge_words", "edge_label", "size_words", "gate_words",
    "tier_chip", "words", "heading",
    # A PACKAGE CARD'S OWN WORDS (GRIDIRON_COMBOS C5, 2026-09-08). The legs
    # arrive as the VENUE wrote them, which is the one place on this page
    # where the text is somebody else's, so it is the place the scan most
    # needs to read.
    "legs_words", "margin_words", "singles_words", "payout_words",
    "price_words", "empty_words", "fee_words",
)

#: A STALE JOB MUST BE ON THE STRIP (NIGHT_AUDIT item 1, 2026-09-08). The
#: payload that draws Picks has to carry every freshness entry, and an entry
#: past its threshold has to say so in its own words -- a mark with no words
#: is a style, and a job that is stale on the ledger and fresh on the page is
#: the dead key again.
FRESHNESS_JOBS = ("daily_run", "venue_read", "reasoning")


def freshness_faults(payload) -> list[str]:
    """The strip hides a dead job, or calls a stale one fresh."""
    block = (payload or {}).get("freshness")
    if not isinstance(block, dict):
        return ["the Picks payload carries no freshness block, so a dead job "
                "cannot reach the first screen"]
    faults = []
    seen = {e.get("job") for e in block.get("entries") or []}
    for job in FRESHNESS_JOBS:
        if job not in seen:
            faults.append(f"freshness: the {job} line is missing from the strip")
    for entry in block.get("entries") or []:
        age, limit = entry.get("age_hours"), entry.get("limit_hours")
        past = age is None or (limit is not None and age > limit)
        if past and not entry.get("stale"):
            faults.append(f"freshness: {entry.get('job')} is {age}h old against "
                          f"a {limit}h threshold and is not marked stale")
        words = entry.get("words") or ""
        # "not forecast" from 2026-09-26 (GRIDIRON_REPAIR item 2): a market
        # with no model says what that costs in those words.
        if entry.get("stale") and not any(
                w in words for w in ("past", "never", "held", "not forecast")):
            faults.append(f"freshness: {entry.get('job')} is stale and its words "
                          f"do not say so")
    # A HELD MARKET IS ON THE STRIP, BY NAME (ruling 2026-09-24).
    from . import language as _language

    shown = [e for e in block.get("entries") or []
             if e.get("job") == "held" and e.get("stale")]
    for hold in block.get("held") or []:
        name = _language.market_words(hold.get("sport", ""), hold.get("market", ""))
        if not any(e.get("sport") == hold.get("sport")
                   and name in (e.get("words") or "") for e in shown):
            faults.append(f"freshness: {hold.get('sport')} {name} is held and "
                          f"the strip does not say so")
    # SO IS A MARKET THE RUN ASKS AND CANNOT ANSWER (GRIDIRON_REPAIR item 2;
    # the operator's ruling of 2026-09-23, built 2026-09-26: "the day strip
    # shows it"), by its name and in a stale line of its own sport.
    shown = [e for e in block.get("entries") or []
             if e.get("job") == "untrained" and e.get("stale")]
    for gap in block.get("untrained") or []:
        name = _language.market_words(gap.get("sport", ""), gap.get("market", ""))
        if not any(e.get("sport") == gap.get("sport")
                   and name in (e.get("words") or "") for e in shown):
            faults.append(f"freshness: {gap.get('sport')} {name} is not "
                          f"forecast, for want of a model, and the strip does "
                          f"not say so")
    return faults


def check_the_strip_shows_a_dead_job(payload) -> None:
    faults = freshness_faults(payload)
    if faults:
        raise LawViolation(
            "A JOB THAT FAILS MUST BE VISIBLE ON THE FIRST SCREEN:"
            + _NL2 + _NL2.join(faults[:6]))


def day_pressure_faults(payload) -> list[str]:
    """A sportsbook's urgency vocabulary anywhere in the day's own words."""
    if not payload:
        return []
    faults: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")
        elif isinstance(node, str) and path.rsplit(".", 1)[-1].split("[")[0] in DAY_TEXT_KEYS:
            for fault in pressure_word_faults(node):
                faults.append(f"{path}: {fault}")

    walk(payload, "")
    return faults


def check_the_day_applies_no_pressure(payload) -> None:
    """Raise if Today reads like a sportsbook rather than like a forecast."""
    faults = day_pressure_faults(payload)
    if faults:
        raise LawViolation(
            "THE GRAMMAR OF A SPORTSBOOK, NEVER ITS PRESSURE. A page that "
            "tells a reader to hurry has stopped telling them anything:"
            + _NL2 + _NL2.join(faults[:6]))


def check_no_duplicate_js_definitions(path=None) -> None:
    faults = duplicate_js_definitions(path)
    if faults:
        raise LawViolation(
            "A FUNCTION DEFINED TWICE IN THE RENDERER. One of them is dead and "
            "neither says so:" + _NL2 + _NL2.join(faults[:6]))


# ---------------------------------------------------------------------------
# THREE STATES (GRIDIRON_THREE_STATES, 2026-09-08)
# ---------------------------------------------------------------------------

#: File types that would be a club's mark. The colour generator reads a
#: payload that also carries `logos`; none of it is stored, and this is what
#: says so in a way a later session cannot talk itself past.
MARK_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
                 ".svg", ".avif", ".tif", ".tiff")


def mark_faults(directory=None) -> list[str]:
    """An image file in the team data directory, which would be a club's mark.

    COLOUR IS ENOUGH TO MAKE A CUBS CARD LOOK LIKE A CUBS CARD. A crest is the
    club's trademark and this project has no licence to it, so the rule is
    structural rather than a note in a docstring: nothing that could BE one is
    stored where the team data lives.
    """
    directory = (Path(__file__).resolve().parent / "data"
                 if directory is None else Path(directory))
    if not directory.exists():
        return []
    faults = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in MARK_SUFFIXES:
            faults.append(
                f"{path.name} sits in the team data directory. A club's logo, "
                f"wordmark or crest is its trademark; this project stores "
                f"colour and nothing else, and colour is enough to make a Cubs "
                f"card look like a Cubs card")
    return faults


def check_no_marks(directory=None) -> None:
    faults = mark_faults(directory)
    if faults:
        raise LawViolation(
            "NO CLUB MARKS. Colour is declared, measured and stored; a crest "
            "is a trademark and is not:" + _NL2 + _NL2.join(faults[:6]))


#: What a card whose game is being played may not carry. Each one is a thing a
#: reader could act on, and the in-game rule says none of them may be acted on:
#: a score up to ninety seconds stale against a live market is adversely
#: selected by construction (THE_PRICED P2).
#:
#: NARROWED 2026-09-09 BY OPERATOR RULING, and the law did not move. LAW 5 has
#: always said "Live win probability may be displayed and is never sized";
#: this list carried `model_words` from 2026-09-08 until today, which forbade
#: the probability itself and left a live card saying nothing at all about the
#: game the operator was watching. That guard was written after the old Picks
#: grid leaked fifteen cards under Live's empty state, and it overshot the
#: ruling that produced it: what was being prevented was a recommendation
#: surface, not a number.
#:
#: `model_words` is therefore GONE from this list and `pregame_words` takes
#: its place on the card -- the corrected probability the claim was written
#: with, carrying the word "pregame". Everything else here stands.
LIVE_FORBIDDEN = ("size_words", "edge_words", "edge_line_words", "edge_label",
                  "payout_words", "price_words", "model_words", "venue_words",
                  "tier_chip", "price", "payout")

#: The word a live card's probability must carry. WITHOUT IT the figure reads
#: as the model's opinion of the game in front of the reader, and there is no
#: such opinion: no live model exists, S5 is unbuilt, and the number is what
#: was thought before the first pitch.
PREGAME_WORD = "pregame"


def live_card_faults(payload) -> list[str]:
    """A live card carrying something a reader could act on.

    THE SCREEN IS THE LAST PLACE THIS RULE COULD BE BROKEN. The sizing path
    already refuses a game in progress and the claim writer refuses a quote
    taken after first pitch; a card that rendered the pregame edge beside a
    live score would put the same adversely-selected number in front of the
    operator with none of them firing.
    """
    if not payload:
        return []
    faults = []

    def walk(node, path):
        if isinstance(node, dict):
            if node.get("state") == "live":
                for field in LIVE_FORBIDDEN:
                    if node.get(field) is not None:
                        faults.append(
                            f"{path or 'a card'} is live and carries "
                            f"{field!r}: a game being played is priced off a "
                            f"feed this app reads up to ninety seconds late, "
                            f"so nothing on it may be acted on")
                if node.get("taken_control") or node.get("can_take"):
                    faults.append(
                        f"{path or 'a card'} is live and offers the tap that "
                        f"records a pick")
                # THE PROBABILITY IS ALLOWED AND THE WORD IS NOT OPTIONAL
                # (operator ruling, 2026-09-09). A figure beside a live score
                # with nothing to date it reads as the model's opinion of the
                # game being played, and there is no such opinion.
                pregame = node.get("pregame_words")
                if pregame is not None and PREGAME_WORD not in str(pregame).lower():
                    faults.append(
                        f"{path or 'a card'} is live and shows {pregame!r} "
                        f"without the word {PREGAME_WORD!r}: no live model "
                        f"exists, so an undated figure beside a live score "
                        f"claims to be something this app does not have")
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(payload, "")
    return faults


def check_the_live_card_offers_nothing(payload) -> None:
    faults = live_card_faults(payload)
    if faults:
        raise LawViolation(
            "NOTHING ON A LIVE CARD CAN BE ACTED ON. The score is up to ninety "
            "seconds stale and the market it would be priced against is not:"
            + _NL2 + _NL2.join(faults[:6]))


# ---------------------------------------------------------------------------
# PACKAGES ARE GRADED, NEVER BUILT (GRIDIRON_COMBOS, 2026-09-08)
# ---------------------------------------------------------------------------
#
# LAW 5 as amended lets the engine price a package the VENUE published. What
# it may never do is put a number on one whose legs it cannot honestly
# multiply: two legs from one game price a correlation nobody declared (LAW
# 2), two sports in one row merge two records (LAW 6), a fourth leg is past
# the declared shape, and a leg this record does not forecast has no
# probability to contribute.


def combo_package_faults(packages) -> list[str]:
    """A package carrying a price it is not entitled to."""
    from .market import combos

    if not packages:
        return []
    faults = []
    for package in packages:
        if not package.get("priceable"):
            continue
        legs = package.get("legs") or []
        games = package.get("games") or []
        where = package.get("ticker") or "a package"
        if package.get("sport") not in combos.FORECAST_SPORTS:
            faults.append(
                f"{where} is priced in {package.get('sport')!r}, a sport this "
                f"record does not forecast, so there is no probability to "
                f"multiply")
        if not combos.MIN_LEGS <= len(legs) <= combos.MAX_LEGS:
            faults.append(
                f"{where} is priced with {len(legs)} legs; the declared shape "
                f"is two or three")
        if games and len(set(games)) != len(games):
            faults.append(
                f"{where} is priced with two legs in one game. Multiplying "
                f"them prices a correlation nobody declared, and this record "
                f"holds no joint model (LAW 2)")
        sports = {s for s in package.get("leg_sports") or [] if s}
        if len(sports) > 1:
            faults.append(
                f"{where} is priced across {sorted(sports)}, and a number that "
                f"mixes two sports describes neither (LAW 6)")
        if package.get("unforecast_leg"):
            faults.append(
                f"{where} is priced with a leg this record does not forecast, "
                f"so one of the factors in its product does not exist")
    return faults


def check_combo_package(packages) -> None:
    faults = combo_package_faults(packages)
    if faults:
        raise LawViolation(
            "A PACKAGE IS GRADED, NEVER BUILT, and never priced on legs this "
            "record cannot honestly multiply:" + _NL2 + _NL2.join(faults[:6]))


# ---------------------------------------------------------------------------
# THE LIVE TAB SHOWS THE GAME AND NOTHING ELSE (2026-09-08)
# ---------------------------------------------------------------------------
#
# `live_card_faults` above rules the CARD. This rules the TAB, and it exists
# because the night audit of the same day passed Live "via the DOM": it read
# the ids it expected, found them right, and could not see that the old Picks
# grid was rendering fifteen cards underneath -- raw probability largest, a
# tier chip on every one, in the design CARD_FACE replaced.
#
# A DOM CHECK SEES WHAT IT ASKS FOR. A screenshot sees what is there.

#: What a card on Live may not carry, beyond the actionable fields
#: `LIVE_FORBIDDEN` already refuses: the model's own probability and the tier
#: chip. Both belong to the pre-CARD_FACE card, and both read as a claim about
#: a game whose score this app is up to ninety seconds late on.
LIVE_TAB_FORBIDDEN_FIELDS = ("probability", "model_prob", "chance",
                             "tier_chip", "tier_label", "tier")

#: The only headings the Live tab may carry. "In progress" is the group's own;
#: "Yours" marks a pick the operator took. Any other heading on this tab is a
#: group that belongs to Upcoming and has followed the reader across.
LIVE_TAB_HEADINGS = ("In progress", "Yours", "Nothing is being played")


def live_tab_faults(payload) -> list[str]:
    """Anything on the Live tab that is not the game.

    Reads the day's payload: the live group's cards and the headings that
    would render beside them -- and, from the board merge (2026-09-29), the
    board's live rows and tiles, where a game being played is shown now.
    """
    today = ((payload or {}).get("today") or {})
    if not today:
        return _board_live_row_faults(payload)
    faults: list[str] = []
    for i, card in enumerate(today.get("live") or []):
        if not isinstance(card, dict):
            continue
        for field in LIVE_TAB_FORBIDDEN_FIELDS:
            if card.get(field) is not None:
                faults.append(
                    f"today.live[{i}] carries {field!r}: the Live tab shows the "
                    f"score and what the operator took, and a probability or a "
                    f"tier chip beside a game in progress is the pre-CARD_FACE "
                    f"card returning")
    heading = today.get("live_heading")
    if heading and not any(word in heading for word in LIVE_TAB_HEADINGS):
        faults.append(
            f"the Live tab's heading is {heading!r}, which is not one of "
            f"{LIVE_TAB_HEADINGS}: a heading from another group has followed "
            f"the reader onto this tab")
    return faults + _board_live_row_faults(payload)


#: What a live row of the board may not carry (LIVE TAB, re-homed by the
#: board merge, 2026-09-29): the old card's fields, and the board's own names
#: for a chance -- `prob` and `prob_words` -- which the board built on every
#: block and drew on none of its live rows.
BOARD_LIVE_FORBIDDEN_FIELDS = LIVE_TAB_FORBIDDEN_FIELDS + ("prob", "prob_words")


def _board_live_row_faults(payload) -> list[str]:
    """LIVE TAB ON THE BOARD (the merge, 2026-09-29). The Live tab left with
    the old Picks route; a game being played is a row on Games now, marked
    LIVE, and the same promise holds it: the row shows the game and the
    pregame figure with its word, and nothing else -- no chance and no tier
    chip on its pick, on any question behind it or on a live prop tile, and
    no label over its pick but the live one (another state's label following
    a game into play is the heading that followed the reader onto Live)."""
    from . import language

    board = ((payload or {}).get("board") or {})
    if not board:
        return []
    faults: list[str] = []
    live_label = language.pick_label_words("live", "none")
    for i, game in enumerate(board.get("games") or []):
        if not isinstance(game, dict) or game.get("state") != "live":
            continue
        blocks = ([("pick", game.get("pick"))] if game.get("pick") else []) + [
            (f"questions[{j}]", q) for j, q in enumerate(game.get("questions") or [])]
        for where, block in blocks:
            if not isinstance(block, dict):
                continue
            for field in BOARD_LIVE_FORBIDDEN_FIELDS:
                if block.get(field) is not None:
                    faults.append(
                        f"board.games[{i}].{where} carries {field!r}: a live "
                        f"row shows the game and the pregame figure, and a "
                        f"chance or a tier chip beside a game in progress is "
                        f"the pre-CARD_FACE card returning")
        label = game.get("pick_label_words")
        if game.get("pick") and label != live_label:
            faults.append(
                f"board.games[{i}] is live and its pick is labelled {label!r}, "
                f"not {live_label!r}: a label from another state has followed "
                f"the game into play")
    for i, tile in enumerate(((board.get("props") or {}).get("tiles")) or []):
        if not isinstance(tile, dict) or tile.get("state") != "live":
            continue
        for field in BOARD_LIVE_FORBIDDEN_FIELDS:
            if tile.get(field) is not None:
                faults.append(
                    f"board.props.tiles[{i}] is live and carries {field!r}: a "
                    f"prop being played shows the game and nothing else")
    return faults


def check_the_live_tab_shows_only_the_game(payload) -> None:
    faults = live_tab_faults(payload)
    if faults:
        raise LawViolation(
            "THE LIVE TAB SHOWS THE GAME AND NOTHING ELSE:"
            + _NL2 + _NL2.join(faults[:6]))


# ---------------------------------------------------------------------------
# EVERY FORECAST MARKET HAS A WAY TO REACH THE VENUE (ruling 1, 2026-09-09)
# ---------------------------------------------------------------------------
#
# WHAT WENT WRONG. `kalshi.SERIES` mapped moneyline, spread and total for
# every sport and nothing else. The record forecasts five NFL player-prop
# markets as well, so `event_ticker` returned None for all of them, every
# card said "no price yet" forever, and NO SCAN NOTICED -- because none of
# them compared the markets the record forecasts against the markets it can
# price. The operator found it by looking at his own screen.
#
# A market may legitimately have no series: the venue does not publish a
# per-game rushing-yards market at all. That is why the declared absence
# exists. The fault is a market in NEITHER map, which is what an oversight
# looks like from the outside -- indistinguishable from a considered
# decision, until somebody writes the decision down.


def venue_series_faults() -> list[str]:
    """Forecast markets with neither a venue series nor a declared absence."""
    from . import config
    from .market import kalshi

    faults: list[str] = []
    for sport in sorted(kalshi.SERIES_MEASURED):
        for market in config.SPORT_MARKETS.get(sport, ()):  # declared order
            if (sport, market) in kalshi.SERIES:
                continue
            if (sport, market) in kalshi.NO_VENUE_SERIES:
                continue
            faults.append(
                f"{sport} forecasts {market!r} and has no way to reach the "
                f"venue for it: no entry in kalshi.SERIES and no dated "
                f"absence in kalshi.NO_VENUE_SERIES. Every card in this "
                f"market will say it has no price for as long as that is "
                f"true, and nothing else will say why. Declare the series, "
                f"or declare the absence with what was searched and when.")
    for (sport, market), why in sorted(kalshi.NO_VENUE_SERIES.items()):
        if len(why.strip()) < 40:
            faults.append(
                f"{sport}.{market} declares an absence in {len(why.strip())} "
                f"characters. An absence is evidence -- what was searched, "
                f"how much of it, and when -- or it is a shrug with a "
                f"docstring.")
        if (sport, market) in kalshi.SERIES:
            faults.append(
                f"{sport}.{market} is declared BOTH as a series and as an "
                f"absence. One of the two is stale.")
    return faults


def check_every_forecast_market_can_reach_the_venue() -> None:
    faults = venue_series_faults()
    if faults:
        raise LawViolation(
            "A FORECAST MARKET HAS NO TICKER AND NO DECLARED ABSENCE:"
            + _NL2 + _NL2.join(faults[:8]))


# ---------------------------------------------------------------------------
# THE BROWSER FILES PARSE (ruling 4, 2026-09-09)
# ---------------------------------------------------------------------------
#
# Every other scan in this module reads `app.js` as TEXT: regexes for
# forbidden words, class literals, the shape of the expander. None of them
# cares whether the text is a program. On 2026-09-08 it was not -- `const
# more` was declared twice in one block, the file did not parse, `boot()`
# never ran, nothing rendered on any route, and the gate was green.
#
# NODE COMES FROM PLAYWRIGHT, not from the machine. Playwright is already a
# declared dependency and ships its own binary, so the gate does not quietly
# depend on whatever somebody happens to have installed -- and if neither is
# there this RAISES rather than passing, because a check that cannot run is
# not a check that passed.
#
# HTML AND CSS ARE NOT PARSED HERE and this does not pretend otherwise: node
# parses JavaScript. What stands behind the other two is the dead-selector
# scan, `tools/contrast.py`, and the browser suite loading the real page.

#: The files node can actually parse. `index.html` and `style.css` are not
#: JavaScript and are not listed rather than being silently skipped.
BROWSER_SCRIPTS = ("app.js", "sw.js")


def _node_binary() -> str | None:
    """Playwright's node first, then the machine's."""
    import shutil
    import sys

    shipped = (Path(sys.prefix) / "Lib" / "site-packages" / "playwright"
               / "driver" / "node.exe")
    if shipped.exists():
        return str(shipped)
    unix = (Path(sys.prefix) / "lib" / "site-packages" / "playwright"
            / "driver" / "node")
    if unix.exists():
        return str(unix)
    return shutil.which("node")


def browser_syntax_faults(root: Path | None = None) -> list[str]:
    """Every browser script that does not parse, with node's own message.

    `root` is for the planting: it copies the shipped files somewhere else,
    breaks one, and asks the same function the gate asks. Breaking the real
    `app.js` to prove a guard works is how a broken `app.js` gets committed.
    """
    import subprocess

    from . import config

    node = _node_binary()
    if node is None:
        raise LawViolation(
            "THE GATE CANNOT PARSE THE BROWSER FILES. No node binary: not at "
            "playwright/driver inside this environment, and not on PATH. A "
            "check that cannot run is not a check that passed -- install "
            "playwright's browsers or put node on PATH.")
    faults: list[str] = []
    for name in BROWSER_SCRIPTS:
        path = (root or (config.PACKAGE_ROOT / "web")) / name
        if not path.exists():
            faults.append(f"{name} is declared a browser script and is not there")
            continue
        done = subprocess.run(
            [node, "--check", str(path)],
            capture_output=True, text=True, timeout=60)
        if done.returncode != 0:
            first = (done.stderr or done.stdout or "").strip().splitlines()
            detail = " | ".join(line.strip() for line in first[:4] if line.strip())
            faults.append(f"{name} does not parse: {detail}")
    return faults


_STRAY_MARKER = re.compile(r"\*/|/\*")


def stray_comment_marker_faults(css: str) -> list[str]:
    """A comment marker left standing once every comment is blanked.

    A COMMENT THAT ATE A RULE (2026-09-24/25): a banner comment opened a
    second comment inside itself, so the first `*​/` closed both and the
    banner's second half stood outside any comment. A browser reads such
    text as the prelude of the next rule and drops that rule whole -- which
    is how `.bar { height: auto }` was written twice and never applied. The
    JS syntax check cannot see this: CSS never fails to parse, it drops.
    """
    stripped = _without_comments(css, "css")
    faults = []
    for n, line in enumerate(stripped.split("\n"), 1):
        if _STRAY_MARKER.search(line):
            faults.append(
                f"style.css line {n} carries a comment marker outside any "
                f"comment ({line.strip()[:60]!r}). The browser reads what "
                f"follows as a rule's prelude and drops the next rule whole.")
    return faults


def check_the_browser_files_parse() -> None:
    faults = browser_syntax_faults()
    from . import config as _config
    css_path = _config.PACKAGE_ROOT / "web" / "style.css"
    if css_path.exists():
        faults += stray_comment_marker_faults(css_path.read_text(encoding="utf-8"))
    if faults:
        raise LawViolation(
            "A BROWSER FILE DOES NOT PARSE, so nothing on any route renders "
            "and every text scan above this line was reading a file the "
            "browser cannot run:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# A CLAIM IS PRICED AT THE LINE, NEVER AT THE OPEN (OPENING_READ, 2026-09-09)
# ---------------------------------------------------------------------------
#
# The opening read exists so a card four days out can show a real number
# instead of "no price yet". It is a look at a market that may be a week from
# closing, and a claim priced off it would be a claim about a price nobody
# could still take by kickoff, scored afterwards against a real outcome --
# which would flatter the record in exactly the way LAW 4 exists to prevent.
#
# So the two looks are told apart in the row, and this is the line between
# them. The near-start read is the only one a claim, an at-the-line row or a
# CLV pair may cite. That is a rule about DATA, so it is checked against the
# data rather than against the code that writes it.


def claims_priced_off_an_open_read(conn) -> list[str]:
    """Claims whose quote is an opening read rather than the near-start look."""
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "at_the_line_claims" not in tables or "venue_quotes" not in tables:
        return []
    columns = {r[1] for r in conn.execute("PRAGMA table_info(venue_quotes)")}
    if "read_kind" not in columns:
        # A record older than the opening read has one kind of look in it and
        # nothing to tell apart. Saying nothing is the truth here; saying
        # "clean" would not be.
        return []
    rows = conn.execute(
        "SELECT c.id, c.prediction_id, c.game_id, c.market, v.fetched_utc"
        "  FROM at_the_line_claims c"
        "  JOIN venue_quotes v ON v.id = c.quote_id"
        " WHERE v.read_kind = 'open'"
        " ORDER BY c.id LIMIT 8").fetchall()
    return [
        f"claim {r['id']} on prediction {r['prediction_id']} "
        f"({r['game_id']} {r['market']}) is priced off an OPENING read taken "
        f"{r['fetched_utc']}. The opening read is a look at a market that may "
        f"be a week from closing; only the near-start look may price a claim."
        for r in rows]


def check_claims_price_at_the_line(conn=None) -> None:
    """Every at-the-line claim cites the near-start look. Named in the brief
    of 2026-09-08 and built 2026-09-09 with the read it guards."""
    close = False
    if conn is None:
        from . import db as _db

        conn = _db.connect()
        close = True
    try:
        faults = claims_priced_off_an_open_read(conn)
    finally:
        if close:
            conn.close()
    if faults:
        raise LawViolation(
            "A CLAIM IS PRICED AT THE LINE, NEVER AT THE OPEN:"
            + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE LIVE POLL KEEPS ASKING, AND NEVER ASKS FOR A PRICE (ruled 2026-09-09)
# ---------------------------------------------------------------------------
#
# TWO RULES, ONE SCAN, both about the same function.
#
# IT KEEPS ASKING. `startLivePolling` ended its tick with
# `if (!live.any_live) stopLivePolling();`, so a page opened before first
# pitch polled ONCE, saw nothing live, and killed its own timer for the day.
# The server held six live cards with scores while the operator's screen said
# nothing was being played. The page stops when the SLATE is complete --
# nothing left to play, which is the poller's own rule -- not when nothing
# happens to be on in the second it asked.
#
# IT NEVER ASKS FOR A PRICE. A live card carries none and may carry none
# (THE_PRICED P2): a score up to ninety seconds stale against a live market is
# adversely selected by construction. A poll that fetched a priced endpoint
# would put that number one render away from the screen.

#: Endpoints that answer with a price, a claim or a recommendation. The live
#: poll may touch none of them.
PRICED_ENDPOINTS = ("/api/week", "/api/shortlist", "/api/recommend",
                    "/api/claims", "/api/combos", "/api/taken")


def live_poll_faults(js: str) -> list[str]:
    """The browser's live poll, read off the renderer."""
    js = _without_comments(js, "js")
    match = re.search(
        r"function\s+startLivePolling\s*\([^)]*\)\s*\{(?P<body>.*?)\n  \}",
        js, re.S)
    if match is None:
        return ["startLivePolling() is not in the renderer, so nothing "
                "re-reads the score while a game is being played"]
    body = match.group("body")
    faults = []
    if re.search(r"if\s*\(\s*!\s*live\.any_live\s*\)", body):
        faults.append(
            "startLivePolling() stops when `any_live` is false: a page opened "
            "before the first game starts polls once, finds nothing on, and "
            "never asks again. It stops when the SLATE is complete.")
    if "slate_complete" not in body:
        faults.append(
            "startLivePolling() never reads `slate_complete`, so nothing "
            "tells it when the day is actually over and the poll may stop.")
    for endpoint in PRICED_ENDPOINTS:
        if endpoint in body:
            faults.append(
                f"startLivePolling() fetches {endpoint!r}: a live card carries "
                f"no price and may carry none, and a poll that reads one puts "
                f"an adversely-selected number one render from the screen.")
    return faults


def check_the_live_poll_keeps_asking(js: str | None = None) -> None:
    if js is None:
        from . import config

        js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    faults = live_poll_faults(js)
    if faults:
        raise LawViolation(
            "THE LIVE POLL KEEPS ASKING, AND NEVER ASKS FOR A PRICE:"
            + _NL2 + _NL2.join(faults))


#: A poll that gives up the first time nothing is on, and one that reads a
#: priced endpoint. The two failures the plantings reproduce.
LIVE_POLL_FIXTURE_POSITIVE = """
  function startLivePolling(data) {
    const tick = async () => {
      const live = await fetchJSON('/api/live');
      applyLive(live);
      if (!live.any_live) stopLivePolling();
    };
    tick();
  }
"""


# ---------------------------------------------------------------------------
# A WITHDRAWN RECOMMENDATION IS NEVER COUNTED (operator ruling 1, 2026-09-24)
# ---------------------------------------------------------------------------
#
# "Voided rows never count in CLV, calibration, correction, readiness, or any
# gate ... Planting: a voided recommendation counted anywhere fails by name."
#
# Recommendations 62, 63, 64 and 66 were published from fits 91-94 before the
# hold and voided by that ruling. On the day it arrived seven statements in
# six functions read `recommendations` straight off the table, and every one
# would have treated those four as standing without a sound: nothing in the
# record said a recommendation could be withdrawn, so nothing asked.
#
# TWO GUARDS, because "anywhere" has two halves:
#
#   * THE SOURCE. Every SQL string in the package and its tools that reads
#     FROM or JOINs `recommendations` sits in a statement that also calls the
#     door, `market.recommend.not_withdrawn`. A new reader that goes round it
#     is named by file, function and line before it can count anything.
#     (From 2026-09-27 a call to `counted_once` answers too: it is this door
#     and question 12's rule, and every measurement reads through it.)
#   * THE ARITHMETIC. The closing line -- the one figure on the page made of
#     recommendations, and the one the kill criterion reads -- is recounted
#     WITHOUT the door and compared. A door that stopped excluding, or a
#     report that stopped using it, shows up as a difference, and the
#     withdrawn recommendations that make it up are named by id.

#: The door, by name. A call to it in the same statement is what makes a read
#: of the table lawful.
RECOMMENDATION_DOOR = "not_withdrawn"

#: THE MEASUREMENT DOOR (operator question 12, ruled 2026-09-27):
#: `market.recommend.counted_once` is `not_withdrawn` and the rule that
#: counts a same-side pair once -- from 2026-09-28 (question 22) one
#: forecaster's, within one distinct bet -- so a call to it answers this
#: scan too.
MEASUREMENT_DOOR = "counted_once"

#: What a read of the table looks like in SQL: FROM or JOIN it, or name it
#: after a comma in a FROM list. Case-insensitive, because SQLite is.
_READS_RECOMMENDATIONS = re.compile(
    r"(?:\b(?:FROM|JOIN)\s+|,\s*)recommendations\b", re.I)

#: The readers allowed round the door, each with its reason. Keyed by the
#: file's path from the repository root and the function it is in.
RECOMMENDATION_DOOR_EXEMPT = {
    "gridiron/market/recommend.py:withdrawn":
        "the other side of the door: it lists what the door leaves out, so "
        "the page can show a withdrawn recommendation as withdrawn",
    # MOVED 2026-09-27 (question 12) from `withdrawn_counted_faults`, whose
    # read it was: both recounts now read the table through this one helper.
    "gridiron/audit.py:_closing_line_rows":
        "the recount: it must not share the door it is checking, or a broken "
        "door would agree with itself",
    "tools/void_fs5.py:select_tainted":
        "the tool that writes the withdrawals reads every recommendation on "
        "the tainted forecasts, withdrawn or not, to prove the set is exactly "
        "the four the ruling names",
}

#: THE READERS THAT KEEP THE RECORD RATHER THAN MEASURE IT (operator
#: question 12, 2026-09-27: "the record shows rows as written. Every
#: measurement counts a same-side pair once"). Each reads every standing
#: recommendation through `not_withdrawn` alone, with its reason; every
#: other reader of the table is a measurement and reads through
#: `counted_once`. Keyed as RECOMMENDATION_DOOR_EXEMPT is, whose readers
#: are exempt from both scans.
RECORD_READERS = {
    # RENAMED 2026-09-28 (question 22) from `_another_standing_row`: the
    # rule pairs a row only with another of the same distinct bet and side.
    "gridiron/market/recommend.py:_an_earlier_row_of_the_same_bet":
        "the rule itself: `counted_once` and `not_counted_once` are both "
        "made of it, so it reads the other standing rows of one distinct "
        "bet as they stand",
    "gridiron/market/recommend.py:not_counted_once":
        "the other side of the measurement door: it lists one forecaster's "
        "repeats the door leaves out, so the page names them",
    "gridiron/market/recommend.py:standing_recommendations":
        "the write rule (GRIDIRON_REPAIR item 5): a game and market holding "
        "any standing recommendation, a pair's later row included, gets no "
        "other, so it reads what stands as written",
    "gridiron/market/recommend.py:let_through_by_the_yes_price":
        "the re-grade tool's selection: a label is written on a row as "
        "written, and question 9 ruled all four -- 3, 10, 26 and 56 -- "
        "though 10 and 26 are each the later row of a pair",
    "gridiron/market/recommend.py:record_closing_prices":
        "the closer: every standing recommendation is closed as written, "
        "and a repeat's close is kept, counted once as its earlier row's",
    "gridiron/market/recommend.py:restate_old_closes":
        "the restatement writes an account beside every old close as "
        "written; it ran once, on 2026-09-24",
    "gridiron/tasks.py:_near_start_snapshots":
        "the near-start reader: every open standing recommendation's "
        "contract is read until its start, so the closer can close it",
    "gridiron/views.py:taken_today":
        "the edge on record when a pick was marked, looked up as written; "
        "it counts nothing",
}


def _door_scan_files(root: Path) -> list[tuple[str, Path]]:
    """(path from the repository root, file) for the package and its tools.

    `tools/guards/` is not read: the plantings break the rule on purpose, in
    a copy. A package planted into a scratch directory has no tools beside
    it, and the scan reads what is there.
    """
    base = root.parent
    files = [(p.relative_to(base).as_posix(), p) for p in sorted(root.rglob("*.py"))
             if "__pycache__" not in p.parts]
    tools = base / "tools"
    if tools.is_dir():
        files += [(p.relative_to(base).as_posix(), p)
                  for p in sorted(tools.glob("*.py"))]
    return files


def _reads_round(root: Path, doors: tuple[str, ...],
                 exempt: set[str]) -> list[tuple[str, int, str | None]]:
    """(file, line, function) of every read of `recommendations` in a
    statement that calls none of `doors`, outside `exempt` ("file:function").
    The one walk both door scans share."""
    found: list[tuple[str, int, str | None]] = []
    for where, path in _door_scan_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        prose = _docstring_nodes(tree)
        parents: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in prose or not _READS_RECOMMENDATIONS.search(node.value):
                continue
            statement, function = node, None
            while statement is not None and not isinstance(statement, ast.stmt):
                statement = parents.get(id(statement))
            outer = statement
            while outer is not None:
                if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function = outer.name
                    break
                outer = parents.get(id(outer))
            if f"{where}:{function}" in exempt:
                continue
            if statement is not None and any(
                    isinstance(n, ast.Call) and (
                        (isinstance(n.func, ast.Name) and n.func.id in doors)
                        or (isinstance(n.func, ast.Attribute)
                            and n.func.attr in doors))
                    for n in ast.walk(statement)):
                continue
            found.append((where, node.lineno, function))
    return found


def recommendation_door_faults(root: Path | None = None) -> list[str]:
    """Every read of `recommendations` in a statement that does not call the
    door, named by file, function and line. `counted_once` answers too: it
    is the door and a rule more (question 12, 2026-09-27)."""
    root = config.PACKAGE_ROOT if root is None else Path(root)
    return [
        f"{where}:{line} ({function or 'module level'}) reads "
        f"`recommendations` without the door. A withdrawn "
        f"recommendation is counted there. Add "
        f"`recommend.{RECOMMENDATION_DOOR}(conn)` to the same "
        f"statement, or a dated reason to "
        f"audit.RECOMMENDATION_DOOR_EXEMPT."
        for where, line, function in _reads_round(
            root, (RECOMMENDATION_DOOR, MEASUREMENT_DOOR),
            set(RECOMMENDATION_DOOR_EXEMPT))]


def measurement_door_faults(root: Path | None = None) -> list[str]:
    """Every read of `recommendations` that is neither through
    `counted_once` nor a reader that keeps the record, named by file,
    function and line (operator question 12, 2026-09-27).

    THE SOURCE HALF OF "EVERY MEASUREMENT". A new count of recommendations
    through `not_withdrawn` alone would count each of the seventeen
    same-side pairs twice -- and, from question 22 (2026-09-28), both
    forecasters' recommendations in one count -- and no figure would say
    so; this names it before it counts anything. (The scan itself is as it
    was: `counted_once` now takes the forecaster, so a statement calling it
    is one forecaster's.) A reader that keeps the record as written -- the
    closer, the write rule -- is in `RECORD_READERS` with its reason.
    """
    root = config.PACKAGE_ROOT if root is None else Path(root)
    return [
        f"{where}:{line} ({function or 'module level'}) reads "
        f"`recommendations` without counting each forecaster's distinct bet "
        f"once. A pair's later row, or both forecasters' rows in one count, "
        f"is counted there. Add `recommend.{MEASUREMENT_DOOR}(conn, "
        f"predictor=...)` to the same statement, or -- if it keeps the "
        f"record rather than measuring it -- a dated reason to "
        f"audit.RECORD_READERS."
        for where, line, function in _reads_round(
            root, (MEASUREMENT_DOOR,),
            set(RECOMMENDATION_DOOR_EXEMPT) | set(RECORD_READERS))]


def check_every_measurement_counts_each_pair_once(root: Path | None = None) -> None:
    faults = measurement_door_faults(root)
    if faults:
        raise LawViolation(
            "A MEASUREMENT READS RECOMMENDATIONS PAST THE COUNTED-ONCE DOOR "
            "(operator questions 12 and 22, 2026-09-27 and 2026-09-28): every "
            "measurement is one forecaster's and counts a same-side pair of "
            "one distinct bet once, and `market.recommend.counted_once` is "
            "the one place that says which rows those are:"
            + _NL2 + _NL2.join(faults))


def check_every_recommendation_reader_uses_the_door(root: Path | None = None) -> None:
    faults = recommendation_door_faults(root)
    if faults:
        raise LawViolation(
            "A READER COUNTS RECOMMENDATIONS PAST THE DOOR (ruling 1, "
            "2026-09-24): a withdrawn recommendation is never counted, and "
            "`market.recommend.not_withdrawn` is the one place that says which "
            "those are:" + _NL2 + _NL2.join(faults))


def _closing_line_rows(conn, sport: str) -> list:
    """Every recommendation of `sport`, read straight off the table with what
    both recounts ask of it: its market, side and stamp, whether it is
    closed, whether its close was measured at the time, whether it is
    withdrawn, whether it carries a re-grade -- and, through the forecast it
    was made from, whose it is and which distinct bet (`bet.columns`: the
    forecaster, the game, the market, the subject -- which names a prop's
    type -- and the rung asked; operator questions 17 and 22, 2026-09-28;
    the prop type out of the key from 2026-09-29, `gridiron.bet`).

    WITHOUT EITHER DOOR, on purpose: a recount that went through
    `not_withdrawn` or `counted_once` would agree with a broken one. (The
    read `withdrawn_counted_faults` made itself until 2026-09-27, shared
    from then with the pair recount of question 12.) The forecast is joined
    LEFT, so a recommendation whose forecast could not be read is kept, with
    no forecaster, and refused by name rather than dropped.
    """
    from . import bet

    def has(table: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,)).fetchone() is not None

    withdrawn_sql = (
        "(EXISTS (SELECT 1 FROM prediction_voids v"
        "          WHERE v.prediction_id = r.prediction_id)"
        + (" OR EXISTS (SELECT 1 FROM recommendation_voids w"
           "             WHERE w.recommendation_id = r.id)"
           if has("recommendation_voids") else "")
        + ")")
    regraded_sql = ("EXISTS (SELECT 1 FROM recommendation_regrades g"
                    "         WHERE g.recommendation_id = r.id)"
                    if has("recommendation_regrades") else "0")
    # AND EACH CLOSE'S ACCOUNT AND VALUE (the prover of question 22,
    # 2026-09-28): a door that counted a pair's LATER row keeps every count
    # and moves the mean, so the recount works out each line's buckets, mean
    # and share too, not its counts alone.
    return conn.execute(
        "SELECT r.id, r.market, r.side, r.created_utc,"
        "       r.closed_utc IS NOT NULL AS closed,"
        "       c.recommendation_id IS NOT NULL AND c.restated = 0"
        "         AND c.clv_cents IS NOT NULL AS measured,"
        "       c.recommendation_id IS NOT NULL AS accounted,"
        "       c.restated AS restated, c.clv_cents AS clv_cents,"
        f"      {withdrawn_sql} AS withdrawn,"
        f"      {regraded_sql} AS regraded,"
        f"      {bet.columns('p')}"
        "  FROM recommendations r"
        "  LEFT JOIN predictions p ON p.id = r.prediction_id"
        "  LEFT JOIN recommendation_closes c ON c.recommendation_id = r.id"
        " WHERE r.sport = ? ORDER BY r.id", (sport,)).fetchall()


def _forecaster_block(report: dict, predictor: str) -> dict:
    """One forecaster's block of a closing line, or {} if it has none."""
    for block in report.get("forecasters") or []:
        if block.get("predictor") == predictor:
            return block
    return {}


def withdrawn_counted_faults(conn, report: dict) -> list[str]:
    """The closing line, recounted without the door, against `report` --
    each forecaster's line on its own (operator question 22, 2026-09-28).

    Written against the table directly, on purpose: a recount that went
    through `not_withdrawn` would agree with a broken `not_withdrawn`. The
    rules are clv_report's own -- measured means an account written at the
    time with a closing value; every closed recommendation is in one of its
    four buckets; an open one is awaiting its close -- applied to the
    recommendations that still stand.

    THE WINDOW IS NOT THIS RECOUNT'S QUESTION (2026-09-27). From the
    operator's ruling 8 of 2026-09-23 a measured close on a recommendation
    written before `config.CLOSING_LINE_WINDOW_START` is named beside the
    count (`before_window`) rather than in it. What is recounted here is every
    measured close, in the count or before the window, so a close the window
    moves from one to the other is neither lost nor found, and a withdrawn one
    in either is caught.

    NOR IS A PAIR (operator question 12, 2026-09-27). The report sets aside a
    same-side pair's later rows, and tallies them (`set_aside`); they are
    added back here, so every standing row is still accounted for once and a
    withdrawn one still shows. Whether the right rows were set aside is
    `pair_counted_faults`'s question.

    PER FORECASTER (question 22): a recommendation is its forecast's
    forecaster's, and each forecaster's block is recounted from that
    forecaster's rows; a block naming a forecaster that is not one of the two
    counts rows nobody wrote, and is `pair_counted_faults`'s to name.
    """
    from .market import recommend

    sport = report["sport"]
    rows = _closing_line_rows(conn, sport)
    faults = []
    for predictor in recommend.FORECASTERS:
        mine = [r for r in rows if r["predictor"] == predictor]
        standing = [r for r in mine if not r["withdrawn"]]
        gone = [r for r in mine if r["withdrawn"]]
        block = _forecaster_block(report, predictor)
        expected = {
            "n": sum(1 for r in standing if r["closed"] and r["measured"]),
            "closed": sum(1 for r in standing if r["closed"]),
            "awaiting_close": sum(1 for r in standing if not r["closed"]),
            "withdrawn": len(gone),
        }
        aside = block.get("set_aside") or {}
        got = {
            "n": (block.get("n", 0) + (block.get("before_window") or 0)
                  + (aside.get("measured") or 0)),
            "closed": sum((block.get(k) or 0) for k in
                          ("n", "unmeasured", "restated", "unaccounted",
                           "before_window")) + (aside.get("closed") or 0),
            "awaiting_close": (block.get("awaiting_close", 0)
                               + (aside.get("awaiting_close") or 0)),
            "withdrawn": block.get("withdrawn", 0),
        }
        culprits = {
            "n": [r["id"] for r in gone if r["closed"] and r["measured"]],
            "closed": [r["id"] for r in gone if r["closed"]],
            "awaiting_close": [r["id"] for r in gone if not r["closed"]],
            "withdrawn": [r["id"] for r in gone],
        }
        what = {
            "n": ("measured closes in its count, before its window or set "
                  "aside as a pair"),
            "closed": "closed recommendations in its buckets or set aside",
            "awaiting_close": "recommendations awaiting a close or set aside",
            "withdrawn": "withdrawn recommendations named beside it",
        }
        whose = config.FORECASTER_LABELS.get(predictor, predictor)
        for key in ("n", "closed", "awaiting_close", "withdrawn"):
            if got[key] == expected[key]:
                continue
            named = ", ".join(str(i) for i in culprits[key][:12]) or "none"
            faults.append(
                f"{sport}: the {whose} closing line reports {got[key]} "
                f"{what[key]} where that forecaster's recommendations that "
                f"stand hold {expected[key]}. Withdrawn recommendation(s) that "
                f"would make the difference: {named}.")
    return faults


def check_no_withdrawn_recommendation_counted(conn, report: dict | None = None,
                                              *, sport: str | None = None) -> None:
    """Refuse a closing line that counts a withdrawn recommendation.

    Runs inside `calibration.scorecard` (from 2026-09-28; `views.scorecard`
    until then) on the payload the API is about to serve, in one instant with
    the line, and in the gate against the record's copy for every sport.
    """
    if report is None:
        # BUILT AND RECOUNTED IN ONE INSTANT (2026-09-28), as the Record
        # page's are: a close written between the two is no fault.
        from . import calibration, db

        with db.one_instant(conn):
            report = calibration.clv_report(conn, sport=sport)
            faults = withdrawn_counted_faults(conn, report)
    else:
        faults = withdrawn_counted_faults(conn, report)
    if faults:
        raise LawViolation(
            "A WITHDRAWN RECOMMENDATION IS COUNTED (ruling 1, 2026-09-24): "
            "voided rows never count in the closing line or anything it "
            "feeds:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# A PAIR COUNTED ONCE, WITHIN ONE FORECASTER'S DISTINCT BET (operator
# question 12, ruled 2026-09-27; question 22, ruled 2026-09-28)
# ---------------------------------------------------------------------------
#
# Question 12: "Every measurement counts a same-side pair once (the earlier
# row)." Question 22: "(A). Recommendation counts split per forecaster, like
# every other count. This reverses Q12 for 45/46: each counts once in its own
# forecaster's line, and the 'Both sides, no position' row goes. Same-side
# pairs count once only within one forecaster." -- on question 17's one
# function (`gridiron.bet`). Two guards, as for a withdrawal: the source scan
# above (`measurement_door_faults`, unchanged) and this recount, which works
# the rule out again here -- in Python, by `bet.of`, from rows read without
# either door -- and refuses a closing line that carries a figure for both
# forecasters at once, a line naming no forecaster or one of neither, or any
# forecaster's or market's count, bucket, mean, share, set-aside tally,
# repeat count or re-grade count that differs from it, or words and labels
# that state another -- naming the rows that would make each difference.
# And a record holding two sides of one distinct bet, which item 5's rule
# cannot write and no ruling says how to count. Runs inside
# `calibration.scorecard`, in one instant with the line (`views.scorecard`
# until 2026-09-28), and in the gate on the record's copy for every sport.

#: WHAT A CLOSING LINE CARRIES AT ITS TOP LEVEL, and nothing else (question
#: 22): every count is inside a forecaster's block or a market's line, so any
#: other key there -- `n`, `window_line`, `awaiting_close`, `repeats`,
#: `both_sides` and the rest the payload carried until 2026-09-28, or a
#: total under any new name -- is a figure over both forecasters, and is
#: refused. An allow-list, not a list of the old names (the prover,
#: 2026-09-28): a total over both called something new would pass a list of
#: what totals used to be called.
CLOSING_LINE_KEYS = ("sport", "record", "declared", "window", "forecasters",
                     "markets", "note")


def _counted_once_roles(rows: list) -> dict[int, str]:
    """The rulings, worked out on their own: for every standing row,
    "counted" or "repeat". Of the standing rows of one distinct bet
    (`bet.of`: one forecaster's question at one rung) on one side, the first
    (stamp, then number) is counted and the rest are repeats. Two
    forecasters, or two rungs, are never one group."""
    from . import bet

    groups: dict[tuple, list] = {}
    for row in sorted((r for r in rows if not r["withdrawn"]),
                      key=lambda r: (r["created_utc"], r["id"])):
        groups.setdefault((bet.of(row), row["side"]), []).append(row)
    roles: dict[int, str] = {}
    for group in groups.values():
        roles[group[0]["id"]] = "counted"
        roles.update({row["id"]: "repeat" for row in group[1:]})
    return roles


def _two_sided_bets(rows: list) -> list[list[int]]:
    """The standing rows of each distinct bet recommended on both sides.
    Item 5's rule (one per game and market, across forecasters) cannot
    write one, and none is on the record (2026-09-28)."""
    from . import bet

    sides: dict[tuple, dict] = {}
    for row in rows:
        if row["withdrawn"]:
            continue
        sides.setdefault(bet.of(row), {}).setdefault(row["side"], []).append(row["id"])
    return [sorted(i for ids in by_side.values() for i in ids)
            for by_side in sides.values() if len(by_side) > 1]


#: Which rows each figure a recount compares is made of: its kind of close
#: (measured, closed, open) or its label. A figure of what was SET ASIDE
#: counts the other way round: more of it means counted rows set aside.
_FIGURE_ROWS = {
    "n": lambda r: r["closed"] and r["measured"],
    "window_line": lambda r: r["closed"] and r["measured"],
    "closed": lambda r: r["closed"],
    "awaiting_close": lambda r: not r["closed"],
    "regraded": lambda r: r["regraded"],
    "repeats": lambda r: True,
    "set_aside_measured": lambda r: r["closed"] and r["measured"],
    "set_aside_closed": lambda r: r["closed"],
    "set_aside_awaiting": lambda r: not r["closed"],
}
_ASIDE_FIGURES = ("repeats", "set_aside_measured", "set_aside_closed",
                  "set_aside_awaiting")


def _likely(rows: list, predictor: str, key: str, got: int,
            expected: int) -> list[int]:
    """The rows that would make the difference between a figure the report
    gives for `predictor` and the one the rule gives, among the rows that
    figure is made of (`_FIGURE_ROWS`).

    Two candidate sets each way. A count too HIGH holds rows the rule leaves
    out: this forecaster's repeats (the rule removed), or the other
    forecaster's counted rows (a count pooling both). A count too LOW has
    lost rows the rule counts: this forecaster's counted rows that share a
    game and market with another standing row (a rule keyed wider than the
    one function, setting them aside), or any of its counted rows. The set
    whose size is the difference is named; where neither or both are, both.
    """
    keep = _FIGURE_ROWS.get(key, lambda r: True)
    scoped = [r for r in rows if r["role"] and keep(r)]
    too_many = (got > expected) != (key in _ASIDE_FIGURES)
    difference = abs(got - expected)
    mine = [r for r in scoped if r["predictor"] == predictor]
    if too_many:
        first = [r["id"] for r in mine if r["role"] == "repeat"]
        second = [r["id"] for r in scoped if r["predictor"] != predictor
                  and r["role"] == "counted"]
    else:
        counted = [r for r in mine if r["role"] == "counted"]
        first = [r["id"] for r in counted if any(
            o["id"] != r["id"] and o["role"] in ("counted", "repeat")
            and o["game_id"] == r["game_id"] and o["market"] == r["market"]
            for o in rows)]
        second = [r["id"] for r in counted]
    for candidates in (first, second):
        if len(candidates) == difference:
            return candidates
    return sorted(set(first) | set(second))


def _buckets(closed: list, window_from: str) -> dict:
    """The closing line's own sorting of closed rows, worked out again: a
    close measured at the time on a recommendation written since the window
    opened is in N; one written before it is `before_window`; an old close
    worked out again is `restated`; one with no account `unaccounted`; the
    rest `unmeasured`. And the mean and the share that beat the close, over
    N, as the builder rounds them."""
    measured = [r for r in closed if r["accounted"] and not r["restated"]
                and r["clv_cents"] is not None]
    got = [r for r in measured if r["created_utc"] >= window_from]
    restated = sum(1 for r in closed if r["accounted"] and r["restated"]
                   and r["clv_cents"] is not None)
    unaccounted = sum(1 for r in closed if not r["accounted"])
    n = len(got)
    return {
        "n": n,
        "before_window": len(measured) - n,
        "restated": restated,
        "unaccounted": unaccounted,
        "unmeasured": len(closed) - len(measured) - restated - unaccounted,
        "mean": round(sum(r["clv_cents"] for r in got) / n, 2) if n else None,
        "beat": (round(sum(1 for r in got if r["clv_cents"] > 0) / n, 4)
                 if n else None),
    }


def pair_counted_faults(conn, report: dict) -> list[str]:
    """The closing line, recounted by questions 12 and 22's rule on the one
    distinct-bet key, per forecaster and per market, against `report` -- its
    counts, its buckets, its mean and share once they may be read, and the
    words and labels that state them (the prover of question 22,
    2026-09-28: a door counting a pair's later row keeps every count, and a
    sentence stating another count than its figure passes a check of the
    figure)."""
    from . import calibration, language
    from .market import recommend

    sport = report["sport"]
    window = report.get("window") or {}
    window_open = bool(window.get("open"))
    window_from = calibration.closing_line_window()["from_utc"]
    raw = _closing_line_rows(conn, sport)
    roles = _counted_once_roles(raw)
    rows = [dict(r, role=roles.get(r["id"])) for r in raw]
    faults: list[str] = []
    # NO FIGURE FOR BOTH AT ONCE (question 22), under any name.
    pooled = [key for key in report if key not in CLOSING_LINE_KEYS]
    if pooled:
        faults.append(
            f"{sport}: the closing line carries {pooled} for both forecasters "
            f"at once; every count of recommendations is one forecaster's, "
            f"and a total over both is refused.")
    # A ROW IN NO FORECASTER'S LINE, AND TWO SIDES OF ONE BET.
    lost = [r["id"] for r in rows if r["role"]
            and r["predictor"] not in recommend.FORECASTERS]
    if lost:
        faults.append(
            f"{sport}: recommendation(s) {lost} stand on no forecaster's "
            f"forecast that can be read, so no forecaster's line counts them.")
    for ids in _two_sided_bets(raw):
        faults.append(
            f"{sport}: recommendations {ids} take both sides of one distinct "
            f"bet (one forecaster's question at one rung). Item 5's rule "
            f"cannot write this, and no ruling says how it is counted: it "
            f"needs the operator's.")
    for block in report.get("forecasters") or []:
        if block.get("predictor") not in recommend.FORECASTERS:
            faults.append(
                f"{sport}: the closing line has a line for "
                f"{block.get('predictor')!r}, which is not one forecaster.")
    for entry in report.get("markets") or []:
        if entry.get("predictor") not in recommend.FORECASTERS:
            faults.append(
                f"{sport}: the closing line for {entry.get('market')!r} names "
                f"forecaster {entry.get('predictor')!r}, not one of "
                f"{list(recommend.FORECASTERS)}: it counts both, or nobody's.")
    for predictor in recommend.FORECASTERS:
        whose = config.FORECASTER_LABELS.get(predictor, predictor)
        mine = [r for r in rows if r["predictor"] == predictor]
        counted = [r for r in mine if r["role"] == "counted"]
        aside = [r for r in mine if r["role"] == "repeat"]
        block = _forecaster_block(report, predictor)
        if not block:
            faults.append(f"{sport}: the closing line has no line for {whose}.")
        held = block.get("set_aside") or {}
        window_line = block.get("window_line") or {}
        sorted_ = _buckets([r for r in counted if r["closed"]], window_from)
        expected = {
            "n": sum(1 for r in counted if r["closed"] and r["measured"]),
            "closed": sum(1 for r in counted if r["closed"]),
            "before_window": sorted_["before_window"],
            "restated": sorted_["restated"],
            "unaccounted": sorted_["unaccounted"],
            "awaiting_close": sum(1 for r in counted if not r["closed"]),
            "repeats": len(aside),
            "set_aside_measured": sum(1 for r in aside
                                      if r["closed"] and r["measured"]),
            "set_aside_closed": sum(1 for r in aside if r["closed"]),
            "set_aside_awaiting": sum(1 for r in aside if not r["closed"]),
            "window_line": sorted_["n"],
        }
        got = {
            "n": block.get("n", 0) + (block.get("before_window") or 0),
            "closed": sum((block.get(k) or 0) for k in
                          ("n", "unmeasured", "restated", "unaccounted",
                           "before_window")),
            "before_window": block.get("before_window") or 0,
            "restated": block.get("restated") or 0,
            "unaccounted": block.get("unaccounted") or 0,
            "awaiting_close": block.get("awaiting_close", 0),
            "repeats": block.get("repeats") or 0,
            "set_aside_measured": held.get("measured") or 0,
            "set_aside_closed": held.get("closed") or 0,
            "set_aside_awaiting": held.get("awaiting_close") or 0,
            "window_line": window_line.get("n", 0),
        }
        what = {
            "n": "measured closes in its count or before its window",
            "closed": "closed recommendations in its buckets",
            "before_window": "measured closes from before its window",
            "restated": "older closes worked out again",
            "unaccounted": "closes with no account",
            "awaiting_close": "recommendations awaiting a close",
            "repeats": "repeats of an earlier recommendation named beside it",
            "set_aside_measured": "measured closes set aside",
            "set_aside_closed": "closed recommendations set aside",
            "set_aside_awaiting": "open recommendations set aside",
            "window_line": "recommendations in its window line (its own N)",
        }
        # ITS WORDS AND ITS LABELS, WHOSE AND HOW MANY, as the builder writes
        # them and nothing else: a window line stating another count than
        # the recount's, or a row naming no forecaster or the other one.
        if block:
            said = {
                "its label": (block.get("label"),
                              language.FORECASTER_FILTER_WORDS.get(predictor)),
                "its window line's label": (
                    window_line.get("label"),
                    language.closing_line_label("Since the repair", predictor)),
                "its window line": (
                    window_line.get("words"),
                    language.closing_line_window_line(
                        window.get("from") or "", window.get("first_clean_read") or "",
                        sorted_["n"], verdict_open=window_open,
                        predictor=predictor) if window.get("from") else None),
            }
            for name, title in (("withdrawn_line", "Withdrawn"),
                                ("regraded_line", "Would not have cleared")):
                if block.get(name):
                    said[f"its {title!r} label"] = (
                        block[name].get("label"),
                        language.closing_line_label(title, predictor))
            for name, (have, want) in said.items():
                if have != want:
                    faults.append(
                        f"{sport}: the {whose} closing line's {name[4:]} reads "
                        f"{have!r} where the recount writes {want!r}.")
        # AND THE RE-GRADE LINE BESIDE IT, a count too: the labelled rows
        # the rule counts. Asked only of a block that carries the line.
        if "regraded" in block:
            expected["regraded"] = sum(1 for r in counted if r["regraded"])
            got["regraded"] = block.get("regraded") or 0
            what["regraded"] = "recommendations that would not have cleared"
        for key in expected:
            if got[key] == expected[key]:
                continue
            named = ", ".join(str(i) for i in _likely(
                rows, predictor, key, got[key], expected[key])[:12]) or "none"
            faults.append(
                f"{sport}: the {whose} closing line reports {got[key]} "
                f"{what[key]} where each of that forecaster's distinct bets "
                f"counted once holds {expected[key]}. A repeat, or a row of "
                f"another forecaster or distinct bet, that would make the "
                f"difference: {named}.")
    # EACH MARKET'S LINE, ONE FORECASTER'S: a market pooled, lost or
    # miscounted inside a forecaster whose totals still add up is seen here.
    entries: dict[tuple, dict] = {}
    for entry in report.get("markets") or []:
        key = (entry.get("market"), entry.get("predictor"))
        if key in entries:
            faults.append(f"{sport}: the closing line has two lines for "
                          f"{key[0]!r}, {key[1]!r}.")
        entries[key] = entry
    held_keys = ({(r["market"], r["predictor"]) for r in rows
                  if r["role"] == "counted" and r["closed"]}
                 | {(r["market"], r["predictor"]) for r in rows
                    if r["role"] == "repeat"})
    for market, predictor in sorted(
            held_keys | {k for k in entries if k[1] in recommend.FORECASTERS},
            key=lambda k: (str(k[0]), str(k[1]))):
        if predictor not in recommend.FORECASTERS:
            continue
        whose = config.FORECASTER_LABELS.get(predictor, predictor)
        here = [r for r in rows if r["market"] == market]
        counted = [r for r in here if r["predictor"] == predictor
                   and r["role"] == "counted" and r["closed"]]
        entry = entries.get((market, predictor))
        if entry is None:
            named = ", ".join(str(r["id"]) for r in counted[:12]) or "none"
            faults.append(
                f"{sport}: the closing line has no {market} line for {whose}, "
                f"where the recount holds {len(counted)} closed recommendation(s) "
                f"of that forecaster counted once: {named}.")
            continue
        sorted_ = _buckets(counted, window_from)
        repeats = sum(1 for r in here if r["predictor"] == predictor
                      and r["role"] == "repeat")
        expected = {
            "n": sum(1 for r in counted if r["measured"]),
            "closed": len(counted),
            "before_window": sorted_["before_window"],
            "restated": sorted_["restated"],
            "unaccounted": sorted_["unaccounted"],
            "repeats": repeats,
        }
        got = {
            "n": entry.get("n", 0) + (entry.get("before_window") or 0),
            "closed": sum((entry.get(k) or 0) for k in
                          ("n", "unmeasured", "restated", "unaccounted",
                           "before_window")),
            "before_window": entry.get("before_window") or 0,
            "restated": entry.get("restated") or 0,
            "unaccounted": entry.get("unaccounted") or 0,
            "repeats": entry.get("repeats") or 0,
        }
        what = {"n": "measured closes in its count or before its window",
                "closed": "closed recommendations in its buckets",
                "before_window": "measured closes from before its window",
                "restated": "older closes worked out again",
                "unaccounted": "closes with no account",
                "repeats": "repeats named beside it"}
        # ITS FIGURES AND ITS WORDS, as the builder writes them from the
        # rows the rule counts: the mean and the share only once the window
        # is open (`calibration.closing_line_window`, whose own door says
        # when), the finding only for a negative mean past the gate, the
        # sentence and the label naming whose line it is.
        floor = calibration.clv_minimum(market)
        figures = bool(sorted_["n"]) and window_open
        mean = sorted_["mean"] if figures else None
        beat = sorted_["beat"] if figures else None
        renderable = window_open and sorted_["n"] >= floor
        said = {
            "mean": (entry.get("mean_cents"), mean),
            "share that beat the close": (entry.get("beat_the_close"), beat),
            "renderable": (bool(entry.get("renderable")), renderable),
            "finding": (entry.get("finding"),
                        language.clv_finding_line(mean, sorted_["n"])
                        if renderable and mean is not None and mean < 0
                        else None),
            "label": (entry.get("category_label"), language.closing_line_label(
                language.market_words(sport, market), predictor)),
            "words": (entry.get("words"), language.clv_line(
                sorted_["n"], mean, beat, floor,
                unmeasured=sorted_["unmeasured"], restated=sorted_["restated"],
                unaccounted=sorted_["unaccounted"],
                before_window=sorted_["before_window"], repeats=repeats,
                since=window.get("from"),
                first_read=(None if window_open
                            else window.get("first_clean_read")))),
        }
        for name, (have, want) in said.items():
            if have != want:
                named = ", ".join(str(r["id"]) for r in counted[:12]) or "none"
                faults.append(
                    f"{sport}: the {market} line for {whose} gives its {name} "
                    f"as {have!r} where the rows the rule counts give "
                    f"{want!r} (counted: {named}).")
        for key in expected:
            if got[key] == expected[key]:
                continue
            named = ", ".join(str(i) for i in _likely(
                here, predictor, key, got[key], expected[key])[:12]) or "none"
            faults.append(
                f"{sport}: the {market} line for {whose} reports {got[key]} "
                f"{what[key]} where that forecaster's distinct bets counted "
                f"once hold {expected[key]}. A row that would make the "
                f"difference: {named}.")
    return faults


def check_each_pair_counted_once(conn, report: dict | None = None,
                                 *, sport: str | None = None) -> None:
    """Refuse a closing line that counts a same-side pair of one distinct bet
    twice, that pools two forecasters, or that sets aside another
    forecaster's or another question's row as a repeat.

    Runs inside `calibration.scorecard` (from 2026-09-28; `views.scorecard`
    until then) on the payload the API is about to serve, in one instant with
    the line, and in the gate against the record's copy for every sport.
    """
    if report is None:
        # BUILT AND RECOUNTED IN ONE INSTANT (2026-09-28), as the Record
        # page's are: a close written between the two is no fault.
        from . import calibration, db

        with db.one_instant(conn):
            report = calibration.clv_report(conn, sport=sport)
            faults = pair_counted_faults(conn, report)
    else:
        faults = pair_counted_faults(conn, report)
    if faults:
        raise LawViolation(
            "A RECOMMENDATION COUNT IS POOLED, OR A PAIR COUNTED TWICE "
            "(operator questions 12 and 22, ruled 2026-09-27 and 2026-09-28): "
            "every count of recommendations is one forecaster's, and a "
            "same-side pair of one distinct bet is counted once, as its "
            "earlier row:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE PRICED RECORD COUNTS ONE STANDING QUESTION PER FORECASTER (operator
# question 14, ruled 2026-09-27, 1 of 3)
# ---------------------------------------------------------------------------
#
# The guard is `calibration.assert_no_pooled_priced_counts`, inside the
# builder. The gate's step 2 built the Record page for one sport only (the
# forecaster check reads NFL's), so the MLB and college football priced
# counts -- the pooled ones -- were never built by it. This builds every
# sport's on the record's copy and turns the guard's refusal into a failure
# by name, rather than an exception that ends the gate.


def check_the_priced_record_is_never_pooled(conn) -> None:
    """Refuse a priced count, in any sport on the record, that pools two
    forecasters, two cards or two passes of one question -- or that the
    recount by the one distinct-bet key does not make (operator question 17,
    2026-09-28)."""
    from . import bet, calibration
    from .priced import forecast as priced

    faults = []
    for sport in config.SPORTS:
        try:
            calibration.priced_scorecard(conn, sport=sport)
        except (calibration.MergedCurve, calibration.MergedRecord,
                config.CrossSportAggregation, priced.PooledCount,
                bet.NotABet) as exc:
            faults.append(f"{sport}: {exc}")
    if faults:
        raise LawViolation(
            "A PRICED COUNT IS POOLED (operator question 14, ruled "
            "2026-09-27): every count on the Record page that states a gate "
            "distance is one forecaster's (one card's, for UFC), one per "
            "standing question:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# WHERE THE LINE WENT COUNTS ONE BET PER FORECASTER (operator question 14,
# ruled 2026-09-27, 2 of 3)
# ---------------------------------------------------------------------------
#
# The guard is `drift.assert_no_pooled_drift_counts`, inside both builders
# that state the count: the Record page's gate list (`views.drift_report`)
# and the learning panel (`views.learning`). The gate built the gate list for
# NFL alone, inside the whole Record page of the first sport, and the
# learning panel for no sport, so the MLB and college football drift counts
# -- the ones past the fifty -- were never built by it. This builds both for
# every sport on the record's copy and turns the guard's refusal into a
# failure by name.


def check_the_drift_record_is_never_pooled(conn) -> None:
    """Refuse a drift count, in any sport on the record, that pools two
    forecasters, two cards, two prop types or two passes of one question --
    or that the recount by the one distinct-bet key does not make, two rungs
    of one game being two bets (operator question 17, 2026-09-28)."""
    from . import bet, calibration, drift, views

    faults = []
    for sport in config.SPORTS:
        for panel, build in (("the gate list", views.drift_report),
                             ("the learning panel", views.learning)):
            try:
                build(conn, sport)
            except (calibration.MergedCurve, calibration.MergedRecord,
                    config.CrossSportAggregation, drift.PooledCount,
                    bet.NotABet) as exc:
                faults.append(f"{sport}, {panel}: {exc}")
    if faults:
        raise LawViolation(
            "A DRIFT COUNT IS POOLED (operator question 14, ruled 2026-09-27): "
            "every count on the Record page that states a gate distance is "
            "one forecaster's (one card's, for UFC), one per bet:"
            + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE BLIND RECORD'S OUTLOOK COUNTS ITS CURVE'S STANDING QUESTIONS (operator
# question 14, ruled 2026-09-27, 3 of 3)
# ---------------------------------------------------------------------------
#
# The guard is `calibration.assert_no_pooled_outlooks`, inside
# `calibration.blind_categories`, the builder of the Record page's "Record by
# category" table. The gate built that table for NFL alone, inside the whole
# Record page of the first sport, so MLB's outlooks -- "350 of 100" beside a
# curve of 246 on 27 September -- and UFC's, one count across three cards,
# were never built by it. This builds every sport's on the record's copy and
# turns the guard's refusal into a failure by name.


def check_the_correction_counts_are_never_pooled(conn) -> None:
    """Refuse a correction count, in any sport on the record, that is not
    the count the fit's own gate reads -- one forecaster's category, every
    prop type together, each question once -- on the gate list or the
    learning panel, or that the recount by the one key does not make
    (operator question 16, ruled (B) 2026-09-27: "Each correction gate's
    count per forecaster and distinct bet"; built 2026-09-29). The guard is
    `calibration.assert_no_pooled_correction_counts`, inside both builders;
    until this date no guard, gate check or planting read a correction
    count."""
    from . import bet, calibration, correction, views

    faults = []
    for sport in config.SPORTS:
        for panel, build in (("the gate list", views.corrections_report),
                             ("the learning panel", views.learning)):
            try:
                build(conn, sport)
            except (calibration.MergedCurve, calibration.MergedRecord,
                    config.CrossSportAggregation, correction.PooledCount,
                    bet.NotABet) as exc:
                faults.append(f"{sport}, {panel}: {exc}")
    if faults:
        raise LawViolation(
            "A CORRECTION COUNT IS POOLED (operator question 16, ruled "
            "2026-09-27): each correction gate's count is one forecaster's, "
            "each question once, the count the fit's own gate reads:"
            + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# A CORRECTION IS IN FORCE ONLY BY ITS OWN DATED ROW (operator question 32)
# ---------------------------------------------------------------------------
#
# "Corrections activate through the same gate as model fits. Every correction
# row is written inactive. Activation is its own dated append-only row."
# (Ruled 2026-09-29, second set.) The schema holds the rows; this holds the
# DOOR to them. A door that read `active_from` again -- as the one released
# before this date did, which is how the weekly refit's fit 71 came into
# force -- agrees with itself on every record whose rows it wrote, so it is
# asked here on a world made to tell the two apart, and on the record's copy
# against the activation rows read straight off their table.


def _in_force_straight(conn, sport: str, market_type: str,
                       forecaster: str) -> int | None:
    """The correction the category's latest activation row puts in force,
    read off the table with no door: the latest row naming no labelled fit,
    measured or scratch -- its correction; withdrawn, or none -- None."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                    " AND name = 'correction_activations'").fetchone() is None:
        return None
    row = conn.execute(
        "SELECT a.correction_id, a.kind FROM correction_activations a"
        " WHERE a.sport = ? AND a.market_type = ? AND a.forecaster = ?"
        "   AND NOT EXISTS (SELECT 1 FROM correction_gate_labels l"
        "                   WHERE l.correction_id = a.correction_id)"
        " ORDER BY a.seq DESC LIMIT 1",
        (sport, market_type, forecaster)).fetchone()
    if row is None or row[1] == "withdrawn":
        return None
    return int(row[0])


def correction_in_force_faults(conn=None) -> list[str]:
    """Where a correction is served as in force by anything but its own
    activation row, in words; [] when the door reads the rows alone.

    ON A WORLD MADE TO TELL THEM APART (always): a correction written in
    force by hand under the rule before this one (its `active_from` set,
    the schema's refusal taken off to write it) must be served by nobody;
    the weekly refit, on a category it can fit, must write its fit inactive
    and no activation; a scratch activation must put its correction in force,
    and a withdrawal must take it out. ON THE RECORD'S COPY (`conn`): every
    category's served correction is the one its latest activation row names.
    """
    from . import correction, db as _db

    faults: list[str] = []
    probe = _db.connect(":memory:")
    try:
        _db.init(probe)
        probe.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home,"
            " away, kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES ('probe', 'nfl', 2025, 1, 'REG', 'AAA', 'BBB',"
            " '2025-12-01T18:00:00Z', 'final', '2025-12-01', 24, 17)")
        for i in range(60):
            probe.execute(
                "INSERT INTO predictions (sport, created_utc, game_id,"
                " market_type, subject, model_prob, model_side, predictor,"
                " factor_set_version, factors_json, reasoning, resolved_utc,"
                " outcome) VALUES ('nfl', '2025-12-01T06:00:00Z', 'probe',"
                " 'total', ?, 0.64, 'over', 'statistical', 'fs3', '{}',"
                " 'probe', '2025-12-02T00:00:00Z', ?)", (f"P{i}", i % 3 and 1))
        probe.commit()
        report = correction.refit_all(probe, now="2026-01-10T00:00:00Z")
        fitted = [c for c in report["categories"] if c["market_type"] == "total"]
        stored = probe.execute(
            "SELECT id, active_from FROM calibration_corrections"
            " WHERE market_type = 'total'").fetchone()
        rows = probe.execute(
            "SELECT COUNT(*) FROM correction_activations").fetchone()[0]
        if not fitted or stored is None:
            faults.append("the weekly refit wrote no fit for a category of "
                          "sixty settled questions")
        elif stored["active_from"] is not None or rows or \
                correction.active_correction(probe, sport="nfl",
                                             market_type="total",
                                             forecaster="statistical"):
            faults.append(
                f"the weekly refit put what it fitted in force (active_from "
                f"{stored['active_from']!r}, {rows} activation row(s))")
        else:
            correction.activate_in_a_scratch_world(
                probe, stored["id"], now="2026-01-11T00:00:00Z")
            served = correction.active_correction(
                probe, sport="nfl", market_type="total",
                forecaster="statistical")
            if served is None or served["id"] != stored["id"]:
                faults.append("a correction's own activation row did not put "
                              "it in force")
            correction.withdraw(probe, stored["id"], now="2026-01-12T00:00:00Z",
                                reason="the probe takes it out of force")
            served = correction.active_correction(
                probe, sport="nfl", market_type="total",
                forecaster="statistical")
            if served is not None:
                faults.append(f"a withdrawn correction is still served in "
                              f"force (version {served['version']})")
        # UNDER THE RULE BEFORE: a row carrying its own activation, written
        # the way the weekly refit wrote fit 71 -- the schema's refusal of it
        # taken off for the one statement, and put back by `init`.
        probe.execute("DROP TRIGGER calibration_corrections_written_inactive")
        probe.execute(
            "INSERT INTO calibration_corrections (sport, market_type,"
            " forecaster, version, fitted_utc, n_train, slope, intercept,"
            " active_from, status) VALUES ('nfl', 'moneyline', 'statistical',"
            " 1, '2026-01-01T00:00:00Z', 120, 0.8, 0.1,"
            " '2026-01-01T00:00:00Z', 'active - written by hand, the old rule')")
        probe.commit()
        _db.init(probe)
        served = correction.active_correction(
            probe, sport="nfl", market_type="moneyline",
            forecaster="statistical")
        if served is not None:
            faults.append(
                f"a correction carrying active_from and no activation row is "
                f"served in force (version {served['version']}): the door "
                f"reads active_from")
    except Exception as exc:  # noqa: BLE001 -- the fault is the finding
        faults.append(f"the probe world could not be asked: "
                      f"{type(exc).__name__}: {exc}")
    finally:
        probe.close()
    if conn is not None:
        for sport, market_type, forecaster in conn.execute(
                "SELECT DISTINCT sport, market_type, forecaster"
                "  FROM calibration_corrections"
                " ORDER BY sport, market_type, forecaster").fetchall():
            served = correction.active_correction(
                conn, sport=sport, market_type=market_type,
                forecaster=forecaster)
            want = _in_force_straight(conn, sport, market_type, forecaster)
            got = None if served is None else int(served["id"])
            if got != want:
                faults.append(
                    f"{sport} {market_type}, {forecaster}: the door serves "
                    f"correction {got} and the activation rows put "
                    f"{want} in force")
    return faults


def check_a_correction_is_in_force_only_by_its_own_row(conn=None) -> None:
    """Refuse a door that serves a correction in force by anything but its
    own dated activation row (operator question 32, ruled 2026-09-29)."""
    faults = correction_in_force_faults(conn)
    if faults:
        raise LawViolation(
            "A CORRECTION IS IN FORCE WITHOUT ITS OWN ROW (operator question "
            "32, ruled 2026-09-29): every correction row is written inactive, "
            "and a correction is in force only by its own dated activation "
            "row, never by active_from:"
            + _NL2 + _NL2.join(faults))


def check_the_blind_outlook_is_never_pooled(conn) -> None:
    """Refuse an outlook, in any sport on the record, that counts another
    forecaster's rows, another card's, a question's superseded passes, or
    anything but the curve it sits beside -- or that the recount by the one
    distinct-bet key does not make (operator question 17, 2026-09-28)."""
    from . import bet, calibration, horizon

    faults = []
    for sport in config.SPORTS:
        try:
            calibration.blind_categories(conn, sport=sport)
        except (calibration.MergedCurve, calibration.MergedRecord,
                config.CrossSportAggregation, horizon.PooledCount,
                bet.NotABet) as exc:
            faults.append(f"{sport}: {exc}")
    if faults:
        raise LawViolation(
            "A BLIND OUTLOOK IS POOLED (operator question 14, ruled "
            "2026-09-27): the line beside each curve counts that curve's "
            "standing questions -- one forecaster's, one card's for UFC, each "
            "once:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE AT-THE-LINE RECORD COUNTS ONE CLAIM PER DISTINCT BET (GRIDIRON_REPAIR
# item 6, 2026-09-26; operator question 17, 2026-09-28)
# ---------------------------------------------------------------------------
#
# The guard is `calibration.assert_no_pooled_claims`, inside
# `calibration.at_the_line_scorecard`. The gate built that payload for every
# sport only for the advice scan (`tools/verify.py::_at_the_line_payload`),
# where until this date a guard's refusal was no failure the step knew, so a
# pooled count ended the gate in a traceback rather than failing by name
# (that step now names it too). This builds every sport's on the record's
# copy and turns the refusal into a failure of its own, as the three records
# beside it are checked.


def check_the_at_the_line_record_is_never_pooled(conn) -> None:
    """Refuse an at-the-line count, in any sport on the record, that pools
    two forecasters or two cards, counts a question's passes or looks twice,
    or that the recount by the one distinct-bet key does not make."""
    from . import bet, calibration
    from .market import at_the_line

    faults = []
    for sport in config.SPORTS:
        try:
            calibration.at_the_line_scorecard(conn, sport=sport)
        except (calibration.MergedCurve, calibration.MergedRecord,
                config.CrossSportAggregation, at_the_line.PooledCount,
                bet.NotABet) as exc:
            faults.append(f"{sport}: {exc}")
    if faults:
        raise LawViolation(
            "AN AT-THE-LINE COUNT IS POOLED (GRIDIRON_REPAIR item 6; operator "
            "question 17, ruled 2026-09-27): every count at the venue's line "
            "is one forecaster's (one card's, for UFC), one claim per "
            "distinct bet:" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# EVERY COUNT KEYS A DISTINCT BET BY THE ONE FUNCTION (operator question 17,
# ruled 2026-09-27; built 2026-09-28)
# ---------------------------------------------------------------------------
#
# "One function defines a distinct bet." Until this date six keys counted
# one: four `bet_of` functions of their own, a window partitioned by hand in
# the at-the-line door, its coverage line's game, and the standing clause's
# question written out twice. The recount (`gridiron.recount`) proves at run
# time that each door counts what the one key counts; this scan proves in
# the source that no count keys a bet any other way, so a key spelled afresh
# is refused before it can count anything.

#: Names a module may not define: each was a key of its own until 2026-09-28.
BET_KEY_FUNCTIONS = ("bet_of", "count_of_bets", "distinct_bets")

#: The payload figures that say how many distinct bets a count holds.
BET_COUNT_FIGURES = ("distinct_bets", "distinct_bets_written")

#: The SQL words that key a window, written ONCE so the scan below can read
#: for them without its own text being a window keyed by hand.
WINDOW_KEY_WORDS = "PARTITION BY"

#: THE KEY AS RULED, held against the one function's (the prover,
#: 2026-09-28). `gridiron.bet.KEY` is the one place the key is written; the
#: door and the recount both read it, so a column dropped from it -- the rung,
#: the forecaster -- would move every count and every recount alike and no
#: runtime guard could see it. The operator ruled what a distinct bet is
#: (question 17, 2026-09-27; question 21, 2026-09-28): a change to the key is
#: a change to the ruling, and the scan refuses one this constant does not
#: also carry.
#:
#: FIVE COLUMNS, NOT SIX (2026-09-29). The brief of 2026-09-28 read the key
#: as six, the prop type beside the subject; but a prop's question is named
#: by its subject, and the prop type is a column the early rows lack -- ten
#: NFL week-one props asked at 05:55Z with none and again at 07:34Z with one
#: were each two questions, so a morning and a later pass of one question
#: counted twice (`gridiron.bet`'s text has the figures). A key that splits
#: a question by such a column is refused here like one that drops the rung.
RULED_DISTINCT_BET = ("predictor", "game_id", "market_type", "subject",
                      "line_asked")


def _calls_the_bet_module(node, attribute: str) -> bool:
    """Is `node` a call of `bet.<attribute>(...)`?"""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == attribute
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "bet")


def distinct_bet_key_faults(root: Path | None = None) -> list[str]:
    """Every place in the package that keys a distinct bet other than through
    `gridiron.bet`, in words.

    Three shapes, each one a key that was in the shipped code until
    2026-09-28: a module-level or nested function named as a key
    (`BET_KEY_FUNCTIONS`); a `distinct_bets` figure counted by anything but
    `bet.count`; and a SQL window partitioned by anything but
    `bet.columns` -- `WINDOW_KEY_WORDS` in a plain string, or in an f-string
    where the part after them is not `bet.columns(...)`. And two reads of
    the running code: the one function's key is the key as ruled
    (`RULED_DISTINCT_BET`), and the question the standing clause keeps one
    row per is `bet.same`, both times it asks. Docstrings are prose and are
    not read, nor is the one constant naming the words.
    """
    root = config.PACKAGE_ROOT if root is None else Path(root)
    words = WINDOW_KEY_WORDS
    faults: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel == "bet.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        exempt = _docstring_nodes(tree)
        exempt |= {id(node.value) for node in tree.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "WINDOW_KEY_WORDS"
                           for t in node.targets)}
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name in BET_KEY_FUNCTIONS):
                faults.append(
                    f"{rel} line {node.lineno}: `{node.name}` keys a distinct "
                    f"bet of its own; a count asks `bet.of` / `bet.count`")
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, ast.Constant)
                            and key.value in BET_COUNT_FIGURES
                            and not _calls_the_bet_module(value, "count")):
                        faults.append(
                            f"{rel} line {key.lineno}: `{key.value}` is counted "
                            f"by something other than `bet.count`")
            if isinstance(node, ast.JoinedStr):
                parts = node.values
                for i, part in enumerate(parts):
                    if not (isinstance(part, ast.Constant)
                            and isinstance(part.value, str)
                            and words in part.value.upper()):
                        continue
                    nxt = parts[i + 1] if i + 1 < len(parts) else None
                    if (part.value.upper().count(words) != 1
                            or not part.value.rstrip().upper().endswith(words)
                            or not isinstance(nxt, ast.FormattedValue)
                            or not _calls_the_bet_module(nxt.value, "columns")):
                        faults.append(
                            f"{rel} line {part.lineno}: a window is partitioned "
                            f"by something other than `bet.columns(...)`")
            elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and id(node) not in exempt
                  and words in node.value.upper()
                  and not _inside_a_joined_string(tree, node)):
                faults.append(
                    f"{rel} line {node.lineno}: a window is partitioned by a "
                    f"key written out in a plain string, not `bet.columns(...)`")
    from . import bet, calibration

    if tuple(bet.KEY) != RULED_DISTINCT_BET:
        faults.append(
            f"bet.KEY is {tuple(bet.KEY)!r}, not the key as ruled "
            f"{RULED_DISTINCT_BET!r} (the forecaster and the venue's "
            f"question, the rung asked included, a prop's named by its "
            f"subject and split by no column the early rows lack)")
    for same_set in (False, True):
        clause = calibration.standing_row_clause(same_set)
        for a, b in (("p2", "p"), ("p3", "p2")):
            if bet.same(a, b) not in clause:
                faults.append(
                    f"calibration.standing_row_clause({same_set}): the question "
                    f"{a} is matched to {b} by is not `bet.same({a!r}, {b!r})`")
    # AND THE PAIR A RECOMMENDATION COUNT SETS ASIDE (operator questions 12
    # and 22, 2026-09-28): two recommendations are one pair only when their
    # forecasts are one distinct bet. The recount beside the closing line
    # (`pair_counted_faults`) can see a rule keyed wider than the one
    # function only where the record holds a pair it would take -- two
    # forecasters, or two rungs, on one side of one game -- and on
    # 2026-09-28 it holds none of either; so the rule's own text is read.
    from .market import recommend

    other, own = recommend._OTHER_FORECAST, recommend._OWN_FORECAST
    rule = recommend.pairs_with("r")
    # THE KEY AS ITS FIRST TERM, AND NO "OR" BESIDE IT (the prover,
    # 2026-09-28): `bet.same(...) OR <game and market>` carries the key's
    # text and pairs across forecasters and rungs all the same.
    if not rule.startswith(bet.same(other, own) + " AND ") \
            or _or_outside_brackets(rule):
        faults.append(
            f"market.recommend.pairs_with: two recommendations are paired by "
            f"something other than `bet.same({other!r}, {own!r})` and further "
            f"conditions on it, the one distinct-bet key: {rule!r}")
    # AND THE EARLIER ROW COUNTS (question 12: "the earlier row"; the prover,
    # 2026-09-28): a rule keeping a pair's LATER row keeps every count, so
    # before the first clean read no figure the recount can compare moves
    # with it. Pinned here in its own words, as `RULED_DISTINCT_BET` pins the
    # key: the pair's other row is written before the counted one, by its
    # stamp and then its number.
    o = recommend._OTHER
    earlier = (f"AND ({o}.created_utc < r.created_utc OR ({o}.created_utc = "
               f"r.created_utc AND {o}.id < r.id))")
    if not " ".join(rule.split()).endswith(earlier):
        faults.append(
            f"market.recommend.pairs_with: the row a pair counts is not its "
            f"earlier one (stamp, then number): {rule!r}")
    # AND THE LABEL'S RULE IN THE SCHEMA (operator question 23, 2026-09-28;
    # built 2026-09-29): "fitted below its gate" is refused unless the fit's
    # corrected count is the record's own, and a rule cannot call Python, so
    # the key is written out there. Held to the one function: the rule's text
    # (whitespace aside) carries `bet.same('q', 'p')`, the question a row is
    # counted once per.
    # AND THE ACTIVATION'S RULE (operator question 32, 2026-09-29): a
    # measured activation's count of distinct bets is recounted in the
    # schema the same way, and held to the same text.
    for rule in (LABEL_KEY_RULE, ACTIVATION_KEY_RULE):
        rule_text = _schema_rule_text(rule)
        if rule_text is None or bet.same("q", "p") not in " ".join(rule_text.split()):
            faults.append(
                f"schema.sql: the rule `{rule}` counts a fit's questions "
                f"by something other than `bet.same('q', 'p')`, the one "
                f"distinct-bet key -- or is not declared")
    return faults


#: The schema rule that counts a fit's questions by the key written out
#: (question 23; 2026-09-29), read by `distinct_bet_key_faults`.
LABEL_KEY_RULE = "correction_gate_label_is_its_fits_own_record"

#: ...and the rule that recounts a measured activation's distinct bets
#: (question 32, 2026-09-29).
ACTIVATION_KEY_RULE = "correction_activation_counts_distinct_bets"


def _schema_rule_text(name: str, schema: str | None = None) -> str | None:
    """One rule's text as `schema.sql` declares it, through its own `END;`,
    comments blanked; None when the schema does not declare it."""
    text = schema if schema is not None else (
        config.PACKAGE_ROOT / "schema.sql").read_text(encoding="utf-8")
    text = re.sub(r"--[^\n]*", "", text)
    found = re.search(
        r"CREATE\s+TRIGGER\s+IF\s+NOT\s+EXISTS\s+" + re.escape(name) + r"\b",
        text)
    if not found:
        return None
    end = text.find("END;", found.end())
    return text[found.start(): len(text) if end < 0 else end + len("END;")]


def _or_outside_brackets(sql: str) -> bool:
    """Does `sql` join two conditions by OR at its top level, outside every
    bracket? Quoted text is not read."""
    depth, quoted = 0, None
    words = re.split(r"(\s+|\(|\)|'|\")", sql)
    for word in words:
        if quoted:
            if word == quoted:
                quoted = None
            continue
        if word in ("'", '"'):
            quoted = word
        elif word == "(":
            depth += 1
        elif word == ")":
            depth -= 1
        elif depth == 0 and word.upper() == "OR":
            return True
    return False


def _inside_a_joined_string(tree: ast.AST, target) -> bool:
    """Is a string constant one part of an f-string (read with it there)?"""
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and any(v is target for v in node.values):
            return True
    return False


def check_every_count_keys_one_bet(root: Path | None = None) -> None:
    faults = distinct_bet_key_faults(root)
    if faults:
        raise LawViolation(
            "A COUNT KEYS A DISTINCT BET ITS OWN WAY (operator question 17, "
            "ruled 2026-09-27): one function defines a distinct bet -- the "
            "forecaster and the venue's question, the rung asked included -- "
            "and every count reads it (`gridiron.bet`):"
            + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE STANDING PASS, CHOSEN BY PASS (operator question 27, ruled 2026-09-28;
# built 2026-09-29)
# ---------------------------------------------------------------------------
#
# "The standing pass is chosen by pass, not by write time: the final pass
# stands whenever one exists before the start; otherwise the latest early
# pass. A read rule -- no row changes." The order is one door,
# `calibration.standing_pass_order` -- the standing clause's and the
# at-the-line window's -- spelled again in Python by `gridiron.recount`, and
# by pass alone by the correction's measurement, which may not read the
# start. WHY A WORLD AND NOT A RECOUNT: the recount beside each count moves
# with the pass only where one pass carried what the other did not (a price,
# a second look, a claim), and on the sixteen NFL totals the ruling moved it
# moves no count at all -- the curve's Brier and log loss move, and nothing
# that counts sees them. So the gate asks every door that chooses a
# question's row which one stands, on a world made to tell the pass from the
# write time, as question 32's check asks the correction door on a world of
# its own.

#: THE WORLD'S QUESTIONS, each its own distinct bet on one settled NFL
#: total: (subject, its rows as (pass, factor set, hours from the start,
#: withdrawn), the place in that list of the row that must stand, and
#: whether the correction's measurement is asked -- it reads no start, so a
#: question with a row written after its start is the tool's check's
#: (`tools/correction_holdout.py`), not this world's).
STANDING_PASS_WORLD = (
    # THE SIXTEEN'S SHAPE: the final pass written first, the early after it,
    # both before the start (23 September 19:30Z, then 24 September 05:32Z).
    ("SIXTEEN", (("final", "fsA", -23, False), ("early", "fsA", -13, False)),
     0, True),
    # the ordinary order, unchanged
    ("ORDINARY", (("early", "fsA", -20, False), ("final", "fsA", -2, False)),
     1, True),
    # a withdrawn final pass leaves the LATEST early pass standing
    ("WITHDRAWN", (("final", "fsA", -30, True), ("early", "fsA", -25, False),
                   ("early", "fsB", -20, False)), 2, True),
    # a final pass written after the start never stands
    ("LATEFINAL", (("early", "fsA", -10, False), ("final", "fsA", 1, False)),
     0, False),
    # two early passes and no final: the latest early pass
    ("TWOEARLY", (("early", "fsA", -20, False), ("early", "fsB", -10, False)),
     1, True),
    # nothing before the start (a backtest): the latest written, whatever its
    # pass -- the fallback as it was
    ("BACKTEST", (("final", "fsA", 1, False), ("early", "fsA", 2, False)),
     1, False),
)

#: The start of the world's one game, and the instant its correction is
#: measured at (after every question settled).
_STANDING_PASS_START = "2025-12-01T18:00:00Z"
_STANDING_PASS_FITTED = "2025-12-02T06:00:00Z"


def _hours_from(stamp: str, hours: float) -> str:
    from datetime import datetime, timedelta

    moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return (moment + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _standing_pass_world(probe) -> dict[str, list[int]]:
    """Write `STANDING_PASS_WORLD` into an empty database: one settled NFL
    game, each question's rows, their withdrawals, two near-start looks at
    the venue and the claims the near-start reader would have written on
    them. Returns each subject's forecast ids in the world's order."""
    start = _STANDING_PASS_START
    probe.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('probe_q27', 'nfl', 2025, 13, 'REG', 'AAA', 'BBB', ?,"
        " 'final', '2025-12-01', 27, 20)", (start,))
    ids: dict[str, list[int]] = {}
    for subject, rows, _stands, _corrected in STANDING_PASS_WORLD:
        for pass_kind, factor_set, hours, _withdrawn in rows:
            cur = probe.execute(
                "INSERT INTO predictions (sport, created_utc, game_id,"
                " market_type, subject, line_asked, model_prob, model_side,"
                " predictor, pass_kind, factor_set_version, factors_json,"
                " reasoning, resolved_utc, outcome)"
                " VALUES ('nfl', ?, 'probe_q27', 'total', ?, 44.5, 0.6,"
                " 'over', 'statistical', ?, ?, '{}', 'probe', ?, 1)",
                (_hours_from(start, hours), subject, pass_kind, factor_set,
                 _hours_from(start, 4)))
            ids.setdefault(subject, []).append(cur.lastrowid)
    for subject, rows, _stands, _corrected in STANDING_PASS_WORLD:
        for i, (_p, _f, _h, withdrawn) in enumerate(rows):
            if withdrawn:
                probe.execute(
                    "INSERT INTO prediction_voids (prediction_id, voided_utc,"
                    " reason) VALUES (?, ?, 'withdrawn in the probe world')",
                    (ids[subject][i], _hours_from(start, 5)))
    # TWO LOOKS BEFORE THE START, and a claim per forecast at each, in the
    # order of their numbers -- as the near-start reader writes them -- so
    # the claim written last is on whichever pass has the higher number.
    looks = []
    for hours in (-3, -1):
        cur = probe.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " fetched_utc, read_kind) VALUES ('kalshi', ?, 'PROBE', 'nfl',"
            " 'probe_q27', 'total', 'total', 44.5, 'over', 0.5, 0.52, ?,"
            " 'near_start')", (f"PROBE-{hours}", _hours_from(start, hours)))
        looks.append((cur.lastrowid, _hours_from(start, hours + 0.1)))
    for quote_id, claimed in looks:
        for subject, rows, _stands, _corrected in STANDING_PASS_WORLD:
            for i, (_p, _f, hours, _w) in enumerate(rows):
                if _hours_from(start, hours) >= claimed:
                    continue
                probe.execute(
                    "INSERT INTO at_the_line_claims (prediction_id, quote_id,"
                    " venue, sport, game_id, market, quantity, line, side,"
                    " shape, model_prob, venue_price, venue_implied,"
                    " price_basis, created_utc, resolved_utc, outcome)"
                    " VALUES (?, ?, 'kalshi', 'nfl', 'probe_q27', 'total',"
                    " 'total', 44.5, 'over', 'rung_matched', 0.6, 0.52, 0.52,"
                    " 'ask', ?, ?, 1)",
                    (ids[subject][i], quote_id, claimed,
                     _hours_from(start, 4)))
    probe.commit()
    return ids


def standing_pass_faults() -> list[str]:
    """Where a door that chooses a question's row keeps another than the
    ruled pass, in words; [] when every door keeps the final pass written
    before the start, otherwise the latest early pass (operator question 27,
    ruled 2026-09-28; built 2026-09-29).

    Asked on a world made to tell them apart (`STANDING_PASS_WORLD`): the
    standing clause (through `calibration.resolved`, across factor sets and
    within one), its recount (`recount.standing_of`), the outlook's door
    (`horizon.standing_questions`, which reads the clause as the priced and
    drift doors do), the at-the-line window and its recount (a claim stands
    for its forecast's pass), the slate's card (`views.week`) and the
    correction's measurement (`correction.holdout_questions`, by pass alone,
    on the questions with no row after the start)."""
    from . import calibration, correction, db as _db, horizon, recount, views
    from .market import at_the_line

    faults: list[str] = []
    probe = _db.connect(":memory:")
    try:
        _db.init(probe)
        ids = _standing_pass_world(probe)
        want = {subject: ids[subject][stands]
                for subject, _rows, stands, _c in STANDING_PASS_WORLD}
        passes = {i: (subject, rows[n][0], rows[n][2])
                  for subject, rows, _s, _c in STANDING_PASS_WORLD
                  for n, i in enumerate(ids[subject])}

        def said(door: str, kept: dict, only=None) -> None:
            for subject in sorted(only if only is not None else want):
                got = kept.get(subject)
                if got == want[subject]:
                    continue
                if got is None:
                    faults.append(f"{door}: question {subject} has no standing "
                                  f"row, where forecast {want[subject]} stands")
                    continue
                _s, pass_kind, hours = passes[got]
                _s, want_pass, want_hours = passes[want[subject]]
                faults.append(
                    f"{door}: question {subject} stands on its {pass_kind} "
                    f"pass written {hours:+g}h from the start (forecast {got}), "
                    f"where the ruled row is its {want_pass} pass written "
                    f"{want_hours:+g}h (forecast {want[subject]})")

        cell = dict(sport="nfl", predictor="statistical")
        said("calibration.standing_row_clause",
             {r.subject: r.id for r in calibration.resolved(
                 probe, market_type="total", **cell)})
        one_set = {s for s, rows, _st, _c in STANDING_PASS_WORLD
                   if {f for _p, f, _h, _w in rows} == {"fsA"}}
        said("calibration.standing_row_clause within one factor set",
             {r.subject: r.id for r in calibration.resolved(
                 probe, market_type="total", factor_set_version="fsA", **cell)},
             only=one_set)
        said("recount.standing_of",
             {r["subject"]: r["id"] for r in recount.standing_of(
                 recount.forecasts(probe, market_type="total", prop_type=None,
                                   event_tier=None, **cell)).values()})
        said("horizon.standing_questions",
             {r["subject"]: r["id"] for r in horizon.standing_questions(
                 probe, market="total", **cell)})
        claimed = {s for s, rows, st, _c in STANDING_PASS_WORLD
                   if rows[st][2] < -1}
        said("market.at_the_line.standing_claims",
             {c["subject"]: c["prediction_id"] for c in
              at_the_line.standing_claims(probe, market="total", **cell)},
             only=claimed)
        said("recount.standing_claims_of",
             {c["subject"]: c["prediction_id"] for c in
              recount.standing_claims_of(recount.claims(
                  probe, market="total", event_tier=None, **cell)).values()},
             only=claimed)
        if not config.held_market("nfl", "total"):
            said("views.week (the slate's card)",
                 {c["subject"]: c["prediction_id"] for c in views.week(
                     probe, "nfl", 2025, 13, forecaster="statistical")["cards"]
                  if c["market_type"] == "total"})
        said("correction.holdout_questions",
             {r["subject"]: r["id"] for r in correction.holdout_questions(
                 probe, {"sport": "nfl", "market_type": "total",
                         "forecaster": "statistical",
                         "fitted_utc": _STANDING_PASS_FITTED})},
             only={s for s, _r, _st, corrected in STANDING_PASS_WORLD
                   if corrected})
    except Exception as exc:  # noqa: BLE001 -- the fault is the finding
        faults.append(f"the probe world could not be asked: "
                      f"{type(exc).__name__}: {exc}")
    finally:
        probe.close()
    return faults


def check_the_final_pass_stands() -> None:
    """Refuse a door that keeps a question's row by write time over its
    final pass written before the start (operator question 27, ruled
    2026-09-28); gate step 2."""
    faults = standing_pass_faults()
    if faults:
        raise LawViolation(
            "A QUESTION STANDS ON ANOTHER PASS THAN THE RULED ONE (operator "
            "question 27, ruled 2026-09-28): the standing pass is chosen by "
            "pass, not by write time -- the final pass stands whenever one "
            "exists before the start; otherwise the latest early pass:"
            + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE ACTIVATION GATE (operator rulings, 2026-09-24)
# ---------------------------------------------------------------------------
#
# A market forecasts from the fit its latest activation names, and a forecast
# row is stamped with the factor set the CONFIG declares. The two must be one
# set: an activation of fs3 under a config that says fs5 would write rows
# labelled fs5 and computed by fs3, and every curve split on that label would
# be split on a lie. `baseline.load_fit` refuses such a market by name; this
# says so in the gate, for every market at once, on the record's own rows.


def active_fit_faults(conn) -> list[str]:
    """Every market whose active fit is not the factor set the config
    declares for it, in words."""
    from .model import activation

    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                    " AND name = 'fit_activations'").fetchone() is None:
        return []
    faults: list[str] = []
    for row in conn.execute(
            "SELECT DISTINCT sport, market_type FROM fit_activations"
            " ORDER BY sport, market_type").fetchall():
        sport, market_type = row[0], row[1]
        active = activation.active_fit(conn, sport, market_type)
        declared = config.factor_set_version(sport, market_type)
        if active is not None and active["factor_set_version"] != declared:
            faults.append(
                f"{config.SPORT_LABELS.get(sport, sport.upper())} "
                f"{market_type.replace('prop:', '').replace('_', ' ')}: the "
                f"active fit {active['fit_id']} is factor set "
                f"{active['factor_set_version']} and the config declares "
                f"{declared}, so every row it wrote would carry the wrong "
                f"set's name.")
    return faults


def check_every_active_fit_is_the_declared_set(conn) -> None:
    """Refuse a record whose active fit and declared factor set disagree."""
    faults = active_fit_faults(conn)
    if faults:
        raise LawViolation(
            "THE ACTIVE FIT IS ANOTHER FACTOR SET (the activation gate, "
            "2026-09-24): a market forecasts from its activated fit, and "
            "that fit must be the set the config declares:"
            + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE REVERT LIFTS THE HOLD (operator rulings of 2026-09-24)
# ---------------------------------------------------------------------------
#
# "The hold is lifted per market only when that market's active fit is the
# incumbent and its forecasts are from it." Two facts about a record, both
# read here: each market the revert lifted forecasts from the incumbent the
# revert named, and every statistical forecast the page shows -- for those
# four and for every other market -- came from its market's active fit. The
# gate runs it on its migrated copy of the live record, which is the record
# as it will be once the tree merges: `db.init` has run the revert there.


def _market_words(sport: str, market_type: str) -> str:
    return (f"{config.SPORT_LABELS.get(sport, sport.upper())} "
            f"{market_type.replace('prop:', '').replace('_', ' ')}")


def hold_lift_faults(conn) -> list[str]:
    """Each market whose hold the revert lifted, on the record the ruling is
    about, whose active fit is not the incumbent the revert named."""
    from .model import activation

    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                    " AND name = 'fit_activations'").fetchone() is None:
        return []
    faults: list[str] = []
    for (sport, market_type), expected in config.FS5_REVERT.items():
        if (sport, market_type) in config.HELD_MARKETS:
            continue            # still held: nothing was lifted
        if activation.revert_fit_faults(conn, sport, market_type, expected):
            continue            # not the record the ruling is about
        active = activation.active_fit(conn, sport, market_type)
        if active is None or active["fit_id"] != expected["fit_id"]:
            faults.append(
                f"{_market_words(sport, market_type)}: the hold was lifted "
                f"{expected['lifted']} for the revert to fit "
                f"{expected['fit_id']}, and the market's active fit is "
                f"{'none' if active is None else active['fit_id']}.")
    return faults


def page_fit_faults(conn, payloads) -> list[str]:
    """Every statistical forecast a page shows, not withdrawn, that its
    market's active fit did not write (`baseline.is_its_forecast`: the fit,
    applied to the row's own stored values and rung, must give back the
    probability the row stored)."""
    import json as _json

    from .model import activation, baseline

    faults: list[str] = []
    fits: dict[tuple[str, str], tuple] = {}
    for payload in payloads:
        for card in payload.get("cards") or []:
            if card.get("predictor") != "statistical":
                continue
            row = conn.execute(
                "SELECT p.id, p.sport, p.market_type, p.prop_type,"
                "       p.line_asked, p.factor_set_version, p.created_utc,"
                "       p.factors_json"
                "  FROM predictions p WHERE p.id = ?"
                "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
                "                   WHERE v.prediction_id = p.id)",
                (card["prediction_id"],)).fetchone()
            if row is None:
                continue        # withdrawn: not shown as a forecast
            key = baseline.market_key(
                row["sport"], row["prop_type"] if row["market_type"] == "prop"
                else row["market_type"])
            sport, market_type = baseline.split_key(key)
            if (sport, market_type) not in fits:
                active = activation.active_fit(conn, sport, market_type)
                try:
                    fits[(sport, market_type)] = (
                        active["fit_id"] if active else None,
                        baseline.load_fit(conn, key))
                except baseline.NotTrained:
                    fits[(sport, market_type)] = (
                        active["fit_id"] if active else None, None)
            fit_id, fit = fits[(sport, market_type)]
            if fit is not None and baseline.is_its_forecast(
                    fit, _json.loads(row["factors_json"] or "{}"),
                    row["line_asked"], sport, market_type):
                continue
            faults.append(
                f"{_market_words(sport, market_type)}: the page shows "
                f"forecast {row['id']} (written "
                f"{row['created_utc']}, {row['factor_set_version']}), and "
                + (f"the market's active fit {fit_id} does not give back its "
                   f"probability from its own stored factors"
                   if fit is not None else
                   "the market has no active fit it could have come from")
                + ".")
    return faults


def check_the_page_forecasts_from_the_active_fit(conn, payloads) -> None:
    """Refuse a lifted hold whose market is not on its incumbent, and a page
    showing a statistical forecast from a fit that is not its market's
    active fit. `payloads` are the slate pages as `views.week` serves them,
    read for the statistical forecaster."""
    faults = hold_lift_faults(conn) + page_fit_faults(conn, payloads)
    if faults:
        raise LawViolation(
            "A FORECAST ON THE PAGE IS NOT FROM ITS MARKET'S ACTIVE FIT "
            "(operator rulings of 2026-09-24: the hold is lifted per market "
            "only when its active fit is the incumbent and its forecasts are "
            "from it):" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# ONE WAY INTO A DATABASE FILE (schema ruling 6 of 2026-09-24, built
# 2026-09-25): "add a scan that refuses a raw sqlite3.connect to the live
# record path outside the approved handles, with a planting."
# ---------------------------------------------------------------------------
#
# A SCAN OF THE SOURCE CANNOT KNOW WHICH FILE A CALL WILL OPEN. The path is
# an argument, a setting, a string a person typed on a command line -- and
# two tools opened whatever `--database` named with a raw `sqlite3.connect`,
# which could be the operator's record and was read with no reason, no
# `query_only` and nothing under verification to refuse it. So the scan
# refuses EVERY raw open outside `db.connect`: the approved handles are
# `db.connect` for a scratch file, `db.read_only(path, why)` and
# `db.read_the_live_record(why)` for a read, and `db.back_up_the_live_record`
# for a copy. A raw open that genuinely has to stay is named in
# `RAW_CONNECT_EXEMPT` with its dated reason; there were none on the day
# this was written.
#
# WHAT IT DOES NOT SEE: a `sqlite3.connect` written inside a string and run
# by a child process (`plant_a_schema_change_during_the_gate` plants one on
# purpose, against a stand-in), and an ATTACH, which opens a file without
# calling connect at all. FOLLOWUPS has both.
#
# THE SCHEDULER APPLYING THE SCHEMA FROM THE MAIN CHECKOUT STAYS AS IT IS,
# by the same ruling: it opens the record through `db.connect`, which is how
# a release migrates, and only merged code reaches the main checkout.

#: The one place a raw `sqlite3.connect` belongs: the connection factory
#: every approved handle is built on.
RAW_CONNECT_HOME = "gridiron/db.py:connect"

#: Raw opens allowed anywhere else, keyed `path:function` from the
#: repository root, each with a dated reason. Empty when written.
RAW_CONNECT_EXEMPT: dict[str, str] = {}

#: What `sqlite3` calls the two ways to open a file.
_SQLITE_OPENERS = ("connect", "Connection")

#: The SQLite drivers, as a module named at run time would name them.
_SQLITE_DRIVERS = ("sqlite3", "_sqlite3", "apsw")


def _python_files_beside(root: Path) -> list[tuple[str, Path]]:
    """(path from the repository root, file) for the package and, where they
    exist beside it, `tools/` (the plantings included), `tests/` and
    `desktop/`: everything the gate or the operator runs."""
    base = root.parent
    files = [(p.relative_to(base).as_posix(), p) for p in sorted(root.rglob("*.py"))
             if "__pycache__" not in p.parts]
    for extra in ("tools", "tests", "desktop"):
        folder = base / extra
        if folder.is_dir():
            files += [(p.relative_to(base).as_posix(), p)
                      for p in sorted(folder.rglob("*.py"))
                      if "__pycache__" not in p.parts]
    return files


def _enclosing_functions(tree: ast.AST) -> dict[int, str | None]:
    """id() of every node, to the name of the function it sits in."""
    where: dict[int, str | None] = {}

    def visit(node: ast.AST, function: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (child.name if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function)
            where[id(child)] = inner
            visit(child, inner)

    visit(tree, None)
    return where


def _qualified_functions(tree: ast.AST) -> dict[int, str | None]:
    """id() of every node, to the QUALIFIED name of the function it sits in:
    `connect`, `back_up.connect`, `Record.open` (2026-09-25).

    THE EXEMPTION IS THE FACTORY, NOT THE WORD. `RAW_CONNECT_HOME` was
    matched against the bare name of the enclosing function, so a helper
    named `connect` nested anywhere in `db.py` -- inside `back_up`, say --
    opened a database raw under the connection factory's exemption (the
    adversarial review of 3603300). Qualified, only the module-level
    `connect` is `gridiron/db.py:connect`."""
    where: dict[int, str | None] = {}

    def visit(node: ast.AST, function: str | None, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                where[id(child)] = name
                visit(child, name, name + ".")
            elif isinstance(child, ast.ClassDef):
                where[id(child)] = function
                visit(child, function, prefix + child.name + ".")
            else:
                where[id(child)] = function
                visit(child, function, prefix)

    visit(tree, None, "")
    return where


def _in_an_annotation(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """Is `node` inside a type annotation, or the class argument of an
    isinstance or issubclass -- the places naming `sqlite3.Connection`
    opens nothing?"""
    child, parent = node, parents.get(id(node))
    while parent is not None:
        if isinstance(parent, ast.arg) and parent.annotation is child:
            return True
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and parent.returns is child:
            return True
        if isinstance(parent, ast.AnnAssign) and parent.annotation is child:
            return True
        if (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                and parent.func.id in ("isinstance", "issubclass")
                and len(parent.args) == 2 and parent.args[1] is child):
            return True
        if isinstance(parent, (ast.stmt, ast.Call, ast.Lambda)):
            return False
        child, parent = parent, parents.get(id(parent))
    return False


def _names_a_driver(node: ast.AST | None) -> str | None:
    """The driver a constant module name names -- 'sqlite3', 'sqlite3.dbapi2',
    '_sqlite3', 'apsw' -- or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str) \
            and node.value.split(".")[0] in _SQLITE_DRIVERS:
        return node.value
    return None


def raw_connect_faults(root: Path | None = None) -> list[str]:
    """Every raw SQLite open outside `db.connect`, named by file, line and
    function: `sqlite3.connect` under any alias (read, called or handed on),
    `sqlite3.dbapi2.connect`, a call of `sqlite3.Connection`, a `getattr` of
    either, a star import from `sqlite3`, and any import of `apsw`, the other
    driver, or of `_sqlite3`, the one underneath.

    AND EVERY WAY ROUND THOSE THE REVIEW OF 3603300 FOUND (2026-09-25): the
    module bound to another name (`s = sqlite3; s.connect(...)`) or handed
    on as a value at all (`vars(sqlite3)["connect"]`, a `getattr` with a
    computed name); a dunder read off it (`sqlite3.__dict__`); a subclass of
    `sqlite3.Connection`, which opens a file when called -- the class may be
    named only in an annotation or an isinstance; the driver imported at run
    time by a constant name (`importlib.import_module("sqlite3")`,
    `__import__("sqlite3")`, `sys.modules["sqlite3"]`); and a function named
    `connect` nested anywhere in `db.py`, which the exemption, keyed on the
    bare name, let through.

    AND THE DRIVER THROUGH ANOTHER MODULE (2026-09-25, the rehearsal of those
    fixes): every module that imports sqlite3 holds it as an attribute, and
    seven shapes opened a database past the scan that way --
    `db.sqlite3.connect`, `from gridiron.db import sqlite3`,
    `gridiron.db.sqlite3.connect`, `vars(db)["sqlite3"]`,
    `getattr(db, "sqlite3")`, `db.__dict__["sqlite3"]` and
    `sys.modules["gridiron.db"].sqlite3`. An attribute named `sqlite3` is
    now read as the module on any base, a `from ... import sqlite3` from any
    module binds it, and any namespace looked up by a driver's constant name
    (a subscript, `.get`, `getattr`) is refused, as is `_sqlite3` read off
    anything and `getattr(sqlite3, "dbapi2")`.

    AND ANY CALL HANDED A DRIVER'S NAME (2026-09-26, the prover of those
    fixes): the importer was known only by the names it was written with,
    so `import_module` or `__import__` bound to another name first,
    `__import__` read out of the builtins, `importlib.util.find_spec`, and
    `import_module(name="sqlite3")` each opened a database past the scan. A
    constant naming the driver, as any call's argument, is refused now.

    Still unseen, a static scan cannot see them: a module name computed at
    run time, and the class of a live connection (`type(conn)(path)`) --
    FOLLOWUPS."""
    root = config.PACKAGE_ROOT if root is None else Path(root)
    faults: list[str] = []
    for where, path in _python_files_beside(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        modules: set[str] = set()          # names bound to sqlite3 or dbapi2
        openers: dict[str, str] = {}       # name -> "connect" | "Connection"
        importers: set[str] = {"__import__"}   # names that import by string
        loaders: set[str] = set()              # names bound to importlib
        found: list[tuple[ast.AST, str]] = []
        parents = {id(child): node for node in ast.walk(tree)
                   for child in ast.iter_child_nodes(node)}
        # A STAR IMPORT AND THE DRIVER UNDERNEATH (2026-09-25, found proving
        # this scan). `from sqlite3 import *` brings `connect` in under a bare
        # name no import line shows, and `_sqlite3` is the C driver `sqlite3`
        # wraps: each opened a database past the first version. Both are
        # refused at the import, as apsw is.
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top == "sqlite3":
                        modules.add(alias.asname or "sqlite3")
                    elif top == "apsw":
                        found.append((node, "imports apsw, a second SQLite driver"))
                    elif top == "_sqlite3":
                        found.append((node, "imports _sqlite3, the driver "
                                            "underneath sqlite3"))
                    elif top == "importlib":
                        loaders.add(alias.asname or "importlib")
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if top == "apsw":
                    found.append((node, "imports from apsw, a second SQLite driver"))
                elif top == "_sqlite3":
                    found.append((node, "imports from _sqlite3, the driver "
                                        "underneath sqlite3"))
                elif top == "importlib":
                    importers.update(alias.asname or alias.name for alias in node.names
                                     if alias.name == "import_module")
                if top != "sqlite3":
                    # THE DRIVER THROUGH ANOTHER MODULE'S NAMESPACE (2026-09-25,
                    # the rehearsal of the fixes for the review of 3603300):
                    # every module that imports sqlite3 holds it as an
                    # attribute, so `from gridiron.db import sqlite3` binds
                    # the driver as surely as an import line -- and opened a
                    # database past the scan.
                    for alias in node.names:
                        if alias.name in ("sqlite3", "dbapi2"):
                            modules.add(alias.asname or alias.name)
                        elif alias.name in ("_sqlite3", "apsw"):
                            found.append((node, f"imports `{alias.name}`, a "
                                                f"SQLite driver, through "
                                                f"`{node.module or '.'}`"))
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        found.append((node, "imports * from sqlite3, which "
                                            "brings `connect` in under a bare "
                                            "name no import line shows"))
                    elif alias.name == "dbapi2":
                        modules.add(alias.asname or alias.name)
                    elif alias.name in _SQLITE_OPENERS:
                        openers[alias.asname or alias.name] = alias.name

        def is_module(node: ast.AST) -> bool:
            """The driver module, under any name this file gives it -- and,
            from 2026-09-25 (the rehearsal of these fixes), read off ANY
            other module that holds it: `db.sqlite3`, `gridiron.db.sqlite3`,
            `sys.modules["gridiron.db"].sqlite3` each opened a database
            past the scan with `.connect`."""
            if isinstance(node, ast.Name):
                return node.id in modules
            return (isinstance(node, ast.Attribute)
                    and (node.attr == "sqlite3"
                         or (node.attr == "dbapi2" and is_module(node.value))))

        def is_connection(node: ast.AST) -> bool:
            """`sqlite3.Connection`, under any spelling the file imports."""
            if isinstance(node, ast.Attribute):
                return node.attr == "Connection" and is_module(node.value)
            return (isinstance(node, ast.Name)
                    and openers.get(node.id) == "Connection")

        # A MODULE BOUND TO ANOTHER NAME IS THE MODULE (2026-09-25): `s =
        # sqlite3` then `s.connect(...)` opened past the first version. The
        # binding is refused below, and the name is read as the module too.
        grew = True
        while grew:
            grew = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and is_module(node.value):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id not in modules:
                            modules.add(target.id)
                            grew = True
        # A SUBCLASS OF THE CONNECTION OPENS A FILE WHEN IT IS CALLED.
        subclasses = {node.name for node in ast.walk(tree)
                      if isinstance(node, ast.ClassDef)
                      and any(is_connection(base) for base in node.bases)}

        called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for node in ast.walk(tree):
            parent = parents.get(id(node))
            if isinstance(node, ast.Attribute) and is_module(node.value) \
                    and not isinstance(node.ctx, ast.Store):
                if node.attr == "connect":
                    found.append((node, "opens a database with a raw "
                                        "`sqlite3.connect`"))
                elif node.attr.startswith("__"):
                    found.append((node, f"reads `sqlite3.{node.attr}`, which "
                                        f"reaches `connect` round this scan"))
            if is_connection(node) and not isinstance(node.ctx, ast.Store) \
                    and not _in_an_annotation(node, parents):
                spelled = ("`sqlite3.Connection`" if isinstance(node, ast.Attribute)
                           else f"`sqlite3.Connection`, imported as `{node.id}`")
                if id(node) in called:
                    found.append((node, f"opens a database by calling {spelled}"))
                elif isinstance(parent, ast.ClassDef):
                    found.append((node, f"subclasses {spelled}; calling the "
                                        f"subclass `{parent.name}` opens a "
                                        f"database"))
                else:
                    found.append((node, f"hands {spelled} on as a value; "
                                        f"calling it opens a database -- it may "
                                        f"be named only in an annotation or an "
                                        f"isinstance"))
            elif isinstance(node, ast.Name) and node.id in openers \
                    and openers[node.id] == "connect" \
                    and isinstance(node.ctx, ast.Load):
                found.append((node, f"opens a database through "
                                    f"`sqlite3.connect`, imported as `{node.id}`"))
            elif isinstance(node, ast.Name) and node.id in subclasses \
                    and id(node) in called:
                found.append((node, f"opens a database by calling `{node.id}`, "
                                    f"a subclass of `sqlite3.Connection`"))
            if (isinstance(node, ast.Name) or is_module(node)) and is_module(node) \
                    and isinstance(getattr(node, "ctx", None), ast.Load) \
                    and not (isinstance(parent, ast.Attribute) and parent.value is node):
                # THE MODULE AS A VALUE (2026-09-25): bound to another name,
                # passed to `vars`, `getattr` with a name computed at run
                # time -- each reaches `connect` without writing it.
                if (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                        and parent.func.id in ("getattr", "hasattr")
                        and parent.args and parent.args[0] is node):
                    name = (parent.args[1] if len(parent.args) > 1 else None)
                    if not (isinstance(name, ast.Constant)
                            and isinstance(name.value, str)):
                        found.append((node, "reaches an attribute of `sqlite3` "
                                            "through getattr, by a name computed "
                                            "at run time"))
                    elif (name.value in _SQLITE_OPENERS or name.value.startswith("__")
                          or name.value == "dbapi2"):
                        found.append((node, f"reaches `sqlite3.{name.value}` "
                                            f"through getattr"))
                elif isinstance(parent, ast.Assign) and parent.value is node:
                    found.append((node, "binds the `sqlite3` module to another "
                                        "name, whose `connect` opens a database"))
                else:
                    found.append((node, "hands the `sqlite3` module on as a "
                                        "value, whose `connect` opens a database"))
            if isinstance(node, ast.Call) and (node.args or node.keywords):
                func = node.func
                by_name = (
                    (isinstance(func, ast.Name) and func.id in importers)
                    or (isinstance(func, ast.Attribute)
                        and (func.attr == "__import__"
                             or (func.attr == "import_module"
                                 and isinstance(func.value, ast.Name)
                                 and func.value.id in loaders))))
                driver = _names_a_driver(node.args[0]) if node.args else None
                handed = [name for name in (
                    _names_a_driver(arg) for arg in
                    [*node.args, *(k.value for k in node.keywords)]) if name]
                if by_name and driver:
                    found.append((node, f"imports `{driver}` at run time, by "
                                        f"name, round every import line"))
                elif (isinstance(func, ast.Attribute) and func.attr == "get"
                      and isinstance(func.value, ast.Attribute)
                      and func.value.attr == "modules" and driver):
                    found.append((node, f"reaches `{driver}` through "
                                        f"sys.modules"))
                # ANY NAMESPACE, LOOKED UP BY THE DRIVER'S NAME (2026-09-25,
                # the rehearsal of these fixes): `getattr(db, "sqlite3")`,
                # `vars(db).get("sqlite3")` -- another module's copy of the
                # driver, fetched by a constant name.
                elif (isinstance(func, ast.Attribute)
                      and func.attr in ("get", "pop", "setdefault") and driver):
                    found.append((node, f"reaches `{driver}` through a "
                                        f"namespace, by name"))
                elif (isinstance(func, ast.Name) and func.id in ("getattr", "hasattr")
                      and len(node.args) > 1 and _names_a_driver(node.args[1])):
                    found.append((node, f"reaches `{_names_a_driver(node.args[1])}` "
                                        f"through getattr on another module"))
                # ANY CALL HANDED A DRIVER'S NAME (2026-09-26, found by the
                # prover of the 5a' fixes). The importer was recognised only
                # under the names `import_module` and `__import__` were
                # written with, so each of these opened a database unnamed,
                # measured on a scratch tree: `load = importlib.import_module`
                # then `load("sqlite3")`, the same with `builtins.__import__`,
                # `__builtins__["__import__"]("sqlite3")`,
                # `getattr(builtins, "__import__")("sqlite3")`, and
                # `importlib.util.find_spec("sqlite3")`. A constant naming the
                # driver, handed to any call, is how a module is fetched by
                # name; which callee does the fetching the scan cannot know,
                # so it refuses the call, as it refuses the module handed on
                # as a value. The real tree hands the name to no call.
                elif handed:
                    found.append((node, f"hands the name `{handed[0]}` to a "
                                        f"call, which fetches the driver by "
                                        f"name round every import line"))
            elif (isinstance(node, ast.Subscript)
                  and isinstance(node.value, ast.Attribute)
                  and node.value.attr == "modules"
                  and _names_a_driver(node.slice)):
                found.append((node, f"reaches `{_names_a_driver(node.slice)}` "
                                    f"through sys.modules"))
            elif isinstance(node, ast.Subscript) and _names_a_driver(node.slice):
                # `vars(db)["sqlite3"]`, `db.__dict__["sqlite3"]`,
                # `globals()["sqlite3"]` (2026-09-25, the same rehearsal).
                found.append((node, f"reaches `{_names_a_driver(node.slice)}` "
                                    f"through a namespace, by name"))
            if (isinstance(node, ast.Attribute) and node.attr == "_sqlite3"
                    and not isinstance(node.ctx, ast.Store)):
                found.append((node, "reads `_sqlite3`, the driver underneath "
                                    "sqlite3, off another module"))
        functions = _qualified_functions(tree)
        for node, what in found:
            function = functions.get(id(node))
            key = f"{where}:{function}"
            if key == RAW_CONNECT_HOME or key in RAW_CONNECT_EXEMPT:
                continue
            faults.append(
                f"{where}:{node.lineno} ({function or 'module level'}) {what}. "
                f"A raw open cannot say which file it reaches, and any of them "
                f"could be the operator's record. Open it through "
                f"`db.connect` (scratch), `db.read_only(path, why)`, "
                f"`db.read_the_live_record(why)` or "
                f"`db.back_up_the_live_record(target, why)`, or give a dated "
                f"reason in audit.RAW_CONNECT_EXEMPT.")
    return faults


def check_no_raw_connect_to_the_live_record(root: Path | None = None) -> None:
    faults = raw_connect_faults(root)
    if faults:
        raise LawViolation(
            "A RAW SQLITE OPEN GOES ROUND THE APPROVED HANDLES (schema ruling "
            "6 of 2026-09-24: no raw sqlite3.connect to the live record path "
            "outside the approved handles):" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# NO GATED TEST DEPENDS ON ELAPSED REAL TIME (schema ruling 5 of 2026-09-24,
# built 2026-09-25): "The auth backoff test takes an injectable clock instead
# of wall time. No test in the gate may depend on elapsed real time."
# ---------------------------------------------------------------------------
#
# THE FLAKE THAT ASKED FOR THIS. `test_the_backoff_survives_a_restart` held
# only while the fraction of a second in the third failure's stamp plus the
# real time the restart took stayed under one second: the stamps are cut to
# whole seconds and the wait is rounded down, so a two-second penalty had at
# most one second of margin (measured 2026-09-25: 0/60 red idle, 3/3 red with
# a 1.1 s pause at the restart). Under the gate's load it ran out once. Auth
# now reads one clock, a test replaces it with one it moves by hand, and the
# two scans below keep both halves true.
#
# WHAT THE TEST SCAN CANNOT SEE: a test that depends on elapsed time without
# reading a clock itself -- which is exactly what the backoff test did, the
# clock being inside the code under test. `auth_clock_faults` closes that for
# auth; FOLLOWUPS has the general gap.

#: The one function in `gridiron/auth.py` that reads the real clock. Every
#: other time auth needs comes from `auth.clock`, through `auth._now`.
AUTH_CLOCK = "_the_real_clock"

#: Calls on the `time` module that measure elapsed time. A test has no other
#: use for them.
_ELAPSED_CLOCKS = frozenset(
    name + suffix for name in ("time", "monotonic", "perf_counter",
                               "process_time", "thread_time")
    for suffix in ("", "_ns"))

#: The waits and clock reads a gated test may still hold, each with its
#: dated reason: a real timeout, where the waiting IS the thing, and nothing
#: is asserted about how long it took. Keyed `path:function`.
ELAPSED_TIME_EXEMPT: dict[str, str] = {
    "tests/conftest.py:_serve":
        "2026-09-25: waits for the shared server's thread to report it has "
        "started, polling every 50 ms, and fails after 20 s. A real timeout: "
        "the fixture's result is the same at 50 ms or 19 s, and only a "
        "server that never starts reaches the limit",
    "tests/conftest.py:served_fresh":
        "2026-09-25: the same 20 s start-up limit as `_serve`, for the "
        "fixture that starts a server on a world of its own",
}

#: HELD, NOT ALLOWED: the browser tier's fixed waits, by function and how
#: many, as they stood on 2026-09-25 -- a `page.wait_for_timeout` after an
#: action, and one `time.sleep(1.2)` inside a route handler that makes a
#: response late. Whether ruling 5 reaches them is operator question 5 in
#: docs/REPAIR_STATE.md, asked 2026-09-25. Until it is answered none is
#: changed and none may be ADDED: a function holding more than its count
#: here fails by name, and one holding fewer must lower its count, so this
#: register can only shrink.
#: SHRUNK BY THE BOARD MERGE (2026-09-29), from 28 functions and 44 waits to
#: 19 and 27. The board removed `test_the_toggle_is_remembered_for_the_session`
#: with the tier filter, and re-homed eight more onto its own controls under
#: new names, bringing their fixed waits along -- `test_motion.py`'s tab
#: switch, `test_rapid.py`'s two tab tests and `test_tabs.py`'s five. A wait
#: under a new name is an added one, so none was registered again: each was
#: rebuilt on an in-page signal (`tests/conftest.py::wait_for_the_redraw_it_
#: starts`, which takes the panel and a count from this merge), and so were
#: the board's own new ones in `test_board.py`. The entries below are the
#: ones that still stand, each at its count.
ELAPSED_TIME_HELD: dict[str, int] = {
    "tests/test_cards.py:test_the_grid_does_not_re_sort_while_a_slate_is_in_progress": 1,
    "tests/test_empty.py:_nothing_but_the_message": 1,
    "tests/test_empty.py:_open_week": 1,
    "tests/test_empty.py:test_a_sport_with_no_forecasts_shows_nothing_of_the_last_one": 1,
    "tests/test_empty.py:test_a_sport_with_no_forecasts_starts_no_live_poll": 1,
    "tests/test_every_control.py:_open_record": 1,
    "tests/test_every_control.py:test_a_settings_switch_reads_what_it_saved": 3,
    "tests/test_every_control.py:test_every_record_control_asks_or_changes_something": 2,
    "tests/test_every_control.py:test_the_forecaster_picker_fetches_the_tier_table_it_names": 2,
    "tests/test_every_control.py:test_the_market_select_fetches_the_tier_table_it_names": 1,
    "tests/test_hidden.py:_open": 1,
    "tests/test_motion.py:test_reduced_motion_is_the_same_layout_with_no_transition": 2,
    "tests/test_rapid.py:_open_week": 1,
    "tests/test_rapid.py:_select": 1,
    "tests/test_rapid.py:slow": 1,
    "tests/test_rapid.py:test_a_slower_earlier_slate_does_not_take_the_page": 2,
    "tests/test_rapid.py:test_offline_says_so_in_words_and_a_later_success_clears_it": 2,
    "tests/test_settled_line.py:test_the_counts_line_names_the_settled_picks": 2,
    "tests/test_smoke.py:test_the_sport_tabs_are_reachable_and_tappable": 1,
}


def _call_name(node: ast.AST) -> tuple[str | None, str | None]:
    """(what it is called on, what is called) for a call's function."""
    if isinstance(node, ast.Attribute):
        owner = node.value
        return (owner.id if isinstance(owner, ast.Name)
                else owner.attr if isinstance(owner, ast.Attribute) else None,
                node.attr)
    if isinstance(node, ast.Name):
        return None, node.id
    return None, None


def _reads_the_wall_clock(node: ast.AST, owners=frozenset()) -> bool:
    """`datetime.now()`, `.utcnow()`, `.today()`, or this project's
    `utcnow()`: a reading of what time it is now. `owners` are the module's
    own other names for the `datetime` and `date` classes (`_clock_names`)."""
    if not isinstance(node, ast.Call):
        return False
    owner, name = _call_name(node.func)
    return (name in ("now", "utcnow", "today")
            and (owner is None or owner in ("datetime", "date", "db", "dt")
                 or owner in owners or name == "utcnow"))


def _is_a_timedelta(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func)[1] == "timedelta"


@dataclass(frozen=True)
class _ClockNames:
    """What one module calls the clocks: names bound to the `time` and
    `asyncio` modules, bare names imported from them ("tick" ->
    "time.perf_counter"), and other names for the `datetime` and `date`
    classes ("D" -> datetime)."""
    time: frozenset
    asyncio: frozenset
    imported: dict
    owners: frozenset

    def full(self, owner: str | None, name: str | None) -> str | None:
        """"time.monotonic", "asyncio.sleep" and the like for a call, or None."""
        if owner is None and name:
            return self.imported.get(name)
        if owner in self.time:
            return f"time.{name}"
        if owner in self.asyncio:
            return f"asyncio.{name}"
        return None


def _clock_names(tree: ast.AST) -> _ClockNames:
    """Every name a module can read a clock through, from its own imports.

    ONE RESOLUTION FOR BOTH SCANS (2026-09-25, found proving the ruling 5
    build). The tests scan resolved `import time as t` and `from time import
    perf_counter` and the auth scan did not, so `auth_clock_faults` passed
    all three of `t.monotonic()`, `perf_counter()` and, in neither scan,
    `from datetime import datetime as D; D.now()`. Both read the names here.
    """
    time_names = {"time"}
    asyncio_names = {"asyncio"}
    imported: dict[str, str] = {}             # bare name -> "time.sleep" etc.
    owners: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "time":
                    time_names.add(alias.asname or "time")
                elif alias.name == "asyncio":
                    asyncio_names.add(alias.asname or "asyncio")
        elif isinstance(node, ast.ImportFrom) and node.module in ("time", "asyncio"):
            for alias in node.names:
                imported[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for alias in node.names:
                if alias.name in ("datetime", "date") and alias.asname:
                    owners.add(alias.asname)
    return _ClockNames(frozenset(time_names), frozenset(asyncio_names),
                       imported, frozenset(owners))


def _clock_faults_in(tree: ast.AST) -> list[tuple[ast.AST, str]]:
    """Every sleep, fixed browser wait, elapsed-clock reading and real-time
    difference in one test file's syntax tree."""
    names = _clock_names(tree)

    found: list[tuple[ast.AST, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            owner, name = _call_name(node.func)
            full = names.full(owner, name)
            if full in ("time.sleep", "asyncio.sleep"):
                found.append((node, f"sleeps (`{full}`)"))
            elif full and full.startswith("time.") \
                    and full[5:] in _ELAPSED_CLOCKS:
                found.append((node, f"reads the elapsed-time clock (`{full}`)"))
            elif owner is not None and name == "wait_for_timeout":
                found.append((node, "waits a fixed time in the browser "
                                    "(`wait_for_timeout`)"))
        elif isinstance(node, ast.Compare):
            for side in (node.left, *node.comparators):
                if isinstance(side, ast.BinOp) and any(
                        _reads_the_wall_clock(n, names.owners)
                        for n in ast.walk(side)):
                    found.append((node, "compares a time reckoned from the "
                                        "real clock"))
                    break
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) \
                and _reads_the_wall_clock(node.left, names.owners) \
                and not _is_a_timedelta(node.right):
            found.append((node, "measures the real time since an earlier "
                                "reading"))
    return found


def elapsed_time_faults(root: Path | None = None) -> list[str]:
    """Every gated test that waits on or measures the real clock, named by
    file, line and function, less the dated exemptions and the held register.

    Reads `tests/` beside the package. What it refuses: a sleep; a fixed
    wait in the browser; a reading of `time.time`, `monotonic`,
    `perf_counter` and their kin, which only ever measure elapsed time; a
    comparison with a time reckoned from the real clock (`now - start < 5`,
    `now + delta > kickoff`); and a difference between now and an earlier
    reading. Placing a fixture at "now plus two days" is not refused: that
    is a date, and nothing in it waits.
    """
    root = config.PACKAGE_ROOT if root is None else Path(root)
    tests = root.parent / "tests"
    if not tests.is_dir():
        return []
    by_function: dict[str, list[str]] = {}
    for path in sorted(tests.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        where = path.relative_to(root.parent).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        functions = _enclosing_functions(tree)
        for node, what in _clock_faults_in(tree):
            function = functions.get(id(node))
            by_function.setdefault(f"{where}:{function}", []).append(
                f"{where}:{node.lineno} ({function or 'module level'}) {what}")
    faults: list[str] = []
    for key, found in sorted(by_function.items()):
        if key in ELAPSED_TIME_EXEMPT:
            continue
        held = ELAPSED_TIME_HELD.get(key, 0)
        if len(found) <= held:
            continue
        for fault in found:
            faults.append(
                f"{fault}. A test whose result can change with how long the "
                f"machine took is a test that goes red under load and green "
                f"when watched. Move the clock by hand, as test_auth does "
                f"with `auth.clock`, or wait for the event itself"
                + (f" ({held} held for operator question 5 in this "
                   f"function; {len(found)} found)." if held else "."))
    for key, held in sorted(ELAPSED_TIME_HELD.items()):
        found = len(by_function.get(key, []))
        if found < held:
            faults.append(
                f"{key}: audit.ELAPSED_TIME_HELD holds {held} and {found} "
                f"remain. The register only shrinks: lower it to {found}"
                + (" or remove the entry." if not found else "."))
    for key in sorted(ELAPSED_TIME_EXEMPT):
        if key not in by_function:
            faults.append(
                f"{key}: exempt in audit.ELAPSED_TIME_EXEMPT and no longer "
                f"waits on the clock. Remove the entry.")
    return faults


def check_no_test_waits_on_the_clock(root: Path | None = None) -> None:
    faults = elapsed_time_faults(root)
    if faults:
        raise LawViolation(
            "A GATED TEST DEPENDS ON ELAPSED REAL TIME (schema ruling 5 of "
            "2026-09-24: no test in the gate may):" + _NL2 + _NL2.join(faults))


def auth_clock_faults(root: Path | None = None) -> list[str]:
    """Every reading of the real clock in `gridiron/auth.py` outside the one
    function allowed to make it, named by line and function."""
    root = config.PACKAGE_ROOT if root is None else Path(root)
    path = root / "auth.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = _enclosing_functions(tree)
    # UNDER ANY NAME (2026-09-25): the clocks are resolved from auth's own
    # imports, as the tests scan resolves them (`_clock_names`), so an alias
    # of `time`, a clock imported bare, or another name for `datetime` is
    # still a reading of the machine's clock.
    names = _clock_names(tree)
    faults: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        full = names.full(*_call_name(node.func)) or ""
        if not (_reads_the_wall_clock(node, names.owners)
                or (full.startswith("time.") and full[5:] in _ELAPSED_CLOCKS)):
            continue
        function = functions.get(id(node))
        if function == AUTH_CLOCK:
            continue
        faults.append(
            f"gridiron/auth.py:{node.lineno} ({function or 'module level'}) "
            f"reads the real clock itself. Auth reads time through "
            f"`auth._now()`, which asks `auth.clock`; a test replaces that "
            f"clock and moves it by hand, and a reading made anywhere else "
            f"is one the test cannot move, so the backoff it decides runs "
            f"on the machine's speed again.")
    return faults


def check_auth_reads_one_clock(root: Path | None = None) -> None:
    faults = auth_clock_faults(root)
    if faults:
        raise LawViolation(
            "AUTH READS A CLOCK A TEST CANNOT MOVE (schema ruling 5 of "
            "2026-09-24: the auth backoff takes an injectable clock):"
            + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE SCHEMA MATCHES THE RELEASE (schema ruling 1 of 2026-09-24, built
# 2026-09-25)
# ---------------------------------------------------------------------------
#
# The brief: "build a fresh database by migrating from nothing at the
# released commit, and compare its schema object by object ... From then on,
# the gate runs this diff read-only and fails on any difference." And the
# ruling: "The diff check compares after normalising quoting, whitespace,
# comments and column order, and fails on any difference in behaviour."
#
# TWO COMPARISONS, BOTH IN GATE STEP 2. "release": the live record, read
# through the read-only door, against a database `db.init` built from nothing
# with the released commit's own code -- the live record matches the release.
# "tree": the gate's copy of the record, after this tree's `db.init` migrated
# it, against a database this tree built from nothing -- this tree's
# migration makes the record match this tree. The first finds what reached
# the record without a release; the second finds, before a merge, what a
# release would leave behind: every one of the eight below arose that way, an
# ALTER or an edit to a table the record already had, and the first
# comparison could only have seen each after it was released.
#
# THE NORMALISING IS `schema_diff`, the one door; this is the register and
# the rule. A difference not in the register fails by name. A register entry
# that no longer differs fails too, so the register cannot outlive what it
# records: it is emptied by the commit after the dated migration of ruling 2
# runs, and from then on the check fails on any difference at all -- the
# brief's "from then on".


@dataclass(frozen=True)
class RegisteredDifference:
    """A difference in behaviour the gate knows about, with where it came
    from and what clears it. Matched by object, property and side exactly,
    so a second difference in a registered table is still new."""
    object: str
    property: str
    #: "record" or "reference": the side that has the property.
    held_by: str
    #: The commit that introduced the reference's definition.
    released_in: str
    #: Which of `SCHEMA_COMPARISONS` measures it.
    comparisons: tuple[str, ...]
    registered: str
    cleared_by: str


#: The two comparisons: what is checked, and what it is checked against.
SCHEMA_COMPARISONS: dict[str, tuple[str, str]] = {
    "release": ("the live record", "the release"),
    "tree": ("the gate's migrated copy of the record", "this tree"),
}

_CLEARED_BY_RULING_2 = "cleared by the dated migration of ruling 2"

#: THE DIFFERENCES THE LIVE RECORD HOLDS, measured 2026-09-24 and again
#: 2026-09-25 (live record read through the read-only door at 03:48Z,
#: against a fresh `db.init` of master fddd61b): eight in behaviour, each the
#: released definition's CHECK or DEFAULT that the record's copy of the
#: table does not have, because the column reached the record by ALTER or
#: the definition changed after the table existed. Every stored row already
#: satisfies every released constraint (measured the same day). The dated
#: migration of ruling 2 (`tools/migrate_2026_09_25_behaviour.py`) rebuilds
#: the eight tables to the released definitions; it runs on the live record
#: after the release that carries it, with a verified backup, by the
#: operator. The commit after it runs empties this register.
#:
#: EMPTIED 2026-09-26 (5b). The migration ran on the live record at
#: 2026-09-26T02:12:57Z from the released f4c4db2, after a verified backup
#: (var/gridiron.db.pre-behaviour-migration-2026-09-26.bak: 60 tables,
#: 1,191,063 rows, every count, column checksum and schema object equal):
#: all eight tables rebuilt and verified in one transaction, every column's
#: exact checksum equal before and after, sequences carried, foreign_key_check
#: 0 rows, the write lock held 3.52 s. From this commit on, any difference in
#: behaviour between the record and the release fails the gate by name -- the
#: brief's "from then on". The eight entries are kept below as history, not
#: as a register.
#:
#: THE NINTH IS GONE (2026-09-25). The record's `spread_sign_source`, which
#: the release's `schema.sql` did not declare, was registered for the
#: release comparison until schema ruling 3 was released; 3603300 carried
#: the declaration, every gate from then on reported the entry "CLEARED,
#: STILL REGISTERED", and the next commit -- item 4, the prompt record --
#: removed it, as the register's own rule requires.
_SPORTS_CHECK = "column sport: check (sport in ('nfl', 'mlb', 'nba', 'cfb', 'ufc'))"
_BOTH = ("release", "tree")

SCHEMA_DIFFERENCES_REGISTERED: tuple[RegisteredDifference, ...] = ()

#: What the register held until the migration cleared it, kept so a reader of
#: the enforcement can see what the gate once tolerated and why. Nothing reads
#: it as a register.
SCHEMA_DIFFERENCES_CLEARED_2026_09_26: tuple[RegisteredDifference, ...] = (
    RegisteredDifference(
        "table factors", _SPORTS_CHECK, "reference",
        "9c0bc64 (its five sports from b09e1c2); the record's column came by "
        "the CHECK-less ALTER in db.MIGRATIONS", _BOTH, "2026-09-25",
        _CLEARED_BY_RULING_2),
    RegisteredDifference(
        "table factor_scores", _SPORTS_CHECK, "reference",
        "9c0bc64 (its five sports from b09e1c2); the record's column came by "
        "the CHECK-less ALTER in db.MIGRATIONS", _BOTH, "2026-09-25",
        _CLEARED_BY_RULING_2),
    RegisteredDifference(
        "table model_fits", _SPORTS_CHECK, "reference",
        "9c0bc64 (its five sports from b09e1c2); the record's column came by "
        "the CHECK-less ALTER in db.MIGRATIONS", _BOTH, "2026-09-25",
        _CLEARED_BY_RULING_2),
    RegisteredDifference(
        "table market_snapshots",
        "column kind: check (kind in ('open_at_predict', 'near_start'))",
        "reference",
        "2d0e98f; the record's column came by the CHECK-less ALTER in "
        "lines.SNAPSHOT_MIGRATIONS", _BOTH, "2026-09-25", _CLEARED_BY_RULING_2),
    RegisteredDifference(
        "table mlb_lineups",
        "column source: check (source in ('live', 'backfill'))", "reference",
        "8002a38; the record's column came by the CHECK-less ALTER in "
        "db.MIGRATIONS", _BOTH, "2026-09-25", _CLEARED_BY_RULING_2),
    RegisteredDifference(
        "table prediction_ranks",
        "column on_shortlist: check (on_shortlist in (0, 1))", "reference",
        "63d998c; the record's column came by the CHECK-less ALTER in "
        "db.MIGRATIONS", _BOTH, "2026-09-25", _CLEARED_BY_RULING_2),
    RegisteredDifference(
        "table ufc_events",
        "column event_tier: check (event_tier is null or event_tier in "
        "('numbered', 'fight_night', 'contender'))", "reference",
        "c78af51 (and bdfaddc, which moved it); the record's column came by "
        "the CHECK-less ALTER in db.MIGRATIONS", _BOTH, "2026-09-25",
        _CLEARED_BY_RULING_2),
    RegisteredDifference(
        "table nba_injuries", "column player_name: default ''", "record",
        "719004d, which declared the column with no default; the record's "
        "came by the ALTER in db.MIGRATIONS, and SQLite requires a default "
        "to add a NOT NULL column", _BOTH, "2026-09-25", _CLEARED_BY_RULING_2),
)


def schema_difference_faults(record, reference, comparison: str,
                             register=None) -> tuple[list[str], str]:
    """(faults, summary) for one comparison: every difference in behaviour
    not in the register, and every registered one no longer found."""
    from . import schema_diff

    record_label, reference_label = SCHEMA_COMPARISONS[comparison]
    register = SCHEMA_DIFFERENCES_REGISTERED if register is None else register
    expected = {(r.object, r.property, r.held_by): r for r in register
                if comparison in r.comparisons}
    result = schema_diff.compare(record, reference)
    measured = {(d.object, d.property, d.held_by): d for d in result.differences}
    faults = []
    for key in sorted(set(measured) - set(expected)):
        faults.append(
            "NEW: " + measured[key].words(record_label, reference_label)
            + ". Nothing registers it. Find where it came from: a record "
              "changed by code that was never released, or a release whose "
              "migration leaves the record short of its own schema.")
    for key in sorted(set(expected) - set(measured)):
        entry = expected[key]
        faults.append(
            "CLEARED, STILL REGISTERED: "
            + schema_diff.Difference(*key).words(record_label, reference_label)
            + f" -- no longer found (registered {entry.registered}, "
              f"{entry.cleared_by}). Remove it from "
              f"audit.SCHEMA_DIFFERENCES_REGISTERED.")
    summary = (f"{len(result.cosmetic)} objects differ only in quoting, "
               f"whitespace, comments or column order; "
               f"{len(expected)} registered difference(s) outstanding")
    return faults, summary


def check_the_schema_matches(record, reference, comparison: str,
                             register=None) -> str:
    """Raise naming every difference in behaviour between the record's
    schema and the reference's that the register does not hold, and every
    registered one that is gone. Returns the summary line when it passes."""
    faults, summary = schema_difference_faults(record, reference, comparison,
                                               register)
    if faults:
        record_label, reference_label = SCHEMA_COMPARISONS[comparison]
        raise LawViolation(
            f"{record_label.upper()} DOES NOT MATCH {reference_label.upper()} "
            f"(schema ruling 1 of 2026-09-24): {len(faults)} fault(s); the "
            f"first is {faults[0]}" + _NL2 + _NL2.join(faults))
    return summary


# ---------------------------------------------------------------------------
# THE PROMPT RECORD (the ruling of 2026-09-24, two additions, item 1; the
# ruling on question 4, 2026-09-25)
# ---------------------------------------------------------------------------
#
# "The reasoning pass stores the exact prompt it sent ... with every row it
# writes, append-only. No reasoning row may exist without it." And: "From the
# release onward, every reasoning row must carry kind = "sent" ... The gate
# fails by name on any post-release row without it, and on any row of any
# date with no record at all." The schema is the first lock; a trigger can be
# dropped, so this is the second, checked in the gate on its migrated copy of
# the record once the reconstruction has been applied to it -- the state the
# live record will have once `tools/reconstruct_prompts.py` has run after the
# release.

#: Every rule the schema holds for the prompt record, by name.
PROMPT_RECORD_TRIGGERS = (
    "reasoning_prompts_no_update",
    "reasoning_prompts_no_delete",
    "reasoning_prompts_never_replaced",
    "reasoning_prompt_reconstructed_only_before_the_release",
    "reasoning_row_carries_its_prompt",
    "prompt_record_instant_is_written_once",
    "prompt_record_instant_never_moves",
    "prompt_record_instant_never_removed",
)

#: The one module that writes the table.
PROMPT_RECORD_DOOR = "gridiron/model/prompt_record.py"

_PROMPT_RECORD_INSERT = re.compile(r"\bINTO\s+reasoning_prompts\b", re.IGNORECASE)
_UTC_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def prompt_record_faults(conn) -> list[str]:
    """Every reasoning forecast without the record the rulings require, and
    every record that is not what it says, named one by one."""
    from .model import prompt_record

    objects = {(r[0], r[1]) for r in conn.execute(
        "SELECT type, name FROM sqlite_master")}
    if ("table", "reasoning_prompts") not in objects:
        return ["NO PROMPT RECORD: the database has no reasoning_prompts "
                "table, so no reasoning forecast on it carries its prompt"]
    faults = [f"A RULE OF THE PROMPT RECORD IS MISSING: trigger {name} is not "
              f"on the database. A trigger can be dropped; this is the "
              f"second lock, and it says so by name."
              for name in PROMPT_RECORD_TRIGGERS if ("trigger", name) not in objects]
    instant = prompt_record.binds_from(conn)
    if instant is None or not _UTC_STAMP.fullmatch(instant):
        faults.append(
            f"NO RELEASE INSTANT: meta holds {instant!r} under "
            f"{prompt_record.BINDS_FROM!r}. The first open under the schema "
            f"that ships the rule writes it, once; without it nothing says "
            f"from when a forecast must carry the prompt it was sent.")
        instant = None

    records = {r["id"]: dict(r) for r in conn.execute(
        "SELECT * FROM reasoning_prompts ORDER BY id")}
    rebuilt: dict[int, dict] = {}
    for rec in records.values():
        where = f"prompt record {rec['id']} ({rec['kind']})"
        if prompt_record.digest(rec["request_json"]) != rec["request_sha256"]:
            faults.append(
                f"A PROMPT WHOSE TEXT DOES NOT MATCH ITS HASH: {where}. The "
                f"stored request no longer hashes to the SHA-256 written with "
                f"it, so it is not the request that was recorded.")
        if rec["repair_json"] is not None and (
                prompt_record.digest(rec["repair_json"]) != rec["repair_sha256"]):
            faults.append(
                f"A PROMPT WHOSE TEXT DOES NOT MATCH ITS HASH: {where}, its "
                f"reformatting request.")
        try:
            request = json.loads(rec["request_json"])
            content = request["messages"][0]["content"]
        except (ValueError, TypeError, KeyError, IndexError):
            faults.append(f"A PROMPT THAT IS NOT A REQUEST: {where} holds no "
                          f"user message.")
            continue
        if prompt_record.canonical(request) != rec["request_json"]:
            faults.append(f"A PROMPT NOT IN ITS ONE FORM: {where} is not "
                          f"canonical JSON, so its hash names bytes no other "
                          f"copy of the same request would have.")
        if not str(content).startswith(f"CLAIM: {rec['claim']}"):
            faults.append(f"A PROMPT ABOUT ANOTHER QUESTION: {where} does not "
                          f"open with the claim it records.")
        if rec["kind"] == prompt_record.KIND_RECONSTRUCTED:
            rebuilt[rec["prediction_id"]] = rec

    cited: dict[int, list[int]] = {}
    forecasts = conn.execute(
        "SELECT id, created_utc, sport, market_type, game_id, factors_json"
        "  FROM predictions WHERE predictor = 'llm' ORDER BY id").fetchall()
    for row in forecasts:
        try:
            payload = json.loads(row["factors_json"])
        except (TypeError, ValueError):
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        cite = payload.get(prompt_record.CITE)
        claim = (payload.get("question") or {}).get("claim")
        where = (f"reasoning forecast {row['id']} ({row['sport']} "
                 f"{row['market_type']}, written {row['created_utc']})")
        sent = records.get(cite) if isinstance(cite, int) else None
        if cite is not None:
            cited.setdefault(cite, []).append(row["id"])
        kept = (sent is not None and sent["kind"] == prompt_record.KIND_SENT
                and sent["game_id"] == row["game_id"] and sent["claim"] == claim
                and (sent["sent_utc"] or "") <= row["created_utc"])
        after = instant is not None and row["created_utc"] >= instant
        if after and not kept:
            faults.append(
                f"WRITTEN AFTER THE RELEASE WITHOUT THE PROMPT IT WAS SENT: "
                f"{where} is at or after the release instant {instant} and "
                f"carries no sent record of its own game and claim"
                + (f" (it cites {cite!r})." if cite is not None else "."))
        elif not kept and row["id"] not in rebuilt:
            faults.append(
                f"NO PROMPT RECORD AT ALL: {where} has neither the prompt it "
                f"was sent nor a reconstruction"
                + (f" (it cites {cite!r}, which is no sent record of its "
                   f"own)." if cite is not None else "."))
        if row["id"] in rebuilt and (after or kept):
            faults.append(
                f"A RECONSTRUCTION WHERE THE PROMPT SENT IS KEPT OR OWED: "
                f"{where} has a reconstructed record, and "
                + ("was written after the release." if after
                   else "carries the prompt it was sent."))
    for cite, ids in cited.items():
        if len(ids) > 1:
            faults.append(f"ONE PROMPT FOR TWO FORECASTS: prompt record {cite} "
                          f"is cited by reasoning forecasts {ids}.")
    ids = {row["id"] for row in forecasts}
    for pid, rec in rebuilt.items():
        if pid not in ids:
            faults.append(f"A RECONSTRUCTION OF NO REASONING FORECAST: prompt "
                          f"record {rec['id']} names forecast {pid}.")
    return faults


def check_every_reasoning_row_has_its_prompt(conn) -> None:
    faults = prompt_record_faults(conn)
    if faults:
        raise LawViolation(
            "A REASONING FORECAST WITHOUT ITS PROMPT RECORD (the rulings of "
            "2026-09-24 and 2026-09-25): " + f"{len(faults)} fault(s); the "
            f"first is {faults[0]}" + _NL2 + _NL2.join(faults))


def prompt_record_door_faults(root: Path | None = None) -> list[str]:
    """Every statement outside the one door that writes the prompt record,
    in the package and the tools. The plantings write around it on purpose,
    to prove the schema refuses them, and are not read."""
    root = config.REPO_ROOT if root is None else Path(root)
    faults = []
    for base in ("gridiron", "tools"):
        for path in sorted((root / base).rglob("*.py")):
            where = path.relative_to(root).as_posix()
            if where == PROMPT_RECORD_DOOR or where.startswith("tools/guards/"):
                continue
            text = _python_without_comments(path.read_text(encoding="utf-8"))
            for match in _PROMPT_RECORD_INSERT.finditer(text):
                line = text.count(chr(10), 0, match.start()) + 1
                faults.append(
                    f"{where}:{line} writes the prompt record itself. Every "
                    f"record goes through `model.prompt_record`, which checks "
                    f"the request is one canonical request and hashes it the "
                    f"one way.")
    return faults


def check_the_prompt_record_has_one_door(root: Path | None = None) -> None:
    faults = prompt_record_door_faults(root)
    if faults:
        raise LawViolation("THE PROMPT RECORD WRITTEN ROUND ITS DOOR:" + _NL2
                           + _NL2.join(faults))


def _forecast_entries(payload, path: str = "$"):
    """Every forecast a payload shows a reader: a card, a face, a detail or a
    row of the record -- a dict naming a prediction and carrying its words."""
    if isinstance(payload, dict):
        if "prediction_id" in payload and (
                "reasoning" in payload or "slate_label" in payload
                or "prompt" in payload):
            yield path, payload
        for key, value in payload.items():
            yield from _forecast_entries(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            yield from _forecast_entries(value, f"{path}[{i}]")


def prompt_label_faults(conn, payloads) -> list[str]:
    """A reasoning forecast shown without its prompt disclosure, or with one
    that says something other than what its record is.

    THE RULING'S WORDS: "The page and the Record page show reconstructed rows'
    prompts labelled 'reconstructed' in those words." So the label is read off
    the RECORD's kind, through the one reader, never off the payload's own
    claim about itself: a reconstructed prompt under the sent label, or a
    label that lost the word, is named here.
    """
    from . import language
    from .model import prompt_record

    entries = [(path, e) for payload in payloads
               for path, e in _forecast_entries(payload)]
    ids = sorted({e["prediction_id"] for _p, e in entries
                  if isinstance(e.get("prediction_id"), int)})
    if not ids:
        return []
    predictor = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        predictor.update({r[0]: r[1] for r in conn.execute(
            f"SELECT id, predictor FROM predictions WHERE id IN "
            f"({','.join('?' * len(chunk))})", chunk)})
    records = prompt_record.records_for(conn, ids)
    faults = []
    for path, entry in entries:
        pid = entry.get("prediction_id")
        if predictor.get(pid) != "llm":
            continue
        block = entry.get("prompt")
        record = records.get(pid)
        kind = record["kind"] if record else None
        where = f"{path} (reasoning forecast {pid})"
        if not isinstance(block, dict):
            faults.append(f"A REASONING FORECAST SHOWN WITHOUT ITS PROMPT: "
                          f"{where} carries no prompt disclosure.")
            continue
        label = str(block.get("label") or "")
        if block.get("kind") != kind or label != language.prompt_label(kind):
            faults.append(
                f"A PROMPT LABELLED AS SOMETHING IT IS NOT: {where} is "
                f"labelled {label!r} as {block.get('kind')!r}; its record is "
                f"{kind!r}, labelled {language.prompt_label(kind)!r}.")
        if kind == prompt_record.KIND_RECONSTRUCTED and (
                "reconstructed" not in label.lower()):
            faults.append(
                f"A RECONSTRUCTED PROMPT NOT LABELLED RECONSTRUCTED: {where} "
                f"reads {label!r}. The ruling of 2026-09-25 asks for the word "
                f"'reconstructed', in those letters.")
        if kind != prompt_record.KIND_RECONSTRUCTED and "reconstructed" in label.lower():
            faults.append(f"A PROMPT CALLED RECONSTRUCTED THAT IS NOT: {where} "
                          f"reads {label!r}.")
        for text in (label, str(block.get("note") or "")):
            for fault in (plain_words_violations(text) + advice_word_faults(text)
                          + pressure_word_faults(text)):
                faults.append(f"{where}: {fault}")
    return faults


def check_the_prompt_says_what_it_is(conn, payloads) -> None:
    faults = prompt_label_faults(conn, payloads)
    if faults:
        raise LawViolation(
            "A PROMPT DISCLOSURE THAT DOES NOT SAY WHAT ITS PROMPT IS (the "
            "ruling of 2026-09-25): " + f"{len(faults)} fault(s); the first "
            f"is {faults[0]}" + _NL2 + _NL2.join(faults))


# ---------------------------------------------------------------------------
# NO WRITE REPLACES A ROW OF AN APPEND-ONLY TABLE (operator question 15,
# ruled 2026-09-27, third set; built the same day, after the predictions
# rules): "one gate scan that refuses INSERT OR REPLACE, REPLACE and ON
# CONFLICT DO UPDATE against every append-only table; any legitimate upsert
# (cache, derived table) is named in a register that may only shrink."
# ---------------------------------------------------------------------------
#
# WHY A SCAN AS WELL AS THE RULES. A table's no-delete rule does not run for
# a row SQLite removes to make room for a replacing write (unless recursive
# triggers are on), so every append-only table without a replace rule of its
# own could lose a stored row to one statement -- sixteen of the twenty with
# a delete rule when question 15 was asked. The rules on `predictions`,
# `recommendations` and `market_snapshots` refuse it when it runs; this
# refuses the statement where it is written, for every table the schema
# protects, before it can run at all.
#
# WHAT IT READS, from the syntax tree: every string the package, `tools/`
# and `desktop/` can hand SQLite -- constants, implicit concatenations, `+`
# joins, f-strings, `%` and `.format` templates, whether passed to execute,
# executemany or executescript or kept in a variable -- with every part
# worked out at run time read as unknown; and every `.sql` file in the
# package, `schema.sql` among them. Tests and `tools/guards/` are outside
# it: they write scratch worlds, and they are how the rules are proved.
# Docstrings are prose and are not read (the precedent of every source scan
# here). The SQL is read as SQL: case, whitespace and comments are not
# words, a quoted name is the name, and a string literal is data.
#
# WHAT IT FINDS: an insert under OR REPLACE, a REPLACE statement, an update
# under OR REPLACE (the stricter default: the hole question 13 closed), an
# upsert whose conflict clause updates the stored row, and a table or column
# key declared to replace on conflict, which makes every plain insert on it
# a replacing one. And where a part worked out at run time sits in the place
# a conflict clause goes -- after INSERT or INSERT OR, after UPDATE OR or
# UPDATE before the table, after a conflict target, or as a statement's
# whole verb -- the write is counted as one that replaces, since the scan
# cannot say it is not.
#
# WHICH TABLES ARE APPEND-ONLY is read from the schema, never from a list:
# every table a rule refuses a delete or an update on (a DELETE or UPDATE
# rule, whatever its timing). A replacing write aimed at one fails by name,
# registered or not; so does one whose table the scan cannot read, which is
# counted as aimed at one (the brief's reading). A write under an OR clause
# is also aimed at every table a rule on its table writes, because the rule's
# own writes inherit the clause (measured by question 15's prover). Any
# other replacing write fails unless `UPSERTS_REGISTERED` names it; a
# registered entry no longer found, registered twice over, naming an
# append-only table, or carrying no dated reason fails too, so the register
# only shrinks.
#
# AND FROM ITS PROVER (2026-09-27), each measured getting round the scan as
# first built: a TEMPLATE is read as one wherever it is filled in -- `{...}`,
# `%s`, `%(name)s`, `$name` are parts worked out at run time in every string
# (kept in a variable and formatted later, handed to `str.format`, a
# `string.Template`, an f-string's `{{}}`), and a `.replace` of a constant is
# read as done; a part worked out at run time after the table is a statement
# going on (`INSERT {clause} INTO predictions {cols} VALUES ...`); OR REPLACE
# anywhere a statement could begin it -- a string of its own, after a part
# worked out at run time (`INSERT {hint} OR REPLACE`, `{verb} OR REPLACE`) --
# is a replacing clause; so is INSERT OR or UPDATE OR where the string ends,
# `UPDATE {clause} {table} SET`, a verb worked out at run time after another
# such part, an insert that ends at its ON CONFLICT, and a DO UPDATE with no
# ON CONFLICT before it in its string (the upsert's other half). And a
# FOREIGN KEY'S ACTION is a write too: SQLite's CASCADE, SET NULL or SET
# DEFAULT rewrites the child when a replacing write removes or changes its
# parent row (measured: SET NULL rewrote an append-only child's key, its
# update rule naming another column), so a replacing write is also aimed at
# every table a key action on its table writes. And the register "may only
# shrink" in the ruling's words: an entry not among those frozen on
# 2026-09-27 fails, so a later upsert cannot be registered.
#
# NOT SEEN: a statement built where the scan reads no string of it -- a
# name read from a file, the environment or the record, pieces of a list
# joined at run time, a constant holding the bare verb (indistinguishable
# from Python's own `errors="replace"`), a docstring handed to SQLite
# through `__doc__`, a `.replace` whose old text is worked out at run time
# -- and a table part worked out at run time in a plain update (`UPDATE
# {table} SET`), which could carry a conflict clause the scan cannot read;
# and a connection's own settings, which no statement shows (FOLLOWUPS).

#: THE REGISTER OF LAWFUL UPSERTS (question 15, 2026-09-27). Each is a cache
#: of an upstream source or a table derived from one, refreshed in place,
#: which the schema gives no no-delete or no-update rule. Keyed (file from the
#: repository root, the qualified function the statement is written in, the
#: table), each with a dated reason in words. One entry per statement; it
#: only shrinks.
UPSERTS_REGISTERED: dict[tuple[str, str, str], str] = {
    ("gridiron/data/cfb_loader.py", "load_season", "games"):
        "2026-09-27: the college schedule and scores as ESPN publishes them, "
        "refreshed as games are played; a mirror of the source, not a record "
        "of anything this project said",
    ("gridiron/data/cfb_loader.py", "load_teams", "teams"):
        "2026-09-27: club names read from the feed, dated and sourced, "
        "refreshed when the feed changes them",
    ("gridiron/data/loader.py", "load_games", "games"):
        "2026-09-27: the NFL schedule and scores as nflverse publishes them, "
        "refreshed as games are played",
    ("gridiron/data/loader.py", "load_games", "game_conditions"):
        "2026-09-27: rest, venue and observed weather from the same schedule "
        "file, refreshed with it",
    ("gridiron/data/loader.py", "load_games", "market_lines_raw"):
        "2026-09-27: the latest published line per game from the same file; "
        "a cache of the source -- what a forecast was compared with is "
        "written once in `market_snapshots`",
    ("gridiron/data/loader.py", "load_player_stats", "player_week_stats"):
        "2026-09-27: players' weekly stat lines as nflverse publishes them, "
        "corrected in place when the source corrects them",
    ("gridiron/data/loader.py", "load_injuries", "injuries"):
        "2026-09-27: the current injury report, current state by the "
        "schema's own words; its history is `injury_reports`, stamped and "
        "written once",
    ("gridiron/data/loader.py", "rebuild_team_week_stats", "team_week_stats"):
        "2026-09-27: derived from `games`, rebuilt from it",
    ("gridiron/data/loader.py", "load_snap_counts", "snap_counts"):
        "2026-09-27: snap shares as the source publishes them, refreshed "
        "from it",
    ("gridiron/data/mlb_loader.py", "_write_game", "games"):
        "2026-09-27: the MLB schedule and scores as the league's API "
        "publishes them, refreshed as games are played",
    ("gridiron/data/mlb_loader.py", "_write_game", "game_conditions"):
        "2026-09-27: the ballpark from the same schedule, refreshed with it",
    ("gridiron/data/mlb_loader.py", "_write_game", "mlb_probables"):
        "2026-09-27: the announced starters, current state from the "
        "schedule, which changes them until first pitch",
    ("gridiron/data/mlb_loader.py", "_write_game", "mlb_team_games"):
        "2026-09-27: each club's result, derived from the same game, "
        "refreshed with it",
    ("gridiron/data/mlb_loader.py", "load_pitcher_logs", "mlb_pitcher_starts"):
        "2026-09-27: pitchers' game logs as the league's API publishes them, "
        "refreshed from it",
    ("gridiron/data/mlb_loader.py", "load_lineups", "mlb_lineups"):
        "2026-09-27: the posted batting order, the latest by the schema's own "
        "words; every capture is kept, stamped, in `lineup_captures`",
    ("gridiron/data/mlb_loader.py", "load_batter_logs", "mlb_batter_games"):
        "2026-09-27: batters' game logs as the league's API publishes them, "
        "refreshed from it",
    ("gridiron/data/mlb_loader.py", "load_people", "mlb_people"):
        "2026-09-27: names and handedness as the league's API publishes "
        "them, a cache of the source",
    ("gridiron/data/nba_loader.py", "load_schedule", "games"):
        "2026-09-27: the NBA schedule and scores as ESPN publishes them, "
        "refreshed as games are played",
    ("gridiron/data/nba_loader.py", "load_schedule", "game_conditions"):
        "2026-09-27: the arena from the same schedule, refreshed with it",
    ("gridiron/data/nba_loader.py", "load_team_games", "nba_team_games"):
        "2026-09-27: the league's team game log, refreshed from it",
    ("gridiron/data/nba_loader.py", "load_player_games", "nba_player_games"):
        "2026-09-27: the league's player game log, refreshed from it",
    ("gridiron/data/nba_loader.py", "load_injuries", "nba_injuries"):
        "2026-09-27: the current injury report, which the schema calls a "
        "snapshot replaced on each fetch rather than a history",
    ("gridiron/data/sources.py", "fetch", "http_cache"):
        "2026-09-27: the cache of every upstream fetch, by address",
    ("gridiron/data/teams.py", "load_teams", "teams"):
        "2026-09-27: club names read from the feed, dated and sourced, "
        "refreshed when the feed changes them",
    ("gridiron/data/ufc_loader.py", "load_season", "ufc_events"):
        "2026-09-27: the cards as ESPN publishes them, refreshed from it",
    ("gridiron/data/ufc_loader.py", "_load_bout", "ufc_bouts"):
        "2026-09-27: the bouts and their results as ESPN publishes them, "
        "refreshed as they are fought",
    ("gridiron/data/ufc_loader.py", "_load_fighter", "ufc_fighters"):
        "2026-09-27: fighters' measured attributes as ESPN publishes them, "
        "refreshed from it",
    ("gridiron/data/weather.py", "fetch_week", "weather_forecasts"):
        "2026-09-27: the latest forecast for a game, current state by the "
        "schema's own words; what was forecast into a prediction is frozen "
        "in its factors",
    ("gridiron/market/crosswalk.py", "_write", "player_crosswalk"):
        "2026-09-27: the measured bridge between two sources' player ids, "
        "measured again from the sources and dated each time",
    ("gridiron/market/espn.py", "fetch_day", "market_lines_raw"):
        "2026-09-27: the latest published line per game; a cache of the "
        "source -- what a forecast was compared with is written once in "
        "`market_snapshots`",
    ("gridiron/market/props.py", "fetch_day", "market_prop_lines_raw"):
        "2026-09-27: the latest published prop lines; a cache of the source "
        "-- what a forecast was compared with is written once in "
        "`market_snapshots`",
    ("gridiron/market/ufc.py", "fetch_for_bouts", "market_lines_raw"):
        "2026-09-27: the latest published line per bout; a cache of the "
        "source -- what a forecast was compared with is written once in "
        "`market_snapshots`",
    ("gridiron/model/ufc_rating.py", "walk_forward", "ufc_ratings"):
        "2026-09-27: derived from the bouts, walked forward again from them",
    ("gridiron/sports/ufc.py", "mirror_bouts", "games"):
        "2026-09-27: the bouts mirrored into the schedule, derived from "
        "`ufc_bouts` and refreshed from it",
    ("gridiron/views.py", "mark_seen", "session_seen"):
        "2026-09-27: when a browser session last read a sport's digest, a "
        "marker for what is new since, not a record",
}

#: THE REGISTER AS IT WAS FROZEN (question 15's prover, 2026-09-27). "A
#: register that may only shrink": an entry of `UPSERTS_REGISTERED` not
#: among these fails by name, so an upsert written after this date cannot
#: be registered -- it is written plainly, or the operator rules. Until then
#: a new upsert with an entry dated 2026-09-27 passed every check. Never
#: added to; an entry left here after its upsert goes holds nothing.
UPSERTS_REGISTERED_ON_2026_09_27: frozenset[tuple[str, str, str]] = frozenset({
    ("gridiron/data/cfb_loader.py", "load_season", "games"),
    ("gridiron/data/cfb_loader.py", "load_teams", "teams"),
    ("gridiron/data/loader.py", "load_games", "games"),
    ("gridiron/data/loader.py", "load_games", "game_conditions"),
    ("gridiron/data/loader.py", "load_games", "market_lines_raw"),
    ("gridiron/data/loader.py", "load_player_stats", "player_week_stats"),
    ("gridiron/data/loader.py", "load_injuries", "injuries"),
    ("gridiron/data/loader.py", "rebuild_team_week_stats", "team_week_stats"),
    ("gridiron/data/loader.py", "load_snap_counts", "snap_counts"),
    ("gridiron/data/mlb_loader.py", "_write_game", "games"),
    ("gridiron/data/mlb_loader.py", "_write_game", "game_conditions"),
    ("gridiron/data/mlb_loader.py", "_write_game", "mlb_probables"),
    ("gridiron/data/mlb_loader.py", "_write_game", "mlb_team_games"),
    ("gridiron/data/mlb_loader.py", "load_pitcher_logs", "mlb_pitcher_starts"),
    ("gridiron/data/mlb_loader.py", "load_lineups", "mlb_lineups"),
    ("gridiron/data/mlb_loader.py", "load_batter_logs", "mlb_batter_games"),
    ("gridiron/data/mlb_loader.py", "load_people", "mlb_people"),
    ("gridiron/data/nba_loader.py", "load_schedule", "games"),
    ("gridiron/data/nba_loader.py", "load_schedule", "game_conditions"),
    ("gridiron/data/nba_loader.py", "load_team_games", "nba_team_games"),
    ("gridiron/data/nba_loader.py", "load_player_games", "nba_player_games"),
    ("gridiron/data/nba_loader.py", "load_injuries", "nba_injuries"),
    ("gridiron/data/sources.py", "fetch", "http_cache"),
    ("gridiron/data/teams.py", "load_teams", "teams"),
    ("gridiron/data/ufc_loader.py", "load_season", "ufc_events"),
    ("gridiron/data/ufc_loader.py", "_load_bout", "ufc_bouts"),
    ("gridiron/data/ufc_loader.py", "_load_fighter", "ufc_fighters"),
    ("gridiron/data/weather.py", "fetch_week", "weather_forecasts"),
    ("gridiron/market/crosswalk.py", "_write", "player_crosswalk"),
    ("gridiron/market/espn.py", "fetch_day", "market_lines_raw"),
    ("gridiron/market/props.py", "fetch_day", "market_prop_lines_raw"),
    ("gridiron/market/ufc.py", "fetch_for_bouts", "market_lines_raw"),
    ("gridiron/model/ufc_rating.py", "walk_forward", "ufc_ratings"),
    ("gridiron/sports/ufc.py", "mirror_bouts", "games"),
    ("gridiron/views.py", "mark_seen", "session_seen"),
})

#: A part of a statement worked out when it runs: a formatted value, a name
#: joined on, a `%` or `.format` placeholder. It reads as no SQL at all.
_UNKNOWN_PART = "\x00"

_SQL_LEXEME = re.compile(
    r"(?P<space>\s+)"
    r"|(?P<comment>--[^\n]*|/\*.*?(?:\*/|\Z))"
    r"|(?P<literal>'(?:[^']|'')*(?:'|\Z))"
    r"|(?P<name>\"(?:[^\"]|\"\")*(?:\"|\Z)|`(?:[^`]|``)*(?:`|\Z)|\[[^\]]*(?:\]|\Z))"
    r"|(?P<word>[A-Za-z_][A-Za-z0-9_$]*)"
    r"|(?P<number>[0-9]+(?:\.[0-9]*)?(?:[eE][-+]?[0-9]+)?)"
    r"|(?P<unknown>\x00+)"
    r"|(?P<other>.)",
    re.S)

#: A `%` placeholder in a template the code fills in with `%`.
_PERCENT_PLACEHOLDER = re.compile(r"%(?:\([^)]*\))?[-#0 +]*[0-9*]*(?:\.[0-9*]+)?[a-zA-Z]")

#: A `{...}` placeholder in a template the code fills in with `.format`.
_BRACE_PLACEHOLDER = re.compile(r"\{[^{}]*\}")

#: A placeholder wherever the template is filled in (the prover,
#: 2026-09-27: a template kept in a variable and formatted later was read as
#: punctuation): `{...}` for `.format`, `%s` or `%(name)s` for `%`, `$name`
#: or `${name}` for `string.Template`, holding whatever Python lets them hold
#: (`{: >10}`, a key with a space). The doubled characters that stand for
#: one character (`{{`, `%%`, `$$`) are kept. A placeholder that swallows a
#: statement's words -- `{` in one literal, `}` in another -- loses nothing:
#: the text is read again as written (`_replacing_writes_in`).
_TEMPLATE_PLACEHOLDER = re.compile(
    r"\{\{|\}\}|\{[^{}]*\}"
    r"|%%|%(?:\([^()]*\))?[-#0 +]*[0-9*]*(?:\.[0-9*]+)?[a-zA-Z]"
    r"|\$\$|(?<![A-Za-z0-9_$])\$(?:\{[^{}]*\}|[A-Za-z_][A-Za-z0-9_]*)")


def _placeholders_unknown(text: str) -> str:
    """The text with every template placeholder read as a part worked out at
    run time, of the same length, so a place in it is the same place in the
    text as written."""
    return _TEMPLATE_PLACEHOLDER.sub(
        lambda m: m.group() if m.group() in ("{{", "}}", "%%", "$$")
        else _UNKNOWN_PART * len(m.group()), text)


#: The conflict algorithms that do not replace.
_NOT_REPLACING = frozenset({"ROLLBACK", "ABORT", "FAIL", "IGNORE"})

#: The forms, in words. Never the statements themselves: this module is
#: read by its own scan.
_FORM_INSERT = "an insert under OR REPLACE"
_FORM_REPLACE = "a REPLACE statement"
_FORM_UPDATE = "an update under OR REPLACE"
_FORM_UPSERT = "an upsert whose conflict clause updates the stored row"
_FORM_KEY = "a key declared to replace the stored row whenever an insert meets it"
_FORM_UNREAD = ("a write whose conflict clause is worked out when it runs, "
                "counted as one that replaces")
_FORM_CLAUSE = ("a conflict clause that replaces, its statement's verb apart "
                "from it or worked out when it runs")


@dataclass(frozen=True)
class _SqlToken:
    kind: str       # word, name, literal, number, unknown, other
    word: str       # a word upper-cased; "" for any other kind
    value: str      # a name as SQLite reads it, lower-cased; the text otherwise
    start: int
    end: int


def _sql_tokens(text: str) -> list[_SqlToken]:
    """SQL as SQLite reads it: comments and whitespace dropped, a quoted name
    unquoted, a string literal one token, a part worked out at run time one
    unknown token."""
    tokens: list[_SqlToken] = []
    for m in _SQL_LEXEME.finditer(text):
        kind = m.lastgroup
        raw = m.group()
        if kind in ("space", "comment"):
            continue
        if kind == "word":
            tokens.append(_SqlToken("word", raw.upper(), raw.lower(), m.start(), m.end()))
        elif kind == "name":
            inner = raw[1:-1] if len(raw) > 1 and raw[-1] in "\"`]" else raw[1:]
            if raw[0] in "\"`":
                inner = inner.replace(raw[0] * 2, raw[0])
            tokens.append(_SqlToken("name", "", inner.lower(), m.start(), m.end()))
        else:
            tokens.append(_SqlToken(kind, "", raw, m.start(), m.end()))
    return tokens


def _read_sql_name(tokens: list[_SqlToken], i: int) -> tuple[str | None, int]:
    """The object named at `tokens[i]` -- `t`, `"t"`, `[t]`, `main.t` --
    lower-cased, and the index after it. None where no whole name is there
    to read: a part worked out at run time, in the name or touching it."""
    n = len(tokens)
    while True:
        if i >= n or tokens[i].kind not in ("word", "name"):
            return None, i
        tok = tokens[i]
        touching = ((i > 0 and tokens[i - 1].kind == "unknown"
                     and tokens[i - 1].end == tok.start)
                    or (i + 1 < n and tokens[i + 1].kind == "unknown"
                        and tokens[i + 1].start == tok.end))
        if touching or _UNKNOWN_PART in tok.value:
            return None, i
        if i + 1 < n and tokens[i + 1].kind == "other" and tokens[i + 1].value == ".":
            i += 2
            continue
        return tok.value, i + 1


def _sql_objects(tokens: list[_SqlToken]) -> list[tuple[int, str, str | None, int]]:
    """(index of CREATE, kind, name, index after the name) for every object
    the text creates: a table, a view, an index or a rule."""
    found = []
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok.word != "CREATE":
            continue
        j = i + 1
        while j < n and tokens[j].word in ("TEMP", "TEMPORARY", "UNIQUE", "VIRTUAL"):
            j += 1
        if j >= n or tokens[j].word not in ("TABLE", "VIEW", "INDEX", "TRIGGER"):
            continue
        kind = tokens[j].word.lower()
        j += 1
        if [t.word for t in tokens[j:j + 3]] == ["IF", "NOT", "EXISTS"]:
            j += 3
        name, after = _read_sql_name(tokens, j)
        found.append((i, kind, name, after))
    return found


def _sql_rules(tokens: list[_SqlToken]) -> list[tuple[str | None, str, str | None, set]]:
    """(rule, event, table, tables its body writes) for every rule the text
    creates -- the event DELETE, INSERT or UPDATE, whatever its timing."""
    rules = []
    n = len(tokens)
    for _at, kind, name, k in _sql_objects(tokens):
        if kind != "trigger":
            continue
        if k < n and tokens[k].word in ("BEFORE", "AFTER"):
            k += 1
        elif k + 1 < n and tokens[k].word == "INSTEAD" and tokens[k + 1].word == "OF":
            k += 2
        if k >= n or tokens[k].word not in ("DELETE", "INSERT", "UPDATE"):
            continue
        event = tokens[k].word
        k += 1
        while k < n and tokens[k].word != "ON":
            k += 1                           # UPDATE OF a, b, c
        table, k = _read_sql_name(tokens, k + 1)
        while k < n and tokens[k].word != "BEGIN":
            k += 1
        depth, body, k = 1, set(), k + 1
        while k < n and depth:
            word = tokens[k].word
            if word == "CASE":
                depth += 1
            elif word == "END":
                depth -= 1
            elif word == "INTO":
                body.add(_read_sql_name(tokens, k + 1)[0])
            elif word == "UPDATE" and k + 1 < n and tokens[k + 1].word != "SET":
                step = 3 if tokens[k + 1].word == "OR" else 1
                body.add(_read_sql_name(tokens, k + step)[0])
            k += 1
        rules.append((name, event, table, body))
    return rules


def _sql_key_actions(tokens: list[_SqlToken]) -> list[tuple[str | None, str | None]]:
    """(parent, child) for every foreign key the text declares with an action
    that writes the child when its parent row is removed or changed -- ON
    DELETE or ON UPDATE, then CASCADE, SET NULL, SET DEFAULT, or one worked
    out at run time (question 15's prover, 2026-09-27). The child is the
    table being created or altered; None where either name cannot be read."""
    found = []
    n = len(tokens)
    for r, tok in enumerate(tokens):
        if tok.word != "REFERENCES":
            continue
        parent, k = _read_sql_name(tokens, r + 1)
        depth, writes = 0, False
        while k < n:
            t = tokens[k]
            if t.kind == "other" and t.value == "(":
                depth += 1
            elif t.kind == "other" and t.value == ")":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and (t.word == "REFERENCES"
                                 or (t.kind == "other" and t.value in (",", ";"))):
                break
            elif (depth == 0 and t.word == "ON" and k + 2 < n
                  and tokens[k + 1].word in ("DELETE", "UPDATE")
                  and (tokens[k + 2].word in ("CASCADE", "SET")
                       or tokens[k + 2].kind == "unknown")):
                writes = True
            k += 1
        if not writes:
            continue
        child = None
        k = r
        while k > 0 and not (tokens[k - 1].kind == "other" and tokens[k - 1].value == ";"):
            k -= 1
            if tokens[k].word == "CREATE":
                for at, kind, name, _after in _sql_objects(tokens[k:]):
                    child = name if at == 0 and kind == "table" else None
                    break
                break
            if tokens[k].word == "ALTER" and k + 1 < n and tokens[k + 1].word == "TABLE":
                child = _read_sql_name(tokens, k + 2)[0]
                break
        found.append((parent, child))
    return found


def _replacing_statements(tokens: list[_SqlToken]) -> list[tuple[int, str, str | None, bool]]:
    """(token index, form, table written or None if unreadable, whether a
    rule's own writes inherit its conflict clause) for every replacing write
    in one text."""
    n = len(tokens)

    def word(k: int) -> str | None:
        return tokens[k].word if 0 <= k < n else None

    def unknown(k: int) -> bool:
        return 0 <= k < n and tokens[k].kind == "unknown"

    def punct(k: int, text: str) -> bool:
        return 0 <= k < n and tokens[k].kind == "other" and tokens[k].value == text

    def after_a_name(k: int) -> int:
        """The index after the name at `k`, a part of it or all of it worked
        out at run time: touching words, quoted names and unknown parts,
        joined by dots."""
        def atom(k: int) -> int:
            if k >= n or tokens[k].kind not in ("word", "name", "unknown"):
                return k
            k += 1
            while (k < n and tokens[k].kind in ("word", "name", "unknown")
                   and tokens[k].start == tokens[k - 1].end):
                k += 1
            return k
        k = atom(k)
        while punct(k, "."):
            k = atom(k + 1)
        return k

    def a_statement_goes_on(k: int) -> bool:
        """Does what follows the table at `k` read as an insert's body? A
        part worked out at run time there, or the string ending there with
        the rest added when it runs, counts (question 15's prover,
        2026-09-27: `{cols}` after the table hid a formatted clause)."""
        return (k >= n or unknown(k) or punct(k, "(")
                or word(k) in ("VALUES", "SELECT", "DEFAULT", "WITH", "AS"))

    def a_statement_begins(k: int) -> bool:
        """Could a statement begin at `k`, as far as the text shows: at its
        start, after a `;`, a `)` or BEGIN, or after a part worked out at
        run time (the prover: `{cte} {verb} INTO ...`)?"""
        return (k == 0 or punct(k - 1, ";") or punct(k - 1, ")")
                or word(k - 1) == "BEGIN" or unknown(k - 1))

    def into_ahead(k: int) -> int | None:
        """The index of the first INTO from `k` before the statement ends."""
        while k < n and not punct(k, ";"):
            if word(k) == "INTO":
                return k
            k += 1
        return None

    def into_behind(k: int) -> bool:
        """Is there an INTO before `k` in its statement?"""
        while k > 0:
            k -= 1
            if punct(k, ";"):
                return False
            if word(k) == "INTO":
                return True
        return False

    def aimed_after(k: int) -> str | None:
        """The table a conflict clause ending before `k` is aimed at: the
        name after the next INTO in its statement, or else a name at `k`
        followed by what an update's table is; None where neither reads."""
        into = into_ahead(k)
        if into is not None:
            return _read_sql_name(tokens, into + 1)[0]
        name, after = _read_sql_name(tokens, k)
        return name if word(after) in ("SET", "AS", "INDEXED", "NOT") else None

    def inserted_into(k: int) -> str | None:
        """The table of the insert an upsert clause at `k` belongs to."""
        while k > 0:
            k -= 1
            if punct(k, ";"):
                return None
            if word(k) == "INTO":
                return _read_sql_name(tokens, k + 1)[0]
        return None

    def created_table(k: int) -> str | None:
        """The table whose definition holds the clause at `k`."""
        while k > 0:
            k -= 1
            if punct(k, ";"):
                return None
            if word(k) == "CREATE":
                for at, kind, name, _after in _sql_objects(tokens[k:]):
                    return name if at == 0 and kind == "table" else None
                return None
        return None

    found: list[tuple[int, str, str | None, bool]] = []
    claimed: set[int] = set()        # each DO read with the ON CONFLICT before it
    for i, tok in enumerate(tokens):
        if tok.word == "INSERT":
            # INSERT OR where the string ends is a clause added when it runs
            # (the prover, 2026-09-27).
            if word(i + 1) == "OR" and (word(i + 2) == "REPLACE" or unknown(i + 2)
                                        or i + 2 >= n):
                form = _FORM_INSERT if word(i + 2) == "REPLACE" else _FORM_UNREAD
                table = _read_sql_name(tokens, i + 4)[0] if word(i + 3) == "INTO" else None
                found.append((i, form, table, True))
            elif (unknown(i + 1) and word(i + 2) == "INTO"
                  and a_statement_goes_on(after_a_name(i + 3))):
                found.append((i, _FORM_UNREAD, _read_sql_name(tokens, i + 3)[0], True))
        elif tok.word == "REPLACE" and not punct(i + 1, "("):
            if word(i - 1) == "OR":
                # OR REPLACE with no INSERT or UPDATE just before it: a clause
                # kept in a string of its own, or after a part worked out at
                # run time -- `INSERT {hint} OR REPLACE`, `{verb} OR REPLACE`
                # (the prover, 2026-09-27) -- and followed by SQL: an INTO
                # ahead, an update's table, a part worked out, or the string's
                # end. Not "Keep {what} or replace it" (prose).
                if (word(i - 2) not in ("INSERT", "UPDATE")
                        and (i - 1 == 0 or unknown(i - 2))
                        and (i + 1 >= n or unknown(i + 1)
                             or into_ahead(i + 1) is not None
                             or aimed_after(i + 1) is not None)):
                    found.append((i - 1, _FORM_CLAUSE, aimed_after(i + 1), True))
            elif word(i + 1) == "INTO":
                found.append((i, _FORM_REPLACE, _read_sql_name(tokens, i + 2)[0], True))
            elif (unknown(i + 1) and a_statement_begins(i)
                  and (i + 2 >= n or into_ahead(i + 2) is not None)):
                # `REPLACE {hint} INTO t`, or REPLACE and the rest added when
                # it runs (the prover). Not the bare word: Python's own
                # `errors="replace"` spells it too.
                found.append((i, _FORM_REPLACE, aimed_after(i + 1), True))
        elif tok.word == "UPDATE":
            if word(i + 1) == "OR" and (word(i + 2) == "REPLACE" or unknown(i + 2)
                                        or i + 2 >= n):
                form = _FORM_UPDATE if word(i + 2) == "REPLACE" else _FORM_UNREAD
                found.append((i, form, _read_sql_name(tokens, i + 3)[0], True))
            elif (unknown(i + 1) and i + 2 < n
                  and tokens[i + 2].kind in ("word", "name", "unknown")
                  and word(i + 2) not in ("SET", "AS", "INDEXED", "NOT")
                  and tokens[i + 2].start > tokens[i + 1].end
                  and word(after_a_name(i + 2)) in ("SET", "AS", "INDEXED", "NOT")):
                # `UPDATE {clause} t SET`: the part before the table is where
                # OR REPLACE goes -- and in `UPDATE {clause} {table} SET` too,
                # the table then unread (the prover). (`UPDATE {table} SET`
                # is the table's own name worked out at run time, and is not
                # read here.)
                found.append((i, _FORM_UNREAD, _read_sql_name(tokens, i + 2)[0], True))
        elif tok.word == "ON" and word(i + 1) == "CONFLICT":
            k = i + 2
            if word(k) == "REPLACE":
                found.append((i, _FORM_KEY, created_table(i), False))
                continue
            if word(k) in _NOT_REPLACING:
                continue
            depth, action = 0, None
            while k < n:
                if punct(k, "("):
                    depth += 1
                elif punct(k, ")"):
                    depth -= 1
                elif depth <= 0 and punct(k, ";"):
                    break
                elif depth <= 0 and unknown(k):
                    action = "unknown"
                    break
                elif depth <= 0 and word(k) == "DO":
                    claimed.add(k)
                    action = ("update" if word(k + 1) == "UPDATE"
                              else "unknown" if unknown(k + 1) else None)
                    break
                k += 1
            else:
                # The string ends before the clause says what it does, so the
                # rest is added when it runs: in an insert, or in a piece
                # that begins with the clause (the prover, 2026-09-27).
                if into_behind(i) or i == 0 or unknown(i - 1):
                    action = "unknown"
            if action == "update":
                found.append((i, _FORM_UPSERT, inserted_into(i), False))
            elif action == "unknown":
                table = inserted_into(i) or created_table(i)
                found.append((i, _FORM_UNREAD, table, True))
        elif (tok.word == "DO" and word(i + 1) == "UPDATE" and i not in claimed
              and (word(i + 2) == "SET" or unknown(i + 2) or i + 2 >= n)):
            # An upsert's other half, its ON CONFLICT in another string (the
            # prover, 2026-09-27): DO UPDATE SET is SQL for nothing else, and
            # "we do update the page" is not it.
            found.append((i, _FORM_UPSERT, inserted_into(i), False))
        elif tok.kind == "unknown" and word(i + 1) == "INTO" and a_statement_begins(i):
            if a_statement_goes_on(after_a_name(i + 2)):
                found.append((i, _FORM_UNREAD, _read_sql_name(tokens, i + 2)[0], True))
    return found


def _replacing_writes_in(tokens: list[_SqlToken], text: str, template: bool
                         ) -> list[tuple[int, str, str | None, bool]]:
    """(offset in the text, form, table, inherited) for every replacing
    write in one text. A string of Python is read twice (question 15's
    prover, 2026-09-27): with each template placeholder a part worked out at
    run time -- a template kept in a variable and filled in later is still a
    template -- and as written, for anything the first reading finds nothing
    at the same place; a placeholder keeps its length, so a place is the
    same in both."""
    as_written = [(tokens[i].start, form, table, inherited)
                  for i, form, table, inherited in _replacing_statements(tokens)]
    if not template:
        return as_written
    filled = _sql_tokens(_placeholders_unknown(text))
    found = [(filled[i].start, form, table, inherited)
             for i, form, table, inherited in _replacing_statements(filled)]
    places = {start for start, _form, _table, _inherited in found}
    return found + [w for w in as_written if w[0] not in places]


def _rendered_sql(node: ast.AST, used: set) -> str | None:
    """The text a string expression hands SQLite, each part worked out at
    run time one unknown mark; None if it holds no string at all. The id of
    every node whose text it reads goes into `used`; a part it reads as
    unknown -- a `.format` argument, the values after `%`, a formatted
    expression -- is not, and is read as a string of its own."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bytes):
            # A bytes literal decoded before it is run is a statement too
            # (question 15's prover, 2026-09-27: `b"...".decode()`).
            used.add(id(node))
            return node.value.decode("utf-8", "replace")
        if not isinstance(node.value, str):
            return None
        used.add(id(node))
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif (isinstance(value, ast.FormattedValue)
                  and isinstance(value.value, ast.Constant)
                  and isinstance(value.value.value, str)
                  and value.format_spec is None and value.conversion == -1):
                parts.append(value.value.value)
                used.add(id(value.value))
            else:
                parts.append(_UNKNOWN_PART)
                continue
            used.add(id(value))
        used.add(id(node))
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _rendered_sql(node.left, used), _rendered_sql(node.right, used)
        if left is None and right is None:
            return None
        used.add(id(node))
        return (_UNKNOWN_PART if left is None else left) + (
            _UNKNOWN_PART if right is None else right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        template = _rendered_sql(node.left, used)
        if template is None:
            return None
        used.add(id(node))
        return _PERCENT_PLACEHOLDER.sub(_UNKNOWN_PART, template).replace("%%", "%")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "format":
            template = _rendered_sql(node.func.value, used)
            if template is None:
                return None
            used.update((id(node), id(node.func)))
            template = template.replace("{{", "\x01").replace("}}", "\x02")
            return (_BRACE_PLACEHOLDER.sub(_UNKNOWN_PART, template)
                    .replace("\x01", "{").replace("\x02", "}"))
        if (node.func.attr == "join" and len(node.args) == 1
                and isinstance(node.args[0], (ast.List, ast.Tuple))):
            separator = _rendered_sql(node.func.value, used)
            if separator is None:
                return None
            pieces = [_rendered_sql(e, used) for e in node.args[0].elts]
            used.update((id(node), id(node.func), id(node.args[0])))
            return separator.join(_UNKNOWN_PART if p is None else p for p in pieces)
        if (node.func.attr == "replace" and len(node.args) >= 2
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str) and node.args[0].value):
            # A statement rewritten by `.replace` is read as rewritten, the
            # new text unknown where it is worked out at run time (question
            # 15's prover, 2026-09-27: `.replace("IGNORE", "REPLACE")`).
            text = _rendered_sql(node.func.value, used)
            if text is None:
                return None
            new = _rendered_sql(node.args[1], used)
            used.update((id(node), id(node.func), id(node.args[0])))
            return text.replace(node.args[0].value, _UNKNOWN_PART if new is None else new)
    return None


#: The words every replacing form holds one of, and a foreign key's. A
#: string with none is not tokenised: a quick way past the prose, never a
#: way past a statement.
_REPLACE_SCAN_WORDS = re.compile(
    r"insert|replace|update|conflict|into|trigger|references", re.I)


def _sql_strings_in(tree: ast.AST) -> list[tuple[ast.AST, str]]:
    """Every whole string expression in a module outside its docstrings, as
    SQLite would read it -- a part of a larger one is read inside it."""
    prose = _docstring_nodes(tree)
    inner: set[int] = set()
    found = []
    for node in ast.walk(tree):
        if id(node) in prose or id(node) in inner:
            continue
        used: set[int] = set()
        text = _rendered_sql(node, used)
        if text is None:
            continue
        inner |= used
        found.append((node, text))
    return found


def _shipped_python_files(root: Path) -> list[Path]:
    """Every Python file of the shipped code: the package, `tools/` less
    `tools/guards/`, and `desktop/` (question 15's scope; shared with the
    roster scan from 2026-09-29, so the two read one list)."""
    base = root.parent
    files = [p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts]
    for extra in ("tools", "desktop"):
        folder = base / extra
        if folder.is_dir():
            files += [p for p in sorted(folder.rglob("*.py"))
                      if "__pycache__" not in p.parts
                      and not (extra == "tools"
                               and p.relative_to(folder).parts[0] == "guards")]
    return files


def _replace_scan_sources(root: Path) -> list[tuple[str, str, list]]:
    """(path from the repository root, "python" or "sql", [(line, function,
    tokens, text)]) for the package, `tools/` less `tools/guards/`,
    `desktop/`, and every `.sql` file in the package. A schema file's
    function is None: each finding in it is named by the object that holds
    it."""
    base = root.parent
    sources = []
    for path in _shipped_python_files(root):
        where = path.relative_to(base).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = _qualified_functions(tree)
        texts = []
        for node, text in _sql_strings_in(tree):
            if _REPLACE_SCAN_WORDS.search(text):
                texts.append((node.lineno, functions.get(id(node)) or "module level",
                              _sql_tokens(text), text))
        sources.append((where, "python", texts))
    for path in sorted(root.rglob("*.sql")):
        where = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8")
        sources.append((where, "sql", [(1, None, _sql_tokens(text), text)]))
    return sources


def _the_schemas_rules(sources: list) -> tuple[dict[str, set], dict[str, set]]:
    """({append-only table: the rules that make it so}, {table: the tables
    its rules write}), read from every SQL text the scan reads. An
    append-only table is one a rule refuses a delete or an update on --
    read from the schema, never a list, so a table given such a rule is
    append-only from that commit on. A table a rule writes whose name cannot
    be read is None, never dropped (question 15's prover, 2026-09-27)."""
    protected: dict[str, set] = {}
    writes: dict[str, set] = {}
    for _where, _kind, texts in sources:
        for entry in texts:
            for rule, event, table, body in _sql_rules(entry[2]):
                if table and event in ("DELETE", "UPDATE"):
                    protected.setdefault(table, set()).add(rule or "a rule")
                if table:
                    writes.setdefault(table, set()).update(body)
    return protected, writes


def _the_schemas_key_actions(sources: list) -> dict[str | None, set]:
    """{parent: the tables a foreign key's action writes when a row of the
    parent is removed or changed}, read from every SQL text the scan reads
    (question 15's prover, 2026-09-27). A name that cannot be read is None;
    a parent None is reached from every table."""
    reached: dict[str | None, set] = {}
    for _where, _kind, texts in sources:
        for entry in texts:
            for parent, child in _sql_key_actions(entry[2]):
                reached.setdefault(parent, set()).add(child)
    return reached


def replacing_write_faults(root: Path | None = None,
                           register: dict | None = None,
                           frozen: frozenset | None = None) -> list[str]:
    """Every replacing write the shipped code or the schema can issue that
    aims at an append-only table -- its own, or one its table's rules or a
    foreign key's action writes -- whose table cannot be read, or that the
    register does not name; and every register entry that is stale, doubled,
    undated, names an append-only table, or is not among the entries `frozen`
    holds (operator question 15, ruled 2026-09-27; its prover the same day).
    Each named by file, line, function and table. With the module's own
    register, `frozen` is `UPSERTS_REGISTERED_ON_2026_09_27`."""
    root = config.PACKAGE_ROOT if root is None else Path(root)
    if register is None:
        register = UPSERTS_REGISTERED
        frozen = UPSERTS_REGISTERED_ON_2026_09_27 if frozen is None else frozen
    sources = _replace_scan_sources(root)
    protected, writes = _the_schemas_rules(sources)
    key_writes = _the_schemas_key_actions(sources)

    def aimed_at(table: str, inherited: bool, keys: bool = True) -> set:
        """The table and every table a write on it reaches: through its
        rules' own writes when the conflict clause is inherited, and through
        a foreign key's action whatever the clause. None is a table the scan
        cannot read."""
        seen, queue = {table}, [table]
        while queue:
            current = queue.pop()
            if current is None:
                continue
            reached = set(writes.get(current, ())) if inherited else set()
            if keys:
                reached |= key_writes.get(current, set()) | key_writes.get(None, set())
            for written in reached:
                if written not in seen:
                    seen.add(written)
                    queue.append(written)
        return seen

    def rules_of(table: str) -> str:
        return ", ".join(f"`{r}`" for r in sorted(protected[table]))

    faults: list[str] = []
    found: dict[tuple[str, str, str], list[str]] = {}
    refused: set[tuple[str, str, str]] = set()   # refused above: reaches one
    for where, kind, texts in sources:
        for line, function, tokens, text in texts:
            objects = _sql_objects(tokens) if kind == "sql" else []
            for start, form, table, inherited in _replacing_writes_in(
                    tokens, text, kind == "python"):
                at = line + text.count("\n", 0, start)
                if kind == "sql":
                    holder = [o for o in objects if tokens[o[0]].start <= start]
                    function = (f"{holder[-1][1]} {holder[-1][2]}" if holder
                                else "module level")
                place = f"{where}:{at} ({function})"
                if table is None:
                    faults.append(
                        f"{place} {form}, and the scan cannot read the table "
                        f"it writes -- a part of its name, or all of it, is "
                        f"worked out when it runs -- so it is counted as "
                        f"aimed at an append-only table, which no register "
                        f"entry can hold. Name the table in the statement.")
                    continue
                reached = aimed_at(table, inherited)
                guarded = sorted(t for t in reached if t in protected)
                unread = None in reached
                if guarded or unread:
                    others = [f"`{t}`" for t in guarded if t != table]
                    if unread:
                        others.append("a table the scan cannot read")
                    through = ""
                    if others:
                        by_rules = aimed_at(table, inherited, keys=False)
                        by_keys = reached != by_rules
                        why = ([] if by_rules == {table} else [
                            "a rule's own writes carry the conflict clause of "
                            "the statement that ran it"]) + ([] if not by_keys else [
                                "a foreign key's action writes its child when "
                                "a parent row is removed or changed"])
                        who = ("rules and keys" if len(why) == 2
                               else "keys" if by_keys else "rules")
                        through = (f" (its {who} write {', '.join(others)}, "
                                   f"and {', and '.join(why)})")
                    counted = [f"`{t}` is append-only: the schema gives it "
                               f"{rules_of(t)}" for t in guarded]
                    if unread:
                        counted.append("a table it reaches that the scan cannot "
                                       "read is counted as append-only")
                    faults.append(
                        f"{place} {form} on `{table}`{through}, and "
                        + "; ".join(counted)
                        + ". SQLite runs no delete rule for a row it removes "
                        f"to make room for a replacing write, so the stored "
                        f"row can go without one. Registered or not, this is "
                        f"refused: write it plainly -- update the stored row, "
                        f"or insert when no row changed.")
                    refused.add((where, function, table))
                    continue
                key = (where, function, table)
                found.setdefault(key, []).append(place)
                if key not in register:
                    faults.append(
                        f"{place} {form} on `{table}`, which "
                        f"audit.UPSERTS_REGISTERED does not name. A table the "
                        f"schema protects with no rule may take a replacing "
                        f"write only as a cache of a source or a table derived "
                        f"from one, registered by file, function and table "
                        f"with a dated reason -- or write it plainly.")
                elif len(found[key]) > 1:
                    faults.append(
                        f"{place} a second replacing write on `{table}` under "
                        f"one register entry (the first is {found[key][0]}). "
                        f"An entry names one statement; the register only "
                        f"shrinks.")
    for key, reason in sorted(register.items()):
        where, function, table = key
        name = f"{where} ({function}) on `{table}`"
        if table in protected:
            faults.append(
                f"{name}: registered in audit.UPSERTS_REGISTERED, and "
                f"`{table}` is append-only -- the schema gives it "
                f"{rules_of(table)}. No entry can hold a replacing write on "
                f"it: remove the entry and write the table plainly.")
        if key in refused and key not in found and table not in protected:
            # Its statement is there and refused above, because a rule or a
            # key carries it onto an append-only table: not "no longer
            # found", which it was called until the prover (2026-09-27).
            faults.append(
                f"{name}: registered in audit.UPSERTS_REGISTERED, and its "
                f"statement is refused above -- a rule or a key of `{table}` "
                f"carries it onto an append-only table. No entry can hold it: "
                f"remove the entry and write the table plainly.")
        elif key not in found and table not in protected:
            faults.append(
                f"{name}: registered in audit.UPSERTS_REGISTERED and no "
                f"longer found. The register only shrinks: remove the entry.")
        if not re.match(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}: \S", str(reason)):
            faults.append(
                f"{name}: registered without a dated reason in words "
                f"(\"2026-09-27: a cache of ...\"). A register nobody can "
                f"date is a list of exceptions nobody re-reads.")
        if frozen is not None and key not in frozen:
            # "A register that may only shrink" (the ruling's words; its
            # prover, 2026-09-27): an entry the register did not hold when it
            # was frozen is growth, however it is dated.
            faults.append(
                f"{name}: registered in audit.UPSERTS_REGISTERED and not among "
                f"the entries frozen on 2026-09-27 "
                f"(audit.UPSERTS_REGISTERED_ON_2026_09_27). The register may "
                f"only shrink: write the table plainly -- update the stored "
                f"row, or insert when no row changed -- or ask the operator.")
    return faults


def check_no_replacing_write_on_an_append_only_table(root: Path | None = None) -> None:
    faults = replacing_write_faults(root)
    if faults:
        raise LawViolation(
            "A WRITE CAN REPLACE A ROW OF AN APPEND-ONLY TABLE (operator "
            "question 15, ruled 2026-09-27: one gate scan refuses a replacing "
            "write against every append-only table, and names every other "
            "upsert in a register that only shrinks):" + _NL2
            + _NL2.join(faults))


# ---------------------------------------------------------------------------
# THE RULES STAY ON, AND THEIR MARKS STAY PUT (operator questions 25 and 29,
# ruled 2026-09-28; question 29's reading confirmed by the operator on
# 2026-09-29; built 2026-09-29)
# ---------------------------------------------------------------------------
#
# Question 25: "yes. The scan also refuses any code that turns the rules off
# by connection setting or registers a function under a built-in's name."
# Question 29: "folded into Q25's scan: refuse any code that writes
# sqlite_sequence, and any multi-row INSERT OR FAIL / OR IGNORE / OR
# ROLLBACK on an append-only table. No separate item." Its reading, which the
# operator confirmed: except `gridiron.rebuild`, which carries the mark
# exactly and is the verified rebuild door, named in a register with its
# dated reason.
#
# WHY A SIBLING OF QUESTION 15'S SCAN. Every rule of the schema is a trigger
# SQLite runs on the connection that writes, and question 15's scan reads the
# statements that replace a row. Four things take a rule's refusal away with
# no replacing statement at all, each measured on a scratch world on
# 2026-09-29:
#   * A CONNECTION'S SETTINGS. With `setconfig(SQLITE_DBCONFIG_ENABLE_TRIGGER,
#     False)` no rule runs: a delete the no-delete rule refuses lands. Seven
#     settings change what a rule does or reads (`RULE_SETTINGS`), five
#     `setconfig` switches do (`RULE_DBCONFIG`), and an authorizer hands a
#     rule's read back as NULL -- a guarded insert landed so.
#   * A FUNCTION OR A COLLATION UNDER A BUILT-IN'S NAME. A rule calling
#     `json_valid` asks the connection, and `create_function("json_valid", 1,
#     ...)`, in any case, answers it in SQLite's place: a value the rule
#     refused landed. `create_collation("NOCASE", ...)` answers every
#     comparison made under it.
#   * THE MARK REWRITTEN. The rules on the number written (questions 13, 15
#     and 24) read SQLite's own table of AUTOINCREMENT marks, and SQLite
#     allows no rule on that table, so a statement writing it -- the mark
#     removed, set back, set forward and back round a move -- is seen by no
#     rule.
#   * A STATEMENT STOPPED PART WAY. An insert of several rows under OR FAIL
#     whose later row fails a NOT NULL keeps the rows before it, and SQLite
#     never writes the mark back for a statement that stopped: rows 3 and 4
#     stood above a mark of 2. (OR IGNORE and OR ROLLBACK left none, measured
#     the same day; the ruling names all three, and an upsert that does
#     nothing on conflict skips a row as OR IGNORE does.)
#
# WHAT IT READS: question 15's scope with its readers -- the package, `tools/`
# less `tools/guards/`, and `desktop/`; every string the code can hand SQLite
# (`_sql_strings_in`), read as written and with its template placeholders as
# parts worked out at run time, and a template filled in with constants alone
# read again whole (the roster scan's `_roster_filled_in`); every `.sql` file
# in the package; and each Python file's syntax tree for the calls that set a
# connection's switches or register a function. Tests and plantings are
# outside it, as they are outside question 15's: they are how the rules are
# proved.
#
# WHAT IT REFUSES, each by file, line and function:
#   1. A SETTING OF ONE OF `RULE_SETTINGS` -- `=` or `(...)` after its name,
#      whatever the value; a name followed by a part worked out at run time,
#      or ending a string not handed whole to `execute`, counts as set -- and
#      a setting whose name the scan cannot read. A `setconfig` of one of
#      `RULE_DBCONFIG` to the value that does it or to one worked out at run
#      time, and a `setconfig` of a switch the scan cannot read. An
#      authorizer.
#   2. A `create_function`, `create_aggregate`, `create_window_function` or
#      `create_collation` whose name, in any case, SQLite itself lists on a
#      fresh connection (`function_list`, `collation_list`) -- never a hand
#      list -- or whose name the scan cannot read; an extension loaded or
#      allowed (`load_extension`, `enable_load_extension`, and the SQL
#      function), whose registrations no scan can read; and any of those
#      calls reached by another name, bound or looked up by a string.
#   3. A WRITE OF SQLITE'S SEQUENCE STORE: an insert, a REPLACE, an update or
#      a delete whose table is it however spelled -- case, quotes, brackets, a
#      schema's prefix, or a string literal, which SQLite takes as a write's
#      table (measured) -- or a name partly worked out at run time whose
#      written letters, three or more, could be it; a verb worked out at run
#      time where a statement begins counts as a write; and the bare name,
#      which the scan cannot place, counts as one, as does this module's own
#      value holding it named anywhere but this scan. The one exception is
#      `SEQUENCE_WRITES_REGISTERED`: the rebuild door's two statements, each
#      with its dated reason, frozen on 2026-09-29 so that it may only shrink.
#   4. AN INSERT OF SEVERAL ROWS under OR FAIL, OR IGNORE or OR ROLLBACK, or
#      with an upsert that does nothing on conflict, aimed at an append-only
#      table -- question 15's set, read from the schema: a table a rule
#      refuses a delete or an update on, one its table's rules write, and one
#      the scan cannot read. Several rows: a VALUES list of two or more or
#      with more rows after it (`VALUES (1) UNION ALL SELECT 2`), a SELECT, a
#      VALUES part worked out at run time or a string that ends before its
#      rows; and, in Python, a statement handed to `executemany`,
#      or not handed whole to `execute` or `executescript`, which the scan
#      cannot see run once. And a key of an append-only table declared to
#      fail, ignore or roll back on conflict, under which every plain insert
#      of several rows runs so (question 15's precedent: a key declared to
#      replace).
#
# LEFT AS THEY ARE, and why (the shipped code on 2026-09-29): `foreign_keys`
# (the rebuild door's and the migrations' own setting, off while a table is
# renamed aside so no child is repointed -- schema ruling 2; a key is not a
# rule, and a key's action is question 15's to read), `legacy_alter_table`
# (whether a rename rewrites the rules naming the table, which the rebuild
# door keeps from happening -- not how a rule runs), `query_only` (refuses
# writes and runs every rule), `defer_foreign_keys`, their `setconfig` twins,
# and `SQLITE_DBCONFIG_DEFENSIVE`, which only forbids more. The switches for
# double-quoted strings are left too: no rule of the schema holds a
# double-quoted word (measured).
#
# WHAT THE SHIPPED CODE DID, measured before the scan was written
# (2026-09-29): no setting of these, no `setconfig`, no function, collation,
# authorizer or extension; the rebuild door's two writes of the sequence
# store and nothing else; and two inserts of several rows under OR IGNORE --
# `db.widen_taken_for_packages` copying `picks_taken` (append-only) back, and
# `db._finish_widening_table` copying back a table worked out when it runs
# (`factors`, append-only, is one of the five it can be) -- each a
# migration's recovery copy, which can run on no record without a
# half-finished widening (the record held none, read through the read-only
# door). Both are plain inserts now, to the same effect -- `db.set_meta`'s
# precedent under question 15 -- tested side by side.
#
# AND FROM ITS PROVER (2026-09-29), each measured getting past the scan as
# first built, which named none of them:
#   * `journal_mode` OFF is a connection setting that turns a rule's refusal
#     off: with no rollback journal, a statement a rule refuses inside a
#     transaction keeps its rows -- the refused row among them, above the
#     mark (measured on a DELETE and on a WAL file). It is refused at OFF or
#     at a value the scan cannot read (`RULE_SETTING_VALUES`); the schema's
#     own WAL is not.
#   * A LOOKUP OF THE CALLS BY A STRING THE SCAN CAN RENDER: joined in pieces,
#     a template filled in with constants, a bytes literal, another case, a
#     string handed to `exec` -- every word of every string is read, and one
#     that is a call's name, or whose written letters (three or more) around
#     a part worked out at run time could be one, is a lookup by name. And
#     this module's own values holding the calls' names (`_REGISTERING_CALLS`,
#     `_RULE_SWITCH_CALLS`), named anywhere but this scan, are the call
#     reached by another name (the roster scan's precedent).
#   * A SWITCH NAMED BY A DISGUISE -- the trigger switch imported under the
#     harmless switch's name, or a class attribute of that name holding its
#     number: a switch's name is read only off the driver itself
#     (`sqlite3.X`, the module imported as itself and never rebound) or from
#     a name imported from it unaliased and never bound again; any other is a
#     switch the scan cannot read, and a statement binding one of the
#     driver's switch names (an assignment, `setattr`) is refused.
#   * A SETTING'S NAME WRITTEN WHOLE, ITS VERB WORKED OUT OR KEPT APART
#     (`verb + " recursive_triggers = 1"`, the verb in two pieces): a listed
#     name followed by a value, a part worked out at run time or the end of a
#     string not handed whole to `execute`, with no verb before it, is a
#     setting; so are this module's values holding the settings' names.
#   * THE SQL FUNCTION THAT LOADS AN EXTENSION, CALLED BY A QUOTED NAME
#     (`"load_extension"(?)`: SQLite calls a function by a quoted name).
#   * THE STORE'S NAME KEPT APART FROM ITS VERB: at the start of a string with
#     its condition after it (`"sqlite_sequence WHERE ..."`), after a FROM or
#     INTO that begins a string, or after a verb in pieces (a word holding a
#     part worked out at run time where a statement could begin) -- each a
#     name the scan cannot place, or a verb worked out, counted as a write;
#     and this module's value holding it looked up by a string in pieces.
#   * AN INSERT OF SEVERAL ROWS WHOSE VERB IS IN PIECES OR KEPT APART
#     (`head + "RT OR FAIL INTO ..."`, `"INSERT " + "OR IGNORE INTO ..."`,
#     `"INSERT OR FAIL"` ending a string).
#   * A RULE RAISING FAIL -- a temporary one the code creates, or one in the
#     schema -- on an append-only table, or on a table an insert into one
#     reaches: a plain insert of several rows then stops part way as OR FAIL
#     does (measured: rows 3 and 4 above a mark of 2). A rule raising FAIL,
#     IGNORE or ROLLBACK is refused as a key declared so is (question 15's
#     precedent, read for a rule).
#   * ONE ROW UNDER A RULED CLAUSE INTO A TABLE WHOSE RULE INSERTS SEVERAL
#     ROWS INTO AN APPEND-ONLY ONE: SQLite runs a rule's statements under the
#     clause of the statement that fired it, so the rule's insert stopped
#     part way under OR FAIL (measured: rows 3 and 4 above a mark of 2). It
#     is counted as an insert of several rows under that clause.
#   * THE DOOR'S OWN STATEMENT REWRITTEN (its DELETE widened to every mark):
#     the register held a verb, so any statement of that verb in the door
#     passed. Each entry now holds the statement it was made with, as SQLite
#     reads it (`SEQUENCE_WRITES_AS_MADE_ON_2026_09_29`); another under the
#     entry is a second door.
#
# NOT SEEN (FOLLOWUPS): what a static scan cannot read -- a setting's, a
# function's or a table's name read from the record, a file or the
# environment, or built where no string of it is rendered (a list joined at
# run time), and a setting whose verb and name are both in pieces; a write
# whose table is wholly worked out at run time (the shipped code's own copies
# of every table, none of them the store); SQLite reached through `ctypes`; an
# update of several rows under OR FAIL; a table's mark carried away by SQLite
# itself when the table is dropped or renamed (a migration's rename aside and
# copy back sets its mark to the highest number copied); and a connection
# outside the shipped code -- a test, a planting, the operator's own shell --
# which is how the rules are proved, not what the gate reads. And beyond the
# rulings' words (the prover, 2026-09-29, measured): a write that is no
# statement at all -- `blobopen`, which rewrote a stored row's text in place
# past its no-update rule, and a backup written into the record's file,
# which replaces every page with no rule run. No shipped code does either.

#: SQLite's own table of AUTOINCREMENT marks. Written once: every other text
#: of this scan builds on it, and a value of this module holding it is named
#: only by the scan itself (`_RULE_WORD_HOLDERS`, proved at import).
SEQUENCE_STORE = "sqlite_sequence"

#: The word that opens a statement setting (or reading) one of SQLite's
#: settings. Written once, for the same reason: the word alone, at the end
#: of a string, is a setting whose name the scan cannot read, and this module
#: is read by its own scan.
_SETTING_VERB = "PRAGMA"

#: THE SETTINGS THAT CHANGE HOW THE SCHEMA'S RULES RUN (question 25,
#: 2026-09-29), by SQLite's own name for each, and what it does to a rule --
#: each measured on a scratch world that day. A statement setting one is
#: refused in the shipped code, whatever the value: the rules are written and
#: measured at SQLite's defaults, and no shipped code sets any of them. Each
#: name is held, when the scan runs, to SQLite's own list of its settings.
RULE_SETTINGS: dict[str, str] = {
    "recursive_triggers": (
        "on, SQLite runs a table's delete rules for a row it removes to make "
        "room for a replacing write (measured: a replacing insert the rules "
        "let through was refused by the delete rule), and a rule's own writes "
        "run rules again -- the schema's rules, and the replace rules "
        "questions 13 and 15 wrote because no delete rule runs for a replaced "
        "row, are written for it off, SQLite's default"),
    "ignore_check_constraints": (
        "on, no CHECK of the schema is enforced (measured: a factor's "
        "activation date that is no date was stored)"),
    "case_sensitive_like": (
        "on, LIKE compares letters by their case, inside a rule or a CHECK as "
        "anywhere (measured: `factors.added_utc`'s CHECK, which reads LIKE, "
        "refused a date its default accepts)"),
    "trusted_schema": (
        "decides which functions a rule may call: on, any the connection "
        "defines, a built-in's name redefined among them; off, a rule calling "
        "one is refused (measured both ways)"),
    "reverse_unordered_selects": (
        "on, a rule reading one row of several in no stated order reads "
        "another (measured: a rule's read of the first of two rows read the "
        "second)"),
    "writable_schema": (
        "on, the schema's own table may be written, so a rule is rewritten or "
        "removed by a statement that names no rule (measured: a no-delete "
        "rule's row deleted from it)"),
    "schema_version": (
        "set, a connection that has read the schema does not read it again, "
        "so a rule added since does not run there (measured: a second "
        "connection deleted a row the new no-delete rule refuses)"),
}

#: THE SETTINGS REFUSED AT ONE VALUE (the prover of questions 25 and 29,
#: 2026-09-29), by SQLite's own name for each: (the value refused, upper-cased,
#: and what it does to a rule). A statement setting one of these to that
#: value, or to a value the scan cannot read, is refused; every other value
#: keeps a rule's refusal whole -- the schema's own `journal_mode = WAL` among
#: them -- and a read handed whole to `execute` is no setting. Each name is
#: held, when the scan runs, to SQLite's own list of its settings.
RULE_SETTING_VALUES: dict[str, tuple[str, str]] = {
    "journal_mode": (
        "OFF",
        "no rollback journal is kept, so inside a transaction a "
        "statement a rule refuses keeps the rows it wrote -- the refused row "
        "among them, above the mark (measured on a scratch world: an insert "
        "of two rows, the second refused by a rule, left both standing; the "
        "same from a WAL file, where WAL, MEMORY and TRUNCATE left none)"),
}

#: THE `setconfig` SWITCHES THAT CHANGE HOW THE RULES RUN (question 25,
#: 2026-09-29), by the driver's name for each: (the value that does it --
#: False, True, or None for either -- and what it does). The number each
#: stands for is read from the driver (`_dbconfig_numbers`), never typed.
RULE_DBCONFIG: dict[str, tuple[bool | None, str]] = {
    "SQLITE_DBCONFIG_ENABLE_TRIGGER": (
        False, "off, no rule of the schema runs on that connection (measured: "
               "a delete the no-delete rule refuses landed)"),
    "SQLITE_DBCONFIG_TRUSTED_SCHEMA": (
        None, "the switch behind the setting `trusted_schema`, which decides "
              "which functions a rule may call"),
    "SQLITE_DBCONFIG_WRITABLE_SCHEMA": (
        True, "the switch behind the setting `writable_schema`: on, a rule is "
              "rewritten or removed by a statement that names no rule"),
    "SQLITE_DBCONFIG_RESET_DATABASE": (
        True, "on, the next VACUUM empties the database, every row gone with no "
              "rule run (measured)"),
    "SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION": (
        True, "on, an extension may be loaded, and what it registers -- "
              "functions and collations, under any name -- no scan can read"),
}

#: The calls that register a function or a collation on a connection, and
#: which of SQLite's own lists a name is held to (2026-09-29).
_REGISTERING_CALLS = {"create_function": "function",
                      "create_aggregate": "function",
                      "create_window_function": "function",
                      "create_collation": "collation"}

#: The other calls that change what a rule may do or read (2026-09-29).
_RULE_SWITCH_CALLS = ("setconfig", "set_authorizer", "load_extension",
                      "enable_load_extension")

#: The conflict clauses question 29 names.
_RULED_CONFLICTS = ("FAIL", "IGNORE", "ROLLBACK")

#: What a bare name, which the scan cannot place, is counted as.
_A_NAME_UNPLACED = "a name the scan cannot place"

#: The fewest written letters a name partly worked out at run time must
#: carry to count as one that could be the sequence store: the roster scan's
#: measure (three), measured again on the shipped code on 2026-09-29 -- at
#: one letter a bare `f"{venue}_{word}"` (this module's credential names)
#: read as the store; at two or more, nothing does.
_STORE_FRAGMENT_MIN = 3

#: THE REGISTER OF WRITES TO THE SEQUENCE STORE (question 29, ruled
#: 2026-09-28; its reading confirmed 2026-09-29): keyed (file from the
#: repository root, the qualified function, the statement's verb), each with
#: a dated reason in words. One entry per statement.
SEQUENCE_WRITES_REGISTERED: dict[tuple[str, str, str], str] = {
    ("gridiron/rebuild.py", "_rebuild_one", "DELETE"): (
        "2026-09-29: the verified rebuild door (schema ruling 2) carries a "
        "rebuilt table's mark exactly -- this takes the table's row out of the "
        "store, the next statement writes back the mark read before the "
        "rebuild, both inside the rebuild's one transaction, and the mark is "
        "read again and compared before it commits, a difference refused and "
        "rolled back (question 29's reading, confirmed by the operator)"),
    ("gridiron/rebuild.py", "_rebuild_one", "INSERT"): (
        "2026-09-29: the same door writing back, exactly, the mark it read "
        "before the rebuild (question 29's reading, confirmed by the "
        "operator)"),
}

#: THE REGISTER AS IT WAS MADE (2026-09-29). The ruling's one exception is
#: the rebuild door's, so an entry not among these fails by name, however it
#: is dated: the register may only shrink (question 15's precedent). Never
#: added to.
SEQUENCE_WRITES_REGISTERED_ON_2026_09_29: frozenset[tuple[str, str, str]] = frozenset({
    ("gridiron/rebuild.py", "_rebuild_one", "DELETE"),
    ("gridiron/rebuild.py", "_rebuild_one", "INSERT"),
})

#: EACH REGISTERED STATEMENT AS IT WAS MADE (the prover, 2026-09-29): an
#: entry names a place and a verb, so the door's DELETE widened to every
#: mark passed under it -- a second door inside the first. A write under an
#: entry whose statement, as SQLite reads it, is not this one fails by name.
#: Built from `SEQUENCE_STORE`, so the store's name is written once. Never
#: changed.
SEQUENCE_WRITES_AS_MADE_ON_2026_09_29: dict[tuple[str, str, str], str] = {
    ("gridiron/rebuild.py", "_rebuild_one", "DELETE"):
        f"DELETE FROM {SEQUENCE_STORE} WHERE name = ?",
    ("gridiron/rebuild.py", "_rebuild_one", "INSERT"):
        f"INSERT INTO {SEQUENCE_STORE} (name, seq) VALUES (?, ?)",
}

#: EVERY VALUE OF THIS MODULE HOLDING A WORD THIS SCAN LOOKS FOR, by its own
#: name, and what it is counted as named anywhere but this scan's own
#: functions (the roster scan's precedent, 2026-09-29): the store's name,
#: which the scan cannot place, a write of it; the setting's word, or a
#: listed setting's name, a setting the scan cannot read; a registering or
#: switching call's name, the call reached by another name (the last two
#: from the prover, 2026-09-29: `getattr(conn, _RULE_SWITCH_CALLS[0])` set the
#: trigger switch off unnamed). The strings inside each holder's own
#: assignment are this scan's words and are not read as code. Proved
#: complete at import.
_RULE_WORD_HOLDERS = {"SEQUENCE_STORE": "store", "_SETTING_VERB": "setting",
                      "SEQUENCE_WRITES_AS_MADE_ON_2026_09_29": "store",
                      "RULE_SETTINGS": "setting", "RULE_SETTING_VALUES": "setting",
                      "_REGISTERING_CALLS": "call", "_RULE_SWITCH_CALLS": "call"}

#: The functions of this module that ARE this scan -- the only ones that may
#: name a value holding the store's name, or a registering call by a string
#: (2026-09-29). One no longer found fails the scan.
_RULE_SCAN_ITSELF = frozenset({
    "_names_the_store", "_rule_findings", "_rule_call_faults", "rule_switch_faults",
    "check_no_code_switches_the_rules_off_or_rewrites_their_marks",
    "_check_the_rule_scan_names_the_store_once",
    # the prover's (2026-09-29): the reader of names in a string
    "_rule_names_in"})

#: A string holding none of these holds no statement, setting or name this
#: scan reads, and is not tokenised: a quick way past prose, never past SQL.
#: From the prover (2026-09-29) a listed setting's name alone, and a rule's
#: RAISE, are enough to be read.
_RULE_QUICK = re.compile(
    r"pr[a]gma|insert|replace|update|delete|into|from|conflict|nothing|"
    r"extension|sqlite|sequence|raise|[\x00{}%$]|"
    + "|".join(re.escape(name) for name in (*RULE_SETTINGS, *RULE_SETTING_VALUES)),
    re.I)


def _dbconfig_numbers() -> dict[int, str]:
    """{the number the driver gives a switch of `RULE_DBCONFIG`: its name},
    read from the driver, so a switch handed over as its number is known."""
    import sqlite3

    numbers = {
        sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER: "SQLITE_DBCONFIG_ENABLE_TRIGGER",
        sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA: "SQLITE_DBCONFIG_TRUSTED_SCHEMA",
        sqlite3.SQLITE_DBCONFIG_WRITABLE_SCHEMA: "SQLITE_DBCONFIG_WRITABLE_SCHEMA",
        sqlite3.SQLITE_DBCONFIG_RESET_DATABASE: "SQLITE_DBCONFIG_RESET_DATABASE",
        sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION:
            "SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION",
    }
    if set(numbers.values()) != set(RULE_DBCONFIG):
        raise LawViolation(
            f"A SCANNER IS BLIND: audit._dbconfig_numbers reads "
            f"{sorted(numbers.values())} from the driver and audit.RULE_DBCONFIG "
            f"names {sorted(RULE_DBCONFIG)}.")
    return numbers


def _sqlite_own_names() -> tuple[frozenset, frozenset, frozenset]:
    """(every function, every collation, every setting) SQLite itself lists
    on a fresh connection, before any code registers anything -- its own
    names, read from it, case-folded, never a hand list (2026-09-29)."""
    from . import db

    conn = db.connect(":memory:")
    try:
        functions = frozenset(str(r[0]).casefold()
                              for r in conn.execute("PRAGMA function_list"))
        collations = frozenset(str(r[1]).casefold()
                               for r in conn.execute("PRAGMA collation_list"))
        settings = frozenset(str(r[0]).casefold()
                             for r in conn.execute("PRAGMA pragma_list"))
    finally:
        conn.close()
    if not (functions and collations and settings):
        raise LawViolation(
            "A SCANNER IS BLIND: SQLite listed no functions, collations or "
            "settings of its own, so no name can be held to them.")
    return functions, collations, settings


def _rule_target(tokens: list[_SqlToken], k: int) -> tuple[str | None, int]:
    """The table a write names at `tokens[k]`, as SQLite reads it -- a word, a
    quoted name, or a string literal, which SQLite also takes as a write's
    table (measured 2026-09-29); a schema's prefix apart; lower-cased -- each
    part worked out at run time kept as `_UNKNOWN_PART`; None where no letter
    of it is written. And the index after it."""
    n = len(tokens)

    def atom(i: int) -> tuple[str, int]:
        text = ""
        while i < n and tokens[i].kind in ("word", "name", "literal", "unknown"):
            tok = tokens[i]
            if text and tokens[i - 1].end != tok.start:
                break
            if tok.kind == "literal":
                inner = tok.value[1:-1] if len(tok.value) > 1 and tok.value.endswith("'") \
                    else tok.value[1:]
                text += inner.replace("''", "'").lower()
            elif tok.kind == "unknown":
                text += _UNKNOWN_PART
            else:
                text += tok.value
            i += 1
        return text, i

    text, i = atom(k)
    while text and i < n and tokens[i].kind == "other" and tokens[i].value == ".":
        after_dot, j = atom(i + 1)
        if not after_dot:
            break
        text, i = after_dot, j
    if not text.replace(_UNKNOWN_PART, ""):
        return None, i
    return text, i


def _names_the_store(name: str | None) -> bool:
    """Could `name` be the sequence store? Whole, only the name itself; with
    parts worked out at run time in it, when its written letters -- at least
    `_STORE_FRAGMENT_MIN` of them -- fall where the store's name could put
    them."""
    if name is None:
        return False
    pieces = name.split(_UNKNOWN_PART)
    if len(pieces) == 1:
        return name == SEQUENCE_STORE
    if len("".join(pieces)) < _STORE_FRAGMENT_MIN:
        return False
    return re.fullmatch("(?s:.*)".join(re.escape(p) for p in pieces),
                        SEQUENCE_STORE) is not None


def _rule_spans(tokens: list[_SqlToken]) -> list[tuple[int, int, str | None]]:
    """(index of CREATE, index after its body's END, the table it is on or
    None where that cannot be read) for every rule one text creates -- a
    temporary one among them (the prover, 2026-09-29)."""
    spans = []
    n = len(tokens)
    for at, kind, _name, k in _sql_objects(tokens):
        if kind != "trigger":
            continue
        while k < n and tokens[k].word != "ON":
            k += 1
        table, k = _read_sql_name(tokens, k + 1)
        while k < n and tokens[k].word != "BEGIN":
            k += 1
        depth, k = 1, k + 1
        while k < n and depth:
            if tokens[k].word == "CASE":
                depth += 1
            elif tokens[k].word == "END":
                depth -= 1
            k += 1
        spans.append((at, k, table))
    return spans


def _rule_setting_value(tokens: list[_SqlToken], after: int, whole: bool) -> str | None:
    """What a setting is set to, its name ending at `tokens[after]` (the
    prover, 2026-09-29): the value upper-cased; "" for none -- a read, the
    name ending a statement handed whole to `execute`, or anything else after
    it; None where the scan cannot read it -- a part worked out at run time
    touching the name or where the value goes, or the string ending there."""
    n = len(tokens)
    if after >= n:
        return "" if whole else None
    tok = tokens[after]
    if tok.kind == "unknown":
        return None
    if not (tok.kind == "other" and tok.value in ("=", "(")):
        return ""
    v = after + 1
    if v >= n or tokens[v].kind == "unknown":
        return None
    value = tokens[v]
    if v + 1 < n and tokens[v + 1].kind == "unknown" and tokens[v + 1].start == value.end:
        return None
    if value.kind == "literal":
        inner = value.value[1:-1] if len(value.value) > 1 and value.value.endswith("'") \
            else value.value[1:]
        return inner.replace("''", "'").upper()
    return value.value.upper()


def _rule_names_in(text: str, names) -> list[tuple[int, str, bool]]:
    """(offset in the text, the name, whether it is written whole) for every
    word of one string that is one of `names` -- in any case -- or that,
    with a part worked out at run time in it, could be one: its written
    letters, `_STORE_FRAGMENT_MIN` or more, falling where the name puts them
    (the prover, 2026-09-29). Words touching one another, or a part worked
    out at run time, are one word; a `.` or anything else parts them. The SQL
    function that loads an extension, called as one (the name followed by
    `(`, no `.` before it), is the extension reading's and not counted here."""
    tokens = _sql_tokens(text)
    n = len(tokens)
    wanted = {name.casefold(): name for name in names}
    found = []
    j = 0
    while j < n:
        if tokens[j].kind == "literal":
            # A quoted string inside the string -- Python code handed to
            # `exec` quotes the name it looks up -- is a word of its own.
            start, j = j, j + 1
            quoted = tokens[start].value
            atom = (quoted[1:-1] if len(quoted) > 1 and quoted.endswith("'")
                    else quoted[1:]).replace("''", "'").casefold()
        elif tokens[j].kind not in ("word", "name", "unknown"):
            j += 1
            continue
        else:
            start, atom = j, ""
            while j < n and tokens[j].kind in ("word", "name", "unknown") and (
                    j == start or tokens[j - 1].end == tokens[j].start):
                atom += (_UNKNOWN_PART if tokens[j].kind == "unknown"
                         else tokens[j].value.casefold())
                j += 1
        pieces = atom.split(_UNKNOWN_PART)
        if len(pieces) == 1:
            hits = [(wanted[atom], True)] if atom in wanted else []
        elif len("".join(pieces)) >= _STORE_FRAGMENT_MIN:
            pattern = "(?s:.*)".join(re.escape(p) for p in pieces)
            hits = [(name, False) for folded, name in wanted.items()
                    if re.fullmatch(pattern, folded)]
        else:
            hits = []
        called_in_sql = (atom == _RULE_SWITCH_CALLS[2] and j < n
                         and tokens[j].kind == "other" and tokens[j].value == "("
                         and not (start > 0 and tokens[start - 1].kind == "other"
                                  and tokens[start - 1].value == "."))
        if not called_in_sql:
            found.extend((tokens[start].start, name, exact) for name, exact in hits)
    return found


def _rule_findings(tokens: list[_SqlToken], whole: bool) -> list[tuple[int, str, object]]:
    """(token index, kind, what) for every place one text could switch a
    rule off or move a mark: ("setting", its name, or None where the scan
    cannot read it), ("setting apart", a listed name standing with no verb
    before it), ("store", the verb that writes it), ("rows", (the clauses,
    the table or None, why several or None for one row)), ("key", (the
    clause, the table or None)), ("raise", (the clause or None, the rule's
    table or None)), ("rule rows", (the rule's table, the table its insert of
    several rows writes, why several)) and ("extension", None). `whole` is
    whether the text is a statement as SQLite will run it -- a `.sql` file,
    or a string handed straight to `execute` or `executescript`."""
    n = len(tokens)

    def word(k: int) -> str | None:
        return tokens[k].word if 0 <= k < n else None

    def unknown(k: int) -> bool:
        return 0 <= k < n and tokens[k].kind == "unknown"

    def punct(k: int, text: str) -> bool:
        return 0 <= k < n and tokens[k].kind == "other" and tokens[k].value == text

    def begins(k: int) -> bool:
        """Could a statement begin at `k`, as far as the text shows?"""
        return (k == 0 or punct(k - 1, ";") or punct(k - 1, ")")
                or word(k - 1) == "BEGIN" or unknown(k - 1))

    def after_parens(k: int) -> int:
        depth = 0
        while k < n:
            if punct(k, "("):
                depth += 1
            elif punct(k, ")"):
                depth -= 1
                if depth <= 0:
                    return k + 1
            k += 1
        return n

    def statement_end(k: int) -> int:
        depth = 0
        while k < n:
            if punct(k, "("):
                depth += 1
            elif punct(k, ")"):
                depth -= 1
            elif depth <= 0 and punct(k, ";"):
                return k
            k += 1
        return n

    def created_table(k: int) -> str | None:
        while k > 0:
            k -= 1
            if punct(k, ";"):
                return None
            if word(k) == "CREATE":
                for at, kind, name, _after in _sql_objects(tokens[k:]):
                    return name if at == 0 and kind == "table" else None
                return None
        return None

    def verb_apart(k: int) -> bool:
        """Could the verb of a write whose INTO, FROM, OR or table stands at
        `k` be kept apart from it, or be worked out in pieces (the prover,
        2026-09-29: `"DELE" + "TE FROM ..."`, `head + "RT INTO ..."`)?
        Nothing before it in the string, or -- an OR and its clause between
        them skipped -- a word holding a part worked out at run time where a
        statement could begin."""
        if k >= 2 and word(k - 2) == "OR" and tokens[k - 1].kind in ("word", "unknown"):
            k -= 2
        if k == 0:
            return True
        a = k - 1
        if tokens[a].kind not in ("word", "name", "unknown"):
            return False
        while (a > 0 and tokens[a - 1].kind in ("word", "name", "unknown")
               and tokens[a - 1].end == tokens[a].start):
            a -= 1
        return any(tokens[x].kind == "unknown" for x in range(a, k)) and begins(a)

    spans = _rule_spans(tokens)

    def rule_table(k: int) -> str | None:
        """The table of the rule whose body holds `k`; None where no rule of
        this text holds it, or its table cannot be read."""
        holding = [s for s in spans if s[0] <= k < s[1]]
        return holding[-1][2] if holding else None

    def in_a_rule(k: int) -> bool:
        return any(s[0] <= k < s[1] for s in spans)

    def set_to_what_is_refused(name: str, after: int) -> bool:
        """Is the setting `name`, its name ending at `after`, set as refused?
        A listed setting at any value; one refused at a value, at that value
        or at one the scan cannot read (the prover, 2026-09-29)."""
        if name in RULE_SETTINGS:
            return (punct(after, "=") or punct(after, "(") or unknown(after)
                    or (after >= n and not whole))
        value = _rule_setting_value(tokens, after, whole)
        return value is None or value == RULE_SETTING_VALUES[name][0]

    found: list[tuple[int, str, object]] = []
    placed: set[int] = set()          # where a write's table was read
    for i, tok in enumerate(tokens):
        w = tok.word
        if w == _SETTING_VERB:
            name, after = _read_sql_name(tokens, i + 1)
            if name is None:
                found.append((i, "setting", None))
            elif (name in RULE_SETTINGS or name in RULE_SETTING_VALUES) \
                    and set_to_what_is_refused(name, after):
                found.append((i, "setting", name))
        elif (tok.kind in ("word", "name")
              and (tok.value in RULE_SETTINGS or tok.value in RULE_SETTING_VALUES)):
            # A LISTED NAME WITH NO VERB BEFORE IT (the prover, 2026-09-29):
            # the verb worked out when it runs, in pieces, or kept apart.
            p = i - 2 if (punct(i - 1, ".") and i >= 2
                          and tokens[i - 2].kind in ("word", "name")) else i
            if word(p - 1) != _SETTING_VERB and set_to_what_is_refused(tok.value, i + 1):
                found.append((i, "setting apart", tok.value))
        elif (tok.kind in ("word", "name") and tok.value == _RULE_SWITCH_CALLS[2]
              and punct(i + 1, "(")):
            # By a quoted name too (the prover, 2026-09-29: SQLite calls a
            # function by one).
            found.append((i, "extension", None))
        elif w == "ON" and word(i + 1) == "CONFLICT" and word(i + 2) in _RULED_CONFLICTS:
            found.append((i, "key", (word(i + 2), created_table(i))))
        elif w == "RAISE" and punct(i + 1, "(") and (
                word(i + 2) in _RULED_CONFLICTS or unknown(i + 2)):
            # A RULE RAISING FAIL, IGNORE OR ROLLBACK (the prover, 2026-09-29).
            found.append((i, "raise", (word(i + 2) or None, rule_table(i))))
        # THE SEQUENCE STORE WRITTEN: every place a write's table goes.
        targets: list[tuple[str, int]] = []
        if w == "INSERT" or (w == "REPLACE" and word(i - 1) != "OR"):
            k = i + 1
            if word(k) == "OR":
                k += 2
            elif unknown(k):
                k += 1
            if word(k) == "INTO":
                targets.append((w, k + 1))
        elif w == "UPDATE":
            k = i + 1
            if word(k) == "OR":
                k += 2
            targets.append(("UPDATE", k))
            if unknown(k):
                targets.append(("UPDATE", k + 1))       # UPDATE {clause} t SET
        elif w == "DELETE" and word(i + 1) == "FROM":
            targets.append(("DELETE", i + 2))
        elif w in ("INTO", "FROM") and verb_apart(i):
            # A FROM or INTO whose verb is worked out when it runs -- and from
            # the prover (2026-09-29) one beginning the string, its verb kept
            # apart, or after a verb in pieces: a DELETE's or an INSERT's.
            targets.append(("a verb worked out when it runs", i + 1))
        placed.update(k for _verb, k in targets)
        for verb, k in targets:
            if _names_the_store(_rule_target(tokens, k)[0]):
                found.append((i, "store", verb))
                break
        # AN INSERT OF SEVERAL ROWS UNDER A CLAUSE THAT FAILS, IGNORES OR
        # ROLLS BACK -- its verb whole, or (the prover, 2026-09-29) kept apart
        # or in pieces before `OR <clause> INTO`.
        if w == "INSERT":
            k, clause = i + 1, None
            if word(k) == "OR":
                clause, k = word(k + 1), k + 2
        elif (w == "OR" and word(i + 1) in _RULED_CONFLICTS
              and word(i - 1) not in ("INSERT", "UPDATE") and verb_apart(i)):
            k, clause = i + 2, word(i + 1)
        else:
            continue
        if word(k) != "INTO":
            if clause in _RULED_CONFLICTS and (k >= n or unknown(k)):
                # `INSERT OR FAIL` ending the string, its table and rows added
                # when it runs (the prover, 2026-09-29).
                found.append((i, "rows", ((clause,), None, "rows added when it runs")))
            continue
        table, a = _rule_target(tokens, k + 1)
        if table is not None and _UNKNOWN_PART in table:
            table = None
        if word(a) == "AS":
            a += 2
        if punct(a, "("):
            a = after_parens(a)
        several: str | None = "rows a SELECT gives"
        if a >= n or unknown(a):
            several = "rows added when it runs"
        elif word(a) == "DEFAULT" and word(a + 1) == "VALUES":
            several = None
        elif word(a) == "VALUES":
            b, count, trailing = a + 1, 0, False
            while punct(b, "("):
                b, count, trailing = after_parens(b), count + 1, False
                if not punct(b, ","):
                    break
                b, trailing = b + 1, True
            if count > 1:
                several = f"a VALUES list of {count}"
            elif count == 0 or trailing or unknown(b):
                several = "a VALUES list worked out when it runs"
            elif not (b >= n or punct(b, ";") or word(b) in ("ON", "RETURNING")):
                # `VALUES (1) UNION ALL SELECT 2` is two rows (2026-09-29).
                several = "a VALUES list with more rows after it"
            else:
                several = None      # one row, as written: how it is run is judged
        end = statement_end(a)
        nothing = any(word(j) == "DO" and word(j + 1) == "NOTHING" for j in range(a, end))
        clauses = tuple([clause] if clause in _RULED_CONFLICTS else []) + (
            ("DO NOTHING",) if nothing else ())
        if clauses:
            found.append((i, "rows", (clauses, table, several)))
        elif several is not None and in_a_rule(i):
            # A RULE'S OWN INSERT OF SEVERAL ROWS (the prover, 2026-09-29):
            # SQLite runs a rule's statements under the conflict clause of the
            # statement that fired it, so one row under OR FAIL on the rule's
            # table is several rows under OR FAIL on this one (measured).
            found.append((i, "rule rows", (rule_table(i), table, several)))
    # THE STORE'S NAME WHERE NO VERB IS BEFORE IT: at the start of the string,
    # or after a word holding a part worked out at run time where a statement
    # could begin -- where a verb kept apart, worked out or in pieces would
    # go (`UPD` + `ATE ...`) -- a name the scan cannot place, counted as a
    # write. The bare name was one; from the prover (2026-09-29) so is one
    # with its condition after it (`sqlite_sequence WHERE name = ...`). After
    # a FROM, a JOIN, a `:` or any whole word it is a read or prose, as before.
    atom_kinds = ("word", "name", "literal", "unknown")
    for j, tok in enumerate(tokens):
        if tok.kind not in atom_kinds or j in placed:
            continue
        if j > 0 and (punct(j - 1, ".") or (tokens[j - 1].kind in atom_kinds
                                            and tokens[j - 1].end == tok.start)):
            continue                     # inside a name that begins earlier
        if verb_apart(j) and _names_the_store(_rule_target(tokens, j)[0]):
            found.append((j, "store", _A_NAME_UNPLACED))
    return found


def _sql_statement_end(tokens: list[_SqlToken], k: int) -> int:
    """The offset where the statement beginning at `tokens[k]` ends: its `;`
    outside any parentheses and any BEGIN ... END or CASE ... END, or the
    text's end."""
    parens = blocks = 0
    for tok in tokens[k:]:
        if tok.kind == "other" and tok.value == "(":
            parens += 1
        elif tok.kind == "other" and tok.value == ")":
            parens -= 1
        elif tok.word in ("BEGIN", "CASE"):
            blocks += 1
        elif tok.word == "END":
            blocks -= 1
        elif tok.kind == "other" and tok.value == ";" and parens <= 0 and blocks <= 0:
            return tok.end
    return tokens[-1].end if tokens else 0


def _rule_findings_in(text: str, whole: bool, template: bool) -> list[tuple[int, str, object]]:
    """(offset in the text, kind, what) for every finding in one text. A
    string of Python is read twice, as `_replacing_writes_in` reads it: with
    each template placeholder a part worked out at run time, and as written
    for anything the first reading finds nothing of at the same place."""
    if not _RULE_QUICK.search(text):
        return []
    tokens = _sql_tokens(text)
    as_written = [(tokens[i].start, kind, what)
                  for i, kind, what in _rule_findings(tokens, whole)]
    if not template:
        return as_written
    filled = _sql_tokens(_placeholders_unknown(text))
    found = [(filled[i].start, kind, what)
             for i, kind, what in _rule_findings(filled, whole)]
    places = {(start, kind) for start, kind, _what in found}
    return found + [f for f in as_written if (f[0], f[1]) not in places]


def _how_it_is_run(node: ast.AST, parents: dict) -> str:
    """"execute" when the string is the statement handed straight to
    `execute` or `executescript`, "executemany" when handed to
    `executemany`, and "elsewhere" -- kept, returned, handed to anything
    else -- otherwise."""
    parent = parents.get(id(node))
    if (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute)
            and parent.args and parent.args[0] is node):
        if parent.func.attr in ("execute", "executescript"):
            return "execute"
        if parent.func.attr == "executemany":
            return "executemany"
    return "elsewhere"


def _rule_call_faults(where: str, tree: ast.AST, functions: dict,
                      own_words: bool, sqlite_functions: frozenset,
                      sqlite_collations: frozenset, numbers: dict,
                      its_own=lambda node: False) -> list[str]:
    """The calls in one module that set a rule-changing switch, register a
    function or a collation under a built-in's name, set an authorizer or
    load an extension -- and each such call reached by another name. `own_words`
    is this module, whose own constants name the calls; `its_own(node)` says
    whether a string there is this scan's own words (the prover, 2026-09-29:
    in the scan's functions or a holder's assignment, never module level
    alone)."""
    faults: list[str] = []
    prose = _docstring_nodes(tree)
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    every_call = set(_REGISTERING_CALLS) | set(_RULE_SWITCH_CALLS)

    def place(node: ast.AST) -> str:
        return f"{where}:{node.lineno} ({functions.get(id(node)) or 'module level'})"

    def constant(node: ast.AST | None):
        if isinstance(node, ast.Constant) and isinstance(node.value, (bool, int)):
            return bool(node.value)
        return None

    # A SWITCH IS NAMED ONLY BY THE DRIVER ITSELF (the prover, 2026-09-29): the
    # trigger switch imported under the harmless switch's name, or a class
    # attribute of that name holding its number, passed as the harmless one.
    # A name is read off `sqlite3` (or `sqlite3.dbapi2`) only where the
    # module imports it as itself and binds that name no other way, and a
    # bare name only where it is imported from the driver unaliased and bound
    # no other way; any other is a switch the scan cannot read.
    driver_imported, from_driver, rebound = False, set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name in ("sqlite3", "sqlite3.dbapi2") and a.asname is None:
                    driver_imported = True
                else:
                    rebound.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if n.module in ("sqlite3", "sqlite3.dbapi2") and a.asname is None:
                    from_driver.add(a.name)
                else:
                    rebound.add(a.asname or a.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            rebound.add(n.id)
        elif isinstance(n, ast.arg):
            rebound.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            rebound.add(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            rebound.add(n.name)

    def the_drivers(op: ast.AST | None) -> str | None:
        if isinstance(op, ast.Attribute) and op.attr.startswith("SQLITE_DBCONFIG_"):
            base = op.value
            if isinstance(base, ast.Attribute) and base.attr == "dbapi2":
                base = base.value
            if (isinstance(base, ast.Name) and base.id == "sqlite3" and driver_imported
                    and "sqlite3" not in rebound):
                return op.attr
        elif (isinstance(op, ast.Name) and op.id.startswith("SQLITE_DBCONFIG_")
              and op.id in from_driver and op.id not in rebound):
            return op.id
        return None

    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and node.attr.startswith("SQLITE_DBCONFIG_")
                and isinstance(node.ctx, (ast.Store, ast.Del))):
            faults.append(
                f"{place(node)} binds `{node.attr}`, the driver's name for a "
                f"connection switch, to something else, so a switch passed by "
                f"that name may be another -- counted as a switch the scan "
                f"cannot read (operator question 25).")
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in ("setattr", "delattr") and len(node.args) >= 2
              and (_rendered_sql(node.args[1], set()) or "").startswith("SQLITE_DBCONFIG_")):
            faults.append(
                f"{place(node)} binds a name of the driver's connection "
                f"switches by `{node.func.id}`, so a switch passed by that name "
                f"may be another -- counted as a switch the scan cannot read "
                f"(operator question 25).")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr == "setconfig":
                op = node.args[0] if node.args else None
                name = the_drivers(op)
                if (isinstance(op, ast.Constant) and isinstance(op.value, int)
                        and not isinstance(op.value, bool)):
                    name = numbers.get(op.value, f"the switch numbered {op.value}")
                value = (True if len(node.args) < 2 else constant(node.args[1]))
                if name is None:
                    faults.append(
                        f"{place(node)} sets a connection switch the scan cannot "
                        f"read -- worked out when it runs -- so it is counted as "
                        f"one that turns the rules off. Name the switch.")
                elif name in RULE_DBCONFIG:
                    wanted, why = RULE_DBCONFIG[name]
                    if value is None or wanted is None or value == wanted:
                        said = ("to a value worked out when it runs" if value is None
                                else "on" if value else "off")
                        faults.append(
                            f"{place(node)} sets the connection switch "
                            f"`{name}` {said}: {why}. The rules are written and "
                            f"measured with it at SQLite's default; no shipped "
                            f"code may set it (operator question 25).")
            elif attr in _REGISTERING_CALLS:
                kind = _REGISTERING_CALLS[attr]
                arg = node.args[0] if node.args else next(
                    (k.value for k in node.keywords if k.arg == "name"), None)
                text = _rendered_sql(arg, set()) if arg is not None else None
                if text is None or _UNKNOWN_PART in text:
                    faults.append(
                        f"{place(node)} registers a {kind} (`{attr}`) under a "
                        f"name the scan cannot read, so it is counted as a "
                        f"built-in's. Name it in the call, and not as SQLite "
                        f"names one of its own.")
                elif text.casefold() in (sqlite_functions if kind == "function"
                                         else sqlite_collations):
                    faults.append(
                        f"{place(node)} registers a {kind} (`{attr}`) under the "
                        f"name `{text}`, which SQLite lists as its own: a rule "
                        f"calling it -- as the schema's rules call `json_valid` "
                        f"-- is answered by the connection in SQLite's place "
                        f"(measured: a value the rule refused landed). Give it "
                        f"a name of its own (operator question 25).")
            elif attr == "set_authorizer":
                if not (node.args and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value is None):
                    faults.append(
                        f"{place(node)} sets an authorizer, which can hand a "
                        f"rule's read back as NULL (measured: an insert a rule "
                        f"refused landed so) -- a rule switched off by a "
                        f"connection setting (operator question 25).")
            elif attr == "enable_load_extension":
                if not (node.args and constant(node.args[0]) is False):
                    faults.append(
                        f"{place(node)} lets the connection load an extension, "
                        f"and what one registers -- functions and collations, "
                        f"under any name, SQLite's own among them -- no scan "
                        f"can read (operator question 25).")
            elif attr == "load_extension":
                faults.append(
                    f"{place(node)} loads an extension, and what it registers "
                    f"-- functions and collations, under any name, SQLite's own "
                    f"among them -- no scan can read (operator question 25).")
        elif (isinstance(node, ast.Attribute) and node.attr in every_call
              and id(node) not in called and not isinstance(node.ctx, ast.Store)):
            faults.append(
                f"{place(node)} reaches `{node.attr}` by another name -- bound "
                f"or handed on -- so the scan cannot read what it sets or "
                f"registers. Call it where it is named.")
    # A LOOKUP BY NAME. Every string the module holds is read -- each constant,
    # each whole string expression as SQLite would be handed it (pieces
    # joined, a bytes literal decoded), and each template filled in with
    # constants -- word by word, in any case (the prover, 2026-09-29: the
    # name in pieces, formatted, as bytes, in capitals lowered, or in a
    # string handed to `exec`, each looked the call up unnamed). A word that
    # is a call's name, or that could be one around a part worked out at run
    # time, is a lookup by name; one place and name is one fault.
    strings = [(n, n.value) for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in prose]
    strings += _sql_strings_in(tree) + _roster_filled_in(tree)
    looked_up: dict[tuple[int, str], tuple[bool, ast.AST]] = {}
    for node, text in strings:
        if own_words and its_own(node):
            continue
        for _at, name, exact in _rule_names_in(text, every_call):
            key = (node.lineno, name)
            if key not in looked_up or (exact and not looked_up[key][0]):
                looked_up[key] = (exact, node)
    for (_line, name), (exact, node) in sorted(looked_up.items(),
                                               key=lambda item: item[0]):
        said = f"`{name}`" if exact else (
            f"what could be `{name}` around a part worked out when it runs")
        faults.append(
            f"{place(node)} names {said} in a string -- a lookup by name -- so "
            f"the scan cannot read what it sets or registers. Call it where it "
            f"is named (operator question 25).")
    return faults


def rule_switch_faults(root: Path | None = None,
                       register: dict | None = None,
                       frozen: frozenset | None = None) -> list[str]:
    """Every place the shipped code or the schema can switch the schema's
    rules off or rewrite their marks (operator questions 25 and 29, ruled
    2026-09-28): a setting or a switch that changes how a rule runs, a
    function or collation under a name SQLite lists as its own, an
    authorizer or an extension, a write of the sequence store the register
    does not name, and an insert of several rows under a clause that fails,
    ignores or rolls back aimed at an append-only table -- and from its
    prover (2026-09-29) a rule raising such a clause there, and a registered
    write whose statement is not the one it was made with -- and every
    register entry that is stale, doubled, undated or not among those it was
    made with. Each named by file, line and function. With the module's own
    register, `frozen` is `SEQUENCE_WRITES_REGISTERED_ON_2026_09_29`."""
    root = config.PACKAGE_ROOT if root is None else Path(root)
    if register is None:
        register = SEQUENCE_WRITES_REGISTERED
        frozen = SEQUENCE_WRITES_REGISTERED_ON_2026_09_29 if frozen is None else frozen
    base = root.parent
    functions_listed, collations_listed, settings_listed = _sqlite_own_names()
    numbers = _dbconfig_numbers()
    faults: list[str] = [
        f"audit.RULE_SETTINGS names `{name}`, which SQLite does not list as a "
        f"setting of its own: a refusal of a name no statement can set refuses "
        f"nothing."
        for name in sorted({*RULE_SETTINGS, *RULE_SETTING_VALUES})
        if name not in settings_listed]
    sources = _replace_scan_sources(root)
    protected, writes = _the_schemas_rules(sources)
    # EVERY RULE'S OWN INSERT OF SEVERAL ROWS (the prover, 2026-09-29), from
    # every text the scan reads: {the rule's table, None where it cannot be
    # read: [(the table the insert writes, or None; why several)]}. One row
    # under a ruled clause on a table whose rules do this is several rows
    # under that clause on the table they write.
    rule_rows: dict[str | None, list[tuple[str | None, str]]] = {}
    for _where, _kind, texts in sources:
        for entry in texts:
            for _i, kind, what in _rule_findings(entry[2], True):
                if kind == "rule rows":
                    on, into, how_several = what
                    rule_rows.setdefault(on, []).append((into, how_several))

    def why_set(name: str) -> str:
        if name in RULE_SETTINGS:
            return RULE_SETTINGS[name]
        value, why = RULE_SETTING_VALUES[name]
        return f"at {value}, or at a value the scan cannot read: {why}"

    def statement_at(text: str, start: int) -> str:
        """The statement beginning at `start` in `text`, as SQLite reads it:
        its words upper-cased, its names lower-cased, one space between."""
        tokens = _sql_tokens(text)
        k = next((i for i, t in enumerate(tokens) if t.start >= start), len(tokens))
        end = _sql_statement_end(tokens, k) if k < len(tokens) else 0
        return " ".join(t.word or t.value for t in tokens[k:]
                        if t.start < end and not (t.kind == "other" and t.value == ";"))

    def reached(table: str | None) -> set:
        """The table and every table its rules write: a rule's own writes
        carry the conflict clause of the statement that ran it."""
        seen, queue = {table}, [table]
        while queue:
            current = queue.pop()
            if current is None:
                continue
            for written in writes.get(current, ()):
                if written not in seen:
                    seen.add(written)
                    queue.append(written)
        return seen

    def rules_of(table: str) -> str:
        return ", ".join(f"`{r}`" for r in sorted(protected[table]))

    #: Every table an insert on an append-only table reaches through its
    #: rules: a rule on one of these raising FAIL stops that insert too.
    fed = set().union(*(reached(t) for t in protected)) if protected else set()

    found: dict[tuple[str, str, str], list[str]] = {}
    scan_itself_found: set[str] | None = None     # None: no audit module read

    def judge(where: str, line: int, function: str, how: str,
              offset_findings: list, text: str) -> None:
        for start, kind, what in offset_findings:
            at = line + text.count("\n", 0, start)
            place = f"{where}:{at} ({function})"
            if kind == "setting":
                if what is None:
                    faults.append(
                        f"{place} a setting whose name the scan cannot read -- a "
                        f"part of it, or all of it, worked out when it runs, or "
                        f"the string ending where it goes -- so it is counted as "
                        f"one that changes how the rules run (operator question "
                        f"25). Name the setting in the statement.")
                else:
                    faults.append(
                        f"{place} sets `{what}`: {why_set(what)}. The rules "
                        f"are written and measured with it at SQLite's default; "
                        f"no shipped code may set it (operator question 25).")
            elif kind == "setting apart":
                faults.append(
                    f"{place} sets `{what}` with no verb before it -- the verb "
                    f"worked out when it runs, in pieces, or kept apart -- so "
                    f"it is counted as set: {why_set(what)}. No shipped code may "
                    f"set it (operator question 25; its prover, 2026-09-29).")
            elif kind == "raise":
                clause, table = what
                if table is not None and table not in protected \
                        and not (reached(table) & set(protected)) and table not in fed:
                    continue
                if table is None:
                    counted = ("a rule whose table the scan cannot read is counted "
                               "as one on an append-only table")
                elif table in protected:
                    counted = (f"`{table}` is append-only: the schema gives it "
                               f"{rules_of(table)}")
                elif reached(table) & set(protected):
                    counted = (f"an insert on `{table}` writes the append-only "
                               + ", ".join(f"`{t}`" for t in sorted(
                                   reached(table) & set(protected))))
                else:
                    counted = f"an insert on an append-only table writes `{table}`"
                faults.append(
                    f"{place} a rule "
                    f"{'on `' + table + '`' if table else 'whose table the scan cannot read'} "
                    f"raising {clause or 'a clause worked out when it runs'}, and "
                    f"{counted}. A rule raising FAIL stops a plain insert of "
                    f"several rows part way, as OR FAIL does, and keeps the rows "
                    f"before it above SQLite's mark (measured: rows 3 and 4 above "
                    f"a mark of 2); the ruling refuses the three clauses alike "
                    f"(operator question 29; question 15's precedent for a key "
                    f"declared so, read for a rule by its prover, 2026-09-29).")
            elif kind == "extension":
                faults.append(
                    f"{place} loads an extension from SQL, and what it registers "
                    f"-- functions and collations, under any name -- no scan can "
                    f"read (operator question 25).")
            elif kind == "store":
                key = (where, function, what)
                if key in register:
                    found.setdefault(key, []).append(place)
                    if len(found[key]) > 1:
                        faults.append(
                            f"{place} a second write of `{SEQUENCE_STORE}` under "
                            f"one register entry (the first is {found[key][0]}). "
                            f"An entry names one statement; the register only "
                            f"shrinks.")
                        continue
                    # THE STATEMENT IT WAS MADE WITH (the prover, 2026-09-29).
                    made = SEQUENCE_WRITES_AS_MADE_ON_2026_09_29.get(key)
                    if made is not None and statement_at(text, start) != statement_at(made, 0):
                        faults.append(
                            f"{place} writes `{SEQUENCE_STORE}` ({what}) under its "
                            f"register entry, and the statement is not the one "
                            f"the register was made with (`{made}`): the ruling's "
                            f"one exception is the rebuild door carrying the mark "
                            f"exactly, and another statement under its entry is a "
                            f"second door (audit.SEQUENCE_WRITES_AS_MADE_ON_2026_09_29; "
                            f"the register only shrinks -- ask the operator).")
                    continue
                faults.append(
                    f"{place} writes `{SEQUENCE_STORE}` ({what}): SQLite's own "
                    f"table of AUTOINCREMENT marks, which the rules on the "
                    f"number written read and on which SQLite allows no rule, "
                    f"so a mark removed, set back or set forward round a move "
                    f"is seen by nothing (operator question 29). Only the "
                    f"rebuild door writes it (audit.SEQUENCE_WRITES_REGISTERED).")
            elif kind == "rows":
                clauses, table, several = what
                if several is None and how in ("executemany", "elsewhere"):
                    several = ("a statement handed to executemany, run once a row"
                               if how == "executemany" else
                               "a statement not handed whole to execute, which "
                               "the scan cannot see run once")
                aimed = reached(table)
                if several is None:
                    # ONE ROW, ON A TABLE A RULE OF WHICH INSERTS SEVERAL (the
                    # prover, 2026-09-29): the rule's insert runs under this
                    # statement's clause. A rule whose table cannot be read is
                    # counted as one on every table.
                    fanned = [(on, into, why) for on, rows in sorted(
                                  rule_rows.items(), key=lambda item: str(item[0]))
                              if on is None or on in aimed
                              for into, why in rows
                              if into is None or into in protected
                              or reached(into) & set(protected)]
                    if not fanned:
                        continue
                    on, into, why = fanned[0]
                    several = (
                        f"one row, and a rule on "
                        f"{'`' + on + '`' if on else 'a table the scan cannot read'} "
                        f"inserts {why} into "
                        f"{'`' + into + '`' if into else 'a table the scan cannot read'}"
                        f" under this statement's clause")
                    aimed = aimed | reached(into)
                guarded = sorted(t for t in aimed if t is not None and t in protected)
                if not guarded and None not in aimed:
                    continue
                counted = [f"`{t}` is append-only: the schema gives it {rules_of(t)}"
                           for t in guarded]
                if None in aimed:
                    counted.append("a table the scan cannot read is counted as "
                                   "append-only")
                faults.append(
                    f"{place} an insert of several rows ({several}) under "
                    f"{' and '.join(clauses)} on "
                    f"{'`' + table + '`' if table else 'a table worked out when it runs'}, "
                    f"and " + "; ".join(counted) + ". An insert of several rows "
                    f"that stops part way keeps the rows before the one that "
                    f"failed above SQLite's mark, where a number read twice "
                    f"writes over them, and the ruling refuses the three "
                    f"clauses alike (operator question 29). Write it plainly, "
                    f"or a row a statement.")
            elif kind == "key":
                clause, table = what
                if table is not None and table not in protected:
                    continue
                faults.append(
                    f"{place} a key of "
                    f"{'`' + table + '`' if table else 'a table the scan cannot read'} "
                    f"declared to "
                    f"{ {'FAIL': 'fail', 'IGNORE': 'ignore', 'ROLLBACK': 'roll back'}[clause] } "
                    f"whenever an insert meets it, and "
                    + (f"`{table}` is append-only: the schema gives it "
                       f"{rules_of(table)}" if table else
                       "a table the scan cannot read is counted as append-only")
                    + ". Every plain insert of several rows on it then runs under "
                    f"that clause for the key (operator question 29; question "
                    f"15's precedent for a key declared to replace).")

    for path in _shipped_python_files(root):
        where = path.relative_to(base).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = _qualified_functions(tree)
        parents = {id(child): node for node in ast.walk(tree)
                   for child in ast.iter_child_nodes(node)}
        own_words = where == "gridiron/audit.py"
        if own_words:
            scan_itself_found = {f for f in functions.values() if f} & _RULE_SCAN_ITSELF

        def in_a_holder(node: ast.AST) -> bool:
            """Is `node` inside the assignment of one of this module's values
            holding a word this scan looks for -- its own words, not code?
            (An annotated one too: the prover, 2026-09-29.)"""
            while node is not None:
                if isinstance(node, ast.Assign):
                    return any(isinstance(t, ast.Name) and t.id in _RULE_WORD_HOLDERS
                               for t in node.targets)
                if isinstance(node, ast.AnnAssign):
                    return (isinstance(node.target, ast.Name)
                            and node.target.id in _RULE_WORD_HOLDERS)
                node = parents.get(id(node))
            return False

        def its_own(node: ast.AST) -> bool:
            return (in_a_holder(node) or (functions.get(id(node)) or "").split(".")[0]
                    in _RULE_SCAN_ITSELF)

        for node, text in _sql_strings_in(tree):
            if own_words and in_a_holder(node):
                continue                 # this scan's own words: what it looks for
            how = _how_it_is_run(node, parents)
            judge(where, node.lineno, functions.get(id(node)) or "module level", how,
                  _rule_findings_in(text, how != "elsewhere", True), text)
        # A TEMPLATE FILLED IN WITH CONSTANTS ALONE, read again whole.
        for node, text in _roster_filled_in(tree):
            if own_words and in_a_holder(node):
                continue
            how = _how_it_is_run(node, parents)
            judge(where, node.lineno, functions.get(id(node)) or "module level", how,
                  [(0, kind, what) for _s, kind, what
                   in _rule_findings_in(text, how != "elsewhere", False)], text)
        faults.extend(_rule_call_faults(where, tree, functions, own_words,
                                        functions_listed, collations_listed, numbers,
                                        its_own))
        # A WORD THIS SCAN LOOKS FOR, BY THE NAME OF A VALUE HOLDING IT -- as
        # Python names it, and (the prover, 2026-09-29) by a string the scan
        # can render: `getattr(audit, "SEQUENCE" + "_STORE")`.
        references = list(_roster_references(tree, _RULE_WORD_HOLDERS))
        for node, text in _sql_strings_in(tree) + _roster_filled_in(tree):
            references += [(node, name) for _at, name, _exact
                           in _rule_names_in(text, _RULE_WORD_HOLDERS)]
        for node, name in references:
            function = functions.get(id(node)) or "module level"
            if own_words and (function.split(".")[0] in _RULE_SCAN_ITSELF
                              or function == "module level"):
                continue                 # the scan's own words, as the roster's
            if _RULE_WORD_HOLDERS[name] == "store":
                faults.append(
                    f"{where}:{node.lineno} ({function}) names `{name}`, "
                    f"audit's value holding the sequence store's name, which "
                    f"the scan cannot place: counted as a write of it "
                    f"(operator question 29).")
            elif _RULE_WORD_HOLDERS[name] == "call":
                faults.append(
                    f"{where}:{node.lineno} ({function}) names `{name}`, "
                    f"audit's value holding the names of the calls that set a "
                    f"connection's switches or register a function: counted as "
                    f"such a call reached by another name, whose switch or "
                    f"name the scan cannot read (operator question 25).")
            else:
                faults.append(
                    f"{where}:{node.lineno} ({function}) names `{name}`, "
                    f"audit's value holding the word that opens a setting, or "
                    f"the names of the settings it refuses: counted as a "
                    f"setting whose name the scan cannot read (operator "
                    f"question 25).")
    for missing in (sorted(_RULE_SCAN_ITSELF - scan_itself_found)
                    if scan_itself_found is not None else []):
        faults.append(
            f"gridiron/audit.py ({missing}): listed in audit._RULE_SCAN_ITSELF, "
            f"the scan's own functions, and no longer found: remove it.")
    for path in sorted(root.rglob("*.sql")):
        where = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8")
        tokens = _sql_tokens(text)
        objects = _sql_objects(tokens)
        for start, kind, what in _rule_findings_in(text, True, False):
            # The object whose statement holds it; a statement after an
            # object's end is the file's own (2026-09-29).
            holder = [o for o in objects if tokens[o[0]].start <= start
                      and start < _sql_statement_end(tokens, o[0])]
            function = f"{holder[-1][1]} {holder[-1][2]}" if holder else "module level"
            judge(where, 1, function, "sql", [(start, kind, what)], text)

    for key, reason in sorted(register.items()):
        where, function, verb = key
        name = f"{where} ({function}) {verb}"
        if key not in found:
            faults.append(
                f"{name}: registered in audit.SEQUENCE_WRITES_REGISTERED and no "
                f"longer found. The register only shrinks: remove the entry.")
        if not re.match(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}: \S", str(reason)):
            faults.append(
                f"{name}: registered without a dated reason in words "
                f"(\"2026-09-29: the verified rebuild door ...\").")
        if frozen is not None and key not in frozen:
            faults.append(
                f"{name}: registered in audit.SEQUENCE_WRITES_REGISTERED and not "
                f"among the entries it was made with "
                f"(audit.SEQUENCE_WRITES_REGISTERED_ON_2026_09_29). The ruling's "
                f"one exception is the rebuild door's; the register may only "
                f"shrink -- ask the operator.")
    # One place read two ways (a template's constant argument and the
    # template filled in) is one fault.
    return list(dict.fromkeys(faults))


def check_no_code_switches_the_rules_off_or_rewrites_their_marks(
        root: Path | None = None) -> None:
    """Raise unless no shipped code or schema can switch the rules off or
    rewrite their marks (operator questions 25 and 29; gate step 2)."""
    faults = rule_switch_faults(root)
    if faults:
        raise LawViolation(
            f"CODE CAN SWITCH THE RULES OFF OR REWRITE THEIR MARKS (operator "
            f"question 25, ruled 2026-09-28: the scan refuses code that turns "
            f"the rules off by a connection setting or registers a function "
            f"under a built-in's name; question 29, folded into it: code that "
            f"writes `{SEQUENCE_STORE}` but the rebuild door, and an insert of "
            f"several rows under OR FAIL, OR IGNORE or OR ROLLBACK on an "
            f"append-only table):" + _NL2 + _NL2.join(faults))


def _check_the_rule_scan_names_the_store_once() -> None:
    """Every value of this module holding the sequence store's name, or the
    word alone that opens a setting -- and from the prover (2026-09-29) a
    listed setting's name or a registering or switching call's name as a
    whole string -- is one of `_RULE_WORD_HOLDERS`, so no value holding any
    of them is read by its own name elsewhere past the scan; the store's name
    is read however it is spelled, and the prover's readings are read."""
    whole_words = {*RULE_SETTINGS, *RULE_SETTING_VALUES,
                   *_REGISTERING_CALLS, *_RULE_SWITCH_CALLS}

    def strings_of(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for k, v in value.items():
                yield from strings_of(k)
                yield from strings_of(v)
        elif isinstance(value, (list, tuple, set, frozenset)):
            for v in value:
                yield from strings_of(v)

    holding = set()
    for name, value in globals().items():
        if callable(value) or type(value).__name__ == "module":
            continue
        shown = repr(value)
        if (SEQUENCE_STORE in shown or repr(_SETTING_VERB) in shown.upper()
                or whole_words & set(strings_of(value))):
            holding.add(name)
    problems = []
    if holding != set(_RULE_WORD_HOLDERS):
        problems.append(f"this module's values holding the store's name or the "
                        f"setting's word are {sorted(holding)}, and "
                        f"audit._RULE_WORD_HOLDERS lists {sorted(_RULE_WORD_HOLDERS)}")
    spelled = ('"' + SEQUENCE_STORE.upper() + '"', "[" + SEQUENCE_STORE + "]",
               "main.`" + SEQUENCE_STORE + "`", "'" + SEQUENCE_STORE + "'",
               SEQUENCE_STORE[:7] + _UNKNOWN_PART, _UNKNOWN_PART + SEQUENCE_STORE[6:])
    for text in spelled:
        if not _names_the_store(_rule_target(_sql_tokens(text), 0)[0]):
            problems.append(f"{text!r} is not read as the store")
    if _names_the_store(_rule_target(_sql_tokens(SEQUENCE_STORE + "_x"), 0)[0]):
        problems.append("another table read as the store")
    # THE PROVER'S READINGS (2026-09-29), each a way past the scan as first
    # built. No setting's or call's name is written here: this function is
    # read by its own scan.
    journal = next(iter(RULE_SETTING_VALUES))
    off = RULE_SETTING_VALUES[journal][0]
    readings = {
        "the store's name with its condition after it": (
            _rule_findings(_sql_tokens(SEQUENCE_STORE + " WHERE seq > 0"), False), "store"),
        "a FROM beginning a string": (
            _rule_findings(_sql_tokens("FROM " + SEQUENCE_STORE), False), "store"),
        "a setting refused at its value": (
            _rule_findings(_sql_tokens(f"{_SETTING_VERB} {journal} = {off}"), True), "setting"),
        "a setting's name with no verb before it": (
            _rule_findings(_sql_tokens(f"{_UNKNOWN_PART} {journal} = {off}"), True),
            "setting apart"),
    }
    for what, (findings, kind) in readings.items():
        if kind not in {k for _i, k, _w in findings}:
            problems.append(f"{what} is not read ({findings})")
    if not {name for _a, name, _e in _rule_names_in(
            _RULE_SWITCH_CALLS[0][:3] + _UNKNOWN_PART, _RULE_SWITCH_CALLS)} >= {
            _RULE_SWITCH_CALLS[0]}:
        problems.append("a switching call's name in pieces is not read")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_rule_scan_names_the_store_once()


# THE BOARD (GRIDIRON_BOARD, operator ruling 2026-09-24)
# ---------------------------------------------------------------------------
#
# Three guards the board brought with it, each proved by a planting:
#
#   * A SIGNAL NEVER RENDERS WITHOUT ITS BADGE. A green outline beside no
#     sample size is the most persuasive thing on the page and says nothing
#     about how much stands behind it -- LAW 4, on the row.
#   * A CLUB'S COLOUR IS MEASURED, NEVER TYPED. `data/team_colours.py` is
#     generated from the feed the names come from; a hex typed into the
#     stylesheet, the renderer or a composer is a second copy that will
#     disagree with it, and a jersey drawn from it would be a guess wearing
#     a club's identity.
#   * A LIVE ROW CARRIES NO PRICE, NO SIZE AND NO TAP. `live_card_faults`
#     already ruled the old card; `LIVE_FORBIDDEN` names the board's own
#     field names as well, so the same walk covers the rows.

#: The four signals, and the two that must be earned before they show.
BOARD_SIGNALS = ("clears", "costs", "won", "lost")
BOARD_GLOWS = ("clears", "costs")


def board_signal_faults(payload) -> list[str]:
    """A row or a tile wearing a signal with no record badge beside it."""
    board = (payload or {}).get("board") or {}
    faults: list[str] = []

    def check(node, where):
        if not isinstance(node, dict):
            return
        signal = node.get("signal")
        if signal in BOARD_SIGNALS and not node.get("badge_words"):
            faults.append(
                f"{where} wears the {signal!r} signal with no record badge "
                f"beside it. A glow or a fill beside no sample size is the "
                f"most persuasive thing on the page and says nothing about "
                f"how much stands behind it (LAW 4).")
        if signal in BOARD_SIGNALS and node.get("badge_n") is None:
            faults.append(f"{where} wears {signal!r} and its badge has no count")

    for i, game in enumerate(board.get("games") or []):
        check(game.get("pick"), f"board.games[{i}].pick")
        for j, q in enumerate(game.get("questions") or []):
            check(q, f"board.games[{i}].questions[{j}]")
    for i, chip in enumerate((board.get("my_day") or {}).get("entries") or []):
        check(chip, f"board.my_day.entries[{i}]")
    for i, tile in enumerate((board.get("props") or {}).get("tiles") or []):
        check(tile, f"board.props.tiles[{i}]")
        # RULING c, 2026-09-25: a prop tile wears no outline until a real
        # multiplier exists for its line -- read from a venue, or typed in
        # the entry rail. The tile's own multiple is DECLARED, and a cushion
        # against a declared number is arithmetic, not an edge. The colour is
        # earned in the rail, against the number the operator typed.
        if tile.get("signal") in ("clears", "costs") and tile.get("multiple_source") != "read":
            faults.append(
                f"board.props.tiles[{i}] wears the {tile.get('signal')!r} outline "
                f"against a multiplier the app assumed "
                f"({tile.get('multiple_source') or 'none'}). A prop tile's "
                f"outline needs a multiplier that was READ for that line; until "
                f"one is, the cushion shows and the colour does not (ruled "
                f"2026-09-25).")
        if tile.get("alt") and not tile.get("high_end_badge_words"):
            faults.append(
                f"board.props.tiles[{i}] is an alt line with no high-end "
                f"record badge: an alt line is a claim near the top of the "
                f"range, and the record there is its own")
    return faults


def check_the_board_signals_carry_their_badges(payload) -> None:
    faults = board_signal_faults(payload)
    if faults:
        raise LawViolation(
            "A SIGNAL WITHOUT ITS BADGE:" + _NL2 + _NL2.join(faults[:6]))


BOARD_SIGNAL_FIXTURE_GOOD = {"board": {"games": [{"pick": {
    "signal": "clears", "badge_words": "12/100", "badge_n": 12}}]}}
BOARD_SIGNAL_FIXTURE_BARE = {"board": {"games": [{"pick": {
    "signal": "clears", "badge_words": None}}]}}
#: A prop tile lit against the DECLARED multiple (ruling c, 2026-09-25) and
#: the same tile against one that was read, which the scan must let stand.
BOARD_SIGNAL_FIXTURE_ASSUMED = {"board": {"props": {"tiles": [{
    "signal": "clears", "badge_words": "12/100", "badge_n": 12,
    "multiple_source": "declared"}]}}}
BOARD_SIGNAL_FIXTURE_READ = {"board": {"props": {"tiles": [{
    "signal": "clears", "badge_words": "12/100", "badge_n": 12,
    "multiple_source": "read"}]}}}


#: Where a hand-typed club hex would sit: the web files and the composers
#: that hand colours to the page. The generated colour file is the one place
#: a club's hex belongs, and `tools/measure_team_colours.py` writes it.
CLUB_HEX_SCAN = (
    "web/app.js", "web/style.css", "web/index.html", "web/login.html",
    "board.py", "views.py", "language.py",
)
_HEX_LITERAL = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def _club_hexes() -> dict[str, str]:
    from .data.team_colours import TEAM_COLOURS

    out: dict[str, str] = {}
    for sport, clubs in TEAM_COLOURS.items():
        for code, (primary, on_white, _how) in clubs.items():
            out.setdefault(primary.lower(), f"{sport} {code}")
            out.setdefault(on_white.lower(), f"{sport} {code}")
    return out


def club_hex_faults(root: Path | None = None, texts: dict | None = None) -> list[str]:
    """A colour literal in the web files or the composers that is a club's."""
    root = root or config.PACKAGE_ROOT
    clubs = _club_hexes()
    faults = []
    sources = texts if texts is not None else {
        name: (root / name).read_text(encoding="utf-8")
        for name in CLUB_HEX_SCAN if (root / name).is_file()}
    for name, text in sources.items():
        kind = "css" if name.endswith(".css") else ("html" if name.endswith(".html") else "js")
        if name.endswith(".py"):
            text = _python_without_comments(text)
        else:
            text = _without_comments(text, kind)
        for n, line in enumerate(text.split("\n"), 1):
            for match in _HEX_LITERAL.finditer(line):
                hexed = match.group(1).lower()
                if len(hexed) == 3:
                    hexed = "".join(c * 2 for c in hexed)
                if hexed in clubs:
                    faults.append(
                        f"{name} line {n} types #{match.group(1)}, which is "
                        f"{clubs[hexed]}'s measured colour. A club's colour "
                        f"comes from data/team_colours.py and nowhere else; a "
                        f"second copy is one that will disagree with it.")
    return faults


def check_no_hand_typed_club_hex(root: Path | None = None) -> None:
    faults = club_hex_faults(root)
    if faults:
        raise LawViolation(
            "A CLUB'S COLOUR WAS TYPED, NOT MEASURED:" + _NL2 + _NL2.join(faults[:6]))


#: The board's own fields a live row may not carry, added to the old card's
#: list so one walk rules both.
LIVE_FORBIDDEN = LIVE_FORBIDDEN + ("pays_words", "size_words", "edge_words")

#: The board's texts a reader meets: every one is scanned for internal
#: vocabulary, pressure and advice, tooltips included.
BOARD_TEXT_KEYS = (
    "line_words", "question", "prob_words", "price_words", "pays_words",
    "size_words", "edge_words", "pregame_words", "settled_words",
    "badge_words", "high_end_badge_words", "cushion_words", "breakeven_words",
    "venue_words", "family_words", "questions_words", "no_pick_words",
    "yours_words", "score_words", "period_words", "polled_words",
    "games_empty_words", "nothing_clears_words", "note", "empty_words",
    "status_words", "counts_words", "heading", "home_form_words", "away_form_words",
    "home_form_tip", "away_form_tip", "injuries_words", "weather_words",
    "factors_words", "factor_words",
    "alt_empty_words", "label", "heading", "empty", "kalshi_absent",
    "market_label", "forecaster_label", "player", "surname", "name",
)


def _without_declared_factor_phrases(text: str) -> str:
    """`text` with every declared factor's own phrase (the registry's `why`)
    blanked, for the advice scan alone (the board merge, 2026-09-29): a
    factor's name is a noun about the game, whatever verb it looks like."""
    from .factors import registry

    out = text or ""
    for factor in registry.REGISTRY.values():
        phrase = getattr(factor, "why", None)
        if phrase:
            out = re.sub(re.escape(phrase), " ", out, flags=re.I)
    return out


def board_words_faults(payload) -> list[str]:
    """Internal vocabulary, pressure or advice anywhere on the board, the
    tooltips included."""
    board = (payload or {}).get("board")
    if not board:
        return []
    faults: list[str] = []

    def scan(text, where):
        # A TOOLTIP MAY CARRY A VERSION NAME, and only a tooltip (operator
        # question 19; the board merge, 2026-09-29).
        for fault in plain_words_violations(
                text, in_a_tooltip=where.endswith("(a tooltip)")):
            faults.append(f"{where}: {fault}")
        for fault in pressure_word_faults(text):
            faults.append(f"{where}: {fault}")
        # A DECLARED FACTOR'S PHRASE ("how many plays both offences run") is
        # the registry's own name for it, read for internal vocabulary and
        # pressure like everything else, and not for advice: the advice scan
        # reads "plays" as a verb, and the phrase is a noun about the game.
        # AND WHERE A SENTENCE QUOTES ONE (the board merge, 2026-09-29): the
        # reasons on a pick's tooltip are the old card's Why sentences, built
        # from the same phrases -- "Mostly it comes down to how many plays
        # both offences run" -- and on the live record's NFL slate twelve of
        # them failed this scan, which the board, built with no record, never
        # met. The declared phrases are taken out of the text before the
        # advice scan reads the rest of the sentence, which is still read.
        if not where.endswith(".factor_words"):
            for fault in advice_word_faults(
                    _without_declared_factor_phrases(text), where):
                faults.append(fault)

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{path}.{key}" if path else str(key)
                if key == "tips" and isinstance(value, dict):
                    for tkey, words in value.items():
                        if isinstance(words, str):
                            scan(words, f"{here}.{tkey} (a tooltip)")
                    continue
                if key in BOARD_TEXT_KEYS and isinstance(value, str):
                    scan(value, here)
                walk(value, here)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(board, "board")
    return sorted(set(faults))


def check_the_board_speaks_plain(payload) -> None:
    faults = board_words_faults(payload)
    if faults:
        raise LawViolation(
            "THE BOARD SHOWS A WORD A READER SHOULD NOT MEET:"
            + _NL2 + _NL2.join(faults[:8]))


def _check_the_board_scanners_can_see() -> None:
    problems = []
    if board_signal_faults(BOARD_SIGNAL_FIXTURE_GOOD):
        problems.append("board_signal_faults flags a badged signal")
    if not board_signal_faults(BOARD_SIGNAL_FIXTURE_BARE):
        problems.append("board_signal_faults misses a glow with no badge")
    if not board_signal_faults(BOARD_SIGNAL_FIXTURE_ASSUMED):
        problems.append("board_signal_faults misses an outline on a prop tile "
                        "against an assumed multiplier")
    if board_signal_faults(BOARD_SIGNAL_FIXTURE_READ):
        problems.append("board_signal_faults refuses an outline against a "
                        "multiplier that was read")
    sample = next(iter(_club_hexes()))
    if not club_hex_faults(texts={"web/app.js": f"const x = '#{sample}';"}):
        problems.append("club_hex_faults misses a typed club hex")
    if club_hex_faults(texts={"web/app.js": "const x = '#0F1114';"}):
        problems.append("club_hex_faults flags the page's own ground")
    if not board_words_faults({"board": {"games": [{"pick": {
            "tips": {"prob": "a hot rushing_yards lock"}}}]}}):
        problems.append("board_words_faults misses a tooltip")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_board_scanners_can_see()


# ---------------------------------------------------------------------------
# THE BOARD MERGE'S OWN GUARDS (the merge checklist of 2026-09-27, with its
# third-set additions; built 2026-09-29)
# ---------------------------------------------------------------------------
#
# HEADINGS IN PLAIN WORDS, AN INTERNAL VERSION NAME ONLY IN A TOOLTIP
# (operator question 19, ruled 2026-09-27: "fixed in the board: headings in
# plain words; internal version names only in a tooltip"). The Record page
# painted the blend's version "b1" beside the heading "Priced, and against
# the close" on every sport, and the ordering's "r3" beside "Did the ordering
# earn its place"; the correction lines said "version 8 is in force since
# ...". A version name is how a stored row is matched to what wrote it; a
# reader needs it to match, never to read. `plain_words_violations` refuses
# one in visible text from this merge (`version_name_violations`, above it),
# and a tooltip may carry it. Two more places are read for it here, in the
# gate where no browser runs:
#
#   * every heading index.html writes, a `<small>` beside the words included
#     (`heading_words_faults`); the words a heading is given at render time
#     are the server's, read by the payload scans and the rendered pages;
#   * the renderer placing a payload's `..._version` field as visible text --
#     `textContent`, `innerText`, `innerHTML`, or the text argument of
#     `el(tag, cls, text)` -- where a `title` may carry it
#     (`version_painted_faults`).
#
# NOT SEEN (FOLLOWUPS): a version name placed by the renderer from a field
# not named `..._version`, and one inside a `.code-literal` block, which the
# rendered pages' scan leaves out on purpose (the prompt disclosure's
# verbatim text).

_HEADING = re.compile(r"<(h[1-6])\b[^>]*>(?P<body>.*?)</\1>", re.S | re.I)


def heading_words_faults(html: str | None = None) -> list[str]:
    """A heading in index.html that is not plain words -- a version name or
    an identifier inside it included (question 19)."""
    if html is None:
        html = (config.PACKAGE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    html = _without_comments(html, "html")
    faults = []
    for match in _HEADING.finditer(html):
        text = " ".join(re.sub(r"<[^>]+>", " ", match.group("body")).split())
        for fault in plain_words_violations(text):
            line = html.count(chr(10), 0, match.start()) + 1
            faults.append(f"index.html:{line} <{match.group(1)}> {text!r}: {fault}")
    return faults


#: The renderer placing a payload's version field as visible text.
_JS_VERSION_PAINTED = re.compile(
    r"(?:\.(?:textContent|innerText|innerHTML)\s*=[^;\n]*|"
    r"\bel\(\s*'[^']*'\s*,\s*[^,()]*,\s*[^;\n]*)"
    r"\b[A-Za-z_$][\w$]*\.(?P<field>\w*_version)\b")


def version_painted_faults(js: str | None = None) -> list[str]:
    """The renderer painting a `..._version` field as visible text (q19)."""
    if js is None:
        js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    js = _without_comments(js, "js")
    faults = []
    for match in _JS_VERSION_PAINTED.finditer(js):
        line = js.count(chr(10), 0, match.start()) + 1
        faults.append(
            f"app.js:{line} paints `{match.group('field')}` as visible text. "
            f"An internal version name appears only in a tooltip (operator "
            f"question 19, 2026-09-27): set it as a `title`, beside words "
            f"that say what the panel is.")
    return faults


def check_headings_are_plain_words() -> None:
    faults = heading_words_faults() + version_painted_faults()
    if faults:
        raise LawViolation(
            "A HEADING IS NOT PLAIN WORDS, OR A VERSION NAME IS PAINTED "
            "(operator question 19, ruled 2026-09-27: headings in plain words; "
            "internal version names only in a tooltip):"
            + _NL2 + _NL2.join(faults[:8]))


#: The Record page's priced heading as it shipped until the merge, and the
#: renderer line that painted the blend's name into it; and as they ship
#: now. Checked at import, like every scanner.
HEADING_FIXTURE_PAINTED = (
    '<h3>Priced, and against the close <small id="priced-version">b1</small></h3>',
    "    if (version && priced) version.textContent = priced.blend_version || '';")
HEADING_FIXTURE_PLAIN = (
    '<h3 id="priced-heading" title="Version b1">Priced, and against the close</h3>',
    "    if (heading && priced) heading.title = priced.version_tip || '';")


def _check_the_version_scanners_can_see() -> None:
    problems = []
    html, js = HEADING_FIXTURE_PAINTED
    if not heading_words_faults(html):
        problems.append("heading_words_faults misses 'b1' beside a heading")
    if not version_painted_faults(js):
        problems.append("version_painted_faults misses a version painted as text")
    html, js = HEADING_FIXTURE_PLAIN
    if heading_words_faults(html) or version_painted_faults(js):
        problems.append("the version scans refuse a heading with its name in a title")
    if not version_name_violations("version 8 is in force since Monday"):
        problems.append("version_name_violations misses a correction's number")
    if version_name_violations("Since the repair, statistical: 12 of 50"):
        problems.append("version_name_violations flags plain words")
    if plain_words_violations("Version b1: the blend.", in_a_tooltip=True):
        problems.append("plain_words_violations refuses a version name in a tooltip")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_version_scanners_can_see()


# ---------------------------------------------------------------------------
# THE BOARD'S COUNTS AND ITS PRICED NUMBERS (the prover of the board merge,
# 2026-09-29)
# ---------------------------------------------------------------------------
#
# Found by walking repair's behaviour through the merged board, each on a
# real payload, none seen by the merge's own guards:
#
#   * MY DAY COUNTED A TAKEN PROP TWICE. A prop question is on its game's row
#     and is a tile, and My day read both: one tap, two chips, "2 taken".
#   * A GAME ROW'S COUNT POOLED THE FORECASTERS. "4 questions on this game"
#     over three of the model's and one of the reasoning pass's, a question
#     both answered counted twice under the word "question" -- the pooled
#     figure operator questions 14 and 22 took off every other panel.
#   * RESULTS' SETTLED HEADING COUNTED ONE SET AND HEADED ANOTHER: the Today
#     block's settled cards ("Settled -- 15 questions") above every question
#     on every finished row, both forecasters'.
#   * A PRICED ROW'S NUMBERS WERE NOT THE CARD'S. The merge read the entry's
#     corrected `fair_value` for a priced question's chance (GRIDIRON_REPAIR
#     item 3, operator question 32's door) from the Today card, which never
#     carried it, so the chance was the stored number; and the price and the
#     payout were the claim's fixed proposition's, never turned to the side
#     the question names -- the wrong-side defect of 2026-09-07 -- so an away
#     side's question read 57% beside the home side's 48c and 2.06x, where
#     the card said 46c against 52c.
#
# `board_count_faults` recounts the first three from the payload's own
# blocks and composes the row's words again; `board_price_side_faults` holds
# each priced block to its Today card: the chance the card's chip states
# (`model_words`, the released chip, corrected and turned), and the card's
# price and payout turned by the card's own `question_takes_the_proposition`
# -- and refuses a priced card that carries no `fair_value`, the shape the
# merge's reading met on every real payload. Both run in gate step 2 over
# every sport's slate on the record's copy.


def board_count_faults(payload) -> list[str]:
    """A count on the board that counts a bet twice, pools the forecasters,
    or states another count than the blocks it heads."""
    from . import language as _language

    board = (payload or {}).get("board") or {}
    if not board:
        return []
    faults: list[str] = []
    chosen = (payload or {}).get("forecaster") or config.PICKS_DEFAULT_FORECASTER
    games = board.get("games") or []
    tiles = ((board.get("props") or {}).get("tiles")) or []
    # MY DAY: each taken question once, none lost, and the count its chips'.
    day = board.get("my_day") or {}
    entries = day.get("entries") or []
    ids = [e.get("prediction_id") for e in entries]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    if twice:
        faults.append(
            f"board.my_day counts taken question(s) {twice} more than once: a "
            f"prop is on its game's row and is a tile, and one tap is one chip")
    taken = {q.get("prediction_id") for g in games for q in (g.get("questions") or [])
             if q.get("taken")} | {t.get("prediction_id") for t in tiles if t.get("taken")}
    if set(ids) != taken:
        faults.append(
            f"board.my_day holds {sorted(i for i in set(ids) if i is not None)} "
            f"and the board's taken questions are {sorted(i for i in taken if i is not None)}")
    if day and day.get("n") != len(entries):
        faults.append(
            f"board.my_day says {day.get('n')!r} taken over {len(entries)} chips")
    # EACH ROW'S QUESTIONS, EACH FORECASTER'S APART.
    for i, game in enumerate(games):
        blocks = game.get("questions") or []
        recount: dict = {}
        for q in blocks:
            recount[q.get("forecaster")] = recount.get(q.get("forecaster"), 0) + 1
        stated = game.get("questions_n")
        if not isinstance(stated, dict):
            faults.append(
                f"board.games[{i}] carries no count per forecaster "
                f"({stated!r}): a row's questions are each forecaster's, "
                f"counted apart (operator questions 14 and 22)")
            continue
        if {f: n for f, n in stated.items() if n} != recount:
            faults.append(
                f"board.games[{i}] counts {stated} and its blocks are {recount}")
        words = _language.game_questions_words(recount, chosen)
        if game.get("questions_words") != words:
            faults.append(
                f"board.games[{i}] says {game.get('questions_words')!r} where its "
                f"blocks, each forecaster's apart, say {words!r}")
    # RESULTS' SETTLED TILES ARE THE HEADING'S OWN QUESTIONS.
    if "settled_ids" in board:
        heading_set = {c.get("prediction_id") for c in
                       (((payload or {}).get("today") or {}).get("settled") or [])}
        named = board.get("settled_ids") or []
        if set(named) != heading_set or len(named) != len(set(named)):
            faults.append(
                f"board.settled_ids {sorted(named)} are not the questions the "
                f"settled heading counts {sorted(heading_set)}")
        finished = {q.get("prediction_id") for g in games if g.get("state") == "final"
                    for q in (g.get("questions") or []) if q.get("forecaster") == chosen}
        stray = sorted(set(named) - finished)
        if stray:
            faults.append(
                f"board.settled_ids names {stray}, which no finished row of "
                f"the page's forecaster holds")
    return faults


def check_the_board_counts_each_bet_once(payload) -> None:
    faults = board_count_faults(payload)
    if faults:
        raise LawViolation(
            "THE BOARD COUNTS A BET TWICE, POOLS THE FORECASTERS OR STATES "
            "ANOTHER COUNT THAN IT SHOWS:" + _NL2 + _NL2.join(faults[:8]))


def board_price_side_faults(payload) -> list[str]:
    """A priced block of the board whose chance, price or payout is not the
    Today card's, turned to the side the question names."""
    from .market import recommend as _recommend

    board = (payload or {}).get("board") or {}
    today = (payload or {}).get("today") or {}
    if not board or not today:
        return []
    cards = {c.get("prediction_id"): c for group in ("clears", "below_floor", "watching")
             for c in (today.get(group) or []) if isinstance(c, dict)}
    faults: list[str] = []

    def check(block, where):
        card = cards.get((block or {}).get("prediction_id"))
        if card is None or block.get("state") != "upcoming" or card.get("state") == "live":
            return
        if card.get("model_words") and "fair_value" not in card:
            faults.append(
                f"{where}: its Today card states the chip {card['model_words']!r} "
                f"and carries no `fair_value`, so the board cannot read the "
                f"corrected number the chip states (GRIDIRON_REPAIR item 3)")
            return
        fair = card.get("fair_value")
        flip = card.get("question_takes_the_proposition") is False
        if fair is not None:
            chance = 1.0 - fair if flip else fair
            if block.get("prob") is None or abs(block["prob"] - chance) > 1e-9:
                faults.append(
                    f"{where} shows the chance {block.get('prob')!r} where its "
                    f"card's corrected number, on the question's side, is "
                    f"{chance!r} (item 3; question 32's door)")
            chip = (card.get("model_words") or "").replace("¢", "%")
            if chip and block.get("prob_words") != chip:
                faults.append(
                    f"{where} says {block.get('prob_words')!r} where its card's "
                    f"chip says {card.get('model_words')!r}")
        price = card.get("price")
        if price is not None:
            side = 1.0 - price if flip else price
            if block.get("price") is None or abs(block["price"] - side) > 1e-9:
                faults.append(
                    f"{where} shows the price {block.get('price')!r} where the "
                    f"side its question names costs {side!r}: a price of the "
                    f"claim's fixed proposition under a question naming the "
                    f"other side is the wrong-side defect of 2026-09-07")
            pays = _recommend.payout_multiple(side) if flip else card.get("payout")
            if pays is not None and (block.get("pays") is None
                                     or abs(block["pays"] - pays) > 1e-9):
                faults.append(
                    f"{where} shows the payout {block.get('pays')!r} where the "
                    f"side its question names pays {pays!r}")

    for i, game in enumerate(board.get("games") or []):
        if game.get("pick"):
            check(game["pick"], f"board.games[{i}].pick")
        for j, q in enumerate(game.get("questions") or []):
            check(q, f"board.games[{i}].questions[{j}]")
    for i, tile in enumerate(((board.get("props") or {}).get("tiles")) or []):
        check(tile, f"board.props.tiles[{i}]")
    return faults


def check_the_board_prices_the_side_it_names(payload) -> None:
    faults = board_price_side_faults(payload)
    if faults:
        raise LawViolation(
            "A PRICED ROW OF THE BOARD IS NOT ITS CARD'S NUMBERS ON THE SIDE "
            "ITS QUESTION NAMES:" + _NL2 + _NL2.join(faults[:8]))


#: One upcoming priced question naming the claim's other side (the away
#: side at a 48.5c home price, a correction in force: the chip 46c), as the
#: payload carries it -- and as the merge carried it.
BOARD_PRICED_FIXTURE_GOOD = {
    "forecaster": "statistical",
    "today": {"clears": [{"prediction_id": 1, "state": "upcoming",
                          "model_words": "46¢", "fair_value": 0.5358,
                          "question_takes_the_proposition": False,
                          "price": 0.485, "payout": 2.062}]},
    "board": {"games": [{"questions": [{
        "prediction_id": 1, "state": "upcoming", "forecaster": "statistical",
        "prob": 1.0 - 0.5358, "prob_words": "46%", "price": 1.0 - 0.485,
        "pays": 1.942}]}]}}
BOARD_PRICED_FIXTURE_MERGED = {
    "forecaster": "statistical",
    "today": {"clears": [{"prediction_id": 1, "state": "upcoming",
                          "model_words": "46¢", "price": 0.485,
                          "payout": 2.062}]},
    "board": {"games": [{"questions": [{
        "prediction_id": 1, "state": "upcoming", "forecaster": "statistical",
        "prob": 0.57, "prob_words": "57%", "price": 0.485,
        "pays": 2.062}]}]}}


def _check_the_board_count_scanners_can_see() -> None:
    from . import language as _language

    problems = []
    if board_price_side_faults(BOARD_PRICED_FIXTURE_GOOD):
        problems.append("board_price_side_faults refuses a block on its card's numbers: "
                        + board_price_side_faults(BOARD_PRICED_FIXTURE_GOOD)[0])
    if not board_price_side_faults(BOARD_PRICED_FIXTURE_MERGED):
        problems.append("board_price_side_faults misses the merge's priced row")
    twice = {"forecaster": "statistical", "board": {
        "games": [{"questions": [{"prediction_id": 7, "forecaster": "statistical",
                                  "taken": True}],
                   "questions_n": {"statistical": 1},
                   "questions_words": _language.game_questions_words(
                       {"statistical": 1}, "statistical")}],
        "props": {"tiles": [{"prediction_id": 7, "taken": True}]},
        "my_day": {"n": 2, "entries": [{"prediction_id": 7}, {"prediction_id": 7}]}}}
    if not board_count_faults(twice):
        problems.append("board_count_faults misses a prop counted twice on My day")
    once = {"forecaster": "statistical", "board": dict(
        twice["board"], my_day={"n": 1, "entries": [{"prediction_id": 7}]})}
    if board_count_faults(once):
        problems.append("board_count_faults refuses a prop counted once: "
                        + board_count_faults(once)[0])
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_board_count_scanners_can_see()


# ---------------------------------------------------------------------------
# THE ROSTER'S NUMBERS ARE DISPLAY ONLY (the operator's ruling of
# 2026-09-29, docs/briefs/2026-09-29-player-numbers.md)
# ---------------------------------------------------------------------------
#
# "player_numbers: a loaded roster table, refreshed each load, not
# append-only; say so in its description. Plain UPDATE then INSERT is fine.
# It is display only: nothing that forecasts, grades, fits or measures may
# read it, and a scan refuses any such read."
#
# WHY. The jersey numbers came in with the board (operator ruling a,
# 2026-09-25) as a declared, dated data addition, not a factor. A number on
# a shirt says nothing about a game, and LAW 2 declares every factor in
# advance: a table no factor names is one a later query can join to without
# anyone declaring anything, and the fit that learned from it would look
# ordinary. So the table is named where it is declared, loaded and drawn,
# and nowhere else.
#
# WHAT IT READS: every string the shipped code can hand SQLite or anything
# else -- the package, `tools/` less `tools/guards/`, and `desktop/`, read
# by question 15's readers (`_sql_strings_in` over `_rendered_sql`; each
# Python string read as written and again with its template placeholders as
# parts worked out at run time) -- and every `.sql` file in the package.
# Docstrings and comments are prose and are not read. The name is the
# table's whole name as SQL reads it -- case, quoting and a schema's prefix
# apart -- anywhere: in a statement, in a string literal inside one, or in a
# bare string (a key, or the argument of a helper that builds the statement
# itself).
#
# HOW A NAME IS PLACED: as the table of a write (UPDATE, INSERT or REPLACE
# INTO, DELETE FROM), of a schema's declaration of it, or as a read, which
# is everything else. A NAME THE SCAN CANNOT PLACE COUNTS AS A READ (the
# brief's words): a bare string, whatever the code then does with it, and a
# name partly worked out at run time whose written letters could be the
# table's (`player_{kind}`, `"{}_numbers"`; three written letters or more).
#
# THE ALLOW-LIST, the stricter default the brief reads: the table's loader
# (the write), the schema (the declaration) and the display code that draws
# the jersey. The database door's own init or migration code is not listed
# because it needs no name (`db.init` runs `schema.sql`), and it could not
# be: `db` is in the prediction closure. Each entry is keyed by file and
# function, allowed one use, and dated; a name in a listed function used
# another way fails, and so does an entry no longer found.
#
# NEVER ALLOWED, EVEN IF LISTED: what forecasts, grades, fits or measures --
# every module of the prediction closure LAW 1 walks from every prediction
# entrypoint, read from the code; the resolver, the calibration, the
# correction, the recounts, the horizon and drift records, the priced
# forecaster, the at-the-line record, the recommendation, the shortlist (the
# ranker), the bet key, the paper record, and the whole of the model. A name
# there fails by name, and so does an entry that lists one.
#
# AND BY ANOTHER NAME (the prover, 2026-09-29; each measured getting past the
# scan as first built, which said nothing to any): the name held in one of
# this module's own values and read by that value's name elsewhere -- the
# calibration's `from gridiron.audit import ROSTER_NUMBERS_TABLE`, then
# `f"SELECT * FROM {ROSTER_NUMBERS_TABLE}"`; the jersey's own reader,
# `board._player_number`, imported by the shortlist or looked up by
# `getattr`, which reads the table for whoever calls it; and a whole name
# the code writes out in constants a template is filled in with
# (`"{}_{}".format("player", "numbers")`, or `%`), which the string readers
# read as parts worked out at run time. So a value of this module holding
# the name (`_ROSTER_NAME_HOLDERS`), named anywhere but the scan's own
# functions -- read off the module, imported under any alias, or looked up
# by its name -- is a read by the function it is in; a function the
# allow-list lets name the table, named in a module that may never name it,
# is a read there; and a template filled in with constants alone is read
# again whole.
#
# NOT SEEN: a name read from the record (`sqlite_master`), a file or the
# environment, or built where the scan renders no string of it -- pieces of
# a list joined at run time, a slice, a reversal, character codes, a
# docstring handed over through `__doc__`, a `string.Template` filled in by
# `substitute`. Nor a read through a function the allow-list does not name
# that calls one it does (a measuring module calling a page that draws the
# jersey): every module reaches `board` by import through `audit` and
# `views`, so an import is no sign, and the call graph is not read. The
# helpers that copy, count or migrate every table (`rebuild`,
# `tools/dbcopy.py`, `db`'s migration, `repo.counts`) take every table's
# name that way and name none; they forecast, grade, fit and measure nothing.

#: The table the ruling names. Written once: every other string in this
#: module builds on it, so nothing here names the table but this.
ROSTER_NUMBERS_TABLE = "player_numbers"

#: WHERE THE TABLE MAY BE NAMED, AND FOR WHAT (2026-09-29). Keyed (file from
#: the repository root, the qualified function the name is written in -- or,
#: in a schema file, the object that holds it), each with its one use --
#: "declares", "writes" or "reads" -- and a dated reason in words.
ROSTER_NUMBERS_ALLOWED: dict[tuple[str, str], tuple[str, str]] = {
    ("gridiron/schema.sql", "table " + ROSTER_NUMBERS_TABLE): (
        "declares",
        "2026-09-29: the table's own declaration, under the comment that says "
        "what it is -- a loaded roster, refreshed at each load, not "
        "append-only, display only"),
    ("gridiron/data/loader.py", "load_rosters"): (
        "writes",
        "2026-09-29: the write -- the NFL refresh's roster load, an update and "
        "then a plain insert where no row changed (the ruling: 'Plain UPDATE "
        "then INSERT is fine')"),
    ("gridiron/data/loader.py", "load_all"): (
        "reads",
        "2026-09-29: the refresh's tally of the rows the roster load wrote, "
        "keyed by the table's name for the report the command line prints; it "
        "issues no statement, and a bare name the scan cannot place is counted "
        "as a read"),
    ("gridiron/board.py", "_player_number"): (
        "reads",
        "2026-09-29: the display code that draws the jersey -- the number on a "
        "prop tile's jersey, or its empty slot where the record has none"),
    ("gridiron/audit.py", "module level"): (
        "reads",
        "2026-09-29: this scan's own words -- the name it looks for"),
}

#: WHAT MAY NEVER NAME IT, EVEN IF LISTED (2026-09-29): what forecasts,
#: grades, fits or measures, by file, or by package ending in "/", from the
#: repository root. Every module of the prediction closure is added to it
#: from the code (`_roster_numbers_never`).
ROSTER_NUMBERS_NEVER: dict[str, str] = {
    "gridiron/resolve.py": "the resolver, which grades",
    "gridiron/calibration.py": "the calibration, which grades and measures",
    "gridiron/correction.py": "the correction, which fits",
    "gridiron/recount.py": "the recounts, which measure",
    "gridiron/horizon.py": "the horizon record, which measures",
    "gridiron/drift.py": "the drift record, which measures",
    "gridiron/priced/": "the priced forecaster, which forecasts",
    "gridiron/market/at_the_line.py": "the at-the-line record, which measures",
    "gridiron/market/recommend.py": "the recommendation, which measures and sizes",
    "gridiron/shortlist.py": "the shortlist, the ranker",
    "gridiron/bet.py": "the bet key every count reads",
    "gridiron/market/paper.py": "the paper record, which measures",
    "gridiron/model/": "the model, which forecasts and fits",
}

#: The uses a name is placed as.
_ROSTER_USES = ("declares", "writes", "reads")

#: The fewest written letters a name partly worked out at run time must
#: carry to count as one that could be the table's. Measured 2026-09-29 on
#: the shipped code: at one letter twelve strings match ("s" after a number,
#: "_" between two parts, "P" before one); at two or more, none does.
_ROSTER_FRAGMENT_MIN = 3

#: A string holding neither the name nor a part worked out at run time (or
#: a template placeholder) names nothing and is not tokenised: a quick way
#: past prose, never past a name.
_ROSTER_QUICK = re.compile(re.escape(ROSTER_NUMBERS_TABLE) + r"|[\x00{}%$]", re.I)

#: The name inside a string literal of the statement.
_ROSTER_IN_A_LITERAL = re.compile(
    r"(?<![A-Za-z0-9_$])" + re.escape(ROSTER_NUMBERS_TABLE) + r"(?![A-Za-z0-9_$])",
    re.I)

#: EVERY VALUE OF THIS MODULE HOLDING THE TABLE'S NAME, by its own name (the
#: prover, 2026-09-29): named anywhere but the scan's own functions, each is
#: the name, and a read by the function it is in. Proved complete at import:
#: a new value holding the name must be listed here.
_ROSTER_NAME_HOLDERS = ("ROSTER_NUMBERS_TABLE", "ROSTER_NUMBERS_ALLOWED",
                        "_ROSTER_QUICK", "_ROSTER_IN_A_LITERAL")

#: The functions of this module that ARE the scan, the only ones that may
#: name a value holding the table's name (2026-09-29). One no longer found
#: fails the scan, so the list only names what is there.
_ROSTER_SCAN_ITSELF = frozenset({
    "_roster_name_fits", "_roster_mentions", "roster_numbers_read_faults",
    "check_the_roster_numbers_are_display_only", "_check_the_roster_scan_can_see"})

#: What `_roster_constant` answers for an expression not written wholly in
#: constants.
_ROSTER_NOT_CONSTANT = object()


def _roster_references(tree: ast.AST, names) -> list[tuple[ast.AST, str]]:
    """(node, name) for every place a module names one of `names` as Python
    names a value: a name, an attribute read off anything, an import (the
    name imported, under any alias), or a string that is the name (a
    `getattr`, a namespace looked up by it). A docstring is prose."""
    prose = _docstring_nodes(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.alias):
            name = node.name.rsplit(".", 1)[-1]
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in prose):
            name = node.value
        else:
            continue
        if name in names:
            found.append((node, name))
    return found


def _roster_constant(node: ast.AST):
    """The value of an expression written wholly in constants -- a number, or
    a string the string readers render with no part worked out at run time --
    or `_ROSTER_NOT_CONSTANT`."""
    if (isinstance(node, ast.Constant)
            and not isinstance(node.value, (str, bytes))):
        return node.value
    text = _rendered_sql(node, set())
    if text is None or _UNKNOWN_PART in text:
        return _ROSTER_NOT_CONSTANT
    return text


def _roster_filled_in(tree: ast.AST) -> list[tuple[ast.AST, str]]:
    """(node, text) for every template a module fills in with constants
    alone -- `.format` with constant arguments, `%` with a constant, a tuple
    or a dict of them -- as it reads once filled in (the prover, 2026-09-29:
    the string readers read each argument as a part worked out at run time,
    so `"{}_{}".format("player", "numbers")` named nothing)."""
    found = []
    for node in ast.walk(tree):
        try:
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "format"):
                template = _roster_constant(node.func.value)
                args = [_roster_constant(a) for a in node.args]
                kwargs = {k.arg: _roster_constant(k.value) for k in node.keywords}
                if (not isinstance(template, str) or None in kwargs
                        or any(a is _ROSTER_NOT_CONSTANT
                               for a in args + list(kwargs.values()))):
                    continue
                found.append((node, template.format(*args, **kwargs)))
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                template = _roster_constant(node.left)
                if not isinstance(template, str):
                    continue
                if isinstance(node.right, ast.Tuple):
                    values = tuple(_roster_constant(e) for e in node.right.elts)
                    parts = list(values)
                elif isinstance(node.right, ast.Dict):
                    keys = [_ROSTER_NOT_CONSTANT if k is None else _roster_constant(k)
                            for k in node.right.keys]
                    held = [_roster_constant(v) for v in node.right.values]
                    parts = keys + held
                    values = dict(zip(keys, held))
                else:
                    values = _roster_constant(node.right)
                    parts = [values]
                if any(p is _ROSTER_NOT_CONSTANT for p in parts):
                    continue
                found.append((node, template % values))
        except (IndexError, KeyError, ValueError, TypeError, AttributeError):
            continue
    return found


def _roster_numbers_never(root: Path) -> dict[str, str]:
    """{file from the repository root, or a package ending in "/": why it
    may never name the table}: `ROSTER_NUMBERS_NEVER`, and every module of
    every prediction closure under `root`, read from the code."""
    never = dict(ROSTER_NUMBERS_NEVER)
    for _what, entrypoint in sorted(prediction_entrypoints().items()):
        closure = import_closure(entrypoint, root)
        for module, path in sorted(closure.modules.items()):
            never.setdefault(path.relative_to(root.parent).as_posix(),
                             f"in the prediction closure ({entrypoint} "
                             f"reaches {module})")
    return never


def _roster_never_why(never: dict[str, str], where: str) -> str | None:
    """Why `where` may never name the table, or None."""
    for place, why in never.items():
        if where == place or (place.endswith("/") and where.startswith(place)):
            return why
    return None


def _roster_name_fits(value: str, before: bool, after: bool) -> bool:
    """Could a name be the table's? Whole, only the name itself; with parts
    worked out at run time touching it (`before`, `after`) or inside it,
    when its written letters -- at least `_ROSTER_FRAGMENT_MIN` of them --
    fall where the table's name could put them."""
    pieces = value.split(_UNKNOWN_PART)
    if len(pieces) == 1 and not (before or after):
        return value == ROSTER_NUMBERS_TABLE
    if len("".join(pieces)) < _ROSTER_FRAGMENT_MIN:
        return False
    pattern = (("(?s:.*)" if before else "")
               + "(?s:.*)".join(re.escape(p) for p in pieces)
               + ("(?s:.*)" if after else ""))
    return re.fullmatch(pattern, ROSTER_NUMBERS_TABLE) is not None


def _roster_use(tokens: list[_SqlToken], i: int, schema: bool) -> str:
    """How the whole name at `tokens[i]` is used: "writes" as the table of
    an UPDATE, an INSERT or REPLACE INTO or a DELETE FROM; "declares" as
    the table a schema file declares; "reads" otherwise."""
    j = i
    while (j >= 2 and tokens[j - 1].kind == "other" and tokens[j - 1].value == "."
           and tokens[j - 2].kind in ("word", "name")):
        j -= 2                                      # a schema's prefix
    words = [t.word for t in tokens[max(0, j - 6):j]]
    if schema:
        head = words[:-3] if words[-3:] == ["IF", "NOT", "EXISTS"] else words
        if head[-1:] == ["TABLE"]:
            head = head[:-1]
            while head[-1:] in (["TEMP"], ["TEMPORARY"]):
                head = head[:-1]
            if head[-1:] == ["CREATE"]:
                return "declares"
    if words[-1:] == ["UPDATE"] or words[-3:-1] == ["UPDATE", "OR"]:
        return "writes"
    if words[-1:] == ["INTO"] and (words[-2:-1] in (["INSERT"], ["REPLACE"])
                                   or words[-4:-2] == ["INSERT", "OR"]):
        return "writes"
    if words[-2:] == ["DELETE", "FROM"]:
        return "writes"
    return "reads"


def _roster_mentions(text: str, schema: bool) -> list[tuple[int, str]]:
    """(offset in the text, use) for every name of the table in one text,
    each once: read as written and, for a Python string, again with its
    template placeholders as parts worked out at run time -- the precedent
    of `_replacing_writes_in`, a placeholder keeping its length so a place
    is the same in both readings."""
    if not _ROSTER_QUICK.search(text):
        return []
    found: dict[int, str] = {}
    for reading in ([text] if schema else [text, _placeholders_unknown(text)]):
        tokens = _sql_tokens(reading)
        n = len(tokens)
        for i, tok in enumerate(tokens):
            if tok.kind == "literal":
                if _ROSTER_IN_A_LITERAL.search(tok.value):
                    found.setdefault(tok.start, "reads")
                continue
            if tok.kind not in ("word", "name"):
                continue
            before = (i > 0 and tokens[i - 1].kind == "unknown"
                      and tokens[i - 1].end == tok.start)
            after = (i + 1 < n and tokens[i + 1].kind == "unknown"
                     and tokens[i + 1].start == tok.end)
            if not _roster_name_fits(tok.value, before, after):
                continue
            whole = tok.value == ROSTER_NUMBERS_TABLE and not (before or after)
            found.setdefault(tok.start,
                             _roster_use(tokens, i, schema) if whole else "reads")
    return sorted(found.items())


def roster_numbers_read_faults(root: Path | None = None,
                               allowed: dict | None = None) -> list[str]:
    """Every name of the roster's numbers table the operator's ruling of
    2026-09-29 refuses, in the shipped code or the schema: one in a module
    that forecasts, grades, fits or measures, listed or not; one no entry of
    `ROSTER_NUMBERS_ALLOWED` lists; one used other than as its entry allows;
    and every entry that lists a place that may never name the table, is no
    longer found, has no known use, or carries no dated reason. Each named
    by file, line and function."""
    root = config.PACKAGE_ROOT if root is None else Path(root)
    allowed = ROSTER_NUMBERS_ALLOWED if allowed is None else allowed
    base = root.parent
    table = ROSTER_NUMBERS_TABLE
    never = _roster_numbers_never(root)
    faults: list[str] = []
    found: set[tuple[str, str]] = set()

    def judge(where: str, line: int, function: str, use: str) -> None:
        place = f"{where}:{line} ({function}) {use} `{table}`"
        why = _roster_never_why(never, where)
        if why is not None:
            faults.append(
                f"{place}, and {where} is {why}. Nothing that forecasts, "
                f"grades, fits or measures may read the roster's numbers (the "
                f"operator's ruling of 2026-09-29), listed or not: take the "
                f"name out.")
            return
        entry = allowed.get((where, function))
        if entry is None:
            faults.append(
                f"{place}, which audit.ROSTER_NUMBERS_ALLOWED does not list. "
                f"The table is display only (the operator's ruling of "
                f"2026-09-29): it is named by its loader, the schema and the "
                f"code that draws the jersey, and nowhere else; a name the "
                f"scan cannot place is counted as a read.")
            return
        found.add((where, function))
        listed = entry[0] if isinstance(entry, tuple) and entry else None
        if listed != use:
            faults.append(
                f"{place}, where its entry in audit.ROSTER_NUMBERS_ALLOWED "
                f"allows only {listed!r}. An entry allows one use; a name the "
                f"scan cannot place is counted as a read.")

    # THE FUNCTIONS THE ALLOW-LIST LETS NAME THE TABLE, by their own names
    # (the prover, 2026-09-29): named where the table may never be, each is a
    # read there.
    readers: dict[str, str] = {}
    for (where, function) in allowed:
        if where.endswith(".py") and function != "module level":
            readers.setdefault(function.rsplit(".", 1)[-1], f"{where} ({function})")
    scan_itself_found: set[str] = set()

    for path in _shipped_python_files(root):
        where = path.relative_to(base).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = _qualified_functions(tree)
        for node, text in _sql_strings_in(tree):
            for start, use in _roster_mentions(text, schema=False):
                judge(where, node.lineno + text.count("\n", 0, start),
                      functions.get(id(node)) or "module level", use)
        # A TEMPLATE FILLED IN WITH CONSTANTS ALONE, read again whole.
        for node, text in _roster_filled_in(tree):
            for start, use in _roster_mentions(text, schema=False):
                judge(where, node.lineno, functions.get(id(node)) or "module level", use)
        # THE NAME BY THE NAME OF A VALUE HOLDING IT: a read by the function
        # it is in, but in the scan's own functions.
        if where == "gridiron/audit.py":
            scan_itself_found = {f for f in functions.values() if f} & _ROSTER_SCAN_ITSELF
        for node, name in _roster_references(tree, _ROSTER_NAME_HOLDERS):
            function = functions.get(id(node)) or "module level"
            if where == "gridiron/audit.py" and function in _ROSTER_SCAN_ITSELF:
                continue
            judge(where, node.lineno, function, "reads")
        # AND THE CODE THAT NAMES IT, named where the table may never be.
        why = _roster_never_why(never, where)
        if why is not None:
            for node, name in _roster_references(tree, readers):
                function = functions.get(id(node)) or "module level"
                faults.append(
                    f"{where}:{node.lineno} ({function}) names `{name}`, "
                    f"{readers[name]}, which the allow-list lets name "
                    f"`{table}`; and {where} is {why}. Nothing that forecasts, "
                    f"grades, fits or measures may read the roster's numbers "
                    f"(the operator's ruling of 2026-09-29), not through the "
                    f"code that loads or draws them either: take the call out.")
    for missing in sorted(_ROSTER_SCAN_ITSELF - scan_itself_found):
        faults.append(
            f"gridiron/audit.py ({missing}): listed in audit._ROSTER_SCAN_ITSELF, "
            f"the scan's own functions, and no longer found: remove it.")
    for path in sorted(root.rglob("*.sql")):
        where = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8")
        tokens = _sql_tokens(text)
        objects = _sql_objects(tokens)
        for start, use in _roster_mentions(text, schema=True):
            holder = [o for o in objects if tokens[o[0]].start <= start]
            function = (f"{holder[-1][1]} {holder[-1][2]}" if holder
                        else "module level")
            judge(where, 1 + text.count("\n", 0, start), function, use)

    for key, entry in sorted(allowed.items()):
        where, function = key
        name = f"{where} ({function})"
        why = _roster_never_why(never, where)
        if why is not None:
            faults.append(
                f"{name}: listed in audit.ROSTER_NUMBERS_ALLOWED, and {where} "
                f"is {why}. No entry lets what forecasts, grades, fits or "
                f"measures read the roster's numbers: remove the entry.")
        if (not isinstance(entry, tuple) or len(entry) != 2
                or entry[0] not in _ROSTER_USES):
            faults.append(
                f"{name}: listed in audit.ROSTER_NUMBERS_ALLOWED without one "
                f"of the uses {_ROSTER_USES} and a reason.")
            continue
        if key not in found and why is None:
            faults.append(
                f"{name}: listed in audit.ROSTER_NUMBERS_ALLOWED and no longer "
                f"names `{table}`: remove the entry.")
        if not re.match(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}: \S", str(entry[1])):
            faults.append(
                f"{name}: listed without a dated reason in words "
                f"(\"2026-09-29: the code that draws the jersey\").")
    # One place read two ways (a template's constant argument and the
    # template filled in) is one fault.
    return list(dict.fromkeys(faults))


def check_the_roster_numbers_are_display_only(root: Path | None = None) -> None:
    """Raise unless the roster's numbers table is named only where the
    allow-list says, and nowhere that forecasts, grades, fits or measures
    (the operator's ruling of 2026-09-29; gate step 2)."""
    faults = roster_numbers_read_faults(root)
    if faults:
        raise LawViolation(
            f"THE ROSTER'S NUMBERS ARE READ WHERE THEY MAY NOT BE (the "
            f"operator's ruling of 2026-09-29: `{ROSTER_NUMBERS_TABLE}` is "
            f"display only, and nothing that forecasts, grades, fits or "
            f"measures may read it):" + _NL2 + _NL2.join(faults))


def _check_the_roster_scan_can_see() -> None:
    """The name read as SQL reads it, placed, and nothing else taken for it
    -- every text built on the constant, so this module names the table
    once."""
    t = ROSTER_NUMBERS_TABLE
    cases = (
        ("SELECT n.jersey_number FROM " + t + " n", False, ["reads"]),
        ("select * from MAIN.\"" + t.upper() + "\"", False, ["reads"]),
        ("UPDATE " + t + " SET jersey_number = ?", False, ["writes"]),
        # OR ABORT, not OR IGNORE (2026-09-29): questions 25 and 29's scan
        # reads this module, and an insert under OR IGNORE on a table it
        # cannot read, kept in a tuple rather than handed to `execute`, is one
        # it counts as run for several rows on an append-only table. The case
        # proves the same placement: an insert under a conflict clause.
        ("INSERT OR ABORT INTO main." + t + " VALUES (?)", False, ["writes"]),
        ("DELETE FROM " + t, False, ["writes"]),
        ("SELECT 1 FROM sqlite_master WHERE name = '" + t + "'", False, ["reads"]),
        (t, False, ["reads"]),
        ("SELECT * FROM " + t[:7] + "{kind}", False, ["reads"]),
        ("SELECT * FROM " + _UNKNOWN_PART + t[6:], False, ["reads"]),
        ("CREATE TABLE IF NOT EXISTS " + t + " (a)", True, ["declares"]),
        ("CREATE TABLE IF NOT EXISTS " + t + " (a)", False, ["reads"]),
        ("SELECT * FROM " + t + "_history", False, []),
        ("SELECT * FROM players", False, []),
        ("read " + _UNKNOWN_PART + "s ago", False, []),
    )
    problems = [f"{text!r} read as {got}, not {want}"
                for text, schema, want in cases
                if (got := [u for _at, u in _roster_mentions(text, schema)]) != want]
    # AND BY ANOTHER NAME (the prover, 2026-09-29): a template filled in with
    # constants alone is read whole, a value holding the name is seen by its
    # own name however it is reached, and every value of this module holding
    # the name is one of those.
    filled = ast.parse(
        repr("SELECT * FROM {}_{}") + ".format(" + repr(t[:6]) + ", " + repr(t[7:]) + ")\n"
        + repr("SELECT * FROM %s_%s") + " % (" + repr(t[:6]) + ", " + repr(t[7:]) + ")\n"
        + repr("SELECT * FROM %(a)s") + " % {'a': " + repr(t) + "}\n"
        + repr("SELECT * FROM {}") + ".format(kind)\n")
    got = [u for _n, text in _roster_filled_in(filled)
           for _at, u in _roster_mentions(text, False)]
    if got != ["reads"] * 3:
        problems.append(f"three templates filled in with the name read as {got}")
    named = ast.parse("from gridiron.audit import " + _ROSTER_NAME_HOLDERS[0] + " as x\n"
                      "y = a." + _ROSTER_NAME_HOLDERS[1] + "\n"
                      "z = getattr(a, " + repr(_ROSTER_NAME_HOLDERS[2]) + ")\n"
                      "w = a.ROSTER_NUMBERS_NEVER\n")
    seen = sorted(name for _n, name in _roster_references(named, _ROSTER_NAME_HOLDERS))
    if seen != sorted(_ROSTER_NAME_HOLDERS[:3]):
        problems.append(f"the name by another name read as {seen}")
    holding = {name for name, value in globals().items()
               if not callable(value) and type(value).__name__ != "module"
               and t in repr(value)}
    if holding != set(_ROSTER_NAME_HOLDERS):
        problems.append(f"this module's values holding the name are {sorted(holding)}, "
                        f"and audit._ROSTER_NAME_HOLDERS lists {list(_ROSTER_NAME_HOLDERS)}")
    if problems:
        raise LawViolation("A SCANNER IS BLIND:" + _NL2 + _NL2.join(problems))


_check_the_roster_scan_can_see()
