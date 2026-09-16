# WHEN -- hot and cold times for the pin

Written by `research/pinwhen.py`. One row per 15-minute close, 634 closes over 8 days, saved in `results/when_closes.jsonl`.

The bot bought on **303 of 634 closes (47.8%)**. 9 closes were dropped for overlapping a known outage (`results/DOWNTIME.json`).

**Before reading anything below:** with about 26 closes per hour of the day, only a gap of **38 percentage points or more** between two hours could be told apart from luck. Anything smaller is noise, however convincing it looks.


## Is it random?

| split | cells | widest gap | p (2,000 shuffles) | verdict |
|---|---|---|---|---|
| hour of day | 24 | 51 points | 0.043 | suggestive, not proven |
| 4-hour block | 6 | 26 points | 0.006 | **REAL, worth acting on** |
| day of week | 7 | 36 points | 0.000 | CANNOT BE READ -- only 2 week(s) on file, so each weekday is one or two particular days and a 'Tuesday effect' is just what the market happened to do that Tuesday |
| weekday vs weekend | 2 | 8 points | 0.051 | CANNOT BE READ -- only 2 week(s) on file, so each weekday is one or two particular days and a 'Tuesday effect' is just what the market happened to do that Tuesday |

## The clock against a real driver

Volatility is the obvious real driver: does the clock still matter once it is held still?

| volatility | closes | bought | p for 4-hour block inside it |
|---|---|---|---|
| calmest third | 210 | 56.7% | 0.319 |
| middle third | 210 | 52.4% | 0.283 |
| choppiest third | 210 | 34.8% | 0.616 |

And in five steps, calmest to choppiest:

| volatility | closes | bought |
|---|---|---|
| 1 of 5 | 126 | 59.5% |
| 2 of 5 | 126 | 54.8% |
| 3 of 5 | 126 | 51.6% |
| 4 of 5 | 126 | 42.9% |
| 5 of 5 | 126 | 31.0% |

Buying rate in the calmest third **56.7%** against the choppiest third **34.8%** -- a gap of 22 points where 14 points is the smallest this much data could show. **The clock splits above stop meaning anything once volatility is held still: the hours are not hot or cold, the CALM is.**

## The maps

`results/when_heatmap.html` -- one map per horizon (1, 3, 7, 14, 21, 30 days), each beside a shuffled twin. Open it in a browser.
