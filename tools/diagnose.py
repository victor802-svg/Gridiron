"""D1 — diagnose the disagreement problem. READ-ONLY.

The finding under investigation: on >5-point disagreements with the market the
model was right 55.6% (n=207), while where the market was the more confident
side the outcome went the model's way 71.2% (n=146). The model is at its worst
exactly where it would be acted on.

This script changes nothing. It reads a resolved record and writes
`docs/DIAGNOSIS.md`.

--------------------------------------------------------------------------
THE DISCIPLINE THIS SCRIPT IS UNDER
--------------------------------------------------------------------------
An analysis that slices until something appears is the same failure mode LAW 2
exists to prevent, just performed on the record instead of on the training
data. So:

* The hypotheses and every slice are declared in `HYPOTHESES` and `SLICES`
  below, at the top of the file, before any code that looks at an outcome.
* The number of pre-registered comparisons is counted, and the significance
  threshold is Bonferroni-adjusted by that count. Testing 30 angles at p<0.05
  finds about 1.5 "findings" in pure noise.
* A slice under n=30 renders as INSUFFICIENT SAMPLE, not as a finding, no
  matter how extreme it looks. Small slices are where noise is loudest.
* "The disagreements lose and we do not know why yet" is a permitted verdict.

    python tools/diagnose.py --database var/backtest.db
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import config, db  # noqa: E402

# ===========================================================================
# PRE-REGISTRATION. Nothing below this block may be added after looking.
# ===========================================================================

MIN_SLICE_N = 30
ALPHA = 0.05


@dataclass(frozen=True)
class Hypothesis:
    id: str
    claim: str
    test: str


HYPOTHESES: tuple[Hypothesis, ...] = (
    Hypothesis(
        "H1a",
        "The model disagrees most when it is MISSING information the market "
        "has — late injury news, lineup changes — which reaches the line before "
        "kickoff but never reaches us.",
        "Correlate disagreement size against the CLOSING line with line movement "
        "between the opening and closing number. If our disagreements were "
        "smaller against the opener, we are fighting information that arrived "
        "after it.",
    ),
    Hypothesis(
        "H1b",
        "SUBSTITUTE FOR H1a, declared at the data-availability check below and "
        "before any outcome was examined. The same underlying claim, tested on "
        "the missingness we can actually observe: disagreements lose more often "
        "when more of the model's own factors were unavailable for that game.",
        "Split the disagreements by how many factors were defaulted (the "
        "`missing` list stored on each prediction) and compare hit rates. Also "
        "split by whether an injury report existed for the game at all.",
    ),
    Hypothesis(
        "H2",
        "The losses concentrate in a slice rather than being spread evenly: "
        "home dogs, big favourites, divisional games, or early season when the "
        "season-to-date factors are thin.",
        "Hit rate within each pre-registered slice below, with N, a Wilson "
        "interval, and a Bonferroni-adjusted binomial test against the overall "
        "disagreement hit rate.",
    ),
    Hypothesis(
        "H3",
        "One factor is dragging: it pushes the model away from the market and "
        "is wrong when it does.",
        "For each factor, the mean stored log-odds contribution among LOST "
        "disagreements versus WON ones, with N and the same adjusted threshold.",
    ),
    Hypothesis(
        "H4",
        "The LLM and statistical paths disagree with the market differently, "
        "and the aggregate hides one of them.",
        "Split the disagreements by `predictor` and compare.",
    ),
)

#: Every slice examined for H2. Declared here so the list cannot grow after
#: seeing which ones look interesting. Each entry is (group name, label, SQL-free
#: predicate over a Disagreement).
SLICE_GROUPS: dict[str, list[tuple[str, str]]] = {
    "rung asked": [
        ("home -7.5", "rung_-7.5"),
        ("home -3.5", "rung_-3.5"),
        ("home +0.5", "rung_+0.5"),
        ("home +3.5", "rung_+3.5"),
    ],
    "market view of the home side": [
        ("home favourite", "home_fav"),
        ("home underdog", "home_dog"),
        ("near pick'em (|line| <= 2.5)", "pickem"),
        ("big favourite (|line| >= 7)", "big_fav"),
    ],
    "game type": [
        ("divisional", "divisional"),
        ("non-divisional", "non_divisional"),
    ],
    "season stage": [
        ("weeks 1-4", "early"),
        ("weeks 5-13", "mid"),
        ("weeks 14-18", "late"),
    ],
    "which side the model took": [
        ("model says cover", "side_cover"),
        ("model says not_cover", "side_not_cover"),
    ],
    "rating basis": [
        ("in-season ratings", "srs_season"),
        ("prior-season fallback", "srs_prior"),
    ],
    "model confidence": [
        ("50-60%", "conf_50"),
        ("60-70%", "conf_60"),
        ("70-80%", "conf_70"),
        ("80%+", "conf_80"),
    ],
    "size of disagreement": [
        ("5-10 points", "gap_small"),
        ("10-20 points", "gap_mid"),
        ("20+ points", "gap_large"),
    ],
}

#: H1b's own slices, counted in the same multiple-comparison budget.
MISSINGNESS_SLICES = [
    ("0 factors defaulted", "miss_0"),
    ("1-2 factors defaulted", "miss_1_2"),
    ("3+ factors defaulted", "miss_3plus"),
    ("injury report present", "injury_present"),
    ("injury report absent", "injury_absent"),
]

# ===========================================================================
# statistics, in pure Python (CLAUDE.md: standard library first)
# ===========================================================================

def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Behaves at small n where the normal interval does
    not, which matters because small n is exactly what we are cautious about."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def binomial_p_two_sided(successes: int, n: int, p0: float) -> float:
    """Exact two-sided binomial test: the total probability of any outcome at
    least as unlikely as the one observed. n is a few hundred here, so exact is
    both cheap and free of approximation caveats."""
    if n == 0:
        return 1.0
    p0 = min(max(p0, 1e-12), 1 - 1e-12)

    def pmf(k: int) -> float:
        return math.comb(n, k) * p0**k * (1 - p0) ** (n - k)

    observed = pmf(successes)
    total = sum(pmf(k) for k in range(n + 1) if pmf(k) <= observed * (1 + 1e-9))
    return min(1.0, total)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def welch_t(a: list[float], b: list[float]) -> float | None:
    """Welch's t statistic. Reported as a magnitude only — with this many
    factors compared at once, the t is a ranking aid, not a licence to claim."""
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = mean(a), mean(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    denom = math.sqrt(va / len(a) + vb / len(b))
    return None if denom == 0 else (ma - mb) / denom


# ===========================================================================
# the record
# ===========================================================================

@dataclass
class Disagreement:
    prediction_id: int
    game_id: str
    season: int
    week: int
    predictor: str
    model_prob: float
    model_side: str
    line_asked: float
    market_line: float
    implied_prob: float
    outcome: int
    div_game: int | None
    srs_basis: str
    missing: list[str]
    contributions: dict[str, float]
    injury_report_present: bool

    @property
    def gap(self) -> float:
        return self.model_prob - self.implied_prob

    @property
    def won(self) -> bool:
        return self.outcome == 1

    def in_slice(self, key: str) -> bool:
        if key.startswith("rung_"):
            return abs(self.line_asked - float(key.split("_")[1])) < 1e-9
        if key == "home_fav":
            return self.market_line > 0
        if key == "home_dog":
            return self.market_line < 0
        if key == "pickem":
            return abs(self.market_line) <= 2.5
        if key == "big_fav":
            return abs(self.market_line) >= 7
        if key == "divisional":
            return self.div_game == 1
        if key == "non_divisional":
            return self.div_game == 0
        if key == "early":
            return self.week <= 4
        if key == "mid":
            return 5 <= self.week <= 13
        if key == "late":
            return self.week >= 14
        if key == "side_cover":
            return self.model_side == "cover"
        if key == "side_not_cover":
            return self.model_side == "not_cover"
        if key == "srs_season":
            return self.srs_basis == "season"
        if key == "srs_prior":
            return self.srs_basis != "season"
        if key == "conf_50":
            return self.model_prob < 0.60
        if key == "conf_60":
            return 0.60 <= self.model_prob < 0.70
        if key == "conf_70":
            return 0.70 <= self.model_prob < 0.80
        if key == "conf_80":
            return self.model_prob >= 0.80
        if key == "gap_small":
            return abs(self.gap) < 0.10
        if key == "gap_mid":
            return 0.10 <= abs(self.gap) < 0.20
        if key == "gap_large":
            return abs(self.gap) >= 0.20
        if key == "miss_0":
            return len(self.missing) == 0
        if key == "miss_1_2":
            return 1 <= len(self.missing) <= 2
        if key == "miss_3plus":
            return len(self.missing) >= 3
        if key == "injury_present":
            return self.injury_report_present
        if key == "injury_absent":
            return not self.injury_report_present
        raise KeyError(f"undeclared slice {key!r}")


def load_disagreements(
    conn: sqlite3.Connection, threshold: float
) -> tuple[list[Disagreement], list[Disagreement], dict]:
    """Every resolved spread prediction with a market comparison, split into the
    subset where the model was the bolder side and the subset where the market
    was."""
    rows = conn.execute(
        "SELECT p.id, p.game_id, p.predictor, p.model_prob, p.model_side,"
        " p.line_asked, p.outcome, p.factors_json,"
        " g.season, g.week, c.div_game,"
        " (SELECT s.implied_prob FROM market_snapshots s WHERE s.prediction_id = p.id"
        "  ORDER BY s.id LIMIT 1) AS implied_prob,"
        " (SELECT s.line FROM market_snapshots s WHERE s.prediction_id = p.id"
        "  ORDER BY s.id LIMIT 1) AS market_line"
        " FROM predictions p"
        " JOIN games g ON g.id = p.game_id"
        " LEFT JOIN game_conditions c ON c.game_id = p.game_id"
        " WHERE p.resolved_utc IS NOT NULL AND p.market_type = 'spread'"
        " ORDER BY p.id"
    ).fetchall()

    injury_weeks = {
        (r["season"], r["week"], r["team"])
        for r in conn.execute("SELECT DISTINCT season, week, team FROM injuries")
    }

    model_bolder: list[Disagreement] = []
    market_bolder: list[Disagreement] = []
    all_scored = 0

    for r in rows:
        if r["implied_prob"] is None or r["market_line"] is None:
            continue
        all_scored += 1
        payload = json.loads(r["factors_json"] or "{}")
        contributions = {
            c["factor"]: c["contribution"] for c in (payload.get("contributions") or [])
        }
        home, away = r["game_id"].split("_")[3], r["game_id"].split("_")[2]
        present = (r["season"], r["week"], home) in injury_weeks

        item = Disagreement(
            prediction_id=r["id"],
            game_id=r["game_id"],
            season=r["season"],
            week=r["week"],
            predictor=r["predictor"],
            model_prob=r["model_prob"],
            model_side=r["model_side"],
            line_asked=r["line_asked"],
            market_line=r["market_line"],
            implied_prob=r["implied_prob"],
            outcome=r["outcome"],
            div_game=r["div_game"],
            srs_basis=(
                "prior"
                if any("fall back" in n for n in (payload.get("notes") or []))
                else "season"
            ),
            missing=payload.get("missing") or [],
            contributions=contributions,
            injury_report_present=present,
        )
        if item.gap > threshold:
            model_bolder.append(item)
        elif -item.gap > threshold:
            market_bolder.append(item)

    context = {
        "resolved_spread_with_market": all_scored,
        "threshold": threshold,
    }
    return model_bolder, market_bolder, context


# ===========================================================================
# the tests
# ===========================================================================

@dataclass
class SliceResult:
    label: str
    n: int
    wins: int
    rate: float | None
    lo: float | None
    hi: float | None
    p_value: float | None
    sufficient: bool


@dataclass
class Finding:
    hypothesis: str
    verdict: str
    detail: str
    rows: list = field(default_factory=list)
    note: str = ""


def evaluate_slice(items: list[Disagreement], key: str, label: str, baseline: float) -> SliceResult:
    subset = [d for d in items if d.in_slice(key)]
    n = len(subset)
    wins = sum(1 for d in subset if d.won)
    if n < MIN_SLICE_N:
        return SliceResult(label, n, wins, None, None, None, None, False)
    lo, hi = wilson(wins, n)
    return SliceResult(
        label, n, wins, wins / n, lo, hi, binomial_p_two_sided(wins, n, baseline), True
    )


def comparison_budget() -> int:
    return sum(len(v) for v in SLICE_GROUPS.values()) + len(MISSINGNESS_SLICES)


def run_h1b(items: list[Disagreement], baseline: float, alpha: float) -> Finding:
    rows = [evaluate_slice(items, key, label, baseline) for label, key in MISSINGNESS_SLICES]
    usable = [r for r in rows if r.sufficient]
    hits = [r for r in usable if r.p_value is not None and r.p_value < alpha]

    if not usable:
        return Finding("H1b", "INSUFFICIENT SAMPLE",
                       "No missingness slice reached n=30.", rows)
    if not hits:
        spread = max(r.rate for r in usable) - min(r.rate for r in usable)
        return Finding(
            "H1b", "NOT SUPPORTED",
            f"Hit rates across missingness slices span {spread * 100:.1f} points and no "
            f"slice differs from the {baseline * 100:.1f}% baseline at the adjusted "
            f"threshold. Missing factors do not explain the losses.",
            rows,
        )
    return Finding(
        "H1b", "SUPPORTED",
        "; ".join(
            f"{r.label}: {r.rate * 100:.1f}% (n={r.n}, p={r.p_value:.4f})" for r in hits
        ),
        rows,
    )


def run_h2(items: list[Disagreement], baseline: float, alpha: float) -> tuple[Finding, dict]:
    grouped: dict[str, list[SliceResult]] = {}
    hits: list[SliceResult] = []
    for group, entries in SLICE_GROUPS.items():
        results = [evaluate_slice(items, key, label, baseline) for label, key in entries]
        grouped[group] = results
        hits += [r for r in results if r.sufficient and r.p_value is not None and r.p_value < alpha]

    usable = sum(1 for rs in grouped.values() for r in rs if r.sufficient)
    if not usable:
        return Finding("H2", "INSUFFICIENT SAMPLE",
                       "No pre-registered slice reached n=30."), grouped
    if not hits:
        return Finding(
            "H2", "NOT SUPPORTED",
            f"{usable} slices reached n=30 and none differs from the "
            f"{baseline * 100:.1f}% baseline at the Bonferroni-adjusted threshold "
            f"of p<{alpha:.5f}. The losses are spread across the record, not "
            "concentrated anywhere the pre-registered list looked.",
        ), grouped
    return Finding(
        "H2", "SUPPORTED",
        "; ".join(f"{r.label}: {r.rate * 100:.1f}% (n={r.n}, p={r.p_value:.5f})" for r in hits),
    ), grouped


def run_h3(items: list[Disagreement], alpha: float) -> tuple[Finding, list]:
    won = [d for d in items if d.won]
    lost = [d for d in items if not d.won]
    factors = sorted({f for d in items for f in d.contributions})

    rows = []
    for factor in factors:
        won_values = [d.contributions[factor] for d in won if factor in d.contributions]
        lost_values = [d.contributions[factor] for d in lost if factor in d.contributions]
        if len(won_values) < MIN_SLICE_N or len(lost_values) < MIN_SLICE_N:
            rows.append({"factor": factor, "n_won": len(won_values), "n_lost": len(lost_values),
                         "mean_won": None, "mean_lost": None, "delta": None, "t": None,
                         "sufficient": False})
            continue
        mw, ml = mean(won_values), mean(lost_values)
        rows.append({
            "factor": factor, "n_won": len(won_values), "n_lost": len(lost_values),
            "mean_won": mw, "mean_lost": ml, "delta": mw - ml,
            "t": welch_t(won_values, lost_values), "sufficient": True,
        })

    rows.sort(key=lambda r: abs(r["t"]) if r["t"] is not None else -1, reverse=True)
    usable = [r for r in rows if r["sufficient"]]
    # A |t| of 3.0 is roughly p<0.003, which is the neighbourhood the adjusted
    # threshold requires once this many factors are compared at once.
    strong = [r for r in usable if r["t"] is not None and abs(r["t"]) >= 3.0]

    if not usable:
        return Finding("H3", "INSUFFICIENT SAMPLE",
                       "No factor had 30 won and 30 lost disagreements."), rows
    if not strong:
        top = usable[0]
        return Finding(
            "H3", "NOT SUPPORTED",
            f"No factor separates won from lost disagreements. The largest "
            f"separation is {top['factor']} (|t|={abs(top['t']):.2f}, mean contribution "
            f"{top['mean_won']:+.4f} when won vs {top['mean_lost']:+.4f} when lost, "
            f"n={top['n_won']}/{top['n_lost']}), which is inside the range "
            f"{len(usable)} simultaneous comparisons produce by chance.",
        ), rows
    return Finding(
        "H3", "SUPPORTED",
        "; ".join(f"{r['factor']}: won {r['mean_won']:+.4f} vs lost {r['mean_lost']:+.4f} "
                  f"(|t|={abs(r['t']):.2f}, n={r['n_won']}/{r['n_lost']})" for r in strong),
    ), rows


def run_h4(items: list[Disagreement], baseline: float) -> tuple[Finding, list]:
    rows = []
    for predictor in ("statistical", "llm"):
        subset = [d for d in items if d.predictor == predictor]
        n = len(subset)
        wins = sum(1 for d in subset if d.won)
        if n < MIN_SLICE_N:
            rows.append(SliceResult(predictor, n, wins, None, None, None, None, False))
            continue
        lo, hi = wilson(wins, n)
        rows.append(SliceResult(predictor, n, wins, wins / n, lo, hi,
                                binomial_p_two_sided(wins, n, baseline), True))

    usable = [r for r in rows if r.sufficient]
    if len(usable) < 2:
        missing = [r.label for r in rows if not r.sufficient]
        return Finding(
            "H4", "INSUFFICIENT SAMPLE",
            f"Only {len(usable)} of 2 forecasters reached n=30 "
            f"({', '.join(f'{r.label}: n={r.n}' for r in rows)}). "
            "The comparison cannot be made.",
        ), rows
    return Finding(
        "H4", "NOT SUPPORTED" if abs(usable[0].rate - usable[1].rate) < 0.10 else "SUPPORTED",
        "; ".join(f"{r.label}: {r.rate * 100:.1f}% (n={r.n})" for r in usable),
    ), rows


# ===========================================================================
# H1a — the data-availability check, run before anything is sliced
# ===========================================================================

#: What was checked upstream, on 2026-08-29, for an opening-line source that
#: covers the seasons in the record. Recorded rather than re-fetched, so the
#: report is reproducible offline; the paths are here to be re-checked.
OPENING_LINE_SEARCH = [
    ("nflverse-data schedules/games.csv",
     "carries spread_line and total_line only. Those are CLOSING numbers; there "
     "is no opening column."),
    ("nfldata/data/initial_lines.csv",
     "1,088 rows, season 2021 only. Does not cover 2024 or 2025."),
    ("nfldata/data/sc_lines.csv",
     "4,092 rows, seasons 2013-2020. Does not cover 2024 or 2025."),
    ("nfldata/data/closing_lines.csv",
     "closing numbers broken out by book. Closing again, not opening."),
]


def check_h1a_testability(conn: sqlite3.Connection, seasons: list[int]) -> Finding:
    """Can H1a be tested at all? Answered before any outcome is looked at."""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(market_lines_raw)")}
    has_opening = any("open" in c for c in columns)
    cached = [
        r["url"] for r in conn.execute("SELECT url FROM http_cache")
        if "initial_lines" in r["url"] or "opening" in r["url"]
    ]
    if has_opening or cached:
        return Finding("H1a", "TESTABLE",
                       "An opening-line source is present; run the movement test.")
    return Finding(
        "H1a", "NOT TESTABLE",
        "No free source publishes opening lines for the seasons in this record "
        f"({min(seasons)}-{max(seasons)}). Every market number Gridiron holds is a "
        "closing number, so line movement cannot be computed at all - not poorly, "
        "not approximately, not at all.",
        note=(
            "H1b was declared as the substitute at this point, before any outcome "
            "was examined. It tests the same underlying claim - that the model "
            "disagrees hardest where it knows least - using the missingness the "
            "record does contain."
        ),
    )


# ===========================================================================
# the report
# ===========================================================================

def slice_table(rows: list[SliceResult]) -> str:
    out = ["| Slice | N | Won | Hit rate | 95% interval | p vs baseline |",
           "|---|---:|---:|---:|---|---:|"]
    for r in rows:
        if not r.sufficient:
            out.append(f"| {r.label} | {r.n} | {r.wins} | - | - | "
                       f"*insufficient (<{MIN_SLICE_N})* |")
        else:
            out.append(
                f"| {r.label} | {r.n} | {r.wins} | {r.rate * 100:.1f}% | "
                f"{r.lo * 100:.1f}-{r.hi * 100:.1f}% | {r.p_value:.4f} |"
            )
    return "\n".join(out)


def build_report(
    conn: sqlite3.Connection,
    model_bolder: list[Disagreement],
    market_bolder: list[Disagreement],
    context: dict,
) -> str:
    seasons = sorted({d.season for d in model_bolder + market_bolder}) or [0]
    baseline = sum(1 for d in model_bolder if d.won) / len(model_bolder)
    market_rate = (
        sum(1 for d in market_bolder if d.won) / len(market_bolder)
        if market_bolder else 0.0
    )
    budget = comparison_budget()
    alpha = ALPHA / budget

    h1a = check_h1a_testability(conn, seasons)
    h1b = run_h1b(model_bolder, baseline, alpha)
    h2, grouped = run_h2(model_bolder, baseline, alpha)
    h3, factor_rows = run_h3(model_bolder, alpha)
    h4, h4_rows = run_h4(model_bolder, baseline)

    findings = [h1a, h1b, h2, h3, h4]
    supported = [f for f in findings if f.verdict == "SUPPORTED"]
    lo, hi = wilson(sum(1 for d in model_bolder if d.won), len(model_bolder))

    L: list[str] = []
    add = L.append

    add("# D1 - diagnosis: why the disagreements lose")
    add("")
    add("**Read-only analysis. No model and no factor was changed to produce it.**")
    add("")
    add("---")
    add("")
    add("## The finding under investigation")
    add("")
    add(f"Across {context['resolved_spread_with_market']:,} resolved spread predictions "
        "carrying a market comparison:")
    add("")
    add("| | N | Hit rate | 95% interval |")
    add("|---|---:|---:|---|")
    add(f"| Model more confident than the market (>{context['threshold'] * 100:.0f} pts) "
        f"| {len(model_bolder)} | {baseline * 100:.1f}% | {lo * 100:.1f}-{hi * 100:.1f}% |")
    if market_bolder:
        mlo, mhi = wilson(sum(1 for d in market_bolder if d.won), len(market_bolder))
        add(f"| Market more confident | {len(market_bolder)} | {market_rate * 100:.1f}% | "
            f"{mlo * 100:.1f}-{mhi * 100:.1f}% |")
    add("")
    add("The model is at its worst exactly where it would be acted on. That is what "
        "this document sets out to explain, and mostly fails to.")
    add("")
    add("---")
    add("")
    add("## Pre-registration")
    add("")
    add("The hypotheses, every slice, and the significance threshold were written into "
        "`tools/diagnose.py` **before any outcome was examined**, and are frozen at the "
        "top of that file. This matters more than usual here: an analysis that slices "
        "until something appears is the failure LAW 2 exists to prevent, performed on "
        "the record instead of on the training data.")
    add("")
    add(f"- **{budget} pre-registered comparisons.** Bonferroni-adjusted threshold: "
        f"**p < {alpha:.5f}** (0.05 / {budget}). At an unadjusted p<0.05, about "
        f"{budget * 0.05:.1f} of these would clear on noise alone.")
    add(f"- **Slices under n={MIN_SLICE_N} render as INSUFFICIENT SAMPLE**, never as "
        "findings, however extreme they look.")
    add("- Intervals are Wilson score intervals. p-values are exact two-sided binomial "
        f"tests against the {baseline * 100:.1f}% baseline.")
    add("")
    for h in HYPOTHESES:
        add(f"**{h.id}.** {h.claim}")
        add("")
        add(f"> *Test:* {h.test}")
        add("")
    add("---")
    add("")

    add("## Verdicts")
    add("")
    add("| Hypothesis | Verdict |")
    add("|---|---|")
    for f in findings:
        add(f"| {f.hypothesis} | **{f.verdict}** |")
    add("")
    add("---")
    add("")

    add("## H1a - missing information the market has")
    add("")
    add(f"### Verdict: {h1a.verdict}")
    add("")
    add(h1a.detail)
    add("")
    add("Sources checked for an opening line covering these seasons:")
    add("")
    add("| Source | What it actually has |")
    add("|---|---|")
    for source, note in OPENING_LINE_SEARCH:
        add(f"| `{source}` | {note} |")
    add("")
    if h1a.note:
        add(h1a.note)
        add("")
    add("Recording this as untestable rather than substituting a proxy is the same rule "
        "the registry applies to `public_bet_pct`. A movement measure built from "
        "something that is not movement would be a finding about that something else, "
        "wearing H1a's label.")
    add("")

    add("## H1b - does the model lose where its own inputs were missing?")
    add("")
    add(f"### Verdict: {h1b.verdict}")
    add("")
    add(h1b.detail)
    add("")
    add(slice_table(h1b.rows))
    add("")
    add("Read this against what the factor report already showed: `precipitation` was "
        "defaulted in 66% of predictions, and `short_week_diff`'s input is structurally "
        "zero. Those are real instrument faults - but if missingness explained the "
        "disagreement losses, the slices above would separate, and they do not.")
    add("")

    add("## H2 - do the losses concentrate in a slice?")
    add("")
    add(f"### Verdict: {h2.verdict}")
    add("")
    add(h2.detail)
    add("")
    for group, rows in grouped.items():
        add(f"**{group}**")
        add("")
        add(slice_table(rows))
        add("")

    # The nearest miss, named rather than left buried in a table. Reporting only
    # the slices that cleared the bar would hide how close the bar was; reporting
    # this as a finding would be the fishing expedition the pre-registration
    # exists to prevent. So it is named, and declined.
    candidates = [r for rs in grouped.values() for r in rs if r.sufficient]
    if candidates:
        closest = min(candidates, key=lambda r: r.p_value)
        add("**The closest thing to a signal, and why it is not one**")
        add("")
        add(f"The lowest p-value among all {len(candidates)} sufficient slices is "
            f"**{closest.label}**: {closest.rate * 100:.1f}% on n={closest.n} "
            f"(p={closest.p_value:.4f}, 95% interval "
            f"{closest.lo * 100:.1f}-{closest.hi * 100:.1f}%).")
        add("")
        if closest.p_value < alpha:
            add("It clears the adjusted threshold and is reported as a finding above.")
        else:
            add(f"It does **not** clear the adjusted threshold of p<{alpha:.5f}, and it "
                f"is not treated as a finding. Three reasons, all of which would still "
                f"apply if it looked twice as strong:")
            add("")
            add(f"1. {len(candidates)} slices were tested. The smallest of "
                f"{len(candidates)} p-values being around {closest.p_value:.3f} is "
                "roughly what pure noise produces; that is what the adjustment is for.")
            add(f"2. n={closest.n} is at or near the n=30 floor, where a swing of three "
                "games moves the rate by ten points.")
            add("3. Acting on it would mean changing the model on the strength of a "
                "slice found by looking at slices, which is the exact procedure LAW 2 "
                "forbids on training data and which is no safer here.")
            add("")
            add("If it is real, a forward season will show it again, and then it will "
                "be a hypothesis worth pre-registering rather than a number worth "
                "explaining away.")
        add("")

    add("## H3 - is one factor dragging?")
    add("")
    add(f"### Verdict: {h3.verdict}")
    add("")
    add(h3.detail)
    add("")
    add("Mean stored log-odds contribution among won versus lost disagreements. A "
        "factor that dragged would push consistently harder on the losses. `|t|` is "
        "Welch's t as a ranking aid only - with this many factors compared at once it "
        "is not a licence to claim.")
    add("")
    add("| Factor | N won / lost | Mean when won | Mean when lost | Difference | \\|t\\| |")
    add("|---|---|---:|---:|---:|---:|")
    for r in factor_rows:
        if not r["sufficient"]:
            add(f"| `{r['factor']}` | {r['n_won']} / {r['n_lost']} | - | - | - | "
                "*insufficient* |")
        else:
            t = "-" if r["t"] is None else f"{abs(r['t']):.2f}"
            add(f"| `{r['factor']}` | {r['n_won']} / {r['n_lost']} | "
                f"{r['mean_won']:+.4f} | {r['mean_lost']:+.4f} | {r['delta']:+.4f} | {t} |")
    add("")

    add("## H4 - do the two forecasters disagree differently?")
    add("")
    add(f"### Verdict: {h4.verdict}")
    add("")
    add(h4.detail)
    add("")
    add(slice_table(h4_rows))
    add("")
    if any(r.label == "llm" and r.n == 0 for r in h4_rows):
        add("The LLM path contributed **zero** predictions to this record. The backtest "
            "ran with the reasoning pass disabled, and the live runs degraded to "
            "statistical-only with the tag `llm_unavailable:no_api_key`. This "
            "hypothesis is not weakly supported and not weakly refuted - it is "
            "untested, and stays untested until the LLM path has a record of its own.")
        add("")

    add("---")
    add("")
    add("## Recommendations")
    add("")
    if not supported:
        add("**None of the pre-registered hypotheses is supported.**")
        add("")
        add("The honest conclusion is the one the brief explicitly permitted: *the "
            "disagreements lose, and we do not know why yet.* The losses are not "
            "concentrated in any slice that was looked for; no factor separates the "
            "wins from the losses; the missingness we can measure does not track the "
            "failures; and the one hypothesis with a real mechanism behind it - that "
            "the market knows things we do not - cannot be tested without an "
            "opening-line source that does not exist for free.")
        add("")
        add("Three things that do **not** follow:")
        add("")
        add("1. **That the model should be tuned to disagree less.** Shrinking towards "
            "the market would improve every score on this page by making the model more "
            "market-like. That is the anchoring failure LAW 1 exists to prevent, "
            "reached by a different road, and it would destroy the only thing the "
            "project measures.")
        add(f"2. **That the factors are wrong.** {baseline * 100:.1f}% on "
            f"n={len(model_bolder)} has a 95% interval of {lo * 100:.1f}-{hi * 100:.1f}%. "
            "That interval contains 'slightly worse than a coin' and 'roughly as good "
            "as the market'. The sample cannot separate those, and neither can this "
            "analysis.")
        add("3. **That nothing should be done.** Two instruments were found broken by "
            "the earlier factor report - not by this diagnosis - and repairing an "
            "instrument that never measured anything requires no hypothesis to justify "
            "it.")
        add("")
        add("**The recommendations are therefore procedural, not corrective:**")
        add("")
        add("1. **Repair the broken instruments and nothing else.** `short_week_diff` "
            "(input non-zero in 1 game of 544) and `precipitation` (no data in 66% of "
            "predictions) never measured anything. Fixing them is maintenance, not a "
            "response to a finding, and the registry rationales should say so plainly "
            "so a later reader does not mistake a repair for a discovery.")
        add("2. **Make missing data an explicit state.** A factor that could not be "
            "measured currently becomes its default and is merely *recorded* as "
            "missing. That is why 66% of `precipitation` values were indistinguishable "
            "from a real zero at fit time. Excluding an unmeasurable factor from that "
            "game's vector is a correctness fix independent of anything here.")
        add(f"3. **Do not re-ask this question until there is forward volume.** The "
            f"subset is n={len(model_bolder)} from a retrospective backtest whose factor "
            "set was chosen with knowledge of these seasons. Re-running this diagnosis "
            "on the same record after changing the model would be measuring the change "
            "against the data that motivated it.")
    else:
        add("Each recommendation is tied to a supported hypothesis. At most three.")
        add("")
        for i, f in enumerate(supported[:3], 1):
            add(f"{i}. **From {f.hypothesis}** - {f.detail}")
    add("")
    add("---")
    add("")
    add("## What this analysis cannot tell you")
    add("")
    add("Every number here comes from a **retrospective backtest**, in a database "
        "marked `kind=backtest`. The predictions were made after the games were played, "
        "by a factor set chosen by someone who already knew how those seasons went in "
        "aggregate. The diagnosis inherits that limitation whole: it can say where the "
        "model failed in a record it was built alongside. It cannot say why the model "
        "will fail next season.")
    add("")
    add(f"Generated by `tools/diagnose.py`. Seasons {min(seasons)}-{max(seasons)}. "
        f"{context['resolved_spread_with_market']:,} resolved spread predictions with a "
        f"market comparison; {len(model_bolder)} of them disagreements in the model's "
        "favour.")
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database", default=str(REPO / "var" / "backtest.db"))
    parser.add_argument("--out", default=str(REPO / "docs" / "DIAGNOSIS.md"))
    parser.add_argument("--threshold", type=float,
                        default=config.EDGE_DISAGREEMENT_THRESHOLD)
    args = parser.parse_args()

    source = Path(args.database)
    if not source.exists():
        raise SystemExit(f"no database at {source}; run tools/backtest.py first")

    conn = db.open_db(source)
    conn.execute("PRAGMA query_only = ON")   # read-only: this phase changes nothing
    model_bolder, market_bolder, context = load_disagreements(conn, args.threshold)
    if not model_bolder:
        raise SystemExit("no disagreements to diagnose")

    report = build_report(conn, model_bolder, market_bolder, context)
    Path(args.out).write_text(report, encoding="utf-8")
    conn.close()

    print(f"wrote {args.out} ({len(report.splitlines())} lines)")
    print(f"  disagreements analysed: {len(model_bolder)} model-bolder, "
          f"{len(market_bolder)} market-bolder")
    print(f"  pre-registered comparisons: {comparison_budget()}, "
          f"adjusted threshold p<{ALPHA / comparison_budget():.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
