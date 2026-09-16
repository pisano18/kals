# Crypto.com / CDNA -- a second venue with the same mechanism. 2026-09-16.

## What it is
CDNA (Crypto.com | Derivatives North America, the former Nadex) is a CFTC
Designated Contract Market. It lists BINARY OPTIONS on crypto, FX and stock
indices in **5, 15 and 20 minute windows**.

## Why it matters
`ptc04012642967.pdf` (CDNA's own Bitcoin Event Contract certification, filed with
the CFTC) defines the Expiration Value as the index value at expiry, where each
second's index is:

> "taking all U-BTC bid/ask midpoint prices occurring in the sixty (60) seconds
> leading up to the Calculation Time... removing the highest twenty (20) percent
> ... and the lowest twenty (20) percent ... The calculation used is a simple
> average of the remaining U-BTC bid/ask midpoint prices"

**A 60-second average ending at expiry.** That is the same variance collapse the
Kalshi pin bot rests on: with 30 seconds left, half the settlement window is
already fixed. Trimming the tails makes a late spike matter LESS, which helps.

Tick $0.01. Position limit 2,500,000 contracts.

## What is public, with no key at all
Base `https://api.crypto.com/dcm/v1/` -- verified working unauthenticated:

| endpoint | gives |
|---|---|
| `public/get-instruments?limit=1000` | every contract, with **STRIKE_PRICE, OPEN_TIME, CLOSE_TIME, underlying index** in `event_details.attributes` |
| `public/get-book?instrument_name=...&depth=10` | live order book |
| `public/get-trades?instrument_name=...` | prints |
| `public/get-tickers?instrument_name=...` | high/low/last/volume |
| `public/settlement-rules` | the settlement rule catalogue |

`?limit=1000` is not optional: the default page showed 122 binaries when 522
were live.

Example row: `XRP >1.2701 (10:40AM)`, opens 14:35, closes 14:40 -- a five-minute
contract with the strike stated outright.

## Scale, measured 2026-09-16 14:5xZ
**522 live binaries at once.** Crypto: BTC ETH SOL XRP LTC BCH DOT ADA XLM LINK
AVAX DOGE SHIB PEPE BONK FLOKI HBAR ONDO SEI CRO (20 names). Also EUR/USD,
GBP/USD, USD/JPY, AUD/USD and the Nasdaq, S&P, Dow and Russell, those quoted as
ladders of strikes. Windows seen: 5 min (38), 15 min (20), 20 min (60).

Kalshi gives us 96 closes a day. Ten coins on 5-minute windows would be 2,880.

## What is NOT available
* **Their index value.** `get-valuations`, `get-candlestick` and `get-tickers`
  all accept `BTCUSD-INDEX@CdnaFunded` and return EMPTY. The exchange WebSocket
  does not know DCM symbols, and `wss://stream.crypto.com/dcm/v1/market` refuses
  the connection. Probably an internal feed.
* **Order placement.** Everything public is read-only. The app's agent key
  (`crypto-agent-trading`) authenticates but carries only app scopes --
  trading.order:write for SPOT, balance, fiat -- and every prediction route
  returns `route_not_found`. That key was revoked after testing.

## The two things the tape will answer without any further access
1. **Is our CF Benchmarks feed a good enough proxy for their index?** Their book
   right before expiry reveals each outcome, so we can score our own feed against
   their settlements without ever seeing their index.
2. **Does anyone sell a near-certain side cheap?** First look was discouraging --
   spreads of 8-24c minutes before expiry, where our edge is 2-4c. If that holds
   into the final seconds there is no trade here regardless of access.

`research/cdc_record.py` records books, trades, tickers and the instrument list
for every binary within 7 minutes of expiry, into `C:\kals\cdc_data`.
Read-only, public GETs only.
