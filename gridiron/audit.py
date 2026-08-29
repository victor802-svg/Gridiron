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
from dataclasses import dataclass, field
from pathlib import Path

from . import config

PACKAGE = "gridiron"

#: The module the whole blind path hangs off.
PREDICTION_ENTRYPOINT = "gridiron.model.predict"

#: Packages the prediction closure may not contain.
FORBIDDEN_MODULES = ("gridiron.market",)

#: Identifiers and literal fragments that name market data. `market_type` is
#: deliberately absent: it is a column on `predictions` describing what kind of
#: question was asked, not a price.
FORBIDDEN_IDENTIFIERS = (
    "market_lines_raw",
    "market_snapshots",
    "spread_line",
    "total_line",
    "moneyline",
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


def check_prediction_closure(
    entrypoint: str = PREDICTION_ENTRYPOINT, root: Path | None = None
) -> ClosureReport:
    """Raise `LawViolation` if the prediction path can reach market data."""
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
