# Brief — retire home runs, the view menu, the hero floor, motion

Received 2026-09-05. Saved before execution, per the unattended contract.

---

FIRST ACT: save this brief to docs/briefs/<date>-retire-hr-motion.md,
commit. Read CLAUDE.md, docs/MENTOR.md. Then D1–D3, then R1–R4, one
commit each, push each.

R1 detail: registry entry {retired: 2026-09-05, reason: "operator
ruling"}; questions.py skips retired markets; the market tab shows
"Home runs · retired" greyed with its final settled count on Record
only (not on Picks); the props cap loop excludes it; the ticked
checklist doc notes the retirement. Plantings: a new HR row written;
a retired market appearing in Picks tabs.

R2 detail: the view menu is a 44px target, opens on click, closes on
outside click/Escape, keyboard reachable; its two choices render as
two small labelled toggles; the current choice shows as a one-word
tag on the menu button ("statistical · final"). Session-remembered
per sport (memory only). Planting: a control row above the hero
beyond the two declared.

R3 detail: HERO_MIN_CLAIM = 0.55 dated; the hero selection function
takes the tab's cards and the sort, filters by the constant, returns
the first or None; the "no lead" sentence composed in language.py.
Planting: a hero showing a claim under the constant.

R4 detail: transitions implemented in the one motion block; the
carousel keeps its dots and arrows and adds swipe on touch; render
before commit at 1440 and 390 with a tab switch mid-transition
captured; reduced-motion render identical layout with zero
transitions. Planting: a translateY or scale outside 2%; a duration
over 200ms.

QA: full suite no skips under .venv; all plantings; verify.py green;
renders (Picks on MLB with the new control row, the view menu open,
the hero on a tab with no >=55% pick, Record with the retired
category); read-cold pass on five cards; /closeout; push.

---

## How this brief is read

- **D1–D3 were not pasted.** The brief names them ("Then D1–D3, then R1–R4")
  and gives detail only for R1–R4. Nothing here says what D1–D3 are, and
  inventing three design phases is the failure the contract forbids. They are
  BLOCKED in the close-out, not skipped; sending them is one paste. R1–R4 are
  built from their detail paragraphs.
- One commit per R, pushed as it lands; every planting named in the paragraph
  gets a guard that fires by name.
- The renders and the cold read happen before the close-out, at 1440 and 390.
