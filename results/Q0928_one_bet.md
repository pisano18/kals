# Q0928 one_bet -- is "one full bet per coin" the right move?

**Answer: keep it.** Both of the big double-bet losses (BTC 09-23 -$130, BTC 09-27 -$132)
were already blocked by other rules live before this one: the 09-25 "genuinely cheaper
offer" check stops the 09-23 kind, and the fresh-offer-with-sellers gate stops the 09-27
kind. So on top of what is already live, the one-bet rule has **given up about $14 in 20
days** (3 winning second bets, 0 losses avoided). What it buys is a hard cap: one market
can never hold two full bets, so no single market can lose about $190. At our size one lost
second bet (about $85-95) wipes out about 30 wins like those three. Three bets can't tell us
whether a second bet loses 0 times in 100 or 20 times in 100.

Sources: our own fills only (Kalshi ledger plus live order records, 09-09 04:00Z to 09-28
03:46Z), using the restored 09-25 log. Logged contract counts match the ledger on all 1,000
markets (0 mismatches). No replay, no tape loss rates.

## 1. Every second full bet we ever made (11 filled, plus 3 sent that filled nothing)

A "second full bet" means an order sent while the market already held a full-size bet, and
not the last-15-seconds add. **All 11 went out 0.2 to 1.9 seconds after the first bet.** No
second full bet ever came later in the quarter-hour.

"Its own" is the second bet's money, including its share of any insurance. "Market" is the
whole market in the ledger. "Without" is what the market would have made with no second bet.

| ET | coin | 1st bet (contracts @ paid) | 2nd bet | offer 1st -> 2nd | secs left | secs apart | result | its own | market | without |
|---|---|---|---|---|---|---|---|---|---|---|
| 09-11 1:14 AM | BTC | 20 @ 96.8c | 9 @ 96.1c | 96.1 -> 96.1 (same) | 18 | 0.3 | won | +$0.33 | +$0.92 | +$0.60 |
| 09-17 10:59 PM | XRP | 97 @ 95.1c | 97 @ 94.5c | 92.8 -> 94.3 (dearer) | 29 | 1.0 | won | +$4.99 | +$9.43 | +$4.45 |
| 09-17 11:29 PM | HYPE | 99 @ 91.6c | 99 @ 90.7c | 91.6 -> 90.7 (**0.9c cheaper**) | 20 | 1.2 | won | +$8.62 | +$16.41 | +$7.78 |
| 09-19 7:14 AM | ZEC | 108 @ 98.0c | 108 @ 97.2c | 98.0 -> 97.2 (**0.8c cheaper**) | 22 | 1.9 | won | +$2.85 | +$4.86 | +$2.00 |
| 09-23 12:59 AM | SOL | 123 @ 96.7c | 96 @ 96.2c | 96.0 -> 96.2 (dearer) | 3 | 0.6 | won | +$3.40 | +$7.15 | +$3.75 |
| 09-23 4:44 AM | SOL | 84 @ 97.8c | 56 @ 97.9c | 97.3 -> 97.3 (same) | 30 | 0.2 | won | +$1.10 | +$2.79 | +$1.69 |
| 09-23 11:14 AM | DOGE | 85 @ 95.8c | 85 @ 95.9c | 94.6 -> 95.1 (dearer) | 15 | 0.2 | won | +$3.24 | +$6.60 | +$3.36 |
| **09-23 8:29 PM** | **BTC** | 88 @ 87.0c | 88 @ 86.1c | 86.0 -> 86.0 (same) | 26 | 0.3 | **lost** | **-$64.08** | **-$130.41** | -$66.32 |
| 09-24 11:59 AM | XRP | 82 @ 95.6c | 55 @ 97.5c | 93.6 -> 95.0 (dearer) | 24 | 0.2 | won | +$1.27 | +$4.64 | +$3.37 |
| 09-25 10:14 AM | SOL | 89 @ 98.0c | 89 @ 97.0c | 98.0 -> 97.0 (**1.0c cheaper**) | 18 | 0.2 | won | +$2.49 | +$4.15 | +$1.65 |
| **09-26 11:59 PM** | **BTC** | 99 @ 97.9c | 99 @ 97.0c | 97.9 -> 97.3 (**0.6c cheaper**) | 30 | 0.4 | **lost** | **-$64.06** | **-$131.98** | -$67.92 |

The two BTC losses: each second bet lost $76-96 on its own, and insurance paid back $12 and
$32 of that. 8 of the 11 second bets saw an offer that was the same as the first or dearer.
They only looked cheaper because the rule compared the offer with the average we had paid,
and sweeping several price levels pushes that average up. The 09-25 fix closed that.

**By half, with the second bet as the only difference:**

| | markets we traded | whole-half result | second bets | lost | second bets' own money |
|---|---|---|---|---|---|
| 09-09..09-17 ET | 471 | +$545.16 | 3 | 0 | +$13.94 |
| 09-18..09-28 ET | 529 | +$124.61 | 8 | 2 | -$158.40 before insurance, -$113.79 after |

For scale: a first bet made +1.0c a contract in the second half (529 markets, 10 lost). The
second bets lost 23.5c a contract (675 contracts).

The other extra buys the rule still allows are positive. Top-ups of a half-filled bet: 58
buys, 2 lost, +$44.28, all in the second half. Last-15-seconds adds: 10 buys, 0 lost, +$18.23.

## 2. The alternatives (change in money against what really happened; + = better)

| rule for the second bet | 09-09..09-17 | 09-18..09-28 | total |
|---|---|---|---|
| never (the live one-bet rule) against no rule at all | -$13.94 | **+$113.79** | +$99.85 |
| half size | -$6.97 | +$56.90 | +$49.93 |
| only when the offer is at least 1c cheaper than the first (keeps only SOL 09-25) | -$13.94 | +$116.28 | +$102.34 |
| only when NOT a fresh offer with others selling | about -$5 to $0 (no seller data yet) | about +$59 to +$64 | about +$54 to +$64 |
| **the real alternative: turn the flag off, other live rules stay on** (offer genuinely 0.5-1c cheaper than both the first offer and our average paid, plus the fresh-offer gate) | +$8.62 (HYPE) | +$5.34 (ZEC, SOL) | **+$13.96 for turning it off** |

- "Fresh offer with others selling" did not stop BTC 09-23: its offer was fresh, but only 34
  to 35 of every 100 recent trades were sells (POSTMORTEM_2026-09-27), under the gate's
  50-in-100 line. So that rule keeps the -$64 loss. The seller data only starts 09-24
  evening, so for 6 of the 8 second-half bets I give a range.
- The "at least 1c cheaper" rule wins here only because the one bet it keeps happened to
  win. The old rule already capped the gap at 1c, so this rule means "exactly 1c". The tape
  study behind that cap found bigger discounts go with more losses. It also refuses HYPE
  (0.9c) and ZEC (0.8c), which were real discounts. It's a fit to 1 market, not a finding.
- On top of what is live, the flag's price is 3 winners, about $0.70 a day. It avoided
  nothing, because both losers are already refused by other live rules.

## 3. Since the flag went live (09-27 4:11 AM ET to 09-28 about 1:20 AM ET)

- Second full bets: **0**. The rule did its job, with nothing that looked like a second bet.
- `rebuy_band` refusals: 6 markets. All 6 won on our side (+$1.80 to +$7.42 each), so no
  loss was avoided and no winner was given up. **In none of the 6 was the refused offer
  0.5-1c cheaper**: the rule before 09-27 would have refused every one of them anyway. The
  bot's once-a-second record of what it looked at shows the same: 34 refused looks on 5 of
  those markets, 0 with an offer the old rule would have taken. So far the flag has never
  been the thing that said no.
- **Correction to PERCAP_AND_FULLSIZE_2026-09-28:** its "one-full-bet removed 5 second
  bets today" counts refusals that would have happened anyway. The number the flag actually
  changed today is 0.

## 4. What this sample can and cannot show

- 11 second bets on 11 different quarter-hours; 2 lost. Only 3 of them were a genuinely
  cheaper offer, and all 3 won. With 0 losses in 3, anything from 0 to about 63 losses in
  100 is still possible. A second bet at about 97c breaks even only below about 3 losses in
  100, so it can't be settled from our fills for months. At about 1 genuine case a week, 30
  cases would take about 7 months.
- Missing-lines check: the 09-25 SOL second bet (+$2.49, 1c cheaper) and the 09-26 11:59 PM
  BTC loss are both in the restored 09-25 log. WHY_NO_MONEY (09-27) was written while those
  lines were missing. Its "+$107 over 19 days (-$13 / +$120)" is +$99.85 (-$13.94 / +$113.79)
  here. The difference is that extra SOL winner plus later days. Its conclusion stands, and
  nothing was decided on a wrong number.
- Offer prices for bets before 09-24 come from the bot's signal record, and after that from
  the order record. The insurance share is split by contracts, and insurance fees are not
  split out.

## Recommendation

**Keep `--one-full-bet`.** On what we've seen, keeping it costs about $14 over 20 days,
under $1 a day. In exchange, the worst single market stays at one bet (about $95 at size 99)
instead of two (about $190). The flag would matter on the first loser that gets past the
other two rules, and 3 cases can't rule that out. Don't swap in "half size" or "1c cheaper":
each one is fitted to one or two markets. Look again once there are 30 or more refusals
where the flag was really the reason (a `rebuy_band` refusal where the offer was 0.5-1c
cheaper than both the first offer and our average paid). So far there are 0.

Scripts (self-tested: planted scale-ins found, empty world finds none):
`scratchpad/q0928/one_bet/onebet.py`, `classes.py`, `trajref.py`. Both recorders were
running when this was written (kalshi_collector pid 2532788, crypto_feeds pid 105352), with
63.8 GB disk free.
