# C_decide — the decision file for the operator

2026-09-23. This is the end of the "there has got to be something we have not
found yet" hunt. Five investigators went looking in five different places
(the coin price feed, the Kalshi order book, the exchange order books, all the
coins at once, and other betting venues). They came back with 22 ideas. A sixth
person then rebuilt every number from scratch and tested each idea on days
nobody had looked at yet.

Everything below comes from Kalshi's own settlement records and the bot's own
logs. Nothing here comes from the backtest.

**The short version: we looked hard in five places and found no new way to pick
better bets. The thing that separates a winner from a loser before we buy is
still not visible in any data we hold. What we did find is that the money in
front of us is in size and in staying switched on — and that one of those is
much safer than it looks.**

---

## First, your live question: yes, one loss flips a day

You asked what would have happened if that one we lost had filled.

Our whole record, day by day (Kalshi's own numbers, every crypto pin market):
a good day makes **$50 to $110**. A single bad market costs **$30 to $108**.
So yes — one more bad market turns almost any green day red.

Concretely: 09-22 made **+$53.70**. Add one loss the size of Sunday's NEAR
loss (**-$59.09**) and the day is **-$5.39**. Do the same to 09-23 so far
(+$15.13) and it is **-$43.96**. Five of our sixteen days are already in that
state.

**This is not new damage and it is not a sign something broke.** It is the
shape of the bet: we win about **$1 per market, 97 times out of 100**, and
lose **$30 to $100** the other 3. It has always looked like this. Your
nervousness is correctly aimed — it just is not aimed at a new problem.

Full day table is in `B_holdout.md` section 25.

---

## SIZE UP — the numbers, in plain terms

You asked what sizing up does. The honest answer is better than a spreadsheet
says, for a reason nobody had checked before.

**Fact 1: we already get almost everything we ask for.** 38,059 contracts of
the 40,123 we asked for — **94.9%**. 88.7% of markets fill completely. Our
execution is not the problem.

**Fact 2, and this is the one that matters: in 437 of our 774 markets (56.5%)
the offer ran out before our size did.** In those markets there was nothing
left to buy. **Raising size does nothing at all there.**

**Fact 3: the four biggest losses we have ever taken are ALL in that half**
(-$107.95, -$66.34, -$64.95, -$59.09). A bigger size could not have made any
of them worse, because there was no more contract to buy.

So size only reaches the other 337 markets — and those are our *better* ones.
Scaling just them:

| | total made | worst single close | most money at risk in one close |
|---|---|---|---|
| **today** | **+$546.89** | **-$108.86** | **$313** |
| size x1.5 | +$720.43 | -$108.86 | $395 |
| **size x2** | **+$893.96** | **-$123.51** | **$526** |
| size x3 | +$1,241.03 | -$185.26 | $789 |
| *what a spreadsheet would say for x2* | *+$1,093.78* | *-$217.73* | *$626* |

**Double the size and you make about 63% more money for a 13% worse worst
day.** Not double for double. In daily terms: we have averaged about **$49 a
day** over the last ten days (**$79 a day** if you drop 09-19, the day the
hedge bugs cost us). +63% is roughly **+$31 a day**, or **+$50 a day** on the
clean rate.

**Four things that all cut AGAINST that number — none for it:**

1. It assumes there was more to buy above our size in those 337 markets. We do
   not log how deep the offer went, so this is the **best case**. The worst
   case is that size x2 buys **zero** extra contracts.
2. A bigger order eats further down the offer list and pays worse prices. Real,
   not in the table, size unknown.
3. The per-close spending cap is set to exactly **two markets' worth of size**,
   so doubling size doubles that cap automatically. We would hold more markets
   per close than this table counts.
4. **The real danger is one bad close, not one bad market.** On 09-11 at 12:30
   ET, 7 of the 9 coins the model was 99.5%+ sure about all went the wrong way
   in the same 45 seconds. Coins do not fail independently — when the basket
   snaps, it takes every coin at once. At today's size the most we have ever had
   at risk in a single close is $313. At double size that is **$526, and it can
   go at once.** `--loss-abort` cannot save you from it: every leg is already
   bought before the close resolves.

**My read: x1.5 is the honest step, not x2.** It is +$174 on this record with
the worst close unchanged at -$108.86, and it lets us find out whether the
extra contracts are actually there before we bet $526 on one minute.

---

## 1. What survived, what it is worth, and the exact next step

### A. Log the order book on every decision — do this first, it changes nothing

**Worth: $0 today. It is the only way anything else in this file ever becomes
provable.**

The bot already computes how long the price level it is about to buy has been
sitting there, and it already sees the sizes on both sides — and it throws all
of it away. We had to rebuild it from the recorded tape, where **a quarter of
the rows arrived after we had already traded** (median 2 seconds late). That
is why half of this hunt is uncertain.

Fix: write four more fields into each decision record (`imb`, `our_sz`,
`opp_sz`, `spread_c`, beside the `level_age_ms` already there), in both the
"we bought" and the "we refused" records.

Blocks nothing. Gates nothing. Cannot touch a hedge. **Do it before the disk
runs out — we have about 3.7 days of recording left** (20.6 GB free at
07:45Z, burning 4.0 GB/day, hard stop at 6 GB).

### B. "Fresh price level" — the only thing that pointed at all three new losses

**Worth: nothing as a blocking rule. Do NOT ship it as one.**

When the price we buy has only just appeared (under a tenth of a second old,
and we watched it appear), the market is worse: **all three of the losses on
the fresh test days were in that bucket** (ages 75, 57 and 38 thousandths of a
second), and it is the only negative bucket in either half of our record.

**But blocking it loses money.** Take out 09-19 — the day the hedge bugs cost
us, since fixed — and blocking that bucket would have **cost $206.51**. Take
out the single -$107.95 market and the bucket goes positive. The whole dollar
case is one broken day.

Next step: **log it (item A), change nothing, and look again after about ten
more losing markets** — roughly a month at our loss rate. Not a paper arm; a
paper arm cannot settle this any faster than reality can.

The second half of that rule — book imbalance — is **dead**. It showed nothing
on the fresh days (the half it says to avoid actually made +$3.66) and a
quarter of its evidence arrived after we had traded.

### C. Coins per close, not dollars per close

**Worth: unpriced, but it is the one idea with a plausible mechanism and no
downside.**

Closes where we held 2 or 3 coins made **more per contract** than closes where
we held 1 (1.03c → 1.57c → 2.68c per contract), and it repeats on the fresh
days. The 2nd and 3rd bet inside a close are taken later and cheaper, which is
exactly where our edge is strongest.

But: `--max-positions 3` **has never once fired in 128 runs**. The thing that
actually turns coins away is the per-close dollar cap, and it did so **478
times**. So the lever is the dollar cap, not the position count.

Next step: a paper arm that holds **more coins for the same total dollars**
(cap 3 markets' worth, size cut to keep the dollar total flat) — not more
money. Bar written down before reading it: **cents per contract at least as
good as live, AND the most money at risk in one close no higher than live,
over 150 closes.** Blocks nothing, cannot touch a hedge.

Caution: this and the correlated-close danger point in opposite directions.
More coins at smaller size is the *safer* version of the same dollars, which is
why it is worth testing — but it is still the same basket.

### D. Show "dollars at risk in this close" as a live number

It does not exist today. The tail we actually fear (item 4 under SIZE UP) acts
on exactly that number, and nothing downstream can catch it. **Do this before
any size increase**, not after.

---

## 2. What is DEAD — do not spend another night on any of these

Each of these was a real idea, was measured, and failed. Named so nobody
re-opens it.

| The idea | Where it came from | Why it is dead |
|---|---|---|
| Make the model honest about rare big moves | coin price feed | The measurement is right — a move it prices at 1-in-a-billion happens about 1 in 325. But the fix **stops the bot trading**: it refuses 645 of 697 markets, and **all 91** of the fresh-day markets. It would also not have refused any of our three worst losses. |
| Stand down when the market is calm | coin price feed | Backwards on money. The calmest fifth **made +$78.11** and was the **best** third on the fresh days. |
| Cool off for a minute after a big jump | coin price feed | Jumps do not cluster (1.16x at best, nothing at the extreme) and 6-sigma prints appear in 17% of all minutes — a cooldown would block a sixth of everything for no gain. |
| Refuse bets that sit too close to the strike | coin price feed | Every version loses money ($46 to $171). On the fresh days the **losers' cushions were BIGGER** than the winners'. The three worst losses ever had the three biggest cushions. |
| "The middle of the window is where money dies" | coin price feed | Refuted on the fresh days — the band it accused has zero losers there. |
| Ladder depth, spread, volume, thin books, a big offer appearing | Kalshi book | Nine separate ideas, all null, several **backwards** from the intuition. |
| Build the volatility ruler from the exchanges instead of the index | exchange books | **Actively harmful** — it would have made the bot MORE confident on the markets it lost. |
| A jump alarm from the exchanges | exchange books | No earlier than the index one (median difference: zero seconds). Adds 28 false alarms on winners to catch 2 losers a few seconds sooner. |
| Exchange book depth as a warning | exchange books | Looked dramatic (58x), then the other venue said the **opposite**, and the number turns out to measure flicker, not thinness. |
| Cross-venue disagreement as a warning sign | exchange books | 101 separate cuts tried. Best one is 72x away from the bar. |
| Use Crypto.com's price as a second opinion | other venues | Its price is **worse informed than Kalshi's at every horizon**; the best weight to put on it is zero. |
| Crypto.com lead / Crypto.com arbitrage | other venues | No lead (0.017 correlation with Kalshi's next move). The arbitrage costs a median **$1.14** to win $1. |
| Crypto.com as a second place to run the pin | other venues | Its book is **withdrawn about a minute before expiry** — exactly our window. Dead venue for this. |
| Polymarket.us / Chainlink | other venues | The arithmetic is right and the conclusion is **backwards**: their settlement locks in 5-15x earlier, so the near-certain side is near-certain for minutes and is already priced at 99.9c. There is nothing left to buy. Our edge exists *because* Kalshi's settlement locks in late. |
| On-chain / blockchain data | other venues | Wrong clock. Blocks are 10 minutes (BTC) and 12 seconds (ETH); funding and basis move over hours. Our bet is half-settled by the time we enter. |

**One thing that survived but cannot be used:** when a fill comes back 2 cents
or more cheaper than the price we were quoted, it loses far more often (2 of
the 3 fresh-day losers). It is the single strongest result in the whole hunt
— and it is only knowable **after** we have already bought. It can never stop
a bet. At best it could make us hedge sooner. Its cause also turned out to be
sweep depth, not somebody picking us off.

**And a danger, written down before it bites:** there is a switch called
`--hedge-normal` that is OFF today. If anyone ever turns it on *at the same
time* as making the model less confident, **every hedge silently stops firing**.
That is precisely the 09-19 failure that cost us $223 in a day.

---

## 3. The one thing we do not record that is worth recording

**Exchange liquidation prints** (Binance `!forceOrder@arr`, Bybit
`allLiquidation`). Nothing else on the list is close.

**Why it could help, specifically.** Settlement is the average of 60 one-second
prints of a crypto index. We buy when the price already sits far enough on our
side that the remaining seconds "cannot" carry it back. What kills us is the
rare case where they do — and we now know something real about those moments:
**our own entry seconds are genuinely more dangerous than random seconds.** A
6-sigma surprise happens about 1 in 116 of the seconds where someone chose to
sell us a 96c contract, against 1 in 325 at a random second — **3.7 times
fatter**. Somebody knows something at that moment and no data we own says what.

A forced liquidation is the one public event that is (a) on our clock —
seconds, not minutes, (b) **self-continuing** — a cascade forces more selling,
which is the only mechanism that carries a move *through* the remaining
settlement seconds rather than reverting, and (c) not already inside the
index ruler we use. Our existing jump guard only reacts to a move that has
already happened. A liquidation print is evidence the move is not done.

It is a hypothesis. It is the best one left.

**What it costs.** A read-only WebSocket subscriber in the same shape as
`crypto_feeds.py`, writing one gzip per hour. Liquidations print only when
they happen, so it is a small fraction of a book feed; our entire constituent
feed folder is **0.33 GB a day against a 4.0 GB a day total burn** (Kalshi's
own book data is 3.66 of that). Disk cost is not the issue.

**But it cannot start yet.** We are **about 3.7 days from the hard collection stop**
(20.6 GB free, 6 GB is where recording *stops altogether*). Nothing new gets
recorded until the SSD is in.

**The bar that settles it in a week, written down first.** Two tests, neither
of which needs us to lose money to answer:

1. **On the index alone:** in the week's data, take every settlement that
   missed by more than 4 sigma. At least **twice as many** of them must carry a
   liquidation print in the 60 seconds before, compared with matched random
   seconds. There are a few hundred such misses a week, so this is answerable.
2. **On our own entries:** a liquidation print in the 30 seconds before our
   entry must appear at least **twice as often** at our entry seconds as at
   random seconds in the same markets (about 350 of our fills a week).

**If neither clears 2x, drop it permanently and write it in this file.** If
both clear, it still only earns a size reduction, never a hedge block.

*Cheap companion, different reason:* we have **no exchange feed at all** for
BNB, HYPE, ZEC and NEAR — **41% of our fills and half our loss dollars**,
including NEAR, our only net-losing coin (-$46.64 over 62 markets). Meanwhile
we record ADA, LTC and BCH, which we have **never traded once**. Swapping them
buys no money by itself; it makes our worst coins measurable at all. Also
blocked by the disk.

---

## 4. The honest bottom line

**Is there an unfound edge in the data we hold? On this evidence, no — not one
we can see with the amount of losing we have done.**

Five people, 22 ideas, about 295 separate cuts of the data. To believe any one
of them you would need it to clear a bar of about 1 in 6,000, because of how
many things were tried. **Not one thing you can check before buying clears it.**
The only test that does clear is one you cannot run until after you have
already bought.

And here is the real limit, which is not about cleverness: **we have only lost
26 markets, ever.** On the fresh days we lost 3. With 3 losses you cannot tell
a good filter from a lucky one — a rule would have to flag a third of our bets
and be **three times** more likely to be wrong on them before it would even
show up. Most of the ideas above are "not found", not "proven absent". We are
statistically blind at this scale, and the only cure is time.

**So: the edge we have — buy the near-certain side inside the last 30 seconds —
is real, and it is thin and capacity-bound.** We already get 94.9% of what we
ask for, and **in 56.5% of markets the offer simply ran out**. That is the
ceiling, and it is a ceiling on *supply*, not on our skill. The money comes
from **size, uptime, and how many coins we can reach per close** — not from a
new signal.

Two things follow, and they are uncomfortable together:

- **Size is where the money is, and the tape says it is safer than it looks**
  (+63% for +13% worse worst-close, because the biggest losses are all in the
  half size cannot reach).
- **Size is also where the only real danger is**, because coins fail together.
  The most we have ever had at risk in one close is $313; at double size that
  is $526 and it can go in one minute, and nothing we have stops it.

That is the whole decision. It is a sizing and capacity question now, not a
search question.

---

## What I need from you

- **Size: x1.5 or x2?** x1.5 makes about +$16 a day more with the worst close
  unchanged at -$108.86. x2 makes about +$31 a day more and takes the worst
  close to -$123.51 and the most-at-risk-in-one-close from $313 to $526. I
  recommend x1.5 first, because we do not log how deep the offer went and the
  x2 figure is a best case.
- **Do you want the four extra logged fields shipped now** (blocks nothing,
  touches no decision, under 4 days of disk left) — yes or no?
- **The SSD: when?** Every new recording idea in this file is blocked until it
  is in, and recording *stops completely* at 6 GB free, which is under 4 days away.
- **Do you want the "more coins, same dollars" paper arm started?** It risks no
  money and reads in about 150 closes (roughly four days).
