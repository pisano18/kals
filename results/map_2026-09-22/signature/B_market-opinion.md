# B -- The market's opinion at entry: does it warn us?

**Finished 2026-09-23 (09-22 evening ET).** Read-only throughout. No process
touched; nothing written outside this file and my scratchpad. Collectors
verified alive after every job (see the bottom).

**Search set: the TRAIN half only** -- closes up to 2026-09-20 23:59:59 ET.
**697 markets, 509 closes, 17 losses (2.44%), +$482.88** on Kalshi's own ledger.
The holdout (09-21 on: 82 markets, 64 closes, 3 losses, +$50.73) was read once,
at the end, only to check direction. No threshold was chosen on it.

Source: the 811-row fill table built by the A investigator
(`...\scratchpad\signature\table\fills.jsonl`), which is live logs + Kalshi's
ledger + the exchange tape. **Every loss count here is a live fill and every
dollar is a Kalshi ledger row.** No replay, no pinsim, no tape loss rates.

**Looks taken: 117.** Multiple-looks bar = 0.05 / 117 = **4.3e-4**. Every rule
below is quoted against that bar, not against 0.05. The full look list is at the
bottom.

---

## The short answer to the question that was asked

*"Cheap insurance means the market agrees with us -- test whether DEAR
insurance at entry is the warning, or the reverse."*

**Neither. Dear insurance is not the warning; insurance that has just GOT dear
is.** The level of the other side's ask carries almost nothing once you condition
on whether it moved:

| the other side's ask at entry | markets | closes | losses | ledger $ |
|---|---|---|---|---|
| >= 20c **and it had just jumped >= 8c in 2 s** | 9 | 9 | **7** | **-142.56** |
| >= 20c and it had **not** jumped | 8 | 8 | **0** | **+30.88** |

Those two rows are the whole finding. Dear-and-static insurance is a wide spread
in a thin market and it has never cost us a cent. Dear-because-it-moved is the
market repricing a second before we hit it, and it holds 7 of the 17 train
losses in 9 markets.

The level table on its own is not even monotone -- the 12-20c bucket is 46
markets, **0 losses, +$139.60**, sitting between two bad buckets:

| insurance at entry | markets | closes | losses | rate | ledger $ |
|---|---|---|---|---|---|
| < 2c | 40 | 40 | 0 | 0.00% | +56.26 |
| 2-5c | 323 | 264 | 1 | 0.31% | +178.24 |
| 5-8c | 172 | 159 | 5 | 2.91% | +138.39 |
| 8-12c | 77 | 73 | 4 | 5.19% | +57.07 |
| 12-20c | 46 | 46 | **0** | 0.00% | **+139.60** |
| 20-40c | 13 | 12 | 4 | 30.77% | -89.25 |
| >= 40c | 4 | 4 | 3 | 75.00% | -22.43 |
| no tape quote (2 dead hours 09-15) | 22 | -- | 0 | 0.00% | +25.02 |

So anyone gating on "insurance costs more than 12c" (A's Finding 4 read as a
level) would block the single cleanest bucket in the table. **The move, not the
level.**

---

# RULE 1 -- the other side's ask rose >= 6c in the 2 seconds before we bought

**Blocks the entry. Does not touch a hedge.**

| | markets | closes | losses | rate | ledger $ | wins inside | losses inside |
|---|---|---|---|---|---|---|---|
| flagged | **22** | **21** | **8 of 17** | 36.4% | **-184.52** | +23.65 | -208.17 |
| the other 675 | 675 | -- | 9 | 1.33% | +667.40 | | |

**Dollars, both halves.** Not entering those 22 returns **+$208.17 of losses**
and gives up **$23.65 of winners** -- net **+$184.52** on a train book that made
+$482.88. That is 38% of everything the train half earned, in 3.2% of its
markets, over 13 days (~$14/day).

**p = 5.0e-9** (Fisher one-sided on markets), 10,000x inside the 4.3e-4 bar.
Poisson: base 2.44% predicts 0.54 losses in 22 markets; 8 observed, P = 1.1e-7.

**MDE.** Separating 36% from 2.44% at 80% power needs 9 markets; we have 22.
To confirm a *milder* version -- say 10% -- would need 126 markets, and 5% would
need 675. So this table can establish a big effect and cannot establish a small
one; that is the honest limit.

**Mechanism, technically.** The other side's ask is the market's price for us
being wrong. The model's confidence at tau 20-45 is carried mostly by the
settlement prints already locked on disk, and those do not move when the spot
does -- `fair()` re-reads the spot but the locked sum dominates `var_factor`, so
`conf` is nearly rigid over two seconds. The book is not. When the opposite ask
jumps 6c+ and our model does not flinch, the gap is not the market being slow;
it is the market having repriced on something the locked average has not yet
absorbed. We then buy a cheap offer that is cheap *because a live seller is
ahead of us*, and the pin edge's premise ("a cheap offer is a stale resting
maker") is false in exactly that second.

**Threshold sweep, all eight cells counted as looks.** The threshold is not
fitted to the losses -- every cut from 5c up catches the same 8 -- but it does
matter for the money, because the 3-6c band is profitable and must be left
alone:

| insurance rose >= | markets | closes | losses | ledger $ | wins given up |
|---|---|---|---|---|---|
| 3c | 44 | 42 | 8 | -115.49 | 92.68 |
| 5c | 27 | 26 | 8 | -166.20 | 41.97 |
| **6c** | **22** | **21** | **8** | **-184.52** | **23.65** |
| 8c | 13 | 13 | 7 | -135.01 | 11.40 |
| 15c | 10 | 10 | 7 | -151.78 | -5.36 |
| 20c | 9 | 9 | 7 | -142.56 | 3.86 |

6c is the dollar maximum. 3c is the only version that **clears the 30-close
floor** (42 closes) and it still catches all 8 losses, at the cost of $69 more
in blocked winners -- see Rule 3.

**The mirror: our own side falling is the same signal.** "Our side's ask fell
>= 5c in 2 s" = 18 markets, 17 closes, 8 losses, **-$187.24**, wins given up
$20.93, p = 7.1e-10. Twelve of the 13 markets where insurance rose >= 8c also
had our ask fall > 3c. **It is one event -- the whole book moving -- seen from
two sides.** A's Finding 1 is the same disease measured on the cheaper side; the
insurance side is the one to deploy on, because our own taking cannot create it
(taking at our ask removes the cheapest offer, pushing our ask UP and insurance
DOWN, the wrong direction for a false positive).

**This is a sharpening of A's Finding 1, not a duplicate.** A's threshold (our
ask fell > 3c) catches 26 train markets. Of those, the 14 that did *not* also
show a >= 8c insurance rise hold **1 loss between them and made +$23.81
ex-09-19**. Raising the threshold halves what is blocked and keeps the losses.

## Artefact checks on Rule 1 -- five run, one bites

1. **The 2 s window could be a quote gap, so the "move" spans longer.**
   *Partly true and it costs some of the effect.* 93.6% of all train markets
   have a from-quote no older than 2 s AND >= 3 real prints in the window; only
   18 of the 22 flagged ones do (82%). Restricted to that strict window:
   **18 markets, 18 closes, 5 of 17 losses, 27.8% vs 1.77%, -$88.78,
   p = 3.2e-5** -- still inside the 4.3e-4 bar, but three of the eight losses
   are in rows whose previous quote was 3-4 s old. **Reported as a real
   weakening, not waved away.** Quoting the conservative number: the rule is
   worth **at least +$88.78** on train, not the full $184.52.
2. **It could be "cheap price", which is already suspected.** *Refuted, and the
   split is the most useful cell in this report:*

   | price paid | insurance rose >= 3c | it did not |
   |---|---|---|
   | < 90c | n=12, **6 losses**, -$73.16 | n=26, **0 losses, +$142.70** |
   | 90-95c | n=3, 0 losses, +$5.02 | n=118, 3 losses, +$201.17 |
   | >= 95c | n=3, 1 loss, -$31.08 | n=535, 7 losses, +$238.22 |

   Cheap offers with a quiet book are **spotless in 26 markets over 26 distinct
   closes**. The danger is entirely the conjunction.
3. **A missing bid could fake a 100c insurance.** Checked: **0 of the flagged
   rows** have a zero yes-bid or a 100c yes-ask. The two 95c insurance rows had
   real quotes on both sides (0.87/0.97 and 0.052/0.056).
4. **Our own order could be moving it.** Cannot: the window ends at our decision
   millisecond, before the send, and our taking pushes insurance the other way.
5. **Is it tau, coin, or size?** No. Flagged taus 11-38 (median 26), nine
   different coins, position sizes 14-100 contracts, and it fired on 8 of the 13
   train days -- 3 on 09-10, 2 each on 09-11/09-16/09-17, 1 each on
   09-14/09-18/09-19/09-20. **It is not the 09-19 bug day**: ex-09-19 it is
   20 markets, 19 closes, **6 of the 13 remaining losses, -$65.00**, still
   negative money, p = 7.2e-7.

**Clustering, stated plainly: 21 closes, below the project's 30-close floor.**
No close is counted twice, and 9 of the 22 flagged markets share a close with an
unflagged fill we would have kept, so the rule is not secretly blocking whole
closes. But it is short of the floor, and by the hard rule that makes it a
**strong hypothesis, not a proven edge.** The 3c version (42 closes) clears it.

**Holdout, looked at once:** 3 markets, 3 closes, **1 of the 3 holdout losses**,
net **+$53.55** -- against a holdout that made +$50.73 in total. Right
direction, n far too small to confirm.

---

# RULE 2 -- the market's best bid for our side is >= 25c below the model's fair

Computed as `insurance_ask_c - 100*(1 - conf)`: what the market will pay for our
side, against what our model says our side is worth. **It needs no history at
all** -- one book read at the decision instant, which the bot already has in
hand. That makes it the cheapest of these to deploy.

| | markets | closes | losses | rate | ledger $ | wins inside |
|---|---|---|---|---|---|---|
| gap >= 25c | **9** | **8** | **6 of 17** | 66.7% | **-126.63** | +7.63 |
| the other 688 | 688 | -- | 11 | 1.60% | +609.51 | |

Net saving **+$126.63**, winners given up **$7.63** -- the best ratio in the
report (+$14 saved per market blocked). p = 6.4e-9. Ex-09-19: 8 markets,
5 of 13 losses, **-$68.87**. The graded version is monotone only at the extreme
(gap < 12c: 398 markets, 2 losses; 12-25c: 47 markets, 1 loss, +$143.93;
>= 25c: 9 markets, 6 losses).

**The same thing said in the bot's own units:** model edge (`conf` minus the
price we paid) >= 20c = 8 markets, 8 closes, 5 losses, -$69.54, p = 2.5e-7. The
bot's own "this is free money" number, past 20c, is a warning light.

**Not independent of Rule 1** -- 8 of its 9 markets are also Rule 1 markets.
Their union is 14 markets / 13 closes / 7 losses / -$131.24. Deploy one of them,
not both, and Rule 1 catches one more loss.

**8 closes -- far below the 30 floor.** Hypothesis only.

---

# RULE 3 -- the floor-clearing version: insurance rose >= 3c

Kept separate because it is the only cut in this report that satisfies the
30-close hard rule.

| | markets | closes | losses | rate | ledger $ | wins inside |
|---|---|---|---|---|---|---|
| flagged | **44** | **42** | **8 of 17** | 18.2% | **-115.49** | +92.68 |
| the other 653 | 653 | -- | 9 | 1.38% | +598.38 | |

p = 2.1e-6, inside the bar. Ex-09-19: 38 markets, 36 closes, 6 of 13 losses,
-$12.91 -- **identification survives the bug day, negative money barely does.**
Under the strict-window restriction it falls to p = 1.8e-3 and **fails the
4.3e-4 bar**, so if the gate is set at 3c it must be understood as a
loss-identifier rather than a proven dollar win.

It blocks 6.3% of entries and $92.68 of winners to return $208.17 of losses.
Rule 1 at 6c gets the same 8 losses while blocking half as much. **3c is the
version to LOG, 6c is the version to GATE.**

---

# What did NOT separate -- reported as nulls

- **The trade flow before entry is not an independent signal.** "70-100% of the
  contracts traded in the 2 s before entry were on the side AGAINST us" looks
  real at first (177 markets, 163 closes, 10 of 17 losses, 5.65% vs 1.35%,
  -$105.30) but **p = 3.1e-3 fails the 4.3e-4 bar**, and it collapses entirely
  once the quote move is removed: the 169 markets that are opp-side-heavy but
  have no >= 3c insurance rise hold **3 losses (1.78%) and made +$33.59**. All
  of its apparent power is the 8 markets it shares with Rule 1. Ex-09-19 the
  whole bucket is **positive money (+$87.99)**. **Do not gate on trade
  imbalance.**
- **Trade count / burst size: nothing.** Under 1 trade in 2 s: 28 markets,
  0 losses. 5-20: 3.49%. 20-60: 1.63%. 60-150: 1.06%. 150+: 3.45%. No shape,
  every p > 0.2.
- **The spread is not a warning.** Combined round-trip spread 6-12c: 49 markets,
  4 losses, p = 0.026, **and it still made +$18.83**. Yes bid-ask >= 6c:
  51 markets, 4 losses, p = 0.030, **+$24.12**. Both fail the bar, both are
  positive money. A thin market is not a dangerous market here.
- **Dear insurance by itself: refuted above.** 8 markets, 0 losses, +$30.88.
- **The 12-20c insurance bucket is the cleanest in the table** (46 markets,
  0 losses, +$139.60), which kills the graded reading of A's Finding 4.
- **The 22 train markets with no tape quote** (the two unreadable 09-15 hours)
  hold 0 losses and +$25.02, so the missing data is not hiding anything.

# Could not measure

- **What the market did in the 2 s after the entry we refused.** The bot logs no
  book snapshot on a refusal, so I cannot say whether a 6c gate would simply
  have bought the same market a second later at a worse price. That is A's
  proposal 4 and it is the single most important missing measurement for this
  rule.
- **The insurance price from the bot's own book read.** `hedge_quote` only
  exists from 2026-09-22 11:52:44Z, so **zero train rows** have it; all 675
  train insurance prices come from the ticker tape. A validated the tape against
  the 22 rows that carry both to a 0.00c median difference (worst 3.7c), which is
  the only reason I trust it. **The bot must start logging the opposite ask on
  every decision, fill or refusal.**
- **Whether Rule 1 helps the two biggest losses. It does not.** The nine train
  losses it misses include the largest two, -$107.95 (KXBTC 09-19 16:00,
  insurance 2.0c and *falling*) and -$66.34 (KXBTC 09-19 02:00, insurance 5.7c
  falling). Those are a different disease and this report says nothing about
  them.
- **Per-fill dollars do not exist** (one ledger row per market). One of the 22
  Rule 1 markets has two fills; the flagged leg is 82.8 of its 84.5 contracts
  (98%), so the market-level attribution is sound to about $1.70 there and exact
  everywhere else.

# Solutions worth testing, and what each one BLOCKS

1. **Log the opposite side's ask and its 2 s change on EVERY decision -- fill
   and refusal -- starting now.** Blocks nothing, changes no behaviour, costs one
   book read the bot already does. Without it every number above depends on the
   tape, and the refusal side stays invisible. This is the prerequisite for (2).
2. **Paper arm: refuse an entry when the opposite ask has risen >= 6c in the
   last 2 s.** Blocks 3.2% of entries; on train it returns $208.17 of losses and
   gives up $23.65 of winners. **Entry only -- it must never be consulted for a
   hedge, a hedge top-up, or a dump.** Validate on live fills: the arm and live
   must trade the same markets (read the head-to-head, not the diff) and the
   flag must be shown to have actually fired -- at 22 markets in 13 days it
   should fire roughly **1.7 times a day**, so a week with zero fires means the
   flag is broken, not that the market changed. Bar to write down before looking:
   >= 30 closes flagged, loss rate above 10%, and negative ledger dollars inside
   the flagged set.
3. **Cheapest variant if only one thing ships: refuse anything priced under 90c
   when the opposite ask has risen >= 3c in 2 s.** 12 train markets, 6 of 17
   losses, +$73.16, $39.00 of winners given up -- and it leaves untouched the 26
   cheap markets with a quiet book that made +$142.70 with zero losses. Blocks
   1.7% of entries. Entry only.
4. **Do NOT gate on the trade-side imbalance, the spread, or the insurance
   level.** All three look like signals and all three are positive money once
   the quote move is taken out. Writing this down so it is not re-litigated.

---

## Look list (117), for the multiple-looks bar

Bucketed tables, one look per cell: insurance level 7, model-minus-market 7,
market-vs-model insurance 7, round-trip spread 6, insurance 2 s move 7,
opposite-side volume share 6, trade count 6, yes bid-ask 5 = **51**.
Price buckets 5, seven named candidate flags 7, price x insurance-level 6,
insurance-move x ask-move partition 3 = **21**.
Eleven combined/negated candidates = **11**.
Insurance threshold sweep 8, our-ask threshold sweep 5, either-side 1,
window-strictness 2, price x flag 6, fill-improvement interaction 3 = **25**.
Strict-window and price-conditional variants = **9**.
**Total 117; bar 0.05/117 = 4.3e-4.** Robustness re-runs of an already-counted
rule (ex-09-19, holdout, whole sample) are not counted as fresh looks.

## Resource check

Free RAM 1.97 GB at start, 3.17 GB at the end; peak python under 60 MB (the
table was already built -- I read a 1.6 MB JSONL and never touched the tape).
Free disk **22.9 GB**, above the 6 GB hard collection stop but still falling
~3 GB a day. **Both collectors alive at the end of the job:
`kalshi_collector.py` pid 105304 at 54 MB, `crypto_feeds.py` pid 105352 at
51 MB.**
