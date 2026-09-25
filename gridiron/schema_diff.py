"""The schema, compared by what it does (schema ruling 1 of 2026-09-24).

THE OPERATOR'S WORDS: "The diff check compares after normalising quoting,
whitespace, comments and column order, and fails on any difference in
behaviour. Byte-identical matching isn't required."

ONE DOOR (built 2026-09-25). The gate's two diffs -- the live record against
the release, and the gate's migrated copy against this tree -- and ruling 2's
migration, asking whether a table is already at its released definition, all
compare here, so "the same schema" means one thing wherever it is asked.

WHAT IS NORMALISED, AND NOTHING ELSE:

  * comments, `--` and `/* */`, wherever they sit, a column list included;
  * whitespace: SQL is compared as a sequence of tokens, so spacing and line
    breaks cannot matter;
  * quoting of names: "x", [x] and `x` are all x, and a name or a keyword is
    compared without regard to case, which is how SQLite resolves them. A
    string literal is kept byte for byte -- 'NFL' is not 'nfl';
  * column order: a table's columns are compared by name. Measured before
    this was built: nothing in the package, the tools or the tests inserts
    without a column list, and every `SELECT *` reader goes by name.

WHAT REMAINS IS A DIFFERENCE IN BEHAVIOUR, reported by object and property in
plain words: a column on one side only; a column's type or one of its clauses
(NOT NULL, DEFAULT, CHECK, COLLATE, REFERENCES, PRIMARY KEY, UNIQUE,
GENERATED); a table constraint or option; an index, trigger or view on one
side only or defined differently. Anything this module cannot tell apart is
reported, never assumed equal: `<>` against `!=`, or `DEFAULT (0)` against
`DEFAULT 0`, is a difference here.

WHY IT READS THE TEXT, AND NOT ONLY THE PRAGMAS. No PRAGMA exposes a CHECK.
Measured 2026-09-25: a comparison of `table_xinfo` alone would have passed 7
of the 8 behavioural differences the live record held. The PRAGMAs are read
too, by column name, as a check on this parser: a difference SQLite reports
that the text comparison did not find is reported as well.

Names no table, and sits outside every prediction closure.
"""

from __future__ import annotations

import collections
import sqlite3
from dataclasses import dataclass, field

#: Words that begin a clause inside a column definition.
_COLUMN_CLAUSES = frozenset({
    "constraint", "primary", "not", "null", "unique", "check", "default",
    "collate", "references", "generated", "as"})

#: Words that begin a table constraint rather than a column.
_TABLE_CONSTRAINTS = frozenset({"constraint", "primary", "unique", "check",
                                "foreign"})

#: Operators SQLite reads as one token.
_OPERATORS = ("<=", ">=", "<>", "!=", "==", "||", "<<", ">>")

#: A clause that owns a following NULL: `DEFAULT NULL`, and `ON DELETE SET
#: NULL` inside a REFERENCES clause, are not the bare NULL constraint.
_OWNS_A_NULL = frozenset({"default", "references", "generated", "as"})

#: Tables SQLite writes for itself that are statistics for the planner, not
#: schema: ANALYZE creates them and no query's result depends on them
#: (2026-09-25). `sqlite_sequence` is NOT here -- it exists exactly when an
#: AUTOINCREMENT table does, so it is compared like any other table.
_PLANNER_STATISTICS = ("sqlite_stat",)

#: Names SQLite gives the index it makes for a PRIMARY KEY or UNIQUE clause.
#: They number the clauses by position, so they are compared through the
#: table that owns them, never by name.
_AUTOMATIC_INDEX = "sqlite_autoindex_"


def tokens(sql: str | None) -> list[str]:
    """SQL text as normalised tokens: no comments, no whitespace, names
    unquoted, names and keywords in lower case, string literals exact."""
    out: list[str] = []
    if not sql:
        return out
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c.isspace():
            i += 1
        elif sql.startswith("--", i):
            end = sql.find(chr(10), i)
            i = n if end < 0 else end + 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif c == "'":
            j = i + 1
            while True:
                k = sql.find("'", j)
                if k < 0:
                    k = n - 1
                    break
                if sql.startswith("''", k):
                    j = k + 2
                    continue
                break
            out.append(sql[i:k + 1])
            i = k + 1
        elif c in '"`':
            j, name = i + 1, []
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:
                        name.append(c)
                        j += 2
                        continue
                    break
                name.append(sql[j])
                j += 1
            out.append("".join(name).lower())
            i = j + 1
        elif c == "[":
            end = sql.find("]", i)
            end = n if end < 0 else end
            out.append(sql[i + 1:end].lower())
            i = end + 1
        elif c.isalnum() or c in "_$":
            j = i
            while j < n and (sql[j].isalnum() or sql[j] in "_$"):
                j += 1
            out.append(sql[i:j].lower())
            i = j
        else:
            for op in _OPERATORS:
                if sql.startswith(op, i):
                    out.append(op)
                    i += len(op)
                    break
            else:
                out.append(c)
                i += 1
    return out


def show(toks) -> str:
    """Tokens back as readable SQL, for a message and for a register key."""
    text = " ".join(toks)
    for before, after in (("( ", "("), (" )", ")"), (" ,", ",")):
        text = text.replace(before, after)
    return text


def _split_top(toks: list[str]) -> list[list[str]]:
    """Split on the commas outside any parentheses."""
    parts: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for t in toks:
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
        if t == "," and depth == 0:
            parts.append(current)
            current = []
        else:
            current.append(t)
    if current:
        parts.append(current)
    return parts


def _column(rest: list[str]) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    """A column's type tokens, and its clauses in the order written."""
    kind: list[str] = []
    clauses: list[tuple[str, ...]] = []
    current: list[str] | None = None
    depth = 0
    for t in rest:
        starts = (
            depth == 0 and t in _COLUMN_CLAUSES
            and not (t == "null" and current
                     and (current[-1] == "not" or current[0] in _OWNS_A_NULL))
            and not (t == "as" and current and current[0] == "generated")
            and not (current and current[0] == "constraint" and len(current) < 3))
        if starts:
            if current is not None:
                clauses.append(tuple(current))
            current = [t]
        elif current is None:
            kind.append(t)
        else:
            current.append(t)
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
    if current is not None:
        clauses.append(tuple(current))
    return tuple(kind), clauses


@dataclass
class TableShape:
    """A CREATE TABLE statement, taken apart."""
    head: tuple[str, ...]
    columns: dict[str, tuple[tuple[str, ...], list[tuple[str, ...]]]]
    order: list[str]
    constraints: list[tuple[str, ...]]
    options: tuple[str, ...]


def table_shape(sql: str) -> TableShape:
    """Take a CREATE TABLE statement apart into its columns, constraints and
    options, every part normalised."""
    toks = tokens(sql)
    opened = toks.index("(")
    depth, closed = 0, len(toks) - 1
    for k in range(opened, len(toks)):
        if toks[k] == "(":
            depth += 1
        elif toks[k] == ")":
            depth -= 1
            if depth == 0:
                closed = k
                break
    columns: dict = {}
    order: list[str] = []
    constraints: list[tuple[str, ...]] = []
    for item in _split_top(toks[opened + 1:closed]):
        if item[0] in _TABLE_CONSTRAINTS:
            constraints.append(tuple(item))
        else:
            columns[item[0]] = _column(item[1:])
            order.append(item[0])
    # THE NAME IS NOT PART OF THE HEAD. A table rebuilt under another name
    # and renamed into place reads `CREATE TABLE "factors"`; the name is what
    # the object is keyed by, so it is compared there and nowhere else.
    return TableShape(tuple(toks[:opened - 1]), columns, order, constraints,
                      tuple(toks[closed + 1:]))


@dataclass(frozen=True)
class Difference:
    """One property of one object that only one side has.

    `held_by` is "record" or "reference": the database being checked, or
    the one it is checked against. A property that differs between the two
    is two of these, one naming each side's version, so every difference
    reads the same way: this side has it, and the other does not.
    """
    object: str
    property: str
    held_by: str

    def words(self, record: str, reference: str) -> str:
        have, lack = ((record, reference) if self.held_by == "record"
                      else (reference, record))
        return f"{self.object}, {self.property}: {have} has it and {lack} does not"


def _both_ways(obj: str, prop: str, record_has, reference_has) -> list[Difference]:
    """A Difference for each side's version of one property."""
    out = []
    for item in record_has:
        out.append(Difference(obj, prop.format(item), "record"))
    for item in reference_has:
        out.append(Difference(obj, prop.format(item), "reference"))
    return out


def _clause_text(clauses) -> str:
    return " ".join(show(c) for c in clauses)


def table_differences(record_sql: str, reference_sql: str,
                      obj: str = "table") -> list[Difference]:
    """What one table's definition does that the other's does not, after
    normalising quoting, whitespace, comments and column order."""
    a, b = table_shape(record_sql), table_shape(reference_sql)
    out: list[Difference] = []
    if a.head != b.head:
        out += _both_ways(obj, "its kind: {}", [show(a.head)], [show(b.head)])
    if a.options != b.options:
        out += _both_ways(obj, "table options: {}", [show(a.options) or "none"],
                          [show(b.options) or "none"])
    for name in sorted(set(a.columns) | set(b.columns)):
        mine, theirs = a.columns.get(name), b.columns.get(name)
        if mine is None or theirs is None:
            kind, clauses = mine or theirs
            whole = f"column {name} ({show(kind)} {_clause_text(sorted(clauses))})"
            out.append(Difference(obj, " ".join(whole.split()).replace(" )", ")"),
                                  "record" if theirs is None else "reference"))
            continue
        if mine[0] != theirs[0]:
            out += _both_ways(obj, f"column {name}: type {{}}",
                              [show(mine[0]) or "none"],
                              [show(theirs[0]) or "none"])
        ours, others = (collections.Counter(mine[1]),
                        collections.Counter(theirs[1]))
        out += _both_ways(obj, f"column {name}: {{}}",
                          [show(c) for c in sorted((ours - others).elements())],
                          [show(c) for c in sorted((others - ours).elements())])
    ours, others = (collections.Counter(a.constraints),
                    collections.Counter(b.constraints))
    out += _both_ways(obj, "table constraint {}",
                      [show(c) for c in sorted((ours - others).elements())],
                      [show(c) for c in sorted((others - ours).elements())])
    return out


@dataclass
class Schema:
    """What one database defines, as read from it, keyed for comparison."""
    objects: dict[tuple[str, str], tuple[str, str | None]]
    columns: dict[str, dict[str, tuple]] = field(default_factory=dict)
    keys: dict[str, list[tuple]] = field(default_factory=dict)
    foreign_keys: dict[str, list[tuple]] = field(default_factory=dict)


def _read(conn: sqlite3.Connection, sql: str) -> list[tuple]:
    return [tuple(r) for r in conn.execute(sql).fetchall()]


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def read_schema(conn: sqlite3.Connection) -> Schema:
    """Every object a database defines, and what SQLite itself reports about
    each table's columns, automatic indexes and foreign keys, keyed by name.
    Reads only."""
    objects = {}
    for kind, name, table, sql in _read(
            conn, "SELECT type, name, tbl_name, sql FROM sqlite_master"):
        if name.startswith(_PLANNER_STATISTICS):
            continue
        objects[(kind, name)] = (table, sql)
    schema = Schema(objects)
    for (kind, name) in objects:
        if kind != "table":
            continue
        q = _quoted(name)
        schema.columns[name] = {
            row[1].lower(): (tuple(tokens(row[2])), row[3],
                             tuple(tokens(row[4])) if row[4] is not None else None,
                             row[5], row[6])
            for row in _read(conn, f"PRAGMA table_xinfo({q})")}
        keys = []
        for _seq, index, unique, origin, partial in _read(
                conn, f"PRAGMA index_list({q})"):
            if origin == "c":
                continue            # a named index is compared as an object
            cols = tuple((r[2].lower() if r[2] else None, r[3],
                          (r[4] or "").lower())
                         for r in _read(conn, f"PRAGMA index_xinfo({_quoted(index)})")
                         if r[5] == 1)
            keys.append((unique, origin, partial, cols))
        schema.keys[name] = sorted(keys, key=repr)
        grouped: dict[int, list] = collections.defaultdict(list)
        for fid, _seq, parent, frm, to, upd, dele, match in _read(
                conn, f"PRAGMA foreign_key_list({q})"):
            grouped[fid].append((parent.lower(), (frm or "").lower(),
                                 (to or "").lower(), upd, dele, match))
        schema.foreign_keys[name] = sorted((tuple(v) for v in grouped.values()),
                                           key=repr)
    return schema


def _describe_column(facts: tuple) -> str:
    kind, notnull, default, pk, hidden = facts
    return (f"type {show(kind) or 'none'}, not null {notnull}, default "
            f"{show(default) if default is not None else 'none'}, primary key "
            f"{pk}, hidden {hidden}")


@dataclass
class Comparison:
    """The outcome of comparing a record with a reference."""
    differences: list[Difference]
    #: Objects whose stored SQL differs only in what the ruling normalises.
    cosmetic: list[str]
    #: How many objects each side defines (automatic indexes included).
    counts: tuple[int, int]


def _named(schema: Schema) -> set[tuple[str, str]]:
    """Every object but the indexes SQLite names for itself."""
    return {k for k in schema.objects if not k[1].startswith(_AUTOMATIC_INDEX)}


def compare(record: sqlite3.Connection, reference: sqlite3.Connection) -> Comparison:
    """Every difference in behaviour between two databases' schemas, object
    by object, after normalising quoting, whitespace, comments and column
    order; and the objects whose text differs only in those."""
    a, b = read_schema(record), read_schema(reference)
    mine, theirs = _named(a), _named(b)
    out: list[Difference] = []
    cosmetic: list[str] = []
    for kind, name in sorted(mine - theirs):
        out.append(Difference(f"{kind} {name}", "the whole object", "record"))
    for kind, name in sorted(theirs - mine):
        out.append(Difference(f"{kind} {name}", "the whole object", "reference"))
    for kind, name in sorted(mine & theirs):
        obj = f"{kind} {name}"
        (table_a, sql_a), (table_b, sql_b) = a.objects[(kind, name)], b.objects[(kind, name)]
        found: list[Difference] = []
        if table_a.lower() != table_b.lower():
            found += _both_ways(obj, "the table it belongs to: {}", [table_a], [table_b])
        if kind == "table" and sql_a and sql_b:
            found += table_differences(sql_a, sql_b, obj)
            found += _pragma_differences(obj, name, a, b, found)
        elif tokens(sql_a) != tokens(sql_b):
            found += _both_ways(obj, "its definition: {}", [show(tokens(sql_a))],
                                [show(tokens(sql_b))])
        if found:
            out += found
        elif (sql_a or "") != (sql_b or ""):
            cosmetic.append(obj)
    return Comparison(out, cosmetic, (len(a.objects), len(b.objects)))


def _pragma_differences(obj: str, table: str, a: Schema, b: Schema,
                        found: list[Difference]) -> list[Difference]:
    """What SQLite reports differently about a table the text comparison
    found equal: the check on the parser."""
    out: list[Difference] = []
    touched = {d.property.split(":")[0].split(" (")[0] for d in found}
    ca, cb = a.columns.get(table, {}), b.columns.get(table, {})
    for column in sorted(set(ca) & set(cb)):
        if f"column {column}" in touched or ca[column] == cb[column]:
            continue
        out += _both_ways(obj, f"column {column}, as SQLite reads it: {{}}",
                          [_describe_column(ca[column])],
                          [_describe_column(cb[column])])
    if found:
        return out
    if a.keys.get(table) != b.keys.get(table):
        out += _both_ways(obj, "the indexes SQLite makes for its keys: {}",
                          [repr(a.keys.get(table))], [repr(b.keys.get(table))])
    if a.foreign_keys.get(table) != b.foreign_keys.get(table):
        out += _both_ways(obj, "its foreign keys, as SQLite reads them: {}",
                          [repr(a.foreign_keys.get(table))],
                          [repr(b.foreign_keys.get(table))])
    return out
