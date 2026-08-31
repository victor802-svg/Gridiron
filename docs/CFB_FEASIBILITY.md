# College football — feasibility probe

**STATUS: INCOMPLETE.** Phase B1 was interrupted mid-probe by the
calibration brief (2026-08-31), which was taken up first. Everything below
is measured, dated, and read-only against the sources. The questions still
unmeasured are listed at the foot, by the brief's own numbering. **No CFB
code exists and nothing has been built on any of this.**

Measured 2026-08-31 against `sports.core.api.espn.com`, league path
`football/leagues/college-football`.

---

## 1. Schedule, results, stats — PARTIALLY MEASURED

**The league path exists and carries completed games with scores.**

| what | measured |
|---|---|
| teams in the 2025 season feed | **807** (all divisions, not just FBS) |
| FBS teams, via group 80 | **136**, across **11** conferences |
| a completed game | scores, `winner`, `STATUS_FINAL`, attendance, venue |

**The division split comes from the feed, not from a guess.** Group 80 is
named `FBS` (11 child conferences) and group 81 is `FCS` (14). Both were
read from `/seasons/2025/types/2/groups/{id}`, and the team's own document
carries a `groups` ref, so "is this opponent FBS?" is answerable per team
without a typed list.

**FBS-vs-FCS games appear as ordinary events.** The first 2025 week-3 event
returned was *Indiana State Sycamores at Indiana Hoosiers* — an FCS
opponent, present in the schedule with scores like any other game.

### The league-wide weekly endpoint is a SUBSET, not the slate

`/seasons/2025/types/2/weeks/{n}/events` returns roughly twenty events per
week — 23, 23, 21 and 16 for weeks 1, 2, 3 and 5, with `pageCount: 1` at
`limit=500`, so this is not pagination. A real FBS week is 60–80 games.
**Anything built on that endpoint would silently forecast a fifth of the
slate.**

The full slate is the **union of per-team schedules**:
`/seasons/2025/types/2/teams/{id}/events` returned 12 events for Auburn.
Cost: ~136 team requests per season plus each event document, all
permanently cacheable for completed seasons.

> Not yet measured: whether the union across all 136 FBS teams reconstructs
> a complete week, and what team game stats the box score actually carries.
> The `competitions` document advertises `boxscoreAvailable` and
> `hasDefensiveStats`; neither has been opened.

## 5. Weather — MEASURED, and it needs a guard

**ESPN's CFB venue documents carry no coordinates.** The full venue
document has exactly: `id`, `guid`, `fullName`, `address`
(city / state / zipCode / country), `grass`, `indoor`, `images`. There are
919 venues in the feed. No latitude, no longitude, at either the
competition's embedded venue or the standalone `/venues/{id}` document.

This matters beyond weather: **travel distance needs coordinates too**, and
NFL gets its from nflverse's published `airports.csv` (CC BY 4.0). College
football has no equivalent in this project, and 136 stadium coordinates
typed from memory is precisely what checklist item 3 forbids.

**Open-Meteo's geocoding API closes the gap** — same provider, same CC BY
4.0 licence, already a declared source for the forecasts themselves.

| measurement | result |
|---|---|
| distinct FBS home venues | **136** |
| indoor / outdoor | **4 indoor, 132 outdoor** |
| venues whose ESPN state code is a real US state | **136 of 136** |
| geocoded to a US city **in the right state** | **136 of 136** |
| of those, where the FIRST US result was the **wrong state** | **23 (17%)** |

**The state filter is not optional and the number proves it.** Open-Meteo
orders results by population, so a bare name lookup for `Auburn` returns
Auburn, **New York** (pop. 26,985) seventh-best-known ahead of Auburn,
**Alabama** (pop. 62,059) — the wrong Auburn by about 900 miles. Twenty-three
of the 136 FBS venues would take the wrong city that way.

`admin1` is the full state **name** ("Alabama"); ESPN gives the two-letter
code ("AL"), so a code→name map is required. That map is 51 rows of a
stable public standard and every code appearing in the feed was checked
against it (0 unknown), which is a round-trip rather than a memory.

**Conclusion for the build:** wind at kickoff is feasible for CFB totals,
and so is travel distance, but only through a geocoding step that filters
on state and records the resolved coordinate with the source and date it
came from. A venue that does not resolve must be **absent**, never
defaulted to a state centroid.

---

## Still unmeasured — the rest of B1

These were not reached before the brief was switched. None is answered, and
none should be assumed:

2. **LINES.** Spread, moneyline and total (`overUnder`) coverage across a
   real current-week slate — the fraction carrying each. This sets the
   slate size under R-A and is the single most consequential unmeasured
   number here. The `competitions[0].odds` ref exists on CFB events, but no
   coverage fraction has been computed. *A first attempt returned 0 games
   because the week filter was wrong, not because the data is absent.*
3. **IDENTITY.** Whether stats and lines are genuinely single-source ESPN
   ids, which would remove the crosswalk problem entirely for CFB. Strongly
   suggested by both coming from the same host, and **not yet confirmed**.
4. **MEASURED CONSTANTS.** CFB margin SD and total-points SD, from past
   seasons, dated and with N. The brief expects margin SD well above NFL's
   12.70; nothing has been computed, so nothing is claimed.
6. **PROPS.** Whether CFB player prop lines exist at usable coverage and
   whether player game stats can resolve them.

Also open from item 1: that the per-team union reconstructs a full week,
and what the box score carries for team game stats.
