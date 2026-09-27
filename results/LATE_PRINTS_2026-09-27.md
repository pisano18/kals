# LEAD 2 -- late index prints vs our live entries (built by lateprints.py)

Entries: live ENTRY orders with a fill, 2026-09-09..09-27 (UTC), hedges excluded. Dropped: {'before 09-09': 27, 'not up/down': 8}. Result conflicts between log / ledger / digest: 0.
Age `a` = the bot's own logged index_age_s at send = send time minus the newest HELD print's stamp second. Tape: {'prints_kept': 7565, 'hours_read': 351, 'truncated_hour': 4, 'missing_hour': 6}.

## MDE (stated before the estimates)

| half | orders | base loss rate | orders a>1s | MDE of loss-rate gap (>1s vs rest, 80% power, 5%) |
|---|---|---|---|---|
| H1 | 471 | 2.8% | 65 | 6.1 pts |
| H2 | 545 | 2.8% | 72 | 5.8 pts |
| ALL | 1016 | 2.8% | 137 | 4.2 pts |

## Age distribution and the tape check

Orders with an exact ms send stamp (09-22 on): 265. For those, S rebuilt WITHOUT the ms stamp matches S from it in 250 of 265.
Held print found on the collector tape: 986 of 1016.
Collector age minus bot age (s): median +0.00, 10th -0.00, 90th +2.00 (n 880) -- near 0 means the collector's receipt times stand in for the bot's.
- H1: age bands {'<0.3s': 265, '0.3-1s': 135, '>1s': 71}; newer print stamped but not received (collector) at send: yes 71 / no 399 / unknown 1
- H2: age bands {'<0.3s': 328, '0.3-1s': 143, '>1s': 74}; newer print stamped but not received (collector) at send: yes 69 / no 447 / unknown 29

## H1 (2026-09-09..2026-09-17): by print age band

| band | orders | markets | closes | lost orders | lost markets | lost closes | loss rate (orders) | $ net | $ lost on losers | $ won on winners |
|---|---|---|---|---|---|---|---|---|---|---|
| <0.3s | 265 | 265 | 223 | 7 | 7 | 7 | 2.6% | +322.48 | -99.96 | +422.44 |
| 0.3-1s | 135 | 134 | 125 | 5 | 4 | 4 | 3.7% | +129.19 | -109.63 | +238.82 |
| >1s | 71 | 71 | 70 | 1 | 1 | 1 | 1.4% | +13.53 | -59.20 | +72.73 |

### H1: by 'newer print stamped but not yet received' (collector tape)

| band | orders | markets | closes | lost orders | lost markets | lost closes | loss rate (orders) | $ net | $ lost on losers | $ won on winners |
|---|---|---|---|---|---|---|---|---|---|---|
| none late | 399 | 396 | 313 | 12 | 10 | 10 | 3.0% | +450.10 | -209.59 | +659.68 |
| newer print late | 71 | 71 | 70 | 1 | 1 | 1 | 1.4% | +13.53 | -59.20 | +72.73 |
| unknown | 1 | 1 | 1 | 0 | 0 | 0 | 0.0% | +1.58 | +0.00 | +1.58 |

### H1: by seconds left x age band

| band | orders | markets | closes | lost orders | lost markets | lost closes | loss rate (orders) | $ net | $ lost on losers | $ won on winners |
|---|---|---|---|---|---|---|---|---|---|---|
| <=10s / <0.3s | 49 | 49 | 46 | 0 | 0 | 0 | 0.0% | +119.05 | +0.00 | +119.05 |
| <=10s / 0.3-1s | 19 | 19 | 19 | 0 | 0 | 0 | 0.0% | +53.98 | +0.00 | +53.98 |
| 11-30s / <0.3s | 199 | 199 | 175 | 7 | 7 | 7 | 3.5% | +183.29 | -99.96 | +283.24 |
| 11-30s / 0.3-1s | 114 | 113 | 109 | 5 | 4 | 4 | 4.4% | +72.80 | -109.63 | +182.44 |
| 11-30s / >1s | 64 | 64 | 63 | 1 | 1 | 1 | 1.6% | +4.81 | -59.20 | +64.00 |
| 31-60s / <0.3s | 17 | 17 | 13 | 0 | 0 | 0 | 0.0% | +20.14 | +0.00 | +20.14 |
| 31-60s / 0.3-1s | 2 | 2 | 2 | 0 | 0 | 0 | 0.0% | +2.41 | +0.00 | +2.41 |
| 31-60s / >1s | 7 | 7 | 7 | 0 | 0 | 0 | 0.0% | +8.73 | +0.00 | +8.73 |

Control (H1): loss-rate gap a>1s minus rest = -1.4 pts; permuting the flag across closes (64 closes flagged), one-sided p = 0.655.
Control (H1): gap for 'newer print late' = -1.6 pts, p = 0.705 (70 closes flagged).
Age mix (H1): winners  share >1s = 14.0% (n 458); losers share >1s = 7.7% (n 13).
Unseen late print moved the index AGAINST our side in 33 of 71 (random sign: half); of those 33, lost 0; of the 38 that moved with/flat, lost 1.

### H1: rule 'refuse an entry when a > X' on our fills

| X | refused orders | refused losers | refused closes | losses removed $ | winners given up $ | net $ | random refusal of same count, net $ |
|---|---|---|---|---|---|---|---|
| 0.5 s | 145 | 2 | 134 | +117.63 | 230.99 | -113.35 | -143.22 |
| 1.0 s | 65 | 1 | 64 | +59.20 | 62.58 | -3.39 | -64.20 |
| 1.5 s | 0 | 0 | 0 | +0.00 | 0.00 | +0.00 | -0.00 |

Total H1: 471 orders, 468 markets, 352 closes, 13 losing orders, net $+465.21.

## H2 (2026-09-18..2026-09-27): by print age band

| band | orders | markets | closes | lost orders | lost markets | lost closes | loss rate (orders) | $ net | $ lost on losers | $ won on winners |
|---|---|---|---|---|---|---|---|---|---|---|
| <0.3s | 328 | 315 | 249 | 6 | 6 | 6 | 1.8% | +205.08 | -356.74 | +561.82 |
| 0.3-1s | 143 | 136 | 118 | 8 | 7 | 7 | 5.6% | -279.34 | -493.14 | +213.80 |
| >1s | 74 | 74 | 71 | 1 | 1 | 1 | 1.4% | +163.33 | -0.83 | +164.16 |

### H2: by 'newer print stamped but not yet received' (collector tape)

| band | orders | markets | closes | lost orders | lost markets | lost closes | loss rate (orders) | $ net | $ lost on losers | $ won on winners |
|---|---|---|---|---|---|---|---|---|---|---|
| none late | 447 | 398 | 294 | 12 | 10 | 10 | 2.7% | +89.19 | -696.11 | +785.30 |
| newer print late | 69 | 69 | 66 | 1 | 1 | 1 | 1.4% | +122.21 | -0.83 | +123.04 |
| unknown | 29 | 25 | 19 | 2 | 1 | 1 | 6.9% | -122.34 | -153.78 | +31.44 |

### H2: by seconds left x age band

| band | orders | markets | closes | lost orders | lost markets | lost closes | loss rate (orders) | $ net | $ lost on losers | $ won on winners |
|---|---|---|---|---|---|---|---|---|---|---|
| <=10s / <0.3s | 23 | 23 | 23 | 0 | 0 | 0 | 0.0% | +78.69 | +0.00 | +78.69 |
| <=10s / 0.3-1s | 15 | 14 | 14 | 0 | 0 | 0 | 0.0% | +45.15 | +0.00 | +45.15 |
| <=10s / >1s | 2 | 2 | 2 | 0 | 0 | 0 | 0.0% | +39.35 | +0.00 | +39.35 |
| 11-30s / <0.3s | 115 | 110 | 97 | 3 | 3 | 3 | 2.6% | +19.17 | -232.29 | +251.46 |
| 11-30s / 0.3-1s | 67 | 61 | 58 | 5 | 4 | 4 | 7.5% | -165.91 | -256.98 | +91.07 |
| 11-30s / >1s | 14 | 14 | 14 | 1 | 1 | 1 | 7.1% | +35.39 | -0.83 | +36.23 |
| 31-60s / <0.3s | 190 | 190 | 162 | 3 | 3 | 3 | 1.6% | +107.21 | -124.46 | +231.67 |
| 31-60s / 0.3-1s | 61 | 61 | 56 | 3 | 3 | 3 | 4.9% | -158.59 | -236.16 | +77.57 |
| 31-60s / >1s | 58 | 58 | 57 | 0 | 0 | 0 | 0.0% | +88.59 | +0.00 | +88.59 |

Control (H2): loss-rate gap a>1s minus rest = -1.6 pts; permuting the flag across closes (70 closes flagged), one-sided p = 0.760.
Control (H2): gap for 'newer print late' = -1.5 pts, p = 0.735 (66 closes flagged).
Age mix (H2): winners  share >1s = 13.4% (n 530); losers share >1s = 6.7% (n 15).
Unseen late print moved the index AGAINST our side in 43 of 69 (random sign: half); of those 43, lost 0; of the 26 that moved with/flat, lost 1.

### H2: rule 'refuse an entry when a > X' on our fills

| X | refused orders | refused losers | refused closes | losses removed $ | winners given up $ | net $ | random refusal of same count, net $ |
|---|---|---|---|---|---|---|---|
| 0.5 s | 162 | 7 | 142 | +339.04 | 302.20 | +36.84 | -26.47 |
| 1.0 s | 72 | 1 | 70 | +0.83 | 160.89 | -160.06 | -11.77 |
| 1.5 s | 1 | 0 | 1 | +0.00 | 0.52 | -0.52 | -0.16 |

Total H2: 545 orders, 482 markets, 341 closes, 15 losing orders, net $+89.06.

## Every losing entry

| t (UTC) | ticker | leg | want | secs left | age a | newer print late? | late print against us? | $ |
|---|---|---|---|---|---|---|---|---|
| 09-09 00:44:38 | KXNEAR15M-26SEP082045-45 | None | no | 22 | 0.44 | False | None | -19.29 |
| 09-09 00:44:39 | KXNEAR15M-26SEP082045-45 | None | no | 21 | 0.33 | False | None | -19.18 |
| 09-09 00:44:43 | KXNEAR15M-26SEP082045-45 | None | no | 17 | 0.19 | False | None | -14.13 |
| 09-10 04:59:39 | KXXRP15M-26SEP100100-00 | None | yes | 21 | 0.18 | False | None | -16.61 |
| 09-10 05:29:34 | KXBNB15M-26SEP100130-30 | None | yes | 26 | 0.22 | False | None | -17.59 |
| 09-10 22:14:49 | KXDOGE15M-26SEP101815-15 | None | no | 11 | 0.43 | False | None | -2.12 |
| 09-11 12:29:30 | KXSOL15M-26SEP110830-30 | None | no | 30 | 0.28 | False | None | -12.16 |
| 09-12 02:59:31 | KXSOL15M-26SEP112300-00 | None | no | 29 | 0.25 | False | None | -19.61 |
| 09-12 07:59:41 | KXSOL15M-26SEP120400-00 | None | yes | 19 | 0.07 | False | None | -18.88 |
| 09-12 23:59:35 | KXZEC15M-26SEP122000-00 | None | yes | 25 | 0.38 | False | None | -10.61 |
| 09-14 09:29:48 | KXBTC15M-26SEP140530-30 | None | no | 13 | 0.93 | False | None | -58.43 |
| 09-14 19:59:30 | KXHYPE15M-26SEP141600-00 | None | no | 30 | 1.02 | True | False | -59.20 |
| 09-16 16:29:30 | KXBNB15M-26SEP161230-30 | None | no | 30 | 0.23 | False | None | -0.98 |
| 09-18 01:14:22 | KXBTC15M-26SEP172115-15 | early | yes | 38 | 0.14 | False | None | -54.19 |
| 09-18 04:14:28 | KXDOGE15M-26SEP180015-15 | early | yes | 32 | 0.20 | False | None | -3.93 |
| 09-19 05:44:36 | KXBNB15M-26SEP190145-45 | full | yes | 24 | 0.18 | False | None | -57.98 |
| 09-19 05:59:25 | KXBTC15M-26SEP190200-00 | early | no | 35 | 0.11 | False | None | -66.34 |
| 09-19 16:29:37 | KXBNB15M-26SEP191230-30 | full | yes | 23 | 0.49 | False | None | -80.69 |
| 09-19 16:29:38 | KXBNB15M-26SEP191230-30 | full | yes | 23 | 0.93 | False | None | -1.67 |
| 09-19 19:59:15 | KXBTC15M-26SEP191600-00 | early | no | 45 | 0.67 | False | None | -107.94 |
| 09-21 16:44:16 | KXNEAR15M-26SEP211245-45 | early | yes | 44 | 0.31 | False | None | -74.24 |
| 09-21 22:14:18 | KXHYPE15M-26SEP211815-15 | early | yes | 43 | 0.94 | False | None | -53.97 |
| 09-23 02:44:48 | KXDOGE15M-26SEP222245-45 | full | no | 12 | 0.52 | False | None | -1.88 |
| 09-23 02:44:49 | KXDOGE15M-26SEP222245-45 | full | no | 11 | 1.04 | True | False | -0.83 |
| 09-24 00:29:34 | KXBTC15M-26SEP232030-30 | full | yes | 26 | 0.18 | None | None | -77.26 |
| 09-24 00:29:34 | KXBTC15M-26SEP232030-30 | full | yes | 26 | 0.68 | None | None | -76.52 |
| 09-27 03:59:30 | KXBTC15M-26SEP270000-00 | full | yes | 30 | 0.14 | False | None | -97.05 |
| 09-27 03:59:30 | KXBTC15M-26SEP270000-00 | full | yes | 30 | 0.58 | False | None | -96.23 |

## Follow-ups (extra.py, trigger.py)

```
age a: min 0.05  median 0.22  90th 1.02  99th 1.08  max 1.78  n 1016
bot a>1 vs collector newer-late: {(False, False): 842, (True, True): 131, (False, True): 9, (False, None): 28, (True, None): 2, (True, False): 4}
collector had NOT yet received the bot's held print at send: 163 of 986 (+106 with nothing received)
H1 0.3-1 vs <0.3: gap +1.1 pts (orders), p 0.107; closes lost 4/125 vs 7/223
H2 0.3-1 vs <0.3: gap +3.8 pts (orders), p 0.010; closes lost 7/118 vs 6/249
ALL 0.3-1 vs <0.3: gap +2.5 pts (orders), p 0.004; closes lost 11/243 vs 13/472
```

Bot entry gate: pinrun.py line ~18248 refuses an entry when idx.spot() age (now minus the newest HELD print's stamp second) > MAX_INDEX_AGE_S = 2 s; logged as kind=refused gate=index_stale (111 market-refusals since 09-09, deduped per market per close). The hedge pass (line ~16843) does NOT refuse on a stale index -- it adds the market's own ask as a second witness.

entries 1016, matched to a signal 975
| half | age band | trigger | orders | closes | lost orders | lost closes | loss rate | $ net |
|---|---|---|---|---|---|---|---|---|
| H1 | 0.3-1s | offer newer than print | 35 | 34 | 0 | 0 | 0.0% | +107.99 |
| H1 | 0.3-1s | offer older than print | 13 | 12 | 0 | 0 | 0.0% | +36.48 |
| H1 | 0.3-1s | unknown | 87 | 81 | 5 | 4 | 5.7% | -15.28 |
| H1 | <0.3s | offer newer than print | 46 | 44 | 1 | 1 | 2.2% | +102.35 |
| H1 | <0.3s | offer older than print | 108 | 94 | 0 | 0 | 0.0% | +235.50 |
| H1 | <0.3s | unknown | 111 | 100 | 6 | 6 | 5.4% | -15.37 |
| H1 | >1s | offer newer than print | 11 | 11 | 0 | 0 | 0.0% | +26.34 |
| H1 | >1s | offer older than print | 17 | 17 | 1 | 1 | 5.9% | -39.27 |
| H1 | >1s | unknown | 43 | 42 | 0 | 0 | 0.0% | +26.46 |
| H1 | all | offer newer than print | 92 | 84 | 1 | 1 | 1.1% | +236.68 |
| H1 | all | offer older than print | 138 | 114 | 1 | 1 | 0.7% | +232.71 |
| H1 | all | unknown | 241 | 186 | 11 | 9 | 4.6% | -4.18 |
| H2 | 0.3-1s | offer newer than print | 102 | 88 | 5 | 5 | 4.9% | -283.99 |
| H2 | 0.3-1s | offer older than print | 18 | 16 | 1 | 1 | 5.6% | +30.34 |
| H2 | 0.3-1s | unknown | 23 | 22 | 2 | 2 | 8.7% | -25.69 |
| H2 | <0.3s | offer newer than print | 100 | 90 | 4 | 4 | 4.0% | -8.23 |
| H2 | <0.3s | offer older than print | 226 | 185 | 2 | 2 | 0.9% | +211.77 |
| H2 | <0.3s | unknown | 2 | 1 | 0 | 0 | 0.0% | +1.53 |
| H2 | >1s | offer newer than print | 47 | 46 | 1 | 1 | 2.1% | +121.52 |
| H2 | >1s | offer older than print | 26 | 26 | 0 | 0 | 0.0% | +41.31 |
| H2 | >1s | unknown | 1 | 1 | 0 | 0 | 0.0% | +0.50 |
| H2 | all | offer newer than print | 249 | 194 | 10 | 9 | 4.0% | -170.70 |
| H2 | all | offer older than print | 270 | 208 | 3 | 3 | 1.1% | +283.42 |
| H2 | all | unknown | 26 | 23 | 2 | 2 | 7.7% | -23.66 |
