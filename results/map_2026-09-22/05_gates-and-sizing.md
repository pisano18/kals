# 05 gates-and-sizing -- COMPLETE (2026-09-22)

Investigator 05. Read-only. **Money = Kalshi's ledger** (`results/kalshi_ledger.json` via
`pinledger.pnl`, one row per market, hedges netted in), crypto pin series only (9 series, 755
markets, +$464.98 all-time; commodities -$108 and coin race -$1 excluded). **Decisions** =
`results/pinrun-live-*.jsonl` (124 runs). **Outcomes of markets we did NOT trade** = tape
`market_lifecycle_v2` "determined" events (25,027 markets) plus `C:\kals\fulltape` (11,785);
zero disagreements where both exist, zero disagreements with our own settled records.
"ET day" = close time minus 4 h. W0 = 09-08..09-12 ET, W1 = 09-13..09-18, W2 = 09-19..09-21.
Scripts: `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\map\05\`
(`parse.py`, `outcomes.py`, `gateval*.py`, `markets.py`, `sizing*.py`, `decomp.py`, `buckets.py`).

Refusal records only exist from 2026-09-14 00:35Z (A25). Nothing before that is scoreable per gate.
End of run: both collectors alive (pids 105304, 105352), 2.15 GB RAM free, 34 GB disk free. Tape read:
`market_lifecycle_v2` (all hours 09-07..09-22, 4 truncated gz files skipped) and one `ticker` hour (09-21 T16).

---

## 1. Findings, ranked by dollars

### F1. The 45-second leg at FULL size is the one sizing choice that is losing money: -$96.48, and the logs hide it.
- **Claim.** In the hours `--early-frac` was 1.0 (09-17 19:41Z..09-18 01:48Z and 09-18 16:33Z..now) markets
  whose first fill was at 31-45 s made **-$96.48 on $11,276 staked** (161 markets, 117 closes, 7 losing markets
  in 6 losing closes, **-$401.39** of losses, -0.83c/contract), by Kalshi's ledger. In the hours it was a third
  or a half: **+$37.48 on $1,061** (41 markets, 32 closes, 0 losses, +3.34c). All-time, every market holding an
  early fill: **-$59.00 on 13,080 contracts** (202 markets, 149 closes, 7 losing).
- The third-size window had 0 losses in 32 closes; at the full-size rate (6 in 117) that happens ~19 times in
  100 by luck. So the size split does NOT prove smaller is safer per contract -- it proves the leg as run is
  net negative, and that its losses scale one-for-one with the fraction.
- **By seconds left at first fill, whole autosize era (09-12 23Z..now, 512 markets / 362 closes):**
  31-45 s **-0.45c/contract** (-$59.00 on $12,618) | 21-30 s +1.85c (+$196.50) | 11-20 s +2.85c (+$135.95) |
  last 10 s +4.94c (+$177.43).
- **Mechanism.** Out at 45 s three quarters of the 60-print settlement average is still unwritten, so the
  model's 99.5% is least true there; full size means the whole bet (70-110 contracts) sits exposed for the
  longest time, so it both loses outright more often (BTC 09-19 16:00 ET -$107.95, BTC 09-19 02:00 -$66.34,
  NEAR 09-21 12:45 -$59.09, HYPE 09-21 18:15 -$31.27) and trips more hedge alarms that turn out false
  (XRP+HYPE 09-19 23:45 ET: both bets WON, the hedges cost -$108.86). 5 of W2's 7 losing closes are early-leg bets.
- **Why the project believes the opposite.** HANDOFF 09-21 says the 45 s leg is "+$110.67, 1.5% loss rate".
  Our own logs, main legs only, to 09-21 05:00Z, say +$176.80; hedge legs -$108.57; and the BTC 09-19 02:00
  position has NO settled record at all (the process crashed holding it). Kalshi's ledger for the same 171
  markets says **-$9.89**. The log-based figure left out the insurance the leg forced and the crashed position.
- **Confidence.** High that the ledger number is right. Moderate on cause: 6 losing closes under full size,
  under the 30-close floor; several of those losses were ALSO hedge bugs (F3). Artefact check: leg assigned by
  `tau_at_send > 30` on the first fill and cross-checked against the order's `leg` field (same 202 markets);
  top-ups after the early leg are ~1% of those markets' contracts, so the market P&L is the early leg's.

### F2. W2's damage (09-19..09-21) is NOT bigger bets. It is more cents lost per contract when a close loses.
| window | closes | losing | loss $ | per losing close | contracts per losing close | cents lost per contract |
|---|---|---|---|---|---|---|
| 09-12..09-14 ("a week ago") | 149 | 6 (4.0%) | -$96.56 | **-$16.09** | 39 | 41.4c |
| 09-15..09-18 | 140 | 3 (2.1%) | -$37.15 | -$12.38 | 123 | 10.1c |
| W2 09-19..09-21 | 124 | 7 (5.6%) | -$488.97 | **-$69.85** | 108 | **64.8c** |
- Against W1 (09-13..09-18, net +$549): W2's excess loss is -$432; **bigger bets explain -$14**, more
  losing closes -$85, **more cents lost per contract -$333**.
- Against "a week ago" (09-12..09-14, SIZE 20-58): the loss per losing close is 4.3x bigger, about **two
  thirds of that is size** (39 -> 108 contracts) and a third is cents per contract (41 -> 65c).
- **W2 average SIZE was 88, the four profitable days before it averaged 86.** At a flat SIZE 85 W2 would still
  have lost **-$90** instead of -$117. The part of W2 bought by the 09-19 deposit ($370.44) netted **+$3.39**
  (won $146.44, lost $143.04) -- a wash.
- **Mechanism.** W1's losses were hedged at the alarm and cost ~10-20c a contract; W2's were unhedged
  because something blocked the hedge (F3), or were false-alarm hedges on bets that won. Size multiplies
  whatever the per-contract result is: W1 +2.99c/contract, W2 **-0.89c**, 09-20..21 +1.69c.
- **Confidence.** Arithmetic is exact (ledger, every close). The rate 2.3% vs 5.6% is 5 vs 7 events -- not
  distinguishable. Baseline matters (memory: baseline error) -- both baselines are shown.

### F3. Gates and brakes blocked or delayed a HEDGE on $225 of W2 losses. All three causes are already switched off.
| close (ET) | loss | what stopped the hedge | evidence |
|---|---|---|---|
| BTC 09-19 16:00 | **-$107.95** | `loss bound` PAUSE fired 19:59:15Z, the same second the 110-contract fill at 98c landed; its `continue` skipped the hedge pass (fixed A69; bound removed A73) | pause record; NO `hedge_alarm` record exists for this market |
| BNB 09-19 01:45 | **-$57.76** | FOUR things: `--hedge-price 0.60` refused NO at **21c**; 5-try cap gave up after 51c/70c/76c tries filled 1 contract; then the ENTRY path's `both_sides` guard refused a NO buy at tau 8 (model had flipped to 0.1% YES). Also: `dump_guard` refused this market at 82c at 05:44:35 and **one second later the bot bought 76 at an 85c signal that passed the 15c line by 0.1c, filling at 75c** | `dumped`, `hedge_wait_price`, `hedge_gave_up`, `refused both_sides` 05:44:35-52Z |
| NEAR 09-21 12:45 | **-$59.09** | A76 proportional hedge bought NOTHING at belief 0.57, tau 42. Ticker tape at 16:44:18Z: NO ~39c with ~44 offered. Bot then paid 70c and 90.5c 11-14 s later | `hedge_prop fraction 0.0`; ticker tape |
- Recoverable part is a HYPOTHESIS: BNB up to ~$60 if 76 NO were fillable at 21c (depth not verified);
  NEAR ~$30 at the alarm-second book; BTC unknown (the alarm was never computed; hedges recover about a third).
- The same `--hedge-price` gate SAVED ~$29 once (NEAR 09-19 17:15 ET, refused 40c on a bet that won) and
  cost ~$9 once (HYPE 09-19 23:45, a 2 s delay, 37c -> 46c on 104 contracts, on a bet that won anyway).
- `--hedge-price` and A76 are removed (v-hedgelastweek, v-hedgefull), the pause fixed (A69/A73).
  **Still live and still able to block a hedge-equivalent buy: `both_sides` and the dump_guard's one-tick memory.**

### F4. The price-bearing entry gates blocked ~4,900 markets that ALL won -- and that number must not be believed.
Blocked = refused and never bought in that close. "If filled" = at the shown price, min(SIZE, shown depth),
fee included. **This is a hypothetical fill in the "an offer was sitting there" population, the one CLAUDE.md
rule 5 measured 31x too optimistic. It is an upper bound, not money.**
| gate | markets blocked (closes) | side won / lost | if filled | c/contract | one loss at size costs |
|---|---|---|---|---|---|
| price_ceiling (98c) | 1,039 (493) | 1,039 / 0 | +$368.80 | 0.73c | ~$110 |
| edge_floor | 2,689 (668) | 2,689 / 0 | +$353.33 | 0.19c | ~$114 |
| depth_floor | 1,041 (513) | 1,041 / 0 | +$2.00 | (under 1 contract offered) | -- |
| jump_against | 69 (60) | 69 / 0 | +$20.54 | 0.69c | ~$104 |
| against_thin | 32 (32) | 32 / 0 | +$18.58 | 1.01c | ~$96 |
| early_cheap (<90c, 45 s leg) | 8 (7) | 8 / 0 | +$42.56 | 11.9c | ~$83 |
| early_wide | 14 (7 priced) | 14 / 0 | +$10.42 | 4.8c | ~$74 |
| dump_guard | 7 (7) | 5 / **2** | +$43.66 | 9.7c | ~$82 |
| close_budget | 326 | 316 / **10** (3.1%) | no price recorded | | |
| market_attempts | 33 | 29 / **4** (12%) | -$21.59 (priced at another gate's price, 9 rows) | | |
| confidence | 553 | 496 / **57** (10.3%) | no price recorded | | |
- **The live counter-evidence.** Our own fills AT the ceiling (entry >= 98c, autosize era) made **-$48.15 on
  $4,953 staked** (93 markets, 90 closes, 2 losses, loss rate 2.2% against a ~2% break-even). The blocked
  population above had 0 losses in 1,039. Same gap as rule 5. **No price gate is shown to be pure cost.**
  Applying the live 2.2% to the 1,039 blocked markets (~49 contracts each), the ceiling SAVED ~$740; at the low
  end of that rate's range (0.26%, 2 of 93) it COST ~$240. Cannot tell which.
- `edge_floor` blocks 99.5-99.9c asks worth 0.18c/contract; five losses in 2,689 erase it. We have zero live
  fills up there, so its tail is unmeasurable. Keep.
- Gates that only stop ADDING to a held market (`early_once` 187, `rebuy_band` 92, `max_per_market` 20,
  `both_sides` 150) never block a new market; `both_sides` refused 5 opposite-side buys on held markets whose
  held side then lost (markets netted -$34.26, -$29.90, -$0.47, +$4.36, -$57.76) -- in 4 the hedge path had
  already bought insurance; in BNB 09-19 01:45 it had given up (F3).

### F5. Size is not tied to edge at all, and edge is the best single predictor of cents per contract we have.
Autosize era, 512 markets / 362 closes, first-signal `edge_c`:
| model edge | markets (closes) | losing | net | on staked | c/contract | contracts per market |
|---|---|---|---|---|---|---|
| 1-2c | 206 (180) | 4 (1.9%) | +$62.00 | $11,881 | **0.51c** | 59 |
| 2-3c | 144 (132) | 3 (2.1%) | +$77.52 | $8,541 | 0.88c | 61 |
| 3-5c | 82 (80) | 4 (4.9%) | +$69.07 | $5,351 | 1.24c | 68 |
| 5-10c | 58 (57) | 4 (6.9%) | +$108.86 | $3,812 | 2.66c | 71 |
| >=10c | 22 (22) | 0 | +$133.42 | $1,203 | **9.91c** | 61 |
- Contracts per market are flat (59-71) across edge and across model confidence (58-64). The only size
  modifiers are the ladder taper (91 fires, +$56.78), the last-10 s 1.5x (fired 3 times, +$17.05) and the
  removed 90-94c 1.5x boost (3 markets, -$44.76 whole-market).
- The thinnest bucket carries 39% of the dollars staked for 14% of the profit: 1-2c bets earned $62 on
  $11,881 while their 4 losing markets cost -$182.69. A winner there averages +$1.21, so one ~$97 full loss
  (SIZE ~100) erases ~80 winners.
- n per bucket is under the floor for losses (4, 3, 4, 4, 0 events). Direction is consistent; magnitude is not
  established.

### F6. How size is set, and how it grew against the bank.
`SIZE = floor(bank / (bank_brake x (max_per_close + max(extra_coin, late_extra)) x price_ceiling))`
= `floor(bank / (4.0 x 3 x 0.98)) = floor(bank / 11.76)`, re-read every 5 min when flat and at once after a
loss (`pinrun.size_for_bank`, `worst_close_cost`). The start record's `bank_divisor: 7.84` leaves out the extra
coin and is NOT the divisor in use (checked: bank $932.37 -> SIZE 79 = /11.76). Per market: `min(SIZE, depth the
taper accepts)`; 45 s leg x `early_frac` 1.0; last 10 s x1.5 on three conditions; per close 2 x SIZE + 1 x SIZE
extra (new coin or tau <= 15); open cap 3 x SIZE contracts; drawdown brake 20% of high-water; `--loss-cap 200`
per ET day; `--max-losses 2` losing closes per RUN.
| ET day | bank (autosize) | avg SIZE | contracts/close | $ at risk/close | as % of bank | worst close |
|---|---|---|---|---|---|---|
| 09-09..09-11 | (fixed size) | 20 | 20-25 | $18-23 | -- | -$17.17 |
| 09-12 | $196 | 21 | 25 | $24 | 12% | -$17.95 |
| 09-13 | $313 | 50 | 65 | $61 | 19% | 0 |
| 09-15 | $466 | 73 | 94 | $90 | 19% | 0 |
| 09-17 | $607 | 97 | 97 | $94 | 16% | -$15.79 |
| 09-19 | $1,013 | 103 | 126 | $125 | 12% | **-$108.86** |
| 09-21 | $953 | 79 | 84 | $83 | 9% | -$59.09 |
- Divisor history: brake 3.0 (/5.88, one bet = 17% of bank) 09-13 -> 4.08 (/8.0) 09-18 06:51Z -> 3.0 + extra
  coin (/8.82) 09-19 04:03Z -> 4.0 (/11.76, one bet = 8.3% of bank) 09-20 05:46Z.
- **The extra coin costs a third of every bet and is almost never used.** It is in the divisor, so SIZE is
  bank/11.76 instead of bank/7.84; since 09-19 04:03Z a third market appeared in 4 of 126 closes (+$23.87).
- **Worst single close vs the $584.46 put in:** -$108.86 (09-19 23:45 ET, XRP+HYPE false-alarm hedges) =
  **18.6%**; -$107.95 (BTC 09-19 16:00) = 18.5%. The largest possible close today is 3 x 79 x $0.98 = ~$232 =
  **40% of all money ever deposited**.
- **Are our biggest bets our worst?** Not clearly. Per market by contracts: 100-125 contracts -$67.18 (49
  markets, 3 losing, -1.29c) but >=125 +$53.98 (7) and 75-100 +$174.17 (162, +1.29c). Per close: 150-200
  contracts +$232.93 (49 closes), >=200 -$55.06 (10 closes, one loss). No monotone pattern at these n.
- **Partial fills are worse than full ones:** markets where we got 50-95% of SIZE lost 4 of 40 (10%, -$56.31,
  -2.92c) vs 11 of 365 (3.0%, +$453.91) when we got the full SIZE. And fills >= 2c BELOW the ask we saw lost
  4 of 15 (27%, -$110.52 net) vs ~2% otherwise. Both mean "the book was being pulled as we bought". n under floor.

### F7. The bot's own brakes halted it for ~2.4 hours in 14 days and missed ~10 closes (~$20-30, estimate).
| halt | downtime | cause |
|---|---|---|
| 09-09 00:45Z loss COUNT (3 fills on one NEAR market) | 62 min | pre-A8 (counted fills, not closes) |
| 09-12 01:59Z position cap (terminal then) | 24 min | fixed A14 |
| 09-20 03:45-04:41Z DRAWDOWN, 3 restarts each re-halting | 56 min, 3 closes | high-water mark $1,046.43 inflated by a fabricated $58.37 "withdrawal" (still open) |
| 09-08, 09-12, 09-14 (bogus $1M mark), 09-18 (open cap went terminal, A74) | 2-4 min each | |
- `--max-losses 2` has not fired since 09-09 and `--loss-cap` never halted: both reset per RUN and 09-19 had
  13 runs; 09-19 lost -$223 across them. The day cap (A79, 09-20) has not been reached since.
- The `loss bound` pause (09-19 07:30Z..~23Z) fired in 25 closes by my close mapping (VERSIONS counts 28 spans), each right after the first fill, and froze the
  rest of that close. Paused closes held 1.24 markets/close vs 1.53 after the fix -- ~7 second bets not made,
  worth ~$10-20 at the era's ~2c/contract (estimate). Its real cost was the $107.95 skipped hedge (F3).
  VERSIONS' "zero signals inside a pause, so it cost no trades" is circular -- a paused loop cannot signal.
- Missed-closes value = 10 closes x the era's ~$2.5-3 per close. A HYPOTHESIS (no fill exists for a close we skipped).

---

## 2. Refuted or not supported

- **"The 09-19..09-21 losses are because the bets got bigger."** Not supported against the four profitable days
  right before (same average SIZE 86-88); supported only against 09-12..09-14. The deposit-funded part of W2 netted +$3.
- **"Gate X is pure cost."** Every price-bearing gate's blocked set won 100% -- but the live fills at the same
  prices do not (F4). No gate can be called pure cost from this evidence.
- **"The biggest bets lose the most per contract."** No monotone pattern by size bucket (F6).
- **"The extra coin / 1.5x boosts drove W2 losses."** Extra coin: 4 closes, +$23.87. Late 1.5x: 3 markets, +$17.05.
  The 90-94c boost: 3 markets, -$44.76, already removed.
- **"depth_floor costs trades."** Confirms HANDOFF: blocked 1,041 markets worth +$2.00 if filled -- under one
  contract on offer.
- **"Brake halts cost us much."** ~2.4 h, ~10 closes in 14 days.

## 3. Could not measure, and why

- **What a blocked trade would really have done.** Only a live fill says that; every "if filled" number above
  is an upper bound (rule 5). The penny test or a paper arm synced after 2026-09-22 06:21Z are the only clean routes.
- **Refusals before 2026-09-14 00:35Z** -- not logged (A25 started then).
- **BTC 09-19 16:00 hedge value** -- the loss-bound pause skipped the hedge pass, so no belief was ever computed;
  rebuilding it needs the index replay (a hypothesis by the operator's rule).
- **BNB 09-19 01:45 depth at 21c** -- not re-read from the order book (would need orderbook_delta reconstruction,
  230 MB/hour; RAM budget).
- **Price of `confidence` and `close_budget` refusals** -- the record carries no price.
- **What the bot would have bought during halts/pauses** -- a stopped loop writes nothing.

## 4. Solutions worth testing

1. **45 s leg back to a third (`--early-frac 0.333`).** Blocks: two thirds of the 31-45 s contracts; the 21-30 s
   top-up still fills the rest where it earns +1.85c. It blocks NO hedge (it is a size, not a gate). Evidence:
   full size -$96.48 on $11,276 (117 closes); a third +$37.48 on $1,061 (32 closes, 0 losses -- luck not excluded).
   Scaling alone, the full-size leg at a third would have been ~-$32 plus whatever the top-ups made; the top-up
   leg's own outcome in those closes cannot be read from live fills. Validate: synced paper arm
   `early-frac 0.333` vs live from 06:21Z 09-22, head-to-head on the SAME markets (`h2h`, not `diff`), bar written
   before reading: 30 closes where either traded the 45 s leg, compare per-contract P&L incl. hedges.
2. **Size by edge.** e.g. half SIZE when edge < 2c, full at >= 3c. Blocks: nothing; halves exposure on ~40% of
   markets (206 of 512). On the autosize-era fills it gives up $122 of winnings to avoid $91 of losses -- net
   -$31, variance down. It is a lose-less trade, not a make-more one. Validate on a synced paper arm; it does
   not touch hedging.
3. **Take the extra coin out of the divisor, or remove the extra coin.** It costs a third of every bet (SIZE
   /11.76 vs /7.84) and was used in 4 of 126 closes. If kept for safety, say so; if removed, SIZE rises ~50% at
   the same bank -- which F2 says multiplies whatever the per-contract edge is, so only after (1).
4. **A dump-guard lockout: after a `dump_guard` refusal, refuse that SAME SIDE of that market for the rest of the
   close.** Blocks: 12 later winning fills (+$55) and 2 losers (NEAR 09-16 -$9.22, BNB 09-19 -$57.76) -> net
   +$12 over 14 days, n = 14 closes. Tiny and one-event-driven. It must not apply to the hedge path or the
   opposite side (ZEC 09-20 and ETH 09-21 flipped side after a dump and won).
5. **`both_sides` must yield to a collapsed position.** When the held side's belief is under the hedge line, an
   entry-path buy of the other side IS a hedge; today the guard refuses it (BNB 09-19 01:45, tau 8). Blocks
   nothing new; needs a self-test that `both_sides` cannot fire while a hedge is owed.
6. **A post-fill alarm.** A fill >= 2c below the ask we saw (4 of 15 lost) or a partial fill of a full SIZE
   order (4 of 40 lost) is evidence the book collapsed while we bought. Test as a hedge TRIGGER on paper only
   (never a gate on entries) -- n = 15 and 40, well under the floor.
7. **Fix the high-water mark before the drawdown brake halts again** (still open in CURRENT_STATE item 3).
   Cost so far: 56 min, 3 closes.
