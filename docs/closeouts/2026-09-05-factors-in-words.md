# Close-out — encoded factors go to the model in words

Brief: *"The 27 encoded factors go to the LLM in WORDS, not numbers… Then
nothing — the reading era."*

---

## 1. Against the brief

| asked for | verdict | evidence |
|---|---|---|
| an indicator renders as its phrase's true/false form | **DONE** | `- a three-round bout`, with **no number appended** |
| a rate renders as a plain quantity with its unit | **DONE** | `- the age difference between the two fighters = 7.8 years` |
| through the same why-template door | **DONE** | `factor_value_words` composes from the declared `why`, the same phrase `why_sentences` uses on a card |
| planting: an indicator handed over as a bare number | **DONE** | plus a second for the half-fix — the phrase *and* the number |

**Nothing SKIPPED, nothing DECLINED.**

## 2. What the model is told now

Before:

```
- ufc_scheduled_rounds = 0
- ufc_age_gap = 0.78
- ufc_is_numbered = 1
- ufc_rating_diff = -0.42
```

After:

```
- a three-round bout
- the age difference between the two fighters = 7.8 years
- on a numbered card
- how good the two fighters have been = -42 rating points
```

**An indicator carries no number at all**, because the phrase *is* the value
and appending `= 0` would put back exactly what the phrase replaces. That is
planted separately, since it is the shape a later edit would most plausibly
take.

## 3. Sixteen declared, and the scales came from the code

`reads` maps an **exact value** to a phrase, so nothing is inferred — and a
tri-state simply declares three entries. `mlb_batter_platoon` reads *"the
batter has the platoon advantage"*, *"a switch hitter, so neither side has
it"*, *"the pitcher has the platoon advantage"*.

`unit`, `unit_scale` and `unit_offset` give a quantity its real units. **Every
scale was read from the function, not from the prose** — `/100.0`, `/365.0`,
`/10.0`, `/1000.0` — because a rationale describes intent and the code is what
runs.

## 4. `cold` carries no unit, and that is the point

`cold` returns `(temp_f - 55) / 20`, so a unit declaration writes itself. **It
also returns `0.0` for an indoor game.** A unit would print *"the cold = 55
°F"* about a dome — a temperature nobody measured, stated confidently.

> **It keeps its bare number**, and that is why this is a decision rather than
> a transcription. **A guessed unit is worse than a bare one: uninformative
> versus wrong.** Eleven other factors are left bare for the same reason — the
> declaration is opt-in and silence is the safe state.

## 5. Two guards caught me while I was writing this one

**LAW 1, within a minute.** The composer went into `language.py` first, and
`model/llm.py` imported it — which pulls a module naming `market_implied_prob`
and `running_total_line` into the **prediction closure**. The scan said so
immediately.

The fix follows the precedent already written in `CLAUDE.md`: *"the runtime
missing-data check therefore lives in `factors.compute`, and `audit`
re-exports it."* Same shape — `factor_value_words` lives in `factors.compute`,
which is on the path, and `language` re-exports it so the plain-words home
still owns the vocabulary.

**And then the planting escaped**, because it patched the re-export while the
prompt calls the real one. Pointed at `factors.compute` and it fired. **The
same lesson as every other guard here: point at the thing that runs.**

## 6. And the indicator pattern flagged ordinary English

The scan finds a factor whose rationale *declares* it an indicator but
declares no reading. The first pattern matched `1 when` — and
`mlb_pitcher_k_rate` reads *"how often he gets one when he has the chance"*,
which is prose about a rate between nought and one.

**"zero otherwise" is what tells a declaration from a sentence**, and the
pattern now requires it. A test pins the distinction using that very factor,
so the false positive cannot come back.

## 7. The gate

- Suite **1,063 tests, 0 skipped, 0 failures** under `.venv` — 8 new.
- Plantings **190/190** — two new.
- `verify.py`: **all four steps PASS**, 44 scan rows, one new.
- **No prediction row written, rewritten, re-dated or deleted.** No fitted
  coefficient changes: `reads` and `unit` affect only what the model is *told*
  and what a reader is *shown*.
- **`.env` was neither read nor written.**

## 8. Rulings taken in your absence

1. **Sixteen factors declared, not twenty-seven.** The eleven left bare are
   the ones whose zero is overloaded (`cold`) or whose scale the code does not
   state unambiguously. Declaring a scale I had inferred from prose would have
   handed the model a confident wrong quantity — the one outcome worse than
   the bare number it replaces.
2. **An indicator prints no number.** The brief said "renders as its phrase's
   true/false form"; a phrase followed by `= 0` is not that, and it is planted
   as a failure rather than left to taste.
3. **Every scale was taken from the function body.** Where the rationale and
   the code could have disagreed, the code wins and the rationale is the
   comment.
4. **The composer sits in `factors.compute`, not `language`.** Forced by LAW 1,
   and it follows a precedent this project had already written down.

## 9. What is left, and it is small

**Eleven encoded factors still hand over a bare number**: `asked_line`,
`nba_asked_line`, `cold`, `cfb_total_vs_form`, the three `prop_mean_vs_line`
variants, the two `prop_volatility` ones, `nba_prop_minutes`,
`nba_prop_teammate_competition` and `nba_net_rating_rolling`. Each needs
somebody to decide what its number means in units — a declaration, not code.
The guard will not chase them, because none of them declares itself an
indicator, which is the honest boundary: **the scan enforces what has been
declared and never guesses what has not.**

## 10. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
