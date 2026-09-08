# Morning report — 2026-09-08

## The one-line answer

**pin is live and trading your money at 1 contract (~$0.99) a bet.** The full
money path — order → fill → fee → settlement → **payout** — is proven end to
end with a real 1-cent trade. The blocker that made every earlier attempt
impossible was that your cash sat on the wrong exchange shard.

## What is certain (verified against the exchange, not from my own logs)

| | |
|---|---|
| Crypto shard (pin's universe) | **$30.0026** — was $0.0026 |
| Default shard | $11.0360 |
| Resting 1c order | `KXBTCMAXY-26DEC31-99999.99`, `penny-proof-1`, still live |
| Penny round trip | **PROVEN** — see below |
| pin deployed | live, size 1, loss abort −$3.00, max 3 positions |

### The proven round trip

```
BOUGHT     0.01 YES @ 0.9900  on KXBTC15M-26SEP080315-15
           order 01a07fdd-6d48-761d-8a15-a8311dbd5656, status executed
BALANCE    $41.0386 -> $41.0286   (-$0.0100 = $0.0099 stake + $0.0001 fee)
SETTLED    yes; we held YES; WON
BALANCE    $41.0286 -> $41.0386   (payout $0.0100)
NET        $0.0000
```

Net zero because at 1/100th of a contract the 1c edge and the fee are both
$0.0001. **At size 1 the identical trade nets +0.93c.**

## THE BLOCKER — why nothing could ever have traded

Kalshi splits an account across shards. **Every 15-minute crypto market is on
shard 2 ("Crypto"), which held $0.0026 while $41.04 sat on shard 0.** pin's
first real order was rejected `insufficient_balance`. Last night's natural-gas
run worked only because commodities are on shard 0.

Fixed with `POST /portfolio/intra_exchange_instance_transfer`, shard 0 → 2,
landed in under 4 seconds. **`amount` is in CENTICENTS** (300,000 = $30.00);
a secondary source saying "cents" is wrong, and the measured transfer proves it.

## The headline measurement

**Flip rate 0.01% — 1 wrong call in 10,421, over 236 closes.**
Breakeven against a 2c win is **2.00%**, so roughly a **200× margin**.

This only became true after a fix that I had *reported as applied and which
had not been*. With `round_digits` assumed instead of read, the rate was 0.75%
(78 wrong, all DOGE). DOGE's `round_digits` is **7**, not the 4 I assumed.

The corrected backtest also survives: **+2.51c/contract, t=+4.1** over 354
closes (was +2.55c, t=+5.0). More importantly pin's own "BELOW the fair band —
our tail probability is wrong" flag is **gone**; the model has stopped
over-claiming its own certainty.

## Every bug found tonight, in order

1. `close_s` used `time.mktime - time.timezone`, which ignores DST — **off by
   3600 s**. pin would have been silently dead all night.
2. `risk_abort` read `LEDGER["halted"]`/`["stake"]`; the real keys are `halt`
   and `committed`. **Both safety checks were dead.**
3. The `$5` stake cap was never released on settlement, so it capped *lifetime
   turnover* (~5 bets) rather than concurrent risk — the run would have halted
   on its own success.
4. `sorted()` on markets sharing a close time raised `TypeError` — all twelve
   coins close on the same second. **Cost a live trading window.**
5. `take()` defaulted `exchange_index` to 0; every crypto market is 2.
6. The strike was read from the truncated `floor_strike` instead of the exact
   `custom_strike.floor_strike`.
7. `round_digits` was assumed (4) instead of read (DOGE is 7) — **77 of 78
   wrong calls.**
8. A rejection (`HTTP 400`) was reported as "no fill — the send path is
   proven", which is backwards, and is how the shard problem got misreported.
9. **Two fixes were reported as applied and had not been** — the patch script
   died on a Windows path inside a Python string and I read the next command's
   "PASSED" as confirmation.

## What is NOT proven

- **pin has never completed a full-size trade.** The proven round trip was
  0.01 contracts, placed deliberately, not chosen by the strategy.
- **The fill rate in the race is unmeasured.** Prediction 40–60%, from tape
  survival times; not observed.
- **Spot substitution is unfixed.** The model replaces every unprinted
  settlement tick with the current price; a dip that recovers makes it
  confidently wrong. The single surviving flip is exactly this, at 1.20σ of
  transient vs 0.29σ when correct (4.1× ratio). A guard would help and was
  **deliberately not added tonight** — that is changing the rule after seeing
  the result, and needs its own pre-registration.

## The decision waiting for you

| size | per bet | earnings/day (backtest) | one wrong bet |
|---|---|---|---|
| 1 (running) | $0.99 | ~$0.93 | −$0.99 |
| 10 | $9.90 | ~$9 | −$9.90 |
| 30 (max on $30) | $29.70 | ~$18–28 | **−$29.70** |

Capital stops helping past ~$100: bets last under 60 s and closes are 15 min
apart, so you only ever need one bet's worth at a time. The binding limit is
**opportunities × book depth**, not cash.

Diversifying across the 12 coins does **not** reduce risk — they settle at the
same second at ~0.8 correlation.
