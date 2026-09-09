```

==============================================================================
LIVE WINDOW -- follow-ups
==============================================================================

  1. FLIP RATE BY WHAT WE PAID. MEASURED_FLIP = 0.90% was measured on DEAR trades
     only ('3 flips in 333'), so pooling every price against it is the wrong comparison.
  price paid           buys  lost  flip rate              95% CI
  0c - 50c               11     6     0.5455     [0.2801, 0.7873]
  50c - 80c              27     1     0.0370     [0.0066, 0.1828]
  80c - 90c              51     2     0.0392     [0.0108, 0.1322]
  90c - 95c             135     5     0.0370     [0.0159, 0.0838]
  95c - 101c            415     1     0.0024     [0.0004, 0.0135]

     Quote age at entry: below 50c, median 567 ms over 11 buys; at 90c+,
     median 581 ms over 550. A much staler quote on the cheap ones would
     mean they are a replay artefact rather than a trade anyone could have had.

  2/3. ALL PRICES: 639 buys, 470 closes, 12 losing closes,
       one win = $1.5158, total $529.84, worst -$37.50 = 24.7 wins.
  trigger                total$   cost$        95% CI on cost   worst$   wins  made  worstFA$
  SPOT_CROSS             363.70 -166.13   [ -329.40,    -3.91]   -22.22   14.7    55     22.22
  SPOT_CROSS_HOLD2       423.88 -105.96   [ -257.22,    56.35]   -22.62   14.9    40     22.62
  MU_CROSS               487.78  -42.06   [ -153.67,    53.87]   -26.86   17.7     5     22.22
  MU_CROSS_HOLD2         491.41  -38.42   [ -139.25,    44.76]   -35.33   23.3     4     22.62
  MODEL_P90              525.14   -4.70   [ -103.28,    67.19]   -35.59   23.5     1     35.59
       'cost$' is profit given up, with a 95% bootstrap interval resampling CLOSES.
       'made' counts closes the hedge turned from a PROFIT into a LOSS; 'worstFA$' is
       the biggest single loss the hedge itself manufactured.

  4. THE OPERATOR'S IDEA TAKEN LITERALLY -- refuse the hedge when the other side
     is dear. A hedge at 90c does not cap a loss, it confirms one.
  trigger              cap  frac   total$   cost$   worst$   wins  made  worstFA$  caught
  SPOT_CROSS           10c  1.00   477.11  -52.73   -18.67   12.3    41      2.28       5
  SPOT_CROSS           10c  0.50   503.30  -26.54   -19.57   12.9    15      0.57       5
  SPOT_CROSS           25c  1.00   447.81  -82.02   -18.67   12.3    52      7.22       8
  SPOT_CROSS           25c  0.50   489.05  -40.79   -20.23   13.3    24      2.99       8
  SPOT_CROSS           50c  1.00   398.96 -130.87   -18.67   12.3    54     17.84       9
  SPOT_CROSS           50c  0.50   464.11  -65.73   -20.23   13.3    25      7.89       9
  SPOT_CROSS          none  1.00   363.70 -166.13   -22.22   14.7    55     22.22      15
  SPOT_CROSS          none  0.50   446.74  -83.10   -20.23   13.3    26      9.89      15
  MU_CROSS             10c  1.00   518.07  -11.76   -37.50   24.7     0      0.00       0
  MU_CROSS             10c  0.50   523.95   -5.88   -37.50   24.7     0      0.00       0
  MU_CROSS             25c  1.00   500.63  -29.20   -37.50   24.7     2      4.13       0
  MU_CROSS             25c  0.50   515.23  -14.60   -37.50   24.7     1      0.67       0
  MU_CROSS             50c  1.00   462.16  -67.67   -37.50   24.7     5     17.84       2
  MU_CROSS             50c  0.50   496.00  -33.84   -37.50   24.7     3      7.89       2
  MU_CROSS            none  1.00   487.78  -42.06   -26.86   17.7     5     22.22      15
  MU_CROSS            none  0.50   509.05  -20.78   -32.18   21.2     4      9.89      15
       'caught' is how many LOSING buys actually got a hedge under that cap.

  2/3. 90c AND DEARER: 550 buys, 431 closes, 5 losing closes,
       one win = $0.8527, total $260.44, worst -$37.50 = 44.0 wins.
  trigger                total$   cost$        95% CI on cost   worst$   wins  made  worstFA$
  SPOT_CROSS             122.20 -138.24   [ -249.00,   -28.11]   -22.22   26.1    54     22.22
  SPOT_CROSS_HOLD2       149.42 -111.02   [ -214.67,    -0.72]   -22.62   26.5    40     22.62
  MU_CROSS               223.72  -36.72   [ -117.44,    27.17]   -26.86   31.5     5     22.22
  MU_CROSS_HOLD2         223.08  -37.36   [ -108.95,    15.84]   -35.33   41.4     4     22.62
  MODEL_P90              231.73  -28.71   [ -129.47,    32.67]   -35.59   41.7     2     35.59
       'cost$' is profit given up, with a 95% bootstrap interval resampling CLOSES.
       'made' counts closes the hedge turned from a PROFIT into a LOSS; 'worstFA$' is
       the biggest single loss the hedge itself manufactured.

  4. THE OPERATOR'S IDEA TAKEN LITERALLY -- refuse the hedge when the other side
     is dear. A hedge at 90c does not cap a loss, it confirms one.
  trigger              cap  frac   total$   cost$   worst$   wins  made  worstFA$  caught
  SPOT_CROSS           10c  1.00   199.93  -60.51   -19.05   22.3    47      2.28       3
  SPOT_CROSS           10c  0.50   229.97  -30.47   -19.57   22.9    17      0.60       3
  SPOT_CROSS           25c  1.00   167.34  -93.10   -18.67   21.9    53      7.22       4
  SPOT_CROSS           25c  0.50   214.21  -46.23   -20.23   23.7    27      2.99       4
  SPOT_CROSS           50c  1.00   130.35 -130.09   -18.67   21.9    54     17.84       4
  SPOT_CROSS           50c  0.50   195.71  -64.73   -20.23   23.7    29      7.89       4
  SPOT_CROSS          none  1.00   122.20 -138.24   -22.22   26.1    54     22.22       6
  SPOT_CROSS          none  0.50   191.84  -68.60   -20.23   23.7    29      9.89       6
  MU_CROSS             10c  1.00   254.22   -6.22   -37.50   44.0     2      1.56       0
  MU_CROSS             10c  0.50   257.33   -3.11   -37.50   44.0     2      0.60       0
  MU_CROSS             25c  1.00   244.37  -16.07   -37.50   44.0     4      4.27       0
  MU_CROSS             25c  0.50   252.40   -8.04   -37.50   44.0     3      1.95       0
  MU_CROSS             50c  1.00   214.02  -46.42   -37.50   44.0     5     17.84       1
  MU_CROSS             50c  0.50   237.23  -23.21   -37.50   44.0     5      7.89       1
  MU_CROSS            none  1.00   223.72  -36.72   -26.86   31.5     5     22.22       6
  MU_CROSS            none  0.50   242.26  -18.18   -32.18   37.7     5      9.89       6
       'caught' is how many LOSING buys actually got a hedge under that cap.

==============================================================================
WIDE WINDOW -- follow-ups
==============================================================================

  1. FLIP RATE BY WHAT WE PAID. MEASURED_FLIP = 0.90% was measured on DEAR trades
     only ('3 flips in 333'), so pooling every price against it is the wrong comparison.
  price paid           buys  lost  flip rate              95% CI
  0c - 50c               10     7     0.7000     [0.3968, 0.8922]
  50c - 80c              74    29     0.3919     [0.2886, 0.5058]
  80c - 90c             266    38     0.1429     [0.1059, 0.1900]
  90c - 95c             496    30     0.0605     [0.0427, 0.0850]
  95c - 101c            628    22     0.0350     [0.0232, 0.0525]

     Quote age at entry: below 50c, median 572 ms over 10 buys; at 90c+,
     median 577 ms over 1124. A much staler quote on the cheap ones would
     mean they are a replay artefact rather than a trade anyone could have had.

  2/3. ALL PRICES: 1,474 buys, 856 closes, 88 losing closes,
       one win = $2.2674, total $-183.65, worst -$38.66 = 17.0 wins.
  trigger                total$   cost$        95% CI on cost   worst$   wins  made  worstFA$
  SPOT_CROSS              35.33  218.97   [  -87.23,   532.77]   -34.58   15.2    61     23.90
  SPOT_CROSS_HOLD2        55.39  239.04   [  -46.05,   540.01]   -35.14   15.5    53     25.07
  MU_CROSS                11.09  194.73   [  -91.38,   471.83]   -34.58   15.2    43     23.90
  MU_CROSS_HOLD2          -4.69  178.96   [  -64.12,   423.96]   -35.14   15.5    37     25.07
  MODEL_P90               53.44  237.08   [  117.29,   357.74]   -35.52   15.7     5     25.07
       'cost$' is profit given up, with a 95% bootstrap interval resampling CLOSES.
       'made' counts closes the hedge turned from a PROFIT into a LOSS; 'worstFA$' is
       the biggest single loss the hedge itself manufactured.

  4. THE OPERATOR'S IDEA TAKEN LITERALLY -- refuse the hedge when the other side
     is dear. A hedge at 90c does not cap a loss, it confirms one.
  trigger              cap  frac   total$   cost$   worst$   wins  made  worstFA$  caught
  SPOT_CROSS           10c  1.00  -126.29   57.36   -38.58   17.0    19      2.98      14
  SPOT_CROSS           10c  0.50  -146.94   36.71   -38.58   17.0     2      0.86      14
  SPOT_CROSS           25c  1.00   -34.16  149.49   -38.58   17.0    48      8.84      33
  SPOT_CROSS           25c  0.50  -108.35   75.30   -38.58   17.0    17      3.79      33
  SPOT_CROSS           50c  1.00   -22.00  161.65   -37.76   16.7    61     17.71      66
  SPOT_CROSS           50c  0.50   -97.55   86.10   -37.76   16.7    41      8.05      66
  SPOT_CROSS          none  1.00    35.33  218.97   -34.58   15.2    61     23.90     126
  SPOT_CROSS          none  0.50   -70.83  112.81   -36.17   16.0    44     11.11     126
  MU_CROSS             10c  1.00  -191.95   -8.30   -38.66   17.0     7      2.98       5
  MU_CROSS             10c  0.50  -183.08    0.56   -38.66   17.0     2      0.86       5
  MU_CROSS             25c  1.00  -133.56   50.09   -38.66   17.0    29      8.84      19
  MU_CROSS             25c  0.50  -157.14   26.50   -38.66   17.0    13      3.79      19
  MU_CROSS             50c  1.00  -100.74   82.90   -38.66   17.0    42     17.71      51
  MU_CROSS             50c  0.50  -136.69   46.96   -38.66   17.0    33      8.05      51
  MU_CROSS            none  1.00    11.09  194.73   -34.58   15.2    43     23.90     126
  MU_CROSS            none  0.50   -82.64  101.00   -36.17   16.0    36     10.79     126
       'caught' is how many LOSING buys actually got a hedge under that cap.

  2/3. 90c AND DEARER: 1,124 buys, 711 closes, 42 losing closes,
       one win = $1.3812, total $9.07, worst -$38.66 = 28.0 wins.
  trigger                total$   cost$        95% CI on cost   worst$   wins  made  worstFA$
  SPOT_CROSS             103.03   93.96   [ -103.38,   308.09]   -34.58   25.0    40     23.37
  SPOT_CROSS_HOLD2        70.31   61.24   [ -134.75,   267.21]   -35.14   25.4    36     23.05
  MU_CROSS               110.68  101.61   [  -88.70,   294.69]   -34.58   25.0    23     23.32
  MU_CROSS_HOLD2         103.14   94.07   [  -80.94,   270.34]   -35.14   25.4    19     23.05
  MODEL_P90              117.89  108.82   [   15.07,   193.73]   -35.52   25.7     3     18.69
       'cost$' is profit given up, with a 95% bootstrap interval resampling CLOSES.
       'made' counts closes the hedge turned from a PROFIT into a LOSS; 'worstFA$' is
       the biggest single loss the hedge itself manufactured.

  4. THE OPERATOR'S IDEA TAKEN LITERALLY -- refuse the hedge when the other side
     is dear. A hedge at 90c does not cap a loss, it confirms one.
  trigger              cap  frac   total$   cost$   worst$   wins  made  worstFA$  caught
  SPOT_CROSS           10c  1.00   -10.46  -19.52   -38.58   27.9    23      2.98       5
  SPOT_CROSS           10c  0.50    -0.38   -9.45   -38.58   27.9     3      0.86       5
  SPOT_CROSS           25c  1.00    43.20   34.13   -38.58   27.9    35      8.84      15
  SPOT_CROSS           25c  0.50    26.14   17.07   -38.58   27.9    20      3.79      15
  SPOT_CROSS           50c  1.00    96.80   87.73   -37.76   27.3    40     17.71      34
  SPOT_CROSS           50c  0.50    56.23   47.16   -37.76   27.3    30      8.05      34
  SPOT_CROSS          none  1.00   103.03   93.96   -34.58   25.0    40     23.37      52
  SPOT_CROSS          none  0.50    58.41   49.34   -36.17   26.2    31     11.11      52
  MU_CROSS             10c  1.00   -12.62  -21.69   -38.66   28.0     8      2.98       1
  MU_CROSS             10c  0.50    -1.50  -10.57   -38.66   28.0     2      0.86       1
  MU_CROSS             25c  1.00    11.76    2.69   -38.66   28.0    18      8.84       8
  MU_CROSS             25c  0.50    11.72    2.65   -38.66   28.0    13      3.79       8
  MU_CROSS             50c  1.00    78.31   69.25   -38.66   28.0    23     17.71      27
  MU_CROSS             50c  0.50    47.52   38.45   -38.66   28.0    22      8.05      27
  MU_CROSS            none  1.00   110.68  101.61   -34.58   25.0    23     23.32      52
  MU_CROSS            none  0.50    62.82   53.75   -36.17   26.2    23     10.79      52
       'caught' is how many LOSING buys actually got a hedge under that cap.
```
