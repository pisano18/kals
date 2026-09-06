# OVERNIGHT — 2026-09-06

## Read these five lines first

1. **THE SELF-TEST GATE IS WEAK, AND THAT WAS THE MOST IMPORTANT FINDING.**
   Mutation-tested `pin` and `informed` the way lens 2 did `queuesim`: **pin's
   self-test kills 33% of deliberately wrong estimators, informed's 40%.**
   Fees abolished entirely, walk-forward replaced by in-sample fitting, MDE
   understated 4×, the null band widened to infinity — all SURVIVED. **But I
   then verified all five properties directly and the shipped code is correct
   on every one.** The number stands; the *guarantee* does not.
2. **`pin` SURVIVES and the race is answered in its favour.** Quotes live a
   median **0.70–0.82 s**; 41–45% are never taken. And the 282 ms lag is
   **Kalshi's ticker channel, not our overhead and not clock skew** —
   `orderbook_delta` delivers the same information in **47 ms**. Reading from
   there we win **~88% of races and keep ~91% of the money**.
3. **WHAT CHANGED — the collector now records the five commodity 15-minute
   series**, which are the ones Kalshi's incentive program actually pays for.
   File deployed to `C:\kals`. **THE RESTART WAS BLOCKED and has not happened**
   — see "Needs you", item 1. They trade 18:00–23:45 ET so there is margin.
4. **WHAT NEEDS YOU** — the collector restart (blocked), and the PREREG is now
   complete enough to sign: $250 accepted, and the MDE section you asked for is
   in as §5b.
5. **WHAT I COULDN'T DO** — **NEW DIRECTIONS and RISK/REWARD never ran; both
   died on the session limit, not by my choice, and I failed to say so.** So did
   the tie audit, the API job, the stage suite, relative value, early exit and
   both adversarial passes: **10 of 17 agents across the two workflows errored
   out.** Nothing ran twice.

---

## 0. MUTATION TESTING — the gate, tested against itself

| stage | applied | killed by the self-test | **survived** | kill rate |
|---|---|---|---|---|
| `pin` | 9 | 3 | **6** | **33%** |
| `informed` | 5 | 2 | **3** | **40%** |

**Survivors — bugs the gate would not have caught:**

- `pin`: **fees abolished entirely** (pin's edge is fee-*netted*)
- `pin`: **walk-forward replaced by in-sample `evaluate`** — the out-of-sample
  claim is the whole result and nothing tests it
- `pin`: **null band widened to infinity**; **MDE understated 4×**; **edge
  overstated 0.5c**
- `informed`: **every cell mean inflated 50%**; **the 30-cluster floor removed**
- `informed`: **"every group counted as monotone"** — that is the sweep shape
  test I wrote *today*; my own contiguity check masks the monotonicity check

**A surviving mutation means the test would not catch that bug — not that the
bug is present.** So each was then checked directly:

| property | direct check | result |
|---|---|---|
| fees charged | hand-recomputed 400 trades; `fee_cents(0.96)=0.2688c` vs `0.07·0.96·0.04·100` | **0 mismatches**, 0.187c drag/trade |
| walk-forward out of sample | truncate input to closes ≤ i, re-run, compare k at close i | **9/9 identical**, 207 past trades bit-identical |
| null band finite | mid-null [−3.41, +0.46], width 3.87c | sane |
| MDE arithmetic | `3·9.391/√336 = 1.537c` | matches `mde()` exactly |
| edge floor binds | four floors | min edge > floor each time |

**A FALSE ALARM OF MINE, RETRACTED.** My first look-ahead test scrambled
outcomes after close index 150 and reported LOOK-AHEAD from 10/20 refits
differing. The test was wrong — `warmup=150, refit_every=10`, so refits at 160,
170… legitimately consume closes inside the scrambled region. The truncation
test above is the correct one and it is clean.

**What this costs:** the project's epistemic claim is "we have not fooled
ourselves because of the self-test gate". That claim is now much weaker than
believed. Strengthening these self-tests is the highest-value engineering work
available, and it is not done.

## 0b. THE 282 ms, DECOMPOSED

| candidate cause | test | verdict |
|---|---|---|
| clock skew | `w32tm /stripchart` vs NTP | **−2 to −6 ms. Eliminated.** |
| collector overhead | compare channels by volume | **Eliminated — see below** |
| Kalshi's own publication delay | what remains | **This is it** |

| channel | messages | min | median lag |
|---|---|---|---|
| `ticker` | 127,812 | 29 ms | **326 ms** |
| `trade` | 649,236 | 10 ms | **46 ms** |
| `orderbook_delta` | **13,498,096** | 22 ms | **47 ms** |

The **heaviest** channel is the **fastest**, so it is not our overhead. `pin`
detects from `ticker` today; the same information is in `orderbook_delta`.
**Real reaction time ~82 ms, not ~320 ms.**

## 0c. RACE ADVERSE SELECTION — favourable

`corr(survival, edge) = +0.136`, `corr(survival, pnl) = +0.072`. **We lose the
low-edge races, not the good ones.**

| latency | races won | $/day | vs ideal |
|---|---|---|---|
| 100 ms (`orderbook_delta`) | 88% | $30.54 | **91%** |
| 320 ms (`ticker`) | 77% | $31.25 | 94% |
| 1.0 s | 59% | $23.76 | 71% |

## 0d. THE tau≤60 MDE CAVEAT — answered

The caveat *"the tau≤60 one-per-close base is below its own MDE, so multiples on
it are a multiple on a non-result"* **does not transfer to the every-market
headline**, and here is the structural reason, measured:

| tau≤60 | n | median tau | mean edge | mean P&L |
|---|---|---|---|---|
| one-per-close | 713 | **59 s** | 1.24c | **0.25c** |
| every-market | 2,641 | **45 s** | 1.91c | **0.81c** |

`rule="first"` takes the *earliest* qualifying second, so at tau≤60 one-per-close
sits at the boundary where the variance collapse has not happened. Different
populations; the non-result does not contaminate the headline.

**The real caveat, stated instead:** tau≤60's money comes from **volume, not
edge quality** (0.81c vs 2.49c at tau≤20). That makes it more exposed to
latency, fees and slippage error than tau≤20 is.

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

1. **THE COLLECTOR RESTART — BLOCKED, and it is the only thing on a clock.**
   `kalshi_collector.py` now lists the five commodity series and is deployed to
   `C:\kals`, verified identical to the repo. **But stopping the running
   process was refused by the permission classifier, so the change is on disk
   and NOT live.** The watchdog respawns within 300 s, so this restores it:

   ```powershell
   Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object {$_.CommandLine -like '*kalshi_collector.py*'} |
     ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   ```

   Then verify: `python research\newseries.py --data C:\kals\kalshi_data`.
   The commodity markets open **18:00 ET**, so it must be live before then.
   Cost of the restart: up to 5 minutes of crypto tape.

2. **`PREREG_pin.md` is now complete enough to sign.** $250 accepted and
   recorded as *not* the binding constraint; §5b gives the MDE you asked for;
   §5c states the regression to expect. Two numbers to know before signing:
   500 closes detects a **halved** edge with only a **1.09× margin**, and a
   **quarter** edge needs **1,674 closes ≈ 22.5 days**. At 74.3 closes/day the
   500-close window is **~7 days**, not 13.

3. **Nothing else.** No orders placed. No money moved. The account is unfunded.

## Not done, and why — nothing silently dropped

**Died on the session limit (reset 09:40), not deprioritised by me:**

| agent | workflow | status |
|---|---|---|
| NEW DIRECTIONS | 1 | **errored — session limit** |
| RISK/REWARD | 1 | **errored — session limit** |
| JOB B tie-audit | 1 | errored |
| JOB C API | 1 | errored |
| JOB D stage suite | 1 | errored |
| adversarial-1, adversarial-2 | 1 | errored |
| relative value | 2 | errored |
| early exit | 2 | errored |
| adversarial-rescope | 2 | errored |

**10 of 17 agents errored.** I reported the workflows as "running" and did not
check the failure list — that is the reporting failure, and it is mine.
**Nothing ran twice.** The fee/API question was assigned to both workflows
(`jobC:api` and `fees-rebates`); `jobC:api` errored, so only one completed.

**Not started by me, from the current list:**

- **D — the rebate's sharing formula, obligations, and our realistic slice.**
  The single highest-value item remaining. Not started.
- **E — the cross-venue accounting** of what was ruled out *without* checking.
  From the report: Deribit, Binance (451), Bybit (403), Robinhood and
  Polymarket-US-crypto were all *checked*. **The sports overlap was NOT priced**
  — the agent ran out of time building the ticker map, and it names it as the
  most promising unexplored branch, better than weather on event identity.
- **Strengthening the self-tests** that mutation testing just showed are weak.

## Resource state

| | |
|---|---|
| free disk | 52.0 GB |
| free RAM | 3.3–3.6 GB of 15.8 GB, never below 3.3 |
| `kalshi_collector.py` | **UP** throughout, pid 2708908, ~25 MB |
| `crypto_feeds.py` | **UP** throughout, pid 531268, ~14 MB |
| OOM kills tonight | 1, early, mine — two processes each holding a full `load_quotes`. Fixed structurally by pre-building shared caches. Collectors were never at risk. |
