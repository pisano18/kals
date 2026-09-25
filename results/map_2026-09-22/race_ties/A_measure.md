# A_measure -- coin race TIES

2026-09-23. Label: measure. Read-only: nothing was written outside this file
and my scratchpad; no process was started, stopped or signalled.
Collectors verified alive at the end (`kalshi_collector.py` pid 105304, 48 MB;
`crypto_feeds.py` pid 105352, 31 MB). Free disk 24 GB (guard 6 GB).
Every python job here held under 250 MB.

## Headline

A coin race settles as a **two-way TIE that pays 50c on every contract of both
tied coins** in **0.75% of all races** (22 of 2,927, 2026-08-20 to 2026-09-23)
-- but in **~2% of the races WE enter** (1 of 49 live; 1.6% by reweighting),
because we enter photo finishes. At 97-98c a tie costs **-47c a contract**,
so one tie wipes out **17-25 wins**. Ties alone consume **42-53% of the 1.86%
break-even budget** and **~28-35% of the gross edge**.

**The one tie we have had flipped the whole coin race programme from +38c to
-57c.** Kalshi's ledger: 96 legs over 57 events, **-$0.5698 net on $89.57
staked**; the two tie legs were **-$0.9535**, the other 94 legs **+$0.3837**.

**And a tie IS visible before entry.** A race-level floor of **0.75 basis
points on the top-two gap at tau 2 refuses 7.2% of races and catches 13 of 13
ties** that have an index rebuild; the kept 94.4% of races contain **zero
ties**. Neither of the two rails we have (z >= 3, the 90c price floor) refuses
it: the z floor **does not apply inside tau 30 by design**, and both legs were
bought at 97c and 98c.

---

## 1. How often does a coin race settle as a tie?

### 1a. From Kalshi's own results -- two independent sources, and they agree

| source | what it is | races | ties | rate |
|---|---|---|---|---|
| `C:\kals\fulltape\lead.json` | Kalshi REST settlement pull, 2026-08-20 16:15Z .. 2026-09-11 22:30Z | 1,874 | 17 | **0.907%** |
| `market_lifecycle_v2` tape | `event_type:"determined"` rows, 2026-08-25 02:00Z .. 2026-09-23 14:15Z | 2,575 | 14 | **0.544%** |
| **union** | every race either source covers | **2,927** | **22** | **0.752%** |

**The two sources agree on all 1,522 races both cover** (9 ties each, same 9).
They differ only in which races they hold -- the tape is missing 23 damaged
hour files, the pull stops on 09-11. So 0.752% is the best single number:
**about 1 race in 133**, roughly **one every 1.4 days** at 96 races a day.

Kalshi's own leg-level shape, from the tape (2,575 events, all 5 legs
determined in every one): 10,286 `no`, 2,561 `yes`, **28 `scalar`** with
`settlement_value: "0.5000"`. 2,561 events had exactly one `yes`; **14 had zero
`yes` and exactly two `scalar`**. **Every tie in 34 days has been two-way.** A
three-way tie (which would pay 33c) has never happened, so nothing here is
evidence about one.

`results/kalshi_ledger.json` -- the races we actually held -- has 96 coin race
leg-rows over 57 events, **1 tie: 1.75% of the events we were in** (n far too
small on its own; it is consistent with the enriched ~2% below).

The 14 tape ties, with how long Kalshi took to determine them:

| close (UTC) | event | tied pair | determined after |
|---|---|---|---|
| 2026-08-25 02:00 | 26AUG242200 | HYPE, XRP | 869 min |
| 2026-08-25 11:15 | 26AUG250715 | BTC, ETH | 314 min |
| 2026-08-27 07:00 | 26AUG270300 | ETH, HYPE | 571 min |
| 2026-08-27 13:30 | 26AUG270930 | SOL, XRP | 181 min |
| 2026-08-27 13:45 | 26AUG270945 | BTC, XRP | 166 min |
| 2026-08-28 00:00 | 26AUG272000 | BTC, ETH | 6 min |
| 2026-09-08 12:00 | 26SEP080800 | BTC, ETH | 76 min |
| 2026-09-08 17:30 | 26SEP081330 | BTC, SOL | 57 min |
| 2026-09-10 22:15 | 26SEP101815 | SOL, XRP | 40 min |
| 2026-09-12 18:30 | 26SEP121430 | BTC, XRP | 40 min |
| 2026-09-14 04:30 | 26SEP140030 | ETH, XRP | 41 min |
| 2026-09-16 11:00 | 26SEP160700 | BTC, ETH | 51 min |
| 2026-09-16 15:00 | 26SEP161100 | BTC, SOL | 11 min |
| 2026-09-23 11:15 | 26SEP230715 | HYPE, XRP | 161 min |

(the pull adds 8 more: 08-21 15:30, 17:15, 17:30; 08-26 08:45, 11:15, 14:30,
16:45; 09-02 23:15 -- all in hours the lifecycle tape lost.)

Coins involved across the 13 ties with an index rebuild: BTC 8, XRP 6, ETH 6,
SOL 4, HYPE 2. No coin is safe and no coin dominates.

### 1b. Independently, from the index

`research/idxload` fast parse over all 677 `cfbenchmarks_value` hour files,
streamed hour by hour on exchange seconds with a two-hour rolling window
(peak RSS ~220 MB). Per race, per coin, the settlement rule from
`research/pinracemodel.py`:

```
return = mean(prints in [close-60, close-1]) / mean(prints in [close-960, close-901])
```

**2,594 races** had all five coins with >= 57 of 60 prints in both windows,
2026-08-25 04:30Z .. 2026-09-23 14:15Z.

Three validations, all clean:

1. **Winner: 1,493 of 1,493 (100%)** of the races where Kalshi named one
   outright.
2. **Tied pair: 8 of 8** inside the overlap -- the index names exactly the two
   coins Kalshi marked `scalar`, and they are ranks 1 and 2 every time.
3. **My raw TWAP, rounded to Kalshi's own `round_digits`, equals Kalshi's own
   published settlement value in 8,326 of 8,386 checks (99.28%).** The 60 that
   differ are almost all one unit in the last place (median 0.013 bp, p90
   0.044 bp, max 0.371 bp).

So the index rebuild *is* the settlement number, to Kalshi's last published
digit. The counting above is therefore Kalshi's, not a model's.

### 1c. The worked example: 2026-09-23 07:15 ET

**The ticker time is EASTERN, not UTC.** `KXCRYPTOLEAD15M-26SEP230715` closed
at **11:15:00Z**. (`lead.json` proves it: `...111830` carries
`close: 1789165800` = 2026-09-11T22:30:00Z. My first rebuild at 07:15Z showed
XRP last and HYPE winning by 7 bp -- a different race entirely. If a race
number ever looks absurd, check this first.)

| coin | final return | as % change | TWAP numerator / denominator | Kalshi's published strike |
|---|---|---|---|---|
| **XRP** | 0.99850328079845 | **-0.1496719%** | 1.5914338333 / 1.5938193333 | 1.5938 (4 dp) |
| **HYPE** | 0.99849411041891 | **-0.1505890%** | 95.8419083333 / 95.9864533333 | 95.9865 (4 dp) |
| ETH | 0.99820663065681 | -0.1793369% | 2732.5821667 / 2737.4915000 | 2737.49 (2 dp) |
| BTC | 0.99810338128601 | -0.1896619% | 85739.5990000 / 85902.5233333 | 85902.52 (2 dp) |
| SOL | 0.99712722278834 | -0.2872777% | 117.2603333 / 117.5981667 | 117.5982 (4 dp) |

All five of my denominators round to Kalshi's five published 15M strikes digit
for digit, so the reconstruction is exact.

**XRP beat HYPE by 9.17e-06 of return = 0.0917 basis points = 0.00092%.**
On the raw numbers XRP won outright. Kalshi paid both 50c.

The bot's own log agrees to the eighth decimal (`settled` row, `returns`:
XRP 0.99850328, HYPE 0.99849411) and printed the gap itself: `gap_bp: 0.0889`
on the XRP fill at tau 2.

---

## 2. What makes a tie

**Not identical prints. Not a clean rounding rule. It is a photo finish that
goes to a slow, discretionary determination.** In order of what the data
supports:

1. **It is always a photo finish, and the boundary is sharp.** Every one of the
   13 ties with an index rebuild closed with a top-two gap **below 0.58 bp**
   (0.0058%). Of 2,543 races, 2,363 closed more than 1 bp apart and **not one
   of those tied**. Tie rate by closing gap:

   | closing top-2 gap | races | ties | rate |
   |---|---|---|---|
   | 0.00 - 0.05 bp | 8 | 2 | 25% |
   | 0.05 - 0.10 bp | 16 | 4 | 25% |
   | 0.10 - 0.20 bp | 23 | 2 | 8.7% |
   | 0.20 - 0.30 bp | 26 | 2 | 7.7% |
   | 0.30 - 0.50 bp | 44 | 2 | 4.5% |
   | 0.50 - 0.75 bp | 63 | 1 | 1.6% |
   | 0.75 bp and up | 2,363 | **0** | **0%** |

2. **NOT identical prints.** **Zero** of 2,543 races had two coins with exactly
   equal returns, whether computed from raw TWAPs or from Kalshi's own
   published `settle` values. No tie was an exact numerical draw.

3. **NOT a rounding rule I can reproduce.** I tested "tie iff the two leaders'
   percent change is equal after rounding to D decimals", on raw TWAPs and on
   TWAPs rounded to Kalshi's `round_digits`, for D = 1..8. No D works:
   D = 2 catches all 13 ties but also flags 112-114 races Kalshi resolved to a
   winner; D = 3 catches only 1-2 and misses 11-12. Same result using Kalshi's
   own published `settle(C)/settle(C-900)`. And the two sides interleave: a
   race **0.0195 bp** apart got an outright winner, while one **0.577 bp**
   apart was tied. **No single precision, and no single gap threshold,
   separates ties from non-ties.**

4. **Rounding is nevertheless the right order of magnitude, and it names the
   exposed coin.** Kalshi settles each index to a fixed number of decimals
   (`round_digits` off `market_lifecycle_v2`, confirmed against 2,205-2,207
   strikes per series): BTC 2, ETH 2, SOL 4, XRP 4, HYPE 4. One unit in the
   last place, as a fraction of price, is:

   | coin | last digit | at current price | in bp of return |
   |---|---|---|---|
   | **XRP** | 0.0001 | ~1.59 | **0.63 bp** |
   | ETH | 0.01 | ~2,737 | 0.037 bp |
   | HYPE | 0.0001 | ~96 | 0.010 bp |
   | SOL | 0.0001 | ~117.6 | 0.0085 bp |
   | BTC | 0.01 | ~85,900 | 0.0012 bp |

   **XRP's last published digit is worth 0.63 bp -- 50x HYPE's and 500x BTC's**,
   and it spans the entire tie zone on its own. XRP is in 6 of the 13 ties.

5. **NOT a stale constituent.** Every tie race had 60 of 60 prints in both
   windows for all five coins (that was the filter to be in the sample at all),
   and the 09-23 example is 60/60 on all five.

6. **What it actually is: a slow manual determination.** A normal race is
   determined **39 s** after close (median, n=2,561; minimum 22 s). **Every one
   of the 14 ties took 338 s or longer** (5.6 min to 14.5 h, median 67 min).
   **0 ties in the 2,292 races determined within 300 s.** The tie is what comes
   back when the automatic determination cannot separate two coins and a human
   process decides -- which is why no arithmetic rule reproduces it, and why
   the first 48 seconds after a close are blind to it.

---

## 3. What it costs

### 3a. The real money, on Kalshi's ledger

| | legs | events | net |
|---|---|---|---|
| every coin race leg we have ever held | 96 | 57 | **-$0.5698** on $89.57 staked |
| the 2 tie legs (26SEP230715) | 2 | 1 | **-$0.9535** |
| everything else | 94 | 56 | **+$0.3837** |
| legs bought at >= 90c (the current rail), ties excluded | 87 | 52 | **+$2.0389** = **+2.34c a leg** |

Per leg: XRP YES cost 0.9700 + 0.0021 fee, paid 0.5000 → **-0.4721**.
HYPE NO cost 0.9800 + 0.0014 fee, paid 0.5000 → **-0.4814**.

**One tie in 57 events turned +38c into -57c.** The only other real losses are
two legs filled at 85-86c (-$0.8685, -$0.8590) that the 90c floor now removes,
plus four sub-cent penny YES bets.

### 3b. Our entry population is enriched in photo finishes

| population | races | close inside 0.58 bp (the tie zone) |
|---|---|---|
| all races | 2,543 | 141 = **5.5%** |
| races the live penny test actually bet | 49 | 6 = **12.2%** |
| races the z3 paper arm bet | 33 | 2 = 6.1% |

**We are ~2.2x more likely than a random race to be holding a photo finish**,
because at tau 2 the model reads a 0.09 bp lead as 99% and buys it: the entry
`|gap_bp|` was **below 0.58 bp on 4.6-9.2% of fills**, and the smallest was
0.0775 bp.

Reweighting the closing-gap buckets in 2b by our own live entry distribution:

**P(tie | a race we entered) = 1.59%**, against a base of 0.51% in the same
sample -- **3.1x**. Scaling to the union base rate (0.752%) gives ~2.3%.
Observed live: **1 tie in 49 entered races = 2.04%**. Call it **~2%, i.e. one
tie in every ~50 races we enter.** (The tightest buckets rest on 2 and 4 ties
out of 8 and 16 races, so this number is noisy; the three routes agreeing at
1.6-2.3% is the confidence, not any one of them.)

### 3c. Expected cost, per race and per day

We hold **1.49 legs on a top-2 coin per entered race** (73 of 85 live legs;
86% of all our legs sit on a coin that a tie would hit). In a tie **both tied
coins pay 50c, so the leader's YES and a rival's NO lose together** -- the
"spread" across a race is not a hedge against a tie, it is double exposure.

```
expected tie cost per entered race = 2.0% x 1.49 legs x 46.3c = 1.38c
                    (at the 1.59% figure)                     = 1.10c
gross per entered race at >=90c, ties excluded                = +3.92c
```

**Ties eat 28-35% of the gross edge.** At 13 entered races a day:
**-$0.14 to -$0.18 a day at 1 contract; -$36 to -$45 a day at 250 contracts.**

### 3d. Against the 1.86% break-even

At 98c: a win is +1.86c, a full loss -98.14c, **a tie -48.14c = 0.491 of a full
loss.** At 97c: +2.79c, -97.21c, **-47.21c = 0.486 of a full loss.**
**One tie erases 17 wins at 98c, 25 wins at 97c.**

A leader-YES leg is on a tied coin whenever the race ties, so its tie rate is
the race rate:

| | tie rate | loss-equivalent | share of the 1.86% budget |
|---|---|---|---|
| all races | 0.75% | 0.37% | **20%** |
| races we enter (reweighted) | 1.59% | 0.78% | **42%** |
| races we enter (live, 1 of 49) | 2.04% | 1.00% | **54%** |

**Ties alone spend 42-54% of the entire break-even budget before anything else
goes wrong.** That is the finding: the strategy is not 1.86% away from
break-even, it is ~0.9-1.1% away.

### 3e. The paper record is worse, because paper runs at size

Two tie races have been bet on paper, and **both were booked as wins**:

| race | paper legs | booked | truth at those prices and sizes | error |
|---|---|---|---|---|
| 26SEP161100 (09-16 11:00Z) | BTC YES 235 @95c, SOL NO 242 @94c, both at tau 3, `gap_bp 0.0158`, `worth 1.0` | **+$24.50** | **-$214.00** | **-$238.50** |
| 26SEP230715 (09-23 11:15Z) | BTC NO 1 @98c, HYPE NO 250 @84c, XRP YES 9 @97c | **+$37.89** | **-$91.61** | **-$129.50** |

(the 09-16 arm's `worth` was **1.0** -- the model said certain -- on a
**0.0158 bp** gap, with both legs on the two coins that tied.)

**Every paper-arm P&L number that includes either of those races is wrong by
$130-$238.** At the 235-250 contract size the penny test is a precursor to,
**one tie costs about -$214.**

### 3f. Does a tie count as a LOSS for the pre-registered bar?

The bar (HANDOFF.md, written before the z3 arm ran): *"PASS at 125 races with
0 losses, or 250 with at most 1; KILL at 2 losses in the first 50."*

**Yes, and the honest weight is half a loss.** A tie costs 0.49 of what a full
loss costs and destroys 17-25 wins, which is exactly what the bar exists to
bound. Arithmetically: **2 ties = 1 loss.** So the bar should read *"125 races
with 0 losses and 0 ties"*, or *"at most 1 tie and 0 losses"* if you want the
same expected cost.

**But the bar cannot currently see one at all.** `pinracearm.py` scores from
its own `winner_from`, which is `max(rets.items(), key=...)` -- a single argmax
that has no tie state -- and then sets
`p["win"] = (coin == won) if side=="yes" else (coin != won)`. For the 09-23 tie
`won` was XRP, so the XRP YES scored a win and the HYPE NO scored a win
(HYPE != XRP). `lost` was empty, so `stop_on_loss` never fired and the rolling
stake was released as if both had paid a dollar. **The z3 arm -- the arm the
125-race bar belongs to -- has already taken 1 tie in 33 entered races (~half a
loss by the arithmetic above) and its own log reads `won 2/2, pnl +0.0465`.**

---

## 4. Is a tie predictable before entry?

### 4a. The actual race, second by second, from the bot's own log

| moment | what the bot saw | what it did |
|---|---|---|
| tau 60 | XRP leads HYPE by **+0.7521 bp** | XRP YES ask 70c, `below_min_price`; HYPE NO 82c, `thin_edge` |
| tau 31 | XRP leads HYPE by **2.125 bp** | **paper** HYPE NO 250 @84c, `worth 0.855` |
| tau 2 | XRP leads HYPE by **0.0889 bp** (`0.0938` in the z3 arm), `zmin 2.3327` | **REAL** XRP YES 1 @97c (`worth 0.99`), **REAL** HYPE NO 1 @98c (`worth 0.993`) |

**The tie was visible, in the bot's own printed number, at the moment it
bought: a 0.09 bp gap is inside the 25%-tie bucket.** It bought anyway because
`--min-gap-bp` is **0.0** and the fair model has no tie state -- its outcome
space is {this coin wins, it does not}, so the most it can ever price is 1.0.
It said 99.0% and 99.3% on the two legs of a coin flip.

### 4b. Neither existing rail refuses it

- **z >= 3 (`arm-race-z3`): NO.** `--min-z-tau 30` means the floor
  **applies only PAST tau 30**, by design and with the reasoning in the
  function's own docstring (*"Inside 30 s ... a fifth of a basis point reads as
  3.6 sd ... z is the wrong ruler at small tau"*). Both real fills were at
  **tau 2**. Proof from the arm's own log: `pinracearm-z3.jsonl` took **both
  legs** at tau 2 with `zmin 2.3327` -- below its own floor of 3 -- and booked
  `won 2/2, pnl +0.0465`.
  Worth knowing: **zmin was 2.33, so a z floor applied at EVERY tau would have
  refused this race.** From the arms' own logs at tau <= 5 the z >= 3 crossing
  sits between 0.094 bp (z = 2.33) and 0.396 bp (z = 12.35), which would catch
  the 10 of 13 ties whose tau-2 gap is under 0.25 bp and miss the 3 at
  0.42-0.66 bp. n = 10 rows; that is an indication, not a measurement.
- **The 90c price floor: NO.** The legs were bought at **97c and 98c**. The
  floor is about cheap fills; a tie is a full-confidence event.

### 4c. What WOULD have refused it: a race-level gap floor at the last look

Projected top-two gap at tau (locked prints + the newest print for the rest --
the same projection `pinracemodel.returns_at` uses), on 2,542 races:

| floor on the top-2 gap at tau 2 | races refused | ties caught | tie rate in the KEPT set |
|---|---|---|---|
| 0.25 bp | 48 (1.9%) | 10 of 13 | 0.120% |
| 0.50 bp | 113 (4.4%) | 11 of 13 | 0.082% |
| **0.75 bp** | **183 (7.2%)** | **13 of 13** | **0.000%** |
| 1.00 bp | 244 (9.6%) | 13 of 13 | 0.000% |
| 1.50 bp | 357 (14.0%) | 13 of 13 | 0.000% |

**At tau 2, no race more than 0.75 bp apart has ever tied: 0 in 2,358.**
The tied pair was already the top two at tau 2 in **13 of 13** (and at tau 10,
30 and 60 in 13 of 13 too -- the *pair* is knowable early, only the *ordering*
is not).

The signal decays with time to close, so the floor has to be read at the last
look, not at the first:

| tau | floor needed for 13 of 13 | races it refuses |
|---|---|---|
| 2 | 0.75 bp | 7.2% |
| 10 | 1.0 bp | 9.6% |
| 30 | 1.5 bp | 14.1% |
| 60 | no floor works -- 3 ties sat at 2-4 bp at tau 60 | -- |

Could 13 of 13 be luck? Only 7.2% of races sit under 0.75 bp at tau 2, so under
a null of no relation the chance of all 13 landing there is ~1e-14. The
relation is real. What is *not* proven is the exact threshold: it is the
observed maximum (0.656 bp) plus a margin, fitted to the same 13 ties, so a
future tie can exceed it. **1.0 or 1.5 bp is the conservative choice and costs
2.4 / 6.9 more percent of races.**

### 4d. The same floor on our own live money

Kalshi's ledger, the 49 live races with an index rebuild, refusing a race when
the projected gap at its earliest decision tau is under the floor:

| floor | races refused | $ on the refused races | $ on the kept races | ties refused |
|---|---|---|---|---|
| none | 0 | -- | **-$0.6692** | 0 of 1 |
| 0.25 bp | 2 | -$0.8977 | +$0.2285 | 1 of 1 |
| 0.50 bp | 4 | -$0.7672 | +$0.0980 | 1 of 1 |
| **0.75 bp** | **7** | **-$1.3923** | **+$0.7231** | **1 of 1** |
| 1.50 bp | 10 | -$1.2807 | +$0.6115 | 1 of 1 |

**A 0.75 bp floor would have refused 7 of our 49 live races; those 7 lost
$1.39 between them and the other 42 made 72c.** Real fills, Kalshi's ledger,
not the replay. n = 7 refusals and the threshold was chosen on the tie data, so
read this as a consistency check, not as the proof -- and note it removes
*both* failure modes, the tie and the wrong-winner photo finish (two of the
seven are the 85-86c losses), which is what you would expect if photo finishes
are simply where this strategy loses.

### 4e. A second, independent rail: the determination clock

**A normal race is determined 39 s after close (median, n = 2,561; min 22 s).
Every tie took 338 s or more. 0 of the 2,292 races determined inside 300 s was
a tie.** So:

- `lag <= 300 s` → **0 ties in 2,292**.
- `lag > 300 s` → 14 of 283 = **4.9%** tie.
- `lag > 600 s` → 13 of 62 = **21%** tie.

This is the fix for the rail the operator actually relies on. It does not need
a model: **do not score a race, release its stake, or clear the first-loss halt
until Kalshi has determined it.** If nothing has arrived by 5 minutes after
close, the race is a tie candidate and new entries should stop until it lands.

---

## 5. Refuted / not supported

- **"A tie is identical prints."** No. Zero of 2,543 races had two coins with
  exactly equal returns, on raw TWAPs or on Kalshi's own published values.
- **"A tie is Kalshi rounding to N decimals."** Not reproducible. No rounding
  precision D (1..8), on raw or on `round_digits`-rounded TWAPs, separates the
  13 ties from the 2,530 non-ties. D = 2 over-flags by 112; D = 3 misses 11.
- **"A tie is a stale constituent."** No. All five coins had 60 of 60 prints in
  both windows in every tie race.
- **"z >= 3 would have stopped it."** No, as configured: `--min-z-tau 30`
  exempts every tau inside 30 s, and both real fills were at tau 2. The arm's
  own log proves it took them at `zmin 2.3327`.
- **"The 90c price floor would have stopped it."** No. 97c and 98c.
- **"The tape under-counts ties relative to the settlement pull."** Not
  supported -- the two sources agree on all 1,522 races both cover. They differ
  only in coverage.
- **"Ties cluster in one coin."** Not supported: BTC 8, XRP 6, ETH 6, SOL 4,
  HYPE 2 across 13 ties. XRP has the coarsest settlement digit (0.63 bp) and is
  over-represented relative to its 1-in-5 share, but BTC leads the count.

## 6. Could not measure, and why

- **The exact rule Kalshi applies.** It is not in any field we record
  (`market_lifecycle_v2` gives `result`, `settlement_value`,
  `determination_ts`, and nothing about the comparison). The 6-869 minute
  determination lags say it is a manual review, so there may be no closed-form
  rule to find. A GET of the series' `rules_primary` text would settle it; I
  did not make network calls.
- **Whether a 3-way tie pays 33c.** Never observed in 2,927 races.
- **The true tie rate inside our entry population** to better than a factor of
  ~1.5. It rests on 13 ties, and the two tightest gap buckets hold 2 and 4 of
  them out of 8 and 16 races.
- **A z floor at every tau** as a tie filter. Only 10 arm-log rows carry
  `zmin` at tau <= 5, so the gap-to-z mapping inside 5 s is an indication
  (crossing between 0.094 and 0.396 bp), not a measurement. Computing zmin for
  all 2,542 races needs `pinracefair`'s covariance machinery run offline.
- **Whether ties have become rarer.** 17 in 1,874 (to 09-11) vs 14 in 2,575
  (from 08-25) is not a significant difference either way.

## 7. Solutions worth testing

The coin race has **no hedge**, so nothing here can block one -- the rule
"a gate must never block a hedge" is satisfied by construction. What each
proposal blocks is stated anyway.

1. **Score from Kalshi, never from `winner_from`.** `winner_from` is
   `max(rets.items(), ...)` -- structurally incapable of a tie. Read
   `market_lifecycle_v2` (`result`, `settlement_value`) or the settlements
   endpoint, and treat a race as unscored until it arrives. *Blocks:* nothing;
   it delays scoring by ~40 s. *Validate:* replay the 09-16 and 09-23 ties
   through the scorer -- it must book -$214.00 and -$91.61, and
   `stop_on_loss` must fire. This is the bug, not a tuning question, and it is
   what makes the first-loss halt real.
2. **A determination-clock rail.** A held race not determined within 300 s is a
   tie candidate: stop new entries, do not release its stake, do not clear the
   halt. *Blocks:* new entries for as long as one race is pending -- which on
   the tape is 10.5% of races (269 of 2,561 non-ties also ran past 300 s), so
   it costs availability, not money. *Validate:* 0 ties in 2,292 fast
   determinations; on live fills, count how many entry windows it actually
   suppresses.
3. **A race-level gap floor at the last look: refuse every leg when the
   projected top-two gap is under 0.75 bp at tau <= 5, 1.0 bp at tau <= 10,
   1.5 bp at tau <= 30.** The bot already computes and logs this number
   (`gap_bp`); the flag `--min-gap-bp` exists and is set to 0.0. *Blocks:*
   7-14% of races, all of them photo finishes -- including the leader's YES,
   which is the leg we most want. *Validate:* live fills against a bar written
   before looking. On the 49 live races it would have refused 7 worth -$1.39
   and kept 42 worth +72c. Check the flag's semantics first: `gap_bp` is a
   LEG's gap to the best other coin, so a floor read off a rank-3 leg is not
   the race gap.
4. **Give the model a tie state.** `worth` cannot exceed 1.0 today, so the most
   the fair model can ever say is "certain", and it said 0.99 on a 0.09 bp gap
   and 1.0 on a 0.0158 bp gap. Price the leader's YES as
   `P(win outright) + 0.5 * P(tie)` and a rival's NO as
   `P(not in the tied pair) + 0.5 * P(tied)`. With P(tie) = 20-25% inside
   0.1 bp, the 09-23 XRP YES is worth ~0.88, not 0.99, and 97c is a refusal on
   edge alone -- no new gate needed. *Blocks:* nothing directly; it changes a
   price. *Validate:* re-score the 13 tie races and the 141 sub-0.58 bp races
   and check the reliability table inside 1 bp.
5. **Stop holding both tied coins.** In a tie, the leader's YES and the
   runner-up's NO lose together; 86% of our legs sit on a top-2 coin, 1.49 per
   race. Inside a photo finish, at most one leg per race, and prefer a NO on a
   coin ranked 3rd or worse (those pay 100c even in a tie). *Blocks:* the
   second leg of a close race. *Validate:* our own legs by final rank --
   rank 3-5 legs were 14 of 96 and none was ever exposed to a tie.

## Sources

- `C:\kals\kalshi_data\market_lifecycle_v2\*.jsonl.gz` -- Kalshi determinations
  (`result`, `settlement_value`, `determination_ts`), 678 hour files, 23 damaged.
- `C:\kals\fulltape\lead.json` -- Kalshi REST settlement pull, 1,874 race events.
- `C:\kals\fulltape\markets.json` -- published `strike` / `settle` per 15M market,
  used to verify my TWAPs and to read `round_digits`.
- `C:\kals\kalshi_data\cfbenchmarks_value\*.jsonl.gz` -- the 1/sec index,
  677 hour files, streamed via `research/idxload._fast_fields`.
- `C:\kals-repo\results\kalshi_ledger.json` via `research/pinledger.py` -- the money.
- `C:\kals-repo\results\pinracepenny-live.jsonl` -- the real bets and the bot's
  own (wrong) scoring; `results/pinracearm-{z3,racectl,raceedge0,racetau40,20260915T221119Z}.jsonl`.
- `research/pinracearm.py` (`winner_from` line 740, `z_refusal` line 611,
  the scoring/halt block line ~2030), `research/pinracemodel.py` (the
  settlement rule), `research/pinledger.py` (`payout`, line 70).

## Verification of the already-committed fix (asked for, not redone)

`research/pinledger.py::payout()` (commit 9aa5f13) is correct. I re-derived the
expected payout independently for **all 960 ledger rows** -- `yes`, `no` and
`scalar` -- and got **0 mismatches**; the tie row returns **0.50**; the file's
own `--selftest` is green. Nothing to redo.
