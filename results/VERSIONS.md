# v-tg-eff -- INSTALLED 2026-10-26 ~10:3xZ in research/{pinlab,botstats,pinphone}.py, LIVE on the phone at /update. Operator 10-26: "make the project more efficient ... check if ... you're collecting or doing something with the same data multiple times". (1) /brief 43.6-49.6 s -> 1.8 s in a running phone (17 s on its first call after a start): pinlab.live_progress spanned the same 573 paper logs 968 times (~5.9 M timestamps through strptime) and re-read first records 24,627 times; now a log's span is kept against its size+mtime, stamps in the usual shape compare as text, the log list and first records are read once a call -- identical spans on all 685 logs, identical live_progress. (2) /funds' past days read botstats' settlement cache (botstats.pot_settlements -> pinphone.funds_hist) instead of their own 7-GET pull seconds before the /funds picture refreshed the same cache; its own pull stays for an account botstats cannot give. Render diff: /funds /bots /today /yesterday /days identical but the clock lines. NOT changed: pinledgerd (the live coin race reads its file); /funds' balance reads (the 429 hot spot: 17-20 of ~58 GETs a pass on /portfolio/balance) -- sharing them would change /funds' 'read now' promise. Self-tests: pinphone 324, botstats 85, tgcharts 30, pinbrief 23, pinlab 305, pindesk 227 -- all OK. ALSO 10-26 (operator scripts, not run): results\retire_paper_tests.cmd (fcvar x3, bettor_paper, race paper arms 3/4, cdc_record: ~235 MB, 4 duplicate Kalshi websockets; tested on a copy, exactly 6 boot_all lines), results\add_fx_recorder_keepalive.cmd (the FX/commodity recorder stops itself ~10-30 08:49Z; the new boot_all entry runs it --minutes 0 and never doubles the running copy), results\restart_ntopng.cmd (the 3+ GB kernel leak). HOLD: dropping the 5 commodity series from kalshi_collector waits until the FX recorder is in boot_all.
# v-tg-losses2 + v-phone-flag -- INSTALLED 2026-10-26 ~09:5xZ in research/{tgcharts,pinphone}.py, LIVE on the phone at the next /update. Operator 10-26 (seeing the OLD /losses, v-tg-losses not yet loaded): "That losses chart is pretty bad it's really hard to notice any trends or anything meaningful and it's also just hard to see what's what. New kind of chart/graph". The /losses picture is now two views of every bot's losses: (top) each ET week Mon-Sun, the last 8: what the winning markets made (green, up) against what the losing ones cost (down, stacked by bot), the week's loss total and count; (bottom) every loss of the last 30 days on its bot's row, circle area = dollars, the 4 biggest named, each row labelled with its count and total. Headline: the last 7 ET days' losses (the words' '7d' count) vs the average week of the 4 before. all_losses' totals gain won_days. v-phone-flag: results/pinphone.update -- its presence runs /update exactly as the command does (self-tests first, old code kept on a failure, said in Telegram), removed before it runs so it fires once; checked every poll cycle (update_flag_tick). So a phone change no longer waits for the operator's /update -- but only AFTER this code is loaded by one more /update. Self-tests: pinphone 323 ok, tgcharts OK.
# v-tg-losses -- INSTALLED 2026-10-26 ~09:0xZ in research/{pinphone,tgcharts}.py, LIVE on the phone at /update. Operator 10-26: "Make it so /losses outputs losses not just for pin and race and show which bot it lost. Show all the same information and show a bit more than just the last ten"; "I don't even think /losses works properly for pin". It did not: /losses was pindesk's losing_closes() -- the main account's markets NETTED per quarter-hour (pin + race together), so a pin loss covered by a win at the same close vanished (10-26 3:15 AM: HYPE -1.59, BTC +2.68 -> +1.09, not listed) and a big one shrank (10-25 2:00 AM ZEC -56.63 listed as -45.06). NOW: tgcharts.all_losses -- every bot's losing MARKETS from botstats (Kalshi's books, every pot), each with its bot, the market, side x contracts ('hedged' for both sides), $ and % of that bot's pot when its day began (botstats.day_pot, the /bots base); the last 30 (LOSSES_SHOWN, fewer if the message would pass 3,900 chars) by ET day, then a by-bot table (lost/settled, last 7 days, $ lost, worst). The chart: every losing market coloured by bot, $ and % panels. Falls back to the old main-account view (text_losses_main / chart_losses_main) when botstats cannot be read. Self-tests: pinphone 322 ok (3 new /losses checks: planted, EMPTY, DOWN), tgcharts (all-bots losses chart), botstats OK. Live render 10-26: 126 losing markets of 2,834 (4.4%), pin 64/1979, forecaster 21/165, race 16/288, weather 15/26, FX 1/77, other 9/53. NOT CHANGED: the pin LOSS alert still nets per quarter-hour (alert_loss_text).
# v-tg-mem -- INSTALLED 2026-10-26 ~07:3xZ in research/{pinphone,tgcharts,pindesk}.py, LIVE on the phone at /update. Operator 10-26: "free up memory, make the project more efficient ... check if anything isn't needed anymore, or if you're collecting or doing something with the same data multiple times". Measured in a copy of the phone process (scratchpad mem/phone_mem.py): 883 MB private after one chart -> 262 MB. (1) numpy's OpenBLAS, loaded by matplotlib, committed a buffer per CPU thread (16): +614 MB on the first chart; OPENBLAS/OMP/MKL_NUM_THREADS=1 set before matplotlib loads -> +131 MB. (2) pindesk Ledger.newest_rows kept every row of the newest pin log (25,795) for pinflat.positions(), which reads only order/hedge/settled rows -> 323 rows, positions identical. Self-tests pindesk/pinphone/tgcharts OK. ALSO 10-26 (processes, no code): stopped 32 tail + 32 grep leftovers of 10-15..10-23 research monitors and the q-2026-10-18c/maker-rest/cutter.sh poll loop; racev2_shadow.py (the reward test v2 it shadowed was killed 10-23); the hourly recorder (hourly_collector.py -> kalshi_data_hourly, 2.5 GB; its hourly-99c study finished DEAD 10-24) -- the FX 15-min recorder kept. READY, NOT RUN (needs admin): results/retire_paper_arms.cmd -> .ps1 stops the 16 September pin paper arms (~1.6 GB, ~1.6 cores, 16 duplicate websocket feeds; nothing read them since September) and makes boot_all stop relaunching them (tested on a copy). FOUND, NOT CHANGED: kalshi_collector (main tape) and the FX recorder both record KXGOLD/SILVER/WTI/NATGAS/COPPER 15M; settlements are fetched three times (pinledgerd -> kalshi_ledger.json, botstats' per-pot cache, /funds' own 7-day pull); the operator's apps: an Oct-17 Claude Code window 1.2 GB, Riot Client ~930 MB since 10-23, ntopng service ~470 MB.
# v-fx-hold5 -- LIVE 2026-10-26 06:20:27Z (fxtake_live pid 3315392, started by boot_all's keep-alive; was 3251600, stopped flat via the stop file at 06:12:15Z, run -$4.85) -- operator 10-26 after the FX taker's first live loss (KXPLATINUM15M 00:30 ET: NO 63c at T-90, 99c at T-32, bought 10 at 99c at T-30, 55c at T-5, settled YES, -$9.91): "Are there changes that could've prevented that?" then "You seriously need to find a solution". research/cleanroom/fxtake_live.py: HOLD_S = 5.0 -- a side is bought only once its bid has STAYED >= 98c 5 s (Book.since / held(); a dip under 98c restarts the clock; a reconnect snapshot still at 98c+ keeps it); start record hold_s; no_order records held_yes/held_no; botstats' FX settings line says it. EVIDENCE (.sweep/q-2026-10-26-fxloss/fx_replay2.py, the live rule replayed tick by tick on every recorded FX/commodity market, 10-23 + 10-25/26 tape, 264 buys): old rule 3 lost, -$5.00 at 10 contracts -- all 3 losers (GOLD 10-23 08:45, GBPUSD 10-23 14:15, PLATINUM 10-26 00:30) bought within 2 s of the bid first reaching 98c; buys whose 98c had held >= 5 s: 69, 0 lost, +$5.97; stop-loss exits at 97c..80c: -$34 to -$54 vs holding (25 'scares' = winners whose bid fell under 80c and came back). The earlier LS10 '0 of 425 lost' sampled the book at fixed T-30 instants, not the live rule's FIRST moment in the window -- that is where the risk is. The hold-as-a-rule replay (fx_replay3.py: lets a market be bought later in the window once 98c has held) was stopped twice by Claude Code's low-memory guard and is NOT run; 3 losers is a small sample -- the fx-taker-read 10-28 judges the new rule. Self-tests: fxtake_live PASSED (+5 hold checks), botstats OK, pinphone OK. REVERT: HOLD_S = 0.0, stop file, remove it (boot_all restarts).
# v-tg-screens -- INSTALLED 2026-10-26 ~04:5xZ in research/{pinphone,botstats,tgcharts,pinbrief}.py, LIVE when the operator sends /update. Operator 10-26: "/yesterday doesn't look good or show % of bank return. I seriously need you to go through every single screen, response, prompt, and command and fix this and make it look nice ... definitely add the percentage anywhere it applied." Every command rendered on live data before and after (scratchpad tg/before, tg/after). /today /yesterday: headline = every pot with its % of all pots and return on bets; a BY BOT table (Money, of bank = that bot's pot when the day began, Return, Lost x/n, ALL row); the 7-day average with its % of all pots and 'above/below average'; the pace line with %; the main account block behind a tap. /days: every bot's week (headline %), a day table with each day's % of all pots, the week bot by bot, all time on the $1,123.46 put in; main account days (% of its bank) behind a tap; 'Pin bot since <version>' line; its chart now draws every pot (% of all pots a day; fallback main account). /stats: an 'of bank' column (Life on the main account's money put in); 'Lifetime by bot' with names (pin bot / coin race / old oil bot). /status: 'Main account $X (pin + race)' (the old '+19.34% on the $1,123.46 put in' mixed one pot's bank with every pot's deposits) + 'All pots $X, all time +$Y (+Z% on the money put in)' + 'All bots today'. /open: every pot (pin's own + each bot's Kalshi positions). /losses /hedges: each one's % of the bank, real day names, 'BTC hourly' / 'coin race' for KXBTCD / KXCRYPTO*. /bots: By day table gains 'of pots' and Lost. /market: 'wanted N contracts, got M'. /brief: every pot on top; pinbrief's 'Yesterday was -$0.99 (+124%)' (today vs yesterday) is now yesterday's % of the bank; plurals. 8 AM summary: every pot + by-bot table, main account story behind a tap. Loss alert: '% of the bank'. /funds: subaccount 4's 7 days are the FX pairs only (was -25.8% from the old reward test's pool-2 legs), what is left out is said. botstats: a 'pause' the bot lifted ('resume') is no longer HALTED (/pin and /bots showed the 27 s 10-25 05:59Z open-cap pause as HALTED for two days); all-pots days carry won/lost, return and pot %. Charts: long headlines shrink to fit. /help describes the new screens. Self-tests: pinphone OK (12 checks rewritten to the new screens, all stricter: tables, %, tap blocks, Telegram's HTML rules), botstats OK, tgcharts OK, pinbrief OK; every rendered screen passes tg_html_problems. Display only: no order, size or rule changes. NOT changed: /bars (September's finished tests, kept for the record), /features, the controls. REVERT: git revert the commit, then /update.
# v-tg-fx -- INSTALLED 2026-10-26 ~04:0xZ in research/{botstats,pinphone,tgcharts}.py, LIVE when the operator sends /update. Operator 10-25: "there's nothing for fx in the commands list so I'm sure it's missing elsewhere. Make sure it's fully implemented" and "The 5th graph says 123.30 dollars" (the /bots chart drew subaccount 5 only). Fixed: /help and the header list /fx; /fx gets a chart (both pots); the /bots and /funds account chart draws ONE panel per bot's pots -- 'Subaccounts 5 + 4 - fx taker' with the split (commodities (5) + currencies (4)) inside the panel (was: subaccount 5 alone, $123.30, and a stray '4 ()' in the caption); the all-pots cash on /bots now includes the FX pots ($2,175.30 -> $2,362.22 on the live read), as do the 'separate pots' and 'Kalshi's app' notes; the FX card names both pots and each pot's cash; /bots' pointer line has /fx; /features lists the FX taker; /funds shows its bet size under accounts 4 and 5 with each pot's start cash; its VERSIONS entry is found (v-fx-twopots was claimed by no bot because its text mentions the coin race); its stop-file exit and refusals read in words. botstats POT_POOL_ONLY {'4': 0}: for the FX taker's pot, subaccount 4 = its pool 0 only (money moved, cash, markets) -- its 'put in' read $209.89 (the old reward test's pool-2 transfers) instead of $180; all-pots totals keep the whole subaccount. SPEC fx keepalive = boot_all (the operator ran add_fx_keepalive.ps1; boot_all 23:50 ET: 'all up', one copy, pid 3251600). Self-tests: botstats OK (+1 check), pinphone OK (+1 check, 3 expectations reworded), tgcharts OK (it had been FAILING since subaccounts 4/5 were added on 10-25 -- /update does not run it; +3 checks). Live words and both PNGs checked (scratchpad fx/funds.png, fx.png). Numbers of trades, money and orders unchanged: display only. REVERT: git revert the commit, then /update.
# v-fx-twopots -- LIVE 2026-10-26 01:07:17Z (fxtake_live pid 3251600, was 3216128; started by hand from the scratchpad, NOT in boot_all) -- operator 10-25: "Sure make the new sub account for currencies". SUBACCOUNT 4 CREATED in pool 0 (ordercli --sub-create --sub-pool 0 -> 201 {'subaccount_number': 4}; the number 4 also names the old coin-race reward pot in pool 2, ~1c, stopped) and FUNDED $60 from main pool 0 (--sub-fund 60 --sub 4 --sub-pool 0 -> 200). research/cleanroom/fxtake_live.py: --fx-subaccount N = the pot for the FX pairs (pool 0); Trader.subs {pool: sub} routes each order (and its cancel, its unknown-answer read-back, its cash read) to the pot that lives in the market's pool; MAX_PER_CLOSE (6) and MAX_HELD ($70) now count EACH pot on its own so the 5 pairs never crowd out a commodity buy; start record carries subs {"0": 4, "2": 5}. Start line: pool 0 = subaccount 4 $60.00, pool 2 = subaccount 5 $121.54. Self-test PASSED (new: each pool's cash from its own pot; 7 commodity + 5 FX ready -> 6 + 5 orders; FX orders carry sub 4 / pool 0). The old run stopped flat via the stop file at 01:06:52Z with run_pnl +$1.542 (16 buys, 16 wins). botstats: SUBS + '4' (pool 0), FX_PAIRS, bot 'fx' owns subs 5 and 4 (bot_subs, sub_name; money/open/balance blocks and pot % over both); pinphone /funds: account 4 = 'FX taker: the 5 currency pairs' (pool 0) / 'coin-race reward test (stopped)' (pool 2), account 5 = 'FX taker: the 8 commodities'. Both self-tests OK; the Telegram process needs /update. REVERT: stop file, restart without --fx-subaccount (FX then refused unfunded_pool), ordercli --sub-return 60 --sub 4 --sub-pool 0.
# v-tg-roi7 -- INSTALLED 2026-10-24 ~07:2xZ in research/pinphone.py, LIVE when the operator sends /update (together with v-tg-reliable). Operator 10-24: "put roi percentages everywhere applicable ... on the past 7 days of bets for anywhere that shows up". Every short money figure (the /bots cards' today / 7 days / all time line and its text form) now reads '+$122.67 (+1.1% on bets · +9.0% of bank)' (_roi_tail); the per-bot 'Last 7 days' day table (/pin /ladder /fc /race) and /bots' 'Last 7 days, by bot' gain Return and 'of bank' columns; /bots' 'By day (all pots)' gains Return; /funds' summary '7 days' column carries the account's share of what it holds now ('-17.82 (-3.4%)') with a legend line. The per-bot 'By day:' text lines (the plain-text fallback) carry the same '(x% on bets · y% of bank)' tail. Numbers unchanged, only shown. Self-test PASSED (3 expectations rewritten to the new format); live render checked (scratchpad tg_roi.txt). REVERT: git revert the commit, then /update.
# v-hedgejump6 + v-etclock -- LIVE 2026-10-24 01:45:37Z -- the pin bot on C:\kals-live-0925m (pinrun code_sha f36c427f99a5: the ET clock from the zone, so the 11-01 DST change cannot shift it) with --hedge-jump 6; started by watch_bot -> restart_bot.ps1 after the run before stopped itself 01:44Z (pintake: an order's outcome UNKNOWN when the home connection failed, 10-23 ~21:41 ET on). restart_bot.last.log: 80 flat args, code file ok x3, pinflat FLAT, flags now live carry --hedge-jump 6 --band-mult 0.955 0.981 1.5 --max-losses 0. Log results/pinrun-live-20261024T014537Z.jsonl. READS clockbug-deploy: code_sha confirmed. The planned ~10-24 11:02Z restart is moot.
# v-ladder-single98 -- LIVE 2026-10-24 01:01:50Z -- ladder_live.py --levels 0 (one 98c rung on the whole 70% rail), pid 2660284, started by KalsBoot/boot_all after the stop file stopped pid 2436716 (98c+95c) at 01:01:19Z in the quiet minutes; start record written. Run by the operator's one-click admin file (Desktop 'Kals bot updates.cmd' -> scratchpad kals_bot_updates.ps1). READ ladder-single98-read 10-30.
# v-wifi5g -- LIVE 2026-10-24 01:01:17Z -- Wi-Fi adapter Preferred Band = '3. Prefer 5GHz band' (operator 10-16, after the 2.4 GHz outage); a 7-s blink while flat, internet back at once, still 5 GHz channel 48. NOT the cause of the 21:41 ET connection trouble: Wi-Fi to the router stayed perfect (212/212 pings, 6 ms) while connections past the router timed out. Revert (admin): Set-NetAdapterAdvancedProperty -Name Wi-Fi -DisplayName 'Preferred Band' -DisplayValue '1. No Preference'.
# v-recorder5-file -- INSTALLED 2026-10-24 01:01:58Z -- C:\kals\kalshi_collector.py is v5 (the 429 fix; backup kalshi_collector.py.bak-20261018-v4; repo copy too). The running v4 recorder was NOT stopped (the one-click script counted it wrong and skipped the stop), so v5 starts at the recorder's next restart (boot_all's deaf check or a reboot; run_all.ps1 starts it).
# v-tg-reliable -- INSTALLED 2026-10-24 ~03:xxZ in research/{botstats,pinphone,tgcharts}.py, LIVE when the operator sends /update. After the 10-23 21:41 ET connection trouble blanked '% of all pots', the pin page's pace chart and lost the 'DOWN -> TRADING' alert: (1) botstats keeps the last pass where every pot read (c['good']) and uses it, said so, when a read fails (3 h limit); (2) a send the connection drops is sent again for 15 min, marked late; charts retried twice; (3) the pace panel draws dollars when no bank is known, never blank; (4) /today: 'Ahead/Behind pace' vs the 7-day average at the same clock; (5) stale things moved out of the way: the stopped race arms behind the tap, the weather bot one line on /bots, the month-old opportunity trend left out of /market, plain-word stop reasons on /pin, the ladder and forecaster descriptions current, a KILLED/infra heading never a bot's version.
# v-tg-today-allbots -- INSTALLED 2026-10-23 ~16:2xZ (research/pinphone.py text_day/_all_bots_day/all_bots_avg_before + research/tgcharts.py chart_day/all_day_markets; old picture kept as chart_day_main, the fallback when botstats cannot be read), LIVE at the next ELEVATED pinphone restart. Operator: "/today doesn't show the right total it says 11.22 right now it's really 24.85" -- /today and /yesterday counted the main account only (pin + race $11.22); now the headline and the picture are EVERY pot from botstats.all_bots (the /bots number: pin +$10.01, race +$1.21, forecaster +$6.83, ladder +$6.80 = +$24.85 at 16:15Z), with yesterday and the 7-day average; the main account's old block follows as 'Pin + race'. Self-tests PASSED (pinphone exit 0, 0 FAIL, /today check updated to the new layout; tgcharts +3 checks: all four bots' markets, total = sum of botstats 'today'); real-data words and PNG checked. /days and /stats are still main account only.
# v-tg-avg7 -- INSTALLED 2026-10-23 ~12:3xZ in research/tgcharts.py, LIVE at the next ELEVATED pinphone restart. Operator: "The 7 day average should be on the other charts too where possible. Like on /today as a 3rd line." /today /yesterday: orange dashed average day of the 7 ET days before (gap days $0; days before the first on the books left out), legend '+$X (+$Y by now)'; /days /brief /summary /stats: 7-day average line over the $ bars and the % bars, drawn to YESTERDAY (today's bar is partial; its last point equals /today's average); /stats: won % over 7 days. Bot pages already had it (pace panel). Self-test PASSED (+3 checks); real-data PNGs checked by eye. REVERT: git revert of this commit + pinphone restart.
# v-ladder-single98 -- boot_all EDITED 2026-10-23 ~12:2xZ by the session (backup results/boot_all.before-single98.ps1); the RESTART was refused by the classifier, so the running ladder pid 2436716 is still 98c+95c until its next restart (restart_ladder_single.ps1 now passes its boot_all check). Was: VERIFIED 2026-10-23 ~10:3xZ, NOT LIVE (one boot_all edit away). ladder_live.py --levels 0 (NO code change: the live Option C path of 10-22 09:00-15:40Z) together with --fit = ONE 98c rung on the whole 70% rail, 91 bids a coin at $643 (was 98c+95c at 46 each). Evidence: (1) the paper-timing rail-aware replay that set v-ladder-fit (.sweep/q-2026-10-23/rung98only/alloc_sweep6.out, 25 ET days 09-27..10-22): 98 alone size 91 $12.13/day (1.89%) vs live 98+95 size 46 $11.67 (1.81%); last 7 days $10.23 vs $8.13 (+26%); wins 15 of 25 days and 14 of the last 15; 0 losses either way; (2) the exact-queue model (.sweep/q-2026-10-23/rung3/rung3.md, 14 days 10-08..10-22, 6,247 markets): 98 alone (92) $11.47/day vs 99+98 (46) $10.23 vs 98+97 (46) $9.73 vs 99+98+97 (30) $9.38. Mechanism: under the fit rule every extra rung halves the 98c size; the 98c rung fills ~1.85x for 2x size while the 95c/97c rungs fill rarely (LIVE since cplus 10-22 15:40Z: 65 bids at 95c, 0 fills; all 1,645 live contracts ever filled came through the 98c rung). Crossover: a 99c rung pays from ~$4,000 bank (99+98 >= 98 alone), three rungs from ~$5,750 -- a later flag, not built. Risk: same ceiling ($446 vs $453 out at once), same worst market ~$89, same rule and coins. Self-test PASSED with the new argv: "fit (big coins above $3000) -> $643.47 bids 91, levels [0] (rungs 98c), ... all fit". SUPERSEDES v-ladder-rung97 (its +5-13% was at EQUAL sizes, ignoring the rail). DEPLOY: boot_all ladder argv "--levels", "0,1" -> "--levels", "0" (operator's one-liner; the classifier blocks me), then the scratchpad restart_ladder_single.ps1 (self-test regex 'bids 91, levels [0] (rungs 98c)'; quiet window). REVERT: put "0,1" back and restart. READ: ladder-single98-read 10-30 (live contracts/day and $/day vs the two-rung days 10-22 15:40Z..deploy; research/ladder_shadow.py).
# fx-collector -- RUNNING 2026-10-23 08:48:57Z (pid 2455836; research/hourly_collector.py 2026-10-23-hourly-v2 --fifteen-min; results/start_fx_collector.ps1; pid file results/fx-collector.pid; log results/fx-collector.out; root C:\kals\kalshi_data_fx). Second instance of the clean-room recorder taping the 13 FX + commodity 15-MINUTE series (KXEURUSD15M KXGBPUSD15M KXUSDJPY15M KXUSDCAD15M KXAUDUSD15M KXGOLD15M KXSILVER15M KXCOPPER15M KXPLATINUM15M KXPALLADIUM15M KXWTI15M KXBRENT15M KXNATGAS15M; one strike each; subscribed 120 s before open): books + trades + lifecycle, v4 record shape. Self-test 85 checks (v1 behaviour byte-identical without the flag; the hourly instance pid 2445764 untouched). Health at +60 s: 13 markets, 456 deltas/s, ~28 MB/h, 0 429s. Purpose: find ladder-class markets WITHOUT a 99c wall (single-print settlement: the 'decided' envelope must come from each asset's own 30-s move distribution). NOT in boot_all; --minutes 10080.

# v-ladder-rung97 -- SUPERSEDED 2026-10-23 ~10:3xZ by v-ladder-single98 (under the fit rule a second rung halves the 98c size; the +5-13% below was at EQUAL sizes). Was: VERIFIED 2026-10-23 ~09:0xZ, NOT LIVE (one boot_all flag away). ladder_live.py --rung1-offset 0.03 (commit 7201711; self-test PASSED) moves the second rung from 95c to 97c. Evidence (.sweep/q-2026-10-23/q97full/, EXACT queue rebuilt from the book tape, 14 ET days 10-08..10-22, 6,247 markets, 98c rebuild = the paper's logged 'ahead' exactly in 93.2%): 98+97 beats 98+95 at every size -- size 45 $9.54 vs $8.75/day (+$0.79, +9.1%), 64 +$0.93 (+7.8%), 100 +$0.84 (+4.8%), 200 +$3.33 (+12.6%); OUT OF SAMPLE last 7 days wins by more: size 45 +$1.02 (+14.7%), 64 +$1.31, 100 +$1.81, 200 +$3.28 (+13-15%); 97c wins 10 of 14 days, ties 1, loses 3. The 97c rung fills in 39 markets / 14 days (116 contracts/day) vs 17 (54/day) for 95c; 98+96 sits between. Caveats: no loss term (the call has never been wrong in the last 30 s on these coins), fees ignored (makers pay none), sales assumed unchanged by our bid, thin (72 of 6,247 markets had any sale <= 0.97 after the bid). Risk: a wrong call costs 97c instead of 95c on that rung (2c more); more fills = more correct-side exposure under the same 70% rail. DEPLOY: boot_all ladder argv add "--rung1-offset", "0.03" after "--levels", "0,1" (operator's one-liner; the classifier blocks me), then a quiet-window stop-file restart (results/restart_ladder_fit.ps1 pattern with the new argv; the self-test argv line must say 'rungs 98c 97c'). REVERT: drop the flag, restart.

# hourly-collector -- RUNNING 2026-10-23 08:12:37Z (pid 2445764; research/hourly_collector.py 2026-10-23-hourly-v1; results/start_hourly_collector.ps1; pid file results/hourly-collector.pid; log results/hourly-collector.out). A clean-room READ-ONLY WebSocket recorder (no write verb in the file; self-test 59 checks; 3 live smoke runs 0 429s) taping the HOURLY crypto markets KXBTCD/KXETHD/KXSOLD -- near strikes every minute + ALL strikes in the last 15 minutes -- into C:\kals\kalshi_data_hourly\<channel>\YYYYMMDDTHH.jsonl.gz in the v4 recorder's record shape (+_conn), so queue97_exact.py's book rebuild works on it. Health at +60 s: 162 markets on 2 connections, 434 deltas/s, ~29 MB/h, 0 errors. Purpose: measure the 99c-rung queue ARRIVAL TIME on decided hourly strikes (the hourly ladder's $33-244/day upper bound vs ~$1-13 behind the 4.5-10.9k resting at 99c). NOT in boot_all (nobody restarts it if it dies; --minutes 10080 = runs to 10-30). Disk guard 8 GB. STOP: Stop-Process on the pid in results/hourly-collector.pid (non-elevated, started from this session).

# v-etclock -- LADDER + FORECASTER LIVE 2026-10-23 (ladder pid 2436716 07:16:13Z, forecaster pid 2437128 07:20:22Z, both on the patched repo code, same argvs); PIN BOT PENDING its natural run end ~2026-10-24 11:02Z (restart_bot.ps1 -> C:\kals-live-0925m / f36c427f99a5) or a flat elevated restart_bot.ps1 run. US daylight time ends 2026-11-01 06:00Z; every bot's ET day key was gmtime(t - 4h) (the day would turn at 23:00 EST from 11-02: pinrun's DAY loss cap and dayloss file an hour early, ladder/forecaster day_pnl + day stop likewise). Patches (clockbug agent, .sweep/q-2026-10-23/clockbug/): et_offset_s(t) = zoneinfo America/New_York if available (this Python has no tzdata) else the US rule (2nd Sun of March 07:00Z .. 1st Sun of Nov 06:00Z); et_day uses it; self-test lines added. REPO (committed, self-tests PASSED): research/cleanroom/ladder_live.py, forecaster_live.py, research/tgcharts.py -- take effect at each bot's next restart (ladder: stop-file restart in a quiet window; forecaster: stop file). PIN BOT: new live dir C:\kals-live-0925m = copy of 0925k + patched research/{pinrun,downtime,pinxfer}.py; pinrun sha f36c427f99a5 (ordercli 467782077a23 / pintake 9150d6b65968 unchanged); startup-path self-test with the FULL restart_bot argv + --selftest: SELF-TEST PASSED. DEPLOY = restart_bot.ps1 $code -> C:\kals-live-0925m, $codeSha -> f36c427f99a5, copy restart_bot.ps1 into 0925m; the natural run end ~2026-10-24 11:02Z relaunches on it (or a flat elevated restart). Deadline: live before 2026-11-02 04:00Z. REVERT: $code back to 0925k / 32639cccc7f1.

# v-racev2-live-test -- KILLED 2026-10-23 08:25:24Z after 2 races (stop file written by the session; it stays so nothing restarts it): fills $17.43 vs $2.61 modelled credit = 6.7x the credit (bar PASS <= 0.25x, KILL > 0.50x). Race 1 (07:30Z): XRP 105 @ 1c, largest print 90. Race 2 (08:15Z): XRP 819 + HYPE 799 + ETH 20 @ 1c (prints of 303), -$16.38. The 'dead legs get no sellers at 1c' premise failed at live size (the paper's 28.6% fill cost did not hold). Sub 4 holds ~$27.6: move it back (ordercli --sub 4 --sub-return, operator). No reward credit observed in main pool 0 by 08:22Z (too early to judge payment; irrelevant now). Was: LIVE 2026-10-23 07:02:27Z (pid 2432856; subaccount 4 $45.01, pool 2; --races 20 --every 3; log results/racereward-v2-live.jsonl). Operator funded sub 4 ($45, transfer 64bfa861... POST 200) and started it at 06:59:51Z via the one-line command; the first two launches REFUSED ('main pool 0 is unreadable' = one 429 under the recorder's storm); racev2_live.py now retries the two start reads 5x (self-test 98/98 PASSED), third launch ran. NOTE: started 02:59 AM ET, OUTSIDE the pre-registered 21:00-23:00 ET window (spec 4.2); the read must say so. Rails: 1,100 x 1c on dead legs, exit 115 s, <= $40 collateral, day stop -$30, test stop -$45, payment tripwire 4 h after the first 2 races, 20 races then exit. READ: python research/sweep/racev2_live.py --subaccount 4 --report 2 h after the last race and at 48 h (bar: fills <= 0.25 x model credit; main pool 0 up >= 0.90 x credit). STOP: results/racev2-live.stop.

# v-race-gap -- LIVE 2026-10-23 04:40:12Z (coin race pinracearm.py --live restarted by boot_all with --min-gap-bp 0.5; its arm record shows min_gap_bp 0.5). Operator ran the boot_all edit + admin kill (backup results/boot_all.before-racegap-oneside.ps1). Evidence (.sweep/q-2026-10-22/flatbots/): every race loss over $1 was a TIE (Kalshi 'scalar' = 50c) bought with the top two coins within 0.25 bp; |gap| < 0.5 bp: 38W/8L -$46.06, >= 0.5 bp: 228W/4L +$48.52 -> ~+$1.5/day vs ~0. REVERT: drop --min-gap-bp from boot_all, admin kill, boot_all relaunches.
# v-fc-oneside -- LIVE 2026-10-23 04:50:19Z (forecaster_live --variant race1_98_r28_oneside, pid 2397168, subaccount 2 $125). The 04:40Z launch REFUSED ('--auto-scale: the pot is unreadable', one 429) and the forecaster was DOWN 04:39-04:50Z; boot_all's 04:50Z retry started it. v-fc-startretry (commit 97a3446): the start read now retries 5x, in effect at the next start. Evidence: 7 of 20 losses were both-sides markets (-$102.49 of -$157.84); the other 139 markets 126-13 +$114.54; one_side on the same entries ~+$2.4/day vs +$0.5. Kill criterion: judge on 2026-11-06 against the ladder's %/day on the same $125; no new money until then. REVERT: --variant race1_98_r28.
# telegram-bankpct/pace/features/update -- LIVE 2026-10-23 04:40:11Z (pinphone restarted by boot_all after the operator's admin kill): bank-% lines, average-day line, 3-panel pace charts, /features, /update.

# v-ladder-fit -- LIVE 2026-10-23 04:04:58Z (ladder pid 2386968, subaccount 1; start record fit true, big_coins_above 3000, size 47 at pot $648.17, max_commit $453.72, levels [0,1], coins the 5). The operator ran the boot_all edit (backup results/boot_all.before-fit.ps1); restart via results/restart_ladder_fit.ps1 (log restart_ladder_fit.log): old pid 2254916 exited in 1 s, 1 start record. Operator 10-23: "Figure out the most profitable safest way to run ladder and that's what we'll do. Make sure it grows with bank, and it should make at least 1% each day and basically never lose but if it does it shouldn't blow the whole account up." ladder_live.py --fit: bid size = floor(COMMIT_FRAC x pot / (coins x rung prices)) so every rung of every coin rests at once (5 coins, 98c+95c, 70%: 46 at $643, 72 at $1,000, 145 at $2,000); --big-coins-above 3000: at a $3,000 pot the coin set becomes all 9 (size 120) -- both re-derived at every rescale, so size and coins grow with the bank; --commit-frac (default 0.70) is the ONE risk knob = the most money that can be out at once (the all-at-once ceiling; the 70% was a margin set 10-02, not derived from data); --rung1-offset 0.03 (97c second rung) built for after the queue check. Evidence: rail-aware replay 25 days (.sweep/q-2026-10-22/ladfit/): fit at 70% $11.90-12.13/day (1.85-1.89%) vs live pot/7.8 $11.27 (1.75%); worst one market $89 vs $158; 22 of 25 days >= 1%; 0 losses; the paper's final call has been wrong in 0 of 20,339 markets. Self-test PASSED (fit sizes, coin switch on rescale, MAX_COMMIT). ARGV: --subaccount 1 --live --auto-size --fit --big-coins-above 3000 --market-cap-x 2 --levels 0,1 --coins KXNEAR15M,KXZEC15M,KXDOGE15M,KXHYPE15M,KXXRP15M --minutes 10080. REVERT: put back --pot-per-contract 7.8 (drop --fit/--big-coins-above) in boot_all and restart.

# v-ladder-fit -- PREPARED 2026-10-23, NOT LIVE (operator's call). ladder_live.py --commit-frac (0.5..1.0, default 0.70 = unchanged; commit a0fdcf4). Candidate argv = the C+ argv with --pot-per-contract 10 --commit-frac 1.0: 64 bids at $643, every rung of every coin rests at once ($618 of $643, 'all fit' in the --selftest argv line). Evidence (rail-aware replay of the paper ladder's real timing, 25 days, .sweep/q-2026-10-22/ladfit/): $15.49-16.14/day (2.41-2.51%) vs live C+ (pot/7.8 + 70%) $11.0-11.3/day (1.71-1.75%); 23 of 25 days >= 1% vs 22; 0 losses either way; worst one market $123 (was $158); all-at-once ceiling $618 (was $450). Adding the 4 big coins back instead: same or less at this bank. DEPLOY: boot_all ladder argv 7.8 -> 10 + --commit-frac 1.0, restart via a clone of results/restart_ladder_fit.ps1 pattern (restart_ladder_cplus.ps1). REVERT: put back --pot-per-contract 7.8 and drop --commit-frac, restart.

# v-ladder-cplus -- LIVE 2026-10-22 15:40:35Z (ladder pid 2244028, subaccount 1; start record live_levels [0,1], market_cap_x 2, size 82 at pot $643.69). Operator 10-22: "Push c+ live". ladder_live.py --levels 0,1 mirrors the paper engine's 95c rung (model-5c) as well as the 98c one, same size; --market-cap-x 2 = one bid of each a market. Evidence: paper 5 coins, 95c rung filled in 65 markets 0 lost; replay at $643 last 7 days $14.25/day vs C $9.37 (since 10-08 $17.46 vs $10.98). Worst single market ~$158 (was ~$80). Shadow: research/ladder_shadow.py 'C+'. REVERT: copy results/boot_all.before-cplus.ps1 over boot_all.ps1 and run results/restart_ladder_optc.ps1 (Option C argv).

# v-ladder-optc -- LIVE 2026-10-22 08:58:24Z (ladder pid 2158860, subaccount 1; start record coins [DOGE HYPE NEAR XRP ZEC], pot_per_contract 7.8, market_cap_x 1, size 11 at pot $93.47). Operator 10-22: "Okay option c but keep something running to know if we ever would have loss or won one on the other option". research/cleanroom/ladder_live.py gains --coins and --pot-per-contract (defaults = unchanged) and a 5-try start read (the first two launches refused on 429s right after maintenance). Option C = the 5 coins where late 95-99c buyers lose least market-wide (tape 10-08..10-22: top-5 1 in 148 markets vs BTC 1/36, SOL 1/45, BNB 1/29, ETH 1/105), the same resting money as 9 coins x pot/14, one bid a market. Expected (paper replay, last 7 days, no losses): $9.37/day at a $643 pot vs $7.71 for the old setup; worst single loss ~$80 at $643. SHADOW: research/ladder_shadow.py replays the paper ladder (all 9 coins, all rungs) as A (old) / C / C+ (C + 95c rung) and lists every paper market where a ladder bid lost (all-time to 10-22: 0 of 263). Self-test PASSED with both argvs; coin-filter mutant caught. boot_all.ps1 carries the new argv (backup results/boot_all.before-optc.ps1). REVERT: copy results/boot_all.before-optc.ps1 over boot_all.ps1, write results/ladder-live.stop, wait for exit, delete it (boot_all restarts the old argv within 10 min; the code defaults are the old behavior).

# v-hedgejump6 -- INSTALLED 2026-10-22 in restart_bot.ps1, LIVE at the next restart (3-day run end ~2026-10-24 11:01Z via watch_bot, or any earlier halt/crash restart). Operator 10-22: "Hedge jump 6". Existing flag (AMENDMENT 52) --hedge-jump 6: also buy insurance 1 s after a 6-sigma one-second index move against our side; the 0.40 belief line stays. Evidence: insurance study wf_223c8340-f7b (+$151..+$189 since 09-22; checker +$114) and false-alarm study .sweep/q-2026-10-20a (+$76 09-12..10-20, +$150 since 09-24, older half -$58: fragile). STOP RULE: if the first 10 jump-fired hedges net below -$50 vs what the 0.40 line would have bought, remove the flag. Self-test PASSED with the full new argv (.sweep/q-2026-10-18j/selftest_jump6.out). REVERT: delete the --hedge-jump line in restart_bot.ps1 and rerun while flat.

# v-band15 -- LIVE 2026-10-21 11:01Z (watch_bot 3-day restart; start record band_mults [[0.955, 0.981, 1.5]], code_sha 32639cccc7f1, max-losses 0; log results/pinrun-live-20261021T110151Z.jsonl) -- installed 2026-10-18 21:xxZ. Operator 10-18: "if 1.5x makes money, do it". Existing flag (AMENDMENT 53): --band-mult 0.955 0.981 1.5 -- buys priced in [95.5c, 98.1c) may reach 1.5 x SIZE. Evidence (per-coin study wf_71bb9c0d-aae + skeptic): fills >= 95.5c lost 1.1% (15/1,372) vs 7.2% (22/305) below, every era; +$8.1-8.8/day, out-of-sample +$132 over 15.2 days; worst day -$276 -> -$314, worst single market -$169 -> -$228; erased if ~6 more losing markets than the 15 observed. Same code 32639cccc7f1; restart_bot -Check 78 flat strings; SELF-TEST PASSED with the full new argv (.sweep/q-2026-10-18j/selftest_band15.out). REVERT: delete the --band-mult line in restart_bot.ps1 and rerun while flat.

# v-phone-layout -- INSTALLED 2026-10-18 15:13Z, LIVE at the next pinphone restart (the running pinphone was started elevated by the logon task; this session cannot stop it). Operator 10-18: Telegram replies readable, every number next to its %, charts if possible, live data only. research/pinphone.py 656e36528afa, bars.py 2a95beb5d693, botstats.py cf125bd886cb, results/race_arms_scored.json dc5e26707b20 (byte-identical to the candidate reviewed GO + GO_WITH_FIXES, 0 blocking, in workflow wf_69636bd4-500; .sweep/q-2026-10-18e/tg/). Layout only (HTML headline number first, aligned tables, % beside money), the coin race described as bank-sized, /racestats arms labelled PAPER/STOPPED with Kalshi-scored and live-size $. Known: VERSIONS headers written as ISO "2026-10-18T11:01:21Z" lose their time in both parsers (write "2026-10-18 11:01Z"). REVERT: copy results\pinphone.before-tglayout.py, bars.before-tglayout.py, botstats.before-tglayout.py back over research\ and restart pinphone. TO GO LIVE NOW: from an ELEVATED PowerShell stop the pinphone python process; boot_all relaunches it within 10 min.

# v-fc-bookwatch -- INSTALLED 2026-10-18 15:11:58Z (forecaster restarted via results\forecaster-live.stop while FLAT; boot_all relaunches it on the new file). Operator 10-18: "Fix the frozen order book ... Definitely do" and "Fix the order part droppings". research/cleanroom/forecaster_live.py fb2c4c7d20aa -> 5a6db5940382 (only this file; bettor_paper.py / fc_variants.py / pintake.py / ordercli.py unchanged). FIX A (always on; --no-book-watch disables): FcWS allocates subscription ids under a lock so the bot can no longer unsubscribe its own fresh book after a reconnect (the 10-11 / 10-13 root cause); BookWatch marks a market stale on code 25, a server unsubscribe, an unconfirmed subscription (5 s), no snapshot 5 s after confirmation, a trade with no book message from 1 s before to 2 s after it, or 15 s of no book messages while index prints arrive; stale markets get no decision and orders are refused (why=stale_book) until a fresh snapshot; resubscribe at most every 10 s. FIX B (--resend-dropped, default OFF, NOT in boot_all's argv yet): re-send a dropped in-flight part once, re-checking every gate; measured +$8.41 since 10-10 (+$5.31 since 10-03) at real fill prices. The reviewer advised turning B on only after a few days of clean book_stale / book_resync logs. Reviews: 2 x GO, 0 blocking; mutation 11/11; tape replays identical on normal minutes; the 10-13 and 10-16 incidents refused. REVERT: copy results\forecaster_live.before-bookwatch.py over research\cleanroom\forecaster_live.py and restart through the stop file while flat.

# v-nopause -- LIVE 2026-10-18T11:01:21Z (watch_bot restarted the bot after the 10:46:05Z 2-loss halt; restart_bot 'flags now live' shows --max-losses 0; start record code_sha 32639cccc7f1; log results/pinrun-live-20261018T110121Z.jsonl; this run's 3-day end ~10-21 11:01Z) -- installed 10:4xZ (operator 10-18: "two losses should not pause the bot. Remove that."). Same code (C:\kals-live-0925k, code_sha 32639cccc7f1); argv --max-losses 2 -> 0 (0 disables the loss COUNT brake: pinrun.py argparse L23277 'halt after this many LOSING trades ... 0 disables'; the check at L17317 is `if a.max_losses and losses >= a.max_losses`). restart_bot.ps1 -Check passed (74 flat strings; all three shas ok). Still on: the day loss stop / run abort from --loss-cap-frac 0.187 x (bank + today's settled losses), about -$234 at today's bank (-60.00 applies only until the first balance read); insurance; every entry gate. Context: the 2-loss pause had halted the bot for 15 min on 10-14 02:30Z (BTC -$32.69 + a 15%-size HYPE -$2.45); 10-18 10:15Z ZEC -$32.69 made loss_count 1 on the current run. REVERT: put "--max-losses", "2" back in restart_bot.ps1 and rerun while flat.

# v-ladderboost -- LIVE 2026-10-18T04:42:46Z (pid 923780, was 38348; the 3-day run ended and watch_bot ran restart_bot.ps1; start record code_sha 32639cccc7f1, late_mult 1.5, same argv) (operator 10-13: "Fix ladder boost"; 10-18: "Yes ladder fix" / "Okay yes do the ladder fix"). Code C:\kals-live-0925k, **code_sha 32639cccc7f1**, ordercli.py 467782077a23 and pintake.py 9150d6b65968 byte-identical to 0925j = v-coinfrac + ONE live line in `_late48`: `if _csz is not None or _ssz is not None:`, so an hourly-LADDER (KXBTCD) order, which is capped at floor(SIZE x 0.12), is never recorded as a FIRED last-10-s boost and a losing ladder rung can no longer switch LATE_MULT off for every coin (patch results/ladderboost_0925k_pinrun.patch). Review GO 10-15 (self-test 1,385/0; orders/hedges identical in A/B; paper start with the live argv clean). Measured value (10-18, wf_4089772c-f05, .sweep/q-2026-10-18/ladderboost-value + skeptic-ladderboost): about +$0.01-0.02/day; hourly-BTC boost-offs ever 0; the one boost-off ever (SOL 10-03) came through the any-losing-leg path, which this does NOT close. Known: the order can only be the same size or smaller (a rung inside 10 s where the tapered depth is below the rung; never seen); a ladder market can still hold 1.5x its rung inside 10 s. Install 10-18 01:02Z: restart_bot.ps1 = C:\kals-live-0925k\restart_bot.ps1; a manual run while FLAT could not stop the elevated pid 38348 and aborted with nothing changed, so it went live at the natural run end. REVERT: copy results\restart_bot.before-ladderboost.ps1 (v-coinfrac, C:\kals-live-0925j d8c3c7dcb888) over restart_bot.ps1 and run it while flat (from an elevated shell, or let watch_bot do it at a run end). Bar: none for money (too small to read); revert at once if any live order differs in size from the 0925j rule other than a smaller ladder rung inside 10 s, or any error/exception in _late48.

# v-coinfrac -- LIVE 2026-10-13T11:30:51Z (pid 1226120, was 2343140, restarted FLAT by restart_bot.ps1; start record code_sha d8c3c7dcb888, coin_size_frac {KXHYPE15M: 0.15}, skip_coin [], keep_conn true, keep_warm true, series_size_frac 0.12, loss_cap_frac 0.187) (operator 10-13: "Just run hype live but scaled down proportionally to where the max bet is a loss that doesn't matter. Live tests are better."). Code C:\kals-live-0925j, **code_sha d8c3c7dcb888**, ordercli.py 467782077a23 and pintake.py 9150d6b65968 byte-identical to 0925i (the launcher checks all three) = v-fastconn (0925i, 813f1806e3ad) + ONE flag, `--coin-size-frac SERIES:F` (repeatable; results/coinfrac_0925j_pinrun.patch, 625 lines incl. 14 self-test checks): that 15-minute series bets max(1, floor(SIZE x F)) instead of SIZE. The coin's bet (`coin_size_for`, `_fsz`) is read once per candidate right after the touch size, and EVERYTHING that measures "full" reads it: the re-buy band (rebuy_ok), the scale-in cap, the late-add trigger and caps, the 45-s leg (EARLY_FRAC x it), the top-up (to it), the full-bet room (MAX_FULL_BETS 1.0) and the cap after every widener on both send paths; the late boost never records a FIRED boost on a capped coin (so a HYPE loss cannot switch LATE_MULT off for the other coins); it follows every autosize. HYPE: `--skip-coin KXHYPE15M` REMOVED, `--coin-size-frac KXHYPE15M:0.15` added = 14 contracts at SIZE 99 (the 45-s leg 4.67), never more than 14 x 1.5 (the late add inside 10 s) = 21 contracts on any route (verified route by route: main 14; early + top-up 14, or 18.66 if the top-up lands inside 10 s; late add 14 + 7; short fill 10 then 4 / 11; boost never; A68 after a hedge none) = worst case about $21 (1.8% of the $1,160 bank); a loss on a boosted HYPE at full size would have cost $98.76 in the same planted world vs $6.77 at 0.15. Why 0.15: his words "a loss that doesn't matter"; HYPE's live record 09-13..10-05 was 132 markets, 5 lost, -$32.36 at full size (worst -$49.02); paper HYPE 10-06..10-12 (twin relaunch) 27 markets, 1 lost, +$82.42, loss side optimistic. Insurance untouched: the hedge pass reads none of the new names (self-test by source); a held HYPE position of any size, incl. one adopted at startup, is hedged in full (driven 5/5, 14/14, 21/21, 99/99). The day loss stop and the 2-loss pause still count a HYPE loss (deliberate; the operator can ask for otherwise). Known, accepted: HYPE's 45-s leg is under 1 contract below SIZE 21 and is refused staged_none (main window unaffected); F = 1.0 is not "off" (it still caps the per-order late boost); the shared close budget means the other coins may now get a buy the old build refused as over budget (their own sizes unchanged). Self-test 1,383/0 (+14 v-coinfrac: default {} pinned; pure sizes; by source x2; NULL driven; control; driven at SIZE 20 -> HYPE orders 4, BTC identical; the 45-s leg scales 9.99 -> 2.0; 5 held HYPE hedged 5/5; PAPER path; re-buy band refused rebuy_band on a 1.5c cheaper ask, identical to a SIZE-4 bot; market cap at SIZE 99 under the live argv [14, 7] with BTC's boost firing alongside and none for HYPE; a HYPE loss: flag off late_boost_off 1, flag on 0 and hedged; a short fill 10 of 14 topped up 4 / 11). NULL against the LIVE code (results/coinfrac_null_2026-10-13.py): 12 of 12 planted worlds byte-identical with the flag off, at MAX_FULL_BETS 0 and 1.0; positive control: only 'BTC+HYPE, live' differs, 0 non-HYPE worlds. Reviews: two independent reviewers (insurance safety; sizing/integration) GO-WITH-FIXES -> fixes made (rebuy_ok/scale-in/late-add on the coin's bet; no boost firing on a capped coin; a repeated series refused) -> an independent verifier GO-WITH-FIXES: 14 mutants, 11 caught; of the 3 not caught, the only money-relevant one (the full-bet trim room) is now caught by the short-fill check (confirmed: that mutant FAILS), the other two are harmless (a gate-vs-zero_take labelling, the paper-only cap); no UnboundLocalError path; max 21 on every route. Startup path: the full new argv with --live + --selftest -> PASSED 1,383/0; argv refusals (F 0, F 1.5, no fraction, a ladder series, a series also --skip-coin, a series twice) all refuse by name; paper runs with the exact argv (--minutes 2) at 10:35Z, 11:03Z and 11:23Z: start record carries code_sha + coin_size_frac, HYPE back in the universe, 0 errors. Launcher results/restart_bot.coinfrac.ps1 (-Check: 74 flat strings, all three files ok) copied over restart_bot.ps1; results/restart_bot.before-coinfrac.ps1 is the launcher it replaced. Bar: READS_DUE hype-live-frac (pre-registered 10-13 ~11Z before deploy: revert at once if a HYPE position ever exceeds floor(SIZE x 0.15) x 1.5, a HYPE market loses over $30, or a HYPE position is not hedged/settled; 7-day/60-market verdict 10-20). Follow-ups, not blocking: port the flag to the repo's research/pinrun.py (the twin's lineage); the pre-existing KXBTCD shape (a boosted-then-capped ladder order is recorded as FIRED, so a ladder loss would switch the boost off for every coin) is NOT fixed here because fixing it changes the live ladder's records (byte-identical NULL) -- put to the operator.

**REVERT:** `Copy-Item C:\kals-repo\results\restart_bot.before-coinfrac.ps1 C:\kals-repo\restart_bot.ps1 -Force`, then, while flat, `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (= v-fastconn, 0925i, HYPE skipped again). Same code, HYPE out: edit restart_bot.ps1 to `"--skip-coin", "KXHYPE15M",` in place of the `--coin-size-frac` line and restart while flat (the flag's default {} is today's behaviour exactly).

---

# v-fastconn -- LIVE 2026-10-12T11:15:11Z (pid 2343140, was 1403468, restarted FLAT by restart_bot.ps1; start record code_sha 813f1806e3ad, keep_conn true, keep_warm true, keep_idle_max_s 120, lookup_budget_s 2.5, ordercli_sha 467782077a23, pintake_sha 9150d6b65968, series_size_frac 0.12, loss_cap_frac 0.187; first autosize 95 at a $1,124.88 bank, hourly 11, stop -$210.35) (operator 10-12: "Yes to fast orders. Make sure to closely monitor for insurance and errors caused by it."). Code C:\kals-live-0925i, **code_sha 813f1806e3ad**, ordercli.py 467782077a23, pintake.py 9150d6b65968 (the launcher checks all three) = v-snowball (0925h, deda2006d5ae) + one kept-open HTTPS connection per thread for orders, insurance and cancels (`--keep-conn on`; 0925g's change: a connection idle over the limit or seen closed is replaced before the send; a failed write is retried once on a fresh connection; a lost reply to an order is NEVER resent -- the order is looked up by client_order_id within a 2.5 s cap, else outcome UNKNOWN, counted covered, re-checked by v-safety2 at +3 s) + `--keep-warm on` (the trading thread's existing periodic GETs ride the kept connection; idle limit 120 s vs production's measured idle-close >= 240 s; no new network call inside 60 s of a close) + logging: `conn_event` records for every non-routine connection event (conn kept/fresh, hedge yes/no, client_order_id, ms, error text), warm/cold + send ms on every order and hedge record, `conn_stats` every 300 s, err text on hedge_unknown and on -1 orders; a recovered order is booked at its real fill cost. Demo orders: warm 85.8 ms median vs today's code 264.0 ms; production GET warm 30-43 ms vs cold 64-86 ms (production ORDER speed not measured -- demo only). Built, reviewed GO by two independent reviewers (insurance safety; integration/speed), then the gaps they found closed and verified GO (self-tests pinrun 1369/0, ordercli, pintake pass; 42/42 mutants caught; paper run across the 11:00Z hourly close: 767 warm GETs, 1 cold, 0 conn_event, 0 errors). Accepted leftover cases (rare): a server close racing our send, or a hung server -> outcome UNKNOWN, insurance re-checked and re-sent by v-safety2 after ~3 s, and new entries halt for the rest of that run. Bar: READS_DUE fastconn-live (pre-registered before the build). Launcher results/restart_bot.fastconn.ps1 copied over restart_bot.ps1.

**REVERT:** fastest, same code: edit restart_bot.ps1 to `"--keep-conn", "off", "--keep-warm", "off"` and restart while flat (today's urllib path exactly). Whole version: `Copy-Item C:\kals-repo\results\restart_bot.before-fastconn.ps1 C:\kals-repo\restart_bot.ps1 -Force`, then, while flat, `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (= v-snowball, 0925h).

---

# v-snowball -- LIVE 2026-10-11T10:43:32Z (pid 1403468, was 3066312, restarted FLAT by restart_bot.ps1; start record code_sha deda2006d5ae, series_size_frac 0.12, loss_cap_frac 0.187, auto_size_max None; first autosize: size 92 at a $1,092.58 bank, hourly 11, day/run stop -$204.31) (operator 10-11: "Bitcoin hourly yes can increase, and I also want it to automatically size up with its bank", "Grow day stop", "Fix count loss", "I don't want to cap any growth"). Code C:\kals-live-0925h, **code_sha deda2006d5ae** = 0925e + (a) `--series-size-frac 0.12` replaces `--series-size 1`: hourly KXBTCD contracts = floor(SIZE x 0.12), recomputed at every autosize (10-11 today, grows with the bank; hedges cover what is held); (b) AUTO_SIZE_MAX 250 removed (no size ceiling; `--size-max N` restores one); (c) `--loss-cap-frac 0.187` replaces `--loss-cap 200`: the run abort and the ET-day loss cap = 0.187 x (bank + today's settled losses added back), ~$200 at a $1,070 bank, growing with the bank and NOT shrinking as the day's losses come in; (d) the 2-loss pause counts a MARKET once, only when all its legs net below zero (the 10-10 ZEC false pause: bet +$62.10, insurance -$57.65 = +$4.45 counted as a loss). Built + independently reviewed GO twice (0925f: 1333/0 self-test; 0925h: 1358/0, 15 reverts all caught, paper startup with the live argv PASS). Launcher results/restart_bot.snowball.ps1 copied over restart_bot.ps1.

**REVERT:** `Copy-Item C:\kals-repo\results\restart_bot.before-snowball.ps1 C:\kals-repo\restart_bot.ps1 -Force`, then, while flat, `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`.

---

# v-race-snowball -- LIVE 2026-10-11T10:15:32Z (pid 494356, start record bank_sizing {contracts_per_bank 0.019048, stake_per_bank 0.038095}; old pid 2697236 held no open leg and was stopped after its stop file did not make it exit -- the stop file only blocks new legs) (operator 10-11: "I don't want to cap any growth ... Every account should be automatically increasing bets with their bank"). Live coin race (research/pinracearm.py sha 19355ccf6853, main account) gets --contracts-per-bank 0.019048 --stake-per-bank 0.038095: contracts a leg = floor(bank x 0.019048) (20 at $1,050) and the open-stake cap = bank x 0.038095 ($40 at $1,050), read from subaccount 0 pool 2 at most every 300 s, only 4:00-10:00 into a quarter hour with no open leg; a failed read keeps the last size. 2-loss stop and tie-as-loss unchanged. Built + independently reviewed GO 10-11 (self-test 271/0; paper runs; 40-day property sweep 0 violations). boot_all.ps1 line updated (backup results/boot_all.before-race-snowball.ps1); restart via results/restart_race_1011.ps1 (stop file -> exit -> start).

**REVERT:** copy results/boot_all.before-race-snowball.ps1 over boot_all.ps1, create results/pinracepenny.stop, wait for exit, delete it; the keep-alive restarts the old argv.

---

# v-racereward-test -- LIVE 2026-10-11T08:24:47Z (pid 3097040, subaccount 4 pool 2, funded $55 from main 08:2xZ; operator 10-10 'Yes to coin race test', 10-11 'Create subaccount 4'). NEW STRATEGY FAMILY (test): research/sweep/racereward_live.py code_sha c73979198066 -- 1,000 YES at $0.01 post_only/maker on DEAD coin-race legs (KXCRYPTOLEAD15M) in each race's last 360 s, cancelled at close-60 s, to earn Kalshi's liquidity reward ($20 per leg per 15-min window, period_reward in centi-cents). Rails in code: subaccount only, price exactly 0.01, <= 1,000, <= 5 resting, <= $55 committed, day budget -$30 (acknowledged-not-final cancels keep their collateral), no order that cannot earn the $1 floor, NO side must qualify, one order per coin per race across restarts, instance lock, stop file results/racereward-live.stop, 20 races then exit. Reviews: results/MONEY_SWEEP_2026-10-10.md item 1 (first review GO with fixes; re-review NO-GO on B1 -> fixed, attack A4 0 breaches in 400 runs; self-test 115/0). Also created 10-11 by the same command (first try returned 3): an EMPTY subaccount 3 in pool 2, unused.

BAR: READS_DUE racereward-test. **STOP / REVERT:** create results/racereward-live.stop; return the cash with `python research/ordercli.py --sub-return <dollars> --sub 4` (dry run first, then --live --signoff <token>).

---

# v-stp-maker -- LIVE 2026-10-10T02:07:23Z (pid 772168, was 3907636; start record: mode live, code_sha 5075b1783acf, toxic_fresh false, max_edge_c 10.0, early_max_edge 10.0, skip_coin [KXHYPE15M], max_full_bets 1.0, no_drawdown_halt true, xfer_confirm true; ktruth at startup: 0 held). Restart via restart_bot.ps1 while FLAT (pinflat), both recorders writing after (operator 2026-10-09 ~9:50 PM ET: "Go v-STp-maker"). The SAME live argv as v-bankfix-nodd (byte-identical flag list; versioncheck clean) on C:\kals-live-0925e, **code_sha 5075b1783acf** (0925d untouched). Launcher: results/restart_bot.stpmaker.ps1 copied over restart_bot.ps1; -Check PASS (70 flat strings).

WHAT CHANGES: insurance (hedge) orders carry `self_trade_prevention_type = "maker"` (research/pintake.py take(): `if hedge: body["self_trade_prevention_type"] = "maker"`). Kalshi's self-trade prevention is per order and applies across subaccounts on one unified book (a YES bid at 98c IS a NO ask at 2c); with the old `taker_at_cross` an insurance IOC that would cross our own ladder's resting bid (subaccount 1) is CANCELLED; with `maker` the ladder's resting bid is cancelled and the insurance proceeds. Entries keep `taker_at_cross`. 0925e also carries `--max-edge-c` (default = the old 10c constant) and new start-record fields (toxic_fresh, max_edge_c, edge_cap_tau); with this argv they change nothing (start record: toxic_fresh false, max_edge_c 10.0, early_max_edge 10.0).

EVIDENCE: results/FINAL_SYNTHESIS_2026-10-09.md (blind design competition: every judge kept this; measured money effect $0 -- all 14 insurance orders since 09-28 checked, the ladder's bids came 4-29 s after each, so it has not happened yet). Self-tests: pintake --selftest PASS (new check: the entry POST carries taker_at_cross, the hedge POST maker); pinrun --selftest PASS; startup path in PAPER with this exact argv PASS (results/pinrun-paper-20261009T111025Z.jsonl, errors 0).

BAR: READS_DUE `stp-maker-live` (pre-registered 10-09): revert at once if any insurance order is refused or cancelled for self-trade, or the insurance path errors; keep after 10 alarms with every insurance order carrying maker and the filled share not below the previous 14 alarms.

**REVERT:** `Copy-Item C:\kals-repo
esults
estart_bot.before-seen.ps1 C:\kals-repo
estart_bot.ps1 -Force` then, while flat, `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (the 0925d build, code_sha c0fe4953e891).

---

# v-ladder-capfix -- LIVE 2026-10-07T12:14:10Z (ladder pid 4047108, was 3832268; subaccount 1; start record 12:14:18.105Z: live true, auto_size true, pot $76.73 -> size 5, market_cap_x 2.0, close_cap_x 0). Code: research/cleanroom/ladder_live.py blob 9fec7b284c9f, previous commit ef85845. Argv unchanged (boot_all.ps1 not edited). Run via results/restart_ladder_1007.ps1 (dry run ok, then live; log results/restart_ladder_1007.log): stop file -> old ladder exited in ~1 s (exit record 12:14:01.992Z) -> boot_all not running -> stop file deleted -> started; one live ladder after.

EVIDENCE: results/READS_1007.md ladder-caps, PLUMBING FAIL on clause 1: KXZEC15M-26OCT060945-45 (10-06 9:45 AM ET) held 15 contracts (3 bids of 5) by Kalshi fills against the x2 cap of 10. Bid 8593 filled on Kalshi at 13:44:58.08Z; its cancel was in flight until :58.255 (404); the third bid was decided at :58.215. A bid with status 'cancelling' was counted by neither open_orders() (sending/resting) nor limbo() (cancel_failed), so exposure(), market_contracts() and every rail were blind to it while its cancel was in flight. 1 market of 3,609 bid since 10-03; it won (+$0.30) but was a $14.70 bet, 19% of the pot vs 14% intended.

WHAT CHANGES: new Broker.in_cancel() = bids with status 'cancelling', not seen finished by the poller (terminal), filled < size; pending() = limbo() + in_cancel() (disjoint by status). exposure() and market_contracts() (and so the max_contracts / max_commit / market_cap / close_cap rails) now count pending() at SIZE - filled, the way limbo() already counted a failed cancel. No double count: the remainder drops out when the cancel returns (-> cancelled), hands over to limbo() once on a 404 (-> cancel_failed), goes to 0 when the poller books the fill (it is then in held), and drops when the poller sees the order finished. flat() unchanged (already treated cancelling as not flat). Effect: a re-bid on a market whose last bid is mid-cancel is refused when held + that remainder + the re-bid > 2 x size; with nothing cancelling every count equals the old formula.

SELF-TEST: 70 -> 80 checks (+10), PASS with the live argv (`python research/cleanroom/ladder_live.py --subaccount 1 --live --auto-size --market-cap-x 2 --minutes 10080 --selftest`). New: the 10-06 shape (5 held, bid A resting, paper consumes A, cancel queued, re-bid on a later tick) -> counted 10 / $9.80 and the re-bid refused why=market_cap; A's fill booked mid-cancel -> held 10, no double count; partial fill counts SIZE - filled; cancel completes -> remainder gone and a re-bid places; terminal cancelling not counted; cancelling -> cancel_failed counted once (5 before, 5 after); NULL: nothing cancelling -> exposure/market_contracts equal the pre-fix formula; cap off -> the same re-bid places. With in_cancel() reverted to [] the self-test FAILS 5 of the 10 (checked from a scratch copy).

UNTESTED: whether refusals rise enough to cost income (expected: rare, only bursts inside a cancel's ~0.2-2 s flight). Read: READS_DUE ladder-capfix (2026-10-10T12:00Z).

**REVERT:** `git checkout ef85845 -- research/cleanroom/ladder_live.py`, then the same stop-file restart: `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/results/restart_ladder_1007.ps1` (its self-test check passes on ef85845 too; same argv).

---

# v-bankfix-nodd -- LIVE 2026-10-06T15:41:22Z (pid 1185604, code_sha c0fe4953e891, no_drawdown_halt true, xfer_confirm true; operator: 'If we lose 20% ... why would we have it' / 'fix whatever issue that is with detecting false deposits'). Was PREPARED 2026-10-06 ~06:45Z, NOT LIVE (deploy below, while the bot is flat). Operator 2026-10-06 ~06:15Z: (b) "If we lose 20% we aren't actually going to have any solutions so why would we have it. All we'd end up doing is running it so it can earn it back." -> the 20% DRAWDOWN halt off; (c) "Also fix whatever issue that is with detecting false deposits" -> v-bankmove ported into the live build. Code: C:\kals-live-0925d\research\pinrun.py = C:\kals-live-0925c (live, v-skiphype, code_sha 3776ff66b2fb) + results/bankfix_0925d_pinrun.patch, **code_sha c0fe4953e891**; plus research\pinxfer.py copied byte-identical from the repo (sha256[:12] 051913f393be; v-bankmove's transfer_rows imports it). The other seven modules are byte-identical to 0925c; C:\kals-live-0925c is untouched.

EVIDENCE (c), live logs: under the 09-25 classifier (live now), results/pinrun-live-20261005T142402Z.jsonl: 2026-10-05T22:04:05Z `external` withdrawal -$19.07 (bank $1,001.04, mark moved to $1,074.18) and 22:09:05Z `external` deposit +$20.00 (mark to $1,094.18), with $0.00 realised by the main bot in between -- the coin race's stake leaving and its payout returning on the same cash account; no transfer happened. The mark now sits $0.93 above where real trading put it ($1,093.25). Under v-bankmove (the 10-03 live run, results/pinrun-live-20261003T081552Z.jsonl) the same shapes read right: 10-03 10:00:55Z -$18.13 and 10:05:55Z +$20.00 -> `unexplained` ("no matching Kalshi transfer"), mark untouched at $1,135.40; 10-04 03:21:11Z a REAL -$50.00 subaccount transfer -> `external` naming transfer ab8f1cfa-9b13-4d24-8617-53c33f148bbe. The 10-04 revert to the 09-25 build (v-revert0925) dropped the fix; this puts it back. Before v-bankmove, 10-01 had four misreads, one of them a delayed $84.62 payout read as a withdrawal (IDEA_LEDGER F21).

WHAT CHANGES:
1. v-bankmove (always on, no flag; today's research/pinrun.py transfer_rows / fetch_transfers / match_transfer / confirm_move and the autosize_tick branch, ported hunk for hunk): a bank move the bot's own settlements do not explain is called a deposit/withdrawal (`external`, mark shifted, transfer ids recorded) ONLY when GET /portfolio/deposits, /portfolio/withdrawals or /portfolio/subaccounts/transfers shows a matching finished transfer in the window; otherwise `unexplained`, the mark is NOT moved and the change counts as trading. A failed read is never a withdrawal. Reads happen only on such a move, only while flat (autosize_tick), cached 60 s, 4 s timeout each. Start record gains `xfer_confirm: true`.
2. `--no-drawdown-halt` (new flag, default off): risk_abort never returns the "DRAWDOWN brake" halt. The drawdown and the high-water mark are still computed every sizing tick; a crossing of 20% is recorded ONCE (`drawdown_no_halt`, re-armed when back inside). Start record gains `no_drawdown_halt: true`.

HOW THE DRAWDOWN HALT WORKS (this build): MAX_DRAWDOWN = 0.20, a constant (no flag before this). The mark (results/pinrun-hwm.json) is raised by every bank read and never lowered except by a classified transfer (shift_hwm) or the operator's START after a DRAWDOWN halt (v-hwm-reset). autosize_tick (every 300 s, flat only) computes drawdown = (mark - bank)/mark; at >= 20% risk_abort halts TERMINALLY and watch_bot.ps1 HOLDS (never restarts) until START writes pinrun-hwm.reset. Now: mark $1,094.18, bank $1,035.94 (04:15Z) = 5.3% down; the halt line is $875.34.

WHICH STOPS REMAIN with the flag on (all unchanged):
- Run loss abort: this run's SETTLED losses reach -$200 (`--loss-cap 200` clamps the derived -2 x size x 2 = -$352 at size 88; `--loss-abort -60` only holds until the first sizing tick). Halts; watch_bot restarts after a 15-min cooldown with a fresh run.
- DAY loss cap: the same -$200 against the ET day's settled total on disk (pinrun-dayloss.json). Survives restarts, so in practice no trading for the rest of that ET day.
- Loss COUNT brake (`--max-losses 2`): 2 losing markets in one run. Halts; watch_bot restarts after 15 min (the count clears on restart, or when the bank gets back to the mark).
- Pauses that clear by themselves: open cap (3 x size contracts held), stake cap. Error halts: 2 order-path errors, 5 consecutive errors, 40 failed reconciles.
NOT stops: `--bank-brake 4.00` is SIZING (bet = bank / $11.76 = bank / (4 x 3 worst-close legs x 98c) -> 88 at $1,035.94); it shrinks bets as the bank falls but never halts.
WHAT THAT MEANS: nothing stops the bot for good any more. A run of bad days can lose up to ~$200 per ET day, every day (plus whatever is open when the cap lands).

THE MARK STILL AFFECTS BET SIZE, so the bank-move fix still matters with the halt off: (1) the last-10-s 1.5x boost (A48, live `--late-mult 1.5`) is capped by one_coin_cap's headroom (bank - 0.8 x mark) / 98c -- full boost while the bank is within ~8.6% of the mark, shrinking after, gone at 20% down (orders 1x); a false deposit raises the mark and cuts the boost, a false withdrawal lowers it and widens it; (2) the 2-loss counter clears when the bank gets back to the mark (A39). The base bet (bank / $11.76) does not read the mark.

watch_bot.ps1 needs NOTHING: its DRAWDOWN HOLD keys on a "DRAWDOWN brake" halt record, which this build never writes with the flag on; its other verdicts are unchanged. Not edited.

SELF-TEST (1,283 -> 1,319, +36: 20 ported with v-bankmove, 16 new): v-bankfix-nodd default False, pinned/restored; by source (risk_abort reads the flag once, on the DRAWDOWN line; main sets it; start record carries it); unit (25% drawdown halts with the flag off, not with it on; with it on -$200 realised still halts "loss abort", a cent under does not; 2 losses still halt "loss COUNT brake"; -$201.50 on the ET day still halts a live run "DAY loss cap"; 60% drawdown alone halts nothing); DRIVEN through the real trade loop (bank $750 under a $1,000 mark: flag off halts on DRAWDOWN and buys nothing, flag on buys and logs one drawdown_no_halt at 25%); NULL DRIVEN (bank $1,000 no mark, and $750 under $850 = 11.8%: flag on = flag off, every record and buy); v-bankmove port on THE 10-05 22:04Z RACE (-$19.07 then +$20.00, no transfer: two `unexplained`, no `external`, mark stays $1,093.25, drawdown measured on it); CONTROL with confirmation off reproduces the live 10-05 walk 1,093.25 -> 1,074.18 -> 1,094.18; a REAL $19.07 subaccount transfer out -> `external` naming it, mark $1,074.18; a 503 on the listing -> `unexplained`, never a withdrawal. Startup path: `C:\Python314\python.exe -u C:\kals-live-0925d\research\pinrun.py <the full new argv, with --live and --no-drawdown-halt> --selftest` -> SELF-TEST PASSED, 1,319 ok, 0 failed, exit 0 (C:\kals-live-0925d\restart_bot.ps1 is a copy of the new launcher). NULL against the LIVE code: results/bankfix_null_2026-10-06.py runs both builds' own offline loop and autosize_tick -> the 12 v-skiphype worlds at live settings byte-identical with the flag off AND on; 3 bank-path worlds identical with the flag off (the 25% one halts on DRAWDOWN in both), with it on only the 25% world differs (buys, 1 drawdown_no_halt); a trading-only bank series identical; the race shape identical to live with confirmation off, `unexplained` with it on. `results\restart_bot.bankfix.ps1 -Check`: 70 flat strings, code file present, code_sha c0fe4953e891. Live state files (pinrun-hwm.json, pinrun-dayloss.json, pinrun-live-size.json) unchanged by the tests. Read: READS_DUE 'bankfix-nodd'.

**DEPLOY** (the bot must be flat; restart_bot refuses otherwise; watch_bot relaunches through the same file, so after the copy any relaunch runs the new build):
`Copy-Item C:\kals-repo\results\restart_bot.bankfix.ps1 C:\kals-repo\restart_bot.ps1 -Force`
`powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`
then confirm the new live start record says code_sha c0fe4953e891, no_drawdown_halt true, xfer_confirm true, skip_coin ["KXHYPE15M"], max_full_bets 1.0, and run `python research/versioncheck.py`. Flag diff vs today's launcher: script `C:\kals-live-0925c\research\pinrun.py` -> `C:\kals-live-0925d\research\pinrun.py`; hash guard 3776ff66b2fb -> c0fe4953e891; ADDED `"--no-drawdown-halt"`; nothing else. Optional, the operator's call: the mark carries the race's phantom +$0.93 ($1,094.18 vs $1,093.25); not worth a hand edit.

**REVERT:** `Copy-Item C:\kals-repo\results\restart_bot.before-bankfix.ps1 C:\kals-repo\restart_bot.ps1 -Force` then `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (flat first). That file is the v-skiphype launcher byte for byte: C:\kals-live-0925c, code_sha 3776ff66b2fb, the 20% halt on, the 09-25 classifier. To keep the bank fix but bring the halt back, delete the `"--no-drawdown-halt",` line from restart_bot.ps1 and rerun it (same code, same hash).

---

# v-skiphype -- LIVE 2026-10-05T14:24:02Z (pid 2931196, code_sha 3776ff66b2fb, skip_coin [KXHYPE15M], max_full_bets 1.0; operator: 'Sure drop it'; 0 HYPE watch records after start). Was PREPARED 2026-10-05 ~14:30Z, NOT LIVE (deploy below, while the bot is flat). Operator 2026-10-05: "Sure drop it" -- stop the live main bot trading HYPE (KXHYPE15M). The live build (09-25 + v-fullcap, C:\kals-live-0925b, code_sha 269958db6d68) plus ONE flag: `--skip-coin KXHYPE15M`. Code: C:\kals-live-0925c\research\pinrun.py = C:\kals-live-0925b + results/skiphype_0925c_pinrun.patch, **code_sha 3776ff66b2fb**; the other seven modules in that folder are byte-identical to 0925b; C:\kals-live-0925b is untouched.

EVIDENCE (our live fills, Kalshi main account, 15-minute coins, 2026-09-20..10-05; results/READS_1005.md section 3): HYPE 81 markets, 4 lost (all over $20, -$198.09), **-$103.12** (-2.44% on money bet); the other 8 coins 539 markets, 13 lost, **+$360.22** (+1.15%). Leaving HYPE out since 09-20 would have made $103.12 more. It hangs on 4 losses (two of them 10-04/10-05: -$49.02, -$73.88); 8 in 100 random 81-market draws from all coins do as badly, so suggestive, not proven -- hence the week's read below.

WHAT CHANGES: KXHYPE15M is taken out of the universe. The refresh still makes the same GET /markets for it, but its markets are never put in seen_markets: never scanned, never watched (no book subscription), never entered or topped up. A belt-and-braces entry gate `skip_coin` on the scan (below the hedge pass, before the signal) refuses one should it ever reach the scan; it cannot fire while the universe rule holds. Start record gains `skip_coin: ["KXHYPE15M"]`. Unknown series names are refused at start; skipping every series is refused.

WHAT IT CAN NEVER BLOCK (a gate must never block a hedge): KXHYPE15M stays in series_index and its index (HYPEUSD_RTI) stays on the feed, so the v-safety2 startup read still ADOPTS a HYPE position already on the account (after a crash-relaunch mid-bet) instead of calling it foreign; its facts come from the refresh (`skip_facts`), its book is subscribed the moment it is adopted (record `skip_coin_watch`), and the hedge pass, reconcile and settlement manage it exactly as any other position. The hedge pass does not read the flag (self-tested by source). Coin race (KXCRYPTOLEAD) is a separate bot: untouched. The HYPE hourly ladder (KXHYPED) is not affected (not traded live).

SELF-TEST (9 new checks, 1,274 -> 1,283): default () = off, pinned in every offline world and restored; pure (HYPE 15M skipped; BTC, KXHYPED, flag off not); by source (hedge pass never reads it; gate below the hedge pass and before the signal; main() does not shrink series_index or the index feed; start record carries skip_coin); NULL DRIVEN (a world with no HYPE: flag on = flag off, every record, order and GET); control (flag off buys HYPE and BTC); DRIVEN (flag on: HYPE never subscribed, signalled or bought; BTC's orders identical to a world with no HYPE); HELD HYPE (5 YES on Kalshi from before a restart, book only after subscription: adopted, subscribed, hedged 5 of 5 on the collapse, no entry, no hedge_no_ask); EQUIVALENCE (that position's hedge and both settled legs identical to the flag off). NULL against the LIVE code: results/skiphype_null_2026-10-05.py runs both builds' own offline loop on 12 planted worlds (the 9 v-fullcap worlds + BTC/HYPE live, BTC/HYPE/ETH paper, HYPE held at restart) -> 12 of 12 byte-identical with the flag off, at MAX_FULL_BETS 0 and at the live 1.0; positive control (`SK=1 FC_X=1.0`): only the 3 HYPE worlds differ (HYPE never watched/bought; the held HYPE position hedged 5 of 5 either way), the 9 non-HYPE worlds identical. Startup path: `python C:\kals-live-0925c\research\pinrun.py <the full new argv, with --live and --skip-coin KXHYPE15M> --selftest` -> SELF-TEST PASSED, 1,283 ok, 0 failed, exit 0 (C:\kals-live-0925c\restart_bot.ps1 is a copy of the new launcher). `results\restart_bot.skiphype.ps1 -Check`: 69 flat strings, code file present, code_sha 3776ff66b2fb. Read: READS_DUE 'skiphype' (due 2026-10-12T12:00Z).

**DEPLOY** (the bot must be flat; restart_bot refuses otherwise; the watchdog relaunches through the same file, so after the copy any relaunch runs the new build):
`Copy-Item C:\kals-repo\results\restart_bot.skiphype.ps1 C:\kals-repo\restart_bot.ps1 -Force`
`powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`
then confirm the new live start record says code_sha 3776ff66b2fb and skip_coin ["KXHYPE15M"] (and max_full_bets 1.0), that no `watch` record adds a KXHYPE15M ticker, and run `python research/versioncheck.py`. Flag diff vs today's launcher: script `C:\kals-live-0925b\research\pinrun.py` -> `C:\kals-live-0925c\research\pinrun.py`; hash guard 269958db6d68 -> 3776ff66b2fb; ADDED `"--skip-coin", "KXHYPE15M"`; nothing else. B6 note: a new code_sha moves the live run's join key; the paper twins keep theirs (they are not re-synced by this change).

**REVERT:** `Copy-Item C:\kals-repo\results\restart_bot.before-skiphype.ps1 C:\kals-repo\restart_bot.ps1 -Force` then `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (flat first). That file is the v-revert0925-fullcap launcher byte for byte (sha256[:12] 781ed6d7964d): C:\kals-live-0925b, code_sha 269958db6d68, --max-full-bets 1.0, HYPE traded.

---

# v-revert0925-fullcap -- LIVE 2026-10-04T09:20:40Z (pid 4202332, start record code_sha 269958db6d68, max_full_bets 1.0; operator: 'Okay one full coin max. Or does a 1.5 coin do better? Check it out' -> 1.0x by the pre-stated rule). Was PREPARED 2026-10-04 ~09:30Z, NOT LIVE (the operator swaps the launcher and restarts) -- the live 09-25 build plus ONE backported rule: `--max-full-bets 1.0`. An ENTRY may not take the contracts a market holds on the side already held past 1.0 x the full bet in force (SIZE x the same band / doubt / late multiple v-topup completes a position to: x1.5 inside the last 10 s, else x1; a KXBTCD rung's full bet is its series size). An order that would cross the cap is TRIMMED to the room (so a top-up of an unfinished position still completes it); a market with no room is refused before the signal, gate `full_cap` (no attempt burned). Operator 10-04: "Okay one full coin max. Or does a 1.5 coin do better? Check it out." Code: C:\kals-live-0925b\research\pinrun.py = the 09-25 build (git 2fce1837e6, f9548c5571ff) + results/fullcap_0925b_pinrun.patch, **code_sha 269958db6d68**; C:\kals-live-0925 is untouched.

PRE-STATED CHOICE RULE (written before the numbers): pick 1.5x only if its net beats 1.0x by more than $20 over the whole window AND it does not let through any loser bigger than 10% of the account at the time; otherwise 1.0x.

Measured on OUR LIVE FILLS only (results/pinrun-live-*.jsonl orders filled > 0, 2026-09-09..2026-10-04 08:30Z, 1,167 fifteen-minute markets, every bet-side count matching Kalshi to 0.5 contract) joined to Kalshi per-market money (results/kalshi_ledger.json: revenue/100 + min(yes,no) - costs - fee). Counterfactual: walk each market's bet-side fills in time order, keep at most X x the full bet in force at each order, drop the LATEST contracts beyond it. Winner: each dropped contract's 1 - price - fee is given up (and its share of any insurance loss is saved). Loser: the market's net scaled by kept/actual -- ASSUMES the insurance would have been sized in proportion. Cannot see knock-on effects (a refused second bet frees close budget for another coin). Whole window, all 12 coins: Kalshi +$744.26 on $58,374 bet-side spend.

| cap | markets touched | winners: $ given up | losers: $ saved | net vs no cap | 09-09..09-27 08:10Z (multi-bet builds) | 09-27 08:11Z..10-04 03:22Z (one-full-bet live) | 10-04 03:22Z.. (09-25 build) |
|---|---|---|---|---|---|---|---|
| 1.0x | 27 | 24, -$44.97 | 3, +$165.96 | **+$121.00** | +$132.38 (19 touched) | -$11.38 (8 winners, all v-lateadd adds at 11-15 s and pre-v-topup top-ups) | 0 touched |
| 1.25x | 23 | 20, -$28.81 | 3, +$128.71 | +$99.89 | +$105.86 | -$5.97 | 0 |
| 1.5x | 13 | 10, -$14.00 | 3, +$91.45 | +$77.45 | +$78.29 | -$0.84 | 0 |
| 2.0x (~ the 09-25 build's --max-per-market 2) | 1 | 0 | 1, +$16.94 | +$16.94 | +$16.94 | 0 | 0 |

The three losers every cap touches (Kalshi $ actual -> at 1.0x / 1.5x; account at the time):
- KXNEAR15M-26SEP082045-45 (09-09 00:44Z, 59 contracts = 2.95 bets of 20): -$52.60 -> -$17.83 / -$26.75; account ~$162 (reconstructed: the 09-13 autosize bank $193.76 minus settlements between) -- at 1.5x 16.5% of the account, at 1.0x 11.0%.
- KXBTC15M-26SEP232030-30 (09-24 00:29Z, 176 = 2 bets of 88): -$130.41 -> -$65.20 / -$97.81; account $1,036 (1.5x: 9.4%).
- KXBTC15M-26SEP270000-00 (09-27 03:59Z, 198 = 2 bets of 99, both in the same second): -$131.98 -> -$65.99 / -$98.98; account $1,166 (1.5x: 8.5%).
After 09-27 08:11Z --one-full-bet was live, so few markets exceeded 1x: only the half-bet late adds at 11-15 s and the top-up leak v-topup closed on 09-30; that window shows only the cost side. The whole money case is THREE losing markets (two of them the same-second BTC double bets); without them every cap is a small loss. It is a size-of-the-worst-market rule more than a proven money rule.

**CHOICE: 1.0x.** 1.5x nets $43.55 LESS than 1.0x (it does not beat it at all, let alone by $20), and it lets NEAR 09-09 through at 16.5% of the account. (Without NEAR 09-09, the oldest-code market, 1.0x still beats 1.5x by $34.6.) Note: at 1.0x the late add at 11-15 s (v-lateadd, half a bet) is refused; inside 10 s the full bet in force is 1.5x, so the A48 late boost and a late add there are untouched. KXBTCD rungs are capped at 1 contract (series size 1; was up to 2 with --max-per-market 2).

What it blocks, stated as the standing rule requires: entry orders (full, top-up, late add, scale-in) on the side already held, past 1.0 x the full bet in force. What it can never block: any hedge (the hedge pass never calls it; it stands down for a market already insured -- hedged_side set, where A68's own cap governs -- and for an entry on the OTHER side from the one held).

Self-test (12 new checks, 1,262 -> 1,274): default OFF; pure room arithmetic (99 held of 99 -> 0 = refuse; 30 held -> 69 = trim; 1.5x -> 49.5; late x1.5 -> 49.5; first buy / other market untouched); hedge exemptions (other side, insured market -> no cap); by source (two calls, both on the entry scan after the whole hedge pass; refusal before the signal; trim LAST on both paths, after A68 and every widener, before the zero_take backstop; flag off returns take_n untouched); DRIVEN through the real loop: NULL flag off reproduces the 09-27 shape (two full bets of 5 inside one second), 1.0x refuses the second (gate full_cap, one order), 1.5x trims it 5 -> 2.5, 2.0x changes nothing, a 2-contract partial fill's next order is trimmed to the 3 missing (flag off asks 5: the leak), and a collapsing full position is hedged in full at 1.0x exactly as with the flag off. NULL against the UNPATCHED code: results/fullcap_null_2026-10-04.py runs both builds' own offline loop on 9 planted worlds (double bet live/paper, partial top-up, BTC 09-23 same ask, cheaper touch, late add, early leg, hedged collapse, two coins) -> 9 of 9 byte-identical with the flag off; positive control with the flag at 1.0: 3 of 9 differ (the three where a second same-side order exists). Startup path, from C:\kals-repo: `python C:\kals-live-0925b\research\pinrun.py <the full new argv, with --live and --max-full-bets 1.0> --selftest` -> SELF-TEST PASSED, 1,274 ok, 0 failed, exit 0 (C:\kals-live-0925b\restart_bot.ps1 is a copy of the new launcher, so the self-test read the argv that will run). `results\restart_bot.fullcap.ps1 -Check`: 67 flat strings, code file present, code_sha 269958db6d68. Start record gains `max_full_bets`. Read: READS_DUE 'fullcap-live' (due 2026-10-11T12:00Z).

**DEPLOY (the operator):** the bot must be flat (restart_bot refuses otherwise).
`Copy-Item C:\kals-repo\results\restart_bot.fullcap.ps1 C:\kals-repo\restart_bot.ps1 -Force`
`powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`
then confirm the new live start record says code_sha 269958db6d68 and max_full_bets 1.0, and run `python research/versioncheck.py`. Flag diff vs today's launcher: script `C:\kals-live-0925\research\pinrun.py` -> `C:\kals-live-0925b\research\pinrun.py`; hash guard f9548c5571ff -> 269958db6d68; ADDED `"--max-full-bets", "1.0"`; nothing else.

**REVERT:** `Copy-Item C:\kals-repo\results\restart_bot.before-fullcap.ps1 C:\kals-repo\restart_bot.ps1 -Force` then `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (flat first). That file is today's v-revert0925 launcher byte for byte (sha256[:12] 3e4ee6c4bce1): the plain 09-25 build from C:\kals-live-0925, code_sha f9548c5571ff.

---

# v-dipsell-live -- LIVE 2026-10-04 07:56:53Z (pid 3955508, subaccount 3 pool 0, $50) -- weather dip-seller live micro test, research/sweep/dipsell_live.py (git 900c5b8, file sha256[:12] a28305371e30), start record live true, subaccount 3, cash $50.00, start_pot $50.00. Operator: "Yes run the test" (10-03), "Yes move weather"; $50 moved main -> subaccount 3 in POOL 0 (exchange_index 0, where Kalshi's KXHIGH weather markets trade) at 2026-10-04 03:20:56Z. This entry written 2026-10-04 ~08:10Z, after the start (the start itself was the operator's, start_dipsell.ps1).

What it does (results/IDEA_SWEEP_2026-10-02.md row SJN1 "Dip Seller (weather)", IDEA_LEDGER U11/SJN1): when a daily-high temperature bracket (18 KXHIGH city series) has its hourly-candle mid fall 10c or more in one hour, with the new mid 15-85c, the hour trading 50+ contracts, both quotes 12c wide or less, and 6-12 h left to the close, it rests a post_only SELL YES (= buy NO) at the post-drop ask + 1c, 2 contracts, in subaccount 3, pool 0; unfilled remainder cancelled 3 h after the candle; fills held to settlement. Hard rails (code constants): one order a market ever, at most 5 open, day stop at -25% of the starting $50 pot (no new order that ET day, resting ones cancelled), KILL once 60 fills have settled with net < 0, stops placing at 100 fills or 14 days; refuses subaccounts 0/1/2 and any pool but 0. State is rebuilt from results/dipsell-live-orders.jsonl on restart (orders, fills, settlements, day stop, kill, done, first start time and pot), so a restart never re-orders a market.

PRE-REGISTERED BAR (READS_DUE 'dipsell-live', verbatim from the sweep): "2 contracts a trigger (then 10), max 5 open, 14 days or 100 fills; pass = fills on 50%+ of triggers, net over +4c a contract with the low end of the range above zero, no day worse than -25%; kill if negative after 60 fills." Read it: `python research/sweep/dipsell_live.py --report`. Evidence before the start: in-sample only ($3.20/day on a $100 account, 13 losing days in 40; the 6-12 h slice is post hoc), so the fortnight is the whole test.

Also 2026-10-04 ~08:10Z: boot_all.ps1's $cleanroom keep-alive list now restarts it (argv `-u research\sweep\dipsell_live.py --subaccount 3 --live --minutes 21600`, logs results\dipsell-live-stdout.log / -stderr.log) unless results\dipsell-live.stop exists (backup results/boot_all.before-dipsell.ps1); the phone shows it as /weather (/wx) and in /bots (research/botstats.py: subaccount 3, cash read from pool 0).

**REVERT:** create the stop file -- `New-Item -ItemType File C:\kals-repo\results\dipsell-live.stop` -- the bot cancels every resting order and exits at its next check (within a minute), and boot_all.ps1 will not restart it while the file exists. Holdings settle on their own. To return the cash to the main account afterwards: `python research/ordercli.py --sub 3 --sub-return <dollars> --sub-pool 0` (dry run + token like every ordercli write; a money move -- ask the operator first).

---

# v-revert0925 -- LIVE 2026-10-04T03:22:52Z (pid 3506784, start record code_sha f9548c5571ff, mode live, early_min_price 0.9, price_ceiling 0.98, early_max_price 1.0, no toxic_fresh, no one_full_bet; autosize 87 contracts on bank $1,025.69; replaced pid 4031340, which was flat -- last bet KXBTC15M-26OCT032315-15 settled +$1.56). PREPARED 2026-10-04T03:17Z (operator: "Revert to 9/25.") -- NOT LIVE until the main bot restarts (`powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`; a watch_bot keep-alive relaunch would also pick it up). The live main bot runs THE 09-25 BUILD: research/pinrun.py at git 2fce1837e6 (v-scalein-caps), code_sha f9548c5571ff, materialised with its research imports at that commit (engine, livebook, pintake, kauth, ordercli, downtime, pinflat) under C:\kals-live-0925\research, on the 09-25 argv with one change, `--early-min-price 0.95 -> 0.90` (operator on the 45-second floor: "do whatever makes the most money"). SUPERSEDES v-floor95 (prepared, never deployed).

**PRE-REGISTERED RULES THIS OVERRIDES, said loudly (operator's order 10-04 ~03:15Z, "Revert now"):** (1) v-reopen98's stop said 98c goes back to 0.978 "if --toxic-fresh is turned off" -- this revert turns the seller check off and runs 0.98 on both legs (the 9/25 build's own behaviour). (2) v-floor90's stop tripped at the 10-03 read (-$61.63); the floor stays 0.90 on the operator's "do whatever is best for the 45": the only loss under it (NEAR 10-03) would have happened at 0.95 too (the 30-s full leg buys the whole bet; read from the log, results of 10-03 floor-95 check), and 1 loss in 28 of our 90-95c 45-s fills is under the ~6-9 in 100 break-even. Without the seller check the 9/19 BTC shape (-$66, 59-ms-old 90-95c offer) is open again -- watch it in the daily read.

Flag diff against restart_bot.ps1 as it stood before this entry (results/restart_bot.before-revert0925.ps1): script `C:\kals-repo\research\pinrun.py` -> `C:\kals-live-0925\research\pinrun.py`; `--early-min-price` 0.95 -> 0.90 (0.90 is what the running pid 4031340 already has; v-floor95 never ran); REMOVED `--early-max-price 0.978` (the 09-25 code's default is 1.0: no 45-second cap); REMOVED `--toxic-fresh` (seller check off); REMOVED `--one-full-bet` (the flag does not exist in the 09-25 code); REMOVED `--price-ceiling 0.98` (no value change: 0.98 is the 09-25 code's default, start record 09-25 price_ceiling 0.98). Unchanged, as 09-25 had them: `--max-losses 2 --loss-abort -60.00 --bank-brake 4.00 --loss-cap 200 --minutes 4320`, and every other flag. Working directory stays C:\kals-repo; the 09-25 code hard-codes RESULTS = C:\kals-repo\results, so the log (results/pinrun-live-*.jsonl), pid file, pinrun-hwm.json / pinrun-hwm.reset, pinrun-dayloss.json and pinrun-live-size.json are the same files, and the halt texts watch_bot.ps1 reads ("loss COUNT brake", "loss abort", "DRAWDOWN brake", "DAY loss cap") are the same strings. Neither version reads results/pinrun-live.stop itself; watch_bot.ps1 and the desktop app act on it, and they match the bot by `pinrun` + `--live`, path-free.

What the live bot LOSES (every behaviour change in research/pinrun.py after 2fce1837e6, plus the launcher flags added after 09-25):
- one full bet per market (v-onefull, 09-27, code 5199cd2): a market already holding a full bet may again take a second full bet in the same second. Protected against: the two worst markets on record were same-second double bets, BTC 09-23 -$130 and BTC 09-27 -$131.98; worst single market ~$193 (two bets) instead of ~$95. Measured on our fills: +$107 over 19 days (week 1 -$13, week 2 +$120); cost of the rule ~$1.50-2/day of winning double bets.
- top-up completes to one bet, no further (v-topup, 09-30, 0ea3dcd): only acted under --one-full-bet. Protected against a small first fill plus a full-size second leg holding 1.2-1.6 bets on one coin (SOL 09-19 174 vs 107 contracts). No money figure.
- seller check (v-toxic-live, 09-27, flag only): entries with > 20 s left are no longer refused when the offer is < 500 ms old AND takers sold > half of the last 3 s. Protected against: the 09-27 04:00Z BTC -$131.98 (both legs in that cell). Measured 7 days: gave up <= $79 of winners (55 markets), saved 3 losers $58 -- too few to tell (WHAT_WORKED_2026-10-03).
- 97.8c cap on the 45-second bet (v-ceiling978 09-27 / kept by v-reopen98 09-28, flag only): the 45-second bet may buy at 97.9-98c again. Protected against: the 45-second part of the 98c band held BTC 9/19 -$108 and HYPE 9/21 -$54. Measured 7 days: gave up <= $47 (88 markets), saved 1 loser $29 -- too few to tell. NOTE: v-reopen98's own pre-registered stop said 98c buys should go back to capped "the moment --toxic-fresh is turned off"; this revert turns it off and reopens 98c on BOTH legs, on the operator's instruction.
- 90c floor without the seller check: v-floor90's case (09-28) counted the BTC 9/19 -$66.34 90-95c loss as refused by the seller gate; under this revert that gate is off.
- whole-cent limits on the hourly BTC ladder (v-cent, 09-29, 8f7bd0c): at a 0.98 ceiling every KXBTCD entry limit is already a whole cent (27 of 27 such orders accepted on record), so only a KXBTCD hedge that reaches the 99.9c cap would be rejected (invalid_price). 1 contract, ~$1.
- bank-move confirmation (v-bankmove, 10-03, f81257e): an unexplained bank move is again called a deposit/withdrawal and shifts the 20% high-water mark. Protected against: 4 misreads on 10-01 (a -$84.62 delayed payout read as a withdrawal: mark reset to $980.80, bet 87 -> 80 for ~1h45m; coin race stakes read as transfers); a real loss read as a withdrawal blinds the drawdown halt by that amount. The coin race now bets 20 a leg on the same account, so its stakes move the bank more often than on 09-25 (5 a leg then).
- `--early-price-free-tries` (10-02, 17bcde8): never on live, so nothing is lost live. Under the 09-25 code an `early_cheap` refusal (an ask under 90c at 31-45 s) still uses one of a coin's 3 tries (the F20 lockout); with no 97.8c cap there is no `early_dear`, so 98c no longer locks a coin out.
- ordercli changes after 2fce (reward / pools / subaccount CLI) are additive; pinrun calls only send / cancel / load_key, unchanged.

Evidence: results/PAPERS_1002_1003.md revert block -- 254 shared closes 2026-09-29T19:00Z..10-02T12:15Z, 15-minute markets: the 09-25 build (paper) +$200.08 on $6,574 bet (+3.04%), current rules (twin, paper) +$164.32 on $5,609 (+2.93%), LIVE +$114.83 on $4,357 (+2.64%); the $36 gap is inside the $18-40 two identical paper copies drift apart, so the money case is NOT proven -- it buys ~40 more markets at the same return per dollar. Kalshi by ET week: 09-20..26 +$373.82 (the 09-25 build ran live only from 09-25 12:24Z of that week; the rest was earlier code), 09-27..10-03 -$1.44 on the newer rules. Nothing has measured the 09-25 build against the twin since 10-02 12:26Z except arm-0925b (pid 4260672, from 10-04 00:36Z).

Startup path: `python C:\kals-live-0925\research\pinrun.py <the full new argv, with --live> --selftest` from C:\kals-repo -> SELF-TEST PASSED, 1,262 checks ok, 0 failed, exit 0 (C:\kals-live-0925\restart_bot.ps1 is a copy of the new launcher, so the self-test read the argv that will run). `restart_bot.ps1 -Check` (new switch: validates and exits before pinflat, before any stop): 65 flat strings, code file present, code_sha f9548c5571ff. restart_bot.ps1 now ABORTS before stopping anything if C:\kals-live-0925\research\pinrun.py is missing or its sha256[:12] is not f9548c5571ff. Read: READS_DUE 'revert0925-live' (due 2026-10-06T12:00Z). At deploy also update READS_DUE reopen98-guard / floor90-guard / bankmove-live / pinrun-exit-1006 (each assumes the newer code or flags) and do NOT run sync_arms.ps1 without thought: it rebuilds every synced arm from the live command line, so the arms would lose --toxic-fresh / --one-full-bet / --early-max-price from their base (arm-toxic15/toxic0 then measure nothing) while still running today's code.

**REVERT:** `Copy-Item C:\kals-repo\results\restart_bot.before-revert0925.ps1 C:\kals-repo\restart_bot.ps1 -Force` then `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (the bot must be flat; restart_bot refuses otherwise). That file is the pre-revert launcher: today's code from C:\kals-repo\research\pinrun.py with --toxic-fresh, --price-ceiling 0.98, --one-full-bet, --early-max-price 0.978 and `--early-min-price 0.95` (the prepared v-floor95 value); to come back at the 0.90 the bot ran on 10-03, change that one value to "0.90" in the copied file before the restart.

---

# v-floor95 -- PREPARED 2026-10-03 12:15Z (restart_bot.ps1 edited and committed; NOT LIVE until the main bot restarts -- the session's permission checker refused the deploy step, operator asked to say "restart the main bot"; a keep-alive relaunch would also pick it up) -- the 45-second bet's price floor back from 90c to 95c (`"--early-min-price", "0.95"`), the v-floor90 PRE-REGISTERED STOP having tripped at the 10-03 08:00 ET read.

The bar (VERSIONS v-floor90, 09-28): "add up the money of every 45-second buy whose ask was under 95c since this switch, insurance included, from the Kalshi ledger; if it goes below $0, back to 0.95 at once." The read: 11 markets since 09-28 14:36Z, 10 won (+$1.46..+$4.22 each, +$25.32 together), 1 lost -- KXNEAR15M-26OCT030645-45, 2026-10-03 10:44Z: 45-s leg saw 93.8c, filled 31.3 at 96.46c at 37 s; top-up 62.7 at 97.47c at 30 s; both insured at ~94.9c at 12 s; Kalshi net -$86.95 (7.9% of the ~$1,100 main account). Running total **-$61.63 < $0 -> revert.** For scale: 45-s buys at 95c and up since 09-28: 46 markets, +$8.87, 2 losses (BNB 09-28 -$8.26; BTC 10-03 04:00 ET false-alarm insurance -$13.01). What 0.95 gives up: the 10 winners' ~$2.50 each, ~$0.5-1/day; what it refuses: the 93.8c-shape entry. Whether the 30-s top-up would still have bought NEAR at 96.9c cannot be read from the log, so this does not claim the NEAR loss would have been avoided in full.

Deploy: `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (stops pid 4031340, relaunches with the file's argv). Startup path self-test with the new argv: NOT RUN (the checker refused the command); no code changed, and 0.95 was the live value 09-23..09-28. READS_DUE 'floor90-guard' stays daily with the new meaning: confirm the live start record carries early_min_price 0.95; the under-95c total is frozen at -$61.63.

**REVERT:** in `restart_bot.ps1` set `"--early-min-price", "0.90"` and run the restart line above (only with a new pre-registered bar; the 09-28 one is spent).

---

# v-ladder-limbo + v-ladder-caps -- LIVE 2026-10-03 07:47:33Z (ladder pid 3832268, was 3080724; pot $71.01 -> size 5; start record carries market_cap_x 2.0, close_cap_x 0). Code SHA ef85845 (prepared ~06:25Z; the first restart attempt was refused by the session's permission checker, operator 07:47Z: "Restart the ladder", run via restart_ladder_1003.ps1, log results/restart_ladder_1003.log). The limbo fix is always on in the code; the cap rides on the boot_all.ps1 line (backup results/boot_all.before-laddercaps.ps1).

What the ladder does differently: (1) v-ladder-limbo -- a bid whose cancel fails (Kalshi 404 = it had already filled) keeps its unfilled remainder counted in the contract/money rails, the new per-market cap and flat() (the auto-size gate) until the fill poller sees the order finished (executed/canceled) or 60 s pass. Before, such a bid counted as neither resting nor held for 0.4-2.8 s -- exactly when NEAR's 1-s bursts of re-bids land -- so the 50-contract rail fired late (all 24 of its refusals since 09-30 came after the poller caught up) and auto-size could resize mid-fill. (2) v-ladder-caps -- `--market-cap-x 2`: at most 2 bids' worth (10 contracts at size 5; scales with the auto-size) resting + held in one market. `--close-cap-x` exists, default off, and is NOT used.

Math (our own live fills, subaccount 1, 09-30 12:26Z..10-03 06:15Z, Kalshi /portfolio/settlements): 40 markets, 0 lost, +$5.58 = +2.07% on $269 bet. The 2x market cap (counting the limbo fills, i.e. with fix 1) refuses 9 bids in 7 closes, removes 30 contracts in 4 NEAR closes, gives up $0.61 (about $0.20/day, 11% of the ladder's money), saves $0 (no losers in the window), and halves the most riding on one market from $19.59 (28% of the pot) to $9.80 (14%). Break-even: it pays if more than about 1.6 in 100 of the capped markets lose; the main bot's live loss rate at these prices has been 2-3 in 100. Without fix 1 the cap would never have fired (0 refusals). The 25-a-quarter-hour cap was REJECTED: it counts resting bids, so it refuses 1,103 bids in every close and gives up $4.98 of $5.58 for $0 saved.

Self-test PASSED (`python research/cleanroom/ladder_live.py --selftest`, and with the full new argv + --selftest): caps off places exactly as before (7 of 7); 2x market / 5x close / 3x close cap counts; 5 held + 2nd bid of 5 allowed, 3rd refused why=market_cap; the 10-03 shape (fill, cancel 404, poller not caught up) keeps 5 counted, not flat, and the cap sees it; the poller's fill zeroes the remainder (no double count); a terminal order or 60 s releases limbo. NULL: with limbo() disabled the test FAILS on three checks.

**REVERT:** boot_all.ps1 ladder line back to `a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", "--minutes", "10080");` (backup results/boot_all.before-laddercaps.ps1), then the stop-file restart (results/ladder-live.stop -> wait for exit -> delete -> start the old argv). The limbo fix reverts with `git checkout <previous SHA> -- research/cleanroom/ladder_live.py` before that restart.

---

# v-race20cap -- LIVE 2026-10-03 06:16Z (coin race pid 3095608; was pid 1431208 at 40 a leg / $120) -- coin race back to 20 contracts a leg and $40 open at once (--max-contracts 20 --max-stake 40; the $40 open cap is the per-race cap in practice, since races do not overlap). Also brings v-race-daystate live (the 2-losses-a-day count survives restarts). Operator 10-03: "Apply any improvements you thought of or found."

Math (results/RACE_WHY_2026-10-02.md, race40 read 10-02): at 40 a leg it filled 39 of 100 contracts asked (46.5 at 20), made $3.49/day vs $4.34/day at 20, and a full lost leg costs $37-39 (about 11 days of its income) vs about $19 at 20; the 10-01 7:14 PM ET race put $73.20 on one 0.45-bp photo finish to win $6.36. Capping the 40-period fills at 20 would have made $2.53 instead of $6.08 over 1.97 days (~$1.80/day less) for half the worst case.

**REVERT:** boot_all.ps1 line ~484 back to "--max-contracts", "40", "--max-stake", "120" (backup results/boot_all.before-race20.ps1), stop the race pid, start the old argv.

---

# v-bankmove -- LIVE 2026-10-03 08:15:52Z (main bot pid 4031340, start record xfer_confirm: true, code_sha 9afb6eca6a91), EARLIER THAN PLANNED: the 09-30 run (pid 4447780) halted on the loss COUNT brake at 08:00:35Z (2 losing trades this run; the 2nd was the BTC 04:00 ET false-alarm hedge leg, -$14.10) and watch_bot.ps1 relaunched it after its 15-min cooldown via restart_bot.ps1, unchanged argv. Written 2026-10-03 (IDEA_LEDGER F21), research/pinrun.py. Was: GOES LIVE WITHOUT A DEPLOY STEP: the live main bot (pid 4447780, started 2026-09-30 12:12:06Z with --minutes 4320) ends its run at ~2026-10-03 12:12Z and the keep-alive (watch_bot.ps1 -> restart_bot.ps1) relaunches it on whatever research/pinrun.py is on disk, which from this commit is this version. Confirm with the new live start record: it now carries `xfer_confirm: true`.

What the bot does differently: a bank change that `realised` does not explain is no longer called a deposit or withdrawal on its own. Before the high-water mark moves, the move is checked against Kalshi's own records -- GET /portfolio/deposits, /portfolio/withdrawals and /portfolio/subaccounts/transfers (the listings research/pinxfer.py and botstats.py already read) -- for a FINISHED transfer of that amount (within the $1.00 noise floor), stamped between an hour before the previous bank read and five minutes after now, not already used to explain an earlier move. Match -> `external` record exactly as before (mark shifted by the amount) plus the transfer id(s) it matched. No match, or any of the three reads failing -> a NEW record kind `unexplained` (move, amount, bank, hwm, why), the mark is NOT shifted, and the move counts as trading: a fall counts against the 20% drawdown halt, a rise raises the mark the ordinary way (a new bank high). A failed read is never a withdrawal. Listings are cached 60 s; an unmatched move forces one fresh read before it is called unexplained. Each read is a signed GET on a daemon thread capped at 4 s, and the whole check runs only when the bot is FLAT (as the classifier always did). `--no-external-detect` still switches all of it off (nothing read, nothing written). No money or size change: bet size is still derived from the bank and the mark; what changes is that the mark can no longer be lowered by a misread.

Evidence = the four misreads in results/pinrun-live-20260930T121206Z.jsonl (`external` records): 10-01 01:00:35Z the coin race's -$1.14 LOSS read as a withdrawal (mark -$1.14); 07:15:21Z a payout delayed by the exchange read as a -$84.62 withdrawal (mark reset to $980.80, bet 87 -> 80 for ~1h45m); 09:00:22Z that payout landing read as a +$87.00 deposit; 23:18:26Z the race's +$6.36 payout read as a deposit (mark moved). Kalshi's listings show no transfer at any of the four times (results/kalshi_transfers.json: 7 deposits, 0 withdrawals, last fetched 10-01 06:55Z). The danger is the first shape: a real loss subtracted from the mark blinds the 20% halt. Self-tests PASSED (planted, driven through autosize_tick end to end with a faked listing): drop + matching withdrawal -> `external`, mark shifted, zero drawdown, transfer id in the record; the SAME drop with no transfer -> `unexplained`, mark untouched, 33% drawdown counted; rise + deposit (net of fee) -> `external`; rise with no deposit -> `unexplained`, mark follows the bank as a new high; pending deposit confirms nothing; a transfer outside the window confirms nothing; a 500 and a raising getter -> `unexplained` with 'read failed', never a withdrawal; a subaccount transfer out of the main account confirms a drop, one into it cannot; NULL: `--no-external-detect` reads nothing and writes nothing; the pure helpers (transfer_rows on the real 09-19 $378/$7.56 record = $370.44, match_transfer window/used-id/sum, fetch_transfers cache 60 s); source check: autosize_tick shifts the mark in ONE place, after confirm_move, only when it returned no reason. `python research/pinrun.py --selftest` PASSED; the startup path with the full restart_bot.ps1 argv plus `--selftest` PASSED (exit 0, 1307 checks); `python research/versioncheck.py` clean (no new flag). READS_DUE `bankmove-live` (2026-10-05 12:00Z).

Known limits: a true deposit/withdrawal that Kalshi has not yet listed when the bank moves reads `unexplained` once (a withdrawal then counts as drawdown until the operator says so -- the brake still has 20% of room, and the record names the amount; Kalshi has never listed a withdrawal on this account -- results/kalshi_transfers.json holds 0 -- so which `status` a just-requested withdrawal carries is unmeasured, and one that sits outside pinxfer.DONE while the balance is already debited reads `unexplained` until it finishes); an exchange-delayed payout (10-01 07:15Z, -$84.62) now counts as a drawdown until it lands instead of lowering the mark -- 10.9% for ~1h45m that day, no halt; a 20% DRAWDOWN halt is a `hold` in watch_bot.ps1 (no auto-restart, needs the operator's START), so two such delays stacked on one bank would stop the bot until he looks; the main account is subaccount "0" in the transfers listing (XFER_MAIN_SUB); pindesk reads `external` records and does not yet show `unexplained` ones (they are in the log).

**REVERT:** `git revert <this commit's SHA>` then `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1` (the bot must be flat; restart_bot refuses otherwise). That puts back the unconfirmed classifier (every unexplained move shifts the mark again).

---

# v-race-daystate -- PREPARED 2026-10-03 (IDEA_LEDGER F29), research/pinracearm.py, NOT YET LIVE: takes effect at the live coin race's next restart (the running race, pid 1431208 since 2026-10-01 07:42:04Z with --minutes 10080 -- corrected 2026-10-03 by the verifier, the entry first named pid 4454164 / 09-30 12:25Z, which no longer exists -- keeps the old in-memory counter until then; nothing restarts it by itself -- READS_DUE `coinrace-relaunch`). SHA = the commit that carries this entry.

What changes: the live race's daily loss counter (`day_losses`, `loss_day`, `halted`, `halted_day` -- the v-race40 "stop for the day after 2 losing races") lived only in memory, so any restart forgot the day's losses and the 2-a-day stop could be beaten by restarting. Now every change is written to results/pinracepenny-daystate.json (tmp + replace), and a `--live` start reads it back: a record from TODAY (ET) restores the count AND the halt (record `daystate_restored`, printed "STILL STOPPED FOR THE DAY"), so a halted day stays halted through a restart; a record from another day is ignored (`daystate_ignored`, what=stale) -- the limit still resets at the ET day turn; a corrupt or unreadable file is ignored with the reason in the record. Paper arms and the self-test never write the file (the writer runs only when `daystate_path` is set, and only `--live` sets it). No money or size change.

Self-tests PASSED (planted): today's file with 2 losses + halt -> restored, every order refused for the rest of the day, still expires at the ET day turn; today's file with 1 loss -> count restored, nothing refused (the next loss halts); yesterday's file -> stale, ignored, nothing refused; corrupt JSON and a junk `halted` -> ignored with the reason; missing -> missing; end to end through settle_pass: first losing race writes {day, 1, no halt}, second writes the halt and its day, a restart the same ET day reads both back, the next ET day it is stale; NULL: a state with no daystate_path writes nothing; wiring: main sets the path and restores under --live after rec() exists and before the loop, settle_pass saves after the day reset, after each counted loss and after the first-loss halt. `python research/pinracearm.py --selftest` PASSED.

**REVERT:** `git revert <this commit's SHA>`, then stop the live race (`type nul > results\pinracepenny.stop`, wait for its exit, delete the stop file) and relaunch it with the v-race40 argv from this file; or simply delete results/pinracepenny-daystate.json before a relaunch to start that day's count at zero (the code stays).

---

# v-fc-r28 -- LIVE 2026-10-03 06:12:13Z (forecaster pid 3090252, scale_sub_1002.ps1 run on the operator's "You run the switch") -- forecaster variant race1_98 -> race1_98_r28: no forecaster buy in the first 2 s of its 30-s window (r_max 30 -> 28). Operator 10-02: "Apply whatever you know works now. Tell me how many losses it saves and winners it loses."

Evidence (our own live fills, 71 fills / 54 settled markets 09-29..10-02): fills with 30+ s left = 6 losing fills in 5 markets ($23.10) and 9 winning fills ($3.58); skipping them nets +$19.52 over the live record. r_max 25 would save $33.28 but give up $12.64 of 26 winning fills (+$20.64): r28 keeps nearly all the gain for a third of the winners lost. Chosen after seeing the losses (14 first entries, 5 lost) -- the paper side-by-side fcvar-paper-early (READS_DUE fc-early-skip, read 10-06) is the check; revert if it fails.

**REVERT:** in boot_all.ps1 section 3e and the running argv, --variant race1_98_r28 -> --variant race1_98, then restart the forecaster (stop file results/forecaster-live.stop, wait for exit, delete it, start the old argv).

---

# v-sub-autosize -- LIVE 2026-10-03 06:12:13-16Z (forecaster pid 3090252 pot $55.93 scale 0.0888; ladder pid 3080724 pot $70.91 size 5; the script's 25-s record check missed the start records, which landed 06:12:18Z and 06:12:24Z -- confirmed by hand) (research/cleanroom/forecaster_live.py `--auto-scale`, research/cleanroom/ladder_live.py `--auto-size`; the one-shot switch is scale_sub_1002.ps1, its -DryRun PASSED 06:51Z): each side-account bot sizes from its OWN pot like the main bot, with NO start-balance cap. Nothing changes until the operator runs the script.

Operator 2026-10-02: "Set no limits on the sub accounts. I don't think you understand the goal, I want each account
running just like the main pin. High total making 2-10% per day of its total."

What the script does (`powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/scale_sub_1002.ps1`; -DryRun = checks only):
validates (both self-tests, no stop files, one live forecaster + one live ladder, main bot and coin race present and
untouched, boot_all.ps1 holds the old argv lines, both pots >= $10), points the keep-alive at the new argv (backup
results/boot_all.before-autosize.ps1), then per bot: stop file -> exit -> delete -> start -> 25 s -> checks the new
start record carries the flag and the size its pot implies.
- **Forecaster (subaccount 2)**: `--scale 0.10` -> `--auto-scale`. scale = pot / 630 (pot = cash + the cost of what it
  holds; $63 -> 0.10 = today's size, $126 -> 0.20, clamped 0.02..1.0 = the paper's own size), read at start and every
  60 s, applied ONLY when nothing is held or in flight ('rescale' record on each change, 'rescale_wait' once when
  deferred). Stops: day -20% of the pot at the day's first rescale, run -33% of the pot at start, held + in flight
  <= 70% of the pot; per side / per close / per order stay 100 / 400 / 100 x scale. At the dry-run pot of $59.05:
  scale 0.0937 -> 9 a side, 37 a close, $41.34 held, day stop -$11.81, run stop -$19.49 (today: 10 / 40 / $44 / -$24
  / -$40 -- the stops get TIGHTER and the size a hair smaller until the pot passes $63). A hedge (the paper's hedge_p
  insurance; no live variant has it) is now exempt from every size/money cap and the crash guard (09-19 rule: a gate
  must never block a hedge) -- before this it was capped like any order; a plain opposite-side bet is capped as before.
  `--variant race1_98 --crash-gap 0.10` unchanged.
- **Ladder (subaccount 1)**: `--size 5` -> `--auto-size`. size = floor(pot / 14) ($70 -> 5 = today's, $140 -> 10,
  clamped 1..100), the same 60-s re-read, applied only when nothing is held and no bid rests or is being cancelled.
  Day stop -20% of the day's first pot; resting + held <= 70% of the pot; contracts <= 10 x size. At the dry-run pot
  of $70.21: 5 a bid, 50 contracts, $49.14 committed, day stop -$14.04 (today: 5 / 50 / $60 / -$30).
- **Both**: NO upper start cap in the new mode (the fixed --scale / --size modes keep theirs: $70 / $73 today);
  refuse under a $10 pot; the primary account still refused; the pot's unit is read from both `balance` (cents) and
  `balance_dollars` and they must agree (hard rule 5); an unreadable pot changes nothing (logged `pot_unreadable`).
  The `--scale` ceiling 0.25 -> 1.0 and `--size` ceiling 20 -> 100, rails still derived from the value.

Evidence: THE OPERATOR'S ORDER ONLY. No paper or live test of pot-driven sizing on these bots exists; the rule is the
main bot's shape (bank-proportional, read when flat), not a measured optimum; 630 and 14 are chosen so today's pots
reproduce today's sizes. Self-tests PASSED (both; planted): scale/size at $63/$126/$630 and $70/$140/$13, the clamps,
rails move with the scale/size, NO rescale while held / in flight / resting / cancelling then applied once flat, the
day stop moves only at the day's first rescale and the run stop never, stops = the stated % of the pot, NULL
(`--scale 0.10` / `--size 5` reproduce today's rails exactly and the old start caps still apply), the hedge path sent
with every cap full and the crash guard on, the pot reader's unit check. Startup path run with each flag in
`--dry-run` 06:51-06:53Z (start records in the order logs, pid 4512916 / 4517292, nothing sent). READS_DUE
`sub-autosize` (2026-10-04 12:00Z; stop-and-revert rule: either bot's day stop twice in the first 3 days).

Verifier 2026-10-02 ~07:10Z: both self-tests re-run PASSED; diffs read; -DryRun re-run PASSED 07:06Z (pots $70.21 /
$59.05, same pids). One fix to the script: before each stop file is removed it now waits (<= 60 s) while boot_all.ps1
is mid-run -- KalsBoot runs it every 10 min and it snapshots the process list once at its start, so a run straddling
the switch could have started a second copy. Known, NOT changed (dormant: race1_98 has no hedge_p): a live hedge
under 75c would still be refused by the 75c price floor in both want() and body_ok(), and by the stop/halt states;
the ladder's day stop halts until restart (pre-existing, `halted` is never reset); the run stop is -33% of the START
pot, not the main bot's 20%-from-high; ordercli's --sub-fund still caps a subaccount at $100 (a funding rail, not a
bot rail).

**REVERT (once the script has run):** `Copy-Item C:\kals-repo\results\boot_all.before-autosize.ps1 C:\kals-repo\boot_all.ps1` then, per bot, `New-Item C:\kals-repo\results\<forecaster|ladder>-live.stop`, wait for the process to exit, `Remove-Item` the stop file, and start the OLD argv:
`Start-Process C:\Python314\python.exe -ArgumentList @("-u","research\cleanroom\forecaster_live.py","--subaccount","2","--live","--variant","race1_98","--scale","0.10","--crash-gap","0.10","--minutes","10080") -WorkingDirectory C:\kals-repo -WindowStyle Hidden -RedirectStandardOutput C:\kals-repo\results\forecaster-live-stdout.log -RedirectStandardError C:\kals-repo\results\forecaster-live-stderr.log`
`Start-Process C:\Python314\python.exe -ArgumentList @("-u","research\cleanroom\ladder_live.py","--subaccount","1","--live","--size","5","--minutes","10080") -WorkingDirectory C:\kals-repo -WindowStyle Hidden -RedirectStandardOutput C:\kals-repo\results\ladder-live-stdout.log -RedirectStandardError C:\kals-repo\results\ladder-live-stderr.log`
(the fixed modes' start caps are $70 / $73: if a pot has grown past them, use a bigger `--scale` / `--size` or the old start rail refuses). Code only: `git checkout 17bcde8 -- research/cleanroom/forecaster_live.py research/cleanroom/ladder_live.py`.

---

# v-lockfix-code -- 2026-10-02 06:03Z -- CODE ON DISK, FLAG OFF (F20; research/pinrun.py `--early-price-free-tries`, on-disk code_sha bc5a3f43e2c5, base commit 0ea3dcd): with the flag ON, an early-leg refusal for PRICE (early_cheap / early_dear) gives back the try it was charged (both counters), so a coin at 97.9-98c at 31-45 s is no longer locked out (market_attempts) of the <= 30 s window. The live command line is unchanged, so the live bot does nothing new; its self-restart ~2026-10-03 12:12Z merely loads this code.

Evidence: pinrun self-test 1287 ok / 0 FAIL plain, under the live argv, and under the live argv plus the flag
(re-run by the verifier 2026-10-02 ~06:20Z). The self-test reproduces the 10-01 lockout with the flag off, buys
one 98c order at 25 s with it on, and shows toxic_fresh (the seller gate) still spending tries. Paper: arm-lockfix
pid 4039624, READS_DUE lockfix-paper (read 2026-10-06 12:00Z). Turning it on live needs that read's GO and its
own entry (`v-lockfix`).

**REVERT (code only; valid while no later commit touches pinrun.py):** `git checkout 0ea3dcd -- research/pinrun.py` -- then, only if live has already restarted onto this code, `powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`.

---

# v-topup -- LIVE 2026-09-30 12:12:02Z (pid 4447780, code_sha b34346497c63, restart_bot.ps1; research/pinrun.py _stage46) -- under --one-full-bet a second full-leg order on the side already held is a TOP-UP: it completes the position to SIZE x the band / doubt / late multiple (the same target an early-leg top-up gets) and no further. It never caps a re-buy into the OTHER side (a hedge).

Why (READS_DUE 'topup-leak'): a small first fill followed by a full-size top-up held 1.2-1.6 bets on one coin
(SOL 09-19 174 vs 107). Driven self-test through the real loop: 2 contracts held -> the top-up asks 3 (flag on)
vs 5 (flag off: the leak); flag off unchanged; the cap sits in _stage46, which live and paper both call. Full
pinrun self-test PASSED. Also loaded by this restart: v-cent (hourly-ladder whole-cent limits).

**REVERT:** `git revert 0ea3dcd` (and 2bd... for v-cent if wanted), then restart per do-the-restart-yourself.

---

# v-race40 + v-forecaster-scale + v-ladder-size + v-crash-guard -- LIVE 2026-09-30 12:25:53-12:25:59Z via scale_up_0930.ps1 (operator: "Go"). Coin race pid 4454164 (pintake rails raised: 40 per take, $120 run stake -- printed in pinracepenny-live.out), forecaster pid 4453188 (--scale 0.10 --crash-gap 0.10), ladder pid 4454364 (--size 5; its start record said "size": 1 -- a literal in the log line, fixed in code 12:3xZ; first bids were 5.00). Keep-alive updated (backup results/boot_all.before-scale-up.ps1). Prepared 2026-09-30 ~05:5xZ. Operator 2026-09-30: "Run whatever sub accounts you want or look like money makers like hourly ladder, increase the coin race size don't stop on one loss, increase clean room forecaster, increase ladder."

The relaunches were refused by the permission check ("Production Deploy") even with that instruction, so all
three are applied by ONE script the operator runs (or allow-lists): `powershell -NoProfile -ExecutionPolicy Bypass
-File C:/kals-repo/scale_up_0930.ps1` (-DryRun checks only; the dry run PASSED 05:50Z). It validates first (self-
tests, no stop files, one live process each, balances inside the new rails), points boot_all.ps1's keep-alive at
the new argv (and adds the live coin race to it), then restarts:
- **v-race40** (research/pinracearm.py, code): --max-contracts 20 -> 40, --max-stake 60 -> 120 (pintake's per-take
  and run-stake rails raised through pintake.set_limits, printed; this file's own ceilings 100 contracts / $300), and
  NEW --live-max-losses 2: stop for the rest of the ET day after 2 losing races (was: stop for good on the first
  loss). Self-test: the daily limit end to end through the real settle path. Record: 204 legs, +$19.20; 78 legs
  without a loss since 09-24; at 20 a leg 46 in 100 contracts filled (supply-bound), so expect +$1-2 a day more;
  a loss costs ~$39 instead of ~$19.6.
- **v-forecaster-scale** (research/cleanroom/forecaster_live.py, code): NEW --scale (default 0.05 unchanged); the
  script runs 0.10 = 1/10 of paper, every rail doubled with it (10 a side, 40 a close, $44 held, -$24 day, -$40 run,
  start balance <= $70). Subaccount 2 funded $26.35 -> $54.35 (ordercli --sub-fund 28 --sub 2).
- **v-ladder-size** (research/cleanroom/ladder_live.py, code): NEW --size (default 1 unchanged); the script runs 5
  contracts a bid, rails x5 (50 contracts, $60 held, -$30 day, start balance <= $73); exposure now counts contracts,
  not orders. Subaccount 1 funded $15.15 -> $65.15 (--sub-fund 50 --sub 1).
- ordercli SUB_MAX_BALANCE $25 -> $100 (the transfer rail), its self-test updated.
- **v-crash-guard** (forecaster_live.py, code, NEW --crash-gap, run by the script at 0.10): skip an order when
  the engine's best ask at the trigger is already more than 10c under the price about to be paid; every order now
  logs best_ask_at_trigger. Why: live 09-29..30, 5 fills landed >10c under the asked price (the offer collapsing
  as we sent): 3 lost, -$3.05; the 17 ordinary fills: 0 lost, +$7.94. Whether the collapse is already visible at
  the trigger is unknown -- the new log field answers it; refusals show as why=crash.
UNTIL THE SCRIPT RUNS: the running bots keep their old sizes; if one of the two penny bots crashes, the keep-alive's
OLD argv now fails its start rail (balances are above $25/$35), so it stays down -- a safe failure.

**REVERT:** resultsoot_all.before-scale-up.ps1 -> boot_all.ps1; restart each bot with its previous argv (coin
race: the v-race20 line; forecaster: v-forecaster-race1 RELAUNCH; ladder: v-ladder-penny RELAUNCH); move money back
with ordercli --sub-return.

---

# v-ladder-settlefix -- LIVE 2026-09-29 17:16:12Z (pid 4217364; research/cleanroom/ladder_live.py): the penny ladder no longer books a market whose settlement lookup came back EMPTY (not yet determined) -- it waits for yes/no, as the paper engine does.

Why: 17:15:04Z it booked KXNEAR15M-26SEP291315-15 (1 NO at 97.9c) as -$0.979 on result "" and dropped the holding;
Kalshi finalized the market NO -- a +$0.021 WIN (subaccount 1 balance 15.063 = 15 + 0.042 + 0.021 confirms). Real
money was never affected; the process's day-loss counter was ($0.98 too low), which could have fired the -$6 day
stop falsely. That one wrong live_settle row stays in ladder-live-orders.jsonl; Kalshi's settlements are the money.
Self-test gains "an empty (unsettled) result books nothing and keeps the holding"; PASSED. Stopped by stop file
17:15:49Z, relaunched 17:16:12Z (boot_all.ps1 argv unchanged).

**REVERT:** `git revert` this commit and restart the ladder (stop file, delete it, boot_all.ps1 or the RELAUNCH line).

---

# v-keepalive-cleanroom -- 2026-09-29 15:37Z (boot_all.ps1 section 3e; runs at logon and every 10 min via the KalsBoot scheduled task): the clean-room bots now restart themselves -- LIVE forecaster_live (subaccount 2, --variant race1_98) and ladder_live (subaccount 1), and PAPER bettor_paper, the ladder paper bot and both forecaster-variant side-by-side runs. Operator 2026-09-29: "Restart and turn everything back on obviously? Make it so they automatically keep themselves in".

A live bot is never started while results\forecaster-live.stop / results\ladder-live.stop exists (the bots exit on
it; delete it to let them come back), nor while any python process is blind to this script. Each pattern was
checked to match exactly one running process before the first run; the first run said "all up; nothing to do".
THE ARGV IN boot_all.ps1 IS NOW THE DEPLOYED VERSION of both penny bots: a variant change means editing it (and a
VERSIONS entry), or the next 10-minute run restarts the old argv after a stop.

**REVERT:** restore boot_all.ps1 from the commit before this one (section 3e is self-contained).

---

# v-ladder-top -- LIVE 2026-09-29 15:35:39Z (pid 4196820; v-ladder-penny pid 3904676 stopped by its stop file 15:35:15Z, 0 fills ever) -- prepared 2026-09-29 ~15:2xZ (research/cleanroom/ladder_live.py): the penny ladder mirrors only the TOP rung (model-2c, LIVE_LEVELS=(0,)) and in EVERY coin (MAX_LIVE_PER_CLOSE 3 -> 9). Rails unchanged (10 contracts / $12 committed / -$6 day, subaccount 1).

Why (READS_DUE 'ladder-live' day-1 read): v-ladder-penny placed and cancelled 829 orders in ~24 h and filled 0;
the paper engine in the same process filled 20 orders in 13 markets -- and NONE of the 20 was an order the live side
had placed: the 3 live slots per quarter-hour went to the first markets to lock, which never trade down to a bid,
while the fills came in markets that locked later. 16 of the 20 paper fills were the top rung, 4 the second, 0 the
third. Self-test updated and PASSED (every market goes live; top rung only; rails still refuse past 10 contracts).
Running process pid 3904676 keeps v-ladder-penny until restarted.

**RELAUNCH (after `results/ladder-live.stop` has stopped the old one and been deleted)**: the RELAUNCH line of
v-ladder-penny below (same command; the code change is in the file).
**REVERT:** `git revert` this commit, relaunch the same way.

---

# v-cent -- LIVE 2026-09-30 12:12:02Z (pid 4447780, code_sha b34346497c63, restart_bot.ps1 with v-topup) -- committed 2026-09-29 ~12:1xZ (research/pinrun.py cent_limit): hourly ladder markets (KXBTCD and the other LADDER_COIN series) take WHOLE-CENT prices only; the entry limit and the hedge limit on those markets are now rounded DOWN to the cent (never under the ask seen). The 15-minute coins are untouched.

Evidence: READS_DUE 'kxbtcd-tick' -- the one early-leg KXBTCD order since v-reopen98 (09-28 23:59 ET,
KXBTCD-26SEP2900-T82999.99, limit 97.8c from --early-max-price 0.978) came back 400 invalid_price; a KXBTCD hedge
capped at HEDGE_MAX_ASK-0.001 = 99.9c would be refused the same way (a gate must never block a hedge). Worth cents
a day at --series-size 1, so NO unplanned restart: the running pid 3882400 keeps the old code until its --minutes
4320 run ends (~10-01 14:36Z) and watch_bot restarts it with restart_bot.ps1's argv. Self-test PASSED (6 new
checks: 97.8c -> 97c; 99.9c hedge -> 99c; whole cents and 15-minute ticks unchanged; both call sites exist; the
rounding precedes the send). No flag, so versioncheck is unaffected. Read: READS_DUE 'vcent-deploy'.

**REVERT:** `git revert <this commit>` (or restore research/pinrun.py from the commit before it), then restart per
do-the-restart-yourself.

---

# v-forecaster-race1 -- LIVE 2026-09-29 15:35:02Z (pid 4196192; relaunched on the operator's "Restart and turn everything back on"; was OFF 07:26:07-15:35:02Z) -- prepared 2026-09-29 07:26Z: the live forecaster was STOPPED (stop file, 07:26:07Z, pid 4036456 exited cleanly) to relaunch with `--variant race1_98` (skip only when the gap to the strike 5 s ago was >= 2x the gap now, i.e. the index closed half the gap, and p < 0.98). The relaunch was DENIED by the auto-mode permission check ("Production Deploy"). THE LIVE FORECASTER IS NOT RUNNING until the operator relaunches it or allows the relaunch.

Why race1_98 over race05_98 (replay, 33 days, full engine, results/FC_VARIANTS_2026-09-29.md): the same 5
losing markets and the same $249 of losses removed; $200 of wins cut instead of $280 -> net +$49 vs -$31 vs base
(TRAIN +$49 / TEST $0 vs -$16 / -$15). Operator 2026-09-29 ~07:1xZ: "You do what makes most in the longrun."
Chosen after both halves were seen (selection); both run side by side in fc_variants_paper.py for the 10-02 read.
Also in this change: the start rail MAX_SUB_BALANCE 25 -> 35 (funded $25 + its own profit; the $22 committed /
$12 day / $20 run limits are unchanged). Subaccount 2 held $25.4961 at 07:25Z.

**RELAUNCH (race1_98)**: `Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "-u","research\cleanroom\forecaster_live.py","--subaccount","2","--live","--variant","race1_98","--minutes","10080" -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden -RedirectStandardOutput "C:\kals-repo\results\forecaster-live-stdout.log" -RedirectStandardError "C:\kals-repo\results\forecaster-live-stderr.log"`
(for race05_98 or plain base, change or drop the --variant pair). Before any relaunch: results/forecaster-live.stop
must not exist (it was deleted at 07:26Z).

---

# v-forecaster-race -- 2026-09-29 04:21:01Z (pid 4036456; research/cleanroom/forecaster_live.py --variant race05_98; Kalshi SUBACCOUNT 2, $25) -- LIVE: the live forecaster now SKIPS a buy when the index has closed half or more of its gap to the strike in the last 5 s AND the model is under 98% on that side (fc_variants.VARIANTS['race05_98'] = {race_x 0.5, race_p 0.98}); everything else identical to v-forecaster-live (the VEngine with no gates reproduces the paper forecaster fill for fill, self-tested). Operator 2026-09-29 ~04:1xZ: "Definitely do the 1/3 less loss for 3% profit trade first."

DEPLOYED ON THE OPERATOR'S DIRECTION BEFORE ITS FORWARD-PAPER BAR (READS_DUE
'fcvar-paper', 10-02) WAS MET -- said loudly, per the no-quiet-bars rule.
Evidence, REPLAY ONLY (tape population, results/FC_VARIANTS_2026-09-29.md, 33
recorded days): net +$3,790 vs base +$3,822 (-$32, -0.8%); money lost in losing
markets -$449 vs -$697 (-36%); 13 losing markets vs 18. TRAIN -$16 net / $148
saved; TEST -$15 net / $101 saved. About 31 versions were tried, so this row is
flattered by selection. Forward paper: race05_98 runs beside base in
fc_variants_paper.py since 01:51Z.
Before the switch, live base: 4 buys, 4 wins, +$2.02 (00:54-04:15Z); the $2.02
was moved back to the main account (ordercli --sub-return 2.02 --sub 2) so the
$25 start rail holds; the start rail now allows 5c of fee residue (25.0042).
The startup path was dry-run WITH the flag 04:19:21-04:20:21Z (pid 4056788, 0
would_place); that minute's paper records sit in forecaster-live.jsonl beside
the live process's.

**REVERT:** create `results/forecaster-live.stop`; once it has exited, delete the
stop file and relaunch WITHOUT `--variant` (the RELAUNCH line of
v-forecaster-live below).

**RELAUNCH** (this version; PowerShell): `Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "-u","research\cleanroom\forecaster_live.py","--subaccount","2","--live","--variant","race05_98","--minutes","10080" -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden -RedirectStandardOutput "C:\kals-repo\results\forecaster-live-stdout.log" -RedirectStandardError "C:\kals-repo\results\forecaster-live-stderr.log"`

---

# v-forecaster-live -- 2026-09-29 00:54:20Z (pid 4014356; research/cleanroom/forecaster_live.py; Kalshi SUBACCOUNT 2, $25) -- LIVE, NEW STRATEGY at 1/20 of paper size: the clean-room FORECASTER on its realistic fill rule. Each paper 'real' fill (size still displayed at the same price 1.0 s after the decision) becomes one immediate-or-cancel buy at that price for round_half_up(paper contracts x 0.05) minus what was already asked on that side. Operator 2026-09-29 ~00:5xZ: "I want clean room forecaster realistic fills. Exactly how it worked to get the 15% return just scaled down". REPLACES v-bettor-penny (he had asked for the wrong one), which placed 0 orders and was stopped by its stop file at 00:50:01Z.

Engine: bettor_paper.py unchanged, strats=("forecaster",): r <= 30 remaining
prints, 'blendvr' model with TRAIN z-scale and calibration map, either side at a
displayed ask 75-98.5c with p_side - q - fee >= 2c, paper caps 100 per side per
market / 400 per close. Live copies both sides of a market when the paper does.
A live miss is not retried. Subaccount 2 topped up $10 -> $25 (ordercli
--sub-fund 15 --sub 2, 200) at ~00:53Z.
Rails in code: 5 per side per market, 20 per close, 5 per order, 20 held / $22
held+in flight, 75-98.5c, never within 0.5 s of the close or on a trigger older
than 1.5 s, -$12 realized per ET day halts to the next ET day, -$20 since start
halts until restart, a resting IOC or an unreadable answer halts, refuses to
start above $25; IOC, post_only False, self_trade_prevention taker_at_cross,
"fc-" client ids; stop file results/forecaster-live.stop. Same "only writer"
exception as ladder_live.py: one POST, one DELETE in the working code
(self-test asserts it).
Self-test: bodies and refusals, proportional increments (77 -> 4, +23 -> 1,
cap 5, 3+6 -> 0, +1 -> 1), no retry after a miss, partial fill, per-close 20,
held 20, late/stale drop, settle arithmetic incl. both sides bought (-2.80),
day/run stops, rested/garbled/4xx, stop file, dry run, and a driven world where
the paper's decision-instant fill sends NOTHING and its 1-s survivor sends one
YES bid at 0.80. Planted bugs caught: 6 per side; 25 per close.
Paper evidence (NOT live, paper population): forecaster 'real' 09-28 07:15Z ->
09-29 00:45Z, 22 markets, 21 won, 1 lost (-$54.96, XRP 16:15Z, bought BOTH
sides when its view flipped), +$208.62 on $1,560.73 staked (13.4%). The
decision-instant rule on the same period: 46 markets, +$116.98 -- four of its
losses (-$62 to -$70) came from offers that vanished within the second, which
the 1-s rule never took. Whether a real order still gets the survivors is the
first thing this measures.
Pre-registered bar (written before any live fill): READS_DUE 'forecaster-live'.

**REVERT:** create `results/forecaster-live.stop` (it halts and exits), then
move the money back: `python research/ordercli.py --sub-return 25 --sub 2`
(dry run, then `--live --signoff <token>`; use the balance shown by
`--sub-status 2`).

**RELAUNCH** (after a reboot; PowerShell, from anywhere): `Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "-u","research\cleanroom\forecaster_live.py","--subaccount","2","--live","--minutes","10080" -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden -RedirectStandardOutput "C:\kals-repo\results\forecaster-live-stdout.log" -RedirectStandardError "C:\kals-repo\results\forecaster-live-stderr.log"`

---

# [STOPPED 2026-09-29 00:50:01Z -- replaced by v-forecaster-live; 0 orders placed] v-bettor-penny -- 2026-09-29 00:20:58Z (pid 3990228; research/cleanroom/bettor_live.py; Kalshi SUBACCOUNT 2, funded $10) -- LIVE, NEW STRATEGY at 1 contract a market: the clean-room BETTOR (bettor_paper.py's engine, bettor rule only, unchanged) mirrored as a real 1-contract immediate-or-cancel buy at the displayed ask each time its paper book takes an ask ('opt' rule). Operator 2026-09-29 ~00:0xZ: "I want to run clean room bettor but at a tiny size."

Account steps: subaccount 2 created 00:09Z (POST /portfolio/subaccounts 201
subaccount_number 2); $10 moved 0 -> 2 on pool 2 (ordercli --sub-fund 10 --sub 2,
200). Main pool-2 balance after: $1,063.27. Subaccount 2 is invisible to pinrun's
v-safety2 (it reads subaccount 0), same as the ladder's subaccount 1.
EXCEPTION TO THE "ordercli is the only writer" RULE, as ladder_live.py: exactly
one POST (create order) and one DELETE (cancel an IOC that came back resting) in
the working code; the self-test asserts it. Every body is checked: IOC,
post_only False, self_trade_prevention taker_at_cross (a would-be self-trade
cancels THIS order, never a resting one), 1 contract, subaccount >= 1, pool 2,
"bet-" client id, price 85-98c for the side bought.
Rails in code: 1 held per market, <= 3 sends per market (a miss may retry on a
later paper take), <= 9 contracts / $10 held, never within 0.5 s of the close or
on a decision older than 1.5 s, -$5 realized per ET day halts to the next ET day,
-$8 since start halts until restart, an unreadable answer or a resting IOC halts,
refuses to start above $25 in the subaccount; stop file results/bettor-live.stop.
Self-test: 30+ checks incl. a driven world (paper take at 95c -> one YES bid at
95c in subaccount 2 -> settle +$0.04), two empty worlds, and two planted rail
bugs caught (2 per market; 12 held). Dry run 00:16-00:20Z: feed healthy (9
indexes at 1/s, lag ~95 ms), no market in its last minute, so no decision seen
before going live -- the first live decision is the first end-to-end one.
Why at 1 contract: the paper bettor's two fill rules disagree on the same
markets (09-28 07:15Z-23:45Z: decision-instant 'opt' 11 markets, 1 loss, -$54.02
-- NEAR 22:30Z at ~85c; 'still shown 1 s later' 3 markets, 0 losses, +$9.30). A
live IOC lands between them; whether it gets the losing offers is the question.
Pre-registered bar (written before any live fill): READS_DUE 'bettor-live'.

**REVERT:** create `results/bettor-live.stop` (it halts and exits), then move the
money back: `python research/ordercli.py --sub-return 10 --sub 2` (dry run, then
`--live --signoff <token>`; use the balance shown by `--sub-status 2`).

**RELAUNCH** (after a reboot; PowerShell, from anywhere): `Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "-u","research\cleanroom\bettor_live.py","--subaccount","2","--live","--minutes","10080" -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden -RedirectStandardOutput "C:\kals-repo\results\bettor-live-stdout.log" -RedirectStandardError "C:\kals-repo\results\bettor-live-stderr.log"`

---

# v-ladder-penny -- 2026-09-28 16:01:26Z (pid 3904676; research/cleanroom/ladder_live.py; Kalshi SUBACCOUNT 1, funded $15) -- LIVE, NEW STRATEGY at penny size: the clean-room locked-average ladder mirrored as real post_only 1-contract bids (model-2c / -5c / -15c) in the last 30 s, at most 3 coins a quarter-hour. Operator 2026-09-28: "I'm giving you the go ahead for that live testing. Build the penny ladder" and "Keep trying the advanced api second account".

Account steps: POST /account/api_usage_level/upgrade 06:5xZ (201; grant
event_contract advanced); subaccount creation refused until the tier showed
"advanced" (15:53Z: 201 subaccount_number 1); $15 moved 0 -> 1 on pool 2
(ordercli --sub-fund, client_transfer_id 7ea20951-...). The live bot reads
positions/balance for subaccount 0 only (Kalshi default), so it cannot adopt or
hedge the ladder's fills; its GET /portfolio/orders (all subaccounts) matches
only its own "pin-" client ids. Both bots use self_trade_prevention maker.
EXCEPTION TO THE "ordercli is the only writer" RULE: ladder_live.py sends
create/cancel order requests itself (exactly one POST in its working code,
self-test asserts it); every body is checked for subaccount >= 1, post_only,
1 contract, pool 2, "lad-" client id before sending.
Rails in code: 10 contracts resting+held, $12 committed, -$6 realized per ET
day stops it for the day, 3 coins per quarter-hour, 3 writes a second (shares
the API key's rate limit with the live bot), refuses to start above $25 in the
subaccount; stop file results/ladder-live.stop cancels everything and exits.
Dry run 15:54-16:01Z: 3 coins, 9 would-place (98c/95c/85c), 9 would-cancel at
close. Evidence for the strategy: results/CLEANROOM_2026-09-27.md (test days
+$430 unkind / +$686 kind, 0 losses in 167 closes, paper). The live test
measures what paper cannot: real fill rate and whether fills are adversely
selected. Read: READS_DUE 'ladder-live'.

**REVERT:** create `results/ladder-live.stop` (it cancels and exits), then move
the money back: `python research/ordercli.py --sub-return 15 --sub 1` (dry run,
then `--live --signoff <token>`; use the balance shown by `--sub-status 1`).

**RELAUNCH** (after a reboot; PowerShell, from anywhere): `Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "-u","research\cleanroom\ladder_live.py","--subaccount","1","--live","--minutes","10080" -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden -RedirectStandardOutput "C:\kals-repo\results\ladder-live-stdout.log" -RedirectStandardError "C:\kals-repo\results\ladder-live-stderr.log"`

---

# v-reopen98 + v-floor90 -- 2026-09-28 14:36:17Z (pid 3882400; no code change) -- LIVE: (1) `--price-ceiling 0.98` + `--early-max-price 0.978`: 97.9-98c buys are back on the 30-second bet ONLY; the 45-second bet stays capped at 97.8c. (2) `--early-min-price 0.90` (was 0.95): the 45-second bet may buy asks from 90c, still at a THIRD of a bet (--early-frac 0.333 unchanged). Operator 2026-09-28 ~06:4xZ: "what we can do to introduce more orders now that we have less risk" and "for the 90c floor just do whatever makes the most and do the math on it. Calculate for risk and check with real examples".

Two changes on two different legs in one restart, separable in the logs by leg
and price (the 09-19 lesson was six changes and two bugs in 15 hours).

(1) REOPEN 98c ON THE 30-SECOND BET (results/SAFE0928_reopen98.md, refuted:
not refuted). The 98c band on our own fills since 09-09: 345 markets, 5 lost,
+$30. The live seller gate (v-toxic-live) would have refused ALL 5 losing buys
(sold share 0.56-0.75, offer ages 9-148 ms, all > 20 s left); one-full-bet
none. With both rules: 302 markets, 0 lost, +$275 (the rules also skip 38
winners, $35). Honest limit: 3 of the 5 catches are inside the data the gate
was designed on; out of sample 2 of 2 caught; 0 in 84 out-of-sample markets
cannot tell 0 in 100 from 4.3 in 100 (break-even ~1.9). The 45-second part of
the band held the two biggest band losses (BTC 9/19 -$108, HYPE 9/21 -$54),
so it stays capped. Expected +$10-16/day if the rate stays near 0, ~$5-8 at
1 in 100, $0 at 1.9, -$6..-10 at 3 in 100. Worst single loss ~$96 (98 x 98c),
~$144 with the late add. Paper since 09-27: the 09-25 build's whole lead over
today's settings (+$17 in 42 quarter-hours, 0 losses either side) was 9 small
97.9-98c winners. **PRE-REGISTERED STOP:** back to 0.978 on the 2nd loss in the
first 100 markets bought at 97.9-98c on the 30-second bet, on ANY such loss the
seller gate could not judge (no sold-share reading or inexact offer age), or
the moment --toxic-fresh is turned off (its protection is the whole case).

(2) 90c FLOOR ON THE 45-SECOND BET (results/SAFE0928_floor90.md, not refuted).
The floor checks the price SEEN. Only ONE 45-second loss ever came from a
90-95c ask: BTC 9/19 2:00 AM, 70 contracts (full size then), -$66.34, offer 59
ms old -- the seller gate now refuses it. (NEAR 9/21 was a 95.5c ask: today's
floor already allows it.) Corrected sample: 1 loss in 17 of our own fills in
the band. At a third of a bet: a win ~$1.85, a loss $16-29 (insured /
uninsured), break-even ~9 in 100 insured. Expected +$2-4/day at 3 in 100, $0 at
9, -$1..-2 at 12. The 14 offers the 95c floor refused since 09-23 all won
(tape, upper bound). Lower floors add nothing: the 10c edge cap already refuses
85-90c. Never with --early-frac 1.0. **PRE-REGISTERED STOP:** add up the money
of every 45-second buy whose ask was under 95c since this switch, insurance
included, from the Kalshi ledger; if it goes below $0, back to 0.95 at once
(checked daily: READS_DUE 'floor90-guard').

Startup path run in paper with the full new argv: self-test 1,270 checks,
start record price_ceiling 0.98 / early_max_price 0.978 / early_min_price 0.9.
Side effect worth knowing: the hourly BTC ladder (KXBTCD, whole-cent ticks)
had every order rejected since 0.978 went live (a 0.978 limit is not a valid
price there); at 0.98 the full leg's limit is a whole cent again.

**REVERT (either or both):** in `restart_bot.ps1` set `"--price-ceiling", "0.978"`
and delete `"--early-max-price", "0.978",` (reopen98); set
`"--early-min-price", "0.95"` (floor90); then
`powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`

---

# v-race20 -- 2026-09-28 02:50Z (pid 3739628; code change in research/pinracearm.py) -- LIVE: coin race penny bot at 20 contracts a leg (was 10, v-race10). Operator 2026-09-28 ~02:4xZ: "Coin race hasn't lost in days. Up it."

Record at the step: since 09-22 110 live races, all won, 0 ties by the log
(bars.py counts 104 won + 1 tie since 09-22 03:03 ET; the tie on 09-23 cost
$0.48); since v-race10 3 races, all won. Legs per race since 09-22: 59 with 1,
50 with 2, 1 with 3. Stake cap stays $60 (pintake's run-stake rail): 20 x 3
legs x 0.97 = $58 fits, so the cap binds only on a 4th leg (never seen). A
loss now costs about $19.40 a leg; the bot still stops on its first loss.
Code: pintake's per-take rail ships at 10 for this process; pinracearm now
raises it through pintake.set_limits (the one-way ratchet, printed) when
--max-contracts is above 10 and at most pintake.HARD_MAX (25); above 25 the
old refusal still fires. Self-test 213 checks pass.

**REVERT:** stop pid 3739628, then relaunch with the v-race10 argv
(`--max-contracts 10`, everything else identical; VERSIONS v-race10 has it).

---

# v-onefull -- 2026-09-27 08:11:15Z (pid 3510420; git ee351cc + this commit; code change in research/pinrun.py) -- LIVE: `--one-full-bet`: a market that already holds a full bet never takes a second full bet (the A23 scale-in); the top-up of an unfinished position and the last-15-seconds add are untouched. Operator 2026-09-27 03:2x ET: "Fix. This. ... SOLVE BY ANY MEANS"; results/WHY_NO_MONEY_2026-09-27.md policy P1.

Why: the bot picks as well as it ever did (2.3 -> 2.0 losses per 100 markets
between the two weeks); what changed is the size of a loss against a win. A win
paid $1.69 then and $1.93 now; a loss cost $25 then and $80 now, and the two
worst markets on record were same-second DOUBLE bets on one coin: BTC 09-23
(176 contracts, -$130) and BTC 09-27 (198 contracts, -$132). Refusing the
second full leg on our own fills: +$107 over 19 days (week 1 -$13, week 2
+$120); winners given up: 7 double-bet winners worth $22 ($4-16 each); on top
of the rules already live (toxic gate refuses 09-27's legs) about +$43-51,
all of it 09-23. It is a size-of-the-worst-market rule more than a money
claim: the worst single market becomes one bet (~$95 at size 99) instead of
two (~$193), and the biggest insurance false alarm halves with it because the
hedge is the same contracts. Downside if wrong: about $1.50-2 a day of winning
double bets. Gates no hedge (rebuy_ok is the entry path; the hedge pass is
separate), needs no new signal, fights no pre-registered bar; it confounds the
97.8c-ceiling watch by about $2 a day.

Code: research/pinrun.py -- globals ONE_FULL_BET / _DEFAULT_ONE_FULL_BET
(default OFF), `rebuy_ok` returns False under the flag after the late-add
allowance and before the band, `--one-full-bet` in main, the flag added to
_OFFLINE_PINNED_FLAGS and _FLAG_GLOBALS; 7 new self-test checks (pure: full
position refused at 0.5c and 1c cheaper, top-up allowed, first buy and other
market untouched, source order late-add < flag < band; DRIVEN: the genuinely
cheaper 95.4c world sends ONE order with no scalein_cap record and a
rebuy_band refusal, the 2-contract top-up world still tops up). Self-test 1,263
-> 1,270, plain and with the live argv; startup path run in paper with the
full live argv plus the flag. Not the flag `--max-per-market 1`: that also
kills the 45-second leg's top-up (+$56 over the record) and the late add.

What to watch: `refused` records with gate rebuy_band on a market that already
holds a full bet; no market should ever show two full-size entry orders in one
close. Read with the 10-01 bars.

**REVERT:** delete the line `    "--one-full-bet",` from `restart_bot.ps1`, then
`powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/restart_bot.ps1`
(the code stays; the flag is the whole deploy).

---

# v-ceiling978 -- 2026-09-27 07:05:37Z (pid 3492544; git 3fb8120; no code change) -- LIVE: `--price-ceiling 0.978`: the bot no longer buys at 97.9c or 98c (was 98.0c since 09-09). Operator 2026-09-27 03:2x ET: "Fix. This. ... SOLVE BY ANY MEANS"; his own earlier idea (09-26): "our lowest allowed bet earns 1.9%, does increasing to 2% add any new risk". (Staged 06:56Z; the 06:57Z restart was refused by the tool permission checker; he added an allow rule at 07:03Z and the session restarted it.)

Why (our own fills, Kalshi ledger + live logs, 09-09..09-27, 917 markets):
- The 98c band (paid 97.85c-98.0c): 301 markets, 5 lost = 1.7 per 100 against
  a break-even of 2.0 per 100; own-leg money -$5.38 over 19 days, -$76 with
  the insurance bought on those markets. A third of all contracts (14,421 of
  44,650) for $0 of income. Every other band is clearly positive: 97c +$81
  (1.4 vs 2.5 per 100), 95-96c +$212 (1.2 vs 3.8), 90-94c +$346 (3.1 vs 7.1).
- Structural, not a sample accident: at 98c a win pays 2.0c and a loss costs
  98c, so the strategy needs fewer than 2.0 losses per 100 there; our all-band
  rate is 2.4 per 100 and the model is 20-80x overconfident above 0.999
  (calibration, index tape). The band is where the model is most wrong and
  the price most unforgiving. Best case (1.7 per 100 holds) it earns +0.33c a
  contract = about $2.50/day; base case it earns nothing.
- Why the bot stopped compounding (09-09..09-17 +$478 vs 09-18..09-27 -$18
  through 09-27 04:00Z... see WHY_NO_MONEY when it lands): gross win per
  contract is the same in both halves (~3.2c) but the loss dollars per
  contract went 0.5c -> 2.4c as size rose 20 -> 99-198 and the average price
  rose 95.5c -> 96.5c. Expected money per contract = 0.976 x win - 0.024 x
  price: 4.5c wins at 95.5c give +1.9c; 3.5c wins at 96.5c give +1.1c;
  2.0c wins at 98c give +0.0c. Every cent of average price is worth about a
  cent of expectancy per contract; dropping the 98c band lowers the average
  price of what is left to ~95.6c.
- Two of the three biggest losses were in the band: BTC 09-19 16:00Z (-$107.95
  at 98c) and BTC 09-27 04:00Z first leg (-$97.05 at 97.89c).

Interactions checked: the early leg's own floor/ceiling (--early-min-price
0.95, A78b sweep cap) and the late boost are unchanged; worst_close_cost reads
the running ceiling, so auto-size rises by 0.2% (bank / (4 x 3 x 0.978)) --
immaterial. Startup path run in paper with the full live argv plus this flag:
self-test 1,263 checks ok, start record price_ceiling 0.978. Not a gate on
hedges (hedges pay up to HEDGE_MAX_ASK; the ceiling is an entry price).

What to watch: contracts per day should fall about a third; income per day
should not fall (record says $0 lost); if the bank grows the auto-size
formula will try to spend the freed cash at <= 97.8c -- the depth under 97.8c
is the new limit, which is the point.

**REVERT:** delete the line `    "--price-ceiling", "0.978",` from
`restart_bot.ps1`, then
`powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-repo\restart_bot.ps1'`

---

# v-race10 -- 2026-09-27 06:01:49Z (pid 3483656; git dc0ace5; no code change) -- LIVE: coin race penny bot at 10 contracts a leg (was 5, v-race5). Operator 2026-09-27: "Go 10. I have a feeling that may be the main bread winner after it's finished being developed."

Argv = the v-race5 argv with `--max-contracts 10`; `--max-stake 60` UNCHANGED
(a first launch with `--max-stake 120` was refused by pintake's own $60
run-stake rail and never armed; 10 contracts x 5 legs x 0.97 = $48.50 fits
under $60 with the rolling stake). Everything else as v-race5: inside 30 s
only, 90c or better, at most 5 legs, stop on the first loss (a tie counts as
a loss). Record at the step: since v-race5 (09-24 15:16Z) 38 races, 38 won,
+$7.38; since 09-22 105 races, 104 won, 1 tie, +$9.44; 154 legs at 96.7c
average, break-even 96.9 of 100 legs must pay, actual 99.7. A loss now costs
about $9.70 a race (was $4.85); the expected gain of the step is about
+$3.50/day. The photo-finish arm (gap075) lost 2 paper races on 09-26 that
live did not enter or entered on the winning leg; no filter for close
finishes exists yet. Swap done at 06:01:35Z between races with no open
position (new bot started and confirmed before the old was stopped).

**REVERT:** stop pid 3483656, then from C:/kals-repo:
`Start-Process C:/Python314/python.exe -ArgumentList '-u','research/pinracearm.py','--live','--max-contracts','5','--max-stake','60','--live-rolling-stake','--live-tau-max','30','--live-min-price','0.90','--live-max-legs','5','--live-confirm','5','--live-clock-tau','20','--minutes','10080','--log','C:/kals-repo/results/pinracepenny-live.jsonl','--model','fair','--tau-max','60','--min-price','0.80','--min-edge','0.00' -WorkingDirectory C:/kals-repo -WindowStyle Hidden`

---

# v-toxic-live -- 2026-09-27 05:08:48Z (pid 3471704; git a5d72e1; no code change) -- LIVE: `--toxic-fresh` ON. With more than 20 s left, refuse an ENTRY when the ask level we would hit is under 500 ms old (exact age) AND takers sold more than half of the last 3 s of volume on our side. Entry only; the one call sits below the hedge pass (self-test asserts it), so no hedge is ever gated. (Staged 04:48Z; the first two restart attempts failed -- path mangled, then refused by the tool permission checker; ran at 05:07Z on the operator's repeated instruction to run it myself.)

Why now, five days before the pre-registered read (results/PREREG_toxic.md,
bar at >= 7 days of live `sell_share_3s`, ~10-01): the 04:00Z BTC loss
(-$131.98 after the hedge; both legs: level age 148 / 50 ms, sold share 0.56 /
0.58) is the cell's textbook case and arm-toxic refused it. The bar's three
conditions on live's own fills since 09-25 12:26Z: the AND cell is net
NEGATIVE (8 markets, -$118.10) [met]; holds >= 2 losers [NOT met: 1]; loss
rate >= 3x the rest (1/8 vs 1/30 = 3.8x) [met]. The pre-registered finding
that built the gate (our fills 09-13..09-24, 392 markets): the AND cell held
8 of 12 early losers, 9.2 losses per 100, net -$285 (about -$75 with today's
hedges). Cost if the gate has no power: the 7 winners it skipped this week
were worth $13.90 in 1.6 days, about $9/day. Operator 09-27 (this session):
"you have permission to do anything, run anything, and spend anything for the
project"; standing rule: lose less first. Deployed by the session, not on a
fresh sign-off for this flag -- he can revert with the line below.

Measurement after this: the refused set no longer has live fills. The bot
logs each priced refusal (`refused`, gate toxic_fresh) with the market; its
outcome is the MARKET result (tape population: understates what our fills
would have lost, so the gate's benefit reads conservative). arm-live-frozen
(no gate) keeps the no-gate record. A workflow post-mortem
(results/POSTMORTEM_2026-09-27.md, running at deploy) re-measures the cell on
every live fill since 09-09 from the trade tape; if it comes back a wash,
revert.

**REVERT:** remove the line `    "--toxic-fresh",` from `restart_bot.ps1`,
then `powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`
(no code changes; the flag is the whole deploy).

---

# v-onepool -- 2026-09-26 07:38Z (ACCOUNT setting, no code in the bot changed) -- LIVE: Kalshi's automatic 15/85 cash split is OFF and all cash sits in pool 2 (Crypto & Commodities), so the account total pinrun sizes on is now exactly the cash its orders can spend. Operator 09-26 ~07:2xZ: "Yes combine all the cash."

Before: pool 0 $139.1532, pool 2 $1,006.2552, target {0:15%, 2:85%} (it parked
$139 of the 09-19 deposit where crypto orders cannot reach; pinrun read the
$1,145.41 total, ~12% more than it could spend). After (read 5 s and ~90 s
later): pool 0 $0, pool 2 $1,145.4084, allocations [], total unchanged to the
cent. Sent by `python research/ordercli.py --pools-off --move-dollars all
--from-pool 0 --to-pool 2 --live --signoff 6d4d528a415e73fc` (new pool mode,
self-test 7 refusal cases); transfer_id 21feddb9-4897-4f7c-a34d-eb7de73adbb0.
CONSEQUENCES: with the split off nothing moves cash automatically any more --
a NEW DEPOSIT may land in pool 0 and sit there (move it with the same command);
any non-crypto test (the reward test: politics markets are pool 0) must move
its own cash to pool 0 first, which makes pinrun oversize by that amount again.
Not checked: how the live bot's log recorded the move (the log read was blocked
by the permission checker); the total never changed, so there is nothing for
its deposit detector to see unless it read mid-transfer.

**REVERT:** restore the old split (Kalshi then moves 15% back to pool 0 within
~10 s): POST /portfolio/target_balance_allocation
`{"allocations":[{"exchange_index":0,"percent":15},{"exchange_index":2,"percent":85}],"resting_margin_reservation":"sum"}`
-- ordercli has no flag for it; it is a one-line addition to pools_main.

---

# v-scalein-caps -- 2026-09-25 12:23:53Z (pid 2951024, code_sha f9548c5571ff) -- LIVE: a same-market scale-in needs a genuinely cheaper ASK (not a sweep-inflated average) and buys only the cheaper contracts; pintake's rails are back to their designed sizes and a hedge covering a held position is never refused on dollars. No flag changed. Operator, 09-25: "do what makes the most money, use the risk in the calculating... Same with order caps."

(A) rebuy_ok: A23's 0.5-1c band is also measured against the cheapest ASK taken
in the market (new per-market `ask_tk`), not only the average paid. Strictly
narrower than before; v-lateadd unchanged.
(B) scalein_cap: an A23 scale-in's limit is capped at min(first ask, paid) -
0.5c, floored to the tick (record `scalein_cap`); the sweep sizes from the
depth under it. Entry path only.
(C) selftest() restores pintake's four rails in its finally: at size 88 the
rails are 132 / 198 / $538 (were 163.5 / 245.25 / $664 since 09-19 12:26Z,
leaked by the A66 test).
(D) pintake.check_take: hedge=True AND the ledger holds this ticker on the
other side AND count <= held + 0.01 -> the stake cap and loss abort are
skipped. Every other rail unchanged; pinracearm / cmdlive / pinrun_afternoon
never pass hedge=True (pinracearm self-test 213 identical on both pintakes).

Evidence: live 09-18..09-25, 8 A23 scale-ins on full positions: 6 at a
same/dearer ask than the first (sent ~0.3 s after the first fill) -- 5 won
$14.00, BTC 09-23 lost $64.83 (second leg -$76.52 + its $11.69 hedge share),
net -$50.83, -10.7c/contract vs +0.9c for first legs at the same seconds-left;
2 genuinely cheaper +$11.46. Re-deciding all 11 live full-position re-buys:
exactly the 6 change; of 131 re-buy refusals, 0 newly allowed. Resample
(moneyproj rules, 4,000 paths, 60 d, not using the BTC outcome): keeping them
is worth <= ~$0.7/day even if no worse than first legs; ~-$5/day and +5 pts
halt probability at the record's loser rate. Designed caps: 0 of 1,467 live
entries and 0 of 41 live hedges would have been refused; peak use 57% of
$538. Driven before -> after: BTC double buy 2 orders -> 1; cheaper-touch
scale-in 5 @ 96.04c avg -> 3 @ 95.4c; hedge at the stake cap / loss abort
0 of 5 -> 5 of 5. Self-test 1252 -> 1263 plain and live argv on the real file;
pintake +22 checks; pinracearm passes; pinattrib 55; versioncheck clean; each
change reverted fails its own checks. Paper arms get it at the next sync.

**REVERT:** `git checkout fe6a99d -- research/pinrun.py research/pintake.py`, then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`
(pinracearm loaded pintake at its own start; nothing to do for it).

---

# v-safety2 -- 2026-09-25 09:36:44Z (pid 2934836, code_sha 28f5e66b2169) -- LIVE: three safety fixes (1, 3, 5); no trading rule changed. Operator's go-ahead 09-25 (~08:5xZ): "it's just doing what it already does but more safely... then do that". Fix 4 (restoring the designed pintake caps) is HELD for the operator: it would tighten a cap pintake also applies to hedges.

(1) The bot now asks Kalshi what it holds: at startup (GET /portfolio/positions,
adopting only a position in our series, in an open market, seen in two reads
>= 2 s apart) and after any order whose reply was lost (GET
/portfolio/orders?ticker=, exact client_order_id). A real fill it did not know
about is booked, hedged and settled into the day-loss total exactly as a seen
fill; a lost hedge that did not fill is sent again; a failed read changes
nothing and is retried (max 1 GET/s, 3 s wait, below the hedge pass). New
record kind `ktruth`. No continuous position polling (a lagging endpoint read
as a hedge could leave a position naked).
(3) An order that would go out as "0.00" contracts is treated as zero
(late_add_full / zero_take use round(take_n, 2) <= 0), not sent and refused.
(5) Paper arms no longer overwrite a second booking made in the same second
(about 1 in 7 was lost); the live path is byte-identical for this item.

Evidence: results/RED_TEAM_2026-09-25.md reds 1-2 and the verified power-hour
audit findings; driven worlds through the real loop, before -> after: lost
entry that really filled -> 0 hedged, exit at 0.05 s -> 5 hedged and settled;
lost hedge never placed 0 -> 5 covered; 2-of-5 partial 2 -> 5; unknown startup
position never hedged -> adopted and hedged; sub-cent add order error ->
refused; paper 1 -> 2 bookings. When every read fails, behaviour is identical
to v-zerotake. Mutation checks: each fix reverted inside the build fails its
checks (14 / 1 / 2). Self-test 1230 -> 1252 green plain and under the live
argv on the real file; pintake caps after startup unchanged (163.5 / 245.25 /
$664 at size 88); pinattrib 55; versioncheck clean.

Not in this version (operator decisions, see HANDOFF): fix 4 (rails restore)
and the scale-in double buy (A23 compares the new ask with the AVERAGE PAID,
which a sweep inflates, so a same-or-dearer ask reads as cheaper: 5 cases
since 09-22, 4 won ~$9, BTC 09-23 lost $76.53 of its -$130.41).

**REVERT:** `git checkout d9fd894 -- research/pinrun.py`, then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`.

---

# v-zerotake -- 2026-09-25 06:25:05Z (pid 2894452, code_sha 52b3e5fb28f8) -- LIVE: the bot never sends (or books) an order for ZERO contracts. A late add on a position already at the (1 + frac) x SIZE cap is refused as `late_add_full`; any other path that reaches the send with 0 is skipped and logged `zero_take`. No trading rule changed.

**Why -- a halt, measured.** 2026-09-25 06:14:55Z (2:14 AM ET),
KXHYPE15M-26SEP250215-15: the late boost filled the position to 1.5 x SIZE
(88 -> 132) at 5 s; a 0.5-1c cheaper ask then passed A23's scale-in band in
rebuy_ok, the v-lateadd relabel capped the add at (1 + 0.5) x SIZE - have =
0, and the order went out for 0 contracts. pintake refused it ("count 0.0 is
not positive") twice -- the two order-path errors that halt the run. The
market won (+$5.77); watch_bot restarted the bot in ~1 min (06:15:32Z ->
pid 2885852). No money lost; each repeat would have cost a minute of trading
and a quick-restart slot.

**What changed:** (1) in the v-lateadd relabel block, after the early-leg
gates and before the signal point, `if take_n <= 0: _gate("late_add_full")`
+ continue -- burns no attempt, logged once per market per close; (2) a
backstop right before `pintake.take` on the live path and before
`_book_slot` on the paper path: `take_n <= 0` -> `rec("zero_take")` +
continue (the attempt stays consumed). Entry path only; the hedge pass is
above and untouched. pinattrib knows `late_add_full`.

**Proof:** a driven world through the REAL loop on the LIVE path, with a
fake wire that refuses count <= 0 exactly as pintake did: full 5 at 14 s,
late add 2.5 (= the 7.5 cap), then a 0.6c cheaper ask. OLD code (replayed
by the session): a third order for 0.0 contracts and an `error` record --
tonight's incident reproduced. NEW code: orders [5.0, 2.5], 0 errors, one
`late_add_full`, no halt. Source checks: the gate sits after `staged_none`
and before the signal; `zero_take` appears twice, the live one right
before the live `out = pintake.take(`. 1,228 -> 1,230 checks green plain
and under the deployed argv on the real file; pinattrib 55; versioncheck
clean.

Paper arms are NOT restarted: their paper path never called pintake, so a
zero take booked a zero slot and raised nothing; restarting them would
reset the 7-day windows of fresh500 / toxic / btcd / edge2c.

**REVERT:** `git checkout 46d1f70 -- research/pinrun.py research/pinattrib.py`,
then `powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`.

---

# v-farrung -- 2026-09-25 04:0xZ -- CODE ON DISK, EVERY FLAG OFF: the bot can buy the FAR rungs of the hourly BTC ladder at 99c (results/FAR_RUNG_2026-09-25.md), but only when seven new flags are passed. The live command line is unchanged, so the live bot does nothing new; the next restart merely runs this code. A 1-contract live test needs the operator's sign-off and its own entry (`v-farrung1`).

**The idea (plain).** With 45 s left, a rung $150 or more from where the
settlement is heading has never finished on the wrong side (0 of 2,136
closes since 09-01, worst miss $136). Those rungs sit at 99c with hundreds
to thousands of contracts resting, and the live bot's 98c ceiling turned
five of them away on 09-24 (one with 7,619 contracts). A winner nets 0.93c
a contract after fee; a loser costs 99.07c; break-even is 0.93 crossings
per 100 contracts. Bank-limited: about $68-85/day at today's bank if the
fills are real, which is what the 1-contract test measures.

**What changed in code (all default None/off, `_DEFAULT_*` twins, pinned in
K1; every branch gated on the ticker being a ladder rung AND its flag):**
- `--ladder-cushion-min/--ladder-cushion-max` (dollars, together): the
  ladder universe keeps every rung whose distance from the projection is
  inside the band, both sides, instead of the nearest 3.
- `--series-ceiling` (e.g. 0.99), `--series-flip`, `--series-ev-floor`: a
  rung is judged by these; every 15-minute market by the old constants
  through the same calls.
- `--series-max-per-side`, `--series-max-per-close`: at most N rungs a side
  per close, nearest the cushion first; and a separate per-close budget so
  ladder legs neither spend nor are refused by the 15-minute budget.
- Gates `cushion` and `series_side` (right before the ceiling gate, so a
  refusal burns no attempt) and `series_close` (where close_budget is
  asked). All three sit BELOW the hedge pass on the entry path only; a
  driven check hedges a ladder position in full on belief collapse.
- `projection()` now holds the arithmetic `fair()` used inline (moved, not
  changed; a check proves fair pivots exactly on it). `mu`, `K`, `cushion`
  are written on ladder signals/orders/refusals. pinattrib knows the gates.
- Known limits: `early_dear` (97.5c early-leg ceiling) is untouched, so a
  99c rung trades at 30 s or less, never 31-45 s ($150 also uncrossed at
  30 s, worst $101). The cushion is in index dollars (BTC scale). A rung
  may still take a top-up to 2 contracts (MAX_PER_MARKET).

**Proof the live path is the same:** with the flags absent a KXBTCD world
produces exactly v-ladder7's ladder record keys, both 99c rungs are refused
`price_ceiling` at 98c, no new gate fires, no decision record carries mu or
cushion; the stub fetch is byte-identical; `count("if _ssz is not None:")
== 3` and the staged_none/_stage46 orderings hold. 1,208 -> 1,228 checks
green plain, under the deployed argv, and under the deployed argv plus the
seven flags (the startup path of the test), re-run by the session on the
real file. pinattrib 55, pinflat green, versioncheck clean.

**The paper arm:** `arm-farrung` = live's argv plus
`--ladder-cushion-min 150 --ladder-cushion-max 600 --series-ceiling 0.99
--series-flip 0.0014 --series-ev-floor 0.005 --series-max-per-side 1
--series-max-per-close 2` (sync_arms row). It exercises the decision path;
paper fills at 99c prove nothing about supply, the live test does.

**REVERT (code):** `git checkout 53f07b3 -- research/pinrun.py research/pinattrib.py sync_arms.ps1`
(the live bot is not running this code until the next restart; if it has
been restarted since, follow with
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`).

---

# v-ladder7 -- 2026-09-25 03:2xZ -- CODE ON DISK, PAPER ONLY: the ladder table knows all seven hourly series Kalshi lists on an index the bot already follows (KXBTCD + KXETHD KXSOLD KXXRPD KXDOGED KXBNBD KXHYPED). The live command line is unchanged (`--series KXBTCD --series-size 1`), so the live bot does nothing new; the next restart merely runs this code.

**What changed in code:** `LADDER_SERIES` / `LADDER_COIN` / `LADDER_STEP`
gain six rows; `ladder_universe` reads a rung's strike from
`custom_strike.floor_strike` when the top-level `floor_strike` is null
(KXDOGED's shape, 55 of 55 rungs); the offline harness can plant that shape.
Nothing else: `series_size_for`, `coin_of`, the live gate in main(), the
trade_loop branch and every 15M path are untouched.

**Proof the live path is the same:** self-test checks that `--series KXBTCD`
alone yields exactly SERIES_TO_INDEX + {KXBTCD: BRTI}; with no `--series` the
universe object IS SERIES_TO_INDEX; the KXBTCD stub fetch is the same one GET
with the same params and the same three rungs; coin_of / series_size_for
answer as before for KXBTCD and KXBTC15M tickers. 1,188 -> 1,208 checks green
plain, under the deployed argv (`pinrun.py --selftest <live argv minus
--live>`, re-run by the session at 03:2xZ: 1,208 ok, SELF-TEST PASSED) and
under the arm's argv. pinflat 23, pinattrib 55, versioncheck clean.

**The paper arm:** `arm-hourly-all` (sync_arms row, pid 2853628, log
`results/pinrun-paper-20260925T030630Z.jsonl`), live's argv with the
`--series` group swapped for all seven. Question: do the other coins' hourly
books fill us the way BTC's do? Read via armh2h2 after >= 7 days.

**REVERT (code):** `git checkout 5a83ffe -- research/pinrun.py research/pinflat.py sync_arms.ps1`
(no restart needed: the live bot is not running this code until the next
restart; if it has been restarted since, follow with
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`).

---

# v-tradefeed -- 2026-09-24 ~22:3xZ -- LIVE at the next restart: the bot subscribes to Kalshi's `trade` channel and LOGS `sell_share_3s` on every signal, order and priced refusal. The `toxic_fresh` gate ships OFF (paper arm `arm-toxic`). No trading rule changed.

**Why.** results/PREREG_toxic.md: on our own early entries, a level posted
under 500 ms ago WHILE takers were net-selling our side in the prior 3 s is
where the losses live (87 markets, 8 of the 12 early losers, -$285; every
other cell positive). The gate needs the trade feed; the bar needs the live
bot to LOG the number first (7 days), so the feed goes live now, logging
only.

**What is always on once the bot runs this code:** livebook subscribes to
`trade` for the watched tickers on its own subscription id, keeps 12 s of
prints per ticker, and answers `taker_flow(tk, side, 3.0)` -> (bought, sold,
age) or None when the newest print for that market is older than 5 s. A
trade-channel error never marks a book suspect and never resyncs (it is
counted and re-subscribed once per connection). Every read in pinrun is
inside try/except that yields None. Records: `trade_feed` on connect and
reconnect; `sell_share_3s`, `taker_n_3s`, `trade_age_s` on signals, orders
and priced refusals. Live smoke (read-only, 3 markets, 14 s): 847 prints,
0 gaps, 0 malformed, books never suspect, ~5% more frames than the book
deltas. Message shape confirmed against the recorder's copy (`count_fp`,
`yes_price_dollars`), not the docs.

**The gate (off):** `--toxic-fresh` with `--toxic-min-age-ms 500
--toxic-min-share 0.5 --toxic-tau-min 20`: refuse an entry with more than
20 s left when the level age is exact and under 500 ms AND sell_share_3s >
0.5. Stands down on None. Entry only, below the hedge pass, after the
early-leg gates (source-order check). `arm-toxic` = live's argv plus the
flag.

Self-test 1,168 -> 1,188 checks green plain, under the deployed argv and
under the arm's argv; livebook and pinattrib green; versioncheck clean.

**REVERT:** `git checkout 8624461 -- research/pinrun.py research/livebook.py
research/pinattrib.py sync_arms.ps1`, then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`.

---

# v-daycap-brake -- 2026-09-24 ~18:1xZ -- watchdog + app: the DAY loss cap halt is now recognised as a money brake (15-min cooldown, BRAKE status); no trading rule changed

Found by the 2026-09-24 guardian review: pinrun's -$200 day cap halts with
the text "DAY loss cap: ...", which was in neither watch_bot.ps1's money-
brake pattern nor the app's. It has never fired live. When it did, the
watchdog would have restarted the bot at once and it would have re-halted
every ~3 min until midnight ET (the cap persists across restarts by design)
while the app said NOT RUNNING and the phone flipped DOWN/TRADING. Now:
watch_bot waits the 15-min cooldown between attempts (self-test case with
the halt's verbatim text), and the app shows STOPPED BY A SAFETY BRAKE
naming the cap. Deployed by replacing the watchdog and relaunching the app;
the bot itself is untouched.

**REVERT:** `git checkout 997cbc9 -- watch_bot.ps1 research/pindesk.py`, then
replace the watchdog (stop watch_bot, run `boot_all.ps1 -NoArms`) and relaunch
the app.

---

# v-btcd1 -- 2026-09-24 ~17:0xZ -- LIVE: the HOURLY BTC ladder (KXBTCD) trades for real money at ONE contract a market, alongside the 15-minute markets

Operator: *"Just run hourly btc full on exactly how we would to make real
money but at 1 contract instead."* Flags added to restart_bot.ps1:
`--series KXBTCD --series-size 1`.

**What it is.** Kalshi's hourly BTC market settles on the same rule as our
15-minute one (the mean of 60 one-second BRTI prints). It is a LADDER -- one
event per hour, ~188 strikes -- so the universe takes the 3 rungs nearest the
index inside 900 s of the hour (v-btcd paper work, 2026-09-24 08Z). Every
gate, the hedge, the loss cap, the drawdown brake and the close budget are
the same code. Only the size differs.

**Why size 1 and not SIZE.** SIZE is bank-driven (78-88 contracts today). An
untested family at that size risks the main strategy's money on a fill rate
nobody has measured. `series_size_for()` caps a ladder ticker at
SERIES_SIZE, applied at the signal point AND again after every widener on
both send paths, so the 1.5x late boost cannot undo it. `--series` LIVE is
REFUSED without `--series-size` (proved by running it).

**Why it is worth real money rather than more paper.** Paper cannot say
whether we get filled, and that is the whole question: the hourly books hold
a median 838 contracts at the price we buy against 28 on the 15-minute
markets (arm-btcd, first 7.5 h), and 3,486 under the 98c ceiling against 168.
If the fills are real, the hourly family is where more bank actually deploys
-- on the 15-minute markets the book runs out past ~3x today's size.

**Why NOT a separate close budget, measured first** (live logs 09-20..24, 425
closes): a budget gate fired on 25 closes (6%), and only 2 closes in five days
lost a market that would really have traded (<= 98c, model >= 99.5% sure). At
$0.51 of average value per market that is $0.05-0.20 a day of crowd-out, and
the budget counts CONTRACTS (2 x SIZE = 156 today), so one hourly contract
spends 1 of 156. Re-keying the budget in the money bot to protect 20 cents a
day is the wrong trade.

**Exposure added:** at most 2 contracts per hourly market (--max-per-market),
24 closes a day, ~97c each -- under $50 a day at risk, every existing rail
unchanged.

Self-test 1,168 checks green plain AND under the deployed argv with the new
flags; pinattrib 55; versioncheck clean. A driven check runs one world with
the flag in force and shows the hourly rung taking 1 contract while a
15-minute market takes the full 5.

**Caught while building, worth recording:** the first draft inserted the cap
between `sig["take_n"]` and the early-leg gates, which re-parented them --
the identical block-nesting regression as 2026-09-24 04:4xZ. The DRIVEN
early-floor check written after that incident caught it in one run.

**REVERT:** delete the `"--series", "KXBTCD", "--series-size", "1",` line
from restart_bot.ps1 and run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`.

---

# v-race5 -- 2026-09-24 ~15:2xZ -- LIVE (coin race penny test): 1 contract -> 5 contracts a leg, stake cap $20 -> $60

Operator, 2026-09-24: "If you're ready to size coin race up and feel confident
we can give it a small boost." This supersedes the standing "size stays 1
contract" rule of 2026-09-22.

**Why 5 and not more.** Since v-race30 (09-22 07:03Z): 60 races, 59 won, 1
TIE, 0 lost, +$1.17 on Kalshi's books; 95 legs at 97.5c average. Break-even
at those prices is 97.7 legs paying in 100; we are at 98.9 -- a margin of
1.2 points, which on 95 legs cannot be told apart from zero with confidence
(roughly +/- 2 points). So this is a size that makes the daily number
VISIBLE (about +$1.50/day if the edge is real) without a single bad race
costing a week: one losing leg at 5 contracts is about -$4.90, a two-leg
race about -$10.

**What makes it safe now and did not before.** v-race-tie1 (06:0xZ today):
a tie is read from Kalshi's own result, pays 50c to both tied coins, and
counts as a LOSS for the stop-on-first-loss rail. On 09-23 a real tie cost
-$0.95, was booked +$0.05, and the rail did not fire -- at 5 contracts that
same race would be -$4.77 and the rail WOULD now stop the test.

Unchanged: inside 30 s only, 90c or better, at most 5 legs, rolling stake
(settled races give their stake back), stop on the first loss.

**Watch next:** `arm-gap075` (refuse races whose top two coins are within
0.75 basis points -- 15 in 100 of the races we enter are that close against
7 in 100 of all races). If it shows those races are the loss class, the
filter goes in BEFORE any further size.

**REVERT:** stop the penny bot and relaunch with `--max-contracts 1
--max-stake 20` (the argv is in HANDOFF.md).

---

# v-paper-flags -- 2026-09-24 ~09:0xZ -- CODE IN THE REPO, BOTH SHIP OFF; the live bot is unchanged (its next restart runs the same defaults): `--series KXBTCD` (paper arm arm-btcd) and `--fresh-min-age-ms 500 --fresh-tau-min 20` (paper arm arm-fresh500)

- `--series KXBTCD` (refused with --live): the hourly BTC strike ladder in the
  universe, 3 rungs nearest BRTI, strike per market. Default path proven
  byte-identical (identity index map; byte-identical GETs in a driven default
  world). Bar: results/IDEAS_2026-09-24.md item 2 (7 days, >= 30 fired closes,
  0 paper losses at <= 30 s, >= 660 captured contracts).
- `--fresh-min-age-ms 500 --fresh-tau-min 20`: with more than 20 s left,
  refuse a level known to have been posted under 500 ms ago (gate
  `fresh_level`, entry only, below the hedge pass). results/PREREG_fresh.md:
  6 of the 7 early losers that survive the live rules hit a level 19-229 ms
  old; resting levels 0 of 155; money a wash on the record. Live = the arm +
  the fresh entries, so the refused set's real outcomes are live's own fills.
  The old "nothing may branch on the quote age" self-test now asserts that
  the only branch is this one, that the flag ships off, and that the bar
  file exists.

Self-test 1,134 -> 1,162 checks; pinattrib 55; versioncheck clean.

**REVERT (code only):** `git checkout 3c82dcd -- research/pinrun.py research/pinattrib.py sync_arms.ps1` (nothing live to restart).

---

# v-hwm-reset -- 2026-09-24 ~06:5xZ -- watchdog + app now; the bot at its next start: after a DRAWDOWN halt the watchdog no longer restarts the bot, and START on the app re-bases the 20% mark to the balance

Operator: "Yes to drawdown halt." Today: mark $1,037.33, halt line $829.86,
bank ~$926 -- one more -$96 day trips a halt that until now needed a human
to edit results/pinrun-hwm.json while the watchdog restarted the bot every
15 min into the same halt.

**Protocol.** `results/pinrun-hwm.reset` is written ONLY by the app's START
(`pindesk.do_start -> arm_hwm_reset`) and only when the status is a
DRAWDOWN halt. At the bot's next start `apply_hwm_reset()` checks that the
newest live log's last halt was a DRAWDOWN brake, sets the mark to the
balance read then, deletes the flag, writes `hwm_rebased` {old, new} to the
log and a dated `v-hwm-rebase` line at the top of this file. Any other last
halt: flag deleted, `hwm_reset_ignored`, mark untouched. Balance unreadable:
`hwm_reset_failed`, flag kept. The 20% brake itself is unchanged and trips
again 20% under the NEW mark. watch_bot.ps1: a DRAWDOWN halt with no flag
is HELD (logged once, no restart); with the flag it restarts at once; every
other halt/crash restarts exactly as before. The app says: "HALTED: 20%
drawdown from the $X high mark (bank $Y). Press START to re-base the mark
and resume. It will NOT auto-restart."

Also found and fixed: `pindesk.Ledger.last_halt()` returned the run's `end`
record, so the app had NEVER shown SAFETY BRAKE for a real halt.

Self-tests: pinrun 1,117 -> 1,134 (green under the deployed argv), pindesk
167 -> 178, watch_bot.ps1 -SelfTest 13 (new), versioncheck clean. No
trading rule changed.

**REVERT:** `git checkout 749c607 -- research/pinrun.py research/pindesk.py
watch_bot.ps1`, then replace the watchdog (stop watch_bot, run
`boot_all.ps1 -NoArms`) and relaunch the app.

---

# v-race-tie1 -- 2026-09-24 ~06:0xZ -- COIN RACE, LIVE penny test + every race arm: real legs are scored from Kalshi's own result; a tie pays 50c to both tied coins and counts as a LOSS for the stop rail; an unscorable race stays pending

**Why.** `winner_from` was a bare argmax. On the 2026-09-23 07:15 tie (XRP
-0.150% vs HYPE -0.151% on Kalshi's 3-decimal numbers, 0.09 bp on our index)
Kalshi paid 50c to both sides: the real legs lost -$0.9535, the bot booked
+$0.0465, released the rolling stake as a win, and the stop-on-first-loss
rail -- the safety of the money test -- did not fire. Paper arms booked
+$7.50 on the same race where the ledger says -$118 at their size. Also, a
race the index could not score was dropped forever (real legs never scored,
stake never released): one real leg (09-22 07:59Z, XRP YES 98c) is still
unscored in the penny log.

**What it does now (research/pinracearm.py, VERSION 2026-09-24-tie1):**
- `winner_from(scores, tie_bp)` -> (winner, is_tie, gap_bp); tie = top two
  equal after `round(pct, 3)`, Kalshi's rule. `leg_value` pays 1/k to YES on
  each of k tied coins, NO gets the complement.
- Real legs are scored the moment every real ticker has a row in
  `results/kalshi_ledger.json` (pinledgerd refreshes every 60 s): `value`
  100/0/50. Until then the race is PENDING (stake held). After 15 min with
  rows missing: index fallback if the top-two gap >= 0.75 bp, otherwise
  `unscored_tie_suspect` -- pending for the life of the process, stake held.
- A tie on a real leg is a loss: `tie` record with its dollars, and the halt
  message says TIE. Rolling stake is released only on a scored result.
- Entry rules, sizes, prices, timing untouched.

Self-test 181 -> 213 checks, green plain and under the penny bot's exact
argv (and the z3 / gap075 / raceedge0 argvs); six mutation reverts each fail
the suite (tie-as-win 7 FAILs, no-wait 8, drop-unscorable 2, scored-before-
pass 1, release-while-pending 5, exact-draw-only 1). The 09-23 race is
replayed from planted numbers and the ledger's verbatim rows: -$0.9535, two
`tie` records, halt fires, stake released once. Live smoke on the real feed
through the `unscored` path clean.

**REVERT:** `git checkout f632e12 -- research/pinracearm.py`, then restart
the penny bot with the argv in HANDOFF.md (the one in the process table).

---

# v-lateadd-fix -- 2026-09-24 04:21Z (pid 2554960, code_sha 11ec840dce4f) -- LIVE: the early-leg gates are back; a late add can no longer be widened; the add only relabels inside its window

**A REGRESSION, LIVE FOR 73 MINUTES (03:31Z-04:21Z), FOUND BY THE AUDIT.**
v-lateadd's cap block was inserted between `sig["take_n"]` and the early-leg
gates, and its `if` body swallowed them: `early_cheap` (the 95c floor),
`early_dear` (97.5c), `early_wide` (10c early cap) and `staged_none` were
unreachable on the live bot and every synced arm, flag on or off. The suite
stayed green because those gates only had source-text checks. Money effect:
none observed (no early fill under 95c or over 97.5c in that window: 3 orders
since 03:31Z, all leg=full), but the 45 s leg ran without its floor.

**Fixes (all driven through the real loop now):**
1. The late-add block sits AFTER the early gates. A driven check buys a 96c
   early ask and refuses a 92c one as `early_cheap`, with the late add on
   and off.
2. `_stage46` clamps a `late_add` leg at REBUY_LATE_FRAC x SIZE and
   (1 + frac) x SIZE per market, so A35 depth sizing and the A48 late boost
   cannot widen it (the audit drove a 38.5 add to 115.5 contracts; a driven
   check now holds the add at half the first leg inside the boost window).
3. The relabel happens only inside REBUY_LATE_TAU: a 21-30 s re-buy on a
   full position that passes A23's band keeps leg `full` and its size (a
   driven null).

Also: `restart_bot.ps1` no longer dies when `Start-Transcript` collides
(6 of 27 watchdog restarts had aborted BEFORE starting the bot); the seven
`sigma_stress` paper arms are retired (RAM commit was 23.4 of 27.8 GB with 34
arms; the money bot shares that pool).

Known, accepted: a late add can fire in the SAME second as the entry at an
unchanged ask (a 1.5 x SIZE position at <=15 s, inside the MAX_PER_MARKET 2
and close-budget bounds). Self-test 1,117 checks green plain and under the
live argv.

**REVERT:** `git checkout 32cbd73 -- research/pinrun.py` reverts to
v-lateadd-live's code (WITH the regression -- do not); the real revert is to
drop the late add entirely: delete the `"--rebuy-late-tau", "15",
"--rebuy-late-frac", "0.5",` line in restart_bot.ps1 and run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`.

---

# v-lateadd-live -- 2026-09-24 03:31Z (pid 2560960, code_sha 04f8a96e34c7) -- LIVE: `--rebuy-late-tau 15 --rebuy-late-frac 0.5` on; `--hedge-slip 0.03 -> 0.10`

Operator, 2026-09-24: "Late-add: whatever makes the most money (accounting for
losses as well)... Hedge slips: again whatever makes the most."

**Late add (code: v-lateadd entry below).** Per-second rebuild of the 820
markets we held: a 0.5 x SIZE add at <=15 s when the ask is at or above
what we paid and every gate passes: +$95 over 16 days (141 fires), ONE
losing add (-$3.23), +$66 at 70% fills, +$59/+$56 by week at <=20 s. Does
it cause more or bigger losses? It cannot open a new losing market; it
enlarges a loss only when a position that qualifies at <=15 s then
reverses -- once in 141 on the record, bounded at 0.5 x SIZE x price
(~$40 at size 88). The close budget and MAX_PER_MARKET still apply (a
market built from two fills cannot add). Expected: +$3..6 per day.
`arm-lateadd-off` (live minus the flag) is the control.

**Hedge slip 0.10.** A taker IOC pays the resting ladder's prices, so the
limit only matters when the touch is gone: BTC 09-23 first try 21 of 88
filled at the 80c limit while 946 were shown at 77c, the rest a second
later at 87c; NEAR 09-21 40 of 81 at a 74c limit, the rest 3 s later at
90.5c. `arm-hedge-slip0` is -$32 vs live on the same markets over 76 h
(less slip = worse). Since the K1-K3 fix every live alarm (4 of 4) was a
real loss. Worst case on a false alarm: about 0.07 x size more than the
touch (~$6). Expected: +$5..10 per 16 days.

Self-test 1,111 checks green under this exact argv. versioncheck clean.

**REVERT:** in restart_bot.ps1 delete the `"--rebuy-late-tau", "15",
"--rebuy-late-frac", "0.5",` line and set `"--hedge-slip", "0.03",`, then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`
(the code path stays; the default is off). Set `arm-lateadd-off` back to
`arm-lateadd15` in sync_arms.ps1 if the arm should keep measuring it.

---

# v-lateadd -- 2026-09-24 ~03:3xZ -- CODE IN THE REPO, SHIPS OFF; PAPER ARM `arm-lateadd15` ONLY. The live bot (pid 2543296) is unchanged until its next restart, and the flag defaults to off even then.

**What it is.** `--rebuy-late-tau S --rebuy-late-frac F`: a position already
at SIZE may ADD F x SIZE inside the last S seconds when the ask is at or above
what we paid (-0.5c) and every entry gate passes (confidence, edge, ceiling,
spike, close budget, MAX_PER_MARKET). Today `rebuy_ok`'s band refuses every
not-cheaper re-buy on a full position -- right at 21-45 s (a discount is
adverse, A23's dose-response), wrong in the last 15 s where the money is.

**Evidence (results/cf_2026-09-24/cf_sim.py-style engine, 820 markets we
held, Kalshi's result, the tape's ask; upper bound -- fills ~70%):** add
0.5 x SIZE at <=15 s: +$95 over 16 days, 141 fires, ONE losing add (-$3.23),
+$66 at 70% fills; at <=20 s +$115 (4 losing adds, -$25); at <=10 s +$62 (0
losing adds); both weeks positive (+$59, +$56 at <=20 s). The engine did not
model the close budget or MAX_PER_MARKET (both apply live), so the arm's
job is to show how many adds actually clear them and at what price.

**Bar before live (pre-registered here, before any arm number is read):**
`arm-lateadd15` runs >= 48 h beside live; it must show >= 20 late_add legs,
NO late_add leg on a market that lost, and arm-minus-live on the SAME
markets >= +$10 (armh2h2.py, closes both were up). Any late_add on a loser
that live did not also lose -> off.

Self-test 1,111 checks green plain and under the live argv + the flags;
the driven check buys in full at 18 s and adds once at 15 s as leg
`late_add` at half size, the null refuses it as `rebuy_band` with the flag
off, and a collapsing position still hedges with the flag on.

**REVERT (code):** `git checkout 3b75f48 -- research/pinrun.py sync_arms.ps1`
(nothing live to restart; the live bot never ran it).

---

# v-cap20 -- 2026-09-24 02:22Z (pid 2543296) -- LIVE: the 10c edge cap applies only with MORE than 20 s left; early-leg price floor 0.90 -> 0.95

**Why.** Per-second rebuild of every market the bot has entered (820 with a
full picture: our-side belief from the index tape with pinrun's own maths,
the market's best ask from the ticker tape, Kalshi's ledger for the money;
scratchpad `cf_build.py` / `cf_sim.py`, copied to `results/cf_2026-09-24/`).
Re-implemented decision, NOT the certified backtest; rows are compared to
each other on one engine, never to Kalshi's number directly.

1. **The cap was refusing the pin edge.** A model-minus-market gap over 10c
   with 20 s or less left: 19 markets, 1 loser (-$2.12, a 10c NO), winners
   +$102 -- the market lagging a nearly-locked average, which is the whole
   strategy. With MORE than 20 s left the same gap lost 3 of 19 (BTC 09-23
   -$130.41, BNB 09-19 -$57.76, SOL 09-11 -$12.16): the market disagreeing
   about the future, and right. Same engine, whole record: cap at every tau
   +$500.70; cap only above 20 s +$633.37; both weeks improve (+$96, +$36).
   The v-nospike write-up counted a refusal as a lost MARKET; the bot in
   fact re-looks every second and buys once the gap closes, so the true
   give-up of the cap is small -- and the late-window part of it was pure
   give-up.
2. **Early floor 0.95.** First entries at 31-45 s priced under 95c: 19
   markets, 4 losers (-$197); at 95-98c: 226 markets, 3 losers, +$96 net.
   Same engine: +$664.97 with the 95c floor against +$633.37 -- it removes
   BTC 09-17 -$9.29, BTC 09-19 02:00 -$22.11, NEAR 09-21 -$19.72 and gives up
   ~$19 of small winners. Three events; the mechanism is the one above
   (cheap early = the market disagrees), and the leg is at 1/3 size.

**Measured and NOT changed:** (a) halving size at 21-30 s with a top-up at
<=20 s (the operator's idea) -- with the cap in place it is -$41 on the same
engine (-$21 and -$20 by week) and does not lower the worst loss further;
paper only. (b) Hedge trigger: on 820 positions, belief < 0.40 with the
current sizing is the best of {0.40..0.90} x {proportional, all-at-once} x
{drop-from-peak 0.1..0.5}; the +$190 the simulation shows over what actually
happened is the 09-19 bug day (blocked/false hedges, since fixed) -- no
change. (c) The spike gate adds only ~$5 on this engine but is the direct
defence for the BTC shape when the gap is under 10c; kept.

Self-test 1104 checks green plain and under the live argv; the new pure and
driven checks assert the 13c gap is refused at 26/21 s and bought at 20/8 s,
an UNKNOWN clock counts as early, and `EDGE_CAP_TAU None` restores the
v-nospike every-tau cap. Entry only; the hedge pass is above both gates
(source-order check unchanged).

**REVERT:** `git checkout f4b8f6d -- research/pinrun.py`, set
`"--early-min-price", "0.90",` in restart_bot.ps1, then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

---

# v-nospike -- 2026-09-24 ~02:0xZ -- LIVE: no spike entries, a 10c edge cap on every leg, hedge trigger 0.25 -> 0.40

**Built from the BTC 8:30 PM ET loss, KXBTC15M-26SEP232030-30, -$130.41 on
Kalshi's ledger -- the largest single loss in the bot's history.** The operator:
"Do everything you can to identify and anything you need to do to make this not
happen again." This overrides the 09-22 freeze (his words: "any rule can be
changed if you think another way is better").

**What happened (the bot's own per-second trajectory, v-traj1):** for 90 s the
market sat ON the strike (fair 0.2-0.6, a coin flip). tau 27: fair 0.196.
tau 26: 0.369. Then ONE index print landed $33 above the strike, fair read
0.99896, and within 100 ms the bot bought 88 at 87c and 88 more at 86c -- 176
contracts, $152 -- against a market that priced YES at 86c: a 13c
disagreement, the widest we take. One second later the print reversed (0.853),
two seconds later 0.374, and it settled NO. Belief fell under 0.40 at tau 22
with insurance at 64c and 1,344 on offer; the 0.25 trigger did not fire until
tau 17, when it cost 77-87c. The hedge covered 176 of 176, late: net -$130.41
against -$152 naked.

**Three changes, each measured on OUR OWN fills:**

1. **Spike gate.** Refuse an entry whose our-side confidence was under 0.90 at
   the previous index print (inside 5 s the cushion is locked prints, so the
   gate stands down). Today's trajectory log: 36 markets, 2 spike entries -- a
   DOGE win worth +$0.76 and this loss. Since the per-second belief log began
   (09-22 12Z): 72 entries, 2 spikes (+$1.17, -$130.41), 70 others +$112.07
   with one loser. A "hold 2 s at >= pin" rule would have refused 29 of 36 --
   the wrong fix; this refuses the JUMP, not the climb.
2. **Edge cap, every leg: refuse when the model beats the market by more than
   10c.** Whole live record, 824 markets: above 10c, 38 markets, 4 losers
   (-$202.45: DOGE -2.12, SOL -12.16, BNB -57.76, BTC -130.41), 34 winners
   (+$183.20) -- net +$19.24 to block, and a 10.5% loss rate against 2.5%.
   A50 capped the 45 s leg at 10c and left the main window open; the main
   window took this trade. Below 10c the gap is the edge and is untouched.
3. **--hedge-belief 0.25 -> 0.40.** On this market a 0.40 trigger fires at
   tau 22 at 64c: net about -$89 instead of -$130. The 0.25 came from
   hedgetune, which the 09-22 map showed priced on the recorder's receive
   time and bypassed PREREG_hedge's "not below 0.30"; its corrected table
   had 0.40 and 0.25 tied lifetime (+$46.87 vs +$44.79). Today breaks the tie.

**What they block:** ENTRIES only. No spike/edge-cap call exists above the
hedge pass (asserted by source position), and a driven test holds a collapsing
position with both gates on and still hedges. Nothing here can delay a hedge.

1,100 self-test checks green plain and under the new live argv; removing
either gate, or comparing the spike to the clock instead of the newest print,
each fails the suite. pinattrib (gate registry), versioncheck, shadow,
markers, barcheck clean.

**REVERT:** `git checkout 9aa5f13 -- research/pinrun.py research/pinattrib.py`,
set `"--hedge-belief", "0.25",` in restart_bot.ps1, then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

---

# v-traj1 -- 2026-09-23 ~06:2xZ -- LIVE: the bot records HOW a market looked on the way to a decision (logging only)

**Freeze-legal: logging and a paper-only flag. No live entry decision changes.**
Proven with the offline loop harness on old and new code across several worlds:
identical decision trail, identical POSTs, identical state.signals; the only
new record kinds are `traj`, `traj_blind` and the frozen-index witness.

1. **The trajectory (R4).** `_gate()` de-duplicates per (close, ticker, gate),
   so a market the bot evaluated ~5,500 times left a MEDIAN OF ONE refusal
   record -- which is why every "was there an earlier warning?" question in
   the 09-22 map came back underpowered. The bot now samples each watched
   market every 5 s out to tau 300 and EVERY SECOND inside 60 s, writing what
   it saw: fair, confidence, spot, strike, the cushion in remaining-window sd,
   our side's ask and size, the OTHER side's ask and size (what insurance
   would cost), book age, index age, and the gate that would have refused it
   -- the real gate, stamped by `_gate()` itself, not a mirror. Its own file
   `results/pintraj-live-<runid>.jsonl`, LIVE ONLY: a reviewer caught that 28
   pinrun processes would have written 1.6 GB/day, so paper arms count drops
   instead of writing (they still decide identically). Measured cost: ~0.6 MB
   per close, 4.4 ms per second for 11 markets, one held file handle flushed
   once a second (per-record open/close was 2.46 ms -- rejected).
2. **The frozen-index witness (K3b).** Tonight's DOGE close exposed that once
   a position is fully insured the hedge pass skips it BEFORE refreshing the
   belief, so the per-second record reprints a stale number and a genuinely
   frozen index would look identical to a healthy feed. Every held position
   now reports its own index age, insured or not, per leg, with the market's
   held/insured/naked counts. Removing the skip instead -- the obvious fix --
   re-buys the insurance every second (22 sends instead of 13); that was
   proven offline before anything was changed.
3. **`--doubt-mult` (R1), OFF in live and REFUSED with `--live`.** Size x1.5
   when the model's own confidence in the side we are buying was under 0.50 at
   a reading at least 5 s earlier in the same close (66 markets, 62 closes, 0
   money-losers, +$2.95/market against +$0.70 book-wide). `arm-doubt15` and
   `arm-doubt125` test it on paper; the bar is results/map_2026-09-22/
   signature/D_plan.md section 1. One boosted loss switches it off.

1,083 self-test checks green plain, under the live argv and under the arm's;
20 of 20 deliberate reverts fail; versioncheck, shadow, markers clean.

**REVERT:** `git checkout b366dbf -- research/pinrun.py` then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

---

# v-unidefer -- 2026-09-23 ~00:3xZ -- LIVE (SAFETY, during the freeze): the market-list refresh waits while a close is near

**Why now, mid-freeze: Kalshi degraded at 2026-09-23 00:2xZ and the loop was
freezing inside closes while holding.** v-instr1's own records, same run:
universe refresh median **3,227 ms**, worst **10,639 ms** (healthy median was
878 ms), **54 slow passes inside 45 s** of a close -- 6,344 ms at tau 21,
4,936 ms at tau 2 -- and a >500 ms stall inside 60 s on **17 of 17** closes.
The 11 GETs run in the trading thread, so those seconds are seconds in which
the bot can neither buy nor HEDGE. The freeze allows safety fixes; the
pre-registered R2 bar (20 of 100 closes with a >500 ms stall inside 45 s) was
already met 17/17 before this change.

**What it does differently:** `defer_universe()` -- while any watched market
is inside `UNI_NEAR_TAU_S = 60` s of its close, the refresh WAITS; it resumes
the moment the close passes, with `UNI_HARD_S = 300` s as a backstop so it can
never defer for ever. One `universe_deferred` record per wait (not per 20 Hz
pass), and the next `universe` record carries `deferred_s`.

**It blocks nothing and cannot delay a hedge.** The refresh already discards
markets closing more than 900 s out, so while one close is inside 60 s the
next close's markets (960 s away) were excluded anyway. The hedge pass gained
no condition; a self-test drives the REAL loop holding a position through a
deferral and it still hedges.

1,005 self-test checks green plain and under the live argv; disabling the
deferral fails 5 of them. versioncheck clean.

**REVERT:** `git checkout 5182c3f -- research/pinrun.py` then
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

---

# v-instr1 -- 2026-09-22 ~20:1xZ -- LIVE: the two invisible things get records (logging only)

**Freeze-legal: records only, no entry decision changes.** Proven, not
asserted: the offline loop harness run on old and new code over three worlds
(burner lockout, four coins spending the base budget, the live order path with
a collapse and a hedge) produces an IDENTICAL decision trail -- 15 decision
rows, same POST count, same state.signals. The only new record kinds are
`universe`, `loop` and the `close_budget_base` refusal.

1. **The silent refusal now writes one.** After every gate passed, a base-
   budget check dropped the third bet of a close with NO record of any kind:
   run 20260920T023207Z ended with `state.signals` 102 against 5 logged
   signals. It now writes `_gate("close_budget_base", ...)` with want, price,
   size, take_n, base, spent, tau (deduped per close+market+gate). Its bar:
   on the first run with an `end` record, signals == signal records + the
   undeduped close_summary counts of close_budget_base/early_cheap/early_dear/
   early_wide/staged_none/price_band. That identity fails by 97 on the old
   code, so the test can fail.
2. **The universe refresh is timed.** 11 sequential GETs (~1 s) run in the
   trading thread every 20 s with no condition on time-to-close: ~4.3% of
   every close's last 30 s buys nothing AND cannot hedge. Now `universe`
   (ms, n, got, watching, close_s, tau) per refresh, and a `loop` record
   whenever a pass exceeds 200 ms (budget 300 per close inside tau 60, 20
   outside; `close_summary` keeps the per-close maxima and counts, which no
   cap can eat). Bar: median universe.ms >= 500 AND >= 20 of 100 closes with
   a pass gap > 500 ms at tau <= 45 -> the stall is worth fixing (after the
   freeze, operator's call). Nothing is deferred and the hedge pass gained no
   condition; the `loop` write sits BELOW the hedge pass.

Also: `--attempts-on-send` exists but is OFF and is NOT in the live argv --
`arm-attempt-send` is the only bot running it. Two reviewer BLOCKERS were
fixed first: the record budget spent itself ~500 s before the window it
measures, and the flag as first built escalated a one-market lockout to the
whole close (reproduced, then fixed so both counters move together).

986 self-test checks green plain, under the live argv, and under the arm's.

**REVERT:** `git checkout 8bd1e51 -- research/pinrun.py research/pinattrib.py`
then `powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

---

# v-race-rolling -- 2026-09-22 ~16:1xZ -- LIVE (coin race penny test): the $20 cap bounds OPEN bets, and it runs a week

Not the pin bot. `pinracearm.py --live` relaunched with `--live-rolling-stake`
and `--minutes 10080` (was 1440); everything else as v-race30 (1 contract a
leg, inside 30 s, >= 90c, confirm-or-clock, STOPS DEAD on the first loss).

**Why:** the operator asked whether the coin race is tuned enough to raise the
bet. It is not known yet: since v-race30, 11 real races, 19 of 19 legs won,
+$0.58 -- and at ~98c one loss erases ~50 wins, so telling a winner from a
break-even needs ~160 loss-free races inside 30 s (map report 08). The test
could not get there: its $20 cap counted every bet it had EVER placed, so it
stopped itself at 11:59 ET with nothing open. Settled legs now give their
stake back to both caps (ours and pintake's MAX_RUN_STAKE), the release
pinrun already does (committed_for). Open exposure stays <= $20; the
first-loss halt still bounds total loss to one race.

**REVERT:** relaunch without `--live-rolling-stake` (argv in HANDOFF.md,
2026-09-22 section; add `--live-tau-max 30 --minutes 1440`).

---

# v-safety1 -- 2026-09-22 ~11:5xZ -- LIVE: the hedge can no longer be silenced by a crash, a halt or a frozen index

**Freeze-compliant:** bug/safety fixes and logging only. No flag added; no
ENTRY decision changes on a healthy loop. Built in a worktree, three
adversarial reviews, every fix with a self-test proven to fail when reverted
(12 reverted builds); 969 checks green plain AND under the live argv and all
26 arm argvs. Verified defects: results/map_2026-09-22/verify/K1-K3.

**What the bot now does differently:**
- **K1** an exception in the entry scan, the hedge body or risk_abort is
  recorded (`error`) and the loop continues; fills are registered for hedging
  and the close budget BEFORE any record formats them. A hedge-step error, or
  5 scan errors, stops new entries, drains (hedging still runs, 0.05 s loop),
  exits when flat, and watch_bot restarts it. Before: the process died holding
  (09-19 02:00 ET, -$66.34).
- **K2** `pintake.take(..., hedge=True)`: a pintake halt refuses entries but
  never a hedge. A hedge POST that provably never left the box is resent; an
  ambiguous one is counted covered (no double hedge).
- **K3** held market's index older than 2 s -> `hedge_blind(index_stale)` and
  belief = min(model, our side's best ASK); fresh index -> byte-identical.
- Paper arms no longer read the live day-loss file.
- Logging: `tau` + `budget_left` on every refusal/signal, `t_ms_decide` /
  `t_ms_send` on orders and hedges, one `hedge_quote` per held market per
  second (insurance ask, size, belief) -- the data FREEZE bars B3/B5 need.

**REVERT:** `git checkout b939501 -- research/pinrun.py research/pintake.py`
then `powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

---

# v-early-third -- 2026-09-22 11:42:12Z (07:42 ET restart, pid 2070976, SHA 1c89619) -- LIVE: the 45 s leg back to a third (--early-frac 1.0 -> 0.333)

The operator, after the project map: *"Cut it to a third but measure which
would have been the best idea in hindsight."* Nothing else changed.

**Evidence (Kalshi's ledger, results/PROJECT_MAP_2026-09-22.md, verified):**
since 09-17 13:05Z the 31-45 s leg's markets net -$57 to -$70, but the deficit
is one day (09-19) and mostly hedge failures/bugs on early positions; early
entries alone are ~break-even. Post-fix it earns +0.71c/contract (+$32 on 70
markets) vs +3.92c (+$82 on 36) for <=30 s buys, and it held 6 of the 8
losing markets since 09-19. It mostly ADDS markets (163 of 203 were never
offered at 90-98c later), so OFF would lose them; a third keeps them and cuts
the tail. Sign NOT established (bootstrap P(>=0) = 0.39). No pre-registered bar
existed for going back; this is the operator's call on a risk trade-off.

**Measuring the alternatives, as asked:** `arm-early-full` (--early-frac 1.0)
and `arm-early-off` run synced to live from this deploy; research/
earlyhindsight.py scores live-third vs full vs off from live fills. Compare
only on closes after this deploy.

**REVERT:** set `"--early-frac", "1.0",` in restart_bot.ps1 and run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

---

# v-race30 -- 2026-09-22 ~07:0xZ -- LIVE (coin race penny test): real bets only inside 30 s

**What it does differently:** `--live-tau-max 60 -> 30`. Nothing else.

**v-race90 below was partly WRONG and is corrected here.** Investigator 08
rebuilt the first loss from the tape to the millisecond: the book was not
stale -- the 93c was a ~150 ms spike and a faster maker picked our order off.
The REST re-read cannot stop that (its first live order: read 97c, filled
91c). And the 90c floor applies to the price we DECIDE on, not the fill, so
"never buys under 90c" was false. What the evidence does support: every race
loss since 09-21, real (2) and paper (2), came 40-60 s out; 0 of 88 paper
races with a 90c+ bet inside 30 s lost. Both real losses were at 40-41 s.
Paper matched real on win/loss 16 of 16, not on price.

**REVERT:** relaunch `pinracearm.py --live` with `--live-tau-max 60` (argv in
HANDOFF.md, 2026-09-22 section).

---

# v-race90 -- 2026-09-22 ~06:07Z -- LIVE (coin race penny test): 90c floor, and every send re-reads the book

Not the pin bot -- `pinrun --live` is untouched. This is `pinracearm.py --live`,
the one-contract coin race test, real money.

**What it does differently:** (1) it never buys under 90c (was 80c); (2) just
before every real order it GETs the market's book over REST and refuses if
the ask there is under 90c or more than 2c under the ask it decided on, or
if the read fails.

**Evidence -- our own fills, 2026-09-21, 15 races:** 24 legs filled at
94-98c, all 24 won; 2 legs filled at 85-86c, both lost (-$0.86, -$0.87).
The tape had rated sub-90c legs at 1.0-1.4% losing. The first loss was
DECIDED at 93c and FILLED at 85c: the race book may sit five minutes
unchanged (MAX_BOOK_AGE_MS) and a buy fills at anything at or under its
limit, so a collapsing price is bought, not refused -- a 90c floor alone
would not have stopped it; the fresh read does. Self-test replays both
losses (refused) and the 24 winners' prices (sent). Two losses is not a
loss RATE; the test still halts on its first loss.

**REVERT, copy-pasteable:**
`git checkout 02ffd18 -- research/pinracearm.py`, then stop the
`pinracearm.py --live` process and relaunch it with `--live-min-price 0.80`
(full argv in HANDOFF.md, 2026-09-22 section).

---

# v-hedge25 -- 2026-09-21 ~19:0xZ -- LIVE: the hedge trigger moves 60% -> 25%

The operator set the objective: *"It's not cutting losses that matters it's
losing the least amount of money."* And the task: *"tune it to catch the most
it can while having enough certainty to offset as much total losses as
possible."*

**REVERT:** set `"--hedge-belief", "0.60",` in `restart_bot.ps1` and run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

## The instrument -- `research/hedgetune.py`, new

Every earlier answer scored a trigger at the price available **at the alarm
second**. That is only right for an alarm already under the trigger when it
fired. Any lower trigger has to WAIT, and insurance gets dearer as confidence
falls -- which is precisely what A76 cost us today. Pricing a wait at the
pre-wait price flatters it by that whole amount.

So this rebuilds, for all 16 alarms with an entry signal: our **confidence
second by second** from the 1/sec index (`settlewin.partial` plus pinrun's own
`eff_strike`, `var_factor`, `conf_of` -- only the two live reads replaced),
and the **hedge price and depth second by second** from the ticker tape. Then
it buys at the first second confidence falls under the trigger, at the price
quoted then, capped by what was offered.

## The dial

| trigger | fires | real | right | the losses | false alarms | TOTAL |
|---|---|---|---|---|---|---|
| **<60% (what we ran)** | 14 | 8 | 57% | -$235.91 | -$134.13 | **-$370.05** |
| <40% | 11 | 8 | 73% | -$242.57 | -$79.02 | -$321.58 |
| **<25% (now live)** | 10 | 8 | 80% | -$276.86 | +$3.71 | **-$273.15** |
| <20% | 8 | 8 | 100% | -$276.94 | +$22.38 | -$254.56 |
| never hedge | 0 | - | - | -$346.78 | +$22.38 | -$324.40 |

**The 0.60 trigger was the worst of every option, including not hedging at
all.** It fires on 14 alarms of which 8 were real; the six false ones cost
$156. At 0.25 it still catches **all 8 real losses** -- not one is missed --
and pays for only two false alarms.

## Why 0.25 and not lower

0.20 and below have never once hedged a bet that went on to win (8 for 8) and
read better still. The **leave-one-out** decides it:

| trigger | worst drop-one, against never hedging |
|---|---|
| <60% | **-$79.30** |
| <30% | -$43.01 |
| **<25%** | **+$23.50** |

0.25 is the loosest trigger where dropping the single most influential alarm
STILL leaves hedging ahead. That is the most coverage the evidence supports,
which is exactly what was asked for.

## Left on the table, deliberately

Sizing to cover the money at risk instead of matching the position reads
**-$220.42** at this trigger, another $53, worst drop-one **+$47.79**. It
needs a new flag and does not go in the same change as this one.

---

# v-hedgelastweek -- 2026-09-21 ~17:5xZ -- LIVE: the hedge is last week's, exactly

The operator: *"make sure that my hedge right now is functioning just like it
did last week. The time were it was cutting them in half and even caused a
profit. I want that exact code as my hedge. The other stuff we changed that's
good stays, but for the hedge I want that one."*

**REVERT, copy-pasteable:** put `"--hedge-price", "0.60",` back into
`restart_bot.ps1`, then run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

## What changed

`--hedge-price 0.60` is REMOVED. With `--no-hedge-prop` from earlier today,
the hedge is now exactly what it was during the week he is describing: the
WHOLE position, at the alarm, with no price gate.

## He is right, and the start records prove it

Every hedge he remembers ran with `hedge_price: None`:

| hedge | unhedged | hedged | cut |
|---|---|---|---|
| BTC 09-14 | -$58.43 | -$34.26 | 41% |
| HYPE 09-14 | -$59.20 | -$29.90 | 49% |
| BNB 09-16 | -$0.98 | -$0.47 | 52% |
| DOGE 09-18 04:15Z | -$3.93 | **+$4.36** | a loss turned into a profit |

The flag was not added until the **2026-09-18 22:46Z** run, after all four.

## Every real-money alarm, replayed against the book at the alarm second

| policy | the 10 losses | 8 false alarms | total |
|---|---|---|---|
| never hedge | -$346.84 | +$22.38 | -$324.46 |
| **LAST WEEK (no price gate)** | **-$235.93** | -$109.38 | -$345.31 |
| with the 0.60 gate | -$280.70 | -$55.76 | -$336.46 |
| A76 proportional | -$246.54 | -$136.20 | -$382.74 |

**The trade-off, stated plainly so nobody is surprised later.** Last week's
rule cuts the LOSSES by **32%** against the gate's 19%, and would have made
today's NEAR **-$48.16 instead of -$74.25**. It costs $53 more on the false
alarms and is $9 worse on the 18-alarm total. The operator has chosen the
loss cut with those numbers in front of him. The total is dominated by two
false alarms on 09-19 and is not what he is optimising.

## What the gate was for, so it is not re-added blindly

It refuses a hedge when insurance is CHEAP -- when the market has not yet
agreed with our model. Of the nine hedges it blocks across the 18 alarms,
**six were false alarms** and it saved us on those. It also blocked today's,
**by one cent**: the NO was 39c against a 40c line.

The replacement is not a price line, it is telling a false alarm from a real
one. The false alarms cluster at 14, 18, 37 and 37c while the big real losses
sat at 44, 52 and 65c. That is being tested now and nothing goes back in
until it is.

## Kept from this week, because it is execution and not a gate

`--hedge-slip 0.03`, `--hedge-max-tries 30` and the 120-attempt cap stay. They
make the hedge order actually cross; last week's 5 tries left hedges unfilled.

---

# v-hedgefull -- 2026-09-21 ~17:0xZ -- LIVE: A76 PROPORTIONAL HEDGING IS OFF

Flag added: `--no-hedge-prop`.

**REVERT, copy-pasteable:** delete the `"--no-hedge-prop",` line from
`restart_bot.ps1`, then run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

## What the bot now does differently

It hedges the WHOLE position the moment belief crosses `--hedge-belief` 0.60,
instead of buying nothing above 40% belief, half at 40%, and topping up later.

## Why -- every real-money alarm we have, replayed against the book

A76 fired for the first time today on `KXNEAR15M-26SEP211245-45` and cost
$59.09. All 18 lifetime alarms with a settlement were replayed against the
**order book at the alarm second**, read from the ticker tape, with every
hedge sized by what was actually offered at that second:

| policy | total over 18 alarms |
|---|---|
| never hedge at all | -$324.46 |
| hedge the whole position at the alarm, no price gate | -$345.31 |
| ...and skip insurance over 60c | -$271.42 |
| ...and skip insurance over 70c | **-$269.10** |
| cover the whole money at risk | -$319.24 |
| **A76 proportional, as deployed** | **-$382.74** |

**A76 is the worst of every policy tested** -- $58 worse than never hedging
and $113 worse than hedging in full at the alarm. The mechanism is not
subtle: the price of insurance tracks the belief, so waiting for belief to
fall guarantees paying up. Today the NO was **39c with 44 contracts offered**
at the alarm second. A76 bought nothing, then paid **70c** eleven seconds
later and **90.5c** three seconds after that, to protect contracts bought at
91.1c. That last leg could never have paid for itself.

`--hedge-price 0.60` is unchanged and still gates the normal path, which is
what the 60c row above measures.

## What was tested and REJECTED, so it is not re-proposed

**Sizing the hedge to cover the whole loss** -- the operator has asked for
this repeatedly and it is right in principle. Two walls, both measured:

* **Depth.** Covering the money needs `risk/(1-price)` contracts: 121 today
  against 44 offered, and short of depth on **9 of 18** alarms, once needing
  1,151 against 3 offered.
* **False alarms.** Where the depth did exist and the bet then WON, full
  cover turned +$5.73 into -$45.66. Across all 18 it is -$319.24, no better
  than 1x.

**Oversizing** reads spectacularly in-sample (6x the position = -$84.80) and
is fitted: chosen on the first nine alarms it **loses $84** on the last nine.
The reverse split chooses 1x at 0.70 and gains $52. Only the 1x rule survives
both directions.

## The bar

Below 40% belief the bet lost **6 times in 7**, so waiting is not information,
it is paying more for the same insurance. If the next 10 alarms under
full-at-alarm hedging are still net negative against never hedging, then
hedging itself goes, not the sizing. `arm-nohedge` answers that without risk.

---

# v-nocap -- 2026-09-20 -- LIVE: the 97.5c early-leg ceiling is REMOVED, hours after it shipped

The operator: *"I actually really want to keep the 45 normal"* and *"If you
think dropping sweep cap makes more do it. I just want the most money."*

## The measurement that killed it

The 45-second leg is not the risky leg. It is the LOW-MARGIN leg, and its
loss rate is BETTER than the main window's:

| leg | markets | contracts | avg paid | money | c/contract | **loss rate** |
|---|---|---|---|---|---|---|
| 45s early | 136 | 8,671 | 96.87c | +$110.67 | 1.28c | **1.5%** |
| main window | 515 | 21,431 | 95.45c | +$441.53 | 2.06c | 2.5% |

Two losing markets in 136, and the hedge turned one of them into **+$4.36**.

The ceiling would have touched **51% of its fills**. The case for it was that
the blocked budget would flow into the 5.6c-a-contract last-ten-seconds
window. **That thesis is now measured and it is FALSE:**

| window | fills | avg filled | avg our bet | we get |
|---|---|---|---|---|
| last 10s | 50 | 62.6 | 65.8 | 95% |
| 11-30s | 225 | 62.4 | 75.8 | 82% |
| 31-45s | 140 | 64.4 | 93.4 | **69%** |

In every window we already fill less than we ask for, and the shortfall grows
with our bet. **There is nowhere for the budget to go** -- the book in the
good window is thinner than we have grown. Blocking the early leg would not
have moved money to a better window; it would simply have been less trading.

`--early-max-price` stays in the code for a paper arm to test properly.

## The bigger thing this turned up

Our bet has outgrown the window that pays best. At 31-45s we fill 69% of what
we ask for; the last ten seconds -- 5.6c a contract, zero losing closes in 71
-- is the hardest place to put size. This is the same finding as "a bigger
bet does not earn more" (correlation -0.05 over six days) arriving from a
different direction, and it is an argument for a SMALLER bet, not a bigger
one. Not acted on; raised for the operator.

## Also confirmed, no change needed

**`depth_floor` is not costing us anything.** It fired 886 times, which
looked like the biggest gate in the bot. Of the 774 that fired under the
live `--min-fill-frac 0`, **every single one had under ONE contract on
offer** (median 0.29). The floor is already 1 contract and the bot already
takes whatever is there. The operator asked "we should be buying 20 if
that's all that's available" -- we already do.

---

# v-earlycap -- 2026-09-20 -- LIVE: a 97.5c ceiling on the 45-second leg, and the loss cap is a DAY not a run

Two changes, both on the operator's word: *"Sure cut to 97.5 I like that. The
whole point is better pricing so that's good"* and *"Yes loss cap change"*.

## A78 -- `--early-max-price 0.975`

The 31-45 s early leg refuses an ask above 97.5c. Measured, live fills:

| window | c/contract | losing closes |
|---|---|---|
| 31-45 s (the early leg) | **1.14c** | 2 of 99 |
| 16-30 s | 1.22c | |
| 6-10 s | **5.63c** | **0 of 71** |

Above 97.5c the early leg risks 98c to make 1.8c, fifteen seconds before the
information the strategy rests on arrives. That is exactly the fill that cost
**-$107.95**: `KXBTC15M-26SEP191600-00`, NO at 98c at tau 45, while the same
model sixteen seconds later said **YES at 99.79%** with YES offered at 92.6c.

**What it blocks:** early fills above 97.5c. It cannot touch the main window
(that leg is `full`), it cannot touch a hedge, and at the shipped default of
1.0 it blocks nothing -- the flag is what turns it on. Refusals log as
`early_dear`, registered in `pinattrib.py` so the gate report can score it.

## A79 -- the loss cap survives restarts

`--loss-cap 200` was **$200 PER RUN**. 2026-09-19 had **thirteen runs**, each
starting with a fresh $200 of permission, and the day reached **-$223.46**. A
cap that resets whenever the watchdog restarts the bot is not a cap.

`results/pinrun-dayloss.json` now holds the ET day's realised total, written
on every LIVE settlement before the log line. `risk_abort` compares the DAY
first and names it. Seeded at deploy from Kalshi's own books: 2026-09-20 was
+$26.88 over 10 markets, so the full $200 of room was intact.

Paper arms never touch the file. A new ET day (04:00Z) starts clean. Wins
count, so a profitable day can never halt on it. A NaN or infinity is refused
on the way in AND on the way out -- a poisoned total would have made every
comparison False for ever, which is a cap that silently stops being one.

## Also in this deploy

- The self-test check `index("book.depth") > index('rec("signal"') - 4000` was
  a character budget standing in for "the depth read is not on the 20 Hz
  path". Adding the A78 gate broke it even though the gate sits AFTER the
  read and cannot make it run more often. Replaced with the real property:
  the read must come after the `confidence` and `no_offer` gates and before
  the signal record.

## Revert

```powershell
# drop the ceiling: remove "--early-max-price", "0.975", from restart_bot.ps1
# drop the day cap: git revert the A79 commit (it has no flag)
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

---

# v-noboost -- 2026-09-20 -- LIVE: the 90-94c 1.5x boost is removed, on its own pre-registered bar

`--band-mult 0.90 0.94 1.5` (A53, v-bands, live since 09-18 22:46Z) shipped
with this bar written at deploy: **"revert at the FIRST loss on a boosted fill
in the first 20 boosted closes; at 20 clean, raise to 2.0."**

The first boosted loss came on the **third** boosted close:
`KXBNB15M-26SEP191230-30`, -$61.75, where the 1.5x multiplied the order into
83 contracts on a level that held 23. `band_boost_off` fired at
2026-09-19T16:30:20Z, as designed -- **but the switch lives in process memory
and every restart re-armed it.** The bot has restarted eight times since.

Lifetime, live fills: **3 boosts, 92 boosted contracts, +$5.28, 1 losing
close.** The bar is met. The flag goes. This is not a judgement about the
90-94c band -- it is the best band we have (70 closes, 1 loss, 6.4c a
contract) -- it is the bot keeping a promise it wrote down before the data
came in.

Restore: put `"--band-mult", "0.90", "0.94", "1.5",` back in `restart_bot.ps1`
and restart. A persistent off-switch would be the right way to bring it back.

## Also corrected here

v-hedgefill's DEPLOY block says `--hedge-slip` went live at 21:58:25Z. The
21:58 restart shipped the A70 CODE with the flag at its 0.0 default; the flag
itself first appears in a `start` record at **2026-09-19T22:50:22Z**. So
`--hedge-slip 0.03` has been live since 22:50Z, not 21:58Z.

---

# v-proportion -- 2026-09-20 -- LIVE: hedge in proportion to conviction, and a quarter off the bet

**DEPLOYED 2026-09-20 05:46:57Z (01:46 ET), pid 1412748, SHA `0061111`.** First autosize: 20 -> 70 contracts at the $825.04 bank (was 93 at brake 3.00). Start record: hedge_prop True, full 0.20, half 0.40. One live process, no halt.

**On the operator's word.** On the hedge: *"Sure on
proportion but make sure if it starts at half then drops below 20 you buy the
rest of the hedge."* On size: *"Make the bet size only a quarter smaller not
half then as proportional."*

## Why

Every alarm the bot has ever raised (18) was rebuilt second-by-second from
the raw CF Benchmarks index. **Nothing visible at the alarm second separates
a real collapse from a false alarm** -- crossing depth, market-wide or not,
belief level, seconds left: every one overlaps. The information arrives
1-10 s later, and on a real collapse the other side is at 99c by then
(trade tape: 58c -> 99c in 5 s on BTC 09-14; 51c -> 87c on HYPE 09-14).
So a confirmation delay is +$37 across everything and **-$79 with the
09-19 23:45 close removed** -- its whole benefit is one close. A hedge
cannot be made rarer without making it useless. It can be made SMALLER
where the model is least sure.

Under the current rules (`--hedge-price 0.60` since 09-18) the hedge is **9
saves (+$112.86) to 2 false alarms (-$116.87)**. Both false alarms were one
close, hedged in FULL at 27% and 50% belief -- a coin flip locked in at
46c -- on 104-contract positions, the largest ever held. Full hedges under
20% belief have been right every time.

Two corrections to earlier reporting, same day: `KXBTC15M-26SEP172115-15`
was a REAL loss (the bot restarted holding it and never wrote a settlement),
not a false alarm; and five of the seven lifetime false alarms fired under
the old 0.80 threshold and are already blocked by `--hedge-price 0.60`.

## A76 -- the rule

Share of the position that should carry a hedge leg:

| belief in our side | hedged |
|---|---|
| at or under **20%** | all of it |
| at or under **40%** | half |
| above 40% | none -- a coin flip is not a collapse |

**The top-up (the operator's condition):** the hedge tracks a TARGET against
what is already covered. A position half-hedged at 30% whose belief falls to
15% buys the other half. A position whose belief recovers is never sold
down.

On tonight's two: XRP 104 -> 52 contracts, HYPE 104 -> 0. On the nine real
losses: three at 52-56% belief would have gone unhedged (~$32 of saves) and
two at 21-24% would have been halved (~$16). Net about +$40 better than the
current rule on the same 15 clusters that produced it. **Below the
30-cluster floor; the operator chose it knowing that.**

What it blocks, per the 09-19 rule: the hedge entirely between 40% and 60%
belief, and half of it between 20% and 40%. `hedge_want()` can never return
more than the contracts still uncovered. `--no-hedge-prop` restores today's
all-or-nothing; `--hedge-prop-full` / `--hedge-prop-half` move the bands.

## The bet: `--bank-brake 3.00 -> 4.00`

Three quarters of the bet: ~69 contracts at the $821 bank instead of ~93.
Size has not been earning more (no correlation between size and daily money
-- the price paid rose with it) and the cheap end of the book has halved,
so a big order walks further up the ladder for less. The ratio stays the
brake.

## Evidence

- Self-test: A76 driven by tonight's real numbers (104 @ 0.27326 -> 52; 104
  @ 0.50066 -> 0), the top-up step by step (30% -> 52, then 15% -> the other
  52, then nothing), the no-sell rule (recovery -> 0, never negative), the
  exposure bound (never more than uncovered), garbage in -> 0 not raise (the
  hedge pass has no try/except), and `--no-hedge-prop` = today exactly.
  Structural: an idle second `continue`s BEFORE a try is counted; the alarm
  is keyed on its own set; live AND paper judge "done" against the uncovered
  count so a half hedge stays open for its top-up.
- Startup path run with the exact deploy flag list, paper.

## Revert

```powershell
# hedge back to all-or-nothing, bet back to 3.00: edit restart_bot.ps1
#   add   "--no-hedge-prop",
#   set   "--bank-brake", "3.00",
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

---

# v-settledonly -- 2026-09-19 -- LIVE: an unsettled bet is no longer counted as a loss

**The operator, and the log agreed with him word for word:** *"I don't know
why it seems like it was calculating the total lost before the bet has
settled. If it was seeing a current bet is down 100 then adding that to the
loss total that is wrong. You should only wait for the bet to end and be
finalized before you count it because that's only the true total."*

## What was wrong

`risk_abort`'s forward-looking bound was
`realised - open_cost - one more contract`, and **`open_cost` is the full
PURCHASE PRICE of everything open, not its mark to market.** So every held
bet was written off as a TOTAL loss the instant it filled -- on a strategy
that wins about 97 times in 100. Real pause records:

```
pause: loss bound: realised $+43.56 with $145.00 still open
pause: loss bound: realised  $+0.00 with $101.15 still open
pause: loss bound: realised $+31.19 with $210.06 still open
```

**It paused the bot while the run was UP $43.56.**

## And it cost no trades -- CURRENT_STATE was wrong about that

Measured across every live run: **28 pause->resume spans, and in ZERO of
them did the bot signal or send an order.** The operator said the cap had not
cost us bets and he was right. `CURRENT_STATE.md` claimed it "blocks NEW
trades for the rest of that close"; that claim was never measured and is
withdrawn.

What it really was: noise in the log, sitting on the same code path whose
`continue` skipped a hedge and cost **$107.95** earlier the same day.

## What it is now

The loss brake is the SETTLED check that already sat one line above it:
`realised <= loss_abort`. Nothing replaced the forward bound.

**WHAT THAT GIVES UP, AND THE OPERATOR HAS BEEN TOLD THE NUMBER.** The run
stops on $200 of FINALISED losses, and whatever is in flight at that moment
is on top. In flight is bounded elsewhere and always was -- the open cap
(`max_positions x SIZE` contracts), the stake cap, and the per-close budget.
At 98 contracts that is **$200 settled plus at most 3 x 98 x $0.98 = $288
open, so about $488 worst case against the old ~$200.**

The old comment defended the bound by saying a settled-only abort "is inert
entirely if the settlement reader is failing". That hole is real and is now
covered properly by A71's `RECONCILE_FAIL_HALT`, which halts on the reader
being broken rather than guessing at losses that have not happened.

## Evidence

- **849 self-test checks pass.** The A73 checks are driven by the FIVE REAL
  (realised, open) pairs from the live log, at the size the bot was actually
  running; each must now be a no-op, and each must come back under the flag.
- `PLANTED: $200.00 of FINALISED losses still halts the run` -- the brake
  that now carries the whole job is asserted to fire, and asserted not to
  fire a cent under.
- The loss bound is asserted to still sit BELOW the hedge pass (A69).
- Startup path run with the exact deploy flag list, paper: SELF-TEST PASSED,
  exit 0.

## Revert, copy-pasteable

Add the flag to `restart_bot.ps1` -- no code change needed:

```
"--loss-bound-open",
```

or revert the commit:

```powershell
cd C:\kals-repo
git revert --no-edit <SHA>
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

---

# v-hedgefill -- 2026-09-19 -- LIVE: the hedge could not fill, and paper could not hedge at all

**Deployed by this session on the operator's instruction: *"I'm not
restarting for you you just do it and stop asking me to"* and, on
`--hedge-slip`, *"Yes Turn the thing you want to change on."*** Deploy time,
pid and SHA are recorded in the DEPLOY block at the end of this entry.

`--hedge-slip 0.03` is now passed by `restart_bot.ps1`. A71 is code, not a
flag, so it went live with the same restart.

**`--loss-cap 200` was NOT changed.** It is what the operator asked for
("Cap losses at 200, keep bet size") and he did not answer the question about
raising it, so it stays. A69 already made the pause safe -- the hedge runs
regardless of it.

## A71.1 -- every paper arm has been an unhedged bot

The hedge pass skips any position missing from `hedge_meta`, and `hedge_meta`
was written at two sites, both live-only. A paper position never had a
strike, so its belief was never computed, so the alarm never fired.

**Measured: the five paper arms running on 09-19 logged 151 signals between
them, ZERO `hedge_alarm` and ZERO `hedge` records. Live on the same markets:
2 alarms, 8 hedges, 2 panics.**

A filled hedge turns a -73c..-96c loss into -26.9c per contract. So every
arm-vs-live head to head has compared a bot that eats its losses whole
against one that insures them. **Arm numbers on losing closes are not
comparable before this SHA.** It also means no hedge change was ever
testable without real money -- A62, A69 and A70 all went straight to live.

## A71.2 -- an ENTRY rail could permanently disable a hedge

The hedge's per-close cap read `attempts`, which the entry path increments,
against `MAX_ATTEMPTS_PER_CLOSE` = 24. Twelve coins settle on the same
quarter hour, so the bot's own buying could spend the budget and then refuse
-- permanently, via `hedged.add()` -- to insure a position already held.
The hedge now counts its own sends against `MAX_HEDGE_ATTEMPTS_PER_CLOSE`
= 120, above anything ordinary hedging can reach (3 positions x 30 tries,
one per second).

## A71.3 -- three hedge skips were silent

No `hedge_meta`, no sigma, no fair value: all skipped the hedge writing
nothing. A feed stutter during a collapse looked exactly like the A69 pause
bug. They now write `hedge_blind`, deduped per (position, reason).

## A71.4 -- bookkeeping above the hedge could kill the process

`report_closes()` and `reconcile()` run before the hedge pass and neither was
wrapped. A69 moved the hedge above the risk check because a `continue` there
cost $107.95; an exception above it ends the process holding a position,
which is the $66.34 loss from the same day. Both are now guarded. A
persistent reconcile failure still halts -- a frozen ledger makes every brake
in `risk_abort` inert -- but it halts IN `risk_abort`, below the hedge pass,
so the last iteration insures what is open first.

## A70 -- `--hedge-slip` (ships at 0.0, OFF)

The entry path has sent a limit above the touch and sized from the ladder
since A35. The hedge sent the ask it saw and the touch size -- one stale
level, priced to the tick -- so when the market moved, which is when a hedge
is needed, the IOC crossed nothing.

**All 29 live hedge attempts, the failures:**

| ticker | tau | asked | touch | filled |
|---|---|---|---|---|
| KXBTC15M-26SEP172115-15 | 36 | 99 | 283.8 | **0** |
| KXBTC15M-26SEP172115-15 | 35 | 99 | 7419.0 | **0** |
| KXBNB15M-26SEP190145-45 | 20 | 76 | 96.0 | **0** |
| KXBNB15M-26SEP190145-45 | 19 | 25 | 25.0 | **1** |
| KXBNB15M-26SEP191230-30 | 11 | 28 | 28.0 | **1** |

Ten of twenty-nine filled nothing or one contract against a book displaying
everything we asked for. The 01:45 BNB close is the **only escape failure in
the project's history** (-$57.76): A62 removed the FILTERS that blocked it
and it still did not fill, because nothing had fixed the EXECUTION.

`hedge_depth()` can only return MORE than the touch, so no hedge that fills
today stops filling; the ladder's contribution is capped at the contracts
still unhedged, past which a leg is naked (A63). `hedge_vwap()` makes a paper
arm pay the ladder average, not the touch.

## Evidence

- **832 self-test checks pass, 66 new.** `shadow.py` and `markers.py` clean.
  `versioncheck.py` clean.
- The launcher's exact flag list **plus `--hedge-slip 0.03`** was run through
  the startup path in paper before commit -- the check that has stopped this
  bot booting five times.
- Fill counts are from live fills only (rule 5). No replay was used.

## Revert, copy-pasteable

```powershell
cd C:\kals-repo
git revert --no-edit 1bd47c9
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

A70 alone is off by default; simply do not pass `--hedge-slip`. A71 has no
flag -- reverting the commit is the way back.

---

# v-taper -- 2026-09-19 ~13:2xZ -- LIVE: buy LESS as the price gets worse (A67), and a bounded bet on the side that is now winning (A68)

Both came out of `KXBNB15M-26SEP191230-30`, which cost **$61.75**.

## A67 `--no-taper` (the taper is ON)

The bot signalled that close at **91.5c** and the 82.8 contracts it got cost
an average of **97.27c**. A35 sized the order from `buyable()` -- every
contract under the 98c sweep limit -- and 11,937 were. Only **23** of them
were at 91.5c.

A35's own comment says why it thought that was safe: *"every extra contract
is already gate-approved."* True and not sufficient. 91.5c clears the gate by
7.8c; 98c clears it by 1.7c. Buying the same quantity of each treats a fifth
of the edge as the whole of it.

Now each price level is weighted by how much of the touch's edge survives
there -- full size at the best price, `size x (edge here / edge at touch)`
above it, nothing once the edge is gone. **On that exact book it asks for 47
instead of 114.**

`--taper-floor FRAC` additionally refuses any level worth less than FRAC of
the touch's edge (default 0.0 = take them, in proportion).

## A68 `--rebuy-mult` (ships at 1.0)

Operator: *"at 15% confidence if our confidence is accurate shouldn't we have
known it's 100% flipping ... even extra than the hedge."*

**Measured, live fills only: every market whose belief fell under the 40%
panic line went on to lose. 6 of 6.** The model is CONSERVATIVE down there --
at 0-5% belief it implies ~98% should lose and 100% did. Above 60% belief 0
of 4 lost, so a mild wobble does recover and this must not fire on one.

So while belief is at or under the panic line, more of the side we hedged
INTO is an ordinary bet at 85c-or-better odds, **capped at 1.0x the contracts
held on the losing side**.

**THE TAIL, STATED IN ADVANCE.** On the BNB close: +$19 expected, and **-$51
worse than the hedge alone** in the ~15% case where it comes back. That is
the trade. A63 was refused for having no cap at all (it would have bought 138
more and taken the worst case from +$3 to -$134); the bet was never the
problem, the size was. n = 6 closes, so the multiple ships at 1.0 and the
caution goes into the size rather than into refusing.

## Evidence and revert

Startup path run with the launcher's exact flag list, paper, `--minutes
0.35`: SELF-TEST PASSED, clean stderr. New checks assert the taper against
the real BNB book and the cap against the real contract counts.

- taper off: add `"--no-taper"` to `restart_bot.ps1`.
- the extra bet off: add `"--rebuy-mult", "0"`.
- both are code-default ON, so reverting the commit reverts them.

---

# v-mirror -- 2026-09-19 12:26:03Z -- LIVE: the bot publishes its contract size so paper arms trade proportionally

SHA: see `git log --oneline -1` at deploy (A66 commit "A66: paper arms trade
the size LIVE trades, and the self-test can no longer forge it").

## What the bot now does differently

On every autosize it writes `results/pinrun-live-size.json`. **Nothing about
its own trading changes** -- no gate, no price, no size, no rail. The file is
write-only from live's point of view; only paper arms read it.

## Why

Paper arms were pinned at 20 contracts while live ran 109. Zero autosize
records across all 43 arms since 2026-09-14, because `read_bank()` needs a
key a paper arm does not have and must never be given. So every arm's dollar
figure was measured at a stake that never faced live's depth.

## Evidence

Measured, not modelled: 0 autosize records in 43 arm logs before; 62 records
reading "mirroring live size 110" after `restart_arms.ps1`. Live's own first
autosize on this version wrote the file at 12:26:04Z with size 110, bank
$970.58.

## The bug this shipped with, caught in paper within two minutes

The startup self-test drives `autosize_tick` with a fake $60 bank and
published `{"size": 7.0}` into the real mirror; 36 arms then sized themselves
to SEVEN. Same shape as the 2026-09-14 high-water-mark outage. `SIZE_MIRROR`
is now sandboxed for the whole self-test, with a check that a pathless
`publish_size()` leaves the real file byte-identical. **No real money was
involved at any point** -- live neither reads the file nor changes behaviour
because of it.

## Revert

`restart_bot.ps1` needs no change -- there is no flag. To stop arms copying
live, add `"--no-size-mirror"` to the arm launchers (`start_sigma.ps1`,
`start_bands.ps1`, `boot_all.ps1`), or delete
`results/pinrun-live-size.json` and arms fall back to `--size` within the
hour. To revert the code: `git revert 277be1f`.

---

# v-cap200 -- 2026-09-19 ~03:1xZ -- LIVE: a hard $200 loss cap; the bet size is UNCHANGED

Operator, immediately after depositing: *"Cap losses at 200, keep bet size."*
Bank went $674 -> **$927.62**.

## 1. `--bank-brake` STAYS AT 3.00 -- the size ratio does not move

**CORRECTED 2026-09-19 03:3xZ, in the operator's own words:** *"Wait why that
seemed perfectly fine I want the same size ratio just after $200 in losses
brake."*

This entry first shipped `--bank-brake` 3.00 -> 4.08, which cut the bet from
**105 contracts to 77** at the $928 bank. That was a size change he did not
ask for -- "keep bet size" meant keep the RATIO, and the ratio is the brake.
It was live for one close (03:30:58Z -> 03:3xZ, size 77, no fills) and is
reverted. The bet is 105 contracts again and the bank covers a bad close
**3.0x**.

What the deposit buys is unchanged either way: the **close budget** rises with
the bank at any brake, and that is what `close_budget` was refusing 423
markets for.

## 2. AMENDMENT 65: `--loss-cap 200`

The loss abort has always been DERIVED -- `-2 x SIZE x MAX_PER_CLOSE`, a band
that survives two worst closes -- so it **grew with the bank**. It had already
reached **-$420** at 105 contracts, and nothing let the operator say "whatever
the arithmetic thinks, stop at two hundred dollars".

`abort_for()` now returns the TIGHTER of the band and the cap:

| SIZE | derived band | with a $200 cap |
|---|---|---|
| 105 | -$420 | **-$200** |
| 77 | -$308 | **-$200** |
| 20 | -$80 | -$80 (the band is tighter; a cap never RAISES the limit) |

**It is re-applied on every autosize**, not once at start-up. A cap applied
once is undone the next time the bank moves -- which is precisely how the old
one-way ratchet let the stop follow the bank up and never come back down.

A stray minus sign on the flag is ignored: the cap is a magnitude, so
`--loss-cap -200` and `--loss-cap 200` mean the same thing and neither can
turn a cap into a licence.

## What the cap can and cannot do

`LOSS_ABORT` is a **running-total** stop: once the run's settled P&L reaches
-$200 every further buy is refused. It is not a per-close stop and cannot be
one -- at 105 contracts a close holding all three legs has $309 at stake, so
one catastrophic close can pass straight through $200. `--max-losses 2` is the
brake that actually bounds that, and it is unchanged.

## Revert

`restart_bot.ps1`: delete `"--loss-cap", "200"` for the derived band
(-$630 at 105 contracts).

---

# v-late15 -- 2026-09-19 ~02:5xZ -- LIVE: the extra BUDGET reaches 15 s while the 1.5x boost stays at 10

Operator, on being shown that 423 markets were refused for `close_budget`:
*"Those sound like good trades why refuse them."* Then: *"Then increase to
15 seconds if it means better cheaper buys."*

## Why they were refused, and it is not a shortage

On the **97 closes where the budget actually ran out**:

| | |
|---|---|
| budget spent at MORE than 15 s left | **75%** of fills, median **97.6c** |
| budget spent at 15 s or less | 25% of fills, median 96.0c |
| when the refusals landed | median **21 s**; **38% inside 15 s** |

**We were spending three quarters of each close's budget early at 97.6c --
worth about 2.2c a contract -- and then refusing the cheaper trades later
because it was gone.** Not a budget shortage: the wrong trades first.

## The change

`--late-tau` was doing two unrelated jobs:

- **when an order may be 1.5x SIZE** (A48) -- extra RISK, on the bets with
  the least time to recover. Wants a TIGHT window. **Stays at 10 s.**
- **when a close may spend an extra bet of budget** (A59) -- not extra risk
  at all, only permission to spend what the close was already allowed.
  Wants a WIDE one. **Now 15 s, via `--late-extra-tau`.**

At a shared value of 10 the entire 11-15 second band was left out -- 38% of
every `close_budget` refusal we have.

## What it cannot do

It cannot raise the worst close. The extra bet still SHARES the
`--extra-coin` allowance (A61), so `worst_close_cost` is unchanged at three
bets, the bet size is unchanged at ~76 contracts, and the bank still covers
the worst close 3.0x.

## Revert

`restart_bot.ps1`: delete `"--late-extra-tau", "15",` and the budget window
falls back to `--late-tau` (10 s), which is the shipped behaviour.

---

# v-panic40 -- 2026-09-19 ~02:2xZ -- LIVE: the no-block line moves to 40% belief

Operator: *"Nothing can block a hedge under 40%. And most hedges just
shouldn't be getting 'blocked' anyway."*

## Every hedge we have ever placed, by the belief that triggered it

| belief | ask | what it did to the close |
|---|---|---|
| 2.0% | 95c | **HELPED** |
| 11.6% | 76c | **HELPED** -- the BNB that cost $57.98; its 21c hedge was BLOCKED |
| 21.4% | 43c | **HELPED** (+$24.18) |
| 24.3% | 74c | **HELPED** (+$8.29) |
| 48.5% | 15c | hurt (-$13.83) |
| 52.5% | 80c | **HELPED** |
| 53.3% | 47c | **HELPED** |
| 55.9% | 51c | **HELPED** (+$29.30) |

(Four more at 64-89% belief all hurt, but `--hedge-belief 0.60` already
stops the hedge firing that high, so they cannot recur.)

**Every hedge at or under 24.3% belief helped.** The only one that hurt sat
at **48.5%** and was bought at **15c** -- precisely what `--hedge-price
0.60` refuses.

## So the 40% line is the right one

- **Below 40%:** nothing touches the hedge. Not the market-agreement test,
  not the normal-bet test, not the attempt cap, not the try cap. Only
  arithmetic: the leg must cost under $1, and there must be an ask.
- **40-60%:** the market-agreement rule survives, and on this record it
  blocks the ONE hedge that hurt and passes all three that helped.

Of the eight hedges that would fire under today's trigger, exactly one is
still subject to a filter, and it is the one that lost money. That is what
"most hedges shouldn't be getting blocked" looks like in code.

## Revert

`--hedge-panic 0` disables the bypass entirely -- the behaviour that cost
$57.98. `--hedge-panic 0.35` returns to the first version of this rule.

---

# v-nohedgeblock -- 2026-09-19 ~02:1xZ -- LIVE: NO filter may block a hedge on a collapsed bet, and it keeps trying for 30 s

**This entry exists because a rule I deployed four hours earlier cost
$57.98.** The operator: *"NOTHING SHOULD BE BLOCKING A HEDGE ON A LIVE BET
WITH A 22% CONFIDENCE RATING ... I HAVE SAID OVER AND OVER HOW CRITICAL
HEDGING IS."* He is right and this should never have shipped.

## What happened -- KXBNB15M-26SEP190145-45

| seconds left | event |
|---|---|
| 30 | signalled YES at 97c, order filled NOTHING |
| 25 | dump guard refused an 82c offer as too-good-to-be-true |
| 24 | signalled at 85c -- **filled 76 contracts at 74.98c**, the book collapsed inside the round trip |
| 23 | hedge alarm, belief **0.227** |
| **23** | **hedge BLOCKED by `--hedge-price 0.60`** -- the other side was 21c, but OUR side still quoted 79c |
| 21 | tried at 51c, filled 0 |
| 20 | tried at 70c, filled 0 |
| 19 | tried at 76c, filled **1 contract** |
| 18 | **gave up** (HEDGE_MAX_TRIES was 5), eighteen seconds still on the clock |
| settle | **-$57.98** |

| hedge at | cost | the close nets |
|---|---|---|
| **23 s at 21c** | $15.96 | **+$3.06** |
| 21 s at 51c | $38.76 | -$19.74 |
| 19 s at 76c | $57.76 | -$38.74 |

**A $61 swing, lost to a filter.**

## A62: below 35% belief, nothing may block a hedge

`hedge_panic(belief)` is true at or under **0.35**. In a panic the loop
bypasses **every discretionary filter**:

- the market-agreement test (A47, `--hedge-price`)
- the normal-bet test (A51, `--hedge-normal`)
- the per-close attempt cap
- the try cap

What still applies is arithmetic rather than opinion: the leg must cost
under $1 (`hedge_ask_ok` -- a leg at or over $1 cannot beat holding), and
there must be an ask to hit. **A missing belief is NOT a panic**: it must
not trigger the one path that ignores every other safeguard.

**Why the market-agreement rule was wrong here.** Its evidence was 5 of 5
cheap hedges hurting -- but those were FALSE ALARMS, positions that
recovered. This was a real collapse: our model knew in one second and the
market took two more. What the market thinks is not evidence against our
own model; it is a two-second lag we have now measured and paid for.

**And the operator's standing answer to the objection**, said many times
before tonight: a hedge that turns out wrong is not a trap. *"ONCE
CONFIDENCE REBUILDS ON EITHER SIDE YOU CAN JUST BUY MORE OF THAT SIDE."*
Being on both sides is recoverable; being naked in a collapse is not.

Above 35% belief the market-agreement rule still applies, which is where
its evidence actually came from.

## A62b: HEDGE_MAX_TRIES 5 -> 30

Five tries gave up at 18 s with the position naked. The runaway that cap
was written for is ORDERS PER SECOND, and the one-per-second pacing is what
prevents that -- not the total. 30 cannot outlive a close (the window is
45 s).

## What is NOT fixed, and is the next thing to look at

**The entry.** The dump guard refused 82c as a crazy deal (over 15c under
fair), the next signal came at 85c -- 14.9c under, squeaking below the bar
by a tenth of a cent -- and the IOC then swept down to **74.98c, 25c under
fair**. The guard checks the price we SEE; it cannot check the price we
GET. Someone sold us 76 contracts at 75c because they knew where BNB was
going. A fill far below the ask we saw is a picked-off signal and nothing
currently reacts to it.

## Revert

`--hedge-panic 0` disables the bypass entirely (that is the behaviour that
cost $57.98). A62b is code: set `HEDGE_MAX_TRIES` back to 5.

---

# v-latebudget -- 2026-09-19 ~01:3xZ -- LIVE: the extra-bet allowance actually works now, and it reaches the last ten seconds

Operator: *"Fix the one that refused 126 markets too that's really bad."*
Two things, and the first is a defect in what went live three hours ago.

## 1. AMENDMENT 61: the third-coin allowance could not fire in 68% of closes

`close_budget_for` required `len(coins) >= MAX_PER_CLOSE` before granting
anything -- I read "after two have been maxed out" as two COINS. **But a
close spends its budget in CONTRACTS.** One market taking two bets exhausts
it without a second coin ever existing, and **282 of our 417 closes hold
exactly one coin**. So the allowance deployed at 00:03 tonight was dead in
more than two thirds of closes.

Measured on the 126 markets `close_budget` refused inside the last ten
seconds:

| what it was | count | fixed by |
|---|---|---|
| a NEW coin with fewer than two coins held | **97** | A61, this entry |
| a coin we already held | 29 | A59, below |

The test is gone. Nothing else guards it and nothing needs to: the function
is only consulted when the base budget is under pressure, the caller still
refuses unless `spent` is under the number it returns, and the exposure was
already counted in `worst_close_cost`. **Risk unchanged, allowance 3.5x more
usable.**

## 2. `--late-extra 1` goes live, SHARING the allowance rather than adding one

Inside `--late-tau` (10 s) a close may spend one extra bet whatever it
already holds -- the 29 above, and any top-up.

**It shares the extra bet with the coin allowance rather than adding a
second.** Summing them would put the worst close at FOUR bets and, at a
fixed brake, cut the bet a quarter to pay for a case that has never
happened. At a $640 bank and a 3.00 brake:

| | bet size | worst close | bank covers |
|---|---|---|---|
| third coin only (00:03 tonight) | 72 | $211.68 | 3.02x |
| **third coin + late top-up, shared** | **72** | **$211.68** | **3.02x** |

**The bet size does not move and neither does the worst case.**

## Why that window is worth it -- our own live fills

| seconds left | fills | contracts | median price | per contract | losing |
|---|---|---|---|---|---|
| 0-5 | 23 | 1,028 | 94.3c | 5.354c | 0 |
| 6-10 | 45 | 2,158 | 94.8c | 5.461c | 0 |
| 16-30 | 344 | 13,023 | 97.2c | 2.103c | 11 |
| 31-45 | 81 | 3,933 | 97.8c | 2.197c | 1 |

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **the late allowance only:** delete `"--late-extra", "1",`.
- **both allowances:** delete that and `"--extra-coin", "1",`, and set
  `"--bank-brake", "4.08"` (or the size stays cut for nothing).

A61's fix is code, not a flag; reverting it means reverting the commit.

---

# v-cheap -- 2026-09-19 ~01:0xZ -- LIVE: the 96.5c price floor is gone, and a top-up can finally be boosted

Two changes, one cause. The operator: *"WOAH WHAT WE CANT BUY CHEAPER THAN
96.5??? ... boost needs to apply to all trades ... please get rid of
whatever is blocking us from cheap trades."*

## 1. `--early-max-edge` 3.0 -> 10.0 : the cap was a price floor in disguise

Our model is usually ~100% sure, so edge is `(1 - price) - fee`. A cap on
EDGE is therefore a floor on PRICE, and nobody intended it:

| price | edge | 3c cap | 10c cap |
|---|---|---|---|
| 90.0c | 9.37c | refused | allowed |
| 94.0c | 5.60c | refused | allowed |
| 96.0c | 3.73c | refused | allowed |
| 96.5c | 3.26c | refused | allowed |
| 97.0c | 2.79c | allowed | allowed |

**That is why every fill was 97-98c.** The 90c floor we deployed on 09-18
as the adverse-selection guard never got a chance to bind. At 10.0 the
floor binds instead, so the 31-45 s leg may now buy 90-98c.

It refused 18 live trades, the cheapest **90.0c with 8.88c of edge**.

**What we give up.** A50 was built on the TAPE -- 6c+ edges at 31-45 s lost
3 of 11 -- and rule 5 says the tape cannot price our losses. The one live
loss of that shape was 93c, 6.43c edge, -$18.69, in the uncapped arm. Both
uncapped arms lead live (+12% on 27 markets, +41% on 28); neither is old
enough to be a result.

**BAR: revert to 3.0 at TWO losing closes on early fills under 96c in the
first 40 such fills.** The 90c floor does not move tonight.

## 2. A60: the top-up re-cap now counts the late boost

`_stage46` capped a top-up at `SIZE - early_held`, whatever A48's boost had
asked for. So a market entered outside the last 10 seconds could NEVER be
boosted inside it -- which is why, in 547 filled markets, **not one was
bought outside 10 s and again inside it**.

Holding 60 of an 80-contract bet, a top-up at 8 s could add 20 more; it may
now add 60. The boost's own conditions still decide whether the extra
contracts are bought: `--late-pin 0.9975` and `--late-jump 2.0` are
unchanged, and a larger cap cannot raise a number the boost never widened.

## What this does NOT fix, and the arm that tests it

`close_budget` still refused 126 markets inside the last 10 seconds -- 97
we did not hold and 29 we did. `--late-extra` (A59) adds a bet of budget
there and is PAPER ONLY tonight: `arm-lateextra` and `arm-nocap-late`.

## Why the last ten seconds is worth this trouble

Our own live fills, every one:

| seconds left | fills | contracts | median price | per contract | losing |
|---|---|---|---|---|---|
| 0-5 | 23 | 1,028 | 94.3c | 5.354c | 0 |
| 6-10 | 45 | 2,158 | 94.8c | 5.461c | 0 |
| 16-30 | 344 | 13,023 | 97.2c | 2.103c | 11 |
| 31-45 | 81 | 3,933 | 97.8c | 2.197c | 1 |

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **the price floor only:** set `"--early-max-edge", "3.0"`.
- **the top-up boost only:** it is code, not a flag -- set `--late-mult 1.0`
  to switch the whole late boost off, or revert commit.

---

# v-thirdcoin -- 2026-09-19 ~00:2xZ -- LIVE: a third COIN may spend beyond the close budget, and the brake moves 4.08 -> 3.00

Operator: *"if we've never lost multiple coins at once, allow extra total
size if it comes in the way of an extra coin after two have been maxed out.
I'm okay with that."*

## The condition he set, measured

**Of 417 closes we have traded, 19 had a losing coin and NOT ONE had two.**
In every one of the nineteen, the other coins at that close won or there
were none. Twelve of those closes already held three coins.

Why it is not luck: a close loses only when the last seconds move against
the side we took ON THAT COIN. Correlated moves across coins are common;
correlated moves that cross twelve different strikes in the same direction
inside the same second are not.

## And the budget really does bind

`close_budget` refused **326 markets on a coin we were NOT holding** -- about
**65 a day** -- against 95 on a coin we already had. So this is not a
theoretical allowance.

## What the bot does differently

A close may now spend **one extra bet of budget on a coin it is not already
holding**, once the base budget has been spread across MAX_PER_CLOSE coins.
A coin we ALREADY hold gets nothing extra: the argument is that two COINS
have never lost together, and topping up the first coin adds a second bet on
it, not a second coin.

## The price, and the choice he has

`worst_close_cost` grows from two bets to three, and **every rail reads it**
-- the bank brake, the loss abort, the stake cap -- so the extra coin is
paid for in the bet size rather than discovered in a drawdown. At a $640
bank:

| brake | extra-coin | bet size | worst close | bank covers it |
|---|---|---|---|---|
| 4.08 | 0 (before tonight) | 80 | $157 | 4.1x |
| 4.08 | 1 | **53** | $156 | 4.1x |
| **3.00** | **1 (deployed)** | **72** | **$212** | **3.0x** |
| 2.72 | 1 | 80 | $235 | 2.7x |

He asked for extra TOTAL size, not the same total spread thinner, so the
brake moves to **3.00**: bets 80 -> 72, a third coin allowed, worst close
$157 -> $212. **One line changes it either way** -- 4.08 keeps tonight's
risk exactly and accepts 53-contract bets; 2.72 keeps 80-contract bets and
a $235 worst close.

## Also in this restart

- **AMENDMENT 57, `--sigma-stress`** exists as a flag now (it was a constant).
  It multiplies the volatility estimate EVERYWHERE -- entry, sweep limit and
  hedge. **Not live**: four paper arms run it at 0.8, 1.25, 1.5 and 2.0, and
  a live run refuses anything under 1.0.
- **AMENDMENT 58**, every settled record now carries a `boost` field: one
  plain sentence saying whether the last-seconds boost fired and why not.

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **third coin only:** delete `"--extra-coin", "1",` and set
  `"--bank-brake", "4.08"`. Both, or the bet size stays cut for nothing.

---

# v-late10 -- 2026-09-18 ~23:5xZ -- LIVE: 1.5x the bet inside the last 10 seconds, on three conditions the operator set

Operator: *"Yes a48 live, make sure it's got good confidence when buying in
the last 10 seconds, have it run at the full normal rate immediately, cut at
first loss. If it looks like it's going to a loss don't buy the extra, and
obviously if it's losing hedge if possible in those last seconds."*

## What the bot does differently

Inside the last 10 seconds one order may reach **1.5 x SIZE** (about 120
contracts at tonight's 80), through the same three rails A45 and A53 use:
the drawdown headroom `(bank - 0.8 x high-water) / ceiling`, what the book
holds at or under the sweep limit, and the close budget.

## Evidence

**The paper arm, 49 markets over 29 hours, ZERO losses, +15.1% against the
live bot on the same markets** (scaled to our own contract volume, so it
compares the strategy and not the stake). It is the only arm old enough to
read that beats live and was not already deployed. Independently, our own
live fills say the window itself is where the money is:

| seconds left | contracts | per contract | losing closes |
|---|---|---|---|
| 0-5 | 1,028 | 5.35c | 0 |
| 6-15 | 4,125 | 3.80c | - |
| 16-30 | 11,363 | 1.90c | - |

**What is NOT proven:** that a 1.5x order fills at the same price as a 1x
one. Paper cannot see a seller choosing to hit us. Rule 5.

## The three conditions, each in code

**1. "good confidence" -- `--late-pin 0.9975`.** The EXTRA contracts need
99.75% confidence in our side where an ordinary bet needs 99.5%. Measured on
all 109 live signals inside 10 seconds: the bar allows 71% of them, and the
ONE that ever lost sat at **99.612%** -- under the bar, so it would have
been refused the extra. The ordinary bet is untouched at every confidence.

**2. "don't buy the extra if it looks like a loss" -- `--late-jump 2.0`.**
A one-second move of 2 sigma against our side skips the boost.
**It must be TIGHTER than `--jump-gate`'s 3.0**, which already refuses the
whole trade: every candidate reaching the boost has passed that bar, so a
`--late-jump` at or above 3.0 could never fire. This was going to ship at
4.0 -- decoration in the start record and in this file. `pinrun` now refuses
to start on such a value, and the same guard refuses a `--late-pin` that is
not above the ordinary gate. Honest limit: jumps are rare (27 refusals in
eleven days), so this is a safety valve, not a volume lever. Condition 1 is
the one doing the work.

**3. "cut at first loss" -- no flag, the bot does it.** One late-boosted
loss sets `LATE_MULT` back to 1.0 for the rest of the run and writes
`late_boost_off`. The extra cost of the boost is therefore bounded by ONE
trade's extra size, about $37 at tonight's bet.

**And hedging is unchanged** -- it fires on belief at any tau including
inside the last seconds, now with the v-bands rule that the market must
agree.

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **boost only:** delete `"--late-tau", "10", "--late-mult", "1.5",`
- **its conditions only:** delete the `--late-pin` and `--late-jump` lines
  (this returns A48 to exactly the arm that was measured)
- **all of it:** delete all four.

---

# v-bands -- 2026-09-18 ~22:3xZ -- LIVE: hedge only when the market agrees, and 1.5x at 90-94c that switches itself off after one boosted loss (`c015709`, off-switch and the skip's withdrawal in the commit after)

Two flags in `restart_bot.ps1` (a third was staged and withdrawn before it ran -- section 2), one entry, each with its own revert line.
Operator, 2026-09-18: *"Okay remove insurance. But keep hedging. We can remove
94-96. If it's safe then yea you figure out a way to buy more beneath 94."*

## 1. `--hedge-price 0.60` (AMENDMENT 47, live for the first time)

**What the bot does differently.** It still buys the other side when its own
belief in our side falls below 0.60 (`--hedge-belief 0.60`, unchanged) -- but
now ONLY if the market agrees: our side must also be trading under 60c, i.e.
the other side's ask must be over 40c. A hedge bought at 10-27c, when the
market still gave our side 73-90%, was insurance against a scare; a hedge at
47-74c is the market confirming the loss.

**Evidence (live fills, every hedge ever placed).** 9 genuine hedged
closes (the two `plant_attempt` test trades and two standalone cheap bets
excluded). The first cut of this table missed the two full-size losses of
09-14 because it was built from legs under 50c; the operator asked "this
version better still hedge when I lose", and the answer is in the rows:

| hedge ask | our side's price | closes | primary lost? | helped | hurt | net vs no hedge |
|---|---|---|---|---|---|---|
| 10-27c | 73-90c | 5 | no (all false alarms) | 0 | 5 | **-$41.72** |
| 43c, 47c, 51c, 58c, 74c | 26-57c | 4 | yes, 4 of 4 | 4 | 0 | **+$62.28** |

The real losses: BTC 09-14 (-$58.43, hedged at 43c and 58c, +$24.18 back),
HYPE 09-14 (-$59.20, hedged at 51c, +$29.30 back), DOGE 09-18 (-$3.93,
hedged at 74c, +$8.29), BNB 09-16 (-$0.98, hedged at 47c, +$0.51). Every
one of those hedges was bought with our side under 60c, so the rule passes
all four; every false alarm was bought with our side at 73c or more, so the
rule blocks all five. The margin between the two groups is 57c vs 73c. It is
also the same number as the belief trigger, so the rule reads: hedge when the
model AND the market both put us under 60%.

**Pre-registered bar.** Every alarm now writes `hedge_wait_price` when the
market disagrees. After 20 such waits, score them: if the blocked hedges
would have helped by more than the fired ones cost, lower the threshold to
0.70. If a position we waited on then lost unhedged, that is the price of
this rule and it is counted against it.

## 2. `--skip-band 0.94 0.96` -- STAGED, THEN WITHDRAWN BEFORE IT RAN

The flag exists (gate `price_band`; the sweep stops under a skipped band)
and stays in the code, OFF. It was in `restart_bot.ps1` for about an hour on
09-18 and was taken out before the operator restarted, because he asked the
right question: *"are we sure there's a correlation behind the 94 band
losing ... and it's not just coincidence."* It was coincidence.

The "+0.8% on 83 closes" that justified it is the WHOLE history, and three
of its four losses are from the first-week bot (09-09 NEAR, 09-10 BNB, 09-12
SOL) before the jump gate, the both-sides guard and the close-clustered
brake existed. On the modern bot (09-13 on): 38 closes, 1 loss, +$51.82 on
$2,305 -- **2.25%**, better than 96-97.5c (1.18%) and level with 97.5c+
(2.03%). The 95% bounds on every band from 94c up overlap. And the slot
argument had no evidence either: not one refusal under 94c has ever been for
a close budget or a position cap. The skip would have cost about 6.5 fills a
day at ~2.3% of ~$59 -- roughly $8/day -- to prevent nothing measurable.

Lesson, already in memory as "check the log dates against the deploy first"
and broken again here: split by bot era BEFORE recommending a refusal.
The paper arm `arm-b-skip9496` now tests the skip beside the control.

## 3. `--band-mult 0.90 0.94 1.5` (AMENDMENT 53, new)

**What the bot does differently.** Inside 90.0-93.9c one order may reach
1.5 x SIZE (about 117 contracts at today's 78), through the same three rails
A45 and A48 use: the drawdown headroom `(bank - 0.8 x high-water) / ceiling`,
what the book actually holds at or under the sweep limit, and the close
budget. After one ordinary loss the headroom alone shrinks the boost back to
SIZE. The order path's count cap now admits the multiple (it did not admit
A48's, which was a latent refusal). An early leg keeps the boost through the
A46 re-cap (`SIZE x mult`), so the 45 s leg can carry it.

**Evidence.** 90-94c: 64 live closes, 0 losses; the 95% upper bound on that
is about 4.6%, against an 8% break-even. On 09-18 the touch at 90-94c held a
median 192 contracts against the 97 we took (4 of 5 signals had 1.5x
available). What is NOT proven: that a 1.5x order fills at the same price
and the same loss rate -- a bigger order meets a smarter seller, and that is
the population rule 5 exists for. Hence 1.5x and not 2x, and the bar below.

**Pre-registered bar, ENFORCED BY THE BOT.** One boosted loss switches
`--band-mult` off for the rest of the run (`band_boost_off` record); the
extra cost of the boost is therefore bounded by one trade's extra size,
about $36 at today's bet. Revert the flag at the FIRST loss on a boosted
fill in the first 20 boosted closes. At 20 boosted closes with no loss and an average
fill within 0.3c of the ask seen, raise to 2.0 (the `arm-b-mult2` paper arm
runs it meanwhile). `band_boost` records carry was/now/cap/avail/room so the
binding rail is visible on every boost.

## What this is expected to be worth

Small and positive per day, larger for what it unlocks: the 1.5x step at
recent frequency (4-7 such fills a day, ~$70 stake) adds roughly $3/day at
the band's 8%; going to 2x and to 80-90c adds several times that. The skip
moves risk, not money. The hedge rule saves about the $33 it has cost so far
per week of similar alarms.

## Revert

All three are FLAGS. Edit `restart_bot.ps1`, then run `.\restart_bot.ps1`:

- **hedge rule only:** delete the `"--hedge-price", "0.60",` line.
- **1.5x only:** delete the `"--band-mult", "0.90", "0.94", "1.5"` line.
- **both:** delete both lines.

The paper arms in `start_bands.ps1` each change one of these against the
new baseline; `arm-b-control` is the new baseline itself in paper.

---

# v-ceiling99 -- 2026-09-18 ~17:4xZ -- NEVER LIVE: the 99c cap took the bot DOWN for ~5 minutes and was reverted

**What happened.** `restart_bot.ps1` was given `--price-ceiling 0.99` and the
bot did not come back: `pinrun` runs its own self-test at startup WITH the flag
already applied, and four older checks assert the 98c ceiling against the
RUNNING value (`worst_close_cost(20) must be ... 39.2, got 39.6`, `ladder_under
... under the 98c ceiling`, two A45 room checks "at the 98c ceiling"). They
failed, the process wrote "self-test failed -- nothing ran", and the live bot
was down from ~17:04 to ~17:09Z. The operator saw it before I did: "Also the
bot is down." My own `--selftest` had passed because it ran WITHOUT the flag.

**Reverted** to the 98c default. The `--price-ceiling` flag stays in the code
(the declared default is asserted, so it is harmless) but MUST NOT be passed
live until those four checks are rewritten against `_DEFAULT_PRICE_CEILING`.
This is the trap already in memory -- self-tests asserting running values
instead of declared defaults -- and it bit a fifth time.

**And the operator's condition was not met.** He said "As long as you're
certain 99c is more profitable." The evidence is 82 live markets at 98-99c,
1 loss (1.22%) against a ~1.4% break-even -- a margin of 0.2 points on one
loss, whose 95% upper bound is near 5%. That is "probably", not "certain".

## What the change WOULD be, for when he decides

**Operator, twice: "The two gates that trim volume without preventing loss,
remove or severely lessen them" and, shown the numbers, "I'm just following
your words."** The cap would become a FLAG at 0.99; the declared default stays
0.98.

## The two numbers he was following, reconciled

`pinattrib` reports, per gate, what every BLOCKED refusal would have paid if
it had filled, using the market's real settlement. Those are UPPER BOUNDS --
every refusal filled, none lost -- and they were quoted to him as money on the
table without the tail beside them. Put beside it:

| gate | "if filled" | per trade | our REAL record in that band | one loss |
|---|---|---|---|---|
| 98c cap | +$122.80 (379 trades) | 32c | 82 live markets, 1 lost, **+$51.07** | ~$76 |
| thin-profit floor | +$136.51 (1,048 trades) | 13c | 5 live markets, +$0.03 | ~$76 |

**The cap is lifted** because the band it excludes has a real, positive live
record including its one loss. The 09-09 resilience arithmetic is unchanged
and still true -- a loss at 98.5c takes ~65 wins to earn back where one at
98c takes 53 -- and he chose the volume with that in front of him.

**The floor is NOT lowered.** At ~99.5c a win is 13c and a loss $76, so one
loss erases 580 wins; break-even is one loss in 200. The 1,048 blocked
trades span roughly 300 closes (rule 4), which bounds the loss rate at
about 1 in 100 -- five times break-even. At any loss rate the data allows the
expected value is negative; the +$136.51 is the ceiling of the outcome, not
its middle. Standing offer: it moves only on his explicit word after this.

## Side effect

The ceiling enters the bet-size divisor: bank / (4.08 * 2 * 0.99) = 8.08, so
size is about 1% smaller than at 0.98. The bank-divisor self-test tolerance
was widened to admit it.

## Revert

```powershell
cd C:\kals-repo
# restart_bot.ps1: delete the "--price-ceiling", "0.99" line
.\restart_bot.ps1
```

---

# v-early-full2 -- 2026-09-18 ~17:0xZ -- LIVE: the 31-45 s leg goes from a THIRD to FULL size

**Operator: "If you're ready, then yes increase to 45."** `restart_bot.ps1`
now passes `--early-frac 1.0` (was `0.333`). The 90c floor and the 3c edge cap
on the early leg are unchanged.

## Why the third was never supported by the evidence

It was a precaution from a mechanism story -- at 45 s only a quarter of the
settlement average is locked -- and the live record does not bear it out:

| live window | markets | model misses | net |
|---|---|---|---|
| 31-45 s | 57 | 1 (hedged to +$4.36) | +$64.79 |
| 3-30 s | 475 | 11 | +$496.62 |

Same miss rate. The raw market at 31-45 s FAILS break-even on the tape in every
price band this week (research on 2026-09-18, `supplyclock.py`), so what makes
the live number good is the confidence filter doing real work at 45 s -- the
test it needed to pass.

Every miss in both windows is a single-second jump of 10-18 sigma with sigma
understated 2-3x at entry, and the losers sit inside the winners' confidence
range (`sigcheck.py`). No entry filter separates them: a 1.5x sigma stress
refuses all four 45 s misses and 88% of the wins. The defence is the hedge,
which is +$46.55 net across every alarm.

## Why full size matters more than the miss rate

Post-fix (after v-a8fix), of 34 early legs on live, **26 got no top-up because
by 30 s nothing was left to buy** (`no_offer`), 3 were topped up, 1 hit the
depth floor, 4 had no look. The early leg is not a starter position; on three
markets in four it IS the trade. At a third size that forgoes two thirds of
the position. Post-fix early legs at a third: 31 markets, 31 won, 0 lost,
+$33.59 -- roughly +$100 at full.

## The tail, stated

A jump loss at full size is three times a jump loss at a third. The one live
45 s miss cost the model leg $3.93 at a third; at full it is about $12 before
the hedge. The stage-2 bar from `PREREG_staged.md` still governs: revert to a
third at 3 losing early markets in 40, or 2 in the first 15.

## Revert

```powershell
cd C:\kals-repo
# restart_bot.ps1: change "--early-frac", "1.0" back to "--early-frac", "0.333"
.\restart_bot.ps1
```

---

# v-oilsweet -- 2026-09-18 ~15:4xZ -- LIVE: oil moves to 16-30 s at 93-99c, and to $20

**Operator: "Okay just do 16-30 93c+ then do a paper arm for 2-30. Increase to
$20."** `cmdlive` now runs `LIVE_WINDOWS = ("wti-sweet",)`, `LIVE_MAX_TAU = 30`,
launched with `--size 20`.

## Why the old window was wrong

The 0-15 s rule came from a MECHANISM STORY -- inside 15 seconds the one-minute
settlement candle is nearly formed -- and `research/oilband.py` measured the
story wrong. It walked **147,401 WTI takers over 287 settled closes**, counted
by CLOSE and not by trade (rule 4), and oil is better between 16 and 30 seconds
than inside 15 **at every price they share**:

| seconds | price | closes | lost | break-even | c/contract |
|---|---|---|---|---|---|
| 0-15 | 95-97c | 55 | 1 (1.82%) | 3.73% | +2.79 |
| **16-30** | **95-97c** | **41** | **0** | 3.73% | **+3.54** |
| 0-15 | 93-95c | 43 | 3 (6.98%) | 5.61% | **fails** |
| **16-30** | **93-95c** | **47** | **1 (2.13%)** | 5.61% | **+5.05** |

So the clock and the price floor INTERACT: under 95c is dangerous inside 15
seconds and safe between 16 and 30. The old rule had the worse half of the
clock AND a floor that excluded the best cell.

## Why 93-99c and not the wider clock the operator asked about

He asked whether 2-30 s would beat 16-30 s, since it fires more often. On the
tape it does -- 73 closes to 57, $32 to $28. But its extra closes carry THREE
losses instead of one, and losses are what get worse when a tape offer becomes
a real fill (rule 5, the 31x). Stressed at 2x, 3x and 5x the tape loss rate,
dollars over those three days at $10 a bet:

| rule | tape | 2x | 3x | 5x |
|---|---|---|---|---|
| 2-15 95-99c (the old live rule) | $13 | $8 | $4 | **-$5** |
| 2-30 93-97c | $32 | $27 | $22 | $13 |
| 2-45 93-97c | $33 | $20 | $7 | **-$17** |
| **16-30 93-99c** | **$29** | **$28** | **$27** | **$24** |

The rules that look best on tape are the ones that collapse. This one holds one
loss in 86 closes, and multiplying one loss by five is still one loss. It also
answers the volume worry outright: **86 closes, MORE than the 72 the old live
rule got** -- widening the PRICE band buys the volume back without buying the
losses.

**Rule 5 stands: this is all tape.** A paper arm on `2:30:0.93:0.99` is running
alongside (`results/cmdarm-wide230.jsonl`) so the wider clock keeps being
measured on real fills without being paid for.

## Size $10 -> $20

Operator's instruction. `MAX_CONTRACTS` is 40 and $20 at the 93c floor is 22
contracts, so the contract ceiling is not binding. The brake is unchanged:
stops at $25 net down or 4 losses in a day.

## Revert

```powershell
cd C:\kals-repo
# research/cmdlive.py: LIVE_WINDOWS = ("wti-near",) and LIVE_MAX_TAU = 15
# then relaunch with --size 10
```

---

# v-bank8 -- 2026-09-18 ~07:0xZ -- LIVE: one bet is the bank divided by 8, and the 45-second leg refuses a wide edge

Two changes, both of which REDUCE risk, deployed together on the operator's
word. `restart_bot.ps1` now also passes `--bank-brake 4.08 --early-max-edge 3.0`.

## 1. Bet size: bank/5.88 -> bank/8

**Operator: "Sure divide by 8."** He asked whether we were betting too high and
was shown this, at a $613.66 bank and 104 contracts a bet:

| if this happens | costs | quarter-hours to earn back |
|---|---|---|
| a typical loss (our 16 losses averaged) | $31 | 12 (~8 hours) |
| the worst we have ever taken | $93 | 37 (~1 day) |
| insurance fails completely, 96c to zero | $100 | 40 (~1.1 days) |

Size is `bank / (BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING)`, so `BANK_BRAKE`
3.0 -> 4.08 makes the divisor 7.997. At the same bank: **104 contracts -> 76,
about $75 a bet.** The worst one close can cost falls from 33% of the bank to
25%; the earning rate falls by about a quarter. He was shown both halves.

It is now a FLAG rather than an edit, so the risk setting can be moved and
reverted without touching the source. `bank_brake` and the derived
`bank_divisor` are both in the start record -- a log showing the size but not
the brake cannot say whether a small size meant caution or a small bank.

## 2. AMENDMENT 50: the 31-45 s leg refuses a WIDE edge

**Operator, on the 45-second leg: "It's earning good it'd be a shame to shut it
off, but also a shame to lose money... It might mean smaller gains but that's
better than none."**

This is a REFUSAL, not a new way to buy, so its worst case is fewer trades --
which is why it went live ahead of its paper arm finishing. Measured over every
signal joined to its settlement, split by how far our model sat above the
market on our side:

| when | model above market | bets | lost | $/bet |
|---|---|---|---|---|
| 31-45 s | under 3c | 177 | 3 | +0.06 |
| 31-45 s | 3-6c | 62 | 5 | **-0.57** |
| 31-45 s | 6c or more | 11 | 3 | **-3.01** |
| 30 s or less | 6c or more | 263 | 1 | **+1.44** |

Live fills agree on the late half: 102 fills at 6c+, 4 losses, +3.08 $/bet.
There has never been a live early fill at 6c+.

**Rule 5 limit, stated:** the 31-45 s rows are dominated by PAPER arms, which
book a fill the moment they see an offer. The LEVELS are not evidence; the
SHAPE is, and the shape is what this acts on. A paper arm at FULL early size
with the same 3c cap is running as the confirmation
(`results/PREREG_a50_early_edge_cap.md`, bars written before any result).

**Why the sign flips:** settlement is the mean of 60 one-second prints. At 15 s
left, 45 are already recorded and a cheap market price is simply wrong -- that
disagreement IS the edge. At 45 s only 15 are, and our confidence rests on a
volatility estimate, so a market disagreeing by six cents is usually right.
**Inside 30 s nothing changes.** `--early-max-edge` refuses to start without
`--early-tau` above 30, and the self-test asserts the check sits inside the
early-leg block. Refusals log as `early_wide` and are named in `pinattrib`.

## Revert

Both are FLAGS, so neither revert needs a code change. Edit
`restart_bot.ps1`, then run `.\restart_bot.ps1`:

- **Size only:** change `"--bank-brake", "4.08"` to `"--bank-brake", "3.0"`.
- **45-second cap only:** delete the `"--early-max-edge", "3.0",` line.
- **Both:** delete both lines.

---

# v-early49 -- 2026-09-18 ~02:3xZ -- LIVE: the 31-45 s leg reopens at a THIRD, with a 90c price floor

**Operator: "Can you re open 45 seconds with a cap at 90c, or whatever number
you like?"** `restart_bot.ps1` passes
`--early-tau 45 --early-frac 0.333 --early-min-price 0.90`.

**Why it is back at all.** `results/RESULTS_pickoff.md`: the cheap offers are
taken a median of **41 seconds** before the close while our window starts at
**30**. The 31-45 s band is where the trades we are missing actually live, so
closing it gives up the only lever aimed at the real problem.

**Why a THIRD, not a full bet.** Full-size life: 31 markets, 29 settled, **29
won, +$35.81** -- then one fill took **$27.87** back.
`KXBTC15M-26SEP172115-15`: ask seen **97.8c**, **FILLED AT 53.0c**, 99
contracts, because the book collapsed inside our 160 ms round trip. **A limit
price is a MAXIMUM, so no price rule can prevent that fill -- only size bounds
it.** At a third the same event costs about $9.

**AMENDMENT 49, the 90c floor.** An early leg now also needs the ask at or
above `EARLY_MIN_PRICE` (0.90). Out at 31-45 s only a quarter of the
settlement average is locked, so `fair` leans much harder on the sigma
estimate; a cheap ask there is the market disagreeing with us exactly where
the model is weakest. **Inside TAU_MAX the full leg is untouched** -- we still
buy at any price down to the dump guard's 84.5c in the 3-30 s window.
Refusals log as `early_cheap` and are named in `pinattrib`, so the floor's
cost is measurable rather than invisible.

**Shipped defaults unchanged and asserted:** `_DEFAULT_EARLY_TAU_MAX = 30`
(off), `_DEFAULT_EARLY_MIN_PRICE = 0.90`.

**Bar:** `results/PREREG_staged.md` stage 2 still stands -- revert at 3 losses
on early-leg closes in the first 40, or 2 in the first 15. The count restarts,
because the size and the floor both changed.

**REVERT:**

```
git revert --no-edit <this commit>
powershell -File C:\kals-repo
estart_bot.ps1
```

or drop `--early-tau/--early-frac/--early-min-price` from `restart_bot.ps1`.

# v-a8fix -- 2026-09-17 ~21:0xZ -- AMENDMENT 8's both-sides guard finally reads the right variable

**Found by the fresh-eyes review of the whole crypto buy path, and confirmed by
three independent readers plus an adversarial verifier.**

**The bug.** The both-sides test sat at `pinrun.py:~5883` and compared
`prev["sides"][tk] != want`. But `want` is not assigned until ~140 lines below,
inside the same scan loop. So it compared the side we hold in THIS market
against the side we happened to want in the PREVIOUS market of the scan -- or
`None` on the first pass.

**What that did.** It blocked roughly **94% of re-looks at a market we already
hold**, including legitimate SAME-side top-ups, and it let a genuine
opposite-side buy through whenever the previous market in the scan happened to
want the same side. Both directions wrong, neither detectable by reading the
gate's name in a log.

**The fix.** The comparison moved to immediately after `want` is assigned --
the first line in the loop where it is meaningful -- and is now a named
function, `_both_sides_block(prev, ticker, want)`, so it can be tested
directly. Only an OPPOSITE side blocks; a same-side re-look is a top-up and
passes.

**What the bot now does differently.** Top-ups on a market we already hold are
no longer blocked at random. Every other gate -- ceiling, edge, EV, dump guard,
rebuy band, per-market cap -- still applies to them unchanged, so this does not
create a new trade type, it stops suppressing an existing one.

**Money.** Small and honestly bounded: the verifier put it at **$5-$40 over the
four days the guard has been reachable**, of which only about $5 is grounded in
live fills (8 of 174 filled markets since 09-14 had an unfinished position, 174
contracts short, worth $4.80 at the measured 2.76c a contract). The original
review claimed $242; that did not survive checking.

**Risk.** This LOOSENS a gate, so it can only increase trading. The protection
it was supposed to provide is now actually present for the first time -- before
the fix, a real opposite-side buy could slip through. So it is safer in the
direction that matters and looser in the direction that costs money.

**Self-tests:** opposite side blocks, same side passes, a different market is
unaffected, all the null paths return False, and the loop is asserted to call
it AFTER `want` exists.

**Deploys on the next restart of `pinrun.py --live`** -- there is no flag; it
is a plain bug fix in the file the watchdog launches.

**REVERT:**

```
git revert --no-edit <this commit>
powershell -File C:\kals-repo
estart_bot.ps1
```

# v-early-full -- 2026-09-17 ~19:5xZ -- LIVE: the 31-45 s leg becomes a FULL bet

**Operator: "Bump 45 seconds up to normal price as well."** `restart_bot.ps1`
now passes `--early-tau 45 --early-frac 1.0` (was `0.333`, and `0.5` before
that on the same day).

**What the bot does differently.** A market that passes every gate with 31-45
seconds left is now bought at **full size**, not a third. The top-up leg
becomes a no-op by construction: `staged_take` returns `size - early_held`,
which is zero once the position is already full. **One early leg per market is
still enforced** by the `early_once` refusal, so this cannot double up, and
`MAX_PER_MARKET` is untouched. In effect `TAU_MAX` is 45 for the first bet.

**What supports it.**

- The flat tau-45 paper arm is the same configuration and has **33 settled
  closes, 0 losses, +$10.17**, with 22 NEW markets (ones that exist only
  because of 31-45 s) and **0 lost**. It takes +230% more closes than its
  control.
- On the tape BY MARKETS (rule 4), buyers of 95-98c lost **2.8% at 31-45 s
  (606 markets)** against **3.9% at 16-30 s (389 markets)**; at 98-99c it is
  0.9% (751) against 1.4% (483). **The earlier window is not the worse one on
  the market's own record.** Break-even is ~3.4% at 96.5c.
- Model error at 31-45 s is 0.058% of moments against 0.021% at 21-30 s
  (`pinbefore`, 14,261 closes, index only). Both are ~1/200th of our 4.66%
  live loss rate, so **the risk here is adverse selection, not arithmetic.**
- Live so far on the staged third: 3 early legs, 3 won.

**What it gives up, stated because it is real.** At a third we took a foot in
the door early and completed at 30 s when more of the settlement average was
locked. At full size we commit at the earlier, worse-information moment and
cannot improve the price afterwards. The compensating fact is that the tape
says 31-45 s is not a worse window; the uncompensated risk is that the tape
cannot see adverse selection, which is precisely what killed every optimistic
tape number this project has produced (rule 5, 31x).

**THE BAR IS UNCHANGED AND STILL BINDING** -- `results/PREREG_staged.md`
stage 2, scored over the first 40 live closes carrying an early leg:
**revert at 3 losses in 40, or 2 in the first 15.** Three closes are in.

**REVERT:**

```
git checkout HEAD~1 -- restart_bot.ps1
powershell -File C:\kals-repo
estart_bot.ps1
```

or edit `--early-frac 1.0` back to `0.333` and restart. Setting it to `0`
disables the early leg entirely and returns the bot to TAU_MAX 30.

# v-cmdpenny -- 2026-09-17 16:14Z -- LIVE: the COMMODITY PENNY TEST, gold and oil, ONE contract

**Operator, 2026-09-17: "I'm ready for commodity penny testing"**, and then
*"Make the good commodities live, also run paper tests on the ones you don't
have confidence in, but do your best to create the best strategy you possibly
can for them."*

**This is a SECOND live process, not a change to the crypto bot.** `pinrun.py
--live` is untouched: same flags, same size, same gates. Nothing about
v-staged or any earlier version changed.

    C:\Python314\python.exe -u research\cmdlive.py --live
        --signoff "commodity penny test" --minutes 1440

**What it does.** Watches KXGOLD15M and KXWTI15M. When the book offers the
priced-in side inside one of that series' windows, it buys **one contract**.
First live fill, 16:14:5xZ: `KXWTI15M-26SEP171215-15` YES @ 90c, 1 contract,
41 s left, $0.90 committed.

**The windows** (`cmdarm.BANDS`, imported by reference so the paper control
cannot drift from the live test), from the grid's BY-MARKETS table:

| window | when | price | tape, by markets |
|---|---|---|---|
| gold-near | 2-15 s, **skips 08-14 ET** | 95-99c | 149 / 2 lost; inside COMEX hours 32 / 2, outside 117 / 0 |
| gold-far | 91-180 s | 95-99c | 379 / 2 lost (0.5%) |
| wti-near | 2-60 s | 95-99c | 254 / 3 |
| wti-mid | 16-45 s | 90-95c | 104 / 6 (5.8% against a 7.5% break-even) |
| wti-far | 121-180 s | 90-99c | 308 / 6; its 90-95c corner is the best commodity cell found, 105 / 3, +4.16c |

The shape behind them: commodities are good at BOTH ENDS of the quarter hour
and dangerous between 16 and 90 seconds -- the opposite of crypto, because
they settle on the CLOSE of a 1-minute candle rather than a 60-second average.

**Silver, copper and natural gas are PAPER ONLY** (`cmdarm.py`, all five
series), each on the best window its series has: silver 121-180 s at 95-99c
(187 / 2 -- silver's near window was the mistake, not the series), copper
46-90 s at 98-99c (227 / 2, and the middle is where every other series is
worst), natural gas 91-120 s at 95-98c (96 / 3, +0.14c, the weakest window in
the file). `cmdarm` also runs `anti-silver-mid`, a window the grid says LOSES
5-12%, as a negative control. `cmdlive.LIVE_SERIES` and an "anti" label check
mean none of those can reach the wire even if passed on the command line.

**What it can cost.** One contract per order; **$10.00 total across the run**,
counted from fills; 60 orders; **2 losses and it writes its own stop file**; a
$300 account floor so the crypto bot's capital is untouchable; 90-99c only;
never inside 2 s. Realistic worst case is the 2-loss brake at about $2.
Balance at launch $579.44.

**Evidence, and its limit.** All tape (rule 5). The tape says an offer was
taken at that price, not that WE could take it; on crypto those populations
differed 31x in loss rate. Measuring that gap IS this test.
`results/PREREG_commodity_live.md` fixes the bar BEFORE the first fill: kill
at 3 losses in 30 fills, or if silver's paper control beats gold and oil;
proceed only at <= 1 loss in 30 fills with at least 20 fills; **no size
increase without a fresh sign-off.**

**Deliberately NOT in `boot_all.ps1`.** A process that spends money should not
come back from a reboot without a human deciding.

**REVERT -- either alone is enough:**

```
type nul > C:\kals-repo
esults\cmdlive.stop
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ? { $_.CommandLine -like '*cmdlive.py*' } | % { Stop-Process -Id $_.ProcessId -Force }"
```

Deleting `results/cmdlive.stop` is what allows a restart. The crypto bot is
unaffected by either command.

# v-staged -- 2026-09-17 ~15:1xZ -- LIVE: a THIRD of a bet at 31-45 s, topped up at 30

**Operator, 2026-09-17: "As long as you have the 45 second is built as safely
as you described, deploy now."** And, on the same message: *"Unless you can
give me a reason to feel okay about the way less opportunity we're getting
push the 45 second."*

`restart_bot.ps1` now passes `--early-tau 45 --early-frac 0.333`, and
`EARLY_LIVE_OK` is True in `research/pinrun.py`. The fraction is his:
*"Bump it down to 1/3 the current size instead of half."* At SIZE 94 the early
leg is ~31 contracts, ~$30 at 97c.

**What the bot does differently.** With 31-45 seconds left, a market that
passes EVERY existing gate (confidence, edge, depth, ceiling, EV, dump guard,
jump gate) may be bought for **one third of a bet**. With 30 seconds or less it is
**topped up to a full bet** only if the same gate still passes at that
moment's price. One early leg per market. If belief has collapsed by the
top-up point, the top-up fails the confidence gate and the hedge pass -- which
covers every open position every second -- buys the other side at belief
< 0.60. **`TAU_MAX` is still 30: a FULL bet can never be bought early.**

**THIS IS A BAR OVERRIDE AND IT IS RECORDED AS ONE.** `results/PREREG_staged.md`
stage 1 asked for 30 paper closes and 20 early markets before reading
anything; the staged arm had run ~20 minutes. The operator deployed on the
evidence that existed:

- the flat tau-45 paper arm, 9.2 h: **27 bets, 27 won, 0 lost**, 3x the
  control's bet count, +0.03c on the 8 markets both arms bought;
- `pinbefore` on the index alone (14,261 closes): model error at 31-45 s is
  **0.058%** against 0.021% at 21-30 s, both trivial next to a 4.66% live
  loss rate;
- exposure per early leg is ONE THIRD of today's per-market worst case.

**The STAGE 2 live bar in PREREG_staged.md is unchanged and now governs:**
40 live closes carrying an early leg; **revert at 3 losses, or 2 in the first
15**; top-up price within 1.0c of the early price; net positive.

**Revert, copy-pasteable:**

```powershell
cd C:\kals-repo
git checkout 83fd965 -- restart_bot.ps1
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

(The code can stay; without the flag it buys no early leg. To disable it
everywhere, set `EARLY_LIVE_OK = False` in `research/pinrun.py`.)

---

# (superseded by v-staged above) AMENDMENT 46 -- built, paper only -- 2026-09-17 14:3xZ

**Live flags unchanged, `versioncheck` clean, full self-test exit 0.** The
file on disk changed again, and the live bot restarts from it. Operator:
*"implement tau 45 in a safe way. Maybe not buying full coins and topping up
what's available once we hit the normal purchase point?"*

`--early-tau 45 --early-frac 0.5` (refused live until `EARLY_LIVE_OK` is
flipped in a commit citing `results/PREREG_staged.md`): with 31-45 s left a
market that passes every gate may be bought for half a bet; with <= 30 s left
it is topped up to a full bet if the gate still passes; if belief collapsed
first the hedge pass covers the half. `staged_take()`; records carry `leg`.
Also fixes AMENDMENT 45 so the paper path widens too (the first version
widened only live orders).

Revert (code only; live bot unaffected until its next restart):

```powershell
cd C:\kals-repo
git checkout bc05d04 -- research/pinrun.py research/pinattrib.py
```

---

# (NOT DEPLOYED) AMENDMENT 45 -- one-coin depth. FLAG IS OFF LIVE. -- 2026-09-17 13:2xZ

**The live bot's flags did not change and `versioncheck` is clean.** But
`research/pinrun.py` on disk did change, and the live bot restarts from that
file, so this is recorded here. The full self-test passed (exit 0) before the
file was left in place; the paper arm started from it at ~13:25Z.

`--one-coin-depth --one-coin-max 2.0` (refused with `--live`) lets ONE market
take more than SIZE from a deep offer at the same limit, capped by the lowest
of: the multiple x SIZE, the close budget, and the drawdown brake's headroom
`(bank - 0.8 x high-water) / 0.98` -- so a single widened position can never
halt the bot. `one_coin_cap()`; bar in `results/PREREG_onecoin.md`; evidence
in `results/RESULTS_quiet.md`. Operator, 2026-09-17: "Build the one coin
depth" and "The brakes are a whichever comes first, which I'm fine with."

Revert (removes the code; the live bot is unaffected until its next restart):

```powershell
cd C:\kals-repo
git checkout eade429 -- research/pinrun.py
```

---

# v-selfheal -- 2026-09-17 04:22Z -- the bot relaunches itself until it works, and the operator gets buttons

**Operator instruction, 2026-09-17: "Does the bot automatically catch itself
being down and relaunch until it works? If not it should. Tonight has
maintenance 3-5am it should auto fire back up when it's done without you or I
needing to do anything. Also ... a program on my desktop and I can click start
pause and stop."**

**The bot's own flags did NOT change** (`versioncheck` clean). What changed is
everything around it:

- `watch_bot.ps1` (rewritten, swapped in at 04:22Z, pid 507780): checks every
  30 s; 4 quick restarts per 15 min, then one every 3 min FOREVER (it used to
  stop for good after 4 in an hour -- during a 2-hour exchange outage that gave
  up in the first 10 minutes). A bot alive but silent 25 min is restarted as
  hung. A money-brake halt (loss COUNT / loss abort / DRAWDOWN) waits 15 min
  before the first relaunch. A stand-down flag `results\pinrun-live.stop`
  stops all relaunching until removed.
- `restart_bot.ps1`: the "is it holding a bet" check is now
  `research\pinflat.py`. The old count (filled orders > settled records)
  DEADLOCKED when the bot died holding a bet: the settled record never came,
  so the restart refused forever, every minute. pinflat reads each open
  fill's close time from its ticker: dead + market closed = flat.
- `boot_all.ps1` + scheduled task **KalsBoot** (at logon +1 min, and every 10
  min all day): starts whatever is missing -- run_all.ps1 (collectors),
  watch_bot.ps1, cdc_record, the paper arms -- and refuses to start collectors
  if any python process hides its command line (the 2026-09-14 lesson).
  Nothing starts the LIVE bot except watch_bot -> restart_bot.
- `research\pindesk.py`, desktop shortcut **Pin Bot**: START / PAUSE / STOP,
  status, health, money, trades, days, losses, logs. PAUSE waits for open bets
  to settle before stopping; STOP asks first if a bet is open. Both set the
  stand-down flag so the watchdog does not undo them.

**Amended 05:1xZ the same night -- THE TICKER'S CLOCK IS EASTERN.**
`KXXRP15M-26SEP170000-00` settled at 04:00:20Z: "26SEP17 0000" is midnight
ET. The first `pinflat.close_epoch` read it as UTC and put every close FOUR
HOURS EARLY, so its "dead bot + market already closed = flat" rule would have
called a market closed while it still had up to four hours to run. Caught
because the app's day totals did not match the operator's ($63.75 vs his
$85.11 for Sep 16; correct now, $85.10). Fixed in `pinflat.close_epoch` with
`downtime.et_offset`, self-test pins 26SEP161000 -> 14:00Z and a January
ticker -> +5 h. `pindesk` gained the operator's second round the same night:
% returns, sortable columns, an interactive chart, a "What's this?" mode,
per-row stories, a Market tab, hedge verdicts and a System tab.

**What it cannot do:** bring the machine back from a reboot while nobody is
signed in. This account has no auto sign-in and is not an administrator, so a
boot-time task was refused (S4U: access denied). Windows Update's active hours
are 3 PM-9 AM, so no update reboot can land in the 3-5 AM window.

**Evidence:** `pinflat --selftest` (16 checks), `pindesk --selftest` (30
checks), watch_bot `-Once` dry run, boot_all dry run ("all up; nothing to
do"), KalsBoot fired through the scheduler with result 0. No live restart was
performed; the bot (pid 327184) ran through the whole change.

**Revert, copy-pasteable** (puts back the old watchdog policy; the deadlock fix
and the app are harmless to leave):

```powershell
cd C:\kals-repo
git checkout 879f5b4 -- watch_bot.ps1 restart_bot.ps1
Stop-Process -Id (Get-Content results\watch_bot.pid) -Force
Unregister-ScheduledTask -TaskName KalsBoot -Confirm:$false
Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File C:\kals-repo\watch_bot.ps1' -WindowStyle Hidden
```

---

# v-hedge60 -- 2026-09-16 ~14:10Z -- hedge trigger 0.80 -> 0.60

**Operator instruction, 2026-09-16: "Change the hedge trigger immediately".**

`restart_bot.ps1` now passes `--hedge-belief 0.60`.

**What the bot does differently.** The hedge buys the opposite side of a held
position when the model's belief in that position falls below the trigger. At
0.80 it fired on shallow dips that then recovered; at 0.60 it waits for a real
collapse.

**Evidence, all 9 hedge events on file (entry leg and hedge leg rebuilt from the
fills, not from the log's pnl field):**

| when ET | belief | entry | hedge | net |
|---|---|---|---|---|
| 09-12 BTC | 0.89 | +1.87 | -2.97 | -1.09 |
| 09-12 ETH | 0.69 | +0.37 | -5.53 | -5.16 |
| 09-12 ZEC | 0.53 | -10.61 | **+1.98** | -8.63 |
| 09-13 BNB | 0.64 | +2.31 | -3.40 | -1.09 |
| 09-14 BTC | 0.21 | -58.43 | **+24.18** | -34.26 |
| 09-14 HYPE | 0.56 | -59.20 | **+29.30** | -29.90 |
| 09-16 NEAR | 0.77 | +6.78 | -15.99 | -9.21 |
| 09-16 DOGE | 0.49 | +1.68 | -13.83 | -12.15 |

Hedge alone at 0.80: **+$13.78**. Every hedge that SAVED money fired at 0.56 or
below; four of the five that COST money fired at 0.64-0.89. At a 0.60 trigger the
same nine events give **+$41.68**, about $28 better, and BOTH disasters (0.21,
0.56) are still caught.

**The honest caveat:** 9 events, and 0.60 was chosen after seeing them. The
mechanism is the argument: a shallow dip is usually noise, a collapse usually a
real move. 2026-09-14's lesson was that a five-event recommendation got reversed
by its sixth, so this is a live change made on the operator's explicit call, not
a proven threshold.

**Revert, copy-pasteable:**

```powershell
cd C:\kals-repo
(Get-Content restart_bot.ps1) -replace '"--hedge-belief", "0.60"', '"--hedge-belief", "0.80"' | Set-Content restart_bot.ps1
powershell -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```
(or delete the `--hedge-belief` line entirely to return to the 0.80 default)

git SHA at deploy: 50329e2

---

# Live strategy versions — what is running, and how to go back

**Every change to what trades real money is listed here with its git SHA, the
evidence, and the exact command to revert.** Newest first.

---

## HOW TO USE THIS FILE — read before adding a version

**Every change to what trades real money gets an entry here, at the moment it
is deployed, not afterwards.** The log lapsed between 2026-09-11 and
2026-09-13 while eight live changes went out; the back-fill below was written
from git on 2026-09-13 and is thinner than it should be, which is exactly the
cost of letting it lapse.

An entry needs five things and nothing else:

1. **A version tag** `v-<short name>`, and the same tag in the deploy command.
2. **The UTC time it went live** and the **git SHA** it was deployed from.
3. **What changed, in one sentence**, in terms of what the bot now does
   differently.
4. **The evidence**, or the honest absence of it, with the pre-registration
   filename if there is one.
5. **THE EXACT REVERT COMMAND.** Not a description of how to revert. The
   command, copy-pasteable.

`research/versioncheck.py` fails if `restart_bot.ps1` carries a flag that no
entry mentions, so a live change without an entry is caught rather than
remembered. Run it in any session that touches the live bot.

---

## (NOT DEPLOYED) AMENDMENT 41 — after a jump, sigma is doubled at entry AND in the hedge. FLAG IS OFF.

Shipped in code 2026-09-15 02:xxZ, **default OFF**, `--jump-widen` turns it on.
Two paper arms carry it from 02:0xZ: **WIDEN** (today's live minus the jump
gate, plus widening) and **BOTH** (today's live plus widening). Recorded so a
future `--jump-widen` in `restart_bot.ps1` has an entry to match.

**What it would change.** For 5 seconds after any one-second index move of
3 sd or more, in either direction, the model's sigma is multiplied by **2.0**
at both places a position is priced — the entry decision and the hedge's
belief. Every signal records whether it was priced widened.

**What it does that the jump gate cannot.** A40 refuses an ENTRY into a jump.
A41 also lowers the belief in a position we ALREADY HOLD when the index jumps
under it, so the hedge fires sooner. Hedging one tier sooner was measured at
~17c per rescued contract on the tape's 25 losing markets.

**The number that put it in.** Same measurement as A40 — 17,811 jumps, index
alone: the 5-second continuation after a >3 sd second has p90 +4.2 sd (calm
+2.1), p95 +6.7 (+3.2), p99 +15.4 (+7.0). The tail is about twice as wide, so
the multiplier is 2.0 and the window is the 5 s the continuation was measured
over. Neither was tuned on our fills.

**Self-tested mechanism.** On the BTC 05:30 shape — 47 prints below the
strike, then the +18.5 second, 13 s left — doubling sigma moves confidence in
NO from **0.9986 to 0.9327**: from passing the 99.5% gate to nowhere near it.
Also: the factor is exactly 1.0 with the flag off, on a missing sigma or
market, on a jump seven seconds old, and on sub-sd wobbles; both `fair()`
call sites carry it (a held position must be priced by the same model that
bought it); the signal records `widened`.

**Why this is not the dead "scale sigma by k".** That multiplied EVERY
decision and shrank the population without touching the loss rate, because
the error is shape, not width. This multiplies only in the one state where
the shape is measurably wrong. It is symmetric on purpose — a jump in our
favour also widens, which costs a few good entries; a directional drift term
is the refinement, not this version.

**Not deployed. The three-day comparison decides it** (see v-jump).

**TO DEPLOY:** add `"--jump-widen"` after `"--jump-gate"` in
`restart_bot.ps1` and run the restart script. **REVERT:** remove it; the
default is OFF.

---

## v-withdraw — 2026-09-15 04:xxZ — THE BOT TELLS A WITHDRAWAL FROM A LOSS

**Operator-directed.** His words: *"can you code it so it dynamically checks
its own price and knows if it's a withdrawal or a loss? ... once it hits cap
I'll take anything above that every day."*

**The problem it fixes.** The drawdown brake compares the balance to its
all-time high. A withdrawal was **indistinguishable from a catastrophic
loss**: taking $500 out of a $1,500 bank read as *"33% below the high -- STOP
AND LOOK"* and halted the bot. With a daily-withdrawal policy that is a halt
every single day.

**How it knows, without any price feed.** The bot already keeps a running
total of its own settled P&L. Between two balance reads:

```
expected change = realised P&L booked in that interval
actual change   = bank now - bank then
unexplained     = actual - expected
```

A trading loss is *fully explained* -- it IS the realised P&L. Money that moves
with no settlement to account for it came from outside. Negative is a
withdrawal, positive a deposit, and the high-water mark is shifted by that
amount so the brake keeps measuring **trading** and ignores the operator's cash.

**Two guards, both self-tested, both of which would have caused real damage:**

1. **Only when flat.** `autosize_tick` returns early while any position is
   open, so collateral is never mistaken for a withdrawal.
2. **The first tick of a run never classifies.** A restart zeroes the realised
   counter while the bank carries over -- without this, *every restart would
   look like a withdrawal of the entire previous run's profit* and shift the
   high-water mark down by it.

**The floor is $1.00.** Below that it is settlement timing and fees, and stays
classified as trading.

**Worked cases from the self-test:** lose $100 -> trading. Withdraw $500 with
no loss -> withdrawal $500. Lose $100 *and* withdraw $400 -> withdrawal $400,
with the $100 still charged to trading. **Win $200 and withdraw exactly $200
so the bank is flat -> withdrawal $200**, which is the operator's stated daily
policy and would otherwise read as a mysterious nothing.

**ON by default** -- the previous behaviour was a known false alarm, not a
safety feature. `--no-external-detect` restores it.

**REVERT:** add `"--no-external-detect"` to `restart_bot.ps1` and restart, or
`git revert` this commit.

---

## v-jump — 2026-09-15 02:xxZ — DO NOT BUY INTO A JUMP THAT JUST WENT AGAINST US (`6f05769`)

**Operator decision, 2026-09-14 ~21:45 ET.** His words: *"If it earns more
money, do it! But perhaps also have a paper trade version going for each and
both that check if these implementations weren't in (the version running
today) would we earn more. That's the realest check if it's good. We'll
compare all in 3 days and see who has made and lost the most."*

**What the bot now does differently.** `--jump-gate` is on: it refuses a
trade when the settlement index made a one-second move of 3 sd or more
against our side in any of the last 3 seconds.

**The three-day comparison, all auto-sized from the same bank:**

| arm | jump gate | post-jump widening | what it answers |
|---|---|---|---|
| **LIVE** | on | off | — |
| paper CONTROL | off | off | "would today's version have earned more without the gate" |
| paper WIDEN | off | on | the model version alone |
| paper BOTH | on | on | the two together |

Compare on 2026-09-17: net per contract and losses, per arm. The evidence
below is what put it live; the arms are what will keep it live or not.

**REVERT:** drop `"--jump-gate"` from `restart_bot.ps1` and run the restart
script; the default is OFF.

### The entry as it stood before deployment, unedited:

#### (was) AMENDMENT 40 — do not buy into a jump that just went against us. FLAG IS OFF.

Shipped in code 2026-09-15 01:xxZ, **default OFF**, `--jump-gate` turns it on.
A paper arm identical to live plus the flag is running from 01:28Z (pid
1646604). Recorded here so a future `--jump-gate` in `restart_bot.ps1` has an
entry to match.

**What it would change.** Refuse a trade when the settlement index made a
**one-second move of 3 sd or more against our side in any of the last 3
seconds**. Runs after AMENDMENT 38 and before the dump guard; every refusal
records the moves and sigma it saw.

**The mechanism — the first entry-side rule today with one.** Index alone,
17,811 jumps over 1,785 closes: after a >3 sd second, the NEXT five seconds
continue the same way with a tail the model does not have. Share followed by
a further >=5 sd inside 5 s: **7.9%**, vs 2.2% after a calm second and
**1.3% under the Gaussian the model assumes**. p99 of the 5-s continuation:
+15.4 sd vs +7.0 after calm. The median is ~0 — most jumps stop — but the
ones that run are the ones that settle against us.

**The live evidence.** BTC 2026-09-14 05:30 ET, second by second: the index
moved +18.5 (4.5 sd) at :46; we bought NO at :47 with spot +12 over the
strike; the model priced it as survivable, and it was, had it stopped; it ran
+22, +18, +18 more. -$58.43. Across all 359 live fills, a >=3 sd move against
us in the prior 3 s:

| move against us in last 3 s | fills | contracts | net | c/contract | losers |
|---|---|---|---|---|---|
| under +1 sd | 323 | 8,460 | +$223.78 | +2.65c | 8 (2.5%) |
| +1 to +2 sd | 26 | 742 | +$15.26 | +2.06c | 2 (7.7%) |
| +2 to +3 sd | 3 | 60 | +$5.10 | +8.50c | 0 |
| **over +3 sd** | **7** | **180** | **-$65.67** | **-36.48c** | **2 (28.6%)** |

Gate at 3 sd: blocks 7 fills over 7 closes — **5 winners worth $4.92 total,
2 losers worth $70.59**. 2.5 winners given up per loss avoided (every
previously tested entry gate cost 22–44). 2% of contracts. **Both holdout
halves positive**: first 60% +$8.94 net of blocking, last 40% +$56.73.
Bootstrap over the 7 blocked closes: mean -$9.38, 95% [-26.36, +1.11] — the
interval touches zero on 7 closes, and that is the honest limit.

**Why this is different from the four entry rules killed earlier today.**
Those had no mechanism and reversed out of sample. This one's mechanism is
measured on 17,811 independent events; the threshold (3 sd) and lookback (3 s)
were fixed in that measurement BEFORE the fill test was run, so it is not a
search; and it holds on both halves. It catches 2 of 12 live losses — but 27%
of the loss dollars — and does nothing about the no-warning kind (HYPE 16:00,
+0.3 sd, correctly passes).

**Not deployed because it changes what trades and no one has said yes.**

**TO DEPLOY:** add `"--jump-gate"` after `"--depth-ladder"` in
`restart_bot.ps1` and run the restart script. **REVERT:** remove it; the
default is OFF.

**The principled follow-up, not built:** widen the model's sigma for a few
seconds AFTER a jump, by the measured tail ratio. That would refuse the same
entries by lowering confidence, AND fire the hedge sooner on positions held
through a jump. `CURRENT_STATE`'s dead "scale sigma by k" was global; this is
conditional on the one state where the model is measurably wrong.

---

## v-nofloor — 2026-09-14 14:5xZ — NO PERCENTAGE FLOOR AT ALL, AND THE GATE READS THE LADDER

**Operator-directed and urgent.** His words, verbatim: *"I've said it a million
times and I'm tired of saying it. I need it implemented immediately if it's
not. It's number one priority. ... we buy every contract possible starting for
the best price then the next all the way til we max our size. And if we can't
max we do as much as we can. No limit on total coins only total contracts. No
thinking 'is it worth it there's no point in that it's wasted time.' That's how
it needs to function right now. No 10%."*

**What the bot now does differently. Two flags, and the FIRST is the one that
does the work.**

1. **`--min-fill-frac 0`** — the percentage floor is **gone**. `MIN_LEVEL`,
   one contract, is the only floor left at any SIZE.
2. **`--depth-ladder`** (AMENDMENT 37) — the floor, whatever is left of it,
   counts what the LADDER can fill rather than what sits at the best price.

**AND THE SECOND IS NEARLY REDUNDANT ONCE THE FIRST IS ON.** A37 only consults
the ladder when the touch fails the floor, and at a one-contract floor almost
nothing fails it. It is deployed anyway because it is the safety net if the
floor is ever raised again, and because it still catches the genuine dust case
— an ask of 0.02 contracts, which the live log does contain.

**WHY THE FLOOR HAD TO GO, and it is not only the operator's preference.** The
floor was `0.10 x SIZE`, so **it grows with the bank**: 6 contracts at SIZE 58,
**25 at SIZE 250**. It would have refused more and more of the book exactly as
we scaled into it. Five of the eight successful ladder walks on 2026-09-14 had
**fewer than 25** contracts at the best price and would have been refused
outright at SIZE 250.

**Its original justification had already expired.** `MIN_FILL_FRAC`'s own
comment gives two harms — a scrap fill "burns a scale-in slot" and "raises the
improve bar" — and AMENDMENT 17 and AMENDMENT 29 removed both. A29 in
particular lets a partial position be topped up at **any** passing price with
no improvement required, so a 6-contract fill can no longer block a
52-contract top-up. The floor has been a leftover from a replaced world since
2026-09-14 02:0xZ.

**Exposure does not change.** The worst close is still
`MAX_PER_CLOSE x SIZE x 0.98`. A smaller fill is the same bet at the same gate
on fewer contracts; `min(SIZE, offered)` can only LOWER exposure. What changes
is how often the budget actually gets spent.

**The measured counter-argument, and why it is stale.**
`results/RESULTS_levels.md` measured removing the floor as costing 30% of the
money (+15% fills, −35% mean size, −25% contracts). **That was measured before
the order walked the ladder.** In that world a thin touch really did mean a
thin fill; it no longer does. The measurement needs redoing and should not be
quoted against this change as though it still applied.

**Latency: no change.** The extra work A37 does is inside the branch that only
runs when the touch fails the floor, and at a one-contract floor that branch
is almost never entered. The operator's condition — *"if it doesn't cause us to
miss deals because we spend extra time searching all of them"* — is met by
construction.

**Coins are already unlimited.** `CLOSE_BUDGET = True` makes the per-close cap
count **contracts** (`MAX_PER_CLOSE x SIZE`), not coins and not fills. The
fill-count cap survives only behind that flag. Nothing needed changing.

**Self-tested:** at `--min-fill-frac 0` the floor is exactly `MIN_LEVEL` at
SIZE 58 **and** at SIZE 250; zero is never tighter than what it replaces; and
the guard still refuses any value above the 0.50 default, so this flag can only
ever loosen.

**REVERT:** in `restart_bot.ps1` set `"--min-fill-frac", "0.10"` and drop
`"--depth-ladder"`, then run the restart script.

---

## v-against — 2026-09-14 14:2xZ — REFUSE A THIN EDGE WHEN THE PRICE IS ALREADY RUNNING AGAINST US

**Operator-approved.** His words: *"if you mean both on the other side and
under 2c you can block it off. It's only happened 5 times so not worth too much
(it's also 2c not a huge profit) and it caused loss most times."*

**What the bot now does differently.** AMENDMENT 38 refuses a trade when BOTH
hold: the live index sits **1.0 or more one-second moves past the strike on the
side that hurts us**, AND the edge is **under 2c**. Either half alone changes
nothing.

**THE CONJUNCTION IS THE WHOLE RULE.** Both halves were measured separately on
332 live fills and both are bad gates:

| rule | fills blocked | winners given up | losses avoided | winners per loss |
|---|---|---|---|---|
| price against us alone | 15 | 13 (+$27.77) | 2 (−$70.59) | 6.5 |
| edge under 2c alone | 105 (**31% of all trading**) | 102 (+$46.30) | 3 (−$97.33) | 34.0 |
| **both together** | **5** | **4 (+$1.81)** | **1 (−$58.43)** | **4.0** |

Every entry gate previously tested in this project cost **22–44 winning trades
per loss avoided** (`PROJECT_HISTORY`). This one costs 4.

**WHY IT IS DEPLOYED ON FIVE EVENTS, against the usual bar.** The four winners
it refuses are worth **41c, 47c, 56c and 37c — $1.81 between them**, because a
sub-2c edge at 97c is pennies by construction. So the cost of being wrong is
about **$2 a week** and the cost of being right is one **$58** loss. The
argument is the asymmetry, not the significance.

**IT IS NOT EVIDENCE AND MUST NOT BE QUOTED AS ANY.** The loss that motivated
the rule is one of the five, so **+$56.62 describes the past and forecasts
nothing**. `results/PREREG_against.md` holds the bar for judging it forward.

**Note the operator's own correction to my framing**, recorded because he was
right: I called it a mirage on the strength of a bootstrap that straddles zero.
That test asks "is the effect real"; the decision actually facing us is "what
does acting cost if it is not", and the answer is $1.81. Significance was the
wrong tool for the question.

**Self-tested:** all five real fills refused by name and by their own numbers;
the same 05:30 book with a 2.5c edge NOT refused; the same 1.9c edge with spot
on our side NOT refused; a missing strike, spot or sigma never blocks.

**REVERT:** set `AGAINST_ENABLED = False` in `research/pinrun.py` and restart.

---

## v-lossreset — 2026-09-14 14:2xZ — THE LOSS COUNTER RESETS WHEN THE BANK IS WHOLE

**Operator-directed.** His words: *"the loss brakes change automatically
counter should reset when the balance hits the balance where it originally
fell from."*

**What the bot now does differently.** AMENDMENT 39 clears the losing-close
count the moment the bank gets back to the high-water mark it fell from.

**The bug this fixes.** The count only ever went up, and the only thing that
cleared it was a **restart** — so the brake's memory was tied to process
lifetime rather than to money, and restarting the bot laundered two losses
away. It now uses the same definition of "recovered" the drawdown brake uses.

**The one trap, and it is self-tested.** The mark must be read **before**
`write_hwm()` raises it. Reading after would make every tick look like a
recovery and the brake would never hold at all.

**REVERT:** `git revert` this commit, or delete the `_hwm_before` block in
`autosize_tick`.

---

## (SUPERSEDED SAME DAY) the 0.10 hedge trigger proposal — WITHDRAWN

Recorded here because a recommendation was made and reversed inside six hours,
and the reversal is the useful part. On five hedge events the hedge looked like
it had cost −$9.08 and 0.10 looked $9.13 better. The sixth hedge, 05:30 ET on
BTC, **saved $24.18** at a belief of 0.214 — which 0.10 would not have fired
on. Net over six: **0.80 is +$14.26, 0.10 is +$0.05.** The trigger stays at
0.80. Bar for revisiting it is in `results/PREREG_hedge.md`; the floor is 0.30,
never lower.

---

## v-brake2 — 2026-09-14 10:0xZ — THE LOSS BRAKE STOPS AT TWO, NOT THREE (`032c73d`)

**Operator decision, 2026-09-14 ~05:5x ET.** His words: *"Brake should be at
either 1/5 of bank lost, or after 2 losses. Which ever comes first. It should
reset once the bank hits its original size again."*

**What the bot now does differently.** `--max-losses 3` → **`--max-losses 2`**.
The other half of his sentence — 1/5 of bank, resetting at a new high — is
already `MAX_DRAWDOWN = 0.20` against `results/pinrun-hwm.json` and is
unchanged by this entry.

**Evidence: none, and none was asked for.** This is a risk preference, not a
measured threshold, and it is strictly more protective than what it replaces.
Cost is real though: of the ten losing closes in live history, no run has yet
had two losses close enough together for this to bind, so the expected cost is
small but is not zero.

**KNOWN GAP, recorded rather than fixed.** `--max-losses` counts losses **in
the current run**. A restart resets the count to zero, so "two losses" means
two since the bot last started. Every restart therefore hands the brake a
clean slate. The drawdown brake does NOT have this problem — its high-water
mark is on disk and survives restarts.

**Also note `versioncheck.py` did not catch this change.** It tracks flag
PRESENCE for the flags it knows about, and `--max-losses` is not one of them,
so changing 3 to 2 passed clean. Worth widening.

**REVERT:** in `restart_bot.ps1` change `"--max-losses", "2"` back to
`"--max-losses", "3"` and run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`.

---

## (not deployed) AMENDMENT 37 — the depth floor reads the ladder. FLAG IS OFF.

Shipped in code on 2026-09-14, **default OFF**, awaiting the operator's word to
turn on. Recorded here so that a future `--depth-ladder` in `restart_bot.ps1`
has an entry to match.

**What it would change.** `pinrun.py`'s depth floor refuses a market when the
contracts at the **best price** are under `MIN_FILL_FRAC x SIZE`. AMENDMENT 35
taught the ORDER to read the whole ladder but never touched this GATE, so a
market showing 3 contracts at the touch with 1,600 one tick behind — the exact
02:00 SOL shape A35 exists for — is still refused outright. A37 judges the
floor on what `book.buyable()` can actually fill up to `sweep_limit()`.

**Why it is not simply "removing the floor".** Every market it lets through
still faces `edge_floor`, the dump guard, `price_ceiling` and `ev_floor`
unchanged — the ladder check runs strictly before them and waves nothing past.
`take_n` is never reassigned, so the order still sizes through A35's own block
and the SIZE cap is untouched: **the worst close does not move.** A thin touch
in front of a thin LADDER still fails, which is the self-tested null.

**It requires `--sweep-depth` and refuses to start without it** — passing the
gate on ladder depth while the order sized from the touch would buy exactly
the scrap fill AMENDMENT 6 added the floor to prevent.

**Evidence so far:** 63 depth-floor refusals in the live gate audit, **7 of
which (11%) passed edge, EV and the ceiling**. A paper arm carrying only this
flag is running from 2026-09-14 10:0xZ.

**TO DEPLOY:** add `"--depth-ladder"` after `"--sweep-depth"` in
`restart_bot.ps1` and restart.
**REVERT:** remove it; the default is OFF. Code: `git revert` the A37 commit.

---

## v-ladder — 2026-09-14 06:1xZ — ASK FOR THE WHOLE LADDER, NOT JUST THE TOUCH (`d0c3d60`)

**Operator-directed, urgent.** His words: *"It better buy as much as it can
that we allow for the trade. That was unacceptable and has happened a lot …
you're losing me quite a bit of money with this bug."*

**What the bot now does differently.** It sizes each order from every price
level up to its own sweep limit, instead of only the contracts resting at the
single best price.

**The bug.** AMENDMENT 18 raised the LIMIT PRICE we send so a lost race takes
the next level instead of nothing — but left the QUANTITY at
`min(SIZE, touch size)`. So the bot declared itself willing to pay 98c and then
asked for only what sat at the top.

**Live evidence, the 02:00 SOL close.** Best ask 96.3c with **six** contracts;
limit sent 98c; order placed for 6; filled 6; profit **$0.21**. SIZE was 53.
Reconstructed from our own orderbook tape (05:46:24Z snapshot + 63,232 deltas)
at the second the order went out:

| price | contracts |
|---|---|
| 95.8c | 10 |
| 95.9c | 48 |
| 96.0c | 204 |
| 96.4c | 202 |
| **≤ 98c total** | **1,636** |

Replaying that exact book through the fix: **it asks for 53, not 6.**

**Why it is safe to deploy without a paper run** — and it was, deliberately,
against the usual rule. Every extra contract is at a price `sweep_limit()` had
ALREADY approved against the same confidence, edge, ceiling and expected-value
tests. Nothing new is bought; the same decision is simply filled. The order is
still capped by SIZE and by what remains of the close's contract budget, so
**the worst case per close is unchanged**.

**Not a regression.** `take_n = min(SIZE, touch size)` dates from AMENDMENT 6
(`47f399b`), long before this week. What IS new is that `--min-fill-frac 0.10`
lets six-contract fills through at all; at the old floor of 26 that close would
have been refused outright and earned nothing. So the tiny fills are new, the
sizing limitation is old, and the fix addresses the old one.

**Also live:** AMENDMENT 36 — every signal now records the eight book levels it
was looking at and their total, so this class of question is answerable from
the log instead of from a screenshot and a tape replay.

**REVERT:** drop `"--sweep-depth"` from `restart_bot.ps1` and restart; the
default is OFF. Code: `git revert --no-edit af42b1b`.

---

## v-brake20 — 2026-09-14 02:3xZ — DRAWDOWN BRAKE AT 1/5, AND THE OPEN CAP COUNTS CONTRACTS (`07b3004`)

**Operator decision.** *"make it 1/5 of bank or 3 losses whichever comes first.
Then drop the contract size to whatever the new calculated amount is and wait."*

**What the bot now does differently.**

1. **Stops when the bank is 20% below its highest-ever level.** The high-water
   mark lives in `results/pinrun-hwm.json`, so a restart cannot clear it. It
   resets itself when the balance makes a new high — which is the operator's
   own *"reset once the full balance has been restored"*, with no extra logic.
2. **Re-sizes the instant a loss settles**, instead of waiting out the rest of
   a five-minute timer while betting the size a larger bank supported.
3. **The dollar stop can tighten**, not only loosen. It used to follow the
   bank up and never come back down.
4. **The open cap counts CONTRACTS** (`max_positions x SIZE`) rather than the
   number of open trades.

**Why 4 was urgent.** `v-spend` removed the limit on the *number* of fills per
close and cut the depth floor to a tenth of SIZE, so one close can now produce
10–18 small fills. A cap of 3 *positions* would have halted the bot three fills
into every close and throttled the exact buying `v-spend` exists to enable.
Exposure is unchanged: three fills of 52 and eighteen of 8.7 are both at the
cap.

**All three brakes now run together**, answering different questions —
`--loss-abort` "too much this run", `--max-losses 3` "is the model broken", and
the new one "how far off our best". Whichever trips first, stops.

**Walked through a losing streak at $310:** size steps 52 → 47 → 41 as the bank
falls, and the brake trips at 20.5% down after **two typical losing closes**,
ahead of the 3-loss brake.

**Chosen failure modes.** A failed balance read or a missing high-water file
reads as **zero** drawdown, never as a trip. A **withdrawal looks identical to
a trading loss** and will stop the bot — the safe direction, and the halt
message says so.

**No new flags.** `MAX_DRAWDOWN = 0.20` is a constant; `--max-positions 3` is
unchanged in the command and now means 3 × SIZE contracts.

**REVERT:** `git revert --no-edit 07b3004`, then restart.

---

## v-spend — 2026-09-14 02:0xZ — SAME-COIN RE-BUY + TOP-UPS + A TENTH-SIZE DEPTH FLOOR (`6ee8409`)

**Operator decision.** His words: *"definitely allow double coin buys if it's
causing this many losses opportunities"* and *"DEFINITELY buy smaller if it
can't reach the max contract that was the entire point of opening multiple
coins so we can mix the way up to the contract threshold."*

**What the bot now does differently.** Three things, all aimed at one finding:

1. **`--max-per-market 2`** — a close may buy the same coin twice.
2. **`--min-fill-frac 0.10`** — the depth floor drops from half of SIZE to a
   tenth, so a thin book is taken instead of skipped. `MIN_LEVEL` (1 contract)
   is still the hard backstop.
3. **AMENDMENT 29, topping up** — if a market is holding LESS than a full
   SIZE, more of it is taken at any price that passes every ordinary gate,
   with no improve-by requirement. Once a full size is held, the A23 band
   (0.5c–1.0c cheaper) applies again.

**THE MEASUREMENT THAT DECIDED IT.** Over 234 live closes we bought on, the
bot spent **6,639 contracts of an allowed 11,488 — 58%**. The **median close
spent exactly 50%**: one fill, never the second. The unspent half needs a
second market to qualify, and only **6.3%** of scan seconds have one. So the
contract cap was never the binding constraint; the inability to reach it was.
Separately, of 404 closes with a tradeable moment, **170 produced no fill**.

**THE WORST CLOSE DOES NOT MOVE.** It is `MAX_PER_CLOSE x SIZE x 0.98` either
way — about a third of the bank at BANK_BRAKE 3.0. What changes is how often
the budget is actually spent, which is the risk that was already accepted and
was not being taken.

**What protects it.** `rebuy_ok()`: below a full size, a top-up needs nothing
beyond the gates every buy passes; at or above one, a second buy must be
0.5–1.0c cheaper. That band is where the measurement put it — **0.70% losses
at 0.5–1c against 26.09% at 5–10c**, over 398 markets, ordering intact in a
60/40 holdout on close time.

**Two refusals were LIFTED, not deleted** — both `--max-per-market` and
`--min-fill-frac` used to raise `SystemExit` on `--live`, and the old text
plus the reason it moved is written next to each in `pinrun.py`.

**Also in this version, and not a trading change:** paper what-ifs now
auto-size from the bank exactly as live does. They did not, so on 2026-09-14
live ran 52 contracts while all four arms ran 20 and none of their dollar
figures could be compared with live's.

**REVERT:**

```powershell
cd C:\kals-repo
# drop "--max-per-market","2","--improve-max","0.010","--min-fill-frac","0.10"
# from the Start-Process line in restart_bot.ps1, then:
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

The declared defaults in the source are unchanged (`MAX_PER_MARKET` 1,
`MIN_FILL_FRAC` 0.50), so removing the flags restores the old behaviour
exactly. To revert the code as well: `git revert --no-edit 6ee8409`.

---

## v-a24 — 2026-09-13 22:2xZ — AMENDMENT 24: buy the BEST market of the second, not the first one reached (`6d85371`)

**What the bot now does differently.** When two or more markets clear every
gate in the same scan second, it buys the one with the most edge instead of
whichever the loop happened to reach first. Also deployed in the same restart:
AMENDMENT 25, which makes every gate record why it refused a trade (logging
only — it decides nothing).

**Evidence.** `research/pinpick.py` over 13,984 gate-passing candidate rows on
738 closes. Two or more different markets pass in the same second on **6.3%**
of passes; when they do the first one reached is the best-edge one only
**56.3%** of the time, giving up a mean 2.10c of edge and paying 2.21c more.
Replayed one contract per close: **+2.07c → +2.76c per contract with IDENTICAL
loss counts (10 and 10)**. Holdout on close time, last 40% never fitted:
**+1.63c → +2.43c, six losses either way.** Ranking by confidence instead of
edge reaches only +2.19c, so the gain is price and not a riskier appetite.

**Why it adds no risk and loses no race.** The ordering comes from the edge
measured on the *previous* pass, 50ms earlier at 20Hz. Nothing is computed
twice and no order is deferred. The old order was dict insertion order — the
one gate in this bot that was never an EV comparison. Every gate still has to
pass; only the sequence changed.

**What is NOT deployed:** `--max-per-market` (AMENDMENT 23). It pays, but it
concentrates a close on one coin, and the operator's condition was "if it's
good and does not raise risk". Still in a paper what-if against the bar in
`results/PREREG_pin_live_AMENDMENT_23_24.md`.

**REVERT:**

```powershell
cd C:\kals-repo
git revert --no-edit 6d85371
# then remove "--pick", "best" from the Start-Process line in restart_bot.ps1
.\restart_bot.ps1
```

To revert ONLY the scan order without losing the gate instrumentation, drop
`"--pick", "best"` from `restart_bot.ps1` and run `.\restart_bot.ps1`; the
default is `"first"`, which is the old behaviour exactly.

---

## ~~NOT LIVE — AMENDMENT 23~~ — SUPERSEDED 2026-09-14 by `v-spend` above

**This entry is kept, not edited, so the reversal is visible.** A23 went LIVE
about four hours after this was written, by operator decision, once the 58%
budget-utilisation measurement showed the concentration argument below had the
wrong counterfactual: the alternative to "both fills on one coin" is not "one
fill each on two coins", it is "one fill and the rest unspent", because only
6.3% of scan seconds offer a second coin. Everything below was true when
written and is left exactly as it was.

---

**Listed here because the FLAG now exists in `pinrun.py` and a future session
must not mistake "the flag is there" for "it is running".** `MAX_PER_MARKET`
is still 1 on the live bot.

- **AMENDMENT 23 — the re-buy band.** `rebuy_ok()`: a SAME-market second buy
  must be cheaper by at least `IMPROVE_BY` (0.5c) and at most `IMPROVE_MAX`
  (1.0c, `--improve-max`). Only reachable when `--max-per-market` > 1, which is
  still refused on `--live`.
  Paper run: `--max-per-market 2 --improve-max 0.010`.

**Why it is here and not live, when AMENDMENT 24 went live the same evening.**
The operator's condition was *"if it's good and does not raise risk, implement
it."* A23 is good and it DOES raise one risk: the contract budget caps the
dollars on a close either way, but allowing a second fill on the same coin
makes the close more likely to spend that whole budget on ONE outcome instead
of splitting it across two. Same worst case, reached more often. A24 had no
such cost — identical loss counts in both halves of the sample — so it went.

*(AMENDMENT 24 was in a paper what-if alongside this one from 21:5xZ and was
deployed at 22:2xZ; see the v-a24 entry above.)*

Evidence, bars and the strike conditions:
`results/PREREG_pin_live_AMENDMENT_23_24.md`, written before either run took a
fill. Measurements: `research/pinpick.py` (first-vs-best, and the re-buy band
with a 60/40 holdout on close time) and `research/pinwarn.py` (18,653 closes
rebuilt from the index, uncensored, on whether confidence warns before a flip).

**Revert (removes both flags from anything that could use them):**

```powershell
cd C:\kals-repo
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*pinrun*' -and
                ($_.CommandLine -like '*--pick*' -or
                 $_.CommandLine -like '*--max-per-market*')} |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
```

That stops the two paper runs and touches nothing else — the live bot carries
neither flag, and the filter requires one of them.

---

## v-a22 — 2026-09-13 19:3xZ — AMENDMENT 22: a second COIN at the same close is allowed on its own merits

**What changed.** `--improve-scope market`. The improve-by rule no longer
blocks a different coin.

**The operator, watching the live bot take ETH and skip HYPE while the what-if
took HYPE:** *"I would've hoped my bot would grab eth, then when hype looks
like a good buy it'd see that and scoop it up too."*

**What happened at 19:15Z.** The bot filled ETH at 98.0c. HYPE was then offered
at 97.7c with **2.14c of edge — a better trade than the one it took** — and was
refused, because 97.7c is not at least 0.5c below 98.0c.

**Why that is a bug and not a design choice.** AMENDMENT 3 wrote the improve-by
rule for SCALING INTO THE SAME MARKET: *"re-buying at the same level would
double the risk without lowering the average paid."* AMENDMENT 13 then set
`MAX_PER_MARKET = 1`, which forbids re-buying the same market at all. **Since
2026-09-12 the rule has been unable to do the job it was written for.** The
only thing it can still do is block a different coin — which it was never meant
to touch — and AMENDMENT 17, the same day, says a close is capped on CONTRACTS
with *"coins unlimited"*. The rule was silently contradicting it.

**Why this does not add risk, and why it is not the ruler.** The close's
contract budget is unchanged: `MAX_PER_CLOSE * SIZE` either way. Two coins at
47 contracts is the same 94 contracts as one coin at 94 — **identical worst
case**, only which markets get bought changes. And because coins at one close
correlate at rho ~0.8 rather than 1.0, splitting the same budget across two
markets can only reduce the chance that all of it loses together.

That is why this went live directly while the ruler went to a what-if: the
ruler was a statistical bet on a population that is not ours, with a measured
cost in volume. This is a code-reading, its exposure is provably unchanged, and
every trade it adds passes every existing gate.

**Revert:** remove `"--improve-scope","market"` from `restart_bot.ps1`.

---

## v-revert1 — 2026-09-13 18:49Z — AMENDMENTS 20, 20b and 21 REVERTED (operator call)

**What changed.** `--sigma-ruler` and `--pin` removed. Back to the 300-second
ruler and the 0.995 gate. **The sweep (v-a18) stays** — it is separately
evidenced, needs no flag, and is 3 for 3.

**Why.** The operator: *"I have barely seen any trades since I woke up and
cannot see how that's smarter... I'm having a very hard time trusting this new
idea."*

He was right and the measurement backs him, not me:

| | signals per hour |
|---|---|
| today, before the ruler change | **4.21** |
| today, after it | **1.55** |

**A 63% cut in signals.** I had measured that cost in advance — 46.6% of
signals, from re-scoring 619 real ones — and deployed anyway, then tried to
buy the volume back by loosening the gate, which is a second change to fix the
first.

**The asymmetry I should have weighted properly the first time.** The ruler's
COST is measured on our own real signals and is certain. Its BENEFIT is
measured on the index population, and CLAUDE.md rule 5 exists precisely because
that population is not ours — it differs by 31x on the one number we care
about. Certain cost, unproven benefit, no forward evidence after 7 hours. That
is a bad trade whoever proposes it.

**What is NOT concluded.** The ruler may still be right — `RESULTS_ruler.md`,
`RESULTS_calib.md` and `RESULTS_flood.md` all stand, and the model's tails
really are 8x too thin. What is concluded is that it may not be deployed on
index-population evidence alone. It needs a test that costs nothing while it
runs.

**Next step for it, if it is revisited:** score the ruler in SHADOW against
live signals — recompute what it would have said at each real decision and
compare, without touching what trades. That is `pinshadow`'s method applied to
the ruler, and it should have been built before the deploy, not after.

**Revert of the revert:** add back `"--sigma-ruler","maxdown","--pin","0.990"`
in `restart_bot.ps1`.

---

## v-a21 — 2026-09-13 17:0xZ — AMENDMENT 21: the confidence gate 0.995 → 0.990

**What changed.** `--pin 0.990`. The gate the model must clear before a trade
is considered.

**Why it is a partial REVERT, not a new bet.** v-a20b moved this gate without
touching it: a wider ruler lowers every stated confidence, so the same PIN
became a stricter gate overnight. Measured — the new ruler reads a median
**1.167x wider** (2,666 tape samples), and re-scoring **619 real live signals**
through `z -> z/1.167` shows it cost **46.6% of them**. Lowering PIN to 0.990
gives back most of that volume at the same expected money.

**Evidence.** `results/PREREG_ruler.md`, amended before this deploy. Both 0.995
and 0.990 are worth the same expected $/hour; 0.990 keeps 83% of trades against
53%, so it leans a third as hard on the one number rule 5 says cannot be
assumed to transfer — that a loss reduction measured on the index population
applies to fills someone chose to sell US.

**Also recorded:** the index population said tightening 0.995 → 0.998 costs
0.7% of decisions; on real signals it costs 51%. A 70x error. That population
may compare rulers and may NOT count trades.

**`--pin` may only LOWER the gate** — outside [0.95, 0.995] it refuses to
start. Raising it needs a code change and a version entry, not a flag.

**Revert:**

```powershell
# edit restart_bot.ps1: delete the "--pin","0.990" arguments
powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```

---

## v-a20b — 2026-09-13 11:57Z — AMENDMENT 20b: the ruler reads DOWN moves only (`9591ec8`)

**What changed.** The volatility estimate is now `max(downside 300s, downside
1800s)` instead of `max(two-sided 300s, two-sided 3600s)`. The model's claim is
one-sided — the settle lands on its side of the strike — and we lose only when
the index comes in the other way, so a ruler built from both directions spends
half its information on moves that cannot hurt us.

**Evidence.** 45 rulers scored over 108,000 decisions rebuilt from the index
alone (`results/RESULTS_ruler.md`). Beat the ruler deployed 47 minutes earlier
on every axis in both halves: gated loss −48.5% vs −42.3%, sd(z) 0.950 vs
0.919 (1.000 is honest), kurtosis 53.5 vs 69.1, decisions kept −0.9% vs −1.0%.
Bar and kill criterion in `results/PREREG_ruler.md`, including BAR ITEM 4
(hedge frequency) added 12:32Z before anything was scored.

**Known cost, measured 2026-09-13 on the 12:30 PM ET BNB close:** this ruler
read **40% wider** than the old one at that second (0.0271 → 0.0379). A wider
ruler pushes every belief toward 0.5 and the hedge fires below 0.80, so it
makes the hedge fire more readily. That is arithmetic, not a counterfactual —
whether that particular hedge would have fired under the old ruler could NOT be
reconstructed from the tape and is not claimed.

**Revert:**

```powershell
# edit restart_bot.ps1: delete the "--sigma-ruler","maxdown" arguments
powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```

---

## v-a20 — 2026-09-13 11:10Z — AMENDMENT 20: the volatility ruler lengthens (`a988c71`)

**What changed.** `--sigma-ruler max3600`: volatility measured over the larger
of 300s and 3600s instead of 300s alone. **Superseded by v-a20b 47 minutes
later; it took two fills.**

**Evidence.** `results/RESULTS_calib.md` and `results/RESULTS_flood.md`: the
calmer the last five minutes, the MORE often the model blew up (4.28% in the
calmest fifth vs 1.05% in the choppiest, 4.05x, holding out of sample) because
a quiet 300 seconds understates the next minute. Lengthening the ruler
collapsed that gradient from 4.09x to 1.15x and cut kurtosis 132 → 47.

**The deploy failed on my own guard and the bot was down ~4 minutes.** The
self-test asserted `SIGMA_RULER == "live"`, but `main()` applies the flag
BEFORE running the suite. Fixed by asserting the DECLARED default
(`_DEFAULT_SIGMA_RULER`) instead. The same latent bug was in AMENDMENT 19's
guard and was fixed at the same time.

---

## v-a18 — 2026-09-13 09:24Z — AMENDMENT 18: bid up to the gate, not to the ask (`986cc71`)

**What changed.** The IOC limit is now the highest price that still passes the
SAME gate, instead of exactly the ask we saw. When we win the race we still pay
the resting price; when we lose it we take the next level instead of buying
nothing.

**Evidence.** 28.2% of orders filled nothing and it was not latency — filled
and zero-filled orders have the same median latency, 96 ms. A crossing IOC
fills at the RESTING price: 283 of 283 live fills at or below the signalled
price, 76 strictly better, ZERO worse (RUNBOOK CONFIRMED FACTS). 43% of lost
races had a next level still inside the gate at a median +0.20c.
`results/PREREG_sweep.md` holds the bar.

**First three swept fills, all winners:** SOL 6:15 AM ET (85.0→87.0c, +$5.01),
XRP 7:00 AM (95.1→97.5c, +$0.98), BNB 12:30 PM (92.0→92.3c, +$2.30 on the bet
before the hedge). n=3 proves the mechanism, not the economics.

**Revert:** add `"--no-sweep"` to the argument list in `restart_bot.ps1`.

---

## v-brake3 — 2026-09-13 02:26Z — BANK_BRAKE 1.5 → 3.0 (`f04087d`)

Size is `bank / (BANK_BRAKE x 2 x 0.98)`. The worst single close falls from 64%
of bank to 32%. Operator's decision; the reason recorded in the commit is not
the one either of us first gave.

**Revert:** `BANK_BRAKE = 1.5` in `research/pinrun.py`, restart.

---

## v-a17 — 2026-09-13 01:49Z — AMENDMENT 17: a close is capped on CONTRACTS (`3f393ea`)

`MAX_PER_CLOSE x SIZE` contracts per close, coins unlimited, instead of a cap
on the number of fills. Same worst-case exposure under both rules.

**Revert:** set `CLOSE_BUDGET = False`; the old fill-count cap is kept behind
it for exactly this.

---

## v-a16 — 2026-09-12 23:13Z — AMENDMENT 16: SIZE follows the bank (`c0f8e33`)

Size is re-read from `/portfolio/balance` every 300 s while flat, so it grows
and shrinks with the account instead of being a fixed argument. `--size` became
a starting value only.

**Revert:** `--no-auto-size`.

---

## v-hedgefix — 2026-09-12 20:07Z — a partial hedge fill was shrinking the original position (`2ffb40d`)

**A correctness fix, not a strategy change.** A partial hedge fill silently
reduced the ORIGINAL position's settled size, which understated losses fed to
the loss-abort brake. Every loss number computed before this commit is
suspect.

---

## v-a15 — 2026-09-12 18:06Z — AMENDMENT 15: the belief-collapse hedge, threshold 0.80

When the model's belief in a held position falls below 0.80, buy the opposite
side. Recovers about one third of a loss; costs ~$1.29/day at size 20 and saves
money in bad stretches. `results/PREREG_hedge.md` holds the bar.
**On 2026-09-12 the railed holdout showed the base strategy NEGATIVE on 72
unseen hours with the hedge carrying it** (`aa257ce`), which is the single most
important caveat attached to any live version.

**Revert:** `HEDGE_ENABLED = False` in `research/pinrun.py`.

---

## BACK-FILL NOTE

v-a13 (one fill per market) and v-a14 are NOT reconstructed here — they were
deployed while the log was lapsed and the commits do not state deploy times.
`git log --grep "AMENDMENT 13"` is the starting point if either needs reverting.
This gap is the cost of letting the log lapse and is left visible rather than
guessed at.

---

## v-a12a — 2026-09-11 13:25Z — AMENDMENT 12a: scraps accumulate, exposure re-bounded (`9aa2014`)

**Found by auditing my own change rather than admiring it.** A12 said a scrap
fill spends no scale-in slot. With nothing else changed that DOUBLED the worst
case: `MAX_ATTEMPTS_PER_CLOSE` is 8, so eight scraps of 9.99 contracts would
each keep a position and none would spend a slot — **79.9 contracts, $78.32,
against an intended $39.20**, with only the run-wide $130 stake cap as a
backstop. That is a regression I introduced this morning.

**Fix:** scraps ACCUMULATE. Once they add up to a real fill (half our size)
they spend a slot exactly as one fill would. Measured in the self-test by the
only number that matters — contracts filled before the slots run out:

| scrap size | contracts before slots exhaust | intended |
|---|---|---|
| 9.99 | 39.96 | 40 |
| 5.0 | 20.00 | 40 |
| 2.0 | 20.00 | 40 |
| 0.5 | 20.00 | 40 |

and within the 8-attempt cap, 0.02 crumbs still spend **no** slot — the thing
A12 exists for.

**Two of my own test assertions were wrong before this passed**, both recorded
in place rather than quietly edited: I asserted 8 scraps of 9.99 spend 7 slots
(the code gives 4, and the code is right), and that 0.02 crumbs "never" exhaust
the slots (they do, after a thousand; the attempt cap is the real bound).
Asserting a bound that does not exist is worse than not asserting.

Restarted 13:25Z, pid 611172.

---

## v-a12 — 2026-09-11 12:40Z — AMENDMENT 12: a scrap fill is not a slot (`d3e2ef0`)

**What changed:** a fill smaller than half our size (under 10 contracts at size
20) still books its POSITION — it exists, settles and releases like any other —
but no longer spends one of the `MAX_PER_CLOSE` buys for that close and no
longer raises the improve bar. It is written as a `scrap` record. The side is
still recorded, so the both-sides guard holds. Nothing else changed.

**Why:** 2026-09-11 07:00 ET, the bot asked for 20 twice and got **2.0** (BNB)
and **0.02** (BTC) — the offer was gone by the time the order landed — and each
scrap consumed a buy for its close and raised the bar, blocking a real fill
behind it. `MIN_FILL_FRAC` gated what we ask for; nothing gated what we got.
This was already logged as open in SKIM.md ("dust fills burn a scale-in slot").

**Risk:** none to money — a scrap can only lose its own few cents. The change
can only ADD a real fill where a scrap used to block one. Self-tested
structurally (slot booked only when `filled >= _real`, scrap recorded) and on
the arithmetic (at size 20 the line is 10; 2.0 and 0.02 are scraps).

Restarted 12:40Z in the quiet window; pid 602652.

---

## v-a10c — 2026-09-11 12:45Z — the crazy-deal guard was WRONG IN BOTH DIRECTIONS; fixed (`65b0fc2`)

**A second loss (KXSOL15M 12:30Z, −$12.16) went straight through the guard**:
99.508% sure, filled at 59.1¢ — a **29.5¢ discount** — because the rule demanded
≥99.9% confidence. Scoring the guard on all 139 live fills then showed the
other half of the error.

| discount to fair at the FILLED price | fills | lost | loss rate | P&L |
|---|---|---|---|---|
| under 2¢ | 42 | 1 | 2.4% | −$2.11 |
| 2–5¢ | 64 | 2 | 3.1% | −$0.11 |
| **5–15¢** | **24** | **0** | **0.0%** | **+$32.20** |
| **15¢+** | **9** | **4** | **44.4%** | **−$12.41** |

**As deployed the guard cost −$10.49**: it refused 8 winners (+$29.22) to avoid
2 losers (−$18.73). A measurably negative rule does not stay — the operator's
own test.

**Two changes, and their evidence is NOT equal.**
* **Drop the confidence condition — NOT fitted.** The SOL loss proves the
  discount matters independent of confidence, and every trade already passes
  PIN, so "confident" carried no information.
* **5¢ → 15¢ — FITTED, and labelled so.** The 5–15¢ evidence is strong and
  one-directional (0 losses in 24 fills, +$32.20; refusing it was the guard's
  worst error). The 15¢ line itself was chosen after seeing 9 fills. It is kept
  only because no guard is also negative on that band (−$12.41) and because the
  operator decided to refuse deals this extreme. **It claims no significance.
  The pre-registered review at 40 records decides it on data it never saw.**

Restarted 12:45Z, pid 601412. Revert: `DUMP_ENABLED = False`.

---

## v-a10b — 2026-09-11 00:12Z — AMENDMENT 10 ON, BY OPERATOR DECISION; would-be outcomes recorded (`0c5f513`)

**Operator:** *"don't do the 'crazy trades', but track them with the 'would be'
outcome. Later they'll be reviewed when populated with more data. Leave the
program to continue."*

**What changed:** `DUMP_ENABLED = True`. A fill where the model is ≥ 0.999 and the
offer is more than 5¢ below fair is refused. **Every such moment writes one
`dumped` record per (close, market)** — ticker, side, price, fair, tau, discount,
depth — whether or not it is refused, so the would-be P&L resolves against the
settlement later. Everything else is v-pin995.

**The basis, stated exactly:** the EV of this class is **undeterminable** on the
six live fills (+$4.75, mean +$0.79, SE ±$4.1, t = 0.19). On an undeterminable tie
the owner chose fewer losses. **This is a recorded owner decision, not a claim
that refusing is profitable.** The 40-fill evaluation stands: refuse stays only
if the 95% CI on mean would-be P&L is not entirely above zero; if it is, the
class comes back. Cumulative P&L is never the trigger.

**To resolve would-be outcomes:** join `dumped` records to settlements on ticker
— the same join `pinrace.py` does for orders.

**Revert (buy them again):** `DUMP_ENABLED = False`, stop/start per RESTART.md.

Restarted 00:12Z; pid 439076.

---

## v-a10a — 2026-09-10 23:51Z — AMENDMENT 10 SWITCHED TO LOG-ONLY: the math does not support it (`82f2656`)

**What changed:** `DUMP_ENABLED = False`. The guard still COUNTS every fill it
would have refused (`dumped` in the close summary) and refuses none. Trading rule
is back to exactly v-pin995. Live for 13 minutes (23:38–23:51Z); no fill was
refused in that window.

**Why it came off — the operator's rule, applied:** *if it is profitable do it,
if not don't; if the math is not certain, don't use it.* The six live fills of
this class: +15.36, +3.78, +2.82, +1.52, −16.61, −2.12 = **+$4.75, mean
+$0.79/fill, standard error ±$4.1, t = 0.19. The sign is not determinable.**
Refusing is not certifiably profitable; neither is buying. The frozen baseline
(buy) therefore stands. v-a10 was deployed on a loss-frequency preference
dressed as a decision, and that was wrong.

**The metric, settled:** `CLAUDE.md`'s own kill criterion defines "consistent"
as positive expectancy. Variance matters only through ruin, and this class
cannot cause ruin at size 20 (≤ $19.60 per fill, brakes intact). So the
criterion is EV alone; EV is unknown; the class is ~3 fills/day, so the decision
is worth ~$2/day either way and does not merit a rule until it can be measured.

**PRE-REGISTERED EVALUATION, fixed now:** at **40 fills** of this class (model
≥ 0.999 and offer > 5¢ below fair), refuse only if the 95% CI on their mean P&L
lies entirely below zero; keep only if entirely above; otherwise re-evaluate at
80. **Cumulative P&L is not a trigger** — a bar moved by outcomes is not a bar.

**Revert to v-a10 (refusing):** `DUMP_ENABLED = True`, stop/start per RESTART.md.

Restarted 23:51Z in the quiet window after the 23:45 settlement; pid 445008.

---

## v-a10 — 2026-09-10 23:38Z — AMENDMENT 10: never buy a certainty at a discount (`fdd581e`)

**What changed in `pinrun.py`:** after the edge floor, a fill is refused when the
model's confidence is ≥ 0.999 (3.09 sd) AND the offer sits more than 5¢ below the
model's fair value. Counted in the close summary as `dumped`. Nothing else: size
20, gate 0.995, ceiling 98.0¢, tau 3–30, brakes unchanged.

**Why (live fills only, both gates — `fair()` is identical in both):** 14 fills at
≥4 sd. The 8 priced 94¢+ went 8–0. The 6 priced below — 8¢ to 90¢ discounts on a
"certainty" — went 4–2, and both losses were the same reconstructed event: the
book sold us the certain side cheap and the index jumped 10–18 sigma within a
second. The model puts that at ~1e−9. A trade whose EV rests on that tail is a
trade whose EV cannot be estimated, so it is removed.

**Not a fitted threshold:** any discount cut from 6.2¢ to 8.1¢ gives the same
live result; 5¢ is the conservative side and ~17× the edge floor.

**Cost on the live record:** forgoes SOL +$15.36, DOGE +$3.78, ETH +$2.82, SOL
+$1.52; avoids XRP −$16.61, DOGE −$2.12. **EV ≈ neutral (−$4.75 over 111 fills);
loss frequency down by the whole class.** The operator's stated preference, and
the definition of consistent.

**The one thing the operator asked that this answers:** *"why can't we just not
buy the crazy 'deals' that basically always end up being someone knowing what's
happening?"* We now don't.

**Revert:** set `DUMP_DISCOUNT = 9.0` (never trips) or `git checkout fdd581e --
research/pinrun.py`, then stop/start per `RESTART.md`.

Restarted 23:38Z in the quiet window after the 23:30 settlement; pid 442440.

---

## v-pin995 — 2026-09-10 08:4xZ — AMENDMENT 9: the confidence gate 0.98 → 0.995 (`184c826`)

**THE BAR MOVED. Loud, dated, and with the evidence beside it.**

**What changed in `pinrun.py`:** `PIN = 0.995` (was 0.98). The bot now needs the
model at 99.5% — a margin of **2.58 sd** instead of 2.05 — before it will buy.
Nothing else: size 20, 2 buys per close, ceiling 98.0¢, tau 3–30, brakes −$60 /
3 losing closes / 2 order errors / 8 attempts.

**Evidence (`research/pinfirst.py`, 10,796 markets walked tau 30→3, flip rate
measured AT THE SECOND THE BOT FIRES, fit/holdout over closes):**

| margin at fill | markets | flips | rate | holdout |
|---|---|---|---|---|
| 2.05–2.3 sd | 502 | 9 | 1.79% | 2.51% → 1.38% (bands pooled) |
| 2.3–2.6 sd | 195 | 6 | 3.08% | |
| 2.6–4 sd | 594 | 3 | 0.51% | 0.74% → 0% |
| 4+ sd | 7,868 | 0 | [0, 0.05%] | 0 → 0 of 2,500 |

Flips at the crossing 18 → 10 at 0.995; holdout 3 → 1; 9,151 of 9,159 markets
still reach 0.995 inside the window. On the 84 live fills: skips 3 of the 5
losses (NEAR ×2, BNB — all fired at 2.09–2.25 sd), keeps every deep win,
keeps 43 fills.

**What is NOT known:** the fill count. Deeper markets are priced higher, so
the same number of opportunities may fill less often. The next 24 h measures
that. The operator's standing want is MORE bets; tonight's want was FEWER
losses, and this trades one for the other on evidence.

**Revert:**
```powershell
# research/pinrun.py line "PIN = 0.995"  ->  "PIN = 0.98", then stop/start per RESTART.md
git checkout 184c826 -- research/pinrun.py
```

Restarted during the maintenance halt; pid 246096.

---

## v-cond — 2026-09-10 07:47Z — conditions logged on every decision (`2994b55`)

**What changed in `pinrun.py`:** every `signal` record now carries `cond_x`,
`cond_n`, `cond_own` (see `IndexWS.conditions`). Tick retention 1200s → 4000s
so the 3600s baseline is real. A per-feed, per-second cache keyed on a version
counter (a revised print busts it, an identical duplicate does not).
**Nothing about what is bought, at what price, or in what size changed.**
Price ceiling, gates, brakes, size: identical to the previous version.

**Evidence:** `research/pintail.py` — the model's loss-tail is 2.22% with no
other coin moving and 6.60% with three or more (9,159 markets). Every fixed
gate on it failed a holdout split, so it is **logged, not gated**.

**Cost on the order path:** `conditions()` runs only when a signal fires;
~0.5 ms cached, 6 ms cold once per second. Measured.

**Revert:**
```powershell
git checkout 33ead84 -- research/pinrun.py
# then stop/start per RESTART.md
```

**Restart done during the exchange's maintenance halt** (`trading_active:
false`, all shards) — trader down 07:43–07:47Z, zero opportunity cost.
pid 245640, size 20, brake at 3 losing closes.

---

## OUTAGE — 2026-09-08 14:40–15:44 UTC, ~1 hour, NO TRADING

**Cause:** three separate hardcoded rails silently refused every scale-up, and
I verified the process *started* rather than that it *survived*.

1. `pinrun` refused `--loss-abort` outside `[-5.00, 0.00)`. The −$10 (v5) and
   −$15 (v6) values were rejected and the process **exited immediately**.
2. `pinrun` refused `--max-positions > 3`. I passed 4.
3. `pintake.MAX_TAKE_COUNT` was **1 contract**, and `MAX_RUN_STAKE` was $5 —
   less than a single size-8 buy (~$7.60). So even with (1) and (2) fixed,
   **size 3 and size 8 would both have been refused at the order stage.**

**The operator noticed before I did** ("No bets have been bought since we upped
it"). The lesson is recorded, not just the fix: **check that a process is still
alive after it starts, and that its orders are accepted, before believing a
deployment.**

**Fixes:** the loss abort now **scales with size** (allowed range is roughly 2–4
ordinary losses at whatever size is trading) instead of a flat cap that was
right at size 1 and fatal at size 8. Order rails raised deliberately with the
reasoning in the source: `MAX_TAKE_COUNT` 1 → 10 (~8% of the median 125
resting at the touch), `HARD_MAX` 5 → 25, `MAX_RUN_STAKE` $5 → $60.

**`pintake`'s own self-test also had to be fixed** — it asserted "count 2 must
be refused", which was correct when the rail was 1 and became a *false alarm*
the moment it was raised. The rail tests are now written **relative to the
constants**, so they stay meaningful at any setting.

---

## v14 — CURRENT (2026-09-08 22:47 UTC) — funded, size 20, cap 3

| setting | value |
|---|---|
| **bank** | **$154.33**, all on the Crypto shard |
| size | **20 contracts** |
| buys per close | **3**, each ≥0.5¢ cheaper than the last |
| partial fills | down to 50% of size |
| price ceiling | 98.8¢ |
| worst case, one close | $60 |
| dollar brake | −$90 |
| **loss-count brake** | **3 losing trades** |
| **attempts per close** | **8**, separate from the 3-fill cap |
| max open positions | 4 |
| pid / code sha | 4074664 / `e4cdb6320807` |

The operator funded the account. The $150 landed on exchange_index 0, where it
could not have bought anything, and $113.0360 was moved to the Crypto shard.

---

## THE RUNAWAY — 2026-09-08 22:44:30Z, 160 refused orders in one second

**No money lost. Balance unchanged, zero fills, zero open positions.** Caught by
the monitor and stopped within seconds.

**Two of my own changes collided, and neither was wrong alone.**

1. **`pintake.MAX_TAKE_COUNT` was still 10**, so every order at size 20 was
   silently refused. **The FOURTH size-1 literal to break scaling in one day**,
   after the loss-abort range, the run-stake cap and the stake release.
   `take()` *returns* its violations rather than raising, so nothing noticed:
   the order records carry `status_code: null`, `parsed: false`, `error: null`.
2. **AMENDMENT 6 had just stopped a no-fill from consuming a scale-in slot.**
   That is correct — an unfilled order creates no exposure — and it earned
   +27.96¢ within five minutes of deployment. But it left **nothing bounding
   how many times we may try**, so a permanently refused order retried at 20 Hz
   forever.

**Fills and attempts needed separate budgets and only had one.**

### Three fixes

| | |
|---|---|
| `set_limits()` now raises `MAX_TAKE_COUNT` too | and `HARD_MAX` with it, announced, never silently. Still refuses to lower either. |
| a returned refusal is now an **error** | `order_errors` increments, so two in a row halt the run |
| `MAX_ATTEMPTS_PER_CLOSE = 8` | counted **before** the send, so a call that never returns still consumes one |

**Verified against the production endpoint without sending:** `check_take` at
size 20 returned `['count 20.0 exceeds MAX_TAKE_COUNT 10.0']` before the fix and
`[]` after.

### The lesson, and it is the second time today

I verified the process **started** and that its start record described the right
configuration. **I did not verify that an order at the new size would be
ACCEPTED.** That is one function call, no network, no money, and it is now part
of every deployment. *"The process is alive"* and *"the process can trade"* are
different claims.

---

## v13 — 2026-09-08 22:15 UTC — cap 2 → 3

**Withdrawn, then reinstated at the operator's instruction** (*"if you know the
idea works then do it"*). It is **not a new mechanism**: the scale-in rule has
been live since v3 and has produced second buys on real closes. Cap 3 only lets
the same proven rule repeat once more, and **the trade it adds is the cheapest
of the close** — every extra buy must clear `IMPROVE_BY`, so a third buy is at
least 1.0¢ below the first. Cheaper wins more *and* loses less, so cap 3 cannot
degrade the average price paid. Structurally, not merely empirically.

Measured with losses injected per close at the 2.31% exact upper bound:

| | typical result | ruined |
|---|---|---|
| size 20, cap 2 | $271 | 3.4% |
| **size 20, cap 3** | **$304** | **1.1%** |

**12% more money and a third of the ruin.** What it costs is exposure, not
per-contract risk.

**The self-test found the deployment bug for free.** With `--max-positions 3`,
the third buy plus a straggler still settling from the previous close would have
been silently refused. The flag is now 4.

---

## v11 — 2026-09-08 21:39 UTC — MORE BETS, same maximum exposure

| setting | value |
|---|---|
| size | 10 contracts |
| **partial fills** | **take `min(size, offered)` down to 50% of size** |
| **scale-in slot** | **consumed by a FILL, never by an attempt** |
| price ceiling | 98.8¢ |
| loss abort | −$30.00 |
| pid / code sha | 4052684 / `792ee01f2153` |

**Neither change raises the maximum exposure of a close.** That was the
constraint, because the balance cannot fund more.

### Change 1 — a no-fill no longer burns a scale-in slot: +33.3%

`fired[close_s]` was written when the SIGNAL fired, *before* the order was
sent, so an order filling **zero** contracts still burned one of the two
allowed buys and still raised the improve bar. **5 of our first 19 live orders
filled nothing**, and depth was not the cause — the misses had 562, 107, 93, 10
and 5 contracts on offer. Lost races, not thin books, so they recur.

| at the observed 26% miss rate | closes won | buys | expected |
|---|---|---|---|
| no-fill BURNS a slot (before) | 67 | 87 | $40.29 |
| **no-fill keeps the slot** | **80** | **119** | **$53.72** |

**Max exposure unchanged** — the cap always meant two *fills*; the bug made it
two *attempts*.

### Change 2 — take a partial down to half size: +1.3% at size 10, +5.4% at 25

| threshold | buys | expected |
|---|---|---|
| full size only (before) | 124 | $59.75 |
| **≥50% of size** | **125** | **$60.53** |
| ≥5% of size | 129 | $58.37 |

**Taking any scrap is worse than taking none:** a tiny early fill burns a slot
and raises the improve bar, trading a big cheap buy later for a small dear one
now. Half is the measured optimum at both sizes. Exposure can only fall.

### MEASURED AND REJECTED: `MAX_PER_CLOSE` 2 → 3

**+26.7%, larger than either change above, and NOT deployed because it cannot
be funded.** Worst close $30 against a $38.83 balance, and the rail would need
a brake at −$45 or looser. **This is the best available change the moment the
account is funded.**

### Three self-tests were inspecting themselves

`src.index("def trade_loop(")` matched this test file's OWN string literal,
because `selftest()` is defined above `trade_loop`. Every structural check
built on it was reading the test instead of the code and could have passed
vacuously. All three now anchor on a newline.

**Revert:** `MIN_FILL_FRAC = 1.0`, and move `_book_slot()` back above the order.
**Pre-registration:** `results/PREREG_pin_live_AMENDMENT_6.md`.

---

## v10 — 2026-09-08 21:14 UTC — size 10, and two silent killers removed

| setting | value |
|---|---|
| size | **10 contracts** |
| price ceiling | 98.8¢ |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | **−$30.00**, and the order path now agrees |
| pid / code sha | 4056648 / `497c2f96b280` |

### First size-10 trade: +103.14¢, more than the whole day before it

```
21:30Z close   KXBTC15M  tau=7s  buy NO @0.8900  fair 0.00256  edge +10.058c
1,000 contracts on offer, we took 10
filled 10.0 @ 0.89, fee $0.0680  ->  settled NO, payout $10.00
stake $8.9000 + fee $0.0680      profit +$1.0314   = 11.59% on stake
```

**89¢ is the cheapest price we have ever paid**, and the cheapest price wins
more *and* loses less. Break-even at 89¢ is an 11% error rate; ours is 0.90%.

### Two size-1 literals were silently disarming the trader — found by audit

1. **The stake release gave back ONE contract instead of the whole fill.**
   pintake commits `filled × price`; reconcile released bare `price`. At size 5
   that stranded $3.90 per settled trade, turning the $60 run-stake cap back
   into a **cap on lifetime turnover** — every order refused after ~15 fills,
   6 at size 10. `take()` *returns* the refusal rather than raising, so nothing
   halted and nothing logged. Two give-up branches released **nothing at all**.
2. **`pintake.LOSS_ABORT` was a hard −$2.00.** One ordinary loss at size 5 is
   −$4.88, so **the first loss we ever took would have shut off all trading**,
   silently, while the −$21 brake sat untouched.

**Fixes:** a single `_release()` used on all three exit paths, releasing
`cost × contracts`; P&L booked on contracts actually filled; and
`pintake.set_limits()`, which raises the order-path rails to agree with the
run's own brake and **refuses to tighten**.

**The self-tests now sweep sizes 1, 5, 8, 10, 25**, include a positive
assertion that a one-contract release at size 5 leaks $3.90 so they cannot pass
vacuously, and scan the source to require every exit path to release.

### Depth tracking added

`close_summary` now carries min/p25/median/p75/max/total contracts offered
across every moment we could have bought, plus how many survive at each
candidate size. Early readings: **median 530 contracts** on one close, **101**
on another, with 414 moments surviving size 10.

**Revert:** `--size 5 --loss-abort -21.00`.
**Revert trigger:** any fill above 98.8¢, or a flip rate above 2.31%.

---

## v9 — CURRENT (2026-09-08 16:36 UTC) — back to a 98.8¢ ceiling

| setting | value |
|---|---|
| **price ceiling** | **98.8¢** |
| size | 5 contracts |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | −$21.00 |
| pid / code sha | 3997812 / `d6826548c653` |

---

## v8 — 96¢ CEILING. IT *WAS* LIVE, IT SUPPRESSED TRADING, AND I TWICE GOT THE STORY WRONG

**This entry has been wrong twice. Both wrong versions are described here rather
than deleted, because the failure mode is the lesson.**

### Wrong version 1 (16:35 UTC): "v8 is live and it is safer AND more profitable"

Two of the three claims did not hold. Total realised profit goes DOWN when you
tighten (742.0¢ → 724.9¢); it only rises in EXPECTATION at an assumed 0.90%
flip rate (625.9¢ → 649.3¢). And "the dear trades were never paying for the
risk" was never measured — there are **zero flips in the entire eligible
sample at every ceiling**, and the 96–98.8¢ band realised **+2.087¢ per
contract** over 784 moments. I stated a model output as a measurement.

### Wrong version 2 (16:20 UTC): "the 96¢ ceiling was never live"

**Also wrong, and worse, because I acted on it.** I read the live process's own
start record, saw `"price_ceiling": 0.988`, and concluded the change had never
been applied.

**That field was DERIVED, not the constant.** The line was:

```python
price_ceiling=round(1.0 - MEASURED_FLIP - EV_FLOOR, 4)   #  = 0.988, ALWAYS
```

It reports the ceiling the EV arithmetic *implies*. It never read
`PRICE_CEILING` at all. **A process running a 96¢ ceiling truthfully logged
98.8¢.** My "verify what the process logged, not what the source says" rule was
right in principle and I applied it to a field that could not answer the
question.

### What actually gave it away — the operator noticed the symptom first

The operator said "haven't seen a trade in a while." The 16:30Z close then
showed this:

```
close 16:30Z  4,264 looks  954 tradeable  fired: FALSE
best: KXBTC15M NO @ 96.6c  edge +2.891c  tau 28s  665.71 contracts on offer
```

Every gate in the code on disk passes that moment: edge 2.891¢ ≥ 0.3¢,
EV 2.270¢ ≥ 0.3¢, price 96.6¢ ≤ 98.8¢. **The only rule that rejects 96.6¢ is a
96¢ ceiling.** Behaviour, not logs, proved it was live.

### Cost

Live signal history: **12 of our 16 real signals were above 96¢** (mean price
paid 97.61¢). The 96¢ ceiling was refusing roughly three quarters of our
trades, against a backtest that predicted it would refuse 30%.

### Two fixes, both in `pinrun.py`

1. **The start record now logs `PRICE_CEILING` itself**, with the derived value
   kept alongside as `ev_implied_ceiling`, plus a `code_sha` fingerprint of the
   running file. A log line can no longer describe code that is not running.
2. **`close_summary` now emits `over_ceiling` and `neg_ev`.** Both counters
   existed and neither was reported, so the refusal was invisible in the log
   that was written specifically to explain refusals.

### The standing rule this replaces

*"Check what the process logged at start"* is not enough. **A configuration
check must read a field that is derived from the constant it claims to
describe — and the way to prove a rule is live is to find a moment it changed
the behaviour.**

---

## v7 — 2026-09-08 16:12 UTC

| setting | value |
|---|---|
| size | **5 contracts** per buy |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| EV gate | ≥0.3¢ at 0.90% flip rate → ceiling 98.8¢ |
| worst case per close | **$10.00** |
| loss abort | **−$21.00** → survives 2.1 bad closes |

### First size-8 trade: WON +49.34¢

```
KXHYPE15M  tau=9s  buy NO @0.9350  fair 0.0103  edge +5.04c  size on offer 34
filled 8.0 @ 0.934, fee $0.0346  ->  settled, payout $8.00
stake $7.4720 + fee $0.0346 = $7.5066   profit +$0.4934   = 6.6% on stake
crypto shard $38.2157 -> $38.7091, reconciles exactly
```

**The rebuilt order rails work end to end at size 8.**

### The safety system caught two configuration errors in ten minutes

**1. Self-halt after the fill (correct).**
```
HALT: realised $+0.00 with $7.47 still open; one more contract
      could take this run past $-15.00
```
Size 8 with 2 buys can commit ~$16 against a −$15 brake. **The configuration
was self-contradictory** and the forward-looking loss bound refused to enter a
state where the brake could be breached. Exactly the right behaviour.

**2. The deployment rail then refused −$21 at size 5 — right call, wrong
arithmetic.** It sized the abort against **one contract** when a close can buy
**MAX_PER_CLOSE** of them. Fixed to use `size × MAX_PER_CLOSE` as the unit of
loss, because **the unit of loss is a CLOSE, not a contract**.

### The pattern, now explicit

This is the **third** time today a limit set for a size-1 proof silently
blocked scaling: the loss-abort range, `pintake`'s 1-contract order cap and $5
run stake, and now the abort's unit of measure. Every one of them was *correct
for size 1* and wrong afterwards.

**Rule going forward: any constant tied to size must be expressed in terms of
size, never as a literal.**

---

## v6 @ size 1 — CURRENT (2026-09-08 15:47 UTC)

| setting | value |
|---|---|
| window | tau 3–**30** s |
| model gate | p_flip ≤ 0.02 |
| EV gate | ≥0.3¢ expected at 0.90% flip rate → ceiling **98.8¢** |
| size | **1 contract** |
| buys per close | up to **2**, second only if ≥0.5¢ cheaper |
| max exposure/close | ~$1.90 |
| loss abort | −$3.00 |

**Deployed at size 1 deliberately.** The operator's instruction: only go one
step beyond a *proven* version, and only if each change passed its historic
test and its failure would be identifiable.

**Each change passed:**
- EV gate — 5 of 7 live trades were negative-EV; break-even price = 1−f is exact
- scale-in — 70 closes, 4.18¢ → 7.43¢/close, average price paid FELL
- tau 30 — 0 flips in 2,872 moments across 118 closes at tau 21–30

**Each failure is distinguishable:**
| symptom | cause | fix |
|---|---|---|
| flips on trades at tau > 20 | v4 | `--tau-max 20` |
| second buy at a WORSE price than the first | v3 | `MAX_PER_CLOSE = 1` |
| any fill above ~98.7¢ | EV gate not binding | check `MEASURED_FLIP` |
| flip rate > 2.31% | the whole ceiling is wrong | re-derive every threshold |

**Size stays at 1 until this version has traded and won on its own.** Scaling
is a separate, later decision — it does not accelerate learning, only exposure.

---

## v4 — 2026-09-08 15:20 UTC — SHA `45966b9`

Window **20 → 30 seconds**. Model calibration measured by horizon: 0 flips in
5,219 moments below tau 30; 3.7× overconfident at 31–45; **10.9× at 46–60**.
The overconfidence is entirely a long-horizon effect, which also explains why
the `tau<=60` backtest cell was dead. Roughly doubles qualifying moments.

**Revert:** set `TAU_MAX = 20`.
**Revert trigger:** any flip on a trade at tau > 20 → review; a second → revert.

---

## v3 — 2026-09-08 15:00 UTC — SHA `d04647d`

**Scale in as the price improves**: up to 2 buys per close, the second only at
≥0.5¢ better. Measured 4.18¢ → 8.87¢ per opportunity, average price paid FELL
95.53¢ → 94.28¢. Waiting instead is strictly worse (skipping one tick missed 7
of 70 closes).

**Revert:** `MAX_PER_CLOSE = 1`.
**Revert trigger:** average fill price across a close exceeding the first
fill's price over 50+ closes.

---

## v2 — 2026-09-08 11:35 UTC — SHA `c3aca51`

**EV gate.** Replaced "model edge ≥ floor" with `EV = (1−f)(1−p) − f·p − fee ≥
0.3¢` at the **measured** 0.90% flip rate, implying a price ceiling near 98.5¢.
Found because 5 of the first 7 live trades were negative-EV: breakeven price is
exactly `1 − f = 99.1¢`, and the model's own fair value implied 0.06% error
where reality is 0.90%.

Effect: profit per trade 1.41¢ → 3.42¢.

**Revert:** remove the `expected_value` check.

---

## v1 — 2026-09-08 08:20 UTC — SHA `2489d73`

**Edge floor 0.5¢ → 0.3¢.** Out of sample the looser floor gave 389 closes /
+2.76¢ / t=+5.6 / 1 flip in 359, against 354 / +2.51¢ / t=+4.1 / 3 flips in 333.

**Revert:** `EDGE_FLOOR = 0.005`.
**Revert trigger:** live flip rate ≥ 1.0%.

---

## v0 — 2026-09-08 07:09 UTC — first live version

tau 3–20, fair ≥0.98/≤0.02, edge ≥0.5¢, one buy per close, size 1,
loss abort −$3.00. First real trade 08:00Z (BTC YES @0.992, won +0.74¢).

---

## Running record

| | |
|---|---|
| won / **lost** | **29 / 3** |
| live flip rate | **9.4%** (3 of 32) — see the caveat below |
| bank | **$110.33** |
| day | started $38.83, funded +$113.04, now $110.33 = **−$41.54** |
| best single close | +$2.52 (three fills) |
| best single trade | +185.51¢ (SOL at 90.1¢) |
| **worst single close** | **−$52.60** (three fills, ONE market, all lost together) |

### THE FIRST LOSS — 2026-09-09 00:45Z, KXNEAR15M

Three same-side buys on **one market** at tau 22 / 21 / 17, 96.2¢ / 95.6¢ /
73.0¢, all lost together. The loss-count brake halted the run. Settlement was
reproduced independently from the raw index and agrees with the exchange, so
**the arithmetic is not broken**. The index sat flat for eight seconds, then
moved 0.0021 in a single second at tau 16 and never came back.

**A six-agent forensic investigation refuted nearly every proposed fix,
including my own.** Flatness, sigma regime and recent-jump separate losers from
winners at p = 0.14–0.99; once the model's own `z` is held fixed, nothing adds
anything. Every entry gate tested costs **22–44 winning trades per loss
avoided**. See AMENDMENT 8 and IDEAS_LOG.

**The live flip rate of 9.4% is 3 losses in one correlated close, not 3
independent events.** Clustered by close it is 1 losing close in 20, and the
sample is far too small either way. It does NOT yet exceed the 2.31% bound that
would kill the strategy, because that bound is per-trade on independent draws
and these were not independent. **This is exactly why the brake now counts
closes.**

## What to check first if it starts losing

1. **Flip rate by tau.** If flips appear above tau 20, v4 is the cause — revert
   to `TAU_MAX = 20`.
2. **Average fill price per close.** If the second buy is coming at *worse*
   prices, v3's mechanism has reversed — set `MAX_PER_CLOSE = 1`.
3. **Prices paid.** If trades are appearing above 98.5¢, the EV gate is not
   binding — check `MEASURED_FLIP` and `EV_FLOOR`.
4. **The measured flip rate itself.** Everything above is built on 0.90% from
   3 flips in 333. If the live rate exceeds 2.31% (the EXACT one-sided 95%
   Clopper-Pearson bound; the 1.80% figure quoted until 2026-09-08 was a normal
   approximation and is optimistic by 28% at only 3 events), the
   price ceiling is wrong and every threshold must be re-derived.
