# RESULTS -- the dump guard IS a hidden 85c price floor, and it is 10-0 against itself

**2026-09-17 ~20:1xZ.** Found by the fresh-eyes review (`guards-jump-dump-bothsides`
agent), then verified by hand from the live logs. **This corrects a statement I
made to the operator earlier today** -- I told him "there is no price floor in
the crypto bot". There is no price floor CONSTANT. There is an effective floor
at **84.5c**, and it is created by a gate whose name says nothing about price.

## The arithmetic

`research/pinrun.py:6147-6167`, AMENDMENT 10:

```python
_conf = f if want == "yes" else (1.0 - f)     # our model's belief in OUR side
_disc = (f - price) if want == "yes" else ((1.0 - f) - price)
if _disc > DUMP_DISCOUNT:        # DUMP_DISCOUNT = 0.15
    ... continue                 # refuse
```

The confidence gate upstream guarantees `_conf >= PIN = 0.995`. So the refusal
condition `_conf - price > 0.15` is exactly

    price < 0.995 - 0.15 = 0.845

**Any offer below about 84.5c on the side we want is refused, by construction,
no matter how good it looks.** The intent (a certainty at a deep discount is
someone else's information) is defensible in principle. The name is not: it
appears in the logs as `dump_guard`, and nothing in the file says "floor".

This is why the 13 sub-85c primary fills in the live record all date from
2026-09-08 to 09-11, before the guard was enabled. The 10c fill the operator
may remember was a HEDGE, which takes a different path and is not gated here.

## What it has actually cost, on live decision records

Every refusal writes a `dumped` record carrying the side, the price, the model's
fair value, and `take_n` (the contracts the book was offering at that instant).
Seventeen markets have been refused; ten have settled.

| market | side | price | contracts offered | outcome | P&L if taken |
|---|---|---|---|---|---|
| KXBNB15M-26SEP120000-00 | no | 0.84 | 20 | won | +3.01 |
| KXBTC15M-26SEP122115-15 | yes | 0.78 | 20 | won | +4.16 |
| KXBTC15M-26SEP131930-30 | yes | 0.73 | 51 | won | +13.07 |
| KXBTC15M-26SEP140045-45 | yes | 0.84 | 53 | won | +7.98 |
| KXDOGE15M-26SEP140315-15 | no | 0.77 | 22 | won | +4.79 |
| KXZEC15M-26SEP141730-30 | no | 0.80 | 48 | won | +9.06 |
| KXBNB15M-26SEP150915-15 | yes | 0.76 | 60 | won | +13.63 |
| KXBTC15M-26SEP160345-45 | no | 0.80 | 9 | won | +1.70 |
| KXNEAR15M-26SEP160430-30 | yes | 0.80 | 84 | won | +15.86 |
| KXBNB15M-26SEP171500-00 | yes | 0.84 | 60 | won | +9.04 |

**Ten of ten would have won. $+82.30 over six days**, against a run that has
made $422 in total. Seven more are unsettled.

They are spread across BNB (3), BTC (4), DOGE, ZEC and NEAR, and across six
days, so this is not one coin or one session misbehaving.

## What this evidence IS and IS NOT

**It is a stronger population than the tape.** These are not replayed book
snapshots. They are moments when OUR bot, live, saw an offer with its own
book connection and decided not to take it. The counterfactual "would we have
been filled" is the same counterfactual as every trade we DO make, where the
measured fill fraction is 80-95% at crypto sizes. So the honest range is
**$66-78, not $82.30.**

**It is not proof.** Ten observations with zero losses bound the true loss rate
below **25.9%** (95%, rule of three). At the mean refused price of about 80c,
break-even is **20%**. So the data cannot formally rule out that these trades
are unprofitable -- it just puts the point estimate at zero and every one of
them is a market the model rates at 99.5%+.

**The dangerous alternative hypothesis, and why it looks unlikely.** A deep
discount could mean OUR model is stale rather than the seller being informed --
a lagged index would manufacture a fake "discount". If that were happening we
would expect the refused markets to lose. Ten of ten won, which is evidence
against staleness as well as against informed dumping.

## Recommendation

The guard cannot be evaluated any further in paper: paper cannot answer whether
the offer would have reached us, and the live decision record already shows the
offers were on screen. The `--take-dumps` flag exists and is **PAPER ONLY** by
design (`research/pinrun.py:6860`).

Options, cheapest first:

1. **Raise `DUMP_DISCOUNT` 0.15 -> 0.25.** The ten refused discounts were 15.9,
   16.0, 16.0, 19.6, 19.8, 20.0, 21.5, 22.9, 23.9 and 26.8 cents, so this admits
   **nine of the ten** (about $69-78) while still refusing the most extreme
   dumps. Smallest change, keeps the guard's stated purpose for the tail.
2. **Disable it live** (allow `--take-dumps` on the live path). Largest gain,
   removes the protection entirely.
3. **Leave it.** Costs roughly $14/day at current size against a ~$70/day run.

**Either live option needs the operator's per-instance sign-off (hard rule 1)
and a pre-registered revert bar before it is deployed.** The bar should be
tight, because the guard protects against a rare event and ten observations
cannot see a rare event: revert on the first two losses among dump-priced fills.
