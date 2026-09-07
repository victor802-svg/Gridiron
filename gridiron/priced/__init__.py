"""The priced forecaster (THE_PRICED P1, 2026-09-07).

**A SECOND FORECASTER, NOT A REPLACEMENT, AND THE DIFFERENCE IS THE POINT.**

The blind forecaster writes its probability before any line is fetched. That is
LAW 1 and this package does not touch it: the blind path keeps its import
closure, its plantings and its guard tests, and it remains the only honest
measurement of whether this project can forecast at all.

This package is the other thing. It runs AFTER the blind row and the market
snapshot exist, it reads the price, and it says so on every row it writes. It
exists because a forecaster built to be well-calibrated is not the same object
as one built to make money: the second competes against a market's estimate of
reality rather than against reality, and it is the harder problem.

WHY BOTH, WRITTEN DOWN SO A LATER SESSION DOES NOT SIMPLIFY IT AWAY: a
forecaster that sees the price will beat a blind one at predicting outcomes and
will teach you nothing about your own skill, because most of what it knows it
read off the market. Keeping both means the project can answer "are we making
money?" and "are we any good?" separately. Collapsing them answers neither.

WHAT IT MAY READ that the blind path may not: the venue's price, the price
recorded when the prediction was written, and the movement between them.
`gridiron.priced` is therefore permitted to import `gridiron.market`, and that
permission is a NAMED EXCEPTION in `audit.CLOSURE_EXEMPT` rather than a
loosening of the rule -- the blind entrypoints are still scanned by name, and
`plant.py` proves the blind refusal still fires immediately after the
exception exists.

ITS SCORE IS NOT A BRIER SCORE. A priced forecaster with a worse Brier score
and a better closing line is succeeding, and the Record page has to be able to
say that without a reader thinking something has gone wrong.
"""
