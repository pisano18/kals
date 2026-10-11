# Loss anatomy -- every live loser against the raw recordings (2026-10-08)
Source order: raw settlement-index feed, raw trade tape and order book, constituent exchange books, our own live fills joined to the ledger. No replay. **This is what happened around OUR fills; it is not a loss rate from the tape and must not be quoted as one.**
## Population
- Losers: every crypto 15M market (12 up/down series; KXCRYPTOLEAD, commodities and pre-2026-09-08 excluded) where the ledger's per-market money (revenue/100 + min(yes,no) - costs - fees) is negative AND pinrun-live has a filled order: **42 markets, $-1539.16**. Ledger markets with no live fill (other bots / manual): 51; losers before 09-08: see skipped.
- Controls: 120 winners sampled with seed 11 from 1316 live winners (+$2240.96), stratified to the losers' tau x price cells (tau [[0, 10], [11, 20], [21, 30], [31, 45], [46, 1000000]]; price [[0.0, 0.9], [0.9, 0.95], [0.95, 0.98], [0.98, 1.01]]). Allocation: {'(2, 2)': 23, '(2, 0)': 11, '(3, 3)': 6, '(3, 2)': 20, '(2, 1)': 14, '(3, 1)': 8, '(1, 1)': 11, '(1, 2)': 6, '(1, 0)': 6, '(3, 0)': 6, '(0, 0)': 3, '(2, 3)': 3, '(0, 1)': 3}
- Decision time = the first FILLED order's send (`t_ms_send`; before 09-22 only the second is logged, placed inside [close - tau, close - tau + 1)). Side, price, tau, strike, sigma, fair, spot, offer-level age and the bot's 3-s sell share come from that order and its signal record.
- Skipped: {'not_crypto15M': 276, 'no_live_fill': 51, 'before_0908': 9}. Unmeasured (no raw file): 0 []
- Crypto losers in the ledger NOT in this population: ['KXWTI15M-26SEP181330-30 -19.96 (no pinrun-live fill)', 'KXWTI15M-26SEP181015-15 -9.41 (no pinrun-live fill)', 'KXGOLD15M-26SEP171700-00 -9.80 (no pinrun-live fill)', 'KXWTI15M-26SEP171615-15 -58.76 (no pinrun-live fill)', 'KXSOL15M-26SEP120600-00 -0.01 (no pinrun-live fill)', 'KXETH15M-26SEP120545-45 -0.00 (no pinrun-live fill)', 'KXBTC15M-26SEP080315-15 -0.00 (no pinrun-live fill)', 'KXNATGAS15M-26SEP070530-30 -8.60 (before 09-08)', 'KXNATGAS15M-26SEP070515-15 -8.22 (before 09-08)', 'KXNATGAS15M-26SEP070500-00 -7.32 (before 09-08)', 'KXGOLD15M-26SEP070330-30 -0.01 (before 09-08)', 'KXBTC15M-26SEP062145-45 -0.00 (before 09-08)', 'KXBTC15M-26AUG222115-15 -10.51 (before 09-08)', 'KXBTC15M-26AUG150130-30 -19.00 (before 09-08)']
- Send-time precision: losers 17 of 42 to the millisecond, controls 42 of 120 (the rest, before 09-22, are placed inside the logged second).
- Constituent feed (Bitstamp/Coinbase/Kraken, Gemini for BTC) exists for BTC/ETH/SOL/XRP/DOGE only: losers with a feed 21 of 42, controls 73 of 120. BNB/NEAR/HYPE/ZEC markets get the index and the Kalshi tape only.
- Settlement cross-check: my 60-print mean vs the ledger result disagrees on 0 of 162 markets []; markets with fewer than 60 prints on the tape: 0 []; my mean vs CF's own `avg_60s_data` at the close differs by >1e-6 on 0 [].
- Tape files missing: 6 ['20260923T16.jsonl.gz', '20260923T20.jsonl.gz', '20260924T00.jsonl.gz', '20260923T16.jsonl.gz', '20260923T20.jsonl.gz', '20260924T00.jsonl.gz']; torn (read up to the tear, nothing filled): 2 ['20260923T19.jsonl.gz', '20260923T19.jsonl.gz']

## Loss classes (first match in this order)
| class | n | $ | meaning |
|---|---|---|---|
| jump_at_send | 14 | -578.87 | a 5-s index move against us of > 3 one-second sd that began within 1 s of the send (we bought into the start of the move) |
| jump_later | 11 | -461.13 | the same kind of move, but it began more than 1 s after the send (nothing at the send had moved yet) |
| rounding_thin | 3 | -126.32 | settlement within 1 unit of the last rounded digit, or within 1 bp, of the strike |
| feed_stale | 1 | -6.08 | bot's index print >= 1.5 s old, or >= 3 missing prints in the last 5 s, or the bot's spot differed from the tape print by > 3 sd |
| hedge_false_alarm | 12 | -236.35 | the market settled OUR way; the money went on a hedge bought against a scare |
| unmeasured | 1 | -130.41 | no usable index window on the tape |

## Every loss (ET close; $ = ledger money; dist = index print minus strike at the send in 1-s sd; lead = seconds a constituent book was on the losing side before the CF print was, after the send (+ = book first); sell3 = tape share of taker volume selling our side in the 3 s before; age = bot's offer-level age ms)
| ticker | ET close | $ | side | price | tau | class | conf bot | dist sd | z tape | move began (s after send) | crossed (s after send) | max 5-s move sd | idx move 3 s before | book move 1 s before | book lead s | sell3 tape | sell3 bot | age ms | hedge (s after send) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KXBTC15M-26SEP270000-00 | 09-27 00:00:00 | -131.98 | yes | 0.9789 | 30 | jump_at_send | 0.998 | 7.281 | 2.878 | 5.79 | 5.8 | 20.819 | -1.569 | -0.0 | 0.481 | 0.5593 | 0.5591 | 50 | 5.8 |
| KXBTC15M-26SEP232030-30 | 09-23 20:30:00 | -130.41 | yes | 0.87 | 26 | unmeasured | 0.99896 | None | None | None | None | None | None | no feed | no feed | None | None | 39 | 8.6 |
| KXBTC15M-26SEP191600-00 | 09-19 16:00:00 | -107.95 | no | 0.98 | 45 | jump_at_send | 0.99944 | 9.237 | 3.261 | 1.3 | 1.3 | 29.811 | -0.095 | 0.0 | 0.179 | 0.6416 | None | 81 |  |
| KXNEAR15M-26OCT030645-45 | 10-03 06:45:00 | -86.95 | no | 0.9646 | 37 | jump_later | 0.99666 | 5.596 | 2.714 | 2.93 | 24.9 | 19.134 | -0.361 | no feed | no feed | 0.0 | 0.0 | 577 | 24.9 |
| KXZEC15M-26OCT070915-15 | 10-07 09:15:00 | -83.26 | yes | 0.931 | 23 | rounding_thin | 0.99951 | 4.353 | 3.297 | 0.5 | 21.5 | 9.618 | -0.592 | no feed | no feed | 0.6387 | 0.6387 | 5 |  |
| KXHYPE15M-26OCT050030-30 | 10-05 00:30:00 | -73.88 | no | 0.97 | 22 | jump_later | 0.99526 | 2.713 | 2.594 | 6.86 | 6.9 | 16.122 | 0.07 | no feed | no feed | 0.8568 | 0.8801 | 3133 | 6.9 |
| KXBTC15M-26SEP190200-00 | 09-19 02:00:00 | -66.34 | no | 0.944 | 35 | jump_later | 0.99687 | 7.643 | 2.734 | 0.87 | 20.9 | 6.699 | -0.764 | 0.0 | 0.109 | 0.7518 | None | 59 |  |
| KXXRP15M-26SEP192345-45 | 09-19 23:45:00 | -64.95 | no | 0.9766 | 41 | hedge_false_alarm | 0.99919 | 6.273 | 3.145 | 0.47 | 10.5 | 8.0 | 3.727 | 2.136 | 0.036 | 0.9582 | None | 35 | 10.5 |
| KXBNB15M-26SEP191230-30 | 09-19 12:30:00 | -61.75 | yes | 0.9727 | 23 | jump_later | 0.99863 | 2.234 | 2.995 | 0.46 | 11.5 | 7.67 | 1.938 | no feed | no feed | 0.8298 | None | 9 | 11.5 |
| KXNEAR15M-26SEP211245-45 | 09-21 12:45:00 | -59.09 | yes | 0.911 | 44 | jump_at_send | 0.99557 | 7.212 | 2.617 | 0.62 | 9.6 | 11.264 | -1.374 | no feed | no feed | 0.4564 | None | 75 | 12.6 |
| KXBNB15M-26SEP190145-45 | 09-19 01:45:00 | -57.76 | yes | 0.7498 | 24 | jump_at_send | 0.99926 | 2.004 | 3.18 | 0.8 | 0.8 | 11.807 | 0.179 | no feed | no feed | 0.6874 | None | 256 | 2.8 |
| KXNEAR15M-26SEP082045-45 | 09-08 20:45:00 | -52.60 | no | 0.962 | 22 | jump_later | 0.9817400000000001 | 3.058 | 2.088 | 5.56 | 5.6 | 11.871 | 0.0 | no feed | no feed | 0.0096 | None | None |  |
| KXHYPE15M-26OCT042015-15 | 10-04 20:15:00 | -49.02 | no | 0.936 | 24 | jump_at_send | 0.99988 | 3.718 | 3.682 | 0.61 | 7.6 | 9.664 | 3.087 | no feed | no feed | 0.6136 | 0.7419 | 23 | 7.6 |
| KXHYPE15M-26SEP192345-45 | 09-19 23:45:00 | -43.92 | no | 0.941 | 33 | hedge_false_alarm | 0.99959 | 2.433 | 3.344 | 0.4 | 4.4 | 11.287 | 2.174 | no feed | no feed | 0.7315 | None | 37 | 3.4 |
| KXXRP15M-26SEP301915-15 | 09-30 19:15:00 | -42.60 | yes | 0.9476 | 20 | rounding_thin | 1.0 | 3.81 | 4.659 | 0.24 | 7.2 | 11.429 | 1.429 | 13.69 | 0.09 | 0.561 | 0.5562 | 859848 | 2.2 |
| KXSOL15M-26OCT022130-30 | 10-02 21:30:00 | -41.11 | no | 0.9146 | 19 | jump_at_send | 0.99998 | 3.647 | 4.071 | 0.86 | 6.9 | 11.737 | 0.0 | 5.952 | -0.308 | 0.5511 | 0.6061 | 24 | 4.9 |
| KXBTC15M-26SEP140530-30 | 09-14 05:30:00 | -34.26 | no | 0.972 | 13 | jump_at_send | 0.99992 | -3.008 | 3.785 | 0.06 | 1.1 | 10.487 | 5.197 | 4.978 | -0.095 | 0.8107 | None | 62 | 1.1 |
| KXETH15M-26SEP270230-30 | 09-27 02:30:00 | -32.73 | yes | 0.8347 | 17 | hedge_false_alarm | 1.0 | -3.623 | 2.317 | 0.94 | 6.9 | 6.211 | 6.901 | 10.64 | -1.725 | 0.7878 | 0.7878 | 92 | 6.9 |
| KXHYPE15M-26SEP211815-15 | 09-21 18:15:00 | -31.27 | yes | 0.98 | 43 | jump_later | 0.9989 | 8.132 | 3.062 | 3.04 | 8.0 | 12.744 | 0.23 | no feed | no feed | 0.6416 | None | 57 | 8.0 |
| KXHYPE15M-26SEP141600-00 | 09-14 16:00:00 | -29.90 | no | 0.9516 | 30 | jump_later | 0.99617 | 1.537 | 2.822 | 9.96 | 12.0 | 15.918 | 0.082 | no feed | no feed | 0.0 | None | 6465 | 11.0 |
| KXBTC15M-26SEP172115-15 | 09-17 21:15:00 | -27.87 | yes | 0.53 | 38 | jump_at_send | 0.99561 | 5.957 | 2.62 | 0.83 | 0.8 | 15.777 | -0.2 | -0.0 | 0.753 | 0.738 | None | 89 | 1.8 |
| KXNEAR15M-26OCT061615-15 | 10-06 16:15:00 | -21.93 | no | 0.975 | 43 | jump_later | 0.99541 | 7.133 | 2.604 | 9.86 | 17.9 | 14.82 | -0.277 | no feed | no feed | 0.3527 | 0.3795 | 816132 | 17.9 |
| KXBNB15M-26SEP261030-30 | 09-26 10:30:00 | -20.29 | no | 0.5954 | 5 | hedge_false_alarm | 0.99722 | -7.931 | -1.944 | None | -0.1 | None | 4.553 | no feed | no feed | 0.3076 | 0.0293 | 427 | -0.1 |
| KXSOL15M-26SEP112300-00 | 09-11 23:00:00 | -19.61 | no | 0.979 | 29 | jump_later | 0.99968 | 5.699 | 3.416 | 7.74 | 17.7 | 51.282 | 0.0 | 0.0 | -0.708 | 0.7523 | None | None |  |
| KXSOL15M-26SEP120400-00 | 09-12 04:00:00 | -18.88 | yes | 0.94 | 19 | jump_at_send | 0.99764 | 8.422 | 2.826 | 0.92 | 3.9 | 14.013 | -5.605 | -0.0 | -0.908 | 0.0768 | None | None |  |
| KXBNB15M-26SEP100130-30 | 09-10 01:30:00 | -17.60 | yes | 0.94 | 26 | jump_at_send | 0.98507 | 4.329 | 2.172 | 1.78 | 16.8 | 4.924 | -2.235 | no feed | no feed | 0.8501 | None | None |  |
| KXXRP15M-26SEP100100-00 | 09-10 01:00:00 | -16.61 | yes | 0.82 | 21 | jump_at_send | 1.0 | 10.127 | 9.099 | 0.82 | 1.8 | 30.886 | 1.772 | 5.19 | 0.762 | 0.9574 | None | None |  |
| KXBTC15M-26OCT061615-15 | 10-06 16:15:00 | -16.59 | no | 0.96 | 45 | hedge_false_alarm | 0.99505 | 7.154 | 2.579 | 0.89 | 30.9 | 7.794 | 0.82 | 0.0 | -0.755 | 0.5367 | 0.5367 | 10 | 30.9 |
| KXBNB15M-26OCT060800-00 | 10-06 08:00:00 | -16.16 | yes | 0.88 | 34 | hedge_false_alarm | 0.99588 | 4.239 | 2.642 | 3.8 | 11.8 | 12.173 | 0.217 | no feed | no feed | 0.6293 | 0.6293 | 53 | 11.8 |
| KXBTC15M-26OCT030400-00 | 10-03 04:00:00 | -13.01 | yes | 0.963 | 36 | hedge_false_alarm | 0.99651 | 6.558 | 2.697 | 5.82 | 16.8 | 12.771 | -1.627 | -0.0 | -7.196 | 0.4992 | 0.5 | 222 | 16.8 |
| KXSOL15M-26SEP110830-30 | 09-11 08:30:00 | -12.16 | no | 0.591 | 30 | jump_at_send | 0.99508 | -1.306 | 2.582 | 0.7 | 0.7 | 34.705 | 7.712 | 13.979 | 0.692 | 0.9354 | None | None |  |
| KXDOGE15M-26SEP160900-00 | 09-16 09:00:00 | -12.14 | no | 0.9793 | 17 | hedge_false_alarm | 0.99537 | 2.731 | 2.56 | 4.81 | 4.8 | 7.75 | 0.0 | 0.0 | 0.694 | None | None | 845044 | 4.8 |
| KXNEAR15M-26SEP160430-30 | 09-16 04:30:00 | -9.22 | yes | 0.9139 | 21 | hedge_false_alarm | 1.0 | 3.31 | 5.678 | 0.76 | None | 12.544 | -0.348 | no feed | no feed | 0.3297 | None | 19 | 2.8 |
| KXZEC15M-26SEP122000-00 | 09-12 20:00:00 | -8.63 | yes | 0.962 | 25 | jump_later | 0.99732 | 6.345 | 2.784 | 1.62 | 4.6 | 20.26 | -1.392 | no feed | no feed | 0.4199 | None | None | 3.6 |
| KXBNB15M-26SEP282000-00 | 09-28 20:00:00 | -8.26 | yes | 0.9749 | 44 | jump_later | 0.99968 | 9.438 | 3.413 | 0.48 | 11.5 | 21.331 | 1.038 | no feed | no feed | 0.2468 | 0.2468 | 116 | 11.5 |
| KXBTC15M-26OCT041615-15 | 10-04 16:15:00 | -6.08 | no | 0.9524 | 45 | feed_stale | 0.99925 | 2.862 | 1.649 | 6.92 | 7.9 | 10.466 | 6.146 | 9.068 | 4.459 | 0.4718 | 0.4591 | 92 | 14.9 |
| KXETH15M-26SEP121115-15 | 09-12 11:15:00 | -5.16 | no | 0.98 | 29 | hedge_false_alarm | 0.99533 | 0.977 | 2.6 | 0.88 | 9.9 | 6.097 | -0.313 | 0.0 | 0.524 | 0.5215 | None | None | 0.9 |
| KXDOGE15M-26SEP222245-45 | 09-22 22:45:00 | -2.47 | no | 0.934 | 12 | jump_at_send | 0.99559 | -0.314 | 2.595 | 1.43 | 1.4 | 12.455 | 0.636 | -0.045 | 0.693 | None | None | 129 | 1.4 |
| KXDOGE15M-26SEP101815-15 | 09-10 18:15:00 | -2.12 | no | 0.0998 | 11 | jump_at_send | 1.0 | 1.51 | 4.577 | 0.56 | 0.6 | 26.6 | 0.2 | 0.0 | 0.493 | 0.8972 | None | None |  |
| KXBNB15M-26SEP131230-30 | 09-13 12:30:00 | -1.10 | no | 0.923 | 5 | hedge_false_alarm | 0.99612 | 1.585 | 2.663 | 0.85 | -15.1 | None | 0.343 | no feed | no feed | 0.5099 | None | 286 | 0.9 |
| KXBTC15M-26SEP121100-00 | 09-12 11:00:00 | -1.09 | no | 0.9 | 30 | hedge_false_alarm | 0.99555 | 7.698 | 2.616 | 0.82 | -23.2 | 5.579 | -0.879 | 0.0 | -3.617 | 0.6201 | None | None | 5.8 |
| KXBNB15M-26SEP161230-30 | 09-16 12:30:00 | -0.47 | no | 0.977 | 30 | rounding_thin | 0.99521 | 3.315 | 2.591 | 4.76 | 10.8 | 9.116 | 0.0 | no feed | no feed | 0.0345 | None | 229 | 9.8 |

## Losers vs controls, every candidate signal available at the send
Threshold = the value that keeps 90% of controls (their 90th or 10th percentile); 'flagged' = beyond it. n = markets. One-sided Fisher p. MDE: with 42 losers and 120 controls, a signal must flag at least 10 losers (0.238 of them) to reach p < 0.05 on one look, and 14 (0.333) to clear the 37-look bar p < 0.0014.
| signal | bad when | threshold | losers flagged | of which before 09-25 / from 09-25 | controls flagged | median losers / controls | p | $ losers flagged | $ controls flagged |
|---|---|---|---|---|---|---|---|---|---|
| bot's own confidence in OUR side at the send | low | 0.9955 | 9 of 42 (21%) | 6 of 27 / 3 of 15 | 11 of 120 (9%) | 0.9975 / 0.9975 | 0.0397 | -212.52 | 32.05 |
| apparent edge = confidence minus price paid (cents) | high | 13.58 | 7 of 42 (17%) | 5 of 27 / 2 of 15 | 12 of 120 (10%) | 4.96 / 4.91 | 0.1879 | -169.53 | 129.45 |
| bot's logged edge_c at the signal | high | 11.196 | 6 of 42 (14%) | 4 of 27 / 2 of 15 | 12 of 120 (10%) | 3.9275 / 3.23 | 0.3078 | -277.77 | 102.41 |
| price paid (cheap = the market disagreed with us) | low | 0.86 | 7 of 42 (17%) | 5 of 27 / 2 of 15 | 11 of 120 (9%) | 0.9458 / 0.948 | 0.1480 | -169.53 | 120.37 |
| model margin recomputed from the tape at the send (sd) | low | 2.597 | 11 of 41 (27%) | 6 of 26 / 5 of 15 | 11 of 117 (9%) | 2.734 / 2.821 | 0.0080 | -247.00 | 35.76 |
| index print minus strike at the send, in 1-s sd | low | 1.853 | 9 of 41 (22%) | 7 of 26 / 2 of 15 | 11 of 117 (9%) | 3.81 / 6.043 | 0.0396 | -140.18 | 69.21 |
| tape 5-min sd / bot sigma | high | 1.0099 | 3 of 41 (7%) | 0 of 26 / 3 of 15 | 11 of 117 (9%) | 1.0 / 1.0 | 0.7576 | -59.10 | 34.30 |
| index moved against us in the last 1 s (sd) | high | 0.457 | 11 of 41 (27%) | 5 of 26 / 6 of 15 | 11 of 117 (9%) | 0.0 / -0.164 | 0.0080 | -322.70 | 59.00 |
| index moved against us in the last 3 s (sd) | high | 0.667 | 13 of 41 (32%) | 6 of 26 / 7 of 15 | 11 of 117 (9%) | 0.07 / -0.528 | 0.0013 | -409.21 | 56.89 |
| index moved against us in the last 10 s (sd) | high | 1.676 | 10 of 41 (24%) | 6 of 26 / 4 of 15 | 11 of 117 (9%) | 0.134 / -0.623 | 0.0184 | -276.05 | 36.67 |
| BTC index 1-s move against us, 1-3 s before (alts only, sd) | high | 1.592 | 8 of 32 (25%) | 5 of 21 / 3 of 11 | 8 of 89 (9%) | 0.6055 / 0.32 | 0.0274 | -367.37 | 20.74 |
| BTC index 1-s move against us incl. the send second (alts, sd) | high | 2.061 | 10 of 32 (31%) | 6 of 21 / 4 of 11 | 8 of 89 (9%) | 1.1365 / 0.393 | 0.0044 | -462.39 | 28.45 |
| worst constituent book move against us, last 1 s (sd) | high | 1.815 | 8 of 21 (38%) | 4 of 14 / 4 of 7 | 7 of 73 (10%) | 0.0 / 0.0 | 0.0042 | -250.49 | 47.47 |
| worst constituent book move against us, last 3 s (sd) | high | 1.954 | 11 of 21 (52%) | 7 of 14 / 4 of 7 | 7 of 73 (10%) | 2.084 / 0.0 | 0.0001 | -320.04 | 40.79 |
| constituent median mid minus CF print, toward our side (sd) | low | -4.319 | 2 of 21 (10%) | 1 of 14 / 1 of 7 | 7 of 73 (10%) | -1.411 / 0.332 | 0.6433 | -59.20 | 7.60 |
| constituent max-min mid spread at the send (bp) | high | 2.999 | 4 of 18 (22%) | 3 of 11 / 1 of 7 | 5 of 52 (10%) | 2.0295 / 0.7755 | 0.1649 | -73.48 | 29.79 |
| constituent books already on the losing side at the send (count) | high | 1 | 4 of 21 (19%) | 2 of 14 / 2 of 7 | 6 of 73 (8%) | 1 / 0 | 0.1539 | -121.74 | 25.74 |
| tape: share of taker volume selling our side, last 3 s | high | 0.7665 | 9 of 39 (23%) | 7 of 24 / 2 of 15 | 11 of 114 (10%) | 0.6136 / 0.4138 | 0.0348 | -316.05 | 41.90 |
| tape: share of taker volume selling our side, last 10 s | high | 0.6541 | 7 of 39 (18%) | 5 of 24 / 2 of 15 | 11 of 114 (10%) | 0.4725 / 0.4411 | 0.1364 | -238.43 | 47.74 |
| tape: contracts of our side sold by takers, last 3 s | high | 17803.95 | 5 of 41 (12%) | 3 of 26 / 2 of 15 | 11 of 117 (9%) | 807.1 / 365.42 | 0.4028 | -233.37 | 71.27 |
| tape: contracts of our side sold by takers, last 10 s | high | 73681.84 | 2 of 41 (5%) | 2 of 26 / 0 of 15 | 11 of 117 (9%) | 1589.57 / 1436.75 | 0.8983 | -94.21 | 63.60 |
| tape: largest single trade, last 10 s (contracts) | high | 3140.0 | 5 of 41 (12%) | 4 of 26 / 1 of 15 | 11 of 117 (9%) | 360.7 / 361.0 | 0.4028 | -142.57 | 62.57 |
| tape: distinct price levels traded, last 10 s | high | 95 | 2 of 41 (5%) | 1 of 26 / 1 of 15 | 11 of 117 (9%) | 49 / 48 | 0.8983 | -198.32 | 71.17 |
| tape: number of trades, last 10 s | high | 2024 | 2 of 41 (5%) | 1 of 26 / 1 of 15 | 11 of 117 (9%) | 148 / 151 | 0.8983 | -198.32 | 66.31 |
| tape: our side bought at/below our price by others, last 10 s | high | 51394.43 | 3 of 41 (7%) | 2 of 26 / 1 of 15 | 11 of 117 (9%) | 621.0 / 1212.36 | 0.7576 | -199.41 | 55.56 |
| tape: seconds since the last trade in this market | low | 0.005 | 3 of 39 (8%) | 2 of 24 / 1 of 15 | 11 of 114 (10%) | 0.034 / 0.0445 | 0.7453 | -158.21 | 48.65 |
| bot's own sell_share_3s at the send | high | 0.8137 | 1 of 15 (7%) | 0 of 0 / 1 of 15 | 2 of 27 (7%) | 0.5562 / 0.4308 | 0.7452 | -73.88 | 6.68 |
| bot: age of the offer level it hit (ms) | low | 17 | 3 of 32 (9%) | 1 of 17 / 2 of 15 | 5 of 88 (6%) | 85.0 / 253.5 | 0.3618 | -161.60 | 23.37 |
| bot: age of its book at the send (ms) | high | 36 | 4 of 42 (10%) | 3 of 27 / 1 of 15 | 11 of 118 (9%) | 4.5 / 6.0 | 0.5907 | -214.95 | 26.37 |
| bot: age of its index print at the send (s) | high | 1.01 | 4 of 42 (10%) | 1 of 27 / 3 of 15 | 12 of 120 (10%) | 0.24 / 0.245 | 0.6378 | -89.00 | 31.27 |
| bot: contracts offered at the level it hit | high | 807.89 | 3 of 42 (7%) | 2 of 27 / 1 of 15 | 12 of 120 (10%) | 146.995 / 66.01 | 0.8012 | -144.51 | 60.16 |
| price paid | high | 0.9795 | 3 of 42 (7%) | 3 of 27 / 0 of 15 | 12 of 120 (10%) | 0.9458 / 0.948 | 0.8012 | -144.38 | 15.00 |
| seconds to close at the send | high | 44 | 3 of 42 (7%) | 1 of 27 / 2 of 15 | 12 of 120 (10%) | 27.5 / 28.0 | 0.8012 | -130.63 | 20.59 |
| contracts filled on the first order | high | 88.0 | 11 of 42 (26%) | 4 of 27 / 7 of 15 | 10 of 120 (8%) | 57.5 / 30.635 | 0.0050 | -686.82 | 82.83 |
| tape book: age of the best offer level (s, losers+controls with a book) | low | 0.003 | 1 of 14 (7%) | 0 of 1 / 1 of 13 | 3 of 32 (9%) | 0.019 / 0.0425 | 0.7796 | -6.08 | 6.23 |
| tape book: offer-side changes in the last 3 s | high | 1433 | 2 of 17 (12%) | 0 of 2 / 2 of 15 | 4 of 42 (10%) | 250 / 188.0 | 0.5626 | -138.06 | 16.02 |
| tape book: contracts offered within 1c of the best | high | 6895.5 | 2 of 16 (12%) | 0 of 1 / 2 of 15 | 3 of 39 (8%) | 319.0 / 425.08 | 0.4562 | -144.98 | 10.95 |

## Fixed rules a bot could run (same population; a rule needs every input it names)
| rule | losers refused | of which before 09-25 / from 09-25 | controls refused | p | $ of losers refused | $ of controls refused |
|---|---|---|---|---|---|---|
| tape: takers sold more of our side than they bought in the last 3 s (share > 0.5) | 26 of 39 (67%) | 17 of 24 / 9 of 15 | 46 of 114 (40%) | 0.0038 | -1058.83 | 178.27 |
| bot's own sell_share_3s > 0.5 (logged since 09-25) | 9 of 15 (60%) | 0 of 0 / 9 of 15 | 9 of 27 (33%) | 0.0890 | -487.33 | 29.86 |
| bot: offer level younger than 500 ms | 26 of 32 (81%) | 15 of 17 / 11 of 15 | 49 of 88 (56%) | 0.0080 | -1117.30 | 223.44 |
| the 09-27 seller gate: level < 500 ms AND tape share > 0.5 AND tau > 20 | 13 of 29 (45%) | 8 of 14 / 5 of 15 | 13 of 83 (16%) | 0.0022 | -758.82 | 65.28 |
| the 09-27 seller gate with the bot's own share (since 09-25) | 5 of 15 (33%) | 0 of 0 / 5 of 15 | 2 of 27 (7%) | 0.0443 | -297.01 | 5.94 |
| index moved >= 1 sd against us over the last 3 s | 12 of 41 (29%) | 6 of 26 / 6 of 15 | 8 of 117 (7%) | 0.0006 | -392.62 | 51.07 |
| index moved >= 2 sd against us over the last 3 s | 8 of 41 (20%) | 4 of 26 / 4 of 15 | 2 of 117 (2%) | 0.0003 | -263.40 | 8.33 |
| index moved >= 1 sd against us over the last 1 s | 7 of 41 (17%) | 3 of 26 / 4 of 15 | 8 of 117 (7%) | 0.0581 | -161.07 | 42.70 |
| a constituent book moved >= 2 sd against us in the last 1 s (feed coins) | 8 of 21 (38%) | 4 of 14 / 4 of 7 | 5 of 73 (7%) | 0.0011 | -250.49 | 37.49 |
| a constituent book moved >= 1 sd against us in the last 3 s (feed coins) | 13 of 21 (62%) | 8 of 14 / 5 of 7 | 12 of 73 (16%) | 0.0001 | -339.10 | 69.23 |
| constituent median sits >= 2 sd below the CF print on the losing side (feed coins) | 9 of 21 (43%) | 5 of 14 / 4 of 7 | 19 of 73 (26%) | 0.1134 | -265.22 | 57.57 |
| index >= 1 sd / 3 s OR a book >= 2 sd / 1 s | 13 of 41 (32%) | 6 of 26 / 7 of 15 | 10 of 117 (9%) | 0.0007 | -433.73 | 62.96 |
| BTC's index moved >= 2 sd against us 1-3 s before (alts) | 7 of 32 (22%) | 4 of 21 / 3 of 11 | 5 of 89 (6%) | 0.0144 | -364.90 | 9.63 |
| index print within 3 sd of the strike at the send | 15 of 41 (37%) | 11 of 26 / 4 of 15 | 19 of 117 (16%) | 0.0075 | -395.71 | 78.02 |
| model margin on the tape below 2.5 sd | 5 of 41 (12%) | 2 of 26 / 3 of 15 | 6 of 117 (5%) | 0.1224 | -129.29 | 13.25 |
| apparent edge (confidence - price) above 10c | 9 of 42 (21%) | 6 of 27 / 3 of 15 | 25 of 120 (21%) | 0.5468 | -316.11 | 181.20 |
| price paid below 90c | 9 of 42 (21%) | 6 of 27 / 3 of 15 | 25 of 120 (21%) | 0.5468 | -316.11 | 181.20 |
| bot's index print older than 0.8 s | 6 of 42 (14%) | 3 of 27 / 3 of 15 | 22 of 120 (18%) | 0.7954 | -154.53 | 58.49 |
| index >= 1 sd / 3 s OR level < 500 ms AND share > 0.5 | 23 of 41 (56%) | 12 of 26 / 11 of 15 | 21 of 117 (18%) | 0.0000 | -974.01 | 136.88 |

Tape 3-s sell share vs the bot's own logged share, where both exist: within 0.15 on 40 of 42 markets (median abs gap 0.002).
Tape order book rebuilt at the send (snapshot + deltas): best offer equals the bot's `ask_seen` on 27 of 55 markets; no negative level on 55 of 55.

## Price and tau on the whole live-filled population (controls are matched on these, so the table above cannot show them)
Every crypto 15M market with a pinrun-live fill since 09-08, counted in markets (our own fills, not the tape).

| bucket | markets | lost | lost per 100 | $ net | $ lost |
|---|---|---|---|---|---|
| price (0.0, 0.9) | 52 | 9 | 17.3 | -9.95 | -316.11 |
| price (0.9, 0.95) | 177 | 13 | 7.3 | 162.52 | -435.68 |
| price (0.95, 0.98) | 865 | 17 | 2.0 | 464.23 | -642.99 |
| price (0.98, 1.01) | 264 | 3 | 1.1 | 85.00 | -144.38 |
| tau (0, 10) | 133 | 2 | 1.5 | 408.38 | -21.38 |
| tau (11, 20) | 219 | 8 | 3.7 | 285.41 | -186.30 |
| tau (21, 30) | 454 | 18 | 4.0 | -66.89 | -761.10 |
| tau (31, 45) | 552 | 14 | 2.5 | 74.89 | -570.38 |

| apparent edge (conf - price, cents) | markets | lost | lost per 100 | $ net |
|---|---|---|---|---|
| [-100, 2) | 496 | 7 | 1.4 | 127.51 |
| [2, 5) | 651 | 14 | 2.2 | 443.14 |
| [5, 10) | 159 | 12 | 7.5 | 141.09 |
| [10, 20) | 44 | 4 | 9.1 | 83.64 |
| [20, 100) | 8 | 5 | 62.5 | -93.60 |
