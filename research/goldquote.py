#!/usr/bin/env python3
# VERSION: 2026-09-07-g1
"""goldquote.py -- the two-sided quoter for the gold cutoff test.

WHAT IT DOES
  Rests S contracts on each side of one KXGOLD15M market at the LIP Reference
  Price, re-pegs as that price moves, and stops after N windows. It exists to
  answer ONE pre-registered question (results/PREREG_gold.md): does Kalshi's
  scoring stop at the full Target Size? Gold is the only family where the two
  answers straddle the $1.00 minimum payout, so the result is a binary.

SAFETY, and why each rail is here
  post_only ALWAYS -- an order that rests or is rejected. It can never cross,
    never take liquidity, never pay a taker fee.
  CANCEL BEFORE PLACE on every re-peg. Placing first would briefly hold TWO
    orders on one side and double the reserve; with a small account that is the
    documented path to a naked position (HANDOFF, ruin analysis).
  A cumulative collateral cap, checked before every order. On a binary the
    total deployed IS the maximum loss.
  A loss abort, checked every loop against the exchange's own numbers.
  Cancel-everything in a finally block, VERIFIED against the paged
    ?status=resting listing -- a cancel that silently fails leaves live
    exposure nobody is watching (that bug was real and is fixed in ordercli).
  --dry-run does every read and every calculation and sends nothing.

USAGE
  python goldquote.py --selftest
  python goldquote.py --dry-run --windows 1
  python goldquote.py --live --windows 8
"""
import argparse
import datetime as dt
import json
import sys
import time

sys.path.insert(0, r"C:\kals-repo\research")
import ordercli as oc

KEY_ID = "b48b406b-b498-4d14-b640-be989913526f"
KEY_FILE = r"C:\kals\kalshi.pem"
SERIES = "KXGOLD15M"
TARGET = 300.0
DISC = 0.50
LOSS_ABORT = -15.00          # dollars of realised+unrealised loss
CADENCE = 3.0                # seconds between re-peg checks

# DO NOT QUOTE AN ALREADY-DECIDED MARKET.
# Observed live 2026-09-07 06:42Z: KXGOLD15M ref_yes 0.988 / ref_no 0.011.
# Quoting 20 a side there costs $19.76 on the YES leg and $0.22 on the NO leg.
# Both legs filling locks a guaranteed $20.00 for $19.98 -- two cents. But a
# YES-ONLY fill leaves $19.76 at risk to earn $0.24, and a one-sided fill is
# precisely what arrives when the price is about to move (adverse selection,
# demonstrated live twice tonight). The rebate is a few dollars; it cannot pay
# for that tail.
# So: only quote when the reference price is away from the extremes, which
# bounds the one-sided exposure at SIZE x PRICE_MAX.
PRICE_MIN, PRICE_MAX = 0.20, 0.80


def ref_price(levels, target=TARGET):
    """Reference Price: walking DOWN from the best, the first level at which
    cumulative resting size reaches ONE FIFTH of Target Size."""
    lv = sorted(levels, reverse=True)
    if not lv:
        return None, 0.0
    depth = sum(s for _, s in lv)
    cum = 0.0
    for p, s in lv:
        cum += s
        if cum >= target / 5.0:
            return p, depth
    return lv[-1][0], depth


def book(api, tk):
    st, ob = api("GET", "/markets/" + tk + "/orderbook", query={"depth": "60"})
    o = (ob or {}).get("orderbook_fp") or {}
    y = [(round(float(p), 4), float(s))
         for p, s in (o.get("yes_dollars") or []) if float(s) > 0.005]
    n = [(round(float(p), 4), float(s))
         for p, s in (o.get("no_dollars") or []) if float(s) > 0.005]
    return y, n


def selftest():
    print("=" * 74)
    print("SELF-TEST -- the reference price and the rails")
    print("=" * 74)
    fails = []

    # reference price: a small order alone at the top must NOT set it
    lv = [(0.60, 5.0), (0.59, 10.0), (0.58, 100.0), (0.57, 500.0)]
    r, d = ref_price(lv)
    print(f"\n  book {lv}")
    print(f"    target/5 = {TARGET/5:.0f}; cumulative reaches it at {r}")
    # hand-check: cumulative 5, 15, 115 -> first level reaching 60 is 0.58
    print(f"    hand-check: cum 5, 15, 115 -> first >= 60 is at 0.58")
    if r != 0.58:
        fails.append(f"reference {r}, hand-check says 0.58")

    # REAL BOOK, photographed by the operator 2026-09-07 06:38Z on
    # KXCOPPER15M: touch holds 2 contracts, so the reference must NOT be the
    # touch. cum 2, 31, 2071 -> first >= 60 is 0.93.
    real = [(0.95, 2.0), (0.94, 29.0), (0.93, 2040.0)]
    rr, _ = ref_price(real)
    print(f"\n  real copper book {real}")
    print(f"    reference {rr} (expect 0.93 -- a 2-contract touch cannot set it)")
    if rr != 0.93:
        fails.append(f"reference {rr} on the real book, expected 0.93")

    lv2 = [(0.60, 500.0)]
    r2, _ = ref_price(lv2)
    print(f"\n  a single deep level at the touch: ref {r2} (expect 0.60)")
    if r2 != 0.60:
        fails.append("a level holding more than target/5 must set the ref")

    r3, d3 = ref_price([])
    print(f"  empty book: ref {r3}, depth {d3} (expect None, 0.0)")
    if r3 is not None:
        fails.append("empty book must give no reference")

    # the rails we depend on
    oc.set_env(True)
    print(f"\n  production ceilings: count {oc.MAX_COUNT}, per-order "
          f"${oc.MAX_NOTIONAL}, cumulative ${oc.MAX_DEPLOYED}")
    b = oc.build_order("KXTEST", "bid", 0.50, oc.MAX_COUNT, "t")
    if b.get("post_only") is not True:
        fails.append("post_only not forced")
    over = oc.build_order("KXTEST", "bid", 0.99, oc.MAX_COUNT, "t")
    if not oc.check_limits(over):
        fails.append("a full-size order at 0.99 was not refused by MAX_NOTIONAL")
    print(f"    full size at 0.99 (collateral ${oc.collateral(over):.2f}) -> "
          f"{'REFUSED' if oc.check_limits(over) else '*** ALLOWED ***'}")

    # an ask must reserve (1-p), not p
    a = oc.build_order("KXTEST", "ask", 0.20, 10, "t")
    if abs(oc.collateral(a) - 8.0) > 1e-9:
        fails.append(f"ask collateral {oc.collateral(a)}, expected 8.00")
    print(f"    ask 10 @ 0.20 reserves ${oc.collateral(a):.2f} (expect 8.00 = "
          f"10 x (1-0.20))")

    print()
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        return False
    print("SELF-TEST PASSED")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--size", type=float, default=20.0)
    ap.add_argument("--windows", type=int, default=8)
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing to trade")
    if not (a.dry_run or a.live):
        raise SystemExit("pass --dry-run or --live")

    oc.set_env(True)
    pk = oc.load_key(KEY_FILE)
    BASE = oc.PROD

    def api(m, p, body=None, query=None):
        return oc.send(BASE, pk, KEY_ID, m, p, body=body, query=query)

    def balance():
        st, b = api("GET", "/portfolio/balance")
        return float((b or {}).get("balance_dollars") or 0)

    start_bal = balance()
    print(f"\n  starting balance ${start_bal:.4f}   size {a.size:.0f}/side   "
          f"{a.windows} window(s)   {'DRY RUN' if a.dry_run else '*** LIVE ***'}")
    print(f"  caps: cumulative ${oc.MAX_DEPLOYED:.2f}, abort at "
          f"${LOSS_ABORT:.2f}\n")

    live = {"yes": None, "no": None}      # side -> (order_id, price, count)
    log = []
    windows_done = 0
    aborted = None

    def cancel_side(side):
        cur = live.get(side)
        if not cur:
            return
        oid, px, cnt = cur
        if a.live:
            st, r, still = oc.cancel(BASE, pk, KEY_ID, oid, 0)
            if still:
                raise RuntimeError(f"CANCEL FAILED and order {oid} is STILL "
                                   f"RESTING -- aborting rather than continue")
        live[side] = None

    def cancel_all():
        for s in ("yes", "no"):
            try:
                cancel_side(s)
            except Exception as e:
                print(f"  !! {e}")
        if a.live:
            rest, ok = oc.resting_orders(BASE, pk, KEY_ID)
            if not ok:
                print("  !! COULD NOT VERIFY -- check for resting orders BY HAND")
            else:
                print(f"  resting after cleanup: {len(rest)}")
                for o in rest:
                    print(f"     {o.get('ticker')} @ {o.get('yes_price_dollars')}")

    try:
        while windows_done < a.windows and not aborted:
            st, b = api("GET", "/markets", query={"series_ticker": SERIES,
                                                  "status": "open", "limit": "3"})
            mks = (b or {}).get("markets", [])
            if not mks:
                print("  no open gold market; waiting")
                time.sleep(10)
                continue
            m = mks[0]
            tk = m["ticker"]
            close = dt.datetime.fromisoformat(
                m["close_time"].replace("Z", "+00:00"))
            print(f"\n  === window {windows_done+1}/{a.windows}: {tk} "
                  f"closes {m['close_time']} ===")
            wstart = balance()
            ticks = 0

            while dt.datetime.now(dt.timezone.utc) < close - dt.timedelta(seconds=8):
                y, n = book(api, tk)
                ry, dy = ref_price(y)
                rn, dn = ref_price(n)
                if ry is None or rn is None or dy < TARGET or dn < TARGET:
                    time.sleep(CADENCE)
                    continue
                if not (PRICE_MIN <= ry <= PRICE_MAX):
                    # decided market -- a one-sided fill here risks the whole
                    # deployment to earn cents. Stand down, and make sure we
                    # are not left resting into it.
                    if live["yes"] or live["no"]:
                        print(f"    ref_yes {ry:.3f} outside "
                              f"[{PRICE_MIN},{PRICE_MAX}] -- standing down")
                        cancel_side("yes")
                        cancel_side("no")
                    time.sleep(CADENCE)
                    continue

                for side, ref in (("yes", ry), ("no", rn)):
                    cur = live.get(side)
                    if cur and abs(cur[1] - ref) < 1e-9:
                        continue                      # already at the reference
                    cancel_side(side)                 # CANCEL BEFORE PLACE
                    # ask price is the YES price; bidding NO at rn means
                    # offering to sell YES at (1 - rn)
                    px = ref if side == "yes" else round(1.0 - ref, 4)
                    o_side = "bid" if side == "yes" else "ask"
                    body = oc.build_order(tk, o_side, px, a.size,
                                          f"gq-{side}-{int(time.time()*1000)%1000000}")
                    bad = oc.check_limits(body)
                    if bad:
                        print(f"    {side}: rails refuse {bad}")
                        continue
                    rest, ok = oc.resting_orders(BASE, pk, KEY_ID) if a.live else ([], True)
                    if not ok:
                        raise RuntimeError("cannot read resting orders")
                    dep = sum(oc.order_collateral(o) for o in rest)
                    if dep + oc.collateral(body) > oc.MAX_DEPLOYED:
                        print(f"    {side}: cumulative ${dep+oc.collateral(body):.2f} "
                              f"> cap ${oc.MAX_DEPLOYED:.2f}, skipping")
                        continue
                    if a.dry_run:
                        live[side] = ("DRY", ref, a.size)
                        print(f"    [dry] {side} {a.size:.0f} @ {px:.4f} "
                              f"(ref {ref:.4f}, collateral "
                              f"${oc.collateral(body):.2f})")
                    else:
                        stx, r = api("POST", "/portfolio/events/orders", body=body)
                        if stx in (200, 201):
                            live[side] = (r.get("order_id"), ref, a.size)
                            print(f"    {side} {a.size:.0f} @ {px:.4f} "
                                  f"(ref {ref:.4f}) -> {stx}")
                        else:
                            print(f"    {side} @ {px:.4f} -> {stx} "
                                  f"{json.dumps(r)[:120] if isinstance(r,dict) else r}")
                ticks += 1
                if ticks % 20 == 0 and a.live:
                    cur_bal = balance()
                    st, p = api("GET", "/portfolio/positions")
                    exposure = sum(float(x.get("market_exposure_dollars") or 0)
                                   for x in (p or {}).get("market_positions", []))
                    pnl = (cur_bal + exposure) - start_bal
                    print(f"    .. bal ${cur_bal:.2f} exposure ${exposure:.2f} "
                          f"P&L ${pnl:+.2f}")
                    if pnl <= LOSS_ABORT:
                        aborted = f"loss abort: P&L ${pnl:+.2f} <= ${LOSS_ABORT}"
                        break
                time.sleep(CADENCE)

            cancel_all()
            windows_done += 1
            wend = balance()
            log.append({"window": windows_done, "ticker": tk,
                        "balance_delta": round(wend - wstart, 4)})
            print(f"  window {windows_done} done; balance ${wend:.4f} "
                  f"(delta ${wend-wstart:+.4f})")
            if aborted:
                break
            time.sleep(4)
    except KeyboardInterrupt:
        aborted = "interrupted by operator"
    except Exception as e:
        aborted = f"exception: {e}"
        print(f"\n  !! {e}")
    finally:
        print("\n  --- CLEANUP ---")
        cancel_all()
        end_bal = balance()
        print(f"\n  windows completed : {windows_done}")
        print(f"  balance           : ${start_bal:.4f} -> ${end_bal:.4f} "
              f"({end_bal-start_bal:+.4f})")
        if aborted:
            print(f"  ABORTED           : {aborted}")
        print(f"  per-window        : {json.dumps(log)}")
        print(f"\n  The rebate, if any, is NOT in this number. It appears in the")
        print(f"  balance 48+ hours from now. Read it against PREREG_gold.md.")


if __name__ == "__main__":
    main()
