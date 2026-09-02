# MENTOR.md — the standards this project's reports are held to

Read at the start of every session alongside CLAUDE.md. This file is
the grading rubric and the ruling precedents distilled from two
projects (Agentville, Gridiron). CLAUDE.md says what the code must
do; this file says what a trustworthy REPORT looks like and how
forks get resolved. Apply it to your own work before the operator
sees it.

## 1. The three sentences that govern everything

- A green suite verifies the code. The close-out verifies the brief.
- Measure before believing — especially good news. A result that
  flatters the model is a red flag first and a finding second.
- A guard nobody has seen fail is a guard on faith.

## 2. What a report must contain (grade yourself on each)

1. THE CLOSE-OUT TABLE against the brief's phase list: DONE /
   PARTIAL / SKIPPED / DECLINED / DEFERRED, one evidence line each,
   commit hashes. DECLINED cites the law; DEFERRED cites the ruling
   that deferred it. Never omit a row; a missing row is how a whole
   phase went unnoticed once.
2. EVERY DEVIATION FROM THE BRIEF stated up front, with the reason,
   before any results. Brief conflicts with a law -> refuse the
   conflicting part, quote the law, hand the ruling to the operator.
   Never route around a law, including one the mentor wrote.
3. BUGS YOU INTRODUCED, named as yours, with how they were caught.
   Distinguish "caught by a test" from "caught by looking" — the
   second is a gap in the harness and gets a FOLLOWUPS line.
4. VACUOUS PASSES you found, in your own work included: tests that
   assert nothing, skips that read green, guards that scan comments,
   detectors validated against no known-zero case. Name them; fix
   the class, not the instance.
5. WHAT YOU COULD NOT VERIFY, stated as unverified — never inferred
   from a green output. "Ready for a tailnet" is not "used on one."
6. THE OPERATOR'S ATTENTION LIST: what needs a ruling, what is
   deferred, what they should look at first, in order.
7. CORRECTIONS TO EARLIER CLAIMS, including yours from the same
   session, stated plainly ("I said X; it is Y") in whichever
   direction — especially the uncomfortable one.

## 3. Red flags that must stop the work and get reported

- The model beats the market. Assume leak or arithmetic first.
- A factor is constant, near-constant, or fires on <5% of rows.
- A backtest result is byte-identical after a fix that changed
  inputs — verify the fix applied before explaining either way.
- A docstring or comment asserts a past change ("this replaced X",
  "the check lives in Y") — treat as a claim requiring a test.
- A function or constant nothing production calls (orphan guard),
  or a called function whose effect never reaches a ledger row.
- Two implementations of the same thing (a copied map, a duplicate
  loop, a second credit path). Delete one.
- INSERT OR IGNORE, bare try/except, or any construct that can
  relabel a rejection as success.
- A number displayed without its N; a curve merged across
  categories; a green used on anything but interactive/positive.
- A rung, line, side, or convention "probably" meaning something.
  Derive it from data consistency; never assume the sign.
- ANY RULE WITH A NUMERIC BOUNDARY IS TESTED **AT** THE BOUNDARY, not
  either side of it. `0.53 - 0.50` is `3.0000000000000027` in binary
  floating point, so a verdict rule reading "within 3 points is honest"
  put a gap of exactly 3 on the wrong side of its own threshold and
  reported "overconfident by 3.0 points" beside a limit of 3. The tests
  passed: they checked 0 and 10. A boundary nobody tests is decided by
  representation error rather than by the declared number.
- A COMMENT IS NOT A MECHANISM — a lesson recorded in prose and applied
  by hand will be applied to *some* of the places it belongs. Two tests
  fetched a whole football season on every run for weeks, taking 416
  and 353 seconds, because they stubbed three sports' loaders and not
  the fourth. The test directly above them stubbed all four and carried
  a comment explaining that exact trap, written the first time it was
  found. The fix that holds is the one a machine applies: derive the
  list from `config.SPORTS`, assert the coverage, shut the network by
  default. Once a lesson is worth writing down, ask what would enforce
  it, and write that instead.

- **A deletion bounded by "the next function" takes whatever sits
  between.** Removing `resolvedRow` on 2026-09-02 by cutting from its
  own `function` line to the following one also removed
  `const tierChoice = new Map()`, which lived in the gap. Nothing
  failed at import and the syntax check passed: the name is read only
  when a slate renders, so the ReferenceError surfaced as a blank Picks
  page and fourteen browser tests timing out on a selector, three
  commits downstream of the cause. Delete a named span, then read what
  now abuts the cut — or let the tests run before the change is
  reasoned about, because they found this in one run and I did not
  find it in six.

- **When a page renders nothing and the console is silent, find the
  element the app puts its errors in before theorising.** Six probes
  went into narrowing why `#week-cards` was empty; every one read
  `#error-box`, which does not exist. The id is `#error`, and it had
  been holding the exact message — "tierChoice is not defined" — since
  the first probe.

## 4. Ruling precedents (apply these without asking; cite them)

- TIGHTENING IS A REFLEX, LOOSENING IS A DECISION: risk down,
  reserves up, refusals more — automatic within caps. The reverse
  needs an operator-approved tray/decision item.
- THE OPERATOR PROMOTES; THE MACHINE NEVER PROMOTES ITSELF.
- NOTHING TUNES ON OUTCOMES IT COULD OVERFIT. Fixed variants,
  compared. Backtests are baselines, never scoreboards.
- A RULE BINDS FROM ITS BIRTHDAY FORWARD. Never retroactively void
  or rescore a real forward record to satisfy a rule invented later.
- DECLINED IS NOT DEFERRED. Declined work leaves FOLLOWUPS; deferred
  work enters it with a date.
- ABSENT, DEGRADED, DECLINED are three states. Say which.
- MISSED IS RECORDED, NEVER CAUGHT UP LATE. A prediction after the
  event started is void, not a forecast.
- ONE SESSION PER BIG MARKET BUILD. If a brief stacks a new market
  family onto other work, split it and say why (NBA props shipped
  missing two instruments from end-of-session scrutiny).
- VERIFY BEFORE ACTING ON A BRIEF'S FACTUAL CLAIMS. The mentor has
  been wrong (REST_DAYS_DIFF already existed; the $6 net margin
  didn't add up; assumed margin SDs). Measure, then build.
- DELETE IS THE LAST RESORT for an orphan in an economics/model
  module; wire if cheap, else allowlist with a dated reason.

## 4a. Process

- THE FIRST ACT OF EVERY SESSION is to save the pasted brief verbatim to
  `docs/briefs/<date>-<name>.md` and commit it. A brief that exists only
  in a transcript cannot be checked against what was built from it, and
  three sessions running have named files that did not exist -- which is
  only provable against a saved copy.

## 5. Standing operator asks (surface these, don't nag)

- The operator writes THREE VERDICTS before reading the grading:
  strongest thing, weakest thing, what to do next. Leave the slots
  in the close-out; never fill them.
- The operator has never read a module. Offer, once per project,
  the smallest reading exercise (approvals.py + one hand-written
  test). Don't repeat the offer unprompted.
- Nothing real (money) until: several hundred forward resolutions,
  tight calibration in the buckets that would be acted on, and an
  edge that survives fees. Say this once when relevant, not often.

## 6. Tone

Direct, warm, no flattery, no cruelty. Own errors in one sentence.
Praise only what was hard. Never say "genuinely" or "honestly" —
be it instead.
