# 02 edge-calibration -- is the model right as often as it says, on OUR fills?

Status: COMPLETE (2026-09-22). Investigator 02. Read-only; nothing started, stopped or edited
outside this file and the scratchpad.

**Sources.** Every real fill in `results/pinrun-live-*.jsonl`: **773 fills, 747 markets,
547 closes, 36,053 contracts, 2026-09-08 07:59Z .. 2026-09-22 06:29Z.** Each fill joined to
the `signal` record that fired it (same run file, same ticker, <=5 s; 773 of 773 matched).
Model confidence = `fair` for a YES buy, `1 - fair` for a NO buy; `fair` is `pinrun.fair()`
= Phi(z) (`honest_conf` false in every live start record). Outcome = Kalshi's own
`market_result` in `results/kalshi_ledger.json`: 773 of 773 found, **0 disagreements** with
the bot's `settled` records, and **767 of 767 agree** with an outcome rebuilt from the raw
index. "Entry $" = the buy alone, no hedge. "Ledger $" = Kalshi's net for the market,
hedge included (a market counted once). "Market expected" = sum over markets of
(1 - ask we saw) -- how many losses the price we paid implied.
Scripts: scratchpad `map/02/` (`fills.py`, `calib.py`, `calib2.py`, `vsmkt.py`, `who.py`,
`idxcal.py`, `idxan.py`, `idxera.py`, `validate.py`, `align.py`).

---

## 1. Findings, ranked by dollars

### F1. The 45-second leg has no edge over the price: we lose there exactly as often as the price we pay says we will. The <=30 s window loses half as often as its price says. (-$59 vs +$544)

**Claim.** Inside the last 30 s our fills lose about half as often as the market price
implies; at 31-45 s they lose exactly as often as the price implies, so every contract
there pays the fee (and the sweep) for nothing.

**Evidence (live fills, per market; ledger outcomes):**

| window | markets | closes | lost | market expected | lost / market-expected | P(this few, if market right) | model expected | entry $ | ledger $ |
|---|---|---|---|---|---|---|---|---|---|
| main leg, tau <= 30 s | 545 | 427 | 13 | 24.7 | **0.53** | 0.008 | 1.64 | +510.06 | **+543.98** |
| 45 s leg, tau 31-45 s | 202 | 149 | 6 | 5.8 | **1.03** | 0.64 | 0.49 | -13.88 | **-59.00** |

Dose-response by seconds left (lost / market-expected): **0-10 s 0.00** (0 of 5.2 expected,
80 markets), **11-20 s 0.49** (3 of 6.2), **21-30 s 0.75** (10 of 13.3), **31-45 s 1.03**
(6 of 5.8). Losses in tau <= 20 vs > 20, conditional test: P = 0.039. <=30 vs >30: P = 0.14.

It is not a price effect: split by the ask we saw, the main leg beats the market at both
<97c (10 lost vs 18.6 expected) and >=97c (3 vs 6.1, +$167 ledger); the 45 s leg does not at
either (<97c 2 vs 2.4; >=97c 4 vs 3.4, **-$68.86 ledger on 149 markets**). It is not an era
effect: the 45 s leg's ratio is 1.03 before 09-19 and 1.04 after.

**Mechanism.** The settlement is the mean of 60 one-second prints. Inside 30 s, most of those
prints are already recorded and the model counts them exactly; the market price does not fully
absorb that, which is the whole edge (CLAUDE.md "Settlement model"). At 31-45 s none or few of
the 60 prints are locked, the model is a plain random-walk forecast off a 300 s volatility,
and the market -- which sees the constituent exchanges the index is built from -- knows as
much or more. The index alone (below, F3) shows the model is no WORSE at 31-46 s than at
<=30 s; what changes is that the market stops being beatable.

**Dollars.** Since the leg went live (09-17 13:05Z): -$59.00 ledger / -$13.88 entry over 202
markets and 12,496 contracts (35% of all contracts ever bought, **66% of contracts since
09-19**). Over the same span the <=30 s window made **+$117.67 ledger on 89 markets** (2 lost
vs 3.6 expected). From 09-19 on, the 45 s leg is
-$126.70 ledger on 129 markets; the <=30 s leg is +$34.62 on 60.

**Also observed, not proven:** main-window fills fell from a median ~45 markets/ET day
(09-08..09-16: 36, 39, 45, 51, 92, 49, 61, 36, 45) to 20-28/day once the 45 s leg ran
(09-17..09-21: 25, 23, 28, 20, 20), while the leg took 31-52/day. With `early_frac 1.0` the
leg buys full size, so the <=30 s top-up has nothing left in that market, and it spends the
close budget. That is crowd-out by construction, but I did not separate it from a fall in
supply (the gate-audit refusal log is de-duplicated, so it cannot count missed moments).

**Confidence.** Main-leg edge over market: solid (P = 0.008; 427 closes). The 45 s leg's
ratio of ~1.0: 149 closes, 6 losses -- it cannot rule out the main leg's 0.53 (P = 0.09), but
the dose-response points the same way and the dollars are negative either way.

**Artefact checks.** (a) "market expected" uses the ASK, which understates the market's own
loss estimate by half the spread -- so it favours the market, not us; the paid-price version
gives 32.7 total vs 30.5, same story. (b) Leg assignment is the `leg` field the bot logged.
(c) One fill per market used for the market's decision (the first); 25 markets had more than one fill.
(d) Losing closes: 19 of 547, never two losing coins in one close -- the losses are not one
correlated event counted many times.

---

### F2. The model says we lose 0.28% of markets; we lose 2.54% -- 9x. Its confidence carries no information about which of our fills lose.

**Evidence.** 19 losing markets of 747 (19 losing closes of 547). The model's own expected
count is **2.1** (P of 19+ if the model were right: 2e-12). The market price expected 30.5.
95% interval on our rate 1.5-5.4%. Average price paid incl. fee 96.07c -> break-even 3.93%.

| model said | markets | closes | lost | our loss rate | model's loss rate | off by | avg price+fee | c/contract | ledger $ |
|---|---|---|---|---|---|---|---|---|---|
| >= 99.9% | 235 | 214 | 6 | 2.55% | 0.029% | 88x | 95.72c | +1.53c | +63.81 |
| 99.75-99.9% | 160 | 152 | 4 | 2.50% | 0.180% | 14x | 96.22c | +1.43c | +119.37 |
| 99.5-99.75% | 322 | 273 | 8 | 2.48% | 0.384% | 6x | 96.30c | +1.44c | +303.34 |
| 99-99.5% (pre-09-10) | 7 | 7 | 0 | 0% | 0.72% | -- | 90.65c | +9.35c | +11.92 |
| 98-99% (pre-09-10) | 33 | 31 | 2 | 6.06% | 1.50% | 4x | 95.44c | -6.58c | -47.62 |

**The loss rate is flat at ~2.5% whether the model says 99.5% or 99.99%.** Ranking our 747
markets by how likely each was to lose: model confidence AUC **0.53** (a coin flip), the ask
we saw 0.62, the price we actually paid 0.73. Log-loss: the market beats the model in every
price band except 90-94c.

**Dollars.** Not a bleed on its own -- the bot does not use the model's confidence for its
expected-value test (it uses `MEASURED_FLIP = 0.009`, itself stale: our rate is 2.8x that).
What it costs is **identification**: any rule that trusts "more confident = safer" buys
nothing. Raising `--pin` would cut trades at an unchanged loss rate.

**Mechanism.** Two parts, split using the raw index (F3): about half is the model's own
too-thin tail (the index alone says 99.5-99.9% claims fail ~1.2-1.3% of the time), and about
half is WHO SELLS TO US -- the fills we get at 90-98c when the model is sure are a worse
population than the model's average moment (2.5% vs ~1.3%). At >=99.9% the gap is widest:
the index alone fails 0.059% of the time, our fills 2.55% (43x). When the model is ~certain
and someone still sells at 95c, the seller is right far more often than the model allows
(we still win 97.5% of those -- the price, not the model, was the better guide).

---

### F3. INDEX ONLY (pincalib method, no book, no replay): the model did NOT get worse after 09-19.

`research/pincalib.py`'s functions (`sigma_at`, `settle_of`, `norm_cdf`, `var_factor`) were
run day-by-day over the raw `cfbenchmarks_value` tape, 2026-09-08 .. 09-22, on the REAL strikes
(previous settle, rounded to the market's digits): 501,552 (market, second) cells, 11,664
markets, 1,296 closes, tau 4-46 s. `pincalib.py --selftest`: 35 checks OK. I did not run its
`main()` (it loads the whole index at once -- over the 500 MB cap -- and writes
`results/RESULTS_calib.md`). **Validated against our fills:** outcome 767/767, strike
756/767, and the rebuilt `fair` matches the logged `fair` at a one-second offset (live tau T
= rebuilt tau T-1) with median logit difference 0.001.

| model says | cells | markets | losing markets | fails (per second) | model says it fails | off by |
|---|---|---|---|---|---|---|
| >= 99.9% | 455,447 | 11,628 | 29 | 0.059% | 0.001% | 65x |
| 99.75-99.9% | 4,241 | 2,041 | 19 | 1.155% | 0.165% | 7.0x |
| 99.5-99.75% | 3,422 | 1,787 | 31 | 1.344% | 0.362% | 3.7x |
| 99-99.5% | 3,692 | 1,702 | 31 | 1.679% | 0.721% | 2.3x |

This agrees with the 09-13 `RESULTS_calib.md` (99.5% -> 1.67%, 99.85% -> 1.21%).
By era, cells at >= 99.5%: before 09-19 0.053% (<=30 s) / 0.162% (31-46 s); from 09-19 0.031% /
0.049%. At 99.5-99.9%: 1.18% before, 1.47% after (6 losing markets after -- not a change).
**So the worse live result after 09-19 came from what we bought, not from the model.**
Caution: the per-second cells are heavily clustered (thousands of seconds per close); the
"losing markets" column is the honest count.

---

### F4. 09-19 onward went from +2.42c to -0.23c a contract, and the edge over the price went from 0.54 to 0.95.

| era | markets | closes | lost | market expected | lost / market-expected | avg price+fee | c/contract | entry $ | ledger $ |
|---|---|---|---|---|---|---|---|---|---|
| before 09-19 | 558 | 413 | 13 | 24.2 | 0.54 | 95.56c | +2.42c | +529.31 | +577.06 |
| 09-19 onward | 189 | 134 | 6 | 6.3 | 0.95 | 96.87c | -0.23c | -33.12 | -92.08 |

Decomposition of the -2.65c: about -1.3c from paying more (break-even 4.44% -> 3.13%) and
-1.3c from a higher contract-weighted loss rate (2.0% -> 3.4%). The loss-rate part is NOT
significant on its own (6 losses; P = 0.13 against the earlier ratio). What changed is the
MIX: the 45 s leg went from 15% to **66% of contracts**, contracts per fill 38 -> 70, and
contracts at >= 97.5c from 46% to 60%. Within the <=30 s window after 09-19: 60 markets, 2
lost vs 2.5 expected, +$34.62 ledger -- too few to say it changed.

---

### F5. A fill far BELOW the ask we saw is often a loser -- small dollars, weak n.

Paid >5c less than the ask we saw: **6 of 15 markets lost (40%)**, entry -$67.33, ledger
-$32.51 (hedges recovered some). Paid the seen price or more: 10 of 632 lost (1.6%). 1-5c
better: 1 of 24. Mechanism: an IOC fills at the resting price, so a fill 10-87c below the
ask we saw means someone dumped our side in the ~100 ms between our look and our order --
the market moved against us and we were its buyer. Visible the instant the fill returns.
**Hypothesis only:** 15 markets / 14 closes, below the 30-close floor, and the 5c cut is one
of many slices I looked at (see multiple-looks note below). 9 of the 15 won, some big (+$15).

---

## 2. Refuted or not supported

- **"More confident = safer."** Refuted on our fills: 2.55% / 2.50% / 2.48% loss at
  >=99.9% / 99.75-99.9% / 99.5-99.75%. A higher `--pin` would cut volume and not losses.
- **"The model got worse after 09-19."** Not supported by the index (F3).
- **"Bigger model-vs-market gap = danger" (the coin race lesson).** Only at the extreme. By
  gap at the ask we saw: <1c 0/15, 1-2c 3.1%, 2-3c 1.2%, 3-5c 3.9%, 5-10c 2.8%, **10c+ 10.0%
  (4/40)**. Flat from 1c to 10c. Even the 10c+ bucket made money (+$105 entry, +$67 ledger)
  because those contracts are cheap. The money-LOSING gap bucket is the THINNEST one:
  1-2c, 3.1% lost at 97.6c average -> -0.62c/contract, **-$112.67 ledger** on 196 markets.
- **"Expensive fills (>=97.5c) lose money."** Not on realised: 5 of 376 lost (1.3%), +$185
  entry. The loss rate falls as the price rises, roughly as the market says. At a flat 2.54%
  they would be -$97 -- but the rate is not flat. Only the 98-99c band is negative (-$17 to
  -$34, 2 losses in 140) and 2 losses cannot separate it from zero.
- **Coin.** No coin differs from the market beyond noise (every P > 0.1 across 9 coins).
  BNB (4 of 90, ratio 1.01) and NEAR (2 of 57, 1.04, -$50) are the worst.
- **Late boost / extra coin.** 3 late-boost fills (0 lost, +$17) and 6 extra-coin fills
  (0 lost, +$14.64): too few to judge. The 4 band-boost fills include the 09-19 BNB loss
  (-$44.76 ledger).

## 3. Could not measure, and why

- **Crowd-out by the 45 s leg** (F1) -- the refusal log is de-duplicated per (close, market,
  gate), so it cannot count moments the <=30 s window lost; separating it from a supply fall
  needs the book at <=30 s for markets the leg had already bought.
- **Any paper-arm comparison.** Arms match live only from 2026-09-22 06:21Z -- too recent.
- **pincalib's `main()` itself** -- memory cap and it writes into `results/`. The same
  functions were run streamed instead (F3), with its self-test green.
- **Calibration of the hedge's `belief`** -- out of scope here (investigator on hedging);
  note the 45 s leg's hedges cost $45 net (entry -$13.88 vs ledger -$59.00).

**Power.** 547 closes, 19 losing. Overall rate interval 1.5-5.4%. Between two groups of ~190
and ~560 markets, the smallest loss-rate difference detectable at 80% power is **~3.7
percentage points** -- we cannot tell 2.3% from 5% by era. A 200-market bucket against its
break-even: ~+/-3 points. Only the 9x model gap (P 2e-12) survives a strict multiple-looks
correction (I looked at ~50 cells; Bonferroni threshold 0.001). The main-leg-vs-market
result (P 0.008) and the tau dose-response (P 0.039) do not survive it on their own; they
stand because the tau direction was predicted by the settlement mechanism before looking.

## 4. Solutions worth testing

1. **Shrink or stop the 45 s leg** (`--early-frac` back to 0.333, or `--early-tau-max 30`).
   Blocks: buys at 31-45 s only. Cannot block a hedge (hedges run on their own path). Might
   free close budget for the <=30 s window. Validate on LIVE fills: pre-register "the 45 s
   leg stays off unless ... " -- or, if kept small, re-read its lost / market-expected
   ratio after 30 more closes; keep it only if the ratio is below ~0.8. At its fill rate
   (~40 markets/day) that is under a week. `arm-early-off` can show the <=30 s volume effect
   from 2026-09-22 06:21Z on, but not the loss rate (paper fills are not our population).
2. **Replace "model confidence" with "edge over the price, by seconds left" in any
   gating/size decision.** The live-measured ratio is ~0 at 0-10 s, ~0.5 at 11-20 s, ~0.75 at
   21-30 s, ~1.0 at 31-45 s. Concretely: size up late (0-20 s), size down or skip at 31-45 s.
   Blocks: nothing new at 0-20 s; early buys. Validation: the same ratio, re-read on live
   fills, per tau band; no replay can supply it.
3. **Do NOT raise `--pin`** (F2: no effect on loss rate) and **do NOT update
   `MEASURED_FLIP` to 2.5% bluntly** -- it would refuse everything above ~97.3c, which on
   the main leg has been profitable (+$167 ledger at >=97c). If it changes, make it
   tau-dependent.
4. **Hypothesis for the hedge owner: a post-fill "dumped on" trigger** -- paid >5c below the
   ask we saw -> check hedge immediately (F5, 6 of 15 lost). It adds a hedge; it blocks
   nothing. Needs ~30 such fills before it can be judged; 9 of the 15 were winners, so
   hedging all of them costs real money on false alarms.
