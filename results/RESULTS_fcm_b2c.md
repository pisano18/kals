# The GEN4 FCM US B2C API is the right product, and it is not FIX

Measured 2026-09-16. This supersedes the working assumption that CDNA order
entry requires FIX onboarding.

## The finding

`/fcm/v1` and `/dcm/v1` **serve the identical instrument set.** Both return
742 `EVENT_COMBO` and 258 `BINARY_OPTION` rows, the same symbols, the same
examples, across 29 underlyings (BTC, ETH, SOL, XRP, ADA, BCH, DOGE, DOT, LTC,
LINK, AVAX, SHIB, PEPE, BONK, FLOKI, HBAR, ONDO, SEI, CRO, four FX pairs, and
index names). The FCM B2C product is the same market `cdc_record.py` has been
taping all day.

That API is **REST and WebSocket**, documented at
`exchange-developer.crypto.com/fcm-b2c/v1/docs/`, and it carries
`private/create-order`. FIX is one way in, not the only way.

## Hosts

| | |
|---|---|
| REST production | `https://api.crypto.com/fcm/v1/{method}` |
| REST sandbox | `https://uat-api.3ona.co/fcm/v1/{method}` |
| WebSocket user | `wss://stream.crypto.com/fcm/v1/user` |
| WebSocket market | `wss://stream.crypto.com/fcm/v1/market` |
| WebSocket sandbox | `wss://uat-stream.3ona.co/fcm/v1/{user,market}` |

**THE SANDBOX IS LIVE AND IT CARRIES 990 BINARY OPTIONS**, including the crypto
names plus GOLD and CRUDE. An order-entry client can be built and certified
there end to end before a dollar is at risk, and sandbox credentials are
normally far easier to obtain than production ones.

## Signing, now verified against the published spec

    sigPayload = method + str(id) + api_key + params_string + str(nonce)
    sig        = hex(HMAC_SHA256(secret, sigPayload))

`params_string` sorts keys, concatenates `key + value` with no delimiter,
writes a null as the literal `null`, flattens lists element by element and
recurses into nested objects to three levels. `fcm_auth.py` implements exactly
this and its self-test checks each rule.

**FCM B2C adds a rule the Exchange API does not: "All numbers must be strings,
and must be wrapped in double quotes."** A client that sends a numeric price
signs a different string than the server verifies. Both forms are implemented
and tried.

## What we hold, and what it gets us

Neither credential authenticates anywhere on FCM. Every attempt, on both hosts,
with both number forms, returns **40101** which the docs define as "not
authenticated, or key/signature incorrect".

It is never **40103** (IP not whitelisted), so the allow-list is fine, and a
deliberately bad nonce does return **40102**, which proves the server parses
our body and reads our fields before rejecting the signature.

So the missing piece is an FCM-issued credential. The docs: "complete FCM
onboarding through Crypto.com Exchange" and "use the API Key provided to you".

## A lead that died, recorded so it is not resurrected

`/fcm/v1/private/get-account-summary` answers **403 with an empty body** while
every other path answers 401, and this was reported to the operator as evidence
that the route exists and we are merely unentitled. **That was wrong.**
`fcm_probe.py` ran the control: an unsigned request carrying no credentials at
all, and a request signed with an invented key, both get the same 403. It is a
gateway rule on the path and says nothing whatever about our entitlement.

## What is needed

One thing: **FCM B2C API credentials**, sandbox first. Everything else --
the client, the signing, the order plumbing -- is ours to build and the
signing half is already written and tested.

## Files

`C:\kals\fcm_instruments.py` (which product carries the binaries),
`fcm_auth.py` (signing to spec, both hosts, both number forms),
`fcm_probe.py` (the control that killed the 403 lead).
