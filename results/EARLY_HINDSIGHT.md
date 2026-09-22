# EARLY_HINDSIGHT -- written by research/earlyhindsight.py

```
EARLY HINDSIGHT -- the 31-45 s leg at a third (live) vs full size vs off
generated 2026-09-22T14:31:06Z; ledger newest settlement 2026-09-22T14:30:08Z; 42 live run logs read (read-only); scorer code_sha256 dba91925d175b6f6

STATUS: REPORT ONLY -- this page never names a winner. The decision is FREEZE bar B1 (research/barcheck.py): its registered rule is in results/FREEZE_bars.json. So far 12 closes since the change as B1 counts them (watched or settled), 4 with a pin ledger row, 2 with an early-leg market.
  to see a $0.50 gap a WATCHED close FULL vs THIRD at 80% power needs ~297 watched closes (B1's unit; spread $3.07 a watched close, since the fixes, 216 watched closes)
  to see a $1.00 gap a WATCHED close FULL vs THIRD at 80% power needs ~75 watched closes (B1's unit; spread $3.07 a watched close, since the fixes, 216 watched closes)
  to see a $0.50 gap a WATCHED close FULL-lo vs THIRD at 80% power needs ~297 watched closes (B1's unit; spread $3.07 a watched close, since the fixes, 216 watched closes)
  to see a $1.00 gap a WATCHED close FULL-lo vs THIRD at 80% power needs ~75 watched closes (B1's unit; spread $3.07 a watched close, since the fixes, 216 watched closes)
  to see a $0.50 gap a WATCHED close OFF vs THIRD at 80% power needs ~99 watched closes (B1's unit; spread $1.77 a watched close, since the fixes, 216 watched closes)
  to see a $1.00 gap a WATCHED close OFF vs THIRD at 80% power needs ~25 watched closes (B1's unit; spread $1.77 a watched close, since the fixes, 216 watched closes)

Money: Kalshi's ledger (pinledger.pnl), pin series only. Tables count TRADED closes (a pin ledger row); B1 counts watched closes (~2.8x as many). Every policy = LIVE + a delta on early-leg entries, their hedge share, top-ups and budget-squeezed later legs, priced on the book the bot logged (counterfactual, not fills). FULL holds price-through fills at what filled; FULL-lo is FULL with every market resting on something unlogged at its worst reading and zero. ET days.

A. SINCE v-early-third (closes after 2026-09-22T11:42:12Z; live runs the early leg at a third)
--------------------------------------------------------------------------------
  LIVE = actual (third). FULL = early entries at full size, capped by the depth logged at that second and by the bot's own budget_left. OFF = early entries and their hedge share removed (markets NOT handed to the <=30 s window).
  minimum detectable difference (80 % power, 5 % two-sided), n = 4 traded closes (a pin ledger row):
    FULL - LIVE: $3.69 total ($0.923/close); sd $0.66/close; 1 of 4 closes differ at all
    FULL-lo - LIVE: $3.69 total ($0.923/close); sd $0.66/close; 1 of 4 closes differ at all
    OFF - LIVE: $3.20 total ($0.801/close); sd $0.57/close; 2 of 4 closes differ at all
  ET day     closes       LIVE       FULL    FULL-lo        OFF   $/close LIVE/FULL/FULL-lo/OFF   losing closes LIVE/FULL/FULL-lo/OFF   P(FULL>LIVE) P(FULL-lo>LIVE) P(OFF>LIVE)
  2026-09-22      4      +7.68      +8.99      +8.99      +6.37   +1.92/+2.25/+2.25/+1.59   0/0/0/0          -        -        -
  ALL             4      +7.68      +8.99      +8.99      +6.37   +1.92/+2.25/+2.25/+1.59   0/0/0/0          -        -        -
  no P value below 30 closes (4 here): with this few, one close decides it.
  resizing tallies (closes in A):
    FULL  early legs scaled up 2
          capped by the depth logged at that second 1
          budget from the bot's own budget_left 2
          top-ups trimmed (already held SIZE) 1
          top-up contracts cut 52.7
    OFF   top-ups kept as run 1
          markets removed entirely (set to exactly $0) 1
            |logs-vs-ledger rounding| dropped with them, $ 0.0

B. PAPER ARMS -- paper -- HYPOTHESIS (their own `settled` records; no ledger; paper fills never lose a race)
------------------------------------------------------------------------
  arm-early-full: pinrun-paper-20260922T114641Z.jsonl, pinrun-paper-20260922T120203Z.jsonl (early_frac 1.0, early window to 45 s, SIZE 79.0); started 2026-09-22T11:46:41Z
    flag exercised: 5 early-leg signals of 10, 5 at the full size cap
    COLLECTING (< 30 closes). MDE on 6 shared closes (either traded): $7.23 total
    arm +12.48 vs live +7.68 ($/close +2.08 vs +1.28); losing closes 0 vs 0; P(arm > live) - (none below 30 closes)
    markets traded by both: 5; arm only: 3; live only: 0 (different markets = not like-for-like)
  arm-early-off: pinrun-paper-20260922T062050Z.jsonl, pinrun-paper-20260922T114638Z.jsonl, pinrun-paper-20260922T120200Z.jsonl (early_frac 0.5, early window to 30 s = leg OFF, SIZE 79.0); started 2026-09-22T06:20:50Z
    flag exercised: 0 early-leg signals of 14, 0 at the full size cap
    COLLECTING (< 30 closes). MDE on 4 shared closes (either traded): $9.39 total
    arm +2.94 vs live +7.68 ($/close +0.74 vs +1.92); losing closes 0 vs 0; P(arm > live) - (none below 30 closes)
    markets traded by both: 4; arm only: 0; live only: 1 (different markets = not like-for-like)

C. CALIBRATION -- 2026-09-17T13:05:02Z .. 2026-09-22T11:42:12Z; the early leg as run: third 09-17 13:05Z..09-17 19:30Z; full 09-17 19:41Z..09-18 01:45Z; off 09-18 01:48Z..09-18 03:00Z; third 09-18 03:02Z..09-18 16:30Z; full 09-18 16:33Z..09-22 11:30Z; third 09-22 11:41Z..09-22 11:42Z
--------------------------------------------------------------------------------
  calibration, not the test. LIVE = what actually ran. THIRD/FULL/OFF = every early entry resized to that policy (hours already at that size are unchanged).
  minimum detectable difference (80 % power, 5 % two-sided), n = 205 traded closes (a pin ledger row):
    THIRD - LIVE: $339.15 total ($1.654/close); sd $8.45/close; 108 of 205 closes differ at all
    FULL - LIVE: $21.64 total ($0.106/close); sd $0.54/close; 26 of 205 closes differ at all
    FULL-lo - LIVE: $140.33 total ($0.685/close); sd $3.50/close; 27 of 205 closes differ at all
    OFF - LIVE: $512.87 total ($2.502/close); sd $12.79/close; 152 of 205 closes differ at all
  ET day     closes       LIVE      THIRD       FULL    FULL-lo        OFF   $/close LIVE/THIRD/FULL/FULL-lo/OFF   losing closes LIVE/THIRD/FULL/FULL-lo/OFF   P(THIRD>LIVE) P(FULL>LIVE) P(FULL-lo>LIVE) P(OFF>LIVE)
  2026-09-17     31     +78.55     +72.43     +89.12     +89.12     +58.53   +2.53/+2.34/+2.87/+2.87/+1.89   1/1/1/1/0       0.28     1.00     1.00     0.14
  2026-09-18     43     +91.85     +70.23    +118.89     +69.01     +32.95   +2.14/+1.63/+2.76/+1.60/+0.77   0/0/0/1/0       0.00     1.00     0.37     0.00
  2026-09-19     54    -223.46    -101.91    -223.46    -223.46     -48.85   -4.14/-1.89/-4.14/-4.14/-0.90   5/5/5/5/2       0.88     0.50     0.50     0.86
  2026-09-20     34    +109.63     +62.40    +109.63    +109.63     +35.42   +3.22/+1.84/+3.22/+3.22/+1.04   0/0/0/0/0       0.00     0.50     0.50     0.00
  2026-09-21     36      -2.97     +25.40      -2.97      -2.97     +44.14   -0.08/+0.71/-0.08/-0.08/+1.23   2/2/2/2/0       0.74     0.50     0.50     0.75
  2026-09-22      7     +10.06      +5.13     +10.06     +10.06      +2.52   +1.44/+0.73/+1.44/+1.44/+0.36   0/0/0/0/0          -        -        -        -
  ALL           205     +63.66    +133.69    +101.26     +51.38    +124.72   +0.31/+0.65/+0.49/+0.25/+0.61   8/8/8/9/2       0.69     1.00     0.40     0.60
  chance each is the BEST of LIVE/THIRD/FULL/FULL-lo/OFF over the whole window (close-clustered bootstrap): LIVE 0.00, THIRD 0.16, FULL 0.40, FULL-lo 0.03, OFF 0.41

C2. same, only since the fixes (closes from 09-20 00:00 ET = 2026-09-20T04:00:00Z)
--------------------------------------------------------------------------------
  minimum detectable difference (80 % power, 5 % two-sided), n = 77 traded closes (a pin ledger row):
    THIRD - LIVE: $126.97 total ($1.649/close); sd $5.16/close; 50 of 77 closes differ at all
    FULL - LIVE: $0.00 total ($0.000/close); sd $0.00/close; 0 of 77 closes differ at all
    FULL-lo - LIVE: $0.00 total ($0.000/close); sd $0.00/close; 0 of 77 closes differ at all
    OFF - LIVE: $198.52 total ($2.578/close); sd $8.08/close; 57 of 77 closes differ at all
  ET day     closes       LIVE      THIRD       FULL    FULL-lo        OFF   $/close LIVE/THIRD/FULL/FULL-lo/OFF   losing closes LIVE/THIRD/FULL/FULL-lo/OFF   P(THIRD>LIVE) P(FULL>LIVE) P(FULL-lo>LIVE) P(OFF>LIVE)
  2026-09-20     34    +109.63     +62.40    +109.63    +109.63     +35.42   +3.22/+1.84/+3.22/+3.22/+1.04   0/0/0/0/0       0.00     0.50     0.50     0.00
  2026-09-21     36      -2.97     +25.40      -2.97      -2.97     +44.14   -0.08/+0.71/-0.08/-0.08/+1.23   2/2/2/2/0       0.74     0.50     0.50     0.75
  2026-09-22      7     +10.06      +5.13     +10.06     +10.06      +2.52   +1.44/+0.73/+1.44/+1.44/+0.36   0/0/0/0/0          -        -        -        -
  ALL            77    +116.72     +92.94    +116.72    +116.72     +82.09   +1.52/+1.21/+1.52/+1.52/+1.07   2/2/2/2/0       0.27     0.50     0.50     0.28
  chance each is the BEST of LIVE/THIRD/FULL/FULL-lo/OFF over the whole window (close-clustered bootstrap): LIVE 0.24, THIRD 0.02, FULL 0.24, FULL-lo 0.24, OFF 0.27
  resizing tallies (closes in C):
    THIRD later legs the budget bound as run (a smaller policy could have bought more: NOT modelled) 4
          top-ups kept as run 3
          hedges resized 5
          markets with a moved early fill cut down (really filled) 9
            this policy's $ difference from LIVE on those 64.5
    FULL  early legs scaled up 41
          capped by the depth logged at that second 15
          capped at an IOC partial fill 5
          price-through fills held at the count that filled 1
          budget rebuilt from the start record 41
          later legs of other markets squeezed by the budget 1
          contracts cut from them 73.0
          top-ups trimmed (already held SIZE) 3
          top-up contracts cut 190.8
          markets removed entirely (set to exactly $0) 1
            |logs-vs-ledger rounding| dropped with them, $ 0.0
          markets resting on something unlogged (-lo set) 2
            this policy's $ difference from LIVE on those 0.6
            -lo minus the headline on those, $ -49.9
    OFF   later legs the budget bound as run (a smaller policy could have bought more: NOT modelled) 5
          top-ups kept as run 6
          hedges resized 6
          markets removed entirely (set to exactly $0) 199
            |logs-vs-ledger rounding| dropped with them, $ 0.8
          markets with a moved early fill cut down (really filled) 11
            this policy's $ difference from LIVE on those 91.0

D. WHAT IS NOT MODELLED, AND HOW OFTEN IT COULD MATTER
-------------------------------------------------------
  A: 4 closes, 2 with an early-leg market. close_budget refusals: 0 (0 in early-leg closes).
     A smaller early leg would have left room for >= 1 contract in 0 of them at a third (0 contracts of room over 0 closes), 0 with the leg off (0 over 0 closes). The gate fires before the book is read, so whether those markets were tradeable is unknown. NOT modelled: upside for the smaller leg. 0 refusals carry no budget at all.
     max_per_market refusals: 1, 1 of them on early-leg markets (FULL buys in one fill, freeing a slot a late boost could use: NOT modelled).
  C: 205 closes, 152 with an early-leg market. close_budget refusals: 200 (178 in early-leg closes).
     A smaller early leg would have left room for >= 1 contract in 169 of them at a third (3512 contracts of room over 34 closes), 178 with the leg off (5300 over 35 closes). The gate fires before the book is read, so whether those markets were tradeable is unknown. NOT modelled: upside for the smaller leg. 0 refusals carry no budget at all.
     max_per_market refusals: 17, 6 of them on early-leg markets (FULL buys in one fill, freeing a slot a late boost could use: NOT modelled).
  FULL's budget: A 0 early scale-ups cut by the close budget, 0 later legs of other markets squeezed (both MODELLED); C 0 and 1.
  A FULL: 0 price-through early fills (landed >= 2c under what the logged book said) held at the count that filled -> $+0.00; their extra contracts at the landing price would be $+0.00, at the decision-time book $+0.00. 0 markets landed >= 2c dearer. FULL-lo: 0 markets rest on something unlogged (moved fill, no depth, past the ladder, hedge scaled up at its average price); FULL there $+0.00, FULL-lo $+0.00.
  C FULL: 1 price-through early fills (landed >= 2c under what the logged book said) held at the count that filled -> $+0.00; their extra contracts at the landing price would be $+8.68, at the decision-time book $-49.32. 1 markets landed >= 2c dearer. FULL-lo: 2 markets rest on something unlogged (moved fill, no depth, past the ladder, hedge scaled up at its average price); FULL there $+0.56, FULL-lo $-49.32.
  C THIRD: 9 markets with a moved early fill cut down; THIRD's difference from LIVE there $+64.48 (those contracts really filled; only a partial cut's price split is approximate).
  C OFF: 11 markets with a moved early fill cut down; OFF's difference from LIVE there $+91.00 (those contracts really filled; only a partial cut's price split is approximate).
  FULL upper bounds: early entries with no logged depth A 0 / C 0; hedge scale-ups whose depth past `asked` was never read A 0 / C 0.
  OFF keeps top-ups as they ran and never hands a market to the <=30 s window (critic G2: 163 of 203 early markets were never offered at 90-98c later, tape): top-up fills A 1, C 6 -- OFF is a lower bound there.
  THIRD in C cannot add top-ups a full-size bot never sent (lower bound). Not modelled anywhere: a different early size changing which market a scan picks, hedge timing, or the loss-cap/brake state.

E. LEDGER vs LOGS
-----------------
  A: early-leg markets 2; hedged markets 0; ledger markets the logs never saw (identical in every policy) 0; markets whose ledger entry-side contracts differ from the logged fills by > 0.5: 0 (net +0.0 contracts); log fills with no ledger row yet: 0
  C: early-leg markets 205; hedged markets 8; ledger markets the logs never saw (identical in every policy) 0; markets whose ledger entry-side contracts differ from the logged fills by > 0.5: 0 (net +0.0 contracts); log fills with no ledger row yet: 0

Multiple looks: 46 P-values on this page; by chance alone about 4.6 of them land under 0.05 or over 0.95. None of them decides anything (B1 does).
```
