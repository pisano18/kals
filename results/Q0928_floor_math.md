# Q0928_floor_math -- "90c minimum and the 60c insurance thing": does the math hold?

Operator, 09-28: *"make it a 90c minimum, and that 60c insurance thing. Make sure
the math checks out for other loss scenarios and then implement it."*
Read-only. Nothing live was changed. Times are ET. Money is Kalshi's ledger
unless a row says "replay".

## Answer, reason first

1. **The 60c insurance rule does nothing with today's insurance trigger.** The bot
   only buys insurance once its confidence falls under 40 in 100. At 40 in 100 or
   lower, a rule added on 09-19 (after BNB 01:45 AM lost $57.98) skips EVERY insurance
   filter, the 60c rule included. So with today's trigger the 60c rule is never
   checked. Checked three ways: the code (`hedge_should_fire` needs belief < 0.40;
   `hedge_panic` bypasses at <= 0.40; the `hedge_price_ok` check sits behind
   `if not _panic`); 2,000 made-up test markets where the result with and without the rule came
   out identical; and the live log (all 13 "panic" records since 09-19 2:06 AM list
   the price rule as skipped).
2. **The 60c rule only does something with the OLD 60-in-100 trigger, and then it
   loses money.** In that setup, insurance gets bought early when confidence sits
   between 40 and 60 in 100 AND our side has already dropped under 60c. On our record
   those extra hedges were mostly false alarms. Replay over every market we held
   since 09-09 (1,001 markets, 725 closes): **-$68 against today's rule** (09-09..09-17
   +$11, 09-18..09-28 -$79). Dropping any single market still leaves it -$21 to
   -$89. One replay row flatters today's rule by $42: on ETH 9/27 2:30 AM the
   replay missed a hedge that live really bought. Corrected, the change is about **-$26**.
   So it is not better and probably worse. The worst single case is HYPE 9/19 11:45
   PM: live ran exactly this setup that night, bought insurance at 43c, our side won
   anyway, and the market finished at **-$43.92 instead of +$5.73**.
3. **The "09-20 build" (the paper bot arm-live-frozen) is a different thing from
   the 60c rule.** In that build both 60c parts are dead code too, because it also runs
   "proportional" insurance: nothing above 40 in 100 confidence, half at 20-40, all
   under 20. That half-size insurance is its only real difference from live. Replay:
   **+$23 against today's rule** (drop-one range -$15 to +$42), which the sample
   cannot tell apart from zero. It wins on false alarms (XRP 9/19 +$38, BNB 9/26
   +$29) and loses on real crashes (BTC 9/23 -$20, NEAR 9/21 -$9, BTC 9/19 2:00 AM
   -$9). It also breaks your standing rule: it holds back half the insurance on a
   bet the model gives 20-40 in 100. You removed it on 09-21 after it cost $59 on NEAR.
4. **The 90c minimum on the 45-second bet: the math is borderline, and our own fills say
   it loses.** At an average 93c, one loss wipes out about 13 wins. So these bets must
   lose fewer than about 7 times in 100 just to break even.
   - While the floor WAS 90c (9/18 2:51 AM .. 9/23 10:22 PM), we bought **16 markets
     at 90-95c on the 45-second bet: 2 lost** (12 in 100). That bet's own money:
     **-$73.99**. The losses were BTC 9/19 2:00 AM (-$66.34, 70 contracts at 94.4c)
     and NEAR 9/21 12:45 PM (-$74.25 on that bet, 81 at 91.1c). Both were
     full-size bets (early-frac 1.0).
   - Since the floor went to 95c: **14 markets** were turned away at 90-95c. None
     would also have been blocked by the 10c edge cap, and **all 14 won** (13 of them
     judged by our model at 0 s left, because we never held them; 1 from Kalshi).
     Taking them would have made **+$18.97 at a third of a bet, +$57.08 at a full
     bet**, with $284 at risk (a third) or $853 (full) over 4.5 days.
     These are offers we did NOT take, so they cannot show the bad fills (someone
     selling to us because they know better). CLAUDE.md rule 5 applies: this is
     not our loss rate.
   - Together: 2 losses in 30. That is right on the break-even line, and 30 markets
     cannot tell 3 in 100 from 12 in 100.
5. **Recommendation: change no flag.**
   - Keep `--early-min-price 0.95`, `--hedge-belief 0.40`, `--no-hedge-prop`, and no
     `--hedge-price`.
   - `--hedge-price 0.60` would be a flag that does nothing today. If someone later
     lowers `--hedge-panic`, it would quietly bring back the 09-19 BNB block. Leave it out.
   - If you still want the 90c minimum live, the only acceptable form is
     `"--early-min-price", "0.90"` with `"--early-frac", "0.333"` left as it is.
     A loss then costs about $28 instead of about $85. Never pair 0.90 with
     `--early-frac 1.0`: both of the 90-95c losses happened at full size.

## 1. What each flag does (pinrun.py, read)

| flag | code | what it can change |
|---|---|---|
| `--early-min-price P` | trade_loop A49: `if _leg46 in ("early","early_once") and price < EARLY_MIN_PRICE: refuse early_cheap` | ONLY the 31-45 s bet (a third of a bet under `--early-frac 0.333`). Checked before the 10c edge cap (`--early-max-edge 10`); the 30-s-and-under bet is untouched |
| `--hedge-price P` (A47) | `if not _panic and not hedge_price_ok(_ask): wait` ; `hedge_price_ok` = our side (1 - hedge ask) < P | waits on a hedge ONLY when belief > `HEDGE_PANIC` (0.40) |
| `--hedge-belief T` | `hedge_should_fire`: belief < T | the alarm line |
| `--hedge-panic` (A62, 0.40) | `hedge_panic`: belief <= 0.40 bypasses hedge_price, hedge_normal, attempt cap | makes P unreachable whenever T <= 0.40 |
| proportional (A76, default ON, live runs `--no-hedge-prop`) | `hedge_want`: 0 above 0.40, half at 0.20-0.40, all under 0.20 | with it, P is unreachable for ANY T (nothing is bought above 0.40) |

The live log agrees. The only 3 `hedge_wait_price` records ever written were all
under the 0.60 trigger (9/19 1:44 AM BNB at 22.7 in 100, 9/19 5:14 PM NEAR at 58.5,
9/19 11:44 PM HYPE at 43.7). The one under 40 in 100 (BNB) happened BEFORE the panic
line existed (first run with it: 9/19 2:06 AM). That block is the $57.98 loss.

## 2. Every insurance setting on every market we held since 09-09 (replay)

**Source warning:** this section is a rebuild, not live fills. Our side's
per-second confidence comes from the index (before 9/23 3:28 AM) or from the bot's own
per-second log (after). The insurance price comes from the ticker tape (before) or the
bot's own book (after). Tape prices at hedge moments matched our real hedge prices
only 9 times in 36 (HEDGE_FLIP_2026-09-25), so any single row can be off by tens of
dollars. Differences between settings on the same row are more reliable than the
dollar levels. Each position is the one we really held (real size, real entry cost);
only the insurance is decided again.

| setting | total, 1,001 markets | vs today | 09-09..09-17 | 09-18..09-28 | hedged | came back (false alarm) | vs today at +5c hedge price |
|---|---|---|---|---|---|---|---|
| never insure | +$694.20 | -$213.93 | -$82.60 | -$131.33 | 0 | - | - |
| **today: trigger 0.40, whole position** | **+$908.13** | -- | -- | -- | 25 | 4 | -- |
| (a) today + `--hedge-price 0.60` | +$908.13 | **$0.00** | $0.00 | $0.00 | 25 | 4 | $0.00 |
| (b) trigger 0.60 + price 0.60, whole | +$840.24 | **-$67.89** | +$10.67 | -$78.56 | 29 | 8 | -$78.91 |
| (c) 09-20 build: 0.60 + 0.60 + proportional | +$930.92 | **+$22.79** | -$0.96 | +$23.76 | 25 | 4 | +$28.55 |
| trigger 0.60, no price rule (09-16..09-18) | +$843.56 | -$64.57 | +$21.69 | -$86.25 | 30 | 9 | -$80.04 |

Drop-one ranges vs today: (b) -$89 to -$21 (always worse); (c) -$15 to +$42 (can't
tell from zero). Real money over the same markets: +$670.06. It is lower than the
"today" row mainly because live ran other triggers before 9/24 and missed some hedges.
Self-test passed: when confidence never falls, every setting gives the same money. Planted
crashes were bought at the planted second and price. (a) matched today to the cent
on 2,000 random worlds.

## 3. The loss scenarios, one by one

"Live" = what really happened (Kalshi). The (a)/(b)/(c) columns are the replay.
Where the replay's today-rule price differs from live's real fill, the live number is
the one to trust.

| market (ET) | what happened live | (a) 60c rule + today's trigger | (b) 0.60 + 60c | (c) 09-20 build |
|---|---|---|---|---|
| BNB 9/19 1:45 AM, **-$57.76** | trigger 0.60 + 60c rule, NO panic line: at 22.7 in 100 the insurance was 21c, but the 60c rule held it back because our side still showed 79c. Chased to 76c, got 1 of 76 | hedges at the first second under 40 in 100 (replay -$34; the tape shows 29c, but live could not find depth) | same as (a): the panic line overrides | same as (a) |
| BTC 9/19 2:00 AM, **-$66.34** | 45-s bet at **94.4c**, 70 contracts (full size). The bot's run ended 30 s before close, so there was no hedge at all | replay hedges at 28 s (56c): -$37 | same | half first: -$46 |
| BNB 9/19 12:30 PM, **-$61.75** | panic hedge at 15 in 100, 44c -> 80c | same (~-$62) | same | same |
| BTC 9/19 4:00 PM, **-$107.95** | 45-s bet at 98c; no insurance alarm recorded (cause not re-checked here; A71 in pinrun.py blames the entry-attempt counter) | no flag here changes it | same | same |
| XRP 9/19 11:45 PM, **-$64.95** (came back) | insured at 27 in 100, 63c | same | same | half: **-$35** |
| HYPE 9/19 11:45 PM, **-$43.92** (came back) | 0.60 + 60c setting: insured at 43.7 in 100 once our side fell to 57c | no hedge: **+$5.73** | **-$41** (this is the case) | no hedge: +$5.73 |
| BTC 9/23 8:30 PM, **-$130.41** | trigger was 0.25: insured at 17 s, 80-87c | replay: 22 s at 64c, about -$93 | same | half first: -$113 |
| BNB 9/26 10:30 AM, **-$20.29** (came back) | insured 98 at 57.8c at 5 s (belief 3 in 100) | identical to live | identical | half: about +$9 at live's price |
| BTC 9/27 12:00 AM, **-$131.98** | belief went 100 -> 4 in 100 in one second; insured 198 at 67-68c | identical: nothing ever sat at 40-60 | identical | identical (under 20 -> all) |
| ETH 9/27 2:30 AM, **-$32.73** (came back) | insured 88 at 51c at 9-10 s (belief 35 in 100) | identical to live | identical | half: about -$9.52 |

So among the named losses, (b) changes exactly one market, and makes it $50 worse
(HYPE 9/19). The panic line, not the 60c rule, is what protects BNB 1:45 AM and
every later crash. (c) helps on the three false alarms (XRP, BNB 9/26, ETH 9/27)
and costs on the real crashes (BTC 9/23, NEAR 9/21, BTC 9/19 2:00 AM).

## 4. The 90c minimum on the 45-second bet

**Our own fills while the floor was 0.90** (9/18 2:51 AM .. 9/23 10:22 PM):

| price paid on the 45-s bet | markets | lost | that bet's money | whole-market money | contracts |
|---|---|---|---|---|---|
| 90-95c | 16 | 2 | **-$73.99** | -$104.92 | 1,247 |
| 95-98c | 188 | 2 | +$82.99 | +$49.71 | 10,620 |

The 90-95c rows (13 at full size, 3 at a third): 14 wins worth +$2.09 to +$9.61
each, and 2 losses: BTC 9/19 2:00 AM -$66.34 and NEAR 9/21 12:45 PM -$74.25.
Scaled to a third, the losses would have been about -$22 and -$25, and the whole
bucket about -$21 (an estimate: it assumes the rest of each bet would have been
bought at 30 s or less).

**Turned away since the floor moved to 0.95** (9/23 10:22 PM .. 9/28), at 90-95c,
first time per market:

| | markets | lost | extra money, a third | extra money, full | at risk, a third | at risk, full |
|---|---|---|---|---|---|---|
| would pass floor + 10c cap | 14 | 0 | +$18.97 | +$57.08 | $284 | $853 |
| of which we bought later anyway | 1 | 0 | +$0.28 | +$0.85 | $6 | $17 |
| of which we never bought | 13 | 0 | +$18.69 | +$56.23 | $279 | $836 |

Outcomes for the 13 we never held come from our model at 0 s left, not from Kalshi's
result. Two refusals carried a size of 0 (the bet was already capped), so they add nothing.
The toxic-fresh and one-full-bet gates were not re-applied to these rows.
**What the sample can detect:** with 30 markets, 2 losses means anywhere from 1 to 22
in 100. The break-even line is about 7 in 100, so this cannot settle the question.
One more loss at a third of a bet (about $28) wipes out the whole 4.5-day gain of the
refused group.

## Method, files

Scripts (stdlib, self-tests pass, one process at a time, well under 300 MB):
`scratchpad/q0928/floor_math/extract.py` (streams every `pinrun-live-*.jsonl`,
including the RESTORED `pinrun-live-20260925T122357Z.jsonl`), `build_traj.py` (the
bot's per-second `pintraj-live-*` logs; handles `want` flipping away from the held
side, which first made the replay price the wrong side), `hedgesim.py` (settings
replay + self-test), `post.py`, `early.py`. Earlier per-second data:
`results/cf_2026-09-24/cf_dataset.jsonl.gz`. Ledger: `results/kalshi_ledger.json`
(written 9/27 11:46 PM ET; later settlements are not in it).
Recorders alive after the run (crypto_feeds pid 105352, kalshi_collector pid
2532788); 63.7 GB free.
