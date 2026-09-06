# REFUTATION — Lens 1 of 3: correctness of the fill model in `research/queuesim.py`

Run 2026-09-06 on the operator's box, read-only. Nothing was written under
`kalshi_data/` or `feed_data/`. `replay.load_quotes` was NOT called. Both
collectors alive before and after every job (`kalshi_collector.py` pid 2708908
25.5 MB, `crypto_feeds.py` pid 531268 14.1 MB). Free RAM never below 3.6 GB;
free disk 52.01 GB.

**Verdict: PARTIALLY REFUTED, at moderate severity. The fill ENGINE survived
every attack I could construct. Two of the report's three validation claims do
not survive, and a measured 3-8% of the headline money comes from the very tick
zone the report says it excluded.** Nothing I found moves $294/day below the
$50/day threshold.

---

## Method

I did not review by reading. I rebuilt the per-level Kalshi book independently
from `orderbook_snapshot` + `orderbook_delta` in exchange **seq** order on the
**deci-cent** grid (`int(round(dollars*1000))`, so the tapered tick is exact),
and used it as a reference the stage has never been scored against.

Scripts (all in `C:\Users\Joe\AppData\Local\Temp\kals-work`):
`refute_depth2.py`, `refute_dprev.py`, `truesim.py`, `truesec.py`,
`qs_subset.py`, `fillqueue.py`, `lookahead.py`, `signctl.py`, `zoneleak.py`,
`offdepth.py`.

Confirmed first: `python research/queuesim.py --selftest` PASSES (26 checks),
`python research/shadow.py ..` clean exit 0, `python research/markers.py ..`
clean exit 0. All as reported.

---

## What SURVIVED — five attacks that failed to break the fill model

**1. The two-book yes-bid / no-bid subtlety IS handled, and I verified the part
the repo never checks.** `flow.py:_l1` derives the ask from `bk.no`
(`ya = 100 - nb`), and 89-93% of cached rows come from the `ticker` channel,
which carries `yes_bid_size_fp` and `yes_ask_size_fp` directly. **`flow.py`'s
own agreement check compares PRICES ONLY** (`if bl[0] == b and bl[2] == a_`,
flow.py ~line 530) — the SIZES, which are the entire queue-position input, are
never validated anywhere in the repo. I ran that check:

    KXBTC15M, hour 20260901T12, 1,328,001 book events, 2,498 ticker instants
      prices   exact agreement  2,493 / 2,498   99.8%
      bid_size exact agreement  2,485 / 2,493   99.7%   (ticker/recon median 1.000)
      ask_size exact agreement  2,481 / 2,493   99.5%   (ticker/recon median 1.000)
    0 crossed / invalid L1 states over the hour.

The input is sound. The gap is in `flow.py`'s validation, not in the number.

**2. Sweep legs are NOT double counted, and the unit is right.** I matched each
trade to the `orderbook_delta` that consumes it: on `KXBTC15M-26SEP010830-30`,
24,648 trades, **0 with no consuming delta at the same `ts_ms` and price**, and
`|delta_fp| == count_fp` exactly on all 10,797 keys owned by a single trade
(the rest are keys shared by several trades in the same millisecond). So
`count_fp` is in the same unit as the book's sizes — a stronger check than the
report's `volume_fp` argument — and front-first cumulative consumption within a
second is the correct treatment of per-level (or per-fill) printing.

**3. No duplicated trades.** Whole day 20260901: `gzsalvage.iter_lines` yielded
**3,313,524** lines, identical to `gzip.open` on all 24 files, and **0
duplicate `trade_id`** among 3,313,524 messages.

**4. The "strictly earlier" guard holds across channels — my best theory for a
maker.py-style look-ahead, and it failed.** The trade channel and the ticker
channel have different receive lags (hour 20260901T12: trade median 31 ms, p90
1,140 ms; ticker median 311 ms), so "one receive second earlier" need not be
earlier at the exchange. Measured over the whole day, per trade, against the
exchange stamp of the ticker message that produced the governing book row:

    3,306,500 trades scored
    book row stamped AT OR AFTER the trade it must precede:  145  (0.004%)
    book_row_ts - trade_ts:  p10 -1,711 ms   median -784 ms   p99 -125 ms

**5. The queue-ahead number is good enough; replacing it with the exact book
moves fills by under 10%, upward.** I re-implemented queuesim's model exactly
(one-second clock, join the back, front-first, prorata cancels, ZONE 10-90,
camp/no-camp) but initialised `ahead` from the **reconstructed** depth at the
second boundary instead of flow.py's snapshot, on the same 3 BTC markets and
hour, and ran `queuesim.simulate_side` itself on the same inputs:

    contracts filled, KXBTC15M x3, hour 20260901T12
                       queuesim      true-depth, same 1s model
      camp   S=1          326.1              353.2
      camp   S=50      15,360.3           16,738.6
      nocamp S=1          315.3              323.8
      nocamp S=50      11,289.4           11,652.8

    the same model at MICROSECOND resolution on the true book:
      nocamp S=1   1,229.9 (prorata) / 622.7 (behind)   -- i.e. far MORE

**The headline fill count also reproduces.** One day (20260901), no-camp,
prorata, ZONE 10-90: **38,693.6 contracts at S=1** against the report's
38,553/day, and $284/day at S=1 over 188 closes on 20260901-02 against the
report's $294.

I also tested and rejected: fills concentrating in thin-book moments (the
fill-weighted displayed touch depth is median **50** against a time-weighted
median of **57** — not a thin-tail artefact); and the theory that the cached
depth is biased low because the ticker fires on trades (`cached/true` at
at-touch print instants: p10 0.4, median 1.0, p90 6.5 — noisy in both
directions, not biased).

---

## What is WRONG — three defects

### D1. The off-touch placebo is not a placebo. `queuesim.py:834, 846`

    off = offset if k == BID else -offset          # line 834
    ...
    ap((sec0 + o, p - off, sz_arr[o]))             # line 846

`offset` moves the quote **price** off the touch but leaves the queue-ahead as
`sz_arr[o]` — **the size resting AT THE TOUCH**, at a price where our order is
not. The order is stood behind the wrong queue.

This is not fixable from this input: `flow_cache/*.v4.csv.gz` stores only level
one (`ticker,sec,bid_c,ask_c,bid_sz,ask_sz,ofi,nmsg,dbid,dask,src`), so the
depth at an off-touch price is not in the cache at all. Measured on the
reconstructed book, the substitution is materially wrong exactly where fills
are generated — the thin tail:

    true depth, sampled book states, KXBTC15M hour 20260901T12
      AT the touch          p10   147   MED 2,989
      1c BEHIND the touch   p10   560   MED 2,190     <- p10 is 3.8x the touch's
      2c BEHIND             p10   899   MED 1,850
      5c BEHIND             p10 1,025   MED 1,455

So the placebo credits an off-touch quote against a queue roughly a quarter of
the real one in the regime that decides fills. **The report's artefact-hunt #5
— "the informative reading is the gradient: 61.5% -> 31.6% -> 8.3%. The
estimator is strongly price-sensitive" — is therefore not a measurement of
price sensitivity.** It is the only real-data check the report offers for
requirement (c); the rest of (c) is verified only in the self-test, where the
trade prices never equal the quote and the check is trivially satisfied.

Note the direction: fixing this would make the placebo look *better*, so it
does not inflate the headline. But "requirement (c) enforced structurally and
verified" is not supported by the run that is cited for it.

### D2. The sign-scrambled control is scrambled at the wrong unit. `queuesim.py:872`

    sh[close] += rng.choice((1.0, -1.0)) * pnl * q / 100.0

The sign is drawn **per fill**. Every fill in one market shares **one**
settlement outcome `Y`, and that shared factor is where essentially all the
per-close variance lives — CLAUDE.md's own rule: *"Cluster by close time...
Hundreds of trades share one settlement outcome."* Scrambling per fill destroys
it, so the control's null is narrower than the statistic it nulls. Measured on
188 closes (20260901-02, no-camp, prorata, 4,000-rep bootstrap):

    S=1    real            $284/day  [  +112,   +463]   per-close sd  13.05
           shuf per FILL    -$12     [  -132,   +111]   sd  8.96  <- queuesim's control
           shuf per MARKET  -$31     [  -182,   +134]   sd 11.56  <- the correct unit
           variance ratio (per-fill control)/(real) = 0.471

    S=50   real          $7,302/day  [+3,072, +11,339]  per-close sd 313.84
           shuf per FILL   -$384     [-3,416,  +2,766]  sd 229.17
           shuf per MARKET -$3,825   [-7,390,     -39]  sd 278.55
           variance ratio = 0.533

The reported control throws away **half the variance of the thing it is meant
to null**, so "sign-scrambled control clean at every size" carries much less
information than stated. The self-test cannot catch this: check (d) plants a
**constant** +40c on every fill, which is precisely the case a per-fill
scramble nulls correctly. The correct per-market control still straddles zero,
so this weakens the evidence, not the estimate.

### D3. The 0.1c tick zone is NOT excluded from the headline — it leaks in at the two zone edges and carries 3-8% of the money.

The headline restricts to a cached touch in 10c-90c because "there the grid is
exact". It is not exact at the boundaries. `flow.py` stores top of book as
`int(round(dollars*100))`, so a **true** touch anywhere in 9.50-10.49c caches as
`10` and 89.50-90.49c caches as `90` — both inside ZONE, both on the 0.1c tick.
`load_trades` rounds print prices the same way (`pc = int(round(pf))`), so every
print from 9.6c to 10.4c reads as *at our 10c quote*. Measured, 20260901:

    cached in-zone touch observations              992,281
      touch cached at exactly 10c   12,709  (1.28%)
      touch cached at exactly 90c   14,067  (1.42%)

    S=1  no-camp: 38,694 contracts, $259
      at 10c and 90c: 1,979 contracts (5.1%), $19 (7.5% of the money)
    S=50 no-camp: 763,306 contracts, $7,054
      at 10c and 90c: 32,464 contracts (4.3%), $197 (2.8% of the money)

2.7% of the in-zone touch observations generate 4-5% of the fills — a ~2x
over-representation, which is what a blurred price grid does to a
queue-clearing condition. Independently confirmed that the grid IS exact
strictly inside the band: of 400,001 deltas scanned in one hour, **0** sub-cent
levels had a whole-cent part in [10, 89]. So the leak is precisely and only at
the two edges — and it is the one place I found where the maker is credited
with fills a real resting order could not have received: a quote at "10c" being
filled by prints at 9.6c.

### D4 (minor). Silent discards. `queuesim.py:673, 685, 696, 707, 715`

`load_trades` increments `unparsed`, `no_timestamp`, `bad_price`, `bad_size`
and `no_taker_side` and **never prints any of them**. CLAUDE.md: *"A guard that
discards data needs its own null: print how much it throws away on a healthy
feed."*

### D5 (minor). The self-test cannot see the real failure modes.

All three synthetic worlds (`_alt_states`) have **one price level and a
constant displayed depth**. The self-test never builds a book where the
displayed depth is stale relative to the true depth, where the level is
replenished between prints, or where the touch price carried from t-1 is no
longer the touch at t — the three things that actually decide the answer on
real tape. It is a correct test of the queue arithmetic and a null test of the
input. (The input turns out to be fine — see survivor 1 and 5 — but that was
established here, not by the stage.)

---

## What this does and does not do to the verdict

It does **not** rescue the $50/day kill criterion. Strip D3's 7.5% and widen
D2's null and S=1 no-camp is still several hundred dollars a day with an
interval far above $50. The fill count is reproducible and survived being
re-run against an exactly reconstructed microsecond book.

What it does is remove two of the three things the report leans on when it says
the number is not an artefact: the off-touch placebo (D1) and the
sign-scrambled control (D2) are not the checks they are described as. The third
leg — the +0.774c benchmark on the whole at-touch population — is outside this
lens.

## Like you're five:

Someone built a pretend trader that stands in a queue and counted how often it
got served. I tried very hard to prove the counting was wrong. I rebuilt the
real queue from scratch out of a different set of records, message by message,
and checked the pretend trader's queue against it: it matched almost exactly,
and when I re-ran the whole thing using the rebuilt queue instead, the pretend
trader got *slightly more* served, not less. So the counting is basically
right.

But two of the safety checks used to prove the counting is right are broken.
One of them moves the pretend trader to a different spot in the shop but
forgets to change the length of the queue it is standing in, so it tells you
nothing. The other is a "what if this were all luck" test that shuffles the
results one item at a time when it should shuffle them one shop at a time —
every item in a shop shares the same outcome, so shuffling item by item makes
the test far too easy to pass. And a small slice of the money (about 3 to 8
cents in every dollar) comes from two prices where the pretend trader's price
board is blurry and it is being handed items it was never actually queueing for.

## What I need from you:

Nothing, this refutation is complete. If you want the two broken checks fixed
before the rule is frozen, the fixes are: (1) either drop the off-touch placebo
or rebuild it from a book that stores more than level one; (2) draw the
scramble sign once per MARKET, not once per fill; (3) narrow ZONE to 11c-89c,
which removes the blurred edges at a cost of about 4% of the fills.
