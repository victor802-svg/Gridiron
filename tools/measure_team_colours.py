"""Measure every club's colours, and whether white can be read on them.

WRITTEN FROM THE SOURCE THE TEAM NAMES ALREADY COME FROM. Every row in
`teams` carries a `source_url` into ESPN's API, and the same payload carries
`color` and `alternateColor`. Reading them there makes the palette a measured
datum with provenance rather than a list typed from memory -- which is the
difference this project draws everywhere else between a declaration and a
guess.

WHAT IS NOT TAKEN: the payload also carries `logos`. A club's logo is its
trademark, and GRIDIRON_THREE_STATES bans marks by name; `audit.check_no_marks`
refuses an image file in the team data directory so that a later session
cannot quietly add one.

CONTRAST IS MEASURED PER CLUB, because white on a club's primary is a
different pair for every club and some of them fail. Each club gets the colour
white can actually be read on:

  * the primary, when white on it clears WCAG AA for normal text;
  * else the alternate, when white on THAT clears it;
  * else the primary darkened until it does, recorded as darkened.

Run:  python tools/measure_team_colours.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

#: One request per sport, and the league path each one needs. The per-team
#: endpoint carries the same fields and would be 337 requests instead of 4.
LEAGUES = {
    "mlb": "baseball/mlb",
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "cfb": "football/college-football",
}
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/{path}/teams?limit=500"

#: WCAG AA for normal text. The card sets club names at the chip size, which is
#: normal text, so 4.5 is the bar rather than 3.
AA_NORMAL = 4.5


def _linear(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def ratio(one: str, two: str) -> float:
    a, b = luminance(one), luminance(two)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def darken(hex_colour: str, step: float = 0.9) -> str:
    value = hex_colour.lstrip("#")
    parts = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{max(0, int(p * step)):02x}" for p in parts)


def readable(primary: str, alternate: str | None) -> tuple[str, str]:
    """The colour white can be read on, and how it was arrived at."""
    if ratio("ffffff", primary) >= AA_NORMAL:
        return primary, "primary"
    if alternate and ratio("ffffff", alternate) >= AA_NORMAL:
        return alternate, "alternate"
    darker = primary
    for _ in range(12):
        darker = darken(darker)
        if ratio("ffffff", darker) >= AA_NORMAL:
            return darker, "darkened"
    return "000000", "black"


def fetch(sport: str) -> list[dict]:
    url = SOURCE.format(path=LEAGUES[sport])
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    out = []
    for entry in payload["sports"][0]["leagues"][0]["teams"]:
        team = entry["team"]
        primary = (team.get("color") or "").lower().lstrip("#")
        alternate = (team.get("alternateColor") or "").lower().lstrip("#")
        if len(primary) != 6:
            continue
        out.append({
            "abbrev": team.get("abbreviation") or "",
            "name": team.get("displayName") or "",
            "primary": primary,
            "alternate": alternate or None,
        })
    return out, url


def main() -> int:
    from gridiron import db

    conn = db.connect()
    known = {
        sport: {r["espn_abbrev"] or r["tricode"]: r["tricode"]
                for r in conn.execute(
                    "SELECT tricode, espn_abbrev FROM teams WHERE sport = ?",
                    (sport,))}
        for sport in LEAGUES
    }
    conn.close()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    blocks, report = [], []
    for sport in LEAGUES:
        teams, url = fetch(sport)
        rows, matched, darkened, alternates = [], 0, 0, 0
        for team in sorted(teams, key=lambda t: t["abbrev"]):
            tricode = known[sport].get(team["abbrev"])
            if tricode is None:
                continue
            matched += 1
            on_white, how = readable(team["primary"], team["alternate"])
            darkened += how == "darkened"
            alternates += how == "alternate"
            rows.append(
                f'    "{tricode}": ("{team["primary"]}", "{on_white}", "{how}"),'
                f'   # {team["name"]}')
        blocks.append(f'  "{sport}": {{\n' + "\n".join(rows) + "\n  },")
        report.append(f"{sport}: {matched} of {len(known[sport])} matched, "
                      f"{alternates} use the alternate, {darkened} darkened")
        print(report[-1])

    out = Path(REPO) / "gridiron" / "data" / "team_colours.py"
    out.write_text(
        '"""Every club\'s primary colour, and the shade white can be read on.\n'
        '\n'
        'GENERATED by tools/measure_team_colours.py -- do not hand-edit; re-run it.\n'
        f'Measured {stamp} from the source the team names themselves come from:\n'
        f'\n'
        f'    {SOURCE.format(path="<league>")}\n'
        '\n'
        'Each entry is (primary, on_white, how):\n'
        '\n'
        '  primary   the club\'s own colour, used for tints, rules and accents\n'
        '  on_white  the shade a WHITE name is set on, which is the primary\n'
        '            when white clears WCAG AA on it, the club\'s alternate when\n'
        '            that clears it instead, and the primary darkened until it\n'
        '            does otherwise\n'
        '  how       which of those three, so the fallback is a recorded fact\n'
        '            rather than a runtime guess\n'
        '\n'
        'NO MARKS. The same payload carries `logos`; a club\'s logo is its\n'
        'trademark and none is stored here or anywhere in this package.\n'
        f'{chr(34) * 3}\n'
        '\n'
        f'MEASURED_UTC = "{stamp}"\n'
        f'SOURCE = "{SOURCE}"\n'
        '\n'
        'TEAM_COLOURS: dict[str, dict[str, tuple[str, str, str]]] = {\n'
        + "\n".join(blocks) +
        '\n}\n',
        encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
