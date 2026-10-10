**Short answer:** yes, but our own bots are only leaving a little: roughly $5–10 a day across all of it, and none of it is proven. The only big money is Kalshi's pay-to-post programs, where Kalshi pays people to keep orders sitting in certain markets. That could be a few hundred dollars a day, but only if Kalshi pays this account, and it never has yet. The coin race test you just approved is what settles that. As it's built now it will probably fail its own bar, and one change fixes that (item 1).

## Ranked: what held up after checking

**1. Coin race pay-to-post test (approved): pull the bids at 60 s before close, not 2 s**
- **Why the change:** in the last minute, sellers dump into 1-cent bids. Of the big 1,000-contract 1-cent piles still up in the last 60 s, 87 in 100 got sold into, about 149 contracts on average.
  - **Held to the close:** fills cost about $7.50–15 a race against about $8.60 of pay. That's about –$6 to +$1 a race even if Kalshi pays.
  - **Pulled at 60 s:** pay falls to about $6.50 a race and fills to about $2.80–5.10. That's +$1.40 to +$3.70 a race.
- **$/day:** $0 if Kalshi doesn't pay us. If it does, about $140–355 a day with the 60-s exit. All 7 races watched were overnight (Thu 10:15–11 PM ET, Sat 4:15–5:15 AM ET), so the daytime figure is unknown.
- **Money needed:** $40 tied up at once, reused every race. The bot won't start with less than $45 in its subaccount, and its dry run showed $0 there.
- **Risk:** at most $40 a race. Over 20 races with no pay, expect about $56–102 of fills with the 60-s exit, or $150–300 holding to the close. Even at 60 s, fills come to 43–78% of pay, so the "fills at most half the pay" part of the bar could still fail.
- **Evidence:** Kalshi's own records show the pool is real, pays $20 a coin every 15 min, and does pay someone. Plus 7 live races watched and 5 days of the market's trade record. We have never seen a payment to us.
- **Cheapest decisive step:** a small code change plus its self-test, then run it. Check the subaccount's cash 24–48 h after the first day of races. If nothing has landed after 48 h, stop: items 7 and 8 die with it.
- **Free check today:** Kalshi's next payout batch is around 3–7 PM ET. It will show whether anyone was paid on the 10-09 treasury programs.

**2. Stop the weather dip-seller (lose less)**
- **Record:** 22 markets, 13 lost, –$6.83 on $23.83 spent (–29% on money spent), –$1.71/day. Four of its 5 weather days were negative. To pass its bar it would need about +15c a contract from here; it has averaged –16c.
- **$/day:** +$1.70 saved (range –$0.40 to +$3).
- **Money:** frees $42, of which only $6–8 was ever at risk. That could fund the item 1 test.
- **Evidence:** our live fills.
- **Step:** its read is due 8 AM ET today. Create `results/dipsell-live.stop`, otherwise the keep-alive restarts it.

**3. Two bots are stuck at a fixed size and don't snowball**
- **Coin race taker (20 a leg, $40 cap).** The check said nothing more was on offer, which is wrong. Half its orders filled in full, so our own size stopped it, not the market. In all 10 orders we could check, more than 20 contracts sat at or under our price (median 125).
  - **At 40 a leg** (cap about $80): +$0.30 to +$2 a day. A tie would cost about $33 instead of $16. Lifetime: 181 races, 6 lost, +2.2% on money spent.
  - **Partly filled orders:** also buying the deeper offers up to 98c would have made +$8.39 over 18 days (17 orders). Small.
- **Bitcoin hourly (KXBTCD), fixed at 1 contract.** 36 markets, 36 won, +$1.54 on $44 (+3.5%). There's plenty on offer (median 833 contracts at or under what we paid).
  - **At 30 contracts:** –$3.40 to +$2.30 a day. It breaks even at about 3 losses in 100, and 36 straight wins still can't rule out 8 in 100.
  - **One loss at 30** can cost up to about $58, because 9 of the 36 markets doubled up late.
- **Evidence:** our live fills plus the order books the bots logged. We have not measured how often they lose at the bigger sizes.
- **Step:** move hourly to 10 contracts, with the bar written first: 40 markets with at most 1 lost and money above $0, then go to 30.

**4. Faster orders: keep one connection to Kalshi open**
- **Measured:** each order opens a new connection. That takes 66 ms against 23 ms on a kept connection, saving 43 ms, and a kept connection still worked after 130 s idle.
- **$/day:** estimated +$1.80 to +$2.90 from 973 of our orders. It is not proven positive, because one kind of losing order (–$77, DOGE 09-23) can't be measured.
- **Money:** $0.
- **Risk:** it touches the order and insurance code. A dead connection must never delay insurance.
- **Step:** build it with an instant fallback to a fresh connection, test on the demo account, then give it its own version entry and bar.

**5. Forecaster: give it more money**
- **Since r28:** 27 markets, +$28 on $132 (+21% on money spent), 2 lost (–$5), $4.14/day on an $84 pot. Money limits it, not offers.
- **At 2x:** +$3/day (range –$1 to +$4). 2x has only run in paper. 8 of its 27 markets were the same bet as the main bot.
- **Problem with its bar:** the 10-13 read can't pass as written. The bar allows buying both sides of a market at most once, and that has already happened 5 times, all before r28. Judging only since r28 would be moving the bar. It already grows with its own pot.

**6. Main bot's "3 tries" lockout (`--attempts-on-send`)**
- **What happens:** the bot counts a try when it decides to buy, even if a later check stops the order. That can lock a coin out for the rest of the 15 minutes with zero orders sent; it happened twice live.
- **Value:** re-checked through every later check at the real size, there were 6 buyable markets in 6 days. That's $2/day if all filled and won, about +$0.30–0.60/day after normal losses. One loss (about $55) undoes 4–5 weeks of it.
- **No test yet:** the paper test cited for it tested a different setting.
- **Step:** a free paper test with the exact live settings.

**7. Treasury-yield hourly pay-to-post (new, Tue 10-13)**
- **The pool:** Kalshi lists $11,200 for 3 AM–5 PM ET (1,120 slots of $10).
- **Competition:** other farmers already sat 600–1,000-contract piles in all five maturities on day 1. One buyer swept 9 piles in 2 minutes, costing those farmers $6–16 each.
- **$/day:** $0 if unpaid. If paid, up to about $700 per listed day on $200 at half share, minus buyouts. Only 2 listed days are known so far.
- **Step (free):** today's payout batch, then poll the books every 60 s on Tue 3–5 AM ET. Put money in only after item 1 shows a payment.

**8. Quiet markets pay-to-post (weekly politics, YouTube views, etc.)**
- **Snapshot:** one Saturday-dawn read gave $983/day on $295 if everything held.
- **Why that's too high:** the sides were picked with the same data used to cost them. 12 of the top 28 are where 1,000-contract piles were eaten in the last 72 h, and weekly markets get swept near the end (21 of 29 last time). The real figure is unknown.
- **Step:** after item 1, a free 3-day watch, then $50 on 5 sides.

**9. S&P 500 hourly late buy**
- **Value:** at the 99.9%-sure level we'd use, the whole market's late selling into 97–98c bids was about $7/day for everyone combined. Realistic for us: $1–4/day.
- **Cost:** needs a new bot and a live S&P price feed we don't have. Its paper bar would likely fail for lack of offers. Low priority.

**Small items:**
- **Ladder:** 9 bids since 09-28 were refused because an offer was already at its price; worth $0.05–0.10/day. Fold the fix into the next ladder build.
- **Moving $270 from main to the ladder: not now.**
  - The precondition hasn't been met: the bank is $1,081 against its $1,095.67 high.
  - It would reverse your 09-20 "only a quarter smaller" choice.
  - Spare room for the late extra buy would drop from about $71 to $17.
  - The ladder has never run above 5 a bid.
  - The same "spare" $280 was counted twice (ladder and forecaster).

## Looked good, didn't hold
- **FX/commodity pay-to-post:** the idea assumed 0.1c prices, but all 7 series trade in whole cents. That leaves the version that lost money in the 09-25 backtest (–$0.67 and –$1.45 a window). Dead.
- **Miami hourly temperature:** 1-cent piles on the losing side get bought out about 4 min after posting. That earlier kill was not part of the 100x pay mistake, and this leans negative even if paid. Dead unless a recording shows piles surviving 20+ min.
- **"Buying deeper coin race offers would have lost $73.61":** the check scored "no" bets as "yes" bets. Corrected, it's +$8.39.
- **Eating other farmers' piles on gas prices:** it looks like one fast bot clears everything at once. Nothing shows a public price feed would call it first. Can't verify.
- **Polymarket:** nothing new. It makes $1–2.50/day on $60, and growing it needs a deposit.
- **Pay-to-post on our own 15-min markets:** there has been none since May. The ladder earns $0 from these programs.
- **Checked, about $0:**
  - Fees: $5.84/day paid, none avoidable.
  - Downtime: 6 of 1,735 closes missed.
  - Errors and stale data: under $0.02/day.
  - Interest: $0.02/day.
  - Stranded cash: $1.49.
  - HYPE: keep it off; live it lost $113.50 over 10 markets.
  - 5-per-second paper bot: read 10-14.
- **Not independently re-checked:** the checker's notes on the fees, downtime, errors and bank-brake items were cut off in what I received, so those figures are the finder's.

## Honest total
- **Proven by our own fills:** +$1.70/day by stopping the dip-seller. That's all.
- **Our own bots, if the size steps and fixes work:** about +$5–10/day more, none of it proven, and a few dollars a day negative at worst. One loss at the bigger sizes ($19–58) wipes 1–3 weeks of that item.
- **Pay-to-post:** $0 until Kalshi pays this account. If it does, a few hundred dollars a day is possible. Those figures rest on 7 overnight races and one Saturday snapshot. Item 1 settles it, at an expected $56–102 if Kalshi doesn't pay.

## What I need from you
- Coin race test: switch it to pull its bids 60 s before close instead of 2 s, before it starts? (A no means running it as approved and expecting it to fail on fill cost.)
- Stop the weather dip-seller now (–$1.71/day, can't realistically pass its bar) and put its $42 toward the test's $45 minimum?
- Bitcoin hourly: raise it from 1 to 10 contracts under the bar of 40 markets, at most 1 lost, money above $0?
- Coin race taker: let its $40 cap grow with the bank along with its size? The cap is your limit.
- Build the faster connection (demo account first, then its own version entry)?
- Forecaster on 10-13: judge it only on results since r28 (that moves the bar), or keep the lifetime rule (it fails)?