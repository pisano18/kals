# Scaling plan -- what more money in the bank actually buys

Written 2026-09-24, 9:55 PM ET (2026-09-25 01:55Z). Read-only measurement from
the bot's own live logs, the code as deployed, and Kalshi's ledger. Nothing was
changed. Every threshold is cited to the line that holds it.

## The short version

- The bot sizes itself: **bet size = bank divided by 11.76**, rounded down,
  never above 250 contracts. Today: bank $1,012.04, size 86.
- On the 15-minute markets the book runs out. At today's size we get about
  **72 of every 100 contracts we ask for**; at 250 contracts, 57 of 100.
- **Past a bank of about $2,940 the code itself stops raising the size**
  (the 250 cap), and the book was already giving less per dollar from
  $1,500 up. More money than ~$3,000 buys nothing on the 15-minute markets.
- The hourly BTC market's book is 6-20 times deeper (4 readings, no live
  fills yet). That is the only place a bigger bank can be spent, and it is
  trading 1 contract at a time until its fills are proven.
- The next step that pays is a **bank of $1,500 (size 127)**: about 38%
  more contracts, for a worst single close of $373 instead of $250. Not
  before the three things at the end are true.

## How the size is set (confirmed in the code)

`research/pinrun.py`, `size_for_bank()` (line ~13085) and
`worst_close_cost()` (line ~12864):

    worst close (dollars, size 1) = (MAX_PER_CLOSE + extra bet) x PRICE_CEILING
                                  = (2 + 1) x 0.98 = $2.94
    size = bank / (worst close x BANK_BRAKE) = bank / (2.94 x 4.00) = bank / 11.76

rounded down, floored at 1 and **capped at 250** (`AUTO_SIZE_MAX`, line
~888: "nothing above this without a fresh depth study").

The formula in the code's comment (`bank / (BANK_BRAKE x MAX_PER_CLOSE x
PRICE_CEILING)`) leaves out the extra bet. The running code counts it: a
close may spend one extra bet on a third coin (`--extra-coin 1`) or in the
last 15 seconds (`--late-extra 1`), and those two share one allowance
(A61). So the honest divisor is **3 bets, not 2**. Check: $1,012.04 / 11.76
= 86.06 -> 86, which is exactly what `results/pinrun-live-size.json` holds.

Where each number lives: `MAX_PER_CLOSE = 2` (pinrun.py line 901);
`PRICE_CEILING = 0.980` (line 4022); `--bank-brake 4.00`, `--extra-coin 1`,
`--late-extra 1`, `--loss-cap 200`, `--max-losses 2`, `--max-positions 3`,
`--series-size 1` (all `restart_bot.ps1`); `MAX_DRAWDOWN = 0.20` (line 2257).

The re-size happens on its own every 5 minutes while the bot holds nothing
(`AUTO_SIZE_EVERY_S = 300`). **So "taking a size step" means depositing;
there is no dial to turn.**

## The table

Per-close budget = 2 x size contracts (`close_budget()`), in dollars at 98c.
Worst single close = 3 x size x $0.98 -- the extra bet included, every
contract lost, nothing hedged. It is exact: a contract cannot lose more
than it cost. The 20% line assumes the bank is at its high mark; today the
mark is $1,037.33 and the line is $829.86 (`results/pinrun-hwm.json`).

"Book holds the size" and "contracts obtainable" come from the live bot's
own signal records over the last 7 days (09-18 to 09-24): at the moment it
decided to buy, how many contracts were offered on its side at or under
98c (`ladder_under`). Population: the main bet (`leg: full`, inside 30 s),
**221 markets on 221 closes**; the 45-second leg and top-ups are excluded
because they are sized at a third or less.

Depth under 98c at those 221 moments: **a quarter of the time 24 or fewer
contracts, median 164, three quarters of the time 653 or fewer.** At the
exact price we would pay, median 48. (Counting every market's first
signal, 470 markets: median 264.)

| bank | size (contracts) | per-close budget | worst single close | 20% halt line | book held >= size | contracts actually obtainable per bet | vs today |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **today $1,012** | **86** | 172 ($169) | **$253** | $829.86 (mark $1,037) | 62 in 100 | **61.5 (72% of size)** | 1.00x |
| $1,000 | 85 | 170 ($167) | $250 | $800 | 62 in 100 | 60.9 (72%) | 0.99x |
| $1,500 | 127 | 254 ($249) | $373 | $1,200 | 52 in 100 | 85.0 (67%) | 1.38x |
| $2,500 | 212 | 424 ($416) | $623 | $2,000 | 45 in 100 | 127.2 (60%) | 2.07x |
| $5,000 | 250 (cap) | 500 ($490) | $735 | $4,000 | 42 in 100 | 143.7 (57%) | 2.34x |
| $10,000 | 250 (cap) | 500 ($490) | $735 | $8,000 | 42 in 100 | 143.7 (57%) | 2.34x |
| $25,000 | 250 (cap) | 500 ($490) | $735 | $20,000 | 42 in 100 | 143.7 (57%) | 2.34x |

Two things the table says that are easy to miss:

- **One worst-case close is 25% of the bank at every level** (3 x 0.98 /
  11.76 = 0.25). A close that loses everything trips the 20% halt on its own,
  today and at $25,000 alike. Real losses have been smaller (the biggest ever
  is -$130.41 on one market, VERSIONS v-nospike) because most losses are one
  leg, partly hedged.
- **The $200 day cap does not grow.** At size 212 one unhedged full bet is
  $208; at 250 it is $245. From a $2,500 bank up, a single bad market ends
  the trading day (`--loss-cap 200`, re-applied on every re-size).

## The hourly BTC family (KXBTCD)

Same settlement rule, one market an hour, 24 closes a day. Live at **1
contract a market** since 09-24 12:48 PM ET (VERSIONS v-btcd1, `--series
KXBTCD --series-size 1`), at most 2 contracts a market (`--max-per-market 2`).

What we have: **4 signals from the paper arm `arm-btcd` (3 markets, 2
closes, 09-24 morning) and 0 live signals in the live bot's first 9 hours**
(it has been watching the hourly rungs; none passed every gate yet).

Depth under 98c at those 4 moments: 915 / 1,000 / 2,243 contracts (quarter,
median, three-quarter, first signal per market); the one main-bet signal
saw 3,486. At the exact price we would pay, median 845 -- against 48 on the
15-minute markets.

| bank | size | book held >= size (4 of 4 readings) | contracts obtainable per bet | vs today |
|---:|---:|---:|---:|---:|
| $1,000 | 85 | 4 of 4 | 85 (100%) | 0.99x |
| $1,500 | 127 | 4 of 4 | 127 (100%) | 1.48x |
| $2,500 | 212 | 4 of 4 | 212 (100%) | 2.47x |
| $5,000+ | 250 (cap) | 4 of 4 | 250 (100%) | 2.91x |

**Four readings is not a measurement; it is a reason to keep measuring.**
Depth at the signal is also not a fill: on the 15-minute markets the live
fill rate is ~70% and the class that hurts us -- someone actively selling to
us at extreme confidence -- is invisible in the book (CLAUDE.md, 2026-09-10
amendment). The hourly family's first job is to show real fills at 1
contract over ~30 fired closes (OPEN_WORK A2). Note also that an hourly
loss is one coin at full size with no other coins to offset it, and the
250 cap and the $200 day cap apply to it exactly as above.

## Money per day at each level

From Kalshi's ledger (`results/kalshi_ledger.json`, written 09-24 9:45 PM ET),
the pin bot's 15-minute crypto markets plus hourly BTC, by ET day:

| ET day | money | markets | losses |
|---|---:|---:|---:|
| Thu 09-18 | +$91.85 | 68 | 0 |
| Sat 09-19 | -$223.46 | 73 | 6 (the bug day, fixed 09-19..20) |
| Sun 09-20 | +$109.63 | 53 | 0 |
| Mon 09-21 | -$2.97 | 48 | 2 |
| Tue 09-22 | +$53.70 | 34 | 1 |
| Wed 09-23 | -$42.46 | 54 | 1 |
| Thu 09-24 (to 9:45 PM ET) | +$89.51 | 61 | 0 |

**Last 7 days: +$75.80 in all, +$10.83 a day on average; best day +$109.63,
worst -$223.46.** Leaving out the 09-19 bug day: +$49.88 a day over 6 days.
Coin race and oil are not in these numbers (they are separate books and
separate sizes).

Expected money per day = (contracts obtainable at that bank / 61.5 today) x
the daily average. First figure uses the 7-day average; in brackets, the
average without the bug day.

| bank | size | expected money per day | biggest loss on record, at that size |
|---:|---:|---:|---:|
| $1,000 | 85 | $10.7 [$49] | -$126 |
| $1,500 | 127 | $15.0 [$69] | -$188 |
| $2,500 | 212 | $22.4 [$103] | -$314 -- over the $200 day cap |
| $5,000 | 250 | $25.3 [$117] | -$370 -- over the cap |
| $10,000 | 250 | $25.3 [$117] | -$370 |
| $25,000 | 250 | $25.3 [$117] | -$370 |

**The honest caveat, once:** a loss scales with the whole size, a win only
with the contracts we actually got. At 250 contracts we obtain 57% of the
size but lose 100% of it when a market goes wrong. So each step up buys
less money per dollar at risk than the step before, and the 09-24 rules
(v-nospike, v-cap20, v-lateadd, v-btcd1) have one day of record. Every
money number above is a 7-day average that mixes four rule sets.

## Where the ceiling binds

- The book: from $1,500 to $2,500 the obtainable contracts rise 50%; from
  $2,500 to $5,000, 13%; after that, zero.
- The code: 250 contracts is reached at a bank of **$2,940** and nothing
  above it changes the size (`AUTO_SIZE_MAX`).
- So on the 15-minute markets **a bank past about $3,000 buys nothing**, and
  the last useful dollar is somewhere between $1,500 and $2,500 -- which is
  the same "$2.5-3k" the 09-23 fill study found (OPEN_WORK C3).

What the hourly family changes: if its fills are real, the book there holds
the full 250 at every bank level, so a bigger bank buys proportionally more
contracts -- up to the same 250 cap, which would need a fresh depth study
and an operator decision to raise. It does not change the $200 day cap or
the 20% halt, and it adds a second way to lose $200 in a day.

## Recommendation

Take the next step at a **bank of $1,500** (size 127: 38% more contracts,
worst single close $373, expected +$15 a day on the 7-day average or +$69
without the bug day), and take it by deposit only after three things are
true: (1) the weekend of 09-26/27 -- the first under the 09-24 rules --
closes with no day-cap halt, no drawdown halt, and the 7-day pin-bot total
still positive; (2) hourly BTC has ~30 fired closes with real fills at 1
contract and no hourly loss above $2 (the cap held); (3) the disk is solved
-- a drive plugged in and the recording moved -- because at 16.4 GB free
and ~4 GB a day the recorder stops itself on about 09-28, and nothing here
matters if the tape stops. $2,500 is the last step that buys anything on
the 15-minute markets; any bank above $3,000 belongs to the hourly family
only, after its fill data is in and after an explicit decision to raise
`--series-size`, which no unattended session may make.
