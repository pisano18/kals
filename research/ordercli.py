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
# HARD CEILINGS. Not arguments. They differ by environment because the two
# environments carry different consequences: demo money is fake, so the only
# reason to bound demo is to stop a runaway loop, while production is bounded
# to what the operator has actually signed off on.
#
# MAX_NOTIONAL binds on COLLATERAL, not on price x count: an ask at price p
# freezes (1 - p), so a sell quote at 2c ties up 98c per contract. Checking
# the wrong leg would understate every sell-side order.
CEILINGS = {
    # env:  (MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED)
    #  MAX_DEPLOYED is CUMULATIVE collateral across every resting order
    #  plus the one being placed. On a binary that sum IS the maximum
    #  loss. Per-order ceilings never bounded it: a repeg loop at the
    #  permitted S=5 still deploys the whole account (ruin adversary,
    #  2026-09-07).
    # RAISED 2026-09-07 for the gold cutoff test (PREREG_gold.md S5).
    # The cumulative cap IS the maximum loss on a binary: $21 of $65.19.
    # MAX_NOTIONAL MUST BE REACHABLE: at MAX_COUNT=20 the largest
    # possible collateral is 20 x 0.99 = $19.80, so a $20 per-order cap
    # could never fire -- the same dead-ceiling bug the self-test caught
    # on this file at MAX_COUNT=5. $15 binds and still allows a full-size
    # leg priced up to 0.75.
    "prod": (20.0, 15.00, 4, 21.00),
    "demo": (2000.0, 50.00, 12, 50.00),
}
MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED = CEILINGS["prod"]


def set_env(is_prod):
    """Select the ceiling set. Called once, before any order is built."""
    global MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED
    MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED = CEILINGS[
        "prod" if is_prod else "demo"]


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


def send(base, pk, key_id, method, path, body=None, query=None):
    """Sign the PATH ONLY; send path+query.

    Appending the query to the signed string produces
    INCORRECT_API_KEY_SIGNATURE -- a mistake already made once in this project.
    """
    q = "" if not query else "?" + "&".join(f"{k}={v}" for k, v in query.items())
    url = base + path + q
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in sign_headers(pk, key_id, method, "/trade-api/v2" + path).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:
        return -1, str(e)


def resting_orders(base, pk, key_id):
    """Every RESTING order, paged. Returns (list, ok).

    ok=False means the listing FAILED and nothing can be concluded from an
    empty list. A caller that treats "could not read" as "nothing resting" has
    reinvented the silent-cancel bug.
    """
    out, cur, pages = [], None, 0
    while pages < 50:
        q = {"status": "resting", "limit": "200"}
        if cur:
            q["cursor"] = cur
        st, r = send(base, pk, key_id, "GET", "/portfolio/orders", query=q)
        if st != 200 or not isinstance(r, dict):
            return out, False
        out.extend(r.get("orders") or [])
        pages += 1
        cur = r.get("cursor") or r.get("next_cursor")
        if not cur:
            break
    return out, True


def order_collateral(o):
    """Collateral a RESTING order record holds.

    BRANCH ON action/book_side, NOT on `side`. A real record on this account:
        action=sell  book_side=ask  side=yes  yes_px=0.3000  no_px=0.7000
    Branching on `side` returned count x 0.30 where the true reserve for
    selling yes at 0.30 is count x 0.70 -- understating a sell leg by 2.3x.
    A BUY reserves what it pays for its own outcome; a SELL reserves what it
    might owe, i.e. (1 - the price it sold at).
    """
    try:
        c = float(o.get("remaining_count_fp") or o.get("remaining_count") or 0)
    except Exception:
        return 0.0
    if c <= 0:
        return 0.0

    def f(k):
        try:
            return float(o.get(k) or 0)
        except Exception:
            return 0.0

    action = str(o.get("action") or "").lower()
    book = str(o.get("book_side") or "").lower()
    side = str(o.get("side") or "").lower()
    if action == "sell" or (not action and book == "ask" and side == "yes"):
        # selling YES at yes_price: we may owe (1 - yes_price)
        return c * max(0.0, 1.0 - f("yes_price_dollars"))
    # a buy pays for its own outcome side
    return c * (f("yes_price_dollars") if side == "yes"
                else f("no_price_dollars"))


def deployed(base, pk, key_id):
    """TOTAL capital at risk: resting collateral PLUS filled inventory.

    The earlier version summed resting orders only. A FILLED order leaves the
    ?status=resting listing entirely, so the total fell back to ~0 and a
    quoting loop would fund a fresh pair, and another, to the whole balance.
    On a binary the total deployed IS the maximum loss, so this must count
    positions too. Returns (total, ok).
    """
    rest, ok = resting_orders(base, pk, key_id)
    if not ok:
        return 0.0, False
    total = sum(order_collateral(o) for o in rest)
    st, p = send(base, pk, key_id, "GET", "/portfolio/positions")
    if st != 200 or not isinstance(p, dict):
        return total, False
    for x in p.get("market_positions", []):
        try:
            total += abs(float(x.get("market_exposure_dollars") or 0))
        except Exception:
            pass
    return total, True


def amend(base, pk, key_id, oid, body):
    """Atomically move a resting order to a new price.

    POST /portfolio/events/orders/{id}/amend. Replaces cancel-then-place, which
    leaves a gap where that side is unquoted, and place-then-cancel, which
    briefly holds TWO orders on one side and doubles the reserve (the documented
    ruin path). Amend has neither failure mode.

    Queue position is forfeited on a price change -- but cancel-then-place
    forfeits it too, so nothing is lost.
    """
    return send(base, pk, key_id, "POST",
                f"/portfolio/events/orders/{oid}/amend", body=body)


def cancel(base, pk, key_id, oid, exchange_index):
    """Cancel, and VERIFY it actually cancelled.

    A 404 here used to be printed and ignored. It must not be: an order left
    resting is real exposure. Retries without the query once, then reports
    loudly if the order is still resting.
    """
    st, r = send(base, pk, key_id, "DELETE",
                 f"/portfolio/events/orders/{oid}",
                 query={"exchange_index": int(exchange_index)})
    if st != 200:
        st, r = send(base, pk, key_id, "DELETE",
                     f"/portfolio/events/orders/{oid}")
    # THE LISTING LAGS THE CANCEL. Observed directly 2026-09-07: a cancel
    # returned 200 while ?status=resting still showed the order seconds later,
    # and a strict one-shot check aborted a live run on that lag alone.
    # So poll: a cancel is only "still resting" if it PERSISTS.
    still = None
    for attempt in range(4):
        rest, ok = resting_orders(base, pk, key_id)
        if not ok:
            still = None             # UNKNOWN; never report "verified"
        elif any(o.get("order_id") == oid for o in rest):
            still = True
        else:
            return st, r, False      # gone: confirmed cancelled
        if attempt < 3:
            time.sleep(0.6)
    return st, r, still


# --- CASH POOLS (added 2026-09-26) -------------------------------------------
# Kalshi keeps cash per exchange index ("pool"); an order draws only on its own
# market's pool. These two calls move the operator's own cash between his own
# pools: no market, no price, no fill -- the account total must not change.
#   POST /portfolio/target_balance_allocation  {"allocations": []} = automatic
#       rebalancing OFF (Kalshi docs: "Passing an empty allocations array
#       disables automatic rebalancing.")
#   POST /portfolio/intra_exchange_instance_transfer  amount in CENTICENTS
#       (1/100 of a cent: $1 = 10,000). Cross-pool transfers run "in up to
#       three non-atomic phases", so the total is re-read afterwards.
POOLS = (0, 1, 2, 3)


def build_allocation_off():
    return {"allocations": [], "resting_margin_reservation": "sum"}


def build_transfer(amount_dollars, from_pool, to_pool):
    """Dollars in, centicents out -- rounded DOWN so we never ask for more
    than the pool holds (139.1532 -> 1391532)."""
    cc = int(round(float(amount_dollars) * 10000.0, 6) // 1)
    return {"source": "event_contract", "destination": "event_contract",
            "amount": cc,
            "source_exchange_shard": int(from_pool),
            "destination_exchange_shard": int(to_pool),
            "source_subaccount": 0, "destination_subaccount": 0}


def check_transfer(body, pool_balance_dollars):
    """Refuse before signing. pool_balance_dollars = the SOURCE pool's cash as
    read just now (None = could not read -> refuse)."""
    bad = []
    if body.get("source") != "event_contract" or \
            body.get("destination") != "event_contract":
        bad.append("only event_contract -> event_contract (never margined)")
    if body.get("source_subaccount") != 0 or \
            body.get("destination_subaccount") != 0:
        bad.append("only the primary account (subaccount 0)")
    s, d = body.get("source_exchange_shard"), body.get("destination_exchange_shard")
    if s not in POOLS or d not in POOLS:
        bad.append(f"pool {s}->{d} not in {POOLS}")
    if s == d:
        bad.append("source and destination pool are the same")
    a = body.get("amount")
    if not isinstance(a, int) or a <= 0:
        bad.append(f"amount {a!r} is not a positive whole number of centicents")
    if pool_balance_dollars is None:
        bad.append("source pool balance unreadable -- refusing blind")
    elif isinstance(a, int) and a > int(round(pool_balance_dollars * 10000)):
        bad.append(f"amount ${a / 10000:.4f} exceeds the source pool's "
                   f"${pool_balance_dollars:.4f}")
    return bad


def pool_balances(bal):
    """{pool: dollars} from a /portfolio/balance body, or None."""
    try:
        return {int(x["exchange_index"]): float(x["balance"])
                for x in bal["balance_breakdown"]}
    except Exception:
        return None


def pools_main(a):
    """--pools-off and/or --move-dollars. PRODUCTION only (it is the
    operator's own cash; demo keys cannot see it). One token covers the
    exact pair of calls printed."""
    base = PROD
    pk = load_key(a.key_file)
    st, bal = send(base, pk, a.key_id, "GET", "/portfolio/balance")
    pools = pool_balances(bal) if st == 200 else None
    st2, alloc = send(base, pk, a.key_id, "GET",
                      "/portfolio/target_balance_allocation")
    print(f"  pools now   : {pools}   total "
          f"${(bal or {}).get('balance_dollars') if isinstance(bal, dict) else '?'}")
    print(f"  auto split  : {alloc if st2 == 200 else ('unreadable', st2)}")
    steps = []
    if a.pools_off:
        steps.append(("POST", "/portfolio/target_balance_allocation",
                      build_allocation_off()))
    if a.move_dollars is not None:
        amt = (pools or {}).get(a.from_pool) if a.move_dollars == "all" \
            else float(a.move_dollars)
        if amt is None:
            raise SystemExit("  *** could not read the source pool. REFUSING. ***")
        tb = build_transfer(amt, a.from_pool, a.to_pool)
        bad = check_transfer(tb, (pools or {}).get(a.from_pool))
        if bad:
            print("\n  *** REFUSED BY THE RAILS ***")
            for v in bad:
                print("    - " + v)
            raise SystemExit(1)
        steps.append(("POST", "/portfolio/intra_exchange_instance_transfer", tb))
    if not steps:
        raise SystemExit("  nothing asked: pass --pools-off and/or --move-dollars")
    tok = token_for({"pool_steps": steps}, base)
    print("\n  STEPS, NOT YET SENT (production, the operator's own cash; "
          "no market risk):")
    for m, p, b in steps:
        print(f"    {m} {p} {json.dumps(b)}")
    print(f"\n  SIGN-OFF TOKEN: {tok}")
    if not a.live:
        print(f"  DRY RUN. To send: add --live --signoff {tok}")
        return
    if a.signoff != tok:
        raise SystemExit(f"  *** sign-off token mismatch. Expected {tok}. "
                         f"REFUSING. ***")
    total0 = float(bal["balance_dollars"])
    for m, p, b in steps:
        st, r = send(base, pk, a.key_id, m, p, b)
        print(f"  {m} {p} -> {st} {r}")
        if st not in (200, 201):
            raise SystemExit("  *** REJECTED; later steps NOT sent. ***")
    time.sleep(5)
    st, bal1 = send(base, pk, a.key_id, "GET", "/portfolio/balance")
    st2, alloc1 = send(base, pk, a.key_id, "GET",
                       "/portfolio/target_balance_allocation")
    print(f"\n  AFTER pools : {pool_balances(bal1)}   total "
          f"${(bal1 or {}).get('balance_dollars')}")
    print(f"  AFTER split : {alloc1}")
    try:
        d = float(bal1["balance_dollars"]) - total0
        print(f"  total moved by ${d:+.4f} "
              f"({'OK: unchanged' if abs(d) < 0.01 else '*** CHECK: a bet settled or the transfer is mid-phase ***'})")
    except Exception as e:
        print(f"  could not compare totals: {e}")


# --- REWARD-REST MODE (added 2026-09-26) -------------------------------------
# The reward test (HANDOFF P2, operator: "Run the reward test"): a few large
# BUY orders at 1c or less, resting for days on quiet non-crypto markets that
# carry a Kalshi liquidity program, to learn whether Kalshi pays THIS account.
# A 1c buy can lose only what it cost, so the ceilings below ARE the maximum
# loss. Unlike the test mode above, these orders are NOT cancelled on exit:
# resting for days is the point. `--reward-cancel` takes them down.
#   buy YES at p  -> side "bid", price p        (costs p a contract)
#   buy NO  at p  -> side "ask", price 1 - p    (costs p a contract)
REWARD_MAX_PRICE = 0.01         # never pay more than 1c a contract
REWARD_MAX_COUNT = 1000.0
REWARD_MAX_ORDER = 10.00        # $ per order (1,000 x 1c)
REWARD_MAX_TOTAL = 60.00        # $ across every reward order AND fill
REWARD_MAX_ORDERS = 4
REWARD_PREFIX = "kals-lip-"
REWARD_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                          "results", "lip_orders.jsonl")
BOT_POOL = 2                    # crypto & commodities: the live bots' pool


def build_reward_order(ticker, buy, price, count, exchange_index, day):
    """buy is 'yes' or 'no'; price is what we PAY per contract (<= 1c).
    The client id is derived from the order and the UTC day, so the dry run
    and the live run build the identical body (same token), and the same
    order cannot be placed twice in one day (Kalshi rejects a repeated id)."""
    side = "bid" if buy == "yes" else "ask"
    px = float(price) if buy == "yes" else round(1.0 - float(price), 4)
    h = hashlib.sha256(f"{ticker}|{buy}|{price}|{count}|{day}".encode())
    b = build_order(ticker, side, px, count,
                    REWARD_PREFIX + h.hexdigest()[:12], exchange_index)
    return b


def reward_cost(body):
    """What the order costs a contract, whatever side it is on."""
    p = float(body["price"])
    return p if body["side"] == "bid" else round(1.0 - p, 4)


def check_reward(body, market_exi, has_program, open_orders, at_risk):
    """Refuse before signing. open_orders = reward orders resting now;
    at_risk = $ in resting reward orders plus reward-market positions
    (None = unreadable -> refuse)."""
    bad = []
    c = float(body["count"])
    cost = reward_cost(body)
    if body.get("post_only") is not True:
        bad.append("post_only is not True")
    if body.get("time_in_force") != "good_till_canceled":
        bad.append("time_in_force is not good_till_canceled")
    if body.get("side") not in ("bid", "ask"):
        bad.append("side is not bid/ask")
    if not (0.0 < cost <= REWARD_MAX_PRICE + 1e-9):
        bad.append(f"pays {cost * 100:.2f}c a contract; reward orders pay "
                   f"at most {REWARD_MAX_PRICE * 100:.0f}c")
    if not (0.0 < c <= REWARD_MAX_COUNT):
        bad.append(f"count {c:g} outside (0, {REWARD_MAX_COUNT:g}]")
    if c * cost > REWARD_MAX_ORDER + 1e-9:
        bad.append(f"order costs ${c * cost:.2f} > ${REWARD_MAX_ORDER:.2f}")
    if market_exi is None:
        bad.append("market's pool unreadable -- refusing blind")
    elif int(market_exi) == BOT_POOL:
        bad.append("market is in pool 2 (the live bots' pool) -- refused")
    if int(body.get("exchange_index", -1)) != (
            -2 if market_exi is None else int(market_exi)):
        bad.append("order's exchange_index differs from the market's")
    if not has_program:
        bad.append("no active liquidity program on this market")
    if open_orders is None or at_risk is None:
        bad.append("could not read our reward orders/positions -- refusing")
    else:
        if open_orders >= REWARD_MAX_ORDERS:
            bad.append(f"{open_orders} reward orders already resting "
                       f">= {REWARD_MAX_ORDERS}")
        if at_risk + c * cost > REWARD_MAX_TOTAL + 1e-9:
            bad.append(f"reward money at risk ${at_risk + c * cost:.2f} would "
                       f"exceed ${REWARD_MAX_TOTAL:.2f}")
    return bad


def reward_log(rec):
    rec = dict(rec, t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(REWARD_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def reward_state(base, pk, key_id):
    """(our resting reward orders, $ at risk, tickers) or (None, None, set())
    when unreadable. $ at risk = resting reward-order cost + exposure in any
    market we have ever sent a reward order to (from the log)."""
    rest, ok = resting_orders(base, pk, key_id)
    if not ok:
        return None, None, set()
    mine = [o for o in rest
            if str(o.get("client_order_id") or "").startswith(REWARD_PREFIX)]
    tks = set(o.get("ticker") for o in mine)
    try:
        with open(REWARD_LOG, encoding="utf-8") as f:
            for ln in f:
                r = json.loads(ln)
                if r.get("ticker"):
                    tks.add(r["ticker"])
    except FileNotFoundError:
        pass
    risk = sum(order_collateral(o) for o in mine)
    st, p = send(base, pk, key_id, "GET", "/portfolio/positions",
                 query={"limit": "1000"})
    if st != 200 or not isinstance(p, dict):
        return None, None, tks
    for x in p.get("market_positions", []):
        if x.get("ticker") in tks:
            try:
                risk += abs(float(x.get("market_exposure_dollars") or 0))
            except Exception:
                pass
    return mine, risk, tks


def reward_main(a):
    base = PROD
    pk = load_key(a.key_file)
    if a.reward_status or a.reward_cancel:
        mine, risk, tks = reward_state(base, pk, a.key_id)
        if mine is None:
            raise SystemExit("  *** could not read orders/positions ***")
        st, bal = send(base, pk, a.key_id, "GET", "/portfolio/balance")
        print(f"  pools: {pool_balances(bal)}  total "
              f"${(bal or {}).get('balance_dollars')}")
        print(f"  reward orders resting: {len(mine)}; money at risk "
              f"${risk:.2f}")
        for o in mine:
            print(f"    {o.get('order_id')} {o.get('ticker')} "
                  f"{o.get('side')} {o.get('action')} "
                  f"yes {o.get('yes_price_dollars')} "
                  f"left {o.get('remaining_count_fp')} "
                  f"filled {o.get('fill_count_fp')}")
        st, pp = send(base, pk, a.key_id, "GET", "/portfolio/positions",
                      query={"limit": "1000"})
        for x in (pp or {}).get("market_positions", []) \
                if isinstance(pp, dict) else []:
            if x.get("ticker") in tks:
                print(f"    position {x.get('ticker')} "
                      f"{x.get('position_fp')} exposure "
                      f"${x.get('market_exposure_dollars')}")
        if a.reward_cancel:
            for o in mine:
                if a.reward_cancel not in ("all", o.get("order_id")):
                    continue
                s, r, still = cancel(base, pk, a.key_id, o.get("order_id"),
                                     o.get("exchange_index") or 0)
                print(f"  CANCEL {o.get('order_id')} -> {s}; still resting: "
                      f"{still}")
                reward_log({"kind": "cancel", "order_id": o.get("order_id"),
                            "ticker": o.get("ticker"), "status": s,
                            "still": still})
        return
    if not (a.ticker and a.buy):
        raise SystemExit("  --reward needs --ticker and --buy yes|no")
    st, m = send(base, pk, a.key_id, "GET", "/markets/" + a.ticker)
    mk = (m or {}).get("market") or {} if isinstance(m, dict) else {}
    exi = mk.get("exchange_index")
    st2, ip = send(base, pk, a.key_id, "GET", "/incentive_programs",
                   query={"status": "active", "type": "liquidity",
                          "limit": "10000"})   # no per-market filter exists
    progs = [p for p in ((ip or {}).get("incentive_programs") or [])
             if isinstance(ip, dict) and p.get("market_ticker") == a.ticker
             and p.get("incentive_type") == "liquidity"]
    day = time.strftime("%Y-%m-%d", time.gmtime())
    body = build_reward_order(a.ticker, a.buy, a.reward_price, a.count,
                              exi if exi is not None else -2, day)
    mine, risk, _ = reward_state(base, pk, a.key_id)
    bad = check_reward(body, exi, bool(progs),
                       None if mine is None else len(mine), risk)
    tok = token_for(body, base)
    print("\n  REWARD ORDER, NOT YET SENT (production, real money):")
    print(f"    market  : {a.ticker}  pool {exi}  status {mk.get('status')}  "
          f"closes {mk.get('close_time')}")
    for p in progs:
        print(f"    program : ${p['period_reward'] / 10000:.2f} "
              f"{p['start_date']} -> {p['end_date']}  target "
              f"{p['target_size_fp']}  discount {p['discount_factor_bps']}bps")
    print(f"    body    : {json.dumps(body)}")
    print(f"    buys {a.buy.upper()} at {reward_cost(body) * 100:.1f}c x "
          f"{float(body['count']):g} = worst case "
          f"${reward_cost(body) * float(body['count']):.2f}; reward money "
          f"already at risk ${risk if risk is not None else float('nan'):.2f}")
    if bad:
        print("\n  *** REFUSED BY THE RAILS ***")
        for v in bad:
            print("    - " + v)
        raise SystemExit(1)
    print(f"\n  SIGN-OFF TOKEN: {tok}")
    if not a.live:
        print(f"  DRY RUN. To send: add --live --signoff {tok}")
        return
    if a.signoff != tok:
        raise SystemExit(f"  *** sign-off token mismatch. Expected {tok}. "
                         f"REFUSING. ***")
    st, resp = send(base, pk, a.key_id, "POST", "/portfolio/events/orders",
                    body)
    oid = (((resp or {}).get("order") or resp or {}).get("order_id")
           if isinstance(resp, dict) else None)
    print(f"  POST /portfolio/events/orders -> {st} {str(resp)[:300]}")
    reward_log({"kind": "place", "status": st, "order_id": oid,
                "ticker": a.ticker, "buy": a.buy, "body": body,
                "programs": [{k: p.get(k) for k in (
                    "id", "period_reward", "start_date", "end_date",
                    "target_size_fp", "discount_factor_bps")}
                    for p in progs]})
    if st not in (200, 201):
        print("  *** REJECTED. Nothing rests. ***")
        return
    print(f"  RESTING. order_id {oid}. It is NOT cancelled on exit; "
          f"take it down with --reward-cancel {oid} (or all).")


def selftest():
    set_env(True)
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
            ("count above MAX_COUNT", {"count": f"{MAX_COUNT * 2:.2f}"}),
            ("collateral above MAX_NOTIONAL",
             {"count": f"{MAX_COUNT:.2f}",
              "price": f"{min(0.99, MAX_NOTIONAL / MAX_COUNT * 1.5):.4f}"}),
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


    print("\n  the CUMULATIVE cap must bind when per-order ceilings do not:")
    # sized off MAX_DEPLOYED so this keeps testing when the ceiling moves
    half = MAX_DEPLOYED / 2.0
    fake_rest = [{"side": "yes", "remaining_count_fp": f"{half / 0.60:.2f}",
                  "yes_price_dollars": "0.6000", "no_price_dollars": "0.4000"},
                 {"side": "no", "remaining_count_fp": f"{half / 0.30:.2f}",
                  "yes_price_dollars": "0.7000", "no_price_dollars": "0.3000"}]
    dep = sum(order_collateral(o) for o in fake_rest)
    print(f"    two resting orders hold ${dep:.2f} against MAX_DEPLOYED "
          f"${MAX_DEPLOYED:.2f}")
    if abs(dep - MAX_DEPLOYED) > 0.02:
        fails.append(f"order_collateral summed {dep:.4f}, expected "
                     f"{MAX_DEPLOYED:.4f} -- a leg is priced off the wrong side")
    cnt = max(0.01, min(MAX_COUNT, (0.05 * MAX_DEPLOYED) / 0.30))
    small = build_order("KXTEST-1", "bid", 0.30, cnt, "t2")
    if check_limits(small):
        fails.append(f"a ${collateral(small):.2f} order failed the per-order "
                     f"rails: {check_limits(small)}")
    if dep + collateral(small) > MAX_DEPLOYED:
        print(f"    + a ${collateral(small):.2f} order -> "
              f"${dep + collateral(small):.2f} > ${MAX_DEPLOYED:.2f} "
              f"-> REFUSED (correct)")
    else:
        fails.append(f"cumulative cap did NOT bind at "
                     f"${dep + collateral(small):.2f} vs ${MAX_DEPLOYED:.2f}")

    print("\n  a FAILED listing must read as UNKNOWN, never as 'nothing resting':")
    class _Fail:
        pass
    def _bad_send(*a, **k):
        return 500, "boom"
    _real = globals()["send"]
    globals()["send"] = _bad_send
    try:
        lst, ok = resting_orders("x", None, "k")
    finally:
        globals()["send"] = _real
    print(f"    send() returning 500 -> resting_orders ok={ok}, "
          f"{len(lst)} orders")
    if ok:
        fails.append("resting_orders reported ok=True on a failed listing")

    print("\n  cash-pool transfer rails:")
    tb = build_transfer(139.1532, 0, 2)
    if tb["amount"] != 1391532:
        fails.append(f"139.1532 dollars -> {tb['amount']} centicents, "
                     f"expected 1391532")
    if check_transfer(tb, 139.1532):
        fails.append(f"a legal whole-pool move was refused: "
                     f"{check_transfer(tb, 139.1532)}")
    for desc, mut, pb in (
            ("more than the pool holds", {"amount": 1391533}, 139.1532),
            ("same pool", {"destination_exchange_shard": 0}, 139.1532),
            ("to margined", {"destination": "margined"}, 139.1532),
            ("a subaccount", {"destination_subaccount": 1}, 139.1532),
            ("zero amount", {"amount": 0}, 139.1532),
            ("unknown pool", {"destination_exchange_shard": 7}, 139.1532),
            ("pool unreadable", {}, None)):
        bb = dict(tb)
        bb.update(mut)
        v = check_transfer(bb, pb)
        print(f"    {desc:<34} -> {'REFUSED' if v else '*** ALLOWED ***'}")
        if not v:
            fails.append(f"transfer: {desc} was NOT refused")
    if build_allocation_off().get("allocations") != []:
        fails.append("allocation-off body is not an empty list")
    if token_for({"pool_steps": [1]}, PROD) == token_for({"pool_steps": [2]}, PROD):
        fails.append("pool token does not change with the steps")

    print("\n  reward-rest rails:")
    ry = build_reward_order("KXTEST-1", "yes", 0.01, 1000, 0, "2026-09-26")
    rn = build_reward_order("KXTEST-1", "no", 0.01, 1000, 0, "2026-09-26")
    if ry["side"] != "bid" or float(ry["price"]) != 0.01 or \
            rn["side"] != "ask" or float(rn["price"]) != 0.99:
        fails.append(f"reward sides wrong: yes {ry['side']}@{ry['price']} "
                     f"no {rn['side']}@{rn['price']}")
    if abs(reward_cost(rn) - 0.01) > 1e-9:
        fails.append("a NO buy at 1c is not costed at 1c")
    for b_ in (ry, rn):
        if check_reward(b_, 0, True, 0, 0.0):
            fails.append(f"legal reward order refused: "
                         f"{check_reward(b_, 0, True, 0, 0.0)}")
    if ry["client_order_id"] != build_reward_order(
            "KXTEST-1", "yes", 0.01, 1000, 0, "2026-09-26")["client_order_id"]:
        fails.append("reward client id is not reproducible (token would "
                     "never match)")
    for desc, b_, exi, prog, n_open, risk in (
            ("pays 2c", build_reward_order("KXTEST-1", "yes", 0.02, 100, 0,
                                           "d"), 0, True, 0, 0.0),
            ("NO buy paying 2c", build_reward_order("KXTEST-1", "no", 0.02,
                                                    100, 0, "d"), 0, True, 0,
             0.0),
            ("1,001 contracts", build_reward_order("KXTEST-1", "yes", 0.01,
                                                   1001, 0, "d"), 0, True, 0,
             0.0),
            ("in the bots' pool 2", build_reward_order(
                "KXTEST-1", "yes", 0.01, 1000, 2, "d"), 2, True, 0, 0.0),
            ("pool unreadable", ry, None, True, 0, 0.0),
            ("exchange_index mismatch", ry, 3, True, 0, 0.0),
            ("no program", ry, 0, False, 0, 0.0),
            ("4 already resting", ry, 0, True, 4, 0.0),
            ("total over $60", ry, 0, True, 1, 55.0),
            ("orders unreadable", ry, 0, True, None, None),
            ("post_only stripped", dict(ry, post_only=False), 0, True, 0,
             0.0)):
        v = check_reward(b_, exi, prog, n_open, risk)
        print(f"    {desc:<34} -> {'REFUSED' if v else '*** ALLOWED ***'}")
        if not v:
            fails.append(f"reward: {desc} was NOT refused")

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
    ap.add_argument("--pools-off", action="store_true",
                    help="turn Kalshi's automatic cash split OFF (prod)")
    ap.add_argument("--move-dollars",
                    help="move cash between pools (prod): dollars or 'all'")
    ap.add_argument("--from-pool", type=int, default=0)
    ap.add_argument("--to-pool", type=int, default=2)
    ap.add_argument("--reward", action="store_true",
                    help="place ONE reward-rest order (prod, <=1c, rests "
                         "until --reward-cancel)")
    ap.add_argument("--buy", choices=["yes", "no"])
    ap.add_argument("--reward-price", type=float, default=0.01)
    ap.add_argument("--reward-status", action="store_true")
    ap.add_argument("--reward-cancel", default="",
                    help="order id, or 'all' reward orders")
    a = ap.parse_args()
    if not a.key_id:
        a.key_id = "5163259c-ecb0-4966-9053-0d2776cf061e"   # kauth.KEY_ID

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing to touch the API")
    if a.pools_off or a.move_dollars is not None:
        return pools_main(a)
    if a.reward or a.reward_status or a.reward_cancel:
        return reward_main(a)
    if not (a.ticker and a.price):
        raise SystemExit("\n--ticker and --price are required")

    set_env(bool(a.prod))
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

    rest, ok = resting_orders(base, pk, a.key_id)
    if not ok:
        raise SystemExit("  *** could not read resting orders; refusing "
                         "to place blind ***")
    deployed = sum(order_collateral(o) for o in rest)
    print(f"  resting now   : {len(rest)} order(s) holding "
          f"${deployed:.4f}; this order adds ${collateral(body):.4f}")
    if len(rest) >= MAX_OPEN_ORDERS:
        raise SystemExit(f"  *** {len(rest)} orders already resting >= "
                         f"MAX_OPEN_ORDERS {MAX_OPEN_ORDERS}. REFUSING. ***")
    if deployed + collateral(body) > MAX_DEPLOYED:
        raise SystemExit(f"  *** cumulative collateral "
                         f"${deployed + collateral(body):.4f} would exceed "
                         f"MAX_DEPLOYED ${MAX_DEPLOYED:.2f}. On a binary that "
                         f"sum IS the maximum loss. REFUSING. ***")

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
        s4, r4, still = cancel(base, pk, a.key_id, oid,
                               body.get("exchange_index", 0))
        print(f"\n  --- CANCEL {oid} -> {s4}")
        print(f"    {str(r4)[:200]}")
        if still is None:
            print("    *** COULD NOT READ THE ORDER LIST. CANCEL STATUS "
                  "UNKNOWN. CHECK BY HAND. ***")
        elif still:
            print("    *** THE ORDER IS STILL RESTING. CANCEL IT BY "
                  "HAND. ***")
        else:
            print("    verified against the paged status=resting list: "
                  "no longer resting.")
        s5, bal2 = g("/portfolio/balance")
        if isinstance(bal2, dict):
            print(f"    balance after cancel: ${bal2.get('balance_dollars')}")
            print(f"    (collateral should be returned IN FULL)")


if __name__ == "__main__":
    main()
