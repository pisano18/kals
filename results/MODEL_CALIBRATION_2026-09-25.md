# MODEL_CALIBRATION_2026-09-25 -- is the live model's P(win) right?

Written 2026-09-25 ~07:5xZ. Read-only. Sources, in the order CLAUDE.md ranks
them: (1) the settlement index tape `C:\kals\kalshi_data\cfbenchmarks_value`
(streamed hour by hour, torn hours salvaged with `gzsalvage.iter_lines`),
(3) our own fills (`results/pinrun-live-202609*.jsonl` signal+order records)
with Kalshi's own outcome (`results/kalshi_ledger.json` market_result). No
replay, no order book. **Nothing from the tape below is our loss rate** (rule
5): the tape says what the index did and what the model computed. Our own
loss numbers come only from section 6 (live fills).

Scripts (each self-tested with a planted answer, all PASS):
`scratchpad/power/calib/calibrun.py` (tape pass, calls `pinrun.fair`,
`pinrun.projection`, `IndexWS.sigma/partial/spot` through a socket-less stub;
self-test proves equality with independent arithmetic on 200 random cases, a
Gaussian world reads 0.74x, a planted-jump world 10x at P>=0.99),
`livepass.py` (our fills re-priced from the tape), `analyse.py` (tables;
planted 1x reads 1.07x, planted 8x reads 8.30x), `money.py`.

## 0. Answer

1. **The model is overconfident only where it says "near-certain" (P > 0.999),
   and there it is badly wrong: 20-80x.** At 45 s it says the favoured side
   loses about 1 time in 50,000; the index made it lose 24 times in 15,363
   (1 in 640). At 30 s: 9 in 17,174 (1 in 1,900) vs a claimed 1 in 90,000.
   At 10 s and 5 s: 0 losses in ~38,000 cells -- the late seconds are safe.
2. **Below 0.995 the model is roughly right** (1-2x at 45/30 s, inside what the
   sample can tell apart). In the 0.995-0.999 band it is 2-8x, significant
   only at 30 s (6 lost of 356, 6.8x; smallest detectable 4.7x).
3. **It has improved.** First 70% of closes 17.4x, last 30% 5.1x; week from
   09-22: 0 lost of 12,243 gated cells.
4. **Sigma does NOT under-react after a volatility jump in a way that matters.**
   In every bucket the next seconds' actual 1-s move is SMALLER than the 300 s
   ruler (median 0.53-0.81 of it). Losses are sudden moves inside the last
   window, not a stale ruler: a max(300 s, 60 s) ruler cut the tape's gated
   losses only 59 -> 54 (holdout 6 -> 6).
5. **No proposal pays on our own fills.** Tested on the 908 fills (862 markets,
   19 of which our side lost) from 09-08..09-24. Each proposal refuses our
   losers only by refusing far more of our winners. Settlement-value net,
   hedges ignored: tail multiplier -$229, 60 s ruler -$359, 3600 s ruler
   -$424, floor 0.999 -$389, floor 0.999 only at tau>=30 -$13. **Recommend
   none for live.** Why the tape gain does not transfer: the tape's losses
   sit in the P>0.999 cells, where a 97-99c price leaves no edge to cut; our
   fills and losers sit at logged P 0.995-0.999 and at prices where the
   model's edge is real on average. What makes our fills lose (2.2% of
   markets vs the tape's ~0.05% of gated cells -- about 40x) is who sells to
   us, which the index cannot see. That is the same gap rule 5 records.

## 1. Method (what exactly was computed)

- 11 index ids on the tape (`TONUSD_RTI` is not on it; ADA and BCH have no
  live market, strike = previous settle unrounded, reported separately and
  excluded from the pooled tables). 2,140 closes from 2026-09-01 00:30Z to
  2026-09-25 07:00Z; 141,240 (index, close, tau) cells; 1,210 index-closes
  skipped for missing any of the 60 settlement prints, 176 for a missing
  previous settle; 608 tape lines unparseable.
- tau in {45, 30, 20, 15, 10, 5}. At tau the stub holds every print up to
  and including second close-tau (the live convention: remaining = tau-1).
  **Verified against the live bot's own logged `fair` on our fills: 747 of 874
  reproduce within 0.00005 (median |diff| 0.000003); 850 of 908 under one of
  the two arrival conventions.** The rest are fills whose decision second had
  a print arrival the tape does not show identically.
- strike(N) = round(settle(N-1), digits) with digits from the live signals
  (BTC/ETH/BNB 2, SOL/XRP/HYPE/NEAR/ZEC 4, DOGE 7). YES iff round(settle, d)
  >= strike. **Checked against Kalshi's recorded result for every market in
  fulltape/markets.json (through 09-18): 12,607 of 12,607 agree.** Strikes
  agree exactly on 11,742 of 12,607; DOGE on 610 of 1,401 (Kalshi's strike
  carried 6 decimals where we carry 7 -- a 1e-7 difference; the outcome still
  agreed on all 1,401).
- P = favoured side's probability from `pinrun.fair` (live ruler 300 s, no
  --honest, no widen, SIGMA_STRESS 1.0 -- the running flags). "lost" = that
  side lost.
- n: every table gives cells AND distinct closes; CIs resample closes.
  "smallest x detectable" = realised/implied ratio a one-sided 5% test finds
  with 80% power (Poisson; floor of 3 losses where <1 expected). It ignores
  cross-coin correlation, so it is optimistic.

ROWS 141240 (live coins 115560), closes 2140, first 2026-09-01 00:30Z last 2026-09-25 07:00Z
closes per index: ADA 2140, BCH 2140, BNB 2140, BTC 2140, DOGE 2140, ETH 2140, HYPE 2140, NEAR 2140, SOL 2140, XRP 2140, ZEC 2140

## 2. Pooled 9 live coins -- model's claimed losses vs what the index did, per tau x P bucket
| tau | P bucket | cells | closes | model says loses | actually lost | realised rate (95% CI, by close) | x model | closes with a loss | smallest x detectable |
|---|---|---|---|---|---|---|---|---|---|
| 45 | 0.950-0.980 | 524 | 445 | 17.33 (3.308%) | 23 | 4.389% [2.677%, 6.090%] | 1.3x | 23 | 1.7x |
| 45 | 0.980-0.990 | 348 | 313 | 5.04 (1.448%) | 11 | 3.161% [1.393%, 5.187%] | 2.2x | 10 | 2.3x |
| 45 | 0.990-0.995 | 306 | 285 | 2.22 (0.725%) | 5 | 1.634% [0.326%, 3.205%] | 2.3x | 5 | 3.1x |
| 45 | 0.995-0.999 | 652 | 546 | 1.68 (0.258%) | 4 | 0.613% [0.154%, 1.264%] | 2.4x | 4 | 3.5x |
| 45 | >0.999 | 15363 | 2140 | 0.34 (0.002%) | 24 | 0.156% [0.065%, 0.288%] | 70.4x | 14 | 8.8x |
| 30 | 0.950-0.980 | 283 | 257 | 9.36 (3.306%) | 8 | 2.827% [1.091%, 4.895%] | 0.9x | 8 | 1.9x |
| 30 | 0.980-0.990 | 182 | 169 | 2.59 (1.420%) | 4 | 2.198% [0.529%, 4.469%] | 1.5x | 4 | 2.9x |
| 30 | 0.990-0.995 | 163 | 156 | 1.16 (0.713%) | 2 | 1.227% [0.000%, 3.125%] | 1.7x | 2 | 4.1x |
| 30 | 0.995-0.999 | 356 | 327 | 0.88 (0.248%) | 6 | 1.685% [0.282%, 3.361%] | 6.8x | 5 | 4.7x |
| 30 | >0.999 | 17174 | 2140 | 0.19 (0.001%) | 9 | 0.052% [0.006%, 0.116%] | 47.4x | 5 | 15.8x |
| 20 | 0.950-0.980 | 143 | 134 | 4.72 (3.298%) | 4 | 2.797% [0.685%, 5.755%] | 0.8x | 4 | 2.4x |
| 20 | 0.980-0.990 | 94 | 92 | 1.33 (1.411%) | 5 | 5.319% [1.075%, 9.783%] | 3.8x | 5 | 3.9x |
| 20 | 0.990-0.995 | 93 | 89 | 0.68 (0.735%) | 2 | 2.151% [0.000%, 5.319%] | 2.9x | 2 | 5.3x |
| 20 | 0.995-0.999 | 169 | 159 | 0.44 (0.263%) | 2 | 1.183% [0.000%, 2.994%] | 4.5x | 2 | 6.8x |
| 20 | >0.999 | 18157 | 2140 | 0.10 (0.001%) | 7 | 0.039% [0.011%, 0.072%] | 69.1x | 6 | 29.6x |
| 15 | 0.950-0.980 | 99 | 97 | 3.35 (3.389%) | 6 | 6.061% [2.020%, 11.000%] | 1.8x | 6 | 2.6x |
| 15 | 0.980-0.990 | 70 | 70 | 1.04 (1.482%) | 2 | 2.857% [0.000%, 7.143%] | 1.9x | 2 | 4.3x |
| 15 | 0.990-0.995 | 55 | 55 | 0.39 (0.715%) | 3 | 5.455% [0.000%, 12.727%] | 7.6x | 3 | 7.6x |
| 15 | 0.995-0.999 | 110 | 103 | 0.26 (0.239%) | 2 | 1.818% [0.000%, 4.545%] | 7.6x | 2 | 11.4x |
| 15 | >0.999 | 18551 | 2140 | 0.06 (0.000%) | 5 | 0.027% [0.005%, 0.059%] | 82.4x | 4 | 49.4x |
| 10 | 0.950-0.980 | 58 | 58 | 1.94 (3.345%) | 0 | 0.000% [0.000%, 0.000%] | 0.0x | 0 | 3.3x |
| 10 | 0.980-0.990 | 47 | 47 | 0.67 (1.422%) | 1 | 2.128% [0.000%, 6.383%] | 1.5x | 1 | 5.4x |
| 10 | 0.990-0.995 | 27 | 27 | 0.19 (0.716%) | 0 | 0.000% [0.000%, 0.000%] | 0.0x | 0 | 15.5x |
| 10 | 0.995-0.999 | 66 | 64 | 0.17 (0.252%) | 0 | 0.000% [0.000%, 0.000%] | 0.0x | 0 | 18.0x |
| 10 | >0.999 | 18881 | 2140 | 0.04 (0.000%) | 0 | 0.000% [0.000%, 0.000%] | 0.0x | 0 | 80.0x |
| 5 | 0.950-0.980 | 18 | 18 | 0.67 (3.735%) | 2 | 11.111% [0.000%, 27.778%] | 3.0x | 2 | 5.4x |
| 5 | 0.980-0.990 | 9 | 9 | 0.13 (1.424%) | 0 | 0.000% [0.000%, 0.000%] | 0.0x | 0 | 23.4x |
| 5 | 0.990-0.995 | 6 | 6 | 0.05 (0.769%) | 1 | 16.667% [0.000%, 50.000%] | 21.7x | 1 | 65.0x |
| 5 | 0.995-0.999 | 19 | 19 | 0.05 (0.263%) | 0 | 0.000% [0.000%, 0.000%] | 0.0x | 0 | 60.1x |
| 5 | >0.999 | 19160 | 2140 | 0.01 (0.000%) | 0 | 0.000% [0.000%, 0.000%] | 0.0x | 0 | 385.1x |

## 3. The live gate (P >= 0.995) per coin x tau: favoured side lost / cells (x model)
| coin | tau 45 | tau 30 | tau 20 | tau 15 | tau 10 | tau 5 | all taus: lost/cells, x model |
|---|---|---|---|---|---|---|---|
| ADA (no market) | 3/1769 (14.9x) | 1/1961 (8.8x) | 2/2033 (52.0x) | 1/2072 (22.4x) | 1/2101 (30.6x) | 0/2122 (0.0x) | 8/12058, 18.3x (model 0.44) |
| BCH (no market) | 4/1884 (21.9x) | 2/1993 (27.1x) | 1/2047 (21.4x) | 0/2076 (0.0x) | 0/2104 (0.0x) | 0/2131 (0.0x) | 7/12235, 19.4x (model 0.36) |
| BNB | 3/1746 (12.4x) | 3/1929 (27.4x) | 0/2032 (0.0x) | 0/2070 (0.0x) | 0/2094 (0.0x) | 0/2130 (0.0x) | 6/12001, 12.0x (model 0.50) |
| BTC | 3/1677 (11.6x) | 1/1903 (5.9x) | 2/2011 (27.6x) | 2/2051 (65.9x) | 0/2103 (0.0x) | 0/2129 (0.0x) | 8/11874, 14.1x (model 0.57) |
| DOGE | 3/1738 (11.7x) | 1/1924 (6.8x) | 0/2021 (0.0x) | 1/2072 (29.6x) | 0/2099 (0.0x) | 0/2132 (0.0x) | 5/11986, 9.5x (model 0.53) |
| ETH | 3/1758 (13.1x) | 1/1926 (7.7x) | 1/2018 (15.2x) | 0/2063 (0.0x) | 0/2102 (0.0x) | 0/2132 (0.0x) | 5/11999, 9.7x (model 0.51) |
| HYPE | 4/1891 (21.6x) | 3/2006 (43.6x) | 2/2077 (46.0x) | 0/2101 (0.0x) | 0/2122 (0.0x) | 0/2138 (0.0x) | 9/12335, 26.0x (model 0.35) |
| NEAR | 1/1818 (5.6x) | 1/1972 (10.4x) | 0/2057 (0.0x) | 1/2090 (28.1x) | 0/2111 (0.0x) | 0/2131 (0.0x) | 3/12179, 8.0x (model 0.38) |
| SOL | 4/1734 (15.3x) | 2/1920 (12.1x) | 1/2015 (14.5x) | 2/2054 (61.5x) | 0/2099 (0.0x) | 0/2129 (0.0x) | 9/11951, 16.0x (model 0.56) |
| XRP | 4/1817 (25.6x) | 3/1975 (31.1x) | 1/2058 (15.4x) | 0/2093 (0.0x) | 0/2120 (0.0x) | 0/2132 (0.0x) | 8/12195, 21.4x (model 0.37) |
| ZEC | 3/1836 (11.7x) | 0/1975 (0.0x) | 2/2037 (57.8x) | 1/2067 (26.2x) | 0/2097 (0.0x) | 0/2126 (0.0x) | 6/12138, 13.1x (model 0.46) |

## 3b. Per coin x bucket, tau 45 + 30 (the early leg)
| coin | 0.950-0.980 | 0.980-0.990 | 0.990-0.995 | 0.995-0.999 | >0.999 |
|---|---|---|---|---|---|
| BNB | 4/118 (model 3.88) | 3/67 (model 0.96) | 2/66 (model 0.47) | 2/109 (model 0.29) | 4/3566 (model 0.06) |
| BTC | 6/129 (model 4.26) | 2/61 (model 0.84) | 0/65 (model 0.47) | 1/142 (model 0.37) | 3/3438 (model 0.06) |
| DOGE | 5/96 (model 3.26) | 2/72 (model 1.06) | 2/51 (model 0.35) | 0/137 (model 0.34) | 4/3525 (model 0.06) |
| ETH | 4/88 (model 2.80) | 2/67 (model 0.95) | 1/47 (model 0.35) | 1/119 (model 0.30) | 3/3565 (model 0.06) |
| HYPE | 2/70 (model 2.28) | 1/41 (model 0.59) | 1/40 (model 0.30) | 1/82 (model 0.20) | 6/3815 (model 0.05) |
| NEAR | 2/85 (model 2.76) | 2/60 (model 0.85) | 1/52 (model 0.37) | 0/85 (model 0.23) | 2/3705 (model 0.05) |
| SOL | 2/78 (model 2.70) | 0/62 (model 0.90) | 0/55 (model 0.39) | 2/142 (model 0.36) | 4/3512 (model 0.06) |
| XRP | 2/65 (model 2.10) | 2/52 (model 0.76) | 0/58 (model 0.42) | 1/81 (model 0.20) | 6/3711 (model 0.06) |
| ZEC | 4/78 (model 2.64) | 1/48 (model 0.71) | 0/35 (model 0.25) | 2/111 (model 0.28) | 1/3700 (model 0.06) |

## 4. Over time (P >= 0.995 cells)
first 70%: 53 lost / 75881 cells; model expected 3.05; 17.4x
last 30%: 6 lost / 32777 cells; model expected 1.17; 5.1x
week from 09-01: 15 lost / 30824 cells, model 1.22, 12.3x
week from 09-08: 32 lost / 31832 cells, model 1.36, 23.6x
week from 09-15: 12 lost / 33759 cells, model 1.21, 9.9x
week from 09-22: 0 lost / 12243 cells, model 0.44, 0.0x

## 5. Does the 300 s sigma under-react after a jump? (tau 45 and 30)
| s60/s300 | cells | sd of realised miss (model says 1.00) | misses beyond 3 sd (normal 0.13% one side) | fwd 1-s sd / s300 (median) | fwd / max(s300,s60) (median) | P>=.995 lost/cells (model) |
|---|---|---|---|---|---|---|
| 0.00-0.50 | 3052 | 0.91 | 0.92% | 0.53 | 0.53 | 0/2676 (0.24) |
| 0.50-0.80 | 12620 | 1.00 | 0.86% | 0.69 | 0.69 | 11/11220 (0.95) |
| 0.80-1.25 | 17012 | 1.17 | 1.27% | 0.80 | 0.77 | 22/14861 (1.31) |
| 1.25-1.75 | 4894 | 1.40 | 1.21% | 0.81 | 0.57 | 10/4043 (0.46) |
| 1.75-2.50 | 926 | 1.07 | 0.65% | 0.69 | 0.36 | 0/730 (0.13) |

## 5b. Proposals on the index tape (P >= 0.995 gate). Tape = index population, NOT our losses
tail multiplier M(tau) fitted on the first 70% (cells P>=0.99): tau 45: 9.3x, tau 30: 9.0x, tau 20: 9.9x, tau 15: 18.4x, tau 10: 1.0x, tau 5: 10.9x

HOLDOUT last 30%:
| rule | cells kept (of the live gate's) | favoured side lost | rate | live gate lost | live gate rate |
|---|---|---|---|---|---|
| live model (P>=0.995) | 32777 of 32777 (100%) | 6 | 0.018% | 6 | 0.018% |
| tail multiplier: 1-M(tau)(1-P) >= 0.995 | 32281 of 32777 (98%) | 3 | 0.009% | 6 | 0.018% |
| sigma = max(s300, s60) | 32559 of 32777 (99%) | 6 | 0.018% | 6 | 0.018% |
| sigma = max(s300, s3600) | 32367 of 32777 (99%) | 4 | 0.012% | 6 | 0.018% |
| P floor 0.999 | 32404 of 32777 (99%) | 5 | 0.015% | 6 | 0.018% |
| P floor 0.999 at tau>=30, 0.995 below | 32490 of 32777 (99%) | 5 | 0.015% | 6 | 0.018% |
| max(s300,s60) AND tail mult | 32018 of 32777 (98%) | 3 | 0.009% | 6 | 0.018% |

ALL closes:
| rule | cells kept (of the live gate's) | favoured side lost | rate | live gate lost | live gate rate |
|---|---|---|---|---|---|
| live model (P>=0.995) | 108658 of 108658 (100%) | 59 | 0.054% | 59 | 0.054% |
| tail multiplier: 1-M(tau)(1-P) >= 0.995 | 106855 of 108658 (98%) | 37 | 0.035% | 59 | 0.054% |
| sigma = max(s300, s60) | 107835 of 108658 (99%) | 54 | 0.050% | 59 | 0.054% |
| sigma = max(s300, s3600) | 107246 of 108658 (99%) | 38 | 0.035% | 59 | 0.054% |
| P floor 0.999 | 107286 of 108658 (99%) | 45 | 0.042% | 59 | 0.054% |
| P floor 0.999 at tau>=30, 0.995 below | 107650 of 108658 (99%) | 49 | 0.046% | 59 | 0.054% |
| max(s300,s60) AND tail mult | 105863 of 108658 (97%) | 29 | 0.027% | 59 | 0.054% |

## 6. Our own fills re-priced from the tape (live fills + Kalshi ledger outcome)
reproduction of the logged fair: print-for-now held: 747/874 within 0.00005 (median |diff| 0.000003); not held: 186/874 (median 0.002563)
either convention within 0.00005: 850/908
fills with a ledger result: 908 (862 markets); want-side LOST: 23 fills on 19 markets

| rule | losing markets it would have refused (fills) | winning fills it would have refused | contracts refused on winners |
|---|---|---|---|
| live | 2 of 19 markets (3 of 23 fills) | 39 of 885 | 595 of 41055 |
| tailmult | 15 of 19 markets (18 of 23 fills) | 664 of 885 | 30449 of 41055 |
| s60 | 4 of 19 markets (6 of 23 fills) | 283 of 885 | 11869 of 41055 |
| s3600 | 12 of 19 markets (15 of 23 fills) | 504 of 885 | 23559 of 41055 |
| floor999 | 14 of 19 markets (18 of 23 fills) | 636 of 885 | 29462 of 41055 |
| floor999_early | 9 of 19 markets (10 of 23 fills) | 307 of 885 | 12917 of 41055 |

losing fills:
| ticker | t (UTC) | tau | want | price | logged fair | tape fair | s60/s300 | s3600/s300 | cushion z | realised z | p60 | p3600 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KXNEAR15M-26SEP082045-45 | 2026-09-09T00:44:38Z | 22 | no | 0.962 | 0.98174 | 0.98174 | 1.21 | 1.29 | 2.09 | -2.90 | 0.95775 | 0.94692 |
| KXNEAR15M-26SEP082045-45 | 2026-09-09T00:44:39Z | 21 | no | 0.956 | 0.98765 | 0.98765 | 1.14 | 1.29 | 2.25 | -3.12 | 0.97543 | 0.95866 |
| KXNEAR15M-26SEP082045-45 | 2026-09-09T00:44:43Z | 17 | no | 0.730 | 0.99827 | 0.99827 | 1.15 | 1.31 | 2.92 | -4.14 | 0.99446 | 0.98739 |
| KXXRP15M-26SEP100100-00 | 2026-09-10T04:59:39Z | 21 | yes | 0.957 | 1.00000 | 1.00000 | 0.73 | 0.90 | 9.15 | -11.34 | 1.00000 | 1.00000 |
| KXBNB15M-26SEP100130-30 | 2026-09-10T05:29:34Z | 26 | yes | 0.940 | 0.98507 | 0.98507 | 1.12 | 0.90 | 2.17 | -2.52 | 0.97361 | 0.98507 |
| KXDOGE15M-26SEP101815-15 | 2026-09-10T22:14:49Z | 11 | no | 0.530 | 1.00000 | 1.00000 | 0.81 | 1.02 | 5.02 | -13.74 | 1.00000 | 1.00000 |
| KXSOL15M-26SEP110830-30 | 2026-09-11T12:29:30Z | 30 | no | 0.700 | 0.99508 | - | - | - | - | - | - | - |
| KXSOL15M-26SEP112300-00 | 2026-09-12T02:59:31Z | 29 | no | 0.979 | 0.99968 | 0.99968 | 0.81 | 1.54 | 3.42 | -6.48 | 0.99968 | 0.98693 |
| KXSOL15M-26SEP120400-00 | 2026-09-12T07:59:41Z | 19 | yes | 0.940 | 0.99764 | 0.99764 | 1.57 | 1.14 | 2.83 | -5.19 | 0.96417 | 0.99341 |
| KXZEC15M-26SEP122000-00 | 2026-09-12T23:59:35Z | 25 | yes | 0.963 | 0.99732 | 0.99732 | 0.90 | 1.70 | 2.78 | -8.02 | 0.99732 | 0.94956 |
| KXHYPE15M-26SEP141600-00 | 2026-09-14T19:59:30Z | 30 | no | 0.950 | 0.99617 | 0.99765 | 1.04 | 1.60 | 2.83 | -3.53 | 0.99681 | 0.96095 |
| KXBNB15M-26SEP161230-30 | 2026-09-16T16:29:30Z | 30 | no | 0.977 | 0.99521 | 0.99521 | 0.73 | 1.67 | 2.59 | -2.91 | 0.99521 | 0.93967 |
| KXBTC15M-26SEP172115-15 | 2026-09-18T01:14:22Z | 38 | yes | 0.978 | 0.99561 | 0.99561 | 0.86 | 0.81 | 2.62 | -3.87 | 0.99561 | 0.99561 |
| KXDOGE15M-26SEP180015-15 | 2026-09-18T04:14:28Z | 32 | yes | 0.976 | 0.99707 | 0.99707 | 0.88 | 1.44 | 2.76 | -4.54 | 0.99707 | 0.97186 |
| KXBNB15M-26SEP190145-45 | 2026-09-19T05:44:36Z | 24 | yes | 0.850 | 0.99926 | 0.99926 | 0.57 | 1.70 | 3.18 | -3.75 | 0.99926 | 0.96951 |
| KXBTC15M-26SEP190200-00 | 2026-09-19T05:59:25Z | 35 | no | 0.943 | 0.99687 | 0.99687 | 0.73 | 0.99 | 2.73 | -3.21 | 0.99687 | 0.99687 |
| KXBNB15M-26SEP191230-30 | 2026-09-19T16:29:37Z | 23 | yes | 0.915 | 0.99863 | 0.99863 | 0.81 | 1.36 | 3.00 | -3.51 | 0.99863 | 0.98619 |
| KXBTC15M-26SEP191600-00 | 2026-09-19T19:59:15Z | 45 | no | 0.980 | 0.99944 | 0.99944 | 0.54 | 1.25 | 3.26 | -5.76 | 0.99944 | 0.99534 |
| KXNEAR15M-26SEP211245-45 | 2026-09-21T16:44:16Z | 44 | yes | 0.955 | 0.99557 | 0.99557 | 1.03 | 1.15 | 2.62 | -3.51 | 0.99456 | 0.98835 |
| KXDOGE15M-26SEP222245-45 | 2026-09-23T02:44:48Z | 12 | no | 0.980 | 0.99559 | 0.99559 | 0.99 | 1.43 | 2.62 | -5.02 | 0.99559 | 0.96671 |
| KXDOGE15M-26SEP222245-45 | 2026-09-23T02:44:49Z | 11 | no | 0.980 | 0.99559 | 0.99867 | 0.99 | 1.43 | 3.00 | -5.76 | 0.99867 | 0.98227 |
| KXBTC15M-26SEP232030-30 | 2026-09-24T00:29:34Z | 26 | yes | 0.860 | 0.99896 | - | - | - | - | - | - | - |
| KXBTC15M-26SEP232030-30 | 2026-09-24T00:29:34Z | 26 | yes | 0.860 | 0.99896 | - | - | - | - | - | - | - |


## 6b. Dollar side of each proposal on OUR fills (money.py)

Only what a rule refuses beyond the live gate's own refusals (my re-creation
of the gate -- P >= 0.995 and P - price - fee >= 0.003 -- refuses 3 of our
losing fills and 39 winning ones it actually took, so "live" is used as the
baseline and subtracted). Loser $ avoided = contracts x price + fee; winner $
forgone = contracts x (1 - price) - fee. Hedges are ignored, so real losses
were smaller than "loser $" and this favours the proposals.

| rule | loser $ avoided | winner $ forgone | net $ | losing markets refused (of 19) | winning fills refused (of 885) |
|---|---|---|---|---|---|
| tail multiplier 1-M(tau)(1-P) >= 0.995, M fitted on first 70% of closes (9-18x) | 794.02 | 1023.49 | -229.47 | 14 | 625 |
| sigma = max(s300, s60) | 110.61 | 469.57 | -358.96 | 3 | 244 |
| sigma = max(s300, s3600) | 388.05 | 812.36 | -424.31 | 11 | 465 |
| P floor 0.999 | 633.55 | 1022.96 | -389.41 | 13 | 597 |
| P floor 0.999 at tau >= 30 only | 348.10 | 360.89 | -12.79 | 7 | 268 |

## 7. What was NOT measured, and gaps

- The fill join is signal-to-order on (ticker, same second). Losing markets
  that appear in `settled` records with pnl_c < 0 but not in the table above
  (KXXRP15M/KXHYPE15M 26SEP192345, KXHYPE15M 26SEP211815) did not join --
  either a hedge-side loss or an order whose record second differs from its
  signal. They are not in the "caught" counts.
- Three losing fills have no tape price (KXSOL15M-26SEP110830-30,
  KXBTC15M-26SEP232030-30 x2): the tape lacks a settlement print for them.
- The dollar table uses the signal's ask as the price; a few loser rows show
  signal prices of 0.07-0.59 (hedge-era or partial records). Those rows move
  "loser $" down, not up.
- The per-coin differences (3-9 losses per coin) are not distinguishable from
  each other at this n; do not build per-coin floors on them.

## 8. Testable next steps (none is a live change)

1. **A paper arm is not justified for any rule here** -- all five are negative
   on our own fills. The nearest to neutral, "P floor 0.999 at tau >= 30"
   (-$13 over 17 days), would need a pre-registered bar before anyone runs it.
2. **Where to look instead (identify better):** the tape says the model's
   stated P is not what separates our losers from our winners -- 16 of the 19
   losing markets had a fill at logged P 0.995-0.9999 (2 at P = 1.00000:
   XRP and DOGE on 09-10; 1 at 0.985: BNB 09-10), the same band as the
   winners. The
   discriminator has to come from the market side (who sold, how fast, how
   much size) -- live-fill data, not the index.
3. **Late seconds are the safe ones on the index:** 0 losses in ~40,000 gated
   cells at tau 10 and 5 (smallest detectable ~80x and ~385x -- weak, but no
   loss at all). Consistent with shifting size toward tau <= 15; that is a
   supply question, not a model one.
