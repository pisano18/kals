# RESULTS_feed -- does our own index run ahead of the published one?

*`research/pinfeed.py`, 2026-09-13T12:01Z. Coin BTC. 1510258 seconds held in both feeds. Constituent exchange feeds and the published settlement index only -- no Kalshi order book, no replay, no fills, no P&L.*

## 1. Lead-lag correlation of one-second changes

A POSITIVE lag means the published feed moves LATER than ours -- we lead. Both feeds read the same exchanges, so the level of correlation proves nothing; only the ASYMMETRY across lags carries information.

| lag (s) | correlation | n |
|---|---|---|
| -5 | 0.0218 | 1509516 |
| -4 | 0.0229 | 1509602 |
| -3 | 0.0284 | 1509690 |
| -2 | 0.0537 | 1509793 |
| -1 | 0.2492 | 1509961 |
| +0 | 0.5851 | 1510074 |
| +1 | 0.0250 | 1509906 |
| +2 | -0.0022 | 1509786 |
| +3 | -0.0037 | 1509687 |
| +4 | 0.0034 | 1509598 |
| +5 | 0.0079 | 1509511 |

**Peak at lag +0 (r = 0.5851).**

## 2. Is it information, or just a differently-stamped clock?

If the two feeds carry the same content and differ only in the second they are stamped with, then our value IS their next value, the "gap" IS their next change, and regressing one on the other returns a slope of 1.0 with an r of 1.0 -- a tautology wearing a lead's clothes. A genuine partial lead, where the published feed closes only part of the gap each second, returns a slope strictly inside (0, 1) and an r well below 1.

**No lead.** slope -0.004, r -0.006, t = -6.9.

A one-second handicap on our own feed is reported in section 3 as a diagnostic. It is NOT a discriminator: a genuine one-second lead and a one-second timestamp offset both collapse under it, which is why the shape test above is the one that decides.

## 3. The gap regression -- the decisive one

Regress the published index's NEXT change on the CURRENT gap between our value and theirs. A noisy copy gives a slope of zero. A feed walking toward where we already are gives a positive slope, and the slope is the share of the gap that closes per second.

| horizon | slope | t | r | n |
|---|---|---|---|---|
| 1 s | -0.0041 | -6.9 | -0.0056 | 1510141 |
| 2 s | 0.0002 | 0.3 | 0.0002 | 1510051 |
| 5 s | 0.0042 | 3.1 | 0.0026 | 1509825 |
| 10 s | 0.0117 | 6.1 | 0.0050 | 1509474 |
| 30 s | 0.0069 | 2.1 | 0.0017 | 1508491 |

With the one-second clock handicap, the one-second slope is -0.0112 (t = -23.6) against -0.0041 (t = -6.9) without it.

**Nothing here is a trading rule and nothing here is a loss rate.** What a lead would buy is a fresher `spot` inside the model's own forecast, which is a better forecast at every tau and costs nothing to use. Whether that survives contact with our fills is a separate question this file does not touch.

