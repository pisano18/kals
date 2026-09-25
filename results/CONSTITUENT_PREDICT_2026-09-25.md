# Can a smarter guess of the last few prints stop our losers? -- 2026-09-25

**Status: COMPLETE. Answer: no.** Script: `research/constpredict.py`
(self-test passes: it finds a planted lead, a planted bounce, and nothing in
two empty worlds). Read-only; nothing under `kalshi_data`, `feed_data` or the
live bot was touched. Sources: the raw index feed and our own exchange-book
replica for the forecast test; our live logs joined to Kalshi's ledger for the
money. No replay, no tape loss rate.

## The answer, in plain words

The bot guesses the rest of the settlement window by assuming the price stays
where the newest print is. We tried three smarter guesses:

1. **The coin's own last few seconds** (is it drifting, is it bouncing back):
   no better than the bot's guess. On the second half of the month, every coin,
   every time-left, the error moved by -10% to +3%, none of it beyond chance.
2. **The exchange order books, read at the same second as the bot's price:**
   also no better (-2.7% to +0.4% pooled, -7.5% to +2.2% per coin, nothing beyond chance).
3. **The exchange books read one second newer than the bot's price:** this one
   works on paper -- it cuts the forecast error about **17 in 100 with 10
   seconds left and 13 in 100 with 20 left** (strong enough to clear the
   76-comparison bar), but only 2-3 in 100 with 30-45 left (not real). It works
   for a boring reason: those books are just an early copy of the next index
   print, which reaches the bot 0.2 s later on a typical second.

**On our real trades it would not have saved money.** 861 of our markets from
09-08 04:00 ET to 09-25 03:00 ET could be rebuilt exactly (26 lost $764.91,
835 won $1,434.11). Using only what the bot could actually have known at
each moment:

- Own-seconds guess: would have refused **4 of 26 losers ($82 saved) and 58
  winners ($111 given up), net -$29**. Random nudges of the same size refuse 4
  losers too (58 times out of 100 you'd do this well by pure luck).
- Books guess, as a live bot could have used it: **2 of 12 losers ($40 saved)
  and 58 winners ($97 given up), net -$57** -- luck level again (57 times out
  of 100). To count as real it would have needed about 5 of the 12 losers.

The "one second newer" guess looks spectacular on the losers -- it would have
refused **9 of 12 ($231 saved)**. **That is peeking, not prediction.** On all
9 of those losers the bot's newest print was only 0.11-0.93 s old when it
bought, so the "next second" books did not exist yet; they came 0.1-0.9 s
AFTER the decision. The bot's newest print was more than a second old on only
70 of 479 trades (about 14 in 100) -- the only moments that guess is honestly
available -- and none of those 70 lost.

**What this does tell us, as a fact rather than a fix:** on 9 of the 12
losers we can check, the move that beat us was already showing in the exchange
books **within one second after we bought**. The losses start right after entry, not
before it. That matches FEED_LEAD_2026-09-24 ("the losses happened AFTER we
entered") and points at who sells to us, not at our forecast.

**Do not build a new projection into the bot.** Not measured here, and the
only open thread: whether hedging off the exchange books would get a loser's
hedge out ~0.2 s sooner (the books run ahead of the print by that much). That
is a hedge-timing question on the ~26 losers, not a forecast question.

## How it was measured

- **Closes:** every quarter hour 08-24 20:00 ET .. 09-25 03:00 ET. 2,742 of
  about 2,757 closes per coin have Kalshi's own close average; our 60-print
  mean matches it to 0.01 bps on 2,735 of 2,735 (every coin). Fitted on the
  first half of the days (to 09-09 20:00 ET), scored on the second half (~1,390
  closes per coin). DOGE's books are thinner in the replica (880-950 test
  closes for the book models).
- **Error** = Kalshi's settlement minus the forecast, in basis points (bps) of
  price. For BTC near $84,000, 1 bps = $8.40: the bot's own forecast misses by
  about $14 typical (rms) with 45 prints left, $1.50 with 10 left.
- **Models**, all straight-line fits with no constant (so "no information"
  lands exactly on the bot's guess): M1 own last 1/3/10/30 s moves; M2 = M1 +
  replica weighted mid, median mid, Coinbase mid (all minus spot) and the
  replica's 3 s move, at the spot second; M3 = M2 + the replica one second
  later; ML = M3 only when the bot's newest print was already >= 1.01 s old at
  the signal (logged `index_age_s`), else M2.
- **Live check:** first filled entry per market (960 filled orders, 907
  markets, 880 rebuilt; dropped: 24 no tape for that close, 3 other). The fair
  value rebuilt from the tape matched the logged one within 0.2c on 861 of 880
  (98 in 100); only those are counted, and all 861 pass their run's own
  confidence and edge floors as rebuilt. Each trade was scored with a model fit
  on the OTHER half of the days, so every trade is out of sample. Refused =
  new confidence below the run's `pin` or edge below its `edge_floor`. Money =
  Kalshi ledger per market (hedged losses included).
- **Luck control:** the model's own nudges dealt out at random across the same
  trades, 2,000 times.

## Forecast error, pooled over coins (second half of the days)

A close is one row; coins are summed inside it. Positive = better than the
bot's flat guess. 76 comparisons in the full table, so a result needs |t| > 3.4.

| prints left | M1 own seconds | M2 books, same second | M3 books, 1 s newer |
|---|---|---|---|
| 45 | -0.9% (t -2.0) | -0.6% (t -0.6) | +1.5% (t 0.5) |
| 30 | -0.7% (t -1.6) | -2.7% (t -2.1) | +2.7% (t 0.7) |
| 20 | -1.1% (t -0.8) | -0.8% (t -0.5) | **+13.3% (t 3.7)** |
| 10 | +0.2% (t 0.3) | +0.4% (t 0.7) | **+17.4% (t 3.5)** |

Hand check on M3: if the next print were known exactly and prices were a pure
random walk, the best possible cut is 26% (10 left), 14% (20), 9.5% (30) and
6.5% (45). M3 recovers most of that at 10-20 and little at 30-45 -- the size
you'd expect from knowing one print early and nothing more.

Per coin, M3 at 10 prints left: BTC +13.6% (t 2.4), ETH +15.8% (3.4), SOL
+22.3% (3.1), XRP +18.5% (3.6), DOGE +13.7% (1.9). Calls on the wrong side of
the strike barely move (BTC at 10 left: 3 flat, 6 with M3, of 1,380 closes).
M1 on the four coins with no book feed (BNB, HYPE, NEAR, ZEC): -9.6% to +2.7%,
nothing real.

## Live trades (Kalshi ledger dollars)

| guess | trades it could score | losers refused | loser $ avoided | winners refused | winner $ given up | net | random nudges: losers / winners / net | luck does this well |
|---|---|---|---|---|---|---|---|---|
| M1 own seconds | 861 (26 losers) | 4 | $82.08 | 58 | $110.85 | **-$28.77** | 3.9 / 91 / -$78 | 58 in 100 |
| M2 books, same second | 479 (12 losers) | 2 | $40.03 | 50 | $86.51 | **-$46.48** | 1.7 / 71 / -$92 | 56 in 100 |
| M3 books, 1 s newer (PEEKS) | 479 (12 losers) | 9 | $230.56 | 105 | $200.50 | +$30.05 | 2.2 / 95 / -$113 | under 1 in 100 |
| ML what live could have known | 479 (12 losers) | 2 | $40.03 | 58 | $97.01 | **-$56.98** | 1.8 / 73 / -$93 | 57 in 100 |

The 12 losers with a book feed and the M3 "confidence" at the decision
(logged confidence first): BTC 09-17 21:15 ET 0.9956 -> 0.21; SOL 09-11
08:30 ET 0.9951 -> 0.01; DOGE 09-10 18:15 ET 1.0000 -> 0.50; XRP 09-10 01:00 ET
1.0000 -> 0.53; ETH 09-12 11:15 ET 0.9953 -> 0.66; BTC 09-14 05:30 ET 0.9999
-> 0.94; BTC 09-19 02:00 ET 0.9969 -> 0.98; BTC 09-12 11:00 ET 0.9956 -> 0.986;
XRP 09-19 23:45 ET 0.9992 -> 0.992; not refused: BTC 09-19 16:00 ET (-$107.95),
SOL 09-11 23:00 ET, SOL 09-12 04:00 ET. The bot's newest print on those 9 was
0.11-0.93 s old, so every one of those numbers used books from after the buy.
Full per-loser table: scratchpad `cp_tables.md`.

## Rerun

    python research/constpredict.py --selftest
    python research/constpredict.py            # ~4 min: re-extracts the last
                                               # 150 s of every close (~25 MB
                                               # scratch), then analyses
