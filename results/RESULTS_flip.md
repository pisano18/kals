# RESULTS_flip -- can a hedge turn being wrong into a profit?

gate 0.990, entry from 55s, ceiling 98c

```
  HEDGE WHEN BELIEF IN OUR SIDE FALLS UNDER 90%
    entries 594, of which the side we bought LOST 29 (4.88%)
    the model flipped and a hedge was available on 63 (10.6%)
      on LOSING entries : 25 of 29 (86.2%)  <- the rescues
      on WINNING entries: 38 of 565 (6.7%)  <- the false alarms
    the two prices added: median 119.9c, p25 108.3c, best 65.0c
      UNDER 100c (a profit despite being wrong): 5 of 63 (7.9%)
    per contract, NO hedging  : +0.72c   total +4.26
    per contract, WITH hedging: +0.29c   total +1.71
    hedging is worth -0.43c per contract here

  HEDGE WHEN BELIEF IN OUR SIDE FALLS UNDER 70%
    entries 594, of which the side we bought LOST 29 (4.88%)
    the model flipped and a hedge was available on 45 (7.6%)
      on LOSING entries : 25 of 29 (86.2%)  <- the rescues
      on WINNING entries: 20 of 565 (3.5%)  <- the false alarms
    the two prices added: median 139.0c, p25 119.9c, best 69.0c
      UNDER 100c (a profit despite being wrong): 2 of 45 (4.4%)
    per contract, NO hedging  : +0.72c   total +4.26
    per contract, WITH hedging: +0.38c   total +2.27
    hedging is worth -0.33c per contract here

  HEDGE WHEN BELIEF IN OUR SIDE FALLS UNDER 50%
    entries 594, of which the side we bought LOST 29 (4.88%)
    the model flipped and a hedge was available on 40 (6.7%)
      on LOSING entries : 25 of 29 (86.2%)  <- the rescues
      on WINNING entries: 15 of 565 (2.7%)  <- the false alarms
    the two prices added: median 150.6c, p25 128.0c, best 69.0c
      UNDER 100c (a profit despite being wrong): 2 of 40 (5.0%)
    per contract, NO hedging  : +0.72c   total +4.26
    per contract, WITH hedging: +0.35c   total +2.08
    hedging is worth -0.37c per contract here

  HEDGE WHEN BELIEF IN OUR SIDE FALLS UNDER 30%
    entries 594, of which the side we bought LOST 29 (4.88%)
    the model flipped and a hedge was available on 32 (5.4%)
      on LOSING entries : 25 of 29 (86.2%)  <- the rescues
      on WINNING entries: 7 of 565 (1.2%)  <- the false alarms
    the two prices added: median 154.9c, p25 131.0c, best 85.0c
      UNDER 100c (a profit despite being wrong): 2 of 32 (6.2%)
    per contract, NO hedging  : +0.72c   total +4.26
    per contract, WITH hedging: +0.87c   total +5.18
    hedging is worth +0.15c per contract here

  HEDGE WHEN BELIEF IN OUR SIDE FALLS UNDER 10%
    entries 594, of which the side we bought LOST 29 (4.88%)
    the model flipped and a hedge was available on 26 (4.4%)
      on LOSING entries : 25 of 29 (86.2%)  <- the rescues
      on WINNING entries: 1 of 565 (0.2%)  <- the false alarms
    the two prices added: median 166.7c, p25 139.0c, best 97.0c
      UNDER 100c (a profit despite being wrong): 1 of 26 (3.8%)
    per contract, NO hedging  : +0.72c   total +4.26
    per contract, WITH hedging: +1.21c   total +7.20
    hedging is worth +0.49c per contract here
```
