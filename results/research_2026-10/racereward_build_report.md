**Built and dry-run. Nothing was sent: both dry runs logged 0 writes, and every call was a GET.**

**File:** `C:\kals-repo\research\sweep\racereward_live.py` (new, not yet in git). The final file's code fingerprint is `8c1d1d5d5714`, and the second dry run ran exactly that file.

Other files it makes or used:
- Dry-run log: `C:\kals-repo\results\racereward-dry.jsonl` (1,562 lines). Dry-run state: `C:\kals-repo\results\racereward-dry.state.json`.
- In live it writes `results\racereward-live.jsonl`, `racereward-live.state.json`, `racereward-report.jsonl`. The stop file is `results\racereward-live.stop`.
- Scratch scripts are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final\money_sweep\build\` (`probe.py`, `report_check.py`, `dry_summary.py`, `dry_summary2.py`, `results_0830.py`, `patch1.py`, `patch2.py`, `dry.out`, `dry2.out`).

**How it is built**
- **Finding races:** same method as `pinracearm.discover()` (open markets in the series, coin from the market's strike field, exactly 5 legs).
- **Orders:** same body as `ladder_live.order_body`; the self-test compares them key by key. Create is POST `/portfolio/events/orders`; cancel is DELETE with subaccount and pool passed in the URL query; sent through `ordercli.send`.
- **Books:** a WebSocket feed via `livebook.LiveBook`, which also carries public trades. Before any order, the book is re-read over REST once as a last look. REST is also the fallback when the socket is down.
- **Reward program:** read from GET `/incentive_programs`. Reward is converted from centi-cents. That endpoint ignores series and market filters (checked today), so it pages the active list and filters locally.
- **Scoring:** the filing's rules exactly:
  - walk the bids from the best price down;
  - the reference price is where the running size first reaches a fifth of the target;
  - stop at the target;
  - credit halves for each cent below the reference;
  - a second counts only if both sides reach the target;
  - a top bid at 99c (the highest possible price) disqualifies that side;
  - credit = $20 × our share-seconds ÷ (2 × 900);
  - nothing is paid under $1 per leg per window.

**Self-test: PASSED, 79 checks, 0 failed.** It covers:
- **Scoring against hand arithmetic:**
  - Alone on the YES side: share 1.0.
  - 300 others at 2c: 0.625.
  - 5,440 others at 1c: 15.5%.
  - NO side under 1,000, or a 99c NO bid: the second is not counted.
  - 360 s alone pays $4.00; 80 s pays $0.89, which floors to $0.
- **Choosing legs:**
  - Best YES bid of 3c qualifies; 4c does not.
  - A YES side already at 1,000 is refused; 999 qualifies.
  - A NO bid at 99c or 98.5c is refused (it would cross); 98c exactly is allowed.
  - A leg with no reward program is refused.
  - Nothing is decided before 360 s out.
  - A world with no dead legs places nothing.
- **Order bodies:** refused for subaccount 0, a price other than 0.0100, count over 1,000 or 0, post_only off, the wrong pool, the wrong self-trade setting, buying NO, another series, a foreign order id, or immediate-or-cancel.
- **Start refusals:**
  - subaccount 0;
  - subaccounts 1–3;
  - unreadable balance;
  - under $45 or over $100;
  - 20 races already done;
  - today's day stop already hit;
  - open positions in the subaccount;
  - today's settled loss at or past $30.
- **Rails:**
  - A 6th resting order is refused.
  - 4 resting ($40) + $10 held + a new $10 is refused ($55 cap).
  - Day stop: −$21 settled − $10 unsettled = −$31 halts, cancels everything, and still blocks a restart.
  - `--races 1` stops after one race.
  - The stop file cancels everything and exits.
  - A 1,000 fill on a leg that loses books −$10.
- **Cancels:**
  - A leg coming alive (best YES 6c) is cancelled at once and never re-placed.
  - The close cancel lands by close−2 s.
- **Write errors can't leave an order up at the close:**
  - Two exceptions plus two 500 errors on cancel: retried every step, still off the book before the close.
  - A lost order reply is matched back by its order id.
  - Lost reply plus a dead fill poller: the close sweep (list resting orders, cancel anything with our id prefix) still cancels it.
  - The book reader crashing every step still ends with the order cancelled.
- **Dry run and code:**
  - The dry run sends no POST and no DELETE.
  - Its would-fill bound includes a planted 99c NO bid.
  - The working code has exactly one POST, two DELETE call sites, and no transfer, deposit, withdrawal or subaccount-creation endpoint.

**Dry run, race closing 4:30 AM ET** (`KXCRYPTOLEAD15M-26OCT100430`; run on the earlier build `a099517c4421`, which differs only in what it logs and the live-only startup sweep)
- At 360 s out, XRP, SOL and ETH had the incumbent's 1c YES stacks of 17,434–37,434 contracts. All three became eligible when those stacks were pulled at 344, 312 and 269 s out. BTC qualified at 57 s out; HYPE was never dead.
- 4 would-be orders, each buy 1,000 YES at 0.0100, subaccount 4, pool 2. All cancelled for the close 3.6 s before it.
- Expected credit by the filing: $7.25 before the $1 floor, **$5.87 after it**.
  - SOL $3.30 (290 of 309 s alone).
  - ETH $2.57.
  - XRP $0.81 → $0.
  - BTC $0.57 → $0.
- All four legs lost (HYPE won), so every contract we would have bought loses its 1c.
- Would-fill from public trades at 1c: 0 contracts after the queue that was ahead of us; up to 404 contracts (~$4.04) if we had been first in line.
- **Finding:** XRP was not counted for 256 of its 341 s and ETH for its last 36 s, because the NO side had no qualifying bids. The likeliest cause is a NO bid resting at 99c, but the build that ran didn't log the NO price, so I couldn't confirm it for this race. If that's what it was, then with our bid really there it would have traded into it. The code now logs best NO and 99c NO size every second and adds that size to the would-fill upper bound.

**Dry run, race closing 4:45 AM ET** (`KXCRYPTOLEAD15M-26OCT100445`, final code)
- 4 would-be orders: BTC at 360 s out, ETH 317, SOL 271, HYPE 201.
- BTC, ETH and SOL were cancelled as "alive" at 209 and 177 s out (best YES rose to 9c), at the same time as the incumbent re-stacked 4,888–6,204 at 1c. HYPE rested to the close.
- Expected credit: $4.35 before the floor, **$2.01 after it** (only HYPE reached $1). BTC, ETH and SOL each fell just under $1 (shares of 36–89%).
- No 99c NO episodes. Would-fill: 0 contracts after the queue; up to 124 (~$1.24) if first.
- XRP won; all four of our legs lost.
- **Two races together:** $7.88 after the floor, about $3.94 a race. The 10-09 three-race sample said $8.55–13.41. Two races are too few to project a day.

**Report mode, checked live (GET only):** subaccount 1 reads $80.38 cash − $65.00 transferred in − $15.38 settled P&L (134 markets) = **$0.0000 leftover**. Subaccount 3 reads $38.17 + $5.00 open − $50.00 − (−$6.83) = **$0.0000**. Both match the 10-10 reconciliation. It reads all 4 cash pools; subaccount 3's cash sits in pool 0.

**Interaction with the other bots**
- **Coin race bot (`pinracearm.py`, main account, running as pid 2697236):**
  - Its price ceiling is 0.98 (line 502). Any ask above it is refused at line 3204 before the live path.
  - The live order goes out through `pintake.take` at that same ask (≤ 0.98), and its self-test (line 1257) checks the ceiling is at most 0.98.
  - A NO buy at ≤ 98c sells YES at ≥ 2c, so it can never match our 1c YES bid. Its YES buys have a 0.90 floor and trade against NO bids, a different side.
  - Even if the ceiling were raised to 99c: self-trade prevention works across subaccounts, and the race bot uses `taker_at_cross`, so its own order would be cancelled and nothing would trade.
  - Side effect: on dead legs our bid shows as a 99c NO offer, which the race bot just logs as "above ceiling".
- **Main bot (`pinrun`, `C:\kals-live-0925e`):**
  - It trades only the 11 up/down 15-minute series plus `--series KXBTCD`.
  - It reads positions for the primary account only.
  - It finds its own orders only by its "pin-" ids; ours start "rrw-".
  - Its own self-test checks that a position in this coin-race series is NOT adopted or hedged.
- **Ladder, forecaster, dip-seller:** no reference to this series in any of them. Their subaccounts (1, 2, 3) are refused in code.
- `kalshiwatch` only reads the newest order's format; harmless.
- **Load on the shared API key:**
  - Writes: at most 10 a race, capped at 3 a second.
  - Reads: discovery every 30 s, about 2 pages of programs a race, one REST book per placement, and a fill check every 2 s while an order is live.
  - It adds one more WebSocket connection, as each race-bot process already does.

**Things the live test should know**
1. **Any fill ends the reward on that leg.** With 1,000 contracts and a 1,000 target, even a partial fill leaves the YES side under the target unless others bid. The leg then stops paying for the rest of the window, so a fill costs its cents plus the remaining credit.
2. **The "alive above 5c" cancel fired on the incumbent's re-quote in race 2**, cancelling 3 of 4 orders early. That is the rule as specified; the log has the data to judge it.
3. **Live needs a new, funded subaccount, which I did not create or fund.** The dry runs used subaccount 4, which doesn't exist and reads $0, so live would refuse it: "$0.00 in pool 2, under the $45 floor". The coin-race pool is pool 2.
4. **Funding it from the main account shrinks the main bot's bets.** Its bet is the main account's money ÷ 11.76, so moving about $55 makes each bet about $4.70 smaller.
5. **A reward paid to the primary account would not show in `--report`.** The whole-account check in `recon.py` covers that case.
6. **Rails I added beyond the spec:**
   - subaccounts 1–3 refused;
   - start refused while the subaccount holds positions, or when Kalshi's own settled P&L for today is −$30 or worse (so the day stop survives a restart even if the state file is lost);
   - a live startup sweep cancels any of our orders left resting;
   - the 20-race count carries across restarts;
   - the day stop counts unsettled fills as already lost.
7. **Not done:** no entry in `READS_DUE.json` or `VERSIONS.md`, and no git commit. Both entries are due in the same commit as the live start.
   - Live command: `python research/sweep/racereward_live.py --subaccount N --live --races 20`.
   - Readout: `--report` 24–48 hours after the last race.
   - Pass bar (LADDER_UPSIDE section 7): at least $1 credited on at least 15 of the 20 races where we sat alone 90 s or more; fill cost at most half the credit; zero self-matches.

Recorders are alive (`kalshi_collector` pid 2532788 at 44 MB, `crypto_feeds` pid 105352 at 27 MB). Free disk is 14.9 GB and free RAM about 2.0 GB. The bot process peaked at about 54 MB.