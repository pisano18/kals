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
  TIER_IMPROVE cap4            70    146   0.9226    1059.2    15.13     7.25      1.21     3.806

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
  TIER_IMPROVE cap4           146     13.25    6.35     11.38    5.45     10.31     16    3.806      4        1      YES      YES

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
  TIER_IMPROVE cap4            100          0           0       1.934          2

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
  FLAT1                               0.0%      0.6%      2.0%            0.00
  FLAT2                               0.9%      5.7%     11.6%            0.00
  FLAT3                               2.2%     11.0%     19.1%            0.00
  EV_PROP cap2                        0.3%      2.7%      6.1%            0.00
  EV_PROP cap3                        0.7%      3.8%      7.9%            0.00
  EV_PROP cap4                        2.1%      6.8%     10.9%            0.00
  CONF_PROP cap2                      0.5%      4.3%     10.5%            0.00
  CONF_PROP cap3                      1.6%      9.3%     18.8%            0.00
  CONF_PROP cap4                      4.5%     15.6%     26.9%            0.00
  PRICE_TIER cap2                     0.1%      0.6%      1.8%            0.00
  PRICE_TIER cap3                     0.2%      1.2%      2.7%            0.00
  PRICE_TIER cap4                     0.7%      2.4%      4.0%            0.00
  KELLY_full cap2                     0.9%      5.7%     11.6%            0.00
  KELLY_1/4 cap2                      0.9%      5.7%     11.6%            0.00
  KELLY_1/10 cap2                     0.9%      5.7%     11.6%            0.00
  KELLY_1/20 cap2                     0.6%      4.7%      9.9%            0.00
  KELLY_1/20 cap4                     2.8%      9.4%     14.9%            0.00
  SCALE_IMPROVE cap2 LIVE             0.3%      1.7%      3.6%            0.00
  SCALE_IMPROVE cap3                  0.4%      2.4%      4.7%            0.00
  SCALE_IMPROVE cap4                  0.6%      2.6%      4.6%            0.00
  TIER_IMPROVE cap4                   1.8%      5.4%      7.6%            0.00

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
  TIER_IMPROVE cap4                    7.255               8.06x             yes             yes

