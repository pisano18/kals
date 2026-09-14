# RESULTS_early -- the winning side's price before the last 30 seconds

```
  THE WINNING SIDE'S PRICE, BY HOW LONG BEFORE THE CLOSE

  This is the cheapest the side that WON was ever offered at, in each
  band. The bot only looks at 0-30s today.

  seconds out | markets | median cheapest | p25    | p75    | under 95c
  ------------|---------|-----------------|--------|--------|----------
    0-10  s   |     261 |           99.6c |  97.9c |  99.9c |   47 (18.0%)
   10-20  s   |     687 |           99.7c |  97.6c |  99.8c |  131 (19.1%)
   20-30  s   |    1000 |           99.5c |  96.0c |  99.8c |  238 (23.8%)
   30-40  s   |    1413 |           99.4c |  94.7c |  99.8c |  365 (25.8%)
   40-50  s   |    1889 |           99.4c |  93.9c |  99.8c |  517 (27.4%)
   50-60  s   |    2200 |           99.0c |  91.4c |  99.8c |  667 (30.3%)

  ANYWHERE in the final minute: 2215 markets, median cheapest 99.0c, and 679 (30.7%) touched 95c or better.

  Every price here is a QUOTE, not a fill. We would have been racing
  for it, and the tape's population is not ours (CLAUDE.md rule 5).
  Treat all of it as the best case.
```
