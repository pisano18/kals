# The Crypto.com agent key cannot reach prediction markets

Measured 2026-09-16. Settled; do not re-litigate without new evidence.

## What the operator had

An agent key issued in the Crypto.com app, shown with **Permissions: All**, a
**weekly trading limit of $20,000** and expiry 2026-12-15. He read the trading
limit as evidence it could trade, which was a reasonable read, and offered to
fund the account with $5 to test order placement.

## What it actually reaches

The key signs correctly against `https://wapi.crypto.com` and the account is
real: id 57243163, native USD, balance $0.00. Its entire route surface:

| route | what it is |
|---|---|
| `/v1/crypto-purchase/quotations` + `/orders` | buy crypto with fiat |
| `/v1/crypto-sales/quotations` + `/orders` | sell crypto for fiat |
| `/v1/crypto-exchange/quotations` + `/orders` | swap one coin for another |
| `/v1/transactions` | history |
| `/v1/portfolio`, `/v1/crypto-account`, `/v1/api-keys/current` | account |

Nothing prediction-shaped exists. Nineteen candidate spellings were probed
(`predictions`, `prediction-markets`, `event-contracts`, `binary-options`,
`derivatives`, `dcm`, `fcm`, `cdna`, `futures`, `sports`, `markets`, and
`/quotations` variants of several) and every one returned
`{"error":"route_not_found"}`.

The route list is independently confirmed by the skill's own source:
`crypto-com/crypto-agent-trading`, `crypto-com-app/scripts/trade.ts`. Its
`SKILL.md` describes spot buy/sell/swap, coin search and fiat cash management,
and mentions prediction markets nowhere.

## The control, and why this file exists at all

**The first version of this measurement was wrong and said the opposite of
nothing.** It probed with GET, found 0 of 39 routes, and concluded predictions
were absent. Then `cdc_control.py` probed four routes taken from the skill's
own source, and three of the four ALSO returned `route_not_found` -- wapi
scopes routes by HTTP method and reports a GET to a POST-only route as a
missing route. The conclusion had no support.

`cdc_routes.py` now probes GET then POST-with-empty-body, and carries the
control inline: it prints how many known-real routes it found and how many
invented ones. The run above found **4 of 4 real, 0 of 2 invented**. Only on
that basis is the absence of prediction routes a finding rather than a bug.

A second bug the self-test caught: the read-only guard's word list did not
contain "order", so it would happily have POSTed to
`/v1/crypto-purchase/orders`, which is a real money order route. `writes()` in
`cdc_routes.py` now rejects a bare `orders` tail.

## Consequence

- **The $5 test cannot work.** There is no endpoint to place the order against.
  Funding the account proves nothing about CDNA.
- Order entry on CDNA prediction contracts is still FIX-only and still needs
  CDNA to issue a session. `results/CDNA_ACCESS_EMAIL.md` is the request.
- **The key should be revoked.** It cannot do the one thing it was made for,
  and it can spend up to $20,000 a week on spot, while sitting in a phone
  screenshot. The skill exposes a revoke call; the app's Agent Key screen has
  a Delete key button.

## Files

`C:\kals\cdc_reach.py` (auth + what the key reaches), `cdc_routes.py` (route
map with inline control), `cdc_control.py` (the check that caught the first
answer). Credentials live in `C:\kals\cdc_agent_key.json`, outside the repo,
and are not committed.
