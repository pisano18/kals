# C7-early-ceiling -- REPRODUCE verifier

Status: DONE (2026-09-22). Own code, nothing reused: scratchpad `map/verify2/C7-early-ceiling-reproduce/`
(build.py = own join, a78.py, robust.py, trim.py, subst.py, tape_rebuy.py, hype_fair.py, versions_check.py, earlycap_check.py).

Claim: an early-leg price ceiling of 97.5c (A78, live ~1 h on 09-20 before v-nocap removed it)
would have been ~+$102.85 to +$115.57 on the ledger over ~100 markets (decision-price vs fill-price scoring).

## Verdict: WEAKENED

The arithmetic reproduces to the cent. The claim does not hold as stated:
1. The range is mislabelled. Both numbers use the DECISION price: $102.85 is the entry-fill figure and $115.57 is the ledger figure. Scored on the FILL price it is +$21.91 entry / +$69.78 ledger.
2. A78 as it actually shipped also capped the early sweep limit at 97.5c (A78b, 8898a44). That trims 23 winning fills, so the historical figure is **+$69.69 to +$87.31 entry**.
3. **All of the value comes from one close: the loss the rule was designed after** (BTC 09-19 16:00 ET, -$107.95). Without it, the rule is worth +$7.62 on the ledger and -$2.64 on entry fills. Before that loss it was losing money. **Out of sample, since it was proposed, it is break-even: -$5.24 ledger / +$16.04 entry over 31 markets and 28 closes, 1 losing close.** Even that one save was probably only partial (section 5).
4. There are only 4 losing closes, far below the 30-close floor. Loss rate blocked vs kept: 4/103 vs 2/100 (Fisher p = 0.68). Close-resampled ledger value: 95% range -$97 to +$415, with about a 20% chance it is <= $0.

## 1. Reproduction

Own join: 124 `pinrun-live-*.jsonl` -> 775 settled entry fills (order rows with filled > 0; `want` taken from the preceding signal where the order row lacks it) -> `kalshi_ledger.json` via `pinledger.pnl` (847 rows, one per ticker, no duplicates).

- **Units:** all 1,550 prices (exec + ask_seen) lie in 0.0998..0.996, i.e. dollars.
- **Cost check:** sum(filled x exec) equals Kalshi's yes+no cost on 732 of 749 markets. The 17 that differ are hedged markets.
- **Decision price:** ask_seen equals the preceding signal's `price` on every fill (0 mismatches). That `price` is what `pinrun.py` gates on (`price > EARLY_MAX_PRICE + 1e-9`, line ~10122).
- **Early leg:** 203 settled fills in 203 markets, 09-17 13:29Z .. 09-22 07:44Z, 6 losing fills.

| rule on the early leg | blocked fills | winners | losers | net entry | all-blocked mkts | net ledger |
|---|---|---|---|---|---|---|
| **decision price > 97.5c (what A78 gates)** | 103 (92 closes) | 99, +$117.19 | 4, -$220.04 | **+$102.85** | 100 (89 closes) | **+$115.57** |
| decision price >= 97.5c | 116 | 112, +$140.88 | 4, -$220.04 | +$79.16 | 113 | +$141.57 |
| fill price > 97.5c | 119 | 117, +$140.00 | 2, -$161.91 | +$21.91 | 115 | +$69.78 |
| fill price >= 97.5c | 125 | 123, +$147.10 | 2, -$161.91 | +$14.82 | 121 | +$62.68 |
| early leg off | 203 | 197, +$341.95 | 6, -$360.62 | +$18.67 | 197 | +$69.84 |

**Reconciling the other reports' A78 numbers:**
- **10_loss-autopsy row 3** (99 W +$117.19 / 4 L -$220.04 / +$102.85 / +$115.57 on 100 markets): reproduced exactly. Its "Live 09-20 04:44-05:48 ET" is consistent with the logs (see 4).
- **D1 autopsy's "+$1.23, a wash":** the FILL-price rule, scored with the ledger for losers and entry fills for winners (116 W +$137.99 vs -$139.22). Mine at the same scoring is +$0.78 with 117 winners; their cutoff had one fewer fill.
- **D1 verifier's "+$45.55":** the DECISION-price rule under the same mixed scoring (99 W +$117.19 vs the 4 losing markets' ledger -$162.73). The mix is inconsistent. It keeps the hedge recoveries on losers (DOGE 09-18 +$4.36, HYPE 09-21, BTC 09-17) but drops the hedge false alarm on a blocked WINNER (XRP 09-19 23:45 ET: bet +$2.27, ledger -$64.95).
- **Which is right:** the all-blocked-market ledger (+$115.57) is the consistent accounting. With A78b included, the right figure is lower (section 3).
- D1 verifier's "+$14 to +$46" and "22 trimmed fills, <= $31.54": same direction as mine (23 fills, $15.54-$33.16 at today's cutoff).

## 2. Where the $115.57 comes from (ledger, per close)

| close | entry | ledger |
|---|---|---|
| BTC 09-19 16:00 ET, NO at 98c at tau 45 (**the loss that motivated A78**) | -107.94 | -107.95 |
| XRP 09-19 23:45 ET (bet WON; hedge false alarm under the old 0.60 trigger) | +2.27 | -64.95 |
| HYPE 09-21 18:15 ET, YES at 98c at tau 43 | -53.97 | -31.27 |
| BTC 09-17 21:15 ET (decided 97.8c, filled 53c) | -54.19 | -27.87 |
| DOGE 09-18 00:15 ET (decided 97.6c, filled 11c; the hedge made it positive) | -3.93 | +4.36 |
| 95 other blocked markets, all winners | about +1.2 each | |

| cut (ledger = all-blocked markets) | net entry | net ledger | markets / closes |
|---|---|---|---|
| everything | +$105.30 | +$115.57 | 100 / 89 |
| without the motivating close | -$2.64 | +$7.62 | 99 / 88 |
| without the worst two closes | | -$57.32 | |
| fills before the motivating loss (< 09-19 19:59Z) | -$2.33 | -$35.59 | 57 / 50 |
| from that loss to the A78 deploy | -$18.81 | +$48.45 (XRP false alarm) | 11 / 10 |
| **out of sample: after A78 registered (>= 09-20 09:11Z)** | **+$16.04** | **-$5.24** | **31 / 28, 1 losing** |

The XRP -$64.95 is a hedge false alarm. The hedge verifier puts it at about -$44 even under today's v-hedge25, so the ledger figure bakes in a hedge regime that no longer exists.

## 3. A78 as shipped capped the sweep too (A78b)

A78b is commit 8898a44, 09:11Z, `_limit = min(_limit, EARLY_MAX_PRICE)`, still in pinrun.py line ~10495. The one early order in the A78 run shows `limit_sent 0.975`.

- 23 early fills were decided at <= 97.5c but filled above it. All were winners.
- Removing the part above 97.5c costs **$15.54** (walking the signal's own logged ladder) up to **$33.16** (the whole fills).
- **A78 as shipped = +$69.69 to +$87.31 entry**, and about +$82 to +$100 ledger, since those fills were unhedged winners.

## 4. Live window

- restart_bot.ps1 carries `--early-max-price 0.975` from 552b4f9 (08:44:24Z). The run at 08:44:42Z started 18 s later; its start record predates the field.
- The run at 09:11:29Z records early_max_price 0.975, with A78b in effect.
- The v-nocap run at 09:48:38Z records 1.0.
- So the gate was live 37-64 min (04:44 or 05:11 ET to 05:48 ET).
- **2 early fills happened in that window, both decided at <= 97.5c. The gate never fired live: 0 `early_dear` refusals in all 124 logs.** Every A78 dollar is post-hoc.

## 5. Counterfactual: a blocked signal is not an idle market (tape + index; what the market did, not a loss rate)

**A. Winners (ticker channel, 74 hour files, all present, 0 blocked markets without quotes).**
- 30 of the 99 blocked winners were offered again on the same side: 23 at 90-97.5c inside the early window (tau 31-44), or 15 at <= 98c in the main window.
- Those 30 carry +$42.81 of the +$117.19 forgone. The other 69 (+$74.37) had nothing buyable afterwards, so most of the forgone winner money really was forgone.
- Re-buying those 30 would RAISE A78's value by up to about $43. That is unmeasured, because it needs the model's state at each second.

**B. HYPE 09-21 18:15, the only out-of-sample loss.**
- At 22:14:23.6Z (tau 36) YES was offered at **96.4c** (6 contracts at the top), which passes the ceiling.
- The bot's own formula on the raw index, with its logged sigma 0.007384, gives **fair 0.99556 >= pin 0.995**. The same computation reproduces the bot's logged 0.9989 at the tau-43 decision exactly.
- Edge is about 3c. The worst 1-s move was 2.3 sd, under the jump gate's 3.0.
- **So under A78 the bot would probably have re-bought part of this loss at 96.4-97.5c.** The size depends on depth <= 97.5c, which the ticker channel does not show.
- **Consequence:** the out-of-sample save of $31.27 (ledger) / $53.97 (entry) is an upper bound, and out of sample A78 is likely below break-even on the ledger.
- The earlier tau-45 order at 96.1c (allowed by A78) got 0 fill.

**C. The other three blocked losers.**
- **BTC 09-19 16:00:** no offer at 90-97.5c after the decision. The model flipped to YES by the main window, so the loss really was avoided. This close is in-sample.
- **BTC 09-17 21:15 and DOGE 09-18 00:15:** the book collapsed below 90c with no 90-97.5c print. Under the A78-era early_min_price 0.90 they would stay blocked.

## 6. VERSIONS.md numbers cited around A78

- **v-nocap**, "136 markets, +$110.67, 2 losing": does not reproduce. On the ledger, early-only markets before 09:48:38Z are **135 markets, -$79.91, 5 losing markets (-$311.03)**. That is the same as 10_loss-autopsy section 5.3 and the same artefact as 07 F1: the bot's own settled rows, entry leg only. BTC 09-17 21:15 and BTC 09-19 02:00 have NO settled row in the logs.
- **v-nocap**, "the ceiling would have touched 51% of its fills": reproduces (71 / 140 on the decision price).
- **v-earlycap**, "31-45 s: 2 of 99 losing closes": the ledger and fills say **4 losing closes in 100 on entry, 3 on the ledger**. The two missing are the same two closes with no settled row.
- Since v-nocap: early leg +$10.06 on 62 markets, 2 losing (-$90.36). Reproduced.

## Multiple looks

About 36 cuts: 5 rule variants x 3 scorings, 5 time splits, 2 leave-outs, 2 trim bounds, 4 tape re-offer cells, 1 index fair, 1 Fisher test, 2 resamples, 4 VERSIONS checks. The bar for p is 0.05/36 = 0.0014. Nothing about A78 comes near it: Fisher p = 0.68, P(value <= 0) = 0.20 on the ledger and 0.25 on entry.

## Could not measure

- Depth <= 97.5c at HYPE tau 36, which needs orderbook_delta (~230 MB per hour). Not read.
- The model state for the 30 re-offered winners, which needs a per-second index rebuild for each; a replay-class reconstruction.
- What freed close budget would have bought elsewhere in the same close.

## Resources

- Read-only.
- Tape reads: `ticker` channel for 74 hours and `cfbenchmarks_value` for 1 hour, streamed and filtered by string, each well under 100 MB of python memory.
- Free RAM 1.60 GB before the tape reads and 1.77 GB after.
- kalshi_collector.py (pid 105304) and crypto_feeds.py (pid 105352) alive.
- Disk 31 GB free.
