# RESULTS_pick -- first or best?

```
  PART 1 -- DOES A CHOICE EVEN EXIST? (counts of what was quoted)

  gate-passing candidate rows      : 13984
  distinct scan seconds with one+  : 2507
  scan seconds offering 2+ MARKETS : 158  (6.3% of passes)

  markets passing in the same second:
     1 market(s) :   2349  ( 93.7%)
     2 market(s) :    144  (  5.7%)
     3 market(s) :     12  (  0.5%)
     4 market(s) :      1  (  0.0%)
     5 market(s) :      1  (  0.0%)

  when 2+ markets pass, the BEST-EDGE one is ALSO the first seen in 89 of 158 (56.3%)
  edge given up by taking the first, cents/contract:
    mean +2.10c   median +0.28c   p90 +7.43c   max +12.72c
    price paid is +2.21c higher on the first than on the best (mean)
```

```
  PART 3 -- SHOULD A SECOND BUY IN THE SAME MARKET BE ALLOWED?

  A second buy shares the first buy's outcome, so the only thing that
  matters is WHICH CLOSES offer one. Both groups below are markets the
  live gate would have bought once.

    no cheaper second ever appeared :   862 markets,    0 lost (  0.00%)
    a cheaper second DID appear     :   398 markets,   25 lost (  6.28%)

    difference: +6.28 pp, 95% CI [+3.46, +9.82] pp, bootstrapped over
    CLOSES (hard rule 4 -- twelve coins settle on one second at rho~0.8)

    Haldane-corrected loss odds ratio (second-available / not): 117.77x

  distinct closes involved: 738  (n is markets above, and markets are
  NOT independent within a close)

  how much cheaper the second buy was:
    drop      | markets | lost | loss rate | second leg, c/contract
    ----------|---------|------|-----------|-----------------------
    0.5-1c    |     142 |    1 |     0.70% |                 +3.08c
    1.0-2c    |     141 |    8 |     5.67% |                 -0.09c
    2.0-5c    |      87 |   10 |    11.49% |                 -4.92c
    5.0-10c   |      23 |    6 |    26.09% |                -11.45c
    10c+      |       1 |    0 |     0.00% |                +13.15c

  HOLDOUT -- split on close time at 1788658200:

  how much cheaper the second buy was, FIRST 60% of closes:
    drop      | markets | lost | loss rate | second leg, c/contract
    ----------|---------|------|-----------|-----------------------
    0.5-1c    |      86 |    0 |     0.00% |                 +3.75c
    1.0-2c    |      75 |    4 |     5.33% |                 +0.38c
    2.0-5c    |      54 |    3 |     5.56% |                 +0.77c
    5.0-10c   |      14 |    2 |    14.29% |                 -3.90c

  how much cheaper the second buy was, LAST 40% of closes (not fitted):
    drop      | markets | lost | loss rate | second leg, c/contract
    ----------|---------|------|-----------|-----------------------
    0.5-1c    |      56 |    1 |     1.79% |                 +2.06c
    1.0-2c    |      66 |    4 |     6.06% |                 -0.62c
    2.0-5c    |      33 |    7 |    21.21% |                -14.23c
    5.0-10c   |       9 |    4 |    44.44% |                -23.20c
    10c+      |       1 |    0 |     0.00% |                +13.15c
```

```
  PART 2 -- REPLAYED OUTCOME, 1 contract(s) per close
  (TAPE population, not ours -- direction only, never a P/L forecast)

  rule                 | closes | contracts |      P/L | c/contract | losses
  ---------------------|--------|-----------|----------|------------|-------
  first (LIVE today)   |    738 |       738 |   +15.27 |      +2.07 |    10
  best edge            |    738 |       738 |   +20.34 |      +2.76 |    10
  best edge per $      |    738 |       738 |   +20.34 |      +2.76 |    10
  highest confidence   |    738 |       738 |   +16.18 |      +2.19 |     9
  cheapest price       |    738 |       738 |   +20.34 |      +2.76 |    10
  deepest book         |    738 |       738 |   +13.18 |      +1.79 |    10
```

```
  PART 2 -- REPLAYED OUTCOME, 2 contract(s) per close
  (TAPE population, not ours -- direction only, never a P/L forecast)

  rule                 | closes | contracts |      P/L | c/contract | losses
  ---------------------|--------|-----------|----------|------------|-------
  first (LIVE today)   |    738 |      1070 |   +18.07 |      +1.69 |    20
  best edge            |    738 |      1072 |   +25.21 |      +2.35 |    20
  best edge per $      |    738 |      1072 |   +25.21 |      +2.35 |    20
  highest confidence   |    738 |      1073 |   +19.13 |      +1.78 |    19
  cheapest price       |    738 |      1073 |   +25.20 |      +2.35 |    20
  deepest book         |    738 |      1073 |   +14.60 |      +1.36 |    20
```

```
  PART 2 -- REPLAYED OUTCOME, 3 contract(s) per close
  (TAPE population, not ours -- direction only, never a P/L forecast)

  rule                 | closes | contracts |      P/L | c/contract | losses
  ---------------------|--------|-----------|----------|------------|-------
  first (LIVE today)   |    738 |      1189 |   +21.69 |      +1.82 |    22
  best edge            |    738 |      1189 |   +29.25 |      +2.46 |    22
  best edge per $      |    738 |      1189 |   +29.25 |      +2.46 |    22
  highest confidence   |    738 |      1194 |   +22.84 |      +1.91 |    21
  cheapest price       |    738 |      1191 |   +29.31 |      +2.46 |    22
  deepest book         |    738 |      1192 |   +17.36 |      +1.46 |    22
```

```
  PART 2 -- REPLAYED OUTCOME, 1 contract(s) per close, FIRST 60% of closes
  (TAPE population, not ours -- direction only, never a P/L forecast)

  rule                 | closes | contracts |      P/L | c/contract | losses
  ---------------------|--------|-----------|----------|------------|-------
  first (LIVE today)   |    442 |       442 |   +10.44 |      +2.36 |     4
  best edge            |    442 |       442 |   +13.16 |      +2.98 |     4
  best edge per $      |    442 |       442 |   +13.16 |      +2.98 |     4
  highest confidence   |    442 |       442 |   +11.39 |      +2.58 |     3
  cheapest price       |    442 |       442 |   +13.16 |      +2.98 |     4
  deepest book         |    442 |       442 |    +9.48 |      +2.15 |     4
```

```
  PART 2 -- REPLAYED OUTCOME, 1 contract(s) per close, LAST 40% of closes (not fitted)
  (TAPE population, not ours -- direction only, never a P/L forecast)

  rule                 | closes | contracts |      P/L | c/contract | losses
  ---------------------|--------|-----------|----------|------------|-------
  first (LIVE today)   |    296 |       296 |    +4.83 |      +1.63 |     6
  best edge            |    296 |       296 |    +7.18 |      +2.43 |     6
  best edge per $      |    296 |       296 |    +7.18 |      +2.43 |     6
  highest confidence   |    296 |       296 |    +4.79 |      +1.62 |     6
  cheapest price       |    296 |       296 |    +7.18 |      +2.43 |     6
  deepest book         |    296 |       296 |    +3.69 |      +1.25 |     6
```

