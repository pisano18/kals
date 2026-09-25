# Who else trades the 15-minute crypto markets -- 2026-09-25

Script: `research/competitors.py` (self-test passes; `--fills-only` re-runs just
our fills in ~5 min, the full week takes ~13 min). Source: the recorder's trade
tape, 2026-09-18 03:00 ET to 2026-09-25 03:00 ET, 12 coin series only. Our money
comes from Kalshi's ledger (`kalshi_ledger.json`). Nothing here comes from the replay.

## The answers, short

1. **Eight kinds of trader, four of them recognisable.** Only two kinds of
   taker made money this week: people buying the likely winner in the last minute
   (our lane) and people buying it in the last 10 seconds. Everyone else lost,
   mostly the taker fee. The four recognisable repeat actors are: a "lottery
   bot" that buys the losing side at 0.1c, retail orders sized in dollars,
   index-watching bots in our lane, and the people who post the offers we buy.
2. **On the other side of our fills is almost always one or two resting offers
   posted a split second earlier.** This looks the same on losers and winners.
   What differs is the traffic in the 3 seconds before we buy. When more than
   half of the buying in those 3 seconds was on the OTHER side, we lost 7 times
   out of 137. When it was not, we lost 1 time out of 218.
3. **No new warning sign that the current gates miss.** The one sign that separates
   winners from losers is the same "people are selling our side" signal as
   PREREG_toxic. It is already running as the paper arm `arm-toxic`, and its bar
   is read ~10-01. This is the same eight losers, not new evidence. The new
   part is that the recorder's tape shows it independently for 09-18 to 09-23,
   before the bot logged it. Everything else I tested failed.
4. **Nobody new is safe to trade against.** The steady losers (the lottery bot and
   retail dollar orders) can only be taken from by resting our own offers, and
   both ways of doing that are already dead (IDEA_LEDGER D16, D17). We already
   profit from the slow group: people who rest offers on the favourite in the
   last minute lose 0.3-1.2c per contract to takers like us.

## 1. The styles (all takers, the whole week)

Every print of one taker order has the same millisecond, so prints were grouped
into 12.95 million taker orders (26.55 million prints). "Fast" = the order
landed in the first 150 ms after the settlement index's once-a-second print.
Random timing puts 15 of 100 there.

| style | orders | fast, per 100 | result for them, per contract |
|---|---|---|---|
| mid-price (15-85c), more than 60 s left | 6,946,777 | 15 | **lose ~2.0c** |
| favourite (>=85c), more than 60 s left | 2,114,101 | 16 | lose ~0.2c |
| longshot (<=15c), more than 60 s left | 2,111,537 | 16 | lose ~0.7c |
| under 1 contract | 929,200 | 15 | lose ~1.0c |
| longshot, last 60 s | 373,454 | 16 | lose ~0.4c |
| **favourite, 10-60 s left (our lane)** | 282,682 | **22** | **make ~0.5c** |
| mid-price, last 60 s | 184,908 | 17 | **lose ~2.6c** |
| **favourite, last 10 s** | 11,389 | **24** | **make ~0.9c** |

The two lanes that make money are also the only two with extra "fast" orders.
About 1 in 4 buyers there fire right after the index print, so bots watching
the index are our direct competition. Among last-minute buyers, 100-lot orders
are the fastest (30 of 100 right after the print). Buyers of 100, 50 and 20 lots
lost 0.1-0.6c a contract this week, while 1-10 lot buyers made 0.1-0.8c.

**Recognisable repeat actors:**

- **The "916" lottery bot.** Its orders come in exact multiples of about 916
  contracts: 915.99, 1831.90, 4579.77, 458.04 and 91.62. It shows up in nearly
  every close, typically 12-29 s before the close, and buys the losing side at
  0.1c. About 27,000 orders this week (16,142 of them the 915.99 size),
  winning 0-2 times out of 100. It lost about $35,000 on the week. Buyers of the
  other side with odd fractional sizes like these were in the 3 s before our
  buy in 83 of every 100 markets we traded, winners and losers alike, so their
  presence tells us nothing.
- **Retail orders sized in dollars.** Odd small sizes (1.01, 1.02, 1.50, 1.70,
  2.01, 3.40, 3.65 ...) appear in about 590 closes each. They trade 15-85c with
  5-10 minutes left and lose 1.5-3c a contract. These are many people, not one bot.
- **Whole-number sizes (11, 13, 17 ...)** are everybody. They are not a fingerprint.
- **Resting sellers of the favourite in the last minute** (the offers WE buy).
  These are 50, 11, 10, 2, 3, 5, 6, 30, 42 and 200-lot offers. They lose
  0.02-1.2c a contract to whoever takes them. Two exceptions: resting 100-lots
  (typical price 99.6c), where buyers lost 0.65c a contract over 5,019 hits,
  and 17-lots at ~93c. **UNCHECKED:** I did not group these by close, so a few
  bad markets could explain them. Treat it as a question, not a finding.

## 2. Our own fills against the tape

388 markets with an entry fill in the window. 355 matched a tape print on our
side within 2.5 s of our send (353 to the exact contract count; the print lands
a median 76 ms after we send). The other 33 fall in the tape gaps and include
2 losers, among them **the week's biggest single loss: BTC 09-23 20:29 ET,
-$130.41. The tape does not have it.**

Matched: **8 losers (-$493.03), 347 winners (+$659.26)**, per market, from the ledger.

| what was there (per market) | markets with it | lost | without it | lost |
|---|---|---|---|---|
| **more than half of the buying in the 3 s before us was on the other side** | 137 (118 closes) | **7 (5 per 100), net -$160.12** | 218 | **1 (0.5 per 100), net +$326.35** |
| 25+ contracts bought against us at our price level (not 0.1c tickets) | 286 | 7 (2.4 per 100) | 69 | 1 (1.4 per 100) |
| we took a single resting offer | 150 | 4 (2.7 per 100) | 205 | 4 (2.0 per 100) |
| a "fast" seller in the 3 s before | 211 | 5 (2.4 per 100) | 144 | 3 (2.1 per 100) |
| a mid-price seller in the 3 s before | 46 | 2 (4.3 per 100) | 309 | 6 (1.9 per 100) |
| another buyer on our side right after us | 354 | 8 | 1 | 0 |

All 8 losers' offers were fresh, posted 35-256 ms before we hit them (from the
bot's own signal records). That fits PREREG_toxic's "fresh AND selling" cell.
**Honest limits:** 8 losers is small. 6 of them are on ET 09-19, the day hedges
were blocked by bugs since fixed. They overlap PREREG_toxic's 12 early
losers, so this confirms that finding with a second data source; it is not new evidence.

The losers (ET):

| when (ET) | market | our side, price, s left | $ | resting offers hit | bought against us in the 3 s before |
|---|---|---|---|---|---|
| 09-19 01:44 | BNB | yes 75c, 24 s | -57.76 | 2 (38.52, 37.48) | 481, at ~7c |
| 09-19 01:59 | BTC | no 94c, 35 s | -66.34 | 1 (70) | 38,383, one order of 10,694 at 8c |
| 09-19 12:29 | BNB | yes 97c, 23 s | -61.75 | 30 tiny ones | 751, at ~0.8c |
| 09-19 15:59 | BTC | no 98c, 45 s | -107.95 | 1 (110) | 11,583, at 2c |
| 09-19 23:44 | XRP | no 98c, 41 s | -64.95 | 4 | 1,069, at 1-1.5c |
| 09-19 23:44 | HYPE | no 94c, 33 s | -43.92 | 1 (104) | 193, at 3-8c |
| 09-21 12:44 | NEAR | yes 91c, 44 s | -59.09 | 2 (72, 9) | 311, at 13-16c |
| 09-21 18:14 | HYPE | yes 98c, 43 s | -31.27 | 1 (55) | 169, at 2-4c |

## 3. Across the whole market (not our loss rate)

For each market, I took the first moment with 10-45 s left when someone paid
90c or more for one side. If someone bought 25+ contracts of the other side in
the 5 s before, the favourite lost **2.0 times per 100** (42 of 2,080 markets,
537 closes). Otherwise it lost **0.8 per 100** (6 of 773, 411 closes). That
is 2.5 times more often, but it flags 73 of every 100 markets, so it is useless
as a rule. It is not adjusted for the favourite's price either. This is what the
market did. It is **not** how often we lose (CLAUDE.md, 2026-09-10 amendment 5).

## Data limits

- 15 of 168 trade hours are missing (including 09-21 21:00 to 09-22 00:59 ET
  and 09-22 20:00-21:59 ET), 7 more are thin, and 1 file has a torn end. 5,590
  orders had no known outcome and are left out of the money columns.
- Close counts per size are approximate. They are counted as "the close
  changed" and overcount near the quarter hour, so the last-minute longshot row
  shows 1,167 "closes" in a week of about 612. Ranking is unaffected.
- A size's profile starts at its 5th close (memory). A size seen fewer than 2
  times in 6 h or 3 times in 24 h was dropped, so a very sparse actor can be missed.
- Posted-and-cancelled offers (the orderbook channel, ~170 MB an hour) were NOT
  read. Anyone who posts and pulls without trading is invisible here.

## What is left

1. The sell-share signal across the whole market, with the favourite's
   price held fixed: thousands of markets instead of our 355. Best next step for
   spotting losers earlier.
2. Group the "resting 100-lot at ~99.6c" losses by close before believing them.
3. Fingerprint the fresh offers from the orderbook channel, one close at a time around our fills.
