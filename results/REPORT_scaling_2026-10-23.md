# The scaling search -- report for the operator (2026-10-23, written ~04:00 ET, completed ~06:40 ET)

Short version: **no strategy measured tonight compounds at 1% a day into the tens of thousands.** Every class the prompt named was measured from the recorded tape with pessimistic fills, and all but one are dead. The one that works is the one already running (the ladder's resting bids on the five small coins), and its ceiling is set by how many people sell the decided side cheaply in the last 30 seconds -- about $35-50 a day at a $5-15k bank, however big the bank. The pin bot's ceiling is ~$30-40 a day. Of the three open items at 04:00 ET: the race v2 reward test is **dead** (filled 6.7x its credit, -$17.43); the 97c second rung is **superseded** by something better found at 06:20 ET -- **one 98c rung on the whole rail makes more than any two-rung ladder at today's bank** (+4% over 25 days, +26% over the last 7, same risk; one boot_all edit); and the hourly 150-290-strike family is now **on tape** and its first two closes show where its money is (lottery-ticket sellers in the ~2% of strikes decided inside the last 15 minutes: $300-900/day extrapolated at size 5,000, but 3 strike-closes carry most of it and the loss rate is unmeasured -- a full day of tape decides).

Everything below is measured; scripts and raw outputs are under `C:\kals-repo\.sweep\q-2026-10-23\<topic>\` and the numbers are in HANDOFF.md.

## 1. Part A -- every killed, cut-short or unverified item, decided

| Item | Verdict | The number that decided it |
|---|---|---|
| 97c second ladder rung | VERIFIED at equal sizes (+5-13%, +13-15% out of sample), then **SUPERSEDED**: under the fit rule a second rung halves the 98c size, and one 98c rung at size 91 beats 98+97 at 46 ($11.47 vs $9.73/day, exact-queue model) and beats the live 98+95 ($12.13 vs $11.67, paper-timing replay; last 7 days $10.23 vs $8.13) | drop the second rung instead: `--levels 0` (v-ladder-single98) |
| Fixed-time earlier bid (-45/-60 s) | DROP | the 9 wrong early calls are alive at -40 s, 0 flips: a -45 s bid inherits all 9 (a loss every 1.5 days) |
| Race v2 live test | **KILLED** 04:25 ET after 2 races (-$17.43; sub 4 holds ~$27.6 to return) | fills $17.43 vs $2.61 modelled credit = 6.7x (kill line 0.5x); the 1c bids get filled by the loser's dump, not left resting |
| Pin zero-fill retry at <= 0.985 | DROP | +$10..46 over 15 days at the realised loss rate; breakeven loss rate 1.5% |
| Pin cheap-leg band floor | DROP | +$7..59 over 15 days, worst day -$70 -> -$111 |
| fill_by_size.py | DROP (superseded by pinops/sizing.py) | prints nothing |
| watch-nopause (weekly read) | KEEP | replayed pauses would have skipped +$0.00 |
| watch-band15 (weekly read) | KEEP | +$14.32 in 1.75 days = +$8.2/day, exactly the study's number |
| forecaster-live read | KEEP, new count from the one-side variant | r28 period +$3.66/day; both-sides losses 2 (the size-up bar fails) |
| ladder-optc read | KEEP 5 coins | shadow since 10-22: C $11.43 vs old A $6.49, 0 losses |
| watch-hedgejump6 | not live until the 10-24 11:02Z restart | 0 jump hedges yet |
| fc-fast-paper | NOT READY; its read is broken (refuses since the variant change) | 161/200 fills; second half negative |
| fc-maker-paper (resting-bid forecaster) | heading to KILL | M500 -$36.42 (kill line < $0) |
| FX 15M reward paper | VOID | no paper rows exist (the quoter never ran) |
| Polymarket | DEAD | sure side offered <= 98c in 6 of 100 windows |
| Weather dip-seller, rain desk | DEAD | -15.9c/contract; winter kill clause fired |
| btc-lead-forward | DROP | scorer lost; "identify better, not make more" |
| et-clock-bug (DST Nov 1) | **FIXED** in the ladder and forecaster (live tonight); pin bot build staged, switches at its 10-24 run end | day key would have turned at 23:00 EST from 11-02 |
| Recorder v5 (admin_1018.ps1) | still never run (operator's admin hand) | 9.5% of public calls 429; the forecaster's 04:40Z and race v2's 06:59Z launches died on one each (retries added to all three bots tonight) |
| Collide leads L1/L2 | L1 arithmetic only (not a money item); L2 disk housekeeping | -- |
| Market making F-P10 | re-measured properly tonight: DEAD | see Part C |

## 2. Part B -- what the current bots can carry

**Ladder (sub 1, $648, fit rule, 70% ceiling).** Measured 1.85-1.89%/day at this bank, 0 losses in 231 live and 20,339 paper markets. Capacity on the five small coins from the exact-queue replay: ~$9/day at 100 a bid, $35/day at 1,000, $42/day at 5,000 -- i.e. the dollars flatten around a $5-10k bank (0.3-0.5%/day) and are ~0.1%/day at $50k. The big four coins add nothing (ETH/SOL: zero cheap sales on the decided side in 3 days; BTC: behind a 6,000-contract queue). So the earlier "add BTC/ETH/SOL/BNB at $3,000" is harmless but worth ~$1/day; the --big-coins-above switch can stay.

**Ladder rungs (found 06:20 ET).** Under the fit rule every extra rung halves the 98c bid, and the 98c rung is the one that fills (every one of the 1,645 contracts the live ladder has ever filled came through it; the 95c rung has had 65 live bids and 0 fills since it went live 10-22). Both replay models agree: **one 98c rung on the whole rail (91 bids a coin at $648) beats the live 98c+95c pair (46 each)** -- $12.13 vs $11.67/day over 25 days (+4%), **$10.23 vs $8.13 over the last 7 (+26%)**, 15 of 25 days and 14 of the last 15; the exact-queue model ranks 98 alone $11.47 > 99+98 $10.23 > 98+97 $9.73 > 99+98+97 $9.38. Same 70% ceiling ($446 vs $453 out at once), same worst market (~$89), same rule and coins, and `--levels 0` is the code path that was live on 10-22 morning. A 99c rung only starts paying at a ~$4,000 bank (then 99+98), three rungs at ~$5,750.

**Pin bot (main, ~$1,420).** 2.4%/day today, but outcome-scaled capacity is flat at ~$30-40/day: its losing legs sit on 50x deeper books than its winners (median 1,547 vs 236 contracts), so more bank buys more of the dumps. Marginal $100 earns $0.83-1.48/day.

**Coin race (main).** Ties were its whole loss; with --min-gap-bp 0.5 (live 00:40 ET) it should run ~+$1.5/day. Small by design.

**Forecaster (sub 2, $125).** One-side variant live 00:50 ET; ~+$2.4/day expected, high variance; kill date 11-06 against the ladder's return on the same $125.

**Allocation:** new money goes to the ladder until its bank is ~$2,500 (then its %/day falls below the pin bot's marginal); nothing to the pin bot; the forecaster's $125 moves to the ladder on 11-06 unless it beats the ladder; race v2 gets its own money only after a PASS.

**Compounding with the bots as they are:** ~3.4-3.9x in 90 days (~$7-8k), 6-9x in 180 days -- and then flat, because both big bots cap in dollars.

## 3. Part C -- the search for something that does not cap out (all 15-minute crypto, 9 coins, exact books)

| Class | Measured | Result |
|---|---|---|
| Taker at fair value (the ladder's p, last 120 s, every second, 300-ms persistence fills) | 5 days, 4,248 markets, 509,760 seconds | DEAD: p is honest unconditionally, but the seconds where the book disagrees with p win 4-12 points less than p says (live spot leads the index prints). In-sample $18.8k/day at S=5000 was a weekend tail; out of sample negative at every size; the one positive family (last 60 s, p >= 0.5) was one day (10-20) and is refuted. |
| Market making off p with inventory limits (both phases) | 3 days late + 1 day uncertain, 64 rule cells, queue-charged | DEAD: loses at every spread and size (-$275/day at S=50 best, -$18k at S=5000); 70-90% of fills are pick-offs within 2 s. |
| Ladder's class on the big coins at 99c/98c | 3 days, exact queue | NOTHING: 0 fills at 99c; BTC 1 fill in 3 days at 98c. The big coins' decided-side sales (6M/day on BTC) print at 0.999 against 166k resting there. |
| Ladder's class on the small coins | 15 days (97c run pending) | the only working class; capped ~$35-50/day |
| Structural rules | survey | race ties (now guarded); sports cancellations pay $0.50/$0.33 (needs the cancellation base rate; outside our data); FX 15M rules contradict on exact ties (single Pyth print, no averaging -> no ladder) |
| Hourly KXBTCD/KXETHD/KXSOLD (60-s average, 150-290 strikes/hour, 33M BTC contracts/day) | ON TAPE since 04:12 ET (own recorder); first 2 closes = 1,576 strike-closes, exact books | 0 wrong calls. 98% of strikes are decided 15 min out and dead (99c wall 24,825 median, nothing sold under it). **All the money is in the ~2% decided inside the last 15 min, where the 99c level is EMPTY at the lock** and lottery buyers of the loser at 2-3c sell the winner at 97-98c for minutes: one bid at the lock = $31-38/close at size 5,000 (**$750-900/day x24**), $13/$7 per close if the paper's cancel rule is honoured ($300/$170/day), **$0 in the paper's own last-30-s window**. 3 strike-closes carry 83-98%; the early locks ran to 13-17 bp of the threshold (a 20-bp adverse move on a 5,000 x 98c fill = -$4,900; breakeven loss rate ~2%, unmeasurable on 30 locks). **Not actionable yet; a full day of tape (read due 10-24) decides.** |
| Parity trades (strike monotonicity inside the hourly ladder; 15M vs hourly at shared closes) | 1.79 h, 4.9M deltas, 19,208 ladder-seconds | DEAD: 3 riskless flickers of 2-8 ms (1-3c, dust) and 0 between the families; band-credit trades lose (the market's band prices beat a realized-vol model in all 6 coin-closes; -$11,719 realized at 50 contracts). |

Ranked candidates against the bar (0.5%/day at $10k, 0.25% at $50k, bounded loss, paper-first): **none passes.** The ladder passes the loss and paper tests and makes money at every bank, but fails the %-at-$50k test. Market making and taking fail on edge. The reward program (race v2) is the only thing whose ceiling is not the order book -- its ceiling is Kalshi's reward budget and its risk is the 1c fills, both being measured now.

## 4. What to do (build plan, with kill criteria)

1. **Ladder, keep compounding it:** fit rule stays; **drop the 95c rung (`--levels 0`, one boot_all edit): +$0.46/day over 25 days, +$2.10/day over the last 7, same risk** -- this replaces the 97c idea. Raise the ceiling to 100% only if you accept ~96% of the bank out at once (+$3.5-4/day; with one rung the ceiling binds less: 91 bids = $446 of $450 at 70%). Kill criterion for the ladder: a first lost market -> stop and review the call that was wrong.
2. **Race v2:** dead; return sub 4's ~$27.6. No more reward research (your call: "the LEAST likely place").
3. **Hourly family:** the recorder is taping; re-run the lock-bid study on the full day (10-24). Worth a paper arm only if >= 20 closes show >= $5/close at size 1,000 under the strict rule AND 0 wrong inside-window locks with the post-lock lead holding above the 21.2-bp floor on >= 90% of them. Otherwise drop it.
4. **Forecaster:** judged 11-06. **Pin bot:** nothing to change; the DST build switches at the 10-24 run end.
5. **Not worth more time:** taking at fair value, market making, big coins at 98/99c, the 85c rung, a 99c rung below a ~$4k bank, earlier calls, parity/monotonicity trades, Polymarket, weather, rain, FX reward paper, maker rewards.
6. **"Buy, then sell before expiry" (your question):** measured negative in both forms on this tape -- market making (70-90% of fills picked off within 2 s; best cell -$275/day) and fair-value taking (the book disagrees with the model only when live spot has already moved; out of sample negative). The ladder's edge is the settlement lock, which pays at expiry 30 s later, so selling early would only give back the 2c. No such method found; the FX/commodity 15-minute tape (recording since 04:48 ET, Monday read) is the last unexplored family.

## 5. Things you should know that you did not ask about

- **Recorder:** it was silent 10-22 07:06-09:00Z (books and trades, not the index) -- its own "frozen book" bug; v5 (admin_1018.ps1) was never run, so the 429 storm continues; three bot launches died on single 429s this week (all three now retry). Books DO rebuild from the tape (my 10-22 note saying otherwise was my bucketing bug).
- **Daylight saving ends 11-01:** fixed in the ladder and forecaster tonight; the pin bot's fixed build is staged and goes live by itself at its 10-24 07:02 AM ET run end. Confirm then: the new pinrun-live start record must show code_sha f36c427f99a5.
- **This Python has no tzdata**; every bot now carries the US DST rule itself.
- **Windows Update rebooted the box on 10-14 and cost ~25 hours ($32 of pin profit)**; auto-login + a power plan that never sleeps is a 15-minute fix on your side.
- **Fees:** all short-dated families are "quadratic" (takers 7% x p x (1-p) per contract, makers nothing) -- the ladder pays no fees; the pin bot paid $54 of fees over 15 days (21% of its gross).
- **Taxes:** results/TAX_TRADES.csv exists; the ledger (results/kalshi_ledger.json) is the source of truth, never a bot's own log.
- **Telegram** is on the new code since 00:40 ET (/features, /update, bank %, pace charts).
- **Backups** of every launcher edit are in results/boot_all.before-*.ps1 and results/restart_bot.before-etclock.ps1; VERSIONS.md has the revert line for every live version.
