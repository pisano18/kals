# 06 code-and-infra -- what in the code and the machine has cost money, and what is waiting to

**STATUS: COMPLETE (07:1xZ).** End-of-job check: collectors 105304 / 105352 alive,
live bot 1985112 and coin-race penny bot 2001776 alive, free disk 33.7 GB, RAM 2.16 GB.

Investigator 06, 2026-09-22 ~06:0x-07:1xZ. Read-only. Nothing started, stopped or edited.
Sources: `results/kalshi_ledger.json` via `pinledger` (money per market -- the authority),
the 124 `results/pinrun-live-*.jsonl` run logs, `results/watch_bot.log`,
`research/pinrun.py` read directly (11,677 lines; the self-test is lines 3125-7750),
`research/pintake.py`, the .ps1 launchers, the Windows task table.
**The running live code is the file on disk**: start record `code_sha` 6f6b1df38af6 ==
sha256 of `research/pinrun.py` now. Scripts: scratchpad `map/06/*.py`.
Nothing here rests on the replay.

---

## 1. Findings, ranked by dollars

### F1. Code bugs have cost $293.80 on four closes (all 09-19); "the process ended while holding" is a separate door that cost $73.83 net over 5 runs. REALISED.

Ledger (Kalshi's own settlements), per market:

| close (ET) | ledger $ | cause | fixed? | would a self-test catch a regression? |
|---|---|---|---|---|
| BNB 09-19 01:45 | **-57.76** | `--hedge-price 0.60` refused the hedge at a 21c ask | yes: A62 panic bypass, and `--hedge-price` is no longer passed (HEDGE_PRICE default None) | partly: `hedge_panic()` has unit checks; the pass itself is only text-searched |
| BTC 09-19 02:00 | **-66.34** | `round(None)` in the close_budget gate's log call killed the process 30 s before the close, holding 70 NO | **the one line** is fixed; the class is not (F3) | only a source-text check on that gate's 420 characters |
| BNB 09-19 12:30 | **-61.75** | sized off phantom ladder depth, then band-boosted | yes: A67 taper; `--band-mult` removed | yes, unit checks on the taper |
| BTC 09-19 16:00 | **-107.95** | the `--loss-cap` pause's `continue` skipped the hedge pass | yes: A69 moved the hedge pass above `risk_abort` | **text search only** -- no test ever runs the loop (F3) |
| **sum** | **-293.80** | against the 67 other 09-19 markets' +$179 (HANDOFF) | | |

Runs that ended holding a position whose close had not yet passed (fills with no
settled row, close later than the run's last record) -- 5 runs, 11 positions,
**net -$73.83 by ledger**:

| run ended (ET) | why | positions | ledger |
|---|---|---|---|
| 09-08 11:59 | loss-bound halt (pre-A74) | HYPE | +0.49 |
| 09-11 21:59 | position-cap halt (pre-A74) | HYPE, SOL, BTC | +2.81 |
| 09-11 23:29 | loss-bound halt (pre-A74) | SOL, BTC, XRP | +0.93 |
| 09-17 21:14 | open-cap halt, terminal by the A31 rename bug (A74 fixed) | BTC (hedged 99/99), ZEC | -27.87, +12.09 |
| 09-19 01:59 | crash, `round(None)` | BTC, ETH | **-66.34**, +4.06 |

A74 (drain on terminal halt) closes the halt door; the crash door and the
external-kill door stay open (F3). When a run dies holding, `pinflat` correctly
refuses a restart until close + 180 s (watch_bot.log shows 4 refusals each on 09-17
21:14 and 09-19 02:00) -- so nothing can hedge that close; a new run never adopts
an old run's position (no position-adoption code exists in pinrun).

**Identify-better side effect, measured:** the bot's own books match Kalshi to the
cent on every ET day EXCEPT the two days a run died holding: 09-17 the bot says
+$115.68, Kalshi +$99.87 (the 21:15 close missing); **09-19 the bot says -$161.14,
Kalshi -$223.46** (the crashed 02:00 close missing). `pinday.py` reads the bot's
logs, so the brief's "09-19 -$161" understates the real loss by $62.32. Every
number built on the bot's logs is wrong exactly on the days code failed.
And the account also ran an oil bot: all-markets truth is 09-17 **+$43.04**
(oil -$56.84) and 09-18 **+$64.57** (oil -$27.28), not +$116 / +$92.

### F2. `classify_bank_move` is still live and still inventing transfers -- but the HANDOFF's diagnosis of it is wrong, and the brake it feeds will stop the bot again after ~$151 more of losses. AT RISK.

**Measured cause: another live bot on the same account, not restarts.** 19
`external` records exist; 1 is real (the $370.44 deposit, 09-19 07:13Z). The other
18 match, within 5 minutes and usually to the cent, another live bot's order or
settlement: 14 are the commodity bot `cmdlive` on 09-17/18 (the "$58.37
withdrawal" at 20:16:58Z is that minute's two oil-bot settlements, WTI
`KXWTI15M-26SEP171615-15` -$58.76 and gold +$0.39 = **-$58.37 exactly**; -$19.96 on
09-18 17:30Z is `KXWTI15M-26SEP181330-30` at exactly -$19.96; the small ones are
oil-bot purchases and $1/$2 payouts), and 4 are the coin-race penny test on 09-21
(+$2, +$1, -$1.95, +$2).
**Zero** trace to a restart. pinrun's `realised` only counts pinrun, so every other
bot's money reads as the operator moving cash.

**The 09-20 "deadlock" was NOT caused by the fake $58.37.** A withdrawal LOWERS the
mark; the 18 fakes moved it net **-$85.86** (made the brake less sensitive). The
$1,046.43 mark was a real balance high ($675.99, reached by `write_hwm` from a real
balance on 09-18/19) plus the real $370.44 deposit. The 22.5% drawdown that halted
the bot at 09-20 03:45Z was **$235.84 of real losses** -- 09-19's. The fix that was
applied (hand-resetting the mark to $810.59, commit dc036e9) erased that memory on a
wrong diagnosis. Measured cost of that halt: log gaps 23:45:35 -> 00:41:50 ET =
**56 min, 3 closes missed** (not the ~2 h the HANDOFF quotes).

**What is waiting:** the drawdown brake (`MAX_DRAWDOWN` 0.20, no flag disables it)
is TERMINAL and self-repeating: it halts, watch_bot waits its 15-min money-brake
cooldown, restarts, and the new run halts again on its first bank read -- four
times on 09-20 until a human edited the file. Mark now **$958.90**
(`pinrun-hwm.json`), bank **$917.92** (size mirror, 06:01Z) -> it trips at
**$767.12, i.e. after $150.80 more of losses from here, on any number of days** --
before the $200 day cap would. At night that is hours of no trading.
And because other bots' money is shifted out of the mark, **no loss brake on the
account sees the coin-race or oil bots' losses** (the day cap counts pinrun only too).

Confidence: high (log records + ledger, n = 19 events). Artefact check: the
coincidence window is 5.5 min; 18 of 18 fakes have a matching other-bot order or
settlement (17 in that bot's own log, the 18th in the ledger: two coin-race $1
payouts at 18:2xZ 09-21); the dollar amounts match the other bot's purchase,
payout or net settlement, several to the cent. Checked.

### F3. No self-test ever EXECUTES `trade_loop`; every loop-level protection (A69, A71, A74) is a text search. An exception anywhere in the ~1,170-line entry scan still kills the process while holding. AT RISK: one close's position, ~$70-$230.

- `grep` finds exactly one call of `trade_loop(`: `main()`, line 11661. The
  4,600-line self-test reads the loop's SOURCE (`index`/`rindex` on
  `"def trade_loop("`) and asserts strings. Behaviour is never driven.
- The per-market scan (`for tk ... in _mk:`, line 9491) has no outer `try`. Only
  three sub-blocks are guarded (9605, 10019, 10069). `main()` wraps the loop in
  `try/finally` only: any exception ends the process. The hedge pass (8965-9312)
  is also unguarded except its book read and its order call.
- **Record so far:** 3 in-loop crashes of newly shipped code in 14 days (09-15
  04:29:30Z A43 TypeError, 09-15 04:59:30Z A41 UnboundLocalError, 09-19 05:59:30Z
  round(None)). **All three at :29:30 / :59:30 -- tau = 30 s, the first second the
  entry path runs its rarely-executed branches.** A new bug in that path by
  construction surfaces at the moment money is going in. 1 of 3 was holding (-$66.34).
- Second door in the same place: after `out = pintake.take(...)` returns a FILL
  (line 10571), the fill is written to `open_pos`/`hedge_meta` only ~50 lines later,
  after a `rec("order", ...)` call full of `round()` arguments (10576-10600). If
  anything there raises, the `except` at 10655 swallows it: the position exists on
  Kalshi but the bot never hedges it, never books it, never counts it against the
  close budget (it can buy the same close again).

### F4. One timed-out order sets pintake's halt, pinrun never clears it, and from then on `pintake.take` refuses every order -- HEDGES INCLUDED -- for up to 10 minutes. AT RISK (never fired: 0 of 1,198 live orders returned status -1).

`pintake._book()` sets `LEDGER["halt"]` on status -1 (request failed), 3xx, 5xx,
an unreadable 2xx, or an IOC that rested. `check_take()` refuses everything while
it is set. `grep clear_halt research/pinrun.py` = nothing. `risk_abort` then returns
"pintake halted" (terminal, not transient) -> A74 drains for `DRAIN_MAX_S` 600 s with
the hedge pass running -- but every hedge it sends goes through the same `take()`
and is refused (`hedge_refused take_refused`) -> exit -> watch_bot restarts. A hedge
POST that times out blocks all later hedge tries on that close. The trigger is
exactly tonight's condition: REST calls returned -1 for 4 h 47 min
(388 `universe_http_-1` tonight; 4 on all other nights combined). The bot was flat and refusing on `book_stale`, so it never
sent. Mid-position, it would have. (The stake-cap and run-loss rails in the same
`check_take` were checked: at the live flags hedges fit under the stake cap with
~$15 to spare, and positions and settlements never overlap closes, so those two
cannot bite today.)

### F5. The hedge is silently blind when the index feed freezes. AT RISK.

The entry path refuses when the index is older than 2 s (`index_stale`). The hedge
pass has no age check: `fair()` uses `idx.spot()` and ignores the age it returns,
and `IndexWS.partial()` ends the locked window at the newest print held. A frozen
feed therefore returns a frozen, confident belief -- **no alarm, and no
`hedge_blind` record** (that record only covers sigma/fair being None). Tonight
the index was stale in 5 of the 14 outage closes that wrote a summary. The hedge also reads a possibly
stale book (no age check), whose order would then hit F4.

### F6. Paper arms read the LIVE day-loss file. AT RISK: the whole measurement fleet dies on a bad live day.

`risk_abort()` line 7792 calls `day_loss()` with no `a.live` check (only the WRITE,
`add_day_loss`, is live-only). 24 of 25 running paper arms carry `--loss-cap 200`
(inherited from live by `sync_arms.ps1`). "DAY loss cap" is terminal and paper arms
are never restarted, so a live day at -$200 halts all 24 at once -- on exactly the
day their comparison matters most. Second coupling: `boot_all.ps1` (every 10 min)
launches a HARD-CODED set of 16 pre-sync arms (`arm-b-*`, `--hedge-price 0.60`,
`--bank-brake 4.08`, ...) whenever no paper arm is running, e.g. after a reboot --
the void configurations CURRENT_STATE says to never trust.

### F7. Operational record: downtime is NOT where the money went.

From run logs (start = first record, gap = previous run's last record to next
run's first):

| | |
|---|---|
| runs (starts) | 124 in 15 days; per ET day 09-15..21: 10, 1, 6, 6, 14, 9, 3 |
| runs that wrote an `end` record | 14 (10 halts, 4 crashes); the other 110 were killed (restarts) |
| restart gap | median 156 s, p90 427 s (103 gaps under 10 min) |
| between-run downtime since 09-15 | **8.9 h**, of which 09-15 = 5.8 h (Windows Update reboots 1 h 52 min by the logs, account block, deleted key, 2 crashes) |
| in-run blind (alive, 0 evaluations) | 09-21/22 outage, 4 h 47 min (14 closes with a summary, the rest wrote none); 2 isolated blind closes otherwise |
| trading windows missed since 09-15 | 682 closes: **31 to downtime** (23 on 09-15), **16 blind** |
| runs ended holding | 5 (F1); restarts attempted while holding: 8, all refused by pinflat, correctly |

At the 09-15..21 ledger average of $0.35 a close (median day $0.89), 47 missed
closes are roughly $16-$42 -- an ESTIMATE, not a measurement. Downtime is small
money; the four bug closes alone are $293.80.

### F8. Infrastructure: what single failure stops the money bot or the tape next.

1. **A Windows reboot.** `KalsBoot` (boot_all.ps1, at logon + every 10 min) is
   `LogonType Interactive` ("Interactive only") and `AutoAdminLogon=0`: after any
   reboot NOTHING starts -- not the bot, not the recorders -- until the operator
   logs in. Windows Update active hours are 15:00-09:00, so an update may reboot
   09:00-15:00 ET, while he is at work. Last boot 09-15 09:32 ET (that reboot cost
   1 h 52 min). No reboot pending now; last patch 09-15.
2. **Disk, faster than documented.** 33.7 GB free at ~07:1xZ (PowerShell, GiB). Measured tape growth:
   `kalshi_data` 3.0 GB/day on the weekend (09-19/20) and **3.8-4.8 GB/day on
   weekdays** (09-21: 4.80), plus `feed_data` 0.26-0.42 GB/day. At 4.5-5.2 GB/day
   the 6 GB guard is **~5.6-6.4 days away (~09-28)**, not the ~9 a 3 GB/day figure
   implies. At 5 GB free `run_all.ps1` exits its loop and the tape ends.
3. **Kalshi connectivity / the API key.** The bot, both recorders and the penny
   test share one network path and key `5163259c`. Tonight: 4 h 47 min blind;
   09-15: key deleted. The new BLIND/SILENT alerts only tell the operator.
4. RAM is not the constraint: 1.98 GB free of 15.8 now, 45 python processes
   2.96 GB (25 paper arms 1.93 GB, ~77 MB each -- not the ~40 MB CURRENT_STATE
   quotes; live bot 70 MB). Claude apps ~2 GB are the swing.

Tonight's fixes verified present, not redone: `boot_all.ps1 -DeafTest` 7/7 ok;
`pindesk.blind_of` exists and is wired into the app and phone with self-tests;
recorders writing (cfbenchmarks T06 and orderbook_delta T06 written 06:50:02Z);
collectors are the 09-15 pids 105304 / 105352. `versioncheck.py`: clean.

---

## 2. Refuted or not supported

- **"Two losses where hedging was live and NOTHING fired"** (HANDOFF 09-19,
  SOL 09-11 23:00 ET -$19.61, SOL 09-12 04:00 ET -$18.88). Refuted: they settled
  09-12 03:00:20Z and 08:00:20Z; the first hedge record in any live log is
  09-12 09:44:35Z and v-a15 went live 18:06Z. Hedging did not exist yet.
- **"`realised` resetting on restart fabricated the $58.37"** -- not supported;
  every fake traces to another bot (F2).
- **"The fake withdrawal pushed the mark to a level never touched and caused the
  09-20 halt"** -- refuted; the fakes lowered the mark; the drawdown was real (F2).
- **"The deadlock cost ~2 hours"** -- measured 56 min, 3 closes.
- **Outages as a main money leak** -- not supported (F7: ~47 missed closes since
  09-15 against $293.80 in four bug closes).
- **pintake's stake cap or run-loss rail blocking a hedge** -- checked at the live
  flags; cannot bite today (F4 note).
- **API rate-limiting from 25 arms** -- no 429 responses in any live log.

## 3. Could not measure, and why

- Whether a frozen index has ever overlapped a HELD position: the hedge pass logs no
  index age, and the tape is the recorder's connection, not the bot's.
- Why the 09-21 20:12Z run ended at 05:29:39Z with no `end` record (hard kill; the
  killer is not logged -- probably the recovering session).
- `pinrun.py --selftest` not re-run (RAM ~2 GB with other investigators running);
  the live bot and all 25 arms passed it at startup on this exact SHA.
- Dollar value of missed closes -- only an estimate is possible (F7).

## 4. Solutions worth testing (none of them blocks a hedge; each says what it blocks)

1. **F3: stop a scan bug from killing a held position.** Wrap the per-market body
   in try/except that records `error where=scan`, skips that market for that tick,
   and keeps looping; move the `open_pos`/`hedge_meta` write to the line straight
   after `take()` returns a fill, before any logging. **Self-test that EXECUTES the
   loop**: fake book + fake index + fake `take`, one open position, a gate
   monkeypatched to raise -> assert the loop survives N iterations and the hedge
   pass wrote a hedge; make `rec("order")` raise -> assert the fill is in `open_pos`;
   NULL: no position -> no hedge. Blocks: that market's entry for one tick.
   Live check: zero `end`-without-`halt` records; `error where=scan` counted.
2. **F4: a hedge must bypass pintake's halt.** A `hedge=True` path in
   `take()/check_take()` that skips `halt`, `MAX_RUN_STAKE` and `LOSS_ABORT` (keeps
   count, price, IOC, post_only, environment). Better still: on an UNKNOWN outcome,
   look the order up by `client_order_id` before halting. Self-test: halted ledger ->
   hedge order is sent, entry still refused. Blocks: nothing new.
3. **F5: a stale index must not mean "all is well".** In the hedge pass, index age
   > 2 s while holding -> record `hedge_blind index_stale` once, and fall back to the
   market's own price (other side's ask below 1 - HEDGE_BELIEF -> hedge). Self-test:
   freeze the fake index confident, drop the fake other-side ask to 20c -> hedge
   fires; NULL: fresh index, calm book -> none. Blocks: nothing; adds a trigger only
   while blind.
4. **F2: transfers from Kalshi's records, not inference.** `classify_bank_move`
   shifts the mark only for a transfer in `pinxfer`'s deposit/withdrawal list.
   Operator decision needed: should the drawdown brake see ALL bots on the account
   (so coin-race losses count) -- today it sees pinrun only. And make the drawdown
   halt a pause with a size cut, or a single halt the watchdog does not re-trigger
   every 15 min. Self-test: another bot's -$58 settlement, empty transfer list ->
   mark unmoved; a real deposit -> mark moves by exactly it. Blocks: new bets only.
5. **F1/F7: the day cap and pinday must use Kalshi's settlements.** Seed today's
   day-loss from `pinledger` at startup and on every reconcile, so a crash-orphaned
   loss counts (09-19 missed $62.32). Self-test: ledger fixture with a settlement
   absent from the logs -> `day_loss()` includes it. Blocks: new bets sooner on a
   bad day, never a hedge (A69 order).
6. **F6:** `day_loss() if a.live else None` in `risk_abort` (arms keep their own
   total); `boot_all.ps1` calls `sync_arms.ps1` instead of its frozen list.
   Self-test: paper args + a -$500 file -> no halt; live args -> halt.
7. **F8:** run KalsBoot "whether the user is logged on or not" (or enable
   auto-logon), and move Windows Update active hours to cover 09:00-15:00 ET or
   pause updates. Test: a planned reboot drill with a stopwatch. Disk: plan for
   ~5 GB a weekday, not 3.
