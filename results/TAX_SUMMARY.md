# Trading record for tax preparation
## Kalshi event contracts - taxpayer resident in Virginia

*Generated 2026-09-13 21:14 UTC by `research/pintax.py`, from the trading system's own execution logs. Every figure is an executed transaction: nothing is modelled, estimated or netted.*

> **THIS IS A RECORD OF TRANSACTIONS, NOT TAX ADVICE.** It states what was bought, when, at what price, what fee the exchange charged, and what it settled for. How that is characterised is for the advisor to decide; nothing here presumes an answer.

## 1. Why this document exists

**Kalshi does not issue a comprehensive 1099-B for event contracts.** It issues a 1099-INT for interest, a 1099-MISC for referral credits, and 1099-B/1099-DA only for crypto transfers handled by its custodian. Event-contract gains are taxable whether or not a form is issued, so **this ledger is the primary record rather than a cross-check against one.**

## 2. What was traded

Binary event contracts on Kalshi, a CFTC-regulated designated contract market. Each contract settles at **$1.00** if the stated event occurs and **$0.00** if it does not.

- **Long only.** Every position was BOUGHT. Nothing was sold short.
- **Held to settlement.** No position was closed early; each was held to expiry and settled by the exchange.
- **Holding period is minutes.** Markets open and settle within 15 minutes, so every disposition is short-term.
- **A HEDGE leg is a separate purchase** of the opposite side of the same market, also held to settlement. It is its own line with its own price and fee. The pair pays exactly $1.00 per contract. Netting the two would understate both gross proceeds and total fees.

## 3. Totals

| | |
|---|---|
| settled legs | 298 |
| open legs, not yet settled | 8 |
| contracts bought | 6094.26 |
| gross cost | $5679.90 |
| exchange fees paid | $20.20 |
| gross proceeds at settlement | $5833.62 |
| **net profit/loss** | **$133.17** |
| winning legs / losing legs | 284 / 14 |

## 4. The three possible treatments, and the figure each needs

The IRS has published no guidance on prediction-market contracts, and no ruling settles whether this is gambling, capital gain, or Section 1256 property. **The advisor chooses; this supplies the number each choice requires.**

| treatment | form | figure it needs | value |
|---|---|---|---|
| Capital gain/loss | Form 8949 + Schedule D | net short-term gain, per lot | **$+133.17**, all short-term |
| Section 1256 | Form 6781 (60/40) | aggregate gain, plus year-end open positions marked to market | **$+133.17**, 8 open at generation |
| Gambling | Sch. 1 income + Sch. A losses | **gross winnings and gross losses SEPARATELY** | won **$294.29**, lost **$161.12** |

**Most published commentary holds that event contracts are NOT Section 1256 property**, because the code's list does not reach them. The question is open and 1256 is the most favourable of the three, so it is the advisor's call; the data supports either.

## 5. How much to hold back for tax

A common suggestion is a flat **28% of net profit**. On this ledger that is **$37.29**. It is offered here with the arithmetic that contradicts it, because a single percentage cannot be right across three treatments that differ by more than a factor of two.

**Two reasons a flat rate on NET understates the reserve:**

1. **Under the gambling treatment the tax is on GROSS WINNINGS, not net.** Winnings are income; losses are an itemised deduction capped at winnings. With the federal standard deduction there is no offset at all, so the base is **$294.29, not $133.17**.
2. **Section 1256 is the opposite** - 60% of the gain at long-term rates and 40% at ordinary, which is materially cheaper than either.

Virginia's top rate is 5.75% and Virginia starts from federal AGI, so the combined rate is federal + 5.75%. Short-term gains are taxed at ordinary rates.

| treatment | taxed on | at 22%+5.75% | at 24%+5.75% | at 32%+5.75% |
|---|---|---|---|---|
| Capital gain (short-term) | $133.17 | $36.95 | $39.62 | $50.27 |
| Section 1256 (60/40) | $133.17 | $31.36 | $32.43 | $40.68 |
| Gambling, itemised | $133.17 | $36.95 | $39.62 | $50.27 |
| Gambling, STANDARD deduction | $294.29 | $81.66 | $87.55 | $111.09 |

**The spread across those cells is the point.** The lowest is a Section 1256 reserve; the highest is gambling treatment with a standard deduction, at **$111.09 - 83% of the $133.17 actually earned**. Until the advisor picks a treatment, reserving toward the high end is the only choice that cannot leave a shortfall.

*Rates above are illustrative brackets, not a determination of the taxpayer's marginal rate, and state and federal liability are combined crudely. The advisor supplies the real figure.*

## 6. Two Virginia questions to put to the advisor

Virginia begins from federal adjusted gross income and has no separate capital-gains rate, so the federal characterisation decides almost everything. Two consequences are worth raising explicitly:

1. **Under the gambling treatment the gross figures matter far more than the net.** Winnings are income; losses are an itemised deduction capped at winnings. A taxpayer taking the federal standard deduction would get no offset at all - here that is **$294.29 of income against $161.12 of losses**, where the net is $+133.17.
2. **Virginia allows itemised deductions only if they were itemised federally**, so that decision carries straight into the state return.

## 7. Wash sales

Each contract is a distinct market that expires within 15 minutes, and no position was closed at a loss and repurchased. The ledger carries the market ticker and a timestamp on every line so this can be checked directly rather than taken on trust.

## 8. Period covered

First trade **2026-09-08 03:59:40 EDT**, last **2026-09-13 16:59:32 EDT**.

## 9. By month (US Eastern)

| month | legs | gross cost | fees | net P/L |
|---|---|---|---|---|
| 2026-09 | 298 | $5679.90 | $20.20 | $+133.17 |

## 10. The line-by-line ledger

`results/TAX_TRADES.csv` - one row per leg, ending in an automatic **TOTAL** row. Columns in order:

Date, Market/Asset, Contract Details, Action, Contracts/Size, Entry Price, Exit Price, Fees, Net Profit/Loss, Time (ET), Timezone, Datetime Acquired (UTC), Datetime Disposed (UTC), Holding Period, Proceeds, Cost Basis incl. Fees, Gain/Loss, Leg Type, Side Bought, Status, Settlement Result, Order ID, Cumulative Net P/L.

**Fees are the exchange's own billed figure** (`fee_total` from the order confirmation), never a reconstruction of the fee formula.

A leg marked **OPEN** was bought but had not settled when this was generated. It carries no result and no profit figure - left blank rather than estimated.
