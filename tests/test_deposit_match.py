"""Check an entry, step 4: a deposit match (GRIDIRON_ENTRY_CHECK; the brief of
2026-09-30, docs/briefs/2026-09-30-entry-check.md, with ruling D of
2026-10-05; built 2026-10-08).

The brief, step 4, whole: "Step 4, deposit match calculator: typed bonus,
playthrough multiple, entry type and payout used for playthrough; output the
bonus's expected value after playthrough at coin-flip legs, with the
playthrough cost shown, and 'read the offer's terms; this assumes the numbers
you typed'." The readings, recorded in docs/REPAIR_STATE.md: (a) it STORES
NOTHING; (b) UNITS, NEVER DOLLARS, every figure per unit of bonus; (c) THE
ARITHMETIC: P x bonus staked, each unit staked returning r (step 1's own
arithmetic of the entry), so the playthrough's expected cost is P x bonus x
(-r) and the bonus after it bonus + P x bonus x r, per unit of bonus; (d) THE
COLOUR, step 1's reading (h) applied to the bonus; (e) the plantings.

EVERY NUMBER BELOW IS WORKED BY HAND in its test (2026-10-08), never read back
off the code: a power entry returns M / 2^N - 1 per unit staked at coin flips,
a flex table the sum over k of C(N, k) / 2^N times what k right pays, less
one; a playthrough P per unit of bonus stakes P, costs -P r and leaves 1 + P r.
Each test fails on feb1b44, which has no deposit match (no
`entry_check.deposit_match`, no route, no section of the panel, no gate check),
and the browser tests fail there on the form they drive.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gridiron import api, audit, auth, db, entry_check, entry_math

ROOT = Path(__file__).resolve().parents[1]

#: THE BRIEF'S OWN SENTENCE, beside every answer.
ASSUMES = "Read the offer's terms; this assumes the numbers you typed."


def _form(entry_type="power", legs=2, payout=None, *, bonus="1", playthrough="5",
          confirmed=True):
    return {"entry_type": entry_type, "legs": str(legs),
            "payout": payout if payout is not None else {"multiplier": "3"},
            "payout_confirmed": confirmed, "bonus": bonus, "playthrough": playthrough}


def _match(form):
    """The shipped deposit match on a form, as the page sends it (through
    JSON). On feb1b44 there is none, and this raises."""
    return entry_check.deposit_match(json.loads(json.dumps(form)))


def _lines(out) -> dict:
    return {line["label"]: line["value_words"] for line in out["lines"]}


def _said(out) -> str:
    return json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------------------
# the task's worked examples, by hand
# ---------------------------------------------------------------------------

def test_a_1_unit_bonus_at_5x_on_2_leg_power_at_3x_costs_1_25_and_leaves_minus_0_25():
    """A 1-unit bonus at a 5x playthrough, staked in 2-leg power entries at
    3x: each unit staked returns 3 / 4 - 1 = -0.25 at coin flips; 5 units are
    staked per unit of bonus, costing 5 x 0.25 = 1.25; the bonus after it is
    1 - 1.25 = -0.25 -- below zero, so the red outline (reading (d)). The
    cost is shown (the brief), and every figure is per unit of bonus."""
    out = _match(_form())
    assert out["computed"] and out["signal"] == "costs"
    n = out["numbers"]
    assert n["per_unit_staked"] == pytest.approx(-0.25, abs=1e-12)
    assert n["staked"] == 5.0
    assert n["cost"] == pytest.approx(1.25, abs=1e-12)
    assert n["after"] == pytest.approx(-0.25, abs=1e-12)
    assert n["breakeven"] == pytest.approx(3 ** -0.5, abs=1e-6)
    assert _lines(out) == {
        "Break-even per leg of the entry": "57.74%",
        "Each unit staked returns, at coin flips": "-0.25 per unit staked",
        "Staked to release the bonus": "5 units per unit of bonus",
        "The playthrough's expected cost": "1.25 per unit of bonus",
        "The bonus after its playthrough, expected": "-0.25 per unit of bonus"}
    assert out["verdict_words"].startswith("Costs at coin flips")
    assert "-0.25 per unit of bonus" in out["verdict_words"]
    assert out["summary_words"] == ("A 1-unit bonus with a 5x playthrough, staked in "
                                    "2-pick power entries (3x). The stake, its cost and "
                                    "the bonus after it are per unit of bonus.")
    assert out["assumes_words"] == ASSUMES


def test_the_same_at_4_5x_gains_0_625_and_leaves_1_625_with_no_outline():
    """The same at 4.5x: 4.5 / 4 - 1 = +0.125 per unit staked; the 5 staked
    GAIN 0.625 (labelled a gain, never a negative cost), and the bonus after
    it is 1 + 0.625 = +1.625. No outline: the entry's break-even per leg is
    4.5^(-1/2) = 47.14%, an even chance 2.86 points over it -- under the 3
    the bar needs (reading (d): green only where every leg clears B.2)."""
    out = _match(_form(payout={"multiplier": "4.5"}))
    assert out["signal"] == "none"
    n = out["numbers"]
    assert n["per_unit_staked"] == pytest.approx(0.125, abs=1e-12)
    assert n["cost"] == pytest.approx(-0.625, abs=1e-12)
    assert n["after"] == pytest.approx(1.625, abs=1e-12)
    lines = _lines(out)
    assert "The playthrough's expected cost" not in lines
    assert lines["The playthrough's expected gain"] == "0.625 per unit of bonus"
    assert lines["The bonus after its playthrough, expected"] == "+1.625 per unit of bonus"
    assert lines["Break-even per leg of the entry"] == "47.14%"
    assert out["verdict_words"].startswith("No outline")
    assert "+1.625 per unit of bonus" in out["verdict_words"]
    assert "2.86 points over its break-even" in out["verdict_words"]


def test_a_flex_table_is_read_by_step_1s_own_arithmetic():
    """FLEX. A 5-leg table paying 10x for 5 right, 2x for 4, 0.4x for 3, with a
    3x playthrough typed "3x": at coin flips (1 x 10 + 5 x 2 + 10 x 0.4) / 32
    - 1 = 24/32 - 1 = -0.25 per unit staked; 3 staked cost 0.75; the bonus
    after is +0.25 -- above zero, but each leg needs 54.25%, so no outline.
    And a 6-leg table paying 25x / 2x / 0.4x at 5x: (25 + 6 x 2 + 15 x 0.4) /
    64 - 1 = 43/64 - 1 = -0.328125; 5 staked cost 1.640625; after -0.640625,
    red. ONE CALCULATOR: the return per unit staked is step 1's own return for
    that payout, to the last digit."""
    five = {"table": {"5": "10", "4": "2", "3": "0.4"}}
    out = _match(_form("flex", 5, five, playthrough="3x"))
    assert out["signal"] == "none"
    n = out["numbers"]
    assert n["per_unit_staked"] == pytest.approx(-0.25, abs=1e-12)
    assert n["staked"] == 3.0 and n["cost"] == pytest.approx(0.75, abs=1e-12)
    assert n["after"] == pytest.approx(0.25, abs=1e-12)
    assert _lines(out)["Break-even per leg of the entry"] == "54.25%"
    assert out["summary_words"].startswith("A 1-unit bonus with a 3x playthrough, staked in "
                                           "5-pick flex entries (5 of 5 right pays 10x, ")
    six = _match(_form("flex", 6, {"table": {"6": "25", "5": "2", "4": "0.4"}}))
    assert six["signal"] == "costs"
    m = six["numbers"]
    assert m["per_unit_staked"] == pytest.approx(-21 / 64, abs=1e-12)
    assert m["cost"] == pytest.approx(1.640625, abs=1e-9)
    assert m["after"] == pytest.approx(-0.640625, abs=1e-9)
    assert entry_math.deposit_match({"table": {5: 10.0, 4: 2.0, 3: 0.4}}, 5,
                                    playthrough=3.0)["per_unit_staked"] \
        == entry_math.expected_return({"table": {5: 10.0, 4: 2.0, 3: 0.4}}, 5)


def test_a_playthrough_of_1x_costs_a_quarter_and_leaves_three_quarters():
    """A 1x playthrough at 3x on two legs: 1 staked at -0.25 costs 0.25 and
    leaves +0.75 -- above zero, the entry 7.74 points under its break-even:
    no outline. "1 unit", never "1 units"."""
    out = _match(_form(playthrough="1"))
    assert out["signal"] == "none"
    lines = _lines(out)
    assert lines["Staked to release the bonus"] == "1 unit per unit of bonus"
    assert lines["The playthrough's expected cost"] == "0.25 per unit of bonus"
    assert lines["The bonus after its playthrough, expected"] == "+0.75 per unit of bonus"
    assert "7.74 points under its break-even" in out["verdict_words"]


# ---------------------------------------------------------------------------
# the colour, reading (d)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("multiple,playthrough,signal,after", [
    # 5 / 4 - 1 = +0.25 a unit staked, 44.72% a leg (5.28 points over): green
    ("5", "5", "clears", 2.25),
    # 4.52 / 4 - 1 = +0.13, 47.04% a leg (2.96 points, under the bar): none
    ("4.52", "5", "none", 1.65),
    # 3x: -0.25 a unit staked; at 4x the playthrough costs the bonus exactly
    ("3", "4", "none", 0.0),
    # 4x: an entry returning exactly its cost -- nothing gained or lost
    ("4", "5", "none", 1.0),
    # 3-leg power at 5x: 5/8 - 1 = -0.375; 10 staked cost 3.75: -2.75, red
    ("5", "10", "costs", -2.75),
])
def test_the_outline_is_reading_d(multiple, playthrough, signal, after):
    """Green only where the bonus after its playthrough is above zero AND every
    leg's break-even is three points or more under an even chance; red where
    the bonus after it is below zero; between, the numbers alone."""
    legs = 3 if playthrough == "10" else 2
    out = _match(_form(legs=legs, payout={"multiplier": multiple}, playthrough=playthrough))
    assert out["signal"] == signal
    assert out["numbers"]["after"] == pytest.approx(after, abs=1e-12)
    if signal == "clears":
        assert out["verdict_words"].startswith("Clears the bar at coin flips")
    if after == 0.0:
        assert "cost the bonus exactly" in out["verdict_words"]
        assert _lines(out)["The playthrough's expected cost"] == "1.00 per unit of bonus"
    if multiple == "4":
        assert _lines(out)["The playthrough's expected cost"] == "0.00 per unit of bonus"
        assert out["numbers"]["cost"] == 0.0 and str(out["numbers"]["cost"]) == "0.0"


def test_a_figure_that_is_not_nothing_is_drawn_with_the_sign_it_has(monkeypatch):
    """THE PROVER (2026-10-08). By hand: 2.999999 / 4 - 1 = -0.25000025 a unit
    staked; a 4x playthrough stakes 4, costing 1.000001; the bonus after it is
    1 - 1.000001 = -0.000001 -- below zero, so red. As handed, five places and
    step 1's signed rule drew it "+0.00 per unit of bonus", in its line and in
    "Costs at coin flips: ... comes to +0.00". And 3.99999 / 4 - 1 =
    -0.0000025 a unit staked was drawn "+0.00 per unit staked". Each is drawn
    now to its first significant place with the sign it has; a figure that is
    nothing (3x at 4x, 4x at 5x) is still "+0.00"; and the gate names the rule
    as handed."""
    from gridiron import language

    out = _match(_form(payout={"multiplier": "2.999999"}, playthrough="4"))
    assert out["signal"] == "costs"
    assert out["numbers"]["after"] == pytest.approx(-0.000001, abs=1e-12)
    lines = _lines(out)
    assert lines["The bonus after its playthrough, expected"] == "-0.000001 per unit of bonus"
    assert lines["The playthrough's expected cost"] == "1.00 per unit of bonus"
    assert out["verdict_words"].endswith("comes to -0.000001 per unit of bonus.")
    assert "+0.00" not in _said(out)
    hair = _lines(_match(_form(payout={"multiplier": "3.99999"})))
    staked = hair["Each unit staked returns, at coin flips"]
    assert staked.startswith("-0.00000") and staked.endswith(" per unit staked"), staked
    assert hair["The playthrough's expected cost"] == "0.00001 per unit of bonus"
    assert _lines(_match(_form(playthrough="4")))[
        "The bonus after its playthrough, expected"] == "+0.00 per unit of bonus"
    assert _lines(_match(_form(payout={"multiplier": "4"})))[
        "Each unit staked returns, at coin flips"] == "+0.00 per unit staked"
    assert audit.deposit_match_faults() == []
    monkeypatch.setattr(language, "deposit_match_after_words",
                        lambda after: f"{language._entry_number(after)} per unit of bonus")
    assert any("2.999999x" in f and "drawn with a sign it does not have" in f
               for f in audit.deposit_match_faults())


# ---------------------------------------------------------------------------
# units, never dollars; the brief's sentence; the terms left open
# ---------------------------------------------------------------------------

def test_every_figure_is_per_unit_of_bonus_and_never_in_dollars():
    """READING (b). A 50-unit bonus draws the same figures as a 1-unit one --
    every figure is per unit of bonus -- and says so; nothing the deposit
    match says carries a currency's sign or name, nor the banned words."""
    one, fifty = _match(_form()), _match(_form(bonus="50"))
    assert one["lines"] == fifty["lines"] and one["numbers"] == fifty["numbers"]
    assert fifty["summary_words"].startswith("A 50-unit bonus")
    for out in (one, fifty, _match(_form(payout={"multiplier": "5"})),
                entry_check.deposit_panel()):
        said = _said(out)
        assert not re.search(r"[$€£¥¢]|\bdollars?\b|\busd\b|\bcents?\b", said, re.I), said[:300]
        assert not re.search(r"\bboost|\bsame[- ]game\b|\bparlay|\bslip\b|\bbuilder\b"
                             r"|\badd leg\b|\bbankroll\b|\bvalue\b|\bplay\b|\bbet\b",
                             said, re.I), said[:300]
        assert audit.entry_check_words_faults(out, "deposit match") == []
    for line in one["lines"][2:]:
        assert line["value_words"].endswith("per unit of bonus"), line


def test_the_briefs_sentence_and_the_terms_it_leaves_open_are_said():
    """The brief's own sentence beside every answer; and the terms it leaves
    open said as the operator must type them, never assumed (reading (c)): a
    playthrough counted on the deposit and the bonus together, and a bonus
    that can only be staked."""
    assert _match(_form())["assumes_words"] == ASSUMES
    panel = entry_check.deposit_panel()
    terms = " ".join(panel["terms"])
    assert "multiple of the bonus alone" in terms
    assert "deposit and the bonus together" in terms and "divided by the bonus" in terms
    assert "can only be staked" in terms
    assert panel["heading"] == "A deposit match"
    assert [o["key"] for o in panel["legs"]] == ["2", "3", "4", "5", "6", "7", "8"]


def test_nothing_is_worked_out_from_a_payout_not_confirmed():
    """Step 1's reading (e), held here: a payout not confirmed -- the last one
    typed in step 1, offered filled in, or one he typed -- works out nothing."""
    out = _match(_form(confirmed=False))
    assert not out["computed"] and out["numbers"] is None and out["signal"] == "none"
    assert out["ask_words"].startswith("Confirm what the app pays for this entry")
    assert out["lines"] == []


@pytest.mark.parametrize("change,words", [
    (lambda f: "not a form", "not a deposit match"),
    (lambda f: dict(f, entry_type="parlay"), "Choose power or flex."),
    (lambda f: dict(f, legs="9"), "2 to 8"),
    (lambda f: dict(f, legs="2.5"), "2 to 8"),
    (lambda f: dict(f, legs=""), "2 to 8"),
    (lambda f: dict(f, payout={"multiplier": ""}), "Type what the app pays for this entry."),
    (lambda f: dict(f, payout={"multiplier": "1"}), "returns no more than the entry costs"),
    (lambda f: dict(f, entry_type="flex", payout={"table": {"2": "1.5", "1": "2"}}),
     "pays less for more legs right"),
    (lambda f: dict(f, bonus=""), "Type the bonus"),
    (lambda f: dict(f, bonus="0"), "Type the bonus"),
    (lambda f: dict(f, bonus="fifty"), "Type the bonus"),
    (lambda f: dict(f, bonus="nan"), "Type the bonus"),
    (lambda f: dict(f, playthrough=""), "Type the playthrough"),
    (lambda f: dict(f, playthrough="0"), "Type the playthrough"),
    (lambda f: dict(f, playthrough="five"), "Type the playthrough"),
    (lambda f: dict(f, playthrough="5000"), "Type the playthrough"),
])
def test_a_form_it_cannot_read_is_refused_in_words(change, words):
    out = entry_check.deposit_match(json.loads(json.dumps(change(_form()))))
    assert out["refused_words"] and words in out["refused_words"], out["refused_words"]
    assert not out["computed"] and out["numbers"] is None and out["signal"] == "none"
    assert audit.entry_check_words_faults(out, "refused") == []


def test_the_arithmetic_is_step_1s_own():
    """ONE CALCULATOR: over the gate's spread of payouts, the return per unit
    staked is `entry_math.expected_return` of the payout (step 1's), the stake
    is the playthrough, the cost minus their product and the bonus after it
    one less the cost; and the break-even the deposit match draws is the one
    step 1's check draws for that payout."""
    for m, n in audit.ENTRY_CHECK_POWER_SPREAD:
        for p in (1.0, 5.0, 10.5):
            got = entry_math.deposit_match({"multiplier": m}, n, playthrough=p)
            r = m * 0.5 ** n - 1.0
            assert got["per_unit_staked"] == entry_math.expected_return({"multiplier": m}, n)
            assert got["staked"] == p
            assert got["cost"] == pytest.approx(-p * r, abs=1e-12)
            assert got["after"] == pytest.approx(1.0 + p * r, abs=1e-12)
    out = _match(_form("flex", 3, {"table": {"3": "2.25", "2": "1.25"}}, playthrough="7.5"))
    assert out["numbers"]["breakeven"] == pytest.approx(
        entry_math.breakeven({"table": {3: 2.25, 2: 1.25}}, 3), abs=1e-6)
    assert out["numbers"]["after"] == pytest.approx(-0.875, abs=1e-12)


# ---------------------------------------------------------------------------
# it stores nothing (reading (a))
# ---------------------------------------------------------------------------

def test_the_reach_scan_reads_what_the_deposit_match_reaches_and_names_a_write(tmp_path):
    """Every function `entry_check.deposit_match` reaches -- the form's reader,
    the arithmetic, the words, the bar -- is read, the shipped code passes, and
    a write planted in one, a handle, or the page keeping the offer in the
    browser's storage is named."""
    assert audit.entry_check_reach_faults() == []
    sources = {n: (ROOT / "gridiron" / n).read_text(encoding="utf-8")
               for n in audit._DEPOSIT_MATCH_MODULES}
    reached, problems = audit._deposit_match_reached(sources)
    names = {(m, node.name) for m, node in reached}
    assert problems == []
    for want in (("entry_check.py", "read_deposit_form"), ("entry_check.py", "_payout"),
                 ("entry_math.py", "deposit_match"), ("entry_math.py", "expected_return"),
                 ("language.py", "deposit_match_verdict_words"),
                 ("picks.py", "clears_the_pick_bar")):
        assert want in names, want
    assert ("entry_check.py", "remember") not in names
    root = tmp_path / "gridiron"
    (root / "web").mkdir(parents=True)
    for name in audit._DEPOSIT_MATCH_MODULES + ("api.py", "m4.py", "web/app.js"):
        (root / name).write_text((ROOT / "gridiron" / name).read_text(encoding="utf-8"),
                                 encoding="utf-8")
    shipped = (root / "entry_check.py").read_text(encoding="utf-8")
    anchor = '    payout, legs = form["payout"], form["legs"]\n    breakeven = '
    assert anchor in shipped
    for put_in, want in (
            ("    db.open_db().execute('INSERT INTO pickem_payouts_typed (app) VALUES (1)')\n",
             "reached by the deposit match"),
            ("    remember(None, form)\n", "names `remember`"),
            ("    open('offer.txt', 'w').write(str(form['bonus']))\n", "names `open`")):
        (root / "entry_check.py").write_text(shipped.replace(anchor, put_in + anchor, 1),
                                             encoding="utf-8")
        assert any(want in f for f in audit.entry_check_reach_faults(root=root)), want
    (root / "entry_check.py").write_text(shipped, encoding="utf-8")
    js = (root / "web" / "app.js").read_text(encoding="utf-8")
    for put_back, want in (
            (js.replace("      deposit.changed = false;\n      paintDepositResult();",
                        "      deposit.changed = false;\n      sessionStorage.setItem('b', "
                        "deposit.bonus);\n      paintDepositResult();"), "browser's storage"),
            (js.replace("      deposit.changed = false;\n      paintDepositResult();",
                        "      deposit.changed = false;\n      prefSet('bonus', deposit.bonus);"
                        "\n      paintDepositResult();"), "browser's storage"),
            (js.replace("const res = await fetch('/api/deposit-match', {",
                        "const res = await fetch('/api/entry-check', {"), "fetches")):
        assert put_back != js
        assert any(want in f for f in audit.entry_check_reach_faults(app_js=put_back)), want
    api_source = (root / "api.py").read_text(encoding="utf-8")
    planted = api_source.replace("    return entry_check.deposit_match(body)",
                                 "    return entry_check.deposit_match(body, get_conn())")
    assert planted != api_source
    assert any("opens a handle on the record" in f
               for f in audit.entry_check_reach_faults(api_source=planted))


def test_the_reach_scan_names_a_write_by_another_name_or_another_road(tmp_path):
    """THE PROVER (2026-10-08). As handed, the reach scan read the forbidden
    names as written, followed no call out of its four modules, and read the
    page's nine deposit functions and nothing they name -- so each of these,
    planted on a copy, wrote past it: the record's door imported under other
    names and called bare; step 1's write bound to another name; a settings
    row written from the deposit match's own words through an import the
    words made; the offer handed to a module the scan does not read, by
    `config.x(...)` or a function imported by name; and on the page a helper
    of its own keeping the offer in `localStorage`, a cookie, an arrow
    helper's `sessionStorage`, a helper handed on as a value, and another
    function keeping the typed bonus. Each is named now; the shipped tree is
    not."""
    root = tmp_path / "gridiron"
    (root / "web").mkdir(parents=True)
    for name in audit._DEPOSIT_MATCH_MODULES + ("api.py", "m4.py", "web/app.js"):
        (root / name).write_text((ROOT / "gridiron" / name).read_text(encoding="utf-8"),
                                 encoding="utf-8")
    assert audit.entry_check_reach_faults(root=root) == []
    work = '    payout, legs = form["payout"], form["legs"]\n    breakeven = '
    imports = "from . import config, db, entry_math, language, m4, picks\n"
    heading = '    return {\n        "heading": "A deposit match",'
    subjects = "from . import subjects as _subjects\n"
    answered = "      deposit.changed = false;\n      paintDepositResult();"
    another = "a door to the record, a setting, a file or another machine by another name"
    forms = [
        ("entry_check.py", [(imports, imports + "from .db import open_db as h, set_meta as k\n"),
                            (work, '    k(h(), "b", str(form["bonus"]))\n' + work)], another),
        ("entry_check.py", [(imports, imports + "from .db import open_db as h\n"),
                            ("\n\ndef deposit_panel()", "\n\nnote_it = remember\n\n\ndef deposit_panel()"),
                            (work, "    note_it(h(), form)\n" + work)], another),
        ("language.py", [(subjects, subjects + "from .settings import set_value as sv\n"
                                               "from .db import open_db as od\n"),
                         (heading, '    sv(od(), "b", "1")\n' + heading)], another),
        ("entry_check.py", [(work, '    config.note_the_offer(form["bonus"])\n' + work)],
         "calls into `gridiron.config`"),
        ("language.py", [(subjects, subjects + "from .tasks import note as _note\n"),
                         (heading, '    _note("deposit")\n' + heading)],
         "calls into `gridiron.tasks`"),
        ("web/app.js", [("  async function checkDeposit(ec) {",
                         "  function keepOffer(b) { localStorage.setItem('o', JSON.stringify(b)); }\n\n"
                         "  async function checkDeposit(ec) {"),
                        (answered, "      deposit.changed = false;\n      keepOffer(depositBody());\n"
                                   "      paintDepositResult();")],
         "`keepOffer`, which `checkDeposit` names, keeps something in the browser's storage"),
        ("web/app.js", [("  function depositBody() {",
                         "  function noteIt(k, v) { document.cookie = k + '=' + v; }\n\n"
                         "  function depositBody() {"),
                        ("    return { entry_type: deposit.type, legs: deposit.legs,",
                         "    noteIt('b', deposit.bonus);\n"
                         "    return { entry_type: deposit.type, legs: deposit.legs,")],
         "`noteIt`, which `depositBody` names, keeps something"),
        ("web/app.js", [("  function prefGet(key, fallback) {",
                         "  const keepIt = (b) => { sessionStorage.setItem('o', b); };\n\n"
                         "  function prefGet(key, fallback) {"),
                        (answered, "      deposit.changed = false;\n      keepIt(`${deposit.bonus}`);\n"
                                   "      paintDepositResult();")],
         "`keepIt`, which `checkDeposit` names, keeps something"),
        ("web/app.js", [("  async function checkDeposit(ec) {",
                         "  function keepAnswer(a) { localStorage.setItem('a', a); return a; }\n\n"
                         "  async function checkDeposit(ec) {"),
                        ("      const answer = await res.json();\n      if (stale(seq)) return;\n"
                         "      deposit.result",
                         "      const answer = await res.json().then(keepAnswer);\n"
                         "      if (stale(seq)) return;\n      deposit.result")],
         "`keepAnswer`, which `checkDeposit` names, keeps something"),
        ("web/app.js", [("    let sortBy = prefGet('props.sort', 'edge');",
                         "    let sortBy = prefGet('props.sort', 'edge');\n"
                         "    prefSet('offer', deposit.bonus);")],
         "`renderProps` names the typed offer (`deposit`) outside"),
    ]
    for name, swaps, want in forms:
        shipped = (ROOT / "gridiron" / name).read_text(encoding="utf-8")
        changed = shipped
        for old, new in swaps:
            assert old in changed, (name, old)
            changed = changed.replace(old, new, 1)
        (root / name).write_text(changed, encoding="utf-8")
        try:
            faults = audit.entry_check_reach_faults(root=root)
        finally:
            (root / name).write_text(shipped, encoding="utf-8")
        assert any(want in f for f in faults), (want, faults[:3])


def test_the_no_ledger_scan_names_a_place_for_a_deposit_bonus_or_playthrough(tmp_path):
    """LAW 5's NO LEDGER, read for the deposit match (reading (a)): the shipped
    schema, settings and a fresh record pass; a table, a column, a setting
    the page could keep one in, or a settings row written for one, is
    named."""
    assert audit.wagering_ledger_faults() == []
    for ddl, want in (("CREATE TABLE deposit_offers (id INTEGER PRIMARY KEY, units REAL)",
                       "a table called deposit_offers"),
                      ("CREATE TABLE offers (id INTEGER PRIMARY KEY, playthrough REAL)",
                       "a column called offers.playthrough"),
                      ("CREATE TABLE entries_seen (id INTEGER PRIMARY KEY, bonus_units REAL)",
                       "a column called entries_seen.bonus_units")):
        conn = db.connect(":memory:")
        conn.execute(ddl)
        with pytest.raises(audit.LawViolation) as exc:
            audit.check_no_wagering_ledger(conn=conn)
        assert want in str(exc.value) and "LAW 5" in str(exc.value)
        conn.close()
    conn = db.connect(":memory:")
    conn.execute("CREATE TABLE settings (id INTEGER PRIMARY KEY, changed_utc TEXT,"
                 " name TEXT, value TEXT)")
    conn.execute("INSERT INTO settings (changed_utc, name, value) VALUES"
                 " ('2026-10-08T00:00:00Z', 'deposit_match_bonus', '50')")
    assert any("a setting written as 'deposit_match_bonus'" in f
               for f in audit.wagering_ledger_faults(conn=conn))
    conn.close()
    root = tmp_path / "gridiron"
    root.mkdir()
    settings = (ROOT / "gridiron" / "settings.py").read_text(encoding="utf-8")
    (root / "settings.py").write_text(
        settings + "\nEDITABLE['last_bonus'] = {'label': 'Bonus'}\n", encoding="utf-8")
    assert any("a setting called 'last_bonus'" in f
               for f in audit.wagering_ledger_faults(root=root))


def test_the_route_writes_nothing_opens_no_handle_and_has_its_two_locks(conn, db_path, monkeypatch):
    """The route answers the offer; without the form token it refuses; it
    opens no handle on the record -- every handle-maker the app has but the
    sign-in's is made to raise, and it still answers -- and no table of the
    record moves; a GET is refused; a body that is not JSON is refused in
    words."""
    from fastapi.testclient import TestClient

    def counts():
        return {r[0]: conn.execute(f'SELECT COUNT(*) FROM "{r[0]}"').fetchone()[0]
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"
                                      " AND name NOT LIKE 'sqlite_%'")}

    token = "test-token-for-the-deposit-match"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(db_path)
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            before = counts()
            refused = client.post("/api/deposit-match", json=_form())
            assert refused.status_code == 403
            csrf = auth.csrf_token(client.cookies.get(auth.COOKIE_NAME))
            headers = {auth.CSRF_HEADER: csrf}

            def no_handle(*a, **k):
                raise AssertionError("the deposit match's route opened a handle on the record")

            for name in ("get_conn", "get_entry_conn", "get_settings_conn", "get_taken_conn"):
                monkeypatch.setattr(api, name, no_handle)
            got = client.post("/api/deposit-match", json=_form(bonus="73.25"), headers=headers)
            assert got.status_code == 200, got.text
            answer = got.json()
            assert answer["computed"] and answer["signal"] == "costs"
            assert answer["numbers"]["after"] == pytest.approx(-0.25, abs=1e-12)
            garbled = client.post("/api/deposit-match", content=b"not json",
                                  headers=dict(headers, **{"Content-Type": "application/json"}))
            assert garbled.status_code == 200
            assert "not a deposit match" in garbled.json()["refused_words"]
            assert client.get("/api/deposit-match").status_code == 405
            after = counts()
    finally:
        api.set_database(None)
    moved = {t for t in set(before) | set(after) if before.get(t) != after.get(t)}
    # The sign-in's own session rows are the auth handle's (the session seen
    # again on each request); nothing else moves.
    assert moved <= {"sessions", "session_seen", "auth_failures"}, moved
    assert "73.25" not in json.dumps(
        [list(map(tuple, conn.execute(f'SELECT * FROM "{t}"'))) for t in after], default=str)


def test_the_panel_offers_the_deposit_match_beside_the_check_on_nfl_only(conn):
    """A section of the check's panel (one panel, one calculator): on the NFL
    page beside "Check an entry", and on another sport's page not at all."""
    panel = entry_check.panel(conn, sport="nfl", tiles=[], now="2099-10-01T00:00:00Z")
    assert panel["deposit"] == entry_check.deposit_panel()
    assert panel["deposit"]["labels"]["check"] == "Work out this deposit match"
    closed = entry_check.panel(conn, sport="mlb", tiles=[], now="2099-10-01T00:00:00Z")
    assert "deposit" not in closed


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def test_the_gate_makes_the_call_and_the_shipped_deposit_match_passes():
    from tests.test_entry_check import _step_2_calls

    assert _step_2_calls("check_the_deposit_match_is_its_own_arithmetic")
    assert _step_2_calls("check_the_entry_check_reaches_no_app")
    assert _step_2_calls("check_no_wagering_ledger")
    audit.check_the_deposit_match_is_its_own_arithmetic()
    assert audit.deposit_match_faults() == []


@pytest.mark.parametrize("what,module,name,make,want", [
    ("the bonus at its face, the cost left out", "math", "deposit_match",
     lambda real: lambda payout, legs, **kw: dict(real(payout, legs, **kw), after=1.0),
     "worked by hand"),
    ("the bonus counted twice", "math", "deposit_match",
     lambda real: lambda payout, legs, **kw: dict(
         real(payout, legs, **kw), after=real(payout, legs, **kw)["after"] + 1.0),
     "worked by hand"),
    ("the bonus added again to the stake", "math", "deposit_match",
     lambda real: lambda payout, legs, *, playthrough, **kw: real(
         payout, legs, playthrough=playthrough + 1.0, **kw), "worked by hand"),
    ("the bonus after its playthrough in dollars", "language", "deposit_match_after_words",
     lambda real: lambda after: "$" + real(after), "a figure in dollars"),
    ("the cost line left off", "check", "_deposit_lines",
     lambda real: lambda words, *a: [l for l in real(words, *a)
                                     if l["label"] != words["line_cost"]
                                     and l["label"] != words["line_gain"]],
     "no line states the playthrough's expected cost"),
])
def test_the_gate_names_each_planted_defect(monkeypatch, what, module, name, make, want):
    """The gate's check works every figure out again from the numbers typed
    and reads each off the words drawn (tools/guards/plant.py holds the
    plantings, each escaping on feb1b44); a few of them here, quickly."""
    from gridiron import language

    target = {"math": entry_math, "check": entry_check, "language": language}[module]
    monkeypatch.setattr(target, name, make(getattr(target, name)))
    faults = audit.deposit_match_faults()
    assert any(want in f for f in faults), (what, faults[:3])


def test_the_gate_names_an_outline_reading_d_does_not_give(monkeypatch):
    """A bonus above zero outlined green whatever the entry's legs (4.5x on two
    legs, +1.625 after a 5x playthrough, 2.86 points under the bar), and the
    page putting the outline on by name, are each named."""
    class _Bar:
        clears_the_pick_bar = staticmethod(lambda e: True)

    monkeypatch.setattr(entry_check, "picks", _Bar())
    assert any("the outline is" in f for f in audit.deposit_match_faults())
    monkeypatch.undo()
    js = (ROOT / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    anchor = "el('div', 'verdict ' + signalClass(d.signal))"
    assert anchor in js
    put_back = js.replace(anchor, "el('div', 'verdict sig-clears')")
    faults = audit.deposit_match_faults(js=put_back)
    assert any("outline" in f and "paintDepositResult" in f for f in faults), faults[:3]


# ---------------------------------------------------------------------------
# the page, in a real Chromium
# ---------------------------------------------------------------------------
#
# ON A COPY OF THE BROWSER WORLD, served on its own port, with a payout kept
# for PrizePicks 2-pick power as step 1 keeps one (the deposit match itself
# keeps nothing). No clock is read and nothing waits a fixed time: every wait
# is for what the page draws.

@pytest.fixture(scope="module")
def _deposit_world(_shared_world, tmp_path_factory):
    from tests import conftest

    target = tmp_path_factory.mktemp("deposit-match") / "world.db"
    source = db.read_only(_shared_world["db"],
                          "copying the browser world for the deposit match's page")
    copy = db.connect(target)
    source.backup(copy)
    source.close()
    copy.close()
    conn = db.open_db(target)
    # STEP 1'S OWN WRITE, as a confirmed check makes it: PrizePicks 2-pick
    # power at 3.5x, offered back to the deposit match for that app and size.
    entry_check.remember(conn, {"app": "prizepicks", "entry_type": "power",
                                "legs": [{}, {}], "payout": {"multiplier": 3.5},
                                "confirmed": True})
    base, server, thread = conftest._serve(target)
    yield {"base": base, "db": target, "conn": conn}
    server.should_exit = True
    thread.join(timeout=10)
    conn.close()
    api.set_database(_shared_world["db"])


def _work_it_out(page, wants):
    page.click("#deposit-check")
    page.wait_for_function(
        "(w) => document.getElementById('deposit-lines').textContent.includes(w)",
        arg=wants, timeout=10000)
    return page.evaluate("""() => {
        const v = document.querySelector('#deposit-lines .verdict');
        return { cls: v ? v.className : null, verdict: v ? v.textContent : null,
                 lines: [...document.querySelectorAll('#deposit-lines .entry-line')]
                          .map(r => [r.querySelector('.entry-label').textContent,
                                     r.querySelector('.entry-value').textContent]),
                 said: [...document.querySelectorAll('#deposit-lines .entry-said')]
                          .map(p => p.textContent) }; }""")


def _storage(page) -> str:
    return page.evaluate("JSON.stringify(Object.assign({}, localStorage))"
                         " + JSON.stringify(Object.assign({}, sessionStorage)) + document.cookie")


@pytest.mark.parametrize("width", ["1300", "390"])
def test_the_page_works_out_an_offer_and_draws_the_servers_answer(_deposit_world, _browser, width):
    """THE PAGE, END TO END: the operator types the entry the playthrough is
    staked in, its payout, ticks the box, the bonus and the playthrough; the
    page asks `/api/deposit-match` and draws its answer -- the server's words,
    figures and outline, nothing composed in the page -- at 3x (red), 4.5x
    (none) and 5x (green); a change puts the answer aside; and nothing he typed
    is in the browser's storage."""
    from tests.test_entry_check import _sign_in

    context, page = _sign_in(_deposit_world, _browser, phone=width == "390")
    try:
        page.wait_for_selector("#deposit-form .entry-head-row select", timeout=15000)
        assert page.is_visible("#deposit-match")
        assert page.text_content("#deposit-heading") == "A deposit match"
        page.fill("#deposit-form .entry-block >> nth=1 >> input >> nth=0", "73.25")
        page.fill("#deposit-form .entry-block >> nth=1 >> input >> nth=1", "5")
        for multiple, signal, opening in (("3", "costs", "Costs at coin flips"),
                                          ("4.5", "none", "No outline"),
                                          ("5", "clears", "Clears the bar at coin flips")):
            page.fill("#deposit-form .entry-pays-rows input", multiple)
            assert not page.is_checked("#deposit-form .entry-confirm input")
            page.check("#deposit-form .entry-confirm input")
            server = entry_check.deposit_match(_form(payout={"multiplier": multiple},
                                                     bonus="73.25"))
            drawn = _work_it_out(page, server["verdict_words"])
            assert server["signal"] == signal
            assert drawn["verdict"] == server["verdict_words"]
            assert drawn["verdict"].startswith(opening)
            has = {"clears": "sig-clears", "costs": "sig-costs"}.get(signal)
            assert (has in drawn["cls"]) if has else ("sig-" not in drawn["cls"]), drawn["cls"]
            assert drawn["lines"] == [[l["label"], l["value_words"]] for l in server["lines"]]
            assert drawn["said"] == [server["summary_words"], ASSUMES]
        page.fill("#deposit-form .entry-block >> nth=1 >> input >> nth=1", "6")
        page.wait_for_function(
            "() => document.getElementById('deposit-lines').textContent.startsWith('Changed since')",
            timeout=10000)
        assert not page.query_selector("#deposit-lines .verdict")
        assert "73.25" not in _storage(page)
        assert not page.page_errors, page.page_errors
    finally:
        context.close()


def test_a_payout_typed_in_step_1_is_offered_for_its_app_type_and_size_unconfirmed(_deposit_world, _browser):
    """READING (a): "a remembered entry payout is step 1's table, offered
    pre-filled and unconfirmed as step 1 does, only if the operator chooses
    the same app, type and size". Nothing is filled before an app is chosen;
    PrizePicks 2-pick power fills 3.5 with the box unticked and the words
    saying when it was typed; worked out unticked, the page asks him to
    confirm; ticked, 3.5 / 4 - 1 = -0.125 a unit staked, 5 staked cost 0.625,
    the bonus after it +0.375; three legs offer nothing."""
    from tests.test_entry_check import _sign_in

    context, page = _sign_in(_deposit_world, _browser, phone=False)
    try:
        heads = "#deposit-form .entry-head-row select"
        payout, box = "#deposit-form .entry-pays-rows input", "#deposit-form .entry-confirm input"
        page.wait_for_selector(heads, timeout=15000)
        assert page.input_value(payout) == "", "a payout filled in before an app was chosen"
        page.select_option(f"{heads} >> nth=0", "prizepicks")
        page.wait_for_function(f"() => document.querySelector('{payout}').value === '3.5'",
                               timeout=10000)
        assert not page.is_checked(box)
        offered = page.text_content("#deposit-offered")
        assert offered.startswith("Last typed for PrizePicks 2-pick power, ") and "3.5x" in offered
        page.fill("#deposit-form .entry-block >> nth=1 >> input >> nth=0", "1")
        page.fill("#deposit-form .entry-block >> nth=1 >> input >> nth=1", "5")
        _work_it_out(page, "Confirm what the app pays for this entry")
        assert not page.query_selector("#deposit-lines .verdict")
        page.check(box)
        drawn = _work_it_out(page, "+0.375 per unit of bonus")
        assert ["The playthrough's expected cost", "0.625 per unit of bonus"] in drawn["lines"]
        page.select_option(f"{heads} >> nth=2", "3")
        page.wait_for_function(f"() => document.querySelector('{payout}').value === ''",
                               timeout=10000)
        assert page.is_hidden("#deposit-offered") and not page.is_checked(box)
        assert not page.page_errors, page.page_errors
    finally:
        context.close()


def test_every_tap_target_of_the_deposit_match_is_44px_at_390(_deposit_world, _browser):
    """At 390, three device pixels to one, at rest, with a 5-leg flex table's
    five rows on screen and its answer drawn: every tap target on the page,
    the deposit match's among them, 44px or more tall in whole pixels and 44px
    or more wide (nothing rounded or widened), and nothing wider than the
    phone."""
    from tests.test_entry_check import _sign_in
    from tests.test_smoke import _AT_REST, _MEASURE_THE_TARGETS, SLATE_TAP_TARGETS

    context, page = _sign_in(_deposit_world, _browser, phone=True)
    try:
        heads = "#deposit-form .entry-head-row select"
        page.wait_for_selector(heads, timeout=15000)
        page.select_option(f"{heads} >> nth=1", "flex")
        page.wait_for_function(
            "() => document.querySelectorAll('#deposit-form .entry-pays-rows input').length === 2",
            timeout=10000)
        page.select_option(f"{heads} >> nth=2", "5")
        page.wait_for_function(
            "() => document.querySelectorAll('#deposit-form .entry-pays-rows input').length === 5",
            timeout=10000)
        for i, value in enumerate(("10", "2", "0.4", "", "")):
            page.fill(f"#deposit-form .entry-pays-rows input >> nth={i}", value)
        page.check("#deposit-form .entry-confirm input")
        page.fill("#deposit-form .entry-block >> nth=1 >> input >> nth=0", "1")
        page.fill("#deposit-form .entry-block >> nth=1 >> input >> nth=1", "3")
        _work_it_out(page, "+0.25 per unit of bonus")
        page.wait_for_function(_AT_REST, timeout=15000)
        got = page.evaluate(_MEASURE_THE_TARGETS, SLATE_TAP_TARGETS)
        assert got["measured"] > 20 and not got["small"], got["small"][:20]
        deposit = page.evaluate(
            "[...document.querySelectorAll('#deposit-match input, #deposit-match select,"
            " #deposit-match button, #deposit-match label')].filter(e => e.offsetParent)"
            ".map(e => e.getBoundingClientRect().height)")
        assert len(deposit) >= 12
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        assert not page.page_errors, page.page_errors
    finally:
        context.close()
