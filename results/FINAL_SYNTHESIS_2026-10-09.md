> Saved 2026-10-09 ~11:1xZ from the design-competition workflow (wf_a3189736-5a6: 8 blind designers, 8 adversarial verifiers, 3 judges, 1 synthesizer; agent files under the session scratchpad final/design, final/verify, final/judge). Orchestrator checks: the 'flat since the revert is HYPE' recon reproduced (168 non-HYPE markets +$80.95, 5 lost; HYPE 10 markets -$113.50); v-stp-maker launcher results/restart_bot.stpmaker.ps1 -Check PASS and its startup path in PAPER with today's exact argv PASS (code_sha 5075b1783acf, toxic_fresh false, max_edge_c 10.0). ONE CORRECTION to the text below: the coin race runs 20 contracts a leg with a $40 stake cap (v-race20cap), not 10. This supersedes results/FINAL_VERSION_2026-10-08.md (v-seen), whose two refusals did not survive.

# FINAL SYNTHESIS: the next version of the 15-minute crypto bot (2026-10-09)

**Inputs.** Eight blind designs. Eight independent verifiers, each of whom rebuilt the numbers from raw data. Three judges, one each for maximum money, robustness and evidence quality. My own checks (design\synth\s1_recon.py and s1.out) and two code reads.

**Rules used.** Loss numbers come only from our own live fills. TRAIN is closes before 09-28 00:00Z. TEST is 09-28 to 10-08 09:30Z. n counts markets. Market close times are in ET.

**Reconciliation (my own run).**
- Lifetime: 1,362 main markets, +$701.78 on $66,379.06 bet, 45 with money below $0.
- 42 of those lost more than 1c. 12 of the 42 were insurance false alarms: our side won, but the insurance cost money.
- TEST without HYPE: 303 markets, 10 lost, +$165.19 (+$15.88/day).
- Since the 10-04 03:30Z revert, without HYPE: 168 markets, 5 lost, +$80.95 (+$19.05/day).
- HYPE alone since the revert: 10 markets, 2 lost, -$113.50.

So "roughly flat since the revert" is entirely HYPE, and HYPE is already skipped.

---

## 0. The operator's worry: "is this just a regular update?"

**In shape, yes. That is what the evidence found, not loyalty to the current bot.**

- **Every part was attacked by someone whose job was to replace it.** Separate designers took: when to buy, how much, how orders are sent, insurance, which markets to refuse, a maker business, a red team of the current bot, and one told to build something entirely new (a maker-only bot with no taker).
  - A separate verifier rebuilt every claim from the raw recordings.
  - Three judges with opposite priorities each assembled a version on their own. All three landed on the same shape.
- **Ideas outside this bot had already been swept.** results/IDEA_LEDGER.md shows 65 ideas checked on 10-02, 49 of them dead. Every survivor pays under $3/day at a size we can run. That covers hourly ladders, weather, brackets, sports and more.
- **The current bot was not given a free pass.** Three things were found against it:
  1. Its buying with more than 20 s left is not shown to make money. By half-period it made +$247, -$134, +$33 and -$162. In TEST, without HYPE, alt buys above 20 s lost $54.94 over 154 markets. It stays only because every alternative's gain rests on a single market. It is now on a tripwire (section 1, rule 7).
  2. Insurance's TRAIN value was overstated by $40-80 because of a stale price model. In TEST it holds on real hedge fills: +$134 over 11 markets.
  3. "Flat since the revert" is HYPE, as shown above.
- **What is genuinely new:**
  1. A signal the bot has never used: BTC's settlement index moving against an alt buy in the 3 s before it. It is the only refusal that held in both time periods on our own fills.
  2. The maker ladder grown as a second business. It makes money at different seconds from the taker: 1,320 of the taker's 1,362 buys happened when the maker's safety rule was not met.
- **What could not be beaten:** timing, size, the sweep and the insurance trigger. Nothing beat the current settings in both periods on real fills. Changing them anyway would be change for its own sake.
- **What is still open:** 6 of the 10 TEST losers would get past the new refusal (BTC markets, buys inside 20 s, insurance false alarms). No measured rule catches them yet.
  - The best leads are watch items (a) and (b) in section 2b. They are "what happened after we bought" signals.
  - That is the one area where a further dedicated design pass could still pay. No new agent was needed to decide this version.

---

## 1. The recommended version: "v-lead"

**In plain words.**
- Keep the taker exactly as it runs today.
- Add one refusal. On alt coins with more than 20 s left, do not buy if Bitcoin's settlement index has just moved sharply against our side, and stay out of that market for the rest of its 15 minutes. BTC moves tend to drag the alts about a second later.
- Make insurance orders win any clash with our own maker bids.
- Grow the maker ladder only with new money, in steps that each pass a bar written in advance.
- Everything else stays as it is.

**Exact rules.**

**1. Taker base (main account).** Today's live arguments exactly (restart_bot.ps1 = results/restart_bot.before-seen.ps1, which is the 0925d argument list), run on build C:\kals-live-0925e (code_sha 5075b1783acf).
- I diffed 0925d against 0925e. With default flags the only behaviour change is that hedge orders carry `self_trade_prevention_type="maker"` (pintake.py around line 761). `--max-edge-c` defaults to the old 10c constant, and `--toxic-fresh` stays off.
- Coins: BTC, ETH, SOL, XRP, DOGE, BNB, NEAR, ZEC. HYPE stays skipped (`--skip-coin KXHYPE15M`).
- Bot model at least 0.995, edge at least 0.3c, ceiling 98c, IOC sweep kept.
- 31-45 s left: early leg, holdings at most 1/3 of a bet, price 90-98c, edge at most 10c.
- 30 s or less: full bet, with one full bet per market (`--max-full-bets 1.0`) and a 10c edge cap above 20 s.
- Inside 15 s: late add of half a bet, plus one late extra bet.
- Inside 10 s: 1.5x boost when the model is at least 0.9975 and there was no 2-sd jump against us. The boost turns off after one boosted loss.
- Bet size = bank / 11.76 (`--bank-brake 4.00`).
- Stops unchanged: -$200 run and day loss caps, and a pause after 2 losses. The 20% drawdown halt is OFF in the live arguments (`--no-drawdown-halt`), but the high-water mark still drives the bank brake and the room for the boost.
- The 1-contract hourly BTC ladder (`--series KXBTCD --series-size 1`) stays.

**2. Insurance.** Unchanged trigger: belief in our side falls below 0.40 on the first print. Full held size, IOC at touch+10c, retried for 30 s. Nothing may block it. A68 stays on.
- The only change is self-trade setting "maker" on insurance orders. An insurance order that crosses our own resting maker bid (subaccount 1) then cancels that bid instead of being cancelled itself.
- Entries keep `taker_at_cross`.
- Measured money effect so far: $0. This must be live before the maker grows.

**3. BTC-lead refusal** (new flags `--btc-lead-sd 1.0 --btc-lead-tau 20 [--btc-lead-shadow]`). Build it in a fresh copy, C:\kals-live-0925f, so 0925e stays the clean revert.
- **Scope:** alt markets only (ETH, SOL, XRP, DOGE, BNB, NEAR, ZEC). BTC markets are never gated.
- **When checked:** every entry order (early, full, top-up, late add) with more than 20 s left. Never on the insurance path, never on A68 rebuys.
- **Inputs:**
  - b = whole-second stamp of the newest CF print the bot holds for that alt's index.
  - P(t) = the BRTI print stamped t.
  - M = P(b-1) - P(b-4).
  - sd = sample sd of BRTI 1-s changes P(t) - P(t-1) for t in [b-301, b-2]. At least 150 valid changes are needed.
- **Score:** s = -M/sd when buying YES, +M/sd when buying NO.
- **Action:** if s ≥ 1.0, refuse the order and lock that market out for the rest of the close. A position already held stays and is insured as usual.
- **Missing input:** no refusal.
- **Code it exactly as measured.** Use b-1, not b. Read the newest BRTI print in memory: one more second of staleness cut TEST from +$180 to +$136.
- **Logging:** log every evaluation, fired or not: ticker, side, tau, ask seen, intended size, s, b, M, sd, and the age of the BTC print used.
- **Shadow mode** (`--btc-lead-shadow`) logs the same fields but never refuses.
- **Self-test, in a driven world:**
  - a BTC drop refuses an alt YES and not an alt NO;
  - nothing fires at 20 s or less, or on BTC markets;
  - a held position is still insured;
  - a missing BRTI print means no refusal;
  - the test fails with the gate reverted;
  - the startup path runs in paper with the full live arguments and asserts `_DEFAULT_` values, never the running ones.

**4. Instrumentation** (log-only, in the same 0925f build). Log the price of each fill per order, our best ask at reply time, and the exchange timestamp of our fill print.
- It must be wrapped so a logging error can never stop an order or a hedge. A self-test case makes the logger throw and checks that the order and the insurance order still go out.
- No money effect. It turns the execution study's estimated ranges into exact numbers.

**5. Maker ladder** (subaccount 1, research/cleanroom/ladder_live.py). The rule is unchanged:
- Decide each second from 30 s to 1 s before the close, on receipt of the print.
- Rest only when p ≥ 0.999 (or ≤ 0.001) AND |proj-thr|/v ≥ 0.25 x MAXERR(rel).
- One post-only GTC 98c bid on the decided side, self-trade "maker". `--market-cap-x 2`, COMMIT_FRAC 0.70, `--auto-size` = pot/14.
- Cancel when the rule stops holding or a print is missing, and cancel everything at the close.
- Never start earlier than 30 s, never use a floor below 0.25, never bid 99c.

The stages:
- **Stage 0 (now):** pot about $78, about 5 contracts a bid.
- **Stage 1:** pot about $350, so auto-size gives about 25 a bid. At most 50 contracts and $49 on one market.
  - Preconditions: the ladder-capfix read (due 10-10 12:00Z) passes, and v-stp-maker is live.
  - Funding: about $270 of new money, which the operator adds himself (Claude never deposits).
  - No code change.
  - Any losing maker market stops the ladder for a re-read.
- **Stage 2:** pot about $700, size about 50. Only after the stage-1 bar passes, and only as a v2 build:
  - coin weights re-estimated on stage-1 live fills plus TEST, not TRAIN (DOGE's TRAIN rank failed in TEST; NEAR, ZEC and XRP held);
  - optional fixed 98.1c and 97.1c price levels instead of model-minus-2c (tape only, about +$0.9/day);
  - one fill per price level per market, no refill;
  - a per-close cap;
  - a stop for the ET day after any losing maker market;
  - the existing 3 writes/s cap;
  - self-test and startup path.

**6. Side bots unchanged:**
- forecaster (subaccount 2), until its own 10-13 bar;
- coin race at 10 contracts a leg with its existing stake cap;
- weather dip-seller (subaccount 3, $50), until its 60-fill bar.
- arm-5hz keeps running in paper.

**7. Tripwires (reads, no code):**
- **21-30 s window.** Count forward from the v-lead restart: markets first filled at 21-30 s, HYPE excluded, money as traded including insurance. At 150 such markets (about 3 weeks): if the total is below -$75 AND 6 or more lost, propose a cap of 1/3 of a bet before 20 s. That needs a code change, the startup self-test and the operator's OK.
- **Insurance.** Over the next 10 alarms: every insurance order carries "maker", none is cancelled for self-trade, and the share filled is not below the previous 14 alarms. Also report the real insurance legs over the next 15 alarms, priced against the trade-based price of the same second, not the 1/s ticker touch.

---

## 2. What goes live, what goes first to shadow or paper, and what was rejected

### 2a. Live now (in order)

| step | what | before going live | revert | keep/revert bar |
|---|---|---|---|---|
| A. **v-stp-maker** (today) | today's arguments on C:\kals-live-0925e; only change: insurance orders self-trade "maker" | startup path in PAPER with this exact argument list (the 10-09 PASS used the v-seen arguments, not these); versioncheck.py; VERSIONS.md entry; READS_DUE item; restart only while flat, arguments checked before the stop | copy results/restart_bot.before-seen.ps1 over restart_bot.ps1 and run it while flat | revert at once if any insurance order is refused or cancelled for self-trade, or the insurance path errors; otherwise rule 7's insurance read |
| B. **v-lead-shadow** (when 0925f passes its self-test; 48 h) | the BTC-lead check logs but never refuses, plus instrumentation | as A, with the new flags | the v-stp-maker launcher | **PASS needs all four** (pre-registered 10-09): (1) live s matches s recomputed offline from cfbenchmarks_value within 0.05 on ≥95% of alt sends above 20 s; (2) it fires on 6-20% of those sends (the study saw about 12%); (3) median age of the BTC print used ≤ 1.3 s; (4) zero evaluations on insurance or A68 orders. Fail = fix, do not refuse. Flagged markets in this period are bought, so their outcomes count toward C's 40. |
| C. **v-lead** (after B passes; operator OK) | drop `--btc-lead-shadow`: the refusal is live | startup path in paper with the live arguments; versioncheck; VERSIONS entry | the v-stp-maker launcher (gate off) | below |
| D. **Maker stage 1** (operator funding; after capfix passes and A is live) | pot about $350, auto-size about 25 | none (no code) | stop file, then move the money back to main if (b) or (c) fails | below |

**Bar for C** (pre-registered 2026-10-09, before any refusal result). It is read at 40 flagged alt markets (about 2 weeks at about 3/day) and again at 80. "Against us" means Kalshi settled the market against the side we would have bought. Insurance false alarms are reported but not counted, which makes keeping the gate harder, not easier.

Value at a flat bet, per flagged market = intended contracts x (1 if our side won, else 0, minus the ask seen) minus the taker fee.

- **KILL** (revert, flag off) if at 40:
  - 1 or fewer went against us, OR
  - the refusals cost more than $30 net.
- **KEEP** if 3 or more went against us in 2 or more distinct closes, AND refusing saved money (value ≤ $0).
- **Otherwise** extend to 80, and keep only if 5 or more went against us in 3 or more closes with value ≤ $0.
- **Engineering kill at any time:** any insurance or A68 order is refused.
- Report results by coin, but do NOT refit coins on this data.
- Odds of the bar: at the measured strength (about 8-10 in 100 against us) it keeps about 6 times in 10. If the signal is pure noise (about 3 in 100), it kills about 2 times in 3 and wrongly keeps about 1 time in 9.

**Bar for D** (pre-registered 2026-10-09). Read at 60 or more filled maker markets AND 7 or more ET days.
- (a) 0 losing maker markets. Any loss halts at once. If the loss was not on a second when the index made the rule wrong, the fill model is wrong: go back to size 5.
- (b) Live contracts are at least 70% of the tape model's contracts for the same closes and size (calib.py or ladder_tape2.py).
- (c) Ladder net is at least +1.0% of the pot per day (about $3.5/day). That is the bar against the real alternative: the taker made about 1.5% of its bank per day in TEST.
- Pass all three: build v2 and put stage 2 to the operator. Fail (b) or (c): back to size 5.

**If the operator would rather move money from main than add new money:**
- Only when the main bank is at or above its $1,095.67 high-water mark, or he approves re-basing the mark (that changes his own risk limit).
- Only while the bot is flat.
- The live log must show an `external` record with the transfer id within 5 minutes. An `unexplained` record means the bot read the transfer as a trading loss.
- Expected money is about $0. The taker sized at 0.73x loses about $4/day (judge j2: TEST -$3.98/day, since the build -$4.77/day), and the maker gains $2.5-4/day.
- What it buys is information: the size-25 fill rate. It does not buy money.

### 2b. Shadow, paper or read first

- **arm-5hz** (paper, running since 10-09 05:23Z, read 10-14). The registered bar stays. **It is made stricter, stated loudly, before any result:** the existing bar compares paper losing counts, which paper cannot judge.
  - PROMOTE now needs both the registered condition AND a live-market condition. The set is shared closes where arm-5hz did NOT buy, the twin DID buy, and LIVE bought. After 5 or more ET days, live money on that set must be at most -$40, with 2 or more losing markets in 2 or more closes.
  - KILL if that live money is $0 or more.
  - If it is ported, re-measure the BTC-lead check on 5 Hz prints in paper before changing its inputs.
- **BTC-lead without the lock-out** (optional paper arm beside the twin). It measures decisions and supply only: how many refused markets would be re-bought within the same close, and at what time left. Consider dropping the lock-out only if more than half are re-bought at 20 s or less.
- **Reusing one HTTPS connection for orders.** Deferred, not built this round. It touches the order and insurance paths, and its sign is not established.
  - Measured: +$1.6-2.7/day on the orders that can be checked. But one known losing-side order (DOGE 09-23, about -$77) cannot be measured.
  - If it is ever built: test on the demo key first; a dead socket must never delay insurance; its own version and bar.
- **Watch, measure, no rule.** These are identify-better leads aimed at the losers the gate cannot catch. Measurement is read-only and should run now.
  - (a) After an early buy, a 90-98c offer reappears on our side in the last 20 s. TEST: those 34 markets made -$271 live; the other 216 made +$179. This is the strongest unmeasured lead. Measure whether it shows up before insurance fires, and what blocking top-ups or insuring earlier would have done, TRAIN vs TEST.
  - (b) First fill 2c or more under the ask seen. TRAIN: 36 markets, 10 lost. TEST: 11 markets, 2 lost.
  - (c) Sweeping past a thin best offer (under 10% of a bet): TRAIN +$135, TEST -$208, 5 TEST losing legs.
  - (d) A 5c cap on how far the sweep may go above the ask seen, with more than 20 s left. Positive in all four windows, but each window rests on one market. Its TRAIN market, BNB 09-19, is already caught by the BTC-lead refusal.
  - (e) The 1 Hz index-age band: first half about $0.
  - Rule for all five: a live change only after 3 or more NEW losing markets of that type in live fills after 10-09, with the rule positive in both the old and the new windows.
  - Untested side lead: when BTC moved at least 1 sd FOR us, the 115 TRAIN and 37 TEST markets were near-clean (2 and 0 losers). Sizing those up is unmeasured and small.

### 2c. Rejected, and why

- **Seller check (`--toxic-fresh`):**
  - In its only live run (09-27..10-04): 61 refused markets never bought, 2 went against us, worth about $0. Refused markets went against us 2.7 times per 100 against 2.5 for entries it let through, so it showed no selectivity.
  - On top of BTC-lead it loses: TEST -$32.69 (bootstrap P(no gain) 0.91), since the build -$45.70.
  - It refuses 37% of markets in the current build against BTC-lead's 8%.
  - Its big TRAIN save (BTC 09-27, -$132) was a double bet that one-full-bet already blocks.
  - Kept only as the fallback if BTC-lead fails its bar.
- **5c edge refusal (`--max-edge-c 5`, `--early-max-edge 5`):** works in one period only.
  - TRAIN at a flat bet -$58.7 (first half -$175.8). It refuses the cheap, big-edge winners that pay most.
  - On top of BTC-lead: TEST -$46.90 (P(no gain) 1.00), since the build -$21.86.
- **V0 as a package vs BTC-lead alone:** BTC-lead is better by +$72.51 in TEST (90% CI +$37 to +$107) and +$74 since the build. TRAIN shows no difference (-$29, CI -$442 to +$327).
- **`--late-mult 2.0`** (boost 2.0x inside 10 s):
  - Verified worth only +$0.70-0.85/day in TEST. It is mostly switched off right now anyway, because the bank brake caps the boost while the bank is below about $1,035.
  - One loss on the extra contracts ($34-48) erases 40-60 days of gain.
  - **Code side effect, confirmed by me** (0925d pinrun.py lines 20089-20091 and 20501-20502): the full-bet cap's room uses LATE_MULT for every order inside LATE_TAU, whether or not the boost conditions hold. At 2.0 that opens room for a second full bet, which the operator capped.
- **Timing alternatives:**
  - Late-only drops about 70% of markets: 86% of TEST early-bought markets had no 90-98c offer on our side in the last 20 s. Without HYPE, its TEST gain is +$0.06/day.
  - No buying at 21-30 s, and 1/3 of a bet before 20 s: each TEST gain is one market (-$15 to -$30 without it), and both lose in TRAIN.
  - Early leg off: loses in every half.
  - Early leg at a full bet: -$3.61/day in TRAIN.
- **Sizing:**
  - R2 (1/3 of a bet before 20 s): TRAIN -$4.24/day; TEST is NEAR 10-03 plus ZEC 10-07, both already caught by BTC-lead. On top of the gate it loses in both periods.
  - R1 (2.0x inside 15 s): about +$1/day at the observed late loss rate, negative at 3 per 100.
  - New stops: stopping after the 2nd loss costs $123 in TRAIN and $79 in TEST; after the 1st, $150 and $56.
  - Auto-size stays as it is.
- **Execution:**
  - Dropping the sweep: TRAIN -$18.6 to -$20.6/day; its TEST gain is NEAR 10-03 alone.
  - Count caps and touch multiples: lose in TRAIN.
  - Dropping late adds: TEST -$4.67/day.
  - No collapse rule: the TEST collapse group is 7 markets, 1 lost, -$1.79. Nothing to save.
- **Insurance variants:**
  - Hair-over skip: TEST -$26 to -$33.
  - No trigger beats 0.40 in both periods. The TRAIN-best, 0.20, is $45 worse in TEST.
  - Half size halves a positive value.
  - Skipping the last 10 s has no TEST alarm to test on.
  - Unwind and 1.5x insurance rest on prices that were shown, not prices we got.
- **Ladder-first, no taker (the "entirely new" design):**
  - It swaps a business proven on live fills (+$701.78) for a tape forecast at 18x the largest size ever run live: TEST $16.83/day, about $12-15 realistic, against the taker's measured $15.88/day without HYPE.
  - That forecast is falling every half-period ($43 → $27 → $18 → $15/day).
  - The 95% upper bound of its loss cost (about $13/day) equals its profit.
  - Per dollar the taker is at least as good.
- **Maker loosening:**
  - Floor 0.20 lets 3 TRAIN flips through.
  - Starting at -60 s gives 7 TRAIN plus 1 TEST flips and losing fills; -45 s gives 3 TRAIN flips.
  - 99c bids make less money.
  - A taker gated by the maker rule keeps 7 of 1,362 markets.
- **Funding the maker by moving money out of main now:** expected about $0, and the bank is below the high-water mark. Only as described in 2a.
- **Coin, hour, weekday and Saturday rules:** not stable across halves.
- **The BTC-lead gate inside 20 s:** TRAIN -$61.57.
- **Restricting the gate to NEAR, ZEC and BNB:** a post-hoc fit.

---

## 3. Expected money per day

| part | central | range | basis |
|---|---|---|---|
| Taker as today (no HYPE) | $14 | $8-19 | live: TEST $15.88/day (303 markets, 10 lost); since the build $19.05/day (168 markets, 5 lost, 4.25 days); daily average since 09-18 $13.48, typical day $26.54. Supply is softening. |
| BTC-lead refusal | +$5 | -$3 to +$10 | live fills, lock-out replay. Without HYPE: TRAIN +$208 (+$10.57/day; +$5.1/day with today's caps applied to history), TEST +$182 (+$17.5/day). Discounted because 2 markets carry TEST and the holdout is partly contaminated. If it is noise: -$1 to -$3/day. |
| Insurance self-trade fix, instrumentation | $0 | $0 | precaution; logging |
| Ladder as now | $1.3 | $1-2 | live: 124 filled markets, 0 lost, +$14.06 on $683.82 |
| **Total, no new money** | **about $20/day** | **$5-30/day** | |
| + maker stage 1 (about $270 new money) | +$3 | +$1 to +$4 | tape at size 25, TEST about $5.5/day before friction and about $4 after, minus today's ladder; only live size 5 is calibrated (live filled 1.33x the model) |
| + maker stage 2 (about $350 more, only if stage 1 passes) | +$8 | $0 to +$11 | tape only; never run above size 5 |

**What drives the uncertainty.**
1. **Day-to-day swings.** Since 09-18 (no HYPE) the daily standard deviation is $75.84. The worst day was -$207, and 7 of 20 full days lost money. From noise alone a 30-day average is only known to about ±$14/day, so a whole-bot difference of $5/day cannot be seen in the bottom line within a month. Each part has to be judged on its own bar.
2. **The BTC-lead gain rests on two markets** (NEAR 10-03 and ZEC 10-07). Without them TEST is +$9.72.
3. **Supply is softening.** The taker's market counts dip on some days; the maker's tape supply falls every half-period.
4. **The maker has never run above size 5.**

**Risk.**
- A day is capped near -$200 by the loss caps.
- The as-traded record since 09-18, resampled into 30-day months, gives a 5th percentile of -$234 and a losing month 16 times in 100. With the gate at half its measured effect it is 2 in 100, but that is in-sample and optimistic.
- A realistic bad month for this version is about -$300 to -$400.

---

## 4. Where the judges disagreed and how I resolved it

1. **BTC-lead: refuse live at once (money, robust) or log-only first (evidence).** → **48 h log-only on the live bot, then refuse.**
   - Wrong-feature builds are this project's commonest bug.
   - Print staleness decides much of the value, and only the live process can measure its own print age.
   - Flagged markets during the log-only period are bought, so their outcomes count toward the same 40-market bar. No evidence is lost.
   - Cost: about 2 days x about $5, so about $10 expected.
   - A 3-week log-only period (the selection verifier's option) was rejected. It forgoes about $60-100 of expected gain to save about $40 of downside.
2. **The kill-bar wording (three versions).** → Combined: the settlement count (≥3 against us of 40 to keep, ≤1 to kill), plus evidence's money clauses (value ≤ $0 to keep, more than $30 cost to kill), plus distinct closes. The odds are in 2a.
3. **`--late-mult 2.0`** (money: optional; robust and evidence: reject). → Rejected. It is under $1/day, mostly switched off by the brake, carries a fat tail, and has the full-bet-cap side effect I confirmed in code.
4. **Funding the maker: new money (money) or a transfer from main (robust: a wash with smaller swings; evidence: a transfer with preconditions).** → New money preferred. A transfer only as an information purchase, with the high-water-mark preconditions. Otherwise no change. Its expected money is about zero, and "no change for its own sake" applies.
5. **Maker stage-1 bar** (60 filled at 70% / 100 filled at 50% / 60 filled plus 7 days plus 70% plus at least 1%/day). → Evidence's version: the strictest, and the only one that compares against the real alternative.
6. **Maker v2 contents** (money: build before stage 2 with TRAIN weights; robust: re-weight on stage-1 fills; evidence: reject for now). → Build v2 only after stage 1 passes, with weights from stage-1 live fills plus TEST, never TRAIN's DOGE rank.
7. **arm-5hz bar** (money and robust: as registered; evidence: rewrite). → Stricter: both conditions are needed to promote. Changed before any result and stated loudly.
8. **21-30 s tripwire** (money: 300 markets / -$100 counted from 09-17, which already stands at -$170 in-sample; robust: 150 / -$75 forward; evidence: 150 / -$75 AND at least 6 lost, forward). → Evidence's version. Forward-only avoids an in-sample start, and the loser count stops one market from tripping it.
9. **Connection reuse** (robust: demo first; evidence: defer; money: reject). → Deferred.
10. **Instrumentation** (evidence only). → Adopted. It is log-only and directly serves "identify better".
11. **Small factual fix.** The evidence judge listed a 20% drawdown halt among the stops. The live arguments carry `--no-drawdown-halt`, so the halt is off. The high-water mark still governs the bank brake and the boost room, which is why the transfer precondition stays.

---

## 5. Does V0 (v-seen) survive?

**Only in part, and not as a money change.**

**What survives:**
- Its vehicle: build 0925e. With today's arguments it differs from the live build only in the insurance self-trade setting.
- That self-trade fix itself.
- Its diagnosis that losses are adverse fills on entries with more than 20 s left. BTC-lead targets the same group with a threshold chosen on TRAIN.
- Its direction of growing the maker. That is stage 1 here, funded with new money.
- Its 5 Hz paper arm, with a stricter read.

**What does not survive:**
- Both refusals: the seller check and the 5c edge cap. Each loses money when added on top of BTC-lead, in TEST and since the build.
  - The seller check showed no selectivity in the only week it ran live.
  - The 5c cap fails TRAIN at a flat bet.
- Its 7-day "≥ +$10/day" bar. A 7-day average is only known to about ±$57/day, so that bar could not have judged the version.
- Its "flat since the revert" framing, which was HYPE.

**Practical consequence.** results/restart_bot.seen.ps1 must NOT be used as it is: it turns on `--toxic-fresh` and the 5c caps. OPEN_WORK A21 "go v-seen" should become "go v-stp-maker, then v-lead".

---

## 6. The three things most likely to make this wrong

1. **The BTC-lead signal is noise or fades.**
   - Two markets carry TEST.
   - The holdout is weaker than it looks: loss_anatomy.md had already flagged BTC moves while looking at all losers, TEST ones included.
   - The gain sits in two of four half-periods: TRAIN halves +$10 and +$198, TEST halves -$7 and +$189, without HYPE.
   - It is sensitive to print staleness, and others may trade the same lead.
   - Cost if wrong: about $2-4/day until the kill bar removes it in 2-3 weeks (about -$40 to -$60). The 48-hour check guards against a wrong build.
2. **The taker's base weakens further, and the losers the gate cannot see keep coming.** Everything here rests on the taker staying positive.
   - If our loss rate rises to 1.5x lifetime (about 4.2 per 100), today's build is about break-even.
   - 6 of 10 TEST losers pass the gate: BTC markets, buys inside 20 s, false alarms.
   - Supply has been softening.
3. **The maker does not scale the way the tape says, or its rare failure comes in a cluster.**
   - It has never run above 5 contracts. Competitors may sit at 98c and above, and supply falls every half-period.
   - The safety bound (1 wrong call in 24,553 markets, 0 in about 16,000 since 09-18) comes from the index, so it holds no matter who sells to us.
   - But a close where the rule is wrong on several coins at once could cost $100-200 at stage 1-2 sizes. This has happened when starting from -60 s (4 coins on 09-15), never from -30 s at floor 0.25.
   - Hence stages, new money only, and a halt on any loss.

---

## 7. Decisions for the operator

1. Go **v-stp-maker** now? Today's exact settings on the 0925e build; the only change is that insurance orders cancel our own maker bid instead of being cancelled. This replaces "go v-seen".
2. Build the **BTC-lead refusal**: 48 hours log-only, then refusing, with the 40-market kill bar in 2a? (yes / no)
3. **Maker stage 1:** add about $270 of NEW money to subaccount 1 for about 25 contracts a bid? (yes / no / instead move it from main later, once the bank is back at $1,095.67)

---

**Files and checks.**
- My script and output: C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final\design\synth\s1_recon.py and s1.out.
- Code reads: C:\kals-live-0925d vs C:\kals-live-0925e (the pintake and pinrun diffs), and the full-bet-cap lines in C:\kals-live-0925d\research\pinrun.py.
- Judge outputs relied on: judge\money\j1.out, j2.out, j3.out; judge\robust\j1.out; judge\evidence\j1.out, j2.out, j3.out and dump_*.txt. Selection refused-market list: design\selection\s11.out.
- I did not read the raw recordings.
- After my runs: kalshi_collector (pid 2532788, 46 MB) and crypto_feeds (pid 105352, 36 MB) were both alive. Free disk 20.9 GB, free RAM 2.45 GB.
- FINAL_SYNTHESIS.md was not written to disk, because subagent rules forbid report .md files. This message is its full text.