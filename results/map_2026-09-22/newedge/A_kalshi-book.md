# A — The Kalshi book itself (label: kalshi-book)

**Question asked:** does the shape of the Kalshi order book in the seconds
BEFORE our entry separate our losing fills from our winning ones?

**Answer: yes, on two facts, and they are nearly independent of each other.**
Both are computable before the order is sent. One of them (`level_age_ms`)
the bot already computes and logs on every signal and gates nothing on. The
other (top-of-book size imbalance) the bot's own `livebook` already holds.

**Sources.** Every dollar is Kalshi's own ledger (`results/kalshi_ledger.json`
via `research/pinledger.pnl`), one row per settled market. Every loss count is
our own fills (`results/pinrun-live-*.jsonl`, `order` with `filled>0` joined to
the `signal` that produced it, 823 fills / 788 markets, 09-08 to 09-22). The
only tape used is the `ticker` channel, and only for *what the book was*,
never for how often we lose. Nothing here comes from pinsim or pindata.

## Population, split and power — read before any number

- n is **markets (closes)**, never fills. 788 markets with a fill.
- **TRAIN = closes on or before 2026-09-20 ET** (708 markets, 17 side-losses,
  +$499.72). **HOLDOUT = 09-21 on** (80 markets, 3 side-losses, +$49.02).
  Every rule below was searched on TRAIN and then looked at on HOLDOUT.
- The book fields only exist from **09-12** (`level_age_ms`) and **09-13/14**
  (`ladder`). The scored population is **513 markets, 11 side-losses,
  +$480.52** (438 TRAIN / 75 HOLDOUT).
- **MDE, stated before the estimates.** With ~450 TRAIN markets, a base loss
  rate of 2% and a flag covering 30% of them, 80% power at the
  multiple-looks bar needs the flagged loss rate to be **~9-10%**. **This
  population cannot PROVE a book rule. It can rank candidates and it can rule
  things out.** Treat every p below as a ranking number.
- **Looks counted: ~75.** Multiple-looks bar = 0.05/75 = **0.0007**.
- Collectors verified alive after every job (`kalshi_collector.py` 47 MB,
  `crypto_feeds.py` 39 MB). Free disk **20.4 GB**.

---

## FINDING 1 — Two pre-entry book facts split our fills into a half with every dollar and no losses, and a half with every loss and no dollars

**The rule (both must hold, both measurable before the order):**

1. **`level_age_ms >= 100`** — the price level we are about to buy has existed
   for at least a tenth of a second. The bot already logs this on every
   signal; `livebook.level_age_ms` measures it from the delta that created
   the level, and `level_age_exact=True` on every loser means we *watched it
   appear*, it is not a lower bound.
2. **`imbalance <= 0.5`** — the other side's touch is not more than 3x our
   side's touch. `imb = (opp_size - our_size)/(opp_size + our_size)` at the
   top of book, where *our* side is the one we are lifting (yes-ask when
   buying yes, yes-bid when buying no).

**Result, all 513 scored markets, Kalshi's ledger:**

| | markets | contracts | side-losses | markets that lost money | dollars | per contract |
|---|---|---|---|---|---|---|
| **CLEAN** (both hold) | 218 (42%) | 14,581 | **0** | **1** | **+$476.63** | **+3.27c** |
| **REST** | 295 (58%) | 16,962 | 11 (3.7%) | 13 | +$3.89 | +0.02c |

The two halves traded almost the same number of contracts. One earns 3.3
cents a contract; the other earns two hundredths of a cent and carries every
large loss.

Worst market in CLEAN: **-$1.10**. Worst six in REST: -$107.95, -$66.34,
-$64.95, -$61.75, -$59.09, -$57.76.

**Split out:**

- TRAIN: CLEAN 198 markets, 0 losses, +$426.06 (+$2.15/mkt); REST 240
  markets, 9 losses, +$6.77 (+$0.03/mkt).
- HOLDOUT: CLEAN 20 markets, 0 losses, +$50.56 (+$2.53/mkt); REST 55
  markets, 2 losses, -$2.88.

**Mechanism.** A level that appeared 60 ms before we hit it is an active
seller arriving, or the whole price grid re-forming because the coin just
moved; a level that has rested for seconds is a passive quote in a market
that has not moved. Our fair value is computed off an index read that is up
to `index_age_s` old, so a book that has just repriced is the market telling
us the index is about to move. The imbalance adds the other half of the
picture the bot never looks at: when the side we are lifting is a thin sliver
and the other side is a wall, we are buying the last of the supply from
someone who chose that moment to stop offering. Individually:

| cut (TRAIN) | flagged | losses | $ flagged | kept | losses | $ kept | p |
|---|---|---|---|---|---|---|---|
| `level_age < 100 ms` | 141 | 6 (4.3%) | -$97.29 | 297 | 3 (1.0%) | +$530.13 | 0.034 |
| `imb > 0.5` | 151 | 7 (4.6%) | -$44.91 | 287 | 2 (0.7%) | +$477.74 | 0.0095 |
| **both** | 52 | 4 (7.7%) | **-$148.97 (-$2.87/mkt)** | 386 | 5 (1.3%) | +$581.81 | 0.014 |

### Artefact checks — what would have to be true, and what I found

**Checked and CLEAN survived:**

- *Is it one bad day?* No. The 11 REST losses fall on **six different days**
  (09-14 x2, 09-16, 09-17 x2, 09-18 x2, 09-19 x2, 09-21 x2). CLEAN has zero
  losses on **every one of the eleven days**, and zero in **every one of the
  nine coins**.
- *A within-day permutation* (20,000 draws, shuffling outcomes inside each ET
  day so day effects cannot produce it): P(CLEAN gets 0 losses) = **0.0023**,
  P(CLEAN gets >= $476.63) = **0.0005**. The dollar version clears the
  0.0007 multiple-looks bar; the loss-count version does not.
- *Is it just which side we buy?* No. CLEAN is 107 yes / 111 no, and the
  effect holds separately in both: want=yes CLEAN 107 markets 0 losses
  +$234.82 vs REST 160 markets 6 losses +$83.87; want=no CLEAN 111 markets 0
  losses +$241.81 vs REST 135 markets 5 losses **-$79.98**.
- *Is it the model's confidence in disguise?* No. Cushion in sigma is 5.90
  for CLEAN vs 5.71 for REST; model edge 2.28c vs 2.31c; entry price 0.9763
  vs 0.9750; tau 30 s vs 29 s. This matters because the map already showed a
  3-sigma cushion floor costs $414 — this is not that filter.
- *Is it the map's "model doubted it >= 5 s earlier" population?* No. CLEAN
  markets that were never refused earlier: 103 markets, 0 losses, +$189.48.
  It is new information.
- *Is it a knife-edge threshold?* No. The plateau is wide — 0 losses in every
  cell of `age >= {100, 200, 500, 1000} ms` x `imb <= {0.2, 0.3, 0.5}`
  (194 to 218 markets). It breaks at `age >= 50` (2 losses) and at
  `imb <= 0.7` (3 losses).
- *Is our own order leaking in?* The imbalance uses only `ticker` rows whose
  **exchange** timestamp is <= (fill second minus 1.0 s), so an IOC sent
  ~90 ms before the logged second cannot appear. And a leak would push
  markets into REST, not into CLEAN. Fills in CLEAN are if anything
  **larger** (median 72 vs 68 contracts), so aggressive sweeps are not
  manufacturing the dirty half.

**Checked and it WEAKENED the claim — state these next to the number:**

- **The signal lives in the last second or two.** Recomputing the imbalance 3
  s, 6 s and 10 s before the fill instead of 1 s puts 2, 2 and 1 losses back
  into CLEAN. The book fact that matters is the one at the decision, which is
  fine for a live bot but means the effect is short-horizon and fragile.
- **The dollar advantage is concentrated in the bad days.** Excluding 09-19:
  CLEAN 179 markets 0 losses +$369.22, REST 261 markets 9 losses **+$206.72**.
  Excluding 09-18 and 09-19 as well: CLEAN 153 markets 0 losses +$328.74,
  REST 227 markets 7 losses **+$283.82**. So on calm days the rejected half
  still makes $1.25 a market. **Blocking it would have cost ~$284 on the
  calm days to avoid ~$280 on the bad ones.** The loss-COUNT separation is
  the robust part; the dollar separation is not.
- **09-19's losses are documented as gate/brake bugs blocking hedges**, so
  part of the dollar gap is a bug that is already fixed, not entry quality.
- It does not clear the multiple-looks bar on loss count (0.0023 vs 0.0007),
  and 11 losses is not many. Clopper-Pearson upper bound on 0/218 is 1.37%;
  REST is 3.73% [1.9, 6.6]. The intervals separate, barely.

**Confidence: medium-high that the ranking is real; low that any threshold is
the right one; low that blocking REST makes money rather than merely losing
less.**

---

## FINDING 2 — A fresh level predicts the already-known bad population, BEFORE entry

The map's marker "the fill came back >= 2c under the ask we saw" is
**post-fill** and can gate nothing. Reproduced on TRAIN (435 markets with
`ask_seen`): 13 markets came back >= 2c and **3 lost (23.1%), -$58.14
(-$4.47/market)**; the other 422 lost 6 (1.4%) and made +$465.94
(+$1.10/market), p = 0.0016 — the only cut in this whole study that clears
the multiple-looks bar, and the one that cannot be used as a gate.

`level_age_ms < 300` predicts that same outcome **before the order**: 188
flagged, 11 came back cheap (5.9%); 247 kept, 2 (0.8%); p = 0.0025.

And the book *before* those cheap fills is visibly different (13 vs 410
markets, medians): level age **70 ms vs 743 ms**; imbalance **+0.54 vs 0.00**;
our side's touch **13.9 vs 43.8 contracts**; the other side had thinned to
**28% vs 89%** of its size 15 s earlier; spread **2.3c vs 1.1c**. Same
picture as finding 1, from a different direction.

---

## REFUTED / NOT SUPPORTED — a clean null on data we own

Tested on TRAIN and found **nothing**. Each of these has now been looked at;
the next session should not re-tread them.

1. **Our side's ladder shape separates nothing.** Size at the touch, supply
   within 1c / 2c / 5c, number of levels within 1c and 2c, the fraction of
   nearby supply sitting at the touch, the gap to the next level. The nine
   TRAIN losers straddle the whole distribution on every one — size at the
   touch for the losers is 1, 6, 34, 39, 52, 60, 144, 482, 675 against a
   population median of 48. (393 markets, 9 losses.)
2. **`ladder_total` / `ladder_levels` are entry price in disguise.** A lower
   entry price mechanically exposes more levels and more far-away dust; the
   apparent separation vanishes inside a price band.
3. **A thin book on our side is not by itself dangerous** — `our_sz < 10`:
   3.5% loss vs 2.1%, p = 0.23. It only matters together with a heavy other
   side, which is what `imb` captures.
4. **Thin support on the other side is not dangerous** — `opp_sz` in the
   bottom quartile: 1.8% loss vs 2.7%, p = 0.84 (wrong direction).
5. **The other side thinning is not dangerous** — `opp_r30 < 0.5`: 0.8% loss
   vs 3.4%, p = 0.996 (strongly the wrong direction; a thinning other side is
   if anything a good sign).
6. **A large resting offer appearing on our side is not dangerous** —
   `our_r5 > 2`: 1.7% vs 2.9%, wrong direction.
7. **A wide spread is not dangerous** — `spread >= 3c`: 2.2% vs 2.6%,
   p = 0.70, and it *made* +$1.11/market. Tight spreads are marginally
   worse (`spread <= 0.5c`: 4.0% vs 1.8%, p = 0.087) but that is mostly the
   same markets as `imb > 0.5`.
8. **Traded volume in the last minute does not separate** — top quartile of
   `vol_60`: 2.3% vs 2.5%, p = 0.65. (Top decile is -$1.28/market but
   p = 0.23 and it is BTC in disguise.)
9. **Book churn cannot be measured from `ticker`** — that channel is
   event-driven at about one print a second per market, so "updates in the
   last 5 s" is always 5. Real churn needs the delta rebuild.
10. **`level_age_ms` alone, as a money filter, is a knife edge.** It looks
    like +$90 on TRAIN at a 100 ms cut and flips to break-even by 200 ms.
    Only in combination with `imb` does the plateau appear.

---

## COULD NOT MEASURE, AND WHY

- **Depth beyond the touch on the other side, and true book churn.** Those
  live only in `orderbook_delta`, which is 71 GB and 160 MB gz per hour;
  rebuilding it sequence-gap-aware across ~290 hours does not fit this job's
  read-only 400 MB budget. The `ticker` channel carries both touches and both
  sizes at 2.8 MB an hour, which is what finding 1 is built on. Still
  unknown: whether the SECOND level on the other side adds anything to `imb`,
  and whether a level that flickered (appeared and vanished twice in 10 s) is
  worse than one that simply appeared.
- **Whether the rule would have changed the fills themselves.** Skipping a
  market changes nothing about the others, so the ledger arithmetic is a
  valid "what these markets did" statement — but a bot that skips 58% of
  entries has more budget and more position slots, and that second-order
  effect is unmeasurable from the ledger.
- **Anything about 09-08 to 09-11.** `level_age_ms` did not exist yet.

---

## SOLUTIONS WORTH TESTING

Each says what it would BLOCK. **None of them touch the hedge path**: all
three are entry-side only, evaluated once when deciding whether to send an
order, and a position already opened must hedge under exactly the rules it
has today.

**S1 (preferred) — size by book cleanliness, block nothing.**
Full size when `level_age_ms >= 100` and `imb <= 0.5`; a third of size
otherwise. **Blocks: nothing.** It cannot stop a hedge, cannot stop an entry,
cannot interact with the budget brake. It keeps the ~$284 the calm-day REST
half earns while cutting the tail — REST's six worst markets, -$418 between
them, would have been about -$139 (that scaling is a hypothesis: it assumes
the same fills at a third the size). Validated on **live fills**: run it as a
paper arm from `sync_arms.ps1`, confirm the arm traded the same markets as
live (read `h2h`, not `diff`) and that its flag actually fired, then compare
loss counts on REST-classified markets only. Needs ~40 more REST markets
(about a week) before the loss count says anything.

**S2 — log both numbers on every signal and every refusal first, decide later.**
The bot already computes `level_age_ms`; add `imb`, `our_sz`, `opp_sz` and
`spread_c` from `livebook` to the `signal` and `refused` records. **Blocks:
nothing** — it is four dictionary fields. This is the cheapest item on the
list and it takes the tape out of the loop entirely, which matters because
the `ticker` hours are the only reason half of this analysis was possible and
the disk has about 4.8 days left at 20.4 GB and ~3 GB/day.

**S3 — hard skip on the worst cell only.**
Refuse the entry when `level_age_ms < 100` **and** `imb > 0.5` — 52 of 438
TRAIN markets (12%), 4 of 9 TRAIN losses, **-$2.87 a market**. **Blocks: 12%
of entries, and nothing else. It must be evaluated only at the entry decision
and must not be consulted anywhere in the hedge, the panic hedge, or the
early leg of a market we are already in.** This is the smallest, least
overfitted version of finding 1 and the only one whose flagged bucket is
clearly negative on its own. Pre-register the bar before looking: over the
next 150 live fills the skipped population must show a loss rate at least 3x
the kept population, or the rule comes out.

**What I would NOT do:** deploy the full CLEAN/REST block. It would have cost
~$284 on calm days to save ~$280 on bad ones, and both thresholds were chosen
after seeing all 11 losses.

---

*Working files (scratchpad, not committed):*
`...\scratchpad\newedge\kalshi-book\fills.py` (fills joined to the ledger),
`tick.py` (both-sides top of book from the `ticker` channel, 289 hour files,
35 s), `feat.py` (pre-entry features with a 1 s exchange-time cushion),
`an.py` (cuts, Fisher, TRAIN/HOLDOUT).
