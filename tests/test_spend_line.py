"""The spend line shows cents (UI audit finding 23, 2026-09-05): "$0.0000 of
$2.00" was four decimals of nothing beside a cap in cents."""
from __future__ import annotations

from gridiron import language


def test_the_spend_line_is_in_cents():
    line = language.colophon({
        "predictions": 0, "seasons_loaded": [], "games_final": 0,
        "market_coverage": {}, "llm_ledger": {"usd_spent": 0, "usd_cap": 2},
    })
    assert "LLM spend today $0.00 of $2.00" in line
    assert "$0.0000" not in line
    line = language.colophon({
        "predictions": 0, "seasons_loaded": [], "games_final": 0,
        "market_coverage": {}, "llm_ledger": {"usd_spent": 0.1234, "usd_cap": 2},
    })
    assert "$0.12 of $2.00" in line
