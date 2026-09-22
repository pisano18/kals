# C -- gate-winners: markets our entry gates refused that then won, and whether loosening is risk-neutral

**Status: COMPLETE (2026-09-22 ~17:00Z).** Read-only. Scripts and intermediate data in scratchpad
`missed/gate-winners/` (parse, outcomes, fills, bands, risk, gates, inwin, tapeoffer, replay, lockout).
Window "post-fix" = 2026-09-20 04:00Z (00:00 ET) .. 2026-09-22 ~16:20Z, about 2.5 days and ~220 watched closes.
Sources: money = Kalshi ledger (`pinledger.pnl`); decisions = all 126 `pinrun-live-*.jsonl`; outcomes of refused
markets = tape `market_lifecycle_v2` + fulltape + ledger (37,654 markets, 0 conflicts); what was OFFERED = tape
`ticker` (exchange `ts_ms`); what the MODEL said at a tape moment = `pinrun.fair` through `pinsim.TapeIndex`
(decision reproduction only -- validated on our 155 post-fix signals: median |fair diff| 0.000003, 141 of 155
within 0.001). Every risk number below is from OUR fills (785 fills, 758 markets, ledger +$503.78). n = closes.
At finish: kalshi_collector (105304) and crypto_feeds (105352) alive; 1.1 GB RAM free; 26.9 GB disk free.

---

## 1. Findings, ranked by dollars

### F1. No entry gate can be loosened without adding risk. Every "winner" they refused was priced where our own fills lose more than the price can carry.

Post-fix, deduped per (market, gate); "blocked" = never bought. Contracts = min(SIZE, touch size).
Value at a loss rate L = contracts x (1 - price - L - fee). Our fills at 97.5-98c (the nearest we have to the
refused prices) lose **5 of 283 closes = 1.8% [95% CI 0.6-4.1%]**.

| gate | blocked (closes) | our side won / lost | avg price | break-even loss rate | $ if never lost (tape) | $ at 0.6% | **$ at 1.8% (our fills)** |
|---|---|---|---|---|---|---|---|
| edge_floor | 856 (207) | 856 / 0 | 99.79c | 0.20% | +$106.25 | -$216.45 | **-$861.84** |
| price_ceiling 98c | 365 (161) | 365 / 0 | 99.21c | 0.73% | +$120.71 | +$22.15 | **-$174.96** |
| jump_against | 25 (24) | 25 / 0 | 99.11c | 0.83% | +$8.62 | +$2.41 | -$9.99 |
| against_thin | 15 (15) | 15 / 0 | 98.97c | 0.96% | +$8.64 | +$3.22 | -$7.62 |
| depth_floor | 310 (159) | 310 / 0 | 99.71c | 0.27% | +$0.32 (119 contracts offered in total) | | |
| staged_none | 7 (7) | 7 / 0 | 97.26c | -- | +$0.06 (under 1 contract left) | | |

- **edge_floor: clearly protecting.** Even at the best-case end of our fills' range (0.6%) it saves $216 in 2.5 days.
- **price_ceiling: protecting at our measured rate**, and at best worth ~$22 in 2.5 days if our loss rate were at
  the bottom of its range. 77% of its refusals were at 31-45 s. Loosening it would need a loss rate under 0.73%;
  our fills' rate falls toward that nowhere: by model confidence >= 99.99% it is 1 of 61 closes (1.6%); only
  "last 10 s" (0 of 71 closes, CI up to 5.1%) and "spot >= 2 sd of remaining move past the strike" (0 of 43, CI up to
  8.2%) are clean, and neither n can show a rate under 0.73%.
- The pattern across price bands says the same thing: our fills lose at 0.25x the market-implied rate at 90-93c,
  ~0.5x at 93-96c, **0.8x at 97-98c** (1.8% vs 2.2%). Our edge over the market shrinks as price rises; above 98c
  it is on course to be negative. (Pattern, not a test.)
- **Artefact check.** The tape's "all won" is the rule-5 population (an offer sitting there, not someone selling
  to us); 05 F4 already warned. Numbers here only use tape outcomes to count; every $ uses our loss rates.
- **Confidence:** high for edge_floor, moderate for price_ceiling (1.8% is 5 losing closes).

### F2. The confidence gate is the one that turns away most of the in-window deals -- and our own fills of that kind lost money.

Tape: 79 markets we never bought had our side offered at 90-98c (>= 1 contract) somewhere in the last 3-30 s.
All 79 won. Replaying the model at those 374 offer moments:

| what the model said at the offer moment | moments | markets (by best moment) |
|---|---|---|
| below 99.5% (confidence gate) | 353 (94%) | 71 |
| of which the model's own number was BELOW the ask | 213 of 353 | |
| passed every price gate | 18 | 8 (F3 explains 3; 5 are sub-second timing or an unfilled order) |
| against_thin / jump_against | 2 / 1 | -- |

Max model confidence per market at those moments: 99-99.5% 8, 98-99% 19, 95-98% 21, 90-95% 14, under 90% 7.
- **Risk side, our own fills of the same kind** (model < 99.5%, price >= 90c; pin 0.98 era 09-08..09-10 plus one
  hour on 09-13): **2 of 35 closes lost (5.7%), -5.43c a contract, ledger -$46.36.** Just above the line
  (99.5-99.75%, >= 90c): 5 of 269 (1.9%), +1.71c, ledger +$313.92. The gate sits where our fills turn from losing
  to winning (5.7% vs 1.9% is 2 vs 5 events -- not significant, but the direction is ours, not the tape's).
- All confidence-refused blocked markets post-fix: **21 of 211 went the other way (10%)** -- before any adverse
  selection on a fill.
- **Verdict: protecting.** 71 markets in 2.5 days is the biggest pool of "missed deals", and the only evidence
  on buying them is our own, and it lost.

### F3. A real bug: one early-leg refusal locks a market out of the ENTIRE close, including the 30-second window. 32 markets since 09-17; 12 later passed every gate at our price, all won. ~$16 missed at our own margins.

- **Mechanism (code, `research/pinrun.py` 11358-11359 vs 11404-11470).** `attempts_tk[(close, market)]` is
  incremented when the signal dict is built -- BEFORE the early-leg gates (`early_cheap`, `early_wide`,
  `early_dear`, `staged_none`, `price_band`) that `continue` without sending anything. The loop looks ~20 times a
  second, so three looks burn `MAX_ATTEMPTS_PER_MARKET = 3` in well under a second, and `market_attempts` then
  refuses that market for the rest of the close -- before the book is even read. The cap's own comment says it
  counts "orders SENT ... filled or not"; A49's comment says "Inside 30 s the full leg is unaffected." Both are
  violated.
- **Proof it is exactly this:** per-close gate counts (`close_summary.gates`, not deduped) show `staged_none: 3`
  then `market_attempts: 676` (09-20 07:15 ET), `staged_none: 3` / `market_attempts: 756` (05:15 ET),
  `early_cheap: 3` / `market_attempts: 490` (09-21 02:00 ET), `staged_none: 2`+... / `market_attempts: 413`.
  The 3 matches the cap exactly. 30 of the 32 locked markets had 0 or 1 real orders.
- **Also fires inside 30 s:** `staged_none` refuses when the TOUCH holds under 1 contract even though
  `depth_floor` just approved the deeper ladder (XRP 09-17 12:15 ET at tau 11, NEAR 09-19 01:30 at tau 9, ZEC 09-20
  13:30 at tau 10) -- and then locks the market too.
- **What was lost** (tape offers after the lockout, model replayed; n = 12 markets / 12 closes, 09-17 13:05Z..now):
  all 12 won. At our own <=30 s fills' margin for each price band: **+$15.65** (tape upper bound +$24.42), ~$3 a
  day. Post-fix alone: 4 markets (BNB 09-20 19:00 ET, BTC 05:15, HYPE 07:15, XRP 09-21 02:00). Examples: BTC 09-19
  16:45 ET -- 1,634 YES offered at 89c at tau 29.5, model 99.80%, 10c edge; HYPE 09-20 07:15 ET -- 68 at 98c, model
  99.99%.
- **Risk side:** a market released from the lockout still has to pass every normal gate at <= 30 s, so it is
  the same kind of trade the bot already takes: our <=30 s fills (since 09-10) lose 10 of 376 closes (2.7%) and
  make +2.44c a contract (+1.65 to +5.11c by 10-second band). It adds exposure of a kind we already carry; it does not add a riskier kind.
  One of the 32 locked markets went against the side we would have wanted (XRP 09-22 02:15 ET) -- the replay found
  no moment where the model would have bought it, so the fix would not have bought it either.
- **Confidence:** high on the mechanism (code + exact counts); the $ is small and rests on 12 markets.

### F4. The other gates are clearly protecting, on our own fills of the same kind.

| gate | blocked post-fix | our own fills of that kind (all eras since 09-10 unless stated) |
|---|---|---|
| dump_guard (ask > 15c below model) | 2 (1 won, 1 lost) | **7 of 16 closes lost (44%), -13.97c/contract, ledger -$91.77** |
| early_cheap (< 90c at 31-45 s) | 4 (all won, 88c) | **2 of 2 closes lost**, -19.87c/contract (09-17..09-18, before the 90c floor) |
| against_thin (spot >= 1 one-second move past strike, edge < 2c) | 15 (all won, 99c) | 1 of 5 lost, -42.25c/contract, ledger -$32.45 |
| jump_against | 25 (all won, 99.1c; only 1 was <= 98c) | not measurable from our fills (moves not logged before the gate); map 11 G6 found the pre-gate losers |

### F5. The capacity gates blocked ZERO new markets post-fix.

`close_budget` 31, `max_per_market` 8, `rebuy_band` 52, `early_once` 74, `market_attempts` (other than F3) --
every one was on a market we already held. Since v-safety1 (11:52:44Z, 18 closes) no refusal of any kind had
`budget_left <= 0`. Loosening these means buying MORE of an outcome we already hold -- more risk by definition.

---

## 2. Refuted or not supported

- **"The gates are throwing away winners."** On the tape, yes (1,571 blocked market-gate pairs post-fix at >= 98c, 0 lost).
  On our fills, those prices lose money at our loss rate (F1). Same 31x trap as rule 5.
- **"The close budget is why the <= 30 s window buys less" (B5's budget hypothesis).** Post-fix it refused no new
  market, and since v-safety1 no refusal had budget left <= 0. Not the gates, at least by these logs (feeds B5).
- **"Gates hide in-window deals at our price."** Tape + model replay: 79 such markets in 2.5 days; 71 were the
  model below 99.5% (the gate working), 3 were the F3 bug, 5 were sub-second timing or an unfilled order.
- **"Stale-data gates cost trades."** 269 blocked markets post-fix, but 120 of the 147 `book_stale` refusals (14 of
  29 closes) and 44 of the 75 `index_stale` refusals (5 of 9 closes) sit inside the 09-22 00:50-05:38Z Kalshi
  connection outage; the rest are 1-3 markets in scattered closes. Not a gate problem.

## 3. Could not measure, and why

- **Our loss rate above 98c.** We have no fills there since 09-09 03:52Z. Only a live or penny fill says it.
- **The price of `confidence` / `close_budget` refusals** -- not logged; recovered here only via tape + replay for
  the in-window subset.
- **Which gate refused a market later in the same close** -- the log keeps the first refusal per (market, gate);
  `close_summary.gates` has counts but no market or price.
- **jump_against's risk on our fills** -- recent moves were not logged before the gate existed.

## 4. Candidate ways to grab missed deals without added risk

1. **Fix the phantom-attempt lockout (F3). The only candidate that passes.** Count an attempt only when an order
   is actually SENT (move the two increments at `pinrun.py` 11358-11359 to just before the order goes out), and
   let `staged_none` use the same deeper-ladder reach `depth_floor` already approved. Size: ~12 markets / 5 days,
   **+$15.65 at our own margins (~$3 a day), tape bound $24.42.** Risk evidence: released markets still pass every
   gate; our <= 30 s fills of that kind lose ~2.4% and earn +1.65-5.11c. **Blocks: nothing** -- it removes a
   refusal; the hedge path never touches `attempts_tk`. The runaway guard (160 orders into one market) still holds,
   because real orders are still counted. Needs a self-test that 3 early-gate refusals do NOT set
   `market_attempts`, and that 3 real sends still do. It changes trading, so under the FREEZE it is the
   operator's call (it is a bug against the code's own stated intent, which the FREEZE allows).
   Validate: after deploy, count `market_attempts` refusals on markets with fewer than 3 orders (must be 0),
   and main-window fills that follow an early-gate refusal.
2. **Raise price_ceiling only in the last 10 s (our cleanest band, 0 of 71 losing closes): not worth it.**
   Measured size: 13 blocked markets / 690 contracts in 2.5 days, **at most +$5.52 if it never lost, -$6.90 at our
   1.8%**; one loss at SIZE costs ~$78. Proving a rate under the 0.73% it needs would take ~400 clean closes. The
   "spot >= 2 sd past the strike" version cannot be sized from the log (price_ceiling records carry no spot).
   Paper arm only, if a slot is spare; bar written first; the arm must show the flag fired.
3. **Do NOT loosen** edge_floor, confidence, dump_guard, early_cheap, against_thin: our own fills of each kind
   lost money (F1, F2, F4). Do not loosen the capacity gates: every refusal was on a market already held (F5).

Side lead for "identify better" (HYPOTHESIS, found while building the risk table, fails the multiple-looks bar):
our fills with spot >= 1.5 sd of remaining move past the strike lost 1 of 125 closes vs 15 of 423 below it
(one-sided p 0.09); at 31-45 s, 0 of 38 vs 6 of 136 (ledger +$72.34 vs -$124.72). No series drives it. It is the
sigma-scaled version map 11 G5 asked for; feed it to B1's early-leg decision as a pre-registered paper test, never
as a gate on a hedge.
