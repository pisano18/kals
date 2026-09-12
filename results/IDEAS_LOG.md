# Ideas log — every idea, what testing it got, what happened

**Purpose: nothing gets lost in fast conversation.** Every idea raised, by
either of us, with its evidence and current status. Update this whenever an
idea is raised, tested, deployed or killed.

Status key: **LIVE** · **TESTED-REJECTED** · **TESTED-PROMISING** (works but not
deployed, with the reason) · **PARTIAL** (tested but not conclusively) ·
**UNTESTED** · **DEAD** (structurally impossible)

---

## LIVE — deployed to real money

| # | idea | evidence | version |
|---|---|---|---|
| 1 | **Edge floor 0.5¢ → 0.3¢** | OOS: 389 closes / +2.76¢ / t=+5.6 / 1 flip in 359, vs 354 / +2.51¢ / t=+4.1 / 3 in 333 | v1 |
| 2 | **EV gate — price ceiling from the MEASURED flip rate** *(operator: "is it even worth doing trades above .99c")* | 5 of first 7 trades were negative-EV. Breakeven price = 1−f = 99.1¢. Profit/trade 1.41¢ → 3.42¢ | v2 |
| 3 | **Scale in as price improves** *(operator)* | 4.18¢ → 7.43¢ per close at cap 2; avg price paid FELL 95.53¢ → 94.60¢ | v3 |
| 4 | **Window 20s → 30s** | Model calibration by horizon: 0 flips in 5,219 moments under tau 30; 3.7× overconfident at 31–45; 10.9× at 46–60 | v4 |
| 5 | **Size 1 → 3 → 8** | Depth median 125 contracts at the touch; we were using ~2% | v5/v6 |

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

## MEASURED 2026-09-12 — the hedge, the maker kill, and the hunt (agents: Opus grunt work, Fable design)

| # | idea | verdict | evidence |
|---|---|---|---|
| 13 | **AMENDMENT 15 — hedge on belief collapse** | **LIVE at full size, 0.90** | 72h unseen holdout: 4 of 4 losers caught with 13–19 s to act, 68.2¢/contract recovered, one $0.77 false alarm, P&L $31.52 → $76.40 (ceiling). Live bar at n=30 in PREREG_hedge.md. |
| 14 | One-contract hedge PILOT on real positions | **REVERSED — my misreading** | Operator meant a planted test, not a cap on real hedges. Ran 30 min, no event. |
| 15 | **Planted one-contract hedge test (`--hedge-plant`)** | **ARMED, one-shot** | Buys 1 contract of the losing side of a decided market, lets the live hedge fire. Costs cents. Operator's design. |
| 16 | **Rest a bid instead of taking (maker, zero fee)** | **KILLED** | Per close −$0.36 vs TAKE, t = −5.8; a resting bid fills 100% of losers, 29% of winners. Third time per-contract reversed per close. |
| 16b | **Entry-time features (offer age/size/freshness, pre-entry jumps, margin-sd)** | **CLOSED — null on the book/index; margin-sd is tautological and every gate costs 33–94% per close** | 409 tradeable entries / 7,328 model-certain; 5/4-day split; control (price) survives the same test → method rejected; RESULTS_entry.md |
| 16c | **SOL / per-coin gate** | **NOT PROVEN; pre-registered 30-close test instead (PREREG_coin.md)** | SOL 3 of 14 closes vs 1 of 101; worst-of-nine p = 0.060; "calmest feed" was a 0.01-step quantization artefact; the NEAR triple was ONE close; RESULTS_coin.md |
| 17 | **COUNT is the lever** | **UNTESTED, queued** | Offer exists on 9.6% of confident markets, 51.8% of confident closes. |
| 18a | **Fidelity harness on our 207 real fills** | **DONE — diagnosis in hand** | pinsim.run() buys 112/207 of our fills and 1/9 losses; at the decision ms under the live gate 178/207. Causes: gate change (51 refusals), once-a-second sampling (78→156 exact price), snapshot merge order (31c vs 0c). Trade channel has holes: counts are lower bounds. |
| 18 | **Backtest rebuild** | **IN PROGRESS** | Fidelity harness on our ~180 real fills (pinreplay.py, Opus). Then event-driven replay (evaluate after every delta, not once per second) — Fable design. |

**Stale item corrected:** the "snapshot bug" was fixed 09-10 and verified 09-12; not the divergence.

---

## MEASURED 2026-09-11 — THE COIN RACE, end to end (full detail: results/RESULTS_coinrace.md)

| # | idea | verdict | evidence |
|---|---|---|---|
| 9 | **Coin Race settlement rule** | **SOLVED** | Highest (close 60s TWAP ÷ open 60s TWAP). Reproduces Kalshi's own `expiration_value` on **773 of 773** events. The spot-at-open alternative gets 92.2%, so the rule is pinned, not guessed. The denominator is known when the window OPENS. |
| 10 | **Name the leader before the close** | **WORKS** | 91.5% at tau 60, 97.8% at tau 30, **99.5% at tau 20**, 100% at tau 5, on 773 events against a 20% base rate. 98–100% on each of nine separate days. |
| 11 | **Buy the named leader** | **REAL BUT SMALL — penny test, not deployment** | Edge per contract by tau: −0.18c (45–61), +1.22c (30–45), +2.56c (20–30), +2.52c (15–20), **+4.72c (10–15)**, **+4.83c (5–10)**. Roughly **$5–10/day at size 20**, on 6–10 opportunities. |
| 12 | **Stand aside unless the leader is cheap** | **TESTED-REJECTED — it is the discount cliff again** | Per contract it climbs −0.18c → +3.61c → +7.91c → +9.12c → +10.11c as the limit falls 98c → 80c. The loss rate climbs **10.6% → 35.1%** alongside it. Cheap legs are cheap because they lose. |

**The mechanism, and it is clean:** the market charges 89.07c at tau 45–61 for
something worth 89.4% — efficient to within the fee. The edge exists only in
the last 30 seconds and grows toward the close, because our information
hardens as prints lock in and the quoted price does not harden as fast.

**TWO BUGS CAUGHT IN THIS MEASUREMENT, both of which INFLATED it:**
1. **Look-ahead** — v1 scored tau-45 purchases against the tau-20 forecast,
   30 seconds of future index prints away. Claimed 98.9% where the truth is
   89.4%. Fixed, and a self-test now asserts for every tau that the forecast
   used is never from the future.
2. **Tau runs backwards** — the "first print in the band" rule used `min()` on
   tau, which is the LAST trade before the close, the most informed and the
   dearest. Claimed 98.6% at tau 20–30 where the truth is 93.6%. Fixed.

Neither was visible in the output table. Both were found by asking why a
number was that good.

**THE CAVEAT THAT SURVIVES: never quote the 99.5%.** We can only buy when
somebody is trading, and those are the closer races — accuracy in the
tradeable subset is 89.6–97.5%, not 91.5–99.6%. Coverage is 6–18% of events.

---

## MEASURED 2026-09-11 — the discount cliff, on 45,287 REAL fills (48h, 144 closes)

**The instrument changed, and that is the lesson.** Every earlier loss-rate
answer came from replaying the ORDER BOOK, which is blind to the population we
care about: it records "an offer was resting there", never "someone shoved an
offer at us". The **TRADE TAPE** (`research/pintrades.py`) prints `taker_side`
on every execution, so the taker's discount and outcome are directly
observable. No reconstruction, no fill assumption.

| # | idea | verdict | evidence |
|---|---|---|---|
| 6 | **Refuse "crazy deals" ≥15¢ under fair** (A10c, LIVE) | **CONFIRMED, kept at 15¢** | The refused band is 329 trades / 13 closes / 18,648 contracts, **31.31% lost [26.33, 36.62], −6.51¢/contract, −$1,213.60**. Monotone across 7 bands. |
| 7 | **Move the guard to 25¢** (where the true cliff is) | **TESTED-REJECTED, deliberately** | 15–25¢ is **+0.17¢/contract = break-even** on 165 trades / 11 closes. Loosening buys ~nothing and moves us next to the −17.10¢ band. Not worth it on 11 closes. |
| 8 | **Be more patient — hold out for a 5–15¢ discount** | **KILLED by per-close arithmetic** | Per CONTRACT it looks 16× better (+6.45¢ and +7.51¢ vs +0.38¢). Per CLOSE it is worse at every threshold: $0.576 → $0.506 (≥2¢) → $0.351 (≥5¢) → $0.102 (≥10¢), because we'd trade 143 closes → 72 → 33 → 6. **Fewer dollars AND a higher loss rate (0.22% → 4.87%).** |

**The methodological rule this produced, which outlives all three:**
**A PER-CONTRACT TABLE MUST BE RE-ASKED PER CLOSE BEFORE IT CHANGES A RULE.**
Idea 8 survived the first table and died on the second. Rarity is invisible in
a per-contract column and it is usually the bigger term.

**What the 48h run changed vs the 10h run:** the 15–25¢ band, which looked
catastrophic on 2 closes (−22.24¢) and is break-even on 11 (+0.17¢). The 10h
caveat — "the magnitude rests on few events" — was right, and the correction
landed exactly where it warned.

**LEVELS ARE NOT OURS.** These are other people's fills; the RANKING is the
result, the dollar level is not. Per house rule **no loss rate for us is ever
quoted from the tape** — ours come from live fills only.

---

## MEASURED 2026-09-10 — the loss-rate hunt, everything proven good or bad

Operator: *"see if you can think of or try anything to improve our lose rate
problem"* and *"make sure anything proven good or bad and anything worth
knowing in the pursuit of the solution is logged."* Commit `2994b55`.

| # | idea | status | evidence |
|---|---|---|---|
| A | **Count flips on the tradeable population and split by conditions** (`pincross.py`) | **DEAD as a method** | The whole tape holds **254 tradeable markets / 147 closes / 2 flips**. MDE stated before looking: +3.34pp. Observed +2.50pp. **Shuffled control gave +2.78pp — larger than the signal.** No power, not no effect. Any factor study that counts flips on this tape is hopeless, whatever the factor. |
| B | **Measure the forecast error instead of the flip** (`pintail.py`) | **TESTED-PROMISING — the right instrument** | One real number per market: `(settle − mu)/sd`. 9,159 markets / 1,019 closes. Settlement model reconciled to 3.8e-07 first. The gate's flip rate is exactly the tail beyond 2.0537 sd, so this measures the loss rate directly, from every market, not from the 2 that flipped. |
| C | **The model's tail is too thin and it is STATE-DEPENDENT** | **PROVEN (well powered)** | mean error 0.657 sd vs 0.798 claimed; losing-side tail **2.58% [2.26, 2.92] vs 2.00% claimed**. By other coins moving: 0 → 2.22%, 1 → 3.92%, 2 → 5.22%, 3–5 → 6.60%. Permutation over closes: mean-error lift on cross-market roughness **p=0.0070** (survives the 6-look threshold of 0.0083); the loss-tail lifts at p=0.025–0.068 do not. Control clean (p=0.44). **The model is wrong in SHAPE, not scale.** |
| D | **A fixed gate on those conditions** (9 thresholds, fit/holdout 70/30) | **TESTED-REJECTED** | Every candidate that gains on the fit half **loses on the holdout**: N≥1 +18.5% → **−18.0%**; X≥1.4 +16.3% → **−8.4%**; N≥2 +11.3% → **−6.6%**; N≥3 +4.1% → −2.3%. The one positive holdout (own≥1.4, +4.7%) was negative on fit — noise flipping sign. **Not deployed. Deploying it would be curve fitting.** |
| E | **Discount-to-fair as adverse selection** (`pindisc.py`, Fable 5.1 in parallel) | **TESTED-REJECTED at live size, PARTIAL below ~10%** | Within price band, high-discount vs low: **0 flips in 73 high-discount closes.** P(0/73 given the live-implied 25%) ≈ 7e-10. Power 0.14 at a 2% effect, 0.74 at 10% — small effects are invisible here. The two tape flips: one on a 36 ms quote, one on a **62.5 s stale quote with 2,024 contracts resting** (the adverse-selection shape, n=1). |
| F | **Live sigma ≠ backtest sigma** (sd-about-mean vs RMS) | **TESTED-REJECTED — and I predicted it wrong** | Same 9,159 seconds: ratio median **1.0008** (5th 0.9938, 95th 1.0017); tails 2.58% vs 2.57%. I asserted live is provably ≤ RMS; my own check returned 35.9% because dividing by (n−1) cancels the mean subtraction. |
| G | **THE FACT THAT REFRAMES IT** | **PROVEN** | Backtest tradeable population flips **0.79% [0.10, 2.82]**; live **8.8% [2.9, 19.3]** (5/57). **The intervals do not overlap.** The cause of the live losses is not in the tape at anything like the live rate. Six failed factor studies were this fact, not bad luck. |
| H | **Log the live conditions on every decision** | **LIVE** (v-cond, `2994b55`) | `cond_x` (the other ten coins' roughness, traded coin excluded), `cond_n` (how many > 2), `cond_own`. Self-tested exclusion. Logged, never gated on. ~70 fills distinguish a 25% problem from a 5% one. |
| I | **Sigma stress as a continuous function of state** instead of a threshold — `SIGMA_STRESS` already exists in pinrun and is 1.0 | **UNTESTED — next idea** | D killed thresholds, not the signal. A tail-matched stress per state (s = −2nd percentile of z / 2.0537, fitted on the fit half, checked on the holdout) would make the 0.98 gate self-adjust with no new constant. Needs K per market (the DOGE 7-digit trap applies). |
| J | **Heartbeat record during exchange halts** | **UNTESTED — observability gap** | During Kalshi's nightly maintenance (halt until ~5am ET / 09:00Z, `trading_active: false` on all shards) the bot writes **nothing** — indistinguishable from a hang. A once-a-minute `alive` record would separate them. |

| K | **The crossing population** (`pinfirst.py`) — the bot fires at the FIRST second the gate opens, so measure the flip rate AT THE CROSSING, not over every gated market | **PROVEN — the right population** | 10,796 markets walked tau 30→3. At the 0.98 crossing: **18 flips / 9,159 = 0.20%**. Raising the gate to 0.995 → 10 flips at zero market-count cost (9,151 still reach it); holdout 3 → 1. |
| L | **Flip rate by MARGIN at the crossing** — the like-for-like with live fills (38% of ours sit at 2.05–2.30 sd) | **PROVEN, holds on holdout** | 2.05–2.3: **1.79%** [0.82, 3.38] (502 mkts / 354 closes); 2.3–2.6: **3.08%** (195); 2.6–4: 0.51% (594); **4+: 0 of 7,868** [0, 0.05%]. Fit → holdout: 2.51% → 1.38% [0.28, 3.97]; 0.74% → 0%; 0 → 0 of 2,500. **The model is calibrated at its own boundary (~2%) and never wrong deep inside.** Live boundary fills lost 3/32 = 9.4% [2.0, 24.7] — touches the tape interval, so not provably worse. |
| M | **Margin-aware EV gate** — replace the constant 0.9% flip in `expected_value()` with 2.2% below 2.6 sd, 0.5% to 4 sd, 0.05% above; the existing EV floor then sets the ceiling per margin (97.3¢ at the boundary, unchanged 98¢ cap elsewhere) | **TESTED — correct in expectation, NOT the fix, not deployed** | Applied to the 84 live fills: refuses **17 fills, all winners (+$3.21), and none of the 5 losses** — every loss was priced 73–96¢, below the boundary ceiling. It is the honest EV line but it does not touch the losses we actually had. The deep-market half (ceiling up to 99.6¢ where 0/7,868 flip) would add ~+0.4¢/contract of low-value volume and reverses the price-ladder call — operator's decision, not mine. |
| N | **THE XRP LOSS IS A SUB-SECOND LEAD, NOT A MODEL ERROR** (2026-09-10 05:00Z close) | **PROVEN on one event — the sharpest lead we have** | Hand-recomputed from tape: bot inputs correct to the last digit, +9.2 sd on YES at 04:59:39. At that same second the **CF index printed 1.39075 while Coinbase had already traded 1.38950** (Kraken 1.38989); the index followed one second later and fell ~10 sd over the last 20 prints. The market was selling YES at 82¢ *because it had seen the exchange tick*. Data ages were fresh (index 0.18 s, book 2 ms) — the CF print itself was stale inside its second. `feed_data` (Coinbase/Kraken ticks with ms receipt times, plus a 1/s replica) has this for the whole tape. **Next test: divergence of the freshest exchange tick from the CF print at the crossing second, in sigma, vs flip — `pinjump.py`.** |
| O | **The other two recent losses are plain boundary flips** (NEAR −2.10 sd, BNB +2.16 sd) | **PROVEN** | Both reconstruct exactly from tape; both at the model's own ~2% boundary rate (row L). No data error, no jump, no lead — the price of trading the boundary. |
| P | **Race selection on our own 319 live attempts** (`pinrace.py`) — do the orders we fail to fill win more? | **PARTIAL — no power** | Filled 5.95% lost (84), unfilled 1.28% (235 attempts but only 29 closes — 160 of them are the runaway close). Per close: 3/58 vs 1/29. Nothing distinguishable. |
| Q | **Live P&L reconciled** | **FACT** | All 84 fills with a known outcome since 09-08: **−$15.02** (bank $136.38 vs $151.87 in — reconciles). The "+$26.50 under current rules" excluded the −$52.60 NEAR close. |
| R | **Penny-size live tests** — operator authorised 2026-09-10: *"you can run as many live tests as you need with pennys"* | **AUTHORISED, none run yet** | Pennies test mechanics (fills, races, data paths), not rates — a 2% event needs ~150 fills to see once. Right use: a size-1 shadow of any new gate (row N) before it touches size 20. |

| S | **Exchange-tick veto** (`pinjump.py`) — at the crossing second, how far the freshest Coinbase/Kraken trade sits from the CF print, in sigma, signed against our side; refuse above k | **MECHANISM PROVEN on events, RULE NOT — not deployed** | 2,895 crossings scored on BTC/ETH/SOL/XRP/DOGE (feeds don't carry BNB/ZEC/HYPE/NEAR), 7 flips. Two of seven are XRP-shaped (BTC 08-27: fresh +10 sd, worst +19). "Worst tick ≥ 4 sd": 1.21% vs 0.20% baseline, **p=0.07**, stale control 0.48%. Freshest-tick rule at k=2: keeps 84%, removes 1 of 5 fit flips and **0 of 2 holdout flips**. Most flips are boundary drifts with no lead at all. Needs more flips; log the quantity live before gating on it. |
| T | **PIN 0.98 → 0.995** — AMENDMENT 9, the bar moved, dated 2026-09-10 08:35Z | **LIVE** (v-pin995) | Row L is the evidence: it excludes exactly the two bands that flip at 1.8–3.1% and keeps 2.6+ sd (0.5%, then 0 of 7,868). Tape 18 → 10 flips, holdout 3 → 1, 9,151 of 9,159 markets still reach it. Live: would have skipped 3 of 5 losses (NEAR ×2, BNB at 2.09–2.25 sd) and no deep win; kept 43 of 84 fills. **Cost unmeasured: fewer fills at higher prices is the expected shape.** Size, brakes, ceiling, window unchanged. Revert: one line. |

| U | **The forecast rebuilt on the new gate** (`pinproj.py`) | **DONE, replaces every earlier projection** | Bank $140.24. Measured: 97.0¢ paid, 50 fills/day, 0.51% loss (2.6–4 sd band, CI [0.10, 1.47]). **Size 125 cap on day 11, $142.50/day = $52k/yr.** Ladder gated by the brake: bank ≥ 3 losing closes × 2 buys × size × price. Old gate through the same model: higher ceiling ($360–474/day) but a **1.08× margin over break-even** and −$15.02 realised. New: **5.5× margin**. |
| V | **PRICE is a bigger lever than the gate** | **MEASURED, next work** | Same 0.51% loss rate: 97¢ → $143/day, 96¢ → $201/day, 95¢ → $259/day. The ZEC fill (93.3¢ at 3.05 sd) shows depth and cheapness are separable. Getting deep markets cheaper — patience, queue position, scale-in — beats any further gate tightening. |

| W | **Tool = control centre: play/pause/stop** (operator) | **SPEC'D, not built** | Control via `results/CONTROL.json` polled by `pinrun`, never a direct process kill and never the order API — keeps the SANDBOX rule intact. Pause must settle open positions, not abandon them (same class as the 09-08 stake leak). |
| X | **Run it on a Raspberry Pi** (operator) | **VIABLE, conditions logged** | Checked today: `pinrun` never reads `kalshi_data`/`feed_data` — trader and collectors are independent, so the trader can move alone on a few MB of disk. Collectors need **2.57 GB/day** and an SSD (SD cards die on sustained writes; the tape is unreproducible). Latency measured: p10–p90 82–119 ms, faster half fills 72.2% vs slower 67.6% on n=70 — no detectable effect **inside** that range, and no evidence about outside it. Validate in PAPER mode on the Pi first. |

| Y | **The sandbox must move RULES, not just assumptions** (operator, from the penny finding) | **SPEC'D, top of the tool build** | A slider over assumptions answers "if I assume X"; a slider over rules that re-runs the tape answers "if I had actually done X". The machinery exists: `pinfirst.py` finds the crossing at any gate level over 10,796 markets, `pindata_fixed` holds every tradeable moment. Must show FIT and HOLDOUT side by side on every result — the conditions gates were +18.5% fit / −18.0% holdout, and a slider tool without a holdout column would have shipped them. |

| Z | **Named profiles, saved from the sandbox and deployable from the tool** (operator) | **SPEC'D, good idea** | `profiles/*.json`, git-tracked; `default.json` is the live rule. Guards: deploy must run the self-test suite and range-check every field (an out-of-band `--loss-abort` once killed the process silently); loosening a brake needs the worst-case dollar figure shown and typed confirmation; the log records profile name + contents + hash (a name alone reintroduces the derived-field bug); switching = stop clean and restart, never mutate size mid-run. |
| AA | **The replay's one real deception: the fill assumption** | **KNOWN, must be on screen** | A replay hands us every resting offer; live we fill **70%** (50 of 72 attempts), so a naive replay overstates trades by ~43% and overstates most where the price is best. The sandbox must show "every offer ours" and "at 70% fill" side by side. Also: apply the impact curve rather than the touch price at size, honour `MIN_FILL_FRAC` so dust is not a position, and state how many markets were dropped for want of a settlement (10,796 of 14,161 have one). The replay is an UPPER BOUND and must be labelled as one on the screen. |

**Worth knowing, not a hypothesis:** the tape's tradeable population is thin —
about 51 tradeable markets a day pass today's rule. Any future test that needs
flips needs *months*, so measure forecast error (B), never flips (A).

---

## THE PRICE LADDER — measured 2026-09-09, and it is the biggest finding of the project

**22,568 model-confident moments, tau 3–60. The question: do CHEAP trades lose
more often, and does it matter?**

| price band | moments | closes | flips | flip rate | break-even | **margin** |
|---|---|---|---|---|---|---|
| 70–85¢ | 80 | 20 | 2 | 2.50% | 18.2% | **7×** |
| 85–93¢ | 356 | 70 | 9 | 2.53% | 9.1% | 4× |
| 93–97¢ | 1,330 | 98 | 26 | 1.95% | 4.2% | 2× |
| 97–98¢ | 2,087 | 117 | 15 | 0.72% | 2.0% | 3× |
| **98–100¢** | **18,712** | 132 | 99 | **0.53%** | **0.3%** | **LOSES MONEY** |

### Two findings, and the second one is alarming

**1. Cheap trades DO flip more often — and it does not matter.** They flip about
5× more (2.50% vs 0.53%), but their break-even is 60× higher. Net margin at
70–85¢ is **7×**; at 93–97¢ it is **2×**. **The cheap end is the SAFEST place we
trade, not the riskiest.**

**2. THE 98–100¢ BAND LOSES MONEY.** Flip rate 0.53% against a break-even of
0.30%. It is not marginal, it is negative — and it holds **18,712 of 22,568
model-confident moments, 83% of everything the model likes.** The vast majority
of what our model calls a good bet is a bet we should never take.

**This independently validates the 98.0¢ ceiling** deployed hours earlier on
Joe's recovery argument. That argument was arithmetic; this is the outcome data
agreeing with it from a completely different direction.

### What it implies, and it is not a gate

Our size is **constant regardless of price**. We stake the same on a bet with a
2× margin as on one with a 7× margin. That is backwards.

| | risk | reward | wins to recover a loss |
|---|---|---|---|
| a normal 96¢ trade, 20 lots | $19.20 | $0.80 | 25.8 |
| the 22¢ SOL trade, 200 lots | $44.00 | $156.00 | **0.30** |

**PROPOSED, NOT DEPLOYED: size inversely with price.** Bet large where the
margin is 7× and small where it is 2×. This follows from Joe's own recovery
argument and is arithmetic, not a fitted parameter.

**Before deploying it needs:** the frequency of cheap offers measured properly
(only 3 moments below 70¢ in 22,568 — the 22¢ SOL fill is genuinely rare), the
market-impact curve applied at larger size, and a bank that can fund the worst
case at the larger size.

### The trade that prompted this

2026-09-09 05:14:48Z, KXSOL15M. Model `fair = 0.0` (certain), edge 42.3¢, 200
contracts on offer. **Bid 56¢, filled at 22¢** — swept a resting offer 34¢
better than we asked. 20 contracts, $4.40 stake, **+$15.36, a 349% return.**

**It is the same shape as the trade that lost $52.60** — a deep discount on a
near-certainty, meaning violent disagreement with the market. Last night the
market was right; this time we were. **What differs is not our accuracy but the
price: at 22¢ we can be wrong 77% of the time and still profit.**

**We took 20 of 200 available.**

---

## MEASURED 2026-09-08 late — the hedge is WEAKER than I reported. Half of them are too thin to use.

### 32 | Is the hedge actually PURCHASABLE at the moment we need it? — **PARTIALLY. And that matters.**

This was flagged as the one unmeasured risk gating the hedge. It is now
measured for depth, and it cuts the benefit roughly in half again.

At a 90% trigger, for all **12 losers** in the wide window:

| | |
|---|---|
| a hedge existed at the trigger moment | **12 of 12** |
| deep enough for a **20-contract** position | **6 of 12** |

The six thin ones offered **1, 2, 6, 9, 1 and 1 contracts**. At our live size of
20 those are unusable.

**And the hedge is not cheap.** At a 90% trigger the other side costs **76¢ to
97.8¢**, not the "5 cent" price the idea was framed around. By the time the
model is 90% sure we have lost, the market has already repriced. Entering at
95¢ and hedging at 92.6¢ pays 187.6¢ for a $1.00 payout — a locked **87.6¢**
loss against an unhedged 95¢. It saves 7.4¢, not 90¢.

### The corrected benefit, and I overstated this earlier

| what I said | what it actually is |
|---|---|
| "cuts ruin risk 30×" (50% trigger) | true only if every hedge is fillable |
| "roughly halves ruin risk" (90% trigger) | **~16% loss-severity cut, and only usable half the time** |

Effective severity cut at size 20 is nearer **8%** than 16%, because half the
hedges cannot be filled at that size. **The 30× figure assumed unlimited depth
and should not be quoted.**

### What this does NOT change

- The **direction** is still right: hedging late is free, hedging early destroys
  a quarter of all profit. Idea #31's false-alarm table stands.
- Availability at the *trigger moment* is genuinely 12 of 12 — the hedge is
  never absent, only sometimes thin.

### Standing caveat on this measurement

`rows.jsonl` holds one row per **genuinely available** trade, so a moment with
no offer at all is simply absent from it. This can measure depth **where a
hedge existed**; it cannot prove one always exists. Settling that needs the raw
order book, and it is **not settled here**.

### Verdict

**Still not deployed, and the case is now weaker rather than stronger.** A
safety net with holes in half its area, saving 8% of each loss, is not worth new
live order-path code while the same effort could go at the race — which costs
us 26% of all orders and is worth far more.

---

## MEASURED 2026-09-08 night — the hedge, and what it costs the bets that were fine

### 31 | Buy the cheap opposite side when a position drifts — **WORKS, but only at a very late trigger**

The operator's idea, and then the operator's follow-up: *"check if it kills
profits on normal bets that would've been fine and how much that hurts us"*.
It does, badly, unless the trigger is late.

**FALSE ALARMS IN THE LIVE WINDOW** (tau 3–30, 165 positions, base 837.4¢,
**zero losers — so every hedge here is pure waste**):

| hedge once p(lose) reaches | false alarms | they cost | % of profit destroyed |
|---|---|---|---|
| 5% | 9 | 222.2¢ | **26.5%** |
| 10% | 8 | 214.0¢ | 25.6% |
| 20% | 4 | 139.8¢ | 16.7% |
| 35% | 3 | 119.7¢ | 14.3% |
| 50% | 1 | 55.7¢ | 6.7% |
| 75% | 1 | 64.6¢ | 7.7% |
| **90%** | **0** | **0.0¢** | **0.0%** |

**A 5% trigger destroys a quarter of all profit.** The operator's instinct to
check this was right and it would have been an expensive mistake to skip.

**AT A 90% TRIGGER IT NEVER FIRED ON A WINNER**, in 165 live-window positions,
while still catching **all 12 losers** in the wide window. *Caveat: zero in 165
is a small-sample zero. The true false-alarm rate is below roughly 0.6%, not
zero.*

### The break-even flip rate for the hedge itself

Cost measured on the LIVE window (what we trade); saving measured on the WIDE
window (the only place losses exist):

| trigger | cost/position | saving/loss | break-even flip rate | at our 0.90% |
|---|---|---|---|---|
| 20% | 0.847¢ | 43.5¢ | 1.95% | marginal |
| 50% | 0.338¢ | 32.6¢ | 1.04% | marginal |
| 75% | 0.392¢ | 25.9¢ | 1.51% | marginal |
| **90%** | **0.000¢** | **15.1¢** | **0.00%** | **PAYS** |

"Marginal" means it does not pay at the 0.90% we measured but does pay before
the **2.31%** exact upper bound we cannot rule out. **It is insurance against
our own flip rate being wrong, not a profit centre.**

### What it does to RUIN, which is the real reason to want it

$150, size 25, cap 2, 3,000 paths, losses drawn per close:

| if the true flip rate is | ruined, no hedge | ruined, 50% trigger | ruined, 90% trigger |
|---|---|---|---|
| 0.90% measured | 0.1% | 0.0% | 0.1% |
| **2.31% bound** | **3.0%** | **0.1%** | **1.1%** |
| 5.00% | 23.4% | 4.2% | 12.4% |
| 10.00% | 79.5% | 45.3% | 65.5% |

**The choice is a real trade-off, not a free lunch:**

- **90% trigger** — costs nothing measurable, roughly halves ruin risk.
- **50% trigger** — costs 6.7% of profit, cuts ruin risk **thirty-fold**.

### A bug found mid-analysis that had flattered the idea

`rows.jsonl`'s `price` is the ask on the **model-favoured** side, and the
favoured side changes as the index moves. The first version inverted it
unconditionally, so once the model switched it priced our *losing* side rather
than the one we wanted to buy. **The tell was impossible monotonicity: hedges
appeared to get CHEAPER the longer we waited** (43¢ at a 50% trigger, 21¢ at
90%), when insurance must get dearer as the fire spreads. Corrected, the wide
window benefit fell from +84% to **+26.4%**.

### NOT DEPLOYED — one unmeasured risk, and it is the important one

`rows.jsonl` holds one row per **genuinely available** trade, so it cannot say
how often the hedge is simply **not offered**. A hedge asks us to buy the side
that is now *winning*, and IDEAS_LOG #29 measured that the winning side has no
seller in **33,427 of 33,431** decided moments. All 12 losers were catchable in
this study, but that sample is selected on availability by construction.
**Measure hedge availability before building this.**

---

## MEASURED 2026-09-08 evening — the closes we miss are NOT missed profit

### 30 | Rest a bid instead of taking one, in the closes where nothing is offered — **TESTED-REJECTED**

Yesterday's answer to "the losing side's book is empty" was "then REST a bid
instead of taking one." Measured on **10,168 decided moments** across the eight
closes where the live runner could buy nothing, sampled on a 5-second grid:

| | |
|---|---|
| best bid on the WINNING side | **99.90¢** (median) |
| price levels quoted | 87 (median) |
| our break-even as a maker | **99.10¢** (no fee) |

**The market is already bidding 99.90¢, which is 0.80¢ BEYOND the price where
this trade stops making money.** To rest anywhere profitable we would sit behind
an enormous queue:

| if we rested at | contracts ahead of us | our EV per contract |
|---|---|---|
| 99.0¢ | 15,218 | +0.10¢ |
| 98.8¢ | ~16,600 | +0.30¢ |
| 98.0¢ | 16,672 | +1.10¢ |
| 96.0¢ | 17,537 | +3.10¢ |
| 90.0¢ | 18,807 | +9.10¢ |

A resting bid has PRICE priority, so every contract bid above ours fills first.
At any price that makes money we are behind more than sixteen thousand
contracts.

**THE IMPORTANT CONSEQUENCE, and it is good news: those closes are not lost
profit.** They are closes where the trade is not available to anybody at a
price that works. We were not too slow and we are not too timid. There is no
version of us that captures them. That closes a line of enquiry rather than
opening one.

**Also worth noting: the 15,218 contracts bid above 99.0¢ are buying
negative-EV contracts at our measured 0.90% flip rate.** Either the resting
crowd's true error rate is far below ours, or they are overpaying. Which of
those is true is unmeasured and matters, because our whole edge rests on 0.90%.

**SCOPE, and it matters.** This is measured only on the closes where NOTHING
was offered. It says nothing about resting in the **41% of closes where an offer
does appear** — a different population, and IDEAS_LOG #6 (+37%) is still open
there.

---

## MEASURED 2026-09-08 evening — THE BINDING CONSTRAINT, and it is not our rules

### 29 | In a decided market the losing side's book is EMPTY — **MEASURED, and it reframes everything**

Replayed the recorded order book across the eight live closes the runner
reported as "nobody offered", using the settled market records pulled from the
API. **33,431 moments where the model was already ≥98% sure:**

| | count | share |
|---|---|---|
| winning side has bids | 33,431 | **100.00%** |
| **losing side has bids (= there is something we can buy)** | **4** | **0.01%** |
| both sides empty (would mean my replay was broken) | 0 | 0.00% |

**The control is what makes this trustworthy.** The winning side is quoted in
every single moment, with a **median of 84 price levels**. So the replay
populated the book fully and the emptiness is real. The four buyable moments
were all priced at **99.90¢**, which the EV gate refuses anyway.

**Why:** to buy the winner somebody must be willing to hold the loser. Once an
outcome is obvious, nobody will, at any price. There is no ask because there is
no bid on the other side.

**What this changes:**

1. **Loosening our own thresholds cannot buy what is not offered.** Every
   parameter argument today — the price ceiling, the edge floor, the EV floor —
   operates on a supply that mostly does not exist. Of 17 closes watched end to
   end, only **7** had any tradeable moment at all.
2. **The ladder sweep is conditional, not general.** `pinladder2`'s $83.14 per
   close was measured on moments where offers existed. Applying it to 33 closes
   a day assumes a book that is empty roughly 59% of the time. At $1,000 of
   capital the honest figure is nearer **$300/day than $729/day**, and market
   impact is still unmeasured on top of that.
3. **RESTING becomes the central untested idea, not a nice-to-have.** We are
   currently racing to take an offer that appears in 0.01% of decided moments.
   A resting bid does not need an offer to exist — it *is* the offer. IDEAS_LOG
   #6 measured +37% for resting and it was parked because zero losses in the
   sample make its one real risk unmeasurable. That parking decision now looks
   much more expensive.
4. **Our 13 wins came from the rare moments a seller appeared.** That is a real
   edge and it is small in count, not in size. It also means the strategy's
   capacity is set by how often someone sells a near-certain winner cheaply,
   which nothing in this repo has yet measured.

**What would make this an artefact, and the check that was run:** if my replay
never populated the book, both sides would read empty and the finding would be
meaningless. Both-sides-empty came back at **0 of 33,431**, with a median of 84
levels quoted on the side that was populated. The finding survives.

---

## MEASURED 2026-09-08 — the two biggest results of the day

### 26 | Size on CONFIDENCE — **TESTED-REJECTED, and it is backwards**

The operator's standing request was to size by how sure we are. Measured across
a panel of sizing rules on 593 eligible trades over 70 closes:

| the model's p_flip | mean price | worth per contract |
|---|---|---|
| below 1e-10 (most certain) | **97.51¢** | **1.41¢** |
| above 1e-3 (least certain) | 94.39¢ | **4.35¢** |

**Confidence and reward are INVERSELY related here.** "Buy more when confident"
is literally "buy more at 97–99¢", which is the expensive end. `CONF_PROP` is
the WORST rule in the panel (3.02¢/contract vs flat's 3.43¢) and gets
monotonically worse as its cap rises.

**What works instead is sizing on what the trade PAYS** — price or EV. That is
the same information with the model's opinion taken out of it. Best survivor:
`TIER_IMPROVE cap2` — first take is 2 contracts when the price is already below
93¢, `n = 1 + floor((0.95 − price)/0.02)`, cap unchanged. +15% per close at
identical max exposure and slightly LOWER abort probability. **Not deployed** —
it is +0.8¢/close measured on 70 closes with zero adverse events, which is a
candidate for pre-registration, not a reason to touch a working process.

### 27 | Is our volatility number any good? — **MEASURED, and it is the wrong SHAPE**

`volcheck.py`, 13.0M cells over 329 hour-files, 90.3% tape coverage. Verified
against the shipped dataset on 28,479 of 28,479 rows (worst relative difference
3.96e-10) and reproduces the settled flip on 28,479 of 28,479.

When the model says the move has standard deviation X, the realised standard
deviation is **1.18X** pooled — 1.105× at tau 3 rising monotonically to 1.262×
at tau 60. But the pooled RMS ratio is only **1.029**, so the *average level* is
nearly right and the gap is per-instance error.

**The distribution is not a gaussian of the wrong width. It is the wrong shape.**

| | realised | gaussian | ratio |
|---|---|---|---|
| median \|z\| (body) | 0.470 | 0.674 | **0.70×** — too NARROW |
| \|z\| > 2 | 7.02% | 4.55% | 1.5× |
| \|z\| > 3 | 2.52% | 0.270% | 9.3× |
| \|z\| > 4 | 1.114% | 0.0063% | **176×** |
| \|z\| > 6 | 0.329% | 2e-7% | 1.7 million× |

**Mechanism, visible in the raw tape: these indices are step functions.**
Fraction of consecutive one-second prints that are EXACTLY equal — SOL 70.5%,
NEAR 39.1%, XRP 17.7%, DOGE 17.6%, ETH 10.7%, BNB 8.4%, HYPE 3.8%, BRTI 0.6%,
ZEC 0.07%. A long flat stretch sets a tiny 300-second sigma, then one second
moves 20–25 sigma and the level persists.

**This independently explains the 0.90% flip rate.** The model implies ~0.06%;
reality is 15× worse. The tail measurement says exceedance at z>3 runs ~9×
gaussian. Two independent routes to the same order of magnitude. **The
protection is not the model — it is that we substitute the measured 0.90% for
the model's number in the EV gate.** That substitution is doing all the work.

**Also corrected here:** the flip-rate 95% upper bound. 1.80% was a Wald normal
approximation on 3 events. The exact one-sided Clopper-Pearson bound on 3 in
333 is **2.31%**, 28% higher. Every headroom figure in this repo now uses 2.31%.

### 28 | Price ceiling 98.8¢ → 96¢ — **TESTED-REJECTED after being wrongly declared live**

See `results/VERSIONS.md`. Committed to disk, never restarted, never traded.
Withdrawn because live prices (mean 97.61¢) are far dearer than the backtest
(93.86¢), so it would refuse 12 of 16 real signals rather than ~30%.

---

## TESTED-PROMISING — works, deliberately not deployed

| # | idea | result | why not deployed |
|---|---|---|---|
| 6 | **Rest at our price instead of racing** *(operator)* | +402¢ vs +292¢ = **+37%**, and no fee | **Zero losses in the sample**, so it cannot measure the one risk resting carries (being filled when wrong). Also needs post/cancel every second — the pattern that lost $24.14 on 2026-09-07. |

**Note:** my *first* test of this was rigged against it — it only filled when
the offer was already at our price, i.e. when we'd have taken it anyway.
Retested with real trade prints, it wins. Caught only because the operator
insisted dead ideas be re-checked.

---

## TESTED-REJECTED

| # | idea | why it failed |
|---|---|---|
| 7 | **Spot lead — predict the index from constituent exchanges** | No forward lead. Predicting index[t+k] from the replica beats persistence by **+0.03% on BTC**. Our replica's noise ($5.4) exceeds a one-second index move ($4.30). The 107 ms *arrival* advantage is real (100.00% of 1,111,809 seconds) but only tells us the present sooner. |
| 8 | **SCALE_ALL — buy every qualifying second** | Highest total but **worst per contract** (4.13¢, below the current rule). More size at worse prices. |
| 9 | **PATIENT — wait for a better price** | Skipping one tick **missed 7 of 70 closes entirely** and earned less per contract. Directly answers "what if it never hits the low": you lose the trade and gain nothing. |
| 10 | **Commodities (GOLD, SILVER, WTI, NATGAS…)** | Settle on a **single instantaneous print**, not a 60-second average. pin's entire mechanism is the variance collapse of an average. Does not apply. |

---

## PARTIAL — tested, not conclusive

| # | idea | state |
|---|---|---|
| 11 | **Dynamic per-trade floor** *(operator, repeatedly)* | The core open item. `pinprob.py` computes `p_flip` per trade and the ceiling falls out as `1 − p_flip − margin`. **Deployed with a CONSTANT p_flip, which collapses it to a fixed ceiling.** Volatility-accuracy study running to decide whether the per-trade number can be trusted. |
| 12 | **Buying cheaper — is it free?** | **No.** The model's own risk rises **700×** from the 99¢ band (0.001%) to the 80–90¢ band (0.739%). The discount is compensation for real risk. Confirmed on model risk; realised flips unmeasurable (zero in sample). |
| 13 | **Confidence-based sizing / Kelly** | Study running. Full Kelly says stake 82% of bankroll — only valid if the probability is *known*; ours rests on 3 flips in 333, and at the 1.80% upper bound Kelly changes violently. That instability is the argument for staying small. |

---

## UNTESTED — queued, with why each matters

| # | idea | why |
|---|---|---|
| 14 | **Sweep MULTIPLE price levels, not just the touch** *(operator, 2026-09-08)* | We measure depth only at the best offer (median 125). The book holds more at 96¢, 97¢, 98¢ — **all under our ceiling and all profitable.** Could multiply capacity several-fold. **Highest-value untested item.** |
| 15 | **Order book features** — quote age, depth, imbalance, spread | Quote age cuts both ways: an old quote suggests an absent quoter (safe); a fresh one may be someone who just repriced (dangerous). Must be measured, not assumed. |
| 16 | **Volatility estimator alternatives** | 30/60/120/300/900s, EWMA, jump-robust bipower, r-matched. The live 300s window is arbitrary and never validated. Study running. |
| 17 | **Autocorrelation in `var_factor`** | `engine.var_factor(tau, rho)` accepts a correlation sequence and **every call site passes white noise.** Nobody has ever checked whether index increments are autocorrelated. |
| 18 | **Kalshi's own `avg_60s_data`** | The index feed carries the exchange's own rolling 60-second mean. We reconstruct it ourselves instead. Using theirs would remove any drift between our locked sum and the settlement figure. |
| 19 | **Cross-asset jump warning** | Eleven coins settle at the same second. A BTC jump may be a live warning for an alt trade about to be placed. |
| 20 | **Hour-of-day effects** | All evidence came from the US afternoon; we ran overnight. Fire rate and flip rate by hour, unmeasured. |
| 21 | **Coin Race (`KXCRYPTOLEAD15M`)** | **Qualifies for pin** — both ends are 60-second averages of indices we already stream — and has **never been traded**. 5 legs per close that must sum to 100¢, a second independent constraint. |
| 22 | **Getting losses into the sample** | Everything above is limited by a dataset with **zero losses at tau 3–30**. Needs a longer span or a deliberately looser rule in backtest only. **Blocks items 6 and 13.** |
| 23 | **Capacity re-measurement under the current rule** | The old "$30/day, ceiling ~$100" figure came from a *different* rule. Not re-derived since v1–v6. |

---

## DEAD — structurally impossible

| # | idea | why |
|---|---|---|
| 24 | `KXADA15M`, `KXBCH15M`, `KXTON15M`, `KXCRYPTOCOMP15M` | Zero markets in any status. Not products. |
| 25 | Spot data for BNB, ZEC, HYPE, NEAR | **No constituent exchange books recorded at all** — `crypto_feeds.py` never subscribed. Four coins we actively trade have no spot-side visibility. Would need a collector change. |

---

## Validation controls (standing gates, run on every change)

| control | result |
|---|---|
| **Mirror** — offer it the opposite side of its own trades | Refused **70 of 70** |
| **Forced wrong side** | Lost **70 of 70**, −4.76¢/trade |
| **Placebo** — outcomes shuffled | **−48.68¢/trade** |

The placebo is the strongest evidence in the project: with outcomes randomised
the same rule bleeds badly, so the edge comes from picking the side, not from
bookkeeping.

---

## Standing caveats that apply to everything above

1. **Zero losses observed, live or in the dataset, at tau 3–30.** At the
   measured 0.90% flip rate this is the *expected* outcome, not evidence of
   safety. The first loss costs roughly ten wins.
2. **The flip rate rests on 3 flips in 333** (or 1 in 359 at the 0.3¢ floor).
   Its 95% upper bound is 1.80% — double the point estimate. Every threshold
   in the system is built on that number.
3. **`MEASURED_FLIP = 0.0090` was taken from the 0.5¢-floor cell** while we
   run the 0.3¢ floor (whose cell shows 0.28%). It lands conservatively
   between estimate and upper bound, but by accident rather than design.
