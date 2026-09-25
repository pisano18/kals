# HEDGE_FLIP_2026-09-25 -- "cash out and still hedge"

Operator, 09-25: *"if we're certain it's going down we cash out where it's at
and still hedge to save a little more?"* Read-only. Nothing live was built or
changed. Market times are ET (the clock the tickers carry); tickers are given
so any row can be looked up.

## Answer

**No. On our own record it would not reliably have made more money, and it
would have made the worst day worse.**

- **What the trade is.** On Kalshi, selling our side at the bid and buying the
  other side at the ask are the same trade. The hedge already buys the other
  side once, which locks $1 a pair. "Cash out and hedge" buys it a *second*
  time, so we end up holding a full bet that the price keeps going the other
  way. It is a new bet, placed at the moment we have just been wrong.
- **That bet only pays if the other side is cheap at the alarm.** It is not,
  measurably: after the model's confidence in a side crashes from 99.5% to
  under 40%, the index shows that side still wins **about 26 times in 100**
  (23 of 90 crashes, all coins, 09-01..09-25). So the other side is worth
  about 74c. We have been paying **69c on the first contract and 76c on the
  last** of our hedges. After the fee, that is roughly break-even: somewhere
  between losing 3c and making 4c a contract, and the range of what it really
  is covers both.
- **On our own 10 hedges under today's 0.40 trigger** (since 9/13), the extra
  bet at full size would have made **+$59** (**+$26** if each extra contract
  had cost 5c more, which is likely because the hedge had already taken the
  cheapest offers). The honest range is **-$124 to +$185**. With 9 usable
  markets, the smallest real edge this record could prove is **$301**, or
  43c a contract. It cannot tell a gain from a loss.
- **The one time it came back, it cost $67.** XRP 9/19 11:45 PM
  (`KXXRP15M-26SEP192345-45`): the extra 104 contracts at 63c would have lost
  **$67.22** on top of the $64.95 we actually lost. At full size the flip makes
  9/19 **-$275 instead of -$223** and the deepest fall from the high **26%
  instead of 22.5%** (the bot's brake halts at 20%).
- **The hedge itself is not the problem.** Hedging under 0.40 saved **$73.90**
  on those 10 markets. Hedges fired by the old 0.60-0.90 triggers lost
  **$53.06** (4 of 6 came back); those triggers are gone.

The hedge is worth keeping because it removes swings, not because it makes
money. The flip does the opposite: roughly the same expected money with
double the swing. You said this is money you need, so that is the wrong trade.

## 1. What the real hedge did -- every hedged market since 9/13

Money from Kalshi's ledger. "No hedge" = the same market without the hedge
leg. "Came back" = our side won anyway, so the hedge was a false alarm.

| market (ET close) | confidence at first hedge order | hedged | paid (first / last) | came back? | actual | no hedge |
|---|---|---|---|---|---|---|
| BNB 9/13 12:30 PM | 0.64 | 32 | 10c | yes | -$1.10 | +$2.31 |
| BTC 9/14 5:30 AM | 0.21 | 60 | 58c | no | -$34.26 | -$58.43 |
| HYPE 9/14 4:00 PM | 0.56 | 62 | 51c | no | -$29.90 | -$59.20 |
| NEAR 9/16 4:30 AM | 0.77 | 84 | 18c | yes | -$9.22 | +$6.77 |
| DOGE 9/16 9:00 AM | 0.49 | 87 | 15c | yes | -$12.14 | +$1.68 |
| BNB 9/16 12:30 PM | 0.53 | 1 | 47c | no | -$0.47 | -$0.98 |
| BTC 9/17 9:15 PM | 0.21 | 99 | 72c | no | -$27.87 | -$54.20 |
| DOGE 9/18 12:15 AM | 0.24 | 34 | 74c | no | +$4.36 | -$3.93 |
| BNB 9/19 1:45 AM | 0.27 | 1 of 76 | 76c | no | -$57.76 | -$57.99 |
| BNB 9/19 12:30 PM | 0.15 | 85 | 44c / 80c | no | -$61.75 | -$82.37 |
| HYPE 9/19 11:45 PM | 0.50 | 104 | 46c | yes | -$43.92 | +$5.73 |
| XRP 9/19 11:45 PM | 0.27 | 104 | 63c | yes | -$64.95 | +$2.27 |
| NEAR 9/21 12:45 PM | 0.39 | 81 | 70c / 90.5c | no | -$59.09 | -$74.25 |
| HYPE 9/21 6:15 PM | 0.23 | 55 | 57c | no | -$31.27 | -$53.98 |
| DOGE 9/22 10:45 PM | 0.05 | 13 | 95c / 98.6c | no | -$2.47 | -$2.71 |
| BTC 9/23 8:30 PM | 0.11 | 176 | 80c / 87c | no | -$130.41 | -$153.79 |
| **total, 16 markets / 15 closes** | | | | 5 came back | **-$562.21** | **-$583.06** |

Hedging made **+$20.85** overall: 11 saves +$170.93, 5 false alarms -$150.08.
Our log's hedge fills match Kalshi's count on all 16.

## 2. The variants, on the same markets at the same second

Extra contracts beyond what the hedge bought are priced at the **worst** price
that hedge paid (the book we actually hit), and again at 5c worse. Where the
hedge itself could not fill (BNB 9/19 1:45 AM got 1 of 76) no extra is
counted -- there was no book. "Range" = where the true number plausibly
lies, 95 times in 100.

**The 10 hedges under 0.40 (today's trigger), 10 closes:**

| variant | total | vs the live hedge | range of vs-live |
|---|---|---|---|
| no hedge | -$539.37 | -$73.90 | -$201 to +$112 |
| half hedge | -$495.02 | -$29.55 | -$92 to +$62 |
| **live hedge (now)** | **-$465.47** | -- | -- |
| hedge + extra 25% | -$450.70 | +$14.77 (+$6.44 at 5c worse) | -$31 to +$46 |
| hedge + extra 50% | -$435.92 | +$29.55 (+$12.87) | -$62 to +$92 |
| **hedge + extra 100% ("cash out and hedge")** | **-$406.37** | **+$59.10 (+$25.74)** | **-$124 to +$185** |

**All 16 hedges** (old triggers included): the full flip is **+$6.04**
(**-$46.27** at 5c worse), range -$287 to +$212. On the 6 old-trigger hedges
alone it is **-$53.06**.

**Earlier or later** (every one of the 662 positions we held since 9/13, hedge
fired second by second; about half the prices at the crash second come from
the ticker tape, which matched our own logged price only 9 times in 36 at
hedge moments -- treat as a rough guide):

- Hedging the moment confidence goes under 0.40 beats every alternative tried:
  a 1 s wait **-$36**, 2 s **-$75**, 3 s **-$70**; a trigger of 0.60 **-$78**,
  0.50 **-$76**, 0.30 **-$90**, 0.25 **-$78**; half size **-$118**. This
  agrees with the 09-24 rebuild. No change.
- The same sweep says the full flip was **+$233**, but $169 of that comes
  from 7 markets priced off the tape, and the tape shows offers at crash
  seconds that our bot did not find (BTC 9/17: tape 52c, our orders missed at
  63c and 66c and filled at 72c three seconds later; BNB 9/19 1:45 AM: tape
  29c, our bot could buy 1 contract, at 76c). The 7 markets priced
  from our own logs give **+$63.90**, the XRP loss included.

## 3. Is the other side cheap at the alarm?

- **Our 10 alarms under 0.40:** the model gave the other side 78% on average,
  its price was 69% (first fill), and it won 9 of 10. If the price had been
  exactly right, 9 or more wins would happen 12 times in 100, so this is not
  evidence. Across all 14 times our confidence crossed 0.40, our side came
  back **once**; the model expected 3.5 (10 times in 100 that few).
- **The index, every coin, 09-01..09-25** (72 closes): a side at 99.5% that
  then fell under 40% came back **23 times in 90 (26%, range 17-36%)**; the
  model expected 19%. So after a crash the model is, if anything,
  **too sure it is over** -- the opposite of what a flip needs.

  | what the crash looked like | crashes | came back | model expected |
  |---|---|---|---|
  | confidence fell to under 10% | 32 | 4 (12.5%) | 3.1% |
  | 10-20% | 9 | 1 (11%) | 13% |
  | 20-30% | 26 | 8 (31%) | 25% |
  | 30-40% | 23 | 10 (43%) | 35% |
  | one big index print (4+ normal moves) | 57 | 8 (14%) | 14% |
  | a slow slide (smaller prints) | 33 | 15 (45%) | 26% |
  | still under 40% three seconds later | 67 | 8 (12%) | 10% |

  The table has many rows, so any single row can look good by luck.

Break-even for the extra bet: the other side must cost less than about 73c
(74c, minus the fee). We paid 69c first and 76c last on average.

## 4. Risk -- what a false alarm does

The extra bet loses its whole price when our side comes back. 5 of 16 hedges
came back (1 of 10 under 0.40). The big day is 9/19:

| variant, only on the under-0.40 hedges | worst day (9/19) | deepest fall from the high |
|---|---|---|
| live hedge | -$223.46 | $235.84 (22.5%) |
| no hedge | -$177.09 | $204.41 (20.7%) |
| half | -$197.83 | $210.21 (20.7%) |
| extra 25% | -$236.28 | $248.65 (23.4%) |
| extra 50% | -$249.10 | $261.47 (24.3%) |
| extra 100% | -$274.73 | $287.10 (26.0%) |

Applied to all 16 old hedges the full flip makes 9/19 **-$324.38** and the
fall **30.6%**. Every flip size leaves 9/19 past the -$200 day cap and pushes
the fall further past the 20% brake. (What the cap and the brake would have
stopped after they fired is not modelled.) A flip also needs cash at the
worst moment: 88 extra contracts at ~75c is ~$66 per alarm, and it is not a
hedge, so the bot's stake cap and loss abort would apply to it.

## 5. Does any smaller version survive?

- **Only on a big index move** (the print that caused the crash was 4+ normal
  moves): on the index, 14% came back (57 crashes, range 6-25%), exactly what
  the model said. Our own 8 alarms of this kind all kept going, and the 5
  that were priced cost 57-99c (average 72c) against a model value of about
  77c. That is about **+4c a contract after fees**, from 5 markets. At 25% extra
  on an 88-contract position that is roughly **+$0.90 per alarm**, about
  one alarm every 1-2 days, against a **$16** loss each time it is wrong.
  Not worth building.
- **Only when confidence is already under 20%**: the index shows these come
  back 12 times in 100 (5 of 41) where the model says 5, so the model
  overrates them.
  Our sweep's +$111 for this rule is mostly tape-priced. Not a result.

No variant wins clearly, so no paper arm is proposed.

**What would change this:** a live record showing our side comes back after a
0.40 alarm less than about 20 times in 100 *at the prices we actually get*.
At roughly one alarm a day that takes months, and a paper arm cannot supply
it because a paper fill at a crash second is not a real one (BTC 9/23 showed
945 contracts offered and filled 21).

**A lead for the hedge itself (not the flip), unmeasured on our fills:**
crashes that were slow slides came back 45 times in 100, big single prints 14.
A hedge on a slide pays about fair price for a coin flip. Worth one read-only
pass on our own fills before anyone proposes a rule.

## Method

- `results/hedgeflip_2026-09-25/hedgeflip.py` (self-test plants a fair-price
  world, which reads about minus the fee, and a 15c-cheap world, which reads
  +13c; checks every variant by hand arithmetic, the drawdown, the parser;
  PASS). Money from `results/kalshi_ledger.json` (`pinledger.pnl`); prices,
  confidence and alarm seconds from our own `hedge*` records in
  `results/pinrun-live-*.jsonl`; the per-second sweep adds
  `results/cf_2026-09-24/cf_dataset.jsonl.gz` where our bot logged nothing.
  Output: `hedgeflip.out`.
- `results/hedgeflip_2026-09-25/crashidx.py`: index tape only, pinrun's own
  `fair()` on a socket-less `IndexWS`, every live coin and close 09-01 00Z to
  09-25 14Z (19,512 coin-closes, 19,555 sides that reached 99.5%, 90 crashes).
  The self-test reads a calibrated random walk as calibrated (0.94x) and a
  planted "keeps going" world as keeping going (0.02x); PASS. Output:
  `crashidx.out`, rows in `crashidx_rows.jsonl.gz`. It is not our loss rate:
  it says what the index did, not what we would have been filled at.
- Clustering is by close. Our record: 10 markets in 10 closes (under 0.40),
  16 in 15 (all). Index: 90 crashes in 72 closes; cross-coin correlation is
  ignored, so its ranges are, if anything, too narrow.
