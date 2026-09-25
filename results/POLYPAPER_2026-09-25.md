# Polymarket paper bot -- first two windows (2026-09-25)

**It works end to end, and it would not have bought anything in either window,
because nobody on Polymarket was selling the winning side at all.**
It is paper only. It never sends an order.

## What happened

| Window closed | Winner | How far it was decided | Polymarket, last 45 s | Kalshi, same seconds |
|---|---|---|---|---|
| 4:00 AM ET | Up | settle $158.81 above the start price | **no Up offer for sale in any of the 45 seconds**; about 6,500 shares bid at 99c | no offer at all |
| 4:15 AM ET | Up | settle $67.60 above | **no Up offer for sale in any of the 45 seconds**; about 3,000 shares bid at 99c | 99.9c from 45 s to 34 s left (too dear: above the 98c ceiling and loses money on average), then nothing |

The model was more than 99.5% sure in all 90 seconds, so the bot wanted to buy
every second. It had nothing to buy.

**Why the Polymarket side is empty:** its prices move in whole cents, so the
most anyone can ask for a winning share is 99c. Once buyers bid 99c, any
seller at 99c is filled immediately. A decided window on Polymarket shows a
wall of 99c buyers and no sellers. The pin bot only buys at 98c or less, so a
decided window there has nothing for it. The money, if there is any, is in
windows that are NOT yet decided at 45 s, where offers still sit at 90-98c.
Two windows cannot say how often that happens -- that needs days of running.

## What was checked and matched

- Polymarket's start price matched the one worked out from our own index tape
  **to the cent, 2 of 2**; its settle price matched ours to the cent, 2 of 2.
  Same index, same rule, confirmed live.
- The fair value is the live bot's own `fair()` code, not a copy; the
  self-test proves it matches the formula worked by hand.
- The bot read the index from the recorder's file about 0.4 s after each
  print, and Polymarket's book arrived in real time (9,459 book/trade messages
  in the second window, no connection errors, no file errors).

## How to leave it running (not left running now)

From a PowerShell prompt:

```powershell
Remove-Item C:\kals-repo\results\polypaper.stop -ErrorAction SilentlyContinue; Start-Process -FilePath C:\Python314\python.exe -ArgumentList '-u','C:\kals-repo\research\polypaper.py','--minutes','4320' -WorkingDirectory C:\kals-repo -WindowStyle Hidden -RedirectStandardOutput C:\kals-repo\results\polypaper.out -RedirectStandardError C:\kals-repo\results\polypaper.err
```

- Stop it: `New-Item -ItemType File C:\kals-repo\results\polypaper.stop` (it exits within 2 s).
- Read it: `python research\polypaper.py --report`.
- Tested: launched this way, stopped by the stop file, nothing left running.
- Cost: about 25 KB of log per window, so about 7 MB over 3 days. Memory about 50 MB.

## What the paper result will and will not mean

- Paper buys are "the offer was there and we took it". Real orders can lose
  the race (our Kalshi orders fill about 70 times out of 100), so paper money
  will look better than real money would. It answers "does Polymarket offer
  the deals", not "how often we would lose".
- Not copied from the live bot: bank-based sizing (paper uses 10 contracts),
  the per-close budget, second buys, hedging, the spike and toxic-selling
  gates. Everything else in the entry decision is the live bot's.
