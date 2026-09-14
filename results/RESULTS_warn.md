# RESULTS_warn -- does confidence warn before a flip?

```
  complete closes on the index          : 19034
  closes the 0.995 gate would have BOUGHT : 18929
  of those, the bought side LOST         : 98 (0.52%)

  AFTER THE FIRST BUY, DID CONFIDENCE DROP BACK UNDER THE GATE?
  (a second buy is only blocked if it did, at that later second)

  tau | on closes that LOST   | on closes that WON
  ----|-----------------------|----------------------
   55s |     0 of 0        0.0% |     0 of 0        0.00%
   50s |    25 of 63      39.7% |   116 of 14477    0.80%
   45s |    37 of 67      55.2% |   140 of 15205    0.92%
   40s |    52 of 70      74.3% |   132 of 15780    0.84%
   35s |    66 of 77      85.7% |   125 of 16338    0.77%
   30s |    70 of 85      82.4% |    96 of 16845    0.57%
   25s |    80 of 88      90.9% |    90 of 17303    0.52%
   20s |    80 of 88      90.9% |    62 of 17700    0.35%
   15s |    88 of 91      96.7% |    46 of 18045    0.25%
   10s |    94 of 97      96.9% |    25 of 18357    0.14%
    5s |    97 of 98      99.0% |    10 of 18630    0.05%

  EVER drops below the gate at any point after entry:
    losing closes :    98 of 98      100.0%   <- the protection
    winning closes:   382 of 18831     2.0%   <- the cost (blocks a good second buy)

  SO: 0 of 98 losing closes (0.0%) NEVER warned -- a second buy there is unprotected.

  THE NUMBER THAT DECIDES IT -- RISK OF A *SECOND* BUY, GIVEN THE GATE
  STILL PASSES AT THAT SECOND. Compare the two loss rates on each row:
  the left is every close still live at that tau, the right is only
  those whose confidence is STILL above the gate right then.

  tau | all still-live closes | gate STILL passing    | loss odds
  ----|-----------------------|-----------------------|----------
   50s |    63 lose of 14540   0.433% |    38 lose of 14399   0.264% |   0.61x
   45s |    67 lose of 15272   0.439% |    30 lose of 15095   0.199% |   0.45x
   40s |    70 lose of 15850   0.442% |    18 lose of 15666   0.115% |   0.26x
   35s |    77 lose of 16415   0.469% |    11 lose of 16224   0.068% |   0.14x
   30s |    85 lose of 16930   0.502% |    15 lose of 16764   0.089% |   0.18x
   25s |    88 lose of 17391   0.506% |     8 lose of 17221   0.046% |   0.09x
   20s |    88 lose of 17788   0.495% |     8 lose of 17646   0.045% |   0.09x
   15s |    91 lose of 18136   0.502% |     3 lose of 18002   0.017% |   0.03x
   10s |    97 lose of 18454   0.526% |     3 lose of 18335   0.016% |   0.03x
    5s |    98 lose of 18728   0.523% |     1 lose of 18621   0.005% |   0.01x

  A ratio under 1.00 means a second buy that still clears the gate is
  SAFER per contract than the first buy was. Above 1.00 means the gate
  has stopped protecting and a second buy is loading the bad closes.
```
