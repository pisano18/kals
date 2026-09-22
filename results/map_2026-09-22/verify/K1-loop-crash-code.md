# VERIFY K1-loop-crash (lens: CODE) -- VERDICT: CONFIRMED, with two corrections

Verifier: K1-loop-crash-code, 2026-09-22. Code: research/pinrun.py at HEAD
1d73bf6 (unmodified in the working tree), research/pintake.py. Own code in
scratchpad/map/verify2/K1-loop-crash-code/ (crashes.py, harness.py,
window_fuzz.py). Nothing contacted Kalshi: urlopen, ordercli.send,
pintake._get/take, read_bank, publish_size, add_day_loss were all replaced by
functions that raise before pinrun ran.

## What in plain words

A crash in the bot's scanning code kills the whole program. If it is holding a
bet when that happens, nothing hedges that bet until it settles. This has
happened once for real (09-19, lost $66.34 on that bet). The second risk the
claim names (a fill getting lost because the log line after it fails) is real
in how the code is written, but nothing that exists today triggers it, and a
stop that already exists limits it to 2 orders per run.

## Findings (line numbers = research/pinrun.py)

1. **No self-test runs trade_loop: CONFIRMED.** `def trade_loop` 8541. The
   only call is main() at 11661. Every self-test mention (3332, 3364, 3620,
   3945, 4044, 4082, 4109, 4231, 4299, 4382) cuts up the SOURCE TEXT. Nothing
   else under research/ calls pinrun.trade_loop. restart_bot.ps1 has no paper
   trial run before it starts the live bot.
2. **The entry scan has no outer try: CONFIRMED.** The `for tk ... in _mk:`
   loop runs from 9491 to 10661. Only these sub-blocks are guarded: 9605
   (book.best), 9807 (buyable), 9845 (ladder), 10019 (level_age), 10069
   (depth), and 10467-10661 (the live order path). main() 11660-11668 is
   try/finally with NO except. The hedge pass (8965-9311, runs only while
   holding), autosize_tick (8922) and risk_abort (9320) are unguarded too.
   A71 guards only report_closes and reconcile (8901-8918).
   **Harness, the real trade_loop, paper mode, fakes only:**
   - Control: holding A (20 contracts). A's belief falls to 0.30 at +4 s.
     The hedge fires at +4.46 s. trade_loop does not raise.
   - Planted fault: B becomes decided at +2 s, and idx.conditions() raises
     `TypeError ... __round__` (it is called at 10009, outside every try).
     trade_loop RAISES at +2.4 s while holding A. There is no hedge record.
3. **Crash record: CONFIRMED (own scan of 124 live logs).** A crash inside the
   loop leaves an `end` record with EMPTY state. There are exactly 3 of them:
   09-15 04:29:30Z, 09-15 04:59:30Z and 09-19 05:59:30Z. **All three are at
   tau = 30 s exactly**, the first second of the main entry window.
   - Only the 09-19 crash was holding: ETH YES 70 (+$4.06) and BTC NO 70
     (-$66.34, from the ledger). Both bets closed at 06:00Z. The bot restarted
     at 06:06:09Z, because pinflat blocks a restart until the close plus 180 s.
   - The 09-19 crash came from the close_budget gate (9533). That gate runs
     ONLY when this close's budget is already spent, meaning we are already
     holding. So that trigger was tied to holding a bet.
   - **The paper arms had already caught this bug.** arm-lateextra.err and
     arm-nocap-late.err show the same `TypeError: NoneType ... __round__` in
     trade_loop at 00:59:3x ET (04:59Z), 60 minutes before live crashed.
     Nothing reads arm stderr.
4. **The fill-registration window: the ORDER of the code is CONFIRMED. The
   claim's wording needs 2 corrections.**
   - pintake.take returns at 10571. open_pos, entry_at and hedge_meta are
     written at 10621-10623. rec("order") sits between them (10576-10600).
     Anything that raises in that gap is swallowed by 10655.
   - Harness, live path with take() FAKED to return a real
     pintake.normalise() fill, plus one extra key that collides (`want`).
     The result: rec() raised "got multiple values for keyword argument
     'want'". The fill never reached open_pos. No hedge. **A SECOND order
     went into the same market 60 ms later**, because `fired` and the close
     budget were never updated. Then the run halted on "2 errors on the ORDER
     path". Control (no collision): 1 order, registered, hedge fires at +4.3 s.
   - **Correction 1: nothing triggers it today.** I ran the real code span
     against 520 `out` shapes from pintake.normalise (5 statuses, 13 response
     shapes, 2 sides, 4 extras). 0 raised. No key normalise() returns collides
     with an explicit keyword. Every round() argument is already checked
     further up: iage at 9618, and price/_limit are compared as numbers
     before the send. This is a hidden hazard for the next edit, not a live
     bug.
   - **Correction 2: "uncounted" is only half right, and the damage has a
     limit.** The real take() -> `_book()` DOES record the fill in
     pintake.LEDGER (committed, positions), so the stake cap and the
     open-contracts cap still see it. What misses it: the hedge, reconcile(),
     the day-loss file (add_day_loss runs only in reconcile), the run's
     realised-loss brakes, and the close budget. `order_errors >= 2` (7900)
     halts after 2 such errors. A74 then drains for up to 600 s on a LEDGER
     position that no hedge can see, then exits.

## Trigger conditions, stated exactly

- **Door 1 (entry scan):** any exception outside the 6 guarded sub-blocks.
  - It can only happen while a market is inside the entry window: tau 3-30 s,
    or 3-45 s with the early leg on.
  - Gates such as close_budget, early_once, max_per_market and both_sides run
    only after a fill in this close. A bug in one of them can only go off
    while we are holding.
  - The same holds for anything in the hedge pass.
  - Record: 3 crashes over 130 pinrun.py commits since 09-08. Each was new
    code going off the first time its branch ran. None since 09-19 (7 commits
    since).
- **Door 2 (fill window):** a future edit to rec("order") arguments or to
  pintake.normalise's keys, or an exception inside take() after the POST.

## Worst realistic cost

- It is one close's position, left unhedged until it settles.
- Dollars at risk per close since 09-19 (137 closes with fills, from the live
  order records): median **$98.54**, 90th percentile $177.81, max $263.12.
- On a close that WINS, the crash costs about $0.
- On a close that LOSES, it costs whatever the hedge would have saved. The
  code alone cannot measure that. **$66.34 is the upper limit for 09-19.**
- An orphaned loss also never reaches the day-loss file, so the $200 day cap
  under-counts it.
- Door 2, if something ever triggers it: 2 unhedged orders per run, then about
  10 min of no trading, every close, until someone fixes it.

## Smallest safe fix, and the self-test that proves it

1. Wrap the per-market scan body (9492-10661) in try/except Exception.
   - On an error: `rec("error", where="scan", ...)`, once per (close, ticker,
     error type), then `continue`.
   - After N scan errors in a run, stop NEW entries only. Never break or exit,
     so the hedge pass keeps running.
   - It blocks nothing but new bets after a crash-level fault. It cannot block
     a hedge, because the hedge pass runs above it.
2. Wrap the per-position hedge body (8984-9311) the same way: record and move
   to the next position.
3. In the live order path, write open_pos, entry_at, hedge_meta and
   _book_slot IMMEDIATELY after take() returns. rec("order") comes after,
   inside its own try.
4. Alarm on any Traceback in results/arm-*.err. The arms caught the 09-19 bug
   an hour early.

**The self-test must drive the behaviour, not search the text.** Build it
like harness.py, with a fake clock injected into pinrun.time so it runs in
under 1 s. Four cases:

- (a) Control: held position, belief collapses. A hedge record MUST exist.
- (b) A fault planted in an entry-scan dependency after the fill.
  trade_loop must NOT raise, the hedge MUST still fire, and an error record
  with where="scan" must exist.
- (c) rec raises on kind "order". The fill MUST be in open_pos, the hedge
  MUST fire on the collapse, and exactly ONE order may go to that market.
- (d) Null world: belief stays high. There must be NO hedge record, so (b)
  and (c) cannot pass by accident.

Today's code fails (b) and (c). I checked this directly: P1 raised, and L1
sent 2 unhedged orders.

## Looks / multiple-looks bar

I made 9 cuts: the crash-signature scan, the ledger lookup, the per-close
stake table, 4 harness scenarios, the 520-shape fuzz, and the commit count.

None of them is a significance test. n = 3 crashes is under the 30-close
floor. "All 3 at tau = 30" is a structural fact (the entry path first runs
its main-window branches at tau 30), not a statistical claim. If one were
wanted, 9 looks gives a Bonferroni bar of p < 0.0056.

## Could not measure

- What the hedge would have recovered on 09-19 BTC. That needs the tape or
  a replay, and a replay is only a hypothesis.
- Whether any exception can be reached in today's scan through a path I did
  not fuzz. I fuzzed only door 2. For door 1 I found no current trigger in the
  gates I read, but that does not prove there is none.
