# RESULTS_warn -- does confidence warn before a flip?

```
  complete closes on the index          : 18708
  closes the 0.995 gate would have BOUGHT : 18653
  of those, the bought side LOST         : 31 (0.17%)

  AFTER THE FIRST BUY, DID CONFIDENCE DROP BACK UNDER THE GATE?
  (a second buy is only blocked if it did, at that later second)

  tau | on closes that LOST   | on closes that WON
  ----|-----------------------|----------------------
   30s |     0 of 0        0.0% |     0 of 0        0.00%
   25s |    11 of 18      61.1% |    32 of 16919    0.19%
   20s |    12 of 19      63.2% |    28 of 17361    0.16%
   15s |    20 of 23      87.0% |    30 of 17736    0.17%
   10s |    27 of 29      93.1% |    17 of 18070    0.09%
    7s |    31 of 31     100.0% |    13 of 18361    0.07%
    5s |    30 of 31      96.8% |     9 of 18492    0.05%
    3s |    31 of 31     100.0% |     6 of 18569    0.03%

  EVER drops below the gate at any point after entry:
    losing closes :    31 of 31      100.0%   <- the protection
    winning closes:    80 of 18622     0.4%   <- the cost (blocks a good second buy)

  SO: 0 of 31 losing closes (0.0%) NEVER warned -- a second buy there is unprotected.

  THE NUMBER THAT DECIDES IT -- RISK OF A *SECOND* BUY, GIVEN THE GATE
  STILL PASSES AT THAT SECOND. Compare the two loss rates on each row:
  the left is every close still live at that tau, the right is only
  those whose confidence is STILL above the gate right then.

  tau | all still-live closes | gate STILL passing    | loss odds
  ----|-----------------------|-----------------------|----------
   25s |    18 lose of 16937   0.106% |     7 lose of 16894   0.041% |   0.39x
   20s |    19 lose of 17380   0.109% |     7 lose of 17340   0.040% |   0.37x
   15s |    23 lose of 17759   0.130% |     3 lose of 17709   0.017% |   0.13x
   10s |    29 lose of 18099   0.160% |     2 lose of 18055   0.011% |   0.07x
    7s |    31 lose of 18392   0.169% |     0 lose of 18348   0.000% |   0.00x
    5s |    31 lose of 18523   0.167% |     1 lose of 18484   0.005% |   0.03x
    3s |    31 lose of 18600   0.167% |     0 lose of 18563   0.000% |   0.00x

  A ratio under 1.00 means a second buy that still clears the gate is
  SAFER per contract than the first buy was. Above 1.00 means the gate
  has stopped protecting and a second buy is loading the bad closes.
```
