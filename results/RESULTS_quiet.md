# RESULTS -- quiet markets: where the money is not, and where some still is

`2026-09-17 ~06:30Z` -- from the LIVE bot's own logs (`results/pinrun-live-*.jsonl`),
not the tape and not the replay, unless a line says otherwise. Operator's brief:
*"We need a way to make more money during quiet times ... Just more money
without substantial risk increase."*

## 1. What quiet IS, measured

Per ET hour over 7-9 days (closes watched, share with any seller, median share
of looks with a seller, fills per day, $):

| ET hours | quarter-hours with a seller | median looks with a seller | fills/day/hour | $/hour of record |
|---|---|---|---|---|
| 0-8 (night) | 86-97% | 12-21% | 2.2-3.3 | +$14 to +$40 (two hours negative) |
| **9-16 (day)** | **74-87%** | **6-12%** | **1.0-1.9** | **+$4 to +$26** |
| 17-23 (evening) | 68-86% | 9-19% | 1.8-3.7 | +$17 to +$41 (one hour -$28) |

Quiet is the US daytime. Sellers show up on half as many looks and we fill
half as often. 16% of all quarter-hours (120 of 761) have nobody selling the
winning side at any price; on those there is nothing to buy.

Money per quarter-hour rises with how often sellers appear: under 5% of looks
-> $0.17 a close; 5-15% -> $0.59; 15-30% -> $0.75; over 30% -> $0.83.

## 2. Where each quarter-hour of the CURRENT version went (64 since 09/16 9:57 AM ET)

| outcome | all | 9 AM-4 PM |
|---|---|---|
| bought | 28% | 25% |
| somebody selling, but every offer failed a rule | 47% | 42% |
| nobody selling at any price | 25% | 33% |

The "failed a rule" bucket is mostly: offer too close to what it is worth
(99.8-99.9c, edge under 0.3c; 15 closes, worth about $0.10-0.20 a fill -- not
money) and offers above the 98c cap (5 closes at 98.1-99.0c in 14 h; 39 of 180
unbought closes over the sweep era). Lost races are 3 of 25 orders (12%) in
this version -- the sweep fixed that.

## 3. The levers, with numbers

**A. Take the whole offer, not just SIZE (NEW, biggest, cheapest).** The bot asks
for SIZE contracts per order. The offers it hits are often much deeper at or
under the very limit price it sent, and the per-close budget (2 x SIZE) already
permits twice that exposure -- it just needs a SECOND market to spend it, which
only 6% of scan-seconds have.

| window | asked | more contracts at the SAME limit within the existing budget | daytime | at the window's realised c/contract |
|---|---|---|---|---|
| current version, 14 h | 1,657 | **+753 (+45%)**, on 11 of 21 closes | +55% | ~$49/day at 3.83c |
| sweep era, 3.5 days | 12,143 | **+3,769 (+31%)**, on 57 of 131 closes | +24% | ~$31/day at 2.89c |

Same price, same gate, same close, same worst case per close as today's budget.
The one new risk is CONCENTRATION: up to 2 x SIZE on one coin instead of spread
over two coins that settle on the same second at rho ~0.8 anyway. Not built:
`pintake` caps an order at SIZE (`max_take_count`) and the change touches the
live order path, so it goes in as a PAPER-ONLY flag first, after the 3-5 AM
maintenance window, with its own PREREG. Do not deploy from this file.

**B. Trading sooner (tau 45).** Arm running since 10:01 PM ET; 13 settled
records and 11 NEW markets by 1:30 AM ET, against the pre-registered minimum of
30 closes each and 20 NEW markets. Outcomes NOT read. At this pace the first
read is late 09/17. The stricter variant (`--honest`) cannot start: the bot's
self-test fails under that flag (pre-existing), so it needs a code fix first.

**C. Coin Race, fair-value arm.** 20 bets, 20 won, on paper. Bar: 40 bets with
at most 2 losses. Its fills land in daytime hours too (10, 13, 14, 16 ET), so
it is a second source of quiet-time sellers. About two more days.

**D. Raise the 98c cap to 99c.** Would add ~8 closes a day at 98.1-99c, worth
about $0.87 a fill = ~$7/day; a loss at 99c costs ~$93, so it dies above 1 loss
in 107. Live fills at 98c+: 61, 0 lost -- consistent with, not proof of, that.
Not now; revisit when 98c+ fills reach ~200 with no loss.

**E. Dead, with the evidence, do not re-try:** resting bids instead of taking
(`RESULTS_maker`, 09/12: filled on 100% of losers, 29% of winners); the other
15-minute series (settle on a 1-minute candle, no locked average, 18x worse);
hourly series (1 buyable of 2,568); lowering the 0.3c edge floor (pennies at
99.9c); every idea in `IDEAS.md`'s graveyard.

## 4. Loss rates by price and edge, live entry fills, all time

| price paid | fills | lost | | edge at signal | fills | lost |
|---|---|---|---|---|---|---|
| under 94c | 92 | 4 (4.3%) | | 0-1c | 16 | 0 |
| 94-96c | 74 | 4 (5.4%) | | 1-2c | 127 | 2 (1.6%) |
| 96-97c | 70 | 2 (2.9%) | | 2-4c | 160 | 2 (1.2%) |
| 97-98c | 148 | 3 (2.0%) | | 4-8c | 95 | 4 (4.2%) |
| **98c+** | **61** | **0** | | **8c+** | **47** | **5 (10.6%)** |

The cheap-looking fills are the dangerous ones; the dear, small-edge fills are
the safe ones. Lever A adds contracts at the SAME price and edge as fills we
already take, so it does not move along this table.
