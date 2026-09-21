# The Coin Race, re-measured from the book — 2026-09-21

Sources, in the standing order of preference: the **index** (1/sec settlement
prints), the **ticker** channel (top of book with sizes), the **trade tape**.
No replay, no pinsim, nowhere. Winners are recomputed from the index and agree
with Kalshi's own `result` **127 of 127**.

New stages, each with a self-test that plants an answer and fails if the
estimator misses it, plants nothing and fails if it finds something, and
parses a line copied verbatim off the tape so a wire-format change cannot pass
silently: `research/racebook.py`, `research/racemaker.py`,
`research/raceclose.py`, `research/racegrid.py`.

---

## THE ONE-LINE ANSWER

The Coin Race was never unprofitable. **−$807.58 was one broken configuration
from 2026-09-15 that bought both sides of the same market.** Under the current
flags the paper arm is **78 of 78 events, 110 legs, zero losing legs**.

On 25 days of resting book, with the forecast **staled two seconds** so it
cannot read the future, the best rule found is:

> **tau ≤ 40 · price ≥ 90c · one position per race · 50–100 contracts**
> 977 races, **4 losing races (0.4%)**, **+2.2 to +2.3c a contract**,
> **$16–26 a day.** Break-even loss rate ≈ 2%; observed 0.4%.

**That is a ceiling on resting offers, not a fill rate.** The single number
that decides whether it is real is our own live loss rate, and only a penny
test produces it.

---

## 1. The −$807.58 was one dead configuration

| arm | events | won | lost | P&L | flags |
|---|---|---|---|---|---|
| `arm2` (09-15) | 12 | 7 | **5** | **−$1,559.72** | no price floor, no tau cap, no per-race cap |
| `arm3` (current) | 78 | 78 | **0** | **+$752.14** | `--tau-max 30 --min-price 0.90` |

arm2's mechanism was not bad forecasting — every leg it bought had a positive
stated edge. As the lead flipped it bought YES on a coin and later bought NO on
the **same ticker**, at prices summing well over $1.00:

**$1,306.03 of guaranteed loss locked in before those races were decided** —
84% of its entire deficit, across 12 markets in 7 races. The −$988 race held 12
positions and ended holding BTC 851 YES + 371 NO *and* ETH 500 YES + 851 NO:
$1,825 staked on a race it could win at most half of.

It cannot recur under `--min-price 0.90`: a YES and a NO on one ticker would
both have to be offered at 90c+, and the two sides of a Kalshi book sum to
about $1.00–1.05. **A hard one-position-per-race cap is still the right belt
and braces** — `run_rule` in `racegrid.py` enforces it and a self-test fails if
a second position is ever opened.

The current live paper arms **do not have that cap**: the `--model fair` arm
took 2 positions in 13 of its 39 races. It has still not lost a race
(39 of 39, +$351.01), and both sides are profitable (YES 32 legs +$168.06, NO
24 legs +$182.95), but the cap must exist before real money.

---

## 2. The basket constraint — riskless, and DEAD

Five legs, exactly one settles YES, so a basket of all five is worth exactly
$1.00 whatever the coins do. Asks summing under a dollar would be riskless
money with no forecast in it at all.

| min size | buys | sells | ceiling | per day | median run |
|---|---|---|---|---|---|
| ≥ 1 | **0** | 20 | $5.14 | **$1.72** | 2 s |
| ≥ 10 | **0** | 15 | $4.67 | $1.56 | 2 s |
| ≥ 50 | **0** | 7 | $3.89 | $1.30 | 1 s |

**Killed.** Not one buy-side occurrence in three days, and the median chance
lives two seconds — not long enough to leg into five markets over REST.

What the scan *did* find is the shape of this book:

| | n | p05 | median | p95 |
|---|---|---|---|---|
| five asks summed, tau ≤ 60s | 2,144 | 1.050 | **1.160** | 1.270 |
| five bids summed, tau ≤ 60s | 127 | 0.960 | **1.000** | 1.010 |

**The whole spread is on the ask side.** The bids sum to fair; the asks sum
16–24c over. Also note the 127: near the close it is almost never true that all
five legs even have a bid, which kills selling beaten legs as a business.

---

## 3. So who collects that spread? The makers **lose $2,850 a day**

Every trade's maker is the exact mirror of its taker and the outcome is
settled, so the passive side's profit is arithmetic. Makers pay no fee here, so
this is net.

**Seven days, 60,920 trades, 1,559,334 contracts: −$20,101.58 = −1.29c a
contract.** Negative on six of the seven days.

| time to close | contracts | maker $ | per contract |
|---|---|---|---|
| 1–15 s | 33,425 | +$16.72 | +0.05c |
| 16–30 s | 45,964 | +$2,474.91 | +5.38c |
| 31–60 s | 90,647 | −$1,046.97 | −1.15c |
| 61–180 s | 296,797 | −$5,161.36 | −1.74c |
| 181–900 s | 1,092,501 | −$16,384.89 | −1.50c |

**DO NOT QUOTE THIS BOOK.** That kills market-making the race and, with it,
the "sell lottery tickets on the beaten legs" idea.

The takers are the ones being paid. **We are a taker.**

---

## 4. THE TRAP: the floor-free rule is 100% look-ahead

A trade or quote stamped inside second *S*, matched to a forecast built from
prints through second *S*, can see a fraction of a second of the future. In a
race half of which is decided by under 7 basis points, that fraction is
everything. So every rule below is run twice — at lag 0 and with the forecast
**staled 2 seconds**.

25 days, 2,191 priced races, one position per race, uncapped:

| rule | lag 0 | **lag 2 (honest)** |
|---|---|---|
| **no price floor**, edge ≥ 0c | +1.48c/ct, **+$101.92/day** | −1.47c/ct, **−$101.89/day** |
| no price floor, edge ≥ 2c | +0.86c/ct, +$40.90/day | −2.45c/ct, −$117.14/day |
| **price ≥ 90c**, edge ≥ 0c | +1.76c/ct, +$93.94/day | **+1.47c/ct, +$71.20/day** |
| price ≥ 90c, edge ≥ 2c | +3.31c/ct, +$55.30/day | +2.86c/ct, +$44.75/day |

**A perfect sign flip on the floor-free rule, and a 24% haircut on the 90c
rule.** Removing the price floor looked like four times the money and was
entirely a sub-second timing illusion: a 40c leg's value is decided by the next
one or two seconds, a 97c leg is already decided.

Two consequences, both counter-intuitive and both now evidenced:

1. **`--min-price 0.90` is the strategy, not a safety rail.** Keep it.
2. **On this product, more "edge" is a danger signal, not an opportunity.**
   Demanding edge ≥ 2c with no floor makes the loss rate *worse* (64.9% of
   races) because more edge means a cheaper leg means more dependence on
   information we will not have in time.

### The price floor, swept (lag 2, uncapped)

| floor | races | bad | bad % | avg paid | c/contract | $/day |
|---|---|---|---|---|---|---|
| none | 1,460 | 638 | 43.7% | 50.7c | −1.47c | −$101.89 |
| ≥ 50c | 1,348 | 114 | 8.5% | 88.6c | +0.50c | +$26.41 |
| ≥ 80c | 1,328 | 26 | 2.0% | 95.5c | +2.09c | +$103.25 |
| **≥ 90c** | 1,310 | **12** | **0.9%** | 97.1c | +1.47c | +$71.20 |
| ≥ 95c | 1,291 | 8 | 0.6% | 98.0c | +1.32c | +$60.75 |

---

## 5. The forecast separates cleanly — on the trades that happened

Seven days of trade tape, every taker YES purchase, scored as a taker **with
fees**, clustered by close, forecast staled 2 s.

**tau ≤ 60, price ≥ 90c:**

| population | trades | races | bad races | contracts | won | NET c/ct | NET $ |
|---|---|---|---|---|---|---|---|
| ALL takers | 2,775 | 435 | 7 | 41,555 | 97.2% | −1.14c | −$472 |
| model edge ≥ 0c | 1,992 | 386 | **0** | 23,298 | **100.0%** | **+1.48c** | **+$344** |
| model says OVERPAID | 538 | 145 | 7 | 13,462 | 91.3% | −6.41c | −$864 |

The same trades. The model kept every winner and dropped every loser. That is
the identification result: the average taker at 90c+ loses; ours does not.

---

## 6. Capacity — the real constraint

The trade tape only shows what somebody else lifted; the ticker shows the offer
itself, with its size, whether or not anyone took it.

Model's leader at that second, 927 races:

| tau | races with an offer | median ask | median size | p90 size | ask < 98c |
|---|---|---|---|---|---|
| 1 s | 11% | 99.0c | 13 | 172 | 5% |
| 10 s | 20% | 98.0c | 11 | 153 | 12% |
| 15 s | 26% | 98.0c | 10 | 120 | 17% |
| 30 s | 43% | 98.0c | 16 | 120 | 29% |
| 60 s | 64% | 96.0c | 24 | 120 | 54% |

**Inside 15 seconds only a quarter of races have any offer on the leader and
the median one is ten contracts.** This is what caps the business.

### Is the big offer the bad offer?

| offer size | races | losses | loss % | c/contract |
|---|---|---|---|---|
| 1–5 | 128 | 2 | 1.6% | +2.21c |
| 5–15 | 74 | 2 | 2.7% | +2.26c |
| 15–40 | 32 | 1 | 3.1% | +3.19c |
| 40–100 | 19 | 0 | 0.0% | +15.21c |
| **100–150** | 93 | **8** | **8.6%** | +11.11c |
| 150+ | 21 | 0 | 0.0% | +3.40c |

**Not a clean signal.** The 100–150 bucket is 3–5x worse than the small ones,
but 150+ is spotless, so this is 93 races and 8 losses, not a law. Worth
watching, not worth a rule yet.

---

## 7. THE RULE, and where it lands

25 days, 2,191 priced races, 90c floor, one position per race, lag 2:

| tau ≤ | cap | races | bad | bad % | c/contract | $/day |
|---|---|---|---|---|---|---|
| 20 | 50 | 587 | 1 | 0.2% | +2.16c | +$9.89 |
| 20 | 100 | 587 | 1 | 0.2% | +2.23c | +$16.04 |
| 30 | 50 | 778 | 3 | 0.4% | +1.87c | +$11.07 |
| 30 | 100 | 778 | 3 | 0.4% | +1.87c | +$17.21 |
| **40** | **50** | 977 | 4 | 0.4% | **+2.20c** | **+$16.13** |
| **40** | **100** | 977 | 4 | 0.4% | **+2.29c** | **+$25.77** |
| 45 | 100 | 1,074 | 7 | 0.7% | +1.59c | +$20.32 |
| 60 | 100 | 1,310 | 12 | 0.9% | +1.19c | +$19.09 |

**tau ≤ 40 is the peak** — more money than 30 at the same 0.4% loss rate, and
both 45 and 60 are worse. The live arm's `--tau-max 30` is close to right and
slightly short.

**All twelve losses in the tau ≤ 60 run happened at tau 42–57.** Not one inside
tau 42. At tau ≤ 30 the whole loss list over 25 days is three races:

```
09-06 21:30Z tau 24 SOL no @94c x50 edge +4.6c $-47.20
09-01 20:30Z tau 30 ETH yes @91c x50 edge +3.4c $-45.79
09-04 12:30Z tau 30 SOL no @98c x1  edge +0.4c $-0.99
```

**The last 14 days have zero losing races and every day positive.**

### The arithmetic that decides it

At tau ≤ 30 the rule pays 97.23c on average and nets **1.875c a contract**.

> **Break-even loss rate: 1.77%. Observed: 0.39%.** About 4.5x of headroom.

**And here is the thing that could take all of it.** The one time this project
compared a tape loss rate to its own live fills, at the pin gate, the tape said
0.11% and live said **3.4%** — a shift of **+3.3 percentage points**. Apply the
same absolute shift here and 0.39% becomes 3.7%, which is **double the
break-even**. The rule would lose.

That is the whole risk, it is not reducible by more tape analysis, and the only
instrument that measures it is our own fills.

---

## 8. What changed, and what is running

**Changed:** nothing live. `pinrun --live` is untouched; no flag, no threshold,
no version entry.

**Started (paper only; `pinracearm` cannot send an order and its own self-test
proves there is no order path):** three arms differing from the control in
exactly one setting each —

| arm | flags | question |
|---|---|---|
| `racectl` | fair, tau 30, ≥90c, edge 2c, one-per-band | the control |
| `racetau40` | …`--tau-max 40` | is 40 really better than 30 |
| `raceedge0` | …`--min-edge 0.00` | is the 2c edge bar costing count |

**`pinracefair.py`:** the fat-tail grid started at 1.0 and the fit half chose
1.0 — the smallest value offered, i.e. a truncation, not an optimum. The grid
now runs to 0.5 and the fit half picks **0.60**, an interior optimum, improving
fit log loss 8.8%. **NOT DEPLOYED:** out of sample the sharper model is better
on photo finishes and on Brier and *worse* on the confident legs, which is
exactly where we trade. `pinracearm` calls `win_probs` with a literal 1.0, so
no running arm changed.

---

## 9. What is still unknown

1. **Our own fill rate and our own loss rate. Everything above is a ceiling.**
2. Whether the 100–150 contract offers are systematically the bad ones (8.6%
   vs 1.6–3.1%, on 93 races).
3. Whether a per-race position cap changes the live arms' results — they do not
   have one, and 13 of 39 races took two positions.
