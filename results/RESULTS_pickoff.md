# RESULTS -- the offers we would buy, and who gets them

Rebuilt 2026-09-18 03:44Z from `research/pinpickoff.py`. TAPE population (rule 5):
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
  2026-09-08      81     41066      507.0   1854    39212         5% |        40s       95.3c |       1887921
  2026-09-09      45     56826     1262.8   4210    52616         7% |        44s       95.3c |       2355378
  2026-09-10      69     98350     1425.4   3856    94494         4% |        45s       95.2c |       4740909
  2026-09-11      73     82996     1136.9   8066    74930        10% |        40s       95.2c |       3313829
  2026-09-12      90    115612     1284.6   9733   105879         8% |        36s       95.1c |       3987095
  2026-09-13      75     46424      619.0   3141    43283         7% |        39s       95.2c |       1491489
  2026-09-14      89     54660      614.2   2414    52246         4% |        42s       95.3c |       2089651
  2026-09-15      84     57856      688.8   1703    56153         3% |        35s       95.0c |       2455447
  2026-09-16      92     51454      559.3   3201    48253         6% |        36s       95.4c |       2064556
  2026-09-17      72     35340      490.8   2851    32489         8% |        45s       95.1c |       1569959

  first 3 days vs last 3 days:
    bargains per close    280.0  ->   583.3
    our share                0%  ->      5%
    median tau taken        45s  ->     38s   (EARLIER means they are moving earlier)
    mean price            95.5c  ->   95.2c

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
