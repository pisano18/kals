#!/usr/bin/env python3
# VERSION: 2026-08-25-b1
"""
book.py -- rebuild the real order book from orderbook_snapshot + delta.

    python research/book.py --selftest
    python research/book.py --data C:\\kals\\kalshi_data

WHY BOTHER, WHEN `ticker` ALREADY HAS A BID AND AN ASK

Three reasons, in ascending order of importance.

1. `ticker` may not carry sizes at all, and a fill model without depth is a
   guess dressed up as a number.

2. Kalshi quotes TWO books per market: yes-bids and no-bids. A no-bid at p is
   the same thing as a yes-ask at (1 - p). Anything that reads only "yes" data
   is looking at half the market. Getting this wrong does not error -- it
   quietly halves your view.

3. PLAN.md sec.4 killed the entire passive/maker strategy on one observation:
   "best bid 0.40 with 3,767 contracts resting". That single number is doing an
   enormous amount of work -- it is the reason the project went taker-only. It
   came from a REST orderbook call, and RUNBOOK separately records that REST
   `/orderbook?depth=N` returns levels ASCENDING and truncates from the BOTTOM,
   which hid top-of-book in the recon output. A number read off an endpoint
   that was simultaneously mis-parsed deserves re-measurement from the
   websocket stream before it is allowed to kill a strategy.

SEQUENCE INTEGRITY IS NOT OPTIONAL

Deltas are only meaningful applied in order. One missed message and every
subsequent level is wrong, silently, forever. So the book carries a `valid`
flag: a gap invalidates it until the next snapshot, and invalid stretches are
excluded rather than quietly used. Applying deltas across a gap is how a
backtest ends up trading against a book that never existed.
"""

import argparse
import glob
import gzip
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from doctor import get_path, walk_paths, find_field       # noqa: E402
from replay import read_jsonl_gz, parse_ts, _num          # noqa: E402


class Book:
    """One market. Prices are integer cents 1..99 on both sides."""

    __slots__ = ("yes", "no", "seq", "valid", "ts")

    def __init__(self):
        self.yes = {}          # yes-bid price -> size
        self.no = {}           # no-bid  price -> size
        self.seq = None
        self.valid = False
        self.ts = None

    def snapshot(self, yes_levels, no_levels, seq, ts):
        self.yes = {int(p): float(s) for p, s in yes_levels if float(s) > 0}
        self.no = {int(p): float(s) for p, s in no_levels if float(s) > 0}
        self.seq, self.valid, self.ts = seq, True, ts

    def delta(self, price, change, side, seq, ts):
        if seq is not None and self.seq is not None and seq != self.seq + 1:
            # A gap. Everything after it would be fiction until a fresh
            # snapshot arrives, so stop pretending the book is known.
            self.valid = False
        self.seq = seq if seq is not None else self.seq
        self.ts = ts
        if not self.valid:
            return
        d = self.yes if side == "yes" else self.no
        p = int(price)
        d[p] = d.get(p, 0.0) + float(change)
        if d[p] <= 0:
            d.pop(p, None)

    def top(self):
        """(yes_bid, yes_bid_size, yes_ask, yes_ask_size) in DOLLARS.

        The yes-ask is derived from the best no-bid: someone bidding p for NO
        is offering YES at (100 - p)."""
        if not self.valid:
            return None
        yb = max(self.yes) if self.yes else None
        nb = max(self.no) if self.no else None
        ya = (100 - nb) if nb is not None else None
        if yb is None or ya is None:
            return None
        return (yb / 100.0, self.yes[yb], ya / 100.0, self.no[nb])

    def depth_within(self, ticks=1):
        """Contracts resting within `ticks` cents of each touch. This is the
        number PLAN sec.4 hangs the maker verdict on."""
        if not self.valid:
            return None, None
        yb = max(self.yes) if self.yes else None
        nb = max(self.no) if self.no else None
        if yb is None or nb is None:
            return None, None
        b = sum(s for p, s in self.yes.items() if p >= yb - ticks + 1)
        a = sum(s for p, s in self.no.items() if p >= nb - ticks + 1)
        return b, a


# ===========================================================================
def _levels(v):
    """Accept [[price, size], ...] or [{'price':p,'size':s}, ...]."""
    out = []
    if not isinstance(v, list):
        return out
    for it in v:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            try:
                out.append((int(it[0]), float(it[1])))
            except (TypeError, ValueError):
                continue
        elif isinstance(it, dict):
            p = it.get("price", it.get("p"))
            s = it.get("size", it.get("s", it.get("quantity")))
            try:
                out.append((int(p), float(s)))
            except (TypeError, ValueError):
                continue
    return out


def rebuild(data_dir, verbose=True, max_msgs=None):
    """ticker -> [(sec, yes_bid, yes_ask, bid_sz, ask_sz)], valid stretches only.

    ORDERING. The collector writes orderbook_snapshot and orderbook_delta into
    two SEPARATE directories, one file per hour each. Concatenating the two
    globs replays an entire day of deltas before the first snapshot is seen, so
    every delta lands on an invalid book and is thrown away: the rebuild
    silently degrades to one book state per snapshot and the depth measurement
    it exists to produce is taken on a book that never had a delta applied.
    The self-test used to miss this because it wrote its snapshot INTO the
    delta directory, which is not the layout on disk.

    So: read both channels, then order per ticker. Book state is per-ticker, so
    interleaving across tickers is irrelevant -- only the order WITHIN a ticker
    matters. `_rx_ms` is the collector's own receive stamp on every message
    from a single local clock, which is exactly the order the socket delivered
    them in; seq breaks ties, and the read index makes it deterministic. seq is
    deliberately NOT the primary key: it restarts on reconnect, and sorting by
    it would interleave two connections' worth of messages into fiction.
    """
    books = defaultdict(Book)
    series = defaultdict(list)
    stats = defaultdict(int)
    depth_samples = []

    files = sorted(glob.glob(os.path.join(data_dir, "orderbook_delta",
                                          "*.jsonl.gz")))
    files += sorted(glob.glob(os.path.join(data_dir, "orderbook_snapshot",
                                           "*.jsonl.gz")))
    if not files:
        if verbose:
            print("  no orderbook channels on disk")
        return {}, stats

    rows = []
    for fp in files:
        try:
            with gzip.open(fp, "rt") as f:
                for line in f:
                    try:
                        m = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rows.append(m)
                    if max_msgs and len(rows) >= max_msgs:
                        break
        except Exception:
            stats["partial_files"] += 1
        if max_msgs and len(rows) >= max_msgs:
            break

    def ts_of(m, d):
        t = parse_ts(d.get("ts")) if isinstance(d, dict) else None
        return t or (m.get("_rx_ms") or 0) / 1000.0

    by_ticker = defaultdict(list)
    for i, m in enumerate(rows):
        typ = m.get("type", "")
        d = m.get("msg") or {}
        tk = d.get("market_ticker") or d.get("ticker")
        if not tk:
            stats["no_ticker"] += 1
            continue
        if "snapshot" not in typ and "delta" not in typ:
            continue
        is_snap = "snapshot" in typ
        t = ts_of(m, d)
        rx = m.get("_rx_ms")
        # no _rx_ms (synthetic fixtures, or a collector that predates it):
        # fall back to the message clock, which is the best available.
        order = (rx / 1000.0) if isinstance(rx, (int, float)) else t
        seq = d.get("seq")
        by_ticker[tk].append((order, seq if isinstance(seq, int) else -1,
                              0 if is_snap else 1, i, typ, d, t))

    ordered = []
    for tk, recs in by_ticker.items():
        recs.sort(key=lambda r: r[:4])
        ordered.append((tk, recs))
    # deterministic across runs, and puts the busiest markets first in stats
    ordered.sort(key=lambda x: x[0])

    for tk, recs in ordered:
        for _o, _s, _k, _i, typ, d, t in recs:
            seq = d.get("seq")
            bk = books[tk]
            if "snapshot" in typ:
                bk.snapshot(_levels(d.get("yes")), _levels(d.get("no")), seq, t)
                stats["snapshots"] += 1
            elif "delta" in typ:
                side = str(d.get("side", "")).lower()
                price = d.get("price")
                change = d.get("delta", d.get("change"))
                if price is None or change is None or side not in ("yes", "no"):
                    stats["unparsed_delta"] += 1
                    continue
                was = bk.valid
                bk.delta(price, change, side, seq, t)
                if was and not bk.valid:
                    stats["seq_gaps"] += 1
                stats["deltas"] += 1
            else:
                continue
            top = bk.top()
            if top is None:
                continue
            yb, ybs, ya, yas = top
            if not (0 < yb < ya < 1):
                stats["crossed_or_odd"] += 1
                continue
            series[tk].append((int(round(t)), yb, ya, ybs, yas))
            b, a = bk.depth_within(1)
            if b is not None:
                depth_samples.append((yb, b, a))

    for v in series.values():
        v.sort()
    stats["markets"] = len(series)
    stats["quotes"] = sum(len(v) for v in series.values())
    if verbose:
        print(f"  book: {dict(stats)}")
    return dict(series), (stats, depth_samples)


def report_depth(depth_samples):
    print("\n" + "=" * 78)
    print("QUEUE DEPTH AT THE TOUCH  --  re-measuring PLAN sec.4")
    print("=" * 78)
    if not depth_samples:
        print("  no valid book snapshots to measure.")
        return
    print("  PLAN.md sec.4 killed the maker strategy on 'best bid 0.40 with")
    print("  3,767 contracts resting'. That came from a REST call which RUNBOOK")
    print("  separately records as mis-parsed (levels ascending, truncated from")
    print("  the bottom, top-of-book hidden). Here it is from the websocket.\n")
    print(f"  {'yes-bid':>9}{'samples':>9}{'median bid depth':>19}"
          f"{'median ask depth':>19}")
    buckets = defaultdict(list)
    for yb, b, a in depth_samples:
        buckets[round(yb * 10) / 10.0].append((b, a))
    for k in sorted(buckets):
        v = buckets[k]
        if len(v) < 20:
            continue
        print(f"  {100*k:>8.0f}c{len(v):>9,}"
              f"{median([x[0] for x in v]):>19,.0f}"
              f"{median([x[1] for x in v]):>19,.0f}")
    allb = [b for _, b, _ in depth_samples]
    print(f"\n  overall median depth at the bid: {median(allb):,.0f} contracts")
    print("  A maker joining that queue is behind roughly that many contracts")
    print("  and fills only when the market trades THROUGH the level -- which")
    print("  is exactly when the fill is adversely selected. If this number is")
    print("  much smaller than 3,767, the maker path deserves a second look.")


# ===========================================================================
def selftest():
    import tempfile, shutil, random
    print("=" * 78)
    print("SELF-TEST -- does the rebuilt book match a known one?")
    print("=" * 78)
    fails = []
    rnd = random.Random(4)

    tmp = tempfile.mkdtemp()
    try:
        # THE REAL LAYOUT: two sibling directories, one file per hour each.
        # Writing the snapshot into orderbook_delta/ (as this test used to)
        # hides the only bug that matters here -- a reader that finishes the
        # whole delta channel before it opens the first snapshot file.
        os.makedirs(os.path.join(tmp, "orderbook_delta"))
        os.makedirs(os.path.join(tmp, "orderbook_snapshot"))
        yes = {40: 500.0, 39: 800.0, 38: 1200.0}
        no = {58: 400.0, 57: 900.0, 56: 1500.0}
        truth = []
        with gzip.open(os.path.join(tmp, "orderbook_snapshot",
                                    "20260825T00.jsonl.gz"), "wt") as f:
            f.write(json.dumps({"type": "orderbook_snapshot",
                                "_rx_ms": 1000 * 1000, "msg": {
                "market_ticker": "M1",
                "yes": [[p, s] for p, s in yes.items()],
                "no": [[p, s] for p, s in no.items()],
                "seq": 1, "ts": 1000}}) + "\n")
        with gzip.open(os.path.join(tmp, "orderbook_delta",
                                    "20260825T00.jsonl.gz"), "wt") as f:
            seq = 1
            for i in range(400):
                seq += 1
                side = "yes" if rnd.random() < 0.5 else "no"
                d = yes if side == "yes" else no
                other = no if side == "yes" else yes
                # a real book never crosses: best_yes + best_no <= 99
                room = 99 - (max(other) if other else 0)
                choices = [p for p in sorted(d) if p <= room]
                if max(d) + 1 <= room:
                    choices.append(max(d) + 1)
                if not choices:
                    seq -= 1
                    continue
                p = rnd.choice(choices)
                ch = rnd.choice([-100.0, -50.0, 50.0, 200.0])
                d[p] = d.get(p, 0.0) + ch
                if d[p] <= 0:
                    d.pop(p, None)
                if not d:
                    d[p] = 100.0
                f.write(json.dumps({"type": "orderbook_delta",
                                    "_rx_ms": (1000 + i + 1) * 1000, "msg": {
                    "market_ticker": "M1", "price": p, "delta": ch,
                    "side": side, "seq": seq, "ts": 1000 + i + 1}}) + "\n")
                if yes and no:
                    truth.append((1000 + i + 1, max(yes) / 100.0,
                                  (100 - max(no)) / 100.0,
                                  yes[max(yes)], no[max(no)]))
        got, _ = rebuild(tmp, verbose=False)
        g = got.get("M1", [])
        print(f"  replayed 400 deltas -> {len(g)} book states "
              f"(expected {len(truth)})")
        bad = 0
        gm = {t: (a, b, c, d) for t, a, b, c, d in g}
        for t, yb, ya, ybs, yas in truth:
            h = gm.get(t)
            if h is None:
                continue
            if (abs(h[0] - yb) > 1e-9 or abs(h[1] - ya) > 1e-9
                    or abs(h[2] - ybs) > 1e-9 or abs(h[3] - yas) > 1e-9):
                bad += 1
        print(f"  mismatches against the book we built by hand: {bad}")
        if bad:
            fails.append(f"{bad} rebuilt states disagree with ground truth")
        if len(g) < len(truth) * 0.9:
            fails.append("rebuilt far fewer states than expected")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # a sequence gap must invalidate, not silently corrupt
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "orderbook_delta"))
        os.makedirs(os.path.join(tmp, "orderbook_snapshot"))
        with gzip.open(os.path.join(tmp, "orderbook_snapshot",
                                    "20260825T00.jsonl.gz"), "wt") as f:
            f.write(json.dumps({"type": "orderbook_snapshot",
                                "_rx_ms": 1000, "msg": {
                "market_ticker": "M2", "yes": [[40, 100]], "no": [[58, 100]],
                "seq": 1, "ts": 1}}) + "\n")
        with gzip.open(os.path.join(tmp, "orderbook_delta",
                                    "20260825T00.jsonl.gz"), "wt") as f:
            for seq, ts in ((2, 2), (3, 3), (9, 4), (10, 5)):   # 4..8 missing
                f.write(json.dumps({"type": "orderbook_delta",
                                    "_rx_ms": ts * 1000, "msg": {
                    "market_ticker": "M2", "price": 40, "delta": 10.0,
                    "side": "yes", "seq": seq, "ts": ts}}) + "\n")
        got, (st, _) = rebuild(tmp, verbose=False)
        n_after = len([r for r in got.get("M2", []) if r[0] >= 4])
        print(f"\n  sequence gap: detected {st.get('seq_gaps', 0)}, "
              f"states emitted after the gap: {n_after}")
        if not st.get("seq_gaps"):
            fails.append("did not detect a sequence gap")
        if n_after:
            fails.append(f"emitted {n_after} book states after an unrepaired gap")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # the yes-ask must come from the no-bid, not from the yes side
    b = Book()
    b.snapshot([(40, 500)], [(58, 300)], 1, 0)
    top = b.top()
    print(f"\n  yes-bid 40c / no-bid 58c -> top = {top}")
    if not top or abs(top[2] - 0.42) > 1e-9:
        fails.append(f"yes-ask should be 1-0.58 = 0.42, got {top}")
    if not top or abs(top[3] - 300) > 1e-9:
        fails.append("ask size should come from the no-bid level")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- book matches ground truth tick for tick, gaps")
    print("invalidate rather than corrupt, and the yes-ask is derived from the")
    print("no-bid side.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    series, res = rebuild(a.data)
    if not series:
        print("\n  Nothing rebuilt. Either the collector is not recording")
        print("  orderbook_delta, or the message shape differs from the one")
        print("  assumed here. Run:  python research/doctor.py --data <dir>")
        return
    st, depth = res
    n = sum(len(v) for v in series.values())
    print(f"\n  {len(series):,} markets, {n:,} valid book states")
    report_depth(depth)


if __name__ == "__main__":
    main()
