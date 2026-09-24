# OPEN_WORK.md — everything in flight, in plain language

**How to use this: say to any new chat — "Read OPEN_WORK.md and tell me where
everything stands." Or name one topic, e.g. "bring up the fresh offer test".**

Written 2026-09-24. Every item says what it is, where it stands, what decides
it, and when. Money numbers are Kalshi's books. Keep this file updated the
moment a state changes; it is the operator's index to the work.

---

## A. Running tests — nothing here changes the bot until its bar is met

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
- **Status:** paper arm since 2026-09-24 07:58Z. 4 signals, 3 settled, all won.
- **Open decision:** switch from paper to a 1-contract REAL test for accurate
  fill data (needs a per-series size cap so hourly bets can never touch the
  main strategy's budget, plus the operator's go-ahead — real money).
- **Decides:** bar in `results/IDEAS_2026-09-24.md` item 2 — 7 days, ≥ 30 fired
  closes, 0 paper losses inside 30 s, ≥ 660 captured contracts.

### A3. 2-cent edge floor — `arm-edge2c`
**Say: "the edge floor test."**
Only buy when the model beats the market by at least 2 cents after fees.
Trades under 2 cents were 314 of our markets, 9 of the 19 remaining losses,
and made +$15 total — break-even trades. The floor halves the loss dollars for
about the same money but cuts 40% of trades, and it was mixed by week
(+$39 one week, −$34 the other). Paper only.

### A4. Control arms — `arm-lateadd-off`, `arm-afternoon`, `arm-live-frozen`
**Say: "the control arms."**
Copies of the bot with one thing changed, so we can prove a change helped.
- `arm-lateadd-off` = today's live bot WITHOUT the late add (which is live).
- `arm-afternoon` = the exact code from the afternoon of 2026-09-23, before
  the night's changes. **Manual process — relaunch by hand after a reboot.**
- `arm-live-frozen` = the settings from 2026-09-20, pinned.

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
for an append-only recording). The machine has ~18 GB free and records ~4 GB a
day; the recorder stops itself at 5 GB free, around 2026-09-28. Once the drive
is plugged in I move the recording and the deadline goes away for ~1.5 years.

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

- **Selling-pressure feed — NOT being built.** In the 3 seconds before our
  order, other traders were net selling our side on 68 of 100 losers vs 33 of
  100 winners (6.5 losses per 100 vs 1.5). It is the same population as A1,
  and A1 uses data we already record while this needs a new live data feed.
  One test, not two. Evidence: `results/cf_2026-09-24/toxicity.md`.
- **Market making (resting our own offers) — parked.** A simulation says
  $160–550/day, but it is a replay (our standing rule: replays are not
  evidence), and testing it needs 2+ GB of memory the money bot cannot spare.
  Right place: the cloud server. `results/IDEAS_2026-09-24.md` item 3.
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
