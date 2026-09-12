# RESULTS_coin -- is one coin's index structurally jumpier?

```

==============================================================================
  1. ONE-SECOND JUMP TAIL, per coin, against the coin's OWN trailing-300s sigma
     826 closes, 7,632 markets, 6,673,899 coin-seconds scored

  coin        sec/coin      k>3      k>4      k>5      k>6      k>8        (rate per 10,000 seconds)
  KXBNB15M     741,545    245.3    127.0     71.9     43.4     19.0
  KXBTC15M     741,543    239.8    123.6     68.4     42.7     20.3
  KXDOGE15M    741,547    202.8    104.3     61.8     40.8     22.1
  KXETH15M     741,545    221.4    101.9     52.9     31.9     14.0
  KXHYPE15M    741,546    203.3    107.7     65.3     43.6     22.9
  KXNEAR15M    741,544    238.1    130.9     79.6     51.7     23.1
  KXSOL15M     741,543    178.5     77.9     41.3     25.6     12.9
  KXXRP15M     741,541    205.0    101.9     59.4     39.2     21.1
  KXZEC15M     741,545    185.7     99.6     62.6     42.7     23.5

  Gaussian expectation, per 10,000 s: k>3 27.0, k>4 0.633, k>5 0.0057, k>6 0.0000, k>8 0.0000
  -- every coin is orders of magnitude above it at k>=5, which is the excess kurtosis
     the RUNBOOK already records. The question here is only whether the coins DIFFER.

  Coin vs the pool of the other 8, clustered on the close (826 clusters).
  MULTIPLE LOOKS: 45 cells, so the threshold is |z| > 3.26, not 1.96.

  coin             k>3       k>4       k>5       k>6       k>8     (z)
  KXBNB15M       18.35     17.27     11.66      5.23     -2.27
  KXBTC15M       16.78     13.36      6.92      3.79      0.92
  KXDOGE15M      -7.20     -4.42     -1.21      1.13      6.03
  KXETH15M        5.55     -6.88    -14.05    -15.90    -19.08
  KXHYPE15M      -5.95     -0.60      3.28      5.23      6.92
  KXNEAR15M      13.90     19.76     19.87     16.88      6.68
  KXSOL15M      -20.42    -34.39    -35.21    -31.82    -22.56
  KXXRP15M       -5.74     -7.20     -5.06     -1.88      3.52
  KXZEC15M      -17.00     -7.88     -0.03      4.20      8.09

  Restricted to the LAST 60 SECONDS before each close -- the settlement window, where
  the bot actually lives and where a jump moves the locked average least but the
  remaining-print projection most:

  coin        sec/coin      k>3      k>4      k>5      k>6      k>8
  KXBNB15M      49,403    230.4    123.3     69.6     39.9     15.6
  KXBTC15M      49,400    207.5    108.7     58.3     36.4     18.6
  KXDOGE15M     49,403    170.6     92.1     55.9     38.1     21.1
  KXETH15M      49,403    186.4     86.6     46.2     28.5     14.2
  KXHYPE15M     49,401    189.3    102.0     63.6     45.1     24.7
  KXNEAR15M     49,400    223.1    128.1     77.1     50.0     22.7
  KXSOL15M      49,400    151.6     69.6     40.5     25.7     13.2
  KXXRP15M      49,399    168.8     83.6     49.8     31.0     19.6
  KXZEC15M      49,402    166.0     94.3     59.7     40.1     22.3

  Largest single one-second move ever printed by each feed, in units of that feed's
  own trailing sigma one second earlier -- the event the 99.5% gate has to survive:

  coin        max |move|/sigma            when (UTC)
  KXBNB15M                76.0   2026-09-06T01:18:38Z
  KXBTC15M                39.4   2026-09-05T02:27:50Z
  KXDOGE15M               65.2   2026-09-05T02:50:11Z
  KXETH15M                54.5   2026-09-04T08:46:12Z
  KXHYPE15M               65.1   2026-09-06T16:42:14Z
  KXNEAR15M               42.3   2026-09-07T12:36:37Z
  KXSOL15M                31.5   2026-09-12T02:59:49Z
  KXXRP15M                65.5   2026-09-05T07:43:40Z
  KXZEC15M               128.1   2026-09-06T11:25:43Z

  ARTEFACT GUARD -- QUANTIZATION. The feeds are quoted to a fixed number of decimals.
  A coin whose one-second sd is only a few quotation steps has a LUMPY move distribution,
  and lumpiness reads as a fat tail in any k-sigma statistic. Read this table BEFORE
  believing any difference above: a coin with sigma/step below ~5 is not comparable.

  coin        zero-move s    quote step   mean sigma  sigma/step
  KXBNB15M           8.2%     0.0010000    0.0419034        41.9
  KXBTC15M           0.5%     0.0100000    3.8248904       382.5
  KXDOGE15M         19.6%     0.0000010    0.0000082         8.2
  KXETH15M           9.7%     0.0100000    0.1435596        14.4
  KXHYPE15M          3.8%     0.0001000    0.0065876        65.9
  KXNEAR15M         37.4%     0.0001000    0.0004274         4.3
  KXSOL15M          69.6%     0.0100000    0.0081722         0.8
  KXXRP15M          15.5%     0.0000100    0.0001038        10.4
  KXZEC15M           0.1%     0.0001000    0.1923815      1923.8

==============================================================================
  2/3. GATE ENTRIES -- first second with tau <= 30 where the model crosses 0.995
     7,266 entries = 7,266 markets over 808 closes. ONE ENTRY PER MARKET.

  *** THESE ARE NOT OUR BETS AND THIS IS NOT OUR LOSS RATE. ***
  The tape's population is 'the model crossed the gate'. Ours is 'someone actively
  sold it to us', which is adversely selected and runs ~31x worse (CLAUDE.md,
  AMENDMENT 2026-09-10 rule 5). These numbers RANK COINS AGAINST EACH OTHER. Nothing
  else may be read off them.

  MDE STATED BEFORE THE ESTIMATE. Two-sided 5% Bonferroni'd over 9 coins, 80% power,
  coin vs pool, at the pooled rates below:

  coin        n mkts   flip MDE  = x pool   collapse MDE  = x pool
  KXBNB15M       808      0.65%      2.8x          0.95%      1.9x
  KXBTC15M       808      0.65%      2.8x          0.95%      1.9x
  KXDOGE15M      808      0.65%      2.8x          0.95%      1.9x
  KXETH15M       806      0.65%      2.8x          0.95%      1.9x
  KXHYPE15M      808      0.65%      2.8x          0.95%      1.9x
  KXNEAR15M      808      0.65%      2.8x          0.95%      1.9x
  KXSOL15M       807      0.65%      2.8x          0.95%      1.9x
  KXXRP15M       806      0.65%      2.8x          0.95%      1.9x
  KXZEC15M       807      0.65%      2.8x          0.95%      1.9x

  Read that column first: with ~807 entries per coin nothing short of a
  3x difference in flip rate is detectable. A coin that is genuinely twice as
  dangerous would NOT show up. 'No effect' and 'no power' are different results.

  FULL WINDOW (9 days)
  coin        mkts  closes  entry tau  collapse            95% CI    flip            95% CI    z col   z flip
  KXBNB15M     808     808       28.8     0.87%      [0.3%, 1.8%]   0.12%      [0.0%, 0.7%]     1.32    -1.71
  KXBTC15M     808     808       28.8     0.37%      [0.1%, 1.1%]   0.12%      [0.0%, 0.7%]    -0.58    -0.83
  KXDOGE15M    808     808       28.9     0.50%      [0.1%, 1.3%]   0.37%      [0.1%, 1.1%]    -0.00     0.82
  KXETH15M     806     806       28.7     0.25%      [0.0%, 0.9%]   0.12%      [0.0%, 0.7%]    -1.35    -0.75
  KXHYPE15M    808     808       29.4     0.74%      [0.3%, 1.6%]   0.37%      [0.1%, 1.1%]     0.95     0.82
  KXNEAR15M    808     808       29.3     0.37%      [0.1%, 1.1%]   0.25%      [0.0%, 0.9%]    -0.69     0.11
  KXSOL15M     807     807       28.7     0.37%      [0.1%, 1.1%]   0.25%      [0.0%, 0.9%]    -0.73     0.12
  KXXRP15M     806     806       29.1     0.62%      [0.2%, 1.4%]   0.37%      [0.1%, 1.1%]     0.54     0.82
  KXZEC15M     807     807       29.1     0.37%      [0.1%, 1.1%]   0.12%      [0.0%, 0.7%]    -0.56    -0.76
  POOL       7,266     808       29.0     0.50%                     0.23%

  FIT HALF -- closes up to 09-08T04:45Z
  coin        mkts  closes  entry tau  collapse            95% CI    flip            95% CI    z col   z flip
  KXBNB15M     464     464       29.0     0.86%      [0.2%, 2.2%]   0.00%      [0.0%, 0.8%]     1.16    -2.25
  KXBTC15M     464     464       29.0     0.43%      [0.1%, 1.5%]   0.00%      [0.0%, 0.8%]     0.08    -2.25
  KXDOGE15M    464     464       28.9     0.43%      [0.1%, 1.5%]   0.22%      [0.0%, 1.2%]     0.08     0.48
  KXETH15M     462     462       28.6     0.22%      [0.0%, 1.2%]   0.00%      [0.0%, 0.8%]    -0.89    -2.25
  KXHYPE15M    464     464       29.4     0.86%      [0.2%, 2.2%]   0.43%      [0.1%, 1.5%]     1.16     1.14
  KXNEAR15M    464     464       29.4     0.22%      [0.0%, 1.2%]   0.00%      [0.0%, 0.8%]    -0.90    -2.25
  KXSOL15M     463     463       28.6     0.00%      [0.0%, 0.8%]   0.00%      [0.0%, 0.8%]    -4.20    -2.25
  KXXRP15M     464     464       29.2     0.43%      [0.1%, 1.5%]   0.22%      [0.0%, 1.2%]     0.08     0.48
  KXZEC15M     464     464       29.1     0.22%      [0.0%, 1.2%]   0.22%      [0.0%, 1.2%]    -0.90     0.48
  POOL       4,173     464       29.0     0.41%                     0.12%

  HOLDOUT -- closes after 09-08T04:45Z (NOT looked at when the hypothesis was formed)
  coin        mkts  closes  entry tau  collapse            95% CI    flip            95% CI    z col   z flip
  KXBNB15M     344     344       28.5     0.87%      [0.2%, 2.5%]   0.29%      [0.0%, 1.6%]     0.65    -0.73
  KXBTC15M     344     344       28.6     0.29%      [0.0%, 1.6%]   0.29%      [0.0%, 1.6%]    -1.01    -0.32
  KXDOGE15M    344     344       28.8     0.58%      [0.1%, 2.1%]   0.58%      [0.1%, 2.1%]    -0.11     0.67
  KXETH15M     344     344       28.8     0.29%      [0.0%, 1.6%]   0.29%      [0.0%, 1.6%]    -1.01    -0.29
  KXHYPE15M    344     344       29.3     0.58%      [0.1%, 2.1%]   0.29%      [0.0%, 1.6%]    -0.11    -0.73
  KXNEAR15M    344     344       29.1     0.58%      [0.1%, 2.1%]   0.58%      [0.1%, 2.1%]    -0.11     0.67
  KXSOL15M     344     344       28.8     0.87%      [0.2%, 2.5%]   0.58%      [0.1%, 2.1%]     0.69     0.76
  KXXRP15M     342     342       29.1     0.88%      [0.2%, 2.5%]   0.58%      [0.1%, 2.1%]     0.70     0.68
  KXZEC15M     343     343       29.2     0.58%      [0.1%, 2.1%]   0.00%      [0.0%, 1.1%]    -0.07    -1.82
  POOL       3,093     344       28.9     0.61%                     0.39%

  Multiple looks on 9 coins: |z| > 2.77.
  Entries with no post-entry second (entered at tau 3) and therefore no collapse observation: 12 of 7,266

  GUARD NULL -- what the scan threw away, per coin (a guard that discards everything
  looks exactly like a thin tape, so it prints its own cost):
    KXBNB15M   29 no_sigma, 271 no_tick
    KXBTC15M   29 no_sigma, 273 no_tick
    KXDOGE15M  29 no_sigma, 269 no_tick
    KXETH15M   29 no_sigma, 271 no_tick
    KXHYPE15M  29 no_sigma, 270 no_tick
    KXNEAR15M  28 no_sigma, 273 no_tick
    KXSOL15M   29 no_sigma, 273 no_tick
    KXXRP15M   28 no_sigma, 276 no_tick
    KXZEC15M   29 no_sigma, 271 no_tick

  ARTEFACT GUARD -- IS THE ENTRY POPULATION THE SAME? A coin can look more dangerous
  simply because its gate entries carry less margin or arrive later. If these columns
  match across coins, a difference in the tables above is about the INDEX, not selection.

  coin            n  mean tau_in  median margin sd  saturated
  KXBNB15M      808         28.8              7.03      77.2%
  KXBTC15M      808         28.8              7.03      72.9%
  KXDOGE15M     808         28.9              7.03      79.1%
  KXETH15M      806         28.7              7.03      76.9%
  KXHYPE15M     808         29.4              7.03      84.5%
  KXNEAR15M     808         29.3              7.03      82.2%
  KXSOL15M      807         28.7              7.03      76.3%
  KXXRP15M      806         29.1              7.03      78.9%
  KXZEC15M      807         29.1              7.03      82.9%

  STABILITY ACROSS THE SPLIT (collapse rate, the statistic with enough events to move):
  coin        fit n  fit col  hold n  hold col    sign held?
  KXBNB15M      464    0.86%     344     0.87%           yes
  KXBTC15M      464    0.43%     344     0.29%            NO
  KXDOGE15M     464    0.43%     344     0.58%            NO
  KXETH15M      462    0.22%     344     0.29%           yes
  KXHYPE15M     464    0.86%     344     0.58%            NO
  KXNEAR15M     464    0.22%     344     0.58%           yes
  KXSOL15M      463    0.00%     344     0.87%            NO
  KXXRP15M      464    0.43%     342     0.88%           yes
  KXZEC15M      464    0.22%     343     0.58%           yes

==============================================================================
  4. OUR OWN LIVE FILLS -- the ONLY valid source for OUR loss rate
==============================================================================
  189 settled fills, 185 distinct markets/closes, 2026-09-08T08:00:20Z .. 2026-09-12T10:00:35Z

  *** THE FIRST CORRECTION IS A COUNTING ONE, AND IT MOVES THE ANSWER. ***
  11 losing FILLS sit on 9 losing MARKETS. The multiply-filled ones:
    KXNEAR15M-26SEP082045-45           3 fills, ONE close, ONE outcome (paid 0.962, 0.956, 0.73)
  Hundreds of fills can share one settlement, so `n` is markets and closes, never
  fills (CLAUDE.md hard rule 4). Counting fills is what turns one NEAR close into
  'three NEAR losses'.

  ALL live runs: 189 fills -> 185 closes, 9 losing closes (4.9%)
  coin          closes  lost    rate      95% CI (Clopper-Pearson)     P(>= this|one rate)
  KXSOL15M          24     4   16.7%                 [4.7%, 37.4%]                  0.0178
  KXXRP15M          28     1    3.6%                 [0.1%, 18.3%]                  0.7797
  KXBNB15M          21     1    4.8%                 [0.1%, 23.8%]                  0.6705
  KXDOGE15M         19     1    5.3%                 [0.1%, 26.0%]                  0.6315
  KXNEAR15M         16     1    6.2%                 [0.2%, 30.2%]                  0.5653
  KXETH15M          15     1    6.7%                 [0.2%, 31.9%]                  0.5410
  KXBTC15M          33     0    0.0%                 [0.0%, 10.6%]                        
  KXHYPE15M         18     0    0.0%                 [0.0%, 18.5%]                        
  KXZEC15M          11     0    0.0%                 [0.0%, 28.5%]                        
  ONE SHARED LOSS RATE for every coin: the chance the WORST coin still reaches
  4 losing closes is p = 0.1358 (9 losses over 185 closes, 200,000 random deals,
  max-per-coin-count statistic). The max is what pays for having noticed the coin
  AFTER the fact; a per-coin p-value would not.
  MDE at this live size: 18.3% against a base of 4.9% -- only a coin
  4x the pool rate is detectable, so 'no effect' and 'no power' are not distinguishable here.

  CURRENT GATE ONLY (pin = 0.995): 107 fills -> 105 closes, 6 losing closes (5.7%)
  coin          closes  lost    rate      95% CI (Clopper-Pearson)     P(>= this|one rate)
  KXSOL15M          15     4   26.7%                 [7.8%, 55.1%]                  0.0036
  KXETH15M           7     1   14.3%                 [0.4%, 57.9%]                  0.3459
  KXDOGE15M          7     1   14.3%                 [0.4%, 57.9%]                  0.3459
  KXBTC15M          21     0    0.0%                 [0.0%, 16.1%]                        
  KXXRP15M          18     0    0.0%                 [0.0%, 18.5%]                        
  KXBNB15M          13     0    0.0%                 [0.0%, 24.7%]                        
  KXHYPE15M         10     0    0.0%                 [0.0%, 30.8%]                        
  KXNEAR15M          8     0    0.0%                 [0.0%, 36.9%]                        
  KXZEC15M           6     0    0.0%                 [0.0%, 45.9%]                        
  ONE SHARED LOSS RATE for every coin: the chance the WORST coin still reaches
  4 losing closes is p = 0.0285 (6 losses over 105 closes, 200,000 random deals,
  max-per-coin-count statistic). The max is what pays for having noticed the coin
  AFTER the fact; a per-coin p-value would not.
  MDE at this live size: 26.6% against a base of 5.7% -- only a coin
  5x the pool rate is detectable, so 'no effect' and 'no power' are not distinguishable here.

  THE LOSS SEQUENCE THE OPERATOR ASKED ABOUT, oldest first:
    2026-09-09T00:45:20Z  KXNEAR15M-26SEP082045-45           gate 0.98  paid 0.962  -1929c
    2026-09-09T00:45:35Z  KXNEAR15M-26SEP082045-45           gate 0.98  paid 0.956  -1918c
    2026-09-09T00:45:50Z  KXNEAR15M-26SEP082045-45           gate 0.98  paid 0.73  -1413c
    2026-09-10T05:00:20Z  KXXRP15M-26SEP100100-00            gate 0.98  paid 0.82  -1661c
    2026-09-10T05:30:20Z  KXBNB15M-26SEP100130-30            gate 0.98  paid 0.94  -1760c
    2026-09-10T22:15:20Z  KXDOGE15M-26SEP101815-15           gate 0.995  paid 0.0998  -212c
    2026-09-11T12:30:20Z  KXSOL15M-26SEP110830-30            gate 0.995  paid 0.591  -1216c
    2026-09-12T03:00:20Z  KXSOL15M-26SEP112300-00            gate 0.995  paid 0.979  -1961c
    2026-09-12T08:00:20Z  KXSOL15M-26SEP120400-00            gate 0.995  paid 0.94  -1888c
    2026-09-12T09:45:20Z  KXETH15M-26SEP120545-45            gate 0.995  paid 0.003  -0c
    2026-09-12T10:00:20Z  KXSOL15M-26SEP120600-00            gate 0.995  paid 0.052  -6c

  The last three losses at the current gate are KXSOL15M, KXETH15M, KXSOL15M.
  GIVEN that the 6 losses fell on the coins they did, the chance the three most
  recent all share ONE coin is 20.0%. So the 'three in a row' framing
  adds essentially nothing beyond the count itself -- the evidence is the table
  above, not the ordering.

==============================================================================
  5. SCALE AUDIT -- is the ONE-SECOND sigma that fair() projects from the right scale?
==============================================================================
  sd of index differences at lag L, divided by sqrt(L), so a random walk gives the
  same number in every column. Divergence at lag 1 means the one-second sigma the
  bot feeds into fair() is not the feed's diffusion.

  coin              level       step  zero-1s         sd1    sd10/r10    sd30/r30    sd60/r60   sd1/sd60
  KXBNB15M       735.5297  0.0010000     8.2%   0.0488976   0.0499061   0.0516827   0.0534034      0.916
  KXBTC15M     78999.7361  0.0100000     0.5%   4.6113855   4.7711797   4.7609186   4.7784226      0.965
  KXDOGE15M        0.0875  0.0000010    19.7%   0.0000101   0.0000108   0.0000109   0.0000110      0.921
  KXETH15M      2482.6364  0.0100000     9.7%   0.1756470   0.1974216   0.2019538   0.2057953      0.854
  KXHYPE15M       84.3046  0.0001000     3.8%   0.0074636   0.0083984   0.0090452   0.0094125      0.793
  KXNEAR15M        2.2909  0.0001000    37.4%   0.0004818   0.0005017   0.0005258   0.0005363      0.898
  KXSOL15M       102.9693  0.0100000    69.6%   0.0090923   0.0097839   0.0099751   0.0101134      0.899
  KXXRP15M         1.4004  0.0000100    15.5%   0.0001238   0.0001455   0.0001506   0.0001533      0.808
  KXZEC15M      1107.1717  0.0001000     0.1%   0.2361463   0.2608832   0.2597940   0.2628005      0.899

  sd1/sd60 > 1: the bot's sigma is TOO BIG, fair() is pulled toward 50c, and the
                99.5% gate is HARDER to reach -- conservative.
  sd1/sd60 < 1: the bot's sigma is TOO SMALL, fair() is pushed toward 0/100c, and
                the gate fires on thinner evidence -- OVERCONFIDENT.

  Same numbers as a multiple of each feed's quote step, which is the quantity that
  decides whether the grid can distort the one-second estimate at all:

  coin         sigma_1s/step  60s move/step    sd1/sd60    comparable?
  KXBNB15M              48.9          413.7       0.916            yes
  KXBTC15M             461.1         3701.4       0.965            yes
  KXDOGE15M             10.1           85.3       0.921            yes
  KXETH15M              17.6          159.4       0.854            yes
  KXHYPE15M             74.6          729.1       0.793            yes
  KXNEAR15M              4.8           41.5       0.898       MARGINAL
  KXSOL15M               0.9            7.8       0.899             NO
  KXXRP15M              12.4          118.7       0.808            yes
  KXZEC15M            2361.5        20356.4       0.899            yes

  'comparable?' is about SECTION 1 only: a coin whose one-second sigma is under a
  few quote steps has a lumpy one-second move distribution, so its k-sigma
  exceedance RATE cannot be compared with a finely-quoted coin's in either
  direction. It does NOT mean the coin is safe or unsafe -- that is the sd1/sd60
  column's job.

==============================================================================
  6. OUR OWN LOSING CLOSES, RECONSTRUCTED ON THE INDEX -- with a base rate
==============================================================================
  9 losing closes in our own fill log. For each, the largest one-second
  index move in the final 60 s, in units of that feed's own sigma one second earlier.

  market                            close (UTC)            max |move|/sigma   at tau   result
  KXBNB15M-26SEP100130-30           2026-09-10T05:30:00Z                5.4       24       no
  KXDOGE15M-26SEP101815-15          2026-09-10T22:15:00Z               20.0       10      yes
  KXNEAR15M-26SEP082045-45          2026-09-09T00:45:00Z                7.6       16      yes
  KXSOL15M-26SEP110830-30           2026-09-11T12:30:00Z               10.5       26      yes
  KXSOL15M-26SEP112300-00           2026-09-12T03:00:00Z               31.5       11      yes
  KXXRP15M-26SEP100100-00           2026-09-10T05:00:00Z               15.0       20       no
  KXETH15M-26SEP120545-45             settlement not yet in markets.json -- EXCLUDED, not estimated
  KXSOL15M-26SEP120400-00             settlement not yet in markets.json -- EXCLUDED, not estimated
  KXSOL15M-26SEP120600-00             settlement not yet in markets.json -- EXCLUDED, not estimated

  THE DENOMINATOR. From section 1's last-60s panel: the chance a close's final minute
  contains at least one such second at all, per coin. A big jump is NOT rare.

  coin            P(>5 sigma in 60s)    P(>8 sigma in 60s)
  KXBNB15M                     34.2%                  8.9%
  KXBTC15M                     29.6%                 10.6%
  KXDOGE15M                    28.5%                 11.9%
  KXETH15M                     24.2%                  8.2%
  KXHYPE15M                    31.8%                 13.8%
  KXNEAR15M                    37.2%                 12.7%
  KXSOL15M                     21.6%                  7.6%
  KXXRP15M                     25.9%                 11.1%
  KXZEC15M                     30.2%                 12.5%

  k > 5: 6 of 6 losing closes carried one. Expected 1.69 under each coin's
          own base rate -> Poisson-binomial P(>= 6 of 6) = 0.00044
  k > 8: 4 of 6 losing closes carried one. Expected 0.60 under each coin's
          own base rate -> Poisson-binomial P(>= 4 of 6) = 0.00120

  SO: belief collapse on a one-second jump is what kills these bets, and that is
  established against the base rate rather than asserted from the cases. But the
  base rate is HIGH -- a fifth to a third of all closes carry a >5-sigma second and
  we win nearly every one -- so 'there was a jump' can never be a gate by itself.
  n here is 6-7 CLOSES. It is a mechanism check, not a rate.

==============================================================================
  7. ENTRY MARGIN vs OUTCOME, on OUR OWN FILLS -- section 5's prediction, TESTED
==============================================================================
  Section 5's sigma understatement inflates every z-score, so it can only change a
  decision NEAR THE GATE. Prediction: losses concentrate in entries barely past
  0.995 and are absent from the saturated ones. Bands are on the LOWEST confidence
  actually bought on that close.

  ALL live runs: 183 closes with both an entry signal and a settlement
  entry confidence band     closes  lost    rate              95% CI   median margin
  0.9950-0.9990                 87     2    2.3%        [0.3%, 8.1%]          2.77 sd
  0.9990-0.99999                35     1    2.9%       [0.1%, 14.9%]          3.41 sd
  0.99999-1 (saturated)         22     2    9.1%       [1.1%, 29.2%]          7.03 sd
  saturated share of ENTRIES 12.0% (22/183); of LOSSES 28.6% (2/7)

  CURRENT GATE ONLY (pin = 0.995): 103 closes with both an entry signal and a settlement
  entry confidence band     closes  lost    rate              95% CI   median margin
  0.9950-0.9990                 66     2    3.0%       [0.4%, 10.5%]          2.75 sd
  0.9990-0.99999                24     1    4.2%       [0.1%, 21.1%]          3.41 sd
  0.99999-1 (saturated)         13     1    7.7%       [0.2%, 36.0%]          7.03 sd
  saturated share of ENTRIES 12.6% (13/103); of LOSSES 25.0% (1/4)

  Our losing closes, least confident first:
    KXNEAR15M-26SEP082045-45           gate 0.98  entry conf 0.981740  margin 2.09 sd
    KXBNB15M-26SEP100130-30            gate 0.98  entry conf 0.985070  margin 2.17 sd
    KXSOL15M-26SEP110830-30            gate 0.995  entry conf 0.995080  margin 2.58 sd
    KXSOL15M-26SEP120400-00            gate 0.995  entry conf 0.997640  margin 2.83 sd
    KXSOL15M-26SEP112300-00            gate 0.995  entry conf 0.999680  margin 3.41 sd
    KXXRP15M-26SEP100100-00            gate 0.98  entry conf 1.000000  margin 7.03 sd
    KXDOGE15M-26SEP101815-15           gate 0.995  entry conf 1.000000  margin 7.03 sd

  *** SECTION 5's PREDICTION FAILS, AND IT FAILS IN THE DIRECTION THAT MATTERS. ***
  The loss rate does not fall as entry confidence rises; the point estimate rises.
  Every interval overlaps every other -- with this many losing closes nothing here
  is significant in EITHER direction -- but a gate change justified by section 5
  would need this table to lean the other way, and it does not. So no PIN change, no
  margin cushion, and no per-coin sigma is proposed from this file.

  ONE THING IS CLEAR AND IT IS NOT ABOUT MARGIN: our entries are only ~12%
  saturated while the TAPE's gate entries are 73-85% saturated (section 2/3). We
  cannot buy what nobody offers, and in a decided market the losing side's book is
  empty -- so we systematically get the LESS certain end of the same gate. That is
  the adverse selection CLAUDE.md rule 5 is about, measured here in its own units.
```
