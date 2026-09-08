#!/usr/bin/env python3
# VERSION: 2026-09-08-pd1
"""pindata.py -- build the ONE dataset every factor test needs.

WHY THIS EXISTS

Every study so far that lacked the order book measured the WRONG POPULATION.
Scoring all the moments the model feels certain gives a flip rate near 0.01%;
scoring the moments somebody actually offered us the winning side cheap gives
0.90%. Ninety times worse, because a near-certainty is only sold cheaply when
the seller may know something. Any factor tested on the first population will
look wonderful and lose money on the second.

So: replay the book and the index together, and emit ONE ROW PER GENUINELY
AVAILABLE TRADE -- a moment where we could actually have bought, at a real
price, in real size -- with every candidate factor attached and the settled
outcome known. After that, testing a factor is a query over a table instead of
a fresh multi-hour tape replay, and testing COMBINATIONS becomes free.

ONE ROW = one (market, second) where a resting offer existed on the side the
model favours. Columns fall into four groups:

  WHAT IT COSTS      price, size available, spread, fee
  THE ARITHMETIC     tau, r, mu, required_move, locked coverage
  THE CONDITIONS     sigma at several horizons, transient, drift, jump flag,
                     book depth and imbalance, quote age, trade intensity,
                     market-implied probability, hour of day
  THE ANSWER         settled result, and whether the favoured side flipped

NO LOOKAHEAD BY CONSTRUCTION: every column except the outcome is computed from
data at or before that second. The outcome is deliberately separate so a factor
study cannot accidentally use it as an input.
"""
import argparse
import array
import glob
import gzip
import json
import math
import os
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
OUT = r"C:\kals-repo\results\pindata"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
                "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
                "KXHYPE15M": 4, "KXNEAR15M": 4, "KXDOGE15M": 7}
TAU_LO, TAU_HI = 2, 90


def billed_fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def eff_strike(k, d):
    return float(k) - 0.5 * (10.0 ** (-int(d))) if d is not None else float(k)


# ---------------------------------------------------------------------------
class Book:
    """One market's book, rebuilt from snapshot + deltas, with level ages."""

    __slots__ = ("yes", "no", "born", "seq", "last_ts", "gaps", "trades")

    def __init__(self):
        self.yes = {}          # price -> size
        self.no = {}
        self.born = {}         # (side, price) -> ts_ms the level appeared
        self.seq = None
        self.last_ts = None
        self.gaps = 0
        self.trades = []       # ts_ms of recent trades

    def snapshot(self, msg, ts):
        self.yes.clear()
        self.no.clear()
        self.born.clear()
        for side, key in (("yes", "yes_dollars"), ("no", "no_dollars")):
            d = self.yes if side == "yes" else self.no
            for pair in (msg.get(key) or []):
                try:
                    p, q = round(float(pair[0]), 4), float(pair[1])
                except Exception:
                    continue
                if q > 0:
                    d[p] = q
                    self.born[(side, p)] = ts
        self.last_ts = ts

    def delta(self, side, price, dq, ts):
        d = self.yes if side == "yes" else self.no
        p = round(float(price), 4)
        was = d.get(p, 0.0)
        now = was + float(dq)
        if now <= 1e-9:
            d.pop(p, None)
            self.born.pop((side, p), None)
        else:
            if was <= 1e-9:
                self.born[(side, p)] = ts
            d[p] = now
        self.last_ts = ts

    def best(self):
        yb = max(self.yes) if self.yes else None
        nb = max(self.no) if self.no else None
        return yb, nb

    def depth(self, side, n=3):
        d = self.yes if side == "yes" else self.no
        return sum(sorted(d.values(), reverse=True)[:n]) if d else 0.0


# ---------------------------------------------------------------------------
def load_index(hours):
    files = sorted(glob.glob(os.path.join(
        DATA, "cfbenchmarks_value", "2026*.jsonl.gz")))[:-1][-hours:]
    raw = defaultdict(dict)
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                        dd = json.loads(m["data"])
                        raw[m["index_id"]][int(dd["time"]) // 1000] = \
                            float(dd["value"])
                    except Exception:
                        continue
        except (EOFError, zlib.error, OSError):
            pass
    out = {}
    for iid, d in raw.items():
        if d:
            lo, hi = min(d), max(d)
            arr = array.array("d", [float("nan")] * (hi - lo + 1))
            for s, v in d.items():
                arr[s - lo] = v
            out[iid] = (lo, arr)
    return out, files


def idx_feats(base, arr, now):
    """sigma at 3 horizons, transient, drift, jump flag -- all backward-looking."""
    i = now - base
    if i < 320 or i >= len(arr):
        return None
    out = {}
    for win, tag in ((30, "s30"), (120, "s120"), (300, "s300")):
        tot = k = 0
        for j in range(max(1, i - win), i + 1):
            a, b = arr[j - 1], arr[j]
            if a == a and b == b:
                dd = b - a
                tot += dd * dd
                k += 1
        out[tag] = math.sqrt(tot / k) if k >= 15 else None
    sg = out.get("s300")
    spot = arr[i]
    if spot != spot or sg is None:
        return None
    # sigma can legitimately be 0 on a dead-flat stretch (an illiquid coin
    # whose index has not moved for 300 s). That is a REAL and interesting
    # state -- nothing can move, so nothing can flip -- so keep the row and
    # report the scaled features as 0 rather than dividing by zero and
    # throwing the observation away.
    scale = sg if sg > 0 else None
    for k_, tag in ((5, "tr5"), (15, "tr15")):
        vals = [arr[j] for j in range(i - k_, i + 1) if arr[j] == arr[j]]
        if len(vals) < 3:
            out[tag] = None
        elif scale is None:
            out[tag] = 0.0
        else:
            out[tag] = (spot - sum(vals) / len(vals)) / (scale * math.sqrt(k_))
    for k_, tag in ((15, "dr15"), (60, "dr60")):
        a = arr[i - k_] if i - k_ >= 0 else float("nan")
        if a != a:
            out[tag] = None
        elif scale is None:
            out[tag] = 0.0
        else:
            out[tag] = (spot - a) / (scale * math.sqrt(k_))
    jump = 0
    for j in range(max(1, i - 30), i + 1):
        a, b = arr[j - 1], arr[j]
        if a == a and b == b and abs(b - a) > 4 * sg:
            jump = 1
            break
    out["jump30"] = jump
    out["spot"] = spot
    out["sigma"] = sg
    return out


def partial(base, arr, close_s, now):
    lo, hi = close_s - N_AVG, min(now, close_s - 1)
    if hi < lo or lo - base < 0 or hi - base >= len(arr):
        return None
    tot = got = 0
    for s in range(lo, hi + 1):
        v = arr[s - base]
        if v == v:
            tot += v
            got += 1
    want = hi - lo + 1
    if got < want * 0.95:
        return None
    return tot * (want / got), N_AVG - want, got / want


# ---------------------------------------------------------------------------
def selftest():
    print("SELF-TEST -- pindata")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    b = Book()
    b.snapshot({"yes_dollars": [["0.60", "100"], ["0.59", "50"]],
                "no_dollars": [["0.39", "200"]]}, 1000)
    yb, nb = b.best()
    ck(yb == 0.60 and nb == 0.39, f"snapshot best yes {yb} no {nb}")
    ck(abs(b.depth("yes", 3) - 150.0) < 1e-9, "depth sums the top levels")
    b.delta("yes", 0.60, -100, 1500)
    yb, _ = b.best()
    ck(yb == 0.59, f"a level emptied by a delta is removed ({yb})")
    ck(("yes", 0.60) not in b.born, "and its age record is dropped")
    b.delta("no", 0.40, 25, 1800)
    ck(b.born[("no", 0.40)] == 1800, "a new level records when it appeared")
    b.delta("no", 0.40, 5, 2500)
    ck(b.born[("no", 0.40)] == 1800,
       "adding to an existing level does NOT reset its age")

    a = array.array("d", [100.0] * 400)
    f = idx_feats(0, a, 350)
    ck(f is not None and f["sigma"] == 0.0,
       "a flat index has zero volatility")
    a2 = array.array("d", [100.0 + (i % 2) * 0.2 for i in range(400)])
    f2 = idx_feats(0, a2, 350)
    ck(f2 and 0.15 < f2["sigma"] < 0.25,
       f"a +/-0.2 sawtooth gives sigma ~0.2 ({f2['sigma'] if f2 else None})")
    p = partial(0, array.array("d", [100.0] * 400), 200, 190)
    ck(p and p[1] == 9,
       f"at tau=10 there are 9 prints still to come ({p[1] if p else None})")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    os.makedirs(a.out, exist_ok=True)
    print(f"\n  loading index ({a.hours}h) ...")
    idx, ifiles = load_index(a.hours)
    print(f"  {len(idx)} indices from {len(ifiles)} files")

    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in SERIES_TO_INDEX:
                mk[r["ticker"]] = r
    print(f"  {len(mk):,} settled markets known")

    bfiles = sorted(glob.glob(os.path.join(
        DATA, "orderbook_delta", "2026*.jsonl.gz")))[:-1][-a.hours:]
    snaps = {os.path.basename(f)[:11]: f for f in sorted(glob.glob(
        os.path.join(DATA, "orderbook_snapshot", "2026*.jsonl.gz")))}
    print(f"  {len(bfiles)} book hours to replay\n")

    rows = 0
    outp = os.path.join(a.out, "rows.jsonl")
    fh_out = open(outp, "w", encoding="utf-8", newline="\n")
    t0 = time.time()

    for bf in bfiles:
        stamp = os.path.basename(bf)[:11]
        books = {}
        want = {}
        for tk, r in mk.items():
            cs = int(float(r["close"]))
            hr = time.strftime("%Y%m%dT%H", time.gmtime(cs))
            if hr == stamp or hr == time.strftime(
                    "%Y%m%dT%H", time.gmtime(cs - 3600)):
                want[tk] = r
        if not want:
            continue
        sf = snaps.get(stamp)
        if sf:
            try:
                with gzip.open(sf, "rt") as f:
                    for line in f:
                        if '"orderbook_snapshot"' not in line:
                            continue
                        try:
                            d = json.loads(line)
                            m = d["msg"]
                        except Exception:
                            continue
                        tk = m.get("market_ticker")
                        if tk in want:
                            books.setdefault(tk, Book()).snapshot(
                                m, int(m.get("ts_ms") or 0))
            except (EOFError, zlib.error, OSError):
                pass

        emitted = defaultdict(set)
        try:
            with gzip.open(bf, "rt") as f:
                for line in f:
                    if '"orderbook_delta"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker")
                    r = want.get(tk)
                    if r is None:
                        continue
                    ts = int(m.get("ts_ms") or 0)
                    sec = ts // 1000
                    close_s = int(float(r["close"]))
                    tau = close_s - sec
                    bk = books.setdefault(tk, Book())
                    try:
                        bk.delta(str(m.get("side", "")).lower(),
                                 m.get("price_dollars", m.get("price")),
                                 m.get("delta_fp", m.get("delta")) or 0.0, ts)
                    except Exception:
                        continue
                    if not (TAU_LO <= tau <= TAU_HI):
                        continue
                    if sec in emitted[tk]:
                        continue
                    iid = SERIES_TO_INDEX[r["series"]]
                    if iid not in idx:
                        continue
                    base, arr = idx[iid]
                    pa = partial(base, arr, close_s, sec)
                    if pa is None:
                        continue
                    locked, rr, cov = pa
                    if rr < 1:
                        continue
                    fe = idx_feats(base, arr, sec)
                    if fe is None:
                        continue
                    mu = (locked + rr * fe["spot"]) / N_AVG
                    K = eff_strike(r["strike"], ROUND_DIGITS.get(r["series"]))
                    req = (60.0 / rr) * (K - mu)
                    yb, nb = bk.best()
                    if yb is None and nb is None:
                        continue
                    side_yes = req <= 0
                    if side_yes:
                        price = round(1 - nb, 4) if nb is not None else None
                        size = bk.no.get(nb, 0.0) if nb is not None else 0.0
                        age = ts - bk.born.get(("no", nb), ts) \
                            if nb is not None else 0
                    else:
                        price = round(1 - yb, 4) if yb is not None else None
                        size = bk.yes.get(yb, 0.0) if yb is not None else 0.0
                        age = ts - bk.born.get(("yes", yb), ts) \
                            if yb is not None else 0
                    if price is None or not (0.5 < price < 1.0) or size < 1:
                        continue
                    emitted[tk].add(sec)
                    won_yes = float(r["result"]) >= 0.5
                    fh_out.write(json.dumps({
                        "tk": tk, "sr": r["series"], "close": close_s,
                        "sec": sec, "tau": tau, "r": rr,
                        "price": price, "size": round(size, 2),
                        "spread": round((1 - nb - yb), 4)
                        if (yb is not None and nb is not None) else None,
                        "dep_y": round(bk.depth("yes"), 1),
                        "dep_n": round(bk.depth("no"), 1),
                        "age_ms": int(age),
                        "mu": mu, "req": req, "cov": round(cov, 4),
                        "spot": fe["spot"], "sig": fe["sigma"],
                        "s30": fe["s30"], "s120": fe["s120"],
                        "tr5": fe["tr5"], "tr15": fe["tr15"],
                        "dr15": fe["dr15"], "dr60": fe["dr60"],
                        "jump": fe["jump30"],
                        "hour": time.gmtime(sec).tm_hour,
                        "side_yes": side_yes,
                        "flip": (side_yes != won_yes),
                    }, default=str) + "\n")
                    rows += 1
        except (EOFError, zlib.error, OSError):
            pass
        books.clear()
        print(f"    {stamp}  rows so far {rows:,}  "
              f"{time.time()-t0:.0f}s", flush=True)

    fh_out.close()
    print(f"\n  {rows:,} rows -> {outp}  ({os.path.getsize(outp)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
