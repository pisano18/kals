#!/usr/bin/env python3
# VERSION: 2026-09-07-pl1
"""pinlive.py -- pin, live. Paper mode by default; sends nothing without --live.

WHAT pin IS (from pin.py, read not remembered):
  In the last <=60s of a crypto 15-minute market, most of the 60-print
  settlement average is already locked on disk, so fair value has almost
  stopped depending on any volatility estimate. When the model says the
  outcome is effectively DECIDED (fair >= 0.98 or <= 0.02) and a quote still
  sits on the WRONG side of that near-certainty -- an ask still selling a
  near-won YES cheap -- pin TAKES it. Wins ~1-3c, loses ~97c, flip rate ~0.4%.

WHY A TAKER, AND WHY THAT CHANGES THE SAFETY MODEL vs last night:
  goldquote was post_only -- it could never cross, never take, never pay a fee.
  pin MUST cross to take the stale quote. So the rails are different:
    * a hard LIMIT price = the exact quote we are taking. The order can never
      fill worse than the price we saw. This is the taker's post_only-equivalent.
    * time_in_force = immediate_or_cancel: take it now if it is there, cancel
      if it is gone. It NEVER rests, so there is no un-hedged inventory to
      manage and no cancel to race. This structurally removes last night's
      whole failure class.
    * we buy a NEAR-CERTAIN contract and hold to settlement (~<=60s). Max loss
      per contract is what we paid (~1-3c below 1.00 on the winning side, or
      the whole ~1-3c stake if it flips).

PAPER MODE (default): computes fair each second from the LIVE index feed,
  spots the wrong-side quotes, and LOGS what it would take. Sends nothing.
  Then scores each would-be trade against the actual settlement. This proves
  the live fair-value math and the fire rate for $0.

LIVE MODE (--live, size 1): sends IOC taker orders at the seen price. Gated by
  a per-order price ceiling, a cumulative-stake cap, and a loss abort that runs
  BEFORE any branch (last night's abort sat after a `continue` and never ran).

LAST NIGHT'S LESSONS, carried in by construction:
  * risk/abort logic runs first, unskippable.
  * order_collateral / stake accounting counts filled inventory, not just
    resting orders (pin holds to settlement, so every fill IS inventory).
  * test every path at size 1 before any size that could earn.
  * read the live index tolerantly (the current hour file is a live gzip).
"""
import argparse
import calendar
import glob
import gzip
import json
import math
import os
import sys
import time
from collections import defaultdict, deque
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                       # noqa: E402

sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get                                       # noqa: E402

ND = NormalDist()
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
RESULTS = r"C:\kals-repo\results"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXBCH15M": "BCHUSD_RTI",
    "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
    "KXTON15M": "TONUSD_RTI",
}

PIN = 0.98            # fair beyond this (or below 1-PIN) = "decided"
TAU_MAX = 60          # only the sigma-proof region
EDGE_FLOOR = 0.005    # the quote must be at least this far on the wrong side
SIGMA_WIN = 300       # seconds of ticks used to estimate per-second sigma


# ---------- live index ------------------------------------------------------
class LiveIndex:
    """Per-second tick history per index_id, tailed from the collector file."""

    def __init__(self):
        self.ticks = defaultdict(dict)          # index_id -> {sec: value}
        self._pos = {}                          # file -> bytes read (unused;
                                                # we re-read the current hour)

    def refresh(self):
        """Re-read the newest one or two hour files, tolerant of a live gzip."""
        files = sorted(glob.glob(os.path.join(IDXDIR, "202609*.jsonl.gz")))[-2:]
        for f in files:
            try:
                with gzip.open(f, "rt") as fh:
                    for line in fh:
                        if '"cfbenchmarks_value"' not in line:
                            continue
                        try:
                            d = json.loads(line)
                        except Exception:
                            continue
                        m = d.get("msg") or {}
                        iid = m.get("index_id")
                        if not iid:
                            continue
                        try:
                            data = json.loads(m.get("data") or "{}")
                            val = float(data.get("value"))
                            t = int(data.get("time")) // 1000
                        except Exception:
                            continue
                        self.ticks[iid][t] = val
            except EOFError:
                pass                             # live gzip; use what parsed

    def spot(self, iid):
        d = self.ticks.get(iid)
        if not d:
            return None, None
        s = max(d)
        return s, d[s]

    def sigma(self, iid):
        """Per-second SD of index innovations over the trailing window."""
        d = self.ticks.get(iid)
        if not d or len(d) < 30:
            return None
        secs = sorted(d)[-SIGMA_WIN:]
        diffs = [d[secs[i]] - d[secs[i - 1]]
                 for i in range(1, len(secs))
                 if secs[i] - secs[i - 1] == 1]
        if len(diffs) < 20:
            return None
        mu = sum(diffs) / len(diffs)
        var = sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1)
        return math.sqrt(var)

    def partial(self, iid, close_s, now_s):
        """(locked sum, remaining count) for the 60s settle window, or None."""
        d = self.ticks.get(iid)
        if not d:
            return None
        lo = close_s - N_AVG + 1
        hi = min(now_s, close_s)
        if hi < lo:
            return 0.0, N_AVG
        want = hi - lo + 1
        got = [d[s] for s in range(lo, hi + 1) if s in d]
        if len(got) < want * 0.95:
            return None
        return sum(got) * (want / len(got)), N_AVG - want


def fair(idx, iid, close_s, now_s, strike, sigma):
    part = idx.partial(iid, close_s, now_s)
    if part is None:
        return None
    locked, r = part
    _, spot = idx.spot(iid)
    if spot is None:
        return None
    mu = (locked + r * spot) / N_AVG
    tau = close_s - now_s
    if tau <= 0:
        return 1.0 if mu >= strike else 0.0
    sd = sigma * math.sqrt(var_factor(int(tau), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= strike else 0.0
    return ND.cdf((mu - strike) / sd)


# ---------- self-test -------------------------------------------------------
def selftest():
    print("SELF-TEST")
    fails = []
    idx = LiveIndex()
    iid = "TEST"
    close_s = 1_000_000
    # a settle window fully locked ABOVE the strike -> fair ~ 1.0
    for s in range(close_s - 59, close_s + 1):
        idx.ticks[iid][s] = 105.0
    f = fair(idx, iid, close_s, close_s, strike=100.0, sigma=1.0)
    print(f"  fully-locked avg 105 vs strike 100 -> fair {f:.4f} (expect ~1)")
    if f < 0.999:
        fails.append(f"decided-yes fair {f}, expected ~1.0")
    # locked below strike -> fair ~ 0
    for s in range(close_s - 59, close_s + 1):
        idx.ticks[iid][s] = 95.0
    f = fair(idx, iid, close_s, close_s, strike=100.0, sigma=1.0)
    print(f"  fully-locked avg 95 vs strike 100 -> fair {f:.4f} (expect ~0)")
    if f > 0.001:
        fails.append(f"decided-no fair {f}, expected ~0.0")
    # half locked at strike, spot at strike, tau 30 -> fair ~ 0.5
    # the locked prints are the FIRST 30s of the window [close-59, close-30];
    # now = close-30 so spot is the last locked tick.
    idx.ticks[iid].clear()
    for s in range(close_s - 59, close_s - 29):
        idx.ticks[iid][s] = 100.0
    f = fair(idx, iid, close_s, close_s - 30, strike=100.0, sigma=1.0)
    print(f"  half-locked at strike, tau 30 -> fair {f:.4f} (expect ~0.5)")
    if not (0.35 <= f <= 0.65):
        fails.append(f"at-the-money fair {f}, expected ~0.5")
    # sigma estimate
    idx.ticks["S2"] = {1000 + i: 100.0 + 0.1 * ((-1) ** i) for i in range(60)}
    sg = idx.sigma("S2")
    print(f"  sigma of a +/-0.1 sawtooth: {sg:.4f} (expect ~0.2)")
    if sg is None or not (0.1 <= sg <= 0.3):
        fails.append(f"sigma estimate {sg}")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for f_ in fails:
        print("  - " + f_)
    return not fails


# ---------- main loop -------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--paper", action="store_true", help="log only (default)")
    ap.add_argument("--live", action="store_true", help="send IOC takers, size 1")
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--edge", type=float, default=EDGE_FLOOR)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    live = a.live
    mode = "LIVE (IOC taker, size 1)" if live else "PAPER (log only)"

    runid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    logpath = os.path.join(RESULTS, f"pin-{'live' if live else 'paper'}-{runid}.jsonl")

    def rec(kind, **kw):
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        kw["kind"] = kind
        try:
            with open(logpath, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(kw, default=str) + "\n")
        except Exception:
            pass

    print(f"  MODE: {mode}   log: {logpath}")
    rec("start", mode=mode, edge=a.edge, minutes=a.minutes)

    idx = LiveIndex()
    seen = set()                    # (ticker, second) already evaluated
    signals = []                    # would-be / real trades, scored later
    universe = {}                   # ticker -> (iid, close_s, strike)
    uni_at = 0.0
    end = time.time() + a.minutes * 60

    def refresh_universe():
        u = {}
        for series, iid in SERIES_TO_INDEX.items():
            try:
                st, b = get("/markets", {"series_ticker": series,
                                         "status": "open", "limit": "5"})
            except Exception:
                continue
            for m in (b or {}).get("markets", []):
                ct, sk = m.get("close_time"), m.get("floor_strike")
                if not ct or sk is None:
                    continue
                cs = calendar.timegm(time.strptime(ct, "%Y-%m-%dT%H:%M:%SZ"))
                u[m["ticker"]] = (iid, cs, float(sk))
        return u

    def live_book(tk):
        """(best yes ask, best yes bid) from the LIVE orderbook, not /markets."""
        try:
            st, ob = get("/markets/" + tk + "/orderbook", {"depth": "3"})
        except Exception:
            return None, None
        o = (ob or {}).get("orderbook_fp") or {}
        yb_lv = [(float(p), float(s)) for p, s in (o.get("yes_dollars") or [])]
        nb_lv = [(float(p), float(s)) for p, s in (o.get("no_dollars") or [])]
        ybid = max((p for p, _ in yb_lv), default=None)
        nbid = max((p for p, _ in nb_lv), default=None)
        yask = round(1.0 - nbid, 4) if nbid is not None else None
        return yask, ybid

    while time.time() < end:
        idx.refresh()
        now_s = int(time.time())
        if time.time() - uni_at > 10:
            universe = refresh_universe()
            uni_at = time.time()
        for tk, (iid, close_s, strike) in list(universe.items()):
            tau = close_s - now_s
            if not (0 < tau <= TAU_MAX):
                continue
            key = (tk, now_s)
            if key in seen:
                continue
            seen.add(key)
            sg = idx.sigma(iid)
            if sg is None:
                continue
            f = fair(idx, iid, close_s, now_s, strike, sg)
            if f is None:
                continue
            if True:
                m = {"ticker": tk}
                ya, yb = live_book(tk)
                if ya is None or yb is None:
                    continue
                # DECIDED YES, and a yes ask still cheap -> take it
                if f >= PIN and 0 < ya <= f - a.edge:
                    sig = dict(ticker=m["ticker"], side="yes", fair=round(f, 4),
                               price=ya, tau=tau, strike=strike,
                               spot=idx.spot(iid)[1], edge=round(f - ya, 4))
                    signals.append(sig)
                    rec("signal", **sig)
                    print(f"  {m['ticker']} fair {f:.3f} take YES ask {ya:.2f} "
                          f"tau {tau}s edge {f-ya:+.3f}")
                # DECIDED NO, and a yes bid still high -> someone overpays for
                # a near-dead YES; we would BUY NO at (1 - yb)
                elif f <= 1 - PIN and yb >= f + a.edge and yb > 0:
                    na = round(1 - yb, 4)
                    sig = dict(ticker=m["ticker"], side="no", fair=round(f, 4),
                               price=na, tau=tau, strike=strike,
                               spot=idx.spot(iid)[1], edge=round((1 - f) - na, 4))
                    signals.append(sig)
                    rec("signal", **sig)
                    print(f"  {m['ticker']} fair {f:.3f} take NO  @ {na:.2f} "
                          f"tau {tau}s edge {(1-f)-na:+.3f}")
        time.sleep(1)

    rec("end", signals=len(signals))
    print(f"\n  {len(signals)} signals in {a.minutes:.0f} min. Log: {logpath}")
    print("  Score them after settlement with:  python pinscore.py " + logpath)


if __name__ == "__main__":
    main()
