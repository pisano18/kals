#!/usr/bin/env python3
"""vfy_tonight_book.py -- independent rebuild of tonight's book, with SEQ.

pinclose.price_tonight_hedge takes the first populated snapshot in the hour
file and then applies EVERY delta in the hour, with no sequence check, and
records the book state at the END of each second. This file rebuilds the same
book with:
  * deltas filtered to seq > the snapshot's seq, applied in seq order;
  * a millisecond timeline, so the question "did the Kalshi book move BEFORE
    the index crossed" can be answered rather than assumed;
  * the best NO bid (what we could SELL our position into) alongside the YES
    ask, because the two are the same liquidity and the operator would take
    whichever is cheaper.

SELF-TEST plants a book, a snapshot in the wrong sequence order, and a delta
that must be ignored; and a null world where nothing arrives.
"""
import gzip
import json
import os
import sys

DATA = r"C:\kals\kalshi_data"
TICKER = "KXNEAR15M-26SEP082045-45"
CLOSE_S = 1788914700
HOUR = "20260909T00"
K_EFF = 2.34915
ENTRY_AVG = (96.2 * 20 + 95.6 * 20 + 73.0 * 19) / 59.0 / 100.0


class Book:
    def __init__(self):
        self.yes = {}
        self.no = {}
        self.seq = None

    def snapshot(self, msg, seq):
        self.yes.clear()
        self.no.clear()
        for key, d in (("yes_dollars_fp", self.yes),
                       ("no_dollars_fp", self.no)):
            for pair in (msg.get(key) or []):
                try:
                    p, q = round(float(pair[0]), 4), float(pair[1])
                except Exception:
                    continue
                if q > 0:
                    d[p] = q
        self.seq = seq

    def delta(self, side, price, dq):
        d = self.yes if side == "yes" else self.no
        p = round(float(price), 4)
        now = d.get(p, 0.0) + float(dq)
        if now <= 1e-9:
            d.pop(p, None)
        else:
            d[p] = now

    def best_no_bid(self):
        return (max(self.no), self.no[max(self.no)]) if self.no else (None, 0.0)

    def best_yes_bid(self):
        return (max(self.yes), self.yes[max(self.yes)]) if self.yes \
            else (None, 0.0)


def fee(p, n=1.0):
    import math
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def selftest():
    print("SELF-TEST -- vfy_tonight_book")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    b = Book()
    b.snapshot({"yes_dollars_fp": [["0.40", "10"], ["0.30", "5"]],
                "no_dollars_fp": [["0.52", "60"], ["0.50", "9"]]}, 100)
    ck(b.best_no_bid() == (0.52, 60.0),
       f"PLANT: the best NO bid is 52c for 60 contracts {b.best_no_bid()}")
    ck(round(1.0 - b.best_no_bid()[0], 4) == 0.48,
       "so the YES ask we would PAY is 48c -- tonight's number, and the same "
       "liquidity we would SELL our NO into at 52c")
    b.delta("no", 0.52, -60.0)
    ck(b.best_no_bid() == (0.50, 9.0),
       f"a delta that empties the touch level exposes the next one "
       f"{b.best_no_bid()}")
    b2 = Book()
    b2.snapshot({"yes_dollars": [["0.40", "10"]]}, 1)
    ck(b2.yes == {} and b2.no == {},
       "NULL: the OLD key names (yes_dollars) load nothing -- the open "
       "pindata bug, kept visible")
    b3 = Book()
    ck(b3.best_no_bid() == (None, 0.0),
       "NULL: an empty book has no bid rather than a stale one")

    # a delta that arrives BEFORE the snapshot must be discarded by seq
    keep = [(99, "no", 0.60, 50.0), (101, "no", 0.55, 7.0)]
    b4 = Book()
    b4.snapshot({"no_dollars_fp": [["0.52", "60"]]}, 100)
    for sq, sd, px, dq in keep:
        if sq > b4.seq:
            b4.delta(sd, px, dq)
    ck(b4.best_no_bid() == (0.55, 7.0),
       f"PLANT: the pre-snapshot delta at seq 99 is discarded and the "
       f"post-snapshot one at 101 is kept {b4.best_no_bid()}")
    b5 = Book()
    b5.snapshot({"no_dollars_fp": [["0.52", "60"]]}, 100)
    for sq, sd, px, dq in keep:
        b5.delta(sd, px, dq)             # what pinclose does: no seq filter
    ck(b5.best_no_bid() == (0.60, 50.0),
       f"and WITHOUT the seq filter the same tape gives a different answer "
       f"{b5.best_no_bid()} -- so the check is not cosmetic")

    ck(abs((1.0 - ENTRY_AVG - 0.48) - fee(ENTRY_AVG) - fee(0.48)
           + 0.38995) < 1e-4,
       "hand arithmetic: 100 - 88.525 - 48.0 - 0.72 - 1.75 = -39.0c, which is "
       "pinclose's printed number")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    print("\n" + "=" * 76)
    print("  TONIGHT'S BOOK, REBUILT WITH SEQUENCE ORDER")
    print("=" * 76)
    snapf = os.path.join(DATA, "orderbook_snapshot", HOUR + ".jsonl.gz")
    deltaf = os.path.join(DATA, "orderbook_delta", HOUR + ".jsonl.gz")

    snaps = []
    with gzip.open(snapf, "rt") as fh:
        for line in fh:
            if TICKER not in line:
                continue
            d = json.loads(line)
            if d["msg"].get("market_ticker") != TICKER:
                continue
            snaps.append(d)
    print(f"  {len(snaps)} snapshot messages for {TICKER}")
    for d in snaps:
        m = d["msg"]
        print(f"    seq {d.get('seq')}  rx {d.get('_rx_ms')}  "
              f"yes levels {len(m.get('yes_dollars_fp') or [])}  "
              f"no levels {len(m.get('no_dollars_fp') or [])}")
    use = None
    for d in snaps:
        if d["msg"].get("yes_dollars_fp") or d["msg"].get("no_dollars_fp"):
            use = d
            break
    if use is None:
        print("  no populated snapshot -- NOT MEASURED")
        return
    bk = Book()
    bk.snapshot(use["msg"], use.get("seq"))
    print(f"  using snapshot seq {bk.seq}; "
          f"best NO bid {bk.best_no_bid()}, best YES bid {bk.best_yes_bid()}")

    deltas = []
    n_before = 0
    with gzip.open(deltaf, "rt") as fh:
        for line in fh:
            if TICKER not in line:
                continue
            d = json.loads(line)
            m = d["msg"]
            if m.get("market_ticker") != TICKER:
                continue
            sq = d.get("seq")
            if sq is not None and bk.seq is not None and sq <= bk.seq:
                n_before += 1
                continue
            deltas.append((sq, m, d.get("_rx_ms")))
    print(f"  {len(deltas):,} deltas after the snapshot seq; "
          f"{n_before:,} discarded as at-or-before it "
          f"(pinclose applies those too)")
    deltas.sort(key=lambda t: (t[0] if t[0] is not None else 0))

    print("\n  MILLISECOND TIMELINE, tau 24 down to tau 12.")
    print("  'YES ask' is what we would PAY to hedge; 'NO bid' is the same")
    print("  liquidity seen as what we could SELL our position into.")
    print(f"  {'tau':>5}{'ms into sec':>13}{'YES ask':>10}{'size':>8}"
          f"{'locked P&L':>13}")
    rows = []
    for sq, m, rx in deltas:
        ts = int(m.get("ts_ms") or rx or 0)
        try:
            bk.delta(str(m.get("side", "")).lower(),
                     m.get("price_dollars", m.get("price")),
                     m.get("delta_fp", m.get("delta")) or 0.0)
        except Exception:
            continue
        tau = CLOSE_S - ts // 1000
        if 12 <= tau <= 24:
            nb, nsz = bk.best_no_bid()
            if nb is None:
                continue
            ask = round(1.0 - nb, 4)
            v = 1.0 - ENTRY_AVG - ask - fee(ENTRY_AVG) - fee(ask)
            rows.append((tau, ts % 1000, ask, nsz, v))
    last = None
    for tau, ms, ask, sz, v in rows:
        key = (tau, ask)
        if key == last:
            continue
        last = key
        print(f"  {tau:>5}{ms:>13}{100*ask:>9.1f}c{sz:>8.0f}{100*v:>12.1f}c")
    print("\n  Index prints (from pinclose's own reconstruction):")
    print("    tau 18 spot 2.34840 BELOW K_eff -> still winning")
    print("    tau 17 spot 2.34840 BELOW K_eff -> still winning, model 0.17%")
    print("    tau 16 spot 2.35050 ABOVE K_eff -> CROSSED, model 59.36%")
    print("  Compare the first second at which the YES ask leaves single "
          "figures.")
    print("\n  DONE.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    main()
