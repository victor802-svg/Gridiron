"""ESPN posts `spread: 0` on a baseball game before the run line exists."""
from __future__ import annotations

from gridiron import audit
from gridiron.market import espn


def test_a_zero_run_line_is_an_absence_not_a_pickem():
    assert espn._home_spread({"spread": 0}, "mlb") is None
    assert espn._home_spread({"spread": 0.0}, "mlb") is None
    assert espn._home_spread({"spread": -1.5}, "mlb") == 1.5
    # Football and basketball can genuinely be a pick'em.
    assert espn._home_spread({"spread": 0}, "nfl") == 0.0
    assert espn._home_spread({"spread": 0}, "nba") == 0.0


def test_the_sign_check_does_not_read_a_placeholder_as_a_contradiction():
    rows = [{"game_id": "mlb_p", "spread_line": 0.0,
             "home_moneyline": -189, "away_moneyline": 155}]
    assert audit.run_line_sign_faults(rows) == []
    assert audit.run_line_sign_faults(audit.RUN_LINE_FIXTURE_CONTRADICTED)
