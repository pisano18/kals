# Gemini: the best-shaped venue yet, and one wall left

Measured 2026-09-16/17.

## Why it matters more than Crypto.com or Polymarket

| | Kalshi (live) | Crypto.com | Polymarket | **Gemini** |
|---|---|---|---|---|
| settlement | 60 x 1s average | 60s trimmed avg | 5-min TWAP | **60s average (Kaiko)** |
| spread | 1-2c | 24c | 1c | **3c** |
| book at the close | alive | **dead at -40s** | alive | not yet measured |
| US access | yes | FIX only, gated | **blocked** | yes, CFTC DCM |
| market data API | yes | yes | yes | **yes, public** |
| order API | yes | no | no | **spot yes, events NO** |

Gemini Titan is a CFTC-regulated DCM (approved December 2025) running 5- and
15-minute Up/Down markets on BTC, ETH, SOL, XRP and ZEC -- the same five coins
we already trade -- settling on `GRR-KAIKO_RFR_<coin>USD_60S`, **a sixty-second
average**. That is the same variance collapse the pin is built on.

## What works

**Event-contract order books are on the PUBLIC api, unauthenticated:**

    GET /v1/book/GEMI-BTC2609170300-HI75800
    -> {"bids":[{"price":"0.95","amount":"444.0", ...

Symbols are `GEMI-<COIN><YYMMDDHHMM>-HI<strike>`. `/v1/symbols/details/<sym>`
works too and reports `tick_size 0.01`, `min_order_size 0.01`,
`status "limit_only"`.

**The key authenticates and trades.** `account-G1cB...`, `isTrader: true`,
**9 authenticated calls per second** measured. A real limit order on BTCUSD was
placed (HTTP 200, `is_live: true`) and cancelled (`is_cancelled: true`), so the
order path is proven end to end on spot.

## The wall

**An order on an event contract returns HTTP 500** with
`"reason":"API request failed: contact Gemini support with error id
'8el27e0ag'"`. The identical request shape succeeds on BTCUSD, so it is not the
route, the key, the signature or the nonce -- it is the instrument.

Almost certainly the same shape of problem as Crypto.com: Gemini Titan is a
separate legal entity from the Gemini spot exchange, and the account is not
enabled for it.

**SO DO NOT SELL THE BTC.** The operator asked to convert it and buy a
contract. Converting his only asset there to USD achieves nothing while the
contracts cannot be bought, and the sale is irreversible. The account holds
$0.01 USD and 0.00017819 BTC, about $13.57.

## Gotchas already paid for

- **The nonce is not milliseconds on a master key.** A `master-` key rejected
  both ms and microsecond nonces; the full error says the nonce must be within
  30 seconds of server time *in seconds*. An `account-` key accepts
  milliseconds and runs at 9 calls/second. Use an account key.
- **SHA-384, not SHA-256.** The signature is 96 hex characters. The wrong
  digest is a silent 401 that looks exactly like a bad key.
- **A master key needs `"account": "primary"`** in the payload or every private
  call returns `MissingAccounts`.
- **The 5-minute markets are not reachable** from any URL found so far. Their
  prediction landing page server-renders only hourly and daily crypto strike
  ladders. Symbols validate cleanly (400 "not a valid symbol" for a guess, 200
  for a real one), so the space is searchable but large.

## Files

`C:\kals\gem_auth.py` (what the key reaches), `gem_order.py` (the ONLY file
that may send an order -- refuses SELL outright, caps cost, requires --live,
and can cancel), `gem_scrape.py` and `gem_find.py` (finding the contracts).
Credentials in `C:\kals\gemini_key.json`, outside the repo.

## What unblocks it

1. Whether the account can be enabled for Gemini Titan prediction trading.
   Error id `8el27e0ag` is the thing to quote at support.
2. The URL of a 5- or 15-minute market page, which yields the symbol pattern
   for the contracts we actually want.
