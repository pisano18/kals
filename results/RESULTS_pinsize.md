========================================================================================================================
pinsize -- does sizing on confidence beat flat sizing?
========================================================================================================================
  population: 593 genuinely available trades over 70 closes, tau 3-20s, p_flip <= 0.02, EV >= 0.3c at 0.90%
  REALISED FLIPS IN THIS POPULATION: 0
  ^ ZERO. Realised P&L is therefore a monotone increasing function of
    contracts bought and CANNOT rank these rules. The EXPECTED columns
    below, which price losses in, are the ones that decide.
  flip rate: 0.90% measured (3 in 333). Upper 95% bound: 1.80% as this project quotes it (a Wald approximation, 1.75% exactly), 2.31% by exact Clopper-Pearson.
  The project's 1.80% is OPTIMISTIC by 28%. Both are scored below; 2.31% is the honest worst case.
  breakeven price: 99.1c at the point estimate, 98.2c at the upper bound
  93 of 593 eligible trades (15.7%) are priced above the upper-bound breakeven, i.e. they are negative EV if the flip rate is really 1.80%

------------------------------------------------------------------------------------------------------------------------
TABLE 1 -- REALISED on this sample. NOT A RANKING: zero losses occurred,
           so every extra contract is free money here and only here.
------------------------------------------------------------------------------------------------------------------------
  rule                     closes  contr   avg px   total c  c/close  c/contr  worst cl  maxExp $
  FLAT1                        70     70   0.9537     303.0     4.33     4.33      1.21     0.988
  FLAT2                        70    139   0.9537     601.6     8.59     4.33      2.42     1.976
  FLAT3                        70    205   0.9535     892.3    12.75     4.35      3.53     2.964
  EV_PROP cap2                 70    113   0.9472     558.0     7.97     4.94      1.21     1.952
  EV_PROP cap3                 70    136   0.9408     753.7    10.77     5.54      1.21     2.894
  EV_PROP cap4                 70    154   0.9356     928.9    13.27     6.03      1.21     3.813
  CONF_PROP cap2               70     96   0.9581     375.9     5.37     3.92      1.21     1.976
  CONF_PROP cap3               70    110   0.9606     405.2     5.79     3.68      1.21     2.964
  CONF_PROP cap4               70    121   0.9622     427.4     6.11     3.53      1.21     3.952
  PRICE_TIER cap2              70     81   0.9422     438.7     6.27     5.42      1.21     1.845
  PRICE_TIER cap3              70     89   0.9341     550.1     7.86     6.18      1.21     2.744
  PRICE_TIER cap4              70     94   0.9281     634.1     9.06     6.75      1.21     3.512
  KELLY_full cap2              70    139   0.9537     601.6     8.59     4.33      2.42     1.976
  KELLY_1/4 cap2               70    139   0.9537     601.6     8.59     4.33      2.42     1.976
  KELLY_1/10 cap2              70    139   0.9537     601.6     8.59     4.33      2.42     1.976
  KELLY_1/20 cap2              70    131   0.9517     591.6     8.45     4.52      1.21     1.972
  KELLY_1/20 cap4              70    196   0.9436    1035.2    14.79     5.28      1.21     3.836
  SCALE_IMPROVE cap2 LIVE      70     96   0.9441     502.3     7.18     5.23      1.21     1.968
  SCALE_IMPROVE cap3           70    106   0.9387     608.6     8.69     5.74      1.21     2.922
  SCALE_IMPROVE cap4           70    108   0.9349     659.0     9.41     6.10      1.21     3.659
  TIER_IMPROVE cap2            70    102   0.9403     570.2     8.15     5.59      1.21     1.968
  TIER_IMPROVE cap3            70    127   0.9297     836.2    11.95     6.58      1.21     2.922
  TIER_IMPROVE cap4            70    146   0.9226    1059.2    15.13     7.25      1.21     3.806
  EV_IMPROVE cap2              70    125   0.9474     615.4     8.79     4.92      1.21     1.968
  EV_IMPROVE cap3              70    165   0.9404     920.0    13.14     5.58      1.21     2.926
  CONF_IMPROVE cap2            70    112   0.9512     511.0     7.30     4.56      1.21     1.976

------------------------------------------------------------------------------------------------------------------------
TABLE 2 -- EXPECTED, losses priced in. THIS is the comparison.
           'trips $3' = one bad close commits $3.00 or more and ends the
           session on a single event -> the rule is REJECTED.
------------------------------------------------------------------------------------------------------------------------
  rule                      contr  Ec/close  Ec/con  Ec/close  Ec/con  Ec/close  negCl  maxExp$ maxCon abort in trips $3  near $3
                                     @0.90%  @0.90%    @1.80%  @1.80%    @2.31% @2.31%   /close /close   closes     in 1  >=$2.70
  FLAT1                        70      3.43    3.43      2.53    2.53      2.02     24    0.988      1        4       no       no
  FLAT2                       139      6.81    3.43      5.02    2.53      4.01     24    1.976      2        2       no       no
  FLAT3                       205     10.11    3.45      7.48    2.55      5.98     24    2.964      3        2       no      YES
  EV_PROP cap2                113      6.52    4.04      5.07    3.14      4.24     24    1.952      2        2       no       no
  EV_PROP cap3                136      9.02    4.64      7.27    3.74      6.28     24    2.894      3        2       no      YES
  EV_PROP cap4                154     11.29    5.13      9.31    4.23      8.19     24    3.813      4        1      YES      YES
  CONF_PROP cap2               96      4.14    3.02      2.90    2.12      2.20     24    1.976      2        2       no       no
  CONF_PROP cap3              110      4.37    2.78      2.96    1.88      2.16     24    2.964      3        2       no      YES
  CONF_PROP cap4              121      4.55    2.63      2.99    1.73      2.11     24    3.952      4        1      YES      YES
  PRICE_TIER cap2              81      5.23    4.52      4.18    3.62      3.59     24    1.845      2        2       no       no
  PRICE_TIER cap3              89      6.71    5.28      5.57    4.38      4.92     24    2.744      3        2       no      YES
  PRICE_TIER cap4              94      7.85    5.85      6.64    4.95      5.96     24    3.512      4        1      YES      YES
  KELLY_full cap2             139      6.81    3.43      5.02    2.53      4.01     24    1.976      2        2       no       no
  KELLY_1/4 cap2              139      6.81    3.43      5.02    2.53      4.01     24    1.976      2        2       no       no
  KELLY_1/10 cap2             139      6.81    3.43      5.02    2.53      4.01     24    1.976      2        2       no       no
  KELLY_1/20 cap2             131      6.77    3.62      5.08    2.72      4.13     24    1.972      2        2       no       no
  KELLY_1/20 cap4             196     12.27    4.38      9.75    3.48      8.32     24    3.836      4        1      YES      YES
  SCALE_IMPROVE cap2 LIVE      96      5.94    4.33      4.71    3.43      4.01     17    1.968      2        2       no       no
  SCALE_IMPROVE cap3          106      7.33    4.84      5.97    3.94      5.20     16    2.922      3        2       no      YES
  SCALE_IMPROVE cap4          108      8.03    5.20      6.64    4.30      5.85     16    3.659      4        1      YES      YES
  TIER_IMPROVE cap2           102      6.84    4.69      5.52    3.79      4.78     17    1.968      2        2       no       no
  TIER_IMPROVE cap3           127     10.31    5.68      8.68    4.78      7.75     16    2.922      3        2       no      YES
  TIER_IMPROVE cap4           146     13.25    6.35     11.38    5.45     10.31     16    3.806      4        1      YES      YES
  EV_IMPROVE cap2             125      7.18    4.02      5.58    3.12      4.67     17    1.968      2        2       no       no
  EV_IMPROVE cap3             165     11.02    4.68      8.90    3.78      7.70     15    2.926      3        2       no      YES
  CONF_IMPROVE cap2           112      5.86    3.66      4.42    2.76      3.60     21    1.976      2        2       no       no

------------------------------------------------------------------------------------------------------------------------
TABLE 3 -- the depth guard's cost, and its null (a rule wanting one
           contract must be truncated zero times)
------------------------------------------------------------------------------------------------------------------------
  rule                      orders  truncated  dust skips  mean exp $  typ abort
  FLAT1                         70          0           0       0.957          4
  FLAT2                         70          1           0       1.900          2
  FLAT3                         70          4           0       2.801          2
  EV_PROP cap2                  70          1           0       1.535          2
  EV_PROP cap3                  70          1           0       1.835          2
  EV_PROP cap4                  70          1           0       2.067          2
  CONF_PROP cap2                70          1           0       1.318          3
  CONF_PROP cap3                70          3           0       1.514          2
  CONF_PROP cap4                70          3           0       1.668          2
  PRICE_TIER cap2               70          0           0       1.094          3
  PRICE_TIER cap3               70          0           0       1.193          3
  PRICE_TIER cap4               70          0           0       1.252          3
  KELLY_full cap2               70          1           0       1.900          2
  KELLY_1/4 cap2                70          1           0       1.900          2
  KELLY_1/10 cap2               70          1           0       1.900          2
  KELLY_1/20 cap2               70          1           0       1.787          2
  KELLY_1/20 cap4               70          4           0       2.652          2
  SCALE_IMPROVE cap2 LIVE       96          0           0       1.300          3
  SCALE_IMPROVE cap3           106          0           0       1.427          3
  SCALE_IMPROVE cap4           108          0           0       1.449          3
  TIER_IMPROVE cap2             91          0           0       1.376          3
  TIER_IMPROVE cap3             98          0           0       1.695          2
  TIER_IMPROVE cap4            100          0           0       1.934          2
  EV_IMPROVE cap2               82          1           0       1.698          2
  EV_IMPROVE cap3               90          2           0       2.226          2
  CONF_IMPROVE cap2             86          1           0       1.527          2

------------------------------------------------------------------------------------------------------------------------
THE MECHANISM -- why sizing on the MODEL'S confidence backfires
------------------------------------------------------------------------------------------------------------------------
  model p_flip band        rows  mean price  EV/contract c   @0.90%
  [0e+00, 1e-10)          113      0.9751           1.41         
  [1e-10, 1e-08)           28      0.9678           2.10         
  [1e-08, 1e-05)           91      0.9681           2.08         
  [1e-05, 1e-03)          156      0.9619           2.66         
  [1e-03, 1e+00)          205      0.9439           4.35         

  The model is MOST confident exactly where the contract is MOST
  EXPENSIVE, so 'buy more when confident' is 'buy more at 97-99c'.
  That is the wrong direction: at these prices the win is 1-3c and the
  loss is 97-99c, and the model's own confidence is already known to be
  ~15x too high (it implies ~0.06% where 0.90% is measured), so its
  ordering within the eligible set carries no information about risk.

------------------------------------------------------------------------------------------------------------------------
RISK -- Monte Carlo on the -$3.00 abort
------------------------------------------------------------------------------------------------------------------------
  Each close is drawn with replacement from the 70 actual buy patterns.
  Every contract in a close flips together (rho -> 1 across coins on the
  same quarter hour; hard rule 4). 20,000 paths of 500 closes -- the
  pre-registered forward window. P&L runs cumulatively from flat.
  rule                      P(abort) 0.90%     1.80%     2.31%  med worst DD $
  FLAT1                               0.0%      0.5%      2.1%            0.02
  FLAT2                               0.9%      5.7%     12.0%            0.05
  FLAT3                               2.4%     11.1%     19.7%            0.07
  EV_PROP cap2                        0.3%      2.8%      6.3%            0.05
  EV_PROP cap3                        0.7%      4.1%      7.7%            0.05
  EV_PROP cap4                        2.1%      6.5%     10.5%            0.05
  CONF_PROP cap2                      0.5%      4.4%     10.9%            0.03
  CONF_PROP cap3                      1.5%      9.3%     19.6%            0.03
  CONF_PROP cap4                      4.4%     15.8%     27.5%            0.03
  PRICE_TIER cap2                     0.1%      0.6%      2.0%            0.03
  PRICE_TIER cap3                     0.3%      1.2%      2.8%            0.03
  PRICE_TIER cap4                     0.7%      2.3%      4.1%            0.03
  KELLY_full cap2                     0.9%      5.7%     12.0%            0.05
  KELLY_1/4 cap2                      0.9%      5.7%     12.0%            0.05
  KELLY_1/10 cap2                     0.9%      5.7%     12.0%            0.05
  KELLY_1/20 cap2                     0.7%      4.7%      9.9%            0.05
  KELLY_1/20 cap4                     3.0%      9.3%     15.0%            0.07
  SCALE_IMPROVE cap2 LIVE             0.2%      1.5%      4.0%            0.03
  SCALE_IMPROVE cap3                  0.4%      2.2%      4.6%            0.03
  SCALE_IMPROVE cap4                  0.6%      2.5%      4.7%            0.03
  TIER_IMPROVE cap2                   0.2%      1.4%      3.6%            0.03
  TIER_IMPROVE cap3                   0.6%      2.5%      5.0%            0.03
  TIER_IMPROVE cap4                   1.9%      4.9%      7.9%            0.04
  EV_IMPROVE cap2                     0.5%      3.3%      7.3%            0.06
  EV_IMPROVE cap3                     1.0%      4.8%      9.2%            0.07
  CONF_IMPROVE cap2                   0.4%      3.5%      8.1%            0.04

------------------------------------------------------------------------------------------------------------------------
KELLY, and why full Kelly is not a candidate
------------------------------------------------------------------------------------------------------------------------
  bankroll assumed $100.00
     price   f* @0.90%  contracts   f* @1.80%  contracts    change
     90.0c       0.910        101       0.820         91      -10%
     93.0c       0.871         93       0.743         79      -15%
     95.0c       0.820         86       0.640         67      -22%
     97.0c       0.700         72       0.400         41      -43%
     98.0c       0.550         56       0.100         10      -82%
     98.2c       0.500         50       0.000          0     -100%
     98.5c       0.400         40      -0.200          0     -100%
     98.7c       0.308         31      -0.385          0     -100%

------------------------------------------------------------------------------------------------------------------------
HOW MUCH FLIP RATE EACH RULE CAN ABSORB before its EV per close is zero
------------------------------------------------------------------------------------------------------------------------
  rule                      breakeven flip %   headroom vs 0.90%  survives 1.80%  survives 2.31%
  FLAT1                                4.328               4.81x             yes             yes
  FLAT2                                4.328               4.81x             yes             yes
  FLAT3                                4.353               4.84x             yes             yes
  EV_PROP cap2                         4.938               5.49x             yes             yes
  EV_PROP cap3                         5.542               6.16x             yes             yes
  EV_PROP cap4                         6.032               6.70x             yes             yes
  CONF_PROP cap2                       3.916               4.35x             yes             yes
  CONF_PROP cap3                       3.683               4.09x             yes             yes
  CONF_PROP cap4                       3.532               3.92x             yes             yes
  PRICE_TIER cap2                      5.416               6.02x             yes             yes
  PRICE_TIER cap3                      6.181               6.87x             yes             yes
  PRICE_TIER cap4                      6.745               7.49x             yes             yes
  KELLY_full cap2                      4.328               4.81x             yes             yes
  KELLY_1/4 cap2                       4.328               4.81x             yes             yes
  KELLY_1/10 cap2                      4.328               4.81x             yes             yes
  KELLY_1/20 cap2                      4.516               5.02x             yes             yes
  KELLY_1/20 cap4                      5.282               5.87x             yes             yes
  SCALE_IMPROVE cap2 LIVE              5.232               5.81x             yes             yes
  SCALE_IMPROVE cap3                   5.742               6.38x             yes             yes
  SCALE_IMPROVE cap4                   6.102               6.78x             yes             yes
  TIER_IMPROVE cap2                    5.591               6.21x             yes             yes
  TIER_IMPROVE cap3                    6.584               7.32x             yes             yes
  TIER_IMPROVE cap4                    7.255               8.06x             yes             yes
  EV_IMPROVE cap2                      4.924               5.47x             yes             yes
  EV_IMPROVE cap3                      5.576               6.20x             yes             yes
  CONF_IMPROVE cap2                    4.562               5.07x             yes             yes

------------------------------------------------------------------------------------------------------------------------
SIGMA STRESS -- how much of this depends on the volatility estimate
------------------------------------------------------------------------------------------------------------------------
  sigma enters these rules in exactly TWO places:
    (a) the ELIGIBILITY gate p_flip <= 0.02, which decides WHICH trades
        exist at all -- shared by every rule including flat sizing;
    (b) CONF_PROP's size, which is the ONLY rule that sizes on sigma.
  PRICE_TIER, EV_PROP and the improve rules size on PRICE, so their
  sizing decision does not read sigma at all.

  Stress multipliers are the measured hour-to-hour spread of sigma_300
  from the volatility-accuracy study (r=19: p05 0.865, median 1.066,
  p95 1.327), plus 1.50 and 2.00 as a deliberate overshoot.
    sigma x  elig rows  closes  TIER_IMPROVE2  SCALE_IMPR2  CONF_PROP2    FLAT2
                                Ec/close@1.8%        @1.8%       @1.8%    @1.8%
      0.865        648      70           6.68         6.08        4.13     5.99
      1.000        593      70           5.52         4.71        2.90     5.02
      1.066        559      69           5.07         4.23        2.57     4.34
      1.327        461      68           3.71         3.05        1.46     2.72
      1.500        391      63           2.92         2.58        1.18     2.17
      2.000        247      55           1.81         1.53        0.96     1.79

  Same rows, as a percentage of the sigma x 1.000 result:
      0.865                              121%         129%        142%     119%
      1.327                               67%          65%         50%      54%
      2.000                               33%          33%         33%      36%

------------------------------------------------------------------------------------------------------------------------
LIVE CONFIGURATION CHECK -- the running process is NOT at size 1
------------------------------------------------------------------------------------------------------------------------
  Read from the live process on 2026-09-08:
    pinrun.py --live --size 8 --minutes 720 --loss-abort -15.00 --max-positions 3
  MAX_PER_CLOSE is 2 and is NOT settable by a flag, so a close can hold
  TWO takes of 8 = 16 contracts.
  pinrun's own rail sizes the abort off ONE take (one_loss = 1.00 * size = $8.00)
  and requires the abort in [-4x, -1.5x] of it. It does not account for
  the second take, so the worst close is twice what the rail assumes.

  rule                      contr  maxExp $  meanExp $  vs abort   trips  bad closes
                                     /close     /close    $15.00    in 1    to abort
  FLAT2                      1048     15.81      14.31      105%     YES           1
  EV_PROP cap2                848     15.61      11.50      104%     YES           1
  CONF_PROP cap2              736     15.81      10.09      105%     YES           1
  PRICE_TIER cap2             656     14.76       8.86       98%      no           2
  KELLY_1/20 cap2             968     15.78      13.18      105%     YES           1
  SCALE_IMPROVE cap2 LIVE     744     15.75      10.07      105%     YES           1
  TIER_IMPROVE cap2           800     15.75      10.79      105%     YES           1
  EV_IMPROVE cap2             936     15.75      12.70      105%     YES           1
  CONF_IMPROVE cap2           872     15.81      11.87      105%     YES           1

  THIS IS THE FINDING THAT MATTERS MOST FOR THE MONEY ACTUALLY AT RISK:
  at --size 8 the live rule's worst single close is already at or over
  the -$15.00 abort, so ONE bad close can end the session. That is a
  property of the CURRENT configuration, not of any rule proposed here,
  and it is unchanged by the sizing question. Every rule below was
  scored at size 1 against -$3.00 as briefed; the ratio is what
  transfers, and the ratio says the same thing at both sizes.

------------------------------------------------------------------------------------------------------------------------
THE VERDICT -- apply the risk rejection, then rank on cents per CLOSE
------------------------------------------------------------------------------------------------------------------------
  REJECT any rule whose worst single close commits >= $2.70, i.e. 90% of the -$3.00
  abort budget. One bad event then ends the session outright or leaves
  too little of the budget standing to keep trading. pinrun's own
  comment already reaches this conclusion for cap 3.

  REJECTED (13): FLAT3 ($2.96), EV_PROP cap3 ($2.89), EV_PROP cap4 ($3.81), CONF_PROP cap3 ($2.96), CONF_PROP cap4 ($3.95), PRICE_TIER cap3 ($2.74), PRICE_TIER cap4 ($3.51), KELLY_1/20 cap4 ($3.84), SCALE_IMPROVE cap3 ($2.92), SCALE_IMPROVE cap4 ($3.66), TIER_IMPROVE cap3 ($2.92), TIER_IMPROVE cap4 ($3.81), EV_IMPROVE cap3 ($2.93)

  SURVIVORS (13), ranked by expected cents per close at the
  EXACT 2.31% upper bound -- the honest worst case:
   rank  rule                      Ec/close  Ec/close  Ec/close  Ec/con  contr  maxExp$  P(abort)  headroom
                                     @0.90%    @1.80%    @2.31%  @2.31%                    @2.31%          
      1  TIER_IMPROVE cap2             6.84      5.52      4.78    3.28    102    1.968      3.6%     6.21x
      2  EV_IMPROVE cap2               7.18      5.58      4.67    2.61    125    1.968      7.3%     5.47x
      3  EV_PROP cap2                  6.52      5.07      4.24    2.63    113    1.952      6.3%     5.49x
      4  KELLY_1/20 cap2               6.77      5.08      4.13    2.21    131    1.972      9.9%     5.02x
      5  SCALE_IMPROVE cap2 LIVE       5.94      4.71      4.01    2.92     96    1.968      4.0%     5.81x
      6  FLAT2                         6.81      5.02      4.01    2.02    139    1.976     12.0%     4.81x
      7  KELLY_full cap2               6.81      5.02      4.01    2.02    139    1.976     12.0%     4.81x
      8  KELLY_1/4 cap2                6.81      5.02      4.01    2.02    139    1.976     12.0%     4.81x
      9  KELLY_1/10 cap2               6.81      5.02      4.01    2.02    139    1.976     12.0%     4.81x
     10  CONF_IMPROVE cap2             5.86      4.42      3.60    2.25    112    1.976      8.1%     5.07x
     11  PRICE_TIER cap2               5.23      4.18      3.59    3.11     81    1.845      2.0%     6.02x
     12  CONF_PROP cap2                4.14      2.90      2.20    1.61     96    1.976     10.9%     4.35x
     13  FLAT1                         3.43      2.53      2.02    2.02     70    0.988      2.1%     4.81x

  CAVEATS THAT TRAVEL WITH EVERY NUMBER ABOVE
  1. 70 closes over THREE days (2026-09-04/05/06), 43 of them on one
     day. That is 3 independent day-blocks, not 70 observations.
  2. ZERO flips occurred here. The 0.90% is IMPORTED from a different
     sample (3 in 333 dear trades, out of sample). Nothing in this
     dataset measures the flip rate, so nothing here can confirm it.
  3. Every EV number is linear in that imported rate. If the true rate
     is above each rule's breakeven (3.5-7.3%), every rule loses.
  4. The backtest always gets the quote. Live, we race for it.
