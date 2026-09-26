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
    compared without regard to case, which is how SQLite resolves them --
    BUT ONLY WHERE THE TEXT IS CERTAINLY A NAME (below). A string literal is
    kept byte for byte -- 'NFL' is not 'nfl';
  * column order: a table's columns are compared by name. Measured before
    this was built: nothing in the package, the tools or the tests inserts
    without a column list, and every `SELECT *` reader goes by name.

QUOTED TEXT IS A NAME ONLY WHERE SQLITE CANNOT READ IT AS ANYTHING ELSE
(2026-09-25, the adversarial review of 3603300). SQLite reads a double-quoted
word as a name when it resolves to one and as a STRING when it does not, and
the first version lower-cased every quoted word as a name -- so
`CHECK (sport IN ("nfl"))` and `("NFL")`, `CHECK (s != NULL)` and
`(s != "NULL")`, `DEFAULT CURRENT_TIMESTAMP` and `DEFAULT "CURRENT_TIMESTAMP"`
all compared equal while doing different things. Now a quoted word loses its
quotes and its case only:

  * where the grammar admits nothing but a name: the object's own name; a
    column's name in CREATE TABLE; the name after CONSTRAINT, COLLATE,
    REFERENCES (and its column list), FROM, JOIN, INTO, UPDATE, and the
    table after an index's or a trigger's ON; either side of a `.`; and a
    list of bare column names -- PRIMARY KEY, UNIQUE and FOREIGN KEY lists,
    an index's columns, a trigger's UPDATE OF, a view's columns;
  * or, inside a table's expressions and an index's, where it names a
    column of that table, which is what SQLite itself resolves it to.

Anywhere else -- a CHECK or a WHEN, an index's WHERE, a trigger body -- it
keeps its quotes and its case, and "x", [x], `x` and a bare x all differ. A
difference reported where SQLite would in fact agree is a false alarm the
operator can read; one erased where it would not is a change in behaviour
the gate passes.

AND A BARE WORD AFTER DEFAULT KEEPS ITS CASE. SQLite stores `DEFAULT live`
as the string 'live' and `DEFAULT LIVE` as 'LIVE'; only the keywords it reads
there -- NULL, TRUE, FALSE, CURRENT_TIME, CURRENT_DATE, CURRENT_TIMESTAMP --
are compared without case, and a quoted word there is always a string.

AND THE EFFECTIVE CLAUSE IS COMPARED. Where a column says COLLATE, DEFAULT or
NOT NULL twice, SQLite keeps the last; the clauses were compared as a set, so
`COLLATE NOCASE COLLATE BINARY` equalled the same two swapped. Only the last
of each is compared now.

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

#: Column clauses of which SQLite keeps only the last when one is written
#: twice (2026-09-25): a second COLLATE, DEFAULT or NOT NULL replaces the
#: first, where a second CHECK or REFERENCES adds to it.
_LAST_WINS = frozenset({"collate", "default", "not"})

#: What SQLite reads as a keyword directly after DEFAULT, whatever its case
#: (2026-09-25). Any other bare word there is stored as a string with the
#: case it was written in. `values` is `INSERT ... DEFAULT VALUES` in a
#: trigger body, which is no default at all.
_DEFAULT_KEYWORDS = frozenset({"null", "true", "false", "current_time",
                               "current_date", "current_timestamp", "values"})

#: Words after which the grammar admits only a name (2026-09-25). FROM is
#: not one after DISTINCT (`IS DISTINCT FROM "x"` compares with a value).
_NAME_FOLLOWS = frozenset({"collate", "references", "constraint", "from",
                           "join", "into", "update", "table", "index",
                           "trigger", "view"})

#: Tables SQLite writes for itself that are statistics for the planner, not
#: schema: ANALYZE creates them and no query's result depends on them
#: (2026-09-25). `sqlite_sequence` is NOT here -- it exists exactly when an
#: AUTOINCREMENT table does, so it is compared like any other table.
_PLANNER_STATISTICS = ("sqlite_stat",)

#: Names SQLite gives the index it makes for a PRIMARY KEY or UNIQUE clause.
#: They number the clauses by position, so they are compared through the
#: table that owns them, never by name.
_AUTOMATIC_INDEX = "sqlite_autoindex_"


@dataclass(frozen=True)
class _Lexeme:
    """One token as written: a bare word, a quoted word (its text without
    the quotes, and which quotes), a string literal, or an operator."""
    kind: str
    text: str
    quote: str = ""


class Token(str):
    """A normalised token: compared as its text, and knowing what it was
    written as (2026-09-25). `kind` is "word" (bare, so possibly a keyword),
    "name" (quoted, where only a name can stand), "quoted" (quoted text
    kept as written), "string" or "op". Only a bare word can open a clause:
    a column named "check" is a column, not a CHECK."""
    kind = "word"

    @classmethod
    def of(cls, text: str, kind: str) -> "Token":
        token = cls(text)
        token.kind = kind
        return token


def _kind(t) -> str:
    """A token's kind; a plain string is read as a bare word or an operator,
    for callers that pass text they tokenised some other way."""
    kind = getattr(t, "kind", None)
    if kind is not None:
        return kind
    return "word" if t[:1].isalnum() or t[:1] in "_$" else "op"


def _is_op(t, text: str) -> bool:
    return _kind(t) == "op" and t == text


def _lex(sql: str | None) -> list[_Lexeme]:
    """SQL text as lexemes: no comments, no whitespace, nothing normalised."""
    out: list[_Lexeme] = []
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
            out.append(_Lexeme("string", sql[i:k + 1]))
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
            out.append(_Lexeme("quoted", "".join(name), c))
            i = j + 1
        elif c == "[":
            end = sql.find("]", i)
            end = n if end < 0 else end
            out.append(_Lexeme("quoted", sql[i + 1:end], "["))
            i = end + 1
        elif c.isalnum() or c in "_$":
            j = i
            while j < n and (sql[j].isalnum() or sql[j] in "_$"):
                j += 1
            out.append(_Lexeme("word", sql[i:j]))
            i = j
        else:
            for op in _OPERATORS:
                if sql.startswith(op, i):
                    out.append(_Lexeme("op", op))
                    i += len(op)
                    break
            else:
                out.append(_Lexeme("op", c))
                i += 1
    return out


def _structure(lx: list[_Lexeme]) -> tuple[set[int], list[str]]:
    """Which lexemes stand where the grammar admits only a name, and the
    columns a CREATE TABLE declares (lower case), in order."""
    names: set[int] = set()
    columns: list[str] = []
    n = len(lx)

    def bare(i: int, *words: str) -> bool:
        return 0 <= i < n and lx[i].kind == "word" and lx[i].text.lower() in words

    def op(i: int, text: str) -> bool:
        return 0 <= i < n and lx[i].kind == "op" and lx[i].text == text

    def name_at(i: int) -> int:
        """A name at i, schema-qualified or not; the index after it."""
        if i < n and lx[i].kind in ("word", "quoted"):
            names.add(i)
            if op(i + 1, ".") and i + 2 < n and lx[i + 2].kind in ("word", "quoted"):
                names.add(i + 2)
                return i + 3
            return i + 1
        return i

    def closing(i: int) -> int:
        depth = 0
        for k in range(i, n):
            if op(k, "("):
                depth += 1
            elif op(k, ")"):
                depth -= 1
                if depth == 0:
                    return k
        return n

    def items(i: int) -> list[tuple[int, int]]:
        """(start, end) of each item of the parenthesised list at i."""
        end, depth, start, found = closing(i), 0, i + 1, []
        for k in range(i + 1, end):
            if op(k, "("):
                depth += 1
            elif op(k, ")"):
                depth -= 1
            elif depth == 0 and op(k, ","):
                found.append((start, k))
                start = k + 1
        found.append((start, end))
        return [(s, e) for s, e in found if s < e]

    def a_list_of_names(i: int) -> None:
        """Each item of the list at i that is one name alone -- or followed
        by COLLATE and ASC or DESC -- is a name: SQLite reads a lone term of
        a key or index list as a column, whatever its quotes."""
        if not op(i, "("):
            return
        for s, e in items(i):
            j = s + 1
            if bare(j, "collate"):
                j += 2
            if bare(j, "asc", "desc"):
                j += 1
            if j == e and lx[s].kind in ("word", "quoted"):
                names.add(s)

    for i, t in enumerate(lx):
        if t.kind == "op" and t.text == ".":
            for k in (i - 1, i + 1):
                if 0 <= k < n and lx[k].kind == "quoted":
                    names.add(k)
        elif t.kind == "word":
            word = t.text.lower()
            if word in _NAME_FOLLOWS and not (word == "from" and bare(i - 1, "distinct")):
                after = name_at(i + 1)
                if word == "references":
                    a_list_of_names(after)
            elif word == "exists" and bare(i - 1, "not") and bare(i - 2, "if"):
                name_at(i + 1)

    if not bare(0, "create"):
        return names, columns
    j = 1
    while bare(j, "temp", "temporary", "unique", "virtual"):
        j += 1
    what = lx[j].text.lower() if bare(j, "table", "index", "trigger", "view") else ""
    j += 1
    if bare(j, "if"):
        j += 3
    after = name_at(j)
    if what == "table" and op(after, "("):
        for s, e in items(after):
            k = s
            if lx[s].kind == "quoted" or (lx[s].kind == "word"
                                          and lx[s].text.lower() not in _TABLE_CONSTRAINTS):
                names.add(s)
                columns.append(lx[s].text.lower())
                continue
            if bare(k, "constraint"):
                k += 2
            if bare(k, "primary", "foreign"):
                a_list_of_names(k + 2)
            elif bare(k, "unique"):
                a_list_of_names(k + 1)
    elif what == "index":
        k = after
        while k < n and not bare(k, "on"):
            k += 1
        a_list_of_names(name_at(k + 1))
    elif what == "trigger":
        k, depth = after, 0
        while k < n and not (depth == 0 and bare(k, "on", "begin")):
            if bare(k, "of") and bare(k - 1, "update"):
                m = k + 1
                while m < n and not bare(m, "on"):
                    if lx[m].kind in ("word", "quoted"):
                        names.add(m)
                    m += 1
            depth += op(k, "(") - op(k, ")")
            k += 1
        if bare(k, "on"):
            name_at(k + 1)
    elif what == "view":
        a_list_of_names(after)
    return names, columns


def _default_values(lx: list[_Lexeme], first: bool) -> set[int]:
    """The lexemes that are a DEFAULT's value: the word or quoted word
    directly after DEFAULT (past a sign), and the first when `first`."""
    starts = [0] if first else []
    starts += [i + 1 for i, t in enumerate(lx)
               if t.kind == "word" and t.text.lower() == "default"
               and not (i > 0 and lx[i - 1].kind == "word"
                        and lx[i - 1].text.lower() == "set")]
    found = set()
    for j in starts:
        if j < len(lx) and lx[j].kind == "op" and lx[j].text in "+-":
            j += 1
        if j < len(lx) and lx[j].kind in ("word", "quoted"):
            found.add(j)
    return found


def _as_written(t: _Lexeme) -> str:
    if t.quote == "[":
        return "[" + t.text + "]"
    return t.quote + t.text.replace(t.quote, t.quote * 2) + t.quote


def _normalised(sql: str | None, columns=(), *, default_value: bool = False
                ) -> list[Token]:
    lx = _lex(sql)
    names, declared = _structure(lx)
    values = _default_values(lx, default_value)
    known = {c.lower() for c in columns} | set(declared)
    out: list[Token] = []
    for i, t in enumerate(lx):
        if t.kind == "word":
            keep = (i in values and t.text.lower() not in _DEFAULT_KEYWORDS
                    and not t.text[:1].isdigit())
            out.append(Token.of(t.text if keep else t.text.lower(), "word"))
        elif t.kind == "quoted":
            if i not in values and (i in names or t.text.lower() in known):
                out.append(Token.of(t.text.lower(), "name"))
            else:
                out.append(Token.of(_as_written(t), "quoted"))
        else:
            out.append(Token.of(t.text, t.kind))
    return out


def tokens(sql: str | None, columns=()) -> list[Token]:
    """SQL text as normalised tokens: no comments, no whitespace, keywords
    and names in lower case and unquoted, string literals exact -- and
    quoted text kept as written wherever it is not certainly a name.

    `columns` are the names an expression in this text may resolve to: an
    index's table's columns. A CREATE TABLE resolves against its own."""
    return _normalised(sql, columns)


def default_tokens(text: str | None) -> list[Token]:
    """A DEFAULT's value as SQLite's PRAGMA reports it, normalised as it
    would be after the word DEFAULT: a bare word keeps its case."""
    return _normalised(text, default_value=True)


def object_tokens(kind: str, sql: str | None, columns=()) -> list[Token]:
    """An index, trigger or view as normalised tokens, for comparing two
    definitions of it. An index's expressions resolve against its table's
    `columns`; a trigger's and a view's resolve against nothing here, so
    their quoted text is kept as written (2026-09-25)."""
    return tokens(sql, columns if kind == "index" else ())


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
        if _is_op(t, "("):
            depth += 1
        elif _is_op(t, ")"):
            depth -= 1
        if _is_op(t, ",") and depth == 0:
            parts.append(current)
            current = []
        else:
            current.append(t)
    if current:
        parts.append(current)
    return parts


def _clause_kind(clause: tuple[str, ...]) -> str:
    """What a clause is: its first word, or the word after a CONSTRAINT's
    name."""
    if clause[0] == "constraint" and len(clause) > 2:
        return clause[2]
    return clause[0]


def _effective(clauses: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """The clauses SQLite keeps: of a COLLATE, DEFAULT or NOT NULL written
    more than once, the last (2026-09-25)."""
    last = {_clause_kind(c): k for k, c in enumerate(clauses)
            if _clause_kind(c) in _LAST_WINS}
    return [c for k, c in enumerate(clauses)
            if _clause_kind(c) not in _LAST_WINS or last[_clause_kind(c)] == k]


def _column(rest: list[str]) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    """A column's type tokens, and its effective clauses in the order
    written."""
    kind: list[str] = []
    clauses: list[tuple[str, ...]] = []
    current: list[str] | None = None
    depth = 0
    for i, t in enumerate(rest):
        after = rest[i + 1] if i + 1 < len(rest) else None
        starts = (
            depth == 0 and _kind(t) == "word" and t in _COLUMN_CLAUSES
            and not (t == "null" and current
                     and (current[-1] == "not" or current[0] in _OWNS_A_NULL))
            and not (t == "as" and current and current[0] == "generated")
            and not (current and current[0] == "constraint" and len(current) < 3)
            # NOT DEFERRABLE AND SET DEFAULT BELONG TO THEIR REFERENCES
            # (2026-09-26, found by the prover of the 5a' fixes). Each opened
            # a clause of its own whose kind is NOT NULL's or DEFAULT's, and
            # of those only the last is kept -- so `x INTEGER NOT NULL
            # REFERENCES p (id) NOT DEFERRABLE` lost its NOT NULL, and
            # `x INTEGER DEFAULT 5 REFERENCES p (id) ON DELETE SET DEFAULT`
            # its DEFAULT 5, and each compared equal to the same column
            # without it -- in the text comparison and in the migration's own
            # question -- while SQLite refused a NULL in one and not the
            # other, and stored 5 in one and not the other.
            and not (t == "not" and after is not None and _kind(after) == "word"
                     and after == "deferrable")
            and not (t == "default" and current and _kind(current[-1]) == "word"
                     and current[-1] == "set"))
        if starts:
            if current is not None:
                clauses.append(tuple(current))
            current = [t]
        elif current is None:
            kind.append(t)
        else:
            current.append(t)
        if _is_op(t, "("):
            depth += 1
        elif _is_op(t, ")"):
            depth -= 1
    if current is not None:
        clauses.append(tuple(current))
    return tuple(kind), _effective(clauses)


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
    opened = next(k for k, t in enumerate(toks) if _is_op(t, "("))
    depth, closed = 0, len(toks) - 1
    for k in range(opened, len(toks)):
        if _is_op(toks[k], "("):
            depth += 1
        elif _is_op(toks[k], ")"):
            depth -= 1
            if depth == 0:
                closed = k
                break
    columns: dict = {}
    order: list[str] = []
    constraints: list[tuple[str, ...]] = []
    for item in _split_top(toks[opened + 1:closed]):
        if _kind(item[0]) == "word" and item[0] in _TABLE_CONSTRAINTS:
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
        # THE DEFAULT AS A DEFAULT (2026-09-25): the PRAGMA reports its text,
        # and a bare word there is a string whose case is kept.
        schema.columns[name] = {
            row[1].lower(): (tuple(tokens(row[2])), row[3],
                             tuple(default_tokens(row[4])) if row[4] is not None
                             else None,
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
        else:
            ta = object_tokens(kind, sql_a, a.columns.get(table_a, {}))
            tb = object_tokens(kind, sql_b, b.columns.get(table_b, {}))
            if ta != tb:
                found += _both_ways(obj, "its definition: {}", [show(ta)], [show(tb)])
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
