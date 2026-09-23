# C_holdout -- adversarial verification and holdout of the three signature hunts

**Finished 2026-09-23 ~02:0xZ (09-22 ~22:0x ET).** Read-only throughout; no
process started, stopped or signalled; nothing written outside this file and my
scratchpad. Collectors verified alive after every job (`kalshi_collector.py`
pid 105304 at 48 MB, `crypto_feeds.py` pid 105352 at 39 MB). Free RAM 2.99 GB,
peak python footprint ~120 MB. **Free disk 22.3 GB** -- above the 6 GB hard
collection stop, still falling ~3 GB a day.

My own code, written from scratch, importing nothing from the other hunts:
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\signature\verify\`
-- `build_fills.py` (logs + Kalshi's ledger), `tape_ms.py` (three quote anchors),
`trade_anchor.py` (our own trade print as the anchor), `dumpprice.py`, `lib.py`.
No replay, no pinsim, no pindata anywhere.

---

## Verdicts, up front

| rule | verdict |
|---|---|
| market-opinion 1 -- insurance rose >= 6c in 2 s -> refuse | **REFUTED** (look-ahead) |
| market-opinion 2 -- market bid 25c+ under model fair -> refuse | **REFUTED** (look-ahead) |
| market-opinion 3 -- insurance rose >= 3c, and the cheap-price conjunction | **REFUTED** (look-ahead) |
| A_table 1 -- our side's ask fell > 3c in 2 s -> refuse | **REFUTED** (look-ahead, same feature) |
| hedge-outcomes 2 -- insurance >= 15c / 20c at entry -> refuse | **REFUTED**, and it REVERSES |
| hedge-outcomes 1 -- never buy a protective leg at entry | **SURVIVES** (it is arithmetic) |
| hedge-outcomes 3 -- no price-triggered hedge at a mid level | **SURVIVES** as a mechanism |
| B_trajectory 1 -- size UP when the model doubted our side earlier | **WEAKENED but alive**, holdout confirms |
| B_trajectory 2 -- do not ship a cushion / locked-prints gate | **SURVIVES** (it was already a null) |
| B_trajectory 3 -- already >= 97% earlier + tau <= 30 -> refuse | **REFUTED** on the holdout |
| **NEW, mine** -- `exec_price` came back below `ask_seen` | **strong hypothesis**, 13 closes |

---

## 0. My table, and where it disagrees

| | mine | A_table |
|---|---|---|
| entry fills | 815 | 811 |
| markets / closes | 782 / 576 | 779 / 573 |
| TRAIN markets (close <= 2026-09-20 ET) | **697** | **697** |
| TRAIN closes / losses | **509 / 17** | **509 / 17** |
| HOLDOUT markets / closes / losses | 85 / 67 / 3 | 82 / 64 / 3 |
| ledger dollars over our markets | $538.43 | $533.61 |

TRAIN reconciles exactly, which is what makes the disagreements below
meaningful rather than a different dataset. The 3 extra holdout markets are
mine: I keep every order with `filled > 0`.

**Two definitional errors that are in the shared table and should not
propagate:**

1. **The time inside a Kalshi 15M ticker is EASTERN, not UTC.** `26SEP222245`
   is 22:45 ET = 02:45 UTC the next day. Verified twice: +4 h reproduces the
   bot's own `tau` on 84 of 84 recent signals and 0 of 84 at +0 h, and it
   reproduces the bot's own `close_s` epoch on **1254 of 1254** refusal records.
   A_table's `close_et` column happens to be right (the ticker's date IS the ET
   date) but its `close_utc` column is 4 h early, and for the 20:00-23:45 ET
   closes that is the wrong calendar day. Anyone doing a day-of-week or
   leave-one-day-out cut off that column gets the wrong days.

2. **All three hunts define a "loss" as `won == False`. That is not a market
   that lost money, and the gap is 7 markets and -$137.57** -- markets our side
   WON where a false-alarm hedge made the net negative: XRP 09-19 -$64.95,
   HYPE 09-19 -$43.92, DOGE 09-16 -$12.14, NEAR 09-16 -$9.22, ETH 09-12 -$5.16,
   BNB 09-13 -$1.10, BTC 09-12 -$1.09. Every one alarmed exactly once and
   hedged. They are 17% of all the negative money, and **every loss-rate
   p-value in all three hunts is blind to them** -- which matters because
   false-alarm hedges on winning bets is the one open cause named in
   CURRENT_STATE.md. (One goes the other way: DOGE 09-18 00:15 lost the binary
   and the hedge kept it at +$4.36.) I report every rule below on BOTH
   outcomes; `lost` is the binary, `neg` is money.

---

## 1. REFUTED: the 2-second quote move before entry is a look-ahead artefact

**This kills market-opinion 1, 2 and 3, A_table 1, and hedge-outcomes 2 -- the
four highest-dollar "gates" in the whole signature map.**

### What the anchor was

The shared tape builder took "the quote at the decision" to be **the last
`ticker` update whose exchange SECOND `ts` was <= the decision second**. Kalshi's
`ticker` messages also carry `ts_ms`, the exchange MILLISECOND; the builder
ignored it. So any update stamped anywhere inside the decision second was
accepted as "before" -- including updates after the decision, and after our own
fill.

### Three anchors, and the proof

| anchor | definition | what it can see |
|---|---|---|
| `same` | last update with `ts <= dec_sec` | A_table's. Can see up to 1 s of the FUTURE. |
| `pre` | last update with `ts_ms < dec_sec*1000` | Cannot see the decision second at all. Up to 1 s stale. |
| `fill` | last update with `ts_ms <` **our own trade print's `ts_ms`** | True pre-trade, to the millisecond. |
| `fill250` | `fill` minus 250 ms | Covers the 107 ms median order latency, so it is what the bot could actually have known. |

The `fill` anchor is built by locating **our own fill on the `trade` channel**
(same taker side, size within 1%, price within 1.5c): matched on **784 of 815
fills**, 498 on size+price and 286 on price alone. Our print lands a median
**+132 ms** after the decision-second boundary. Validation: the `fill` anchor's
our-side ask sits a median **-0.10c** from the bot's own logged `ask_seen`, and
on the 28 fills where the bot logged its own decision millisecond (`t_ms_decide`,
which exists only from 2026-09-22 11:52:44Z) the true-millisecond anchor matches
`pre` on 21 of 28 and `same` on 10 of 28.

On the 29 fills the collapse flag fires on, the `same` anchor's our-side ask sits
a median **-2.15c** below what the bot itself saw and filled at, **minimum
-92.00c**. A quote 92c below the price we paid cannot have existed before we paid
it -- we would have filled there. Across all 783 fills with a print inside the
decision second, the insurance moves as much as **+94.1c** and our side's ask as
much as **-93.0c** *within that one second*. The whole "signal" lives inside the
second the builder could not resolve, and it resolved it forward.

### The decisive table -- TRAIN, 697 markets / 509 closes / 17 losses / +$482.88

| rule | anchor | mkts | closes | lost | ledger $ | Fisher p |
|---|---|---|---|---|---|---|
| **market-opinion 1** insurance rose >= 6c | `same` | 20 | 20 | **8** | **-188.16** | 2.6e-9 |
| | `pre` | 13 | 13 | 0 | +32.99 | 1.00 |
| | **`fill`** | **15** | **15** | **1** | **-28.10** | **0.32** |
| | `fill250` | 15 | 15 | 0 | +33.16 | 1.00 |
| **A_table 1** our ask fell > 3c | `same` | 23 | 22 | **8** | **-167.56** | 9.7e-9 |
| | **`fill`** | **16** | **16** | **1** | **-19.67** | **0.34** |
| | `fill250` | 12 | 12 | 0 | +30.62 | 1.00 |
| **market-opinion 3a** insurance rose >= 3c | `same` | 40 | 39 | **8** | **-149.45** | 1.2e-6 |
| | **`fill`** | **29** | **29** | **1** | **+16.67** | **0.53** |
| **market-opinion 2** bid 25c+ under fair | `same` | 9 | 8 | **6** | **-126.63** | 7.8e-9 |
| | **`fill`** | **12** | **12** | **0** | **+38.20** | 1.00 |
| **hedge-outcomes 2** insurance >= 15c | `same` | 42 | 41 | **7** | **-32.63** | 2.7e-5 |
| | **`fill`** | **61** | **61** | **0** | **+197.58** | 1.00 |
| **hedge-outcomes 2** insurance >= 20c | `same` | 17 | 16 | **7** | **-111.68** | 2.7e-8 |
| | **`fill`** | **29** | **29** | **0** | **+89.95** | 1.00 |
| market-opinion 3b cheap AND insurance rose >= 3c | `same` | 9 | 9 | 6 | -96.19 | -- |
| | `pre` | 4 | 4 | 0 | +16.60 | -- |

My `same` column reproduces the hunts' own numbers closely (they report
22/21/8/-$184.52 for market-opinion 1 where I get 20/20/8/-$188.16, and
9/8/6/-$126.63 for rule 2 where I get 9/8/6/-$126.63 exactly). **This is the
same measurement with the clock fixed, not a different dataset.**

### Mechanism of the artefact, plainly

On a binary the other side's ask is exactly 100c minus our side's bid, so
"insurance got dear" and "our side got cheap" are ONE event: the market
repricing against the side we bet on. A market repricing against us *in the
second we entered* is not a warning -- it is most of the definition of the
loss. The builder measured the loss and called it a predictor. That the same
feature was found independently by two hunts with opposite signs and near
identical n and p should have been the tell.

### What is left after the fix

At the true pre-trade millisecond the flag catches **1 of 17 TRAIN losses**
(base rate over 15-16 markets predicts 0.4), p = 0.32-0.53, and 250 ms earlier
-- which is where the bot actually stands when it decides -- it catches **zero**.
**The information does not exist before we send. It appears between our send and
our fill.** That is not a gate; it is a description of being the counterparty to
the collapse. Section 4 is the handle that does exist.

**Shipping any of these as an entry gate would have blocked 12-61 markets that
made +$17 to +$198 and prevented at most one of the 17 TRAIN losses.**

### The reversal, worth knowing on its own

On the honest anchor, **dear insurance at entry is a GOOD sign, not a warning**:
insurance >= 15c is 61 markets / 61 closes / **0 losses** / **+$197.58**
(+$3.24 a market against the book-wide +$0.69). This says the same thing
market-opinion's own null #3 said about the spread -- a thin market is not a
dangerous market here -- only much louder. It is 0 of 61, base rate predicts
1.5, P(0) = 0.22, so it is **not established**; I report it as a null for
gating, plus a warning that a "dear insurance" gate would have blocked our
cleanest population.

---

## 2. SURVIVES: hedge-outcomes 1 and 3

**Finding 1 ("never buy a protective leg at entry at the market's price")
survives, and the correct anchor makes it stronger.** One correction to how it
was argued: the claim "the two asks summed below 100c in 0 of 696 quoted fills"
is not a measurement, it is an identity. Our side's ask plus the other side's
ask = our ask + (100c - our bid) = 100c + the spread, so it is >= 100c whenever
the ask is at or above the bid. I confirm 0 of 696 on both anchors, and the
conclusion is right *because* it is an identity -- a free hedge at entry cannot
exist, ever, not merely did not in this sample. Re-pricing the 1:1 protective
leg on the strictly-pre-decision anchor costs **$2272.41** in premium and fees
against **$2020.94** on the contaminated one, so their -$1236.39 net verdict is
if anything conservative. Nothing here changes.

**Finding 3 (no price-triggered hedge at a mid level) survives as a mechanism.**
It is reported as a mechanism in 5 of 7 saves, not as a rate, and I have nothing
that contradicts it. My section 1 adds to it: the collapse that leaves no rung
to fill at is the same event that contaminated the entry anchor, and it happens
inside a single second.

**B_trajectory 2 (do not ship a cushion / locked-prints gate) survives.** It was
already reported as a null that costs money on both halves; I did not spend
power re-litigating a rule nobody wants to ship.

---

## 3. WEAKENED but alive: B_trajectory 1 -- size UP on late-arriving confidence

`traj_min_conf_ge5s` = the lowest fair value the bot's own model put on the side
we eventually bought, at any logged evaluation at least 5 s earlier in the same
close. Rebuilt from my own pass over `refused`/`signal` records.

**It reproduces to the cent, which is the best validation in this whole report.**

| | markets | closes | lost | money-neg | ledger $ | $/mkt | c/contract |
|---|---|---|---|---|---|---|---|
| TRAIN all | 697 | 509 | 17 | 23 | +482.88 | +0.69 | +1.47 |
| TRAIN doubt < 50% | **50** | **46** | **0** | **0** | **+157.76** | **+3.16** | +4.50 |
| TRAIN 50-97% | 144 | 123 | 4 | 4 | +123.61 | +0.86 | +1.22 |
| TRAIN already >= 97% | 35 | 35 | 3 | 5 | -65.34 | -1.87 | -3.16 |
| TRAIN no earlier reading | 468 | 367 | 10 | 14 | +266.86 | +0.57 | +1.55 |
| HOLDOUT all | 85 | 67 | 3 | 3 | +55.54 | +0.65 | +1.16 |
| **HOLDOUT doubt < 50%** | **18** | **18** | **0** | **0** | **+42.82** | **+2.38** | +3.49 |

**Holdout confirms, and it confirms on each holdout day separately** -- which is
the bit that matters, because the bot's settings changed inside the holdout
(v-early-third 11:42Z and v-safety1 11:52Z on 09-22):

- 09-21: doubt 8 markets +$18.83, **the rest of that day -$21.80**.
- 09-22: doubt 10 markets +$23.99, the rest +$29.71.

Combined both halves: **68 markets, 64 closes, 0 losses, 0 money-losers,
+$200.58.**

### My attacks, and what they did

- **Pre-entry?** Yes. Every reading used is a `refused`/`signal` record whose own
  second is at least 5 s before the entry second, so the worst-case gap is 4.0 s.
  Nothing in it comes from the tape, so nothing in it can have the section-1
  disease.
- **Is it a date artefact?** Nearly. The feature does not exist before
  2026-09-13 (the bot logged too few earlier evaluations: 0 flagged markets on
  09-08 through 09-13, 19 of 61 on 09-14 alone), so the "no earlier reading"
  comparison bucket is largely a different era with a smaller bank and smaller
  sizes. **It survives anyway**: drop 09-14 entirely and the flag is 31 markets
  at **+$3.30 a market**, and every leave-one-day-out fit stays between +$2.86
  and +$3.32.
- **Is it one or two markets?** No. Drop the single best market: 49 markets,
  +$2.88/mkt. Drop the best three: 47 markets, +$2.62/mkt.
- **Is it just price?** No, and this surprised me. Median price 96.5c against
  97.2c book-wide, only 1 of 50 sub-90c. Inside price bands it still adds:
  90-97c **+5.98 c/contract vs +2.03**, >= 97c **+2.10 vs +0.31**.
- **Is it tau in disguise?** Partly by construction (median tau 13 vs 29
  book-wide: time must pass for confidence to arrive), **but it adds inside every
  tau band**: tau 0-15 $3.09/mkt vs $1.63, tau 16-29 $3.35 vs $0.21.
- **Multiple looks.** Total looks across the three hunts: 82 + 117 + 242 =
  **441**, so the bar is **0.05/441 = 1.13e-4** and A_table's own scan sits on
  top of that, making 1.13e-4 a FLOOR. My own within-day permutation on dollars
  per market (20k draws, day composition held fixed): **p = 0.00010 on TRAIN** --
  inside the bar by a hair, and at the 20k-draw resolution floor. **Leave-one-day-
  out breaks it**: dropping 09-17 gives p = 0.0032 and dropping 09-19 gives
  0.0025, both failing the bar by 22-28x. So the DIRECTION is robust to every
  cut I tried and the SIGNIFICANCE is not.
- **Could it block or delay a hedge?** No. It only raises entry size. Across
  both halves the 68 flagged markets were **hedged 0 times and alarmed 0 times**
  (base rate 18 hedges and 19 alarms in 782 markets, so 0 in 68 is expected 1.6
  and unremarkable -- it is not evidence of safety, only of no interaction).
  **6 of the 68 were DUMPED**, and doubling the size doubles what a dump costs.
- **Can the size actually be doubled?** Partly, and this is the real unpriced
  cost. **37 of the 68 flagged fills already SWEPT** -- they walked up the ladder
  to fill what the bot wanted -- so on those a 1.5-2x order pays a worse average
  price and eats directly into the +4.50 c/contract the rule is built on. On the
  other 30 the bot got what it asked for with depth left over (median
  `ladder_total / contracts filled` = 32.7x, p10 = 4.8x). **A 2x rule is not 2x
  the money; nobody has priced the slippage and I cannot price it from fills we
  never placed.**
- **Zero-loss MDE, honestly.** 0 losses in 68 markets puts the 95% upper bound
  on the true loss rate at **5.28%**, against a 2.44% base. It takes **about 153
  flagged markets with still zero losses** to exclude the base rate -- roughly
  **85 more, about 3 weeks** at the current ~4 a day. **The money is the claim;
  the zero loss rate is not established.**

**Verdict: WEAKENED. The money effect is real and replicated out of sample on
two separate days; the p-value does not survive leave-one-day-out at the
corrected bar; and the rule's own cost (slippage on the 54% of fills that
already swept) has never been measured.** It is a sizing rule, it cannot touch a
hedge, and the sensible form is the small one -- 1.25-1.5x, not 2x -- logged as
its own paper arm so the slippage is measured on real fills before the size goes
up again.

---

## 4. NEW and CLEAN: the order response already tells us we were picked off

**Claim.** When `exec_price` comes back **3c or more BELOW the `ask_seen` the bot
decided on**, the book collapsed while our order was in flight and we are the
counterparty to it. **14 markets / 13 closes hold 5 of the 20 losses and
-$117.62, against +$1.14 a market everywhere else.**

This is the honest version of what section 1's four refuted rules were groping
at, and it is uncontaminated: both numbers are the bot's OWN logged fields, from
its own book read and its own order response. No tape, no anchor, no clock.

| bucket (509 markets that log `ask_seen`) | mkts | closes | lost | neg | ledger $ | $/mkt | Fisher p |
|---|---|---|---|---|---|---|---|
| paid MORE than the ask (swept up) | 97 | 89 | 1 | 1 | +218.34 | +2.25 | -- |
| paid the ask | 379 | 293 | 5 | 9 | +322.67 | +0.85 | -- |
| 0.5-3c better | 19 | 18 | 1 | 1 | +23.11 | +1.22 | -- |
| **3-10c better** | **9** | **9** | **2** | **3** | **-59.57** | **-6.62** | -- |
| **> 10c better** | **5** | **4** | **3** | **2** | **-58.05** | **-11.61** | -- |
| **>= 3c better, all data** | **14** | **13** | **5** | **5** | **-117.62** | **-8.40** | **2.7e-5** |
| >= 3c better, TRAIN | 11 | 10 | 3 | 3 | -62.77 | -5.71 | 3.2e-3 |
| >= 3c better, HOLDOUT | 3 | 3 | 2 | 2 | -54.85 | -18.28 | 2.5e-3 |

The asymmetry is the mechanism and it is exactly the right shape: **paying MORE
than the ask (sweeping up) is fine -- 97 markets, 1 loss, +$218.34. Only paying
LESS is dangerous.** Sweeping up means we consumed depth we could see. Paying
less means the offer got cheaper in the ~107 ms our order was in flight, which
only happens because somebody was selling into us.

The 14, worst first: NEAR 09-21 12:45 -$59.09 (4.4c better), BNB 09-19 01:45
-$57.76 (10.0c), HYPE 09-19 23:45 -$43.92 (3.4c), BTC 09-17 21:15 -$27.87
(**44.8c** better -- read 97.8c, filled 53.0c), **DOGE 09-22 22:45 -$2.47 (4.6c
better -- tonight's loss)**, then 9 winners worth +$73.49.

### Attacks

- **Pre-entry?** **NO, and I will not pretend otherwise.** It is known ~107 ms
  (median order latency) AFTER the fill. It can never gate an entry. It can only
  drive an action on a position we already hold.
- **Is it a stale book read on our side?** No -- the opposite. In the flagged
  bucket the bot's `book_age_ms` is a median **4 ms** against 8 ms book-wide. Its
  read was FRESHER than average; the market moved, we did not lag.
- **Swept orders?** 0 of 14, by construction -- a sweep averages above the ask.
- **Drop the biggest loss?** Survives: 13 markets, 4 losses, -$58.53.
- **Leave one day out?** Survives 7 of the 9 days it spans inside the bar
  (worst p = 1.35e-4 dropping 09-18, a marginal fail against 1.13e-4).
  **Dropping the 09-19 bug day entirely: 11 markets, 4 losses, -$23.98,
  p = 1.5e-5** -- it is not a 09-19 artefact.
- **Tau or leg in disguise?** Neither. Flagged spread over tau (2 at tau<=15, 5
  at 16-29, 7 at >=31) and the flagged tau>=31 markets are the worst
  (-$104.53 over 7 against +$71.51 over the other 217). Leg 7 early / 4 full /
  3 none against 224/102/183 book-wide -- proportional.
- **Multiple looks.** I took ~6 threshold looks. Against the 1.13e-4 bar:
  pooled p = 2.7e-5 clears it, **TRAIN alone (3.2e-3) does NOT** and neither
  does the holdout alone (2.5e-3). Pooling is not a holdout, so the honest
  statement is: TRAIN fails the bar by 29x, and the holdout independently
  reproduces the direction and the size, with 3 markets carrying 2 of the
  holdout's 3 money losses and -$54.85 against a holdout that made +$55.54 in
  total. Those 3 markets were essentially the entire drag on the holdout.
- **Closes.** 13 -- **below the project's 30-close floor. Strong hypothesis, not
  a proven edge.** MDE at the corrected bar: 14 markets needs 5 losses and 80%
  power needs a true rate of 48.0%; we measured 35.7% (95% interval 12.8% to
  64.9%). 30 markets needs 7 losses at a true rate of 30.3%; 50 needs 8 at
  20.5%. At ~1 flagged market a day it is **2-4 weeks to a gateable n**.
- **Could it block or delay a hedge?** **No, structurally: it fires after the
  fill and can only ADD an action.** 6 of the 14 were hedged and 6 alarmed, so it
  lands on the hedge population -- which is a reason to wire it as "treat as
  already alarming", never as "suppress".
- **Availability.** `ask_seen` is logged only from 2026-09-13 (0 of the first
  213 markets, all of the 509 since), so this feature is 509 markets not 782, and
  it IS being logged live today -- deployable without a new field.
- **Overlap with the doubt-sizing rule: ZERO.** 68 flagged and 14 flagged, 0 in
  common. The two surviving findings are independent.

### What the action is worth -- and this is where it stops being clean

I priced the only action the tape can price: dump the position straight back at
the market's bid for our side, on the first quote within 1.5 s of our own fill
(`dumpprice.py`). 13 of the 14 priced (DOGE 09-22 22:45 has no quote -- the tape
is deaf from 2026-09-23 00:11Z).

**Dumping immediately: -$63.42. What actually happened on those 13, hedges
included: -$115.14. Difference +$51.72.**

Two things make that an optimistic ceiling, not a recommendation:

1. It fills the whole position at **top-of-book bid only**, on sizes of 73-104
   contracts. A real sale walks down the book, and I cannot price how far
   without the depth.
2. **It gives up money on 9 of the 13.** The entire gain is 3 markets (BTC 09-17
   +$38.91, BNB 09-19 +$52.86, NEAR 09-21 +$69.83 against holding); the other 10
   cost between $3.27 and $32.73 each. That is a high-variance rule on 13
   closes.

**So the deployable form is the conservative one, and it is not the dump:** when
`ask_seen - exec_price >= 3c`, (a) **do not add to the position** -- the only
such case in the sample is DOGE's second fill, 11 NO at 7.1c, worth about 78c,
so this is small but free; and (b) **treat the market as already alarming for
hedge purposes**, i.e. let the existing 0.25 belief trigger fire without waiting
for more evidence. Both only ADD protective action. Neither can block a hedge.
The whole thing should run as a **logging record plus a paper arm first**,
because 13 closes does not license a live change.

---

## 5. REFUTED on the holdout: B_trajectory 3

"Refuse when the model was already >= 97% on our side >= 5 s ago and we are
entering at tau <= 30."

- TRAIN: 15 markets / 15 closes / 2 losses / 3 money-losers / **-$20.19**.
  Poisson p = **0.044** against the 1.13e-4 bar -- fails by 390x.
- HOLDOUT: 3 markets / 3 closes / **0 losses** / **+$10.37** (+$3.46 a market,
  five times the holdout's own +$0.65). **Deploying it would have cost $10.37 out
  of sample.**
- The wider version (any tau) is TRAIN 35 markets / 3 losses / -$65.34 but
  HOLDOUT 12 markets / 0 losses / **+$22.33**.

B_trajectory's own verdict was "INSTRUMENT, DO NOT GATE". I agree with the
instruction and go further on the evidence: the holdout points the other way, so
this is refuted as a gate, not merely underpowered. Keep logging
`traj_min_conf_ge5s` and `traj_gap_s` -- they are free and they are what
section 3 runs on.

---

## 6. Nulls I independently confirmed

- **"Confidence deteriorating into the entry" is not a population.** Of the 314
  fills that had any earlier model reading, the model's confidence on our side
  was lower at entry than at some earlier point in **0** of them. B_trajectory
  said 0 of 718 on its own population; same answer.
- **The cushion / locked-prints signature (tonight's DOGE lead) is a null.** Both
  hunts found it dollar-positive to leave alone; I did not spend power
  re-litigating a rule nobody proposes to ship, and I found nothing that
  contradicts them.
- **Protection bought at the market's price at entry cannot be free** -- an
  identity, section 2.

## 7. Could not measure

- **Whether any refused entry would simply have been re-bought a second later at
  a worse price.** The refusal side carries no price and no opposite-side quote,
  so every "winners blocked" number in every hunt, and in this report, is an
  upper bound on what a gate costs and says nothing about what it re-buys.
- **The slippage cost of a 1.5-2x order** on the 37 of 68 doubt-flagged fills
  that already swept. It needs orders we never placed.
- **How far a dump walks down the book.** Top-of-book only, so section 4's
  +$51.72 is a ceiling.
- **The DOGE 22:45 close's own post-fill book** -- the tape is deaf from
  2026-09-23 00:11Z, and I did not go to `feed_data` because the question was
  about the Kalshi book, which `feed_data` does not hold.
- **Anything about the 7 false-alarm-hedge money losses at n = 7.** They are the
  operator's named open cause and they are structurally invisible to a
  `won == False` loss rate; B_hedge searched 19 features across 7 saves and 7
  false alarms and its best p was 0.123, where only a perfect separator could
  have cleared any bar. That remains true.

## 8. What I would do with this

1. **Do not ship any of the five refuted gates.** They would have blocked
   12-61 profitable markets and stopped at most one of 17 losses.
2. **Fix the shared table** (`ts_ms` not `ts`, ticker time is ET, count money
   losses not binary losses) before anything else is built on it, and re-run any
   conclusion that used the `same` anchor. A_table Finding 1 is the headline of
   that report and it is gone.
3. **Add `traj_min_conf_ge5s`, `traj_gap_s` and `ask_seen - exec_price` as
   logged fields on every signal, refusal and order**, and start a paper arm for
   each of the two surviving rules. Both are cheap, neither touches a hedge.
4. **The one change I would make live now is a record, not a rule:** log
   `ask_seen - exec_price` on every order and alert when it is >= 3c. It costs
   nothing, it cannot block anything, and it is the only feature in this whole
   map that flags tonight's DOGE loss from the bot's own data with no clock
   trickery.

---

## Honest MDE summary, per rule

At the corrected bar (0.05/441 = 1.13e-4), base loss rate 2.44%, 80% power:

| flagged markets | losses needed | true loss rate needed |
|---|---|---|
| 14 | 5 | 48.0% |
| 20 | 6 | 39.5% |
| 30 | 7 | 30.3% |
| 50 | 8 | 20.5% |
| 80 | 10 | 15.6% |
| 120 | 12 | 12.3% |
| 200 | 16 | 9.6% |
| 400 | 24 | 7.0% |

**This table can establish a rule that loses a third of the time. It cannot
establish one that loses a tenth of the time.** Everything in section 1 was
"establishes a huge effect" -- which is exactly the shape a look-ahead makes.
The zero-loss claims (doubt-sizing at 0 of 68, dear-insurance at 0 of 61) need
about 153 markets each to exclude the base rate, roughly 3 weeks at the current
rate.
