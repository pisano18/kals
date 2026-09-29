# Forecaster loss-cutting variants -- 2026-09-29

REPLAY FIRST, SO SAID FIRST: every number in the tables below is the tape population (offers that were displayed),
priced with the paper's 1-s survival rule, over the clean-room digest's 33 recorded days (TRAIN 08-25..09-17, TEST
09-18..09-26). It compares rules with each other on the same tape; it is NOT how often WE lose (2026-09-10 amendment).
About 31 versions were tried, so the best replay rows are flattered by selection; the forward paper
(research/cleanroom/fc_variants_paper.py, results/fcvar-paper.jsonl, READS_DUE 'fcvar-paper') is the test.

Operator 2026-09-29: "start working on methods that keep its great earning potential but minimizes losses and test
them on the side as a paper ... See if your version would've out earned or earned less or saved any losses."

## What was found

- Baseline replay: 793 markets, 18 losing, +$3,821 on $39,574 staked (9.7%); losses -$697 in losing markets.
- Offline screen of ~19,000 one- and two-condition removal rules on the fills: none cut losses without cutting more
  in wins on BOTH halves, except a 'quiet market' family resting on 4 losing fills -- which then failed as a full
  engine run (quiet12: -$889 TRAIN, -$448 TEST).
- Full engine runs (cap interactions included), 33 days combined:
  - **race05_98_hedge40** -- skip a buy when the index has closed half or more of its gap to the strike in the last
    5 s and the model is under 98%; buy the other side when the held side's belief drops under 40%:
    net +$3,840 vs +$3,822 (+$18), money lost in losing markets -$401 vs -$697 (-42%), 12 losing markets vs 18.
    TRAIN +$13 / TEST +$5 vs base; losses -35% / -61%. Passes the pre-registered bar on the replay TEST half.
  - **stable3_hedge40** -- buy only after the model has had the side at >= 90% on 3 straight decisions; same hedge:
    net +$3,018 vs +$3,822 (-21%), lost -$75 vs -$697 (-89%), 2 losing markets vs 18, 0 days below zero vs 2.
    Gives up money, so it FAILS the 'net >= 95% of base' bar; it is the 'lose far less' option.
  - hedge40 alone: +$61 net, +$60 losses saved (both halves positive, small).
  - one_side (never buy the second side): -$73 net -- the both-sides buys helped on the tape.
  - tighter edge / price floors / p95 / r20 / survive2 / age gates: each cut more wins than losses.
- Forward paper restarted 2026-09-29 01:51:06Z (pid 4025624) with base + 13 variants; the first run (01:28-01:50Z)
  showed its base does not match the separate paper forecaster fill for fill: two processes see the book at
  different instants and the 1-s check is sensitive to that (one check ran 0.37 s late under load). All variants
  inside one process see the identical book, so variant-vs-base is fair; the restart adds tick/lag timing to health.

## Full tables (replay)

REPLAY (tape population, 1-s survival rule) -- C:/Users/Joe/AppData/Local/Temp/claude/C--kals-repo/b2dbb5c1-92b0-452a-b1e9-86b7402d3a34/scratchpad/clean/fcvar2

TEST
| version | markets | losing | lost $ | net $ | return on stake | worst day $ | days < 0 | net vs base $ | losses saved vs base $ |
|---|---|---|---|---|---|---|---|---|---|
| base | 168 | 4 | -198 | +887 | 11.44% | +18 | 0 of 9 |  |  |
| age_max10 | 89 | 4 | -198 | +355 | 8.11% | -25 | 1 of 9 | -532 | +0 |
| age_max5 | 89 | 4 | -198 | +355 | 8.11% | -25 | 1 of 9 | -532 | +0 |
| age_min1 | 94 | 0 | 0 | +615 | 14.74% | +10 | 0 of 8 | -271 | +198 |
| edge3 | 140 | 4 | -198 | +796 | 12.78% | +15 | 0 of 9 | -91 | +0 |
| edge4 | 121 | 4 | -198 | +762 | 13.63% | +9 | 0 of 9 | -124 | +0 |
| floor80 | 140 | 1 | -85 | +579 | 9.3% | -23 | 1 of 9 | -308 | +113 |
| floor85 | 114 | 1 | -85 | +348 | 6.75% | -44 | 1 of 9 | -538 | +113 |
| flow_ok | 143 | 4 | -190 | +737 | 11.14% | +5 | 0 of 9 | -150 | +8 |
| hedge20 | 168 | 4 | -198 | +887 | 11.42% | +18 | 0 of 9 | +0 | +0 |
| hedge40 | 168 | 4 | -178 | +907 | 11.62% | +18 | 0 of 9 | +20 | +20 |
| hedge50 | 168 | 4 | -178 | +907 | 11.62% | +18 | 0 of 9 | +20 | +20 |
| no_toward5 | 132 | 3 | -97 | +781 | 13.25% | +9 | 0 of 9 | -106 | +101 |
| one_side | 168 | 4 | -199 | +885 | 11.44% | +18 | 0 of 9 | -1 | -1 |
| p95 | 122 | 1 | -85 | +596 | 10.62% | -18 | 1 of 9 | -291 | +113 |
| p98 | 108 | 0 | 0 | +608 | 12.38% | +2 | 0 of 9 | -279 | +198 |
| quiet12 | 87 | 3 | -113 | +439 | 10.24% | +12 | 0 of 9 | -448 | +85 |
| quiet12_race2 | 80 | 3 | -97 | +394 | 10.06% | +12 | 0 of 9 | -493 | +101 |
| r15 | 91 | 0 | 0 | +586 | 15.22% | +1 | 0 of 9 | -301 | +198 |
| r20 | 106 | 0 | 0 | +703 | 15.02% | +1 | 0 of 9 | -184 | +198 |
| race05_98 | 154 | 3 | -97 | +872 | 12.54% | +31 | 0 of 9 | -15 | +101 |
| race05_98_hedge40 | 154 | 3 | -77 | +892 | 12.73% | +31 | 0 of 9 | +5 | +121 |
| race05_99 | 152 | 3 | -97 | +871 | 12.55% | +31 | 0 of 9 | -15 | +101 |
| race1_98 | 157 | 3 | -97 | +887 | 12.47% | +31 | 0 of 9 | +0 | +101 |
| race2 | 161 | 4 | -182 | +842 | 11.41% | +8 | 0 of 9 | -45 | +16 |
| stable2 | 135 | 0 | 0 | +799 | 13.11% | +18 | 0 of 9 | -88 | +198 |
| stable2_race05_98_hedge40 | 128 | 0 | 0 | +767 | 13.23% | +10 | 0 of 9 | -120 | +198 |
| stable3 | 125 | 0 | 0 | +740 | 13.36% | +8 | 0 of 9 | -146 | +198 |
| stable3_hedge40 | 125 | 0 | 0 | +740 | 13.36% | +8 | 0 of 9 | -146 | +198 |
| stable3_p85 | 132 | 0 | 0 | +781 | 13.38% | +13 | 0 of 9 | -106 | +198 |
| stable3_race05_98_hedge40 | 122 | 0 | 0 | +727 | 13.39% | +8 | 0 of 9 | -160 | +198 |
| survive2 | 116 | 0 | 0 | +759 | 14.92% | +12 | 0 of 8 | -128 | +198 |

TRAIN
| version | markets | losing | lost $ | net $ | return on stake | worst day $ | days < 0 | net vs base $ | losses saved vs base $ |
|---|---|---|---|---|---|---|---|---|---|
| base | 625 | 14 | -499 | +2935 | 9.22% | -28 | 2 of 24 |  |  |
| age_max10 | 463 | 14 | -499 | +1964 | 7.82% | -28 | 3 of 24 | -971 | +0 |
| age_max5 | 461 | 14 | -499 | +1960 | 7.83% | -28 | 3 of 24 | -974 | +0 |
| age_min1 | 294 | 2 | -39 | +1512 | 10.84% | +7 | 0 of 24 | -1423 | +460 |
| edge3 | 480 | 11 | -478 | +2601 | 10.84% | -48 | 2 of 24 | -334 | +22 |
| edge4 | 388 | 8 | -341 | +2355 | 12.78% | -58 | 2 of 24 | -579 | +158 |
| floor80 | 582 | 12 | -445 | +2412 | 8.06% | -29 | 2 of 24 | -523 | +55 |
| floor85 | 518 | 8 | -348 | +1748 | 6.58% | -20 | 2 of 24 | -1187 | +151 |
| flow_ok | 518 | 7 | -198 | +2556 | 10.34% | +7 | 0 of 24 | -379 | +301 |
| hedge20 | 625 | 13 | -498 | +2938 | 9.22% | -28 | 2 of 24 | +3 | +2 |
| hedge40 | 625 | 13 | -460 | +2976 | 9.32% | -28 | 1 of 24 | +41 | +40 |
| hedge50 | 625 | 14 | -467 | +2964 | 9.28% | -28 | 1 of 24 | +29 | +32 |
| no_toward5 | 493 | 9 | -342 | +2297 | 9.51% | -48 | 2 of 24 | -637 | +157 |
| one_side | 625 | 16 | -552 | +2863 | 9.1% | -28 | 2 of 24 | -72 | -53 |
| p95 | 517 | 4 | -114 | +2342 | 8.93% | -8 | 1 of 24 | -593 | +385 |
| p98 | 430 | 1 | -51 | +1889 | 8.74% | -14 | 1 of 24 | -1046 | +448 |
| quiet12 | 457 | 13 | -423 | +2046 | 8.21% | -30 | 2 of 24 | -889 | +76 |
| quiet12_race2 | 447 | 9 | -275 | +2141 | 8.73% | -30 | 1 of 24 | -794 | +224 |
| r15 | 293 | 1 | -6 | +1655 | 11.36% | +9 | 0 of 24 | -1280 | +493 |
| r20 | 386 | 4 | -128 | +1981 | 10.41% | -48 | 1 of 24 | -954 | +371 |
| race05_98 | 596 | 10 | -352 | +2918 | 9.55% | -39 | 2 of 24 | -16 | +148 |
| race05_98_hedge40 | 596 | 9 | -324 | +2948 | 9.63% | -39 | 2 of 24 | +13 | +176 |
| race05_99 | 588 | 10 | -352 | +2864 | 9.55% | -40 | 2 of 24 | -70 | +148 |
| race1_98 | 602 | 10 | -352 | +2983 | 9.63% | -35 | 2 of 24 | +49 | +148 |
| race2 | 615 | 10 | -352 | +3029 | 9.65% | -35 | 2 of 24 | +95 | +148 |
| stable2 | 528 | 6 | -212 | +2384 | 8.89% | +23 | 0 of 24 | -550 | +287 |
| stable2_race05_98_hedge40 | 509 | 4 | -142 | +2366 | 9.06% | +21 | 0 of 24 | -569 | +358 |
| stable3 | 480 | 3 | -103 | +2248 | 9.19% | +8 | 0 of 24 | -686 | +397 |
| stable3_hedge40 | 480 | 2 | -75 | +2278 | 9.29% | +22 | 0 of 24 | -657 | +425 |
| stable3_p85 | 511 | 5 | -187 | +2398 | 9.17% | -53 | 1 of 24 | -537 | +313 |
| stable3_race05_98_hedge40 | 467 | 2 | -75 | +2217 | 9.23% | +22 | 0 of 24 | -717 | +425 |
| survive2 | 349 | 7 | -206 | +1637 | 10.48% | -29 | 2 of 24 | -1297 | +294 |


## Added 2026-09-29 ~05:30Z: quiet buys at double size (replay)

From the research synthesis (results/FC_RESEARCH_2026-09-29.md): buys with no trade in the market since close-45 s
had 0 losses on TRAIN (157) and TEST (79). quiet2x doubles the per-side cap in those markets, specified before it
was run (one configuration):

| version | split | markets | losing | lost $ | net $ | net vs base $ |
|---|---|---|---|---|---|---|
| quiet2x | TRAIN | 604 | 14 | -499 | +3212 | +277 |
| quiet2x | TEST | 155 | 4 | -198 | +1097 | +210 |
| race05_98_quiet2x | TRAIN | 575 | 10 | -352 | +3196 | +261 |
| race05_98_quiet2x | TEST | 141 | 3 | -97 | +1082 | +195 |

Fewer markets than base because the per-close cap (400) fills sooner. Forward paper: READS_DUE 'quiet2x-paper'.
