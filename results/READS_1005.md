# Reads 2026-10-05 (morning, ~12:00Z)

Read-only. Live money from Kalshi (main-account ledger pulled to 10:15Z, no settlement since; subaccount 2 for the live
forecaster). Paper money from `settled.pnl_c`/100; money bet recovered from pnl_c, cost and the fee. Paper loss counts
are the tape population, never ours. Scripts: session scratchpad `rv1005.py`, `cr_read.py`, `cr_live.py`, `kfetch1005.py`.
Main pot ~$980 (bank at the 04:30Z halt).

## 1. missed-daily (10-04 12Z .. 10-05 12Z)

Live (Kalshi): 15-min 51 markets, 3 lost, -$54.89; hourly BTC 7, +$0.23; race/other 5, +$2.32. **Total -$52.34 (~5% of the pot).**
Losses: HYPE 10-05 00:30 ET -$73.88, HYPE 10-04 20:15 ET -$49.02, BTC 10-04 16:15 ET -$6.08.
No gate refused mostly winners by more than one typical loss (ceiling net +$17.97, spike +$40.19 = 0.7 loss); none
actionable. The one-full-bet cap refused 10 extra bets, both HYPE losers among them (those extras: at most -$157.34), so
it saved money. 3 `full_cap_trim`, all on winners. One no-fill (BTC 9:14 PM ET, NO 89 @ 97.7c) would have lost $87.
Live halted on the 2-loss brake at 04:30:50Z; the watcher restarted it 04:46:15Z (pid 1649400, same code, --minutes 4320,
so it runs out about 10-08 04:46Z, not 10-07 as the `pinrun-exit-1007` item says).

## 2. revert-0925b / revert-0914 (progress: 1 of the >= 3 full ET days)

15-minute coins, closes where the arm, arm-live-twin and live were all up 60 s before the close.

| | arm | twin (newer rules) | LIVE (09-25 build) |
|---|---|---|---|
| **0925b set, 140 closes** (10-03 8:45 PM .. 10-05 7:45 AM ET) | +$24.69, +0.63% on $3,909, 88 mk, 3 lost | +$7.18, +0.30% on $2,362, 50 mk, 2 lost | -$21.78, -0.59% on $3,671, 72 mk, 3 lost |
| 10-04 ET (full day, 96 closes) | +$56.72 (+2.31%) | +$54.77 (+4.24%) | +$22.35 (+0.93%) |
| **0914 set, 130 closes** (10-03 11:15 PM .. 10-05 7:45 AM ET) | -$34.77, **-5.63%** on $617 (flat 20), 44 mk, 3 lost | +$0.44, +0.02% on $2,133, 45 mk, 2 lost | -$28.55, -0.83% on $3,452, 68 mk, 3 lost |
| 10-04 ET (full day) | -$19.03 (-4.16%) | +$54.77 (+4.24%) | +$22.35 (+0.93%) |

- 0925b leads the twin by $17.51 (under the $40 noise line) with MORE losing markets (3 vs 2): bar not met.
- 0914 trails the twin by 5.6 points on money bet (about -$120 at the twin's size), 3 vs 2 losing markets: bar not met.
  Its rules are not the 09-19 rules.
- Live losers on the arms: HYPE 00:30 ET: 0925b -$70.72 and twin -$70.88 (both bought the same 89 @ 97c), 0914 -$19.44
  (20 @ 97c, no insurance). HYPE 20:15 ET: 0925b -$45.40 (same buy as live), twin **did not buy** (seller check), 0914
  -$18.71 (20 @ 93.1c, no insurance). BTC 16:15 ET: 0925b +$19.26, 0914 +$2.82, twin -$1.96.
- Both arms alive; code_sha f9548c5571ff and 06d396480a7a unchanged. arm-0925b runs --early-min-price 0.95, live 0.90.

## 3. HYPE

| market | LIVE (Kalshi) | twin (newer rules) | arm-0914 (paper, 20 flat) |
|---|---|---|---|
| KXHYPE15M-26OCT042015-15 (10-04 8:15 PM ET) | NO 92 @ 93.6c at 24 s, insured YES 92 @ 58.5c, late YES 46 @ 98c: **-$49.02** | **refused**: `toxic_fresh` at 24 s (offer 26 ms old, takers selling our side 74/100), then `market_attempts`: $0 | NO 20 @ 93.1c at 24 s, no insurance: -$18.71 (-100%; ~-$86 at 92) |
| KXHYPE15M-26OCT050030-30 (10-05 12:30 AM ET) | NO 89 @ 97.0c at 22 s, insured YES 89 @ 86c, late YES 44.5 @ 97.8c: **-$73.88** | bought the same 89 @ 97c at 22 s, insured @ 82c: -$70.88. No rule refused it: the offer was 3.1 s old, so not fresh to the seller check; the 97.8c cap covers only the 45-s bet; one-full-bet did not apply | NO 20 @ 97c at 22 s, no insurance: -$19.44 (-100%; ~-$86 at 89) |

Newer rules would have saved $49.02 of the $122.90 (12.5% of the pot) on these two.

HYPE's live record since 2026-09-20 (Kalshi, main account, 15-min coins):

| | markets | losing | net | per market | on money bet |
|---|---|---|---|---|---|
| HYPE | 81 | 4 (all over $20: -$198.09) | **-$103.12** | -$1.27 | -2.44% |
| other 8 coins | 539 | 13 (9 over $20) | +$360.22 | +$0.67 | +1.15% |
| HYPE before 10-04 03:22Z | 71 | 2 | +$10.38 | +$0.15 | |
| others before 10-04 03:22Z | 482 | 12 | +$276.83 | +$0.57 | |

Leaving HYPE out since 09-20 would have **made $103.12 more** (n = 81 HYPE markets, 4 losses). HYPE loses about 5 times
in 100 markets vs about 2 in 100 for the rest, and even before these two losses it earned about $0.42 a market less.
But it hangs on 4 losses: 8 in 100 random 81-market draws from all coins do as badly, so this is suggestive, not proven.

## 4. cleanroom-3-paper (overdue, no bar) -- marked read

09-28 03:15Z .. 10-05 11:45Z, 695 closes (the 7-day run ended 10-05 03:16Z; a new one started 03:20Z, pid 1469140).
Realistic fills: forecaster **-$521.58** on $9,026 (-5.78%), 129 markets, 28 losing (+$235 in its first day, then lost
five ET days running, 09-29..10-03); bettor +$52.88 on $3,996 (+1.32%), 50 markets, 1 losing; contrarian +$73.41 on
$1,058 (+6.94%), 22 markets, 0 losing. Same window, LIVE forecaster (Kalshi sub 2, 98c cap + crash guard, 1/20 then
1/10 size): **+$12.38 on $297.83 (+4.16%), 66 markets, 11 losing**, vs the plain paper forecaster -$730.20 (-9.78%) on
those days. The plain version is a loser; only the guarded live variant makes money (its own read is tonight).

## 5. Other items due today

- dipsell-live: live true, sub 3, $50 pot. 12 triggers, 4 fills (2 contracts each), 0 settled yet: no verdict.
- disk: **22.9 GB free**, about 5-6 GB/day, so about 3 days (around 10-08) to the 6 GB guard and the 5 GB hard
  collection stop. The bar says buy the drive while more than 20 GB remain: that line is about half a day away.
- forecaster-live (9 PM ET) and fcvar-paper (9:30 PM ET) are tonight's reads, left open.

Recorders alive at the end: kalshi_collector.py pid 2532788, crypto_feeds.py pid 105352.
