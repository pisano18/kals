**Verdict: NO-GO on `1181c8dba682` as it stands. It becomes GO once B1 below is fixed.** No full re-review is needed after that fix: re-run `--selftest` and my attack A4.

**Fingerprint reviewed:** `1181c8dba682`. This is the SHA-256 of `C:\kals-repo\research\sweep\racereward_live.py`, and it matches the `code_sha` in my dry run's start record. The self-test passed: 113 checks, 0 failed.

## Blocking defects: 1

**B1. The day budget can still go past −$30, by up to $10.**
- **How:** an order gets partly filled, then its coin comes alive and the bot cancels it within the same 2-second poll gap.
  - The cancel gets a 200, the status becomes "cancelled", and `resting_collateral()` (:629-630) stops counting that order straight away.
  - The fill isn't known until the next poll, up to 2 s later.
  - In that gap, a leg that was waiting on `rail_day_budget` is placed. In my runs that took 0.3–0.8 s, sometimes in the same step.
- **Measured:** 400 randomized races on the bot's fake exchange, with partial fills and coins coming alive. 118 of 707 orders went out with a true worst case below −$30. The worst was −$39.99.
  - Example, seed 25: the day stood at −$15. BTC filled 999 contracts and was cancelled as alive. 0.3 s later ETH was placed, while the bot still thought it was at −$15 with nothing held. The true worst case was −$34.99.
- **When:** it needs a partial fill in the ~2 s before a coin comes alive. That is rare, but coins do come alive: 2 of 4 orders in the first review's dry run were cancelled that way.
- **Cost:** at most one extra $10 order each time it happens. The subaccount's cash still caps the total.
- **Fix:** about 2 lines.
  - In `resting_collateral()`, keep counting an order whose status is "cancelled" but not yet final at (count − filled) until `poll_orders` marks it final.
  - Or book the fill as count − `reduced_by` from the DELETE reply at :812-817.
- **Fix tested:** I patched in the first option. A4 then gave 0 breaches in 400 runs (worst exactly −$30.00), and the existing self-test still passes 113/0.
- **Self-test to add:** a partial fill and a coming-alive cancel in the same step, with a leg waiting on the day budget. No order may go out before the poll.

## Remaining non-blocking defects
1. **The exit cancels start at 60 s before the close, not all done by then.** With 5 orders, the 3-writes-a-second limit means the last cancel lands up to 1.6 s later, about 58.4 s before the close. If "off by 60 s" must be strict, start the exit about 2 s earlier.
2. **The 2-second timeout doesn't cover everything.** It is urllib's limit on each socket operation, so it doesn't cover a DNS lookup or a reply that trickles in slowly. A DNS stall that starts just before the 15-second cancel-only window could still delay the exit cancel. Rare.
3. **Cancels can repeat a lot when the order list can't be read.** After a 404, a cancel that can't be confirmed is re-sent every 0.5 s for each order. In one run (lost DELETE reply with the order list down) that was 50 DELETEs in 25 s, on the API key the live bots share. Consider slowing to 1–2 s after the first 404.
4. **The lock refusal message names the holder as "?"** on Windows, because the lock also blocks reading the file. Cosmetic: the lock itself works across processes and after a hard kill (A7).
5. **A hard kill leaves orders on the book** until the next start's sweep or the market close. That is built into the design, and the startup sweep handles it (A3).
6. **A race can count toward `--races` with nothing sent.** The race is added to `state["races"]` in memory before the save, so if the save fails it still counts.
7. **Design note (the fixer already flagged it):** the day budget allows 3 orders per race on a clean day, and fewer after any loss.

## What I verified as passing
- **No order at or after the exit, and nothing left at the close.** This held across 1,548 hang runs, 300 restarts and 300 floor runs.
- **Hangs (A1, 1,548 runs).** I tried 20 s and 30 s hangs, both as a window and as a single call, starting from 40 s before the exit to 2 s after it. I ran each with the WebSocket up and down, 3 or 5 orders, and 0.05–0.3 s latency per call.
  - When GET or GET+POST calls hang, the last cancel lands at most 1.56 s after the exit.
  - When DELETE also hangs, the last cancel lands at most 3.72 s after Kalshi answers again.
  - In the 15-second window, 0 calls other than cancels and the cancel-confirm poll went out, 0 calls had a timeout over 2 s, and 0 earlier calls could block into the window.
- **Lost DELETE reply, and repeated 404s with the order list down (A2):** every order was off the book within 4.6 s of the exit. The bot ended with all of them cancelled and final, and none was falsely logged as cancelled by Kalshi.
- **Restarts (A3):** 300 hard kills at random times, 30% of them with a lost order reply, each followed by the startup sweep. Results:
  - 0 second orders on any coin
  - 0 orders after the exit
  - 0 left resting
  - all orders cancelled within 3 s of the exit or the restart, whichever was later.
- **$1 floor (A5):** 300 races with coins dying at random times produced 1,045 orders. 0 earned under $1, and 0 coins that could have earned $1 were skipped.
- **NO side must qualify:** when the WebSocket book says yes but Kalshi's own book says no (NO side 800, a 99c NO bid, or a full YES side), 0 orders went out. Each was refused at the last look for the right reason.
- **Single-instance lock:** a second process is refused, and the lock frees after the first is hard-killed. A Ctrl-C during an order send leaves nothing behind: the sweep cancels it (A9).
- **Stop file** during the cancel-only window, with GETs hanging: cancels landed within 0.46 s.
- **`--report`** against the real subaccount 4, using GET only (8 GETs) and scratch logs: it prints the leftover, the per-day table, the bar and a verdict. It gave FAIL for a synthetic race 49 h old, and NO_RACES with no live log.
- **Everything the first review passed still passes:**
  - Subaccount 0 is refused in `main`, `start_refusal` and `body_ok`, and subaccounts 1–3 are refused too.
  - The price is the constant 0.0100, and the count is at most 1,000.
  - Every order is post_only, self-trade 'maker', good-till-canceled.
  - At most 5 resting. The $55 limit can't be breached: one order per coin per race caps a race at $50.
  - The code has 1 POST and 2 DELETE call sites, and no transfer endpoint.
  - The bot's helper files (pinracearm, pintake, ordercli, livebook, ladder_live, pinledger) are unchanged since the first review. pinracearm's price ceiling is still 0.98 (:502, :3204), so it can't trade into our 1c bid.
  - The series reports fee_type 'quadratic'.

## My dry run (GET only, subaccount 4, race closing 6:45 AM ET, `KXCRYPTOLEAD15M-26OCT100645`)
- **Sent:** 0 orders or cancels (writes 0). Books came from the WebSocket. A live start would refuse: $0.00 in pool 2.
- **Would-be orders:** 3, each buy 1,000 YES at 0.0100 (post_only, maker, subaccount 4, pool 2): HYPE at 325 s, SOL at 293 s and ETH at 270 s before the close.
- **BTC was refused twice:** first by the day budget at 270 s, then under the $1 floor at 156 s ($0.9993).
- **Exit:** all 3 cancels went out at 59.95 s before the close.
- **Expected credit:** $7.25 in total, every coin over the floor: HYPE $2.81, SOL $2.21, ETH $2.23. Every second on the book counted.
- **Would-fill:** 0 contracts after the queue ahead of us; up to 178 if we had been first in line.
- **Clean-up:** I restored `results\racereward-dry.state.json` byte for byte (hash D62886637BC4…) and removed the dry lock file.

## Resources
- `kalshi_collector` (pid 2532788) and `crypto_feeds` (pid 105352) are alive.
- Free disk 12.4 GB, free RAM 1.6 GB.
- My processes were seen at about 21 MB; I did not measure their peak. None of them is still running.

Files are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\rereview\`:
- attack.py
- a4dbg.py
- a4fix.py
- a789.py
- dry.jsonl
- dry.out
- dry_sum.py