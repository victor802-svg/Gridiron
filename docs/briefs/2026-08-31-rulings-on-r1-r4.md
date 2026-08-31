# Rulings on the R1–R4 attention list

Pasted verbatim, 2026-08-31, in answer to §6 of
`docs/closeouts/2026-08-31-r1-r4.md`.

---

Rulings on the R1-R4 attention list:

1. PROSE IS COMPOSED SERVER-SIDE ONLY, in language.py, period. The
   frontend renders strings it is handed; it never builds a
   sentence, never concatenates a subject, never uppercases a stat.
   Enforce two ways: the package-wide side_named guard as shipped,
   plus a JS scan for prose-building patterns ('picked ' +, subject
   concatenation, toUpperCase on data fields) — imperfect is fine,
   it is a tripwire not a proof; the render-based plain-words scan
   remains the backstop that sees results.
2. Run the shadowed-definition guard's question backwards once: any
   OTHER dead-but-named code shapes? Add the app.js orphan scan
   (renderCard, 5,417 chars, zero callers) to this sweep — one
   FOLLOWUPS item, one session, not now.
3. Versions change lines: cap at the two most consequential changes
   plus "and N smaller changes", full list stays on the page below.
4. The ladder question gets MEASURED before it gets retuned. Add to
   the props slate log the model's claim at every OFFERED rung,
   written or not. After two weeks: if below-floor claims cluster
   at 60-69 near the mean rung, that is the floor working as
   designed, not a mis-set ladder. Decide then, with the
   distribution in hand. Four days is not evidence.

---

## How these were read

- **1, 3 and 4 are built this session.**
- **2 is deferred to its own session** ("one session, not now") and
  enters FOLLOWUPS as one item. One correction to its premise is
  recorded below.
- Ruling 4 is a MEASUREMENT, not a retune. Nothing about the floor or
  the ladder changes; the log starts recording what would be needed to
  decide, and the decision waits two weeks for the distribution.

## Correction to ruling 2's example

`renderCard` was already deleted, in the K0–K4 session, along with
`shortSubject` — both found by the Python orphan scan being pointed at
`app.js` by hand and both removed then. The example is spent; the
RULING is not, because nothing automated looks at `app.js` today, so
the next orphan there will not be found the same way.
