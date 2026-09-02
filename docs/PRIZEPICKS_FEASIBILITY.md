# PrizePicks as a market source — feasibility probe

**Read-only. Measured 2026-09-02.** Nothing was built from this document.

Brief: `docs/briefs/2026-09-02-prizepicks.md`, PHASE Z1.

---

## The short answer

**The projections API is not accessible to this app, and the reason is not a
rate limit — it is active bot detection.**

Reaching it would mean defeating a CAPTCHA challenge. That is not something
this project will do, so **the build cannot proceed on this source** and phases
Z2 and Z4's live proof are blocked. Question 1 below is answered; questions 2
to 5 cannot be answered from PrizePicks at all, and the roster they were meant
to produce is not built from guesses.

This is the outcome the brief asked to be reported plainly: *"Say plainly that
it is unofficial and may break or be blocked."* It is blocked.

---

## 1. The endpoint, and what it actually returns

The endpoint the brief refers to is the public projections feed:

```
GET https://api.prizepicks.com/projections
```

**What one unauthenticated request returns, measured 2026-09-02:**

```
HTTP 403 Forbidden

{"url":"https://geo.captcha-delivery.com/captcha/?initialCid=...&cid=...
  &referer=https%3A%2F%2Fapi.prizepicks.com%2Fprojections ...}
```

`geo.captcha-delivery.com` is **DataDome**, a commercial bot-detection service.
The response is not an error page and not a rate-limit notice: it is a
challenge, served to the first request from a clean client with an honest
User-Agent identifying this project.

### The robots posture, and the tension in it

| host | `robots.txt` | meaning |
|---|---|---|
| `www.prizepicks.com` | `User-Agent: *` / `Disallow:` (empty) | nothing disallowed |
| `app.prizepicks.com` | **HTTP 403** | the file itself is behind the challenge |
| `api.prizepicks.com` | **HTTP 403** | same |

The marketing site's `robots.txt` disallows nothing. **The API host will not
serve `robots.txt` at all** — it answers the same challenge to that request as
to any other.

Where a published policy and a deployed technical control disagree, the control
is the clearer statement of intent: an operator who has paid for bot detection
and pointed it at their API is saying automated clients are not welcome there.
**This probe reads it that way**, and does not treat an empty `Disallow` on a
different host as permission.

### Rate expectations

Not measurable, and deliberately not explored. One request was made. Probing
the shape of a block is the beginning of working around it, and the answer to
"how hard is it to get past" is not one this project needs.

---

## 2–4. The questions that cannot be answered

The brief asks for stat types and per-slate counts by league (Q2), an identity
match against our stored players (Q3), and rung coverage against our declared
ladders (Q4).

**Every one of those requires the projections data.** They are not answerable
from any other source, and they will not be estimated:

- A stat roster inferred from what PrizePicks is *reported* to offer is a
  guess, and a ladder extension justified by a guess would be a declared
  constant with nothing behind it — the exact failure LAW 1 and the dated
  ladder rule exist to prevent.
- An identity-match rate cannot be computed against a name space we cannot see.
  The MLB crosswalk exists and was *measured*; inventing a rate for the other
  three sports would be worse than having none.

**They are recorded as unanswered.**

---

## 5. The roster

`docs/MARKET_ROSTER.md` **is not produced by this probe**, and the reason
matters: the brief's ranking is *volume × data availability*, and **volume is
the half that only PrizePicks can supply**.

What this project *can* measure on its own — whether resolution data exists in
our sources for a given stat — is one axis of a two-axis ranking. Publishing
that alone under the name the brief chose would present half a ranking as a
whole one, and the order it produced would look measured while resting on
nothing for the other half.

If a roster is wanted from what we can actually see, that is a different and
smaller document: "stats our loaders can already resolve", ranked by data
availability alone, with no claim about how often anyone offers them. Say the
word and it is an hour's work. It is not this.

---

## What this means for the rest of the brief

| phase | status |
|---|---|
| **Z1** the probe | **DONE** — this document. A negative result is a result. |
| **Z2** the second market source | **BLOCKED.** There is no accessible source to snapshot. |
| **Z3** STRONG by default | **UNAFFECTED.** It is a ruling about our own interface (R2) and touches no market source. |
| **Z4** verification | **PARTIAL.** Everything except the live PrizePicks proof, which has nothing to prove against. |

**The Law 5 amendment stands regardless.** It permits read-only lines from
PrizePicks as market data; it does not require them to exist, and the
one-module quarantine it introduced (`audit.market_source_faults`, planted and
caught) is a real guard that will hold if a lawful source ever appears.

## If this is to be revisited

Three routes, in the order this project would prefer them:

1. **An official or documented feed.** If PrizePicks publishes terms permitting
   programmatic read access, this becomes ordinary work.
2. **A different named public source** for the same stat types. The Law 5
   amendment names sources explicitly, so adding one is an operator ruling and
   a one-line change to the law — the same act that added PrizePicks.
3. **Nothing.** The record already scores itself against ESPN's lines. A second
   source is an improvement, not a requirement, and the props floor and the
   STRONG band do not depend on it.

**What this project will not do** is defeat the challenge, rotate identities,
or route the request to look like a browser. That is not a judgement about
PrizePicks; it is what "unauthenticated, read-only, public" has to mean if it
means anything.
