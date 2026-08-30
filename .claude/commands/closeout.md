Run the session close-out against docs/MENTOR.md and CLAUDE.md.

1. Produce the close-out table for THIS session's brief: every phase
   the brief named, verdict (DONE / PARTIAL / SKIPPED / DECLINED /
   DEFERRED), one evidence line with commit hash.
2. Grade the session against MENTOR.md section 2, item by item:
   state which items the report satisfies and which it does not.
   Do not soften a miss.
3. List every red flag from section 3 that occurred this session
   and what was done about it.
4. List the vacuous passes found (including your own) and the
   class-level fix for each.
5. State what remains unverified, in those words.
6. Write the operator's attention list in priority order.
7. Leave three empty labelled slots for the operator's verdicts.
   Do not fill them.
8. Confirm FOLLOWUPS.md delta is non-zero if anything was deferred
   or learned; if it is zero, say why that is correct.

Output the whole thing as the final message. If tools/verify.py
has not run this session, run it first and include the gate output.
