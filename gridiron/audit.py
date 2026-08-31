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
FORBIDDEN_MODULES = ("gridiron.market",)

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


def betting_surface(root: Path | None = None) -> list[str]:
    """Any identifier in the package that would belong to a staking tool."""
    root = root or config.PACKAGE_ROOT
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
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

SNAKE_CASE = __import__("re").compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")


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
    return sorted(set(hits))


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
    """Every file whose calls count: the package, plus `tools/`. Never tests."""
    out: dict[str, str] = {}
    roots = [root]
    tools = root.parent / "tools"
    if tools.is_dir():
        roots.append(tools)
    for base in roots:
        for path in sorted(base.rglob("*.py")):
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
