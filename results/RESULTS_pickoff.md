# RESULTS -- the offers we would buy, and who gets them

Rebuilt 2026-09-18 02:02Z from `research/pinpickoff.py`. TAPE population (rule 5):
what the market did, never our loss rate.

```
THE OFFERS WE WOULD BUY, AND WHO GOT THEM
  A 'bargain' = any taker buying the WINNING side at 90-98c within 60s of the close.
  TAPE POPULATION -- what the market did. Not our loss rate (rule 5).

  day         closes  bargains  per close   ours   theirs  our share | median tau  mean price | contracts theirs
  2026-08-25      65     13417      206.4      0    13417         0% |        49s       95.6c |        725173
  2026-08-26      14      6380      455.7      0     6380         0% |        42s       95.5c |        320157
  2026-08-27      62     19689      317.6      0    19689         0% |        45s       95.4c |       1117742
  2026-08-28      70     26377      376.8      0    26377         0% |        38s       95.1c |       1337571
  2026-08-29      81     38000      469.1      0    38000         0% |        43s       95.3c |       2001784
  2026-08-30      67     20342      303.6      0    20342         0% |        44s       95.7c |        967686
  2026-08-31      69     29930      433.8      0    29930         0% |        42s       95.3c |       1694215
  2026-09-01      67     28107      419.5      0    28107         0% |        43s       95.1c |       1515578
  2026-09-02      59     26427      447.9      0    26427         0% |        43s       95.7c |       1559337
  2026-09-03      63     24717      392.3      0    24717         0% |        44s       95.4c |       1509805
  2026-09-04      74     35402      478.4      0    35402         0% |        39s       95.3c |       1920946
  2026-09-05      90     53290      592.1      0    53290         0% |        38s       95.3c |       2780532
  2026-09-06      80     36208      452.6      0    36208         0% |        40s       95.3c |       1688876
  2026-09-07      73     31817      435.8      0    31817         0% |        42s       95.5c |       1495370
  2026-09-08      81     35283      435.6   1737    33546         5% |        38s       95.3c |       1659228
  2026-09-09      45     28413      631.4   2105    26308         7% |        44s       95.3c |       1177689
  2026-09-10      69     49175      712.7   1928    47247         4% |        45s       95.2c |       2370454
  2026-09-11      73     41498      568.5   4033    37465        10% |        40s       95.2c |       1656915
  2026-09-12      53     38952      734.9   3570    35382         9% |        35s       95.1c |       1254541

  first 3 days vs last 3 days:
    bargains per close    280.0  ->   664.7
    our share                0%  ->      7%
    median tau taken        45s  ->     41s   (EARLIER means they are moving earlier)
    mean price            95.5c  ->   95.1c

  HOW TO READ 'our share': one of our orders prints as MANY tape trades
  (it sweeps several resting orders), and the join accepts any print
  within 6 s and 1c of one of our fills. The share is an UPPER bound on
  the slice we take. Use the TREND and the pool size, not the level.

  REVISIT THIS ONCE IT HAS TWO MORE WEEKS IN IT. Three things to act on:
    1. median tau falling  -> competitors are moving earlier; widen our own early
       window (AMENDMENT 46 is at 45s) or accept a thinner edge sooner.
    2. our share falling while bargains per close holds -> we are losing RACES,
       not opportunities; the answer is latency and the sweep, not the gates.
    3. bargains per close falling -> the pool itself is drying up; that is the
       one that argues for a second product rather than a better bot.
```
