# Live bots report -- 2026-10-01 ~13:00Z (9 AM ET)

Built by workflow wf_45eaa6a4-c7e (one analyst per live bot + one writer); Kalshi money. Checked by hand afterwards: the early-cap lockout (13 markets in the 09-30 12:12Z run refused early_dear at 98c then market_attempts in the same second, never ordered) and the false withdrawal/deposit (external records 07:15:21Z -84.62 and 09:00:22Z +87.00 during the Thursday 3-5 AM ET closure; also -1.14 at 01:00:35Z = the coin race loss read as a withdrawal). CORRECTION applied in the reply: crediting the seller gate with the full bet it locked out means charging its cost with the full bets it locked out too -> roughly even, not +$43-85 vs $18-40.

**The -$108.28 is not a loss.** The Kalshi app shows only the main pot. That pot holds $1,044.96 now, and the app compares it with $1,153.24, which was all three pots together at midnight. All three pots now hold $1,177.17, so the bots are **up $23.93 today**. The main pot alone is up $19.81 since midnight.

**The $40 loss:** the main bot, on XRP at 7:15 PM ET yesterday, lost $42.60. With 20 seconds left, sellers were dumping XRP. It bought 89 contracts, starting at 88c and paying up to 98c. Its confidence then fell, and insurance bought the other side. The bet lost $84.65 and insurance won back $42.05. The seller check couldn't have caught it: that offer had been sitting for 14 minutes, and the check is off in the last 20 seconds. A "never buy right after a dump" rule just broke even on 10 past cases (+$0.01 total). A narrower idea is worth measuring: buy only what is offered at the first price and don't chase it up. Only 11 contracts were at 88c, so this loss would have been about $5-10.

**Your $30-vs-$40 question: yes, keep the seller check.** The $30 is a floor and the $40 is a ceiling.
- **The $30 saved** (BTC 1:30 PM ET 09-29) only counted the small early bet. The check also kept BTC out of the full bet, so the real save is about $43-85.
- **The $40 missed:** $21.80 of it was coins the bot bought anyway at a smaller size. Only $17.86 was truly missed.
- **Net:** over 4 days it saved $43-85 and cost $18-40. That rests on one save, so I'll re-count on 10-08.

| Bot | Today | Since last change | Last 7 days | All time | Pot now |
|---|---|---|---|---|---|
| Pin (main) | +$19.76 (3.7%), 10 of 10 won | +$2.13 (0.1%) since 09-30 8:12 AM | +$130.52 (1.1%), 5 lost of 227 | +$676.09 (1.2%) | Main $1,044.96 (shared with race) |
| Coin race | +$0.05 (1 bet) | -$1.10 (2 bets) since 40 a bet, 09-30 8:25 AM | +$17.51 (3.9%) since 09-24 | +$18.47 (3.2%) | Main pot |
| Forecaster | +$2.91 (2 bets) | +$7.14 (9.4%) since 1/10 size, 09-30 8:26 AM | +$12.84 (9.4%) | Same as 7 days | $63.82 = +25% on $50.98 put in |
| Ladder | +$1.21 (2.1%) | +$3.06 (2.1%) since 5 a bid, 09-30 8:26 AM | +$3.39 (2.1%) | Same as 7 days | $68.39 = +5.2% on $65 put in |
| **All** | **+$23.93** | | | **+$592.71** | **$1,177.17 = +101% on $584.46 deposited** |

The % column is profit per $1 bet: 1.1% means 1.1 cents back for every dollar bet. Pin's "+$2.13 since its change" is 29 wins (+$44.73) minus the XRP loss (-$42.60).

**Pin**
- **Income has halved, but each bet earns the same.** A typical day is now $23, against $54 for 09-20 to 09-26, because it buys about 25 coins a day instead of 50. Each bet still earns about 3c per $1.
  - The biggest cause, about 11 coins a day, is a side effect of the 09-28 change. The early bet (45 seconds before close) refuses coins at 97.9-98c. Those refusals use up the coin's 3 tries, so the coin is locked out of the later bet (30 seconds before close), where 98c is allowed. That happened to 33 coins in 3 days.
  - Fixing it is worth $0-11 a day and can be tested on paper first. It adds volume, not safety: at 98c, one loss eats about 50 wins.
- **Insurance is paying lately.** Since 09-27, three real alarms saved $129.78 and one false alarm cost $44.88. Over its whole life it is now about break-even; it was -$55 on 09-27.
- **Worry: the margin is thin.** A win pays about $1.65. An insured loss costs about $43 (25 wins); an uninsured one about $85 (50 wins). This week it lost 2 times in 100, and at 98c the break-even point is about 2 in 100. One insured loss wipes out about two days of income.
- **Worry: a bug.** Kalshi's Thursday maintenance delayed an $84.62 payout at 3 AM ET today.
  - The bot read the delay as a withdrawal. It shrank its bets from 87 to 80 contracts for about 1¾ hours and reset its "stop after a 20% drop" mark twice.
  - If the same misreading happened during a real loss, that stop would not see the loss. This needs a fix.

**Coin race**
- **Small and steady.** It made +$17.51 since 09-24 (about $2.50 a day) and won 66 of 68 bets.
- **40 a bet has added nothing.** In a day it got 2 of the 94 contracts it asked for, against 46 in 100 at 20 a bet. What it did do is double what one loss costs: a full losing bet at 40 is $36-39, about 2 weeks of this bot's profit. Last night's 9 PM ET loss was only $1.14 because just 1 of the 40 contracts filled.
- **The 97-98c bets carry the risk and earn little.** They were 138 of 176 bets since 09-22 and made $6.80 on $388 bet. One loss at 40 contracts there (-$39) wipes out about 6 times everything that price range has ever earned. Its 90-93c bets made $9.65 on $100.
- **Worries:**
  - Its "stop after 2 losses a day" count resets on every restart, and the keep-alive restarted it at 3:42 AM ET today.
  - It went silent from 3:01 to 3:42 AM ET and missed 2 races, while the keep-alive reported "all up" four times. No money was affected.
  - The phone stats show its rules wrong ("20 a bet", "stops after 1 loss"). The money numbers there are right.

**Forecaster**
- **Best return per dollar.** It made +$12.84 in 2.5 days, won 31 of 35, and earned about 9.4c per $1 both before and after the size step. Luck alone gives a result this good about 4 times in 100, so this is encouraging, not proof. Its worst loss ever is -$5.42 (SOL, 10:45 AM ET 09-30, bought both sides 14 seconds apart).
- **Its paper copy is no guide.** Over the same days, paper was -$15.59 at live size while live was +$12.84.
  - The crash guard skips a buy when the offer is collapsing. It skipped 5 bets: 4 would have lost $14-27 and 1 would have won about $2.
  - Keep it at 10c; tomorrow's 8 AM ET check passes.
- **Worry: it will lock itself out.** It refuses to start if its pot is over $70.05. At $63.82 and gaining $5-7 a day, it crosses that in about a day. After that, any restart leaves it off with no alert: a reboot, a crash, or its scheduled end on 10-07 at 8:26 AM ET.
- **Hold its size until the 10-06 check.** It has 35 of the 60 markets that check needs. One more loss from buying both sides fails it.

**Ladder**
- **Its record proves nothing yet.** It is +$3.39 and has won 32 of 32, about $3 a day. But a win pays about 2c a contract and a loss costs about 98c, so it must win 98 of every 100 just to break even. A bot that only breaks even still goes 32 for 32 about half the time. About 150 markets (roughly another week) would settle it.
- **Worry: one bad quarter-hour costs about $49.** That is its 50-contract cap: 72% of its pot, or about 16 days of profit. It has run near that cap 16 times since 09-30. Two markets took 20 contracts each, putting $19.58 at risk to win $0.41.
- **It doubles up on pin instead of spreading risk.** In 8 of its 32 markets it bet the same side as pin. Both 20-contract bets were on NEAR while pin held $87 and $128 on the same side. If NEAR had gone the other way, the two pots together would have lost $106-148.
- **It has the same start-limit trap.** It refuses to start above $73, and at $68.39 plus about $3 a day it gets there around 10-02 or 10-03.

**Other things to know**
- **Whole account: +$592.71 on $584.46 deposited.** By bot: pin +$676.09, race +$18.47, forecaster +$12.84, ladder +$3.39. Old tests that are no longer running lost $118.06: oil, gas and gold from 09-07 to 09-18, plus one $10 Tencent bet on 09-28. These match Kalshi's cash to within 3 cents.
- **The $116 moved into the ladder and forecaster pots makes pin's bets about 11% smaller.** That's about 88 contracts instead of 98, worth roughly $2 a day of pin income. Yesterday those two pots made about $10.
- **Disk: 43.4 GB free.** It has been dropping about 5 GB a day for the last two days. At that pace it reaches the 6 GB safety line around 10-08; at 5 GB the recorders stop for good.
- **Everything was running at 9:03 AM ET:** both recorders and all four bots.

## What I need from you
- Seller check: keep it on (my pick; I re-count on 10-08) or turn it off?
- Coin race size: back to 20 a bet (my pick), 40 only on bets at 96c or less with 20 at 97-98c, or keep 40 on everything?
- Forecaster and ladder pots are near their start limits ($70.05 and $73). Move the profit back to main (forecaster down to about $56, ladder to $65; my pick) or raise both limits (for example to $100)? Without one of these, the next restart leaves them off.
- Ladder limits: cap each market at 10 contracts and each quarter-hour at 25, or leave them as they are? The caps cut the worst market from $19.58 to $9.80 and the worst quarter-hour from $49 to $24.50. They would have cost $0.41 of its $3.39 so far.
- Disk: buy the 2 TB drive before about 10-08, or OK deleting old restore points (frees 9.7 GB) and turning off hibernation (frees 6.8 GB)? That second option only buys about 3 more days.

## Per-bot analyst output (raw)

```json
[
 {
  "bot": "pin (main bot, research/pinrun.py --live, pid 4447780, v-topup since 09-30 8:12 AM ET; main account, which it shares with the coin race). Still running at ~8:50 AM ET. Recorders are alive and the drive has 43.4 GB free.",
  "table": [
   {
    "window": "Today, ET Thu 10-01 (to ~8:50 AM ET)",
    "dollars": 19.76,
    "markets": 10,
    "lost": 0,
    "put_in": 539.89,
    "pct_of_put_in": 3.66,
    "pct_of_pot": 1.93
   },
   {
    "window": "Yesterday, ET Wed 09-30",
    "dollars": 12.45,
    "markets": 31,
    "lost": 1,
    "put_in": 1720.66,
    "pct_of_put_in": 0.72,
    "pct_of_pot": 1.14
   },
   {
    "window": "Since v-topup (09-30 8:12 AM ET)",
    "dollars": 2.13,
    "markets": 30,
    "lost": 1,
    "put_in": 1613.23,
    "pct_of_put_in": 0.13,
    "pct_of_pot": 0.2
   },
   {
    "window": "Last 7 days, ET 09-25..10-01",
    "dollars": 130.52,
    "markets": 227,
    "lost": 5,
    "put_in": 11809.96,
    "pct_of_put_in": 1.11,
    "pct_of_pot": 12.75
   },
   {
    "window": "7 days before, ET 09-18..09-24",
    "dollars": 79.71,
    "markets": 393,
    "lost": 10,
    "put_in": 24198.99,
    "pct_of_put_in": 0.33,
    "pct_of_pot": 8.22
   },
   {
    "window": "All time (08-15..10-01)",
    "dollars": 676.09,
    "markets": 1132,
    "lost": 36,
    "put_in": 54446.76,
    "pct_of_put_in": 1.24,
    "pct_of_pot": 115.68
   }
  ],
  "pot_note": "Money is Kalshi's own settlement records for the main account, filtered to pin's markets: the 12 fifteen-minute coins plus hourly BTC. They were read live at ~8:52 AM ET (GET only). The cache was not rewritten. A day is the ET day of each market's close. The pot is approximate. It is the main account's cash at the start of each window, rebuilt backwards from $1,044.96 now by taking out settled money for pin, the race and the old bot, adding back the transfers to the subaccounts, and taking out deposits:\n- Today: ~$1,025.15.\n- Yesterday: ~$1,091.47. The $50 + $28 moved to the subaccounts at 1:46 AM ET 09-30 is added back.\n- Since v-topup: $1,043.93, the bot's own bank reading at its restart.\n- Last 7 days: ~$1,023.84.\n- 7 days before: $599.04 at the start plus the $370.44 deposit on 09-19 = $969.48. Against $599 alone it would read 13.3%.\n- All time: the $584.46 of net deposits.\nPositions open at a window's start are ignored, which is off by at most one quarter-hour's bets. Pin shares this cash with the coin race, so the pot is not pin's alone.",
  "biggest_win": "Biggest win in the last 7 days and all time: BTC 10:45 PM ET 09-25, +$22.13 (141 NO contracts). Yesterday's best was BTC 2:30 AM ET, +$8.81. Today's best is BNB 2:15 AM ET, +$7.56: the last-10-second boost took that bet from 87 to 130 contracts.",
  "biggest_loss": "Biggest loss in the last 7 days and all time: BTC 12:00 AM ET 09-27, -$131.98. That was two full bets on the same coin in the same second; insurance had already cut it from about -$194. Yesterday's loss is the \"$40\" he saw: XRP 7:15 PM ET, -$42.60. At 7:14:40 PM, with 20 s left, sellers were dumping XRP and someone offered it at 75c. The dump guard refused that offer, but in the same second the bot bought 89 YES starting at the 88c offer, paid up to 98c and averaged 94.8c. Four seconds later its confidence fell to 39 in 100 and insurance bought 89 NO at 51c. XRP settled NO. The bet lost $84.65 and the insurance won back $42.05, so insurance halved it.",
  "thoughts": [
   "Income halved because the bot trades half as many coins, not because each trade got worse. Coins bought per day: 50 (09-20..26) vs 25 (09-28..30). Per coin it is the same: about $55 put in and $1.62-1.77 per win (~3c per $1). Wins per day $87 -> $39, losses per day $35 -> $17. The median day fell from $54 to $23.",
   "Where the missing coins went (bot's own logs): the 45-second buy fell from ~33 coins a day to ~11. The 30-second buy barely moved (20 -> 18).",
   "The biggest piece, about 11 coins a day, is a side effect of the 09-28 10:36 AM ET change (v-reopen98). That change reopened 97.9-98c buys for the 30-second bet only. The 45-second bet stayed capped at 97.8c. When a coin sits at 97.9-98c during the 45-second window, the cap refuses it about 3 times in 0.15 s. Those refusals use up the coin's 3 tries, so it is locked out for the rest of the quarter-hour, including the 30-second window where 98c is allowed. Counted: 33 coins in 2.9 days. All 33 ended on the side we wanted, but that is the market's result, not our loss rate. At 98c one loss wipes out about 50 wins. Our real 98c buys since 09-28: 28 coins, 0 losses, +$27.33 (about $1 each). So this lockout is worth $0 to $11 a day, probably nearer the low end.",
   "Other pieces of the drop:\n- The seller gate (since 09-27) skips about 7 coins a day.\n- One-full-bet skips about $9 a day of second bets (22 of 23 skipped would have won, +$42.65, and 1 lost, -$5.27, over 4 days).\n- About 20% fewer usable offers than the 09-22..26 median. This is measured in bot checks, not coins.",
   "His '$30 vs $40' question is the seller-gate read; my answer is yes, keep it. In 4 days it refused 34 coins, and 2 of those settled against us. The bigger one, BTC 1:30 PM ET 09-29, counts as $29.20 saved, but that is a floor: it only prices the small 45-second bet. The gate's refusals also locked BTC out of the 30-second full bet, so the real save is about $43 (if insurance had fired) to $85 (if it hadn't). The '$40' is a ceiling ($39.66). $21.80 of it was coins the bot bought anyway at a smaller size. Only $17.86 was coins never bought, and even that is priced on market results, which flatter us. So: saved $29-85 vs cost at most ~$18-40. It rests on one save, so it is thin evidence.",
   "The seller gate could not have stopped yesterday's XRP loss. The XRP offer had been sitting for 14 minutes, and the gate only fires on offers under half a second old. With 20 s left it was also inside the window where the gate is off. A rule like 'don't buy right after a dump' (IDEA_LEDGER F19) is a wash on live fills: 10 such buys since 09-21. 8 won (+$75), 2 lost (-$75). One of the two was an insurance false alarm on a winning bet. Net +$0.01.",
   "Insurance lately pays: since 09-27, 3 real alarms saved +$129.78 (BTC 09-27 +$64.35, BNB 09-28 +$21.82, XRP 09-30 +$43.61) and 1 false alarm cost -$44.88 (ETH 09-27). Lifetime it is now about break-even (it was -$55 on 09-27).",
   "Bet size: 88 contracts = main-account cash / 11.76 at ~$1,044. $116 net has moved from the main account to the ladder and forecaster pots since 09-28. That makes pin's bets about 10 contracts (~11%) smaller than they would be. The coin race's open bets also come out of the same cash.",
   "Today so far: 10 coins, 10 won, +$19.76 (3.7 cents per $1 put in). That is a normal day at this volume. The Kalshi app's -$108.28 compares the main account now with the whole account (all three pots) at midnight. Against its own midnight level the main account is up about $19.81 (pin +$19.76, race +$0.05)."
  ],
  "risks": [
   "Thin margin. A win pays ~$1.65. An insured loss costs ~$43 (about 25 wins). An uninsured one costs ~$85 (about 50 wins), up to ~$130 with the 1.5x last-10-second boost. At ~25 coins a day, one insured loss erases about two days of income. Live loss record: 5 losing coins in 227 over 7 days (about 2 in 100). Break-even at 98c is about 2 in 100.",
   "Known bug confirmed today: Kalshi's Thursday maintenance delayed the 3:00 AM ET BTC payout. The bot read the missing $84.62 as a withdrawal (3:15 AM ET) and the payout as an $87 deposit (5:00 AM ET). Its bet shrank to 80 for about 1 3/4 hours, and its 20% drawdown mark was reset twice. The same misreading during a real loss would hide that loss from the drawdown halt. Kalshi's transfer list shows no transfer since 09-30.",
   "Same-second double orders still happen (23 pairs 150-900 ms apart since 09-27). Since v-topup the 15-minute ones stay within one bet, plus the planned half-bet late add. The hourly BTC markets still end up holding 2 contracts instead of 1 (6 times since 09-28). That is pennies, but it is the same mechanism behind the 09-23 and 09-27 $130 losses.",
   "Fixing the lockout would add about 11 coins a day at 97.9-98c, where one loss eats about 50 wins. It adds volume, not safety.",
   "This live run ends about 10-03 8:12 AM ET (--minutes 4320). watch_bot.ps1 should restart it with the same settings; check that it did."
  ],
  "suggestions": [
   {
    "what": "Stop the 45-second price cap from locking coins out of the 30-second bet. Build a narrow flag so early-price refusals (early_dear, early_cheap) no longer use up the coin's 3 tries, while seller-gate refusals still do. Run it as a paper arm against arm-live-twin for 2-3 days, then go live with a VERSIONS entry. Do not use the existing --attempts-on-send flag: it would also release the seller-gate lockouts.",
    "evidence": "Since 09-28 10:36 AM ET, 33 coins were refused at 97.9-98c by the 45-second cap and then locked out ('market_attempts') before the 30-second window opened. None was ever bought, and all 33 settled on our side (market results, an upper bound). The early_dear gate count went from 0 a day before 09-28 to 14-17 a day. Lockouts went from 5-7 a day to 13-17 a day. pinrun.py adds the try at line 18938, above the early gates at line 19026 and the seller gate at 19110. Live 98c buys since 09-28: 28 coins, 0 losses, +$27.33. Value: $0-11 a day.",
    "needs_operator": false
   },
   {
    "what": "Keep the seller gate (--toxic-fresh) on, and answer his question that way. Re-count at 10-08.",
    "evidence": "research/sweep/toxic_read.py read 10-01: 34 refused coins, 2 settled against us. BTC 1:30 PM ET 09-29 counts at least $29.20 saved, really about $43-85, because the gate also kept BTC out of the full 30-second bet. Wins skipped: at most $17.86 on coins never bought ($39.66 including coins bought anyway). Of the 14 lockouts the seller gate caused, 13 settled our side and 1 against us, and that one was this save.",
    "needs_operator": false
   },
   {
    "what": "Keep one-full-bet. It costs about $9 a day.",
    "evidence": "onefull_read (10-01): 23 refused second bets, 22 would have won (+$42.65), 1 lost (-$5.27) = ~$37 in 4 days. Before it, two same-second double bets lost $130.41 (BTC 09-23) and $131.98 (BTC 09-27) within 5 days. With one bet per coin the worst single coin is ~$85 uninsured, not ~$170.",
    "needs_operator": false
   },
   {
    "what": "Don't add a 'no buy right after a dump' rule yet. Instead, measure the narrower version from the live logs: after a dump, buy only what is offered at the first price and don't pay up through the book.",
    "evidence": "research/sweep/dump_then_buy.py: 10 dump-then-buy coins since 09-21, net +$0.01 (8 won +$75, 2 lost). In yesterday's XRP buy only 11 contracts were at 88c; the other 78 were bought on the way up to 98c. With only the first-price 11 the loss would have been roughly $5-10, not $42.60.",
    "needs_operator": false
   },
   {
    "what": "Fix the bot's bank-move reader so it checks Kalshi's transfer list before calling a cash change a deposit or withdrawal. Today it called a delayed payout a withdrawal.",
    "evidence": "pinrun-live-20260930T121206Z.jsonl: 'external' withdrawal -84.62 at 07:15:21Z and deposit +87.00 at 09:00:22Z, both while the BTC 3:00 AM ET position (87 contracts, cost $84.45) waited out maintenance. The bet went 87 -> 80 -> 88 and the high-water mark moved 980.80 -> 1067.80. GET /portfolio/subaccounts/transfers shows no transfer since 09-30. This is CURRENT_STATE open item 5 (classify_bank_move).",
    "needs_operator": false
   },
   {
    "what": "Cap hourly BTC at 1 contract per market even when two orders go out in the same second.",
    "evidence": "KXBTCD held 2 contracts on 6 markets since 09-28 (two 'full' orders 148-357 ms apart, 1 contract each, e.g. KXBTCD-26OCT0108-T83899.99 at 7:59 AM ET today) while --series-size is 1. Money at stake is tiny, but it shows that double sends still get past the size cap on the hourly path.",
    "needs_operator": false
   }
  ]
 },
 {
  "bot": "Coin race (research/pinracearm.py --live, main account; pid 1431208, relaunched Oct 1 3:42 AM ET by the keep-alive; size v-race40 = 40 contracts a bet, $120 open cap, stops for the ET day after 2 losing races)",
  "table": [
   {
    "window": "Today (Oct 1 ET, to 8:54 AM ET)",
    "dollars": 0.05,
    "markets": 1,
    "lost": 0,
    "put_in": 0.95,
    "pct_of_put_in": 4.9
   },
   {
    "window": "Since v-race40 (40 a bet, Sep 30 8:25 AM ET)",
    "dollars": -1.1,
    "markets": 2,
    "lost": 1,
    "put_in": 2.08,
    "pct_of_put_in": -52.6
   },
   {
    "window": "Since v-race20 (20 a bet, Sep 27 10:50 PM ET)",
    "dollars": 9.32,
    "markets": 14,
    "lost": 1,
    "put_in": 186.84,
    "pct_of_put_in": 5
   },
   {
    "window": "Since v-race5 (Sep 24 11:16 AM ET)",
    "dollars": 17.51,
    "markets": 68,
    "lost": 1,
    "put_in": 448.48,
    "pct_of_put_in": 3.9
   },
   {
    "window": "Since v-race30 (Sep 22 3:03 AM ET)",
    "dollars": 19.62,
    "markets": 176,
    "lost": 3,
    "put_in": 552.17,
    "pct_of_put_in": 3.55
   },
   {
    "window": "All time (first settled Sep 6)",
    "dollars": 18.47,
    "markets": 207,
    "lost": 9,
    "put_in": 578.25,
    "pct_of_put_in": 3.19
   }
  ],
  "pot_note": "The coin race shares the main account with the pin bot, so a share of that pot means nothing for this bot. The % column is money made divided by money staked (what the contracts cost). Numbers are Kalshi's own settlements for subaccount 0, KXCRYPTOLEAD rows (botstats cache, refreshed this run). I checked two by hand. The Sep 29 BTC win: 20 contracts at 85c = $17.00, paid $20, fee $0.18, so +$2.82. The Sep 30 loss: 1.26 contracts at 90c = $1.13 plus a $0.01 fee, so -$1.14. \"Since v-race30: 3 lost\" is 3 bets in 2 races: the Sep 23 tie, which lost 2 bets about half their cost (-$0.95 together), and the Sep 30 loss. The 9 lost all time also include 4 bets from Sep 6-7 and Sep 15 under $0.02 each, and 2 one-contract losses on Sep 21 (-$0.86 and -$0.87).",
  "biggest_win": "+$2.82: BTC race closing 8:15 AM ET on Sep 29. Bought 20 YES, saw them offered at 90c and got them at 85c, 10 seconds before close. BTC won.",
  "biggest_loss": "-$1.14: BTC race closing 9:00 PM ET on Sep 30, the bot's only real loss since Sep 22. It bought YES at 90c 28 seconds before close. It asked for 40 because 40 were showing, but only 1.26 filled. BTC did not win. That tiny fill was luck: the full 40 would have cost about $36. The 2-losses-a-day stop worked as written. It logged loss 1 of 2 for Sep 30, kept trading, and the count reset at midnight ET.",
  "thoughts": [
   "A small, steady earner. Since Sep 24 it made +$17.51 over about 7 days, roughly $2.50 a day, on $448 staked: about 4 cents back per dollar staked. It won 66 of 68 bets. Its one real loss was -$1.14 (Sep 30); the Sep 23 tie cost $0.95 and falls just before this window.",
   "Going to 40 a bet has added nothing yet. In 24 hours it sent 3 orders and got 2 of 94 contracts it asked for (2 in 100). At 20 a bet it got 46 in 100. The bigger the order, the less of it fills: 91 in 100 at 5, 58 at 10, 46 at 20, 2 at 40 (only 3 orders, so not settled). The bot only asks for what it sees offered, but that offer is mostly gone by the time its order arrives (it waits 5 seconds to confirm, then re-checks the price). The extra +$1-2 a day expected at 40 has not shown up: it is -$1.10 since the change.",
   "There were also fewer chances: 3 races with an order in the last day, against about 7 a day at 20 a bet (Sep 28-30). Nearly all refusals were 'not close enough to the finish yet' or 'price under 90c', so this is the market being quiet, not the size.",
   "On the $30-vs-$40 question, as it applies to this bot: at 40 a bet, a win pays $0.75 (bought at 98c) to $3.75 (at 90c). One full losing bet costs $36-39, about 2 weeks of this bot's recent profit. So far 40 a bet has doubled what one loss costs, without adding any wins.",
   "The thinnest bets are at 97-98c. Since Sep 22 that price range was 138 of 176 bets and earned +$6.80 on $388 staked (under 2 cents per dollar). At 98c the bot must lose fewer than 2 bets in 100 just to break even. Its live record there is 1 tie race (2 bets) in 138, already near that line. One 40-contract loss at 98c (-$39) would wipe out almost 6 times what that whole price range has ever earned. The 90-93c range is healthier: 21 bets, 1 lost, +$9.65 on $100.",
   "The pre-set check on the size step is due Oct 2 8:00 AM ET (READS_DUE race40). Its rule: go back to 20 if the daily stop fires on 2 of the first 3 days, or if it is below $0 after 30+ bets. At 2-3 filled bets a day, 30 bets is 10+ days away, so that money test cannot decide anything on Oct 2. As of now: below $0 (-$1.10) after 2 bets, and the daily stop has not fired.",
   "Unexplained outage today: the live race wrote nothing from 3:01 to 3:42 AM ET, so it missed the 3:15 and 3:30 AM races. The keep-alive checks at 3:10, 3:20, 3:30 and 3:40 all said 'all up'. At 3:42 AM all three race processes were gone and the keep-alive restarted them. A paper race process logged a dropped connection to Kalshi's live feed. Nothing was open, so no money was affected.",
   "Checked: the collector and the crypto feeds recorder are both running. Disk has 43.5 GB free."
  ],
  "risks": [
   "The 2-losses-a-day stop is kept only in the running program's memory (pinracearm.py lines 283 and 1117-1131); nothing reads today's earlier losses back at startup. Since Sep 30 the keep-alive restarts the live race whenever it is missing (boot_all.ps1 line 483), and it did so today at 3:42 AM ET. A crash or restart after a loss, or after the daily stop has fired, starts the count from zero, so the bot could lose 2 more races that same day.",
   "One race can lose several bets at once. All bets in a race depend on which single coin wins, and the rules allow up to 5 bets and $120 open in one race; 52 of 123 live races since Sep 22 had 2 or more bets. The stop counts losing races, not losing bets. At 40 a bet, the rules allow about $240 lost in a day (2 races at $120); a plain day with 2 losing bets is about $75. Paper example only (not our record, and the live rules would not have bought it): the bot's paper side lost all 3 bets in the 8:45 AM ET race today (81-87c).",
   "The keep-alive only checks that the process exists, not that it is working. It reported the race as 'all up' four times during today's 41 minutes of silence. A frozen live bot looks healthy.",
   "Bets at 97-98c: a win is about $0.75 and a loss about $39 at 40 a bet, so the bot needs fewer than 2 losses in 100 to break even. The live record (1 tie race in 138 bets) cannot yet tell 1 loss in 100 apart from 3 in 100.",
   "The phone/desktop numbers (botstats text_summary('race')) show this bot's rules wrong: 'Version: v-race20', 'stops after its first loss' and 'Keep-alive: none'. In fact it runs v-race40, --live-max-losses 2, and is in boot_all.ps1. The operator can be misled about what limits are live. The money numbers are right."
  ],
  "suggestions": [
   {
    "what": "Go back to 20 contracts a bet, keeping the $120 cap and the 2-losses-a-day stop, or keep 40 only for bets priced 96c or less. Revert line: VERSIONS v-race20 argv (--max-contracts 20 --max-stake 60).",
    "evidence": "At 40 it filled 2 of 94 contracts in 3 orders (2 in 100) vs 46 in 100 at 20. It is -$1.10 since the change, with no extra money. The Sep 30 9 PM ET loss would have cost about $36 with a full 40 fill instead of $1.14. At 20 a bet a full loss costs about $19 and the record since Sep 28 is +$9.32.",
    "needs_operator": true
   },
   {
    "what": "Stop buying 97-98c at 40 a bet: either cap the live price at 96c, or buy 97-98c at 20 or fewer.",
    "evidence": "Live, Kalshi-settled, since Sep 22. 97-98c: 138 bets, +$6.80 on $388 (+1.75%), 1 tie race (2 bets lost about half). 94-96c: 17 bets, 0 lost, +$3.16 (+5.0%). 90-93c: 21 bets, 1 lost, +$9.65 (+9.6%). Break-even at 98c is under 2 losses per 100 bets; one 40-contract loss there costs $39, almost 6 times that range's total earnings.",
    "needs_operator": true
   },
   {
    "what": "Make the daily loss stop survive a restart. At startup, read today's (ET) live_loss and live_halt records from results/pinracepenny-live.jsonl back into day_losses, loss_day, halted and halted_day. Add a self-test: a restart after 2 losses on the same day stays halted. This needs a live restart and a VERSIONS entry.",
    "evidence": "The state is in memory only (pinracearm.py LIVE dict line 283; the counter at lines 1117-1131; nothing at startup reads it back). Since v-race40 the keep-alive restarts the live race (boot_all.ps1 line 483), and it did today at 3:42 AM ET.",
    "needs_operator": false
   },
   {
    "what": "Add a 'still working' check for the live race to the keep-alive: if pinracepenny-live.jsonl has not been written for 20 minutes, say so loudly (alert, not an automatic kill).",
    "evidence": "Today the log went silent 3:01-3:42 AM ET (07:01:15Z-07:42:05Z) and missed 2 races. boot_all.log says 'all up; nothing to do' at 3:10, 3:20, 3:30 and 3:40 AM ET. pinracearm4-live.err shows a dropped connection to Kalshi's live feed.",
    "needs_operator": false
   },
   {
    "what": "Fix botstats' race display: show the version from the combined 'v-race40 + ...' heading, read --live-max-losses into the settings line, and report the boot_all.ps1 keep-alive.",
    "evidence": "text_summary('race') printed 'Version: v-race20', 'stops after its first loss' and 'Keep-alive: none'. The live argv (pid 1431208) has --live-max-losses 2, and VERSIONS line 12 plus boot_all.ps1 line 483 show v-race40 is live and kept alive. botstats.py line 92 still says 'nothing restarts the live one'; version_of at line 784 drops a heading that also names the forecaster.",
    "needs_operator": false
   },
   {
    "what": "At the Oct 2 8:00 AM ET read (READS_DUE race40), report plainly that its money rule ('below $0 after 30+ bets') cannot be judged yet at 2-3 filled bets a day, and put the 20-vs-40 choice to the operator on the fill evidence. Do not quietly change the pre-set rule. Also fix the stale READS_DUE coinrace-relaunch entry, which still names v-race20 pid 3739628 and 'nothing restarts it'.",
    "evidence": "3 orders and 2.26 contracts filled in the first 24 hours at 40. READS_DUE coinrace-relaunch has status open, due Oct 4 10:50 PM ET, and describes a process that no longer exists.",
    "needs_operator": false
   }
  ]
 },
 {
  "bot": "forecaster (clean-room forecaster, subaccount 2, 1/10 of paper size since Tue 9/30 8:26 AM ET; running, pid 4453188, healthy at 8:53 AM ET today)",
  "table": [
   {
    "window": "Today, Wed 10/01 ET (so far)",
    "dollars": 2.91,
    "markets": 2,
    "lost": 0,
    "put_in": 8.93,
    "pct_of_put_in": 32.6,
    "pct_of_pot": 4.8
   },
   {
    "window": "Yesterday, Tue 9/30 ET",
    "dollars": 6.63,
    "markets": 16,
    "lost": 2,
    "put_in": 83.29,
    "pct_of_put_in": 7.96,
    "pct_of_pot": 12.2
   },
   {
    "window": "Since size went to 1/10 (Tue 9/30 8:26 AM ET)",
    "dollars": 7.14,
    "markets": 12,
    "lost": 1,
    "put_in": 75.91,
    "pct_of_put_in": 9.41,
    "pct_of_pot": 12.6
   },
   {
    "window": "1/20 size phase (Mon 9/28 8:54 PM - Tue 9/30 8:26 AM ET)",
    "dollars": 5.7,
    "markets": 23,
    "lost": 3,
    "put_in": 60.46,
    "pct_of_put_in": 9.43
   },
   {
    "window": "Since going live (Mon 9/28 8:54 PM ET)",
    "dollars": 12.84,
    "markets": 35,
    "lost": 4,
    "put_in": 136.37,
    "pct_of_put_in": 9.42,
    "pct_of_pot": 25.2
   }
  ],
  "biggest_win": "XRP, market closing 7:15 PM ET Tue 9/30: 10 NO at 67c (it asked 77c and got filled 10c cheaper), +$3.15.",
  "biggest_loss": "SOL, market closing 10:45 AM ET Tue 9/30, -$5.42 (the both-sides loss). At 10:44:32 AM it bought 10 YES at 77c. 14 seconds later the model changed its mind and bought 10 NO at 75c. Holding both sides cost $15.16 for a $10 payout, so the loss was locked in either way. The second buy was the right call: keeping only the YES would have lost $7.78, so the flip saved $2.37. The mistake was the first bet. Its paper copy made the same two buys (-$5.74 at live size).",
  "pot_note": "The forecaster has its own pot (subaccount 2), and the Kalshi app's main-account number does not include it. Net $50.98 came in by transfers from main: $10 + $15 on the evening of 9/28 ET, $2.02 sent back at 12:19 AM ET 9/29, then $28 at 1:46 AM ET 9/30. Cash now is $63.82 with nothing open, so it is up $12.84. Kalshi's 35 settled markets in that pot add up to the same $12.84 to the cent (fees of $1.80 included), so the number checks out. How pct_of_pot is measured: today against the $60.91 in the pot at midnight ET; yesterday against $54.28 (the start-of-day cash plus the $28 added at 1:46 AM); since the size step against the $56.68 the bot's own start record shows; since live against the $50.98 net transferred in. By day (ET, by when each market closed): 9/28 +$1.76, 9/29 +$1.54, 9/30 +$6.63, 10/01 +$2.91.",
  "thoughts": [
   "It is making money: +$12.84 in about 2.5 days on $50.98 put in, which is +25% on its pot. Every $1 bet has returned about 9.4c profit, the same before and after the size doubled. It won 31 of 35 markets. It pays about 79c a contract on average, so if prices were exactly right it should win about 27 of 34 one-sided bets; it won 31. Pure luck would do that about 4 times in 100. That is encouraging but not proof: the 35 markets fall in only 28 quarter-hours, and the coins tend to move together.",
   "The $40 loss you saw yesterday was not this bot. Its worst market ever is -$5.42.",
   "Its paper copy is no guide to its money. The paper version of this exact bot, scaled to live size over the same days, is DOWN $15.59 while live is UP $12.84. The whole $28 gap comes from bets on offers that were collapsing. Paper books those at the old price and takes the full loss. Live either skipped them (the crash guard) or got filled 26-43c cheaper. So the '15% return' that got it switched on is not borne out even by its own paper copy. The live profit comes from its ordinary bets: 30 markets, +$15.89, 1 loss (the SOL both-sides).",
   "The crash guard (skips a buy when the best offer is already more than 10c under the price it's about to pay) is earning its keep. Since 8:26 AM ET 9/30 it skipped 5 bets: 4 would have lost and 1 would have won (+$1.69 to +$2.75). The 4 losses add up to $27.45 if it had paid the price it asked for. If it had been filled 30-40c cheaper, as collapsing offers were before the guard, they would have come to roughly $14-17. Either way that beats the bot's whole profit since the step (+$7.14). Before the guard, the same kind of bet happened 5 times at half today's size: 3 lost, -$3.05 in all. Tomorrow's 8 AM ET crash-guard check passes on these numbers: KEEP.",
   "Against its own pre-set target for the 10/06 check: 35 of the 60 markets it needs; return +9.4% (target at least 5%); it got 89% of the contracts it asked for (target at least 60%); 1 both-sides loss, which is the most the target allows. A second one fails it. Size went to 1/10 on 9/30 on your order, before this check was met.",
   "Small leak: when two buy signals land in the same second, the second is dropped and usually never made up. Since the size step that skipped about $2.13 of winning size (8 HYPE contracts at 6:29 AM ET today, 9 NEAR contracts at 3:44 PM ET 9/30). That is about $1 a day."
  ],
  "risks": [
   "It will lock itself out soon. The bot refuses to start if its pot holds more than $70.05, a start limit that grew with the size step. The pot is at $63.82 and gaining about $5-7 a day, so it should pass $70 in about a day. After that, any restart leaves the bot off: a PC reboot, a crash, or its scheduled 7-day end at 8:26 AM ET Wed 10/07. The keep-alive retries every 10 minutes and gets refused every time, and nothing alerts. Code: research/cleanroom/forecaster_live.py line 709 (MAX_SUB_BALANCE = $35 x 2 at 1/10 size).",
   "Thin sample at a bigger size. One lost market at 10 contracts costs $7-9, about a day's profit. Its limits allow up to 40 contracts and $44 out at once in one quarter-hour. The daily stop is -$24. The whole-run stop of -$40 starts over at every restart, so it never builds up across restarts.",
   "The crash guard rests on 5 skips. A collapse that doesn't yet show in the best offer when it decides still gets through. Two buys went through exactly at the 10c edge (XRP 7:14 PM ET and BTC 3:29 PM ET on 9/30); both won, which was luck at the edge.",
   "The model can swing hard in the last 30 seconds. On DOGE at 12:29 AM ET today its odds went 31% -> 20% -> 30% -> 16% -> 47% -> 100% within 30 seconds. Swings like that cause both-side buys like the SOL one. One more both-side loss fails its 10/06 target.",
   "The phone/desktop stats still describe it as '1/20 of paper size' (research/botstats.py, SPEC['forecaster']['what']). It is 1/10 now.",
   "Machine: the price recorder and exchange feeds are both alive. Free disk is 43.5 GB, down from 54 GB on 9/29 (about 5 GB a day). At that pace the 6 GB stop line is about 7 days out, around 10/08."
  ],
  "suggestions": [
   {
    "what": "Before the forecaster's pot passes $70, either move its profit back to main (for example $63.82 down to about $56, by a subaccount 2 -> 0 transfer) or raise its start limit (for example to $100). Otherwise its next restart leaves it switched off with no alert.",
    "evidence": "Cash $63.82 against a $70.05 start limit (forecaster_live.py line 709). It made +$7.14 in its first day at 1/10 size. A forced restart is already scheduled: --minutes 10080 ends at 8:26 AM ET Wed 10/07, and boot_all.ps1 relaunches it every 10 minutes.",
    "needs_operator": true
   },
   {
    "what": "Keep the crash guard at 10c and do not tighten it. Mark the 10/02 8 AM ET crash-guard read KEEP.",
    "evidence": "It skipped 5 bets: 4 losers ($14-27 avoided at live size) and 1 winner (+$1.69 to +$2.75). Since the step, buys where the best offer was 4-5c under the asked price: 3 won and 1 lost (the SOL both-sides). The biggest win (XRP +$3.15) sat exactly at the 10c edge, so a tighter guard would have skipped it.",
    "needs_operator": false
   },
   {
    "what": "Hold at 1/10 size until the 10/06 read. Do not step up on 35 markets.",
    "evidence": "Pre-set target: 60 markets, return at least 5%, fills at least 60%, at most 1 both-sides loss. Now: 35 markets, +9.4%, 89%, and 1 both-sides loss already used. Pure luck would produce results this good about 4 times in 100.",
    "needs_operator": false
   },
   {
    "what": "Have skipped ('refused') records log the best offer at the moment of the decision, as placed orders already do. Then the crash guard's savings can be measured exactly instead of given as a $14-27 range.",
    "evidence": "The 5 why=crash records in results/forecaster-live-orders.jsonl have no best_ask field. Placed records do (best_ask_at_trigger).",
    "needs_operator": false
   },
   {
    "what": "Fix the dropped-second-order leak. After an order comes back, re-offer the skipped amount only if the same price is still showing (the paper's own 1-second rule), within the existing limits. This is a live code change and needs a VERSIONS.md entry.",
    "evidence": "17 'in_flight' skips. Since the size step, about $2.13 of size that would have won was never re-sent (HYPE 8 contracts at 6:29 AM ET today, NEAR 9 contracts at 3:44 PM ET 9/30). That is about $1 a day.",
    "needs_operator": false
   },
   {
    "what": "Update the forecaster label in research/botstats.py from '1/20 of paper size' to '1/10 of paper size'.",
    "evidence": "SPEC['forecaster']['what'] still says 1/20. The running process has --scale 0.10, and its start record at 12:26Z 9/30 shows scale 0.1 and 10 per side.",
    "needs_operator": false
   }
  ]
 },
 {
  "bot": "ladder (subaccount 1, research/cleanroom/ladder_live.py, pid 4454364 running, 5 contracts a bid since Sep 30 8:26 AM ET)",
  "table": [
   {
    "window": "Today (Oct 1, since 12 AM ET)",
    "dollars": 1.21,
    "markets": 9,
    "lost": 0,
    "put_in": 58.79,
    "pct_of_put_in": 2.06,
    "pct_of_pot": 1.86
   },
   {
    "window": "Since 5 a bid (Sep 30 8:26 AM ET)",
    "dollars": 3.06,
    "markets": 21,
    "lost": 0,
    "put_in": 146.95,
    "pct_of_put_in": 2.08,
    "pct_of_pot": 4.7
   },
   {
    "window": "Since going live (Sep 28 12:01 PM ET)",
    "dollars": 3.39,
    "markets": 32,
    "lost": 0,
    "put_in": 163.07,
    "pct_of_put_in": 2.08,
    "pct_of_pot": 5.21
   }
  ],
  "pot_note": "He put in $65 by transfer ($15 on Sep 28, $50 on Sep 30). Cash now is $68.39 with nothing open, so it is up $3.39. That matches Kalshi's own settlement total ($3.3872) to the cent. The 'pct_of_pot' column is dollars divided by the $65 he put in. It made no fills for the first 25 hours (the v-ladder-penny version, fixed by v-ladder-top Sep 29). The first fill was Sep 29 at 1:00 PM ET, so the $3.39 came in about 2 days of actual trading.",
  "biggest_win": "NEAR 3:45 PM ET Sep 30: 20 contracts bought at 97.9c, won +$0.42. To win that it had $19.58 at stake. Close second: NEAR 7:45 AM ET Oct 1, 20 contracts, +$0.41.",
  "biggest_loss": "None. It has never lost: 32 markets, 32 wins, 166 contracts. Its smallest win was +$0.01 (DOGE Sep 29, a 0.46-contract partial fill).",
  "thoughts": [
   "The math: every win pays about 2c a contract and every loss costs about 98c. One loss at 5 contracts (-$4.90) wipes out 49 wins of $0.10. It has to win 98 of every 100 markets just to break even. Every win returns about 2% of what was bet, fixed by the price. A loss is -100% of that bet.",
   "Is it worth it? Not proven either way yet. 32 wins in a row is weak proof. A bot that loses exactly 2 times in 100 (break-even) still goes 32 for 32 about half the time (52 in 100). One that loses 4 in 100, which is about -$3 a day at this size, still does it about 1 time in 4. To be confident it beats break-even (19 times in 20) takes about 150 markets with no loss. At about 21 markets a day that is roughly a week more.",
   "Closest real-money comparison (our own fills, not paper): pin's own buys at 97.5c and up were 597 markets, and the side it bought lost 5 times (3 outright, 2 where pin's hedge caught it). That is about 1 in 120, inside break-even. If the ladder lost at that rate, about 60% of its winnings would survive: about $1.75 a day instead of the $3 a day it shows now. The ladder probably does worse than pin. It only fills when someone chooses to sell to it in the last 30 seconds, and it has none of pin's guards against sellers dumping. It also has no hedge.",
   "Its biggest bets came from someone selling hard. Both 20-contract markets filled 4 times in 2 to 4 seconds. That is the pattern pin's dump guard treats as a warning. Both won; 2 cases prove nothing either way.",
   "It does not spread risk; it doubles up on pin. In 8 of its 32 markets pin was betting the same way, and those 8 made 40% of its profit ($1.34 of $3.39). Both 20-contract bets were NEAR markets where pin held $87 and $128 on the same side. Had either NEAR market gone the other way, the account would have lost about $106 or $148 across both pots.",
   "Pace at 5 a bid: +$3.06 over 24.5 hours (21 markets, about $3 a day), almost all in small coins: NEAR 9, ZEC 8, XRP 5, SOL 4, BNB 3, DOGE 2, HYPE 1, no BTC or ETH.",
   "Books check out. Kalshi says +$3.39 and the bot's own log says +$2.38. The $1.01 gap is two things. On Sep 29 the bot booked a NEAR market as a loss before it had settled; it actually won +$0.02 (already fixed that day, v-ladder-settlefix). And Kalshi filled 0.46 of a DOGE contract that the bot never saw (new bug, below).",
   "Verdict: fine to keep running at 5 a bid as a test while it is small: about $3 a day up, about $49 down in the worst realistic quarter-hour. Not worth sizing up until about 150 markets are in. The bot was running at 12:54 PM UTC (8:54 AM ET), both recorders were alive, and 43.5 GB of disk was free."
  ],
  "risks": [
   "One bad quarter-hour can cost about $49: its cap is 50 contracts at 98c. It is regularly near that cap. Since going to 5 a bid it refused a bid for being full 16 times, and each refusal means 46 or more contracts were already on the table. The -$30 daily stop only counts losses after they settle, so it cannot stop that first hit. $49 is 72% of the pot and about 16 days of its profit.",
   "One market alone: 20 contracts has happened twice, and losing one would cost $19.58, about 6.5 days of profit.",
   "It will stop itself without anyone deciding to. At 5 a bid it refuses to START if its pot holds more than $73. The pot is $68.39 and growing about $3 a day, so it passes $73 around Oct 2-3. After that, any restart fails: a reboot, a crash, or its 7-day run ending Oct 7 at 8:26 AM ET, when keep-alive (boot_all.ps1) tries to relaunch it. Keep-alive would then retry and be refused every 10 minutes.",
   "Same-side bets with pin (8 of 32 markets) mean a bad NEAR or ZEC quarter-hour hits both pots at once.",
   "Partial fills are rounded down to whole contracts in the bot's own records (0.46 became 0 on DOGE Sep 29). Its 50-contract cap and its -$30 daily stop see less than Kalshi does. Small today: under 1 contract per order.",
   "Its current pass/fail rule (stop if the daily stop fires twice) would not catch a slow bleed. Losing 3 in 100 markets is about -$3 a day at this size and never trips a -$30 day."
  ],
  "suggestions": [
   {
    "what": "Cap each market at 10 contracts (2 bids of 5). The worst single-market loss falls from $19.58 to $9.80.",
    "evidence": "Two NEAR markets took 20 contracts each, 4 fills in 2-4 seconds. With a 10 cap they would have made about $0.41 less, 12% of the $3.39 total.",
    "needs_operator": true
   },
   {
    "what": "Lower the quarter-hour cap from 50 to 25 contracts. The worst bad quarter-hour falls from about $49 (72% of the pot) to about $24.50.",
    "evidence": "The 50 cap refused a bid 16 times since Sep 30 8:26 AM ET, so 46 or more contracts were at stake each time. The -$30 daily stop only acts after settlement.",
    "needs_operator": true
   },
   {
    "what": "Before the pot passes $73 (about Oct 2-3), either move profit above $65 back to the main account, or raise the start limit MAX_SUB_BALANCE in ladder_live.py. Otherwise the next restart is refused and the ladder quietly stops, at the latest Oct 7 8:26 AM ET when its 7-day run ends.",
    "evidence": "ladder_live.py main(): refuses to start if the sub balance is above 25 + 12*(size-1) = $73 at size 5. Cash is $68.39 and rising about $3 a day. boot_all.ps1 relaunches it with --minutes 10080 (started Sep 30 12:26Z).",
    "needs_operator": true
   },
   {
    "what": "Keep fractions of a contract in the fill tracking: drop int() around float(fill_count_fp) in poll_fills_once (~line 277) and in the place response (~line 239) of research/cleanroom/ladder_live.py.",
    "evidence": "Kalshi settled 0.46 contracts of KXDOGE15M-26SEP291515-15 in subaccount 1. The bot's log has no fill or settle for it. The cap and the daily stop undercount by up to 1 contract per order.",
    "needs_operator": false
   },
   {
    "what": "Write a pass/fail bar into READS_DUE 'ladder-live' now, before the number is seen. At 150 settled markets: 0-1 losses = keep (only then discuss size); 4 or more = stop. No size increase before then.",
    "evidence": "Break-even is 98 wins in 100. 32 for 32 happens about half the time even at break-even. The current rule (daily stop fires twice) never trips on a 3-in-100 slow bleed (about -$3 a day).",
    "needs_operator": false
   }
  ]
 }
]
```
