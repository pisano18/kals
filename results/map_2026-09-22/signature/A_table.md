# A_table -- one row per live entry fill, with only what was knowable before the decision

**Finished 2026-09-23 ~01:2xZ (09-22 ~21:2x ET).** Read-only throughout; no
process touched, nothing written outside this file and my scratchpad. Collectors
verified alive after every job (`kalshi_collector.py` pid 105304 at 57 MB,
`crypto_feeds.py` pid 105352 at 56 MB). Free RAM 2.18 GB, free disk **23.6 GB**
-- above the 6 GB hard collection stop, but still falling ~3 GB a day.

## What the table is

**811 entry fills, 779 markets, 573 closes, 2026-09-08 -> 2026-09-23, 85 fields
a row.** JSONL (not in the repo):
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\signature\table\fills.jsonl`
Builders beside it: `build.py` (logs + ledger), `tape.py` (tape features),
`check.py` (the adversarial checks below).

Sources: the 128 live logs for every decision (`signal` paired 1:1 with its
`order`, plus `refused` for the fair trajectory, `hedge*` for the insurance);
**Kalshi's ledger for every dollar and every outcome**; the tape (`ticker`,
`trade`) on EXCHANGE timestamps only for what the market did. No replay, no
pinsim, no pindata anywhere in this table.

**20 of the 779 markets lost (2.57%), in 20 distinct closes.**
TRAIN (close <= 2026-09-20 ET): 697 markets, 509 closes, **17 losses**.
HOLDOUT (09-21 on): 82 markets, 64 closes, **3 losses**.

## Reconciliation, done before any claim was believed

- All **779 filled tickers are in the ledger**, one row each.
- Rebuilt by hand per market (entry legs + hedge legs + billed fees) it matches
  the ledger within 5c on **777 of 779**; total **$534.83 vs $533.61** (0.2%).
  The two misses: `KXBNB15M-26SEP191230-30` (-53c, hedge fee detail) and
  `KXBNB15M-26SEP190145-45` (-22c, that position was DUMPED, a sale my
  arithmetic does not model).
- **Ledger rows with no log row: 130, worth -$147.25** -- 39 WTI, 3 NATGAS,
  9 GOLD, 1 COPPER, 1 BTCD, 69 KXCRYPTOLEAD (other bots), **plus 8 crypto-15M
  markets (6 BTC, 1 SOL, 1 ETH) worth -$20.00 that the pin logs never recorded.**
- **Hand-check, the DOGE loss** (`KXDOGE15M-26SEP222245-45`): 2 NO at 93.4c and
  11 NO at 7.1c, 13 YES hedge at 98.008c average, billed fees 0.86 + 5.06 +
  0.70 + 1.07c -> **-$246.69 against Kalshi's -$246.73**. The hedge recovered
  25.9c gross, **24.1c net**.
- **Hand-check, a winner** (`KXBTC15M-26SEP221800-00`, NO at 93.1c, tau 29,
  +$5.71): recomputed the model's own fair from the raw 1/sec index
  (`cfbenchmarks_value`, BRTI, 32 of 32 locked prints, r = tau-1 = 28) ->
  **P(NO) = 0.998891 against the logged 0.99889**, spot identical to 4 decimals,
  and the settle from 60/60 prints (86197.40) below the strike (86211.92), so NO
  won exactly as the ledger says.

---

# FINDING 1 -- our side's price collapsing in the 2 seconds BEFORE we buy

**Claim.** When the ask on the side we are about to buy has fallen more than 3c
in the previous 2 seconds, **31 of 779 markets (4%) hold 9 of the 20 losses
(45%), lose 29% of the time, and are the only bucket in the whole table that is
net negative: -$213.45.**

| our ask, 2 s before entry | markets | closes | losses | loss rate | ledger $ | $/contract |
|---|---|---|---|---|---|---|
| **fell > 3c** | **31** | **30** | **9** | **29.0%** | **-213.45** | -0.139 |
| fell 1-3c | 38 | 38 | 0 | 0.00% | +13.06 | +0.007 |
| fell 0-1c | 54 | 52 | 0 | 0.00% | +75.29 | +0.029 |
| flat | 45 | 45 | 1 | 2.22% | +5.01 | +0.002 |
| rose 0-1c | 197 | 183 | 2 | 1.02% | +94.44 | +0.010 |
| rose 1-3c | 202 | 188 | 5 | 2.48% | +175.71 | +0.019 |
| rose > 3c | 184 | 180 | 2 | 1.09% | +356.56 | +0.038 |
| no tape (2 dead hours on 09-15) | 28 | 20 | 1 | 3.57% | +26.98 | +0.025 |

In the bucket we win 22 times for **+$53.81 in total** and lose 9 times for
**-$267.26**. Every one of the 31 had model confidence between 99.5% and 100%.

**Mechanism.** The offer is cheap *because the market has already repriced*, and
the model structurally cannot see it: at tau 20-45 the model's confidence is
carried by the locked settlement prints, which do not move when the spot does.
The pin edge assumes a cheap offer is a stale resting maker; in these 31 cases it
is a live seller who is ahead of us. Tonight's DOGE is the same disease one
second later -- there the collapse arrived *after* our fill, which is why DOGE is
caught by Finding 2 rather than this one.

**Dollar impact, next to the return that bought it.** Not entering these 31
would have added **+$213.45** to a book that made +$533.61 -- and would have
given up the +$53.81 of wins inside them. Over 15 days that is about **$14/day**.

**Artefact checks -- all four run, none of them killed it.**
1. *The 2 s window could be empty, so the "move" spans longer.* Refuted: the
   flagged rows have the same quote-gap profile as everything else (median
   from-quote age 2 s, p90 2 s, max 4 s; median 3 real prints inside the
   window). Restricting to windows with >= 2 real prints and a from-quote <= 3 s
   old: 30 markets, still 9 losses, still **-$204.2**.
2. *It could just be "cheap price", which we already knew was adversely
   selected.* **Refuted, and this is the most useful thing in the table** -- the
   flag separates INSIDE every price bucket, and cheap offers without a collapse
   are spotless:

   | price paid | ask dropped > 3c | did not |
   |---|---|---|
   | < 90c | n=9, 6 losses, **-$97.1** | n=30, **0 losses, +$178.4** |
   | 90-95c | n=12, 1 loss, -$30.2 | n=118, 4 losses, +$214.0 |
   | 95-97c | n=6, 0 losses, +$8.5 | n=155, 3 losses, +$143.8 |
   | >= 97c | n=4, 2 losses, **-$94.6** | n=445, 4 losses, +$210.8 |
3. *Our own order could be moving the price.* No: taking at the ask REMOVES the
   cheapest offer and pushes the price UP, and the window ends at our decision
   millisecond, before the send.
4. *Unit / side error.* The tape's insurance price was validated against the
   bot's own `hedge_quote` on the 22 rows that carry both: median difference
   **0.00c**, worst 3.7c. Our-side ask from the tape matches the bot's
   `ask_seen` to 0.1c median.

**Significance and MDE.** Base rate 2.57% predicts 0.80 losses in 31 markets;
9 observed, Poisson P(>=9) = **1.7e-07**, past the multiple-looks bar
(0.05/14 looks = 0.0036). Clusters: **30 closes -- exactly at the 30-close
floor**, no close counted twice. MDE: separating 29% from 2.6% at 80% power needs
~14 markets; we have 31.

**It survives the two cuts that have killed every earlier finding here.**
- Excluding all of 09-19 (the bug day): 28 markets, **7 of 16 losses,
  -$101.97**, while the other 678 markets made +$859.05.
- HOLDOUT (09-21 on, never looked at while building the feature): 5 of 82
  markets, **1 of the 3 losses, -$46.00**, against a holdout that made +$50.73
  in total. Small n, right direction.

---

# FINDING 2 -- a fill that comes in BETTER than the ask we saw

**Claim.** When the executed price is >= 3c better than the ask the bot saw
~200 ms earlier: **24 markets, 8 of the 20 losses, 33% loss rate, -$115.34.**
Monotone: 0c -> 1.55% and +$527; 3-6c -> 18%; 6-12c -> 29%; >= 12c -> 67%.

| improvement | markets | closes | losses | loss rate | ledger $ |
|---|---|---|---|---|---|
| 0c | 647 | 500 | 10 | 1.55% | +527.27 |
| 0-1c | 93 | 87 | 2 | 2.15% | +80.63 |
| 1-3c | 15 | 15 | 0 | 0.00% | +41.05 |
| 3-6c | 11 | 11 | 2 | 18.18% | **-73.62** |
| 6-12c | 7 | 7 | 2 | 28.57% | **-25.98** |
| >= 12c | 6 | 6 | 4 | 66.67% | **-15.74** |

**Mechanism.** The improvement is the market repricing *while our order is in
flight*. A NO limit at 98c that fills at 7.1c -- the DOGE 11-lot tonight -- means
the book flipped in those 175 ms. The improvement IS the bad news, delivered as a
price.

**This is NOT an entry gate.** It is only knowable after the send, so its only
use is as an immediate hedge trigger. Tonight's DOGE proves the timing: the bot
waited for its belief to cross 0.25 at tau 10 and paid 93.4c and 98.6c for
insurance that had cost 6.7c at tau 12.

**Artefact checks.** Prices are Kalshi's own (the ledger reconciles to 0.2% on
777/779). Not sweeping: `swept` is false in 0 of the 25 improved fills -- a sweep
pays UP. 24 distinct closes, no close twice. Poisson p ~ 1e-7.

---

# FINDING 3 -- the age of the offer we take

`level_age_ms`, knowable before the send:

| level age | markets | closes | losses | loss rate | ledger $ |
|---|---|---|---|---|---|
| < 50 ms | 113 | 105 | 1 | 0.88% | +151.59 |
| **50-150 ms** | **89** | **84** | **7** | **7.87%** | **-227.07** |
| 150-500 ms | 59 | 58 | 2 | 3.39% | +79.81 |
| 0.5-2 s | 45 | 43 | 0 | 0.00% | +105.60 |
| 2-60 s | 29 | 29 | 1 | 3.45% | +32.05 |
| > 60 s | 186 | 164 | 1 | 0.54% | +343.95 |
| not logged (old runs) | 258 | 201 | 8 | 3.10% | +47.68 |

Every big loss we have ever taken (-$107.95, -$66.34, -$61.75, -$59.09, -$34.26,
-$31.27, -$27.87) is in that one 100 ms band. An offer resting for a minute is
the safest thing we buy.

**Caveats first: the shape is NOT monotone** (under 50 ms is the second-cleanest
bucket), so I do not have the mechanism and will not invent one. Excluding 09-19:
73 markets, 4 losses (5.48%), **-$20.31** -- the loss concentration survives, the
big negative does not. Only 339 markets have an exact level age at all.

---

# FINDING 4 -- the market's own price of the flip, at entry, grades us

Opposite side's ask at the decision second, rebuilt from the tape (780 of 811
fills):

| insurance cost at entry | markets | losses | loss rate | ledger $ |
|---|---|---|---|---|
| < 2c | 45 | 0 | 0.00% | +63.91 |
| 2-5c | 372 | 2 | 0.54% | +209.17 |
| 5-8c | 183 | 5 | 2.73% | +158.24 |
| 8-12c | 85 | 4 | 4.71% | +90.36 |
| **>= 12c** | 66 | **8** | **12.12%** | **-15.04** |

Two more views of the same second, same direction: insurance RISING > 3c in the
2 s before entry -> 50 markets, 9 losses, 18.0%, -$158.71. 70-95% of the volume
in those 2 s buying the side AGAINST us -> 113 markets, 8 losses, 7.08%,
-$111.32.

---

# FINDING 5 -- a cheap hedge has never once been right

All 17 hedged markets, split on the insurance ASK at the alarm second (already in
the log, so available at the hedge decision):

| insurance ask at the alarm | hedges | saves | false alarms | hedge $ |
|---|---|---|---|---|
| < 0.30 (0.10-0.28) | 5 | **0** | **5** | **-41.72** |
| >= 0.30 (0.43-0.94) | 12 | 10 | 2 | +57.44 |

**"Do not hedge when insurance costs under 30c" would have returned $41.72 and
blocked zero saves**; the cheapest hedge that ever saved anything cost 43c, a 13c
margin. Mechanism: the alarm fires on the MODEL's belief crossing 0.25 while the
price is the MARKET's belief, and a 15c opposite side means the market says we
have already won. Fisher p = 0.0034, **n = 17, below the 30-close floor -- this
is suggestive, not proven**, and 2 of the 5 were fired by triggers no longer
deployed.

---

# The three flags together

| set | markets | losses | loss rate | ledger $ | $/contract |
|---|---|---|---|---|---|
| ANY of the three | 127 | **13 of 20** | 10.24% | **-234.82** | -0.033 |
| none of the three | 652 | 7 | 1.07% | **+768.43** | +0.025 |
| ANY, excluding 09-19 | 108 | 9 of 16 | 8.33% | +65.58 | +0.012 |
| none, excluding 09-19 | 598 | 7 | 1.17% | +691.50 | +0.027 |

They are largely independent (31 / 89 / 24 markets; pairwise overlap 5, 11, 3;
all three 2). **16% of the book holds two thirds of every loss.** Honest split:
*identification* survives dropping the bug day, the *negative dollars* of the
union do not -- only Finding 1 is still negative money ex-09-19.

# Refuted, or not supported

- **The model's own confidence does not rank its own losses.** 99.5-99.8% ->
  2.47% loss; 99.8-99.95% -> 2.37%; >= 99.95% -> 2.42%. Flat. (Consistent with
  AMENDMENT 19's calibration table.)
- **"Refused for confidence earlier in the same close" is not a warning**: 340
  markets with an earlier confidence refusal lost 2.6%, the 439 without lost
  2.5%. Tonight's DOGE had one, but it is not a signal.
- **The confidence swing since tau 45 is not a warning**: 0pt 2.33%, 0-2pt
  1.79%, 2-10pt 3.12%, 10-30pt 5.77% (n=52), >30pt 1.64%. No shape.
- **"The spot is on the wrong side and only the locked prints hold us up"**
  (`frac_locked` > 1, the DOGE signature): 34 markets, 3 losses, 8.8% against
  2.2% -- 4x, but Poisson p = 0.04, short of the multiple-looks bar, and the
  bucket still made +$15.97. Suggestive only.
- **Book age, index age, latency, coin, leg and sweeping** all separate weakly or
  not at all (book age <5 ms 3.55% vs 5-20 ms 1.67%; latency <120 ms 2.36%;
  no coin above 4.4%).
- **Cheap offers are NOT adversely selected by themselves.** Under 90c with no
  2 s collapse: 30 markets, **0 losses, +$178.4**. The earlier "chase cheap
  carefully" reading needs this condition added.

# Could not measure, and why

- **The fair trajectory is mostly absent by construction.** `conf_t45` exists for
  346 of 811 rows, `conf_t30` 432, `conf_t20` 145, `conf_t15` 165 -- because the
  bot enters at the *first* second it is allowed to (125 fills at tau 30, 82 at
  tau 45), so there is no earlier evaluation to read. The trajectory is only
  meaningful for late entries.
- **Insurance from the log covers 28 of 811 rows** (`hedge_quote` starts
  2026-09-22 11:52:44Z). The tape covers 780; 31 rows have no tape quote, 28 of
  them from two unreadable hours on 09-15 (`20260915T13`, `20260915T20` --
  EOFError and a zlib error in both `ticker` and `trade`).
- **Per-fill ledger money does not exist.** A hedged market is ONE ledger row, so
  each row carries the market's ledger dollars plus my own exact per-leg
  arithmetic; 32 of 811 fills share a market with another fill.
- **8 crypto-15M markets (-$20.00) have no log row at all**, so they are outside
  every rate above.

# Solutions worth testing, each with what it BLOCKS

1. **Do not take an offer whose price has fallen more than 3c in the last 2
   seconds (the entry gate).** Blocks 31 of 779 entries (4%), 9 of 20 losses,
   +$213.45 lifetime, giving up $53.81 of wins inside it. Validate on live fills: the bot
   already holds its own book history, so the feature costs nothing to compute
   and can be *logged before it gates* -- log it for ~300 closes, confirm the
   rate matches this table, then gate. **It blocks ENTRIES only. It must not
   look at, delay or condition a hedge.** Companion paper arm: `--drop-gate 3`.
2. **Treat a fill 3c better than the ask seen as a hedge trigger in its own
   right**, evaluated the moment the fill report lands, instead of waiting for
   the belief to cross 0.25. Blocks nothing -- it only makes a hedge EARLIER.
   Tonight it would have priced insurance at ~6.7c instead of 93.4c. Validate on
   the 24 flagged markets' live fills.
3. **Do not pay for insurance under 30c** (paper arm first, bar at 0.30, 13c
   below the cheapest save that ever worked). +$41.72 lifetime, 0 saves blocked
   in 17 hedges. **This one DOES block hedges** -- it is the only proposal here
   that touches the rule CURRENT_STATE says is untouchable, so it belongs in
   `pinrun --paper-live --hedge-min-ask 0.30` and nowhere near live until it has
   30+ hedged closes.
4. **Log `level_age_ms` and the 2 s price move on every refusal too**, not only
   on fills, so the 258 rows with no level age stop being unscoreable and the
   gate in (1) can be measured against what it would have skipped.
5. **Find the 8 unlogged crypto-15M markets (-$20.00).** A fill Kalshi knows
   about and our log does not is the same class of blindness as the invisible
   budget skip -- the ledger should be reconciled against the logs nightly.
