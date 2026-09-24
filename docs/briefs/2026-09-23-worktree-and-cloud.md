# Brief — two rulings: the worktree rule, and the cloud split (2026-09-23)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Two rulings, 2026-09-23.

1. CLAUDE.md gains the rule the worktree move discovered: scheduled tasks run from the released commit on the main checkout; all repair and feature work happens in a worktree on its own branch and reaches the main checkout only by merge after a green gate. Planting: an uncommitted edit on the main checkout fails the gate by name.

2. Work split for cloud sessions. The operator has cloud credits. Jobs that run there, from a clone and a scratch copy of the record: adversarial diff reviews, multi-agent verification passes, the pick'em board-read measurement (never from the home IP), the Discord bot as its own repository, and Board UI screenshots against scratch. Jobs that stay local: anything that writes the live record, trains on it, registers or restarts a task, or reads the venue near kickoff. Every close-out reports its spend. Item 2 (fs5) is local and goes next, before Thursday's kickoff.

---

## How this brief is read

**Order.** GRIDIRON_REPAIR item 1 was mid-gate and mid-review when these
rulings arrived. It finishes first. Then item 2 (fs5), which is local and
time-bound: NFL week 3 kicks off Friday 25 September at 00:15Z, Thursday
evening Pacific. The worktree rule follows as its own commit with its planting.
Then repair items 3 to 8.

**Item 1's adversarial review started locally, before this ruling.** It is
allowed to finish, and the close-out says so. From here on, diff reviews and
verification passes run in cloud sessions, from a clone of the pushed branch
and a scratch copy of the record, never the live file.

**Spend** means the tokens each job used: the main session, its local agents
and its cloud sessions. Each is reported separately, and in dollars where the
app reports dollars.
