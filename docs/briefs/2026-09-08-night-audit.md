# Brief — GRIDIRON_NIGHT_AUDIT (2026-09-08)

Saved before execution, as the standing contract requires. The operator's text
is unedited; how it is read follows.

---

GRIDIRON_NIGHT_AUDIT — ruled by the operator 2026-09-08. The operator is asleep; no answers are coming until morning. This is an AUDIT with a narrow repair remit, not an optimisation pass. The observation window is open and runs to 21 September.

THE REMIT, in three classes:
(a) DEFECT — something that does not do what its brief, law, or docstring says: fix it, gate it, commit it, list it.
(b) MODEL, RANKER, CORRECTION, DRIFT, SNAPSHOT, CAP, GATE, FACTOR — do not touch, however tempting. Write the finding to FOLLOWUPS with the evidence and stop.
(c) AMBIGUOUS — report it in the morning table with the two readings; do not choose.
Nothing in this run may write to the live record. All verification runs against the scratch database under the guard from GRIDIRON_COMBOS; if that guard does not yet exist, building it is the first task.

FIRST, close what is open from tonight if not already closed: the synthetic tap's retraction as an append-only row; the scratch-database guard and its planting; the sport tag on the "college-basketball" packages printed beside a package title; then commit, push, rebuild the bundle, and record the build hash.

THEN AUDIT, in this order, each with evidence not assertion:

1. SILENT FAILURE. For every scheduled job — daily run, recalibration, near-start pass, live poller, venue read, resolve — report: when it last ran, when it last SUCCEEDED, and whether those differ. Then build the check that the dead key should have tripped: the day strip on Upcoming prints the age of the last successful run, the last venue read, and the last reasoning pass, and turns red past a declared threshold per job. A job that fails must be visible on the first screen the operator opens. This is a screen change and is permitted.

2. SLEEP. Report whether each scheduled task is configured to wake the machine and what happens to the record if the desktop sleeps from 12 to 20 September. Do not change power settings; tell the operator what to set.

3. THE PIPELINE, END TO END, ON SCRATCH. Key present from .env and not the environment; ticker resolution for every sport with a game today, including doubleheaders; the near-start window; the side map; claims priced against pregame prices and never in-game; the LLM pass reaching game markets only; both forecasters writing on every run with the View menu gone. One row per step: pass, fail, or not exercisable today, with why.

4. GUARDS. Run the full planting set and the gate. Report the count and the hash. Then read the plain-words list, the credential scan, the no-marks scan, the taken-is-not-a-ledger check, and the closure scans, and list any string, asset, column, or import that would pass today and should not.

5. WASTE. Daily API spend by call type over the last seven days; the poller's request count and whether it polls when nothing is live; any query that runs per card instead of per page; any fetch repeated within one run. Fix only what is a defect by class (a); report the rest.

6. DEAD WEIGHT. Code, routes, templates, styles and tests that served the pages removed by THREE_STATES and the View menu; duplicate function definitions; migrations that split on semicolons; the two pre-existing card defects found tonight and any siblings of them on other cards. Remove dead code only when a test proves nothing references it.

7. BOTH WIDTHS. Overlap, overflow and contrast on every route at desktop and 390px, with the pair list current. Screenshots of Upcoming, Live, Results and Settings at both widths in the close-out.

8. THE RECORD. For each sport and market: N settled, N with a venue price, N of CLV pairs, correction status, days until each gate at the current rate. This is the table the operator reads on the 21st; produce it tonight so he sees the trajectory.

9. READINESS and FOLLOWUPS. READINESS records the date the pipeline became whole, the backfilled-claims flag, and the combo record's open date. Triage FOLLOWUPS into: fix now (class a, and do it), rule needed (class c, for the morning), and after the 21st.

MORNING REPORT: one table, one row per item above plus one per defect fixed, columns: item, verdict, evidence, what changed, what needs the operator. Then the build hash the desktop and phone are running. Then, in one paragraph and plain words, the single thing most likely to cost the operator money in the next thirteen days.

---

## How this brief is read

**Class (a) is the only class that changes code**, and it has to be a defect
against a brief, a law or a docstring — not an improvement. Class (b) is a
hard fence around the model, ranker, correction, drift, snapshots, caps, gates
and factors: findings go to FOLLOWUPS with evidence, and nothing else. Class
(c) is reported with both readings and no choice made.

**Nothing writes to the live record.** The guard from GRIDIRON_COMBOS
(`db.LiveRecordTouched`, `db.read_the_live_record`) exists; every measurement
in this audit runs under it or on a scratch copy.

**Item 1's screen change is explicitly permitted** and is the one construction
task in the brief. Everything else is measurement, repair-by-class, and the
morning table.

**Ordering is the operator's:** close tonight's open items and record the
build hash first; then 1 through 9 in order; then the morning report.
