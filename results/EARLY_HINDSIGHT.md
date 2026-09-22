# EARLY_HINDSIGHT -- written by research/earlyhindsight.py

```
EARLY HINDSIGHT -- the 31-45 s leg at a third (live) vs full size vs off
generated 2026-09-22T13:38:47Z; ledger newest settlement 2026-09-22T13:00:08Z; 42 live run logs read (read-only)

STATUS: COLLECTING -- 2 settled closes since the change, 1 of them with an early-leg market; nothing is called before 30 such closes.
  to see a $0.50/close gap FULL vs THIRD at 80% power needs ~838 closes (per-close spread $5.16, calibration since the fixes, 77 closes)
  to see a $1.00/close gap FULL vs THIRD at 80% power needs ~210 closes (per-close spread $5.16, calibration since the fixes, 77 closes)
  to see a $0.50/close gap OFF vs THIRD at 80% power needs ~277 closes (per-close spread $2.97, calibration since the fixes, 77 closes)
  to see a $1.00/close gap OFF vs THIRD at 80% power needs ~70 closes (per-close spread $2.97, calibration since the fixes, 77 closes)

Money: Kalshi's ledger (pinledger.pnl), pin series only; n = closes. Every policy = LIVE + a delta on early-leg entries, their hedge share, top-ups and budget-squeezed later legs, priced on the book the bot logged (counterfactual, not fills). ET days.

A. SINCE v-early-third (closes after 2026-09-22T11:42:12Z; live runs the early leg at a third)
--------------------------------------------------------------------------------
  LIVE = actual (third). FULL = early entries at full size, capped by the depth logged at that second and by the bot's own budget_left. OFF = early entries and their hedge share removed (markets NOT handed to the <=30 s window).
  minimum detectable difference (80 % power, 5 % two-sided), n = 2 closes:
    FULL - LIVE: $3.69 total ($1.847/close); sd $0.93/close; 1 of 2 closes differ at all
    OFF - LIVE: $3.30 total ($1.651/close); sd $0.83/close; 1 of 2 closes differ at all
  ET day     closes       LIVE       FULL        OFF   $/close LIVE/FULL/OFF   losing closes LIVE/FULL/OFF   P(FULL>LIVE) P(OFF>LIVE)
  2026-09-22      2      +5.37      +6.69      +4.19   +2.69/+3.35/+2.10   0/0/0       0.87     0.13
  ALL             2      +5.37      +6.69      +4.19   +2.69/+3.35/+2.10   0/0/0       0.87     0.13
  chance each is the BEST of LIVE/FULL/OFF over the whole window (close-clustered bootstrap): LIVE 0.08, FULL 0.84, OFF 0.08
  resizing tallies (closes in A):
    FULL  early legs scaled up 1
          budget from the bot's own budget_left 1
          top-ups trimmed (already held SIZE) 1
          top-up contracts cut 52.7
    OFF   top-ups kept as run 1

B. PAPER ARMS -- paper -- HYPOTHESIS (their own `settled` records; no ledger; paper fills never lose a race)
------------------------------------------------------------------------
  arm-early-full: pinrun-paper-20260922T120203Z.jsonl (early_frac 1.0, early window to 45 s, SIZE 79.0); started 2026-09-22T12:02:03Z
    flag exercised: 4 early-leg signals of 6, 4 at the full size cap
    COLLECTING (< 30 closes). MDE on 3 shared closes (either traded): $1.20 total
    arm +6.27 vs live +5.37 ($/close +2.09 vs +1.79); losing closes 0 vs 0; P(arm > live) 1.00
    markets traded by both: 2; arm only: 2; live only: 0 (different markets = not like-for-like)
  arm-early-off: pinrun-paper-20260922T120200Z.jsonl (early_frac 0.5, early window to 30 s = leg OFF, SIZE 79.0); started 2026-09-22T12:02:00Z
    flag exercised: 0 early-leg signals of 4, 0 at the full size cap
    COLLECTING (< 30 closes). MDE on 2 shared closes (either traded): $7.07 total
    arm +1.47 vs live +5.37 ($/close +0.74 vs +2.69); losing closes 0 vs 0; P(arm > live) 0.00
    markets traded by both: 2; arm only: 0; live only: 0 (different markets = not like-for-like)

C. CALIBRATION -- 2026-09-17T13:05:02Z .. 2026-09-22T11:42:12Z; the early leg as run: third 09-17 13:05Z..09-17 19:30Z; full 09-17 19:41Z..09-18 01:45Z; off 09-18 01:48Z..09-18 03:00Z; third 09-18 03:02Z..09-18 16:30Z; full 09-18 16:33Z..09-22 11:30Z; third 09-22 11:41Z..09-22 11:42Z
--------------------------------------------------------------------------------
  calibration, not the test. LIVE = what actually ran. THIRD/FULL/OFF = every early entry resized to that policy (hours already at that size are unchanged).
  minimum detectable difference (80 % power, 5 % two-sided), n = 205 closes:
    THIRD - LIVE: $339.15 total ($1.654/close); sd $8.45/close; 108 of 205 closes differ at all
    FULL - LIVE: $32.16 total ($0.157/close); sd $0.80/close; 27 of 205 closes differ at all
    OFF - LIVE: $512.87 total ($2.502/close); sd $12.79/close; 152 of 205 closes differ at all
  ET day     closes       LIVE      THIRD       FULL        OFF   $/close LIVE/THIRD/FULL/OFF   losing closes LIVE/THIRD/FULL/OFF   P(THIRD>LIVE) P(FULL>LIVE) P(OFF>LIVE)
  2026-09-17     31     +78.55     +72.43     +89.12     +58.53   +2.53/+2.34/+2.87/+1.89   1/1/1/0       0.28     1.00     0.14
  2026-09-18     43     +91.85     +70.23    +127.57     +32.95   +2.14/+1.63/+2.97/+0.77   0/0/0/0       0.00     1.00     0.00
  2026-09-19     54    -223.46    -101.91    -223.46     -48.85   -4.14/-1.89/-4.14/-0.90   5/5/5/2       0.88     0.50     0.86
  2026-09-20     34    +109.63     +62.40    +109.63     +35.42   +3.22/+1.84/+3.22/+1.04   0/0/0/0       0.00     0.50     0.00
  2026-09-21     36      -2.97     +25.40      -2.97     +44.14   -0.08/+0.71/-0.08/+1.23   2/2/2/0       0.74     0.50     0.75
  2026-09-22      7     +10.06      +5.13     +10.06      +2.52   +1.44/+0.73/+1.44/+0.36   0/0/0/0       0.00     0.50     0.00
  ALL           205     +63.66    +133.69    +109.94    +124.72   +0.31/+0.65/+0.54/+0.61   8/8/8/2       0.69     1.00     0.60
  chance each is the BEST of LIVE/THIRD/FULL/OFF over the whole window (close-clustered bootstrap): LIVE 0.00, THIRD 0.14, FULL 0.46, OFF 0.41

C2. same, only since the fixes (closes from 09-20 00:00 ET = 2026-09-20T04:00:00Z)
--------------------------------------------------------------------------------
  minimum detectable difference (80 % power, 5 % two-sided), n = 77 closes:
    THIRD - LIVE: $126.97 total ($1.649/close); sd $5.16/close; 50 of 77 closes differ at all
    FULL - LIVE: $0.00 total ($0.000/close); sd $0.00/close; 0 of 77 closes differ at all
    OFF - LIVE: $198.52 total ($2.578/close); sd $8.08/close; 57 of 77 closes differ at all
  ET day     closes       LIVE      THIRD       FULL        OFF   $/close LIVE/THIRD/FULL/OFF   losing closes LIVE/THIRD/FULL/OFF   P(THIRD>LIVE) P(FULL>LIVE) P(OFF>LIVE)
  2026-09-20     34    +109.63     +62.40    +109.63     +35.42   +3.22/+1.84/+3.22/+1.04   0/0/0/0       0.00     0.50     0.00
  2026-09-21     36      -2.97     +25.40      -2.97     +44.14   -0.08/+0.71/-0.08/+1.23   2/2/2/0       0.74     0.50     0.75
  2026-09-22      7     +10.06      +5.13     +10.06      +2.52   +1.44/+0.73/+1.44/+0.36   0/0/0/0       0.00     0.50     0.00
  ALL            77    +116.72     +92.94    +116.72     +82.09   +1.52/+1.21/+1.52/+1.07   2/2/2/0       0.27     0.50     0.28
  chance each is the BEST of LIVE/THIRD/FULL/OFF over the whole window (close-clustered bootstrap): LIVE 0.35, THIRD 0.02, FULL 0.35, OFF 0.27
  resizing tallies (closes in C):
    THIRD later legs the budget bound as run (a smaller policy could have bought more: NOT modelled) 4
          top-ups kept as run 3
          hedges resized 5
          markets whose early fill landed >= 2c off the price decided on 8
            this policy's $ difference from LIVE on those (depth at landing unknown) 68.2
    FULL  early legs scaled up 41
          capped by the depth logged at that second 14
          capped at an IOC partial fill 5
          budget rebuilt from the start record 41
          later legs of other markets squeezed by the budget 1
          contracts cut from them 73.0
          top-ups trimmed (already held SIZE) 3
          top-up contracts cut 190.8
          hedges resized 1
          hedges scaled up 1
          hedge scale-up with depth past `asked` never read -> UPPER bound 1
          markets removed entirely (set to exactly $0) 1
            |logs-vs-ledger rounding| dropped with them, $ 0.0
          markets whose early fill landed >= 2c off the price decided on 2
            this policy's $ difference from LIVE on those (depth at landing unknown) 9.2
    OFF   later legs the budget bound as run (a smaller policy could have bought more: NOT modelled) 5
          top-ups kept as run 6
          hedges resized 6
          markets removed entirely (set to exactly $0) 199
            |logs-vs-ledger rounding| dropped with them, $ 0.8
          markets whose early fill landed >= 2c off the price decided on 10
            this policy's $ difference from LIVE on those (depth at landing unknown) 97.1

D. WHAT IS NOT MODELLED, AND HOW OFTEN IT COULD MATTER
-------------------------------------------------------
  A: 2 closes, 1 with an early-leg market. close_budget refusals: 0 (0 in early-leg closes).
     In 0 of those the early leg already held more than the shortfall, so a smaller early leg (THIRD/OFF) would have let the bot at least look at the market; the gate fires before the book is read, so whether it was tradeable is unknown. NOT modelled (upside for the smaller leg). 0 refusals carry no budget at all.
     max_per_market refusals: 1, 1 of them on early-leg markets (FULL buys in one fill, freeing a slot a late boost could use: NOT modelled).
  C: 205 closes, 152 with an early-leg market. close_budget refusals: 200 (178 in early-leg closes).
     In 178 of those the early leg already held more than the shortfall, so a smaller early leg (THIRD/OFF) would have let the bot at least look at the market; the gate fires before the book is read, so whether it was tradeable is unknown. NOT modelled (upside for the smaller leg). 0 refusals carry no budget at all.
     max_per_market refusals: 17, 6 of them on early-leg markets (FULL buys in one fill, freeing a slot a late boost could use: NOT modelled).
  FULL's budget: A 0 early scale-ups cut by the close budget, 0 later legs of other markets squeezed (both MODELLED); C 0 and 1.
  FULL upper bounds: early entries with no logged depth A 0 / C 0; hedge scale-ups whose depth past `asked` was never read A 0 / C 1; extra hedge contracts priced at the market's average hedge price (a deeper hedge pays more).
  C THIRD: 8 markets had an early fill land >= 2c off the price decided on (critic C6); THIRD's difference from LIVE on them is $+68.25. Those contracts really filled; only the price split of a partial cut is approximate.
  C FULL: 2 markets had an early fill land >= 2c off the price decided on (critic C6); FULL's difference from LIVE on them is $+9.24. Its extra contracts assume the landing book had depth nobody logged: treat as unknown sign.
  C OFF: 10 markets had an early fill land >= 2c off the price decided on (critic C6); OFF's difference from LIVE on them is $+97.10. Those contracts really filled; only the price split of a partial cut is approximate.
  OFF keeps top-ups as they ran and never hands a market to the <=30 s window (critic G2: 163 of 203 early markets were never offered at 90-98c later, tape): top-up fills A 1, C 6 -- OFF is a lower bound there.
  THIRD in C cannot add top-ups a full-size bot never sent (lower bound). Not modelled anywhere: a different early size changing which market a scan picks, hedge timing, or the loss-cap/brake state.

E. LEDGER vs LOGS
-----------------
  A: early-leg markets 1; hedged markets 0; ledger markets the logs never saw (identical in every policy) 0; markets whose ledger entry-side contracts differ from the logged fills by > 0.5: 0 (net +0.0 contracts); log fills with no ledger row yet: 0
  C: early-leg markets 205; hedged markets 8; ledger markets the logs never saw (identical in every policy) 0; markets whose ledger entry-side contracts differ from the logged fills by > 0.5: 0 (net +0.0 contracts); log fills with no ledger row yet: 0

Multiple looks: 37 P-values on this page; by chance alone about 3.7 of them land under 0.05 or over 0.95. Per-day cells are description, not tests.
```
