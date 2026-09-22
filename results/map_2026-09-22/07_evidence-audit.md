# 07 evidence-audit -- which live settings rest on real evidence (2026-09-22)

**Status: COMPLETE (last update ~07:3xZ 09-22).** Question: which settings the bot runs with right now are backed by real evidence, and which rest on the replay, the tape, a handful of closes, or nothing.

Sources: Kalshi ledger (`results/kalshi_ledger.json`, `pinledger.pnl`, one row per market); the bot's own 124 `pinrun-live-*.jsonl` (start / order / settled / hedge records); `results/VERSIONS.md`; `restart_bot.ps1`; `results/PREREG_*.md`; 305 `pinrun-paper-*.jsonl` for the arm window. Pin-bot universe = the 9 crypto 15-minute series: 747 markets with our fills, 09-08 07:59Z .. 09-22 06:29Z, ledger total **+$464.98**. Markets are attributed to a setting by the time of their FIRST fill. Scratch scripts: scratchpad `map/07/*.py` (load, markets, epochs, early, since, flips2, arms). Deploy times are from the bot's own `start` records, not VERSIONS.md (see F6).

## 1. Findings, ranked by the money riding on each

### F1 -- The 31-45 s early leg carries 69% of our markets and has NO live evidence that it makes money; the number used to keep it (v-nocap) was an artefact of the bot's own log.
- **Claim.** Since it went live (09-17 13:05Z) 202 of 291 markets were entered at 31-45 s; on Kalshi's books those markets net **-$59.00** over 149 closes (7 losing markets), while the 89 main-window-only markets net **+$117.67** over 80 closes (2 losing). Since full size (09-18 16:33Z): early **-$108.01** (143 mkts / 107 closes / 6 losing) vs main **+$49.78** (66 / 60 / 2). Since v-nocap (09-20 09:48Z, bugs fixed): early +$9.78 on 62 mkts (+$0.16/mkt) vs main +$68.85 on 28 (+$2.46/mkt). 7 of the 9 hedge alarms since 09-17 were on early-leg positions.
- **The evidence behind it is an artefact, reproduced exactly.** v-nocap (09-20) kept the leg at full size and removed its ceiling on "136 markets, 8,671 contracts, +$110.67, 1.5% losing". My rerun: the 136 early markets that HAVE a `settled` record, scored on the ENTRY LEG ONLY, give +$124.14 with 1 loss. The ledger for the same window: **140 markets, -$68.78, 5 losing.** The +$179 gap is (a) 4 markets with no settled row because the process died or restarted holding them (BTC 09-17 21:15 ET -$27.87; BTC 09-19 02:00 ET -$66.34) and (b) hedge-leg costs on early positions (XRP + HYPE 09-19 23:45 ET false alarms, -$108.86). `pinledger.py` was written on 09-18 precisely because our logs miss dead-process rows and second legs; v-nocap two days later did not use it. The 09-14 conclusion that early entry "looks like a loser" was WITHDRAWN on this same number.
- **Its other supports:** the tau-45 paper arm (27-33 closes, 0 losses) could not hedge and ran stale flags (void by CURRENT_STATE's own rule); "buyers of 95-98c lost 2.8% at 31-45 s vs 3.9% at 16-30 s" is a TAPE loss rate (the rule that forbids quoting one is dated 09-11); and `pinrun.py`'s own TAU_MAX comment still calls 31-45 s "a measured wall ... do NOT extend past 30".
- **Two pre-registered bars on this leg fired or passed-then-bled.** (1) v-cheap (09-19): "revert `--early-max-edge` to 3.0 at TWO losing closes on early fills under 96c in the first 40". The second losing close was fill #9 (HYPE, 09-20 03:44Z); a third followed at #17 (NEAR 09-21, -$59.09). Those 19 fills net **-$94.31**; the 10 after the bar fired net -$17.66. Flag still 10.0. (2) PREREG_staged stage 2 (first 40 early closes: under 3 losses AND net positive) PASSED -- +$47.09, 1 loss (+$66.69, 0 losses counting from the 09-18 03:02Z recount) -- and the **next 88-109 early closes lost $106-146 with 5 losing closes**. Every bar in this project is a one-shot gate on the first N closes; none keeps watching.
- **Confidence / artefact check.** High that v-nocap's figure was wrong (reproduced to the market count). Low-to-medium that the early leg is WORSE than the main window: close-clustered bootstrap, early -$0.40/close vs main +$1.47/close, difference -$1.87, 95% CI [-5.18, +1.48], 13% chance the sign is noise. Two early losses were bugs since fixed (A69 pause skipped a hedge, -$107.95; process exit holding a bet, -$66.34); without them early is +$0.78/close, still under main. Flip rates are similar (early 6/202, main 2/84) and so are average prices (96.44c vs 96.19c): the gap is loss SIZE -- full-size positions caught by hedge failures and false alarms -- not how often it loses. Counterfactual not measurable from the ledger: without the leg, some of these markets would have been bought at <=30 s and some would have had nothing left (26 of 34 early legs on 09-18 found no offer by 30 s).

### F2 -- All three hedge settings now live were deployed in 3 h 09 min on 09-21 on replays of 16-18 alarms; the trigger (0.25) sits below a pre-registered floor (0.30) nobody mentioned.
- **Money riding.** The hedge decides the size of every big loss: the 10 worst closes since 09-13 sum to -$568.92 against +$455.45 total. 1-2 alarms a day (21 in 14 days), $20-110 swing each. Lifetime the hedge is roughly break-even to negative (-$9.35 per investigator 04; -$47 per CURRENT_STATE).
- **What the evidence is.** `v-hedgefull` (17:03Z): 18 alarms re-priced against the book at the alarm second (tape-priced replay). `v-hedgelastweek` (18:14Z): operator preference; the same replay said it was $9 WORSE in total. `v-hedge25` (20:12Z): `hedgetune` replay of 16 alarms, trigger chosen in-sample with leave-one-out, **no holdout split and no live bar** -- rule 4 of the 09-10 amendment. PREREG_hedge.md (09-14): "**Not below 0.30.** Everything under it gives up the 05:30 BTC hedge", and "do not move the trigger ... until at least 10 further hedge events [after 09-14] ... no single event accounts for more than half the difference". Neither 0.60 (09-16, 9 events) nor 0.25 met it.
- **The replays disagree with each other by as much as the policies differ.** "Hedge the whole position at 60%, no price gate" is -$345.31 in v-hedgefull and -$370.05 in v-hedge25 (a $25 method gap); 0.25 vs 0.20 differ by $19. `hedgetune.py` has no lag, staleness or latency parameter at all (grep), so its ranking was never run with the confidence read 1-2 s late -- the test that inverted the coin-race result (+$102/day at lag 0, -$102/day at lag 2). The live bot allows a book up to 2,000 ms old.
- **Live since v-hedge25:** 1 alarm, HYPE 09-21 18:15 ET, a real loss (early leg, 55 YES at 98c, tau 43); hedged at belief 0.23 for 57c, close -$31.27 instead of about -$54. One event.
- **Confidence:** high on the process facts; the replay's ranking of triggers is a hypothesis.

### F3 -- Five pre-registered bars were met or bypassed and not honoured on time.
- **Edge floor 0.3c** (AMENDMENT_1, 09-08): "if the live flip rate at the 0.3c floor exceeds 1.0% ... the floor returns to 0.5c." Live: **19 of 747 markets flipped, 2.5%** (2.4% since pin 0.995). Never reverted or re-registered. (Where the EV test binds, first fill 97.5-98c, 3 of 269 = 1.1%, +$101.10 -- so the floor may be fine; the point is the bar was never looked at.)
- **v-cheap** early edge cap (F1): met 09-20 03:44Z, ignored.
- **Band-mult 1.5x** (v-bands): "revert at the first boosted loss" met 09-19 16:30Z (BNB -$61.75, 83 contracts into 23 of depth); stayed live 15.5 h because the off-switch lived in memory and each restart re-armed it; it boosted again (XRP 09-20 04:59Z) after its own bar had fired.
- **PREREG_hedge** (above), twice.
- **PREREG_staged** stage 1 (30 paper closes) -- overridden at ~20 minutes, recorded as an override.
- **Money:** directly measurable only for v-cheap (-$94.31 on its 19 fills). The pattern is the finding: a bar that no code checks is not a bar.

### F4 -- At the pace changes went live, no single change since 09-12 can be judged from the money. (Question 3.)
- **52 behaviour-changing restarts 09-12 03:07Z .. 09-21 20:12Z** (start records + code-only changes). Per ET day: 09-12: 5, **09-13: 10**, 09-14: 5, 09-15: 1, 09-16: 1, 09-17: 5, 09-18: 3, **09-19: 13 (the -$161 day)**, 09-20: 5, 09-21: 3. Several restarts carried 2-3 changes at once.
- **Median change got 2.25 hours and 3 traded closes** before the next one. 34 of 52 got under 10 closes; 2 got 30+ (v-withdraw 09-15, 41; v-nocap 09-20, 47). Five 09-19 epochs had zero closes.
- **Measured detectability (358 traded closes since 09-13):** mean +$1.27/close, sd $11.39. Smallest difference detectable (80% power, 5% two-sided): 3 closes -> $18.42/close (14x the whole edge); 30 closes -> $5.82; 300 closes (8 days unchanged) -> $1.84, still bigger than the edge. Halving the loss rate (3.5% -> 1.75% of closes) needs ~1,300 closes per arm, **~34 days** at 39 traded closes a day.
- **So the -$161 and -$3 days cannot be pinned on any one change from P&L.** What can be read is mechanical: a gate that fired, a hedge that did not fill, a record that is missing.

### F5 -- The settings with real live evidence are the core, and they carry the profit.
- `pin` 0.995 (live since 09-10): index-measured with a holdout, then **487 closes / 666 markets / +$499.64** on the ledger. Main window 3-30 s: main-window-only markets since 09-17 +$117.67. 98c ceiling: arithmetic plus 523 closes. Hedge-slip: 29 real hedge attempts, 10 filled 0-1 contracts. These are the settings nobody should touch without a bar.

### F6 -- Smaller items that affect "identify better".
- **VERSIONS.md clock errors.** Eight entries written 09-18/19 (v-late10, v-thirdcoin, v-cheap, v-latebudget, v-nohedgeblock, v-panic40, v-late15, v-cap200) and the back-filled v-a17 give **ET clock times labelled Z**, 4 h early (v-late10 "~23:5xZ"; the first start with late_mult 1.5 is 09-19T04:03:58Z). Joining logs to versions by those times mis-attributes the closes of the worst day.
- **`external_detect` is known broken and live**: it invented a $58.37 withdrawal and deadlocked the bot ~2 h (CURRENT_STATE open item 3).
- **Configuration debt with nothing behind it** (each low stakes, each makes attribution harder): late 1.5x boost (fired 3 times ever, paper evidence void), `late_pin` 0.9975 (set just above the ONE losing signal), A68 flip-bet (n=6 closes, never fired), taper (one book), A38 (5 events, "IS NOT EVIDENCE" in its own entry), dump guard 15c (fitted on 9 fills), jump gate (7 live fills, promised arm comparison never validly scored), extra-coin (used on 4 of 126 closes).

## Table: every live setting and its evidence (question 1)

Live record = Kalshi ledger, every market whose first fill came after the setting's CURRENT value went live (so it includes everything deployed later -- no setting since 09-13 can be isolated, see Change velocity). Kinds: LIVE = our own fills; INDEX = 1/sec settlement index (valid for what the model computes); TAPE = market trade/book tape (valid for what the market did, never for our loss rate); REPLAY = a counterfactual re-simulation (pin.py / pinsim / hedgetune style) -- a hypothesis; PAPER = paper arm (void before 09-20 14:2xZ); PREF = operator preference / risk choice; REASON = mechanism argument only.

| setting (value now) | live since (UTC, start record) | evidence cited | kind | >=30 closes behind the CHOICE? | pre-registered bar? | live record since (closes / losing mkts / $) | verdict |
|---|---|---|---|---|---|---|---|
| confidence gate `pin` 0.995 | 09-10 08:33 (1 h at 0.990 on 09-13) | pinfirst: 10,796 markets, flip rate at the firing second, fit/holdout; 84 live fills (skips 3 of 5 losses) | INDEX + LIVE | yes (index); live 84 fills / 5 losses | no file; holdout yes | 487 / 22 / **+$499.64** | **Supported by live money** |
| main window tau 3-30 s | 09-08 15:38 | A4: order-book dataset by horizon; its comment calls 31-45 s "a measured wall ... do NOT extend past 30" | TAPE/REPLAY | yes | A4 prereg | 536 / 25 / +$484.76 (main-window-only markets since 09-17: 89 / 2 / +$117.67) | Supported by live |
| edge floor 0.3c after fee | 09-08 08:22 | pin.py backtest, 4 floors tried on the same 9 days, "1 flip in 359" | REPLAY | replay only | **yes, AMENDMENT_1: "revert to 0.5c if live flip rate >= 1.0%"** | 546 / 25 / +$484.97; live flip rate **19 of 747 markets = 2.5%** | **Bar breached 2.5x, never honoured** (gate went to 0.995 instead) |
| EV floor 0.3c with measured_flip 0.009 | 09-08 15:38 | "3 flips in 333 dear trades" OOS run | REPLAY | replay | AMENDMENT_2 | live flip 2.5% vs the 0.9% the EV test assumes | EV test assumes a flip rate 2.8x better than live |
| price ceiling 98c | 09-09 03:52 | recovery arithmetic (53 wins vs 89 to earn back one loss); 83 closes | REASON + LIVE | yes | no | 523 / 24 / +$525.57; 98-99c band when it was allowed: 82 mkts, 1 loss, +$51.07 | Supported (risk choice with arithmetic) |
| volatility ruler 300 s, sigma_stress 1.0 | 09-08 (ruler put back 09-13 18:49) | original design; the 09-13 ruler change was reverted because it cut signals 63% | REASON | -- | PREREG_sigma_live (09-21) is open for a BOLDER sigma | whole record | Default, never tested against an alternative on live money; paper says bolder is ahead (Paper arms) |
| dump guard 15c below fair | 09-11 12:45 | 9 live fills; "15c chosen after seeing 9 fills ... FITTED" | LIVE, n=9 | **no** | review at 40 records (28 `dumped` so far) | 436 / 20 / +$477.91; refused 19 times ever | Fitted, small n, low stakes |
| max-per-market 2, min-fill-frac 0, sweep, sweep-depth, depth-ladder, pick best, improve-scope market | 09-13 19:33 .. 09-14 15:53 | live logs: 58% budget use, the SOL ladder book, 28% zero-fill IOCs; pinpick (13,984 rows, 60/40 holdout) | LIVE + REPLAY | yes | A23/24 prereg | 285-324 / 13-14 / +$285 to +$356 | Mechanical ("same decision, filled"); reasonable |
| A38 against-us thin-edge refusal | 09-14 14:22 | **5 events** (4 winners $1.81, 1 loss $58); its own entry: "IS NOT EVIDENCE" | LIVE, n=5 | **no** | PREREG_against (30 closes) | refused 45 times; 288 / 13 / +$294.48 | Asymmetry argument; low stakes |
| jump gate 3 sd / 3 s | 09-15 01:39 | index: 17,811 jumps; live: 7 fills after a >3 sd move, 2 losers; both holdout halves +; bootstrap straddles 0 | INDEX + LIVE n=7 | index yes, live **no** | 3-day arm comparison promised for 09-17 -- arms could not hedge then, never validly scored | refused 82 times; 270 / 12 / +$255.41 | Mechanism measured on the index; effect on our money unproven |
| drawdown 20%, max-losses 2, loss cap $200 per ET day, max-positions 3 | 09-14 12:54 / 09-19 07:30 / 09-20 08:44 | "Evidence: none, and none was asked for" | PREF | n/a | n/a | -- | Risk choices. max-losses counts per RUN; the watchdog relaunches a halted bot after 15 min |
| **early leg: tau 45, FULL size** | 09-18 16:33 | tau-45 paper arm 27-33 closes, 0 losses (**pre-sync, unhedged: void**); **tape loss rates by market, 2.8% vs 3.9%**; index model error 0.058% vs 0.021%; 31 live markets at a third | PAPER(void) + **TAPE LOSS RATE** + INDEX | **no** on live at decision | PREREG_staged stage 2 (first 40 only): **passed, then bled** | early-leg markets since 09-18 16:33: **143 / 6 losing / -$108.01** | **Not supported: live record negative, the positive evidence was an artefact (F1)** |
| early min price 90c | 09-18 03:02 | A49 mechanism ("the market disagreeing where our model is weakest") | REASON | no | stage-2 count restarted (a bar reset) | see early leg | Unmeasured |
| **early max edge 10c** (was 3c) | 09-19 05:08 | operator: "get rid of whatever is blocking us from cheap trades" | PREF | no | **yes: revert at 2 losing closes in the first 40 early fills under 96c** | those fills: **19, 3 losing, -$94.31**; bar met at fill #9 | **Bar met 09-20 03:44Z, not honoured** |
| no early price ceiling (v-nocap) | 09-20 09:48 | "136 markets, +$110.67, 1.5% losing" | bot's own log, entry leg only | -- | no | ledger for the same 140 markets: **-$68.78, 5 losing**; since: early 62 mkts +$9.78 | **Evidence was an artefact (F1)** |
| late boost 1.5x inside 10 s | 09-19 04:03 | paper arm 49 mkts, 0 losses (**pre-sync, unhedged: void**); live 0-10 s window, 68 fills, 0 losing closes | PAPER(void) + LIVE window | window yes; **the 1.5x size never** | "cut at first loss" (in memory, re-armed by every restart) | boost fired **3 times** ever; <=10 s markets since 09-17: 11 / 0 / +$43.23 | Window supported; the 1.5x itself untested |
| late_pin 0.9975, late_jump 2.0 | 09-19 04:03 | 109 signals; the ONE loss sat at 99.612%, bar set just above it | LIVE, fitted to 1 event | no | no | refused the boost 5 times | Fitted to one loss |
| extra-coin 1, late-extra 1, late-extra-tau 15 | 09-19 04:03 / 05:08 / 06:58 | 417 closes, 19 with a losing coin, none with two (LIVE); close_budget refusal counts | LIVE | yes (for the safety condition) | no | 3+ coins at one close: **4 of 126 closes**, +$23.87 | Safety condition measured; benefit unmeasured |
| taper (A67) ON, flip-bet (A68) 1.0x | 09-19 18:01 | one BNB book (A67); **n = 6 closes** (A68) | LIVE n=1 / n=6 | no | no | A68 has **never fired**; 90 / 5 / -$41.76 since | Mechanism only |
| hedge-slip 3c, hedge tries 30, 120-attempt cap | 09-19 06:06 / 22:50 | 29 live hedge attempts, 10 filled 0-1 contracts against a book showing enough | LIVE | n/a (execution) | no | 82 / 4 / +$48.28 since the slip | Execution fix on live evidence |
| hedge-panic 0.40 | 09-19 06:20 | 8 hedges tabulated by belief | LIVE n=8 | no | no | now only bypasses attempt caps (no price gate left to bypass) | Mostly inert now |
| **bank-brake 4.00** (bet ~ bank / 7.84) | 09-20 05:46 | operator: "a quarter smaller"; "no correlation between size and daily money (-0.05, six days)" | PREF (+ 6 days) | no | no | 68 / 2 / +$97.28 | Risk choice |
| **hedge the full position at the alarm** (`--no-hedge-prop`) | 09-21 17:03 | 18 alarms re-priced against the book at the alarm second | **REPLAY on tape**, n=18 | **no** | "next 10 alarms" -- superseded 71 min later | -- | Hypothesis |
| **no hedge price gate** | 09-21 18:14 | operator: "last week's hedge"; the same replay says it is $9 WORSE in total | PREF against the replay | no | no | -- | Operator's choice, made knowingly |
| **hedge-belief 0.25** | 09-21 20:12 | hedgetune replay of 16 alarms; trigger chosen in-sample, leave-one-out | **REPLAY**, n=16 | **no** | **none; and below PREREG_hedge's "Not below 0.30" floor** | 1 alarm: HYPE 09-21 18:15 ET, real loss, hedge cut about -$54 to -$31.27 | Hypothesis; broke a pre-registered floor |
| external-detect (withdrawal classifier) | 09-15 04:19 | self-test cases | REASON | n/a | n/a | invented a $58.37 withdrawal and deadlocked the bot 2 h (CURRENT_STATE open item 3) | **Known broken, still live** |

Count: of 26 rows, **4 have live evidence behind the value that is running** (pin, main window, ceiling, hedge-slip execution) plus the mechanical fill-execution group; **2 have a negative live record and no valid positive evidence** (early leg full size / no ceiling; early edge cap 10c); **2 run past a pre-registered bar that fired** (edge floor, early edge cap); **3 rest on a replay of 16-18 events** (all three hedge settings deployed 09-21); the rest are small-n fits, void paper, reasoning or operator preference.

## Rule breaks: live changes vs the standing rules (question 2)

Rules checked: **R1** the replay/backtest is a hypothesis, not evidence (09-10, hardened 09-18); **R2** never quote a loss rate from the tape (09-11); **R3** 30 closes before calling anything (CLAUDE.md, from the start); **R4** no threshold from a replay without a holdout split AND a pre-registered live bar written first (09-10); **R5** a pre-registered bar is never moved or ignored quietly. "After" = what the live record did, Kalshi ledger.

| live change (UTC deploy) | rule(s) broken | how | what happened after |
|---|---|---|---|
| hedge 0.90 -> 0.80 (09-12 18:06) | none (compliant as then written) | replay holdout on 72 unseen hours + PREREG_hedge n=30 live bar | the n=30 live bar was never scored: 0.60 replaced it at 9 events |
| A20 / A20b volatility ruler (09-13 11:10 / 11:57) | R1-spirit (index population, not ours) | benefit measured on 108,000 index decisions; cost on our own signals | signals -63%; reverted 7 h later (v-revert1) |
| A21 pin 0.990 (09-13 17:51) | R3/R5 | a second change to buy back the first one's volume | reverted 58 min later |
| A38 against-us (09-14 14:22) | R3 | 5 events; its own entry: "IS NOT EVIDENCE AND MUST NOT BE QUOTED AS ANY" | refused 45 times; effect unmeasurable (low stakes) |
| jump gate (09-15 01:39) | R3 | 7 live fills, bootstrap straddles zero; the promised 3-day arm comparison ran on arms that could not hedge | refused 82 times; effect never scored |
| **hedge 0.80 -> 0.60 (09-16 13:57)** | **R3, R5** | 9 events, 0.60 chosen after seeing them; PREREG_hedge required 10 further events after 09-14, 0.30 favoured on those alone, no single event > half the gap -- not met | per the 09-21 replay (hypothesis), 0.60 was "the worst of every option, including not hedging": -$370 vs -$324 never, over 16 alarms |
| **v-staged early leg (09-17 13:05)** | **R3, R5 (recorded override)** | PREREG_staged stage 1 asked for 30 paper closes; deployed after ~20 minutes on a paper arm that could not hedge | early-leg markets lifetime: **202, -$59.00** (F1) |
| **early leg full size (09-17 19:41)** | **R2** | cited "buyers of 95-98c lost 2.8% at 31-45 s (606 markets) vs 3.9% at 16-30 s" -- a TAPE LOSS RATE, 6 days after the rule | 6 h later the 53c fill (-$27.87); operator reverted it to paper; re-deployed next day |
| early leg reopened, count restarted (09-18 03:02) | R5 | "the count restarts, because the size and the floor both changed" -- the stage-2 bar reset rather than scored | bar then passed its first 40, and the next 88 early closes lost -$145.73 |
| A50 early edge cap 3c (09-18 06:51) | R2, R3 | built on tape+paper rows (11 bets in the 6c+ cell); deployed ahead of its own PREREG_a50 arm | "A50 shipped BROKEN and refused our best trades all day" (16916de); then lifted to 10c |
| v-bands hedge-price 0.60 (09-18 22:46) | R3 | 9 hedged closes | blocked the BNB 01:45 ET hedge by the market-agreement test (-$57.98, "a $61 swing lost to a filter"); flag removed 09-21 after 3 of its 20 pre-registered waits |
| v-bands 1.5x at 90-94c (09-18 22:46) | R5 (bar honoured late) | bar "revert at the first boosted loss" was met 09-19 16:30Z (BNB -$61.75, 83 contracts into 23 of depth) | stayed live 15.5 h, the in-memory off-switch re-armed on each restart, and it boosted again (XRP 09-20 04:59Z) after its own bar had fired |
| late boost 1.5x + late_pin (09-19 04:03) | R3, void-paper | paper arm could not hedge; late_pin set just above the ONE losing signal | fired 3 times in 3 days; nothing to read |
| **v-cheap early edge cap 3 -> 10c (09-19 05:08)** | **R5** | bar written: revert at 2 losing closes in the first 40 early fills under 96c | **bar met at fill #9 (09-20 03:44Z), not honoured; 19 fills, 3 losing, -$94.31** |
| A67 taper / A68 flip-bet (09-19 18:01) | R3 | one book / "n = 6 closes, which is thin" | A68 never fired |
| **A76 proportional hedge + brake 4.0 (09-20 05:46)** | **R3, R4** | "+$40 better on the same 15 clusters that produced it. Below the 30-cluster floor" | first firing 09-21, NEAR **-$59.09**; removed after ONE event, its own "10 alarms" bar never used |
| v-earlycap 97.5c (09-20 09:11) | R3 | one motivating loss | removed 37 min later |
| **v-nocap (09-20 09:48)** | sources-of-truth rule (ledger is the authority) | used the bot's own log, entry leg only | same markets on the ledger: **-$68.78 not +$110.67** (F1) |
| **v-hedgefull (09-21 17:03)** | **R1, R3** | 18 alarms re-priced on the tape; bar "next 10 alarms" | superseded 71 min later |
| v-hedgelastweek (09-21 18:14) | (operator's explicit choice against R1's own replay) | replay said $9 worse in total; chosen for the loss cut | superseded 118 min later |
| **v-hedge25 (09-21 20:12)** | **R1, R3, R4, R5** | 16-alarm replay, trigger picked in-sample (leave-one-out, no holdout split), no live bar; **below PREREG_hedge's "Not below 0.30" floor** without mention | 1 alarm since (real loss; hedge cut ~-$54 to -$31.27) |

**Tally, 09-12 to 09-22:** 20 live changes broke at least one standing rule; **5 pre-registered bars were met or bypassed without being honoured on time** (edge floor 1.0% flip, PREREG_hedge 10-event / 0.30 floor twice, stage-1 staged, v-cheap under-96c, band-mult off-switch); 8 changes were reverted or superseded within 2 hours of going live. **Of the rule-breaking changes whose money can be read at all (the early leg family), the result was negative.**

## Change velocity (question 3)

See F4. Epoch table (behaviour-changing restart -> hours until the next -> traded closes -> $ on the ledger) is reproducible with scratchpad `map/07/epochs.py`; the headline rows:

| since (UTC) | change | hours | closes | losing mkts | $ |
|---|---|---|---|---|---|
| 09-15 04:19 | A43 withdraw | 33.6 | 41 | 2 | +$104.65 |
| 09-16 13:57 | hedge 0.80 -> 0.60 | 23.1 | 24 | 1 | +$76.66 |
| 09-19 04:03 .. 07:38 | 8 restarts (late 1.5x, third coin, brake 4.08->3.00->4.08->3.00, v-cheap, A62, panic .40, late-extra-tau, cap 200) | 3.6 total | 7 | 2 | -$104.44 |
| 09-19 18:01 | A67 taper + A68 | 2.35 | 5 | 1 | -$99.08 |
| 09-20 02:32 | A74 | 3.25 | 6 | 2 | -$88.40 |
| 09-20 09:48 | v-nocap (longest stable run) | 31.3 | 47 | 1 | +$53.79 |
| 09-21 20:12 | v-hedge25 | 10.3 (incl. 4 h 47 m outage) | 10 | 1 | -$10.38 |

Median epoch 2.25 h / 3 closes; 34 of 52 epochs under 10 closes.

## False results: what fooled us before, and whether it is in today's evidence (question 4)

A sub-agent read PROJECT_HISTORY.md, BIASES.md, THEORY.md, the memory files and ~85% of HANDOFF.md and catalogued **215 conclusions later withdrawn or corrected** (full table, sources and line numbers: scratchpad `map/07/false_results.md`). Counted by primary cause:

| rank | what fooled us | times |
|---|---|---|
| 1 | a unit / field / parse bug (incl. 3 ET-read-as-UTC) | 38 |
| 2 | a mechanism story, or a rail/gate assumed to work, never measured | 29 |
| 3 | too few closes / no power / one outlier close | 18 |
| 4 | wrong baseline (a peak day, a changed population, the wrong counterfactual) | 13 |
| 5 | a stale or mismatched paper arm | 9 |
| 5 | look-ahead | 9 |
| 7 | trades counted instead of closes; selection on outcome; wrong denominator | 8 each |
| -- | tape vs our fills; the replay | 5 and 2 -- **fewest by count, biggest by size**: tape 0.11% vs live 3.4% (31x); replay flip 0.79% vs live 8.8%; coin-race tape 0.4% vs penny 2 of 15 |

Repeat offenders: `realised` summed as if per-trade (4 times), the `_fp` field names (3), sequence/message ordering (4), paper-arm evidence voided (8).

**The same failure modes in the evidence behind today's live settings:**

| failure mode (from the history) | present in | how |
|---|---|---|
| our own log instead of Kalshi's books (dead-process rows and second legs missing -- memory "never quote a bank delta", `pinledger` 09-18) | **early leg kept at full size, ceiling removed (v-nocap)** | entry-leg-only settled rows: +$110.67; ledger -$68.78 (F1) |
| tape loss rate quoted as ours | **early leg full size (09-17)**, A50 edge cap | "2.8% vs 3.9% by market" |
| void paper arm | **early leg** (tau-45 arm), **late 1.5x boost** (49-market arm), jump-gate comparison | arms could not hedge and ran stale flags |
| too few events + chosen in-sample | **hedge-belief 0.25** (16), A76 (15, since removed), hedge 0.60 (9), dump guard 15c (9), A68 (6), A38 (5), `late_pin` (1 event) | threshold picked on the events that motivated it |
| the replay | **all three hedge settings of 09-21** | counterfactual priced on the tape; no lag test |
| a mechanism story, never measured | early min price 90c, taper, `late_jump`, extra-coin benefit | no live test designed |
| confounded by simultaneous changes | every setting since 09-13 (F4) | median 3 closes between changes |
| changed population / wrong baseline | hedge replays pool alarms from 20-contract (09-12) to 104-contract (09-20) positions and four different trigger/gate regimes | "18 alarms" are not one population |
| ET-read-as-UTC | VERSIONS.md deploy times (F6) | 9 entries 4 h off |

Four of the top five historical failure modes are present in the evidence for the two settings with the most money on them (early leg, hedge).

## Paper arms (question 5)

- **The promised summary of tonight's arm head-to-head is not in HANDOFF.md** (checked: the top section is the 09-22 outage write-up; no arm comparison dated 09-22). Not redone here; below is only which comparisons are valid and what the raw totals say.
- **Valid window 1: 09-20 14:2xZ (resynced ~15:30Z) .. 09-21 17:00Z (~25.5 h).** Arms were live's flags plus one change (verified by diffing each arm's `start` record against live's 09-20 09:48Z start). Live in the window: 55 markets / 39 closes / +$30.68 (ledger). Arm totals are PAPER settled P&L, same window:

  | arm (one change) | mkts / closes | paper $ |
  |---|---|---|
  | control (no change) | 62 / 42 | +$23.73 |
  | sigma_stress 0.4 / 0.6 / 0.8 | 92/54, 59/32, 52/29 | +$111.44, +$68.34, +$38.60 |
  | sigma_stress 1.25 / 1.5 / 2.0 | 28/24, 12/10, 5/5 | +$53.64, +$22.25, +$5.87 |
  | pin 0.97 / 0.975 / 0.98 / 0.985 / 0.99 | 54/28, 51/28, 48/27, 45/25, 70/44 | +$47.88, +$60.66, +$44.89, +$29.95, +$36.52 |
  | early leg OFF (tau 30) | 30 / 24 | +$37.00 |
  | early to 60 s | 92 / 52 | +$1.03 |
  | no hedge (belief 0.01) | 57 / 38 | -$0.46 |
  | hedge-prop off / hedge-price none / hedge-slip 0 | 60/41, 63/42, 61/41 | +$47.67, +$20.13, +$25.43 |
  | brake 3.0 / 6.0 | 59/39, 61/41 | +$21.75, +$35.35 |
  | 1.5x at 90-94c | 60 / 41 | -$38.72 |
  | arm-friday (09-18 settings, 13 differences) | 54 / 36 | +$70.94 |

- **What it says:** directionally the same two things as the live record -- more early leg earns less per close (early-off +$1.54/close, control +$0.56, early-60 +$0.02), and bolder confidence books more paper money. **What it cannot say:** at 24-54 closes the detectable difference is ~$5/close; every gap above is inside that. Paper books any offer it sees, so it has no adverse selection -- the exact thing that makes bolder settings look good (the 31x gap). And the inherited `--max-losses 2` truncated them: **the bold arms (pin 0.97-0.985, sigma 0.6 and 0.8) each took two losses live's gate refused** (ETH 09-20 15:30 ET and ETH 09-21 02:15 ET) and were halted at 06:16Z 09-21, so their totals cover ~15 of the 25.5 h; sigma 0.4, pin 0.99, early-60 and 1.5x halted at 16:46Z on the NEAR loss. A paper arm can kill an idea; it cannot deploy one (PREREG_tau45's own words).
- **Valid window 2: from 09-22 06:21Z** (after the resync). Under an hour old at writing; nothing to read.
- **Everything else is void:** before 09-20 (arms could not hedge; up to 16 stale settings), and 09-21 17:00Z .. 09-22 06:21Z (three hedge changes, no resync).

## 2. Refuted or not supported

- **Expected the confidence gate to be the weakly-evidenced core; it is the best-evidenced setting** (index holdout, then 487 live closes, +$499.64).
- **Expected the early leg to lose more often; it does not.** Flip rates are similar (6/202 vs 2/84) and prices are similar (96.44c vs 96.19c). Its deficit is in loss size, and the difference from the main window is not statistically established (13% chance the sign is noise).
- **Expected the hedge trigger change to have hurt already; no evidence either way** -- one alarm since 0.25, and it helped (about +$23 against staying naked).
- **Expected the 1.5x late boost and third-coin allowance to matter; they barely fire** (3 boosts and 4 three-coin closes in three days), so they are neither the cause of the losses nor a source of gains.

## 3. Could not measure, and why

- **The counterfactual of removing the early leg on live money.** The ledger records what we bought, not what the main window would have bought instead; paper can only say "fewer markets, similar direction".
- **Whether `hedgetune`'s trigger ranking survives a 1-2 s lag.** Needs the index and ticker tape for all 16 alarm windows; not run here (read-only brief, RAM budget), and it belongs to the hedge investigator.
- **The per-change effect of any of the 52 changes** -- the data cannot resolve it (F4), not a tooling gap.
- **PREREG_against's 30-close score and the dump guard's 40-record review** -- the scoring scripts were not run; the refusal counts (45 and 19) are all that is reported.

## 4. Solutions worth testing

1. **Honour the bar that already fired: `--early-max-edge` back to 3.0.** It is v-cheap's own pre-registered revert. Blocks: early-leg buys under ~96.5c (19 fills so far, -$94.31). Cannot block a hedge (entry gate only). Validate on live fills: early-leg $/close over the next 40 early closes against the main window's, from the ledger.
2. **Put the early leg back to a third** (PREREG_a50's own FAIL action), or off, and score it continuously. Blocks: two thirds of the 31-45 s position on ~70% of markets. Never touches a hedge. Validation: ledger $/close for early vs main, running, with a stop at a pre-written line -- not a first-40 gate.
3. **Freeze the live config for 300 traded closes (~8 days)** except bug fixes and a gate-blocks-a-hedge emergency. Blocks: new changes only. It is the only way any change becomes readable (F4); even then only differences above ~$1.84/close show.
4. **Make every pre-registered bar executable.** One script (or a `pindesk` panel) that recomputes each open bar from the ledger every close and alarms when one is met: edge-floor flip rate, v-cheap under-96c losses, early-leg running net, hedge 10-alarm bar. Persist off-switches to disk (the band-mult switch re-armed on every restart). Blocks nothing by itself.
5. **Write the missing bar for hedge-belief 0.25 now, before the next alarm:** e.g., over the next 10 alarms, hedged-close net vs the same close's entry leg alone (both from the ledger); revert to the last pre-registered value if behind. Add the 1-2 s lag test to `hedgetune` before any further trigger move.
6. **Money claims in VERSIONS.md must come from `pinledger`**, never from `settled` rows -- a `versioncheck` rule that fails an entry quoting a $ figure without naming the ledger. And correct the nine ET-as-Z deploy times from the start records.
