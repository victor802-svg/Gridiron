# Brief — four fixes from the key-rotation findings

Received 2026-09-05. Saved before execution, per the unattended contract.

---

Four fixes, in this order:
1. ufc_scheduled_rounds = 0 on a three-round bout: find out whether
   the prompt renders ABSENT as 0 (silent default — forbidden by
   checklist item 5) or the stored value is wrong. Fix at the source;
   plant it. Check every factor the LLM prompt receives for the same
   rendering.
2. send() posts before it records. Reverse it: record intent, post,
   then mark sent/failed — a push that reached the phone must exist
   in the record. Planting: a post with no prior row fails.
3. llm.reason runs before the existence check. Move the check first
   so an interrupted or backfilled run never re-reasons rows that
   exist. Planting: a re-run on a half-written slate makes zero
   calls for the written half.
4. LLM reasoning carries internal identifiers onto the card (45%).
   Two changes: the prompt presents factor values under their plain
   names (the why-template phrases), never the code names; and the
   plain-words scan runs on the LLM view — add the forecaster switch
   to the render test, since the view has never been looked at.
   Existing rows stand (Law 3) — at render time the humaniser
   substitutes plain names for any code name in stored reasoning,
   through the one door, so old rows read cleanly without being
   rewritten. Planting: a code name in rendered LLM reasoning.
Commit each, push, /closeout.

---

## How this brief is read

- **Four commits, in the given order**, each pushed. The order matters: fix 1
  is a diagnosis before it is a change, and fix 4 depends on knowing what the
  prompt actually hands the model.
- **Fix 1 is a question first.** "Find out whether" — the answer decides where
  the fix goes. A stored zero and a rendered zero have different repairs and
  only one of them is checklist item 5.
- **Fix 4 has two halves and a third quiet part.** The prompt stops using code
  names; the render test starts looking at the LLM view; and old rows are
  humanised AT RENDER TIME rather than rewritten, because LAW 3 forbids
  touching them.
