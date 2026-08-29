"""One thing we are about to be wrong or right about.

Lives in its own module so a sport adapter can describe a question without
importing the prediction loop, and so the loop can accept questions from any
sport without importing every sport.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Question:
    sport: str
    game_id: str
    #: The storage bucket: 'spread', 'moneyline' or 'prop'.
    market_type: str
    #: The scoring category: 'spread', 'moneyline', 'points', 'receptions', ...
    #: Every market is its own curve and its own gate (LAW 4, LAW 6).
    market: str
    subject: str
    #: The line OUR question is about. Never the market's price.
    line_asked: float | None
    claim: str
    yes_label: str
    no_label: str
    player_id: str | None = None
    stat: str | None = None

    @property
    def market_key(self) -> str:
        """Which fitted model answers this question."""
        if self.market_type == "prop":
            return f"{self.sport}:prop:{self.stat}"
        return f"{self.sport}:{self.market_type}"
