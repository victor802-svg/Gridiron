# Morning report — GRIDIRON_NIGHT_AUDIT, 2026-09-08

Nothing in this run wrote to the live record: every measurement went through the query-only handle or a scratch copy made with the backup API. Full close-out: `docs/closeouts/2026-09-08-night-audit.md`.

| item | verdict | evidence | what changed | what needs you |
|---|---|---|---|---|
| **First: tonight's open items** | DONE | tap retraction as an append-only row (`picks_retracted`, `picks_taken_no_delete`); scratch guard `LiveRecordTouched` + `read_the_live_record`, 26 call sites converted; the college-basketball package printed beside its tag — `cbb`, correct — and `SAME_GAME_SERIES` declared | commit `1af3f74`, pushed; bundle stamped `1af3f74`, exe SHA-256 `c4eaa413…c86cd` | nothing |
| **1. Silent failure** | DONE + 1 defect + 2 rulings | every job's last run vs last success (close-out table). The notices bar THREE_STATES removed was the only route from `task_runs` to the first screen. | the day strip now prints "daily run 16h ago · venue read 10h ago · reasoning pass 12h ago", marked stale past 36/30/36 h (dated in config) with the threshold in the words; scan + planting | **the live poller has no scheduled task and has not run since 2 Sep** (register it, or declare Live a read of `refresh`); **"turns red" vs the colour law** — red is reserved for a loss by the guard you ruled; stale ships bold in the warning ink until you widen it |
| **2. Sleep** | REPORTED | Balanced plan, **sleeps after 15 min idle on AC**, hibernate off, wake timers allowed, **no task has WakeToRun**, all `StartWhenAvailable`, catch-up at logon only | nothing, by ruling | **run `powercfg /change standby-timeout-ac 0`** (or give each `Gridiron-*` task `-WakeToRun`). Asleep 12–20 Sep the record stops growing, each slate that starts is written MISSED, the phone loses the app |
| **3. Pipeline on scratch** | DONE + 1 ruling | key from `.env` ✓ (absent from the environment); MLB tickers 15/15, no doubleheader today, UFC 0/5 by declared absence; refresh ✓; near-start not exercisable at 02:40; 0 claims after kickoff since the guard; side map ✓; LLM game-markets-only ✓; predict refused an answered slate correctly | nothing | **the closer sits below near-start's early return** — two finished games' recommendations stay unclosed until the next window (value unchanged; timing only) |
| **4. Guards** | DONE, 3 gaps closed | 243/243 → 245/245. Would have passed: a `urllib` POST at the venue (`Request(url, data=…)` has no verb), the COMBOS identifiers on a label, four credential spellings, two ledger shapes | scan reads the market module's syntax tree; planting; list additions (each grepped first, 0 hits) | nothing |
| **5. Waste** | REPORTED + 1 ruling | 7-day fetches by host; LLM 178 calls; poller **0 requests, it never runs**; `refresh` 2 requests, 0 repeats; **694 SQL statements per Picks render** — coverage re-measured per card (0.3 s today) | nothing | per-card coverage: declare once-per-slate, or leave |
| **6. Dead weight** | DONE | `heroPool`/`HERO_STEPS`/`shortNotice`: 0 callers; `.notices*`/`.view-menu`: classes nothing builds; **the edge line repeated its label on both card kinds** ("EDGE AFTER FEES +9.0¢ after fees") — sibling of "Payspays" | removed with a test proving absence; `edge_line_words` fixed | nothing |
| **7. Both widths** | DONE (DOM), screenshots partial | Upcoming/Live/Results/Settings at 1100 and 390: no overflow anywhere, Settings widest 376 px at 390, 0 tap targets under 44 px; the pane was minimized so most captures timed out — two succeeded | nothing | nothing |
| **8. The record** | PRODUCED | MLB moneyline 155 settled / 97 priced, spread & total 97/76, cfb three markets 130–137 all at gate; **CLV pairs 0 everywhere** (first closes land at the next near-start window); corrections fitted but not applied — check rows 13–29 of 40 | nothing | read it on the 21st |
| **9. READINESS / FOLLOWUPS** | DONE | READINESS: pipeline whole 2026-09-07; the 17 backfilled claims identified by `created_utc > kickoff_utc` (no column marks them); combo record opened 2026-09-08 empty. FOLLOWUPS triaged by class | docs | six rulings, above |
| fixed: edge line repeats its label | (a) | | `edge_line_words` | |
| fixed: dead job invisible on first screen | (a) | | the strip | |
| fixed: urllib POST passes the order-path scan | (a) | | scan + planting | |
| fixed: dead code and styles | (a) | | removals + test | |

**Build the desktop and phone are running:** audit commit `77a0bbd`, pushed; bundle stamped `77a0bbd`; `Gridiron.exe` SHA-256 `ee6023aca4894ea78cd657e5b32d29ac0549bcb3285c983a49d8087ab0388a90`. Serve was stopped for the rebuild and restarted; it answers on 8848.

**One housekeeping item for you, not done because it is irreversible:** `var/gridiron.db.pre-combos.bak` (966 MB) is the pre-migration backup I took before rebuilding `picks_taken`; the migration is proven and committed, so it can be deleted.

**The single thing most likely to cost you money in the next thirteen days.** The machine sleeps after fifteen idle minutes and nothing wakes it, and the one pass that reads the venue near kickoff — the second look that writes the price you are shown, the at-the-line claim, and the close — only runs while the box is awake. The first NFL slate opens tomorrow with zero settled questions in every football market, so every football card will carry "no measured edge" and a flat unit; the danger is not that, which the card says, but a card whose price is hours stale because the pass slept, read as current. Set the box never to sleep on AC, and read the pulse line under the day strip before any tap: if "venue read" is past 30 h, the price on the card is not the price at the window.

---

## Addendum, 2026-09-08 morning — your six rulings and your six defects

**Your rulings, all executed.** (1) `Gridiron-Live` registered at the cadence
`live.py` declares — every 90 seconds, `IgnoreNew`, in the installer too; it
has fired on its own and recorded "nothing is on; no request made". THREE_STATES
shipped the Live tab on 2026-09-08 against a poller whose only two runs were by
hand on 2026-09-02, so `games.status` never became `in` and Live had nothing to
show on any evening in between — recorded in that close-out. (2) The closer
moved above near-start's early return, with a planting. (3) The colour law
stands; every "red" in the docs now says what shipped. (4) Per-card coverage
left, after the 21st. (5) The backup is yours.

**(6) "Fitted, not applied" is DELIBERATE, with the reason and the date, and
not a defect.** `correction.HOLDOUT_MIN = 40` says so in its own declaration:
the holdout needs 40 rows, which at the 80/20 split means a category activates
from **about 200 settled** — "later than the brief's fifty, and it is what the
measurement supports: fifty is the bar for FITTING a correction and looking at
it, not for applying one." The measurement is dated 2026-08-31: a perfectly
calibrated category passed a bare comparison 38% of the time, so activating on
one would switch on corrections that correct nothing while the page called them
earned.

It does not contradict TODAY's ruling. "Apply automatically and report
afterwards" removed the human approval step; it did not remove the quality bar.
**But my column heading was misleading and I am correcting it:** it should read
"fitted; not yet activated, because its holdout is too small to judge on".
Where each category actually stands, measured today:

| category | settled | holdout rows | more needed (of ~200) |
|---|---|---|---|
| mlb moneyline | 141 | 28 | 59 |
| cfb moneyline | 137 | 27 | 63 |
| cfb spread | 134 | 26 | 66 |
| cfb total | 129 | 25 | 71 |
| mlb spread / total | 83 | 16 | 117 |
| mlb prop | 65 | 13 | 135 |

**No correction has ever been active on any category.** At current settle rates
the first activations land in early October, not on the 21st. If you want them
sooner, that is a dated ruling lowering `HOLDOUT_MIN` and accepting the
measured false-activation rate — a class (b) change I did not make.

**Your six screen defects: one was not a defect, five were, all five fixed.**
The Combos group renders with zero packages at both widths — your screenshot
predates the 03:14 rebuild. Fixed: the old "More picks" grid and its renderer
removed; the group heads now leave the screen with their groups; one source of
truth for the next start (header and Live now both say 3:35 PM); baseball reads
"total runs" on Picks, Results and the digest; and each sport's flagged-method
note cites only its own walk-forward.

**And the finding about my own work, which is the one that matters:** the night
audit passed Live "via the DOM" because screenshots timed out with the pane
minimised. A DOM check sees what it asks for. It could not see fifteen cards in
a design we replaced rendering underneath. **From here a close-out with no
screenshot of a route says that route is unverified.** All four routes at both
widths are captured in the addendum to the night-audit close-out.

I also introduced two defects doing this and both were caught by loading the
page rather than by a test — a text-boundary cut in `app.js` took six
neighbouring functions with it, and the grid's loading skeleton outlived the
grid. Both are written up where they happened.
