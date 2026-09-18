# Can we get MORE crypto trades? Yes -- and it is worth much less than it looks

**2026-09-17.** The operator: *"is there anything we can do to increase the
amount of crypto trades we get by any amount? ... we get less and less every
day even though our criteria is to get whatever is available below 99."*

**First, a correction: our ceiling is 98c, not 99c.** `PRICE_CEILING = 0.980`.
Everything at 98c and above is refused, and that is 431 refusals on the live
record.

## What the ceiling actually blocks

Markets the ceiling refused **and that we never bought at any other moment**
(the dump-guard lesson: a refusal marks a moment, not a market's fate), scored
on the **exchange's own settlement**, sized as `min(SIZE, offer)`:

| price | markets | won | lost | contracts | $ if taken | $/day |
|---|---|---|---|---|---|---|
| 98.0-98.7c | 40 | 40 | 0 | 1,289 | +$19.39 | +$1.94 |
| 98.7-99.0c | 47 | 47 | 0 | 2,003 | +$21.80 | +$2.18 |
| 99c+ | 224 | 224 | 0 | 10,639 | +$59.51 | +$5.95 |

**311 markets, not one loss.** And yet the whole lot is worth about **$10 a
day** against a run earning ~$70.

## The point, and it answers the real question

**Raising the ceiling roughly DOUBLES the trade count and adds about 14% to
the money.** 31 extra markets a day against our current 30-48 bets. The reason
the two numbers diverge so violently: **at 99c a win pays 1c.** You can take
three times as many trades and barely move the total.

So "we get less and less every day" and "we earn less" are not the same
problem. The trades are there. They are just priced where there is nothing
left to win. `RESULTS_decay.md` measured the mechanism: the cheap tail is
vanishing -- the share of best offers above 98c went 44% -> 52% -> 68%.

## The structural fact worth carrying

**Our live loss rate FALLS as the price RISES:**

| our fill price | fills | lost |
|---|---|---|
| under 97c | 244 | 10 (4.1%) |
| 97-98c | 157 | 3 (1.9%) |
| 98c+ | 62 | 0 (0.0%) |

Expensive contracts are *safer*, because an expensive offer is one the market
also agrees about. Cheap offers are where adverse selection lives. That is the
opposite of the intuition that cheap = bargain, and it is why raising the
ceiling is low-risk even though it is low-reward.

## The trap, if the ceiling is ever raised

`EV_FLOOR` becomes the binding gate at about **98.7c** -- a gate that has never
fired once in 5,500 live refusals, parameterised by `MEASURED_FLIP = 0.0090`,
a replay number. So `PRICE_CEILING = 0.99` alone delivers only the first row of
the table (+$1.94/day). Reaching the second row means revisiting
`MEASURED_FLIP` too, and that constant must be made price-conditional if it is
ever refreshed -- at the aggregate live rate it would cap price at ~96.2c and
kill the 97.5-98c band, the single most profitable slab we trade.

## Ranked, what is actually available for MORE MONEY

1. **Size up near the close (AMENDMENT 48, built, paper arm running).** Our own
   fills earn 5.35c a contract inside 5 seconds against 1.90c at 16-30 s, and
   the book is not the constraint -- median depth at our own sweep limit is 433
   contracts against a SIZE of 95. This is the only lever whose upside is
   measured in tens of dollars a day rather than ones.
2. **Raise the ceiling to 0.99.** +$1.94/day reachable immediately, +$4.12/day
   if `MEASURED_FLIP` is handled. Nearly free: 0 losses in 311 settled markets
   and 0 in 62 of our own fills at 98c+.
3. **A second venue.** The capacity ceiling is structural -- 36.8% of markets
   have no offer on the winning side at all, and `RESULTS_maker.md` killed
   resting bids (filled on 29% of winners and 100% of the 17 losers).
4. **The Coin Race series**, which we do not trade live at all.

**Rule 5 caveat on all of section 1-2:** the offers were on screen; whether WE
would have been filled is the one thing this cannot see. Our measured fill
fraction is 80-95%, so discount accordingly.
