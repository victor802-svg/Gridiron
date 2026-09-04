GRIDIRON_18 SESSION C — COUNT WHAT COUNTS.

THE CAUSAL CLAIM, stated before anything changes: passing touchdowns
are overconfident by 12.4 points in every bucket (98 resolved). They
are a small-count event forecast by a logistic built for continuous
yardage. Home runs and strikeouts are the same shape. A count is
honestly modelled as a RATE: predict the expected count, then the
probability of clearing a rung follows from the distribution.

 C1 For passing TDs, home runs, strikeouts (and any roster market
    that is a count): a Poisson-rate forecaster — factors predict the
    expected count (log link), P(over rung) = 1 − CDF(rung). Declared
    model-form change per market, dated, own factor-set version for
    those markets only. Where measured dispersion materially exceeds
    Poisson (report it), negative binomial with the measured
    dispersion, dated.
 C2 Walk-forward sanity per market: calibration by bucket old vs
    new, labelled sanity-only. IF THE RATE FORM IS NOT BETTER
    CALIBRATED IN THE WALK-FORWARD, DO NOT SHIP IT — say so. The
    causal claim must survive its own test.
 C3 "Why" for count markets speaks the rate: "the model expects about
    0.9 home runs; clearing 0.5 is about 60%."
 C4 Plantings: a count market scored by the logistic path; a rung
    probability that does not fall as the rung rises. Full suite,
    verify.py, /closeout, push.

Contract: unattended; never stop to ask; forks by law, precedent, then
the conservative default, recorded under "Rulings taken in your
absence"; operator-only decisions BLOCKED and skipped; commit +
verified push at every phase boundary; a complete item beats a
half-built one; gate, renders and /closeout per item.
