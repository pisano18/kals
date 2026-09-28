# Why the Polymarket bot has not traded -- 2026-09-28

The Polymarket bot has made no trades for three reasons. (1) It is a paper bot: it has no code that places orders. The real order tool passed its 1-cent test on 09-26, but the step that lets it act on the bot's buy signals is not built. (2) The paper bot has been blind since 2:00 AM ET on 09-26, about 45 hours. Polymarket sent the error "max subscriptions per connection reached", and the bot did not notice. So its 173 "no_offer" windows mean it received no prices at all, not that nobody was selling. (3) When it could see prices, the kind of deal we buy existed in only about 18 of 100 fifteen-minute windows, and the most it could make is about $6/day at 10 contracts a buy.

**Why it is blind (checked):** The price recorder and the paper bot use the same key. Each opens one connection and adds 2 new subscriptions per window, and never drops old ones. After 5 requests (about 75 minutes) Polymarket answers `{"error":"max subscriptions per connection reached"}`. From then on, new windows never get prices. Neither program reads that error. The recorder's last price update was at 2:00 AM ET on 09-26. The paper bot had no prices in any of the 7,830 seconds in its current log. The same thing blinded it earlier, 8-11 PM ET on 09-25. It only came back when the connection happened to drop and reconnect.

**What it did while it could see (6:26 PM ET 09-25 to 2:00 AM ET 09-26):** It had prices in 22 windows and made 6 Polymarket paper buys of about 10 contracts each. All 6 won, for +$1.63 in total.

**Where the sellers are.** Recorded prices cover 57 fifteen-minute windows and 25 one-hour windows, 11 PM ET 09-24 to 2 AM ET 09-26. This is what the market offered, not our fills.

| Time before close | Leading side's typical price | Leading side offered at 98c or less | Side our model called certain (>=99.5%) offered at 98c or less | Contracts traded per window (15-min / 1-hour) |
|---|---|---|---|---|
| last 15 s | 99c | 1 of 57 windows | 0 of 57 | 1,707 / 289 (mostly holders selling the winner at 99c) |
| 16-30 s | 99c | 8 of 57 | 6 of 56 | 2,280 / 583 |
| 31-45 s | 97c | 13 of 57 | 8 of 54 | 2,528 / 739 |
| 46-60 s | 96c | 19 of 57 | 7 of 45 | 2,520 / 883 |
| 1-2 min | 92c | 31 of 57 | 13 of 41 | 8,315 / 1,997 |
| 2-5 min | 89c | 52 of 57 | 16 of 31 | 20,599 / 4,041 |
| 5-15 min | 62-72c | every window | (rarely certain) | about 28,000 / about 4,500 |

When the certain side is offered at 98c or less, there are usually 700 to 2,000 contracts for sale. The one-hour market has the same pattern with about 1/6 of the trading.

**Each idea tested on the recorded prices.** "Won/lost" counts how the market's offers turned out. It is NOT how often we would lose: on Kalshi the recorded prices said 1 loss in 900, while real fills lost about 3 in 100.

| Idea | 15-min windows | 1-hour windows |
|---|---|---|
| A. Live rule: last 45 s, model >=99.5% sure, buy at 98c or less | fires in 10 of 57; 10 won, 0 lost; +2.5c per contract | 6 of 25; 6 won; +3.4c |
| B. Buy earlier (2-5 min before close) when the model's chance beats the price by 2-5c | 21-24 fires, 2-4 lost, -6c to 0c per contract | 16-20 fires, 1-4 lost, -6c to +4c |
| B2. Buy the leading side at 90-98c, 1-5 min before close, no model | 49 fires, 3 lost, +1.0c | 22 fires, 2 lost, -2.7c |
| C. Bid 97c on the certain side, last 30 s (like the ladder) | a sale hit 97c or lower in 13 of 57; 13 won; +3.0c; typically 23 contracts; our place in line not modelled | 13 of 25; 13 won; +3.0c |
| C. Same bid, last 60 / 120 / 300 s | 1-2 lost; -1.4c to -5c | 1 lost; -1c to -5c |

**Money:** A and C together would have had something to buy in 15 of 57 fifteen-minute windows, about 26 in 100. That is about 25 chances a day across both markets. At 10 contracts that is about $6/day if nothing loses. One loss at 97-98c costs about $9.70, which wipes out about 1.5 days.

## Recommendation
1. Fix the blindness before judging Polymarket. In research/polypaper.py (ws_loop) and scan_poly_ws.py: drop each window's subscriptions once it closes, or reconnect every window. Treat any `error` message, or 10 seconds with no price update for the current window, as "reconnect". The paper bot also needs to log that it has no prices, instead of calling it `no_offer`. I did not stop or restart either program. Someone has to restart them after the fix.

2. Smallest test: run the fixed paper bot for 3 days (about 290 fifteen-minute and 72 one-hour windows). These bars are written before the result is seen:
- Stop Polymarket if the certain side is offered at 98c or less in fewer than 10 of 100 windows, or if prices are missing in more than 5 of 100 windows.
- Go on only if it is offered in at least 15 of 100 windows, with at least 20 contracts typically for sale.
- If it passes, run the live Step 2 already written in POLYMARKET_ORDERS.md: 1 contract a buy, 20 buys, at most $0.98 at risk each. Stop at 2 losses. It passes only with fills in at least 10 of the 20 and a typical price of 97.5c or less.
- Optional after that: 1-contract resting 97c bids on the certain side in the last 30 s (at most $0.97 each). polyorder already refuses to leave one resting more than 60 s.

3. Drop the "buy earlier" and "1-hour market" ideas. Before the last minute, crowd prices were about right (between -6c and +4c per contract, with losses). The one-hour market has the same shape with about 1/6 of the trading.

4. Plainly: Polymarket does have sellers for this strategy, but only about 1 window in 4. Even at full success it is a small add-on (about $6/day at 10 contracts). It is not the answer to "something needs to make more money".

## Caveats
- **The brief's premise was wrong.** "Nobody offered the decided side" was an artefact: the paper bot had no prices at all in all 7,830 logged seconds.
- **Small, old sample.** Only 57 fifteen-minute and 25 one-hour windows, about one day (11 PM ET 09-24 to 2 AM ET 09-26, with gaps). Nothing was recorded after that because the recorder hit the same subscription limit. Every window count here is small.
- **Win/loss counts come from recorded prices, not our fills,** so they can't give our loss rate (hard rule 5).
- **The resting-bid idea (C) is an upper bound.** It ignores the thousands of contracts bid ahead of us. Paper can't show whether we would get filled.
- **The model's chance in idea B is a simple stand-in written for this analysis, not the live bot's pricing code,** so B's results are only a rough guide.
- **Two data repairs:**
  - The recorded price file had a broken segment from a recorder restart. I read it segment by segment: 3 segments, 1 skip.
  - I dropped any second where the last price update was more than 10 s old. This removed one false 28c "buy" in the 1-hour window that closed at 11:00Z (7 AM ET) on 09-25.
- **Win/loss comes from our own index tape.** For windows the paper bot logged, its Polymarket start price matched our index to the cent in the earlier checks.
- **Current paper-bot log is missing its start.** It begins at 3:44 AM ET 09-26. The version saved in git starts at 6:26 PM ET 09-25. The first ~9 hours were overwritten in the working copy, so I used the git copy for that period.
- **Free memory went below the 0.6 GB limit (0.33-0.52 GB) early in the session.** My programs stayed small (about 40 MB) and ran one at a time; at the end 1.09 GB was free.
- **Nothing stopped, restarted, ordered or written under C:\kals.** kalshi_collector.py (pid 2532788) and crypto_feeds.py (pid 105352) are both running. Free disk: 64.4 GB.
