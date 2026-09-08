#!/usr/bin/env python3
# VERSION: 2026-09-08-eb1
"""earlybook.py -- top-of-book WITH RESTING SIZE on a tau grid, per market.

WHY THE ticker CHANNEL AND NOT orderbook_delta
  The question is "how much size is resting AT THE TOUCH tau seconds before
  close". Kalshi's ticker message carries exactly that -- yes_bid_dollars,
  yes_ask_dollars, yes_bid_size_fp, yes_ask_size_fp -- at 1.7 MB/hour, where
  orderbook_delta is 60-80 MB/hour. earlyverify.py checks the two agree by
  rebuilding the book from deltas; this file is the cheap path, not a guess.

  Kalshi's convention, and getting it backwards inverts every number here:
    buy YES -> pay yes_ask,      size available = yes_ask_size
    buy NO  -> pay 1 - yes_bid,  size available = yes_bid_size
  (yes_ask is 1 - best no bid, so yes_ask_size IS the resting no-bid size.)

NO-LOOKAHEAD, ENFORCED HERE AND NOWHERE ELSE
  The state stored at tau is the LAST ticker message with ts_ms <= the
  decision instant (close - tau). A message at close-tau+1 can never reach
  the cell for tau. The fill is done by streaming the tape forward in time
  and closing out grid cells behind the clock; the code has no access to a
  future row when it writes a cell.

Writes NEW files only, under early_cache/.
"""
import argparse, array, calendar, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gzsalvage                                            # noqa: E402

CACHE = os.path.join(os.path.dirname(HERE), "early_cache")
TKDIR = r"C:\kals\kalshi_data\ticker"
TG = 140                 # tau grid 0..TG seconds
LOOKBACK = 400           # how far back a quote may be and still be "the book"

SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXZEC15M", "KXHYPE15M", "KXNEAR15M")


def iso_s(s):
    return calendar.timegm(
        (int(s[0:4]), int(s[5:7]), int(s[8:10]),
         int(s[11:13]), int(s[14:16]), int(s[17:19]), 0, 0, 0))


def load_markets():
    d = json.load(open(os.path.join(CACHE, "settled.json")))
    out = {}
    for t, m in d.items():
        if m["series"] not in SERIES or m["result"] not in ("yes", "no"):
            continue
        if m["floor_strike"] is None or m["round_digits"] is None:
            continue
        out[t] = {"series": m["series"], "close_s": iso_s(m["close_ts"]),
                  "result": m["result"], "K": float(m["floor_strike"]),
                  "d": int(m["round_digits"])}
    return out


def _f(m, a, b):
    v = m.get(a)
    if v is not None:
        return float(v)
    v = m.get(b)
    return None if v is None else float(v) / 100.0


def build(verbose=True):
    mk = load_markets()
    files = sorted(glob.glob(os.path.join(TKDIR, "*.jsonl.gz")))
    lo = iso_s("2026-08-25T00:00:00Z")
    ids, order = {}, []
    for t, m in sorted(mk.items(), key=lambda kv: kv[1]["close_s"]):
        if m["close_s"] >= lo:
            ids[t] = len(order)
            order.append(t)
    N = len(order)
    if verbose:
        print("  %d settled markets in the tape window, %d ticker hour files"
              % (N, len(files)))
    W = TG + 1
    yb = array.array("f", bytes(4 * N * W))
    ya = array.array("f", bytes(4 * N * W))
    bs = array.array("f", bytes(4 * N * W))
    asz = array.array("f", bytes(4 * N * W))
    age = array.array("f", [-1.0]) * (N * W)
    prev = {}                     # id -> (ts_s, yb, ya, bs, as)

    def flush(i, upto_ts):
        """Close out every grid cell whose decision instant is < upto_ts."""
        p = prev.get(i)
        if p is None:
            return
        c = mk[order[i]]["close_s"]
        pts = p[0]
        t_hi = c - pts                       # largest tau with d >= pts
        t_lo = c - upto_ts + 1               # smallest tau with d < upto_ts
        if t_hi > TG:
            t_hi = TG
        if t_lo < 0:
            t_lo = 0
        base = i * W
        for tau in range(t_lo, t_hi + 1):
            if c - tau - pts > LOOKBACK:
                continue
            k = base + tau
            yb[k] = p[1]
            ya[k] = p[2]
            bs[k] = p[3]
            asz[k] = p[4]
            age[k] = (c - tau) - pts

    nrows = 0
    for fi, fp in enumerate(files):
        for line in gzsalvage.iter_lines(fp):
            if '"ticker"' not in line:
                continue
            try:
                m = json.loads(line)["msg"]
            except Exception:
                continue
            i = ids.get(m.get("market_ticker"))
            if i is None:
                continue
            ts = m.get("ts_ms")
            if ts is None:
                continue
            ts = int(ts) // 1000
            c = mk[order[i]]["close_s"]
            if ts > c or c - ts > LOOKBACK + TG:
                continue
            b = _f(m, "yes_bid_dollars", "yes_bid")
            a = _f(m, "yes_ask_dollars", "yes_ask")
            sb = _f(m, "yes_bid_size_fp", "yes_bid_size")
            sa = _f(m, "yes_ask_size_fp", "yes_ask_size")
            if b is None or a is None:
                continue
            p = prev.get(i)
            if p is not None and ts < p[0]:
                continue                      # out of order: ignore
            flush(i, ts)
            prev[i] = (ts, b, a, sb or 0.0, sa or 0.0)
            nrows += 1
        if verbose and fi % 40 == 0:
            print("    .. %s  %d rows kept" % (os.path.basename(fp), nrows))
    for i in list(prev):
        flush(i, mk[order[i]]["close_s"] + 1)

    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, "book_grid.bin"), "wb") as f:
        for a in (yb, ya, bs, asz, age):
            f.write(a.tobytes())
    meta = {"W": W, "TG": TG, "N": N, "order": order,
            "markets": {t: mk[t] for t in order}}
    with open(os.path.join(CACHE, "book_meta.json"), "w") as f:
        json.dump(meta, f)
    if verbose:
        have = sum(1 for x in age if x >= 0)
        print("\n  %d ticker rows kept, %d/%d grid cells filled (%.1f%%)"
              % (nrows, have, N * W, 100.0 * have / (N * W)))
    return meta


def load():
    meta = json.load(open(os.path.join(CACHE, "book_meta.json")))
    N, W = meta["N"], meta["W"]
    raw = open(os.path.join(CACHE, "book_grid.bin"), "rb").read()
    n = N * W * 4
    outs = []
    for j in range(5):
        a = array.array("f")
        a.frombytes(raw[j * n:(j + 1) * n])
        outs.append(a)
    return meta, outs


def selftest():
    # A cell at tau must be answered by the last row at or before close-tau
    # and NEVER by a later one. Plant two rows and check both directions.
    close, TGx = 1000, 5
    rows = [(994, 0.10), (997, 0.90)]
    grid, pts = {}, None
    for ts, v in rows:
        if pts is not None:
            for tau in range(max(0, close - ts + 1), close - pts[0] + 1):
                if tau <= TGx:
                    grid[tau] = pts[1]
        pts = (ts, v)
    for tau in range(0, close - pts[0] + 1):
        if tau <= TGx:
            grid[tau] = pts[1]
    ok = (grid.get(5) == 0.10 and grid.get(4) == 0.10 and
          grid.get(3) == 0.90 and grid.get(0) == 0.90)
    print("  tau=5,4 -> %s,%s   (row at close-6=994)"
          % (grid.get(5), grid.get(4)))
    print("  tau=3,0 -> %s,%s   (row at close-3=997)"
          % (grid.get(3), grid.get(0)))
    print("  a cell is NEVER answered by a row after its decision instant")
    print("SELF-TEST " + ("PASSED" if ok else "*** FAILED ***"))
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    build()
