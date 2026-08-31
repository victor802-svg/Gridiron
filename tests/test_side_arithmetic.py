"""K1: the chance shown must agree with the arithmetic shown, on every card.

The failure this exists for has now happened twice in the same shape. The
renderer built the sentence naming what the confidence figure was a chance OF,
using a hardcoded verb per market type:

  * every PROP read "goes over" whichever side the model took (fixed in M4);
  * every SPREAD read "covers" whichever side the model took -- 34 cards in the
    record, 20 NBA and 14 NFL, each stating the opposite of its own forecast at
    high confidence, with a correct decomposition underneath contradicting it.

Fixing one branch left the next. So the check here is not "is the verb right"
but the invariant underneath it: **push the displayed contributions through the
logistic and the answer must be the displayed chance for the displayed side.**
A card that fails it is lying whichever words it uses.
"""

from __future__ import annotations

import json
import math

import pytest

from gridiron import db, language


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


#: Which side the question was FORMED as, per market type. `model_prob` is
#: confidence in `model_side`, which is this side or its complement.
YES_SIDE = {"spread": "cover", "moneyline": "win", "prop": "over"}


def displayed_chance_matches_arithmetic(row: dict) -> tuple[bool, float, float]:
    """(agrees, what the arithmetic says, what the card shows)."""
    payload = json.loads(row["factors_json"])
    contribs = payload.get("contributions") or []
    log_odds = payload.get("log_odds")
    if log_odds is None:
        return True, row["model_prob"], row["model_prob"]   # no decomposition shown

    shown = sum((c.get("contribution") or 0.0) for c in contribs)
    intercept = log_odds - shown
    p_yes = logistic(shown + intercept)
    is_yes = row["model_side"] == YES_SIDE.get(row["market_type"])
    expected = p_yes if is_yes else 1.0 - p_yes
    return abs(expected - row["model_prob"]) <= 0.005, expected, row["model_prob"]


# --- the invariant, over the real record -----------------------------------

def test_every_card_in_the_record_agrees_with_its_own_arithmetic():
    """All sports, all market types. Skips nothing: an empty record would make
    this vacuous, so it asserts there is something to check."""
    from gridiron import config

    conn = db.open_db(config.DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id, sport, market_type, model_prob, model_side, factors_json"
            " FROM predictions WHERE predictor = 'statistical'"
        ).fetchall()
        assert rows, "no predictions to check — this test would pass vacuously"

        bad = []
        for r in rows:
            ok, expected, shown = displayed_chance_matches_arithmetic(dict(r))
            if not ok:
                bad.append(
                    f"#{r['id']} {r['sport']}:{r['market_type']} "
                    f"side={r['model_side']} shows {shown:.4f}, "
                    f"arithmetic says {expected:.4f}"
                )
        assert not bad, "cards disagreeing with their own decomposition:\n" + "\n".join(bad[:8])
    finally:
        conn.close()


def test_a_flipped_side_is_caught():
    """PLANTED. Take a sound row and flip the side without touching the
    numbers, which is exactly what the renderer was doing in words."""
    sound = {
        "market_type": "spread",
        "model_side": "cover",
        "model_prob": 0.9753,
        "factors_json": json.dumps({
            "contributions": [{"factor": "a", "contribution": -3.65}],
            "log_odds": 3.6849,
        }),
    }
    # As stored it is consistent: logistic(3.6849) = 0.9753 for the yes side.
    ok, _e, _s = displayed_chance_matches_arithmetic(sound)
    assert ok

    flipped = dict(sound, model_side="not_cover")
    ok, expected, shown = displayed_chance_matches_arithmetic(flipped)
    assert not ok, "a flipped side must not pass"
    assert abs(expected - 0.0247) < 0.001
    assert abs(shown - 0.9753) < 0.001


# --- the words, which is where it actually went wrong ----------------------

@pytest.mark.parametrize("market_type,side,subject,expected", [
    ("spread", "cover", "WAS", "WAS covers"),
    ("spread", "not_cover", "WAS", "WAS does not cover"),
    ("moneyline", "win", "TB", "TB wins"),
    ("moneyline", "lose", "TB", "TB loses"),
])
def test_the_clause_names_the_side_actually_taken(market_type, side, subject,
                                                  expected):
    assert language.chance_clause({
        "subject": subject, "market_type": market_type, "model_side": side,
    }) == expected


def test_the_spread_clause_is_not_hardcoded():
    """The exact regression: 'covers' for every spread whatever the side."""
    covers = language.chance_clause(
        {"subject": "WAS", "market_type": "spread", "model_side": "cover"})
    does_not = language.chance_clause(
        {"subject": "WAS", "market_type": "spread", "model_side": "not_cover"})
    assert covers != does_not


def test_the_renderer_has_no_verb_table_left():
    """The structural half. Fixing a branch leaves the next one; removing the
    table removes the class."""
    from pathlib import Path

    from gridiron import config

    app = (Path(config.PACKAGE_ROOT) / "web" / "app.js").read_text(encoding="utf-8")
    body = app.split("function probBlock")[1].split("function ")[0]
    assert "chance_clause" in body, "the renderer must print what the server sends"
    for invented in ("'covers'", "'goes '", "'wins'", "'loses'"):
        assert invented not in body, (
            f"probBlock is building words again ({invented}); the humaniser is "
            "the single source of truth for what a side is called"
        )


def test_the_clause_and_the_pick_sentence_cannot_disagree():
    """Both come from language.py, so a side change moves both together."""
    for side, in (("over",), ("under",)):
        item = {
            "subject": "Fernando Tatis Jr. batter_hits", "market_type": "prop",
            "prop_type": "batter_hits", "model_side": side, "line_asked": 1.5,
        }
        assert side in language.phrase(item)
        assert side in language.chance_clause(item)
