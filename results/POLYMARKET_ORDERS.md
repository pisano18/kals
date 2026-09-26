# Polymarket US order path -- built, dry-run only (2026-09-25)

Times in this file are UTC (repo rule). File: `research/polyorder.py`.
**No order was sent to Polymarket or Kalshi while building this. Nothing was cancelled.**
The only requests that left the machine were reads (GET), listed in section 5.

## 1. In plain words

**What it does.** `polyorder.py` can buy Up or Down on the Bitcoin 15-minute
and 1-hour markets, the only markets your account offers. By default it
only *shows* the order it would send and sends nothing. It sends only when
you approve that exact order. Approval is a 16-character code that the dry
run prints. The code matches one market, one side, one price, one size, once.
Change anything and the code stops working. Re-using a code is refused.

**What it will not do.**
- Sell anything.
- Place a "market" order (buy at whatever price is there).
- Leave an order sitting in the book. Every order is "take what is there at
  my price, cancel the rest" (immediate-or-cancel).
- Pay more than 98c.
- Buy more than 5 contracts, or risk more than $5, in one order.
- Put more than $10 at risk in one day.
- Keep trading after $5 of losses in a day.
- Place more than 20 orders a day, or more than one order per window.
- Trade when it cannot read your balance, open orders, position or loss
  history. "Could not read" is treated as "stop", never as "nothing there".

**When a reply is lost.** Polymarket has no way to mark an order so that
sending it twice counts once. So the file never re-sends. It reads your
account to find out what happened. If it still cannot tell, it stops all
trading until that order is settled by hand (`--resolve`).

**Can your current key trade? Probably yes. Not proven.**
- Polymarket US documents only one kind of personal key. The same page that
  tells you how to make one says it is "where you place orders".
- Nothing about read-only keys appears anywhere for personal accounts. The
  permission levels in the docs belong to the separate institutional API.
- Your key already reads balances, positions, open orders, fills and a single
  order by its number: all returned 200.
- The only way to prove it can trade is to send something that writes. I did
  not. Step 1 of the test plan (section 6) does that for at most 1 cent.
- The key file says "disposable test key, 2026-09-17". The recorder and the
  paper bot use the same key, so do not delete it while they run.

**What your $60.52 actually is (read from your account at 11:49Z):**

| Part | Amount | Can you withdraw it? |
|---|---|---|
| Promotional deposit bonus (added 05:52Z) | $50.00 | No, it is held |
| Apple Pay deposit, status still PENDING | $10.00 | Not yet |
| Winnings from your 2.52-contract Down bet | $0.52 | Yes |

All $60.52 counts as buying power, so it can be traded. I could not find the
bonus rules through the API. They decide whether a loss comes out of the $50
bonus or your $10.

**Your manual bet, as the exchange recorded it:**
- Bought Down 2.52 contracts at 78c for $1.97, plus a $0.03 fee.
- Window 05:45-06:00Z. It won $0.55 before the fee, $0.52 after.
- It was paid 82 minutes after the window closed (07:22:38Z).
- The same record confirmed how Down orders must be written on the wire
  (section 3).

## 2. What you need to do to enable trading

1. **Nothing for the key, probably.** If Step 1 below is refused with "not
   allowed" or 401/403, then create a new key:
   - go to polymarket.us/developer;
   - sign in the **same way** you sign into the app (Apple, Google or email --
     their docs warn that switching breaks keys);
   - click create;
   - copy the Key ID and Secret (the secret is shown once) into a new file
     `C:\kals\polymarket_trade_key.json` as `{"key_id": "...", "secret": "..."}`;
   - `polyorder.py --creds C:\kals\polymarket_trade_key.json` then uses it.
2. **Check the bonus terms in the app**, if you care whether test losses eat
   the $50 promotion or your own $10.
3. **Approve Step 1** (section 6): one order that should not fill, at most 1c
   at risk.

## 3. The API, from primary sources

| Fact | Value | Source |
|---|---|---|
| Base URL (trading, account) | `https://api.polymarket.us` | [introduction](https://docs.polymarket.us/api-reference/introduction.md) |
| Auth | `X-PM-Access-Key`, `X-PM-Timestamp` (ms, within 30 s of their clock), `X-PM-Signature` = base64 Ed25519 over `{ts}{METHOD}{path}`, **path without query**, key = first 32 bytes of the secret | [authentication](https://docs.polymarket.us/api-reference/authentication.md), SDK `auth.py` |
| **Signature does not cover the body** | a leaked fresh signature for `POST /v1/orders` could carry any order for 30 s, so polyorder never prints or logs a full signature | same (message has no body) |
| Create | `POST /v1/orders` -> `{id, executions[]}` | [create-order](https://docs.polymarket.us/api-reference/orders/create-order.md) |
| Body | `marketSlug`, `intent` (BUY_LONG / BUY_SHORT / SELL_LONG / SELL_SHORT), `type` LIMIT / MARKET, `price {value, currency}`, `quantity` (number), `tif`, `participateDontInitiate` (post-only), `goodTillTime`, `manualOrderIndicator` ("required for regulatory compliance"), `synchronousExecution` + `maxBlockTime` | [orders overview](https://docs.polymarket.us/api-reference/orders/overview.md) |
| Time in force | DAY, GTC, GTD, **IMMEDIATE_OR_CANCEL**, FILL_OR_KILL | same |
| **Up / Down** | only Up (YES, "long") is an instrument. `price.value` is ALWAYS the Up price. Buy Down at q = `BUY_SHORT` with `price.value = 1 - q`. Confirmed on your real order: BUY_SHORT, price.value 0.12, avgPx 0.22 = Down at 0.78. The **order** is in Up terms; your **position** record shows 0.78 (Down terms) | same, and your order `CPZBEBJ5YXPK` |
| Cost / max loss | buy Up at p: pay p. Buy Down at q: buying power falls by q. Fully collateralised, no margin calls | [collateral-and-margin](https://docs.polymarket.us/market-structure/collateral-and-margin.md) |
| Tick / size | read from the market: BTC 15m and 1h both `orderPriceMinTickSize` 0.01, `minimumTradeQty` 0.01 (fractions allowed); prices 0.01-0.99 | market objects (GET), overview |
| Fees | taker 0.0695 x C x p x (1-p), maker rebate 0.0125 x C x p x (1-p), banker's rounding to the cent **per order**. 1 contract at 97-98c = **$0.00**; 60 at 97c = $0.12 | [fees](https://docs.polymarket.us/fees.md) (effective 2026-09-25) |
| Rate limit | 20 requests/s per key, all endpoints (shared with the recorder and polypaper) | [rate-limits](https://docs.polymarket.us/api-reference/rate-limits.md) |
| Latency stopgap | an order not processed within 5 s is rejected with the text "Global Rate Limit Exceeded". Their docs: this is NOT a rate limit, do not back off | same |
| **No idempotency key** | there is no client order id. The official SDK never retries an order: "the API has no idempotency key, so a retry after a partial failure could submit a duplicate order" | polymarket-us 1.0.2 `_retry.py` |
| Read an order | `GET /v1/order/{id}`: state, cumQuantity, leavesQuantity, avgPx (Up terms), commissionNotionalTotalCollected | [get-order](https://docs.polymarket.us/api-reference/orders/get-order.md) |
| Open orders | `GET /v1/orders/open?slugs=...` | [get-open-orders](https://docs.polymarket.us/api-reference/orders/get-open-orders.md) |
| Cancel | `POST /v1/order/{id}/cancel` body `{marketSlug}`. Cancel-all and batch cancel exist; polyorder uses neither. Batched results "do not confirm per-entry success" | [cancel-order](https://docs.polymarket.us/api-reference/orders/cancel-order.md) |
| Balance | **`GET /v1/account/balances`** (the 404 seen earlier was `/v1/portfolio/balance`, a route that does not exist) | [get-account-balances](https://docs.polymarket.us/api-reference/account/get-account-balances.md) |
| Positions / fills / payouts | `GET /v1/portfolio/positions?market=`, `GET /v1/portfolio/activities?types=ACTIVITY_TYPE_TRADE / ACTIVITY_TYPE_POSITION_RESOLUTION&marketSlug=` | [positions](https://docs.polymarket.us/api-reference/portfolio/get-user-positions.md), [activities](https://docs.polymarket.us/api-reference/portfolio/get-activities.md) |
| Real-time fills | `wss://api.polymarket.us/v1/ws/private`: SUBSCRIPTION_TYPE_ORDER / POSITION / ACCOUNT_BALANCE | [private websocket](https://docs.polymarket.us/api-reference/websocket/private.md) |
| Test environment | **none for personal accounts.** Pre-production exists only on the institutional Exchange API (`api.preprod.polymarketexchange.com`, RSA keys + onboarding). There is an order **preview** (`POST /v1/order/preview`) that returns expected fills without creating an order. Its body shape differs between the REST doc (wrapped in `request`) and the SDK (bare) -- unverified | [preview-order](https://docs.polymarket.us/api-reference/orders/preview-order.md), [trader-guide auth](https://docs.polymarket.us/trader-guide/authentication.md) |

**Traps found in your real records, now handled in code:**
- A **filled** order carries `orderRejectReason: ORD_REJECT_REASON_EXCHANGE_OPTION`.
  Code that treats "has a reject reason" as "rejected" books every fill as a
  reject. polyorder counts an order as rejected only if the event type or the
  order state says REJECTED.
- Trade records contain the order that took the trade, including its id. That
  is how a lost reply is matched back to our order.
- 15-minute markets **do not always exist**:
  - 11:00, 11:15, 11:30 and 11:45Z today returned 404 (the paper bot logged
    no price-to-beat for 11:30Z);
  - future windows read MARKET_STATUS_HALTED until they open: 12:00Z read
    HALTED at 11:49Z and OPEN at 12:04Z, 12:15Z read HALTED at 12:04Z.
  polyorder refuses any market that is not OPEN.

## 4. Self-test

`python research/polyorder.py --selftest`: **84 checks, 0 failed.** It runs
automatically before every use and refuses to touch the API if it fails. It
uses a fake connection that records every request, so nothing reaches the
network. What it proves:

- **Nothing is sent without both switches.** No approval code, a wrong code,
  and an oversize order *with its own valid code* each produce zero requests.
  The right code produces exactly one create request. Replaying it is refused
  by the order log.
- **Every limit refuses:**
  - "97" instead of 0.97 (the unit is never guessed);
  - 0.975 (off the 1c tick), 0.99 (over 98c), 0 and 1;
  - quantity 6, 0, 0.005 and 1.005;
  - a Kalshi ticker, or any other Polymarket market;
  - a GTC order, a market order, a SELL, a Down price written in Down terms,
    or an extra field;
  - a market that is HALTED or has ended;
  - post-only left resting over 60 s;
  - $5 of cost is tested with the size cap raised. At the shipped 5-contract
    cap the most any order can cost is $4.90, so the size cap binds first.
- **Outcomes read correctly** (from the create reply, then confirmed by
  reading the order back):
  - full fill;
  - a Down fill booked at 97c from a wire price of 0.03;
  - partial fill (1 of 3);
  - no fill;
  - exchange reject, with its reason kept;
  - the 5-second latency reject;
  - an HTTP 400;
  - accepted with no fills reported yet;
  - your real order: Down, 2.52 contracts at 78c, $0.03 fee.
- **Lost replies are settled by reading, never by re-sending:**
  - timeout, then our order is found in the fill history: filled;
  - timeout, nothing found, position unchanged: no fill;
  - timeout, nothing found, but the position moved: UNKNOWN;
  - server error and the account unreadable: UNKNOWN;
  - an UNKNOWN stops the next order even with a valid code, until
    `--resolve` settles it by reads alone.
- **An order that stays in the book when it should not** (IOC read back as
  resting): cancelled by its own id, checked gone, and trading stops if the
  cancel cannot be confirmed. Cancelling an id this program did not create is
  refused.
- **Daily limits and pre-send reads each refuse with nothing sent:**
  - $9.50 already at risk today plus a 97c order;
  - $5.20 lost today;
  - loss history unreadable;
  - balance unreadable;
  - 50c of buying power;
  - an order already open;
  - market halted;
  - local clock 60 s off the exchange's.
- **Signing and logs:**
  - signatures verify against the key and match `C:\kals\poly_us.py` byte for
    byte;
  - the query string is never signed;
  - the real connection code was run with the network stubbed out;
  - across 224 log lines, neither the secret nor any of the 162 signatures
    appears.
- **Code map:**
  - requests leave from only three functions: create, cancel-own-order, and
    reads;
  - the program contains no cancel-all, close-position, modify, batch,
    delete, market order, cash-sized order or SELL.

**Mutation check** (does the test catch a broken program?). I broke 21 rails
one at a time in a scratch copy. The self-test failed on **20**. The 21st
removed the "no code given" check. Its removal changes nothing, because an
empty code also fails the "wrong code" check. Two gaps this check found were
fixed before this write-up: a signature logged under a different field name,
and "no order found but the position moved".

## 5. Read-only checks with the existing key (GET only)

| Request | Result |
|---|---|
| `GET /v1/account/balances` | 200, 156 ms: buying power $60.5244; withdrawable $0.5244; bonus held $50; deposit reserved $10; open orders $0 |
| `GET /v1/portfolio/positions` | 200: none |
| `GET /v1/orders/open` | 200: none |
| `GET /v1/portfolio/activities` | 200: 4 records (the $10 deposit PENDING, the $50 bonus, your fill, its payout) |
| `GET /v1/order/CPZBEBJ5YXPK` | 200: FILLED, Down 2.52 at 78c, fee $0.03 |
| `GET /v1/market/slug/...` | 1h 11:00Z OPEN; 15m 11:00-11:45Z 404; 15m 12:00-12:30Z HALTED at 11:49Z |
| dry runs (Down 97c x1 on 15m 12:00Z; Up 97c x1 on 1h 12:00Z) | built, signed and printed. Approval codes `9bdb6b3a311ca55b` and `2ec4a4d7bbc26f4d` are **not approved and now useless** (both windows are over) |
| `results/polyorder-20260925.jsonl` | 9 GET, 0 POST, no signature |

GET round trips from this machine: 81-197 ms.

## 6. Proposed live test (each step needs your per-order approval)

**Step 1: wire test. Should not fill; worst case 1 cent.**
- Buy Up at $0.01 x1, immediate-or-cancel, on an open window where Up is
  plainly not offered at 1c.
- *Pass:* 200; state CANCELED; 0 filled; no position; balance unchanged.
  This proves the key can trade, the body shape, the immediate-or-cancel
  behaviour and the read-back.
- *Kill:* 401/403 (make a new key, section 2); any fill; any outcome still
  UNKNOWN after `--resolve`; the order still resting after the reply.

**Step 2: 1-contract pin fills. 20 fired windows or 14 days, whichever first.**
- A window fires when `polypaper.py`'s decision says buy: the live bot's
  gates, Polymarket's fee, 45 s or less left.
- One order per window: 1 contract, limit = the offer, never over 98c.
- Worst case $0.98 a window. The $10 daily cap and $5 daily-loss cap hold
  throughout.
- Written before any result is seen, so the bar cannot move:
  - *Kill at once* on any mechanical failure:
    - an outcome still UNKNOWN after `--resolve`;
    - an order left resting;
    - a fill above our limit;
    - a payout that does not credit $1.00 per winning contract within 2 hours;
    - the $5 daily-loss cap reached.
  - *Kill on losses:* 2 or more losing windows in the first 20.
    - Break-even is 2 losses in 100 at 98c and 3 in 100 at 97c.
    - If the true rate were 3 in 100, this bar would kill a good strategy 12
      times in 100. If it were 10 in 100, it would kill 61 times in 100.
  - *Pass (go to 5 contracts, which is a code edit plus a new version entry):*
    all of:
    - 0 mechanical failures;
    - at most 1 loss;
    - contracts filled in at least 10 of the 20 fired windows (Kalshi fills
      about 70 in 100);
    - median price paid 97.5c or less.
- **What it cannot tell you: the loss rate.** 20 windows cannot tell 0
  losses in 100 from 3 in 100. Even at 3 in 100 there is a 54-in-100 chance
  of zero losses in 20. It measures the plumbing, the fill rate, speed and
  payout time.
- Money: at most +$0.60 if all 20 win at 97c. One loss costs $0.97.
- **How per-order approval works at this speed.** The decision lands in the
  last 45 s, too fast to approve by hand.
  - So you approve a list of tickets **before** the windows open: for each
    chosen window, "Up at up to 98c x1" and "Down at up to 98c x1". Each
    ticket has its own code.
  - The one-order-per-window rule means at most one ticket per window is
    ever used.
  - Every ticket is still one exact order approved in advance. Nothing is
    standing approval. The wiring that consumes tickets is not built yet.

## 7. How it would plug into a bot (described, not built)

- **Decision:**
  - `polypaper.Bot.second()` already runs the live bot's own `fair()` and
    entry gates on Polymarket's real-time book every second;
  - its first "would buy" in a window becomes
    `make_order(slug, side, min(offer, 0.98), qty)`;
  - the order goes to `run_live(order, <ticket code>, ...)`.
- **Keep the reads out of the fast path:**
  - `run_live` does 6 GETs first (market, balance, open orders, position,
    loss history, clock). At the measured 81-197 ms each that is about
    0.5-1.2 s;
  - a bot would do them at about 60 s before the close and cache them, so
    only the create request (~0.1-0.2 s) happens when it fires. That needs a
    `run_live` variant that takes the cached snapshot. Not built.
- **Fills:** subscribe to `wss://api.polymarket.us/v1/ws/private` (order and
  position updates) instead of polling. Keep the read-back as the fallback
  for a lost reply.
- **Payouts:** read `ACTIVITY_TYPE_POSITION_RESOLUTION`. Your bet paid 82
  minutes after its window. The power-hour read saw 7-27 minutes, with some
  windows still unpaid after 73. So money is tied up 8 to 80+ minutes per
  fire.
  That lowers how many windows $60 can cover back to back.
- **Hedging must not be blocked.** The one-order-per-window rule would block
  a hedge (buying the other side in the same window). Before any hedging bot:
  allow a second order per window only on the opposite side.
- **Shared limits:** the recorder, polypaper and a live bot share one key's
  20 requests a second. A version entry (`v-poly1`) goes into
  `results/VERSIONS.md` at the moment of deployment, with the revert command.

## 8. Not verified

- That the current key can write. Step 1 settles it.
- The exact create reply for an immediate-or-cancel order with
  `synchronousExecution`: the shape is from the docs, not seen live.
  polyorder confirms every order by reading it back, so a different shape
  degrades to a read, not a wrong booking.
- `goodTillTime`'s accepted format. Post-only is built and fake-tested but
  has never run live; the test plan does not use it.
- The bonus rules, and whether losses draw on the $50 bonus first.
- Latency from here to their matching engine. Reads measured 81-197 ms.

## Commands

```
python research/polyorder.py --selftest
python research/polyorder.py --show balance        # also: positions, open, fills, resolutions
python research/polyorder.py --show order --order-id <id>
python research/polyorder.py --slug <slug> --side up|down --price 0.97 --qty 1     # dry run
python research/polyorder.py ... --live --signoff <code printed by the dry run>    # only with approval
python research/polyorder.py --resolve <intent id>  # read-only
python research/polyorder.py --ledger
```

## Step 1 result -- 2026-09-26 07:26Z: PASS

Order CQNA55ZVAYCA: buy 1 Up at $0.01, IMMEDIATE_OR_CANCEL, on
cpc-btc-updown-15m-2026-09-26-0715z, sent by the session after the operator
added the permission rule. HTTP 200; state ORDER_STATE_EXPIRED; filled 0; fee 0;
clock skew 0.6 s. Read-back: 0 open orders, no position, buying power $60.5244
(unchanged; $50 bonus held, $10 deposit not yet available, $0.5244
withdrawable). Every pass condition met; no kill condition hit. Next: Step 2.
