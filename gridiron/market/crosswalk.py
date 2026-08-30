"""THE MEASURED PLAYER CROSSWALK — new-market checklist, item 3.

The stats source and the odds source share no player id. Paul Goldschmidt is
`502671` to statsapi.mlb.com and `31027` to ESPN; neither payload carries the
other's number, and neither offers a crosswalk field. The only bridge is the
name.

A name bridge is exactly the kind of thing this project has been burned by
twice, both times in the same shape: a mapping written from memory, believed,
and wrong in a way nothing announced. Two reversed NBA aliases left 7 of 53
games unmatched, and the reference set written to check them was itself wrong.
So this module does four things that a `dict` in a source file cannot:

  1. **It measures.** Every match records HOW it was made — `exact` when the two
     raw names were already identical, `normalised` when it took accent
     stripping and punctuation folding. Both rates are reported. The
     normaliser's contribution is a number, not a hope.
  2. **It refuses.** Two players normalising to the same string is an ambiguity,
     and an ambiguity is recorded as a refusal with its reason. The prop is
     skipped. A coin flip between two players is not a match.
  3. **It persists, dated.** Rows carry `measured_utc`, so a crosswalk can be
     read months later and its age is visible.
  4. **It re-runs.** September roster expansion lands inside the window these
     markets are scored over, and a name that did not exist last week is a new
     unmatched name — logged, never silently dropped.

**This module is inside the LAW 1 quarantine** because it reads ESPN. It maps
ids so a published prop line can be attached to an already-written prediction;
nothing in any prediction path may import it.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata

from ..data import sources as http
from ..db import utcnow

CORE = "https://sports.core.api.espn.com/v2/sports"

LEAGUE_PATH = {"mlb": "baseball/leagues/mlb"}


def normalise(name: str | None) -> str:
    """Fold a name to the form two feeds can be compared on.

    Accents, punctuation and case only. NOT nicknames, NOT initials, NOT
    fuzzy distance — every one of those turns a failed match into a wrong one,
    and a wrong match attaches a line to the wrong player silently.
    """
    if not name:
        return ""
    stripped = unicodedata.normalize("NFKD", name)
    ascii_only = stripped.encode("ascii", "ignore").decode("ascii")
    for ch in (".", "'", "’", ","):
        ascii_only = ascii_only.replace(ch, "")
    ascii_only = ascii_only.replace("-", " ")
    return " ".join(ascii_only.lower().split())


def athlete_url(sport: str, espn_id: str) -> str:
    return f"{CORE}/{LEAGUE_PATH[sport]}/athletes/{espn_id}"


def our_players(conn: sqlite3.Connection, sport: str) -> dict[str, list[tuple]]:
    """Every player we hold stats for, keyed by normalised name.

    Drawn from the record itself rather than from a roster endpoint, and that is
    deliberate: a player we have no game log for cannot be forecast, so a prop
    about him has nothing to be a prop about. An unmatched September call-up is
    a correct refusal, not a gap to paper over.

    A list per key, because the whole point is to notice when there is more
    than one.
    """
    if sport != "mlb":
        raise ValueError(f"no crosswalk source declared for {sport!r}")

    out: dict[str, list[tuple]] = {}
    rows = list(
        conn.execute(
            "SELECT DISTINCT player_id AS pid, player_name AS name"
            " FROM mlb_batter_games WHERE player_name IS NOT NULL"
        )
    ) + list(
        conn.execute(
            "SELECT DISTINCT pitcher_id AS pid, pitcher_name AS name"
            " FROM mlb_probables WHERE pitcher_name IS NOT NULL"
        )
    )
    seen: set[int] = set()
    for row in rows:
        if row["pid"] in seen:
            continue
        seen.add(row["pid"])
        out.setdefault(normalise(row["name"]), []).append(
            (int(row["pid"]), row["name"])
        )
    return out


def _espn_name(conn: sqlite3.Connection, sport: str, espn_id: str) -> str | None:
    """One athlete's name. Cached permanently: a player's name does not change."""
    try:
        payload = json.loads(
            http.fetch(conn, athlete_url(sport, espn_id), immutable=True)
        )
    except (http.SourceUnavailable, json.JSONDecodeError):
        return None
    return payload.get("fullName") or payload.get("displayName")


def resolve(
    conn: sqlite3.Connection, sport: str, espn_ids: list[str], *, progress=None
) -> dict:
    """Match a slate's ESPN athlete ids onto our player ids, and record how.

    Returns the measured report. Every id ends up in `player_crosswalk` with one
    of four methods, including the two refusals — "we looked and could not tell"
    is a different fact from "we never looked", and only the first justifies
    skipping a prop.
    """
    index = our_players(conn, sport)
    now = utcnow()
    report = {
        "asked": len(espn_ids),
        "exact": 0,
        "normalised": 0,
        "refused_ambiguous": 0,
        "refused_unmatched": 0,
        "no_name": 0,
        "unmatched_names": [],
        "ambiguous_names": [],
        "measured_utc": now,
    }

    # Raw exact matching needs the raw names on our side too, not the folded
    # ones. Built once here so the exact rate is a real measurement rather than
    # a normalised match that happened to need no folding.
    raw_index: dict[str, list[tuple]] = {}
    for entries in index.values():
        for pid, name in entries:
            raw_index.setdefault(name, []).append((pid, name))

    for i, espn_id in enumerate(espn_ids):
        if progress and i % 25 == 0:
            progress(f"crosswalk {i}/{len(espn_ids)}")
        espn_name = _espn_name(conn, sport, espn_id)
        if not espn_name:
            report["no_name"] += 1
            _write(conn, sport, espn_id, "", None, None, "", "refused_unmatched",
                   "ESPN returned no name for this athlete id", now)
            continue

        key = normalise(espn_name)
        exact = raw_index.get(espn_name) or []
        candidates = index.get(key) or []

        if len(candidates) > 1:
            report["refused_ambiguous"] += 1
            report["ambiguous_names"].append(espn_name)
            _write(
                conn, sport, espn_id, espn_name, None, None, key,
                "refused_ambiguous",
                f"{len(candidates)} players normalise to {key!r}: "
                + ", ".join(f"{pid} {nm}" for pid, nm in candidates)
                + ". A prop about a name that could be two people is skipped.",
                now,
            )
            continue

        if not candidates:
            report["refused_unmatched"] += 1
            report["unmatched_names"].append(espn_name)
            _write(
                conn, sport, espn_id, espn_name, None, None, key,
                "refused_unmatched",
                "no player in the record normalises to this name; we hold no "
                "game log for him, so there is nothing to forecast",
                now,
            )
            continue

        pid, our_name = candidates[0]
        method = "exact" if len(exact) == 1 and exact[0][0] == pid else "normalised"
        report[method] += 1
        _write(conn, sport, espn_id, espn_name, pid, our_name, key, method,
               None, now)

    conn.commit()
    matched = report["exact"] + report["normalised"]
    report["matched"] = matched
    report["match_rate"] = round(matched / report["asked"], 4) if report["asked"] else None
    report["exact_rate"] = (
        round(report["exact"] / report["asked"], 4) if report["asked"] else None
    )
    # What the folding actually bought, as a count rather than a belief.
    report["normaliser_earned"] = report["normalised"]
    return report


def _write(conn, sport, espn_id, espn_name, source_id, source_name, key,
           method, reason, now) -> None:
    conn.execute(
        "INSERT INTO player_crosswalk (sport, espn_id, source_id, espn_name,"
        " source_name, normalised, method, reason, measured_utc)"
        " VALUES (?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(sport, espn_id) DO UPDATE SET source_id=excluded.source_id,"
        " espn_name=excluded.espn_name, source_name=excluded.source_name,"
        " normalised=excluded.normalised, method=excluded.method,"
        " reason=excluded.reason, measured_utc=excluded.measured_utc",
        (sport, str(espn_id), source_id, espn_name, source_name, key, method,
         reason, now),
    )


def lookup(conn: sqlite3.Connection, sport: str, espn_id: str) -> int | None:
    """Our player id for an ESPN athlete id, or None when it was refused."""
    row = conn.execute(
        "SELECT source_id FROM player_crosswalk WHERE sport = ? AND espn_id = ?",
        (sport, str(espn_id)),
    ).fetchone()
    return None if row is None else row["source_id"]


def refusals(conn: sqlite3.Connection, sport: str) -> list[sqlite3.Row]:
    """Every id we looked at and could not match, with the reason."""
    return list(
        conn.execute(
            "SELECT * FROM player_crosswalk WHERE sport = ? AND method LIKE 'refused_%'"
            " ORDER BY measured_utc DESC, espn_name",
            (sport,),
        )
    )
