# ADVERSARIAL REVIEW — LENS 1: THE MONEY CLAIMS

**Targets:** `results/overnight/REBATE_RISK.md` (rebate inventory risk) and
`results/overnight/INCENTIVE_FAMILIES.md` (incentive families).
**Stance:** adversary, no stake, default to refuted.
**Everything below was RUN, not read.** Scripts in
`C:\Users\Joe\AppData\Local\Temp\kals-work\advl1\`.

---

## HEADLINE

Both jobs score the Liquidity Incentive Program with a rule that **is not in
Kalshi's CFTC filing**, on a **book that is missing most of its resting depth**.
The two errors point in opposite directions and do not cancel.

1. **The "one fifth of Target Size" reference price does not exist.** I read the
   Feb 11 2026 filing text myself. The Reference Price **is the best bid**, and
   the multiplier is `0.5 ^ (ticks below the best bid)`. Under the filed rule
   REBATE_RISK's recommended quote — 3 ticks behind the touch — earns **4.2%**
   of the side, not the 10.3% its own rule gives it, and its central claim
   ("you never have to quote at the touch — that is the whole finding") is
   **exactly inverted**: under the filed rule you are paid essentially only at
   the touch.

2. **The replayed book throws away every snapshot's contents.** `extract.py`
   writes `orderbook_snapshot` rows as `price 0, qty 0`; `sim.py` responds by
   emptying the book. 1,350 of 4,030 Coin Race snapshots carry a real book
   (median 2,253 / 3,124 contracts) and all are discarded. Measured
   consequence: qualification **23.4% reconstructed vs 83.5% correct**, median
   YES depth **721 vs 6,002**. The 26.0% qualification rate under every dollar
   in REBATE_RISK Table C is wrong by 3.4x — **low**.

3. **The filed rule pays nothing below $1.00 per window, and the recommended
   configuration falls under it.** S=50 at d=3 earns a mean $0.84 per market per
   window. Only **23.4% of market-windows clear the $1.00 floor.** $/day falls
   from $403 to **$191**. The proposed live validation test (S=5, d=3) clears
   the floor in **0.6%** of windows and would return ~$0 — a **false negative
   by construction**.

4. **The pro-rata model does not survive one rival re-quote.** A rival who posts
   **Target Size (1,000) one tick inside the touch** takes our share from 26.6%
   to **exactly 0.00%** — under the filed rule the qualifying walk stops at
   their level and every other bid is excluded from scoring entirely. That costs
   them ~$380–510 of collateral against a $9,600/day pool. It is inside our own
   $1,000 budget, and it is inside everyone else's.

**Net: no configuration in either report is a number I would fund.** What
survives is smaller and duller — see §8.

---

## 1. THE RULE. I READ THE FILING.

Both target reports, `lipslice.py`, `HANDOFF.md` and `results/OVERNIGHT.md` all
state the scoring rule as:

> Reference Price = walking down from the best bid, first price level at which
> cumulative resting size reaches **one fifth** of Target Size. Multiplier 1.0
> at or better than that price, else `0.50 ^ ticks`.

`FUNDING_ELIGIBILITY.md` (a third overnight job) disputes this. **I did not take
its word for it.** Its cited evidence file, `jobFUND\lip_cftc.txt`, is an
unextracted binary PDF — a grep of it returns zero hits for *everything*,
including "Reference Yes Price", so its "zero occurrences of *fifth*" proves
nothing. **That evidence is void.**

The real extracted text is `jobFUND\lip2.txt` (the Feb 11 2026 CFTC portal
submission). I read the scoring section directly. Verbatim, de-hyphenated:

> "Snapshots will be excluded if there is not two-sided liquidity (i.e., resting
> orders sufficient to meet the **Target Size** on each side of the market) at
> the time of the Snapshot."
>
> "First, Kalshi will initialize the Qualifying Yes Bids to the empty set. **If
> the highest yes bid price exists and is less than the highest possible price,
> it is assigned to the Reference Yes Price.** ... Kalshi will add the size
> available at the current bid price to the Qualifying Yes Total Size ... **If
> the Qualifying Yes Total Size is greater than or equal to the target size, the
> procedure is stopped here.** Otherwise, Kalshi will find the next highest yes
> bid price and repeat **without reinitializing** the Qualifying Yes Total Size,
> Qualifying Yes Bids, **or Reference Yes Price**. If no more bids exist, Kalshi
> will clear the Qualifying Yes Bids, as there were not enough bids to reach the
> Target Size."
>
> "each Qualifying Yes Bid is assigned a score equal to the **Discount Factor
> taken to the Nth power multiplied by its size, where N is the number of ticks
> between the Reference Yes Price and the price of the Qualifying Yes Bid**."
>
> "Each Time Period Liquidity Provider Score is multiplied by the Time Period
> Reward, and **if the result is greater than or equal to $1.00, the result is
> paid out** to the corresponding user, rounded down to the nearest cent."

Independently counted in the same file: **"fifth" 0, "Target" 0 (rendered
"T arget"), "Reference" 12, "Qualifying" 44.** The word "fifth" is absent.

### What the filed rule actually says

| | brief's rule (both jobs) | **filed rule** |
|---|---|---|
| Reference price | first level where cum size ≥ **target/5** | **the best bid**, assigned once, never updated |
| Walk terminates at | target/5 | **Target Size** |
| Bids below the walk | scored at `0.5^ticks` | **not Qualifying — score zero** |
| Multiplier | 1.0 at or better than reference | `0.5 ^ (ticks below the best bid)` |
| Minimum payment | not modelled | **$1.00 per Time Period or nothing** |

### VERBATIM DISAGREEMENT

> REBATE_RISK.md: *"Kalshi's Liquidity Incentive Programme does **not** pay for
> being at the touch. It pays full credit at or above a reference price that
> sits a median four ticks below the touch... So the answer to 'you only get
> paid where you get run over' is **no — and that is the whole finding**."*

**I disagree.** Under the filed rule it pays full credit **only** at the touch
and halves every tick after. The answer to "you only get paid where you get run
over" is **yes**. That is the whole finding, with the sign reversed.

> REBATE_RISK.md, check C1: *"the premise was wrong, not the result"*

**I disagree.** The premise ("halving per tick means only the touch scores") was
right, and the check that overturned it was run against a rule with no verified
source and a book missing 80% of its depth.

### Two things I must not overstate

* The Feb 11 filing says the Program runs "**until the earlier of September 1,
  2026**, or the date that Kalshi amends or terminates". Today is 6 Sep 2026.
  **The filed terms nominally lapsed five days ago.** Live programmes still
  exist in the API, so a successor rule is in force and **I do not have it.**
* So: I have **disproved** that the brief's rule is the Feb-11 filed rule. I
  have **not** proved the Feb-11 rule is today's rule. Both jobs used a rule
  with *no* verified source; I have one with a *verified but possibly
  superseded* source. **Neither report should be funded until the live rule
  text is obtained.** The two rules recommend opposite quotes.

---

## 2. THE BOOK IS MISSING MOST OF ITS DEPTH — PROVED THREE WAYS

`extract.py` line for the snapshot channel writes `side=""`, `price=0`,
`qty=0.0` — the level arrays are never read. `sim.py` then does:

```python
if rank == 2:
    m.book = Book()          # <- snapshot: book emptied, contents never applied
```

`lipslice.py` states the justification as established fact:

> *"orderbook_snapshot messages for this series carry NO level arrays at all
> (just market_ticker and market_id), which is correct: a 15-minute market opens
> with an empty book. The book is therefore built from deltas alone."*

**This is false.** The arrays are named `yes_dollars_fp` / `no_dollars_fp`.

**Proof 1 — audit of every snapshot, 3 days, KXCRYPTOLEAD15M:**

```
snapshots                                     4,030
NON-EMPTY (carry yes_dollars_fp/no_dollars_fp) 1,350 = 33.5%
   median YES depth 2,253   NO depth 3,124   max 17,243
   already BOTH sides >= 1,000 target         1,277/1,350 = 94.6%
which snapshot within a market is non-empty:   ordinal 0 only  (all 1,350)
```

Each market gets exactly one snapshot carrying its opening resting book, ~48 s
after the window opens, and it is discarded.

**Proof 2 — deltas remove size the sim book never had** (`negcheck.py`,
20260905T00–02):

```
deltas applied                                          134,808
deltas that would drive a level NEGATIVE, deltas-only     1,359 = 1.0%
contracts removed that were never there                 485,102
```

A delta can only remove size that really existed. Every one of those contracts
was in the discarded snapshot.

**Proof 3 — a live authenticated orderbook, pulled during this review**
(`KXCRYPTOLEAD15M-26SEP061545-BTC`, 19:34 UTC): **YES depth 5,426, NO depth
6,191.** The correct reconstruction's medians (6,002 / 3,009) match; the sim
book's (721 / 964) do not.

### Measured consequence (`bookdiff.py`, 17,318 market-seconds)

| | A = `sim.py` (deltas only) | B = correct (snapshot applied) |
|---|---:|---:|
| median YES depth | 721 | **6,002** |
| median NO depth | 964 | **3,009** |
| median top-of-book size, YES / NO | 120 / 120 | 120 / 120 |
| median ref distance (brief's rule) | 4 / 4 | 4 / 4 |
| **QUALIFY, both sides ≥ 1,000** | **23.4%** | **83.5%** |
| share, S=50 d=3, brief's rule | 15.67% / 16.29% | 15.48% / 16.28% |

**The share is unaffected and the qualification rate is wrong by 3.6x.** The
missing depth is all deep in the book where `0.5^ticks` makes it worthless, so
it never showed up in a share check — it only ever showed up in the one number
that gates the whole pool.

Over a full day on the correct book (`filed.py`, 20260905, 164,421
market-seconds): **qualification 89.8%.**

### The artefact check the brief asked me to push on — it was the bug

`lipcheck.py` reported top-of-book agreement with the exchange's `ticker` feed
of 78.8% (bid) / 92.0% (ask), median difference 0.0, but **19.1% of seconds with
the bid more than 10% short**. I re-ran the identical test against both
reconstructions (`checkboth.py`, 16,755 matched market-seconds):

| | A = deltas only | B = snapshot applied |
|---|---:|---:|
| YES-bid top size within 2% of ticker | 81.6% | **99.5%** |
| YES-ask top size within 2% of ticker | 93.3% | **99.2%** |
| recon bid **>10% below** ticker | **16.2%** | **0.2%** |
| median total depth, YES / NO | 963 / 1,219 | **3,248 / 6,073** |

**The 19.1% anomaly was entirely the discarded snapshot.** It collapses to 0.2%.

**And the check could never have caught the real problem.** It compares
*top-of-book size*, which both books get right (120 = 120). The money depends on
*total depth* (qualification) and the *sum of discounted scores* (share), and
the `ticker` feed publishes neither. **The artefact check was aimed at a
quantity that was not broken.** That is the general lesson here, and it is
worth more than any number in this file.

---

## 3. RECOMPUTING THE MONEY — FILED RULE, CORRECT BOOK

`filed.py` / `floor.py`, 20260905, 478 market-windows, 147,626 qualifying
snapshots, both books rebuilt correctly.

### Share of side score, same book, both rules (S=50)

| d | **filed rule** | brief's rule | brief ÷ filed |
|---|---:|---:|---:|
| 0 | **26.64%** | 12.54% | 0.47 |
| 1 | 16.36% | 12.32% | 0.75 |
| 2 | 8.24% | 10.64% | 1.29 |
| **3** | **4.76%** | **10.30%** | **2.16** |
| 4 | 2.78% | 9.31% | 3.34 |

**The brief's rule understates the touch by 2.1x and overstates d=3 by 2.2x.**
It is not a level error, it is a *shape* error, and the shape is what the
recommendation was built on.

Hand-reconciled on the live BTC book pulled at 19:34 UTC
(YES: 38c×120, 34c×120, 31c×120, 27c×220, 23c×120, 19c×120, 15c×120, 11c×120, …):

* brief's rule — cum reaches 200 at 34c ⇒ ref = 34c; total score 256.78; our 50
  at 35c scores 50 ⇒ **16.30%**. Identical at d = 0,1,2,3,4 — under the brief's
  rule **queue position is worth literally nothing**, which alone should have
  been a red flag.
* filed rule — ref = 38c (best bid); walk 120→240→360→580→700→820→940→1060 ≥
  1000 stops at 11c; scores 120 + 7.5 + 0.9375 + 0.107 + 0.004 + … = 128.549;
  our 50 at 35c scores 50×0.5³ = 6.25 ⇒ **6.25/134.80 = 4.64%**; at the touch
  50/178.549 = **28.0%**.

### THE $1.00 FLOOR — never modelled by anyone

Payout per market-window = $20 × Time Period score. Below $1.00 it is **not
paid at all**, so any configuration averaging under a 5% share is worth zero.

| S | d | mean share | $/mkt/win | **windows ≥ $1** | $/day no floor | **$/day with floor** |
|---|---|---:|---:|---:|---:|---:|
| 5 | 3 | 0.66% | 0.133 | **0.6%** | 64 | **8** |
| 5 | 0 | 4.63% | 0.926 | 26.4% | 444 | 211 |
| 10 | 3 | 1.17% | 0.235 | 2.3% | 113 | 21 |
| 10 | 0 | 7.98% | 1.597 | 86.2% | 766 | 709 |
| 25 | 3 | 2.43% | 0.487 | 9.4% | 234 | 76 |
| 25 | 0 | 15.96% | 3.192 | 100.0% | 1,532 | 1,532 |
| **50** | **3** | **4.20%** | **0.840** | **23.4%** | **403** | **191** |
| 50 | 2 | 7.40% | 1.480 | 72.2% | 710 | 643 |
| 50 | 1 | 15.70% | 3.139 | 99.0% | 1,507 | 1,504 |
| **50** | **0** | **25.77%** | **5.154** | **100.0%** | **2,474** | **2,474** |
| 100 | 3 | 7.22% | 1.445 | 70.7% | 693 | 625 |
| 100 | 0 | 38.82% | 7.763 | 100.0% | 3,726 | 3,726 |
| 300 | 0 | 61.55% | 12.310 | 100.0% | 5,909 | 5,909 |

**The floor bites hardest exactly at the recommended configuration.** S=50 d=3
loses **53% of its rebate** to a threshold neither report mentions.

**And it kills the proposed validation test.** REBATE_RISK's next step is *"one
window, five coins, S = 5 contracts, 3 ticks back. Peak capital $25. That is
enough to confirm a payout lands."* Measured: S=5 d=3 clears $1.00 in **0.6% of
windows**. **The test is designed to pay zero and would be read as "LIP does not
pay."** If the operator runs one live test, this is the single most expensive
mistake in either report — it burns the one thing replay cannot establish.

### A correction that runs the other way, and I state it plainly

All three jobs multiply the payout by the qualification rate
(`lipslice.py`: `per = sh * PERIOD_REWARD * (inc/tot)`; `econ.py`:
`per_win = qr*(...)`). **That is not in the filed rule.** The denominator is
"the sum of all Snapshot Liquidity Provider Scores"; an excluded snapshot
contributes zero to numerator *and* denominator, so it **cancels**. The full $20
is distributed among whoever is present during qualifying snapshots. The tables
above therefore carry **no** qualification haircut. This makes the numbers
*larger*, and I report it because it is what the filing says.

### THE ARITHMETIC IS ABSURD, AND THE ABSURDITY IS THE POINT

The corrected model says **$284 of collateral and 50 contracts a side takes 26%
of a $9,600/day pool — $2,474/day, 871%/day on capital.** I do not believe that
for a moment, and neither should anyone. It is not a discovery of free money; it
is a **model that has stopped tracking reality**, and §4 says where.

For completeness in the units the operator asked for:

| configuration | $/contract/day | peak capital | % return/day |
|---|---:|---:|---:|
| REBATE_RISK headline (S=50 d=3, its own numbers) | $0.564 | $254 | 111% |
| same order, filed rule + correct book, no floor | $0.806 | $254 | 159% |
| same order, **filed rule + correct book + $1 floor** | **$0.382** | $254 | **75%** |
| filed rule at the touch (S=50 d=0) | $4.95 | ~$284 | 871% |
| **after one rival posts 1,000 one tick inside** | **$0.00** | $254–284 | **0%** |

---

## 4. DISPLACEMENT — THE MODEL DIES ON CONTACT

My brief: *"at 50 contracts we would be 11.6% of the side and at 300 we would be
40% — the pro-rata model assumes we displace nobody, and that is false at those
sizes."* It is worse than that. Under the filed rule the figure at S=50 is not
11.6% but **26.6%**, and the defence is not a haircut, it is a switch.

Measured over all 147,626 qualifying snapshots (`floor.py`), S=50 at the touch:

| incumbent's response | cost to them | our share | vs base | our $/day |
|---|---|---:|---:|---:|
| none (both reports' assumption) | — | 26.64% | 1.00 | 2,558 |
| joins us with 50 more at the touch | ~$25 | 20.00% | 0.75 | 1,920 |
| posts 120 **one tick inside** | ~$46 | 10.75% | 0.40 | 1,032 |
| **posts 1,000 (= Target Size) one tick inside** | **~$380–510** | **0.00%** | **0.00** | **0** |

The last row is structural, not marginal. The filed walk **stops** as soon as
cumulative size reaches Target Size. A single participant resting Target Size at
the best bid is the entire Qualifying set: they take 100% of that side and
**every other resting order on the book scores nothing at all.**

Under the brief's rule the same attack is cheaper still. Hand-computed on the
live BTC book, our 50 at 35c starting from 16.30%:

| incumbent's move | their cost | our share |
|---|---|---:|
| move their 34c order to 36c | **$2.40** | 9.29% |
| add 80 contracts at the 38c touch | **$30.40** | 2.91% |
| post 200 one tick inside at 39c | **$78** | 1.17% |

**Under either rule, our entire claim is erased for two figures of dollars.**

Two further things neither report says:

* **The incumbent's observed behaviour is inconsistent with both rules.** They
  rest ~120 at the touch and a 3c-spaced ladder of 120s down to 1c — 5,426
  contracts scoring 128.5, an efficiency of 2.4%. Under *either* rule the
  dominant move is to consolidate at the best bid. Nobody locks up ~$1,000 to
  earn 2.4% score efficiency **on purpose**. Either they are not playing LIP at
  all (a vanilla maker whose ladder exists for other reasons), or **the rule in
  force is neither rule we have modelled.** Both possibilities are bad for a
  model that assumes we can read the denominator off the book.
* **The filed rule contains a discretionary kill switch aimed at exactly this
  strategy.** Verbatim: *"Kalshi... shall retain the right to revoke participant
  status if Kalshi's Chief Regulatory Officer concludes... that a participant's
  participation in the program is **abusive or in any way inconsistent with the
  purpose of the Program**"*, the stated purpose being *"to increase liquidity
  on the central limit order book"*. REBATE_RISK's recommended quote is
  explicitly chosen because it **minimises executable liquidity** — 3 ticks back
  precisely to cut fills 60%. That is not a haircut risk. It is a zero, and it
  is unmentioned.

---

## 5. "IS THE TARGET SIZE EVER ACTUALLY REACHED?" — YES, AND IT IS THE ONE THING BOTH REPORTS GOT BACKWARDS

My brief asks whether any claimed pool survives this question. On Coin Race it
survives **more strongly than either report claimed**, and I have three
independent sources:

1. Correct tape reconstruction, full day: **89.8%** of market-seconds qualify.
2. Live REST orderbooks (INCENTIVE_FAMILIES, 1,040 snapshots): 64.5%, second
   window 100%; my own live pull at 19:34 UTC: 5,426 / 6,191 against a 1,000
   target.
3. **The exchange's own `paid_out` flag**, from the authenticated endpoint —
   6,220 ended KXCRYPTOLEAD15M programmes, **5,402 paid = 86.8%**, and by date:

```
2026-08-30 100.0%   2026-09-02 100.0%   2026-09-04 100.0%
2026-08-31 100.0%   2026-09-03 100.0%   2026-09-05  26.0%  <- flag lag
2026-09-01 100.0%                       2026-09-06   2.5%  <- flag lag
```

Steady state **97.5–100%**; the last two days are the flag landing ~1–2 days
after the window, not non-payment.

So HANDOFF's **28.9%** and REBATE_RISK's **26.0%** are both artefacts of the
discarded snapshot, and:

### VERBATIM DISAGREEMENT

> REBATE_RISK.md, unpriced risk #2: *"**NOBODY HAS EVER SEEN A PAYMENT.** Every
> live programme reads `paid_out: false`. The pool is confirmed to exist; it is
> not confirmed to land in an account."*

**Refuted, from data job 2 had already pulled.** Across the exchange
**165,124 of 176,914** programmes read `paid_out: true`; for Coin Race, 5,402 of
6,220 ended windows, including windows ending 2026-09-06T04:15Z. Risk #2 looked
only at programmes that had **not yet ended**, which of course read false. That
is half a comparison reported as a finding, and it is the *most* pessimistic
line in the report — it happens to be wrong in the direction of caution, but it
is still wrong.

> REBATE_RISK.md, unpriced risk #4: *"Only 26.0% of snapshots qualify... 74% of
> the pool is never paid to anyone."*

**Refuted.** ~90% qualify and ~99% of windows pay out. And under the filed rule
the qualification rate does not scale the payout at all.

> REBATE_RISK.md, unpriced risk #1: *"LIP requires a verified SSN on file above
> IRS reporting thresholds... If the operator's account does not meet this,
> every number above is zero."*

**Overstated.** The filed Eligible Participants clause excludes only *(i)*
Kalshi affiliates, *(ii)* members with a Market Maker Agreement, *(iii)* IBs,
FCMs and their customers. **No SSN condition appears in the filing.** An SSN is
a 1099 reporting condition on *receiving* money above a threshold, not a gate on
*participating*. Still worth confirming with the operator — but it is not the
"nothing else on this idea is worth an hour" blocker the report makes it.

---

## 6. INCENTIVE_FAMILIES — RECOMPUTED

`econ.py` computes `per_win = qr * (shY*10 + shN*10)` with `analyse()` placing
our order **at the brief's reference price**, a median 4 ticks below the touch.
The arithmetic reconciles internally — 0.645 × (0.148+0.277) × $10 = $2.74 per
market-window, × 5 × 96 = **$1,315/day**, matching the reported $1,318 — but on
two wrong inputs.

For **the same physical order** (4 ticks below the touch, S=100):

| | INCENTIVE_FAMILIES | this review |
|---|---:|---:|
| share of side score | 21.3% blended | **4.72%** (filed rule) |
| qualification multiplier | ×0.645 | **×1.0** (cancels in the filed formula) |
| $/market/window | $2.74 | **$0.944** |
| $/day (5 mkts × 96) | **$1,318** | **$453**, before the $1.00 floor |
| % return on ~$415 | 318% | 109% |

(I measured the floor's bite at S=100 **d=3** — 70.7% of windows clear $1.00. I
did **not** separately measure it at d=4, which is strictly worse. So $453 is an
upper bound and the floor takes an unmeasured further bite out of it.)

**Overstated 2.9x for the same order**, before displacement — after which it is
zero.

### VERBATIM DISAGREEMENT

> INCENTIVE_FAMILIES.md: *"Even after a 90% haircut for all six, this is
> $132/day on ~$415 — still larger than pin's whole measured range ($30–101/day).
> That is the finding."*

**I disagree with the method, not just the number.** Four of the six listed
risks are not haircuts — they are switches that pay 0x or 2x (eligibility;
side split; rule identity; competitive response). Averaging a binary into a
"90% haircut" manufactures a floor that does not exist. The correct statement is
**"this is somewhere between $0 and $1,300/day and the width is not sampling
error."** Comparing that floor to pin — which is measured on realised fills at
settlement and does not depend on a subsidy rule anyone can change — is not a
like-for-like comparison.

> INCENTIVE_FAMILIES.md, uncertainty #1: *"The 50/50 side split is assumed, not
> verified... If the split is not 50/50 this is wrong by up to 2x either way."*

**This one I resolve in the report's favour.** The filed formula defines a
user's snapshot score as *"the sum of all Normalized Qualifying Yes Scores and
Normalized Qualifying No Scores"*, and each side's normalized scores sum to 1.0.
A qualifying snapshot therefore allocates exactly 2.0 across all users, 1.0 per
side. **The 50/50 split is exact, by construction.** `discount_factor_bps=5000`
is the 0.5 per-tick decay — the report's own guess — and is not a side split.
Uncertainty #1 can be closed.

### What survives in INCENTIVE_FAMILIES

* **The family rate table survives and is the best thing in either report.**
  $/hour/market is arithmetic on `period_reward` and period length from the
  authenticated endpoint; no book, no share model, no rule assumption.
  KXDIESELD at $7.80/hr vs the 15M families at $80/hr does not depend on
  anything I have refuted. **The brief's premise really was inverted.**
* **"KXTTELITEMATCH and KXALBUMSTREAMS never qualify"** — measured on live REST
  books, which are correct. Under the filed rule a side that never meets Target
  Size clears the Qualifying set and pays nobody. **Survives.**
* **The 176,914-program pull and the `volume` programme's death (2026-05-12).**
  Survives; it is API arithmetic.
* **The two sampling bugs caught (`status=open` staleness, newest-first sort).**
  Real, and honestly reported.

---

## 7. WHAT I DID NOT RE-RUN, AND WHAT THAT COSTS

* **The fill/toxicity engine.** `sim.py`'s queue model computes the size ahead
  of us from the same broken book. At the touch this barely matters (top-of-book
  size is identical, 120 = 120), but at **d ≥ 1 the size at better prices is
  understated several-fold**, so the fill counts in Table A/B at d ≥ 1 are
  **overstated** and the "fill P&L flips positive at d ≥ 1" result rests on
  them. I did not requantify it — it needs the whole engine re-run on a fixed
  book. **Report Table B's fill column as unverified, not as measured.**
* **The model-free taker P&L** (`takerpnl.py`) splits cleanly: the core
  "taker loses 1.309c gross to settlement, 2.263c after fees" uses only trades +
  settlements and **survives**. The "price paid vs mid −3.957c" and the
  ticks-past-the-touch table need a mid and a touch from the broken book and are
  **contaminated** (top-of-book agreement was 81.6% bid / 93.3% ask).
* **The sum-to-100 arbitrage check** uses the broken book's best bid/ask, but
  its conclusion rests on fee arithmetic (5 legs at p≈0.2 cost ≈5.6c against a
  median 1c dislocation), which is independent. **Survives.**
* **Peak capital and the 96x turnover.** I did not attack these; the arithmetic
  reconciles and the unit (peak concurrent resting collateral) is legitimate,
  though flattering. One measured wrinkle: the `paid_out` flag lands **1–2 days**
  after the window, so the rebate is a receivable, not same-day cash.
* **I could not obtain the rule in force today.** The Feb 11 filing lapsed 1 Sep
  2026; a 4 Aug amendment is referenced with a CFTC review closing **14 Sep
  2026**. This is the single largest open item and it is not a coding problem.

---

## 8. RANKED BY RELIABILITY OF THE MONEY

**1. Nothing here. `pin` remains the only measured money.** It depends on
realised fills at settlement, not on a subsidy whose rule text I could not
obtain, whose filed version lapsed five days ago, and which is under CFTC review
closing in eight days. Its $30–101/day on $50–268 is small and it is *real* in a
way none of this is.

**2. The family rate table (INCENTIVE_FAMILIES).** Pure API arithmetic. Tells
you where *not* to spend time (KXDIESELD, KXRAIN, KXAAAGASD) — worth an hour
saved, worth $0 directly.

**3. "The pool exists and is paid."** 165,124 `paid_out: true`, 97.5–100% of
Coin Race windows. Real, and better established than either report said. It says
nothing about **our** share.

**4. The LIP share model, either version.** Not fundable. It requires (a) a rule
text nobody has, (b) that no rival re-quotes for two figures of dollars, and (c)
that Kalshi's CRO does not read a deliberately-unfillable quote as "inconsistent
with the purpose of the Program".

**Does this need the market to be WRONG?** No — and that is the trap. LIP is a
subsidy, not a mispricing, so it needs no edge over anyone. What it needs
instead is for **every other participant to keep leaving money on the table
while we take it**, and for the rules committee not to change its mind. That is
a *weaker* footing than needing the market to be wrong, not a stronger one: a
mispricing does not re-quote when you arrive, and a mispricing has no CRO.

---

## 9. WHAT WOULD MAKE **THIS REVIEW** FICTION, AND WHAT THE CHECK SAID

| # | If true, this review is wrong | what I measured | verdict |
|---|---|---|---|
| A1 | The snapshots really are empty and my "missing depth" is double-counting | 1,350/4,030 carry `yes_dollars_fp`; 1,359 deltas would go negative without them, removing 485,102 phantom contracts | **holds** |
| A2 | My reconstruction is the broken one | live authenticated orderbook 5,426/6,191; ticker top-of-book agreement 99.5%/99.2% (vs 81.6%/93.3%) | **holds** |
| A3 | I mis-read the filing / read the wrong document | read `lip2.txt` (Feb 11 2026 CFTC portal submission) directly; quoted verbatim; "fifth" appears 0 times, "Reference" 12, "Qualifying" 44 | **holds** |
| A4 | FUNDING_ELIGIBILITY's grep evidence was sound and I duplicated it | its cited file `lip_cftc.txt` is an unextracted binary PDF returning 0 hits for *every* term — **that evidence is void**; I used a different file | **their evidence void, conclusion independently confirmed** |
| A5 | The filed rule is superseded, so my recomputation is moot | filing self-expires 1 Sep 2026; successor not retrieved | **CONCEDED — this is the review's own biggest hole** |
| A6 | The $1.00 floor applies per programme, not per window | `period_reward` 200000 (=$20) is per 15-min market-window; "Time Period Reward" is the same field | **holds, but rests on that identification** |
| A7 | The displacement result is a modelling choice, not the rule | it follows directly from "the procedure is **stopped here**" once cumulative size ≥ Target Size | **holds under the filed rule; under the brief's rule the same attack costs $2.40** |
| A8 | One day is not enough | 20260905 only: 478 market-windows, 164,421 market-seconds, 147,626 qualifying. Book comparison and artefact check on two further independent slices | **single-day; the qualification and rule findings are structural, the $/day levels are not multi-day** |

---

## 10. NEXT STEP — ONE THING, AND IT IS NOT CODE

**Get the LIP rule text in force today.** Not an API call — Kalshi's Help Center
page or support, plus the 4 Aug 2026 CFTC amendment. Until it exists, the two
candidate rules recommend **opposite quotes** (at the touch vs 3 ticks back) and
differ 2–4x on every dollar. No quoting bot, no funding conversation, and no
further replay is worth an hour before that.

Then, and only then, the discriminating live test — **but sized above the $1.00
floor**, which the currently-proposed one is not:

* Post **S = 50 at the best bid** in one market and **S = 50 three ticks back**
  in another, same window, and compare the credits actually received.
* Filed rule predicts ~26.6% vs ~4.2%, and the 3-ticks-back leg to **pay
  nothing at all** (below $1.00 in 77% of windows).
* Brief's rule predicts ~12.5% vs ~10.3% and both legs paid.
* Peak capital ~$100. **This settles the rule, the floor, and eligibility in one
  window**, which no amount of replay can do.
* The currently-proposed S=5/d=3 test resolves none of it and returns $0 by
  construction.

Before any of that: **fix `extract.py` to read `yes_dollars_fp`/`no_dollars_fp`
and `sim.py` to apply the snapshot instead of clearing the book**, and delete
the false claim in `lipslice.py`'s docstring and in `HANDOFF.md` that Coin Race
snapshots carry no levels. Every LIP number in the repo is downstream of it.

---

## FILES

| path | what |
|---|---|
| `C:\Users\Joe\AppData\Local\Temp\kals-work\advl1\bookdiff.py` | rebuilds the book both ways on the same tape; the qualification 23.4% vs 83.5% table |
| `...\advl1\negcheck.py` | proves the deltas-only book is missing state (485,102 phantom contracts) |
| `...\advl1\checkboth.py` | re-runs lipcheck's artefact test against both reconstructions |
| `...\advl1\filed.py` | filed rule vs brief's rule, share and $/mkt/win, S×d sweep, full day |
| `...\advl1\floor.py` | the $1.00 minimum-payment test and the displacement test |
| `...\advl1\floor.out` | its output |
| **source read** `...\kals-work\jobFUND\lip2.txt` | the extracted Feb 11 2026 CFTC filing — the only verified rule text on disk |
| **void** `...\kals-work\jobFUND\lip_cftc.txt` | unextracted binary PDF; greps against it are meaningless |

**Collectors: `kalshi_collector.py` (PID 3381772) and `crypto_feeds.py`
(PID 3385232) were alive before, during and after every job here — same PIDs,
created 10:57, never restarted. Free disk 51.3 GB, free RAM 3.8–4.1 GB
throughout. Nothing was killed. No orders were placed; every API call was an
authenticated GET.**
