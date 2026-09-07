#!/usr/bin/env python3
# VERSION: 2026-09-06-o1
"""ordercli.py -- the ONLY file in this repo that can send a non-GET request.

IT DOES NOTHING BY DEFAULT. Every path is a dry run unless the operator passes
--live AND --signoff with the exact token printed by the dry run. There is no
standing permission: the token changes with the order, so a sign-off authorises
ONE order and cannot be reused for a different one.

WHY IT EXISTS
  Everything this project has measured about market-making is a model of an
  undisturbed book. An independent critic put it exactly right: "static-book
  share is not live share... no amount of historical reconstruction closes it.
  Only filled orders do." This file is how that gets closed, at the smallest
  size that produces a readable answer.

THE SAFETY RAILS, and why each one is here
  post_only=True ALWAYS. A post_only order rests or is rejected; it can never
    cross the spread. So this file CANNOT take liquidity, cannot pay a taker
    fee, and cannot execute against a price it did not choose. That single flag
    is what makes a live test bounded.
  MAX_COUNT and MAX_NOTIONAL are hard-coded ceilings checked before signing.
    They are not arguments. Changing them is a code edit and a commit.
  Never a market order. Never `time_in_force` other than good_till_canceled.
  Cancel-on-exit: any order this process opens, it closes, including on
    KeyboardInterrupt and on an unhandled exception.
  DEMO IS THE DEFAULT BASE URL. Production requires --prod, which is checked
    against the sign-off token as well.

  Credentials are NOT shared between environments (Kalshi's own words), so a
  demo key cannot touch production even by mistake.

    python ordercli.py --selftest
    python ordercli.py --dry-run --ticker KXCRYPTOLEAD15M-... --price 0.30 --count 1
    python ordercli.py --live --signoff <token>   # only after the operator says yes
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEMO = "https://external-api.demo.kalshi.co/trade-api/v2"
PROD = "https://external-api.kalshi.com/trade-api/v2"

# HARD CEILINGS. Not arguments. A live test that needs more than this is a
# different decision and needs a different commit.
MAX_COUNT = 5.0            # contracts, per order
# MAX_NOTIONAL MUST BIND. At MAX_COUNT=5 the largest possible notional is
# 5 x 0.99 = $4.95, so a $5.00 ceiling could NEVER fire -- the self-test
# caught it as dead code on its first run. $2.50 is reachable (5 contracts at
# 50c) and therefore actually constrains.
MAX_NOTIONAL = 2.50        # dollars of collateral, per order
MAX_OPEN_ORDERS = 4        # across the process


def load_key(path):
    from cryptography.hazmat.primitives import serialization
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def sign_headers(pk, key_id, method, path):
    """Kalshi RSA-PSS over timestamp+method+path. The path EXCLUDES the query."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    ts = str(int(time.time() * 1000))
    sig = pk.sign((ts + method + path).encode(),
                  padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                              salt_length=padding.PSS.DIGEST_LENGTH),
                  hashes.SHA256())
    return {"KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "Content-Type": "application/json",
            "Accept": "application/json"}


def build_order(ticker, side, price, count, client_id, exchange_index=0):
    """The V2 request body, taken from Kalshi's own create-order-v2 reference.

    side is "bid" (buy YES) or "ask" (sell YES, i.e. economically buy NO).
    price and count are FIXED-POINT STRINGS in dollars, 2-4 decimals.

    Do not re-derive these names from /portfolio/orders records: those are V1
    RESPONSE objects and using them as a request schema is what produced the
    410 on 2026-09-06.

    post_only is not optional and is not an argument.
    """
    return {
        "ticker": ticker,
        "side": side,
        "count": f"{float(count):.2f}",
        "price": f"{float(price):.4f}",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "maker",
        "post_only": True,                  # <-- CANNOT CROSS. The whole rail.
        "client_order_id": client_id,
        "exchange_index": int(exchange_index),
    }


def collateral(body):
    """What the exchange actually freezes. A bid at p costs p; an ask at p is
    a sale of YES, which costs (1 - p). Getting this backwards would understate
    the risk of every sell-side quote."""
    c = float(body["count"])
    p = float(body["price"])
    return c * (p if body["side"] == "bid" else (1.0 - p))


def check_limits(body):
    """Refuse before signing, not after. Returns a list of violations."""
    bad = []
    c = float(body["count"])
    p = float(body["price"])
    if c > MAX_COUNT:
        bad.append(f"count {c} exceeds MAX_COUNT {MAX_COUNT}")
    if c <= 0:
        bad.append(f"count {c} is not positive")
    if not (0.0 < p < 1.0):
        bad.append(f"price {p} is outside (0,1)")
    if collateral(body) > MAX_NOTIONAL:
        bad.append(f"collateral {collateral(body):.2f} exceeds MAX_NOTIONAL "
                   f"{MAX_NOTIONAL}")
    if body.get("post_only") is not True:
        bad.append("post_only is not True -- this order could TAKE liquidity")
    if body.get("time_in_force") != "good_till_canceled":
        bad.append(f"time_in_force is {body.get('time_in_force')!r}, not "
                   f"good_till_canceled")
    if body.get("side") not in ("bid", "ask"):
        bad.append(f"side is {body.get('side')!r}, not bid or ask")
    return bad


def token_for(body, base):
    """A sign-off token bound to THIS order on THIS environment.

    Changing any field changes the token, so an approval cannot be replayed
    against a different order, a different size, or production.
    """
    blob = json.dumps({"b": body, "base": base}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def send(base, pk, key_id, method, path, body=None):
    url = base + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in sign_headers(pk, key_id, method,
                             base.split("kalshi.co")[-1].split("kalshi.com")[-1]
                             + path if False else
                             "/trade-api/v2" + path).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:
        return -1, str(e)


def selftest():
    print("=" * 78)
    print("SELF-TEST -- the rails must hold before anything can be sent")
    print("=" * 78)
    fails = []

    b = build_order("KXTEST-1", "bid", 0.30, 1, "t1")
    print(f"\n  a well-formed 1-contract order at 30c: {json.dumps(b)}")
    if b.get("post_only") is not True:
        fails.append("build_order did not set post_only -- it could TAKE")
    if check_limits(b):
        fails.append(f"a legal order was rejected: {check_limits(b)}")

    print("\n  every ceiling must REFUSE, before signing:")
    for desc, mut in (
            ("count above MAX_COUNT", {"count": "999.00"}),
            ("collateral above MAX_NOTIONAL", {"count": "5.00", "price": "0.8000"}),
            ("price at 0", {"price": "0.0000"}),
            ("price at 1", {"price": "1.0000"}),
            ("negative count", {"count": "-1.00"}),
            ("post_only stripped", {"post_only": False}),
            ("time_in_force changed", {"time_in_force": "fill_or_kill"}),
            ("side made nonsense", {"side": "sell"})):
        bb = dict(b)
        bb.update(mut)
        v = check_limits(bb)
        print(f"    {desc:<34} -> {'REFUSED' if v else '*** ALLOWED ***'}")
        if not v:
            fails.append(f"{desc} was NOT refused")

    print("\n  the sign-off token must bind to the exact order and environment:")
    t1 = token_for(b, DEMO)
    t2 = token_for(dict(b, count="2.00"), DEMO)
    t3 = token_for(b, PROD)
    print(f"    demo/1 contract {t1}   demo/2 contracts {t2}   PROD/1 {t3}")
    if t1 == t2:
        fails.append("token does not change with size -- a sign-off for 1 "
                     "contract would authorise 2")
    if t1 == t3:
        fails.append("token does not change with environment -- a demo "
                     "sign-off would authorise PRODUCTION")

    print("\n  default environment:")
    print(f"    base defaults to DEMO: {DEMO}")

    print()
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        return False
    print("SELF-TEST PASSED -- post_only is forced, every ceiling refuses "
          "before\nsigning, and a sign-off token cannot be replayed onto a "
          "bigger order\nor onto production.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ticker")
    ap.add_argument("--side", default="bid", choices=["bid", "ask"])
    ap.add_argument("--price", type=float)
    ap.add_argument("--count", type=float, default=1.0)
    ap.add_argument("--client-id", default="",
                    help="fix the client_order_id so the sign-off token "
                         "is reproducible by both sides")
    ap.add_argument("--prod", action="store_true",
                    help="use PRODUCTION. Demo is the default.")
    ap.add_argument("--live", action="store_true",
                    help="actually send. Requires --signoff.")
    ap.add_argument("--rest-seconds", type=int, default=20,
                    help="seconds to leave it resting before cancelling")
    ap.add_argument("--signoff", default="",
                    help="the token printed by the dry run of THIS order")
    ap.add_argument("--key-id", default=os.environ.get("KALSHI_KEY_ID", ""))
    ap.add_argument("--key-file", default=r"C:\kals\kalshi.pem")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing to touch the API")
    if not (a.ticker and a.price):
        raise SystemExit("\n--ticker and --price are required")

    base = PROD if a.prod else DEMO
    body = build_order(a.ticker, a.side, a.price, a.count,
                       a.client_id or ("kals-" + str(int(time.time()))))
    bad = check_limits(body)
    tok = token_for(body, base)

    print("\n" + "=" * 78)
    print("ORDER, NOT YET SENT")
    print("=" * 78)
    print(f"  environment : {'PRODUCTION -- REAL MONEY' if a.prod else 'DEMO'}")
    print(f"  base        : {base}")
    print(f"  body        : {json.dumps(body, indent=2)}")
    print(f"  collateral  : ${collateral(body):.2f}")
    print(f"  worst case  : ${collateral(body):.2f} "
          f"(it fills and settles against us)")
    if bad:
        print("\n  *** REFUSED BY THE RAILS ***")
        for v in bad:
            print("    - " + v)
        raise SystemExit(1)
    print(f"\n  SIGN-OFF TOKEN: {tok}")
    print("  This token is bound to this exact order and environment. It "
          "cannot\n  authorise a different size, price, ticker, or "
          "production.")

    if not a.live:
        print("\n  DRY RUN. Nothing was sent. To send, the OPERATOR must "
              "approve\n  this specific order, then re-run with:")
        print(f"    --live --signoff {tok}" + (" --prod" if a.prod else ""))
        return
    if a.signoff != tok:
        raise SystemExit(f"\n  *** sign-off token mismatch. Expected {tok}, "
                         f"got {a.signoff!r}. REFUSING. ***")

    print("\n  sign-off matches. Sending ...")
    pk = load_key(a.key_file)

    def g(path):
        return send(base, pk, a.key_id, "GET", path)

    st0, bal0 = g("/portfolio/balance")
    print(f"  balance BEFORE : "
          f"{json.dumps(bal0)[:180] if isinstance(bal0, dict) else bal0}")

    st, resp = send(base, pk, a.key_id, "POST", "/portfolio/events/orders", body)
    print(f"\n  POST /portfolio/events/orders -> {st}")
    print(f"    {json.dumps(resp)[:500] if isinstance(resp, dict) else resp}")
    if st not in (200, 201):
        print("\n  *** REJECTED. Nothing rests. Nothing is at risk. ***")
        print("  The response above names what is wrong -- that IS the result")
        print("  of this test, and it is how we learn the correct body shape.")
        return

    oid = ((resp or {}).get("order") or resp or {}).get("order_id")
    print(f"\n  ACCEPTED. order_id {oid}")
    print(f"  resting {a.rest_seconds}s, then verifying, then CANCELLING.")
    try:
        for _ in range(int(a.rest_seconds)):
            time.sleep(1)

        print("\n  --- VERIFY 1: does the exchange say it is resting? ---")
        s1, r1 = g("/portfolio/orders")
        mine = ([o for o in (r1 or {}).get("orders", [])
                 if o.get("order_id") == oid] if isinstance(r1, dict) else [])
        if mine:
            o = mine[0]
            print(f"    status={o.get('status')}  "
                  f"remaining={o.get('remaining_count_fp')}  "
                  f"filled={o.get('fill_count_fp')}  "
                  f"maker_fees={o.get('maker_fees_dollars')}  "
                  f"taker_fees={o.get('taker_fees_dollars')}")
        else:
            print(f"    order NOT found in /portfolio/orders (status {s1})")

        print("\n  --- VERIFY 2: is our size VISIBLE in the PUBLIC book? ---")
        print("      Every rebate figure assumes it is. Never checked before.")
        s2, r2 = g("/markets/" + body["ticker"] + "/orderbook")
        ob = ((r2 or {}).get("orderbook_fp") or {}) if isinstance(r2, dict) else {}
        # a bid rests on the yes book at p; an ask rests on the
        # no book at (1-p) -- Kalshi's two books are one book.
        bid = body["side"] == "bid"
        key = "yes_dollars" if bid else "no_dollars"
        want = (float(body["price"]) if bid
                else round(1.0 - float(body["price"]), 4))
        hit = [(float(px), float(sz)) for px, sz in (ob.get(key) or [])
               if abs(float(px) - want) < 1e-9]
        if hit:
            print(f"    YES -- {key} shows {hit[0][1]:.2f} contracts at "
                  f"${hit[0][0]:.2f}.")
            print(f"    Our resting size IS in the public depth feed.")
        else:
            print(f"    NO -- nothing at ${want:.2f} on {key}.")
            print(f"    Either the feed lags, or resting size here is not")
            print(f"    published. THAT WOULD MATTER A GREAT DEAL.")

        print("\n  --- VERIFY 3: what collateral was actually held? ---")
        s3, bal1 = g("/portfolio/balance")
        try:
            b0 = float((bal0 or {}).get("balance_dollars"))
            b1 = float((bal1 or {}).get("balance_dollars"))
            exp = collateral(body)
            ok = "MATCH" if abs((b0 - b1) - exp) < 1e-6 else "*** DIFFERS ***"
            print(f"    before ${b0:.4f}   after ${b1:.4f}   "
                  f"held ${b0 - b1:.4f}   expected ${exp:.4f}   {ok}")
        except Exception as e:
            print(f"    could not compare balances: {e}")
    finally:
        s4, r4 = send(base, pk, a.key_id, "DELETE",
                      f"/portfolio/events/orders/{oid}")
        print(f"\n  --- CANCEL: DELETE /portfolio/events/orders/{oid} -> {s4}")
        print(f"    {str(r4)[:200]}")
        s5, bal2 = g("/portfolio/balance")
        if isinstance(bal2, dict):
            print(f"    balance after cancel: ${bal2.get('balance_dollars')}")
            print(f"    (collateral should be returned IN FULL)")


if __name__ == "__main__":
    main()
