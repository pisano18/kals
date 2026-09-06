# Reply to both critiques — 2026-09-06

**Short version: you are right to disbelieve the number. The second critique
(the text one) is substantially correct and I concede its central point. The
first critique (the screenshots) is wrong on its central claim, and I can show
that from Kalshi's own data rather than by asserting it.**

---

## 0. Do I agree the returns look insane? Yes.

111%/day on capital is not a normal number. My prior should be — and is — that
it is wrong. The single most likely failure mode was that my **unit conversion**
was wrong, because every downstream figure multiplies by it. That is the first
thing I tested, and it is now closed. What is *not* closed is everything the
second critic raises.

---

## 1. What is now VERIFIED, from primary sources

### 1a. The units. `period_reward` is in 1e-4 dollars, so 200000 = $20.

Proven, not inferred, by an arithmetic coincidence that cannot happen twice by
accident:

| family | raw `period_reward` | markets | ÷10,000 × markets |
|---|---|---|---|
| `KXTRUMPACT` | **909090** | 11 | **$1,000.00** |
| `KXTRUMPENDORSEMENTS` | **1428571** | 7 | **$1,000.00** |
| `KXTRUTHSOCIAL` | 1000000 | 10 | **$1,000.00** |
| `KXMAMDANIEO` | 10000000 | 1 | **$1,000.00** |

`909090 = 10,000,000 ÷ 11` and `1428571 = 10,000,000 ÷ 7`. That is a $1,000
pool split N ways, in ten-thousandths of a dollar. Under the alternative
(`÷100`) these become $100,000 each — 100× Kalshi's documented ceiling.

### 1b. The pool is real, and it is paid.

`GET /incentive_programs`, **paginated via `next_cursor`** — this matters,
because the first page alone is all future windows and shows `paid_out: false`
everywhere. I made exactly that mistake earlier and wrongly reported "nothing
has ever been paid."

| | |
|---|---|
| programmes seen | **80,000** |
| `paid_out: true` | **68,805** |
| **total actually paid** | **$5,051,195** over 86.8 days |
| implied rate | **$58,171/day ≈ $1.75M/month** across all families |

$1.75M/month is large but entirely ordinary for a regulated exchange
bootstrapping liquidity across ~1,320 market families.

### 1c. The screenshot critique's central claim is refuted by measurement.

It says: *"Kalshi does not fund standalone $20 bills to 96 sequential markets a
day per coin ($1,920/day per coin). If it did, it would be handing out $9,600 a
day across 5 coins ($288,000 a month) on micro-crypto markets alone. The math
your AI is multiplying against is fundamentally inflated."*

**Kalshi is doing exactly that.** Coin Race, per calendar day, from the API:

| day | advertised | **actually paid** | paid % |
|---|---|---|---|
| 2026-08-26 | $9,600 | **$9,600** | 100% |
| 2026-08-30 | $9,600 | **$9,600** | 100% |
| 2026-09-01 | $9,600 | **$9,600** | 100% |
| 2026-09-04 | $9,600 | **$9,600** | 100% |

Across its 13 full days: **$9,477/day advertised, $8,294/day actually paid,
95–100% of programmes paid.** The "$288,000 a month" it presents as an absurdity
is roughly the real figure.

Its other errors, briefly:

- **"$1 to $1,000 per market, per day, not per 15 minutes"** — no contradiction.
  `KXCRYPTOLEAD15M-26SEP070000-HYPE` **is** a market. It lives 15 minutes and
  gets $20. That is $20 per market per day, comfortably inside the range. It
  conflated *market* with *series*.
- **"1,000 / 51,000 = 1.96% of market share"** — wrong denominator. Kalshi
  divides by **distance-weighted score**, not raw contracts, and the multiplier
  halves every tick. Measured on the live book: 4,737 raw contracts on XRP's yes
  side score **268.8**. Its 50,000-contract figure is also not measured — the
  citation on its own screenshot is "X".
- **"you must post ≥ target_size yourself"** (from the earlier screenshot) —
  false, and it is the most important detail in the programme. Verbatim from
  Kalshi: Target Size is *"the depth that must be resting on each side for a
  snapshot to count"* — **aggregate**. If its reading were right, none of this
  would be reachable at $1,000.

---

## 2. Where the SECOND critique is right, and I concede it

This one is much better argued and I am not going to defend against it.

### 2a. "You measured a static book." — CORRECT, AND IT IS THE STRONGEST POINT.

I measured the book as it was, then computed what our share *would have been*
had we been in it. That is not the same as what our share *will be* once we are
in it, because the other participants respond. I cannot refute this from
historical data, because we have never posted anything.

**I concede this fully.** What I can do — and have now launched — is bound it:
the tape contains thousands of natural experiments where *somebody else* added
size at the touch. Measuring what the rest of the book did in the next 1s/5s/30s
gives the book's empirical response function to exactly the action we would
take. That is not the same as observing a response to *us*, and I will say so
when the number arrives.

### 2b. "Inventory P&L is never subtracted." — PARTLY RIGHT, AND THE PART THAT IS RIGHT MATTERS.

Partly unfair: fill P&L *was* measured. Coin Race takers lose −1.309c/contract
gross to settlement, so the average maker earns +1.309c. But queue position
selects the bad fills — front-of-queue +0.560 c/ctr, back-of-queue **−1.462 to
−4.730** c/ctr.

But the criticism lands on **my headline**, and that is fair. The $282–348/day I
have been quoting is largely **rebate-only**. A mean fill P&L is not a
distribution, and the operator has $1,000, for whom the tail is the whole
question. Building the joint per-window distribution of (rebate, inventory P&L)
is now a running job, block-bootstrapped over whole **days**, not iid over
windows — an iid bootstrap already flattered this project once, putting the
1%-worst week at +$47.

### 2c. "Small capital cannot do this across five markets." — TESTABLE, AND BEING TESTED.

This is arithmetic plus simulation, and it determines the only parameter we
actually control: size. Running now: exact collateral rules, the maximum loss if
all five coins fill against us, and a ruin simulation at S = 10/25/50/100 with
block-resampled days, reporting probability of a 20% drawdown, a 50% drawdown,
and ruin.

**One fact that may matter more than any of this and nobody has checked:** on
Coin Race exactly one coin leads, so the five YES legs settle to **exactly
100c**. The five markets are therefore *not* independent — a move against us on
one coin may be a move *for* us on another. Whether the five-coin inventory is
naturally hedged or naturally correlated could be the single most important
number in the strategy, and it is being measured.

---

## 3. What remains genuinely unknown

1. **The book's response to us specifically.** Untestable without placing an
   order. Bounded, not eliminated.
2. **A factor of two.** Kalshi's rule says *"your snapshot score is your share
   of the yes side **plus** your share of the no side."* I implemented the
   **average**. If "plus" is literal, every figure doubles. I have taken the
   conservative half everywhere and flagged it rather than assume in our favour.
3. **Whether an unfunded account can even rest an order**, the minimum deposit,
   whether an SSN is required before rewards accrue, and whether API rate limits
   permit quoting ten books at one-second cadence. Being checked.

---

## 4. My honest position

The **pool** is verified: real, correctly sized, and paid at ~$8,294/day on Coin
Race. The **scoring rule** is verified verbatim, and my implementation had one
real bug (a flat tick where the grid is tapered) which I found and fixed — and
which had made us look *worse*, not better.

The **share** is measured but on an undisturbed book, and that is exactly the
assumption the second critic attacks. Until the impact and inventory
distributions land, **$282–348/day is a model of an undisturbed book, not a
trading result.** That phrasing is the critic's and it is fair.

I would not stake money on it today. I expect the honest number to be lower —
possibly much lower — and I would rather find that now than after funding.

**A clean kill found cheaply is a good outcome, and this project has said so
from the start.**
