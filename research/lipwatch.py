#!/usr/bin/env python3
"""lipwatch.py -- the reward test's recorder. READ-ONLY (GET only).

Every 5 minutes, for every market we have sent a reward order to
(results/lip_orders.jsonl), write one row to results/lipwatch.jsonl:
  - the book both sides (top 6 levels) and, from lipscan's copy of Kalshi's
    scoring rule, our share of our side and the payout rate that implies
    ($/h if the book held), so the pass bar ("credit >= 50% of what the rules
    predicted") is measured against what the book really was, not a guess;
  - our reward orders (resting / filled counts);
  - account total and pools, so an unexplained credit shows up by time;
  - each program's paid_out flag.
Stops when results/lipwatch.stop exists, or after --hours.

    python research/lipwatch.py --once       # one row per market, printed
    python research/lipwatch.py --hours 96   # the test's recorder
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kauth                                     # noqa: E402
import lipscan                                   # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LOG = os.path.join(ROOT, "results", "lip_orders.jsonl")
OUT = os.path.join(ROOT, "results", "lipwatch.jsonl")
STOP = os.path.join(ROOT, "results", "lipwatch.stop")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def placed():
    """{order_id: place record} for every accepted reward order."""
    out = {}
    try:
        with open(LOG, encoding="utf-8") as f:
            for ln in f:
                r = json.loads(ln)
                if r.get("kind") == "place" and r.get("order_id"):
                    out[r["order_id"]] = r
    except FileNotFoundError:
        pass
    return out


def one_round():
    now = time.time()
    st, bal = kauth.get("/portfolio/balance")
    pools = None
    if st == 200:
        pools = {int(x["exchange_index"]): float(x["balance"])
                 for x in bal.get("balance_breakdown") or []}
    # the API has no per-market filter: one read of every liquidity program
    sp, ip = kauth.get("/incentive_programs",
                       {"status": "all", "type": "liquidity", "limit": "10000"})
    rows = []
    for oid, r in placed().items():
        tk = r["ticker"]
        so, o = kauth.get("/portfolio/orders/" + oid)
        od = (o or {}).get("order") or {} if so == 200 else {}
        sb, ob = kauth.get(f"/markets/{tk}/orderbook")
        yb, nb = lipscan.book_sides(ob) if sb == 200 else ([], [])
        our_left = float(od.get("remaining_count_fp") or 0) \
            if od.get("status") == "resting" else 0.0
        # the book INCLUDES our resting size; take it out, then score us in
        body = r.get("body") or {}
        lipscan_side = r.get("buy")
        our_px = (float(body.get("price", 0)) if lipscan_side == "yes"
                  else round(1.0 - float(body.get("price", 1)), 4))
        mine = yb if lipscan_side == "yes" else nb
        them = []
        for p, s in mine:
            if abs(p - our_px) < 1e-9:
                s = s - our_left
            if s > 1e-9:
                them.append((p, s))
        if lipscan_side == "yes":
            yb2, nb2 = them, nb
        else:
            yb2, nb2 = yb, them
        progs = []
        for p in r.get("programs") or []:
            t0, t1 = ts(p["start_date"]), ts(p["end_date"])
            if not (t0 <= now <= t1):
                continue
            rate = p["period_reward"] / 10000.0 / (t1 - t0) * 3600.0
            d, sh, q = lipscan.predict(
                yb2, nb2, float(p["target_size_fp"]),
                p["discount_factor_bps"] / 10000.0, rate, 1.0, lipscan_side,
                our_px, our_left)
            progs.append({"id": p["id"], "usd_per_h": round(d, 4),
                          "share": round(sh, 4), "counted": q})
        paid = [{"id": p.get("id"), "paid_out": p.get("paid_out"),
                 "end": p.get("end_date")}
                for p in ((ip or {}).get("incentive_programs") or [])
                if p.get("market_ticker") == tk] if sp == 200 else None
        rows.append({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "order_id": oid, "ticker": tk, "buy": lipscan_side,
                     "status": od.get("status"), "left": our_left,
                     "filled": od.get("fill_count_fp"),
                     "yes": sorted(yb, reverse=True)[:6],
                     "no": sorted(nb, reverse=True)[:6],
                     "pred": progs, "paid": paid,
                     "total": (bal or {}).get("balance_dollars")
                     if st == 200 else None, "pools": pools})
    with open(OUT, "a", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x) + "\n")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--hours", type=float, default=96.0)
    ap.add_argument("--every", type=float, default=300.0)
    a = ap.parse_args()
    if not lipscan.selftest():
        raise SystemExit("lipscan self-test failed")
    end = time.time() + a.hours * 3600
    while True:
        try:
            rows = one_round()
            for x in rows:
                print(x["t"], x["ticker"], x["buy"], x["status"],
                      "left", x["left"], "filled", x["filled"],
                      [(p["share"], p["usd_per_h"], p["counted"])
                       for p in x["pred"]], "total", x["total"], flush=True)
        except Exception as e:                        # noqa: BLE001
            print("round failed:", repr(e), flush=True)
        if a.once or time.time() > end or os.path.exists(STOP):
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
