# results/INDEX.md -- what is in results/, by kind

Snapshot 2026-09-25 ~07:10Z. **1,937 files, 731 MB on disk.** Git: 1,687 tracked (365 MB in the checkout), 231 untracked (131 MB), 19 ignored (235 MB). Sizes move by the minute: live processes write here. Everything in the repo is UTC. For code, see `research/INDEX.md`; for the map, `REPO_MAP.md`.

**Do not move, rename or hand-edit anything a process writes** (live logs, state json, heartbeats, .out/.err, VERSIONS.md). Paths are hard-coded in .py and .ps1 files.

## By kind (top level only; subdirectories below)

| pattern | n | MB | git | written by / read by |
|---|---|---|---|---|
| pinrun-paper-<startUTC>.jsonl | 525 | 203 | 353 T, 172 U | paper arms (`pinrun.py --arm-name`); pinlab, bars, armh2h2 |
| pinpickoff_cache.json | 1 | 110 | ignored | pinpickoff; rebuildable |
| pintraj-live-<startUTC>.jsonl | 9 | 95 | ignored | live bot 1 Hz trajectory sampler |
| pinlook_<date>.json | 3 | 58 | tracked | pinlook -> pinlookweb; rebuildable cache |
| oilband_<series>.json | 10 | 21 | tracked | oilband.py output (09-18) |
| RESULTS_pinsignal_rows.jsonl, pinlevels_rows.jsonl, pinwarn_rows.json | 3 | 37 | tracked | row caches of 09-09..13 studies; rebuildable |
| pinexit_positions.jsonl, pinentry_rows.jsonl, pingrid_cache.json | 3 | 30 | ignored | row caches; rebuildable |
| arm-<name>.out / .err | 86+84 | 15 | 146 T, 24 U | paper-arm stdout; the .out names the arm's current log |
| pinrun-live-<startUTC>.jsonl | 137 | 14 | 126 T, 11 U | **live bot, one file per start** -- the money log |
| kalshi_volume_history.json | 1 | 11 | tracked | market volume history (09-18) |
| pinracearm-<arm>.jsonl / .out / .err | 6+6+7 | 8 | mostly T | coin-race paper arms (running) |
| pinracepenny-live.jsonl / .out / .err | 3 | 5 | tracked | **coin-race LIVE bot** (running) |
| wxwatch-, quakewatch-, rungwatch-<startUTC>.jsonl | 3 | 9 | untracked | watchers (running) |
| arm-restart-*.out/.err, restale-*.out/.err | 172 | 8 | tracked | stdout of arm relaunches 09-18..20 (retired) |
| pinracearm-<startUTC>.jsonl, pinracetest-*.jsonl | 18 | 3 | tracked | early coin-race arms / penny test (09-11..22) |
| cmdarm-*.jsonl, cmdlive-*.jsonl | 25 | 2 | mostly T | oil paper arm (running) / oil live test (stopped 09-18) |
| RESULTS_*.md / PREREG_*.md / other *.md | 64/29/58 | 2 | tracked | reports -- see below |
| RESULTS_*.txt, spotlead_*.txt, *_run.txt, VFY/verify txt | ~40 | 1 | tracked | raw stdout of 09-08..21 studies |
| run-<stamp>.log | 22 | 0.3 | tracked | run_when_away.ps1 analysis runs |
| *.log (boot_all, pinphone, pindesk, watch_bot, restart_bot.last) | 6 | 0.3 | tracked | ops logs, appended continuously |
| pinrun-live.pid, watch_bot.pid, *.heartbeat, cmdlive.stop | 7 | 0 | tracked | process state -- see below |
| pinrun-hwm/dayloss/live-size.json, kalshi_ledger.json, kalshi_transfers.json, lab_control.json | 6 | 0.5 | tracked | live state -- see below |
| *.html (pinboard, pindeck, pinmobile, when_heatmap, pin_report; dashboard ignored) | 6 | 1.3 | 5 T, 1 I | old one-page views (09-08..18) |
| *.py in results/ (_verify*.py, sigcheck, supplyclock, hedge_falsealarm) | 11 | 0.1 | tracked | one-off scripts that were saved beside their output |
| pin-paper-*, pinsmoke-*, run-dry-*, run-live-*.jsonl | 16 | 0.3 | tracked | first paper/live runs 09-07..08 (history) |

## Live money files -- the bot reads or writes these

| file | what | writer -> readers |
|---|---|---|
| `pinrun-live-<startUTC>.jsonl` | live 15-min bot log; newest = current run. Per-market money is `settled.pnl_c/100`; `settled.realised` is a running DAY total | pinrun --live -> pinday, pinattrib, pinver, pindesk, pinphone |
| `pinrun-live.out` / `.err` / `.pid` | live stdout / stderr / pid | pinrun -> restart_bot.ps1, watch_bot.ps1, pinflat, pindesk |
| `pinrun-hwm.json`, `pinrun-dayloss.json`, `pinrun-live-size.json` | bank high-water mark, day loss, contract size -- read at start | pinrun -> pinphone, watch_bot.ps1, arms (size) |
| `kalshi_ledger.json` | the books FROM KALSHI -- the money authority | pinledgerd -> pinledger, pinday, bars, pindesk, pinphone, pinracearm |
| `kalshi_transfers.json` | deposits/withdrawals FROM KALSHI (never infer them from bank deltas) | pinxfer |
| `pinracepenny-live.jsonl` | coin-race live bot log (5 contracts a leg) | pinracearm --live |
| `VERSIONS.md` | every live change, newest first, with revert command. **Parsed by versioncheck.py -- do not reformat** | humans -> versioncheck.py |
| `lab_control.json` | desktop app's pause/delete state for arms | pindesk |
| `*.heartbeat`, `watch_bot.pid` | liveness stamps (pinphone, pinledgerd, watch_bot) | -> pindesk, boot_all.ps1 |
| `pintraj-live-*.jsonl` | 1 Hz trajectory of every tracked market (ignored, tens of MB/day) | pinrun |

## Paper arms -- running at snapshot

The arm name is **not** inside a paper log. Current log of an arm: `results/arm-<name>.out` prints it. All logs of an arm across restarts: `pinlab.join_logs` (matches on the start record). Arm vs live, same markets: `results/cf_2026-09-24/armh2h2.py` (read `h2h`, not `diff`). Arms before 2026-09-20 could not hedge and differed from live in up to 16 settings -- their numbers are void.

| arm | current log |
|---|---|
| arm-afternoon | pinrun-paper-20260924T035152Z.jsonl |
| arm-brake3 | pinrun-paper-20260925T022733Z.jsonl |
| arm-btcd | pinrun-paper-20260925T022743Z.jsonl |
| arm-early-off | pinrun-paper-20260925T022729Z.jsonl |
| arm-edge2c | pinrun-paper-20260925T022739Z.jsonl |
| arm-fresh500 | pinrun-paper-20260925T022747Z.jsonl |
| arm-hourly-all | pinrun-paper-20260925T030630Z.jsonl |
| arm-lateadd-off | pinrun-paper-20260925T022736Z.jsonl |
| arm-live-frozen | pinrun-paper-20260925T063011Z.jsonl |
| arm-toxic | pinrun-paper-20260925T022751Z.jsonl |

Coin-race paper arms running: `pinracearm-{z3,gap075,racectl,raceedge0,racetau40}.jsonl`. Oil paper arms: `cmdarm-20260924T154014Z.jsonl`, `cmdarm-wide230.jsonl`. Watchers: `wxwatch-`, `quakewatch-` (09-24), `rungwatch-` (09-25). Retired arm stdout (`arm-<name>.out` not in the list above, `arm-restart-*`, `restale-*`) is history only.

## Reports (.md), newest questions first within each group

### Money record and state -- read before acting

- `VERSIONS.md` (09-25, 214K) -- every live change, newest first, with its revert command; parsed by versioncheck.py -- do not reformat
- `IDEA_LEDGER.md` (09-25, 7K) -- every money idea ever checked, one row each, never deleted

### Plans and scans, 2026-09-22 onward (current)

- `SECOND_INCOME_SCAN_2026-09-25.md` (09-25, 26K) -- SECOND INCOME SCAN -- 2026-09-25 (written 03:35 UTC, jobs still running)
- `SCALING_PLAN_2026-09-24.md` (09-25, 10K) -- Scaling plan -- what more money in the bank actually buys
- `MAKER_SIM_2026-09-24.md` (09-25, 21K) -- MAKER SIM 2026-09-24 -- two-sided 1-contract quotes at the touch, 10-90c, from the raw tape
- `IDEAS_2026-09-24.md` (09-25, 84K) -- IDEAS 2026-09-24 -- the hunt for new markets and new ways to earn
- `FEED_LEAD_2026-09-24.md` (09-25, 13K) -- Do the exchange books we record lead the CF print the bot trades on? -- 2026-09-24
- `FAR_RUNG_2026-09-25.md` (09-25, 17K) -- buying the far rungs of the hourly ladder at 99c
- `VM_PLAN_2026-09-24.md` (09-24, 32K) -- Moving the bot off the laptop and onto a cloud computer -- the plan
- `PROJECT_MAP_2026-09-22.md` (09-22, 6K) -- PROJECT MAP 2026-09-22 -- where the money went, verified
- `FREEZE_status.md` (09-22, 8K) -- FREEZE status -- 9/22 10:55 ET
- `FREEZE_2026-09-22.md` (09-22, 24K) -- FREEZE 2026-09-22 -- ~300 closes of one configuration, and the bars that judge it
- `EARLY_HINDSIGHT.md` (09-22, 14K) -- written by research/earlyhindsight.py

### Pre-registrations (bars written before the data)

- `PREREG_toxic.md` (09-25, 3K) -- "a FRESH offer while others are SELLING our side" -- written 2026-09-24 ~17:4xZ, BEFORE any arm ran
- `PREREG_fresh.md` (09-24, 3K) -- "no fresh offers with more than 20 s left" -- written 2026-09-24 ~08:1xZ, BEFORE the paper arm ran
- `PREREG_sigma_live.md` (09-21, 4K) -- PRE-REGISTRATION — moving `--sigma-stress` below 1.0 onto the live bot
- `PREREG_a52_jump_hedge.md` (09-18, 4K) -- PREREG -- A52: hedge on the JUMP, not on the belief
- `PREREG_a50_early_edge_cap.md` (09-18, 5K) -- PREREG -- A50: cap the EDGE on the 45-second leg, so it can be sized up
- `PREREG_tau45.md` (09-17, 8K) -- PRE-REGISTRATION -- BUY EARLIER: TAU_MAX 30 -> 45
- `PREREG_staged.md` (09-17, 5K) -- PRE-REGISTRATION -- AMENDMENT 46, STAGED EARLY ENTRY (tau 45, half a bet, top up at 30)
- `PREREG_onecoin.md` (09-17, 5K) -- PRE-REGISTRATION -- AMENDMENT 45, ONE-COIN DEPTH
- `PREREG_hedgeprice.md` (09-17, 4K) -- PRE-REGISTRATION -- AMENDMENT 47: THE MARKET MUST AGREE BEFORE WE PAY FOR INSURANCE
- `PREREG_commodity_live.md` (09-17, 5K) -- PRE-REGISTRATION -- THE COMMODITY PENNY TEST (`research/cmdlive.py`)
- `PREREG_hedge.md` (09-16, 26K) -- PRE-REGISTRATION -- AMENDMENT 15, the belief-collapse hedge
- `PREREG_race_arm4.md` (09-15, 2K) -- PRE-REGISTRATION -- Coin Race paper arm, ARM4 (fair value). Written 2026-09-15 ~22:40Z, before any arm4 bet.
- `PREREG_race_arm3.md` (09-15, 2K) -- PRE-REGISTRATION -- Coin Race paper arm, ARM3. Written 2026-09-15 ~21:40Z, before any arm3 bet.
- `PREREG_against.md` (09-14, 6K) -- was there any sign the 05:30 trade would go wrong?
- `PREREG_sweep.md` (09-13, 5K) -- PRE-REGISTRATION -- RACE HARDER: an IOC limit above the resting ask
- `PREREG_ruler.md` (09-13, 12K) -- PRE-REGISTRATION -- AMENDMENT 20, the volatility ruler
- `PREREG_pin_live_AMENDMENT_23_24.md` (09-13, 6K) -- PRE-REGISTRATION — AMENDMENTS 23 and 24
- `PREREG_honest.md` (09-13, 3K) -- PRE-REGISTRATION -- AMENDMENT 19, honest confidence
- `PREREG_coinrank.md` (09-13, 3K) -- PREREG -- is any coin genuinely safer than the others?
- `PREREG_coin.md` (09-12, 2K) -- PRE-REGISTRATION -- the SOL question. Written 2026-09-12 14:1xZ, before the data.
- `PREREG_pin_live_AMENDMENT_6.md` (09-08, 3K) -- AMENDMENT 6 — more bets, without more risk per bet
- `PREREG_pin_live_AMENDMENT_5.md` (09-08, 2K) -- > **WITHDRAWN 2026-09-08 16:20 UTC, BEFORE IT EVER TRADED.
- `PREREG_pin_live_AMENDMENT_4.md` (09-08, 2K) -- AMENDMENT 4 — extend the trading window from 20 to 30 seconds
- `PREREG_pin_live_AMENDMENT_3.md` (09-08, 3K) -- AMENDMENT 3 — scale in as the price improves, instead of one shot
- `PREREG_pin_live_AMENDMENT_2.md` (09-08, 3K) -- AMENDMENT 2 — replace the edge floor with an EXPECTED VALUE test
- `PREREG_pin_live_AMENDMENT_1.md` (09-08, 3K) -- AMENDMENT 1 to PREREG_pin_live.md — lower the edge floor 0.5c → 0.3c
- `PREREG_pin_live.md` (09-08, 5K) -- PRE-REGISTRATION -- pin, first live run (size 1)
- `PREREG_gold.md` (09-07, 4K) -- PRE-REGISTRATION — the gold cutoff test
- `PREREG_2_natgas.md` (09-07, 4K) -- PRE-REGISTRATION 2 — the first live rebate run

### RESULTS_* -- one per question

- `RESULTS_coinrace_2026-09-21.md` (09-21, 11K) -- The Coin Race, re-measured from the book — 2026-09-21
- `RESULTS_pickoff.md` (09-18, 4K) -- RESULTS -- the offers we would buy, and who gets them
- `RESULTS_cushion.md` (09-18, 2K) -- A minimum "distance from the strike" gate would have COST us money. Killed.
- `RESULTS_ceiling_volume.md` (09-18, 3K) -- Can we get MORE crypto trades? Yes -- and it is worth much less than it looks
- `RESULTS_attrib.md` (09-18, 10K) -- what each gate in the bot actually did
- `RESULTS_quiet.md` (09-17, 9K) -- RESULTS -- quiet markets: where the money is not, and where some still is
- `RESULTS_pinbefore.md` (09-17, 2K) -- ok: at 60 seconds the whole window is ahead and nothing has drifted yet
- `RESULTS_grid.md` (09-17, 36K) -- RESULTS -- the grid: who loses buying near-certainties, by seconds left and price; and the reversal screen
- `RESULTS_gemini.md` (09-17, 3K) -- Gemini: the best-shaped venue yet, and one wall left
- `RESULTS_dumpguard.md` (09-17, 4K) -- RESULTS -- the dump guard IS a hidden 85c price floor, but it has NOT cost $82
- `RESULTS_decay.md` (09-17, 7K) -- RESULTS -- is the market catching on? Yes, in one specific way, and it is measurable
- `RESULTS_commodity_firstloss.md` (09-17, 4K) -- The first commodity losses, and the defect that doubled them
- `RESULTS_commodities.md` (09-17, 5K) -- RESULTS -- the commodities method
- `RESULTS_actions.md` (09-17, 10K) -- RESULTS -- 2026-09-17 afternoon: what the grid, the pickoff tracker and the market-health work say to DO
- `RESULTS_racearb.md` (09-16, 2K) -- The Coin Race basket — real, tiny, and capital-hungry. PARKED, not killed.
- `RESULTS_fcm_b2c.md` (09-16, 3K) -- The GEN4 FCM US B2C API is the right product, and it is not FIX
- `RESULTS_cdna_venue.md` (09-16, 3K) -- Crypto.com / CDNA -- a second venue with the same mechanism. 2026-09-16.
- `RESULTS_cdna_key.md` (09-16, 3K) -- The Crypto.com agent key cannot reach prediction markets
- `RESULTS_warn.md` (09-14, 2K) -- does confidence warn before a flip?
- `RESULTS_flip.md` (09-14, 2K) -- can a hedge turn being wrong into a profit?
- `RESULTS_early.md` (09-14, 1K) -- the winning side's price before the last 30 seconds
- `RESULTS_select.md` (09-13, 19K) -- calibration or selection
- `RESULTS_ruler.md` (09-13, 11K) -- every way of measuring volatility, scored
- `RESULTS_pick.md` (09-13, 6K) -- first or best?
- `RESULTS_levels.md` (09-13, 18K) -- expected P&L per CONTRACT SIZE, and how far it scales
- `RESULTS_flood.md` (09-13, 3K) -- can we see a jump coming?
- `RESULTS_feed_BTC.md` (09-13, 2K) -- RESULTS_feed -- does our own index run ahead of the published one?
- `RESULTS_exit.md` (09-13, 18K) -- can we SELL the winner before it settles?
- `RESULTS_disagree.md` (09-13, 1K) -- do the exchanges disagreeing predict a blow-up?
- `RESULTS_contest.md` (09-13, 5K) -- did anyone else want the offer?
- `RESULTS_calib.md` (09-13, 4K) -- is the model's uncertainty the right width?
- `RESULTS_book.md` (09-13, 1K) -- does the order book warn of a jump?
- `_count_verdict.md` (09-12, 7K) -- 0. VERDICT — COUNT is a LIQUIDITY problem, and no threshold reaches it
- `RESULTS_tapegaps.md` (09-12, 34K) -- where the tape is SILENT, second by second
- `RESULTS_replay_rebuild.md` (09-12, 42K) -- the backtest rebuilt so that it takes our own trades
- `RESULTS_replay.md` (09-12, 37K) -- does the tape replay reproduce our own trades?
- `RESULTS_maker.md` (09-12, 50K) -- RESULTS — pinmaker: how to buy better (take vs rest)
- `RESULTS_entry.md` (09-12, 78K) -- how to know when NOT to buy
- `RESULTS_count.md` (09-12, 36K) -- why we trade nothing on half the certain closes
- `RESULTS_coin.md` (09-12, 39K) -- does the run of SOL losses mean anything?
- `RESULTS_coinrace.md` (09-11, 6K) -- The Coin Race — measured 2026-09-11
- `RESULTS_pinsignal_verify.md` (09-09, 8K) -- pinsignal_verify -- adversarial check of pinsignal.py
- `RESULTS_pinsignal.md` (09-09, 181K) -- pinsignal -- what, at ENTRY, separates the losers?
- `RESULTS_pinsize.md` (09-08, 25K) -- pinsize -- does sizing on confidence beat flat sizing?
- `RESULTS_pin.md` (09-06, 15K) -- go.py stage `pin`, automated run (research phase)
- `RESULTS_informed.md` (09-06, 13K) -- go.py stage `informed`, automated run (research phase)
- `RESULTS_strikes.md` (09-04, 4K) -- go.py stage `strikes`, automated run (research phase)
- `RESULTS_flow.md` (09-04, 16K) -- go.py stage `flow`, automated run (research phase)
- `RESULTS_proxy.md` (09-03, 6K) -- go.py stage `proxy`, automated run (research phase)
- `RESULTS_pathstats.md` (09-03, 13K) -- go.py stage `pathstats`, automated run (research phase)
- `RESULTS_openwindow.md` (09-03, 7K) -- go.py stage `openwindow`, automated run (research phase)
- `RESULTS_maker_go_20260903.md` (09-03, 9K) -- go.py stage `maker_go_20260903`, automated run (research phase)
- `RESULTS_leadlag.md` (09-03, 11K) -- go.py stage `leadlag`, automated run (research phase)
- `RESULTS_feeds.md` (09-03, 9K) -- go.py stage `feeds`, automated run (research phase)
- `RESULTS_cross.md` (09-03, 7K) -- go.py stage `cross`, automated run (research phase)
- `RESULTS_chain.md` (09-03, 17K) -- go.py stage `chain`, automated run (research phase)
- `RESULTS_voltiming.md` (09-02, 10K) -- go.py stage `voltiming`, automated run (research phase)
- `RESULTS_term.md` (09-02, 41K) -- go.py stage `term`, automated run (research phase)
- `RESULTS_surface.md` (09-02, 13K) -- go.py stage `surface`, automated run (research phase)
- `RESULTS_reconcile.md` (09-02, 7K) -- go.py stage `reconcile`, automated run (research phase)
- `RESULTS_patterntrade.md` (09-02, 3K) -- go.py stage `patterntrade`, automated run (research phase)
- `RESULTS_oos.md` (09-02, 13K) -- go.py stage `oos`, automated run (research phase)
- `RESULTS_implied.md` (09-02, 26K) -- go.py stage `implied`, automated run (research phase)
- `RESULTS_endgame.md` (09-02, 13K) -- go.py stage `endgame`, automated run (research phase)
- `RESULTS_calfit.md` (09-02, 8K) -- go.py stage `calfit`, automated run (research phase)

### Generated daily -- proposals, nothing measured; skip unless asked

25 files: `COLLIDE_<stamp>.md` (collide.py, ~08:48Z daily) and `LEADS_<date>.md` (a remote session with no data). Each opens by saying nothing in it was measured.

### Older briefs, plans, logs (before 2026-09-22)

- `cryptocom_fixapi_email.md` (09-17, 3K) -- Draft email to fixapi@crypto.com
- `WHEN.md` (09-16, 2K) -- hot and cold times for the pin
- `VALUE.md` (09-16, 2K) -- where the money actually comes from
- `STREAKS.md` (09-16, 1K) -- do the chances come in bunches?
- `CDNA_ACCESS_EMAIL.md` (09-16, 3K) -- CDNA trading access — the email, and where it goes
- `GROWTH_TRACK.md` (09-15, 12K) -- are we on track?
- `FINDINGS_20260914_overnight.md` (09-15, 38K) -- Overnight review — 2026-09-14, ~04:00–05:00 ET
- `BRIEF_FOR_OPERATOR.md` (09-14, 4K) -- Brief for the operator — written 2026-09-13 11:3x PM ET, to be read to him when he is back
- `TAX_SUMMARY.md` (09-13, 6K) -- Trading record for tax preparation
- `SKIM.md` (09-13, 100K) -- everything that matters, short
- `IDEAS_LOG.md` (09-12, 47K) -- Ideas log — every idea, what testing it got, what happened
- `OVERNIGHT.md` (09-08, 9K) -- 2026-09-07 into 2026-09-08
- `MORNING.md` (09-08, 4K) -- Morning report — 2026-09-08
- `LOSS_PLAN.md` (09-08, 8K) -- What happens when we lose — written BEFORE the first loss
- `FACTOR_PROGRAMME.md` (09-08, 6K) -- The factor programme — what sets the price we'll pay, recomputed every second
- `THE_PLAN.md` (09-07, 9K) -- THE PLAN — what to do with the $20, and what it would take to do better
- `FULL_PLAN_FOR_REVIEW.md` (09-07, 43K) -- THE GOLD CUTOFF TEST — everything, for independent review
- `BRIEF_FOR_REVIEW.md` (09-07, 22K) -- Kalshi liquidity-rebate project — state of evidence, 2026-09-07 05:40Z
- `REPLY_TO_CRITICS.md` (09-06, 8K) -- Reply to both critiques — 2026-09-06

## Subdirectories

- `map_2026-09-22/` -- the 09-22 whole-project map: 01..11 topic reports (money vs changes, edge, execution, hedge, gates, code/infra, evidence audit, coin race, market, loss autopsy, critic), BRIEF.md, plus verify/, autopsy/, doge2245/, missed/, race_earlier/, signature/ and (UNTRACKED) newedge/, race_ties/, size15/
- `overnight/` -- 27 overnight adversarial reviews (account forensics, attacks, capital ruin, cross-venue, fees, funding)
- `INFRA_2026-09-23/` -- why the recorders/trackers break: A_inventory, B_diagnosis, C_plan
- `cf_2026-09-24/` -- per-second rebuild used for price rules (cf_build/cf_sim, cf_dataset.jsonl.gz), toxicity.md, feed_lead_tables.md, **armh2h2.py** (arm vs live)
- `audit/` -- 62 files: 09-08 AUDIT/AUDIT2 verification scripts + AUDIT2_p3_verdict.md
- `_verify/` -- 09-08..10 VFY_*.txt outputs + vfy_*.py
- `pindraw/` -- 09-09 hedge-vs-drawdown study: FOLLOWUP.md, REPORT.md (**ignored** by the root `REPORT.md` rule), state.pkl 17 MB
- `pindata/, pindata_fixed/, pindata_long/` -- 09-08..10 factor datasets rows.jsonl (15 + 28 + 1 MB, tracked); built by pindata.py
- `opp/` -- 20 MB: 09-0x opportunity aggregates (agg_loose/strict.json, ep_<date>.json, REPORT_loose/strict.txt)
- `sandbox/` -- tool/Builder profile runs (09-11)
- `_attic/` -- pending deletion; README says nothing here is load-bearing

