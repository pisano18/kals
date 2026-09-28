# Q0928 refute-one_bet -- check of the "keep one full bet per coin" finding

**Verdict: the money numbers hold; the main reason given for the rule does not.** The finding
says the flag "caps one market at one bet, about $95, never about $190". It does not. The flag
only stops a *second full bet on top of a full bet*. Two other paths still put 1.3 to 1.6 full
bets on one coin, and both are still open today:

1. **Small first fill, then a full-size top-up.** When the first order fills only part of a bet,
   the bot treats the next buy as "finishing" it, but the code sizes that buy as a whole new bet
   (`take_n = min(SIZE, size)`; `rebuy_ok` returns "yes" for any top-up before it ever reads the
   flag, pinrun.py lines 2935-2944). Live `--min-fill-frac 0` lets the first fill be any size.
   This happened 3 times in 20 days (all won):

   | ET | coin | full bet | contracts held | times a full bet | market result |
   |---|---|---|---|---|---|
   | 09-19 12:44 PM | SOL | 107 | 174.45 (67.45 then 107) at 98c | 1.63 | won +$3.25 |
   | 09-25 6:44 AM | BNB | 88 | 115.40 | 1.31 | won +$2.33 |
   | 09-26 3:29 AM | BTC | 97 | 112.82 | 1.16 | won +$2.26 |

   The SOL one had about $171 riding on one coin, with the flag's logic already in place (the
   flag would not have stopped it).
2. **The last-15-seconds add** (0.5 of a bet, allowed by design). Since the flag went live:
   BTC 09-27 4:29 AM ET held 130.5 contracts at a full bet of 88 (1.48x); BNB 09-27 11:29 AM ET
   held 132 at 88 (1.5x).

So the real worst market with the flag on is about 1.5 bets (about $130-140) from the late add,
and up to about 2 bets (the close budget, 2 x SIZE) through the small-fill-then-top-up path.

## What I re-checked by hand and found right

- Ledger money, 4 markets (payout on winning side minus both costs minus fee):
  BTC 09-23 8:29 PM ET -$130.41 (176 YES at $152.36 = 88 at 87.0c + 88 at 86.13c; 176 insurance NO
  at $151.13); HYPE 09-17 11:29 PM ET +$16.41 (second bet 99 at 90.7c, about +$8.6 of it);
  SOL 09-25 10:14 AM ET +$4.15 (second 89 at 97.0c, about +$2.5); BTC 09-26 11:59 PM ET -$131.98
  (198 YES = 99 at 97.89c + 99 at 97.0c, insurance 198 NO at $133.65). All match the finding.
- Offers: BTC 09-23 86.0c both times (not cheaper, so the 09-25 rule refuses it); BTC 09-26
  97.9c then 97.3c (0.6c cheaper, so the 09-25 rule allowed it; only the fresh-offer-with-sellers
  gate, live 09-27 1:08 AM ET, refuses it -- after that loss but before the flag). Correct.
- Since the flag (09-27 4:11 AM ET): 6 markets refused a re-buy, all 6 won (+$1.80..+$7.42);
  none had an offer 0.5-1c cheaper than both the first offer and our average. The flag has not
  yet been the deciding "no". Correct.
- The flag is checked only in the entry loop (one call site, pinrun.py line 18667); it cannot
  block insurance.

## One more correction (makes "keep" even cheaper)

Two of the three winners the flag "gave up" (ZEC 09-19, SOL 09-25) had a first bet at 98.0c.
The 97.8c price ceiling (live 09-27 3:05 AM ET) refuses that first bet now, so the flag's cost on
top of today's rules is HYPE 09-17 alone, +$8.62 in 20 days, not +$13.96.

## Limits

11 second bets, 2 lost; 3 over-size top-ups, 0 lost. Too few to say how often any of these
lose. Sizes for the over-size check come from the bot's own refusal records (`size_now`) at the
nearest earlier time. Scripts: scratchpad/q0928/refute-one_bet/scan.py, ledger.py, over.py
(self-tested). Recorders alive (pids 2532788, 105352); 63.8 GB free.
