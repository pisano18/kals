# race_earlier / B_verify -- adversarial verification of A_find

Status: COMPLETE (2026-09-22 ~14:2xZ). Read-only. Nothing live touched, no size
change, no code deployed. Collectors alive and checked at the end
(`kalshi_collector.py` pid 105304, `crypto_feeds.py` pid 105352); free RAM
1.40-1.80 GB through the run (my python held ~350 MB, one process at a time,
with a 950 MB guard); free disk 26.5 GB.

My own loader, my own entry logic, my own statistics, on the finder's
`rows_all.jsonl` (index info + exchange-`ts_ms` book, 2,372 races, 08-27..09-22).
Nothing imported from `load.py` / `analyze*.py`. Scratch:
`...\scratchpad\race_earlier\verify\` (`v.py`, `v2.py`, `v3.py`, `v4.py`,
`out1..out4.txt`).

**n = races throughout. The book tables say what the MARKET did, never what WE
would lose. Our own 49 real legs are the only risk evidence and are labelled.**

---

## VERDICT: WEAKENED

The answer survives -- there is a threshold, it is the model's own scaled lead,
and opening to 60 s behind it is defensible. But **three of A_find's
load-bearing numbers are wrong or carry no information**, the money is
overstated by ~2x, and the proposed rule is not the best version of itself.
A corrected rule is in section 6; it is better than A_find's on the tape
(+$0.34/day vs +$0.22/day) and, unlike A_find's, it cannot take anything away
from what runs live today.

---

## 1. What does NOT hold

### V1. The headline evidence -- "0 of 321 at 31-60 s with zmin >= 3" -- is worth a coin flip

At 31-60 s with no floor the tape loses **1 of 593**. `zmin >= 3` keeps 321 of
those 593 and loses 0. So the floor's entire achievement on that table is
removing one loser by discarding 271 races.

- **A RANDOM discard of the same 271 races shows 0 losses 46% of the time.**
  (hypergeometric, 1 loser in 593, 321 kept).
- From the index side: at 31-60 s the z>=3 population is 1,703 races with 5
  losers; the price filter keeps 18.8% of them. If price and losing were
  independent, **P(0 of the 5 losers survives) = 35%**.

So "0 of 321" is what chance alone produces a third to a half of the time. It
is not evidence. (The floor IS informative -- see V6 -- but not from this table.)

### V2. "31-60 s already loses LESS than inside 30 s" is an artefact of a confirmation rule that is not live's

`pinracearm.arm_leg` is called by the paper scan **before** `live_refusals`, at
every tau, so a leg that has been qualifying since tau 65 fires the instant tau
reaches the `tau_max` bar. A_find's `entry()` does the opposite: `if tw +
confirm > hi: continue`, so nothing in the top 5 s of a band can ever fire, and
every entry is up to 5 s later (and safer) than live's would be.

Re-run with live's semantics (lag 0, the bot's own alignment -- see V5):

| rule | A_find's confirm | live-accurate confirm |
|---|---|---|
| 2-30 s (live today) | 4 of 494 (0.81%) | **6 of 586 (1.02%)** |
| 31-60 s, no floor | 1 of 593 (0.17%) | **9 of 752 (1.20%)** |
| 31-45 s, no floor | 1 of 329 (0.30%) | **6 of 486 (1.23%)** |
| 31-60 s, zmin >= 3 | 0 of 321 | **0 of 402** |

**Refuted:** A_find section 2's "31-60 s is not inherently the dangerous band
-- on the tape it loses less than inside 30 s (0.17% vs 0.81%)". Corrected, the
far band is *slightly worse* unfloored (1.20% vs 1.02%). The floor is what does
the work, not the band.

### V3. On the index -- the cleanest and largest source -- z>=3 at 31-60 s is 2.3x today's rate, not equal to it

5 of 1,703 (0.294%) against 3 of 2,366 (0.127%) inside 30 s. One-sided Fisher
p = 0.115, so "no worse" is not refuted -- but neither is "twice as bad", and
the 95% upper bounds are 0.62% and 0.33%. A_find's headline reached parity by
quoting **z>=3.5** for the far band (2 of 1,597) while **proposing z>=3**. Both
numbers are in its own table; the sentence picks the one that matches.

### V4. "zmin >= 3 = the model gives the leader >= 99.87%" is wrong twice

- Arithmetically: zmin >= 3 means *each* of four challengers is >= 3 sd back, so
  the model's leader probability is `1 - sum(Phi(-z))` **>= 99.46%**, not 99.87%.
- Empirically the model's tail is fiction. Exogenous grid, index only, bucketed
  by the model's own predicted loss:

  | model says | n (race-seconds) | reality | ratio |
  |---|---|---|---|
  | < 0.001% | 7,373 | 0.027% (2) | 720x |
  | 0.001-0.01% | 772 | 0.130% (1) | 32x |
  | 0.01-0.1% | 1,130 | 0.531% (6) | 13x |
  | 0.1-1% | 1,589 | 0.504% (8) | 1x |
  | 1-5% | 1,729 | 1.504% (26) | 1x |
  | > 5% | 6,301 | 18.58% (1,171) | 1x |

  At the actual 31-60 z>=3 entries the model predicts a median 0.005% chance of
  losing. **The honest planning number is the index's 0.29%, ~60x that** -- still
  8x inside the 2.4% break-even, but the gate's stated confidence is not real.

### V5. The identity "zmin is the live model's own number" reproduces less well than claimed, and the finder ran it one second late

A_find: "reproduces the bot's logged `worth` to a median 0.3c (p90 1.8c) on 164
legs". Against `pinracepenny-live.jsonl`, matching only **leader-YES** legs
(the only legs where the bot's leg-level `worth` and the race-level `1 - pz` are
the same object):

- **lag 0: median 0.56c, p75 1.58c, p90 2.61c, max 12.3c (n = 51)**; the rebuilt
  `gap_bp` matches the bot's logged one to a **median 0.000 bp**.
- lag 1: median 0.87c, p90 7.02c; gap differs by a median 0.088 bp.
- **So lag 0 is the bot's own alignment and A_find ran everything at lag 1.**
  That made its simulation one second more conservative than live, which is the
  safe direction, but every number in A_find is off the live clock by a second.
- A `zmin >= 3` gate and a "bot `worth` >= 0.9946" gate classify **3 of 51 legs
  differently**. The gate has to be built the analytic way A_find says, or it is
  a different rule from the one measured.

### V6. ...but the floor itself IS informative -- and only the corrected run shows it

Live-accurate arming, 31-60 s: no floor = 9 losers in 734 races. `zmin >= 3`
keeps 373 (51%) and **removes all 9**. P(as few, under a random discard of that
size) = **0.0016**. The steps: z>=2 P=0.006, z>=2.5 P=0.015, z>=3 P=0.0016,
z>=3.5 P=0.027, z>=4 P=0.10.

The exogenous fixed-second grid (no search, the sampling CLAUDE.md asks for)
agrees: leader loses at z>=3 -- **1/1,694 at 30 s, 1/1,268 at 45 s, 1/888 at
60 s, 2/624 at 75 s**. And it is not a coin proxy: at 31-60 s with no floor the
losses are BTC 1/127, ETH 2/106, HYPE 2/205, SOL 0/126, XRP 4/170; with the
floor every coin is 0.

**Threshold choice, honestly: 3 is where the count hits zero, which is the
definition of fitting the sample.** The incremental evidence for 3 over 2.5 is
P = 0.027 (3 of 3 remaining losers removed by dropping 30% of races); for 3.5
over 3 it is P = 1.0. **2.5, 3 and 3.5 are not distinguishable here.**

**Multiple looks.** A_find's three scripts print ~330 cells per window and were
run on three windows -- of order **1,000 cells**, over a sample containing 12-14
book-level losers. A Bonferroni bar is p < 5e-5. The best single cell I can
produce is p = 0.0016. **No cell here survives a strict multiple-looks bar**;
the nested structure makes Bonferroni conservative, but the forward test is the
only honest arbiter, and A_find says so too.

### V7. The money is overstated about 2x, and A_find's version of the rule gives some away

Tape P&L at 1 contract, legs the live bot would actually buy (leader YES at its
ask + trailer NO at 1-bid, capped at the live 2-leg limit, fee charged), lag 0,
live arming, 24.7 race-days:

| rule | races | lost | legs/day | tape $/day |
|---|---|---|---|---|
| tau <= 30, no floor (LIVE TODAY) | 586 (23.7/d) | 6 (1.02%) | 34.9 | **+0.69** |
| tau <= 60, no floor | 1,088 (44.0/d) | 12 (1.10%) | 64.8 | +1.21 |
| A_find's: 2-60 s, zmin >= 3 everywhere | 778 (31.5/d) | 3 (0.39%) | 45.8 | **+0.90** |
| corrected: zmin >= 3 above 30 s only | 853 (34.5/d) | 6 (0.70%) | 50.5 | **+1.03** |

A_find's rule is **+$0.22/day** over today, not +$0.36: it adds 11.9 races/day
worth +$0.35/day and **drops 4.1 races/day worth -$0.13/day** that the live bot
takes now. A_find reported only the first half.

Worse, the floor inside 30 s does not do what A_find says. Its claim: 4 of 493
becomes 1 of 429. Corrected: **6 of 586 becomes 3 of 485**, and the three
survivors have zmin 3.36, 3.43, 3.62 on raw leads of **4.64, 1.48 and 0.19 bp**.
That is the mechanism: inside 30 s the settlement variance has collapsed, so a
fifth of a basis point is "3.6 sd". **z is the wrong ruler at small tau**; a raw
basis-point floor is the right one there (A_find's own section 2 found every
inside-30 loser under 2.1 bp), and it costs 10 of 15 of our own inside-30 races
to remove losses we have never had.

### V8. The pooled rate hides a regime that was 4-5x riskier, and A_find's split does not show it

Index only (full coverage, so not a book artefact), first crossing:

| rule | main 09-08..09-22 | holdout 08-27..09-07 |
|---|---|---|
| index 2-30 s, z>=3 | 1/1,305 (0.077%) | 2/1,061 (0.189%) |
| index 31-60 s, z>=3 | **1/928 (0.108%)** | **4/775 (0.516%)** |

Per week at 31-60 z>=3: W34 0.38%, W35 0.68%, W36 0.24%, W37 0.00%, W38 0.00%.
On the book with live arming, the **unfloored** 31-60 rule ran at 2.50% in the
holdout -- **above the 2.42% break-even**. The recent zero is partly a benign
fortnight. A forward test starting now is being scored in the friendliest
regime in the sample.

---

## 2. What survives every attack I could make

- **Staleness does not flip it.** 24 combinations -- index lag 0/1/2/3 s x book
  age 0/1/2 s x both confirm modes -- and **31-60 s zmin >= 3 loses 0 in every
  one** (n 260-468). 2-60 z>=3 ranges 0-3 losses in 611-898 races (worst 0.38%).
  This is the test that flipped an earlier race rule by $204/day; it does not
  flip this one.
- **Leave-one-day-out.** 31-60 zmin >= 3: 0 losses with any one of the 27 days
  removed, $0.54-0.56/day. Index 31-60 z>=3: 0.18%-0.31% across LODO.
- **The rows are real.** Winner agrees with `lead.json` 1,391/1,391 where both
  exist. Independent spot check of our own pickoff fill `26SEP220230`: the bot
  saw XRP at 97c at tau 33 and filled at **91c**, and the rebuilt book shows the
  120-lot maker's ask at exactly **0.91 x 119 at tw 33**, with 0.97 x ~7 at
  tw 30-32 and 34-35. The 1-second tape reproduced a real pickoff fill to the
  cent. (That race's zmin was 1.74 -- the floor would have blocked it; it won.)
- **Our own fills agree, at n = 2 losses.** 49 real legs, 30 races. At tau 31-60:
  15 races, 2 with a losing leg, **zmin 1.09 and 1.58** at the decision second
  (A_find said 1.68 and 1.50; same conclusion, my numbers differ slightly
  because of the lag). zmin >= 2 keeps 10 of the 15 and **0 of the 2 losers**;
  our 4 real races above 30 s with zmin >= 3 all won. At tau 2-30: 15 races,
  0 losses, and a zmin >= 3 floor would keep only 5 of the 15.
- **Past 60 s stays dead.** 61-90 s with zmin >= 3 loses 2 of 234 (0.85%) under
  live arming and 1 of 204 under A_find's; the index says 0.25-0.39% at every
  floor including z>=4. Agreed: do not extend.

## 3. Would the extra early bets be filled, or picked off?

No worse than today's, on every proxy the 1 Hz tape can give -- and the spike
mechanism is **much rarer** far out:

| rule | ask falls within 2 s | within 5 s | entry ask >= 3c over its own 10 s median | median top size |
|---|---|---|---|---|
| 2-30 s (live today) | 7% | 6% | **19%** | 10 |
| 31-60 s, no floor | 6% | 7% | 5% | 7 |
| **31-60 s, zmin >= 3** | **4%** | **5%** | **5%** | **5** |

The median ask does not move at all in the 5 s after entry in any band. So "we
buy the top of a flicker" is a *near*-expiry problem, not an early one.

**What this cannot see, and it is the important part.** Both real race losses
filled at prices a 1-per-second tape never shows (93c seen -> 85c paid; an 86c
offer that lived 0.1 s). Our own 31-60 races lost **2 of 15 (13%)** where the
tape says 1.20% -- a 10x gap, the same direction and the same order as the pin
bot's 31x. The floor selects which races we are in; it does nothing about the
fill. Top-of-book depth at the new entries is thinner (median 5 contracts vs
10), which matters only above 1 contract.

## 4. Could not measure

- Our own loss rate above 30 s under any floor. 15 real races, 2 losses, neither
  with zmin above 1.6. Only a forward test produces this number.
- Sub-second book behaviour: the tape is 1 Hz on exchange time.
- Fill probability at 31-60 s. 4 of 31 real race orders were cancelled unfilled;
  that is all we know.
- Whether the benign W37-W38 regime persists.

## 5. Corrected numbers for A_find's own claims

| A_find said | corrected |
|---|---|
| 31-60 no floor: 1 of 592 (0.17%) | **9 of 752 (1.20%)** (live arming, lag 0) |
| 2-30 live: 4 of 493 (0.81%) | **6 of 586 (1.02%)** |
| 31-60 z>=3: 0 of 321 | 0 of 402 -- but a random discard gives 0 **46%** of the time |
| 2-60 z>=3: 1 of 694 | **3 of 778 (0.39%)**, all three inside 30 s |
| "+$0.36/day" | **+$0.22/day** net of what the floor drops |
| "the floor turns 4/493 into 1/429 inside 30 s" | **6/586 into 3/485, for -$0.13/day** |
| "z>=3 = model says 99.87%" | >= 99.46% by the union bound; true rate ~0.29% |
| "reproduces `worth` to 0.3c, p90 1.8c" | 0.56c / p90 2.61c on 51 leader-YES legs, at **lag 0** |
| 31-60 z>=3 "as safe as inside 30" | index 0.294% vs 0.127% (2.3x); parity needs z>=3.5 |

---

## 6. The corrected rule (paper arm only; no live change here; size untouched)

**`arm-race-z3-above30`: `--live-tau-max 60`, plus a RACE-LEVEL `zmin >= 3` that
applies ONLY above tau 30, computed analytically from the pairwise leads and
`live_fair`'s covariance, and treated as part of QUALIFYING -- so it must hold
through all five confirmation seconds, exactly like the price does.**
Everything else unchanged: 1 contract, 90c floor, edge >= 0, confirm-5-or-clock-20,
2 legs per race, first-loss halt.

Three differences from A_find's proposal, each of which I measured:

1. **The floor does not apply inside 30 s.** A_find's version drops 4.1
   races/day and $0.13/day that run live today, removes 3 of 6 losses, and
   leaves three losers at zmin 3.4-3.6 on 0.19-4.6 bp leads. Not worth it, and
   it means A_find's arm cannot be compared cleanly to live. Mine can only add.
2. **z is part of qualifying, not a fire-time check.** Checked only at the fire
   second, the early band loses 1 of 554; served through the confirmation it
   loses 0 of 366 (n = 1 -- but it is the same lesson as the 09-21 spike: a
   confidence that holds for one second is not a signal).
3. **Threshold stated as a range, not a point.** 2.5 / 3 / 3.5 are
   indistinguishable on this data (V6). 3 is the middle; if the arm is ever
   scored, score `zmin` as a continuous number, not as a pass/fail.

**On the tape, lag 0, live arming, 24.7 days:** 853 races (34.5/day) against
today's 586 (23.7/day); **6 losses, the same six, all of them inside 30 s and
0 of the 366 new races above 30 s lost**; 50.5 legs/day vs 34.9; loss rate
1.02% -> 0.70%; tape P&L +$1.03/day vs +$0.69/day. **+$0.34/day at 1 contract,
and it blocks nothing that runs today.**

**What it blocks:** only entries at tau 31-60 in races whose leader is under
3 sd clear -- every leg, YES or NO, including the "confident NO on a trailing
coin in a three-way tie" that lost `26SEP211830`. It blocks **nothing inside
30 s**, so live behaviour is a strict superset of today's. **It blocks nothing
hedge-related: the coin race has no hedge.**

**Pre-registered bar, written before the arm is read.** Score it on **races
entered above 30 s only** -- that is the thing being tested; inside-30 races are
unchanged and must not be counted as evidence for it.

- **PASS:** 125 early races with 0 losses (bounds the true rate under the 2.42%
  break-even at 95%), or 250 with at most 1.
- **KILL:** 2 losses inside the first 50 early races. (False-kill risk 2.6% if
  the truth is the index's 0.5%; it catches a 3% truth 44% of the time.)
- **ALSO KILL** on any early loss whose fill came 2c or more under the decision
  price -- that is the pickoff signature, and the floor does not address it.
- At ~11 early races/day that is **11-23 days**, not 9-12.

**And do this now, whatever else happens: log `zmin` (and the four pairwise z's)
on every race signal and every refusal.** It is one line, it costs nothing, and
without it the next version of this measurement is another rebuild of the tape
instead of a read of our own decisions.

**Power, stated honestly.** The zero above 30 s rests on 366-402 tape races
(market-did, not ours), 1,703 index races with 5 losers, and 4 of our own. The
single best statistic is P = 0.0016 against a bar of 5e-5 after ~1,000 looks.
The earlier half of the sample was 4-5x riskier than the recent half. At 1
contract the whole thing is worth about a third of a dollar a day: this is a
measurement, not a business, and its value is the number it produces in three
weeks, not the money it makes meanwhile.
