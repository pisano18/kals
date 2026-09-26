# OPEN_WORK.md — everything in flight, in plain language

**How to use this: say to any new chat — "Read OPEN_WORK.md and tell me where
everything stands." Or name one topic, e.g. "bring up the fresh offer test".**

Written 2026-09-24, updated 2026-09-25. Every item says what it is, where it stands, what decides
it, and when. Money numbers are Kalshi's books. Keep this file updated the
moment a state changes; it is the operator's index to the work.

---

## A. Running tests — nothing here changes the bot until its bar is met

### A00. PICK UP WHERE WE LEFT OFF
**Say: "pick up where we left off".** The top of `HANDOFF.md` ("PICK UP HERE",
2026-09-26) has the last instructions and jobs P0-P7.

### A13. The reward test -- APPROVED 2026-09-26; the order tool needs a reward mode first
**Say: "run the reward test".** Kalshi pays daily reward pots to people whose
orders sit in certain quiet markets. Seven ideas from the money sweep depend on
whether Kalshi pays OUR account. Test: 2-4 resting 1-cent buy orders, at most
about $60 at risk, answer in 2-3 days. Pass: paid at least half of what the
rules predict on 2+ markets. Kill: $0 after 3 days. Kept out of the markets the
bot trades. Details: HANDOFF P2, `results/IDEA_SWEEP_2026-09-25.md` row 1.

### A14. Combine the Kalshi cash -- APPROVED 2026-09-26
**Say: "combine the cash".** An automatic 85/15 split parks about $139 where the
crypto bot cannot spend it, while the bot sizes its bets on the full balance
(about 13% too big). The operator said combine it. API-only on Kalshi; HANDOFF P1.

### A15. Polymarket -- wire test PASSED 2026-09-26 3:26 AM ET; next is Step 2
**Say: "Polymarket step 2".** The 1-cent test order was accepted, did not fill,
left nothing open and cost nothing: the key can trade. Then Step 2 (20 windows at 1 contract) per
`results/POLYMARKET_ORDERS.md`. The operator: "do what you want on polymarket".
Paper results due ~09-28 ("read the Polymarket paper results").

### A16. The money sweep results -- 2026-09-25
**Say: "the money sweep".** 119 agents, nothing proven; top lead is the reward
test (A13). `results/IDEA_SWEEP_2026-09-25.md`; every idea is a row in
`results/IDEA_LEDGER.md`. Also: the 60-day money chart
https://claude.ai/artifact/WeWnNH1dKZ2TZ5Z6MBgBh3 ("show the bank outlook").

### A0. The money-idea sweep — many agents hunting for new ways to make money
**Say: "the money sweep" (results) or "run the money sweep" (a new run).**
On 2026-09-25 about 100 agents went through every kind of bet on Kalshi and
Polymarket US (and anything else legal), cross-bred ideas, checked each one
with real data and had a second agent try to disprove it. Result:
`results/IDEA_SWEEP_2026-09-25.md`. Every idea ever checked, dead or alive,
is one line in `results/IDEA_LEDGER.md`, so nothing is re-proposed. How to
run it again: `research/sweep/README.md`.

### A12. Zero-size order fix — `v-zerotake` (live since 2026-09-25 2:25 AM ET)
**Say: "the zero order fix."**
At 2:14 AM ET the bot tried to add to a HYPE position that was already at
its maximum and sent an order for 0 contracts. Kalshi's side refused it
twice and two refused orders stop the bot; the watchdog restarted it in a
minute and nothing was lost (that market won $5.77). Now the bot refuses
the add itself. Nothing else changed.

### A1. "fresh offer" test — `arm-fresh500`
**Say: "the fresh offer test."**
When we buy, we take an offer someone left sitting. If that offer appeared
less than half a second ago — right after the price moved — the person is
reacting to the same news we are, and we lose more often. Of the 7 losses our
new rules do NOT already catch, 6 bought an offer under a quarter-second old;
offers that had been sitting 10+ seconds lost 0 times out of 155.
- Only applies with MORE than 20 seconds left. Inside 20 s the age doesn't matter.
- On the record the money is a wash (−$12 over 11 days), so it is a
  "lose less", not a "make more". Not live.
- **Decides:** 7 days beside the live bot, read ~2026-10-01 with
  `results/cf_2026-09-24/armh2h2.py`. Bar written first in
  `results/PREREG_fresh.md`: turn it on if the live bot's fresh-offer buys are
  net ≤ +$25 and contain ≥ 2 losses; kill it if they are ≥ +$100 with ≤ 1 loss.

### A2. Hourly BTC markets — `arm-btcd`
**Say: "hourly BTC."**
Kalshi runs an hourly BTC market on the same settlement rule as our 15-minute
one. Its order books are about **30× deeper at the price we buy** (median 838
contracts resting vs 28). So the "$14/day" ceiling from the idea hunt was OUR
own per-close spending limit, not the market's supply.
- **Why it matters:** on the 15-minute markets more bank buys nothing past
  ~3× today's size (the book runs out). On the hourly ones it buys
  proportionally more. This is the scaling path.
- **Status: LIVE FOR REAL MONEY at 1 contract a market since 2026-09-24
  16:48Z** (`v-btcd1`, flags `--series KXBTCD --series-size 1` in
  restart_bot.ps1). The same gates, the same hedge, the same rails as the
  15-minute markets — only the size differs, and it cannot be widened (the cap
  is re-applied after every sizing step). At most 2 contracts per hourly
  market, 24 closes a day: under $50/day at risk. The paper arm `arm-btcd`
  keeps running beside it as the comparison.
- **First 10 hours live: ZERO orders sent** (70 refusals: nothing offered 33,
  stale book 26, not confident enough 6, too expensive 5).
- **Decides:** ~30 fired closes (about a week). Watching: do we actually get
  filled, and at what price. If fills are real, the next step is a bigger
  per-close allowance for the hourly family — that is the only place more bank
  buys more contracts.

### A10. Far rungs of the hourly BTC ladder at 99c -- KILLED 2026-09-25 (no supply)
**Say: "the far rung idea."**
**KILLED: across 68 hourly closes (Sep 22-24), nobody sold the safe side of
a rung $150+ away at 97c or better in the last 45 seconds -- not once. The
99c offers the live bot saw on Sep 24 were all on the rung right next to the
settlement, the risky one. Code stays in, switched off. Details:
`results/FAR_RUNG_2026-09-25.md`, verdict at the top.** What follows is the
original reasoning, kept so nobody re-proposes it.
With 45 seconds left, a rung $150 or more from where the settlement is
heading has never finished on the wrong side (0 of 2,136 closes since
Sep 1; worst miss $136). Those rungs sit at 99c with hundreds to thousands
of contracts resting, and the live bot's 98c ceiling turned five of them
away on Sep 24. A winner makes 0.93c a contract; a loser costs 99c; it
breaks even if fewer than 0.93 in 100 cross. Bank-limited: about $68-85 a
day at today's bank, and one crossing costs about $225 at that size.
- **Status:** the code is built and OFF (`v-farrung`). Its paper copy
  (`arm-farrung`) was stopped and retired 2026-09-25 when the idea died.
  The 1-contract live test would have needed the operator's yes; its bar is in
  `results/FAR_RUNG_2026-09-25.md` section 0 (100+ fills over 30+ closes,
  zero crossings, 0.8c+ a contract, fills on half of orders).
- **Honest limit:** 24 days of tape with no flash crash in it.
- **Overnight (midnight and 1 AM ET, Sep 25): nobody offered the safe side
  of any far rung at any price.** The 99c offers seen on Sep 24 were all
  1-7 PM ET. (Written before the kill above. The book watcher `rungwatch`
  takes its last daytime reads on Sep 25; stop it after ~7 PM ET Sep 25 by
  creating `results/rungwatch.stop`.)

### A11. Polymarket US -- the same BTC contract, second book (recorder running)
**Say: "Polymarket."**
Since Sep 22 Polymarket US lists our exact BTC 15-minute contract (same
index, same strike to the cent). Its book is a tenth to a fiftieth of
Kalshi's; makers there are paid a rebate. Cross-venue "free money" showed
on a cached feed and vanished on the real one. Realistic $0-15 a day.
**Operator, 2026-09-25: Polymarket US offers him ONLY Bitcoin 15-minute and 1-hour
up/down -- no other coins or time frames. His account is funded (~$60) and he has
placed a bet there, so he is eligible for those contracts.**
A read-only recorder runs 3 days (to ~Sep 28); bar in
`results/SECOND_INCOME_SCAN_2026-09-25.md` section 1.

**Order path BUILT 2026-09-25 (`research/polyorder.py`, `results/POLYMARKET_ORDERS.md`),
nothing sent.** Dry-run by default; a live send needs `--live` plus a one-time code
bound to one market/side/price/size; buys only, takes what is there and cancels the
rest, never above 98c; caps 5 contracts / $5 per order, $10 risked and $5 lost per
day. Next: Step 1 wire test (buy 1 Up at 1c, should not fill, proves the key can
trade) -- waits on the operator's yes. His $60.52 is $50 promo bonus + $10 pending
deposit + $0.52 cash. The paper bot `research/polypaper.py` runs to ~09-28.

### A9. Hourly markets on the other coins -- `arm-hourly-all` (paper, since 2026-09-25 03:06Z)
**Say: "the other hourly coins."**
Kalshi runs the same hourly ladder for ETH, SOL, XRP, DOGE, BNB and HYPE that
it runs for BTC, all settling on an index the bot already follows. A paper
copy of the live bot now trades all seven at 1 contract a rung beside the
live bot (which trades only BTC). Question: do the other coins' hourly books
fill us the way BTC's do, and at what price? Nothing goes live on them
without a sign-off. Code proven not to change the live BTC path
(`v-ladder7` in `results/VERSIONS.md`). Read after ~7 days (2026-10-02).

### A7. "fresh offer while they're selling" — `arm-toxic` (built, running)
**Say: "the toxic offer test."**
The two "someone is selling to us" signals crossed on our own early entries:
- offer resting, nobody selling: 146 markets, 1 loss (+$204)
- offer resting, sellers around: 51 markets, 0 losses (+$109)
- fresh offer, nobody selling: 108 markets, 3 losses (+$126)
- **fresh offer AND sellers dumping our side: 87 markets, 8 losses, −$285**
Eight of our twelve early losses sit in that last cell — 22% of the entries
and the only cell that loses money. Refusing only that cell would have been
+$285 over 11 days (about +$7/day after discounting the 09-19 hedge-bug
losses to what they'd be now), while refusing either signal alone gives up
far more winners. Needs the bot to listen to Kalshi's trade feed (the
recorder already does). **Built and deployed 2026-09-24 22:20Z:** the live
bot now listens to the trade feed and logs the number on every trade (gate
OFF); `arm-toxic` runs with the gate ON. Bar in `results/PREREG_toxic.md`,
7 days from 22:20Z (read ~2026-10-01). Both thresholds were fixed before the
cross. `/bars` on the phone reads it.

### A8. `/bars` on the phone — the one command that reads every test
**Say: "/bars" (or "read the bars").**
Prints each running test against the bar that was written before its data,
the numbers so far, days into the window, and PASS / KILL / EXTEND / TOO EARLY.
Also `python research/bars.py`. Early reads on 2026-09-24 10:20 PM ET: the
fresh-offer arm is $35 behind live on 42 shared markets (it refuses the first
look and re-enters smaller later) with 21 fresh fills all won — too early; the
hourly BTC arm fires rarely (2 closes in 18 h), so its 30-close bar may need
more than 7 days; photo finishes so far: 10 of 10 refused races were won.

### A3. 2-cent edge floor — `arm-edge2c`
**Say: "the edge floor test."**
Only buy when the model beats the market by at least 2 cents after fees.
Trades under 2 cents were 314 of our markets, 9 of the 19 remaining losses,
and made +$15 total — break-even trades. The floor halves the loss dollars for
about the same money but cuts 40% of trades, and it was mixed by week
(+$39 one week, −$34 the other). Paper only.

### A4. Control arms — `arm-lateadd-off`, `arm-early-off`, `arm-afternoon`, `arm-live-frozen`
*(As of 2026-09-25 the paper fleet copying the 15-minute bot is 10 arms: these
four, `arm-fresh500`, `arm-toxic`, `arm-btcd`, `arm-edge2c`, `arm-hourly-all`,
and `arm-brake3` for sizing; plus five coin-race arms (B2, B3) and two
commodity arms. It was 34 — most were retired on 2026-09-24 because their
questions were settled and the money bot shares the machine's memory. Every
pid and end date: top of `HANDOFF.md`.)*
**Say: "the control arms."**
Copies of the bot with one thing changed, so we can prove a change helped.
- `arm-lateadd-off` = today's live bot WITHOUT the late add (which is live).
- `arm-early-off` = today's live bot WITHOUT the 45-second early buy (live
  runs it at a third of size since 2026-09-22).
- `arm-afternoon` = the exact code from the afternoon of 2026-09-23, before
  the night's changes. **Manual process — relaunch by hand after a reboot.**
- `arm-live-frozen` = the settings from 2026-09-20, pinned. Its 3-day run ended
  2026-09-25 06:21Z (+$309 on paper, 1 loss); relaunched for 7 days at 06:30Z.
- `arm-afternoon` ends ~2026-09-27 03:51Z (11:51 PM ET Sep 26).

### A5. Weather markets — `research/wxwatch.py`
**Say: "the weather idea."**
Kalshi's hourly temperature markets settle on an index Kalshi publishes itself.
The prediction is flawless — the settlement matched the index 240 times out of
240, and with a 1°F cushion the index never ended on the wrong side (0 in 3,072
checks). **But nobody sells it to us:** 3 buyable markets in 7½ hours, ~$13/day
ceiling, New York and LA zero all day. Expect nothing; the watcher finishes
around 2026-09-28. Report: `python research/wxwatch.py --report`.

### A6. Earthquake markets — `research/quakewatch.py`
**Say: "the earthquake idea."**
When a big quake is confirmed by the US Geological Survey, the "biggest quake
this week" market is decided but sometimes still trades below 97c. Read-only
watch for 14 days (to ~2026-10-08). Small money at best (~$0–10/day).
Report: `python research/quakewatch.py --report`.

---

## B. Coin race

### B1. Size — now 5 contracts a leg (`v-race5`, 2026-09-24)
**2026-09-26: NOT yet ready to size up.** 18 of 18 races won at 5 contracts (+$3.80); 84 won + 1 tie of 85 since 09-22. Waits on the photo-finish arm and ~100 races at 5 with 0 losses.
**Say: "coin race size."**
Was 1 contract. Record since 2026-09-22: 60 races, 59 won, 1 tie, 0 lost,
+$1.17. Break-even needs 97.7 legs paying per 100; we are at 98.9 — a
1.2-point margin on 95 legs, which cannot yet be told apart from zero. At 5
contracts a bad race costs ~$10 and a real edge shows ~$1.50/day within a week.
**Next size step waits on B2.**

### B2. Photo finishes — `arm-gap075`
**Say: "photo finishes."**
Races where the top two coins finish within 0.75 basis points are **15 of every
100 races we enter, against 7 of 100 overall** — we are twice as exposed to
near-ties as the market is. The arm refuses them. If they turn out to be the
loss class, that filter goes in before any further size increase.

### B3. Earlier entry — `z3` arm
**Say: "earlier race entry."**
Enters more than 30 seconds before the close when one coin leads by a wide
margin. 36 won, 1 tie, 0 lost in 37 races. Its bar now: 250 races with at most
one loss (it already has the one tie).

### B4. Ties — FIXED and live (`v-race-tie1`, 2026-09-24)
**Say: "the tie fix."**
The bot used to score a tie as a win. A real tie on 2026-09-23 cost −$0.95 and
was booked +$0.05, so the "stop after the first loss" safety never fired. Now
the result comes from Kalshi's own books, a tie pays 50c to both coins and
counts as a loss. This is what made the size step safe.

---

## C. Decisions waiting on the operator

### C1. Hard drive — buy one
**Say: "the disk."**
2 TB external hard drive ($105 Toshiba / $119 Seagate — an SSD buys nothing
for an append-only recording). **Not bought yet.** 11.9 GB free at 3:02 AM ET
Sep 25 (it dipped to 5.9-7.9 GB on the evening of Sep 24 before space was
freed). The recorder stops itself for good at 5 GB free. How fast it fills is
not pinned down — notes say anywhere from 1 to 4 GB a day, and other jobs on
the machine move it too — so the stop date could be anywhere from about Sep 27
to early October. Once the drive is plugged in I move the recording and the
deadline goes away for ~1.5 years.

### C2. Cloud server — deferred until after the weekend
**Say: "the VM."**
Kalshi's exchange runs in Amazon's Ohio data centre (proven by address lookup,
not a blog). A rented machine there is ~1 millisecond from the exchange against
~20 from home, and removes home internet, power and laptop risk. Recommended:
Amazon Lightsail Ohio, Windows, 16 GB — $124/month, everything moves as-is in
about a day. Linux is $84/month but 1–2 weeks of rewriting. Full plan:
`results/VM_PLAN_2026-09-24.md`. Operator: revisit after a good weekend.

### C3. Bigger size on the 15-minute markets
**Say: "size up."**
At our fills the book holds a median 325 contracts under our price ceiling
against our size of 78 — so ~3× today's size is genuinely available, needing
roughly a $2,500–3,000 bank (the rule is: the bank must cover the worst close
about 4 times over). Past that the 15-minute books run out; that is why A2
matters.

---

## D. Decided and closed (do not re-open without new data)

- **Selling-pressure feed — REVERSED, now being built (see A7).** I first
  said it was the same population as A1 and not worth a second test. Crossing
  the two on our own entries proved otherwise — see A7. Old evidence:
  `results/cf_2026-09-24/toxicity.md`; the cross: `results/PREREG_toxic.md`.
- **Market making (resting our own offers) — KILLED 2026-09-25.** Simulated
  on 61 hours of recorded books (968 markets): it lost money in every one of
  12 versions on every day, even assuming we are first in line and instant
  (-0.15c a contract at best, -1.60c at a realistic 300 ms, worst day
  -$3,409). Whoever trades against a resting quote here usually knows where
  the index is going. `results/MAKER_SIM_2026-09-24.md` section 9.
- **Exchange-feed "move against us" gate — killed on our own fills
  (2026-09-25).** The recorded exchange books DO explain 70–79% of the next
  index print 0–300 ms early (`results/FEED_LEAD_2026-09-24.md`) — but at our
  651 entries the move in the 200–3,000 ms before the order did not separate
  losers from winners (medians 0 basis points both; p = 0.13–0.8; only 8 losers
  with feed coverage, 49% power). The print-prediction itself is kept as a
  possible latency use later; no gate.
- **Second-income scan 2026-09-25** (`results/SECOND_INCOME_SCAN_2026-09-25.md`):
  crypto one-touch monthlies $2-10/day needs data; ladder both-sides
  arbitrage 0 of 1,496 polls; sports final minute unmeasured (score feed
  blocked here); S&P/Nasdaq close, Crypto.com, ForecastEx, Robinhood,
  PrizePicks, Sporttrade, air quality, box office, app rankings, Google
  Trends: killed with reasons. The Polymarket "no short-dated crypto" kill
  is REVERSED (see A11).
- **32 other ideas killed with reasons** — including hedging with a crypto
  futures position, Polymarket US, daily high/low temperature markets, selling
  the winning side into the queue, selling lottery tickets, new coins, buying
  in the last 5 seconds. All listed with one-line reasons in
  `results/IDEAS_2026-09-24.md` section 3, so nobody re-proposes them.
- **Drawdown halt — live.** If the bank falls 20% below its high mark the bot
  now stops and WAITS. It no longer restarts into the same halt every 15
  minutes. Pressing START on the app resets the mark and resumes.
- **Phone commands — live.** `/stats` (lifetime, 7 days, 3 days, today, and
  since the newest version: money, win rate, break-even win rate and the margin
  between them, losses, hedges, fees, entry timing, bank and halt headroom),
  `/race`, `/racestats`, plus everything that existed before.

---

## E. The one-line health check

Live bot `research/pinrun.py --live`; recorders `kalshi_collector.py` and
`crypto_feeds.py`; app `research/pindesk.py`; phone `research/pinphone.py`;
coin race `research/pinracearm.py --live`. Money: `python research/pinday.py`.
Versions and how to undo any change: `results/VERSIONS.md`. The running story:
top of `HANDOFF.md`.
