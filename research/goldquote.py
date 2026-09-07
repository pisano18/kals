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

# NEVER JOIN A WINDOW LATE. The operator caught this before it ran.
# reward = R x mean over ALL snapshots in the period of our share. Join a
# 900-second window with 60 seconds left and we are present for 1/15 of the
# snapshots, so a $1.42 window pays about $0.09 -- under the $1.00 floor, so
# ZERO. We would carry the full fill risk for no possible credit.
# Require most of the window to remain, otherwise wait for the next one.
MIN_WINDOW_SECONDS = 780      # of a 900 s window; refuse anything shorter


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
    ap.add_argument("--max-minutes", type=float, default=45.0,
                    help="hard wall-clock stop. This process "
                         "outlives the session that started it, "
                         "so it must be able to end itself.")
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
    hard_stop = time.time() + a.max_minutes * 60.0

    def cancel_side(side):
        cur = live.get(side)
        if not cur:
            return
        oid, px, cnt = cur
        if a.live:
            st, r, still = oc.cancel(BASE, pk, KEY_ID, oid, 0)
            # None means the listing could not be read: UNKNOWN, not OK.
            # `if still:` treated None as success because None is falsy.
            if still is not False:
                raise RuntimeError(
                    f"cancel of {oid} returned still={still!r} -- "
                    f"UNVERIFIED or STILL RESTING. Aborting rather than "
                    f"quote on top of an order we cannot account for.")
        live[side] = None

    def cancel_all():
        for s in ("yes", "no"):
            try:
                cancel_side(s)
            except Exception as e:
                print(f"  !! {e}")
        if a.live:
            # CANCEL what is left, do not merely report it. Printing a
            # resting order and exiting leaves live exposure nobody is
            # watching -- and this process may outlive the session.
            for attempt in range(3):
                rest, ok = oc.resting_orders(BASE, pk, KEY_ID)
                if not ok:
                    print("  !! CANNOT READ ORDERS -- CHECK BY HAND")
                    break
                if not rest:
                    print("  verified: nothing resting")
                    break
                print(f"  {len(rest)} still resting, cancelling (pass "
                      f"{attempt+1}/3)")
                for o in rest:
                    oc.cancel(BASE, pk, KEY_ID, o.get("order_id"),
                              o.get("exchange_index") or 0)
                time.sleep(2)
            else:
                print("  *** ORDERS STILL RESTING AFTER 3 PASSES -- "
                      "CANCEL BY HAND ***")

    try:
        while windows_done < a.windows and not aborted:
            if time.time() > hard_stop:
                aborted = f"wall-clock limit {a.max_minutes:.0f} min"
                break
            st, b = api("GET", "/markets", query={"series_ticker": SERIES,
                                                  "status": "open", "limit": "3"})
            mks = (b or {}).get("markets", [])
            if not mks:
                print("  no open gold market; waiting")
                time.sleep(10)
                continue
            # pick the market with the MOST time left, and refuse to join late
            def left(mm):
                return (dt.datetime.fromisoformat(
                    mm["close_time"].replace("Z", "+00:00"))
                    - dt.datetime.now(dt.timezone.utc)).total_seconds()
            mks = sorted([x for x in mks if x.get("close_time")],
                         key=left, reverse=True)
            if not mks or left(mks[0]) < MIN_WINDOW_SECONDS:
                secs = left(mks[0]) if mks else 0
                print(f"  only {secs:.0f}s left in the freshest window "
                      f"(need {MIN_WINDOW_SECONDS}s) -- waiting for the next")
                time.sleep(min(30, max(5, secs + 5)))
                continue
            m = mks[0]
            tk = m["ticker"]
            close = dt.datetime.fromisoformat(
                m["close_time"].replace("Z", "+00:00"))
            print(f"\n  === window {windows_done+1}/{a.windows}: {tk} "
                  f"closes {m['close_time']} ({left(m):.0f}s of quoting) ===")
            wstart = balance()
            ticks = 0

            while (dt.datetime.now(dt.timezone.utc)
                   < close - dt.timedelta(seconds=8)
                   and time.time() < hard_stop):
                y, n = book(api, tk)
                ry, dy = ref_price(y)
                rn, dn = ref_price(n)
                if ry is None or rn is None or dy < TARGET or dn < TARGET:
                    ticks += 1
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
                    ticks += 1
                    time.sleep(CADENCE)
                    continue

                # BOTH LEGS OR NEITHER.
                # The dry run caught this: when one leg was refused by a rail
                # the loop placed the OTHER one anyway and sat quoting a single
                # side continuously -- which is the naked directional exposure
                # this design exists to avoid. A safety ceiling was CREATING
                # the unsafe state. Build both, validate both, then act.
                plan = {}
                for side, ref in (("yes", ry), ("no", rn)):
                    px = ref if side == "yes" else round(1.0 - ref, 4)
                    o_side = "bid" if side == "yes" else "ask"
                    plan[side] = (ref, px, oc.build_order(
                        tk, o_side, px, a.size,
                        f"gq-{side}-{int(time.time()*1000) % 1000000}"))
                bad = {s: oc.check_limits(v[2]) for s, v in plan.items()}
                pair_collat = sum(oc.collateral(v[2]) for v in plan.values())
                # TOTAL deployed = resting collateral + FILLED inventory.
                # Counting resting orders alone made the cap dead code: a
                # fill left the listing, held fell to ~0, and the next
                # tick funded a fresh pair, to the whole balance.
                if a.live:
                    held_all, ok = oc.deployed(BASE, pk, KEY_ID)
                    if not ok:
                        raise RuntimeError("cannot read deployed capital")
                    rest, _ = oc.resting_orders(BASE, pk, KEY_ID)
                    mine = {live[s][0] for s in ("yes", "no") if live[s]}
                    ours = sum(oc.order_collateral(o) for o in rest
                               if o.get("order_id") in mine)
                    held = held_all - ours
                else:
                    held = 0.0
                blocked = [f"{s}:{b}" for s, b in bad.items() if b]
                if held + pair_collat > oc.MAX_DEPLOYED:
                    blocked.append(f"pair ${pair_collat:.2f} + held ${held:.2f} "
                                   f"> cap ${oc.MAX_DEPLOYED:.2f}")
                if blocked:
                    if live["yes"] or live["no"]:
                        print(f"    PAIR BLOCKED {blocked} -- standing down "
                              f"(never one-sided)")
                        cancel_side("yes")
                        cancel_side("no")
                    ticks += 1
                    time.sleep(CADENCE)
                    continue

                # both legs are legal; re-peg only the ones that moved
                for side in ("yes", "no"):
                    ref, px, body = plan[side]
                    cur = live.get(side)
                    if cur and abs(cur[1] - ref) < 1e-9:
                        continue                      # already at the reference
                    # ATOMIC RE-PEG when an order already rests on this side.
                    # Neither cancel-then-place (a gap where the side is
                    # unquoted) nor place-then-cancel (two orders on one side,
                    # double reserve -- the documented ruin path). Amend has
                    # neither failure mode. Price changes forfeit queue
                    # position, but so does cancel-then-place, so nothing is
                    # lost.
                    if cur and not a.dry_run:
                        stx, r = oc.amend(BASE, pk, KEY_ID, cur[0], body)
                        if stx in (200, 201):
                            nid = (r.get("order_id") if isinstance(r, dict)
                                   else None) or cur[0]
                            live[side] = (nid, ref, a.size)
                            print(f"    {side} AMEND -> {px:.4f} "
                                  f"(ref {ref:.4f}) -> {stx}")
                            continue
                        print(f"    {side} amend -> {stx} "
                              f"{json.dumps(r)[:110] if isinstance(r,dict) else r}"
                              f"  falling back to cancel+place")
                    cancel_side(side)                 # CANCEL BEFORE PLACE
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
                            # a leg failed to place -- do not run one-sided
                            print(f"    leg failed; cancelling the other side")
                            cancel_side("yes" if side == "no" else "no")
                            break
                ticks += 1
                if ticks % 6 == 0 and a.live:
                    cur_bal = balance()
                    # MARK TO MARKET, not to cost. An outside reviewer caught
                    # this and was right: market_exposure_dollars is the COST
                    # basis (verified -- a contract bought at 0.79 reports
                    # exposure 0.790000). Cash falls by the cost when a fill
                    # lands, so cash + cost is CONSTANT and the abort could
                    # never fire on an unrealised loss. It would only see the
                    # damage after settlement, by which time the window is
                    # over. Value the position at what the market says now.
                    st, p = api("GET", "/portfolio/positions")
                    mv = 0.0
                    for x in (p or {}).get("market_positions", []):
                        try:
                            n = float(x.get("position_fp") or 0)
                        except Exception:
                            continue
                        if abs(n) < 1e-9:
                            continue
                        py, pn = book(api, x.get("ticker"))
                        if not py or not pn:
                            # cannot mark it -- fall back to cost, and say so
                            mv += float(x.get("market_exposure_dollars") or 0)
                            print(f"    !! cannot mark {x.get('ticker')}, "
                                  f"using cost basis")
                            continue
                        yes_mid = (py[0][0] + (1.0 - pn[0][0])) / 2.0
                        mv += (n * yes_mid) if n > 0 else (abs(n) * (1.0 - yes_mid))
                    pnl = (cur_bal + mv) - start_bal
                    print(f"    .. bal ${cur_bal:.2f} mark-to-mkt ${mv:.2f} "
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
