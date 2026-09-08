#!/usr/bin/env python3
# VERSION: 2026-09-08-pq1
"""pinqueue.py -- if resting is the only way to buy, WHERE would we have to rest?

CONTEXT. research/pinoffer.py measured that in a decided market the LOSING
side's book is empty in 33,427 of 33,431 moments, so there is nothing to take.
The obvious response is "then REST a bid instead of taking one". This file
tests that, and the answer is NO -- for these closes.

A resting bid has PRICE PRIORITY: every contract bid ABOVE our price is filled
before us when a seller finally arrives. So the question is not "can we rest"
but "how long is the queue at a price that still makes money".

MEASURED 2026-09-08 over 10,168 decided moments on a 5-second grid, across the
eight closes where the live runner could not buy anything:

    best bid on the winning side   median 99.90c
    price levels quoted            median 87
    contracts ahead of us at 98.8c ~16,600

THE DECISIVE NUMBER IS 99.90c. Resting pays no fee, so break-even is exactly
1 - flip = 99.10c. The market is ALREADY BIDDING 99.90c, which is 0.80c BEYOND
the price at which this trade stops making money. There is no profitable price
at which we could join that queue.

**SO THOSE CLOSES ARE NOT MISSED PROFIT.** They are closes where the trade is
not available to anyone at a price that works. That is a much better answer
than "we were too slow".

SCOPE, AND IT MATTERS. This is measured on the closes where NOTHING was
offered, which is the population that motivated the question. It says nothing
about resting in the 41% of closes where an offer DOES appear -- a different
population, and still an open question.
"""
import argparse
import glob, gzip, json, math, os, sys, time, zlib
sys.path.insert(0, r"C:\kals-repo\research")
from pindata import Book, load_index, idx_feats, partial, eff_strike, \
    SERIES_TO_INDEX, ROUND_DIGITS
from engine import var_factor, N_AVG
from statistics import NormalDist
ND = NormalDist(); DATA = r"C:\kals\kalshi_data"

def main():
    mk = json.load(open(sys.argv[1], encoding="utf-8"))
    TARGETS = sorted({v["close"] for v in mk.values()})
    idx, _ = load_index(300)
    snaps = {os.path.basename(f)[:11]: f for f in
             glob.glob(os.path.join(DATA, "orderbook_snapshot", "2026*.jsonl.gz"))}
    hours = sorted({time.strftime("%Y%m%dT%H", time.gmtime(c)) for c in TARGETS})
    RUNGS = [0.99, 0.985, 0.98, 0.97, 0.96, 0.95, 0.93, 0.90, 0.85, 0.80]
    ahead = {r: [] for r in RUNGS}
    best_bid = []; nlev = []; n = 0
    for h in hours:
        cands = glob.glob(os.path.join(DATA, "orderbook_delta", h + "*.jsonl.gz"))
        if not cands: continue
        books = {}
        sf = snaps.get(h)
        if sf:
            try:
                with gzip.open(sf, "rt") as fh:
                    for line in fh:
                        if '"orderbook_snapshot"' not in line: continue
                        try: m = json.loads(line)["msg"]
                        except Exception: continue
                        if m.get("market_ticker") in mk:
                            books.setdefault(m["market_ticker"], Book()).snapshot(m, int(m.get("ts_ms") or 0))
            except (EOFError, zlib.error, OSError): pass
        try:
            with gzip.open(cands[0], "rt") as fh:
                for line in fh:
                    if '"orderbook_delta"' not in line: continue
                    try: m = json.loads(line)["msg"]
                    except Exception: continue
                    tk = m.get("market_ticker"); rec = mk.get(tk)
                    if rec is None: continue
                    ts = int(m.get("ts_ms") or 0)
                    bk = books.setdefault(tk, Book())
                    try:
                        bk.delta(str(m.get("side","")).lower(),
                                 m.get("price_dollars", m.get("price")),
                                 m.get("delta_fp", m.get("delta")) or 0.0, ts)
                    except Exception: continue
                    sec = ts//1000; close_s = rec["close"]; tau = close_s-sec
                    if not (3 <= tau <= 30): continue
                    if sec % 5: continue                    # exogenous 5s grid
                    iid = SERIES_TO_INDEX[rec["series"]]
                    if iid not in idx: continue
                    base, arr = idx[iid]
                    pa = partial(base, arr, close_s, sec)
                    if pa is None: continue
                    locked, rr, _ = pa
                    if rr < 1: continue
                    fe = idx_feats(base, arr, sec)
                    if fe is None or not fe["sigma"]: continue
                    mu=(locked+rr*fe["spot"])/N_AVG
                    rd=rec.get("round_digits")
                    K=eff_strike(rec["strike"], int(rd) if rd is not None else ROUND_DIGITS.get(rec["series"]))
                    req=(60.0/rr)*(K-mu)
                    sd=fe["sigma"]*math.sqrt(var_factor(int(rr),[1.0]))*(60.0/rr)
                    if sd<=0: continue
                    pf=(1-ND.cdf(req/sd)) if req>0 else ND.cdf(req/sd)
                    if pf>0.02: continue
                    side_yes = req<=0
                    win = bk.yes if side_yes else bk.no     # BIDS for the winner
                    if not win: continue
                    n += 1
                    best_bid.append(max(win.keys())); nlev.append(len(win))
                    for r in RUNGS:
                        ahead[r].append(sum(s for p, s in win.items() if p > r))
        except (EOFError, zlib.error, OSError): pass
        books.clear()

    def med(x):
        x = sorted(x); return x[len(x)//2] if x else 0
    print(f"\n  {n:,} decided moments, sampled on a 5-second grid\n")
    print(f"  best bid on the winning side: median {100*med(best_bid):.2f}c")
    print(f"  price levels quoted:          median {med(nlev)}\n")
    print(f"  {'if we RESTED at':<18}{'contracts AHEAD of us':>24}{'our EV/contract':>18}{'verdict':>22}")
    def fee(p,nn=1): return math.ceil(0.07*p*(1-p)*nn*10000)/10000
    for r in RUNGS:
        a = med(ahead[r])
        ev = (1-0.0090)*(1-r) - 0.0090*r          # RESTING pays NO FEE
        v = "loses money" if ev <= 0 else ("front of queue" if a < 50 else
            ("deep queue" if a < 1000 else "hopeless queue"))
        print(f"  {100*r:>15.1f}c{a:>24,.0f}{100*ev:>17.2f}c{v:>22}")
    print("\n  A resting bid has PRICE priority: everything bid ABOVE our price is")
    print("  filled first when a seller arrives. 'Contracts ahead' is that queue.")
    print("  Resting pays NO FEE, so breakeven is exactly 1 - flip = 99.10c.")


def selftest():
    """Plant a queue whose answer is known, and a null world with no queue."""
    print("SELF-TEST -- pinqueue")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    def ahead(bids, rest_at):
        return sum(s for p, s in bids.items() if p > rest_at)

    def ev_resting(p, flip=0.0090):
        return (1 - flip) * (1 - p) - flip * p        # NO FEE for a maker

    bids = {0.999: 500.0, 0.995: 1000.0, 0.99: 2000.0, 0.98: 4000.0, 0.90: 9.0}
    ck(ahead(bids, 0.98) == 3500.0,
       f"queue ahead of a 98.0c rest is everything bid ABOVE it, not at or "
       f"above it (got {ahead(bids, 0.98)})")
    ck(ahead(bids, 0.9999) == 0.0,
       "resting above every bid puts nobody ahead of us -- the null case")
    ck(ahead(bids, 0.0) == 7509.0,
       f"resting at zero puts the WHOLE book ahead (got {ahead(bids, 0.0)})")
    ck(abs(ev_resting(1 - 0.0090)) < 1e-9,
       "a maker's break-even is EXACTLY 1 - flip = 99.10c, because resting "
       "pays no fee")
    ck(ev_resting(0.999) < 0 < ev_resting(0.98),
       "bidding 99.90c LOSES money at our measured flip rate while 98.0c "
       "makes it -- which is the whole finding")
    ck(ahead({}, 0.98) == 0.0,
       "an EMPTY book reports an empty queue and must not be read as a short "
       "queue we could join -- there is simply nothing there")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


if __name__ == "__main__":
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--selftest", action="store_true")
    _a, _rest = _ap.parse_known_args()
    if _a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    main()
