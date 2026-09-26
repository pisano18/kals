#!/usr/bin/env python3
"""lipscan.py -- where would a resting 1c BUY earn Kalshi liquidity rewards?

READ-ONLY (GET only). For every active liquidity program outside the live bots'
pool (exchange_index 2 = crypto & commodities), read the book and apply the
program's own scoring rule (CFTC filing 2026-07-15, effective 07-30):

  per side (a yes ask counts as a no bid), walk bids from the best price down,
  adding size, until the total reaches TARGET. The reference price is the first
  price where the running total reaches TARGET/5. A bid scores
  DF ** ticks_below_reference * size (0 ticks if above it); scores are
  normalised per side. A second is EXCLUDED (pays nobody) unless BOTH sides
  reach TARGET. Our period payout ~= reward * mean over counted seconds of
  (our share of yes side + our share of no side) / 2 * counted/total seconds.

Below 10c the tick is 0.1c, so a 1c bid that is one CENT under the reference
is 10 ticks down and scores DF**10 (1/1024 at DF 0.5): worthless. So the only
1c orders that earn are on a side whose bids above 1c total under TARGET/5.

The prediction assumes the book stays as it is now for the rest of the period.
It is what the pass/kill bar of the reward test is measured against, not a
forecast of money.

    python research/lipscan.py --selftest
    python research/lipscan.py [--min-hours 36] [--count 1000]
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])

BOT_POOL = 2


def tick(p):
    """Kalshi's tapered tick: 0.1c below 10c and above 90c, 1c between."""
    return 0.001 if (p < 0.10 - 1e-9 or p > 0.90 + 1e-9) else 0.01


def ticks_between(hi, lo):
    """Number of ticks from lo up to hi (hi >= lo), walking the taper."""
    n, p = 0, round(lo, 4)
    while p < hi - 1e-9 and n < 5000:
        p = round(p + tick(p), 4)
        n += 1
    return n


def side_scores(bids, target, df):
    """bids: [(price, size, owner)] on ONE side. Returns ({owner: normalised
    score}, qualifies). Implements the filing's walk exactly."""
    lv = sorted(bids, key=lambda b: -b[0])
    if not lv:
        return {}, False
    if lv[0][0] >= 1.0 - 1e-9:
        return {}, False
    tot, ref, q = 0.0, None, []
    prices = sorted(set(round(b[0], 4) for b in lv), reverse=True)
    for px in prices:
        at = [b for b in lv if abs(b[0] - px) < 1e-9]
        tot += sum(b[1] for b in at)
        q.extend(at)
        if ref is None and tot >= target / 5.0 - 1e-9:
            ref = px
        if tot >= target - 1e-9:
            break
    else:
        return {}, False                     # never reached TARGET
    s = {}
    for (px, sz, who) in q:
        n = 0 if px >= ref - 1e-9 else ticks_between(ref, px)
        s[who] = s.get(who, 0.0) + (df ** n) * sz
    z = sum(s.values())
    return ({k: v / z for k, v in s.items()} if z > 0 else {}), True


def predict(yes_bids, no_bids, target, df, reward, frac_left, our_side,
            our_px, our_n):
    """Our payout for the rest of the period if the book holds still and we
    add our_n at our_px on our_side ('yes' or 'no'). Returns (dollars,
    our_share_of_side, both_sides_qualify)."""
    yb = [(p, s, "them") for p, s in yes_bids]
    nb = [(p, s, "them") for p, s in no_bids]
    (yb if our_side == "yes" else nb).append((our_px, our_n, "us"))
    ys, yq = side_scores(yb, target, df)
    ns, nq = side_scores(nb, target, df)
    if not (yq and nq):
        return 0.0, (ys if our_side == "yes" else ns).get("us", 0.0), False
    share = (ys if our_side == "yes" else ns).get("us", 0.0)
    return reward * frac_left * share / 2.0, share, True


def selftest():
    fails = []
    ck = lambda ok, msg: (print(("  ok   " if ok else "  FAIL ") + msg),
                          None if ok else fails.append(msg))
    print("lipscan self-test")
    ck(ticks_between(0.02, 0.01) == 10, "1c->2c is 10 ticks under the taper")
    ck(ticks_between(0.12, 0.11) == 1, "11c->12c is 1 tick")
    ck(ticks_between(0.11, 0.09) == 11, "9c->11c is 10 + 1 ticks")
    # an EMPTY side (50 contracts) that we fill with 1000 at 1c: ref = 1c,
    # we hold 1000/1050 of it; the other side qualifies -> half the pot
    d, sh, q = predict([(0.01, 50)], [(0.97, 5000)], 1000, 0.5, 100.0, 1.0,
                       "yes", 0.01, 1000)
    ck(q and abs(sh - 1000 / 1050) < 1e-9 and abs(d - 50 * 1000 / 1050) < 1e-6,
       f"filling an empty side pays ~half the pot ({d:.2f} of 100)")
    # without us the side never reaches target -> every second excluded
    _, _, q0 = predict([(0.01, 50)], [(0.97, 5000)], 1000, 0.5, 100.0, 1.0,
                       "yes", 0.01, 0.0)
    ck(not q0, "a side under TARGET excludes the second")
    # a 1c bid under a 2c reference is worth DF**10 of its size
    d2, sh2, _ = predict([(0.02, 5000)], [(0.97, 5000)], 1000, 0.5, 100.0, 1.0,
                         "yes", 0.01, 1000)
    ck(sh2 == 0.0, "1c under a 5,000-lot at 2c does not even qualify "
       "(target reached at 2c)")
    d3, sh3, _ = predict([(0.02, 300)], [(0.97, 5000)], 1000, 0.5, 100.0, 1.0,
                         "yes", 0.01, 1000)
    ck(sh3 < 0.01, f"1c under a 2c reference scores ~DF**10 ({sh3:.5f})")
    # a nothing-planted world: we add nothing -> we earn nothing
    d4, sh4, _ = predict([(0.01, 5000)], [(0.97, 5000)], 1000, 0.5, 100.0,
                         1.0, "yes", 0.01, 0.0)
    ck(d4 == 0.0 and sh4 == 0.0, "zero size earns zero")
    # the price at 1.00 has no reference
    ck(side_scores([(1.0, 5000, "x")], 1000, 0.5) == ({}, False),
       "a bid at the top price has no reference")
    print("SELF-TEST " + ("PASSED" if not fails else "FAILED"))
    return not fails


def book_sides(ob):
    """GET /markets/<t>/orderbook body -> (yes_bids, no_bids) as
    [(price_dollars, size)]. Dollar fields only: the unit is fixed by the
    field name, never inferred from magnitude (hard rule 5)."""
    o = (ob or {}).get("orderbook_fp") or {}
    f = lambda k: [(float(p), float(s)) for p, s in (o.get(k) or [])]
    return f("yes_dollars"), f("no_dollars")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--min-hours", type=float, default=36.0)
    ap.add_argument("--count", type=float, default=1000.0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; not touching the API")
    import kauth
    progs, cur = [], None
    for _ in range(80):
        q = {"limit": "200", "status": "active"}
        if cur:
            q["cursor"] = cur
        st, b = kauth.get("/incentive_programs", q)
        if st != 200:
            raise SystemExit(f"incentive_programs read failed: {st} {b}")
        progs += b.get("incentive_programs") or []
        cur = b.get("next_cursor")
        if not cur:
            break
    now = time.time()
    ts = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    keep = []
    for p in progs:
        if p.get("incentive_type") != "liquidity":
            continue
        t0, t1 = ts(p["start_date"]), ts(p["end_date"])
        if t1 - now < a.min_hours * 3600:
            continue
        keep.append((p, t0, t1))
    print(f"{len(progs)} active programs; {len(keep)} liquidity programs "
          f"with >= {a.min_hours:g} h left")
    import threading
    from concurrent.futures import ThreadPoolExecutor
    rows, lock, done = [], threading.Lock(), [0]

    def scan_one(item):
        p, t0, t1 = item
        tk = p["market_ticker"]
        st, ob = kauth.get(f"/markets/{tk}/orderbook")
        if st != 200:
            return
        yb, nb = book_sides(ob)
        rew = p["period_reward"] / 10000.0
        tgt = float(p["target_size_fp"])
        df = p["discount_factor_bps"] / 10000.0
        left = (t1 - max(now, t0)) / (t1 - t0)
        hits = []
        for side in ("yes", "no"):
            d, sh, q = predict(yb, nb, tgt, df, rew, left, side, 0.01,
                               a.count)
            if d > 0:
                hits.append((side, d, sh))
        if hits:
            # the pool is read only for earning sides: a market in the live
            # bots' pool (2) is dropped here, never shown
            st, m = kauth.get("/markets/" + tk)
            mk = (m or {}).get("market") or {}
            exi = mk.get("exchange_index")
            if st == 200 and exi is not None and int(exi) != BOT_POOL:
                for side, d, sh in hits:
                    mine = yb if side == "yes" else nb
                    with lock:
                        rows.append({
                            "ticker": tk, "side": side, "pred": round(d, 2),
                            "share": round(sh, 3), "reward": rew,
                            "hours_left": round((t1 - now) / 3600, 1),
                            "frac_left": round(left, 3), "target": tgt,
                            "exi": exi, "status": mk.get("status"),
                            "side_book": sorted(mine, reverse=True)[:4],
                            "other_book": sorted(nb if side == "yes" else yb,
                                                 reverse=True)[:3],
                            "vol24": mk.get("volume_24h_fp"),
                            "close": mk.get("close_time")})
        with lock:
            done[0] += 1
            if done[0] % 250 == 0:
                print(f"  ... {done[0]}/{len(keep)} read, {len(rows)} "
                      f"earning sides", flush=True)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(scan_one, keep))
    rows.sort(key=lambda r: -r["pred"])
    out = a.out or "results/lipscan_" + datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H%MZ") + ".json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)
    print(f"\n{len(rows)} sides where {a.count:g} at 1c would earn; "
          f"written {out}\n")
    for r in rows[:30]:
        print(f"  ${r['pred']:>7.2f}  share {r['share']:.2f}  {r['side']:<3} "
              f"{r['ticker']:<45} pot ${r['reward']:.0f} "
              f"{r['hours_left']:>5.0f} h  book {r['side_book']}  "
              f"vol24 {r['vol24']}")


if __name__ == "__main__":
    main()
