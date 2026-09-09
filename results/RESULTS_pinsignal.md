# pinsignal -- what, at ENTRY, separates the losers?

Generated 2026-09-09T01:19:23Z from `C:\kals-repo\results\pindata\rows.jsonl`.

Index tape: 69 hourly files, 1 ended early (truncated gzip tolerated).


**CORRECTION TO THE BRIEF, measured not assumed:** the wide window is tau 3-**60**, not 3-200. `pindata.partial()` needs at least one still-unpublished print inside the 60-second settlement window, so no row can exist above tau 60. The largest tau in rows.jsonl is 60.


**P1 -- WIDE, every available second, tau 3-60**: rows 28,446, markets 1,014, **closes 132**, losing rows 1,506, losing markets 101, **loss-carrying closes 67**, row loss rate 5.29%

POPULATION CALIBRATION: the model predicted 3.708% and reality delivered 5.294% -- **1.4x** more losses than the gaussian says.


**P1_tau45+ -- WIDE, tau 45-60 only -- tau held nearly fixed**: rows 13,765, markets 1,003, **closes 132**, losing rows 901, losing markets 92, **loss-carrying closes 61**, row loss rate 6.55%

POPULATION CALIBRATION: the model predicted 4.177% and reality delivered 6.546% -- **1.6x** more losses than the gaussian says.


**P1_tau30-44 -- WIDE, tau 30-44 only -- tau held nearly fixed**: rows 8,927, markets 788, **closes 129**, losing rows 408, losing markets 54, **loss-carrying closes 41**, row loss rate 4.57%

POPULATION CALIBRATION: the model predicted 3.645% and reality delivered 4.570% -- **1.3x** more losses than the gaussian says.


**P2 -- WIDE and the LIVE RULE's gates (price<=98.8c, model p<=2%, EV>=0.3c)**: rows 4,696, markets 438, **closes 118**, losing rows 55, losing markets 12, **loss-carrying closes 10**, row loss rate 1.17%

POPULATION CALIBRATION: the model predicted 0.393% and reality delivered 1.171% -- **3.0x** more losses than the gaussian says.


**P1M -- one TRADE per market (earliest qualifying second), WIDE**: rows 1,014, markets 1,014, **closes 132**, losing rows 73, losing markets 73, **loss-carrying closes 53**, row loss rate 7.20%

POPULATION CALIBRATION: the model predicted 4.560% and reality delivered 7.199% -- **1.6x** more losses than the gaussian says.


**P2M -- one TRADE per market, LIVE RULE's gates**: rows 438, markets 438, **closes 118**, losing rows 12, losing markets 12, **loss-carrying closes 10**, row loss rate 2.74%

POPULATION CALIBRATION: the model predicted 0.930% and reality delivered 2.740% -- **2.9x** more losses than the gaussian says.


MULTIPLE LOOKS: 23 features are tested in each population, so the 5% threshold after Bonferroni is p = 0.0022. A permutation p above that is not a finding.


---

## Population P1 -- WIDE, every available second, tau 3-60


### `flat10` -- frac of last 10s prints exactly equal to the previous

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.422 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.1 | 16,674 | 804 | 132 | 922 | **5.53%** | 3.95% | 1.4x |
| 2 | 0.2 .. 0.3 | 5,533 | 491 | 129 | 229 | **4.14%** | 2.81% | 1.5x |
| 3 | 0.4 .. 1 | 6,239 | 380 | 130 | 355 | **5.69%** | 3.86% | 1.5x |

RAW  top - bottom = **+0.16 pp**   95% CI (close-cluster bootstrap) [-2.80, +3.32] pp   SE 1.579 pp

EXCESS OVER MODEL, top - bottom = **+0.25 pp**   95% CI [-2.04, +2.76] pp   MDE 3.451 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.15, +6.23] pp, null SE 3.353 pp, permutation p = **0.9082**

### `flat30` -- frac of last 30s prints exactly equal

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.250 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.03333 | 10,318 | 479 | 131 | 683 | **6.62%** | 4.43% | 1.5x |
| 2 | 0.06667 .. 0.1333 | 5,925 | 409 | 129 | 200 | **3.38%** | 2.83% | 1.2x |
| 3 | 0.1667 .. 0.3333 | 6,368 | 367 | 126 | 247 | **3.88%** | 2.92% | 1.3x |
| 4 | 0.3667 .. 1 | 5,835 | 263 | 129 | 376 | **6.44%** | 4.18% | 1.5x |

RAW  top - bottom = **-0.18 pp**   95% CI (close-cluster bootstrap) [-3.82, +3.54] pp   SE 1.875 pp

EXCESS OVER MODEL, top - bottom = **+0.07 pp**   95% CI [-2.78, +3.14] pp   MDE 4.208 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.39, +7.20] pp, null SE 4.064 pp, permutation p = **0.9760**

### `flat60` -- frac of last 60s prints exactly equal

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.247 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0 | 5,471 | 245 | 124 | 425 | **7.77%** | 5.10% | 1.5x |
| 2 | 0.01667 .. 0.05 | 4,750 | 258 | 117 | 248 | **5.22%** | 3.46% | 1.5x |
| 3 | 0.06667 .. 0.15 | 6,255 | 323 | 124 | 217 | **3.47%** | 2.99% | 1.2x |
| 4 | 0.1667 .. 0.3333 | 6,123 | 295 | 119 | 238 | **3.89%** | 2.95% | 1.3x |
| 5 | 0.35 .. 0.9833 | 5,847 | 240 | 128 | 378 | **6.46%** | 4.17% | 1.6x |

RAW  top - bottom = **-1.30 pp**   95% CI (close-cluster bootstrap) [-5.81, +3.07] pp   SE 2.231 pp

EXCESS OVER MODEL, top - bottom = **-0.37 pp**   95% CI [-3.78, +3.03] pp   MDE 4.900 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.38, +9.13] pp, null SE 4.734 pp, permutation p = **0.8523**

### `flat300` -- frac of last 300s prints exactly equal

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.726 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.006667 | 5,262 | 199 | 122 | 357 | **6.78%** | 5.04% | 1.3x |
| 2 | 0.01 .. 0.08 | 6,028 | 244 | 121 | 345 | **5.72%** | 3.45% | 1.7x |
| 3 | 0.08333 .. 0.17 | 5,641 | 232 | 115 | 182 | **3.23%** | 2.80% | 1.2x |
| 4 | 0.1733 .. 0.3433 | 5,800 | 199 | 104 | 261 | **4.50%** | 2.83% | 1.6x |
| 5 | 0.3467 .. 0.9467 | 5,715 | 208 | 126 | 361 | **6.32%** | 4.54% | 1.4x |

RAW  top - bottom = **-0.47 pp**   95% CI (close-cluster bootstrap) [-4.52, +3.49] pp   SE 2.045 pp

EXCESS OVER MODEL, top - bottom = **+0.03 pp**   95% CI [-3.20, +3.21] pp   MDE 4.528 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.03, +9.05] pp, null SE 4.949 pp, permutation p = **0.9741**

### `s30_s300` -- sigma_30 / sigma_300  (low = unusually quiet right now)

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.438 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.5411 | 5,689 | 451 | 116 | 214 | **3.76%** | 2.07% | 1.8x |
| 2 | 0.5411 .. 0.741 | 5,689 | 567 | 128 | 185 | **3.25%** | 2.99% | 1.1x |
| 3 | 0.741 .. 0.9401 | 5,690 | 567 | 128 | 260 | **4.57%** | 3.09% | 1.5x |
| 4 | 0.9403 .. 1.254 | 5,689 | 480 | 123 | 412 | **7.24%** | 4.32% | 1.7x |
| 5 | 1.254 .. 3.025 | 5,689 | 341 | 108 | 435 | **7.65%** | 6.08% | 1.3x |

RAW  top - bottom = **+3.88 pp**   95% CI (close-cluster bootstrap) [+0.86, +7.15] pp   SE 1.585 pp

EXCESS OVER MODEL, top - bottom = **-0.13 pp**   95% CI [-2.48, +2.19] pp   MDE 3.383 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.58, +7.29] pp, null SE 4.070 pp, permutation p = **0.3114**

### `s300_s900` -- sigma_300 / sigma_900 (low = quiet vs the last 15 min)

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.453 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2971 .. 0.7966 | 5,689 | 257 | 96 | 239 | **4.20%** | 2.30% | 1.8x |
| 2 | 0.7967 .. 0.9229 | 5,688 | 284 | 109 | 277 | **4.87%** | 3.01% | 1.6x |
| 3 | 0.9229 .. 1.039 | 5,691 | 303 | 113 | 297 | **5.22%** | 3.55% | 1.5x |
| 4 | 1.039 .. 1.165 | 5,689 | 259 | 110 | 376 | **6.61%** | 4.19% | 1.6x |
| 5 | 1.165 .. 1.693 | 5,689 | 236 | 91 | 317 | **5.57%** | 5.49% | 1.0x |

RAW  top - bottom = **+1.37 pp**   95% CI (close-cluster bootstrap) [-2.64, +5.04] pp   SE 1.948 pp

EXCESS OVER MODEL, top - bottom = **-1.82 pp**   95% CI [-5.55, +0.84] pp   MDE 4.470 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.39, +10.18] pp, null SE 5.139 pp, permutation p = **0.7565**

### `s300_s3600` -- sigma_300 / sigma_3600 (low = quiet vs the hour)

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.871 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2054 .. 0.6613 | 5,689 | 232 | 82 | 270 | **4.75%** | 2.52% | 1.9x |
| 2 | 0.6613 .. 0.8126 | 5,689 | 272 | 104 | 358 | **6.29%** | 3.20% | 2.0x |
| 3 | 0.8126 .. 0.9767 | 5,690 | 277 | 113 | 312 | **5.48%** | 3.99% | 1.4x |
| 4 | 0.9767 .. 1.184 | 5,689 | 252 | 102 | 259 | **4.55%** | 3.95% | 1.2x |
| 5 | 1.184 .. 2.922 | 5,689 | 232 | 82 | 307 | **5.40%** | 4.88% | 1.1x |

RAW  top - bottom = **+0.65 pp**   95% CI (close-cluster bootstrap) [-2.76, +4.20] pp   SE 1.740 pp

EXCESS OVER MODEL, top - bottom = **-1.71 pp**   95% CI [-4.45, +0.88] pp   MDE 3.838 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.99, +10.25] pp, null SE 5.198 pp, permutation p = **0.8882**

### `s300_sday` -- sigma_300 / sigma_86400 (low = quiet vs the day)

rows 27,891   closes 129   **loss-carrying closes 65**   losing markets 97   dropped (feature unavailable) 555

**MDE (stated before the estimate): 6.051 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.09508 .. 0.3895 | 5,576 | 190 | 62 | 373 | **6.69%** | 2.87% | 2.3x |
| 2 | 0.3895 .. 0.5337 | 5,580 | 215 | 93 | 319 | **5.72%** | 3.99% | 1.4x |
| 3 | 0.5337 .. 0.725 | 5,579 | 239 | 104 | 327 | **5.86%** | 4.04% | 1.5x |
| 4 | 0.725 .. 1.034 | 5,577 | 237 | 94 | 189 | **3.39%** | 3.04% | 1.1x |
| 5 | 1.034 .. 4.41 | 5,579 | 242 | 84 | 239 | **4.28%** | 4.42% | 1.0x |

RAW  top - bottom = **-2.41 pp**   95% CI (close-cluster bootstrap) [-6.98, +1.53] pp   SE 2.161 pp

EXCESS OVER MODEL, top - bottom = **-3.95 pp**   95% CI [-8.16, -0.42] pp   MDE 5.657 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.95, +11.07] pp, null SE 5.641 pp, permutation p = **0.6168**

### `mx10_sig` -- largest 1s move in last 10s, in sigma_300

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 3.417 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.7151 | 5,689 | 660 | 129 | 252 | **4.43%** | 2.55% | 1.7x |
| 2 | 0.7151 .. 1.225 | 5,689 | 701 | 131 | 233 | **4.10%** | 2.70% | 1.5x |
| 3 | 1.225 .. 1.848 | 5,690 | 647 | 130 | 232 | **4.08%** | 3.27% | 1.2x |
| 4 | 1.848 .. 2.832 | 5,689 | 611 | 129 | 298 | **5.24%** | 4.19% | 1.2x |
| 5 | 2.833 .. 16.5 | 5,689 | 491 | 126 | 491 | **8.63%** | 5.83% | 1.5x |

RAW  top - bottom = **+4.20 pp**   95% CI (close-cluster bootstrap) [+1.83, +6.63] pp   SE 1.220 pp

EXCESS OVER MODEL, top - bottom = **+0.92 pp**   95% CI [-1.08, +2.89] pp   MDE 2.783 pp

SHUFFLED-LABEL CONTROL: null 95% range [-5.73, +6.05] pp, null SE 3.086 pp, permutation p = **0.1836**

### `mx30_sig` -- largest 1s move in last 30s, in sigma_300

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.369 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 1.649 | 5,689 | 463 | 121 | 222 | **3.90%** | 2.37% | 1.6x |
| 2 | 1.649 .. 2.352 | 5,689 | 482 | 128 | 105 | **1.85%** | 2.54% | 0.7x |
| 3 | 2.352 .. 3.188 | 5,690 | 433 | 128 | 288 | **5.06%** | 3.26% | 1.6x |
| 4 | 3.188 .. 4.661 | 5,689 | 389 | 123 | 459 | **8.07%** | 4.45% | 1.8x |
| 5 | 4.661 .. 16.54 | 5,689 | 325 | 111 | 432 | **7.59%** | 5.91% | 1.3x |

RAW  top - bottom = **+3.69 pp**   95% CI (close-cluster bootstrap) [+0.67, +6.72] pp   SE 1.560 pp

EXCESS OVER MODEL, top - bottom = **+0.15 pp**   95% CI [-2.28, +2.51] pp   MDE 3.469 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.40, +8.00] pp, null SE 4.122 pp, permutation p = **0.3413**

### `mx60_sig` -- largest 1s move in last 60s, in sigma_300

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.069 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.1934 .. 2.406 | 5,679 | 343 | 115 | 109 | **1.92%** | 2.29% | 0.8x |
| 2 | 2.406 .. 3.301 | 5,699 | 372 | 119 | 269 | **4.72%** | 3.20% | 1.5x |
| 3 | 3.302 .. 4.323 | 5,690 | 344 | 119 | 354 | **6.22%** | 3.31% | 1.9x |
| 4 | 4.323 .. 6.173 | 5,689 | 327 | 114 | 396 | **6.96%** | 4.48% | 1.6x |
| 5 | 6.176 .. 16.54 | 5,689 | 279 | 105 | 378 | **6.64%** | 5.26% | 1.3x |

RAW  top - bottom = **+4.73 pp**   95% CI (close-cluster bootstrap) [+2.13, +7.64] pp   SE 1.453 pp

EXCESS OVER MODEL, top - bottom = **+1.75 pp**   95% CI [-0.39, +4.17] pp   MDE 3.307 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.68, +8.03] pp, null SE 4.564 pp, permutation p = **0.2236**

### `req_rng30` -- |required move| / index range over last 30s

rows 28,369   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 77

**MDE (stated before the estimate): 5.561 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 8.037e-05 .. 1.031 | 5,674 | 240 | 98 | 1,168 | **20.59%** | 16.03% | 1.3x |
| 2 | 1.031 .. 2.512 | 5,674 | 474 | 120 | 173 | **3.05%** | 1.96% | 1.6x |
| 3 | 2.513 .. 4.39 | 5,673 | 599 | 125 | 92 | **1.62%** | 0.43% | 3.8x |
| 4 | 4.391 .. 7.911 | 5,674 | 670 | 132 | 26 | **0.46%** | 0.14% | 3.2x |
| 5 | 7.911 .. 871.8 | 5,674 | 582 | 128 | 38 | **0.67%** | 0.01% | 53.7x |

RAW  top - bottom = **-19.92 pp**   95% CI (close-cluster bootstrap) [-23.84, -16.09] pp   SE 1.986 pp

EXCESS OVER MODEL, top - bottom = **-3.89 pp**   95% CI [-7.32, -0.51] pp   MDE 4.820 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.19, +7.33] pp, null SE 3.653 pp, permutation p = **0.0020**

### `req_rng60` -- |required move| / index range over last 60s

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.160 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 7.398e-05 .. 0.6632 | 5,689 | 253 | 100 | 1,210 | **21.27%** | 16.34% | 1.3x |
| 2 | 0.6633 .. 1.518 | 5,689 | 426 | 118 | 132 | **2.32%** | 1.79% | 1.3x |
| 3 | 1.519 .. 2.635 | 5,690 | 600 | 124 | 53 | **0.93%** | 0.32% | 2.9x |
| 4 | 2.635 .. 4.664 | 5,689 | 624 | 130 | 104 | **1.83%** | 0.08% | 22.0x |
| 5 | 4.664 .. 114.1 | 5,689 | 552 | 127 | 7 | **0.12%** | 0.01% | 23.6x |

RAW  top - bottom = **-21.15 pp**   95% CI (close-cluster bootstrap) [-25.71, -17.16] pp   SE 2.200 pp

EXCESS OVER MODEL, top - bottom = **-4.81 pp**   95% CI [-8.55, -1.49] pp   MDE 5.009 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.16, +7.12] pp, null SE 3.749 pp, permutation p = **0.0020**

### `req_rng300` -- |required move| / index range over last 300s

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.904 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 2.446e-05 .. 0.3081 | 5,689 | 249 | 104 | 1,275 | **22.41%** | 17.32% | 1.3x |
| 2 | 0.3081 .. 0.5658 | 5,689 | 418 | 114 | 125 | **2.20%** | 1.16% | 1.9x |
| 3 | 0.5658 .. 0.8792 | 5,690 | 584 | 125 | 46 | **0.81%** | 0.06% | 12.6x |
| 4 | 0.8793 .. 1.376 | 5,689 | 649 | 129 | 54 | **0.95%** | 0.00% | 486.4x |
| 5 | 1.376 .. 28.25 | 5,689 | 593 | 127 | 6 | **0.11%** | 0.00% | 20071.8x |

RAW  top - bottom = **-22.31 pp**   95% CI (close-cluster bootstrap) [-26.68, -18.21] pp   SE 2.109 pp

EXCESS OVER MODEL, top - bottom = **-4.99 pp**   95% CI [-8.83, -1.39] pp   MDE 5.251 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.98, +7.01] pp, null SE 3.861 pp, permutation p = **0.0020**

### `gap` -- market implied p(lose) minus model p(lose)

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.065 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.4663 .. 0.001 | 5,686 | 638 | 129 | 674 | **11.85%** | 9.21% | 1.3x |
| 2 | 0.001 .. 0.002 | 5,692 | 863 | 132 | 27 | **0.47%** | 0.12% | 4.0x |
| 3 | 0.002 .. 0.005 | 5,690 | 753 | 131 | 47 | **0.83%** | 0.33% | 2.5x |
| 4 | 0.005 .. 0.018 | 5,689 | 577 | 125 | 123 | **2.16%** | 1.35% | 1.6x |
| 5 | 0.018 .. 0.4429 | 5,689 | 347 | 115 | 635 | **11.16%** | 7.53% | 1.5x |

RAW  top - bottom = **-0.69 pp**   95% CI (close-cluster bootstrap) [-4.20, +2.97] pp   SE 1.809 pp

EXCESS OVER MODEL, top - bottom = **+0.99 pp**   95% CI [-2.12, +4.06] pp   MDE 4.406 pp

SHUFFLED-LABEL CONTROL: null 95% range [-6.41, +7.22] pp, null SE 3.487 pp, permutation p = **0.8204**

### `lgap` -- log( market implied p(lose) / model p(lose) )

rows 19,465   closes 129   **loss-carrying closes 67**   losing markets 100   dropped (feature unavailable) 8,981

**MDE (stated before the estimate): 7.516 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -3.468 .. 0.2148 | 3,893 | 256 | 105 | 952 | **24.45%** | 20.05% | 1.2x |
| 2 | 0.2149 .. 1.816 | 3,893 | 370 | 115 | 406 | **10.43%** | 6.82% | 1.5x |
| 3 | 1.819 .. 5.372 | 3,893 | 510 | 122 | 59 | **1.52%** | 0.21% | 7.1x |
| 4 | 5.373 .. 11.21 | 3,893 | 631 | 123 | 31 | **0.80%** | 0.00% | 620.4x |
| 5 | 11.21 .. 24.48 | 3,893 | 717 | 129 | 31 | **0.80%** | 0.00% | 679637.5x |

RAW  top - bottom = **-23.66 pp**   95% CI (close-cluster bootstrap) [-28.87, -18.24] pp   SE 2.684 pp

EXCESS OVER MODEL, top - bottom = **-3.60 pp**   95% CI [-8.40, +1.20] pp   MDE 6.650 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.83, +6.24] pp, null SE 3.525 pp, permutation p = **0.0020**

### `z` -- |required move| in model sd (higher should be safer)

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.896 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.00026 .. 1.986 | 5,689 | 274 | 105 | 1,349 | **23.71%** | 18.08% | 1.3x |
| 2 | 1.986 .. 3.867 | 5,689 | 499 | 120 | 64 | **1.12%** | 0.46% | 2.4x |
| 3 | 3.867 .. 5.907 | 5,690 | 694 | 125 | 49 | **0.86%** | 0.00% | 1289.7x |
| 4 | 5.907 .. 9.181 | 5,689 | 793 | 130 | 37 | **0.65%** | 0.00% | 56618560.9x |
| 5 | 9.181 .. 794.1 | 5,689 | 713 | 131 | 7 | **0.12%** | 0.00% | 5794992309754221568.0x |

RAW  top - bottom = **-23.59 pp**   95% CI (close-cluster bootstrap) [-27.86, -19.37] pp   SE 2.106 pp

EXCESS OVER MODEL, top - bottom = **-5.51 pp**   95% CI [-9.48, -1.74] pp   MDE 5.459 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.24, +5.96] pp, null SE 3.360 pp, permutation p = **0.0020**

### `pmod` -- model p(lose) at entry

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.908 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 7.205e-26 | 5,689 | 715 | 132 | 10 | **0.18%** | 0.00% | 2914582029011744301514752.0x |
| 2 | 7.426e-26 .. 1.743e-09 | 5,689 | 790 | 130 | 34 | **0.60%** | 0.00% | 52027866.7x |
| 3 | 1.744e-09 .. 5.508e-05 | 5,690 | 694 | 125 | 49 | **0.86%** | 0.00% | 1289.7x |
| 4 | 5.512e-05 .. 0.02352 | 5,689 | 499 | 120 | 64 | **1.12%** | 0.46% | 2.4x |
| 5 | 0.02353 .. 0.4999 | 5,689 | 274 | 105 | 1,349 | **23.71%** | 18.08% | 1.3x |

RAW  top - bottom = **+23.54 pp**   95% CI (close-cluster bootstrap) [+19.28, +27.77] pp   SE 2.110 pp

EXCESS OVER MODEL, top - bottom = **+5.46 pp**   95% CI [+1.69, +9.43] pp   MDE 5.475 pp

SHUFFLED-LABEL CONTROL: null 95% range [-6.71, +6.40] pp, null SE 3.380 pp, permutation p = **0.0020**

### `tau` -- seconds to close at entry

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 3.179 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 3 .. 28 | 5,356 | 437 | 119 | 183 | **3.42%** | 2.62% | 1.3x |
| 2 | 29 .. 39 | 5,952 | 698 | 128 | 257 | **4.32%** | 3.47% | 1.2x |
| 3 | 40 .. 47 | 5,725 | 878 | 131 | 283 | **4.94%** | 3.86% | 1.3x |
| 4 | 48 .. 53 | 5,110 | 924 | 132 | 327 | **6.40%** | 3.95% | 1.6x |
| 5 | 54 .. 60 | 6,303 | 978 | 131 | 456 | **7.23%** | 4.52% | 1.6x |

RAW  top - bottom = **+3.82 pp**   95% CI (close-cluster bootstrap) [+1.66, +6.03] pp   SE 1.135 pp

EXCESS OVER MODEL, top - bottom = **+1.92 pp**   95% CI [-0.01, +3.85] pp   MDE 2.759 pp

SHUFFLED-LABEL CONTROL: null 95% range [-4.95, +4.75] pp, null SE 2.488 pp, permutation p = **0.1477**

### `price` -- price paid, dollars

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.550 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.51 .. 0.947 | 5,652 | 262 | 107 | 1,302 | **23.04%** | 17.31% | 1.3x |
| 2 | 0.948 .. 0.988 | 5,181 | 462 | 118 | 112 | **2.16%** | 1.36% | 1.6x |
| 3 | 0.989 .. 0.996 | 5,773 | 643 | 127 | 40 | **0.69%** | 0.10% | 6.9x |
| 4 | 0.997 .. 0.998 | 4,737 | 744 | 131 | 20 | **0.42%** | 0.01% | 43.4x |
| 5 | 0.999 .. 0.999 | 7,103 | 886 | 132 | 32 | **0.45%** | 0.00% | 330.1x |

RAW  top - bottom = **-22.59 pp**   95% CI (close-cluster bootstrap) [-26.57, -18.72] pp   SE 1.982 pp

EXCESS OVER MODEL, top - bottom = **-5.28 pp**   95% CI [-8.98, -1.70] pp   MDE 5.138 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.22, +5.90] pp, null SE 3.248 pp, permutation p = **0.0020**

### `spread` -- bid-ask spread at entry

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.640 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.001 .. 0.001 | 9,767 | 906 | 132 | 90 | **0.92%** | 0.18% | 5.1x |
| 2 | 0.002 .. 0.005 | 7,074 | 794 | 131 | 52 | **0.74%** | 0.23% | 3.2x |
| 3 | 0.006 .. 0.022 | 5,835 | 601 | 125 | 601 | **10.30%** | 6.43% | 1.6x |
| 4 | 0.023 .. 0.749 | 5,770 | 349 | 116 | 763 | **13.22%** | 11.20% | 1.2x |

RAW  top - bottom = **+12.30 pp**   95% CI (close-cluster bootstrap) [+9.03, +15.59] pp   SE 1.657 pp

EXCESS OVER MODEL, top - bottom = **+1.29 pp**   95% CI [-1.63, +4.24] pp   MDE 4.176 pp

SHUFFLED-LABEL CONTROL: null 95% range [-5.91, +6.56] pp, null SE 3.218 pp, permutation p = **0.0020**

### `size` -- contracts resting at the touch

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 3.655 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 .. 14.99 | 5,627 | 771 | 131 | 278 | **4.94%** | 3.47% | 1.4x |
| 2 | 15 .. 43.98 | 5,700 | 797 | 131 | 321 | **5.63%** | 4.06% | 1.4x |
| 3 | 44 .. 103 | 5,723 | 814 | 130 | 232 | **4.05%** | 3.51% | 1.2x |
| 4 | 103 .. 249.9 | 5,618 | 776 | 129 | 312 | **5.55%** | 3.89% | 1.4x |
| 5 | 250 .. 4.216e+04 | 5,778 | 722 | 131 | 363 | **6.28%** | 3.61% | 1.7x |

RAW  top - bottom = **+1.34 pp**   95% CI (close-cluster bootstrap) [-1.32, +3.93] pp   SE 1.305 pp

EXCESS OVER MODEL, top - bottom = **+1.21 pp**   95% CI [-0.61, +3.03] pp   MDE 2.582 pp

SHUFFLED-LABEL CONTROL: null 95% range [-5.45, +4.58] pp, null SE 2.546 pp, permutation p = **0.4990**

### `age_ms` -- age of the resting level, ms

rows 28,446   closes 132   **loss-carrying closes 67**   losing markets 101   dropped (feature unavailable) 0

**MDE (stated before the estimate): 2.618 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 218 | 5,688 | 871 | 132 | 530 | **9.32%** | 6.03% | 1.5x |
| 2 | 219 .. 865 | 5,688 | 834 | 132 | 458 | **8.05%** | 6.06% | 1.3x |
| 3 | 866 .. 3361 | 5,692 | 875 | 131 | 268 | **4.71%** | 3.85% | 1.2x |
| 4 | 3362 .. 1.98e+04 | 5,689 | 832 | 131 | 145 | **2.55%** | 1.49% | 1.7x |
| 5 | 1.981e+04 .. 8.753e+05 | 5,689 | 744 | 130 | 105 | **1.85%** | 1.11% | 1.7x |

RAW  top - bottom = **-7.47 pp**   95% CI (close-cluster bootstrap) [-9.30, -5.70] pp   SE 0.935 pp

EXCESS OVER MODEL, top - bottom = **-2.55 pp**   95% CI [-4.08, -0.99] pp   MDE 2.137 pp

SHUFFLED-LABEL CONTROL: null 95% range [-4.37, +4.33] pp, null SE 2.284 pp, permutation p = **0.0020**

### control: coin

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| KXBTC15M | 3,755 | 120 | 301 | 8.02% |
| KXETH15M | 3,362 | 117 | 223 | 6.63% |
| KXDOGE15M | 3,530 | 117 | 224 | 6.35% |
| KXZEC15M | 2,583 | 104 | 160 | 6.19% |
| KXSOL15M | 3,419 | 122 | 195 | 5.70% |
| KXBNB15M | 2,512 | 101 | 110 | 4.38% |
| KXNEAR15M | 2,143 | 88 | 92 | 4.29% |
| KXXRP15M | 3,978 | 127 | 120 | 3.02% |
| KXHYPE15M | 3,164 | 118 | 81 | 2.56% |

### control: hour of day (UTC)

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| 1 | 1,106 | 6 | 128 | 11.57% |
| 11 | 775 | 3 | 89 | 11.48% |
| 21 | 1,301 | 6 | 122 | 9.38% |
| 0 | 1,482 | 6 | 133 | 8.97% |
| 3 | 1,393 | 6 | 122 | 8.76% |
| 13 | 1,312 | 6 | 98 | 7.47% |
| 16 | 1,127 | 6 | 83 | 7.36% |
| 12 | 1,145 | 6 | 74 | 6.46% |
| 2 | 1,421 | 6 | 91 | 6.40% |
| 18 | 1,288 | 6 | 73 | 5.67% |
| 19 | 1,046 | 6 | 51 | 4.88% |
| 20 | 1,580 | 6 | 74 | 4.68% |
| 22 | 1,547 | 6 | 71 | 4.59% |
| 23 | 1,246 | 6 | 57 | 4.57% |
| 7 | 1,003 | 5 | 39 | 3.89% |
| 14 | 987 | 6 | 35 | 3.55% |
| 5 | 1,457 | 6 | 47 | 3.23% |
| 17 | 1,143 | 6 | 34 | 2.97% |
| 15 | 1,177 | 6 | 31 | 2.63% |
| 10 | 850 | 3 | 19 | 2.24% |
| 8 | 1,062 | 4 | 19 | 1.79% |
| 4 | 1,154 | 6 | 11 | 0.95% |
| 9 | 593 | 3 | 2 | 0.34% |
| 6 | 1,251 | 6 | 3 | 0.24% |

---

## Population P1_tau45+ -- WIDE, tau 45-60 only -- tau held nearly fixed


### `flat10` -- frac of last 10s prints exactly equal to the previous

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.867 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.1 | 8,212 | 753 | 132 | 543 | **6.61%** | 4.24% | 1.6x |
| 2 | 0.2 .. 0.3 | 2,589 | 417 | 129 | 145 | **5.60%** | 3.53% | 1.6x |
| 3 | 0.4 .. 1 | 2,964 | 319 | 130 | 213 | **7.19%** | 4.58% | 1.6x |

RAW  top - bottom = **+0.57 pp**   95% CI (close-cluster bootstrap) [-3.26, +4.96] pp   SE 2.095 pp

EXCESS OVER MODEL, top - bottom = **+0.23 pp**   95% CI [-2.96, +4.10] pp   MDE 4.982 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.57, +7.58] pp, null SE 3.698 pp, permutation p = **0.8164**

### `flat30` -- frac of last 30s prints exactly equal

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.248 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.03333 | 5,009 | 427 | 130 | 401 | **8.01%** | 4.69% | 1.7x |
| 2 | 0.06667 .. 0.1333 | 2,917 | 329 | 127 | 106 | **3.63%** | 3.20% | 1.1x |
| 3 | 0.1667 .. 0.3333 | 3,068 | 304 | 124 | 169 | **5.51%** | 3.69% | 1.5x |
| 4 | 0.3667 .. 1 | 2,771 | 235 | 128 | 225 | **8.12%** | 4.82% | 1.7x |

RAW  top - bottom = **+0.11 pp**   95% CI (close-cluster bootstrap) [-4.72, +5.37] pp   SE 2.589 pp

EXCESS OVER MODEL, top - bottom = **-0.02 pp**   95% CI [-4.28, +4.69] pp   MDE 6.315 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.05, +8.02] pp, null SE 4.302 pp, permutation p = **0.9461**

### `flat60` -- frac of last 60s prints exactly equal

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.918 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0 | 2,700 | 218 | 120 | 237 | **8.78%** | 5.49% | 1.6x |
| 2 | 0.01667 .. 0.05 | 2,285 | 211 | 108 | 153 | **6.70%** | 3.47% | 1.9x |
| 3 | 0.06667 .. 0.15 | 3,113 | 287 | 121 | 126 | **4.05%** | 3.70% | 1.1x |
| 4 | 0.1667 .. 0.3333 | 2,886 | 258 | 117 | 159 | **5.51%** | 3.51% | 1.6x |
| 5 | 0.35 .. 0.9833 | 2,781 | 223 | 127 | 226 | **8.13%** | 4.71% | 1.7x |

RAW  top - bottom = **-0.65 pp**   95% CI (close-cluster bootstrap) [-6.02, +4.86] pp   SE 2.828 pp

EXCESS OVER MODEL, top - bottom = **+0.13 pp**   95% CI [-4.52, +4.99] pp   MDE 6.648 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.04, +9.14] pp, null SE 4.931 pp, permutation p = **0.9062**

### `flat300` -- frac of last 300s prints exactly equal

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.036 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.006667 | 2,630 | 195 | 120 | 218 | **8.29%** | 5.36% | 1.5x |
| 2 | 0.01 .. 0.07667 | 2,844 | 222 | 117 | 194 | **6.82%** | 3.76% | 1.8x |
| 3 | 0.08 .. 0.1633 | 2,718 | 210 | 114 | 88 | **3.24%** | 3.12% | 1.0x |
| 4 | 0.1667 .. 0.3433 | 2,802 | 206 | 107 | 189 | **6.75%** | 3.78% | 1.8x |
| 5 | 0.3467 .. 0.9467 | 2,771 | 206 | 126 | 212 | **7.65%** | 4.92% | 1.6x |

RAW  top - bottom = **-0.64 pp**   95% CI (close-cluster bootstrap) [-5.45, +4.26] pp   SE 2.513 pp

EXCESS OVER MODEL, top - bottom = **-0.19 pp**   95% CI [-4.34, +3.88] pp   MDE 5.826 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.24, +9.73] pp, null SE 5.107 pp, permutation p = **0.9501**

### `s30_s300` -- sigma_30 / sigma_300  (low = unusually quiet right now)

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.509 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.5268 | 2,753 | 316 | 100 | 175 | **6.36%** | 3.13% | 2.0x |
| 2 | 0.5269 .. 0.7161 | 2,753 | 407 | 119 | 104 | **3.78%** | 3.41% | 1.1x |
| 3 | 0.7161 .. 0.8962 | 2,753 | 412 | 121 | 145 | **5.27%** | 3.59% | 1.5x |
| 4 | 0.8963 .. 1.18 | 2,753 | 381 | 120 | 190 | **6.90%** | 4.51% | 1.5x |
| 5 | 1.18 .. 3.025 | 2,753 | 285 | 105 | 287 | **10.42%** | 6.24% | 1.7x |

RAW  top - bottom = **+4.07 pp**   95% CI (close-cluster bootstrap) [-0.52, +8.66] pp   SE 2.325 pp

EXCESS OVER MODEL, top - bottom = **+0.96 pp**   95% CI [-2.71, +4.46] pp   MDE 5.202 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.55, +8.46] pp, null SE 4.659 pp, permutation p = **0.3154**

### `s300_s900` -- sigma_300 / sigma_900 (low = quiet vs the last 15 min)

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.886 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.3041 .. 0.7832 | 2,753 | 224 | 85 | 145 | **5.27%** | 1.97% | 2.7x |
| 2 | 0.7832 .. 0.907 | 2,753 | 244 | 103 | 201 | **7.30%** | 3.58% | 2.0x |
| 3 | 0.907 .. 1.019 | 2,753 | 257 | 108 | 135 | **4.90%** | 3.90% | 1.3x |
| 4 | 1.019 .. 1.149 | 2,753 | 240 | 103 | 212 | **7.70%** | 5.21% | 1.5x |
| 5 | 1.149 .. 1.693 | 2,753 | 224 | 87 | 208 | **7.56%** | 6.22% | 1.2x |

RAW  top - bottom = **+2.29 pp**   95% CI (close-cluster bootstrap) [-3.76, +7.45] pp   SE 2.816 pp

EXCESS OVER MODEL, top - bottom = **-1.96 pp**   95% CI [-7.43, +2.33] pp   MDE 6.852 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.30, +9.08] pp, null SE 4.653 pp, permutation p = **0.6008**

### `s300_s3600` -- sigma_300 / sigma_3600 (low = quiet vs the hour)

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.793 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2054 .. 0.6594 | 2,753 | 212 | 79 | 155 | **5.63%** | 2.50% | 2.2x |
| 2 | 0.6594 .. 0.8044 | 2,753 | 233 | 99 | 256 | **9.30%** | 4.02% | 2.3x |
| 3 | 0.8044 .. 0.9623 | 2,753 | 243 | 107 | 157 | **5.70%** | 3.82% | 1.5x |
| 4 | 0.9625 .. 1.175 | 2,753 | 236 | 101 | 148 | **5.38%** | 4.95% | 1.1x |
| 5 | 1.175 .. 2.922 | 2,753 | 219 | 79 | 185 | **6.72%** | 5.59% | 1.2x |

RAW  top - bottom = **+1.09 pp**   95% CI (close-cluster bootstrap) [-3.68, +5.69] pp   SE 2.426 pp

EXCESS OVER MODEL, top - bottom = **-2.00 pp**   95% CI [-6.11, +1.69] pp   MDE 5.663 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.41, +9.44] pp, null SE 5.011 pp, permutation p = **0.8343**

### `s300_sday` -- sigma_300 / sigma_86400 (low = quiet vs the day)

rows 13,455   closes 129   **loss-carrying closes 59**   losing markets 89   dropped (feature unavailable) 310

**MDE (stated before the estimate): 9.482 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.09508 .. 0.4013 | 2,691 | 195 | 62 | 283 | **10.52%** | 3.92% | 2.7x |
| 2 | 0.4013 .. 0.5504 | 2,691 | 205 | 93 | 192 | **7.13%** | 4.76% | 1.5x |
| 3 | 0.5505 .. 0.7615 | 2,691 | 223 | 103 | 149 | **5.54%** | 3.86% | 1.4x |
| 4 | 0.7616 .. 1.074 | 2,691 | 217 | 91 | 109 | **4.05%** | 3.61% | 1.1x |
| 5 | 1.075 .. 4.41 | 2,691 | 223 | 79 | 132 | **4.91%** | 4.63% | 1.1x |

RAW  top - bottom = **-5.61 pp**   95% CI (close-cluster bootstrap) [-12.84, +0.43] pp   SE 3.386 pp

EXCESS OVER MODEL, top - bottom = **-6.32 pp**   95% CI [-13.40, -1.03] pp   MDE 8.984 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.62, +10.22] pp, null SE 4.897 pp, permutation p = **0.2615**

### `mx10_sig` -- largest 1s move in last 10s, in sigma_300

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.900 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.7074 | 2,753 | 496 | 125 | 156 | **5.67%** | 3.27% | 1.7x |
| 2 | 0.7074 .. 1.197 | 2,753 | 526 | 130 | 138 | **5.01%** | 3.19% | 1.6x |
| 3 | 1.198 .. 1.823 | 2,753 | 494 | 129 | 144 | **5.23%** | 3.56% | 1.5x |
| 4 | 1.823 .. 2.779 | 2,753 | 446 | 125 | 177 | **6.43%** | 4.65% | 1.4x |
| 5 | 2.78 .. 15.57 | 2,753 | 381 | 121 | 286 | **10.39%** | 6.22% | 1.7x |

RAW  top - bottom = **+4.72 pp**   95% CI (close-cluster bootstrap) [+1.26, +8.09] pp   SE 1.750 pp

EXCESS OVER MODEL, top - bottom = **+1.78 pp**   95% CI [-1.11, +4.72] pp   MDE 4.159 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.70, +5.88] pp, null SE 3.536 pp, permutation p = **0.1357**

### `mx30_sig` -- largest 1s move in last 30s, in sigma_300

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.978 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 1.596 | 2,753 | 330 | 110 | 149 | **5.41%** | 2.99% | 1.8x |
| 2 | 1.596 .. 2.227 | 2,753 | 334 | 118 | 97 | **3.52%** | 3.38% | 1.0x |
| 3 | 2.227 .. 3.028 | 2,753 | 317 | 120 | 156 | **5.67%** | 3.59% | 1.6x |
| 4 | 3.029 .. 4.311 | 2,753 | 297 | 117 | 253 | **9.19%** | 4.79% | 1.9x |
| 5 | 4.311 .. 16.54 | 2,753 | 279 | 108 | 246 | **8.94%** | 6.14% | 1.5x |

RAW  top - bottom = **+3.52 pp**   95% CI (close-cluster bootstrap) [-0.92, +7.67] pp   SE 2.135 pp

EXCESS OVER MODEL, top - bottom = **+0.37 pp**   95% CI [-3.06, +3.55] pp   MDE 4.776 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.46, +8.57] pp, null SE 4.583 pp, permutation p = **0.3453**

### `mx60_sig` -- largest 1s move in last 60s, in sigma_300

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.014 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.4984 .. 2.358 | 2,753 | 261 | 102 | 95 | **3.45%** | 2.86% | 1.2x |
| 2 | 2.358 .. 3.221 | 2,753 | 272 | 109 | 163 | **5.92%** | 3.47% | 1.7x |
| 3 | 3.221 .. 4.117 | 2,753 | 273 | 111 | 203 | **7.37%** | 3.64% | 2.0x |
| 4 | 4.118 .. 5.883 | 2,753 | 271 | 109 | 189 | **6.87%** | 4.54% | 1.5x |
| 5 | 5.885 .. 16.54 | 2,753 | 249 | 103 | 251 | **9.12%** | 6.38% | 1.4x |

RAW  top - bottom = **+5.67 pp**   95% CI (close-cluster bootstrap) [+1.64, +10.10] pp   SE 2.148 pp

EXCESS OVER MODEL, top - bottom = **+2.14 pp**   95% CI [-1.03, +5.63] pp   MDE 4.829 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.61, +8.03] pp, null SE 4.832 pp, permutation p = **0.1497**

### `req_rng30` -- |required move| / index range over last 30s

rows 13,760   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 5

**MDE (stated before the estimate): 7.208 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.0003831 .. 1.234 | 2,752 | 247 | 100 | 677 | **24.60%** | 17.68% | 1.4x |
| 2 | 1.235 .. 2.68 | 2,752 | 352 | 112 | 94 | **3.42%** | 2.39% | 1.4x |
| 3 | 2.681 .. 4.425 | 2,752 | 404 | 117 | 73 | **2.65%** | 0.57% | 4.6x |
| 4 | 4.426 .. 7.884 | 2,752 | 424 | 126 | 22 | **0.80%** | 0.23% | 3.4x |
| 5 | 7.884 .. 68.47 | 2,752 | 356 | 112 | 35 | **1.27%** | 0.02% | 54.3x |

RAW  top - bottom = **-23.33 pp**   95% CI (close-cluster bootstrap) [-28.54, -18.28] pp   SE 2.574 pp

EXCESS OVER MODEL, top - bottom = **-5.68 pp**   95% CI [-10.03, -1.11] pp   MDE 6.335 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.14, +8.61] pp, null SE 4.344 pp, permutation p = **0.0020**

### `req_rng60` -- |required move| / index range over last 60s

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.590 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.0003831 .. 0.7194 | 2,753 | 241 | 100 | 681 | **24.74%** | 17.99% | 1.4x |
| 2 | 0.7194 .. 1.668 | 2,753 | 333 | 115 | 97 | **3.52%** | 2.36% | 1.5x |
| 3 | 1.668 .. 2.717 | 2,753 | 362 | 120 | 29 | **1.05%** | 0.41% | 2.6x |
| 4 | 2.718 .. 4.632 | 2,753 | 364 | 124 | 88 | **3.20%** | 0.12% | 26.8x |
| 5 | 4.633 .. 32.99 | 2,753 | 327 | 107 | 6 | **0.22%** | 0.01% | 24.9x |

RAW  top - bottom = **-24.52 pp**   95% CI (close-cluster bootstrap) [-30.06, -19.47] pp   SE 2.711 pp

EXCESS OVER MODEL, top - bottom = **-6.54 pp**   95% CI [-11.05, -2.33] pp   MDE 6.260 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.92, +8.39] pp, null SE 4.246 pp, permutation p = **0.0020**

### `req_rng300` -- |required move| / index range over last 300s

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.114 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.0001223 .. 0.3125 | 2,753 | 241 | 102 | 726 | **26.37%** | 19.22% | 1.4x |
| 2 | 0.3126 .. 0.5702 | 2,753 | 300 | 109 | 85 | **3.09%** | 1.57% | 2.0x |
| 3 | 0.5702 .. 0.8747 | 2,753 | 338 | 122 | 35 | **1.27%** | 0.10% | 13.4x |
| 4 | 0.8748 .. 1.35 | 2,753 | 349 | 125 | 51 | **1.85%** | 0.00% | 562.0x |
| 5 | 1.35 .. 10.87 | 2,753 | 312 | 112 | 4 | **0.15%** | 0.00% | 11346.2x |

RAW  top - bottom = **-26.23 pp**   95% CI (close-cluster bootstrap) [-31.37, -21.29] pp   SE 2.541 pp

EXCESS OVER MODEL, top - bottom = **-7.01 pp**   95% CI [-11.51, -2.39] pp   MDE 6.632 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.34, +7.81] pp, null SE 4.320 pp, permutation p = **0.0020**

### `gap` -- market implied p(lose) minus model p(lose)

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.947 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.3614 .. 0.001 | 2,753 | 424 | 123 | 366 | **13.29%** | 10.51% | 1.3x |
| 2 | 0.001 .. 0.002 | 2,753 | 514 | 132 | 30 | **1.09%** | 0.16% | 6.9x |
| 3 | 0.002 .. 0.005 | 2,753 | 495 | 130 | 39 | **1.42%** | 0.47% | 3.0x |
| 4 | 0.005 .. 0.01781 | 2,753 | 446 | 124 | 80 | **2.91%** | 1.50% | 1.9x |
| 5 | 0.01783 .. 0.4429 | 2,753 | 333 | 115 | 386 | **14.02%** | 8.25% | 1.7x |

RAW  top - bottom = **+0.73 pp**   95% CI (close-cluster bootstrap) [-4.58, +6.28] pp   SE 2.838 pp

EXCESS OVER MODEL, top - bottom = **+2.99 pp**   95% CI [-1.60, +7.85] pp   MDE 6.844 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.81, +8.61] pp, null SE 4.165 pp, permutation p = **0.8782**

### `lgap` -- log( market implied p(lose) / model p(lose) )

rows 10,379   closes 129   **loss-carrying closes 61**   losing markets 91   dropped (feature unavailable) 3,386

**MDE (stated before the estimate): 9.035 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -3.017 .. 0.1663 | 2,076 | 236 | 102 | 500 | **24.08%** | 19.63% | 1.2x |
| 2 | 0.1664 .. 1.668 | 2,076 | 325 | 113 | 269 | **12.96%** | 7.84% | 1.7x |
| 3 | 1.67 .. 5.019 | 2,075 | 334 | 115 | 48 | **2.31%** | 0.23% | 10.1x |
| 4 | 5.022 .. 10.56 | 2,076 | 337 | 115 | 33 | **1.59%** | 0.00% | 911.7x |
| 5 | 10.56 .. 23.01 | 2,076 | 364 | 125 | 30 | **1.45%** | 0.00% | 807136.3x |

RAW  top - bottom = **-22.64 pp**   95% CI (close-cluster bootstrap) [-28.84, -16.22] pp   SE 3.227 pp

EXCESS OVER MODEL, top - bottom = **-3.01 pp**   95% CI [-8.52, +3.05] pp   MDE 8.252 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.15, +8.19] pp, null SE 4.477 pp, permutation p = **0.0020**

### `z` -- |required move| in model sd (higher should be safer)

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.299 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.0005146 .. 1.777 | 2,753 | 237 | 103 | 739 | **26.84%** | 20.04% | 1.3x |
| 2 | 1.778 .. 3.463 | 2,753 | 327 | 112 | 74 | **2.69%** | 0.84% | 3.2x |
| 3 | 3.463 .. 5.178 | 2,753 | 381 | 117 | 38 | **1.38%** | 0.00% | 337.6x |
| 4 | 5.179 .. 7.757 | 2,753 | 410 | 127 | 40 | **1.45%** | 0.00% | 1480609.9x |
| 5 | 7.757 .. 45.25 | 2,753 | 370 | 120 | 10 | **0.36%** | 0.00% | 26433933992547.0x |

RAW  top - bottom = **-26.48 pp**   95% CI (close-cluster bootstrap) [-31.55, -21.50] pp   SE 2.607 pp

EXCESS OVER MODEL, top - bottom = **-6.44 pp**   95% CI [-11.16, -1.79] pp   MDE 6.886 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.75, +7.85] pp, null SE 4.251 pp, permutation p = **0.0020**

### `pmod` -- model p(lose) at entry

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.299 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 4.33e-15 | 2,753 | 370 | 120 | 10 | **0.36%** | 0.00% | 26433933992547.0x |
| 2 | 4.441e-15 .. 1.114e-07 | 2,753 | 410 | 127 | 40 | **1.45%** | 0.00% | 1480609.9x |
| 3 | 1.121e-07 .. 0.0002668 | 2,753 | 381 | 117 | 38 | **1.38%** | 0.00% | 337.6x |
| 4 | 0.0002674 .. 0.03774 | 2,753 | 327 | 112 | 74 | **2.69%** | 0.84% | 3.2x |
| 5 | 0.03776 .. 0.4998 | 2,753 | 237 | 103 | 739 | **26.84%** | 20.04% | 1.3x |

RAW  top - bottom = **+26.48 pp**   95% CI (close-cluster bootstrap) [+21.52, +31.57] pp   SE 2.607 pp

EXCESS OVER MODEL, top - bottom = **+6.44 pp**   95% CI [+1.85, +11.20] pp   MDE 6.886 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.85, +8.75] pp, null SE 4.251 pp, permutation p = **0.0020**

### `tau` -- seconds to close at entry

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 2.242 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 45 .. 47 | 2,352 | 855 | 131 | 118 | **5.02%** | 3.74% | 1.3x |
| 2 | 48 .. 50 | 2,522 | 872 | 132 | 153 | **6.07%** | 3.85% | 1.6x |
| 3 | 51 .. 53 | 2,588 | 906 | 132 | 174 | **6.72%** | 4.06% | 1.7x |
| 4 | 54 .. 56 | 2,659 | 914 | 131 | 189 | **7.11%** | 4.37% | 1.6x |
| 5 | 57 .. 60 | 3,644 | 968 | 131 | 267 | **7.33%** | 4.63% | 1.6x |

RAW  top - bottom = **+2.31 pp**   95% CI (close-cluster bootstrap) [+0.77, +3.95] pp   SE 0.801 pp

EXCESS OVER MODEL, top - bottom = **+1.42 pp**   95% CI [+0.02, +2.99] pp   MDE 2.110 pp

SHUFFLED-LABEL CONTROL: null 95% range [-2.06, +1.83] pp, null SE 0.995 pp, permutation p = **0.0259**

### `price` -- price paid, dollars

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.376 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.51 .. 0.94 | 2,748 | 249 | 106 | 732 | **26.64%** | 19.08% | 1.4x |
| 2 | 0.941 .. 0.987 | 2,590 | 328 | 113 | 82 | **3.17%** | 1.78% | 1.8x |
| 3 | 0.988 .. 0.995 | 2,279 | 346 | 117 | 33 | **1.45%** | 0.15% | 9.9x |
| 4 | 0.996 .. 0.998 | 2,947 | 436 | 130 | 26 | **0.88%** | 0.04% | 24.9x |
| 5 | 0.999 .. 0.999 | 3,201 | 452 | 130 | 28 | **0.87%** | 0.00% | 869.0x |

RAW  top - bottom = **-25.76 pp**   95% CI (close-cluster bootstrap) [-30.84, -20.72] pp   SE 2.634 pp

EXCESS OVER MODEL, top - bottom = **-6.68 pp**   95% CI [-11.30, -1.94] pp   MDE 6.800 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.62, +6.59] pp, null SE 3.977 pp, permutation p = **0.0020**

### `spread` -- bid-ask spread at entry

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.428 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.001 .. 0.001 | 5,090 | 723 | 132 | 77 | **1.51%** | 0.21% | 7.2x |
| 2 | 0.002 .. 0.004 | 2,828 | 602 | 131 | 31 | **1.10%** | 0.31% | 3.5x |
| 3 | 0.005 .. 0.019 | 2,747 | 557 | 124 | 246 | **8.96%** | 5.17% | 1.7x |
| 4 | 0.02 .. 0.749 | 3,100 | 354 | 115 | 547 | **17.65%** | 13.34% | 1.3x |

RAW  top - bottom = **+16.13 pp**   95% CI (close-cluster bootstrap) [+11.51, +20.65] pp   SE 2.296 pp

EXCESS OVER MODEL, top - bottom = **+3.01 pp**   95% CI [-1.11, +6.89] pp   MDE 5.717 pp

SHUFFLED-LABEL CONTROL: null 95% range [-6.42, +7.09] pp, null SE 3.434 pp, permutation p = **0.0020**

### `size` -- contracts resting at the touch

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.550 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 .. 14.99 | 2,687 | 696 | 130 | 175 | **6.51%** | 3.94% | 1.7x |
| 2 | 15 .. 41.97 | 2,783 | 717 | 131 | 197 | **7.08%** | 4.51% | 1.6x |
| 3 | 42 .. 101 | 2,786 | 726 | 130 | 139 | **4.99%** | 3.90% | 1.3x |
| 4 | 101 .. 253 | 2,754 | 667 | 130 | 190 | **6.90%** | 4.66% | 1.5x |
| 5 | 253 .. 4.216e+04 | 2,755 | 502 | 131 | 200 | **7.26%** | 3.86% | 1.9x |

RAW  top - bottom = **+0.75 pp**   95% CI (close-cluster bootstrap) [-2.49, +3.88] pp   SE 1.625 pp

EXCESS OVER MODEL, top - bottom = **+0.83 pp**   95% CI [-1.67, +3.37] pp   MDE 3.542 pp

SHUFFLED-LABEL CONTROL: null 95% range [-6.78, +6.37] pp, null SE 3.418 pp, permutation p = **0.8064**

### `age_ms` -- age of the resting level, ms

rows 13,765   closes 132   **loss-carrying closes 61**   losing markets 92   dropped (feature unavailable) 0

**MDE (stated before the estimate): 3.621 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 269 | 2,747 | 781 | 132 | 309 | **11.25%** | 7.20% | 1.6x |
| 2 | 270 .. 937 | 2,757 | 792 | 132 | 266 | **9.65%** | 6.42% | 1.5x |
| 3 | 939 .. 3729 | 2,754 | 810 | 131 | 159 | **5.77%** | 4.37% | 1.3x |
| 4 | 3734 .. 2.342e+04 | 2,754 | 661 | 131 | 108 | **3.92%** | 1.70% | 2.3x |
| 5 | 2.346e+04 .. 8.349e+05 | 2,753 | 553 | 127 | 59 | **2.14%** | 1.21% | 1.8x |

RAW  top - bottom = **-9.11 pp**   95% CI (close-cluster bootstrap) [-11.74, -6.57] pp   SE 1.293 pp

EXCESS OVER MODEL, top - bottom = **-3.11 pp**   95% CI [-5.52, -0.89] pp   MDE 3.297 pp

SHUFFLED-LABEL CONTROL: null 95% range [-6.29, +5.56] pp, null SE 2.879 pp, permutation p = **0.0020**

### control: coin

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| KXBTC15M | 1,639 | 119 | 170 | 10.37% |
| KXETH15M | 1,594 | 117 | 149 | 9.35% |
| KXDOGE15M | 1,665 | 116 | 147 | 8.83% |
| KXZEC15M | 1,387 | 103 | 113 | 8.15% |
| KXNEAR15M | 1,165 | 88 | 65 | 5.58% |
| KXSOL15M | 1,650 | 121 | 89 | 5.39% |
| KXXRP15M | 1,825 | 127 | 83 | 4.55% |
| KXBNB15M | 1,232 | 96 | 40 | 3.25% |
| KXHYPE15M | 1,608 | 116 | 45 | 2.80% |

### control: hour of day (UTC)

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| 1 | 529 | 6 | 89 | 16.82% |
| 0 | 669 | 6 | 82 | 12.26% |
| 11 | 334 | 3 | 38 | 11.38% |
| 21 | 605 | 6 | 67 | 11.07% |
| 3 | 627 | 6 | 61 | 9.73% |
| 22 | 668 | 6 | 62 | 9.28% |
| 13 | 738 | 6 | 65 | 8.81% |
| 12 | 593 | 6 | 51 | 8.60% |
| 19 | 530 | 6 | 41 | 7.74% |
| 23 | 587 | 6 | 42 | 7.16% |
| 16 | 554 | 6 | 35 | 6.32% |
| 2 | 676 | 6 | 39 | 5.77% |
| 15 | 588 | 6 | 31 | 5.27% |
| 18 | 625 | 6 | 32 | 5.12% |
| 20 | 750 | 6 | 38 | 5.07% |
| 10 | 392 | 3 | 19 | 4.85% |
| 14 | 541 | 6 | 26 | 4.81% |
| 8 | 487 | 4 | 18 | 3.70% |
| 7 | 501 | 5 | 16 | 3.19% |
| 17 | 574 | 6 | 16 | 2.79% |
| 5 | 648 | 6 | 17 | 2.62% |
| 4 | 614 | 6 | 11 | 1.79% |
| 9 | 312 | 3 | 2 | 0.64% |
| 6 | 623 | 6 | 3 | 0.48% |

---

## Population P1_tau30-44 -- WIDE, tau 30-44 only -- tau held nearly fixed


### `flat10` -- frac of last 10s prints exactly equal to the previous

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.743 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0 | 3,400 | 441 | 126 | 216 | **6.35%** | 4.46% | 1.4x |
| 2 | 0.1 .. 0.1 | 1,687 | 338 | 120 | 36 | **2.13%** | 3.16% | 0.7x |
| 3 | 0.2 .. 0.3 | 1,835 | 307 | 117 | 70 | **3.81%** | 2.81% | 1.4x |
| 4 | 0.4 .. 1 | 2,005 | 258 | 119 | 86 | **4.29%** | 3.44% | 1.2x |

RAW  top - bottom = **-2.06 pp**   95% CI (close-cluster bootstrap) [-5.89, +1.95] pp   SE 2.051 pp

EXCESS OVER MODEL, top - bottom = **-1.05 pp**   95% CI [-4.17, +2.21] pp   MDE 4.578 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.10, +6.92] pp, null SE 4.404 pp, permutation p = **0.7605**

### `flat30` -- frac of last 30s prints exactly equal

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.119 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.03333 | 3,116 | 319 | 123 | 198 | **6.35%** | 4.73% | 1.3x |
| 2 | 0.06667 .. 0.1333 | 1,938 | 243 | 109 | 52 | **2.68%** | 2.49% | 1.1x |
| 3 | 0.1667 .. 0.3333 | 1,971 | 240 | 113 | 61 | **3.09%** | 2.78% | 1.1x |
| 4 | 0.3667 .. 1 | 1,902 | 190 | 115 | 97 | **5.10%** | 3.94% | 1.3x |

RAW  top - bottom = **-1.25 pp**   95% CI (close-cluster bootstrap) [-5.43, +3.16] pp   SE 2.185 pp

EXCESS OVER MODEL, top - bottom = **-0.46 pp**   95% CI [-3.73, +3.05] pp   MDE 4.878 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.15, +8.31] pp, null SE 4.808 pp, permutation p = **0.9062**

### `flat60` -- frac of last 60s prints exactly equal

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.967 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0 | 1,608 | 162 | 106 | 124 | **7.71%** | 5.26% | 1.5x |
| 2 | 0.01667 .. 0.06667 | 1,886 | 203 | 106 | 84 | **4.45%** | 3.80% | 1.2x |
| 3 | 0.08333 .. 0.15 | 1,580 | 178 | 101 | 40 | **2.53%** | 2.17% | 1.2x |
| 4 | 0.1667 .. 0.35 | 2,015 | 202 | 100 | 73 | **3.62%** | 2.94% | 1.2x |
| 5 | 0.3667 .. 0.9667 | 1,838 | 175 | 114 | 87 | **4.73%** | 4.12% | 1.1x |

RAW  top - bottom = **-2.98 pp**   95% CI (close-cluster bootstrap) [-8.49, +2.35] pp   SE 2.845 pp

EXCESS OVER MODEL, top - bottom = **-1.83 pp**   95% CI [-6.43, +2.46] pp   MDE 6.437 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.85, +9.93] pp, null SE 5.746 pp, permutation p = **0.7066**

### `flat300` -- frac of last 300s prints exactly equal

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.361 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.006667 | 1,590 | 151 | 105 | 93 | **5.85%** | 5.11% | 1.1x |
| 2 | 0.01 .. 0.08333 | 1,971 | 187 | 105 | 109 | **5.53%** | 3.51% | 1.6x |
| 3 | 0.08667 .. 0.1733 | 1,752 | 164 | 94 | 47 | **2.68%** | 2.58% | 1.0x |
| 4 | 0.1767 .. 0.35 | 1,810 | 152 | 86 | 66 | **3.65%** | 2.66% | 1.4x |
| 5 | 0.3533 .. 0.94 | 1,804 | 167 | 116 | 93 | **5.16%** | 4.53% | 1.1x |

RAW  top - bottom = **-0.69 pp**   95% CI (close-cluster bootstrap) [-5.96, +4.54] pp   SE 2.629 pp

EXCESS OVER MODEL, top - bottom = **-0.12 pp**   95% CI [-4.34, +3.82] pp   MDE 5.883 pp

SHUFFLED-LABEL CONTROL: null 95% range [-12.14, +10.27] pp, null SE 5.640 pp, permutation p = **0.9920**

### `s30_s300` -- sigma_30 / sigma_300  (low = unusually quiet right now)

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.041 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.5597 | 1,780 | 232 | 92 | 14 | **0.79%** | 1.01% | 0.8x |
| 2 | 0.5597 .. 0.7549 | 1,791 | 276 | 108 | 54 | **3.02%** | 2.78% | 1.1x |
| 3 | 0.755 .. 0.9602 | 1,785 | 308 | 115 | 72 | **4.03%** | 2.82% | 1.4x |
| 4 | 0.9603 .. 1.257 | 1,785 | 268 | 105 | 153 | **8.57%** | 4.68% | 1.8x |
| 5 | 1.257 .. 2.999 | 1,786 | 208 | 84 | 115 | **6.44%** | 6.93% | 0.9x |

RAW  top - bottom = **+5.65 pp**   95% CI (close-cluster bootstrap) [+3.07, +8.76] pp   SE 1.443 pp

EXCESS OVER MODEL, top - bottom = **-0.27 pp**   95% CI [-2.55, +2.31] pp   MDE 3.443 pp

SHUFFLED-LABEL CONTROL: null 95% range [-12.06, +9.59] pp, null SE 5.476 pp, permutation p = **0.2455**

### `s300_s900` -- sigma_300 / sigma_900 (low = quiet vs the last 15 min)

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.967 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2971 .. 0.7999 | 1,785 | 178 | 73 | 47 | **2.63%** | 2.72% | 1.0x |
| 2 | 0.7999 .. 0.9236 | 1,786 | 196 | 92 | 69 | **3.86%** | 2.83% | 1.4x |
| 3 | 0.9237 .. 1.037 | 1,785 | 196 | 93 | 100 | **5.60%** | 2.96% | 1.9x |
| 4 | 1.037 .. 1.158 | 1,786 | 175 | 91 | 116 | **6.49%** | 4.16% | 1.6x |
| 5 | 1.158 .. 1.642 | 1,785 | 161 | 65 | 76 | **4.26%** | 5.57% | 0.8x |

RAW  top - bottom = **+1.62 pp**   95% CI (close-cluster bootstrap) [-1.79, +5.25] pp   SE 1.774 pp

EXCESS OVER MODEL, top - bottom = **-1.23 pp**   95% CI [-4.36, +1.72] pp   MDE 4.392 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.93, +10.14] pp, null SE 5.874 pp, permutation p = **0.6986**

### `s300_s3600` -- sigma_300 / sigma_3600 (low = quiet vs the hour)

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.277 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2168 .. 0.6552 | 1,785 | 173 | 71 | 81 | **4.54%** | 2.55% | 1.8x |
| 2 | 0.6552 .. 0.8157 | 1,786 | 193 | 89 | 82 | **4.59%** | 3.23% | 1.4x |
| 3 | 0.8158 .. 0.9728 | 1,785 | 179 | 88 | 84 | **4.71%** | 3.96% | 1.2x |
| 4 | 0.973 .. 1.167 | 1,786 | 171 | 79 | 56 | **3.14%** | 3.13% | 1.0x |
| 5 | 1.167 .. 2.345 | 1,785 | 164 | 66 | 105 | **5.88%** | 5.36% | 1.1x |

RAW  top - bottom = **+1.34 pp**   95% CI (close-cluster bootstrap) [-2.91, +5.87] pp   SE 2.242 pp

EXCESS OVER MODEL, top - bottom = **-1.47 pp**   95% CI [-4.95, +2.15] pp   MDE 5.062 pp

SHUFFLED-LABEL CONTROL: null 95% range [-12.66, +10.70] pp, null SE 5.667 pp, permutation p = **0.7904**

### `s300_sday` -- sigma_300 / sigma_86400 (low = quiet vs the day)

rows 8,782   closes 127   **loss-carrying closes 39**   losing markets 51   dropped (feature unavailable) 145

**MDE (stated before the estimate): 5.941 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.09649 .. 0.39 | 1,756 | 151 | 49 | 72 | **4.10%** | 2.40% | 1.7x |
| 2 | 0.3901 .. 0.5284 | 1,757 | 165 | 82 | 77 | **4.38%** | 3.55% | 1.2x |
| 3 | 0.5284 .. 0.7166 | 1,756 | 175 | 89 | 103 | **5.87%** | 4.66% | 1.3x |
| 4 | 0.7168 .. 0.9921 | 1,757 | 164 | 78 | 61 | **3.47%** | 2.81% | 1.2x |
| 5 | 0.9946 .. 3.813 | 1,756 | 168 | 68 | 72 | **4.10%** | 4.46% | 0.9x |

RAW  top - bottom = **+0.00 pp**   95% CI (close-cluster bootstrap) [-4.05, +4.14] pp   SE 2.122 pp

EXCESS OVER MODEL, top - bottom = **-2.06 pp**   95% CI [-5.84, +1.73] pp   MDE 5.429 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.88, +10.48] pp, null SE 5.667 pp, permutation p = **0.9661**

### `mx10_sig` -- largest 1s move in last 10s, in sigma_300

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.230 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.766 | 1,785 | 350 | 110 | 67 | **3.75%** | 2.18% | 1.7x |
| 2 | 0.766 .. 1.332 | 1,786 | 372 | 116 | 76 | **4.26%** | 2.84% | 1.5x |
| 3 | 1.332 .. 1.94 | 1,785 | 321 | 116 | 69 | **3.87%** | 3.23% | 1.2x |
| 4 | 1.94 .. 2.988 | 1,784 | 318 | 117 | 71 | **3.98%** | 4.11% | 1.0x |
| 5 | 2.988 .. 16.5 | 1,787 | 265 | 99 | 125 | **6.99%** | 5.86% | 1.2x |

RAW  top - bottom = **+3.24 pp**   95% CI (close-cluster bootstrap) [-0.31, +6.96] pp   SE 1.868 pp

EXCESS OVER MODEL, top - bottom = **-0.43 pp**   95% CI [-3.73, +2.88] pp   MDE 4.744 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.29, +8.85] pp, null SE 4.701 pp, permutation p = **0.5190**

### `mx30_sig` -- largest 1s move in last 30s, in sigma_300

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.686 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 1.732 | 1,785 | 226 | 92 | 34 | **1.90%** | 1.73% | 1.1x |
| 2 | 1.732 .. 2.408 | 1,786 | 233 | 105 | 8 | **0.45%** | 2.39% | 0.2x |
| 3 | 2.408 .. 3.251 | 1,785 | 244 | 115 | 101 | **5.66%** | 3.44% | 1.6x |
| 4 | 3.252 .. 4.724 | 1,786 | 218 | 107 | 135 | **7.56%** | 3.83% | 2.0x |
| 5 | 4.726 .. 16.5 | 1,785 | 189 | 83 | 130 | **7.28%** | 6.83% | 1.1x |

RAW  top - bottom = **+5.38 pp**   95% CI (close-cluster bootstrap) [+2.21, +8.80] pp   SE 1.673 pp

EXCESS OVER MODEL, top - bottom = **+0.28 pp**   95% CI [-2.57, +3.17] pp   MDE 4.173 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.26, +10.48] pp, null SE 5.438 pp, permutation p = **0.2435**

### `mx60_sig` -- largest 1s move in last 60s, in sigma_300

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 3.900 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.5552 .. 2.42 | 1,785 | 195 | 87 | 11 | **0.62%** | 2.11% | 0.3x |
| 2 | 2.42 .. 3.297 | 1,785 | 217 | 101 | 73 | **4.09%** | 2.94% | 1.4x |
| 3 | 3.297 .. 4.27 | 1,785 | 205 | 105 | 92 | **5.15%** | 3.15% | 1.6x |
| 4 | 4.27 .. 6.088 | 1,787 | 198 | 90 | 148 | **8.28%** | 4.55% | 1.8x |
| 5 | 6.088 .. 16.5 | 1,785 | 182 | 89 | 84 | **4.71%** | 5.47% | 0.9x |

RAW  top - bottom = **+4.09 pp**   95% CI (close-cluster bootstrap) [+1.54, +7.04] pp   SE 1.393 pp

EXCESS OVER MODEL, top - bottom = **+0.73 pp**   95% CI [-1.70, +3.51] pp   MDE 3.752 pp

SHUFFLED-LABEL CONTROL: null 95% range [-12.21, +10.64] pp, null SE 6.019 pp, permutation p = **0.4212**

### `req_rng30` -- |required move| / index range over last 30s

rows 8,905   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 22

**MDE (stated before the estimate): 8.629 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 8.037e-05 .. 0.9917 | 1,781 | 161 | 79 | 349 | **19.60%** | 16.54% | 1.2x |
| 2 | 0.9919 .. 2.609 | 1,781 | 241 | 102 | 39 | **2.19%** | 1.42% | 1.5x |
| 3 | 2.61 .. 4.645 | 1,781 | 291 | 114 | 15 | **0.84%** | 0.25% | 3.3x |
| 4 | 4.645 .. 7.939 | 1,781 | 318 | 116 | 1 | **0.06%** | 0.06% | 1.0x |
| 5 | 7.942 .. 76.13 | 1,781 | 290 | 108 | 4 | **0.22%** | 0.00% | 64.8x |

RAW  top - bottom = **-19.37 pp**   95% CI (close-cluster bootstrap) [-25.99, -13.79] pp   SE 3.082 pp

EXCESS OVER MODEL, top - bottom = **-2.84 pp**   95% CI [-8.47, +2.10] pp   MDE 7.435 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.55, +9.77] pp, null SE 5.073 pp, permutation p = **0.0020**

### `req_rng60` -- |required move| / index range over last 60s

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.832 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 7.398e-05 .. 0.6756 | 1,785 | 169 | 83 | 355 | **19.89%** | 16.60% | 1.2x |
| 2 | 0.6757 .. 1.55 | 1,786 | 220 | 94 | 29 | **1.62%** | 1.40% | 1.2x |
| 3 | 1.551 .. 2.733 | 1,785 | 290 | 112 | 9 | **0.50%** | 0.16% | 3.1x |
| 4 | 2.733 .. 4.7 | 1,786 | 295 | 111 | 14 | **0.78%** | 0.06% | 13.7x |
| 5 | 4.701 .. 37.14 | 1,785 | 274 | 105 | 1 | **0.06%** | 0.00% | 13.5x |

RAW  top - bottom = **-19.83 pp**   95% CI (close-cluster bootstrap) [-26.67, -14.17] pp   SE 3.154 pp

EXCESS OVER MODEL, top - bottom = **-3.23 pp**   95% CI [-8.90, +1.79] pp   MDE 7.570 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.92, +10.53] pp, null SE 5.302 pp, permutation p = **0.0020**

### `req_rng300` -- |required move| / index range over last 300s

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.170 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 2.446e-05 .. 0.3109 | 1,785 | 170 | 85 | 366 | **20.50%** | 17.26% | 1.2x |
| 2 | 0.311 .. 0.5724 | 1,786 | 225 | 101 | 33 | **1.85%** | 0.94% | 2.0x |
| 3 | 0.5726 .. 0.8876 | 1,785 | 265 | 103 | 4 | **0.22%** | 0.03% | 6.5x |
| 4 | 0.8879 .. 1.404 | 1,786 | 281 | 117 | 4 | **0.22%** | 0.00% | 222.0x |
| 5 | 1.404 .. 12.15 | 1,785 | 280 | 109 | 1 | **0.06%** | 0.00% | 5485716.8x |

RAW  top - bottom = **-20.45 pp**   95% CI (close-cluster bootstrap) [-26.44, -14.91] pp   SE 2.918 pp

EXCESS OVER MODEL, top - bottom = **-3.19 pp**   95% CI [-8.60, +1.92] pp   MDE 7.463 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.03, +9.41] pp, null SE 5.080 pp, permutation p = **0.0020**

### `gap` -- market implied p(lose) minus model p(lose)

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.462 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.3496 .. 0.001 | 1,779 | 345 | 119 | 204 | **11.47%** | 9.02% | 1.3x |
| 2 | 0.001 .. 0.002 | 1,792 | 410 | 125 | 5 | **0.28%** | 0.13% | 2.1x |
| 3 | 0.002 .. 0.004 | 1,704 | 368 | 122 | 5 | **0.29%** | 0.17% | 1.7x |
| 4 | 0.004 .. 0.01568 | 1,867 | 342 | 115 | 31 | **1.66%** | 1.30% | 1.3x |
| 5 | 0.01569 .. 0.4066 | 1,785 | 227 | 96 | 163 | **9.13%** | 7.58% | 1.2x |

RAW  top - bottom = **-2.34 pp**   95% CI (close-cluster bootstrap) [-6.77, +2.30] pp   SE 2.308 pp

EXCESS OVER MODEL, top - bottom = **-0.89 pp**   95% CI [-4.87, +3.06] pp   MDE 5.559 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.41, +9.66] pp, null SE 4.811 pp, permutation p = **0.5449**

### `lgap` -- log( market implied p(lose) / model p(lose) )

rows 5,977   closes 122   **loss-carrying closes 41**   losing markets 51   dropped (feature unavailable) 2,950

**MDE (stated before the estimate): 10.296 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -3.016 .. 0.2145 | 1,195 | 164 | 91 | 287 | **24.02%** | 20.49% | 1.2x |
| 2 | 0.2146 .. 1.837 | 1,196 | 208 | 98 | 100 | **8.36%** | 6.54% | 1.3x |
| 3 | 1.837 .. 5.663 | 1,195 | 230 | 102 | 11 | **0.92%** | 0.20% | 4.6x |
| 4 | 5.667 .. 11.9 | 1,196 | 255 | 107 | 1 | **0.08%** | 0.00% | 113.4x |
| 5 | 11.91 .. 23.83 | 1,195 | 284 | 115 | 3 | **0.25%** | 0.00% | 479715.9x |

RAW  top - bottom = **-23.77 pp**   95% CI (close-cluster bootstrap) [-31.15, -16.72] pp   SE 3.677 pp

EXCESS OVER MODEL, top - bottom = **-3.28 pp**   95% CI [-9.94, +2.86] pp   MDE 9.272 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.21, +9.71] pp, null SE 5.349 pp, permutation p = **0.0020**

### `z` -- |required move| in model sd (higher should be safer)

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.079 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.00026 .. 2.002 | 1,785 | 177 | 87 | 385 | **21.57%** | 17.82% | 1.2x |
| 2 | 2.002 .. 4.041 | 1,786 | 252 | 103 | 14 | **0.78%** | 0.41% | 1.9x |
| 3 | 4.042 .. 6.176 | 1,785 | 311 | 112 | 2 | **0.11%** | 0.00% | 378.3x |
| 4 | 6.176 .. 9.462 | 1,786 | 344 | 119 | 6 | **0.34%** | 0.00% | 152437026.1x |
| 5 | 9.463 .. 54.86 | 1,785 | 308 | 119 | 1 | **0.06%** | 0.00% | 42718029464537931776.0x |

RAW  top - bottom = **-21.51 pp**   95% CI (close-cluster bootstrap) [-27.24, -16.07] pp   SE 2.885 pp

EXCESS OVER MODEL, top - bottom = **-3.69 pp**   95% CI [-9.15, +1.57] pp   MDE 7.729 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.80, +9.08] pp, null SE 5.056 pp, permutation p = **0.0020**

### `pmod` -- model p(lose) at entry

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.109 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 8.646e-29 | 1,785 | 307 | 116 | 2 | **0.11%** | 0.00% | 1700139657288367258428506112.0x |
| 2 | 8.973e-29 .. 3.287e-10 | 1,786 | 346 | 118 | 5 | **0.28%** | 0.00% | 127030855.0x |
| 3 | 3.293e-10 .. 2.645e-05 | 1,785 | 311 | 112 | 2 | **0.11%** | 0.00% | 378.3x |
| 4 | 2.657e-05 .. 0.02265 | 1,786 | 252 | 103 | 14 | **0.78%** | 0.41% | 1.9x |
| 5 | 0.02265 .. 0.4999 | 1,785 | 177 | 87 | 385 | **21.57%** | 17.82% | 1.2x |

RAW  top - bottom = **+21.46 pp**   95% CI (close-cluster bootstrap) [+16.02, +27.24] pp   SE 2.896 pp

EXCESS OVER MODEL, top - bottom = **+3.63 pp**   95% CI [-1.64, +9.15] pp   MDE 7.766 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.97, +8.46] pp, null SE 5.006 pp, permutation p = **0.0020**

### `tau` -- seconds to close at entry

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 2.603 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 30 .. 32 | 1,455 | 533 | 124 | 55 | **3.78%** | 3.41% | 1.1x |
| 2 | 33 .. 35 | 1,645 | 605 | 121 | 76 | **4.62%** | 3.44% | 1.3x |
| 3 | 36 .. 38 | 1,823 | 655 | 125 | 85 | **4.66%** | 3.44% | 1.4x |
| 4 | 39 .. 41 | 1,942 | 692 | 129 | 85 | **4.38%** | 3.80% | 1.2x |
| 5 | 42 .. 44 | 2,062 | 733 | 129 | 107 | **5.19%** | 4.01% | 1.3x |

RAW  top - bottom = **+1.41 pp**   95% CI (close-cluster bootstrap) [-0.31, +3.27] pp   SE 0.930 pp

EXCESS OVER MODEL, top - bottom = **+0.81 pp**   95% CI [-0.90, +2.76] pp   MDE 2.645 pp

SHUFFLED-LABEL CONTROL: null 95% range [-3.28, +3.09] pp, null SE 1.579 pp, permutation p = **0.3972**

### `price` -- price paid, dollars

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.971 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.51 .. 0.948 | 1,762 | 172 | 85 | 370 | **21.00%** | 17.17% | 1.2x |
| 2 | 0.949 .. 0.989 | 1,682 | 231 | 98 | 29 | **1.72%** | 1.30% | 1.3x |
| 3 | 0.99 .. 0.996 | 1,503 | 276 | 107 | 2 | **0.13%** | 0.06% | 2.4x |
| 4 | 0.997 .. 0.998 | 1,525 | 326 | 121 | 3 | **0.20%** | 0.01% | 28.4x |
| 5 | 0.999 .. 0.999 | 2,455 | 438 | 126 | 4 | **0.16%** | 0.00% | 72.5x |

RAW  top - bottom = **-20.84 pp**   95% CI (close-cluster bootstrap) [-26.57, -15.45] pp   SE 2.847 pp

EXCESS OVER MODEL, top - bottom = **-3.67 pp**   95% CI [-9.19, +1.39] pp   MDE 7.463 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.22, +8.85] pp, null SE 4.701 pp, permutation p = **0.0020**

### `spread` -- bid-ask spread at entry

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 5.848 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.001 .. 0.001 | 3,211 | 569 | 129 | 12 | **0.37%** | 0.17% | 2.1x |
| 2 | 0.002 .. 0.004 | 1,961 | 452 | 123 | 14 | **0.71%** | 0.21% | 3.3x |
| 3 | 0.005 .. 0.022 | 1,968 | 409 | 118 | 177 | **8.99%** | 5.81% | 1.5x |
| 4 | 0.023 .. 0.51 | 1,787 | 240 | 107 | 205 | **11.47%** | 11.26% | 1.0x |

RAW  top - bottom = **+11.10 pp**   95% CI (close-cluster bootstrap) [+7.22, +15.48] pp   SE 2.089 pp

EXCESS OVER MODEL, top - bottom = **+0.01 pp**   95% CI [-3.65, +3.84] pp   MDE 5.308 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.35, +9.00] pp, null SE 4.167 pp, permutation p = **0.0120**

### `size` -- contracts resting at the touch

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 4.545 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 .. 14.01 | 1,785 | 495 | 123 | 82 | **4.59%** | 3.72% | 1.2x |
| 2 | 14.02 .. 43.98 | 1,776 | 510 | 123 | 78 | **4.39%** | 3.88% | 1.1x |
| 3 | 44 .. 104.7 | 1,795 | 549 | 125 | 54 | **3.01%** | 3.52% | 0.9x |
| 4 | 105 .. 257 | 1,786 | 469 | 122 | 96 | **5.38%** | 3.83% | 1.4x |
| 5 | 257.7 .. 3.219e+04 | 1,785 | 384 | 125 | 98 | **5.49%** | 3.29% | 1.7x |

RAW  top - bottom = **+0.90 pp**   95% CI (close-cluster bootstrap) [-2.30, +4.16] pp   SE 1.623 pp

EXCESS OVER MODEL, top - bottom = **+1.33 pp**   95% CI [-1.17, +3.86] pp   MDE 3.579 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.68, +6.55] pp, null SE 3.678 pp, permutation p = **0.7864**

### `age_ms` -- age of the resting level, ms

rows 8,927   closes 129   **loss-carrying closes 41**   losing markets 54   dropped (feature unavailable) 0

**MDE (stated before the estimate): 3.867 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 218 | 1,783 | 583 | 127 | 167 | **9.37%** | 6.07% | 1.5x |
| 2 | 219 .. 925 | 1,788 | 572 | 123 | 127 | **7.10%** | 6.20% | 1.1x |
| 3 | 926 .. 4098 | 1,785 | 570 | 126 | 67 | **3.75%** | 3.84% | 1.0x |
| 4 | 4106 .. 2.056e+04 | 1,786 | 452 | 123 | 17 | **0.95%** | 1.02% | 0.9x |
| 5 | 2.061e+04 .. 8.491e+05 | 1,785 | 383 | 115 | 30 | **1.68%** | 1.10% | 1.5x |

RAW  top - bottom = **-7.69 pp**   95% CI (close-cluster bootstrap) [-10.56, -5.18] pp   SE 1.381 pp

EXCESS OVER MODEL, top - bottom = **-2.72 pp**   95% CI [-5.14, -0.60] pp   MDE 3.205 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.23, +6.45] pp, null SE 3.411 pp, permutation p = **0.0259**

### control: coin

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| KXBTC15M | 1,153 | 97 | 89 | 7.72% |
| KXETH15M | 921 | 79 | 50 | 5.43% |
| KXSOL15M | 1,143 | 103 | 62 | 5.42% |
| KXDOGE15M | 1,166 | 95 | 62 | 5.32% |
| KXZEC15M | 770 | 77 | 37 | 4.81% |
| KXBNB15M | 844 | 80 | 30 | 3.55% |
| KXXRP15M | 1,296 | 108 | 37 | 2.85% |
| KXHYPE15M | 1,005 | 89 | 26 | 2.59% |
| KXNEAR15M | 629 | 60 | 15 | 2.38% |

### control: hour of day (UTC)

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| 11 | 261 | 3 | 37 | 14.18% |
| 3 | 451 | 6 | 43 | 9.53% |
| 2 | 432 | 6 | 41 | 9.49% |
| 0 | 455 | 6 | 41 | 9.01% |
| 1 | 343 | 6 | 25 | 7.29% |
| 12 | 318 | 5 | 23 | 7.23% |
| 21 | 422 | 6 | 26 | 6.16% |
| 16 | 326 | 6 | 20 | 6.13% |
| 7 | 324 | 5 | 18 | 5.56% |
| 18 | 442 | 5 | 23 | 5.20% |
| 17 | 358 | 6 | 18 | 5.03% |
| 13 | 386 | 6 | 18 | 4.66% |
| 23 | 396 | 6 | 15 | 3.79% |
| 19 | 308 | 6 | 10 | 3.25% |
| 5 | 478 | 6 | 15 | 3.14% |
| 20 | 519 | 6 | 16 | 3.08% |
| 14 | 305 | 5 | 9 | 2.95% |
| 22 | 487 | 6 | 9 | 1.85% |
| 8 | 338 | 4 | 1 | 0.30% |
| 15 | 368 | 6 | 0 | 0.00% |
| 4 | 370 | 6 | 0 | 0.00% |
| 6 | 374 | 6 | 0 | 0.00% |
| 9 | 198 | 3 | 0 | 0.00% |
| 10 | 268 | 3 | 0 | 0.00% |

---

## Population P2 -- WIDE and the LIVE RULE's gates (price<=98.8c, model p<=2%, EV>=0.3c)


**FEWER THAN 30 LOSS-CARRYING CLOSES (10) -- NO SIGNIFICANCE IS CLAIMED ANYWHERE IN THIS POPULATION.** The intervals are printed so the size of the uncertainty is visible, not so they can be read as findings.


### `flat10` -- frac of last 10s prints exactly equal to the previous

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 2.293 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.1 | 2,795 | 317 | 114 | 40 | **1.43%** | 0.41% | 3.5x |
| 2 | 0.2 .. 0.2 | 579 | 133 | 84 | 2 | **0.35%** | 0.35% | 1.0x |
| 3 | 0.3 .. 1 | 1,322 | 175 | 92 | 13 | **0.98%** | 0.39% | 2.6x |

RAW  top - bottom = **-0.45 pp**   95% CI (close-cluster bootstrap) [-2.03, +1.24] pp   SE 0.819 pp

EXCESS OVER MODEL, top - bottom = **-0.43 pp**   95% CI [-2.01, +1.25] pp   MDE 2.274 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.31, +10.56] pp, null SE 5.591 pp, permutation p = **0.9341**

### `flat30` -- frac of last 30s prints exactly equal

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 2.964 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.03333 | 1,823 | 200 | 102 | 31 | **1.70%** | 0.38% | 4.5x |
| 2 | 0.06667 .. 0.1333 | 951 | 123 | 81 | 1 | **0.11%** | 0.46% | 0.2x |
| 3 | 0.1667 .. 0.2667 | 907 | 109 | 74 | 8 | **0.88%** | 0.34% | 2.6x |
| 4 | 0.3 .. 1 | 1,015 | 127 | 81 | 15 | **1.48%** | 0.40% | 3.7x |

RAW  top - bottom = **-0.22 pp**   95% CI (close-cluster bootstrap) [-2.20, +1.94] pp   SE 1.058 pp

EXCESS OVER MODEL, top - bottom = **-0.25 pp**   95% CI [-2.21, +1.91] pp   MDE 2.955 pp

SHUFFLED-LABEL CONTROL: null 95% range [-14.86, +13.12] pp, null SE 7.014 pp, permutation p = **0.9800**

### `flat60` -- frac of last 60s prints exactly equal

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 3.034 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.05 | 1,739 | 179 | 99 | 31 | **1.78%** | 0.38% | 4.7x |
| 2 | 0.06667 .. 0.15 | 1,036 | 108 | 77 | 2 | **0.19%** | 0.45% | 0.4x |
| 3 | 0.1667 .. 0.3 | 971 | 101 | 71 | 8 | **0.82%** | 0.33% | 2.5x |
| 4 | 0.3167 .. 0.9833 | 950 | 107 | 75 | 14 | **1.47%** | 0.42% | 3.5x |

RAW  top - bottom = **-0.31 pp**   95% CI (close-cluster bootstrap) [-2.35, +1.88] pp   SE 1.084 pp

EXCESS OVER MODEL, top - bottom = **-0.35 pp**   95% CI [-2.39, +1.83] pp   MDE 3.033 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.62, +14.78] pp, null SE 7.501 pp, permutation p = **0.9980**

### `flat300` -- frac of last 300s prints exactly equal

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 5.277 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.003333 | 662 | 72 | 63 | 16 | **2.42%** | 0.44% | 5.6x |
| 2 | 0.006667 .. 0.07667 | 1,205 | 119 | 78 | 15 | **1.24%** | 0.36% | 3.4x |
| 3 | 0.08 .. 0.19 | 949 | 91 | 66 | 2 | **0.21%** | 0.44% | 0.5x |
| 4 | 0.1933 .. 0.3033 | 936 | 73 | 53 | 15 | **1.60%** | 0.31% | 5.2x |
| 5 | 0.3067 .. 0.9367 | 944 | 100 | 72 | 7 | **0.74%** | 0.43% | 1.7x |

RAW  top - bottom = **-1.68 pp**   95% CI (close-cluster bootstrap) [-5.72, +1.56] pp   SE 1.885 pp

EXCESS OVER MODEL, top - bottom = **-1.67 pp**   95% CI [-5.74, +1.55] pp   MDE 5.266 pp

SHUFFLED-LABEL CONTROL: null 95% range [-19.13, +18.60] pp, null SE 9.548 pp, permutation p = **0.8683**

### `s30_s300` -- sigma_30 / sigma_300  (low = unusually quiet right now)

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.055 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.5968 | 939 | 143 | 81 | 24 | **2.56%** | 0.38% | 6.8x |
| 2 | 0.5971 .. 0.7958 | 939 | 159 | 97 | 4 | **0.43%** | 0.38% | 1.1x |
| 3 | 0.796 .. 1.02 | 940 | 174 | 87 | 14 | **1.49%** | 0.45% | 3.3x |
| 4 | 1.02 .. 1.375 | 939 | 140 | 73 | 9 | **0.96%** | 0.38% | 2.5x |
| 5 | 1.375 .. 3.024 | 939 | 107 | 57 | 4 | **0.43%** | 0.37% | 1.1x |

RAW  top - bottom = **-2.13 pp**   95% CI (close-cluster bootstrap) [-5.37, +0.06] pp   SE 1.448 pp

EXCESS OVER MODEL, top - bottom = **-2.13 pp**   95% CI [-5.35, +0.06] pp   MDE 4.022 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.12, +16.29] pp, null SE 8.101 pp, permutation p = **0.8064**

### `s300_s900` -- sigma_300 / sigma_900 (low = quiet vs the last 15 min)

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 0.714 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.3903 .. 0.7981 | 939 | 82 | 46 | 2 | **0.21%** | 0.32% | 0.7x |
| 2 | 0.7984 .. 0.9154 | 939 | 105 | 64 | 25 | **2.66%** | 0.37% | 7.1x |
| 3 | 0.9155 .. 1.039 | 940 | 110 | 74 | 14 | **1.49%** | 0.38% | 3.9x |
| 4 | 1.039 .. 1.173 | 939 | 107 | 70 | 13 | **1.38%** | 0.53% | 2.6x |
| 5 | 1.173 .. 1.642 | 939 | 102 | 51 | 1 | **0.11%** | 0.36% | 0.3x |

RAW  top - bottom = **-0.11 pp**   95% CI (close-cluster bootstrap) [-0.67, +0.30] pp   SE 0.255 pp

EXCESS OVER MODEL, top - bottom = **-0.15 pp**   95% CI [-0.72, +0.27] pp   MDE 0.719 pp

SHUFFLED-LABEL CONTROL: null 95% range [-18.96, +17.47] pp, null SE 9.231 pp, permutation p = **0.9880**

### `s300_s3600` -- sigma_300 / sigma_3600 (low = quiet vs the hour)

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 3.867 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2056 .. 0.6577 | 939 | 88 | 52 | 20 | **2.13%** | 0.33% | 6.5x |
| 2 | 0.6581 .. 0.783 | 939 | 89 | 59 | 7 | **0.75%** | 0.29% | 2.5x |
| 3 | 0.7832 .. 0.9305 | 940 | 107 | 63 | 25 | **2.66%** | 0.43% | 6.2x |
| 4 | 0.9306 .. 1.124 | 939 | 103 | 65 | 0 | **0.00%** | 0.43% | 0.0x |
| 5 | 1.124 .. 2.434 | 939 | 114 | 55 | 3 | **0.32%** | 0.48% | 0.7x |

RAW  top - bottom = **-1.81 pp**   95% CI (close-cluster bootstrap) [-5.11, +0.21] pp   SE 1.381 pp

EXCESS OVER MODEL, top - bottom = **-1.96 pp**   95% CI [-5.23, +0.05] pp   MDE 3.848 pp

SHUFFLED-LABEL CONTROL: null 95% range [-17.57, +15.97] pp, null SE 8.750 pp, permutation p = **0.8184**

### `s300_sday` -- sigma_300 / sigma_86400 (low = quiet vs the day)

rows 4,634   closes 116   **loss-carrying closes 9**   losing markets 11   dropped (feature unavailable) 62

**BELOW THE 30-CLUSTER FLOOR (9 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 2.295 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.1224 .. 0.3383 | 927 | 60 | 32 | 2 | **0.22%** | 0.23% | 0.9x |
| 2 | 0.3384 .. 0.484 | 927 | 91 | 48 | 22 | **2.37%** | 0.34% | 6.9x |
| 3 | 0.484 .. 0.6793 | 926 | 109 | 69 | 21 | **2.27%** | 0.44% | 5.2x |
| 4 | 0.6794 .. 0.9467 | 927 | 96 | 65 | 0 | **0.00%** | 0.45% | 0.0x |
| 5 | 0.9467 .. 4.141 | 927 | 103 | 52 | 9 | **0.97%** | 0.50% | 1.9x |

RAW  top - bottom = **+0.76 pp**   95% CI (close-cluster bootstrap) [-0.48, +2.66] pp   SE 0.820 pp

EXCESS OVER MODEL, top - bottom = **+0.49 pp**   95% CI [-0.77, +2.35] pp   MDE 2.290 pp

SHUFFLED-LABEL CONTROL: null 95% range [-21.25, +19.96] pp, null SE 9.837 pp, permutation p = **0.9341**

### `mx10_sig` -- largest 1s move in last 10s, in sigma_300

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.026 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.7329 | 939 | 186 | 92 | 18 | **1.92%** | 0.36% | 5.4x |
| 2 | 0.7332 .. 1.158 | 939 | 193 | 89 | 11 | **1.17%** | 0.34% | 3.4x |
| 3 | 1.159 .. 1.831 | 940 | 197 | 90 | 6 | **0.64%** | 0.38% | 1.7x |
| 4 | 1.831 .. 2.911 | 939 | 185 | 92 | 10 | **1.06%** | 0.44% | 2.4x |
| 5 | 2.933 .. 16.15 | 939 | 156 | 74 | 10 | **1.06%** | 0.45% | 2.4x |

RAW  top - bottom = **-0.85 pp**   95% CI (close-cluster bootstrap) [-4.01, +1.61] pp   SE 1.438 pp

EXCESS OVER MODEL, top - bottom = **-0.95 pp**   95% CI [-4.13, +1.49] pp   MDE 4.016 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.93, +11.50] pp, null SE 6.192 pp, permutation p = **0.8842**

### `mx30_sig` -- largest 1s move in last 30s, in sigma_300

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.289 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 1.771 | 939 | 129 | 75 | 19 | **2.02%** | 0.35% | 5.7x |
| 2 | 1.771 .. 2.526 | 939 | 141 | 83 | 8 | **0.85%** | 0.41% | 2.1x |
| 3 | 2.527 .. 3.624 | 940 | 141 | 85 | 16 | **1.70%** | 0.40% | 4.2x |
| 4 | 3.624 .. 5.228 | 938 | 120 | 72 | 2 | **0.21%** | 0.42% | 0.5x |
| 5 | 5.231 .. 16.52 | 940 | 101 | 57 | 10 | **1.06%** | 0.38% | 2.8x |

RAW  top - bottom = **-0.96 pp**   95% CI (close-cluster bootstrap) [-4.35, +1.57] pp   SE 1.532 pp

EXCESS OVER MODEL, top - bottom = **-0.98 pp**   95% CI [-4.35, +1.52] pp   MDE 4.255 pp

SHUFFLED-LABEL CONTROL: null 95% range [-16.02, +17.08] pp, null SE 8.011 pp, permutation p = **0.9401**

### `mx60_sig` -- largest 1s move in last 60s, in sigma_300

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.201 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.6968 .. 2.646 | 939 | 128 | 70 | 23 | **2.45%** | 0.42% | 5.8x |
| 2 | 2.646 .. 3.749 | 939 | 120 | 77 | 20 | **2.13%** | 0.43% | 5.0x |
| 3 | 3.75 .. 5.048 | 940 | 112 | 74 | 1 | **0.11%** | 0.40% | 0.3x |
| 4 | 5.048 .. 6.963 | 939 | 105 | 65 | 10 | **1.06%** | 0.38% | 2.8x |
| 5 | 6.966 .. 16.52 | 939 | 94 | 56 | 1 | **0.11%** | 0.33% | 0.3x |

RAW  top - bottom = **-2.34 pp**   95% CI (close-cluster bootstrap) [-5.63, +0.13] pp   SE 1.500 pp

EXCESS OVER MODEL, top - bottom = **-2.25 pp**   95% CI [-5.52, +0.20] pp   MDE 4.178 pp

SHUFFLED-LABEL CONTROL: null 95% range [-17.78, +16.72] pp, null SE 8.705 pp, permutation p = **0.7745**

### `req_rng30` -- |required move| / index range over last 30s

rows 4,691   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 5

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 3.738 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2178 .. 0.9557 | 938 | 132 | 67 | 1 | **0.11%** | 0.55% | 0.2x |
| 2 | 0.9568 .. 1.566 | 938 | 192 | 91 | 16 | **1.71%** | 0.48% | 3.5x |
| 3 | 1.568 .. 2.357 | 939 | 210 | 101 | 2 | **0.21%** | 0.42% | 0.5x |
| 4 | 2.359 .. 3.833 | 938 | 202 | 94 | 11 | **1.17%** | 0.35% | 3.3x |
| 5 | 3.835 .. 46.87 | 938 | 148 | 79 | 25 | **2.67%** | 0.15% | 17.6x |

RAW  top - bottom = **+2.56 pp**   95% CI (close-cluster bootstrap) [+0.36, +5.53] pp   SE 1.335 pp

EXCESS OVER MODEL, top - bottom = **+2.96 pp**   95% CI [+0.75, +5.92] pp   MDE 3.713 pp

SHUFFLED-LABEL CONTROL: null 95% range [-14.07, +14.61] pp, null SE 7.385 pp, permutation p = **0.7465**

### `req_rng60` -- |required move| / index range over last 60s

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.896 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.174 .. 0.646 | 939 | 151 | 75 | 2 | **0.21%** | 0.63% | 0.3x |
| 2 | 0.6464 .. 0.9344 | 939 | 195 | 90 | 10 | **1.06%** | 0.41% | 2.6x |
| 3 | 0.9353 .. 1.322 | 940 | 200 | 90 | 5 | **0.53%** | 0.38% | 1.4x |
| 4 | 1.322 .. 2.086 | 939 | 179 | 88 | 7 | **0.75%** | 0.36% | 2.0x |
| 5 | 2.089 .. 20.12 | 939 | 141 | 75 | 31 | **3.30%** | 0.18% | 18.3x |

RAW  top - bottom = **+3.09 pp**   95% CI (close-cluster bootstrap) [+0.19, +6.90] pp   SE 1.749 pp

EXCESS OVER MODEL, top - bottom = **+3.54 pp**   95% CI [+0.65, +7.32] pp   MDE 4.861 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.02, +15.12] pp, null SE 7.836 pp, permutation p = **0.6886**

### `req_rng300` -- |required move| / index range over last 300s

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 3.506 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.06429 .. 0.3338 | 939 | 150 | 81 | 11 | **1.17%** | 0.76% | 1.6x |
| 2 | 0.3339 .. 0.4232 | 939 | 215 | 101 | 5 | **0.53%** | 0.56% | 1.0x |
| 3 | 0.4234 .. 0.5188 | 940 | 220 | 96 | 15 | **1.60%** | 0.40% | 4.0x |
| 4 | 0.519 .. 0.6771 | 939 | 204 | 92 | 12 | **1.28%** | 0.19% | 6.6x |
| 5 | 0.6772 .. 3.196 | 939 | 162 | 80 | 12 | **1.28%** | 0.06% | 21.7x |

RAW  top - bottom = **+0.11 pp**   95% CI (close-cluster bootstrap) [-2.36, +2.66] pp   SE 1.252 pp

EXCESS OVER MODEL, top - bottom = **+0.80 pp**   95% CI [-1.67, +3.36] pp   MDE 3.498 pp

SHUFFLED-LABEL CONTROL: null 95% range [-14.59, +14.48] pp, null SE 7.450 pp, permutation p = **0.9980**

### `gap` -- market implied p(lose) minus model p(lose)

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 2.536 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.006463 .. 0.01395 | 939 | 310 | 114 | 3 | **0.32%** | 0.57% | 0.6x |
| 2 | 0.01395 .. 0.019 | 939 | 292 | 114 | 4 | **0.43%** | 0.23% | 1.9x |
| 3 | 0.019 .. 0.02598 | 940 | 267 | 106 | 2 | **0.21%** | 0.20% | 1.1x |
| 4 | 0.02598 .. 0.042 | 939 | 215 | 94 | 28 | **2.98%** | 0.37% | 8.1x |
| 5 | 0.042 .. 0.4429 | 939 | 170 | 85 | 18 | **1.92%** | 0.60% | 3.2x |

RAW  top - bottom = **+1.60 pp**   95% CI (close-cluster bootstrap) [+0.09, +3.56] pp   SE 0.906 pp

EXCESS OVER MODEL, top - bottom = **+1.57 pp**   95% CI [+0.07, +3.51] pp   MDE 2.519 pp

SHUFFLED-LABEL CONTROL: null 95% range [-12.25, +12.89] pp, null SE 6.369 pp, permutation p = **0.7984**

### `lgap` -- log( market implied p(lose) / model p(lose) )

rows 4,513   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 183

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 1.625 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.4036 .. 1.497 | 903 | 238 | 105 | 11 | **1.22%** | 1.15% | 1.1x |
| 2 | 1.498 .. 2.459 | 902 | 249 | 104 | 22 | **2.44%** | 0.63% | 3.9x |
| 3 | 2.462 .. 3.914 | 903 | 253 | 102 | 11 | **1.22%** | 0.24% | 5.2x |
| 4 | 3.917 .. 6.643 | 902 | 244 | 102 | 9 | **1.00%** | 0.03% | 35.1x |
| 5 | 6.673 .. 24.48 | 903 | 196 | 86 | 2 | **0.22%** | 0.00% | 295.1x |

RAW  top - bottom = **-1.00 pp**   95% CI (close-cluster bootstrap) [-2.22, +0.00] pp   SE 0.580 pp

EXCESS OVER MODEL, top - bottom = **+0.15 pp**   95% CI [-1.07, +1.15] pp   MDE 1.619 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.30, +11.30] pp, null SE 5.896 pp, permutation p = **0.8822**

### `z` -- |required move| in model sd (higher should be safer)

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 2.813 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 2.054 .. 2.403 | 939 | 268 | 103 | 20 | **2.13%** | 1.34% | 1.6x |
| 2 | 2.404 .. 2.809 | 939 | 280 | 109 | 14 | **1.49%** | 0.49% | 3.1x |
| 3 | 2.81 .. 3.336 | 940 | 289 | 107 | 14 | **1.49%** | 0.13% | 11.8x |
| 4 | 3.336 .. 4.177 | 939 | 258 | 106 | 6 | **0.64%** | 0.01% | 43.0x |
| 5 | 4.178 .. 27.89 | 939 | 198 | 90 | 1 | **0.11%** | 0.00% | 468.0x |

RAW  top - bottom = **-2.02 pp**   95% CI (close-cluster bootstrap) [-4.18, -0.39] pp   SE 1.005 pp

EXCESS OVER MODEL, top - bottom = **-0.69 pp**   95% CI [-2.85, +0.95] pp   MDE 2.813 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.76, +10.44] pp, null SE 5.417 pp, permutation p = **0.7705**

### `pmod` -- model p(lose) at entry

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 2.813 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 1.473e-05 | 939 | 198 | 90 | 1 | **0.11%** | 0.00% | 468.0x |
| 2 | 1.479e-05 .. 0.0004249 | 939 | 258 | 106 | 6 | **0.64%** | 0.01% | 43.0x |
| 3 | 0.0004257 .. 0.002477 | 940 | 289 | 107 | 14 | **1.49%** | 0.13% | 11.8x |
| 4 | 0.002485 .. 0.008118 | 939 | 280 | 109 | 14 | **1.49%** | 0.49% | 3.1x |
| 5 | 0.008127 .. 0.02 | 939 | 268 | 103 | 20 | **2.13%** | 1.34% | 1.6x |

RAW  top - bottom = **+2.02 pp**   95% CI (close-cluster bootstrap) [+0.40, +4.18] pp   SE 1.005 pp

EXCESS OVER MODEL, top - bottom = **+0.69 pp**   95% CI [-0.94, +2.86] pp   MDE 2.813 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.44, +10.76] pp, null SE 5.417 pp, permutation p = **0.7705**

### `tau` -- seconds to close at entry

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.059 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 3 .. 26 | 936 | 143 | 80 | 0 | **0.00%** | 0.28% | 0.0x |
| 2 | 27 .. 38 | 908 | 162 | 82 | 3 | **0.33%** | 0.42% | 0.8x |
| 3 | 39 .. 46 | 862 | 170 | 89 | 12 | **1.39%** | 0.40% | 3.5x |
| 4 | 47 .. 54 | 1,040 | 207 | 100 | 11 | **1.06%** | 0.45% | 2.4x |
| 5 | 55 .. 60 | 950 | 234 | 105 | 29 | **3.05%** | 0.42% | 7.3x |

RAW  top - bottom = **+3.05 pp**   95% CI (close-cluster bootstrap) [+0.62, +6.24] pp   SE 1.450 pp

EXCESS OVER MODEL, top - bottom = **+2.91 pp**   95% CI [+0.45, +6.10] pp   MDE 4.058 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.79, +11.76] pp, null SE 6.122 pp, permutation p = **0.5928**

### `price` -- price paid, dollars

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 3.105 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.54 .. 0.951 | 921 | 178 | 87 | 22 | **2.39%** | 0.73% | 3.3x |
| 2 | 0.952 .. 0.969 | 848 | 225 | 93 | 15 | **1.77%** | 0.43% | 4.1x |
| 3 | 0.97 .. 0.978 | 923 | 281 | 108 | 13 | **1.41%** | 0.36% | 3.9x |
| 4 | 0.979 .. 0.983 | 995 | 306 | 113 | 2 | **0.20%** | 0.28% | 0.7x |
| 5 | 0.984 .. 0.987 | 1,009 | 352 | 114 | 3 | **0.30%** | 0.19% | 1.6x |

RAW  top - bottom = **-2.09 pp**   95% CI (close-cluster bootstrap) [-4.46, -0.11] pp   SE 1.109 pp

EXCESS OVER MODEL, top - bottom = **-1.55 pp**   95% CI [-3.89, +0.42] pp   MDE 3.094 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.64, +11.28] pp, null SE 5.600 pp, permutation p = **0.7166**

### `spread` -- bid-ask spread at entry

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 3.620 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.001 .. 0.001 | 756 | 211 | 96 | 19 | **2.51%** | 0.30% | 8.3x |
| 2 | 0.002 .. 0.007 | 1,062 | 292 | 106 | 8 | **0.75%** | 0.33% | 2.3x |
| 3 | 0.008 .. 0.019 | 990 | 278 | 102 | 15 | **1.52%** | 0.39% | 3.9x |
| 4 | 0.02 .. 0.037 | 924 | 235 | 104 | 8 | **0.87%** | 0.42% | 2.0x |
| 5 | 0.038 .. 0.44 | 964 | 181 | 99 | 5 | **0.52%** | 0.51% | 1.0x |

RAW  top - bottom = **-1.99 pp**   95% CI (close-cluster bootstrap) [-4.67, +0.26] pp   SE 1.293 pp

EXCESS OVER MODEL, top - bottom = **-2.20 pp**   95% CI [-4.87, +0.03] pp   MDE 3.614 pp

SHUFFLED-LABEL CONTROL: null 95% range [-12.25, +12.26] pp, null SE 6.210 pp, permutation p = **0.7246**

### `size` -- contracts resting at the touch

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 2.236 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 .. 9.97 | 871 | 302 | 111 | 10 | **1.15%** | 0.39% | 2.9x |
| 2 | 10 .. 24.92 | 998 | 314 | 109 | 10 | **1.00%** | 0.37% | 2.7x |
| 3 | 25 .. 63 | 948 | 308 | 115 | 12 | **1.27%** | 0.44% | 2.9x |
| 4 | 63.36 .. 181.7 | 940 | 295 | 109 | 7 | **0.74%** | 0.42% | 1.8x |
| 5 | 182 .. 1.858e+04 | 939 | 222 | 101 | 16 | **1.70%** | 0.35% | 4.9x |

RAW  top - bottom = **+0.56 pp**   95% CI (close-cluster bootstrap) [-0.68, +2.45] pp   SE 0.799 pp

EXCESS OVER MODEL, top - bottom = **+0.60 pp**   95% CI [-0.62, +2.49] pp   MDE 2.216 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.08, +10.36] pp, null SE 4.883 pp, permutation p = **0.9281**

### `age_ms` -- age of the resting level, ms

rows 4,696   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.075 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 126 | 938 | 300 | 109 | 7 | **0.75%** | 0.36% | 2.1x |
| 2 | 127 .. 401 | 939 | 326 | 109 | 5 | **0.53%** | 0.40% | 1.3x |
| 3 | 402 .. 923 | 938 | 332 | 114 | 5 | **0.53%** | 0.39% | 1.4x |
| 4 | 924 .. 4761 | 942 | 296 | 113 | 10 | **1.06%** | 0.38% | 2.8x |
| 5 | 4764 .. 8.653e+05 | 939 | 274 | 107 | 28 | **2.98%** | 0.44% | 6.7x |

RAW  top - bottom = **+2.24 pp**   95% CI (close-cluster bootstrap) [-0.24, +5.33] pp   SE 1.455 pp

EXCESS OVER MODEL, top - bottom = **+2.15 pp**   95% CI [-0.33, +5.24] pp   MDE 4.079 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.05, +7.41] pp, null SE 4.041 pp, permutation p = **0.5130**

### control: coin

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| KXZEC15M | 397 | 44 | 16 | 4.03% |
| KXNEAR15M | 386 | 37 | 8 | 2.07% |
| KXETH15M | 641 | 55 | 12 | 1.87% |
| KXHYPE15M | 553 | 46 | 8 | 1.45% |
| KXXRP15M | 886 | 63 | 7 | 0.79% |
| KXBNB15M | 233 | 29 | 1 | 0.43% |
| KXBTC15M | 810 | 68 | 2 | 0.25% |
| KXDOGE15M | 468 | 49 | 1 | 0.21% |
| KXSOL15M | 322 | 47 | 0 | 0.00% |

### control: hour of day (UTC)

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| 11 | 130 | 3 | 11 | 8.46% |
| 14 | 113 | 5 | 9 | 7.96% |
| 19 | 127 | 5 | 7 | 5.51% |
| 15 | 232 | 5 | 10 | 4.31% |
| 3 | 266 | 5 | 8 | 3.01% |
| 16 | 166 | 5 | 4 | 2.41% |
| 12 | 138 | 4 | 2 | 1.45% |
| 1 | 244 | 5 | 2 | 0.82% |
| 22 | 357 | 6 | 2 | 0.56% |
| 13 | 173 | 6 | 0 | 0.00% |
| 17 | 176 | 6 | 0 | 0.00% |
| 18 | 178 | 5 | 0 | 0.00% |
| 20 | 271 | 6 | 0 | 0.00% |
| 21 | 206 | 6 | 0 | 0.00% |
| 23 | 212 | 5 | 0 | 0.00% |
| 0 | 216 | 6 | 0 | 0.00% |
| 2 | 268 | 5 | 0 | 0.00% |
| 4 | 130 | 5 | 0 | 0.00% |
| 5 | 350 | 5 | 0 | 0.00% |
| 6 | 225 | 6 | 0 | 0.00% |
| 7 | 199 | 4 | 0 | 0.00% |
| 8 | 152 | 4 | 0 | 0.00% |
| 9 | 42 | 3 | 0 | 0.00% |
| 10 | 125 | 3 | 0 | 0.00% |

---

## Population P1M -- one TRADE per market (earliest qualifying second), WIDE


### `flat10` -- frac of last 10s prints exactly equal to the previous

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.251 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.1 | 594 | 594 | 131 | 38 | **6.40%** | 4.76% | 1.3x |
| 2 | 0.2 .. 0.3 | 193 | 193 | 109 | 13 | **6.74%** | 3.44% | 2.0x |
| 3 | 0.4 .. 1 | 227 | 227 | 122 | 22 | **9.69%** | 4.98% | 1.9x |

RAW  top - bottom = **+3.29 pp**   95% CI (close-cluster bootstrap) [-1.55, +8.53] pp   SE 2.590 pp

EXCESS OVER MODEL, top - bottom = **+3.08 pp**   95% CI [-1.04, +7.68] pp   MDE 6.146 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.54, +7.11] pp, null SE 3.845 pp, permutation p = **0.3393**

### `flat30` -- frac of last 30s prints exactly equal

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.230 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.03333 | 376 | 376 | 129 | 31 | **8.24%** | 4.58% | 1.8x |
| 2 | 0.06667 .. 0.1333 | 207 | 207 | 111 | 8 | **3.86%** | 4.31% | 0.9x |
| 3 | 0.1667 .. 0.3333 | 220 | 220 | 112 | 13 | **5.91%** | 4.40% | 1.3x |
| 4 | 0.3667 .. 1 | 211 | 211 | 126 | 21 | **9.95%** | 4.93% | 2.0x |

RAW  top - bottom = **+1.71 pp**   95% CI (close-cluster bootstrap) [-3.60, +7.78] pp   SE 2.939 pp

EXCESS OVER MODEL, top - bottom = **+1.36 pp**   95% CI [-3.16, +6.55] pp   MDE 7.086 pp

SHUFFLED-LABEL CONTROL: null 95% range [-7.84, +8.47] pp, null SE 4.335 pp, permutation p = **0.6727**

### `flat60` -- frac of last 60s prints exactly equal

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 9.268 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0 | 198 | 198 | 117 | 21 | **10.61%** | 5.65% | 1.9x |
| 2 | 0.01667 .. 0.05 | 180 | 180 | 105 | 10 | **5.56%** | 3.29% | 1.7x |
| 3 | 0.06667 .. 0.15 | 225 | 225 | 114 | 10 | **4.44%** | 4.73% | 0.9x |
| 4 | 0.1667 .. 0.3167 | 203 | 203 | 110 | 10 | **4.93%** | 3.98% | 1.2x |
| 5 | 0.3333 .. 0.9833 | 208 | 208 | 124 | 22 | **10.58%** | 5.01% | 2.1x |

RAW  top - bottom = **-0.03 pp**   95% CI (close-cluster bootstrap) [-6.09, +6.40] pp   SE 3.310 pp

EXCESS OVER MODEL, top - bottom = **+0.61 pp**   95% CI [-4.51, +6.09] pp   MDE 7.680 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.30, +9.88] pp, null SE 4.977 pp, permutation p = **0.9721**

### `flat300` -- frac of last 300s prints exactly equal

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.482 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.006667 | 192 | 192 | 121 | 20 | **10.42%** | 5.78% | 1.8x |
| 2 | 0.01 .. 0.07 | 206 | 206 | 117 | 12 | **5.83%** | 3.79% | 1.5x |
| 3 | 0.07333 .. 0.16 | 209 | 209 | 112 | 6 | **2.87%** | 3.82% | 0.8x |
| 4 | 0.1633 .. 0.3367 | 204 | 204 | 105 | 17 | **8.33%** | 4.26% | 2.0x |
| 5 | 0.34 .. 0.9467 | 203 | 203 | 126 | 18 | **8.87%** | 5.25% | 1.7x |

RAW  top - bottom = **-1.55 pp**   95% CI (close-cluster bootstrap) [-7.23, +4.37] pp   SE 3.029 pp

EXCESS OVER MODEL, top - bottom = **-1.02 pp**   95% CI [-5.90, +4.06] pp   MDE 7.093 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.35, +10.41] pp, null SE 5.009 pp, permutation p = **0.7345**

### `s30_s300` -- sigma_30 / sigma_300  (low = unusually quiet right now)

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.119 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.5064 | 203 | 203 | 86 | 17 | **8.37%** | 3.69% | 2.3x |
| 2 | 0.5073 .. 0.7053 | 203 | 203 | 99 | 13 | **6.40%** | 4.54% | 1.4x |
| 3 | 0.7054 .. 0.8875 | 202 | 202 | 96 | 14 | **6.93%** | 3.85% | 1.8x |
| 4 | 0.8883 .. 1.151 | 203 | 203 | 98 | 10 | **4.93%** | 4.21% | 1.2x |
| 5 | 1.153 .. 3.024 | 203 | 203 | 88 | 19 | **9.36%** | 6.50% | 1.4x |

RAW  top - bottom = **+0.99 pp**   95% CI (close-cluster bootstrap) [-4.61, +6.45] pp   SE 2.900 pp

EXCESS OVER MODEL, top - bottom = **-1.83 pp**   95% CI [-7.15, +2.91] pp   MDE 7.244 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.85, +9.36] pp, null SE 4.828 pp, permutation p = **0.7864**

### `s300_s900` -- sigma_300 / sigma_900 (low = quiet vs the last 15 min)

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.803 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.3041 .. 0.7824 | 203 | 203 | 78 | 12 | **5.91%** | 2.03% | 2.9x |
| 2 | 0.7828 .. 0.9054 | 203 | 203 | 94 | 13 | **6.40%** | 3.95% | 1.6x |
| 3 | 0.9056 .. 1.014 | 202 | 202 | 98 | 12 | **5.94%** | 4.21% | 1.4x |
| 4 | 1.014 .. 1.148 | 203 | 203 | 95 | 16 | **7.88%** | 5.67% | 1.4x |
| 5 | 1.149 .. 1.693 | 203 | 203 | 82 | 20 | **9.85%** | 6.94% | 1.4x |

RAW  top - bottom = **+3.94 pp**   95% CI (close-cluster bootstrap) [-2.64, +9.70] pp   SE 3.144 pp

EXCESS OVER MODEL, top - bottom = **-0.97 pp**   95% CI [-6.99, +3.85] pp   MDE 7.768 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.84, +8.37] pp, null SE 4.701 pp, permutation p = **0.3074**

### `s300_s3600` -- sigma_300 / sigma_3600 (low = quiet vs the hour)

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.727 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2056 .. 0.6611 | 203 | 203 | 78 | 12 | **5.91%** | 2.95% | 2.0x |
| 2 | 0.6623 .. 0.8057 | 203 | 203 | 94 | 21 | **10.34%** | 4.24% | 2.4x |
| 3 | 0.8071 .. 0.9599 | 202 | 202 | 99 | 13 | **6.44%** | 4.37% | 1.5x |
| 4 | 0.9601 .. 1.18 | 203 | 203 | 92 | 16 | **7.88%** | 5.84% | 1.3x |
| 5 | 1.18 .. 2.919 | 203 | 203 | 78 | 11 | **5.42%** | 5.39% | 1.0x |

RAW  top - bottom = **-0.49 pp**   95% CI (close-cluster bootstrap) [-5.23, +3.99] pp   SE 2.402 pp

EXCESS OVER MODEL, top - bottom = **-2.93 pp**   95% CI [-7.27, +1.34] pp   MDE 6.286 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.34, +7.88] pp, null SE 4.761 pp, permutation p = **0.9481**

### `s300_sday` -- sigma_300 / sigma_86400 (low = quiet vs the day)

rows 992   closes 129   **loss-carrying closes 52**   losing markets 72   dropped (feature unavailable) 22

**MDE (stated before the estimate): 9.368 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.09508 .. 0.4103 | 198 | 198 | 64 | 23 | **11.62%** | 4.59% | 2.5x |
| 2 | 0.4116 .. 0.5662 | 199 | 199 | 91 | 15 | **7.54%** | 4.91% | 1.5x |
| 3 | 0.5663 .. 0.7707 | 198 | 198 | 96 | 13 | **6.57%** | 3.77% | 1.7x |
| 4 | 0.771 .. 1.091 | 199 | 199 | 89 | 11 | **5.53%** | 4.93% | 1.1x |
| 5 | 1.092 .. 4.398 | 198 | 198 | 74 | 10 | **5.05%** | 4.61% | 1.1x |

RAW  top - bottom = **-6.57 pp**   95% CI (close-cluster bootstrap) [-13.79, -0.60] pp   SE 3.346 pp

EXCESS OVER MODEL, top - bottom = **-6.59 pp**   95% CI [-13.53, -1.23] pp   MDE 8.681 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.61, +11.11] pp, null SE 5.289 pp, permutation p = **0.1697**

### `mx10_sig` -- largest 1s move in last 10s, in sigma_300

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.550 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.6855 | 203 | 203 | 87 | 12 | **5.91%** | 3.07% | 1.9x |
| 2 | 0.6862 .. 1.14 | 203 | 203 | 100 | 19 | **9.36%** | 4.61% | 2.0x |
| 3 | 1.141 .. 1.745 | 202 | 202 | 109 | 8 | **3.96%** | 3.65% | 1.1x |
| 4 | 1.748 .. 2.627 | 203 | 203 | 100 | 14 | **6.90%** | 4.55% | 1.5x |
| 5 | 2.642 .. 13.99 | 203 | 203 | 94 | 20 | **9.85%** | 6.92% | 1.4x |

RAW  top - bottom = **+3.94 pp**   95% CI (close-cluster bootstrap) [-2.39, +9.34] pp   SE 3.053 pp

EXCESS OVER MODEL, top - bottom = **+0.10 pp**   95% CI [-5.77, +4.64] pp   MDE 7.609 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.36, +10.34] pp, null SE 4.952 pp, permutation p = **0.4830**

### `mx30_sig` -- largest 1s move in last 30s, in sigma_300

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.346 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 1.574 | 203 | 203 | 89 | 15 | **7.39%** | 2.99% | 2.5x |
| 2 | 1.577 .. 2.19 | 203 | 203 | 105 | 12 | **5.91%** | 4.44% | 1.3x |
| 3 | 2.191 .. 3.003 | 202 | 202 | 105 | 13 | **6.44%** | 4.16% | 1.5x |
| 4 | 3.004 .. 4.28 | 203 | 203 | 103 | 15 | **7.39%** | 4.56% | 1.6x |
| 5 | 4.281 .. 16.54 | 203 | 203 | 90 | 18 | **8.87%** | 6.65% | 1.3x |

RAW  top - bottom = **+1.48 pp**   95% CI (close-cluster bootstrap) [-4.56, +6.83] pp   SE 2.981 pp

EXCESS OVER MODEL, top - bottom = **-2.19 pp**   95% CI [-7.88, +2.63] pp   MDE 7.683 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.85, +9.36] pp, null SE 4.910 pp, permutation p = **0.7585**

### `mx60_sig` -- largest 1s move in last 60s, in sigma_300

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.109 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.5161 .. 2.406 | 203 | 203 | 90 | 7 | **3.45%** | 3.33% | 1.0x |
| 2 | 2.407 .. 3.282 | 203 | 203 | 98 | 16 | **7.88%** | 3.74% | 2.1x |
| 3 | 3.285 .. 4.234 | 202 | 202 | 98 | 13 | **6.44%** | 3.92% | 1.6x |
| 4 | 4.238 .. 6.061 | 203 | 203 | 100 | 16 | **7.88%** | 4.79% | 1.6x |
| 5 | 6.084 .. 16.54 | 203 | 203 | 90 | 21 | **10.34%** | 7.01% | 1.5x |

RAW  top - bottom = **+6.90 pp**   95% CI (close-cluster bootstrap) [+2.08, +11.81] pp   SE 2.539 pp

EXCESS OVER MODEL, top - bottom = **+3.22 pp**   95% CI [-0.87, +7.31] pp   MDE 5.866 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.85, +8.87] pp, null SE 4.877 pp, permutation p = **0.1138**

### `req_rng30` -- |required move| / index range over last 30s

rows 1,013   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 1

**MDE (stated before the estimate): 10.287 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.002844 .. 1.217 | 203 | 203 | 92 | 56 | **27.59%** | 19.11% | 1.4x |
| 2 | 1.224 .. 2.627 | 202 | 202 | 98 | 4 | **1.98%** | 2.71% | 0.7x |
| 3 | 2.632 .. 4.714 | 203 | 203 | 103 | 7 | **3.45%** | 0.74% | 4.6x |
| 4 | 4.742 .. 8.364 | 202 | 202 | 105 | 2 | **0.99%** | 0.21% | 4.6x |
| 5 | 8.429 .. 58.16 | 203 | 203 | 92 | 4 | **1.97%** | 0.01% | 139.2x |

RAW  top - bottom = **-25.62 pp**   95% CI (close-cluster bootstrap) [-32.51, -18.14] pp   SE 3.674 pp

EXCESS OVER MODEL, top - bottom = **-6.52 pp**   95% CI [-12.73, +0.54] pp   MDE 9.395 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.84, +8.37] pp, null SE 4.942 pp, permutation p = **0.0020**

### `req_rng60` -- |required move| / index range over last 60s

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 9.286 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.002844 .. 0.6934 | 203 | 203 | 95 | 56 | **27.59%** | 19.62% | 1.4x |
| 2 | 0.6949 .. 1.678 | 203 | 203 | 98 | 7 | **3.45%** | 2.48% | 1.4x |
| 3 | 1.683 .. 2.669 | 202 | 202 | 99 | 2 | **0.99%** | 0.51% | 2.0x |
| 4 | 2.696 .. 4.889 | 203 | 203 | 101 | 6 | **2.96%** | 0.16% | 18.5x |
| 5 | 4.916 .. 27.37 | 203 | 203 | 94 | 2 | **0.99%** | 0.01% | 92.1x |

RAW  top - bottom = **-26.60 pp**   95% CI (close-cluster bootstrap) [-33.17, -20.15] pp   SE 3.317 pp

EXCESS OVER MODEL, top - bottom = **-6.99 pp**   95% CI [-12.81, -1.41] pp   MDE 7.922 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.34, +8.87] pp, null SE 4.972 pp, permutation p = **0.0020**

### `req_rng300` -- |required move| / index range over last 300s

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.601 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.001027 .. 0.3078 | 203 | 203 | 98 | 58 | **28.57%** | 20.83% | 1.4x |
| 2 | 0.3083 .. 0.5801 | 203 | 203 | 93 | 7 | **3.45%** | 1.79% | 1.9x |
| 3 | 0.5805 .. 0.8791 | 202 | 202 | 103 | 3 | **1.49%** | 0.15% | 10.1x |
| 4 | 0.8795 .. 1.415 | 203 | 203 | 105 | 5 | **2.46%** | 0.00% | 651.1x |
| 5 | 1.418 .. 8.647 | 203 | 203 | 90 | 0 | **0.00%** | 0.00% | 0.0x |

RAW  top - bottom = **-28.57 pp**   95% CI (close-cluster bootstrap) [-34.83, -22.97] pp   SE 3.072 pp

EXCESS OVER MODEL, top - bottom = **-7.74 pp**   95% CI [-13.58, -2.33] pp   MDE 7.955 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.85, +9.36] pp, null SE 4.943 pp, permutation p = **0.0020**

### `gap` -- market implied p(lose) minus model p(lose)

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 9.819 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.1935 .. 0.001 | 203 | 203 | 101 | 25 | **12.32%** | 10.65% | 1.2x |
| 2 | 0.001 .. 0.002 | 203 | 203 | 108 | 3 | **1.48%** | 0.19% | 7.8x |
| 3 | 0.002 .. 0.006 | 201 | 201 | 102 | 1 | **0.50%** | 0.64% | 0.8x |
| 4 | 0.006 .. 0.01947 | 204 | 204 | 101 | 6 | **2.94%** | 1.66% | 1.8x |
| 5 | 0.01962 .. 0.2809 | 203 | 203 | 97 | 38 | **18.72%** | 9.64% | 1.9x |

RAW  top - bottom = **+6.40 pp**   95% CI (close-cluster bootstrap) [-0.47, +13.45] pp   SE 3.507 pp

EXCESS OVER MODEL, top - bottom = **+7.41 pp**   95% CI [+1.61, +13.25] pp   MDE 8.431 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.87, +10.34] pp, null SE 4.851 pp, permutation p = **0.1976**

### `lgap` -- log( market implied p(lose) / model p(lose) )

rows 776   closes 129   **loss-carrying closes 53**   losing markets 72   dropped (feature unavailable) 238

**MDE (stated before the estimate): 9.528 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -3.017 .. 0.1268 | 155 | 155 | 84 | 32 | **20.65%** | 19.37% | 1.1x |
| 2 | 0.1268 .. 1.567 | 155 | 155 | 90 | 29 | **18.71%** | 10.21% | 1.8x |
| 3 | 1.608 .. 4.345 | 156 | 156 | 87 | 6 | **3.85%** | 0.24% | 15.9x |
| 4 | 4.356 .. 10.09 | 155 | 155 | 86 | 2 | **1.29%** | 0.01% | 254.6x |
| 5 | 10.11 .. 21.84 | 155 | 155 | 96 | 3 | **1.94%** | 0.00% | 586531.8x |

RAW  top - bottom = **-18.71 pp**   95% CI (close-cluster bootstrap) [-25.34, -11.77] pp   SE 3.403 pp

EXCESS OVER MODEL, top - bottom = **+0.66 pp**   95% CI [-5.68, +7.56] pp   MDE 9.173 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.97, +10.32] pp, null SE 5.511 pp, permutation p = **0.0040**

### `z` -- |required move| in model sd (higher should be safer)

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.122 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.005882 .. 1.665 | 203 | 203 | 97 | 57 | **28.08%** | 21.62% | 1.3x |
| 2 | 1.666 .. 3.279 | 203 | 203 | 100 | 10 | **4.93%** | 1.15% | 4.3x |
| 3 | 3.284 .. 4.962 | 202 | 202 | 101 | 2 | **0.99%** | 0.01% | 116.6x |
| 4 | 4.972 .. 7.697 | 203 | 203 | 108 | 4 | **1.97%** | 0.00% | 635917.6x |
| 5 | 7.705 .. 45.19 | 203 | 203 | 93 | 0 | **0.00%** | 0.00% | 0.0x |

RAW  top - bottom = **-28.08 pp**   95% CI (close-cluster bootstrap) [-33.87, -22.64] pp   SE 2.901 pp

EXCESS OVER MODEL, top - bottom = **-6.46 pp**   95% CI [-11.89, -1.31] pp   MDE 7.564 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.36, +9.36] pp, null SE 4.946 pp, permutation p = **0.0020**

### `pmod` -- model p(lose) at entry

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.122 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 6.544e-15 | 203 | 203 | 93 | 0 | **0.00%** | 0.00% | 0.0x |
| 2 | 6.883e-15 .. 3.31e-07 | 203 | 203 | 108 | 4 | **1.97%** | 0.00% | 635917.6x |
| 3 | 3.493e-07 .. 0.0005111 | 202 | 202 | 101 | 2 | **0.99%** | 0.01% | 116.6x |
| 4 | 0.0005211 .. 0.0479 | 203 | 203 | 100 | 10 | **4.93%** | 1.15% | 4.3x |
| 5 | 0.04791 .. 0.4977 | 203 | 203 | 97 | 57 | **28.08%** | 21.62% | 1.3x |

RAW  top - bottom = **+28.08 pp**   95% CI (close-cluster bootstrap) [+22.65, +33.91] pp   SE 2.901 pp

EXCESS OVER MODEL, top - bottom = **+6.46 pp**   95% CI [+1.38, +11.90] pp   MDE 7.564 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.36, +9.36] pp, null SE 4.946 pp, permutation p = **0.0020**

### `tau` -- seconds to close at entry

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 7.345 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 15 .. 59 | 74 | 74 | 58 | 3 | **4.05%** | 3.56% | 1.1x |
| 2 | 60 .. 60 | 940 | 940 | 131 | 70 | **7.45%** | 4.64% | 1.6x |

RAW  top - bottom = **+3.39 pp**   95% CI (close-cluster bootstrap) [-2.26, +8.00] pp   SE 2.623 pp

EXCESS OVER MODEL, top - bottom = **+2.32 pp**   95% CI [-2.35, +6.39] pp   MDE 6.258 pp

SHUFFLED-LABEL CONTROL: null 95% range [-11.27, +12.84] pp, null SE 6.070 pp, permutation p = **0.5749**

### `price` -- price paid, dollars

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 9.427 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.51 .. 0.935 | 200 | 200 | 96 | 59 | **29.50%** | 20.65% | 1.4x |
| 2 | 0.938 .. 0.985 | 201 | 201 | 100 | 8 | **3.98%** | 2.22% | 1.8x |
| 3 | 0.986 .. 0.995 | 189 | 189 | 99 | 2 | **1.06%** | 0.18% | 5.8x |
| 4 | 0.996 .. 0.998 | 182 | 182 | 97 | 2 | **1.10%** | 0.07% | 15.0x |
| 5 | 0.999 .. 0.999 | 242 | 242 | 109 | 2 | **0.83%** | 0.00% | 758.4x |

RAW  top - bottom = **-28.67 pp**   95% CI (close-cluster bootstrap) [-35.47, -22.42] pp   SE 3.367 pp

EXCESS OVER MODEL, top - bottom = **-8.02 pp**   95% CI [-14.36, -2.21] pp   MDE 8.614 pp

SHUFFLED-LABEL CONTROL: null 95% range [-9.44, +8.81] pp, null SE 4.777 pp, permutation p = **0.0020**

### `spread` -- bid-ask spread at entry

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 8.129 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.001 .. 0.001 | 350 | 350 | 123 | 5 | **1.43%** | 0.15% | 9.4x |
| 2 | 0.002 .. 0.006 | 254 | 254 | 116 | 5 | **1.97%** | 0.24% | 8.1x |
| 3 | 0.007 .. 0.02 | 207 | 207 | 100 | 28 | **13.53%** | 7.58% | 1.8x |
| 4 | 0.021 .. 0.55 | 203 | 203 | 104 | 35 | **17.24%** | 14.48% | 1.2x |

RAW  top - bottom = **+15.81 pp**   95% CI (close-cluster bootstrap) [+10.05, +21.61] pp   SE 2.903 pp

EXCESS OVER MODEL, top - bottom = **+1.49 pp**   95% CI [-3.57, +6.52] pp   MDE 7.262 pp

SHUFFLED-LABEL CONTROL: null 95% range [-8.78, +9.09] pp, null SE 4.471 pp, permutation p = **0.0020**

### `size` -- contracts resting at the touch

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.063 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 .. 11.04 | 203 | 203 | 101 | 15 | **7.39%** | 3.44% | 2.1x |
| 2 | 11.19 .. 34 | 203 | 203 | 105 | 19 | **9.36%** | 6.40% | 1.5x |
| 3 | 34.25 .. 87.58 | 202 | 202 | 106 | 14 | **6.93%** | 4.49% | 1.5x |
| 4 | 89 .. 249.9 | 202 | 202 | 103 | 15 | **7.43%** | 4.51% | 1.6x |
| 5 | 250 .. 1.538e+04 | 204 | 204 | 112 | 10 | **4.90%** | 3.95% | 1.2x |

RAW  top - bottom = **-2.49 pp**   95% CI (close-cluster bootstrap) [-6.86, +1.76] pp   SE 2.165 pp

EXCESS OVER MODEL, top - bottom = **-3.00 pp**   95% CI [-7.00, +0.77] pp   MDE 5.587 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.56, +9.11] pp, null SE 5.073 pp, permutation p = **0.6507**

### `age_ms` -- age of the resting level, ms

rows 1,014   closes 132   **loss-carrying closes 53**   losing markets 73   dropped (feature unavailable) 0

**MDE (stated before the estimate): 6.235 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 147 | 202 | 202 | 108 | 23 | **11.39%** | 5.19% | 2.2x |
| 2 | 148 .. 815 | 204 | 204 | 101 | 18 | **8.82%** | 7.82% | 1.1x |
| 3 | 820 .. 3360 | 202 | 202 | 108 | 21 | **10.40%** | 5.68% | 1.8x |
| 4 | 3372 .. 2.236e+04 | 203 | 203 | 104 | 9 | **4.43%** | 2.42% | 1.8x |
| 5 | 2.272e+04 .. 8.087e+05 | 203 | 203 | 109 | 2 | **0.99%** | 1.67% | 0.6x |

RAW  top - bottom = **-10.40 pp**   95% CI (close-cluster bootstrap) [-14.88, -6.15] pp   SE 2.227 pp

EXCESS OVER MODEL, top - bottom = **-6.88 pp**   95% CI [-10.46, -3.33] pp   MDE 5.039 pp

SHUFFLED-LABEL CONTROL: null 95% range [-10.62, +9.14] pp, null SE 5.041 pp, permutation p = **0.0579**

### control: coin

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| KXBTC15M | 120 | 120 | 13 | 10.83% |
| KXETH15M | 117 | 117 | 12 | 10.26% |
| KXZEC15M | 104 | 104 | 10 | 9.62% |
| KXDOGE15M | 117 | 117 | 11 | 9.40% |
| KXNEAR15M | 88 | 88 | 6 | 6.82% |
| KXSOL15M | 122 | 122 | 8 | 6.56% |
| KXXRP15M | 127 | 127 | 6 | 4.72% |
| KXHYPE15M | 118 | 118 | 4 | 3.39% |
| KXBNB15M | 101 | 101 | 3 | 2.97% |

### control: hour of day (UTC)

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| 1 | 45 | 6 | 6 | 13.33% |
| 21 | 48 | 6 | 6 | 12.50% |
| 11 | 24 | 3 | 3 | 12.50% |
| 19 | 43 | 6 | 5 | 11.63% |
| 3 | 47 | 6 | 5 | 10.64% |
| 0 | 48 | 6 | 5 | 10.42% |
| 13 | 50 | 6 | 5 | 10.00% |
| 12 | 44 | 6 | 4 | 9.09% |
| 15 | 44 | 6 | 4 | 9.09% |
| 20 | 50 | 6 | 4 | 8.00% |
| 22 | 50 | 6 | 4 | 8.00% |
| 10 | 26 | 3 | 2 | 7.69% |
| 23 | 43 | 6 | 3 | 6.98% |
| 8 | 34 | 4 | 2 | 5.88% |
| 7 | 38 | 5 | 2 | 5.26% |
| 14 | 41 | 6 | 2 | 4.88% |
| 16 | 41 | 6 | 2 | 4.88% |
| 9 | 21 | 3 | 1 | 4.76% |
| 2 | 45 | 6 | 2 | 4.44% |
| 18 | 47 | 6 | 2 | 4.26% |
| 17 | 44 | 6 | 1 | 2.27% |
| 4 | 46 | 6 | 1 | 2.17% |
| 6 | 47 | 6 | 1 | 2.13% |
| 5 | 48 | 6 | 1 | 2.08% |

---

## Population P2M -- one TRADE per market, LIVE RULE's gates


**FEWER THAN 30 LOSS-CARRYING CLOSES (10) -- NO SIGNIFICANCE IS CLAIMED ANYWHERE IN THIS POPULATION.** The intervals are printed so the size of the uncertainty is visible, not so they can be read as findings.


### `flat10` -- frac of last 10s prints exactly equal to the previous

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.076 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.1 | 262 | 262 | 109 | 8 | **3.05%** | 0.91% | 3.4x |
| 2 | 0.2 .. 0.3 | 80 | 80 | 64 | 1 | **1.25%** | 0.94% | 1.3x |
| 3 | 0.4 .. 1 | 96 | 96 | 68 | 3 | **3.12%** | 0.98% | 3.2x |

RAW  top - bottom = **+0.07 pp**   95% CI (close-cluster bootstrap) [-3.96, +4.51] pp   SE 2.170 pp

EXCESS OVER MODEL, top - bottom = **+0.01 pp**   95% CI [-4.03, +4.46] pp   MDE 6.082 pp

SHUFFLED-LABEL CONTROL: null 95% range [-12.40, +12.25] pp, null SE 6.070 pp, permutation p = **0.9741**

### `flat30` -- frac of last 30s prints exactly equal

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.897 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0 | 128 | 128 | 86 | 5 | **3.91%** | 0.84% | 4.6x |
| 2 | 0.03333 .. 0.1333 | 128 | 128 | 83 | 2 | **1.56%** | 1.00% | 1.6x |
| 3 | 0.1667 .. 0.3333 | 93 | 93 | 67 | 1 | **1.08%** | 0.89% | 1.2x |
| 4 | 0.3667 .. 0.9667 | 89 | 89 | 70 | 4 | **4.49%** | 1.00% | 4.5x |

RAW  top - bottom = **+0.59 pp**   95% CI (close-cluster bootstrap) [-4.17, +5.52] pp   SE 2.463 pp

EXCESS OVER MODEL, top - bottom = **+0.43 pp**   95% CI [-4.34, +5.35] pp   MDE 6.899 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.80, +13.75] pp, null SE 7.102 pp, permutation p = **0.9701**

### `flat60` -- frac of last 60s prints exactly equal

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 5.556 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.05 | 170 | 170 | 98 | 6 | **3.53%** | 0.87% | 4.0x |
| 2 | 0.06667 .. 0.15 | 84 | 84 | 63 | 1 | **1.19%** | 1.00% | 1.2x |
| 3 | 0.1667 .. 0.3167 | 91 | 91 | 66 | 2 | **2.20%** | 0.85% | 2.6x |
| 4 | 0.3333 .. 0.9833 | 93 | 93 | 70 | 3 | **3.23%** | 1.04% | 3.1x |

RAW  top - bottom = **-0.30 pp**   95% CI (close-cluster bootstrap) [-4.02, +3.57] pp   SE 1.984 pp

EXCESS OVER MODEL, top - bottom = **-0.47 pp**   95% CI [-4.24, +3.44] pp   MDE 5.568 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.36, +13.26] pp, null SE 6.692 pp, permutation p = **0.9461**

### `flat300` -- frac of last 300s prints exactly equal

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.553 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.003333 | 69 | 69 | 61 | 2 | **2.90%** | 0.90% | 3.2x |
| 2 | 0.006667 .. 0.06667 | 105 | 105 | 75 | 3 | **2.86%** | 0.81% | 3.5x |
| 3 | 0.07 .. 0.1767 | 84 | 84 | 63 | 2 | **2.38%** | 1.09% | 2.2x |
| 4 | 0.18 .. 0.3233 | 90 | 90 | 64 | 4 | **4.44%** | 0.79% | 5.7x |
| 5 | 0.3267 .. 0.9367 | 90 | 90 | 67 | 1 | **1.11%** | 1.08% | 1.0x |

RAW  top - bottom = **-1.79 pp**   95% CI (close-cluster bootstrap) [-6.94, +2.27] pp   SE 2.340 pp

EXCESS OVER MODEL, top - bottom = **-1.96 pp**   95% CI [-7.13, +2.13] pp   MDE 6.573 pp

SHUFFLED-LABEL CONTROL: null 95% range [-16.86, +15.65] pp, null SE 8.354 pp, permutation p = **0.7864**

### `s30_s300` -- sigma_30 / sigma_300  (low = unusually quiet right now)

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.611 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.1135 .. 0.5679 | 88 | 88 | 56 | 4 | **4.55%** | 0.93% | 4.9x |
| 2 | 0.5681 .. 0.7814 | 87 | 87 | 68 | 1 | **1.15%** | 0.99% | 1.2x |
| 3 | 0.784 .. 1.006 | 88 | 88 | 61 | 1 | **1.14%** | 0.91% | 1.2x |
| 4 | 1.008 .. 1.304 | 87 | 87 | 61 | 4 | **4.60%** | 0.88% | 5.2x |
| 5 | 1.309 .. 3.024 | 88 | 88 | 51 | 2 | **2.27%** | 0.94% | 2.4x |

RAW  top - bottom = **-2.27 pp**   95% CI (close-cluster bootstrap) [-7.23, +2.25] pp   SE 2.361 pp

EXCESS OVER MODEL, top - bottom = **-2.27 pp**   95% CI [-7.22, +2.24] pp   MDE 6.600 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.91, +14.77] pp, null SE 7.853 pp, permutation p = **0.7864**

### `s300_s900` -- sigma_300 / sigma_900 (low = quiet vs the last 15 min)

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 5.835 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.397 .. 0.8126 | 88 | 88 | 51 | 2 | **2.27%** | 0.70% | 3.2x |
| 2 | 0.8135 .. 0.9285 | 87 | 87 | 59 | 3 | **3.45%** | 0.94% | 3.7x |
| 3 | 0.9316 .. 1.046 | 88 | 88 | 61 | 3 | **3.41%** | 0.92% | 3.7x |
| 4 | 1.048 .. 1.177 | 87 | 87 | 63 | 3 | **3.45%** | 1.09% | 3.2x |
| 5 | 1.178 .. 1.635 | 88 | 88 | 46 | 1 | **1.14%** | 1.00% | 1.1x |

RAW  top - bottom = **-1.14 pp**   95% CI (close-cluster bootstrap) [-5.46, +2.95] pp   SE 2.084 pp

EXCESS OVER MODEL, top - bottom = **-1.44 pp**   95% CI [-5.73, +2.61] pp   MDE 5.860 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.64, +15.91] pp, null SE 7.328 pp, permutation p = **0.8204**

### `s300_s3600` -- sigma_300 / sigma_3600 (low = quiet vs the hour)

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 8.333 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2056 .. 0.6663 | 88 | 88 | 53 | 4 | **4.55%** | 0.78% | 5.8x |
| 2 | 0.6669 .. 0.8112 | 87 | 87 | 56 | 2 | **2.30%** | 0.72% | 3.2x |
| 3 | 0.8126 .. 0.9619 | 88 | 88 | 60 | 3 | **3.41%** | 0.97% | 3.5x |
| 4 | 0.9659 .. 1.18 | 87 | 87 | 59 | 0 | **0.00%** | 1.01% | 0.0x |
| 5 | 1.18 .. 2.346 | 88 | 88 | 47 | 3 | **3.41%** | 1.16% | 2.9x |

RAW  top - bottom = **-1.14 pp**   95% CI (close-cluster bootstrap) [-7.56, +4.21] pp   SE 2.976 pp

EXCESS OVER MODEL, top - bottom = **-1.52 pp**   95% CI [-7.93, +3.86] pp   MDE 8.410 pp

SHUFFLED-LABEL CONTROL: null 95% range [-14.77, +14.77] pp, null SE 7.424 pp, permutation p = **0.8503**

### `s300_sday` -- sigma_300 / sigma_86400 (low = quiet vs the day)

rows 429   closes 116   **loss-carrying closes 9**   losing markets 11   dropped (feature unavailable) 9

**BELOW THE 30-CLUSTER FLOOR (9 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 7.034 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.1234 .. 0.3935 | 86 | 86 | 40 | 1 | **1.16%** | 0.76% | 1.5x |
| 2 | 0.3938 .. 0.5238 | 86 | 86 | 54 | 4 | **4.65%** | 0.90% | 5.2x |
| 3 | 0.5248 .. 0.7176 | 85 | 85 | 58 | 3 | **3.53%** | 0.92% | 3.8x |
| 4 | 0.7186 .. 0.9913 | 86 | 86 | 56 | 0 | **0.00%** | 0.94% | 0.0x |
| 5 | 0.9931 .. 2.631 | 86 | 86 | 47 | 3 | **3.49%** | 1.11% | 3.1x |

RAW  top - bottom = **+2.33 pp**   95% CI (close-cluster bootstrap) [-2.28, +8.00] pp   SE 2.512 pp

EXCESS OVER MODEL, top - bottom = **+1.97 pp**   95% CI [-2.68, +7.60] pp   MDE 7.064 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.12, +15.12] pp, null SE 7.664 pp, permutation p = **0.7325**

### `mx10_sig` -- largest 1s move in last 10s, in sigma_300

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 7.086 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.7747 | 88 | 88 | 61 | 2 | **2.27%** | 0.95% | 2.4x |
| 2 | 0.7855 .. 1.284 | 87 | 87 | 63 | 4 | **4.60%** | 0.92% | 5.0x |
| 3 | 1.311 .. 2.046 | 88 | 88 | 62 | 0 | **0.00%** | 0.91% | 0.0x |
| 4 | 2.054 .. 3.449 | 87 | 87 | 62 | 3 | **3.45%** | 0.98% | 3.5x |
| 5 | 3.468 .. 16.15 | 88 | 88 | 55 | 3 | **3.41%** | 0.90% | 3.8x |

RAW  top - bottom = **+1.14 pp**   95% CI (close-cluster bootstrap) [-3.66, +6.24] pp   SE 2.531 pp

EXCESS OVER MODEL, top - bottom = **+1.18 pp**   95% CI [-3.67, +6.22] pp   MDE 7.106 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.91, +15.91] pp, null SE 7.861 pp, permutation p = **0.9042**

### `mx30_sig` -- largest 1s move in last 30s, in sigma_300

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 8.354 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.4137 .. 1.771 | 88 | 88 | 55 | 3 | **3.41%** | 0.99% | 3.4x |
| 2 | 1.784 .. 2.473 | 87 | 87 | 64 | 2 | **2.30%** | 0.98% | 2.3x |
| 3 | 2.496 .. 3.47 | 88 | 88 | 68 | 1 | **1.14%** | 0.87% | 1.3x |
| 4 | 3.497 .. 4.924 | 87 | 87 | 61 | 2 | **2.30%** | 0.98% | 2.4x |
| 5 | 4.937 .. 16.52 | 88 | 88 | 52 | 4 | **4.55%** | 0.83% | 5.5x |

RAW  top - bottom = **+1.14 pp**   95% CI (close-cluster bootstrap) [-4.92, +7.06] pp   SE 2.984 pp

EXCESS OVER MODEL, top - bottom = **+1.30 pp**   95% CI [-4.62, +7.16] pp   MDE 8.326 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.91, +13.64] pp, null SE 7.676 pp, permutation p = **0.8164**

### `mx60_sig` -- largest 1s move in last 60s, in sigma_300

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.172 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.697 .. 2.496 | 88 | 88 | 58 | 3 | **3.41%** | 1.03% | 3.3x |
| 2 | 2.507 .. 3.47 | 87 | 87 | 62 | 2 | **2.30%** | 0.92% | 2.5x |
| 3 | 3.505 .. 4.656 | 88 | 88 | 60 | 2 | **2.27%** | 1.00% | 2.3x |
| 4 | 4.659 .. 6.456 | 87 | 87 | 57 | 4 | **4.60%** | 0.85% | 5.4x |
| 5 | 6.474 .. 16.52 | 88 | 88 | 56 | 1 | **1.14%** | 0.85% | 1.3x |

RAW  top - bottom = **-2.27 pp**   95% CI (close-cluster bootstrap) [-6.64, +2.04] pp   SE 2.204 pp

EXCESS OVER MODEL, top - bottom = **-2.09 pp**   95% CI [-6.47, +2.23] pp   MDE 6.175 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.91, +13.64] pp, null SE 7.547 pp, permutation p = **0.8403**

### `req_rng30` -- |required move| / index range over last 30s

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 7.727 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.3287 .. 0.8761 | 88 | 88 | 56 | 1 | **1.14%** | 1.16% | 1.0x |
| 2 | 0.8804 .. 1.366 | 87 | 87 | 57 | 3 | **3.45%** | 1.09% | 3.2x |
| 3 | 1.386 .. 2.041 | 88 | 88 | 63 | 1 | **1.14%** | 1.02% | 1.1x |
| 4 | 2.055 .. 3.347 | 87 | 87 | 61 | 2 | **2.30%** | 0.78% | 2.9x |
| 5 | 3.362 .. 38.14 | 88 | 88 | 58 | 5 | **5.68%** | 0.59% | 9.7x |

RAW  top - bottom = **+4.55 pp**   95% CI (close-cluster bootstrap) [-0.59, +10.38] pp   SE 2.760 pp

EXCESS OVER MODEL, top - bottom = **+5.12 pp**   95% CI [-0.01, +11.01] pp   MDE 7.737 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.64, +14.77] pp, null SE 7.516 pp, permutation p = **0.5828**

### `req_rng60` -- |required move| / index range over last 60s

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.877 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.2263 .. 0.5735 | 88 | 88 | 51 | 1 | **1.14%** | 1.22% | 0.9x |
| 2 | 0.5775 .. 0.8565 | 87 | 87 | 57 | 0 | **0.00%** | 1.12% | 0.0x |
| 3 | 0.8665 .. 1.292 | 88 | 88 | 60 | 3 | **3.41%** | 0.97% | 3.5x |
| 4 | 1.298 .. 2.128 | 87 | 87 | 60 | 4 | **4.60%** | 0.87% | 5.3x |
| 5 | 2.162 .. 17.16 | 88 | 88 | 59 | 4 | **4.55%** | 0.47% | 9.6x |

RAW  top - bottom = **+3.41 pp**   95% CI (close-cluster bootstrap) [-1.16, +8.70] pp   SE 2.456 pp

EXCESS OVER MODEL, top - bottom = **+4.16 pp**   95% CI [-0.32, +9.40] pp   MDE 6.822 pp

SHUFFLED-LABEL CONTROL: null 95% range [-14.77, +14.77] pp, null SE 7.732 pp, permutation p = **0.6487**

### `req_rng300` -- |required move| / index range over last 300s

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 7.301 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.09527 .. 0.308 | 88 | 88 | 57 | 3 | **3.41%** | 1.38% | 2.5x |
| 2 | 0.3084 .. 0.3763 | 87 | 87 | 59 | 0 | **0.00%** | 1.25% | 0.0x |
| 3 | 0.377 .. 0.4597 | 88 | 88 | 64 | 4 | **4.55%** | 1.03% | 4.4x |
| 4 | 0.4598 .. 0.6081 | 87 | 87 | 66 | 3 | **3.45%** | 0.73% | 4.7x |
| 5 | 0.6209 .. 2.744 | 88 | 88 | 56 | 2 | **2.27%** | 0.25% | 9.1x |

RAW  top - bottom = **-1.14 pp**   95% CI (close-cluster bootstrap) [-6.28, +3.96] pp   SE 2.608 pp

EXCESS OVER MODEL, top - bottom = **-0.00 pp**   95% CI [-5.16, +5.08] pp   MDE 7.281 pp

SHUFFLED-LABEL CONTROL: null 95% range [-14.77, +13.64] pp, null SE 7.316 pp, permutation p = **0.8822**

### `gap` -- market implied p(lose) minus model p(lose)

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 5.388 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.006463 .. 0.01283 | 88 | 88 | 61 | 0 | **0.00%** | 1.36% | 0.0x |
| 2 | 0.01292 .. 0.01833 | 87 | 87 | 69 | 3 | **3.45%** | 0.54% | 6.4x |
| 3 | 0.01839 .. 0.03079 | 88 | 88 | 65 | 0 | **0.00%** | 0.55% | 0.0x |
| 4 | 0.03081 .. 0.05932 | 87 | 87 | 57 | 6 | **6.90%** | 1.07% | 6.4x |
| 5 | 0.05935 .. 0.292 | 88 | 88 | 59 | 3 | **3.41%** | 1.13% | 3.0x |

RAW  top - bottom = **+3.41 pp**   95% CI (close-cluster bootstrap) [+0.00, +7.69] pp   SE 1.924 pp

EXCESS OVER MODEL, top - bottom = **+3.64 pp**   95% CI [+0.18, +8.03] pp   MDE 5.470 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.91, +14.77] pp, null SE 7.954 pp, permutation p = **0.6467**

### `lgap` -- log( market implied p(lose) / model p(lose) )

rows 432   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 6

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.147 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | -0.4036 .. 0.7244 | 86 | 86 | 58 | 0 | **0.00%** | 1.67% | 0.0x |
| 2 | 0.7307 .. 1.416 | 87 | 87 | 68 | 4 | **4.60%** | 1.38% | 3.3x |
| 3 | 1.418 .. 2.165 | 86 | 86 | 58 | 2 | **2.33%** | 1.10% | 2.1x |
| 4 | 2.171 .. 3.775 | 87 | 87 | 57 | 2 | **2.30%** | 0.54% | 4.3x |
| 5 | 3.787 .. 17.83 | 86 | 86 | 63 | 4 | **4.65%** | 0.03% | 158.8x |

RAW  top - bottom = **+4.65 pp**   95% CI (close-cluster bootstrap) [+1.10, +9.43] pp   SE 2.196 pp

EXCESS OVER MODEL, top - bottom = **+6.29 pp**   95% CI [+2.74, +11.04] pp   MDE 6.142 pp

SHUFFLED-LABEL CONTROL: null 95% range [-15.12, +16.28] pp, null SE 7.901 pp, permutation p = **0.5569**

### `z` -- |required move| in model sd (higher should be safer)

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.948 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 2.054 .. 2.109 | 88 | 88 | 59 | 3 | **3.41%** | 1.88% | 1.8x |
| 2 | 2.11 .. 2.214 | 87 | 87 | 60 | 2 | **2.30%** | 1.56% | 1.5x |
| 3 | 2.216 .. 2.532 | 88 | 88 | 65 | 1 | **1.14%** | 0.93% | 1.2x |
| 4 | 2.549 .. 3.214 | 87 | 87 | 64 | 4 | **4.60%** | 0.26% | 17.7x |
| 5 | 3.224 .. 11.09 | 88 | 88 | 61 | 2 | **2.27%** | 0.02% | 145.7x |

RAW  top - bottom = **-1.14 pp**   95% CI (close-cluster bootstrap) [-6.17, +3.55] pp   SE 2.481 pp

EXCESS OVER MODEL, top - bottom = **+0.73 pp**   95% CI [-4.30, +5.42] pp   MDE 6.950 pp

SHUFFLED-LABEL CONTROL: null 95% range [-17.05, +13.64] pp, null SE 7.674 pp, permutation p = **0.8862**

### `pmod` -- model p(lose) at entry

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.948 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 0.0006319 | 88 | 88 | 61 | 2 | **2.27%** | 0.02% | 145.7x |
| 2 | 0.0006555 .. 0.005409 | 87 | 87 | 64 | 4 | **4.60%** | 0.26% | 17.7x |
| 3 | 0.005677 .. 0.01335 | 88 | 88 | 65 | 1 | **1.14%** | 0.93% | 1.2x |
| 4 | 0.01342 .. 0.01745 | 87 | 87 | 60 | 2 | **2.30%** | 1.56% | 1.5x |
| 5 | 0.01748 .. 0.02 | 88 | 88 | 59 | 3 | **3.41%** | 1.88% | 1.8x |

RAW  top - bottom = **+1.14 pp**   95% CI (close-cluster bootstrap) [-3.53, +6.20] pp   SE 2.481 pp

EXCESS OVER MODEL, top - bottom = **-0.73 pp**   95% CI [-5.39, +4.33] pp   MDE 6.950 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.64, +17.05] pp, null SE 7.674 pp, permutation p = **0.8862**

### `tau` -- seconds to close at entry

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 4.249 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 3 .. 34 | 83 | 83 | 63 | 0 | **0.00%** | 1.24% | 0.0x |
| 2 | 35 .. 49 | 88 | 88 | 60 | 4 | **4.55%** | 1.39% | 3.3x |
| 3 | 50 .. 59 | 84 | 84 | 59 | 2 | **2.38%** | 1.23% | 1.9x |
| 4 | 60 .. 60 | 183 | 183 | 96 | 6 | **3.28%** | 0.43% | 7.7x |

RAW  top - bottom = **+3.28 pp**   95% CI (close-cluster bootstrap) [+0.60, +6.63] pp   SE 1.517 pp

EXCESS OVER MODEL, top - bottom = **+4.09 pp**   95% CI [+1.49, +7.39] pp   MDE 4.236 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.36, +11.72] pp, null SE 6.381 pp, permutation p = **0.5729**

### `price` -- price paid, dollars

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 7.170 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.69 .. 0.929 | 88 | 88 | 57 | 3 | **3.41%** | 1.19% | 2.9x |
| 2 | 0.931 .. 0.96 | 87 | 87 | 58 | 4 | **4.60%** | 1.19% | 3.9x |
| 3 | 0.961 .. 0.974 | 78 | 78 | 60 | 3 | **3.85%** | 0.95% | 4.0x |
| 4 | 0.975 .. 0.981 | 95 | 95 | 69 | 0 | **0.00%** | 0.81% | 0.0x |
| 5 | 0.982 .. 0.987 | 90 | 90 | 64 | 2 | **2.22%** | 0.54% | 4.1x |

RAW  top - bottom = **-1.19 pp**   95% CI (close-cluster bootstrap) [-6.25, +3.80] pp   SE 2.561 pp

EXCESS OVER MODEL, top - bottom = **-0.54 pp**   95% CI [-5.69, +4.48] pp   MDE 7.248 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.59, +14.60] pp, null SE 7.339 pp, permutation p = **0.8303**

### `spread` -- bid-ask spread at entry

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 8.923 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.001 .. 0.001 | 62 | 62 | 53 | 4 | **6.45%** | 0.89% | 7.3x |
| 2 | 0.002 .. 0.008 | 108 | 108 | 68 | 2 | **1.85%** | 0.74% | 2.5x |
| 3 | 0.009 .. 0.019 | 89 | 89 | 68 | 2 | **2.25%** | 0.99% | 2.3x |
| 4 | 0.02 .. 0.039 | 89 | 89 | 62 | 2 | **2.25%** | 0.93% | 2.4x |
| 5 | 0.04 .. 0.318 | 90 | 90 | 69 | 2 | **2.22%** | 1.12% | 2.0x |

RAW  top - bottom = **-4.23 pp**   95% CI (close-cluster bootstrap) [-11.19, +1.22] pp   SE 3.187 pp

EXCESS OVER MODEL, top - bottom = **-4.47 pp**   95% CI [-11.35, +0.98] pp   MDE 8.945 pp

SHUFFLED-LABEL CONTROL: null 95% range [-16.24, +16.24] pp, null SE 8.374 pp, permutation p = **0.6647**

### `size` -- contracts resting at the touch

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 6.287 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 .. 7.99 | 88 | 88 | 54 | 1 | **1.14%** | 0.80% | 1.4x |
| 2 | 8 .. 18 | 85 | 85 | 64 | 1 | **1.18%** | 0.97% | 1.2x |
| 3 | 19 .. 52 | 90 | 90 | 66 | 2 | **2.22%** | 0.97% | 2.3x |
| 4 | 52.12 .. 142 | 87 | 87 | 62 | 5 | **5.75%** | 1.01% | 5.7x |
| 5 | 151 .. 3865 | 88 | 88 | 67 | 3 | **3.41%** | 0.88% | 3.9x |

RAW  top - bottom = **+2.27 pp**   95% CI (close-cluster bootstrap) [-1.93, +7.00] pp   SE 2.245 pp

EXCESS OVER MODEL, top - bottom = **+2.19 pp**   95% CI [-2.01, +6.97] pp   MDE 6.282 pp

SHUFFLED-LABEL CONTROL: null 95% range [-13.64, +13.64] pp, null SE 7.019 pp, permutation p = **0.7006**

### `age_ms` -- age of the resting level, ms

rows 438   closes 118   **loss-carrying closes 10**   losing markets 12   dropped (feature unavailable) 0

**BELOW THE 30-CLUSTER FLOOR (10 loss-carrying closes). Nothing below is a significance claim, whatever the interval says.**

**MDE (stated before the estimate): 8.014 pp** difference in loss rate between the top and bottom bucket, at 80% power.

| bucket | range | rows | markets | closes | losses | loss rate | model said | obs/model |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 .. 136 | 87 | 87 | 62 | 4 | **4.60%** | 0.87% | 5.3x |
| 2 | 140 .. 446 | 87 | 87 | 54 | 0 | **0.00%** | 1.01% | 0.0x |
| 3 | 449 .. 1097 | 89 | 89 | 68 | 2 | **2.25%** | 0.93% | 2.4x |
| 4 | 1100 .. 1.11e+04 | 87 | 87 | 60 | 3 | **3.45%** | 0.85% | 4.1x |
| 5 | 1.234e+04 .. 8.436e+05 | 88 | 88 | 62 | 3 | **3.41%** | 0.98% | 3.5x |

RAW  top - bottom = **-1.19 pp**   95% CI (close-cluster bootstrap) [-6.80, +4.23] pp   SE 2.862 pp

EXCESS OVER MODEL, top - bottom = **-1.29 pp**   95% CI [-6.88, +4.10] pp   MDE 7.988 pp

SHUFFLED-LABEL CONTROL: null 95% range [-16.55, +14.32] pp, null SE 7.671 pp, permutation p = **0.9222**

### control: coin

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| KXNEAR15M | 37 | 37 | 2 | 5.41% |
| KXZEC15M | 44 | 44 | 2 | 4.55% |
| KXETH15M | 55 | 55 | 2 | 3.64% |
| KXBNB15M | 29 | 29 | 1 | 3.45% |
| KXXRP15M | 63 | 63 | 2 | 3.17% |
| KXHYPE15M | 46 | 46 | 1 | 2.17% |
| KXDOGE15M | 49 | 49 | 1 | 2.04% |
| KXBTC15M | 68 | 68 | 1 | 1.47% |
| KXSOL15M | 47 | 47 | 0 | 0.00% |

### control: hour of day (UTC)

| value | rows | closes | losses | loss rate |
|---|---|---|---|---|
| 14 | 13 | 5 | 2 | 15.38% |
| 12 | 17 | 4 | 2 | 11.76% |
| 11 | 10 | 3 | 1 | 10.00% |
| 15 | 23 | 5 | 2 | 8.70% |
| 19 | 15 | 5 | 1 | 6.67% |
| 16 | 18 | 5 | 1 | 5.56% |
| 1 | 18 | 5 | 1 | 5.56% |
| 3 | 25 | 5 | 1 | 4.00% |
| 22 | 29 | 6 | 1 | 3.45% |
| 13 | 22 | 6 | 0 | 0.00% |
| 17 | 19 | 6 | 0 | 0.00% |
| 18 | 20 | 5 | 0 | 0.00% |
| 20 | 24 | 6 | 0 | 0.00% |
| 21 | 22 | 6 | 0 | 0.00% |
| 23 | 17 | 5 | 0 | 0.00% |
| 0 | 20 | 6 | 0 | 0.00% |
| 2 | 24 | 5 | 0 | 0.00% |
| 4 | 14 | 5 | 0 | 0.00% |
| 5 | 22 | 5 | 0 | 0.00% |
| 6 | 20 | 6 | 0 | 0.00% |
| 7 | 15 | 4 | 0 | 0.00% |
| 8 | 15 | 4 | 0 | 0.00% |
| 9 | 5 | 3 | 0 | 0.00% |
| 10 | 11 | 3 | 0 | 0.00% |

---

## The live loss, on every feature


NEAR index tape: 26 hourly files, 1 ended early.


### buy at tau 22s, NO @ 96.2c x20

recomputed here from the raw tape: locked sum over 39 prints, mu 2.348593, required move +0.001590, sigma_300 0.00027719, model p(lose) 1.813%

| feature | live-loss value | pctile among P1 WINNERS | pctile among P2 WINNERS | P1 winner median | P1 loser median |
|---|---|---|---|---|---|
| `flat10` | 0.4 | 83.5% | 85.9% | 0.1 | 0 |
| `flat30` | 0.4667 | 86.0% | 90.2% | 0.1 | 0.06667 |
| `flat60` | 0.4 | 83.7% | 88.3% | 0.1167 | 0.08333 |
| `flat300` | 0.51 | 87.5% | 92.1% | 0.1367 | 0.1033 |
| `s30_s300` | 1.287 | 82.1% | 75.7% | 0.8294 | 1.038 |
| `s300_s900` | 0.9384 | 43.8% | 44.4% | 0.9736 | 1.023 |
| `s300_s3600` | 0.7694 | 33.8% | 38.3% | 0.8831 | 0.8757 |
| `s300_sday` | 0.6884 | 56.2% | 61.2% | 0.6284 | 0.5732 |
| `mx10_sig` | 6.133 | 96.4% | 95.6% | 1.508 | 1.916 |
| `mx30_sig` | 6.133 | 89.1% | 84.6% | 2.647 | 3.668 |
| `mx60_sig` | 6.133 | 80.0% | 71.8% | 3.764 | 4.489 |
| `req_rng30` | 0.8371 | 13.7% | 15.8% | 3.615 | 0.3871 |
| `req_rng60` | 0.3879 | 8.2% | 2.9% | 2.157 | 0.2815 |
| `req_rng300` | 0.15 | 6.0% | 0.4% | 0.7509 | 0.1155 |
| `gap` | 0.01987 | 82.6% | 43.7% | 0.003 | 0.00561 |
| `lgap` | 0.7402 | 25.0% | 7.0% | 3.933 | 0.05102 |
| `z` | 2.094 | 17.3% | 2.6% | 5.075 | 0.738 |
| `pmod` | 0.01813 | 82.7% | 97.4% | 1.938e-07 | 0.2302 |
| `tau` | 22 | 11.7% | 15.3% | 44 | 48 |
| `price` | 0.962 | 19.5% | 28.9% | 0.995 | 0.75 |
| `spread` | unavailable | | | | |
| `size` | unavailable | | | | |
| `age_ms` | unavailable | | | | |

### buy at tau 21s, NO @ 95.6c x20

recomputed here from the raw tape: locked sum over 40 prints, mu 2.348593, required move +0.001670, sigma_300 0.00027713, model p(lose) 1.223%

| feature | live-loss value | pctile among P1 WINNERS | pctile among P2 WINNERS | P1 winner median | P1 loser median |
|---|---|---|---|---|---|
| `flat10` | 0.5 | 87.2% | 89.9% | 0.1 | 0 |
| `flat30` | 0.4667 | 86.0% | 90.2% | 0.1 | 0.06667 |
| `flat60` | 0.4 | 83.7% | 88.3% | 0.1167 | 0.08333 |
| `flat300` | 0.5133 | 87.6% | 92.2% | 0.1367 | 0.1033 |
| `s30_s300` | 1.288 | 82.1% | 75.7% | 0.8294 | 1.038 |
| `s300_s900` | 0.9382 | 43.7% | 44.4% | 0.9736 | 1.023 |
| `s300_s3600` | 0.7692 | 33.8% | 38.3% | 0.8831 | 0.8757 |
| `s300_sday` | 0.6882 | 56.2% | 61.2% | 0.6284 | 0.5732 |
| `mx10_sig` | 6.134 | 96.4% | 95.6% | 1.508 | 1.916 |
| `mx30_sig` | 6.134 | 89.1% | 84.6% | 2.647 | 3.668 |
| `mx60_sig` | 6.134 | 80.0% | 71.9% | 3.764 | 4.489 |
| `req_rng30` | 0.8789 | 14.4% | 17.2% | 3.615 | 0.3871 |
| `req_rng60` | 0.4073 | 8.8% | 3.5% | 2.157 | 0.2815 |
| `req_rng300` | 0.1575 | 6.4% | 0.4% | 0.7509 | 0.1155 |
| `gap` | 0.03177 | 88.3% | 69.6% | 0.003 | 0.00561 |
| `lgap` | 1.28 | 30.7% | 15.4% | 3.933 | 0.05102 |
| `z` | 2.25 | 19.0% | 11.4% | 5.075 | 0.738 |
| `pmod` | 0.01223 | 81.0% | 88.6% | 1.938e-07 | 0.2302 |
| `tau` | 21 | 10.7% | 14.0% | 44 | 48 |
| `price` | 0.956 | 17.9% | 22.2% | 0.995 | 0.75 |
| `spread` | unavailable | | | | |
| `size` | unavailable | | | | |
| `age_ms` | unavailable | | | | |

### buy at tau 17s, NO @ 73.0c x19

recomputed here from the raw tape: locked sum over 44 prints, mu 2.348632, required move +0.001944, sigma_300 0.00027477, model p(lose) 0.172%

| feature | live-loss value | pctile among P1 WINNERS | pctile among P2 WINNERS | P1 winner median | P1 loser median |
|---|---|---|---|---|---|
| `flat10` | 0.5 | 87.2% | 89.9% | 0.1 | 0 |
| `flat30` | 0.4 | 83.2% | 87.1% | 0.1 | 0.06667 |
| `flat60` | 0.4167 | 84.5% | 89.1% | 0.1167 | 0.08333 |
| `flat300` | 0.51 | 87.5% | 92.1% | 0.1367 | 0.1033 |
| `s30_s300` | 1.329 | 83.7% | 77.7% | 0.8294 | 1.038 |
| `s300_s900` | 0.9297 | 41.8% | 42.9% | 0.9736 | 1.023 |
| `s300_s3600` | 0.7626 | 32.6% | 36.8% | 0.8831 | 0.8757 |
| `s300_sday` | 0.6824 | 55.5% | 60.3% | 0.6284 | 0.5732 |
| `mx10_sig` | 1.092 | 35.7% | 36.0% | 1.508 | 1.916 |
| `mx30_sig` | 6.187 | 89.3% | 84.9% | 2.647 | 3.668 |
| `mx60_sig` | 6.187 | 80.4% | 72.2% | 3.764 | 4.489 |
| `req_rng30` | 1.023 | 16.6% | 22.4% | 3.615 | 0.3871 |
| `req_rng60` | 0.6703 | 16.8% | 22.3% | 2.157 | 0.2815 |
| `req_rng300` | 0.1834 | 8.0% | 1.0% | 0.7509 | 0.1155 |
| `gap` | 0.2683 | 99.9% | 99.9% | 0.003 | 0.00561 |
| `lgap` | 5.059 | 55.6% | 70.1% | 3.933 | 0.05102 |
| `z` | 2.926 | 26.6% | 45.0% | 5.075 | 0.738 |
| `pmod` | 0.001715 | 73.4% | 55.0% | 1.938e-07 | 0.2302 |
| `tau` | 17 | 6.8% | 9.9% | 44 | 48 |
| `price` | 0.73 | 4.0% | 0.1% | 0.995 | 0.75 |
| `spread` | unavailable | | | | |
| `size` | unavailable | | | | |
| `age_ms` | unavailable | | | | |

---

## Does any feature add anything the model does not already charge for?


Every strong column above -- price, `z`, `pmod`, `lgap`, the range ratios -- is the same underlying fact (the strike is close relative to the noise) wearing a different hat, and the live rule ALREADY refuses trades on it via the 2% model gate. The only result that could change the rule is a feature that still separates losers with the model's own number held fixed. Each row below buckets the feature WITHIN quintiles of the conditioner and pools.


### P1

| feature | held fixed | rows | loss-closes | top-bottom | 95% CI | MDE | permutation p |
|---|---|---|---|---|---|---|---|
| `req_rng60` | `z` | 18,962 | 65 | **-4.30 pp** | [-6.49, -2.24] | 2.99 pp | 0.1793 |
| `req_rng300` | `z` | 18,962 | 67 | **-5.89 pp** | [-8.01, -4.03] | 2.82 pp | 0.0717 |
| `z` | `req_rng60` | 18,962 | 67 | **-9.89 pp** | [-12.22, -7.70] | 3.32 pp | 0.0040 |
| `flat10` | `z` | 28,446 | 67 | **-0.03 pp** | [-1.93, +1.75] | 2.67 pp | 0.8765 |
| `flat30` | `z` | 18,030 | 59 | **-0.78 pp** | [-3.59, +1.76] | 3.73 pp | 0.9920 |
| `flat300` | `z` | 18,921 | 53 | **-0.55 pp** | [-2.98, +1.63] | 3.38 pp | 0.8327 |
| `mx10_sig` | `z` | 18,962 | 62 | **+1.13 pp** | [-0.64, +2.85] | 2.59 pp | 0.5498 |
| `mx60_sig` | `z` | 18,963 | 51 | **+1.25 pp** | [-0.76, +3.32] | 2.85 pp | 0.5737 |
| `s30_s300` | `z` | 18,962 | 62 | **+0.57 pp** | [-1.29, +2.45] | 2.61 pp | 0.7490 |
| `s300_sday` | `z` | 18,593 | 50 | **-3.52 pp** | [-6.74, -0.89] | 4.18 pp | 0.3586 |
| `tau` | `z` | 19,067 | 64 | **+1.57 pp** | [-0.35, +3.61] | 2.80 pp | 0.5020 |
| `spread` | `z` | 22,713 | 65 | **-0.22 pp** | [-1.83, +1.21] | 2.11 pp | 0.8008 |
| `age_ms` | `z` | 18,957 | 67 | **-1.80 pp** | [-2.90, -0.80] | 1.46 pp | 0.2908 |
| `price` | `z` | 20,515 | 67 | **-5.87 pp** | [-7.54, -4.28] | 2.22 pp | 0.0359 |
| `gap` | `z` | 20,858 | 66 | **-0.27 pp** | [-1.90, +1.17] | 2.15 pp | 0.8247 |

### P1_tau45+

| feature | held fixed | rows | loss-closes | top-bottom | 95% CI | MDE | permutation p |
|---|---|---|---|---|---|---|---|
| `req_rng60` | `z` | 9,180 | 59 | **-5.25 pp** | [-7.85, -2.88] | 3.66 pp | 0.1394 |
| `req_rng300` | `z` | 9,180 | 61 | **-7.04 pp** | [-9.75, -4.39] | 3.78 pp | 0.0518 |
| `z` | `req_rng60` | 9,180 | 61 | **-10.63 pp** | [-13.60, -7.61] | 4.33 pp | 0.0040 |
| `flat10` | `z` | 13,765 | 61 | **-0.28 pp** | [-2.92, +2.49] | 3.87 pp | 0.9841 |
| `flat30` | `z` | 8,553 | 51 | **-1.28 pp** | [-4.85, +2.15] | 5.13 pp | 0.7849 |
| `flat300` | `z` | 9,157 | 48 | **-0.88 pp** | [-4.33, +2.48] | 4.87 pp | 0.9960 |
| `mx10_sig` | `z` | 9,176 | 56 | **+1.33 pp** | [-1.42, +4.24] | 4.16 pp | 0.5418 |
| `mx60_sig` | `z` | 9,184 | 46 | **+1.84 pp** | [-0.87, +4.79] | 4.09 pp | 0.3944 |
| `s30_s300` | `z` | 9,181 | 56 | **+1.52 pp** | [-1.02, +3.95] | 3.61 pp | 0.5458 |
| `s300_sday` | `z` | 8,971 | 48 | **-4.95 pp** | [-9.83, -1.12] | 6.26 pp | 0.1633 |
| `tau` | `z` | 9,339 | 60 | **+0.65 pp** | [-0.65, +2.06] | 1.94 pp | 0.4701 |
| `spread` | `z` | 9,062 | 59 | **+0.46 pp** | [-1.83, +2.68] | 3.25 pp | 0.9004 |
| `age_ms` | `z` | 9,178 | 61 | **-1.53 pp** | [-3.19, +0.19] | 2.42 pp | 0.5339 |
| `price` | `z` | 10,190 | 60 | **-6.46 pp** | [-8.53, -4.51] | 2.81 pp | 0.0438 |
| `gap` | `z` | 10,097 | 60 | **+0.97 pp** | [-1.58, +3.18] | 3.32 pp | 0.9960 |

### P2


**10 loss-carrying closes -- below the floor. No claim.**

| feature | held fixed | rows | loss-closes | top-bottom | 95% CI | MDE | permutation p |
|---|---|---|---|---|---|---|---|
| `req_rng60` | `z` | 3,130 | 9 | **+2.24 pp** | [+0.45, +4.47] | 2.86 pp | 0.8486 |
| `req_rng300` | `z` | 3,130 | 9 | **+0.77 pp** | [-1.42, +3.19] | 3.17 pp | 0.8167 |
| `z` | `req_rng60` | 3,130 | 9 | **-2.30 pp** | [-4.48, -0.45] | 2.88 pp | 0.6255 |
| `flat10` | `z` | 4,696 | 10 | **-0.65 pp** | [-1.99, +0.68] | 1.88 pp | 0.9522 |
| `flat30` | `z` | 3,219 | 8 | **-0.86 pp** | [-3.18, +1.11] | 3.07 pp | 0.9880 |
| `flat300` | `z` | 3,120 | 7 | **-0.52 pp** | [-2.60, +1.44] | 2.77 pp | 0.8606 |
| `mx10_sig` | `z` | 3,131 | 8 | **-0.64 pp** | [-3.03, +1.43] | 3.20 pp | 0.9562 |
| `mx60_sig` | `z` | 3,129 | 7 | **-1.92 pp** | [-4.27, -0.21] | 2.95 pp | 0.7610 |
| `s30_s300` | `z` | 3,130 | 9 | **-0.83 pp** | [-2.91, +0.62] | 2.56 pp | 0.9243 |
| `s300_sday` | `z` | 3,091 | 8 | **-0.91 pp** | [-3.14, +0.84] | 2.74 pp | 0.8805 |
| `tau` | `z` | 3,152 | 8 | **+2.03 pp** | [+0.51, +4.11] | 2.57 pp | 0.7968 |
| `spread` | `z` | 3,067 | 8 | **-1.23 pp** | [-2.88, +0.26] | 2.29 pp | 0.8606 |
| `age_ms` | `z` | 3,128 | 10 | **+1.34 pp** | [-0.41, +3.39] | 2.82 pp | 0.6335 |
| `price` | `z` | 3,207 | 9 | **-1.38 pp** | [-2.69, -0.29] | 1.76 pp | 0.7331 |
| `gap` | `z` | 3,130 | 9 | **+1.34 pp** | [+0.25, +2.64] | 1.74 pp | 0.8526 |

---

## What a gate would cost


One TRADE per market -- the earliest second that clears the gates, which is what the live rule actually buys. P&L is cents per contract, fee included, at the price really on offer.


### P2 (live rule, tau 3-60): 438 trades over 118 closes, 12 of them losers, ungated P&L +796.9c


**`flat10` -- refuse when the last 10s were too flat**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.1 | 249 | 244 | 5 | 48.8 | -602.5c |
| 0.2 | 176 | 172 | 4 | 43.0 | -318.9c |
| 0.4  **<- the live loss's own value** | 96 | 93 | 3 | 31.0 | -91.0c |
| 0.7 | 46 | 45 | 1 | 45.0 | -47.6c |
| 0.8 | 32 | 31 | 1 | 31.0 | +12.3c |

**`flat30` -- refuse when the last 30s were too flat**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.1 | 228 | 223 | 5 | 44.6 | -526.7c |
| 0.2333 | 146 | 142 | 4 | 35.5 | -238.6c |
| 0.3667 | 89 | 85 | 4 | 21.2 | +33.1c |
| 0.4667  **<- the live loss's own value** | 67 | 65 | 2 | 32.5 | -69.8c |
| 0.6667 | 45 | 45 | 0 | INF (no loss avoided) | -141.8c |
| 0.8 | 24 | 24 | 0 | INF (no loss avoided) | -72.9c |

**`mx30_sig` -- refuse when a big 1s move already happened**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 2.872 | 220 | 214 | 6 | 35.7 | -634.7c |
| 3.982 | 133 | 128 | 5 | 25.6 | -395.1c |
| 4.924 | 89 | 85 | 4 | 21.2 | -259.0c |
| 6.133  **<- the live loss's own value** | 57 | 56 | 1 | 56.0 | -351.4c |
| 6.875 | 45 | 44 | 1 | 44.0 | -250.0c |
| 8.425 | 23 | 22 | 1 | 22.0 | -79.8c |

**`req_rng60` -- refuse when the required move is small vs the 60s range**  (refuse when <= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 1.035 | 219 | 215 | 4 | 53.8 | -933.4c |
| 0.7072 | 132 | 131 | 1 | 131.0 | -832.8c |
| 0.5735 | 88 | 87 | 1 | 87.0 | -543.9c |
| 0.4865 | 44 | 44 | 0 | INF (no loss avoided) | -380.5c |
| 0.4016 | 22 | 22 | 0 | INF (no loss avoided) | -226.9c |
| 0.3879  **<- the live loss's own value** | 20 | 20 | 0 | INF (no loss avoided) | -198.1c |

**`z` -- refuse when the model's own cushion is thin**  (refuse when <= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 2.352 | 219 | 213 | 6 | 35.5 | -609.2c |
| 2.154 | 132 | 128 | 4 | 32.0 | -331.8c |
| 2.109 | 88 | 85 | 3 | 28.3 | -175.3c |
| 2.094  **<- the live loss's own value** | 71 | 69 | 2 | 34.5 | -187.6c |
| 2.077 | 44 | 43 | 1 | 43.0 | -145.1c |
| 2.066 | 22 | 22 | 0 | INF (no loss avoided) | -105.5c |

**`pmod` -- TIGHTEN THE MODEL CEILING below the live 2%**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.001 | 337 | 328 | 9 | 36.4 | -838.4c |
| 0.002 | 312 | 304 | 8 | 38.0 | -840.4c |
| 0.005 | 271 | 265 | 6 | 44.2 | -866.5c |
| 0.01 | 208 | 202 | 6 | 33.7 | -538.2c |
| 0.01813  **<- the live loss's own value** | 71 | 69 | 2 | 34.5 | -187.6c |
| 0.02 | 0 | 0 | 0 | INF (no loss avoided) | +0.0c |

**`price` -- refuse when the price is too high**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.962  **<- the live loss's own value** | 259 | 254 | 5 | 50.8 | -35.3c |
| 0.969 | 224 | 221 | 3 | 73.7 | -123.1c |
| 0.978 | 139 | 137 | 2 | 68.5 | -18.0c |
| 0.982 | 90 | 88 | 2 | 44.0 | +75.2c |
| 0.985 | 54 | 54 | 0 | INF (no loss avoided) | -68.9c |
| 0.987 | 27 | 27 | 0 | INF (no loss avoided) | -32.7c |

### PLIVE (live rule AND the live tau 3-30 window): 165 trades over 83 closes, 0 of them losers, ungated P&L +837.4c


No losers -- a gate can only cost here.


**`flat10` -- refuse when the last 10s were too flat**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.1 | 98 | 98 | 0 | INF (no loss avoided) | -472.9c |
| 0.2 | 61 | 61 | 0 | INF (no loss avoided) | -251.9c |
| 0.3 | 48 | 48 | 0 | INF (no loss avoided) | -198.1c |
| 0.4  **<- the live loss's own value** | 33 | 33 | 0 | INF (no loss avoided) | -134.4c |
| 0.6 | 18 | 18 | 0 | INF (no loss avoided) | -74.5c |
| 0.7 | 12 | 12 | 0 | INF (no loss avoided) | -51.1c |

**`flat30` -- refuse when the last 30s were too flat**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.1 | 89 | 89 | 0 | INF (no loss avoided) | -440.1c |
| 0.2 | 57 | 57 | 0 | INF (no loss avoided) | -256.5c |
| 0.3 | 34 | 34 | 0 | INF (no loss avoided) | -138.4c |
| 0.4667  **<- the live loss's own value** | 19 | 19 | 0 | INF (no loss avoided) | -78.2c |
| 0.7667 | 11 | 11 | 0 | INF (no loss avoided) | -45.1c |

**`mx30_sig` -- refuse when a big 1s move already happened**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 3.521 | 83 | 83 | 0 | INF (no loss avoided) | -522.5c |
| 4.937 | 51 | 51 | 0 | INF (no loss avoided) | -358.7c |
| 6.024 | 34 | 34 | 0 | INF (no loss avoided) | -227.7c |
| 6.133  **<- the live loss's own value** | 33 | 33 | 0 | INF (no loss avoided) | -221.9c |
| 7.777 | 18 | 18 | 0 | INF (no loss avoided) | -137.9c |
| 10.29 | 10 | 10 | 0 | INF (no loss avoided) | -79.7c |

**`req_rng60` -- refuse when the required move is small vs the 60s range**  (refuse when <= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.6636 | 83 | 83 | 0 | INF (no loss avoided) | -550.4c |
| 0.5221 | 50 | 50 | 0 | INF (no loss avoided) | -376.6c |
| 0.437 | 33 | 33 | 0 | INF (no loss avoided) | -291.6c |
| 0.3879  **<- the live loss's own value** | 18 | 18 | 0 | INF (no loss avoided) | -163.7c |
| 0.3726 | 17 | 17 | 0 | INF (no loss avoided) | -150.6c |
| 0.3177 | 9 | 9 | 0 | INF (no loss avoided) | -81.9c |

**`z` -- refuse when the model's own cushion is thin**  (refuse when <= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 2.507 | 83 | 83 | 0 | INF (no loss avoided) | -527.2c |
| 2.207 | 50 | 50 | 0 | INF (no loss avoided) | -319.4c |
| 2.134 | 33 | 33 | 0 | INF (no loss avoided) | -208.0c |
| 2.094  **<- the live loss's own value** | 17 | 17 | 0 | INF (no loss avoided) | -94.8c |
| 2.092 | 17 | 17 | 0 | INF (no loss avoided) | -94.8c |
| 2.077 | 9 | 9 | 0 | INF (no loss avoided) | -59.1c |

**`pmod` -- TIGHTEN THE MODEL CEILING below the live 2%**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.001 | 113 | 113 | 0 | INF (no loss avoided) | -692.3c |
| 0.002 | 104 | 104 | 0 | INF (no loss avoided) | -628.3c |
| 0.005 | 88 | 88 | 0 | INF (no loss avoided) | -546.2c |
| 0.01 | 64 | 64 | 0 | INF (no loss avoided) | -399.0c |
| 0.01813  **<- the live loss's own value** | 17 | 17 | 0 | INF (no loss avoided) | -94.8c |
| 0.02 | 0 | 0 | 0 | INF (no loss avoided) | +0.0c |

**`price` -- refuse when the price is too high**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.962  **<- the live loss's own value** | 83 | 83 | 0 | INF (no loss avoided) | -172.7c |
| 0.963 | 83 | 83 | 0 | INF (no loss avoided) | -172.7c |
| 0.976 | 53 | 53 | 0 | INF (no loss avoided) | -84.8c |
| 0.98 | 41 | 41 | 0 | INF (no loss avoided) | -60.1c |
| 0.986 | 18 | 18 | 0 | INF (no loss avoided) | -22.2c |
| 0.987 | 13 | 13 | 0 | INF (no loss avoided) | -15.7c |

### P1 (wide): 1,014 trades over 132 closes, 73 of them losers, ungated P&L -1840.4c


**`flat10` -- refuse when the last 10s were too flat**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.1 | 600 | 558 | 42 | 13.3 | +1096.8c |
| 0.2 | 420 | 385 | 35 | 11.0 | +1367.1c |
| 0.4  **<- the live loss's own value** | 227 | 205 | 22 | 9.3 | +956.8c |
| 0.7 | 112 | 103 | 9 | 11.4 | +352.1c |
| 0.9 | 55 | 49 | 6 | 8.2 | +360.4c |

**`flat30` -- refuse when the last 30s were too flat**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.1 | 557 | 520 | 37 | 14.1 | +833.8c |
| 0.2333 | 329 | 299 | 30 | 10.0 | +1205.6c |
| 0.3667 | 211 | 190 | 21 | 9.0 | +1025.4c |
| 0.4667  **<- the live loss's own value** | 155 | 140 | 15 | 9.3 | +746.1c |
| 0.6667 | 106 | 98 | 8 | 12.2 | +275.0c |
| 0.8 | 64 | 57 | 7 | 8.1 | +356.6c |

**`mx30_sig` -- refuse when a big 1s move already happened**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 2.601 | 508 | 465 | 43 | 10.8 | +794.7c |
| 3.541 | 305 | 282 | 23 | 12.3 | -106.8c |
| 4.28 | 204 | 186 | 18 | 10.3 | +45.9c |
| 5.809 | 103 | 92 | 11 | 8.4 | +27.2c |
| 6.133  **<- the live loss's own value** | 93 | 83 | 10 | 8.3 | +52.8c |
| 7.478 | 52 | 44 | 8 | 5.5 | +274.8c |

**`req_rng60` -- refuse when the required move is small vs the 60s range**  (refuse when <= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 2.168 | 507 | 443 | 64 | 6.9 | +1246.2c |
| 1.166 | 304 | 243 | 61 | 4.0 | +1343.7c |
| 0.6934 | 203 | 147 | 56 | 2.6 | +1300.3c |
| 0.3879  **<- the live loss's own value** | 116 | 73 | 43 | 1.7 | +951.5c |
| 0.3514 | 102 | 64 | 38 | 1.7 | +647.2c |
| 0.1826 | 51 | 28 | 23 | 1.2 | +286.2c |

**`z` -- refuse when the model's own cushion is thin**  (refuse when <= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 4.032 | 507 | 440 | 67 | 6.6 | +1428.1c |
| 2.502 | 304 | 241 | 63 | 3.8 | +1388.0c |
| 2.094  **<- the live loss's own value** | 252 | 191 | 61 | 3.1 | +1403.5c |
| 1.665 | 203 | 146 | 57 | 2.6 | +1245.4c |
| 0.8978 | 102 | 59 | 43 | 1.4 | +1041.4c |
| 0.464 | 51 | 24 | 27 | 0.9 | +704.9c |

**`pmod` -- TIGHTEN THE MODEL CEILING below the live 2%**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.001 | 382 | 316 | 66 | 4.8 | +1487.1c |
| 0.002 | 352 | 287 | 65 | 4.4 | +1444.9c |
| 0.005 | 314 | 251 | 63 | 4.0 | +1367.5c |
| 0.01 | 278 | 215 | 63 | 3.4 | +1486.4c |
| 0.01813  **<- the live loss's own value** | 252 | 191 | 61 | 3.1 | +1403.5c |
| 0.02 | 246 | 185 | 61 | 3.0 | +1416.8c |

**`price` -- refuse when the price is too high**  (refuse when >= threshold)

| threshold | trades refused | wins refused | losses avoided | wins refused per loss avoided | P&L change |
|---|---|---|---|---|---|
| 0.962  **<- the live loss's own value** | 757 | 745 | 12 | 62.1 | +656.7c |
| 0.993 | 508 | 503 | 5 | 100.6 | +386.8c |
| 0.998 | 328 | 324 | 4 | 81.0 | +362.7c |
| 0.999 | 242 | 240 | 2 | 120.0 | +178.2c |
