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
BETTING_IDENTIFIERS = (
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
MARKET_SOURCE_IDENTIFIERS = ("prizepicks", "prize_picks")


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
                        f"amended permits read-only lines from PrizePicks "
                        f"ONLY inside the market module -- that quarantine is "
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
    """Any identifier in the package that would belong to a staking tool."""
    root = root or config.PACKAGE_ROOT
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in BETTING_SCAN_EXEMPT:
            continue
        for name in sorted(identifiers_in(path)):
            lowered = name.lower()
            for word in BETTING_IDENTIFIERS:
                if word in lowered:
                    hits.append(f"{path.name}:{name}")
    return hits


def check_not_a_betting_tool(root: Path | None = None) -> None:
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


def plain_words_violations(text: str) -> list[str]:
    """Internal vocabulary found in text a person will read.

    Deliberately crude: it looks at rendered visible text, not at markup, and
    flags anything shaped like an identifier. A false positive is fixed by
    writing the label in words, which is the desired outcome anyway.
    """
    hits: list[str] = []
    for term in INTERNAL_TERMS:
        if term in text:
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
CORRECTION_TABLES = frozenset({
    "predictions", "prediction_voids", "calibration_corrections",
})

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
    """Every SQL statement in the module, with its line."""
    import ast as _ast

    tree = _ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Constant) and isinstance(node.value, str):
            if _SQL_START.match(node.value):
                out.append((getattr(node, "lineno", 0), node.value))
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


def frame_truncation_faults(css: str) -> list[str]:
    """Every rule that would truncate something inside the frame."""
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


#: The function that must not move the frame, and the two things it has to do:
#: read the frame's position before changing anything, and put it back.
_JS_KEEPS_SCROLL = re.compile(
    r"function\s+selectTile\s*\([^)]*\)\s*\{(?P<body>.*?)\n  \}", re.S)


def selection_moves_the_frame(js: str) -> list[str]:
    """True-ish when selecting a pick would cost the reader their place."""
    match = _JS_KEEPS_SCROLL.search(js)
    if match is None:
        return ["selectTile() is not in the renderer at all, so nothing "
                "protects the reader's position when a pick is selected"]
    body = match.group("body")
    faults = []
    if "scrollTop" not in body:
        faults.append(
            "selectTile() never reads the frame's scrollTop, so it cannot "
            "restore it. Selecting a pick half way down a 177-pick slate "
            "would throw the reader back to the top, and looking at "
            "something would cost them their place.")
    elif body.count("scrollTop") < 2:
        faults.append(
            "selectTile() reads the frame's scrollTop but never writes it "
            "back. Reading it and discarding it is the same as not reading "
            "it, and looks more careful.")
    return faults


SELECT_FIXTURE_POSITIVE = """
  function selectTile(tile) {
    if (!tile) return;
    tile.setAttribute('aria-selected', 'true');
    paintRail(tile);
  }
"""
SELECT_FIXTURE_NEGATIVE = """
  function selectTile(tile) {
    if (!tile) return;
    const frame = document.getElementById('week-frame');
    const keep = frame ? frame.scrollTop : 0;
    tile.setAttribute('aria-selected', 'true');
    if (frame) frame.scrollTop = keep;
  }
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
        problems.append("selection_moves_the_frame misses a selectTile that "
                        "never touches scrollTop")
    if selection_moves_the_frame(SELECT_FIXTURE_NEGATIVE):
        problems.append("selection_moves_the_frame flags a selectTile that "
                        "correctly saves and restores scrollTop")
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
        if name not in ALLOWED_KEYFRAMES:
            faults.append(
                f"@keyframes {name!r} is not in the vocabulary. The only thing "
                f"on this page that repeats is the mark saying a game is being "
                f"played right now; anything else that loops is decoration.")
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

#: The value tokens and their aliases. `--pos` and `--neg` are the older
#: names, still used by the pages built before the dark theme.
_WIN_TOKENS = ("--win", "--win-wash", "--pos")
_LOSS_TOKENS = ("--loss", "--loss-wash", "--neg")

#: A selector that is allowed to say "won" / "lost". `up` and `down` are
#: the counts of picks that went the model's way and against it -- in
_WIN_SELECTOR = re.compile(r"\.win\b|v-win\b|\.up\b|\.pos\b")
_LOSS_SELECTOR = re.compile(r"\.loss\b|v-loss\b|\.neg\b|\.down\b")

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


def colour_law_faults(css: str) -> list[str]:
    """Every rule that paints something a value colour without a value."""
    faults = []
    for match in _CSS_RULE.finditer(css):
        selector = match.group("selector")
        # A selector spanning a comment or an at-rule preamble is not a rule.
        selector = selector.split("*/")[-1].strip()
        if not selector or selector.startswith("@"):
            continue
        # `:root` DECLARES the tokens; it does not paint anything with them.
        # The legacy aliases `--pos` and `--neg` are defined there in terms of
        # `--win` and `--loss`, which is the one place those names may appear
        # without a verdict beside them.
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
                f"Green means a pick won and red means a pick lost; a link, a "
                f"tab, a focus ring and a pressed segment are none of those. "
                f"Interactive is chrome (R2).")
            continue
        if used_win and not _WIN_SELECTOR.search(selector):
            faults.append(
                f"{one_line!r} uses {', '.join(used_win)} but says nothing "
                f"about a pick that won. GREEN MEANS A PICK WON, and nothing "
                f"else may wear it (R2).")
        if used_loss and not _LOSS_SELECTOR.search(selector):
            faults.append(
                f"{one_line!r} uses {', '.join(used_loss)} but says nothing "
                f"about a pick that lost. A warning, an error and a stale feed "
                f"are not losses; they carry weight and position instead (R2).")
    return faults


#: A green LINK and a red WARNING BORDER: the two misuses the rename ended,
#: and the two the plantings reproduce.
COLOUR_LAW_FIXTURE_POSITIVE = """
.row-more { color: var(--win); text-decoration: none; }
.notices-summary { border-left: 2px solid var(--loss); }
"""
COLOUR_LAW_FIXTURE_NEGATIVE = """
.verdict.win { color: var(--win); background: var(--win-wash); }
.verdict.loss { color: var(--loss); background: var(--loss-wash); }
.row-more { color: var(--chrome); text-decoration: none; }
"""


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
            "THE COLOUR LAW WAS BROKEN -- green means a pick won, red means a "
            "pick lost, and nothing else wears either:"
            + _NL2 + _NL2.join(faults))


def _check_the_colour_scanner_can_see() -> None:
    problems = []
    hits = colour_law_faults(COLOUR_LAW_FIXTURE_POSITIVE)
    if len(hits) < 2:
        problems.append(
            "colour_law_faults misses a green link or a red warning border")
    if colour_law_faults(COLOUR_LAW_FIXTURE_NEGATIVE):
        problems.append("colour_law_faults flags a correct verdict chip")
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

#: The nav, as ruled. Order included: it is the order the questions come in.
NAV_PAGES = ("week", "record", "results", "settings")

#: Every route that was removed, and where it went.
REDIRECTED = {
    "history": "results",
    "factors": "record",
    "versions": "record",
    "schedule": "settings",
    "digest": "week",
}


def nav_faults(js: str, html: str) -> list[str]:
    """A nav that is not the four ruled pages, or an old route left to 404."""
    faults = []
    links = re.findall(r'data-route="([a-z-]+)"', html)
    if tuple(links) != NAV_PAGES:
        faults.append(
            f"the nav is {links}, not {list(NAV_PAGES)}. Four pages is the "
            f"ruling (GRIDIRON_13 R4); a nav grows one link at a time, each "
            f"defensible on its own, which is how it got to seven.")
    for old, new in REDIRECTED.items():
        if not re.search(rf"{old}\s*:\s*'{new}'", js):
            faults.append(
                f"#/{old} does not redirect to #/{new}. A removed route must "
                f"land, not 404: somebody bookmarked it or wrote it down, and "
                f"the address bar is what tells them where the page went.")
    return faults


NAV_FIXTURE_A_FIFTH_ITEM = (
    '<a href="#/week" data-route="week">Picks</a>'
    '<a href="#/record" data-route="record">Record</a>'
    '<a href="#/results" data-route="results">Results</a>'
    '<a href="#/settings" data-route="settings">Settings</a>'
    '<a href="#/digest" data-route="digest">Digest</a>'
)
NAV_FIXTURE_A_DEAD_LINK = "const RENAMED = { history: 'results' };"


def check_the_nav_is_four_pages(js_path=None, html_path=None) -> None:
    js_path = js_path or (config.PACKAGE_ROOT / "web" / "app.js")
    html_path = html_path or (config.PACKAGE_ROOT / "web" / "index.html")
    html = Path(html_path).read_text(encoding="utf-8")
    nav = re.search(r'<nav id="nav".*?</nav>', html, re.S)
    faults = nav_faults(Path(js_path).read_text(encoding="utf-8"),
                        nav.group(0) if nav else html)
    if faults:
        raise LawViolation(
            "THE NAV IS NOT WHAT WAS RULED:" + _NL2 + _NL2.join(faults))


def _check_the_nav_scanner_can_see() -> None:
    problems = []
    good_js = ("const RENAMED = { history: 'results', factors: 'record',"
               " versions: 'record', schedule: 'settings', digest: 'week' };")
    good_nav = "".join(
        f'<a href="#/{p}" data-route="{p}">x</a>' for p in NAV_PAGES)
    if nav_faults(good_js, good_nav):
        problems.append("nav_faults flags the four ruled pages")
    if not nav_faults(good_js, NAV_FIXTURE_A_FIFTH_ITEM):
        problems.append("nav_faults misses a fifth nav item")
    if not nav_faults(NAV_FIXTURE_A_DEAD_LINK, good_nav):
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
RESORT_CALLS = ("renderWeek", ".sort(")


def live_update_faults(js: str) -> list[str]:
    """A live update that rebuilds or reorders the grid instead of patching."""
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
    return faults


LIVE_UPDATE_FIXTURE_POSITIVE = """
  function applyLive(live) {
    (live.picks || []).forEach(p => Object.assign(slateCards.get(p.id), p));
    renderWeek();
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
