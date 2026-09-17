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

**A. Take deeper on one coin -- AND MY FIRST VERSION OF THIS WAS WRONG.**

**WITHDRAWN: "+45% more contracts at the same limit, same worst case, free."**
That was computed from the `signal` record's `take_n`/`size` fields, which
describe the depth at the TOUCH price only. The order the bot actually sends is
larger: `--depth-ladder` already expands the ask to the full SIZE and sweeps the
ladder up to the limit. Checked order by order against `body.count`:
**0 of 31 orders in the current version asked for less than SIZE while more was
on offer under the same limit.** There are no free contracts. The bot is
already taking everything its per-market rule allows.

So the real proposal is the one I described as merely a side effect: **raise the
per-market cap above SIZE.** That is new exposure on one coin, and it must be
priced as such.

| cap on ONE market | extra contracts, current version | extra, sweep era | ~$/day at the realised rate |
|---|---|---|---|
| 1.0 x SIZE (today) | +0 (+0%) | +238 (+2%) | $0-2 |
| **1.2 x SIZE** | **+384 (+18%)** | **+2,252 (+20%)** | **$19-25** |
| 1.6 x SIZE | +1,067 (+50%) | +6,100 (+54%) | $50-70 |
| 2.0 x SIZE (full close budget) | +1,702 (+80%) | +9,796 (+87%) | $81-112 |

**What caps it is the DRAWDOWN BRAKE, and the arithmetic is unforgiving.**
`MAX_DRAWDOWN = 0.20` measures the bank against a high-water mark stored in
`results/pinrun-hwm.json`, which never falls on its own. Bank $556.02,
high-water $574.79: the bank may fall to $459.83 before the bot HALTS, so there
is room for a **$96.19** loss.

Measured cost of a losing coin-leg, all 11 on the record, 430 contracts:
**62.3c per contract gross, 49.3c net after the hedge (which recovered 21%
overall and NOTHING on 7 of the 11), worst observed 98.0c.**

- At the worst observed 98c: $96.19 / 0.98 = **98 contracts**. SIZE is 94.
  **Today's single-coin position is already at 96% of what the brake allows.**
- At a fresh high the room is 20% of bank = $111.20 = 113 contracts = **1.21 x SIZE**.
- The FULL close budget on one coin (2 x SIZE = 188) loses $184 = **33% of the
  bank**, which is **1.66x what the brake permits**.

**And it cannot be grown out of.** SIZE = bank / 5.88 (BANK_BRAKE 3.0), so the
worst close is always bank/3 = 33%, while the brake is always 20%. Both scale
with the bank. The ratio is fixed until SIZE hits `AUTO_SIZE_MAX` 250 at a bank
of ~$1,470; the full budget only fits under the brake above a bank of ~$2,450.

**THE LATENT INCONSISTENCY THIS EXPOSED, which is worth more than the idea.**
The sizing rail (BANK_BRAKE 3.0) permits a close that the ruin rail
(MAX_DRAWDOWN 0.20) would halt the bot for. They contradict each other by 1.66x.
It has never fired because **two coins have never both lost** (below) -- an
empirical fact that no rail enforces. If one close ever did lose both legs, the
bot would halt, and because the high-water mark persists it would **halt again on
every restart** until the bank recovered, which it cannot do while halted. That
is a bot-offline-until-manual-intervention failure mode sitting in the current
design, not in the proposal.

**A TWO-COIN CLOSE IS GENUINELY TWO BETS -- so the current spreading is real.**
Over 101 closes where 2+ different coins were held: **0 had every coin lose.**
Given one coin lost, the other lost **0 of 9** times (baseline per-leg loss rate
4.00%). The 95% upper bound on that conditional rate is 33% (rule of three on
9), so this is a lean, not a proof -- but it leans the safe way, and it is why
the 1.66x inconsistency has stayed harmless.

**Not built, and not recommended as a fixed multiple.** If it is done, the honest
rule is a LIVE cap: contracts on one market <= (bank - 0.8 x high-water) / 0.98,
which is 98 today (i.e. nothing) and ~1.2 x SIZE at a fresh high. That is
~$20/day, not the ~$50 I first wrote.

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
