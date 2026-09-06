# OVERNIGHT — 2026-09-06

## Read these five lines first

1. **WHAT DIED — the queue simulator's market-making number.** It said
   $195–309/day from ONE contract resting per side. Three adversarial refuters
   ran; **two REFUTED it, one partially.** The kill: a quote that always joins
   the **back** of the queue was earning **2.0× the per-contract rate of the
   flow it stands in**. A back-of-queue order's fills are a *subset* of at-touch
   flow — that subset can earn the same or less, never double. **Do not spend
   against that number.**
2. **WHAT SURVIVED — `pin`, and the race question is now ANSWERED in its
   favour.** I was wrong that it was unmeasurable. Quotes survive a **median
   0.70–0.82 s**; 41–45% are never depleted at all. Our full reaction time is
   **~320 ms** (282 ms feed lag + 35 ms order round-trip). **~80–85% of races
   are winnable.**
3. **WHAT CHANGED — the best money found tonight needs nobody to be wrong.**
   Kalshi runs a **Liquidity Incentive Program** that pays makers for *resting*
   orders whether or not they fill. It is live on 15-minute families, and the
   12 crypto series this project has worked on for weeks are the **only**
   15-minute family with **no** program at all.
4. **WHAT NEEDS YOU** — `PREREG_pin.md` is drafted and unsigned; the incentive
   program's pool-sharing formula needs one more check before it is money; the
   $50 live test is designed only if you want it. See "Needs you".
5. **WHAT I COULDN'T DO** — the race adverse-selection join was still running
   at write time, and JOB D (full stage suite) had not started. Both named
   below with status. Nothing was silently dropped.

---

## 1. THE RACE — answered, and I was wrong to call it unanswerable

I said twice that the race for a stale quote could not be measured from
recordings. That was habit, not fact. `orderbook_delta` carries **microsecond**
timestamps, a sequence number and a signed `delta_fp` per price level, so the
life of the exact level `pin` wants is directly reconstructable.

**Quote survival, 335 of 336 `pin` entries traced, 9,569 deltas:**

| to fill | p10 | p25 | median | p75 | p90 | never depleted |
|---|---|---|---|---|---|---|
| 10 contracts | 0.058s | 0.197s | **0.777s** | 1.246s | 2.413s | 45.3% |
| 30 contracts | 0.084s | 0.312s | **0.696s** | 1.264s | 2.323s | 43.6% |
| 50 contracts | 0.083s | 0.310s | **0.816s** | 1.264s | 2.323s | 41.4% |

**Our real reaction time is not 35 ms.** Measured on this box:

| stage | median | p75 | p90 |
|---|---|---|---|
| ticker websocket delivery lag (`_rx_ms − ts_ms`, n=375,927) | **282 ms** | 601 ms | 984 ms |
| order round-trip, read-only GET × 12 | ~35 ms (min 29, max 199) | | |
| **total** | **~320 ms** | ~640 ms | ~1.0 s |

Against the survival table: **87.7% of levels survive 0.25 s and 78.6% survive
0.50 s.** So we win roughly **80–85%** of races at median latency, ~73% at p75.

**Caveat that cuts both ways:** the 282 ms is *our collector's* lag — it is
gzip-compressing and writing to disk in the same process. A purpose-built order
client would be faster by an unknown amount. That is exactly what a live test
would measure and nothing else can.

**Still running at write time:** whether the races we LOSE are the *good* ones.
If high-edge quotes vanish fastest we keep the dross, and an 85% win rate would
not mean 85% of the money. Result appended when it lands.

## 2. `pin` — in your units, not mine

`$/day at 50 contracts` was my framing and it was wrong for your capital.

| rule | peak concurrent capital | $/day | % return on peak capital/day |
|---|---|---|---|
| tau≤20, one-per-close, cap 50 | **$49.70** | $30.22 | **67.2%** |
| tau≤60, every-mkt, cap100/frac0.25 | $268.01 | $88.10 | 37.7% |

**Risk, measured properly.** My first attempt flattered us: a close-level *iid*
bootstrap said the 1%-worst week was **+$47**. That is an artefact — resampling
closes independently destroys the one mechanism that makes a real bad week, a
session where the model is wrong across many closes at once. Redone as a **block
bootstrap over whole days**:

| rule | days | negative days | worst day | mean/day |
|---|---|---|---|---|
| tau≤20 one, cap 50 | 10 | **1** | −$18.30 | +$30.22 |
| tau≤60 every-mkt | 11 | **0** | +$10.47 | +$88.10 |

5-day week resampling **days**: 1%-worst **+$27**, 5%-worst **+$65**, 0.3% of
weeks lose money. **Your $150 bad-week limit does not bind. Depth binds.**
Stress arithmetic by hand: a flip costs ~$38 at cap 50, so $150 needs **4 flips
in a week**; observed rate is 1 in 263 → λ≈0.7 per 185-close week → **P(≥4) ≈
0.5%**. **But 10 days contains no crash. This measures variance, not tail.**

**A better size rule was found.** Capping at a *fraction of the touch* removes
the race assumption structurally instead of hoping:

| tau≤60 every-market | $/day | 95% interval | maxDD | eats whole level |
|---|---|---|---|---|
| cap 50, frac 1.00 | 83 | [+40, +122] | $115 | **46%** |
| **cap 100, frac 0.25** | **101** | **[+65, +143]** | **$51** | **0%** |

It earns *more* because it sizes up on deep books and down on thin ones, and
per-contract edge does not decay with depth. This is the rule in `PREREG_pin.md`.

## 3. THE QUEUE SIMULATOR — refuted, and the refutation is the finding

JOB A built `research/queuesim.py` (self-test green, 26 checks) and reported
market-making clearing every threshold at every size — 20 cells, 20 passes,
$195–309/day from one contract per side. Three Opus refuters attacked it.

- **Lens 3 (statistics): REFUTED.** Reproduced the headline *to the cent*, then
  killed it on weighting. The report's central artefact check compared a
  close-clustered mean against a close-clustered population; weighted the way
  the money is actually made — pooled, per contract — our fills earn **+0.76c
  against a population +0.43c at S=1, and +0.94c vs +0.43c at S=50**. That is
  **~2.0× the population rate, at every size.** A back-of-queue quote cannot do
  that. Close-clustering is right for a *t-statistic* and wrong for a
  *reconciliation*, and the error hid the artefact it was built to find.
- **Lens 2 (self-test): REFUTED.** Planted 20 deliberately wrong estimators;
  **14 passed all 26 checks**, including three that reverse or multiply the
  headline money and one that deletes the null control. The entire cancel-policy
  block is never executed by the self-test. It found no bug in the shipped code
  — it found that the self-test would not tell us if there were one, which is
  precisely what CLAUDE.md says the self-test exists for.
- **Lens 1 (fill model): PARTIALLY REFUTED.** The fill engine survived every
  attack, rebuilt independently on the deci-cent grid. Two of three validation
  claims did not survive; 3–8% of the money comes from a tick zone the report
  claimed to exclude.

**Verdict: market-making is UNRESOLVED, not proven.** The +0.48c per-fill edge
from `informed.py` is untouched by this — what is refuted is the *capacity*
number built on top of it.

## 4. FEES AND REBATES — the best thing found tonight

**`GET /incentive_programs` (live API call) returns a per-market, per-15-minute
reward pool. Kalshi pays makers for RESTING orders whether or not they fill.**

| family | reward/window | target size | windows/day | pool/day | already recorded? |
|---|---|---|---|---|---|
| `KXCRYPTOLEAD15M` (Coin Race) | $20.00 | 1,000 | ~52 | **~$5,200** | **yes** |
| `KXGOLD15M`/`SILVER`/`WTI`/`NATGAS`/`COPPER` | $20.00 | 300 | 24 each | ~$2,400 | no |
| `KXBTC15M` + 11 crypto siblings | **none** | — | — | **$0** | yes |

**The twelve series this project has spent weeks on are the only 15-minute
family with no incentive program at all.**

This is money that does not require anyone to be wrong — you are paid for
posting depth. **It is not yet money, and here is what stands between:** the
pool is *shared*. $20/window is the pool, not our cut; our share depends on our
depth against everyone else's, with a target size of 1,000 (Coin Race) or 300
(commodities). At $1,000 of capital we cannot post 1,000 contracts. **The
sharing formula is the next check and it decides everything.**

Contradiction 3 is settled: `KXINX15M` and `KXNDQ15M` both return 200 OK.

## 5. CROSS-VENUE — no money, and the reason is worth knowing

**Money found: none.** Not "none reachable" — none.

- Kalshi `KXBTC15M` ↔ Polymarket `btc-updown-15m` is a genuine same-event
  overlap: **99.00% outcome agreement over 1,198 matched windows**, with 100%
  of disagreements in windows moving less than $5. **You cannot legally trade
  it from a US IP.**
- The one legally reachable overlap (Kalshi vs Polymarket US, daily high
  temperature) is **arbed out: mean net edge −2.53c.**
- The apparent crypto gap **turned out to be our own data going stale**, twice,
  in opposite directions.

Two keepers: **Kalshi's REST `/markets` quote fields are stale by tens of
seconds — wrong by up to 17 cents**, verified against Kalshi's own candlesticks
(a hazard for any live monitoring). And **Polymarket US pays makers
`0.0125·p·(1−p)` where Kalshi pays zero** — +0.31c per contract at 50c,
unconditional.

## 6. Bookkeeping — thresholds moved twice, loudly

`CLAUDE.md` now carries three dated versions of the kill criteria with the
reason each changed: +$50/day (original, pre-measurement) → positive with
tolerable drawdown (revised after seeing the number) → **positive expectancy**
(your definition of "consistently"). **No measurement was ever re-run, re-fitted
or re-weighted. Only the question moved.** Under the final definition `pin` is a
PASS and was all along.

Also fixed: `pin.py`'s `portfolio()` hardcoded **96 closes/day**. It now uses
the measured fire rate. That constant overstated the four published portfolio
figures by **1.73× to 3.91×**.

---

## Needs you

1. **`PREREG_pin.md` — drafted, UNSIGNED, clock not started.** The survival
   result supports signing it. §5 needs your drawdown number; my proposal is
   $250 (≈5× observed max, ≈2.5 days of P&L).
2. **The incentive-program sharing formula.** If our share at a few hundred
   contracts is meaningful, this is the most reliable money on the table and it
   points at Coin Race and the commodity 15-minute families, not at crypto.
3. **The $50 live test.** The race is ~85% won on recordings, so it is no longer
   *needed* to answer the question — but it is the only way to measure a real
   order client's latency versus our collector's 282 ms. I have not designed it
   because it is no longer the blocker. Say the word and I will.

## Not done, and why

- **Race adverse-selection join** — running at write time; the scan re-reads 277
  delta files. Appended when it lands.
- **JOB D, full stage suite** — not started. It is last in the workflow by
  design and the queue-sim refutation makes re-publishing less urgent.
- **JOB B tie-audit, relative value, early exit, constraint audit** — agents
  running; reports land in `results/overnight/`.
- **The $50 live-test design** — deliberately not written; see above.

## Resource state

| | |
|---|---|
| free disk | 52.0 GB |
| free RAM | 3.3–3.6 GB of 15.8 GB, never below 3.3 |
| `kalshi_collector.py` | **UP** throughout, pid 2708908, ~25 MB |
| `crypto_feeds.py` | **UP** throughout, pid 531268, ~14 MB |
| OOM kills tonight | 1, early, mine — two processes each holding a full `load_quotes`. Fixed structurally by pre-building shared caches. Collectors were never at risk. |
