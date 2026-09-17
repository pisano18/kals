# PRE-REGISTRATION -- AMENDMENT 45, ONE-COIN DEPTH
## Written 2026-09-17 ~13:1xZ, before the paper arm's first fill

**Rule:** a bar is never moved after seeing a result without saying so loudly,
and no threshold is deployed from a replay without a holdout split AND a
pre-registered live bar written before the number is seen. **Nothing is
deployed.** `--one-coin-depth` is refused on a live run; the paper arm carries
it.

## The change

Today one market may hold at most SIZE contracts per fill (two fills if the
second is 0.5-1c cheaper, AMENDMENT 23). The offers the bot hits are often far
deeper at or under the limit price it already sends. With the flag on, the
first order on a market may ask for more than SIZE, capped by the LOWEST of:

1. `--one-coin-max` x SIZE (2.0 in this arm);
2. what is left of the close's contract budget (2 x SIZE, unchanged);
3. what a TOTAL loss at the 98c ceiling could cost before the drawdown brake
   halts the bot: `(bank - 0.8 x high-water) / 0.98`.

`one_coin_cap()` in `pinrun.py`; seven self-test checks pin the arithmetic.
Price, gate and per-close worst case are untouched. The only new thing is how
much of the per-close budget may sit on ONE coin.

## The operator's decision this rests on

2026-09-17: *"The brakes are a whichever comes first, which I'm fine with."*
So the drawdown brake stays at 20% and the sizing rule at bank/5.88; ceiling 3
above is what keeps a single widened position from being able to halt the bot.

## What is known (results/RESULTS_quiet.md)

- Extra contracts at the same limit, current version 14 h: 1.2x = +18%, 2.0x
  = +80%; sweep era 3.5 d: +20% / +87%. ~$20/day at 1.2x, ~$80-110/day at 2.0x
  at realised rates, at today's size.
- The brake headroom was $96 on 2026-09-17 (98 contracts vs SIZE 94), ~1.25x
  SIZE at a fresh high. So in practice this arm will widen mostly on days the
  bank is at or near its high, and by ~20-25%, not 100%.
- Two coins on one close have never both lost (0 of 101 closes; given one
  lost, the other lost 0 of 9). A widened single-coin position gives that
  spreading up on the contracts above SIZE.
- Loss per losing contract, all 11 legs: 62.3c gross, 49.3c net after hedge,
  worst 98.0c. The hedge recovered nothing on 7 of 11.

## What the paper arm CAN and CANNOT show

It can show how often the cap binds and how many extra contracts it would
have asked for, at which prices, and whether the widened orders would have
been on markets that went on to lose (a TAPE population -- NOT our loss rate,
rule 5). It cannot show whether the deeper part of an offer fills at the shown
price when we actually take it, nor whether the seller of a 300-contract
offer is a different animal from the seller of a 90-contract one. Those are
the live bar's job.

## STAGE 1 -- paper arm vs control. Bars fixed now.

Arm: live flags + `--one-coin-depth --one-coin-max 2.0`. Control: pid 411820
(identical flags, no widening). Both settle the same closes.

**Minimum before reading:** 30 settled closes in the arm and at least 15
closes on which `one_coin_depth` records show the cap actually widened an
order (the WIDENED population).

**Kill:**
1. On WIDENED closes the arm's loss rate exceeds the control's on the same
   closes by more than one loss in 30.
2. The widened contracts, scored at their own price against the settled
   result, are net negative at 30 widened closes.

**Proceed to a live bar:**
1. WIDENED closes lose no more often than the control's same closes.
2. Widened contracts net positive, and the extra contracts per day at least
   +15% of the control's.

## STAGE 2 -- the LIVE bar, decided now

If deployed: `--one-coin-depth --one-coin-max 2.0` in `restart_bot.ps1`, the
live refusal in `pinrun.py` lifted by a code edit that cites this file,
`results/VERSIONS.md` entry with the revert line, `versioncheck` clean.

Scored over the first **40 live closes with a widened fill** (an `order`
whose count exceeds SIZE at the time):

1. **Close-loss rate on those closes <= 6.0%.** All-time live is 4.66%; a
   widened close that loses costs up to twice today's typical loss, so the
   tolerance is tighter than the 8% used for the sweep. At 3 losses in the
   first 40, or 2 in the first 15, revert immediately.
2. **The drawdown brake never fires on a single widened close.** One
   occurrence is an immediate revert and a bug in `one_coin_cap`, not a data
   point.
3. **Fill share on widened orders >= 80% of what was asked.** If the deep
   part of the ladder is not really there when we take it, the mechanism is
   not what this file claims.
4. **Net positive on those 40 closes.**

## Kill criterion for the idea itself

If at 40 live widened closes the extra contracts are under +10% of the
control's volume (the brake headroom rarely allows it), the flag stays off and
the idea is closed until the bank clears ~$2,450, where the full budget fits
under the brake without the headroom cap.

## What is NOT being proposed

No change to SIZE, BANK_BRAKE, MAX_DRAWDOWN, MAX_PER_CLOSE, the rebuy band,
PIN, the ceiling, the edge floor or the hedge. The second fill on the same
market still needs its 0.5-1c discount.
