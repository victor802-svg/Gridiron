# College football — feasibility probe

Measured 2026-08-31 against `sports.core.api.espn.com`, league path
`football/leagues/college-football`. Read-only throughout; no CFB code
existed when any of this was taken.

**One market is killed by the evidence: player props.** Everything else the
brief asked for is supported. The detail is below, item by item.

---

## 1. Schedule, results and stats

**The league path carries the full FBS season with finals and team box
scores.** The division split is read from the feed: group 80 is named `FBS`
with 11 child conferences, group 81 `FCS` with 14, and each team document
carries a `groups` ref — so "is this opponent FBS?" is answerable per team,
never from a typed list.

| | 2025 | 2026 |
|---|---|---|
| FBS teams, via group 80 | **136** | **138** |
| distinct regular-season events (union of team schedules) | **888** | **892** |

### The weekly endpoint is a subset and must never be used

`/seasons/{y}/types/2/weeks/{n}/events` returns roughly twenty events per
week — 23, 23, 21, 16 for weeks 1, 2, 3, 5 — with `pageCount: 1` at
`limit=500`, so it is not pagination. Against the 888 the union finds, that
endpoint carries under a third of the season. **Anything built on it would
silently forecast a fraction of the slate and look complete.**

**The slate is the union of the 136 per-team schedules**
(`/seasons/{y}/types/2/teams/{id}/events`), de-duplicated by event id. One
request per team per season, permanently cacheable once a season is done.

### Two shapes the loader must handle

- **FBS-vs-FCS games appear as ordinary events**, with scores, and resolve
  like any other. The first week-3 event returned was *Indiana State at
  Indiana*.
- **`week` is `None` on 2026 events.** The week number is not populated for
  the live season, so **slates must be derived from dates**, not from
  `week.number`. The day groupings are unambiguous: 2026-09-05 has 60 games,
  2026-09-06 has 16, 2026-09-04 has 8.

### Team game statistics exist

Each competitor carries a `statistics` ref with ten categories including
`passing` (attempts, completions, net yards) and `rushing` (attempts,
yards) — enough to derive pace without a second source.

## 2. Lines — the R-A slate size

**Two independent measurements agree that spreads and totals are effectively
complete, and that the moneyline is the competitive slate only.**

A random sample of **260** of the 888 completed 2025 events:

| | count | share |
|---|---|---|
| carries an odds document | 259 | **100%** |
| spread | 256 | **98%** |
| total (`overUnder`) | 258 | **99%** |
| moneyline | 227 | **87%** |

The live slate for **Saturday 2026-09-05**, all 60 games:

| | count | share |
|---|---|---|
| odds / spread / total | 60 | **100%** |
| moneyline | 44 | **73%** |

### Where the moneyline goes missing, and why

The 32 games with no moneyline are not a parsing failure: their
`homeTeamOdds` carries spread fields and no `moneyLine` key at all. They are
the **blowouts**.

| | n | median \|spread\| |
|---|---|---|
| games carrying a moneyline | 227 | **8.5** |
| games without one | 29 | **34.5** |

At `|spread| < 28`, 212 of 221 games carry a moneyline (**96%**). At
`|spread| >= 28`, only 15 of 35 (**43%**).

**Consequence for R-A:** spread and total questions can be asked on the whole
slate; moneyline questions will be asked on roughly three-quarters of it, and
the missing quarter is systematically the least competitive games. That
absence must be recorded as an absence, never filled from the spread.

## 3. Identity — single-source, no crosswalk

**260 of 260** sampled events carry both competitors' team ids inline, and
those ids are the same ESPN ids the odds documents key on. Stats, schedule
and lines all come from one host and one id space.

**Checklist item 3 is satisfied by construction for CFB**: there is no second
feed to reconcile, so there are no aliases to reverse and no reference set to
get wrong. This is the one thing about college football that is *easier* than
MLB or NBA.

Team names come from the feed's `displayName` (e.g. "Auburn Tigers") with
`location` ("Auburn") beside it — which maps exactly onto the existing
full/city split, so the school form in prose costs nothing new.

## 4. Measured constants

From the same 260-game sample, all with final scores:

| | mean | **SD** | N |
|---|---|---|---|
| margin (home − away) | +9.79 | **22.46** | 260 |
| total points | 53.82 | **16.19** | 260 |

**CFB margin SD is 22.46 against NFL's 12.70** — 77% wider, which is what the
brief expected and is now measured rather than assumed. The home-field mean
of +9.79 is also far above the NFL's.

Both constants are dated 2026-08-31 with their N, and the undated-SD guard
extends to them.

> Measured on a sample, not the full season, because each game's scores sit
> behind two further `$ref` fetches and a full season is ~2,700 requests.
> 260 is reported beside every figure it produced.

## 5. Weather and travel — possible, with a mandatory filter

**ESPN's CFB venue documents carry no coordinates.** The full document has
`fullName`, `address` (city / state / zipCode / country), `grass`, `indoor`
and nothing else. 919 venues. This blocks wind *and* travel distance, both of
which NFL takes from nflverse's published airports table — for which college
football has no equivalent, and 136 stadium coordinates typed from memory is
what checklist item 3 exists to forbid.

**Open-Meteo's geocoder closes it** — same provider and CC BY 4.0 licence as
the forecast path already in use.

| measurement | result |
|---|---|
| distinct FBS home venues | **136** |
| indoor / outdoor | **4 / 132** |
| ESPN state code is a real US state | **136 of 136** |
| geocoded to a US city **in the right state** | **136 of 136** |
| where the FIRST US result was the **wrong state** | **23 (17%)** |

**The state filter is mandatory and the number proves it.** Open-Meteo orders
by population, so a bare lookup for `Auburn` returns Auburn, **New York**
ahead of Auburn, **Alabama** — the wrong Auburn by about 900 miles. Twenty-
three of 136 venues would take the wrong city. `admin1` is the full state
name and ESPN gives the two-letter code, so a code→name map is required; every
code appearing in the feed was checked against it (0 unknown).

Resolved coordinates are stored with their source and the date they were
fetched, and a venue that does not resolve is **absent**, never defaulted to a
state centroid.

## 6. Player props — NOT AVAILABLE, and not built

**Zero prop rows, on completed and upcoming games alike.**

- Every 2025 event probed returns an error from
  `/events/{id}/competitions/{id}/odds/{provider}/propBets`.
- Every one of Saturday's 60 games returns **0 prop rows**.
- A CFB event carries exactly **one odds provider** (100, DraftKings), and
  that provider's `propBets` endpoint 404s. There is no second provider to
  fall back to.

Player *game statistics* do exist and would resolve props if lines existed —
the gap is the lines, not the results.

**Ruling on R-C: props are not built for CFB.** The build shrinks to the
three team markets the evidence supports: spread, moneyline and total.

---

## What this means for the build

| market | verdict | slate |
|---|---|---|
| **spread** | build | ~100% of games |
| **total** | build | ~100% of games |
| **moneyline** | build | ~73%, and the absent quarter is the blowouts |
| **player props** | **do not build** | no lines exist at any provider |
