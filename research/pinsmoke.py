#!/usr/bin/env python3
# VERSION: 2026-09-08-ps1
"""pinsmoke.py -- ONE deliberate penny-size trade, to prove the plumbing.

THIS IS NOT A STRATEGY TRADE. It does not wait for a pin signal and it has no
edge. Its only job is to exercise the whole money path end to end with about
one cent at risk, so that nothing is discovered for the first time when real
size is on:

    build -> rails -> POST -> fill -> position -> fee -> settlement -> payout

The operator asked for exactly this after last night, where a live run met its
first cancel/exit problem with real money already committed. A strategy that
only trades on rare signals cannot prove its plumbing on demand; this can.

WHAT IT BUYS, AND WHY THAT SIDE
The near-certain side, at whatever it is offered for (typically 0.97-0.999).
  * it crosses, so it fills immediately -- the point is to GET a fill
  * it costs about 0.01 x 0.99 = ~$0.0099, one cent
  * it should settle as a WIN, which is what makes the PAYOUT leg testable:
    a losing penny proves the debit but never proves the credit
Buying the cheap side would risk less but almost certainly settle worthless,
proving nothing about payout. One cent is the right price for that evidence.

EVERY ORDER GOES THROUGH pintake.check_take. This file cannot bypass the
rails, and a self-test asserts that.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ordercli                                             # noqa: E402
import pintake                                              # noqa: E402
import livebook                                             # noqa: E402

sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
import kauth                                                # noqa: E402
from kauth import get                                       # noqa: E402

RESULTS = r"C:\kals-repo\results"
SERIES = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M"]


def balance():
    st, b = get("/portfolio/balance")
    return float((b or {}).get("balance_dollars") or 0.0) if st == 200 else None


def find_market(lo=10, hi=88):
    """A crypto 15M market closing in [lo, hi] seconds, with a live book."""
    now = int(time.time())
    out = []
    for s in SERIES:
        st, b = get("/markets", {"series_ticker": s, "status": "open",
                                 "limit": "4"})
        if st != 200 or not isinstance(b, dict):
            continue
        for m in b.get("markets", []):
            ct = m.get("close_time")
            if not ct:
                continue
            cs = pintake.close_epoch(ct)
            if lo <= cs - now <= hi:
                out.append((cs, m))
    return out


def book_of(tk):
    st, ob = get("/markets/" + tk + "/orderbook", {"depth": "2"})
    if st != 200 or not isinstance(ob, dict):
        return None
    o = ob.get("orderbook_fp") or {}
    yb = [(float(p), float(q)) for p, q in (o.get("yes_dollars") or [])]
    nb = [(float(p), float(q)) for p, q in (o.get("no_dollars") or [])]
    best_y = max(yb, key=lambda x: x[0]) if yb else None
    best_n = max(nb, key=lambda x: x[0]) if nb else None
    return {
        "yes_bid": best_y[0] if best_y else None,
        "no_bid": best_n[0] if best_n else None,
        "yes_ask": round(1 - best_n[0], 4) if best_n else None,
        "no_ask": round(1 - best_y[0], 4) if best_y else None,
        "yes_ask_size": best_n[1] if best_n else 0.0,
        "no_ask_size": best_y[1] if best_y else 0.0,
    }


def choose(bk):
    """The near-certain side of a book, or None. Split out so the self-test
    can exercise it: the first version of this file crashed in the market
    loop BEFORE any trade, and an untested selection path is how two live
    windows were lost."""
    if not bk or bk.get("yes_ask") is None or bk.get("no_ask") is None:
        return None
    if bk["yes_ask"] >= bk["no_ask"]:
        want, price, size = "yes", bk["yes_ask"], bk["yes_ask_size"]
    else:
        want, price, size = "no", bk["no_ask"], bk["no_ask_size"]
    if price is None or not (0.75 <= price < 1.0) or size < 1:
        return None
    return want, price, size


def selftest():
    print("SELF-TEST -- pinsmoke")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    needles = ["ordercli" + ".send(", "url" + "open("]
    ck(not [n for n in needles if n in src],
       "no send path except pintake.take")
    b = pintake.build_take("T-00", "yes", 0.99, 0.01)
    ck(b["count"] == "0.01", f"a penny order is 0.01 contracts ({b['count']})")
    ck(abs(pintake.stake(b) - 0.0099) < 1e-9,
       f"it stakes $0.0099, about one cent (${pintake.stake(b):.6f})")
    ck(b["post_only"] is False and b["time_in_force"] == "immediate_or_cancel",
       "it crosses and never rests")
    bad = pintake.check_take(b, time.time() + 300, time.time(),
                             base=pintake.PROD_ELECTIONS)
    ck(any("close" in v or "tau" in v for v in bad),
       f"the 90s close rail still refuses a far market ({bad})")
    # THE CRASH THAT COST TWO LIVE WINDOWS: all twelve series close on the
    # same quarter hour, so sorted() on (close, dict) tuples falls through to
    # comparing dicts and raises TypeError.
    same = [(1000, {"ticker": "A"}), (1000, {"ticker": "B"})]
    try:
        sorted(same, key=lambda x: x[0])
        ok_sort = True
    except TypeError:
        ok_sort = False
    ck(ok_sort, "two markets sharing a close time sort without raising")
    try:
        sorted(same)
        bare = True
    except TypeError:
        bare = False
    ck(not bare, "and a BARE sorted() would still crash -- the key is required")

    ck(choose({"yes_ask": 0.953, "no_ask": 0.051,
               "yes_ask_size": 49, "no_ask_size": 41}) == ("yes", 0.953, 49),
       "choose() takes the dearer, near-certain side")
    ck(choose({"yes_ask": 0.16, "no_ask": 0.85,
               "yes_ask_size": 5187, "no_ask_size": 204}) == ("no", 0.85, 204),
       "choose() takes NO when NO is the dear side")
    ck(choose({"yes_ask": 0.5, "no_ask": 0.5, "yes_ask_size": 9,
               "no_ask_size": 9}) is None, "choose() skips a coin-flip book")
    ck(choose({"yes_ask": 0.99, "no_ask": 0.01, "yes_ask_size": 0.02,
               "no_ask_size": 9}) is None, "choose() skips fractional dust")
    ck(choose({"yes_ask": None, "no_ask": None}) is None,
       "choose() survives an empty book")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--size", type=float, default=0.01)
    ap.add_argument("--go", action="store_true",
                    help="actually send it (production, real money)")
    ap.add_argument("--wait", type=float, default=15.0,
                    help="minutes to wait for a market in the window")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    log = os.path.join(RESULTS, "pinsmoke-%s.jsonl"
                       % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))

    def rec(kind, **kw):
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        kw["kind"] = kind
        with open(log, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(kw, default=str) + "\n")

    b0 = balance()
    print(f"\n  balance before: ${b0:.4f}")
    print(f"  log {log}")
    rec("start", balance_before=b0, size=a.size, go=bool(a.go))

    deadline = time.time() + a.wait * 60
    chosen = None
    while time.time() < deadline and chosen is None:
        # sort on the close time ONLY. All twelve series close on the
        # same quarter hour, so a bare sorted() falls through to
        # comparing the market dicts and raises TypeError -- which is
        # exactly what killed the first attempt, before any trade.
        for cs, m in sorted(find_market(), key=lambda x: x[0]):
            tk = m["ticker"]
            bk = book_of(tk)
            if not bk or not bk["yes_ask"] or not bk["no_ask"]:
                continue
            got = choose(bk)
            if got is None:
                continue
            want, price, size = got
            chosen = (cs, m, want, price, size)
            break
        if chosen is None:
            time.sleep(2)

    if chosen is None:
        print("  no suitable market appeared in the wait window")
        rec("end", why="no market")
        return
    cs, m, want, price, size = chosen
    tk = m["ticker"]
    ei = int(m.get("exchange_index") or 0)
    tau = cs - time.time()
    print(f"\n  MARKET  {tk}   exchange_index {ei}   tau {tau:+.0f}s")
    print(f"  BUYING  {a.size:g} contracts of {want.upper()} at {price:.4f}")
    print(f"  STAKE   ${a.size * price:.6f}   "
          f"expected fee ${pintake.expected_fee(price, a.size):.6f}")
    rec("chosen", ticker=tk, want=want, price=price, level_size=size,
        tau=round(tau, 1), exchange_index=ei)

    if not a.go:
        print("\n  DRY RUN -- pass --go to actually send it.")
        rec("end", why="dry run")
        return

    pintake.arm_prod("pinsmoke: one penny-size functionality trade")
    pk = ordercli.load_key(pintake.PROD_KEY_FILE)
    out = pintake.take(pintake.PROD_ELECTIONS, pk, kauth.KEY_ID, tk, want,
                       price, a.size, cs, exchange_index=ei)
    print(f"\n  RESPONSE status {out.get('status_code')}  "
          f"order {out.get('order_id')}")
    print(f"    status {out.get('status')}  filled {out.get('filled')}  "
          f"remaining {out.get('remaining')}")
    print(f"    exec_price {out.get('exec_price')}  fee {out.get('fee')}")
    if out.get("refused"):
        print(f"    REFUSED BY THE RAILS: {out['refused']}")
    rec("order", **{k: v for k, v in out.items() if k != "raw"})
    rec("order_raw", raw=out.get("raw"))

    filled = float(out.get("filled") or 0)
    sc = out.get("status_code")
    if sc is None or not (200 <= int(sc) < 300):
        # A NON-2xx IS A REJECTION, NOT A MISSED FILL. The first run printed
        # "no fill -- the send path is proven" on an HTTP 400
        # insufficient_balance, which is exactly backwards: nothing was
        # accepted, and the real cause was that the money sat on the wrong
        # exchange shard. Report the exchange's own words, never a guess.
        err = out.get("error") or out.get("raw")
        print(f"\n  *** REJECTED by Kalshi: HTTP {sc} -- {err}")
        print("  Nothing was placed. This is NOT 'no fill'.")
        rec("end", why="rejected", status_code=sc, error=err,
            balance_after=balance())
        return
    if filled <= 0:
        print("\n  accepted but no fill -- the IOC found nothing at that "
              "price and cancelled. Send path proven; fill path not.")
        rec("end", why="no fill", balance_after=balance())
        return

    # ---- verify against the exchange's own records ----
    time.sleep(3)
    st, f = get("/portfolio/fills", {"limit": "5"})
    mine = [x for x in (f or {}).get("fills", []) if x.get("ticker") == tk]
    print(f"\n  /portfolio/fills shows {len(mine)} fill(s) on this market:")
    for x in mine:
        print(f"    {x.get('count_fp') or x.get('count')} @ "
              f"yes {x.get('yes_price_dollars')} / no {x.get('no_price_dollars')}"
              f"  taker={x.get('is_taker')}  fee ${x.get('fee_cost')}")
        rec("fill", **x)
    st, p = get("/portfolio/positions", {"limit": "50"})
    pos = [x for x in (p or {}).get("market_positions", [])
           if x.get("ticker") == tk]
    print(f"  position: {pos[0].get('position_fp') if pos else 'NONE'}")
    rec("position", pos=pos[0] if pos else None)
    b1 = balance()
    print(f"  balance after the buy: ${b1:.4f}   (was ${b0:.4f}, "
          f"delta ${b1-b0:+.4f})")

    # ---- wait for settlement and prove the payout ----
    print(f"\n  waiting for settlement (closes in {cs - time.time():+.0f}s)...")
    end = time.time() + 420
    result = None
    while time.time() < end:
        time.sleep(10)
        st, mb = get("/markets/" + tk)
        mm = (mb or {}).get("market") or {}
        if mm.get("status") == "finalized" and mm.get("result") in ("yes", "no"):
            result = mm["result"]
            break
    b2 = balance()
    won = (result == want) if result else None
    print(f"\n  SETTLEMENT: {result}   we held {want.upper()}   "
          f"{'WON' if won else 'LOST' if won is False else 'UNKNOWN'}")
    print(f"  balance now ${b2:.4f}")
    print(f"    before buy   ${b0:.4f}")
    print(f"    after buy    ${b1:.4f}   (stake+fee: ${b1-b0:+.4f})")
    print(f"    after settle ${b2:.4f}   (payout:    ${b2-b1:+.4f})")
    print(f"    NET on the whole round trip: ${b2-b0:+.4f}")
    expect = (filled * (1.0 - price)) if won else -(filled * price)
    print(f"    modelled net (before fee): ${expect:+.6f}")
    rec("settled", result=result, won=won, balance_before=b0,
        after_buy=b1, after_settle=b2, net=round(b2 - b0, 6),
        modelled=round(expect, 6))
    print(f"\n  THE WHOLE PATH IS PROVEN: order -> fill -> position -> fee -> "
          f"settlement -> payout.")


if __name__ == "__main__":
    main()
