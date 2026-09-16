# VALUE -- where the money actually comes from

`research/pinvalue.py`. 391 markets bought, rebuilt from the fills themselves. Saved in `results/value_trades.jsonl`.

Bank moved **$+267.86** over the same window; the fills add up to **$+263.41**. They agree.

Total staked **$11323**, total profit **$+263.41**, which is **2.33% on every dollar put at risk**.

(7 markets had fills but no settlement on file and were dropped.)


## The three things that make money

Money in an hour is *how often a bet appears* x *how big it is* x *what it returns*. Here is each, by how calm the market was:

| market | buys | losses | avg price | avg contracts | return per $ staked | profit | profit per buy |
|---|---|---|---|---|---|---|---|
| calmest fifth | 77 | 1 | 95.1c | 26 | 4.89% | $+91.18 | $+1.184 |
| 2nd calmest | 77 | 1 | 95.8c | 28 | 1.43% | $+28.98 | $+0.376 |
| middle fifth | 77 | 1 | 94.6c | 34 | 4.74% | $+115.75 | $+1.503 |
| 2nd choppiest | 77 | 4 | 95.6c | 29 | -1.20% | $-25.66 | $-0.333 |
| choppiest fifth | 81 | 3 | 93.5c | 35 | 1.76% | $+47.70 | $+0.589 |

Spread in profit per buy across those fifths: p = 0.255 against chance. **10 of the 389 buys lost.** One loss at 95c undoes about thirty wins, so a fifth's average is mostly a record of where those losses landed -- which is why the column is not in order even though the COUNT of chances (pinwhen) is.

Return per dollar, calmest **4.89%** against choppiest **1.76%**.

## Is any of it predictable?

| pair | rank correlation | p (2,000 shuffles) | reading |
|---|---|---|---|
| how choppy vs return per $ | -0.11 | 0.032 | maybe |
| how choppy vs price paid | +0.08 | 0.106 | chance |
| price paid vs return per $ | -0.92 | 0.000 | ARITHMETIC, not a finding |
| contracts bought vs return per $ | +0.06 | 0.264 | chance |

*Price against return is near -1 by construction: winning a contract bought at 90c returns 11%, one bought at 98c returns 2%. It says nothing about when to trade.*

## Money by hour of the day

| hours (ET) | buys | losses | staked | profit | return per $ |
|---|---|---|---|---|---|
| 00:00-04:00 | 82 | 2 | $2470 | $+110.72 | 4.48% |
| 04:00-08:00 | 78 | 2 | $2258 | $+18.23 | 0.81% |
| 08:00-12:00 | 52 | 1 | $1572 | $+52.47 | 3.34% |
| 12:00-16:00 | 35 | 0 | $964 | $+42.60 | 4.42% |
| 16:00-20:00 | 72 | 2 | $2080 | $+36.74 | 1.77% |
| 20:00-24:00 | 72 | 3 | $1978 | $+2.65 | 0.13% |

Spread in profit per buy across those blocks: p = 0.835. That is what chance produces when a dozen losses fall somewhere in 391 buys, so there is nothing here to act on yet.
