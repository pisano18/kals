# SKIM — everything that matters, short

**Read this instead of the long messages. Updated as things change.**

---

## ⭐⭐⭐ THE DISCOUNT CLIFF — answered 2026-09-11 on REAL TRADES, 48 hours, 144 closes

**The operator refused to accept "1 loss in 891" and refused to accept "we
can't measure it". He was right twice.** The order-book replay is
structurally blind to dumped offers (the 82c XRP fill we took is absent from
it entirely). **The TRADE TAPE is not** — every execution is printed with
`taker_side`, the price paid and the size. That is exactly the "someone
actively sold it to us" population, and there are millions of them.

**45,287 real fills where the taker bought a side our model called ≥ 99.5%
certain, over 144 closes (the 10-hour run's numbers are kept below it):**

| discount the taker got | trades | closes | loss rate | 95% CI | **taker P&L/contract** |
|---|---|---|---|---|---|
| 0–2c | 38,294 | 143 | 0.22% | [0.17, 0.27] | +0.38c |
| 2–5c | 4,604 | 76 | 0.26% | [0.13, 0.45] | +2.79c |
| 5–10c | 1,694 | 42 | 0.77% | [0.41, 1.31] | +6.45c |
| 10–15c | 226 | 15 | 4.87% | [2.45, 8.54] | **+7.51c** |
| 15–25c | 165 | 11 | 15.76% | [10.56, 22.23] | +0.17c |
| **25–50c** | 106 | 7 | 39.62% | [30.25, 49.59] | **−17.10c** |
| **50–100c** | 58 | 6 | 60.34% | [46.64, 72.95] | **−7.40c** |

**THE BAND WE REFUSE (≥15c): 329 trades over 13 closes, 18,648 contracts,
31.31% lost [26.33, 36.62], −6.51c/contract, −$1,213.60 total.**

**THE GUARD STANDS, and the 48-hour run moved where the true cliff is.** On
10 hours the 15–25c band looked catastrophic (−22.24c). On 144 closes it is
**+0.17c — break-even.** The real collapse begins at **25c**. So the 15c
guard costs us almost nothing and keeps a wide margin from the −17c band.
**Kept at 15c deliberately: giving up a break-even band to stay clear of a
−17c one is a good trade, and the 15–25c estimate rests on 11 closes.**

### ❌ RETRACTED: "be more patient for a 5–10c discount"

The 10-hour table tempted me into it — 5–10c pays +6.45c/contract against
+0.38c at 0–2c, sixteen times better per contract. **It is wrong, and the
per-CLOSE arithmetic kills it.** Deeper discounts are rarer, and the
frequency loss swamps the size gain:

| only take discounts ≥ | closes we'd trade | $/close at size 20 | loss rate in band |
|---|---|---|---|
| **0c (what we do)** | **143 of 144** | **$0.576** | 0.22% |
| 2c | 72 | $0.506 | 0.26% |
| 4c | 36 | $0.368 | — |
| 5c | 33 | $0.351 | 0.77% |
| 8c | 11 | $0.163 | — |
| 10c | 6 | $0.102 | 4.87% |

**Being pickier earns LESS MONEY and LOSES MORE OFTEN — both of Joe's
objectives move the wrong way.** Take everything below 15c. The idea is dead;
do not resurrect it from the per-contract column.

**LEVELS HERE ARE NOT OURS.** These are other people's fills, so the dollar
column says what the trade was worth to whoever won the race, not what we
would earn. The RANKING is the result; the level is not. Per house rule,
**no loss rate for US is ever quoted from the tape.**

**CAVEAT ADDED 2026-09-12, QUANTIFIED 14:5xZ (`results/RESULTS_tapegaps.md`):** the trade channel has recording holes -- 6.42% of all covered seconds -- but mostly OUTSIDE the trading window. In the last 30 s before a close, inside the tau band this table keeps, **3.28% of seconds fall in a silent run >= 10 s; 0.71% excluding the 97 flagged HOLE hours.** So every COUNT here is a lower bound by roughly 3%, and the RANKING of bands stands. The holes are COLLECTOR-side (654 of 705 long runs show a `seq` jump or a reset to 1, and the book goes silent with the trades while the index keeps ticking on the same socket) -- see HANDOFF for the proposed collector fix.

**METHOD NOTE THAT OUTLIVES THIS:** `pintrades.py` reads the TRADE tape and
has no book-reconstruction blind spot. For any question of the form "what
happens to someone who takes this trade", it is the right instrument and
`pindata`/`pinsim` are the wrong ones. **And any per-contract table must be
re-asked per-close before it changes a rule** — that is the mistake this
section records.

<details><summary>the 10-hour run it replaced (8,351 trades, 31 closes)</summary>

| discount | trades | closes | loss rate | taker P&L/contract |
|---|---|---|---|---|
| 0–2c | 5,962 | 31 | 0.07% | +0.33c |
| 2–5c | 1,616 | 16 | 0.37% | +2.94c |
| 5–10c | 627 | 9 | 1.44% | +5.27c |
| 10–15c | 40 | 2 | 17.50% | +3.08c |
| 15–25c | 40 | 2 | 22.50% | −22.24c |
| 25–50c | 39 | 1 | 35.90% | −27.19c |
| 50–100c | 25 | 1 | 92.00% | −43.17c |

Its caveat — "the three losing bands are 1–2 closes each, the magnitude rests
on few events" — was correct and the 48-hour run resolved it: the 15–25c
number was the one that moved.
</details>

---

## 🛑 PYTH / COMMODITIES — KILLED STRUCTURALLY 2026-09-11. DO NOT PAY $500/MONTH.

The operator was offered a 14-day Pyth trial with a **$500/month** starter
subscription behind it. **The answer is no, and the reason is not price.**

**Read the settlement rules side by side.** Both are from `/markets`:

- **Crypto (`KXBTC15M`)** — *"If the **simple average of the sixty seconds** of
  CF Benchmarks' BRTI before 7:15 PM EDT is at least the simple average of the
  sixty seconds before 7:00 PM EDT..."*
- **Commodities (`KXGOLD15M`, and identically SILVER/WTI/COPPER/NATGAS)** —
  *"If the **close price of the 1-minute candlestick** for Gold at 7:15 PM EDT
  is at least the close price of the 1-minute Pyth GOLD candlestick at 7:00 PM
  EDT..."*

**A candle close is ONE point. There is no average, so there is nothing to
lock.** Our entire edge is that with `tau` seconds left, `60-tau` of the sixty
settlement prints are already recorded and the variance of what remains
collapses far faster than `sqrt(tau)`. That mechanism is absent here.

| tau | crypto sd/sigma | Pyth sd/sigma | Pyth worse by |
|---|---|---|---|
| 30 | 1.62 | 5.48 | **3.4×** |
| 20 | 0.89 | 4.47 | **5.0×** |
| 10 | 0.33 | 3.16 | **9.7×** |
| 5 | 0.12 | 2.24 | **18.1×** |
| 3 | 0.06 | 1.73 | **27.8×** |

**To reach the same 99.5% gate the price would have to sit 11.5 sigma away at
tau 20 instead of 2.30, and 8.15 sigma at tau 10 instead of 0.84.** Those
moments effectively never occur. There is no version of `pin` that trades
these markets.

**So the trial is not worth taking either** — not because it costs money, but
because we already know what it would show, and a fortnight spent building a
Pyth collector is a fortnight not spent on the crypto and Coin Race work that
does have a mechanism. **Saved: $500/month, $6,000/year.**

### And `KXINX15M` / `KXNDQ15M` are settled too — CLAUDE.md contradiction 3

Both series EXIST with `frequency: fifteen_min` and `fee_type: quadratic`,
which is what the repo claimed. But `/markets?status=settled` returns **zero
markets for both**. They are listed and not traded, so the half-fee-at-
frequency lever the repo hoped for is unavailable in practice. **The operator's
version was right about the consequence; the repo was right about the field.**
`IDEAS.md` B3 should be struck.

**THE RULE THIS PRODUCES:** read the settlement rule text of a new series
BEFORE costing out its data feed. One `/markets` call would have answered the
Pyth question days ago, and `fee_type` — already the first thing we check —
is not the only per-series property that decides whether a strategy exists.

---

## ⭐⭐ THE COIN RACE — measured end to end 2026-09-11 (results/RESULTS_coinrace.md)

**Settlement rule SOLVED: highest (close 60s TWAP ÷ open 60s TWAP), 773 of
773 events.** The denominator is known the moment the window opens.

**We can name the leader: 97.8% at tau 30, 99.5% at tau 20**, against a 20%
base rate, stable on all nine days.

**But the market is efficient early and only slips late:**

| tau | it charges | leader is right | edge/contract | loss rate |
|---|---|---|---|---|
| 45–61 | 89.07c | 89.4% | **−0.18c** | 10.6% |
| 30–45 | 88.64c | 90.3% | +1.22c | 9.7% |
| 20–30 | 90.63c | 93.6% | +2.56c | 6.4% |
| 15–20 | 94.71c | 97.5% | +2.52c | 2.5% |
| 10–15 | 91.17c | 96.2% | **+4.72c** | 3.8% |
| 5–10 | 90.92c | 96.0% | **+4.83c** | 4.0% |

**Worth ~$5–10/day at size 20 on 6–10 opportunities. Penny test, NOT a
deployment** — the race is unproven, coverage is 6–18% of events, and the
loss-rate intervals are wide.

**NEVER QUOTE THE 99.5% AS A TRADE'S ACCURACY.** We can only buy when someone
is trading, and those are the closer races: 89.6–97.5%, not 91.5–99.6%.

**Buying only when the leader looks cheap is the discount cliff again** — per
contract it climbs to +10.11c at a 80c limit while the loss rate climbs to
**35.1%**. Cheap legs are cheap because they lose.

**Two bugs inflated the first version and both were caught here: look-ahead
(98.9% vs a true 89.4%) and tau running backwards (98.6% vs a true 93.6%).**

---

## ⭐⭐⭐ THE HEDGE — LIVE AT FULL SIZE, HOLDOUT-CONFIRMED (2026-09-12 09:5xZ)

**AMENDMENT 15 is live: when the model's belief in an open position falls
below 90%, the bot buys the opposite side for the contracts it holds, locking
the loss at (entry + hedge − 1) instead of the full entry.** Deployed 08:45Z;
a one-contract pilot cap I added by misreading the operator ran ~30 min and
was reversed at his correction (PREREG_hedge.md, dated).

**Holdout, 72 unseen hours (09-06T22 → 09-10T04), 162 positions, 4 lost:**

| threshold | false alarms | losers caught | recovered ¢/contract | P&L unhedged → hedged |
|---|---|---|---|---|
| 0.70 | 0 | 4 of 4 | 43.2 | $31.52 → $64.84 |
| 0.80 | 0 | 4 of 4 | 55.5 | $31.52 → $74.60 |
| **0.90 (live)** | 1 ($0.77) | **4 of 4** | **68.2** | **$31.52 → $76.40** |

Alarm fired on the losers with 19, 16, 13, 13 seconds left. **Ceiling
numbers** — delta-only replayed book, and the replay always wins the race.
The live bar (`results/PREREG_hedge.md`, n=30 hedge events) is the test that
counts. **A planted one-contract test is armed (`--hedge-plant`)**: at the
first decided market it buys ONE contract of the side about to lose and lets
the live hedge path fire on it, for a few cents — the operator's own design
for proving the mechanics.

**PLANT #1 FIRED 09:44:35Z and found a bug for a third of a cent.** It bought
1 YES @ 0.3c on a fully decided ETH market; the alarm fired instantly; there
was no NO ask (dead-side book empty = the winner has no ask -- real
structure); and the hedge **burned all five retries in ~250 ms** because the
loop runs 20x/second while HEDGE_MAX_TRIES was documented as seconds. Fixed:
one try per wall-clock second, self-tested. Settled -0.33c. Plant now targets
NEARLY decided markets (winner 90-99%) so the hedge can actually FILL; plant
#2 armed on pid 858644. Details and exit-criteria status in PREREG_hedge.md.

**PLANT #2 FIRED 09:59:35Z -- THE FULL LIVE HEDGE PATH IS PROVEN.** Bought 1 NO
@ 5.2c on a 96.5%-YES SOL market; alarm at belief 2%; hedge bought 1 YES @
94.9c, executed; both legs settled (-5.55c, +4.76c); **pair net -0.79c =
the +0.1c lock minus 0.69c fees, to the cent.** All three exit criteria met.
Planting stops (two plants, 1.12c total); the n=30 live bar now counts REAL
collapses only, because the one thing a plant cannot test is whether a real
collapse leaves an ask we can reach. Trader in production on pid 854512.

**Correction to an item below:** "SNAPSHOT BUG, OPEN" is STALE. `pindata.Book
.snapshot()` was fixed 2026-09-10 (reads `yes_dollars_fp`), and on 2026-09-12
the tape's snapshots were verified to carry levels for every market that has
a book (56 of ~160 per hour; the rest are genuinely empty books). It is not
the live/backtest divergence.

**The divergence that IS structural, now being measured on our own fills
(`research/pinreplay.py`, in progress):** the replay evaluates once per
second with the book as of that boundary; the live bot samples ~20×/second.
An offer that appears at :15.400 and is eaten at :15.600 is a real fill for
us and invisible to the replay. **Honest counter-note:** the 72h holdout above
showed a 2.47% loss rate, close to the filtered live ~2.0% — the replay is
not uniformly blind to losses; the 48h window ending 09-12 05:00Z (0.67%) was
unusually calm.

---

## ❌ "IS SOL STRUCTURALLY WORSE?" — NOT PROVEN, AND TWO OF MY OWN COUNTS WERE WRONG (Opus agent, 2026-09-12; `results/RESULTS_coin.md`, `results/PREREG_coin.md`)

**Two corrections to what I reported earlier today, and both are mine:**
1. **"NEAR 3 of 18" was wrong.** The three NEAR losses are three fills on ONE market in
   ONE close (09-09 00:45). Hard rule 4 says cluster by close. NEAR is **1 of 18** by
   close. My per-bet table broke my own rule.
2. **"SOL's feed is the least jumpy" was a QUANTIZATION ARTEFACT.** SOL is quoted in 0.01
   steps against a 0.0082 one-second sigma, so 70% of SOL seconds print NO change and the
   jump-tail statistic sees a calm grid, not a calm coin. Withdrawn.

**What is actually true:** at the current gate SOL has lost **3 of 14 closes** vs **1 of
101** for the other eight. Alone p = 0.0055; **as the worst of nine coins we went looking
through, p = 0.060**; over all runs p = 0.333. Only a coin 4–6× worse was detectable on 14
closes. SOL is −$38.39 at the current gate while the other eight made +$67 — but that is
three events, and on the all-runs window NEAR is worst on money from its one triple-filled
close. **Which coin is "worst" flips with the window.** The worst-of-nine p went 0.060 →
0.0285 → 0.060 in one afternoon as two half-penny hedge-test plants entered and left the
loss count.

**Mechanism confirmed, gate impossible:** every reconstructable losing close carried a
one-second index jump past 5σ (p = 0.0004 vs Poisson), but **22–37% of ALL closes do and
we win nearly all of them.**

**Adverse selection in its own units:** our entries are ~12% "saturated" (belief at the
numerical ceiling) vs 73–85% on the tape's model-certain moments — we get the
less-certain end of the gate because that is where offers exist.

**No SOL gate. Instead `results/PREREG_coin.md`: the next 30 SOL closes at the current
gate, ≥3 losses excludes SOL, ≤1 closes the question, written before the data.**

**Standing correction to the ledger:** count losses BY CLOSE and exclude `plant-`/`hedge-`
legs. By close: 195 closes, SOL 3, XRP 1, BNB 1, DOGE 1, NEAR 1, BTC/HYPE/ETH/ZEC 0.

---

## ⭐⭐⭐⭐ THE BACKTEST IS REBUILT AND REPRODUCES 7 OF 7 OF OUR LOSSES (2026-09-12 18:4xZ; `research/pinsim.py` commit 8ec2ae7, `results/RESULTS_replay_rebuild.md`)

The operator's demand: "Don't stop until you can backtest our last trade and get
the same results. I want to see more losses because we actually have losses."

**Built:** a seq-ordered event stream merging snapshots and deltas in the exchange's
own order with real `_rx_ms` snapshot times (the old loader stamped every snapshot 0);
a decision after EVERY book event on a tracked market (3.06M decision moments over 72
hours, was ~1,000/hour); the index fed to the event's millisecond; `--gate-from` to
replay under the gate a live run actually used. Streamed, 80 MB resident.

**Acceptance on our own 210 real fills (all 9 losses):**

| pinsim's own book + evaluation | before | **after** |
|---|---|---|
| exact live-logged price | 33% | **75%** |
| bought our fill, gate that was live | 143/210 | **180/210 (86%)** |
| of the 9 losses, live gate | 1/9 | **9/9** |
| of the 9 losses, today's gate | 1/9 | 6/9 |

The old replay reproduced our WINS five times better than our LOSSES (55% vs 11%);
the rebuilt one reproduces both at 66%. **Mechanism:** the offers that hurt us live a
median 1.4 s; a once-a-second sampler preferentially missed the adversely-selected
fills — the losing ones. The 201 winners move identically (control).

**The literal test, run per loss-hour with `--gate-from`:** 6 of 7 printed our own
loss as a `LOSS` line before the settlement refresh; after `pinsettle` (+477 markets,
through 18:00Z) the seventh does too: `LOSS KXSOL15M-26SEP120400-00 yes 93.8c tau 19
$-18.84` against our real YES @ 94.0c tau 19 −$18.88. **Seven of seven.**

**And the faithful replay is WORSE — which is the point.** Same 72 unseen hours:

| | old replay | rebuilt |
|---|---|---|
| fills / losses | 162 / 4 (2.47%) | 195 / 6 (3.08%) |
| P&L ceiling | $+31.52 | **$+10.45** |
| at the 70% live fill rate | $+22.06 | **$+7.31** |
| last-30% slice | $+14.90 | **$−0.55** |

It now agrees with the $2–9/day the live bot actually makes. **No $/day projection
from the old replay may be quoted again.**

**Hedge threshold re-read on the faithful replay:** 0.80 nets +$35.69 (false alarms
1.54%) vs 0.90 +$25.54 (3.08%, exactly the bar). **HEDGE_BELIEF 0.90 → 0.80, dated in
PREREG_hedge.md; trader restarted on it (pid 962352).** The two real live alarms (both
false, at 0.887 and 0.664) point the same way but are not the reason.

**Left in, named:** a collector reconnect resets `seq` and the merge does not segment
on it (8 in 72 h, counted; one-line fix deferred); `MAX_PER_CLOSE` not enforced in the
replay (one close took 5 correlated markets, −$95 in a quarter hour); index fed by
stamp not arrival (8 of 207 fills); `pinreplay`'s `PINSIM_BOOK_DIFFERS...` flag now
measures the OLD pinsim.

---

## ⭐⭐⭐ WHY THE BACKTEST NEVER SHOWED OUR LOSSES — ANSWERED ON OUR OWN 207 FILLS (2026-09-12; `results/RESULTS_replay.md`, `research/pinreplay.py`)

**207 real fills, 160 closes, all 9 losses, replayed at the exact second.** Fair
reproduces (180/207 to 1e-4 by arrival; the 4 misses are sigma from the bot's separate
index socket). Settlement: **0 disagreements in 196.** Our fill reconciles to a swept
ladder on the trade tape 198/207. **The offer we hit was in the rebuilt book at SOME
millisecond for 207/207 — never invisible.**

**Would `pinsim.decide` (called, not reimplemented) have bought our own fills?**

| book read at | gate | bought |
|---|---|---|
| second boundary (what `pinsim.run()` does) | today's | **112/207** — and **1 of 9 losses** |
| decision millisecond | today's | 137/207 |
| second boundary | the one that was LIVE | 147/207 |
| **decision millisecond** | **the one that was LIVE** | **178/207 (86%)** |

**Three causes, ranked by count:**
1. **The gate changed** — PIN 0.98 → 0.995 refuses 42 of our own fills as `undecided`
   (3 of 9 losses), and dump guards that did not exist then refuse 9 more (4 of 9 losses).
   51 of 97 refusals. **A rule change, not a replay defect** — but a backtest of our history
   must run under the gate that was live, or it cannot show our losses by construction.
2. **Once-a-second sampling of a book that changes ~99 times a second.** Reading at the
   decision millisecond lifts exact-price agreement from 78/207 to **156/207** and buys 20
   more of our fills. Offers we hit lived a median 1.4 s; 32 existed only inside a second.
3. **Book merge order.** Snapshots carry no exchange timestamp; merging on the clock puts a
   snapshot AFTER a delta it already contains → phantom levels, **31c median error**. Merged
   on `seq`: 0.00c median error. `pinsim` also stamps snapshots at 0 (reads `ts_ms`, absent;
   the field is `_rx_ms`).

**All three are in the rebuild spec now running (Opus agent); acceptance = this harness.**

**NEW CAVEAT THAT REACHES BACK: the `trade` channel has holes.** One hour had 374 silent
seconds of 3,523 (10.6%) in runs of 230, 72 and 53 s, across ALL markets, while the book
channel was fine. **Any COUNT or RATE from the trade tape is a lower bound — `pintrades.py`
and the discount-cliff table above included. RANKINGS stand; counts do not.**

**Reading the live log, addendum:** `settled` records now include the plant legs and hedge
legs (tickers holding both sides). A lifetime tally must net them per ticker or exclude
`plant-`/`hedge-` order ids. Agent's raw count: 189 settled, 178 W +$145.08, 11 L −$139.63,
net +$5.45 — of which 2 "losses" are plant legs; 9 real.

---

## ❌ "KNOW WHEN NOT TO BUY" FROM THE ORDER BOOK OR THE INDEX — CLOSED (Opus agent, 2026-09-12; `results/RESULTS_entry.md`)

216 book hours, two populations in one pass: **A = 409 entries the live gate would have
taken (274 closes, 3 losses, 16 belief-collapses)** and **B = 7,328 model-certain moments
(801 closes)**. Features at the entry second: offer age, offer freshness, offer size
(absolute and vs that market's own median touch), pre-entry >3σ jump count, largest
jump, tau, price, discount, margin-to-strike in sd. Split 5 days / 4 days; nothing is a
survivor unless it holds in BOTH halves; 92 looks, Bonferroni applied.

**Nothing in the book or the index tells you not to buy.** Offer age/freshness/size and
pre-entry jumpiness are null in both halves, and the signs on size and jumpiness mostly
run AGAINST "a fresh, large offer is a dump by someone who knows."

**The one thing that separates — margin to the strike in sd — is nearly a tautology and
the control proves the method would certify nonsense.** `margin_sd = Φ⁻¹(belief)`, and a
collapse is that same belief later falling under 0.90; an entry at the gate floor starts
1.29 sd from its own alarm, one at 6 sd starts 4.72 sd away. `price`, included purely as a
control, survives the identical test. And **every margin gate is ruinous per close**:
refuse `margin_sd < 3` → −33%/close; `< 5` → −53%; the price control → −94%. 13 of the 16
collapses on A went on to WIN, so most of what a gate buys is a scare avoided, not a loss.
**No gate proposed; both candidates written out and rejected on cost.**

**Positive control passed:** inside the margin stratum, a discount ≥ 10c collapsed 6 of 24
(25%) vs 10 of 272 (3.7%) — the discount cliff, rediscovered from a different outcome on a
different population, already guarded live at 15c. Not grounds to tighten (−38%/close).

**Practical read:** a new entry refusal would just be a tightening of PIN priced at 33–53%
of the income, decided by drawdown tolerance rather than by a feature. **Everything rides
on the exit (the hedge) and on COUNT (offers exist on 9.6% of confident markets).**

**Replay bug confirmed independently:** `pinsim.load_hour` reads `d["ts_ms"]` on
snapshots, absent on 100% of them; the real field is `_rx_ms`, and snapshots arrive
throughout the hour, not at the top. In the pinsim rebuild spec.

---

## ❌ "BUY BETTER BY RESTING A BID" — TESTED AND KILLED (Opus agent, 2026-09-12; `results/RESULTS_maker.md`)

9 days, 793 closes, trade tape. Resting a bid (zero fee) instead of taking:
**per close it loses in 113 of 114 comparison rows.** TAKE $0.824/close vs
REST-1 (5s) $0.465, t = −5.8, holdout t = −3.65. **The mechanism is near-total
adverse selection: a resting bid was filled on 100% of the eventual losers
(17 of 17) and 29% of the winners.** Nobody sells you a near-certain contract
for no reason. Cancel-on-alarm does not help — the loser fill lands a median
5 s before our belief drops. The fee it saves is 2–5× smaller than the cost.
**Per contract it pointed the wrong way for the THIRD time.**

**The lead it turned up instead — COUNT, not price:** an acceptable offer
appeared on only **694 of 7,266 markets we were confident about (9.6%)** and
on **411 of 793 closes (51.8%)**. Half the closes we are sure about, we never
trade because nobody is offering. That is a larger number than any price
tweak and is now on the hunt list.

---

## 🛑 COIN RACE — DEAD 2026-09-12 05:00Z. Watched the book empty in real time.

The penny test ran live for 70 minutes: **5 races judged, 0 orders sent, $0
spent.** Every race refused for the same reason -- `no_yes_ask`, nobody
offering the winning leg. Then I sat on a race and sampled the leader's ask
every second:

| seconds to close | ETH (the leader) ask | the four losers |
|---|---|---|
| 90 | 89c | 1-22c |
| 40 | **98c** | 1-10c |
| 20 | 98c | 1-5c |
| **19 -> 3** | **GONE** | 1-5c |

**The market knows the leader 40 seconds out and charges 98c -- above the
break-even for tau-40 accuracy. At 19 seconds every offer on the winner is
pulled.** Our measured band was tau 15-20. There is nothing there.

The tape said takers paid ~87c in that window (+12.1c/contract). Those prints
were real but they are the rare seconds when a straggler offer existed, and
live, right now, it does not. Same mechanism as the up/down markets: **in a
decided market the losing side's book is empty** (33,427 of 33,431 moments).

**Also found and fixed along the way, all mine:** look-ahead in the price
stage, tau running backwards, `watch()` vs `subscribe()`, a staleness gate
that refused quiet books, a liveness gate that re-created it, and the REST
orderbook keys (`orderbook_fp.no_dollars`, not `orderbook.no`). None visible
in the output; every one found by asking why a number was that good or that
empty.

---

## ⭐⭐⭐ THE $19 LOSS, DISSECTED — the model knew, and the bot held (2026-09-12)

Second-by-second replay of the three "ordinary" losses that no filter
catches, using the model's own fair value:

| loss | entered | 2-6s later | 14s left | outcome |
|---|---|---|---|---|
| NEAR, NO @ 96.2c | 98.2% | **40.7%** (tau 16) | **1.0%** | -$19.29 |
| BNB, YES @ 94.0c | 98.5% | **46.3%** (tau 24) | 44.9% | -$17.60 |
| SOL, NO @ 97.9c | 99.9% | 100% | **0.2%** (tau 11, ONE second) | -$19.61 |

**Two of three collapsed within seconds of entry with 14+ seconds left,
while the bot held to zero.** SOL was a 0.14% one-second jump -- the genuine
tail, uncatchable.

**THE TAPE TEST, 48 hours, 1,653 markets entered at our gate:**

| lowest belief after entry | winners (1,642) | losers (11) |
|---|---|---|
| never below 99% | **1,630** | 0 |
| 90-99% | 8 | 0 |
| 20-90% | 4 | 0 |
| **below 20%** | 0 | **11** |

**A stop at belief < 70% fires on 2 of 1,642 winners (0.12%) and catches
11 of 11 losers.** The separation is essentially complete. Alarm timing on the
losers: tau 29, 29, 28, 27, 25, 24, 23, 19, 11, 10, 10 -- eight of eleven with
19+ seconds to act.

**TWO WAYS TO USE IT, being measured now:**
1. **Exit when belief turns** -- needs a bid to sell into; the losing side's
   book thins fast, so the achievable price is the whole question.
2. **Refuse to enter on a spike** -- require belief >= 99.5% for N consecutive
   seconds. Needs no exit liquidity. Would not have saved SOL.

**ENTRY STABILITY — TESTED, WEAK (2026-09-12).** Requiring belief ≥ 99.5% for
N consecutive seconds before buying, on 1,656 tape markets:

| N seconds | entered | lost | loss rate |
|---|---|---|---|
| 1 (now) | 1,655 | 11 | 0.66% |
| 3 | 1,651 | 10 | 0.61% |
| 5 | 1,643 | 10 | 0.61% |
| 8 | 1,638 | 9 | 0.55% |

Removes 2 of 11 losers for 1% of entries. **The losers were mostly NOT spike
entries** — belief was stable at 99.5%+ and collapsed later (SOL: 19 seconds
stable, then 100% → 0.2% in one second). So the entry side is not where the
lever is. **Everything rides on the exit.**

**THE EXIT — IS THERE ANYONE TO SELL TO? YES, ABOUT HALF THE TIME IT MATTERS (2026-09-12).**
For each of the 11 tape losers, the prices that actually TRADED on our side in
the alarm second (belief first < 70%). Typical print, not best print:

| market | alarm at tau | typical print on our side | loss/contract vs 96c held |
|---|---|---|---|
| NEAR 0830 | 23 | 99c | **~0c** |
| BNB 0830 | 29 | 70c | 26c |
| HYPE 0830 | 27 | 63c | 33c |
| XRP 0100 | 19 | 66c | 30c |
| BTC 2300 | 10 | 65c | 31c |
| SOL 0830 | 29 | 60c | 36c |
| ETH 2215 | 24 | 58c | 38c |
| DOGE 0830 | 25 | 27c | 69c |
| SOL 2300 | 11 | 19c | 77c |
| XRP 0830 | 28 | 9c | 87c |
| DOGE 1815 | 10 | 3c | 93c |

**Mean recoverable ~49c of the 96c. The average loss halves, from ~$19 to
~$9.50 at 20 contracts.** Seven of eleven recover a third or more; four are
one-second collapses where the price is gone before the alarm.

Prints carry real size (x200, x294, x3964), so selling into them is realistic
-- but we would be selling INTO a collapse alongside everyone else, so the
achieved price will sit at or below these. Treat 49c as the ceiling.

**False alarms:** 2 of 1,642 tape winners dipped below 70%. Exiting those at
~50c costs ~$9 each = 0.12% x $9 x 39 bets/day = **~$0.42/day**. The gain
is roughly (96c-49c) x 20 x 2.0% loss rate x 39/day = **~$7/day.** Net ~+$6.5
a day at size 20 on a strategy making ~$9. **Roughly a 70% improvement,
before the achieved-price haircut.**

**HOW IT WOULD BE BUILT -- with machinery already proven live:** buy the
OPPOSITE side via the same `pintake.take()` path, at the best ask, for the
size we hold. Holding 20 NO at 96c and 20 YES at 35c locks in exactly
-31c/contract whatever settles. Settlement is per ORDER (`open_pos`), so the
two legs pay independently and correctly. The A8 both-sides guard sits in
the SIGNAL path and does not see the hedge. **No new order type, no sell
path, no change to pintake.**

**GATES BEFORE IT GOES LIVE (AMENDMENT 2026-09-10 applies):** a pinsim holdout
on days not used above, and a pre-registered live bar written before the first
live hedge fires.

**FOURTH DISSECTED LOSS, out of sample (SOL, YES @ 94c, 2026-09-12 08:00):**
belief 99.8% at entry (tau 19) -> 83.7% at tau 16 -> **0.05% at tau 15**. A
70% alarm fires at tau 15 with the price already gone. A **90% alarm fires at
tau 16 with belief still 84%**, while the market is still worth selling into.
**So the threshold is a real parameter, and the holdout sweeps it.** Live bar
pre-registered in `results/PREREG_hedge.md` before the code exists.

**Tape caveat, standing:** this is the model's fair PATH, driven by the index,
not by the book -- so unlike a loss RATE it should transfer to our fills. Both
live losses that had warning showed exactly this shape.

---

## ❌ "STOP PAYING ABOVE 94c" — TESTED AND KILLED 2026-09-12

**Our own 150 bets said every dollar of profit came from under 94c and that
94-98c earned nothing across 103 bets. That was NOISE, and independent data
says the opposite.**

Tested on the TRADE TAPE -- 33,732 fills over 104 closes by takers who have
never heard of us, at our own gate with our own 15c guard applied:

| price paid | fills | closes | loss rate | break-even | P&L/contract |
|---|---|---|---|---|---|
| under 90c | 167 | 10 | 4.19% | 11.92% | **+9.54c** |
| 90–94c | 827 | 26 | 1.09% | 7.97% | +7.16c |
| 94–96c | 1,319 | 31 | 0.00% | 4.96% | +4.63c |
| 96–97c | 1,144 | 36 | 0.00% | 3.53% | +3.29c |
| 97–98c | 1,987 | 59 | 0.60% | 2.55% | +1.93c |
| 98–100c | 28,288 | 104 | 0.29% | 0.44% | +0.34c |

Per contract, cheaper is monotonically better. **Per CLOSE it is the reverse,
because cheap fills are rare:**

| refuse to pay above | closes traded | $/close at size 20 |
|---|---|---|
| **100c** | 104 (100%) | **$0.566** |
| 99c | 77 (74%) | $0.550 |
| **98c (what we run)** | **67 (64%)** | **$0.528** |
| 97c | 47 (45%) | $0.444 |
| 96c | 36 (35%) | $0.376 |
| 94c | 27 (26%) | $0.295 |
| 90c | 11 (11%) | $0.071 |

**A 94c ceiling earns $0.295 per close against $0.566. It halves the income.**

**THE CURRENT 98c CEILING IS WELL PLACED**: it keeps 93% of the money while
trading 64% of the closes. Tightening to 97c costs 21% of the money for
2 percentage points of loss-rate protection. Leave it alone.

**THE LESSON, AND IT IS THE SECOND TIME:** a per-contract table must be
re-asked per close before it changes a rule. "Be more patient for a bigger
discount" died here on 2026-09-11 and "stop paying above 94c" died here on
2026-09-12, for the identical reason -- rarity is invisible in a per-contract
column and is usually the larger term.

**AND A SECOND LESSON: 150 of our own bets cannot settle a question that
33,732 independent fills can.** The 94-98c band looked worthless on our data
(103 bets, -$8) and carries most of the available money on the tape. Small
samples manufacture confident nonsense.

---

## ⚠️⚠️ ON 72 UNSEEN HOURS THE BASE STRATEGY IS NEGATIVE, AND THE HEDGE IS CARRYING IT (2026-09-12 22:xxZ; `results/pinsim_hedge_holdout_railed.log`)

The same 72 unseen hours (09-06T22 → 09-10T04), re-run on the replay with pinrun's
per-close rails enforced — the run that decides the hedge threshold:

| | before the rails | **with the rails (correct)** |
|---|---|---|
| fills / closes | 195 / 117 | **156 / 117** |
| losses | 6 (3.08%) | **6 (3.85%)** |
| mean price paid | 96.29c | 96.14c |
| **unhedged P&L, ceiling** | **+$10.45** | **−$11.01** |
| fit (first 70% of closes) | +$14.90 | **−$3.67** |
| **holdout (last 30%)** | −$0.55 | **−$7.35** |

**The rails removed 39 fills and $21.46 of profit, and both halves are now negative.**
That is the correct direction and the correct reason: those extra fills were real in
the replay and impossible live, because MAX_PER_CLOSE is 2. A backtest that takes
five markets into one correlated close will always look better than a bot that takes
two.

**At 96.14c the break-even loss rate is 3.86%. The window realised 3.85%.** The base
strategy sat exactly on its own break-even line for three days — which is the "1.4×
headroom" finding arriving from a completely different instrument.

### The hedge is what makes the window positive

| threshold | alarms | false | fa cost | losers caught | recovered c/contract | net ΔP&L | **hedged P&L** |
|---|---|---|---|---|---|---|---|
| 0.70 | 8 | 2 | $19.66 | **6 of 6** | 41.7 | +$28.48 | $17.46 |
| **0.80 (LIVE)** | 9 | 3 | $22.21 | **6 of 6** | **49.8** | **+$35.69** | **$24.68** |
| 0.90 | 12 | 6 | $34.93 | 6 of 6 | 58.3 | +$25.54 | $14.53 |

**0.80 is confirmed best on the corrected tool** — the threshold deployed at 18:2xZ
survives the fix that invalidated the run it was chosen from. 0.90's false-alarm rate
is **3.85% [1.42, 8.18]**, outside the pre-registered 3% bar; 0.80's is 1.92%, inside.
All three catch 6 of 6 losers, so the choice is entirely about what the false alarms
cost and what the exit recovers.

**Read this as ONE window of 117 closes, not as the expectation.** It is a ceiling
(the replay wins every race), the interval on 6 losses is wide, and the full-history
sweep over 422 hours supersedes it. What it establishes is narrower and firmer:
**the hedge is not a refinement, it is load-bearing**, and the unhedged strategy at
this gate is close enough to break-even that a normal three-day window can sit on the
wrong side of it.

**New tape property recorded by the same run:** 12.7% of deltas carry a `ts_ms`
already seen in `seq` order (595,337 of 4,692,864 on 20260909T00) — the TAPE's own
clock inversions, not the merge's. The simulated clock is held, never rewound.

---

## ⭐⭐⭐ COUNT IS A LIQUIDITY PROBLEM, NOT A SETTINGS PROBLEM — 88% OUT OF REACH (Opus agent, 2026-09-12; `results/RESULTS_count.md`, `research/pincount.py`)

180 book hours / 9 days / 697 closes on the REBUILT replay under the live gate. The
instrument independently reproduces the number that prompted the hunt — **52.2% of
model-certain closes traded** vs `RESULTS_maker.md`'s 51.8% — from the BOOK channel,
not the trade tape.

**The mechanism, from 167,458 fresh certain market-seconds:** **140,990 (84.2%) carry
NO ask on the winning side — and 140,989 of those 140,990 carry one on the LOSING
side.** The book is not dead; it is one-sided against us. Buying a near-certainty
requires somebody to bid the side about to lose, and when the outcome is obvious
nobody does. Of the 26,468 market-seconds that DO have an ask, 18,006 are above 99.5c
and only 3,141 are at or below 98c. **That is a capacity limit of the product. No
parameter touches it.**

**The 333 silent closes, by the closest rung they reached:**

| best offer the close ever showed | closes | reachable by |
|---|---|---|
| dearer than 98.7c only | **219 (65.8%)** | the EV floor, not the ceiling |
| no ask our side, loser had one | 71 (21.3%) | **nothing — liquidity** |
| 98.0–98.7c and deep | 35 (10.5%) | PRICE_CEILING → 0.987 |
| everything else | 8 (2.4%) | size / rails / edge |

**Only 39 of 333 (11.7%) lie inside the reach of any price or size constant.**

### The one lever, and it is NOT established

`PRICE_CEILING` 0.980 → **0.987**: +5 points of count (52.1% → 57.1%), **+$1.90/day at
size 20**, inside its own MDE (+$0.0245 vs $0.0575), and the two dollar columns
disagree in sign. **0.99 and 0.995 are byte-identical to 0.987** — pinrun's own EV
floor refuses everything dearer (EV(0.987) = +0.31c clears 0.30c; EV(0.988) = +0.21c
does not), hand-reconciled at six prices. **A ceiling above 0.987 is inert.**

**The artefact check that decides it:** all 123 added fills are dearer than 98c, and
the gain flips sign on the one number the tape may not supply —

| loss rate on those 123 dear fills | worth |
|---|---|
| 0.8% (the replay's own) | +$12.98 |
| 1.0% | +$9.49 |
| **2.0%** | **−$14.00** |
| 3.0% | −$37.50 |

$15.21 of the $17.08 comes from a 64–0 bucket at 98.5–98.7c where ONE adverse fill
costs $18.75 at size 20. **We have never bought above 98c live, so no live rate exists
for this population.** PROPOSED, not deployed: run it at ONE CONTRACT above 98c and
count, exactly as the hedge plant was run. **Needs per-order sign-off.**

### The tau kill is CONFIRMED on the rebuilt replay — the old one was right here

Flip rate per certain MARKET at today's gate: 0.02% (tau 3–10), 0.18% (11–20), 0.20%
(21–30), **0.44% (31–45, 2.2×)**, **0.75% (46–60, 3.7×)**. Same wall AMENDMENT 4 found
at PIN 0.98, lower in level, identical in shape. And dearer: mean price rises
monotonically 93.63c → 96.33c. TAU_MAX 60 earns +$111 on new closes and loses
**−$316 on closes we already trade**, because an early dear fill burns a
MAX_PER_CLOSE slot and raises the improve bar against the better offer still to come.
TAU_MAX 35 is the only positive row and is inside its MDE.

### The only result that clears its own MDE is NEGATIVE

`MIN_FILL_FRAC` 0.5 → 0.25 buys 5 closes worth +$0.69 and loses $18.48 on shared
closes: **−$0.0255/close, t = −5.3 against MDE $0.0095.** Do not lower the floor.

### Holdout: no power, not no effect

The BASE gate itself earned $0.2722/close in train and $0.0174 in holdout while
trading the same share of closes at the same mean price — the COUNT is stable, the
outcomes were worse. Holdout MDEs land 5–20× above the base's own holdout level.
**The holdout can refute a large lever; it cannot adjudicate one worth cents a close.**

### Two agent bugs caught and self-tested

The census first counted BOOK STATES, so a market whose book changes 7×/s contributed
204 rows against a thin market's 28 — it read "an ask exists 84.3% of the time" when
the per-(market,second) truth is **15.8%**, weighting the thin books out of their own
measurement. And `per_close_stats` reported the same fill count for all three splits.

---

## ⚠️ THE LIVE RECORD IS EIGHT STRATEGIES, NOT ONE — never quote a blended $/day (2026-09-12 20:4xZ)

The operator, correcting me: *"It doesn't need to land near 4.60 because 4.60 is
using a collection of strategies that slowly got improved. We haven't seen just this
strategy yet."* He is right. Every live fill split by the gate its run STARTED with:

| PIN / ceiling / guard / per-mkt / hedge | legs | markets | days | net $ | $/day |
|---|---|---|---|---|---|
| 0.98 / – | 11 | 11 | 0.27 | +0.21 | +0.79 |
| 0.98 / 0.988 | 21 | 19 | 0.40 | **−43.58** | **−110.09** |
| 0.98 / 0.98 | 50 | 50 | 1.10 | +25.93 | **+23.49** |
| 0.995 / 0.98 | 72 | 71 | 1.66 | +34.94 | **+21.10** |
| 0.995 / 0.98 / 0.15 | 3 | 3 | 0.02 | −16.20 | −777 |
| 0.995 / 0.98 / 0.15 / 1 | 21 | 21 | 0.22 | −1.98 | −9.06 |
| 0.995 / 0.98 / 0.15 / 1 / 0.90 | 43 | 39 | 0.34 | +14.49 | +42.15 |
| 0.995 / 0.98 / 0.15 / 1 / 0.80 | 7 | 7 | 0.09 | +3.90 | +41.59 |

**The blended "+$19.77 lifetime, ~$4.60/day" is dragged down by the −$43.58 of the
0.988-ceiling era, which no longer exists.** The longest single-gate window is
**1.66 days**; the full current model (0.80 hedge) has existed for hours. Every
$/day on a span under ~1 day is noise and is shown only to make that visible.

**Consequences that bind:**
1. **No live sample can anchor a $/day figure for any configuration.** The rebuilt
   backtest is the primary estimate, and its day-block bootstrap interval is the
   honest uncertainty — not agreement with a blended live number.
2. **A P&L tally must be grouped by gate**, read from each run's own `start` record.
   The start record logs every constant precisely so this is possible; that is what
   it is for.
3. The bank (+$19.77) remains the authority on CASH, and is still the only check on
   whether the logs are complete. It is not a rate.

---

## ⚠️ SUPERSEDED — THE LIVE RATE IS $1.71/DAY, NOT $25-30/DAY (reconciled 2026-09-12 03:22Z)

**The bank is the only authority on P&L and it must be checked before any
$/day figure is quoted.**

| | |
|---|---|
| bank | **$158.71** |
| deposited | $151.87 |
| **actually made** | **+$6.84 over ~4 days = $1.71/day at size 20** |
| the logs say | +$2.10 over 158 bets |
| unreconciled | $4.75 |

**The gap is explained and it is a LOGGING bug, not a money bug.** 164 orders
filled; only 158 `settled` records exist. The six missing ones are positions
that were open at the moment the trader was restarted: the new process never
knew about them, so it never wrote their outcome. Three of the six are the
`26SEP112200` markets held when the bot hit its position cap at 02:00.

**Consequence: every P&L number computed from `settled` records UNDERSTATES
the truth, and the count of bets is short by the number of restarts.** Quote
the bank.

**AND THE BACKTEST WAS OUT BY 15x.** `pin` was projected at $25-30/day at this
size. Live is $1.71/day. The cause is already documented -- the tape's
population is "an offer was resting there" and ours is "someone sold it to
us", so the tape says 0.11% loss and live says 5.1% -- but the SIZE of the gap
in dollars had not been stated until now. **No $/day projection from any
backtest may be quoted for this strategy.**

### Why it is so thin

Ordinary trades (what the guard allows): 147 bets, 4 lost, **2.7%**
[0.7, 6.8], average price paid **96.2c**.

At 96.2c the break-even loss rate is **3.8%**. We run 2.7%. **Headroom 1.4x,
and the 95% upper bound (6.8%) is ABOVE break-even.** The edge is positive at
the point estimate and its interval includes zero.

### Does more capital help? NO -- it scales, it does not improve

Depth measured over 88,169 resting offers on 217 closes:

| size | offers that hold it | total contracts vs size 1 |
|---|---|---|
| 20 (now) | ~80% | ~17x |
| 50 | 68.8% | 38x |
| 125 | 50.6% | 70x |
| 250 | 32.9% | 91x |

Roughly linear to ~50 and clearly sub-linear past it. **But the edge per
contract does not change, so more money multiplies the wins AND the losses
identically.** The only genuine benefit of a bigger bank is drawdown
tolerance: a worst close becomes a smaller fraction, which is what would allow
more bets per close.

**Recommendation: do not add money while headroom is 1.4x.** Scaling a thin
edge multiplies the consequence of it being zero.

---

## ⚠️ READING THE LIVE LOG — A TRAP THAT REPORTS 85x THE TRUTH (found 2026-09-11)

A `settled` record looks like this:

```json
{"ticker":"KXSOL15M-26SEP111845-45","want":"no","result":"no",
 "cost":0.83,"pnl_c":320.24,"realised":7.636,"t":"2026-09-11T22:45:20Z"}
```

- **`pnl_c` is THIS BET's profit in CENTS.** 320.24 = $3.20.
- **`realised` is the SESSION'S RUNNING TOTAL in DOLLARS**, not this bet's.

**Summing `realised` across records gives $1,183.46 on an account that has
made $13.87.** It reproduces `realised` exactly as a running sum of
`pnl_c`/100 on 144 of 144 records, so the two fields are consistent — they
just answer different questions, and the names do not say so.

**The right lifetime figure is `sum(pnl_c)/100`.** It was caught only by
reconciling against `/portfolio/balance`, which is the rule: a P&L number is
not believed until the bank agrees with it.

### LIVE, reconciled 2026-09-11 22:50Z

| | |
|---|---|
| lifetime | **144 bets, 137 W, 7 L — 4.9% loss rate, +$11.93** |
| account | $165.74 held, $151.87 deposited, **+$13.87** (the $1.94 gap is an open position / fee rounding, not reconciled) |
| today | 33 W, 1 L, +$11.30 |
| **since the 15¢ guard + 0.995 gate went live 13:23Z** | **9 bets, 9 W, 0 L, +$8.51** |

**Every loss, all seven:**

| when | market | paid | result |
|---|---|---|---|
| 09-09 00:45:20 | NEAR | 96.2¢ | −$19.29 |
| 09-09 00:45:35 | NEAR | 95.6¢ | −$19.18 |
| 09-09 00:45:50 | NEAR | 73.0¢ | −$14.13 |
| 09-10 05:00:20 | XRP | 82.0¢ | −$16.61 |
| 09-10 05:30:20 | BNB | 94.0¢ | −$17.60 |
| 09-10 22:15:20 | DOGE | 10.0¢ | −$2.12 |
| 09-11 12:30:20 | SOL | 59.1¢ | −$12.16 |

**Four of the seven were deep-discount fills the 15¢ guard now refuses** —
the SOL at 59.1¢ (40.4¢ under fair), the NEAR at 73¢ (26.8¢ under), the XRP at
82¢ and the DOGE at 10¢. `pinrun --selftest` asserts each of those is refused
by the code now running.

**The guard has fired 6 times.** The newest, 09-11 21:29Z, refused XRP NO at
74¢ against a 99.7% fair — a 25.7¢ discount, which the trade tape puts in the
band that loses 39.62% and costs −17.10¢ per contract.

---

## STATE 2026-09-11 12:40Z — read this first

**Current gate (0.995) since 09-10 08:33Z: 54 fills, 52 W, 2 L, +$21.73.**
Bank **$158.11** vs $151.87 in (+$6.24). Both losses were "crazy deals"
(DOGE 10¢, SOL 59.1¢ on a 29.5¢ discount).

**The class we still trade (discount under 15¢): 52 fills, 0 lost, +$36.01.**
Skeptically: 0 of 52 has a 95% upper bound of **6.8%**, and break-even at the
95.9¢ mean price is **3.78%** — the point estimate is excellent and the
interval still includes "loses money." That is what the 180-fill bar is for.
**No scaling** (54/180).

**Three amendments today, each on the live record:**
* **A10c** — the crazy-deal guard was wrong both ways: it demanded ≥99.9%
  confidence (the SOL loss was 99.5%) and refused the 5–15¢ band, which went
  24–0 for +$32.20. Now: discount-only, line at 15¢. The 15¢ line is FITTED
  on 9 fills and says so; the 40-record review decides it.
* **A12** — a scrap fill (under half our size) no longer spends a scale-in
  slot. Two scraps (2.0 and 0.02 contracts) had blocked real fills.
* Settlement file refreshed so the sandbox and the review resolve recent
  markets.

**The residual risk no rule touches:** a wrongly-"certain" bet at a FAIR
price. One costs ~$19.40 at 97¢; a win there pays $0.56; 32 wins to recover.
Live in the 2.6–4 sd band: 1 loss in 52. The model's extreme tail is not
trustworthy and only price limits the damage. This is the whole business, and
only fills will answer it.

**Open:** tool auth before any phone access (do not port-forward); Live tab
should aggregate every log of the current version; AMENDMENT 11 (control
reader) not built; Robinhood venue; the exchange-tick veto stays log-only.

## THE GAME PLAN — 2026-09-10 23:20Z, set from LIVE facts only. Bars fixed BEFORE the next number is seen.

### What is actually happening (live fills only; no backtest number in this section)

| | fills | losses | P&L | what the losses were |
|---|---|---|---|---|
| old gate 0.98 (09-08 → 09-10 08:33Z) | 85 | 5 | −$3.89 | 4 boundary trades at 2.1–2.9 sd, no price improvement, −$70 between them; 1 deep adverse fill (XRP, 82¢ after a 13.7¢ improvement) |
| **current gate 0.995 (since 08:33Z)** | **27** | **1** | **+$17.65** | 1 deep adverse fill (DOGE, 10¢ after a 43¢ improvement), −$2.12 |

**Two distinct loss mechanisms, both reconstructed by hand from the tape with no data error:**

1. **Boundary flips** — the model's own ~2% rate at 2.05–2.6 sd. Cost −$70 of the
   old gate's −$3.89. **Removed by construction** at 0.995 (2.58 sd). This is the
   only change whose effect is certain, because it is arithmetic, not a fit.
2. **Adverse fills at extreme confidence** — the model says certain, the book is
   selling far below fair, and the index then moves many sigma within a second.
   Pooled across both gates: **2 losses in 14 deep fills (14%)**, both with huge
   price improvement, against a model claim of ~1e−9. The tape cannot see this
   population at all (it hands us every offer), so no backtest can measure it.
   The exposure is self-limiting at cheap prices (10¢ → 90% break-even) and lethal
   at 60–94¢ (break-even 15%). Only **1** such 60–94¢ fill exists under the
   current gate. n is far too small to write a rule from.

### OWNER DECISION 00:12Z — refuse the "crazy deals", record what would have happened

EV of the class is undeterminable on six fills; the owner broke the tie toward
fewer losses. Guard ON; every such moment writes a `dumped` record (side, price,
fair, tau) so the would-be P&L resolves against the settlement. Reviewed at 40.
`VERSIONS.md` v-a10b.

### DECISION REVISED AGAIN 23:51Z — AMENDMENT 10 SWITCHED TO LOG-ONLY. The math does not support it.

The operator's rule: *if it is profitable do it, if not don't; if the math is not
certain, don't use it.* Six live fills of the "discounted certainty" class sum to
**+$4.75 — mean +$0.79/fill, SE ±$4.1, t = 0.19. The sign is not determinable.**
Refusing them is not certifiably profitable, so the frozen baseline (buy them)
stands and the guard only counts. **v-a10 was a loss-frequency preference dressed
as a decision; that was my error.** Pre-registered evaluation at 40 fills of the
class, on the 95% CI of mean P&L, never on cumulative P&L. `VERSIONS.md` v-a10a.

### DECISION REVISED 23:38Z — AMENDMENT 10 DEPLOYED: never buy a certainty at a discount

The operator asked the right question — *why not just refuse the crazy deals?* —
and the math says yes: on every live fill so far the rule is EV-neutral (−$4.75
over 111 fills) and removes the entire adverse-fill loss class. A trade whose EV
rests on the model's extreme tail (proven worthless: 2 of 14 vs ~1e−9) is a trade
whose EV cannot be estimated. Refused at ≥0.999 confidence and >5¢ discount.
Self-tested on the two real losses (refused) and the real cheap wins (untouched).
Details and revert: `VERSIONS.md` v-a10. **Bars A–C below are unchanged.**

### DECISION: HOLD. Size 20, gate 0.995, nothing else changes tonight.

Reasons, in order: the current version's live record is positive and broad-based
(+$17.65, 26–1, best trade only +$2.06); the expensive loss class is gone by
arithmetic; the remaining class is rare, mostly cheap, and every rule I wrote for
it in the last 48 h was fitted after the fact. I am not deploying another fitted
rule. **Wait-and-see is the correct decision, with the bars below written down now.**

### PRE-REGISTERED BARS — the number is decided before it is seen

**A. Scaling to size 25 requires ALL of:**
- **≥ 180 fills under the current gate** (that is what it takes to tell a 1% loss
  rate from the ~3.7% break-even at 96¢ with 80% power — not a round number I like)
- **observed loss rate ≤ 2.0%** over those fills
- **no single losing close over $25**
- the **−$60 abort literal fixed to scale with size** (at size 40+ one losing close
  trips it; it is fine at 20, and it is a precondition, not a tweak)
- bank ≥ **$196.00** (one worst-case losing close at the 98¢ ceiling ≤ 25% of bank)

**B. The adverse-fill guard (refuse deep-confidence offers priced 60–94¢) deploys
only if:** losses in that cell reach **2 of the next 6** such fills under this gate.
Until then it is logged, not acted on. Cost of leaving it open ≈ $2/day expected.

**C. The backtest.** `pinsim.py` is the only backtest. It is certified for exactly
one thing: it reproduces the live bot's DECISION (13 of 14 live signals, fair and
sigma to five decimals). **It is NOT certified for loss rates and must not be
quoted for them** — it cannot model fills, and the adverse-fill population is
precisely the one it cannot see. **Every loss-rate number in this repo comes from
live fills until pinsim has reproduced live LOSS OUTCOMES, which needs a fill
model it does not have.** `pincross`/`pintail`/`pinfirst` measure the model's
tail on the tape; they are not backtests of trading and are not to be described
as one.

### How reporting changes, because today's errors were mine

Every number carries **(gate version, n fills, n closes, time window)**. No
extrapolation from a partial day. No pooled number presented as one version's.
Ticker dates are ET; the log `t` field is UTC — read the `t` field.

---

## RIGHT NOW

| | |
|---|---|
| bank | **$110.45** |
| record | 30 wins, 3 losses |
| live | size **20**, 2 buys per close, ceiling **98.0¢**, tau 3–30, **gate 0.995 (A9)**; discounted-certainty guard **ON, would-be outcomes recorded** (A10b, owner decision) |
| restart it | **`RESTART.md`** in the repo root — one line to paste |
| brakes | −$60 · 3 losing **closes** · 2 order errors · 8 attempts/close |
| day | started $38.83, funded +$113.04 → **−$41.54** |

---

## ⭐⭐ 2026-09-10 — WHY THE LOSS RATE PROBLEM IS NOT A SIGNAL PROBLEM

**Two investigations ran in parallel on different hypotheses. They converge on
the same answer, and it is not the answer either was looking for.**

### The fact that reframes everything

| population | loss rate | 95% interval |
|---|---|---|
| backtest, moments we could actually have bought | **0.79%** | [0.10%, 2.82%] |
| live, what actually happened | **8.8%** | [2.9%, 19.3%] |

**Those intervals do not overlap.** Whatever is losing our money live is *not
present in the historical tape at anything like the live rate*. So no amount of
factor-hunting on tape can find it — and six investigations failing was the
tape telling us that, not us being unlucky.

### What was measured, and what died

**1. The model's tail IS too thin, and it IS state-dependent. (real, well powered)**
`pintail.py`, **9,159 settled markets over 1,019 closes**, settlement model
reconciled to 3.8e-07 first.

| | measured | the model claims |
|---|---|---|
| mean forecast error | **0.657 sd** | 0.798 sd |
| chance of an error past the gate, the losing way | **2.58%** | 2.00% |

**The model is not wrong in scale — it is wrong in SHAPE.** Errors are usually
*smaller* than it thinks, occasionally far larger. And the tail moves with
conditions: **2.22% when no other coin is moving, 6.60% when three or more are.**

**2. But no gate built on it survives out of sample. (the important negative)**
Thresholds fitted on the first 70% of closes and re-measured on the last 30%:

| refuse when | profit change, fit | profit change, **holdout** |
|---|---|---|
| 1+ other coins moving | +18.5% | **−18.0%** |
| cross-market roughness ≥ 1.4 | +16.3% | **−8.4%** |
| 2+ other coins moving | +11.3% | **−6.6%** |

**Every one of them.** The conditions are real; a *fixed threshold* on them is
not. Deploying one today would be curve fitting, and I am not doing it.

**3. Cheap fills are not the culprit. (refuted)** The suspicion was that a
seller dumping a near-certainty far below fair value knows something. Tested
properly, controlling for price level: **0 flips in 73 high-discount closes.**
The live-sized version of the claim (~25% flips on discounted fills) is refuted
outright at P ≈ 7e-10. Anything under ~10% is simply invisible in this sample.

**4. The live/backtest sigma gap. (refuted, and I was wrong)** The live bot
computes sigma as a standard deviation about the mean; the backtest uses a
root-mean-square. I expected live to be systematically smaller — a looser gate
than the backtest scores. Measured on the same 9,159 seconds: ratio **1.0008**,
tails **2.58% vs 2.57%**. Dividing by (n−1) almost exactly cancels the mean
subtraction. **Not the bug.**

### What was DEPLOYED (logging only, no money at risk)

`pinrun` now records the market-wide conditions at the instant of every
decision: `cond_x` (how rough the *other ten* coins are, this one excluded),
`cond_n` (how many of them are moving), `cond_own`. Self-tested, including the
exclusion — the traded coin's own spike must leave its own index *exactly*
unchanged, or it is the refuted own-sigma filter under a new name.

**Logged, not gated on.** We have zero live records of the conditions our
losses happened in, and the tape has been shown unable to explain them.

### ⚠ CORRECTION 2026-09-10 20:5xZ — THE CAPACITY CEILING IS 2x LOWER THAN I QUOTED

Triggered by the operator saying the number would be life-changing. That is
exactly when to go looking for the artefact.

**THE ERROR: every projection assumed fills/day stays constant as size grows.
It does not — the book runs out.** Measured on today's 37 real signals:

| size | signals with enough depth | contracts/day | **$/day** | what I quoted |
|---|---|---|---|---|
| 20 | 37 (100%) | 1,148 | $40.53 | $36.01 |
| 50 | 28 (76%) | 2,115 | $74.66 | $90.02 |
| 100 | 23 (62%) | 3,140 | **$110.83** | $180.03 |
| 125 | **17 (46%)** | 3,082 | $108.80 | $225.04 |

**Income PEAKS at size 100 (~$111/day) and DECLINES at 125** — past that we are
bidding for contracts that are not on offer. The bot needs `MIN_FILL_FRAC`
(half its size) resting; today's depth was min 10, p25 27, median 60.

**So the honest ceiling is ~$111/day = ~$40k/year, not $225/day = $82k/year.**
And the model still runs 28% hot at size 20 ($40.53 modelled vs **$31.59
observed**), so even $111 is an upper bound.

**THE MOST SOBERING NUMBER, and it belongs above all of the above: lifetime
P&L is about ZERO.** $151.40 in the account against $151.87 deposited — down
$0.47. Today's +$15.02 just recovered the −$15.02 the old gate lost. **This
strategy has never made money over its life**, and every forecast above is a
projection of a thing that so far has not paid.

**And we have never seen a loss under the current rule.** The 0.51% rests on 3
flips in 594 tape markets, CI [0.10%, 1.47%]. At the top of that interval the
peak is ~$81/day. Break-even at today's 95.67c is a **4.04%** loss rate; the
old gate ran at 5.95%.

---

### THE FORECAST, REBUILT ON AMENDMENT 9 (2026-09-10 12:0xZ) — `pinproj.py`

Bank **$140.24**. Every input re-measured, none inherited from the old forecast.

| | old gate 0.98 | **new gate 0.995** |
|---|---|---|
| price we pay | 93.1¢ | **97.0¢** |
| fills/day | 65 | **50** (−22%) |
| loss rate | **5.95% actual** | ~0.51% expected |
| break-even loss rate | 6.43% | **2.78%** |
| **safety margin** | **1.08×** | **5.5×** |
| profit per contract | +0.48¢ | **+2.27¢** |
| days to the 125 cap | 33 | **11** |
| income at the cap | $39/day | **$142/day · $4,275/mo · $52k/yr** |

**DAYS TO EACH SIZE** (measured inputs, 0.51% loss, 97.0¢, 50 fills/day):

| size | day | bank | $/day there | $/month |
|---|---|---|---|---|
| 20 | now | $140 | $22.80 | $684 |
| 30 | 2 | $192 | $34.20 | $1,026 |
| 50 | 5 | $306 | $57.00 | $1,710 |
| 80 | 8 | $494 | $91.20 | $2,736 |
| **125 (cap)** | **11** | **$813** | **$142.50** | **$4,275** |

**The ladder is set by the brake, not by hope:** size may rise only when the
bank covers `3 losing closes × 2 buys × size × price`. At $140 and 97¢ that
funds exactly size 20.

**THE HONEST COMPARISON.** The old gate had a *higher ceiling* ($360–474/day if
its loss rate had been low) because it bought at 93.1¢ and cheap contracts pay
more. It was running at a **1.08× margin over break-even** and it actually
lost **−$15.02 over 84 fills.** A ceiling you never reach is worth nothing.
The change bought a 5.5× margin for a lower ceiling. That is the trade, stated
plainly, and it is reversible in one line.

**THE BIGGEST LEVER IS NOT THE GATE — IT IS THE PRICE.** At the same 0.51%
loss rate: 97.0¢ → $143/day, 96.0¢ → $201/day, **95.0¢ → $259/day.** One cent
cheaper is worth more than anything else on the board. The ZEC fill proves the
two are separable: **93.3¢ AND 3.05 sd deep.** Getting deep markets at cheap
prices — patience, queue position, scale-in — is now the highest-value work.

**WITH REAL LOSSES IN IT (operator caught that the table above has none —
6,000 simulated 40-day runs, losses drawn PER CLOSE because a losing close
loses every fill on it):**

| loss rate | size 125 by (unlucky/typical) | bank at 40d (p10/p50) | worst dip 1-in-10 | ends poorer | brake halts |
|---|---|---|---|---|---|
| 0.10% | day 10 / 9 | $5,772 / $6,032 | $0 | 0.0% | 0.01 |
| **0.51% (measured)** | **day 13 / 10** | **$4,331 / $4,978** | **$192** | **1.1%** | **0.37** |
| 1.47% (upper 95% CI) | day 28 / 17 | $108 / $2,214 | $427 | **16.4%** | 3.87 |
| 2.80% (break-even) | day 36 / 25 | $88 / $106 | $262 | 89.5% | 3.54 |

**The measured case barely changes the headline — but the upper end of the
confidence interval is a different business**: a 16% chance of ending 40 days
poorer and a halt roughly every 10 days. The loss rate rests on 3 flips in 594
markets, so that column is not paranoia, it is the honest other end of what we
actually measured.

**Also corrected:** the "days to each size" table printed only the days the
size CHANGED, which hid the days in between and made the arithmetic look
wrong. Day 2 ($191.54, size 30) to day 5 ($305.54) is not 3×$34.20 — the rate
steps up to $45.60 when size reaches 40 on day 4.

**What is thin:** 50 fills/day rests on 7 fills over 3.3 h. The model predicts
$22.80/day at size 20; the first 3.3 h ran at ~$28/day — consistent, but that
is one afternoon. Sensitivity tables for loss rate × price × fill rate are in
`results/pinproj.log`.

**If the loss rate is really 2%+ at 97¢ we are near break-even** (2.78%) and
the answer is a cheaper price, not a stricter gate.

### DEPLOYED 08:4xZ — AMENDMENT 9: confidence gate 0.98 → 0.995. THE BAR MOVED.

The one lever with holdout evidence. It refuses the two margin bands that
flip at 1.8–3.1% and keeps everything at 2.6 sd or deeper (0.5%, then 0 of
7,868). Tape flips 18 → 10, holdout 3 → 1, no loss of opportunities in market
count. **It would have skipped 3 of our 5 losses and no deep win.** Cost
unmeasured: expect fewer fills at higher prices — the next day tells. Size,
brakes, ceiling unchanged. Revert is one line (`VERSIONS.md`).

The exchange-tick veto (the XRP mechanism) is **proven on events, not as a
rule** — 2 of 7 tape flips have the signature, p=0.07, 0 of 2 holdout flips
caught. Logged, not deployed (IDEAS_LOG S).

### LATER THE SAME NIGHT — three more results, one of them the lead we needed

**1. The model is right at its own boundary and never wrong deep inside.** Measured
at the second the bot actually fires (10,796 markets walked): flips are **1.8–3.1%
at 2.05–2.6 sd, 0.5% at 2.6–4 sd, and 0 of 7,868 above 4 sd.** Holds on a
holdout. Our live boundary fills lost 3/32 — inside that interval. **Two of our
three recent losses are exactly this: the boundary's own ~2%.** Raising the gate
to 0.995 halves tape flips at zero market-count cost; a margin-aware EV line is
correct but would not have removed a single live loss (it refuses 17 small
winners). Neither deployed; both logged (IDEAS_LOG K–M).

**2. The XRP loss was a sub-second information lead, not a model error.** At the
signal second the CF index printed **1.39075** while **Coinbase had already
traded 1.38950.** The seller at 82¢ had seen the exchange tick; the index caught
up one second later and fell ~10 sd. Our data was fresh — the *print* was stale
inside its own second. We already record every exchange tick (`feed_data`) and
have never used it. **This is the next test and the most promising lever of the
week: refuse to fire when the freshest exchange tick disagrees with the CF print
by more than ~2 sd.** It costs nothing when nothing is moving.

**3. Live P&L, reconciled to the bank: −$15.02 over all 84 fills.** The earlier
"+$26.50" excluded the −$52.60 NEAR close.

### The one thing that would actually settle it

**~70 more live fills with these columns attached.** That is the sample that
distinguishes a 25% problem from a 5% one. Tape alone would need ~10 more days
for the crude version and ~44 days for the fine one, and the interval mismatch
above says even then it would be answering about a different population.

---


## CORRECTION TO THE SECTION BELOW — I CONFLATED TWO CONFIGURATIONS

The operator: *"How has it lost twice in two days when we put this version out
this morning?"* **He is right and the section below overstates the case badly.**

**What I got wrong:**
1. **"Twice in two days" is false.** Both losses were on 2026-09-10. Kalshi
   tickers are in ET, so `26SEP100100` is 01:00 ET = 05:00Z and
   `26SEP101815` is 18:15 ET = 22:15Z — the same day.
2. **Worse: the XRP loss at 04:59Z predates this version.** The 0.995 gate went
   live at **08:33Z**. XRP was the OLD gate. Only the DOGE loss belongs to the
   version we are running.
3. **"Our entire profit is one trade" is a fact about the OLD gate, not this
   one**, and I applied it to both.

**THE CORRECT SPLIT:**

| | fills | losses | P&L | without its best trade |
|---|---|---|---|---|
| old gate 0.98 | 85 | 5 | **−$3.89** | **−$19.25** — profit WAS one trade |
| **new gate 0.995** | **26** | **1** | **+$17.28** | **+$15.21** — broad-based |

**The new version's record is 26 fills, one loss, +$17.28, and its profit is
NOT concentrated in one outlier.** The one-trade problem was real and it was
the old gate's.

**WHAT STILL STANDS, and it is narrower than I claimed:** `fair()` is the same
function in both versions — the gate changed the threshold, not the model. So
the deep-band evidence pools legitimately: **2 losses in 14 fills at 4+ sd,
where the model claims ~1e−9.** The model's extreme-confidence tail is
unreliable. But **only 3 of those 14 fills are under the current version**, so
nothing can yet be said about this gate's deep-band rate.

**THE SCALE-UP STAYS PAUSED — for the correct reason.** Not "the profit is one
trade" (false for this version) but **26 fills is too few to scale on**, and
the deep-band question is open. Hold at 20.

---

## 🚨 THE HONEST STATE, 2026-09-10 23:0xZ — OUR ENTIRE PROFIT IS ONE TRADE

Operator: *"I don't care if 'we got lucky and only lost 2 dollars', that isn't
the point. Unless that was a crazy fluke then we are fucked why aren't you
seeing that."* **He is right. I was reporting the dollar and missing the
mechanism.**

### 1. The model's confidence is meaningless at the extremes

| model says | live fills | lost | **live rate** | model's own number | tape |
|---|---|---|---|---|---|
| 2.05–2.6 sd | 45 | 3 | 6.7% | 0.01 | 1.8–3.1% |
| 2.6–4.0 sd | 52 | 1 | 1.9% | 0.0005 | 0.5% |
| **4–8 sd** | **14** | **2** | **14.3%** [1.8, 42.8] | **1e−9** | **0 of 7,882** |

**In the band the model calls certain we lose 14.3% of the time.** That is 350x
the tape's upper bound and nine orders of magnitude off the model. Twice in two
days, both at 7.03 sd. **It is not a fluke and it is not a rounding error — the
tail of this model carries no information at all.**

### 2. What has been saving us is the PRICE, not the model

| deep band, by price paid | fills | lost | P&L | break-even loss rate |
|---|---|---|---|---|
| under 60c | 2 | 1 (50%) | **+$13.24** | 84% |
| **60–94c** | **4** | **1 (25%)** | **−$8.49** | **15%** |
| 94c+ | 8 | 0 | +$2.55 | 2% |

**The lethal cell is high confidence at a moderately discounted price.** Cheap
enough that the market clearly disagrees, dear enough that being wrong hurts.
And the 94c+ deep cell is the biggest latent risk: eight fills, no loss yet, a
2% break-even, against a 14% observed rate.

### 3. THE NUMBER THAT MATTERS MOST

**111 live fills. Lifetime P&L +$13.39.**
**Remove the single best trade (SOL at 22c, +$15.36) and it is −$1.97.**
**Remove the best two and it is −$8.85.**

Median trade +$0.46, mean +$0.12. Many small wins, rare large losses — the
negative-skew shape this project was built to avoid. **We do not have evidence
that this strategy makes money.** We have one lucky trade and 110 others that
net out slightly negative.

### WHAT CHANGED AS A RESULT

**THE AUTOMATIC SCALE-UP TO SIZE 25 AT $196 IS CANCELLED.** I promised it
earlier today; on this evidence it would have been wrong. **Size does not rise
until the deep band is understood.** Nothing about scaling is supported by 111
fills whose profit is one outlier.

---

## THE FIRST LOSS UNDER THE NEW GATE — 2026-09-10 22:15Z, KXDOGE15M, −$2.12

**It cost $2.12. The same wrong call an hour earlier would have cost $19.48.**

Two signals on the same close:

| | tau | our bid | filled | model | outcome |
|---|---|---|---|---|---|
| 1 | 17s | 97.4c | **nothing — lost the race** | 99.55%, 2.61 sd | — |
| 2 | 11s | 53.0c | **9.98c** (43c improvement) | 100.00%, 7.03 sd | **LOST** |

**LOSING THE FIRST RACE SAVED US $17.36.** Filled at 97.4c the loss is $19.48;
filled at 9.98c it is $2.12. This is the price-ladder thesis paying out in the
most literal way available: *the same error, nine times cheaper.*

**What happened.** DOGE sat 7.5e−6 below the strike for 30 seconds, we filled at
t−11, and **one second later it jumped +9.1e−5 — 18 sigma — and never came
back.** Window mean settled 0.0840355 against a strike of 0.0840226. No data
error: the bot's inputs reconcile to the tape exactly.

**The market knew and we read it backwards.** Our model said NO was certain;
the book was selling NO at **10c**, i.e. pricing YES at 90%. We treated a
violent disagreement as free money. It was a warning.

**The conditions index gave NO warning** — `cond_x` 0.81, `cond_n` 0,
`cond_own` 0.55 (calmer than its own hour). First live test of the thing I
deployed this morning, and it was blind to this.

**AND THE TAPE SAYS THIS CANNOT HAPPEN: 0 flips in 7,882 markets at 4+ sd.**
We have now had **two in two days** (XRP 7.03 sd, DOGE 7.03 sd). That is the
live-vs-backtest gap again, in the one band the backtest calls risk-free.

**But the dollars say something calmer.** Across all 85 live fills:

| price improvement | fills | losses | P&L |
|---|---|---|---|
| none (<0.5c) | 79 | 4 | **−$22.33** |
| 0.5–5c | 3 | 0 | +$8.56 |
| 5c+ (the adverse-fill shape) | 3 | 2 | −$3.37 |

**Four of our six lifetime losses were ordinary boundary trades with zero price
improvement, and they cost −$70 between them.** The deep adverse fills are
roughly break-even (XRP −$16.61, DOGE −$2.12, SOL +$15.36). **The gate change
already addressed where the money actually went.** Not deploying anything on
n=3.

---

## THE ONE LOSS, IN FOUR LINES

Three buys, **one market**, one close. 96.2¢ / 95.6¢ / 73.0¢. All lost together. **−$52.60.**
The index sat still for 8 seconds, then moved 0.0021 **in one second** and never came back.
Settlement checked independently: **the arithmetic is not broken.**
The brake stopped it. Nothing was left open.

---

## WHAT I GOT WRONG (and corrected)

| I said | truth |
|---|---|
| hedging cuts ruin risk **30×** | assumed unlimited depth. Only **6 of 12** hedges are deep enough at size 20 |
| model is **3×** overconfident | **1.43×**, CI [1.18, 1.70]. My 3× rested on 10 closes |
| tighten the gate to 1.5% | costs **22–44 winning trades per loss avoided** |
| the scale-in rule caused the loss | **not supported** — loss rate is flat by buy index |
| stale sigma was the warning sign | **dead**, p = 0.14–0.99 |
| a $28.92 balance drop was unexplained | it was committed stake, to the cent. I reported before subtracting |

**Seven size-1 constants broke scaling in one day.** Any constant tied to size must be written in terms of size.

---

## THE BEST THING LEARNED (2026-09-09, Joe's argument)

**"Unless it eliminates 100% of losses it just makes earning back our blunders
more difficult."** Correct, and it kills every probability gate: each costs
22–44 winning trades to avoid a loss worth ~24 wins, so it's a wash AND it
burns the wins we recover with.

**But the recovery ratio is a PRICE lever, not a probability one, and it is
arithmetic:**

| price paid | a win pays | wins to recover one loss |
|---|---|---|
| 98.8¢ | 1.11¢ | **89** |
| 98.0¢ | 1.86¢ | 53 |
| 96.0¢ | 3.73¢ | 26 |
| 90.0¢ | 9.37¢ | **10** |

Ceiling moved 98.8¢ → **98.0¢**: measured 129 trades/742¢ → 118 trades/**768¢**,
and wins-to-recover 16 → 14. **More money and better resilience at once.**

---

## THE ANALOGUE STUDY — a lesson worth more than the result

Joe's idea: find historic moments that look exactly like the one we lost on,
see what happened next. **It looked like a hit: 200 nearest analogues crossed
36% of the time against a 10% base rate, 3.5x, p=0.0003.**

**The verifier killed it with the null the study never ran.** The target
fingerprint was chosen BECAUSE IT FLIPPED. If flip probability varies across
feature space — and volatility clustering guarantees it does — then picking a
target from flipped cells buys a lift with **zero predictive content**.

Re-run with targets drawn from other flipped cells: **median placebo = 1.96x.**
Nearly two thirds of the 3.5x was free. Corrected p = **0.159. Not significant.**
The jump result went from 2.20x to **0.59x** in units of current volatility.

**THE RULE THIS GIVES US: when you search for things resembling a known bad
outcome, your control must also be drawn from bad outcomes.** Otherwise you
measure your own selection.

Also costed and rejected: repricing with `max(sigma_30, sigma_300)` refuses
**963 winners for 6 losses avoided**, net −4,538¢.

---

## THE HEDGE: TESTED PROPERLY UNDER JOE'S OBJECTIVE. IT DOES NOT WORK.

Three tracks, six agents, all refuted. **No hedge gets near the target.**

| | worst loss, in wins to recover |
|---|---|
| Joe's target | **1–5 wins** |
| no hedge | 21.8 |
| best hedge, with realistic depth | **20.7** |

**It moves the worst loss by one win.** And it costs **−6.9% of all profit** on
the window we actually trade, for **zero measured benefit** there (0 losers in
83 closes). The headline +39% came entirely from tau 31–60, a window
AMENDMENT 4 already removed from the live rule.

**Break-even for the rule is a 0.90% loss rate. Our live constant IS 0.90%.**
A coin flip on our own best estimate.

### Why insurance is never cheap here

There IS enough time — losers cross at median tau 14 and 97–100% of alarms fire
with ≥3 seconds left. **The constraint is PRICE, not latency.** The market
reprices in the same instant the move happens, so by the time we know, the
other side already costs what it is worth.

### Two things that kill the "warning sign" idea for good

- **`mu` crossing the strike is a near-perfect classifier** — losers cross
  100% of the time, winners essentially never. But it arrives at the *same
  moment* as the price. It is a report, not a warning.
- **Tonight the cushion |spot − K| GREW from 0.00085 to 0.00135 as the trade
  died.** An unsigned-distance alarm is structurally incapable of warning.

### The win unit was optimistic and the corrected figure is worse

Median winning close is **$0.78**, median 3.26¢ per contract. So the worst
close, −$37.50, is **47.8 wins at the median**, not 20.8. The recovery problem
is bigger than I said.

---

## ⭐ THE PRICE LADDER — the biggest finding, measured 2026-09-09

22,568 model-confident moments. **Cheap trades flip ~5× more often and are far
SAFER, because break-even rises faster than the flip rate.**

| price | flip rate | break-even | margin |
|---|---|---|---|
| 70–85¢ | 2.50% | 18.2% | **7× safe** |
| 93–97¢ | 1.95% | 4.2% | 2× safe |
| **98–100¢** | **0.53%** | **0.30%** | **LOSES MONEY** |

**83% of everything our model likes sits in the band that loses money.** The
98.0¢ ceiling now has outcome data behind it, not just arithmetic.

**NEXT ACTION, not yet deployed: SIZE INVERSELY WITH PRICE.** We currently stake
the same on a 2×-margin bet as a 7×-margin one. The 22¢ SOL trade had 200
contracts available and we took 20. Needs: cheap-offer frequency (only 3 of
22,568 moments were under 70¢), market impact at size, and a bank that funds it.

---

## ⭐⭐⭐ THE THING WE MUST DO — Joe, 2026-09-10

> *"We can control our own losses because we already do. We don't try to buy
> into every bet, we look at the conditions and see if it's favorable. We need
> better conditions, and a faster understanding of how 'favorable' changes."*

**He is right and it corrects me.** I had said we cannot control how often we
lose — only what a loss costs and when we stop. That is wrong. **The gate IS a
choice about frequency.** Every close we decline is a loss we chose not to
take. What is true is only that we have not yet found a BETTER rule for
choosing.

### Why six investigations all came back empty

We judge "favourable" with **ONE number per trade**: how far the index must
move, divided by a volatility estimate averaged over the trailing 300 seconds.

That number is **slow** (five minutes of history), **isolated** (one coin, blind
to the other eleven), and **measurably wrong in the tail** (the gaussian is 9.3×
too thin at 3 sigma, 176× at 4).

**Every fix attempted this week was a FILTER BOLTED ONTO THAT ONE NUMBER** —
flatness, sigma regime, recent jump, price velocity, model-vs-market divergence,
cushion ratio, k-NN fingerprints. All six failed, and they failed for the same
reason: *asking a slow blind measure to say something it cannot*. The forensics
proved it directly — once `z` is held fixed, **nothing else adds anything.**

### So the answer is not another filter. It is a better signal.

Measure **the conditions themselves**, across all twelve coins, continuously,
and let the definition of favourable move with them:

- realised volatility **now** (1s / 5s / 30s), not a 300-second average
- **how many coins are moving at once** — a cross-market roughness index. The
  per-coin version is what got refuted; the cross-market version is untested.
- the rate of change of roughness, not its level
- book-side signals: spread widening, depth thinning, quote churn

Then tighten the gate while it is elevated and loosen while it is flat, instead
of holding one fixed threshold through calm and storm alike.

### The evidence this is the right target

**All five losses live in TWO hours out of thirty.** Twenty-eight hours with
none. Losses are not a steady drip; they arrive in bursts, because volatility
arrives in bursts. A fixed threshold cannot see a burst. **A live conditions
measure is the only proposal we have that aims at the FREQUENCY of losses
rather than their size.**

First test (weak version, using a loss as the signal): the close immediately
after a losing close is **1.8×** more dangerous, dying to nothing by 4 closes.
Right shape, but p = 0.318 on 22 events — not significant. **The strong version
uses live conditions, available before any loss, across 53,555 rows instead of
22 events. It has never been run.**

---

## ⭐⭐ THE BACKTEST IS FIXED, AND THE REMAINING GAP HAS A SUSPECT

**Two real bugs fixed 2026-09-10.** `Book.snapshot()` read `yes_dollars`; the
tape sends `yes_dollars_fp`, so snapshot seeding NEVER worked and every replayed
book was delta-only. And `fulltape/markets.json` was stale to 09-06, so all
three real losses had no settlement and were invisible. `research/pinverify.py`
is the acceptance test: **3 real losses AND 2 real wins must all reproduce.**
It now passes. It caught two errors of mine first, including a fixture where I
had typed the wrong side for 4 of 5 trades.

| | fixed | old (broken) |
|---|---|---|
| rows | **53,555** | 28,479 |
| closes | **151** | 80 |
| losing closes | **1 = 0.66%** | 0 = 0.00% |
| avg price | 93.77¢ | 93.06¢ |
| profit/contract | **+5.38¢** | +6.50¢ |

**But the backtest still says 0.66% while live says 5.71% (2 in 35).**

### THE SUSPECT: we are filled at prices nobody meant to give us

| | n | asked | paid | improvement |
|---|---|---|---|---|
| wins | 78 | 94.91¢ | 94.41¢ | **0.49¢** |
| **losses** | 5 | 90.90¢ | 88.16¢ | **2.74¢** |

Fills bettering our ask by **>0.5¢ lost 25% of the time**; fills at or near our
ask lost **5.1%**. The worst: we bid **95.7¢ on XRP and were filled at 82¢** —
13.7¢ of unexpected generosity, and it lost $16.61.

**The mechanism: the backtest models the trade we INTENDED, at the displayed
price. Live we get the trade someone CHOSE to hand us — and a seller in a hurry
often knows something.** That is a different, adversely-selected population, and
it would explain the whole 0.66%-vs-5.71% gap without the replay being wrong.

### THE EVIDENCE AGAINST IT, which matters

**Our single biggest win was also our biggest price improvement.** The 22¢ SOL
fill was bid at 56¢ — **34¢ of improvement** — and made **+$15.36**. So a
surprising fill is not simply poison; it is HIGH VARIANCE. Of the two largest
improvements on record, one won huge and one lost huge.

**And it rests on five losses.** The 25%-vs-5% split turns on ONE loss among
four improved fills. Three patterns of exactly this shape have already dissolved
under proper testing this week. **Do not deploy anything on it.**

### HOW TO SETTLE IT

The rebuilt dataset carries `price` and `spread` per moment, so the modelled
fill can be compared against the touch across 53,555 rows rather than 83. Test
whether flip rate rises with the gap between ask and fill, clustered by close,
with a shuffled control. If it survives, the fix is not a gate but a **price
sanity check**: refuse a fill that betters our ask by more than X, because it is
not the trade we priced.

---

## 📌 FRIDAY LIST — raised by Joe 2026-09-09, not yet started

### 1. ROBINHOOD RUNS THE SAME MARKET ON THE SAME PRICE SOURCE

Joe: *"Robinhood has the exact same 15 min average market and same price source
as Kalshi."*

**This attacks our actual binding constraint.** We measured that the limit on
earnings is not capital and not our rules — it is that **8 of 30 closes have
nothing to buy at all** (the losing side's book is empty in 33,427 of 33,431
decided moments). A second venue settling on the *same index* is a second shot
at the same certainty. Potentially double the opportunities for the same
research.

**Check in this order, cheapest first:**
1. Is there an API, and does it allow programmatic orders?
2. Fee schedule — Kalshi is `ceil(0.07·p·(1−p)·n)` and makers pay zero. If
   Robinhood charges differently the whole price ladder shifts.
3. Settlement wording: is it the same 60-print average over the same window,
   and the same rounding? `strike − 0.5·10^−digits` matters enormously.
4. Do prices actually diverge between venues? If the same outcome is 94¢ on
   one and 97¢ on the other, that is a real edge on top of the strategy.

**Caution worth stating up front:** "same price source" is a claim to verify,
not assume. This project has been burned by assumed field semantics twice
(DOGE's 7 round-digits, the `_fp` snapshot keys). Read their contract wording
before writing any code.

### 2. A DESKTOP WINDOW INTO THE BOT'S BRAIN — two modes

**LIVE** — what the bot is seeing and thinking right now.
**SANDBOX** — the same panels, driven by historic tape instead of the live feed,
with every constant editable. Joe's name for it, and the name carries the point:
*a place to play with past data and made-up values without touching real money.*
Scrub to any past close, change the ceiling / size / cap / gate, and watch what
the bot WOULD have done. Every rejected idea in IDEAS_LOG could have been
answered here in minutes instead of by a six-agent workflow.

**The sandbox must make one thing impossible: mistaking it for live.** Different
ground colour, a permanent banner, and no code path to the order API at all —
not a disabled button, an absent one.

Joe: *"I want a desktop tool to live view the bot what it's seeing and reading
and get a peek into its brain."*

Everything needed is **already being logged** — `pinrun-live-*.jsonl` carries,
per close: every market watched, the index spot and its age, sigma, the
computed fair value, the required move, the price on offer and its depth, which
gate refused it, order latency, and the fill. Nothing new needs instrumenting.

What is missing is a **reader**. Shape worth building:
- the 15-minute countdown, and for each of the 12 markets: spot vs strike, how
  far it must move to flip, and the model's confidence
- a live funnel per close — looked → decided → offered → passed the gates →
  fired — so a quiet close explains itself
- the price ladder colour-coded by wins-to-recover, since that is the number
  that actually matters
- the brakes: realised P&L against −$60, losing closes against 3

**AND AN EQUITY CURVE, TREATED LIKE A TICKER.** Joe: *"track the bets we do and
my balance amount in a stock like line graph with all the things a regular
stock has, exc % change and all the other things."*

The balance line, with every trade marked on it, plus the standard readouts a
ticker carries:

| | |
|---|---|
| headline | balance, absolute change, **% change**, up/down colour |
| ranges | today · 7d · 30d · all — each with its own % change |
| session bar | open · high · low · current, and the day's range |
| **max drawdown** | peak-to-trough, in dollars, % **and wins-to-recover** |
| volume | trades per period, fill rate, and races lost |
| markers | every fill on the curve, hover for coin/price/size/result; **losses flagged** |
| return | since inception, and annualised **with the capacity ceiling stated** |
| capital | deployed vs idle — this strategy caps out around $940 |

**Two things a normal ticker does NOT have, and this one must:** the *wins to
recover* figure on every drawdown, because that is the operator's own unit; and
an explicit note that annualised return is meaningless past the capacity
ceiling, so the chart cannot imply compounding that the market will not allow.

---

### 2a. THE SANDBOX IS THE POINT — operator, 2026-09-10

> *"you showed the penny changing profits so much, that's why I wanted the
> simulator sandbox so I can see how that changes all the other variables too"*

**He is right, and this is a bigger idea than the spec I wrote.** One cent of
price is worth **+40% of income** ($143/day at 97.0¢ vs $201/day at 96.0¢).
Nobody's intuition is calibrated for that, mine included — I spent a week
tuning the gate and the biggest lever on the board was the price.

**TWO KINDS OF SLIDER, and the difference is everything.**

| | ASSUMPTION sliders | **RULE sliders** |
|---|---|---|
| what moves | loss rate, price paid, fills/day, bank | gate (PIN), ceiling, tau window, size, max per close |
| what happens | re-runs `pinproj.py` instantly | **re-runs the real tape** and *derives* fills, price and loss rate |
| honesty | a toy — it answers "if I assume X" | a decision tool — it answers "if I had actually done X" |
| speed | instant | seconds to a minute |

**Only the second kind is worth trusting**, and we can now build it: `pinfirst.py`
already walks all 10,796 markets and finds the crossing at ANY gate level, and
`pindata_fixed` holds every tradeable moment. So moving the gate slider can
produce a REAL fill count, a REAL average price and a REAL loss rate, which
then feed the projection — instead of me guessing at them.

**THE TRAP, AND THE TOOL MUST BE BUILT AGAINST IT.** A slider that shows profit
invites hunting for the profit-maximising setting on data we have already seen.
That is precisely how every conditions gate died: **+18.5% on the fit half,
−18.0% on the holdout.** So:

* **every RULE result shows FIT and HOLDOUT side by side, always, never one
  number.** A setting that only looks good on the fit half must look obviously
  broken in the tool.
* every rate carries its **n as markets AND closes**, and its exact interval.
  "0.51% [0.10, 1.47] on 594 markets / 3 flips" — not "0.51%".
* a **"you are now curve fitting" warning** once the operator has tried more
  than a handful of settings, with the multiple-looks threshold shown.
* the **live setting is always marked on every axis**, so "what am I actually
  proposing to change" is never ambiguous.

**AND THE HARD RULE STANDS:** the sandbox build has **no code path to the order
API and no writer for `CONTROL.json`** — an absent button, not a disabled one.

**Why this matters more than the pretty charts:** the live view tells us what
happened. The sandbox is where we find out what *would* happen — and given
that a penny is worth 40%, that is where the money is.

---

### 2d. PROFILES — operator, 2026-09-10. YES, and it replaces a manual process.

> *"profiles that you can save the sandbox as then run that profile. Default
> will be the main configuration... I can create a new profile by adjusting
> some risk and saving it as 'risky' and I can run/deploy that configuration
> from the tool whenever I want."*

**This is right and it formalises something already done by hand.** Every live
change is currently a source edit plus a `VERSIONS.md` entry plus a restart.
A profile IS that entry, in a form the machine reads.

**Shape:** `profiles/*.json`, git-tracked so they diff and revert like code.
`default.json` is today's live rule (gate 0.995, ceiling 98.0c, tau 3-30,
size 20, 2 per close, -$60 abort, 3 losing closes). `pinrun --profile risky`.

**FOUR GUARDS, and the first one is not negotiable.**

1. **DEPLOYING A PROFILE MUST STILL RUN THE SELF-TEST SUITE AND REFUSE ON A
   FAILURE.** One-click deploy is a live-money action that would otherwise
   bypass the gate that has caught *every* serious bug in this project. It
   must also range-check every field: `--loss-abort` outside its band once
   made the process exit instantly and silently, and we lost an hour of
   trading to it.
2. **A profile may not loosen a brake without the worst case shown and typed
   confirmation.** The tool must print "this profile permits losing $X before
   it halts" using the profile's own numbers, not a stored string.
3. **THE LOG RECORDS THE PROFILE NAME, ITS FULL CONTENTS AND A HASH AT
   START.** We already carry `code_sha` because I once read a DERIVED log
   field and wrongly announced that a ceiling had never been live. A profile
   name alone would reintroduce exactly that bug.
4. **Switching profiles = stop cleanly, restart.** Never mutate size or
   brakes mid-run: the brake counters and open positions are keyed to the
   running configuration, and changing size under an open fill is how stakes
   get stranded.

**And a temptation to name:** running "risky" for a day and comparing to
"default" proves nothing at our loss rates. Any A/B in the tool must print
its MDE first.

---

### 2e. "WHAT WOULD REALLY HAVE HAPPENED" — the operator asked what could
deceive here. There is one big thing, and it is the project's largest known risk.

> *"the time progression should just be showing exactly what would've really
> happened had we bet... Not sure what confusion or deception could be there"*

**The replay is honest about the MARKET. It cannot be honest about whether the
trade would have been OURS.** In a replay every resting offer is ours for the
taking. In life we send an order and **fill 70% of the time** (50 of 72
attempts). A replay that assumes every offer is a fill overstates the trade
count by ~43%, and it overstates it *most* exactly where the money is, because
the best prices are the ones others are also racing for.

**So the sandbox shows BOTH, always, side by side:**
`if every offer were ours: $X` and `at our measured 70% fill rate: $0.7X`.

Four smaller ones, all real:

* **Market impact.** A profile at size 125 takes 125 contracts at the
  top-of-book price in a replay. Measured impact keeps 10.2-11.3x of a naive
  12.5x, so it is not fatal — but the replay must apply the curve, not the
  touch price.
* **Partial and dust fills.** A 0.02-contract fill is not a position. The
  replay must model the same `MIN_FILL_FRAC` the live bot uses.
* **Settlements we do not have.** 10,796 of 14,161 markets carry a settlement
  level. The replay must state how many it dropped, every time.
* **Our own footprint.** At size 125 we are a visible participant; nobody has
  measured what the other side does when we show up repeatedly.

**None of these make the replay useless — they make it an UPPER BOUND, and it
must be labelled as one on the screen, not in a footnote.**

---

### 2b. THE CONTROL CENTRE — play / pause / stop (operator, 2026-09-10)

The tool is not just a window, it is the **control centre**: play, pause and
stop the trader from it.

**HOW, and the design matters more than the buttons.** The tool must NEVER hold
the order API, and must never kill a process directly. Instead:

* the tool writes `results/CONTROL.json` — `{"state": "run" | "pause" | "stop"}`
* `pinrun` reads it once per loop and obeys: `pause` stops opening new
  positions but keeps settling and reconciling the ones already open; `stop`
  finishes open positions, writes the `end` record and exits cleanly.
* **PAUSE MUST NEVER ABANDON AN OPEN POSITION.** A pause that stops the loop
  dead would leave a fill unsettled and its stake stranded in the ledger —
  the same class of bug as the stake leak fixed on 09-08.
* the file is the only channel. That keeps the SANDBOX rule intact: the
  sandbox build has no code path to the order API *and* no writer for this
  file.
* the trader logs every control transition, so "why did it stop trading at
  3am" is answerable afterwards.

**Not yet built.** `pinrun` has no control-file reader today; stop is currently
`Stop-Process` per `RESTART.md`.

---

### 2c. RUNNING IT ON A RASPBERRY PI (operator, 2026-09-10) — YES, WITH CONDITIONS

**The decisive architectural fact, checked today: `pinrun.py` never reads
`kalshi_data` or `feed_data`.** It opens its own WebSockets for the index and
the book. **The trader and the collectors are completely independent.** So the
move splits into two very different jobs:

| | trader (`pinrun`) | collectors |
|---|---|---|
| disk needed | a few MB of JSONL | **2.57 GB/day** (45.5 GB so far) |
| if it stops | brakes halt safely, restart any time | **tape is gone forever** |
| verdict | **move it first** | move only onto an SSD, never an SD card |

**LATENCY — measured, not guessed.** Order latency today is 76–1128 ms, p10–p90
**82–119 ms**. Splitting our 70 deduped attempts at the median: the faster half
fills 72.2%, the slower half 67.6% — a 4.6pp gap on n=70, well inside noise.
**Within the ±20 ms we naturally vary, latency does not detectably change the
fill rate.** That is NOT a licence to add 200 ms: it says nothing about
latencies outside the observed range. And note we win 70% of the races we
enter — the reason we skip closes is `no_offer` (60,812 moments with the model
decided and nobody selling), not losing races.

**Conditions before trusting a Pi:**
1. **SSD over USB, never an SD card** if the collectors move — sustained
   writes kill SD cards, and the tape is unreproducible.
2. **Port the paths.** `C:\kals`, `C:\kals-repo`, `C:\Users\Joe\...` are
   hardcoded across the repo, plus `C:\Python314`.
3. **Check the Python version.** This runs on 3.14; Pi OS ships 3.11.
   `research/shadow.py` exists precisely because a module once broke 14 of 16
   stages on 3.14 while passing on 3.11. Run the full self-test suite there
   before it touches money.
4. **Wire, not WiFi.**
5. **Validate latency in PAPER mode on the Pi, side by side with the PC**,
   before moving the live trader. That measurement is cheap and it is the only
   thing that could make this a bad idea.

**The alternative worth pricing: a small cloud VM would be FASTER, not slower**
(Kalshi is US-East; we are on a home connection), which raises fills/day — the
single biggest driver in `pinproj.py`. It costs real money monthly, so it is
the operator's call, and it is only worth raising once size is past ~50 and
$10/month is noise instead of 7% of the bank.

---

### 3. DUST FILLS BURN A SCALE-IN SLOT (found live 2026-09-10 03:44Z)

`KXBTC15M` filled **0.02 contracts** at 97.9¢ — worth about **0.03¢** — and it
consumed one of the two buys allowed for that close.

Same shape as the no-fill bug fixed on 09-08, one layer down: `MIN_FILL_FRAC`
gates what we ASK for, nothing gates what we GET. A fill under some fraction of
the requested size should not book a slot, since it creates almost no exposure
and blocks a real position behind it. Cheap fix, needs a self-test that a dust
fill does not book and a real partial still does.

---

### 4. SWEEP THE SURPLUS ONCE WE HIT THE CAPACITY CEILING

Joe's instinct, 2026-09-10: once the bet size caps out, the extra money is doing
nothing, so take it off the table.

**He is right about the money and wrong about the reason.** The cap does not make
anything "guaranteed won" — every close still risks the full stake, and at size
125 a losing close costs about $120. What is true is that **only ~$940 is doing
any work**. Above that, capital sits idle *and stays exposed to the account's
own risk of ruin* for zero return.

**POLICY: once size caps at ~125 contracts, sweep everything above ~$1,100 out
of the Crypto shard.** That surplus is then genuinely out of reach. It also
means a catastrophic loss rate can only ever destroy the working float, not the
winnings.

Needs: a withdrawal path (never automatic — the operator moves money, not me),
a float threshold with hysteresis so it does not sweep and refund daily, and the
size ladder recomputed against the *float*, not the total balance.

---

## OPEN QUESTIONS — where pushback is worth most

1. **THE RACE.** 26% of orders fill nothing. Depth is not the cause (misses had 562, 107, 93 contracts on offer). Our round trip is ~100ms whether we win or lose; misses happen on *fresher* prices. Suggests we lose to **already-resting** orders, not faster ones. Unmeasurable from tape so far.
2. **THE HEDGE, RE-AIMED.** Earlier study optimised **expected value** and rejected it. Joe's objective is different: *"losing 1–5 wins worth more frequently beats one loss costing tens to a hundred wins."* **Under that objective the earlier answer does not apply.** Being re-tested.
3. **PLAYING TOO CLOSE TO THE LINE.** Is there a minimum absolute distance to the strike below which we should never trade, regardless of what the model says?
4. **CAP 3 vs CAP 2.** Cap 3 measured better (12% more money, a third of the ruin) and is currently OFF only because the bank cannot fund its brake. Restore it at ~$150.
5. ~~SNAPSHOT BUG~~ **FIXED 2026-09-10, verified 2026-09-12** — reads `yes_dollars_fp`; tape snapshots carry levels wherever a book exists. Not the divergence.

---

## WHAT IS SETTLED, DON'T RE-LITIGATE

- Settlement = mean of 60 one-second prints over `[close-60, close-1]`. Reproduced on 9,124 of 9,124 markets.
- Fee = `ceil(0.07·p·(1−p)·n, $0.0001)`. Makers pay zero.
- **In a decided market the losing side's book is EMPTY** — 33,427 of 33,431 moments. That is why we miss closes, and no threshold change fixes it.
- Market impact does **not** block scaling: 10 → 125 contracts keeps 10.2–11.3× of the naive 12.5×. **Capital is the constraint.**
- Cheap prices win more *and* lose less. Break-even at 90¢ is a 10% error rate; at 98¢ it is 2%.
- **Price and risk are different things.** Our dearest trade (98.7¢) was our safest (0.001% model risk).

---

## HOUSE RULES

- Never deposit, never margin, never borrow. Say when funds are needed.
- Never claim an unmeasured result. Report failures, don't estimate.
- A bar is never moved after seeing a result without saying so loudly.
- **Argue with Joe.** He has asked not to be agreed with by default.
