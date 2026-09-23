# D_plan -- what actually ships, what it costs, and the bar it must clear

**Written 2026-09-23 ~03:0xZ (09-22 ~23:0x ET).** Read-only throughout; no
process started, stopped or signalled. Nothing written outside this file and
`...\scratchpad\signature\design\`. Collectors verified alive after every job:
`kalshi_collector.py` pid 105304 at 47 MB, `crypto_feeds.py` pid 105352 at
38 MB. Free RAM 3.17 GB, peak python footprint ~70 MB, **free disk 22 GB**
(above the 6 GB hard collection stop, still falling ~3 GB/day).

My own code, written from scratch, importing only `pinledger` and `pinrun`'s
own `hedge_vwap`: `...\scratchpad\signature\design\` -- `pickoff.py`,
`ownlook.py`, `doubt.py`, `slip.py`. No tape, no replay, no pinsim, no
quote anchor anywhere in this report. Every number below comes from the bot's
own log records and Kalshi's settlements.

---

## 0. The answer to the operator's question, first

**Is there an early warning the bot is not looking at, or is a thin-cushion
loss like tonight's the unavoidable cost of the strategy?**

Tonight's DOGE loss had **no warning that existed before we bought.** The
four big "warning" gates the map found were all measuring the loss itself
through a broken clock (C_holdout section 1), and at the true pre-send instant
they catch nothing. So for that class: **yes, it is the cost of the strategy.**

But the question has a second half nobody asked, and the answer there is
worth money:

1. **There IS a signal, and it points the other way.** The markets where the
   bot's own model was *unsure of our side earlier in the same close* are our
   best population -- 66 markets, 62 closes, **0 money-losers, +$2.95 a market
   against +$0.70 book-wide.** Late-arriving confidence is a quality signal,
   not a warning. That is rule R1 below.

2. **The bot already knows it was picked off, ~107 ms after the fact, and does
   nothing with it.** When the fill comes back cheaper than the ask it decided
   on, we were the counterparty to a collapse: 14 markets, 13 closes, **5 of
   the 20 money losses, -$117.62**, against +$1.14 a market everywhere else.
   It cannot gate an entry. It can add a protective action. That is R2.

3. **The reason every "was there an earlier sign?" question in this map came
   back underpowered is an instrumentation defect, not an absence of signs.**
   The bot evaluates a close **5,508 times** (median, `close_summary.looks`)
   and writes a **median of 1 refusal record per market** -- because `_gate()`
   de-duplicates on `(close_s, ticker, gate)` (pinrun.py:10412-10416). The
   entire visible history of a market before we buy it is 1-4 numbers, and each
   is the *first* firing of a distinct gate, not a sample of a trajectory.
   Every overlay the operator asked for was run against that. R4 fixes it.

**And one mechanism, named but not established (n = 2), that is the real shape
of tonight's loss:** `net_edge` grows as the market reprices against us,
because `fair` has not moved. Section 5.

---

## 1. R1 -- SIZE UP when the model doubted our side earlier. SHIP AS A PAPER ARM.

### The rule

`traj_min_conf_ge5s` = the lowest fair value the bot's own model put on the
side we eventually bought, at any logged evaluation at least 5 s earlier in the
same close. **When it is below 0.50, multiply the entry size by 1.5.** Unknown
(no earlier reading) = 1.0x. Never touches a hedge; it only raises entry size.

### My own rebuild -- a third independent one, and it reproduces

`doubt.py`, full live history, money from Kalshi's ledger, side taken from the
entry `signal` record (**not** the order record -- `want` was only added there
by AMENDMENT 72 and using it silently cuts the sample from 784 markets to 163).

| bucket | mkts | closes | money-losers | ledger $ | $/mkt |
|---|---|---|---|---|---|
| every market with a fill Kalshi settled | 784 | 577 | 26 | +546.13 | +0.70 |
| **doubt < 0.50** | **66** | **62** | **0** | **+194.80** | **+2.95** |
| doubt 0.50-0.97 | 173 | 150 | 5 | +185.81 | +1.07 |
| already >= 0.97 | 50 | 50 | 5 | -35.18 | -0.70 |
| no reading >= 5 s earlier | 481 | 378 | 16 | +198.84 | +0.41 |

B_trajectory and C_holdout got 68 markets / 64 closes / 0 losses / +$200.58 /
+$2.95 a market. I get 66 / 62 / 0 / +$194.80 / **+$2.95**. Three independent
implementations, same answer to the cent per market.

**62 closes clears the project's 30-close floor.** That was never in doubt and
is worth saying, because most of this map's candidates did not.

### The two objections, and what I did to them

**(a) The p-value, and it is still the weak point.** My own within-day
permutation on dollars per market (20k draws, day composition held fixed, so
the autosize and calendar drift cannot produce it): **p = 0.00015** against the
corrected multiple-looks bar of 0.05/441 = **1.13e-4**. That is a marginal
fail, not a pass. Leave-one-ET-day-out, my own run:

| drop | mkts | $/mkt | p | vs the bar |
|---|---|---|---|---|
| all days | 66 | +2.95 | 0.00015 | marginal fail |
| 09-17 | 61 | **+2.72** | 0.00110 | fails 10x |
| 09-14 | 47 | **+2.96** | 0.00060 | fails 5x |
| 09-18 | 61 | **+3.01** | 0.00030 | fails 3x |
| 09-23 | 65 | **+2.89** | 0.00025 | fails 2x |

**The money is rock-stable -- it never drops below +$2.72 a market on any
leave-one-day-out. The significance is not.** That is the verdict, and it is
exactly why this goes to a paper arm and a live bar rather than straight to 2x.

**(b) The slippage, which C_holdout said "needs orders we never placed". IT
DOES NOT, and I priced it.** Every `signal` record already carries `ladder` --
up to `LADDER_LEVELS` of real resting depth in our side's price terms, built at
pinrun.py:12388-12396 on every signal, live and paper. Walking it with
pinrun's own tested `hedge_vwap()`, capped at the 98c `PRICE_CEILING` (the
highest price the bot may actually pay), over all 617 signals that logged a
ladder:

| | 1.0x | 1.25x | 1.5x | 2.0x |
|---|---|---|---|---|
| median VWAP | 97.20c | +0.02c | **+0.03c** | +0.05c |
| p90 penalty | -- | -- | **+0.167c** | +0.300c |
| p99 / max penalty | -- | -- | +0.648c / **+1.441c** | +2.204c |

**A 1.5x order costs a median 3 hundredths of a cent a contract more**, against
the rule's +4.50 c/contract edge -- under 1% of the edge at the median, under
4% at p90. On the doubt-flagged markets alone it is the same: median +0.03c,
worst +0.57c.

The honest caveat: the ladder under the ceiling **held 2x on 445 of 617
signals (72%)**. On the other 28% the extra contracts simply *do not fill* --
a bigger order there is a partial fill, not a worse price. And this prices the
book **at the decision**; whether that depth survives the ~107 ms flight is
R2's question, and a 1.5x order carries 1.5x of that risk. On the record the
two populations never overlap (0 of the 66 doubt markets is a pickoff market).

**So C_holdout's one unpriced cost is now priced and it is small. The
slippage objection to R1 is dead.** What is left is the p-value.

### What is missing in the code -- I checked `pinrun.py`'s argparse

`python research/pinrun.py --help` has `--band-mult LO HI MULT`, `--late-mult`,
`--flip-mult`, `--rebuy-mult`, `--extra-coin`, `--late-extra`. **There is no
flag for this and no in-process trajectory state.** Precisely what is missing:

1. **`--doubt-mult X` and `--doubt-under F`** (argparse, near the
   `--band-mult` block at pinrun.py:13283). Defaults `1.0` and `0.50`, i.e.
   OFF, so the declared default is the shipped behaviour -- the A55 rule.
2. **`DOUBT_MULT` / `DOUBT_UNDER` added to the `_FLAG_GLOBALS` tuple
   (pinrun.py:3717) and to the `start`-record flag list (pinrun.py:3426)**, or
   the Lab cannot tell one doubt arm from another. That is the A47/A48/A49
   blank-tab lesson and the self-test at 4898 enforces the pattern.
3. **A per-close trajectory dict**, alongside `gate_seen`/`near`:
   `traj[(close_s, tk)] = [(now_s, fair)]`, appended on **every** evaluation
   that computes `fair`, trimmed to the current close. The bot already computes
   `fair` on every look; this is a list append, no new I/O.
   **`conf_on_our_side = fair if want == "yes" else 1.0 - fair`** -- `fair()`
   returns P(YES) (pinrun.py:2804), so the side conversion is mandatory and
   getting it backwards inverts the rule.
4. **The multiplier applied where the others are** -- a `_doubt()` helper
   beside `_band53`/`_late48`, called in BOTH the paper block
   (pinrun.py:12777-12782) and the live `take_n` path, or the paper arm books
   a size the live path refuses.
5. **`max(...)` at pinrun.py:10007 must admit it**: `max_take_count=max(...,
   LATE_MULT, max_band_mult(), FLIP_MULT)` becomes `..., FLIP_MULT,
   DOUBT_MULT)`. Miss this and `pintake` refuses the wider live order while the
   paper path books it -- the exact failure the self-test at 4883 exists for.
6. **The A53/A55 first-boosted-loss rail**: one doubt-boosted loss switches
   `DOUBT_MULT` back to 1.0 for the rest of the run, with a
   `rec("doubt_boost_off", ...)` record, mirroring pinrun.py:10549-10571. The
   operator's own condition: *"we aren't just going to boost a trade above our
   normal level then just lose a bunch of money."*
7. **`--doubt-mult` must NOT be accepted with `--live` until the bar below is
   crossed**, in the same style as `--take-dumps` and `--one-coin-depth`
   (pinrun.py:13521-13540).

**The arm itself is one line in `sync_arms.ps1`'s `$arms` table (line 144):**

```powershell
  @{ n="arm-doubt15";      drop=@();                    add=@("--doubt-mult","1.5") },
  @{ n="arm-doubt125";     drop=@();                    add=@("--doubt-mult","1.25") }
```

It then inherits the live bot's own command line automatically, which is the
whole point of that script.

### What it blocks, and what it costs in winners

**It blocks nothing. Zero.** It only raises entry size on markets we already
buy. It cannot refuse an entry, it cannot delay, suppress, shrink or reprice a
hedge -- it is not consulted on any hedge path. **Cost in winners on our live
record: $0.00.**

What it *risks* is bounded and must be stated: 6 of the 68 flagged markets
across both halves were **dumped**, and 1.5x size makes a dump cost 1.5x. And
0 losses in 66-68 markets puts the 95% upper bound on the true loss rate at
**5.28%** against a 2.44% base -- **the zero loss rate is NOT established**;
about 153 flagged markets with still zero losses are needed to exclude the base
rate, roughly 85 more, ~3 weeks at ~4 a day. The money is the claim.

### PRE-REGISTERED BAR -- written before any arm data is read

**Window opens the moment `arm-doubt15` and `arm-doubt125` first log a fill,
and runs to the later of 20 trading days or 60 flagged closes.** Scored on
`arm-doubt15` vs live head-to-head on the **same markets** (read `h2h`, never
`diff` -- an arm that traded different markets proves nothing), plus the live
bot's own flagged population from the ledger.

**PASS, and all four must hold:**

1. The flag fires on **>= 60 closes** in the window (so the floor is cleared on
   fresh data, not on the training set).
2. Flagged markets make **>= +$2.00 a market** on Kalshi's ledger, and
   **strictly more** per market than the same window's unflagged markets.
3. **<= 2 money-losing flagged markets** in the window. (The base rate over 60
   closes predicts ~1.5; 3 or more says the zero was luck.)
4. `arm-doubt15`'s realised average entry price on flagged markets is within
   **0.20c** of live's on the same markets -- the measured p90 slippage is
   0.167c, so a bigger gap means the depth is not there and the arm is
   flattering itself.

**FAIL, any one of these, and the arm is closed and this document says so:**

- any **3rd** money-losing flagged market;
- flagged $/market **below** unflagged $/market;
- fewer than 40 flagged closes by day 20 (a power failure, reported as a power
  failure, not as a null);
- the arm's flagged entry price is **more than 0.5c worse** than live's.

**Live step on a PASS is 1.25x, not 1.5x, and not 2x.** The measured per-market
money is stable at +$2.72 to +$3.01 across every leave-one-day-out, but the
p-value fails the corrected bar on every one of them, so the first live size is
the smallest one that can be detected. 1.5x live requires a second clean
window. **2x is not on the table from this evidence.**

---

## 2. R2 -- the bot already knows it was picked off. LOG IT, THEN ACT. SHIP THE RECORD NOW.

### The rule

When `ask_seen - exec_price >= 3c` (both the bot's own fields, same side,
`exec_price` normalised to the wanted outcome by `pintake` line 540), the book
collapsed while our order was in flight and **we were the counterparty**.

### My own rebuild -- exact, to the cent

`pickoff.py`, the bot's own order records joined to Kalshi's settlements:

| bucket | mkts | closes | money-losers | ledger $ | $/mkt |
|---|---|---|---|---|---|
| paid MORE than the ask (swept up) | 233 | 200 | 3 | +399.75 | +1.72 |
| paid the ask | 210 | 186 | 5 | +141.98 | +0.68 |
| 0.5-3c better | 54 | 53 | 3 | +30.11 | +0.56 |
| **3-10c better** | **8** | **8** | **2** | **-57.11** | **-7.14** |
| **> 10c better** | **6** | **5** | **3** | **-60.51** | **-10.09** |
| no `ask_seen` logged (pre 09-13) | 273 | 212 | 10 | +91.92 | +0.34 |
| **>= 3c better (the flag)** | **14** | **13** | **5** | **-117.62** | **-8.40** |
| everything else | 770 | -- | 21 | +663.75 | +0.86 |

**14 markets / 13 closes / 5 of the 20 money losses / -$117.62.** Identical to
C_holdout to the cent, from code that shares nothing with it. The asymmetry is
the mechanism: **paying MORE than the ask is fine** (233 markets, 3 losses,
+$399.75) -- sweeping up means we ate depth we could see. **Only paying LESS is
dangerous.**

**A detail C_holdout did not report, and it matters for the action.** The flag
fires on **second fills**, not only first ones. Tonight's DOGE is the clean
case: the entry read NO at 98.0c and filled at 93.4c (4.6c better, 2 contracts,
-$1.88), then **one second later a second order read NO at 98.0c and filled 11
at 7.1c -- a 90.9c gap** (-$0.83). We bought more of the losing side *after*
the collapse. So the action "do not add to a position that was just picked off"
is not the 78c curiosity C priced; on DOGE it was **11 contracts** and the only
reason it was cheap is that the price had already gone.

### What is missing in the code

**Nothing for the record. `want`, `ask_seen`, `limit_sent`, `exec_price`,
`swept`, `book_age_ms`, `latency_ms`, `t_ms_decide` and `t_ms_send` are ALL
already on every `order` record** (pinrun.py:12967-12996, AMENDMENT 72, whose
own comment says *"the difference between these two is the only picked-off
signal we have... nothing branches on this"*). `ask_seen` is present on all 509
markets since 2026-09-13 and is being written live right now.

What is missing is three things, in increasing order of risk:

1. **A `pickoff` record** written immediately after the fill is registered,
   carrying `gap_c = 100*(ask_seen - exec_price)`, `filled`, `want`,
   `book_age_ms`, `latency_ms` and the position's cost. Derived, cannot fail a
   decision, costs one dict. `research/pinphone.py` should alert on
   `gap_c >= 3` -- **this is the one change I would make live tonight**, and it
   is a record, not a rule.
2. **"Do not add."** A flagged `(close_s, ticker)` refuses any further entry
   order in that market for the rest of the close, under its own gate name
   `pickoff` so the cost of the refusal is scorable (the `_gate()` convention
   at pinrun.py:10407). This is a **new gate and it blocks entries** -- see
   the cost below.
3. **"Treat as already alarming."** A flagged position is handed to the
   existing `hedge_belief` 0.25 trigger without waiting for further evidence.
   **This only ADDS protective action. It can never suppress, delay or shrink a
   hedge, and it must be written so that is structurally true -- no branch in
   the hedge path may ever read this flag and decide `no`.**

### What it blocks and what that costs

R2 (2) is the only piece that blocks anything, and on our live record it blocks
**exactly one order: DOGE 09-22 22:45's second fill, 11 NO at 7.1c.** That
order lost $0.83. Across all 784 markets no other flagged market had a
subsequent entry order. **Cost in winners: $0.00. Losses prevented on the
record: $0.83.** It is nearly free and nearly worthless -- ship it because it
is right, not because it pays.

R2 (3) is where the money would be, and **I cannot price it.** C_holdout priced
the only action a tape can price (dump at top-of-book bid): -$63.42 against
-$115.14 actually realised, a +$51.72 ceiling -- but it gives up money on 9 of
13, the whole gain is 3 markets, and it fills 73-104 contracts at the touch bid
with no idea how far the real sale walks. **That is not a recommendation and
this plan does not make it one.**

### PRE-REGISTERED BAR

**Log-only first, and the window opens the moment the `pickoff` record ships.**
There is no paper arm for this: a paper fill is booked at the price the bot
read, so a paper bot *can never be picked off* and the arm would fire zero
times. That is a hard limit, not a choice.

**Runs to 30 flagged markets** (13 today; the flag fires ~1 a day, so ~4-6
weeks, and the plan says 4-6 weeks rather than pretending otherwise).

**PASS, both:** >= 30 flagged markets, and **>= 7 of them money-losing**
(the MDE at the corrected bar: 30 markets needs 7 losses at a true rate of
30.3%; we have measured 35.7%, 95% interval 12.8%-64.9%). Then, and only then,
does a protective action become arguable, and it gets its own pre-registration.

**FAIL:** 30 flagged markets with <= 4 money losers -- the 5-of-14 was the
09-19 bug day and 2 holdout markets, and it did not hold.

**Current status, stated plainly: TRAIN alone is p = 3.2e-3 and fails the
1.13e-4 bar by 29x; pooled is 2.7e-5 and clears it; pooling is not a holdout.
13 closes is below the 30-close floor. This is a strong hypothesis, not a
proven edge, and nothing in it licenses touching a hedge.**

---

## 3. What must NOT ship. Do not re-litigate any of these.

| candidate | why not |
|---|---|
| insurance rose >= 6c / >= 3c in 2 s -> refuse | **look-ahead.** At the true pre-fill millisecond: 15 mkts, 1 of 17 losses, p = 0.32. At fill-250ms: **zero** losses. |
| our side's ask fell > 3c in 2 s -> refuse | same feature, same artefact. On a binary the two are one event. |
| market bid 25c+ under model fair -> refuse | honest anchor: 12 mkts, **0** losses, **+$38.20**. |
| insurance >= 15c / 20c at entry -> refuse | **it REVERSES.** Honest anchor: 61 mkts, 61 closes, 0 losses, **+$197.58** (+$3.24/mkt vs +$0.69). Dear insurance at entry is a GOOD sign. A gate here blocks our cleanest population. |
| cushion_sd < 0 / frac_locked > 1 -> refuse (tonight's DOGE signature) | dollar-negative in both halves (-$30.59 / -$10.81 on TRAIN), p 0.13-0.46, present in 2 of 17 losses. It diagnoses one loss and does not generalise. |
| already >= 97% earlier + tau <= 30 -> refuse | **refuted on the holdout, twice.** My rebuild: TRAIN 37 mkts -$1.57/mkt, HOLDOUT 13 mkts **+$1.76/mkt** -- the sign flips. |
| buy a protective leg at entry at the market's price | an **identity**: ask + (100 - bid) = 100 + spread, so a free hedge at entry cannot exist. -$1236 on TRAIN, and abstention beats protection by $112 even with perfect foresight. |
| price-triggered hedge at a mid level ("buy at 25c") | there is no rung to fill at -- the price gaps the whole 15-40c band in one second. Tonight: 6.6c, 6.6c, **93c** with 1 contract offered. |
| trade imbalance, spread width, insurance LEVEL alone | all fail the bar and all are **positive money**. A thin market is not a dangerous market here. |

Shipping any of the first five would have blocked 12-61 profitable markets and
prevented **at most one** of 17 TRAIN losses.

---

## 4. R3/R4 -- the recorder and tracker defects, which is the operator's other question

This is not tidying. Every underpowered answer in this map traces to one of
these, and two of them make an existing arm lie.

### R3. The paper entry path books at the touch and never walks the ladder

pinrun.py:12777-12786, the `if not live:` block:
`open_pos[_poid46] = (close_s, want, price, take_n, tk)` -- `take_n` contracts
at `price`, the **touch**, whatever the depth. `hedge_vwap()` exists and is
self-tested (pinrun.py:1413, 5691-5699) and is used **only on the hedge leg**
(line 11271), where its own docstring names the danger: *"so a paper arm
running --hedge-slip does not book ladder depth at the touch price and report
an edge the exchange would never have given it -- the flattering error that
makes an arm look good."* **A70 fixed that for the hedge and never for the
entry.**

**Consequence:** every arm that changes entry SIZE has been booking depth it
may not have had -- `arm-band15`, `arm-early-full`, the `--late-mult` boost,
`--one-coin-depth`, `--flip-mult`, and R1's own arms.

**The fix is one line**, in the `if not live:` block, after the four `take_n`
adjusters and before `_book_slot`:

```python
price = hedge_vwap([r for r in (sig.get("ladder") or [])
                    if float(r[0]) <= PRICE_CEILING + 1e-9], take_n, price)
```

`sig["ladder"]` is already built on every signal, live and paper
(pinrun.py:12388-12396), in our side's price terms. The helper already returns
the fallback when the ladder cannot hold `n`, which is the correct behaviour --
do not invent a price.

**I have measured how much this has been flattering the arms, so nobody has to
guess: median +0.03c a contract at 1.5x, p90 +0.167c, max +1.441c.** Small --
which is the good news, because it means R1's arm is usable *before* this fix
lands. Fix it anyway; a known bias that is small today is not small at 2x.

### R4. The bot writes a median of ONE refusal record per market

`_gate()` de-duplicates on `(close_s, ticker, gate)` (pinrun.py:10412-10416),
so a market that is refused 400 times by one gate logs it once, with the
values from the **first** firing. Measured over the last 12 live runs:

- refusal records per (close, ticker): **median 1**, p90 4, max 10, mean 2.07;
- distinct gates per (close, ticker): **median 1**, max 10;
- `close_summary.looks` per close: **median 5,508**.

**So `traj_min_conf_ge5s` -- the feature R1 rests on -- is not a trajectory
minimum. It is "the model's fair value at the first firing of each distinct
gate".** It is still strictly pre-entry and it still works, but its
availability depends on *which* gates happened to fire, which is a selection
effect nobody has bounded. And a live bot computing a true running minimum
would be measuring a **different feature** than the one that showed +$2.95 a
market. **R1's implementation must reproduce the historical definition** (min
over logged gate firings) **or the historical number does not transfer** --
which is precisely why R1 goes to a paper arm rather than straight to live.

**The fix, and it is cheap:** a `trace` record at 1 Hz per watched market for
`tau <= 60`, carrying `ticker, close_s, tau, fair, want, touch, touch_size`,
written to its own file so it never bloats the decision log. Volume: 12 markets
x 60 s x 96 closes = ~69k records/day, ~14 MB/day uncompressed. Against 22 GB
free falling 3 GB/day that is 0.5% of one day's burn. **After that, the next
person who asks "was there an earlier sign?" has 60 readings per market instead
of one, and the answer stops being "cannot measure".**

### R5. Two definitional errors already in the shared table

Both are C_holdout's and both are confirmed; they are here so the fix is not
lost. **(a) The time in a Kalshi 15M ticker is EASTERN** -- `26SEP222245` is
02:45Z the next day; +4 h reproduces the bot's own `close_s` on 1254 of 1254
refusals. Any day-of-week or leave-one-day-out cut off a `close_utc` column
built at +0 h uses the wrong days. **(b) A loss is not `won == False`** -- 7
markets our side WON where a false-alarm hedge made the net negative, -$137.57,
17% of all negative money, invisible to every p-value in the three hunts. I
report money losses (`neg$`) throughout this file for that reason.

---

## 5. The mechanism behind tonight's loss, named and NOT established

Tonight's DOGE close, from the bot's own log, 244 ms apart:

| | tau | our side's ask | `edge_c` | contracts wanted | result |
|---|---|---|---|---|---|
| look 1 | 12 | 98.0c | 1.422 | 2 | filled 2 at **93.4c** |
| look 2 | 12 | **93.4c** | **5.728** | **62.4 -> 82** (sweep_depth) | **canceled, filled 0** |
| look 3 | 11 | 98.0c | 1.422 | 11 | filled 11 at **7.1c** |

`fair` was 0.00441 at all three looks. **The market repriced 4.6c against us
and the bot's demand went up 41x**, because `net_edge` is (our price) against
(an unchanged model fair): a cheaper price on our side reads as a bigger edge.
**We were saved by a cancel.** Had look 2 filled, that close would have cost
about **$58** at 62.4 contracts, or **$77** at the 82 that `sweep_depth` asked
for -- instead of $2.47.

I tried to measure this as a rule: "our side's touch fell >= 3c since **my own
previous look** at this market, within 2 s" -- pre-entry by construction, the
bot's own eyes, no tape, immune to C_holdout's look-ahead. **It is unmeasurable
at n = 2.** The bot normally fires one signal per market per close, so only 38
of 511 markets have two comparable own looks at all, and only 2 show a >= 3c
fall (DOGE -$2.47, ETH 09-22 14:15 +$1.17). **Reported as a mechanism, not a
rate, and it is a mechanism with real teeth.** The cheap thing to do about it
is R4's trace plus a `rec()` on any look whose own-side price fell >= 3c since
this bot's previous look at the same market -- log-only, no gate, and revisit
when the population exists.

One cell I will flag and not build on, because I chose it out of six and it is
one look past the bar: of the 38 markets with two comparable own looks, the 29
where the second look was at the **same or a higher** price are 29 closes, 4 of
16 money losses, **-$86.89 (-$3.00/mkt)** against +$1.09 for the rest. That is
the re-buy population and `rebuy_ok()` already governs it. p ~ 0.004 against a
1.13e-4 bar. **Not a finding. A place to look once R4 exists.**

---

## 6. Could not measure

- **Whether any refused entry would simply have been re-bought a second later
  at a worse price.** The `refused` record carries no price and no
  opposite-side quote, so every "winners blocked" number in this map, mine
  included, is an **upper bound** on what a gate costs and says nothing about
  what it re-buys. This is the single most valuable missing field and R4's
  trace supplies it.
- **What a protective action on a picked-off position is worth.** No paper arm
  can ever be picked off, so it needs live money or a depth-aware replay, and
  the replay is not evidence here.
- **How far a real sale walks down the book.** Top-of-book bid only.
- **Tonight's DOGE post-fill Kalshi book.** The tape is deaf from
  2026-09-23 00:11Z. `feed_data` holds the constituent exchanges, not the
  Kalshi book, so it cannot answer this one.
- **Anything about the 7 false-alarm-hedge money losses at n = 7.** They are
  the operator's named open cause, they are structurally invisible to a
  `won == False` loss rate, and 19 features over 7 saves and 7 false alarms
  gave a best p of 0.123 where only a perfect separator could have cleared any
  bar. Still true. Still open.

---

## 7. Order of work, and the version discipline

1. **Tonight, no gate, no risk:** the `pickoff` record + `pinphone` alert on
   `gap_c >= 3c`. R2 (1).
2. **Tonight or next session:** the R3 one-line paper VWAP fix, and the R5
   ticker-is-Eastern / money-loss corrections wherever the shared table is
   reused.
3. **Next:** R4's 1 Hz `trace` record. It is what makes the next map able to
   answer the question this one could not.
4. **Then:** `--doubt-mult` + `--doubt-under`, refused with `--live`, and
   `arm-doubt15` / `arm-doubt125` added to `sync_arms.ps1`. Window opens at
   their first fill.
5. **Only on a PASS:** R2 (2) "do not add", then 1.25x live for R1.

**Every one of these that touches `restart_bot.ps1` needs a `results/VERSIONS.md`
entry written AT DEPLOY** -- UTC time, SHA, one sentence, the evidence, and the
copy-pasteable revert. `python research/versioncheck.py` fails if
`restart_bot.ps1` passes a flag VERSIONS.md does not mention, and it must be
run in any session that touches the live bot. Steps 1-3 touch no flag and need
no entry; step 4 touches `sync_arms.ps1` only, which is not the live bot; step
5 is a live flag and needs one.

**And run the startup path with the new flag before restarting live.** `pinrun`
self-tests at STARTUP with flags applied, and `--selftest` alone runs with
defaults -- a new `--price-ceiling` flag took the live bot down 6 minutes this
way once.
