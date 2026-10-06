# Reads 2026-10-06 (due 12:00Z, read ~15:50Z)

Read-only. Live money from Kalshi (main ledger to the 15:15Z settlement; subaccount 2 = live forecaster, 3 = dip-seller;
balances pulled 15:44Z). Paper money from `settled.pnl_c`/100 (pinrun arms) or the paper fill files (forecaster).
Paper loss counts are the tape population, never ours. Main account at the read: $1,014.66 cash + $29.27 open = $1,043.93;
main bot bank $1,042.75 at the 15:41:22Z v-bankfix-nodd start. Scripts (session scratchpad): `kfetch1006.py`,
`rv1006.py` (from `rv1005.py`), `fc1006.py`, `lockfix1006.py`, `race1006.py`. `portwatch-1006` was read by another agent.

## Verdicts

| item | number | bar | verdict |
|---|---|---|---|
| revert0925-live | since the revert (10-04 03:22:52Z): main bot 126 markets, **+$9.85 = +0.96% of the $1,025.69 bank at the revert** (+0.17% on $5,659 bet); losing markets per ET day: 10-04 **2**, 10-05 1, 10-06 1 (to 11:15 AM ET) | revert on 3+ losing markets in an ET day, or (superseded) a 20% account loss | **KEEP.** No day reached 3. The 20% clause is superseded by the operator's 10-06 order (20% drawdown halt removed in v-bankfix-nodd); reported as a % only. Start record confirmed f9548c5571ff / early_min_price 0.9; live now runs c0fe4953e891 (same 09-25 base + full-bet cap, HYPE skip, bank fix). |
| revert-0925b | 252 shared closes (10-03 8:45 PM .. 10-06 11:45 AM ET): 0925b **+$91.48** (+1.39% on $6,582, 152 mk, 3 lost) vs twin **+$61.65** (+1.50% on $4,098, 88 mk, 2 lost) vs LIVE +$17.89 (+0.30% on $5,898, 122 mk, 4 lost) | over >= 3 full ET days, beat twin by > $40 AND no more losing markets | **Not met** (lead $29.83 < $40; 3 losers vs 2). 2 full ET days so far (10-04, 10-05). |
| revert-0914 | 242 shared closes: 0914 **-$21.71, -1.99%** on $1,090 (flat 20; 78 mk, 3 lost) vs twin +$54.92 (+1.42% on $3,869, 83 mk, 2 lost) | same | **Not met**: trails the twin by 3.4 points on money bet (about -$132 at the twin's size), 3 vs 2 losers. Its rules are not the 09-19 rules. |
| hype-shadow | since v-skiphype: arm-0925b 6 HYPE markets, 6 won, **+$5.57 on $215 (+2.6%)**; twin 4 won, **+$5.88 on $174 (+3.4%)**; today 0925b 4 mk +$3.82, twin 3 mk +$3.58 | none of its own; put-back bar (skiphype, 10-12): > +$30 over the week with NO losing market | No paper HYPE loser yet. PAPER: the loss side is optimistic. Both arms alive (last record 15:37Z). Next read +1 day. |
| fcvar-crash-paper | since 10-02 05:58Z: race1_98_crash10 (= live) **-$105.62**, lost $433.87, 36 mk 7 losing; race1_98 (no guard) **-$206.47**, lost $633.72; guard fired 49 times | VALIDATED if crash10 net >= race1_98 AND money lost no bigger; another gap replaces 10 only if net beats it by > $40 with money lost no bigger | **VALIDATED** (+$100.85 net, $199.85 less lost). crash05 (-$63.78, lost $312.34) beats crash10 by **$41.84**, just over the $40 line, with less lost: literally it **qualifies to replace 0.10**. crash15 (-$55.44) beats by $50.18 but lost $5.49 more: does not. CAUTION: the plumbing check shows two identical copies (base, race1_98 here vs fcvar-paper.jsonl) differ by $90-119 in this window, so a $42 edge is inside copy noise. Changing the live gap is the operator's call; nothing changed. |
| fc-early-skip | since 10-02 21:28Z: r28 **-$14.21** (lost $215.82, 20 mk 4 losing) vs crash10 **-$65.99** (lost $297.59, 22 mk 5 losing); r25 -$44.37 (lost $218.09) | r28 net >= crash10 AND lost <= 80% of crash10's ($238.07) AND live still shows 30+ s first entries losing more often | Paper clauses **pass** for r28 (and r25; r28 is better). Live clause **cannot be shown**: only 1 live first entry at 30+ s since 10-02 21:28Z (won, +$0.16) because r28 has been LIVE since 10-03 06:12Z (v-fc-r28, operator's order). Live since r28: 10 mk, 1 lost, **+$12.34 on $58.71 (+21%)**. Keep r28. |
| lockfix-paper | window 10-02 06:04Z..10-06 12:00Z, 407 shared closes. Flag fired (start record true; 57 of 65 early_dear tickers with no market_attempts after). NEWLY BOUGHT: **3 markets (all early_dear), 3 closes, 0 losers, +$4.99**; early_cheap 0 | GO if > $0 with no loser | **GO by the bar.** But the live bot is now the 09-25 build: it has no `--early-price-free-tries` (needs a port) and no 97.8c cap on the 45-s bet, so the early_dear case it frees cannot occur live. Paper is optimistic (the twin beats live by $6-29/day). Outside the bar: 12 other markets lockfix bought and the twin did not (all won, +$10.67; 9 are 45-s bets at 31-43 s, 7 of them after the twin's early_dear/early_cheap refusals used up its tries -- 2 of those are early_cheap, BTC 10-03 6:30 and 7:00 PM ET, +$5.59, the one kind that could matter live), 7 with more buys than the twin (+$1.04 vs the twin; v-topup drift and same-second second levels). |
| race20cap | since 10-03 06:16Z: 35 orders, max 20 contracts, max open stake $36; fills 309 of 632 contracts (49 in 100). Kalshi: **16 races, 0 lost, +$9.30 on $299 bet (+3.1%) = $2.74/day** vs $4.34/day (20-a-leg period) and $3.49/day (40-a-leg) | PLUMBING fails if any order > 20 or open > $40, or the daystate file is never written after a settled leg | Size/stake plumbing **PASS**. Daystate clause **trips literally** (`results/pinracepenny-daystate.json` does not exist) but investigated: the code writes it only on a losing race or a halt change (pinracearm.py 1180-1209), and there have been 0 losing races, so nothing was due to be written. Not a fault; no revert. The first losing race is its first live test. |
| dipsell-live | live true, sub 3, pot $50 (confirmed). 21 triggers, 7 rail-refused, 14 sent: **3 Kalshi rejections** (2 invalid-parameters from the client-id bug fixed 10-04 19:20Z, 1 post-only cross) + 11 real orders, **9 filled** (82 in 100 of real orders), 2 cancelled unfilled. 9 settled, 6 won 3 lost, 18 contracts: **+$1.24 = +2.5% of the $50 pot** (Kalshi sub 3 balance $51.24 agrees); +6.9c a contract, range low -5.2c; worst day -0.8% (10-05) | 100 fills / 14 days; pass = fills on 50%+ of triggers, > +4c a contract with the low end above zero, no day worse than -25%; kill if negative after 60 fills | **Keep running, no verdict** (9 of 100 fills). Fills on 9 of 21 raw triggers = 43 in 100 (the script's 64 in 100 counts sent orders); low end not yet above zero. |
| disk-guard | **34.92 GB free** at 15:43Z (37.1 after the 06:20Z cleanup; -2.2 GB in 9.4 h, about 5.6 GB/day) | below 10 GB say so loudly; below 6 GB stop analysis | **OK.** About 5 days to the 6 GB guard at today's rate (~10-11), 5.4-7.6 days at 3.8-5.4 GB/day (10-11 .. 10-14). Daily until a drive is bought. |

## Live losing markets in the revert window (Kalshi) and what the arms did

| market | LIVE | arm-0925b | twin | arm-0914 (20 flat) |
|---|---|---|---|---|
| HYPE 10-05 00:30 ET | -$73.88 | -$70.72 | -$70.88 | -$19.44 |
| HYPE 10-04 20:15 ET | -$49.02 | -$45.40 | did not buy (seller check) | -$18.71 |
| **BNB 10-06 08:00 ET (new)** | **-$16.16** (1.5% of the pot): 45-s YES 29.6 @ 88c at 34 s + top-up 59.4 @ 96c at 30 s, then false-alarm insurance at belief 0.14 (NO 89 @ ~23c) at 22 s; the bet won, the insurance lost $21.56 | did not buy (early_cheap: its 45-s floor is 95c) | did not buy (early_cheap / seller check) | +$0.75 |
| BTC 10-04 16:15 ET | -$6.08 | +$19.26 | -$1.96 | +$2.82 |

## Needs a decision

- **arm-live-twin ends by itself today ~18:59Z (2:59 PM ET)** (--minutes 10080 from 09-29 18:59Z; no keep-alive). The
  revert-0925b and revert-0914 bars need 3 full ET days of shared closes with the twin; only 10-04 and 10-05 are full, so
  neither bar can be met unless the twin is restarted (same argv) before then. The lockfix twin comparison also ends there.
- fcvar crash gap: paper says 0.05 by $1.84 over the line, inside copy noise; live stays 0.10 unless the operator says otherwise.
- lockfix: GO by its bar, but it needs a port into the live 09-25 build, where the case it fixes cannot occur.

Recorders alive at the end: see the session report.
