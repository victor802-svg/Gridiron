# Close-out — the measured margin, three guards, and the final passes installed

Brief: `docs/briefs/2026-09-03-measured-margin.md`; STEP 0 of
`docs/briefs/2026-09-03-daytime.md`.

---

## 1. Close-out table

| item | verdict | evidence |
|---|---|---|
| **R1** adopt the measured slope and intercept, dated | **DONE** | `cfb_expected_margin` now reads `EXPECTED_MARGIN_FIT`; 4.848 + 0.9351 × rating_diff. |
| **R1** the old pair kept as "assumed, did not reproduce" | **DONE** | `CFB_HOME_MARGIN_ASSUMED` = 9.79, `..._SLOPE` = 1.0, with the comparison in the comment. |
| **R1** retrain CFB | **DONE** | n=1,664, converged, **nothing constant, nothing dropped**. |
| **R1** Saturday's rows stand | **DONE** | Nothing rewritten, re-dated or deleted. |
| **R1** base rate before/after | **DONE** | **0.3943 → 0.5024**. The ruling expected "near 0.50". |
| **R2** every training loader asserts one sport | **DONE** | `baseline.assert_one_sport`, called by all three spread loaders. |
| **R2** a loader returning two sports fails by name | **DONE** | `TrainingSetSpansSports`, planted. |
| **R2** a missing `markets()` fails at import | **DONE** | `sports._check_adapter` on the six-name contract, planted. |
| **R3** docstrings naming `audit.<name>` must resolve | **DONE** | `audit.docstring_reference_faults`, an AST scan, planted with a phantom. |
| **STEP 0** install the final passes | **DONE** | All eight tasks read back from the OS. |
| **STEP 0** verify Settings > Health shows them | **DONE** | All four appear with plain names. |

## 2. The base rate, before and after

```
before   0.3943      the assumed 9.79 + 1.0 x rating_diff
after    0.5024      the measured 4.848 + 0.9351 x rating_diff
```

A rung chosen nearest the expected margin should be close to a coin flip by
construction. It was 10.6 points off, and the cause was an intercept nearly
double what the data supports: **the model expected college home sides to win
by five points more than they do**, chose a rung that far out, and recorded the
favourite quietly failing it.

All three sports now sit where the rule says they should:

| sport | base rate |
|---|---|
| NFL | 0.4867 |
| NBA | 0.5016 |
| CFB | **0.5024** |

The refit intercept moved from −0.7275 to **−0.2701**, which is the same fact
seen from the model's side.

## 3. The three guards

**A training loader returns one sport.** `assert_one_sport` reads the `sport`
column off the games each loader selected and refuses a fit spanning more than
one. The NFL loader lost its `sport` filter in a commit about something else
and trained on four sports for days; a filter is a convention and this is a
mechanism.

**A sport adapter is complete or it is not loaded.** `sports.get` now checks
six required names when the module is imported. `markets()` was missing from
two adapters and took ruling R4's duplicate-slate guard down with it — failing
at first use, inside a scheduled run, as an AttributeError nobody reads.

**A docstring may not promise a guard that is not there.** An AST scan reads
every module, class and function docstring in the package, `tools/` and
`desktop/`, and fails on any `audit.<name>` that does not resolve. This rule
exists because `attach_decision` claimed a scan checked it and no such function
existed — the sentence read as a guarantee and the carve-out it described went
on to open the app on a five-day-old build.

Two things the scan learned immediately, both recorded in it: a name
hard-wrapped across a line is still one name, and **the planting's own
docstring tripped it** until the name was built at runtime instead — the same
self-reference `audit.py` already has with betting identifiers, answered here
without an exemption.

## 4. The final passes are installed

| task | at | held by the OS |
|---|---|---|
| Gridiron-Final-MLB | 14:30 | Ready, next 9/4 2:30 PM |
| Gridiron-Final-NFL | 08:00 | Ready, next 9/4 8:00 AM |
| Gridiron-Final-NBA | 15:00 | Ready, next 9/4 3:00 PM |
| Gridiron-Final-CFB | 08:00 | Ready, next 9/4 8:00 AM |

Read back from the scheduler, not assumed from the installer's output. Health
lists all four by their plain names; three read "has never run", which is true
until tomorrow morning.

## 5. What is measurably true now

- Suite **939 tests, 0 skips**, EXIT=0; `verify.py` **4/4**; **138/138**
  plantings (three new).
- CFB spread base rate **0.3943 → 0.5024**; all three sports within 0.02 of a
  coin flip.
- Eight scheduled tasks held by the OS at their declared times.
- No prediction row rewritten.

## 6. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
