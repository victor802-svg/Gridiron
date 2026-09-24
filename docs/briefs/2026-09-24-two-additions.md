# Brief — two additions (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Two additions, 2026-09-24:
1. The reasoning pass stores the exact prompt it sent, or its hash plus the full inputs, with every row it writes, append-only. No reasoning row may exist without it; planting. Queue it after the voids, before item 3.
2. After the voids are gated, released and written to the live record, end this session as ruled. The next one starts from REPAIR_STATE.md.

---

## How this brief is read

"After the voids, before item 3" allows two places in the queue. This
morning's order already puts three rulings between the voids and item 3:
inactive-until-activated fits, the revert, and weather. The prompt record goes
**after those three and before item 3**. That keeps the order the operator set
earlier and satisfies both bounds of this one.

The need was found when the 31 reasoning rows had to be judged. No copy of the
prompts they were sent had been kept, so each had to be rebuilt from its
stored inputs through the prompt code as it stood that morning.
