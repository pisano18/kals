# research/INDEX.md -- every .py in the repo, one line each

Generated 2026-09-25 ~07:10Z from docstrings, imports (ast), `*.ps1` references and the live process table. **Read this instead of opening files.** Statuses are a snapshot: a process started or stopped since then is not reflected -- the process table is the truth (query in REPO_MAP.md).

Columns: file | KB | purpose (from the docstring) | who uses it. `imp:` = imported by (LIVE importers named first); `run:` = named by a .ps1/.cmd; `go stage` = in research/go.py STAGES. Paths are `research/` unless shown. Root `*.py` are listed with their root path.

Counts: LIVE 32, OPS 21, ANALYSIS-CURRENT 21, ANALYSIS-DONE 187, DEAD 30.

## LIVE -- running now, or imported by something running

Editing one of these changes a money process at its next restart. Run `python research/versioncheck.py` and follow CLAUDE.md's version rule. `lib` = imported, not run.

| file | KB | purpose | used by |
|---|---|---|---|
| (root) crypto_feeds.py | 18 | Record the INPUTS to the settlement index. | RUNNING as C:\kals copy (run_all.ps1); deploy = copy file / run: boot_all.ps1,run_all.ps1 |
| (root) kalshi_collector.py | 18 | Phase 1. Record everything, trade nothing. | RUNNING as C:\kals copy (run_all.ps1); deploy = copy file / run: boot_all.ps1,run_all.ps1 |
| bars.py | 59 | [lib] every running test against the bar written for it BEFORE its data. | cited in sync_arms.ps1 comments / imp: LIVE pinphone |
| cdc_record.py | 8 | record Crypto.com's DCM prediction market, read-only. | RUNNING as C:\kals copy (boot_all.ps1) / run: boot_all.ps1 |
| cmdarm.py | 36 | THE COMMODITIES PAPER ARM. Nothing is ever ordered. | RUNNING: 2 oil paper arms (boot_all.ps1) / run: boot_all.ps1 / imp: cmdlive |
| downtime.py | 8 | [lib] hours the live bot could NOT trade, so a bad day is not | imp: LIVE pinday,pindesk,pinflat,pinpickoff,pinrun,rungwatch; barcheck,earlyhindsight,pinboard,pindeck +4 |
| engine.py | 29 | [lib] decision maths: var_factor, N_AVG, fee_per_contract, tick_at | imp: LIVE pinrun,pinrun_afternoon; _gatecheck_dt,_gatecheck_dt2,_gatecheck_dt3,acvar +79 |
| idxload.py | 7 | [lib] NEW FILE. Dense, cached loader for cfbenchmarks_value. | imp: LIVE pinracefair,pinracemodel,pinraceno; cdcedge,empcheck,empdiag,empfair +15 |
| kauth.py | 3 | [lib] Kalshi RSA request signing / auth headers for REST and WebSocket | imp: LIVE cmdarm,livebook,pinledger,pinledgerd,pinracearm,pinrun,pinrun_afternoon,pinxfer,quakewatch,rungwatch,wxwatch; cmdlive,densample,earlypull,lipscore +20 |
| livebook.py | 69 | [lib] real-time Kalshi order book over the WebSocket (the bot's eyes) | imp: LIVE cmdarm,pinracearm,pinrun,pinrun_afternoon; cmdlive,pinracetest,pinrun913,pinsmoke +5 |
| ordercli.py | 25 | [lib] the ONLY file that sends a non-GET order; post_only, --live + sign-off token | imp: LIVE pinledger,pinledgerd,pinracearm,pinrun,pinrun_afternoon,pintake; cmdlive,goldquote,pinhourly,pinrun913 +6 |
| pinbrief.py | 16 | [lib] the daily briefing, in one place, in plain words. | imp: LIVE pinphone |
| pinday.py | 40 | [lib] what we made, by EASTERN day. The one place that answers it. | imp: LIVE pinledger,pinphone; cmdlive,earlyhindsight |
| pindesk.py | 264 | the desktop app. START / PAUSE / STOP, and what an owner needs to see. | RUNNING: desktop app (pythonw); START/PAUSE/STOP / cited in watch_bot.ps1 comments / imp: LIVE bars,pinbrief,pinphone; pinfloor,pinlook,pinmobile |
| pinflat.py | 16 | [lib] is the live bot holding a bet right now? One answer, one source. | run: restart_bot.ps1 / imp: LIVE bars,cmdarm,pindesk,pinphone,pinpickoff,pinrun; barcheck,cmdlive,oilband,pingrid,pinlook |
| pinlab.py | 163 | [lib] the drawing board: every experiment, what it means, where it got to. | imp: LIVE pinbrief,pindesk; pinmobile |
| pinledger.py | 16 | [lib] the books, taken from KALSHI, not from our own logs. | imp: LIVE pinbrief,pinday,pindesk,pinledgerd,pinphone,pinracearm; barcheck,earlyhindsight,pinmobile |
| pinledgerd.py | 4 | keep `results/kalshi_ledger.json` fresh, forever. | RUNNING: ledger refresher (boot_all.ps1) / run: boot_all.ps1 |
| pinphone.py | 110 | the bot in your pocket: a Telegram bot you message. | RUNNING: Telegram bot (boot_all.ps1) / run: boot_all.ps1 / imp: LIVE bars |
| pinpickoff.py | 23 | [lib] the offers we would buy, and who gets them. | imp: LIVE pinsupply |
| pinracearm.py | 165 | Coin Race bot: paper by default; --live trades real money since 09-21 (docstring says nothing is ever sent) | RUNNING: coin-race live (--live, pinracepenny-live) + 5 paper / run: boot_all.ps1,start_arms.ps1 |
| pinracefair.py | 25 | [lib] a real probability for every Coin Race leg, and a test of | imp: LIVE pinracearm; raceclose,racegrid,racemaker,racenoearly,racerho |
| pinracemodel.py | 25 | [lib] the Coin Race forecast, VALIDATED against Kalshi's own | imp: LIVE pinracearm,pinracefair,pinraceno; raceclose,racegrid,racemaker,racenoearly,racerho |
| pinraceno.py | 18 | [lib] THE FOUR LEGS NOBODY HAS EVER PRICED. | imp: LIVE pinracefair |
| pinrun.py | 1132 | THE LIVE BOT (pin strategy). --live = real money; else paper arm. 1.1 MB: grep it, never Read whole | RUNNING: live bot (1x --live) + 9 paper arms (--arm-name) / run: boot_all.ps1,restart_bot.ps1,restart_stale_arms.ps1,start_arms.ps1,start_bands.ps1,start_early60.ps1,start_missing.ps1,start_sigma.ps1,sync_arms.ps1 / imp: LIVE pinracearm; hedgetune,pinattrib,pinbank,pincalib +19 |
| pinrun_afternoon.py | 940 | frozen copy of pinrun.py from 09-23 afternoon (docstring still says pinrun.py) | RUNNING: paper arm-afternoon (frozen 09-23 code) |
| pinsupply.py | 32 | [lib] is the opportunity actually going away, and what moves it? | imp: LIVE pinbrief,pindesk |
| pintake.py | 83 | [lib] the taker order path (IOC limit at the seen price) used by pinrun/pinracearm | imp: LIVE pinledger,pinledgerd,pinracearm,pinrun,pinrun_afternoon; cmdlive,pinhourly,pinracetest,pinrun913 +6 |
| pinxfer.py | 11 | [lib] every dollar that entered or left the account, FROM KALSHI. | imp: LIVE pindesk |
| quakewatch.py | 41 | READ-ONLY shadow watcher for the biggest-quake lock | RUNNING: quake watcher |
| rungwatch.py | 44 | READ-ONLY depth watcher for the FAR rungs of Kalshi's hourly | RUNNING: far-rung watcher |
| wxwatch.py | 43 | READ-ONLY shadow watcher for the hourly temperature "pin" | RUNNING: weather watcher |

## OPS -- checks, pipeline, operator tools

Run on demand or by a .ps1. Not research questions.

| file | KB | purpose | used by |
|---|---|---|---|
| (root) kalshi_fulltape.py | 27 | Remove the truncation bias and settle D properly. | run: run_when_away.ps1 / settlement pull, writes C:/kals/fulltape |
| collide.py | 13 | force facts that live apart into the same sentence. | writes results/COLLIDE_*.md |
| deploycheck.py | 7 | the deployed copies must match the repo. | checks C:\kals copies == repo |
| doctor.py | 26 | [lib] read the real collector output and tell the truth about it. | go stage / imp: book,flow,replay / writes schema.json the loaders read |
| go.py | 32 | one command. Runs everything in order, writes one report. | run: run_when_away.ps1 / imp: earlyhindsight / analysis pipeline runner |
| markers.py | 10 | a stage must not SAY it loaded nothing unless it did. | go.py preflight |
| newseries.py | 9 | is the collector actually recording what we told it to? | collector check |
| pinclock.py | 8 | is this machine's clock still telling the truth? | clock check |
| pindash.py | 76 | the bot's whole life in one page you can open yourself. | imp: pinhealth / idle; writes results/dashboard.html |
| pindeck.py | 21 | the flight deck. One page an owner can glance at. | run: open_deck.cmd / idle |
| pinmobile.py | 29 | the desktop tool, as one page you can open on a phone. | idle; superseded by pinphone |
| pinsettle.py | 6 | refresh settlements WITHOUT pulling the trade tape. | settlement refresh |
| pintax.py | 28 | a complete, auditable record of every trade, for a tax advisor. | tax record |
| pintool.py | 34 | the local server behind the tool (Live / Builder / Profiles / Learn). | idle; serves tool/index.html |
| pinver.py | 19 | everything the live log knows about ONE version of the bot. | per-version live summary |
| poly/poly_ws_record.py | 4 | READ-ONLY Polymarket US WebSocket book recorder (docstring says scan_poly_ws.py) | Polymarket recorder (runs from scratch as scan_poly_ws.py) |
| shadow.py | 26 | does any file in this repo shadow a standard-library module? | run: run_when_away.ps1 / go.py preflight |
| sweep/sweep_catalogue.py | 12 | build the market catalogue the money-idea sweep reads. | money-idea sweep (research/sweep/README.md) |
| unbound.py | 16 | names a function reads but never binds, across the repo. | go.py check |
| versioncheck.py | 6 | a live flag with no version entry is an error. | run in any session that touches the live bot |
| whatate.py | 19 | WHAT ATE MY DISK? Read-only. This program does not delete, move, or modify anything. It measures | disk check |

## ANALYSIS-CURRENT -- touched since 2026-09-17

Recent research or tools behind an open question (bars, arms, sweeps). Check OPEN_WORK.md before re-running.

| file | KB | purpose | used by |
|---|---|---|---|
| barcheck.py | 105 | the 2026-09-22 FREEZE's pre-registered bars, checked against | - |
| earlyhindsight.py | 123 | the 31-45 s "early" leg at a THIRD, at FULL size, or | cited in restart_bot.ps1 comments |
| hedgetune.py | 19 | where to set the hedge trigger, and how much to buy. | cited in restart_bot.ps1 comments |
| makersim.py | 78 | a MEMORY-BOUNDED, streaming queue simulation of the two-sided | - |
| oilband.py | 30 | where the money in oil actually is, by price and by clock. | - |
| pinattrib.py | 58 | [lib] what did each individual gate in the bot actually DO? | imp: oilband,pindash,pinlook |
| pinbefore.py | 9 | what if we bought EARLIER than 30 seconds? | - |
| pincheap.py | 12 | HOW MUCH CHEAP SUPPLY IS THERE, per day and per week. | - |
| pinfloor.py | 18 | why the money fell: the depth floor moves with the bank. | - |
| pingrid.py | 30 | what buyers of near-certainties actually lose, by series, by | - |
| pinlook.py | 20 | every opportunity, second by second, with our decision beside it. | imp: pinlookweb |
| pinlookweb.py | 16 | turn a pinlook day into something a human can actually browse. | - |
| pinproject.py | 8 | an honest compounding projection, with the measured ceiling. | - |
| poly/poly_ws_report.py | 10 | report on the Polymarket recording (docstring says scan_poly_ws_report.py) | - |
| racebook.py | 31 | [lib] the Coin Race basket constraint, measured on the live book. | imp: hedgetune,raceclose,racegrid,racemaker +2 |
| raceclose.py | 28 | the last twenty seconds of a Coin Race, and what is resting | - |
| racegrid.py | 17 | price every Coin Race second ONCE, then sweep every rule. | - |
| racemaker.py | 26 | what the OTHER side of every Coin Race trade earned. | - |
| racenoearly.py | 47 | is there money in buying a Coin Race NO EARLY? | - |
| racerho.py | 19 | the correlation the Coin Race book is implying, against the | - |
| rungtrades.py | 14 | READ-ONLY: how much far-rung SAFE-SIDE supply was actually | - |

## ANALYSIS-DONE -- question answered, kept as evidence

Last touched before 2026-09-17. The answer is in results/ (see results/INDEX.md) or HANDOFF/PROJECT_HISTORY. `[lib]` = imported by 3+ files; do not delete.

| file | KB | purpose | used by |
|---|---|---|---|
| (root) kalshi_brti.py | 11 | Get the REAL index prices behind every settled window. | - |
| (root) kalshi_gate1.py | 9 | THE GATE. Does our settlement reconstruction match Kalshi's? | - |
| (root) kalshi_signals.py | 11 | Mine the fields I threw away. python kalshi_signals.py --out ./fulltape | - |
| _verify/t1_timing.py | 5 | Independent re-derivation of the timing claim, from raw files only. | - |
| _verify/t2_load.py | 3 | Independent load: BRTI index + BTC replica (wmid AND coinbase mid), whole tape. | - |
| _verify/t3_settle.py | 10 | Independent re-run of the DECISIVE settlement test, plus the economic | - |
| _verify/t4_cents.py | 7 | How many CENTS does the spot lead move the fair value, ON THE CLOSES WHERE | - |
| _verify/t5_size.py | 6 | How OFTEN does the spot lead move the quoted price at all, how many | - |
| _verify/t6_depth.py | 9 | Two checks on the DEPTH study. (1) Re-derive its headline conditional-quantile lifts straight fro... | - |
| _verify/t7_scale.py | 7 | Is the depth study's conditioning worth anything ON TOP of simply fixing the | - |
| _verify/t8_gate.py | 9 | THE DECISIVE ECONOMIC TEST FOR pin's FROZEN RULE. pinrun.py fires only when the model's fair valu... | - |
| _verify_pindraw.py | 14 | ADVERSARIAL verification of pindraw/pindrawq/pindrawcase. | imp: _verify_pindraw2 |
| _verify_pindraw2.py | 8 | the controls pindraw.py did not run. THE MISSING NULL. pindraw's null world prices the hedge at i... | - |
| _verify_pindraw3.py | 6 | the 2026-09-09 case under the rule the AGGREGATE | - |
| _verify_pinmatch.py | 10 | ADVERSARIAL VERIFICATION of research/pinmatch.py. The three things pinmatch.py did NOT test: | - |
| _verify_pinmatch_jump.py | 4 | Is 'the shape predicts a large move' anything more than 'sigma_300 is | - |
| acgapchk.py | 6 | could the measured index autocorrelation be a GAP artefact? | - |
| acrun.py | 30 | run acvar's questions against the real tape. | - |
| acvar.py | 20 | IS THE WHITE-NOISE ASSUMPTION INSIDE THE VARIANCE MODEL TRUE? | imp: acgapchk,acrun |
| avgfeed.py | 45 | [lib] IMPROVEMENT 4 -- Kalshi publishes its own rolling 60s mean; use it. | imp: avgfeed_latency,avgfeed_m1,avgfeed_round |
| avgfeed_latency.py | 2 | Leak-check on the --strict-rx gate itself. --strict-rx admits a message when _rx_ms <= (close-tau... | - |
| avgfeed_m1.py | 6 | M1 residual: where does the exchange's OWN published 60s mean at the close | - |
| avgfeed_round.py | 4 | Is Kalshi's settle = ROUND-HALF-UP of the exchange's own 60s mean? | - |
| book.py | 34 | [lib] rebuild the real order book from orderbook_snapshot + delta. | go stage / imp: cross,flow,implied,openwindow +3 |
| calfit.py | 22 | ONE number for the whole calibration curve. | go stage / imp: oos |
| calib.py | 29 | is the calibration edge real, or is it which side traded? | go stage / imp: patterntrade |
| cdcalive.py | 6 | when is there actually a market to trade? The claim I made to the operator this morning, off one... | - |
| cdcbook.py | 5 | what the Crypto.com book actually looks like into expiry. | - |
| cdcchain.py | 8 | does OUR index reproduce THEIR settlement, to the cent? | - |
| cdcedge.py | 10 | [lib] would the pin strategy have worked on Crypto.com's binaries? | imp: cdcalive,cdcbook,cdcchain,cdcfair |
| cdcfair.py | 16 | would a strategy have made money on Crypto.com's binaries? | - |
| chain.py | 57 | everything you can learn WITHOUT the index feed. | go stage |
| cross.py | 16 | turn the 12-series correlation from a liability into an asset. | go stage |
| densample.py | 7 | log the LIP qualifying denominator, live, once a minute. | - |
| early.py | 10 | IMPROVEMENT 5: trade EARLIER, on an arithmetic lock. | imp: earlyrun,earlyself |
| earlybook.py | 8 | [lib] top-of-book WITH RESTING SIZE on a tau grid, per market. | imp: early,earlycross,earlydir,earlylag +2 |
| earlycross.py | 5 | a book-free test of whether the ticker touch is real. | - |
| earlydir.py | 5 | WHICH SIDE IS WRONG: the ticker channel, or the rebuild? | - |
| earlyidx.py | 4 | build a compact second-indexed cache of the settlement index. | imp: early,earlym |
| earlylag.py | 5 | WHY the ticker grid and the delta rebuild disagree. | - |
| earlym.py | 8 | M(index, tau): the largest move this index has ACTUALLY made. | imp: early,earlyrun |
| earlypull.py | 3 | READ-ONLY settlement pull with FULL strike precision. | - |
| earlyrun.py | 15 | the measurements and the backtest for IMPROVEMENT 5. | - |
| earlyself.py | 6 | the self-test gate for early.py / earlyrun.py. | imp: earlyrun |
| earlyverify.py | 7 | [lib] IS THE ticker CHANNEL REALLY THE TOP OF BOOK? | imp: earlydir,earlylag,earlyverify2 |
| earlyverify2.py | 6 | validate the ticker top-of-book AFTER repairing the | - |
| edge.py | 31 | [lib] model vs market. The only question that matters. | imp: calib,informed,maker |
| empcheck.py | 8 | NEW FILE, READ-ONLY. Reconcile empfair's fast machinery | - |
| empdiag.py | 5 | NEW FILE, READ-ONLY. WHY does the empirical estimator beat the | - |
| empfair.py | 21 | [lib] NEW FILE, READ-ONLY. Replace the bell curve with the index's | imp: empcheck,empdiag,empscore,empsig |
| empscore.py | 19 | NEW FILE, READ-ONLY. Score the Gaussian fair value against | imp: empcheck,empsig |
| empsig.py | 6 | NEW FILE, READ-ONLY. Is the Gaussian's miscalibration bigger | - |
| endgame.py | 62 | [lib] the LAST sixty seconds. The mirror of openwindow.py. | go stage / imp: informed,pin,pinbefore,pinselect +2 |
| feeds.py | 22 | the largest unexploited asset in this project. | go stage / imp: crypto_feeds,proxy |
| flow.py | 69 | the order book, streamed. Does order flow predict the next move? | go stage |
| gzsalvage.py | 12 | [lib] read the collector's gzip files even when a restart broke them. | imp: avgfeed,avgfeed_m1,book,cdcbook +26 |
| implied.py | 41 | [lib] stop asking "is the market wrong". Ask what the market believes. | go stage / imp: reconcile,term,voltiming |
| informed.py | 53 | the taker's trade is the signal. Who is informed, and when? | go stage |
| leadlag.py | 15 | does the contract FOLLOW the index? The #1 candidate edge. | go stage |
| lipcheck.py | 4 | ARTEFACT CHECK on the LIP slice. The slice is share = S / (total_score + S). If my delta-reconstr... | - |
| lipscore.py | 5 | The LIP score with the TAPERED TICK, which my first implementation got wrong. | - |
| lipslice.py | 6 | Our realistic slice of Kalshi's Liquidity Incentive Program, MEASURED. | - |
| maker.py | 32 | can you QUOTE these markets rather than cross them? | go stage |
| oos.py | 22 | WALK-FORWARD. What you would have made, trading it live. | go stage |
| opening_value.py | 7 | "every window opens at exactly 50c by construction" is false. | - |
| openwindow.py | 16 | the first sixty seconds. H5, done the way it should have been. | go stage |
| pathstats.py | 23 | is the contract price a martingale in its own right? | go stage |
| patterntrade.py | 15 | trade the one calibration pattern that survived. | go stage |
| pin.py | 59 | the pinned endgame: harvesting quotes the settlement math has | go stage |
| pinadverse.py | 7 | why does "certain" lose more than "nearly certain"? | - |
| pinalarm.py | 68 | once we are ALREADY in a position, does the trajectory of our | imp: pinalarmverify |
| pinalarmverify.py | 32 | ADVERSARIAL verification of research/pinalarm.py. | - |
| pinarb.py | 12 | the five legs of a Coin Race must sum to exactly $1. Do they? | - |
| pinbank.py | 20 | how much bank a given contract SIZE needs, and the inverse. | - |
| pinboard.py | 19 | one page: when the chances come, what they are worth, and | - |
| pinbook.py | 20 | does the ORDER BOOK on the source exchanges warn of a jump? | - |
| pinbooktrend.py | 9 | the KALSHI order book, day by day: is it getting deeper | - |
| pincal.py | 18 | IS THE MODEL CALIBRATED AT THE GATE pin ACTUALLY TRADES? | imp: empfair |
| pincalib.py | 33 | [lib] IS THE MODEL'S UNCERTAINTY RIGHT, AND WHEN DID IT STOP BEING? | imp: pinbook,pindis,pinflood,pinruler +2 |
| pincap.py | 5 | what is ACTUALLY capping the live bot's earnings? | - |
| pinclose.py | 78 | ARE WE PLAYING TOO CLOSE TO THE LINE? | - |
| pincoin.py | 90 | IS SOME COIN'S INDEX STRUCTURALLY JUMPIER THAN THE OTHERS? | - |
| pincontest.py | 56 | DID ANYONE ELSE WANT THE OFFER WE WOULD HAVE TAKEN? | - |
| pincount.py | 97 | WHY WE TRADE NOTHING ON HALF THE CLOSES THE MODEL IS SURE OF. | - |
| pincross.py | 25 | [lib] IS TROUBLE VISIBLE IN THE OTHER TEN COINS? | imp: pincoin,pincontest,pincount,pinentry +14 |
| pindata.py | 17 | [lib] build the ONE dataset every factor test needs. | imp: pincoin,pincount,pinentry,pinexit +10 |
| pindepth.py | 7 | is a THIN offer a warning? | - |
| pindis.py | 12 | DOES THE EXCHANGES DISAGREEING PREDICT A BLOW-UP? | - |
| pindisc.py | 36 | does DISCOUNT TO FAIR predict flips, once PRICE is held fixed? | - |
| pindiversify.py | 10 | do the Coin Race and the up/down pin LOSE AT THE SAME TIME? | - |
| pindraw.py | 61 | [lib] the hedge, re-run against DRAWDOWN instead of expected value. | imp: _verify_pindraw,_verify_pindraw2,_verify_pindraw3,pindrawcase,pindrawq |
| pindrawcase.py | 8 | replay ONE close, second by second, with the hedge rules. | imp: _verify_pindraw3 |
| pindrawq.py | 12 | follow-up queries on the cached pindraw state. | - |
| pinearly.py | 11 | what price is on offer BEFORE the last 30 seconds, and would | - |
| pinedge.py | 8 | are our THIN trades actually making money? | - |
| pinentry.py | 86 | HOW TO KNOW WHEN NOT TO BUY. | - |
| pinexit.py | 63 | CAN WE SELL THE WINNER BEFORE IT SETTLES, OR ONLY WHEN IT | imp: pinexit_run |
| pinexit_run.py | 52 | the real-data half of pinexit.py. Kept in its own file so that ` | - |
| pinfeat_book.py | 9 | FEATURE FAMILY 2: the order book as a risk signal. | - |
| pinfeat_np7_idx.py | 6 | build a compact 1-second index cache from | - |
| pinfeat_path.py | 14 | FEATURE FAMILY 4: THE SHAPE OF THE PATH, NOT ITS VOLATILITY. | - |
| pinfeat_regime.py | 14 | NEW FILE, READ-ONLY. FEATURE FAMILY 6: time, regime | - |
| pinfeat_vol.py | 17 | FEATURE FAMILY 1: better volatility estimators for p_flip. | - |
| pinfeed.py | 24 | DOES OUR OWN INDEX RUN AHEAD OF THE ONE WE SETTLE AGAINST? | imp: pindis |
| pinfill.py | 5 | what fraction of what it ASKED FOR, at the time, did it get? | - |
| pinfirst.py | 12 | THE BOT BUYS AT THE CROSSING. MEASURE THE CROSSING. | imp: pinjump |
| pinflip.py | 11 | can a hedge turn being WRONG into a profit? | - |
| pinflood.py | 25 | CAN WE SEE FLOOD SEASON COMING? | imp: pinbook,pindis |
| pingap.py | 65 | WHY DO THE BACKTEST AND THE LIVE TAPE DISAGREE ABOUT PRICE? | - |
| pingrow.py | 20 | every trading day from the first live order to three days | - |
| pinhealth.py | 30 | the early warning: is the edge being competed away? | imp: pindash |
| pinhedge.py | 12 | if a position starts drifting the wrong way, should we buy the | imp: pinclose |
| pinhedgelive.py | 9 | every hedge we have actually placed, what it cost or | - |
| pinhourly.py | 17 | could this bot trade the HOURLY markets? Sampled live. | run: watch_hourly.ps1 |
| pinhourlyedge.py | 8 | does the pin edge EXIST on the hourly markets? | - |
| pinimpact.py | 67 | MARKET IMPACT. What does it cost to buy 125 instead of 10? | - |
| pinjump.py | 14 | DOES THE EXCHANGE TAPE KNOW BEFORE THE INDEX PRINTS? | - |
| pinladder.py | 8 | one shot, or keep buying as the price improves? | - |
| pinladder2.py | 11 | how much can we buy on ONE bet across ALL price levels? | - |
| pinlead.py | 15 | THE COIN RACE: can we name the leader, and what is it priced at? | - |
| pinleadprice.py | 13 | WHAT DOES THE MARKET CHARGE FOR A LEADER WE CAN NAME? | - |
| pinlevels.py | 86 | WHAT EACH CONTRACT SIZE EARNS, AND HOW FAR IT SCALES. | - |
| pinlotto.py | 12 | BUY THE SIDE THE MODEL CALLS IMPOSSIBLE. THE IDEA, and it is the mirror of everything we have don... | - |
| pinmaker.py | 50 | HOW TO BUY BETTER: cross the spread, or rest and wait? | - |
| pinmatch.py | 68 | ANALOGUE SEARCH. Find the historical moments whose INDEX | imp: _verify_pinmatch,_verify_pinmatch_jump |
| pinmirror.py | 8 | the operator's falsification test. Force the WRONG side. | - |
| pinoffer.py | 9 | is the losing side of a decided market actually EMPTY? | - |
| pinpick.py | 27 | FIRST or BEST? which of several passing candidates to buy. | - |
| pinprob.py | 12 | THE PROBABILITY, COMPUTED. No fixed floor anywhere. | imp: pinprob_test |
| pinprob_test.py | 8 | score the COMPUTED probability against the tape. | - |
| pinproj.py | 14 | WHAT THE MONEY DOES FROM HERE, under AMENDMENT 9. | - |
| pinqueue.py | 8 | if resting is the only way to buy, WHERE would we have to rest? | - |
| pinrace.py | 7 | ARE WE LOSING THE RACE, OR WINNING THE WRONG ONES? | - |
| pinreal.py | 11 | what does this actually top out at, using only contracts that | imp: pingrow |
| pinreplay.py | 105 | THE FIDELITY HARNESS. Does the tape reproduce our own trades? | - |
| pinreplay41.py | 15 | what would AMENDMENT 40 (the jump gate) and AMENDMENT 41 | - |
| pinrest2.py | 9 | resting, tested FAIRLY this time. | - |
| pinruler.py | 34 | EVERY WAY OF MEASURING VOLATILITY, SCORED AGAINST THE TAPE. | - |
| pinrules.py | 25 | [lib] THE STRATEGY AS DATA: params, rules, trackers, profiles. | imp: pinexit,pinlevels,pinreplay,pinsim,pintool |
| pinscale.py | 50 | did the SCALE-IN RULE lose the money, or did CONCENTRATION? | imp: pinscaleaudit |
| pinscaleaudit.py | 30 | adversarial audit of research/pinscale.py's recommendation. | - |
| pinselect.py | 77 | CALIBRATION OR SELECTION. The single fork in the road. | imp: pincontest |
| pinsep.py | 12 | is there ANY combination of things, visible at the moment we | - |
| pinshadow.py | 6 | what the shadows WOULD have done, against what the bot did. | - |
| pinsignal.py | 59 | AT THE MOMENT WE DECIDED TO BUY, was anything different | imp: pinsignal_verify |
| pinsignal_verify.py | 15 | ADVERSARIAL VERIFICATION of research/pinsignal.py. | - |
| pinsim.py | 82 | [lib] the only certified backtest -- decision reproduction only, NOT evidence for loss rates | imp: pincoin,pincount,pinentry,pinexit +6 |
| pinsize.py | 48 | [lib] does sizing on confidence beat flat sizing? | imp: _gatecheck_dt3,_gatecheck_dt4,_gatecheck_dt5,_gatecheck_dt6 +2 |
| pinsmall.py | 6 | are small fills worse than large ones? | - |
| pinstrat.py | 12 | which earns the most, ACCOUNTING FOR LOSSES: buy-then-hedge, | - |
| pinstreak.py | 12 | bursts and droughts. Do the buys clump, and does a quiet | imp: pinboard,pindeck |
| pinstress.py | 13 | run the PROPOSED live configuration through the whole | - |
| pinsure.py | 8 | does 100% ever lose, and does the hedge fire when it shouldn't? | - |
| pinsweep.py | 15 | try every combination of the bot's dials against the tape. | imp: pinflip |
| pintail.py | 30 | STOP COUNTING FLIPS. MEASURE THE ERROR THAT CAUSES THEM. | imp: pinfirst,pinjump |
| pintrades.py | 10 | MEASURE THE DISCOUNT QUESTION ON TRADES THAT ACTUALLY HAPPENED. | - |
| pinvalue.py | 20 | money per hour, not buys per hour. Where the value actually | imp: pinboard,pindeck |
| pinverify.py | 7 | THE BACKTEST IS NOT FIXED UNTIL IT REPRODUCES OUR REAL LOSSES. | - |
| pinwarn.py | 20 | does the model's OWN CONFIDENCE warn us before a flip? | imp: pinflip,pinsweep |
| pinwhatif.py | 21 | the live bot against a what-if running beside it. | - |
| pinwhen.py | 29 | WHEN do the chances come? Hot and cold hours, tested against | imp: pinboard |
| pinwhy.py | 6 | why are opportunities plummeting? | - |
| pinwindow.py | 6 | does starting EARLIER get us a better price, or just a worse bet? | - |
| pinxlead.py | 12 | does one coin's settlement index move BEFORE another's? | - |
| placebo.py | 14 | what does the calibration estimator return when the market IS | go stage |
| power.py | 51 | given the data that EXISTS, what could we have detected? | - |
| proxy.py | 17 | which price is the market maker ACTUALLY quoting off? | go stage |
| queuesim.py | 56 | the queue-position simulator. How many fills does a quote | - |
| racecheck.py | 7 | HOW LONG DOES A STALE QUOTE SURVIVE? pin's own notes name this as its primary open risk, above ev... | - |
| reconcile.py | 26 | three estimators disagree about volatility. Find the liar. | go stage |
| remain.py | 33 | STOP SUBSTITUTING ONE NOISY TICK FOR THE FUTURE. | imp: remainfv,remainz |
| remainfv.py | 21 | WHAT THE REMAINING-PRINT ESTIMATOR DOES TO A TRADE. | imp: remainz |
| remainz.py | 13 | IS THE INDEX ACTUALLY MEAN-REVERTING, AND WHAT WOULD EACH | - |
| replay.py | 35 | [lib] loaders: load_quotes, load_index, load_markets, SERIES_TO_INDEX | go stage / imp: avgfeed,avgfeed_m1,avgfeed_round,book +31 |
| settlement_math.py | 15 | the exact fair-value model, derived and then VERIFIED. | imp: opening_value |
| settlewin.py | 8 | [lib] the settlement-window partial average, in ONE place. | imp: cross,endgame,hedgetune,implied +3 |
| spotdepth.py | 58 | does the SPOT ORDER BOOK bound how far the index can move? | - |
| spotlead.py | 71 | does the CONSTITUENT spot market tell us what the settlement | - |
| strikes.py | 19 | can one event's strikes contradict each other, executably? | go stage |
| surface.py | 33 | WHERE a volatility mispricing is worth crossing the spread | go stage |
| tapegaps.py | 83 | a second-by-second census of RECORDING HOLES in the tape. | - |
| tdist.py | 6 | [lib] Student-t, because stdlib has none and a clustered standard error | imp: calib,endgame,feeds,flow +14 |
| term.py | 34 | the VOLATILITY TERM STRUCTURE, and what it says about the | go stage |
| viability.py | 15 | what is an edge actually WORTH, and when would you know? | - |
| volcheck.py | 52 | VALIDATE THE VOLATILITY ESTIMATOR ALONE, ON ITS OWN TERMS. | - |
| volmodel.py | 19 | is the fat tail REAL, or is it vol clustering wearing a costume? | go stage |
| voltiming.py | 37 | [lib] can the ONE confirmed finding be turned into money? | go stage / imp: calfit,oos,surface |

## DEAD -- superseded, frozen, temp, or a closed test

Nothing running uses these. Do not run or extend. Some are still imported by other DEAD/DONE files or matched by pindesk/pinlab by name, so do not delete or rename without grepping.

| file | KB | purpose | used by |
|---|---|---|---|
| (root) kalshi_backtest.py | 13 | Replay the past as if it were live. No outcome peeking. | phase-0 replay; superseded |
| _cdc_app_probe.py | 2 | what can the Crypto.com agent key actually reach? | one-off probe |
| _gatecheck_dt.py | 4 | deploy-gate cross-check (09-08) | 09-08 one-off |
| _gatecheck_dt2.py | 3 | deploy-gate cross-check variant | 09-08 one-off |
| _gatecheck_dt3.py | 3 | Falsification: replay the SAME sizing rules on the only window that HAS flips. | 09-08 one-off |
| _gatecheck_dt4.py | 4 | deploy-gate cross-check variant | 09-08 one-off |
| _gatecheck_dt5.py | 4 | Break the constant-flip-rate assumption that Table 2 rests on. | 09-08 one-off |
| _gatecheck_dt6.py | 2 | deploy-gate cross-check variant | 09-08 one-off |
| _gatecheck_dt7.py | 2 | deploy-gate cross-check variant | 09-08 one-off |
| _raw_tmp.py | 1 | scratch | temp |
| _recon2_tmp.py | 3 | scratch | temp |
| _recon_tmp.py | 3 | scratch | temp |
| cmdlive.py | 59 | THE COMMODITY PENNY TEST. Real money, one contract at a time. | run: boot_all.ps1 / commodity live test; disabled in boot_all.ps1 ($false) |
| everything.py | 43 | one command. Does every job in RUN_WHEN_HOME.md, in the right | superseded by go.py |
| goldquote.py | 28 | the two-sided quoter for the gold cutoff test. | gold/LIP cutoff test, closed |
| pinlive.py | 14 | pin, live. Paper mode by default; sends nothing without --live. | superseded by pinrun |
| pinracetest.py | 28 | THE COIN RACE PENNY TEST. Ten one-contract buys, no more. | run: START_COINRACE_LIVE.ps1 / 09-11 coin-race penny test; superseded by pinracearm --live |
| pinreport.py | 17 | the operator's report: what happened, what it means, in PDF. | imp: pinreport_build / 09-08 PDF report |
| pinreport_build.py | 31 | compose the operator's PDF report. Reads the live run logs, the proven penny round trip, the cali... | 09-08 PDF report |
| pinrest.py | 12 | RACE FOR IT versus SIT AT MY PRICE. Which wins more? | superseded by pinrest2 |
| pinrun913.py | 292 | frozen copy of pinrun.py from 09-13 (docstring still says pinrun.py) | frozen pinrun copy; arm KILLED 09-20 |
| pinscore.py | 3 | grade a pinlive paper/live log against actual settlement. | grades pinlive logs |
| pinsmoke.py | 13 | ONE deliberate penny-size trade, to prove the plumbing. | 09-08 one penny trade, done |
| pinvin_0912a.py | 146 | frozen copy of pinrun.py (0912a vintage, docstring still says pinrun.py) | frozen pinrun copy; not running (pinlab still says RUNNING) |
| pinvin_0912b.py | 175 | frozen copy of pinrun.py (0912b vintage, docstring still says pinrun.py) | frozen pinrun copy; not running (pinlab still says RUNNING) |
| pinvin_0913a.py | 187 | frozen copy of pinrun.py (0913a vintage, docstring still says pinrun.py) | frozen pinrun copy; not running (pinlab still says RUNNING) |
| pinvin_0913b.py | 218 | frozen copy of pinrun.py (0913b vintage, docstring still says pinrun.py) | frozen pinrun copy; not running (pinlab still says RUNNING) |
| pinvin_0913c.py | 276 | frozen copy of pinrun.py (0913c vintage, docstring still says pinrun.py) | frozen pinrun copy; not running (pinlab still says RUNNING) |
| runreview.py | 7 | read a goldquote run log and say what actually happened. | reads goldquote logs |
| sweptwatch.py | 3 | report each NEW swept fill, once. The operator, 2026-09-13: "Keep a monitor out and tell me the f... | 09-13 monitor, not running |
