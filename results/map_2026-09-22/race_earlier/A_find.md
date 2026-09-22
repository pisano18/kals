# race_earlier / A_find -- which 31-90 s coin races are as safe as inside-30 s

Status: COMPLETE (2026-09-22 ~18:10Z). Read-only. Nothing live changed, no size change,
no code deployed. Collectors alive and checked at the end (`kalshi_collector.py` pid 105304, 51 MB;
`crypto_feeds.py` pid 105352, 43 MB); free RAM 0.6-1.8 GB through the run -- my jobs
held <= 80 MB and paused themselves whenever free RAM fell under 950 MB; free disk
26.5 GB.

**Answer in one line:** yes -- at 31-60 s, races where the leader is **3+ standard
deviations clear of every other coin** lost no more often than the inside-30 s bets do
(index only, 5 of 1,703 vs 3 of 2,366; with the book and the live filters, 0 of 321 vs
4 of 493), and that floor would have blocked all three of our own losing races; past
60 s no floor tested makes it safe, because those losses are one-second jumps.

## What was measured, and from what

- **Index tape** (1/s CF prints, `cfbenchmarks_value`) = what the coins did. Winner
  recomputed from it; agrees with `race_truth.json` 657/657 and with `lead.json`
  except 3 races Kalshi settled "scalar" (a tie inside its rounding).
- **Ticker channel on the EXCHANGE's `ts_ms`** (not `_rx_ms`, per map report 08 F7)
  = what the market offered, sampled once a second at w*1000+500 ms.
- **Our own real and paper race legs** (`pinracepenny-live.jsonl`,
  `pinracearm-*.jsonl`) = the only evidence about how often WE lose.
- No replay, no pinsim. **n = races** (one race per quarter hour).
- Windows: **main 09-08..09-22, 1,310 races; holdout 08-27..09-07, 1,062 races** (a
  genuine out-of-sample split -- everything below is shown for both).
- Scratch: `...\scratchpad\race_earlier\find\` (`build.py`, `analyze*.py`,
  `rows_main.jsonl`, `rows_hold.jsonl`, `an*_*.txt`).

**The scaled lead (`zmin`).** At each second: the leader's projected lead over EACH
other coin, divided by the sd of that pair's spread change over the time left --
the pair's own trailing-hour 1-s covariance (`pinracefair.RaceSeries` + `pick_cov`
"3600", the ruler live uses), `var_factor` for the prints already locked, and
`pinracemodel.returns_at` for the locked+spot projection. `zmin` is the smallest of
the four. All of it is `pinracefair`'s own code, read-only.

**It is the live model's own number.** `1 - sum(Phi(-z))` reproduces the bot's logged
`worth` to a median 0.3c (p90 1.8c) on 164 legs, and the per-second leads match the
bot's logged `gap_bp` exactly at the bot's tau labelling. So "zmin >= 3" is the same
statement as "the model gives the leader >= 99.87%" (they agree on 99.8% of
race-seconds; same rule, 318 vs 321 races, both 0 losses).

---

## 1. Findings

### F1. At 31-60 s a 3-sd leader is as safe as an inside-30 s bet; at 61-90 s nothing is

**Index only, race level** -- first second in the band where `zmin >= T`; did that
leader lose? No price, no book, so this is the cleanest source we have.

| band | z>=2 | z>=2.5 | z>=3 | z>=3.5 | z>=4 |
|---|---|---|---|---|---|
| 2-30 s (today's live window) | 7/2369 | 5/2369 | **3/2366 (0.13%)** | 2/2364 | 1/2361 |
| 31-45 s | 8/1941 | 3/1813 | 3/1693 | 1/1593 | 0/1505 |
| 46-60 s | 10/1626 | 6/1438 | 3/1289 | 1/1138 | 1/1013 |
| **31-60 s** | 14/1955 | 6/1824 | **5/1703 (0.29%)** | **2/1597 (0.13%)** | 1/1509 |
| 61-90 s | 10/1318 | 6/1100 | 3/915 (0.33%) | 2/746 | 2/615 (0.33%) |

Both windows are far under the ~2.4% break-even at 97-98c. Split: 31-60 z>=3 is
1/927 in the main window and 4/776 in the holdout; inside 30 s it is 1/1304 and
2/1062. **The holdout period was worse for everything, not worse for 31-60 s
specifically.**

### F2. With the book and the live filters, 31-60 s already loses LESS than inside 30 s -- and the z floor makes the whole window cleaner

Entry = leader YES or second-place NO offered at 90-98c, model edge >= 0, the live
confirm-5s-or-clock-20 rule. Pooled 24.7 race-days. **Market-did numbers: how often
the leader at that second lost. NOT our loss rate.**

| rule | races | per day | lost | 95% upper bound |
|---|---|---|---|---|
| 2-30 s (what is live today) | 493 | 20.0 | 4 (0.81%) | 1.85% |
| 31-60 s, no floor | 592 | 24.0 | 1 (0.17%) | 0.80% |
| 31-60 s, zmin >= 3 | 321 | 13.0 | **0** | 0.93% |
| 61-90 s, no floor | 463 | 18.7 | 5 (1.08%) | 2.26% |
| 61-90 s, zmin >= 3 | 204 | 8.3 | 1 (0.49%) | 2.30% |
| **2-60 s, zmin >= 3 (one floor, whole window)** | **694** | **28.1** | **1 (0.14%)** | 0.68% |

So opening to 60 s *and* adding the floor gives **more races (28 vs 20 a day) with
fewer losses on the tape (1 in 694 vs 4 in 493)**.

Two caveats that matter:
- The 4 inside-30 losers were all near-ties (leads of 0.18, 1.08, 1.50, 2.09 bp) and
  3 of the 4 fired on the **clock** rule at tau <= 20, i.e. with no confirmation.
- Without the confirmation (what our paper arms actually do), 31-60 s is NOT clean:
  8 of 582 in the main window, 11 of 313 in the holdout. Every one of those losers had
  zmin 1.5-2.4, and **zmin >= 3 removes all of them** (0/385 main, 3/157 holdout).

### F3. Our own fills agree: all three losing races at 31-60 s were under 1.7 sd

The only risk evidence we have. Real + paper legs decided at 90c+ (n = races):

| | races | bad | zmin at the decision second |
|---|---|---|---|
| real, 2-30 s | 16 | 0 | median 2.85 |
| real, 31-60 s | 14 | 1 | median 2.1 (31-45) / 2.9 (46-60); the loser 1.68 |
| paper, 2-30 s | 102 | 0 | median 2.75 |
| paper, 31-60 s | 47 | 2 | losers 1.68 and 0.09 |

- `26SEP210930` (real -$0.86 and paper): HYPE led by 5.6 bp, **zmin 1.68**, model 95.3%.
- `26SEP211830` (paper, ETH NO at 98c at 60 s): a three-way tie, **race zmin 0.09**.
  The leg's own model number was 98.6% -- a leg-level confidence gate would not have
  stopped it; a race-level one does.
- `26SEP211615` (real -$0.87, decided at 86c so the 90c floor already blocks it):
  **zmin 1.50**.
- zmin >= 2 keeps 23 of 39 winning races and 0 of 2 losing; zmin >= 3 keeps 10 of 39.
  Our four real 31-60 s races with zmin >= 3 all won. **n = 3 losers: an
  illustration, not a rate.**

### F4. What kills the far-out races is a one-second jump, not drift -- which is why the floor stops working past 60 s

- The model's sd is right or a little too wide in the middle (realised/predicted sd of
  the leader-second spread change 0.85-0.98; robust version 0.52-0.69) but its tails
  are fat: moves beyond 4 predicted sd happen 0.15-0.6% of the time against 0.006%
  expected, and the excess grows with seconds left (|u|>3 is 0.9% at 30 s, 2.1% at 60 s).
- **Every loser at zmin >= 3 in 31-60 s, individually** (5 pooled; 4 of them in the
  holdout period, 1 in the main window):

  | close (ET) | leader | lead at entry | max z | what made it lose |
  |---|---|---|---|---|
  | 08-30 19:30 | HYPE | 12.6 bp at 59 s | 3.7 | one-second swing of 4.6 sd at 52 s, then a steady BTC run |
  | 09-03 16:00 | XRP | 10.5 bp at 52 s | 3.3 | one-second swing of 5.0 sd at 36 s; lead gone by 45 s |
  | 09-04 08:30 | HYPE | 5.6 bp at 34 s | 3.2 | no jump (biggest swing 2.7 sd): a steady 4.6-sd drift to SOL |
  | 09-04 16:00 | XRP | 10.8 bp at 60 s | 4.9 | one-second swing of 10.8 sd at 53 s; finished 11 bp behind |
  | 09-12 11:45 | HYPE | 4.6 bp at 44 s | 3.3 | no jump (2.4 sd): steady 3.8-sd drift to XRP |

  3 of 5 were single-second jumps of 4.6-10.8 sd. The leader was XRP or HYPE in all 5
  (and XRP or HYPE was involved in 8 of the 11 races in the 09-08..09-22 window that
  lost after ever being 2 sd clear).
- **In 4 of these 5, the market never offered that leader at 90-98c during the
  qualifying seconds** (the ask was 99c or there was no ask at all); in the fifth the
  confirmation broke. That is why the book-based table in F2 shows 0 losses -- the
  price filter and the z floor fail on different races, which is the argument for
  keeping both.

### F5. What it adds, at what price, and what it gives up

Pooled, entry at 31-60 s with zmin >= 3, on top of what the inside-30 rule already takes:

- **+10.7 new races a day** (races the inside-30 rule never sees) and **+15.4 legs a
  day** at 1 contract; the floor also drops 2.6 inside-30 races a day that the rule
  takes today, so the net is **28.1 races a day against 20.0 now**.
- Prices: median ask 98c, average 97.4c, 25th percentile 98c. Break-even loss rate at
  that price is **2.4%** (about 1 loss in 41 legs). Top-of-book size at entry: median 5
  contracts, p75 21, p90 92 -- no capacity problem at 1 contract; ~5-20 contracts if it
  ever grows.
- **Money at 1 contract: about +$0.36 a day** if the loss rate really is near zero
  (15.4 legs x 2.4c). This is a test, not a business, at this size.
- **What the floor gives up:** at 31-60 s it drops 271 of the 592 races the price rule
  alone would take (about 11 races and 13.5 legs a day, ~$0.32/day of margin at 1
  contract) -- and those 271 lost nothing on the tape. The floor is insurance bought
  against the population our own fills lose in, which the tape cannot show (F6).

### F6. The risk this cannot see: sub-second fills

Both real losses were **filled at prices the once-a-second tape never shows** (93c
seen -> 85c filled; an 86c offer that existed for 0.1 s). The tape's population is "an
offer was standing at the sample instant"; ours is "someone sold it to us". A z floor
does not stop a flicker fill -- it only decides which races we are in. What it does do
is make the flicker land on a race the index says is 3 sd clear: our one flicker fill
inside such a race (`26SEP220230`, seen 97c, filled 91c, zmin 1.74) still won.

---

## 2. Refuted or not supported

- **"The market's own price is the safety filter."** No. Requiring 97c+ at 31-60 s
  removes none of the 8 no-confirm losers -- 4 of them were offered at 97-98c while
  the bid sat at 90-95c. A 97-98c ask at those moments is a stale resting offer, not
  the market's opinion.
- **"31-60 s is inherently the dangerous band."** Not once the live filters are on: on
  the tape it loses less than inside 30 s (0.17% vs 0.81% pooled). The 09-21 evidence
  that produced v-race30 came from a regime with an 80c floor and, on the paper side,
  no confirmation.
- **"Inside 30 s is clean."** The paper arms' "0 of 88" is a small sample of a
  filtered population. On the tape, inside-30 entries lost 4 of 493 (0.81%), all
  near-ties, 3 of them clock-fired without confirmation. A floor helps there too
  (4/493 -> 1/429 at zmin >= 3).
- **"A raw basis-point lead floor is enough."** It works but has to be re-tuned by
  time -- 3 bp at 30 s, 8 bp at 45 s, 10 bp at 60 s to reach zero on a fixed grid --
  and at matched coverage it keeps fewer races than the z floor (pooled 31-60: lead >=
  8 bp keeps 233 races, zmin >= 3 keeps 321, both 0 losses). One exception worth
  keeping in mind: every inside-30 loser had a raw lead under 2.1 bp, so a 3 bp floor
  would have removed all four -- but it costs 303 of 429 inside-30 races to remove one
  ~$1 loss, so it does not pay at 1 contract.
- **"The model is simply overconfident past 30 s."** Half-true: its middle is fine
  (slightly too wide); the failure is entirely in the tail.

## 3. Could not measure

- **Our own loss rate at 31-60 s under the current rule.** 14 real races, and its one
  loss predates the confirm rule; the paper side has no confirmation, so it is not the
  same rule. Only a forward test at 1 contract produces this number.
- **Sub-second book behaviour.** The tape was sampled once a second on exchange time;
  flickers of 0.1-0.2 s (the mechanism of both real losses) are invisible to it.
- **Fill probability at 31-60 s.** The tape shows offers, not whether we would get
  them. Live fill rate on the pin bot is ~70%; unknown here.
- **A jump-aware model.** The fat tail (F4) is measured but not modelled; without it,
  61-90 s cannot be made safe by any floor tested.

## 4. Solutions worth testing (paper arm only; no live change proposed)

1. **Paper arm `arm-race-z3`: the current live penny rule with `--live-tau-max 60`
   plus a RACE-LEVEL floor `zmin >= 3` (equivalently: the model's leader confidence
   >= 99.87%).** Nothing else changes -- 1 contract, 90c floor, edge >= 0,
   confirm-5-or-clock-20, one position per race.
   - *What it blocks:* every leg -- YES or NO -- in a race whose leader is under 3 sd
     clear, including the "confident NO on a trailing coin in a three-way tie" that
     lost `26SEP211830`. It blocks nothing hedge-related: the coin race has no hedge.
   - *How to compute it:* analytically from the pairwise leads and the covariance
     `live_fair` already builds (4 numbers). **Do not read it off `win_probs`** --
     1,000 draws cannot resolve 0.1%, and 0.9987 is finer than its grid.
   - *Validation, on races (win/loss transfers from paper to real: 16 of 16):*
     **pre-registered bar, written before the arm is read** -- PASS at 125 races with
     0 losses (that bounds the true rate under the 2.4% break-even at 95%), or 250 with
     at most 1; KILL at 2 losses inside the first 50 races. At ~11-14 qualifying races
     a day that is 9-12 days.
2. **Apply the same floor inside 30 s in the same arm** (one gate for the whole 2-60 s
   window). On the tape it turns 4 losses in 493 into 1 in 429 and costs 2.6 races a
   day. Same bar as above.
3. **Log `zmin` on every race signal and refusal now**, even before any gate. It is
   one line, it makes the next version of this measurement come from our own decisions
   rather than a rebuild of the tape, and it is the number the bar in (1) is scored on.
4. **Do not extend past 60 s.** At 61-90 s the loss rate stays at 0.3-0.5% at every
   floor tested and the losers are 5-11 sd one-second jumps. If it is ever revisited,
   it needs a jump-aware model, not a bigger lead.

## 5. Power, stated honestly

- The zero-loss claims rest on: **321 tape races** (market-did) at 31-60 s with
  zmin >= 3, **1,703 index races** (5 losses), and **only 10 of our own** races.
- Break-even at 97.4c is **2.4%** -- one loss in 41 legs erases the rest.
- Many cells were looked at (5 floors x 5 bands x 2 confirm settings x 3 windows).
  With 5 losers in total, no single cell is significant on its own; the split between
  main and holdout is the only real check here, and the forward bar in (1) is the
  honest one.
