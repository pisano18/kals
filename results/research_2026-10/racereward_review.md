REVIEW.md was not written because this harness doesn't let subagents write report .md files. The full review follows.

# racereward_live.py: independent review (code fingerprint 8c1d1d5d5714)

## Verdict: GO for the 20-race live test, with 2 conditions
1. **Fund the new subaccount with no more than about $55 in pool 2.** The start window allows $45–$100. The bot's own day stop is not a hard cap (N2), so the subaccount's cash is the real limit on what can be lost.
2. **Rewrite the pass bar before the first order.** As written it can't be measured (N8).

These should be fixed before launch. Each is a few lines and each reduces losses: N1, N2, N3, N4.

## Blocking defects: none
I found no path to any of these:
- an order from subaccount 0;
- any price other than $0.01;
- more than 1,000 contracts;
- a ticker outside KXCRYPTOLEAD15M;
- a taker order;
- a trade against the coin-race bot (pinracearm) or pinrun.

Every defect below is limited to $10 per leg and by the subaccount's cash.

## What I ran
- **`--selftest`:** passed, 79 checks, 0 failed. The fingerprint matches 8c1d1d5d5714.
- **One-race dry run** (GET only, subaccount 4), race closing 5:15 AM ET:
  - 4 would-be orders: ETH at 262 s out, XRP at 222 s, BTC at 206 s, SOL at 205 s.
  - XRP and SOL were cancelled within 15–25 s because those coins came back to life ("alive" cancels).
  - ETH and BTC were cancelled for the close 3.0 s before it.
  - Expected credit: $4.19 before the $1 floor, **$3.91 after it** (ETH $1.76, BTC $2.15, XRP and SOL $0).
  - Would-fill: ETH 0–226 contracts (156 of them from a 99c NO bid), BTC 0–99.
  - 0 writes sent.
  - I backed up the builder's `results/racereward-dry.state.json` before the run and restored it byte for byte afterwards. My log is `review_dry.jsonl`.
- **GET-only API probe** (`review_probe.py`, `review_probe2.py`, `review_probe3.py`).
- **15 attack cases** run against the bot's own fake exchange, with a real loop and latency (`review_break.py`, `review_break2.py`).

## Checklist
1. **Order limits: PASS.**
   - Subaccount 0 is refused at three points (`main` :1630, `start_refusal` :338, `body_ok` :300); subaccounts 1–3 are refused too.
   - Subaccount 4 does not exist yet. `/portfolio/subaccounts/balances` lists only 0–3, and a missing subaccount reads $0.00 with HTTP 200 (probed 4, 5, 9 and 63), so a live start is refused under the $45 floor.
   - Price "0.0100" is a constant with no price argument. Count = min(1000, program target).
   - The code has 1 POST and 2 DELETE call sites, and no transfer or deposit endpoint.
   - At most 5 resting and at most $55, by rail. One order per leg per race within a process; across a restart it can be two (N7).
2. **Every order off the book by close−2 s even when things fail: FAIL.** See N1, N5, N6.
3. **Day stop and run stop survive a restart: PASS.**
   - What carries over: `halted_day` in the state file, Kalshi's settled P&L for today (−$30 or worse refuses a start), any open position in the subaccount (refuses), the race count in the state file, and the stop file.
   - But the day stop does not cap the day's loss (N2).
4. **post_only and self-trade setting "maker" on every order: PASS.** There is one body builder, `body_ok` enforces both, and the body matches `ladder_live.order_body` key for key.
5. **Can't cross pinracearm, doesn't disturb pinrun: PASS.**
   - pinracearm only buys at asks of 98c or less (`PRICE_CEILING` pinracearm.py:502, enforced at :3204). Its immediate-or-cancel limit equals the ask, with no slippage. So a NO buy sells YES at 2c or more and can never reach our 1c bid. Its own self-trade setting is taker_at_cross.
   - No other bot trades KXCRYPTOLEAD15M. pinrun has it only inside a self-test.
   - Our sweeps cancel only `rrw-` orders in our own subaccount. The other bots' order polls match only their own order ids.
   - pinrun's v-bankmove reads subaccount transfers, so the funding move is recognised as a withdrawal. Its bets shrink by about $4–5 for every $50 moved out.
6. **Scoring matches the filing: PASS.**
   - The bot follows the filing:
     - reference price at target/5;
     - whole price levels walked down to the target;
     - credit halves for each tick below the reference;
     - both sides must reach the target;
     - a 99c top bid disqualifies that side;
     - credit = $20 × share-seconds ÷ 1,800;
     - $1 floor per leg per window.
   - Reward units are centi-cents: 200000 → $20.00. Verified live: all 5 legs of the 5:00 AM ET race have a 900 s period, target 1,000 and 5000 bps.
   - One nuance that affects only the dry run's estimate: N9.
7. **Stop file: PASS.** It cancels everything, sweeps by client-id prefix and exits; a restart is refused while the file exists.

## Non-blocking defects (most important first)

**N1. The close cancel is best effort, not guaranteed. Medium; fix before live.**
- **Where:** `close_deadline` :830-832 leaves only 0.5 s + ⅓ s per order of slack. Everything runs in one thread (`step` :991-1035): discovery, the REST last look, the fill poll, settlement reads and REST book reads all share the loop with the cancels. Every call can block for 20 s (ordercli.py:190). There is no writer thread.
- **What breaks:**
  - **Socket down, 0.12 s per call:** the last cancel lands after close−2 s in 3 of 40 runs with 1 order and 4 of 40 runs with 5 orders. The latest landed 1.86 s before the close.
  - **One 3-second GET in the last 6 s:** a single order's cancel lands 0.40 s before the close.
  - **One 20-second hang starting at close−8 s:** no cancel is ever sent. Time jumps past close+10 s, :843-846 marks the orders `expired_at_close`, and the sweep window at :850 has already passed. The orders rest until Kalshi closes the market. Kalshi then answers 409 `market_closed` or 404; the ladder's live log shows this pattern on 10,221 cancels.
  - **Socket up at 0.12–0.30 s per call:** 0 of 120 runs were late.
- **Cost:** still at most $10 per leg. The builder's claims "all land by then" and "write errors can't leave an order up at the close" are false.
- **Test blind spot:** the self-test check at :1441 reads `cancel_t`, which is the step's start time (:616), not the send time. In one 4-order run every order was recorded as cancelled 3.77 s before the close, but the cancels actually landed 2.65–3.65 s before.
- **Fix:** in the last ~15 s before a close, skip every call except cancels; start cancels at close−2 − n/3 − 2 s; use a short (~2 s) timeout on calls near the close.

**N2. The day stop only fires after a loss and does not limit new orders. Medium.**
- **Where:** `rails_refusal` :510-521 has no day-budget term. `check_day_stop` :523-531 runs only on a fill or a settlement.
- **What breaks:** with $29.99 already lost, a new race still rested 3 orders ($30). If all fill on losing coins, the day ends at −$59.99. The realistic worst day is about −$30 plus −$40 (4 losing coins) ≈ **−$70**, capped only by the subaccount's cash.
- **Fix:** refuse a new order when realized − unsettled cost − resting collateral − $10 < −$30.

**N3. Orders that can never earn are still placed. Medium; pure cost.**
- **Where:** :855. The only time limit on a new order is the cancel deadline (close−2.5 s when nothing rests).
- **Why it matters:** the $1 floor needs at least 90 s alone ($20 × 90 ÷ 1,800).
- **What breaks:**
  - A coin that went dead 3 s before the close got an order sent at close−2.62 s.
  - An order placed 80 s out was worth $0.86, floored to $0.
  - In the builder's 4:30 AM ET dry run, BTC was placed 57 s out: $0.57, floored to $0.
  - Such an order also uses up one of the 20 test races if it is that race's only order.
- **Fix:** no new order unless (close − 2 − now) × current share × $20 ÷ 1,800 ≥ $1. When alone, that means at least about 92 s left.

**N4. Orders go on coins whose seconds can't count. Low–medium; pure cost.**
- **Where:** `leg_refusal` :268-277 checks the NO side's best price but not whether the NO side reaches the target.
- **Evidence:** in the builder's 4:30 AM ET dry run, XRP was not counted for 256 of its 341 s and ETH for its last 36 s, because the NO side had no qualifying bids.
- **Fix:** require the NO side to qualify when placing.

**N5. A fill near the close can vanish from the bot's own books. Low–medium.**
- **Where:** :843-846 marks an unconfirmed order `expired_at_close`, and the poll list at :685 never includes that status again.
- **What breaks:** cancel and poll both fail through the close, and the order fills 1,000 contracts at close−1 s. The bot shows 0 filled, never settles it, and its day total stays $0.00 while Kalshi books −$10.00. The race is then dropped. A restart would catch it (open-position and settled-P&L checks); the running process doesn't.
- **Fix:** keep polling until Kalshi reports the order final.

**N6. A 404 on cancel is taken as "off the book" without checking. Low.**
- **Where:** :621-622. Only `unknown` is revived to resting (:708).
- **What breaks:** a 404 while the order still rests → status `gone`, only 2 cancels ever sent, and the order rests to the close.
- **Why low:**
  - The cancel URL and query are identical to the working ladder's.
  - The live ladder's 158 pre-close 404s fit orders that had already filled.
  - But the ladder itself treats a 404 as a failed cancel and re-checks it.
- **Fix:** confirm with a GET before marking an order gone.

**N7. "One order per coin per race" holds only within one process. Low.**
- **Where:** state records races, not coins (:562-567).
- **What breaks:**
  - A restart mid-race: the startup sweep cancels the first order, then a second order goes to the same coin in the same race.
  - The startup sweep ignores a failed cancel of a stray order and still returns True (:657-664).
  - There is no single-instance lock, so two live processes would double every rail. The other live bots also have none.

**N8. The pass bar can't be measured as written. Process issue; restate before the first order.**
- The bar ("≥$1 on ≥15 of 20 races sat alone ≥90 s; zero self-matches") needs per-race attribution.
- `--report` (:1082-1179) gives one leftover reading per ET day, and credits arrive 16–40 h later with no line item. So rewards can't be attributed to individual races.
- An exchange-side self-trade cancel looks like any other cancel to the poller (:710-713). So "zero self-matches" is never measured.
- **Proposed bar:** total leftover 48 h after the last race vs the sum of `expected_credit_floored` over races where we sat alone ≥90 s. Also log an `exchange_cancelled` event when Kalshi shows "canceled" on an order we never asked to cancel.

**N9. Scoring nuance, dry run only. Low.**
- **Where:** :251 counts a second where the NO side's top bid is 99c as excluded.
- **Filing rule:** a second is excluded only when resting size is under target on a side. Under the filing that second still counts, with the NO side scoring 0. So dry-run credit understates those seconds.
- This can't happen live: a 99c NO bid would trade into our 1c bid.
- The reference-price rule relies on reading struck text in an extracted redline. It makes no difference when we sit alone at 1c.

**N10. Minor.**
- **:792-795** uses an assumed $20/1,000 program when the program list can't be read. An order on a coin whose program has ended is pure cost; refuse instead.
- **:1000-1007** a stop in mid-race skips that race's summary, so its expected credit is missing from the report.
- **:1018-1021** an error on one coin skips the remaining coins for that step. The close cancel is unaffected.

## API assumptions verified live (GET only)
- **Positions:** `count_filter`/`settlement_status` work, and `market_exposure_dollars` is present.
- **Order listing:** honours `subaccount`, `status=resting` and `min_ts`, and carries `client_order_id`, `fill_count_fp` and `maker_fees_dollars`.
- **Settlements:** the subaccount filter works.
- **Transfers:** the fields are as the code expects.
- **Incentive list:** 2 pages, 6,178 active programs, read in 0.86 s.
- **`--report`:** on subaccounts 1 and 3 it reconciles to $0.0000, so a fresh subaccount is a clean credit detector.
- **DELETE success reply:** `{order_id, reduced_by, ts_ms}`, taken from the ladder's log. The bot's cancel step books no fill from that reply; the poller does.

## Before launch (operator steps)
- Create subaccount 4 and fund pool 2 with $45–55. Neither the bot nor this review sends that request.

## Resources
- Every review process stayed under 50 MB. No review process is still running.
- `kalshi_collector` (pid 2532788) and `crypto_feeds` (pid 105352) are alive.
- Free disk 13.3 GB, free RAM 2.1 GB.

Files are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final\money_sweep\build\`:
- review_probe.py
- review_probe2.py
- review_probe3.py
- review_break.py
- review_break2.py
- review_ladder_dels.py
- review_dry.jsonl
- review_dry.out
- review_dry_summary.py
- racereward-dry.state.backup.json