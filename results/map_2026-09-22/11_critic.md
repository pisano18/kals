# 11 -- Completeness critic: what the map is MISSING (2026-09-22, ~10:20Z)

**Status: COMPLETE.** Read: 01-10, autopsy/ (7), verify/ (24 files, of which 7 are dead
"in progress" stubs: C2-model-overconfident x3, C3 alternative/artefact, C4 alternative/artefact),
and the 15 verifier verdicts. Own code only: scratchpad `map/verify2/critic/` (join.py, periods.py,
recon.py, waterfall.py, price.py, ftab.py, checks.py, sweep.py, row2.py, displace.py,
feedlead.py, feedlead2.py, cbms.py). Money = `kalshi_ledger.json` via `pinledger.pnl` (850 rows,
kept fresh by `pinledgerd.py`, last settlement 09-22 09:45Z). Fills = 124 live logs: 776 fills,
750 markets, all settled, **+$487.26**. Tape read only for what the market/index/exchanges did.
Read-only throughout; python peak < 100 MB; both recorders alive (105304, 105352) at the end;
free RAM 1.8 GB; free disk 30.2 GiB.

---

## 1. Gaps, ranked by the money that could be hiding in them

### G1. The operator's question had no single additive answer. It does now: the bleed is the SIZE of 7 losses, 72% of it from causes already fixed. ($459)

Nobody reconciled "steady era" to "now" in one table that sums. Own join, ledger money, n = closes:

| since the 45 s leg (09-17 13:05Z) | $ |
|---|---|
| actual, 203 closes | **+$60.95** |
| at the steady era's rate (09-13 02Z..09-17 13:05Z: 152 closes, +$2.56/close) | +$520.01 |
| **shortfall** | **-$459.06** |
| = losing closes bigger than the steady era's average loss (-$17.20) | **-$367.18 (80%)** |
| + winning closes paid less ($2.90 vs $3.23 per winning close) | -$64.87 (14%) |
| + more losing closes (8 vs 6.7 expected) | -$27.02 (6%) |

The -$367.18 by cause (each close's excess over -$17.20):

| cause | closes | excess $ | state today |
|---|---|---|---|
| hedge never ran: BTC 09-19 16:00 ET (pause skipped it), BTC 09-19 02:00 ET (crash) | 2 | -135.84 | fixed (A69, round(None)) -- but K1/K2/K3 show three more doors of the same class still open |
| hedge false alarm on two WINNING bets: XRP+HYPE 09-19 23:45 ET | 1 | -91.67 | trigger moved to 0.25 on a replay (C9: not significant); **the one open cause** |
| phantom-depth sizing: BNB 09-19 12:30 ET | 1 | -44.56 | fixed (A67 taper) |
| hedge blocked by the price gate: BNB 09-19 01:45 ET | 1 | -40.56 | removed |
| adverse fill + A76 waited: NEAR 09-21 12:45 ET | 1 | -41.89 | A76 removed |
| ordinary late move, hedged: HYPE 09-21 18:15 ET, BTC 09-17 21:15 ET | 2 | -12.66 | the strategy's cost |

**68% of the shortfall is one ET day (09-19, -$312.63).** Since the fixes (09-20 00:00 ET .. now):
**75 closes, +$114.01, +$1.52 a close** against the steady era's +$2.56 -- positive, but lower,
with only 2 losing closes behind the gap (not significant; C1 verifiers: p 0.004-0.015 per
contract against a ~0.001 bar). 6 of the 8 losing closes contain a 45 s-leg market; the two
BNB closes were <=30 s buys.

Per day (ET, ledger): 09-15 +76.32, 09-16 +85.11, 09-17 +99.87, 09-18 +91.85, **09-19 -223.46**,
09-20 +109.63, 09-21 -2.97, 09-22 (5 closes so far) +7.35.

### G2. "Turn the 45 s leg off" was costed on an assumption nobody tested: that the <=30 s window would have bought those markets. The tape says it mostly could not. (the early leg's whole P&L, -$57 to -$70 since 09-17; +$32 since the fixes)

Every report and verifier listed crowd-out as unmeasured. Measured here from the `ticker`
channel on exchange `ts_ms` (what the market offered, not a loss rate): for each of the 203
markets the 45 s leg bought first, was OUR side offered at 90-98c with >= 1 contract at any
second from tau 30 to tau 3?

| | markets | ledger $ |
|---|---|---|
| never offered at 90-98c later (won) | **157** | +246.74 |
| never offered at 90-98c later (lost) | 6 | -288.16 |
| offered later, not cheaper (won) | 23 | +72.64 |
| offered later CHEAPER than we paid (won; includes the two 09-19 23:45 false alarms) | 17 | -88.60 |

- **80% of the early leg's markets (163 of 203) could not have been bought by the <=30 s
  window** under its 98c ceiling. The early leg mostly ADDS markets; it does not displace them.
- Where the same market was offered later (40), the early leg paid +0.16c more on average,
  median -0.04c: **"the early leg pays more for the same market" is refuted at market level**
  (matches C1-alternative's within-close result).
- So 10's "+$69.84 if off" (freed budget idle) is close to the real counterfactual, and 01's
  "that is a FLOOR on the leg's cost" framing is not supported.
- **Unexplained:** the <=30 s window's volume fell 65% (2,654 -> 936 contracts a day, B vs
  post-fix) while tape supply was flat (09 F3). Displacement explains ~20% of it at most. The
  cause is unmeasured: the refusal log is de-duplicated per (close, market, gate) and
  `close_summary` is not split by seconds-left. Those <=30 s contracts earn +3.1 to +5.6c each
  (post-fix: 0-10 s +5.6c, 11-20 s +3.5c, 21-30 s +3.1c, 0 losses). At B's volume that is an
  ARITHMETIC upper bound of ~$50-60/day of "make more" -- not a measurement.

### G3. Which tweak raised the price we pay: 75% of it is the 45 s leg's book (~$28/day)

09 showed our price rose while the market's did not; nobody named the setting. Contract-weighted
exec price, steady era 95.56c -> post-fix 96.54c (+0.98c):
- the 45 s leg pays 96.88c on 68% of post-fix contracts vs 95.81c for <=30 s buys: **leg mix
  +0.73c (75%)**;
- inside the <=30 s window the touch got cheaper (95.49c -> 95.26c) but the sweep premium above
  the touch grew (+0.22c -> +0.55c): +0.25c.

Worth ~$28/day at post-fix volume (6,568 contracts in 2.2 days x 0.98c), before the lower loss
rate that dearer contracts buy back. Per contract post-fix: early-first markets +0.71c,
late-first +3.92c.

### G4. 08's early-leg pointer is wrong by $344 and nobody caught it

08 F2: early-first markets since 09-19 22:29Z **-$384.15** (87 markets) vs full-first +$93.97.
Ledger: early-first **-$40.15** (87 markets, to 06:29Z); full-first +$93.97 (correct).
The $344.00 is exactly the payouts of four hedged early markets (104 + 81 + 104 + 55 contracts)
lost to Kalshi's `revenue` = 0 field. C6 caught the same bug in 08's -$270.91 and -$19.27, but
not here. Anyone reading 08 alone would see the early leg as 8.6x worse than it is.

### G5. 10's second-best prevention rule is a BTC rule in disguise (claimed +$181.69)

Rule 2, "early leg: refuse when spot is < 3 bp from the strike on our side". Unverified by
anyone. 3 bp is not scaled by each coin's volatility, so it selects BTC: **21 of 32 BTC early
markets are under 3 bp, against 1-6 of 16-29 for every other coin.** Under it: 45 markets,
3 lost, ledger -$173.04 -- all 3 losses are BTC, and two are the 09-19 bug losses (crash
-$66.34, pause -$107.95). The 24 non-BTC markets under 3 bp lost none (-$0.37 net, the -$36.20
is the HYPE false alarm). Needs a sigma-scaled version before it means anything.

### G6. A data source nobody read: `feed_data/` (13 GB of constituent-exchange books). Read; it adds nothing the jump gate does not already see.

- 1-second composite (`index_replica`, median of Coinbase/Bitstamp/Kraken mids; covers only
  BTC/ETH/SOL/XRP/DOGE): exchanges vs the CF value the bot used at the send second. 457 fills,
  10 losing. **AUC 0.41** (no separation). Power check: it barely leads the next CF print
  (corr 0.07).
- Millisecond Coinbase ticks, adverse move over the 1-3 s before the send (send time from the
  `client_order_id` ms stamp; local clock is 10-60 ms behind Coinbase's, so no look-ahead):
  230 usable fills, 6 losing in 6 closes, **AUC 0.80, permutation p = 0.004**. But the 3
  flagged losers are all 09-10..09-14, before the jump gate went live (09-15 01:39Z). After it:
  112 fills, 3 lost, and the 14 fills with a > 2 sd Coinbase move all won. **Covered by the
  jump gate; not a new lever.** Closes the "the market sees the exchanges first" route for
  these 5 coins.

### G7. Documents the next session reads FIRST are wrong about the money and the live config

- CURRENT_STATE says the hedge is "proportional (A76)" and "A76 has NEVER FIRED". A76 fired
  (NEAR 09-21, +$15.15) and was removed; live argv has `--no-hedge-prop --hedge-belief 0.25`.
- CURRENT_STATE/HANDOFF: hedging "8 saves +$111, 7 false alarms -$159"; memory: "-$47".
  Ledger: **-$9.35** (10 saves +$149.26, 7 false alarms -$158.60; C9 exact).
- HANDOFF §0 "money made +$386.94" vs HANDOFF §1 "+$307" in the same section. Measured:
  **+$333.49** (bank $917.92 minus $584.46 deposits = $333.46 at 06:01Z; ledger to that second
  +$333.49 -- a 3-cent match). $386.94 matches neither the account nor the pin bot.
- The memory item "a $16 gap is unexplained": explained. It is the 09-17 21:15 ET close the
  bot's log never recorded (pinday +$115.68 vs ledger +$99.87 = $15.81). No money is missing.

### G8. Live failure modes nobody looked at (checked here)

| failure mode | checked how | result | money |
|---|---|---|---|
| paper arms halt on the LIVE day-loss | `risk_abort` line 7792 calls `day_loss()` with no `a.live` check | **confirmed (06 F6)**: a -$200 live day kills the whole fleet | measurement, not money |
| reboot leaves bot + recorders down until login | `KalsBoot` LogonType Interactive; AutoAdminLogon 0 | **confirmed (06 F8.1)** | ~$1.5/close while down; tape lost |
| PAUSE button "No new bets" | pinrun never reads `pinrun-live.stop`; PAUSE only waits for flat then kills | the bot keeps entering until the next flat moment; tooltip is wrong | small |
| local clock skew breaking tau / ms timing | Coinbase `_rx` - exchange time: p50 12-60 ms, p5 9-55 ms | **not a problem** | -- |
| session load slowing the live bot | order latency p50 87-100 ms every day; 09-22 (this map running, 2.85 GB of Claude processes, 1.8 GB free) 7 orders p50 120 ms | watch item, n = 7 | the price-through race is ~100 ms |
| two or three coins losing in one close | our fills: 0 of 549 closes; index co-occurrence never measured | **unmeasured** | worst close today ~3 x 79 x $0.98 = **$232 (40% of deposits)** |
| disk | kalshi_data +200 MB/h this morning (~4.8 GB/weekday); 30.2 GiB free -> 6 GiB guard ~09-27 | as 06 said; **this map's own scratch holds 3.1 GB** (2.0 GB `verify-D1-0921`, 0.7 GB `map/09`) | tape |

### G9. Claims nobody verified (after this pass)

Verified here: 02 F1 (tau ratio: reproduced exactly -- 0-10 s 0 of 5.3, 11-20 s 3 of 6.2,
21-30 s 10 of 13.3, 31-45 s 6 of 5.8; <=30 s ratio 0.53, P = 0.006); 03 F5 sweep (direction
reproduced: contracts above the touch +$173.60, +2.02c, 163 orders, 2 lost vs 03's +$188.29);
05 F6 divisor (autosize bank $917.92 -> 78 = /11.77); 06 F6, 06 F8.1; 07 F6 (v-late10 "~23:5xZ"
vs first start 09-19T04:03:58Z; v-cheap "~01:0xZ" vs 05:08:21Z; v-cap200 "~03:1xZ" vs 07:30:57Z).

Still unverified, by money riding:
1. **02 F3 index calibration** (the model is 3.7-65x overconfident on the index itself). Needs
   the whole index streamed; corroborated only by the 09-13 RESULTS_calib.md.
2. **09 F3 "competitors did not move earlier"** -- the early leg's founding premise, tape only.
3. **05 F3 "`both_sides` can still block a hedge-equivalent buy"** after the hedge path gives
   up (30 tries) -- a live door of the class that cost 09-19.
4. 04 F7 market-price trigger (replay), 03 F3 hedge chase $46 (fixed), 03 F4 unfilled
   +$15/-$70, 06 F7 downtime 47 closes, 10 rules 4 and 6, 08 F4/F8 (race, ~$1).

---

## 2. Numbers two reports give differently

| quantity | values | who is right |
|---|---|---|
| pin lifetime | 01 +$484.98 (747 mk); 05/07 +$464.98 (07 calls it 747 mk); 10 +$487.20 (749); C3 +$487.21; mine +$487.26 (750) | window + 8 non-bot markets (-$20). **07 pairs the 755-market total with 747 markets** |
| account made | CURRENT_STATE/HANDOFF §0 $386.94; HANDOFF §1 $307 | **$333.49** measured (G7) |
| commodities | 01 -$101.6 | **-$108.06** (10, mine: WTI -77.51, NATGAS -24.14, GOLD -6.62, COPPER +0.21); bot stopped 09-18 |
| hedge lifetime | 04/10/C9 -$9.35; 01 -$11.21; 03 "-$11"; CURRENT_STATE +$111/-$159; memory -$47; K2/K3 -$35.57 (bot rows) | **-$9.35** (C9 exact; bot rows miss BTC 09-17 +$26.32) |
| 09-19 / 09-17 | pinday -$161.14 / +$115.68 | **ledger -$223.46 / +$99.87** (C3) |
| early leg since 09-17 13:05Z | 09 -$57.38; 02/05/07 -$59.00; 01 -$65.41 (own day table sums to -$68.62); 10 -$69.84; C1 -$63.79 | all correct by definition (C1 x3) |
| early leg after 09-19 22:29Z | **08 -$384.15** | **-$40.15** (G4) |
| early leg, era C | 09 -$140.88 (ET days); 02 -$126.70 (UTC) | both right by window |
| early losing markets, era C | 10 "5 of 8" | **6 of 8 markets, 5 of 7 closes** (C1 x3) |
| early leg since full size | 07 -$108.01 (143); C1-art -$110.65 (141 early-only); 05 -$96.48 (161, full-size hours) | definitions |
| v-nocap evidence | VERSIONS +$110.67 (136); **07 rerun +$124.14 (bug in 07)**; ledger -$68.78 (140); -$79.91 (135 early-only); -$76.03 leg-exact | C3 |
| v-cheap bar | 07 -$94.31 (19 fills, bar 09-19 23:44 ET); 01 -$34.59 (26 legs) | **C4: -$35.40 on the 25 fills the cap admitted**; stricter date 09-21 12:44 ET |
| price-through | 01/02 ">5c" 6/15, -$67.33 entry / -$32.51 ledger; 03 ">2c" 7/27 closes -$102.69; 04 ">=3c" 7/23 -$113.18; 05 ">=2c" 4/15 -$110.52; **08 -$270.91 & others -$19.27**; 10 7/28 vs 15/747 | C6: 03 right (really >=2c); 04's is naked (ledger -$112.87); 02's 15 is a float boundary; **08 wrong (-$85.91; +$139.73)**; 10's 747 is 745 fills; 05 unverified |
| fresh offer | 03 <100 ms all legs -$115.79; 10 early <250 ms +$268.72 | C5: +$139..+$184 on today's code; post-hoc; bar not cleared |
| A78 97.5c early cap | 10 +$102.85/+$115.57; D1 +$1.23; D1-verifier +$45.55 | C7: all by definition; in-sample; out-of-sample -$5.24 |
| hedgetune 0.25 vs 0.60 | VERSIONS +$96.90; 04 +$22..42; 10 +$60.69 | C9: +$8..+$46 (best-sourced +$45.51), t 0.52 |
| margin by era | 09 3.76/3.05/2.93c; 10 6.40/4.38/3.41c; 01 4.14 -> 3.04c | different eras/price filters; C8 reproduces 09 |
| steady-era luck | 09 "1 of 199, ~1-in-12" | C8: **3 of 202 by decision price, ~1-in-3.5** |
| bet divisor | 07 "bank / 7.84" | **bank / 11.76** (05, autosize) |
| deadlock | HANDOFF ~2 h, caused by realised reset | **56 min, 3 closes; fakes were other bots and LOWERED the mark** (06, K4) |
| fake transfers net | 06 -$85.86 (14); K4 -$82.81 (18) | K4 |
| edge >= 10c | 02 gap 10c+ 4/40 lost; 05 edge >= 10c 0 of 22 | mine: 3/37 all-time, 1/23 autosize era -- 05's zero does not hold |
| >= 98c fills | 02 98-99c -$17..-$34 (2 of 140); 05 -$48.15 (93, autosize) | windows differ; neither verified |
| crashes | 06 "4 crashes" and "3 in-loop" | K1: 3 |
| order count | 03 1,198; K2/C5 1,204 | K2 (03 stopped at 06:29Z) |
| `ask_seen` logging start | 08 "09-19 22:29Z" | present on 09-15 orders; it is `want` that started later |
| A76 | CURRENT_STATE "never fired", "deployed" | fired once, removed 09-21 17:03Z |
| disk rate / arm RAM | CURRENT_STATE 3 GB/day, 40 MB/arm | 06 3.8-4.8 GB/day, 77 MB; mine +200 MB/h this morning, 61-68 MB/arm |

---

## 3. Refuted or not supported (by this pass)

- "The early leg displaced the <=30 s window" (01 F1 mechanism 3, 02, 07): 80% of its markets
  were never buyable later (G2).
- "The early leg pays more for the same market": +0.16c mean, -0.04c median on the 40 that were.
- "The exchange feeds would have warned us": not after the jump gate (G6).
- "Sweeping deep is the margin leak": contracts above the touch made +2.02c each (G9).
- "Money is missing between bank and ledger": 3-cent match (G7).
- "The disk is falling ~1 GiB/h" (a reading of the 06:25-10:07Z free-space drop): the drop is
  tape (~200 MB/h) plus this map's 3.1 GB of scratch; free space rose 105 MB between 10:07 and
  10:17Z as temporary files cleared.

## 4. Could not measure, and why

- **Why the <=30 s window's volume fell 65%.** Refusals are de-duplicated per (close, market,
  gate); `close_summary` is not split by seconds-left. Needs a log field, not more analysis.
- **Joint losses across coins in one close** -- needs the whole index streamed (> RAM budget
  with this map running).
- **02 F3 on the index** -- same reason.
- Millisecond exchange data for BNB/HYPE/NEAR/ZEC -- `feed_data` does not record them.

## 5. Solutions worth testing

1. **Log, on every `signal` and every refusal, the seconds-left and the close budget left.**
   Blocks nothing. It is the only way to answer G2's open half (why <=30 s volume fell) and to
   price the "make more" upper bound of ~$50-60/day. Validate: one day of records.
2. **Decide the 45 s leg on the corrected counterfactual:** off = lose its markets outright
   (they mostly cannot be bought later), not "hand them to the <=30 s window". Post-fix the leg
   is +$31.96 on 70 markets (+0.71c/contract) against +$82.05 on 36 for <=30 s. The honest
   options are a third size (keeps the adding, cuts the tail) or a live test with a written bar;
   never a gate that can touch a hedge.
3. **Sigma-scale 10's rule 2 before anyone uses it** (G5), and test it on non-BTC markets only
   after the 09-19 bug losses are excluded.
4. **Fix CURRENT_STATE's hedge section and money figures** (G7) before the next context clear:
   -$9.35 hedge lifetime, +$333.49 account, A76 removed, trigger 0.25.
5. **Gate paper arms' day-loss read on `a.live`** (06 F6, confirmed) and **run KalsBoot
   whether logged on or not** (06 F8.1, confirmed). Neither blocks a hedge.
6. **Delete the map's scratch after the operator has read the reports** (3.1 GB,
   `scratchpad/map/verify-D1-0921` and `map/09` are 2.7 GB of it). Disk is the hard deadline.

## Cuts and multiple looks

Inferential looks in this pass: 1-s replica (2 features), Coinbase ms (2 features, 3
thresholds), post-gate split (1), tau ratio (reproduction), edge buckets (2 definitions),
displacement (1), latency (1) -- **about 12, bar p < 0.004.** Only the Coinbase AUC reached
p = 0.004, and it is explained by the jump gate. Every dollar figure in G1-G5 is an exact sum
on the ledger, not an inference. Every losing-close count here is under the 30-close floor.
